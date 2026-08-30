"""Tests for the ledger data-integrity instrumentation (ledger_instrumentation p1).

Lock the two halves of the emission contract:

1. **The field emission** — a synthetic workflow run's ledger carries the attempt fields
   (``attempt_count`` + per-attempt ``retry_reason`` / ``first_pass`` / ``accepted`` /
   ``escalation_from`` / ``escalation_to``), the breach fields (``stall_evidence`` /
   ``deploy_gate`` / ``commit_gate`` / ``relabel_gate`` on every phase), and the ``checkpoints``
   array.

2. **The backward compatibility** — a ledger WITHOUT the new fields (a pre-instrumentation
   ledger) still parses: the new keys are strictly additive and never rename or remove an
   existing key, so the old corpus is never broken.

The emission writes the EXACT schema semantics of ``experiment_spec.LEDGER_FIELDS``: the
workflow runner makes one attempt per agent phase (no retry, no model escalation), so the
attempt fields are emitted with their honest values — never fabricated.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

from agentic_dynamics.experiment.experiment_spec import load_spec
from agentic_dynamics.runtime.workflow_runner import (
    AttemptRecord,
    _build_attempt_records,
    run_workflow,
)

SPEC = Path(__file__).resolve().parent.parent / "workflows" / "repository" / "control_room_portal.yaml"

# The aggregator lives in scripts/ (not on the package import path); import it by module name,
# matching the sibling script tests (tests/test_aggregate_workflow_metrics.py).
agg = importlib.import_module("scripts.aggregate_workflow_metrics")

#: The four breach fields the runner computes and the phase ledger must serialize.
BREACH_FIELDS = ("stall_evidence", "deploy_gate", "commit_gate", "relabel_gate")

#: The attempt-level fields the schema declares and p1 now emits (the "declared-not-written"
#: finding). ``attempt_count`` is emitted at the run level; the rest ride each attempt record.
ATTEMPT_FIELDS = (
    "attempt_id",
    "job_id",
    "phase",
    "attempt_number",
    "parent_attempt_id",
    "retry_reason",
    "first_pass",
    "accepted",
    "escalation_from",
    "escalation_to",
)


def _fake_agent(**overrides):
    """A synthetic agent result shaped like the adapters' ``AgenticResult`` (the test seam)."""
    base = dict(
        prompt_tokens=10,
        completion_tokens=20,
        reasoning_tokens=5,
        answer_tokens=0,
        explanation_tokens=0,
        total_tokens=35,
        estimated_cost_usd=0.001,
        files_created=[],
        files_modified=[],
        final_response="done",
        ok=True,
        exit_code=0,
        error="",
        cache_read_tokens=0,
        cache_write_tokens=0,
        cache_hit_rate=0.0,
        session_id="s1",
        confidence=0.9,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _run_synthetic(tmp_path):
    """Run the control_room_portal spec against a fake agent and return the serialized ledger."""
    spec = load_spec(SPEC)
    result = run_workflow(
        spec,
        goal="the goal",
        model="openai/gpt-5.6-sol",
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )
    return result, result.to_dict()


def test_attempt_record_to_dict_emits_exact_schema_fields():
    """``AttemptRecord.to_dict()`` carries every attempt-level field the schema declares."""
    rec = AttemptRecord(
        attempt_id="wf_x_y_scope_a1",
        job_id="wf_x_y",
        phase="scope",
        attempt_number=1,
        retry_reason="",
        first_pass=True,
        accepted=True,
        model="m",
        status="ok",
        cost_usd=0.001,
        tokens={"in": 10, "out": 20},
        test_executed_success=True,
        confidence=0.9,
    )
    d = rec.to_dict()
    # The declared attempt fields are all present, with their exact (honest) values.
    for field in ATTEMPT_FIELDS:
        assert field in d, f"attempt record missing field: {field}"
    # Null-not-zero: an absent escalation is None, never a fabricated "" or 0.
    assert d["escalation_from"] is None
    assert d["escalation_to"] is None
    assert d["attempt_number"] == 1
    assert d["retry_reason"] == ""


def test_build_attempt_records_one_per_agent_phase():
    """One attempt record per agent phase; test phases produce no attempt (no model call)."""
    spec = load_spec(SPEC)
    result = run_workflow(
        spec,
        goal="g",
        model="m",
        workdir=Path("/tmp"),
        commit=False,
        run_agentic_fn=lambda *a, **k: _fake_agent(),
    )
    # The spec's phases are scope/ux_design/implement (agent) + verify (test).
    agent_phase_names = ["scope", "ux_design", "implement"]
    records = _build_attempt_records(result, "wf_control_room_portal_m")
    assert [r.phase for r in records] == agent_phase_names
    assert [r.attempt_number for r in records] == [1, 1, 1]
    assert [r.retry_reason for r in records] == ["", "", ""]
    assert [r.first_pass for r in records] == [True, True, True]
    assert [r.accepted for r in records] == [True, True, True]
    assert [r.escalation_from for r in records] == [None, None, None]
    assert all(r.job_id == "wf_control_room_portal_m" for r in records)


def test_run_ledger_carries_attempt_fields(tmp_path):
    """A synthetic run's serialized ledger emits the attempt fields + ``attempt_count``."""
    result, d = _run_synthetic(tmp_path)
    n_agent = sum(1 for p in result.phases if p.kind == "agent")
    assert d["attempt_count"] == n_agent
    assert isinstance(d["attempts"], list)
    assert len(d["attempts"]) == n_agent
    for attempt in d["attempts"]:
        for field in ATTEMPT_FIELDS:
            assert field in attempt, f"attempt missing field: {field}"


def test_run_ledger_carries_breach_fields(tmp_path):
    """Every phase in the serialized ledger carries the four breach fields (None = no breach)."""
    _, d = _run_synthetic(tmp_path)
    for phase in d["phases"]:
        for field in BREACH_FIELDS:
            assert field in phase, f"phase {phase['phase']} missing breach field: {field}"


def test_run_ledger_carries_checkpoints_array(tmp_path):
    """The serialized ledger carries the ``checkpoints`` array (empty on a run with no checkpoint)."""
    _, d = _run_synthetic(tmp_path)
    assert "checkpoints" in d
    assert isinstance(d["checkpoints"], list)


def test_old_ledger_without_new_fields_still_parses():
    """A pre-instrumentation ledger (no attempts/attempt_count/breach/checkpoints) still parses.

    The new keys are additive; the aggregator's workflow-run extractor reads every field
    defensively (``.get``), so an old ledger yields the same phases/checkpoints and never crashes.
    """
    old_ledger = {
        "spec_name": "control_room_portal",
        "spec_id": "control_room_portal@0.2",
        "model": "openai/gpt-5.6-sol",
        "workdir": "/tmp/wt",
        "goal": "the goal",
        "git_sha": "abc123",
        "started_at": "2026-08-19T00:00:00+00:00",
        "ended_at": "2026-08-19T00:05:00+00:00",
        # No "attempts", no "attempt_count", no "state", no "checkpoints", and the phase
        # dicts carry NONE of the breach fields — the pre-instrumentation shape.
        "ok": True,
        "total_cost_usd": 0.003,
        "phases": [
            {"phase": "scope", "kind": "agent", "status": "ok", "cost_usd": 0.001, "duration_s": 1.0},
            {"phase": "verify", "kind": "test", "status": "ok", "cost_usd": 0.0, "duration_s": 0.5},
        ],
    }
    # Classification + extraction must succeed and preserve the phase rows (never a crash).
    assert agg.classify(old_ledger) == agg.KIND_WORKFLOW_RUN
    corpus = agg.extract_ledger(old_ledger, "experiments/results/workflows/control_room_portal/x.json")
    assert [p.phase for p in corpus.phases] == ["scope", "verify"]
    # The old ledger records no breach evidence — and that is a coverage gap, never a fabricated
    # clean SLA record (the measured-not-estimated rule, applied to the old corpus).
    assert not any(p.breach_fields_recorded for p in corpus.phases)


def test_new_ledger_is_a_superset_of_the_old_shape(tmp_path):
    """The instrumented ledger keeps every pre-existing key and only ADDS the new ones.

    Backward compatibility in the other direction: a consumer that reads the OLD keys still
    finds them unchanged on a NEW ledger, so the old corpus is never broken and the new corpus
    stays readable by old consumers.
    """
    _, d = _run_synthetic(tmp_path)
    # The pre-instrumentation keys are all still present, byte-for-byte in shape.
    for key in ("spec_name", "spec_id", "model", "workdir", "goal", "git_sha",
                "started_at", "ended_at", "ok", "state", "total_cost_usd", "phases",
                "checkpoints"):
        assert key in d, f"new ledger lost pre-existing key: {key}"
    # The new keys are additive.
    assert "attempts" in d
    assert "attempt_count" in d
