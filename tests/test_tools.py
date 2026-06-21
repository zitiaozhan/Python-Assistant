"""工具单元测试：不依赖模型，验证工具自身的 ``run`` 行为。"""

from __future__ import annotations

import os

from personal_assistant.tools.bash import BashTool


def test_bash_missing_command_arg() -> None:
    out = BashTool().run({})
    assert "错误" in out or "command" in out


def test_bash_runs_simple_command() -> None:
    out = BashTool().run({"command": "echo hello"})
    assert "hello" in out
    assert "[exit 0]" in out


def test_bash_reports_nonzero_exit() -> None:
    out = BashTool().run({"command": "exit 7"})
    assert "[exit 7]" in out


def test_bash_handles_chinese_and_home_path(tmp_path, monkeypatch) -> None:
    """bash 工具能在 ~ 下创建含中文的文件并正确读回（UTF-8 不乱码）。"""
    monkeypatch.setenv("HOME", str(tmp_path))
    tool = BashTool()
    tool.cwd = str(tmp_path)

    tool.run({"command": 'echo "这就是我的逃跑路线" > test.txt'})
    out = tool.run({"command": "cat test.txt"})

    assert "这就是我的逃跑路线" in out
    assert os.path.exists(os.path.join(tmp_path, "test.txt"))
