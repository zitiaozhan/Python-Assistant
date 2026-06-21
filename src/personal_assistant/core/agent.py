"""Agent —— 工具编排核心。

Agent 维护与模型的对话循环（toolcall 协议）：

1. 把消息连同工具声明发给模型；
2. 若模型请求工具调用 → 执行工具 → 把结果回填到消息 → 回到 1；
3. 若模型给出最终文本回复 → 返回给调用方。

Agent 仅依赖 :mod:`core.protocol` 中的类型，与具体模型完全解耦。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personal_assistant.core.protocol import Message, ToolCall, ToolResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from personal_assistant.core.tool import Tool
    from personal_assistant.llm.client import LLMClient


class Agent:
    """具备工具调用能力的对话 Agent。"""

    def __init__(
        self,
        llm: LLMClient,
        tools: list[Tool] | None = None,
        *,
        system_prompt: str = "",
        max_iterations: int = 10,
        confirm: Callable[[str, dict, str], bool] | None = None,
        on_event: Callable[[str, dict], None] | None = None,
    ) -> None:
        """
        Args:
            llm: 已配置好的 LLM 客户端。
            tools: 可用工具列表；模型从中自选。
            system_prompt: 系统提示词。
            max_iterations: 单轮对话中工具调用循环上限，防止死循环。
            confirm: 工具执行前的确认回调 ``(name, arguments, preview) -> bool``。
                返回 False 则跳过执行并把「用户拒绝」回填给模型。为 None 时自动放行。
            on_event: 中间过程回调，用于 UI 展示。事件名：
                ``"tool_call"``（{"name","arguments"}）、``"tool_result"``（{"name","output"}）。
        """
        self.llm = llm
        self.tools: dict[str, Tool] = {t.name: t for t in (tools or [])}
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.confirm = confirm
        self.on_event = on_event

    def register(self, tool: Tool) -> None:
        """运行时追加一个工具。"""
        self.tools[tool.name] = tool

    def run(self, messages: list[Message]) -> str:
        """驱动一轮对话，直到模型给出最终文本回复。

        ``messages`` 应已包含 system 提示与最新的 user 消息。本方法会把中间的
        assistant / tool 消息追加进去，最后追加最终 assistant 回复，并返回其文本。
        """
        tool_specs = [t.to_spec() for t in self.tools.values()]

        for _ in range(self.max_iterations):
            resp = self.llm.complete(messages, tool_specs or None)

            if not resp.has_tool_calls:
                text = resp.content or ""
                messages.append(Message.assistant(text))
                return text

            # 模型请求工具调用：先记录 assistant 消息（含 tool_calls），再逐个执行。
            messages.append(Message.assistant(content=resp.content, tool_calls=resp.tool_calls))
            for call in resp.tool_calls:
                result = self._execute(call)
                messages.append(Message.tool(call.id, call.name, self._format_result(result)))

        exhausted = "(已达到最大工具调用轮次，强制结束。)"
        messages.append(Message.assistant(exhausted))
        return exhausted

    def _execute(self, call: ToolCall) -> ToolResult:
        tool = self.tools.get(call.name)
        if tool is None:
            return ToolResult(call.id, call.name, f"未知工具：{call.name}", is_error=True)

        # 确认门禁（CLI 交互时可由用户放行/拒绝；为 None 时自动放行）。
        if self.confirm is not None:
            preview = self._preview(call.name, call.arguments)
            if not self.confirm(call.name, call.arguments, preview):
                return ToolResult(call.id, call.name, "用户拒绝了本次工具调用。", is_error=True)

        if self.on_event:
            self.on_event("tool_call", {"name": call.name, "arguments": call.arguments})
        try:
            output = tool.run(call.arguments)
        except Exception as exc:  # noqa: BLE001 - 顶层兜底，保证循环不被工具异常打断
            return ToolResult(call.id, call.name, f"工具执行抛出异常：{exc!r}", is_error=True)
        if self.on_event:
            self.on_event("tool_result", {"name": call.name, "output": output})
        return ToolResult(call.id, call.name, output)

    @staticmethod
    def _preview(name: str, arguments: dict) -> str:
        """生成供确认提示展示的单行预览。"""
        if name == "bash":
            return str(arguments.get("command", ""))
        return repr(arguments)

    @staticmethod
    def _format_result(result: ToolResult) -> str:
        prefix = "[错误] " if result.is_error else ""
        return f"{prefix}{result.output}"
