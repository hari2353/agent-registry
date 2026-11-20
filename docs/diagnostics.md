# Diagnostics

Every expected failure carries a stable code, a fix, and this page. Probe
results keep the legacy `error` string and add `diagnostic`:

```json
{"code": "REG_PROBE_HTTP_STATUS",
 "message": "HTTP 404",
 "hint": "make the agent serve /.well-known/agent-card.json with a 2xx",
 "docs": "docs/diagnostics.md#reg_probe_http_status"}
```

HTTP rejections put the same object in `detail`.

| code | meaning | fix |
|---|---|---|
| `REG_BAD_AGENT_URL` | agent URL is not http(s) | register an http(s) URL |
| `REG_PROBE_HTTP_STATUS` | card endpoint returned 4xx/5xx | serve the card with a 2xx |
| `REG_PROBE_BODY_TOO_LARGE` | body exceeded 64KB | serve a real card (0.3–1KB) |
| `REG_PROBE_INVALID_JSON` | body was not a JSON object | serve the A2A card JSON |
| `REG_PROBE_UNREACHABLE` | connect/timeout/transport error | start the agent, check the URL |
| `REG_UNKNOWN_AGENT` | name is not registered | `GET /agents` |
| `REG_TOPIC_REQUIRED` | brief had a blank topic | send a non-blank topic |
| `REG_ENGINE_UNREACHABLE` | skills-engine call failed | start the engine |

## REG_BAD_AGENT_URL

The probe only follows http/https. `file:`, `ftp:`, and bare strings are
caller mistakes, so they raise instead of returning a probe verdict.

## REG_PROBE_HTTP_STATUS

The agent answered, but not with a card. Check the well-known path and the
agent's routing; a 404 here usually means the card moved.

## REG_PROBE_BODY_TOO_LARGE

Agent cards are under 1KB. A 64KB+ body is not a card and is rejected before
parsing.

## REG_PROBE_INVALID_JSON

The response was HTML, plain text, or malformed JSON. Serve a JSON object at
`/.well-known/agent-card.json` (and the legacy `/agent.json` alias if needed).

## REG_PROBE_UNREACHABLE

The probe could not connect. This is a transport failure, not a card mismatch.
Start the agent and re-check its registered URL.

## REG_UNKNOWN_AGENT

The name does not exist in this registry. `GET /agents` lists what does.

## REG_TOPIC_REQUIRED

`POST /briefs` needs a non-blank `topic`.

## REG_ENGINE_UNREACHABLE

The brief could not be built because the skills engine call failed. Start
skills-engine or fix its base URL.
