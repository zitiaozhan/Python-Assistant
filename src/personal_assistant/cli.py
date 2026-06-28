"""命令行交互主程序（REPL）。

启动一个带工具能力的 Agent：在循环中读取用户输入 → 交给 Agent 编排
（Agent 自主决定是否调用工具）→ 打印最终回复与中间过程。

支持的斜杠命令：
- ``/exit`` / ``/quit``：退出
- ``/clear``：清空当前对话历史
- ``/help``：显示帮助

工具确认策略：
- ``use_skill``：免确认（纯信息读取，无副作用）
- ``bash``：仅黑名单命令（删除、格式化等）需确认，其余自动放行
- 其他工具：免确认
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from personal_assistant.config import ConfigError, load_config
from personal_assistant.core.agent import Agent
from personal_assistant.core.protocol import Message
from personal_assistant.llm.client import LLMClient
from personal_assistant.skills import default_skill_manager
from personal_assistant.tools import default_tools

_BANNER = (
    "Personal Assistant 已就绪。直接输入消息即可；"
    "Agent 会自主决定是否调用工具或技能。输入 /help 查看命令，/exit 退出。"
)
_HELP = """可用命令：
  /exit, /quit   退出程序
  /clear         清空当前对话历史
  /skills        查看已注册的技能列表
  /help          显示本帮助
其余输入将作为消息发送给 Agent（可能触发工具调用）。"""
_EXIT_OK = 0
_EXIT_CONFIG_ERROR = 2

#: 黑名单文件路径（相对于项目根目录）
_BLACKLIST_PATH = Path(__file__).resolve().parents[2] / "config" / "bash_blacklist.txt"


class _CliState:
    """CLI 运行时状态，跟踪流式输出与工具调用的换行需求。"""

    need_newline: bool = False  # True 表示当前行有待结束的内容（流式文本或 "助理 > " 前缀）


# --------------------------------------------------------------------------- #
# Bash 命令黑名单
# --------------------------------------------------------------------------- #

_BLACKLIST_PATTERNS: list[re.Pattern[str]] = []


def _load_blacklist() -> None:
    """加载 bash 命令黑名单文件，编译为正则列表。"""
    if not _BLACKLIST_PATH.exists():
        return
    for line in _BLACKLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            _BLACKLIST_PATTERNS.append(re.compile(line, re.IGNORECASE))
        except re.error:
            pass  # 跳过无效正则


def _is_dangerous(command: str) -> bool:
    """检查 bash 命令是否匹配黑名单中的危险模式。"""
    return any(p.search(command) for p in _BLACKLIST_PATTERNS)


# --------------------------------------------------------------------------- #
# CLI 回调
# --------------------------------------------------------------------------- #


def _before_tool_output() -> None:
    """在打印工具相关信息前，确保已换行到新行。"""
    if _CliState.need_newline:
        print()
        _CliState.need_newline = False


def _on_chunk(chunk: str) -> None:
    """流式回调：实时打印模型输出的文本增量。"""
    print(chunk, end="", flush=True)
    _CliState.need_newline = True


def _confirm_tool(name: str, arguments: dict, preview: str) -> bool:
    """工具执行前的确认提示。

    - ``use_skill``：免确认
    - ``bash``：仅黑名单命令需确认
    - 其他工具：免确认
    """
    if name == "use_skill":
        return True
    if name == "bash":
        command = str(arguments.get("command", ""))
        if not _is_dangerous(command):
            return True  # 非危险命令自动放行
        _before_tool_output()
        print(f"[危险命令] {command}")
        try:
            ans = input("  允许执行？[Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return ans in ("", "y", "yes")
    return True


def _on_event(event: str, data: dict) -> None:
    """展示 Agent 的中间过程：仅显示使用的工具/技能名称，不展示输入输出。"""
    if event == "context_compressed":
        _before_tool_output()
        count = data.get("compression_count", 0)
        old_msgs = data.get("old_messages", 0)
        new_msgs = data.get("new_messages", 0)
        summary = data.get("summary", "")
        print(f"  [上下文压缩] 第 {count} 次压缩：{old_msgs} 条 → {new_msgs} 条")
        if summary:
            print(f"  [摘要] {summary}...")
        return
    if event != "tool_call":
        return
    name = data["name"]
    if name == "use_skill":
        _before_tool_output()
        skill_name = data["arguments"].get("skill_name", "")
        print(f"  [使用技能] {skill_name}")
    elif name == "bash":
        command = str(data["arguments"].get("command", ""))
        if not _is_dangerous(command):
            # 非危险命令：在此显示（危险命令已在 _confirm_tool 中显示）
            _before_tool_output()
            preview = command[:80] + "..." if len(command) > 80 else command
            print(f"  [执行命令] {preview}")


# --------------------------------------------------------------------------- #
# 主程序
# --------------------------------------------------------------------------- #


def run() -> int:
    """启动 CLI REPL。返回进程退出码。"""
    _load_blacklist()

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
        skills=default_skill_manager(),
        max_messages=50,  # 上下文压缩：最大消息数
        auto_compress=True,  # 启用自动上下文压缩
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
        if cmd == "/skills":
            _show_skills(agent)
            continue
        if cmd == "/help":
            print(_HELP, "\n")
            continue

        history.append(Message.user(user_input))
        print("助理 > ", end="", flush=True)
        _CliState.need_newline = True
        try:
            agent.run(history, on_chunk=_on_chunk)
        except Exception as exc:  # noqa: BLE001 - 顶层兜底，保证 REPL 不崩
            if _CliState.need_newline:
                print()
                _CliState.need_newline = False
            print(f"[Agent 失败] {exc}\n", file=sys.stderr)
            history.pop()
            continue
        # 流式文本已通过 _on_chunk 实时输出，此处只需收尾换行
        if _CliState.need_newline:
            print()
            _CliState.need_newline = False
        _show_token_usage(agent)
        print()


def _show_skills(agent: Agent) -> None:
    """打印已注册的技能列表。"""
    skills = agent.skill_manager.list()
    if not skills:
        print("  (暂无已注册技能)\n")
        return
    print("已注册技能：")
    for s in skills:
        print(f"  {s.name}: {s.description}")
    print()


def _show_token_usage(agent: Agent) -> None:
    """打印本轮对话的 token 消耗统计。"""
    usage = agent.last_usage
    if usage.total_tokens > 0:
        print(f"\n[Token] {usage.format()}")


def main() -> int:
    """``personal-assistant`` 命令入口。"""
    return run()


if __name__ == "__main__":
    sys.exit(run())
