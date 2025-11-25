# -*- coding: utf-8 -*-
# ===========================================================
# 文件：backend/app/agents/agent_e_question_generation.py
# 功能：Agent E – 智能出题生成（高保真仿真版，最小差异修正版）
# ===========================================================

import os
import json
import re
import aiohttp
import asyncio
from dotenv import load_dotenv
from app.agents.shared_state import shared_state
from app.agents.models.quiz_models import Question, QuestionBank, SubQuestion
from app.agents.database.question_bank_storage import save_question_bank, BASE_DATA_DIR

# -----------------------------------------------------------
# 环境配置
# -----------------------------------------------------------

load_dotenv()
API_URL = os.getenv("LLM_BINDING_HOST", "https://api.siliconflow.cn/v1")
API_KEY = os.getenv("LLM_BINDING_API_KEY")
MODEL_NAME = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


def _save_llm_response(conversation_id: str, section_name: str, prompt: str, response: str):
    """保存 LLM 的完整请求和响应到 debug 目录"""
    debug_dir = os.path.join(BASE_DATA_DIR, conversation_id, "debug")
    os.makedirs(debug_dir, exist_ok=True)
    
    # 清理文件名中的非法字符
    safe_section = re.sub(r'[\\/:*?"<>|]', '_', section_name)
    file_path = os.path.join(debug_dir, f"agent_e_{safe_section}_response.txt")
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"Section: {section_name}\n")
        f.write("=" * 80 + "\n\n")
        f.write("【发送的 Prompt】\n")
        f.write("-" * 40 + "\n")
        f.write(prompt)
        f.write("\n\n")
        f.write("【LLM 原始响应】\n")
        f.write("-" * 40 + "\n")
        f.write(response)
        f.write("\n")
    
    print(f"📝 LLM 响应已保存：{file_path}")

def _has_cjk(s: str) -> bool:
    import re
    return bool(re.search(r"[\u4e00-\u9fff]", s or ""))

def _detect_language_from_stem(stem: str) -> str:
    return "Chinese" if _has_cjk(stem or "") else "English"


def _format_sub_questions(sub_questions, indent=1) -> str:
    """递归格式化子题目为文本，供 Prompt 使用"""
    if not sub_questions:
        return ""
    
    lines = []
    prefix = "  " * indent
    for sq in sub_questions:
        label = sq.label if hasattr(sq, 'label') else sq.get('label', '')
        stem = sq.stem if hasattr(sq, 'stem') else sq.get('stem', '')
        kps = sq.knowledge_points if hasattr(sq, 'knowledge_points') else sq.get('knowledge_points', [])
        difficulty = sq.difficulty if hasattr(sq, 'difficulty') else sq.get('difficulty', 'medium')
        nested = sq.sub_questions if hasattr(sq, 'sub_questions') else sq.get('sub_questions', [])
        
        lines.append(f"{prefix}({label}) {stem}")
        if kps:
            lines.append(f"{prefix}    知识点: {', '.join(kps)}")
        if difficulty:
            lines.append(f"{prefix}    难度: {difficulty}")
        
        # 递归处理嵌套子题
        if nested:
            lines.append(_format_sub_questions(nested, indent + 1))
    
    return "\n".join(lines)


def _sub_questions_to_json_example(sub_questions) -> list:
    """将子题目转换为 JSON 示例结构"""
    if not sub_questions:
        return []
    
    result = []
    for sq in sub_questions:
        label = sq.label if hasattr(sq, 'label') else sq.get('label', '')
        stem = sq.stem if hasattr(sq, 'stem') else sq.get('stem', '')
        kps = sq.knowledge_points if hasattr(sq, 'knowledge_points') else sq.get('knowledge_points', [])
        difficulty = sq.difficulty if hasattr(sq, 'difficulty') else sq.get('difficulty', 'medium')
        qtype = sq.question_type if hasattr(sq, 'question_type') else sq.get('question_type', 'short_answer')
        nested = sq.sub_questions if hasattr(sq, 'sub_questions') else sq.get('sub_questions', [])
        
        item = {
            "label": label,
            "stem": stem,
            "knowledge_points": kps,
            "difficulty": difficulty,
            "question_type": qtype,
        }
        if nested:
            item["sub_questions"] = _sub_questions_to_json_example(nested)
        result.append(item)
    
    return result


def _parse_sub_questions_from_dict(sub_list: list) -> list:
    """从 LLM 返回的字典列表解析为 SubQuestion 对象列表"""
    if not sub_list or not isinstance(sub_list, list):
        return []
    
    result = []
    for item in sub_list:
        if not isinstance(item, dict):
            continue
        
        label = str(item.get("label", "")).strip()
        stem = str(item.get("stem", "")).strip()
        if not stem:
            continue
        
        # 递归解析嵌套子题
        nested = _parse_sub_questions_from_dict(item.get("sub_questions", []))
        
        sq = SubQuestion(
            label=label or "sub",
            stem=stem,
            score=int(item.get("score", 0)) if item.get("score") else 0,
            question_type=str(item.get("question_type", "short_answer")),
            difficulty=str(item.get("difficulty", "medium")),
            knowledge_points=item.get("knowledge_points", []) or ["通用知识"],
            sub_questions=nested
        )
        result.append(sq)
    
    return result

def _extract_json_array(text: str):
    """从 LLM 输出中提取 JSON 数组，支持嵌套结构（如 sub_questions）"""
    if not text:
        return []
    
    text = text.strip()
    
    def _safe_parse(candidate: str):
        """尝试解析 JSON，处理常见的 LaTeX 转义问题"""
        fixed = candidate
        
        # 修复 LaTeX 中常见的非法 JSON 转义
        # \{ \} \( \) 在 LaTeX 中是合法的，但在 JSON 中需要双反斜杠
        # 注意：只在字符串值内部处理，不影响 JSON 结构
        latex_escapes = [
            (r'\{', r'\\{'),
            (r'\}', r'\\}'),
            (r'\(', r'\\('),
            (r'\)', r'\\)'),
            (r'\[', r'\\['),
            (r'\]', r'\\]'),
            (r'\_', r'\\_'),
            (r'\^', r'\\^'),
            (r'\&', r'\\&'),
            (r'\%', r'\\%'),
            (r'\$', r'\\$'),
            (r'\#', r'\\#'),
        ]
        
        for old, new in latex_escapes:
            # 避免重复转义（如果已经是 \\ 开头就跳过）
            fixed = re.sub(r'(?<!\\)' + re.escape(old), new, fixed)
        
        return json.loads(fixed)
    
    def _find_balanced_json_array(s: str, start_pos: int = 0) -> str:
        """使用括号匹配找到完整的 JSON 数组"""
        # 找到第一个 [
        arr_start = s.find('[', start_pos)
        if arr_start == -1:
            return None
        
        bracket_count = 0
        brace_count = 0
        in_string = False
        escape_next = False
        
        for i in range(arr_start, len(s)):
            char = s[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        return s[arr_start:i+1]
                elif char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
        
        return None
    
    # 1. 尝试提取 ```json ... ``` 代码块
    code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if code_block_match:
        block_content = code_block_match.group(1).strip()
        json_str = _find_balanced_json_array(block_content)
        if json_str:
            try:
                return _safe_parse(json_str)
            except json.JSONDecodeError:
                pass
    
    # 2. 直接在文本中查找 JSON 数组
    json_str = _find_balanced_json_array(text)
    if json_str:
        try:
            return _safe_parse(json_str)
        except json.JSONDecodeError as e:
            print(f"[⚠️ JSON 解析失败] {e}")
            # 尝试修复常见问题后重试
            try:
                # 移除可能的尾部逗号
                fixed = re.sub(r',\s*}', '}', json_str)
                fixed = re.sub(r',\s*]', ']', fixed)
                return _safe_parse(fixed)
            except:
                pass
    
    # 3. 全角括号转半角后重试
    txt2 = text.replace("【", "[").replace("】", "]")
    json_str = _find_balanced_json_array(txt2)
    if json_str:
        try:
            return _safe_parse(json_str)
        except:
            pass
    
    # 4. 尝试解析单个对象
    brace_start = text.find('{')
    if brace_start != -1:
        brace_count = 0
        in_string = False
        escape_next = False
        for i in range(brace_start, len(text)):
            char = text[i]
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        try:
                            return [_safe_parse(text[brace_start:i+1])]
                        except:
                            break
    
    return []


def _convert_html_table_to_markdown(html_text: str) -> str:
    """将HTML表格转换为Markdown表格格式，供LLM理解"""
    if not html_text or '<table' not in html_text.lower():
        return html_text
    
    result = html_text
    # 查找所有表格
    table_pattern = re.compile(r'<table[^>]*>(.*?)</table>', re.DOTALL | re.IGNORECASE)
    
    for table_match in table_pattern.finditer(html_text):
        table_html = table_match.group(0)
        table_content = table_match.group(1)
        
        # 提取所有行
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_content, re.DOTALL | re.IGNORECASE)
        if not rows:
            continue
        
        markdown_rows = []
        for i, row in enumerate(rows):
            # 提取单元格
            cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row, re.DOTALL | re.IGNORECASE)
            if cells:
                # 清理单元格内容
                clean_cells = []
                for cell in cells:
                    cell_text = re.sub(r'<[^>]+>', '', cell)
                    cell_text = ' '.join(cell_text.split())
                    clean_cells.append(cell_text)
                
                # 构建Markdown行
                markdown_rows.append('| ' + ' | '.join(clean_cells) + ' |')
                
                # 第一行后添加分隔符
                if i == 0:
                    markdown_rows.append('| ' + ' | '.join(['---'] * len(clean_cells)) + ' |')
        
        # 替换原HTML表格
        if markdown_rows:
            markdown_table = '\n' + '\n'.join(markdown_rows) + '\n'
            result = result.replace(table_html, markdown_table)
    
    return result


def _convert_markdown_table_to_html(markdown_text: str) -> str:
    """将Markdown表格转换为HTML表格格式，用于保存和显示"""
    if not markdown_text or '|' not in markdown_text:
        return markdown_text
    
    result = markdown_text
    # 匹配Markdown表格
    # 格式：| Header | Header |\n|--------|--------|\n| Cell | Cell |
    table_pattern = re.compile(
        r'(\|.+\|\n\|[\s\-:]+\|\n(?:\|.+\|\n?)+)',
        re.MULTILINE
    )
    
    for table_match in table_pattern.finditer(markdown_text):
        markdown_table = table_match.group(0)
        lines = [line.strip() for line in markdown_table.split('\n') if line.strip()]
        
        if len(lines) < 2:
            continue
        
        # 第一行是表头
        header_cells = [cell.strip() for cell in lines[0].split('|') if cell.strip()]
        
        # 第二行是分隔符，跳过
        # 其余行是数据
        data_rows = []
        for line in lines[2:]:
            cells = [cell.strip() for cell in line.split('|') if cell.strip()]
            if cells:
                data_rows.append(cells)
        
        # 构建HTML表格
        html_parts = ['<table>']
        
        # 表头
        html_parts.append('<tr>')
        for cell in header_cells:
            html_parts.append(f'<td>{cell}</td>')
        html_parts.append('</tr>')
        
        # 数据行
        for row_cells in data_rows:
            html_parts.append('<tr>')
            for cell in row_cells:
                html_parts.append(f'<td>{cell}</td>')
            html_parts.append('</tr>')
        
        html_parts.append('</table>')
        
        html_table = ''.join(html_parts)
        result = result.replace(markdown_table, html_table)
    
    return result


async def _generate_answer_for_table_question(session, question_id: str, stem: str) -> str:
    """为包含表格的题目生成答案"""
    if '<table' not in stem:
        return None
    
    # 将HTML表格转为Markdown供LLM理解
    stem_for_llm = _convert_html_table_to_markdown(stem)
    
    prompt = f"""请为以下题目提供详细的答案。题目包含表格数据，请仔细分析表格中的信息来回答问题。

题目：
{stem_for_llm}

要求：
1. 如果题目有多个子问题(a)(b)(c)等，请分别作答
2. 对于计算题，给出计算步骤和最终结果
3. 对于分析题，给出清晰的分析思路和结论
4. 答案要简洁明确，重点突出关键步骤和结论
5. 使用中文作答

请直接输出答案，不要重复题目：
"""
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "你是一名数据挖掘和机器学习领域的专家，擅长解答算法、数学计算和数据分析相关的问题。"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2000,
        "temperature": 0.3,
    }
    
    try:
        print(f"[→] 正在为表格题目 {question_id} 生成答案...")
        async with session.post(f"{API_URL}/chat/completions", headers=HEADERS, json=payload, timeout=300) as resp:
            res = await resp.json()
            if "error" in res:
                print(f"❌ API错误: {res['error']}")
                return None
            
            if "choices" not in res or len(res["choices"]) == 0:
                print(f"❌ 响应格式错误")
                return None
            
            answer = res["choices"][0]["message"]["content"].strip()
            print(f"✅ 表格题目 {question_id} 答案已生成 (长度: {len(answer)})")
            return answer
    except Exception as e:
        print(f"❌ 表格题目 {question_id} 答案生成失败: {e}")
        return None


# -----------------------------------------------------------
# Prompt 构造
# -----------------------------------------------------------

def build_prompt(section, distribution_model, examples=None, global_difficulty="medium",
                 expected_count=None, expected_type=None, expected_kps=None,
                 target_difficulty_hint="保持与样例相同层级，但在深度与综合性上提高",
                 min_subparts=2,expected_language=None):
    """
    构造高保真出题 Prompt：
    - 题量/题型硬约束
    - 知识点必含清单
    - 深度要求（多步子问、定量分析、边界/对比）
    """
    type_info = distribution_model.get("type_distribution", {})
    diff_info = distribution_model.get("difficulty_distribution", {})
    kp_info   = distribution_model.get("knowledge_point_distribution", {})

    prompt = f"""
你是一名经验丰富的命题专家。请根据以下约束生成新的高质量题目：
1️⃣ 难度与样题一致（{target_difficulty_hint}），不得简化题意、缩短篇幅或降低逻辑复杂度；
2️⃣ 确保知识点覆盖合理，符合专业课程考试风格；
3️⃣ 输出格式必须为 JSON 数组，不含额外文字。

【出题目标】
- 当前章节：{section['title']}
- 建议难度水平：{global_difficulty}
- 题型分布参考：{json.dumps(type_info, ensure_ascii=False, indent=2)}
- 难度分布参考：{json.dumps(diff_info, ensure_ascii=False, indent=2)}
- 知识点覆盖参考：{json.dumps(kp_info, ensure_ascii=False, indent=2)}
"""
    if expected_count is not None:
        prompt += f"\n【数量约束】本节必须严格生成 {expected_count} 道题（不多不少）。"
    if expected_type:
        prompt += f"\n【题型约束】本节题型固定为：{expected_type}（每题 question_type 保持一致）。"
    if expected_kps:
        prompt += f"\n【知识点约束】本节生成的题目必须显式覆盖以下知识点：{expected_kps}。"

    # —— 深度与结构要求（关键）——
    prompt += f"""
【深度与结构要求】
- 题干需包含至少 {min_subparts} 个有递进关系的子问（(a)(b)(c) …），覆盖不同角度（定义/推导/比较/反例/复杂度/工程取舍）。
- 至少包含一次“定量计算或公式推导”与一次“方法对比或边界/异常情形分析”。
- 如为综合/应用类题，要求设置真实数据片段或近似数据、并给出明确计算或判断步骤。
- 对于选择题，干扰项必须基于常见误区（不要明显错误的选项）。

【样题参考】
"""
    if examples:
        example_snippets = []
        for q in examples[:3]:
            # 将样题中的HTML表格转换为Markdown，让LLM更容易理解和模仿
            stem_for_llm = _convert_html_table_to_markdown(q.stem)
            
            snippet = (
                f"题干：{stem_for_llm}\n"
                f"答案：{q.answer or '（无答案）'}\n"
                f"知识点：{', '.join(q.knowledge_points)}\n"
                f"难度：{q.difficulty}\n"
                f"题型：{q.question_type}\n"
            )
            
            # 添加子题目信息
            sub_qs = q.sub_questions if hasattr(q, 'sub_questions') else []
            if sub_qs:
                snippet += f"子题目数量：{len(sub_qs)}\n"
                snippet += f"子题目结构：\n{_format_sub_questions(sub_qs)}\n"
            
            example_snippets.append(snippet)
        prompt += "\n---\n".join(example_snippets)

    # ✅ 在这里插入语言约束逻辑
    if expected_language:
        prompt += f"\n【语言约束】题干（stem）、答案（answer）、解析（explanation）必须使用 {expected_language} 输出；" \
                  f"knowledge_points 字段可以使用中文。"

    # 根据样题是否有子题目，动态生成输出格式示例
    has_sub_questions = False
    if examples:
        for q in examples[:3]:
            sub_qs = q.sub_questions if hasattr(q, 'sub_questions') else []
            if sub_qs:
                has_sub_questions = True
                break
    
    prompt += """
【表格格式说明】
如果题目需要包含表格数据，请使用Markdown表格格式：
| 列1 | 列2 | 列3 |
|-----|-----|-----|
| 数据1 | 数据2 | 数据3 |

【输出格式示例】
"""
    
    if has_sub_questions:
        prompt += """[
  {
    "stem": "主题干文本（简短描述题目背景或总体要求）",
    "options": [],
    "answer": "（待补充）或综合答案要点",
    "explanation": "整体解析说明",
    "difficulty": "easy | medium | hard",
    "knowledge_points": ["涉及的知识点 1", "知识点 2"],
    "question_type": "short_answer | calculation | comprehensive",
    "sub_questions": [
      {
        "label": "a",
        "stem": "子问题(a)的具体题干内容",
        "knowledge_points": ["子题知识点"],
        "difficulty": "easy | medium | hard",
        "question_type": "short_answer | calculation",
        "sub_questions": []
      },
      {
        "label": "b",
        "stem": "子问题(b)的具体题干内容",
        "knowledge_points": ["子题知识点"],
        "difficulty": "easy | medium | hard",
        "question_type": "calculation",
        "sub_questions": [
          {
            "label": "i",
            "stem": "嵌套子问题(i)内容",
            "knowledge_points": ["嵌套子题知识点"],
            "difficulty": "easy",
            "question_type": "short_answer",
            "sub_questions": []
          }
        ]
      }
    ]
  }
]
注意：
1. 如果样题有子题目结构，生成的题目也必须包含 sub_questions 数组
2. 每个子题目必须有独立的 label（如 a/b/c 或 i/ii/iii）、stem、knowledge_points
3. 子题目可以嵌套（如 c 下面有 i/ii/iii）
"""
    else:
        prompt += """[
  {
    "stem": "题干文本",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "answer": "正确答案或要点",
    "explanation": "简要说明正确原因",
    "difficulty": "easy | medium | hard",
    "knowledge_points": ["涉及的知识点 1", "知识点 2"],
    "question_type": "single_choice | short_answer | calculation"
  }
]
"""
    
    prompt += "只输出 JSON，不要添加解释或其他自然语言。\n"
    return prompt



# -----------------------------------------------------------
# 调用 LLM 异步生成
# -----------------------------------------------------------

async def async_generate_section(session, section, distribution_model, examples=None, global_difficulty="medium"):
    # 期望题数
    expected_count = None
    try:
        ranges = section.get("question_ranges", [])
        expected_count = sum(r.get("to", 0) - r.get("from", 0) + 1 for r in ranges if r)
    except Exception:
        pass

    # 期望题型（来自标题 “… Section”）
    expected_type = None
    title = section.get("title") or ""
    if isinstance(title, str) and title.endswith(" Section"):
        expected_type = title[:-8]

    # 模板知识点与难度提示（在 run_agent_e 里设置进 section）
    expected_kps = section.get("expected_kps")
    target_difficulty_hint = section.get("target_difficulty_hint", "保持与样例相同层级，但在深度与综合性上提高")

    # 🆕 根据 question_ranges 选择对应的 examples
    section_examples = examples  # 默认使用全部 examples
    if examples and len(examples) > 0:
        try:
            ranges = section.get("question_ranges", [])
            if ranges and len(ranges) > 0:
                # 获取第一个 range 的起始位置（1-based index）
                start_idx = ranges[0].get("from", 1) - 1  # 转换为 0-based
                end_idx = ranges[0].get("to", 1)  # inclusive
                section_examples = examples[start_idx:end_idx]
                print(f"[📌 Section] 使用 examples[{start_idx}:{end_idx}]，共 {len(section_examples)} 道题")
        except Exception as e:
            print(f"[⚠️ 选择 section examples 失败] {e}")

    prompt = build_prompt(
        section, distribution_model, section_examples, global_difficulty,
        expected_count=expected_count, expected_type=expected_type,
        expected_kps=expected_kps, target_difficulty_hint=target_difficulty_hint,
        min_subparts=2, expected_language=section.get("expected_language")
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "你是一名高级考试命题专家，擅长生成尺度恰当且覆盖全面的深度试题。"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4000,   # ↑ 略增
        "temperature": 0.6,   # ↓ 略降，提升稳定度与对齐度
        "top_p": 0.95,
    }

    # 获取 conversation_id 用于保存 debug 文件
    conv_id = section.get("_conversation_id", "unknown")
    section_title = section.get("title", "unknown").replace(" ", "_")
    
    try:
        async with session.post(f"{API_URL}/chat/completions", headers=HEADERS, json=payload, timeout=240) as resp:
            res = await resp.json()
            content = res["choices"][0]["message"]["content"]
            
            # 保存 LLM 原始响应到 debug 目录
            _save_llm_response(conv_id, section_title, prompt, content)
            
            items = _extract_json_array(content)

            # 将LLM生成的Markdown表格转换为HTML表格
            for item in items:
                if 'stem' in item and item['stem']:
                    item['stem'] = _convert_markdown_table_to_html(item['stem'])
                if 'answer' in item and item['answer']:
                    item['answer'] = _convert_markdown_table_to_html(item['answer'])
                if 'explanation' in item and item['explanation']:
                    item['explanation'] = _convert_markdown_table_to_html(item['explanation'])

            # 🆕 为包含表格的题目生成答案
            for idx, item in enumerate(items, 1):
                stem = item.get('stem', '')
                answer = item.get('answer', '')
                # 如果题干包含表格且答案为空或为待补充，则生成答案
                if '<table' in stem and (not answer or answer == '（待补充）'):
                    question_id = f"{section.get('title', 'Q')}_{idx}"
                    generated_answer = await _generate_answer_for_table_question(session, question_id, stem)
                    if generated_answer:
                        item['answer'] = generated_answer

            # 超额裁剪（不足不做二次重试，保持最小改动策略）
            if expected_count is not None and len(items) > expected_count:
                items = items[:expected_count]
            return items
    except Exception as e:
        print(f"[❌ LLM 生成失败] section={section.get('title', 'unknown')}, error={e}")
        print(f"[🔄 使用降级方案] 基于当前 section 的样例题目生成")
        
        # 降级方案：使用样例题目或生成简单题目
        fallback_questions = []
        
        # 🆕 使用 section_examples 而不是 examples（确保每个 section 用不同的题目）
        if section_examples and len(section_examples) > 0:
            for idx, example in enumerate(section_examples[:expected_count or 1], 1):
                q_dict = example.dict() if hasattr(example, 'dict') else example
                fallback_questions.append({
                    "stem": q_dict.get('stem', f"示例题目 {idx}"),
                    "options": q_dict.get('options', []),
                    "answer": q_dict.get('answer', '参考答案'),
                    "explanation": q_dict.get('explanation', '详见教材'),
                    "difficulty": global_difficulty,
                    "knowledge_points": q_dict.get('knowledge_points', ['通用知识']),
                    "question_type": q_dict.get('question_type', 'short_answer')
                })
        else:
            # 生成默认题目
            for i in range(expected_count or 3):
                fallback_questions.append({
                    "stem": f"请简述{section.get('name', '相关')}的主要概念。",
                    "options": [],
                    "answer": "请参考教材相关章节。",
                    "explanation": "本题考查基础概念理解。",
                    "difficulty": global_difficulty,
                    "knowledge_points": [section.get('name', '通用知识')],
                    "question_type": "short_answer"
                })
        
        print(f"[✅ 降级方案生成] {len(fallback_questions)} 道题目")
        return fallback_questions



# -----------------------------------------------------------
# 主函数
# -----------------------------------------------------------

def run_agent_e(conversation_id: str):
    print("🧩 [Agent E] 高保真智能出题生成开始...")

    qb = shared_state.question_bank
    dist_model = shared_state.distribution_model
    structure_model = getattr(shared_state, "sample_structure", None)

    if not dist_model:
        print("⚠️ 缺少 Agent C 输出，无法生成分布模型。")
        return None

    # —— 若存在模板题库：逐题建段（顺序对齐 + 题型对齐 + 知识点对齐）——
    if qb and getattr(qb, "questions", None):
        sections = []
        TYPE_TITLE_EN = {
            "简答题": "Short Answer",
            "综合题": "Comprehensive",
            "综合分析题": "Comprehensive",
            "算法应用题": "Applied Algorithms",
            "计算题": "Problem Solving",
        }
        for idx, tq in enumerate(qb.questions, start=1):
            t = (tq.question_type or "short_answer")
            # 标题英文化，避免中英混排干扰模型语言选择
            title_en = TYPE_TITLE_EN.get(t, t if _has_cjk(t) is False else "Section")
            expected_language = _detect_language_from_stem(getattr(tq, "stem", "") or "")
            sections.append({
                "title": f"{title_en} Section_{idx}",
                "question_ranges": [{"from": idx, "to": idx}],
                "score": None,
                "expected_kps": tq.knowledge_points if getattr(tq, "knowledge_points", None) else None,
                "target_difficulty_hint": "保持与样例相同层级，但在深度与综合性上提高",
                "expected_language": expected_language,
                "_conversation_id": conversation_id,  # 用于保存 debug 文件
            })
        structure_model = {"sections": sections}
    else:
        # 无模板则保留你的原兜底，顺便修补"sections 为空也视为无效结构"
        if (not structure_model
            or structure_model.get("section_count", 0) == 0
            or not structure_model.get("sections")):
            print("⚠️ 无有效样例结构，使用 Agent C 的题型比例生成虚拟章节。")
            type_dist = dist_model.get("type_distribution", {})
            sections = []
            q_start = 1
            total_questions = dist_model.get("total_questions", 10)
            for t, ratio in type_dist.items():
                count = max(1, int(total_questions * ratio))
                q_end = q_start + count - 1
                sections.append({
                    "title": f"{t} Section",
                    "question_ranges": [{"from": q_start, "to": q_end}],
                    "score": None,
                    "_conversation_id": conversation_id,
                })
                q_start = q_end + 1
            structure_model = {"sections": sections}

    # 自动检测全局难度（保持不变）
    if qb and getattr(qb, "questions", None):
        difficulties = [q.difficulty for q in qb.questions if q.difficulty]
        global_difficulty = max(set(difficulties), key=difficulties.count) if difficulties else "medium"
    else:
        global_difficulty = "medium"

    print(f"👉 检测到整体难度：{global_difficulty}")

    async def main():
        async with aiohttp.ClientSession() as session:
            tasks = [
                async_generate_section(session, section, dist_model, qb.questions if qb else None, global_difficulty)
                for section in structure_model["sections"]
            ]
            return await asyncio.gather(*tasks)

    all_sections = asyncio.run(main())

    # 合并生成题目
    generated_questions = []
    for sec in all_sections:
        for item in sec:
            try:
                # 解析子题目
                sub_questions = _parse_sub_questions_from_dict(item.get("sub_questions", []))
                
                q = Question(
                    id=f"GEN_{len(generated_questions)+1:03d}",
                    stem=item.get("stem"),
                    options=item.get("options", []),
                    answer=item.get("answer"),
                    explanation=item.get("explanation"),
                    difficulty=item.get("difficulty", "medium"),
                    knowledge_points=item.get("knowledge_points", ["通用知识"]),
                    question_type=item.get("question_type", "short_answer"),
                    sub_questions=sub_questions
                )
                generated_questions.append(q)
                
                if sub_questions:
                    print(f"[✓] 题目 {q.id} 包含 {len(sub_questions)} 个子题目")
            except Exception as e:
                print(f"[⚠️ 题目解析异常] {e}")

    new_qb = QuestionBank(questions=generated_questions)
    shared_state.generated_exam = new_qb

    save_path = save_question_bank(f"{conversation_id}_generated", new_qb)
    print(f"✅ 高保真 Agent E 完成，共生成 {len(generated_questions)} 题。")
    print(f"💾 题库保存路径：{save_path}")
    return new_qb



