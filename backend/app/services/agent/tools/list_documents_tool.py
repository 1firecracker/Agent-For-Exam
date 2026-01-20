"""
列出文档工具模块

本模块提供了列出对话中所有文档的工具实现，支持：
- 列出当前对话的所有文档
- 显示文档的基本信息（文件名、上传时间、状态等）

主要组件：
    list_documents_handler: 列出文档工具的处理函数
    LIST_DOCUMENTS_TOOL: 列出文档工具的 ToolDefinition 实例

工具参数：
    - conversation_id (string, required): 对话ID（自动注入）

返回格式：
    {
        "status": "success" | "error",
        "message": "执行结果描述",
        "documents": [
            {
                "file_id": "文档ID",
                "filename": "文件名",
                "upload_time": "上传时间",
                "status": "文档状态",
                ...
            }
        ],
        "document_count": 文档数量
    }

使用示例：
    用户输入："列出所有文档"
    LLM 调用：list_documents({})  # conversation_id 自动注入
"""
from typing import Dict, Any
from app.services.agent.tool_registry import ToolDefinition, ToolParameter
from app.services.document_service import DocumentService
from app.services.conversation_service import ConversationService


async def list_documents_handler(
    conversation_id: str
) -> Dict[str, Any]:
    """列出对话中所有文档的工具处理函数
    
    Args:
        conversation_id: 对话ID
        
    Returns:
        工具执行结果
    """
    try:
        doc_service = DocumentService()
        conversation_service = ConversationService()
        
        # 获取对话信息，提取 subject_id
        conversation = conversation_service.get_conversation(conversation_id)
        subject_id = conversation.get("subject_id") if conversation else None
        
        # 如果对话有 subject_id，使用 subject_id 来列出文档（因为文档现在基于 subject_id 存储）
        # 否则回退到使用 conversation_id（向后兼容）
        if subject_id:
            documents = doc_service.list_documents_for_subject(subject_id)
        else:
            documents = doc_service.list_documents(conversation_id)
        
        if not documents:
            return {
                "status": "success",
                "message": "当前对话中没有文档",
                "documents": [],
                "document_count": 0
            }
        
        # 格式化文档信息（只包含关键字段）
        formatted_documents = []
        for doc in documents:
            formatted_doc = {
                "file_id": doc.get("file_id", ""),
                "filename": doc.get("filename", "未知文件"),
                "upload_time": doc.get("upload_time", ""),
                "status": doc.get("status", "unknown"),
                "file_type": doc.get("file_type", ""),
                "file_size": doc.get("file_size", 0)
            }
            formatted_documents.append(formatted_doc)
        
        # 构建格式化的结果文本
        result_parts = [f"当前对话共有 {len(documents)} 个文档：\n"]
        for i, doc in enumerate(formatted_documents, 1):
            status_text = {
                "processing": "处理中",
                "completed": "已完成",
                "failed": "失败",
                "pending": "等待中"
            }.get(doc["status"], doc["status"])
            
            file_size = doc.get("file_size", 0)
            size_text = ""
            if file_size > 0:
                if file_size < 1024:
                    size_text = f" ({file_size} B)"
                elif file_size < 1024 * 1024:
                    size_text = f" ({file_size / 1024:.2f} KB)"
                else:
                    size_text = f" ({file_size / (1024 * 1024):.2f} MB)"
            
            result_parts.append(
                f"{i}. {doc['filename']}{size_text} - {status_text}"
            )
            result_parts.append(f"   文档ID (file_id): {doc['file_id']}")
            if doc.get("upload_time"):
                result_parts.append(f"   上传时间: {doc['upload_time']}")
        
        result_text = "\n".join(result_parts)
        
        return {
            "status": "success",
            "message": f"成功列出 {len(documents)} 个文档",
            "result": result_text,
            "documents": formatted_documents,
            "document_count": len(documents)
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"列出文档时出错: {str(e)}",
            "error": str(e),
            "documents": [],
            "document_count": 0
        }


# 定义列出文档工具
LIST_DOCUMENTS_TOOL = ToolDefinition(
    name="list_documents",
    description="列出当前对话中的所有文档，包括文件名、上传时间、状态等信息。",
    parameters={
        "conversation_id": ToolParameter(
            type="string",
            description="对话ID",
            required=True
        )
    },
    handler=list_documents_handler,
    category="document",
    rate_limit=10  # 每分钟最多10次
)

