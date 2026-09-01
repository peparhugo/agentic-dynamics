"""Tests for the Redis live-telemetry publisher."""

import json

from agentic_dynamics.control import live as live_module
from agentic_dynamics.control.live import LivePublisher, make_publisher


class FakeRedis:
    def __init__(self):
        self.published = []
        self.logs = {}

    def ping(self):
        return True

    def publish(self, channel, payload):
        self.published.append((channel, payload))

    def lpush(self, key, payload):
        self.logs.setdefault(key, []).insert(0, payload)

    def ltrim(self, key, start, end):
        pass


def test_publisher_disabled_without_cell_id(monkeypatch):
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    pub = LivePublisher(None)
    assert not pub.enabled
    pub.publish_status("running")
    pub.publish_event({"type": "text"})
    assert pub.enabled is False


def test_make_publisher_none_without_env(monkeypatch):
    monkeypatch.delenv("FINOPS_CELL_ID", raising=False)
    assert make_publisher() is None


def test_make_publisher_returns_publisher_with_env(monkeypatch):
    monkeypatch.setenv("FINOPS_CELL_ID", "cell_abc")
    pub = make_publisher()
    assert pub is not None
    assert pub.cell_id == "cell_abc"


def test_publish_status_and_event(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(live_module, "_connect", lambda: fake)
    pub = LivePublisher("cell_abc")
    assert pub.enabled

    pub.publish_status("done")
    pub.publish_event({"type": "text", "part": {"type": "text", "text": "hi"}})

    assert fake.published[0][0] == "status"
    assert json.loads(fake.published[0][1]) == {"cell_id": "cell_abc", "status": "done"}
    assert fake.published[1][0] == "events:cell_abc"
    assert json.loads(fake.published[1][1])["type"] == "text"


def test_set_phase_writes_phase_hash(monkeypatch):
    """The workflow phase badge writes to the ``story_phase`` hash, keyed by cell."""

    class PhaseRedis:
        def __init__(self):
            self.phases = {}

        def ping(self):
            return True

        def hset(self, key, field, value):
            self.phases[(key, field)] = value

    fake = PhaseRedis()
    monkeypatch.setattr(live_module, "_connect", lambda: fake)
    monkeypatch.setattr(live_module, "_phase_stamp", lambda: "2026-09-01T12:00:00Z")
    pub = LivePublisher("cell_abc")

    pub.set_phase({"name": "rerun_contaminated", "index": 4, "total": 7})

    written = json.loads(fake.phases[("story_phase", "cell_abc")])
    assert written["name"] == "rerun_contaminated"
    assert written["index"] == 4 and written["total"] == 7
    # The write carries the server-side published-at stamp the board's live window reads.
    assert written["published_at"] == "2026-09-01T12:00:00Z"


def test_set_phase_stamps_every_write(monkeypatch):
    """Every phase write is stamped, so the board never mistakes stale for fresh."""

    class PhaseRedis:
        def __init__(self):
            self.phases = {}

        def ping(self):
            return True

        def hset(self, key, field, value):
            self.phases[(key, field)] = value

    fake = PhaseRedis()
    monkeypatch.setattr(live_module, "_connect", lambda: fake)
    stamps = iter(["2026-09-01T12:00:00Z", "2026-09-01T12:03:00Z"])
    monkeypatch.setattr(live_module, "_phase_stamp", lambda: next(stamps))
    pub = LivePublisher("cell_abc")

    pub.set_phase({"name": "implement", "index": 1, "total": 3})
    pub.set_phase({"name": "rework", "index": 2, "total": 3})

    first = json.loads(fake.phases[("story_phase", "cell_abc")])
    assert first["published_at"] == "2026-09-01T12:03:00Z"


def test_publish_event_maintains_history_log(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(live_module, "_connect", lambda: fake)
    pub = LivePublisher("cell_abc")

    pub.publish_event({"type": "text"})
    pub.publish_event({"type": "tool_use"})

    assert fake.published[0][0] == "events:cell_abc"
    assert "events_log:cell_abc" in fake.logs
    # newest first in the log
    assert json.loads(fake.logs["events_log:cell_abc"][0])["type"] == "tool_use"


def test_publish_event_persists_before_publish(monkeypatch):
    """A live event must be retained before it is published (M3 ordering)."""
    calls = []

    class OrderingRedis:
        def ping(self):
            return True

        def lpush(self, key, payload):
            calls.append("lpush")

        def ltrim(self, key, start, end):
            calls.append("ltrim")

        def publish(self, channel, payload):
            calls.append("publish")

    monkeypatch.setattr(live_module, "_connect", lambda: OrderingRedis())
    pub = LivePublisher("cell_abc")

    pub.publish_event({"type": "text"})

    assert calls == ["lpush", "ltrim", "publish"]


def test_publisher_disables_after_failure(monkeypatch):
    class FailingRedis:
        def ping(self):
            return True

        def publish(self, channel, payload):
            raise RuntimeError("redis down")

    monkeypatch.setattr(live_module, "_connect", lambda: FailingRedis())
    pub = LivePublisher("cell_abc")
    assert pub.enabled
    pub.publish_status("done")
    assert not pub.enabled
    pub.publish_status("done")
    pub.publish_event({"type": "text"})
