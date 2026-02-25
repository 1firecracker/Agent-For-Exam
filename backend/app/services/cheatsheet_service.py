"""Cheatsheet 服务 — 从文档内容生成紧凑速查表"""
import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

import aiohttp

import app.config as config
from app.utils.document_parser import DocumentParser

logger = config.get_logger("app.cheatsheet")


class CheatsheetService:

    def __init__(self):
        self.document_parser = DocumentParser()

    def _collect_document_texts(self, subject_id: str) -> List[Dict]:
        """收集知识库下所有文档的文本和元信息"""
        from app.services.document_service import DocumentService
        doc_service = DocumentService()
        documents = doc_service.list_documents_for_subject(subject_id)

        results = []
        for doc in documents:
            file_path = doc.get("file_path")
            if not file_path or not Path(file_path).exists():
                continue
            try:
                text = self.document_parser.extract_text(file_path, doc.get("file_id"))
                results.append({
                    "file_id": doc.get("file_id"),
                    "filename": doc.get("original_filename", ""),
                    "extension": doc.get("file_extension", ""),
                    "text": text,
                    "total_pages": doc.get("total_pages", 0),
                })
            except Exception as e:
                logger.warning("提取文档文本失败", extra={
                    "event": "cheatsheet.extract_failed",
                    "file_id": doc.get("file_id"),
                    "error": str(e),
                })
        return results

    def _collect_image_refs(self, subject_id: str, documents: List[Dict]) -> List[Dict]:
        """收集文档中每页的图片引用 URL"""
        refs = []
        for doc in documents:
            fid = doc["file_id"]
            pages = doc.get("total_pages", 0)
            for page in range(1, pages + 1):
                refs.append({
                    "file_id": fid,
                    "page": page,
                    "url": f"/api/subjects/{subject_id}/documents/{fid}/slides/{page}/image",
                })
        return refs

    def _build_prompt(self, documents: List[Dict], include_images: bool) -> str:
        combined = ""
        for doc in documents:
            combined += f"\n=== 文档: {doc['filename']} ===\n{doc['text']}\n"

        image_instruction = ""
        if include_images:
            image_instruction = """
- 在每个章节标题后使用 <!-- PAGE:file_id:page --> 标记表示关联的文档页码，前端会自动替换为图片。"""

        return f"""你是一名教学助手，请根据以下讲义内容，生成一份紧凑的考试速查表（Cheatsheet）。

要求：
- 使用 Markdown 格式输出
- 用 ## 分章节/主题
- 用 - 列要点，每个要点一句话概括核心知识
- 信息要密集紧凑，不要冗余解释
- 保留关键公式、定义、数据
- 使用中文输出（如果原文是中文）{image_instruction}

讲义内容：
{combined}"""

    async def generate_stream(
        self,
        subject_id: str,
        include_images: bool = False,
    ) -> AsyncGenerator[str, None]:
        """流式生成 cheatsheet（NDJSON 格式）"""
        documents = self._collect_document_texts(subject_id)
        if not documents:
            yield json.dumps({"error": "当前知识库没有可用的文档"}) + "\n"
            return

        image_refs = []
        if include_images:
            image_refs = self._collect_image_refs(subject_id, documents)

        prompt = self._build_prompt(documents, include_images)

        from app.services.config_service import config_service
        chat_config = config_service.get_config("chat")
        api_key = chat_config.get("api_key", config.settings.chat_llm_binding_api_key)
        model = chat_config.get("model", config.settings.chat_llm_model)
        host = chat_config.get("host", config.settings.chat_llm_binding_host)

        if not api_key:
            yield json.dumps({"error": "LLM API Key 未配置"}) + "\n"
            return

        if include_images and image_refs:
            yield json.dumps({"image_refs": image_refs}) + "\n"

        api_url = f"{host}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是一名教学助手，专门生成紧凑的考试速查表。严格按照 Markdown 格式输出。"},
                {"role": "user", "content": prompt},
            ],
            "stream": True,
            "temperature": 0.3,
            "max_tokens": 8000,
        }

        timeout = aiohttp.ClientTimeout(total=config.settings.timeout)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, headers=headers, json=payload, timeout=timeout) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        yield json.dumps({"error": f"LLM API 错误: {resp.status}"}) + "\n"
                        return

                    async for line in resp.content:
                        if not line:
                            continue
                        for chunk in line.decode("utf-8").split("\n"):
                            chunk = chunk.strip()
                            if not chunk or chunk.startswith(":"):
                                continue
                            if chunk.startswith("data: "):
                                chunk = chunk[6:]
                            if chunk == "[DONE]":
                                return
                            try:
                                data = json.loads(chunk)
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield json.dumps({"content": content}) + "\n"
                            except json.JSONDecodeError:
                                continue
        except asyncio.TimeoutError:
            yield json.dumps({"error": "生成超时，请重试"}) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"
