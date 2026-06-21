"""LLM 客户端封装。

基于 OpenAI SDK 的兼容协议接入 DeepSeek。通过 :class:`~personal_assistant.config.ModelConfig`
驱动，更换模型/供应商无需改代码——只要对方提供 OpenAI 兼容的 ``base_url``。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from openai import OpenAI

from personal_assistant.config import ModelConfig


class LLMClient:
    """对大模型 API 的薄封装，提供流式与非流式两种对话接口。"""

    def __init__(self, config: ModelConfig) -> None:
        self._config = config
        self._client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
        )

    @property
    def model_name(self) -> str:
        return self._config.model

    def chat(self, messages: list[dict[str, str]]) -> Iterator[str]:
        """流式对话：逐块 ``yield`` 文本增量。

        Args:
            messages: OpenAI 消息格式 ``[{"role": ..., "content": ...}, ...]``。
                      调用方负责维护多轮上下文（通常在前面插入 system_prompt）。

        Yields:
            模型输出的文本片段（增量）。
        """
        kwargs = self._common_kwargs(messages)
        # stream=True 时返回的是迭代器。
        stream = self._client.chat.completions.create(stream=True, **kwargs)  # type: ignore[call-overload]
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    def chat_once(self, messages: list[dict[str, str]]) -> str:
        """非流式对话：一次性返回完整文本。便于测试或简单调用。"""
        kwargs = self._common_kwargs(messages)
        kwargs["stream"] = False
        resp = self._client.chat.completions.create(**kwargs)  # type: ignore[call-overload]
        return resp.choices[0].message.content or ""

    def _common_kwargs(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "model": self._config.model,
            "messages": messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            **self._config.extra,
        }
