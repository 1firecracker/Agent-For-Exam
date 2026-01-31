"""对话管理 API"""
import asyncio
import json
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.conversation_service import ConversationService

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
                    if event.get("type") == "stream_end":
                        break
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
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
class MessageRequest(BaseModel):
    query: str
    answer: str
    tool_calls: Optional[List[dict]] = None  # 工具调用信息（可选）
    stream_items: Optional[List[dict]] = None  # 流式输出项（工具调用和文本的混合顺序，可选）

class MessageResponse(BaseModel):
    role: str
    content: str
    timestamp: str
    streamItems: Optional[List[dict]] = None  # 流式输出项（工具调用和文本的混合顺序，可选）
    toolCalls: Optional[List[dict]] = None  # 工具调用信息（向后兼容，可选）

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
    # print(f"📥 [API] 获取到 {len(messages)} 条消息")  # 调试日志已关闭
    
    # 转换字段名：将 stream_items 转换为 streamItems，tool_calls 转换为 toolCalls（前端期望的格式）
    converted_messages = []
    for i, msg in enumerate(messages):
        converted_msg = msg.copy()
        msg_role = converted_msg.get('role', 'unknown')
        # print(f"📝 [API] 处理消息 {i+1}/{len(messages)}: role={msg_role}, content长度={len(str(converted_msg.get('content', '')))}")  # 调试日志已关闭
        
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
        
        converted_messages.append(converted_msg)
    
    # print(f"✅ [API] 转换完成，共 {len(converted_messages)} 条消息")  # 调试日志已关闭
    
    return MessagesResponse(
        messages=[MessageResponse(**msg) for msg in converted_messages]
    )


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

