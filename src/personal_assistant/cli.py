"""命令行交互主程序（REPL）。

在一个循环中：
1. 从命令行读取用户输入；
2. 将输入交给 :class:`~personal_assistant.llm.client.LLMClient`；
3. 把模型输出流式打印到命令行；
4. 维护多轮对话上下文。

支持的命令（以 ``/`` 开头）：
- ``/exit`` 或 ``/quit``：退出
- ``/clear``：清空当前对话历史
- ``/help``：显示帮助
"""

from __future__ import annotations

import sys

from personal_assistant.config import ConfigError, load_config
from personal_assistant.llm.client import LLMClient

_BANNER = "Personal Assistant 已就绪。输入消息开始对话，输入 /help 查看命令，/exit 退出。"
_HELP = """可用命令：
  /exit, /quit   退出程序
  /clear         清空当前对话历史
  /help          显示本帮助
其余输入将作为消息发送给模型。"""
# 退出/错误码
_EXIT_OK = 0
_EXIT_CONFIG_ERROR = 2


def run() -> int:
    """启动 CLI REPL。返回进程退出码。"""
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"[配置错误] {exc}", file=sys.stderr)
        return _EXIT_CONFIG_ERROR

    llm = LLMClient(config)
    # 多轮对话历史：首条固定为 system prompt。
    history: list[dict[str, str]] = [{"role": "system", "content": config.system_prompt}]

    print(_BANNER)
    print(f"[模型] {config.model} @ {config.base_url}\n")

    while True:
        try:
            user_input = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+D / Ctrl+C 视为退出。
            print("\n再见。")
            return _EXIT_OK

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in ("/exit", "/quit"):
            print("再见。")
            return _EXIT_OK
        if cmd == "/clear":
            history = [{"role": "system", "content": config.system_prompt}]
            print("[已清空对话历史]\n")
            continue
        if cmd == "/help":
            print(_HELP, "\n")
            continue

        history.append({"role": "user", "content": user_input})
        print("助理 > ", end="", flush=True)
        try:
            assistant_text = _stream_print(llm, history)
        except Exception as exc:  # noqa: BLE001 - 顶层兜底，保证 REPL 不崩
            print(f"\n[请求失败] {exc}\n", file=sys.stderr)
            # 失败时回滚刚加入的 user 消息，保持历史一致。
            history.pop()
            continue
        history.append({"role": "assistant", "content": assistant_text})
        print()  # 换行分隔下一轮


def _stream_print(llm: LLMClient, history: list[dict[str, str]]) -> str:
    """流式打印模型输出，并返回完整文本。"""
    chunks: list[str] = []
    for delta in llm.chat(history):
        print(delta, end="", flush=True)
        chunks.append(delta)
    return "".join(chunks)


def main() -> int:
    """``personal-assistant`` 命令入口。"""
    return run()


# 便于 ``python -m personal_assistant`` 直接启动。
if __name__ == "__main__":
    sys.exit(run())
