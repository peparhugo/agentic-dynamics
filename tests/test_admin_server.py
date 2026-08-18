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

    review = server.app.test_client().get("/api/matrix").get_json()["stages"]["review"]

    assert review["retry"] == 2
    assert review["running"] == 3  # 1 running + 2 retries, still in flight
    assert review["total"] == 3
    assert review["done"] == 0


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
