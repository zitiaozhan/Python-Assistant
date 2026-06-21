# Architecture

> Status: **Agent + tool calling 已可用**。Agent 通过与模型解耦的 toolcall 协议
> 自主调用工具（首个工具：bash）。手机↔电脑协作、插件自动发现为后续路线图。

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
│   (intent routing, planning, memory, LLM)      │
├───────────────────────────────────────────────┤
│              Plugin registry                   │   extensibility
├───────────────┬───────────────┬───────────────┤
│   plugins/    │   plugins/    │   plugins/    │   capabilities
│  builtin      │  3rd-party    │  user-local   │
├───────────────┴───────────────┴───────────────┤
│                 sync/                          │   phone<->PC
│   (transport, pairing, shared state)           │
└───────────────────────────────────────────────┘
```

## Core abstractions

- **`Agent`** (`core/agent.py`) — the coordinator. Drives the toolcall loop:
  sends messages + tool specs to the model, executes any requested tools,
  feeds results back, and loops until the model gives a final text reply.
  Includes a `confirm` gate (per tool call) and `on_event` hook for UI.
- **`Tool`** (`core/tool.py`) — base class for all tools. Subclasses declare
  `name` / `description` / `parameters` (JSON Schema) and implement `run`.
  See `tools/README.md` for how to add one.
- **Protocol** (`core/protocol.py`) — the model-agnostic contract between
  Agent and `LLMClient`: `ToolSpec`, `ToolCall`, `ToolResult`, `Message`,
  `LLMResponse`. **This is the decoupling boundary** — Agent never sees the
  model's wire format.
- **`Capability` / `Plugin`** (`core/plugin.py`) — an earlier, coarser
  capability abstraction, reserved for future higher-level composition.

## Decoupling: Agent ↔ model

```
Agent (core/agent.py)
   │  operates only on protocol types (Message / ToolSpec / ToolCall ...)
   ▼
LLMClient (llm/client.py)        ←── translates to/from the model's wire format
   │  (OpenAI-compatible: tools=[], tool_calls=[], role="tool" ...)
   ▼
DeepSeek / OpenAI / any compatible provider
```

Switching providers: change `config/model.json` (`base_url`/`model`) and,
only if the wire protocol differs, adjust the translators in `LLMClient`.
Agent and tools stay untouched.

## How to extend (tools)

Prefer adding a **tool** over editing core code:

1. Subclass `Tool`, fill in `name` / `description` / `parameters`, implement `run`.
2. Register it in `tools/__init__.default_tools()`.
3. The model will discover and call it automatically via toolcall.

See [`src/personal_assistant/tools/README.md`](../src/personal_assistant/tools/README.md)
for a worked example (bash).

## Phone–PC collaboration

The `sync/` subpackage will provide:

- A transport layer (websocket / mDNS / cloud relay — TBD).
- Device pairing and authentication.
- Shared context (clipboard, notifications, active task state).

Capabilities can then declare on which device they prefer to run, and the
agent can delegate across the link.

## Milestones (indicative)

1. ✅ Project skeleton, build/test tooling.
2. ✅ CLI chat REPL with streaming output + configurable model (DeepSeek via OpenAI-compatible API).
3. ✅ Agent tool-calling: decoupled protocol + orchestration loop + bash tool.
4. ⬜ More built-in tools (files, search, clipboard).
5. ⬜ Plugin/tool auto-discovery (entry points / directory scanning).
6. ⬜ Phone–PC transport and pairing.
7. ⬜ Multi-step task planning on top of tool calling.
