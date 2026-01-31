"""校验候选映射：读取讲义指定页，判断是否包含该知识点"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import app.config as config


def _get_page_content(subject_id: str, document_id: str, page_index: int) -> Optional[str]:
    """从 page_index JSON 中读取指定页的文本。page_index 为 1-based。"""
    page_dir = Path(config.settings.conversations_metadata_dir) / "subjects" / subject_id / "page_index"
    path = page_dir / f"{document_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for p in data.get("pages", []):
        if p.get("page_index") == page_index:
            return p.get("content", "")
    return None


def verify_draft_mapping(
    subject_id: str,
    knowledge_point: str,
    document_id: str,
    page_numbers: List[int],
) -> Dict[str, Any]:
    """
    校验单条「知识点 — 文档 — 页码」是否成立：该页内容是否包含该知识点。
    返回 {"status": "accepted"|"rejected", "feedback": str}。
    """
    if not page_numbers:
        return {"status": "rejected", "feedback": "未提供页码"}
    content_parts: List[str] = []
    for pn in page_numbers:
        c = _get_page_content(subject_id, document_id, pn)
        if c:
            content_parts.append(c)
    if not content_parts:
        return {"status": "rejected", "feedback": f"无法读取文档 {document_id} 的页码 {page_numbers}"}
    combined = " ".join(content_parts)
    # 简单规则：知识点名称（或去掉空格）出现在页面内容中即通过
    k = knowledge_point.strip()
    if not k:
        return {"status": "rejected", "feedback": "知识点名称为空"}
    if k in combined or k.replace(" ", "") in combined.replace(" ", ""):
        return {"status": "accepted", "feedback": ""}
    return {
        "status": "rejected",
        "feedback": f"在文档 {document_id} 第 {page_numbers} 页未发现知识点「{k}」，请核对或更换检索词",
    }
