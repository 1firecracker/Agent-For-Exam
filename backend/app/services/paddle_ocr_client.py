"""
Gitee PaddleOCR-VL 客户端封装。

支持：
- 提交文档解析任务
- 轮询任务状态
- 下载并落地 Markdown / 图片
- 将结果整理为解析器可用的数据结构
"""
from __future__ import annotations

import base64
import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
from requests_toolbelt import MultipartEncoder

import app.config as config


logger = logging.getLogger(__name__)


class GiteePaddleOCRClient:
    """调用 Gitee AI PaddleOCR-VL 异步接口的小型客户端。
    
    增强功能：支持多 Token 轮询（备用 API Key 逻辑）。
    """

    API_URL = "https://ai.gitee.com/v1/async/documents/parse"
    TASK_STATUS_URL = "https://ai.gitee.com/api/v1/task/{task_id}"

    def __init__(
        self,
        token: str,
        timeout: int = 30,
        max_retry: int = 2,
        poll_interval: int = 5,
        max_wait: int = 60,
    ):
        # 支持逗号分隔的多个 token
        self.tokens = [t.strip() for t in token.split(",") if t.strip()]
        self._current_token_idx = 0
        
        self.timeout = timeout
        self.max_retry = max_retry
        self.poll_interval = poll_interval
        self.max_wait = max_wait

    @property
    def enabled(self) -> bool:
        return bool(self.tokens)

    def _get_token(self) -> str:
        """获取当前使用的 Token"""
        if not self.tokens:
            return ""
        return self.tokens[self._current_token_idx]

    def _rotate_token(self) -> bool:
        """切换到下一个 Token。如果切换成功（还有未尝试的 Token），返回 True；如果所有 Token 都试过了，返回 False。"""
        if len(self.tokens) <= 1:
            return False
            
        next_idx = (self._current_token_idx + 1) % len(self.tokens)
        if next_idx == 0:
            # 已经轮了一圈，所有 Token 都试过了
            # 这里的逻辑可以根据需求调整：是重置继续试，还是报错
            # 目前策略：重置为 0，但返回 False 表示“这一轮都失败了”
             self._current_token_idx = 0
             return False
        
        self._current_token_idx = next_idx
        logger.info(f"切换 OCR Token: 使用第 {next_idx + 1}/{len(self.tokens)} 个 Token")
        return True

    def parse_pdf(
        self,
        file_path: str,
        conversation_id: str,
        document_id: str,
        output_dir: Path = None,
    ) -> Dict[str, object]:
        if not self.enabled:
            raise RuntimeError("Gitee OCR token 未配置，无法使用远程 OCR")

        file_path_obj = Path(file_path).resolve()
        if not file_path_obj.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        task_id = self._submit_task(file_path_obj)
        task_json = self._poll_task(task_id)

        status = task_json.get("status")
        if status != "success":
            raise RuntimeError(f"Gitee OCR 任务失败: {json.dumps(task_json, ensure_ascii=False)}")

        if output_dir:
            base_dir = output_dir
        else:
            base_dir = (
                Path(config.settings.exercises_dir)
                / conversation_id
                / "samples"
                / document_id
            )
            
        output = task_json.get("output") or {}
        self._persist_task(task_json, base_dir)
        text, images = self._persist_segments(output, base_dir)

        return {
            "text": text,
            "images": images,
            "file_type": "pdf",
        }

    # ---------------- internal helpers ---------------- #

    def _submit_task(self, file_path: Path) -> str:
        # 总重试次数 = (Token数 * (max_retry + 1))
        # 但为了简单，我们在外层循环处理 Token 切换，内层处理网络抖动重试
        
        # 尝试遍历所有 Token
        tokens_tried = 0
        total_tokens = len(self.tokens)
        
        while tokens_tried < total_tokens:
            # 对当前 Token 进行重试
            for attempt in range(self.max_retry + 1):
                fields = [
                    ("model", "MinerU2.5"),
                    ("is_ocr", "true"),
                    ("include_image_base64", "true"),
                    ("formula_enable", "true"),
                    ("table_enable", "true"),
                    ("layout_model", "doclayout_yolo"),
                    ("output_format", "md"),
                ]
                mime = file_path.suffix.lower()
                
                try:
                    # 必须每次重新打开文件，因为 MultipartEncoder 读取后指针会移动
                    with file_path.open("rb") as fh:
                        # 修复: 避免文件名包含中文导致 'latin-1' 编码错误
                        # 我们上传给 Gitee 时，使用一个安全的 ASCII 文件名
                        safe_filename = f"source_file{file_path.suffix}"
                        
                        fields.append(
                            ("file", (safe_filename, fh, self._guess_mime(mime)))
                        )
                        encoder = MultipartEncoder(fields)
                        headers = {
                            "Authorization": f"Bearer {self._get_token()}",
                            "Content-Type": encoder.content_type,
                        }
                        
                        response = requests.post(
                            self.API_URL,
                            headers=headers,
                            data=encoder,
                            timeout=self.timeout,
                        )
                        
                        # 检查响应
                        # 401/403: Token 无效/过期 -> 立即切换 Token
                        if response.status_code in (401, 403):
                            logger.warning(f"Token {self._current_token_idx+1} 无效 ({response.status_code})，尝试切换...")
                            raise PermissionError("Token invalid")
                        
                        response.raise_for_status()
                        payload = response.json()
                        
                        # error_code 18: QPS limit -> 立即切换 Token
                        if payload.get("error_code") == 18:
                            logger.warning(f"Token {self._current_token_idx+1} 达到 QPS 限制，尝试切换...")
                            raise PermissionError("QPS limit reached")
                            
                        if payload.get("error"):
                            raise RuntimeError(json.dumps(payload, ensure_ascii=False))
                            
                        return payload.get("task_id") or payload.get("result", {}).get("task_id")
                        
                except PermissionError:
                    # Token 相关错误（401/403/QPS），跳出内层重试，直接切换下一个 Token
                    break 
                except Exception as exc:
                    logger.warning("Gitee OCR 提交失败: %s (attempt=%d)", exc, attempt + 1)
                    if attempt >= self.max_retry:
                        # 当前 Token 的重试次数用尽，如果没有下一个 Token 可用，这里的异常会被抛出
                        # 但我们希望进入外层的 Token 轮换
                        break
                    time.sleep(1 + attempt)
            
            # 尝试切换到下一个 Token
            if self._rotate_token():
                tokens_tried += 1
                logger.warning("Gitee OCR 提交失败，切换到下一个 Token")
                time.sleep(1) # 切换后稍等一下
                continue
            else:
                # 已经轮完了所有 Token 且都失败了
                raise RuntimeError("Gitee OCR 提交失败，所有 Token 均不可用")
                
        raise RuntimeError("Gitee OCR 提交失败，重试次数耗尽")

    def _poll_task(self, task_id: str) -> Dict[str, object]:
        url = self.TASK_STATUS_URL.format(task_id=task_id)
        # 动态获取当前 Token
        headers = {"Authorization": f"Bearer {self._get_token()}"}

        elapsed = 0
        while elapsed <= self.max_wait:
            response = self._send_with_retry(
                method="GET",
                url=url,
                headers=headers,
            )
            task_json = response.json()
            status = task_json.get("status")
            if status in {"success", "failed", "cancelled"}:
                return task_json
            time.sleep(self.poll_interval)
            elapsed += self.poll_interval

        raise TimeoutError(f"Gitee OCR 轮询超时（task_id={task_id}）")

    def _persist_task(self, task_json: Dict[str, object], base_dir: Path) -> None:
        base_dir.mkdir(parents=True, exist_ok=True)
        task_file = base_dir / "task.json"
        task_file.write_text(json.dumps(task_json, ensure_ascii=False, indent=2), encoding="utf-8")

    def _persist_segments(self, output: Dict[str, object], base_dir: Path) -> (str, List[Dict[str, object]]):
        segments = output.get("segments") or []
        images_dir = base_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        markdown_lines: List[str] = []
        images_meta: List[Dict[str, object]] = []
        # 匹配完整的 Markdown 图片语法: ![alt](data:image/...;base64,...)
        image_pattern = re.compile(r"!\[([^\]]*)\]\(data:image/(png|jpeg|jpg);base64,([^)]+)\)")

        for seg in segments:
            content = seg.get("content", "")
            matches = list(image_pattern.finditer(content))
            for idx, match in enumerate(matches, start=1):
                alt_text = match.group(1)  # alt 文本
                ext = match.group(2)  # 图片格式
                data = match.group(3)  # base64 数据
                image_bytes = base64.b64decode(data)
                image_name = f"image_{seg.get('index', 0)}_{idx}.{ 'jpg' if ext == 'jpeg' else ext}"
                image_path = images_dir / image_name
                image_path.write_bytes(image_bytes)

                # 替换为完整的 Markdown 图片语法
                content = content.replace(match.group(0), f"![{alt_text}](images/{image_name})")
                images_meta.append(
                    {
                        "page_number": None,
                        "image_index": idx,
                        "file_path": f"images/{image_name}",
                        "image_format": image_path.suffix.lstrip("."),
                        "width": 0,
                        "height": 0,
                    }
                )

            markdown_lines.append(content)

        markdown = "\n\n".join(markdown_lines)
        result_path = base_dir / "result.md"
        result_path.write_text(markdown, encoding="utf-8")

        return markdown, images_meta

    def _send_with_retry(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data=None,
    ) -> requests.Response:
        for attempt in range(self.max_retry + 1):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=data,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = {}
                try:
                    payload = response.json()
                except ValueError:
                    pass
                if isinstance(payload, dict) and payload.get("error_code") == 18:
                    # QPS 限制
                    raise RuntimeError("Open api qps request limit reached")
                return response
            except Exception as exc:
                logger.warning("Gitee OCR 请求失败: %s (attempt=%d)", exc, attempt + 1)
                if attempt >= self.max_retry:
                    raise
                time.sleep(1 + attempt)

    @staticmethod
    def _guess_mime(ext: str) -> str:
        mapping = {
            ".pdf": "application/pdf",
        }
        return mapping.get(ext, "application/octet-stream")


def get_gitee_client() -> GiteePaddleOCRClient:
    settings = config.settings
    return GiteePaddleOCRClient(
        token=settings.gitee_ocr_token,
        timeout=settings.gitee_ocr_timeout,
        max_retry=settings.gitee_ocr_max_retry,
        poll_interval=settings.gitee_ocr_poll_interval,
        max_wait=settings.gitee_ocr_max_wait,
    )

