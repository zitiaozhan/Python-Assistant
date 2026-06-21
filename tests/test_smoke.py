"""Smoke tests verifying the skeleton imports and basic structure.

These do not exercise real functionality (none exists yet); they only
guard the project layout against accidental breakage.
"""

from __future__ import annotations

import pytest

import personal_assistant
from personal_assistant.core import Agent, Capability, Plugin


def test_version_string() -> None:
    assert isinstance(personal_assistant.__version__, str)
    assert personal_assistant.__version__.count(".") >= 1


def test_agent_base_handle_is_not_implemented() -> None:
    agent = Agent()
    with pytest.raises(NotImplementedError):
        import asyncio

        asyncio.run(agent.handle("hello"))


def test_plugin_can_register_capability() -> None:
    class Echo(Capability):
        name = "echo"

        def can_handle(self, intent: str) -> bool:
            return intent.startswith("echo:")

        async def run(self, intent: str, context=None) -> str:
            return intent[len("echo:") :].strip()

    plugin = Plugin()
    cap = Echo()
    plugin.register(cap)
    assert plugin.capabilities == [cap]

    agent = Agent(capabilities=plugin.capabilities)
    assert agent.capabilities[0].can_handle("echo: hi")
