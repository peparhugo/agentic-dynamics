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
import yaml

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


def _prepared_payload(tmp_path: Path, **overrides) -> Path:
    base = dict(
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
    base.update(overrides)
    request = StepRequest(**base)
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


def test_prepared_child_never_recomposes_routing_or_reenters_the_engine(tmp_path, monkeypatch):
    """Astra ae212a0 finding 5: the worker executes the CONCRETE request directly.

    The engine must not run at all — monkeypatched to explode if reached. The parent owns
    routing/signals; the payload is the resolved result, so the adapter sees the payload's model
    and the verbatim prompt and no re-planning happens.
    """
    calls: list[dict] = []

    def fake_run_agentic(prompt, **kwargs):
        calls.append({"prompt": prompt, **kwargs})
        return _fake_result()

    def explosive_engine(*_a, **_k):  # pragma: no cover - reached only on regression
        raise AssertionError("prepared child must not enter the workflow engine")

    monkeypatch.setattr(workflow_runner, "run_agentic", fake_run_agentic)
    monkeypatch.setattr(rw_mod, "run_workflow", explosive_engine)
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

    assert len(calls) == 1
    assert calls[0]["model"] == "m/one"
    assert calls[0]["prompt"] == "EXACT parent literal {goal}"


def _mutated_spec(tmp_path: Path, mutate) -> Path:
    """Write a copy of the test spec with ``mutate(raw)`` applied (the source-spec bait)."""
    raw = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    mutate(raw)
    path = tmp_path / "mutated-spec.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def _run_prepared_cli(
    tmp_path: Path,
    monkeypatch,
    *,
    spec_path: Path,
    prepared_kwargs: dict,
    calls: list[dict],
) -> None:
    def fake_run_agentic(prompt, **kwargs):
        calls.append({"prompt": prompt, **kwargs})
        return _fake_result()

    monkeypatch.setattr(workflow_runner, "run_agentic", fake_run_agentic)
    payload = _prepared_payload(tmp_path, **prepared_kwargs)
    monkeypatch.setattr(sys, "argv", [
        "run_workflow.py",
        "--spec", str(spec_path),
        "--goal", "SHOULD-NOT-APPLY",
        "--model", "m/other",
        "--workdir", str(tmp_path),
        "--only-phase", "scope",
        "--prepared-step", str(payload),
        "--no-commit",
        "--timeout", "9999",
    ])
    with pytest.raises(SystemExit):
        rw_mod.main()


def test_prepared_child_ignores_source_model_pool(tmp_path, monkeypatch):
    """Probe 1: source ``model_pool=[m/one, m/two]`` must not refuse or reroute.

    Before the fix the child re-entered the engine with no router and the multi-model pool
    raised — ZERO calls. Now the concrete request executes exactly once on its own model.
    """
    calls: list[dict] = []

    def mutate(raw):
        raw["workflow"]["params"]["model_pool"] = ["m/one", "m/two"]

    _run_prepared_cli(
        tmp_path, monkeypatch,
        spec_path=_mutated_spec(tmp_path, mutate),
        prepared_kwargs={"model": "m/two"},
        calls=calls,
    )

    assert len(calls) == 1  # exactly one invocation at the provider seam
    assert calls[0]["model"] == "m/two"


def test_prepared_child_ignores_phase_run_model(tmp_path, monkeypatch):
    """Probe 2: a source phase ``run_model: m/one`` must not override the prepared ``m/two``."""
    calls: list[dict] = []

    def mutate(raw):
        for phase in raw["workflow"]["params"]["phases"]:
            if phase["name"] == "scope":
                phase["run_model"] = "m/one"

    _run_prepared_cli(
        tmp_path, monkeypatch,
        spec_path=_mutated_spec(tmp_path, mutate),
        prepared_kwargs={"model": "m/two"},
        calls=calls,
    )

    assert len(calls) == 1
    assert calls[0]["model"] == "m/two"


def test_prepared_child_ignores_phase_timeout(tmp_path, monkeypatch):
    """Probe 3: a source phase ``timeout: 999`` must not override the prepared ``77``."""
    calls: list[dict] = []

    def mutate(raw):
        for phase in raw["workflow"]["params"]["phases"]:
            if phase["name"] == "scope":
                phase["timeout"] = 999

    _run_prepared_cli(
        tmp_path, monkeypatch,
        spec_path=_mutated_spec(tmp_path, mutate),
        prepared_kwargs={"model": "m/two", "timeout": 77},
        calls=calls,
    )

    assert len(calls) == 1
    assert calls[0]["timeout"] == 77
