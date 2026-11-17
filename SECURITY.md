# Security Notes

Runs behind an authenticating gateway in production deployments; registration endpoints are the trust
boundary for agent metadata.

## Controls in place

- **Pydantic-validated Agent Cards**: `url`, `name`, skills are typed and length-bounded by model config;
  no free-form HTML/HTML-renderable fields are stored or returned unescaped by this API
- **Agent URLs are data, not instructions**: brief responses include registered URLs verbatim as strings —
  callers must treat them as untrusted (SSRF-safe clients should allowlist schemes)
- **Engine outage containment**: skills-engine failures return structured 502s, never partial/fabricated briefs
- **Append-only persistence**: JSONL op-log replays `upsert`/`deregister`; no query surface, nothing to inject
- **Security headers**: `X-Content-Type-Options: nosniff` on all responses
- **Bounded conformance probe**: `probe.py` fetches the agent's own `/.well-known/agent-card.json` with http/https schemes only, a 3s timeout, no redirects, and a 64KB body cap (agent cards are 0.3-1KB; arXiv 2508.03095) — probe failures degrade to `verified: false`, never a crash; probing is opt-in per call

## Known gaps (deliberate for demo scope)

- No authN on registration — production would require per-agent mTLS or gateway-issued identities
- Heartbeat/staleness is honor-system; a malicious agent can keep itself alive — mitigate with signed heartbeats
