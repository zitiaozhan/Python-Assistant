"""Core abstractions of the assistant.

This subpackage defines the foundational protocols and base classes that
every part of the system builds upon: the orchestration :class:`Agent`,
the tool-calling protocol (see :mod:`personal_assistant.core.protocol`),
and the :class:`Tool` base class.
"""

from personal_assistant.core.agent import Agent
from personal_assistant.core.plugin import Capability, Plugin
from personal_assistant.core.skill import SkillFolder, SkillManager
from personal_assistant.core.tool import Tool

__all__ = ["Agent", "Capability", "Plugin", "SkillFolder", "SkillManager", "Tool"]
