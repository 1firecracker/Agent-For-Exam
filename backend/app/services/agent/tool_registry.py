"""
工具注册系统模块

本模块提供了工具注册和管理功能，支持：
- 工具定义和参数验证
- 工具注册和查询
- 工具格式转换为 OpenAI Function Calling 格式

主要类：
    ToolParameter: 工具参数定义（基于 JSON Schema）
    ToolDefinition: 工具定义（包含名称、描述、参数、处理函数等）
    ToolRegistry: 工具注册表，管理所有可用工具

使用示例：
    ```python
    # 定义工具
    tool = ToolDefinition(
        name="my_tool",
        description="我的工具",
        parameters={
            "param1": ToolParameter(
                type="string",
                description="参数1",
                required=True
            )
        },
        handler=my_handler
    )
    
    # 注册工具
    registry = ToolRegistry()
    registry.register(tool)
    
    # 转换为 Function Calling 格式
    functions = registry.to_function_calling_format()
    ```

注意事项：
    - conversation_id 参数会自动从 Function Calling 格式中排除
    - 工具参数必须符合 JSON Schema 规范
"""
from typing import Dict, List, Callable, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ToolParameter(BaseModel):
    """工具参数定义（JSON Schema 格式）"""
    type: str = Field(..., description="参数类型：string, number, boolean, object, array")
    description: str = Field(..., description="参数描述")
    required: bool = Field(default=False, description="是否必需")
    enum: Optional[List[Any]] = Field(default=None, description="可选值列表（用于枚举类型）")
    default: Optional[Any] = Field(default=None, description="默认值")
    items: Optional[Dict] = Field(default=None, description="数组类型的元素定义")


class ToolDefinition(BaseModel):
    """工具定义"""
    name: str = Field(..., description="工具名称（唯一标识）")
    description: str = Field(..., description="工具描述（用于LLM理解）")
    parameters: Dict[str, ToolParameter] = Field(default_factory=dict, description="参数定义")
    handler: Callable = Field(..., description="工具执行函数")
    category: str = Field(default="general", description="工具类别")
    requires_auth: bool = Field(default=False, description="是否需要认证")
    rate_limit: Optional[int] = Field(default=None, description="速率限制（每分钟调用次数）")


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
    
    def register(self, tool: ToolDefinition):
        """注册工具"""
        if tool.name in self.tools:
            raise ValueError(f"工具 {tool.name} 已存在")
        self.tools[tool.name] = tool
        print(f"✅ 工具已注册: {tool.name} ({tool.category})")
    
    def unregister(self, tool_name: str):
        """注销工具"""
        if tool_name in self.tools:
            del self.tools[tool_name]
            print(f"🗑️ 工具已注销: {tool_name}")
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """获取工具"""
        return self.tools.get(name)
    
    def list_tools(self, category: Optional[str] = None) -> List[ToolDefinition]:
        """列出工具（可按类别过滤）"""
        if category:
            return [t for t in self.tools.values() if t.category == category]
        return list(self.tools.values())
    
    def to_function_calling_format(self) -> List[Dict]:
        """转换为 OpenAI Function Calling 格式
        
        注意：conversation_id 参数会被自动排除，因为它在执行时会自动注入
        """
        functions = []
        for tool in self.tools.values():
            # 构建参数属性
            properties = {}
            required = []
            
            for param_name, param_def in tool.parameters.items():
                # 排除 conversation_id，因为它会在执行时自动注入
                if param_name == "conversation_id":
                    continue
                
                param_dict = {
                    "type": param_def.type,
                    "description": param_def.description
                }
                
                # 添加枚举值
                if param_def.enum:
                    param_dict["enum"] = param_def.enum
                
                # 添加默认值
                if param_def.default is not None:
                    param_dict["default"] = param_def.default
                
                # 添加数组元素定义
                if param_def.type == "array" and param_def.items:
                    param_dict["items"] = param_def.items
                
                properties[param_name] = param_dict
                
                if param_def.required:
                    required.append(param_name)
            
            functions.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            })
        
        return functions

