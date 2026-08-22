"""Tests for the task-optimal routing engine."""

from agentic_dynamics.control.routing import compute_routing, normalize_task, recommend_route

DEEPSEEK = "deepseek/deepseek-v4-pro"
CLAUDE = "anthropic/claude-fable-5"


def _entry(model, correctness, cost, experiment="url_shortener"):
    return {"model": model, "correctness": correctness, "cost": cost, "experiment": experiment}


def test_normalize_task_strips_suffixes():
    assert normalize_task("url_shortener_s0.8") == "url_shortener"
    assert normalize_task("task_manager_r2") == "task_manager"
    assert normalize_task("plain_task") == "plain_task"


def test_recommend_route_default_when_cheap_model_qualified():
    entries = [
        _entry(DEEPSEEK, 0.9, 0.001),
        _entry(CLAUDE, 0.92, 0.010),
    ]
    rec = recommend_route("url_shortener", entries)
    assert rec["default_model"] == DEEPSEEK
    assert rec["routing"] == "default"
    assert rec["best_correctness_model"] == CLAUDE


def test_recommend_route_escalates_when_lead_margin_exceeded():
    entries = [
        _entry(DEEPSEEK, 0.72, 0.001),
        _entry(CLAUDE, 0.95, 0.010),
    ]
    rec = recommend_route("url_shortener", entries)
    assert rec["routing"] == "escalate"
    assert rec["escalate_model"] == CLAUDE


def test_recommend_route_single_model_no_escalate():
    rec = recommend_route("url_shortener", [_entry(DEEPSEEK, 0.8, 0.001)])
    assert rec["routing"] == "default"
    assert rec["escalate_model"] == ""


def test_compute_routing_requires_two_models():
    entries = [
        _entry(DEEPSEEK, 0.9, 0.001, "task_a"),
        _entry(CLAUDE, 0.95, 0.010, "task_a"),
        _entry(DEEPSEEK, 0.7, 0.001, "task_b"),  # only one model → skipped
    ]
    out = compute_routing(entries)
    assert out["_meta"]["tasks_analyzed"] == 1
    assert out["per_task"][0]["task"] == "task_a"
    assert f"{DEEPSEEK}_only" in out["strategies"]
    assert "grit_routed" in out["strategies"]


def test_compute_routing_skips_narration_failures():
    entries = [
        _entry(DEEPSEEK, 0.9, 0.001, "task_a"),
        _entry(CLAUDE, 0.95, 0.010, "task_a"),
        {
            "model": CLAUDE,
            "correctness": 0.1,
            "cost": 0.05,
            "experiment": "task_a",
            "narration_failure": True,
        },
    ]
    out = compute_routing(entries)
    assert out["_meta"]["total_valid_entries"] == 2


def test_recommend_route_treats_unavailable_cost_as_unavailable():
    """A model with no captured cost is never a zero-cost efficiency winner.

    DeepSeek's cost is ``None`` (uncaptured) while Claude's is captured: DeepSeek must not
    become ``best_efficiency_model`` via ``correctness / 1e-6``, and must not be the
    ``cheapest_qualified`` default.
    """
    entries = [
        _entry(DEEPSEEK, 0.9, None),
        _entry(CLAUDE, 0.92, 0.010),
    ]
    rec = recommend_route("url_shortener", entries)
    assert rec["models"][DEEPSEEK]["efficiency"] is None
    assert rec["models"][DEEPSEEK]["avg_cost"] is None
    assert rec["best_efficiency_model"] == CLAUDE
    assert rec["default_model"] == CLAUDE


def test_recommend_route_treats_unavailable_outcome_as_unavailable():
    """A model with no measured outcome is not a zero-correctness failure (or a default)."""
    entries = [
        _entry(DEEPSEEK, None, 0.001),
        _entry(CLAUDE, 0.92, 0.010),
    ]
    rec = recommend_route("url_shortener", entries)
    assert rec["models"][DEEPSEEK]["avg_correctness"] is None
    assert rec["best_correctness_model"] == CLAUDE
    assert rec["default_model"] == CLAUDE
