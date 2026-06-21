"""Plugin / capability extension points.

The assistant is designed to grow indefinitely via plugins. A
:class:`Plugin` bundles one or more :class:`Capability` objects; each
capability declares what kinds of intents it can handle. The discovery
and dispatch mechanism will be implemented in a later milestone.
"""

from __future__ import annotations

import abc
from typing import Any


class Capability(abc.ABC):
    """A single unit of functionality the assistant can perform.

    Subclasses implement :meth:`can_handle` and :meth:`run`.
    """

    #: Human-readable name, e.g. ``"clipboard-sync"``.
    name: str = "capability"

    @abc.abstractmethod
    def can_handle(self, intent: str) -> bool:
        """Return whether this capability should serve the given intent."""

    @abc.abstractmethod
    async def run(self, intent: str, context: dict[str, Any] | None = None) -> Any:
        """Execute the capability for the given intent."""


class Plugin:
    """A bundle of related :class:`Capability` objects.

    Plugins are the recommended unit of distribution: a third party can
    ship ``personal-assistant-foo`` exposing a :class:`Plugin` that the
    core agent loads at startup.
    """

    name: str = "plugin"

    def __init__(self, capabilities: list[Capability] | None = None) -> None:
        self.capabilities: list[Capability] = list(capabilities or [])

    def register(self, capability: Capability) -> None:
        self.capabilities.append(capability)
