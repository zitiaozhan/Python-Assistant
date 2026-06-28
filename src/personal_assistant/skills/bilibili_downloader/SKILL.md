# Bilibili Downloader（B站视频下载器）

> 使用 yt-dlp 下载 Bilibili 视频，支持选择清晰度、下载弹幕、指定输出目录。

## 使用场景

- 用户想下载 B 站视频到本地
- 用户需要指定清晰度下载
- 用户需要同时下载弹幕
- 用户想查看视频有哪些可用清晰度

## 使用步骤

1. 用 bash 工具执行下载脚本，传入视频链接和选项：

```bash
python "<技能文件夹>/bilibili_downloader.py" "视频链接" [选项]
```

注意：`<技能文件夹>` 的实际路径为 `D:\Code\AI\Python-Assistant\src\personal_assistant\skills\bilibili_downloader`

2. 脚本调用 yt-dlp 执行下载，输出进度信息。
3. 下载完成后告知用户文件保存位置。

## 支持选项

| 选项 | 说明 |
|------|------|
| `--quality Q` | 清晰度：360p, 480p, 720p, 1080p, 4k, best（默认 best） |
| `--output-dir DIR` | 保存目录，默认 `./downloads` |
| `--danmaku` | 同时下载弹幕（SRT 字幕格式） |
| `--list-formats` / `-F` | 仅列出可用格式，不下载 |
| `--cookies FILE` | Cookie 文件路径（用于下载高清/大会员视频） |
| `--cookies-from-browser BROWSER` | 从浏览器提取 Cookie（chrome/firefox/edge） |
| `--referer URL` | Referer 请求头，默认 `https://www.bilibili.com/`（避免 HTTP 412 错误） |

## 示例

```bash
# 下载单个视频（默认最佳画质）
python "D:/Code/AI/Python-Assistant/src/personal_assistant/skills/bilibili_downloader/bilibili_downloader.py" "https://www.bilibili.com/video/BV1xx411c7mD"

# 查看可用的清晰度
python "D:/Code/AI/Python-Assistant/src/personal_assistant/skills/bilibili_downloader/bilibili_downloader.py" "https://www.bilibili.com/video/BV1xx411c7mD" --list-formats

# 下载 1080p + 弹幕，保存到桌面
python "D:/Code/AI/Python-Assistant/src/personal_assistant/skills/bilibili_downloader/bilibili_downloader.py" "https://www.bilibili.com/video/BV1xx411c7mD" --quality 1080p --danmaku --output-dir ~/Desktop/bilibili_videos

# 使用浏览器 Cookie 下载大会员视频
python "D:/Code/AI/Python-Assistant/src/personal_assistant/skills/bilibili_downloader/bilibili_downloader.py" "https://www.bilibili.com/video/BV1xx411c7mD" --cookies-from-browser chrome
```

## 常见问题

### HTTP Error 412: Precondition Failed

**原因**：B站现已强制要求登录 Cookie，未携带 Cookie 的请求会被拒绝。

**解决方案（二选一）**：

#### 方法 1：从浏览器提取 Cookie（推荐，最简单）

确保你的浏览器（Chrome/Firefox/Edge）已登录 B 站账号，然后：

```bash
# 从 Chrome 提取
python ".../bilibili_downloader.py" "视频链接" --cookies-from-browser chrome

# 从 Firefox 提取
python ".../bilibili_downloader.py" "视频链接" --cookies-from-browser firefox

# 从 Edge 提取
python ".../bilibili_downloader.py" "视频链接" --cookies-from-browser edge
```

支持的浏览器：chrome, firefox, edge, opera, brave, vivaldi, safari

#### 方法 2：导出 Cookie 文件

1. 在浏览器中安装扩展：**Get cookies.txt LOCALLY**
2. 打开 B 站并登录
3. 点击扩展图标，导出 `cookies.txt` 文件
4. 使用 Cookie 文件下载：

```bash
python ".../bilibili_downloader.py" "视频链接" --cookies cookies.txt
```

## 前置依赖

- **yt-dlp**：`pip install yt-dlp`（已安装）

## 注意事项

- 下载的视频仅供个人学习研究使用，请遵守版权规定
- 高清视频（1080p 以上）可能需要 B 站登录 Cookie
- 弹幕以字幕格式 (.srt) 保存，可用视频播放器加载
- 默认跳过播放列表，只下载单个视频
- 如果下载失败，可尝试先查看可用格式再指定清晰度
