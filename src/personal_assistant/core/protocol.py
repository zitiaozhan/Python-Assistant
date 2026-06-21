"""Agent ↔ 模型 之间的交互协议（与具体模型解耦）。

本模块定义 Agent 与 :class:`~personal_assistant.llm.client.LLMClient` 之间
约定的数据结构。Agent 只操作这些类型，**完全不感知** OpenAI/DeepSeek 的线上
格式；由 LLMClient 负责双向翻译。

更换模型供应商时，只需调整 client 的转换逻辑，Agent 与工具代码无需改动——
这正是「协议与模型解耦」的边界。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSpec:
    """向模型声明的工具能力（名称 + 描述 + 参数 JSON Schema）。"""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolCall:
    """模型请求发起的一次工具调用（arguments 已解析为 dict）。"""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """工具执行结果，回填给模型。"""

    call_id: str
    name: str
    output: str
    is_error: bool = False


@dataclass
class Message:
    """对话中的一条消息，统一覆盖 system / user / assistant / tool 四种角色。"""

    role: str
    content: str | None = None
    # 仅 assistant 角色使用：模型决定发起的工具调用。
    tool_calls: list[ToolCall] | None = None
    # 仅 tool 角色使用：对应的工具调用 id 与工具名。
    tool_call_id: str | None = None
    name: str | None = None

    @classmethod
    def system(cls, content: str) -> Message:
        return cls("system", content)

    @classmethod
    def user(cls, content: str) -> Message:
        return cls("user", content)

    @classmethod
    def assistant(
        cls, content: str | None = None, tool_calls: list[ToolCall] | None = None
    ) -> Message:
        return cls("assistant", content=content, tool_calls=tool_calls)

    @classmethod
    def tool(cls, call_id: str, name: str, output: str) -> Message:
        return cls("tool", content=output, tool_call_id=call_id, name=name)


@dataclass
class LLMResponse:
    """LLMClient.complete 的返回：要么是最终文本回复，要么是工具调用请求。"""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)
