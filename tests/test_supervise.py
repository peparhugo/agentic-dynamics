"""Persistence tests for the flag-only supervisor feeder."""

from __future__ import annotations

import json

from instrument.supervisor import SUPERVISOR_FLAGS_KEY
from scripts import supervise


class FakeRedis:
    """Record hot-list operations while exposing no current stream mapping."""

    def __init__(self):
        self.calls = []

    def hget(self, key, field):
        """Return no mapping for this persistence-only fixture."""
        self.calls.append(("hget", key, field))
        return None

    def lpush(self, key, value):
        """Record the canonical payload appended to the hot list."""
        self.calls.append(("lpush", key, value))

    def ltrim(self, key, start, end):
        """Record the bounded-retention operation."""
        self.calls.append(("ltrim", key, start, end))


def test_emit_flag_appends_file_then_pushes_and_trims_redis(monkeypatch, tmp_path, capsys):
    """Durable JSONL remains first and stdout remains last in the flag path."""
    redis = FakeRedis()
    path = tmp_path / "flags.jsonl"
    monkeypatch.setattr(supervise, "FLAGS_FILE", path)
    monkeypatch.setattr(supervise, "_redis", lambda: redis)
    monkeypatch.setattr(supervise, "now", lambda: "2026-08-14T12:00:00Z")

    supervise.emit_flag(
        {"id": "ses_a", "title": "Investigate retry", "model": {"id": "model/a"}},
        "stalled",
        "No forward progress.",
    )

    persisted = json.loads(path.read_text())
    pushed = next(call for call in redis.calls if call[0] == "lpush")
    assert pushed[1] == SUPERVISOR_FLAGS_KEY
    assert json.loads(pushed[2]) == persisted
    assert ("ltrim", SUPERVISOR_FLAGS_KEY, 0, 199) in redis.calls
    assert "[FLAG] stalled: Investigate retry" in capsys.readouterr().out


def test_emit_flag_keeps_file_and_stdout_when_redis_is_down(monkeypatch, tmp_path, capsys):
    """Framework Redis failure cannot erase the durable assessment."""
    path = tmp_path / "flags.jsonl"
    monkeypatch.setattr(supervise, "FLAGS_FILE", path)
    monkeypatch.setattr(
        supervise,
        "_redis",
        lambda: (_ for _ in ()).throw(RuntimeError("redis down")),
    )

    supervise.emit_flag(
        {"id": "ses_b", "title": "Repair queue", "model": {"id": "model/b"}},
        "off_track",
        "Editing unrelated files.",
    )

    assert json.loads(path.read_text())["session_id"] == "ses_b"
    assert "[FLAG] off_track: Repair queue" in capsys.readouterr().out
