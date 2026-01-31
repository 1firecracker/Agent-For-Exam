"""SSE 事件总线：按 conversation_id 注册队列，分析任务向队列推送事件"""
import asyncio
from typing import Any, Dict, List

_subscribers: Dict[str, List[asyncio.Queue]] = {}
_lock = asyncio.Lock()

STREAM_END = {"type": "stream_end"}


async def subscribe(conversation_id: str) -> asyncio.Queue:
    """为某对话注册一个订阅队列，返回该队列（消费者从队列取事件）"""
    async with _lock:
        if conversation_id not in _subscribers:
            _subscribers[conversation_id] = []
        q: asyncio.Queue = asyncio.Queue()
        _subscribers[conversation_id].append(q)
        return q


async def unsubscribe(conversation_id: str, queue: asyncio.Queue) -> None:
    """取消订阅"""
    async with _lock:
        lst = _subscribers.get(conversation_id, [])
        if queue in lst:
            lst.remove(queue)
        if not lst:
            _subscribers.pop(conversation_id, None)


async def wait_for_subscriber(conversation_id: str, timeout: float = 30.0) -> bool:
    """在发出首条事件前等待至少一名订阅者，避免事件丢失。返回是否已有订阅者。"""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        async with _lock:
            n = len(_subscribers.get(conversation_id, []))
        if n >= 1:
            return True
        await asyncio.sleep(0.1)
    return False


def emit(conversation_id: str, event: Dict[str, Any]) -> None:
    """向该对话的所有订阅者推送事件（非阻塞 put_nowait）"""
    for q in _subscribers.get(conversation_id, []):
        q.put_nowait(event)
