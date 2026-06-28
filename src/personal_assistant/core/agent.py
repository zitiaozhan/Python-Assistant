"""Agent —— 工具编排核心。

Agent 维护与模型的对话循环（toolcall 协议）：

1. 把消息连同工具声明发给模型；
2. 若模型请求工具调用 → 执行工具 → 把结果回填到消息 → 回到 1；
3. 若模型给出最终文本回复 → 返回给调用方。

Agent 仅依赖 :mod:`core.protocol` 中的类型，与具体模型完全解耦。

系统提示词变量
---------------
系统提示词中可使用 ``{{variable_name}}`` 格式的变量占位符。Agent 在每次对话前
会提取这些变量、解析其值，并追加到提示词**末尾**——原文中的占位符不被替换，
以最大化 prompt cache 命中率。

内置变量：``{{current_time}}``、``{{current_date}}``、``{{os}}``。
可通过 :meth:`Agent.register_var` 注册自定义变量。

示例::

    system_prompt = "你是一个个人助理。当前时间：{{current_time}}"
    # 实际发给模型的内容：
    #   你是一个个人助理。当前时间：{{current_time}}
    #
    #   ---variables---
    #   current_time: 2025-06-21 14:30:00
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from personal_assistant.core.protocol import Message, TokenUsage, ToolCall, ToolResult
from personal_assistant.core.skill import SkillFolder, SkillManager

if TYPE_CHECKING:
    from collections.abc import Callable

    from personal_assistant.core.tool import Tool
    from personal_assistant.llm.client import LLMClient

#: 变量占位符正则：匹配 ``{{variable_name}}``
_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")
#: 变量值追加的分隔标记（下次 run 时据此剥离旧值，再重新解析）
_VAR_SEPARATOR = "\n\n---variables---\n"


def _default_var_resolvers() -> dict[str, Callable[[], str]]:
    """返回内置变量解析器。"""
    import platform
    from datetime import datetime

    return {
        "current_time": lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "current_date": lambda: datetime.now().strftime("%Y-%m-%d"),
        "os": lambda: f"{platform.system()} {platform.release()}",
    }


class Agent:
    """具备工具调用能力的对话 Agent。"""

    def __init__(
        self,
        llm: LLMClient,
        tools: list[Tool] | None = None,
        *,
        system_prompt: str = "",
        max_iterations: int = 200,
        confirm: Callable[[str, dict, str], bool] | None = None,
        on_event: Callable[[str, dict], None] | None = None,
        skills: SkillManager | None = None,
        var_resolvers: dict[str, Callable[[], str]] | None = None,
        max_messages: int = 500,
        auto_compress: bool = True,
    ) -> None:
        """
        Args:
            llm: 已配置好的 LLM 客户端。
            tools: 可用工具列表；模型从中自选。
            system_prompt: 系统提示词。可包含 ``{{变量名}}`` 占位符，
                Agent 会在每次对话前解析并追加到末尾（不替换原文，利于 prompt cache）。
            max_iterations: 单轮对话中工具调用循环上限，防止死循环。
            confirm: 工具执行前的确认回调 ``(name, arguments, preview) -> bool``。
                返回 False 则跳过执行并把「用户拒绝」回填给模型。为 None 时自动放行。
            on_event: 中间过程回调，用于 UI 展示。事件名：
                ``"tool_call"``（{"name","arguments"}）、``"tool_result"``（{"name","output"}）。
            skills: 技能管理器；传入后会自动注册 ``use_skill`` 工具，
                模型即可通过 toolcall 调用已注册的技能。为 None 时创建空管理器。
            var_resolvers: 自定义变量解析器，覆盖或补充内置变量。
                键为变量名（不含花括号），值为无参 callable 返回字符串。
        """
        self.llm = llm
        self.tools: dict[str, Tool] = {t.name: t for t in (tools or [])}
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.confirm = confirm
        self.on_event = on_event
        self.skill_manager = skills or SkillManager()
        #: 最近一轮对话的累计 token 消耗（run() 结束后更新）。
        self.last_usage = TokenUsage()
        #: 最大消息数阈值，超过此数量将触发上下文压缩。
        self.max_messages = max_messages
        #: 是否自动压缩上下文。
        self.auto_compress = auto_compress
        #: 上下文压缩次数计数。
        self._compression_count = 0
        # 系统提示词变量解析器：内置默认 + 用户自定义。
        self._var_resolvers: dict[str, Callable[[], str]] = _default_var_resolvers()
        if var_resolvers:
            self._var_resolvers.update(var_resolvers)
        # 注册 use_skill 工具，让模型能调用已注册的技能。
        self._register_use_skill()

    def register(self, tool: Tool) -> None:
        """运行时追加一个工具。"""
        self.tools[tool.name] = tool

    def register_var(self, name: str, resolver: Callable[[], str]) -> None:
        """注册一个系统提示词变量解析器。

        Args:
            name: 变量名（对应 ``{{name}}`` 中的 name）。
            resolver: 无参可调用对象，返回变量的字符串值。
                每次 :meth:`run` 时会被调用，确保时间敏感变量始终最新。
        """
        self._var_resolvers[name] = resolver

    def _process_system_prompt(self, content: str) -> str:
        """处理系统提示词：提取 ``{{变量}}`` 并将解析值追加到末尾。

        原文中的 ``{{变量}}`` 占位符**不被替换**（保持 prompt cache 命中），
        变量的实际值以 ``变量名: 值`` 的格式追加到提示词末尾。

        每次 :meth:`run` 调用时会重新解析，确保时间敏感变量（如 current_time）始终最新。
        上轮追加的旧值通过 :data:`_VAR_SEPARATOR` 标记剥离，不会累积。
        """
        # 剥离上轮追加的变量值，还原 base prompt
        base = content.split(_VAR_SEPARATOR, 1)[0]

        # 提取所有变量名（去重、保序）
        found = _VAR_PATTERN.findall(base)
        if not found:
            return base

        seen: set[str] = set()
        lines: list[str] = []
        for name in found:
            if name in seen:
                continue
            seen.add(name)
            resolver = self._var_resolvers.get(name)
            if resolver is not None:
                try:
                    value = resolver()
                except Exception:  # noqa: BLE001 - 解析失败不中断对话
                    value = "(解析失败)"
                lines.append(f"{name}: {value}")

        if not lines:
            return base

        return base + _VAR_SEPARATOR + "\n".join(lines)

    def add_skill(self, skill: SkillFolder) -> None:
        """运行时注册一个技能文件夹。模型在下一轮对话中即可使用。"""
        self.skill_manager.register(skill)

    def add_skill_from_folder(self, folder_path: str) -> None:
        """从文件夹路径加载并注册一个技能。"""
        self.skill_manager.register(SkillFolder(folder_path))

    def remove_skill(self, name: str) -> bool:
        """运行时移除一个技能，返回是否成功。"""
        return self.skill_manager.unregister(name)

    def _estimate_tokens(self, messages: list[Message]) -> int:
        """估算消息列表的 token 数量（粗略估算）。

        1 中文字 ≈ 1.5 token，1 英文词 ≈ 1.3 token。
        """
        total = 0
        for msg in messages:
            text = msg.content or ""
            # 粗略估算：中文字符数 * 1.5 + 英文单词数 * 1.3
            chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
            english_words = len(re.findall(r'[a-zA-Z]+', text))
            total += int(chinese_chars * 1.5 + english_words * 1.3)
        return total

    def _compress_context(self, messages: list[Message]) -> list[Message]:
        """压缩上下文：总结旧消息为摘要，保留最近消息。

        Args:
            messages: 当前消息列表（应已包含 system prompt 和用户最新消息）。

        Returns:
            压缩后的新消息列表。
        """
        # 如果禁用自动压缩，直接返回原消息
        if not self.auto_compress:
            return messages

        if len(messages) <= self.max_messages:
            return messages

        # 保留 system prompt 和最近一半的消息
        system_msg = messages[0] if messages[0].role == "system" else None
        recent_count = self.max_messages // 2
        recent_messages = messages[-recent_count:]

        # 需要压缩的旧消息（不包括 system 和最近消息）
        if system_msg:
            old_messages = messages[1 : len(messages) - len(recent_messages)]
        else:
            old_messages = messages[: len(messages) - len(recent_messages)]

        if not old_messages:
            return messages

        # 调用 LLM 生成摘要
        summary_prompt = Message.system(
            "请总结以下对话历史的关键信息，包括：\n"
            "1. 用户的主要需求和意图\n"
            "2. 已完成的任务和重要结果\n"
            "3. 正在进行中的任务状态\n"
            "4. 重要的上下文信息\n"
            "总结要简洁（不超过 200 字），但保留所有关键信息。"
        )

        # 只取前 20 条旧消息避免过长
        summary_messages = [summary_prompt] + old_messages[:20]

        try:
            # 调用 LLM 生成摘要（不携带工具，避免复杂化）
            resp = self.llm.complete(summary_messages, tools=None)
            summary_text = resp.content or "历史对话摘要生成失败。"
        except Exception:  # noqa: BLE001 - 摘要生成失败不影响对话
            summary_text = "历史对话因过长已被截断，部分信息可能丢失。"

        # 创建摘要消息
        self._compression_count += 1
        summary_msg = Message.system(
            f"[上下文压缩摘要 - 第 {self._compression_count} 次压缩]\n{summary_text}"
        )

        # 通知压缩事件
        if self.on_event:
            self.on_event(
                "context_compressed",
                {
                    "old_messages": len(old_messages),
                    "new_messages": len(recent_messages) + 2,  # +2: system + summary
                    "compression_count": self._compression_count,
                    "summary": summary_text[:100],
                },
            )

        # 重组消息：system + 摘要 + 最近消息
        compressed: list[Message] = []
        if system_msg:
            compressed.append(system_msg)
        compressed.append(summary_msg)
        compressed.extend(recent_messages)

        return compressed

    def _register_use_skill(self) -> None:
        """注册 use_skill 工具（延迟导入避免循环依赖）。"""
        from personal_assistant.skills import UseSkillTool

        self.tools["use_skill"] = UseSkillTool(self.skill_manager)

    def run(
        self,
        messages: list[Message],
        *,
        on_chunk: Callable[[str], None] | None = None,
    ) -> str:
        """驱动一轮对话，直到模型给出最终文本回复。

        ``messages`` 应已包含 system 提示与最新的 user 消息。本方法会把中间的
        assistant / tool 消息追加进去，最后追加最终 assistant 回复，并返回其文本。

        Args:
            on_chunk: 流式回调，模型每产出一块文本就调用一次。传入时使用流式 API，
                文本实时输出；为 None 时使用非流式 API。工具调用阶段不会触发回调。

        执行完毕后，:attr:`last_usage` 更新为本轮对话中所有模型调用的 token 总消耗。
        """
        # 处理系统提示词变量：解析 {{变量}} 并将值追加到末尾（不替换原文）
        if messages and messages[0].role == "system":
            processed = self._process_system_prompt(messages[0].content or "")
            messages[0] = Message.system(processed)

        # 检查是否需要压缩上下文（自动触发）
        if self.auto_compress and len(messages) > self.max_messages:
            messages = self._compress_context(messages)

        tool_specs = [t.to_spec() for t in self.tools.values()]
        total_usage = TokenUsage()

        for _ in range(self.max_iterations):
            if on_chunk is not None:
                resp = self.llm.complete_stream(messages, tool_specs or None, on_chunk=on_chunk)
            else:
                resp = self.llm.complete(messages, tool_specs or None)
            if resp.usage is not None:
                total_usage = total_usage + resp.usage

            if not resp.has_tool_calls:
                text = resp.content or ""
                messages.append(Message.assistant(text))
                self.last_usage = total_usage
                return text

            # 模型请求工具调用：先记录 assistant 消息（含 tool_calls），再逐个执行。
            messages.append(Message.assistant(content=resp.content, tool_calls=resp.tool_calls))
            for call in resp.tool_calls:
                result = self._execute(call)
                messages.append(Message.tool(call.id, call.name, self._format_result(result)))

        exhausted = "(已达到最大工具调用轮次，强制结束。)"
        if on_chunk:
            on_chunk(exhausted)
        messages.append(Message.assistant(exhausted))
        self.last_usage = total_usage
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
        if name == "use_skill":
            skill_name = arguments.get("skill_name", "")
            return f"技能: {skill_name}"
        return repr(arguments)

    @staticmethod
    def _format_result(result: ToolResult) -> str:
        prefix = "[错误] " if result.is_error else ""
        return f"{prefix}{result.output}"
