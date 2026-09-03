"""Tests for ExperimentSpec dataclasses, YAML loading, and the requires/produces validator."""

from pathlib import Path

import pytest

from agentic_dynamics.experiment.experiment_spec import (
    LEDGER_FIELDS,
    SPEC_KEYS,
    SPEC_STATUSES,
    ComparisonSpec,
    ExperimentSpec,
    Factor,
    MetricSpec,
    RuleSpec,
    Workflow,
    committed_spec_paths,
    compute_workflow_revision_id,
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


def test_validate_rules_admits_instrumented_arms(tmp_path):
    spec = load_spec(_write_yaml(tmp_path))
    errors = validate_rules(spec)
    # All four formerly-missing fields are now ledger-produced: grit needs
    # perturbation_strength + test_executed_success, model_cascade needs
    # confidence. The flagship spec therefore validates with no unmet requires.
    assert errors == []


def test_round_trip_to_dict_from_dict(tmp_path):
    spec = ExperimentSpec.from_yaml(_write_yaml(tmp_path))
    restored = ExperimentSpec.from_dict(spec.to_dict())
    assert restored == spec


def test_ledger_fields_are_measured():
    # The instrumentation gap is closed: the four fields the control arms consume
    # are now ledger-produced, so the validator admits them.
    assert "confidence" in LEDGER_FIELDS
    assert "perturbation_strength" in LEDGER_FIELDS
    assert "test_executed_success" in LEDGER_FIELDS
    assert "tokens_answer" in LEDGER_FIELDS
    assert "tokens_explanation" in LEDGER_FIELDS
    assert "attempt_number" in LEDGER_FIELDS
    assert "budget" in LEDGER_FIELDS


def test_validator_admits_flagship_spec(tmp_path):
    spec = load_spec(_write_yaml(tmp_path))
    # The flagship spec (grit + model_cascade + dynamics arms) now compiles clean:
    # every requires field is produced by the ledger.
    assert validate_spec(spec) == []


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


# ── Spec lifecycle (the status layer) ───────────────────────────

LIFECYCLE_YAML = """\
name: canonical_state_round2
question: Does the canonical registry survive a supersede chain?
version: "0.3"
workflow:
  kind: agent_task
  params: {language: python}
factors:
  - {name: model, levels: [anthropic/claude-opus-5]}
design: factorial
status: superseded
supersedes: [canonical_state_design, canonical_state_implement]
superseded_by: canonical_state_finalize
completed_at: "2026-08-15T10:00:00+00:00"
last_run_at: "2026-08-15T09:30:00+00:00"
results_pointer: experiments/results/workflows/canonical_state_round2/20260815T093000Z.json
"""


def _minimal_spec(**overrides) -> ExperimentSpec:
    """An ExperimentSpec with only the required fields, plus any lifecycle overrides."""
    base = dict(
        name="x",
        question="q",
        version="1",
        workflow=Workflow("agent_task"),
        factors=[Factor("model", ["a"])],
        design="factorial",
    )
    base.update(overrides)
    return ExperimentSpec(**base)


def test_lifecycle_defaults_are_unset():
    # The 63 committed specs carry no lifecycle keys, so every default must be the
    # "nothing asserted" value — the index derives status from these, not the YAML.
    spec = _minimal_spec()
    assert spec.status == ""
    assert spec.supersedes == []
    assert spec.superseded_by is None
    assert spec.completed_at is None
    assert spec.last_run_at is None
    assert spec.results_pointer is None


def test_load_spec_preserves_lifecycle_fields(tmp_path):
    path = tmp_path / "canonical_state_round2.yaml"
    path.write_text(LIFECYCLE_YAML)
    spec = load_spec(path)
    assert spec.status == "superseded"
    assert spec.supersedes == ["canonical_state_design", "canonical_state_implement"]
    assert spec.superseded_by == "canonical_state_finalize"
    assert spec.completed_at == "2026-08-15T10:00:00+00:00"
    assert spec.last_run_at == "2026-08-15T09:30:00+00:00"
    assert spec.results_pointer.endswith("20260815T093000Z.json")


def test_lifecycle_round_trips_through_to_dict(tmp_path):
    path = tmp_path / "canonical_state_round2.yaml"
    path.write_text(LIFECYCLE_YAML)
    spec = load_spec(path)
    assert ExperimentSpec.from_dict(spec.to_dict()) == spec
    # ... and every key to_dict emits is a recognized top-level key, so a round trip
    # through the serialized form can never trip the unknown-key warning.
    assert set(spec.to_dict()) <= SPEC_KEYS


def test_supersedes_accepts_a_bare_string():
    # `supersedes: old_spec` is as natural to author as `supersedes: [old_spec]`;
    # both normalize to a list so consumers never branch on the type.
    spec = ExperimentSpec.from_dict(
        {
            "name": "x", "question": "q", "version": "1",
            "workflow": {"kind": "agent_task"},
            "factors": [{"name": "model", "levels": ["a"]}],
            "design": "factorial",
            "supersedes": "old_spec",
        }
    )
    assert spec.supersedes == ["old_spec"]


def test_empty_lifecycle_strings_normalize_to_none():
    spec = ExperimentSpec.from_dict(
        {
            "name": "x", "question": "q", "version": "1",
            "workflow": {"kind": "agent_task"},
            "factors": [{"name": "model", "levels": ["a"]}],
            "design": "factorial",
            "superseded_by": "", "completed_at": "  ", "supersedes": "",
        }
    )
    assert spec.superseded_by is None
    assert spec.completed_at is None
    assert spec.supersedes == []


def test_unknown_top_level_key_warns_and_is_not_silently_dropped():
    # A typo'd lifecycle key used to vanish without a trace, so the spec looked like it
    # had been honoured. It must now be visible — and still non-fatal.
    payload = {
        "name": "typo_spec", "question": "q", "version": "1",
        "workflow": {"kind": "agent_task"},
        "factors": [{"name": "model", "levels": ["a"]}],
        "design": "factorial",
        "supercedes": "old_spec",  # note the misspelling
    }
    with pytest.warns(UserWarning, match="supercedes"):
        spec = ExperimentSpec.from_dict(payload)
    assert spec.supersedes == []          # the typo really was not applied ...
    assert spec.name == "typo_spec"       # ... and the load still succeeded


def test_known_keys_do_not_warn(recwarn):
    load_spec_payload = ExperimentSpec.from_dict(
        {
            "name": "x", "question": "q", "version": "1",
            "workflow": {"kind": "agent_task"},
            "factors": [{"name": "model", "levels": ["a"]}],
            "design": "factorial",
            "status": "draft", "supersedes": [], "superseded_by": None,
            "completed_at": None, "last_run_at": None, "results_pointer": None,
        }
    )
    assert load_spec_payload.status == "draft"
    assert [w for w in recwarn.list if issubclass(w.category, UserWarning)] == []


def test_spec_id_is_name_at_version():
    # `spec_id` is a declared LEDGER_FIELD; this property is its one canonical builder,
    # so job and attempt records cannot drift into two formats.
    assert _minimal_spec(name="spec_lifecycle", version="0.1").spec_id == "spec_lifecycle@0.1"
    assert "spec_id" in LEDGER_FIELDS


@pytest.mark.parametrize("status", sorted(SPEC_STATUSES))
def test_validator_admits_every_defined_status(status):
    assert validate_spec(_minimal_spec(status=status)) == []


def test_validator_admits_unset_status():
    # "" means "not asserted" — the index derives it. Every committed spec is in this state.
    assert validate_spec(_minimal_spec(status="")) == []


def test_validator_flags_unknown_status():
    errors = validate_spec(_minimal_spec(status="retired"))
    assert any("retired" in e for e in errors)


def test_validator_flags_self_referential_lineage():
    errors = validate_spec(_minimal_spec(name="loop", superseded_by="loop"))
    assert any("superseded_by" in e for e in errors)
    errors = validate_spec(_minimal_spec(name="loop", supersedes=["loop"]))
    assert any("supersedes" in e for e in errors)


def test_committed_specs_all_load_without_unknown_key_warnings(recwarn):
    """Every committed spec must load clean — no unknown keys, no validation errors.

    This is the regression guard for the corpus itself: adding a lifecycle key to a spec
    YAML that this dataclass does not know about would light up here rather than in a run.
    """
    specs_dir = Path(__file__).resolve().parent.parent
    paths = committed_spec_paths(specs_dir)
    assert len(paths) >= 63, f"expected the committed spec corpus, found {len(paths)}"
    for path in paths:
        spec = load_spec(path)
        assert spec.spec_id == f"{spec.name}@{spec.version}"
    unknown_key_warnings = [
        w for w in recwarn.list if "unknown top-level key" in str(w.message)
    ]
    assert unknown_key_warnings == []


# ── Prose-vs-schema safety gate (review P1) ─────────────────────────────────
# A safety requirement in prompt prose is advisory; in the schema it is enforceable.
# The gate fires when a phase orders an operator halt without checkpoint: true, or issues
# a production deploy command without deploy_allowed: true.


def _phase_spec(phases):
    return _minimal_spec(workflow=Workflow("agent_task", {"phases": phases}))


HALT_PROMPT = "Build the thing. STOP THE CAMPAIGN: the operator must visually approve."
DEPLOY_PROMPT = "Build the site, then firebase deploy --only hosting (canonical ai-finops-rulebook)."


def test_halt_prose_without_checkpoint_is_rejected():
    errors = validate_spec(_phase_spec([{"name": "p1", "kind": "agent", "prompt": HALT_PROMPT}]))
    assert any("orders an operator halt" in e and "checkpoint: true" in e for e in errors)


def test_halt_prose_with_checkpoint_is_accepted():
    errors = validate_spec(
        _phase_spec([{"name": "p1", "kind": "agent", "checkpoint": True, "prompt": HALT_PROMPT}])
    )
    assert errors == []


def test_deploy_command_without_deploy_allowed_is_rejected():
    errors = validate_spec(_phase_spec([{"name": "p1", "kind": "agent", "prompt": DEPLOY_PROMPT}]))
    assert any("production deploy command" in e and "deploy_allowed: true" in e for e in errors)


def test_deploy_command_with_deploy_allowed_is_accepted():
    errors = validate_spec(
        _phase_spec([{"name": "p1", "kind": "agent", "deploy_allowed": True, "prompt": DEPLOY_PROMPT}])
    )
    assert errors == []


def test_dry_run_deploy_mentions_are_not_commands():
    prompt = "Check the deploy with firebase deploy --only hosting --dry-run before anything."
    errors = validate_spec(_phase_spec([{"name": "p1", "kind": "agent", "prompt": prompt}]))
    assert errors == []


def test_quoted_or_bare_deploy_mentions_are_not_commands():
    prompt = (
        "The lesson: terra ran `firebase deploy` during p3, silently. "
        "Bypass shapes: 'firebase --help > /dev/null && firebase deploy', "
        "'npx firebase-tools deploy'. The p2 deploy gate must catch them."
    )
    errors = validate_spec(_phase_spec([{"name": "p1", "kind": "agent", "prompt": prompt}]))
    assert errors == []


def test_machinery_mentions_do_not_trigger_halt_rule():
    prompt = "Implement the checkpoint phase kind: a phase declaring checkpoint: true that completes successfully stops with awaiting_operator_approval."
    errors = validate_spec(_phase_spec([{"name": "p1", "kind": "agent", "prompt": prompt}]))
    assert errors == []


def test_committed_spec_corpus_passes_the_prose_safety_gate():
    """Every committed spec validates clean under the prose-vs-schema safety gate.

    This is the regression guard for the review's flagship finding: the
    cap_site_revamp4_diagrams workflow ordered operator halts and a deploy in prose
    while declaring no checkpoint/deploy_allowed markers. A workflow that stops or
    deploys in prose must declare the mechanical markers, or this test fails.
    """
    specs_dir = Path(__file__).resolve().parent.parent
    paths = committed_spec_paths(specs_dir)
    assert len(paths) >= 63, f"expected the committed spec corpus, found {len(paths)}"
    for path in paths:
        spec = load_spec(path)
        errors = validate_spec(spec)
        assert errors == [], f"{path} fails validation: {errors}"



# ── w2: workflow_revision_id — canonicalized spec revision digest ──────────────


def _agent_spec(**overrides) -> dict:
    """A structural agent_task spec mapping (dict form, like a parsed YAML)."""
    base = {
        "name": "ship",
        "question": "does it work?",
        "version": "0.1",
        "workflow": {
            "kind": "agent_task",
            "params": {
                "language": "python",
                "phases": [
                    {"name": "p1_build", "kind": "agent", "prompt": "build it"},
                    {"name": "p2_verify", "kind": "test", "tests": ["tests/test_x.py"]},
                ],
            },
        },
        "factors": [{"name": "model", "levels": ["deepseek/deepseek-v4-pro"]}],
        "design": "factorial",
        "rules": [{"name": "r", "plane": "measurement", "evidence_class": "[M]"}],
        "stop": {"budget_usd": 10.0},
        "adapt": {"strategy": "manual", "selection": "highest_regret"},
    }
    base.update(overrides)
    return base


def test_workflow_revision_id_is_exposed_on_the_spec_object():
    spec = ExperimentSpec.from_dict(_agent_spec())
    assert spec.workflow_revision_id == compute_workflow_revision_id(spec)
    assert len(spec.workflow_revision_id) == 64  # sha256 hexdigest


def test_revision_digest_is_stable_across_cosmetic_edits(tmp_path: Path):
    """VERIFY (a) first direction: comment/whitespace edits leave the digest untouched."""
    import yaml

    path = tmp_path / "ship.yaml"
    path.write_text(yaml.dump(_agent_spec()))
    before = load_spec(path).workflow_revision_id

    # cosmetic: comments, blank lines, indentation — none change the parsed structure
    path.write_text("# leading comment\n" + yaml.dump(_agent_spec()) + "\n\n# trailing\n")
    assert load_spec(path).workflow_revision_id == before

    # lifecycle/volatile keys are NOT part of the definition and never re-key a revision
    with_lifecycle = _agent_spec()
    with_lifecycle["status"] = "completed"
    with_lifecycle["completed_at"] = "2026-09-02T00:00:00+00:00"
    assert (
        ExperimentSpec.from_dict(with_lifecycle).workflow_revision_id
        == ExperimentSpec.from_dict(_agent_spec()).workflow_revision_id
    )


def test_revision_digest_changes_on_structural_edits():
    """VERIFY (a) second direction: adding a phase / a gate changes the digest."""
    base = _agent_spec()
    base_digest = ExperimentSpec.from_dict(base).workflow_revision_id

    appended_gate = dict(base)
    appended_gate["workflow"]["params"]["phases"] = list(base["workflow"]["params"]["phases"]) + [
        {"name": "p3_gate", "kind": "test", "tests": ["tests/test_gate.py"]}
    ]
    assert ExperimentSpec.from_dict(appended_gate).workflow_revision_id != base_digest

    edited_phase = dict(base)
    edited_phase["workflow"]["params"]["phases"] = [
        {**base["workflow"]["params"]["phases"][0], "name": "p1_build_renamed"}
    ] + base["workflow"]["params"]["phases"][1:]
    assert ExperimentSpec.from_dict(edited_phase).workflow_revision_id != base_digest


def test_revision_digest_is_deterministic_across_construction_paths(tmp_path: Path):
    """The same definition hashes the same whether built by dict or loaded from YAML."""
    import yaml

    path = tmp_path / "ship.yaml"
    path.write_text(yaml.dump(_agent_spec()))
    assert load_spec(path).workflow_revision_id == ExperimentSpec.from_dict(_agent_spec()).workflow_revision_id


def test_revision_digest_ignores_key_order_within_a_definition(tmp_path: Path):
    """Structural YAML key order is not definitional — the digest is canonicalized."""
    import yaml

    a = _agent_spec()
    # round-trip through YAML text with keys reordered at the top level
    txt = yaml.dump(a)
    shuffled = yaml.safe_load(txt)
    reordered = {"adapt": shuffled["adapt"], "name": shuffled["name"],
                 "workflow": shuffled["workflow"], "rules": shuffled["rules"],
                 "stop": shuffled["stop"], "factors": shuffled["factors"],
                 "design": shuffled["design"], "question": shuffled["question"],
                 "version": shuffled["version"]}
    assert ExperimentSpec.from_dict(reordered).workflow_revision_id == ExperimentSpec.from_dict(a).workflow_revision_id
