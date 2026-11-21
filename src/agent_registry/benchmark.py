"""Deterministic agent benchmark harness, following QuArch's eval shape.

Cross-pollinated from harvard-edge/quarch-eval: a fixed case set, a parser
per response, per-category scores, and bounded failure detail. Scoring is
rule-based (required/forbidden terms), so the same run is reproducible and
no judge model is on the path.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

_MAX_FAILURES = 20
_P95 = 0.95


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    prompt: str
    category: str
    required_terms: tuple[str, ...]
    forbidden_terms: tuple[str, ...] = ()
    max_latency_s: float | None = None

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.prompt.strip() or not self.category.strip():
            raise ValueError("case_id, prompt and category must be non-empty")
        if not self.required_terms or any(not t.strip() for t in self.required_terms):
            raise ValueError("required_terms must contain non-empty terms")
        if any(not t.strip() for t in self.forbidden_terms):
            raise ValueError("forbidden_terms must not contain blank terms")
        if self.max_latency_s is not None and self.max_latency_s <= 0:
            raise ValueError("max_latency_s must be positive")


@dataclass(frozen=True, slots=True)
class CaseResult:
    case_id: str
    category: str
    passed: bool
    latency_s: float
    reason: str


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _score(case: BenchmarkCase, output: str, latency_s: float) -> CaseResult:
    text = _normalize(output)
    missing = [t for t in case.required_terms if _normalize(t) not in text]
    banned = [t for t in case.forbidden_terms if _normalize(t) in text]
    if missing:
        reason = "missing: " + ", ".join(missing[:5])
    elif banned:
        reason = "forbidden: " + ", ".join(banned[:5])
    elif case.max_latency_s is not None and latency_s > case.max_latency_s:
        reason = f"latency {latency_s:.3f}s > {case.max_latency_s}s"
    else:
        reason = "passed"
    return CaseResult(
        case_id=case.case_id,
        category=case.category,
        passed=reason == "passed",
        latency_s=round(latency_s, 4),
        reason=reason,
    )


def run_benchmark(
    cases: list[BenchmarkCase],
    call: Callable[[str], str],
    *,
    clock: Callable[[], float] = time.perf_counter,
) -> dict:
    """Run every case, returning pass rate, category slices and bounded failures."""
    if not cases:
        raise ValueError("cases must be non-empty")

    results: list[CaseResult] = []
    for case in cases:
        started = clock()
        try:
            output = call(case.prompt)
        except Exception as exc:  # a broken agent is a failed case, not a crash
            output = ""
            latency = clock() - started
            results.append(CaseResult(case.case_id, case.category, False,
                                      round(latency, 4), f"error: {exc}"))
            continue
        results.append(_score(case, str(output), clock() - started))

    categories: dict[str, dict] = {}
    for result in results:
        bucket = categories.setdefault(result.category, {"total": 0, "passed": 0})
        bucket["total"] += 1
        bucket["passed"] += int(result.passed)
    for bucket in categories.values():
        bucket["pass_rate"] = round(bucket["passed"] / bucket["total"], 4)

    latencies = sorted(r.latency_s for r in results)
    index = min(int(round((len(latencies) - 1) * _P95)), len(latencies) - 1)
    passed = sum(1 for r in results if r.passed)
    failures = [r for r in results if not r.passed][:_MAX_FAILURES]
    return {
        "total": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 4),
        "p95_latency_s": latencies[index],
        "categories": dict(sorted(categories.items())),
        "failures": [
            {"case_id": r.case_id, "category": r.category,
             "latency_s": r.latency_s, "reason": r.reason}
            for r in failures
        ],
    }
