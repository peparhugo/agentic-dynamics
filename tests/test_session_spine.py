"""Tests for the session-spine record type (session_ingestion) — s1a of the
self_knowledge_layer wave, extended by the s1b session-close command cases.

Covers the record-type cases (the s1a scope fence): the ``meta_session`` source-type
reuse, the AIO org-root actor/scope carriage, the seven content fields, the round trip through
record_to_artifact / record_to_event / extract_record, rerun-safe identity (same input -> same
knowledge_id), and the identity-namespace separation from the legacy ``ledger/v1`` meta_session
lines. The close (s1b) command cases below extend this file in its own phase: ``session close``
writes artifact + event into the KB, re-running close for the same session is a no-op, and a
producer failure is a warning, never a crash. The open (s1c) command cases extend this file in
their phase.
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

from agentic_dynamics.knowledge import ledger_ingestion as li
from agentic_dynamics.knowledge import reflection_ingestion as ri
from agentic_dynamics.knowledge import session_ingestion as si
from agentic_dynamics.knowledge.knowledge import (
    SOURCE_TYPES,
    Authority,
)
from agentic_dynamics.knowledge.knowledge_ingestion import (
    REPOSITORY_ID,
    extract_record,
    record_to_artifact,
    record_to_event,
)

ROOT = Path(__file__).resolve().parent.parent


def _session(**overrides) -> dict:
    """A synthetic AIO session close payload — the s1a DONE_WHEN fixture."""
    base = {
        "session_date": "2026-09-03",
        "slug": "wt_selfk_s1a_session_record_type",
        "waves_run": ["self_knowledge_layer/s0_pin_spec", "self_knowledge_layer/s1a"],
        "merged": ["2026-08-14_experiment-spec-and-compiler-design"],
        "parked": ["fleet ladder rung 2", "deploy-gate false positive"],
        "open_threads": ["session spine close command (s1b)", "open command (s1c)"],
        "self_notes": "I re-derived the wave verdict by grep instead of reading a record.",
    }
    base.update(overrides)
    return base


def _payload(record) -> dict:
    return json.loads(record.text)


def _ledger_meta_session_attempt(attempt_id: str = "9696322fa9636310_1"):
    """A legacy embryonic meta_session record (the shape Edge 1 inspected at the s0 pin): a
    ledger_ingestion attempt whose title routed to ``meta_session`` by classify_session."""
    story_result = {
        "story_id": "abc123def456",
        "story_name": "task_manager_api",
        "language": "python",
        "worktree": "/tmp/pipeline/story_abc123",
        "sessions": [
            {
                "session_number": 1,
                "agentic": {
                    "total_tokens": 661,
                    "estimated_cost_usd": 0.001252412,
                    "confidence": None,
                },
            }
        ],
    }
    row = {"title": "meta_batch_042", "cost": 0.5, "tokens_input": 400, "tokens_output": 261}
    records = li.derive_ledger_records(story_result, row, {})
    assert {r.source_type for r in records} == {"ledger_job", "meta_session"}
    return next(r for r in records if r.source_type == "meta_session")


# ── Extractor contract constants ────────────────────────────────


def test_extractor_constants():
    assert si.SOURCE_TYPE == "meta_session"
    assert si.EXTRACTOR_VERSION == "session/v1"
    assert si.ACTOR == "aio"
    assert si.REVISION_FALLBACK == "session/unrevisioned"
    assert si.CONTENT_FIELDS == (
        "session_date",
        "slug",
        "waves_run",
        "merged",
        "parked",
        "open_threads",
        "self_notes",
    )
    # meta_session stays the single registered vocabulary row — the spine family is a producer
    # reuse of the existing source_type, never a fork in the vocabulary (the disambiguator is
    # extractor_version, exactly as the schema separates every other reuse).
    assert si.SOURCE_TYPE in SOURCE_TYPES


def test_session_ingestion_is_exported_from_the_knowledge_package():
    from agentic_dynamics.knowledge import session_ingestion

    assert session_ingestion is si


# ── Provenance + the actor/scope carriage ───────────────────────


def test_record_provenance_is_advisory_h_like_meta_session_nominal():
    record = si.derive_session_record(_session())
    assert record.source_type == "meta_session"
    assert record.authority is Authority.ADVISORY
    assert record.evidence_class == "[H]"
    assert SOURCE_TYPES["meta_session"].authority is Authority.ADVISORY


def test_record_carries_aio_actor_and_org_root_scope():
    record = si.derive_session_record(_session())
    # Scope is structural on the record: the org id as repository_id, the org-root AIO scope as
    # acl_scope — distinct from the corpus's "public" acl rows and from any self-* cell scope.
    assert record.repository_id == REPOSITORY_ID
    assert record.acl_scope == "org:agentic-dynamics"
    # And self-describing in the body: the actor + scope keys are part of the hashed payload, so
    # a consumer can filter "what did I (the AIO) write" purely from the artifact bytes.
    payload = _payload(record)
    assert payload["actor"] == "aio"
    assert payload["scope"] == record.acl_scope


def test_repository_override_rescopes_the_record():
    record = si.derive_session_record(_session(), repository_id="another-org")
    assert record.repository_id == "another-org"
    assert record.acl_scope == "org:another-org"
    assert _payload(record)["scope"] == "org:another-org"


def test_cell_scoped_retrieval_excludes_the_aio_record():
    # Actor layering, deterministic at the type: the record lives at the org root (repository_id
    # "agentic-dynamics"), so the retrieval hard pre-filter (scope_excluded) excludes it from any
    # cell/workload query — a self-* cell scope never equals the org id, so a cell agent cannot
    # resolve the AIO's session records. Only an explicit org-root read sees them.
    from agentic_dynamics.knowledge.retrieval import scope_excluded

    record = si.derive_session_record(_session())
    assert scope_excluded(record.repository_id, requested_scope="self-wt_03")
    assert scope_excluded(record.repository_id, requested_scope="org:agentic-dynamics/workload:x")
    # And the AIO itself resolves its record by asking for its own org scope (empty candidate scope
    # semantics unchanged: "" is never a wildcard on either side).
    assert not scope_excluded(record.repository_id, requested_scope="")
    assert not scope_excluded("", requested_scope="agentic-dynamics")


# ── The seven content fields round-trip ─────────────────────────


def test_content_fields_round_trip_through_artifact_and_event():
    session = _session()
    record = si.derive_session_record(session)

    artifact = record_to_artifact(record)
    event = record_to_event(record)
    extracted = extract_record(event, artifact)

    # The durable artifact + pointer carry the record; extract_record reconstructs it losslessly
    # for every stable field, and the content fields survive in the body verbatim.
    assert extracted.knowledge_id == record.knowledge_id
    assert extracted.content_hash == record.content_hash
    assert extracted.entity_id == record.entity_id
    assert extracted.acl_scope == record.acl_scope
    assert extracted.text == record.text

    payload = _payload(extracted)
    assert payload["session_date"] == session["session_date"]
    assert payload["slug"] == session["slug"]
    assert payload["waves_run"] == session["waves_run"]
    assert payload["merged"] == session["merged"]
    assert payload["parked"] == session["parked"]
    assert payload["open_threads"] == session["open_threads"]
    assert payload["self_notes"] == session["self_notes"]

    # The standard pointer contract (mirrors every producer's): content_hash is the sha256 of the
    # artifact, the event names the per-record artifact URI, observed_at round-trips the session's
    # own date (not the producer wall-clock).
    assert event.knowledge_id == record.knowledge_id
    assert event.entity_id == record.entity_id
    assert event.operation == "upsert"
    assert event.source_uri == f"file://experiments/results/kb/{record.knowledge_id}.json"
    # The pointer's source_revision is the record's commit_sha ("" for a session record — the
    # record is not bound to a commit; the stable revision marker travels in the artifact body and
    # the knowledge_id, never on the pointer). content_hash + observed_at round-trip the session's
    # own body + date.
    assert event.source_revision == record.commit_sha == ""
    assert event.content_hash == hashlib.sha256(artifact).hexdigest()
    assert event.observed_at == session["session_date"]
    assert extracted.observed_at == session["session_date"]


def test_full_dict_round_trip_is_lossless():
    from agentic_dynamics.knowledge.knowledge import KnowledgeRecord

    record = si.derive_session_record(_session())
    restored = KnowledgeRecord.from_dict(record.to_dict())
    assert restored == record


def test_derive_and_build_delegate_to_the_same_record():
    session = _session()
    # Two derivation calls land microseconds apart, so the volatile consumer clocks (valid_from /
    # indexed_at) differ — but the stable identity and body are byte-identical (what rerun-safety
    # and the s1b no-op-on-reclose both depend on).
    a = si.derive_session_record(session)
    b = si.build_session_record(session)
    for attr in (
        "knowledge_id",
        "entity_id",
        "content_hash",
        "source_uri",
        "text",
        "logical_locator",
        "acl_scope",
        "repository_id",
    ):
        assert getattr(a, attr) == getattr(b, attr)


# ── Rerun-safe identity ─────────────────────────────────────────


def test_knowledge_id_is_rerun_safe_same_input_same_id():
    first = si.derive_session_record(_session())
    # Re-derivation at a DIFFERENT producer wall-clock must still yield the same id — the volatile
    # timestamps are blanked from the artifact, so the content hash (and the id folding it) is a
    # pure function of the session body + the stable identity. This is what makes a repeated close
    # a no-op rather than a fresh record every session boundary.
    second = si.derive_session_record(_session())
    assert second.knowledge_id == first.knowledge_id
    assert second.entity_id == first.entity_id
    assert second.content_hash == first.content_hash


def test_changed_content_rekeys_knowledge_id_but_not_entity_id():
    first = si.derive_session_record(_session())
    second = si.derive_session_record(_session(waves_run=["self_knowledge_layer/s0_pin_spec"]))
    # A changed wave list is a NEW body -> a new immutable knowledge_id (a new version of the
    # session slot), while the entity_id — the slug's logical identity — holds.
    assert second.entity_id == first.entity_id
    assert second.knowledge_id != first.knowledge_id
    assert second.content_hash != first.content_hash


def test_identity_is_namespace_distinct_from_legacy_ledger_meta_session():
    # Edge 1's legacy shape is a ledger/v1 attempt whose title routed to meta_session. Give the
    # spine producer the SAME logical string as that attempt's slug: the two must never collide on
    # identity — the spine family is session:<slug> + session/v1, the legacy is
    # meta_session:<attempt> + ledger/v1.
    legacy = _ledger_meta_session_attempt()
    assert legacy.extractor_version == "ledger/v1"
    assert legacy.source_uri.startswith("meta_session:")

    spine = si.derive_session_record(_session(slug=legacy.logical_locator))
    assert spine.source_uri.startswith("session:")
    assert spine.extractor_version == "session/v1"
    assert spine.entity_id != legacy.entity_id
    assert spine.knowledge_id != legacy.knowledge_id


# ── Validation + normalization ──────────────────────────────────


def test_missing_slug_raises_value_error():
    with pytest.raises(ValueError, match="slug"):
        si.derive_session_record(_session(slug=""))


def test_missing_session_date_raises_value_error():
    with pytest.raises(ValueError, match="session_date"):
        si.derive_session_record(_session(session_date=None))


def test_empty_list_fields_normalize_to_empty_lists():
    record = si.derive_session_record(
        _session(waves_run=[], merged=None, parked=[], open_threads=None)
    )
    payload = _payload(record)
    assert payload["waves_run"] == []
    assert payload["merged"] == []
    assert payload["parked"] == []
    assert payload["open_threads"] == []
    assert (
        payload["self_notes"]
        == "I re-derived the wave verdict by grep instead of reading a record."
    )


def test_list_fields_coerce_elements_and_keep_caller_order():
    # waves_run is chronological — the list must survive in caller order (never re-sorted) and be
    # JSON-serializable even for non-str elements.
    record = si.derive_session_record(_session(merged=("doc-a", "doc-b"), parked=[42]))
    payload = _payload(record)
    assert payload["merged"] == ["doc-a", "doc-b"]
    assert payload["parked"] == ["42"]


def test_revision_is_not_bound_to_a_commit_so_close_is_rerun_safe():
    record = si.derive_session_record(_session())
    assert record.commit_sha == ""
    # The revision folded into knowledge_id is the stable fallback marker, never the checkout HEAD.
    from agentic_dynamics.knowledge.knowledge import compute_knowledge_id

    recomputed = compute_knowledge_id(
        record.entity_id, si.REVISION_FALLBACK, record.content_hash, si.EXTRACTOR_VERSION
    )
    assert record.knowledge_id == recomputed


# ═════════════════════════════════════════════════════════════════════════════
# s1b — the session CLOSE command cases (tests/test_session_spine.py is the gate)
# ═════════════════════════════════════════════════════════════════════════════


class _FakeRedis:
    """In-memory stand-in for the knowledge-stream Redis (DB 2 on 6380).

    Implements the surface ``knowledge_stream.publish_event`` + ``close_session`` touch:
    ``hget``/``hset`` on the source-type index and the checkpoint hash, and ``xadd`` on the
    change stream. A single flat hash is enough — the fields are the globally-unique
    ``knowledge_id``s, so no key collision is possible across the two hashes.
    """

    def __init__(self):
        self.hash: dict[str, str] = {}
        self.stream: dict[str, dict] = {}
        self._n = 0

    def hset(self, key, field, value):  # noqa: A003 - redis-shaped surface
        self.hash[field] = value

    def hget(self, key, field):
        return self.hash.get(field)

    def xadd(self, stream, payload):
        self._n += 1
        entry_id = f"1-{self._n}"
        self.stream[entry_id] = payload
        return entry_id


def _close(session: dict, tmp_path: Path, redis) -> si.SessionCloseResult:
    """Run the close emission seam against a tmp artifact dir + a fake stream."""
    return si.close_session(session, artifact_dir=tmp_path, connect_fn=lambda: redis)


class TestSessionClose:
    def test_close_writes_durable_artifact_and_pointer_event(self, tmp_path):
        """DONE_WHEN (1): session close lands BOTH halves — the artifact and the event."""
        session = _session()
        redis = _FakeRedis()
        result = _close(session, tmp_path, redis)

        assert result.status == "closed"
        assert result.warnings == []
        record = result.record

        # The durable per-record artifact is on disk at the canonical pointer path, and its
        # bytes are exactly the producer's deterministic artifact (so a consumer's
        # content_hash verification passes the moment the event lands).
        assert result.artifact_path == tmp_path / f"{record.knowledge_id}.json"
        assert result.artifact_path.is_file()
        assert result.artifact_path.read_bytes() == record_to_artifact(record)

        # The pointer event landed on the change stream, naming the same record, and the
        # knowledge_id is checkpointed (the producers' shared idempotence ledger) so a re-close
        # is a no-op rather than a double emit.
        assert len(redis.stream) == 1
        event = next(iter(redis.stream.values()))
        assert event["knowledge_id"] == record.knowledge_id
        assert event["entity_id"] == record.entity_id
        assert event["operation"] == "upsert"
        assert redis.hash.get(record.knowledge_id)

        # The record that lands is the AIO's org-root session record — actor + scope ride in
        # the body, scope rides structurally on the record.
        payload = _payload(record)
        assert payload["actor"] == "aio"
        assert payload["scope"] == "org:agentic-dynamics"
        assert record.acl_scope == payload["scope"]

    def test_repeat_close_of_the_same_session_is_a_noop(self, tmp_path):
        """DONE_WHEN (2): re-running close for the same session is a no-op (rerun-safe key)."""
        session = _session()
        redis = _FakeRedis()
        first = _close(session, tmp_path, redis)
        second = _close(session, tmp_path, redis)

        assert first.status == "closed"
        assert first.entry_id  # the first close published
        assert second.status == "no-op"
        assert second.entry_id == ""  # nothing published the second time
        assert second.warnings == []
        # No second event, no rewritten artifact, and the SAME knowledge_id throughout — a
        # repeated close changes nothing (the s1a rerun-safe identity made this possible).
        assert second.record.knowledge_id == first.record.knowledge_id
        assert len(redis.stream) == 1
        assert second.artifact_path.read_bytes() == first.artifact_path.read_bytes()

    def test_close_of_a_changed_session_body_is_a_new_version_not_a_noop(self, tmp_path):
        """A changed wave list is a changed body -> a new knowledge_id for the SAME entity.

        The no-op is content-keyed, never slug-keyed: closing the same session slot with
        different content publishes a new version (the supersede-capable spine's input), it is
        never silently swallowed as "already closed".
        """
        redis = _FakeRedis()
        first = _close(_session(), tmp_path, redis)
        second = _close(_session(waves_run=["self_knowledge_layer/s0_pin_spec"]), tmp_path, redis)

        assert first.status == "closed"
        assert second.status == "closed"
        assert second.record.entity_id == first.record.entity_id
        assert second.record.knowledge_id != first.record.knowledge_id
        assert len(redis.stream) == 2

    def test_producer_failure_is_a_warning_never_a_crash(self, tmp_path):
        """DONE_WHEN (3): a downed stream degrades to a warning — the record is never lost."""

        def down():
            raise ConnectionError("knowledge stream is down")

        result = si.close_session(_session(), artifact_dir=tmp_path, connect_fn=down)

        assert result.status == "degraded"
        assert result.warnings  # the reason is surfaced, not swallowed
        assert result.entry_id == ""
        # The durable artifact still landed — the close is never lost to a stream outage.
        assert result.artifact_path.is_file()
        assert result.artifact_path.read_bytes() == record_to_artifact(result.record)

    def test_reclose_repairs_a_partial_failure_once_the_stream_returns(self, tmp_path):
        """A close that wrote the artifact but could not publish is COMPLETED by re-running.

        The artifact-presence check alone would make the second close a no-op and strand the
        record off the stream forever; the checkpoint hash is the publish ledger, so a re-close
        sees the missing event and publishes it.
        """

        def down():
            raise ConnectionError("knowledge stream is down")

        degraded = si.close_session(_session(), artifact_dir=tmp_path, connect_fn=down)
        assert degraded.status == "degraded"

        redis = _FakeRedis()
        repaired = si.close_session(_session(), artifact_dir=tmp_path, connect_fn=lambda: redis)

        assert repaired.status == "closed"
        assert repaired.record.knowledge_id == degraded.record.knowledge_id
        assert len(redis.stream) == 1  # exactly one event — the repair, never a duplicate

    def test_close_rejects_a_session_with_no_slug(self, tmp_path):
        """The type's one hard requirement is honored at the close seam, not papered over."""
        redis = _FakeRedis()
        with pytest.raises(ValueError, match="slug"):
            si.close_session(_session(slug=""), artifact_dir=tmp_path, connect_fn=lambda: redis)


class TestSessionCloseCommand:
    """The ``agentic-dynamics session close`` command (CLI shell over the emission seam)."""

    def test_command_resolves_to_session_close_script(self):
        from agentic_dynamics import cli

        assert cli._resolve(["session", "close"]) == ("session_close.py", [])
        assert (ROOT / "scripts" / "session_close.py").is_file()

    def test_command_end_to_end_writes_into_the_kb(self, tmp_path, monkeypatch, capsys):
        """Run the REAL command against a fake stream + tmp artifact dir: artifact + event land.

        Since s6a the close ALSO appends the session's reflection entry, so the command lands
        TWO durable records in the KB: the session-spine record (the s1b deliverable) AND the
        session-keyed reflection entry seeded from its self-notes (the s6a append path).
        """
        from agentic_dynamics.core import paths as core_paths
        from agentic_dynamics.knowledge import knowledge_stream as ks

        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import session_close as sc

        redis = _FakeRedis()
        monkeypatch.setattr(ks, "connect", lambda: redis)
        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)

        session = {
            "session_date": "2026-09-03",
            "slug": "wt_selfk_s1b_close_writer",
            "waves_run": ["self_knowledge_layer/s0_pin_spec", "self_knowledge_layer/s1a"],
            "merged": ["2026-08-14_experiment-spec-and-compiler-design"],
            "parked": ["fleet ladder rung 2"],
            "open_threads": ["session spine close command (s1b)"],
            "self_notes": "I re-derived the wave verdict by grep instead of reading a record.",
        }
        argv = [
            "--slug",
            session["slug"],
            "--session-date",
            session["session_date"],
            "--wave",
            "self_knowledge_layer/s0_pin_spec",
            "--wave",
            "self_knowledge_layer/s1a",
            "--merged",
            "2026-08-14_experiment-spec-and-compiler-design",
            "--parked",
            "fleet ladder rung 2",
            "--open-thread",
            "session spine close command (s1b)",
            "--self-notes",
            session["self_notes"],
        ]
        assert sc.main(argv) == 0
        spine = si.derive_session_record(session)
        reflection = ri.derive_reflection_record(session)
        assert {path.name for path in tmp_path.glob("*.json")} == {
            f"{spine.knowledge_id}.json",
            f"{reflection.knowledge_id}.json",
        }
        events = [payload["knowledge_id"] for payload in redis.stream.values()]
        assert len(events) == 2
        assert {spine.knowledge_id, reflection.knowledge_id} <= set(events)
        assert len(redis.stream) == 2
        out = capsys.readouterr().out
        assert "closed" in out
        assert "reflection: appended" in out

    def test_command_rerun_is_a_noop(self, tmp_path, monkeypatch):
        from agentic_dynamics.core import paths as core_paths
        from agentic_dynamics.knowledge import knowledge_stream as ks

        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import session_close as sc

        redis = _FakeRedis()
        monkeypatch.setattr(ks, "connect", lambda: redis)
        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)

        argv = ["--slug", "wt_selfk_s1b_close_writer", "--session-date", "2026-09-03"]
        assert sc.main(argv) == 0
        assert sc.main(argv) == 0  # the identical re-close exits clean, emits nothing new
        assert len(redis.stream) == 1
        assert len(list(tmp_path.glob("*.json"))) == 1

    def test_command_downed_stream_is_a_warning_and_exits_zero(self, tmp_path, monkeypatch, capsys):
        from agentic_dynamics.core import paths as core_paths
        from agentic_dynamics.knowledge import knowledge_stream as ks

        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import session_close as sc

        def down():
            raise ConnectionError("knowledge stream is down")

        monkeypatch.setattr(ks, "connect", down)
        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)

        rc = sc.main(["--slug", "wt_selfk_s1b_close_writer", "--session-date", "2026-09-03"])
        assert rc == 0  # never a crash
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()
        assert "degraded" in captured.out or "NOT published" in captured.out
        assert len(list(tmp_path.glob("*.json"))) == 1  # the durable artifact still lands

    def test_command_missing_slug_is_a_usage_error(self, capsys):
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import session_close as sc

        with pytest.raises(SystemExit) as exc:
            sc.main(["--session-date", "2026-09-03"])
        assert exc.value.code == 2  # argparse usage error, not a close attempt


# ═════════════════════════════════════════════════════════════════════════════
# s1c — the session OPEN command cases (tests/test_session_spine.py is the gate)
# ═════════════════════════════════════════════════════════════════════════════


def _open(session_dir: Path, **kwargs) -> si.SessionOpenResult:
    """Run the open retrieval seam against a durable-artifact dir."""
    return si.open_session(artifact_dir=session_dir, **kwargs)


class TestSessionOpen:
    """The ``session_ingestion.open_session`` read seam (the direct KB read)."""

    def test_no_prior_close_is_bootstrap(self, tmp_path):
        """DONE_WHEN (2): open with no prior close renders the bootstrap, never an error."""
        result = _open(tmp_path)
        assert result.status == "bootstrap"
        assert result.slug is None
        assert result.payload is None
        assert result.artifact_path is None
        assert result.candidates == 0
        assert result.warnings == []
        text = si.render_opening_context(result)
        assert "First session" in text
        assert "session close" in text  # the bootstrap names the command that ends it

    def test_foreign_artifacts_do_not_break_the_bootstrap(self, tmp_path):
        """A dir holding only other-org/other-family records is still the first-session state."""
        (tmp_path / "not-a-session.json").write_bytes(b"{}")
        foreign = si.derive_session_record(_session(slug="cell-wt_03"), repository_id="another-org")
        (tmp_path / f"{foreign.knowledge_id}.json").write_bytes(record_to_artifact(foreign))
        legacy = _ledger_meta_session_attempt()
        (tmp_path / f"{legacy.knowledge_id}.json").write_bytes(record_to_artifact(legacy))

        result = _open(tmp_path)
        assert result.status == "bootstrap"
        assert result.candidates == 0
        assert result.warnings == []

    def test_round_trip_close_then_open_is_exact(self, tmp_path):
        """DONE_WHEN (3): the round-trip is exact — open reads back exactly what close wrote."""
        session = _session()
        closed = _close(session, tmp_path, _FakeRedis())

        opened = _open(tmp_path)
        assert opened.status == "opened"
        assert opened.slug == session["slug"]
        assert opened.knowledge_id == closed.record.knowledge_id
        assert opened.entity_id == closed.record.entity_id
        assert opened.candidates == 1
        # The decoded body is byte-identical to the closed record's own canonical payload.
        assert opened.payload == json.loads(closed.record.text)
        for field in si.CONTENT_FIELDS:
            assert opened.payload[field] == session[field]

    def test_open_resolves_the_last_session_by_session_date(self, tmp_path):
        """DONE_WHEN (1): the LAST session's close — greatest session_date — is resolved."""
        redis = _FakeRedis()
        earlier = _close(
            _session(slug="wt_selfk_s1a_session_record_type", session_date="2026-09-02"),
            tmp_path,
            redis,
        )
        later = _close(
            _session(slug="wt_selfk_s1b_close_writer", session_date="2026-09-03"),
            tmp_path,
            redis,
        )
        opened = _open(tmp_path)
        assert opened.status == "opened"
        assert opened.slug == later.record.logical_locator
        assert opened.knowledge_id == later.record.knowledge_id
        assert opened.knowledge_id != earlier.record.knowledge_id
        assert opened.candidates == 2

    def test_same_date_sessions_resolve_by_the_documented_slug_tie_break(self, tmp_path):
        """Two sessions closed the same day: content cannot order them, so slug order is the
        documented, checkout-stable resolution (mtime dies on a fresh git checkout)."""
        redis = _FakeRedis()
        _close(
            _session(slug="wt_selfk_s1b_close_writer", session_date="2026-09-03"),
            tmp_path,
            redis,
        )
        later_named = _close(
            _session(slug="wt_selfk_s1c_open_reader", session_date="2026-09-03"),
            tmp_path,
            redis,
        )
        opened = _open(tmp_path)
        assert opened.status == "opened"
        assert opened.slug == "wt_selfk_s1c_open_reader"
        assert opened.knowledge_id == later_named.record.knowledge_id

    def test_explicit_slug_selects_that_session_not_the_last(self, tmp_path):
        """--slug opens one named session slot even when a later session exists."""
        redis = _FakeRedis()
        target = _close(
            _session(slug="wt_selfk_s1b_close_writer", session_date="2026-09-03"),
            tmp_path,
            redis,
        )
        _close(
            _session(slug="wt_selfk_s1c_open_reader", session_date="2026-09-04"),
            tmp_path,
            redis,
        )
        opened = _open(tmp_path, slug="wt_selfk_s1b_close_writer")
        assert opened.status == "opened"
        assert opened.slug == "wt_selfk_s1b_close_writer"
        assert opened.knowledge_id == target.record.knowledge_id
        assert opened.requested_slug == "wt_selfk_s1b_close_writer"

    def test_explicit_slug_with_no_close_is_bootstrap(self, tmp_path):
        """A named slot that was never closed is a bootstrap for THAT slot, not an error."""
        _close(_session(), tmp_path, _FakeRedis())
        result = _open(tmp_path, slug="never-closed")
        assert result.status == "bootstrap"
        assert result.slug == "never-closed"  # the requested slot is echoed, not lost
        assert result.requested_slug == "never-closed"
        assert result.candidates == 1  # the scan ran; nothing matched the slug
        assert "never-closed" in si.render_opening_context(result)

    def test_reclose_on_a_later_date_is_the_newer_version_of_the_slot(self, tmp_path):
        """A changed-body re-close is a NEW version of the SAME slot; open returns the newest.
        Content ordering (session_date) selects it — no mtime dependence, so a fresh checkout
        resolves identically."""
        redis = _FakeRedis()
        first = _close(
            _session(
                slug="wt_selfk_s1b_close_writer",
                session_date="2026-09-03",
                waves_run=["self_knowledge_layer/s0_pin_spec"],
            ),
            tmp_path,
            redis,
        )
        second = _close(
            _session(
                slug="wt_selfk_s1b_close_writer",
                session_date="2026-09-04",
                waves_run=["self_knowledge_layer/s0_pin_spec", "self_knowledge_layer/s1a"],
            ),
            tmp_path,
            redis,
        )
        assert second.record.entity_id == first.record.entity_id  # same session slot
        assert second.record.knowledge_id != first.record.knowledge_id  # new body -> new version

        opened = _open(tmp_path)
        assert opened.status == "opened"
        assert opened.knowledge_id == second.record.knowledge_id
        assert opened.payload["waves_run"] == [
            "self_knowledge_layer/s0_pin_spec",
            "self_knowledge_layer/s1a",
        ]
        assert opened.candidates == 2

    def test_duplicate_same_day_closes_resolve_deterministically(self, tmp_path):
        """Two versions of the SAME slot closed the same day: open is reproducible (same record
        every time), never an error over the ambiguity."""
        redis = _FakeRedis()
        base = _session(slug="wt_selfk_s1c_open_reader", session_date="2026-09-03")
        _close(base, tmp_path, redis)
        _close({**base, "waves_run": ["self_knowledge_layer/s0_pin_spec"]}, tmp_path, redis)

        first = _open(tmp_path)
        second = _open(tmp_path)
        assert first.status == "opened"
        assert first.candidates == 2
        assert first.knowledge_id == second.knowledge_id
        assert first.payload == second.payload
        assert first.artifact_path == second.artifact_path

    def test_scope_excludes_foreign_repository_and_legacy_ledger_records(self, tmp_path):
        """SCOPE FENCE: the org-root read resolves ONLY the AIO's org-root records — a
        cell/workload repository's session/v1 record and a legacy ledger/v1 meta_session line
        in the same dir are invisible (never candidates, never noise)."""
        closed = _close(_session(slug="wt_selfk_s1b_close_writer"), tmp_path, _FakeRedis())

        foreign = si.derive_session_record(_session(slug="cell-wt_03"), repository_id="another-org")
        (tmp_path / f"{foreign.knowledge_id}.json").write_bytes(record_to_artifact(foreign))
        legacy = _ledger_meta_session_attempt()
        (tmp_path / f"{legacy.knowledge_id}.json").write_bytes(record_to_artifact(legacy))

        opened = _open(tmp_path)
        assert opened.status == "opened"
        assert opened.slug == "wt_selfk_s1b_close_writer"
        assert opened.knowledge_id == closed.record.knowledge_id
        assert opened.candidates == 1  # exactly the org-root AIO record, nothing else
        assert opened.warnings == []

    def test_org_artifact_with_a_foreign_actor_is_warned_not_selected(self, tmp_path):
        """A session/v1 artifact IN the org scope whose body actor is not the AIO's is surfaced
        as a warning — the honest signal a layering violation happened — never silently picked."""
        closed = _close(_session(slug="wt_selfk_s1b_close_writer"), tmp_path, _FakeRedis())

        data = json.loads(record_to_artifact(si.derive_session_record(_session(slug="impostor"))))
        payload = json.loads(data["text"])
        payload["actor"] = "supervisor"  # not the AIO
        data["text"] = json.dumps(payload)
        (tmp_path / "impostor.json").write_bytes(json.dumps(data, sort_keys=True).encode())

        opened = _open(tmp_path)
        assert opened.status == "opened"
        assert opened.knowledge_id == closed.record.knowledge_id  # the real close still wins
        assert opened.candidates == 1
        assert any("impostor.json" in warning for warning in opened.warnings)


class TestSessionOpenCommand:
    """The ``agentic-dynamics session open`` command (CLI shell over the read seam)."""

    def test_command_resolves_to_session_open_script(self):
        from agentic_dynamics import cli

        assert cli._resolve(["session", "open"]) == ("session_open.py", [])
        assert (ROOT / "scripts" / "session_open.py").is_file()

    def test_command_no_prior_close_renders_bootstrap(self, tmp_path, monkeypatch, capsys):
        """DONE_WHEN (2): open with no close renders the bootstrap — human and machine."""
        from agentic_dynamics.core import paths as core_paths

        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import session_open as so

        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)

        assert so.main(["--json"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["schema"] == "session-open/v1"
        assert report["status"] == "bootstrap"
        assert report["slug"] is None
        assert report["candidates"] == 0
        assert report["warnings"] == []

        assert so.main([]) == 0
        out = capsys.readouterr().out
        assert "First session" in out
        assert "session close" in out
        assert capsys.readouterr().err == ""  # a clean bootstrap warns nothing

    def test_command_round_trip_close_then_open_is_exact(self, tmp_path, monkeypatch, capsys):
        """The REAL close command then the REAL open command: the round-trip is exact (DONE_WHEN
        1 + 3) — open renders precisely what close wrote, in the same durable artifact dir.

        Since s6a the close also appends the session's reflection entry, so the dir holds TWO
        records — but ``session open`` reads ONLY the AIO's ``session/v1`` spine family, so the
        reflection record is foreign to it and the round-trip stays exact (candidates == 1)."""
        from agentic_dynamics.core import paths as core_paths
        from agentic_dynamics.knowledge import knowledge_stream as ks

        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import session_close as sc
        import session_open as so

        redis = _FakeRedis()
        monkeypatch.setattr(ks, "connect", lambda: redis)
        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)

        session = {
            "session_date": "2026-09-03",
            "slug": "wt_selfk_s1b_close_writer",
            "waves_run": ["self_knowledge_layer/s0_pin_spec", "self_knowledge_layer/s1a"],
            "merged": ["2026-08-14_experiment-spec-and-compiler-design"],
            "parked": ["fleet ladder rung 2"],
            "open_threads": ["open command (s1c)"],
            "self_notes": "I re-derived the wave verdict by grep instead of reading a record.",
        }
        argv = [
            "--slug",
            session["slug"],
            "--session-date",
            session["session_date"],
            "--wave",
            "self_knowledge_layer/s0_pin_spec",
            "--wave",
            "self_knowledge_layer/s1a",
            "--merged",
            "2026-08-14_experiment-spec-and-compiler-design",
            "--parked",
            "fleet ladder rung 2",
            "--open-thread",
            "open command (s1c)",
            "--self-notes",
            session["self_notes"],
        ]
        assert sc.main(argv) == 0
        capsys.readouterr()  # drop the close command's report — the buffer below is open's own
        spine = si.derive_session_record(session)
        reflection = ri.derive_reflection_record(session)
        artifacts = {path.name for path in tmp_path.glob("*.json")}
        assert artifacts == {
            f"{spine.knowledge_id}.json",
            f"{reflection.knowledge_id}.json",
        }

        assert so.main(["--json"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["status"] == "opened"
        assert report["slug"] == "wt_selfk_s1b_close_writer"
        assert report["session_date"] == "2026-09-03"
        assert report["waves_run"] == [
            "self_knowledge_layer/s0_pin_spec",
            "self_knowledge_layer/s1a",
        ]
        assert report["merged"] == ["2026-08-14_experiment-spec-and-compiler-design"]
        assert report["parked"] == ["fleet ladder rung 2"]
        assert report["open_threads"] == ["open command (s1c)"]
        assert report["self_notes"] == (
            "I re-derived the wave verdict by grep instead of reading a record."
        )
        assert report["knowledge_id"] == spine.knowledge_id  # the record close just wrote
        assert report["entity_id"] == spine.entity_id
        assert report["candidates"] == 1  # the reflection entry is foreign to the spine read
        assert report["warnings"] == []

        assert so.main([]) == 0
        out = capsys.readouterr().out
        assert "Last session close: wt_selfk_s1b_close_writer (2026-09-03)" in out
        assert "self_knowledge_layer/s0_pin_spec, self_knowledge_layer/s1a" in out
        assert "open command (s1c)" in out
        assert "I re-derived the wave verdict by grep instead of reading a record." in out
