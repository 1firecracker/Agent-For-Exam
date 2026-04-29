"""对话管理 API"""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

import app.config as config
from app.services.config_service import config_service
from app.services.conversation_service import ConversationService
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

# 请求/响应模型
class ConversationCreateRequest(BaseModel):
    title: Optional[str] = None

class ConversationUpdateRequest(BaseModel):
    title: Optional[str] = None
    pinned: Optional[bool] = None

class ConversationResponse(BaseModel):
    conversation_id: str
    title: str
    subject_id: Optional[str] = None
    conversation_type: str = "chat"
    selected_exam_ids: Optional[List[str]] = None
    created_at: str
    updated_at: str
    file_count: int
    status: str
    pinned: bool = False

    class Config:
        from_attributes = True

class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    total: int


class CheatsheetLayout(BaseModel):
    paper_type: str = "A4"
    orientation: str = "portrait"
    font_size: int = Field(default=10, ge=8, le=14)
    line_height: float = Field(default=1.2, ge=1.0, le=1.5)
    margin: str = "narrow"
    margin_mm: int = Field(default=8, ge=4, le=30)
    columns: int = Field(default=2, ge=1, le=4)


class CheatsheetContentOptions(BaseModel):
    density: str = "standard"
    include_formulas: bool = True
    include_definitions: bool = True
    include_algorithms: bool = True
    include_examples: bool = True
    include_page_refs: bool = True


class CheatsheetGenerateRequest(BaseModel):
    subject_id: str
    document_ids: List[str]
    layout: CheatsheetLayout = Field(default_factory=CheatsheetLayout)
    content_options: CheatsheetContentOptions = Field(default_factory=CheatsheetContentOptions)
    language: str = "auto"
    style: str = "auto"
    user_prompt: Optional[str] = None


class CheatsheetUpdateRequest(BaseModel):
    content: str
    layout: Optional[CheatsheetLayout] = None
    content_options: Optional[CheatsheetContentOptions] = None
    language: Optional[str] = None
    style: Optional[str] = None
    user_prompt: Optional[str] = None


class CheatsheetPdfRequest(BaseModel):
    # 可选：如果不传 content，则使用已保存的 cheatsheet.content
    content: Optional[str] = None
    html: Optional[str] = None
    layout: Optional[CheatsheetLayout] = None
    content_options: Optional[CheatsheetContentOptions] = None
    language: Optional[str] = None
    style: Optional[str] = None


def _cheatsheet_file(conversation_id: str) -> Path:
    return Path(config.settings.conversations_dir) / conversation_id / "cheatsheet.json"


def _strip_markdown_fence(content: str) -> str:
    text = (content or "").strip()
    match = re.match(r"^```(?:markdown|md)?\s*([\s\S]*?)\s*```$", text, re.IGNORECASE)
    return match.group(1).strip() if match else text


def _normalize_cheatsheet_soft_breaks(content: str) -> str:
    """Fold PDF/PPT extraction soft breaks so preview and PDF export use the same text shape."""
    if not content:
        return content

    normalized_content = _strip_markdown_fence(content).replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized_content.split("\n")
    nonblank = [line.strip() for line in lines if line.strip()]

    blank_count = len(lines) - len(nonblank)
    short_count = sum(1 for line in nonblank if len(line) <= 18)
    is_stream_spaced = (
        len(nonblank) >= 80
        and blank_count >= len(nonblank) * 0.5
        and short_count / len(nonblank) >= 0.8
    )

    repaired: List[str] = []
    paragraph_parts: List[str] = []
    in_fence = False

    def is_structural(line: str) -> bool:
        if not line:
            return True
        if line.startswith("```"):
            return True
        return bool(re.match(r"^(#{1,6}\s+|[-*]\s+|\d+\.\s+|>\s+|\|)", line))

    def normalize_joined_text(joined: str) -> str:
        text = re.sub(r"\s+([,.;:!?%)\]])", r"\1", joined)
        text = re.sub(r"([(\[])\s+", r"\1", text)
        text = re.sub(r"\*\*\s+([^*]+?)\s+\*\*", r"**\1**", text)
        return re.sub(r"\s{2,}", " ", text).strip()

    def flush_paragraph() -> None:
        if not paragraph_parts:
            return
        trimmed = [part.strip() for part in paragraph_parts if part.strip()]
        if not trimmed:
            paragraph_parts.clear()
            return
        avg_len = sum(len(part) for part in trimmed) / len(trimmed)
        if is_stream_spaced or (len(trimmed) >= 12 and avg_len <= 18):
            repaired.append(normalize_joined_text(" ".join(trimmed)))
        else:
            repaired.append("\n".join(part.rstrip() for part in paragraph_parts).rstrip())
        paragraph_parts.clear()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if is_stream_spaced:
                continue
            flush_paragraph()
            if repaired and repaired[-1] != "":
                repaired.append("")
            continue
        if line.startswith("```"):
            flush_paragraph()
            in_fence = not in_fence
            repaired.append(raw_line.rstrip())
            continue
        if in_fence:
            repaired.append(raw_line.rstrip())
            continue
        if is_structural(line):
            flush_paragraph()
            repaired.append(raw_line.rstrip())
            continue
        paragraph_parts.append(raw_line)

    flush_paragraph()
    if is_stream_spaced:
        return "\n\n".join(part for part in repaired if part).strip()
    return "\n".join(repaired).strip()


def _repair_stream_spaced_cheatsheet(content: str) -> str:
    """Backward-compatible wrapper for old saved cheatsheets."""
    return _normalize_cheatsheet_soft_breaks(content)


def _load_cheatsheet(conversation_id: str) -> Optional[Dict[str, Any]]:
    file_path = _cheatsheet_file(conversation_id)
    if not file_path.exists():
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("content"), str):
            data["content"] = _repair_stream_spaced_cheatsheet(data["content"])
        return data
    except Exception:
        return None


def _save_cheatsheet(conversation_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    file_path = _cheatsheet_file(conversation_id)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.utcnow().isoformat() + "Z"
    existing = _load_cheatsheet(conversation_id) or {}
    payload = {
        **existing,
        **data,
        "conversation_id": conversation_id,
        "updated_at": now,
        "created_at": existing.get("created_at", now),
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def _delete_cheatsheet(conversation_id: str) -> bool:
    file_path = _cheatsheet_file(conversation_id)
    if not file_path.exists():
        return False
    file_path.unlink()
    return True


def _json_event(event: str, data: Dict[str, Any]) -> str:
    return f"data: {json.dumps({'event': event, **data}, ensure_ascii=False)}\n\n"


def _chunk_text(text: str, max_chars: int = 1800) -> List[str]:
    """Split lecture text into stable chunks so the LLM covers more source material."""
    chunks = []
    current = []
    current_len = 0
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        block_len = len(block)
        if current and current_len + block_len > max_chars:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        if block_len > max_chars:
            for start in range(0, block_len, max_chars):
                chunks.append(block[start:start + max_chars])
            continue
        current.append(block)
        current_len += block_len
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _build_cheatsheet_chunk_prompt(
    filename: str,
    chunk_text: str,
    chunk_index: int,
    total_chunks: int,
    request: CheatsheetGenerateRequest,
) -> str:
    options = request.content_options
    layout = request.layout
    style = request.style if request.style and request.style != "auto" else "faithful"
    custom_prompt = request.user_prompt.strip() if request.user_prompt else "尽量把原文知识点紧密转写到 cheatsheet 中，少做抽象总结。"
    min_items = max(10, min(36, len(chunk_text) // 90))
    return f"""你是考试复习 cheatsheet 编写助手。请严格基于当前讲义片段生成 Markdown cheatsheet，不要编造讲义外信息。

用户提示词：
{custom_prompt}

生成风格：{style}
语言偏好：{request.language}（auto 表示默认使用讲义主要语言）
内容密度：{options.density}
排版约束：纸张 {layout.paper_type}，方向 {layout.orientation}，字号 {layout.font_size}px，页边距 {layout.margin_mm}mm，{layout.columns} 栏。
内容选项：
- 包含公式：{options.include_formulas}
- 包含定义：{options.include_definitions}
- 包含算法步骤：{options.include_algorithms}
- 包含例题提示：{options.include_examples}
- 包含页码引用：{options.include_page_refs}

输出要求：
- 只输出 Markdown 内容，绝对不要使用 ``` 或 ```markdown 代码围栏。
- 默认采用“完全尊重原文紧密转写”：这是逐行/逐句提取式整理，不是摘要。必须为输入片段里的每个有效句子、项目符号、概念、定义、步骤、术语、例子、约束、对比和结论生成对应内容，而不是只总结 3-5 条。
- 只能转写、压缩、重排原文明确出现的内容；禁止补充原文没有出现的例子、算法、术语、应用场景或背景知识。
- 保留原文层级、顺序和术语；可压缩措辞，但不要丢关键限定条件。
- 当前片段至少输出 {min_items} 条有效要点；如果原文有效要点少于该数量，按实际数量输出。若原文存在重复页，也要至少完整写出一页的全部有效内容。
- 对列表/流程/表格型原文，逐项保留；不要合并成一句泛泛概括。
- 不要用 “all concepts appear identically / 内容重复” 这类一句话替代重复页或重复项目；如果多页重复出现，应保留首次内容并标注覆盖页码。
- 优先短句、列表、表格和公式块，适配高密度打印。
- 如能判断页码，请保留文件名和页码引用。
- 如果讲义内容不足以支持某项内容，请省略该项，不要补写；宁可少写，也不要添加外部知识。

当前文档：{filename}
当前片段：{chunk_index}/{total_chunks}

讲义片段内容：
{chunk_text}
"""


def _build_cheatsheet_backfill_prompt(
    filename: str,
    chunk_text: str,
    existing_output: str,
    request: CheatsheetGenerateRequest,
) -> str:
    custom_prompt = request.user_prompt.strip() if request.user_prompt else "尽量完整保留原文有效内容。"
    return f"""上一轮 cheatsheet 输出明显过短。请对同一讲义片段做“补漏扩写”，只补充上一轮遗漏的有效内容。

硬性要求：
- 只输出 Markdown 片段；不要代码围栏。
- 逐条检查原文每一行/每个项目，只补充上一轮遗漏的原文显式内容。
- 不要重复上一轮已有内容；不要抽象总结；不要添加原文未出现的例子、算法、术语、应用场景或背景知识。
- 如果没有遗漏的原文显式内容，只输出：无补充。
- 用户提示词：{custom_prompt}

文档：{filename}

上一轮已有输出：
{existing_output}

原文片段：
{chunk_text}
"""


def _extract_pdf_pages(text: str) -> List[Dict[str, Any]]:
    pages: List[Dict[str, Any]] = []
    current_page: Optional[Dict[str, Any]] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        marker = re.match(r"^\[FILE:([^\]]+)\]\[(?:PAGE|SLIDE):(\d+)\]$", line)
        if marker:
            current_page = {
                "file_id": marker.group(1),
                "page": marker.group(2),
                "lines": [],
            }
            pages.append(current_page)
            continue
        if current_page is None:
            current_page = {"file_id": "", "page": "?", "lines": []}
            pages.append(current_page)
        current_page["lines"].append(line)

    return pages


def _build_faithful_page_prompt(filename: str, page: Dict[str, Any], request: CheatsheetGenerateRequest) -> str:
    custom_prompt = request.user_prompt.strip() if request.user_prompt else "完整保留所有有效内容，逐页逐条转写原文，不要摘要，不要合并。"
    page_text = "\n".join(page.get("lines", []))
    return f"""你是讲义 cheatsheet 的逐页转写助手。请把当前讲义页面/幻灯片转写成 Markdown cheatsheet。

硬性要求：
- 必须使用 LLM 进行轻量整理，但不能摘要、不能合并、不能省略。
- 保留当前页面所有有效内容，尤其是编号列表、项目符号、定义、术语、公式、步骤、例子、提示。
- 如果原文有 12 个编号项，输出也必须有 12 个对应编号项。
- 重复内容也要保留，不要写“同上 / identical / duplicates / not repeated”。
- 只能转写原文明确出现的内容，禁止补充外部知识。
- 只输出 Markdown，不要代码围栏。
- 用户要求：{custom_prompt}

文档：{filename}
页码：[FILE:{page.get("file_id", "")}][PAGE:{page.get("page", "?")}]

原文页面内容：
{page_text}
"""


def _build_faithful_missing_lines(page: Dict[str, Any], generated: str) -> str:
    source_numbered = [line for line in page.get("lines", []) if re.match(r"^\d+\.\s+", line)]
    generated_numbered_count = len(re.findall(r"^\s*\d+\.\s+", generated, flags=re.MULTILINE))
    if generated_numbered_count >= len(source_numbered):
        return ""

    missing = source_numbered[generated_numbered_count:]
    if not missing:
        return ""

    output = ["", "### 原文逐条补全", ""]
    output.extend(missing)
    return "\n".join(output)


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(request: ConversationCreateRequest):
    """创建新对话
    
    用于手动创建对话，如不提供标题则自动生成编号
    """
    service = ConversationService()
    
    try:
        conversation_id = service.create_conversation(title=request.title)
        conversation = service.get_conversation(conversation_id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="对话创建失败"
            )
        
        return ConversationResponse(**conversation)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建对话失败: {str(e)}"
        )


@router.get("", response_model=ConversationListResponse)
async def list_conversations(status_filter: Optional[str] = None):
    """获取所有对话列表
    
    Args:
        status_filter: 可选，过滤状态（active/archived）
    """
    service = ConversationService()
    
    try:
        conversations = service.list_conversations(status=status_filter)
        
        return ConversationListResponse(
            conversations=[ConversationResponse(**conv) for conv in conversations],
            total=len(conversations)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取对话列表失败: {str(e)}"
        )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str):
    """获取对话详情
    
    Args:
        conversation_id: 对话ID
    """
    service = ConversationService()
    
    conversation = service.get_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话 {conversation_id} 不存在"
        )
    
    return ConversationResponse(**conversation)


@router.get("/{conversation_id}/exam_analysis/trace")
async def get_exam_analysis_trace(conversation_id: str):
    """试题分析多智能体轨迹"""
    from app.services.exam_analysis.trace_storage import TraceStorage
    data = TraceStorage.get_trace(conversation_id)
    return {"items": data.get("items", [])}


@router.get("/{conversation_id}/exam_analysis/report")
async def get_exam_analysis_report(conversation_id: str):
    """试题分析报告（第三阶段）。无 mapping 或未生成时返回 404。"""
    conv = ConversationService().get_conversation(conversation_id)

    from app.services.exam_analysis.trace_storage import TraceStorage
    from app.services.exam_analysis.report_aggregation import build_report
    cached = TraceStorage.get_report(conversation_id)
    if cached:
        return cached
    report = build_report(conversation_id)

    TraceStorage.save_report(conversation_id, report)
    return report


@router.post("/{conversation_id}/exam_analysis/report/regenerate")
async def regenerate_exam_analysis_report(conversation_id: str):
    """重新生成报告（清除缓存后根据当前 verified_mappings 再算一次）。无 mapping 时返回 404。"""
    conv = ConversationService().get_conversation(conversation_id)
    from app.services.exam_analysis.trace_storage import TraceStorage
    from app.services.exam_analysis.report_aggregation import build_report
    TraceStorage.delete_report(conversation_id)
    report = build_report(conversation_id)
    if not report:
        raise HTTPException(status_code=404, detail="暂无映射数据，请先完成试题分析")
    TraceStorage.save_report(conversation_id, report)
    return report


@router.get("/{conversation_id}/exam_analysis/stream")
async def stream_exam_analysis_events(conversation_id: str):
    """试题分析 SSE 流：先连接此接口，再 POST /exam_analysis/start，即可实时收到事件"""
    from app.services.exam_analysis.event_bus import subscribe, unsubscribe, STREAM_END
    conv = ConversationService().get_conversation(conversation_id)
    if not conv or conv.get("conversation_type") != "exam_analysis":
        raise HTTPException(status_code=400, detail="仅试题分析对话可订阅流")
    queue = await subscribe(conversation_id)

    async def event_stream():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    if event.get("type") == "stream_end":
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                except asyncio.CancelledError:
                    break
        finally:
            await unsubscribe(conversation_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{conversation_id}/exam_analysis/start", status_code=status.HTTP_202_ACCEPTED)
async def start_exam_analysis(conversation_id: str, background_tasks: BackgroundTasks):
    """启动试题分析（后台执行多智能体分析）"""
    conv = ConversationService().get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    if conv.get("conversation_type") != "exam_analysis":
        raise HTTPException(status_code=400, detail="仅试题分析对话可启动分析")
    from app.services.exam_analysis.orchestration import run_analysis
    background_tasks.add_task(run_analysis, conversation_id)
    return {"message": "分析已启动", "conversation_id": conversation_id}


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(conversation_id: str, request: ConversationUpdateRequest):
    """更新对话信息（重命名、置顶等）
    
    Args:
        conversation_id: 对话ID
        request: 更新请求（title、pinned）
    """
    service = ConversationService()
    
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话 {conversation_id} 不存在"
        )
    
    try:
        updated = service.update_conversation(
            conversation_id,
            title=request.title,
            pinned=request.pinned
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新对话失败"
            )
        
        conversation = service.get_conversation(conversation_id)
        return ConversationResponse(**conversation)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新对话失败: {str(e)}"
        )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: str):
    """删除对话及所有相关数据
    
    Args:
        conversation_id: 对话ID
    """
    service = ConversationService()
    
    conversation = service.get_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话 {conversation_id} 不存在"
        )
    
    success = service.delete_conversation(conversation_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除对话失败"
        )
    
    return None


# 消息历史相关API
class DocMessageRequest(BaseModel):
    """文档附件消息请求"""
    type: str  # 'doc-highlight' 或 'doc-image'
    filename: str
    page_number: int = Field(..., alias='pageNumber')
    file_extension: str = Field(..., alias='fileExtension')
    file_id: str = Field(..., alias='fileId')
    image_url: Optional[str] = Field(None, alias='imageUrl')  # 仅当 type 为 'doc-image' 时需要
    base_timestamp: Optional[str] = Field(None, alias='baseTimestamp')  # 基础时间戳（可选），用于确保多个 doc-* 消息按顺序排列
    
    class Config:
        populate_by_name = True  # 允许同时使用字段名和别名

class MessageRequest(BaseModel):
    query: str
    answer: str
    tool_calls: Optional[List[dict]] = None  # 工具调用信息（可选）
    stream_items: Optional[List[dict]] = None  # 流式输出项（工具调用和文本的混合顺序，可选）

class MessageResponse(BaseModel):
    role: str
    content: Optional[str] = ""  # 对于 doc-* 消息，content 可以为空
    timestamp: Optional[str] = None  # 对于 doc-* 消息，timestamp 可以为空
    streamItems: Optional[List[dict]] = None  # 流式输出项（工具调用和文本的混合顺序，可选）
    toolCalls: Optional[List[dict]] = None  # 工具调用信息（向后兼容，可选）
    # doc-* 消息的额外字段
    type: Optional[str] = None  # 'doc-highlight' 或 'doc-image'
    filename: Optional[str] = None
    pageNumber: Optional[int] = None
    fileExtension: Optional[str] = None
    fileId: Optional[str] = None
    imageUrl: Optional[str] = None  # 仅 doc-image 有

class MessagesResponse(BaseModel):
    messages: List[MessageResponse]

class MessageResetRequest(BaseModel):
    index: int = Field(..., ge=0, description="保留到的最后一条消息索引")


@router.get("/{conversation_id}/messages", response_model=MessagesResponse)
async def get_messages(conversation_id: str):
    """获取对话历史消息
    
    Args:
        conversation_id: 对话ID
    """
    service = ConversationService()
    
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话 {conversation_id} 不存在"
        )
    
    messages = service.get_messages(conversation_id)
    
    # 转换字段名：将 stream_items 转换为 streamItems，tool_calls 转换为 toolCalls（前端期望的格式）
    converted_messages = []
    for i, msg in enumerate(messages):
        converted_msg = msg.copy()
        msg_role = converted_msg.get('role', 'unknown')
        
        # 处理 doc-* 类型的消息（文档附件）
        if converted_msg.get('role') == 'system' and converted_msg.get('type') in ['doc-highlight', 'doc-image']:
            # doc-* 消息保持原样，不需要转换 tool_calls 和 stream_items
            # 但需要确保字段名符合前端期望（pageNumber 而不是 page_number）
            if 'page_number' in converted_msg:
                converted_msg['pageNumber'] = converted_msg['page_number']
                del converted_msg['page_number']
            if 'file_extension' in converted_msg:
                converted_msg['fileExtension'] = converted_msg['file_extension']
                del converted_msg['file_extension']
            if 'file_id' in converted_msg:
                converted_msg['fileId'] = converted_msg['file_id']
                del converted_msg['file_id']
            if 'image_url' in converted_msg:
                converted_msg['imageUrl'] = converted_msg['image_url']
                del converted_msg['image_url']
            # doc-* 消息不需要 streamItems 和 toolCalls
            converted_msg['streamItems'] = None
            converted_msg['toolCalls'] = None
            # 确保有 content 和 timestamp 字段（即使为空）
            if 'content' not in converted_msg:
                converted_msg['content'] = ""
            if 'timestamp' not in converted_msg or not converted_msg.get('timestamp'):
                converted_msg['timestamp'] = datetime.utcnow().isoformat() + "Z"
            converted_messages.append(converted_msg)
            continue
        
        # 如果存在 stream_items，添加 streamItems 别名（前端期望的字段名），并删除原始字段
        if 'stream_items' in converted_msg:
            converted_msg['streamItems'] = converted_msg['stream_items']
            del converted_msg['stream_items']
        # 如果存在 tool_calls，添加 toolCalls 别名（向后兼容），并删除原始字段
        if 'tool_calls' in converted_msg:
            converted_msg['toolCalls'] = converted_msg['tool_calls']
            del converted_msg['tool_calls']
        # 确保所有消息都包含 streamItems 和 toolCalls 字段（即使为 None），以便 Pydantic 正确序列化
        if 'streamItems' not in converted_msg:
            converted_msg['streamItems'] = None
        if 'toolCalls' not in converted_msg:
            converted_msg['toolCalls'] = None
        
        # 验证必需字段
        if 'role' not in converted_msg:
            print(f"⚠️ [API] 警告: 消息 {i+1} 缺少 role 字段")
        if 'content' not in converted_msg:
            print(f"⚠️ [API] 警告: 消息 {i+1} 缺少 content 字段")
        if 'timestamp' not in converted_msg:
            print(f"⚠️ [API] 警告: 消息 {i+1} 缺少 timestamp 字段")
            converted_msg['timestamp'] = datetime.utcnow().isoformat() + "Z"
        
        converted_messages.append(converted_msg)
    
    return MessagesResponse(
        messages=[MessageResponse(**msg) for msg in converted_messages]
    )


@router.post("/{conversation_id}/messages/doc", status_code=status.HTTP_201_CREATED)
async def save_doc_message(conversation_id: str, request: DocMessageRequest):
    """保存文档附件消息到对话历史
    
    Args:
        conversation_id: 对话ID
        request: 文档附件消息数据
    """
    service = ConversationService()
    
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话 {conversation_id} 不存在"
        )
    
    if request.type not in ["doc-highlight", "doc-image"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的消息类型: {request.type}，必须是 'doc-highlight' 或 'doc-image'"
        )
    
    success = service.add_doc_message(
        conversation_id,
        request.type,
        request.filename,
        request.page_number,
        request.file_extension,
        request.file_id,
        request.image_url,
        request.base_timestamp
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="保存文档消息失败"
        )
    
    return {"status": "success"}

@router.post("/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def save_message(conversation_id: str, request: MessageRequest):
    """保存消息到对话历史
    
    Args:
        conversation_id: 对话ID
        request: 包含 query 和 answer
    """
    service = ConversationService()
    
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话 {conversation_id} 不存在"
        )
    
    success = service.add_message(
        conversation_id, 
        request.query, 
        request.answer,
        tool_calls=request.tool_calls,
        stream_items=request.stream_items
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="保存消息失败"
        )
    
    return {"status": "success"}


@router.post("/{conversation_id}/messages/reset", status_code=status.HTTP_200_OK)
async def reset_messages(conversation_id: str, request: MessageResetRequest):
    """重置对话历史，保留指定索引之前的所有消息
    
    Args:
        conversation_id: 对话ID
        request: 包含 index 字段，表示保留到的最后一条消息索引
    """
    service = ConversationService()
    
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话 {conversation_id} 不存在"
        )
    
    success = service.reset_history(conversation_id, request.index)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="重置历史失败"
        )
    
    return {"status": "success"}


@router.get("/{conversation_id}/cheatsheet")
async def get_cheatsheet(conversation_id: str):
    service = ConversationService()
    if not service.get_conversation(conversation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    data = _load_cheatsheet(conversation_id)
    return {"exists": data is not None, "cheatsheet": data}


@router.patch("/{conversation_id}/cheatsheet")
async def update_cheatsheet(conversation_id: str, request: CheatsheetUpdateRequest):
    service = ConversationService()
    if not service.get_conversation(conversation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    data = _save_cheatsheet(
        conversation_id,
        {
            "content": request.content,
            "layout": request.layout.model_dump() if request.layout else None,
            "content_options": request.content_options.model_dump() if request.content_options else None,
            "language": request.language,
            "style": request.style,
            "user_prompt": request.user_prompt,
            "status": "saved",
        },
    )
    return {"status": "success", "cheatsheet": data}


@router.delete("/{conversation_id}/cheatsheet", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cheatsheet(conversation_id: str):
    service = ConversationService()
    if not service.get_conversation(conversation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    file_path = _cheatsheet_file(conversation_id)
    if file_path.exists():
        file_path.unlink()
    return None


@router.post("/{conversation_id}/cheatsheet/generate")
async def generate_cheatsheet(conversation_id: str, request: CheatsheetGenerateRequest, http_request: Request):
    service = ConversationService()
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    conv_subject_id = conversation.get("subject_id")
    if conv_subject_id != request.subject_id:
        # 兼容：历史对话可能未绑定 subject_id（为 None/空字符串），此时允许自动绑定后继续生成
        if not conv_subject_id:
            service.update_conversation(conversation_id, subject_id=request.subject_id)
            conversation = service.get_conversation(conversation_id) or conversation
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="subject 与当前对话不匹配")
    if not request.document_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择至少一个讲义文档")

    doc_service = DocumentService()
    subject_docs = {doc["file_id"]: doc for doc in doc_service.list_documents_for_subject(request.subject_id)}
    selected_docs = []
    for document_id in request.document_ids:
        doc = subject_docs.get(document_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"文档不存在: {document_id}")
        if doc.get("status") != "completed":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"文档尚未处理完成: {doc.get('filename')}")
        ext = (doc.get("file_extension") or "").strip().lower()
        ext = ext.lstrip(".")
        if ext not in ("pdf", "pptx"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cheatsheet 仅支持 PDF / PPTX 讲义: {doc.get('filename')}",
            )
        file_path = doc_service.file_manager.get_file_path_for_subject(request.subject_id, document_id)
        if not file_path or not file_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"文档文件不存在: {doc.get('filename')}")
        selected_docs.append((doc, file_path))

    chat_config = config_service.get_config("chat")
    api_key = chat_config.get("api_key")
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chat LLM API Key 未配置")

    async def event_stream():
        def emit(event: str, payload: Dict[str, Any]):
            return f"data: {json.dumps({'event': event, **payload}, ensure_ascii=False)}\n\n"

        async def should_stop() -> bool:
            try:
                return await http_request.is_disconnected()
            except Exception:
                return False

        try:
            if await should_stop():
                return
            yield emit("progress", {"message": "正在读取讲义", "current": 0, "total": len(selected_docs)})
            generation_jobs = []
            for doc_index, (doc, file_path) in enumerate(selected_docs, 1):
                if await should_stop():
                    return
                yield emit("progress", {"message": f"正在解析 {doc['filename']}", "current": doc_index, "total": len(selected_docs)})
                text = (doc_service.document_parser.extract_text(str(file_path), file_id=doc["file_id"]) or "").strip()
                if not text:
                    yield emit("warning", {"message": f"{doc['filename']} 未提取到文本，已跳过"})
                    continue

                chunks = _chunk_text(text)
                for chunk_index, chunk in enumerate(chunks, 1):
                    generation_jobs.append({
                        "filename": doc["filename"],
                        "file_id": doc["file_id"],
                        "chunk_index": chunk_index,
                        "total_chunks": len(chunks),
                        "text": chunk,
                    })

            if not generation_jobs:
                yield emit("error", {"message": "没有可用于生成 cheatsheet 的讲义文本"})
                return

            layout = request.layout.model_dump()
            options = request.content_options.model_dump()
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            url = f"{chat_config.get('host', '').rstrip('/')}/chat/completions"

            async def stream_llm(client: httpx.AsyncClient, prompt_text: str):
                if await should_stop():
                    return
                payload = {
                    "model": chat_config.get("model"),
                    "messages": [
                        {"role": "system", "content": "你只输出 Markdown cheatsheet 内容；禁止代码围栏；必须保留原文有效内容。"},
                        {"role": "user", "content": prompt_text},
                    ],
                    "stream": True,
                    "temperature": 0.05,
                    "max_tokens": 8192,
                }
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code >= 400:
                        error_text = await response.aread()
                        raise RuntimeError(f"LLM API 错误: {response.status_code}, {error_text.decode('utf-8', errors='replace')[:500]}")
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if raw == "[DONE]":
                            break
                        try:
                            data = json.loads(raw)
                            delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        except Exception:
                            delta = ""
                        if delta:
                            yield delta
                        if await should_stop():
                            return

            faithful_mode = request.style in ("faithful", "auto")
            if faithful_mode:
                content_parts = []
                page_jobs = []
                for doc, file_path in selected_docs:
                    if await should_stop():
                        return
                    text = (doc_service.document_parser.extract_text(str(file_path), file_id=doc["file_id"]) or "").strip()
                    for page in _extract_pdf_pages(text):
                        page_jobs.append({"doc": doc, "page": page})

                if not page_jobs:
                    yield emit("error", {"message": "没有可用于逐页转写的讲义文本"})
                    return

                async with httpx.AsyncClient(timeout=config.settings.timeout) as client:
                    for page_index, job in enumerate(page_jobs, 1):
                        if await should_stop():
                            return
                        doc = job["doc"]
                        page = job["page"]
                        heading = f"\n\n## Page {page.get('page', '?')} [FILE:{page.get('file_id', '')}][PAGE:{page.get('page', '?')}]\n\n"
                        content_parts.append(heading)
                        yield emit("chunk", {"content": heading})
                        yield emit(
                            "progress",
                            {
                                "message": f"正在用 LLM 逐页转写 {doc['filename']} 第 {page.get('page', '?')} 页",
                                "current": page_index,
                                "total": len(page_jobs),
                            },
                        )

                        page_parts = []
                        prompt = _build_faithful_page_prompt(doc["filename"], page, request)
                        try:
                            async for delta in stream_llm(client, prompt):
                                if await should_stop():
                                    return
                                page_parts.append(delta)
                                content_parts.append(delta)
                                yield emit("chunk", {"content": delta})
                        except RuntimeError as exc:
                            yield emit("error", {"message": str(exc)})
                            return

                        missing = _build_faithful_missing_lines(page, "".join(page_parts))
                        if missing:
                            content_parts.append(missing)
                            yield emit("chunk", {"content": missing})

                content = "".join(content_parts).strip()
                saved = _save_cheatsheet(
                    conversation_id,
                    {
                        "status": "completed",
                        "content": content,
                        "layout": layout,
                        "content_options": options,
                        "language": request.language,
                        "style": request.style,
                        "user_prompt": request.user_prompt,
                        "document_ids": request.document_ids,
                        "documents": [{"file_id": doc["file_id"], "filename": doc["filename"]} for doc, _ in selected_docs],
                    },
                )
                yield emit("done", {"cheatsheet": saved})
                return

            content_parts = []
            total_jobs = len(generation_jobs)

            async with httpx.AsyncClient(timeout=config.settings.timeout) as client:
                for job_index, job in enumerate(generation_jobs, 1):
                    if await should_stop():
                        return
                    heading = f"\n\n## {job['filename']} - Part {job['chunk_index']}/{job['total_chunks']}\n\n"
                    content_parts.append(heading)
                    yield emit("chunk", {"content": heading})
                    yield emit(
                        "progress",
                        {
                            "message": f"正在生成 {job['filename']} 第 {job['chunk_index']}/{job['total_chunks']} 段",
                            "current": job_index,
                            "total": total_jobs,
                        },
                    )

                    try:
                        prompt = _build_cheatsheet_chunk_prompt(
                            job["filename"],
                            job["text"],
                            job["chunk_index"],
                            job["total_chunks"],
                            request,
                        )
                        chunk_parts = []
                        async for delta in stream_llm(client, prompt):
                            if await should_stop():
                                return
                            chunk_parts.append(delta)
                            content_parts.append(delta)
                            yield emit("chunk", {"content": delta})
                        chunk_output = "".join(chunk_parts)
                        # Very short outputs are usually accidental summaries. Ask once more for omissions.
                        if len(chunk_output.strip()) < max(900, len(job["text"]) * 0.45):
                            backfill_heading = "\n\n### 补漏扩写\n\n"
                            content_parts.append(backfill_heading)
                            yield emit("chunk", {"content": backfill_heading})
                            yield emit("progress", {"message": f"正在补漏扩写 {job['filename']} 第 {job['chunk_index']}/{job['total_chunks']} 段", "current": job_index, "total": total_jobs})
                            backfill_prompt = _build_cheatsheet_backfill_prompt(job["filename"], job["text"], chunk_output, request)
                            async for delta in stream_llm(client, backfill_prompt):
                                if await should_stop():
                                    return
                                content_parts.append(delta)
                                yield emit("chunk", {"content": delta})
                    except RuntimeError as exc:
                        yield emit("error", {"message": str(exc)})
                        return

            content = "".join(content_parts).strip()
            if not content:
                yield emit("error", {"message": "LLM 未返回 cheatsheet 内容"})
                return

            saved = _save_cheatsheet(
                conversation_id,
                {
                    "status": "completed",
                    "content": content,
                    "layout": layout,
                    "content_options": options,
                    "language": request.language,
                    "style": request.style,
                    "user_prompt": request.user_prompt,
                    "document_ids": request.document_ids,
                    "documents": [{"file_id": doc["file_id"], "filename": doc["filename"]} for doc, _ in selected_docs],
                },
            )
            yield emit("done", {"cheatsheet": saved})
        except Exception as exc:
            yield emit("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{conversation_id}/cheatsheet/pdf")
async def export_cheatsheet_pdf(conversation_id: str, request: CheatsheetPdfRequest):
    service = ConversationService()
    if not service.get_conversation(conversation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")

    saved = _load_cheatsheet(conversation_id) or {}
    content_md = _normalize_cheatsheet_soft_breaks(
        request.content if request.content is not None else saved.get("content") or ""
    ).strip()
    if not content_md:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="暂无 cheatsheet 内容可导出")

    layout = (request.layout.model_dump() if request.layout else (saved.get("layout") or CheatsheetLayout().model_dump()))
    paper_type = layout.get("paper_type", "A4")
    orientation = layout.get("orientation", "portrait")
    font_size = int(layout.get("font_size", 10))
    line_height = float(layout.get("line_height", 1.2))
    margin_mm = int(layout.get("margin_mm", layout.get("margin", 8) if isinstance(layout.get("margin"), int) else 8))
    columns = int(layout.get("columns", 2))

    html_body = (request.html or "").strip()
    if not html_body:
        try:
            import markdown as md
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Markdown 渲染依赖缺失: {exc}")

        html_body = md.markdown(
            content_md,
            extensions=["tables", "fenced_code", "sane_lists", "toc"],
            output_format="html5",
        )

    # 纸张尺寸（mm）
    paper_mm = {
        "A4": (210, 297),
        "Letter": (216, 279),
        "A5": (148, 210),
    }.get(paper_type, (210, 297))
    page_w, page_h = paper_mm
    if orientation == "landscape":
        page_w, page_h = page_h, page_w
    column_count = max(1, columns)

    # 纯打印页面（避免带入应用 UI）。后续通过 Playwright 显式生成每一页，
    # 与前端预览的“横向多栏带 + 裁切”分页逻辑保持一致。
    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>cheatsheet</title>
  <style>
    @page {{
      size: {page_w}mm {page_h}mm;
      margin: 0;
    }}
    html, body {{
      padding: 0;
      margin: 0;
      background: #fff;
      color: #111827;
    }}
    body {{
      font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, "Noto Sans", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      font-size: {font_size}px;
      line-height: {line_height};
    }}
    #pages {{
      background: #fff;
    }}
    .cheatsheet-page {{
      box-sizing: border-box;
      width: {page_w}mm;
      height: {page_h}mm;
      padding: {margin_mm}mm;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      background: #fff;
      break-after: page;
      page-break-after: always;
    }}
    .cheatsheet-page:last-child {{
      break-after: auto;
      page-break-after: auto;
    }}
    .cheatsheet-flow-slice {{
      flex: 1 1 auto;
      overflow: hidden;
      position: relative;
    }}
    .cheatsheet-page-content {{
      text-align: justify;
      font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, "Noto Sans", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      font-size: {font_size}px;
      line-height: {line_height};
      word-break: break-word;
      overflow-wrap: anywhere;
    }}
    .cheatsheet-flow-content {{
      column-count: {column_count};
      column-gap: 12px;
      column-fill: auto;
      overflow: visible;
    }}
    #measure-page {{
      position: absolute;
      left: -99999px;
      top: 0;
      visibility: hidden;
      pointer-events: none;
    }}
    #measure {{
      overflow-x: auto;
      overflow-y: hidden;
    }}
    .cheatsheet-page-number {{
      flex: 0 0 auto;
      height: 18px;
      line-height: 18px;
      margin-top: 0;
      color: #6b7280;
      font-size: 10px;
      text-align: center;
    }}
    h1,h2,h3 {{
      margin: 0 0 0.55em;
      line-height: 1.15;
      font-family: "Merriweather", Georgia, "Times New Roman", "Noto Serif SC", serif;
      font-weight: 700;
      color: #1A1A1A;
    }}
    p,ul,ol,table {{
      margin-top: 0;
      margin-bottom: 0.65em;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      table-layout: fixed;
    }}
    th,td {{
      border: 1px solid #d1d5db;
      padding: 3px 5px;
      vertical-align: top;
      word-break: break-word;
      overflow-wrap: anywhere;
    }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
    code {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
  </style>
</head>
<body>
  <section id="measure-page" class="cheatsheet-page">
    <div id="measure-frame" class="cheatsheet-flow-slice">
      <div id="measure" class="cheatsheet-page-content cheatsheet-flow-content">
        {html_body}
      </div>
    </div>
    <div class="cheatsheet-page-number">Page 0</div>
  </section>
  <main id="pages"></main>
</body>
</html>"""

    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Playwright 依赖缺失: {exc}")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html, wait_until="load")
        await page.evaluate(
            """() => {
                const measurePage = document.getElementById('measure-page');
                const measureFrame = document.getElementById('measure-frame');
                const source = document.getElementById('measure');
                const pagesRoot = document.getElementById('pages');
                if (!measurePage || !measureFrame || !source || !pagesRoot) return;

                const columnGap = 12;
                const frameRect = measureFrame.getBoundingClientRect();
                const innerW = Math.max(80, frameRect.width);
                const innerH = Math.max(80, frameRect.height);

                source.style.width = `${innerW}px`;
                source.style.height = `${innerH}px`;

                const totalW = Math.max(innerW, source.scrollWidth || 0);
                const pageStride = innerW + columnGap;
                const pageCount = Math.max(1, Math.ceil((totalW + columnGap) / pageStride));
                const sourceHtml = source.innerHTML;

                pagesRoot.innerHTML = '';
                for (let i = 0; i < pageCount; i += 1) {
                    const pageEl = document.createElement('section');
                    pageEl.className = 'cheatsheet-page';

                    const sliceEl = document.createElement('div');
                    sliceEl.className = 'cheatsheet-flow-slice';
                    sliceEl.style.width = `${innerW}px`;
                    sliceEl.style.height = `${innerH}px`;

                    const flowEl = document.createElement('div');
                    flowEl.className = 'cheatsheet-page-content cheatsheet-flow-content';
                    flowEl.style.width = `${innerW}px`;
                    flowEl.style.height = `${innerH}px`;
                    flowEl.style.transform = `translateX(-${i * pageStride}px)`;
                    flowEl.style.transformOrigin = 'top left';
                    flowEl.innerHTML = sourceHtml;

                    const pageNumberEl = document.createElement('div');
                    pageNumberEl.className = 'cheatsheet-page-number';
                    pageNumberEl.textContent = `Page ${i + 1}`;

                    sliceEl.appendChild(flowEl);
                    pageEl.appendChild(sliceEl);
                    pageEl.appendChild(pageNumberEl);
                    pagesRoot.appendChild(pageEl);
                }

                measurePage.remove();
            }"""
        )
        await page.emulate_media(media="print")
        pdf_bytes = await page.pdf(
            width=f"{page_w}mm",
            height=f"{page_h}mm",
            print_background=True,
            margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
            prefer_css_page_size=True,
        )
        await browser.close()

    filename = f"cheatsheet-{conversation_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
