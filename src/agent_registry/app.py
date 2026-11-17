from fastapi import FastAPI, HTTPException

from .brief import build_brief
from .models import AgentCard
from .probe import probe_agent
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

    @app.get("/.well-known/agent-card.json")
    def own_card_2026() -> dict:
        # IANA-registered well-known path (A2A v0.2+); /agent.json stays as
        # an alias for cards written against the older convention.
        return OWN_CARD.model_dump(mode="json")

    @app.post("/agents")
    def register(card: AgentCard, probe: bool = False) -> dict:
        agent = reg.register(card)
        out = {"name": agent.card.name, "registered_at": agent.registered_at}
        if probe:
            result = probe_agent(card)
            reg.record_probe(agent.card.name, result)
            agent = reg.get(agent.card.name)
            out.update({"verified": agent.verified, "last_probe": agent.last_probe,
                        "probe": agent.probe})
        return out

    def _agent_view(agent) -> dict:
        return {"card": agent.card.model_dump(mode="json"),
                "last_heartbeat": agent.last_heartbeat,
                "verified": agent.verified,
                "last_probe": agent.last_probe,
                "probe": agent.probe}

    @app.post("/agents/{name}/probe")
    def reprobe(name: str) -> dict:
        agent = reg.get(name)
        if agent is None:
            raise HTTPException(status_code=404, detail="unknown agent")
        result = probe_agent(agent.card)
        reg.record_probe(name, result)
        agent = reg.get(name)
        return {"name": name, "verified": agent.verified,
                "last_probe": agent.last_probe, "probe": agent.probe}

    @app.get("/agents")
    def list_agents(include_stale: bool = False) -> list[dict]:
        out = []
        for agent in reg.list(include_stale=include_stale):
            out.append({"card": agent.card.model_dump(mode="json"),
                        "stale": agent.heartbeat_age_seconds() > reg.stale_after_seconds,
                        "verified": agent.verified})
        return out

    @app.get("/agents/{name}")
    def get_agent(name: str) -> dict:
        agent = reg.get(name)
        if agent is None:
            raise HTTPException(status_code=404, detail="unknown agent")
        return _agent_view(agent)

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
