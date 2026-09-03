#!/usr/bin/env python3
"""The sibling-spawn wrapper — the orchestrator's ONE escalation, validated (proposal §2/D-14, §5/D-16).

The wrapper is the ORCHESTRATOR side of the launch boundary: a spawn request is validated
against the per-step scope model (the closed five-scope vocabulary + the phase→scope
authorization) and the mount contract (the four + the D-2 auth set) **before** anything is
launched. A phase requesting an undeclared scope, an unauthorized scope, a mount outside the
contract, an undeclared network, or an undeclared write flag fails here — never at the socket.

**b3_launch_broker + fb2_broker_hostside: the socket left this module, and so did the broker
import.** The wrapper no longer invokes docker — and after fb2 it no longer imports the broker
module and calls it in-process either. It builds the TYPED launch request (``image_digest`` /
``network`` / ``mount_profile`` / ``state_namespace`` / ``command`` / ``timeout_seconds`` +
the scope-model context), validates it, and emits it over the IPC seam to the launch broker —
a genuinely host-side systemd user unit (``infrastructure/
agentic-dynamics-launch-broker.service``) that owns the Docker socket and is the ONLY Docker
API caller (its two documented exceptions: the game board's read-only ``docker ps``,
``scripts/system_snapshot.py`` — fb3 f4 — and the archived one-time sonar-scanner docker run,
``scripts/archive/backfill_sonar.py`` — ws3_stragglers, frozen, never re-run; both are reads,
never a launch). The wrapper speaks the seam through ``broker_client.BrokerClient`` (a unix socket,
one framed request per connection); the broker re-validates the request (both sides run the
same shared checks: :func:`broker_contract.validate_launch_request` + :func:`validate_spawn`)
and performs the docker call itself. ``docker-compose.ladder.yml`` mounts no docker socket into
any container; the docker socket lives ONLY where the broker runs (host). The fleet:commands
dispatch (scale/drain/restart/submit) delegates its ``docker compose`` calls over the SAME
seam (:func:`_broker_client` → the broker's ``fleet-command`` verb). NO in-container code
calls docker, and a spawn path that cannot reach the host broker fails loudly — never silently.

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

    spawn_sibling          — validate_spawn THEN emit the typed launch request to the broker
                             (which builds + runs the ``docker run``).
    build_phase_request    — build a scope-driven typed launch request from a workflow phase
                             (the campaign-wrapper→sibling-cell mechanism, D-16); the request's
                             mounts are the broker's profile expansion (shared).
    consume_fleet_commands — BRPOP ``fleet:commands`` (db1 / 6380) and dispatch validated
                             resize/drain/restart/submit commands THROUGH the broker,
                             wiring a submitted job's board record through
                             launching -> running -> completed/failed (+ the ``fleet_jobs``
                             DLQ on refusal or a nonzero exit, p2_launch_handler).

This module is a script (``scripts/fleet/``), not a package plane. Its package imports are the
scope model from the experiment plane (tier 1 — ``agentic_dynamics.experiment.experiment_spec``),
which is the source of truth for the vocabulary + authorization + configs, the tier-0 admission
vocabulary (``agentic_dynamics.core.admission_context``) for step 6's pure lease-block check, the
pure shared contract (``broker_contract`` — tier-0/1 only, the profiles/expansion/validation this
module validates against), and the seam client (``broker_client`` — stdlib-only). It never
imports ``control``/``runtime``/``adapters`` and NEVER imports the broker module
(``launch_broker``) — the admission *decision* stays in ``control.admission``; the docker call
stays in the host-side broker's process, reached only over the seam. The structural validators
above remain pure and stdlib-only (validation never requires ``redis``); only the
fleet:commands BRPOP consumer and the seam client touch a socket, and the seam client
(``broker_client``) is itself stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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

# scripts/fleet/ is a dir, not a package — add it beside src/ so the SHARED pure contract
# (broker_contract — the profiles/expansion/validation this module validates against) and the
# seam client (broker_client — the module this module reaches the HOST-side broker through)
# import as top-level modules.
#
# fb2_broker_hostside: this module NO LONGER imports the broker (launch_broker) at all. The
# broker's docker-executing code is not importable from the orchestrator's spawn path; the
# spawn path talks to the host-side broker over the unix-socket seam (broker_client).
_FLEET_DIR = Path(__file__).resolve().parent
if str(_FLEET_DIR) not in sys.path:
    sys.path.insert(0, str(_FLEET_DIR))

from broker_client import BrokerClient, BrokerError  # noqa: E402
from broker_contract import (  # noqa: E402
    AUTH_CRED_FILE,
    LAUNCH_NETWORK,
    MOUNT_PROFILES,
    REPO_TARGET,
    RESULTS_TARGET,
    STATE_TARGET,
    WORKTREE_TARGET,
    config_view,
    mounts_for_profile,
    sanitize_namespace,
    validate_launch_request,
)

from agentic_dynamics.core.admission_context import (  # noqa: E402
    LEASE_REQUEST_FIELDS,
    LeaseContext,
    admission_required,
    validate_lease_fields,
)
from agentic_dynamics.core.paths import (  # noqa: E402
    PathConfig,
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
#
# b1_path_config (fleet_launch_boundary Wave 2): the CONTAINER targets below are fixed
# constants (the isolation contract — the worktree namespace, results, the repo + gitdir
# overlays, the per-attempt state namespace, the credential FILE). The HOST paths that back
# them (the repo at its host path, the git dir, the worktree root, the results dir, the auth
# home + its D-2 auth dirs, the state root) are ALL derived from ONE :class:`PathConfig`
# (``agentic_dynamics.core.paths``) — never from a host-specific literal. The host-specific
# repo-alias contract (historically a hard-coded host-user repo pair in this map) is now the
# config's ``repo_root`` / ``git_dir``: the request builders and the validator derive the SAME
# values from the SAME config, so a spawn request can never name a repo alias the validator
# does not also derive.

#: The default PathConfig the wrapper's request-builders and validators derive from when the
#: caller does not pass one — the environment at call time, validated once (a missing repo root
#: is refused). "Every consumer takes it as a parameter": a caller that cares about a specific
#: config (tests, the composition root) passes it explicitly; these module functions accept it
#: and fall back to this derivation only for backward-compatible callers that predate it.
def default_path_config() -> PathConfig:
    """The wrapper's :class:`PathConfig`, derived from the environment at call time.

    Reads the existing ``FINOPS_REPO_DIR`` / ``FINOPS_WORKTREE_ROOT`` /
    ``FINOPS_OPENCODE_STATE_ROOT`` / ``AUTH_HOME`` env contract (defaults are the repo's own
    paths relative to the package root) and validates the config once — a missing repo root is
    a refusal, never a silent fallback. Callers that need a specific config (tests, an
    operator overriding a single root) pass a ``PathConfig`` explicitly.
    """
    return PathConfig.from_env()


#: The D-2 auth set (proposal §0/D-2) — the four read-only auth mounts, derived from the
#: default config's ``auth_home`` (``PathConfig.auth_dirs``): the container auth home is the
#: host user's home (``HOME`` / ``AUTH_HOME`` in the compose), so the claude symlink chain
#: (``~/.local/bin/claude`` → ``~/.local/share/claude/versions/<v>``) resolves unchanged.
#: A snapshot for importers of this module's historical name; the request builders and the
#: validator use the config's own :meth:`PathConfig.auth_dirs`, so the two can never disagree
#: about which auth dirs a given config mounts.
#:
#: NOTE (P0-3, control-plane stabilization): ``~/.local/share/opencode`` is deliberately NOT
#: here. The sibling's CLI state is the per-attempt :data:`STATE_TARGET` namespace (rw, mounted
#: by :func:`build_phase_request`), and its credential is the :data:`AUTH_CRED_FILE` file mount
#: (ro) — the host's LIVE opencode state (opencode.db, sessions, compaction) never enters a
#: cell in any mode, and no two cells ever share a writable CLI-state directory.
AUTH_DIRS: frozenset[str] = frozenset(
    str(d) for d in PathConfig.from_env(require_existing=False).auth_dirs
)

#: P0-3: the credential FILE mount (ro) + the per-attempt CLI-state target (rw). Both are now
#: defined ONCE in the pure shared contract (``broker_contract.AUTH_CRED_FILE`` /
#: ``broker_contract.STATE_TARGET`` — imported above and re-exported here for this module's
#: historical import surface): the broker's profile expansion mounts them, so a credential/state
#: constant that drifted between the wrapper and the broker would be a mount the wrapper
#: validated but the broker did not mount. One definition — the contract's.
STATE_ROOT = str(PathConfig.from_env(require_existing=False).state_root)

#: The XDG redirect vars the state namespace sets, so the CLI's writable state lands in the
#: per-attempt namespace instead of the image's default ``~/.local/share``.
STATE_ENV_KEYS: tuple[str, ...] = ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME")

#: The fixed CONTAINER mount targets (proposal §3). ``mode`` is the CONTRACT's mode;
#: ``results`` is ``None`` because the scope narrows it (ro vs rw). These targets are the same
#: in every deployment — the isolation constant. A mount target outside this map (plus the
#: PathConfig-derived repo-alias/.git pair and the D-2 auth set, assembled by
#: :func:`contract_targets`) is outside the contract — rejected at step 3.
FIXED_CONTRACT_TARGETS: dict[str, tuple[str, str | None]] = {
    "/tmp": ("worktree", "rw"),
    "/app/experiments/results": ("results", None),
    "/repo": ("repo", "ro"),
    #: The gitdir overlay (D-16 fix, 2026-08-31): a sibling cell must COMMIT its phase work
    #: into the shared worktree, which writes the worktree registration + objects + refs under
    #: /repo/.git — read-only there breaks every phase commit. Mirrors the results-overlay
    #: pattern: the repo working tree stays ro; only .git is overlaid rw.
    "/repo/.git": ("repo-git", "rw"),
    #: P0-3: the per-attempt CLI-state namespace (rw). The ONE writable state a cell gets —
    #: mounted as a unique per-run/step/attempt host dir, never a shared pool directory.
    STATE_TARGET: ("state", "rw"),
}

#: The repo at its HOST path (D-16 fix, 2026-08-31): worktrees in the shared worktree namespace
#: carry a ``gitdir:`` pointer to the repo's HOST path (``<repo_root>/.git/...``). Without this
#: mount the pointer does not resolve inside a cell, git treats the worktree as foreign, and the
#: runner rewrites the pointer to /repo/.git — wedging the worktree for the host. Mounting the
#: repo at the SAME path in the container makes one pointer valid in both views. The host path
#: is the config's ``repo_root`` / ``git_dir`` — derived, never a literal (b1_path_config).
#:
#: This shared-worktree surface (the D-16 alias + the ``/repo/.git`` overlay + the shared
#: ``/tmp`` namespace in :data:`FIXED_CONTRACT_TARGETS`) belongs to the PRE-clone shared-worktree
#: contract ONLY. fb1_clone_mounted's clone-world contract (:func:`clone_contract_targets`)
#: excludes every one of them: a cell that mounts its per-run clone needs no worktree gitdir
#: pointer and no shared ``.git`` — the clone has its own.


def contract_targets(path_config: PathConfig) -> dict[str, tuple[str, str | None]]:
    """The full mount contract for ``path_config`` — fixed targets + derived host-path targets.

    The fixed CONTAINER targets (:data:`FIXED_CONTRACT_TARGETS`) are joined with the
    config-derived host-path targets: the repo at its host path (``repo-alias`` ro), its git
    dir (``repo-alias-git`` rw — the D-16 overlay), the D-2 auth dirs (``auth`` ro, from
    ``path_config.auth_dirs``), and the credential FILE (``auth-file`` ro). Both the request
    builders and :func:`validate_spawn` assemble the contract from the SAME config, so a
    request can never name a mount the validator does not also derive.
    """
    targets: dict[str, tuple[str, str | None]] = dict(FIXED_CONTRACT_TARGETS)
    targets[str(path_config.repo_root)] = ("repo-alias", "ro")
    targets[str(path_config.git_dir)] = ("repo-alias-git", "rw")
    targets.update({str(d): ("auth", "ro") for d in path_config.auth_dirs})
    targets[AUTH_CRED_FILE] = ("auth-file", "ro")
    return targets


#: The mount CATEGORY of the clone-sourced repo mount (fb1_clone_mounted). A clone-world
#: request mounts its per-run clone at ``/repo`` — this category distinguishes that mount from
#: the shared-worktree shape's ``repo`` (working tree of the SHARED repo) + ``repo-git``
#: (overlay of the SHARED ``.git``), so validation can require a clone-world cell's repo to be
#: its own clone and refuse the shared surfaces outright.
REPO_CLONE_CATEGORY = "repo-clone"


def clone_contract_targets(path_config: PathConfig) -> dict[str, tuple[str, str | None]]:
    """The CLONE-world mount contract for ``path_config`` (fb1_clone_mounted).

    When a spawn request names a run clone (``run_clone`` = ``runs_root/<run-id>/repo``), the
    cell's world IS that clone — so the shared-host surfaces of the shared-worktree contract
    are deliberately NOT part of this contract: no worktree namespace (``/tmp``), no shared
    ``/repo/.git`` overlay, no D-16 host-path repo/``.git`` aliases. Two concurrent cells must
    never share git metadata through ANY path, and the shared surfaces are the paths that
    would reintroduce sharing.

    The clone-world contract is the per-cell surface only: ``/repo`` (the run's clone — mode
    ro|rw per the profile, validated separately), ``results`` (mode = the scope's
    ``results_mode``), the per-attempt ``state`` namespace (rw), the D-2 ``auth`` dirs (ro) and
    the credential ``auth-file`` (ro). ``validate_spawn`` derives THIS table (never the
    shared-worktree :func:`contract_targets`) when the request under validation carries a run
    clone, so a request that would mount the shared worktree or shared ``.git`` fails step 3.
    """
    targets: dict[str, tuple[str, str | None]] = {
        REPO_TARGET: (REPO_CLONE_CATEGORY, None),
        RESULTS_TARGET: ("results", None),
        STATE_TARGET: ("state", "rw"),
        AUTH_CRED_FILE: ("auth-file", "ro"),
    }
    targets.update({str(d): ("auth", "ro") for d in path_config.auth_dirs})
    return targets


#: The default config's full contract — the historical module-level map, kept as a snapshot for
#: importers that name it directly. Runtime validation uses :func:`contract_targets` on the
#: caller's own config (default: :func:`default_path_config`), never this import-time snapshot,
#: so a monkeypatched env is always honored.
CONTRACT_TARGETS: dict[str, tuple[str, str | None]] = contract_targets(
    PathConfig.from_env(require_existing=False)
)

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
#: validation refuses them if present. In the clone world (fb1_clone_mounted) the candidate
#: surface is the run's own clone (``repo-clone``), which is a member of the same read-only set.
VERIFIER_READONLY_CATEGORIES: frozenset[str] = frozenset(
    {"worktree", "repo", "repo-git", "repo-alias", "repo-alias-git", "repo-clone"}
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
#: attacker-supplied third-party image on the broker's phase-cell launches. The
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


def _mounts_shared_surface(mount: Any, path_config: PathConfig) -> bool:
    """True when a CLONE-world mount would expose the SHARED worktree or the SHARED ``.git``.

    fb1_clone_mounted — a clone-world cell's repo is its per-run clone, so any mount that
    reaches the shared-host surfaces is a sharing hazard and is refused. Checked by TARGET
    (the shared ``/tmp`` worktree namespace, the shared ``/repo/.git`` overlay, and the D-16
    host-path repo + ``.git`` aliases) and by SOURCE (the shared worktrees-root namespace root
    itself, or the shared git dir — ``git_dir`` itself or anything under it). Sources UNDER the
    worktrees root (e.g. the per-attempt state namespace, which lives at
    ``worktrees_root/opencode_state``) are NOT shared surfaces — only the namespace ROOT
    bind that would hand a cell every worktree is.
    """
    target = str((mount or {}).get("target", ""))
    source = str((mount or {}).get("source", "") or "")
    if target in (
        WORKTREE_TARGET,
        f"{REPO_TARGET}/.git",
        str(path_config.repo_root),
        str(path_config.git_dir),
    ):
        return True
    if source:
        src = Path(source).resolve()
        worktrees_root = path_config.worktrees_root.resolve()
        git_dir = path_config.git_dir.resolve()
        if src in (worktrees_root, git_dir) or git_dir in src.parents:
            return True
    return False


# ── The five-check validation (§5, D-16) ─────────────────────────────────────


def validate_spawn(
    request: dict[str, Any],
    *,
    phase_scopes: dict[str, str] | None = None,
    now: float | None = None,
    require_lease: bool | None = None,
    path_config: PathConfig | None = None,
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

    ``path_config`` (b1_path_config) is the :class:`PathConfig` step 3 derives the mount
    contract from — the repo-alias/.git pair and the D-2 auth dirs are config-derived, so a
    request built against one config validates against the SAME config. ``None`` (the default)
    derives it from the environment at call time (:func:`default_path_config`).
    """
    errors: list[str] = []
    path_config = path_config or default_path_config()
    contract = contract_targets(path_config)
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

    # Step 3 — every mount's target ∈ the contract, and its mode matches the scope/contract.
    # The effective contract depends on whether the request names a run clone (fb1_clone_mounted
    # — the clone is the cell's world):
    #   * NO run_clone — the shared-worktree contract (:func:`contract_targets`: the four + D-2
    #     + the D-16 host-path repo/.git alias), unchanged from before fb1.
    #   * run_clone present — the CLONE-world contract (:func:`clone_contract_targets`): the
    #     cell's repo IS its per-run clone (runs_root/<run-id>/repo), so the shared worktree
    #     mount and the shared .git overlays/aliases are OUT of contract, and a request that
    #     would mount them (by target or by source) is refused HERE, before the socket call.
    # A VERIFIER request (the DockerVerifierExecutor's read-only cell — stamped by
    # build_verifier_request) is a DIFFERENT contract on top: it may carry ONLY the read-only
    # candidate surface (worktree/repo/repo-git/repo-alias/repo-alias-git/repo-clone, all ro),
    # never the results/state/auth mounts of an agent cell. Read-only-for-candidate is enforced
    # HERE, at validation time — a verifier request that would mount its candidate rw is
    # refused before the socket call, never left to the child's --no-commit.
    is_verifier = bool(request.get(VERIFIER_REQUEST_MARKER))
    clone_ref = request.get("run_clone")
    clone_world = bool(clone_ref)
    mounts = request.get("mounts", []) or []
    if clone_world:
        if not path_config.is_run_clone_dir(str(clone_ref)):
            errors.append(
                f"step 3: run_clone {clone_ref!r} is not a runs_root/<run-id>/repo clone path "
                f"— a clone-world request must name the run's private clone"
            )
        contract = clone_contract_targets(path_config)
    for m in mounts:
        target = str((m or {}).get("target", ""))
        mode = str((m or {}).get("mode", ""))
        source = str((m or {}).get("source", "") or "")
        if clone_world and _mounts_shared_surface(m, path_config):
            errors.append(
                f"step 3: mount target {target!r} (source {source!r}) is the SHARED "
                f"worktree/.git surface — a clone-world cell mounts its own run clone "
                f"(runs_root/<run-id>/repo), never the shared worktree or the shared .git"
            )
            continue
        if target not in contract:
            if clone_world:
                errors.append(
                    f"step 3: mount target {target!r} is outside the clone-world contract "
                    f"(the shared worktree/.git surface is not mountable by a run-clone cell)"
                )
            else:
                errors.append(
                    f"step 3: mount target {target!r} is outside the four-mount contract + the "
                    f"D-2 auth set"
                )
            continue
        category, contract_mode = contract[target]
        if clone_world and target == REPO_TARGET and source and source != str(clone_ref):
            errors.append(
                f"step 3: the /repo mount sources {source!r}, but a clone-world cell's repo "
                f"must source from ITS run clone {clone_ref!r} (runs_root/<run-id>/repo)"
            )
            continue
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
        elif category == REPO_CLONE_CATEGORY:
            # The clone mount is the cell's repo: ro for a read-only cell, rw for a
            # commit-capable implementation cell (its commits land in ITS clone). Either is
            # contract-legal; the shared surfaces are already excluded above.
            if mode not in ("ro", "rw"):
                errors.append(
                    f"step 3: /repo clone mount mode {mode!r} not in ro/rw"
                )
        elif mode != contract_mode:
            errors.append(
                f"step 3: mount {target!r} mode {mode!r} != contract {contract_mode!r}"
            )
    if clone_world and not any(
        str((m or {}).get("target", "")) == REPO_TARGET
        and str((m or {}).get("source", "") or "") == str(clone_ref)
        for m in mounts
    ):
        errors.append(
            f"step 3: a clone-world request must mount its repo from the run clone "
            f"({clone_ref!r}) at {REPO_TARGET} — no /repo clone mount present"
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
    path_config: PathConfig | None = None,
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
    ``path_config`` (b1_path_config) is forwarded to the submit delegation; scale/drain/restart
    never touch host paths.
    """
    errors: list[str] = []
    action = str(command.get("action", ""))
    if action not in FLEET_ACTIONS:
        errors.append(f"action {action!r} is not one of {sorted(FLEET_ACTIONS)}")
        return errors

    if action == "submit":
        return validate_submit_request(
            command, repo_root=repo_root, phase_scopes=phase_scopes, path_config=path_config,
        )

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


def _is_worktree_scoped_workdir(
    workdir: str,
    path_config: PathConfig | None = None,
) -> list[str]:
    """Check a submit's ``workdir`` against the worktree-root contract + host-service markers.

    A valid workdir is a path strictly UNDER the config's ``worktrees_root`` (the shared worktree
    namespace every worker/orchestrator already agrees on — ``FINOPS_WORKTREE_ROOT``, default
    the ``/tmp`` namespace the ladder mounts into every container at the same path).
    "Strictly under" (not equal to the root) matters because the root itself is a shared
    directory, not one job's isolated worktree — mounting it would hand a cell every OTHER
    job's worktree too.
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

    path_config = path_config or default_path_config()
    worktree_root = path_config.worktrees_root.resolve()
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
    path_config: PathConfig | None = None,
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

    ``path_config`` (b1_path_config) is the :class:`PathConfig` the workdir check and the
    per-phase mount derivation/validation use, so a submit request and its derived phase
    requests all speak one config (default: derived from the environment at call time).
    ``repo_root`` remains the spec-resolution root (the checkout the wrapper sees); it defaults
    to this module's own repo root and is independent of the host-path ``path_config.repo_root``.
    """
    errors: list[str] = []
    path_config = path_config or default_path_config()
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
    errors.extend(_is_worktree_scoped_workdir(workdir, path_config=path_config))

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
                path_config=path_config,
            )
            for e in validate_spawn(
                phase_request, phase_scopes=phase_scopes, path_config=path_config
            ):
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


# ── The spawn mechanism (validate THEN the broker over the seam) ─────────────


def _broker_client() -> BrokerClient:
    """The seam client for this spawn path, bound to the configured broker socket.

    The socket path is resolved from the environment at call time (``FINOPS_LAUNCH_BROKER_SOCKET``,
    else the user runtime dir) so a test or an operator can re-point the seam between requests.
    The broker itself — the host-side systemd unit — is never imported here; this module only
    ever speaks the seam.
    """
    return BrokerClient()


def _broker_outcome_or_raise(outcome: dict[str, Any]) -> dict[str, Any]:
    """Map a broker outcome's NAMED ``state`` onto this module's refusal contract.

    The host broker replies to every request with a complete outcome carrying a ``state``:

    * ``REFUSED`` — the broker re-validated what it will execute and refused. Mapped to
      :class:`SpawnValidationError` with the broker's errors, the SAME refusal type the old
      in-process ``LaunchRequestError`` mapping produced (callers keep one refusal type).
    * ``DOCKER_UNAVAILABLE`` / ``SERVER_ERROR`` — the broker cannot reach docker, or faulted.
      Raised as a :class:`SpawnValidationError` carrying the named state — a LOUD failure,
      never a silent pass (fb2 VERIFY e: docker-unavailable fails loudly, never silently).
    * ``DRY_RUN`` / ``OK`` / ``RUN_FAILED`` / ``PONG`` — returned as-is; the caller classifies
      the docker outcome (a nonzero ``returncode`` is a normal cell outcome, not a refusal).
    """
    state = str(outcome.get("state", ""))
    if state == "REFUSED":
        raise SpawnValidationError(
            outcome.get("errors") or ["the launch broker refused the request"]
        )
    if state == "DOCKER_UNAVAILABLE":
        raise SpawnValidationError(
            [outcome.get("stderr") or "the host-side broker cannot reach docker (state "
             "DOCKER_UNAVAILABLE)"]
        )
    if state == "SERVER_ERROR":
        raise SpawnValidationError(
            [outcome.get("stderr") or "the launch broker faulted (state SERVER_ERROR)"]
        )
    return outcome


def spawn_sibling(
    request: dict[str, Any],
    *,
    phase_scopes: dict[str, str] | None = None,
    dry_run: bool = False,
    now: float | None = None,
    require_lease: bool | None = None,
    path_config: PathConfig | None = None,
) -> dict[str, Any]:
    """Validate a typed launch request, then emit it to the broker over the seam.

    The ordering is the load-bearing guarantee: :func:`validate_spawn` runs FIRST, and any error
    raises :class:`SpawnValidationError` before anything is launched — a compromised phase can
    never reach the broker with a request it was not authorized for, and (since admission_leases
    p2) never with a request it has no lease for. The typed contract is then checked with the
    SHARED :func:`broker_contract.validate_launch_request` (the wrapper validates what it intends
    to submit against the same profiles the broker validates what it will execute against), and
    the request is emitted to the host-side launch broker over the seam
    (:func:`_broker_client` → ``BrokerClient.launch``). The wrapper never builds a docker argv
    and never calls docker (b3_launch_broker), and it never imports the broker module either
    (fb2_broker_hostside — the docker call executes only in the broker's host process).

    On success returns ``{"ok", "argv", "returncode", "stdout", "stderr", "state"}`` — the argv
    is the broker's (a ``dry_run`` builds it only). A broker refusal (``state == REFUSED``) and
    a broker-side failure (``DOCKER_UNAVAILABLE`` / ``SERVER_ERROR``) are mapped onto this
    module's :class:`SpawnValidationError` so callers keep one loud refusal type
    (:func:`_broker_outcome_or_raise`). A seam that cannot be reached (the broker unit is down)
    raises :class:`SpawnValidationError` with the socket path — never a silent pass.

    ``path_config`` (b1_path_config) is the :class:`PathConfig` the LOCAL validation derives its
    mount contract from (default: derived from the environment at call time). The broker
    re-validates + executes against ITS OWN host config, derived from the same env in
    deployment — a client never sends host paths or a config over the seam.
    """
    errors = validate_spawn(
        request, phase_scopes=phase_scopes, now=now, require_lease=require_lease,
        path_config=path_config,
    )
    if errors:
        raise SpawnValidationError(errors)

    typed_errors = validate_launch_request(request, path_config=path_config)
    if typed_errors:
        raise SpawnValidationError(typed_errors)

    try:
        outcome = _broker_client().launch(request, dry_run=dry_run)
    except BrokerError as exc:
        # The SEAM itself failed (the host broker unit is down / the socket is absent) — loud.
        raise SpawnValidationError([str(exc)]) from exc
    return _broker_outcome_or_raise(outcome)


#: P0-3: state-namespace sanitization is defined ONCE in the pure shared contract
#: (``broker_contract.sanitize_namespace`` — the broker mints the same namespace it validates).
#: This alias preserves this module's historical private name for its callers/tests; it never
#: re-implements the rule, so the wrapper and the broker cannot drift.
_sanitize_namespace = sanitize_namespace


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
    run_clone: str | Path | None = None,
    path_config: PathConfig | None = None,
    image: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    """Build a scope-driven spawn request for one workflow phase (the campaign-wrapper mechanism).

    Resolves the phase's authorized scope (declared ``scope:`` → authorization table), then
    assembles the mount profile (the fixed :data:`MOUNT_PROFILES` the broker defines — selected
    by the scope's writability) + the scope's network + the canonical cell env (the write flag
    only when the scope authorizes it). The result IS the typed launch request the broker
    accepts (:data:`LaunchRequest`): the six canonical fields ``image_digest`` / ``network`` /
    ``mount_profile`` / ``state_namespace`` / ``command`` / ``timeout_seconds`` ride on the
    request alongside the scope-model context (``phase`` / ``scope`` / ``env`` / the lease
    block / ``run_clone``) that the shared validation consumes. The request's ``mounts`` are the
    SHARED profile expansion (:func:`broker_contract.mounts_for_profile` — the ONE expansion the
    wrapper AND the broker derive) — the wrapper validates the same mount set the broker will
    execute, and neither side can assemble a mount the other does not derive. The result feeds
    :func:`spawn_sibling`, which re-validates it before emitting it to the broker over the seam.
    ``command`` is the sibling container's entrypoint (defaults to the phase-runner; see
    ``phase_runner.py``).

    ``path_config`` (b1_path_config) is the :class:`PathConfig` every host path on the request
    derives from — the worktree/results/repo mounts' SOURCES, the repo-alias + its ``.git``
    target pair (the config's ``repo_root`` / ``git_dir``), the D-2 auth dirs (the config's
    ``auth_home``), the per-attempt state namespace root, and the credential-file source.
    Defaults to the environment-derived config (:func:`default_path_config`); a request built
    with an explicit config validates against the SAME config (``validate_spawn``'s
    ``path_config``), so a request can never name a host path the validator does not derive.

    P0-3 (control-plane stabilization): every sibling carries a UNIQUE writable state
    namespace — ``<config.state_root>/<state_namespace>`` mounted at ``/state`` (rw) with
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

    ``run_clone`` (fb1_clone_mounted — the clone is the cell's world) is the run's private
    ephemeral clone path — ``PathConfig.runs_root/<run-id>/repo`` — carried on the request so
    the cell executes in ITS OWN clone, never a shared worktree with a shared writable ``.git``.
    It is both a top-level typed REFERENCE (the broker validates it resolves to a genuine
    runs_root clone) AND the mount source of the cell's repo: :func:`mounts_for_profile`
    binds the clone at ``/repo`` (rw for a commit-capable implementation cell, ro for a
    read-only cell) and drops the shared worktree/``.git`` surface from the expansion. The
    request's ``mounts`` are that clone-world expansion, and :func:`validate_spawn` refuses a
    clone-world request that would mount the shared worktree or shared ``.git``. Omitted (the
    default — a caller that has not provisioned a clone), the request keeps the pre-clone
    shared-worktree shape and carries no ``run_clone`` key.

    ``view`` (ws2_broker_pathview, fleet_launch_smoke): every request this builder returns
    carries the VIEW of ``path_config`` — the config whose paths the request's mounts were
    built against. A config rooted at the image's ``/app`` (a container-tier derivation,
    ``FINOPS_REPO_DIR`` absent) stamps ``container``; a checkout-rooted config stamps ``host``.
    The broker validates the request against the view it carries (a container-view request
    against the container-view PathConfig), so the D-16 repo-alias split never becomes a
    refusal for a request the container tier legitimately built.

    ``image`` (b3_launch_broker) is the sibling's image reference (``fleet/base`` /
    ``fleet/orchestrator`` / ``fleet/job-<name>``) carried on the request as
    ``image_digest``. Defaults to :data:`CELL_IMAGE`. ``timeout_seconds`` bounds the broker's
    docker subprocess when positive; ``0``/``None`` (the default) means the child's own
    per-phase ``--timeout`` governs (no docker-side kill).
    """
    path_config = path_config or default_path_config()
    scope = phase_scope(phase_def)
    if scope is None:
        # No declared scope and no authorization-table entry — the spawn will fail at step 2.
        scope = ""
    cfg = _scope_config(scope) or {}
    results_mode = cfg.get("results_mode", "rw")

    # b3_launch_broker: the mount PROFILE is the closed vocabulary; the profile's expansion
    # (mounts_for_profile) is the mount set BOTH sides derive. The profile is selected by the
    # scope's writability — results rw ⇒ implementation_rw, results ro ⇒ repo_readonly — and a
    # verifier request overrides it to verifier_readonly in build_verifier_request. The
    # membership guard keeps the builder on the SAME closed table the broker validates against
    # (a profile the broker does not define can never leave this builder).
    profile = "implementation_rw" if results_mode == "rw" else "repo_readonly"
    if profile not in MOUNT_PROFILES:
        raise ValueError(
            f"scope {scope!r} resolved to profile {profile!r}, which is not in the broker's "
            f"fixed mount profiles {sorted(MOUNT_PROFILES)}"
        )

    # P0-3: the per-attempt state namespace + the credential FILE mount. The host namespace is
    # minted by the profile expansion (mkdir -p, best-effort) and is unique to this request:
    # <spec>/<phase> by default, or a finer run/step/attempt value the orchestrator passes.
    namespace = state_namespace or f"{spec_name or 'spec'}/{phase_def.get('name', 'phase')}"
    ns_safe = sanitize_namespace(namespace)
    mounts = mounts_for_profile(
        profile,
        path_config=path_config,
        state_namespace=ns_safe,
        run_clone=run_clone,
    )

    auth_home = path_config.auth_home
    env: dict[str, str] = {
        "FINOPS_REDIS_HOST": os.environ.get("FINOPS_REDIS_HOST", "finops-queue"),
        "FINOPS_REDIS_PORT": os.environ.get("FINOPS_REDIS_PORT", "6379"),
        "FINOPS_REDIS_DB": "1",
        "FINOPS_KB_DB": "2",
        "FINOPS_WORKTREE_ROOT": "/tmp",
        "HOME": str(auth_home),
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
        "network": cfg.get("network", LAUNCH_NETWORK),
        "env": env,
        "command": command or [
            "python3", "scripts/fleet/phase_runner.py",
            "--spec-name", spec_name,
            "--phase", str(phase_def.get("name", "")),
            "--goal", goal,
            "--model", model,
            "--workdir", "/tmp",
        ],
        # b3_launch_broker — the typed launch fields the broker validates against the fixed
        # profiles (image in the closed fleet namespace, network fixed, profile known,
        # namespace safe, command a typed argv, timeout bounded).
        "image_digest": image or CELL_IMAGE,
        "mount_profile": profile,
        "state_namespace": ns_safe,
        "timeout_seconds": timeout_seconds or 0,
    }
    # fb1_clone_mounted: the run's private clone path, when the caller carries one. The request
    # carries the clone — runs_root/<run-id>/repo — as a typed reference (validate_launch_request
    # step 5b checks it resolves under the runs root) AND its mount set is the clone-world
    # expansion (mounts_for_profile bound the clone at /repo and dropped the shared
    # worktree/.git surface), which validate_spawn's step 3 enforces at the mount contract.
    if run_clone:
        request["run_clone"] = str(run_clone)
    # ws2_broker_pathview (fleet_launch_smoke): the request carries the VIEW of the PathConfig
    # its mounts were built against (config_view — host for a checkout-rooted config, container
    # for a config rooted at the image's /app). The broker validates the request against that
    # view, so a container-tier request's /app D-16 alias mounts are never refused for a path
    # split the caller cannot see. Absent (a hand-built legacy request) the broker defaults to
    # host; every builder-made request carries its view explicitly.
    request["view"] = config_view(path_config)
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
    run_clone: str | Path | None = None,
    path_config: PathConfig | None = None,
    image: str | None = None,
    timeout_seconds: int | None = None,
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
    READ-ONLY in its entirety (g1_verifier_mount, engine_gaps_followups F1). In the
    shared-worktree shape that surface is the worktree namespace (``/tmp`` — the candidate
    workdir), the repo (``/repo``), and both git dirs (``/repo/.git`` + the host-path ``.git``
    alias). In the clone world (fb1_clone_mounted) it is the run's own clone, mounted read-only
    at ``/repo`` — the suite runs against the clone's TREE, and the clone's own ``.git`` rides
    inside the mount (no shared git dir is mounted at all). A verifier needs the candidate's
    TREE to run the suite against, never the ability to change it — so the writable candidate
    surfaces an agent phase mounts (``rw`` because it COMMITS its work) are flipped to ``ro``
    HERE, at the mount contract, never left to the child's ``--no-commit``. The request is
    stamped with :data:`VERIFIER_REQUEST_MARKER` so :func:`validate_spawn` enforces
    read-only-for-candidate at validation time (a verifier request that would mount the
    candidate ``rw`` is refused before the socket call).

    ``admission`` mirrors ``build_phase_request``'s contract: supplied when a lease context is
    in force; a verifier request deliberately has none when absent, because the verifier spends
    no model dollars (a budget lease reserves model spend — the verifier has none to reserve).

    ``path_config`` (b1_path_config) is forwarded to :func:`build_phase_request`; the
    forbidden-surface drop removes exactly the auth dirs THAT config mounted, so a verifier
    request can never retain a credential mount the config did not add.

    ``run_clone`` (fb1_clone_mounted) is forwarded to :func:`build_phase_request` unchanged —
    a verifier verifies against the run's private clone too (the suite runs in the read-only
    clone), so when the caller carries the clone path the verifier request's candidate mount IS
    the clone (read-only), and validation (step 3's verifier branch + the clone-world repo
    binding) enforces that it stays read-only against the clone.

    ``image`` / ``timeout_seconds`` (b3_launch_broker) are forwarded to
    :func:`build_phase_request`. The typed request's ``mount_profile`` is overridden to
    :data:`verifier_readonly <broker_contract.MOUNT_PROFILES>` — the broker's fixed verifier
    profile — and the request's ``mounts`` become THAT profile's expansion (the reduced,
    all-``ro`` candidate surface), so the wrapper validates the exact mount set the broker will
    execute for a verifier.
    """
    path_config = path_config or default_path_config()
    request = build_phase_request(
        phase_def,
        goal=goal,
        workdir=workdir,
        model=model,
        spec_name=spec_name,
        command=command,
        admission=admission,
        run_clone=run_clone,
        path_config=path_config,
        image=image,
        timeout_seconds=timeout_seconds,
    )
    # F1 (g1_verifier_mount) + b3_launch_broker: the verifier's mount set IS the broker's
    # ``verifier_readonly`` profile expansion — the candidate surface (worktree /tmp, repo
    # /repo + /repo/.git, the host-path repo-alias + its .git), every mount READ-ONLY, with NO
    # results/state/auth mounts. Deriving it from the profile (not by dropping mounts from the
    # agent expansion) makes the wrapper and the broker derive the SAME verifier surface from
    # the SAME profile. The verifier container cannot write its candidate through any mount; if
    # a writable scratch is ever genuinely needed it is a SEPARATE, empty, non-candidate volume
    # (never the worktree, never .git), and validation refuses any non-candidate mount on a
    # verifier request regardless. Marking the request lets validation REFUSE a request that
    # would mount the candidate rw.
    ns_safe = str(request.get("state_namespace", "") or "verifier")
    request["mount_profile"] = "verifier_readonly"
    request["mounts"] = mounts_for_profile(
        "verifier_readonly",
        path_config=path_config,
        state_namespace=ns_safe,
        run_clone=run_clone,
    )
    request[VERIFIER_REQUEST_MARKER] = True
    env = {k: v for k, v in (request.get("env", {}) or {}).items() if k not in STATE_ENV_KEYS}
    env.pop("FINOPS_OPENCODE_STATE_DIR", None)
    for flag in WRITE_FLAG_ENVS:
        env.pop(flag, None)
    # ws4_smoke (fleet_launch_smoke, exposed by THE SMOKE): a verifier cell runs a SUITE and
    # makes NO model call, so it mounts no CLI/auth dirs (the D-18 probe's whole premise — the
    # model CLIs attach through the D-2 auth mounts). Its container therefore boots with the
    # entrypoint's binary-resolution probe SKIPPED — the same FLEET_SKIP_PROBE=1 the compose
    # gives the supervisor services that invoke no CLI (docker-compose.ladder.yml "the
    # supervisor services invoke no CLI"). Before this fix a real verifier cell always died at
    # boot: the probe found no opencode/claude (they are not mounted) and FAILED the container
    # before the suite ever ran. An agent cell (build_phase_request) does NOT set this — it
    # mounts the CLI dirs and the probe legitimately asserts they resolve.
    env["FLEET_SKIP_PROBE"] = "1"
    request["env"] = env
    return request


#: NOTE (b3_launch_broker + fb2_broker_hostside): the compose argv builders live in the launch
#: broker module (its ``build_submit_argv`` / ``build_fleet_action_argv``) — the wrapper
#: never builds docker/compose argv. The wrapper validates a submit and emits it over the seam;
#: the HOST broker performs the ``docker compose run`` with its own compose config (a client
#: never chooses the broker's compose file — that is host-side state).


def dispatch_submit(
    command: dict[str, Any],
    *,
    repo_root: Path | str | None = None,
    phase_scopes: dict[str, str] | None = None,
    path_config: PathConfig | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Validate a submit command, then emit it to the host broker over the seam.

    Mirrors :func:`spawn_sibling`'s ordering guarantee: :func:`validate_submit_request` runs
    FIRST, and any error raises :class:`SpawnValidationError` before anything is submitted — an
    invalid submit (a bad scope, an unlisted model, a host-service workdir, an undeclared write
    flag) never reaches the broker. The compose call itself is performed by the HOST broker over
    the seam (:func:`_broker_client` → ``BrokerClient.submit``), which re-validates the submit
    with the same :func:`validate_submit_request` before executing — the ONLY docker caller
    (b3_launch_broker), reached only over the seam (fb2_broker_hostside).
    ``consume_fleet_commands`` emits ``fleet-command`` over the SAME seam for the live BRPOP
    loop; this function exists so the ordering itself is unit-testable without Redis.

    ``path_config`` (b1_path_config) is forwarded to :func:`validate_submit_request` for the
    local validation; the broker validates + executes against its own host config.
    """
    errors = validate_submit_request(
        command, repo_root=repo_root, phase_scopes=phase_scopes, path_config=path_config,
    )
    if errors:
        raise SpawnValidationError(errors)

    try:
        outcome = _broker_client().submit(command, dry_run=dry_run)
    except BrokerError as exc:
        # The SEAM itself failed (the host broker unit is down / the socket is absent) — loud.
        raise SpawnValidationError([str(exc)]) from exc
    return _broker_outcome_or_raise(outcome)


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
    dry_run: bool = False,
    once: bool = False,
) -> None:
    """BRPOP ``fleet:commands`` and dispatch validated scale/drain/restart/submit commands (D-14).

    Each popped command is validated against :func:`validate_fleet_command` BEFORE anything is
    dispatched; an invalid command is logged and dropped (never acted on). This is the
    orchestrator's "hands" — the supervisor LPUSHes, this consumer validates + emits.

    Every ``docker compose`` call is performed by the HOST launch broker over the seam
    (:func:`_broker_client` → the broker's ``fleet-command`` verb), which re-validates the
    command with the same :func:`validate_fleet_command` before executing. ``submit`` is
    dispatched the same way as scale/drain/restart (validate, then emit) but through the
    broker's submit path (the ``submit`` verb) instead of the service-shaped actions — and,
    per the isolation-over-coordination design, dispatching one submit never blocks or refuses
    another: there is no lock here, only per-request validation. NO in-container code calls
    docker and NO container mounts the docker socket (fb2_broker_hostside); the broker's own
    compose file is host-side state the client never chooses.

    A submit's ``job_id`` additionally drives the board lifecycle (p2_launch_handler,
    :func:`fleet_manager.record_job_status`): a refusal here (never reaching the broker) writes
    "failed" straight away; otherwise "running" is recorded just before the broker's
    ``docker compose`` call, and the observed exit code resolves it to "completed" or "failed" —
    a nonzero exit (or a pre-broker refusal) is ALSO filed onto the ``fleet_jobs`` dead-letter
    list (``scripts/fleet/dlq.py``), reusing the existing per-queue DLQ surface rather than
    adding a new one. A seam that cannot be reached (the host broker unit is down) marks the
    job failed with the socket path in the reason — a loud failure, never a silent pass.
    ``client`` is an injectable redis connection (tests pass a fake; the real consumer loop
    leaves it ``None`` and connects via :func:`_connect_redis`) — the same "the caller may own
    the connection" shape ``fleet_manager.py``'s own functions already use.
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

    print(f"[spawn-wrapper] consuming {COMMANDS_KEY}", flush=True)
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
        job_id = command.get("job_id") if action == "submit" else None
        if job_id:
            fleet_manager.record_job_status(client, job_id, "running")
        if not dry_run:
            try:
                outcome = _broker_client().fleet_command(command, dry_run=False)
            except BrokerError as exc:
                # The SEAM itself failed (the host broker unit is down / the socket is absent) —
                # record the job failed with the socket path; never a silent pass.
                print(f"[spawn-wrapper] BROKER UNREACHABLE {command}: {exc}", flush=True)
                if job_id:
                    reason = f"launch broker unreachable: {exc}"
                    fleet_manager.record_job_status(client, job_id, "failed", error=reason)
                    dlq.record_dead(client, "fleet_jobs", command, reason)
                if once:
                    return
                continue
            state = outcome.get("state")
            if state == "REFUSED":
                # The broker re-validated what it will execute and refused (should not fire
                # after the wrapper's own validation — fail-closed anyway).
                errors = outcome.get("errors") or ["the launch broker refused the command"]
                print(f"[spawn-wrapper] BROKER REFUSED {command}: {errors}", flush=True)
                if job_id:
                    reason = "; ".join(errors)
                    fleet_manager.record_job_status(client, job_id, "failed", error=reason)
                    dlq.record_dead(client, "fleet_jobs", command, reason)
                if once:
                    return
                continue
            if state in ("DOCKER_UNAVAILABLE", "SERVER_ERROR"):
                reason = outcome.get("stderr") or f"broker state {state}"
                print(f"[spawn-wrapper] {state} {command}: {reason}", flush=True)
                if job_id:
                    fleet_manager.record_job_status(client, job_id, "failed", error=reason)
                    dlq.record_dead(client, "fleet_jobs", command, reason)
                if once:
                    return
                continue
            argv = outcome.get("argv", [])
            print(f"[spawn-wrapper] DISPATCH {action} {service or job_id}: {argv}", flush=True)
            if job_id:
                ledger = _latest_ledger(_spec_name_for_ledger(str(command.get("spec", ""))))
                if outcome.get("returncode") == 0:
                    fleet_manager.record_job_status(
                        client, job_id, "completed",
                        returncode=outcome.get("returncode"), ledger=ledger,
                    )
                else:
                    reason = f"compose run exited {outcome.get('returncode')}"
                    fleet_manager.record_job_status(
                        client, job_id, "failed",
                        returncode=outcome.get("returncode"), ledger=ledger, error=reason,
                    )
                    dlq.record_dead(client, "fleet_jobs", command, reason)
        else:
            try:
                argv = _broker_client().fleet_command(command, dry_run=True).get("argv", [])
            except BrokerError as exc:
                print(
                    f"[spawn-wrapper] BROKER UNREACHABLE {command}: {exc} (dry-run)",
                    flush=True,
                )
                if once:
                    return
                continue
            print(f"[spawn-wrapper] DISPATCH {action} {service or job_id}: {argv} (dry-run)",
                  flush=True)
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
    args = parser.parse_args(argv)

    if args.command == "validate":
        request = json.loads(sys.stdin.read())
        errors = validate_spawn(request)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 2
        print("spawn valid")
        return 0

    consume_fleet_commands(dry_run=args.dry_run, once=args.once)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
