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
        
        # 验证查询模式
        valid_modes = ["naive", "local", "global", "mix"]
        if mode not in valid_modes:
            return {
                "status": "error",
                "message": f"无效的查询模式: {mode}，支持的模式: {', '.join(valid_modes)}"
            }
        
        # 检查是否有文档
        if not service.check_has_documents_fast(conversation_id):
            return {
                "status": "info",
                "message": "对话中没有文档，将使用通用知识回答",
                "result": None,
                "mode": "bypass"
            }
        
        # 执行查询 - 使用 aquery_data 获取原始数据，而不是 LLM 生成的回答
        # 这样 Agent 的 LLM 可以基于原始数据生成更合适的回答
        from app.services.lightrag_service import LightRAGService
        lightrag_service = LightRAGService()
        lightrag = await lightrag_service.get_lightrag_for_conversation(conversation_id)
        from lightrag import QueryParam
        param = QueryParam(mode=mode)
        
        # 使用 aquery_data 获取原始查询数据（实体、关系、文本块等）
        query_data = await lightrag.aquery_data(query, param=param)
        
        # 格式化查询结果为可读的文本，供 LLM 理解
        if isinstance(query_data, dict) and query_data.get("status") == "success":
            data = query_data.get("data", {})
            entities = data.get("entities", [])
            relationships = data.get("relationships", [])
            chunks = data.get("chunks", [])
            metadata = query_data.get("metadata", {})
            
            # 构建格式化的查询结果文本
            result_parts = []
            
            # 添加元数据信息
            query_mode = metadata.get("query_mode", mode)
            keywords = metadata.get("keywords", {})
            high_level_keywords = keywords.get("high_level", [])
            low_level_keywords = keywords.get("low_level", [])
            
            result_parts.append(f"查询模式: {query_mode}")
            if high_level_keywords:
                result_parts.append(f"高级关键词: {', '.join(high_level_keywords)}")
            if low_level_keywords:
                result_parts.append(f"低级关键词: {', '.join(low_level_keywords)}")
            
            # 添加实体信息
            if entities:
                result_parts.append(f"\n找到 {len(entities)} 个相关实体:")
                for i, entity in enumerate(entities[:10], 1):  # 最多显示10个实体
                    entity_name = entity.get("entity_name", "")
                    entity_type = entity.get("entity_type", "")
                    description = entity.get("description", "")
                    if description:
                        result_parts.append(f"{i}. {entity_name} ({entity_type}): {description}")
                    else:
                        result_parts.append(f"{i}. {entity_name} ({entity_type})")
            
            # 添加关系信息
            if relationships:
                result_parts.append(f"\n找到 {len(relationships)} 个相关关系:")
                for i, rel in enumerate(relationships[:10], 1):  # 最多显示10个关系
                    src = rel.get("src_id", "")
                    tgt = rel.get("tgt_id", "")
                    desc = rel.get("description", "")
                    if desc:
                        result_parts.append(f"{i}. {src} -> {tgt}: {desc}")
                    else:
                        result_parts.append(f"{i}. {src} -> {tgt}")
            
            # 添加文本块信息
            if chunks:
                result_parts.append(f"\n找到 {len(chunks)} 个相关文本块:")
                for i, chunk in enumerate(chunks[:5], 1):  # 最多显示5个文本块
                    content = chunk.get("content", "")
                    if content:
                        # 截断过长的内容
                        content_preview = content[:200] + "..." if len(content) > 200 else content
                        result_parts.append(f"{i}. {content_preview}")
            
            formatted_result = "\n".join(result_parts)
            
            return {
                "status": "success",
                "message": f"查询完成（模式: {mode}），找到 {len(entities)} 个实体，{len(relationships)} 个关系，{len(chunks)} 个文本块",
                "result": formatted_result,
                "raw_data": {
                    "entities": entities,
                    "relationships": relationships,
                    "chunks": chunks,
                    "metadata": metadata
                },
                "mode": mode,
                "query": query
            }
        else:
            # 如果查询失败或返回空结果
            error_msg = query_data.get("message", "查询失败") if isinstance(query_data, dict) else "查询失败"
            return {
                "status": "error",
                "message": error_msg,
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

