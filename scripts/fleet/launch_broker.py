#!/usr/bin/env python3
"""The launch broker — the host-side (non-container) holder of the Docker socket (b3_launch_broker, fb2_broker_hostside).

The socket leaves the container. Before this module the orchestrator tier mounted
``/var/run/docker.sock`` and one large trusted module (``spawn_wrapper.py``) both validated
AND invoked arbitrary docker commands — and ``:ro`` on the filesystem mount does not
constrain Docker Engine authority. This broker is the ONLY component that calls the Docker
API (its two documented exceptions — the game board's read-only ``docker ps`` in
``scripts/system_snapshot.py``, fb3 f4, and the archived one-time sonar-scanner docker run in
``scripts/archive/backfill_sonar.py``, ws3_stragglers — frozen, never re-run; both are reads,
never a launch, never a write into the fleet), and
it accepts ONLY a TYPED launch request — arbitrary docker CLI capability is never exposed to
any tier:

    LaunchRequest {image_digest, network, mount_profile, state_namespace,
                   command, timeout_seconds}

It validates the typed request against the FIXED mount profiles the ladder defines (the
read-only repo profile, the implementation rw profile, the verifier read-only profile),
performs the docker call itself (``docker run`` for a cell; ``docker compose`` for the
scale/drain/restart/submit fleet actions), and returns the outcome.

**fb2_broker_hostside — the broker runs where the socket is.** This module is now deployed as
a genuinely host-side service: the systemd user unit
``infrastructure/agentic-dynamics-launch-broker.service`` runs this module's ``serve`` mode
(:func:`serve`) as a long-running daemon that listens on a unix-socket IPC seam. The
orchestrator's spawn path (``spawn_wrapper.py``) NO LONGER imports this module and calls
docker in-process — it talks to this broker over that seam through
``broker_client.py`` (a dependency-free socket client). NO container mounts the docker socket
and NO in-container code calls docker: a socketless orchestrator reaches ONLY the broker's
typed seam, and the broker — which owns the socket — is where every docker call executes. The
broker unit is the docker socket's only home.

**The shared validation.** The wrapper's validation logic is shared with the broker: both
validate against the same profiles — the wrapper validates what it intends to submit, the
broker validates what it will execute. Both run the SAME pure functions, which now live in
``broker_contract.py`` (this module imports + re-exports them); the wrapper imports that
contract directly, never this module. :func:`launch` runs the same checks again (plus the
scope-model check ``spawn_wrapper.validate_spawn`` — imported lazily to keep this module
import-cycle-free) the instant before the docker call. A request that fails either side never
reaches the socket.

**The profiles own the mounts.** A launch request does not carry an arbitrary mount list as
its isolation contract: ``broker_contract.MOUNT_PROFILES`` is the closed vocabulary, and the
broker expands the request's ``mount_profile`` into the concrete mount list itself
(:func:`broker_contract.mounts_for_profile`). The wrapper's request builders derive the SAME
expansion from the SAME profile (that module is the single source), so the two cannot
disagree about what a cell may mount. The broker executes from its OWN expansion, never from a
caller-supplied mount list — a forged or partial mount set cannot reach the socket.

**The broker validates the view it executes** (ws2_broker_pathview, fleet_launch_smoke). The
D-16 repo-alias split means the container tier and the host derive different repo paths: a
container-tier caller (``FINOPS_REPO_DIR`` absent from its env) roots its config at the
image's ``/app``, so the mounts it builds target the /app-in-container paths, while the broker
derives its contract from the operator's host env (the repo at its host path). Before ws2 the
broker re-validated those container-built mounts against its own host config and REFUSED every
containerized spawn for a path split the caller cannot see. A launch request now carries the
VIEW of the config it was built against (``host`` or ``container``, absent = host):
:func:`launch` validates a container-view request against the container-view
:class:`PathConfig` (:func:`broker_contract.container_view_config` — the /app paths) and a
host-view request against the host config — the same shared checks, the same refusals for a
request that is genuinely wrong, but never a refusal for the split itself. The broker's OWN
launch argv is always expanded from the host config: a docker bind source is a host path, and
the container-view mounts are validated, never executed.

This module is a script (``scripts/fleet/``), not a package plane. Its package imports are the
tier-0 path object (``agentic_dynamics.core.paths.PathConfig``) and the tier-1 scope config
table (``agentic_dynamics.experiment.experiment_spec.SCOPE_CONFIGS``) — the same tier-0/1
surface ``spawn_wrapper.py`` already imports. It never imports ``control`` / ``runtime`` /
``adapters``; the docker call is a plain ``subprocess`` over an argv this module builds (the
broker runs on the HOST and subprocesses the host's docker binary — ``FINOPS_DOCKER_BIN``;
no fleet image carries a docker client, because no container holds a socket or calls docker,
fb3_stragglers).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

# scripts/fleet/ -> the repo root is two parents up; put src/ on sys.path so the tier-0/1
# planes resolve (the same "scripts/ is sys.path[0]" convention as the other scripts).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _REPO_ROOT / "src"
# The repo root itself is required: the broker validates a submit's spec through
# ``load_spec_any`` -> the top-level ``workflows/`` namespace package, which resolves only
# with the repo root on sys.path. Missing here, the broker raised ModuleNotFoundError for
# every valid submit whose spec path resolved (observed 2026-09-12, the wave-C batch).
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# scripts/fleet/ is a dir, not a package — add it beside src/ so the SHARED contract module
# (broker_contract) and the seam-client module (broker_client) import as top-level modules,
# and the lazy ``spawn_wrapper`` import inside :func:`launch` resolves. Same convention as
# spawn_wrapper.py's own bootstrap.
_FLEET_DIR = Path(__file__).resolve().parent
if str(_FLEET_DIR) not in sys.path:
    sys.path.insert(0, str(_FLEET_DIR))

import broker_client  # noqa: E402
from broker_client import recv_frame, send_frame  # noqa: E402

# ── Re-exports (fb2_broker_hostside) ─────────────────────────────────────────
#
# The pure typed contract (profiles, the shared expansion, the shared validation, the
# namespace sanitizer) physically lives in ``broker_contract.py`` so ``spawn_wrapper`` can
# import it WITHOUT importing this module (the broker's docker-executing code). This module
# imports the contract names below (for its own execution functions) AND re-exports them, so
# the historical import surface (``from launch_broker import AUTH_CRED_FILE, ...`` — tests and
# older callers that reach the shared vocabulary through the broker module) keeps resolving.
# Importing these names never invokes docker — only the execution functions below do.
from broker_contract import (  # noqa: E402
    AUTH_CRED_FILE,
    CONTAINER_REPO_ROOT,
    IMAGE_NAMESPACE,
    JOB_IMAGE_PATTERN,
    LAUNCH_NETWORK,
    LAUNCH_REQUEST_FIELDS,
    MAX_LAUNCH_TIMEOUT_SECONDS,
    MIN_LAUNCH_TIMEOUT_SECONDS,
    MOUNT_PROFILES,
    REPO_TARGET,
    RESULTS_TARGET,
    STATE_TARGET,
    VERIFIER_MARKER,
    VIEW_CONTAINER,
    VIEW_HOST,
    VIEWS,
    WORKTREE_TARGET,
    LaunchRequestError,
    container_view_config,
    mounts_for_profile,
    request_view,
    sanitize_namespace,
    validate_launch_request,
)

from agentic_dynamics.core.admission_context import admission_required  # noqa: E402
from agentic_dynamics.core.paths import PathConfig  # noqa: E402

__all__ = [
    "AUTH_CRED_FILE",
    "CONTAINER_REPO_ROOT",
    "IMAGE_NAMESPACE",
    "JOB_IMAGE_PATTERN",
    "LAUNCH_NETWORK",
    "MOUNT_PROFILES",
    "REPO_TARGET",
    "RESULTS_TARGET",
    "STATE_TARGET",
    "VERIFIER_MARKER",
    "VIEWS",
    "VIEW_CONTAINER",
    "VIEW_HOST",
    "WORKTREE_TARGET",
    "LaunchRequestError",
    "LAUNCH_REQUEST_FIELDS",
    "MAX_LAUNCH_TIMEOUT_SECONDS",
    "MIN_LAUNCH_TIMEOUT_SECONDS",
    "container_view_config",
    "mounts_for_profile",
    "request_view",
    "sanitize_namespace",
    "validate_launch_request",
    # docker-executing surface (this module):
    "build_launch_argv",
    "launch",
    "build_submit_argv",
    "submit_run",
    "build_fleet_action_argv",
    "run_fleet_command",
    "serve",
    "main",
]


def _bounded_timeout(timeout_seconds: Any) -> float | None:
    """The subprocess timeout for a request: ``None`` when unset (child-managed kill)."""
    if not timeout_seconds:
        return None
    return float(timeout_seconds)


def validation_config_for_request(
    request: dict[str, Any],
    host_config: PathConfig,
) -> PathConfig:
    """The :class:`PathConfig` a request's mounts must be validated against — its declared VIEW.

    ws2_broker_pathview (fleet_launch_smoke): a launch request carries the VIEW of the path
    config its mounts were built against. A HOST-view request validates against the broker's
    host config; a CONTAINER-view request validates against the container-view config (the
    /app-in-container repo paths its mounts target — ``container_view_config``) derived from
    that same host config. The broker therefore never refuses a request for the D-16 repo-alias
    split (the container tier's /app alias targets vs the host path) that the caller cannot
    see. ``host_config`` is the broker's own launch config (the docker bind sources); it is
    ALWAYS the config the launch argv is expanded from, whatever view a request declares.
    """
    if request_view(request) == VIEW_CONTAINER:
        return container_view_config(host_config)
    return host_config


# ── The docker call — the ONLY call site in the runtime code ────────────────


def build_launch_argv(
    request: dict[str, Any],
    *,
    docker: str = "docker",
    mounts: list[dict[str, str]] | None = None,
) -> list[str]:
    """Build the ``docker run`` argv for a validated typed request (called only AFTER validation).

    The argv is assembled from the broker's OWN profile expansion (:func:`mounts_for_profile`)
    + the request's validated env/network/image/command — never from a caller-supplied argv.
    The container runs as a sibling cell; the socket is deliberately NOT mounted on the sibling
    (it is a phase CELL, not the broker). The argv's docker run flags are FIXED here; the
    request's ``command`` is appended AFTER the image, where docker treats it as the container
    command (never as a docker flag), so a hostile command cannot reach the host engine.
    """
    mounts = mounts if mounts is not None else []
    argv = [docker, "run", "--rm", "-i"]
    for m in mounts:
        source = str((m or {}).get("source", ""))
        target = str((m or {}).get("target", ""))
        mode = str((m or {}).get("mode", "ro"))
        argv += ["-v", f"{source}:{target}:{mode}"]
    argv += ["--network", str(request.get("network", LAUNCH_NETWORK))]
    for k, v in (request.get("env", {}) or {}).items():
        argv += ["-e", f"{k}={v}"]
    argv += [str(request.get("image_digest", ""))]
    argv += list(request.get("command", []))
    return argv


def launch(
    request: Any,
    *,
    docker: str = "docker",
    dry_run: bool = False,
    path_config: PathConfig | None = None,
) -> dict[str, Any]:
    """The broker's ONE launch path: validate the typed request, then ``docker run``.

    Two validations run before the socket is reached, and BOTH are the shared checks:

    1. :func:`broker_contract.validate_launch_request` — the typed contract (image/network/
       profile/namespace/command/timeout) against the fixed profiles; and
    2. ``spawn_wrapper.validate_spawn`` — the scope model (phase authorization, mount contract,
       network, write flags, the lease block), imported lazily so this module never forms an
       import cycle with the wrapper. The broker validates what it will execute with the SAME
       refusals the wrapper applied when it validated what it intended to submit.

    **The broker validates the view it executes** (ws2_broker_pathview, fleet_launch_smoke):
    the request carries the VIEW (host | container) of the path config its mounts were built
    against. Both validations run against that view's config (:func:`validation_config_for_request`)
    — a container-view request (its D-16 repo-alias mounts target the /app-in-container paths a
    container-tier caller derives) validates against the container-view :class:`PathConfig`,
    a host-view request against the host config — never refusing a request for a path split the
    caller cannot see. The broker's OWN launch argv is ALWAYS the host view
    (:func:`mounts_for_profile` on ``host_config``): a docker bind source is a host path, and
    the request's container-view mounts are validated, never executed.

    A refusal raises :class:`LaunchRequestError` BEFORE any docker argv is built. On success
    returns ``{"ok", "argv", "returncode", "stdout", "stderr"}`` (``dry_run`` builds the argv
    only). ``timeout_seconds`` on the request bounds the docker subprocess when positive.
    """
    # The shared scope-model checks below live in spawn_wrapper — imported lazily so this
    # module never imports spawn_wrapper at module scope (spawn_wrapper imports the pure
    # contract module broker_contract, never this module — the fb2 seam boundary).
    import spawn_wrapper  # noqa: PLC0415

    # The broker's own launch config (docker bind sources) — the HOST view, whatever view a
    # request declares. The argv is expanded from it below.
    host_config = path_config or spawn_wrapper.default_path_config()
    # ws2_broker_pathview: the mount contract + the scope model are validated against the view
    # the request carries (container-view requests validate against the /app-in-container paths
    # their mounts were built with). An unknown view was already refused by the typed check.
    cfg = validation_config_for_request(request, host_config)
    errors = validate_launch_request(request, path_config=cfg)
    if errors:
        raise LaunchRequestError(errors)

    scope_errors = spawn_wrapper.validate_spawn(
        request, path_config=cfg,
        # F3 (fleet_launch_container_smoke cs4): phase AUTHORIZATION was adjudicated
        # wrapper-side (the wrapper's step 2 ran with the spec's declared scopes before the
        # request crossed the seam — a compromised phase can never reach the broker). The
        # broker re-validates the LAUNCH MECHANICS (contract, mounts, lease, view) against
        # the request's own resolved scope — it cannot re-adjudicate phase authorization
        # without the spec, and must not refuse a legitimately-declared scope because the
        # static table cannot know a custom spec's phases.
        phase_scopes={str(request.get("phase", "")): str(request.get("scope", ""))},
    )
    if scope_errors:
        raise LaunchRequestError(scope_errors)

    # The broker mounts ITS OWN profile expansion — never a caller-supplied mount list. The
    # expansion is the HOST view (host_config): the request's container-view mounts were
    # validated above; what docker actually bind-mounts are the host paths.
    profile = str(request.get("mount_profile", ""))
    mounts = mounts_for_profile(
        profile,
        path_config=host_config,
        state_namespace=str(request.get("state_namespace", "")),
        run_clone=request.get("run_clone"),
    )
    argv = build_launch_argv(request, docker=docker, mounts=mounts)
    if dry_run:
        return {"ok": True, "argv": argv, "returncode": None, "stdout": "", "stderr": ""}

    try:
        proc = subprocess.run(  # noqa: S603 — the only docker invocation in the runtime code
            argv, capture_output=True, text=True, timeout=_bounded_timeout(
                request.get("timeout_seconds")
            )
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "argv": argv,
            "returncode": None,
            "stdout": "",
            "stderr": f"docker run exceeded timeout_seconds={request.get('timeout_seconds')}",
        }
    return {
        "ok": proc.returncode == 0,
        "argv": argv,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


# ── The compose lifecycle — the same typed discipline (fleet:commands, D-14) ─


def _compose_file_default() -> str:
    return str(_REPO_ROOT / "infrastructure" / "docker-compose.ladder.yml")


def build_submit_argv(
    command: dict[str, Any],
    *,
    compose: str = "docker-compose",
    compose_file: str | None = None,
) -> list[str]:
    """Build the ``docker compose run`` argv for a validated submit.

    The reference containerized execution path: ``docker compose -f docker-compose.ladder.yml
    run --rm workflow-runner python3 scripts/run_workflow.py --spec ... --goal ... --model ...
    --workdir ... --orchestrator``. Lives HERE (the broker owns every docker/compose call); the
    wrapper validates the submit and delegates the call to :func:`submit_run`.

    The extended identity fields (AIO remediation 2026-09-14) ride the SAME argv so they
    survive the hop to the orchestrator container: ``resume``/``parent_run_id`` (continuation
    identity) become ``--resume``/``--parent-run-id``; ``admission`` becomes the armed-env
    ``FINOPS_ADMISSION_REQUIRED=1`` plus the campaign cap flags the run's composition root
    applies to the lease registry. ``spec_sha256`` is carried in the command for the broker's
    byte-level verification and deliberately NOT forwarded — the orchestrator pins its own
    ``workflow_revision_id`` from the bytes it loads.
    """
    compose_file = compose_file or _compose_file_default()
    job_id = str(command.get("job_id", "") or "")
    argv = [compose, "-f", compose_file, "run", "--rm"]
    if job_id:
        argv += ["-e", f"FINOPS_CELL_ID={job_id}"]
    admission = command.get("admission") or {}
    if isinstance(admission, dict) and admission.get("required"):
        # The armed admission gate crosses the compose boundary as the env the composition
        # root's fail-closed spend gate reads — a submit declaring admission must not silently
        # arrive disarmed (the 2026-09-14 first-launch defect: "gate disarmed" on a manual
        # compose launch while the recorded plan said armed).
        argv += ["-e", "FINOPS_ADMISSION_REQUIRED=1"]
    argv += [
        "workflow-runner",
        "python3", "scripts/run_workflow.py",
        "--spec", str(command.get("spec", "")),
        "--goal", str(command.get("goal", "")),
        "--model", str(command.get("model", "")),
        "--workdir", str(command.get("workdir", "")),
        "--orchestrator",
    ]
    if command.get("resume"):
        argv += ["--resume"]
    if str(command.get("parent_run_id", "") or ""):
        argv += ["--parent-run-id", str(command.get("parent_run_id", ""))]
    if isinstance(admission, dict):
        if admission.get("campaign_budget_usd") is not None:
            argv += ["--campaign-budget-usd", str(admission["campaign_budget_usd"])]
        if admission.get("campaign_concurrency") is not None:
            argv += ["--campaign-concurrency", str(admission["campaign_concurrency"])]
    image = command.get("image")
    if image:
        argv += ["--cell-image", str(image)]
    return argv


def submit_run(
    command: dict[str, Any],
    *,
    repo_root: Path | str | None = None,
    phase_scopes: dict[str, str] | None = None,
    path_config: PathConfig | None = None,
    compose: str = "docker-compose",
    compose_file: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """The broker's submit path: re-validate a submit, then ``docker compose run`` it.

    The wrapper validated the submit before delegating; the broker validates it AGAIN with the
    same ``spawn_wrapper.validate_submit_request`` (the shared refusal), then performs the
    compose call — the broker validates what it will execute. Returns
    ``{"ok", "argv", "returncode", "stdout", "stderr"}``.
    """
    import spawn_wrapper  # noqa: PLC0415

    # The disarmed-submit refusal (AIO remediation 2026-09-14) — FIRST, so it is the named
    # refusal a submitter sees: a durable submit that arrives with NO admission settings while
    # the broker's own environment has the gate armed would launch a run whose phases run
    # unleased — "admission: gate disarmed" in a log beside a record that says the run was
    # armed (the first-launch defect). Refuse at the gate, before any container exists. The
    # broker reads its OWN environment (the operator's policy), never the command's claim.
    if admission_required() and not bool((command.get("admission") or {}).get("required")):
        raise LaunchRequestError([
            "submit: admission is armed on this host (FINOPS_ADMISSION_REQUIRED=1) but the "
            "command declares no admission settings — the durable submit path never silently "
            "disarms the spend gate"
        ])

    errors = spawn_wrapper.validate_submit_request(
        command, repo_root=repo_root, phase_scopes=phase_scopes, path_config=path_config,
    )
    if errors:
        raise LaunchRequestError(errors)

    # The deployment probe (remediation closed-loop, decision f987cde9): the wrapper cannot
    # run git (no-subprocess contract), so the broker — the last gate before the compose call —
    # probes the workdir base against the repo's main tip AND verifies the declared spec
    # digest (the extended immutable-input check). A stale/diverged workdir or a digest
    # mismatch refuses here, before any container exists; a declared resume skips the
    # main-freshness check (a pinned continuation is never destroyed by unrelated main moves).
    probe_errors = deployment_probe(
        str(command.get("workdir", "") or ""), repo_root=repo_root or _REPO_ROOT,
        spec_rel=str(command.get("spec", "") or ""),
        spec_sha256=command.get("spec_sha256"),
        resume=bool(command.get("resume", False)),
    )
    if probe_errors:
        raise LaunchRequestError(probe_errors)

    argv = build_submit_argv(command, compose=compose, compose_file=compose_file)
    if dry_run:
        return {"ok": True, "argv": argv, "returncode": None, "stdout": "", "stderr": ""}
    # The run's OWN output is captured and returned (then echoed so the journal still shows
    # it). It carries the run's identity — the ``ledger: <path>`` line on stderr — which the
    # wrapper uses to associate the exact result with the job (identity recovery). The
    # sibling ``launch`` path has captured its output the same way since b3.
    proc = subprocess.run(  # noqa: S603 — the broker owns the compose call
        argv, check=False, capture_output=True, text=True,
    )
    if proc.stdout:
        sys.stdout.write(proc.stdout)
        sys.stdout.flush()
    if proc.stderr:
        sys.stderr.write(proc.stderr)
        sys.stderr.flush()
    return {
        "ok": proc.returncode == 0,
        "argv": argv,
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
    }


# ── The deployment probe (remediation closed-loop, decision f987cde9) ─────────


def deployment_probe(
    workdir: str,
    *,
    repo_root: Path | str,
    spec_rel: str = "",
    spec_sha256: str | None = None,
    resume: bool = False,
) -> list[str]:
    """Refuse a submit whose declared inputs cannot be the inputs the run will execute.

    The run clone pins ``base_sha`` to the WORKDIR HEAD, so a stale worktree silently mints
    runs from a dead tree — the 2026-09-13 fleet failure class (four launches cloned at
    ``b57b84688`` while main was ``0a29f28b4``, each dying at spec load). This lives HERE, not
    in ``spawn_wrapper``: the probe must run git, and the wrapper's contract bans subprocess
    entirely (the no-docker/no-subprocess guard) — the broker is the one module allowed to run
    subprocess, so the probe fires at the last gate before the compose call.

    The probe judges only what it can prove: when both paths are git worktrees and the repo's
    ``main`` resolves, the workdir HEAD must be AT or AHEAD of main (``merge-base
    --is-ancestor`` exits 0) — at/ahead is legal (a resume worktree carries phase commits),
    behind (stale) or diverged is refused with the fix named. When either side cannot be
    judged (not a git tree, no main ref, git unavailable), the probe says nothing — the clone
    path itself will name those, and a fabricated refusal is worse than none.

    The extended checks (AIO remediation 2026-09-14):

    * ``spec_sha256`` (when declared) is verified against the SPEC FILE'S bytes at the
      broker's repo — the declared immutable input, not merely "a worktree contains today's
      main". A mismatch refuses: the caller's identity claim does not describe what the
      orchestrator will load.
    * ``resume=True`` SKIPS the main-freshness refusal: a legitimate pinned resume runs on
      the run's own phase commits, and an unrelated main advance must never destroy it
      (the stale check would have refused exactly that — the resume's base predates main).
      Its lineage is the parent-run linkage, which the run's own composition root verifies
      against the control database (``ParentRunRefused``), not this probe.
    """
    if spec_rel and spec_sha256:
        try:
            spec_bytes = (Path(repo_root) / spec_rel).read_bytes()
            actual = hashlib.sha256(spec_bytes).hexdigest()
        except OSError:
            actual = ""
        if actual and actual.lower() != str(spec_sha256).lower():
            return [
                f"submit: spec {spec_rel} digest mismatch — declared "
                f"{str(spec_sha256)[:12]}…, the repo's bytes hash to {actual[:12]}…; "
                "the declared immutable input is not the spec the run would execute"
            ]
    wd = Path(workdir) if workdir else None
    if not wd or not wd.is_dir():
        return []
    if resume:
        # A continuation resumes the run's own worktree state — main-freshness is not its
        # contract (see above).
        return []
    if not (wd / ".git").exists() or not (Path(repo_root) / ".git").exists():
        return []
    main_sha = _git_probe(str(repo_root), ["rev-parse", "--verify", "main^{commit}"])
    if not main_sha:
        return []
    head_sha = _git_probe(str(wd), ["rev-parse", "--verify", "HEAD^{commit}"])
    if not head_sha:
        return [
            f"submit: workdir {wd} has no HEAD — create the worktree at the repo's main tip first"
        ]
    rc = _git_probe_rc(str(wd), ["merge-base", "--is-ancestor", main_sha, head_sha])
    if rc == 0:
        return []  # at or ahead of main — the legal base
    if rc is None or rc >= 128:  # git error (unjudgeable) — never fabricate
        return []
    return [
        f"submit: workdir base {head_sha[:12]} is behind or diverged from the repo main tip "
        f"{main_sha[:12]} — update the worktree first (git -C {wd} reset --hard origin/main), "
        "then re-submit; the run clone pins base_sha to the workdir HEAD"
    ]


def _git_probe(workdir: str, args: list[str]) -> str:
    """One ``git`` call for the deployment probe; ``""`` on any failure (never raises)."""
    try:
        proc = subprocess.run(  # noqa: S603 — the broker's probe is the git caller
            ["git", "-C", str(workdir), *args],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _git_probe_rc(workdir: str, args: list[str]) -> int | None:
    """The return code of one ``git`` call; ``None`` when git itself cannot run."""
    try:
        proc = subprocess.run(  # noqa: S603
            ["git", "-C", str(workdir), *args],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.returncode


def build_fleet_action_argv(
    command: dict[str, Any],
    *,
    compose: str = "docker-compose",
    compose_file: str | None = None,
) -> list[str]:
    """Build the ``docker compose`` argv for a validated scale/drain/restart command."""
    compose_file = compose_file or _compose_file_default()
    action = str(command.get("action", ""))
    service = str(command.get("service", ""))
    if action == "scale":
        return [compose, "-f", compose_file, "up", "-d", "--scale",
                f"{service}={command['count']}", service]
    if action == "drain":
        return [compose, "-f", compose_file, "stop", service]
    return [compose, "-f", compose_file, "restart", service]


def run_fleet_command(
    command: dict[str, Any],
    *,
    compose: str = "docker-compose",
    compose_file: str | None = None,
    dry_run: bool = False,
    repo_root: Path | str | None = None,
    phase_scopes: dict[str, str] | None = None,
    path_config: PathConfig | None = None,
) -> dict[str, Any]:
    """The broker's fleet-command path: re-validate a fleet:commands command, then execute it.

    ``submit`` is delegated to :func:`submit_run` (a different shape); scale/drain/restart are
    re-validated against the compose allowlist (:func:`spawn_wrapper.validate_fleet_command` —
    the shared refusal) and then executed via ``docker compose``. Returns
    ``{"ok", "argv", "returncode", "stdout", "stderr"}``.
    """
    if str(command.get("action", "")) == "submit":
        return submit_run(
            command,
            repo_root=repo_root,
            phase_scopes=phase_scopes,
            path_config=path_config,
            compose=compose,
            compose_file=compose_file,
            dry_run=dry_run,
        )

    import spawn_wrapper  # noqa: PLC0415

    errors = spawn_wrapper.validate_fleet_command(
        command, repo_root=repo_root, phase_scopes=phase_scopes, path_config=path_config,
    )
    if errors:
        raise LaunchRequestError(errors)

    argv = build_fleet_action_argv(command, compose=compose, compose_file=compose_file)
    if dry_run:
        return {"ok": True, "argv": argv, "returncode": None, "stdout": "", "stderr": ""}
    proc = subprocess.run(argv, check=False)  # noqa: S603 — the broker owns the compose call
    return {
        "ok": proc.returncode == 0,
        "argv": argv,
        "returncode": proc.returncode,
        "stdout": "",
        "stderr": "",
    }


# ── The IPC seam — the host-side ``serve`` mode (fb2_broker_hostside) ────────
#
# The systemd user unit (infrastructure/agentic-dynamics-launch-broker.service) runs this
# module's ``serve`` mode on the host. The seam is a unix socket; each connection carries ONE
# framed request ({"verb", "request", "dry_run"}) and receives ONE framed outcome — every
# reply is a complete JSON object, so a refusal, a docker-unavailable state, or a server error
# is a NAMED state in the object, never a dropped connection and never a silent pass. The
# socket's protocol (the framing) is shared with the client (``broker_client.py``), so the two
# sides of the seam cannot drift about framing.

#: The outcome ``state`` values the seam returns (callers switch on ``state``, never on
#: ``ok`` alone — an ``ok: false`` docker run and a broker-side refusal are different things).
STATE_DRY_RUN = "DRY_RUN"
STATE_OK = "OK"
STATE_RUN_FAILED = "RUN_FAILED"
STATE_REFUSED = "REFUSED"
STATE_DOCKER_UNAVAILABLE = "DOCKER_UNAVAILABLE"
STATE_SERVER_ERROR = "SERVER_ERROR"
STATE_PONG = "PONG"

#: The typed seam's closed verb set — a request carrying any other verb is refused.
SERVE_VERBS: frozenset[str] = frozenset({"launch", "submit", "fleet-command", "ping"})


def serve_request(
    request: dict[str, Any],
    *,
    docker: str = "docker",
    compose: str = "docker-compose",
    compose_file: str | None = None,
    path_config: PathConfig | None = None,
) -> dict[str, Any]:
    """Dispatch ONE framed seam request to the typed broker paths. Never raises to the caller.

    Every request — valid or not — maps to a complete outcome dict with a NAMED ``state``:
    a refused launch/fleet request is ``REFUSED`` with the shared validation's ``errors``; the
    docker/compose binary being absent (or not executable) is ``DOCKER_UNAVAILABLE`` with a
    loud ``stderr``; an unexpected broker fault is ``SERVER_ERROR``. ``ping`` is the liveness
    probe. This is the function the ``serve`` loop calls per connection and the function the
    broker-hosted smoke drives directly.
    """
    verb = str((request or {}).get("verb", ""))
    dry_run = bool((request or {}).get("dry_run"))
    payload = (request or {}).get("request") or {}
    if verb == "ping":
        return {"ok": True, "state": STATE_PONG}
    if verb not in SERVE_VERBS:
        return {
            "ok": False,
            "state": STATE_REFUSED,
            "errors": [
                f"unknown broker verb {verb!r} — the typed seam accepts "
                f"{sorted(SERVE_VERBS)}"
            ],
            "argv": None,
            "returncode": None,
            "stdout": "",
            "stderr": "",
        }
    try:
        if verb == "launch":
            outcome = launch(payload, docker=docker, dry_run=dry_run, path_config=path_config)
        elif verb == "submit":
            outcome = submit_run(
                payload,
                path_config=path_config,
                compose=compose,
                compose_file=compose_file,
                dry_run=dry_run,
            )
        else:
            outcome = run_fleet_command(
                payload,
                path_config=path_config,
                compose=compose,
                compose_file=compose_file,
                dry_run=dry_run,
            )
    except LaunchRequestError as exc:
        return {
            "ok": False,
            "state": STATE_REFUSED,
            "errors": exc.errors,
            "argv": None,
            "returncode": None,
            "stdout": "",
            "stderr": "",
        }
    except (FileNotFoundError, PermissionError, OSError) as exc:
        # The docker/compose binary is absent or not runnable — the broker cannot reach the
        # engine. This is a NAMED loud failure, never a silent pass.
        return {
            "ok": False,
            "state": STATE_DOCKER_UNAVAILABLE,
            "argv": None,
            "returncode": None,
            "stdout": "",
            "stderr": (
                f"docker is unavailable to the host-side broker ({exc}) — is the engine "
                f"installed and is the broker unit's PATH correct? (state "
                f"{STATE_DOCKER_UNAVAILABLE})"
            ),
        }
    except Exception as exc:  # noqa: BLE001 — a broker fault is a named state, never a crash
        return {
            "ok": False,
            "state": STATE_SERVER_ERROR,
            "argv": None,
            "returncode": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc} (state {STATE_SERVER_ERROR})",
        }
    if dry_run:
        return {**outcome, "state": STATE_DRY_RUN}
    return {**outcome, "state": STATE_OK if outcome.get("ok") else STATE_RUN_FAILED}


def _serve_connection(conn: Any, *, docker: str, compose: str, compose_file: str | None,
                      path_config: PathConfig | None) -> None:
    """Read one framed request on ``conn`` and reply with one framed outcome (then close)."""
    with conn:
        try:
            request = recv_frame(conn)
        except Exception as exc:  # noqa: BLE001 — a malformed frame is a loud reply, never a hang
            reply = {
                "ok": False,
                "state": STATE_SERVER_ERROR,
                "errors": [f"the broker could not read the request frame: {exc}"],
                "argv": None,
                "returncode": None,
                "stdout": "",
                "stderr": "",
            }
            with contextlib.suppress(Exception):  # noqa: BLE001 — nothing more for a broken peer
                send_frame(conn, reply)
            return
        outcome = serve_request(
            request, docker=docker, compose=compose, compose_file=compose_file,
            path_config=path_config,
        )
        try:
            send_frame(conn, outcome)
        except Exception as exc:  # noqa: BLE001 — the peer went away mid-reply; log, never crash
            print(f"[launch-broker] reply to {request.get('verb')!r} failed: {exc}", flush=True)


def serve(
    socket_path: str,
    *,
    docker: str = "docker",
    compose: str = "docker-compose",
    compose_file: str | None = None,
    path_config: PathConfig | None = None,
    stop_event: threading.Event | None = None,
    ready_event: threading.Event | None = None,
) -> None:
    """The host-side broker service: listen on the seam socket and serve typed requests.

    Binds ``socket_path`` (creating + securing its parent dir), accepts connections, and
    serves each on its own daemon thread (:func:`serve_request`). Blocks until ``stop_event``
    is set (or the listen socket is closed), then unlinks the socket. ``ready_event`` (tests)
    is set once the socket is bound + listening. ``docker`` / ``compose`` / ``compose_file`` /
    ``path_config`` are the broker's runtime configuration — the unit passes the docker/compose
    binaries the host provides; tests inject a stub docker binary to prove a round-trip.

    One request per connection keeps the protocol stateless: a client connects, sends one
    framed request, reads one framed outcome, and closes. Long-running launches (a docker run
    of hours) occupy their own connection thread, so one slow cell never blocks another spawn.
    """
    socket_path = str(socket_path)
    parent = Path(socket_path).parent
    parent.mkdir(parents=True, exist_ok=True)
    if os.path.exists(socket_path):
        try:
            os.unlink(socket_path)
        except OSError as exc:  # pragma: no cover — a stale non-socket file at the path
            raise SystemExit(f"launch-broker: cannot replace stale {socket_path}: {exc}") from exc

    import socket as _socket

    listen = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
    try:
        listen.bind(socket_path)
    except OSError as exc:
        listen.close()
        raise SystemExit(f"launch-broker: cannot bind seam socket {socket_path}: {exc}") from exc
    with contextlib.suppress(OSError):
        # Best-effort; the socket still works on a permissive umask.
        os.chmod(socket_path, 0o660)
    listen.listen(16)
    listen.settimeout(0.5)
    if ready_event is not None:
        ready_event.set()
    print(f"[launch-broker] serving {socket_path} (docker={docker} compose={compose})",
          flush=True)
    try:
        while stop_event is None or not stop_event.is_set():
            try:
                conn, _addr = listen.accept()
            except (OSError, TimeoutError):
                # The 0.5s accept timeout lets the loop poll stop_event between connections.
                continue
            thread = threading.Thread(
                target=_serve_connection,
                args=(conn,),
                kwargs={
                    "docker": docker,
                    "compose": compose,
                    "compose_file": compose_file,
                    "path_config": path_config,
                },
                daemon=True,
            )
            thread.start()
    finally:
        listen.close()
        with contextlib.suppress(OSError):
            os.unlink(socket_path)


def _outcome_json(outcome: dict[str, Any]) -> str:
    return json.dumps(outcome, indent=2, default=str)


def main(argv: list[str] | None = None) -> int:
    """CLI: host-side broker entry points (``launch`` / ``submit`` / ``fleet-command`` / ``serve``).

    The one-shot subcommands read a JSON request object (``--request`` or stdin), validate it
    with the same shared checks, and — only when valid — perform the docker/compose call.
    ``--dry-run`` prints the argv it would execute. ``serve`` runs the host-side daemon the
    systemd user unit starts: it binds the seam socket and serves typed requests indefinitely.
    """
    parser = argparse.ArgumentParser(
        description="The host-side launch broker (the ONLY Docker API caller — its two "
                    "documented exceptions: the game board's read-only docker ps, "
                    "scripts/system_snapshot.py, and the archived one-time sonar-scanner "
                    "docker run, scripts/archive/backfill_sonar.py)."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (
        ("launch", "run one typed LaunchRequest (docker run)"),
        ("submit", "run one validated submit (docker compose run workflow-runner)"),
        ("fleet-command", "run one scale/drain/restart/submit fleet command"),
    ):
        p = sub.add_parser(name, help=handler)
        p.add_argument("--request", default=None, help="JSON request object (else stdin)")
        p.add_argument("--dry-run", action="store_true", help="validate + print argv, run nothing")
        p.add_argument("--compose-file", default=None)
    p_serve = sub.add_parser("serve", help="the host-side broker daemon (systemd unit)")
    p_serve.add_argument("--socket", default=broker_client.default_socket_path())
    p_serve.add_argument("--docker", default=os.environ.get("FINOPS_DOCKER_BIN", "docker"))
    p_serve.add_argument(
        "--compose", default=os.environ.get("FINOPS_DOCKER_COMPOSE_BIN", "docker-compose")
    )
    p_serve.add_argument("--compose-file", default=None)
    args = parser.parse_args(argv)

    if args.command == "serve":
        serve(
            args.socket,
            docker=args.docker,
            compose=args.compose,
            compose_file=args.compose_file,
        )
        return 0

    raw = args.request if args.request is not None else sys.stdin.read()
    try:
        request = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"launch refused: request is not valid JSON: {exc}", file=sys.stderr)
        return 2

    try:
        if args.command == "launch":
            outcome = launch(request, dry_run=args.dry_run)
        elif args.command == "submit":
            outcome = submit_run(
                request, compose_file=args.compose_file, dry_run=args.dry_run,
            )
        else:
            outcome = run_fleet_command(
                request, compose_file=args.compose_file, dry_run=args.dry_run,
            )
    except LaunchRequestError as exc:
        print("\n".join(str(exc).splitlines()), file=sys.stderr)
        return 2
    except (FileNotFoundError, PermissionError, OSError) as exc:
        print(
            f"docker is unavailable to the host-side broker ({exc}) — state "
            f"{STATE_DOCKER_UNAVAILABLE} (never a silent pass)",
            file=sys.stderr,
        )
        return 2
    print(_outcome_json(outcome))
    return 0 if outcome.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
