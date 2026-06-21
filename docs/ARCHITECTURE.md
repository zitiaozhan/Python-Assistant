# Architecture

> Status: **Agent + 工具调用 + 技能系统 + Token 统计已可用**。Agent 通过与模型解耦的
> toolcall 协议自主调用工具（bash）和技能（文件夹式 SKILL.md），并在每轮对话后报告
> Token 消耗。手机↔电脑协作为后续路线图。

## Goals

1. **Personal assistant** — understands intents and acts on the user's behalf.
2. **Phone–PC collaboration** — the same assistant spans a phone and a
   computer, sharing context and delegating work to whichever device is
   best suited.
3. **Continuously extensible** — new abilities can be added without
   touching core code, ideally as independently distributable packages.

## Layered overview

```
┌───────────────────────────────────────────────┐
│              CLI / UI / API                    │   entry points
├───────────────────────────────────────────────┤
│                  Agent                         │   orchestration
│   (intent routing, toolcall loop, token sum)   │
├───────────────┬───────────────┬───────────────┤
│   tools/      │   skills/     │   plugins/    │   capabilities
│  (Tool 类)    │ (文件夹+MD)    │  (预留)       │
├───────────────┴───────────────┴───────────────┤
│              LLMClient                         │   protocol translation
│   (OpenAI-compatible ↔ internal types)         │
├───────────────────────────────────────────────┤
│                 sync/                          │   phone<->PC (预留)
│   (transport, pairing, shared state)           │
└───────────────────────────────────────────────┘
```

## Core abstractions

- **`Agent`** (`core/agent.py`) — the coordinator. Drives the toolcall loop:
  sends messages + tool specs to the model, executes any requested tools,
  feeds results back, and loops until the model gives a final text reply.
  Includes a `confirm` gate (per tool call), `on_event` hook for UI, and
  accumulates `TokenUsage` across all model calls in a single turn.
- **`Tool`** (`core/tool.py`) — base class for all tools. Subclasses declare
  `name` / `description` / `parameters` (JSON Schema) and implement `run`.
  The model calls tools directly via toolcall. See `tools/README.md`.
- **`SkillFolder` / `SkillManager`** (`core/skill.py`) — folder-based skill
  system. Each skill is a subdirectory containing `SKILL.md` (name +
  description + body). The model sees only names+descriptions; upon calling
  `use_skill`, it receives the full `SKILL.md` + all markdown files.
  `SkillManager` auto-scans the `skills/` directory. See `skills/README.md`.
- **`TokenUsage`** (`core/protocol.py`) — token consumption tracking.
  Supports `+` accumulation across multiple model calls in one turn.
  Fields: `prompt_tokens`, `completion_tokens`, `total_tokens`,
  `cached_tokens`, `reasoning_tokens`. Compatible with OpenAI standard
  (`prompt_tokens_details.cached_tokens`) and DeepSeek extension
  (`prompt_cache_hit_tokens`) formats.
- **Protocol** (`core/protocol.py`) — the model-agnostic contract between
  Agent and `LLMClient`: `ToolSpec`, `ToolCall`, `ToolResult`, `Message`,
  `LLMResponse`, `TokenUsage`. **This is the decoupling boundary** — Agent
  never sees the model's wire format.
- **`Capability` / `Plugin`** (`core/plugin.py`) — an earlier, coarser
  capability abstraction, reserved for future higher-level composition.

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

## How to extend

### Tools (原子操作)

Prefer adding a **tool** for atomic operations:

1. Subclass `Tool`, fill in `name` / `description` / `parameters`, implement `run`.
2. Register it in `tools/__init__.default_tools()`.
3. The model will discover and call it automatically via toolcall.

See [`src/personal_assistant/tools/README.md`](../src/personal_assistant/tools/README.md)
for a worked example (bash).

### Skills (领域知识 + 多步骤指引)

Prefer adding a **skill** for domain knowledge and multi-step task guidance:

1. Create a subdirectory under `skills/`.
2. Write `SKILL.md` (name + description + body).
3. Optionally add auxiliary files (scripts, more markdown docs).

`SkillManager` auto-discovers it on startup — no code changes needed.

See [`src/personal_assistant/skills/README.md`](../src/personal_assistant/skills/README.md)
for details and the built-in `websearch` skill as an example.

### Tool vs Skill

| Aspect | Tool | Skill |
|--------|------|-------|
| Form | Python class | Folder + `SKILL.md` |
| Model invocation | Direct toolcall | Via `use_skill` indirect call |
| Returned to model | `run()` result | `SKILL.md` full text + all `.md` files |
| Best for | Atomic operations | Domain knowledge + multi-step guidance |
| Adding new | Write class + register | Create folder + write `SKILL.md` |

## Phone–PC collaboration

The `sync/` subpackage will provide:

- A transport layer (websocket / mDNS / cloud relay — TBD).
- Device pairing and authentication.
- Shared context (clipboard, notifications, active task state).

Capabilities can then declare on which device they prefer to run, and the
agent can delegate across the link.

## Milestones (indicative)

1. ✅ Project skeleton, build/test tooling (uv + ruff + pytest + hatchling).
2. ✅ CLI chat REPL with streaming output + configurable model (DeepSeek via OpenAI-compatible API).
3. ✅ Agent tool-calling: decoupled protocol + orchestration loop + bash tool.
4. ✅ Skill system: folder-based `SKILL.md` + `use_skill` tool + auto-scan + websearch skill.
5. ✅ Token usage tracking: prompt/completion/total/cached/reasoning, OpenAI & DeepSeek compatible.
6. ⬜ More built-in tools (file I/O, clipboard, system notifications).
7. ⬜ Skill/tool auto-discovery (entry points / directory scanning).
8. ⬜ Phone–PC transport and pairing.
9. ⬜ Multi-step task planning on top of tool calling.
