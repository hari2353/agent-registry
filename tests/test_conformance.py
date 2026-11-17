"""Card conformance probe + 2026 spec path (steal items 1-2).

Every A2A directory in the market (a2aregistry.org, Agenstry, allagents,
LocalMark) sells the same thing: uptime + conformance results read from the
agent's own `/.well-known/agent-card.json`. This repo listed cards but never
verified them. A probe fetches the card at the agent's declared URL,
compares it to what was registered, and stores a bounded verdict. Until
verified, cards are just self-reported.

SSRF posture: agent URLs are untrusted data (SECURITY.md). The probe allows
only http/https, uses a short timeout, and caps the response body — the
result is data, never a redirect to follow blindly.
"""
import json

import pytest


@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient

    from agent_registry.app import create_app
    from agent_registry.registry import AgentRegistry

    return TestClient(create_app(registry=AgentRegistry(persistence_path=tmp_path / "a.jsonl")))


CARD = {
    "name": "resume-screener",
    "url": "http://screener.local/a2a",
    "skills": [{"name": "Python", "confidence": 0.9}],
    "capabilities": ["screening"],
}


class FakeResp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


# ---------------------------------------------------------------- unit: probe
def test_probe_verifies_matching_card(monkeypatch):
    from agent_registry import probe as probe_module

    served = {"name": "resume-screener", "url": "http://screener.local/a2a",
              "skills": [{"name": "Python"}]}
    seen = {}

    def fake_get(url, **kw):
        seen["url"] = url
        seen["kw"] = kw
        return json.dumps(served)

    result = probe_module.probe_agent(_card(), transport=fake_get)
    assert result["verified"] is True
    assert result["error"] is None
    assert seen["url"].endswith("/.well-known/agent-card.json")
    assert seen["kw"]["timeout"] <= 5.0


def test_probe_flags_mismatched_skills(monkeypatch):
    from agent_registry import probe as probe_module

    served = {"name": "resume-screener",
              "skills": [{"name": "Docker"}]}          # registered: Python

    result = probe_module.probe_agent(
        _card(), transport=lambda url, **kw: json.dumps(served))
    assert result["verified"] is False
    assert any("python" in m.casefold() for m in result["mismatched"])
    assert result["error"] is None


def test_probe_reports_reachable_but_wrong_agent(monkeypatch):
    from agent_registry import probe as probe_module

    served = {"name": "someone-elses-agent", "skills": [{"name": "Python"}]}
    result = probe_module.probe_agent(
        _card(), transport=lambda url, **kw: json.dumps(served))
    assert result["verified"] is False
    assert result["error"] is None


def test_probe_bounded_body_and_bad_payload(monkeypatch):
    from agent_registry import probe as probe_module

    # garbage body → error, never a crash
    result = probe_module.probe_agent(
        _card(), transport=lambda url, **kw: "<html>not json</html>")
    assert result["verified"] is False
    assert result["error"]

    # bodies over the 64KB cap are rejected outright — agent cards are
    # 0.3-1KB (arXiv 2508.03095); anything bigger is not a card
    r2 = probe_module.probe_agent(
        _card(), transport=lambda url, **kw: "x" * 70_000)
    assert r2["verified"] is False
    assert "64kb" in r2["error"].casefold()


def test_probe_rejects_non_http_schemes():
    from agent_registry import probe as probe_module

    card = _card()
    card.url = "file:///etc/passwd"
    with pytest.raises(ValueError):
        probe_module.probe_agent(card, transport=lambda url, **kw: FakeResp(text="{}"))


def test_probe_translates_transport_errors(monkeypatch):
    from agent_registry import probe as probe_module

    def boom(url, **kw):
        raise RuntimeError("connection refused")
    result = probe_module.probe_agent(_card(), transport=boom)
    assert result["verified"] is False
    assert "connection refused" in result["error"]


# --------------------------------------------------- api: probe on register
def _ok_probe():
    return {"verified": True, "error": None, "mismatched": [], "checked": ["name"],
            "fetched_at": "2026-11-17T00:00:00+00:00"}


def _dead_probe():
    return {"verified": False, "error": "connection refused", "mismatched": [],
            "checked": [], "fetched_at": "2026-11-17T00:00:00+00:00"}


def test_register_with_probe_stores_verified(client, monkeypatch):
    from agent_registry import app as app_module

    monkeypatch.setattr(app_module, "probe_agent", lambda card, **kw: _ok_probe())
    resp = client.post("/agents?probe=true", json=CARD)
    assert resp.status_code == 200
    got = client.get("/agents/resume-screener").json()
    assert got["verified"] is True
    assert got["last_probe"]
    assert got["probe"]["verified"] is True


def test_register_probe_failure_is_not_a_registration_failure(client, monkeypatch):
    from agent_registry import app as app_module

    monkeypatch.setattr(app_module, "probe_agent", lambda card, **kw: _dead_probe())
    resp = client.post("/agents?probe=true", json=CARD)
    assert resp.status_code == 200                 # still registered
    got = client.get("/agents/resume-screener").json()
    assert got["verified"] is False
    assert "connection refused" in got["probe"]["error"]


def test_register_without_probe_stays_unprobed(client):
    client.post("/agents", json=CARD)
    got = client.get("/agents/resume-screener").json()
    assert got["verified"] is None                 # self-reported only


def test_reprobe_endpoint(client, monkeypatch):
    from agent_registry import app as app_module

    client.post("/agents", json=CARD)
    monkeypatch.setattr(app_module, "probe_agent", lambda card, **kw: _ok_probe())
    resp = client.post("/agents/resume-screener/probe")
    assert resp.status_code == 200
    assert resp.json()["verified"] is True
    assert client.post("/agents/ghost/probe").status_code == 404


# ---------------------------------------------------------------- spec path
def test_2026_wellknown_path_served(client):
    """agent-card.json is the IANA-registered path (A2A v0.2+); keep the
    old /agent.json as an alias."""
    new = client.get("/.well-known/agent-card.json")
    old = client.get("/.well-known/agent.json")
    assert new.status_code == 200 and old.status_code == 200
    assert new.json() == old.json()


# ---------------------------------------------------------------- persistence
def test_probe_fields_survive_replay(client, tmp_path):
    from agent_registry.registry import AgentRegistry

    path = tmp_path / "a.jsonl"
    from fastapi.testclient import TestClient
    from agent_registry.app import create_app

    c = TestClient(create_app(registry=AgentRegistry(persistence_path=path)))
    c.post("/agents", json=CARD)
    reg = AgentRegistry(persistence_path=path)
    agent = reg.get("resume-screener")
    assert agent.verified is None                  # unprobed card replays clean


def _card():
    from agent_registry.models import AgentCard

    return AgentCard(**CARD)
