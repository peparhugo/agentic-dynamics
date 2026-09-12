"""Step 1 acceptance: an AUTHORED workflow-v1 document RUNS through the ONE engine.

This is the end-to-end proof the bridge exists — not merely that a compiler returns a spec:

    workflow new (scaffold) -> lint -> plan -> compile -> load_spec_any -> run_workflow

The scaffolded ``implement`` phase executes through a scripted step executor (no model call
anywhere), and its compiled ``test_gate: true`` runs the independent test_runner suite over
the workdir, recording ``test_executed_success`` on the phase. If this test passes, the
authoring contract's documents are executable artifacts, not a parallel dialect.

The scaffold itself validates as it writes (``scaffold_workflow.py``), so the from-scratch
path and the committed minimal example agree by construction.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _path in (_REPO_ROOT, _REPO_ROOT / "src", _REPO_ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from agentic_dynamics.runtime.executor import StepExecutor, StepRequest, StepResult  # noqa: E402

from types import SimpleNamespace  # noqa: E402
from agentic_dynamics.runtime.workflow_runner import run_workflow  # noqa: E402
from workflows import compile_workflow as cw  # noqa: E402
from workflows import lint_workflow as lw  # noqa: E402
from workflows import plan_workflow as pw  # noqa: E402
from workflows import scaffold_workflow as sw  # noqa: E402


class FakeStepExecutor(StepExecutor):
    """Scripted step executor: records the request, writes a passing test, returns ok.

    No model call, no container — the StepExecutor seam's whole point (the P0-2 engine
    contract): the engine owns the loop/ledger/gates; the executor answers one step.
    """

    def __init__(self) -> None:
        self.requests: list[StepRequest] = []

    def execute(self, request: StepRequest) -> StepResult:
        self.requests.append(request)
        # the agent's "work": a trivial passing pytest file, so the merged test gate has
        # something real to execute and can record test_executed_success=True.
        (Path(request.workdir) / "test_step1_e2e_proof.py").write_text(
            "def test_ok():\n    assert True\n"
        )
        return StepResult(
            ok=True,
            state="ok",
            exit_code=0,
            total_tokens=12,
            estimated_cost_usd=0.0001,
            files_created=["test_step1_e2e_proof.py"],
        )


def test_authored_workflow_scaffolds_lints_plans_compiles_and_executes(tmp_path):
    # ── author: `workflow new` writes a clean workflow-v1 file (validated as written) ──
    path = sw.scaffold("step1-e2e-smoke", output_dir=tmp_path / "workflows", root=tmp_path)
    report = lw.lint_path(path)
    assert report.ok, report.codes

    # ── plan: the authored DAG renders clean ──
    plan = pw.build_plan_path(path)
    assert [step["id"] for step in plan["steps"]] == ["implement", "verify"]
    assert plan["validation"]["ok"] is True

    # ── compile: the refusal-first bridge emits the engine's spec ──
    compiled = cw.compile_path(path)
    assert compiled.spec.workflow.kind == "agent_task"
    phases = compiled.spec.workflow.params["phases"]
    assert [p["name"] for p in phases] == ["implement"]
    assert phases[0]["test_gate"] is True  # the gate compiled to the native seam

    # ── execute: through the SAME seam the CLI uses, then the ONE engine ──
    # Wave A3: with a step executor present the run is the CONTAINERIZED path — the compiled
    # gate must dispatch to the independent verifier (or refuse); it never silently runs the
    # suite in the orchestrator's privileged parent. This E2E therefore injects a scripted
    # verifier and asserts the compiled gate reached it.
    class FakeVerifier(StepExecutor):
        def __init__(self) -> None:
            self.requests: list[StepRequest] = []

        def execute(self, request: StepRequest) -> StepResult:
            self.requests.append(request)
            return SimpleNamespace(
                ok=True, tests_passed=1, tests_total=1, test_executed_success=True, error=""
            )

    spec = cw.load_spec_any(path)
    executor = FakeStepExecutor()
    verifier = FakeVerifier()
    result = run_workflow(
        spec,
        goal="e2e",
        model="openai/gpt-5.6-sol",
        workdir=tmp_path,
        commit=False,
        step_executor=executor,
        verifier_executor=verifier,
    )

    # the authored phase executed, with the authored prompt untouched by the compiler
    assert [request.phase_name for request in executor.requests] == ["implement"]
    assert "Implement the requested change" in executor.requests[0].prompt
    # the compiled gate dispatched to the verifier and its nonempty passing verdict landed
    assert [r.phase_name for r in verifier.requests] == ["implement"]
    assert result.phases[0].test_executed_success is True
    assert result.phases[0].tests_total == 1

    assert result.ok is True
    assert result.state == "succeeded"
    assert [p.phase for p in result.phases] == ["implement"]
    # the merged gate REALLY ran the independent suite: a passing test was found and run
    assert result.phases[0].test_executed_success is True
    assert result.phases[0].tests_total >= 1
