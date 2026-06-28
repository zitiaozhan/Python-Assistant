#!/usr/bin/env python3
"""Skill 创建器——自动生成技能文件夹和模板文件。

用法::

    python create_skill.py "技能名称" "技能描述"
    python create_skill.py "timer" "计时器和提醒工具"
    python create_skill.py "translator" "多语言翻译工具" --script
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Windows 终端默认 GBK 编码，强制 stdout 使用 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def create_skill(name: str, description: str, with_script: bool = False) -> str:
    """创建新的 Skill 文件夹和模板文件。"""
    # 找到 skills 目录
    skills_dir = Path(__file__).resolve().parent.parent
    skill_folder = skills_dir / name

    # 检查是否已存在
    if skill_folder.exists():
        return f"错误：技能文件夹已存在 {skill_folder}"

    # 创建文件夹
    skill_folder.mkdir(parents=True, exist_ok=True)

    # 生成 SKILL.md
    skill_md = f"""# {name.replace('_', ' ').title()}（技能名称）

> {description}

## 使用场景

- 用户需要...
- 用户想要...

## 使用步骤

1. 用 bash 工具执行脚本：

```bash
python "<技能文件夹>/{name}.py" "参数"
```

注意：`<技能文件夹>` 的实际路径为 `{skill_folder}`

2. 脚本返回结果后，为用户总结关键信息。

## 示例

```bash
# 示例1
python "{skill_folder}/{name}.py" "示例参数"

# 示例2
python "{skill_folder}/{name}.py" "另一个参数"
```

## 注意事项

- 注意事项1
- 注意事项2
- 如果脚本执行失败，检查依赖是否安装
"""

    (skill_folder / "SKILL.md").write_text(skill_md, encoding="utf-8")

    # 可选：创建脚本模板
    script_path = skill_folder / f"{name}.py"
    if with_script:
        script_template = f'''#!/usr/bin/env python3
"""{name.replace('_', ' ').title()} 脚本——{description}。

用法::

    python {name}.py "参数"
"""

from __future__ import annotations

import sys

# Windows 终端默认 GBK 编码，强制 stdout 使用 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def {name}_function(arg: str) -> str:
    """实现{ description }功能。"""
    # TODO: 实现具体功能
    return f"处理结果: {{arg}}"


def main() -> int:
    if len(sys.argv) < 2:
        print(f"用法: python {name}.py <参数>")
        return 1

    arg = " ".join(sys.argv[1:])
    print({name}_function(arg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''
        script_path.write_text(script_template, encoding="utf-8")

    # 生成成功消息
    lines = [
        f"✓ 技能创建成功！",
        "",
        f"技能文件夹: {skill_folder}",
        f"技能名称: {name}",
        f"技能描述: {description}",
        "",
        "已生成文件:",
        f"  - SKILL.md ✓",
    ]
    if with_script:
        lines.append(f"  - {name}.py ✓")
    lines.extend([
        "",
        "下一步:",
        "1. 编辑 SKILL.md 完善使用说明和示例",
        "2. 如果创建了脚本，实现具体功能并测试",
        "3. 重启服务，新技能会被自动加载",
    ])

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="创建新的 Skill")
    parser.add_argument("name", help="技能名称（英文小写，下划线分隔）")
    parser.add_argument("description", help="技能描述（一句话说明功能）")
    parser.add_argument("--script", action="store_true", help="同时创建脚本模板")

    args = parser.parse_args()

    # 验证名称格式
    if not args.name.replace("_", "").isalnum():
        print("错误：技能名称只能包含英文字母、数字和下划线")
        return 1

    print(create_skill(args.name, args.description, args.script))
    return 0


if __name__ == "__main__":
    sys.exit(main())
