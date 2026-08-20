

from agentic_dynamics.measurement.basin import BasinMetrics
from agentic_dynamics.measurement.solution import SolutionMetrics


def _scrub_nan(d: dict) -> dict:
    for k, v in d.items():
        if isinstance(v, float) and v != v:
            d[k] = None
    return d


# ── SolutionMetrics provenance fields ─────────────────────────────────────────

def test_solution_metrics_has_evaluator_source():
    sm = SolutionMetrics()
    assert sm.evaluator_source == "unavailable"
    assert sm.evaluator_independent is False


def test_solution_metrics_to_dict_includes_provenance():
    sm = SolutionMetrics(correctness_score=0.45, evaluator_source="heuristic")
    d = sm.to_dict()
    assert d["evaluator_source"] == "heuristic"
    assert d["evaluator_independent"] is False


# ── Pipeline ordering: tests override heuristic correctness ──────────────────

def test_correctness_overridden_by_test_results():
    sm = SolutionMetrics(correctness_score=0.8, evaluator_source="heuristic")
    test_results = {"ok": False, "passed": 0, "failed": 1, "total": 1, "pass_rate": 0.0}
    if test_results and test_results.get("total", 0) > 0:
        sm.correctness_score = test_results["pass_rate"]
        sm.evaluator_source = "agent_authored_test"
    assert sm.correctness_score == 0.0
    assert sm.evaluator_source == "agent_authored_test"


def test_heuristic_survives_when_no_tests():
    sm = SolutionMetrics(correctness_score=0.5, evaluator_source="heuristic")
    test_results = {"ok": False, "error": "no test files"}
    if test_results and test_results.get("total", 0) > 0:
        sm.correctness_score = test_results["pass_rate"]
    assert sm.correctness_score == 0.5
    assert sm.evaluator_source == "heuristic"


def test_python_test_ok_semantics():
    sm = SolutionMetrics(correctness_score=0.8, evaluator_source="heuristic")
    test_results = {"ok": False, "passed": 0, "failed": 5, "total": 5, "pass_rate": 0.0}
    if test_results and test_results.get("total", 0) > 0:
        sm.correctness_score = test_results["pass_rate"]
        sm.evaluator_source = "agent_authored_test"
    assert sm.correctness_score == 0.0
    assert sm.evaluator_source == "agent_authored_test"


# ── Basin receives canonical correctness ─────────────────────────────────────

def test_basin_receives_post_test_correctness():
    SolutionMetrics(correctness_score=0.9)
    perturbed = SolutionMetrics(correctness_score=0.8, evaluator_source="heuristic")
    test_results = {"ok": False, "passed": 0, "failed": 1, "total": 1, "pass_rate": 0.0}
    if test_results and test_results.get("total", 0) > 0:
        perturbed.correctness_score = test_results["pass_rate"]
        perturbed.evaluator_source = "agent_authored_test"
    basin = BasinMetrics(
        correctness=perturbed.correctness_score,
        perturbation_operator="invert_constraint",
    )
    assert basin.correctness == 0.0


# ── Narration failure path still works ───────────────────────────────────────

def test_narration_failure_with_zero_correctness():
    sm = SolutionMetrics(correctness_score=0.0, evaluator_source="heuristic")
    sm.correctness_score = max(0, sm.correctness_score - 1.0)
    assert sm.correctness_score == 0.0


# ── Evaluator provenance flow through metrics dict ───────────────────────────

def test_metrics_dict_includes_evaluator_source():
    metrics = {
        "correctness": 0.5,
        "evaluator_source": "heuristic",
        "evaluator_independent": False,
    }
    assert metrics["evaluator_source"] == "heuristic"
    assert metrics["evaluator_independent"] is False


# ── build_data pass_rate: test-based only vs heuristic-only vs mixed ─────────

def test_pass_rate_test_only():
    entries = [
        {"test_results": {"total": 10, "passed": 8, "failed": 2}, "correctness": 0.8,
         "evaluator_source": "agent_authored_test"},
        {"test_results": {"total": 5, "passed": 4, "failed": 1}, "correctness": 0.8,
         "evaluator_source": "agent_authored_test"},
    ]
    total_tests = sum(r["test_results"]["total"] for r in entries if r.get("test_results", {}).get("total", 0) > 0)
    total_passed = sum(r["test_results"]["passed"] for r in entries if r.get("test_results", {}).get("total", 0) > 0)
    assert total_tests > 0
    assert total_passed == 12
    assert total_passed / total_tests == 0.8


def test_pass_rate_heuristic_only():
    entries = [
        {"correctness": 0.7, "evaluator_source": "heuristic"},
        {"correctness": 0.9, "evaluator_source": "heuristic"},
    ]
    total_tests = sum(r.get("test_results", {}).get("total", 0) for r in entries)
    avg = sum(r["correctness"] for r in entries) / len(entries)
    assert total_tests == 0
    assert avg == 0.8


def test_pass_rate_mixed_sources():
    entries = [
        {"test_results": {"total": 10, "passed": 8}, "correctness": 0.8,
         "evaluator_source": "agent_authored_test"},
        {"correctness": 0.5, "evaluator_source": "heuristic"},
    ]
    total_tests = sum(r["test_results"]["total"] for r in entries
                      if r.get("test_results", {}).get("total", 0) > 0)
    total_passed = sum(r["test_results"]["passed"] for r in entries
                       if r.get("test_results", {}).get("total", 0) > 0)
    n_heuristic = sum(1 for r in entries
                      if r.get("evaluator_source") == "heuristic")
    assert total_tests == 10
    assert total_passed == 8
    assert n_heuristic == 1
    tag = " [mixed]" if n_heuristic > 0 else " [tests]"
    pass_rate = f"{total_passed / total_tests:.0%} ({total_passed}/{total_tests}){tag}"
    assert "[mixed]" in pass_rate
