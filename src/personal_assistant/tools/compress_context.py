"""CompressContextTool —— 上下文压缩工具。

让 Agent 可以主动触发上下文压缩，保存当前任务进展并清理旧消息。
"""

from __future__ import annotations

from typing import Any

from personal_assistant.core.tool import Tool


class CompressContextTool(Tool):
    """上下文压缩工具。

    Agent 可以在认为对话历史过长或任务阶段性完成时调用此工具，
    触发上下文压缩以清理旧消息并保留关键信息。

    实际上压缩逻辑由 Agent._compress_context() 处理，此工具仅作为
    Agent 主动触发压缩的接口。
    """

    name = "compress_context"
    description = (
        "当对话历史过长或认为需要保存当前进展时，调用此工具压缩上下文。"
        "会总结历史对话并清理旧消息，保留最近的关键信息。"
        "适用场景：1) 对话消息过多 2) 任务阶段性完成 3) 需要清理上下文以继续长期任务"
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": (
                    "压缩原因（如：对话过长、任务阶段性完成、需要清理上下文以继续新任务）"
                ),
            },
        },
        "required": ["reason"],
    }

    def run(self, arguments: dict) -> str:
        """执行上下文压缩。

        注意：实际的压缩逻辑由 Agent._compress_context() 在下一轮 run() 时自动处理。
        此工具仅返回提示信息。
        """
        reason = arguments.get("reason", "未指定")
        return (
            f"已请求压缩上下文（原因：{reason}）。"
            "压缩将在下一轮对话时自动执行，历史消息将被总结为简洁摘要。"
        )
