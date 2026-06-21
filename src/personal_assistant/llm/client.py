"""LLM 客户端封装。

基于 OpenAI SDK 的兼容协议接入 DeepSeek。本模块是**协议翻译层**：对上以
:class:`~personal_assistant.core.protocol` 中的类型与 Agent 交互，对下转换成
具体模型的线上格式。更换模型/供应商时，通常只需改配置文件；仅当线上协议
不兼容时才需调整本文件的转换函数。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

from openai import OpenAI

from personal_assistant.config import ModelConfig
from personal_assistant.core.protocol import LLMResponse, Message, TokenUsage, ToolCall, ToolSpec


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
        return LLMResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            usage=self._extract_usage(resp.usage),
        )

    # ------------------------------------------------------------------
    # 流式补全（Agent 主用，文本实时输出 + 工具调用累积）
    # ------------------------------------------------------------------
    def complete_stream(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        *,
        on_chunk: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        """流式补全：文本增量通过 *on_chunk* 回调实时输出，最终返回完整 LLMResponse。

        与 :meth:`complete` 功能相同，但文本内容逐块回调，适用于 CLI 实时输出。
        工具调用的参数会跨多个 chunk 累积，最终拼装为完整的 ToolCall 列表。
        """
        payload = self._common_kwargs([self._message_to_dict(m) for m in messages])
        if tools:
            payload["tools"] = [self._spec_to_dict(t) for t in tools]
        payload["stream"] = True
        # 请求在最后一个 chunk 中包含 usage 统计
        payload["stream_options"] = {"include_usage": True}

        stream = self._client.chat.completions.create(**payload)  # type: ignore[call-overload]

        content_parts: list[str] = []
        tool_calls_map: dict[int, dict[str, Any]] = {}
        usage_obj = None

        for chunk in stream:
            # 部分 provider 在最后一个 chunk 中包含 usage（choices 为空）
            if hasattr(chunk, "usage") and chunk.usage is not None:
                usage_obj = chunk.usage

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # 文本内容
            if delta.content:
                content_parts.append(delta.content)
                if on_chunk:
                    on_chunk(delta.content)

            # 工具调用（跨 chunk 累积）
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_map:
                        tool_calls_map[idx] = {"id": "", "name": "", "args": []}
                    if tc.id:
                        tool_calls_map[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_map[idx]["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_map[idx]["args"].append(tc.function.arguments)

        content = "".join(content_parts)
        tool_calls: list[ToolCall] = []
        for idx in sorted(tool_calls_map):
            tc = tool_calls_map[idx]
            args_str = "".join(tc["args"]) or "{}"
            try:
                arguments = json.loads(args_str)
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCall(id=tc["id"] or f"call_{idx}", name=tc["name"], arguments=arguments)
            )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=self._extract_usage(usage_obj) if usage_obj else None,
        )

    # ------------------------------------------------------------------
    # 纯流式文本（不含工具调用，供简单对话场景）
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

    @staticmethod
    def _extract_usage(usage_obj: Any) -> TokenUsage | None:
        """从 OpenAI 兼容 API 的 usage 对象中提取 token 统计。

        兼容 OpenAI 标准格式（``prompt_tokens_details.cached_tokens``）与
        DeepSeek 扩展格式（``prompt_cache_hit_tokens``）。
        """
        if usage_obj is None:
            return None

        prompt_tokens = getattr(usage_obj, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage_obj, "completion_tokens", 0) or 0
        total_tokens = getattr(usage_obj, "total_tokens", 0) or 0

        # 缓存命中 token：优先取 OpenAI 标准字段，回退到 DeepSeek 扩展字段。
        cached_tokens = 0
        prompt_details = getattr(usage_obj, "prompt_tokens_details", None)
        if prompt_details is not None:
            cached_tokens = getattr(prompt_details, "cached_tokens", 0) or 0
        if not cached_tokens:
            cached_tokens = getattr(usage_obj, "prompt_cache_hit_tokens", 0) or 0

        # 推理 token（DeepSeek-R1 等推理模型会产生）。
        reasoning_tokens = 0
        completion_details = getattr(usage_obj, "completion_tokens_details", None)
        if completion_details is not None:
            reasoning_tokens = getattr(completion_details, "reasoning_tokens", 0) or 0

        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
        )
