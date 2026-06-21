"""Command-line entry point.

Run with: ``python -m personal_assistant`` or ``personal-assistant``.
The current implementation only prints version information; real CLI
subcommands will be added as features land.
"""

from __future__ import annotations

import sys

from personal_assistant import __version__


def main() -> int:
    """Entry point for the ``personal-assistant`` console script."""
    print(f"Personal Assistant v{__version__}")
    print("Skeleton initialized. No functionality implemented yet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
