"""命令行入口。

``python -m personal_assistant`` 与安装后的 ``personal-assistant`` 命令
都会调用 :func:`personal_assistant.cli.run` 启动 REPL。
"""

from __future__ import annotations

import sys

from personal_assistant import __version__
from personal_assistant.cli import run


def main() -> int:
    """Entry point for the ``personal-assistant`` console script."""
    print(f"Personal Assistant v{__version__}\n")
    return run()


if __name__ == "__main__":
    sys.exit(main())
