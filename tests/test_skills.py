"""技能系统单元测试：SkillFolder / SkillManager / UseSkillTool。

测试新的文件夹式技能系统：
- 每个 Skill 是一个文件夹，包含 SKILL.md（名称 + 描述 + 正文）。
- 模型通过 use_skill 工具调用技能时，返回 SKILL.md 全文 + 所有 markdown 文件。
"""

from __future__ import annotations

from pathlib import Path

from personal_assistant.core.agent import Agent
from personal_assistant.core.protocol import LLMResponse, Message, TokenUsage, ToolCall
from personal_assistant.core.skill import SkillFolder, SkillManager
from personal_assistant.skills import UseSkillTool, default_skill_manager

# --------------------------------------------------------------------------- #
# 辅助函数：创建临时技能文件夹
# --------------------------------------------------------------------------- #


def _make_skill_folder(
    base: Path,
    name: str,
    description: str,
    body: str,
    extra_files: dict[str, str] | None = None,
) -> Path:
    """在 base 目录下创建一个技能文件夹。返回文件夹路径。"""
    folder = base / name
    folder.mkdir(parents=True, exist_ok=True)
    content = f"# {name}\n\n> {description}\n\n{body}\n"
    (folder / "SKILL.md").write_text(content, encoding="utf-8")

    if extra_files:
        for rel_path, content in extra_files.items():
            file_path = folder / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

    return folder


# --------------------------------------------------------------------------- #
# SkillFolder
# --------------------------------------------------------------------------- #


def test_skill_folder_parses_name_and_description(tmp_path: Path) -> None:
    folder = _make_skill_folder(
        tmp_path,
        "echo",
        "回显输入文本",
        "## 步骤\n\n1. 读取输入\n2. 原样返回\n",
    )
    skill = SkillFolder(folder)
    assert skill.name == "echo"
    assert skill.description == "回显输入文本"
    assert "步骤" in skill.body


def test_skill_folder_parses_with_blank_lines(tmp_path: Path) -> None:
    """SKILL.md 前面有空白行时也能正确解析。"""
    folder = tmp_path / "test_skill"
    folder.mkdir()
    (folder / "SKILL.md").write_text(
        "\n\n# Test Skill\n\n> A test.\n\nBody here.\n", encoding="utf-8"
    )
    skill = SkillFolder(folder)
    assert skill.name == "Test Skill"
    assert skill.description == "A test."
    assert "Body here" in skill.body


def test_skill_folder_raises_without_skill_md(tmp_path: Path) -> None:
    import pytest

    folder = tmp_path / "empty_skill"
    folder.mkdir()
    with pytest.raises(FileNotFoundError, match="SKILL.md"):
        SkillFolder(folder)


def test_skill_folder_load_content_includes_skill_md(tmp_path: Path) -> None:
    folder = _make_skill_folder(
        tmp_path,
        "websearch",
        "搜索网络",
        "## 步骤\n\n用 bash 执行搜索脚本。",
    )
    skill = SkillFolder(folder)
    content = skill.load_content()
    assert "[技能文件夹:" in content
    assert "=== SKILL.md ===" in content
    assert "# websearch" in content
    assert "搜索网络" in content
    assert "用 bash 执行搜索脚本" in content


def test_skill_folder_load_content_includes_extra_markdown(tmp_path: Path) -> None:
    """load_content 包含技能文件夹下的所有 markdown 文件（含子文件夹）。"""
    folder = _make_skill_folder(
        tmp_path,
        "my_skill",
        "测试技能",
        "正文",
        extra_files={
            "guide.md": "# Guide\n\n补充说明。",
            "examples/case.md": "# Case\n\n示例用例。",
        },
    )
    skill = SkillFolder(folder)
    content = skill.load_content()

    # SKILL.md 在最前面
    assert "=== SKILL.md ===" in content
    # guide.md 被包含
    assert "=== guide.md ===" in content
    assert "补充说明" in content
    # 子文件夹中的 markdown 也被包含
    assert "=== examples" in content
    assert "示例用例" in content


def test_skill_folder_to_spec(tmp_path: Path) -> None:
    folder = _make_skill_folder(tmp_path, "echo", "回显", "正文")
    skill = SkillFolder(folder)
    spec = skill.to_spec()
    assert spec.name == "echo"
    assert spec.description == "回显"


# --------------------------------------------------------------------------- #
# SkillManager
# --------------------------------------------------------------------------- #


def test_skill_manager_scans_directory(tmp_path: Path) -> None:
    """SkillManager 自动扫描目录下所有含 SKILL.md 的子文件夹。"""
    _make_skill_folder(tmp_path, "skill_a", "技能A", "正文A")
    _make_skill_folder(tmp_path, "skill_b", "技能B", "正文B")
    # 不含 SKILL.md 的文件夹应被忽略
    (tmp_path / "not_a_skill").mkdir()

    manager = SkillManager(tmp_path)
    names = [s.name for s in manager.list()]
    assert "skill_a" in names
    assert "skill_b" in names
    assert "not_a_skill" not in names


def test_skill_manager_get_and_invoke(tmp_path: Path) -> None:
    _make_skill_folder(tmp_path, "echo", "回显", "执行步骤...")
    manager = SkillManager(tmp_path)

    skill = manager.get("echo")
    assert skill is not None
    assert skill.description == "回显"

    content = manager.invoke("echo")
    assert "执行步骤" in content


def test_skill_manager_invoke_unknown(tmp_path: Path) -> None:
    manager = SkillManager(tmp_path)
    result = manager.invoke("nonexistent")
    assert "未知技能" in result


def test_skill_manager_register_and_unregister(tmp_path: Path) -> None:
    manager = SkillManager(tmp_path)
    folder = _make_skill_folder(tmp_path, "temp_skill", "临时", "正文")
    skill = SkillFolder(folder)

    manager.register(skill)
    assert manager.get("temp_skill") is not None

    assert manager.unregister("temp_skill") is True
    assert manager.get("temp_skill") is None
    assert manager.unregister("temp_skill") is False


def test_default_skill_manager_loads_websearch() -> None:
    """默认 SkillManager 应加载内置的 websearch 技能。"""
    manager = default_skill_manager()
    assert manager.get("Web Search") is not None or manager.get("websearch") is not None
    # 确认至少有一个技能
    assert len(manager.list()) >= 1


# --------------------------------------------------------------------------- #
# UseSkillTool
# --------------------------------------------------------------------------- #


def test_use_skill_tool_description_includes_skills(tmp_path: Path) -> None:
    _make_skill_folder(tmp_path, "echo", "回显输入文本", "正文")
    manager = SkillManager(tmp_path)
    tool = UseSkillTool(manager)

    desc = tool.description
    assert "echo" in desc
    assert "回显输入文本" in desc


def test_use_skill_tool_description_empty(tmp_path: Path) -> None:
    manager = SkillManager(tmp_path)
    tool = UseSkillTool(manager)
    assert "无可用技能" in tool.description


def test_use_skill_tool_run_returns_content(tmp_path: Path) -> None:
    _make_skill_folder(tmp_path, "echo", "回显", "详细说明内容。")
    manager = SkillManager(tmp_path)
    tool = UseSkillTool(manager)

    result = tool.run({"skill_name": "echo"})
    assert "详细说明内容" in result
    assert "=== SKILL.md ===" in result


def test_use_skill_tool_run_unknown(tmp_path: Path) -> None:
    manager = SkillManager(tmp_path)
    tool = UseSkillTool(manager)
    result = tool.run({"skill_name": "nope"})
    assert "未知技能" in result


def test_use_skill_tool_to_spec_has_dynamic_description(tmp_path: Path) -> None:
    _make_skill_folder(tmp_path, "echo", "回显", "正文")
    manager = SkillManager(tmp_path)
    tool = UseSkillTool(manager)

    spec = tool.to_spec()
    assert spec.name == "use_skill"
    assert "echo" in spec.description


# --------------------------------------------------------------------------- #
# Agent 集成
# --------------------------------------------------------------------------- #


class _MockLLM:
    """按预设脚本依次返回响应的假 LLM。"""

    def __init__(self, script: list[LLMResponse]) -> None:
        self.script = list(script)

    def complete(self, messages, tools=None) -> LLMResponse:
        return self.script.pop(0)


def test_agent_auto_registers_use_skill_tool() -> None:
    """Agent 初始化后自动注册 use_skill 工具。"""
    agent = Agent(_MockLLM([LLMResponse(content="ok")]), tools=[])
    assert "use_skill" in agent.tools


def test_agent_skill_via_toolcall(tmp_path: Path) -> None:
    """模型通过 use_skill 调用技能 → 获取内容 → 给出最终回复。"""
    _make_skill_folder(tmp_path, "echo", "回显", "技能详细说明。")
    manager = SkillManager(tmp_path)

    llm = _MockLLM(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="use_skill",
                        arguments={"skill_name": "echo"},
                    )
                ]
            ),
            LLMResponse(content="done"),
        ]
    )
    agent = Agent(llm, tools=[], skills=manager)
    messages = [Message.user("使用 echo 技能")]
    reply = agent.run(messages)

    assert reply == "done"
    # 消息历史：user → assistant(tool_calls) → tool(结果) → assistant(最终)
    roles = [m.role for m in messages]
    assert roles == ["user", "assistant", "tool", "assistant"]
    # tool 消息包含技能内容
    tool_msg = messages[2]
    assert "技能详细说明" in (tool_msg.content or "")


def test_agent_add_skill_from_folder(tmp_path: Path) -> None:
    """运行时通过文件夹路径添加技能。"""
    _make_skill_folder(tmp_path, "dynamic", "动态技能", "动态内容。")
    agent = Agent(_MockLLM([LLMResponse(content="ok")]), tools=[])

    agent.add_skill_from_folder(str(tmp_path / "dynamic"))
    assert agent.skill_manager.get("dynamic") is not None

    content = agent.skill_manager.invoke("dynamic")
    assert "动态内容" in content


def test_agent_remove_skill(tmp_path: Path) -> None:
    """运行时移除技能。"""
    _make_skill_folder(tmp_path, "removable", "可移除", "正文")
    manager = SkillManager(tmp_path)
    agent = Agent(_MockLLM([LLMResponse(content="ok")]), tools=[], skills=manager)

    assert agent.skill_manager.get("removable") is not None
    assert agent.remove_skill("removable") is True
    assert agent.skill_manager.get("removable") is None


# --------------------------------------------------------------------------- #
# Token 使用统计（保持兼容）
# --------------------------------------------------------------------------- #


def test_agent_tracks_token_usage() -> None:
    """Agent 在 run() 后 last_usage 应反映本轮所有模型调用的 token 总消耗。"""

    class _UsageLLM:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages, tools=None) -> LLMResponse:
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(
                    tool_calls=[ToolCall(id="c1", name="use_skill", arguments={})],
                    usage=TokenUsage(
                        prompt_tokens=100,
                        completion_tokens=20,
                        total_tokens=120,
                        cached_tokens=50,
                    ),
                )
            return LLMResponse(
                content="done",
                usage=TokenUsage(
                    prompt_tokens=200,
                    completion_tokens=30,
                    total_tokens=230,
                    cached_tokens=80,
                ),
            )

    agent = Agent(_UsageLLM(), tools=[])
    agent.run([Message.user("hi")])

    usage = agent.last_usage
    assert usage.prompt_tokens == 300
    assert usage.completion_tokens == 50
    assert usage.total_tokens == 350
    assert usage.cached_tokens == 130


def test_token_usage_addition() -> None:
    a = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15, cached_tokens=3)
    b = TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30, cached_tokens=7)
    c = a + b
    assert c.prompt_tokens == 30
    assert c.completion_tokens == 15
    assert c.total_tokens == 45
    assert c.cached_tokens == 10


def test_token_usage_format() -> None:
    usage = TokenUsage(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cached_tokens=30,
    )
    text = usage.format()
    assert "输入 100" in text
    assert "输出 50" in text
    assert "总计 150" in text
    assert "缓存命中 30" in text
