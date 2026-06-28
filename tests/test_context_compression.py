"""测试上下文压缩功能。"""

from __future__ import annotations

import pytest

from personal_assistant.core.agent import Agent
from personal_assistant.core.protocol import Message


class MockLLM:
    """模拟 LLM 客户端，用于测试。"""

    def complete(self, messages, tools=None):
        from personal_assistant.core.protocol import LLMResponse

        # 检查是否是压缩请求（包含"总结"关键词）
        if messages and messages[0].role == "system" and "总结" in (messages[0].content or ""):
            return LLMResponse(
                content="用户之前查询了天气和新闻，然后要求整理文件。所有任务已完成。",
            )
        # 普通对话响应
        return LLMResponse(content="这是测试回复。")

    def complete_stream(self, messages, tools=None, on_chunk=None):
        from personal_assistant.core.protocol import LLMResponse

        if messages and messages[0].role == "system" and "总结" in (messages[0].content or ""):
            return LLMResponse(
                content="用户之前查询了天气和新闻，然后要求整理文件。所有任务已完成。",
            )
        return LLMResponse(content="这是测试回复。")


class TestContextCompression:
    """测试上下文压缩功能。"""

    def test_compress_context_auto_trigger(self):
        """测试自动压缩触发。"""
        agent = Agent(
            MockLLM(),
            max_messages=10,
            auto_compress=True,
        )

        # 创建超过阈值的历史消息
        messages = [Message.system("你是一个助手。")]
        for i in range(15):
            messages.append(Message.user(f"消息 {i}"))
            messages.append(Message.assistant(f"回复 {i}"))

        assert len(messages) > agent.max_messages

        # 触发压缩
        compressed = agent._compress_context(messages)

        # 验证压缩后消息数量减少
        assert len(compressed) < len(messages)
        # 验证保留了 system prompt
        assert compressed[0].role == "system"
        # 验证包含压缩摘要
        assert any("上下文压缩摘要" in (msg.content or "") for msg in compressed)
        # 验证压缩计数增加
        assert agent._compression_count == 1

    def test_compress_context_no_trigger_below_threshold(self):
        """测试低于阈值时不触发压缩。"""
        agent = Agent(
            MockLLM(),
            max_messages=50,
            auto_compress=True,
        )

        messages = [Message.system("你是一个助手。")]
        for i in range(5):
            messages.append(Message.user(f"消息 {i}"))
            messages.append(Message.assistant(f"回复 {i}"))

        # 低于阈值，不应该压缩
        assert len(messages) <= agent.max_messages
        compressed = agent._compress_context(messages)

        # 消息应该保持不变
        assert len(compressed) == len(messages)

    def test_compress_context_disabled(self):
        """测试禁用自动压缩时不触发。"""
        agent = Agent(
            MockLLM(),
            max_messages=10,
            auto_compress=False,
        )

        messages = [Message.system("你是一个助手。")]
        for i in range(15):
            messages.append(Message.user(f"消息 {i}"))
            messages.append(Message.assistant(f"回复 {i}"))

        # 即使超过阈值，禁用后也不应该压缩
        compressed = agent._compress_context(messages)
        assert len(compressed) == len(messages)

    def test_compress_context_preserves_system_prompt(self):
        """测试压缩后保留 system prompt。"""
        agent = Agent(
            MockLLM(),
            max_messages=10,
            auto_compress=True,
        )

        messages = [Message.system("你是一个有用的助手。")]
        for i in range(15):
            messages.append(Message.user(f"消息 {i}"))
            messages.append(Message.assistant(f"回复 {i}"))

        compressed = agent._compress_context(messages)

        # 验证 system prompt 保留
        assert compressed[0].role == "system"
        assert compressed[0].content == "你是一个有用的助手。"

    def test_compress_context_emits_event(self):
        """测试压缩时触发事件。"""
        events = []

        def on_event(event: str, data: dict):
            events.append((event, data))

        agent = Agent(
            MockLLM(),
            max_messages=10,
            auto_compress=True,
            on_event=on_event,
        )

        messages = [Message.system("你是一个助手。")]
        for i in range(15):
            messages.append(Message.user(f"消息 {i}"))
            messages.append(Message.assistant(f"回复 {i}"))

        agent._compress_context(messages)

        # 验证触发了压缩事件
        assert len(events) == 1
        event_name, event_data = events[0]
        assert event_name == "context_compressed"
        assert "old_messages" in event_data
        assert "new_messages" in event_data
        assert "compression_count" in event_data
        assert "summary" in event_data

    def test_estimate_tokens(self):
        """测试 token 估算功能。"""
        agent = Agent(MockLLM())

        messages = [
            Message.user("你好世界"),  # 4 个中文字
            Message.assistant("Hello World"),  # 2 个英文单词
        ]

        tokens = agent._estimate_tokens(messages)
        # 4 * 1.5 + 2 * 1.3 = 6 + 2.6 = 8.6 ≈ 8
        assert tokens > 0
        assert tokens < 20  # 应该在合理范围内

    def test_compress_context_multiple_times(self):
        """测试多次压缩。"""
        agent = Agent(
            MockLLM(),
            max_messages=10,
            auto_compress=True,
        )

        # 第一次压缩
        messages = [Message.system("你是一个助手。")]
        for i in range(15):
            messages.append(Message.user(f"消息 {i}"))
            messages.append(Message.assistant(f"回复 {i}"))

        compressed1 = agent._compress_context(messages)
        assert agent._compression_count == 1

        # 再次添加消息并压缩
        for i in range(20):
            compressed1.append(Message.user(f"新消息 {i}"))
            compressed1.append(Message.assistant(f"新回复 {i}"))

        compressed2 = agent._compress_context(compressed1)
        assert agent._compression_count == 2
