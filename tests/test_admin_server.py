"""Contract tests for the Flask Control Room backend."""

from __future__ import annotations

import dataclasses
import functools
import json

import pytest

from agentic_dynamics.control.pipeline_status import review_stage_summary, stage_summary
from apps.control_room import server
from apps.control_room.routes import telemetry as telemetry_routes
from apps.control_room.services.context import ControlRoomServices

# --------------------------------------------------------------------------------------
# The review-stage authority (dependency injection).
#
# ``GET /api/matrix`` does not compute the review population itself; it asks the authority
# injected as ``ControlRoomServices.review_stage_source``. Production binds the file-derived
# ``review_stage_summary`` (the reviews on disk). The tests below bind their OWN authority so
# the route is isolated from the filesystem completely — with no injection these tests would be
# measuring the repo's real experiments/results/reviews/ directory, which is exactly the
# coupling that made them red (they assert a seeded fake-Redis population of 3, while the real
# tree holds hundreds of review files).
# --------------------------------------------------------------------------------------


def _inject_review_source(monkeypatch, source):
    """Bind ``source`` as the review authority the matrix route consults, for one test.

    ``monkeypatch.setattr`` restores the production authority at teardown, so a test that
    injects can never leak its double into the next test.
    """
    monkeypatch.setattr(telemetry_routes._services, "review_stage_source", source)
    return source


def _queue_review_source():
    """A Redis/queue-derived review authority built from the public ``stage_summary``.

    This is the legacy review population — the ``review_jobs`` list plus the ``review_status``
    hash — which the display retired in favour of the files on disk. It remains a perfectly
    valid *authority*: the tests that exercise status folding (retry_N → running) inject it so
    they read the ``FakeRedis`` state they seed rather than the real review directory.
    """
    return functools.partial(stage_summary, queue_key="review_jobs", status_key="review_status")


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

    def __init__(self, *, statuses=None, results=None, logs=None, messages=None,
                 analysis_statuses=None, review_statuses=None,
                 analysis_queue=0, review_queue=0, phases=None):
        self.statuses = statuses or {}
        self.results = results or {}
        self.analysis_statuses = analysis_statuses or {}
        self.review_statuses = review_statuses or {}
        self.analysis_queue = analysis_queue
        self.review_queue = review_queue
        self.logs = logs or {}
        self.phases = phases or {}
        self.pubsub_client = FakePubSub(messages)
        self.requested_logs = []

    def llen(self, key):
        if key == "story_jobs":
            return 2
        if key == "analysis_jobs":
            return self.analysis_queue
        if key == "review_jobs":
            return self.review_queue
        raise AssertionError(f"unexpected llen key: {key}")

    def hgetall(self, key):
        if key == "story_status":
            return self.statuses
        if key == "story_results":
            return self.results
        if key == "analysis_status":
            return self.analysis_statuses
        if key == "review_status":
            return self.review_statuses
        if key == "story_phase":
            return self.phases
        raise AssertionError(f"unexpected hgetall key: {key}")

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
        for _ in self._deleted:
            self._redis.queue = []
        for _, value in self._rpushes:
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
    # The phase is keyed by the same cell id as the fleet status, so the running
    # cell "alpha" carries the badge "4/7 rerun_contaminated".
    assert body["cells"]["alpha"] == "running"
    phase = body["phases"]["alpha"]
    assert phase["index"] == 4 and phase["total"] == 7 and phase["name"] == "rerun_contaminated"


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


def test_matrix_surfaces_three_stage_pipeline(monkeypatch):
    """The matrix exposes execute, analyze, and review as one pipeline view."""
    redis = FakeRedis(
        statuses={"alpha": "running", "beta": "done"},
        results={"beta": "result.json"},
        analysis_statuses={"alpha": "done", "beta": "running"},
        review_statuses={"alpha_S1": "done", "alpha_story": "queued", "beta_S1": "retry_1"},
    )
    monkeypatch.setattr(server, "_redis", lambda: redis)
    # Inject the queue-derived review authority so the review stage reflects the
    # ``review_statuses`` seeded above and nothing on disk.
    _inject_review_source(monkeypatch, _queue_review_source())

    body = server.app.test_client().get("/api/matrix").get_json()

    stages = body["stages"]
    # Flask's JSON_SORT_KEYS default reorders dict keys alphabetically; the
    # client iterates its own fixed stage list, so assert membership, not order.
    assert set(stages) == {"execute", "analyze", "review"}

    # Execute stage keeps the legacy flat fields.
    assert stages["execute"]["total"] == 2
    assert stages["execute"]["running"] == 1
    assert stages["execute"]["results_saved"] == 1

    # Analyze stage has no results hash.
    assert stages["analyze"]["total"] == 2
    assert stages["analyze"]["running"] == 1
    assert stages["analyze"]["done"] == 1
    assert stages["analyze"]["results_saved"] is None

    # Review stage folds retry_N into running and reports the retry count.
    assert stages["review"]["total"] == 3
    assert stages["review"]["retry"] == 1
    assert stages["review"]["running"] == 1
    assert stages["review"]["queued"] == 1
    assert stages["review"]["done"] == 1


def test_matrix_posthoc_queues_report_remaining_and_empty_stages(monkeypatch):
    """Empty post-hoc stages still appear with queue lengths and zero counts."""
    redis = FakeRedis(
        statuses={"alpha": "done"},
        analysis_statuses={},
        review_statuses={},
        analysis_queue=4,
        review_queue=1,
    )
    monkeypatch.setattr(server, "_redis", lambda: redis)
    _inject_review_source(monkeypatch, _queue_review_source())

    stages = server.app.test_client().get("/api/matrix").get_json()["stages"]

    # Execute remains independent of the post-hoc stages.
    assert stages["execute"]["total"] == 1
    assert stages["execute"]["remaining_in_queue"] == 2

    # Analyze: a backlog with no status hash yet (jobs waiting to be picked up).
    assert stages["analyze"]["total"] == 0
    assert stages["analyze"]["remaining_in_queue"] == 4
    assert stages["analyze"]["queued"] == 0
    assert stages["analyze"]["results_saved"] is None
    assert stages["analyze"]["cells"] == {}

    # Review: same shape, its own queue length.
    assert stages["review"]["total"] == 0
    assert stages["review"]["remaining_in_queue"] == 1
    assert stages["review"]["results_saved"] is None


def test_matrix_review_retry_folds_multiple_into_running(monkeypatch):
    """Every retry_N status folds into ``running`` and is counted in ``retry``."""
    redis = FakeRedis(
        statuses={"alpha": "done"},
        review_statuses={"a": "running", "b": "retry_1", "c": "retry_2"},
    )
    monkeypatch.setattr(server, "_redis", lambda: redis)
    _inject_review_source(monkeypatch, _queue_review_source())

    review = server.app.test_client().get("/api/matrix").get_json()["stages"]["review"]

    assert review["retry"] == 2
    assert review["running"] == 3  # 1 running + 2 retries, still in flight
    assert review["total"] == 3
    assert review["done"] == 0


def test_matrix_review_stage_comes_from_the_injected_authority(monkeypatch):
    """PROOF the injection is real: a sentinel authority's payload reaches the response verbatim.

    This asserts *provenance*, not a number. If ``api_matrix`` ever re-acquires a concrete
    review summariser (a hard-wired import, a filesystem read, a Redis read of its own), the
    sentinel payload cannot appear in ``stages.review`` and this test fails.
    """
    redis = FakeRedis(
        statuses={"alpha": "done"},
        # Deliberately non-empty: a route that computed the review stage itself would report
        # these instead of the sentinel below.
        review_statuses={"a": "done", "b": "done", "c": "done"},
    )
    monkeypatch.setattr(server, "_redis", lambda: redis)

    # A payload no real authority could ever produce — the marker proves provenance.
    sentinel = {
        "total": 4242,
        "remaining_in_queue": 0,
        "queued": 0,
        "running": 0,
        "done": 4242,
        "failed": 0,
        "timeout": 0,
        "retry": 0,
        "completed": 4242,
        "results_saved": None,
        "cells": {"authority": "sentinel-not-a-real-source"},
    }
    calls = []

    def sentinel_source(redis_client):
        """Record the client it was handed, then answer with the sentinel population."""
        calls.append(redis_client)
        return sentinel

    _inject_review_source(monkeypatch, sentinel_source)

    review = server.app.test_client().get("/api/matrix").get_json()["stages"]["review"]

    # The response carries the injected authority's answer, byte for byte.
    assert review == sentinel
    # The authority was consulted exactly once, and handed the same Redis client the rest of
    # the route used — the injected source is wired into the real request path, not a bypass.
    assert calls == [redis]


def test_matrix_review_stage_falls_back_to_the_production_file_authority(monkeypatch):
    """PROOF the injection is load-bearing: remove it and the answer changes shape.

    With no test authority injected, the route consults the production one bound by
    ``build_services()`` — the file-derived ``review_stage_summary``, which ignores Redis
    entirely. Its ``cells`` is a ``{reviewed, corpus}`` rollup, whereas the queue-derived
    authority returns the raw ``id -> status`` map. Asserting on that structural difference is
    stable regardless of how many review files the repo happens to hold.
    """
    redis = FakeRedis(
        statuses={"alpha": "done"},
        review_statuses={"a": "running", "b": "retry_1", "c": "retry_2"},
    )
    monkeypatch.setattr(server, "_redis", lambda: redis)
    # NOTE: no _inject_review_source call here — that omission is the point of the test.

    review = server.app.test_client().get("/api/matrix").get_json()["stages"]["review"]

    # The production authority answered: the file-derived rollup shape, not the status map.
    assert set(review["cells"]) == {"reviewed", "corpus"}
    assert review == review_stage_summary(redis)
    # And it is genuinely a different answer from the one the injected authority gives, so the
    # three tests above would fail loudly if their injection were dropped.
    assert review != _queue_review_source()(redis)


def test_control_room_services_requires_a_review_authority():
    """The review authority has no dataclass default — omitting it fails loudly at build time.

    A default would let a route silently re-acquire the real filesystem dependency that the
    injection exists to remove. Construction must raise instead.
    """
    live = telemetry_routes._services
    kwargs = {
        field.name: getattr(live, field.name)
        for field in dataclasses.fields(ControlRoomServices)
    }

    # The full kwargs set still builds a valid context...
    assert isinstance(ControlRoomServices(**kwargs), ControlRoomServices)

    # ...but dropping the review authority is a TypeError, never a silent default.
    kwargs.pop("review_stage_source")
    with pytest.raises(TypeError, match="review_stage_source"):
        ControlRoomServices(**kwargs)


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
    for left, right in zip(after_order, after_order[1:], strict=False):
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


# ── canonical-state round 2, plan step 17: /api/registry* ────────
#
# Both routes are file-only (never Redis, never Neo4j — see api_registry's/
# api_registry_lineage's own docstrings) so these tests monkeypatch
# server.DATA_MANIFEST_PATH to a tmp_path fixture rather than reusing FakeRedis/
# FakePubSub for the data itself; FakeRedis is still the right double for confirming
# these routes touch NO Redis state at all (test_api_registry_never_touches_redis).


def _registry_row(**overrides):
    base = {
        "knowledge_id": "kid_0001",
        "entity_id": "eid_0001",
        "source_type": "story",
        "logical_locator": "story_abc",
        "source_uri": "story:story_abc",
        "lifecycle_state": "current",
        "observed_at": "2026-08-15T00:00:00+00:00",
        "indexed_at": "2026-08-15T00:00:01+00:00",
        "supersedes": None,
        "causes": None,
    }
    base.update(overrides)
    return base


def _write_manifest(path, rows):
    path.write_text(json.dumps({"schema_version": "1.0", "registry": rows}))


def test_api_registry_returns_filtered_table(tmp_path, monkeypatch):
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [
        _registry_row(knowledge_id="kid_story", source_type="story"),
        _registry_row(knowledge_id="kid_review", entity_id="eid_review", source_type="review"),
    ])
    monkeypatch.setattr(server, "DATA_MANIFEST_PATH", manifest_path)

    response = server.app.test_client().get("/api/registry?record_type=story")
    body = response.get_json()

    assert response.status_code == 200
    assert body["count"] == 1
    assert body["registry"][0]["knowledge_id"] == "kid_story"


def test_api_registry_with_no_filters_returns_everything(tmp_path, monkeypatch):
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [
        _registry_row(knowledge_id="kid_a", entity_id="eid_a"),
        _registry_row(knowledge_id="kid_b", entity_id="eid_b"),
    ])
    monkeypatch.setattr(server, "DATA_MANIFEST_PATH", manifest_path)

    body = server.app.test_client().get("/api/registry").get_json()
    assert body["count"] == 2


def test_api_registry_filters_by_lifecycle_and_since(tmp_path, monkeypatch):
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [
        _registry_row(knowledge_id="kid_old", entity_id="eid_old",
                       lifecycle_state="current", observed_at="2026-01-01T00:00:00+00:00"),
        _registry_row(knowledge_id="kid_new", entity_id="eid_new",
                       lifecycle_state="current", observed_at="2026-08-15T00:00:00+00:00"),
        _registry_row(knowledge_id="kid_dead", entity_id="eid_dead",
                       lifecycle_state="tombstoned", observed_at="2026-08-15T00:00:00+00:00"),
    ])
    monkeypatch.setattr(server, "DATA_MANIFEST_PATH", manifest_path)

    body = server.app.test_client().get(
        "/api/registry?lifecycle=current&since=2026-06-01"
    ).get_json()

    assert body["count"] == 1
    assert body["registry"][0]["knowledge_id"] == "kid_new"


def test_api_registry_missing_manifest_returns_empty_table(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA_MANIFEST_PATH", tmp_path / "does_not_exist.json")
    response = server.app.test_client().get("/api/registry")
    body = response.get_json()
    assert response.status_code == 200
    assert body == {"registry": [], "count": 0}


def test_api_registry_never_touches_redis(tmp_path, monkeypatch):
    """Both routes are pure file reads — confirms neither ever calls server._redis()."""
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [_registry_row()])
    monkeypatch.setattr(server, "DATA_MANIFEST_PATH", manifest_path)

    def _explode():
        raise AssertionError("/api/registry* must never connect to Redis")

    monkeypatch.setattr(server, "_redis", _explode)

    client = server.app.test_client()
    assert client.get("/api/registry").status_code == 200
    assert client.get("/api/registry/eid_0001").status_code == 200


def test_api_registry_lineage_returns_the_matched_entity(tmp_path, monkeypatch):
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [_registry_row(entity_id="eid_target")])
    monkeypatch.setattr(server, "DATA_MANIFEST_PATH", manifest_path)

    response = server.app.test_client().get("/api/registry/eid_target")
    body = response.get_json()

    assert response.status_code == 200
    assert body["record"]["entity_id"] == "eid_target"
    assert "causes_record" not in body  # only present for actuation records


def test_api_registry_lineage_renders_causes_for_actuation_records(tmp_path, monkeypatch):
    manifest_path = tmp_path / "data_manifest.json"
    observation = _registry_row(
        knowledge_id="kid_observation_1", entity_id="eid_observation_1",
        source_type="observation", logical_locator="assessment_xyz",
    )
    actuation = _registry_row(
        knowledge_id="kid_actuation_1", entity_id="eid_actuation_1",
        source_type="actuation", logical_locator="actuation_xyz",
        causes="kid_observation_1",
    )
    _write_manifest(manifest_path, [observation, actuation])
    monkeypatch.setattr(server, "DATA_MANIFEST_PATH", manifest_path)

    response = server.app.test_client().get("/api/registry/eid_actuation_1")
    body = response.get_json()

    assert response.status_code == 200
    assert body["record"]["source_type"] == "actuation"
    assert body["causes_record"]["knowledge_id"] == "kid_observation_1"


def test_api_registry_lineage_actuation_with_unresolvable_causes(tmp_path, monkeypatch):
    manifest_path = tmp_path / "data_manifest.json"
    actuation = _registry_row(
        knowledge_id="kid_actuation_2", entity_id="eid_actuation_2",
        source_type="actuation", causes="kid_never_registered",
    )
    _write_manifest(manifest_path, [actuation])
    monkeypatch.setattr(server, "DATA_MANIFEST_PATH", manifest_path)

    body = server.app.test_client().get("/api/registry/eid_actuation_2").get_json()
    assert body["causes_record"] is None


def test_api_registry_lineage_404_when_entity_not_found(tmp_path, monkeypatch):
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [_registry_row(entity_id="eid_a")])
    monkeypatch.setattr(server, "DATA_MANIFEST_PATH", manifest_path)

    response = server.app.test_client().get("/api/registry/does-not-exist")
    assert response.status_code == 404
    assert response.get_json()["error"] == "not_found"


# ── control-room hardening review: F1-F5 ────────────────────────
#
# F1: /api/experiments joins the shared mutation boundary.
# F3: design-session /input validates delivery against a server-side allowlist.
# F2: the 28-route inventory matches the registered url_map.
# F4: /api/registry caches the parsed manifest.
# F5: lineage surfaces ambiguity instead of silently picking the first match.


def test_experiments_requires_idempotency_key():
    """F1: a JSON enqueue body without an Idempotency-Key is rejected at the gate."""
    response = server.app.test_client().post(
        "/api/experiments",
        json={"action": "enqueue"},
    )

    assert response.status_code == 400
    assert "Idempotency-Key" in response.get_json()["error"]


def test_experiments_rejects_non_loopback_remote():
    """F1: the enqueue route is loopback-gated like every other mutation."""
    response = server.app.test_client().post(
        "/api/experiments",
        json={"action": "enqueue"},
        headers={"Idempotency-Key": "exp-remote"},
        environ_overrides={"REMOTE_ADDR": "203.0.113.7"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "loopback access required"


def test_experiments_rejects_unknown_action(monkeypatch):
    """F1: the action allowlist survives the boundary; unknown actions are 400."""
    redis = QueueRedis(queue=[])
    monkeypatch.setattr(server, "_redis", lambda: redis)

    response = server.app.test_client().post(
        "/api/experiments",
        json={"action": "launch_the_missiles"},
        headers={"Idempotency-Key": "exp-bad-action"},
    )

    assert response.status_code == 400
    assert "unknown action" in response.get_json()["error"]


def test_experiments_enqueue_spawns_subprocess(monkeypatch):
    """F1: a gated enqueue still reaches scripts/enqueue.py via subprocess."""
    redis = QueueRedis(queue=[])
    monkeypatch.setattr(server, "_redis", lambda: redis)
    calls = []

    class FakeProc:
        returncode = 0
        stdout = "enqueued 30 cells\n"
        stderr = ""

    def fake_run(cmd, capture_output, text, timeout, cwd):
        calls.append((cmd, capture_output, text, timeout, cwd))
        return FakeProc()

    monkeypatch.setattr(server.subprocess, "run", fake_run)

    response = server.app.test_client().post(
        "/api/experiments",
        json={"action": "enqueue"},
        headers={"Idempotency-Key": "exp-enqueue"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["output"] == "enqueued 30 cells"
    assert len(calls) == 1
    assert calls[0][0][-1] == "scripts/enqueue.py"
    assert calls[0][0][0:2] == [server.sys.executable, "scripts/enqueue.py"]
    assert calls[0][3] == 30


def test_experiments_clear_appends_flag(monkeypatch):
    """F1: the clear action passes --clear through to the subprocess."""
    redis = QueueRedis(queue=[])
    monkeypatch.setattr(server, "_redis", lambda: redis)
    calls = []

    class FakeProc:
        returncode = 0
        stdout = "cleared\n"
        stderr = ""

    def fake_run(cmd, capture_output, text, timeout, cwd):
        calls.append(cmd)
        return FakeProc()

    monkeypatch.setattr(server.subprocess, "run", fake_run)

    response = server.app.test_client().post(
        "/api/experiments",
        json={"action": "clear"},
        headers={"Idempotency-Key": "exp-clear"},
    )

    assert response.status_code == 200
    assert calls[0] == [server.sys.executable, "scripts/enqueue.py", "--clear"]


def test_design_session_input_rejects_unknown_delivery():
    """F3: a client cannot smuggle an unknown delivery mode through /input."""
    response = server.app.test_client().post(
        "/api/design-sessions/ds_abc/input",
        json={"prompt": "make it so", "delivery": "teleport"},
        headers={"Idempotency-Key": "input-bad-delivery"},
    )

    assert response.status_code == 400
    assert "delivery" in response.get_json()["error"]


def test_design_session_input_forwards_allowlisted_delivery(monkeypatch):
    """F3: an allowlisted delivery mode is forwarded untouched to the manager."""
    redis = QueueRedis(queue=[])
    monkeypatch.setattr(server, "_redis", lambda: redis)
    admitted = []

    class FakeManager:
        def send_input(self, portal_id, *, prompt, delivery):
            admitted.append((portal_id, prompt, delivery))
            return {"ok": True, "admitted": True, "delivery": delivery, "response": {}}

    monkeypatch.setattr(server, "_design_sessions", lambda: FakeManager())

    response = server.app.test_client().post(
        "/api/design-sessions/ds_abc/input",
        json={"prompt": "make it so", "delivery": "steer"},
        headers={"Idempotency-Key": "input-steer"},
    )

    assert response.status_code == 200
    assert admitted == [("ds_abc", "make it so", "steer")]


def test_route_inventory_covers_all_registered_routes():
    """F2: the inventory's 31 routes match the actual url_map exactly.

    The count tracks the documented inventory in ``apps/control_room/server.py``'s module
    docstring and ``scripts/CONTEXT.md``. It went 28 -> 29 when ``GET /api/subscription-usage``
    landed, and 29 -> 31 when the docs-health pair (``GET /api/docs-health`` +
    ``POST /api/docs-health/approve``) landed with the docs-drift rail's p4; this guard is what
    catches a route shipped without its inventory entry, so a bump here must always be paired
    with the doc update (never the other way round).
    """
    rules = [rule for rule in server.app.url_map.iter_rules() if not rule.rule.startswith("/static")]

    # GET and POST on the same path register two Rule objects; count them
    # (31), then dedupe for path-membership assertions below.
    assert len(rules) == 31
    routes = {rule.rule for rule in rules}

    # The surfaces the stale inventory omitted are all registered.
    for required in (
        "/",
        "/api/registry",
        "/api/registry/<entity_id>",
        "/api/queue/reinterleave",
        "/api/experiments",
        "/api/subscription-usage",
        "/api/flags",
        "/api/flags/<session_id>/steer",
        "/api/flags/<session_id>/interrupt",
        "/api/design-sessions/<portal_id>/spec",
        "/api/design-sessions/<portal_id>/save",
        "/api/design-sessions/<portal_id>/run",
        "/api/docs-health",
        "/api/docs-health/approve",
    ):
        assert required in routes, f"missing route in inventory: {required}"


def test_api_registry_caches_parsed_manifest(tmp_path, monkeypatch):
    """F4: a second registry request reuses the parsed manifest, not a re-parse."""
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [_registry_row(knowledge_id="kid_cached")])
    monkeypatch.setattr(server, "DATA_MANIFEST_PATH", manifest_path)
    server._REGISTRY_CACHE.clear()

    loads = []
    real_load = server.registry_cli.load_registry

    def counting_load(path):
        loads.append(path)
        return real_load(path)

    monkeypatch.setattr(server.registry_cli, "load_registry", counting_load)

    client = server.app.test_client()
    first = client.get("/api/registry")
    second = client.get("/api/registry")

    assert first.status_code == 200
    assert second.get_json()["count"] == 1
    assert len(loads) == 1


def test_api_registry_cache_invalidates_on_rewrite(tmp_path, monkeypatch):
    """F4: rewriting the manifest (a size change) busts the parsed-manifest cache."""
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [_registry_row(knowledge_id="kid_v1")])
    monkeypatch.setattr(server, "DATA_MANIFEST_PATH", manifest_path)
    server._REGISTRY_CACHE.clear()

    client = server.app.test_client()
    assert client.get("/api/registry").get_json()["count"] == 1

    _write_manifest(manifest_path, [
        _registry_row(knowledge_id="kid_v1"),
        _registry_row(knowledge_id="kid_v2", entity_id="eid_v2"),
    ])
    assert client.get("/api/registry").get_json()["count"] == 2


def test_api_registry_lineage_flags_ambiguity(tmp_path, monkeypatch):
    """F5: duplicate entity rows surface an ambiguity, never a silent first pick."""
    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [
        _registry_row(knowledge_id="kid_dup_a", entity_id="eid_dup"),
        _registry_row(knowledge_id="kid_dup_b", entity_id="eid_dup"),
    ])
    monkeypatch.setattr(server, "DATA_MANIFEST_PATH", manifest_path)
    server._REGISTRY_CACHE.clear()

    response = server.app.test_client().get("/api/registry/eid_dup")
    body = response.get_json()

    assert response.status_code == 409
    assert body["error"] == "ambiguous"
    assert body["count"] == 2
    assert [row["knowledge_id"] for row in body["records"]] == ["kid_dup_a", "kid_dup_b"]


# ── actuation call site (review §5.4) ───────────────────────────
#
# The steer/interrupt handlers are the first caller of the actuation producer:
# after a successful intervention, they emit ONE actuation record whose ``causes``
# is the flag observation's knowledge_id. Best-effort — a KB outage never blocks
# the steer. Observation (GET) surfaces never emit.


def _flagged_session(**overrides):
    flag = {
        "at": "2026-08-15T00:00:00+00:00",
        "session_id": "sess_abc",
        "title": "task_manager_api",
        "model": "deepseek/deepseek-v4-flash",
        "status": "stalled",
        "why": "no forward progress",
        "review": {
            "state": "mapped",
            "cell_id": "cell_1",
            "source": "publisher_index",
            "mapped_at": "2026-08-15T00:00:00Z",
        },
    }
    flag.update(overrides)
    return flag


def test_supervisor_steer_emits_exactly_one_actuation_record(monkeypatch):
    """A successful steer emits exactly one actuation record citing the flag's knowledge_id."""
    from agentic_dynamics.control.observation_ingestion import derive_flag_record
    from agentic_dynamics.knowledge import knowledge_stream as ks
    from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID

    redis = QueueRedis(queue=[])
    monkeypatch.setattr(server, "_redis", lambda: redis)

    flag = _flagged_session()
    monkeypatch.setattr(
        server, "_authorize_supervisor_action",
        lambda session_id, cell_id: (flag, None),
    )

    sent = []

    class FakeOpenCode:
        def send_input(self, session_id, prompt, *, delivery):
            sent.append((session_id, prompt, delivery))

    monkeypatch.setattr(server, "_opencode_client", lambda: FakeOpenCode())

    published = []

    def fake_connect():
        return object()

    def fake_publish_event(redis_client, event, **kwargs):
        published.append((event, kwargs))
        return "entry-1"

    monkeypatch.setattr(ks, "connect", fake_connect)
    monkeypatch.setattr(ks, "publish_event", fake_publish_event)

    response = server.app.test_client().post(
        "/api/flags/sess_abc/steer",
        json={"cell_id": "cell_1", "prompt": "please continue"},
        headers={"Idempotency-Key": "steer-1"},
    )

    assert response.status_code == 200
    assert sent == [("sess_abc", "please continue", "steer")]
    assert len(published) == 1
    event, kwargs = published[0]
    assert event.causes == derive_flag_record(flag, repository_id=REPOSITORY_ID).knowledge_id
    assert kwargs["source_type"] == "actuation"
    assert kwargs["authorized"] is True
    assert kwargs["armed"] is True


def test_supervisor_interrupt_emits_exactly_one_actuation_record(monkeypatch):
    """A successful interrupt emits exactly one actuation record, kind=interrupt."""
    redis = QueueRedis(queue=[])
    monkeypatch.setattr(server, "_redis", lambda: redis)

    flag = _flagged_session()
    monkeypatch.setattr(
        server, "_authorize_supervisor_action",
        lambda session_id, cell_id: (flag, None),
    )

    interrupted = []

    class FakeOpenCode:
        def interrupt(self, session_id):
            interrupted.append(session_id)

    monkeypatch.setattr(server, "_opencode_client", lambda: FakeOpenCode())

    emitted = []
    monkeypatch.setattr(
        server, "_emit_actuation_record",
        lambda f, **kw: emitted.append((f, kw)),
    )

    response = server.app.test_client().post(
        "/api/flags/sess_abc/interrupt",
        json={"cell_id": "cell_1", "confirmation": "INTERRUPT sess_abc"},
        headers={"Idempotency-Key": "interrupt-1"},
    )

    assert response.status_code == 200
    assert interrupted == ["sess_abc"]
    assert len(emitted) == 1
    emitted_flag, kwargs = emitted[0]
    assert emitted_flag is flag
    assert kwargs["actuation_kind"] == "interrupt"
    assert kwargs["target_cell_id"] == "cell_1"


def test_actuation_emit_is_best_effort_and_never_blocks_the_steer(monkeypatch):
    """A KB-plane failure swallows the actuation emit and still returns 200."""
    from agentic_dynamics.knowledge import knowledge_stream as ks

    redis = QueueRedis(queue=[])
    monkeypatch.setattr(server, "_redis", lambda: redis)

    flag = _flagged_session()
    monkeypatch.setattr(
        server, "_authorize_supervisor_action",
        lambda session_id, cell_id: (flag, None),
    )

    class FakeOpenCode:
        def send_input(self, session_id, prompt, *, delivery):
            return None

    monkeypatch.setattr(server, "_opencode_client", lambda: FakeOpenCode())

    def failing_connect():
        raise RuntimeError("KB DB 2 down")

    monkeypatch.setattr(ks, "connect", failing_connect)

    response = server.app.test_client().post(
        "/api/flags/sess_abc/steer",
        json={"cell_id": "cell_1", "prompt": "please continue"},
        headers={"Idempotency-Key": "steer-1"},
    )

    # The steer still succeeded despite the KB outage.
    assert response.status_code == 200
    assert response.get_json()["admitted"] is True


def test_get_only_paths_never_emit_actuation(tmp_path, monkeypatch):
    """Observation surfaces (flags, registry, matrix) never emit an actuation record."""
    def _explode(*_args, **_kwargs):
        raise AssertionError("read-only path must never emit an actuation record")

    monkeypatch.setattr(server, "_emit_actuation_record", _explode)

    manifest_path = tmp_path / "data_manifest.json"
    _write_manifest(manifest_path, [_registry_row()])
    monkeypatch.setattr(server, "DATA_MANIFEST_PATH", manifest_path)
    server._REGISTRY_CACHE.clear()

    monkeypatch.setattr(server, "_redis", lambda: FakeRedis(statuses={"a": "running"}))
    monkeypatch.setattr(
        server, "_load_supervisor_flags",
        lambda limit: ({"flags": [], "warnings": [], "degraded": False}, 200),
    )

    client = server.app.test_client()
    assert client.get("/api/flags").status_code == 200
    assert client.get("/api/registry").status_code == 200
    assert client.get("/api/matrix").status_code == 200
