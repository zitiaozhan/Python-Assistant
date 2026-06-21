"""内置技能集合与 ``use_skill`` 工具。

技能系统基于文件夹：每个子文件夹是一个技能，包含 ``SKILL.md``（名称 + 描述 + 正文）
及其他 markdown 文件。``SkillManager`` 自动扫描 ``skills/`` 目录加载所有技能。

模型通过 ``use_skill`` 工具调用技能时，系统返回该技能的完整 markdown 内容
（SKILL.md 全文 + 所有 .md 文件），模型据此执行任务。
"""

from __future__ import annotations

from typing import Any

from personal_assistant.core.skill import SkillFolder, SkillManager
from personal_assistant.core.tool import Tool

__all__ = [
    "SkillFolder",
    "SkillManager",
    "UseSkillTool",
    "default_skill_manager",
]


class UseSkillTool(Tool):
    """让模型通过 toolcall 协议使用已注册的技能。

    工具描述**动态**包含所有已注册技能的名称与描述（精简信息），
    模型据此决定是否使用某技能。调用后返回该技能的完整 markdown 内容，
    模型阅读后按说明执行任务（可能需要配合 bash 等其他工具）。
    """

    name = "use_skill"
    parameters = {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "要使用的技能名称（见上方可用技能列表）",
            },
        },
        "required": ["skill_name"],
    }

    def __init__(self, skill_manager: SkillManager) -> None:
        self.skill_manager = skill_manager

    @property
    def description(self) -> str:  # type: ignore[override]
        """动态生成描述，包含当前所有可用技能的名称与描述。"""
        skills = self.skill_manager.list()
        if not skills:
            return "使用一个已注册的技能（当前无可用技能）。"
        lines = [
            "使用一个已注册的技能。调用后返回该技能的详细说明文档（SKILL.md 全文"
            "及其他 markdown 文件），请仔细阅读后按说明操作。",
            "可用技能列表：",
        ]
        for s in skills:
            lines.append(f"  - {s.name}: {s.description}")
        return "\n".join(lines)

    def run(self, arguments: dict[str, Any]) -> str:
        skill_name = arguments.get("skill_name", "")
        return self.skill_manager.invoke(skill_name)


def default_skill_manager() -> SkillManager:
    """返回包含默认技能的 SkillManager 实例（自动扫描 skills/ 目录）。"""
    return SkillManager()
