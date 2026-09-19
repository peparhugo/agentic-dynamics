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


# ── isolated conversation forks + the workflow session store ──────────────────────────────

def _seed_data_dir(tmp_path, name="seed-data"):
    """A LIVE seed data dir whose latest write is still in the WAL (the review's case).

    The writer connection stays open (autocheckpoint off) so the WAL genuinely carries the
    late row at snapshot time — exactly the live-source condition the backup API must handle.
    """
    import sqlite3

    seed = tmp_path / name
    (seed / "opencode").mkdir(parents=True)
    db = seed / "opencode" / "opencode.db"
    con = sqlite3.connect(db)
    con.execute("pragma journal_mode=wal")
    con.execute("pragma wal_autocheckpoint=0")
    con.execute("create table session (id text primary key, time_created integer)")
    con.execute("insert into session values ('ses_parent_abc', 5)")
    con.commit()
    con.execute("insert into session values ('ses_late_wal', 9)")  # stays in the WAL
    con.commit()
    assert (seed / "opencode" / "opencode.db-wal").exists()
    return seed, con


def _fork_decl(seed, session="ses_parent_abc"):
    return {"path": str(seed), "session_id": session}


def test_fork_snapshot_is_standalone_and_contains_wal_content(tmp_path):
    """The transported snapshot is a complete db (WAL content included, no sidecars)."""
    import sqlite3

    seed, con = _seed_data_dir(tmp_path)
    clone = tmp_path / "runs" / "run-abc" / "repo"
    clone.mkdir(parents=True)
    executor = _executor(run_clone=str(clone))
    request = _request()
    request.phase_def = {"scope": "implementation", "fork_checkpoint": _fork_decl(seed)}
    executor.build_request(request)

    dest = clone / ".fleet" / "fork_checkpoints" / "p1.a1.db"
    assert dest.is_file()
    assert not (clone / ".fleet" / "fork_checkpoints" / "p1.a1.db-wal").exists()
    con = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
    ids = {r[0] for r in con.execute("select id from session")}
    con.close()
    assert ids == {"ses_parent_abc", "ses_late_wal"}  # the WAL row survived the snapshot
    prepared = json.loads(
        (clone / ".fleet" / "prepared_steps" / "p1.a1.json").read_text(encoding="utf-8")
    )
    assert prepared["fork"]["session_id"] == "ses_parent_abc"
    assert prepared["fork"]["db_path"].endswith("/.fleet/fork_checkpoints/p1.a1.db")
    con.close()


def test_fork_requires_an_explicit_parent_session(tmp_path):
    """A declaration without session_id (or with an absent session) refuses before launch."""
    import pytest

    seed, con = _seed_data_dir(tmp_path)
    clone = tmp_path / "runs" / "run-abc" / "repo"
    clone.mkdir(parents=True)
    executor = _executor(run_clone=str(clone))

    no_session = _request()
    no_session.phase_def = {"scope": "implementation", "fork_checkpoint": {"path": str(seed)}}
    with pytest.raises(RuntimeError, match="explicit parent session_id"):
        executor.build_request(no_session)

    absent = _request()
    absent.phase_def = {"scope": "implementation", "fork_checkpoint": _fork_decl(seed, "ses_nope")}
    with pytest.raises(RuntimeError, match="is not present"):
        executor.build_request(absent)

    missing_src = _request()
    missing_src.phase_def = {
        "scope": "implementation",
        "fork_checkpoint": {"path": str(tmp_path / "nope"), "session_id": "ses_x"},
    }
    with pytest.raises(RuntimeError, match="source missing"):
        executor.build_request(missing_src)
    con.close()


def test_persist_publishes_receipt_and_latest_idempotently(tmp_path, monkeypatch):
    """Per-attempt receipt + latest pointer; identical re-publication is idempotent."""
    import json as _json
    import sqlite3

    import agentic_dynamics.core.paths as core_paths
    import scripts.fleet.docker_executor as de

    run_dir = tmp_path / "runs" / "run-abc"
    clone = run_dir / "repo"
    clone.mkdir(parents=True)
    state_root = tmp_path / "state"
    monkeypatch.setattr(de.spawn_wrapper, "STATE_ROOT", str(state_root), raising=True)
    monkeypatch.setattr(core_paths, "PROJECT_ROOT", tmp_path, raising=True)
    (tmp_path / ".git").mkdir(exist_ok=True)

    ns = state_root / "t" / "run-abc" / "p1" / "a1" / "data" / "opencode"
    ns.mkdir(parents=True)
    db = ns / "opencode.db"
    con = sqlite3.connect(db)
    con.execute("create table session (id text primary key, time_created integer)")
    con.execute("insert into session values ('ses_child_1', 9)")
    con.commit()
    con.close()

    executor = _executor(run_clone=str(clone))
    ref, err = executor._persist_session_state(_request(), session_id="ses_child_1")
    assert ref == "t/run-abc-p1.a1" and err == ""
    store = tmp_path / "experiments" / "results" / "opencode" / "t"
    snapshot = store / "snapshots" / "run-abc-p1.a1.db"
    receipt = store / "receipts" / "run-abc-p1.a1.json"
    latest = store / "latest.json"
    assert snapshot.is_file() and receipt.is_file() and latest.is_file()
    rec = _json.loads(receipt.read_text())
    assert rec["session_id"] == "ses_child_1" and rec["sha256"]
    assert _json.loads(latest.read_text())["attempt_id"] == "run-abc-p1.a1"

    # identical re-publication is idempotent (no error, same bytes)
    ref2, err2 = executor._persist_session_state(_request(), session_id="ses_child_1")
    assert (ref2, err2) == (ref, "")


def test_persist_refuses_different_bytes_at_the_same_identity(tmp_path, monkeypatch):
    """Different bytes at an already-published identity are refused, never silently replaced."""
    import sqlite3

    import pytest

    import agentic_dynamics.core.paths as core_paths
    import scripts.fleet.docker_executor as de

    run_dir = tmp_path / "runs" / "run-abc"
    clone = run_dir / "repo"
    clone.mkdir(parents=True)
    state_root = tmp_path / "state"
    monkeypatch.setattr(de.spawn_wrapper, "STATE_ROOT", str(state_root), raising=True)
    monkeypatch.setattr(core_paths, "PROJECT_ROOT", tmp_path, raising=True)
    (tmp_path / ".git").mkdir(exist_ok=True)

    ns = state_root / "t" / "run-abc" / "p1" / "a1" / "data" / "opencode"
    ns.mkdir(parents=True)
    db = ns / "opencode.db"
    con = sqlite3.connect(db)
    con.execute("create table session (id text primary key, time_created integer)")
    con.execute("insert into session values ('ses_child_1', 9)")
    con.commit()
    con.close()

    executor = _executor(run_clone=str(clone))
    executor._persist_session_state(_request(), session_id="ses_child_1")

    con = sqlite3.connect(db)
    con.execute("insert into session values ('ses_changed', 10)")
    con.commit()
    con.close()
    with pytest.raises(RuntimeError, match="refusing to replace evidence"):
        executor._persist_session_state(_request(), session_id="ses_child_1")


def test_latest_ref_resolves_the_published_checkpoint(tmp_path, monkeypatch):
    """ref: latest:<workflow> resolves to the published snapshot + explicit session."""
    import sqlite3

    import pytest

    import agentic_dynamics.core.paths as core_paths
    import scripts.fleet.docker_executor as de

    run_dir = tmp_path / "runs" / "run-abc"
    clone = run_dir / "repo"
    clone.mkdir(parents=True)
    state_root = tmp_path / "state"
    monkeypatch.setattr(de.spawn_wrapper, "STATE_ROOT", str(state_root), raising=True)
    monkeypatch.setattr(core_paths, "PROJECT_ROOT", tmp_path, raising=True)
    (tmp_path / ".git").mkdir(exist_ok=True)

    ns = state_root / "t" / "run-abc" / "seed" / "a1" / "data" / "opencode"
    ns.mkdir(parents=True)
    db = ns / "opencode.db"
    con = sqlite3.connect(db)
    con.execute("create table session (id text primary key, time_created integer)")
    con.execute("insert into session values ('ses_seed', 1)")
    con.commit()
    con.close()

    executor = _executor(run_clone=str(clone))
    request = _request()
    request.phase_name = "seed"
    executor._persist_session_state(request, session_id="ses_seed")

    snapshot, session, sha = executor._resolve_fork_source({"ref": "latest:t"})
    assert snapshot.is_file() and session == "ses_seed" and sha
    with pytest.raises(RuntimeError, match="no published receipt"):
        executor._resolve_fork_source({"ref": "latest:nope"})
    executor.build_request  # sanity: attribute still exists


def test_store_membership_is_the_checkpoint(tmp_path, monkeypatch):
    """A published snapshot carries the parent session; an absent one refuses at stage time."""
    import sqlite3

    import pytest

    import agentic_dynamics.core.paths as core_paths
    import scripts.fleet.docker_executor as de

    run_dir = tmp_path / "runs" / "run-abc"
    clone = run_dir / "repo"
    clone.mkdir(parents=True)
    state_root = tmp_path / "state"
    monkeypatch.setattr(de.spawn_wrapper, "STATE_ROOT", str(state_root), raising=True)
    monkeypatch.setattr(core_paths, "PROJECT_ROOT", tmp_path, raising=True)
    (tmp_path / ".git").mkdir(exist_ok=True)
    ns = state_root / "t" / "run-abc" / "seed" / "a1" / "data" / "opencode"
    ns.mkdir(parents=True)
    con = sqlite3.connect(ns / "opencode.db")
    con.execute("create table session (id text primary key, time_created integer)")
    con.execute("insert into session values ('ses_seed', 1)")
    con.commit()
    con.close()
    executor = _executor(run_clone=str(clone))
    seed_request = _request()
    seed_request.phase_name = "seed"
    executor._persist_session_state(seed_request, session_id="ses_seed")

    branch = _request()
    branch.phase_def = {"scope": "research_readonly", "fork_checkpoint": {"ref": "latest:t"}}
    executor.build_request(branch)  # resolves, snapshots into the clone, stamps
    prepared = json.loads(
        (clone / ".fleet" / "prepared_steps" / "p1.a1.json").read_text(encoding="utf-8")
    )
    assert prepared["fork"]["session_id"] == "ses_seed"

    wrong = _request()
    wrong.phase_def = {"scope": "research_readonly", "fork_checkpoint": {"ref": "latest:nope"}}
    with pytest.raises(RuntimeError, match="no published receipt"):
        executor.build_request(wrong)
