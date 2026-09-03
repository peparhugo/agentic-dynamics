"""DockerAgentExecutor — the P0-2 sibling-container step executor (composition root side).

Implements ``runtime.executor.StepExecutor``: run ONE agent phase inside a sibling
container (scope-driven mounts/network/env, validated by the spawn wrapper BEFORE any
socket call) and return a structured :class:`StepResult`. This is the executor the
``--orchestrator`` flag injects into the ONE workflow engine — it never reimplements
the phase loop, stop-on-failure, checkpoints, gates, or the ledger; the engine owns
all of those (P0-2, control-plane stabilization).

The child runs ``run_workflow.py --only-phase <name>`` inside the container — the
normal single-phase path, with the P0-1 exit-code contract + result envelope. The
executor classifies the child by its envelope first (``ok``/``awaiting``/``state``),
the exit code second, exactly like ``run_workflow.py:classify_child_outcome`` — a
pre-contract child that exits 0 with ``ok:false`` is failed, never success.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from agentic_dynamics.runtime.executor import StepExecutor, StepRequest, StepResult

# scripts/fleet/ is a dir, not a package — add it beside scripts/ so the wrapper imports.
_FLEET_DIR = str(Path(__file__).resolve().parent)
if _FLEET_DIR not in sys.path:
    sys.path.insert(0, _FLEET_DIR)

import spawn_wrapper  # noqa: E402


class DockerAgentExecutor(StepExecutor):
    """Run each agent phase as a sibling cell container with its scope config.

    ``spec_path`` is the spec path AS THE SIBLING SEES IT (the launch broker mounts the repo
    at ``/repo`` per the request's mount profile, so ``/repo/<spec>``); ``spec_name`` is the
    workflow's name used for the per-attempt state namespace; ``cell_image`` is the sibling's
    image (``fleet/job-<name>`` or the default cell base), carried on the typed request.

    ``run_clone`` (fb1_clone_mounted — the clone is the cell's world) is the run's private
    ephemeral clone path (``PathConfig.runs_root/<run-id>/repo``). When set, every phase
    request this executor builds carries it (``build_phase_request(run_clone=...)``) and mounts
    the clone as the cell's repo — the launch broker binds ``runs_root/<run-id>/repo`` at
    ``/repo`` (rw for this commit-capable cell) and the shared worktree/``.git`` surface is
    absent from the request. It may be passed explicitly or inherited from the
    ``FINOPS_RUN_CLONE`` env var (a host-side launcher exports it to the workflow-runner tier);
    absent both, requests carry no clone — the pre-b2 shared-worktree shape unchanged.
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
        """Build the sibling-cell spawn request for ``request`` (pure, no docker).

        The admission in force (the engine entered ``phase_admission_scope`` before calling
        us) is stamped onto the spawn request as the lease block — a container inherits an
        environment, not a ContextVar. The run's clone path (fb1_clone_mounted), when one is
        configured, is carried on the request so the launch broker mounts the clone as the
        cell's repo — and the child runs INSIDE the clone (its ``--workdir`` is the clone's
        container mount point ``/repo``), so the cell's git operations and commits happen
        against ITS clone, never the shared worktree.
        """
        from agentic_dynamics.core.admission_context import current_context

        # fb1_clone_mounted: with a run clone the sibling operates in the clone, mounted at
        # /repo (spawn_wrapper/launch_broker REPO_TARGET) — the shared /tmp worktree namespace
        # is no longer mounted, so the cell's workdir IS the clone. Without a clone the cell
        # keeps operating in the shared-worktree path (pre-b2 shape, unchanged).
        sibling_workdir = spawn_wrapper.REPO_TARGET if self._run_clone else self._workdir
        sibling_cmd = [
            sys.executable, "scripts/run_workflow.py",
            "--spec", self._spec_path,
            "--goal", self._goal,
            "--model", self._model,
            "--workdir", sibling_workdir,
            "--only-phase", request.phase_name,
            "--timeout", str(request.timeout or self._timeout),
        ]
        if self._backend or request.backend:
            sibling_cmd += ["--backend", self._backend or request.backend]

        admission = current_context()
        return spawn_wrapper.build_phase_request(
            request.phase_def,
            goal=self._goal,
            workdir=sibling_workdir,
            model=self._model,
            spec_name=self._spec_name,
            command=sibling_cmd,
            admission=admission,
            run_clone=self._run_clone,
            # P0-3: a per-attempt state namespace — <spec>/<phase>/ — so retries and
            # concurrent phases never share a writable CLI-state directory.
            state_namespace=f"{self._spec_name}/{request.phase_name}",
            # b3_launch_broker: the cell image + docker-side timeout ride on the TYPED request
            # (image_digest / timeout_seconds) — the executor no longer passes them to a docker
            # call of its own; the broker validates + executes them.
            image=self._cell_image,
            timeout_seconds=request.timeout or self._timeout or 0,
        )

    def execute(self, request: StepRequest) -> StepResult:
        """Spawn one sibling cell for ``request`` (via the launch broker) and classify its outcome."""
        phase_request = self.build_request(request)
        outcome = spawn_wrapper.spawn_sibling(phase_request)
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
            sr.session_id = str(phase.get("session_id", "") or "")
            sr.total_tokens = int(phase.get("tokens", {}).get("total", 0) or 0)
            sr.prompt_tokens = int(phase.get("tokens", {}).get("in", 0) or 0)
            sr.completion_tokens = int(phase.get("tokens", {}).get("out", 0) or 0)
            sr.reasoning_tokens = int(phase.get("tokens", {}).get("reasoning", 0) or 0)
            sr.answer_tokens = int(phase.get("tokens", {}).get("answer", 0) or 0)
            sr.explanation_tokens = int(phase.get("tokens", {}).get("explanation", 0) or 0)
            sr.estimated_cost_usd = float(phase.get("cost_usd", 0.0) or 0.0)
            sr.files_created = list(phase.get("files_created", []) or [])
            sr.files_modified = list(phase.get("files_modified", []) or [])
            sr.confidence = phase.get("confidence")
            sr.final_response = str(phase.get("final_response", "") or "")
        return sr


def _phase_from_envelope(envelope: dict[str, Any]) -> dict[str, Any] | None:
    """Pull the single phase's record out of the child's run envelope."""
    phases = envelope.get("phases") or []
    if not phases:
        return None
    return dict(phases[0])


def _classify(outcome: dict[str, Any]) -> dict[str, Any]:
    """Classify the spawned sibling's outcome: envelope-first, exit-code fallback.

    Mirrors ``run_workflow.py:classify_child_outcome`` (the P0-1 contract): never trust
    ``returncode == 0`` alone — a pre-contract child exits 0 with ``ok:false`` or
    ``awaiting:true``. Kept here (not imported) so the executor has zero dependencies
    on the CLI script and no import cycle.
    """
    stdout = outcome.get("stdout", "") or ""
    returncode = outcome.get("returncode")
    envelope = _parse_envelope(stdout)
    if returncode == 10:
        return {"state": "awaiting", "envelope": envelope}
    if returncode not in (None, 0):
        return {"state": "failed", "envelope": envelope}
    if envelope is not None:
        if envelope.get("awaiting") is True:
            return {"state": "awaiting", "envelope": envelope}
        if envelope.get("ok") is False:
            return {"state": "failed", "envelope": envelope}
    return {"state": "ok", "envelope": envelope}


def _parse_envelope(stdout: str) -> dict[str, Any] | None:
    """Best-effort parse of the child's final result envelope (its last JSON document)."""
    if not stdout:
        return None
    lines = stdout.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() != "{":
            continue
        try:
            obj = json.loads("\n".join(lines[i:]))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "ok" in obj:
            return obj
    return None
