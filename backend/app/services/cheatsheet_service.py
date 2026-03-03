"""Cheatsheet 服务 — 从文档内容生成紧凑速查表，支持超长文档分块"""
import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

import aiohttp
import tiktoken

import app.config as config
from app.utils.document_parser import DocumentParser

logger = config.get_logger("app.cheatsheet")

CHUNK_SIZE = 5000
CHUNK_OVERLAP = 400
CONTEXT_TAIL_TOKENS = 800

_enc = None
def _get_enc():
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("cl100k_base")
    return _enc


class CheatsheetService:

    def __init__(self):
        self.document_parser = DocumentParser()

    @staticmethod
    def _count_tokens(text: str) -> int:
        return len(_get_enc().encode(text))

    @staticmethod
    def _chunk_text(text: str) -> List[str]:
        """将文本按 token 数分块，块间有重叠"""
        enc = _get_enc()
        tokens = enc.encode(text)
        if len(tokens) <= CHUNK_SIZE:
            return [text]
        chunks = []
        start = 0
        while start < len(tokens):
            end = min(start + CHUNK_SIZE, len(tokens))
            chunks.append(enc.decode(tokens[start:end]))
            if end >= len(tokens):
                break
            next_start = end - CHUNK_OVERLAP
            if next_start <= start:
                next_start = end
            start = next_start
        return chunks

    @staticmethod
    def _tail_text(text: str, max_tokens: int) -> str:
        """取文本末尾 max_tokens 个 token 对应的文字"""
        enc = _get_enc()
        tokens = enc.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return enc.decode(tokens[-max_tokens:])

    def _collect_document_texts(self, subject_id: str, file_ids: Optional[List[str]] = None) -> List[Dict]:
        from app.services.document_service import DocumentService
        doc_service = DocumentService()
        documents = doc_service.list_documents_for_subject(subject_id)
        if file_ids:
            id_set = set(file_ids)
            documents = [d for d in documents if d.get("file_id") in id_set]
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
                    "file_id": doc.get("file_id"), "error": str(e),
                })
        return results

    def _collect_image_refs(self, subject_id: str, documents: List[Dict]) -> List[Dict]:
        refs = []
        for doc in documents:
            fid = doc["file_id"]
            for page in range(1, doc.get("total_pages", 0) + 1):
                refs.append({
                    "file_id": fid, "page": page,
                    "url": f"/api/subjects/{subject_id}/documents/{fid}/slides/{page}/image",
                })
        return refs

    def _base_requirements(self, include_images: bool, custom_prompt: Optional[str] = None) -> str:
        img = ""
        if include_images:
            img = "\n- 在章节标题后使用 <!-- PAGE:file_id:page --> 标记关联页码"
        user = ""
        if custom_prompt:
            user = f"\n- 用户额外要求：{custom_prompt}"
        return f"""要求：
- 使用 Markdown 格式输出，不要用 ```markdown 代码块包裹
- 用 ## 分章节/主题，用 - 列要点
- 每个要点一句话，信息密集紧凑，不要冗余解释
- 保留关键公式、定义、数据
- 使用中文输出（如果原文是中文）{img}{user}"""

    def _build_first_prompt(self, chunk_text: str, total_chunks: int,
                            include_images: bool, custom_prompt: Optional[str] = None) -> str:
        reqs = self._base_requirements(include_images, custom_prompt)
        multi = ""
        if total_chunks > 1:
            multi = f"\n\n注意：讲义内容较长，将分 {total_chunks} 次输入。这是第 1 部分，请先处理这部分内容。"
        return f"""你是一名教学助手，请根据以下讲义内容，生成一份紧凑的考试速查表（Cheatsheet）。

{reqs}{multi}

讲义内容：
{chunk_text}"""

    def _build_continuation_prompt(self, chunk_text: str, chunk_idx: int, total_chunks: int,
                                   cheatsheet_tail: str) -> str:
        return f"""继续生成考试速查表。这是第 {chunk_idx + 1}/{total_chunks} 部分。

以下是之前已生成的速查表末尾（仅供上下文衔接参考，不要重复这些内容）：
---
{cheatsheet_tail}
---

请继续根据以下新内容，补充速查表（与之前内容衔接，不要重复已总结的知识点）：

{chunk_text}"""

    async def _stream_llm(self, prompt: str, system_msg: str) -> AsyncGenerator[str, None]:
        """调用 LLM 流式返回原始文本片段"""
        from app.services.config_service import config_service
        chat_config = config_service.get_config("chat")
        api_key = chat_config.get("api_key", config.settings.chat_llm_binding_api_key)
        model = chat_config.get("model", config.settings.chat_llm_model)
        host = chat_config.get("host", config.settings.chat_llm_binding_host)

        if not api_key:
            return

        api_url = f"{host}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            "stream": True, "temperature": 0.3, "max_tokens": 8000,
        }

        timeout = aiohttp.ClientTimeout(total=config.settings.timeout)
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, headers=headers, json=payload, timeout=timeout) as resp:
                if resp.status != 200:
                    return
                async for line in resp.content:
                    if not line:
                        continue
                    for part in line.decode("utf-8").split("\n"):
                        part = part.strip()
                        if not part or part.startswith(":"):
                            continue
                        if part.startswith("data: "):
                            part = part[6:]
                        if part == "[DONE]":
                            return
                        try:
                            data = json.loads(part)
                            content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

    async def generate_stream(
        self,
        subject_id: str,
        include_images: bool = False,
        file_ids: Optional[List[str]] = None,
        custom_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        documents = self._collect_document_texts(subject_id, file_ids)
        if not documents:
            yield json.dumps({"error": "当前知识库没有可用的文档"}) + "\n"
            return

        # 图片引用
        if include_images:
            refs = self._collect_image_refs(subject_id, documents)
            if refs:
                yield json.dumps({"image_refs": refs}) + "\n"

        # 拼接所有文档文本
        combined = ""
        for doc in documents:
            combined += f"\n=== 文档: {doc['filename']} ===\n{doc['text']}\n"

        # 分块
        chunks = self._chunk_text(combined)
        total_chunks = len(chunks)

        logger.info("Cheatsheet 生成开始", extra={
            "event": "cheatsheet.generate_start",
            "subject_id": subject_id,
            "total_tokens": self._count_tokens(combined),
            "total_chunks": total_chunks,
        })

        if total_chunks > 1:
            yield json.dumps({"progress": f"文档较长，将分 {total_chunks} 次生成"}) + "\n"

        system_msg = "你是一名教学助手，专门生成紧凑的考试速查表。严格按照 Markdown 格式输出，不要使用代码块包裹。"
        accumulated = ""

        try:
            for i, chunk_text in enumerate(chunks):
                if i == 0:
                    prompt = self._build_first_prompt(chunk_text, total_chunks, include_images, custom_prompt)
                else:
                    tail = self._tail_text(accumulated, CONTEXT_TAIL_TOKENS)
                    prompt = self._build_continuation_prompt(chunk_text, i, total_chunks, tail)

                async for token in self._stream_llm(prompt, system_msg):
                    accumulated += token
                    yield json.dumps({"content": token}) + "\n"

                if total_chunks > 1 and i < total_chunks - 1:
                    sep = "\n\n"
                    accumulated += sep
                    yield json.dumps({"content": sep}) + "\n"

        except asyncio.TimeoutError:
            yield json.dumps({"error": "生成超时，请重试"}) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"
