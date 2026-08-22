from __future__ import annotations

import json
import threading
from pathlib import Path

from .models import AgentCard, RegisteredAgent, utc_now_iso


class AgentRegistry:
    def __init__(self, persistence_path: Path | None = None, stale_after_seconds: float = 900.0) -> None:
        self._agents: dict[str, RegisteredAgent] = {}
        self._lock = threading.Lock()
        self.persistence_path = persistence_path
        self.stale_after_seconds = stale_after_seconds
        self._load()

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
                    self._agents.pop(record["card"]["name"], None)
                else:
                    agent = RegisteredAgent.model_validate(record["agent"])
                    self._agents[agent.card.name] = agent

    def _append(self, record: dict) -> None:
        if self.persistence_path is None:
            return
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        with self.persistence_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

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
            self._append({"op": "upsert", "agent": agent.model_dump(mode="json")})
            return agent

    def deregister(self, name: str) -> bool:
        with self._lock:
            removed = self._agents.pop(name, None) is not None
            if removed:
                self._append({"op": "deregister", "card": {"name": name}})
            return removed

    def heartbeat(self, name: str) -> bool:
        with self._lock:
            agent = self._agents.get(name)
            if agent is None:
                return False
            agent.last_heartbeat = utc_now_iso()
            self._append({"op": "upsert", "agent": agent.model_dump(mode="json")})
            return True

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
