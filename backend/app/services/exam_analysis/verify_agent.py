"""Verify Agent：用 LLM 语义判断「页面内容」是否包含/支持「知识点」，替代规则子串匹配"""
import asyncio
import json
import logging
import re
from typing import Any, Dict

import aiohttp

import app.config as config
from app.services.config_service import config_service

logger = logging.getLogger(__name__)

VERIFY_PROMPT = """你是一个校验助手。给定「知识点」和「页面内容」，判断该页是否包含或支持该知识点。
允许：同义、近义、标点/空格/全半角差异、缩写、中英文混用。
拒绝：明显无关、错页、知识点与页面主题不符。
只输出一行 JSON，不要其他文字：{"status": "accepted" 或 "rejected", "feedback": "若拒绝则简短原因，否则空字符串"}"""


async def _call_llm(messages: list) -> Dict[str, Any]:
    chat_config = config_service.get_config("chat")
    model = chat_config.get("model", config.settings.chat_llm_model)
    api_key = chat_config.get("api_key", config.settings.chat_llm_binding_api_key)
    host = chat_config.get("host", config.settings.chat_llm_binding_host)
    url = f"{host}/chat/completions"
    timeout_sec = min(getattr(config.settings, "timeout", 300), 60)
    if timeout_sec <= 0:
        timeout_sec = 60
    payload = {"model": model, "messages": messages, "stream": False, "temperature": 0.1}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    max_attempts = 2
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout_sec)
                ) as resp:
                    if resp.status != 200:
                        last_error = f"LLM {resp.status}"
                        await asyncio.sleep([5, 10][attempt - 1])
                        continue
                    text = await resp.text()
                    data = json.loads(text) if text else {}
                    choices = data.get("choices", [])
                    if not choices:
                        last_error = "LLM 无 choices"
                        await asyncio.sleep([5, 10][attempt - 1])
                        continue
                    content = (choices[0].get("message", {}).get("content") or "").strip()
                    m = re.search(r'\{[^{}]*"status"\s*:\s*"(accepted|rejected)"[^{}]*"feedback"\s*:\s*"([^"]*)"[^{}]*\}', content)
                    if m:
                        s, fb = m.group(1).lower(), m.group(2)
                        if s == "accepted":
                            return {"status": "accepted", "feedback": fb}
                        return {"status": "rejected", "feedback": fb or "未通过校验"}
                    for line in content.splitlines():
                        line = line.strip().strip("`")
                        if line.startswith("{"):
                            obj = json.loads(line)
                            s = (obj.get("status") or "").lower()
                            if s == "accepted":
                                return {"status": "accepted", "feedback": obj.get("feedback", "") or ""}
                            return {"status": "rejected", "feedback": obj.get("feedback", "") or "未通过校验"}
                    last_error = "LLM 未返回有效 JSON"
            except (aiohttp.ClientError, OSError, TimeoutError, asyncio.TimeoutError, json.JSONDecodeError) as e:
                last_error = str(e)
                logger.warning("verify_agent LLM 失败 attempt=%s err=%s", attempt, last_error)
            if attempt < max_attempts:
                await asyncio.sleep([5, 10][attempt - 1])
    return {"status": "rejected", "feedback": f"校验服务暂时不可用: {last_error}"}


async def verify_one(knowledge_point: str, page_content: str) -> Dict[str, Any]:
    """
    用 LLM 判断页面内容是否包含/支持该知识点。
    返回 {"status": "accepted"|"rejected", "feedback": str}。
    """
    k = (knowledge_point or "").strip()
    if not k:
        return {"status": "rejected", "feedback": "知识点名称为空"}
    content_preview = (page_content or "")[:8000]
    user = f"知识点：{k}\n\n页面内容：\n{content_preview}"
    messages = [{"role": "system", "content": VERIFY_PROMPT}, {"role": "user", "content": user}]
    return await _call_llm(messages)
