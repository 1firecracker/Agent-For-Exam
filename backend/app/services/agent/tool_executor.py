"""
工具执行器模块

本模块负责执行已注册的工具，提供：
- 工具参数验证
- 工具执行和错误处理
- 执行历史记录
- 速率限制检查

主要类：
    ToolExecutor: 工具执行器，负责执行工具调用并返回结果

使用示例：
    ```python
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    
    result = await executor.execute(
        tool_name="my_tool",
        parameters={"param1": "value1"},
        conversation_id="abc123"
    )
    
    if result["status"] == "success":
        print(f"执行成功: {result['result']}")
    ```

注意事项：
    - conversation_id 会在执行前自动注入到参数中
    - 工具执行失败会返回错误信息，不会抛出异常
    - 执行历史会记录所有工具调用（用于调试和审计）
"""
import time
import asyncio
from typing import Dict, Any, List, Optional
from app.services.agent.tool_registry import ToolRegistry, ToolDefinition
from app.config import get_logger

logger = get_logger("app.tool_executor")


class ToolExecutor:
    """工具执行器"""
    
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.execution_history: List[Dict] = []  # 执行历史
    
    async def execute(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        conversation_id: str
    ) -> Dict[str, Any]:
        """执行工具
        
        Args:
            tool_name: 工具名称
            parameters: 工具参数
            conversation_id: 对话ID（自动注入）
            
        Returns:
            工具执行结果
        """
        # 1. 获取工具定义
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return {
                "status": "error",
                "message": f"工具 {tool_name} 不存在",
                "tool_name": tool_name
            }
        
        # 2. 注入 conversation_id（在执行前注入，这样验证时也会包含它）
        # conversation_id 总是自动注入，即使 LLM 没有提供
        if "conversation_id" not in parameters:
            parameters["conversation_id"] = conversation_id
        
        # 3. 验证参数（现在 conversation_id 已经在 parameters 中了）
        validation_result = self._validate_parameters(tool, parameters)
        if not validation_result["valid"]:
            return {
                "status": "error",
                "message": f"参数验证失败: {validation_result['error']}",
                "tool_name": tool_name
            }
        
        # 4. 检查速率限制
        if not self._check_rate_limit(tool):
            return {
                "status": "error",
                "message": "工具调用频率过高，请稍后再试",
                "tool_name": tool_name
            }
        
        # 5. 执行工具
        try:
            logger.info(
                "开始执行工具",
                extra={
                    "event": "tool.execute_start",
                    "tool_name": tool_name,
                    "conversation_id": conversation_id,
                    "parameters": parameters,
                },
            )
            
            # 调用工具处理函数
            if asyncio.iscoroutinefunction(tool.handler):
                result = await tool.handler(**parameters)
            else:
                result = tool.handler(**parameters)
            
            # 5. 记录执行历史
            self.execution_history.append({
                "tool_name": tool_name,
                "parameters": parameters,
                "result": result,
                "timestamp": time.time()
            })
            
            logger.info(
                "工具执行成功",
                extra={
                    "event": "tool.execute_success",
                    "tool_name": tool_name,
                    "conversation_id": conversation_id,
                },
            )
            
            return {
                "status": "success",
                "tool_name": tool_name,
                "result": result
            }
        
        except Exception as e:
            error_msg = f"工具执行失败: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    "event": "tool.execute_failed",
                    "tool_name": tool_name,
                    "conversation_id": conversation_id,
                },
            )
            return {
                "status": "error",
                "message": error_msg,
                "tool_name": tool_name,
                "error": str(e)
            }
    
    def is_generator_tool(self, tool_name: str) -> bool:
        """检查工具是否为生成器工具"""
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return False
        import inspect
        return inspect.isasyncgenfunction(tool.handler)
    
    async def execute_generator(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        conversation_id: str
    ):
        """执行生成器工具（用于支持进度更新）
        
        Yields:
            - {"type": "tool_progress", "tool_name": str, "progress": dict} - 进度更新
            - {"type": "tool_result", "tool_name": str, "result": dict} - 最终结果
        """
        # 1. 获取工具定义
        tool = self.registry.get_tool(tool_name)
        if not tool:
            yield {
                "type": "tool_result",
                "tool_name": tool_name,
                "result": {
                    "status": "error",
                    "message": f"工具 {tool_name} 不存在"
                }
            }
            return
        
        # 2. 注入 conversation_id
        if "conversation_id" not in parameters:
            parameters["conversation_id"] = conversation_id
        
        # 3. 验证参数
        validation_result = self._validate_parameters(tool, parameters)
        if not validation_result["valid"]:
            yield {
                "type": "tool_result",
                "tool_name": tool_name,
                "result": {
                    "status": "error",
                    "message": f"参数验证失败: {validation_result['error']}"
                }
            }
            return
        
        # 4. 检查速率限制
        if not self._check_rate_limit(tool):
            yield {
                "type": "tool_result",
                "tool_name": tool_name,
                "result": {
                    "status": "error",
                    "message": "工具调用频率过高，请稍后再试"
                }
            }
            return
        
        # 5. 执行生成器工具
        try:
            logger.info(
                "开始执行生成器工具",
                extra={
                    "event": "tool.execute_generator_start",
                    "tool_name": tool_name,
                    "conversation_id": conversation_id,
                    "parameters": parameters,
                },
            )
            
            result = None
            async for item in tool.handler(**parameters):
                if isinstance(item, dict) and item.get("type") == "tool_progress":
                    # 进度更新
                    yield {
                        "type": "tool_progress",
                        "tool_name": tool_name,
                        "progress": item.get("progress")
                    }
                elif isinstance(item, dict) and ("status" in item or "message" in item):
                    # 最终结果
                    result = item
                    break
                else:
                    # 其他情况，作为最终结果
                    result = item
            
            # 如果没有收到结果，使用默认值
            if result is None:
                result = {"status": "success", "message": "工具执行完成"}
            
            # 记录执行历史
            self.execution_history.append({
                "tool_name": tool_name,
                "parameters": parameters,
                "result": result,
                "timestamp": time.time()
            })
            
            logger.info(
                "生成器工具执行成功",
                extra={
                    "event": "tool.execute_generator_success",
                    "tool_name": tool_name,
                    "conversation_id": conversation_id,
                },
            )
            
            yield {
                "type": "tool_result",
                "tool_name": tool_name,
                "result": result
            }
        
        except Exception as e:
            error_msg = f"工具执行失败: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    "event": "tool.execute_generator_failed",
                    "tool_name": tool_name,
                    "conversation_id": conversation_id,
                },
            )
            yield {
                "type": "tool_result",
                "tool_name": tool_name,
                "result": {
                    "status": "error",
                    "message": error_msg,
                    "error": str(e)
                }
            }
    
    def _validate_parameters(self, tool: ToolDefinition, parameters: Dict) -> Dict[str, Any]:
        """验证参数
        
        Returns:
            {"valid": bool, "error": str}
        """
        # 检查必需参数
        for param_name, param_def in tool.parameters.items():
            if param_def.required and param_name not in parameters:
                return {
                    "valid": False,
                    "error": f"缺少必需参数: {param_name}"
                }
            
            # 检查参数类型
            if param_name in parameters:
                value = parameters[param_name]
                if not self._check_type(value, param_def.type):
                    return {
                        "valid": False,
                        "error": f"参数 {param_name} 类型错误，期望 {param_def.type}，实际 {type(value).__name__}"
                    }
                
                # 检查枚举值
                if param_def.enum and value not in param_def.enum:
                    return {
                        "valid": False,
                        "error": f"参数 {param_name} 的值不在允许的枚举值中: {param_def.enum}"
                    }
        
        return {"valid": True, "error": None}
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查类型"""
        type_map = {
            "string": str,
            "number": (int, float),
            "boolean": bool,
            "object": dict,
            "array": list
        }
        expected = type_map.get(expected_type)
        if expected:
            return isinstance(value, expected)
        return True
    
    def _check_rate_limit(self, tool: ToolDefinition) -> bool:
        """检查速率限制"""
        if tool.rate_limit is None:
            return True
        
        # 检查最近一段时间内的调用次数（最近1分钟）
        current_time = time.time()
        recent_calls = [
            h for h in self.execution_history
            if h["tool_name"] == tool.name
            and current_time - h["timestamp"] < 60
        ]
        
        return len(recent_calls) < tool.rate_limit
    
    def get_execution_history(self, tool_name: Optional[str] = None) -> List[Dict]:
        """获取执行历史"""
        if tool_name:
            return [h for h in self.execution_history if h["tool_name"] == tool_name]
        return self.execution_history

