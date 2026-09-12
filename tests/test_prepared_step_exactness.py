"""Wave A2 — exact prepared execution + real attempt identity (the review's #4).

Pins, at the real seams:

* the engine propagates the ATTEMPT ordinal into the executor request (the review's
  reproduction showed requests carrying ``1`` on every retry while the ledger recorded
  ``1, 2`` — the retry namespace collided at ``a1``);
* ``_attempt_base`` continues the parent's numbering for a prepared child (attempt 7 -> a7);
* the prepared child executes the payload EXACTLY: the payload's settings and prompt (verbatim,
  placeholders intact), ONE adapter invocation even when the first result fails (the parent
  owns retry policy — no in-child escalation ladder), and the parent's routing/signals are not
  recomposed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src", _ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import run_workflow as rw_mod  # noqa: E402

from agentic_dynamics.experiment.experiment_spec import load_spec  # noqa: E402
from agentic_dynamics.runtime import workflow_runner  # noqa: E402
from agentic_dynamics.runtime.executor import StepRequest  # noqa: E402
from agentic_dynamics.runtime.workflow_runner import run_workflow  # noqa: E402

SPEC = _ROOT / "workflows" / "repository" / "control_room_portal.yaml"


def _fake_result(**overrides):
    base = dict(
        ok=True, exit_code=0, error="", prompt_tokens=1, completion_tokens=1,
        reasoning_tokens=0, total_tokens=2, estimated_cost_usd=0.001,
        files_created=[], files_modified=[], final_response="x",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class _RecordingExecutor:
    """A StepExecutor that records each request's attempt ordinal, failing the first call."""

    def __init__(self, *, fail_first: bool = True):
        self.attempts: list[int] = []
        self.prompts: list[str] = []
        self._fail_first = fail_first

    def execute(self, request: StepRequest):
        self.attempts.append(request.attempt)
        self.prompts.append(request.prompt)
        failed = self._fail_first and len(self.attempts) == 1
        return _fake_result(ok=not failed, exit_code=0 if not failed else 1,
                            error="boom" if failed else "")


def test_engine_propagates_attempt_ordinals_to_the_executor(tmp_path):
    """A retried phase's TWO requests carry the REAL ordinals 1, 2 — not 1, 1."""
    spec = load_spec(SPEC)
    spec.workflow.params["escalation"] = {"ladder": ["m/one", "m/two"]}
    recording = _RecordingExecutor()
    run_workflow(
        spec, goal="g", model="m/one", workdir=tmp_path, commit=False,
        run_agentic_fn=lambda *a, **k: _fake_result(), step_executor=recording,
    )
    assert recording.attempts[:2] == [1, 2]


def test_attempt_base_continues_the_parents_numbering(tmp_path):
    """A prepared child on attempt 7 labels its request a7 (the namespace must not collide)."""
    spec = load_spec(SPEC)
    spec.workflow.params["_attempt_base"] = 7
    recording = _RecordingExecutor(fail_first=False)
    run_workflow(
        spec, goal="g", model="m/one", workdir=tmp_path, commit=False,
        run_agentic_fn=lambda *a, **k: _fake_result(), step_executor=recording,
    )
    assert recording.attempts[:1] == [7]


def _prepared_payload(tmp_path: Path) -> Path:
    request = StepRequest(
        phase_name="scope",
        phase_kind="agent",
        prompt="EXACT parent literal {goal}",
        model="m/one",
        goal="g",
        spec_name="control_room_portal",
        workdir=str(tmp_path),
        thinking_effort="low",
        thinking_budget_tokens=7,
        output_token_limit=11,
        timeout=77,
        attempt=7,
    )
    path = tmp_path / "prepared-step.json"
    import json

    path.write_text(json.dumps(request.to_prepared_dict()))
    return path


def test_prepared_child_executes_the_payload_exactly_and_once(tmp_path, monkeypatch):
    """One adapter invocation with the payload's settings and VERBATIM prompt, even on failure.

    The failing fake proves the escalation ladder does not run in the child (the review's
    two-call reproduction); the prompt keeps its ``{goal}`` placeholder (no re-rendering);
    every setting comes from the payload, not this invocation's contradicting flags.
    """
    calls: list[dict] = []

    def fake_run_agentic(prompt, **kwargs):
        calls.append({"prompt": prompt, **kwargs})
        return _fake_result(ok=False, exit_code=1, error="provider refused")

    monkeypatch.setattr(workflow_runner, "run_agentic", fake_run_agentic)
    payload = _prepared_payload(tmp_path)

    monkeypatch.setattr(sys, "argv", [
        "run_workflow.py",
        "--spec", str(SPEC),
        "--goal", "SHOULD-NOT-APPLY",
        "--model", "m/other",
        "--workdir", str(tmp_path),
        "--only-phase", "scope",
        "--prepared-step", str(payload),
        "--no-commit",
        "--timeout", "9999",
        "--thinking-effort", "high",
    ])
    with pytest.raises(SystemExit):
        rw_mod.main()

    assert len(calls) == 1  # no escalation retry in the child
    call = calls[0]
    assert call["prompt"] == "EXACT parent literal {goal}"  # verbatim, not substituted
    assert call["model"] == "m/one"  # payload over every flag/spec value
    assert call["thinking_effort"] == "low"
    assert call["thinking_budget_tokens"] == 7
    assert call["output_token_limit"] == 11
    assert call["timeout"] == 77


def test_prepared_child_does_not_recompose_routing_or_replan(tmp_path, monkeypatch):
    """The captured spec shows the child's conformance flags: attempt base, escalation gone,
    augmentation off, the prepared phase marked — and no requeueing of the parent's policy."""
    captured: dict = {}

    def fake_engine(spec, **kwargs):
        captured["params"] = dict(spec.workflow.params)
        captured["phase"] = dict((spec.workflow.params.get("phases") or [{}])[0])
        captured["model"] = kwargs.get("model")
        captured["router"] = kwargs.get("router")
        captured["signals"] = kwargs.get("signals")
        raise SystemExit(0)  # stop before main's post-run bookkeeping

    monkeypatch.setattr(rw_mod, "run_workflow", fake_engine)
    payload = _prepared_payload(tmp_path)

    monkeypatch.setattr(sys, "argv", [
        "run_workflow.py",
        "--spec", str(SPEC),
        "--goal", "SHOULD-NOT-APPLY",
        "--model", "m/other",
        "--workdir", str(tmp_path),
        "--only-phase", "scope",
        "--prepared-step", str(payload),
        "--no-commit",
    ])
    with pytest.raises(SystemExit):
        rw_mod.main()

    assert captured["params"]["_attempt_base"] == 7
    assert "escalation" not in captured["params"]
    assert captured["params"]["rag_augment"] is False
    assert captured["phase"]["_prepared_step"] is True
    assert captured["phase"]["prompt"] == "EXACT parent literal {goal}"
    assert captured["model"] == "m/one"
    assert captured["router"] is None  # routing is the parent's decision
    assert captured["signals"] is None
