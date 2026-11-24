from datetime import datetime, timezone

from pydantic import BaseModel, Field


class AgentSkill(BaseModel):
    name: str
    description: str = ""
    confidence: float = 1.0


class AgentCard(BaseModel):
    name: str = Field(max_length=128)
    description: str = Field(default="", max_length=2000)
    url: str = Field(max_length=500)
    version: str = Field(default="0.1.0", max_length=32)
    skills: list[AgentSkill] = Field(default_factory=list, max_length=50)
    capabilities: list[str] = Field(default_factory=list, max_length=25)

    @property
    def skill_names(self) -> list[str]:
        return [s.name for s in self.skills]


class RegisteredAgent(BaseModel):
    card: AgentCard
    registered_at: str
    last_heartbeat: str
    verified: bool | None = None  # None = never probed (self-reported only)
    last_probe: str | None = None
    probe: dict | None = None  # bounded verdict from probe.probe_agent

    def heartbeat_age_seconds(self, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        last = datetime.fromisoformat(self.last_heartbeat)
        return max((now - last).total_seconds(), 0.0)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
