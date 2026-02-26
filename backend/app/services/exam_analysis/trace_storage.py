"""试题分析轨迹与 Verified Mapping 存储"""
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import app.config as config

_file_locks: Dict[str, threading.Lock] = {}
_lock_mu = threading.Lock()


def _base_dir() -> Path:
    return Path(config.settings.conversations_metadata_dir) / "exam_analysis"


def _conv_dir(conversation_id: str) -> Path:
    d = _base_dir() / conversation_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_lock(cid: str) -> threading.Lock:
    with _lock_mu:
        if cid not in _file_locks:
            _file_locks[cid] = threading.Lock()
        return _file_locks[cid]


class TraceStorage:
    """轨迹与 Verified 存储。append 使用原子写入；update_sub_trace 就地更新 Sub 进度，刷新后可加载未完成内容。"""

    @staticmethod
    def append_trace(conversation_id: str, item: Dict[str, Any]) -> None:
        """追加一条 Agent 轨迹（Lead/Sub），原子写入避免并发读时拿到不完整 JSON"""
        lock = _get_lock(conversation_id)
        with lock:
            d = _conv_dir(conversation_id)
            path = d / "trace.json"
            tmp_path = d / "trace.json.tmp"
            items: List[Dict] = []
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items = data.get("items", [])
            items.append(item)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump({"items": items}, f, ensure_ascii=False, indent=2)
            tmp_path.replace(path)

    @staticmethod
    def update_sub_trace(
        conversation_id: str,
        agent_id: str,
        thinking_blocks: List[Dict[str, Any]],
        tool_calls: List[Dict[str, Any]],
        status: Optional[str] = None,
    ) -> None:
        """就地更新该 Sub 的 thinking_blocks / tool_calls（及可选 status），刷新后可加载未完成内容"""
        lock = _get_lock(conversation_id)
        with lock:
            d = _conv_dir(conversation_id)
            path = d / "trace.json"
            tmp_path = d / "trace.json.tmp"
            if not path.exists():
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data.get("items", [])
            for i, it in enumerate(items):
                if it.get("role") == "sub" and it.get("agent_id") == agent_id:
                    items[i] = {**it, "thinking_blocks": thinking_blocks, "tool_calls": tool_calls}
                    if status is not None:
                        items[i]["status"] = status
                    break
            else:
                return
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump({"items": items}, f, ensure_ascii=False, indent=2)
            tmp_path.replace(path)

    @staticmethod
    def get_trace(conversation_id: str) -> Dict[str, Any]:
        """读取完整轨迹"""
        lock = _get_lock(conversation_id)
        with lock:
            path = _conv_dir(conversation_id) / "trace.json"
            if not path.exists():
                return {"items": []}
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {"items": data.get("items", [])}

    @staticmethod
    def append_verified_mapping(conversation_id: str, mapping: Dict[str, Any]) -> None:
        """追加一条 Verified Mapping"""
        d = _conv_dir(conversation_id)
        path = d / "verified_mappings.json"
        items: List[Dict] = []
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data.get("mappings", [])
        items.append(mapping)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"mappings": items}, f, ensure_ascii=False, indent=2)

    @staticmethod
    def get_verified_mappings(conversation_id: str) -> List[Dict[str, Any]]:
        """读取所有 Verified Mapping"""
        path = _conv_dir(conversation_id) / "verified_mappings.json"
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("mappings", [])

    @staticmethod
    def save_report(conversation_id: str, report: Dict[str, Any]) -> None:
        """保存报告 JSON（第三阶段）"""
        d = _conv_dir(conversation_id)
        path = d / "report.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    @staticmethod
    def get_report(conversation_id: str) -> Optional[Dict[str, Any]]:
        """读取报告，不存在返回 None"""
        path = _conv_dir(conversation_id) / "report.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def delete_report(conversation_id: str) -> None:
        """删除报告缓存（重新跑分析时失效）"""
        path = _conv_dir(conversation_id) / "report.json"
        if path.exists():
            path.unlink()
