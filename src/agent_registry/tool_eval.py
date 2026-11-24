"""Tool-use evaluation (cross-pollinated from cloud agent-skill benchmarks).

Scores whether an agent invoked the expected tools with the expected
arguments, independent of its final text. Pure, deterministic, no judge model.
"""

from __future__ import annotations


def _key(call: dict) -> tuple:
    tool = str(call.get("tool", call.get("name", "")))
    args = call.get("args", call.get("arguments", {})) or {}
    # Canonicalize arg keys for comparison.
    arg_items = tuple(sorted((str(k), str(v)) for k, v in args.items()))
    return (tool, arg_items)


def tool_use_score(predicted: list[dict], gold: list[dict]) -> dict:
    """Precision/recall/F1 over predicted vs gold tool calls (multiset)."""
    if not isinstance(predicted, list) or not isinstance(gold, list):
        raise TypeError("predicted and gold must be lists")
    pred_keys = [_key(c) for c in predicted]
    gold_keys = [_key(c) for c in gold]

    # Multiset intersection.
    from collections import Counter

    pred_counter = Counter(pred_keys)
    gold_counter = Counter(gold_keys)
    matched = sum((pred_counter & gold_counter).values())

    precision = (
        matched / len(pred_keys) if pred_keys else (1.0 if not gold_keys else 0.0)
    )
    recall = matched / len(gold_keys) if gold_keys else (1.0 if not pred_keys else 0.0)
    f1 = (
        (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    )
    exact = pred_keys == gold_keys and len(pred_keys) == len(gold_keys)
    return {
        "predicted": len(pred_keys),
        "gold": len(gold_keys),
        "matched": matched,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "exact_match": exact,
    }
