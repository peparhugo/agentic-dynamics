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
``run_workflow.py --spec <boundary> --only-phase <boundary_phase> --no-commit`` inside the
container — a GENERATED, concrete test-only execution boundary (``TestBoundary``) that carries
the suite target(s), the candidate, the language, the authorizing scope and the timeout, and
NOTHING from the producing phase. The normal single-phase path's ``kind: test`` branch then
executes the suite in-process via ``test_runner.run_suite`` inside the verifier
(LocalVerifier). The parent classifies the child by its result envelope first
(``ok``/``awaiting``/``state``), the exit code second, exactly like the agent executor — a
pre-contract child that exits 0 with ``ok:false`` is failed, never success. The verdict fields
are pulled from the child's phase record, so the parent and the engine record the exact object
the independent runner produced.

The boundary exists because the producer's phase and the verifier's phase are DIFFERENT
things (Astra ae212a0 finding 3): the native ``test_gate`` is attached to an agent phase, and
a verifier child must never reload that agent phase by name (which would re-run the agent and
re-execute the parent workflow's gates inside a credential-less verifier cell). The parent
builds the boundary; this executor serialises it to a generated spec the child loads instead
of the original document.

The engine dispatches a ``kind: test`` phase through this executor ONLY when it is injected at
the composition root (under ``--orchestrator``); absent the injection the in-process run_suite
path is unchanged, and a containerized run with a step executor but NO verifier refuses loudly
(``VERIFIER_REFUSED``, never a skip — the P0-1 fail-closed contract).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from agentic_dynamics.runtime.executor import StepExecutor, StepRequest, StepResult, TestBoundary

# scripts/fleet/ is a dir, not a package — add it beside scripts/ so the sibling modules
# (spawn_wrapper, docker_executor) import.
_FLEET_DIR = str(Path(__file__).resolve().parent)
if _FLEET_DIR not in sys.path:
    sys.path.insert(0, _FLEET_DIR)

import spawn_wrapper  # noqa: E402
from docker_executor import _classify, _phase_from_envelope  # noqa: E402


class DockerVerifierExecutor(StepExecutor):
    """Run each ``kind: test`` phase as a READ-ONLY sibling verifier container.

    ``spec_path`` is retained for constructor parity with ``DockerAgentExecutor``; the
    verifier child no longer loads it (Astra ae212a0 finding 3) — it loads the GENERATED
    concrete test-only boundary (see :meth:`_write_boundary_spec`) instead, so the producing
    phase is never reloaded by name and its gates never execute inside the verifier.
    ``spec_name`` is the workflow's name; ``cell_image`` is the sibling's image
    (``fleet/job-<name>`` or the default cell base), carried on the typed request.

    ``run_clone`` (fb1_clone_mounted — the clone is the cell's world) is the run's private
    ephemeral clone path. When set, the verifier request carries it too (a test phase verifies
    against the run's clone — the suite runs in the read-only clone, mounted at ``/repo``), so
    the launch broker can bind the clone read-only and no shared worktree/``.git`` surface is
    mounted. It may be passed explicitly or inherited from ``FINOPS_RUN_CLONE``; absent
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

    @staticmethod
    def _concrete_boundary(request: StepRequest) -> TestBoundary:
        """Resolve the CONCRETE test-only boundary this request executes.

        The engine's native ``test_gate`` always supplies ``request.test_boundary`` (built
        from the gate declaration, never the producing agent phase). A hand-built test
        request without one is still supported by synthesising the boundary from its own
        ``phase_def`` — but the producing phase is never re-derived from the spec.
        """
        if request.test_boundary is not None:
            return request.test_boundary
        phase_def = request.phase_def or {}
        raw = phase_def.get("tests")
        suite = [raw] if isinstance(raw, str) else [str(t) for t in (raw or [])]
        return TestBoundary(
            phase_name=request.phase_name,
            suite=suite,
            candidate=request.workdir,
            language=request.language,
            scope=str(phase_def.get("scope") or ""),
            timeout=int(request.timeout or 0),
        )

    def _write_boundary_spec(self, boundary: TestBoundary, *, model: str) -> str:
        """Write the concrete test-only boundary as a generated spec; return its child path.

        The verifier child must NOT reload the original phase by name: that would re-run the
        producing agent (a model call in a credential-less verifier cell) and re-execute the
        parent workflow's gates. Instead the boundary — suite/target/candidate/scope/timeout,
        and nothing else — is serialised to a minimal, single-``kind:test``-phase spec the
        child loads in the original's place. JSON is valid YAML, so the generated document is
        consumed by ``run_workflow.py``'s ordinary ``load_spec_any`` path unchanged.
        """
        phase: dict[str, Any] = {"name": boundary.phase_name, "kind": "test"}
        if boundary.suite:
            phase["tests"] = list(boundary.suite)
        if boundary.scope:
            phase["scope"] = boundary.scope
        if boundary.timeout:
            phase["timeout"] = int(boundary.timeout)
        document = {
            "name": f"{self._spec_name}__verifier",
            "question": (
                f"concrete test-only execution boundary for phase {boundary.phase_name!r} "
                "— generated by DockerVerifierExecutor; never the producing phase"
            ),
            "version": "0.1",
            "artifact_kind": "workflow",
            "intent": "measure",
            "side_effects": {"repository": False, "external_services": False},
            "repeatable": True,
            "workflow": {
                "kind": "agent_task",
                "params": {
                    "language": boundary.language or "python",
                    "phases": [phase],
                },
            },
            "factors": [{"name": "model", "levels": [model]}],
            "design": "factorial",
            "rules": [],
            "metrics": [],
            "writeup": {"format": "lab_book", "sections": ["question"]},
            "stop": {"budget_usd": 0.0, "max_attempts": 1},
            "adapt": {"strategy": "manual", "selection": "highest_regret"},
        }
        # The generated spec lives beside the prepared-step transport (DockerAgentExecutor's
        # pattern): inside the run clone when one exists, else the shared worktree. The host
        # writes it; the verifier child reads it through the same read-only mount the candidate
        # uses. A local-only .git/info/exclude entry keeps it out of the cell's commits.
        boundary_file = f"{boundary.phase_name}.verify.json"
        if self._run_clone:
            host_dir = Path(self._run_clone) / ".fleet" / "verifier"
            child_path = f"{spawn_wrapper.REPO_TARGET}/.fleet/verifier/{boundary_file}"
            exclude = Path(self._run_clone) / ".git" / "info" / "exclude"
            if exclude.parent.is_dir():
                line = ".fleet/verifier/"
                text = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
                if line not in text.splitlines():
                    separator = "" if not text or text.endswith("\n") else "\n"
                    exclude.write_text(f"{text}{separator}{line}\n", encoding="utf-8")
        else:
            host_dir = Path(self._workdir) / ".fleet" / "verifier"
            child_path = str(host_dir / boundary_file)
        host_dir.mkdir(parents=True, exist_ok=True)
        (host_dir / boundary_file).write_text(
            json.dumps(document, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return child_path

    def build_request(self, request: StepRequest) -> dict[str, Any]:
        """Build the READ-ONLY verifier spawn request for ``request`` (pure, no docker).

        The request is what test (d) of the w1 parity suite inspects: it carries NO
        credentials and NO writable CLI-state namespace (see
        ``spawn_wrapper.build_verifier_request``), and its child command runs the SAME
        suite the in-process LocalVerifier path would run (same ``tests`` target, carried
        on the concrete boundary) inside the container — the local-parity target list. The
        child loads the GENERATED boundary spec, never the original phase by name. The run's
        clone path (fb1_clone_mounted), when one is configured, is carried as the candidate
        surface and the child runs INSIDE the read-only clone (its ``--workdir`` is the
        clone's container mount point ``/repo``).
        """
        boundary = self._concrete_boundary(request)
        # fb1_clone_mounted: with a run clone the verifier runs its suite inside the clone,
        # mounted read-only at /repo (REPO_TARGET) — the shared /tmp worktree namespace is not
        # mounted, so the candidate the suite runs against IS the clone. Without a clone the
        # verifier keeps operating against the shared-worktree candidate (pre-b2 shape).
        sibling_workdir = spawn_wrapper.REPO_TARGET if self._run_clone else self._workdir
        # ws4_smoke (fleet_launch_smoke, exposed by THE SMOKE): the sibling command must name
        # the interpreter the CONTAINER resolves on PATH ("python3" = the fleet image's
        # /usr/local/bin/python3 — the interpreter the deps were installed under), never the
        # executor process's own sys.executable. The executor may run on the HOST (this wave's
        # in-process smoke drove it there), where sys.executable is the host's /usr/bin/python3
        # — a DIFFERENT interpreter that the fleet/base image also carries but with NO project
        # deps, so the verifier child died at import before the suite ran. spawn_wrapper's own
        # default cell command ("python3 scripts/fleet/phase_runner.py") and the compose
        # workflow-runner command already use the PATH-resolved python3; the executors'
        # sys.executable was the one spot that baked a host path into a container argv.
        boundary_spec = self._write_boundary_spec(boundary, model=request.model or self._model)
        sibling_cmd = [
            "python3",
            "scripts/run_workflow.py",
            "--spec",
            boundary_spec,
            "--goal",
            self._goal,
            "--model",
            request.model or self._model,
            "--workdir",
            sibling_workdir,
            "--only-phase",
            boundary.phase_name,
            "--timeout",
            str(request.timeout or self._timeout),
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
        verifier_phase_def: dict[str, Any] = {"name": boundary.phase_name, "kind": "test"}
        if boundary.suite:
            verifier_phase_def["tests"] = list(boundary.suite)
        if boundary.scope:
            verifier_phase_def["scope"] = boundary.scope
        return spawn_wrapper.build_verifier_request(
            verifier_phase_def,
            goal=self._goal,
            workdir=sibling_workdir,
            model=request.model or self._model,
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
        # F3 parity (cs4, mirrored from DockerAgentExecutor): the phase's OWN declared scope
        # authorizes its spawn. A custom spec's test-phase name is not in the static
        # PHASE_SCOPE_AUTHORIZATION table; without this mapping step 2 refuses the verifier
        # (the g6_test_gate "authorized: None" refusal, run-5126d586f734) and the independent
        # gate silently never runs.
        auth_scopes = None
        declared = request.phase_def.get("scope") if isinstance(request.phase_def, dict) else None
        if declared in spawn_wrapper.SCOPE_VOCABULARY:
            auth_scopes = {request.phase_name: declared}
        try:
            if auth_scopes:
                outcome = spawn_wrapper.spawn_sibling(verifier_request, phase_scopes=auth_scopes)
            else:
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
        phase = _phase_from_envelope(envelope)

        # Evidence precedence (L58, 2026-09-24): when the child ran a phase, THAT phase's
        # error is the verdict's real content — the independent runner's suite tail
        # ("FAILED … / N failed, M passed"). The envelope's top-level error is often empty,
        # and the stderr fallback carries only the child's closing banner ("admission: gate
        # disarmed…", "control: child mode…") — which reads like a refusal and cost three
        # gate failures (L49 att2 u3, L51 att4 u4, L51 att7 u5) a host-side re-run to
        # diagnose. Prefer the phase error whenever a phase record exists.
        phase_error = str((phase or {}).get("error") or "")
        sr = StepResult(
            ok=state == "ok",
            state=state,
            error=(phase_error or str(envelope.get("error") or outcome.get("stderr", "")))[:800],
            exit_code=int(outcome.get("returncode", -1) or -1),
        )
        if phase is not None:
            # The verdict object is the child phase's own record — test_executed_success /
            # tests_passed / tests_total produced by the independent runner inside the
            # verifier container. Same field names, same source semantics as in-process.
            sr.test_executed_success = phase.get("test_executed_success")
            sr.tests_passed = int(phase.get("tests_passed", 0) or 0)
            sr.tests_total = int(phase.get("tests_total", 0) or 0)
        return sr
