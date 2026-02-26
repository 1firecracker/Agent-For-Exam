"""Exam Analysis 模块 Hook 接口与默认实现。

首版仅定义接口与默认实现骨架，具体逻辑在分阶段重构中逐步填充。
"""
from typing import Any, Dict, List

from app.services.exam_analysis.event_bus import emit as event_emit
from app.services.exam_analysis.trace_storage import TraceStorage


class ExamAnalysisPipelineHooks:
    """流水线级 Hook：一次完整 Exam Analysis 会话的开始/结束、按试卷的开始/结束、报告保存等。"""

    def on_pipeline_start(self, conversation_id: str, subject_id: str, selected_exam_ids: List[str]) -> None:
        """分析开始前调用。默认不做任何操作。"""
        return

    def on_pipeline_exam_start(
        self,
        conversation_id: str,
        subject_id: str,
        exam_id: str,
        total_questions: int,
        batch_size: int,
    ) -> None:
        """单张试卷开始前调用。默认不做任何操作。"""
        return

    def on_pipeline_exam_end(self, conversation_id: str, subject_id: str, exam_id: str, success: bool) -> None:
        """单张试卷处理完成后调用。默认不做任何操作。"""
        return

    def on_pipeline_end(self, conversation_id: str, success: bool) -> None:
        """全部试卷处理完成后调用。默认不做任何操作。"""
        return

    def on_report_saved(self, conversation_id: str, summary: Dict[str, Any]) -> None:
        """报告写入磁盘后调用。默认不做任何操作。"""
        return


class ExamAnalysisAgentHooks:
    """Agent 生命周期 Hook：Lead/Sub 的开始与结束。"""

    def on_lead_start(self, conversation_id: str, lead_trace: Dict[str, Any]) -> None:
        """Lead Agent 启动时调用：写入轨迹并发送 lead_started 事件。"""
        TraceStorage.append_trace(conversation_id, lead_trace)
        event_emit(
            conversation_id,
            {
                "type": "lead_started",
                "agent_id": lead_trace.get("agent_id"),
                "label": lead_trace.get("label"),
                "status": lead_trace.get("status"),
            },
        )

    def on_lead_end(self, conversation_id: str, lead_done_trace: Dict[str, Any]) -> None:
        """Lead Agent 完成时调用：写入轨迹并发送 lead_done 事件。"""
        TraceStorage.append_trace(conversation_id, lead_done_trace)
        event_emit(
            conversation_id,
            {
                "type": "lead_done",
                "agent_id": lead_done_trace.get("agent_id"),
                "label": lead_done_trace.get("label"),
            },
        )

    def on_subagent_start(self, conversation_id: str, sub_placeholder: Dict[str, Any]) -> None:
        """Sub Agent 占位创建时调用：写入占位轨迹并发送 sub_started 事件。"""
        TraceStorage.append_trace(conversation_id, sub_placeholder)
        event_emit(
            conversation_id,
            {
                "type": "sub_started",
                "agent_id": sub_placeholder.get("agent_id"),
                "label": sub_placeholder.get("label"),
                "lead_id": sub_placeholder.get("lead_id"),
            },
        )

    def on_subagent_end(self, conversation_id: str, sub_final_trace: Dict[str, Any]) -> None:
        """Sub Agent 完成时调用：更新轨迹并发送 sub_done 事件。"""
        agent_id = sub_final_trace.get("agent_id") or ""
        thinking_blocks = sub_final_trace.get("thinking_blocks") or []
        tool_calls = sub_final_trace.get("tool_calls") or []
        status = sub_final_trace.get("status")
        TraceStorage.update_sub_trace(conversation_id, agent_id, thinking_blocks, tool_calls, status=status)
        event_emit(conversation_id, {"type": "sub_done", "agent_id": agent_id})


class ExamAnalysisToolHooks:
    """工具调用 Hook：记录工具调用前后信息、更新轨迹与事件等。"""

    def on_tool_use_start(
        self,
        conversation_id: str,
        agent_id: str,
        tool_call_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        step: int,
    ) -> None:
        """工具调用前调用。默认不做任何操作。"""
        return

    def on_tool_use_end(
        self,
        conversation_id: str,
        agent_id: str,
        tool_call_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result_str: str,
        success: bool,
        step: int,
        thinking_blocks: List[Dict[str, Any]],
        tool_calls_log: List[Dict[str, Any]],
    ) -> None:
        """工具调用后调用。默认追加 call_entry、写入轨迹并发送 sub_tool_call 事件。"""
        status = "success" if success else "error"
        call_entry: Dict[str, Any] = {
            "id": tool_call_id,
            "name": tool_name,
            "arguments": arguments,
            "result": result_str,
            "status": status,
            "step": step,
        }
        tool_calls_log.append(call_entry)
        event_emit(
            conversation_id,
            {"type": "sub_tool_call", "agent_id": agent_id, "call": call_entry},
        )
        TraceStorage.update_sub_trace(conversation_id, agent_id, thinking_blocks, tool_calls_log)


class ExamAnalysisLLMHooks:
    """LLM 调用 Hook：错误与重试等。"""

    def on_llm_retry(
        self,
        conversation_id: str,
        agent_id: str,
        attempt: int,
        max_attempts: int,
        err_msg: str,
        thinking_blocks: List[Dict[str, Any]],
        tool_calls_log: List[Dict[str, Any]],
        step: int,
    ) -> None:
        """LLM 请求失败准备重试时调用：追加重试思考块并刷新轨迹。"""
        block = {
            "title": "重试",
            "content": f"LLM 请求失败，正在第 {attempt}/{max_attempts} 次重试…\n{err_msg}",
            "sequence": len(thinking_blocks),
            "step": step,
        }
        thinking_blocks.append(block)
        event_emit(
            conversation_id,
            {"type": "sub_thinking", "agent_id": agent_id, "block": block},
        )
        TraceStorage.update_sub_trace(conversation_id, agent_id, thinking_blocks, tool_calls_log)


class DefaultExamAnalysisHooks:
    """默认 Hook 集合，对外通过属性暴露各类 Hook 分组。"""

    def __init__(self) -> None:
        self.pipeline = ExamAnalysisPipelineHooks()
        self.agents = ExamAnalysisAgentHooks()
        self.tools = ExamAnalysisToolHooks()
        self.llm = ExamAnalysisLLMHooks()


# 默认单例实例，供 exam_analysis 模块内部直接使用
default_hooks = DefaultExamAnalysisHooks()

