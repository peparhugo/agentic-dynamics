"""Tests for the spec → DAG compiler and its phases (matrix, compare, evaluate)."""

import math

import pytest

from instrument.compile_experiment import (
    DAG,
    MEASUREMENT_RULES,
    Phase,
    SpecError,
    compare_arms,
    compile_spec,
    evaluate_rules,
    experiment_matrix,
    first_pass_quality,
)
from instrument.experiment_spec import (
    ExperimentSpec,
    Factor,
    RuleSpec,
    Workflow,
)


def _spec(**kwargs) -> ExperimentSpec:
    defaults = dict(
        name="routing_regret_under_degradation",
        question="q",
        version="0.2",
        workflow=Workflow("story"),
        factors=[Factor("model", ["flash", "pro"])],
        design="factorial",
    )
    defaults.update(kwargs)
    return ExperimentSpec(**defaults)


def test_compile_spec_emits_full_dag():
    spec = _spec()
    dag = compile_spec(spec)
    assert dag.names() == ["validate", "cells", "execute", "measure", "compare", "writeup", "adapt"]
    assert dag.edges[0] == ("validate", "cells")
    assert dag.edges[-1] == ("writeup", "adapt")
    assert dag.feedback == [("adapt", "cells")]
    assert dag.topological_order() == dag.names()


def test_compile_spec_refuses_unmet_requires(tmp_path):

    from instrument.experiment_spec import ExperimentSpec

    p = tmp_path / "s.yaml"
    p.write_text(
        "name: s\nquestion: q\nversion: '1'\n"
        "workflow: {kind: story}\n"
        "factors: [{name: model, levels: [a]}]\n"
        "design: factorial\n"
        "rules:\n"
        "  - {name: model_cascade, plane: control, evidence_class: '[H]', requires: [next_gen_signal]}\n"
    )
    spec = ExperimentSpec.from_yaml(p)
    with pytest.raises(SpecError) as exc:
        compile_spec(spec)
    assert "next_gen_signal" in str(exc.value)


def test_experiment_matrix_cross_product():
    spec = _spec(
        factors=[
            Factor("model", ["flash", "pro"]),
            Factor("condition", ["clean", "bad_seed", "early_degrade"]),
        ]
    )
    cells = experiment_matrix(spec)
    assert len(cells) == 6
    assert all("cell_id" in c for c in cells)
    models = {c["model"] for c in cells}
    assert models == {"flash", "pro"}
    assert all(c["condition"] in {"clean", "bad_seed", "early_degrade"} for c in cells)


def test_experiment_matrix_skips_inactive_factors():
    spec = _spec(
        factors=[
            Factor("model", ["flash", "pro"]),
            Factor("policy", ["cheapest", "dynamics"], active=False),
        ]
    )
    cells = experiment_matrix(spec)
    assert len(cells) == 2
    assert all("policy" not in c for c in cells)


def test_compare_arms_regret():
    results = [
        {"policy": "cheapest", "cost": 0.01, "correctness": 0.70},
        {"policy": "cheapest", "cost": 0.02, "correctness": 0.70},
        {"policy": "premium_static", "cost": 0.10, "correctness": 0.95},
        {"policy": "premium_static", "cost": 0.12, "correctness": 0.95},
    ]
    out = compare_arms(
        results,
        arm_factor="policy",
        loss={"cost": 1.0, "quality": -5.0},
    )
    assert out["best_arm"] == "premium_static"
    assert out["regrets"]["premium_static"] == 0.0
    assert out["regrets"]["cheapest"] == pytest.approx(1.155, abs=1e-3)
    assert out["arms"]["cheapest"]["avg_cost"] == 0.015


def test_compare_arms_empty_results():
    out = compare_arms([], arm_factor="policy", loss={"cost": 1.0})
    assert out["best_arm"] is None
    assert out["regrets"] == {}


def test_first_pass_quality():
    attempts = [
        {"attempt_number": 1, "accepted": True},
        {"attempt_number": 1, "accepted": False},
        {"attempt_number": 2, "accepted": True},
        {"attempt_number": 3, "accepted": True},
    ]
    rr = first_pass_quality(attempts)
    assert rr.produces["first_pass_rate"] == 0.25
    assert rr.produces["accepted_outcome"] == 0.75
    assert rr.evidence_class == "[M]"


def test_grit_returns_unmeasured_when_attempts_lack_inputs():
    # Grit(s) = P(test_executed_success | perturbation_strength=s). The inputs are now
    # ledger-measured (re-admitted by the validator), but a specific attempts list that
    # lacks those fields still yields an explicit unmeasured result — never a
    # "completed/n" proxy.
    assert "grit" in MEASUREMENT_RULES
    rr = MEASUREMENT_RULES["grit"]([{"attempt_number": 1, "completed": True}])
    assert math.isnan(rr.metric)
    assert rr.uncertainty == 1.0
    assert rr.produces == {}


def test_grit_computes_operational_definition():
    grit_fn = MEASUREMENT_RULES["grit"]
    attempts = [
        # baseline s=0: all succeed, cost 1.0
        {"perturbation_strength": 0.0, "test_executed_success": True, "cost": 1.0},
        {"perturbation_strength": 0.0, "test_executed_success": True, "cost": 1.0},
        # s=0.5: half succeed, cost 2.0
        {"perturbation_strength": 0.5, "test_executed_success": True, "cost": 2.0},
        {"perturbation_strength": 0.5, "test_executed_success": False, "cost": 2.0},
    ]
    rr = grit_fn(attempts)
    assert rr.produces["grit"][0.0] == 1.0
    assert rr.produces["grit"][0.5] == 0.5
    assert rr.produces["retention"][0.5] == 0.5
    # retention curve: R(0)=1.0, R(0.5)=0.5 → trapezoid over [0, 0.5] = (1.0+0.5)/2*0.5
    assert rr.produces["grit_auc"] == pytest.approx(0.375, abs=1e-3)
    # recovery premium: successful perturbed (cost 2.0) / successful baseline (cost 1.0)
    assert rr.produces["recovery_premium"] == 2.0


def test_evaluate_rules_runs_measurement_rules_only():
    spec = _spec(
        rules=[
            RuleSpec("first_pass_quality", "measurement", "[M]"),
            RuleSpec("grit", "measurement", "[M]"),
            RuleSpec("model_cascade", "control", "[H]", requires=["confidence"]),
        ]
    )
    attempts = [
        {"attempt_number": 1, "accepted": True, "completed": True},
        {"attempt_number": 2, "accepted": True, "completed": True},
    ]
    results = evaluate_rules(spec, attempts)
    assert len(results) == 2
    by_name = {r.rule: r for r in results}
    assert by_name["first_pass_quality"].produces["first_pass_rate"] == 0.5
    # grit has a grounded implementation but the ledger lacks its inputs → unmeasured
    assert math.isnan(by_name["grit"].metric)
    assert by_name["grit"].uncertainty == 1.0


def test_evaluate_rules_missing_implementation_is_unmeasured():
    spec = _spec(
        rules=[RuleSpec("outcome_multiplier", "measurement", "[P]", produces=["net_value"])]
    )
    results = evaluate_rules(spec, [])
    assert len(results) == 1
    assert math.isnan(results[0].metric)
    assert results[0].uncertainty == 1.0
    assert results[0].produces == {}


def test_measurement_rules_registry_has_first_pass_and_grit():
    assert "first_pass_quality" in MEASUREMENT_RULES
    assert "grit" in MEASUREMENT_RULES


def test_dag_topological_order_is_stable():
    dag = DAG(
        phases=[Phase("a", "a"), Phase("b", "b"), Phase("c", "c")],
        edges=[("a", "b"), ("b", "c")],
    )
    assert dag.topological_order() == ["a", "b", "c"]
