"""L31: a terminal row never records a placeholder candidate sha.

The 2026-09-22 triage found 8 promotable rows sharing the SAME unresolvable candidate
(``2e6ace3``) — the board then advertised promote actions no filesystem could fulfil. The
terminal write now verifies the sha resolves in the run's own repo and records EMPTY when it
does not (honest absence, never a false identity).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _load_module(name="run_workflow_under_test_candidate_guard"):
    spec = importlib.util.spec_from_file_location(
        name, PROJECT_ROOT / "scripts" / "run_workflow.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
    ):
        subprocess.run(cmd, cwd=repo, check=True)
    (repo / "a.txt").write_text("one\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "one"], cwd=repo, check=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    return repo, sha


def test_a_resolvable_candidate_is_recorded_verbatim(tmp_path: Path):
    module = _load_module()
    repo, sha = _repo(tmp_path)
    assert module._verified_candidate_sha(sha, str(repo)) == sha


def test_an_unresolvable_candidate_records_empty_never_a_placeholder(tmp_path: Path):
    """The 2e6ace3 class: a sha that resolves to nothing anywhere is recorded as ABSENT."""
    module = _load_module()
    repo, _sha = _repo(tmp_path)
    assert module._verified_candidate_sha("2e6ace3", str(repo)) == ""
    assert module._verified_candidate_sha("", str(repo)) == ""
    # A sha that resolves nowhere because the workdir is gone or unknown is also absent.
    assert module._verified_candidate_sha("deadbeef", "") == ""
    assert module._verified_candidate_sha("deadbeef", str(tmp_path / "missing-repo")) == ""
