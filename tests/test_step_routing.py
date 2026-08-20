"""Tests for per-step model routing (docs/routing_design.md).

Covers the three-step selection semantics (pin / allowed_models subset / full pool),
preference scoring over measured signals, the model-switch-vs-cache-prefix trade-off,
validator gating (edge_case_coverage / confidence), and graceful cold-start fallback.
"""

from types import SimpleNamespace

from agentic_dynamics.experiment.experiment_spec import ExperimentSpec, Factor, Workflow
from agentic_dynamics.control.signal_store import build_signal_store
from agentic_dynamics.control.step_routing import (
    FORBIDDEN_SIGNALS,
    MEASURED_SIGNALS,
    ModelSignals,
    RouteState,
    RoutingPreferences,
    cache_switch_penalty,
    resolve_pool,
    route_step,
    validate_preferences,
    validate_step_selector,
    validate_workflow_routing,
)
from agentic_dynamics.runtime.workflow_runner import run_workflow

DS = "deepseek/deepseek-v4-pro"
CL = "anthropic/claude-sonnet-5"
FLASH = "deepseek/deepseek-v4-flash"
POOL = [DS, CL, FLASH]


def _prefs(*objectives):
    return RoutingPreferences(objectives=list(objectives))


def _min(signal, weight=1.0):
    from agentic_dynamics.control.step_routing import Objective

    return Objective(signal, "minimize", weight)


def _max(signal, weight=1.0):
    from agentic_dynamics.control.step_routing import Objective

    return Objective(signal, "maximize", weight)


def _sig(model, **kwargs):
    return ModelSignals(model=model, **kwargs)


def _state(pool=POOL, prev_model=None, prev_cache_read_tokens=0):
    return RouteState(pool=pool, prev_model=prev_model, prev_cache_read_tokens=prev_cache_read_tokens)


# ── Three-step selection semantics ──────────────────────────────


def test_pin_wins():
    job = {"model": DS}
    signals = {DS: _sig(DS, cost=0.001, correctness=0.8), CL: _sig(CL, cost=0.0, correctness=1.0)}
    # Even though CL is strictly better on every signal, the pin is honored verbatim.
    assert route_step(job, _state(), _prefs(_min("cost"), _max("correctness")), signals=signals) == DS


def test_allowed_models_restricts_the_subset():
    job = {"allowed_models": [CL, FLASH]}
    # The cheapest model (DS) is in the pool but NOT allowed; the router must ignore it.
    signals = {
        DS: _sig(DS, cost=0.0001),
        CL: _sig(CL, cost=0.01),
        FLASH: _sig(FLASH, cost=0.005),
    }
    chosen = route_step(job, _state(), _prefs(_min("cost")), signals=signals)
    assert chosen in (CL, FLASH)
    assert chosen == FLASH  # cheapest within the allowed subset


def test_unconstrained_draws_from_full_pool():
    job = {}
    signals = {
        DS: _sig(DS, cost=0.001),
        CL: _sig(CL, cost=0.01),
        FLASH: _sig(FLASH, cost=0.0005),
    }
    assert route_step(job, _state(), _prefs(_min("cost")), signals=signals) == FLASH


# ── Preference scoring ──────────────────────────────────────────


def test_lowest_cost_preference_selects_cheapest():
    signals = {DS: _sig(DS, cost=0.001), CL: _sig(CL, cost=0.010)}
    assert route_step({}, _state(), _prefs(_min("cost")), signals=signals) == DS


def test_highest_correctness_preference():
    signals = {DS: _sig(DS, correctness=0.8), CL: _sig(CL, correctness=0.95)}
    assert route_step({}, _state(), _prefs(_max("correctness")), signals=signals) == CL


def test_weighted_preferences_flip_the_choice():
    # cost favors DS, correctness favors CL; weighting correctness higher flips to CL.
    signals = {DS: _sig(DS, cost=0.001, correctness=0.8), CL: _sig(CL, cost=0.010, correctness=0.95)}
    cost_first = _prefs(_min("cost", 1.0), _max("correctness", 0.1))
    assert route_step({}, _state(), cost_first, signals=signals) == DS
    quality_first = _prefs(_min("cost", 0.1), _max("correctness", 1.0))
    assert route_step({}, _state(), quality_first, signals=signals) == CL


# ── edge_case_coverage gating + scoring ─────────────────────────


def test_edge_case_coverage_is_gated_without_measurement_rule():
    prefs = _prefs(_min("cost"), _max("edge_case_coverage"))
    errors = validate_preferences(prefs)  # produced defaults to empty
    assert any("edge_case_coverage" in e and "not produced" in e for e in errors)


def test_edge_case_coverage_admitted_when_produced():
    prefs = _prefs(_min("cost"), _max("edge_case_coverage"))
    assert validate_preferences(prefs, produced={"edge_case_coverage"}) == []


def test_coverage_objective_scores_when_measured():
    signals = {
        DS: _sig(DS, cost=0.001, edge_case_coverage=0.3),
        CL: _sig(CL, cost=0.002, edge_case_coverage=0.9),
    }
    # Coverage weight dominates cost, so the high-coverage model wins despite costing more.
    prefs = _prefs(_min("cost", 1.0), _max("edge_case_coverage", 2.0))
    assert route_step({}, _state(), prefs, signals=signals) == CL


# ── Cache-aware trade-off ───────────────────────────────────────


def test_cache_switch_penalty_uses_deepseek_spread():
    # input $0.66/1M − cache_read $0.022/1M = $0.638/1M.
    penalty = cache_switch_penalty(DS, 1_000_000)
    assert abs(penalty - 0.638) < 1e-6


def test_switch_penalty_keeps_router_on_prior_model():
    # CL is nominally cheaper ($0.0005 vs $0.001), but switching forfeits 10M cache-read
    # tokens (~$6.38) from the prior DeepSeek session → the router stays on DS.
    signals = {DS: _sig(DS, cost=0.001), CL: _sig(CL, cost=0.0005)}
    state = _state(prev_model=DS, prev_cache_read_tokens=10_000_000)
    assert route_step({}, state, _prefs(_min("cost")), signals=signals) == DS


def test_no_prior_prefix_routes_to_cheaper_model():
    # Same signals, but no prior session → no cache to lose → CL (cheaper) wins.
    signals = {DS: _sig(DS, cost=0.001), CL: _sig(CL, cost=0.0005)}
    assert route_step({}, _state(), _prefs(_min("cost")), signals=signals) == CL


# ── Cold start / fallback ───────────────────────────────────────


def test_cold_start_prefers_prior_model_then_first():
    # No signals at all → fall back to the prior model (continuity, free fork).
    state = _state(prev_model=CL)
    assert route_step({}, state, _prefs(_min("cost"))) == CL
    # First step (no prior) → deterministic first pool entry, not random.
    assert route_step({}, _state(), _prefs(_min("cost"))) == POOL[0]


def test_unmeasured_candidate_is_dropped_not_fabricated():
    # CL has no measurement; the router must score DS alone, never invent a number for CL.
    signals = {DS: _sig(DS, cost=0.001)}
    assert route_step({}, _state(), _prefs(_min("cost")), signals=signals) == DS


# ── Validation ──────────────────────────────────────────────────


def test_validate_step_selector_rejects_both_keys():
    errors = validate_step_selector({"model": DS, "allowed_models": [CL]}, POOL)
    assert any("both" in e for e in errors)


def test_validate_step_selector_rejects_empty_and_unknown():
    assert any("non-empty" in e for e in validate_step_selector({"allowed_models": []}, POOL))
    assert any("not in model_pool" in e for e in validate_step_selector({"allowed_models": ["x/y"]}, POOL))
    assert any("not in model_pool" in e for e in validate_step_selector({"model": "x/y"}, POOL))
    assert any("duplicate" in e for e in validate_step_selector({"allowed_models": [DS, DS]}, POOL))


def test_validate_preferences_forbids_confidence():
    errors = validate_preferences(_prefs(_min("confidence")))
    assert any("confidence" in e and "forbidden" in e for e in errors)
    assert "confidence" in FORBIDDEN_SIGNALS
    assert "confidence" not in MEASURED_SIGNALS
    assert "edge_case_coverage" not in MEASURED_SIGNALS


def test_validate_preferences_rejects_unknown_signal_and_bad_direction():
    errors = validate_preferences(_prefs(_min("not_a_signal")))
    assert any("not_a_signal" in e for e in errors)
    from agentic_dynamics.control.step_routing import Objective

    errors = validate_preferences(RoutingPreferences(objectives=[Objective("cost", "sideways", 1.0)]))
    assert any("sideways" in e for e in errors)


def test_validate_workflow_routing_inactive_for_plain_spec():
    spec = ExperimentSpec(
        name="x", question="q", version="1", workflow=Workflow("agent_task", {"phases": [{"name": "a"}]}),
        factors=[Factor("model", ["a"])], design="factorial",
    )
    assert validate_workflow_routing(spec, default_model="a") == []


def test_build_signal_store_aggregates_entries():
    entries = [
        {"model": DS, "correctness": 0.9, "cost": 0.001},
        {"model": DS, "correctness": 0.7, "cost": 0.003},
        {"model": CL, "correctness": 0.95, "cost": 0.010,
         "tokens_cache_read": 500, "tokens_input": 500},
    ]
    store = build_signal_store(entries)
    assert set(store) == {DS, CL}
    assert store[DS].correctness == 0.8
    assert store[DS].cost == 0.002
    assert store[DS].efficiency == 0.8 / 0.002
    assert store[CL].cache_hit_rate == 0.5  # 500 / (500 + 500)
    assert store[DS].cache_hit_rate is None


def test_build_signal_store_aggregates_quality_dimensions():
    # SolutionMetrics quality dimensions are measured today and must be consumable by the
    # router; NaN marks "unmeasured" in _results_summary.json and is skipped, not averaged in.
    # constraint_score is *derived* (constraints_met / constraints_total), not read directly.
    entries = [
        {"model": DS, "constraints_met": 6, "constraints_total": 10, "code_quality_score": 0.8},
        {"model": DS, "constraints_met": 8, "constraints_total": 10,
         "code_quality_score": float("nan")},
        {"model": CL, "novelty_score": 0.4, "composite_score": 0.7},
    ]
    store = build_signal_store(entries)
    assert store[DS].constraint_score == 0.7  # (0.6 + 0.8) / 2
    assert store[DS].code_quality_score == 0.8  # NaN row dropped, not averaged
    assert store[CL].novelty_score == 0.4
    assert store[CL].composite_score == 0.7
    assert store[DS].novelty_score is None


def test_resolve_pool_prefers_model_pool_then_default():
    spec_pool = ExperimentSpec(
        name="x", question="q", version="1",
        workflow=Workflow("agent_task", {"model_pool": [DS, CL]}),
        factors=[Factor("model", ["a"])], design="factorial",
    )
    assert resolve_pool(spec_pool, default_model="z") == [DS, CL]
    spec_plain = ExperimentSpec(
        name="x", question="q", version="1", workflow=Workflow("agent_task"),
        factors=[Factor("model", ["a"])], design="factorial",
    )
    assert resolve_pool(spec_plain, default_model="z") == ["z"]


# ── Integration: run_workflow wires the router ──────────────────


def _fake_agent_recording(seen_models, seen_kwargs):
    def agent(prompt, *, model, backend, workdir, **kwargs):
        seen_models.append(model)
        seen_kwargs.append(kwargs)
        return SimpleNamespace(
            prompt_tokens=1, completion_tokens=1, reasoning_tokens=0, total_tokens=2,
            estimated_cost_usd=0.0, files_created=[], files_modified=[], final_response="",
            ok=True, exit_code=0, error="", session_id="sess_1",
            cache_read_tokens=0, cache_write_tokens=0, cache_hit_rate=0.0,
        )

    return agent


def test_run_workflow_routes_per_step(tmp_path):
    phases = [
        {"name": "pinned", "kind": "agent", "model": DS, "prompt": "a"},
        {"name": "subset", "kind": "agent", "allowed_models": [CL, FLASH], "prompt": "b"},
        {"name": "open", "kind": "agent", "prompt": "c"},
    ]
    spec = ExperimentSpec(
        name="routing_test", question="q", version="1",
        workflow=Workflow("agent_task", {"language": "python", "model_pool": POOL, "phases": phases}),
        factors=[Factor("model", [DS])], design="factorial",
    )
    signals = {
        DS: _sig(DS, cost=0.001, correctness=0.8),
        CL: _sig(CL, cost=0.010, correctness=0.95),
        FLASH: _sig(FLASH, cost=0.0005, correctness=0.7),
    }
    seen_models, seen_kwargs = [], []
    result = run_workflow(
        spec, goal="g", model=DS, workdir=tmp_path, commit=False,
        preferences=_prefs(_min("cost")), signals=signals,
        run_agentic_fn=_fake_agent_recording(seen_models, seen_kwargs),
    )
    assert [p.phase for p in result.phases] == ["pinned", "subset", "open"]
    # pinned → DS; subset → cheapest of {CL, FLASH} = FLASH; open → cheapest of pool = FLASH.
    assert seen_models == [DS, FLASH, FLASH]


def test_run_workflow_forks_when_model_unchanged(tmp_path):
    phases = [
        {"name": "a", "kind": "agent", "prompt": "a"},
        {"name": "b", "kind": "agent", "prompt": "b"},
    ]
    spec = ExperimentSpec(
        name="routing_test", question="q", version="1",
        workflow=Workflow("agent_task", {
            "language": "python", "model_pool": POOL, "fork": True, "phases": phases,
        }),
        factors=[Factor("model", [DS])], design="factorial",
    )
    seen_models, seen_kwargs = [], []
    run_workflow(
        spec, goal="g", model=DS, workdir=tmp_path, commit=False,
        signals={DS: _sig(DS, cost=0.001)},
        run_agentic_fn=_fake_agent_recording(seen_models, seen_kwargs),
    )
    # Both phases route to the same (only measured) model → phase 2 forks from phase 1.
    assert seen_models == [DS, DS]
    assert seen_kwargs[0].get("fork") is None
    assert seen_kwargs[1].get("fork") is True
    assert seen_kwargs[1].get("session_id") == "sess_1"
