"""Contract tests for the separate Claude background-session poll/relay process."""

from __future__ import annotations

import json

import pytest

from apps.control_room.claude_agents_client import CURSOR_KEY_PREFIX, OWNED_SESSIONS_KEY, ROSTER_KEY
from scripts import claude_agents_supervisor as supervisor_module
from scripts.claude_agents_supervisor import ClaudeAgentsSupervisor


class FakeRedis:
    """In-memory subset of Redis used by the supervisor's roster/cursor writes."""

    def __init__(self, *, owned=None):
        self.owned = set(owned or [])
        self.store: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, dict]] = []

    def smembers(self, key):
        assert key == OWNED_SESSIONS_KEY
        return set(self.owned)

    def set(self, key, value, **kwargs):
        self.store[key] = value
        self.set_calls.append((key, value, kwargs))
        return True

    def get(self, key):
        return self.store.get(key)


class FakeClient:
    """Record subprocess-wrapper calls without shelling out to ``claude``."""

    def __init__(self, *, agents_by_cwd=None, logs_by_id=None):
        self.agents_by_cwd = agents_by_cwd or {}
        self.logs_by_id = logs_by_id or {}
        self.list_calls: list[str] = []
        self.log_calls: list[str] = []

    def list_agents(self, cwd, *, all=True, timeout=15.0):
        self.list_calls.append(cwd)
        return self.agents_by_cwd.get(cwd, [])

    def get_logs(self, session_id, *, timeout=10.0):
        self.log_calls.append(session_id)
        return self.logs_by_id.get(session_id, "")


class FakePublisher:
    """Record publish/status calls in place of a real Redis-backed LivePublisher."""

    instances: list[FakePublisher] = []

    def __init__(self, cell_id):
        self.cell_id = cell_id
        self.enabled = True
        self.events: list[dict] = []
        self.statuses: list[str] = []
        FakePublisher.instances.append(self)

    def set_status(self, status):
        self.statuses.append(status)

    def publish_event(self, event):
        self.events.append(event)


@pytest.fixture(autouse=True)
def _patch_publisher(monkeypatch):
    FakePublisher.instances = []
    monkeypatch.setattr(supervisor_module, "LivePublisher", FakePublisher)
    yield


def _supervisor(*, client=None, redis=None, workdirs=None):
    redis = redis if redis is not None else FakeRedis()
    return ClaudeAgentsSupervisor(
        client=client or FakeClient(), redis_factory=lambda: redis, workdirs=workdirs or ["/tmp/work"]
    ), redis


def test_refresh_roster_merges_by_id_across_workdirs_and_tags_owned():
    client = FakeClient(
        agents_by_cwd={
            "/tmp/a": [{"id": "sess_a", "status": "running"}],
            "/tmp/b": [{"id": "sess_b", "status": "stopped"}],
        }
    )
    supervisor, redis = _supervisor(client=client, workdirs=["/tmp/a", "/tmp/b"], redis=FakeRedis(owned={"sess_a"}))

    roster = supervisor.refresh_roster()

    by_id = {entry["id"]: entry for entry in roster}
    assert by_id["sess_a"]["owned"] is True
    assert by_id["sess_b"]["owned"] is False
    assert json.loads(redis.store[ROSTER_KEY]) == roster
    assert client.list_calls == ["/tmp/a", "/tmp/b"]


def test_refresh_roster_writes_ttl_bound_to_poll_interval(monkeypatch):
    monkeypatch.setattr(supervisor_module, "POLL_INTERVAL", 10.0)
    client = FakeClient(agents_by_cwd={"/tmp/work": [{"id": "sess_a", "status": "running"}]})
    supervisor, redis = _supervisor(client=client)

    supervisor.refresh_roster()

    key, _value, kwargs = redis.set_calls[0]
    assert key == ROSTER_KEY
    assert kwargs["ex"] == 20


def test_refresh_roster_recovers_from_a_failing_workdir(monkeypatch, caplog):
    class FlakyClient(FakeClient):
        def list_agents(self, cwd, *, all=True, timeout=15.0):
            if cwd == "/tmp/bad":
                # Use the exact class the supervisor module imported (it inserts
                # admin/ onto sys.path and imports the bare module name), so
                # ``except ClaudeAgentsError`` there matches this instance.
                raise supervisor_module.ClaudeAgentsError("boom", code="timeout")
            return super().list_agents(cwd, all=all, timeout=timeout)

    client = FlakyClient(agents_by_cwd={"/tmp/good": [{"id": "sess_good", "status": "running"}]})
    supervisor, redis = _supervisor(client=client, workdirs=["/tmp/bad", "/tmp/good"])

    with caplog.at_level("WARNING"):
        roster = supervisor.refresh_roster()

    assert [entry["id"] for entry in roster] == ["sess_good"]


def test_relay_candidates_include_owned_running_and_recently_terminal(monkeypatch):
    monkeypatch.setattr(supervisor_module, "RELAY_GRACE_SECONDS", 120.0)
    supervisor, _redis = _supervisor()
    merged = {
        "sess_running": {"id": "sess_running", "status": "running"},
        "sess_terminal_recent": {
            "id": "sess_terminal_recent",
            "status": "stopped",
            "updated_at": "2026-08-14T11:59:00+00:00",
        },
        "sess_terminal_old": {
            "id": "sess_terminal_old",
            "status": "completed",
            "updated_at": "2020-01-01T00:00:00+00:00",
        },
        "sess_not_owned": {"id": "sess_not_owned", "status": "running"},
    }
    owned = {"sess_running", "sess_terminal_recent", "sess_terminal_old"}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(supervisor_module.time, "time", lambda: 1755172800.0)  # 2025-08-14T12:00:00Z
        candidates = supervisor._relay_candidates(merged, owned)

    ids = {entry["id"] for entry in candidates}
    assert ids == {"sess_running", "sess_terminal_recent"}


def test_reconcile_relays_starts_owned_sessions_and_stops_unwanted_ones(monkeypatch):
    monkeypatch.setattr(
        ClaudeAgentsSupervisor, "_relay_session", lambda self, session_id, stop_event: stop_event.wait()
    )
    supervisor, _redis = _supervisor()

    wanted_ids = supervisor._reconcile_relays([{"id": "sess_a"}, {"id": "sess_b"}])
    assert wanted_ids == {"sess_a", "sess_b"}
    assert set(supervisor._relay_threads) == {"sess_a", "sess_b"}

    # sess_b falls out of the candidate set on the next tick: its thread is signaled to stop.
    supervisor._reconcile_relays([{"id": "sess_a"}])
    stop_event_b = supervisor._relay_stop.get("sess_b")
    assert stop_event_b is None or stop_event_b.is_set()
    supervisor._relay_threads["sess_b"].join(timeout=1)
    assert not supervisor._relay_threads["sess_b"].is_alive()

    # Cleanup: release sess_a's thread too.
    supervisor._relay_stop["sess_a"].set()
    supervisor._relay_threads["sess_a"].join(timeout=1)


def test_reconcile_relays_caps_concurrency_and_logs_overflow_without_dropping_roster(monkeypatch, caplog):
    monkeypatch.setattr(supervisor_module, "MAX_RELAYS", 2)
    monkeypatch.setattr(
        ClaudeAgentsSupervisor, "_relay_session", lambda self, session_id, stop_event: stop_event.wait()
    )
    supervisor, _redis = _supervisor()
    candidates = [{"id": "sess_1"}, {"id": "sess_2"}, {"id": "sess_3"}]

    with caplog.at_level("WARNING"):
        wanted_ids = supervisor._reconcile_relays(candidates)

    assert wanted_ids == {"sess_1", "sess_2"}
    assert "capacity" in caplog.text
    assert "sess_3" in caplog.text

    for session_id in list(supervisor._relay_stop):
        supervisor._relay_stop[session_id].set()
    for thread in supervisor._relay_threads.values():
        thread.join(timeout=1)


def test_refresh_roster_marks_relay_active_and_overflow_sessions_inactive(monkeypatch):
    monkeypatch.setattr(supervisor_module, "MAX_RELAYS", 1)
    monkeypatch.setattr(
        ClaudeAgentsSupervisor, "_relay_session", lambda self, session_id, stop_event: stop_event.wait()
    )
    client = FakeClient(
        agents_by_cwd={
            "/tmp/work": [
                {"id": "sess_1", "status": "running"},
                {"id": "sess_2", "status": "running"},
            ]
        }
    )
    supervisor, redis = _supervisor(client=client, redis=FakeRedis(owned={"sess_1", "sess_2"}))

    roster = supervisor.refresh_roster()

    by_id = {entry["id"]: entry for entry in roster}
    active_count = sum(1 for entry in by_id.values() if entry["relay_active"])
    assert active_count == 1
    assert all(entry["owned"] for entry in by_id.values())

    for session_id in list(supervisor._relay_stop):
        supervisor._relay_stop[session_id].set()
    for thread in supervisor._relay_threads.values():
        thread.join(timeout=1)


def test_relay_once_publishes_only_new_lines_and_advances_cursor():
    client = FakeClient(logs_by_id={"sess_1": "line1\nline2\n"})
    supervisor, redis = _supervisor(client=client)
    publisher = FakePublisher("claude_bg_sess_1")
    cursor_key = f"{CURSOR_KEY_PREFIX}sess_1"

    published = supervisor._relay_once("sess_1", redis, cursor_key, publisher)
    assert published == 2
    assert [event["part"]["text"] for event in publisher.events] == ["line1", "line2"]
    assert redis.store[cursor_key] == "2"

    client.logs_by_id["sess_1"] = "line1\nline2\nline3\n"
    published_again = supervisor._relay_once("sess_1", redis, cursor_key, publisher)
    assert published_again == 1
    assert [event["part"]["text"] for event in publisher.events] == ["line1", "line2", "line3"]
    assert redis.store[cursor_key] == "3"


def test_relay_once_is_a_no_op_when_no_new_lines():
    client = FakeClient(logs_by_id={"sess_1": "line1\n"})
    supervisor, redis = _supervisor(client=client)
    publisher = FakePublisher("claude_bg_sess_1")
    cursor_key = f"{CURSOR_KEY_PREFIX}sess_1"

    supervisor._relay_once("sess_1", redis, cursor_key, publisher)
    published_again = supervisor._relay_once("sess_1", redis, cursor_key, publisher)
    assert published_again == 0
    assert len(publisher.events) == 1


def test_external_sessions_are_never_included_in_relay_candidates():
    supervisor, _redis = _supervisor()
    merged = {"sess_external": {"id": "sess_external", "status": "running"}}
    candidates = supervisor._relay_candidates(merged, owned_ids=set())
    assert candidates == []
