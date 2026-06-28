#!/usr/bin/env python3
"""B站视频下载器——基于 yt-dlp 下载 Bilibili 视频。

用法::

    python bilibili_downloader.py "视频链接" [选项]

选项:
    --quality Q        清晰度: 360p, 480p, 720p, 1080p, 4k, best（默认 best）
    --output-dir DIR   保存目录（默认当前目录下的 downloads）
    --danmaku          同时下载弹幕（SRT 字幕格式）
    --list-formats     仅列出可用格式，不下载
    --cookies FILE     Cookie 文件路径（用于下载高清/大会员视频）
    --cookies-from-browser BROWSER  从浏览器提取 Cookie（如 chrome, firefox, edge）
    --referer URL      Referer 请求头（默认 https://www.bilibili.com/）
"""

from __future__ import annotations

import subprocess
import sys
import os
import json
import shutil

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


QUALITY_MAP = {
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "4k": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "best": "bestvideo+bestaudio/best",
}


def find_ytdlp() -> str | None:
    """查找 yt-dlp 可执行文件路径。"""
    ytdlp_path = shutil.which("yt-dlp")
    if ytdlp_path:
        return ytdlp_path
    # 尝试通过 python -m 方式
    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return "module"
    except Exception:
        pass
    return None


def parse_args(args: list[str]) -> dict:
    """解析命令行参数。"""
    parsed = {
        "url": "",
        "quality": "best",
        "output_dir": os.path.join(os.getcwd(), "downloads"),
        "danmaku": False,
        "list_formats": False,
        "cookies": None,
        "cookies_from_browser": None,
        "referer": "https://www.bilibili.com/",
    }
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        elif arg == "--quality" and i + 1 < len(args):
            i += 1
            parsed["quality"] = args[i]
        elif arg == "--output-dir" and i + 1 < len(args):
            i += 1
            parsed["output_dir"] = args[i]
        elif arg == "--danmaku":
            parsed["danmaku"] = True
        elif arg == "--list-formats" or arg == "-F":
            parsed["list_formats"] = True
        elif arg == "--cookies" and i + 1 < len(args):
            i += 1
            parsed["cookies"] = args[i]
        elif arg == "--cookies-from-browser" and i + 1 < len(args):
            i += 1
            parsed["cookies_from_browser"] = args[i]
        elif arg == "--referer" and i + 1 < len(args):
            i += 1
            parsed["referer"] = args[i]
        elif not arg.startswith("--") and not parsed["url"]:
            parsed["url"] = arg
        i += 1
    return parsed


def build_command(parsed: dict) -> list[str]:
    """构建 yt-dlp 命令。"""
    ytdlp = find_ytdlp()
    if ytdlp is None:
        print("❌ 错误: 未找到 yt-dlp，请先安装: pip install yt-dlp")
        sys.exit(1)

    if ytdlp == "module":
        cmd = [sys.executable, "-m", "yt_dlp"]
    else:
        cmd = [ytdlp]

    # URL（放在最后）
    url = parsed["url"]

    # 输出模板
    output_template = os.path.join(parsed["output_dir"], "%(title)s.%(ext)s")
    cmd.extend(["-o", output_template])

    # 格式
    fmt = QUALITY_MAP.get(parsed["quality"], QUALITY_MAP["best"])
    cmd.extend(["-f", fmt])

    # 下载弹幕
    if parsed["danmaku"]:
        cmd.extend(["--write-subs", "--sub-langs", "danmaku", "--convert-subs", "srt"])

    # 仅列出格式
    if parsed["list_formats"]:
        cmd.append("-F")

    # Cookies（文件）
    if parsed["cookies"]:
        cmd.extend(["--cookies", parsed["cookies"]])

    # Cookies（从浏览器提取）
    if parsed["cookies_from_browser"]:
        cmd.extend(["--cookies-from-browser", parsed["cookies_from_browser"]])

    # User-Agent（模拟真实浏览器，避免 412 错误）
    cmd.extend([
        "--user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ])

    # Referer 请求头（避免 HTTP 412 错误）
    if parsed["referer"]:
        cmd.extend(["--referer", parsed["referer"]])

    # HTTP Headers（修复 412 错误的关键）
    cmd.extend([
        "--add-header", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "--add-header", "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8",
        "--add-header", "Sec-Fetch-Dest: document",
        "--add-header", "Sec-Fetch-Mode: navigate",
        "--add-header", "Sec-Fetch-Site: none",
        "--add-header", "Sec-Fetch-User: ?1",
        "--add-header", "Upgrade-Insecure-Requests: 1",
    ])

    # 通用选项
    cmd.extend(["--no-playlist", "--progress", "--newline"])

    # URL 放在最后（yt-dlp 要求）
    cmd.append(url)

    return cmd


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1

    parsed = parse_args(args)

    if not parsed["url"]:
        print("❌ 错误: 请提供 B 站视频链接")
        print("用法: python bilibili_downloader.py \"https://www.bilibili.com/video/BVxxxxxx\"")
        return 1

    # 确保输出目录存在
    os.makedirs(parsed["output_dir"], exist_ok=True)

    cmd = build_command(parsed)

    print(f"🔗 视频链接: {parsed['url']}")
    print(f"📂 保存目录: {parsed['output_dir']}")
    print(f"🎬 清晰度: {parsed['quality']}")
    print(f"🔗 Referer: {parsed['referer']}")
    if parsed["danmaku"]:
        print(f"💬 弹幕下载: 是")
    if parsed["cookies"]:
        print(f"🍪 Cookie 文件: {parsed['cookies']}")
    if parsed["cookies_from_browser"]:
        print(f"🍪 Cookie 来源: 浏览器 {parsed['cookies_from_browser']}")
    print(f"{'─' * 50}")

    # 执行 yt-dlp
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        # 输出标准输出和错误
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        if result.returncode == 0:
            if not parsed["list_formats"]:
                print(f"\n✅ 下载完成！文件保存在: {parsed['output_dir']}")
            return 0
        else:
            print(f"\n❌ 下载失败 (退出码: {result.returncode})")
            # 检查是否是 412 错误
            if "412" in result.stderr or "Precondition Failed" in result.stderr:
                print("\n💡 解决方案：B站现在强制要求登录 Cookie，请使用以下方法之一：")
                print("   方法 1: 从浏览器提取 Cookie（推荐）")
                print('     python ".../bilibili_downloader.py" "视频链接" --cookies-from-browser chrome')
                print("   方法 2: 导出 Cookie 文件")
                print('     1. 使用浏览器扩展（如 "Get cookies.txt LOCALLY"）导出 cookies.txt')
                print('     2. python ".../bilibili_downloader.py" "视频链接" --cookies cookies.txt')
                print("\n   支持的浏览器: chrome, firefox, edge, opera, brave, vivaldi, safari")
            return result.returncode
    except FileNotFoundError:
        print("❌ 错误: 未找到 yt-dlp，请先安装: pip install yt-dlp")
        return 1
    except KeyboardInterrupt:
        print("\n⚠️ 用户取消下载")
        return 130


if __name__ == "__main__":
    sys.exit(main())
