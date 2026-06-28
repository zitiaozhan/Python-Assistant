#!/usr/bin/env python3
"""菜谱查询脚本——使用网络搜索获取菜谱信息。

用法::

    python recipe.py "菜名"
    python recipe.py "宫保鸡丁"
    python recipe.py "番茄"

输出格式::

    搜索: 宫保鸡丁
    找到 5 个菜谱:

    [1] 宫保鸡丁（经典川菜）
        食材: 鸡胸肉、花生、干辣椒...
        步骤:
        1. 鸡胸肉切丁，加料酒、淀粉腌制
        2. ...
"""

from __future__ import annotations

import sys

# Windows 终端默认 GBK 编码，强制 stdout 使用 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def search_recipe(query: str, num: int = 5) -> str:
    """搜索菜谱，返回格式化文本。"""
    if not query.strip():
        return "错误：请输入菜名或食材"

    # 尝试使用 websearch 技能搜索菜谱
    try:
        from personal_assistant.skills.websearch.search import search as web_search
        result = web_search(f"{query} 菜谱 做法", num)
        return result
    except ImportError:
        # 如果 websearch 不可用，使用 ddgs 直接搜索
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(f"{query} 菜谱 做法", max_results=num))

            if not results:
                return f"搜索: {query}\n未找到相关菜谱。"

            lines = [f"搜索: {query} 菜谱", f"找到 {len(results)} 个结果:", ""]
            for i, r in enumerate(results, 1):
                lines.append(f"[{i}] {r.get('title', '')}")
                lines.append(f"    链接: {r.get('href', '')}")
                body = r.get("body", "")
                if body:
                    lines.append(f"    摘要: {body[:200]}...")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"搜索失败：{e!r}\n\n建议：\n1. 检查网络连接\n2. 使用 websearch 技能搜索"


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python recipe.py <菜名或食材>")
        print("示例: python recipe.py 宫保鸡丁")
        return 1

    query = " ".join(sys.argv[1:])
    print(search_recipe(query))
    return 0


if __name__ == "__main__":
    sys.exit(main())
