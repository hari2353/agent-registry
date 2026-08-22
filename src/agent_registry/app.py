from fastapi import FastAPI, HTTPException

from .brief import build_brief
from .models import AgentCard
from .registry import AgentRegistry

OWN_CARD = AgentCard(
    name="agent-registry",
    description="A2A-style registry of skill-capable agents with brief orchestration",
    url="/.well-known/agent.json",
    skills=[],
    capabilities=["registry", "heartbeat", "briefs"],
)


def create_app(registry: AgentRegistry | None = None) -> FastAPI:
    app = FastAPI(title="Agent Registry", version="0.1.0")
    reg = registry or AgentRegistry()

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/.well-known/agent.json")
    def own_card() -> dict:
        return OWN_CARD.model_dump(mode="json")

    @app.post("/agents")
    def register(card: AgentCard) -> dict:
        agent = reg.register(card)
        return {"name": agent.card.name, "registered_at": agent.registered_at}

    @app.get("/agents")
    def list_agents(include_stale: bool = False) -> list[dict]:
        out = []
        for agent in reg.list(include_stale=include_stale):
            out.append({"card": agent.card.model_dump(mode="json"), "stale": agent.heartbeat_age_seconds() > reg.stale_after_seconds})
        return out

    @app.get("/agents/{name}")
    def get_agent(name: str) -> dict:
        agent = reg.get(name)
        if agent is None:
            raise HTTPException(status_code=404, detail="unknown agent")
        return {"card": agent.card.model_dump(mode="json"), "last_heartbeat": agent.last_heartbeat}

    @app.post("/agents/{name}/heartbeat")
    def heartbeat(name: str) -> dict:
        if not reg.heartbeat(name):
            raise HTTPException(status_code=404, detail="unknown agent")
        return {"name": name, "heartbeat": "ok"}

    @app.delete("/agents/{name}")
    def deregister(name: str) -> dict:
        if not reg.deregister(name):
            raise HTTPException(status_code=404, detail="unknown agent")
        return {"name": name, "deregistered": True}

    @app.post("/briefs")
    def create_brief(payload: dict) -> dict:
        topic = str(payload.get("topic", "")).strip()
        if not topic:
            raise HTTPException(status_code=422, detail="topic required")
        context_type = str(payload.get("context_type", "job_description"))
        try:
            brief = build_brief(reg, topic, context_type)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"skills engine unreachable: {exc}")
        return brief

    return app


app = create_app()
