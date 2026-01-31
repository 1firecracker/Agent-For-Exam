"""Sub Agent：对一批题目做知识点提取与页码定位，工具循环直到提交并通过校验"""
import asyncio
import json
from typing import Any, Callable, Dict, List, Optional

import aiohttp

import app.config as config
from app.services.config_service import config_service
from app.services.exam_analysis.tools import (
    query_knowledge_base,
    locate_knowledge_pages,
    submit_draft_mapping,
)

# Sub Agent 最大工具调用轮数（每轮可包含多次工具调用）
MAX_TOOL_ROUNDS = 25

SYSTEM_PROMPT = """你是试题分析助手。任务：为给定的题目建立「试题 — 知识点 — 讲义页码」映射。
步骤：1) 用 query_knowledge_base 检索与题目相关的知识点；2) 用 locate_knowledge_pages 定位知识点所在文档与页码；3) 用 submit_draft_mapping 提交候选映射。
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


async def _call_llm(messages: List[Dict], tools: List[Dict]) -> Dict[str, Any]:
    """非流式调用 chat/completions，返回 choices[0].message。"""
    chat_config = config_service.get_config("chat")
    binding = chat_config.get("binding", config.settings.chat_llm_binding)
    model = chat_config.get("model", config.settings.chat_llm_model)
    api_key = chat_config.get("api_key", config.settings.chat_llm_binding_api_key)
    host = chat_config.get("host", config.settings.chat_llm_binding_host)
    url = f"{host}/chat/completions"
    payload = {"model": model, "messages": messages, "stream": False, "temperature": 0.3}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status != 200:
                text = await resp.text()
                return {"error": f"LLM {resp.status}: {text}"}
            data = await resp.json()
    choices = data.get("choices", [])
    if not choices:
        return {"error": "LLM 返回无 choices"}
    return choices[0].get("message", {})


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
    emit: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """
    对一批题目运行 Sub Agent，返回轨迹项（thinking_blocks + tool_calls）。
    question_batch: [{"id": str, "content": str, ...}, ...]
    emit: 可选，收到事件时调用，用于 SSE 实时推送。
    """
    thinking_blocks: List[Dict[str, str]] = []
    tool_calls_log: List[Dict[str, Any]] = []
    user_content = "请为以下题目建立「试题 — 知识点 — 讲义页码」映射。\n\n"
    for q in question_batch:
        user_content += f"题目ID: {q.get('id', '')}\n题干: {q.get('content', '')[:500]}...\n\n"
    messages: List[Dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    for _ in range(MAX_TOOL_ROUNDS):
        msg = await _call_llm(messages, TOOLS_OPENAI)
        if msg.get("error"):
            block = {"title": "错误", "content": msg["error"], "sequence": len(thinking_blocks)}
            thinking_blocks.append(block)
            if emit:
                emit({"type": "sub_thinking", "agent_id": agent_id, "block": block})
            break
        content = (msg.get("content") or "").strip()
        if content:
            block = {"title": "思考", "content": content, "sequence": len(thinking_blocks)}
            thinking_blocks.append(block)
            if emit:
                emit({"type": "sub_thinking", "agent_id": agent_id, "block": block})
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
            result_str = await _execute_tool(fname, fargs, subject_id, conversation_id, exam_id, qid)
            call_entry = {"id": fid, "name": fname, "arguments": fargs, "result": result_str, "status": "success"}
            tool_calls_log.append(call_entry)
            if emit:
                emit({"type": "sub_tool_call", "agent_id": agent_id, "call": call_entry})
            messages.append({"role": "tool", "tool_call_id": fid, "content": result_str})
    if emit:
        emit({"type": "sub_done", "agent_id": agent_id})
    return {
        "agent_id": agent_id,
        "role": "sub",
        "label": label,
        "status": "done",
        "thinking_blocks": thinking_blocks,
        "tool_calls": tool_calls_log,
        "updated_at": None,
    }
