import os

import httpx

from .registry import AgentRegistry

ENGINE_URL = os.getenv("SKILLS_ENGINE_URL", "http://127.0.0.1:8000")


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
        agents = registry.find_by_skill(skill)
        if agents:
            best = sorted(agents, key=lambda a: -next(s.confidence for s in a.card.skills if s.name.casefold() == skill.casefold()))[0]
            recommended.append({"skill": skill, "agent": best.card.name, "url": best.card.url})
            covered.add(skill)
    gaps = [s for s in required if s not in covered]
    summary_bits = []
    if recommended:
        summary_bits.append(f"{len(recommended)} of {len(required)} required skills covered by registered agents")
    else:
        summary_bits.append("no registered agents cover the required skills")
    if gaps:
        summary_bits.append(f"gaps: {', '.join(gaps)}")
    return {
        "topic": topic,
        "required_skills": required,
        "recommended_agents": recommended,
        "skill_gaps": gaps,
        "summary": "; ".join(summary_bits),
    }
