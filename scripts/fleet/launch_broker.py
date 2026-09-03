#!/usr/bin/env python3
"""The launch broker — the host-side (non-container) holder of the Docker socket (b3_launch_broker).

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
scale/drain/restart/submit fleet actions), and returns the outcome. The spawn wrapper stops
invoking docker: it builds the typed request, and the broker — which owns the socket —
executes it. ``docker-compose.ladder.yml`` stops mounting the socket into the orchestrator
tier; the socket lives ONLY where the broker runs (host).

**The shared validation.** The wrapper's validation logic is shared with the broker: both
validate against the same profiles — the wrapper validates what it intends to submit, the
broker validates what it will execute. The wrapper imports this module's
:func:`validate_launch_request` and runs it on the request it is about to submit;
:func:`launch` runs the same check again (plus the scope-model check
``spawn_wrapper.validate_spawn`` — imported lazily to keep this module import-cycle-free) the
instant before the docker call. A request that fails either side never reaches the socket.

**The profiles own the mounts.** A launch request does not carry an arbitrary mount list as
its isolation contract: :data:`MOUNT_PROFILES` is the closed vocabulary, and the broker
expands the request's ``mount_profile`` into the concrete mount list itself
(:func:`mounts_for_profile`). The wrapper's request builders derive the SAME expansion from
the SAME profile (this module is the single source), so the two cannot disagree about what a
cell may mount. The broker executes from its OWN expansion, never from a caller-supplied
mount list — a forged or partial mount set cannot reach the socket.

This module is a script (``scripts/fleet/``), not a package plane. Its package imports are
the tier-0 path object (``agentic_dynamics.core.paths.PathConfig``) and the tier-1 scope
config table (``agentic_dynamics.experiment.experiment_spec.SCOPE_CONFIGS``) — the same
tier-0/1 surface ``spawn_wrapper.py`` already imports. It never imports ``control`` /
``runtime`` / ``adapters``; the docker call is a plain ``subprocess`` over an argv this
module builds (the project's fleet images carry the docker CLI for the operator's
``build.sh``; the broker is the only module that RUNS it).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

# scripts/fleet/ -> the repo root is two parents up; put src/ on sys.path so the tier-0/1
# planes resolve (the same "scripts/ is sys.path[0]" convention as the other scripts).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agentic_dynamics.core.paths import (  # noqa: E402
    PathConfig,
)
from agentic_dynamics.experiment.experiment_spec import (  # noqa: E402
    SCOPE_CONFIGS,
)

# ── The typed contract (proposal §2/D-14, fleet_launch_boundary b3) ──────────
#
# The ONLY shape the broker accepts. The six canonical fields are the security contract the
# broker validates against the fixed profiles; the context fields (phase/scope/env/lease/
# run_clone + the verifier marker) are the portion of a launch only the request builder knows
# (the lease block a cell must inherit as env, the scope model its validation runs against),
# carried in the SAME typed object and validated by the SAME shared checks.

#: The verifier request marker (shared with spawn_wrapper's ``VERIFIER_REQUEST_MARKER`` — the
#: value is the literal key name, so the two constants can never disagree about the field).
VERIFIER_MARKER = "verifier"

#: The mount profiles (fixed — the ladder already defines them): every non-verifier agent cell
#: mounts the four-mount contract + the D-2 auth set + the per-attempt state namespace, with
#: ``results_mode`` (ro/rw over the results mount) the ONLY per-scope variation
#: (``experiment_spec``: "results_mode is the only mount that varies, ro vs rw"). The verifier
#: profile is the reduced read-only candidate surface. A ``mount_profile`` outside this table is
#: refused by :func:`validate_launch_request` — an unknown profile never reaches the socket.
#:
#: fb1_clone_mounted: each profile's EXPANSION (:func:`mounts_for_profile`) takes the run's
#: ``run_clone`` when the request carries one and mounts the CLONE as the cell's repo (see the
#: function's docstring). The profiles below declare the cell's writability; the expansion
#: decides which host surface backs it.
MOUNT_PROFILES: dict[str, dict[str, Any]] = {
    #: The read-only repo profile: a cell that only READS the repo + results (the
    #: ``research_readonly`` / ``adversarial_readonly`` scopes). Repo and results are ro; the
    #: cell still runs a CLI agent, so it carries the D-2 auth set + its own state namespace.
    "repo_readonly": {
        "results_mode": "ro",
        "verifier": False,
        "description": "the read-only repo profile (research/adversarial read-only cells)",
    },
    #: The implementation rw profile: a cell that COMMITS + writes results (the
    #: ``implementation`` / ``proposal_write`` / ``review_readonly`` scopes — results rw). In
    #: the shared-worktree shape the gitdir overlay is rw so the phase commit can write; in the
    #: clone shape (fb1) the run's private clone is mounted rw so the cell's commits land in
    #: ITS clone.
    "implementation_rw": {
        "results_mode": "rw",
        "verifier": False,
        "description": "the implementation rw profile (implementation/proposal/review cells)",
    },
    #: The verifier read-only profile (g1_verifier_mount): the candidate surface ONLY, every
    #: mount ro — no results, no state namespace, no credentials (a verifier makes no model
    #: call). A verifier request MUST carry this profile. In the clone shape (fb1) the
    #: candidate surface IS the run's clone, mounted read-only.
    "verifier_readonly": {
        "results_mode": None,
        "verifier": True,
        "description": "the verifier read-only profile (kind:test read-only candidate cell)",
    },
}

#: The closed image namespace a launch may request. The ladder's own images (built by
#: ``scripts/fleet/build.sh``) plus the per-job ``fleet/job-<name>`` builds off the fleet/base
#: cache root (p3_base_image_caching). Anything else — a third-party image, ``docker.io/...``,
#: a bare tag — is refused: the broker is the privileged socket holder, and an arbitrary image
#: would be an arbitrary container the broker executes on the host's behalf.
IMAGE_NAMESPACE: frozenset[str] = frozenset(
    {"fleet/base", "fleet/orchestrator", "fleet/supervisor"}
)
JOB_IMAGE_PATTERN = re.compile(r"^fleet/job-[a-z0-9][a-z0-9_-]*$")

#: The only network a cell may attach to (every scope's declared network; D-17 fleet-net).
LAUNCH_NETWORK = "fleet-net"

#: The default docker subprocess timeout when a request does not declare one. A positive
#: ``timeout_seconds`` on the request is honored up to :data:`MAX_LAUNCH_TIMEOUT_SECONDS`;
#: ``0``/``None`` means "no docker-side kill" (the child's own per-phase ``--timeout``
#: governs), which is the default posture — a phase timeout of hours (e.g. the 4h adversarial
#: phase) must never be killed by the broker.
DEFAULT_LAUNCH_TIMEOUT_SECONDS = 7 * 24 * 3600
MAX_LAUNCH_TIMEOUT_SECONDS = 7 * 24 * 3600
MIN_LAUNCH_TIMEOUT_SECONDS = 1

#: The closed set of top-level fields a launch request may carry. A request carrying a field
#: outside this set is REFUSED by :func:`validate_launch_request` — the typed contract holds;
#: an untyped/arbitrary payload (a raw docker command string, a random dict, a ``docker run``
#: argv) is never accepted. Mirrors the field names ``spawn_wrapper``'s builders emit.
LAUNCH_REQUEST_FIELDS: frozenset[str] = frozenset(
    {
        # the six canonical typed fields:
        "image_digest",
        "network",
        "mount_profile",
        "state_namespace",
        "command",
        "timeout_seconds",
        # the scope-model context the shared validation consumes:
        "phase",
        "scope",
        "mounts",  # the wrapper's validated record of its profile expansion (step 3 checks it)
        "env",
        VERIFIER_MARKER,
        "run_clone",  # fb1 clone-mount reference: the broker validates runs_root/<run-id>/repo
                      # (step 5b) AND mounts the clone as the cell's /repo (mounts_for_profile)
        # the lease block (step 6 / admission_leases p2):
        "reserved_cost_usd",
        "hard_cap_usd",
        "budget_lease_id",
        "concurrency_lease_id",
        "expires_at",
    }
)

#: The canonical container mount targets + the per-attempt state target + the credential FILE
#: (the isolation constant, §3). Kept here so :func:`mounts_for_profile` — the shared
#: profile→mounts expansion both the wrapper and the broker consume — is self-contained.
WORKTREE_TARGET = "/tmp"
RESULTS_TARGET = "/app/experiments/results"
REPO_TARGET = "/repo"
STATE_TARGET = "/state"
AUTH_CRED_FILE = "/auth/opencode_auth.json"


class LaunchRequestError(ValueError):
    """Raised when a launch/fleet request fails the broker's typed validation (socket never reached).

    Carries the refused request's errors on ``.errors`` (mirrors ``SpawnValidationError`` so
    the wrapper can map a broker refusal onto its own exception type without losing detail).
    """

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("launch refused:\n" + "\n".join(f"  - {e}" for e in errors))


# ── state_namespace sanitization (shared with spawn_wrapper) ────────────────


def sanitize_namespace(namespace: str) -> str:
    """Map an arbitrary run/step/attempt identifier onto a safe RELATIVE path.

    The state namespace becomes a host path under the config's ``state_root`` — it must stay a
    relative path (no ``..``, no absolute path, no leading slash) or a ``..`` escape would walk
    the state root. Separators legal in identifiers but hostile in paths are collapsed to ``/``
    segments and ``..``/empty/``.`` segments are dropped. This is the SAME rule the wrapper's
    request builders apply when minting the state directory, so a validated namespace and a
    minted namespace can never disagree.
    """
    parts = [
        p for p in str(namespace).replace("\\", "/").split("/") if p not in ("", ".", "..")
    ]
    if not parts:
        return "unnamed"
    return "/".join(parts)


# ── The shared profile→mounts expansion ─────────────────────────────────────


def _is_verifier(profile: str) -> bool:
    return bool((MOUNT_PROFILES.get(profile) or {}).get("verifier"))


def mounts_for_profile(
    profile: str,
    *,
    path_config: PathConfig | None = None,
    state_namespace: str,
    run_clone: str | Path | None = None,
) -> list[dict[str, str]]:
    """The concrete mounts for ``profile`` — the ONE expansion both sides consume.

    The wrapper's request builders call this to assemble the mounts they validate at step 3;
    the broker calls it again to assemble the ``-v`` flags it will actually execute. Both run
    the same function against the same profile, so the isolation the wrapper validated is the
    isolation the broker mounts — a caller cannot smuggle a mount list past the profile.

    Without ``run_clone`` (the pre-b2 shared-worktree shape) each profile expands to the
    historical cell surface:

    * ``repo_readonly`` / ``implementation_rw`` — the agent-cell surface: the worktree
      namespace rw, results (mode = the profile's ``results_mode``), the repo ro + its gitdir
      overlay rw (a phase cell COMMITS), the repo at its host path (D-16 alias) + its git dir,
      the D-2 auth set ro, the per-attempt state namespace rw, and the credential FILE ro.
    * ``verifier_readonly`` — the reduced read-only candidate surface: the worktree + repo +
      both git dirs, ALL ro; no results, no state namespace, no credentials.

    With ``run_clone`` (fb1_clone_mounted — the clone is the cell's world) the expansion is the
    CLONE-world contract instead: the shared host surfaces a shared-worktree cell needed are
    GONE from the cell, and the repo the cell reads/commits comes from the run's OWN private
    clone at ``PathConfig.runs_root/<run-id>/repo``:

    * the repo source is the clone — ``/repo`` binds ``runs_root/<run-id>/repo``, read-only for
      the ``repo_readonly`` / ``verifier_readonly`` profiles and rw for ``implementation_rw``
      (an implementation cell COMMITS into its clone, so its clone is the cell's private
      working copy);
    * the shared worktree mount (``worktrees_root -> /tmp``), the shared ``/repo/.git``
      overlay, and the D-16 host-path repo + ``.git`` aliases are ALL absent — the clone has
      its OWN ``.git`` (inside the mounted clone), so no shared git metadata is reachable and
      no worktree gitdir pointer needs resolving;
    * the results / D-2 auth / per-attempt state / credential FILE mounts are unchanged.

    Two concurrent cells therefore never share git metadata through any mount: distinct runs
    have distinct clones (distinct ``runs_root/<run-id>`` paths) and each cell mounts only its
    own run's clone.
    """
    cfg = path_config or PathConfig.from_env(require_existing=False)
    profile_def = MOUNT_PROFILES.get(profile)
    if profile_def is None:
        raise LaunchRequestError(
            [f"mount_profile {profile!r} is not one of the fixed profiles "
             f"{sorted(MOUNT_PROFILES)}"]
        )

    ns = sanitize_namespace(state_namespace)
    state_src = cfg.state_root / ns
    state_src.mkdir(parents=True, exist_ok=True)

    # fb1_clone_mounted: a request that names a run clone mounts the clone as the cell's repo.
    clone = str(run_clone) if run_clone is not None else None
    if profile_def.get("verifier"):
        if clone is not None:
            # The verifier's candidate surface IS the run's clone, read-only: the suite runs
            # against the clone's tree and its own .git rides inside the mount. No results /
            # state / credential mounts (a verifier makes no model call), no shared worktree /
            # shared .git (the candidate is the clone, never the shared repo).
            return [
                {"source": clone, "target": REPO_TARGET, "mode": "ro"},
            ]
        return [
            {"source": str(cfg.worktrees_root), "target": WORKTREE_TARGET, "mode": "ro"},
            {"source": str(cfg.repo_root), "target": REPO_TARGET, "mode": "ro"},
            {"source": str(cfg.git_dir), "target": f"{REPO_TARGET}/.git", "mode": "ro"},
            {"source": str(cfg.repo_root), "target": str(cfg.repo_root), "mode": "ro"},
            {"source": str(cfg.git_dir), "target": str(cfg.git_dir), "mode": "ro"},
        ]

    results_mode = str(profile_def.get("results_mode") or "rw")
    if clone is not None:
        # The clone-world agent-cell surface: results + the repo from the run clone + the
        # D-2 auth set + the per-attempt state namespace + the credential FILE. The shared
        # worktree mount, the /repo/.git overlay, and the D-16 host-path repo/.git aliases are
        # NOT part of this contract (fb1_clone_mounted) — a cell's git operations happen
        # against ITS clone, never the shared repo's git dir.
        repo_mode = "ro" if profile == "repo_readonly" else "rw"
        mounts: list[dict[str, str]] = [
            {"source": str(cfg.results_dir), "target": RESULTS_TARGET, "mode": results_mode},
            {"source": clone, "target": REPO_TARGET, "mode": repo_mode},
        ]
        for d in cfg.auth_dirs:
            mounts.append({"source": str(d), "target": str(d), "mode": "ro"})
        mounts.append({"source": str(state_src), "target": STATE_TARGET, "mode": "rw"})
        mounts.append(
            {
                "source": str(cfg.auth_home / ".local/share/opencode/auth.json"),
                "target": AUTH_CRED_FILE,
                "mode": "ro",
            }
        )
        return mounts

    mounts: list[dict[str, str]] = [
        {"source": str(cfg.worktrees_root), "target": WORKTREE_TARGET, "mode": "rw"},
        {"source": str(cfg.results_dir), "target": RESULTS_TARGET, "mode": results_mode},
        {"source": str(cfg.repo_root), "target": REPO_TARGET, "mode": "ro"},
        {"source": str(cfg.git_dir), "target": f"{REPO_TARGET}/.git", "mode": "rw"},
    ]
    # The repo at its HOST path + its .git (D-16 fix): worktree gitdir pointers in the shared
    # worktree namespace resolve to the config's repo_root/git_dir — mounted at the SAME path
    # so one pointer is valid in the host and the container views (config-derived, never a
    # host literal — b1_path_config).
    mounts += [
        {"source": str(cfg.repo_root), "target": str(cfg.repo_root), "mode": "ro"},
        {"source": str(cfg.git_dir), "target": str(cfg.git_dir), "mode": "rw"},
    ]
    for d in cfg.auth_dirs:
        mounts.append({"source": str(d), "target": str(d), "mode": "ro"})
    # P0-3: the per-attempt state namespace (rw) + the credential FILE mount (ro).
    mounts.append({"source": str(state_src), "target": STATE_TARGET, "mode": "rw"})
    mounts.append(
        {
            "source": str(cfg.auth_home / ".local/share/opencode/auth.json"),
            "target": AUTH_CRED_FILE,
            "mode": "ro",
        }
    )
    return mounts


# ── The typed launch-request validation (shared: wrapper + broker) ──────────


def _valid_image_digest(image_digest: Any) -> bool:
    """An image reference is valid iff it is in the closed fleet namespace (with an optional
    ``:tag`` — the tag is an artifact of the image name, never an arbitrary registry pull)."""
    if not isinstance(image_digest, str) or not image_digest:
        return False
    name = image_digest.split(":")[0]
    return name in IMAGE_NAMESPACE or bool(JOB_IMAGE_PATTERN.match(name))


def _valid_state_namespace(namespace: Any) -> bool:
    """A state namespace is valid iff it is a non-empty string that sanitization leaves intact
    (no absolute path, no ``..``, no empty/dot segments) — a ``..`` escape is refused."""
    if not isinstance(namespace, str) or not namespace:
        return False
    return sanitize_namespace(namespace) == namespace


def _valid_command(command: Any) -> tuple[bool, str]:
    """A command is valid iff it is a non-empty list of plain strings (a typed argv — never a
    raw shell string) with no NUL/newline smuggling. Anything else is refused: a shell string
    or a flag-shaped argv[0] is not the typed contract."""
    if not isinstance(command, list) or not command:
        return False, "command must be a non-empty list of strings (a typed argv)"
    for i, part in enumerate(command):
        if not isinstance(part, str) or not part:
            return False, f"command[{i}] must be a non-empty string"
        if "\x00" in part or "\n" in part or "\r" in part:
            return False, f"command[{i}] carries a NUL/newline — refused (argv smuggling)"
    if str(command[0]).startswith("-"):
        return False, f"command[0] {command[0]!r} starts with '-' — refused (a docker flag, not a command)"
    return True, ""


def validate_launch_request(
    request: Any,
    *,
    path_config: PathConfig | None = None,
) -> list[str]:
    """Validate a TYPED launch request. Empty list = valid; the docker call happens only then.

    This is the SHARED validation: ``spawn_wrapper`` runs it on the request it intends to
    submit (the wrapper validates what it intends to submit) and the broker runs it again
    immediately before executing (the broker validates what it will execute) — both against
    the same profiles and vocabularies in this module, so the two can never disagree.

    Checks, in order:

    1. the request is a JSON object with NO field outside :data:`LAUNCH_REQUEST_FIELDS` — an
       untyped/arbitrary payload (a raw docker command string, a ``docker run`` argv, a random
       dict) is refused here, never interpreted;
    2. ``image_digest`` is in the closed fleet image namespace;
    3. ``network`` is exactly :data:`LAUNCH_NETWORK`;
    4. ``mount_profile`` is one of the fixed :data:`MOUNT_PROFILES` AND is consistent with the
       request — a ``verifier`` request must carry ``verifier_readonly``, and an agent
       profile's ``results_mode`` must match the request's scope (the same scope rule step 3
       of ``validate_spawn`` enforces on the results mount);
    5. ``state_namespace`` is a safe relative path (:func:`_valid_state_namespace`);
    6. ``command`` is a typed argv (:func:`_valid_command`);
    7. ``timeout_seconds`` is absent, ``0``/``None`` (no docker-side kill) or a positive number
       bounded by :data:`MAX_LAUNCH_TIMEOUT_SECONDS`.
    """
    errors: list[str] = []

    # Step 1 — the typed contract holds: an object with only known fields.
    if not isinstance(request, Mapping):
        errors.append(
            f"the broker accepts ONLY a typed launch request (a JSON object), not "
            f"{type(request).__name__!r} — a raw docker command string is refused"
        )
        return errors
    unknown = sorted(set(request) - LAUNCH_REQUEST_FIELDS)
    if unknown:
        errors.append(
            f"launch request carries unknown field(s) {unknown} — the typed contract is "
            f"closed; an arbitrary payload (a raw docker command string, a docker argv) is "
            f"refused"
        )
        return errors
    required = ("image_digest", "mount_profile", "state_namespace", "command", "network")
    for name in required:
        if request.get(name) in (None, ""):
            errors.append(f"launch request is missing the typed field {name!r}")

    # Step 2 — the image is in the closed fleet namespace.
    if request.get("image_digest") not in (None, "") and not _valid_image_digest(
        request.get("image_digest")
    ):
        errors.append(
            f"image_digest {request.get('image_digest')!r} is outside the closed fleet image "
            f"namespace {sorted(IMAGE_NAMESPACE)} + fleet/job-<name> — the broker executes "
            f"only images the ladder builds"
        )

    # Step 3 — the network is exactly the one cell network.
    network = request.get("network")
    if network not in (None, "") and network != LAUNCH_NETWORK:
        errors.append(f"network {network!r} != {LAUNCH_NETWORK!r} — the only cell network")

    # Step 4 — the mount_profile is fixed AND consistent with the request.
    profile = request.get("mount_profile")
    profile_def = MOUNT_PROFILES.get(profile) if isinstance(profile, str) else None
    if profile_def is None:
        errors.append(
            f"mount_profile {profile!r} is not one of the fixed profiles "
            f"{sorted(MOUNT_PROFILES)} — an unknown profile refuses"
        )
    else:
        is_verifier = request.get(VERIFIER_MARKER) is True
        if is_verifier and not profile_def.get("verifier"):
            errors.append(
                f"mount_profile {profile!r} is not the verifier profile — a verifier request "
                f"must carry {sorted(k for k, v in MOUNT_PROFILES.items() if v['verifier'])}"
            )
        if not is_verifier and profile_def.get("verifier"):
            errors.append(
                f"mount_profile {profile!r} is verifier-only — an agent request cannot carry it"
            )
        scope = str(request.get("scope", ""))
        cfg = SCOPE_CONFIGS.get(scope) if scope else None
        expected = cfg.get("results_mode") if cfg is not None else None
        if (
            expected is not None
            and profile_def.get("results_mode") is not None
            and expected != profile_def.get("results_mode")
        ):
            errors.append(
                f"mount_profile {profile!r} results_mode {profile_def.get('results_mode')!r}"
                f" != scope {scope} results_mode {expected!r} — the profile must match the "
                f"scope's writability"
            )

    # Step 5 — the state namespace cannot escape the state root.
    if request.get("state_namespace") not in (None, "") and not _valid_state_namespace(
        request.get("state_namespace")
    ):
        errors.append(
            f"state_namespace {request.get('state_namespace')!r} is not a safe relative path "
            f"(no absolute path, no '..' — a namespace cannot escape the state root)"
        )

    # Step 5b — the run_clone reference (fb1_clone_mounted) must name a clone under the runs
    # root: runs_root/<run-id>/repo, exactly (PathConfig.is_run_clone_dir — the ONE shape rule
    # shared with run_clone's lifecycle and spawn_wrapper's clone-world mount check). A request
    # can never name an arbitrary host path as its "clone" and have it mounted as the cell's
    # repo.
    run_clone = request.get("run_clone")
    if run_clone not in (None, ""):
        if not isinstance(run_clone, str) or not run_clone or "\x00" in run_clone:
            errors.append(f"run_clone {run_clone!r} is not a valid clone path string")
        else:
            cfg = path_config or PathConfig.from_env(require_existing=False)
            runs_root = cfg.runs_root
            if not cfg.is_run_clone_dir(run_clone):
                errors.append(
                    f"run_clone {run_clone!r} is not a runs_root/<run-id>/repo clone path "
                    f"(must be two segments under the runs root {runs_root}, the last 'repo')"
                )

    # Step 6 — the command is a typed argv.
    if request.get("command") not in (None, []):
        ok, why = _valid_command(request.get("command"))
        if not ok:
            errors.append(why)

    # Step 7 — timeout_seconds is bounded (when set).
    timeout = request.get("timeout_seconds")
    if (
        timeout not in (None, 0)
        and (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or timeout < MIN_LAUNCH_TIMEOUT_SECONDS
            or timeout > MAX_LAUNCH_TIMEOUT_SECONDS
        )
    ):
        errors.append(
            f"timeout_seconds {timeout!r} is not a number in "
            f"[{MIN_LAUNCH_TIMEOUT_SECONDS}, {MAX_LAUNCH_TIMEOUT_SECONDS}]"
        )

    return errors


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

    1. :func:`validate_launch_request` — the typed contract (image/network/profile/namespace/
       command/timeout) against the fixed profiles; and
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
    # launch_broker never imports spawn_wrapper at module scope (spawn_wrapper imports this
    # module at module scope for validate_launch_request + mounts_for_profile).
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


def _outcome_json(outcome: dict[str, Any]) -> str:
    return json.dumps(outcome, indent=2, default=str)


def main(argv: list[str] | None = None) -> int:
    """CLI: host-side broker entry points (``launch`` / ``submit`` / ``fleet-command``).

    Each subcommand reads a JSON request object (``--request`` or stdin), validates it with the
    same shared checks, and — only when valid — performs the docker/compose call. ``--dry-run``
    prints the argv it would execute. This is how the broker is invoked as its OWN host-side
    process (never from inside a socket-holding container — there is none anymore).
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
    args = parser.parse_args(argv)

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
    print(_outcome_json(outcome))
    return 0 if outcome.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
