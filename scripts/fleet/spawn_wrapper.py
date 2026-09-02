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

    validate_spawn         — the six ordered checks: scope ∈ vocab → phase-authorized →
                             mounts ⊆ scope's set (⊆ four + D-2) → network = scope's →
                             env = scope's (no undeclared write flag) → the LEASE block
                             (admission_leases p2: reserved_cost_usd / hard_cap_usd /
                             budget_lease_id / concurrency_lease_id / expires_at, well-formed
                             and unexpired). Steps 1-5 are §5's original scope/isolation
                             contract; step 6 is the spend contract layered on top — a cell may
                             now be refused for being *unbudgeted* as well as for being
                             *unauthorized*.
    validate_fleet_command — the D-14 fleet:commands check (resize/drain/restart against the
                             compose allowlist + bounded counts).

    spawn_sibling          — validate_spawn THEN build/run the ``docker run`` sibling command.
    build_phase_request    — build a scope-driven spawn request from a workflow phase (the
                             campaign-wrapper→sibling-cell mechanism, D-16).
    consume_fleet_commands — BRPOP ``fleet:commands`` (db1 / 6380) and dispatch validated
                             resize/drain/restart/submit commands to ``docker compose``,
                             wiring a submitted job's board record through
                             launching -> running -> completed/failed (+ the ``fleet_jobs``
                             DLQ on refusal or a nonzero exit, p2_launch_handler).

This module is a script (``scripts/fleet/``), not a package plane. Its package imports are the
scope model from the experiment plane (tier 1 — ``agentic_dynamics.experiment.experiment_spec``),
which is the source of truth for the vocabulary + authorization + configs, and the tier-0
admission vocabulary (``agentic_dynamics.core.admission_context``) for step 6's pure lease-block
check. It never imports ``control``/``runtime``/``adapters`` — the admission *decision* stays in
``control.admission``; what lands here is only the structural validator, which is stdlib-only and
so preserves this module's invariant that validation never requires ``redis``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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

from agentic_dynamics.core.admission_context import (  # noqa: E402
    LEASE_REQUEST_FIELDS,
    LeaseContext,
    admission_required,
    validate_lease_fields,
)
from agentic_dynamics.experiment.compile_experiment import (  # noqa: E402
    SpecError,
    compile_spec,
)
from agentic_dynamics.experiment.experiment_spec import (  # noqa: E402
    PHASE_SCOPE_AUTHORIZATION,
    SCOPE_CONFIGS,
    SCOPE_VOCABULARY,
    load_spec,
    phase_scope,
)

# ── The mount contract (the isolation constant, proposal §3) ─────────────────
#
# The ONLY host paths a ladder container may mount, per category. ``results`` mode is
# scope-dependent (rw for implementation/review_readonly/proposal_write, ro for
# research_readonly/adversarial_readonly); every other category's mode is fixed.

#: The D-2 auth set (proposal §0/D-2) — the four read-only auth mounts. The container auth home
#: is the host user's home (``HOME=/home/drseuss`` in the compose), so the claude symlink chain
#: (``~/.local/bin/claude`` → ``~/.local/share/claude/versions/<v>``) resolves unchanged.
#:
#: NOTE (P0-3, control-plane stabilization): ``~/.local/share/opencode`` is deliberately NOT
#: here. The sibling's CLI state is the per-attempt :data:`STATE_TARGET` namespace (rw, mounted
#: by :func:`build_phase_request`), and its credential is the :data:`AUTH_CRED_FILE` file mount
#: (ro) — the host's LIVE opencode state (opencode.db, sessions, compaction) never enters a
#: cell in any mode, and no two cells ever share a writable CLI-state directory.
AUTH_DIRS: frozenset[str] = frozenset(
    {
        "/home/drseuss/.claude",
        "/home/drseuss/.local/bin",
        "/home/drseuss/.local/share/claude",
        "/home/drseuss/.opencode/bin",
    }
)

#: P0-3: the credential FILE mount (ro). Auth is a single file, never the host's whole state
#: directory: a cell mounts ``<host auth.json>`` at ``/auth/opencode_auth.json`` and the
#: entrypoint seeds it into the cell's OWN state namespace. Mirrors the compose-level
#: ``/auth/opencode_auth.json`` contract.
AUTH_CRED_FILE = "/auth/opencode_auth.json"

#: P0-3: the per-attempt CLI-state target (rw). Every spawned sibling gets a UNIQUE host
#: namespace under :data:`STATE_ROOT` mounted here, and ``XDG_DATA_HOME``/``XDG_CONFIG_HOME``/
#: ``XDG_CACHE_HOME`` point into it — opencode's session DB, SQLite/WAL, and compaction state
#: are private to one run/step/attempt. Two concurrent cells can never see each other's
#: session IDs (review finding P0: "all scaled OpenCode cells appear to share the same
#: writable OpenCode state directory").
STATE_TARGET = "/state"
STATE_ROOT = os.environ.get("FINOPS_OPENCODE_STATE_ROOT", "/tmp/opencode_state")

#: The XDG redirect vars the state namespace sets, so the CLI's writable state lands in the
#: per-attempt namespace instead of the image's default ``~/.local/share``.
STATE_ENV_KEYS: tuple[str, ...] = ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME")

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
    #: P0-3: the per-attempt CLI-state namespace (rw). The ONE writable state a cell gets —
    #: mounted as a unique per-run/step/attempt host dir, never a shared pool directory.
    STATE_TARGET: ("state", "rw"),
}
CONTRACT_TARGETS.update({d: ("auth", "ro") for d in AUTH_DIRS})
CONTRACT_TARGETS[AUTH_CRED_FILE] = ("auth-file", "ro")

#: The write-flag env keys the scope model governs (G1/G2). ``FINOPS_KB_WRITE`` is allowed only
#: when the scope's ``write_flag`` is True (the ``implementation`` scope, and only for a P1-P11
#: emitting phase); ``FINOPS_ACTUATION_ARMED`` is NEVER set in the ladder (G2 — zero actuation
#: producers).
WRITE_FLAG_ENVS: frozenset[str] = frozenset({"FINOPS_KB_WRITE", "FINOPS_ACTUATION_ARMED"})

#: A write flag is "set" only on an explicit truthy value (the FINOPS_* convention: "1" or "true").
_TRUTHY = {"1", "true", "True", "yes", "on"}

#: The verifier request marker (g1_verifier_mount, 2026-09-02). ``build_verifier_request``
#: stamps this on the request so :func:`validate_spawn` can enforce the READ-ONLY-for-candidate
#: contract at validation time — a verifier request whose worktree/.git mounts are ``rw`` is
#: refused BEFORE any spawn, never behaviorally via ``--no-commit``. An agent-phase request
#: (no marker) keeps its ``rw`` candidate contract unchanged.
VERIFIER_REQUEST_MARKER = "verifier"

#: The mount CATEGORIES a verifier request may carry, every one READ-ONLY (F1/g1_verifier_mount).
#: The candidate surface the verifier runs its suite against — the worktree namespace
#: (``worktree``), the repo (``repo``) and both git dirs (``repo-git`` / ``repo-alias-git``),
#: plus the host-path alias (``repo-alias``) — is mounted ``ro``: a verifier needs the
#: candidate's TREE, never the ability to change it. Categories OUTSIDE this set (``results``,
#: ``state``, the ``auth``/``auth-file`` credential mounts) are never on a verifier request —
#: validation refuses them if present.
VERIFIER_READONLY_CATEGORIES: frozenset[str] = frozenset(
    {"worktree", "repo", "repo-git", "repo-alias", "repo-alias-git"}
)

#: Step 6's vocabulary (admission_leases p2), re-exported from the tier-0 admission contract so
#: the wrapper's own callers and tests can name the block without reaching past this module.
#: Owned by ``core.admission_context`` — one definition, shared by the fleet wrapper, the
#: enqueue producer, and the controller, so the three can never drift.
LEASE_FIELDS: tuple[str, ...] = LEASE_REQUEST_FIELDS

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

#: The supervisor's command vocabulary (D-14, extended for the submit verb). "submit" adds
#: a fourth action alongside the pool-shaping trio (scale/drain/restart): it commands the
#: orchestrator to VALIDATE + LAUNCH a containerized workflow run, rather than reshaping an
#: already-running service pool. Both families share one Redis channel (``fleet:commands``)
#: and one validate-before-socket discipline; they differ only in what "valid" means.
FLEET_ACTIONS: frozenset[str] = frozenset({"scale", "drain", "restart", "submit"})

# ── The submit contract (proposal: fleet_job_submission, p1_submit_contract) ────────────────
#
# "submit" is deliberately NOT a scale/drain/restart-shaped command: it does not name a
# compose ``service`` from the allowlist, it names a *spec* (a workflow definition) plus the
# goal/model/workdir a fresh containerized run needs. The isolation contract still applies —
# a submit is refused unless it resolves to a spec that compile-validates, a whitelisted
# model, a worktree-scoped workdir, and (for every phase the spec declares) a mount set that
# stays inside the four-mount contract + the D-2 auth set. None of this is a coordination
# lock: two valid submits for the same or different specs are both accepted, and refusal is
# ALWAYS about validity, never about "another job is already running" (proposal hard rule 4,
# "NO ORCHESTRATOR LOCK" — overlap is the measurement apparatus's problem, not this gate's).

#: The models a submit request may target — the same seven models the project's experiment
#: matrix runs (AGENTS.md "Models in use"). A model outside this set is refused before the
#: spec is even compiled: an unlisted model has no pricing entry (measurement.efficiency's
#: ``PROVIDER_PRICING``) and no operational support (no queue worker expects it), so it is a
#: closed vocabulary here for the same reason ``SCOPE_VOCABULARY`` is closed.
MODEL_WHITELIST: frozenset[str] = frozenset(
    {
        "deepseek/deepseek-v4-flash",
        "deepseek/deepseek-v4-pro",
        "anthropic/claude-haiku-4-5",
        "anthropic/claude-sonnet-5",
        "openai/gpt-5.6-luna",
        "openai/gpt-5.6-sol",
        "openai/gpt-5.6-terra",
    }
)

#: The two directories a submit's ``spec`` path is allowed to resolve under (the rec-3 split
#: documented on ``load_spec``: experiments vs. work-order workflows). A spec path escaping
#: both — via an absolute path elsewhere, or a ``..`` traversal — is refused at step 1, before
#: the file is even opened; this is the same "outside the contract" refusal the mount check
#: gives a bad mount target, applied to the ONE path a submit request gets to name freely.
SUBMIT_SPEC_DIRS: tuple[str, ...] = ("workflows", "experiments/definitions")

#: Substrings that mark a string as naming a HOST service rather than a worktree path — the
#: story-agent Redis on 6379 (AGENTS.md: "Story agents build Flask/Celery apps against
#: finops-redis on 6379 ... Never run the queue on 6379") and its compose hostname/loopback
#: spellings. A workdir (or any other submit field checked against this) containing one of
#: these is refused: the isolation the docker layer buys is worthless if a "worktree path"
#: can smuggle a host-service address through validation.
HOST_SERVICE_MARKERS: tuple[str, ...] = ("6379", "127.0.0.1", "finops-redis", "localhost")

#: The orchestrator image the sibling spawn uses by default (fleet/orchestrator is base + docker
#: CLI + this wrapper; the sibling PHASE cells run fleet/base, not the orchestrator).
ORCHESTRATOR_IMAGE = "fleet/orchestrator"
CELL_IMAGE = "fleet/base"

#: The per-job image namespace a submit request's optional ``image`` field may name
#: (p3_base_image_caching — ``scripts/fleet/build.sh job <name>`` builds
#: ``infrastructure/jobs/<name>/Dockerfile`` FROM ``fleet/base`` with ``--cache-from
#: fleet/base``, tagged ``fleet/job-<name>``). This is a CLOSED namespace, not an arbitrary
#: image override: a submit can never name ``fleet/base``/``fleet/orchestrator``/
#: ``fleet/supervisor`` directly (those are the ladder's own tiers, not a job's to pick) or an
#: attacker-supplied third-party image on the one socket-holding service's phase cells. The
#: matched image is threaded through to the orchestrator's sibling-cell spawn as
#: ``--cell-image`` (``scripts/run_workflow.py``) — it changes what image the PHASE cells run,
#: never the orchestrator/workflow-runner container itself.
JOB_IMAGE_PATTERN = re.compile(r"^fleet/job-[a-z0-9][a-z0-9_-]*$")

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


def validate_spawn(
    request: dict[str, Any],
    *,
    phase_scopes: dict[str, str] | None = None,
    now: float | None = None,
    require_lease: bool | None = None,
) -> list[str]:
    """Validate a spawn request against the scope model + the spend contract. Empty list = valid.

    The six ordered checks run in order and stop at the first failure family — a request that
    fails step 1 (scope ∉ vocab) never reaches the mount/env/lease checks, exactly as the
    proposal specifies ("fails at step 1 or 2 — before the socket call").

    ``request`` shape::

        {"phase": <name>, "scope": <one of five>, "mounts": [{"target", "mode"}...],
         "network": <name>, "env": {<k>: <v>...},
         # step 6, admission_leases p2 — required when the gate is armed:
         "reserved_cost_usd": <float>, "hard_cap_usd": <float|None>,
         "budget_lease_id": <str>, "concurrency_lease_id": <str>, "expires_at": <epoch s>}

    ``phase_scopes`` overrides the phase→scope authorization resolution (a test injects the
    spec's DECLARED scopes here; when ``None``, :data:`PHASE_SCOPE_AUTHORIZATION` is the fallback).

    ``require_lease`` overrides step 6's strictness; ``None`` (the default) resolves it from
    ``FINOPS_ADMISSION_REQUIRED``. Armed ⇒ a spawn with no lease block is refused. Disarmed ⇒
    the block is optional — but a *partial* or malformed one is refused either way, because a
    request that looks budgeted and is not is worse than one that plainly is not.

    ``now`` is the clock step 6 judges expiry against (injected for deterministic tests; defaults
    to the wall clock).
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
    # A VERIFIER request (the DockerVerifierExecutor's read-only cell — stamped by
    # build_verifier_request) is a DIFFERENT contract: it may carry ONLY the read-only
    # candidate surface (worktree/repo/repo-git/repo-alias/repo-alias-git, all ro), never the
    # results/state/auth mounts of an agent cell. Read-only-for-candidate is enforced HERE, at
    # validation time — a verifier request that would mount its candidate rw is refused before
    # the socket call, never left to the child's --no-commit.
    is_verifier = bool(request.get(VERIFIER_REQUEST_MARKER))
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
        if is_verifier:
            # The verifier's mount contract (g1_verifier_mount): candidate surface only, ro.
            if category not in VERIFIER_READONLY_CATEGORIES:
                errors.append(
                    f"step 3: verifier mount {target!r} (category {category!r}) is outside "
                    f"the read-only candidate surface — a verifier carries no "
                    f"results/state/auth mounts"
                )
            elif mode != "ro":
                errors.append(
                    f"step 3: verifier mount {target!r} mode {mode!r} != ro — the verifier "
                    f"cannot write its candidate (read-only-for-candidate)"
                )
            continue
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

    # Step 6 — the LEASE block (admission_leases p2). The isolation contract (steps 1-5) says
    # what a cell may TOUCH; this says whether its spend was reserved. A cell that is perfectly
    # scoped and completely unbudgeted is exactly the run the audit found: authorized to write,
    # unaccounted for in dollars.
    #
    # Structural only — "is this lease block well-formed and still live?", never "is this lease
    # outstanding in the registry?". The second question needs Redis, and this validator's
    # invariant is that it is pure (it runs in the orchestrator's hot path and in tests with no
    # infrastructure). The registry-backed check is
    # ``control.admission.AdmissionController.verify``, which the orchestrator may call
    # separately.
    strict = admission_required() if require_lease is None else bool(require_lease)
    lease_errors = validate_lease_fields(request, required=strict)
    for message in lease_errors:
        errors.append(f"step 6: {message}")
    if not lease_errors and "expires_at" in request:
        moment = time.time() if now is None else now
        if float(request["expires_at"]) <= moment:
            errors.append(
                f"step 6: lease expired at {request['expires_at']} (now {moment}) — the "
                f"admission's claim is gone; re-admit before spawning"
            )
    return errors


# ── The D-14 fleet:commands validation ───────────────────────────────────────


def validate_fleet_command(
    command: dict[str, Any],
    *,
    allowlist: frozenset[str] | None = None,
    max_scale: int = MAX_SCALE,
    repo_root: Path | str | None = None,
    phase_scopes: dict[str, str] | None = None,
) -> list[str]:
    """Validate a fleet:commands command against the compose allowlist + bounded counts.

    ``command`` is the shape the fleet-manager LPUSHes (``fleet_manager._send_command``):
    ``{"action": scale|drain|restart, "service": ..., "count": ..., "backoff": ...}``. A resize/
    drain/restart is refused unless its ``service`` is in the compose allowlist and (for scale)
    its ``count`` is bounded. The mount contract is implicit — the compose allowlist IS the
    declaration of what may be scaled, so an unknown service name is the mount-contract breach.

    A ``submit`` command has a different shape entirely (``{"spec", "goal", "model",
    "workdir"}`` — no ``service``/``count``), so it is delegated whole to
    :func:`validate_submit_request` rather than checked against the service allowlist.
    """
    errors: list[str] = []
    action = str(command.get("action", ""))
    if action not in FLEET_ACTIONS:
        errors.append(f"action {action!r} is not one of {sorted(FLEET_ACTIONS)}")
        return errors

    if action == "submit":
        return validate_submit_request(command, repo_root=repo_root, phase_scopes=phase_scopes)

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


# ── The submit contract (D-14 extended, p1_submit_contract) ─────────────────


def _resolve_spec_path(spec_rel: str, repo_root: Path) -> tuple[Path | None, list[str]]:
    """Resolve a submit's ``spec`` field to a file INSIDE the repo, under an allowed dir.

    Returns ``(path, errors)`` — ``path`` is ``None`` whenever an error is appended, so a
    caller can just check truthiness rather than re-deriving the failure. Three ways to fail,
    all "outside the contract" in spirit: empty, escapes the repo root (``..`` traversal or an
    absolute path elsewhere), or lands outside the two declared spec directories.
    """
    errors: list[str] = []
    if not spec_rel:
        errors.append("submit: spec path is required")
        return None, errors

    candidate = (repo_root / spec_rel) if not Path(spec_rel).is_absolute() else Path(spec_rel)
    resolved = candidate.resolve()
    try:
        rel = resolved.relative_to(repo_root.resolve())
    except ValueError:
        errors.append(f"submit: spec path {spec_rel!r} escapes the repository root")
        return None, errors

    if not any(str(rel).startswith(f"{d}/") for d in SUBMIT_SPEC_DIRS):
        errors.append(
            f"submit: spec path {spec_rel!r} is outside the declared spec directories "
            f"{SUBMIT_SPEC_DIRS}"
        )
        return None, errors

    if not resolved.is_file():
        errors.append(f"submit: spec path {spec_rel!r} does not resolve to a file")
        return None, errors

    return resolved, errors


def _is_worktree_scoped_workdir(workdir: str) -> list[str]:
    """Check a submit's ``workdir`` against the worktree-root contract + host-service markers.

    A valid workdir is a path strictly UNDER ``FINOPS_WORKTREE_ROOT`` (the shared ``/tmp``
    namespace every worker/orchestrator already agrees on — see ``build_phase_request``'s own
    ``FINOPS_WORKTREE_ROOT`` default). "Strictly under" (not equal to the root) matters because
    the root itself is a shared directory, not one job's isolated worktree — mounting it would
    hand a cell every OTHER job's worktree too.
    """
    errors: list[str] = []
    if not workdir:
        errors.append("submit: workdir is required")
        return errors

    lowered = workdir.lower()
    if any(marker in lowered for marker in HOST_SERVICE_MARKERS):
        errors.append(
            f"submit: workdir {workdir!r} names a host service — outside the mount contract "
            f"(the story Redis / loopback / compose-hostname surface is never a worktree path)"
        )
        return errors

    worktree_root = Path(os.environ.get("FINOPS_WORKTREE_ROOT", "/tmp")).resolve()
    resolved = Path(workdir).resolve()
    if resolved == worktree_root or worktree_root not in resolved.parents:
        errors.append(
            f"submit: workdir {workdir!r} is not a path strictly under the worktree root "
            f"{worktree_root} (an allowed worktree path)"
        )
    return errors


def validate_submit_request(
    request: dict[str, Any],
    *,
    repo_root: Path | str | None = None,
    phase_scopes: dict[str, str] | None = None,
) -> list[str]:
    """Validate a ``submit`` request. Empty list = valid; the socket is reached only then.

    Eight checks (p1_submit_contract's SHAPE + p3_base_image_caching's image check, in order —
    later checks still run even after an earlier one fails, so a caller sees every problem in
    one pass rather than iterating):

    1. ``spec`` resolves to a file inside the repo's declared spec directories AND
       compile-validates (:func:`compile_spec` — the requires/produces gate).
    2. ``model`` is a member of :data:`MODEL_WHITELIST`.
    3. ``workdir`` is a path strictly under the worktree root, and never a host-service marker.
    4. ``goal`` is a non-blank string.
    5. every phase the spec declares resolves an AUTHORIZED scope, and that scope's derived
       mount set (:func:`build_phase_request`) passes the same mount-contract check
       :func:`validate_spawn` runs at its step 3 — a submit whose spec would eventually spawn
       an out-of-contract phase is refused NOW, before any container exists.
    6. ``network`` (when the request declares one) is exactly ``"fleet-net"``.
    7. no undeclared write flag: ``FINOPS_ACTUATION_ARMED`` is never allowed (G2), and
       ``FINOPS_KB_WRITE`` is allowed only when the spec has at least one ``implementation``-
       scope phase (the one scope whose ``write_flag`` is ``True``).
    8. ``image`` (when the request declares one) matches :data:`JOB_IMAGE_PATTERN` — a
       ``fleet/job-<name>`` per-job image built off the fleet/base cache root
       (p3_base_image_caching), never a bare override to fleet/base/orchestrator/supervisor or
       an arbitrary third-party image on the phase cells.

    ``request`` shape: ``{"spec", "goal", "model", "workdir", "network"?, "env"?, "image"?}`` —
    the exact fields ``fleet_manager submit`` LPUSHes, plus the three optional fields a caller
    may set to exercise checks 6/7/8 directly (the CLI never sets network/env; they default to
    the permitted value — ``image`` is CLI-settable via ``--image``, still validated here).
    """
    errors: list[str] = []
    repo_root = Path(repo_root) if repo_root is not None else _REPO_ROOT

    # Step 1 — spec path resolvable + compile-validates.
    spec_rel = str(request.get("spec", "") or "")
    spec_path, spec_errors = _resolve_spec_path(spec_rel, repo_root)
    errors.extend(spec_errors)
    spec = None
    if spec_path is not None:
        try:
            spec = load_spec(spec_path)
            compile_spec(spec)
        except (SpecError, OSError, ValueError) as exc:
            errors.append(f"submit: spec {spec_rel!r} does not compile-validate: {exc}")
            spec = None

    # Step 2 — model in the whitelist.
    model = str(request.get("model", "") or "")
    if model not in MODEL_WHITELIST:
        errors.append(
            f"submit: model {model!r} is not in the model whitelist {sorted(MODEL_WHITELIST)}"
        )

    # Step 3 — workdir is an allowed worktree path.
    workdir = str(request.get("workdir", "") or "")
    errors.extend(_is_worktree_scoped_workdir(workdir))

    # Step 4 — goal present.
    goal = str(request.get("goal", "") or "").strip()
    if not goal:
        errors.append("submit: goal is required")

    # Step 5 — mounts derived from the phase scopes stay inside the mount contract.
    if spec is not None:
        phases = [p for p in (spec.workflow.params.get("phases") or []) if isinstance(p, dict)]
        if not phases:
            errors.append(f"submit: spec {spec_rel!r} declares no phases")
        for phase in phases:
            phase_request = build_phase_request(
                phase,
                goal=goal or "submit",
                workdir=workdir or "/tmp",
                model=model,
                spec_name=spec.name,
                phase_scopes=phase_scopes,
            )
            for e in validate_spawn(phase_request, phase_scopes=phase_scopes):
                errors.append(f"submit: phase {phase.get('name')!r}: {e}")

    # Step 6 — network must be exactly fleet-net (only checked when the request declares one —
    # fleet_manager submit never sets it; a submit request MAY be built with one for testing).
    network = str(request.get("network", "fleet-net") or "fleet-net")
    if network != "fleet-net":
        errors.append(f"submit: network {network!r} != fleet-net")

    # Step 7 — no undeclared write flag at the request level.
    has_implementation_phase = spec is not None and any(
        phase_scope(p, phase_name=p.get("name")) == "implementation"
        for p in (spec.workflow.params.get("phases") or [])
        if isinstance(p, dict)
    )
    for k, v in (request.get("env", {}) or {}).items():
        if k not in WRITE_FLAG_ENVS or str(v) not in _TRUTHY:
            continue
        if k == "FINOPS_ACTUATION_ARMED":
            errors.append("submit: FINOPS_ACTUATION_ARMED is never set in the ladder (G2)")
        elif not has_implementation_phase:
            errors.append(
                "submit: FINOPS_KB_WRITE=1 is undeclared — the spec has no implementation-"
                "scope phase to authorize it"
            )

    # Step 8 — an optional per-job image must be a fleet/job-<name> build off the cache root.
    image = request.get("image")
    if image is not None:
        image = str(image)
        if not JOB_IMAGE_PATTERN.match(image):
            errors.append(
                f"submit: image {image!r} is not a fleet/job-<name> image "
                f"(the only per-job image namespace a submit may reference — never "
                f"fleet/base, fleet/orchestrator, fleet/supervisor, or a third-party image)"
            )

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
    now: float | None = None,
    require_lease: bool | None = None,
) -> dict[str, Any]:
    """Validate a spawn request, then (if valid) run the sibling container.

    The ordering is the load-bearing guarantee: :func:`validate_spawn` runs FIRST, and any error
    raises :class:`SpawnValidationError` before a single ``docker`` argv is built — a compromised
    phase can never reach the socket with a request it was not authorized for, and (since
    admission_leases p2) never with a request it has no lease for. On success returns
    ``{"ok", "argv", "returncode"?, "stdout"?, "stderr"?}`` (``dry_run`` builds the argv only).
    """
    errors = validate_spawn(
        request, phase_scopes=phase_scopes, now=now, require_lease=require_lease
    )
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


def _sanitize_namespace(namespace: str) -> str:
    """P0-3: map an arbitrary run/step/attempt identifier onto a safe relative path segment.

    The state namespace becomes a host path under :data:`STATE_ROOT` — it must be a single
    relative path (no ``..``, no absolute path, no leading slash) or a ``..`` escape would
    walk the state root. Separators that are legal in identifiers but hostile in paths are
    collapsed to ``/`` segments, and any remaining ``..``/empty segments are dropped.
    """
    parts = [
        p for p in str(namespace).replace("\\", "/").split("/")
        if p not in ("", ".", "..")
    ]
    if not parts:
        return "unnamed"
    return "/".join(parts)


def build_phase_request(
    phase_def: dict[str, Any],
    *,
    goal: str,
    workdir: str | Path,
    model: str,
    spec_name: str = "",
    phase_scopes: dict[str, str] | None = None,
    command: list[str] | None = None,
    admission: LeaseContext | None = None,
    state_namespace: str | None = None,
) -> dict[str, Any]:
    """Build a scope-driven spawn request for one workflow phase (the campaign-wrapper mechanism).

    Resolves the phase's authorized scope (declared ``scope:`` → authorization table), then
    assembles the four-mount contract (with the scope's results mode) + the scope's network + the
    canonical cell env (the write flag only when the scope authorizes it). The result feeds
    :func:`spawn_sibling` — which re-validates it before the socket call. ``command`` is the
    sibling container's entrypoint (defaults to the phase-runner; see ``phase_runner.py``).

    P0-3 (control-plane stabilization): every sibling carries a UNIQUE writable state
    namespace — ``<STATE_ROOT>/<state_namespace>`` mounted at ``/state`` (rw) with
    ``XDG_DATA_HOME``/``XDG_CONFIG_HOME``/``XDG_CACHE_HOME`` pointed into it — plus the
    credential FILE mount (``/auth/opencode_auth.json``, ro). ``state_namespace`` defaults to
    ``<spec_name>/<phase>``; the orchestrator may pass a finer per-attempt value (run/step/
    attempt) to isolate retries. A host namespace is NEVER shared between two cells, so two
    concurrent OpenCode sessions can never read or write each other's state (session IDs,
    SQLite/WAL, compaction).

    ``admission`` (admission_leases p2) is the phase's granted lease context, obtained by the
    orchestrator from ``control.admission`` before it calls this. When supplied it lands in the
    request twice, on purpose:

    * as the top-level :data:`LEASE_FIELDS` block, which is what validation step 6 checks — the
      *orchestrator side* of the contract; and
    * as the ``FINOPS_ADMISSION_*`` env vars in the cell's environment, which is what the
      *cell side* reads (its ``adapters.backends.run_agentic`` bypass guard), since a container
      cannot inherit a ContextVar.

    Omitting it produces a request with no lease block: valid while the gate is disarmed,
    refused at step 6 once it is armed. The wrapper never mints an admission itself — reserving
    against Redis is the controller's job, and a validator that could also grant would be a
    validator that could grant itself a pass.
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

    # P0-3: the per-attempt state namespace + the credential FILE mount. The host namespace is
    # minted here (mkdir -p, best-effort — a mkdir failure surfaces as a spawn error, never a
    # silent fallback to a shared directory) and is unique to this request: <spec>/<phase>
    # by default, or a finer run/step/attempt value the orchestrator passes.
    namespace = state_namespace or f"{spec_name or 'spec'}/{phase_def.get('name', 'phase')}"
    state_src = Path(STATE_ROOT) / _sanitize_namespace(namespace)
    state_src.mkdir(parents=True, exist_ok=True)
    mounts.append({"source": str(state_src), "target": STATE_TARGET, "mode": "rw"})
    mounts.append({"source": f"{auth_home}/.local/share/opencode/auth.json",
                   "target": AUTH_CRED_FILE, "mode": "ro"})

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
        #: P0-3: the CLI's writable state is redirected into the per-attempt namespace. With
        #: XDG_DATA_HOME=/state/data the session DB, SQLite/WAL, and compaction all land under
        #: this sibling's OWN host directory — never in a pool-shared one.
        "XDG_DATA_HOME": f"{STATE_TARGET}/data",
        "XDG_CONFIG_HOME": f"{STATE_TARGET}/config",
        "XDG_CACHE_HOME": f"{STATE_TARGET}/cache",
        "FINOPS_OPENCODE_STATE_DIR": f"{STATE_TARGET}/data",
    }
    if cfg.get("write_flag", False):
        # The implementation scope MAY emit (P1-P11) — the write flag is authorized; the
        # compose-level "P1-P10 units only" placement is the finer gate, not this wrapper.
        env["FINOPS_KB_WRITE"] = "1"

    if admission is not None:
        # The cell reads its admission from the environment (no ContextVar crosses a container
        # boundary); the orchestrator's validator reads it from the request's lease block.
        env.update(admission.to_env())

    request: dict[str, Any] = {
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
    if admission is not None:
        request.update(admission.to_request_fields())
    return request


def build_verifier_request(
    phase_def: dict[str, Any],
    *,
    goal: str,
    workdir: str | Path,
    model: str,
    spec_name: str = "",
    command: list[str] | None = None,
    admission: LeaseContext | None = None,
) -> dict[str, Any]:
    """Build the READ-ONLY verifier spawn request for a ``kind: test`` phase (w1, 2026-09-02).

    The reference containerized path's verifier cell (the DockerVerifierExecutor) is NOT an
    agent cell: it runs a declared independent verification against the candidate and makes
    NO model call. It therefore carries NO credentials and NO writable CLI state — the two
    writable/secret surfaces the P0-3 per-attempt state namespace exists to isolate from agent
    cells are simply ABSENT here, and the write flags an emitting phase may carry are dropped.

    The request is the phase's normal spawn request (same scope/network/env of record, so the
    isolation contract's scope model still governs it) MINUS the verifier-forbidden surface:

    * the per-attempt CLI-state namespace (``/state`` + the ``XDG_*`` /
      ``FINOPS_OPENCODE_STATE_DIR`` redirect env) — absent (a verifier runs no CLI session);
    * the credential mounts — the D-2 auth dirs and the ``/auth/opencode_auth.json`` credential
      FILE mount (no model call, no credential needed);
    * the results mount — the verifier writes nothing to ``experiments/results`` (a ``kind:
      test`` phase produces only its verdict, which the PARENT aggregates); and
    * any write-flag env (``FINOPS_KB_WRITE`` / ``FINOPS_ACTUATION_ARMED``) the phase's scope
      would otherwise authorize — a verifier never emits.

    What REMAINS is the candidate surface the suite runs against — and it is mounted
    READ-ONLY in its entirety (g1_verifier_mount, engine_gaps_followups F1): the worktree
    namespace (``/tmp`` — the candidate workdir), the repo (``/repo``), and both git dirs
    (``/repo/.git`` + the host-path ``.git`` alias). A verifier needs the candidate's TREE
    to run the suite against, never the ability to change it — so the writable candidate
    surfaces an agent phase mounts (``rw`` because it COMMITS its work) are flipped to ``ro``
    HERE, at the mount contract, never left to the child's ``--no-commit``. The request is
    stamped with :data:`VERIFIER_REQUEST_MARKER` so :func:`validate_spawn` enforces
    read-only-for-candidate at validation time (a verifier request that would mount the
    candidate ``rw`` is refused before the socket call).

    ``admission`` mirrors ``build_phase_request``'s contract: supplied when a lease context is
    in force; a verifier request deliberately has none when absent, because the verifier spends
    no model dollars (a budget lease reserves model spend — the verifier has none to reserve).
    """
    request = build_phase_request(
        phase_def,
        goal=goal,
        workdir=workdir,
        model=model,
        spec_name=spec_name,
        command=command,
        admission=admission,
    )
    forbidden_mount_targets = {STATE_TARGET, AUTH_CRED_FILE, *AUTH_DIRS}
    request["mounts"] = [
        m for m in (request.get("mounts") or [])
        if str((m or {}).get("target", "")) not in forbidden_mount_targets
    ]
    # The verifier writes nothing to the results mount — drop it (its mode is scope-derived
    # and read-only-for-a-verifier would otherwise fail the scope's own mode check).
    request["mounts"] = [
        m for m in request["mounts"]
        if not str((m or {}).get("target", "")).startswith("/app/experiments/results")
    ]
    # F1 (g1_verifier_mount): after the forbidden-surface drops the ONLY mounts left ARE the
    # candidate surface (worktree /tmp, repo /repo + /repo/.git, the host-path repo-alias +
    # its .git) — flip every one of them to READ-ONLY. The verifier container cannot write its
    # candidate through any mount; if a writable scratch is ever genuinely needed it is a
    # SEPARATE, empty, non-candidate volume (never the worktree, never .git), and validation
    # refuses any non-candidate mount on a verifier request regardless. Marking the request
    # lets validation REFUSE a request that would mount the candidate rw.
    for m in request["mounts"]:
        m["mode"] = "ro"
    request[VERIFIER_REQUEST_MARKER] = True
    env = {k: v for k, v in (request.get("env", {}) or {}).items() if k not in STATE_ENV_KEYS}
    env.pop("FINOPS_OPENCODE_STATE_DIR", None)
    for flag in WRITE_FLAG_ENVS:
        env.pop(flag, None)
    request["env"] = env
    return request


def build_submit_argv(
    command: dict[str, Any],
    *,
    compose: str = "docker-compose",
    compose_file: str | None = None,
) -> list[str]:
    """Build the ``docker compose run`` argv for a validated submit (called only AFTER
    :func:`validate_submit_request` returns no errors).

    This is the reference containerized execution path (see the run-workflow skill):
    ``docker compose -f infrastructure/docker-compose.ladder.yml run --rm workflow-runner
    python3 scripts/run_workflow.py --spec ... --goal ... --model ... --workdir ...
    --orchestrator``. ``--orchestrator`` switches ``run_workflow.py`` into sibling-spawn mode,
    where EVERY phase re-runs through :func:`validate_spawn` before its own container exists —
    this dispatch only proves the whole spec is launchable, not that any individual phase gets
    a free pass later.

    ``command["image"]`` (already checked against :data:`JOB_IMAGE_PATTERN` by
    :func:`validate_submit_request`'s step 8), when present, becomes ``--cell-image`` — it
    changes which image the orchestrator spawns for each PHASE cell (``run_workflow.py``'s
    ``_run_orchestrator`` threads it to :func:`spawn_sibling`), never the ``workflow-runner``
    container itself, which always runs ``fleet/orchestrator`` (the one socket-holder needs the
    docker CLI + this wrapper — a job image built off fleet/base does not carry either).
    """
    compose_file = compose_file or str(_REPO_ROOT / "infrastructure" / "docker-compose.ladder.yml")
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


def dispatch_submit(
    command: dict[str, Any],
    *,
    repo_root: Path | str | None = None,
    phase_scopes: dict[str, str] | None = None,
    compose: str = "docker-compose",
    compose_file: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Validate a submit command, then (if valid) run ``docker compose run`` for it.

    Mirrors :func:`spawn_sibling`'s ordering guarantee: :func:`validate_submit_request` runs
    FIRST, and any error raises :class:`SpawnValidationError` before :func:`build_submit_argv`
    is even called — an invalid submit (a bad scope, an unlisted model, a host-service workdir,
    an undeclared write flag) never reaches the socket. ``consume_fleet_commands`` inlines this
    same ordering (via ``validate_fleet_command`` + ``build_submit_argv``) for the live BRPOP
    loop; this function exists so the ordering itself is unit-testable without Redis.
    """
    errors = validate_submit_request(command, repo_root=repo_root, phase_scopes=phase_scopes)
    if errors:
        raise SpawnValidationError(errors)

    argv = build_submit_argv(command, compose=compose, compose_file=compose_file)
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


def _spec_name_for_ledger(spec_rel: str) -> str:
    """The spec's declared ``name:`` field, for locating its ledger directory.

    A submit command only carries the spec's repo-relative PATH; the ledger a run writes is
    keyed by the spec's declared name (``run_workflow.py``'s ``main()``: ``experiments/results/
    workflows/<spec.name>/``), which need not match the file's stem. Reloading is cheap and, for
    a command that already passed :func:`validate_submit_request` (which itself calls
    :func:`load_spec`), should not fail — but this is purely an observability lookup, so any
    failure falls back to the file stem rather than raising and losing the board update.
    """
    try:
        path, errors = _resolve_spec_path(spec_rel, _REPO_ROOT)
        if path is not None and not errors:
            return load_spec(path).name
    except (SpecError, OSError, ValueError):
        pass
    return Path(spec_rel).stem


def _latest_ledger(spec_name: str) -> str | None:
    """The most recently written ledger for a spec name — a submitted job's board pointer.

    An ``--orchestrator`` run has no single top-level ledger of its own: each phase spawns as
    its own sibling running ``run_workflow.py --only-phase <name>``, and THAT single-phase run
    is what writes the timestamped ledger JSON under ``experiments/results/workflows/
    <spec_name>/`` (``run_workflow.py``'s own ``main()``). The lexicographic
    ``YYYYMMDDTHHMMSSZ.json`` naming sorts chronologically, so the last file is the job's most
    recent phase result — the pointer :func:`fleet_manager.record_job_status` attaches to a
    completed/failed submit record.
    """
    ledger_dir = _REPO_ROOT / "experiments" / "results" / "workflows" / spec_name
    if not ledger_dir.is_dir():
        return None
    files = sorted(ledger_dir.glob("*.json"))
    return str(files[-1]) if files else None


def consume_fleet_commands(
    *,
    client: Any | None = None,
    compose_file: str | None = None,
    dry_run: bool = False,
    once: bool = False,
) -> None:
    """BRPOP ``fleet:commands`` and dispatch validated scale/drain/restart/submit commands (D-14).

    Each popped command is validated against :func:`validate_fleet_command` BEFORE any
    ``docker compose`` call; an invalid command is logged and dropped (never acted on). This is
    the orchestrator's "hands" — the supervisor LPUSHes, this consumer validates + executes.

    ``submit`` is dispatched the same way as scale/drain/restart (validate, then build argv,
    then run) but through :func:`build_submit_argv` instead of the service-shaped argv the
    other three actions use — and, per the isolation-over-coordination design, dispatching one
    submit never blocks or refuses another: there is no lock here, only per-request validation.

    A submit's ``job_id`` additionally drives the board lifecycle (p2_launch_handler,
    :func:`fleet_manager.record_job_status`): a refusal here (never reaching the socket) writes
    "failed" straight away; otherwise "running" is recorded just before the ``docker compose``
    call, and the observed exit code resolves it to "completed" or "failed" — a nonzero exit (or
    a pre-socket refusal) is ALSO filed onto the ``fleet_jobs`` dead-letter list
    (``scripts/fleet/dlq.py``), reusing the existing per-queue DLQ surface rather than adding a
    new one. ``client`` is an injectable redis connection (tests pass a fake; the real consumer
    loop leaves it ``None`` and connects via :func:`_connect_redis`) — the same "the caller may
    own the connection" shape ``fleet_manager.py``'s own functions already use.
    """
    # Sibling script modules (scripts/fleet/ is a dir, not a package — no __init__.py, so a
    # bare "import dlq" only resolves once this dir is on sys.path; this module may itself be
    # reached as the namespace package `scripts.fleet.spawn_wrapper`, which does NOT add this
    # dir to sys.path, so it is added here rather than relying on some other caller having done
    # it first). Imported lazily so the pure validators above this function never pull in
    # `redis` (fleet_manager imports it at module scope) just to be importable.
    _fleet_dir = str(Path(__file__).resolve().parent)
    if _fleet_dir not in sys.path:
        sys.path.insert(0, _fleet_dir)
    import dlq  # noqa: PLC0415
    import fleet_manager  # noqa: PLC0415

    client = client if client is not None else _connect_redis()
    compose_file = compose_file or str(_REPO_ROOT / "infrastructure" / "docker-compose.ladder.yml")
    compose = os.environ.get("DOCKER_COMPOSE", "docker-compose")

    print(f"[spawn-wrapper] consuming {COMMANDS_KEY} (compose {compose_file})", flush=True)
    while True:
        try:
            result = client.brpop(COMMANDS_KEY, timeout=10)
        except (TimeoutError, ConnectionError, OSError) as exc:
            # A transient Redis socket timeout (the client's socket timeout can trip before
            # the BRPOP's own 10s) must not kill the orchestrator's hands — retry the read.
            # The 2026-09-01 crash: an unhandled socket TimeoutError exited the consume loop
            # mid-fleet, leaving a queued submit marked "launching" with no consumer.
            print(f"[spawn-wrapper] redis read interrupted ({type(exc).__name__}); retrying", flush=True)
            if once:
                return
            continue
        if result is None:
            if once:
                return
            continue
        _key, raw = result
        try:
            command = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[spawn-wrapper] dropping malformed command: {raw!r}", flush=True)
            if once:
                return
            continue
        errors = validate_fleet_command(command)
        if errors:
            print(f"[spawn-wrapper] REFUSED {command}: {errors}", flush=True)
            if command.get("action") == "submit" and command.get("job_id"):
                reason = "; ".join(errors)
                fleet_manager.record_job_status(client, command["job_id"], "failed", error=reason)
                dlq.record_dead(client, "fleet_jobs", command, reason)
            if once:
                return
            continue
        action = command["action"]
        service = command.get("service")
        if action == "submit":
            argv = build_submit_argv(command, compose=compose, compose_file=compose_file)
        elif action == "scale":
            argv = [compose, "-f", compose_file, "up", "-d", "--scale",
                    f"{service}={command['count']}", service]
        elif action == "drain":
            argv = [compose, "-f", compose_file, "stop", service]
        else:  # restart
            argv = [compose, "-f", compose_file, "restart", service]
        print(f"[spawn-wrapper] DISPATCH {action} {service or command.get('job_id')}: {argv}",
              flush=True)
        job_id = command.get("job_id") if action == "submit" else None
        if job_id:
            fleet_manager.record_job_status(client, job_id, "running")
        if not dry_run:
            proc = subprocess.run(argv, check=False)
            if job_id:
                ledger = _latest_ledger(_spec_name_for_ledger(str(command.get("spec", ""))))
                if proc.returncode == 0:
                    fleet_manager.record_job_status(
                        client, job_id, "completed", returncode=proc.returncode, ledger=ledger,
                    )
                else:
                    reason = f"compose run exited {proc.returncode}"
                    fleet_manager.record_job_status(
                        client, job_id, "failed", returncode=proc.returncode, ledger=ledger,
                        error=reason,
                    )
                    dlq.record_dead(client, "fleet_jobs", command, reason)
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
