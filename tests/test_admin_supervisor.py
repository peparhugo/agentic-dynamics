"""Contracts for the human-reviewed supervisor Control Room surface."""

from __future__ import annotations

import json

from agentic_dynamics.control.supervisor import (
    SUPERVISOR_FLAGS_KEY,
    SUPERVISOR_SESSION_CELLS_KEY,
    canonical_json,
    register_session_mapping,
)
from apps.control_room import server


class FakeRedis:
    """Implement the list, hash, and idempotency operations used by the routes."""

    def __init__(self, *, flags=None, mappings=None):
        self.flags = list(flags or [])
        self.mappings = dict(mappings or {})
        self.values = {}

    def lrange(self, key, start, end):
        """Return Redis-list order, which is newest first for supervisor flags."""
        assert key == SUPERVISOR_FLAGS_KEY
        assert start == 0
        return self.flags if end < 0 else self.flags[: end + 1]

    def hget(self, key, field):
        """Read one exact native-session mapping."""
        assert key == SUPERVISOR_SESSION_CELLS_KEY
        return self.mappings.get(field)

    def hset(self, key, field, value):
        """Store one exact mapping for shared-helper tests."""
        assert key == SUPERVISOR_SESSION_CELLS_KEY
        self.mappings[field] = value

    def set(self, key, value, *, nx=False, ex=None):
        """Model the atomic reservation and completed-response cache."""
        assert ex is not None
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def get(self, key):
        """Read one idempotency record."""
        return self.values.get(key)


class FakeOpenCodeClient:
    """Record control calls without connecting to a live OpenCode server."""

    def __init__(self):
        self.steers = []
        self.interrupts = []

    def send_input(self, session_id, prompt, *, delivery):
        """Record exact steer delivery arguments."""
        self.steers.append((session_id, prompt, delivery))
        return {"ok": True}

    def interrupt(self, session_id):
        """Accept an interrupt with the native API's valid empty response."""
        self.interrupts.append(session_id)
        return {}


def _flag(session_id: str, *, at: str, status: str = "off_track", why: str = "Needs review") -> str:
    """Build one canonical persisted six-field assessment."""
    return canonical_json({
        "at": at,
        "session_id": session_id,
        "title": f"Session {session_id}",
        "model": "openai/gpt-5.6-sol",
        "status": status,
        "why": why,
    })


def _mapping(session_id: str, cell_id: str, *, source: str = "publisher_index") -> str:
    """Build one exact current mapping record."""
    return canonical_json({
        "session_id": session_id,
        "cell_id": cell_id,
        "source": source,
        "mapped_at": "2026-08-14T12:00:00Z",
        "last_activity_at": "2026-08-14T12:00:01Z",
    })


def test_flags_api_deduplicates_newest_valid_records_and_maps_review(monkeypatch, tmp_path):
    """Malformed and older assessments cannot displace the newest valid row."""
    redis = FakeRedis(
        flags=[
            "not-json",
            _flag("ses_a", at="2026-08-14T12:03:00Z", why="Newest reason"),
            _flag("ses_b", at="2026-08-14T12:02:00Z", status="novel_status"),
            _flag("ses_a", at="2026-08-14T12:01:00Z", why="Old reason"),
        ],
        mappings={"ses_a": _mapping("ses_a", "wf_a")},
    )
    monkeypatch.setattr(server, "_redis", lambda: redis)
    monkeypatch.setattr(server, "SUPERVISOR_FLAGS_FILE", tmp_path / "missing.jsonl")

    response = server.app.test_client().get("/api/flags?limit=1000")

    assert response.status_code == 200
    body = response.get_json()
    assert body["source"] == "redis"
    assert [flag["session_id"] for flag in body["flags"]] == ["ses_a", "ses_b"]
    assert body["flags"][0]["why"] == "Newest reason"
    assert body["flags"][0]["review"]["cell_id"] == "wf_a"
    assert body["flags"][1]["status"] == "novel_status"
    assert "skipped 1 malformed" in body["warnings"][0]


def test_flags_api_uses_newest_first_bounded_file_fallback(monkeypatch, tmp_path):
    """An empty Redis hot list falls back to reversed append-only JSONL order."""
    path = tmp_path / "flags.jsonl"
    path.write_text("\n".join([
        _flag("ses_a", at="2026-08-14T12:00:00Z", why="Old"),
        _flag("ses_b", at="2026-08-14T12:01:00Z"),
        _flag("ses_a", at="2026-08-14T12:02:00Z", why="New"),
    ]) + "\n")
    monkeypatch.setattr(server, "_redis", lambda: FakeRedis())
    monkeypatch.setattr(server, "SUPERVISOR_FLAGS_FILE", path)

    response = server.app.test_client().get("/api/flags")

    assert response.status_code == 200
    body = response.get_json()
    assert body["source"] == "file"
    assert body["degraded"] is True
    assert [flag["session_id"] for flag in body["flags"]] == ["ses_a", "ses_b"]
    assert body["flags"][0]["why"] == "New"


def test_steer_and_interrupt_require_exact_mapping_and_confirmation(monkeypatch, tmp_path):
    """Only explicit, mapped actions reach the mocked native client."""
    redis = FakeRedis(
        flags=[_flag("ses_a", at="2026-08-14T12:03:00Z")],
        mappings={"ses_a": _mapping("ses_a", "wf_a")},
    )
    opencode = FakeOpenCodeClient()
    monkeypatch.setattr(server, "_redis", lambda: redis)
    monkeypatch.setattr(server, "_opencode_client", lambda: opencode)
    monkeypatch.setattr(server, "SUPERVISOR_FLAGS_FILE", tmp_path / "missing.jsonl")
    client = server.app.test_client()

    steer = client.post(
        "/api/flags/ses_a/steer",
        json={"cell_id": "wf_a", "prompt": "Run the failing test first."},
        headers={"Idempotency-Key": "steer-1"},
    )
    bad_confirmation = client.post(
        "/api/flags/ses_a/interrupt",
        json={"cell_id": "wf_a", "confirmation": "yes"},
        headers={"Idempotency-Key": "interrupt-bad"},
    )
    interrupt = client.post(
        "/api/flags/ses_a/interrupt",
        json={"cell_id": "wf_a", "confirmation": "INTERRUPT ses_a"},
        headers={"Idempotency-Key": "interrupt-1"},
    )

    assert steer.status_code == 200
    assert steer.get_json() == {"action": "steer", "admitted": True, "session_id": "ses_a"}
    assert opencode.steers == [("ses_a", "Run the failing test first.", "steer")]
    assert bad_confirmation.status_code == 400
    assert interrupt.status_code == 200
    assert interrupt.get_json() == {"action": "interrupt", "accepted": True, "session_id": "ses_a"}
    assert opencode.interrupts == ["ses_a"]

    # Replaying an identical mutation returns the cached admission and does not
    # call OpenCode a second time.
    replay = client.post(
        "/api/flags/ses_a/interrupt",
        json={"cell_id": "wf_a", "confirmation": "INTERRUPT ses_a"},
        headers={"Idempotency-Key": "interrupt-1"},
    )
    assert replay.status_code == 200
    assert opencode.interrupts == ["ses_a"]


def test_action_rejects_changed_mapping_before_opencode(monkeypatch, tmp_path):
    """A stale browser cell cannot steer a remapped native session."""
    redis = FakeRedis(
        flags=[_flag("ses_a", at="2026-08-14T12:03:00Z")],
        mappings={"ses_a": _mapping("ses_a", "wf_new")},
    )
    opencode = FakeOpenCodeClient()
    monkeypatch.setattr(server, "_redis", lambda: redis)
    monkeypatch.setattr(server, "_opencode_client", lambda: opencode)
    monkeypatch.setattr(server, "SUPERVISOR_FLAGS_FILE", tmp_path / "missing.jsonl")

    response = server.app.test_client().post(
        "/api/flags/ses_a/steer",
        json={"cell_id": "wf_old", "prompt": "Continue"},
        headers={"Idempotency-Key": "stale-1"},
    )

    assert response.status_code == 409
    assert opencode.steers == []


def test_direct_mapping_takes_precedence_over_supervisor_relay():
    """Relay registration cannot replace a stream owned by a direct publisher."""
    redis = FakeRedis()
    register_session_mapping(redis, "ses_a", "wf_a", source="publisher_index")
    register_session_mapping(redis, "ses_a", "live_a", source="supervisor_relay")

    stored = json.loads(redis.mappings["ses_a"])
    assert stored["cell_id"] == "wf_a"
    assert stored["source"] == "publisher_index"
