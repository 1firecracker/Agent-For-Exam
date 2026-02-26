"""
知识图谱查询工具模块

本模块提供了知识图谱查询工具的实现，支持多种查询模式：
- naive: 简单查询，直接检索相关文本块
- local: 本地图谱查询，基于实体和关系
- global: 全局查询，综合分析
- mix: 混合查询，结合多种方式（默认模式）

主要组件：
    query_knowledge_graph_handler: 知识图谱查询工具的处理函数
    QUERY_TOOL: 知识图谱查询工具的 ToolDefinition 实例

工具参数：
    - conversation_id (string, required): 对话ID（自动注入）
    - query (string, required): 查询文本
    - mode (string, optional): 查询模式，可选值：["naive", "local", "global", "mix"]
      - 默认值：mix

返回格式：
    {
        "status": "success" | "error" | "info",
        "message": "执行结果描述",
        "result": "查询结果内容（字符串）",
        "mode": "使用的查询模式",
        "query": "原始查询文本"
    }

使用示例：
    用户输入："文档中关于考试的内容是什么？"
    LLM 调用：query_knowledge_graph({
        "query": "文档中关于考试的内容是什么？",
        "mode": "mix"
    })
    
    用户输入："查询神经网络相关的内容"
    LLM 调用：query_knowledge_graph({
        "query": "神经网络",
        "mode": "local"
    })

注意事项：
    - 如果对话中没有文档，会返回 info 状态，提示将使用通用知识回答
    - 查询结果会包含从知识图谱中检索到的相关实体、关系和文本块
"""
from typing import Dict, Any
from app.services.agent.tool_registry import ToolDefinition, ToolParameter
from app.services.graph_service import GraphService


async def query_knowledge_graph_handler(
    conversation_id: str,
    query: str,
    mode: str = "mix"
) -> Dict[str, Any]:
    """查询知识图谱的工具处理函数
    
    Args:
        conversation_id: 对话ID
        query: 查询文本
        mode: 查询模式（naive/local/global/mix）
        
    Returns:
        工具执行结果
    """
    try:
        service = GraphService()
        valid_modes = ["naive", "local", "global", "mix"]
        if mode not in valid_modes:
            return {
                "status": "error",
                "message": f"无效的查询模式: {mode}，支持的模式: {', '.join(valid_modes)}"
            }
        if not service.check_has_documents_fast(conversation_id):
            return {
                "status": "info",
                "message": "对话中没有文档，将使用通用知识回答",
                "result": None,
                "mode": "bypass"
            }
        from app.services.conversation_service import ConversationService
        conversation = ConversationService().get_conversation(conversation_id)
        subject_id = conversation.get("subject_id") if conversation else None
        rag_id = subject_id if subject_id else conversation_id
        result = await service.query_knowledge_raw(rag_id, query, mode, context_id=conversation_id)
        if result.get("status") == "success":
            return {
                "status": "success",
                "message": result.get("message", ""),
                "result": result.get("result", ""),
                "raw_data": result.get("raw_data"),
                "mode": mode,
                "query": query
            }
        return {
            "status": "error",
            "message": result.get("message", "查询失败"),
            "result": "",
            "mode": mode,
            "query": query
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"查询知识图谱时出错: {str(e)}",
            "error": str(e)
        }


# 定义知识图谱查询工具
QUERY_TOOL = ToolDefinition(
    name="query_knowledge_graph",
    description="在对话的知识图谱中查询信息。支持多种查询模式：naive（简单查询，直接检索相关文本块）、local（本地图谱查询，基于实体和关系）、global（全局查询，综合分析）、mix（混合查询，结合多种方式）。",
    parameters={
        "conversation_id": ToolParameter(
            type="string",
            description="对话ID",
            required=True
        ),
        "query": ToolParameter(
            type="string",
            description="查询文本",
            required=True
        ),
        "mode": ToolParameter(
            type="string",
            description="查询模式",
            required=False,
            enum=["naive", "local", "global", "mix"],
            default="mix"
        )
    },
    handler=query_knowledge_graph_handler,
    category="query",
    rate_limit=20  # 每分钟最多20次
)

