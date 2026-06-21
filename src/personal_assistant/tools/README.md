# Tools —— 如何新增工具

工具（Tool）是 Agent 通过 **toolcall 协议** 调用的能力单元。模型看到工具列表后，
自行决定是否调用、调用哪个、传什么参数；Agent 负责执行并把结果回填给模型。

工具体系与具体模型**解耦**：你只需按下面的规范写一个 Python 类，无需关心
OpenAI/DeepSeek 的线上格式——那由 `llm/client.py` 负责翻译。

## 目录约定

```
src/personal_assistant/tools/
├── README.md      ← 本文件
├── __init__.py    ← default_tools()：默认启用的工具清单
├── base.py        ← （基类 Tool 实际定义在 core/tool.py）
└── bash.py        ← bash 工具（示例）
```

> 基类 `Tool` 定义在 [`../core/tool.py`](../core/tool.py)，协议数据结构
> （`ToolSpec`/`ToolCall`/`ToolResult`/`Message`）在
> [`../core/protocol.py`](../core/protocol.py)。

## 新增一个工具：4 步

### 1. 新建工具文件

在 `tools/` 下新建 `my_tool.py`，继承 `Tool`，填三个类属性并实现 `run`：

```python
"""我的工具：做某件事。"""
from __future__ import annotations
from typing import Any
from personal_assistant.core.tool import Tool


class MyTool(Tool):
    name = "my_tool"                       # 模型用来调用它的唯一标识
    description = "一句话说明这个工具做什么、何时用、注意点。"  # 越清晰模型选得越准
    parameters = {                         # JSON Schema，描述参数
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "操作目标"},
        },
        "required": ["target"],
    }

    def run(self, arguments: dict[str, Any]) -> str:
        target = arguments.get("target", "")
        # ... 实际逻辑 ...
        return f"已完成对 {target} 的操作"  # 返回给模型可见的纯文本
```

### 2. 注册到默认清单

编辑 [`__init__.py`](./__init__.py)，把新工具加入 `default_tools()`：

```python
from personal_assistant.tools.my_tool import MyTool

def default_tools() -> list[Tool]:
    return [BashTool(), MyTool()]
```

### 3.（可选）按需构造

`default_tools()` 之外，你也可以在构造 `Agent` 时按需传入工具子集：

```python
agent = Agent(llm, tools=[BashTool(), MyTool()], system_prompt=...)
```

### 4. 写测试

工具是纯逻辑，建议用单元测试覆盖 `run()`（不需要联网、不依赖模型）。

## 规范要点

- **`name`** 全局唯一、小写下划线，如 `read_file`、`bash`。
- **`description`** 是模型决策的关键信号：写清「做什么 + 何时该用 + 边界/风险」。
  例如危险操作可在描述里注明「会修改/删除文件，谨慎使用」。
- **`parameters`** 是标准 JSON Schema。把每个字段的作用写进 `description`，
  模型才能正确填参。
- **`run` 的返回值**是给模型看的纯文本。把模型推理所需的信息都包进去
  （如命令的 exit code、查询的结果、报错原因）。
- **异常处理**：`run` 内部抛出的异常会被 Agent 捕获并作为错误结果回填模型，
  不会中断对话；但建议在 `run` 内自行处理可预期错误并返回友好文本。
- **安全**：有副作用或不可逆的工具（写文件、删数据、发请求），可依赖
  Agent 的 `confirm` 回调在执行前向用户确认。

## 运行时如何工作

```
Agent.run()
  ├─ 把每个 Tool.to_spec() 转成 ToolSpec → LLMClient 翻译成模型的 tools 字段
  ├─ 模型返回 tool_calls → LLMClient 翻译回 ToolCall
  ├─ Agent 按 tool_call.name 找到 Tool 实例 → 调用 tool.run(arguments)
  └─ 结果包成 ToolResult → 回填为 Message(role="tool") → 进入下一轮，直到模型给出最终文本
```

整个往返里，你的工具只关心 `run(arguments) -> str`，其余由框架处理。
