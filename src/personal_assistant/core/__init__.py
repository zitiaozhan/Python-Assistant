"""Core abstractions of the assistant.

This subpackage defines the foundational protocols and base classes that
every part of the system builds upon. See ``agent`` and ``plugin``.
"""

from personal_assistant.core.agent import Agent
from personal_assistant.core.plugin import Capability, Plugin

__all__ = ["Agent", "Capability", "Plugin"]
