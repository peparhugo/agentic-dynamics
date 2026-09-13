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

import json
import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src", _ROOT / "scripts", _ROOT / "scripts" / "fleet"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import spawn_wrapper  # noqa: E402
from docker_verifier_executor import DockerVerifierExecutor  # noqa: E402

from agentic_dynamics.experiment.experiment_spec import load_spec  # noqa: E402
from agentic_dynamics.runtime.executor import StepRequest  # noqa: E402
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
    # BOTH verification shapes dispatched to the verifier — the native gate and the spec's
    # explicit test phase — as CONCRETE kind:test boundaries: one contract, two callers.
    # The native gate used to dispatch as the producing phase's kind:agent, which the real
    # DockerVerifierExecutor refuses (Astra ae212a0 finding 3).
    assert [(r.phase_name, r.phase_kind) for r in verifier.requests] == [
        ("scope__test_gate", "test"),
        ("verify", "test"),
    ]
    assert phase.tests_total == 3 and phase.tests_passed == 3
    assert phase.test_executed_success is True
    assert phase.status != "failed"


def test_native_gate_request_is_a_concrete_test_boundary(tmp_path):
    """A producing agent phase's native gate builds a concrete test-only boundary.

    The request carries ``kind=test`` and the gate's own suite/target/candidate — never the
    producing phase's kind, prompt or ``test_gate`` marker (an agent child must not retain or
    execute the parent workflow's gates).
    """
    spec = _with_gate(load_spec(SPEC))
    spec.workflow.params["phases"][0]["scope"] = "implementation"
    spec.workflow.params["phases"][0]["tests"] = ["tests/test_boundary.py"]
    verifier = _FakeVerifier(
        SimpleNamespace(ok=True, tests_passed=1, tests_total=1, test_executed_success=True,
                        error="")
    )
    run_workflow(
        spec, goal="g", model="m/one", workdir=tmp_path, commit=False,
        run_agentic_fn=lambda *a, **k: _agent(), verifier_executor=verifier,
    )
    native = verifier.requests[0]
    assert native.phase_kind == "test"          # never the producing agent's kind
    assert native.phase_def["kind"] == "test"
    assert native.phase_def["tests"] == ["tests/test_boundary.py"]
    assert native.phase_def["scope"] == "implementation"
    # the producing phase's own markers are NOT retained
    assert "test_gate" not in native.phase_def
    assert "prompt" not in native.phase_def
    boundary = native.test_boundary
    assert boundary is not None
    assert boundary.phase_name == "scope__test_gate"
    assert boundary.suite == ["tests/test_boundary.py"]     # the concrete suite/target
    assert boundary.candidate == str(tmp_path)              # the concrete candidate
    assert boundary.language == "python"
    assert boundary.scope == "implementation"


def _canned_verifier_outcome() -> dict:
    """A sibling outcome carrying a passing test-phase envelope (the classify contract)."""
    envelope = {
        "spec_name": "spec_x", "state": "succeeded", "ok": True, "awaiting": False,
        "phases": [{
            "phase": "scope__test_gate", "kind": "test", "status": "ok",
            "test_executed_success": True, "tests_passed": 1, "tests_total": 1, "error": "",
        }],
    }
    return {
        "ok": True, "argv": ["docker", "run", "--rm", "-i"], "returncode": 0,
        "stdout": "noise\n" + json.dumps(envelope, indent=2), "stderr": "",
    }


def test_real_executor_accepts_the_constructed_boundary_and_refuses_agent_kind(
    tmp_path, monkeypatch
):
    """The REAL DockerVerifierExecutor guard: accepts the engine's boundary, refuses agent.

    This is the reproduction the review demanded a real contract for — the permissive fake
    accepted an agent-kind request production refuses. Here the real executor's ``execute``
    runs for real (only the docker boundary, ``spawn_sibling``, is injected), so the gate is
    the production gate.
    """
    spec = _with_gate(load_spec(SPEC))
    spec.workflow.params["phases"][0]["scope"] = "implementation"
    spec.workflow.params["phases"][0]["tests"] = ["tests/test_boundary.py"]
    capture = _FakeVerifier(
        SimpleNamespace(ok=True, tests_passed=1, tests_total=1, test_executed_success=True,
                        error="")
    )
    run_workflow(
        spec, goal="g", model="m/one", workdir=tmp_path, commit=False,
        run_agentic_fn=lambda *a, **k: _agent(), verifier_executor=capture,
    )
    boundary_request = capture.requests[0]

    executor = DockerVerifierExecutor(
        spec_path="/repo/workflows/repository/control_room_portal.yaml",
        spec_name="control_room_portal", goal="g", model="m/one", workdir=str(tmp_path),
    )
    spawned: list[dict] = []

    def fake_spawn(request, **kwargs):
        spawned.append(request)
        return _canned_verifier_outcome()

    monkeypatch.setattr(spawn_wrapper, "spawn_sibling", fake_spawn)

    verdict = executor.execute(boundary_request)
    assert spawned, "the guard refused a concrete kind:test boundary"
    assert verdict.state == "ok"
    assert verdict.test_executed_success is True and verdict.tests_total == 1

    # an AGENT-kind request is refused before the broker is ever reached
    spawned.clear()
    agent_request = StepRequest(
        phase_name="scope", phase_kind="agent", prompt="do work", model="m/one", goal="g",
        spec_name="control_room_portal", workdir=str(tmp_path),
        phase_def={"name": "scope", "kind": "agent", "test_gate": True},
    )
    refused = executor.execute(agent_request)
    assert refused.state == "refused"
    assert "VERIFIER_REFUSED" in refused.error
    assert spawned == []


def test_verifier_child_never_reloads_the_producing_phase_by_name(tmp_path):
    """No reload-by-name path: the verifier child loads a GENERATED boundary spec.

    The child command must not point at the original spec or ``--only-phase`` the producing
    agent phase — that reload would re-run the agent and its parent gates inside the verifier.
    """
    spec = _with_gate(load_spec(SPEC))
    spec.workflow.params["phases"][0]["scope"] = "implementation"
    spec.workflow.params["phases"][0]["tests"] = ["tests/test_boundary.py"]
    capture = _FakeVerifier(
        SimpleNamespace(ok=True, tests_passed=1, tests_total=1, test_executed_success=True,
                        error="")
    )
    run_workflow(
        spec, goal="g", model="m/one", workdir=tmp_path, commit=False,
        run_agentic_fn=lambda *a, **k: _agent(), verifier_executor=capture,
    )
    request = capture.requests[0]
    executor = DockerVerifierExecutor(
        spec_path="/repo/workflows/repository/control_room_portal.yaml",
        spec_name="control_room_portal", goal="g", model="m/one", workdir=str(tmp_path),
    )
    spawn_request = executor.build_request(request)
    command = [str(c) for c in spawn_request.get("command", [])]
    command_text = " ".join(command)

    # it runs the boundary phase, never the producing agent phase
    assert "--only-phase scope__test_gate" in command_text
    assert "--only-phase scope " not in command_text
    # and it loads the generated boundary, never the original spec
    spec_arg = command[command.index("--spec") + 1]
    assert spec_arg.endswith(".verify.json")
    assert "/repo/workflows/repository/control_room_portal.yaml" not in command_text
    generated = Path(spec_arg)
    assert generated.is_file()
    document = json.loads(generated.read_text())
    phase = document["workflow"]["params"]["phases"][0]
    assert phase["kind"] == "test"
    assert phase["tests"] == ["tests/test_boundary.py"]
    assert "prompt" not in phase and "test_gate" not in phase
    assert document["workflow"]["params"]["language"] == "python"

    # the generated boundary is a RUNNABLE test-only execution boundary: the engine runs the
    # suite and NEVER invokes the producing agent (which would re-execute the parent's work
    # in a credential-less verifier cell).
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_boundary.py").write_text(
        "def test_boundary_ok():\n    assert True\n"
    )

    def _must_not_run(*args, **kwargs):  # pragma: no cover - the assertion IS the contract
        raise AssertionError("the verifier child must never invoke the producing agent")

    boundary_spec = load_spec(generated)
    result = run_workflow(
        boundary_spec, goal="g", model="m/one", workdir=tmp_path, commit=False,
        run_agentic_fn=_must_not_run,
    )
    assert result.ok is True
    assert [p.kind for p in result.phases] == ["test"]
    assert result.phases[0].test_executed_success is True
    assert result.phases[0].tests_total == 1


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
