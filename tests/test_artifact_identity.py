"""Artifact-identity metadata tests (refactor-repair P1-3 schema).

Pins the explicit, validated identity metadata on :class:`ExperimentSpec` and the compiler's
artifact-identity gate. Before P1-3, identity was guessed from question text (a substring
classifier) and real misplacements survived (``posthoc_pipeline`` — operational — and
``workflow_step_routing`` — source-modifying — both lived in ``experiments/definitions/``).
Now ``artifact_kind``/``intent``/``side_effects``/``repeatable`` are declared fields, and the
validator refuses a pure "experiment" that would mutate the repository unless it is explicitly
``sandboxed`` (runs in a disposable worktree).

All of this is backward-compatible: the pre-P1-3 corpus carries none of these fields, so the
defaults (experiment / measure / no side effects / repeatable / not sandboxed) must load and
validate unchanged.
"""

from __future__ import annotations

from agentic_dynamics.experiment.experiment_spec import (
    ARTIFACT_KINDS,
    INTENTS,
    SPEC_KEYS,
    ExperimentSpec,
    Factor,
    SideEffects,
    Workflow,
    validate_spec,
)


def _spec(**overrides) -> ExperimentSpec:
    """A minimal valid spec, with the identity fields overridable via kwargs."""
    base: dict = dict(
        name="x",
        question="q",
        version="1",
        workflow=Workflow("agent_task"),
        factors=[Factor("model", ["a"])],
        design="factorial",
    )
    base.update(overrides)
    return ExperimentSpec(**base)


# ── defaults (backward compatibility) ────────────────────────────


def test_identity_defaults_are_benign():
    """A spec without the new fields defaults to a pure, repeatable, un-sandboxed experiment."""
    spec = _spec()
    assert spec.artifact_kind == "experiment"
    assert spec.intent == "measure"
    assert spec.side_effects.repository is False
    assert spec.side_effects.external_services is False
    assert spec.repeatable is True
    assert spec.sandboxed is False
    assert validate_spec(spec) == []


def test_identity_fields_are_known_keys():
    """The new fields are recognized top-level keys (never tripping the unknown-key warning)."""
    for key in ("artifact_kind", "intent", "side_effects", "repeatable", "sandboxed"):
        assert key in SPEC_KEYS


def test_identity_round_trips_through_dict():
    """to_dict → from_dict preserves every identity field, and the keys are all SPEC_KEYS."""
    spec = _spec(
        artifact_kind="workflow",
        intent="mutate",
        side_effects=SideEffects(repository=True, external_services=True),
        repeatable=False,
        sandboxed=True,
    )
    restored = ExperimentSpec.from_dict(spec.to_dict())
    assert restored.artifact_kind == "workflow"
    assert restored.intent == "mutate"
    assert restored.side_effects.repository is True
    assert restored.side_effects.external_services is True
    assert restored.repeatable is False
    assert restored.sandboxed is True
    assert set(spec.to_dict()) <= SPEC_KEYS


def test_side_effects_from_dict_accepts_partial():
    """An authored ``side_effects: {repository: true}`` leaves ``external_services`` at default."""
    side = SideEffects.from_dict({"repository": True})
    assert side.repository is True
    assert side.external_services is False


# ── enum validation ──────────────────────────────────────────────


def test_validator_flags_unknown_artifact_kind():
    errors = validate_spec(_spec(artifact_kind="pipeline"))
    assert any("artifact_kind" in e for e in errors)
    assert {"experiment", "workflow"} == ARTIFACT_KINDS


def test_validator_flags_unknown_intent():
    errors = validate_spec(_spec(intent="rewrite"))
    assert any("intent" in e for e in errors)
    assert {"measure", "mutate"} == INTENTS


# ── the artifact-identity gate ───────────────────────────────────


def test_experiment_may_measure():
    """A pure experiment (measure, no repo side effects) is valid."""
    assert validate_spec(_spec(artifact_kind="experiment", intent="measure")) == []


def test_experiment_rejects_mutate_intent():
    """An experiment that mutates source is refused — it is a workflow, not an experiment."""
    errors = validate_spec(_spec(artifact_kind="experiment", intent="mutate"))
    assert any("artifact_kind" in e and "intent=mutate" in e for e in errors)


def test_experiment_rejects_repository_side_effects():
    """An experiment that writes to the repository is refused unless sandboxed."""
    errors = validate_spec(
        _spec(artifact_kind="experiment", side_effects=SideEffects(repository=True))
    )
    assert any("artifact_kind" in e and "repository" in e for e in errors)


def test_experiment_rejects_both_reasons_at_once():
    """Both rejection reasons are reported together when both apply."""
    errors = validate_spec(
        _spec(
            artifact_kind="experiment",
            intent="mutate",
            side_effects=SideEffects(repository=True),
        )
    )
    matching = [e for e in errors if "artifact_kind" in e]
    assert matching and any("intent=mutate" in e and "repository" in e for e in matching)


def test_experiment_admits_mutation_when_sandboxed():
    """The explicit escape hatch: a sandboxed experiment may mutate (disposable worktree)."""
    assert (
        validate_spec(
            _spec(
                artifact_kind="experiment",
                intent="mutate",
                side_effects=SideEffects(repository=True),
                sandboxed=True,
            )
        )
        == []
    )


def test_workflow_may_mutate_unsandboxed():
    """A workflow is the artifact kind for source/repo mutation — no sandbox required."""
    assert (
        validate_spec(
            _spec(
                artifact_kind="workflow",
                intent="mutate",
                side_effects=SideEffects(repository=True, external_services=True),
            )
        )
        == []
    )


def test_external_services_alone_does_not_reject_an_experiment():
    """external_services is metadata, not a rejection trigger — only source/repo mutation is."""
    # An experiment may read external services (e.g. the Redis queue) without modifying the repo.
    assert (
        validate_spec(
            _spec(artifact_kind="experiment", side_effects=SideEffects(external_services=True))
        )
        == []
    )
