"""Agent base class.

The :class:`Agent` is the central coordinator: it receives an intent,
decides which capability should handle it, and orchestrates the response.
The concrete orchestration logic (LLM calls, planning, memory, etc.) will
be implemented in later milestones.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from personal_assistant.core.plugin import Capability


class Agent:
    """Base class for all assistant agents.

    Subclasses are expected to override :meth:`handle`. The default
    implementation is a placeholder that signals the agent is not yet
    wired up.
    """

    name: str = "base-agent"

    def __init__(self, *, capabilities: list[Capability] | None = None) -> None:
        self.capabilities: list[Capability] = list(capabilities or [])

    def register(self, capability: Capability) -> None:
        """Attach a new :class:`Capability` to this agent."""
        self.capabilities.append(capability)

    async def handle(self, intent: str, context: dict[str, Any] | None = None) -> Any:
        """Handle an incoming intent.

        Args:
            intent: A natural-language or structured request.
            context: Optional shared context (session, device info, ...).

        Note:
            Not yet implemented. Concrete subclasses will provide behavior.
        """
        raise NotImplementedError(
            f"{type(self).__name__}.handle() is not implemented yet."
        )
