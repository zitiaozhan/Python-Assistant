#!/usr/bin/env python3
"""Bing 搜索脚本——使用标准库实现，无需额外依赖。

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

import re
import sys
import urllib.parse
import urllib.request
from html import unescape

# Windows 终端默认 GBK 编码，强制 stdout 使用 UTF-8 避免中文/特殊字符报错。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


def _strip_tags(html: str) -> str:
    """去除 HTML 标签，保留纯文本。"""
    text = re.sub(r"<[^>]+>", "", html)
    return unescape(text).strip()


def _fetch_bing(query: str, num: int = 10) -> str:
    """请求 Bing 搜索页面，返回 HTML 文本。"""
    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count={num}&setlang=zh-CN"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read()
    # Bing 通常返回 UTF-8
    return raw.decode("utf-8", errors="replace")


def _parse_results(html: str, max_results: int = 10) -> list[dict[str, str]]:
    """从 Bing HTML 中提取搜索结果。"""
    results: list[dict[str, str]] = []

    # Bing 搜索结果在 <li class="b_algo"> 块中
    blocks = re.findall(r'<li[^>]*class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)

    for block in blocks[:max_results]:
        # 提取标题和链接：<h2 ...><a href="URL">TITLE</a></h2>
        title_match = re.search(
            r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL
        )
        if not title_match:
            continue
        url = unescape(title_match.group(1))
        title = _strip_tags(title_match.group(2))
        if not title:
            continue

        # 提取摘要：优先 <div class="b_caption"> 中的 <p>，其次任意 <p>
        snippet = ""
        # 尝试从 b_caption 中提取
        cap_match = re.search(r'<div[^>]*class="b_caption"[^>]*>(.*?)</div>', block, re.DOTALL)
        search_area = cap_match.group(1) if cap_match else block
        # 提取所有 <p> 标签内容，取最长的作为摘要
        p_matches = re.findall(r"<p[^>]*>(.*?)</p>", search_area, re.DOTALL)
        if p_matches:
            snippet = max((_strip_tags(p) for p in p_matches), key=len)

        results.append({"title": title, "url": url, "snippet": snippet})

    return results


def search(query: str, num: int = 10) -> str:
    """执行 Bing 搜索，返回格式化文本结果。"""
    if not query.strip():
        return "错误：搜索关键词为空"

    try:
        html = _fetch_bing(query, num)
    except Exception as exc:  # noqa: BLE001
        return f"搜索失败：{exc!r}"

    results = _parse_results(html, num)

    if not results:
        return f"搜索: {query}\n未找到搜索结果。"

    lines = [f"搜索: {query}", f"共找到 {len(results)} 条结果:", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}")
        lines.append(f"    链接: {r['url']}")
        if r["snippet"]:
            lines.append(f"    摘要: {r['snippet']}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("用法: python search.py <搜索关键词> [--num N]")
        return 1

    # 解析 --num 参数
    num = 10
    query_parts = []
    i = 0
    while i < len(args):
        if args[i] == "--num" and i + 1 < len(args):
            try:
                num = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        else:
            query_parts.append(args[i])
            i += 1

    query = " ".join(query_parts)
    if not query:
        print("错误：请提供搜索关键词")
        return 1

    print(search(query, num))
    return 0


if __name__ == "__main__":
    sys.exit(main())
