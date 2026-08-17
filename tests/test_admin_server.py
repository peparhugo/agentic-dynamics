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

    def __init__(self, *, statuses=None, results=None, logs=None, messages=None, phases=None):
        self.statuses = statuses or {}
        self.results = results or {}
        self.logs = logs or {}
        self.phases = phases or {}
        self.pubsub_client = FakePubSub(messages)
        self.requested_logs = []

    def llen(self, key):
        assert key == "story_jobs"
        return 2

    def hgetall(self, key):
        if key == "story_status":
            return self.statuses
        if key == "story_phase":
            return self.phases
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


class QueuePipeline:
    """Model the atomic delete+rpush transaction used by queue reinterleave."""

    def __init__(self, redis):
        self._redis = redis
        self._deleted = []
        self._rpushes = []

    def delete(self, key):
        self._deleted.append(key)
        return self

    def rpush(self, key, value):
        self._rpushes.append((key, value))
        return self

    def execute(self):
        for key in self._deleted:
            self._redis.queue = []
        for key, value in self._rpushes:
            self._redis.queue.append(value)


class QueueRedis(FakeRedis):
    """Extend FakeRedis with a story_jobs list plus idempotency ops."""

    def __init__(self, *, queue=None, **kwargs):
        super().__init__(**kwargs)
        self.queue = list(queue or [])
        self.values = {}

    def lrange(self, key, start, end):
        if key == "story_jobs":
            assert (start, end) == (0, -1)
            return self.queue
        return super().lrange(key, start, end)

    def pipeline(self, transaction=False):
        if transaction:
            return QueuePipeline(self)
        return super().pipeline(transaction=transaction)

    def set(self, key, value, *, nx=False, ex=None):
        assert ex is not None
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def get(self, key):
        return self.values.get(key)


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


def test_matrix_surfaces_live_workflow_phases(monkeypatch):
    """The ``story_phase`` hash renders as a badge map; malformed entries are dropped."""
    redis = FakeRedis(
        statuses={"alpha": "running"},
        phases={
            "alpha": json.dumps({"name": "rerun_contaminated", "index": 4, "total": 7}),
            "beta": "not-json",
            "gamma": json.dumps({"index": 2, "total": 3}),  # no name -> dropped
        },
    )
    monkeypatch.setattr(server, "_redis", lambda: redis)

    body = server.app.test_client().get("/api/matrix").get_json()

    assert body["phases"] == {"alpha": {"name": "rerun_contaminated", "index": 4, "total": 7}}


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


def _queue_cell(model: str, cell_id: str) -> str:
    """Serialize one queued job the way enqueue.py does (head->tail LPUSH)."""
    return json.dumps({"model": model, "cell_id": cell_id, "story": "task_manager_api"})


def test_queue_reinterleave_spreads_providers_and_preserves_jobs(monkeypatch):
    """The endpoint round-robins providers and never loses or duplicates a job.

    The fake queue holds cells in Redis head->tail order (as LPUSH stores them).
    ``_read_queue`` reads that and reverses for consumption order, exactly like
    the worker's BRPOP. The fixture has a same-provider run at the consumption
    tail (two openai cells back-to-back) so the reorder is observable.
    """
    queue = [
        _queue_cell("openai/gpt-5.6-luna", "openai_a"),
        _queue_cell("openai/gpt-5.6-luna", "openai_b"),
        _queue_cell("deepseek/deepseek-v4-flash", "deepseek_a"),
        _queue_cell("anthropic/claude-haiku-4-5", "anthropic_a"),
        _queue_cell("anthropic/claude-sonnet-5", "anthropic_b"),
        _queue_cell("openai/gpt-5.6-sol", "openai_c"),
    ]
    redis = QueueRedis(queue=queue)
    monkeypatch.setattr(server, "_redis", lambda: redis)

    response = server.app.test_client().post(
        "/api/queue/reinterleave",
        json={},
        headers={"Idempotency-Key": "reinterleave-1"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["count"] == 6

    # Consumption order (tail-first, i.e. reversed head->tail) after reorder
    # must have no two adjacent cells sharing a provider.
    after_order = body["after"]["order"]
    for left, right in zip(after_order, after_order[1:]):
        assert left != right, f"adjacent same-provider cells: {left}, {right}"

    # The queue still holds exactly the same cell ids (no loss, no duplication).
    before_ids = sorted(json.loads(cell)["cell_id"] for cell in queue)
    after_ids = sorted(json.loads(cell)["cell_id"] for cell in redis.queue)
    assert len(after_ids) == len(before_ids) == 6
    assert after_ids == before_ids


def test_queue_reinterleave_idempotent_replay_does_not_rewrite(monkeypatch):
    """Replaying the same Idempotency-Key returns the cached result unchanged.

    A second identical POST must not re-read/reorder the (already reordered)
    queue; it replays the reserved response, preserving the idempotency
    contract that other Control Room mutations honor.
    """
    queue = [
        _queue_cell("openai/gpt-5.6-luna", "openai_a"),
        _queue_cell("deepseek/deepseek-v4-flash", "deepseek_a"),
        _queue_cell("anthropic/claude-haiku-4-5", "anthropic_a"),
    ]
    redis = QueueRedis(queue=queue)
    monkeypatch.setattr(server, "_redis", lambda: redis)
    client = server.app.test_client()
    headers = {"Idempotency-Key": "reinterleave-replay"}

    first = client.post("/api/queue/reinterleave", json={}, headers=headers)
    snapshot_after_first = list(redis.queue)
    replay = client.post("/api/queue/reinterleave", json={}, headers=headers)

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.get_json() == first.get_json()
    assert list(redis.queue) == snapshot_after_first


def test_queue_reinterleave_requires_idempotency_header(monkeypatch):
    """The route exists and enforces the server's mutation conventions."""
    redis = QueueRedis(queue=[])
    monkeypatch.setattr(server, "_redis", lambda: redis)

    # Registered (not 404) but rejected because the body-validation convention
    # requires an Idempotency-Key header on mutating POSTs.
    response = server.app.test_client().post("/api/queue/reinterleave", json={})

    assert response.status_code == 400
