"""LLM 客户端层。

封装对大模型 API 的调用。当前使用 OpenAI 兼容协议接入 DeepSeek；
换用其它兼容供应商（如 OpenAI、Moonshot、通义千问等）只需改配置文件。
"""

from personal_assistant.llm.client import LLMClient

__all__ = ["LLMClient"]
