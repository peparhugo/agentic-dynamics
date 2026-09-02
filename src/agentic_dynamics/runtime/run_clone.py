"""The ephemeral-clone lifecycle (fleet_launch_boundary Wave 2, ``b2_ephemeral_clone``).

Hard rule 3 of the wave: **PRIVATE CLONE PER RUN** — a run's cells execute in their OWN
ephemeral clone at ``PathConfig.runs_root/<run-id>/repo``, never in a shared host worktree
whose ``.git`` is a writable shared overlay. Two concurrent cells never share git metadata,
and a bad cell cannot pollute another cell's view (or the shared repo's objects).

This module owns the lifecycle **half** of that rule — clone CREATION and DISCARD:

* :func:`create_run_clone` — a fresh ``git clone`` of the source repo (default: the
  config's ``repo_root``) at ``runs_root/<run-id>/repo``, checked out at the run's base sha.
  The clone is independent: it is made with ``--no-hardlinks`` so it shares NO object files
  with the source (a bad cell that corrupts its own clone's objects cannot corrupt the
  source or a sibling clone), and it has its OWN ``.git`` (its own refs/HEAD/index/config).
  Refusal is fail-closed: an existing clone directory for the same run id is never reused —
  a stale clone must be discarded first (or swept), never silently adopted.
* :func:`discard_run_clone` — removes a run's clone after the run. It accepts a
  :class:`RunClone`, a path, or a run id, and refuses to remove anything that is not exactly
  a ``runs_root/<run-id>/repo`` directory (a stray path can never be rm -rf'd through this
  API). Removal is idempotent.
* :func:`sweep_stale_clones` — the **pending-cleanup rail**: a run that dies before its
  discard leaves its clone behind; the sweep removes clones whose ``repo`` directory has not
  been touched for ``max_age_seconds``. Discard is the primary cleanup; the sweep is the
  documented crash/abandonment backstop.

The **mount** half of the rule belongs to the launch broker (``b3_launch_broker``): the
clone is mounted into a cell (read-only, or rw only for the cell's own scratch) by the
broker, which owns the Docker call. The **request** half is wired in
``scripts/fleet/spawn_wrapper.py``: :func:`~scripts.fleet.spawn_wrapper.build_phase_request`
and :func:`~scripts.fleet.spawn_wrapper.build_verifier_request` carry the clone path on the
spawn request (``run_clone``) so the broker can mount it and the verifier can run its suite
in the read-only clone. Until the broker lands, the composition root / launch environment
signals the clone path to the executors via the ``FINOPS_RUN_CLONE`` env var (see the
``fleet.docker_executor`` / ``fleet.docker_verifier_executor`` constructors).

Deliberately a leaf module for its plane: it imports only the tier-0 :class:`PathConfig`
(``core.paths``) plus the standard library — no ``redis``/``chromadb``/``neo4j``, no
``control``. The lifecycle is pure host-side git + filesystem, deterministic and offline:
a clone is created from a local source, never from a remote URL.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from agentic_dynamics.core.paths import PathConfig

#: The clone subdirectory under each run's private root (``runs_root/<run-id>/repo``).
#: ``<run-id>/repo`` — not ``<run-id>`` itself — is the clone, so the run's root can later
#: carry siblings (a scratch dir, a results pointer) without ever reusing the clone path.
REPO_SUBDIR = "repo"

#: The env name the spawn/executor path reads when the composition root does not pass a clone
#: path explicitly (``fleet.docker_executor`` / ``fleet.docker_verifier_executor``). A
#: host-side launcher that provisions a run's clone exports this to the workflow-runner tier;
#: the executors then stamp it onto every phase/verifier spawn request. Absent, executors
#: carry no clone (pre-b3 behavior unchanged).
RUN_CLONE_ENV = "FINOPS_RUN_CLONE"


class RunCloneError(RuntimeError):
    """Raised when a clone cannot be created/discarded — never silently ignored."""


@dataclass(frozen=True)
class RunClone:
    """A run's private ephemeral clone — its identity and where it lives.

    ``base_sha`` is the commit the clone was created from (the run's candidate/base sha at
    creation time) and — because creation verifies the checkout — the clone's HEAD when it
    was handed over. Sequential phases of one run commit INTO this same clone, so its HEAD
    advances as the run produces its candidate; ``base_sha`` stays the creation point.
    """

    run_id: str
    path: Path
    base_sha: str


def _git(*args: str, cwd: Path | None = None) -> str:
    """Run one git command; return stdout (stripped). A nonzero exit raises :class:`RunCloneError`.

    ``args`` are passed verbatim (callers spell full forms: ``"-C", str(path)`` first when a
    repo context is needed). Capture is silent — git's own stderr is folded into the error.
    """
    proc = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd is not None else None,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip() or (proc.stdout or "").strip() or "git failed"
        raise RunCloneError(f"git {' '.join(args)} exited {proc.returncode}: {detail}")
    return (proc.stdout or "").strip()


def _safe_run_segment(run_id: str) -> str:
    """Map an arbitrary run identifier onto ONE safe relative path segment.

    A run id is minted by the controller/fleet-manager (a uuid or a control-db id), but this
    module refuses to trust that: a hostile id must not be able to walk ``runs_root`` via a
    ``..``/absolute/separator-laden segment. Separators are split out and the surviving
    parts are joined back into a SINGLE segment (``..``/empty/``.`` parts dropped) — a
    ``<run-id>`` that is exactly one directory under ``runs_root`` is the invariant both
    :func:`create_run_clone` and :func:`discard_run_clone` rely on (their paths are always
    exactly ``runs_root/<segment>/repo``). An id with no usable part refuses loudly.
    """
    parts = [
        p for p in str(run_id).replace("\\", "/").split("/") if p not in ("", ".", "..")
    ]
    if not parts:
        raise RunCloneError(f"run id {run_id!r} has no usable path segment")
    return "-".join(parts)


def run_clone_dir(run_id: str, *, path_config: PathConfig | None = None) -> Path:
    """The clone path for a run: ``PathConfig.runs_root/<run-id>/repo`` (never creates it).

    ``path_config`` defaults to the environment-derived config (:func:`PathConfig.from_env`).
    """
    cfg = path_config or PathConfig.from_env(require_existing=False)
    return cfg.runs_root / _safe_run_segment(run_id) / REPO_SUBDIR


def create_run_clone(
    run_id: str,
    base_sha: str | None = None,
    *,
    source_repo: str | Path | None = None,
    path_config: PathConfig | None = None,
) -> RunClone:
    """Create a run's private ephemeral clone from ``base_sha``; verify its head.

    The clone is created fresh at ``PathConfig.runs_root/<run-id>/repo`` as an independent
    ``git clone`` of ``source_repo`` (default: the config's ``repo_root``):

    * ``--no-hardlinks`` — the clone copies its objects; it shares NO file with the source,
      so a bad cell that corrupts its clone's object DB cannot corrupt the shared repo or a
      sibling clone created from the same source.
    * when ``base_sha`` is given, the clone is checked out detached at exactly that commit
      and its HEAD is verified to equal ``base_sha`` before it is returned — a clone whose
      head is NOT the requested base is a failed creation (the deliverable of b2 VERIFY (a)).
      A ``base_sha`` that does not exist in the source fails the checkout and is refused.
    * when ``base_sha`` is omitted, the clone checks out the source's default branch and the
      resolved HEAD becomes the recorded ``RunClone.base_sha``.

    Fail-closed on reuse: an existing ``runs_root/<run-id>/repo`` is REFUSED (a stale clone
    from a previous incarnation of the same id must be discarded/swept, never silently
    adopted — two run ids producing distinct clones is the invariant, and a reused path would
    be the same clone twice). A failed creation removes its own partial directory.

    ``path_config`` defaults to the environment-derived config; ``source_repo`` defaults to
    the config's ``repo_root``. Both may be injected (tests point both at scratch dirs).
    """
    cfg = path_config or PathConfig.from_env()
    source = Path(source_repo).expanduser() if source_repo is not None else cfg.repo_root
    if not source.is_dir():
        raise RunCloneError(
            f"create_run_clone: source repo {source} is not an existing directory — "
            f"there is nothing to clone"
        )
    if not _looks_like_repo(source):
        # .git may be a directory (main checkout) or a gitdir pointer file (linked worktree);
        # either is a repo. Anything else is not — refused before git runs.
        raise RunCloneError(
            f"create_run_clone: source {source} has no .git (dir or gitdir pointer) — "
            f"not a git repository"
        )

    dest = run_clone_dir(run_id, path_config=cfg)
    if dest.exists():
        raise RunCloneError(
            f"create_run_clone: run {run_id!r} already has a clone at {dest} — refusing to "
            f"reuse a stale clone; discard or sweep it first (two runs never share a path)"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        if base_sha:
            _git("clone", "--no-checkout", "--no-hardlinks", "--", str(source), str(dest))
            _git("-C", str(dest), "checkout", "--quiet", "--detach", base_sha)
            head = _git("-C", str(dest), "rev-parse", "HEAD")
            if head != base_sha:
                raise RunCloneError(
                    f"create_run_clone: clone head {head} != requested base {base_sha} — "
                    f"the clone does not contain the expected head"
                )
        else:
            _git("clone", "--no-hardlinks", "--", str(source), str(dest))
            head = _git("-C", str(dest), "rev-parse", "HEAD")
        return RunClone(run_id=run_id, path=dest, base_sha=head)
    except RunCloneError:
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        raise


def _looks_like_repo(path: Path) -> bool:
    return (path / ".git").exists()


def _clone_path_for(clone: RunClone | Path | str, *, path_config: PathConfig | None = None) -> Path:
    """Resolve ``clone`` (a RunClone, a path, or a run id) to a clone PATH.

    A bare string is a run id when it has no path separators and does not already exist as a
    path; otherwise it is taken as a path. The resolved path is NOT yet checked for being
    under ``runs_root`` — :func:`discard_run_clone` applies that guard.
    """
    if isinstance(clone, RunClone):
        return clone.path
    value = Path(clone)
    if isinstance(clone, str) and "/" not in clone.replace("\\", "/") and not value.exists():
        return run_clone_dir(clone, path_config=path_config)
    return value


def discard_run_clone(
    clone: RunClone | Path | str,
    *,
    path_config: PathConfig | None = None,
) -> bool:
    """Remove a run's ephemeral clone; idempotent; refuses anything outside ``runs_root``.

    Only an EXACT ``runs_root/<run-id>/repo`` directory may be removed through this API — the
    path must resolve strictly under the config's ``runs_root`` and its final two segments
    must be ``<run-id>/repo``. A stray absolute path, a path outside the runs root, or a
    ``runs_root/<run-id>`` that is not a ``repo`` directory raises :class:`RunCloneError`
    (never an rm -rf of an arbitrary directory). Returns ``True`` when a clone was removed,
    ``False`` when there was nothing to remove (idempotent discard).
    """
    cfg = path_config or PathConfig.from_env()
    dest = _clone_path_for(clone, path_config=cfg).resolve()
    runs_root = cfg.runs_root.resolve()
    try:
        rel = dest.relative_to(runs_root)
    except ValueError:
        raise RunCloneError(
            f"discard_run_clone: {dest} is outside the runs root {runs_root} — refusing"
        ) from None
    if len(rel.parts) != 2 or rel.parts[-1] != REPO_SUBDIR:
        raise RunCloneError(
            f"discard_run_clone: {dest} is not a runs_root/<run-id>/{REPO_SUBDIR} directory "
            f"(relative {rel}) — refusing to remove it"
        )
    if not dest.is_dir():
        return False
    shutil.rmtree(dest)
    return True


def sweep_stale_clones(
    *,
    path_config: PathConfig | None = None,
    max_age_seconds: float = 7 * 24 * 3600,
    now: float | None = None,
) -> list[Path]:
    """The pending-cleanup sweep: remove ``runs_root/*/repo`` clones untouched for the TTL.

    Discard (:func:`discard_run_clone`) is the primary end-of-run cleanup; this sweep is the
    documented backstop for a run that died (or was killed) before its discard ran — the
    "pending-cleanup with a sweep" half of b2 VERIFY (c). A clone's ``repo`` directory mtime
    is the staleness clock (clone creation + every subsequent phase commit touch it). Clones
    younger than ``max_age_seconds`` are never touched (an active run may legitimately pause
    between phases). Returns the removed paths; a runs root that does not exist sweeps nothing.
    """
    cfg = path_config or PathConfig.from_env()
    runs_root = cfg.runs_root
    moment = time.time() if now is None else now
    removed: list[Path] = []
    if not runs_root.is_dir():
        return removed
    for run_dir in sorted(p for p in runs_root.iterdir() if p.is_dir()):
        clone = run_dir / REPO_SUBDIR
        if not clone.is_dir():
            continue
        try:
            age = moment - clone.stat().st_mtime
        except OSError:
            continue
        if age > max_age_seconds:
            shutil.rmtree(clone, ignore_errors=True)
            removed.append(clone)
    return removed
