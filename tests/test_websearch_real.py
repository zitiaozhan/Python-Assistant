"""真实 LLM 验收测试：Agent 使用 websearch 技能搜索马斯克新闻。

测试流程：
1. Agent 收到用户请求（搜索马斯克新闻）
2. Agent 调用 use_skill("Web Search") 获取技能说明
3. Agent 按 SKILL.md 说明用 bash 执行 search.py
4. Agent 阅读搜索结果并总结

运行方式::

    uv run python tests/test_websearch_real.py

需要配置好 config/model.json 或环境变量 DEEPSEEK_API_KEY。
"""

from __future__ import annotations

import sys

# Windows 终端默认 GBK，强制 UTF-8 避免中文/emoji 报错。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from personal_assistant.config import load_config
from personal_assistant.core.agent import Agent
from personal_assistant.core.protocol import Message
from personal_assistant.llm.client import LLMClient
from personal_assistant.skills import default_skill_manager
from personal_assistant.tools import default_tools


def main() -> int:
    config = load_config()
    llm = LLMClient(config)

    # 打印技能信息
    skill_manager = default_skill_manager()
    print("=== 已注册技能 ===")
    for s in skill_manager.list():
        print(f"  {s.name}: {s.description}")
    print()

    agent = Agent(
        llm,
        tools=default_tools(),
        system_prompt=config.system_prompt,
        confirm=None,  # 自动放行所有工具调用
        on_event=_on_event,
        skills=skill_manager,
        max_iterations=15,
    )

    print("=== 工具列表 ===")
    print(f"  {', '.join(agent.tools.keys())}")
    print()

    messages = [
        Message.system(config.system_prompt),
        Message.user(
            "请搜索一下关于马斯克（Elon Musk）的最新新闻，搜索一两次即可，然后给我总结几条重要的。"
        ),
    ]

    print("=== 用户请求 ===")
    print("请搜索一下关于马斯克（Elon Musk）的最新新闻，搜索一两次即可，然后给我总结几条重要的。")
    print("\n=== Agent 执行过程 ===\n")

    reply = agent.run(messages)

    print("\n=== Agent 最终回复 ===")
    print(reply)

    # 验证：回复中应包含搜索结果相关信息
    print("\n=== Token 统计 ===")
    print(agent.last_usage.format())

    # 简单断言：回复不应为空，且应包含与马斯克相关的关键词
    success = bool(reply) and (
        "马斯克" in reply or "Musk" in reply or "Tesla" in reply or "SpaceX" in reply
    )
    print(f"\n=== 测试结果: {'通过' if success else '失败'} ===")
    return 0 if success else 1


def _on_event(event: str, data: dict) -> None:
    """展示 Agent 的中间过程。"""
    if event == "tool_call":
        name = data["name"]
        args = data["arguments"]
        if name == "use_skill":
            print(f"  [技能调用] {args.get('skill_name', '')}")
        elif name == "bash":
            cmd = args.get("command", "")
            print(f"  [Bash] {cmd[:120]}")
    elif event == "tool_result":
        name = data["name"]
        output = data["output"]
        # 截断过长的输出
        preview = output[:200] + "..." if len(output) > 200 else output
        print(f"  [结果] {name}: {preview}")


if __name__ == "__main__":
    sys.exit(main())
