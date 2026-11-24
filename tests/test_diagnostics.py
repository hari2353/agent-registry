"""Agent repair contract: probe failures and API rejections carry a stable
code, a plain-language fix, and a docs pointer.
"""

import json
from pathlib import Path

import pytest

from agent_registry import probe as probe_module
from agent_registry.diagnostics import CATALOG

ROOT = Path(__file__).resolve().parents[1]

CARD = {
    "name": "resume-screener",
    "url": "http://screener.local/a2a",
    "skills": [{"name": "Python", "confidence": 0.9}],
    "capabilities": ["screening"],
}


def _card():
    from agent_registry.models import AgentCard

    return AgentCard(**CARD)


@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient

    from agent_registry.app import create_app
    from agent_registry.registry import AgentRegistry

    return TestClient(
        create_app(registry=AgentRegistry(persistence_path=tmp_path / "a.jsonl"))
    )


def test_unreachable_probe_carries_code_and_fix() -> None:
    def boom(url, **kw):
        raise RuntimeError("connection refused")

    result = probe_module.probe_agent(_card(), transport=boom)
    assert result["verified"] is False
    assert "connection refused" in result["error"]
    diag = result["diagnostic"]
    assert diag["code"] == "REG_PROBE_UNREACHABLE"
    assert diag["hint"] and diag["docs"].startswith("docs/diagnostics.md#")


def test_bad_scheme_is_a_typed_diagnostic() -> None:
    card = _card()
    card.url = "file:///etc/passwd"
    with pytest.raises(probe_module.Diagnostic) as exc:
        probe_module.probe_agent(card, transport=lambda url, **kw: "{}")
    assert exc.value.code == "REG_BAD_AGENT_URL"
    assert isinstance(exc.value, ValueError)


def test_invalid_json_has_its_own_code() -> None:
    result = probe_module.probe_agent(
        _card(), transport=lambda url, **kw: "not a json object"
    )
    assert result["diagnostic"]["code"] == "REG_PROBE_INVALID_JSON"


def test_http_status_is_not_mislabelled_unreachable(monkeypatch) -> None:
    class Stream:
        status_code = 404

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def iter_bytes(self, cap):
            return iter([b"", b""])

    class Client:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def stream(self, method, url):
            return Stream()

    monkeypatch.setattr(probe_module.httpx, "Client", Client)
    result = probe_module.probe_agent(_card())
    assert result["diagnostic"]["code"] == "REG_PROBE_HTTP_STATUS"


def test_api_unknown_agent_detail_has_code(client) -> None:
    resp = client.post("/agents/ghost/probe")
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["code"] == "REG_UNKNOWN_AGENT"
    assert detail["hint"] and detail["docs"]


def test_api_blank_topic_detail_has_code(client) -> None:
    resp = client.post("/briefs", json={"topic": "  "})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "REG_TOPIC_REQUIRED"


def test_catalog_is_documented() -> None:
    docs = (ROOT / "docs" / "diagnostics.md").read_text(encoding="utf-8")
    missing = [code for code in CATALOG if code not in docs]
    assert not missing, f"undocumented diagnostic codes: {missing}"
