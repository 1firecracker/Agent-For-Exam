"""知识图谱查询 API"""
import json
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.graph_service import GraphService
from app.services.memory_service import MemoryService
from app.config import get_logger

router = APIRouter(tags=["graph"])
logger = get_logger("app.graph")

# 请求/响应模型
class QueryRequest(BaseModel):
    query: str
    mode: Optional[str] = "naive"  # naive/local/global/mix/agent

class QueryResponse(BaseModel):
    conversation_id: str
    query: str
    mode: str
    result: str

class SourceDocument(BaseModel):
    """来源文档信息"""
    file_id: str
    filename: str
    file_type: str

class EntityResponse(BaseModel):
    entity_id: str
    name: str
    type: str
    description: str
    source_id: Optional[str] = None
    file_path: Optional[str] = None
    source_documents: List[SourceDocument] = []  # 来源文档列表

class RelationResponse(BaseModel):
    relation_id: str
    source: str
    target: str
    type: str
    description: str

class GraphResponse(BaseModel):
    entities: List[EntityResponse]
    relations: List[RelationResponse]
    total_entities: int
    total_relations: int

class GraphStatusResponse(BaseModel):
    """知识图谱状态响应"""
    is_ready: bool  # 是否完全生成完成
    total_documents: int  # 总文档数
    completed_documents: int  # 已完成文档数
    processing_documents: int  # 处理中文档数
    pending_documents: int  # 等待处理文档数
    failed_documents: int  # 失败文档数


@router.get("/api/conversations/{conversation_id}/graph/status",
            response_model=GraphStatusResponse)
async def get_graph_status(conversation_id: str):
    """检查知识图谱生成状态
    
    Args:
        conversation_id: 对话ID
        
    Returns:
        知识图谱状态信息
    """
    from app.services.document_service import DocumentService
    
    doc_service = DocumentService()
    documents = doc_service.list_documents(conversation_id)
    
    total = len(documents)
    completed = 0
    processing = 0
    pending = 0
    failed = 0
    
    for doc in documents:
        status = doc.get("status", "pending")
        if status == "completed":
            completed += 1
        elif status == "processing":
            processing += 1
        elif status == "failed":
            failed += 1
        else:
            pending += 1
    
    # 只有当所有文档都完成时，知识图谱才算完全生成
    is_ready = total > 0 and completed == total
    
    return GraphStatusResponse(
        is_ready=is_ready,
        total_documents=total,
        completed_documents=completed,
        processing_documents=processing,
        pending_documents=pending,
        failed_documents=failed
    )


@router.get("/api/conversations/{conversation_id}/graph",
            response_model=GraphResponse)
async def get_graph(conversation_id: str):
    """获取对话的所有实体和关系
    
    Args:
        conversation_id: 对话ID
    """
    service = GraphService()
    
    try:
        entities = await service.get_all_entities(conversation_id)
        relations = await service.get_all_relations(conversation_id)
        
        # 转换实体数据，包括来源文档
        entity_responses = []
        for entity in entities:
            source_docs = [
                SourceDocument(**doc) for doc in entity.get("source_documents", [])
            ]
            entity_responses.append(EntityResponse(
                entity_id=entity["entity_id"],
                name=entity["name"],
                type=entity["type"],
                description=entity.get("description", ""),
                source_id=entity.get("source_id"),
                file_path=entity.get("file_path"),
                source_documents=source_docs
            ))
        
        return GraphResponse(
            entities=entity_responses,
            relations=[RelationResponse(**relation) for relation in relations],
            total_entities=len(entities),
            total_relations=len(relations)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取知识图谱失败: {str(e)}"
        )


@router.get("/api/conversations/{conversation_id}/graph/entities/{entity_id}",
            response_model=EntityResponse)
async def get_entity(conversation_id: str, entity_id: str):
    """获取单个实体详情
    
    Args:
        conversation_id: 对话ID
        entity_id: 实体ID
    """
    service = GraphService()
    
    entity = await service.get_entity_detail(conversation_id, entity_id)
    
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"实体 {entity_id} 不存在"
        )
    
    # 转换来源文档
    source_docs = [
        SourceDocument(**doc) for doc in entity.get("source_documents", [])
    ]
    
    return EntityResponse(
        entity_id=entity["entity_id"],
        name=entity["name"],
        type=entity["type"],
        description=entity.get("description", ""),
        source_id=entity.get("source_id"),
        file_path=entity.get("file_path"),
        source_documents=source_docs
    )


@router.get("/api/conversations/{conversation_id}/graph/relations",
            response_model=RelationResponse)
async def get_relation(
    conversation_id: str,
    source: str = Query(..., description="源实体ID"),
    target: str = Query(..., description="目标实体ID")
):
    """获取单个关系详情
    
    Args:
        conversation_id: 对话ID
        source: 源实体ID
        target: 目标实体ID
    """
    service = GraphService()
    
    relation = await service.get_relation_detail(conversation_id, source, target)
    
    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"关系 {source} -> {target} 不存在"
        )
    
    return RelationResponse(**relation)


@router.post("/api/conversations/{conversation_id}/query",
            response_model=QueryResponse)
async def query_knowledge_graph(conversation_id: str, request: QueryRequest):
    """在对话的知识图谱中查询（非流式）
    
    支持不同的查询模式：
    - naive: 基础查询
    - local: 本地图谱查询
    - global: 全局查询
    - mix: 混合查询（默认）
    
    Args:
        conversation_id: 对话ID
        request: 查询请求（包含 query 和 mode）
    """
    service = GraphService()
    
    # 验证查询模式
    valid_modes = ["naive", "local", "global", "mix"]
    if request.mode not in valid_modes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的查询模式: {request.mode}，支持的模式: {', '.join(valid_modes)}"
        )
    
    try:
        # 获取历史对话并计算 token（减少到3轮，并限制单条消息长度）
        memory_service = MemoryService()
        history = memory_service.get_recent_history(conversation_id, max_turns=3, max_tokens_per_message=500)
        token_stats = memory_service.calculate_input_tokens(request.query, history, request.mode)
        logger.debug(
            "知识图谱查询 token 统计",
            extra={
                "event": "graph.token_stats",
                "conversation_id": conversation_id,
                "mode": token_stats.get("mode"),
                "query_tokens": token_stats.get("query_tokens"),
                "history_tokens": token_stats.get("history_tokens"),
                "total_input_tokens": token_stats.get("total_input_tokens"),
            },
        )
        
        result = await service.query(conversation_id, request.query, request.mode)
        
        return QueryResponse(
            conversation_id=conversation_id,
            query=request.query,
            mode=request.mode,
            result=result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询失败: {str(e)}"
        )


@router.post("/api/conversations/{conversation_id}/query/stream")
async def query_knowledge_graph_stream(conversation_id: str, request: QueryRequest):
    """流式查询知识图谱（支持逐字显示）
    
    支持不同的查询模式：
    - naive: 基础查询
    - local: 本地图谱查询
    - global: 全局查询
    - mix: 混合查询（默认）
    
    当知识图谱为空或查询未匹配到相关内容时，会自动降级到 LLM 直接回答，并显示提示。
    
    Args:
        conversation_id: 对话ID
        request: 查询请求（包含 query 和 mode）
        
    Returns:
        StreamingResponse: NDJSON 格式的流式响应
        - 每行一个 JSON 对象：{"response": "chunk"} 或 {"warning": "message"}
        - 错误时：{"error": "error message"}
    """
    service = GraphService()
    memory_service = MemoryService()
    
    # 获取历史对话（减少到3轮，并限制单条消息长度）
    history = memory_service.get_recent_history(conversation_id, max_turns=3, max_tokens_per_message=500)
    
    # 计算输入 token
    token_stats = memory_service.calculate_input_tokens(request.query, history, request.mode)
    logger.debug(
        "知识图谱流式查询 token 统计",
        extra={
            "event": "graph.token_stats_stream",
            "conversation_id": conversation_id,
            "mode": token_stats.get("mode"),
            "query_tokens": token_stats.get("query_tokens"),
            "history_tokens": token_stats.get("history_tokens"),
            "total_input_tokens": token_stats.get("total_input_tokens"),
        },
    )
    
    # 检查是否是 Agent 模式
    if request.mode == "agent":
        # 使用 Agent 服务处理
        from app.services.agent.agent_service import AgentService
        
        agent_service = AgentService()
        
        async def agent_stream():
            try:
                async for chunk in agent_service.process_user_query(
                    conversation_id,
                    request.query,
                    conversation_history=history
                ):
                    # 格式化输出
                    if chunk["type"] == "tool_call":
                        # tool_call 事件：发送 tool_call 对象
                        yield f"{json.dumps({'tool_call': chunk.get('tool_call')})}\n"
                    elif chunk["type"] == "tool_result":
                        yield f"{json.dumps({'tool_result': chunk})}\n"
                    elif chunk["type"] == "tool_error":
                        yield f"{json.dumps({'tool_error': chunk})}\n"
                    elif chunk["type"] == "tool_progress":
                        yield f"{json.dumps({'tool_progress': chunk})}\n"
                    elif chunk["type"] == "mindmap_content":
                        yield f"{json.dumps({'mindmap_content': chunk['content']})}\n"
                    elif chunk["type"] == "response":
                        yield f"{json.dumps({'response': chunk['content']})}\n"
                    elif chunk["type"] == "error":
                        yield f"{json.dumps({'error': chunk['content']})}\n"
            except Exception as e:
                error_msg = str(e)
                if "401" in error_msg or "Invalid token" in error_msg or "Unauthorized" in error_msg:
                    error_msg = "API Key 无效或已过期，请在设置中检查并更新 API Key"
                yield f"{json.dumps({'error': error_msg})}\n"
        
        return StreamingResponse(
            agent_stream(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    # 验证查询模式（排除 bypass 模式和 agent 模式）
    valid_modes = ["naive", "local", "global", "mix"]
    if request.mode not in valid_modes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的查询模式: {request.mode}，支持的模式: {', '.join(valid_modes + ['agent'])}"
        )
    
    # 第一层：快速检查是否有文档（无需初始化 LightRAG）
    if not service.check_has_documents_fast(conversation_id):
        # 快速路径：直接使用 bypass 模式，无需初始化 LightRAG 和检查知识图谱
        async def fast_bypass_stream():
            try:
                # 发送警告提示
                warning_message = "[未上传文档 ,直接给出回答]"
                yield f"{json.dumps({'warning': warning_message})}\n"
                # 发送换行
                newline_text = '\n\n'
                yield f"{json.dumps({'response': newline_text})}\n"
                
                # 初始化 LightRAG（仅用于 bypass 模式，无需检查知识图谱）
                lightrag = await service.lightrag_service.get_lightrag_for_conversation(conversation_id)
                from lightrag import QueryParam
                
                # 临时替换 LLM 函数为聊天配置（用于查询）
                original_llm_func = lightrag.llm_model_func
                chat_llm_func = service.lightrag_service.get_chat_llm_func()
                lightrag.llm_model_func = chat_llm_func
                
                # 使用 bypass 模式查询（包含历史对话）
                bypass_param = QueryParam(mode="bypass", stream=True)
                if history:
                    bypass_param.conversation_history = history
                try:
                    bypass_result = await lightrag.aquery_llm(request.query, param=bypass_param)
                except Exception as e:
                    error_msg = str(e)
                    if "401" in error_msg or "Invalid token" in error_msg or "Unauthorized" in error_msg:
                        error_msg = "API Key 无效或已过期，请在设置中检查并更新 API Key"
                    yield f"{json.dumps({'error': error_msg})}\n"
                    return
                
                # 恢复原始的 LLM 函数（用于文档抽取）
                lightrag.llm_model_func = original_llm_func
                
                # 检查是否有错误状态
                if bypass_result.get("status") == "failure":
                    error_msg = bypass_result.get("message", "查询失败")
                    if "401" in error_msg or "Invalid token" in error_msg or "Unauthorized" in error_msg:
                        error_msg = "API Key 无效或已过期，请在设置中检查并更新 API Key"
                    yield f"{json.dumps({'error': error_msg})}\n"
                    return
                
                llm_response = bypass_result.get("llm_response", {})
                
                # 流式发送响应
                if llm_response.get("is_streaming"):
                    response_stream = llm_response.get("response_iterator")
                    if response_stream:
                        try:
                            async for chunk in response_stream:
                                if chunk:
                                    yield f"{json.dumps({'response': chunk})}\n"
                        except Exception as e:
                            error_msg = str(e)
                            if "401" in error_msg or "Invalid token" in error_msg or "Unauthorized" in error_msg:
                                error_msg = "API Key 无效或已过期，请在设置中检查并更新 API Key"
                            yield f"{json.dumps({'error': error_msg})}\n"
                    else:
                        content = llm_response.get("content", "")
                        if content:
                            yield f"{json.dumps({'response': content})}\n"
                else:
                    content = llm_response.get("content", "")
                    if content:
                        yield f"{json.dumps({'response': content})}\n"
                    else:
                        yield f"{json.dumps({'error': 'No response generated'})}\n"
            except Exception as e:
                error_msg = str(e)
                if "401" in error_msg or "Invalid token" in error_msg or "Unauthorized" in error_msg:
                    error_msg = "API Key 无效或已过期，请在设置中检查并更新 API Key"
                yield f"{json.dumps({'error': error_msg})}\n"
        
        return StreamingResponse(
            fast_bypass_stream(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    # 第二层：有文档，进入正常流程（包含知识图谱检查）
    async def stream_generator():
        try:
            # 步骤1：查询前检测知识图谱是否为空
            kg_empty_before, error_msg = await service.check_knowledge_graph_empty(conversation_id)
            
            if error_msg:
                # 检测出错，显示错误信息
                yield f"{json.dumps({'error': error_msg})}\n"
                return
            
            lightrag = await service.lightrag_service.get_lightrag_for_conversation(conversation_id)
            from lightrag import QueryParam
            
            # 如果查询前知识图谱为空，直接使用 bypass 模式，跳过查询
            if kg_empty_before:
                # 直接发送警告提示并使用 bypass 模式
                warning_message = "⚠️ 未检索到相关文档，将基于通用知识回答："
                yield f"{json.dumps({'warning': warning_message})}\n"
                # 发送换行（不能在 f-string 表达式中使用反斜杠）
                newline_text = '\n\n'
                yield f"{json.dumps({'response': newline_text})}\n"
                
                # 临时替换 LLM 函数为聊天配置（用于查询）
                original_llm_func = lightrag.llm_model_func
                chat_llm_func = service.lightrag_service.get_chat_llm_func()
                lightrag.llm_model_func = chat_llm_func
                
                # 直接使用 bypass 模式查询（包含历史对话）
                bypass_param = QueryParam(mode="bypass", stream=True)
                if history:
                    bypass_param.conversation_history = history
                try:
                    bypass_result = await lightrag.aquery_llm(request.query, param=bypass_param)
                except Exception as e:
                    error_msg = str(e)
                    if "401" in error_msg or "Invalid token" in error_msg or "Unauthorized" in error_msg:
                        error_msg = "API Key 无效或已过期，请在设置中检查并更新 API Key"
                    yield f"{json.dumps({'error': error_msg})}\n"
                    return
                
                # 恢复原始的 LLM 函数（用于文档抽取）
                lightrag.llm_model_func = original_llm_func
                
                # 检查是否有错误状态
                if bypass_result.get("status") == "failure":
                    error_msg = bypass_result.get("message", "查询失败")
                    if "401" in error_msg or "Invalid token" in error_msg or "Unauthorized" in error_msg:
                        error_msg = "API Key 无效或已过期，请在设置中检查并更新 API Key"
                    yield f"{json.dumps({'error': error_msg})}\n"
                    return
                
                llm_response = bypass_result.get("llm_response", {})
            else:
                # 临时替换 LLM 函数为聊天配置（用于查询）
                original_llm_func = lightrag.llm_model_func
                chat_llm_func = service.lightrag_service.get_chat_llm_func()
                lightrag.llm_model_func = chat_llm_func
                
                # 步骤2：执行查询（知识图谱不为空，包含历史对话）
                param = QueryParam(mode=request.mode, stream=True)
                if history:
                    param.conversation_history = history
                try:
                    result = await lightrag.aquery_llm(request.query, param=param)
                except Exception as e:
                    error_msg = str(e)
                    if "401" in error_msg or "Invalid token" in error_msg or "Unauthorized" in error_msg:
                        error_msg = "API Key 无效或已过期，请在设置中检查并更新 API Key"
                    yield f"{json.dumps({'error': error_msg})}\n"
                    return
                
                # 恢复原始的 LLM 函数（用于文档抽取）
                lightrag.llm_model_func = original_llm_func
                
                # 步骤3：查询后验证结果
                result_empty, no_content = await service.check_query_result_empty(result, kg_empty_before)
                
                # 判断是否需要降级到 bypass 模式
                need_fallback = False
                warning_message = None
                
                if result_empty:
                    if no_content:
                        # 有知识图谱但查询未匹配到相关内容
                        need_fallback = True
                        warning_message = "⚠️ 未检索到相关内容，将基于通用知识回答："
                    else:
                        # 其他情况（查询失败等）
                        need_fallback = True
                        warning_message = "⚠️ 未检索到相关文档，将基于通用知识回答："
                elif result.get("status") == "failure":
                    # 查询失败（非 401 错误）
                    need_fallback = True
                    warning_message = "⚠️ 未检索到相关文档，将基于通用知识回答："
                
                # 如果需要降级，使用 bypass 模式重新查询
                if need_fallback:
                    # 先发送警告提示
                    if warning_message:
                        yield f"{json.dumps({'warning': warning_message})}\n"
                        # 发送换行（不能在 f-string 表达式中使用反斜杠）
                        newline_text = '\n\n'
                        yield f"{json.dumps({'response': newline_text})}\n"
                    
                    # 临时替换 LLM 函数为聊天配置（用于查询）
                    original_llm_func = lightrag.llm_model_func
                    chat_llm_func = service.lightrag_service._get_llm_func(use_chat_config=True)
                    lightrag.llm_model_func = chat_llm_func
                    
                    # 使用 bypass 模式重新查询（包含历史对话）
                    bypass_param = QueryParam(mode="bypass", stream=True)
                    if history:
                        bypass_param.conversation_history = history
                    try:
                        bypass_result = await lightrag.aquery_llm(request.query, param=bypass_param)
                    except Exception as e:
                        error_msg = str(e)
                        if "401" in error_msg or "Invalid token" in error_msg or "Unauthorized" in error_msg:
                            error_msg = "API Key 无效或已过期，请在设置中检查并更新 API Key"
                        yield f"{json.dumps({'error': error_msg})}\n"
                        return
                    
                    # 恢复原始的 LLM 函数（用于文档抽取）
                    lightrag.llm_model_func = original_llm_func
                    llm_response = bypass_result.get("llm_response", {})
                else:
                    # 正常使用查询结果
                    llm_response = result.get("llm_response", {})
            
            # 步骤4：检查是否有错误状态（在获取 llm_response 之前）
            # 检查所有可能的结果来源
            result_to_check = None
            if kg_empty_before:
                result_to_check = bypass_result
            elif need_fallback:
                result_to_check = bypass_result
            else:
                result_to_check = result
            
            if result_to_check and result_to_check.get("status") == "failure":
                error_msg = result_to_check.get("message", "查询失败")
                if "401" in error_msg or "Invalid token" in error_msg or "Unauthorized" in error_msg:
                    error_msg = "API Key 无效或已过期，请在设置中检查并更新 API Key"
                yield f"{json.dumps({'error': error_msg})}\n"
                return
            
            # 步骤5：流式发送响应
            if llm_response.get("is_streaming"):
                # 流式模式：逐块发送响应
                response_stream = llm_response.get("response_iterator")
                if response_stream:
                    try:
                        async for chunk in response_stream:
                            if chunk:  # 只发送非空内容
                                yield f"{json.dumps({'response': chunk})}\n"
                    except Exception as e:
                        error_msg = str(e)
                        if "401" in error_msg or "Invalid token" in error_msg or "Unauthorized" in error_msg:
                            error_msg = "API Key 无效或已过期，请在设置中检查并更新 API Key"
                        yield f"{json.dumps({'error': error_msg})}\n"
                else:
                    # 如果没有流式响应，发送完整内容
                    content = llm_response.get("content", "")
                    if content:
                        yield f"{json.dumps({'response': content})}\n"
            else:
                # 非流式模式：发送完整响应
                content = llm_response.get("content", "")
                if content:
                    yield f"{json.dumps({'response': content})}\n"
                else:
                    yield f"{json.dumps({'error': 'No response generated'})}\n"
                    
        except Exception as e:
            error_msg = str(e)
            # 检测 401 错误
            if "401" in error_msg or "Invalid token" in error_msg or "Unauthorized" in error_msg:
                error_msg = "API Key 无效或已过期，请在设置中检查并更新 API Key"
            yield f"{json.dumps({'error': error_msg})}\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

