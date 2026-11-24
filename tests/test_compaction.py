"""Op-log compaction (steal item 5).

The append-only JSONL op-log grows forever — every heartbeat is a full
agent dump. Consul's answer is snapshots: periodically rewrite the log as
one record per live agent. compact() does exactly that, atomically
(temp file + os.replace), and auto-triggers after compact_after appends.

Tradeoff, stated plainly: compaction truncates the event history with it
(history replays from the log), so it defaults to 1000 ops — a local
fleet's history window stays large, disk stays bounded.
"""

import json

import pytest


def _mk(tmp_path, **kw):
    from agent_registry.registry import AgentRegistry

    return AgentRegistry(persistence_path=tmp_path / "a.jsonl", **kw)


def _card(name):
    from agent_registry.models import AgentCard

    return AgentCard(name=name, url=f"http://{name}.local", skills=[])


def test_manual_compact_snapshots_live_state(tmp_path):
    reg = _mk(tmp_path)
    reg.register(_card("a"))
    reg.register(_card("b"))
    for _ in range(3):
        reg.heartbeat("a")
    reg.deregister("b")

    lines_before = len((tmp_path / "a.jsonl").read_text().splitlines())
    written = reg.compact()

    assert written == 1  # only live agent a
    lines = (tmp_path / "a.jsonl").read_text().splitlines()
    assert len(lines) == 1 and lines_before == 6

    reg2 = _mk(tmp_path)  # replay == state
    assert reg2.get("a") is not None and reg2.get("b") is None
    assert reg2.get("a").registered_at == reg.get("a").registered_at


def test_auto_compact_after_threshold(tmp_path):
    reg = _mk(tmp_path, compact_after=4)
    reg.register(_card("a"))
    for _ in range(3):
        reg.heartbeat("a")  # 4th append triggers
    assert len((tmp_path / "a.jsonl").read_text().splitlines()) == 1
    assert reg.get("a") is not None


def test_compact_preserves_probe_fields(tmp_path):
    reg = _mk(tmp_path)
    reg.register(_card("a"))
    reg.record_probe(
        "a",
        {
            "verified": True,
            "error": None,
            "checked": ["name"],
            "mismatched": [],
            "fetched_at": "now",
        },
    )
    reg.compact()
    reg2 = _mk(tmp_path)
    assert reg2.get("a").verified is True
    assert reg2.get("a").probe["checked"] == ["name"]


def test_compact_without_persistence_is_a_noop():
    from agent_registry.registry import AgentRegistry

    reg = AgentRegistry()  # no persistence_path
    reg.register(_card("a"))
    assert reg.compact() == 0  # no crash, nothing written


def test_compaction_keeps_append_working(tmp_path):
    reg = _mk(tmp_path, compact_after=2)
    reg.register(_card("a"))
    reg.register(_card("b"))  # triggers compaction
    reg.register(_card("c"))  # appends after compact
    reg2 = _mk(tmp_path)
    assert {n for n in ("a", "b", "c") if reg2.get(n)} == {"a", "b", "c"}
