"""内置工具集合。

新增工具后，在 :func:`default_tools` 中注册即可被 Agent 默认启用。
"""

from __future__ import annotations

from personal_assistant.core.tool import Tool
from personal_assistant.tools.bash import BashTool

__all__ = ["BashTool", "default_tools"]


def default_tools() -> list[Tool]:
    """返回默认启用的工具实例列表。"""
    return [BashTool()]
