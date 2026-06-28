# Web Search

> 使用多引擎聚合搜索（Bing + Sogou）获取实时信息。自动根据查询语言选择最佳引擎：中文查询优先 Sogou，英文/技术查询优先 Bing。支持新闻搜索和时间范围过滤。

## 使用场景

- 用户询问最新新闻或当前事件
- 需要查找训练数据中没有的实时信息（股价、新闻、最新技术等）
- 用户明确要求搜索某个话题
- 需要多角度信息时可多次搜索

## 使用步骤

1. 用 bash 工具执行搜索，传入搜索关键词：

```bash
python3 "<技能文件夹>/search.py" "搜索关键词"
```

注意：`<技能文件夹>` 的实际路径已在技能内容开头的 `[技能文件夹: ...]` 中给出，请替换为实际路径。

2. 脚本返回格式化结果（标题、链接、摘要），最多 10 条（默认）。
3. 阅读搜索结果，为用户总结关键信息。
4. 如结果不够全面，可调整关键词或选项重新搜索。
5. 同一任务的搜索不超过 3 次，超过后直接处理已有信息。

## 完整参数

```bash
python3 "<技能文件夹>/search.py" "<关键词>" [选项]

选项:
  --num N         返回条数（1-30，默认10）
  --engine NAME   搜索引擎：
                    auto  = 自动选择（默认，推荐）
                    bing  = Bing（英文/技术内容更好）
                    sogou = Sogou（中文新闻/资讯更好）
  --type TYPE     搜索类型：web（默认）/ news（新闻）
  --time LIMIT    时间范围：d=一天 w=一周 m=一月 y=一年
```

## 使用示例

```bash
# 默认搜索（自动选引擎）
python3 "/path/to/skills/websearch/search.py" "马斯克 最新消息"

# 明确用 Sogou 搜中文新闻
python3 "/path/to/skills/websearch/search.py" "特斯拉最新财报" --engine sogou

# 搜最近一周的 AI 新闻
python3 "/path/to/skills/websearch/search.py" "AI 大模型进展" --type news --time w

# 英文技术查询，返回15条
python3 "/path/to/skills/websearch/search.py" "python asyncio best practices" --num 15

# 搜今天的热点
python3 "/path/to/skills/websearch/search.py" "今日头条新闻" --type news --time d --engine sogou
```

## 引擎选择指南

| 场景 | 推荐引擎 | 原因 |
|------|----------|------|
| 中文新闻/人物/财经 | `sogou` 或 `auto` | Bing 中文版对某些内容有过滤 |
| 英文技术文档 | `bing` | 英文内容质量更高 |
| 不确定 | `auto`（默认） | 自动判断并切换 |

## 注意事项

- 脚本使用 Python 标准库，无需额外依赖
- 中国网络环境下 DuckDuckGo 不可用，已改用 Bing + Sogou
- 若 `auto` 结果不理想，可显式指定 `--engine sogou` 或 `--engine bing`
- 如果搜索失败，可尝试简化关键词或稍后重试
