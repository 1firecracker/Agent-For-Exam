"""Sub Agent：对一批题目做知识点提取与页码定位，工具循环直到提交并通过校验"""
import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

import app.config as config
from app.services.config_service import config_service
from app.services.exam_analysis.trace_storage import TraceStorage
from app.services.exam_analysis.hooks import default_hooks
from app.services.exam_analysis.tools import (
    query_knowledge_base,
    locate_knowledge_pages,
    submit_draft_mapping,
)

# Sub Agent 最大工具调用轮数（每轮可包含多次工具调用）
MAX_TOOL_ROUNDS = 50

SYSTEM_PROMPT = """你是试题分析助手。任务：为给定的题目建立「试题 — 知识点 — 讲义页码」映射。
步骤：1) 用 query_knowledge_base 检索与题目相关的内容；2) 用 locate_knowledge_pages 根据检索到的实体或关键词定位文档与页码；3) 用 submit_draft_mapping 提交候选映射。
知识点命名要求：point_name 必须使用讲义原文中出现过的短语（如小节标题、关键术语、实体名），长度建议 3～7 个字或3-7个英文单词；禁止使用单字或过度抽象概括（如仅写「定律」「方法」）。优先使用 locate_knowledge_pages 返回的 entity 名称，或 query_knowledge_base 检索结果中的原文表述。
若 submit_draft_mapping 返回 rejected，根据 feedback 修正后重试。只有提交被接受后才结束。"""

TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "query_knowledge_base",
            "description": "在讲义知识库中检索与查询词相关的内容（实体、关系、文本块）",
            "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "检索关键词或短句"}}, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "locate_knowledge_pages",
            "description": "根据实体名或关键词，在讲义中定位可能出现的文档与页码",
            "parameters": {"type": "object", "properties": {"entity_or_keyword": {"type": "string", "description": "实体名或关键词"}}, "required": ["entity_or_keyword"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_draft_mapping",
            "description": "提交当前题目的「知识点-文档-页码」候选映射，由系统校验；若未通过需根据反馈重试",
            "parameters": {
                "type": "object",
                "properties": {
                    "question_id": {"type": "string", "description": "题目ID"},
                    "knowledge_points": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "point_name": {"type": "string"},
                                "document_id": {"type": "string"},
                                "page_numbers": {"type": "array", "items": {"type": "integer"}},
                            },
                            "required": ["point_name", "document_id", "page_numbers"],
                        },
                    },
                },
                "required": ["question_id", "knowledge_points"],
            },
        },
    },
]


async def _call_llm(
    messages: List[Dict],
    tools: List[Dict],
    on_retry: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, Any]:
    """非流式调用 chat/completions，连接/超时类错误重试 3 次并退避；on_retry(attempt, max_attempts, err_msg) 用于前端展示重试中。"""
    chat_config = config_service.get_config("chat")
    model = chat_config.get("model", config.settings.chat_llm_model)
    api_key = chat_config.get("api_key", config.settings.chat_llm_binding_api_key)
    host = chat_config.get("host", config.settings.chat_llm_binding_host)
    url = f"{host}/chat/completions"
    timeout_sec = getattr(config.settings, "timeout", 300)
    if timeout_sec <= 0:
        timeout_sec = 300
    payload = {"model": model, "messages": messages, "stream": False, "temperature": 0.3}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    max_attempts = 3
    last_error = ""
    # 仅以下状态不重试（客户端错误，重试无意义）
    no_retry_statuses = (400, 401, 403, 404)

    for attempt in range(1, max_attempts + 1):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout_sec)
                ) as resp:
                    status = resp.status
                    text = await resp.text()
                if status == 200:
                    try:
                        data = json.loads(text) if text else {}
                    except json.JSONDecodeError:
                        return {"error": "LLM 返回无效 JSON"}
                    choices = data.get("choices", [])
                    if not choices:
                        return {"error": "LLM 返回无 choices"}
                    return choices[0].get("message", {})
                last_error = f"LLM {status}: {text[:200]}"
                if status in no_retry_statuses:
                    return {"error": last_error}
                logger.warning("exam_analysis LLM 非 200 attempt=%s status=%s", attempt, status)
                if attempt < max_attempts:
                    if on_retry:
                        on_retry(attempt, max_attempts, last_error)
                    await asyncio.sleep([10, 20, 40][attempt - 1])
                else:
                    return {"error": f"LLM 请求失败（已重试 {max_attempts} 次）: {last_error}"}
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "exam_analysis LLM 请求异常 attempt=%s url=%s err=%s",
                    attempt, url, last_error,
                    exc_info=True,
                )
                if attempt < max_attempts:
                    if on_retry:
                        on_retry(attempt, max_attempts, last_error)
                    await asyncio.sleep([10, 20, 40][attempt - 1])
                else:
                    return {"error": f"LLM 请求失败（已重试 {max_attempts} 次）: {last_error}"}
    return {"error": f"LLM 请求失败（已重试 {max_attempts} 次）: {last_error}"}


async def _execute_tool(
    name: str,
    arguments: Dict[str, Any],
    subject_id: str,
    conversation_id: str,
    exam_id: str,
    question_id: str,
) -> str:
    """执行单个工具，返回结果字符串。"""
    if name == "query_knowledge_base":
        out = await query_knowledge_base(subject_id, conversation_id, arguments.get("query", ""))
        return json.dumps(out, ensure_ascii=False)
    if name == "locate_knowledge_pages":
        out = locate_knowledge_pages(subject_id, conversation_id, arguments.get("entity_or_keyword", ""))
        return json.dumps(out, ensure_ascii=False)
    if name == "submit_draft_mapping":
        kps = arguments.get("knowledge_points", [])
        out = await submit_draft_mapping(conversation_id, subject_id, exam_id, arguments.get("question_id", question_id), kps)
        return json.dumps(out, ensure_ascii=False)
    return json.dumps({"status": "error", "message": f"未知工具: {name}"}, ensure_ascii=False)


async def run_sub_agent(
    subject_id: str,
    conversation_id: str,
    exam_id: str,
    question_batch: List[Dict[str, Any]],
    agent_id: str,
    label: str,
    lead_id: str,
    emit: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """
    对一批题目运行 Sub Agent，返回轨迹项（thinking_blocks + tool_calls）。
    question_batch: [{"id": str, "content": str, ...}, ...]
    lead_id: 所属 Lead Agent 的 agent_id，用于前端树形展示。
    emit: 可选，收到事件时调用，用于 SSE 实时推送。
    """
    thinking_blocks: List[Dict[str, Any]] = []
    tool_calls_log: List[Dict[str, Any]] = []
    step_index = [0]

    user_content = "请为以下题目建立「试题 — 知识点 — 讲义页码」映射。\n\n"
    for q in question_batch:
        user_content += f"题目ID: {q.get('id', '')}\n题干: {q.get('content', '')[:500]}...\n\n"
    messages: List[Dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    def _on_retry(attempt: int, max_attempts: int, err_msg: str) -> None:
        current_step = step_index[0]
        step_index[0] += 1
        default_hooks.llm.on_llm_retry(
            conversation_id=conversation_id,
            agent_id=agent_id,
            attempt=attempt,
            max_attempts=max_attempts,
            err_msg=err_msg,
            thinking_blocks=thinking_blocks,
            tool_calls_log=tool_calls_log,
            step=current_step,
        )

    for _ in range(MAX_TOOL_ROUNDS):
        msg = await _call_llm(messages, TOOLS_OPENAI, on_retry=_on_retry)
        if msg.get("error"):
            block = {"title": "错误", "content": msg["error"], "sequence": len(thinking_blocks), "step": step_index[0]}
            step_index[0] += 1
            thinking_blocks.append(block)
            if emit:
                emit({"type": "sub_thinking", "agent_id": agent_id, "block": block})
            TraceStorage.update_sub_trace(conversation_id, agent_id, thinking_blocks, tool_calls_log)
            break
        content = (msg.get("content") or "").strip()
        if content:
            block = {"title": "思考", "content": content, "sequence": len(thinking_blocks), "step": step_index[0]}
            step_index[0] += 1
            thinking_blocks.append(block)
            if emit:
                emit({"type": "sub_thinking", "agent_id": agent_id, "block": block})
            TraceStorage.update_sub_trace(conversation_id, agent_id, thinking_blocks, tool_calls_log)
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            break
        messages.append(msg)
        for tc in tool_calls:
            fid = tc.get("id") or ""
            fn = tc.get("function", {})
            fname = fn.get("name") or ""
            fargs_str = fn.get("arguments") or "{}"
            try:
                fargs = json.loads(fargs_str)
            except json.JSONDecodeError:
                fargs = {}
            qid = question_batch[0].get("id") if question_batch else ""
            default_hooks.tools.on_tool_use_start(
                conversation_id=conversation_id,
                agent_id=agent_id,
                tool_call_id=fid,
                tool_name=fname,
                arguments=fargs,
                step=step_index[0],
            )
            result_str = await _execute_tool(fname, fargs, subject_id, conversation_id, exam_id, qid)
            default_hooks.tools.on_tool_use_end(
                conversation_id=conversation_id,
                agent_id=agent_id,
                tool_call_id=fid,
                tool_name=fname,
                arguments=fargs,
                result_str=result_str,
                success=True,
                step=step_index[0],
                thinking_blocks=thinking_blocks,
                tool_calls_log=tool_calls_log,
            )
            step_index[0] += 1
            messages.append({"role": "tool", "tool_call_id": fid, "content": result_str})
    return {
        "agent_id": agent_id,
        "role": "sub",
        "label": label,
        "lead_id": lead_id,
        "status": "done",
        "thinking_blocks": thinking_blocks,
        "tool_calls": tool_calls_log,
        "updated_at": None,
    }
