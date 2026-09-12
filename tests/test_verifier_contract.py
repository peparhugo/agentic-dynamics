"""Wave A3 — one verifier contract: dispatch parity, required-empty refusal, gated acceptance.

Pins the review's #5 reproductions:

* a REQUIRED native ``test_gate`` with zero tests is a false green — the phase must FAIL
  (it previously read ``ok=True`` while recording ``test_executed_success=False``);
* the native gate dispatches to the independent verifier executor when one is present (the
  same three-way contract the explicit ``kind: test`` phase uses) and REFUSES when the
  containerized path has no verifier — never a silent local run in the privileged parent;
* multi-attempt records finalize ``accepted`` from the GATED phase outcome, never the
  adapter's pre-gate status (the review's escalation reproduction: final gate fails while
  the final attempt still recorded accepted=True).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.experiment.experiment_spec import load_spec  # noqa: E402
from agentic_dynamics.runtime.workflow_runner import run_workflow  # noqa: E402

SPEC = _ROOT / "workflows" / "repository" / "control_room_portal.yaml"


def _agent(**overrides):
    base = dict(
        ok=True, exit_code=0, error="", prompt_tokens=1, completion_tokens=1,
        reasoning_tokens=0, total_tokens=2, estimated_cost_usd=0.001,
        files_created=[], files_modified=[], final_response="x",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _with_gate(spec, *, escalation: bool = False):
    spec.workflow.params["phases"][0]["test_gate"] = True
    if escalation:
        spec.workflow.params["escalation"] = {"ladder": ["m/one", "m/two"]}
    return spec


def test_required_native_gate_refuses_a_zero_test_suite(tmp_path):
    """#5b: total 0 is a FAILURE for a required gate — never a false green."""
    spec = _with_gate(load_spec(SPEC))
    result = run_workflow(
        spec, goal="g", model="m/one", workdir=tmp_path, commit=False,
        run_agentic_fn=lambda *a, **k: _agent(),
    )
    phase = result.phases[0]
    assert phase.status == "failed"
    assert phase.tests_total == 0
    assert phase.test_executed_success is False
    assert "TEST_GATE" in phase.error or "no tests" in phase.error
    assert result.ok is False


class _FakeVerifier:
    """The dispatched-verifier shape: records requests, returns a scripted StepResult."""

    def __init__(self, verdict: SimpleNamespace):
        self.verdict = verdict
        self.requests: list = []

    def execute(self, request):
        self.requests.append(request)
        return self.verdict


def test_native_gate_dispatches_to_the_injected_verifier(tmp_path):
    """Dispatch parity: the native gate uses the independent verifier when present."""
    spec = _with_gate(load_spec(SPEC))
    verifier = _FakeVerifier(
        SimpleNamespace(ok=True, tests_passed=3, tests_total=3, test_executed_success=True,
                        error="")
    )
    result = run_workflow(
        spec, goal="g", model="m/one", workdir=tmp_path, commit=False,
        run_agentic_fn=lambda *a, **k: _agent(), verifier_executor=verifier,
    )
    phase = result.phases[0]
    # BOTH verification shapes dispatched to the verifier — the native gate (scope, agent
    # kind) and the spec's explicit test phase (verify, test kind): one contract, two callers.
    assert [(r.phase_name, r.phase_kind) for r in verifier.requests] == [
        ("scope", "agent"),
        ("verify", "test"),
    ]
    assert phase.tests_total == 3 and phase.tests_passed == 3
    assert phase.test_executed_success is True
    assert phase.status != "failed"


def test_native_gate_refuses_an_empty_verifier_verdict(tmp_path):
    """The required-empty rule applies to the DISPATCHED shape too — one contract."""
    spec = _with_gate(load_spec(SPEC))
    verifier = _FakeVerifier(
        SimpleNamespace(ok=True, tests_passed=0, tests_total=0, test_executed_success=False,
                        error="")
    )
    result = run_workflow(
        spec, goal="g", model="m/one", workdir=tmp_path, commit=False,
        run_agentic_fn=lambda *a, **k: _agent(), verifier_executor=verifier,
    )
    assert result.phases[0].status == "failed"
    assert "TEST_GATE" in result.phases[0].error


def test_multi_attempt_acceptance_is_finalized_after_the_gate(tmp_path):
    """#5a: the escalated final attempt must NOT record accepted=True once the gate fails it."""
    spec = _with_gate(load_spec(SPEC), escalation=True)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        return _agent(ok=model != "m/one", exit_code=0 if model != "m/one" else 1)

    result = run_workflow(
        spec, goal="g", model="m/one", workdir=tmp_path, commit=False, run_agentic_fn=agent,
    )
    assert result.phases[0].status == "failed"  # the empty required gate failed the phase
    first, second = result.attempts[:2]
    assert first.accepted is False
    assert second.accepted is False  # was True pre-fix (pre-gate adapter status)
    assert first.first_pass is False and second.first_pass is None
