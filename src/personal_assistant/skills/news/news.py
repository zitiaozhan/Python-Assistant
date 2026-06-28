#!/usr/bin/env python3
"""新闻摘要脚本——聚合 RSS 源获取热点新闻。

用法::

    python news.py [类别]
    python news.py
    python news.py tech
    python news.py business

输出格式::

    今日技术新闻（共 10 条）:

    [1] 新闻标题
        摘要: ...
        链接: https://...
"""

from __future__ import annotations

import sys
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape

# Windows 终端默认 GBK 编码，强制 stdout 使用 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# RSS 源配置
RSS_FEEDS = {
    "tech": [
        "https://feeds.feedburner.com/36kr/tech",
        "https://rsshub.app/36kr/newsflashes",
    ],
    "business": [
        "https://rsshub.app/cls/telegraph",
    ],
    "general": [
        "https://rsshub.app/bbc/zhongwen/simp",
    ],
}

# 备用方案：使用新闻 API
NEWS_API_URL = "https://newsapi.org/v2/top-headlines"


def _fetch_rss(url: str, timeout: int = 10) -> list[dict[str, str]]:
    """解析 RSS/Atom feed，返回文章列表。"""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 Python-Assistant/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            xml_data = resp.read().decode("utf-8", errors="replace")

        root = ET.fromstring(xml_data)
        items = []

        # RSS 2.0 格式
        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            description = item.findtext("description", "")
            link = item.findtext("link", "")
            if title:
                items.append({
                    "title": unescape(title),
                    "description": unescape(description or "").strip(),
                    "link": link or "",
                })

        # Atom 格式
        if not items:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//atom:entry", ns):
                title_elem = entry.find("atom:title", ns)
                summary_elem = entry.find("atom:summary", ns)
                link_elem = entry.find("atom:link[@rel='alternate']", ns)
                title = title_elem.text if title_elem is not None else ""
                summary = summary_elem.text if summary_elem is not None else ""
                link = link_elem.get("href", "") if link_elem is not None else ""
                if title:
                    items.append({
                        "title": unescape(title),
                        "description": unescape(summary or "").strip(),
                        "link": link,
                    })

        return items[:10]  # 最多返回 10 条

    except Exception:
        return []


def get_news(category: str = "tech") -> str:
    """获取指定类别的新闻摘要。"""
    feeds = RSS_FEEDS.get(category, RSS_FEEDS["tech"])

    all_news = []
    for feed_url in feeds:
        items = _fetch_rss(feed_url)
        all_news.extend(items)
        if len(all_news) >= 10:
            break

    if not all_news:
        # 如果 RSS 都失败，返回提示信息
        category_names = {
            "tech": "技术",
            "business": "财经",
            "entertainment": "娱乐",
            "general": "综合",
        }
        cat_name = category_names.get(category, category)
        return (
            f"今日{cat_name}新闻获取失败。\n"
            "建议：\n"
            "1. 检查网络连接\n"
            "2. 尝试其他类别\n"
            "3. 使用 websearch 技能搜索新闻"
        )

    # 格式化输出
    category_names = {
        "tech": "技术",
        "business": "财经",
        "entertainment": "娱乐",
        "general": "综合",
    }
    cat_name = category_names.get(category, category)

    lines = [f"今日{cat_name}新闻（共 {len(all_news)} 条）:", ""]
    for i, item in enumerate(all_news[:10], 1):
        lines.append(f"[{i}] {item['title']}")
        if item["description"]:
            # 截断过长的描述
            desc = item["description"][:150] + "..." if len(item["description"]) > 150 else item["description"]
            lines.append(f"    摘要: {desc}")
        if item["link"]:
            lines.append(f"    链接: {item['link']}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    category = sys.argv[1] if len(sys.argv) > 1 else "tech"
    print(get_news(category))
    return 0


if __name__ == "__main__":
    sys.exit(main())
