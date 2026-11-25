"""LLM evaluation metrics (cross-pollinated from confident-ai/deepeval).

Pure, deterministic, dependency-free approximations of common RAG/agent eval
metrics using token overlap. No judge model required.
"""

from __future__ import annotations


def _tokens(text: str) -> set[str]:
    return set(text.lower().split())


def faithfulness(answer: str, context: str) -> float:
    """Fraction of answer tokens grounded in the context."""
    a = _tokens(answer)
    if not a:
        return 1.0
    c = _tokens(context)
    return round(len(a & c) / len(a), 4)


def answer_relevance(question: str, answer: str) -> float:
    """Token overlap between question and answer (higher = more on-topic)."""
    q = _tokens(question)
    if not q:
        return 0.0
    a = _tokens(answer)
    return round(len(q & a) / len(q), 4)


def context_precision(context: str, ground_truth: str) -> float:
    """Fraction of context tokens that appear in the ground truth."""
    c = _tokens(context)
    if not c:
        return 1.0
    g = _tokens(ground_truth)
    return round(len(c & g) / len(c), 4)


def context_recall(context: str, ground_truth: str) -> float:
    """Fraction of ground-truth tokens covered by the context."""
    g = _tokens(ground_truth)
    if not g:
        return 1.0
    c = _tokens(context)
    return round(len(g & c) / len(g), 4)
