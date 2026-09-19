"""Step 3a: the Docker executor's state namespace is per-RUN, not merely per-spec/phase.

The pre-step-3 ``<spec>/<phase>`` key let two runs of the same spec share one writable
CLI-state directory. With a run clone the namespace now carries the run id
(``runs_root/<run-id>/repo``); without a clone (the legacy shared-worktree shape) it keeps the
old form and fabricates no id.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _path in (_REPO_ROOT, _REPO_ROOT / "src", _REPO_ROOT / "scripts", _REPO_ROOT / "scripts" / "fleet"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from docker_executor import DockerAgentExecutor  # noqa: E402

from agentic_dynamics.runtime.executor import StepRequest  # noqa: E402


def _executor(**kwargs) -> DockerAgentExecutor:
    base = dict(
        spec_path="/repo/workflows/repository/t.yaml",
        spec_name="t",
        goal="g",
        model="m",
        workdir="/tmp/wt",
    )
    base.update(kwargs)
    return DockerAgentExecutor(**base)


def _request() -> StepRequest:
    return StepRequest(
        phase_name="p1",
        phase_kind="agent",
        prompt="do the thing",
        model="m",
        goal="g",
        spec_name="t",
        workdir="/tmp/wt",
        phase_def={"scope": "implementation"},
    )


def test_namespace_carries_the_run_id_when_a_clone_is_present():
    executor = _executor(run_clone="/tmp/runs/run-abc/repo")
    built = executor.build_request(_request())
    assert built["state_namespace"] == "t/run-abc/p1/a1"


def test_namespace_keeps_the_legacy_shape_without_a_clone():
    executor = _executor()
    built = executor.build_request(_request())
    assert built["state_namespace"] == "t/p1/a1"


# ── step 3b: the prepared-step transport (parent side) ──────────────────────────────────────

def test_prepared_step_is_written_and_passed_to_the_child(tmp_path):
    """The parent readies the EXACT step: the transport file carries the prompt + its hash,
    and the child argv names the child-visible path — no re-derivation from the spec."""
    clone = tmp_path / "runs" / "run-abc" / "repo"
    (clone / ".git" / "info").mkdir(parents=True)
    (clone / ".git" / "info" / "exclude").write_text("", encoding="utf-8")

    executor = _executor(run_clone=str(clone))
    built = executor.build_request(_request())

    command = built["command"]
    assert "--prepared-step" in command
    child_path = command[command.index("--prepared-step") + 1]
    assert child_path == "/repo/.fleet/prepared_steps/p1.a1.json"

    written = json.loads(
        (clone / ".fleet" / "prepared_steps" / "p1.a1.json").read_text(encoding="utf-8")
    )
    assert written["schema"] == "prepared-step/v1"
    assert written["prompt"] == "do the thing"
    assert written["prompt_sha256"] == _request().prompt_sha256
    # The concrete request is stamped with the CHILD-visible workdir (the clone mount), never
    # the parent's host path — the field the direct-execution worker uses as its cwd.
    assert written["workdir"] == "/repo"

    # the transport never lands in the cell's commits (a local-only exclude entry)
    assert ".fleet/prepared_steps/" in (
        clone / ".git" / "info" / "exclude"
    ).read_text(encoding="utf-8")

def test_prepared_step_exclusion_lands_without_a_git_info_dir(tmp_path):
    """A run clone with ``.git`` but WITHOUT ``.git/info/`` still excludes the transport.

    The original write skipped the exclusion silently when ``info/`` was absent (fresh clone
    shapes), and the engine's post-phase ``git add -A`` then committed the transport file into
    the candidate — observed on main as committed ``.fleet/prepared_steps/*.json``. The
    exclusion must be CREATED, not skipped.
    """
    import shutil
    import subprocess

    clone = tmp_path / "runs" / "run-abc" / "repo"
    clone.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=clone, check=True)
    info = clone / ".git" / "info"
    if info.exists():  # git versions differ on whether init materializes info/
        shutil.rmtree(info)
    assert not (clone / ".git" / "info").exists()

    executor = _executor(run_clone=str(clone))
    executor.build_request(_request())

    exclude = clone / ".git" / "info" / "exclude"
    assert exclude.is_file()
    assert ".fleet/prepared_steps/" in exclude.read_text(encoding="utf-8")
    # The exclusion is REAL: git refuses to see the transport as a candidate addition.
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", ".fleet/prepared_steps/p1.a1.json"],
        cwd=clone,
        capture_output=True,
    )
    assert ignored.returncode == 0

# ── run-inspection slice: the executor records the clone-relative prepared-step reference ─────


def test_prepared_relative_path_names_the_written_transport(tmp_path):
    """The recorded reference is the same transport the child is pointed at, minus the mount."""
    clone = tmp_path / "runs" / "run-abc" / "repo"
    (clone / ".git" / "info").mkdir(parents=True)
    (clone / ".git" / "info" / "exclude").write_text("", encoding="utf-8")
    executor = _executor(run_clone=str(clone))

    assert executor._prepared_relative_path(_request()) == ".fleet/prepared_steps/p1.a1.json"
    command = executor.build_request(_request())["command"]
    child_path = command[command.index("--prepared-step") + 1]
    assert child_path == "/repo/.fleet/prepared_steps/p1.a1.json"
    assert child_path.endswith(executor._prepared_relative_path(_request()))


# ── isolated conversation forks: the parent-side checkpoint staging ───────────────────────

def test_fork_checkpoint_is_staged_into_the_clone_and_stamped(tmp_path):
    """A declared fork_checkpoint: session id + hash stamped, db copied beside the step."""
    import sqlite3

    seed = tmp_path / "seed-data"
    (seed / "opencode").mkdir(parents=True)
    con = sqlite3.connect(seed / "opencode" / "opencode.db")
    con.execute("create table session (id text primary key, time_created integer)")
    con.execute("insert into session values ('ses_parent_abc', 5)")
    con.commit()
    con.close()

    clone = tmp_path / "runs" / "run-abc" / "repo"
    clone.mkdir(parents=True)
    executor = _executor(run_clone=str(clone))
    request = _request()
    request.phase_def = {"scope": "implementation", "fork_checkpoint": str(seed)}
    built = executor.build_request(request)

    prepared = json.loads(
        (clone / ".fleet" / "prepared_steps" / "p1.a1.json").read_text(encoding="utf-8")
    )
    assert prepared["fork"]["session_id"] == "ses_parent_abc"
    stamped = clone / ".fleet" / "fork_checkpoints" / "p1.a1.db"
    assert stamped.is_file()
    assert (seed / "opencode" / "opencode.db").read_bytes() == stamped.read_bytes()
    assert prepared["fork"]["db_path"].endswith("/.fleet/fork_checkpoints/p1.a1.db")
    assert built["command"]  # the sibling command still builds


def test_fork_checkpoint_missing_refuses_before_launch(tmp_path):
    """Declared-but-missing never degrades to a fresh session: it raises, no request built."""
    import pytest

    clone = tmp_path / "runs" / "run-abc" / "repo"
    clone.mkdir(parents=True)
    executor = _executor(run_clone=str(clone))
    request = _request()
    request.phase_def = {"scope": "implementation", "fork_checkpoint": str(tmp_path / "nope")}
    with pytest.raises(RuntimeError, match="no session db"):
        executor.build_request(request)
