"""Tests for ExperimentSpec dataclasses, YAML loading, and the requires/produces validator."""

from instrument.experiment_spec import (
    LEDGER_FIELDS,
    ComparisonSpec,
    ExperimentSpec,
    Factor,
    MetricSpec,
    RuleSpec,
    Workflow,
    load_spec,
    validate_rules,
    validate_spec,
)

FLAGSHIP_YAML = """\
name: routing_regret_under_degradation
question: >-
  Does a dynamics controller that escalates on measured confidence beat
  static cheapest/premium policies in accepted-cost-per-outcome?
version: "0.2"
workflow:
  kind: story
  params: {stories: [task_manager_api, static_site_gen, notification_service]}
factors:
  - {name: model, levels: [flash, luna, pro, haiku, terra, sonnet, sol]}
  - {name: condition, levels: [clean, bad_seed, early_degrade, late_degrade]}
  - {name: policy, levels: [cheapest, premium_static, quality_cascade, dynamics]}
design: factorial
rules:
  - {name: first_pass_quality, plane: measurement, evidence_class: "[M]",
     requires: [attempt_number, accepted, evaluator_independent],
     produces: [first_pass_rate, accepted_outcome]}
  - {name: grit, plane: measurement, evidence_class: "[M]",
     requires: [perturbation_strength, test_executed_success, condition],
     produces: [grit, retention, grit_auc, recovery_premium]}
  - {name: outcome_multiplier, plane: measurement, evidence_class: "[P]",
     requires: [value, rework_cost, reuse_value],
     produces: [net_value]}
  - {name: model_cascade, plane: control, evidence_class: "[H]",
     requires: [confidence],
     produces: [escalation_decision]}
  - {name: budget_ceiling, plane: control, evidence_class: "[P]",
     requires: [budget, forecast_cost, actual_cost],
     produces: [admit_or_halt]}
metrics:
  - {name: cost_per_accepted_outcome, agg: mean, over: outcome}
  - {name: first_pass_rate, agg: ratio, over: job}
comparison:
  kind: routing_regret
  arm_factor: policy
  loss: {cost: 1.0, quality: 5.0, sla: 2.0, value: -3.0}
writeup: {format: lab_book, sections: [hypothesis, method, results, interpretation]}
stop: {budget_usd: 40.0, uncertainty_threshold: 0.05}
adapt: {strategy: coordinate_descent, selection: highest_regret}
"""


def _write_yaml(tmp_path):
    p = tmp_path / "routing_regret.yaml"
    p.write_text(FLAGSHIP_YAML)
    return p


def test_load_spec_round_trip(tmp_path):
    spec = load_spec(_write_yaml(tmp_path))
    assert spec.name == "routing_regret_under_degradation"
    assert spec.workflow.kind == "story"
    assert [f.name for f in spec.factors] == ["model", "condition", "policy"]
    assert spec.factors[2].levels == ["cheapest", "premium_static", "quality_cascade", "dynamics"]
    assert len(spec.rules) == 5
    assert spec.comparison.arm_factor == "policy"
    assert spec.adapt.strategy == "coordinate_descent"


def test_validate_rules_reports_unmet_requires(tmp_path):
    spec = load_spec(_write_yaml(tmp_path))
    errors = validate_rules(spec)
    # Three unmet fields: grit needs perturbation_strength + test_executed_success,
    # model_cascade needs confidence. One error per unmet field.
    assert len(errors) == 3
    assert any("model_cascade" in e and "confidence" in e for e in errors)
    assert any("grit" in e and "perturbation_strength" in e for e in errors)
    assert any("grit" in e and "test_executed_success" in e for e in errors)


def test_round_trip_to_dict_from_dict(tmp_path):
    spec = ExperimentSpec.from_yaml(_write_yaml(tmp_path))
    restored = ExperimentSpec.from_dict(spec.to_dict())
    assert restored == spec


def test_confidence_is_not_a_ledger_field():
    # The load-bearing gap: model_cascade needs confidence, grit needs
    # perturbation_strength + test_executed_success — none are measured yet.
    assert "confidence" not in LEDGER_FIELDS
    assert "perturbation_strength" not in LEDGER_FIELDS
    assert "test_executed_success" not in LEDGER_FIELDS
    assert "attempt_number" in LEDGER_FIELDS
    assert "budget" in LEDGER_FIELDS


def test_validator_refuses_unmeasured_rules(tmp_path):
    spec = load_spec(_write_yaml(tmp_path))
    errors = validate_spec(spec)
    assert len(errors) == 3
    assert any("model_cascade" in e and "confidence" in e for e in errors)
    assert any("grit" in e and "perturbation_strength" in e for e in errors)


def test_validator_admits_after_missing_information_instrumented(tmp_path):
    spec = load_spec(_write_yaml(tmp_path))
    spec.rules.insert(
        0,
        RuleSpec("confidence_probe", "measurement", "[M]", requires=["completed"], produces=["confidence"]),
    )
    spec.rules.insert(
        0,
        RuleSpec(
            "success_probe",
            "measurement",
            "[M]",
            requires=["attempt_number"],
            produces=["perturbation_strength", "test_executed_success"],
        ),
    )
    assert validate_spec(spec) == []


def test_validator_accepts_measurement_rules_with_ledger_inputs():
    spec = ExperimentSpec(
        name="x",
        question="q",
        version="1",
        workflow=Workflow("story"),
        factors=[Factor("model", ["a", "b"])],
        design="factorial",
        rules=[
            RuleSpec("first_pass_quality", "measurement", "[M]", requires=["attempt_number", "accepted"]),
        ],
    )
    assert validate_spec(spec) == []


def test_validator_flags_invalid_plane():
    spec = ExperimentSpec(
        name="x",
        question="q",
        version="1",
        workflow=Workflow("story"),
        factors=[Factor("model", ["a", "b"])],
        design="factorial",
        rules=[RuleSpec("bad", plane="side_channel", evidence_class="[H]")],
    )
    errors = validate_spec(spec)
    assert any("side_channel" in e for e in errors)


def test_validator_flags_invalid_evidence_class():
    spec = ExperimentSpec(
        name="x",
        question="q",
        version="1",
        workflow=Workflow("story"),
        factors=[Factor("model", ["a", "b"])],
        design="factorial",
        rules=[RuleSpec("bad", plane="measurement", evidence_class="[Q]")],
    )
    errors = validate_spec(spec)
    assert any("evidence_class" in e for e in errors)


def test_validator_flags_duplicate_rule_names():
    spec = ExperimentSpec(
        name="x",
        question="q",
        version="1",
        workflow=Workflow("story"),
        factors=[Factor("model", ["a", "b"])],
        design="factorial",
        rules=[
            RuleSpec("dup", plane="measurement", evidence_class="[M]"),
            RuleSpec("dup", plane="measurement", evidence_class="[M]"),
        ],
    )
    errors = validate_spec(spec)
    assert any("duplicate" in e for e in errors)


def test_validator_flags_unmeasured_requires():
    spec = ExperimentSpec(
        name="x",
        question="q",
        version="1",
        workflow=Workflow("story"),
        factors=[Factor("model", ["a", "b"])],
        design="factorial",
        rules=[
            RuleSpec(
                "ctrl",
                plane="control",
                evidence_class="[H]",
                requires=["not_a_real_field"],
            )
        ],
    )
    errors = validate_spec(spec)
    assert any("not_a_real_field" in e for e in errors)


def test_validator_resolves_measurement_produces():
    spec = ExperimentSpec(
        name="x",
        question="q",
        version="1",
        workflow=Workflow("story"),
        factors=[Factor("model", ["a", "b"])],
        design="factorial",
        rules=[
            RuleSpec("probe", plane="measurement", evidence_class="[M]", produces=["confidence"]),
            RuleSpec("ctrl", plane="control", evidence_class="[H]", requires=["confidence"]),
        ],
    )
    assert validate_spec(spec) == []


def test_validator_flags_comparison_arm_not_a_factor():
    spec = ExperimentSpec(
        name="x",
        question="q",
        version="1",
        workflow=Workflow("story"),
        factors=[Factor("model", ["a", "b"])],
        design="factorial",
        comparison=ComparisonSpec("routing_regret", arm_factor="policy"),
    )
    errors = validate_spec(spec)
    assert any("arm_factor" in e for e in errors)


def test_validator_flags_invalid_metric_agg():
    spec = ExperimentSpec(
        name="x",
        question="q",
        version="1",
        workflow=Workflow("story"),
        factors=[Factor("model", ["a", "b"])],
        design="factorial",
        metrics=[MetricSpec("m", agg="median", over="job")],
    )
    errors = validate_spec(spec)
    assert any("median" in e for e in errors)


def test_workflow_default_params_and_factor_current():
    wf = Workflow("task")
    assert wf.params == {}
    f = Factor("seed", ["1", "2"], current="1")
    assert f.current == "1"
    assert f.to_dict()["current"] == "1"


def test_stop_and_writeup_defaults():
    spec = ExperimentSpec(
        name="x",
        question="q",
        version="1",
        workflow=Workflow("story"),
        factors=[Factor("model", ["a"])],
        design="factorial",
    )
    assert spec.stop.budget_usd is None
    assert spec.adapt.strategy == "manual"
    assert spec.writeup is None
