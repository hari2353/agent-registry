"""Fuzzy skill matching + coverage_pct in briefs (steal item 3).

Agennect's #1 marketed feature is "describe your goal → ranked agent
matches" (semantic search); Neuronto fuses rankings. This repo matched
skills by EXACT casefold name — an agent whose card says "Graph
orchestration with LangGraph" was invisible to the skill "orchestration".

We don't need a vector DB to get 80% of that: token overlap between the
required skill and the card's own text (name, description, skills,
capabilities). Exact = 1.0; partial >= 0.5, labelled as such; below that
the skill stays an honest gap. Briefs also report coverage_pct so a
caller can gate on "is this brief good enough" without parsing prose.
"""

import pytest


@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient

    from agent_registry.app import create_app
    from agent_registry.registry import AgentRegistry

    return TestClient(
        create_app(registry=AgentRegistry(persistence_path=tmp_path / "a.jsonl"))
    )


def _card(**over):
    from agent_registry.models import AgentCard

    base = {
        "name": "graph-agent",
        "url": "http://g.local",
        "skills": [],
        "capabilities": [],
    }
    base.update(over)
    return AgentCard(**base)


# ---------------------------------------------------------------- unit
def test_match_scores_token_overlap():
    from agent_registry.brief import match_score

    card = _card(
        description="Graph orchestration with LangGraph", skills=[{"name": "LangGraph"}]
    )
    assert match_score("orchestration", card) == 1.0
    assert match_score("graph orchestration", card) == 1.0
    assert match_score("kubernetes", card) == 0.0


def test_match_scores_multiword_skills_partial():
    from agent_registry.brief import match_score

    card = _card(skills=[{"name": "Data"}])
    assert 0.49 < match_score("data engineering", card) < 1.0
    assert match_score("quantum physics", card) == 0.0


def test_match_scores_are_case_and_punctuation_robust():
    from agent_registry.brief import match_score

    card = _card(skills=[{"name": "C++"}, {"name": "Node.js"}])
    assert match_score("c++", card) == 1.0
    assert match_score("node.js", card) == 1.0


# ---------------------------------------------------------------- brief
def test_exact_match_labelled_exact(client, monkeypatch):
    from agent_registry import brief as bm

    client.post(
        "/agents",
        json={
            "name": "py-agent",
            "url": "http://p.local",
            "skills": [{"name": "Python"}],
        },
    )
    monkeypatch.setattr(
        bm,
        "infer_required_skills",
        lambda text, ct="job_description", transport=None: ["Python"],
    )
    body = client.post("/briefs", json={"topic": "t"}).json()
    rec = body["recommended_agents"][0]
    assert rec["match"] == "exact" and rec["score"] == 1.0
    assert body["coverage_pct"] == 100


def test_partial_match_via_description_recommended(client, monkeypatch):
    from agent_registry import brief as bm

    client.post(
        "/agents",
        json={
            "name": "graph-agent",
            "url": "http://g.local",
            "description": "Builds graph pipelines with LangGraph",
            "skills": [{"name": "LangGraph"}],
        },
    )
    monkeypatch.setattr(
        bm,
        "infer_required_skills",
        lambda text, ct="job_description", transport=None: ["Graph pipelines"],
    )
    body = client.post("/briefs", json={"topic": "t"}).json()
    rec = body["recommended_agents"][0]
    assert rec["agent"] == "graph-agent"
    # not an exact skill-name entry → "partial", even at full token coverage
    assert rec["match"] == "partial" and 0.5 <= rec["score"] <= 1.0
    assert body["coverage_pct"] == 100  # partial still counts as covered


def test_weak_matches_stay_honest_gaps(client, monkeypatch):
    from agent_registry import brief as bm

    client.post(
        "/agents",
        json={
            "name": "py-agent",
            "url": "http://p.local",
            "skills": [{"name": "Python"}],
        },
    )
    monkeypatch.setattr(
        bm,
        "infer_required_skills",
        lambda text, ct="job_description", transport=None: ["Quantum error correction"],
    )
    body = client.post("/briefs", json={"topic": "t"}).json()
    assert body["recommended_agents"] == []  # not recommended on a 0-score hunch
    assert body["skill_gaps"] == ["Quantum error correction"]
    assert body["coverage_pct"] == 0


def test_best_agent_wins_on_score_then_confidence(client, monkeypatch):
    from agent_registry import brief as bm

    client.post(
        "/agents",
        json={
            "name": "weak",
            "url": "http://w.local",
            "description": "python-adjacent tooling",
            "skills": [{"name": "Tooling", "confidence": 0.99}],
        },
    )
    client.post(
        "/agents",
        json={
            "name": "strong",
            "url": "http://s.local",
            "skills": [{"name": "Python", "confidence": 0.5}],
        },
    )
    monkeypatch.setattr(
        bm,
        "infer_required_skills",
        lambda text, ct="job_description", transport=None: ["Python"],
    )
    body = client.post("/briefs", json={"topic": "t"}).json()
    assert body["recommended_agents"][0]["agent"] == "strong"


def test_coverage_pct_mixed(client, monkeypatch):
    from agent_registry import brief as bm

    client.post(
        "/agents",
        json={
            "name": "py-agent",
            "url": "http://p.local",
            "skills": [{"name": "Python"}],
        },
    )
    monkeypatch.setattr(
        bm,
        "infer_required_skills",
        lambda text, ct="job_description", transport=None: [
            "Python",
            "Kubernetes",
            "Terraform",
        ],
    )
    body = client.post("/briefs", json={"topic": "t"}).json()
    assert body["coverage_pct"] == 33
    assert "1 of 3" in body["summary"]
