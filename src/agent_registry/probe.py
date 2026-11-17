"""Card conformance probe — what every A2A directory in the market sells
(a2aregistry.org, Agenstry, allagents, LocalMark): uptime + conformance
read from the agent's OWN /.well-known/agent-card.json, not the submitted
copy. A verified card here means: the live endpoint serves a card whose
name and every registered skill match what this registry holds.

SSRF posture (SECURITY.md: agent URLs are data, not instructions):
http/https schemes only, 3s timeout, no redirects followed, response
bodies over the 64KB cap are rejected — agent cards are 0.3-1KB
(arXiv 2508.03095), anything bigger is not a card.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from .models import AgentCard

BODY_CAP = 65_536
CAP_ITEMS = 25
PROBE_TIMEOUT = 3.0


def _http_get(url: str, timeout: float = PROBE_TIMEOUT) -> str:
    """Bounded fetch: no redirects, error statuses raise, body sliced to
    the cap BEFORE json parsing (oversize → explicit cap error)."""
    with httpx.Client(follow_redirects=False, timeout=timeout) as client:
        with client.stream("GET", url) as resp:
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}")
            it = resp.iter_bytes(BODY_CAP)
            chunk = next(it, b"")
            if next(it, b""):
                raise RuntimeError("agent-card.json exceeds the 64KB body cap")
            return chunk.decode("utf-8", errors="replace")


def probe_agent(card: AgentCard, transport=None, timeout: float = PROBE_TIMEOUT) -> dict:
    """Fetch {card.url}/.well-known/agent-card.json and compare it to the
    registered card. Never raises for network/content problems — those
    become {"verified": False, "error": ...}. A wrong scheme raises:
    that's a caller mistake, not a probe result."""
    scheme = urlparse(card.url).scheme.casefold()
    if scheme not in ("http", "https"):
        raise ValueError(f"probe needs an http(s) agent url, got {scheme or 'none'}")
    out: dict = {"verified": False, "error": None, "mismatched": [],
                 "checked": [], "fetched_at": None}
    url = card.url.rstrip("/") + "/.well-known/agent-card.json"
    try:
        transport = transport or _http_get
        text = transport(url, timeout=timeout)
    except Exception as exc:
        out["error"] = str(exc)[:200] or type(exc).__name__
        return out
    out["fetched_at"] = datetime.now(timezone.utc).isoformat()
    if len(text) > BODY_CAP:
        out["error"] = "agent-card.json exceeds the 64KB body cap"
        return out
    try:
        served = json.loads(text)
        assert isinstance(served, dict)
    except Exception:
        out["error"] = "agent-card.json is not a JSON object"
        return out
    served_name = str(served.get("name", "")).casefold()
    served_skills = {str(s.get("name", "")).casefold()
                     for s in served.get("skills", []) or [] if isinstance(s, dict)}
    checked, mismatched = [], []
    (checked if served_name == card.name.casefold() else mismatched).append("name")
    for s in card.skills:
        (checked if s.name.casefold() in served_skills
         else mismatched).append(f"skill:{s.name}")
    out["checked"] = checked[:CAP_ITEMS]
    out["mismatched"] = mismatched[:CAP_ITEMS]
    out["verified"] = bool(checked) and not mismatched
    return out
