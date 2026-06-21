"""Skill 抽象——基于文件夹的技能系统。

每个 Skill 是 ``skills/`` 目录下的一个子文件夹，至少包含 ``SKILL.md``。

``SKILL.md`` 格式::

    # 技能名称

    > 一句话描述，说明此技能做什么、何时使用。

    正文内容：详细的使用说明、步骤、注意事项等。

交互协议（参照 toolcall）：
- 对话时只把技能的 **名称 + 描述** 提供给模型（通过 ``use_skill`` 工具描述）；
- 模型决定使用某技能时，调用 ``use_skill`` → 系统返回 ``SKILL.md`` 全文
  及技能文件夹下所有 markdown 文件内容（含子文件夹），模型据此执行任务。
"""

from __future__ import annotations

from pathlib import Path

from personal_assistant.core.protocol import ToolSpec


class SkillFolder:
    """从文件夹加载的技能。

    文件夹结构::

        skills/my_skill/
        ├── SKILL.md          ← 必需：名称 + 描述 + 正文
        ├── guide.md          ← 可选：补充说明
        ├── examples/         ← 可选：子文件夹
        │   └── case.md
        └── search.py         ← 可选：非 markdown 文件（不自动加载，但可在 SKILL.md 中引用）
    """

    def __init__(self, folder_path: str | Path) -> None:
        self.folder_path = Path(folder_path).resolve()
        self.name: str = ""
        self.description: str = ""
        self.body: str = ""
        self._parse_skill_md()

    def _parse_skill_md(self) -> None:
        """解析 SKILL.md，提取名称、描述与正文。

        - 第一个 ``#`` 行 → 名称；
        - 第一个 ``>`` 行 → 描述；
        - 其余内容 → 正文。
        """
        skill_md = self.folder_path / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"技能文件夹缺少 SKILL.md: {self.folder_path}")

        text = skill_md.read_text(encoding="utf-8")
        lines = text.splitlines()

        # 跳过前导空行，提取名称
        idx = 0
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        if idx < len(lines) and lines[idx].lstrip().startswith("#"):
            self.name = lines[idx].lstrip("#").strip()
            idx += 1

        # 跳过空行，提取描述
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        if idx < len(lines) and lines[idx].lstrip().startswith(">"):
            self.description = lines[idx].lstrip(">").strip()
            idx += 1

        # 剩余内容为正文
        self.body = "\n".join(lines[idx:]).strip()

    def load_content(self) -> str:
        """加载技能的完整内容：SKILL.md 全文 + 所有 markdown 文件。

        返回的文本以技能文件夹路径开头，方便模型引用文件夹内的脚本等资源。
        SKILL.md 始终排在最前面，其余 markdown 文件按相对路径排序。
        """
        parts: list[str] = [
            f"[技能文件夹: {self.folder_path}]",
            "",
        ]

        # SKILL.md 全文（包含名称、描述、正文）
        skill_md = self.folder_path / "SKILL.md"
        parts.append("=== SKILL.md ===")
        parts.append(skill_md.read_text(encoding="utf-8").rstrip())
        parts.append("")

        # 递归收集其他 markdown 文件
        other_mds = sorted(p for p in self.folder_path.rglob("*.md") if p.name != "SKILL.md")
        for md_path in other_mds:
            rel = md_path.relative_to(self.folder_path)
            parts.append(f"=== {rel} ===")
            parts.append(md_path.read_text(encoding="utf-8").rstrip())
            parts.append("")

        return "\n".join(parts)

    def to_spec(self) -> ToolSpec:
        """返回名称 + 描述（发给模型的精简声明）。"""
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={"type": "object", "properties": {}},
        )

    def __repr__(self) -> str:
        return f"SkillFolder(name={self.name!r}, folder={self.folder_path!s})"


class SkillManager:
    """技能注册表：扫描目录、加载技能、按名称调用。

    用法::

        manager = SkillManager()          # 自动扫描默认 skills/ 目录
        manager.list()                    # 列出所有技能
        manager.invoke("websearch")       # 返回技能完整内容
    """

    def __init__(self, skills_dir: str | Path | None = None) -> None:
        """初始化技能管理器。

        Args:
            skills_dir: 技能根目录。为 None 时使用默认目录
                （``personal_assistant/skills/`` 包目录）。
        """
        self._skills: dict[str, SkillFolder] = {}
        self._skills_dir = Path(skills_dir) if skills_dir else _default_skills_dir()
        self._scan()

    def _scan(self) -> None:
        """扫描技能目录，加载所有包含 SKILL.md 的子文件夹。"""
        if not self._skills_dir.is_dir():
            return
        for entry in sorted(self._skills_dir.iterdir()):
            if entry.is_dir() and (entry / "SKILL.md").exists():
                try:
                    skill = SkillFolder(entry)
                    self._skills[skill.name] = skill
                except Exception:  # noqa: BLE001 - 跳过加载失败的技能
                    pass

    def register(self, skill: SkillFolder) -> None:
        """手动注册一个技能。同名技能会被覆盖。"""
        self._skills[skill.name] = skill

    def unregister(self, name: str) -> bool:
        """移除技能，返回是否成功。"""
        return self._skills.pop(name, None) is not None

    def get(self, name: str) -> SkillFolder | None:
        """按名称获取技能。"""
        return self._skills.get(name)

    def list(self) -> list[SkillFolder]:
        """返回所有已注册的技能列表。"""
        return list(self._skills.values())

    def invoke(self, name: str) -> str:
        """按名称调用技能——返回技能的完整内容供模型阅读。

        技能不存在时返回友好提示，不抛异常。
        """
        skill = self._skills.get(name)
        if skill is None:
            available = ", ".join(self._skills) or "(无)"
            return f"未知技能：{name}。可用技能：{available}"
        return skill.load_content()


def _default_skills_dir() -> Path:
    """返回默认技能目录（本包所在的 skills/ 文件夹）。"""
    return Path(__file__).resolve().parent.parent / "skills"
