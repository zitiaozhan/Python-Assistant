# Skills —— 技能系统使用与新增指南

技能（Skill）是 Agent 的高层能力单元。与工具（Tool）不同，技能以**文件夹**形式存在，
核心是一个 `SKILL.md` 文档，模型阅读后按文档说明执行任务。

## 工作原理

```
对话开始 → use_skill 工具描述中列出所有技能的名称+描述（精简信息）
    ↓
模型决定使用某技能 → 调用 use_skill("skill_name")
    ↓
系统返回该技能的完整文档（SKILL.md 全文 + 所有 .md 文件）
    ↓
模型阅读文档 → 按说明执行任务（可能配合 bash 等工具）
```

## 目录结构

```
src/personal_assistant/skills/
├── __init__.py          ← UseSkillTool + 默认 SkillManager
├── README.md            ← 本文件
└── websearch/           ← 内置技能：网络搜索
    ├── SKILL.md         ← 技能定义（名称 + 描述 + 正文）
    └── search.py        ← 搜索脚本（SKILL.md 中引用）
```

`SkillManager` 启动时自动扫描 `skills/` 目录，将每个含 `SKILL.md` 的子文件夹加载为技能。

## SKILL.md 格式

```markdown
# 技能名称

> 一句话描述：说明此技能做什么、何时使用。

正文内容：详细的使用说明、步骤、示例、注意事项等。
模型在调用 use_skill 后会看到这里的所有内容。
```

- **第一行 `#`** → 技能名称（全局唯一，小写下划线推荐）
- **第一行 `>`** → 技能描述（模型决策的关键信号，写清做什么+何时用）
- **其余内容** → 正文（使用说明、步骤、示例等）

## 新增一个技能：3 步

### 1. 创建技能文件夹

在 `skills/` 下新建子文件夹，添加 `SKILL.md`：

```
skills/my_skill/
└── SKILL.md
```

### 2. 编写 SKILL.md

```markdown
# My Skill

> 做某件事的技能。当用户需要XXX时使用。

## 使用步骤

1. 用 bash 工具执行：
   ```bash
   python "<技能文件夹>/script.py" "参数"
   ```

2. 阅读输出结果，为用户总结。
```

> `<技能文件夹>` 会在调用时被替换为实际路径，开头会显示 `[技能文件夹: /actual/path]`。

### 3.（可选）添加辅助文件

技能文件夹可包含任意文件：Python 脚本、配置文件、更多 markdown 文档等。

- **markdown 文件**（`.md`）：调用时自动加载，内容随 SKILL.md 一起返回给模型。
- **其他文件**：不自动加载，但可在 SKILL.md 中引用（如让模型用 bash 执行脚本）。

```
skills/my_skill/
├── SKILL.md          ← 主文档
├── guide.md          ← 补充说明（自动加载）
├── examples/
│   └── case.md       ← 示例（自动加载，含子文件夹）
└── script.py         ← 脚本（需在 SKILL.md 中指示模型用 bash 执行）
```

**无需修改任何代码**——重启程序后新技能自动被发现并可用。

## 技能 vs 工具

| 特性 | Tool | Skill |
|------|------|-------|
| 形式 | Python 类 | 文件夹 + SKILL.md |
| 模型调用方式 | 直接通过 toolcall | 通过 `use_skill` 间接调用 |
| 返回给模型的内容 | `run()` 的执行结果 | SKILL.md 全文 + 所有 .md 文件 |
| 适合场景 | 原子操作（执行命令、读文件） | 领域知识 + 多步骤任务指引 |
| 新增方式 | 写 Python 类 + 注册 | 创建文件夹 + 写 SKILL.md |

## 运行时管理

```python
from personal_assistant.skills import default_skill_manager

manager = default_skill_manager()

# 列出所有技能
for skill in manager.list():
    print(f"{skill.name}: {skill.description}")

# 按名称获取
skill = manager.get("websearch")

# 手动注册外部技能
from personal_assistant.core.skill import SkillFolder
manager.register(SkillFolder("/path/to/custom_skill"))

# 移除技能
manager.unregister("websearch")
```

在 Agent 中：

```python
from personal_assistant.skills import default_skill_manager

agent = Agent(llm, tools=..., skills=default_skill_manager())

# 运行时添加
agent.add_skill_from_folder("/path/to/skill_folder")

# 运行时移除
agent.remove_skill("skill_name")
```

## CLI 命令

在对话中输入 `/skills` 查看已注册的技能列表。

## 内置技能

| 技能 | 说明 |
|------|------|
| `websearch` | 使用必应搜索网络信息，获取实时新闻和资讯 |
