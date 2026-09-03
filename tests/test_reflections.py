"""Tests for the reflection record type + append path (reflection_ingestion) — s6a of the
self_knowledge_layer wave, extended by the s6b reflection-read command cases.

Covers the s6a DONE_WHEN + type/append cases. The deliverable: the reflection record type and
the append path — the session close (s1b) appends its self-notes into a session-keyed
reflection series. A reflection record is ONE entry per session: ``{session_date, slug,
self_notes}`` (the s1a session type's own self-notes field fed straight through) plus
``actor``/``scope``. Producer aio, org-root scope, private to the controller-AIO pair — never
resolved by cell agents (the scope fence asserted via ``retrieval.scope_excluded``) or the
supervisor rail.

The s6b read cases below extend this file in their phase: ``reflect --read`` renders the
accumulated reflection series in chronological order (the read seam
``read_reflection_series``/``render_reflection_series`` over the same org-root family), and an
empty series renders a clear empty state — never an error.

Cases:

* the record type: ``reflection`` registered as an observation-family ADVISORY/[H] source type;
  the actor/scope carriage; the three content fields round-tripping through
  record_to_artifact/record_to_event/extract_record; rerun-safe identity (same input -> same
  knowledge_id) with per-session versioning (amended self-notes re-key knowledge_id while
  entity_id holds — ONE entry per session, never a second entry); namespace separation from the
  session spine and the decision family; missing slug/session_date refuse loudly.
* the append path: append_reflection lands artifact + event; re-append is a rerun-safe no-op; a
  SECOND session's append adds a SECOND entry — the first is untouched (the series grows,
  nothing overwrites); empty self-notes reflect nothing (status ``no-notes``, nothing written);
  a producer failure is a warning, never a crash; a re-run repairs a partial append.
* the family (DONE_WHEN 3): the series is retrievable as a family — scan resolves the session-
  keyed records and resolve_reflection_series yields ONE current entry per session in
  session_date order, collapsing a same-session amended re-close into its newest version.
* the CLI wiring: the REAL ``agentic-dynamics session close`` command appends its reflection
  entry; a close with no self-notes appends nothing; an identical re-close appends nothing
  twice (rerun-safe).
* the read command (s6b — DONE_WHEN): the REAL ``agentic-dynamics reflect --read`` renders the
  accumulated entries in chronological order (sorted by session_date, never by append order);
  an empty series renders a clear empty state; the machine reflect/v1 report carries the full
  ordered series; anomalies are warned on stderr and foreign/other-family records are never
  candidates.
"""

import json
import sys
from pathlib import Path

import pytest

from agentic_dynamics.knowledge import reflection_ingestion as ri
from agentic_dynamics.knowledge import session_ingestion as si
from agentic_dynamics.knowledge.knowledge import (
    ACTUATION_TYPES,
    SOURCE_TYPES,
    Authority,
    SourceTypeSpec,
    message_family,
)
from agentic_dynamics.knowledge.knowledge_ingestion import (
    REPOSITORY_ID,
    extract_record,
    record_to_artifact,
    record_to_event,
)

ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = str(ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def _session(**overrides) -> dict:
    """A synthetic AIO session close payload — the s6a DONE_WHEN fixture.

    Carries the s1a content shape; the reflection reads ``session_date``/``slug`` (identity)
    and ``self_notes`` (the entry's content — the s1a type's self-notes field, which the
    deliverable says feeds the entry).
    """
    base = {
        "session_date": "2026-09-03",
        "slug": "wt_selfk_s6a_reflection_type_append",
        "waves_run": ["self_knowledge_layer/s0_pin_spec", "self_knowledge_layer/s6a"],
        "merged": ["s6a_reflection_type_append"],
        "parked": [],
        "open_threads": ["the reflection read command (s6b)"],
        "self_notes": "I re-derived the wave verdict by grep instead of reading a record.",
    }
    base.update(overrides)
    return base


def _payload(record) -> dict:
    return json.loads(record.text)


def _minimal_session(slug: str, session_date: str, self_notes: str) -> dict:
    """The exact session shape the CLI builds from its flags (slug/date/notes only)."""
    return {
        "slug": slug,
        "session_date": session_date,
        "self_notes": self_notes,
    }


class _FakeRedis:
    """In-memory stand-in for the knowledge-stream Redis (the session test double)."""

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


def _append(session: dict, tmp_path: Path, redis) -> ri.ReflectionAppendResult:
    """Run the append emission seam against a tmp artifact dir + a fake stream."""
    return ri.append_reflection(session, artifact_dir=tmp_path, connect_fn=lambda: redis)


# ── Extractor contract constants ────────────────────────────────


def test_extractor_constants():
    assert ri.SOURCE_TYPE == "reflection"
    assert ri.EXTRACTOR_VERSION == "reflection/v1"
    assert ri.ACTOR == "aio"
    assert ri.REVISION_FALLBACK == "reflection/unrevisioned"
    assert ri.CONTENT_FIELDS == ("session_date", "slug", "self_notes")
    # Registered as its own observation-family ADVISORY/[H] vocabulary row — minted beside the
    # session spine (meta_session) it is seeded by, never a fork of it.
    assert ri.SOURCE_TYPE in SOURCE_TYPES
    assert SOURCE_TYPES["reflection"] == SourceTypeSpec("observation", Authority.ADVISORY, "[H]")
    assert message_family("reflection") == "observation"
    assert "reflection" not in ACTUATION_TYPES


def test_reflection_ingestion_is_exported_from_the_knowledge_package():
    from agentic_dynamics.knowledge import reflection_ingestion

    assert reflection_ingestion is ri


# ── Provenance + the actor/scope carriage ───────────────────────


def test_record_provenance_is_advisory_h_observation_family():
    record = ri.derive_reflection_record(_session())
    assert record.source_type == "reflection"
    assert record.authority is Authority.ADVISORY
    assert record.evidence_class == "[H]"
    assert SOURCE_TYPES["reflection"].authority is Authority.ADVISORY
    assert message_family(record.source_type) == "observation"


def test_record_carries_aio_actor_and_org_root_scope():
    record = ri.derive_reflection_record(_session())
    # Scope is structural on the record: the org id as repository_id, the org-root AIO scope as
    # acl_scope — distinct from the corpus's "public" acl rows and any self-* cell scope.
    assert record.repository_id == REPOSITORY_ID
    assert record.acl_scope == "org:agentic-dynamics"
    # And self-describing in the body: actor + scope keys are part of the hashed payload.
    payload = _payload(record)
    assert payload["actor"] == "aio"
    assert payload["scope"] == record.acl_scope


def test_repository_override_rescopes_the_record():
    record = ri.derive_reflection_record(_session(), repository_id="another-org")
    assert record.repository_id == "another-org"
    assert record.acl_scope == "org:another-org"
    assert _payload(record)["scope"] == "org:another-org"


def test_cell_scoped_retrieval_never_resolves_the_aio_record():
    # Actor layering, deterministic at the type: the record lives at the org root, so the
    # retrieval hard pre-filter (scope_excluded) excludes it from any cell/workload query — a
    # self-* cell scope never equals the org id, so a cell agent cannot resolve the AIO's
    # private reflection records. Only an explicit org-root read sees them (the design's
    # "private to the controller-AIO pair" rule).
    from agentic_dynamics.knowledge.retrieval import scope_excluded

    record = ri.derive_reflection_record(_session())
    assert scope_excluded(record.repository_id, requested_scope="self-wt_03")
    assert scope_excluded(record.repository_id, requested_scope="org:agentic-dynamics/workload:x")
    assert not scope_excluded(record.repository_id, requested_scope="")
    assert not scope_excluded("", requested_scope="agentic-dynamics")


# ── The three content fields round-trip ─────────────────────────


def test_self_notes_feed_the_entry_and_content_round_trips():
    session = _session()
    record = ri.derive_reflection_record(session)

    artifact = record_to_artifact(record)
    event = record_to_event(record)
    extracted = extract_record(event, artifact)

    assert extracted.knowledge_id == record.knowledge_id
    assert extracted.content_hash == record.content_hash
    assert extracted.entity_id == record.entity_id
    assert extracted.acl_scope == record.acl_scope
    assert extracted.text == record.text

    # The entry's content is EXACTLY the s1a session's own self-notes, keyed by its slug/date.
    payload = _payload(extracted)
    assert payload["session_date"] == session["session_date"]
    assert payload["slug"] == session["slug"]
    assert payload["self_notes"] == session["self_notes"]

    # Standard pointer contract: content_hash = sha256(artifact), observed_at = the session's
    # own date (not the producer wall-clock).
    import hashlib

    assert event.knowledge_id == record.knowledge_id
    assert event.operation == "upsert"
    assert event.source_uri == f"file://experiments/results/kb/{record.knowledge_id}.json"
    assert event.content_hash == hashlib.sha256(artifact).hexdigest()
    assert event.observed_at == session["session_date"]
    assert extracted.observed_at == session["session_date"]


def test_full_dict_round_trip_is_lossless():
    from agentic_dynamics.knowledge.knowledge import KnowledgeRecord

    record = ri.derive_reflection_record(_session())
    restored = KnowledgeRecord.from_dict(record.to_dict())
    assert restored == record


def test_derive_and_build_delegate_to_the_same_record():
    session = _session()
    a = ri.derive_reflection_record(session)
    b = ri.build_reflection_record(session)
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


# ── Rerun-safe, session-keyed identity ──────────────────────────


def test_knowledge_id_is_rerun_safe_same_input_same_id():
    first = ri.derive_reflection_record(_session())
    second = ri.derive_reflection_record(_session())
    assert second.knowledge_id == first.knowledge_id
    assert second.entity_id == first.entity_id
    assert second.content_hash == first.content_hash


def test_changed_self_notes_rekey_knowledge_id_but_keep_one_entry_per_session():
    # Amended self-notes on the SAME session slot are a NEW VERSION of that session's ONE entry
    # (entity_id — the slug's logical identity — holds); the series never gets a second entry
    # for the same session. "One entry per session, never overwriting a prior session's" — the
    # version rule is per-session; OTHER sessions are other entities and never collide.
    first = ri.derive_reflection_record(_session())
    second = ri.derive_reflection_record(
        _session(self_notes="A second thought: I should read the wave verdict record.")
    )
    assert second.entity_id == first.entity_id
    assert second.knowledge_id != first.knowledge_id
    assert second.content_hash != first.content_hash
    assert second.logical_locator == first.logical_locator == "wt_selfk_s6a_reflection_type_append"


def test_two_sessions_are_two_entities_never_overwriting():
    # A different session (slug) is a different entity — the "second session appends a SECOND
    # entry" identity rule, at the type level: nothing about the two derivations can collide.
    first = ri.derive_reflection_record(_session(slug="wt_selfk_s6a_session_one"))
    second = ri.derive_reflection_record(_session(slug="wt_selfk_s6a_session_two"))
    assert first.entity_id != second.entity_id
    assert first.knowledge_id != second.knowledge_id
    assert first.source_uri == "reflection:wt_selfk_s6a_session_one"
    assert second.source_uri == "reflection:wt_selfk_s6a_session_two"


def test_identity_is_namespace_distinct_from_the_session_spine_and_decisions():
    # The reflection family is reflection:<slug> + reflection/v1 — a same-slug session close
    # (session:<slug> + session/v1) and a same-word decision (decision:<id> + decision/v1) are
    # different entities, never collisions on the artifact dir the two families share.
    spine = si.derive_session_record(_session())
    reflection = ri.derive_reflection_record(_session())
    assert spine.source_uri == "session:wt_selfk_s6a_reflection_type_append"
    assert reflection.source_uri == "reflection:wt_selfk_s6a_reflection_type_append"
    assert spine.extractor_version == "session/v1"
    assert reflection.extractor_version == "reflection/v1"
    assert spine.entity_id != reflection.entity_id
    assert spine.knowledge_id != reflection.knowledge_id

    from agentic_dynamics.knowledge import decision_ingestion as di

    decision = di.derive_decision_record(
        {
            "what": "reflect on self-notes at close",
            "why": "the reflection series needs an append path",
            "category": "scope",
            "decided_at": "2026-09-03T12:00:00+00:00",
        }
    )
    assert decision.source_uri != reflection.source_uri
    assert decision.entity_id != reflection.entity_id


def test_empty_self_notes_normalize_to_an_empty_notes_field():
    record = ri.derive_reflection_record(_session(self_notes="   "))
    assert _payload(record)["self_notes"] == ""
    assert record.source_type == "reflection"


# ── Validation + normalization ──────────────────────────────────


def test_missing_slug_raises_value_error():
    with pytest.raises(ValueError, match="slug"):
        ri.derive_reflection_record(_session(slug=""))


def test_missing_session_date_raises_value_error():
    with pytest.raises(ValueError, match="session_date"):
        ri.derive_reflection_record(_session(session_date=None))


# ═════════════════════════════════════════════════════════════════════════════
# The append path (s6a — the DONE_WHEN cases)
# ═════════════════════════════════════════════════════════════════════════════


class TestAppendPath:
    def test_append_lands_durable_artifact_and_pointer_event(self, tmp_path):
        """DONE_WHEN (1): a close appends its entry — BOTH halves land (artifact + event)."""
        session = _session()
        redis = _FakeRedis()
        result = _append(session, tmp_path, redis)

        assert result.status == "appended"
        assert result.warnings == []
        record = result.record
        assert record is not None

        # The durable per-record artifact is on disk at the canonical pointer path, and its
        # bytes are exactly the producer's deterministic artifact (content_hash verifies).
        assert result.artifact_path == tmp_path / f"{record.knowledge_id}.json"
        assert result.artifact_path.is_file()
        assert result.artifact_path.read_bytes() == record_to_artifact(record)

        # The pointer event landed on the change stream, naming the same record, and the
        # knowledge_id is checkpointed (the shared idempotence ledger) so a re-append is a no-op.
        assert len(redis.stream) == 1
        event = next(iter(redis.stream.values()))
        assert event["knowledge_id"] == record.knowledge_id
        assert event["entity_id"] == record.entity_id
        assert event["operation"] == "upsert"
        assert redis.hash.get(record.knowledge_id)

        # The entry that lands is the AIO's org-root reflection — actor + scope ride in the body.
        payload = _payload(record)
        assert payload["actor"] == "aio"
        assert payload["scope"] == "org:agentic-dynamics"
        assert payload["self_notes"] == session["self_notes"]

    def test_repeat_append_of_the_same_session_is_a_noop(self, tmp_path):
        """An identical re-append changes nothing (rerun-safe key) — the spine close's re-run
        cadence can call the append unconditionally without double-emitting."""
        session = _session()
        redis = _FakeRedis()
        first = _append(session, tmp_path, redis)
        second = _append(session, tmp_path, redis)

        assert first.status == "appended"
        assert first.entry_id
        assert second.status == "no-op"
        assert second.entry_id == ""
        assert second.warnings == []
        assert second.record.knowledge_id == first.record.knowledge_id
        assert len(redis.stream) == 1
        assert second.artifact_path.read_bytes() == first.artifact_path.read_bytes()

    def test_second_session_appends_a_second_entry_nothing_overwrites(self, tmp_path):
        """DONE_WHEN (2): a second session's close appends a SECOND entry — the series grows,
        nothing overwrites: the first session's entry is byte-for-byte untouched."""
        redis = _FakeRedis()
        first_session = _session(slug="wt_selfk_s6a_session_one", session_date="2026-09-03")
        second_session = _session(slug="wt_selfk_s6a_session_two", session_date="2026-09-04")

        first = _append(first_session, tmp_path, redis)
        second = _append(second_session, tmp_path, redis)

        assert first.status == "appended"
        assert second.status == "appended"
        # Two distinct entries, never a collision on id or file.
        assert second.record.knowledge_id != first.record.knowledge_id
        assert second.record.entity_id != first.record.entity_id
        assert len(redis.stream) == 2
        assert len(list(tmp_path.glob("*.json"))) == 2
        # The first entry survived the second append byte-for-byte (nothing overwrote it).
        assert first.artifact_path.read_bytes() == record_to_artifact(first.record)
        assert (
            first.artifact_path.read_bytes()
            == tmp_path.joinpath(f"{first.record.knowledge_id}.json").read_bytes()
        )

    def test_amended_self_notes_reappend_is_a_version_of_the_same_entry(self, tmp_path):
        """A re-close of the SAME session with amended notes writes a NEW VERSION of its one
        entry (entity holds, id re-keys) — never a second entry for the same session."""
        redis = _FakeRedis()
        first = _append(_session(self_notes="Original notes."), tmp_path, redis)
        second = _append(_session(self_notes="Amended notes after a rethink."), tmp_path, redis)

        assert first.status == "appended"
        assert second.status == "appended"
        assert second.record.entity_id == first.record.entity_id
        assert second.record.knowledge_id != first.record.knowledge_id
        # Both versions are durable (the amended write never deletes the first); the series
        # resolution collapses them to ONE current entry per session.
        assert len(list(tmp_path.glob("*.json"))) == 2

    def test_empty_self_notes_reflect_nothing(self, tmp_path):
        """A session with no self-notes appends NO entry — the honest skip, never a fabricated
        empty reflection that would read as one."""
        redis = _FakeRedis()
        result = _append(_session(self_notes="  "), tmp_path, redis)

        assert result.status == "no-notes"
        assert result.record is None
        assert result.artifact_path is None
        assert result.warnings == []
        assert len(redis.stream) == 0
        assert list(tmp_path.glob("*.json")) == []

    def test_producer_failure_is_a_warning_never_a_crash(self, tmp_path):
        """A downed stream degrades to a warning — the reflection entry is never lost."""

        def down():
            raise ConnectionError("knowledge stream is down")

        result = ri.append_reflection(_session(), artifact_dir=tmp_path, connect_fn=down)

        assert result.status == "degraded"
        assert result.warnings
        assert result.entry_id == ""
        # The durable artifact still landed — the reflection survives the stream outage.
        assert result.artifact_path.is_file()
        assert result.artifact_path.read_bytes() == record_to_artifact(result.record)

    def test_reappend_repairs_a_partial_failure_once_the_stream_returns(self, tmp_path):
        """An append that wrote the artifact but could not publish is COMPLETED by re-running —
        the checkpoint hash is the publish ledger, so the repair publishes exactly once."""

        def down():
            raise ConnectionError("knowledge stream is down")

        degraded = ri.append_reflection(_session(), artifact_dir=tmp_path, connect_fn=down)
        assert degraded.status == "degraded"

        redis = _FakeRedis()
        repaired = ri.append_reflection(_session(), artifact_dir=tmp_path, connect_fn=lambda: redis)

        assert repaired.status == "appended"
        assert repaired.record.knowledge_id == degraded.record.knowledge_id
        assert len(redis.stream) == 1  # exactly one event — the repair, never a duplicate

    def test_append_rejects_a_session_with_no_slug(self, tmp_path):
        redis = _FakeRedis()
        with pytest.raises(ValueError, match="slug"):
            ri.append_reflection(_session(slug=""), artifact_dir=tmp_path, connect_fn=lambda: redis)


# ═════════════════════════════════════════════════════════════════════════════
# The family (DONE_WHEN 3 — the series is retrievable as a family)
# ═════════════════════════════════════════════════════════════════════════════


class TestReflectionSeries:
    def test_series_is_retrievable_as_a_family(self, tmp_path):
        """DONE_WHEN (3): after two sessions close, the series resolves BOTH entries — one per
        session — in session_date order (the accumulated series the next session contemplates)."""
        redis = _FakeRedis()
        earlier = _session(slug="wt_selfk_s6a_session_one", session_date="2026-09-03")
        later = _session(slug="wt_selfk_s6a_session_two", session_date="2026-09-04")
        first = _append(earlier, tmp_path, redis)
        second = _append(later, tmp_path, redis)

        entries, warnings = ri.resolve_reflection_series(artifact_dir=tmp_path)
        assert warnings == []
        assert [entry[2]["slug"] for entry in entries] == [
            "wt_selfk_s6a_session_one",
            "wt_selfk_s6a_session_two",
        ]
        assert [entry[2]["session_date"] for entry in entries] == ["2026-09-03", "2026-09-04"]
        # Each resolved entry is the durable artifact the append wrote, in chronological order.
        assert entries[0][0].name == f"{first.record.knowledge_id}.json"
        assert entries[1][0].name == f"{second.record.knowledge_id}.json"

    def test_series_collapses_versions_to_one_current_entry_per_session(self, tmp_path):
        """An amended re-close leaves two durable versions of the SAME session; the series
        resolves the CURRENT one — the family is one entry per session, never one per version."""
        redis = _FakeRedis()
        original = _append(_session(self_notes="Original notes."), tmp_path, redis)
        amended = _append(_session(self_notes="Amended notes after a rethink."), tmp_path, redis)
        assert amended.record.entity_id == original.record.entity_id

        entries, warnings = ri.resolve_reflection_series(artifact_dir=tmp_path)
        assert warnings == []
        assert len(entries) == 1  # ONE current entry per session
        assert entries[0][0].name == f"{amended.record.knowledge_id}.json"
        assert entries[0][2]["self_notes"] == "Amended notes after a rethink."
        # The raw scan sees both durable versions — the collapse is the series RESOLUTION.
        raw, _ = ri.scan_reflection_records(artifact_dir=tmp_path)
        assert len(raw) == 2

    def test_scan_is_session_keyed(self, tmp_path):
        """scan_reflection_records retrieves by key (slug) — the session-keyed family read."""
        redis = _FakeRedis()
        target = _append(
            _session(slug="wt_selfk_s6a_session_one", session_date="2026-09-03"), tmp_path, redis
        )
        _append(
            _session(slug="wt_selfk_s6a_session_two", session_date="2026-09-04"), tmp_path, redis
        )

        by_key, _ = ri.scan_reflection_records(
            slug="wt_selfk_s6a_session_one", artifact_dir=tmp_path
        )
        assert len(by_key) == 1
        assert by_key[0][0].name == f"{target.record.knowledge_id}.json"
        assert by_key[0][2]["slug"] == "wt_selfk_s6a_session_one"

    def test_empty_dir_resolves_an_empty_series(self, tmp_path):
        """No entries (a fresh checkout with no KB yet) is an empty series — never an error."""
        entries, warnings = ri.resolve_reflection_series(artifact_dir=tmp_path)
        assert entries == []
        assert warnings == []
        raw, _ = ri.scan_reflection_records(artifact_dir=tmp_path)
        assert raw == []

    def test_scope_fence_excludes_foreign_repository_and_other_families(self, tmp_path):
        """SCOPE FENCE: the family read resolves ONLY the AIO's org-root reflection records — a
        cell/workload repository's reflection record, the session spine (a session/v1 artifact)
        and a decision artifact in the same dir are invisible (never candidates, never noise)."""
        closed = _append(
            _session(slug="wt_selfk_s6a_session_one", session_date="2026-09-03"),
            tmp_path,
            _FakeRedis(),
        )

        foreign = ri.derive_reflection_record(
            _session(slug="cell-wt_03", session_date="2026-09-03"), repository_id="another-org"
        )
        (tmp_path / f"{foreign.knowledge_id}.json").write_bytes(record_to_artifact(foreign))
        spine = si.derive_session_record(_session(session_date="2026-09-03"))
        (tmp_path / f"{spine.knowledge_id}.json").write_bytes(record_to_artifact(spine))
        from agentic_dynamics.knowledge import decision_ingestion as di

        decision = di.derive_decision_record(
            {
                "what": "reflect at close",
                "why": "to accumulate the series",
                "category": "scope",
                "decided_at": "2026-09-03T12:00:00+00:00",
            }
        )
        (tmp_path / f"{decision.knowledge_id}.json").write_bytes(record_to_artifact(decision))

        entries, warnings = ri.resolve_reflection_series(artifact_dir=tmp_path)
        assert warnings == []
        assert len(entries) == 1  # exactly the org-root AIO reflection, nothing else
        assert entries[0][0].name == f"{closed.record.knowledge_id}.json"

    def test_org_artifact_with_a_foreign_actor_is_warned_not_included(self, tmp_path):
        """A reflection/v1 artifact IN the org scope whose body actor is not the AIO's is
        surfaced as a warning — the honest signal a layering violation happened — never part of
        the series."""
        closed = _append(
            _session(slug="wt_selfk_s6a_session_one", session_date="2026-09-03"),
            tmp_path,
            _FakeRedis(),
        )

        data = json.loads(
            record_to_artifact(ri.derive_reflection_record(_session(slug="impostor")))
        )
        payload = json.loads(data["text"])
        payload["actor"] = "supervisor"  # the supervisor rail never writes AIO reflections
        data["text"] = json.dumps(payload)
        (tmp_path / "impostor.json").write_bytes(json.dumps(data, sort_keys=True).encode())

        entries, warnings = ri.resolve_reflection_series(artifact_dir=tmp_path)
        assert len(entries) == 1
        assert entries[0][0].name == f"{closed.record.knowledge_id}.json"
        assert any("impostor.json" in warning for warning in warnings)


# ═════════════════════════════════════════════════════════════════════════════
# The session-close wiring (s6a — the s1b close appends its entry)
# ═════════════════════════════════════════════════════════════════════════════


class TestSessionCloseAppends:
    def test_command_close_appends_its_reflection_entry(self, tmp_path, monkeypatch, capsys):
        """The REAL ``session close`` command appends the session's reflection entry — the spine
        record AND the reflection entry land in the same KB (the s6a DONE_WHEN at the cadence)."""
        import session_close as sc

        from agentic_dynamics.core import paths as core_paths
        from agentic_dynamics.knowledge import knowledge_stream as ks

        redis = _FakeRedis()
        monkeypatch.setattr(ks, "connect", lambda: redis)
        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)

        session = _minimal_session(
            "wt_selfk_s6a_reflection_type_append", "2026-09-03", "I re-derived the wave verdict."
        )
        argv = [
            "--slug",
            session["slug"],
            "--session-date",
            session["session_date"],
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
        out = capsys.readouterr().out
        assert "closed" in out
        assert "reflection: appended" in out

    def test_command_second_session_append_grows_the_series(self, tmp_path, monkeypatch, capsys):
        """DONE_WHEN (2) at the cadence: a SECOND session's close appends a SECOND reflection
        entry; the series (read back as a family) holds both, nothing overwrote the first."""
        import session_close as sc

        from agentic_dynamics.core import paths as core_paths
        from agentic_dynamics.knowledge import knowledge_stream as ks

        redis = _FakeRedis()
        monkeypatch.setattr(ks, "connect", lambda: redis)
        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)

        first_session = _minimal_session(
            "wt_selfk_s6a_session_one", "2026-09-03", "First session reflection."
        )
        second_session = _minimal_session(
            "wt_selfk_s6a_session_two", "2026-09-04", "Second session reflection."
        )
        for session in (first_session, second_session):
            assert (
                sc.main(
                    [
                        "--slug",
                        session["slug"],
                        "--session-date",
                        session["session_date"],
                        "--self-notes",
                        session["self_notes"],
                    ]
                )
                == 0
            )
        capsys.readouterr()

        entries, warnings = ri.resolve_reflection_series(artifact_dir=tmp_path)
        assert warnings == []
        assert [entry[2]["slug"] for entry in entries] == [
            "wt_selfk_s6a_session_one",
            "wt_selfk_s6a_session_two",
        ]
        # Nothing overwrote the first session's entry.
        assert (
            tmp_path / f"{ri.derive_reflection_record(first_session).knowledge_id}.json"
        ).is_file()

    def test_command_close_without_self_notes_appends_nothing(self, tmp_path, monkeypatch, capsys):
        """A close with no self-notes reflects nothing — only the spine record lands, and the
        report says so plainly (no-notes), never a fabricated empty entry."""
        import session_close as sc

        from agentic_dynamics.core import paths as core_paths
        from agentic_dynamics.knowledge import knowledge_stream as ks

        redis = _FakeRedis()
        monkeypatch.setattr(ks, "connect", lambda: redis)
        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)

        session = _minimal_session("wt_selfk_s6a_reflection_type_append", "2026-09-03", "")
        assert (
            sc.main(
                [
                    "--slug",
                    session["slug"],
                    "--session-date",
                    session["session_date"],
                ]
            )
            == 0
        )
        spine = si.derive_session_record(session)
        assert {path.name for path in tmp_path.glob("*.json")} == {f"{spine.knowledge_id}.json"}
        assert len(redis.stream) == 1
        out = capsys.readouterr().out
        assert "no self-notes" in out

    def test_command_identical_reclose_appends_nothing_twice(self, tmp_path, monkeypatch):
        """Re-running the close for the same session is rerun-safe on BOTH halves: the spine
        no-ops AND the reflection append no-ops — no duplicate reflection entry ever appears."""
        import session_close as sc

        from agentic_dynamics.core import paths as core_paths
        from agentic_dynamics.knowledge import knowledge_stream as ks

        redis = _FakeRedis()
        monkeypatch.setattr(ks, "connect", lambda: redis)
        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)

        session = _minimal_session(
            "wt_selfk_s6a_reflection_type_append", "2026-09-03", "I re-derived the wave verdict."
        )
        argv = [
            "--slug",
            session["slug"],
            "--session-date",
            session["session_date"],
            "--self-notes",
            session["self_notes"],
        ]
        assert sc.main(argv) == 0
        assert sc.main(argv) == 0
        assert len(redis.stream) == 2  # spine + reflection, exactly once each
        assert len(list(tmp_path.glob("*.json"))) == 2
        entries, warnings = ri.resolve_reflection_series(artifact_dir=tmp_path)
        assert warnings == []
        assert len(entries) == 1  # ONE entry for the session, never two


# ═════════════════════════════════════════════════════════════════════════════
# The read command (s6b — reflect --read renders the accumulated series)
# ═════════════════════════════════════════════════════════════════════════════


class TestReflectReadCommand:
    """The ``agentic-dynamics reflect --read`` command (CLI shell over the s6b read seam)."""

    def test_command_resolves_to_reflect_script(self):
        from agentic_dynamics import cli

        assert cli._resolve(["reflect"]) == ("reflect.py", [])
        assert cli._resolve(["reflect", "--read"]) == ("reflect.py", ["--read"])
        assert cli._resolve(["reflect", "--json"]) == ("reflect.py", ["--json"])
        assert (ROOT / "scripts" / "reflect.py").is_file()

    def test_command_renders_the_accumulated_series_in_order(self, tmp_path, monkeypatch, capsys):
        """DONE_WHEN (1): reflect --read renders the accumulated entries in chronological order —
        the round-trip from the REAL close command: two sessions close, the read shows both, the
        first is byte-for-byte the entry that session appended (never overwritten)."""
        import session_close as sc

        from agentic_dynamics.core import paths as core_paths
        from agentic_dynamics.knowledge import knowledge_stream as ks

        redis = _FakeRedis()
        monkeypatch.setattr(ks, "connect", lambda: redis)
        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)

        first_session = _minimal_session(
            "wt_selfk_s6a_session_one", "2026-09-03", "First session reflection."
        )
        second_session = _minimal_session(
            "wt_selfk_s6b_session_two", "2026-09-04", "Second session reflection."
        )
        for session in (first_session, second_session):
            assert (
                sc.main(
                    [
                        "--slug",
                        session["slug"],
                        "--session-date",
                        session["session_date"],
                        "--self-notes",
                        session["self_notes"],
                    ]
                )
                == 0
            )
        capsys.readouterr()

        import reflect as refl

        assert refl.main(["--read"]) == 0
        out = capsys.readouterr().out
        # Both sessions' reflections render, in the order the sessions happened (09-03 before
        # 09-04) — the accumulated series, not just the last close.
        first_pos = out.index("wt_selfk_s6a_session_one")
        second_pos = out.index("wt_selfk_s6b_session_two")
        assert first_pos < second_pos
        assert "2026-09-03" in out and "2026-09-04" in out
        assert "First session reflection." in out
        assert "Second session reflection." in out
        # The durable entries both survived — the first session's entry was never overwritten.
        assert (
            tmp_path / f"{ri.derive_reflection_record(first_session).knowledge_id}.json"
        ).is_file()

    def test_command_sorts_by_session_date_never_by_append_order(self, tmp_path, monkeypatch, capsys):
        """The order is the sessions' own dates (content), never the append/filesystem order: a
        later-dated session appended FIRST still renders after the earlier-dated one."""
        redis = _FakeRedis()
        # Appended in reverse session order — the read must render chronological (09-03 first).
        _append(
            _session(slug="wt_selfk_s6b_session_two", session_date="2026-09-04"),
            tmp_path,
            redis,
        )
        _append(
            _session(slug="wt_selfk_s6a_session_one", session_date="2026-09-03"),
            tmp_path,
            redis,
        )

        from agentic_dynamics.core import paths as core_paths

        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)
        import reflect as refl

        assert refl.main(["--read"]) == 0
        out = capsys.readouterr().out
        assert out.index("wt_selfk_s6a_session_one") < out.index("wt_selfk_s6b_session_two")

    def test_command_machine_report_carries_the_ordered_series(self, tmp_path, monkeypatch, capsys):
        """The machine reflect/v1 report names every entry with its content + durable identity,
        in session order, with the AIO actor/scope and an empty warning list."""
        redis = _FakeRedis()
        earlier = _append(
            _session(slug="wt_selfk_s6a_session_one", session_date="2026-09-03"),
            tmp_path,
            redis,
        )
        later = _append(
            _session(slug="wt_selfk_s6b_session_two", session_date="2026-09-04"),
            tmp_path,
            redis,
        )

        from agentic_dynamics.core import paths as core_paths

        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)
        import reflect as refl

        assert refl.main(["--read", "--json"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["schema"] == "reflect/v1"
        assert report["status"] == "read"
        assert report["count"] == 2
        assert report["actor"] == "aio"
        assert report["scope"] == "org:agentic-dynamics"
        assert report["warnings"] == []
        assert [entry["slug"] for entry in report["entries"]] == [
            "wt_selfk_s6a_session_one",
            "wt_selfk_s6b_session_two",
        ]
        assert [entry["session_date"] for entry in report["entries"]] == [
            "2026-09-03",
            "2026-09-04",
        ]
        assert report["entries"][0]["self_notes"] == json.loads(
            earlier.record.text
        )["self_notes"]
        assert report["entries"][0]["knowledge_id"] == earlier.record.knowledge_id
        assert report["entries"][1]["knowledge_id"] == later.record.knowledge_id
        assert report["entries"][0]["entity_id"] == earlier.record.entity_id
        assert report["entries"][1]["entity_id"] == later.record.entity_id
        assert report["entries"][0]["actor"] == "aio"
        assert report["entries"][0]["scope"] == "org:agentic-dynamics"

    def test_command_empty_series_renders_a_clear_empty_state(self, tmp_path, monkeypatch, capsys):
        """DONE_WHEN (2): no entries (a fresh checkout with no KB yet) renders a clear empty
        state — human and machine, exit 0, never an error, never a fabricated entry."""
        from agentic_dynamics.core import paths as core_paths

        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)
        import reflect as refl

        assert refl.main(["--read"]) == 0
        captured = capsys.readouterr()
        out, err = captured.out, captured.err
        assert "No reflections yet" in out
        assert "empty" in out
        assert "session close" in out  # the empty state names the command that seeds the series
        assert err == ""  # a clean empty read warns nothing

        assert refl.main(["--read", "--json"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["schema"] == "reflect/v1"
        assert report["status"] == "empty"
        assert report["count"] == 0
        assert report["entries"] == []
        assert report["warnings"] == []

    def test_command_read_seam_reports_an_empty_series(self, tmp_path):
        """The module read seam mirrors the command: an empty dir resolves ``empty``."""
        result = ri.read_reflection_series(artifact_dir=tmp_path)
        assert result.status == "empty"
        assert result.entries == []
        assert result.count == 0
        assert result.warnings == []
        assert "No reflections yet" in ri.render_reflection_series(result)

    def test_command_scope_fence_resolves_only_the_org_root_aio_series(self, tmp_path, monkeypatch, capsys):
        """SCOPE FENCE: reflect reads ONLY the AIO's org-root reflection records — a foreign
        repository's reflection, the session spine, and a decision artifact in the same dir are
        never candidates; an org-scope artifact whose body actor is not the AIO's is a warning on
        stderr, never part of the series."""
        closed = _append(
            _session(slug="wt_selfk_s6a_session_one", session_date="2026-09-03"),
            tmp_path,
            _FakeRedis(),
        )

        foreign = ri.derive_reflection_record(
            _session(slug="cell-wt_03", session_date="2026-09-03"), repository_id="another-org"
        )
        (tmp_path / f"{foreign.knowledge_id}.json").write_bytes(record_to_artifact(foreign))
        spine = si.derive_session_record(_session(session_date="2026-09-03"))
        (tmp_path / f"{spine.knowledge_id}.json").write_bytes(record_to_artifact(spine))
        from agentic_dynamics.knowledge import decision_ingestion as di

        decision = di.derive_decision_record(
            {
                "what": "reflect at close",
                "why": "to accumulate the series",
                "category": "scope",
                "decided_at": "2026-09-03T12:00:00+00:00",
            }
        )
        (tmp_path / f"{decision.knowledge_id}.json").write_bytes(record_to_artifact(decision))

        data = json.loads(
            record_to_artifact(ri.derive_reflection_record(_session(slug="impostor")))
        )
        payload = json.loads(data["text"])
        payload["actor"] = "supervisor"  # the supervisor rail never writes AIO reflections
        data["text"] = json.dumps(payload)
        (tmp_path / "impostor.json").write_bytes(json.dumps(data, sort_keys=True).encode())

        from agentic_dynamics.core import paths as core_paths

        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)
        import reflect as refl

        assert refl.main(["--read", "--json"]) == 0
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["status"] == "read"
        assert report["count"] == 1  # exactly the org-root AIO reflection, nothing else
        assert report["entries"][0]["slug"] == "wt_selfk_s6a_session_one"
        assert report["entries"][0]["knowledge_id"] == closed.record.knowledge_id
        assert "impostor.json" in captured.err  # the layering violation is a warning, never silent
        assert any("impostor.json" in w for w in report["warnings"])

