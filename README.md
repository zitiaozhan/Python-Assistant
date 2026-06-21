# Python-Assistant

一个面向**个人助理**的 Agent 项目，目标是打通**手机与电脑的协作**，并通过
**插件化架构**实现可持续扩展的能力体系。

> 当前状态：已实现 **流式对话 + Agent 工具调用 + 技能系统 + Token 统计 + 系统提示词变量**。
> Agent 能自主决定是否调用工具或技能，在本地真实执行，文本流式输出，
> 并在每轮对话后报告 Token 消耗。手机↔电脑协作为后续路线图。

---

## 设计目标

1. **个人助理** — 理解用户意图，并代表用户采取行动。
2. **手机 ↔ 电脑协作** — 同一个助理跨越手机与电脑两端，共享上下文，
   将任务委派给最合适的设备。
3. **可不断扩展** — 新增能力无需改动核心代码，理想情况下可作为独立分发的包
   插入到系统中。

## 核心设计

项目通过**协议解耦**实现「换模型不改代码、加能力不改核心」：

```
用户输入
  │
  ▼
┌──────────┐    toolcall 协议     ┌──────────────┐
│  Agent   │ ◄──────────────────► │   LLMClient   │ ◄──► DeepSeek / OpenAI / 兼容供应商
│ (编排核心) │                      │ (协议翻译层)   │
└────┬─────┘                      └──────────────┘
     │ 执行
     ├─► Tool（工具）：原子操作，模型直接 toolcall 调用
     │     例：bash → 执行 shell 命令
     │
     └─► Skill（技能）：领域知识 + 多步骤指引
           模型调用 use_skill → 获得 SKILL.md 全文 → 按文档执行
           例：websearch → 搜索 Bing 并返回结果
```

- **Agent** 只操作 `protocol.py` 中定义的类型（`Message` / `ToolSpec` / `ToolCall`…），
  完全不感知模型的线上格式。
- **LLMClient** 负责双向翻译（内部类型 ↔ OpenAI 兼容格式）并提取 Token 用量。
- **Tool** 和 **Skill** 是两种扩展方式，均无需修改核心代码。

> 更详细的架构说明见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

## 目录结构

```
Python-Assistant/
├── src/personal_assistant/
│   ├── core/                  # 核心抽象（与模型解耦）
│   │   ├── agent.py           #   Agent：工具编排循环 + Token 累计 + 系统提示词变量
│   │   ├── tool.py            #   Tool 基类：name/description/parameters/run
│   │   ├── skill.py           #   SkillFolder + SkillManager：文件夹式技能
│   │   ├── protocol.py        #   协议类型：Message/ToolSpec/ToolCall/TokenUsage…
│   │   └── plugin.py          #   （预留）高层能力组合
│   ├── llm/
│   │   └── client.py          # LLMClient：协议翻译 + Token 提取 + 流式补全
│   ├── tools/
│   │   ├── bash.py            #   bash 工具（Git Bash 执行，强制 UTF-8）
│   │   ├── __init__.py        #   default_tools() 默认工具清单
│   │   └── README.md          #   如何新增工具
│   ├── skills/
│   │   ├── __init__.py        #   UseSkillTool + default_skill_manager()
│   │   ├── README.md          #   如何新增技能
│   │   └── websearch/         #   内置技能：Bing 搜索
│   │       ├── SKILL.md       #     名称 + 描述 + 使用说明
│   │       └── search.py      #     搜索脚本（标准库实现，无额外依赖）
│   ├── cli.py                 # 命令行 REPL（流式输出 + 工具确认门禁 + Token 展示）
│   ├── config.py              # 加载 model.json，支持环境变量覆盖
│   ├── plugins/               # （预留）能力插件命名空间
│   └── sync/                  # （预留）手机↔电脑协作层
├── config/
│   ├── model.json             # 真实配置（含 API key，.gitignore 忽略）
│   ├── model.json.example     # 配置模板（提交到版本库）
│   └── bash_blacklist.txt     # Bash 危险命令黑名单（删除/格式化等需确认）
├── tests/                     # 单元测试 + Agent 编排测试 + 真实 LLM 验收测试
├── docs/
│   └── ARCHITECTURE.md        # 架构与扩展机制说明
├── pyproject.toml             # 项目元信息、依赖、工具配置
└── README.md
```

## 技术栈

| 能力         | 选型                          |
| ------------ | ----------------------------- |
| 语言         | Python ≥ 3.12                 |
| 依赖/环境    | [uv](https://github.com/astral-sh/uv) |
| 测试         | pytest                        |
| Lint/Format  | ruff（uv 自带）               |
| 打包         | hatchling                     |

## 快速开始

### 前置条件

- 已安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)

### 初始化环境

```bash
# 在项目根目录执行，uv 会自动按 .python-version 创建 .venv 并安装依赖
uv sync
```

### 配置模型

复制配置模板并填入你的 API key：

```bash
cp config/model.json.example config/model.json
# 编辑 config/model.json，把 api_key 改成你的真实 key
```

也可不修改文件，改用环境变量（优先级更高，便于 CI / 容器）：

```bash
# Windows cmd
set DEEPSEEK_API_KEY=sk-xxxx
# PowerShell / *nix
export DEEPSEEK_API_KEY=sk-xxxx
```

更换模型或供应商时，只需改 `config/model.json` 里的 `base_url` 与 `model`
（只要对方提供 OpenAI 兼容接口，如 OpenAI、Moonshot、通义千问等）。

### 常用命令

```bash
# 启动 CLI 对话（多轮、流式输出）
uv run personal-assistant
# 或
uv run python -m personal_assistant

# 运行测试
uv run pytest

# 代码检查与格式化
uv run ruff check .
uv run ruff format .
```

### CLI 交互命令

在对话中可以用 `/` 开头的命令：

| 命令 | 作用 |
| --- | --- |
| `/exit`、`/quit` | 退出程序 |
| `/clear` | 清空当前对话历史 |
| `/skills` | 查看已注册的技能列表 |
| `/help` | 显示帮助 |

### 工具能力（toolcall）

Agent 采用 **toolcall 协议** 自主使用工具：

- 启动时把工具列表（名称 + 描述 + 参数 JSON Schema）随消息发给模型；
- 模型自行决定**是否**调用、调用**哪个**工具、传什么参数；
- Agent 在本地真实执行工具，把结果回填给模型，进入下一轮，直到模型给出最终回复。

内置工具：**bash**（在 Git Bash 中执行命令，`~` 展开为用户主目录，强制 UTF-8 编码）。

**工具确认策略**（基于 [`config/bash_blacklist.txt`](config/bash_blacklist.txt) 黑名单）：

| 工具/场景 | 确认策略 | 显示 |
|-----------|---------|------|
| `use_skill`（技能调用） | 免确认 | `[使用技能] 技能名` |
| `bash`（黑名单命令，如 `rm`、`format`） | 需确认 | `[危险命令] rm ...` + `允许执行？[Y/n]` |
| `bash`（非黑名单命令，如 `ls`、`echo`） | 免确认 | `[执行命令] ls ...` |
| 其他工具 | 免确认 | — |

黑名单文件每行一个正则表达式，可自由编辑，重启生效。工具/技能的输入输出详情不展示，保持对话界面简洁。

> 想新增工具？参考 [`src/personal_assistant/tools/README.md`](src/personal_assistant/tools/README.md)，
> 只需继承 `Tool` 实现 4 个字段，无需关心模型协议（已解耦）。

### 技能系统（Skill）

技能是比工具更高层的能力单元，以**文件夹**形式存在。每个技能是一个包含 `SKILL.md`
的子文件夹，模型阅读文档后按说明执行任务。

**工作流程**：

1. 对话时，`use_skill` 工具描述中列出所有技能的**名称 + 描述**（精简信息）；
2. 模型决定使用某技能 → 调用 `use_skill("技能名")`；
3. 系统返回该技能的 **SKILL.md 全文 + 所有 markdown 文件**（含子文件夹）；
4. 模型阅读文档 → 按说明执行任务（可能配合 bash 等工具）。

内置技能：**Web Search**（使用必应搜索网络信息，获取实时新闻和资讯）。

> 想新增技能？参考 [`src/personal_assistant/skills/README.md`](src/personal_assistant/skills/README.md)，
> 只需在 `skills/` 下创建文件夹 + `SKILL.md`，无需改任何代码。

### Token 消耗统计

每轮对话结束后，CLI 自动显示本轮 Token 消耗统计：

```
[Token] 输入 23362 | 输出 1150 | 总计 24512 | 缓存命中 17408 | 推理 462
```

兼容 OpenAI 标准格式（`prompt_tokens_details.cached_tokens`）与 DeepSeek 扩展格式
（`prompt_cache_hit_tokens`），涵盖输入、输出、总计、缓存命中、推理五个维度。

### 流式输出

模型回复**逐字流式输出**，无需等待完整生成。工具调用阶段暂停流式，
工具执行完毕后自动恢复。通过 OpenAI 兼容的 `stream=True` + `stream_options`
实现，同时支持流式模式下的 Token 统计提取。

### 系统提示词变量

系统提示词中可使用 `{{variable_name}}` 格式的变量占位符。Agent 在每次对话前
解析变量值并**追加到提示词末尾**——原文中的占位符不被替换，以最大化 prompt cache 命中率。

内置变量：`{{current_time}}`、`{{current_date}}`、`{{os}}`。
可通过 `agent.register_var(name, resolver)` 注册自定义变量。

```json
// config/model.json 示例
{
  "system_prompt": "你是一个个人助理。当前时间：{{current_time}}，运行环境：{{os}}。"
}
```

实际发给模型的内容（占位符保留 + 变量值追加）：
```
你是一个个人助理。当前时间：{{current_time}}，运行环境：{{os}}。

---variables---
current_time: 2025-06-21 14:30:00
os: Windows 11
```

### 对话示例

以下是一次真实对话的简化输出，展示流式输出、工具调用、技能使用与 Token 统计的完整流程：

```
你 > 请搜索一下关于马斯克的最新新闻
助理 >   [使用技能] Web Search
  [执行命令] python ".../skills/websearch/search.py" "Elon Musk latest news"
以下是关于马斯克的一些最新新闻：    ← 文本流式输出，逐字显示
  1. ...
  2. ...

[Token] 输入 23362 | 输出 1150 | 总计 24512 | 缓存命中 17408 | 推理 462
```

- **流式输出**：模型文本逐字实时显示，工具调用间隙暂停
- **技能调用**免确认，仅显示 `[使用技能] 技能名`
- **bash 命令**：仅黑名单命令（删除/格式化等）需确认，其余自动放行并显示 `[执行命令]`
- 工具/技能的**输入输出详情不展示**，保持对话界面简洁
- Agent 先调用 `use_skill` 获取技能文档，再按文档用 `bash` 执行搜索，
  最后阅读结果为用户总结——整个过程由模型自主决策

## 如何扩展

本项目提供两种扩展方式，均无需修改核心代码：

| 特性 | Tool（工具） | Skill（技能） |
|------|-------------|--------------|
| 形式 | Python 类 | 文件夹 + `SKILL.md` |
| 模型调用方式 | 直接 toolcall | 通过 `use_skill` 间接调用 |
| 返回给模型的内容 | `run()` 的执行结果 | `SKILL.md` 全文 + 所有 `.md` 文件 |
| 适合场景 | 原子操作（执行命令、读文件） | 领域知识 + 多步骤任务指引 |
| 新增方式 | 写 Python 类 + 注册 | 创建文件夹 + 写 `SKILL.md` |

### 新增工具（Tool）

1. 继承 `Tool`，填写 `name` / `description` / `parameters`，实现 `run()`；
2. 在 `tools/__init__.default_tools()` 中注册。

详见 [`src/personal_assistant/tools/README.md`](src/personal_assistant/tools/README.md)。

### 新增技能（Skill）

1. 在 `skills/` 下创建子文件夹；
2. 编写 `SKILL.md`（名称 + 描述 + 正文）；
3. 可选添加辅助文件（脚本、更多 markdown 文档等）。

重启后自动发现，无需改代码。详见 [`src/personal_assistant/skills/README.md`](src/personal_assistant/skills/README.md)。

## 路线图

- [x] 项目骨架与工具链（uv + ruff + pytest + hatchling）
- [x] CLI 对话主程序（多轮对话、**流式输出**、模型可配置化）
- [x] Agent 工具调用能力（toolcall 协议、Bash 工具、自主编排）
- [x] 技能系统（文件夹式 `SKILL.md` + `use_skill` 工具 + 自动扫描）
- [x] Token 消耗统计（输入/输出/总计/缓存命中/推理，兼容 OpenAI/DeepSeek）
- [x] 内置 websearch 技能（Bing 搜索，标准库实现零依赖）
- [x] Bash 命令黑名单确认（仅危险命令需确认，可自定义黑名单文件）
- [x] 系统提示词变量（`{{variable}}` 占位符 + prompt cache 友好的追加模式）
- [ ] 更多内置工具（文件读写、剪贴板、系统通知等）
- [ ] 手机↔电脑传输层与配对
- [ ] 基于 LLM 的多步任务规划
- [ ] 技能/工具自动发现（entry points / 目录扫描）

## License

MIT
