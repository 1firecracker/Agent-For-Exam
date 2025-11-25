# -*- coding: utf-8 -*-
# ===========================================================
# 文件：backend/app/agents/agent_b_knowledge_analysis.py
# 功能：Agent B - 按整题汇总知识点，查询知识图谱获取相关实体与周边知识
# ===========================================================

import asyncio
import json
import os
from typing import Dict, List, Set, Tuple

from app.agents.shared_state import shared_state
from app.agents.database.question_bank_storage import BASE_DATA_DIR, load_question_bank
from app.agents.models.quiz_models import QuestionBank, Question, SubQuestion
from app.services.graph_service import GraphService


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


def _collect_all_kps(question: Question) -> List[str]:
    """递归收集题目及所有子题的知识点，去重后返回"""
    kps: Set[str] = set()

    # 添加主题知识点
    for kp in _ensure_list(question.knowledge_points or []):
        kps.add(kp)

    # 递归收集子题知识点
    def collect_from_subs(subs: List[SubQuestion]):
        if not subs:
            return
        for sub in subs:
            for kp in _ensure_list(sub.knowledge_points or []):
                kps.add(kp)
            if sub.sub_questions:
                collect_from_subs(sub.sub_questions)

    if question.sub_questions:
        collect_from_subs(question.sub_questions)

    return list(kps) if kps else ["通用知识"]


def _summarize_questions(qb: QuestionBank) -> Dict[str, Dict]:
    """按整题汇总，返回 {question_id: {stem, knowledge_points}}"""
    summarized: Dict[str, Dict] = {}

    for idx, question in enumerate(qb.questions, 1):
        qid = _normalize_text(getattr(question, "id", "") or f"Q{idx:03d}")
        summarized[qid] = {
            "stem": _normalize_text(question.stem or ""),
            "knowledge_points": _collect_all_kps(question),
        }

    return summarized


def _build_entity_lookup(entities: List[Dict]) -> Tuple[Dict[str, Dict], List[Dict]]:
    """构建实体名称索引"""
    lookup: Dict[str, Dict] = {}
    for entity in entities:
        name = entity.get("name") or entity.get("entity_id") or ""
        normalized = _normalize_key(name)
        if normalized and normalized not in lookup:
            lookup[normalized] = entity
    return lookup, entities


def _collect_relations_map(relations: List[Dict]) -> Dict[str, List[Dict]]:
    """构建实体到关系的映射"""
    adjacency: Dict[str, List[Dict]] = {}
    for relation in relations:
        source = relation.get("source") or relation.get("src_id") or ""
        target = relation.get("target") or relation.get("tgt_id") or ""
        for node in (source, target):
            node_key = _normalize_key(node)
            if node_key:
                adjacency.setdefault(node_key, []).append({
                    "source": source,
                    "target": target,
                    "type": relation.get("type") or relation.get("relation_type") or "",
                    "description": relation.get("description", ""),
                })
    return adjacency


def _find_entity(
    knowledge_point: str,
    lookup: Dict[str, Dict],
    all_entities: List[Dict],
) -> Dict | None:
    """精确匹配 + 模糊匹配查找实体"""
    normalized = _normalize_key(knowledge_point)
    if normalized in lookup:
        return lookup[normalized]
    # 模糊匹配：包含关系
    for entity in all_entities:
        candidate = _normalize_key(entity.get("name") or entity.get("entity_id") or "")
        if candidate and (normalized in candidate or candidate in normalized):
            return entity
    return None


def _get_neighbor_entities(
    entity_name: str,
    relation_map: Dict[str, List[Dict]],
    entity_lookup: Dict[str, Dict],
    max_neighbors: int = 5,
) -> List[Dict]:
    """获取实体的邻居实体信息"""
    neighbors = []
    visited = set()
    entity_key = _normalize_key(entity_name)
    relations = relation_map.get(entity_key, [])

    for rel in relations[:max_neighbors * 2]:  # 多取一些再去重
        # 找到关系的另一端
        source = rel.get("source", "")
        target = rel.get("target", "")
        other = target if _normalize_key(source) == entity_key else source

        other_key = _normalize_key(other)
        if other_key in visited or not other_key:
            continue
        visited.add(other_key)

        # 查找邻居实体的详细信息
        neighbor_entity = entity_lookup.get(other_key, {})
        neighbors.append({
            "entity": other,
            "description": neighbor_entity.get("description", ""),
            "relation_type": rel.get("type", ""),
            "relation_desc": rel.get("description", ""),
        })

        if len(neighbors) >= max_neighbors:
            break

    return neighbors


def _match_graph_data(
    knowledge_points: List[str],
    lookup: Dict[str, Dict],
    all_entities: List[Dict],
    relation_map: Dict[str, List[Dict]],
    max_relations: int = 5,
    max_neighbors: int = 5,
) -> List[Dict]:
    """根据知识点匹配图谱实体、关系及周边知识"""
    matches = []
    visited = set()

    for kp in knowledge_points:
        entity = _find_entity(kp, lookup, all_entities)
        if not entity:
            continue

        entity_name = entity.get("name") or entity.get("entity_id") or ""
        entity_key = _normalize_key(entity_name)
        if not entity_key or entity_key in visited:
            continue
        visited.add(entity_key)

        # 获取关系
        relations = relation_map.get(entity_key, [])[:max_relations]

        # 获取邻居实体（周边知识）
        neighbors = _get_neighbor_entities(
            entity_name, relation_map, lookup, max_neighbors
        )

        matches.append({
            "knowledge_point": kp,
            "entity": entity_name,
            "description": entity.get("description", ""),
            "relations": relations,
            "neighbors": neighbors,
            "source_documents": entity.get("source_documents", []),
        })

    return matches


def _save_related_knowledge(conversation_id: str, related_payload: Dict[str, Dict]) -> str:
    """保存关联知识到 JSON 文件"""
    target_dir = os.path.join(BASE_DATA_DIR, conversation_id)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, "related_knowledge.json")
    with open(file_path, "w", encoding="utf-8") as fp:
        json.dump(related_payload, fp, ensure_ascii=False, indent=2)
    return file_path


async def _collect_related_knowledge(
    conversation_id: str,
    summarized_questions: Dict[str, Dict],
) -> Dict[str, Dict]:
    """收集每道题的知识图谱相关信息"""
    graph_service = GraphService()
    has_docs = graph_service.check_has_documents_fast(conversation_id)

    entities: List[Dict] = []
    relations: List[Dict] = []
    if has_docs:
        entities = await graph_service.get_all_entities(conversation_id)
        relations = await graph_service.get_all_relations(conversation_id)
        print(f"📊 知识图谱加载完成：{len(entities)} 个实体，{len(relations)} 条关系")
    else:
        print("⚠️ 未找到知识图谱文档，将返回空匹配结果")

    entity_lookup, entity_list = _build_entity_lookup(entities)
    relation_map = _collect_relations_map(relations)

    result = {}
    for qid, payload in summarized_questions.items():
        kps = payload.get("knowledge_points", [])
        graph_matches = _match_graph_data(
            kps, entity_lookup, entity_list, relation_map
        )
        result[qid] = {
            "knowledge_points": kps,
            "graph_matches": graph_matches,
        }
        print(f"  ✓ 题目 {qid}: {len(kps)} 个知识点 → {len(graph_matches)} 个匹配")

    return result


def run_agent_b(conversation_id: str):
    """
    Agent B：
    按整题汇总知识点 → 查询知识图谱 → 保存 related_knowledge.json
    """
    print(f"🧩 [Agent B] 开始知识图谱检索，会话ID: {conversation_id}")

    qb: QuestionBank = shared_state.question_bank
    if qb is None or not qb.questions:
        print("⚠️ shared_state.question_bank 为空，尝试从磁盘加载。")
        qb = load_question_bank(conversation_id)

    if qb is None or not qb.questions:
        print("❌ 无可处理题库，Agent B 终止。")
        return None

    summarized = _summarize_questions(qb)
    print(f"📋 共 {len(summarized)} 道题目待处理")

    related_map = asyncio.run(
        _collect_related_knowledge(conversation_id, summarized)
    )
    file_path = _save_related_knowledge(conversation_id, related_map)

    shared_state.related_knowledge_path = file_path
    print(f"✅ Agent B 完成，关联知识已保存：{file_path}")
    return related_map
