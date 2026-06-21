"""Bash 工具：执行 shell 命令并返回输出。

执行环境为 Windows 上的 Git Bash（``bash -c "<command>"``）。``~`` 会展开为
用户主目录，故 ``~/Desktop/test.txt`` 即用户桌面。强制 UTF-8 环境变量，确保
中文读写不乱码。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

from personal_assistant.core.tool import Tool

_DEFAULT_TIMEOUT = 60


class BashTool(Tool):
    name = "bash"
    description = (
        "在用户的电脑上执行一条 bash 命令，返回标准输出、标准错误与退出码。"
        "运行环境为 Windows 上的 Git Bash：路径使用正斜杠；"
        "家目录 ~ 会展开为用户主目录（例如 ~/Desktop 即用户桌面）。"
        "可用于创建/读写文件、运行脚本、查询系统信息等。"
        '示例：创建文件 echo "内容" > ~/Desktop/file.txt'
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 bash 命令",
            }
        },
        "required": ["command"],
    }

    def __init__(self, *, cwd: str | None = None, timeout: int = _DEFAULT_TIMEOUT) -> None:
        self.cwd = cwd or os.path.expanduser("~")
        self.timeout = timeout
        self._bash = shutil.which("bash")

    def run(self, arguments: dict[str, Any]) -> str:
        command = arguments.get("command")
        if not isinstance(command, str) or not command.strip():
            return "错误：缺少参数 command"
        env = self._utf8_env()
        try:
            if self._bash:
                proc = subprocess.run(
                    [self._bash, "-c", command],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=self.cwd,
                    timeout=self.timeout,
                    env=env,
                )
            else:
                # 没有 bash 时退化为系统默认 shell（仅作兜底）。
                proc = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=self.cwd,
                    timeout=self.timeout,
                    env=env,
                )
        except subprocess.TimeoutExpired:
            return f"$ {command}\n[超时：超过 {self.timeout}s 未完成]"
        out = proc.stdout or ""
        err = proc.stderr or ""
        parts = [f"$ {command}", f"[exit {proc.returncode}]"]
        if out:
            parts.append(out.rstrip("\n"))
        if err:
            parts.append(f"[stderr]\n{err.rstrip('\n')}")
        return "\n".join(parts)

    @staticmethod
    def _utf8_env() -> dict[str, str]:
        env = dict(os.environ)
        # 促使 Git Bash 以 UTF-8 处理字符，避免中文乱码。
        env.setdefault("LANG", "C.UTF-8")
        env.setdefault("LC_ALL", "C.UTF-8")
        return env
