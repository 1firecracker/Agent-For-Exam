"""第三阶段：报告聚合与生成（考频、分布、对照表、概述、建议）"""
from collections import defaultdict
from typing import Any, Dict, List, Optional

from app.services.conversation_service import ConversationService
from app.services.document_service import DocumentService
from app.services.exam.exam_storage import ExamStorage
from app.services.exam_analysis.trace_storage import TraceStorage


def _year_str(info: Optional[dict]) -> str:
    if not info:
        return ""
    y = info.get("year")
    return str(y) if y is not None else ""


def _build_question_order(selected_exam_ids: List[str], exam_storage: ExamStorage) -> Dict[str, int]:
    """按 selected_exam_ids 与试卷内题目顺序构造 question_id -> 排序键。"""
    order: Dict[str, int] = {}
    idx = 0
    for eid in selected_exam_ids:
        exam = exam_storage.get_exam(eid)
        if not exam or not exam.questions:
            continue
        for q in exam.questions:
            sub = getattr(q, "sub_questions", None) or []
            if sub:
                for s in sub:
                    order[getattr(s, "id", "")] = idx
                    idx += 1
            else:
                order[getattr(q, "id", "")] = idx
                idx += 1
    return order


def build_report(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    根据 verified_mappings 与对话/试卷/文档元数据聚合报告。
    无 mapping 时返回 None（调用方返回 404）。
    """
    mappings = TraceStorage.get_verified_mappings(conversation_id)
    if not mappings:
        return None

    conv_svc = ConversationService()
    conversation = conv_svc.get_conversation(conversation_id)
    if not conversation:
        return None
    subject_id = conversation.get("subject_id") or ""
    selected_exam_ids: List[str] = conversation.get("selected_exam_ids") or []

    exam_storage = ExamStorage()
    doc_svc = DocumentService()

    exam_id_to_year: Dict[str, str] = {}
    for eid in selected_exam_ids:
        info = exam_storage.get_exam_status(eid)
        exam_id_to_year[eid] = _year_str(info)
    years = list(filter(None, exam_id_to_year.values()))
    unique_years = list(dict.fromkeys(years))
    has_trend = len(unique_years) > 1

    # 题目分值：exam_id -> question_id -> score
    qid_to_score: Dict[str, float] = {}
    for eid in selected_exam_ids:
        exam = exam_storage.get_exam(eid)
        if exam and exam.questions:
            for q in exam.questions:
                if q.score is not None:
                    qid_to_score[q.id] = float(q.score)
                elif q.id not in qid_to_score:
                    qid_to_score[q.id] = 0.0

    question_order = _build_question_order(selected_exam_ids, exam_storage)

    # 展平：每个 (mapping, kp) 一条；按年份分组对照表
    mapping_table_by_year: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    point_count_total: Dict[str, int] = defaultdict(int)
    point_count_by_year: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    point_questions: Dict[str, set] = defaultdict(set)
    point_questions_by_year: Dict[str, Dict[str, set]] = defaultdict(lambda: defaultdict(set))
    point_score_weight: Dict[str, float] = defaultdict(float)

    for m in mappings:
        exam_id = m.get("exam_id") or ""
        question_id = m.get("question_id") or ""
        year = exam_id_to_year.get(exam_id, "")
        q_score = qid_to_score.get(question_id, 0.0)

        for kp in m.get("knowledge_points") or []:
            point_name = kp.get("point_name") or ""
            document_id = kp.get("document_id") or ""
            page_numbers = kp.get("page_numbers")
            if not isinstance(page_numbers, list):
                page_numbers = [page_numbers] if page_numbers is not None else []
            doc = doc_svc.get_document_for_subject(subject_id, document_id) if subject_id else None
            document_title = (doc.get("filename") or "未知文档") if doc else "未知文档"

            row = {
                "question_id": question_id,
                "point_name": point_name,
                "document_id": document_id,
                "page_numbers": page_numbers,
                "document_title": document_title,
            }
            mapping_table_by_year[year].append(row)

            point_count_total[point_name] += 1
            point_count_by_year[year][point_name] += 1
            point_questions[point_name].add(question_id)
            point_questions_by_year[year][point_name].add(question_id)
            point_score_weight[point_name] += q_score

    for year in mapping_table_by_year:
        mapping_table_by_year[year].sort(
            key=lambda row: (question_order.get(row["question_id"], 9999), row.get("point_name", ""))
        )

    # 考题在各文档的分布（题号+文档+页码，同题同文档合并页码，不展示知识点）
    doc_dist_total: Dict[tuple, Dict[str, Any]] = {}  # (question_id, document_id) -> { document_title, pages set }
    doc_dist_by_year: Dict[str, Dict[tuple, Dict[str, Any]]] = defaultdict(lambda: {})
    for m in mappings:
        exam_id = m.get("exam_id") or ""
        question_id = m.get("question_id") or ""
        year = exam_id_to_year.get(exam_id, "")
        for kp in m.get("knowledge_points") or []:
            document_id = kp.get("document_id") or ""
            page_numbers = kp.get("page_numbers")
            if not isinstance(page_numbers, list):
                page_numbers = [page_numbers] if page_numbers is not None else []
            doc = doc_svc.get_document_for_subject(subject_id, document_id) if subject_id else None
            document_title = (doc.get("filename") or "未知文档") if doc else "未知文档"
            key = (question_id, document_id)
            pages_set = set(p for p in page_numbers if p is not None)
            if key not in doc_dist_total:
                doc_dist_total[key] = {"document_title": document_title, "pages": set(pages_set)}
            else:
                doc_dist_total[key]["pages"] |= pages_set
            if year:
                if key not in doc_dist_by_year[year]:
                    doc_dist_by_year[year][key] = {"document_title": document_title, "pages": set(pages_set)}
                else:
                    doc_dist_by_year[year][key]["pages"] |= pages_set
    doc_distribution_total = []
    for (qid, doc_id), data in doc_dist_total.items():
        doc_distribution_total.append({
            "question_id": qid,
            "document_id": doc_id,
            "document_title": data["document_title"],
            "page_numbers": sorted(data["pages"]),
        })
    doc_distribution_total.sort(
        key=lambda row: (question_order.get(row["question_id"], 9999), row.get("document_title", ""))
    )
    doc_distribution_by_year = {}
    for y in unique_years:
        rows = []
        for (qid, doc_id), data in doc_dist_by_year[y].items():
            rows.append({
                "question_id": qid,
                "document_id": doc_id,
                "document_title": data["document_title"],
                "page_numbers": sorted(data["pages"]),
            })
        rows.sort(key=lambda row: (question_order.get(row["question_id"], 9999), row.get("document_title", "")))
        doc_distribution_by_year[y] = rows

    total_occurrences = sum(point_count_total.values())
    frequency_by_point = [
        {"point_name": k, "count": v, "ratio": round(v / total_occurrences, 4) if total_occurrences else 0}
        for k, v in sorted(point_count_total.items(), key=lambda x: -x[1])
    ]
    frequency_by_year_and_point: Dict[str, List[Dict[str, Any]]] = {}
    for y in unique_years:
        t = sum(point_count_by_year[y].values())
        frequency_by_year_and_point[y] = [
            {"point_name": k, "count": v, "ratio": round(v / t, 4) if t else 0}
            for k, v in sorted(point_count_by_year[y].items(), key=lambda x: -x[1])
        ]

    distribution_by_point = [
        {
            "point_name": k,
            "question_ids": sorted(v),
            "question_count": len(v),
            "score_weight": round(point_score_weight[k], 2),
        }
        for k, v in sorted(point_questions.items(), key=lambda x: -len(x[1]))
    ]
    distribution_by_year_and_point: Dict[str, List[Dict[str, Any]]] = {}
    for y in unique_years:
        distribution_by_year_and_point[y] = [
            {
                "point_name": k,
                "question_ids": sorted(v),
                "question_count": len(v),
            }
            for k, v in sorted(point_questions_by_year[y].items(), key=lambda x: -len(x[1]))
        ]

    # 试卷列表（年份、标题）
    exam_list: List[Dict[str, str]] = []
    for eid in selected_exam_ids:
        info = exam_storage.get_exam_status(eid)
        if info:
            exam_list.append({
                "exam_id": eid,
                "year": exam_id_to_year.get(eid, ""),
                "title": info.get("title") or "",
                "subject": info.get("subject") or "",
            })
    total_questions = len(set(m.get("question_id") for m in mappings))
    num_points = len(point_count_total)

    overview = f"本报告基于当前试题分析对话的已验证映射生成。共 {len(exam_list)} 套试卷、{total_questions} 道题目，涉及 {num_points} 个知识点。"
    summary = overview
    if has_trend:
        summary += " 多年份数据已计算考频与分布趋势。"
    else:
        summary += " 当前仅包含一年试卷，未进行跨年趋势分析。"

    # 学习建议：按考频与分值权重排序，取 Top 知识点
    sorted_points = sorted(
        point_questions.keys(),
        key=lambda p: (point_count_total[p], point_score_weight[p]),
        reverse=True,
    )
    top_points = sorted_points[:5]
    suggestions = [f"优先复习：{p}（考频 {point_count_total[p]} 次）" for p in top_points if point_count_total[p] > 0]

    return {
        "overview": overview,
        "summary": summary,
        "exam_list": exam_list,
        "total_questions": total_questions,
        "frequency_by_point": frequency_by_point,
        "frequency_by_year_and_point": frequency_by_year_and_point,
        "distribution_by_point": distribution_by_point,
        "distribution_by_year_and_point": distribution_by_year_and_point,
        "doc_distribution_total": doc_distribution_total,
        "doc_distribution_by_year": doc_distribution_by_year,
        "mapping_table_by_year": dict(mapping_table_by_year),
        "suggestions": suggestions,
        "meta": {"has_trend": has_trend, "years": unique_years},
    }
