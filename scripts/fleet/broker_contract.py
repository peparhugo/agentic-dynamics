#!/usr/bin/env python3
"""The launch broker's SHARED typed contract — the pure vocabulary both sides consume (fb2_broker_hostside).

The broker runs where the socket is (a host-side systemd user unit,
``infrastructure/agentic-dynamics-launch-broker.service``); the orchestrator's spawn path is NO
LONGER allowed to import the broker module and call docker in-process — it talks to the broker
over the unix-socket seam (``broker_client.py``). What the wrapper and the broker still MUST
share is this module: the fixed mount profiles, the profile→mounts expansion, the typed
launch-request validation, and the namespace sanitization. Both sides run the SAME functions
against the SAME profiles, so the isolation the wrapper validates is the isolation the broker
executes — a request can never be validated against one contract and executed against another.

This module is PURE by construction: it holds the typed vocabulary and the validation logic
only. It never builds a docker argv and never calls subprocess (the docker-argv builders and
the docker calls live in ``launch_broker.py`` — the host-side broker — so the "the ONLY docker
call site is the broker" scan stays one-file). It imports only the tier-0 path object
(``agentic_dynamics.core.paths.PathConfig``) and the tier-1 scope config table
(``agentic_dynamics.experiment.experiment_spec.SCOPE_CONFIGS``) — the same tier-0/1 surface
``spawn_wrapper.py`` already imports. It never imports ``control`` / ``runtime`` /
``adapters`` and never imports ``launch_broker`` / ``broker_client`` / ``spawn_wrapper``.
"""

from __future__ import annotations

import re
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
        # ws2_broker_pathview — the VIEW of the PathConfig the mounts were built against
        # (host | container): the broker validates a request against the view it carries, never
        # refusing a request for the D-16 repo-alias split a caller cannot see. Absent = host.
        "view",
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

# ── The request's VIEW — the path config a request's mounts were built against ─
# (ws2_broker_pathview, fleet_launch_smoke). A launch request is built by a caller on ONE
# side of the D-16 repo-alias split and carries the VIEW of the :class:`PathConfig` it derived
# its mounts from. The HOST view is the broker's own launch view (the operator's env — the
# repo at its host path). The CONTAINER view is what a container-tier caller derives:
# ``FINOPS_REPO_DIR`` is absent from the container env, so its ``repo_root`` defaults to the
# image's baked code root, ``/app`` — the container's D-16 alias targets are the /app-in-
# container paths, NOT the host path the mounts were really built for. The broker validates a
# request against the view it carries — never refusing a request for a path split the caller
# cannot see — while the broker's OWN launch argv always uses the host view (a docker bind
# source is a host path, whatever view a request claims).

#: The two views a request may carry. A request whose view is neither value is refused.
VIEW_HOST = "host"
VIEW_CONTAINER = "container"
VIEWS: frozenset[str] = frozenset({VIEW_HOST, VIEW_CONTAINER})

#: The in-container repo root of the fleet images (``Containerfile.fleet`` ``WORKDIR /app``) —
#: the container-tier caller's ``repo_root`` when ``FINOPS_REPO_DIR`` is absent from the
#: container env. It is the same fixed container-path vocabulary as :data:`RESULTS_TARGET`
#: (``/app/experiments/results``) — a container-path constant of the images this repo builds,
#: never a host-specific literal.
CONTAINER_REPO_ROOT = "/app"


def container_view_config(host_config: PathConfig) -> PathConfig:
    """The container-view :class:`PathConfig` — the config a container-tier request was built against.

    A container-tier caller derives its config from the container env: ``FINOPS_REPO_DIR`` /
    ``FINOPS_GIT_DIR`` / ``FINOPS_RESULTS_DIR`` are absent there, so its ``repo_root`` /
    ``git_dir`` / ``results_dir`` re-root to the image's baked ``/app`` layout
    (``CONTAINER_REPO_ROOT``), while every other field resolves from the shared env contract
    (``FINOPS_WORKTREE_ROOT`` / ``FINOPS_RUNS_ROOT`` / ``HOME``) to the same values the host
    config holds. This function derives THAT config from a host config, so the broker can
    validate a container-view request against the /app-path expectations its mounts were built
    with. The result is used for VALIDATION ONLY — the broker's own launch argv is always the
    host view (the broker's :func:`~launch_broker.launch` expands the mounts it executes from
    its host config), because a docker bind source is a host path.

    ``host_config``'s repo-rooted fields are deliberately NOT copied: the container view re-roots
    them to the in-image layout by construction. Everything else (the shared worktree/runs/state
    roots and the auth home) carries over unchanged — both views agree on them by the env contract.
    """
    repo_root = Path(CONTAINER_REPO_ROOT)
    return PathConfig(
        repo_root=repo_root,
        git_dir=repo_root / ".git",
        worktrees_root=host_config.worktrees_root,
        runs_root=host_config.runs_root,
        results_dir=repo_root / "experiments" / "results",
        state_root=host_config.state_root,
        auth_home=host_config.auth_home,
    )


def config_view(path_config: PathConfig) -> str:
    """The VIEW a :class:`PathConfig` represents — container when it is rooted at the in-image
    ``/app`` code root (a container-tier derivation), host otherwise. A request built against a
    config carries exactly this value, so the broker re-derives the SAME config from the view a
    request declares (``container_view_config`` on its host config) and the two cannot disagree
    about which repo-alias targets are in contract."""
    if str(path_config.repo_root) == CONTAINER_REPO_ROOT:
        return VIEW_CONTAINER
    return VIEW_HOST


def request_view(request: Any) -> str:
    """The view a (validated) request declares — :data:`VIEW_HOST` when it carries none (a
    host-side caller that predates the view field) or is not a typed request object at all.
    Callers run this only after :func:`validate_launch_request` has accepted the request, so an
    unknown view value is already a refusal, never silently re-mapped to host."""
    if isinstance(request, Mapping):
        view = request.get("view")
        if view in VIEWS:
            return view
    return VIEW_HOST


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
       dict) is refused here, never interpreted; an explicit ``view`` is one of the two known
       views (``host`` / ``container`` — ws2_broker_pathview; absent = host);
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

    # Step 1b — the VIEW is one of the two known views (ws2_broker_pathview). Absent = host
    # (a host-side caller that predates the view field); an explicit value outside {host,
    # container} is refused — the broker validates a request against the view it carries, and
    # an unknown view is a request the broker cannot classify.
    view = request.get("view")
    if view not in (None, "") and view not in VIEWS:
        errors.append(
            f"view {view!r} is not one of {sorted(VIEWS)} — the broker validates a launch "
            f"request against the view it carries (host = the broker's own config, container "
            f"= the /app-in-container config a container-tier caller derives)"
        )

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
