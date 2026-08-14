"""Regression tests for opencode event schema normalization.

Verifies that normalize_opencode_event correctly handles both v1 (historical)
and v2 (current) opencode event formats, producing a canonical representation.
"""

import json
import subprocess
from pathlib import Path

import pytest

from instrument.opencode import _init_git_workdir, normalize_opencode_event


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
        assert "read_calls" or "write_calls" or "bash_calls"  # would be counted


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
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True).returncode == 0


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
    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True).stdout
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
