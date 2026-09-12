"""Tests for the step-9 escalation mechanism (G-27/G-28): opt-in cascade, recorded attempts.

The plan (``runtime/escalation.py``) is pure and pinned directly. The runner integration uses
the real engine with a fake agent that fails on the first ladder model and succeeds on the
successor. Pins:

* default OFF: exactly one attempt, no escalation fields — the historical engine;
* a laddered failure retries the successor ONCE, and the attempt records carry the per-attempt
  truth (model/status/cost/tokens/from/to/reason, parent chain);
* the phase totals include EVERY attempt's spend (an escalation is a second paid call);
* a model not on the ladder never escalates; the attempt cap is honored;
* a malformed ladder is a loud spec error at the door, never a silent no-op;
* a budget-refused retry fails closed, never stamps the escalation as started, and still owes
  the first attempt's cost.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from agentic_dynamics.core.admission_context import AdmissionRefused
from agentic_dynamics.experiment.experiment_spec import load_spec
from agentic_dynamics.runtime.escalation import EscalationPlan
from agentic_dynamics.runtime.workflow_runner import run_workflow

SPEC = Path(__file__).resolve().parent.parent / "workflows" / "repository" / "control_room_portal.yaml"


def _fake_agent(**overrides):
    base = dict(
        prompt_tokens=10,
        completion_tokens=20,
        reasoning_tokens=5,
        total_tokens=35,
        estimated_cost_usd=0.001,
        files_created=["docs/scope.md"],
        files_modified=[],
        final_response="done",
        ok=True,
        exit_code=0,
        error="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _run(tmp_path, agent, *, model="m/one", escalation=None, phase_admission=None):
    spec = load_spec(SPEC)
    if escalation is not None:
        spec.workflow.params["escalation"] = escalation
    return run_workflow(
        spec,
        goal="g",
        model=model,
        workdir=tmp_path,
        commit=False,
        run_agentic_fn=agent,
        phase_admission=phase_admission,
    )


# ── the pure plan ───────────────────────────────────────────────


def test_plan_walks_the_ladder_and_honors_the_cap():
    plan = EscalationPlan.from_params({"escalation": {"ladder": ["a", "b", "c"]}})
    assert plan is not None
    assert plan.successor("a", attempts_made=1) == "b"
    assert plan.successor("b", attempts_made=2) == "c"
    assert plan.successor("c", attempts_made=3) is None  # end of ladder
    assert plan.successor("z", attempts_made=1) is None  # not on the ladder
    capped = EscalationPlan.from_params({"escalation": {"ladder": ["a", "b"], "max_attempts": 2}})
    assert capped is not None
    assert capped.successor("a", attempts_made=2) is None  # cap reached before the walk


def test_absent_config_is_default_off():
    assert EscalationPlan.from_params({}) is None
    assert EscalationPlan.from_params(None) is None


@pytest.mark.parametrize(
    "raw",
    [
        [],  # not a mapping
        {"ladder": []},  # empty ladder
        {"ladder": ["a", ""]},  # empty model
        {"ladder": ["a", "a"]},  # duplicate -> self-escalation
        {"ladder": ["a"], "max_attempts": 0},  # non-positive cap
        {"ladder": ["a"], "max_attempts": True},  # bool is not an int
    ],
)
def test_malformed_plans_raise(raw):
    with pytest.raises(ValueError):
        EscalationPlan.from_params({"escalation": raw})


# ── the runner integration ──────────────────────────────────────


def test_default_off_keeps_exactly_one_attempt(tmp_path):
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(model)
        return _fake_agent(ok=False, error="boom")

    result = _run(tmp_path, agent)
    assert calls == ["m/one"]
    assert result.phases[0].status == "failed"
    assert len(result.attempts) == 1
    record = result.attempts[0]
    assert record.attempt_number == 1
    assert record.escalation_from is None and record.escalation_to is None
    assert record.retry_reason == ""


def test_laddered_failure_retries_the_successor_and_records_both_attempts(tmp_path):
    calls = []

    def agent(prompt, *, model, backend, workdir, **kwargs):
        calls.append(model)
        if model == "m/one":
            return _fake_agent(
                ok=False,
                error="boom",
                estimated_cost_usd=0.25,
                prompt_tokens=50,
                completion_tokens=50,
                total_tokens=100,
            )
        return _fake_agent(
            estimated_cost_usd=1.0, prompt_tokens=100, completion_tokens=100, total_tokens=200
        )

    result = _run(tmp_path, agent, escalation={"ladder": ["m/one", "m/two"]})
    assert calls[:2] == ["m/one", "m/two"]
    phase = result.phases[0]
    assert phase.status == "ok"
    assert len(phase.attempts) == 2
    assert phase.cost_usd == 1.25  # BOTH attempts' spend — an escalation is a paid second call
    assert phase.tokens["total"] == 300

    first, second = result.attempts[:2]
    assert (first.attempt_number, first.model, first.status) == (1, "m/one", "failed")
    # the failed row stays clean; the RETRY row carries both ends of the escalation (one
    # event per escalation — a half-stamp on the failed attempt would duplicate the event)
    assert (first.escalation_from, first.escalation_to, first.retry_reason) == (None, None, "")
    assert (second.attempt_number, second.model, second.status) == (2, "m/two", "ok")
    assert (second.escalation_from, second.escalation_to, second.retry_reason) == (
        "m/one",
        "m/two",
        "escalation",
    )
    assert second.parent_attempt_id == first.attempt_id
    assert first.first_pass is False and second.first_pass is None
    assert first.accepted is False and second.accepted is True
    assert first.cost_usd == 0.25 and second.cost_usd == 1.0


def test_a_model_off_the_ladder_never_escalates(tmp_path):
    def agent(prompt, *, model, backend, workdir, **kwargs):
        return _fake_agent(ok=False, error="boom")

    result = _run(tmp_path, agent, model="m/other", escalation={"ladder": ["m/one", "m/two"]})
    assert result.phases[0].status == "failed"
    assert len(result.attempts) == 1
    assert result.attempts[0].escalation_to is None


def test_a_lone_ladder_model_has_no_successor(tmp_path):
    def agent(prompt, *, model, backend, workdir, **kwargs):
        return _fake_agent(ok=False, error="boom")

    result = _run(tmp_path, agent, escalation={"ladder": ["m/one"]})
    assert result.phases[0].status == "failed"
    assert len(result.attempts) == 1


def test_malformed_config_is_a_loud_spec_error(tmp_path):
    spec = load_spec(SPEC)
    spec.workflow.params["escalation"] = {"ladder": []}
    with pytest.raises(ValueError, match="ladder"):
        run_workflow(
            spec,
            goal="g",
            model="m/one",
            workdir=tmp_path,
            commit=False,
            run_agentic_fn=lambda *args, **kwargs: _fake_agent(),
        )


class _RefusingRetryGate:
    """The first phase admission passes; the retry's admission is refused (budget exhausted)."""

    def __init__(self):
        self.calls = 0

    def __call__(self, phase_name, model):
        self.calls += 1
        if self.calls > 1:
            raise AdmissionRefused("no budget for a retry")
        return contextlib.nullcontext()


def test_a_refused_retry_fails_closed_and_still_owes_the_first_attempt(tmp_path):
    def agent(prompt, *, model, backend, workdir, **kwargs):
        return _fake_agent(ok=False, error="boom", estimated_cost_usd=0.25)

    gate = _RefusingRetryGate()
    result = _run(
        tmp_path,
        agent,
        escalation={"ladder": ["m/one", "m/two"]},
        phase_admission=gate,
    )
    phase = result.phases[0]
    assert phase.status == "failed"
    assert "ADMISSION_DENIED" in phase.error
    assert gate.calls == 2  # the first admission + the refused retry
    # the first attempt SPENT: its cost is on the phase even though the retry never ran…
    assert phase.cost_usd == 0.25
    # …and the escalation is NOT stamped as started (the ledger must not claim a call
    # was refused by the gate after it already happened).
    assert len(result.attempts) == 1
    assert result.attempts[0].escalation_from is None
    assert result.attempts[0].escalation_to is None


def test_the_escalated_ledger_roundtrips_into_the_cascade_projection(tmp_path):
    """Engine -> ledger dict -> the P9 loader/builder: the surface finally sees a real event.

    This is the loop the step-7 projection could not close: with the writer landed, the
    ledger's attempt rows carry the escalation, and the room's loader+builder produce the
    event (from/to/reason/cost) with nothing invented in between.
    """
    import json as _json

    from agentic_dynamics.control.projections.escalation import (
        build_escalation_cascade,
        load_escalation_attempts,
    )

    def agent(prompt, *, model, backend, workdir, **kwargs):
        if model == "m/one":
            return _fake_agent(ok=False, error="boom", estimated_cost_usd=0.25)
        return _fake_agent(estimated_cost_usd=1.0)

    result = _run(tmp_path, agent, escalation={"ladder": ["m/one", "m/two"]})
    ledger_dir = tmp_path / "workflows" / "escalation_probe"
    ledger_dir.mkdir(parents=True)
    (ledger_dir / "run.json").write_text(
        _json.dumps(
            {
                "spec_name": "escalation_probe",
                "attempts": [attempt.to_dict() for attempt in result.attempts],
            }
        )
    )

    rows, n_ledgers = load_escalation_attempts(tmp_path / "workflows")
    assert n_ledgers == 1
    payload = build_escalation_cascade(rows)
    assert payload["armed"] is True
    first_event = payload["events"][0]
    assert (first_event["from"], first_event["to"]) == ("m/one", "m/two")
    assert first_event["reason"] == "escalation"
    assert first_event["cost_usd"] == 1.0
