"""Tests for the operator drain command (``control_db_evidence`` e2).

The run-path drain already works and is NOT under test here — this file proves the operator
RECOVERY surface: ``scripts/control_drain_outbox.py``, which re-runs the same publisher on
demand so pending rows are delivered once the knowledge stream returns, and reports the
delivered/dead/pending counts honestly (both directions: what the pass did, and what the table
still owes).

Like ``test_outbox.py``, the knowledge stream is a fake (``FakeStream``) and the control
database is always real (a SQLite file under ``tmp_path``) — the reporting contract is provable
only by controlling exactly when the stream acks, which a live Redis will not let a test do.

The script is loaded via ``importlib`` (``scripts/control_drain_outbox.py`` is not a package,
the same technique ``test_run_workflow_graph_cli.py`` uses), so both its ``run_drain`` seam and
its CLI ``main`` are exercised hermetically.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from agentic_dynamics.control.control_db import (
    ControlDB,
    OutboxStatus,
    RunState,
)
from agentic_dynamics.control.outbox import BackoffPolicy, knowledge_payload
from agentic_dynamics.knowledge.knowledge import Authority, KnowledgeEvent, KnowledgeRecord

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_module(name="control_drain_outbox_under_test"):
    spec = importlib.util.spec_from_file_location(
        name, PROJECT_ROOT / "scripts" / "control_drain_outbox.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


@pytest.fixture()
def db(tmp_path):
    handle = ControlDB.open(tmp_path / "control" / "control.db")
    yield handle
    handle.close()


@pytest.fixture()
def run_id(db):
    return db.create_run(
        spec_name="control_db_evidence",
        model="deepseek/deepseek-v4-flash",
        state=RunState.RUNNING,
    ).run_id


class FakeStream:
    """A knowledge stream that records publishes and can fail on demand (see test_outbox)."""

    def __init__(self, *, fail_times: int = 0, error: Exception | None = None):
        self.published: list[tuple[dict, str, bool]] = []
        self.checkpoints: dict[str, dict[str, str]] = {}
        self.fail_times = fail_times
        self.error = error or RuntimeError("stream rejected the event")

    def connect(self):
        return self

    def publish(self, client, event, *, source_type="", authorized=False):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise self.error
        self.published.append((event.to_dict(), source_type, authorized))
        return f"1700000000-{len(self.published)}"  # the ack: a stream entry id

    def hget(self, key, field):
        return self.checkpoints.get(key, {}).get(field)

    def hset(self, key, field, value):
        self.checkpoints.setdefault(key, {})[field] = value


def make_record(knowledge_id: str = "k" * 64, **overrides) -> KnowledgeRecord:
    fields = dict(
        knowledge_id=knowledge_id,
        entity_id="spec:control_db_evidence",
        source_uri="file://experiments/results/kb/x.json",
        source_type="finding",
        logical_locator="workflows/repository/control_db_evidence.yaml",
        repository_id="self-wt_evidence",
        branch="main",
        worktree_id="wt_evidence",
        commit_sha="a" * 40,
        content_hash="b" * 64,
        extractor_version="measured-finding/v1",
        embedding_version="none",
        authority=Authority.MEASURED,
        valid_from="2026-09-02T00:00:00Z",
        valid_to=None,
        observed_at="2026-09-02T00:00:00Z",
        indexed_at="2026-09-02T00:00:01Z",
        acl_scope="repo",
        contains_sensitive_data=False,
        text="the operator drain delivered this",
        token_count=5,
        language="python",
        symbols=[],
        outcome_id="",
        test_executed_success=True,
        evidence_class="[M]",
    )
    fields.update(overrides)
    return KnowledgeRecord(**fields)


def make_event(record: KnowledgeRecord, **overrides) -> KnowledgeEvent:
    fields = dict(
        knowledge_id=record.knowledge_id,
        entity_id=record.entity_id,
        operation="upsert",
        source_uri=record.source_uri,
        source_revision=record.commit_sha,
        content_hash=record.content_hash,
        occurred_at=record.observed_at,
        schema_version="knowledge-event/v1",
        event_id=record.knowledge_id,
        reason="operator drain test",
    )
    fields.update(overrides)
    return KnowledgeEvent(**fields)


def enqueue_pending(db, run_id, *, tag):
    """Enqueue one pending knowledge payload with a deterministic id derived from ``tag``."""
    kid = f"{'a' * 63}{tag}"[:64]
    record = make_record(knowledge_id=kid)
    return db.enqueue_outbox_event(
        run_id, knowledge_payload(record, make_event(record))
    )


def drain_kwargs(tmp_path, stream):
    return dict(
        connect=stream.connect,
        publish=stream.publish,
        artifact_dir=tmp_path / "kb",
        registry_path=tmp_path / "registry_index.jsonl",
        checkpoint_key="finops:kb:checkpoint",
        log=lambda _msg: None,
    )


# ── The operator drain delivers pending rows when the stream returns ─────────────────────────


def test_drain_delivers_pending_rows_and_reports_honestly(tmp_path, db, run_id, module):
    """(a) When the stream returns, the operator drain delivers every pending row and the
    report's delivered count and post-drain pending count agree."""
    row_a = enqueue_pending(db, run_id, tag="1")
    row_b = enqueue_pending(db, run_id, tag="2")
    assert db.outbox_events(run_id=run_id)[0].status is OutboxStatus.PENDING

    stream = FakeStream()
    doc = module.run_drain(db, **drain_kwargs(tmp_path, stream))

    assert doc["drained"]["delivered"] == 2
    assert doc["drained"]["stream_error"] == ""
    assert doc["outbox_after"]["pending"] == 0
    assert doc["outbox_after"]["delivered"] == 2
    # The table state really moved: the rows the operator queued are delivered.
    statuses = {r.event_id: r.status for r in db.outbox_events(run_id=run_id)}
    assert statuses[row_a.event_id] is OutboxStatus.DELIVERED
    assert statuses[row_b.event_id] is OutboxStatus.DELIVERED
    # And the stream really received the events (the ack ordering held).
    assert len(stream.published) == 2


def test_drain_reports_dead_and_pending_honestly(tmp_path, db, run_id, module):
    """A pre-existing DEAD row is reported as dead (never re-attempted) while live pending
    rows are delivered — dead stays dead, pending falls to zero, delivered counts real rows."""
    dead_row = enqueue_pending(db, run_id, tag="9")
    db.mark_outbox_dead(dead_row.event_id, error="earlier operator diagnosis")
    pending_row = enqueue_pending(db, run_id, tag="1")

    stream = FakeStream()
    doc = module.run_drain(db, **drain_kwargs(tmp_path, stream))

    # The dead row was NOT re-attempted (dead is terminal for the row).
    assert doc["outbox_before"]["dead"] == 1
    assert doc["drained"]["delivered"] == 1  # only the live pending row
    assert doc["outbox_after"]["pending"] == 0
    assert doc["outbox_after"]["delivered"] == 1
    assert doc["outbox_after"]["dead"] == 1
    assert dead_row.event_id in doc["outbox_after"]["dead_event_ids"]
    assert db.get_outbox_event(pending_row.event_id).status is OutboxStatus.DELIVERED
    assert db.get_outbox_event(dead_row.event_id).status is OutboxStatus.DEAD


def test_drain_when_the_stream_is_down_leaves_rows_pending(tmp_path, db, run_id, module):
    """A downed stream is reported (stream_error set) and every row honestly stays pending —
    the command never reports a delivered count that did not happen."""
    row_a = enqueue_pending(db, run_id, tag="1")
    row_b = enqueue_pending(db, run_id, tag="2")

    class DownedStream(FakeStream):
        def connect(self):
            raise ConnectionError("redis is down")

    doc = module.run_drain(db, **drain_kwargs(tmp_path, DownedStream()))

    assert doc["drained"]["delivered"] == 0
    assert doc["drained"]["stream_error"] != ""
    assert doc["outbox_after"]["pending"] == 2
    assert db.get_outbox_event(row_a.event_id).status is OutboxStatus.PENDING
    assert db.get_outbox_event(row_b.event_id).status is OutboxStatus.PENDING
    # A stream outage charged NO row an attempt — the retry budget is intact for the retry.
    assert db.get_outbox_event(row_a.event_id).attempts == 0


def test_drain_retries_are_reported_and_then_delivered_when_the_stream_returns(
    tmp_path, db, run_id, module
):
    """Transient per-row failures are reported as retried (rows stay pending, budget charged),
    and the SAME operator drain delivers them once the stream accepts — the recovery loop."""
    enqueue_pending(db, run_id, tag="1")
    enqueue_pending(db, run_id, tag="2")

    # Zero-base backoff so a retried row is eligible again on the very next pass (the test
    # proves the reporting + recovery, not the 2s wait of the production policy).
    policy = BackoffPolicy(base_seconds=0.0)
    flaky = FakeStream(fail_times=2)
    doc = module.run_drain(db, policy=policy, **drain_kwargs(tmp_path, flaky))
    assert doc["drained"]["retried"] == 2
    assert doc["drained"]["delivered"] == 0
    assert doc["outbox_after"]["pending"] == 2  # retried rows are still owed

    healed = FakeStream()
    doc2 = module.run_drain(db, policy=policy, **drain_kwargs(tmp_path, healed))
    assert doc2["drained"]["delivered"] == 2
    assert doc2["outbox_after"]["pending"] == 0


def test_drain_failure_never_raises(tmp_path, db, run_id, module):
    """(d) A drain that cannot reach the stream, and one whose publishes all fail, RETURNS an
    honest report instead of raising — a drain failure can never fail anything else."""
    enqueue_pending(db, run_id, tag="1")

    class AlwaysDown(FakeStream):
        def connect(self):
            raise ConnectionError("stream down")

    doc = module.run_drain(db, **drain_kwargs(tmp_path, AlwaysDown()))
    assert doc["drained"]["stream_error"] != ""

    # All-publish-failures burn the retry budget to dead, still without raising. A 1-attempt
    # policy makes "exhausted -> dead" observable in one pass instead of five.
    enqueue_pending(db, run_id, tag="2")
    failing = FakeStream(fail_times=100)
    doc2 = module.run_drain(
        db, policy=BackoffPolicy(max_attempts=1), **drain_kwargs(tmp_path, failing)
    )
    assert doc2["drained"]["dead"] >= 1  # exhausted rows went dead, the report says so
    assert doc2["outbox_after"]["pending"] + doc2["outbox_after"]["delivered"] + \
        doc2["outbox_after"]["dead"] >= 2


# ── The CLI shell ─────────────────────────────────────────────────────────────────────────────


def test_cli_refuses_when_there_is_no_control_database(tmp_path, module, capsys):
    """A drain command must never CREATE a control database — no db means nothing to drain."""
    missing = tmp_path / "does-not-exist" / "control.db"
    rc = module.main(["--db", str(missing), "--json"])
    captured = json.loads(capsys.readouterr().out)
    assert rc == module.EXIT_NO_CONTROL_DB
    assert captured["error"] == "control_db_unavailable"


def test_cli_reports_a_stream_outage_honestly(tmp_path, db, run_id, module, monkeypatch, capsys):
    """The CLI returns 0 with an honest human report when the stream is unreachable — the rows
    stay pending and the command says so, rather than failing or lying."""
    enqueue_pending(db, run_id, tag="1")
    db.close()

    import agentic_dynamics.knowledge.knowledge_stream as ks

    def boom():
        raise ConnectionError("no redis here")

    monkeypatch.setattr(ks, "connect", boom)
    rc = module.main(["--db", str(db.path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "stream unreachable" in out
    assert "1 row(s) stay pending" in out
