# Python-Assistant

一个面向**个人助理**的 Agent 项目，目标是打通**手机与电脑的协作**，并通过
**插件化架构**实现可持续扩展的能力体系。

> 当前状态：已实现 **Web UI 对话 + Markdown 渲染 + Agent 工具调用 + 技能系统 + Token 统计 + 系统提示词变量 + 配置管理 + 手机扫码远程访问**。Agent 能自主决定是否调用工具或技能，在本地真实执行，文本流式输出，并在每轮对话后报告 Token 消耗。手机端可通过 QR 码扫描连接到同一对话会话，实现双向消息同步。

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
用户输入（Web / 手机 / CLI）
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
           例：websearch → 搜索 Bing/Sogou 并返回结果
```

- **Agent** 只操作 `protocol.py` 中定义的类型（`Message` / `ToolSpec` / `ToolCall`…），
  完全不感知模型的线上格式。
- **LLMClient** 负责双向翻译（内部类型 ↔ OpenAI 兼容格式）并提取 Token 用量。
- **Tool** 和 **Skill** 是两种扩展方式，均无需修改核心代码。
- **Web 层** 采用广播 WebSocket 架构，PC 和手机共享同一对话历史，所有消息双向同步。

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
│   │   ├── bash.py            #   bash 工具（执行 shell 命令，强制 UTF-8）
│   │   ├── __init__.py        #   default_tools() 默认工具清单
│   │   └── README.md          #   如何新增工具
│   ├── skills/
│   │   ├── __init__.py        #   UseSkillTool + default_skill_manager()
│   │   ├── README.md          #   如何新增技能
│   │   └── websearch/         #   内置技能：Bing + Sogou 双引擎搜索
│   │       ├── SKILL.md       #     名称 + 描述 + 使用说明（含引擎选择指南）
│   │       └── search.py      #     搜索脚本（标准库实现，无额外依赖）
│   ├── cli.py                 # 命令行 REPL（流式输出 + 工具确认门禁 + Token 展示）
│   ├── web.py                 # FastAPI Web 服务（REST API + 广播 WebSocket + 静态文件）
│   ├── config.py              # 加载 model.json，支持环境变量覆盖
│   ├── plugins/               # （预留）能力插件命名空间
│   └── sync/                  # （预留）手机↔电脑协作层
├── web/                       # 前端静态资源（由 /static/ 路由提供）
│   ├── index.html             #   主 SPA 入口（精简骨架，引用外部 CSS/JS）
│   ├── mobile.html            #   手机端页面（触控优化，独立 WebSocket 会话共享）
│   ├── css/
│   │   ├── variables.css      #   CSS 设计 Token（颜色、阴影、圆角、动画）
│   │   ├── layout.css         #   侧边栏、主区域、导航
│   │   ├── chat.css           #   聊天气泡、Markdown 样式、流式光标
│   │   ├── components.css     #   按钮、卡片、表单、Toast、QR 弹窗
│   │   └── editor.css         #   技能编辑器（文件树、标签页、分屏预览）
│   └── js/
│       ├── utils.js           #   通用工具（$、escapeHtml、showToast、renderMarkdown）
│       ├── api.js             #   API 请求封装（apiGet/Post/Put/Delete）
│       ├── chat.js            #   WebSocket 对话（流式+Markdown 渲染、广播、历史回放）
│       ├── config.js          #   模型配置页
│       ├── tools.js           #   工具管理页
│       ├── skills.js          #   技能管理 + 文件编辑器工作空间
│       ├── blacklist.js       #   黑名单管理页
│       └── main.js            #   页面路由 + QR 码弹窗 + 应用初始化
├── config/
│   ├── model.json             # 真实配置（含 API key，.gitignore 忽略）
│   ├── model.json.example     # 配置模板（提交到版本库）
│   └── bash_blacklist.txt     # Bash 危险命令黑名单（正则表达式，每行一条）
├── tests/                     # 单元测试 + Agent 编排测试 + 真实 LLM 验收测试
├── docs/
│   └── ARCHITECTURE.md        # 架构与扩展机制说明
├── requirements.md            # 依赖清单（运行时 + 开发 + 传递依赖）
├── pyproject.toml             # 项目元信息、依赖、工具配置
└── README.md
```

## 技术栈

| 能力         | 选型                          |
| ------------ | ----------------------------- |
| 语言         | Python ≥ 3.12                 |
| 依赖/环境    | [uv](https://github.com/astral-sh/uv) |
| Web 框架     | FastAPI + Uvicorn             |
| 前端         | 原生 JS + CSS（无构建工具，模块化文件）|
| 搜索引擎     | DuckDuckGo（ddgs 库）|
| QR 码生成    | Python `qrcode` 库（SVG 输出）|
| 测试         | pytest                        |
| Lint/Format  | ruff（uv 自带）               |
| 打包         | hatchling                     |

## 快速开始

### 前置条件

- Python ≥ 3.12
- 推荐安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)（可选，也支持 pip + venv）
- 依赖清单：请查看 [requirements.md](requirements.md)，启动项目前需确保所有依赖已安装

### 安装依赖

> ⚠️ **重要**：首次运行或拉取新代码后，请先安装依赖，否则可能出现 `ModuleNotFoundError`。

完整依赖清单及说明见 [requirements.md](requirements.md)。

### 初始化环境

```bash
# 方式 A：使用 uv（推荐，自动使用清华镜像源）
uv sync

# 方式 B：使用 pip + venv
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

### 配置模型

复制配置模板并填入你的 API key：

```bash
cp config/model.json.example config/model.json
# 编辑 config/model.json，把 api_key 改成你的真实 key
```

也可不修改文件，改用环境变量（优先级更高，便于 CI / 容器）：

```bash
export DEEPSEEK_API_KEY=sk-xxxx
```

更换模型或供应商时，只需改 `config/model.json` 里的 `base_url` 与 `model`
（只要对方提供 OpenAI 兼容接口，如 OpenAI、Moonshot、通义千问等）。

### 常用命令

```bash
# 启动 Web UI 服务（浏览器访问 http://127.0.0.1:8000）
.venv/bin/uvicorn personal_assistant.web:app --host 0.0.0.0 --port 8000 --reload

# 或使用 entry point（若已安装）
uv run personal-assistant-web

# 启动 CLI 对话（多轮、流式输出）
uv run personal-assistant

# 运行测试
uv run pytest

# 代码检查与格式化
uv run ruff check .
uv run ruff format .
```

> **注意**：Web 服务使用 `--host 0.0.0.0` 以允许局域网内手机访问。

---

## Web UI

### 启动

```bash
.venv/bin/uvicorn personal_assistant.web:app --host 0.0.0.0 --port 8000 --reload
```

浏览器访问 `http://127.0.0.1:8000` 即可使用。

### 功能页面

| 页面 | 功能 |
|------|------|
| 对话 | 流式对话、**Markdown 渲染**、代码块复制、工具调用展示、Token 统计 |
| 模型配置 | 修改 Base URL、API Key、模型名、Temperature、Max Tokens、System Prompt |
| 工具管理 | 查看已注册工具的列表和描述 |
| 技能管理 | 查看、新建、编辑、删除技能（文件夹 + SKILL.md + 文件编辑器） |
| 黑名单 | 查看、添加、删除 Bash 危险命令正则规则 |

### Markdown 渲染

AI 的回复支持完整 Markdown 渲染，包括：

- 标题（`#` ~ `######`）、粗体、斜体、删除线
- 无序/有序列表、引用块、水平线
- 行内代码 + **代码块**（附「复制」按钮）
- 链接与图片

流式输出时先显示原始文本（实时反馈），消息完成后自动渲染为 Markdown。

### 手机扫码访问

PC 和手机可通过同一个 WebSocket 会话共享对话，消息双向实时同步：

1. 点击聊天头部的 📱 **二维码按钮**；
2. 弹窗显示 QR 码和手机访问链接（局域网 IP）；
3. 手机扫码或手动访问链接，打开移动端专属页面；
4. 在手机上发送消息，AI 在**电脑端执行任务**；
5. 电脑端发出的消息和 AI 的回复，**手机端同步可见**。

```
手机浏览器 ─ ws://192.168.x.x:8000/ws/chat ─┐
                                              ├──► Agent ──► 工具执行（在电脑本地）
PC 浏览器  ─ ws://192.168.x.x:8000/ws/chat ─┘
```

新设备连接时会自动收到**历史消息回放**，可继续查看之前的对话。

---

## 技能系统（Skill）

技能是比工具更高层的能力单元，以**文件夹**形式存在。每个技能是一个包含 `SKILL.md`
的子文件夹，模型阅读文档后按说明执行任务。

**工作流程**：

1. 对话时，`use_skill` 工具描述中列出所有技能的**名称 + 描述**（精简信息）；
2. 模型决定使用某技能 → 调用 `use_skill("技能名")`；
3. 系统返回该技能的 **SKILL.md 全文 + 所有 markdown 文件**（含子文件夹）；
4. 模型阅读文档 → 按说明执行任务（可能配合 bash 等工具）。

### 内置技能：Web Search

使用 **Bing（cn.bing.com）+ Sogou** 双引擎聚合搜索，获取实时信息：

```bash
# 自动选择引擎（中文 → Sogou，英文 → Bing）
python3 "/path/to/skills/websearch/search.py" "马斯克 最新消息"

# 明确指定引擎
python3 ".../search.py" "特斯拉财报" --engine sogou --num 8

# 新闻搜索 + 时间范围
python3 ".../search.py" "AI 大模型" --type news --time w
```

| 参数 | 说明 |
|------|------|
| `--engine auto` | 自动选（默认）：中文→Sogou，英文→Bing |
| `--engine bing` | Bing 搜索（技术/英文内容更好） |
| `--engine sogou` | Sogou 搜索（中文新闻/资讯更好） |
| `--type web/news` | 普通搜索 / 新闻搜索 |
| `--time d/w/m/y` | 时间范围：一天/一周/一月/一年 |
| `--num N` | 返回条数（1-30，默认 10） |

> **实现说明**：纯标准库实现（无外部依赖），自动过滤 Bing China 的审查替代内容（汉字字典词条等），并发解析 Sogou 重定向链接。

---

## 工具能力（toolcall）

Agent 采用 **toolcall 协议** 自主使用工具：

- 启动时把工具列表（名称 + 描述 + 参数 JSON Schema）随消息发给模型；
- 模型自行决定**是否**调用、调用**哪个**工具、传什么参数；
- Agent 在本地真实执行工具，把结果回填给模型，进入下一轮，直到模型给出最终回复。

内置工具：**bash**（执行 shell 命令，`~` 展开为用户主目录，强制 UTF-8 编码）。

**工具确认策略**（基于 [`config/bash_blacklist.txt`](config/bash_blacklist.txt) 黑名单）：

| 工具/场景 | 确认策略 | 显示 |
|-----------|---------|------|
| `use_skill`（技能调用） | 免确认 | `[使用技能] 技能名` |
| `bash`（黑名单命令，如 `rm`、`format`） | 需确认 | 弹窗显示命令 + 允许/拒绝 |
| `bash`（非黑名单命令，如 `ls`、`echo`） | 免确认 | `[执行命令] ls ...` |
| 其他工具 | 免确认 | — |

黑名单文件每行一个正则表达式，可自由编辑，重启生效。

---

## CLI 交互命令

在命令行对话中可以用 `/` 开头的命令：

| 命令 | 作用 |
| --- | --- |
| `/exit`、`/quit` | 退出程序 |
| `/clear` | 清空当前对话历史 |
| `/skills` | 查看已注册的技能列表 |
| `/help` | 显示帮助 |

---

## Token 消耗统计

每轮对话结束后，CLI 自动显示本轮 Token 消耗统计（Web UI 显示在对话区底部）：

```
[Token] 输入 23362 | 输出 1150 | 总计 24512 | 缓存命中 17408 | 推理 462
```

兼容 OpenAI 标准格式（`prompt_tokens_details.cached_tokens`）与 DeepSeek 扩展格式
（`prompt_cache_hit_tokens`），涵盖输入、输出、总计、缓存命中、推理五个维度。

---

## 系统提示词变量

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
os: macOS 14.4
```

---

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

---

## 路线图

- [x] 项目骨架与工具链（uv + ruff + pytest + hatchling）
- [x] CLI 对话主程序（多轮对话、**流式输出**、模型可配置化）
- [x] Agent 工具调用能力（toolcall 协议、Bash 工具、自主编排）
- [x] 技能系统（文件夹式 `SKILL.md` + `use_skill` 工具 + 自动扫描）
- [x] Token 消耗统计（输入/输出/总计/缓存命中/推理，兼容 OpenAI/DeepSeek）
- [x] 内置 websearch 技能（Bing + Sogou 双引擎，标准库实现，自动适配中国网络环境）
- [x] Bash 命令黑名单确认（仅危险命令需确认，可自定义黑名单文件）
- [x] 系统提示词变量（`{{variable}}` 占位符 + prompt cache 友好的追加模式）
- [x] Web UI（FastAPI + WebSocket 实时对话 + 配置/工具/技能/黑名单管理）
- [x] **前端模块化重构**（CSS/JS 拆分为独立文件，index.html 从 2321 行精简至 301 行）
- [x] **Markdown 渲染**（流式光标 + 代码块复制按钮 + 完整 Markdown 语法支持）
- [x] **UI 现代化**（新设计语言：气泡样式、卡片阴影、动画、QR 码弹窗）
- [x] **手机扫码访问**（广播 WebSocket + 共享会话历史 + 历史回放 + 移动端专属页面）
- [ ] 更多内置工具（文件读写、剪贴板、系统通知等）
- [ ] 技能/工具自动发现（entry points / 目录扫描）
- [ ] 危险命令确认的跨设备同步（手机端也能确认/拒绝）
- [ ] 基于 LLM 的多步任务规划

## License

MIT
