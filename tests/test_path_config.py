"""Tests for the ONE typed path object — ``PathConfig`` (fleet_launch_boundary b1_path_config).

The mandate's VERIFY both directions:

(a) PathConfig derives the expected paths from env with sane defaults — and NO host-specific
    literal lives in the module (grep it): defaults are the repo's own paths relative to the
    package root, overridable by the existing ``FINOPS_REPO_DIR`` / ``FINOPS_WORKTREE_ROOT`` /
    ``FINOPS_OPENCODE_STATE_ROOT`` env contract.
(b) PathConfig refuses an invalid configuration — a missing repo root (or a relative one) is a
    :class:`PathConfigError`, never a silent fallback.

Every test is pure (no docker/Redis/subprocess); the fast path's parallel-safety audit does
not cover this module (it is not ``fast``-marked), but it stays dependency-free anyway.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_dynamics.core.paths import (
    PROJECT_ROOT,
    PathConfig,
    PathConfigError,
)

_MODULE_SRC = Path(__file__).resolve().parent.parent / "src" / "agentic_dynamics" / "core" / "paths.py"


def _make_repo(tmp_path: Path, name: str = "repo") -> Path:
    """A real repo root under ``tmp_path`` (dir + ``.git``) for existence-validated configs."""
    repo = tmp_path / name
    (repo / ".git").mkdir(parents=True)
    return repo


# ── (a) derivation from env with sane defaults, no host literals ──────────────


def test_defaults_are_package_relative_with_no_env():
    """No env overrides → every path derives from the package root (or the agreed shared
    namespace contract), never a host literal: repo_root is the package root, git_dir its
    ``.git``, results_dir repo-relative, state_root under the worktrees root."""
    cfg = PathConfig.from_env({})
    assert cfg.repo_root == PROJECT_ROOT
    assert cfg.git_dir == PROJECT_ROOT / ".git"
    assert cfg.worktrees_root == Path("/tmp")
    assert cfg.results_dir == PROJECT_ROOT / "experiments" / "results"
    assert cfg.state_root == cfg.worktrees_root / "opencode_state"
    # runs_root is the design's per-run clone root (consumed by b2, modeled here by b1)
    assert cfg.runs_root == Path("/var/lib/agentic-dynamics/runs")
    # all seven are absolute host paths
    for name in ("repo_root", "git_dir", "worktrees_root", "runs_root", "results_dir",
                 "state_root", "auth_home"):
        assert getattr(cfg, name).is_absolute(), f"{name} must be absolute"


def test_no_host_specific_literal_in_the_module():
    """(a) grep the module: the host-specific repo path (and the /home user prefix it lived
    under) appears NOWHERE in the source — the default is the package root, never a literal."""
    text = _MODULE_SRC.read_text()
    assert "ai-finops-framework" not in text, "the host repo literal must not be in the module"
    assert "drseuss" not in text, "the host-user literal must not be in the module"
    # the package-root default is real: /home/... would only appear as a DERIVED env value at
    # runtime, never as text in this file.


def test_env_overrides_each_field(tmp_path):
    repo = _make_repo(tmp_path)
    results = tmp_path / "out" / "results"
    results.mkdir(parents=True)
    env = {
        "FINOPS_REPO_DIR": str(repo),
        "FINOPS_GIT_DIR": str(tmp_path / "custom.git"),
        "FINOPS_WORKTREE_ROOT": str(tmp_path / "wt"),
        "FINOPS_RUNS_ROOT": str(tmp_path / "runs"),
        "FINOPS_RESULTS_DIR": str(results),
        "FINOPS_OPENCODE_STATE_ROOT": str(tmp_path / "state"),
        "AUTH_HOME": str(tmp_path / "auth"),
    }
    (tmp_path / "custom.git").mkdir(parents=True)
    (tmp_path / "auth").mkdir(parents=True)
    (tmp_path / "wt").mkdir(parents=True)
    cfg = PathConfig.from_env(env)
    assert cfg.repo_root == repo
    assert cfg.git_dir == tmp_path / "custom.git"
    assert cfg.worktrees_root == tmp_path / "wt"
    assert cfg.runs_root == tmp_path / "runs"
    assert cfg.results_dir == results
    assert cfg.state_root == tmp_path / "state"
    assert cfg.auth_home == tmp_path / "auth"


def test_git_dir_defaults_to_repo_root_dot_git(tmp_path):
    repo = _make_repo(tmp_path)
    cfg = PathConfig.from_env({"FINOPS_REPO_DIR": str(repo)})
    assert cfg.git_dir == repo / ".git"


def test_state_root_defaults_under_the_worktrees_root(tmp_path):
    repo = _make_repo(tmp_path)
    wt = tmp_path / "wt"
    wt.mkdir()
    cfg = PathConfig.from_env({"FINOPS_REPO_DIR": str(repo), "FINOPS_WORKTREE_ROOT": str(wt)})
    assert cfg.state_root == wt / "opencode_state"


def test_results_dir_defaults_repo_relative(tmp_path):
    repo = _make_repo(tmp_path)
    cfg = PathConfig.from_env({"FINOPS_REPO_DIR": str(repo)})
    assert cfg.results_dir == repo / "experiments" / "results"


def test_auth_home_prefers_auth_home_then_home(tmp_path):
    repo = _make_repo(tmp_path)
    auth = tmp_path / "auth"
    auth.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = PathConfig.from_env({"FINOPS_REPO_DIR": str(repo), "AUTH_HOME": str(auth),
                               "HOME": str(home)})
    assert cfg.auth_home == auth
    cfg2 = PathConfig.from_env({"FINOPS_REPO_DIR": str(repo), "HOME": str(home)})
    assert cfg2.auth_home == home


def test_auth_dirs_derive_from_auth_home(tmp_path):
    """The D-2 auth set is ``auth_home``-relative (the four read-only dirs) — the config
    derivation the wrapper's contract uses, never a host-home literal."""
    repo = _make_repo(tmp_path)
    auth = tmp_path / "auth"
    auth.mkdir()
    cfg = PathConfig.from_env({"FINOPS_REPO_DIR": str(repo), "AUTH_HOME": str(auth)})
    assert cfg.auth_dirs == (
        auth / ".claude",
        auth / ".local" / "bin",
        auth / ".local" / "share" / "claude",
        auth / ".opencode" / "bin",
    )


def test_from_env_reads_os_environ(monkeypatch, tmp_path):
    repo = _make_repo(tmp_path)
    monkeypatch.setenv("FINOPS_REPO_DIR", str(repo))
    monkeypatch.setenv("FINOPS_WORKTREE_ROOT", str(tmp_path / "wt"))
    cfg = PathConfig.from_env()
    assert cfg.repo_root == repo
    assert cfg.worktrees_root == tmp_path / "wt"


# ── (b) refusal of an invalid configuration ───────────────────────────────────


def test_missing_repo_root_is_refused(tmp_path):
    env = {"FINOPS_REPO_DIR": str(tmp_path / "does_not_exist")}
    with pytest.raises(PathConfigError, match="not an existing directory"):
        PathConfig.from_env(env)


def test_missing_git_dir_is_refused(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()  # a dir WITHOUT .git is not a usable repo for the fleet
    with pytest.raises(PathConfigError, match="git_dir"):
        PathConfig.from_env({"FINOPS_REPO_DIR": str(repo)})


def test_relative_repo_root_is_refused():
    with pytest.raises(PathConfigError, match="absolute"):
        PathConfig.from_env({"FINOPS_REPO_DIR": "relative/repo"})


def test_relative_results_dir_is_refused():
    with pytest.raises(PathConfigError, match="absolute"):
        PathConfig.from_env({"FINOPS_RESULTS_DIR": "out/results"})


def test_structural_config_skips_existence_but_validate_refuses(tmp_path):
    """A guard may derive a config whose env values are not materialized on the checking host
    (require_existing=False still enforces type/absoluteness); the existence refusal comes when
    ``validate()`` is called — the "validated once" contract."""
    missing = tmp_path / "missing"
    cfg = PathConfig.from_env({"FINOPS_REPO_DIR": str(missing)}, require_existing=False)
    assert cfg.repo_root == missing
    with pytest.raises(PathConfigError, match="not an existing directory"):
        cfg.validate()


def test_validate_refuses_a_git_file_missing_root(tmp_path):
    repo = _make_repo(tmp_path)
    cfg = PathConfig.from_env({"FINOPS_REPO_DIR": str(repo)})
    assert cfg.validate() is None  # a real repo validates clean
