"""
思维脑图生成工具模块

本模块提供了思维脑图生成工具的实现，支持：
- 为指定文档生成思维脑图
- 为所有文档生成合并的思维脑图
- 流式生成支持

主要组件：
    generate_mindmap_handler: 思维脑图生成工具的处理函数
    MINDMAP_TOOL: 思维脑图工具的 ToolDefinition 实例

工具参数：
    - conversation_id (string, required): 对话ID（自动注入）
    - document_ids (array[string], optional): 要生成思维导图的文档ID列表
      - 如果不提供，则生成所有文档的合并思维脑图
      - 如果提供，则只为指定文档生成思维脑图

返回格式：
    {
        "status": "success" | "error",
        "message": "执行结果描述",
        "mindmap_content": "思维脑图 Markdown 内容（仅成功时）",
        "document_names": ["文档1", "文档2"]（仅成功时）
    }

使用示例：
    用户输入："请生成思维导图"
    LLM 调用：generate_mindmap({})  # 生成所有文档的思维脑图
    
    用户输入："为文档1和文档2生成思维导图"
    LLM 调用：generate_mindmap({"document_ids": ["doc1", "doc2"]})
"""
from typing import List, Optional, Dict, Any
from app.services.agent.tool_registry import ToolDefinition, ToolParameter
from app.services.mindmap_service import MindMapService
from app.services.document_service import DocumentService
from app.services.conversation_service import ConversationService
from app.config import get_logger

logger = get_logger("app.mindmap_tool")


async def generate_mindmap_handler(
    conversation_id: str,
    document_ids: Optional[List[str]] = None
):
    """生成思维脑图的工具处理函数
    
    Args:
        conversation_id: 对话ID
        document_ids: 要生成思维导图的文档ID列表（可选，如果不提供则生成所有文档）
        
    Returns:
        工具执行结果
    """
    try:
        mindmap_service = MindMapService()
        doc_service = DocumentService()
        conv_service = ConversationService()
        
        # 获取对话信息
        conversation = conv_service.get_conversation(conversation_id)
        conversation_title = conversation.get("title", "未命名课程") if conversation else "未命名课程"
        
        # 获取文档列表
        all_documents = doc_service.list_documents(conversation_id)
        
        if not all_documents:
            yield {
                "status": "error",
                "message": "对话中没有文档，无法生成思维脑图"
            }
            return
        
        # 如果指定了文档ID，只处理这些文档
        if document_ids:
            documents = [doc for doc in all_documents if doc["file_id"] in document_ids]
            if not documents:
                yield {
                    "status": "error",
                    "message": f"指定的文档ID不存在: {document_ids}"
                }
                return
        else:
            documents = all_documents
        
        # 准备文档列表（包含文件路径和文件名）
        doc_list = []
        for doc in documents:
            file_path = doc_service.file_manager.get_file_path(conversation_id, doc["file_id"])
            if file_path and file_path.exists():
                text = doc_service.document_parser.extract_text(str(file_path), file_id=doc["file_id"])
                if text:
                    doc_list.append({
                        "filename": doc["filename"],
                        "text": text,
                        "file_id": doc["file_id"]
                    })
        
        if not doc_list:
            yield {
                "status": "error",
                "message": "没有可用的文档内容"
            }
            return
        
        # 按文件名排序（确保生成顺序一致）
        doc_list.sort(key=lambda x: x["filename"])
        total_docs = len(doc_list)
        logger.info(
            "准备生成思维脑图",
            extra={
                "event": "mindmap.batch_start",
                "conversation_id": conversation_id,
                "total_docs": total_docs,
            },
        )

        # 每次新的思维脑图生成请求，先清空当前对话的脑图文件，再重新逐个追加
        mindmap_service.reset_mindmap(conversation_id)

        # 方案A：逐个文档生成思维脑图，通过文件级追加实现合并
        # LLM每次只处理当前文档，不再合并已有脑图（避免上下文过大和内容丢失）
        document_filenames = []
        
        for i, doc_info in enumerate(doc_list, 1):
            doc_filename = doc_info["filename"]
            doc_text = doc_info["text"]
            document_filenames.append(doc_filename)
            
            # 发送进度更新
            yield {
                "type": "tool_progress",
                "progress": {
                    "current": i,
                    "total": total_docs,
                    "message": f"正在处理第 {i}/{total_docs} 个文档: {doc_filename}",
                    "percentage": int((i / total_docs) * 100)
                }
            }
            
            logger.debug(
                "处理单个文档的思维脑图",
                extra={
                    "event": "mindmap.doc_processing",
                    "conversation_id": conversation_id,
                    "doc_index": i,
                    "total_docs": total_docs,
                    "document_id": doc_info.get("file_id"),
                    "document_filename": doc_filename,
                },
            )
            
            # 所有文档都只生成当前文档的脑图，不合并已有脑图
            # 合并通过 _save_mindmap 的文件级追加实现
            accumulated_content = ""
            try:
                async for chunk in mindmap_service.generate_mindmap_stream(
                    conversation_id,
                    doc_text,
                    conversation_title,
                    doc_filename,
                    document_id=doc_info.get("file_id"),
                    merge_existing=False
                ):
                    accumulated_content += chunk
                
                logger.info(
                    "单个文档思维脑图生成完成",
                    extra={
                        "event": "mindmap.doc_success",
                        "conversation_id": conversation_id,
                        "doc_index": i,
                        "total_docs": total_docs,
                        "document_id": doc_info.get("file_id"),
                        "document_filename": doc_filename,
                    },
                )
            except Exception as e:
                # 单个文档生成失败，记录错误但继续处理其他文档
                error_msg = f"处理文档 {doc_filename} 时出错: {str(e)}"
                logger.warning(
                    "单个文档思维脑图生成失败",
                    extra={
                        "event": "mindmap.doc_failed",
                        "conversation_id": conversation_id,
                        "document_id": doc_info.get("file_id"),
                        "document_filename": doc_filename,
                        "error_message": str(e),
                    },
                )
                # 发送进度更新，显示错误
                yield {
                    "type": "tool_progress",
                    "progress": {
                        "current": i,
                        "total": total_docs,
                        "message": f"⚠️ {error_msg}",
                        "percentage": int((i / total_docs) * 100)
                    }
                }
                # 如果 accumulated_content 有内容，尝试保存（可能部分成功）
                if accumulated_content:
                    try:
                        mindmap_content = mindmap_service._extract_mindmap_content(accumulated_content)
                        if mindmap_content:
                            mindmap_service._save_mindmap(conversation_id, mindmap_content)
                            logger.info(
                                "已保存部分思维脑图内容",
                                extra={
                                    "event": "mindmap.partial_saved",
                                    "conversation_id": conversation_id,
                                    "document_id": doc_info.get("file_id"),
                                    "document_filename": doc_filename,
                                },
                            )
                    except Exception as save_error:
                        logger.warning(
                            "保存部分思维脑图内容失败",
                            extra={
                                "event": "mindmap.partial_save_failed",
                                "conversation_id": conversation_id,
                                "document_id": doc_info.get("file_id"),
                                "document_filename": doc_filename,
                                "error_message": str(save_error),
                            },
                        )
                # 继续处理下一个文档，不中断整个流程
        
        logger.info(
            "所有文档思维脑图处理完成",
            extra={
                "event": "mindmap.batch_done",
                "conversation_id": conversation_id,
                "total_docs": total_docs,
            },
        )
        
        # 提取最终保存的思维脑图内容
        from pathlib import Path
        import app.config as config
        
        mindmap_dir = Path(config.settings.data_dir) / "mindmaps"
        mindmap_file = mindmap_dir / f"{conversation_id}.md"
        
        if mindmap_file.exists():
            mindmap_content = mindmap_file.read_text(encoding='utf-8')
        else:
            # 如果文件不存在，尝试从最后一次流式内容中提取
            mindmap_content = mindmap_service._extract_mindmap_content(accumulated_content) if accumulated_content else None
        
        if mindmap_content:
            yield {
                "status": "success",
                "message": f"思维脑图已生成（基于 {len(doc_list)} 个文档，逐个生成并合并）",
                "mindmap_content": mindmap_content,
                "document_count": len(doc_list),
                "document_names": document_filenames
            }
        else:
            yield {
                "status": "error",
                "message": "思维脑图生成失败，无法提取有效内容"
            }
    
    except Exception as e:
        yield {
            "status": "error",
            "message": f"生成思维脑图时出错: {str(e)}",
            "error": str(e)
        }


# 定义思维脑图工具
MINDMAP_TOOL = ToolDefinition(
    name="generate_mindmap",
    description="根据对话中的文档内容生成思维导图。可以指定特定文档，或生成所有文档的思维导图。生成的思维导图会保存到对话中，可以在思维脑图标签页查看。",
    parameters={
        "conversation_id": ToolParameter(
            type="string",
            description="对话ID",
            required=True
        ),
        "document_ids": ToolParameter(
            type="array",
            description="要生成思维导图的文档ID列表（可选，如果不提供则生成所有文档）。**重要：必须使用 file_id（文档ID），而不是 filename（文件名）, 若不提供file_id 参数 则用全部文档生成**。可以通过 list_documents 工具获取每个文档的 file_id。",
            required=False,
            items={
                "type": "string"
            }
        )
    },
    handler=generate_mindmap_handler,
    category="mindmap",
    rate_limit=5  # 每分钟最多5次
)

