#!/usr/bin/env python3
"""文件整理脚本——按类型或日期自动整理文件夹。

用法::

    python fileorg.py "文件夹路径" [选项]
    python fileorg.py "~/Downloads"
    python fileorg.py "~/Downloads" --dry-run
    python fileorg.py "~/Documents" --by date
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Windows 终端默认 GBK 编码，强制 stdout 使用 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 文件类型映射
FILE_TYPES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico"],
    "Documents": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv"],
    "Videos": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"],
    "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
    "Code": [".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".go", ".rs"],
}


def get_category(filename: str) -> str:
    """根据文件扩展名返回分类名称。"""
    ext = Path(filename).suffix.lower()
    for category, extensions in FILE_TYPES.items():
        if ext in extensions:
            return category
    return "Others"


def get_date_folder(file_path: Path) -> str:
    """根据文件修改日期返回年月文件夹名（如 2024-01）。"""
    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
    return mtime.strftime("%Y-%m")


def organize_by_type(folder: Path, dry_run: bool = False) -> str:
    """按文件类型整理文件夹。"""
    moved = 0
    skipped = 0
    actions = []

    for item in folder.iterdir():
        if item.is_file():
            category = get_category(item.name)
            target_dir = folder / category
            target_file = target_dir / item.name

            # 处理同名文件
            if target_file.exists():
                stem = item.stem
                suffix = item.suffix
                counter = 1
                while target_file.exists():
                    target_file = target_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

            if dry_run:
                actions.append(f"[预览] {item.name} → {category}/")
            else:
                target_dir.mkdir(exist_ok=True)
                shutil.move(str(item), str(target_file))
                actions.append(f"[移动] {item.name} → {category}/")
            moved += 1
        elif item.is_dir() and item.name not in FILE_TYPES and item.name != "Others":
            skipped += 1

    lines = [f"{'[预览模式] ' if dry_run else ''}按类型整理: {folder}", f"共处理 {moved} 个文件:", ""]
    lines.extend(actions[:20])  # 最多显示 20 条
    if len(actions) > 20:
        lines.append(f"... 以及其他 {len(actions) - 20} 个文件")
    lines.append("")

    if not dry_run:
        lines.append(f"✓ 整理完成：{moved} 个文件已移动，{skipped} 个文件夹已跳过")
    else:
        lines.append(f"预览完成：{moved} 个文件将被移动")

    return "\n".join(lines)


def organize_by_date(folder: Path, dry_run: bool = False) -> str:
    """按修改日期整理文件夹。"""
    moved = 0
    actions = []

    for item in folder.iterdir():
        if item.is_file():
            date_folder = get_date_folder(item)
            target_dir = folder / date_folder
            target_file = target_dir / item.name

            # 处理同名文件
            if target_file.exists():
                stem = item.stem
                suffix = item.suffix
                counter = 1
                while target_file.exists():
                    target_file = target_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

            if dry_run:
                actions.append(f"[预览] {item.name} → {date_folder}/")
            else:
                target_dir.mkdir(exist_ok=True)
                shutil.move(str(item), str(target_file))
                actions.append(f"[移动] {item.name} → {date_folder}/")
            moved += 1

    lines = [f"{'[预览模式] ' if dry_run else ''}按日期整理: {folder}", f"共处理 {moved} 个文件:", ""]
    lines.extend(actions[:20])
    if len(actions) > 20:
        lines.append(f"... 以及其他 {len(actions) - 20} 个文件")
    lines.append("")

    if not dry_run:
        lines.append(f"✓ 整理完成：{moved} 个文件已移动")
    else:
        lines.append(f"预览完成：{moved} 个文件将被移动")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="文件整理工具")
    parser.add_argument("folder", help="要整理的文件夹路径")
    parser.add_argument("--by", choices=["type", "date"], default="type", help="整理方式（默认：type）")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际移动文件")

    args = parser.parse_args()

    folder = Path(args.folder).expanduser().resolve()
    if not folder.exists():
        print(f"错误：文件夹不存在 {folder}")
        return 1
    if not folder.is_dir():
        print(f"错误：路径不是文件夹 {folder}")
        return 1

    if args.by == "type":
        print(organize_by_type(folder, args.dry_run))
    else:
        print(organize_by_date(folder, args.dry_run))

    return 0


if __name__ == "__main__":
    sys.exit(main())
