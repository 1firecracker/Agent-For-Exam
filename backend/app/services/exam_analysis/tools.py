"""试题分析 Sub Agent 工具：检索知识库、定位页码、提交候选映射"""
from typing import Any, Dict, List

from app.services.graph_service import GraphService
from app.services.exam_analysis.verifier import verify_draft_mapping
from app.services.exam_analysis.trace_storage import TraceStorage


async def query_knowledge_base(subject_id: str, conversation_id: str, query: str) -> Dict[str, Any]:
    """在讲义知识库中检索与 query 相关的内容（aquery_data + 实体/关系/块+页码，与对话检索逻辑一致）。"""
    service = GraphService()
    rag_id = subject_id or conversation_id
    context_id = subject_id or conversation_id
    result = await service.query_knowledge_raw(rag_id, query, "mix", context_id=context_id)
    if result.get("status") == "success":
        return {"status": "success", "result": result.get("result", "")}
    return {"status": "success", "result": result.get("message", "未检索到相关内容")}


def locate_knowledge_pages(subject_id: str, conversation_id: str, entity_or_keyword: str) -> Dict[str, Any]:
    """根据实体名或关键词，在讲义中定位可能出现的 (文档, 页码)。"""
    graph = GraphService()
    entities = graph.load_entity_page_mapping(subject_id or conversation_id)
    entity_lower = entity_or_keyword.strip().lower()
    candidates: List[Dict[str, Any]] = []
    for name, pages in entities.items():
        if entity_lower in name.lower() or name.lower() in entity_lower:
            for p in pages[:3]:
                candidates.append({"entity": name, "document_id": p.get("file_id"), "page_index": p.get("page_index")})
    if not candidates:
        return {"status": "success", "candidates": [], "message": "实体映射中未找到匹配，请尝试其他关键词或先构建实体页码映射"}
    return {"status": "success", "candidates": candidates}


async def submit_draft_mapping(
    conversation_id: str,
    subject_id: str,
    exam_id: str,
    question_id: str,
    knowledge_points: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    knowledge_points: [{"point_name": str, "document_id": str, "page_numbers": [int]}]
    校验每条映射，全部通过则写入 Verified 并返回 accepted。
    """
    failed: List[Dict[str, Any]] = []
    for kp in knowledge_points:
        name = kp.get("point_name") or ""
        doc_id = kp.get("document_id") or ""
        pages = kp.get("page_numbers")
        if not isinstance(pages, list):
            pages = [pages] if pages is not None else []
        result = await verify_draft_mapping(subject_id, name, doc_id, pages)
        if result.get("status") != "accepted":
            failed.append({"point_name": name, "document_id": doc_id, "page_numbers": pages, "feedback": result.get("feedback", "")})
    if failed:
        return {
            "status": "rejected",
            "feedback": "；".join([f"「{f.get('point_name')}」{f.get('feedback', '')}" for f in failed]),
            "failed_items": failed,
        }
    # 全部通过，写入 Verified
    mapping = {
        "exam_id": exam_id,
        "question_id": question_id,
        "knowledge_points": [
            {"point_name": kp.get("point_name"), "document_id": kp.get("document_id"), "page_numbers": kp.get("page_numbers")}
            for kp in knowledge_points
        ],
    }
    TraceStorage.append_verified_mapping(conversation_id, mapping)
    return {"status": "accepted", "feedback": ""}
