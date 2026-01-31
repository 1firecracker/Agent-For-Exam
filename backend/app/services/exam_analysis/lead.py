"""Lead Agent：按试卷拉取题目、划分批次、派发 Sub 并汇总轨迹"""
import asyncio
from typing import Any, Dict, List

from app.services.exam.exam_storage import ExamStorage
from app.services.exam_analysis.event_bus import emit as event_emit
from app.services.exam_analysis.sub_agent import run_sub_agent
from app.services.exam_analysis.trace_storage import TraceStorage

# 同时最多运行的 Sub Agent 数，其余在队列等待
MAX_CONCURRENT_SUBS = 2


def _flatten_questions(questions: List[Any]) -> List[Dict[str, Any]]:
    """将题目列表（含子题）展平为 [{id, content, ...}, ...]。"""
    out: List[Dict[str, Any]] = []

    def add(q: Any) -> None:
        sub = getattr(q, "sub_questions", None) or []
        if sub:
            for s in sub:
                add(s)
        else:
            out.append({"id": getattr(q, "id", ""), "content": getattr(q, "content", ""), "index": getattr(q, "index", 0)})

    for q in questions:
        add(q)
    return out


async def run_lead(
    conversation_id: str,
    subject_id: str,
    exam_id: str,
    batch_size: int = 5,
) -> None:
    """
    拉取该试卷所有题目，按 batch_size 分批，每批跑一个 Sub Agent，并写入轨迹。
    """
    storage = ExamStorage()
    exam = storage.get_exam(exam_id)
    if not exam or not exam.questions:
        return
    questions_data = _flatten_questions(exam.questions)
    if not questions_data:
        return
    year = getattr(exam, "year", None) or ""
    label = f"年份 Lead · {year}"
    lead_trace: Dict[str, Any] = {
        "agent_id": f"lead-{exam_id}",
        "role": "lead",
        "label": label,
        "status": "running",
        "thinking_blocks": [{"title": "任务规划", "content": f"试卷 {exam_id} 共 {len(questions_data)} 题，按每 {batch_size} 题一批派发 Sub。", "sequence": 0}],
        "tool_calls": [],
        "updated_at": None,
    }
    TraceStorage.append_trace(conversation_id, lead_trace)
    event_emit(conversation_id, {"type": "lead_started", "agent_id": lead_trace["agent_id"], "label": label, "status": "running"})
    sem = asyncio.Semaphore(MAX_CONCURRENT_SUBS)
    append_lock = asyncio.Lock()  # 串行写 trace，避免并发读-改-写覆盖
    batch_starts = list(range(0, len(questions_data), batch_size))

    def _emit(ev: Dict[str, Any]) -> None:
        event_emit(conversation_id, ev)

    async def run_batch(start_i: int) -> None:
        batch = questions_data[start_i : start_i + batch_size]
        sub_id = f"sub-{exam_id}-{start_i // batch_size}"
        sub_label = f"题目 Sub · {batch[0]['id']}-{batch[-1]['id']}"
        event_emit(conversation_id, {"type": "sub_started", "agent_id": sub_id, "label": sub_label})
        async with sem:
            sub_trace = await run_sub_agent(
                subject_id=subject_id,
                conversation_id=conversation_id,
                exam_id=exam_id,
                question_batch=batch,
                agent_id=sub_id,
                label=sub_label,
                emit=_emit,
            )
        async with append_lock:
            TraceStorage.append_trace(conversation_id, sub_trace)

    await asyncio.gather(*[run_batch(i) for i in batch_starts])

    lead_done: Dict[str, Any] = {
        "agent_id": f"lead-{exam_id}-done",
        "role": "lead",
        "label": label + " · 完成",
        "status": "done",
        "thinking_blocks": [{"title": "完成", "content": f"试卷 {exam_id} 已处理完毕。", "sequence": 0}],
        "tool_calls": [],
        "updated_at": None,
    }
    TraceStorage.append_trace(conversation_id, lead_done)
    event_emit(conversation_id, {"type": "lead_done", "agent_id": lead_done["agent_id"], "label": lead_done["label"]})
