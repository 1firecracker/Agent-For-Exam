"""
技能读取工具模块

本模块提供了读取技能详细说明的工具实现，支持：
- 获取指定技能的完整 SKILL.md 内容
- 列出所有可用技能的元数据

主要组件：
    read_skill_instructions_handler: 读取技能说明的处理函数
    READ_SKILL_TOOL: 读取技能说明工具的 ToolDefinition 实例

工具参数（read_skill_instructions）：
    - skill_name (string, required): 要读取的技能名称

返回格式：
    {
        "status": "success" | "error",
        "message": "执行结果描述",
        "skill_name": "技能名称",
        "instructions": "完整的 SKILL.md 内容（仅成功时）"
    }

使用示例：
    用户输入："帮我画个思维导图"
    LLM 推理：需要了解 generate_mindmap 的详细用法
    LLM 调用：read_skill_instructions({"skill_name": "generate_mindmap"})
    LLM 获取完整说明后：调用 generate_mindmap 工具
"""
from typing import Dict, Any, List

from app.services.agent.tool_registry import ToolDefinition, ToolParameter
from app.services.agent.skill_manager import SkillManager
from app.config import get_logger

logger = get_logger("app.services.agent.skill_tools")

# 全局 SkillManager 实例
_skill_manager: SkillManager = None


def _get_skill_manager() -> SkillManager:
    """获取 SkillManager 单例
    
    Returns:
        SkillManager 实例
    """
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
        _skill_manager.discover_skills()
    return _skill_manager


async def read_skill_instructions_handler(
    skill_name: str
) -> Dict[str, Any]:
    """读取指定技能的详细说明
    
    这是渐进式披露的核心实现：当 Agent 决定使用某个技能时，
    调用此工具获取完整的使用说明。
    
    Args:
        skill_name: 技能名称（如 "generate_mindmap"）
        
    Returns:
        包含技能说明的结果字典
    """
    try:
        manager = _get_skill_manager()
        
        # 加载技能说明
        instructions = manager.load_skill_instructions(skill_name)
        
        if instructions is None:
            # 列出可用技能，帮助 LLM 选择正确的技能
            available_skills = list(manager._registry.keys())
            
            logger.warning(
                "技能不存在",
                extra={
                    "event": "skill_tool.not_found",
                    "skill_name": skill_name,
                    "available_skills": available_skills,
                }
            )
            
            return {
                "status": "error",
                "message": f"技能 '{skill_name}' 不存在",
                "skill_name": skill_name,
                "available_skills": available_skills,
                "hint": "请使用 list_available_skills 查看所有可用技能"
            }
        
        logger.info(
            "技能说明已读取",
            extra={
                "event": "skill_tool.read_success",
                "skill_name": skill_name,
                "content_length": len(instructions),
            }
        )
        
        return {
            "status": "success",
            "message": f"成功读取技能 '{skill_name}' 的详细说明",
            "skill_name": skill_name,
            "instructions": instructions
        }
    
    except Exception as e:
        logger.error(
            "读取技能说明失败",
            extra={
                "event": "skill_tool.read_error",
                "skill_name": skill_name,
                "error": str(e),
            }
        )
        return {
            "status": "error",
            "message": f"读取技能说明时出错: {str(e)}",
            "skill_name": skill_name,
            "error": str(e)
        }





# 定义读取技能说明工具
READ_SKILL_TOOL = ToolDefinition(
    name="read_skill_instructions",
    description="获取某个技能的详细使用说明和参数定义。在调用复杂工具前，先用此工具了解详细用法。",
    parameters={
        "skill_name": ToolParameter(
            type="string",
            description="要读取的技能名称，如 'generate_mindmap'、'query_knowledge_graph' 等",
            required=True
        )
    },
    handler=read_skill_instructions_handler,
    category="skill",
    rate_limit=30  # 每分钟最多 30 次
)



