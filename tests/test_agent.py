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
