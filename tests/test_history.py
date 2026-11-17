"""Per-agent event history (steal item 4).

allagents and LocalMark both show a per-agent CHECK HISTORY — when it was
last seen, what probes found. This repo already writes every event to the
JSONL op-log but exposes only the latest state; the history was there,
just unreachable through the API. Bounded: last 20 events per agent,
replayed from the op-log on restart.
"""
import pytest


@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient

    from agent_registry.app import create_app
    from agent_registry.registry import AgentRegistry

    return TestClient(create_app(registry=AgentRegistry(persistence_path=tmp_path / "a.jsonl")))


CARD = {"name": "resume-screener", "url": "http://screener.local/a2a",
        "skills": [{"name": "Python"}]}


def test_history_records_lifecycle(client):
    client.post("/agents", json=CARD)
    client.post("/agents/resume-screener/heartbeat")
    client.post("/agents/resume-screener/heartbeat")
    client.delete("/agents/resume-screener")

    h = client.get("/agents/resume-screener/history").json()
    ops = [e["op"] for e in h["events"]]
    assert ops == ["register", "heartbeat", "heartbeat", "deregister"]
    assert all(e["at"] for e in h["events"])


def test_history_records_probe_with_verdict(client, monkeypatch):
    from agent_registry import app as app_module

    client.post("/agents", json=CARD)
    monkeypatch.setattr(app_module, "probe_agent",
                        lambda card, **kw: {"verified": True, "error": None,
                                            "checked": ["name"], "mismatched": [],
                                            "fetched_at": "now"})
    client.post("/agents/resume-screener/probe")
    h = client.get("/agents/resume-screener/history").json()
    probe_events = [e for e in h["events"] if e["op"] == "probe"]
    assert probe_events and probe_events[0]["verified"] is True


def test_history_unknown_agent_404(client):
    assert client.get("/agents/ghost/history").status_code == 404


def test_history_survives_restart(client, tmp_path):
    from agent_registry.app import create_app
    from agent_registry.registry import AgentRegistry
    from fastapi.testclient import TestClient

    client.post("/agents", json=CARD)
    client.post("/agents/resume-screener/heartbeat")

    reg2 = AgentRegistry(persistence_path=tmp_path / "a.jsonl")
    c2 = TestClient(create_app(registry=reg2))
    h = c2.get("/agents/resume-screener/history").json()
    ops = [e["op"] for e in h["events"]]
    assert "register" in ops and "heartbeat" in ops


def test_history_bounded_at_20(client):
    client.post("/agents", json=CARD)
    for _ in range(25):
        client.post("/agents/resume-screener/heartbeat")
    h = client.get("/agents/resume-screener/history").json()
    assert len(h["events"]) == 20
    assert h["events"][0]["op"] == "heartbeat"      # oldest events dropped


def test_reregister_after_deregister_keeps_history(client):
    client.post("/agents", json=CARD)
    client.delete("/agents/resume-screener")
    client.post("/agents", json=CARD)
    h = client.get("/agents/resume-screener/history").json()
    ops = [e["op"] for e in h["events"]]
    assert ops == ["register", "deregister", "register"]
