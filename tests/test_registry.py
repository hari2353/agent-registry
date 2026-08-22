from agent_registry.models import AgentCard, AgentSkill
from agent_registry.registry import AgentRegistry


def card(name, skills, url="http://agent.local"):
    return AgentCard(name=name, url=url, skills=[AgentSkill(name=s) for s in skills])


def test_register_and_list_roundtrip(tmp_path):
    reg = AgentRegistry(persistence_path=tmp_path / "agents.jsonl")
    reg.register(card("coder", ["Python", "Docker"]))
    reg.register(card("writer", ["Content Strategy"]))
    names = [a.card.name for a in reg.list()]
    assert names == ["coder", "writer"]


def test_find_by_skill_exact_casefold():
    reg = AgentRegistry()
    reg.register(card("ml", ["Machine Learning"]))
    reg.register(card("etl", ["Spark"]))
    hits = reg.find_by_skill("machine learning")
    assert [a.card.name for a in hits] == ["ml"]
    assert reg.find_by_skill("nothing") == []


def test_persistence_replays_upsert_and_deregister(tmp_path):
    path = tmp_path / "agents.jsonl"
    reg1 = AgentRegistry(persistence_path=path)
    reg1.register(card("a", ["X"]))
    reg1.register(card("b", ["Y"]))
    reg1.deregister("a")
    reg2 = AgentRegistry(persistence_path=path)
    assert [a.card.name for a in reg2.list()] == ["b"]
    assert reg2.get("a") is None


def test_stale_filtering():
    reg = AgentRegistry(stale_after_seconds=-1.0)
    reg.register(card("old", ["Z"]))
    assert reg.list() == []
    assert len(reg.list(include_stale=True)) == 1
