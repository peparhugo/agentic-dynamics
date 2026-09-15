"""Regression tests for opencode event schema normalization.

Verifies that normalize_opencode_event correctly handles both v1 (historical)
and v2 (current) opencode event formats, producing a canonical representation.
"""

import json
import logging
import subprocess
from pathlib import Path

from agentic_dynamics.adapters.opencode import (
    WORKER_AGENT,
    SnapshotSkipped,
    _build_opencode_cmd,
    _capture_git_baseline,
    _diff_workdir,
    _init_git_workdir,
    _list_files,
    normalize_opencode_event,
)

# ── v1 format (historical — flat structure, no "part" key) ───────────────────


def test_v1_reasoning_event():
    raw = {"type": "reasoning", "text": "Let me think about this..."}
    ev = normalize_opencode_event(raw)
    assert ev["type"] == "reasoning"
    assert ev["text"] == "Let me think about this..."
    assert ev["_schema"] == 1


def test_v1_tool_event():
    raw = {
        "type": "tool",
        "tool": "write",
        "state": {"status": "completed", "input": {"path": "app.py", "content": "..."}},
    }
    ev = normalize_opencode_event(raw)
    assert ev["type"] == "tool"
    assert ev["tool"] == "write"
    assert ev["_schema"] == 1
    assert ev["state"]["status"] == "completed"


def test_v1_step_finish_event():
    raw = {
        "type": "step-finish",
        "tokens": {"input": 5000, "output": 2000, "total": 7000, "reasoning": 1000},
        "cost": 0.015,
        "snapshot": "abc123",
    }
    ev = normalize_opencode_event(raw)
    assert ev["type"] == "step-finish"
    assert ev["tokens"]["input"] == 5000
    assert ev["tokens"]["output"] == 2000
    assert ev["_schema"] == 1


def test_v1_step_start_event():
    raw = {"type": "step-start", "snapshot": "abc123"}
    ev = normalize_opencode_event(raw)
    assert ev["type"] == "step-start"
    assert ev["_schema"] == 1


def test_v1_text_event():
    raw = {"type": "text", "text": "Here is the implementation..."}
    ev = normalize_opencode_event(raw)
    assert ev["type"] == "text"
    assert ev["text"] == "Here is the implementation..."
    assert ev["_schema"] == 1


# ── v2 format (current — nested "part" key) ──────────────────────────────────


def test_v2_tool_use_event():
    raw = {
        "type": "tool_use",
        "sessionID": "ses_xxx",
        "part": {
            "type": "tool",
            "tool": "bash",
            "callID": "call_01",
            "state": {"status": "completed", "input": "pytest -q", "output": "10 passed"},
        },
    }
    ev = normalize_opencode_event(raw)
    assert ev["type"] == "tool"
    assert ev["tool"] == "bash"
    assert ev["_schema"] == 2
    assert ev["callID"] == "call_01"
    assert ev["state"]["status"] == "completed"


def test_v2_step_finish_event():
    raw = {
        "type": "step_finish",
        "sessionID": "ses_xxx",
        "part": {
            "tokens": {"total": 8000, "input": 5000, "output": 2000, "reasoning": 1000},
            "cost": 0.015,
        },
    }
    ev = normalize_opencode_event(raw)
    assert ev["type"] == "step-finish"
    assert ev["tokens"]["total"] == 8000
    assert ev["tokens"]["output"] == 2000
    assert ev["cost"] == 0.015
    assert ev["_schema"] == 2


def test_v2_text_event():
    raw = {
        "type": "text",
        "sessionID": "ses_xxx",
        "part": {"type": "text", "text": "Here is the code..."},
    }
    ev = normalize_opencode_event(raw)
    assert ev["type"] == "text"
    assert ev["text"] == "Here is the code..."
    assert ev["_schema"] == 2


def test_v2_step_start_event():
    raw = {
        "type": "step_start",
        "sessionID": "ses_xxx",
        "part": {"type": "step-start"},
    }
    ev = normalize_opencode_event(raw)
    assert ev["type"] == "step-start"
    assert ev["_schema"] == 2


def test_v2_reasoning_event():
    raw = {
        "type": "reasoning",
        "sessionID": "ses_xxx",
        "part": {"type": "reasoning", "text": "Planning the fix..."},
    }
    ev = normalize_opencode_event(raw)
    assert ev["type"] == "reasoning"
    assert ev["text"] == "Planning the fix..."
    assert ev["_schema"] == 2


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_non_dict_returns_error():
    ev = normalize_opencode_event("not a dict")
    assert ev["type"] == "unknown"
    assert ev["_schema"] == 0
    assert "_error" in ev


def test_empty_dict():
    ev = normalize_opencode_event({})
    assert ev["_schema"] == 1  # no part → detected as v1
    assert ev["type"] == ""


def test_v1_unknown_type_passthrough():
    raw = {"type": "some_custom_event", "data": "foo"}
    ev = normalize_opencode_event(raw)
    assert ev["type"] == "some_custom_event"
    assert ev["_schema"] == 1


def test_v2_with_empty_part():
    raw = {"type": "tool_use", "part": {}}
    ev = normalize_opencode_event(raw)
    assert ev["type"] == "tool"
    assert ev["tool"] == ""


def test_v1_preserves_timestamp():
    raw = {"type": "tool", "tool": "read", "timestamp": 1700000000000}
    ev = normalize_opencode_event(raw)
    assert ev["timestamp"] == 1700000000000


# ── Round-trip compatibility with trajectory analyzer ────────────────────────


def test_v1_event_recognized_by_trajectory_parser():
    """Simulate the trajectory analyzer's event dispatch on v1 normalized events."""
    raw = {"type": "tool", "tool": "write", "state": {}}
    ev = normalize_opencode_event(raw)

    # This is what the trajectory analyzer does:
    if ev["type"] == "tool":
        tool = ev.get("tool", "unknown")
        assert tool == "write"


def test_v2_tool_use_recognized_by_trajectory_parser():
    """A v2 tool_use event normalizes to v1-compatible 'tool' type."""
    raw = {
        "type": "tool_use",
        "part": {"type": "tool", "tool": "bash", "state": {"status": "completed"}},
    }
    ev = normalize_opencode_event(raw)

    if ev["type"] == "tool":
        tool = ev.get("tool", "unknown")
        assert tool == "bash"
        assert True  # would be counted


def test_both_formats_produce_same_canonical_tool_signature():
    """v1 and v2 events for the same tool call should normalize identically."""
    v1 = {"type": "tool", "tool": "read"}
    v2 = {"type": "tool_use", "part": {"type": "tool", "tool": "read"}}

    ev1 = normalize_opencode_event(v1)
    ev2 = normalize_opencode_event(v2)

    assert ev1["type"] == ev2["type"] == "tool"
    assert ev1["tool"] == ev2["tool"] == "read"
    # Schema versions differ but canonical fields match
    assert ev1["_schema"] == 1
    assert ev2["_schema"] == 2


# ── git workdir initialization hygiene (docs/routing_next_steps.md item 5.2) ──


def _git_rev_parse_head(path: Path) -> bool:
    return (
        subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True).returncode == 0
    )


def test_init_git_workdir_is_a_noop_when_history_exists(tmp_path):
    """An already-committed worktree must not gain a misnamed "Initial" commit."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "a@a"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "a"], cwd=tmp_path, check=True)
    (tmp_path / "file.txt").write_text("content")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "real"], cwd=tmp_path, check=True)
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()

    _init_git_workdir(str(tmp_path))

    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True
    ).stdout
    assert head_after == head_before  # no new commit was created
    assert "Initial" not in log


def test_init_git_workdir_skips_empty_initial_commit(tmp_path):
    """A fresh, empty worktree initializes with config but no empty "Initial" commit."""
    _init_git_workdir(str(tmp_path))

    assert _git_rev_parse_head(tmp_path) is False  # nothing staged → no commit
    email = subprocess.run(
        ["git", "config", "user.email"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    assert email == "experiment@instrument.local"  # runner identity still set for the new repo


# ── files_modified is the CHANGED-set, not the pre-existing-set (degradation review 3b.2) ──


def test_diff_workdir_reports_changed_set_not_preexisting_set(tmp_path):
    """A file that existed before the run but was untouched must NOT be "modified"."""
    (tmp_path / "keep.py").write_text("v1")
    (tmp_path / "mod.py").write_text("old")
    (tmp_path / "gone.py").write_text("x")

    before = _list_files(str(tmp_path))

    (tmp_path / "mod.py").write_text("new content")  # changed
    (tmp_path / "keep.py").write_text("v1")  # rewritten identically → not modified
    (tmp_path / "gone.py").unlink()  # deleted → not listed
    (tmp_path / "new.py").write_text("y")  # created

    created, modified = _diff_workdir(str(tmp_path), before)

    assert created == ["new.py"]
    assert modified == ["mod.py"]
    assert "keep.py" not in modified  # the pre-existing-set bug would list it
    assert "gone.py" not in modified


# ── workdir snapshot cap + honest degradation (adapter_snapshot_guard) ─────────


def test_list_files_skips_hashing_above_cap(tmp_path, monkeypatch, caplog):
    """A tree above the cap is not hashed and reports the named degradation.

    Proof of "not hashed" is structural: the walk stops at ``cap + 1`` files, so a
    150-file tree under a cap of 100 observes exactly 101 — it never walks the rest.
    """
    monkeypatch.setenv("FINOPS_ADAPTER_MAX_SNAPSHOT_FILES", "100")
    for i in range(150):
        (tmp_path / f"f{i:04d}.py").write_text("x")

    with caplog.at_level(logging.WARNING):
        snapshot = _list_files(str(tmp_path))

    assert isinstance(snapshot, SnapshotSkipped)  # distinguishable from a real empty dict
    assert not isinstance(snapshot, dict)
    assert snapshot.cap == 100
    assert snapshot.observed == 101  # stopped at cap+1, never walked the whole tree
    assert (
        "workdir snapshot skipped: 101 files > cap "
        "(FINOPS_ADAPTER_MAX_SNAPSHOT_FILES)" in caplog.text
    )


def test_diff_workdir_falls_back_to_git_when_snapshot_skipped(tmp_path, monkeypatch):
    """A skipped snapshot yields the changed set from ``git status`` — a PARTIAL observation."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "a@a"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "a"], cwd=tmp_path, check=True)
    (tmp_path / "tracked.py").write_text("v1")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    monkeypatch.setenv("FINOPS_ADAPTER_MAX_SNAPSHOT_FILES", "1")
    before = _list_files(str(tmp_path))
    assert isinstance(before, SnapshotSkipped)

    (tmp_path / "tracked.py").write_text("v2")  # modified
    (tmp_path / "untracked.py").write_text("new")  # created

    diff = _diff_workdir(str(tmp_path), before)

    assert diff.detection == "git_status"
    assert diff.partial is True  # the narrower observation — explicitly marked
    assert "tracked.py" in diff.modified
    assert "untracked.py" in diff.created


def test_diff_workdir_reports_unavailable_when_git_cannot_answer(tmp_path, monkeypatch):
    """Skipped snapshot + no git → the empty lists are "unavailable", not "no changes"."""
    monkeypatch.setenv("FINOPS_ADAPTER_MAX_SNAPSHOT_FILES", "0")
    (tmp_path / "a.py").write_text("x")  # /tmp is not a git repo

    before = _list_files(str(tmp_path))
    assert isinstance(before, SnapshotSkipped)

    diff = _diff_workdir(str(tmp_path), before)

    assert diff.detection == "unavailable"
    assert diff.partial is True
    assert diff.created == [] and diff.modified == []


def test_diff_workdir_under_cap_behaves_exactly_as_today(tmp_path, monkeypatch):
    """Below the cap the hashed comparison is unchanged (and tagged as such)."""
    monkeypatch.setenv("FINOPS_ADAPTER_MAX_SNAPSHOT_FILES", "10000")
    (tmp_path / "keep.py").write_text("v1")
    (tmp_path / "mod.py").write_text("old")

    before = _list_files(str(tmp_path))
    assert isinstance(before, dict)  # a real snapshot, not a sentinel

    (tmp_path / "mod.py").write_text("new")
    (tmp_path / "keep.py").write_text("v1")  # identically rewritten → untouched
    (tmp_path / "new.py").write_text("y")

    diff = _diff_workdir(str(tmp_path), before)

    assert diff.detection == "hashed"
    assert diff.partial is False
    assert diff.created == ["new.py"]
    assert diff.modified == ["mod.py"]
    assert "keep.py" not in diff.modified


# ── git BASELINE fallback: `git status` is not a before/after diff (finding 8b) ──


def _init_test_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "a@a"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "a"], cwd=tmp_path, check=True)


def test_git_baseline_diff_sees_a_change_committed_during_the_attempt(tmp_path, monkeypatch):
    """A modified file COMMITTED during the attempt must not become an empty changed set.

    ``git status`` is clean after the commit; the baseline comparison still names the file,
    as ``detection="git_baseline"`` (the full observation). Without a baseline, status alone
    is clean — but that narrower observation is explicitly ``partial``, never an ordinary
    empty set.
    """
    _init_test_repo(tmp_path)
    (tmp_path / "source.py").write_text("v1")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    baseline = _capture_git_baseline(str(tmp_path))
    assert baseline is not None and baseline.head

    monkeypatch.setenv("FINOPS_ADAPTER_MAX_SNAPSHOT_FILES", "0")
    before = _list_files(str(tmp_path))
    assert isinstance(before, SnapshotSkipped)

    (tmp_path / "source.py").write_text("v2")  # modified and committed during the attempt
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "change"], cwd=tmp_path, check=True)

    diff = _diff_workdir(str(tmp_path), before, baseline=baseline)

    assert diff.detection == "git_baseline"
    assert diff.partial is False
    assert "source.py" in diff.modified  # the change is NOT lost

    # The narrower observation the defect was about: status is clean, but it is marked
    # partial — an empty list no longer masquerades as a measured "no changes".
    narrow = _diff_workdir(str(tmp_path), before)
    assert narrow.detection == "git_status"
    assert narrow.partial is True
    assert narrow.modified == []


def test_git_baseline_handles_initial_dirty_and_untracked_state(tmp_path, monkeypatch):
    """Pre-existing dirty/untracked files are attributed to the attempt only when they CHANGE."""
    _init_test_repo(tmp_path)
    (tmp_path / "tracked.py").write_text("v1")
    (tmp_path / "dirty.py").write_text("v1")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    # The initial dirty/untracked state BEFORE the attempt starts.
    (tmp_path / "dirty.py").write_text("dirty v1")  # tracked, dirty vs HEAD
    (tmp_path / "untouched_untracked.py").write_text("keep")  # untracked
    (tmp_path / "pre_existing_dir").mkdir()
    (tmp_path / "pre_existing_dir" / "inside.py").write_text("keep")  # untracked dir contents

    baseline = _capture_git_baseline(str(tmp_path))
    assert baseline is not None
    assert "dirty.py" in baseline.dirty_hashes
    assert "untouched_untracked.py" in baseline.dirty_hashes
    assert "pre_existing_dir/inside.py" in baseline.dirty_hashes

    monkeypatch.setenv("FINOPS_ADAPTER_MAX_SNAPSHOT_FILES", "0")
    before = _list_files(str(tmp_path))
    assert isinstance(before, SnapshotSkipped)

    # The attempt: further modifies the baseline-dirty file, creates + commits a new file,
    # leaves the baseline-untracked file untouched.
    (tmp_path / "dirty.py").write_text("dirty v2")
    (tmp_path / "new.py").write_text("new")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "work"], cwd=tmp_path, check=True)

    diff = _diff_workdir(str(tmp_path), before, baseline=baseline)

    assert diff.detection == "git_baseline"
    assert "dirty.py" in diff.modified  # pre-existing dirt, but changed further during the turn
    assert "new.py" in diff.created
    # Untouched pre-existing untracked file: NOT this attempt's work.
    assert "untouched_untracked.py" not in diff.created + diff.modified
    # Untouched pre-existing untracked DIRECTORY contents: also not this attempt's work.
    assert "pre_existing_dir/inside.py" not in diff.created + diff.modified


# ── Worker agent pinning (Unit B) ─────────────────────────────────────────────


def test_worker_argv_selects_build_even_with_an_aio_project_default():
    """The project default is the AIO coordinator (``opencode.json``'s ``default_agent``);
    an ordinary worker call must still select the build profile EXPLICITLY — a default alone
    would silently turn every worker cell into a coordinator."""
    config = json.loads((Path(__file__).resolve().parent.parent / "opencode.json").read_text())
    assert config.get("default_agent") == "aio-control", "the project default this pin beats"
    assert WORKER_AGENT == "build"

    cmd = _build_opencode_cmd(model="deepseek/deepseek-v4-flash", workdir="/tmp/wd")
    assert cmd[cmd.index("--agent") + 1] == "build"
    # EVERY ordinary invocation carries the pin, not only the bare flag combination
    full = _build_opencode_cmd(
        model="m", workdir="/tmp/wd", prompt="p", thinking_effort="high",
        session_name="s", session_id="ses_x", fork=True,
    )
    assert full[full.index("--agent") + 1] == "build"
    # a caller-selected specialized profile is preserved
    specialized = _build_opencode_cmd(model="m", workdir="/tmp/wd", agent="instrument-dev")
    assert specialized[specialized.index("--agent") + 1] == "instrument-dev"
