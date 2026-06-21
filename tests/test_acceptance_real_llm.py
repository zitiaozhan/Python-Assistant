"""验收测试：用真实 DeepSeek 让 Agent 自主在桌面创建 test.txt。

本测试会：
1. 调用真实模型 API（消耗额度）；
2. 在用户桌面创建文件 ~/Desktop/test.txt。

默认 skip，避免 CI / 常规 ``pytest`` 误触发。手动跑通即视为本里程碑达标：

    uv run pytest tests/test_acceptance_real_llm.py -s --run-real-llm

在 conftest.py 中注册了 ``--run-real-llm`` 开关。
"""

from __future__ import annotations

import os

import pytest

from personal_assistant.config import load_config
from personal_assistant.core.agent import Agent
from personal_assistant.core.protocol import Message
from personal_assistant.llm.client import LLMClient
from personal_assistant.tools import default_tools

_DESKTOP = os.path.expanduser("~/Desktop/test.txt")
_EXPECTED = "这就是我的逃跑路线"


@pytest.mark.skipif(
    "not config.getoption('--run-real-llm')",
    reason="需要 --run-real-llm 才运行（会调用真实模型并在桌面建文件）",
)
def test_agent_creates_desktop_file() -> None:
    config = load_config()
    llm = LLMClient(config)
    # confirm=None：测试场景自动放行所有工具调用。
    agent = Agent(
        llm,
        tools=default_tools(),
        system_prompt=config.system_prompt,
        confirm=None,
    )

    reply = agent.run(
        [
            Message.system(config.system_prompt),
            Message.user(f"请在我的桌面创建一个 test.txt，内容是「{_EXPECTED}」。"),
        ]
    )
    print("\n[Agent 最终回复]", reply)

    # 结束条件：文件存在 + 内容正确（UTF-8 无乱码）。
    assert os.path.exists(_DESKTOP), f"桌面未找到 {_DESKTOP}"
    content = open(_DESKTOP, encoding="utf-8").read()  # noqa: SIM115
    assert _EXPECTED in content, f"文件内容异常：{content!r}"
