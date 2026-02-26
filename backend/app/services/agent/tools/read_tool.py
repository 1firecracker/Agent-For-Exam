"""
阅读文档指定页码工具：按文档名与起止页码返回讲义/教材文本。
"""
import json
from pathlib import Path
from typing import Any, Dict

import app.config as config
from app.services.conversation_service import ConversationService
from app.services.document_service import DocumentService


def _load_page_content(
    context_id: str,
    is_subject: bool,
    document_id: str,
    start_page: int,
    end_page: int,
) -> str:
    """从 page_index JSON 读取 [start_page, end_page] 页内容并拼接。页码 1-based。"""
    if is_subject:
        page_dir = Path(config.settings.conversations_metadata_dir) / "subjects" / context_id / "page_index"
    else:
        page_dir = Path(config.settings.conversations_metadata_dir) / "page_index" / context_id
    path = page_dir / f"{document_id}.json"
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    parts = []
    pages = data.get("pages", [])
    for p in pages:
        pi = p.get("page_index")
        if pi is None:
            continue
        if start_page <= pi <= end_page:
            raw = p.get("content", "")
            parts.append(f"【第 {pi} 页】\n{raw}" if raw else f"【第 {pi} 页】")
    out = "\n\n".join(parts)
    return out


async def read_handler(
    conversation_id: str,
    filename: str,
    start_page: int,
    end_page: int,
) -> Dict[str, Any]:
    """
    读取指定文档的起止页码范围内的文本内容。
    文档名需与当前对话/知识库中的文件名一致（可用 list_documents 查看）。
    页码为 1-based，含起始页和终止页。
    """
    try:
        if not filename or not filename.strip():
            return {"status": "error", "message": "请提供文档名（filename）"}
        if start_page is None or end_page is None:
            return {"status": "error", "message": "请提供起始页码和终止页码"}
        start_page = int(start_page)
        end_page = int(end_page)
        if start_page < 1 or end_page < 1:
            return {"status": "error", "message": "页码必须为正整数"}
        if start_page > end_page:
            return {"status": "error", "message": "起始页码不能大于终止页码"}

        conv_service = ConversationService()
        doc_service = DocumentService()
        conversation = conv_service.get_conversation(conversation_id)
        subject_id = conversation.get("subject_id") if conversation else None

        if subject_id:
            documents = doc_service.list_documents_for_subject(subject_id)
            context_id = subject_id
            is_subject = True
        else:
            documents = doc_service.list_documents(conversation_id)
            context_id = conversation_id
            is_subject = False

        filename_clean = filename.strip()
        file_id = None
        for doc in documents:
            if (doc.get("filename") or "").strip() == filename_clean:
                file_id = doc.get("file_id")
                break
        if not file_id:
            return {
                "status": "error",
                "message": f"未找到文档「{filename_clean}」。请先调用 list_documents 查看当前文档列表及准确文件名。",
            }

        content = _load_page_content(context_id, is_subject, file_id, start_page, end_page)
        if not content:
            return {
                "status": "success",
                "message": f"文档「{filename_clean}」第 {start_page}–{end_page} 页无内容或页码超出范围",
                "content": "",
                "filename": filename_clean,
                "start_page": start_page,
                "end_page": end_page,
            }
        return {
            "status": "success",
            "message": "",
            "content": content,
            "filename": filename_clean,
            "start_page": start_page,
            "end_page": end_page,
        }
    except Exception as e:
        return {"status": "error", "message": f"读取失败: {str(e)}"}


from app.services.agent.tool_registry import ToolDefinition, ToolParameter

READ_TOOL = ToolDefinition(
    name="read",
    description="按文档名和起止页码读取讲义/教材的纯文本内容。文档名必须与当前对话中的文件名完全一致（可通过 list_documents 查看）。页码从 1 开始，包含起始页和终止页。",
    parameters={
        "conversation_id": ToolParameter(type="string", description="对话ID", required=True),
        "filename": ToolParameter(type="string", description="文档名（与 list_documents 返回的 filename 一致）", required=True),
        "start_page": ToolParameter(type="number", description="起始页码（1-based，含）", required=True),
        "end_page": ToolParameter(type="number", description="终止页码（1-based，含）", required=True),
    },
    handler=read_handler,
    category="document",
    rate_limit=30,
)
