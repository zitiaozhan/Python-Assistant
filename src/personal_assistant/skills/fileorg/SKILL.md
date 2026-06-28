# File Organizer（文件整理）

> 根据文件类型、日期或自定义规则自动整理文件夹，帮助用户快速清理下载目录、整理项目文件。

## 使用场景

- 用户想清理混乱的下载文件夹
- 用户需要按类型（图片/文档/视频）分类文件
- 用户想按日期整理文件

## 使用步骤

1. 用 bash 工具执行文件整理脚本：

```bash
python "<技能文件夹>/fileorg.py" "文件夹路径" [选项]
```

选项：
- `--by type` - 按文件类型整理（默认）
- `--by date` - 按修改日期整理
- `--dry-run` - 预览模式（不实际移动文件）

注意：`<技能文件夹>` 的实际路径已在技能内容开头的 `[技能文件夹: ...]` 中给出，请替换为实际路径。

2. 脚本会报告整理结果（移动了多少文件，创建了什么文件夹）。
3. 如果使用 `--dry-run`，只会显示预览，不会实际移动文件。

## 示例

```bash
# 整理下载文件夹（按类型）
python "/path/to/skills/fileorg/fileorg.py" "~/Downloads"

# 预览整理效果（不实际移动）
python "/path/to/skills/fileorg/fileorg.py" "~/Downloads" --dry-run

# 按日期整理
python "/path/to/skills/fileorg/fileorg.py" "~/Documents" --by date

# 整理当前目录
python "/path/to/skills/fileorg/fileorg.py" "."
```

## 注意事项

- 首次使用建议加 `--dry-run` 预览效果
- 按类型整理会创建：Images/ Documents/ Videos/ Archives/ Others 等文件夹
- 按日期整理会创建：2024-01/ 2024-02/ 等年月文件夹
- 不会覆盖同名文件，会自动添加序号
- 操作不可撤销，请谨慎使用
