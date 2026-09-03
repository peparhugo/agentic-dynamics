"""b2_ephemeral_clone (fleet_launch_boundary Wave 2) — the per-run private clone lifecycle.

The wave's hard rule 3: **PRIVATE CLONE PER RUN** — a run's cells execute in their own
ephemeral clone at ``PathConfig.runs_root/<run-id>/repo``, never in a shared host worktree
with a writable shared ``.git``. This suite proves the lifecycle module
(``agentic_dynamics.runtime.run_clone``) end to end, both directions:

* (a) a run's clone is created at ``PathConfig.runs_root/<run-id>/repo`` from the base sha
  and contains the expected head;
* (b) two run ids produce two distinct clones that never share git metadata (a commit in one
  clone is invisible to the other);
* (c) discard removes the clone after the run, and the stale-clone sweep is the documented
  pending-cleanup backstop for a run that dies before its discard.

The spawn-request half of b2 (the executor's request referencing the clone path) is covered
in ``tests/test_spawn_wrapper.py`` (request builders stamp ``run_clone``) and
``tests/test_workflow_executor_parity.py`` (the real executors thread it). This suite is
pure host-side git + filesystem — no docker, no Redis, no network.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from agentic_dynamics.core.paths import PathConfig
from agentic_dynamics.runtime.run_clone import (
    REPO_SUBDIR,
    RunCloneError,
    create_run_clone,
    discard_run_clone,
    is_clone_dir,
    run_clone_dir,
    sweep_stale_clones,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))


def _git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return (proc.stdout or "").strip()


def _make_source_repo(tmp_path: Path) -> Path:
    """A real source repo with two commits (sha_a/base and sha_b/head) on ``main``."""
    repo = tmp_path / "src"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "test@example.com", cwd=repo)
    _git("config", "user.name", "test", cwd=repo)
    (repo / "a.txt").write_text("one")
    _git("add", ".", cwd=repo)
    _git("commit", "-q", "-m", "base", cwd=repo)
    (repo / "b.txt").write_text("two")
    (repo / "a.txt").write_text("one-v2")
    _git("add", ".", cwd=repo)
    _git("commit", "-q", "-m", "head", cwd=repo)
    return repo


def _make_cfg(tmp_path: Path, repo: Path) -> PathConfig:
    return PathConfig(
        repo_root=repo,
        git_dir=repo / ".git",
        worktrees_root=tmp_path / "worktrees",
        runs_root=tmp_path / "runs",
        results_dir=tmp_path / "results",
        state_root=tmp_path / "state",
        auth_home=tmp_path / "auth",
    )


def test_clone_created_at_runs_root_repo_with_expected_head(tmp_path):
    """(a) the run's clone lands at runs_root/<run-id>/repo at the base sha, tree intact."""
    repo = _make_source_repo(tmp_path)
    base_sha = _git("rev-parse", "HEAD", cwd=repo)
    cfg = _make_cfg(tmp_path, repo)

    clone = create_run_clone("run-1", base_sha, path_config=cfg)

    assert clone.path == cfg.runs_root / "run-1" / REPO_SUBDIR
    assert clone.path.is_dir()
    assert clone.base_sha == base_sha
    # the clone contains the expected head — git metadata is its own .git
    assert _git("rev-parse", "HEAD", cwd=clone.path) == base_sha
    # and the working tree is the base sha's tree, not the source's later commits
    assert (clone.path / "b.txt").read_text() == "two"
    assert (clone.path / "a.txt").read_text() == "one-v2"
    # a git dir is present and private
    assert (clone.path / ".git").is_dir()


def test_two_run_ids_produce_distinct_clones_never_sharing_metadata(tmp_path):
    """(b) two run ids → two distinct clones; a commit in one is invisible to the other."""
    repo = _make_source_repo(tmp_path)
    base_sha = _git("rev-parse", "HEAD", cwd=repo)
    cfg = _make_cfg(tmp_path, repo)

    clone_a = create_run_clone("run-a", base_sha, path_config=cfg)
    clone_b = create_run_clone("run-b", base_sha, path_config=cfg)

    assert clone_a.path != clone_b.path
    assert clone_a.path.exists() and clone_b.path.exists()
    # the .git metadata directories are separate filesystem objects (hardlinks would make
    # them the same inode set — the clone is created --no-hardlinks)
    git_a = (clone_a.path / ".git").stat().st_ino
    git_b = (clone_b.path / ".git").stat().st_ino
    assert git_a != git_b

    # a commit in clone A advances ONLY clone A
    _git("config", "user.email", "test@example.com", cwd=clone_a.path)
    _git("config", "user.name", "test", cwd=clone_a.path)
    (clone_a.path / "c.txt").write_text("cell-a-only")
    _git("add", ".", cwd=clone_a.path)
    _git("commit", "-q", "-m", "cell a commit", cwd=clone_a.path)
    head_a = _git("rev-parse", "HEAD", cwd=clone_a.path)

    assert head_a != base_sha
    # clone B's head never moved, and clone B's object store cannot see A's commit
    assert _git("rev-parse", "HEAD", cwd=clone_b.path) == base_sha
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{head_a}^{{commit}}"],
        cwd=str(clone_b.path), capture_output=True, text=True,
    )
    assert proc.returncode != 0, "clone B can resolve clone A's commit — shared metadata!"


def test_create_refuses_existing_run_dir_never_reuses_a_stale_clone(tmp_path):
    """A second create for the same run id refuses; the first clone is untouched."""
    repo = _make_source_repo(tmp_path)
    base_sha = _git("rev-parse", "HEAD", cwd=repo)
    cfg = _make_cfg(tmp_path, repo)

    first = create_run_clone("run-x", base_sha, path_config=cfg)
    with pytest.raises(RunCloneError, match="already has a clone"):
        create_run_clone("run-x", base_sha, path_config=cfg)
    # the original is intact and still at its base
    assert first.path.is_dir()
    assert _git("rev-parse", "HEAD", cwd=first.path) == base_sha


def test_create_with_unknown_base_sha_fails_and_leaves_no_partial(tmp_path):
    """A base sha the source cannot produce is refused, and the partial clone is removed."""
    repo = _make_source_repo(tmp_path)
    cfg = _make_cfg(tmp_path, repo)

    with pytest.raises(RunCloneError):
        create_run_clone("run-bad", "0" * 40, path_config=cfg)
    # nothing is left behind — a failed creation never leaves a stale clone for a later run
    assert not (cfg.runs_root / "run-bad" / REPO_SUBDIR).exists()


def test_create_without_base_sha_clones_the_default_head(tmp_path):
    """Omitting the base sha clones the source's default branch and records its HEAD."""
    repo = _make_source_repo(tmp_path)
    head = _git("rev-parse", "HEAD", cwd=repo)
    cfg = _make_cfg(tmp_path, repo)

    clone = create_run_clone("run-default", path_config=cfg)

    assert clone.base_sha == head
    assert _git("rev-parse", "HEAD", cwd=clone.path) == head
    assert (clone.path / "b.txt").exists()


def test_discard_removes_clone_after_the_run_and_is_idempotent(tmp_path):
    """(c) discard removes the clone; a second discard is a no-op, not an error."""
    repo = _make_source_repo(tmp_path)
    base_sha = _git("rev-parse", "HEAD", cwd=repo)
    cfg = _make_cfg(tmp_path, repo)

    clone = create_run_clone("run-keep", base_sha, path_config=cfg)
    assert clone.path.is_dir()

    assert discard_run_clone(clone, path_config=cfg) is True
    assert not clone.path.exists()
    assert discard_run_clone(clone, path_config=cfg) is False
    # the run's parent dir may remain; the clone itself is gone
    assert not (cfg.runs_root / "run-keep" / REPO_SUBDIR).exists()


def test_discard_accepts_run_id_and_path_and_refuses_outside_runs_root(tmp_path):
    """Discard takes a RunClone, a path, or a run id — and refuses anything not under runs_root."""
    repo = _make_source_repo(tmp_path)
    base_sha = _git("rev-parse", "HEAD", cwd=repo)
    cfg = _make_cfg(tmp_path, repo)

    create_run_clone("run-id-discard", base_sha, path_config=cfg)
    # by run id string
    assert discard_run_clone("run-id-discard", path_config=cfg) is True
    # by path
    clone2 = create_run_clone("run-path-discard", base_sha, path_config=cfg)
    assert discard_run_clone(clone2.path, path_config=cfg) is True

    # an arbitrary directory outside the runs root is refused — never an rm -rf escape hatch
    stray = tmp_path / "precious"
    stray.mkdir()
    with pytest.raises(RunCloneError, match="outside the runs root"):
        discard_run_clone(stray, path_config=cfg)
    assert stray.is_dir()
    # a runs_root/<run-id> that is not a repo dir is refused too
    wrong = cfg.runs_root / "some-run"
    wrong.mkdir(parents=True)
    with pytest.raises(RunCloneError, match="repo"):
        discard_run_clone(wrong, path_config=cfg)


def test_sweep_removes_only_stale_clones(tmp_path):
    """(c) the pending-cleanup sweep reaps old clones and never touches fresh ones."""
    repo = _make_source_repo(tmp_path)
    base_sha = _git("rev-parse", "HEAD", cwd=repo)
    cfg = _make_cfg(tmp_path, repo)

    old = create_run_clone("run-old", base_sha, path_config=cfg)
    fresh = create_run_clone("run-fresh", base_sha, path_config=cfg)
    # age only the old clone's repo directory past the TTL (the clone path IS the repo dir)
    past = old.path.stat().st_mtime - 3600
    os.utime(old.path, (past, past))

    removed = sweep_stale_clones(path_config=cfg, max_age_seconds=1800)

    assert removed == [old.path]
    assert not old.path.exists()
    assert fresh.path.exists()


def test_run_clone_dir_sanitizes_a_hostile_run_id(tmp_path):
    """A run id cannot walk runs_root — separators/.. collapse to ONE safe path segment."""
    cfg = _make_cfg(tmp_path, tmp_path / "src-absent")
    path = run_clone_dir("../escape/../run/../../evil", path_config=cfg)
    # the result is exactly runs_root/<one-segment>/repo — no .., no nesting, no escape
    assert cfg.runs_root in path.parents
    assert len(path.relative_to(cfg.runs_root).parts) == 2
    assert path.name == REPO_SUBDIR
    assert path.parent.name == "escape-run-evil"


def test_is_clone_dir_accepts_only_runs_root_run_id_repo(tmp_path):
    """(fb1) the ONE clone-shape test: exactly ``runs_root/<run-id>/repo`` is a clone path —
    nothing else (pure structural; the directory need not exist yet)."""
    cfg = _make_cfg(tmp_path, tmp_path / "src-absent")
    assert is_clone_dir(cfg.runs_root / "run-1" / "repo", path_config=cfg) is True
    assert is_clone_dir(str(cfg.runs_root / "run-1" / "repo"), path_config=cfg) is True
    assert is_clone_dir(cfg.runs_root / "run-abc" / REPO_SUBDIR, path_config=cfg) is True
    for bad in (
        "/etc/passwd",                     # a stray absolute host path
        str(cfg.runs_root / "run-1" / "other"),  # runs_root/<run-id>/<not repo>
        str(cfg.runs_root / "run-1"),      # the run dir itself, not the clone
        str(cfg.runs_root / "a" / "b" / "repo"),  # nested too deep
        str(tmp_path / "outside" / "run-1" / "repo"),  # outside runs_root
    ):
        assert is_clone_dir(bad, path_config=cfg) is False, bad
