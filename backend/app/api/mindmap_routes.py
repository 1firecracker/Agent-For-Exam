"""思维脑图 API 路由"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.services.mindmap_service import MindMapService
from app.services.document_service import DocumentService
from app.utils.document_parser import DocumentParser

router = APIRouter(tags=["mindmap"])


class MindMapResponse(BaseModel):
    content: Optional[str] = None
    exists: bool = False


@router.get("/api/conversations/{conversation_id}/mindmap",
            response_model=MindMapResponse)
async def get_mindmap(conversation_id: str):
    """获取对话的思维脑图
    
    Args:
        conversation_id: 对话ID
    """
    service = MindMapService()
    mindmap_content = await service.get_mindmap(conversation_id)
    
    return MindMapResponse(
        content=mindmap_content,
        exists=mindmap_content is not None
    )


@router.post("/api/conversations/{conversation_id}/mindmap/generate")
async def generate_mindmap(conversation_id: str, document_id: Optional[str] = None):
    """生成或更新思维脑图（流式）
    
    Args:
        conversation_id: 对话ID
        document_id: 文档ID（可选，如果提供则只处理该文档）
    """
    service = MindMapService()
    doc_service = DocumentService()
    parser = DocumentParser()
    from app.services.conversation_service import ConversationService
    conv_service = ConversationService()
    
    try:
        # 获取对话标题（课程名）
        conversation = conv_service.get_conversation(conversation_id)
        conversation_title = conversation.get("title", "未命名课程") if conversation else "未命名课程"
        
        # 获取文档文本
        if document_id:
            # 处理单个文档
            file_path = doc_service.file_manager.get_file_path(conversation_id, document_id)
            if not file_path or not file_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"文档 {document_id} 不存在"
                )
            
            # 获取文档信息（用于获取文件名和状态）
            document_info = doc_service.get_document(conversation_id, document_id)
            if not document_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"文档 {document_id} 信息不存在"
                )
            
            # 如果文档还在处理中，尝试等待一下（最多等待5秒）
            if document_info.get("status") == "processing":
                import asyncio
                print(f"⏳ 文档 {document_id[:8]}... 正在处理中，等待文档文本准备...")
                for i in range(10):  # 等待最多5秒（每次0.5秒）
                    await asyncio.sleep(0.5)
                    # 重新获取文档信息
                    document_info = doc_service.get_document(conversation_id, document_id)
                    if document_info and document_info.get("status") != "processing":
                        break
                    # 即使还在处理中，也尝试提取文本（文件可能已经准备好了）
                    try:
                        text = parser.extract_text(str(file_path))
                        if text and text.strip():
                            document_text = text
                            break
                    except Exception as e:
                        print(f"⚠️ 尝试提取文本失败: {e}")
                        pass
            
            # 提取文档文本
            document_text = parser.extract_text(str(file_path))
            document_filename = document_info.get("filename", f"文档_{document_id[:8]}") if document_info else f"文档_{document_id[:8]}"
        else:
            # 处理对话的所有文档（合并）- 这种情况不应该使用新的结构，保持原有逻辑
            # 但为了兼容，我们使用第一个文档的文件名作为主文档名
            documents = doc_service.list_documents(conversation_id)
            if not documents:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="对话中没有文档"
                )
            
            # 合并所有文档的文本
            all_texts = []
            first_doc_filename = None
            for doc in documents:
                file_path = doc_service.file_manager.get_file_path(conversation_id, doc["file_id"])
                if file_path and file_path.exists():
                    text = parser.extract_text(str(file_path))
                    if text:
                        all_texts.append(f"\n\n=== 文档: {doc['filename']} ===\n\n{text}")
                        if first_doc_filename is None:
                            first_doc_filename = doc['filename']
            
            if not all_texts:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="没有可用的文档内容"
                )
            
            document_text = "\n".join(all_texts)
            document_filename = first_doc_filename or "合并文档"
        
        if not document_text or not document_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文档内容为空"
            )
        
        # 流式生成思维脑图
        async def generate():
            async for chunk in service.generate_mindmap_stream(
                conversation_id, 
                document_text,
                conversation_title,
                document_filename,
                document_id
            ):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # 禁用 Nginx 缓冲
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成思维脑图失败: {str(e)}"
        )


@router.delete("/api/conversations/{conversation_id}/mindmap",
               status_code=status.HTTP_204_NO_CONTENT)
async def delete_mindmap(conversation_id: str):
    """删除对话的思维脑图
    
    Args:
        conversation_id: 对话ID
    """
    service = MindMapService()
    success = await service.delete_mindmap(conversation_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="思维脑图不存在"
        )
    
    return None

