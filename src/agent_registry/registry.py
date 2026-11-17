from __future__ import annotations

import json
import os
import threading
from collections import deque
from pathlib import Path

from .models import AgentCard, RegisteredAgent, utc_now_iso

EVENTS_MAX = 20          # bounded per-agent history: last 20 events
COMPACT_AFTER = 1000     # appends before the op-log is snapshotted


class AgentRegistry:
    def __init__(self, persistence_path: Path | None = None,
                 stale_after_seconds: float = 900.0,
                 compact_after: int = COMPACT_AFTER) -> None:
        self._agents: dict[str, RegisteredAgent] = {}
        self._events: dict[str, deque] = {}
        # RLock: _append runs under a caller's lock and auto-compaction
        # re-enters it
        self._lock = threading.RLock()
        self.persistence_path = persistence_path
        self.stale_after_seconds = stale_after_seconds
        self.compact_after = compact_after
        self._appends_since_compact = 0
        self._load()

    def _note(self, name: str, op: str, at: str | None = None, **extra) -> None:
        event = {"op": op, "at": at or utc_now_iso()}
        event.update(extra)
        self._events.setdefault(name, deque(maxlen=EVENTS_MAX)).append(event)

    def _load(self) -> None:
        if self.persistence_path is None or not self.persistence_path.exists():
            return
        with self.persistence_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get("op") == "deregister":
                    name = record["card"]["name"]
                    self._agents.pop(name, None)
                    self._note(name, "deregister", at=record.get("at"))
                else:
                    agent = RegisteredAgent.model_validate(record["agent"])
                    self._agents[agent.card.name] = agent
                    # kind distinguishes register/heartbeat/probe upserts;
                    # records written before kinds existed default to register
                    kind = record.get("kind", "register")
                    at = {"register": agent.registered_at,
                          "heartbeat": agent.last_heartbeat,
                          "probe": agent.last_probe or agent.last_heartbeat}[kind]
                    if kind == "probe":
                        self._note(agent.card.name, "probe", at=at,
                                   verified=agent.verified)
                    else:
                        self._note(agent.card.name, kind, at=at)

    def _append(self, record: dict) -> None:
        if self.persistence_path is None:
            return
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        with self.persistence_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        self._appends_since_compact += 1
        if self.compact_after and self._appends_since_compact >= self.compact_after:
            self.compact()

    def compact(self) -> int:
        """Rewrite the op-log as one upsert per live agent (Consul-style
        snapshot), atomically via temp file + os.replace. Bounds disk
        without losing live state. Tradeoff: pre-compaction event history
        goes with the truncated log. Returns agents written; 0 when not
        persisting."""
        if self.persistence_path is None:
            return 0
        with self._lock:
            tmp = self.persistence_path.with_suffix(
                self.persistence_path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                for agent in sorted(self._agents.values(),
                                    key=lambda a: a.card.name):
                    fh.write(json.dumps(
                        {"op": "upsert", "kind": "register",
                         "agent": agent.model_dump(mode="json")}) + "\n")
            os.replace(tmp, self.persistence_path)
            self._appends_since_compact = 0
            return len(self._agents)

    def register(self, card: AgentCard) -> RegisteredAgent:
        with self._lock:
            now = utc_now_iso()
            existing = self._agents.get(card.name)
            agent = RegisteredAgent(
                card=card,
                registered_at=existing.registered_at if existing else now,
                last_heartbeat=now,
            )
            self._agents[card.name] = agent
            self._append({"op": "upsert", "kind": "register",
                          "agent": agent.model_dump(mode="json")})
            self._note(card.name, "register", at=now)
            return agent

    def deregister(self, name: str) -> bool:
        with self._lock:
            removed = self._agents.pop(name, None) is not None
            if removed:
                now = utc_now_iso()
                self._append({"op": "deregister", "card": {"name": name}, "at": now})
                self._note(name, "deregister", at=now)
            return removed

    def heartbeat(self, name: str) -> bool:
        with self._lock:
            agent = self._agents.get(name)
            if agent is None:
                return False
            agent.last_heartbeat = utc_now_iso()
            self._append({"op": "upsert", "kind": "heartbeat",
                          "agent": agent.model_dump(mode="json")})
            self._note(name, "heartbeat", at=agent.last_heartbeat)
            return True

    def record_probe(self, name: str, result: dict) -> bool:
        """Store a conformance verdict (probe.probe_agent output) on the
        agent and replay it as an upsert. Unknown names are a no-op."""
        with self._lock:
            agent = self._agents.get(name)
            if agent is None:
                return False
            agent.verified = bool(result.get("verified"))
            agent.last_probe = utc_now_iso()
            agent.probe = {
                "verified": agent.verified,
                "error": result.get("error"),
                "checked": (result.get("checked") or [])[:25],
                "mismatched": (result.get("mismatched") or [])[:25],
                "fetched_at": result.get("fetched_at"),
            }
            self._append({"op": "upsert", "kind": "probe",
                          "agent": agent.model_dump(mode="json")})
            self._note(name, "probe", at=agent.last_probe,
                       verified=agent.verified)
            return True

    def history(self, name: str) -> list[dict] | None:
        """Bounded event trail (last EVENTS_MAX) for an agent this registry
        has seen. None = never seen. History outlives deregistration."""
        if name not in self._events and name not in self._agents:
            return None
        return list(self._events.get(name, ()))

    def get(self, name: str) -> RegisteredAgent | None:
        return self._agents.get(name)

    def list(self, include_stale: bool = False) -> list[RegisteredAgent]:
        out = []
        for agent in self._agents.values():
            if not include_stale and agent.heartbeat_age_seconds() > self.stale_after_seconds:
                continue
            out.append(agent)
        return sorted(out, key=lambda a: a.card.name)

    def find_by_skill(self, skill_name: str) -> list[RegisteredAgent]:
        needle = skill_name.casefold()
        return [a for a in self.list() if any(needle == s.casefold() for s in a.card.skill_names)]
