from datetime import datetime, timezone

from pydantic import BaseModel, Field


class AgentSkill(BaseModel):
    name: str
    description: str = ""
    confidence: float = 1.0


class AgentCard(BaseModel):
    name: str
    description: str = ""
    url: str
    version: str = "0.1.0"
    skills: list[AgentSkill] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)

    @property
    def skill_names(self) -> list[str]:
        return [s.name for s in self.skills]


class RegisteredAgent(BaseModel):
    card: AgentCard
    registered_at: str
    last_heartbeat: str

    def heartbeat_age_seconds(self, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        last = datetime.fromisoformat(self.last_heartbeat)
        return max((now - last).total_seconds(), 0.0)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
