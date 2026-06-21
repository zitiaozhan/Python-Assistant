# Python-Assistant

一个面向**个人助理**的 Agent 项目，目标是打通**手机与电脑的协作**，并通过
**插件化架构**实现可持续扩展的能力体系。

> 当前状态：仅完成项目骨架（目录结构、构建/测试工具链、核心抽象的占位定义），
> 尚未实现任何具体功能。

---

## 设计目标

1. **个人助理** — 理解用户意图，并代表用户采取行动。
2. **手机 ↔ 电脑协作** — 同一个助理跨越手机与电脑两端，共享上下文，
   将任务委派给最合适的设备。
3. **可不断扩展** — 新增能力无需改动核心代码，理想情况下可作为独立分发的包
   插入到系统中。

## 目录结构

```
Python-Assistant/
├── src/personal_assistant/
│   ├── core/          # Agent 基类、Capability/Plugin 等核心抽象（占位）
│   ├── plugins/       # 内置能力插件（预留命名空间）
│   └── sync/          # 手机↔电脑协作层：传输、配对、共享状态（预留）
├── tests/             # 冒烟测试，守护骨架不被破坏
├── docs/
│   └── ARCHITECTURE.md   # 架构与扩展机制说明
├── pyproject.toml     # 项目元信息、依赖、工具配置
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

### 常用命令

```bash
# 运行测试
uv run pytest

# 代码检查与格式化
uv run ruff check .
uv run ruff format .

# 运行 CLI（当前仅打印版本信息）
uv run personal-assistant
# 或
uv run python -m personal_assistant
```

## 如何扩展（预告）

本项目采用「插件优先」的扩展方式，而非修改核心代码：

1. 继承 `Capability`，实现 `can_handle(intent)` 与 `run(intent, context)`；
2. 将相关能力组合进一个 `Plugin`；
3. 在启动时把插件注册给 `Agent`。

> 插件的自动发现机制（entry points / 目录扫描）将在后续里程碑实现。
> 详细设计见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

## 路线图

- [x] 项目骨架与工具链
- [ ] 插件注册表与意图分发
- [ ] 第一个内置能力（如剪贴板同步）
- [ ] 手机↔电脑传输层与配对
- [ ] 基于 LLM 的意图理解

## License

MIT
