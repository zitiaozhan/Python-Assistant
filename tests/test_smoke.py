"""Smoke tests verifying the skeleton imports and basic structure.

These do not exercise real functionality (none exists yet); they only
guard the project layout against accidental breakage.
"""

from __future__ import annotations

import personal_assistant


def test_version_string() -> None:
    assert isinstance(personal_assistant.__version__, str)
    assert personal_assistant.__version__.count(".") >= 1
