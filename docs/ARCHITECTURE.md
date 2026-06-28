# Architecture

> Status: **Agent + 工具调用 + 技能系统 + Token 统计 + Web UI + Markdown 渲染（含表格） + 手机扫码访问 + 上下文压缩已可用**。
> Agent 通过与模型解耦的 toolcall 协议自主调用工具（bash）和技能（文件夹式 SKILL.md），并在每轮对话后报告 Token 消耗。Web 层采用广播 WebSocket 架构，PC 与手机共享同一对话会话，消息实时双向同步。支持长期任务运行，上下文过长时自动压缩历史对话。

## Goals

1. **Personal assistant** — understands intents and acts on the user's behalf.
2. **Phone–PC collaboration** — the same assistant spans a phone and a
   computer, sharing context and delegating work to whichever device is
   best suited.
3. **Continuously extensible** — new abilities can be added without
   touching core code, ideally as independently distributable packages.

## Layered overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Entry Points                                 │
│   CLI (cli.py)  │  Web UI (web/)  │  Mobile (/mobile)           │
├─────────────────────────────────────────────────────────────────┤
│                   Web Layer (web.py)                             │
│  FastAPI REST API  │  Broadcast WebSocket  │  Static Files       │
│  /api/*            │  /ws/chat             │  /static/*          │
│  /api/qrcode.svg   │  shared_history       │  /mobile            │
│  /api/server-info  │  event_log (replay)   │                     │
├─────────────────────────────────────────────────────────────────┤
│                     Agent (core/agent.py)                        │
│        intent routing · toolcall loop · token accumulation       │
├──────────────┬──────────────────┬──────────────────────────────┤
│   tools/     │    skills/       │         plugins/ (预留)        │
│  (Tool 类)   │  (文件夹+MD)     │                               │
├──────────────┴──────────────────┴──────────────────────────────┤
│                     LLMClient (llm/client.py)                    │
│           OpenAI-compatible ↔ internal protocol types            │
└─────────────────────────────────────────────────────────────────┘
```

## Core abstractions

### Agent (`core/agent.py`)

The coordinator. Drives the toolcall loop:
- Sends messages + tool specs to the model
- Executes any requested tools
- Feeds results back and loops until the model gives a final text reply
- Includes a `confirm` gate (per tool call), `on_event` hook for UI
- Accumulates `TokenUsage` across all model calls in a single turn
- Resolves `{{variable}}` placeholders in system prompts and appends values
  (preserving the original prompt for prompt cache hits)
- **Context compression**: automatically summarizes old messages when exceeding
  `max_messages` threshold (default 50), preserving system prompt + summary +
  recent messages. Also provides `compress_context` tool for AI-initiated compression.

### Tool (`core/tool.py`)

Base class for all tools. Subclasses declare `name` / `description` /
`parameters` (JSON Schema) and implement `run`. The model calls tools
directly via toolcall. See `tools/README.md`.

Built-in: **bash** — executes shell commands, forces UTF-8 output, expands `~`.

### SkillFolder / SkillManager (`core/skill.py`)

Folder-based skill system:
- Each skill is a subdirectory containing `SKILL.md` (name + description + body)
- The model sees only names + descriptions; upon calling `use_skill`, it receives
  the full `SKILL.md` + all markdown files in the folder
- `SkillManager` auto-scans the `skills/` directory on startup
- Skills can contain arbitrary auxiliary files (scripts, docs)

Built-in: **websearch** — see [Websearch Skill](#websearch-skill) below.

### TokenUsage (`core/protocol.py`)

Token consumption tracking. Supports `+` accumulation across multiple model
calls in one turn. Fields: `prompt_tokens`, `completion_tokens`, `total_tokens`,
`cached_tokens`, `reasoning_tokens`. Compatible with OpenAI standard
(`prompt_tokens_details.cached_tokens`) and DeepSeek extension
(`prompt_cache_hit_tokens`) formats.

### Protocol (`core/protocol.py`)

The model-agnostic contract between Agent and `LLMClient`:
`ToolSpec`, `ToolCall`, `ToolResult`, `Message`, `LLMResponse`, `TokenUsage`.

**This is the decoupling boundary** — Agent never sees the model's wire format.

---

## Web Layer Architecture

### REST API (`web.py`)

| Route | Method | Description |
|-------|--------|-------------|
| `/api/config` | GET/POST | Model configuration (read/write `model.json`) |
| `/api/tools` | GET | List registered tools |
| `/api/skills` | GET/POST | List/create skills |
| `/api/skills/{name}` | GET/PUT/DELETE | Read/update/delete skill |
| `/api/skills/{name}/files` | GET/POST | List/create files in skill folder |
| `/api/skills/{name}/files/{path}` | GET/POST/DELETE | File content CRUD |
| `/api/skills/{name}/upload` | POST | Upload binary file (base64) |
| `/api/blacklist` | GET/POST/DELETE | Bash blacklist rule management |
| `/api/server-info` | GET | Local IP, port, and mobile URL |
| `/api/qrcode.svg` | GET | QR code SVG for mobile access |
| `/ws/chat` | WebSocket | Real-time chat (broadcast to all clients) |
| `/` | GET | Main Web UI (`web/index.html`) |
| `/mobile` | GET | Mobile-optimized page (`web/mobile.html`) |
| `/static/*` | GET | Static assets (`web/css/`, `web/js/`, etc.) |

### Broadcast WebSocket Architecture

**Problem**: A personal assistant should be accessible from multiple devices
simultaneously, with all messages visible on every connected client.

**Solution**: All WebSocket connections share a single conversation session.

```
                  ┌─────────────────────────────────┐
                  │         web.py globals            │
                  │                                   │
                  │  _active_connections: set[WS]     │
                  │  _shared_history: list[Message]   │
                  │  _event_log: list[dict]            │
                  │  _chat_lock: asyncio.Lock         │
                  └────────────┬────────────────────┘
                               │
          ┌────────────────────┼─────────────────────┐
          │                    │                       │
    PC Browser            Mobile Browser        (future clients)
    ws://host/ws/chat     ws://host/ws/chat
```

**Key globals**:

| Variable | Type | Purpose |
|----------|------|---------|
| `_active_connections` | `set[WebSocket]` | All currently connected clients |
| `_shared_history` | `list[Message]` | Shared conversation (in-place modified by Agent) |
| `_event_log` | `list[dict]` | Event replay log for new clients |
| `_chat_lock` | `asyncio.Lock` | Serializes Agent calls (one at a time) |
| `_pending_confirms` | `dict[str, Future[bool]]` | Awaiting dangerous-command confirmations |

**`_broadcast(msg, log=False)`**: sends `msg` to all `_active_connections`,
removes dead connections, and optionally appends to `_event_log`.

### WebSocket Event Protocol

All events use JSON with a `type` field:

```
Client → Server:
  {"type": "chat",    "content": "..."}       # send user message
  {"type": "clear"}                            # clear conversation
  {"type": "confirm", "id": "...", "approved": true/false}  # confirm dangerous cmd

Server → Client(s) [broadcast]:
  {"type": "user_message",    "content": "..."}   # user message (for replay & cross-device)
  {"type": "start"}                                # AI started generating
  {"type": "chunk",           "content": "..."}   # streaming text chunk
  {"type": "tool_call",       "data": {...}}       # tool invoked
  {"type": "done",            "usage": {...}}      # generation complete + token stats
  {"type": "error",           "message": "..."}   # error occurred
  {"type": "cleared"}                              # conversation was cleared
  {"type": "assistant_message","content": "..."}  # complete AI reply (replay only)
  {"type": "confirm_request", "id": "...", "command": "..."}  # dangerous command prompt
```

**History replay**: When a new client connects, the server immediately sends
all events from `_event_log` so the client sees the full conversation history.
Only `user_message`, `assistant_message`, and `tool_call` events are logged
(not `chunk` or `start`).

### Chat Flow

```
Client sends {"type": "chat", "content": "..."}
         │
         ▼
chat_ws receives → acquires _chat_lock → calls _handle_chat()
         │
         ▼ _handle_chat():
  1. Append Message.user(...) to _shared_history
  2. Log {"type": "user_message"} to _event_log
  3. broadcast {"type": "user_message"}     → all clients show user message
  4. broadcast {"type": "start"}            → all clients show typing indicator
  5. Run agent in thread pool:
       agent.run(_shared_history, on_chunk=...) [modifies list in-place]
       on_chunk → broadcast {"type": "chunk"}    (per character/token)
       on_event → broadcast {"type": "tool_call"} + log to _event_log
  6. Log {"type": "assistant_message"} to _event_log
  7. broadcast {"type": "done", "usage": ...}
```

### Frontend Module Structure

The Web UI is split into small, focused files served via `/static/`:

```
web/
├── index.html          # HTML skeleton only (~300 lines), no inline JS/CSS
├── mobile.html         # Self-contained mobile page (embedded CSS+JS)
├── css/
│   ├── variables.css   # CSS custom properties (colors, shadows, animations)
│   ├── layout.css      # Sidebar, main area, page routing, responsive
│   ├── chat.css        # Chat bubbles, Markdown styles, streaming cursor
│   ├── components.css  # Buttons, cards, forms, modals, toasts, QR dialog
│   └── editor.css      # Skill editor: file tree, tabs, split view, fullscreen
└── js/
    ├── utils.js        # $(), escapeHtml(), showToast(), renderMarkdown()
    ├── api.js          # apiGet/Post/Put/Delete wrappers
    ├── chat.js         # WebSocket handling, message rendering, broadcast-aware
    ├── config.js       # Model config page
    ├── tools.js        # Tools list page
    ├── skills.js       # Skills list + workspace + file editor (sync scroll, fullscreen)
    ├── blacklist.js    # Blacklist management page
    └── main.js         # Page routing, QR code modal, app init
```

Scripts are loaded in dependency order (no bundler). All shared state is in
module-level globals; no ES module `import/export`.

### Markdown Rendering (`utils.js → renderMarkdown()`)

Two-phase approach to handle streaming safely:

1. **During stream** (`type: chunk`): accumulate raw text in `dataset.raw`,
   display as plain text with a blinking cursor.
2. **On completion** (`type: done`): call `renderMarkdown(raw)` and replace
   content with rendered HTML.

The renderer is stateful (line-by-line), preserving code blocks via placeholder
substitution before HTML escaping to prevent corruption:

```
Input text
  → Extract code blocks/inline code → replace with \x00CODE0\x00 placeholders
  → Extract tables → replace with \x00TABLE0\x00 placeholders
  → HTML-escape remaining text
  → Process line-by-line: headings, blockquotes, lists, paragraphs
  → Restore code blocks with <pre><code>
  → Restore tables with <table> (supports alignment, hover highlight)
  → Attach copy buttons to <pre> elements
```

**Table support** (`parseTable()`):
- Parses standard Markdown tables with header, separator, and data rows
- Supports alignment (`:---` left, `:---:` center, `---:` right)
- Cells support inline Markdown (bold, italic, strikethrough, links)
- Renders with responsive wrapper for horizontal scrolling
- Styled for both desktop (chat.css) and mobile (mobile.html)

---

## Decoupling: Agent ↔ model

```
Agent (core/agent.py)
   │  operates only on protocol types (Message / ToolSpec / ToolCall / TokenUsage ...)
   ▼
LLMClient (llm/client.py)        ←── translates to/from the model's wire format
   │  (OpenAI-compatible: tools=[], tool_calls=[], role="tool" ...)
   │  also extracts token usage from API response
   ▼
DeepSeek / OpenAI / any compatible provider
```

Switching providers: change `config/model.json` (`base_url`/`model`) and,
only if the wire protocol differs, adjust the translators in `LLMClient`.
Agent and tools stay untouched.

---

## Websearch Skill

The built-in **websearch** skill (`skills/websearch/search.py`) uses direct
HTTP scraping with Python's standard library — no external dependencies.

### Engine strategy

| Query type | Primary engine | Fallback |
|------------|---------------|---------|
| Chinese characters detected | Sogou (www.sogou.com) | Bing |
| English / technical | Bing (cn.bing.com) | Sogou |
| `--engine bing` | Bing | — |
| `--engine sogou` | Sogou | — |

**Rationale**: cn.bing.com applies content filtering for some Chinese topics
(returning character-dictionary entries instead of relevant results). Sogou
lacks this filter for Chinese content. The auto mode detects the query language
and routes accordingly. A junk-content filter (`_is_junk()`) removes dictionary
filler results that slip through.

### Sogou URL resolution

Sogou wraps result URLs in `/link?url=…` redirects. The script resolves each
to the real URL by fetching the redirect page and extracting the `window.location.replace(url)`
JavaScript call, using a thread pool for concurrent resolution.

### Parameters

```
python3 search.py <query> [--num N] [--engine auto|bing|sogou] [--type web|news] [--time d|w|m|y]
```

---

## How to extend

### Tools (原子操作)

1. Subclass `Tool`, fill in `name` / `description` / `parameters`, implement `run`.
2. Register it in `tools/__init__.default_tools()`.
3. The model will discover and call it automatically via toolcall.

See [`src/personal_assistant/tools/README.md`](../src/personal_assistant/tools/README.md).

### Skills (领域知识 + 多步骤指引)

1. Create a subdirectory under `skills/`.
2. Write `SKILL.md` (name + description + body).
3. Optionally add auxiliary files (scripts, more markdown docs).

`SkillManager` auto-discovers it on startup — no code changes needed.

See [`src/personal_assistant/skills/README.md`](../src/personal_assistant/skills/README.md).

### Tool vs Skill

| Aspect | Tool | Skill |
|--------|------|-------|
| Form | Python class | Folder + `SKILL.md` |
| Model invocation | Direct toolcall | Via `use_skill` indirect call |
| Returned to model | `run()` result | `SKILL.md` full text + all `.md` files |
| Best for | Atomic operations | Domain knowledge + multi-step guidance |
| Adding new | Write class + register | Create folder + write `SKILL.md` |

---

## Phone–PC collaboration (实现状态)

**已实现**（通过广播 WebSocket）：
- PC 和手机共享同一 Agent 对话历史
- 任意设备发消息，所有设备实时收到响应
- 新设备连接时接收历史消息回放
- QR 码生成（`/api/qrcode.svg`，Python `qrcode` 库，SVG 输出）
- 移动端专属页面（`/mobile`，触控优化，内联 CSS/JS）

**待实现**（`sync/` 子包）：
- 传输层（WebSocket / mDNS / 云中转 — TBD）
- 设备配对与认证
- 共享上下文（剪贴板、通知、活跃任务状态）
- 能力声明优先运行设备（在哪台设备上执行）

---

## Milestones

1. ✅ Project skeleton, build/test tooling (uv + ruff + pytest + hatchling).
2. ✅ CLI chat REPL with streaming output + configurable model (DeepSeek via OpenAI-compatible API).
3. ✅ Agent tool-calling: decoupled protocol + orchestration loop + bash tool.
4. ✅ Skill system: folder-based `SKILL.md` + `use_skill` tool + auto-scan.
5. ✅ Token usage tracking: prompt/completion/total/cached/reasoning, OpenAI & DeepSeek compatible.
6. ✅ Websearch skill: Bing HTML scraping, standard library only.
7. ✅ Bash blacklist confirmation gate.
8. ✅ System prompt variables (`{{variable}}` placeholders, prompt-cache friendly).
9. ✅ Web UI: FastAPI + WebSocket streaming + config/tools/skills/blacklist management.
10. ✅ **Frontend modularization**: CSS/JS split into focused files; `index.html` from 2321 → 301 lines.
11. ✅ **Markdown rendering**: code block protection + streaming cursor + copy buttons.
12. ✅ **UI modernization**: new design tokens, gradient bubbles, animations, QR dialog.
13. ✅ **Broadcast WebSocket architecture**: shared history, event-log replay, `_active_connections`.
14. ✅ **Mobile QR access**: `/api/qrcode.svg`, `/api/server-info`, `/mobile`, touch-optimized page.
15. ✅ **Websearch dual-engine**: Bing + Sogou, auto language detection, junk filter, news/time params.
16. ✅ **Markdown table rendering**: alignment support, hover highlight, responsive wrapper, chat + editor.
17. ✅ **Context compression**: AI-summarized history + auto-trigger + AI-initiated, enables long-running tasks.
18. ⬜ More built-in tools (file I/O, clipboard, system notifications).
19. ⬜ Skill/tool auto-discovery (entry points / directory scanning).
20. ⬜ Cross-device dangerous-command confirmation (mobile can approve/reject).
21. ⬜ Phone–PC transport and pairing (sync/ subpackage).
22. ⬜ Multi-step task planning on top of tool calling.
