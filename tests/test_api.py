import pytest


@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient

    from agent_registry.app import create_app
    from agent_registry.registry import AgentRegistry

    return TestClient(create_app(registry=AgentRegistry(persistence_path=tmp_path / "a.jsonl")))


def sample_card():
    return {
        "name": "resume-screener",
        "url": "http://screener.local/a2a",
        "skills": [{"name": "Python", "confidence": 0.9}, {"name": "Docker", "confidence": 0.8}],
        "capabilities": ["screening"],
    }


def test_health_and_own_agent_card(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    card = client.get("/.well-known/agent.json").json()
    assert card["name"] == "agent-registry"
    assert "briefs" in card["capabilities"]


def test_register_get_heartbeat_delete_lifecycle(client):
    assert client.post("/agents", json=sample_card()).status_code == 200
    got = client.get("/agents/resume-screener").json()
    assert got["card"]["url"] == "http://screener.local/a2a"
    assert client.post("/agents/resume-screener/heartbeat").json()["heartbeat"] == "ok"
    assert client.delete("/agents/resume-screener").json()["deregistered"] is True
    assert client.get("/agents/resume-screener").status_code == 404
    assert client.delete("/agents/ghost").status_code == 404


def test_unknown_agent_404_on_heartbeat(client):
    assert client.post("/agents/ghost/heartbeat").status_code == 404


def test_brief_recommends_and_reports_gaps(client, monkeypatch):
    from agent_registry import brief as brief_module

    client.post("/agents", json=sample_card())

    def fake_infer(text, context_type="job_description", transport=None):
        return ["Python", "Docker", "Kubernetes"]

    monkeypatch.setattr(brief_module, "infer_required_skills", fake_infer)
    body = client.post("/briefs", json={"topic": "platform engineer JD"}).json()
    assert set(body["required_skills"]) == {"Python", "Docker", "Kubernetes"}
    assert {r["agent"] for r in body["recommended_agents"]} == {"resume-screener"}
    assert body["skill_gaps"] == ["Kubernetes"]
    assert "gaps" in body["summary"]


def test_brief_requires_topic(client):
    assert client.post("/briefs", json={"topic": "  "}).status_code == 422
