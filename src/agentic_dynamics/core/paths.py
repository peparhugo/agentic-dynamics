"""Single source of truth for the filesystem paths the planes share.

Two families live here:

1. **Knowledge-base / registry paths** (canonical-state R6): two repo-root-relative literals —
   the durable per-record artifact directory (``experiments/results/kb``) and the flat
   append-only registry index (``experiments/results/registry_index.jsonl``) — were
   hand-duplicated across the ``kb_produce*`` producers, ``kb_worker``, ``generate_manifest``,
   and ``knowledge_ingestion``, each with a "keep in sync by hand" comment. This module owns
   them so a path change can never silently desync a producer (which writes an artifact)
   from a consumer (which reads it back at the same location — a real data-loss vector).

2. **The fleet ``PathConfig``** (fleet_launch_boundary Wave 2, ``b1_path_config``): ONE typed
   path object for the host paths the fleet ladder mounts and derives. Before this the wrapper
   hard-coded a host-specific literal — the repo's fixed host checkout path — as its repo-alias
   mount contract and the tests pinned the same literal, tying the fleet to one host identity.
   ``PathConfig`` derives every field from the existing env contract
   (``FINOPS_REPO_DIR`` / ``FINOPS_WORKTREE_ROOT`` / ``FINOPS_OPENCODE_STATE_ROOT`` etc.) or
   from the package root, validates the configuration once (type, absoluteness, existence of
   the repo root), and refuses to be instantiated with a host-specific literal baked in as a
   default. Every consumer takes it as a parameter — never re-derives, never hardcodes.

Deliberately a *leaf* module: it imports only :mod:`pathlib`, :mod:`os`, and :mod:`dataclasses`
— no ``redis``/``chromadb``/``neo4j``. ``scripts/generate_manifest.py`` imports it as a
value-only top-level module (pointing ``sys.path`` straight at the package root) so that
dependency-light script never pulls in heavy plane ``__init__`` modules — see that script's
comment.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

#: Repo root, resolved from this module's location (``src/instrument/`` → repo root).
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

#: Durable per-record artifact directory, repo-root-RELATIVE. This relative form is the
#: ``file://`` URI contract ``knowledge_ingestion.artifact_uri`` builds (a consumer's
#: ``knowledge_stream.read_artifact`` resolves it against the checkout root); the absolute
#: :data:`KB_ARTIFACT_DIR` below is what on-disk writers use.
KB_ARTIFACT_DIR_REL = "experiments/results/kb"

#: Absolute filesystem path to the durable per-record artifact directory.
KB_ARTIFACT_DIR = PROJECT_ROOT / KB_ARTIFACT_DIR_REL

#: Flat, append-only registry index the ``kb-registry-v1`` consumer appends one compacted
#: JSON line to per indexed record (``scripts/kb_worker.py``), and that
#: ``scripts/generate_manifest.py`` later compacts into one row per entity_id.
REGISTRY_INDEX_PATH = PROJECT_ROOT / "experiments" / "results" / "registry_index.jsonl"


# ── PathConfig — ONE typed path object (fleet_launch_boundary b1_path_config) ──────────────

#: The env names the fleet path contract reads (the existing FINOPS_* contract + ``AUTH_HOME``).
#: A config is "derived from env with sane defaults": each name below is the override for one
#: :class:`PathConfig` field, and its default is the repo's own path relative to the package
#: root — never a host-specific literal.
FINOPS_REPO_DIR = "FINOPS_REPO_DIR"
FINOPS_GIT_DIR = "FINOPS_GIT_DIR"
FINOPS_WORKTREE_ROOT = "FINOPS_WORKTREE_ROOT"
FINOPS_RUNS_ROOT = "FINOPS_RUNS_ROOT"
FINOPS_RESULTS_DIR = "FINOPS_RESULTS_DIR"
FINOPS_OPENCODE_STATE_ROOT = "FINOPS_OPENCODE_STATE_ROOT"
AUTH_HOME = "AUTH_HOME"

#: The shared worktree namespace default (the pre-b2 contract: host ``/tmp`` mounted into every
#: ladder container at the same path, so existing host ``/tmp/...`` worktree paths resolve
#: unchanged inside cells). ``core.constants.WORKTREE_ROOT`` and the run/worker scripts agree
#: on this same default — the env contract, not a new invention.
_DEFAULT_WORKTREES_ROOT = "/tmp"

#: The per-run ephemeral-clone root default (fleet_launch_boundary b2 hard rule 3 names
#: ``/var/lib/agentic-dynamics/runs/<run-id>/repo``). b2 owns clone creation/discard; b1 only
#: models the path.
_DEFAULT_RUNS_ROOT = "/var/lib/agentic-dynamics/runs"

#: The D-2 auth-set relative dirs under :data:`PathConfig.auth_home` — the four read-only auth
#: mounts a cell may carry (in the container the claude symlink chain
#: ``~/.local/bin/claude`` → ``~/.local/share/claude/versions/<v>`` resolves unchanged).
AUTH_DIR_RELATIVES: tuple[str, ...] = (
    ".claude",
    ".local/bin",
    ".local/share/claude",
    ".opencode/bin",
)


class PathConfigError(ValueError):
    """Raised when a :class:`PathConfig` cannot be derived or fails validation."""


@dataclass(frozen=True)
class PathConfig:
    """ONE typed path object — the fleet's host paths, derived + validated once.

    Every field is a HOST-side absolute path the fleet mounts or writes. Defaults are the
    repo's own paths relative to the package root (or the existing env contract where the
    fleet already agreed on a shared namespace), so the object carries NO host-specific
    literal: a config whose root does not exist, or whose fields are not absolute, is refused
    at derivation time.

    Fields (env override in parentheses):

    * ``repo_root`` — the repository checkout (``FINOPS_REPO_DIR``; default: package root).
    * ``git_dir`` — the repo's git metadata dir (``FINOPS_GIT_DIR``; default
      ``repo_root/.git`` — a directory in a main checkout, a gitdir-pointer file in a linked
      worktree, either is valid).
    * ``worktrees_root`` — the shared worktree namespace (``FINOPS_WORKTREE_ROOT``; default
      ``/tmp`` — the existing contract; b2 replaces shared worktrees with per-run clones).
    * ``runs_root`` — the per-run ephemeral-clone root (``FINOPS_RUNS_ROOT``; default
      ``/var/lib/agentic-dynamics/runs`` — consumed by b2, not b1).
    * ``results_dir`` — the durable experiment-results dir (``FINOPS_RESULTS_DIR``; default
      ``repo_root/experiments/results``).
    * ``state_root`` — the per-attempt CLI-state namespace root (``FINOPS_OPENCODE_STATE_ROOT``;
      default ``worktrees_root/opencode_state`` — the compose ``${FINOPS_WORKTREE_ROOT}/opencode_state``
      contract).
    * ``auth_home`` — the host auth home the D-2 mounts + the credential file derive from
      (``AUTH_HOME``, then ``HOME``; default: the process home).
    """

    repo_root: Path
    git_dir: Path
    worktrees_root: Path
    runs_root: Path
    results_dir: Path
    state_root: Path
    auth_home: Path

    def __post_init__(self) -> None:
        #: Normalize string inputs to Path (a dataclass is allowed Path values only; coercing
        #: here keeps direct construction forgiving without a second path type in the API).
        for name in self.__dataclass_fields__:  # type: ignore[attr-defined]
            value = getattr(self, name)
            if not isinstance(value, Path):
                object.__setattr__(self, name, Path(value))
        for name in self.__dataclass_fields__:  # type: ignore[attr-defined]
            if not getattr(self, name).is_absolute():
                raise PathConfigError(
                    f"PathConfig.{name} must be an absolute path, got "
                    f"{getattr(self, name)!r} — a host path is required, never a relative one"
                )

    @property
    def auth_dirs(self) -> tuple[Path, ...]:
        """The D-2 auth set under :attr:`auth_home` — the four read-only auth mounts.

        This is the path-config derivation the spawn wrapper's ``AUTH_DIRS`` contract snapshot
        is built from (``scripts/fleet/spawn_wrapper.py``): no host-home literal lives in the
        wrapper; the four dirs are ``auth_home``-relative, exactly as compose derives them from
        ``${AUTH_HOME}``.
        """
        return tuple(self.auth_home / rel for rel in AUTH_DIR_RELATIVES)

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        require_existing: bool = True,
    ) -> PathConfig:
        """Derive a config from ``env`` (default: :data:`os.environ`) with package-root defaults.

        ``require_existing`` toggles the existence validation on the repo root + git dir: the
        default (``True``) is the "validated once" contract the fleet operates under — a
        missing root is refused, never silently accepted. ``False`` is for structural checks
        (a guard comparing contract shapes against a config whose env values may not be
        materialized on the checking host) — it still enforces type/absoluteness.
        """
        env = os.environ if env is None else env
        repo_root = Path(env.get(FINOPS_REPO_DIR) or PROJECT_ROOT)
        git_dir = Path(env.get(FINOPS_GIT_DIR) or repo_root / ".git")
        worktrees_root = Path(env.get(FINOPS_WORKTREE_ROOT) or _DEFAULT_WORKTREES_ROOT)
        runs_root = Path(env.get(FINOPS_RUNS_ROOT) or _DEFAULT_RUNS_ROOT)
        results_dir = Path(
            env.get(FINOPS_RESULTS_DIR) or repo_root / "experiments" / "results"
        )
        state_root = Path(
            env.get(FINOPS_OPENCODE_STATE_ROOT) or worktrees_root / "opencode_state"
        )
        auth_home = Path(env.get(AUTH_HOME) or env.get("HOME") or Path.home())
        cfg = cls(
            repo_root=repo_root,
            git_dir=git_dir,
            worktrees_root=worktrees_root,
            runs_root=runs_root,
            results_dir=results_dir,
            state_root=state_root,
            auth_home=auth_home,
        )
        if require_existing:
            cfg.validate()
        return cfg

    def validate(self) -> None:
        """The "validated once" existence pass — the repo root must be real.

        Only the repo root and its git dir are required to EXIST at derivation: the worktree /
        runs / results / state roots and the auth home are created or mounted on demand (the
        state namespace is ``mkdir``-ed per attempt; a results dir may be an empty overlay on a
        fresh host). A config whose repo root is missing is invalid — there is nothing to
        mount, so the refusal is the point.
        """
        if not self.repo_root.is_dir():
            raise PathConfigError(
                f"PathConfig repo_root {self.repo_root} is not an existing directory — "
                f"a missing root is an invalid configuration (refusing, never treating an "
                f"unknown root as a default)"
            )
        if not self.git_dir.exists():
            raise PathConfigError(
                f"PathConfig git_dir {self.git_dir} does not exist — the repo metadata the "
                f"cells mount is absent"
            )
