import os
import re

import httpx

from .registry import AgentRegistry

ENGINE_URL = os.getenv("SKILLS_ENGINE_URL", "http://127.0.0.1:8000")

# ── fuzzy skill matching (Agennect's semantic search, 80% via tokens) ─────────
# Exact casefold matching made an agent whose card says "Graph orchestration
# with LangGraph" invisible to the skill "orchestration". Token overlap over
# the card's own text gets most of the way with zero new dependencies.
# Exact = 1.0, partial >= 0.5 (labelled), below that the skill stays a gap.

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.]*")
_MATCH_STOP = frozenset("the a an and or of for with in on to at".split())
_PARTIAL_THRESHOLD = 0.5


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall((text or "").casefold())
            if t not in _MATCH_STOP}


def match_score(skill: str, card) -> float:
    """Fraction of the skill's tokens present in the card's text (name,
    description, skill names/descriptions, capabilities)."""
    skill_tokens = _tokens(skill)
    if not skill_tokens:
        return 0.0
    card_tokens = _tokens(card.name) | _tokens(card.description)
    for s in card.skills:
        card_tokens |= _tokens(s.name) | _tokens(s.description)
    card_tokens |= _tokens(" ".join(card.capabilities))
    return round(len(skill_tokens & card_tokens) / len(skill_tokens), 2)


class SkillGap(Exception):
    pass


def infer_required_skills(text: str, context_type: str = "job_description", transport=None) -> list[str]:
    payload = {"text": text, "context_type": context_type}
    if transport is not None:
        return [s["canonical_name"] for s in transport("/v1/skills/infer", payload)["skills"]]
    resp = httpx.post(f"{ENGINE_URL}/v1/skills/infer", json=payload, timeout=60.0)
    resp.raise_for_status()
    return [s["canonical_name"] for s in resp.json()["skills"]]


def build_brief(registry: AgentRegistry, topic: str, context_type: str = "job_description", engine_transport=None) -> dict:
    required = infer_required_skills(topic, context_type, engine_transport)
    recommended: list[dict] = []
    covered: set[str] = set()
    for skill in required:
        skill_cf = skill.casefold()
        scored = []
        for agent in registry.list():
            score = match_score(skill, agent.card)
            if score < _PARTIAL_THRESHOLD:
                continue
            # confidence is only defined for an exact skill-name entry
            conf = next((s.confidence for s in agent.card.skills
                         if s.name.casefold() == skill_cf), 0.0)
            scored.append((score, conf, agent))
        if not scored:
            continue
        scored.sort(key=lambda t: (-t[0], -t[1], t[2].card.name))
        score, _, best = scored[0]
        # "exact" = the card lists the skill by name; fuzzy text matches are
        # partial even at full token coverage
        exact = any(s.name.casefold() == skill_cf for s in best.card.skills)
        recommended.append({"skill": skill, "agent": best.card.name,
                            "url": best.card.url,
                            "match": "exact" if exact else "partial",
                            "score": score})
        covered.add(skill)
    gaps = [s for s in required if s not in covered]
    pct = round(100 * len(covered) / len(required)) if required else 0
    summary_bits = []
    if recommended:
        summary_bits.append(f"{len(recommended)} of {len(required)} required "
                            f"skills covered by registered agents ({pct}%)")
    else:
        summary_bits.append("no registered agents cover the required skills")
    if gaps:
        summary_bits.append(f"gaps: {', '.join(gaps)}")
    return {
        "topic": topic,
        "required_skills": required,
        "recommended_agents": recommended,
        "skill_gaps": gaps,
        "coverage_pct": pct,
        "summary": "; ".join(summary_bits),
    }
