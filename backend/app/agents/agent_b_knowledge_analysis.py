# -*- coding: utf-8 -*-
# ===========================================================
# 文件：backend/app/agents/agent_b_knowledge_analysis.py
# 功能：Agent B - 题目关联知识检索（向量库 + 知识图谱）
# ===========================================================

import asyncio
import json
import os
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from lightrag import QueryParam

from app.agents.shared_state import shared_state
from app.agents.database.question_bank_storage import BASE_DATA_DIR, load_question_bank
from app.agents.models.quiz_models import QuestionBank, SubQuestion
from app.services.graph_service import GraphService
from app.services.lightrag_service import LightRAGService

load_dotenv()


def _normalize_text(value: str) -> str:
    return str(value or "").strip()


def _normalize_key(value: str) -> str:
    return _normalize_text(value).lower()


def _ensure_list(items) -> List[str]:
    normalized = []
    if isinstance(items, list):
        for item in items:
            text = _normalize_text(item)
            if text:
                normalized.append(text)
    return normalized


def _flatten_questions(qb: QuestionBank) -> Dict[str, Dict[str, List[str]]]:
    flattened: Dict[str, Dict[str, List[str]]] = {}

    def collect_sub_questions(base_key: str, subs: List[SubQuestion]):
        if not subs:
            return
        for index, sub in enumerate(subs, 1):
            label = _normalize_text(sub.label or "")
            suffix = label.replace(" ", "") if label else f"sub_{index}"
            key = f"{base_key}-{suffix}"
            flattened[key] = {
                "stem": _normalize_text(sub.stem or ""),
                "knowledge_points": _ensure_list(sub.knowledge_points or []),
            }
            if sub.sub_questions:
                collect_sub_questions(key, sub.sub_questions)

    for idx, question in enumerate(qb.questions, 1):
        qid = _normalize_text(getattr(question, "id", "") or f"Q{idx:03d}")
        flattened[qid] = {
            "stem": _normalize_text(question.stem or ""),
            "knowledge_points": _ensure_list(question.knowledge_points or []),
        }
        if question.sub_questions:
            collect_sub_questions(qid, question.sub_questions)

    return flattened


def _build_entity_lookup(entities: List[Dict]) -> Tuple[Dict[str, Dict], List[Dict]]:
    lookup: Dict[str, Dict] = {}
    for entity in entities:
        name = entity.get("name") or entity.get("entity_id") or ""
        normalized = _normalize_key(name)
        if normalized and normalized not in lookup:
            lookup[normalized] = entity
    return lookup, entities


def _collect_relations_map(relations: List[Dict]) -> Dict[str, List[Dict]]:
    adjacency: Dict[str, List[Dict]] = {}
    for relation in relations:
        source = relation.get("source") or relation.get("src_id")
        target = relation.get("target") or relation.get("tgt_id")
        for node in (source, target):
            node_id = _normalize_text(node or "")
            if node_id:
                adjacency.setdefault(node_id, []).append(
                    {
                        "source": source,
                        "target": target,
                        "type": relation.get("type") or relation.get("relation_type") or "",
                        "description": relation.get("description", ""),
                    }
                )
    return adjacency


def _find_entity(
    knowledge_point: str,
    lookup: Dict[str, Dict],
    all_entities: List[Dict],
) -> Dict | None:
    normalized = _normalize_key(knowledge_point)
    if normalized in lookup:
        return lookup[normalized]
    for entity in all_entities:
        candidate = _normalize_key(entity.get("name") or entity.get("entity_id") or "")
        if candidate and (normalized in candidate or candidate in normalized):
            return entity
    return None


def _match_graph_data(
    knowledge_points: List[str],
    lookup: Dict[str, Dict],
    all_entities: List[Dict],
    relation_map: Dict[str, List[Dict]],
    max_relations: int = 5,
) -> List[Dict]:
    matches = []
    visited = set()
    for kp in knowledge_points:
        entity = _find_entity(kp, lookup, all_entities)
        if not entity:
            continue
        entity_id = entity.get("entity_id") or entity.get("name")
        if not entity_id or entity_id in visited:
            continue
        visited.add(entity_id)
        normalized_id = _normalize_text(entity_id)
        relations = relation_map.get(normalized_id, [])[:max_relations]
        matches.append(
            {
                "knowledge_point": kp,
                "entity": entity.get("name") or entity_id,
                "description": entity.get("description", ""),
                "relations": relations,
                "source_documents": entity.get("source_documents", []),
            }
        )
    return matches


async def _query_vector_context(lightrag, stem: str, top_k: int) -> List[Dict]:
    if not stem:
        return []
    param = QueryParam(mode="local")
    param.top_k = top_k
    param.chunk_top_k = top_k
    result = await lightrag.aquery_data(stem, param)
    if not isinstance(result, dict):
        return []
    payload = result.get("data") or {}
    chunks = payload.get("chunks") or []
    matches = []
    for chunk in chunks[:top_k]:
        matches.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "file_path": chunk.get("file_path"),
                "content": chunk.get("content", ""),
                "reference_id": chunk.get("reference_id"),
            }
        )
    return matches


def _save_related_knowledge(conversation_id: str, related_payload: Dict[str, Dict]) -> str:
    target_dir = os.path.join(BASE_DATA_DIR, conversation_id)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, "related_knowledge.json")
    with open(file_path, "w", encoding="utf-8") as fp:
        json.dump(related_payload, fp, ensure_ascii=False, indent=2)
    return file_path


async def _collect_related_knowledge(
    conversation_id: str,
    flattened_questions: Dict[str, Dict[str, List[str]]],
    vector_top_k: int = 5,
    max_concurrent: int = 3,
) -> Dict[str, Dict]:
    graph_service = GraphService()
    lightrag_service = LightRAGService()
    has_docs = graph_service.check_has_documents_fast(conversation_id)

    lightrag = None
    entities: List[Dict] = []
    relations: List[Dict] = []
    if has_docs:
        lightrag = await lightrag_service.get_lightrag_for_conversation(conversation_id)
        entities = await graph_service.get_all_entities(conversation_id)
        relations = await graph_service.get_all_relations(conversation_id)

    entity_lookup, entity_list = _build_entity_lookup(entities)
    relation_map = _collect_relations_map(relations)

    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = []

    async def process_item(key: str, payload: Dict[str, List[str]]):
        async with semaphore:
            vector_matches: List[Dict] = []
            if lightrag is not None:
                vector_matches = await _query_vector_context(
                    lightrag, payload.get("stem", ""), vector_top_k
                )
            graph_matches = _match_graph_data(
                payload.get("knowledge_points", []),
                entity_lookup,
                entity_list,
                relation_map,
            )
            return key, {
                "vector_matches": vector_matches,
                "graph_matches": graph_matches,
            }
    i = 0
    for key, payload in flattened_questions.items():
        print(f"第{i}个子题目正在处理")
        i += 1
        tasks.append(process_item(key, payload))

    gathered = await asyncio.gather(*tasks)
    return {key: value for key, value in gathered}


def run_agent_b(conversation_id: str):
    """
    Agent B：
    从题库抽取最小粒度题目 → 查询向量知识库 / 知识图谱 → 保存 related_knowledge.json
    """
    print(f"🧩 [Agent B] 开始关联知识检索，会话ID: {conversation_id}")

    qb: QuestionBank = shared_state.question_bank
    if qb is None or not qb.questions:
        print("⚠️ shared_state.question_bank 为空，尝试从磁盘加载。")
        qb = load_question_bank(conversation_id)

    if qb is None or not qb.questions:
        print("❌ 无可处理题库，Agent B 终止。")
        return None

    flattened = _flatten_questions(qb)
    if not flattened:
        print("⚠️ 题库无法展开子题，Agent B 终止。")
        return None

    related_map = asyncio.run(
        _collect_related_knowledge(conversation_id, flattened)
    )
    file_path = _save_related_knowledge(conversation_id, related_map)

    shared_state.related_knowledge_path = file_path
    print(f"✅ Agent B 完成，关联知识已保存：{file_path}")
    print(f"📌 记录数量：{len(related_map)}")
    return related_map
