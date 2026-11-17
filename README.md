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
| GET | `/.well-known/agent-card.json` | this registry's own A2A-style card (IANA-registered v0.2+ path; `/agent.json` stays as an alias) |
| POST | `/agents` | register an Agent Card; `?probe=true` also verifies the card against the agent's own `/.well-known/agent-card.json` |
| GET | `/agents` | list live agents (stale filtered) |
| POST | `/agents/{name}/heartbeat` | liveness ping |
| DELETE | `/agents/{name}` | deregister |
| POST | `/agents/{name}/probe` | re-run the conformance probe |
| GET | `/agents/{name}/history` | bounded event trail (last 20: register/heartbeat/probe/deregister) |
| POST | `/briefs` | `{topic}` → inferred skills → recommended agents + gaps + `coverage_pct` |

## Design notes

- Registry is append-only JSONL with op replay (`upsert` / `deregister`) — crash-safe persistence without a DB; auto-compacted to a snapshot after 1000 ops
- Staleness is time-based (`stale_after_seconds`, default 15 min); dead agents drop out of discovery automatically
- Card conformance probe: `?probe=true` on register (or `POST .../probe`) fetches the agent's own `/.well-known/agent-card.json` and compares name + every registered skill — `verified` is earned, not claimed. http/https only, 3s timeout, no redirects, 64KB body cap
- Briefs match skills by token overlap (exact skill-name entries labelled `exact`, fuzzy text matches `partial`, below 0.5 stays an honest gap) and report `coverage_pct`
- Briefs never fail silently: uncovered skills are returned as `skill_gaps` rather than dropped
- Engine outage degrades to HTTP 502 with reason — no fabricated recommendations

MIT
