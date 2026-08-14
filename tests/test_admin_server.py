"""Contract tests for the Flask Control Room backend."""

from __future__ import annotations

import json

from admin import server


class FakePubSub:
    """Small deterministic Redis Pub/Sub stand-in for SSE generator tests."""

    def __init__(self, messages=None):
        self.messages = list(messages or [])
        self.subscriptions = []
        self.unsubscriptions = []
        self.closed = False

    def subscribe(self, channel):
        self.subscriptions.append(channel)

    def get_message(self, **_kwargs):
        if self.messages:
            return self.messages.pop(0)
        raise GeneratorExit

    def unsubscribe(self, channel):
        self.unsubscriptions.append(channel)

    def close(self):
        self.closed = True


class FakeRedis:
    """Implement only the Redis operations used by the admin routes."""

    def __init__(self, *, statuses=None, results=None, logs=None, messages=None):
        self.statuses = statuses or {}
        self.results = results or {}
        self.logs = logs or {}
        self.pubsub_client = FakePubSub(messages)
        self.requested_logs = []

    def llen(self, key):
        assert key == "story_jobs"
        return 2

    def hgetall(self, key):
        if key == "story_status":
            return self.statuses
        assert key == "story_results"
        return self.results

    def lrange(self, key, start, end):
        assert (start, end) == (0, -1)
        self.requested_logs.append(key)
        return self.logs.get(key, [])

    def pubsub(self):
        return self.pubsub_client

    def pipeline(self, transaction=False):
        assert transaction is False
        return FakePipeline(self)


class FakePipeline:
    """Record pipelined log reads and replay their per-key results in order."""

    def __init__(self, redis):
        self._redis = redis
        self._keys = []

    def lrange(self, key, start, end):
        assert (start, end) == (0, -1)
        self._redis.requested_logs.append(key)
        self._keys.append(key)
        return self

    def execute(self):
        return [self._redis.logs.get(key, []) for key in self._keys]


def _step(cost=None, input_tokens=None, output_tokens=None, **extra):
    """Return a realistic serialized ``step_finish`` event for fixtures."""
    part = {"tokens": {"input": input_tokens, "output": output_tokens}, "cost": cost}
    return json.dumps({"type": "step_finish", "part": part, **extra})


def test_matrix_preserves_legacy_fields_and_adds_retained_telemetry(monkeypatch):
    """The telemetry extension must not change baseline matrix semantics."""
    redis = FakeRedis(
        statuses={"alpha": "running", "beta": "done", "odd": "new-state"},
        results={"beta": "result.json"},
        logs={
            # Redis stores newest first; the endpoint returns ordered samples.
            "events_log:alpha": [
                _step(0.02, 20, 4, sessionID="s1", timestamp="2026-08-14T12:00:02Z"),
                _step(0.01, 10, 2, sessionID="s1", timestamp="2026-08-14T12:00:01Z"),
            ],
            "events_log:beta": [json.dumps({"type": "text", "part": {"text": "done"}})],
        },
    )
    monkeypatch.setattr(server, "_redis", lambda: redis)

    response = server.app.test_client().get("/api/matrix")

    assert response.status_code == 200
    body = response.get_json()
    assert {key: body[key] for key in (
        "total", "remaining_in_queue", "queued", "running", "done", "failed",
        "timeout", "completed", "results_saved", "cells",
    )} == {
        "total": 3,
        "remaining_in_queue": 2,
        "queued": 0,
        "running": 1,
        "done": 1,
        "failed": 0,
        "timeout": 0,
        "completed": 1,
        "results_saved": 1,
        "cells": {"alpha": "running", "beta": "done", "odd": "new-state"},
    }
    telemetry = body["telemetry"]
    assert telemetry["provenance"] == "retained_window"
    assert telemetry["partial"] is True
    assert telemetry["reported_cost"] == 0.03
    assert telemetry["input_tokens"] == 30
    assert telemetry["output_tokens"] == 6
    assert [sample["cost"] for sample in telemetry["cells"]["alpha"]["samples"]] == [0.01, 0.02]
    assert redis.requested_logs == ["events_log:alpha", "events_log:beta", "events_log:odd"]


def test_matrix_ignores_invalid_telemetry_but_preserves_reported_zero(monkeypatch):
    """Invalid data is unavailable; an explicitly reported zero remains data."""
    invalid = [
        _step("0.4", "12", -1),
        _step(-0.1, float("nan"), float("inf")),
        "not-json",
    ]
    zero = _step(0, 0, 0)
    redis = FakeRedis(statuses={"alpha": "running", "empty": "queued"}, logs={
        "events_log:alpha": invalid + [zero],
    })
    monkeypatch.setattr(server, "_redis", lambda: redis)

    telemetry = server.app.test_client().get("/api/matrix").get_json()["telemetry"]

    assert telemetry["reported_cost"] == 0
    assert telemetry["input_tokens"] == 0
    assert telemetry["output_tokens"] == 0
    assert telemetry["cost_samples"] == 1
    assert telemetry["cells"]["empty"]["reported_cost"] is None
    assert telemetry["cells"]["empty"]["samples"] == []


def test_matrix_redis_failure_keeps_existing_503_contract(monkeypatch):
    """Redis startup failures retain the established response shape."""
    monkeypatch.setattr(server, "_redis", lambda: (_ for _ in ()).throw(RuntimeError("down")))

    response = server.app.test_client().get("/api/matrix")

    assert response.status_code == 503
    assert response.get_json() == {"error": "redis_unavailable", "cells": {}}


def test_event_stream_replays_in_order_then_marks_live_boundary(monkeypatch):
    """The additive boundary separates retained samples from burn-rate data."""
    redis = FakeRedis(
        logs={"events_log:alpha": ["new", "old"]},
        messages=[{"data": "live"}],
    )
    monkeypatch.setattr(server, "_redis", lambda: redis)
    response = server.app.test_client().get("/api/events/alpha", buffered=False)
    iterator = iter(response.response)

    assert next(iterator).decode() == "data: old\n\n"
    assert next(iterator).decode() == "data: new\n\n"
    boundary = next(iterator).decode()
    assert boundary.startswith("event: replay_complete\ndata: ")
    assert json.loads(boundary.split("data: ", 1)[1]) == {"cell_id": "alpha"}
    assert next(iterator).decode() == "data: live\n\n"
    assert redis.pubsub_client.subscriptions == ["events:alpha"]
    response.close()
    assert redis.pubsub_client.unsubscriptions == ["events:alpha"]
    assert redis.pubsub_client.closed is True


def test_index_and_existing_static_asset_routes_remain_available():
    """The single-page redesign retains the established static routes."""
    client = server.app.test_client()

    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_matrix_pipeline_failure_keeps_telemetry_additive(monkeypatch):
    """A whole-connection pipeline failure degrades without dropping the matrix."""
    class FailingPipeline:
        def lrange(self, _key, _start, _end):
            return self

        def execute(self):
            raise RuntimeError("connection lost")

    class PipelineRedis(FakeRedis):
        def pipeline(self, transaction=False):
            assert transaction is False
            return FailingPipeline()

    redis = PipelineRedis(statuses={"alpha": "running"})
    monkeypatch.setattr(server, "_redis", lambda: redis)

    response = server.app.test_client().get("/api/matrix")

    assert response.status_code == 200
    telemetry = response.get_json()["telemetry"]
    assert telemetry["available"] is False
    assert telemetry["history_capped"] is False
    assert telemetry["cells"]["alpha"]["samples"] == []


def test_matrix_flags_history_capped_when_window_full(monkeypatch):
    """A cell at the retained-window bound surfaces the fleet truncation flag."""
    monkeypatch.setattr(server, "EVENT_LOG_MAX", 3)
    redis = FakeRedis(
        statuses={"alpha": "running"},
        logs={"events_log:alpha": [_step(0.01, 1, 1) for _ in range(3)]},
    )
    monkeypatch.setattr(server, "_redis", lambda: redis)

    telemetry = server.app.test_client().get("/api/matrix").get_json()["telemetry"]

    assert telemetry["history_capped"] is True
    assert telemetry["cells"]["alpha"]["history_capped"] is True


def test_matrix_history_capped_false_when_window_open(monkeypatch):
    """The fleet truncation flag stays false when no cell has hit the bound."""
    monkeypatch.setattr(server, "EVENT_LOG_MAX", 3)
    redis = FakeRedis(
        statuses={"alpha": "running"},
        logs={"events_log:alpha": [_step(0.01, 1, 1) for _ in range(2)]},
    )
    monkeypatch.setattr(server, "_redis", lambda: redis)

    telemetry = server.app.test_client().get("/api/matrix").get_json()["telemetry"]

    assert telemetry["history_capped"] is False
