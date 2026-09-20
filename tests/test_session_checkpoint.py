"""The supported operation that freezes a live session into a fork checkpoint.

Contract: extract ONLY the selected conversation (never credentials), verify it, publish it in
the fleet's receipt format — and prove the fork transport's own resolver accepts the result.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scripts.fleet.docker_executor import DockerAgentExecutor, resolve_checkpoint_ref
from scripts.session_checkpoint import extract_session, publish_checkpoint


def _source_db(path: Path, session_id: str = "ses_live_1") -> Path:
    con = sqlite3.connect(path)
    con.execute(
        "create table session (id text primary key, project_id text, workspace_id text, "
        "title text, agent text, time_created integer, time_updated integer)"
    )
    con.execute(
        "create table message (id text primary key, session_id text, time_created integer, data text)"
    )
    con.execute(
        "create table part (id text primary key, message_id text, session_id text, "
        "time_created integer, data text)"
    )
    con.execute("create table project (id text primary key, name text)")
    con.execute("create table project_directory (project_id text, directory text)")
    con.execute("create table workspace (id text primary key)")
    con.execute("create table data_migration (id text primary key, applied integer)")
    con.execute("create table credential (id text primary key, secret text)")
    con.execute(
        "insert into session values ('ses_live_1', 'proj1', null, 'aio run', 'aio-control', 1, 9)"
    )
    con.execute(
        "insert into session values ('ses_other', 'proj1', null, 'other', 'aio-control', 1, 9)"
    )
    con.execute("insert into message values ('m1', 'ses_live_1', 1, '{}')")
    con.execute("insert into message values ('m2', 'ses_other', 1, '{}')")
    con.execute("insert into part values ('p1', 'm1', 'ses_live_1', 1, '{\"type\":\"text\"}')")
    con.execute("insert into part values ('p2', 'm2', 'ses_other', 1, '{}')")
    con.execute("insert into project values ('proj1', 'repo')")
    con.execute("insert into project_directory values ('proj1', '/repo')")
    con.execute("insert into data_migration values ('0001', 1)")
    con.execute("insert into credential values ('c1', 'SUPER-SECRET')")
    con.commit()
    con.close()
    return path


def test_extract_keeps_only_the_selected_session_and_never_credentials(tmp_path):
    src = _source_db(tmp_path / "live.db")
    dest = tmp_path / "freeze.db"
    counts = extract_session(src, "ses_live_1", dest)
    assert counts["session"] == 1 and counts["message"] == 1 and counts["part"] == 1
    con = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
    try:
        assert con.execute("select id from session").fetchall() == [("ses_live_1",)]
        assert con.execute("select count(*) from message where session_id = 'ses_other'").fetchone()[0] == 0
        assert con.execute("select count(*) from credential").fetchone()[0] == 0
        assert con.execute("select secret from credential").fetchall() == []
        assert con.execute("select count(*) from data_migration").fetchone()[0] == 1
    finally:
        con.close()
    with pytest.raises(RuntimeError, match="not found"):
        extract_session(src, "ses_missing", tmp_path / "nope.db")


def test_published_checkpoint_is_accepted_by_the_fork_transport(tmp_path, monkeypatch):
    """End-to-end: live-session freeze -> resolver -> executor staging of a fork phase."""
    import agentic_dynamics.core.paths as core_paths
    import scripts.fleet.docker_executor as de

    monkeypatch.setattr(core_paths, "PROJECT_ROOT", tmp_path, raising=True)
    (tmp_path / ".git").mkdir(exist_ok=True)
    src = _source_db(tmp_path / "live.db")
    snapshot = tmp_path / "snapshot.db"
    extract_session(src, "ses_live_1", snapshot)
    store = tmp_path / "experiments" / "results" / "opencode"
    publish_checkpoint(snapshot, workflow="aio_session", attempt_id="freeze1",
                       session_id="ses_live_1", store=store)

    pinned = resolve_checkpoint_ref("latest:aio_session")
    assert pinned == "aio_session/freeze1"

    clone = tmp_path / "runs" / "run-b1" / "repo"
    clone.mkdir(parents=True)
    state_root = tmp_path / "state"
    monkeypatch.setattr(de.spawn_wrapper, "STATE_ROOT", str(state_root), raising=True)
    executor = DockerAgentExecutor(spec_path="/repo/w.yaml", spec_name="fork_branch", goal="q",
                                   model="m", workdir="/tmp/wt", run_clone=str(clone),
                                   fork_checkpoint=pinned)
    from agentic_dynamics.runtime.executor import StepRequest

    request = StepRequest(phase_name="branch", phase_kind="agent", prompt="q", model="m",
                          goal="q", spec_name="fork_branch", workdir="/tmp/wt",
                          phase_def={"scope": "research_readonly", "fork": True})
    executor.build_request(request)
    prepared = json.loads(
        (clone / ".fleet" / "prepared_steps" / "branch.a1.json").read_text(encoding="utf-8")
    )
    assert prepared["fork"]["session_id"] == "ses_live_1"
