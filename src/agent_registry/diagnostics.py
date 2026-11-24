"""Agent repair contract: a stable code, a plain-language fix, and a docs
pointer on every expected failure. Modelled on Solid 2.0's agent diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass

DOCS = "docs/diagnostics.md"

CATALOG: dict[str, str] = {
    "REG_BAD_AGENT_URL": "register an http(s) agent URL; file/ftp schemes are refused",
    "REG_PROBE_HTTP_STATUS": "make the agent serve /.well-known/agent-card.json with a 2xx",
    "REG_PROBE_BODY_TOO_LARGE": "serve a card under the 64KB cap",
    "REG_PROBE_INVALID_JSON": "serve a JSON object at /.well-known/agent-card.json",
    "REG_PROBE_UNREACHABLE": "check the agent is running and the registered URL is reachable",
    "REG_UNKNOWN_AGENT": "list registered agents with GET /agents",
    "REG_TOPIC_REQUIRED": "send a non-blank topic",
    "REG_ENGINE_UNREACHABLE": "start skills-engine or check its base URL",
}


@dataclass(frozen=True)
class Diagnostic(ValueError):
    """A caller-fixable failure. Inherits ValueError so existing handlers work."""

    code: str
    message: str

    def __post_init__(self) -> None:
        if self.code not in CATALOG:
            raise ValueError(f"undocumented diagnostic code: {self.code}")

    @property
    def hint(self) -> str:
        return CATALOG[self.code]

    @property
    def docs(self) -> str:
        return f"{DOCS}#{self.code.casefold()}"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "docs": self.docs,
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} (fix: {self.hint}) (docs: {self.docs})"
