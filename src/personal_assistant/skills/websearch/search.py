#!/usr/bin/env python3
"""网络搜索脚本——基于 duckduckgo-search，支持中英文搜索。

用法::

    python search.py "搜索关键词"
    python search.py "马斯克 最新新闻" --num 5

输出格式::

    搜索: 关键词
    共找到 N 条结果:

    [1] 标题
        链接: https://...
        摘要: ...
"""

from __future__ import annotations

import sys

# Windows 终端默认 GBK 编码，强制 stdout 使用 UTF-8 避免中文/特殊字符报错。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


def search(query: str, num: int = 10, region: str = "cn-zh") -> str:
    """执行 DuckDuckGo 搜索，返回格式化文本结果。

    Args:
        query: 搜索关键词。
        num: 最大结果数。
        region: 搜索区域，默认 cn-zh（中国中文），可设为 wt-wt（全球）等。
    """
    if not query.strip():
        return "错误：搜索关键词为空"

    try:
        from ddgs import DDGS
    except ImportError:
        return "搜索失败：缺少依赖 ddgs，请运行 pip install ddgs"

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region=region, max_results=num))
    except Exception as exc:  # noqa: BLE001
        return f"搜索失败：{exc!r}"

    if not results:
        return f"搜索: {query}\n未找到搜索结果。"

    lines = [f"搜索: {query}", f"共找到 {len(results)} 条结果:", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.get('title', '')}")
        lines.append(f"    链接: {r.get('href', '')}")
        snippet = r.get("body", "")
        if snippet:
            lines.append(f"    摘要: {snippet}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("用法: python search.py <搜索关键词> [--num N] [--region REGION]")
        return 1

    # 解析参数
    num = 10
    region = "cn-zh"
    query_parts = []
    i = 0
    while i < len(args):
        if args[i] == "--num" and i + 1 < len(args):
            try:
                num = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        elif args[i] == "--region" and i + 1 < len(args):
            region = args[i + 1]
            i += 2
        else:
            query_parts.append(args[i])
            i += 1

    query = " ".join(query_parts)
    if not query:
        print("错误：请提供搜索关键词")
        return 1

    print(search(query, num, region))
    return 0


if __name__ == "__main__":
    sys.exit(main())
