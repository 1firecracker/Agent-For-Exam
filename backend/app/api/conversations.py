"""对话管理 API"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse
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


def _cheatsheet_file(conversation_id: str) -> Path:
    return Path(config.settings.conversations_dir) / conversation_id / "cheatsheet.json"


def _load_cheatsheet(conversation_id: str) -> Optional[Dict[str, Any]]:
    file_path = _cheatsheet_file(conversation_id)
    if not file_path.exists():
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
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


def _build_cheatsheet_prompt(
    documents: List[Dict[str, str]],
    request: CheatsheetGenerateRequest,
) -> str:
    options = request.content_options
    layout = request.layout
    doc_text = "\n\n".join(
        f"## 文档：{doc['filename']}\n{doc['text']}" for doc in documents
    )
    custom_prompt = request.user_prompt.strip() if request.user_prompt else "请生成适合考试复习的 cheatsheet。"
    return f"""你是考试复习 cheatsheet 编写助手。请严格基于以下讲义内容生成 Markdown cheatsheet，不要编造讲义外信息。

用户提示词：
{custom_prompt}

生成风格：{request.style}
语言偏好：{request.language}（auto 表示默认使用讲义主要语言）
内容密度：{options.density}
排版约束：纸张 {layout.paper_type}，方向 {layout.orientation}，字号 {layout.font_size}px，{layout.columns} 栏。
内容选项：
- 包含公式：{options.include_formulas}
- 包含定义：{options.include_definitions}
- 包含算法步骤：{options.include_algorithms}
- 包含例题提示：{options.include_examples}
- 包含页码引用：{options.include_page_refs}

输出要求：
- 只输出 Markdown 内容。
- 优先短句、列表、表格和公式块，适配高密度打印。
- 如能判断页码，请保留文件名和页码引用。
- 如果讲义内容不足以支持某项内容，请省略该项，不要补写。

讲义内容：
{doc_text}
"""


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
async def generate_cheatsheet(conversation_id: str, request: CheatsheetGenerateRequest):
    service = ConversationService()
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    if conversation.get("subject_id") != request.subject_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="subject 与当前对话不匹配")
    if not request.document_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择至少一个 PDF 讲义文档")

    doc_service = DocumentService()
    subject_docs = {doc["file_id"]: doc for doc in doc_service.list_documents_for_subject(request.subject_id)}
    selected_docs = []
    for document_id in request.document_ids:
        doc = subject_docs.get(document_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"文档不存在: {document_id}")
        if doc.get("status") != "completed":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"文档尚未处理完成: {doc.get('filename')}")
        if doc.get("file_extension") != "pdf":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cheatsheet MVP 仅支持 PDF 讲义: {doc.get('filename')}")
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

        try:
            yield emit("progress", {"message": "正在读取 PDF 讲义", "current": 0, "total": len(selected_docs)})
            doc_sections = []
            for index, (doc, file_path) in enumerate(selected_docs, 1):
                yield emit("progress", {"message": f"正在解析 {doc['filename']}", "current": index, "total": len(selected_docs)})
                text = doc_service.document_parser.extract_text(str(file_path), file_id=doc["file_id"])
                text = (text or "").strip()
                if not text:
                    yield emit("warning", {"message": f"{doc['filename']} 未提取到文本，已跳过"})
                    continue
                doc_sections.append(f"=== {doc['filename']} ({doc['file_id']}) ===\n{text[:18000]}")

            if not doc_sections:
                yield emit("error", {"message": "没有可用于生成 cheatsheet 的 PDF 文本"})
                return

            options = request.content_options.model_dump()
            layout = request.layout.model_dump()
            prompt = f"""
你是考试速查表生成助手。请严格基于用户选择的 PDF 讲义生成 cheatsheet，输出 Markdown。

要求：
- 默认使用讲义主要语言；如果 language 不是 auto，则遵循 language={request.language}
- 风格 style={request.style}，用户提示词优先：{request.user_prompt or "无"}
- 内容密度 density={options["density"]}
- 是否包含公式={options["include_formulas"]}，定义={options["include_definitions"]}，算法步骤={options["include_algorithms"]}，例题提示={options["include_examples"]}，页码引用={options["include_page_refs"]}
- 适配密集排版：短句、列表、表格优先，避免长段落
- 不要编造讲义中不存在的信息
- 若能识别页码，请用 [文件名 p.X] 形式标注引用

排版参数仅供内容密度参考：{json.dumps(layout, ensure_ascii=False)}

讲义内容：
{chr(10).join(doc_sections)}
""".strip()

            payload = {
                "model": chat_config.get("model"),
                "messages": [
                    {"role": "system", "content": "你只输出可直接放入 cheatsheet 的 Markdown 内容。"},
                    {"role": "user", "content": prompt},
                ],
                "stream": True,
                "temperature": 0.2,
            }
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            url = f"{chat_config.get('host', '').rstrip('/')}/chat/completions"
            content_parts = []
            yield emit("progress", {"message": "正在调用 LLM 生成 cheatsheet", "current": len(selected_docs), "total": len(selected_docs)})

            async with httpx.AsyncClient(timeout=config.settings.timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code >= 400:
                        error_text = await response.aread()
                        yield emit("error", {"message": f"LLM API 错误: {response.status_code}, {error_text.decode('utf-8', errors='replace')[:500]}"})
                        return
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
                            content_parts.append(delta)
                            yield emit("chunk", {"content": delta})

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

