"""命令行交互主程序（REPL）。

启动一个带工具能力的 Agent：在循环中读取用户输入 → 交给 Agent 编排
（Agent 自主决定是否调用工具）→ 打印最终回复与中间过程。

支持的斜杠命令：
- ``/exit`` / ``/quit``：退出
- ``/clear``：清空当前对话历史
- ``/help``：显示帮助
"""

from __future__ import annotations

import sys

from personal_assistant.config import ConfigError, load_config
from personal_assistant.core.agent import Agent
from personal_assistant.core.protocol import Message
from personal_assistant.llm.client import LLMClient
from personal_assistant.tools import default_tools

_BANNER = (
    "Personal Assistant 已就绪。直接输入消息即可；"
    "Agent 会自主决定是否调用工具。输入 /help 查看命令，/exit 退出。"
)
_HELP = """可用命令：
  /exit, /quit   退出程序
  /clear         清空当前对话历史
  /help          显示本帮助
其余输入将作为消息发送给 Agent（可能触发工具调用）。"""
_EXIT_OK = 0
_EXIT_CONFIG_ERROR = 2


def _confirm_tool(name: str, arguments: dict, preview: str) -> bool:
    """工具执行前的确认提示。"""
    print(f"\n[工具调用] {name}: {preview}")
    try:
        ans = input("  允许执行？[Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return ans in ("", "y", "yes")


def _on_event(event: str, data: dict) -> None:
    """展示 Agent 的中间过程（工具调用结果）。"""
    if event == "tool_result":
        print(f"  [结果] {data['name']}: {data['output']}")


def run() -> int:
    """启动 CLI REPL。返回进程退出码。"""
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"[配置错误] {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR

    llm = LLMClient(config)
    agent = Agent(
        llm,
        tools=default_tools(),
        system_prompt=config.system_prompt,
        confirm=_confirm_tool,
        on_event=_on_event,
    )

    print(_BANNER)
    print(f"[模型] {config.model} @ {config.base_url}")
    print(f"[工具] {', '.join(t.name for t in agent.tools.values())}\n")

    history: list[Message] = [Message.system(config.system_prompt)]
    while True:
        try:
            user_input = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            return _EXIT_OK
        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in ("/exit", "/quit"):
            print("再见。")
            return _EXIT_OK
        if cmd == "/clear":
            history = [Message.system(config.system_prompt)]
            print("[已清空对话历史]\n")
            continue
        if cmd == "/help":
            print(_HELP, "\n")
            continue

        history.append(Message.user(user_input))
        print("助理 > ", end="", flush=True)
        try:
            reply = agent.run(history)
        except Exception as exc:  # noqa: BLE001 - 顶层兜底，保证 REPL 不崩
            print(f"\n[Agent 失败] {exc}\n", file=sys.stderr)
            history.pop()
            continue
        print(reply, "\n")


def main() -> int:
    """``personal-assistant`` 命令入口。"""
    return run()


if __name__ == "__main__":
    sys.exit(run())
