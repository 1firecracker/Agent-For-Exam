"""校验候选映射：读取讲义指定页，由 Verify Agent 语义判断是否包含该知识点（方案 B）"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import app.config as config

from app.services.exam_analysis.verify_agent import verify_one as verify_agent_verify_one


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


async def verify_draft_mapping(
    subject_id: str,
    knowledge_point: str,
    document_id: str,
    page_numbers: List[int],
) -> Dict[str, Any]:
    """
    校验单条「知识点 — 文档 — 页码」是否成立：由 Verify Agent 语义判断该页是否包含该知识点。
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
    result = await verify_agent_verify_one(knowledge_point.strip(), combined)
    if result.get("status") == "accepted":
        return {"status": "accepted", "feedback": result.get("feedback", "") or ""}
    feedback = result.get("feedback", "") or f"在文档 {document_id} 第 {page_numbers} 页未发现知识点，请核对或更换检索词"
    return {"status": "rejected", "feedback": feedback}
