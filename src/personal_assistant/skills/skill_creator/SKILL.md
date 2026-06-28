# Skill Creator（技能创建器）

> 帮助用户在对话中创建新的 Skill，自动生成文件夹结构、SKILL.md 模板和脚本文件，让 Agent 可以自己扩展能力。

## 使用场景

- 用户想要添加自定义功能
- Agent 发现自己需要新能力来完成任务
- 想要为特定场景创建专用工具

## 使用步骤

1. 用 bash 工具执行技能创建脚本：

```bash
python "<技能文件夹>/create_skill.py" "技能名称" "技能描述" [--script]
```

参数：
- `技能名称` - 技能的英文标识符（如 weather、news）
- `技能描述` - 一句话描述技能功能
- `--script` - 可选，是否同时创建脚本模板

注意：`<技能文件夹>` 的实际路径已在技能内容开头的 `[技能文件夹: ...]` 中给出，请替换为实际路径。

2. 脚本会在 `skills/` 目录下创建新技能文件夹，包含：
   - `SKILL.md` - 技能文档模板
   - `script.py` - 脚本模板（如果使用了 --script）

3. 编辑生成的 SKILL.md，完善使用说明和示例。
4. 重启 Web 服务或 CLI，新技能会被自动发现并加载。

## 示例

```bash
# 创建简单技能（只有 SKILL.md）
python "/path/to/skills/skill_creator/create_skill.py" "timer" "计时器和提醒工具"

# 创建带脚本的技能
python "/path/to/skills/skill_creator/create_skill.py" "translator" "多语言翻译工具" --script

# 创建文件整理技能
python "/path/to/skills/skill_creator/create_skill.py" "pdf_reader" "PDF 内容提取和搜索" --script
```

## SKILL.md 模板格式

生成的 SKILL.md 包含以下结构：

```markdown
# Skill Name（技能中文名）

> 一句话描述，说明此技能做什么、何时使用。

## 使用场景

- 场景1
- 场景2

## 使用步骤

1. 用 bash 工具执行...

## 示例

```bash
python "<技能文件夹>/script.py" "参数"
```

## 注意事项

- 注意事项1
- 注意事项2
```

## 注意事项

- 技能名称使用英文小写，用下划线分隔（如 file_organizer）
- 创建后需要手动编辑 SKILL.md 完善内容
- 如果创建了脚本，需要测试脚本功能是否正常
- 新技能会在下次服务启动时自动加载
