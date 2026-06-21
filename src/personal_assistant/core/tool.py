"""Tool 抽象基类。

每个工具声明自己的 ``name``、``description`` 与参数 JSON Schema（``parameters``），
并实现 :meth:`run`。工作流程：

1. Agent 把各工具的 :meth:`to_spec` 结果（:class:`ToolSpec`）随消息一起发给模型；
2. 模型自行决定是否调用、调用哪个工具（toolcall 协议）；
3. Agent 拿到 :class:`ToolCall` 后，按 ``name`` 找到工具实例并执行 :meth:`run`。

新增工具请参考 ``src/personal_assistant/tools/README.md``。
"""

from __future__ import annotations

import abc
from typing import Any

from personal_assistant.core.protocol import ToolSpec


class Tool(abc.ABC):
    """所有工具的基类。子类需覆盖三个类属性与 :meth:`run`。"""

    name: str = "tool"
    description: str = ""
    parameters: dict[str, Any] = {}

    @abc.abstractmethod
    def run(self, arguments: dict[str, Any]) -> str:
        """执行工具，返回给模型可见的文本结果。

        Args:
            arguments: 模型给出的、已按 ``parameters`` JSON Schema 解析好的参数。
        Returns:
            纯文本结果（含足够信息让模型继续推理）。
        """

    def to_spec(self) -> ToolSpec:
        """转换为可发给模型的 :class:`ToolSpec`。"""
        return ToolSpec(name=self.name, description=self.description, parameters=self.parameters)
