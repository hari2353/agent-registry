from agent_registry.benchmark import BenchmarkCase, run_benchmark

CASES = [
    BenchmarkCase("greet", "say hi", "chat", ("hello",)),
    BenchmarkCase("safe", "summarize", "chat", ("summary",), ("password",)),
    BenchmarkCase("skill", "find python", "discovery", ("python",)),
]


def test_all_cases_pass():
    out = run_benchmark(CASES, lambda prompt: {
        "say hi": "Hello there",
        "summarize": "Summary ready",
        "find python": "Python role",
    }[prompt])
    assert out["passed"] == 3
    assert out["pass_rate"] == 1.0
    assert out["failures"] == []
    assert out["categories"]["chat"]["pass_rate"] == 1.0


def test_missing_term_fails_with_reason():
    out = run_benchmark(
        CASES, lambda prompt: "Hello summary password" if prompt == "summarize" else "x"
    )
    failures = {f["case_id"]: f for f in out["failures"]}
    assert "greet" in failures
    assert "missing: hello" in failures["greet"]["reason"]
    assert "forbidden: password" in failures["safe"]["reason"]


def test_matching_is_case_and_space_insensitive():
    case = BenchmarkCase("c", "q", "cat", ("machine learning",))
    out = run_benchmark([case], lambda prompt: "MACHINE   Learning")
    assert out["passed"] == 1


def test_latency_budget_is_enforced():
    case = BenchmarkCase("c", "q", "cat", ("ok",), max_latency_s=0.5)
    ticks = iter([0.0, 0.6])
    out = run_benchmark([case], lambda prompt: "ok", clock=lambda: next(ticks))
    assert out["passed"] == 0
    assert "latency" in out["failures"][0]["reason"]


def test_agent_exception_is_a_failed_case():
    out = run_benchmark([CASES[0]], lambda prompt: (_ for _ in ()).throw(RuntimeError("down")))
    assert out["passed"] == 0
    assert "error: down" in out["failures"][0]["reason"]


def test_category_slices():
    out = run_benchmark(CASES, lambda prompt: "hello python")
    assert out["categories"]["chat"]["total"] == 2
    assert out["categories"]["chat"]["passed"] == 1
    assert out["categories"]["discovery"]["pass_rate"] == 1.0


def test_empty_cases_rejected():
    try:
        run_benchmark([], lambda prompt: "")
    except ValueError:
        pass
    else:
        raise AssertionError("empty case list accepted")
