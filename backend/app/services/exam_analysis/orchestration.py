"""Orchestrator：扫描对话所选试卷，按试卷并行/串行跑 Lead，写入轨迹"""
import asyncio
from typing import List

from app.services.conversation_service import ConversationService
from app.services.graph_service import GraphService
from app.services.exam_analysis.event_bus import emit as event_emit
from app.services.exam_analysis.lead import run_lead
from app.services.exam_analysis.trace_storage import TraceStorage


async def run_analysis(conversation_id: str) -> None:
    """
    读取对话的 subject_id、selected_exam_ids；
    可选：为该 subject 构建实体页码映射；
    对每个 exam_id 串行执行 run_lead；
    轨迹由 Lead/Sub 内部 append_trace 写入。
    """
    from app.services.exam_analysis.event_bus import wait_for_subscriber
    conv_svc = ConversationService()
    conversation = conv_svc.get_conversation(conversation_id)
    if not conversation:
        return
    subject_id = conversation.get("subject_id")
    selected_exam_ids: List[str] = conversation.get("selected_exam_ids") or []
    if not subject_id or not selected_exam_ids:
        return
    await wait_for_subscriber(conversation_id)
    event_emit(conversation_id, {"type": "analysis_started", "conversation_id": conversation_id})
    graph = GraphService()
    await graph.build_entity_page_mapping(subject_id)
    for exam_id in selected_exam_ids:
        await run_lead(conversation_id=conversation_id, subject_id=subject_id, exam_id=exam_id, batch_size=5)
    event_emit(conversation_id, {"type": "analysis_done"})
    event_emit(conversation_id, {"type": "stream_end"})
