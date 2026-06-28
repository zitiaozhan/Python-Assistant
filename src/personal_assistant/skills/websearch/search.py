#!/usr/bin/env python3
"""网络搜索脚本——多引擎聚合，优先使用中国网络可达的搜索服务。

支持的搜索引擎：
  - bing  : cn.bing.com  —— 技术/英文内容首选，速度快
  - sogou : www.sogou.com —— 中文新闻/资讯首选，内容更全
  - auto  : 先 bing，自动用 sogou 补足（默认）

用法::

    python search.py "搜索关键词"
    python search.py "马斯克 最新新闻" --num 8 --engine sogou
    python search.py "特斯拉财报" --num 5 --engine auto --type news
    python search.py "python asyncio" --num 10 --time w

参数::

    --num N      最多返回条数（1-30，默认10）
    --engine     bing / sogou / auto（默认 auto）
    --type       web / news（默认 web）
    --time       d=一天内  w=一周内  m=一月内  y=一年内

输出格式::

    搜索: 关键词
    来源: Bing + Sogou
    共找到 N 条结果:

    [1] 标题
        链接: https://...
        摘要: ...
"""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import NamedTuple

# Windows 终端兼容：强制 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# --------------------------------------------------------------------------- #
# 公共 HTTP 工具
# --------------------------------------------------------------------------- #

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "identity",
}


class SearchResult(NamedTuple):
    title: str
    href: str
    body: str


def _get(url: str, extra_headers: dict[str, str] | None = None, timeout: int = 12) -> str:
    """HTTP GET，返回 UTF-8 解码文本。"""
    headers = dict(_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        return r.read().decode(charset, errors="replace")


def _strip(html: str) -> str:
    """去除 HTML 标签，解码常见 entity，合并空白。"""
    text = re.sub(r"<[^>]+>", " ", html)
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&nbsp;", " ")
        .replace("&#160;", " ")
    )
    text = re.sub(r"&#?\w+;", "", text)
    return " ".join(text.split())


# --------------------------------------------------------------------------- #
# Bing 搜索  (cn.bing.com)
# --------------------------------------------------------------------------- #

def _bing_url(query: str, num: int, search_type: str, time_limit: str) -> str:
    q = urllib.parse.quote(query)
    if search_type == "news":
        url = f"https://cn.bing.com/news/search?q={q}&count={num}&setlang=zh-Hans"
    else:
        url = f"https://cn.bing.com/search?q={q}&count={num}&setlang=zh-Hans"
    if time_limit:
        # Bing 时间过滤：ex1=ez1（一天）~ez4（一年）
        tmap = {"d": "ez1", "w": "ez2", "m": "ez3", "y": "ez4"}
        if time_limit in tmap:
            url += f"&filters=ex1%3A%22{tmap[time_limit]}%22"
    return url


def search_bing(query: str, num: int = 10, search_type: str = "web", time_limit: str = "") -> list[SearchResult]:
    """从 Bing 获取搜索结果。"""
    url = _bing_url(query, num * 2, search_type, time_limit)
    html = _get(url)
    results: list[SearchResult] = []

    if search_type == "news":
        # Bing News 结果卡片
        blocks = re.findall(
            r'<div[^>]+class="[^"]*news-card[^"]*"[^>]*>(.*?)</div>\s*</div>',
            html, re.DOTALL
        )
    else:
        # 普通搜索：从 ol#b_results 中提取 h2/h3 标题行
        results_area_m = re.search(r'<ol[^>]+id="b_results"[^>]*>(.*?)</ol>', html, re.DOTALL)
        if results_area_m:
            html = results_area_m.group(1)
        # 把 <h2...>...<a href="https://...">...</a>...</h2> 逐个提取
        blocks = re.split(r'(?=<h2[^>]*>\s*<a\s)', html)

    for block in blocks:
        if len(results) >= num:
            break

        # 找标题 + 链接
        link_m = re.search(
            r'<a[^>]+href="(https?://(?!r\.bing\.com)[^"]+)"[^>]*>(.*?)</a>',
            block, re.DOTALL
        )
        if not link_m:
            continue
        href = link_m.group(1).strip()
        title = _strip(link_m.group(2))
        if not title or len(title) < 3:
            continue

        # 过滤 Bing 内部链接
        if "bing.com" in href:
            continue

        # 找摘要（多种 class）
        snip_m = re.search(
            r'<p[^>]*class="b_lineclamp[^"]*"[^>]*>(.*?)</p>'
            r'|<div[^>]*class="b_caption[^"]*".*?<p[^>]*>(.*?)</p>'
            r'|<p[^>]*class="b_algoSlug[^"]*"[^>]*>(.*?)</p>'
            r'|<p[^>]*>(.*?)</p>',
            block, re.DOTALL
        )
        body = ""
        if snip_m:
            raw = next((g for g in snip_m.groups() if g), "")
            body = _strip(raw)[:300]

        results.append(SearchResult(title=title, href=href, body=body))

    return results


# --------------------------------------------------------------------------- #
# Sogou 搜索  (www.sogou.com)
# --------------------------------------------------------------------------- #

def _sogou_resolve(link_path: str, timeout: int = 5) -> str:
    """把 Sogou 的 /link?url=xxx 解析成真实 URL（用 JS redirect 提取）。"""
    url = "https://www.sogou.com" + link_path
    try:
        html = _get(url, extra_headers={"Referer": "https://www.sogou.com/"}, timeout=timeout)
        m = re.search(r'window\.location\.replace\("(https?://[^"]+)"\)', html)
        if m:
            return m.group(1)
        # noscript 备用
        m2 = re.search(r"URL='(https?://[^']+)'", html)
        if m2:
            return m2.group(1)
    except Exception:  # noqa: BLE001
        pass
    return url  # 回退到 sogou 重定向 URL


def _sogou_snippets(html: str) -> dict[str, str]:
    """提取 {sogou_link_path: snippet} 映射。"""
    snippets: dict[str, str] = {}
    # vrwrap 块
    depth_pos = 0
    for m in re.finditer(r'<div[^>]+class="vrwrap"', html):
        start = m.start()
        depth = 0
        i = start
        while i < len(html):
            if html[i:i+4] == "<div":
                depth += 1
                i += 4
            elif html[i:i+6] == "</div>":
                depth -= 1
                if depth == 0:
                    block = html[start:i+6]
                    # 找本块中的 /link 路径
                    link_m = re.search(r'href="(/link\?[^"]+)"', block)
                    # 找摘要（sogou 用 <p class="...">, data-lg-tj, etc.）
                    snip_m = re.search(
                        r'<p[^>]*class="[^"]*fz-14[^"]*"[^>]*>(.*?)</p>'
                        r'|<div[^>]*class="[^"]*str_info[^"]*"[^>]*>(.*?)</div>'
                        r'|<p[^>]*class="[^"]*[^"]*"[^>]*data-[^>]*>(.*?)</p>',
                        block, re.DOTALL
                    )
                    if link_m:
                        path = link_m.group(1)
                        snippet = ""
                        if snip_m:
                            raw = next((g for g in snip_m.groups() if g), "")
                            snippet = _strip(raw)[:300]
                        snippets[path] = snippet
                    break
                i += 6
            else:
                i += 1
    return snippets


def search_sogou(query: str, num: int = 10, search_type: str = "web", time_limit: str = "") -> list[SearchResult]:
    """从 Sogou 获取搜索结果。"""
    q = urllib.parse.quote(query)
    if search_type == "news":
        url = f"https://news.sogou.com/news?query={q}&num={num * 2}"
    else:
        url = f"https://www.sogou.com/web?query={q}&num={num * 2}"
    if time_limit:
        tmap = {"d": "1", "w": "7", "m": "31", "y": "365"}
        if time_limit in tmap:
            url += f"&tsn={tmap[time_limit]}"

    html = _get(url, extra_headers={"Referer": "https://www.sogou.com/"})

    # 提取标题 + /link/ 路径：精确匹配 h3.vr-title 内的 <a>
    h3_links = re.findall(
        r'<h3[^>]*class="[^"]*vr-title[^"]*"[^>]*>.*?'
        r'href="(/link\?url=[A-Za-z0-9\-_=]+)"[^>]*>(.*?)</a>',
        html, re.DOTALL
    )

    if not h3_links:
        # 宽匹配备用：直接找 h3 内的 /link
        h3_links = re.findall(
            r'<h3[^>]*>.*?href="(/link\?url=[A-Za-z0-9\-_=]+)"[^>]*>(.*?)</a>',
            html, re.DOTALL
        )

    # 摘要映射
    snippets = _sogou_snippets(html)

    results: list[SearchResult] = []
    seen_paths: set[str] = set()

    # 并发解析真实 URL（最多 num 个，使用线程池）
    unique_pairs = []
    for path, title_html in h3_links:
        if path not in seen_paths:
            seen_paths.add(path)
            unique_pairs.append((path, _strip(title_html)))
        if len(unique_pairs) >= num:
            break

    def resolve_one(item: tuple[str, str]) -> SearchResult | None:
        path, title = item
        if not title or len(title) < 3:
            return None
        real_url = _sogou_resolve(path, timeout=6)
        body = snippets.get(path, "")
        return SearchResult(title=title, href=real_url, body=body)

    max_workers = min(6, len(unique_pairs))
    if max_workers > 0:
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="sogou") as ex:
            futures = {ex.submit(resolve_one, p): p for p in unique_pairs}
            for future in as_completed(futures, timeout=15):
                try:
                    r = future.result()
                    if r:
                        results.append(r)
                except Exception:  # noqa: BLE001
                    pass
            # 保持原始顺序
            ordered = []
            seen_hrefs: set[str] = set()
            for path, _ in unique_pairs:
                for r in results:
                    key = r.href
                    if key not in seen_hrefs and (r.href.endswith(path) or True):
                        seen_hrefs.add(key)
                        ordered.append(r)
                        break
            results = ordered[:num]

    return results[:num]


# --------------------------------------------------------------------------- #
# 统一入口
# --------------------------------------------------------------------------- #

_ENGINE_MAP = {
    "bing":  ("Bing",  search_bing),
    "sogou": ("Sogou", search_sogou),
}

# 汉字字典类垃圾结果特征（Bing China 审查替代内容）
_JUNK_URL = re.compile(
    r"(汉语字典|部首|笔顺|拼音|汉语国学|新华字典|汉典|chagushici|zdic\.net|hgcha\.com|"
    r"hanyuguoxue|gushici\.net|"
    # 单字百科词条：item/单字编码/4~7位数字
    r"baike\.baidu\.com/item/%[0-9A-Fa-f]{2}%[0-9A-Fa-f]{2}%[0-9A-Fa-f]{2}/\d{4,7}$"
    r"|baike\.baidu\.com/item/[^/]{1,4}/\d{4,7}$"
    # 汉语查类
    r"|hgcha\.com/zidian|chagushici\.com/zidian|gushici\.net"
    r"|zdic\.net/hans)"
)
_JUNK_TITLE = re.compile(
    r"(字的意思|字典网|汉语字|汉语国学|新华字典|部首|笔顺|拼音是[a-z]|汉字|字形演变|"
    r"文言文中有什么意思|怎么读_.*的拼音|的意思.*的解释.*的拼音|"
    # 马匹/牲畜相关（Bing 审查替代内容）
    r"图鉴.*马|马.*图鉴|马.*配种|配种.*马|汗血宝马|马驹|公马|母马|"
    r"奇蹄目|马科马属|马属草食性)"
)
# 看起来是域名的标题（Bing 会把 site name 作为 h2）
_LOOKS_LIKE_DOMAIN = re.compile(r"^[a-zA-Z0-9一-鿿.-]{2,30}\.(com|cn|net|org|io)\s")


def _is_junk(r: SearchResult) -> bool:
    """判断是否为审查替代内容（字典词条、域名标题等）。"""
    if _JUNK_URL.search(r.href):
        return True
    if _JUNK_TITLE.search(r.title):
        return True
    # 摘要也检查（有时标题无法判断）
    if r.body and _JUNK_TITLE.search(r.body):
        return True
    # 标题像 "baidu.com https://..." 或 "sina.com.cn ›" 形式
    if _LOOKS_LIKE_DOMAIN.match(r.title):
        return True
    # 标题太短（< 4 字符）
    if len(r.title.strip()) < 4:
        return True
    return False


def _has_chinese(text: str) -> bool:
    """判断文本是否包含中文字符。"""
    return bool(re.search(r'[一-鿿]', text))


def search(
    query: str,
    num: int = 10,
    engine: str = "auto",
    search_type: str = "web",
    time_limit: str = "",
) -> str:
    """执行搜索，返回格式化文本。

    Args:
        query:       搜索关键词。
        num:         最大结果数（默认 10）。
        engine:      bing / sogou / auto（默认 auto）。
                     auto 模式：中文查询优先 sogou，英文查询优先 bing；
                     若主引擎结果不足或有审查替代内容，自动切换补充。
        search_type: web（普通）/ news（新闻）。
        time_limit:  d=一天, w=一周, m=一月, y=一年，空=不限。
    """
    if not query.strip():
        return "错误：搜索关键词为空"

    results: list[SearchResult] = []
    sources_used: list[str] = []

    if engine == "auto":
        # 中文查询：Sogou 主引擎更可靠；英文查询：Bing 速度更快
        engines_to_try = ["sogou", "bing"] if _has_chinese(query) else ["bing", "sogou"]
    elif engine in _ENGINE_MAP:
        engines_to_try = [engine]
    else:
        engines_to_try = ["bing"]

    for eng_key in engines_to_try:
        if len(results) >= num:
            break
        eng_name, fn = _ENGINE_MAP[eng_key]
        need = num - len(results)
        try:
            found = fn(query, num=need + 3, search_type=search_type, time_limit=time_limit)
        except Exception as exc:  # noqa: BLE001
            sources_used.append(f"{eng_name}(失败:{type(exc).__name__})")
            continue

        # 过滤审查替代内容
        found = [r for r in found if not _is_junk(r)]

        existing = {r.href for r in results}
        added = 0
        for r in found:
            if r.href not in existing and r.title:
                results.append(r)
                existing.add(r.href)
                added += 1
        if added:
            sources_used.append(eng_name)

    results = results[:num]
    source_label = " + ".join(sources_used) if sources_used else "未知"

    if not results:
        return (
            f"搜索: {query}\n来源: {source_label}\n"
            "未找到搜索结果。请尝试：\n"
            "  - 简化关键词\n"
            "  - 使用 --engine sogou（中文内容更全）\n"
            "  - 使用 --engine bing（技术/英文内容）"
        )

    lines = [
        f"搜索: {query}",
        f"来源: {source_label}",
        f"共找到 {len(results)} 条结果:",
        "",
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.title}")
        lines.append(f"    链接: {r.href}")
        if r.body:
            lines.append(f"    摘要: {r.body}")
        lines.append("")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(
            "用法: python search.py <关键词> [选项]\n"
            "选项:\n"
            "  --num N         最多返回条数（默认10，最大30）\n"
            "  --engine NAME   bing / sogou / auto（默认auto）\n"
            "  --type TYPE     web / news（默认web）\n"
            "  --time LIMIT    d=一天 w=一周 m=一月 y=一年\n"
            "\n示例:\n"
            "  python search.py \"马斯克 最新消息\" --engine sogou\n"
            "  python search.py \"特斯拉\" --type news --time w\n"
            "  python search.py \"python asyncio\" --num 15"
        )
        return 0 if args else 1

    num = 10
    engine = "auto"
    search_type = "web"
    time_limit = ""
    query_parts: list[str] = []

    i = 0
    while i < len(args):
        if args[i] == "--num" and i + 1 < len(args):
            try:
                num = max(1, min(30, int(args[i + 1])))
            except ValueError:
                pass
            i += 2
        elif args[i] == "--engine" and i + 1 < len(args):
            engine = args[i + 1].lower()
            i += 2
        elif args[i] == "--type" and i + 1 < len(args):
            search_type = args[i + 1].lower()
            i += 2
        elif args[i] == "--time" and i + 1 < len(args):
            time_limit = args[i + 1].lower()
            i += 2
        else:
            query_parts.append(args[i])
            i += 1

    query = " ".join(query_parts)
    if not query:
        print("错误：请提供搜索关键词")
        return 1

    print(search(query, num=num, engine=engine, search_type=search_type, time_limit=time_limit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
