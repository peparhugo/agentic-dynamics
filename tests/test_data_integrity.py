"""Regression guards for the Phase-1 data-integrity remediation.

These assert, at the source level, that the fabrication/duplication
anti-patterns the architecture review flagged (P0-1, P0-2, P0-3) do not
return. They are cheap and run with no external dependencies.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text()


def test_no_duplicate_pricing_in_constants():
    # P0-2: _constants.py must not carry a second PROVIDER_PRICING.
    assert "PROVIDER_PRICING" not in _read("src/agentic_dynamics/core/constants.py")


def test_no_fabricated_pass_rate_in_build_data():
    # P0-1: compute_story_models must never set test_executions_passed ==
    # test_executions_run (nor the old conflated tests_passed == tests_total)
    # or hardcode a 100% pass rate.
    src = _read("scripts/build_data.py")
    assert "all stories passed" not in src
    assert 'pass_rate": f"100%' not in src


def test_story_model_test_counts_use_distinct_scope_names():
    # smaller (c5): the model-card must distinguish the story-level peak test count from
    # the summed session-execution counts, and label the pass rate's weighting — never the
    # conflated tests_total / tests_passed / tests_run triple.
    src = _read("scripts/build_data.py")
    assert '"final_tests_discovered"' in src
    assert '"test_executions_passed"' in src
    assert '"test_executions_run"' in src
    assert '"pass_rate_scope"' in src


def test_basin_cost_fallback_uses_get_pricing():
    # P0-2: basin.py must not hardcode a literal per-token rate.
    src = _read("src/agentic_dynamics/measurement/basin.py")
    assert "0.27" not in src
    assert "get_pricing" in src


def test_no_resurrected_arch_constants_in_build_data():
    # P0-3: build_data.py must not emit the debunked 500B/37B active-param claims.
    src = _read("scripts/build_data.py")
    assert '"claude_active_params"' not in src
    assert '"37B"' not in src


def test_correctness_tag_uses_independent_evaluator():
    # P0-11: game_report.py must tag correctness [M] only when the evaluator is
    # independent, not merely when tests were run (agent-authored tests ≠ [M]).
    src = _read("src/agentic_dynamics/reporting/game_report.py")
    assert "evaluator_independent" in src
    assert "'[M]' if sol.tests_total > 0" not in src


def test_pytest_errors_included_in_total():
    # P0-12: analyze_worktrees.py must count errors in the denominator so an
    # errored run can never report 100%.
    src = _read("scripts/analyze_worktrees.py")
    assert "total = passed + failed + errors" in src


def test_no_cross_experiment_baseline_fallback():
    # P0-8: analyze_worktrees.py must not fall back to "any baseline for the
    # same model" across experiments.
    src = _read("scripts/analyze_worktrees.py")
    assert "any baseline for same model" not in src
    assert "for bk, entry in baseline_index.items():\n            if target in bk" not in src


def test_go_rust_patterns_in_ast_diff():
    # P0-10: commit_analysis.py diff stats must cover Go (func) and Rust (fn).
    src = _read("src/agentic_dynamics/measurement/commit_analysis.py")
    assert r"\n\+func " in src
    assert r"\n\+fn " in src
    assert r"\n\+use " in src
