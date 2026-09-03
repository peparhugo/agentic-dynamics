#!/usr/bin/env python3
"""The launch broker — the host-side (non-container) holder of the Docker socket (b3_launch_broker, fb2_broker_hostside).

The socket leaves the container. Before this module the orchestrator tier mounted
``/var/run/docker.sock`` and one large trusted module (``spawn_wrapper.py``) both validated
AND invoked arbitrary docker commands — and ``:ro`` on the filesystem mount does not
constrain Docker Engine authority. This broker is the ONLY component that calls the Docker
API, and it accepts ONLY a TYPED launch request — arbitrary docker CLI capability is never
exposed to any tier:

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

This module is a script (``scripts/fleet/``), not a package plane. Its package imports are the
tier-0 path object (``agentic_dynamics.core.paths.PathConfig``) and the tier-1 scope config
table (``agentic_dynamics.experiment.experiment_spec.SCOPE_CONFIGS``) — the same tier-0/1
surface ``spawn_wrapper.py`` already imports. It never imports ``control`` / ``runtime`` /
``adapters``; the docker call is a plain ``subprocess`` over an argv this module builds (the
project's fleet images carry the docker CLI for the operator's ``build.sh``; the broker is the
only module that RUNS it).
"""

from __future__ import annotations

import argparse
import contextlib
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
    WORKTREE_TARGET,
    LaunchRequestError,
    mounts_for_profile,
    sanitize_namespace,
    validate_launch_request,
)

from agentic_dynamics.core.paths import PathConfig  # noqa: E402

__all__ = [
    "AUTH_CRED_FILE",
    "IMAGE_NAMESPACE",
    "JOB_IMAGE_PATTERN",
    "LAUNCH_NETWORK",
    "MOUNT_PROFILES",
    "REPO_TARGET",
    "RESULTS_TARGET",
    "STATE_TARGET",
    "VERIFIER_MARKER",
    "WORKTREE_TARGET",
    "LaunchRequestError",
    "LAUNCH_REQUEST_FIELDS",
    "MAX_LAUNCH_TIMEOUT_SECONDS",
    "MIN_LAUNCH_TIMEOUT_SECONDS",
    "mounts_for_profile",
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

    A refusal raises :class:`LaunchRequestError` BEFORE any docker argv is built. On success
    returns ``{"ok", "argv", "returncode", "stdout", "stderr"}`` (``dry_run`` builds the argv
    only). ``timeout_seconds`` on the request bounds the docker subprocess when positive.
    """
    errors = validate_launch_request(request, path_config=path_config)
    if errors:
        raise LaunchRequestError(errors)

    # The shared scope-model validation (the same six checks the wrapper runs) — lazily, so
    # launch_broker never imports spawn_wrapper at module scope (spawn_wrapper imports the
    # pure contract module broker_contract, never this module — the fb2 seam boundary).
    import spawn_wrapper  # noqa: PLC0415

    cfg = path_config or spawn_wrapper.default_path_config()
    scope_errors = spawn_wrapper.validate_spawn(request, path_config=cfg)
    if scope_errors:
        raise LaunchRequestError(scope_errors)

    # The broker mounts ITS OWN profile expansion — never a caller-supplied mount list.
    profile = str(request.get("mount_profile", ""))
    mounts = mounts_for_profile(
        profile,
        path_config=cfg,
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
    """
    compose_file = compose_file or _compose_file_default()
    job_id = str(command.get("job_id", "") or "")
    argv = [compose, "-f", compose_file, "run", "--rm"]
    if job_id:
        argv += ["-e", f"FINOPS_CELL_ID={job_id}"]
    argv += [
        "workflow-runner",
        "python3", "scripts/run_workflow.py",
        "--spec", str(command.get("spec", "")),
        "--goal", str(command.get("goal", "")),
        "--model", str(command.get("model", "")),
        "--workdir", str(command.get("workdir", "")),
        "--orchestrator",
    ]
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

    errors = spawn_wrapper.validate_submit_request(
        command, repo_root=repo_root, phase_scopes=phase_scopes, path_config=path_config,
    )
    if errors:
        raise LaunchRequestError(errors)

    argv = build_submit_argv(command, compose=compose, compose_file=compose_file)
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
        description="The host-side launch broker (the ONLY Docker API caller)."
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
