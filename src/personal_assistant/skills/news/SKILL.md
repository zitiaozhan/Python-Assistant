# News Digest（新闻摘要）

> 获取今日热点新闻摘要，支持按类别（技术/财经/娱乐/综合）筛选，帮助用户快速了解当日大事。

## 使用场景

- 用户询问"今天有什么新闻"
- 用户想了解特定领域的最新动态
- 早晨快速获取当日新闻摘要

## 使用步骤

1. 用 bash 工具执行新闻查询脚本：

```bash
python "<技能文件夹>/news.py" [类别]
```

类别选项：
- `tech` - 技术新闻（默认）
- `business` - 财经新闻
- `entertainment` - 娱乐新闻
- `general` - 综合新闻

注意：`<技能文件夹>` 的实际路径已在技能内容开头的 `[技能文件夹: ...]` 中给出，请替换为实际路径。

2. 脚本返回今日热点新闻列表（标题 + 摘要 + 链接）。
3. 为用户总结关键新闻要点。

## 示例

```bash
# 获取技术新闻（默认）
python "/path/to/skills/news/news.py"

# 获取财经新闻
python "/path/to/skills/news/news.py" business

# 获取综合新闻
python "/path/to/skills/news/news.py" general
```

## 注意事项

- 使用新闻 RSS 源聚合，无需 API key
- 如果某个新闻源不可用，会自动跳过
- 返回的新闻数量有限（最多 10 条），避免信息过载
