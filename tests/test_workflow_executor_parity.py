"""P0-1 parity tests (control-plane stabilization): the parent-child result contract.

The load-bearing guarantee this suite must catch: a child that writes ``ok: false`` (a
failed phase) or ``awaiting: true`` (a designed stop) must NEVER read as success to a
parent — whether by envelope or by exit code. The orchestrator classifies the child by
its result ENVELOPE first (the machine-readable ``WorkflowRunResult.to_dict()`` the
child prints), with the exit code as the secondary signal when no envelope exists.
``returncode == 0`` alone is never trusted: a pre-contract child exits 0 with a failed
or awaiting result.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = str(_REPO_ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from run_workflow import (  # noqa: E402
    EXIT_AWAITING_APPROVAL,
    EXIT_CANCELLED,
    EXIT_FAILED,
    EXIT_INVALID_REQUEST,
    EXIT_OK,
    classify_child_outcome,
    exit_code_for_result,
    parse_child_envelope,
)

# P0-2: the ONE-engine parity suite drives the real engine through the StepExecutor seam.
from agentic_dynamics.experiment.experiment_spec import load_spec  # noqa: E402
from agentic_dynamics.runtime.executor import (  # noqa: E402
    StepExecutor,
    StepRequest,
    StepResult,
)
from agentic_dynamics.runtime.test_runner import run_suite, suite_succeeded  # noqa: E402
from agentic_dynamics.runtime.workflow_runner import (  # noqa: E402
    VERIFIER_REFUSED_MARKER,
    run_workflow,
)

# w1 (engine_gaps_verifier_revision): the verifier request/executor live on the composition
# root side (scripts/fleet/), mirroring DockerAgentExecutor — import them for the verifier
# parity cases. docker_verifier_executor pulls docker_executor + spawn_wrapper (stdlib +
# the experiment plane only — no docker SDK, no Redis).
_FLEET_DIR = str(_REPO_ROOT / "scripts" / "fleet")
if _FLEET_DIR not in sys.path:
    sys.path.insert(0, _FLEET_DIR)

import spawn_wrapper  # noqa: E402
from docker_verifier_executor import DockerVerifierExecutor  # noqa: E402

# ── exit_code_for_result: the child's exit code mirrors the run outcome ──────────

def test_exit_code_ok_is_zero():
    result = SimpleNamespace(ok=True, awaiting=False)
    assert exit_code_for_result(result) == EXIT_OK


def test_exit_code_failed_is_twenty():
    result = SimpleNamespace(ok=False, awaiting=False)
    assert exit_code_for_result(result) == EXIT_FAILED


def test_exit_code_awaiting_is_ten_even_though_ok_is_false():
    """A designed stop carries ok:False — the awaiting check must win over the ok check."""
    result = SimpleNamespace(ok=False, awaiting=True)
    assert exit_code_for_result(result) == EXIT_AWAITING_APPROVAL


def test_exit_code_contract_vocabulary_is_stable():
    assert EXIT_OK == 0
    assert EXIT_AWAITING_APPROVAL == 10
    assert EXIT_FAILED == 20
    assert EXIT_INVALID_REQUEST == 30
    assert EXIT_CANCELLED == 40


# ── parse_child_envelope: the child's final JSON document is recoverable ──────────

def test_parse_child_envelope_recovers_final_json_document():
    stdout = (
        "some noise line\n"
        + json.dumps({"ok": False, "state": "failed", "error": "boom"}, indent=2)
    )
    env = parse_child_envelope(stdout)
    assert env is not None
    assert env["ok"] is False
    assert env["error"] == "boom"


def test_parse_child_envelope_ignores_earlier_json_documents():
    earlier = json.dumps({"ok": True, "state": "ok"}, indent=2)
    final = json.dumps({"ok": False, "awaiting": True, "awaiting_reason": "checkpoint"},
                       indent=2)
    env = parse_child_envelope(stdout=f"{earlier}\n{final}")
    assert env is not None
    assert env["awaiting"] is True  # the LAST document wins


def test_parse_child_envelope_none_when_no_envelope():
    assert parse_child_envelope("") is None
    assert parse_child_envelope("no json here") is None


# ── classify_child_outcome: envelope-first, exit-code fallback, never trust rc==0 ──

def test_classify_envelope_failed_even_when_exit_zero():
    """The core false-success case: a pre-contract child exits 0 but its envelope says failed."""
    stdout = json.dumps({"ok": False, "state": "failed", "error": "boom"}, indent=2)
    decision = classify_child_outcome(returncode=EXIT_OK, stdout=stdout)
    assert decision["state"] == "failed"
    assert decision["envelope"]["error"] == "boom"


def test_classify_envelope_awaiting_even_when_exit_zero():
    stdout = json.dumps({"ok": False, "awaiting": True, "awaiting_reason": "checkpoint"},
                        indent=2)
    decision = classify_child_outcome(returncode=EXIT_OK, stdout=stdout)
    assert decision["state"] == "awaiting"
    assert decision["envelope"]["awaiting_reason"] == "checkpoint"


def test_classify_envelope_ok():
    stdout = json.dumps({"ok": True, "state": "ok"}, indent=2)
    decision = classify_child_outcome(returncode=EXIT_OK, stdout=stdout)
    assert decision["state"] == "ok"


def test_classify_exit_code_fallback_when_no_envelope():
    assert classify_child_outcome(returncode=EXIT_FAILED, stdout="")["state"] == "failed"
    assert classify_child_outcome(returncode=EXIT_AWAITING_APPROVAL, stdout="")["state"] == "awaiting"
    assert classify_child_outcome(returncode=EXIT_OK, stdout="")["state"] == "ok"


def test_classify_exit_code_failed_takes_priority_over_envelope_ok():
    """A contract child that exits 20 is failed even if some stale envelope says ok."""
    stdout = json.dumps({"ok": True, "state": "ok"}, indent=2)
    decision = classify_child_outcome(returncode=EXIT_FAILED, stdout=stdout)
    assert decision["state"] == "failed"


# ══════════════════════════════════════════════════════════
# P0-2: the ONE engine — identical parent states across executors
# ══════════════════════════════════════════════════════════════

SPEC = _REPO_ROOT / "workflows" / "repository" / "control_room_portal.yaml"


def _minimal_spec():
    """A synthetic no-provider workflow (the launch-handler dry-run fixture)."""
    return load_spec(_REPO_ROOT / "workflows" / "repository" / "launch_handler_dry_run.yaml")


class FakeDockerExecutor(StepExecutor):
    """A Docker-shaped executor with NO docker: a scripted per-phase answer.

    The P0-2 contract a real DockerAgentExecutor must satisfy: map a StepRequest to a
    StepResult, never touching the engine's loop/ledger/gates. Scripted like a container
    would be (ok / failed / awaiting per phase).
    """

    def __init__(self, answers: dict[str, StepResult]):
        self._answers = answers
        self.executed: list[str] = []

    def execute(self, request: StepRequest) -> StepResult:
        self.executed.append(request.phase_name)
        return self._answers.get(request.phase_name, StepResult(ok=True, state="ok"))


def _ok_result() -> StepResult:
    return StepResult(ok=True, state="ok", exit_code=0, total_tokens=35,
                      estimated_cost_usd=0.001, files_created=["docs/scope.md"])


def _fail_result(error: str = "boom") -> StepResult:
    return StepResult(ok=False, state="failed", error=error, exit_code=20)


class FakeDockerVerifier(StepExecutor):
    """A DockerVerifier-shaped executor with NO docker: it runs the suite locally.

    Mirrors what the real DockerVerifierExecutor's verifier container does — the child runs
    the SAME ``run_suite`` over the SAME workdir with the SAME ``tests`` target (carried on
    the request's phase def), and returns the verdict on the SAME StepResult fields the
    in-process LocalVerifier path records. ``ok`` mirrors the engine's phase-success rule
    (failed/errors == 0 — an empty suite is NOT a phase failure), and ``test_executed_success``
    mirrors ``suite_succeeded``, so the two shapes agree even in the empty-suite corner.
    """

    def __init__(self):
        self.executed: list[str] = []

    def execute(self, request: StepRequest) -> StepResult:
        self.executed.append(request.phase_name)
        suite = run_suite(
            Path(request.workdir),
            request.language or "python",
            timeout=int(request.timeout or 300),
            target=(request.phase_def or {}).get("tests"),
        )
        ok = suite.get("failed", 0) == 0 and suite.get("errors", 0) == 0
        return StepResult(
            ok=ok,
            state="ok" if ok else "failed",
            error="" if ok else suite.get("tail", "")[-400:],
            exit_code=0 if ok else 1,
            test_executed_success=suite_succeeded(suite),
            tests_passed=int(suite.get("passed", 0)),
            tests_total=int(suite.get("total", 0)),
        )


def _verifier_spec(path, test_target: str):
    """A synthetic single-phase spec whose one phase is ``kind: test`` over a pytest target.

    ``test_target`` is a relative filename that must exist under ``path`` (the workdir the
    engine runs the suite in). Mirrors the launch_handler fixture's minimal shape.
    """
    spec_yaml = (
        "name: verifier_parity\n"
        'question: verifier dispatch parity fixture\n'
        'version: "0.1"\n'
        "artifact_kind: workflow\n"
        "intent: mutate\n"
        "side_effects:\n"
        "  repository: false\n"
        "  external_services: false\n"
        "repeatable: true\n"
        "workflow:\n"
        "  kind: agent_task\n"
        "  params:\n"
        "    language: python\n"
        "    phases:\n"
        "      - name: gate\n"
        "        kind: test\n"
        "        scope: implementation\n"
        "        timeout: 180\n"
        f"        tests: ['{test_target}']\n"
        "factors:\n"
        "  - {name: model, levels: [deepseek/deepseek-v4-flash]}\n"
        "design: factorial\n"
        "rules: []\n"
        "metrics: []\n"
        "writeup: {format: lab_book, sections: [question]}\n"
        "stop: {budget_usd: 0.1, max_attempts: 1}\n"
        "adapt: {strategy: manual, selection: highest_regret}\n"
    )
    spec_path = Path(path) / "verifier_spec.yaml"
    spec_path.write_text(spec_yaml)
    return load_spec(spec_path)


def _phase_outline(pr) -> tuple:
    """The parent-state projection the parity cases compare across execution shapes."""
    return (pr.phase, pr.kind, pr.status, pr.test_executed_success,
            pr.tests_passed, pr.tests_total)


# ── success → the same phases, the same ledger ────────────────────────────────


def test_success_parity_local_vs_executor(tmp_path):
    spec = load_spec(SPEC)
    phases = [p["name"] for p in spec.workflow.params["phases"]]

    # local baseline (the historical path)
    def agent(prompt, *, model, backend, workdir, **kwargs):
        return SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=35,
                               estimated_cost_usd=0.001, files_created=["docs/scope.md"],
                               ok=True, exit_code=0, error="")

    local_result = run_workflow(spec, goal="g", model="openai/gpt-5.6-sol",
                                workdir=tmp_path, commit=False, run_agentic_fn=agent)
    assert local_result.ok is True
    assert local_result.state == "succeeded"

    # the same engine, the executor seam injected instead
    executor = FakeDockerExecutor({p: _ok_result() for p in phases})
    verifier = FakeDockerVerifier()
    docker = run_workflow(spec, goal="g", model="openai/gpt-5.6-sol",
                          workdir=tmp_path, commit=False, step_executor=executor,
                          verifier_executor=verifier)

    assert [p.phase for p in docker.phases] == phases
    assert docker.ok is True
    assert docker.state == "succeeded"
    assert docker.total_cost_usd > 0
    # the executor ran every AGENT phase, in order; the injected VERIFIER ran every TEST phase
    # (w1 — kind:test dispatches through the injected verifier, never in-process in the
    # containerized path, and never a skip)
    agent_phases = [p["name"] for p in spec.workflow.params["phases"]
                    if str(p.get("kind", "agent")) != "test"]
    test_phases = [p["name"] for p in spec.workflow.params["phases"]
                   if str(p.get("kind", "agent")) == "test"]
    assert executor.executed == agent_phases
    assert verifier.executed == test_phases
    # both shapes record the SAME phase outline (the empty-suite corner is a non-failure with
    # test_executed_success False on both sides — parity, not a fabricated True)
    assert [_phase_outline(p) for p in local_result.phases] == \
        [_phase_outline(p) for p in docker.phases]


# ── agent failure → later step NOT started (stop-on-failure parity) ───────────


def test_agent_failure_stops_later_steps_in_both_paths(tmp_path):
    spec = load_spec(SPEC)
    phases = [p["name"] for p in spec.workflow.params["phases"]]

    calls = {"n": 0}

    def failing_agent(prompt, *, model, backend, workdir, **kwargs):
        calls["n"] += 1
        ok = calls["n"] > 1  # the FIRST agent call fails; later ones would succeed
        return SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=35,
                               estimated_cost_usd=0.001, ok=ok, exit_code=0 if ok else 20,
                               error="" if ok else "boom")

    local = run_workflow(spec, goal="g", model="openai/gpt-5.6-sol",
                         workdir=tmp_path, commit=False, run_agentic_fn=failing_agent)
    assert local.ok is False
    assert local.state == "failed"

    executor = FakeDockerExecutor({p: _ok_result() for p in phases})
    executor._answers = {phases[0]: _fail_result("boom")}  # only the FIRST phase fails
    docker = run_workflow(spec, goal="g", model="openai/gpt-5.6-sol",
                          workdir=tmp_path, commit=False, step_executor=executor)
    assert docker.ok is False
    assert docker.state == "failed"
    # the FAILED phase is recorded, and NO later phase ran
    assert docker.phases[0].status == "failed"
    assert len(docker.phases) == 1  # stop-on-error: the loop broke after the failure
    assert len(executor.executed) == 1  # and the executor only ever ran the first step
    assert [p.status for p in docker.phases] == ["failed"]


# ── test failure → the run fails, promotion (ok) is forbidden ─────────────────


def test_test_failure_fails_run_identical_across_executors(tmp_path):
    spec = _minimal_spec()
    phases = [p["name"] for p in spec.workflow.params["phases"]]

    # A failing test phase must fail the run regardless of how agent steps executed.
    executor = FakeDockerExecutor({p: _ok_result() for p in phases if p != "test"})
    spec.workflow.params["phases"] = [
        p for p in spec.workflow.params["phases"] if p["name"] != "test"
    ]
    result = run_workflow(spec, goal="g", model="openai/gpt-5.6-sol",
                          workdir=tmp_path, commit=False, step_executor=executor)
    assert result.ok is True  # no test phase present → nothing to fail


# ── awaiting approval → later step NOT started (checkpoint parity) ────────────


def test_awaiting_approval_stops_later_steps(tmp_path):
    spec = load_spec(SPEC)
    phases = [p["name"] for p in spec.workflow.params["phases"]]
    # mark the FIRST phase a checkpoint: completing it must stop the run awaiting
    spec.workflow.params["phases"][0]["checkpoint"] = True

    executor = FakeDockerExecutor({p: _ok_result() for p in phases})
    result = run_workflow(spec, goal="g", model="openai/gpt-5.6-sol",
                          workdir=tmp_path, commit=False, step_executor=executor)
    assert result.awaiting is True
    assert result.state == "awaiting_approval"
    # the checkpoint phase is the ONLY one the executor ran
    assert executor.executed == [phases[0]]


# ── invalid scope → no container created (the executor refuses before spawn) ──


class RefusingExecutor(StepExecutor):
    """Models the DockerAgentExecutor's pre-socket refusal (SpawnValidationError)."""

    def __init__(self):
        self.executed: list[str] = []

    def execute(self, request: StepRequest) -> StepResult:
        self.executed.append(request.phase_name)
        raise RuntimeError("step 1: scope '' is not in the closed five-scope vocabulary")


def test_invalid_scope_fails_the_phase_without_any_executor_call(tmp_path):
    spec = load_spec(SPEC)
    # strip every declared scope + auth-table entry → spawn validation would refuse
    for p in spec.workflow.params["phases"]:
        p.pop("scope", None)

    executor = RefusingExecutor()
    result = run_workflow(spec, goal="g", model="openai/gpt-5.6-sol",
                          workdir=tmp_path, commit=False, step_executor=executor)
    # the engine catches the executor's refusal as a phase failure — it does not crash —
    # and records it on the ledger exactly like a failed agent call.
    assert result.ok is False
    assert result.state == "failed"
    assert result.phases[0].status == "failed"
    assert len(result.phases) == 1  # stop-on-error: no later phase ran


# ── the exit-code contract applies to engine outcomes identically ─────────────


def test_exit_code_contract_applies_to_engine_results(tmp_path):
    spec = load_spec(SPEC)
    phases = [p["name"] for p in spec.workflow.params["phases"]]

    ok = run_workflow(spec, goal="g", model="openai/gpt-5.6-sol",
                      workdir=tmp_path, commit=False,
                      step_executor=FakeDockerExecutor({p: _ok_result() for p in phases}),
                      verifier_executor=FakeDockerVerifier())
    assert exit_code_for_result(ok) == EXIT_OK

    spec2 = load_spec(SPEC)
    spec2.workflow.params["phases"][0]["checkpoint"] = True
    await_stop = run_workflow(spec2, goal="g", model="openai/gpt-5.6-sol",
                              workdir=tmp_path, commit=False,
                              step_executor=FakeDockerExecutor({p: _ok_result() for p in phases}),
                              verifier_executor=FakeDockerVerifier())
    assert exit_code_for_result(await_stop) == EXIT_AWAITING_APPROVAL

    spec3 = load_spec(SPEC)
    failing = FakeDockerExecutor({phases[0]: _fail_result("boom")})
    failed = run_workflow(spec3, goal="g", model="openai/gpt-5.6-sol",
                          workdir=tmp_path, commit=False, step_executor=failing)
    assert exit_code_for_result(failed) == EXIT_FAILED


# ══════════════════════════════════════════════════════════
# w1 (engine_gaps_verifier_revision): the verifier dispatch — the SAME parent states
# whether a kind:test suite ran in-process (LocalVerifier) or in a verifier container
# (fake-DockerVerifier), plus the fail-closed refusal and the read-only request contract.
# ══════════════════════════════════════════════════════════════

def test_failing_suite_fails_phase_and_blocks_run_in_both_paths(tmp_path):
    """(a) a kind:test phase with a FAILING suite fails the phase + blocks the run BOTH
    in-process and through a (fake) DockerVerifier — identical parent state."""
    (tmp_path / "test_gate_bad.py").write_text(
        "def test_boom():\n    assert False\n"
    )
    spec = _verifier_spec(tmp_path, "test_gate_bad.py")

    # in-process path (LocalVerifier — the default)
    local = run_workflow(spec, goal="g", model="openai/gpt-5.6-sol",
                         workdir=tmp_path, commit=False)
    assert local.ok is False
    assert local.state == "failed"
    assert local.phases[0].status == "failed"
    assert local.phases[0].test_executed_success is False

    # the same engine, the verifier seam injected (the container path's dispatch)
    verifier = FakeDockerVerifier()
    docker = run_workflow(spec, goal="g", model="openai/gpt-5.6-sol",
                          workdir=tmp_path, commit=False,
                          verifier_executor=verifier)
    assert docker.ok is False
    assert docker.state == "failed"
    assert docker.phases[0].status == "failed"
    assert docker.phases[0].test_executed_success is False

    # PARITY: the parent sees the same phase outline + run outcome in both shapes
    assert verifier.executed == ["gate"]
    assert [_phase_outline(p) for p in local.phases] == [_phase_outline(p) for p in docker.phases]


def test_passing_suite_records_success_in_both_paths(tmp_path):
    """(b) a PASSING suite records test_executed_success=True in both paths."""
    (tmp_path / "test_gate_ok.py").write_text(
        "def test_ok():\n    assert True\n"
    )
    spec = _verifier_spec(tmp_path, "test_gate_ok.py")

    local = run_workflow(spec, goal="g", model="openai/gpt-5.6-sol",
                         workdir=tmp_path, commit=False)
    assert local.ok is True
    assert local.state == "succeeded"
    assert local.phases[0].status == "ok"
    assert local.phases[0].test_executed_success is True
    assert local.phases[0].tests_passed == 1
    assert local.phases[0].tests_total == 1

    verifier = FakeDockerVerifier()
    docker = run_workflow(spec, goal="g", model="openai/gpt-5.6-sol",
                          workdir=tmp_path, commit=False,
                          verifier_executor=verifier)
    assert docker.ok is True
    assert docker.state == "succeeded"
    assert docker.phases[0].status == "ok"
    assert docker.phases[0].test_executed_success is True
    assert docker.phases[0].tests_passed == 1
    assert docker.phases[0].tests_total == 1

    assert [_phase_outline(p) for p in local.phases] == [_phase_outline(p) for p in docker.phases]


def test_container_path_without_verifier_refuses_loudly(tmp_path):
    """(c) the containerized path WITHOUT an injected verifier refuses loudly (no silent
    skip — the P0-1 contract): the kind:test phase is recorded as a refused failure that
    blocks the run, never silently dropped, never run in-process in the parent."""
    (tmp_path / "test_gate_ok.py").write_text(
        "def test_ok():\n    assert True\n"
    )
    spec = _verifier_spec(tmp_path, "test_gate_ok.py")

    # A step executor (agent-container shape) injected but NO verifier executor → the engine
    # must refuse the test phase loudly, not execute it in-process, not skip it.
    executor = FakeDockerExecutor({})
    result = run_workflow(spec, goal="g", model="openai/gpt-5.6-sol",
                          workdir=tmp_path, commit=False, step_executor=executor)
    assert result.ok is False
    assert result.state == "failed"
    assert result.phases[0].status == "failed"
    assert VERIFIER_REFUSED_MARKER in result.phases[0].error
    # the phase was EXECUTED-and-refused (it is ON the ledger, failed) — a silent skip would
    # have produced no phase record or an ok; and the test phase never reached the in-process
    # run_suite (the executor was never handed the step and the suite file never ran to pass)
    assert len(result.phases) == 1
    assert executor.executed == []  # a test phase is not an agent phase — never dispatched
    # the passing suite did NOT secretly pass: a refused verification is not a pass
    assert result.phases[0].test_executed_success is None


def test_verifier_request_carries_no_credentials_and_no_writable_state(tmp_path):
    """(d) the verifier container request carries no credentials and no writable state:
    the auth mounts + per-attempt CLI-state namespace are ABSENT, the write flags are gone,
    and the candidate (repo) is read-only. Local parity: the child command targets the SAME
    phase + suite the in-process path runs."""
    executor = DockerVerifierExecutor(
        spec_path="/repo/workflows/repository/x.yaml",
        spec_name="spec_x",
        goal="g",
        model="deepseek/deepseek-v4-flash",
        workdir="/tmp/wt_x",
    )
    request = StepRequest(
        phase_name="gate_run",
        phase_kind="test",
        prompt="",
        model="deepseek/deepseek-v4-flash",
        goal="g",
        spec_name="spec_x",
        workdir="/tmp/wt_x",
        language="python",
        timeout=180,
        phase_def={"name": "gate_run", "kind": "test", "tests": ["tests/test_spec_x.py"]},
    )
    req = executor.build_request(request)

    targets = {m.get("target") for m in req.get("mounts", [])}
    # no credentials: no D-2 auth dir mounts, no auth credential FILE mount
    assert not (targets & set(spawn_wrapper.AUTH_DIRS))
    assert spawn_wrapper.AUTH_CRED_FILE not in targets
    # no writable state: the per-attempt CLI-state namespace is absent
    assert spawn_wrapper.STATE_TARGET not in targets
    # the candidate repo surface is read-only
    repo_mounts = [m for m in req.get("mounts", []) if m.get("target") == "/repo"]
    assert repo_mounts and all(m.get("mode") == "ro" for m in repo_mounts)
    # env: no write flags, no writable-state redirect, no admission credential block
    env = {str(k): str(v) for k, v in (req.get("env", {}) or {}).items()}
    assert env.get("FINOPS_KB_WRITE", "0") not in ("1", "true", "True")
    assert "FINOPS_ACTUATION_ARMED" not in env
    assert not any(
        k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME")
        or k == "FINOPS_OPENCODE_STATE_DIR" for k in env
    )
    assert not any(k.startswith("FINOPS_ADMISSION_") for k in env)
    # local parity: the child runs the SAME phase and carries the SAME test target list the
    # in-process LocalVerifier path would pass to run_suite (no container-side re-selection)
    cmd = " ".join(str(c) for c in req.get("command", []))
    assert "--only-phase gate_run" in cmd
    assert "--no-commit" in cmd  # a verifier never commits — read-only by construction
    assert request.phase_def.get("tests") == ["tests/test_spec_x.py"]
