"""LLM 客户端封装。

基于 OpenAI SDK 的兼容协议接入 DeepSeek。本模块是**协议翻译层**：对上以
:class:`~personal_assistant.core.protocol` 中的类型与 Agent 交互，对下转换成
具体模型的线上格式。更换模型/供应商时，通常只需改配置文件；仅当线上协议
不兼容时才需调整本文件的转换函数。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from openai import OpenAI

from personal_assistant.config import ModelConfig
from personal_assistant.core.protocol import LLMResponse, Message, ToolCall, ToolSpec


class LLMClient:
    """对大模型 API 的封装，提供工具感知的补全接口与流式文本接口。"""

    def __init__(self, config: ModelConfig) -> None:
        self._config = config
        self._client = OpenAI(base_url=config.base_url, api_key=config.api_key)

    @property
    def model_name(self) -> str:
        return self._config.model

    # ------------------------------------------------------------------
    # 工具感知补全（Agent 主用）
    # ------------------------------------------------------------------
    def complete(self, messages: list[Message], tools: list[ToolSpec] | None = None) -> LLMResponse:
        """非流式补全：返回最终文本或模型请求的工具调用。

        Args:
            messages: 内部 :class:`Message` 列表（含完整多轮 + 工具结果）。
            tools: 可用工具声明；为空则不启用工具调用，模型直接回复文本。
        """
        payload = self._common_kwargs([self._message_to_dict(m) for m in messages])
        if tools:
            payload["tools"] = [self._spec_to_dict(t) for t in tools]
        payload["stream"] = False
        resp = self._client.chat.completions.create(**payload)  # type: ignore[call-overload]
        msg = resp.choices[0].message

        tool_calls: list[ToolCall] = []
        for tc in msg.tool_calls or []:
            args_str = tc.function.arguments or "{}"
            try:
                arguments = json.loads(args_str)
            except json.JSONDecodeError:
                # 模型偶发返回非法 JSON，降级为空字典，由工具自身报缺参。
                arguments = {}
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=arguments))
        return LLMResponse(content=msg.content or "", tool_calls=tool_calls)

    # ------------------------------------------------------------------
    # 流式文本（纯对话场景，供未来按需使用）
    # ------------------------------------------------------------------
    def chat(self, messages: list[Message]) -> Iterator[str]:
        """流式对话：逐块 ``yield`` 文本增量（不含工具调用）。"""
        payload = self._common_kwargs([self._message_to_dict(m) for m in messages])
        stream = self._client.chat.completions.create(stream=True, **payload)  # type: ignore[call-overload]
        for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

    # ------------------------------------------------------------------
    # 协议翻译：内部类型 ↔ 模型线上格式
    # ------------------------------------------------------------------
    @staticmethod
    def _message_to_dict(m: Message) -> dict[str, Any]:
        if m.role in ("system", "user"):
            return {"role": m.role, "content": m.content or ""}
        if m.role == "assistant":
            d: dict[str, Any] = {"role": "assistant", "content": m.content or ""}
            if m.tool_calls:
                d["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                    for tc in m.tool_calls
                ]
            return d
        if m.role == "tool":
            return {
                "role": "tool",
                "tool_call_id": m.tool_call_id,
                "content": m.content or "",
            }
        return {"role": m.role, "content": m.content or ""}

    @staticmethod
    def _spec_to_dict(spec: ToolSpec) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            },
        }

    def _common_kwargs(self, wire_messages: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "model": self._config.model,
            "messages": wire_messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            **self._config.extra,
        }
