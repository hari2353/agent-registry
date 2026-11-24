from agent_registry.tool_eval import tool_use_score


def test_perfect_match():
    gold = [{"tool": "search", "args": {"q": "x"}}]
    pred = [{"tool": "search", "args": {"q": "x"}}]
    out = tool_use_score(pred, gold)
    assert out["precision"] == 1.0
    assert out["recall"] == 1.0
    assert out["f1"] == 1.0
    assert out["exact_match"] is True


def test_missing_call_lowers_recall():
    gold = [
        {"tool": "search", "args": {"q": "x"}},
        {"tool": "read", "args": {"id": "1"}},
    ]
    pred = [{"tool": "search", "args": {"q": "x"}}]
    out = tool_use_score(pred, gold)
    assert out["recall"] == 0.5
    assert out["precision"] == 1.0


def test_extra_call_lowers_precision():
    gold = [{"tool": "search", "args": {"q": "x"}}]
    pred = [
        {"tool": "search", "args": {"q": "x"}},
        {"tool": "read", "args": {"id": "1"}},
    ]
    out = tool_use_score(pred, gold)
    assert out["precision"] == 0.5
    assert out["recall"] == 1.0


def test_arg_mismatch_is_not_a_match():
    gold = [{"tool": "search", "args": {"q": "x"}}]
    pred = [{"tool": "search", "args": {"q": "y"}}]
    out = tool_use_score(pred, gold)
    assert out["matched"] == 0
    assert out["f1"] == 0.0


def test_empty_both_is_perfect():
    out = tool_use_score([], [])
    assert out["precision"] == 1.0
    assert out["recall"] == 1.0
    assert out["exact_match"] is True


def test_type_check():
    try:
        tool_use_score("nope", [])
    except TypeError:
        pass
    else:
        raise AssertionError("non-list accepted")
