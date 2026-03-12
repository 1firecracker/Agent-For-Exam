"""试卷处理业务服务

负责协调：
- 文件上传
- OCR 解析
- 结构化抽取
- 存储管理
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import UploadFile
import aiohttp

import app.config as config
from app.config import get_logger
from app.schemas.exam import ExamPaper, ExamListItem, ExamStatusResponse
from app.services.exam.exam_parser import ExamParser
from app.services.exam.exam_storage import ExamStorage
from app.services.config_service import config_service
from app.utils.text_cleaner import TextCleaner

logger = get_logger("app.exam_service")


class ExamService:
    """试卷处理服务"""
    
    def __init__(self):
        self.storage = ExamStorage()
        self.parser = ExamParser()

    @staticmethod
    def _infer_year(filename: str, text_snippet: str) -> Optional[str]:
        """从文件名和正文前段用正则推断年份，返回 4 位数字字符串或 None。"""
        year_re = re.compile(r"(19|20)\d{2}")
        for source in (filename, text_snippet):
            if not source:
                continue
            m = year_re.search(source)
            if m:
                return m.group(0)
        return None
    
    async def upload_exam(
        self,
        file: UploadFile,
        year: str = "",
        title: str = "",
        subject: str = ""
    ) -> dict:
        """上传并处理试卷

        Args:
            file: 上传的 PDF 文件
            year: 考试年份（可选；空则处理时由文件名与内容推断）
            title: 试卷标题
            subject: 科目名称
            
        Returns:
            包含 exam_id 和 task_id 的字典
        """
        # 1. 验证文件类型
        filename = file.filename or "unknown.pdf"
        ext = Path(filename).suffix.lower()
        if ext not in [".pdf"]:
            raise ValueError(f"不支持的文件类型: {ext}，仅支持 PDF")
        
        # 2. 读取文件内容
        content = await file.read()
        if len(content) > config.settings.max_file_size:
            raise ValueError(f"文件过大，最大支持 {config.settings.max_file_size // 1024 // 1024}MB")
        
        # 3. 创建试卷条目（未填年份时用占位，后续在解析流程中推断）
        year_initial = (year or "").strip() or "Unknown"
        exam_id = self.storage.create_exam_entry(year=year_initial, title=title, subject=subject)
        
        # 4. 保存原始 PDF（会写入 original_filename 供推断）
        self.storage.save_source_pdf(exam_id, content, filename)
        
        # 5. 启动异步处理任务
        task = asyncio.create_task(self._process_exam_async(exam_id, year_initial))
        task_id = f"exam-{exam_id}"
        
        logger.info(
            "试卷上传成功，开始异步处理",
            extra={"event": "exam.upload", "exam_id": exam_id, "file_name": filename, "year": year_initial}
        )
        
        return {
            "exam_id": exam_id,
            "task_id": task_id,
            "filename": filename,
            "status": "processing",
            "message": "试卷已上传，正在解析中..."
        }
    
    async def reparse_exam(self, exam_id: str) -> dict:
        """重新解析试卷（跳过 OCR，仅进行结构化抽取）
        
        Args:
            exam_id: 试卷 ID
            
        Returns:
            状态字典
        """
        # 验证试卷是否存在
        exam_info = self.storage.get_exam_status(exam_id)
        if not exam_info:
            raise FileNotFoundError(f"试卷不存在: {exam_id}")
            
        # 启动异步处理
        task = asyncio.create_task(self._reparse_exam_async(exam_id))
        
        return {
            "exam_id": exam_id,
            "status": "processing",
            "message": "已触发重新解析（跳过 OCR）"
        }

    async def _reparse_exam_async(self, exam_id: str) -> None:
        """异步处理重解析流程"""
        try:
            self.storage.update_status(exam_id, "processing")
            exam_info = self.storage.get_exam_status(exam_id)
            year = str(exam_info.get("year", "2024"))
            
            # 1. 获取已存在的 Markdown 内容
            exam_dir = self.storage.get_exam_dir(exam_id)
            cleaned_path = exam_dir / "cleaned.md"
            raw_path = exam_dir / "raw.md"
            
            cleaned_text = ""
            
            if cleaned_path.exists():
                logger.info(f"直接复用 cleaned.md: {exam_id}")
                cleaned_text = cleaned_path.read_text(encoding="utf-8")
            elif raw_path.exists():
                logger.info(f"复用 raw.md 并进行清洗: {exam_id}")
                raw_markdown = raw_path.read_text(encoding="utf-8")
                
                # 文本清洗
                images_dir = self.storage.get_images_dir(exam_id)
                cleaner = TextCleaner(base64_output_dir=images_dir)
                cleaned_text, base64_map = cleaner.clean(raw_markdown)
                self.storage.save_cleaned_markdown(exam_id, cleaned_text)
                
                if base64_map:
                    base64_path = exam_dir / "base64_map.json"
                    cleaner.save_base64_map(base64_path)
            else:
                self.storage.update_status(exam_id, "failed", error_message="Markdown 文件丢失，请重新上传")
                return

            # 2. 结构化解析
            logger.info(f"开始结构化解析 (Reparse): {exam_id}")
            questions = await self.parser.parse(cleaned_text, exam_id, year)
            
            # 3. 构建完整试卷对象
            exam_paper = ExamPaper(
                id=exam_id,
                year=year,
                title=exam_info.get("title", ""),
                subject=exam_info.get("subject", ""),
                questions=questions,
                source_pdf_path=exam_info.get("source_pdf_path", ""),
                raw_markdown_path=str(raw_path),
                parsed_json_path=str(exam_dir / "parsed.json"),
                created_at=datetime.utcnow(), # 注意：不想覆盖创建时间的话应读取原值，但简单起见更新
                status="completed"
            )
            
            # 4. 保存结果
            self.storage.save_parsed_json(exam_id, exam_paper)
            
            logger.info(
                "试卷重解析完成",
                extra={"event": "exam.reparsed", "exam_id": exam_id, "question_count": len(questions)}
            )
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"试卷重解析失败: {exam_id}, 错误: {error_msg}")
            self.storage.update_status(exam_id, "failed", error_message=error_msg)

    async def _process_exam_async(self, exam_id: str, year: str) -> None:
        """异步处理试卷的完整流程"""
        try:
            self.storage.update_status(exam_id, "processing")
            
            # 1. 获取 PDF 路径
            exam_info = self.storage.get_exam_status(exam_id)
            pdf_path = exam_info.get("source_pdf_path")
            if not pdf_path or not Path(pdf_path).exists():
                raise FileNotFoundError("原始 PDF 文件不存在")
            
            # 2. OCR 解析
            logger.info(f"开始 OCR 解析: {exam_id}")
            raw_markdown = await self._perform_ocr(exam_id, pdf_path)
            self.storage.save_raw_markdown(exam_id, raw_markdown)
            
            # 3. 文本清洗
            logger.info(f"开始文本清洗: {exam_id}")
            images_dir = self.storage.get_images_dir(exam_id)
            cleaner = TextCleaner(base64_output_dir=images_dir)
            cleaned_text, base64_map = cleaner.clean(raw_markdown)
            self.storage.save_cleaned_markdown(exam_id, cleaned_text)
            
            # 保存 base64 映射（如果有）
            if base64_map:
                base64_path = self.storage.get_exam_dir(exam_id) / "base64_map.json"
                cleaner.save_base64_map(base64_path)
            
            # 3.5 若用户未填年份，从文件名与正文前段推断并写回索引
            exam_info = self.storage.get_exam_status(exam_id)
            current_year = (exam_info.get("year") or "").strip()
            if not current_year or current_year == "Unknown":
                filename = exam_info.get("original_filename") or ""
                text_for_infer = (cleaned_text or "")[:2000]
                inferred = self._infer_year(filename, text_for_infer)
                year = inferred if inferred else "Unknown"
                self.storage.update_year(exam_id, year)
                if inferred:
                    logger.info(f"从文件名/内容推断年份: {exam_id} -> {year}")
            else:
                year = current_year
            
            # 4. 结构化解析
            logger.info(f"开始结构化解析: {exam_id}")
            questions = await self.parser.parse(cleaned_text, exam_id, year)
            
            # 5. 构建完整试卷对象
            exam_paper = ExamPaper(
                id=exam_id,
                year=year,
                title=exam_info.get("title", ""),
                subject=exam_info.get("subject", ""),
                questions=questions,
                source_pdf_path=pdf_path,
                raw_markdown_path=str(self.storage.get_exam_dir(exam_id) / "raw.md"),
                parsed_json_path=str(self.storage.get_exam_dir(exam_id) / "parsed.json"),
                created_at=datetime.utcnow(),
                status="completed"
            )
            
            # 6. 保存结果
            self.storage.save_parsed_json(exam_id, exam_paper)
            
            logger.info(
                "试卷解析完成",
                extra={"event": "exam.completed", "exam_id": exam_id, "question_count": len(questions)}
            )
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"试卷处理失败: {exam_id}, 错误: {error_msg}")
            self.storage.update_status(exam_id, "failed", error_message=error_msg)
    
    async def _perform_ocr(self, exam_id: str, pdf_path: str) -> str:
        """执行 OCR 解析"""
        ocr_cfg = config_service.get_config("ocr")
        host = (ocr_cfg.get("host") or "https://api.siliconflow.cn/v1").rstrip("/")
        model = (ocr_cfg.get("model") or "PaddlePaddle/PaddleOCR-VL-1.5").strip()
        api_key = (ocr_cfg.get("api_key") or "").strip()

        if api_key:
            try:
                return await self._ocr_pdf_with_siliconflow(
                    pdf_path=pdf_path,
                    host=host,
                    api_key=api_key,
                    model=model,
                )
            except Exception as e:
                logger.warning(f"SiliconFlow OCR 失败，将回退本地解析: {e}")

        # 回退方案：使用本地 PDF 解析器
        from app.utils.pdf_parser import PDFParser
        parser = PDFParser()
        return parser.extract_text(pdf_path)

    async def _ocr_pdf_with_siliconflow(self, pdf_path: str, host: str, api_key: str, model: str) -> str:
        """使用 SiliconFlow 的 OCR 模型解析 PDF（逐页渲染为图片后识别）。"""
        import fitz  # PyMuPDF

        file_path_obj = Path(pdf_path).resolve()
        if not file_path_obj.exists():
            raise FileNotFoundError(f"文件不存在: {pdf_path}")

        # 避免极端大 PDF 导致请求/成本不可控：这里做一个软限制
        max_pages_soft_limit = 80
        texts: List[str] = []

        with fitz.open(str(file_path_obj)) as doc:
            page_count = doc.page_count
            if page_count > max_pages_soft_limit:
                logger.warning(
                    f"PDF 页数过多({page_count})，仅识别前 {max_pages_soft_limit} 页以避免请求过大"
                )
                page_count = max_pages_soft_limit

            for i in range(page_count):
                page = doc.load_page(i)
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")

                page_text = await self._ocr_image_with_siliconflow(
                    image_base64=img_b64,
                    host=host,
                    api_key=api_key,
                    model=model,
                )
                if page_text:
                    texts.append(page_text.strip())

        return "\n\n".join([t for t in texts if t])

    async def _ocr_image_with_siliconflow(self, image_base64: str, host: str, api_key: str, model: str) -> str:
        """调用 SiliconFlow OpenAI 兼容接口的 OCR（Vision）模型，返回识别出的纯文本。"""
        url = f"{host}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # 采用 OpenAI 兼容的多模态消息格式（image_url data URL）
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是 OCR 引擎。请只输出从图片中识别出的文字内容，不要添加任何解释或多余标点。",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请识别这张图片中的文字并原样输出。"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                        },
                    ],
                },
            ],
            "temperature": 0.0,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=180),
            ) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"OCR 请求失败: {resp.status}, {text[:500]}")
                data = json.loads(text)
                content = (
                    (data.get("choices") or [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                return content or ""
    
    def get_exam_status(self, exam_id: str) -> Optional[ExamStatusResponse]:
        """获取试卷处理状态"""
        info = self.storage.get_exam_status(exam_id)
        if not info:
            return None
        
        # 如果已完成，附带完整数据
        result = None
        if info.get("status") == "completed":
            result = self.storage.get_exam(exam_id)
        
        return ExamStatusResponse(
            exam_id=exam_id,
            status=info.get("status", "unknown"),
            message=info.get("error_message"),
            result=result
        )
    
    def get_exam(self, exam_id: str) -> Optional[ExamPaper]:
        """获取完整试卷数据"""
        return self.storage.get_exam(exam_id)
    
    def list_exams(self, year: str = None, subject: str = None) -> List[ExamListItem]:
        """列出试卷"""
        return self.storage.list_exams(year=year, subject=subject)
    
    def delete_exam(self, exam_id: str) -> bool:
        """删除试卷"""
        return self.storage.delete_exam(exam_id)

    def update_exam_year(self, exam_id: str, year: str) -> bool:
        """更新试卷年份（索引 + 已解析的 parsed.json）"""
        info = self.storage.get_exam_status(exam_id)
        if not info:
            return False
        year_str = (year or "").strip() or "Unknown"
        self.storage.update_year(exam_id, year_str)
        exam = self.storage.get_exam(exam_id)
        if exam:
            exam.year = year_str
            self.storage.save_parsed_json(exam_id, exam)
        return True
