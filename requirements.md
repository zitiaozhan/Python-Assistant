# Python-Assistant 依赖清单

> 启动项目前请确保所有依赖已安装。推荐使用 `uv` 管理依赖。

## 快速安装

```bash
# 使用 uv（推荐，自动使用清华镜像源）
uv sync

# 或使用 pip
pip install -r requirements.txt
```

## 运行时依赖

| 包名 | 最低版本 | 用途 |
|------|----------|------|
| openai | >=2.43.0 | LLM API 客户端（兼容 OpenAI 协议） |
| ddgs | >=9.0.0 | DuckDuckGo 搜索引擎（websearch 技能） |
| fastapi | >=0.115.0 | Web 框架（REST API + WebSocket） |
| uvicorn | >=0.32.0 | ASGI 服务器 |
| websockets | >=16.0 | WebSocket 协议支持（uvicorn 依赖） |
| qrcode | >=8.0 | 二维码生成（手机扫码访问） |

## 开发依赖

| 包名 | 最低版本 | 用途 |
|------|----------|------|
| pytest | >=9.1.1 | 单元测试框架 |
| ruff | >=0.15.18 | 代码检查 + 格式化 |

## 传递依赖（自动安装）

以下依赖由上述包自动安装，无需手动指定：

| 包名 | 用途 |
|------|------|
| annotated-doc | FastAPI 文档生成 |
| annotated-types | Pydantic 类型注解 |
| anyio | 异步 I/O 基础库 |
| brotli | 压缩算法（ddgs 依赖） |
| certifi | CA 证书包 |
| click | CLI 框架（uvicorn 依赖） |
| colorama | Windows 终端颜色 |
| distro | 系统信息检测 |
| fake-useragent | 用户代理生成（ddgs 依赖） |
| h11 | HTTP/1.1 协议解析 |
| h2 | HTTP/2 协议支持（ddgs 依赖） |
| hpack | HPACK 压缩（ddgs 依赖） |
| httpcore | HTTP 连接池 |
| httpx | HTTP 客户端 |
| hyperframe | HTTP/2 帧处理（ddgs 依赖） |
| idna | 国际化域名 |
| jiter | JSON 解析加速 |
| lxml | HTML/XML 解析（ddgs 依赖） |
| packaging | 版本解析（pytest 依赖） |
| pluggy | 插件系统（pytest 依赖） |
| primp | HTTP 客户端（ddgs 依赖） |
| pydantic | 数据验证 |
| pydantic-core | Pydantic 核心 |
| pygments | 代码高亮 |
| sniffio | 异步后端检测 |
| socksio | SOCKS 代理支持（ddgs 依赖） |
| starlette | ASGI 框架（FastAPI 基础） |
| tqdm | 进度条 |
| typing-extensions | 类型注解扩展 |
| typing-inspection | 类型检查 |

## 环境要求

- **Python**: >=3.12
- **操作系统**: Windows / macOS / Linux
- **网络**: 需要访问 LLM API（默认 DeepSeek）和 DuckDuckGo
