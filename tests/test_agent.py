"""Agent 编排循环测试：用 Mock LLM 验证 toolcall 往返，不依赖真实模型。"""

from __future__ import annotations

from personal_assistant.core.agent import Agent
from personal_assistant.core.protocol import LLMResponse, Message, ToolCall
from personal_assistant.core.tool import Tool


class _RecordingTool(Tool):
    """记录每次被调用的参数，供断言。"""

    name = "record"
    description = "记录工具，仅用于测试"
    parameters = {"type": "object", "properties": {"text": {"type": "string"}}}

    def __init__(self) -> None:
        self.calls: list[str] = []

    def run(self, arguments: dict) -> str:
        self.calls.append(arguments.get("text", ""))
        return f"已记录: {arguments.get('text', '')}"


class _MockLLM:
    """按预设脚本依次返回响应的假 LLM。"""

    def __init__(self, script: list[LLMResponse]) -> None:
        self.script = list(script)
        self.completions: list[list[Message]] = []

    def complete(self, messages, tools=None) -> LLMResponse:
        self.completions.append(list(messages))
        return self.script.pop(0)


def test_agent_executes_tool_then_finishes() -> None:
    """模型先请求工具 → Agent 执行 → 结果回填 → 模型给出最终文本。"""
    tool = _RecordingTool()
    llm = _MockLLM(
        [
            LLMResponse(tool_calls=[ToolCall(id="c1", name="record", arguments={"text": "hi"})]),
            LLMResponse(content="done"),
        ]
    )
    agent = Agent(llm, tools=[tool], system_prompt="sys")

    messages = [Message.system("sys"), Message.user("请记录 hi")]
    reply = agent.run(messages)

    assert reply == "done"
    assert tool.calls == ["hi"]  # 工具被真正执行了一次
    # 消息历史正确：assistant(tool_calls) + tool(结果) + assistant(最终)
    roles = [m.role for m in messages]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]
    # 第二次 complete 时已能看到工具结果消息
    assert any(m.role == "tool" and "已记录: hi" in (m.content or "") for m in llm.completions[1])


def test_agent_passes_tool_specs_to_llm() -> None:
    """Agent 应把工具声明（ToolSpec）透传给 LLM 的 complete。"""
    tool = _RecordingTool()
    llm = _MockLLM([LLMResponse(content="ok")])
    agent = Agent(llm, tools=[tool])

    agent.run([Message.user("hi")])

    assert llm.completions  # complete 被调用过
    # 工具列表传入了（用 _MockLLM 的 tools 参数验证）
    assert llm.completions is not None  # 占位，下方单独验证 specs


def test_agent_passes_specs() -> None:
    tool = _RecordingTool()
    captured: list = []

    class _LLM2:
        def complete(self, messages, tools=None):
            captured.append(tools)
            return LLMResponse(content="ok")

    Agent(_LLM2(), tools=[tool]).run([Message.user("hi")])
    assert captured and captured[0] is not None
    assert captured[0][0].name == "record"


def test_agent_unknown_tool_returns_error_result() -> None:
    """模型请求了不存在的工具 → 回填错误，循环继续。"""
    llm = _MockLLM(
        [
            LLMResponse(tool_calls=[ToolCall(id="x", name="nope", arguments={})]),
            LLMResponse(content="sorry"),
        ]
    )
    agent = Agent(llm, tools=[])
    reply = agent.run([Message.user("hi")])
    assert reply == "sorry"


def test_agent_respects_confirm_reject() -> None:
    """confirm 回调返回 False 时，工具不执行且回填「用户拒绝」。"""
    tool = _RecordingTool()
    llm = _MockLLM(
        [
            LLMResponse(tool_calls=[ToolCall(id="c", name="record", arguments={"text": "x"})]),
            LLMResponse(content="ok"),
        ]
    )
    agent = Agent(llm, tools=[tool], confirm=lambda name, args, preview: False)
    agent.run([Message.user("hi")])
    assert tool.calls == []  # 被拒绝，未执行


# --------------------------------------------------------------------------- #
# 系统提示词变量处理
# --------------------------------------------------------------------------- #


def test_process_system_prompt_appends_variables() -> None:
    """{{变量}} 占位符不被替换，解析值追加到末尾。"""
    agent = Agent(_MockLLM([LLMResponse(content="ok")]), system_prompt="")
    processed = agent._process_system_prompt("当前时间：{{current_time}}，用户：{{user_name}}")

    # 原文占位符保留
    assert "{{current_time}}" in processed
    assert "{{user_name}}" in processed
    # 变量值追加在末尾
    assert "---variables---" in processed
    assert "current_time:" in processed
    # user_name 无解析器，不应出现
    assert "user_name:" not in processed


def test_process_system_prompt_no_variables() -> None:
    """无变量的提示词原样返回。"""
    agent = Agent(_MockLLM([LLMResponse(content="ok")]), system_prompt="")
    prompt = "你是一个个人助理。"
    processed = agent._process_system_prompt(prompt)
    assert processed == prompt


def test_process_system_prompt_default_resolvers() -> None:
    """内置变量 current_time / current_date / os 可正常解析。"""
    from datetime import datetime

    agent = Agent(_MockLLM([LLMResponse(content="ok")]), system_prompt="")
    processed = agent._process_system_prompt("{{current_time}} {{current_date}} {{os}}")

    today = datetime.now().strftime("%Y-%m-%d")
    assert f"current_date: {today}" in processed
    assert "current_time:" in processed
    assert "os:" in processed
    # 原文占位符保留
    assert "{{current_time}}" in processed


def test_register_custom_var() -> None:
    """register_var 注册的自定义变量可被解析。"""
    agent = Agent(_MockLLM([LLMResponse(content="ok")]), system_prompt="")
    agent.register_var("user_name", lambda: "张三")
    processed = agent._process_system_prompt("你好，{{user_name}}")

    assert "{{user_name}}" in processed  # 原文保留
    assert "user_name: 张三" in processed  # 值追加在末尾


def test_var_resolvers_init_param() -> None:
    """通过 __init__ 的 var_resolvers 参数传入自定义解析器。"""
    agent = Agent(
        _MockLLM([LLMResponse(content="ok")]),
        var_resolvers={"city": lambda: "北京"},
    )
    processed = agent._process_system_prompt("所在地：{{city}}")
    assert "city: 北京" in processed


def test_run_processes_system_prompt() -> None:
    """run() 调用时自动处理系统消息中的变量。"""
    llm = _MockLLM([LLMResponse(content="done")])
    agent = Agent(llm, system_prompt="时间：{{current_time}}")
    messages = [Message.system("时间：{{current_time}}"), Message.user("hi")]
    agent.run(messages)

    # 发给模型的消息中，系统提示词已包含变量值
    sent_system = llm.completions[0][0]
    assert sent_system.role == "system"
    assert "{{current_time}}" in (sent_system.content or "")  # 原文保留
    assert "current_time:" in (sent_system.content or "")  # 值已追加


def test_run_does_not_accumulate_variables() -> None:
    """多次 run() 不会累积变量值（分隔符剥离旧值）。"""
    call_count = 0

    class _CountingLLM:
        def complete(self, messages, tools=None):
            nonlocal call_count
            call_count += 1
            return LLMResponse(content=f"reply {call_count}")

    agent = Agent(_CountingLLM(), system_prompt="{{current_time}}")

    messages1 = [Message.system("{{current_time}}"), Message.user("first")]
    agent.run(messages1)
    first_content = messages1[0].content or ""
    # 只应有一处 ---variables---
    assert first_content.count("---variables---") == 1

    # 第二轮：系统消息已包含上轮追加的值
    messages2 = [messages1[0], Message.user("second")]
    agent.run(messages2)
    second_content = messages2[0].content or ""
    # 仍然只有一处 ---variables---（旧值被剥离后重新追加）
    assert second_content.count("---variables---") == 1


def test_process_system_prompt_deduplicates() -> None:
    """同一变量出现多次时只解析一次。"""
    agent = Agent(_MockLLM([LLMResponse(content="ok")]), system_prompt="")
    processed = agent._process_system_prompt("{{current_time}} and {{current_time}}")
    # 变量值只出现一次
    lines_with_time = [line for line in processed.split("\n") if line.startswith("current_time:")]
    assert len(lines_with_time) == 1


def test_process_system_prompt_unknown_var_ignored() -> None:
    """未注册的变量不会出现在追加区域。"""
    agent = Agent(_MockLLM([LLMResponse(content="ok")]), system_prompt="")
    processed = agent._process_system_prompt("{{unknown_var}}")
    # 无变量值可追加，返回 base prompt
    assert "---variables---" not in processed
    assert "{{unknown_var}}" in processed
