"""Persistence tests for the flag-only supervisor feeder."""

from __future__ import annotations

import json

from agentic_dynamics.control.supervisor import SUPERVISOR_FLAGS_KEY
from agentic_dynamics.knowledge import knowledge_stream as ks
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


# ── canonical-state round 2, plan step 13: registry emission ────


def test_emit_flag_also_registers_flag_record(monkeypatch, tmp_path):
    """FINOPS_KB_WRITE-gated: emit_flag() also publishes a source_type=flag record to
    the SEPARATE DB2 knowledge stream, on top of its existing flags.jsonl + hot-list
    writes (which the two tests above already cover and which stay unchanged)."""
    redis = FakeRedis()
    path = tmp_path / "flags.jsonl"
    monkeypatch.setattr(supervise, "FLAGS_FILE", path)
    monkeypatch.setattr(supervise, "_redis", lambda: redis)
    monkeypatch.setattr(supervise, "now", lambda: "2026-08-14T12:00:00Z")
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")

    published = []
    monkeypatch.setattr(ks, "connect", lambda: object())
    monkeypatch.setattr(
        ks, "publish_event",
        lambda r, event, **kw: published.append((event, kw)) or "0-1",
    )

    supervise.emit_flag(
        {"id": "ses_c", "title": "Investigate drift", "model": {"id": "model/c"}},
        "off_track",
        "Diverged from spec.",
    )

    assert len(published) == 1
    event, kwargs = published[0]
    assert kwargs["source_type"] == "flag"
    assert kwargs["authorized"] is True
    # The durable JSONL write is unaffected by the new registry side-channel.
    assert json.loads(path.read_text())["session_id"] == "ses_c"


def test_emit_flag_skips_registration_when_kb_write_unset(monkeypatch, tmp_path):
    redis = FakeRedis()
    path = tmp_path / "flags.jsonl"
    monkeypatch.setattr(supervise, "FLAGS_FILE", path)
    monkeypatch.setattr(supervise, "_redis", lambda: redis)
    monkeypatch.delenv("FINOPS_KB_WRITE", raising=False)

    def _explode():
        raise AssertionError("must not connect to the knowledge stream when KB_WRITE is unset")

    monkeypatch.setattr(ks, "connect", _explode)

    supervise.emit_flag(
        {"id": "ses_d", "title": "Quiet path", "model": {"id": "model/d"}},
        "stalled", "No progress.",
    )
    # No assertion error raised above == no connection attempt was made.


def test_emit_flag_registration_failure_never_blocks_the_flag(monkeypatch, tmp_path, capsys):
    """A downed DB2 knowledge stream must not cost emit_flag() its durable write or
    stdout line — this is the live-loop best-effort trade-off documented inline in
    supervise.py (contrast with story.py:save_story_result, which intentionally lets
    the analogous failure raise)."""
    redis = FakeRedis()
    path = tmp_path / "flags.jsonl"
    monkeypatch.setattr(supervise, "FLAGS_FILE", path)
    monkeypatch.setattr(supervise, "_redis", lambda: redis)
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")
    monkeypatch.setattr(
        ks, "connect", lambda: (_ for _ in ()).throw(RuntimeError("db2 down")),
    )

    supervise.emit_flag(
        {"id": "ses_e", "title": "Still works", "model": {"id": "model/e"}},
        "off_track", "Editing unrelated files.",
    )

    assert json.loads(path.read_text())["session_id"] == "ses_e"
    assert "[FLAG] off_track: Still works" in capsys.readouterr().out


class _FakeStoryStatusRedis:
    """Minimal Redis stand-in for ``supervise_once()``: only ``story_status`` (via
    ``running_cells``) and one cell's ``events_log:*`` list (via ``_cell_activity``) are
    ever read — a different surface than ``FakeRedis`` above, which models the
    framework hot-list client ``emit_flag()`` uses instead."""

    def __init__(self, cell_id: str, activity_lines: list[str]):
        self.cell_id = cell_id
        self.activity_lines = activity_lines

    def hgetall(self, key):
        assert key == "story_status"
        return {self.cell_id: "running"}

    def lrange(self, key, start, end):
        assert key == f"events_log:{self.cell_id}"
        return self.activity_lines


class _FakeMonitorClient:
    """``supervise_once`` only ever calls ``send_input`` on the monitor client — the
    reply itself is harvested through ``read_reply``, monkeypatched directly below."""

    def send_input(self, monitor_id, batch, delivery="queue"):
        pass


def test_supervise_once_registers_every_verdict_including_healthy(monkeypatch):
    # The literal OQ6a assertion: a "healthy" verdict produces NO flags.jsonl line (the
    # emit_flag() gate below is UNCHANGED) but MUST still produce a durable observation
    # record — that's what plan step 13's unconditional registration block exists for.
    cell_id = "wf_task_manager_api_1"
    activity = [json.dumps({"type": "text", "part": {"text": "implementing the endpoint"}})]
    redis_client = _FakeStoryStatusRedis(cell_id, activity)

    monkeypatch.setattr(supervise, "read_reply", lambda *a, **kw: "STATUS: healthy\nWHY: on track")
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")

    published = []
    monkeypatch.setattr(ks, "connect", lambda: object())
    monkeypatch.setattr(
        ks, "publish_event",
        lambda r, event, **kw: published.append((event, kw)) or "0-1",
    )

    flagged = []
    monkeypatch.setattr(supervise, "emit_flag", lambda *a: flagged.append(a))

    supervise.supervise_once(_FakeMonitorClient(), "monitor_1", redis_client)

    # Registered despite being healthy...
    assert len(published) == 1
    assert published[0][1]["source_type"] == "observation"
    # ...and, unchanged, a healthy verdict never reaches emit_flag().
    assert flagged == []


def test_supervise_once_still_flags_non_healthy_verdicts_unchanged(monkeypatch):
    # The flag-emission gate itself (status not in ("healthy", "unknown")) is explicitly
    # UNCHANGED by this round — this is a regression guard for that invariant.
    cell_id = "wf_task_manager_api_2"
    activity = [json.dumps({"type": "text", "part": {"text": "editing unrelated files"}})]
    redis_client = _FakeStoryStatusRedis(cell_id, activity)

    monkeypatch.setattr(supervise, "read_reply", lambda *a, **kw: "STATUS: off_track\nWHY: drifted")
    monkeypatch.delenv("FINOPS_KB_WRITE", raising=False)  # registration path inert here

    flagged = []
    monkeypatch.setattr(supervise, "emit_flag", lambda *a: flagged.append(a))

    supervise.supervise_once(_FakeMonitorClient(), "monitor_1", redis_client)

    assert len(flagged) == 1
    assert flagged[0][1] == "off_track"


def test_supervise_once_skips_registration_when_kb_write_unset(monkeypatch):
    cell_id = "wf_task_manager_api_3"
    activity = [json.dumps({"type": "text", "part": {"text": "still going"}})]
    redis_client = _FakeStoryStatusRedis(cell_id, activity)

    monkeypatch.setattr(supervise, "read_reply", lambda *a, **kw: "STATUS: healthy\nWHY: fine")
    monkeypatch.delenv("FINOPS_KB_WRITE", raising=False)
    monkeypatch.setattr(supervise, "emit_flag", lambda *a: None)

    def _explode():
        raise AssertionError("must not connect to the knowledge stream when KB_WRITE is unset")

    monkeypatch.setattr(ks, "connect", _explode)

    supervise.supervise_once(_FakeMonitorClient(), "monitor_1", redis_client)
    # No assertion error raised above == no connection attempt was made.
