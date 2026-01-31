"""试题分析轨迹与 Verified Mapping 存储"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import app.config as config


def _base_dir() -> Path:
    return Path(config.settings.conversations_metadata_dir) / "exam_analysis"


def _conv_dir(conversation_id: str) -> Path:
    d = _base_dir() / conversation_id
    d.mkdir(parents=True, exist_ok=True)
    return d


class TraceStorage:
    """轨迹与 Verified 存储"""

    @staticmethod
    def append_trace(conversation_id: str, item: Dict[str, Any]) -> None:
        """追加一条 Agent 轨迹（Lead/Sub）"""
        d = _conv_dir(conversation_id)
        path = d / "trace.json"
        items: List[Dict] = []
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data.get("items", [])
        items.append(item)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"items": items}, f, ensure_ascii=False, indent=2)

    @staticmethod
    def get_trace(conversation_id: str) -> Dict[str, Any]:
        """读取完整轨迹"""
        path = _conv_dir(conversation_id) / "trace.json"
        if not path.exists():
            return {"items": []}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

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
