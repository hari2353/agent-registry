# Agent Registry

[![ci](https://github.com/hari2353/agent-registry/actions/workflows/ci.yml/badge.svg)](https://github.com/hari2353/agent-registry/actions/workflows/ci.yml)

An **A2A-style agent registry**: agents publish Agent Cards (name, url, skills, capabilities), heartbeat to
stay discoverable, and a **brief orchestrator** matches required skills (inferred by
[skills-engine](https://github.com/hari2353/skills-engine)) against registered agents — reporting coverage,
recommendations, and explicit skill gaps.

Part of the agentic stack: `skills-engine` (reasoning over skills) → `skills-mcp` (tool exposure) →
`agent-registry` (discovery + orchestration).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/.well-known/agent.json` | this registry's own A2A-style card |
| POST | `/agents` | register an Agent Card |
| GET | `/agents` | list live agents (stale filtered) |
| POST | `/agents/{name}/heartbeat` | liveness ping |
| DELETE | `/agents/{name}` | deregister |
| POST | `/briefs` | `{topic}` → inferred skills → recommended agents + gaps |

## Design notes

- Registry is append-only JSONL with op replay (`upsert` / `deregister`) — crash-safe persistence without a DB
- Staleness is time-based (`stale_after_seconds`, default 15 min); dead agents drop out of discovery automatically
- Briefs never fail silently: uncovered skills are returned as `skill_gaps` rather than dropped
- Engine outage degrades to HTTP 502 with reason — no fabricated recommendations

MIT
