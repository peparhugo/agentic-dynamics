#!/usr/bin/env python3
"""The sibling-spawn wrapper — the orchestrator's ONE escalation, validated (proposal §2/D-14, §5/D-16).

The orchestrator tier is the only tier that mounts ``/var/run/docker.sock`` (ro, D-3/D-14).
Everything that socket does is gated by this wrapper: a spawn request is validated against the
per-step scope model (the closed five-scope vocabulary + the phase→scope authorization) and the
mount contract (the four + the D-2 auth set) **before** the ``docker`` call. A phase requesting an
undeclared scope, an unauthorized scope, a mount outside the contract, an undeclared network, or
an undeclared write flag fails here — never at the socket.

Two jobs, both read-only with respect to *what* is allowed (the compose + the scope model are the
fixed contract this module enforces):

    validate_spawn         — the five ordered checks (§5): scope ∈ vocab → phase-authorized →
                             mounts ⊆ scope's set (⊆ four + D-2) → network = scope's →
                             env = scope's (no undeclared write flag).
    validate_fleet_command — the D-14 fleet:commands check (resize/drain/restart against the
                             compose allowlist + bounded counts).

    spawn_sibling          — validate_spawn THEN build/run the ``docker run`` sibling command.
    build_phase_request    — build a scope-driven spawn request from a workflow phase (the
                             campaign-wrapper→sibling-cell mechanism, D-16).
    consume_fleet_commands — BRPOP ``fleet:commands`` (db1 / 6380) and dispatch validated
                             resize/drain commands to ``docker compose``.

This module is a script (``scripts/fleet/``), not a package plane. Its ONLY package import is the
scope model from the experiment plane (tier 1 — ``agentic_dynamics.experiment.experiment_spec``),
which is the source of truth for the vocabulary + authorization + configs; it never imports
``control``/``runtime``/``adapters``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# scripts/fleet/ -> the repo root is two parents up; put src/ on sys.path so the experiment
# plane resolves (the same "scripts/ is sys.path[0]" convention as the other scripts).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agentic_dynamics.experiment.experiment_spec import (  # noqa: E402
    PHASE_SCOPE_AUTHORIZATION,
    SCOPE_CONFIGS,
    SCOPE_VOCABULARY,
    phase_scope,
)

# ── The mount contract (the isolation constant, proposal §3) ─────────────────
#
# The ONLY host paths a ladder container may mount, per category. ``results`` mode is
# scope-dependent (rw for implementation/review_readonly/proposal_write, ro for
# research_readonly/adversarial_readonly); every other category's mode is fixed.

#: The D-2 auth set (proposal §0/D-2) — the five read-only auth mounts. The container auth home
#: is the host user's home (``HOME=/home/drseuss`` in the compose), so the claude symlink chain
#: (``~/.local/bin/claude`` → ``~/.local/share/claude/versions/<v>``) resolves unchanged.
AUTH_DIRS: frozenset[str] = frozenset(
    {
        "/home/drseuss/.claude",
        "/home/drseuss/.local/share/opencode",
        "/home/drseuss/.local/bin",
        "/home/drseuss/.local/share/claude",
        "/home/drseuss/.opencode/bin",
    }
)

#: The fixed-mount categories (proposal §3). ``mode`` is the CONTRACT's mode; ``results`` is
#: ``None`` because the scope narrows it (ro vs rw). A mount target not in this map (plus the
#: D-2 auth set) is outside the contract — rejected at step 3.
CONTRACT_TARGETS: dict[str, tuple[str, str | None]] = {
    "/tmp": ("worktree", "rw"),
    "/app/experiments/results": ("results", None),
    "/repo": ("repo", "ro"),
    #: The gitdir overlay (D-16 fix, 2026-08-31): a sibling cell must COMMIT its phase work
    #: into the shared worktree, which writes the worktree registration + objects + refs under
    #: /repo/.git — read-only there breaks every phase commit. Mirrors the results-overlay
    #: pattern: the repo working tree stays ro; only .git is overlaid rw.
    "/repo/.git": ("repo-git", "rw"),
    #: The repo at its HOST path (D-16 fix, 2026-08-31): worktrees in the shared /tmp namespace
    #: carry a ``gitdir:`` pointer to the repo's HOST path (e.g.
    #: /home/drseuss/ai-finops-framework/.git/...). Without this mount the pointer does not
    #: resolve inside a cell, git treats the worktree as foreign, and the runner rewrites the
    #: pointer to /repo/.git — wedging the worktree for the host. Mounting the repo at the
    #: SAME path in the container makes one pointer valid in both views.
    "/home/drseuss/ai-finops-framework": ("repo-alias", "ro"),
    "/home/drseuss/ai-finops-framework/.git": ("repo-alias-git", "rw"),
}
CONTRACT_TARGETS.update({d: ("auth", "ro") for d in AUTH_DIRS})

#: The write-flag env keys the scope model governs (G1/G2). ``FINOPS_KB_WRITE`` is allowed only
#: when the scope's ``write_flag`` is True (the ``implementation`` scope, and only for a P1-P11
#: emitting phase); ``FINOPS_ACTUATION_ARMED`` is NEVER set in the ladder (G2 — zero actuation
#: producers).
WRITE_FLAG_ENVS: frozenset[str] = frozenset({"FINOPS_KB_WRITE", "FINOPS_ACTUATION_ARMED"})

#: A write flag is "set" only on an explicit truthy value (the FINOPS_* convention: "1" or "true").
_TRUTHY = {"1", "true", "True", "yes", "on"}

# ── The D-14 fleet:commands contract ─────────────────────────────────────────

#: The compose allowlist — the ladder service names a resize/drain/restart may target. Anything
#: else is rejected (the spawn-wrapper is the audit surface for "the socket appears in exactly one
#: tier and only touches these services").
COMPOSE_ALLOWLIST: frozenset[str] = frozenset(
    {
        "story-worker", "analysis-worker", "review-unit",
        "kb-chroma", "kb-ledger", "kb-registry", "kb-neo4j",
        "kb-produce", "kb-produce-sources", "kb-produce-facts", "kb-produce-campaign-evidence",
        "run-single", "supervise", "orphan-sweep",
        "egress", "fleet-manager", "control-room", "game-board", "trigger-reviews",
        "registry-cli", "bundle-reference-check", "report-tools",
        "campaign-wrapper", "workflow-runner",
    }
)

#: The bounded scale ceiling (D-14: "count bounded"). A resize beyond this is refused.
MAX_SCALE: int = 32

FLEET_ACTIONS: frozenset[str] = frozenset({"scale", "drain", "restart"})

#: The orchestrator image the sibling spawn uses by default (fleet/orchestrator is base + docker
#: CLI + this wrapper; the sibling PHASE cells run fleet/base, not the orchestrator).
ORCHESTRATOR_IMAGE = "fleet/orchestrator"
CELL_IMAGE = "fleet/base"

#: The fleet:commands + review-trigger Redis keys (db1 / 6380 — the D-14 channel).
COMMANDS_KEY = "fleet:commands"


class SpawnValidationError(ValueError):
    """Raised when a spawn request fails validation (the socket is never reached)."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("spawn refused:\n" + "\n".join(f"  - {e}" for e in errors))


def _scope_config(scope: str) -> dict[str, Any]:
    """The declared config for a scope (its SCOPE_CONFIGS row), or the empty dict if absent."""
    return SCOPE_CONFIGS.get(scope, {})


# ── The five-check validation (§5, D-16) ─────────────────────────────────────


def validate_spawn(request: dict[str, Any], *, phase_scopes: dict[str, str] | None = None) -> list[str]:
    """Validate a spawn request against the scope model. Empty list = valid.

    The five ordered checks (§5) run in order and stop at the first failure family — a request
    that fails step 1 (scope ∉ vocab) never reaches the mount/env checks, exactly as the proposal
    specifies ("fails at step 1 or 2 — before the socket call").

    ``request`` shape::

        {"phase": <name>, "scope": <one of five>, "mounts": [{"target", "mode"}...],
         "network": <name>, "env": {<k>: <v>...}}

    ``phase_scopes`` overrides the phase→scope authorization resolution (a test injects the
    spec's DECLARED scopes here; when ``None``, :data:`PHASE_SCOPE_AUTHORIZATION` is the fallback).
    """
    errors: list[str] = []
    phase = str(request.get("phase", ""))
    scope = str(request.get("scope", ""))

    # Step 1 — the scope must be a member of the closed five-scope vocabulary.
    if scope not in SCOPE_VOCABULARY:
        errors.append(
            f"step 1: scope {scope!r} is not in the closed five-scope vocabulary "
            f"{sorted(SCOPE_VOCABULARY)}"
        )
        return errors

    # Step 2 — the phase must be AUTHORIZED for that scope (its declared allowed scope).
    if phase_scopes is not None:
        authorized = phase_scopes.get(phase)
    else:
        authorized = PHASE_SCOPE_AUTHORIZATION.get(phase)
    if authorized != scope:
        errors.append(
            f"step 2: phase {phase!r} is not authorized for scope {scope!r} "
            f"(authorized: {authorized!r})"
        )
        return errors

    cfg = _scope_config(scope)

    # Step 3 — every mount's target ∈ the four + D-2, and its mode matches the scope/contract.
    for m in request.get("mounts", []) or []:
        target = str((m or {}).get("target", ""))
        mode = str((m or {}).get("mode", ""))
        if target not in CONTRACT_TARGETS:
            errors.append(
                f"step 3: mount target {target!r} is outside the four-mount contract + the "
                f"D-2 auth set"
            )
            continue
        category, contract_mode = CONTRACT_TARGETS[target]
        if category == "results":
            expected = cfg.get("results_mode", "rw")
            if mode != expected:
                errors.append(
                    f"step 3: results mount mode {mode!r} != scope {scope} results_mode "
                    f"{expected!r}"
                )
        elif mode != contract_mode:
            errors.append(
                f"step 3: mount {target!r} mode {mode!r} != contract {contract_mode!r}"
            )

    # Step 4 — the network must be exactly the scope's declared network.
    network = str(request.get("network", ""))
    if network != cfg.get("network", "fleet-net"):
        errors.append(
            f"step 4: network {network!r} != scope {scope} network "
            f"{cfg.get('network', 'fleet-net')!r}"
        )

    # Step 5 — no undeclared write flag in the env.
    for k, v in (request.get("env", {}) or {}).items():
        if k not in WRITE_FLAG_ENVS:
            continue
        if str(v) not in _TRUTHY:
            continue
        if k == "FINOPS_ACTUATION_ARMED":
            errors.append("step 5: FINOPS_ACTUATION_ARMED is never set in the ladder (G2)")
        elif not cfg.get("write_flag", False):
            errors.append(
                f"step 5: scope {scope} does not authorize FINOPS_KB_WRITE=1 (undeclared "
                f"write flag)"
            )
    return errors


# ── The D-14 fleet:commands validation ───────────────────────────────────────


def validate_fleet_command(
    command: dict[str, Any],
    *,
    allowlist: frozenset[str] | None = None,
    max_scale: int = MAX_SCALE,
) -> list[str]:
    """Validate a fleet:commands command against the compose allowlist + bounded counts.

    ``command`` is the shape the fleet-manager LPUSHes (``fleet_manager._send_command``):
    ``{"action": scale|drain|restart, "service": ..., "count": ..., "backoff": ...}``. A resize/
    drain/restart is refused unless its ``service`` is in the compose allowlist and (for scale)
    its ``count`` is bounded. The mount contract is implicit — the compose allowlist IS the
    declaration of what may be scaled, so an unknown service name is the mount-contract breach.
    """
    errors: list[str] = []
    action = str(command.get("action", ""))
    if action not in FLEET_ACTIONS:
        errors.append(f"action {action!r} is not one of {sorted(FLEET_ACTIONS)}")
        return errors

    allowed = allowlist if allowlist is not None else COMPOSE_ALLOWLIST
    service = str(command.get("service", ""))
    if service not in allowed:
        errors.append(f"service {service!r} is not in the compose allowlist")

    if action == "scale":
        count = command.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or not (0 <= count <= max_scale):
            errors.append(f"scale count {count!r} is not an int in [0, {max_scale}]")
    if action == "restart":
        backoff = command.get("backoff")
        if backoff is not None and (
            not isinstance(backoff, (int, float)) or isinstance(backoff, bool) or backoff < 0
        ):
            errors.append(f"restart backoff {backoff!r} is not a non-negative number")
    return errors


# ── The spawn mechanism (validate THEN socket) ───────────────────────────────


def build_spawn_argv(
    request: dict[str, Any],
    *,
    docker: str = "docker",
    image: str | None = None,
    command: list[str] | None = None,
    name: str | None = None,
) -> list[str]:
    """Build the ``docker run`` argv for a sibling container (called only AFTER validation).

    The container runs as a sibling cell with the request's mounts/network/env. The socket is
    deliberately NOT mounted on the sibling (it is a phase CELL, not the orchestrator) — the
    escalation stays with the orchestrator that spawned it (D-3).
    """
    argv = [docker, "run", "--rm", "-i"]
    if name:
        argv += ["--name", name]
    for m in request.get("mounts", []) or []:
        source = str((m or {}).get("source", ""))
        target = str((m or {}).get("target", ""))
        mode = str((m or {}).get("mode", "ro"))
        argv += ["-v", f"{source}:{target}:{mode}"]
    argv += ["--network", str(request.get("network", "fleet-net"))]
    for k, v in (request.get("env", {}) or {}).items():
        argv += ["-e", f"{k}={v}"]
    argv += [image or CELL_IMAGE]
    argv += command or request.get("command", [])
    return argv


def spawn_sibling(
    request: dict[str, Any],
    *,
    phase_scopes: dict[str, str] | None = None,
    docker: str = "docker",
    image: str | None = None,
    command: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Validate a spawn request, then (if valid) run the sibling container.

    The ordering is the load-bearing guarantee: :func:`validate_spawn` runs FIRST, and any error
    raises :class:`SpawnValidationError` before a single ``docker`` argv is built — a compromised
    phase can never reach the socket with a request it was not authorized for. On success returns
    ``{"ok", "argv", "returncode"?, "stdout"?, "stderr"?}`` (``dry_run`` builds the argv only).
    """
    errors = validate_spawn(request, phase_scopes=phase_scopes)
    if errors:
        raise SpawnValidationError(errors)

    argv = build_spawn_argv(request, docker=docker, image=image, command=command)
    if dry_run:
        return {"ok": True, "argv": argv, "returncode": None}

    proc = subprocess.run(argv, capture_output=True, text=True)
    return {
        "ok": proc.returncode == 0,
        "argv": argv,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def build_phase_request(
    phase_def: dict[str, Any],
    *,
    goal: str,
    workdir: str | Path,
    model: str,
    spec_name: str = "",
    phase_scopes: dict[str, str] | None = None,
    command: list[str] | None = None,
) -> dict[str, Any]:
    """Build a scope-driven spawn request for one workflow phase (the campaign-wrapper mechanism).

    Resolves the phase's authorized scope (declared ``scope:`` → authorization table), then
    assembles the four-mount contract (with the scope's results mode) + the scope's network + the
    canonical cell env (the write flag only when the scope authorizes it). The result feeds
    :func:`spawn_sibling` — which re-validates it before the socket call. ``command`` is the
    sibling container's entrypoint (defaults to the phase-runner; see ``phase_runner.py``).
    """
    scope = phase_scope(phase_def)
    if scope is None:
        # No declared scope and no authorization-table entry — the spawn will fail at step 2.
        scope = ""
    cfg = _scope_config(scope) or {}
    results_mode = cfg.get("results_mode", "rw")

    auth_home = os.environ.get("AUTH_HOME", "/home/drseuss")
    mounts = [
        {"source": os.environ.get("FINOPS_WORKTREE_ROOT", "/tmp"),
         "target": "/tmp", "mode": "rw"},
        {"source": os.environ.get("FINOPS_RESULTS_DIR", str(_REPO_ROOT / "experiments" / "results")),
         "target": "/app/experiments/results", "mode": results_mode},
        {"source": os.environ.get("FINOPS_REPO_DIR", str(_REPO_ROOT)),
         "target": "/repo", "mode": "ro"},
        {"source": f"{os.environ.get('FINOPS_REPO_DIR', str(_REPO_ROOT))}/.git",
         "target": "/repo/.git", "mode": "rw"},
    ]
    repo_home = os.environ.get("FINOPS_REPO_DIR", str(_REPO_ROOT))
    mounts += [
        {"source": repo_home, "target": repo_home, "mode": "ro"},
        {"source": f"{repo_home}/.git", "target": f"{repo_home}/.git", "mode": "rw"},
    ]
    for d in AUTH_DIRS:
        mounts.append({"source": d, "target": d, "mode": "ro"})

    env: dict[str, str] = {
        "FINOPS_REDIS_HOST": os.environ.get("FINOPS_REDIS_HOST", "finops-queue"),
        "FINOPS_REDIS_PORT": os.environ.get("FINOPS_REDIS_PORT", "6379"),
        "FINOPS_REDIS_DB": "1",
        "FINOPS_KB_DB": "2",
        "FINOPS_WORKTREE_ROOT": "/tmp",
        "HOME": auth_home,
        "OPENCODE_BIN": f"{auth_home}/.opencode/bin/opencode",
        "CLAUDE_BIN": f"{auth_home}/.local/bin/claude",
        "FINOPS_CELL_ID": f"{spec_name}:{phase_def.get('name', 'phase')}",
        #: The CLI's subagent (Task) socket lives under XDG_RUNTIME_DIR (/run/user/<uid> on the
        #: host — not mounted into cells, which silently disabled the Task tool inside them).
        "XDG_RUNTIME_DIR": "/tmp/cc-runtime",
    }
    if cfg.get("write_flag", False):
        # The implementation scope MAY emit (P1-P11) — the write flag is authorized; the
        # compose-level "P1-P10 units only" placement is the finer gate, not this wrapper.
        env["FINOPS_KB_WRITE"] = "1"

    return {
        "phase": str(phase_def.get("name", "")),
        "scope": scope,
        "mounts": mounts,
        "network": cfg.get("network", "fleet-net"),
        "env": env,
        "command": command or [
            "python3", "scripts/fleet/phase_runner.py",
            "--spec-name", spec_name,
            "--phase", str(phase_def.get("name", "")),
            "--goal", goal,
            "--model", model,
            "--workdir", "/tmp",
        ],
    }


# ── The fleet:commands BRPOP consumer (D-14) ─────────────────────────────────


def _connect_redis() -> Any:
    """Connect to the framework Redis (db1 / 6380) with backoff (imported lazily — validation
    is pure and must not require redis)."""
    import redis  # noqa: PLC0415 — the consumer needs it, the pure validators must not

    host = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
    port = int(os.environ.get("FINOPS_REDIS_PORT", "6379"))
    db = int(os.environ.get("FINOPS_REDIS_DB", "1"))
    delay = 2.0
    while True:
        try:
            client = redis.Redis(
                host=host, port=port, db=db, decode_responses=True, socket_connect_timeout=5,
            )
            client.ping()
            return client
        except Exception as exc:  # noqa: BLE001 — the consumer must survive a Redis blip
            print(f"[spawn-wrapper] redis unavailable ({exc}); retrying in {delay:.0f}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30.0)


def consume_fleet_commands(
    *,
    compose_file: str | None = None,
    dry_run: bool = False,
    once: bool = False,
) -> None:
    """BRPOP ``fleet:commands`` and dispatch validated resize/drain/restart commands (D-14).

    Each popped command is validated against :func:`validate_fleet_command` BEFORE any
    ``docker compose`` call; an invalid command is logged and dropped (never acted on). This is
    the orchestrator's "hands" — the supervisor LPUSHes, this consumer validates + executes.
    """
    client = _connect_redis()
    compose_file = compose_file or str(_REPO_ROOT / "infrastructure" / "docker-compose.ladder.yml")
    compose = os.environ.get("DOCKER_COMPOSE", "docker-compose")

    print(f"[spawn-wrapper] consuming {COMMANDS_KEY} (compose {compose_file})", flush=True)
    while True:
        result = client.brpop(COMMANDS_KEY, timeout=10)
        if result is None:
            if once:
                return
            continue
        _key, raw = result
        try:
            command = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[spawn-wrapper] dropping malformed command: {raw!r}", flush=True)
            continue
        errors = validate_fleet_command(command)
        if errors:
            print(f"[spawn-wrapper] REFUSED {command}: {errors}", flush=True)
            continue
        action, service = command["action"], command["service"]
        if action == "scale":
            argv = [compose, "-f", compose_file, "up", "-d", "--scale",
                    f"{service}={command['count']}", service]
        elif action == "drain":
            argv = [compose, "-f", compose_file, "stop", service]
        else:  # restart
            argv = [compose, "-f", compose_file, "restart", service]
        print(f"[spawn-wrapper] DISPATCH {action} {service}: {argv}", flush=True)
        if not dry_run:
            subprocess.run(argv, check=False)
        if once:
            return


def main(argv: list[str] | None = None) -> int:
    """CLI: ``validate`` (a spawn request JSON on stdin) or ``consume`` (the BRPOP loop)."""
    parser = argparse.ArgumentParser(description="The sibling-spawn wrapper (D-14/D-16).")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate a spawn request (JSON on stdin)")
    p_consume = sub.add_parser("consume", help="BRPOP fleet:commands and dispatch")
    p_consume.add_argument("--once", action="store_true")
    p_consume.add_argument("--dry-run", action="store_true")
    p_consume.add_argument("--compose-file", default=None)
    args = parser.parse_args(argv)

    if args.command == "validate":
        request = json.loads(sys.stdin.read())
        errors = validate_spawn(request)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 2
        print("spawn valid")
        return 0

    consume_fleet_commands(compose_file=args.compose_file, dry_run=args.dry_run, once=args.once)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
