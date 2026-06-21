# Architecture

> Status: **skeleton only**. This document describes the intended design so
> that future work has a clear target. No concrete functionality is
> implemented yet.

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

- **`Agent`** (`core/agent.py`) — the coordinator. Receives an intent,
  decides which capability handles it, and returns a result. Today it is
  an abstract shell; orchestration logic is a future milestone.
- **`Capability`** (`core/plugin.py`) — a single unit of functionality.
  Declares `can_handle(intent)` and `run(intent, context)`.
- **`Plugin`** (`core/plugin.py`) — a bundle of related capabilities; the
  recommended unit of distribution.

## How to extend

Prefer adding a **plugin** over editing core code:

1. Create a `Capability` subclass implementing `can_handle` and `run`.
2. Group related capabilities into a `Plugin`.
3. Register the plugin with the `Agent` at startup.

The plugin-discovery mechanism (entry points / directory scanning) will be
implemented in a later milestone.

## Phone–PC collaboration

The `sync/` subpackage will provide:

- A transport layer (websocket / mDNS / cloud relay — TBD).
- Device pairing and authentication.
- Shared context (clipboard, notifications, active task state).

Capabilities can then declare on which device they prefer to run, and the
agent can delegate across the link.

## Milestones (indicative)

1. ✅ Project skeleton, build/test tooling.
2. ⬜ Plugin registry + intent dispatch.
3. ⬜ First built-in capability (e.g. clipboard sync).
4. ⬜ Phone–PC transport and pairing.
5. ⬜ LLM-backed intent understanding.
