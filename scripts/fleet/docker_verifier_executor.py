"""DockerVerifierExecutor — the READ-ONLY sibling verifier (w1, engine_gaps_verifier_revision).

Implements ``runtime.executor.StepExecutor`` for ``kind: test`` phases: run ONE declared
independent verification (the phase's suite) inside a READ-ONLY verifier container bound to
the candidate SHA and return a structured :class:`StepResult` carrying the verdict on the
SAME fields the in-process LocalVerifier path fills (``test_executed_success`` /
``tests_passed`` / ``tests_total``), from the SAME source semantics — the container runs the
suite, and the exit + report are the verdict. Never the agent's self-report: the verifier
makes NO model call, so the container carries NO credentials and NO writable CLI-state
namespace (see ``spawn_wrapper.build_verifier_request``).

Mirrors ``fleet.docker_executor.DockerAgentExecutor`` (the P0-2 sibling-cell pattern): it is
the composition-root side of the one engine's verifier dispatch seam. The child runs
``run_workflow.py --only-phase <name> --no-commit`` inside the container — the normal
single-phase path, whose ``kind: test`` branch executes the suite in-process via
``test_runner.run_suite`` inside the verifier (LocalVerifier). The parent classifies the child
by its result envelope first (``ok``/``awaiting``/``state``), the exit code second, exactly
like the agent executor — a pre-contract child that exits 0 with ``ok:false`` is failed,
never success. The verdict fields are pulled from the child's phase record, so the parent and
the engine record the exact object the independent runner produced.

The engine dispatches a ``kind: test`` phase through this executor ONLY when it is injected at
the composition root (under ``--orchestrator``); absent the injection the in-process run_suite
path is unchanged, and a containerized run with a step executor but NO verifier refuses loudly
(``VERIFIER_REFUSED``, never a skip — the P0-1 fail-closed contract).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from agentic_dynamics.runtime.executor import StepExecutor, StepRequest, StepResult

# scripts/fleet/ is a dir, not a package — add it beside scripts/ so the sibling modules
# (spawn_wrapper, docker_executor) import.
_FLEET_DIR = str(Path(__file__).resolve().parent)
if _FLEET_DIR not in sys.path:
    sys.path.insert(0, _FLEET_DIR)

import spawn_wrapper  # noqa: E402
from docker_executor import _classify, _phase_from_envelope  # noqa: E402


class DockerVerifierExecutor(StepExecutor):
    """Run each ``kind: test`` phase as a READ-ONLY sibling verifier container.

    ``spec_path`` is the spec path AS THE SIBLING SEES IT (the launch broker mounts the repo at
    ``/repo`` read-only per the verifier mount profile, so ``/repo/<spec>``); ``spec_name`` is
    the workflow's name; ``cell_image`` is the sibling's image (``fleet/job-<name>`` or the
    default cell base), carried on the typed request.

    ``run_clone`` (b2_ephemeral_clone, fleet_launch_boundary Wave 2) is the run's private
    ephemeral clone path. When set, the verifier request references it too (a test phase
    verifies against the run's clone — the suite runs in the read-only clone), so the launch
    broker can validate the reference and a later wave can bind the clone mount read-only for
    the verifier. It may be passed explicitly or inherited from ``FINOPS_RUN_CLONE``; absent
    both, requests carry no clone (pre-b2 shape).
    """

    def __init__(
        self,
        *,
        spec_path: str,
        spec_name: str,
        goal: str,
        model: str,
        workdir: str,
        backend: str | None = None,
        timeout: int = 1800,
        cell_image: str | None = None,
        run_clone: str | None = None,
    ):
        self._spec_path = spec_path
        self._spec_name = spec_name
        self._goal = goal
        self._model = model
        self._workdir = workdir
        self._backend = backend
        self._timeout = timeout
        self._cell_image = cell_image
        self._run_clone = run_clone or os.environ.get("FINOPS_RUN_CLONE")

    def build_request(self, request: StepRequest) -> dict[str, Any]:
        """Build the READ-ONLY verifier spawn request for ``request`` (pure, no docker).

        The request is what test (d) of the w1 parity suite inspects: it carries NO
        credentials and NO writable CLI-state namespace (see
        ``spawn_wrapper.build_verifier_request``), and its child command runs the SAME
        suite the in-process LocalVerifier path would run (same ``tests`` target, carried
        on the phase def) inside the container — the local-parity target list. The run's
        clone path (b2), when one is configured, is carried as a top-level reference for
        the launch broker to mount read-only.
        """
        sibling_cmd = [
            sys.executable, "scripts/run_workflow.py",
            "--spec", self._spec_path,
            "--goal", self._goal,
            "--model", self._model,
            "--workdir", self._workdir,
            "--only-phase", request.phase_name,
            "--timeout", str(request.timeout or self._timeout),
            # A test phase never commits; --no-commit is belt-and-braces. The verifier's
            # read-only-for-candidate contract is now ENFORCED at the mount (g1_verifier_mount:
            # build_verifier_request mounts the candidate's worktree + git dirs ro and
            # validate_spawn refuses any request that would mount them rw) — never behavioral.
            "--no-commit",
        ]
        if self._backend or request.backend:
            sibling_cmd += ["--backend", self._backend or request.backend]

        # The verifier has NO admission context by construction: kind:test phases run outside
        # the engine's per-phase admission scope (there is no model call to reserve spend for),
        # so no lease block is stamped and none is read. The cell image + docker-side timeout
        # ride on the typed request (b3_launch_broker) like the agent executor's.
        return spawn_wrapper.build_verifier_request(
            request.phase_def,
            goal=self._goal,
            workdir=self._workdir,
            model=self._model,
            spec_name=self._spec_name,
            command=sibling_cmd,
            run_clone=self._run_clone,
            image=self._cell_image,
            timeout_seconds=request.timeout or self._timeout or 0,
        )

    def execute(self, request: StepRequest) -> StepResult:
        """Spawn one READ-ONLY verifier sibling for ``request`` and classify its outcome.

        Defensively refuses any non-``kind: test`` step (the engine only dispatches test
        phases here, but an executor never silently runs an agent phase): the failure is a
        loud refusal StepResult, never a pass and never a skip.
        """
        if request.phase_kind != "test":
            return StepResult(
                ok=False,
                state="refused",
                error=(
                    f"VERIFIER_REFUSED: DockerVerifierExecutor only executes kind:test phases "
                    f"(got kind {request.phase_kind!r}) — refusing, never a skip"
                ),
                exit_code=20,
            )

        verifier_request = self.build_request(request)
        try:
            outcome = spawn_wrapper.spawn_sibling(verifier_request)
        except Exception as exc:  # noqa: BLE001 — a spawn refusal is a failed verdict, never a crash
            return StepResult(
                ok=False,
                state="failed",
                error=f"VERIFIER_ERROR: spawn refused: {exc!r}"[:800],
                exit_code=20,
            )

        decision = _classify(outcome)
        state = decision["state"]
        envelope = decision.get("envelope") or {}

        sr = StepResult(
            ok=state == "ok",
            state=state,
            error=str(envelope.get("error") or outcome.get("stderr", ""))[:800],
            exit_code=int(outcome.get("returncode", -1) or -1),
        )
        phase = _phase_from_envelope(envelope)
        if phase is not None:
            # The verdict object is the child phase's own record — test_executed_success /
            # tests_passed / tests_total produced by the independent runner inside the
            # verifier container. Same field names, same source semantics as in-process.
            sr.test_executed_success = phase.get("test_executed_success")
            sr.tests_passed = int(phase.get("tests_passed", 0) or 0)
            sr.tests_total = int(phase.get("tests_total", 0) or 0)
        return sr
