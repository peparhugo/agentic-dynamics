"""Tests for the decision-record type + command (decision_ingestion) — s2a of the
self_knowledge_layer wave.

Covers the s2a command cases (the DONE_WHEN): ``agentic-dynamics decision record`` writes a
retrievable-by-category record carrying all fields {what, why, alternatives, category,
decided_at, actor, run_id/candidate_sha when bound}; an identical re-record is a rerun-safe
no-op; a producer failure (downed knowledge stream) is a warning, never a crash — the durable
record still lands. Also covers the record type the command rides on: the ``decision``
source_type registered as an observation-family ADVISORY/[H] record (a decision IS an
observation with intent), minted beside the a5 observation family (prereg D-1's second option)
and org-root scoped so a cell agent's retrieval never resolves it.

Also covers the s2b emission cases (the s2b DONE_WHEN): the verified-command call sites —
``scripts/promote.py`` and ``scripts/publish_release.py`` — emit their own s2 decision record
(actor: ``verified_command``, org-root scope) bound to the run_id + candidate_sha the permanence
act acted on. Default-on and best-effort: a failed record never blocks the promote/publish.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from agentic_dynamics.knowledge import decision_ingestion as di
from agentic_dynamics.knowledge.knowledge import (
    SOURCE_TYPES,
    Authority,
    message_family,
)
from agentic_dynamics.knowledge.knowledge_ingestion import (
    REPOSITORY_ID,
    extract_record,
    record_to_artifact,
    record_to_event,
)
from agentic_dynamics.knowledge.session_ingestion import aio_acl_scope

ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = str(ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def _decision(**overrides) -> dict:
    """A synthetic AIO decision dict — the s2a DONE_WHEN fixture."""
    base = {
        "what": "park the fleet",
        "why": "the lane is dormant and burning ~$1.1/hr in idle orchestration",
        "alternatives": ["keep it live", "promote it"],
        "category": "park",
        "decided_at": "2026-09-03T12:00:00+00:00",
        "actor": "aio",
    }
    base.update(overrides)
    return base


def _payload(record) -> dict:
    return json.loads(record.text)


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


def _record(decision: dict, tmp_path: Path, redis) -> di.DecisionRecordResult:
    """Run the record emission seam against a tmp artifact dir + a fake stream."""
    return di.record_decision(decision, artifact_dir=tmp_path, connect_fn=lambda: redis)


# ── Extractor contract constants ────────────────────────────────


def test_extractor_constants():
    assert di.SOURCE_TYPE == "decision"
    assert di.EXTRACTOR_VERSION == "decision/v1"
    assert di.ACTOR == "aio"
    assert di.REVISION_FALLBACK == "decision/unrevisioned"
    assert di.DECISION_CATEGORIES == ("park", "model", "name", "scope")
    # The decision source_type is registered in the one vocabulary table, as an observation
    # family — a decision IS an observation with intent, never an actuation.
    assert di.SOURCE_TYPE in SOURCE_TYPES
    assert SOURCE_TYPES["decision"].authority is Authority.ADVISORY
    assert SOURCE_TYPES["decision"].evidence_class == "[H]"
    assert message_family("decision") == "observation"


def test_decision_ingestion_is_exported_from_the_knowledge_package():
    from agentic_dynamics.knowledge import decision_ingestion

    assert decision_ingestion is di


# ── Provenance + the actor/scope carriage ───────────────────────


def test_record_provenance_is_advisory_h_like_observation():
    record = di.derive_decision_record(_decision())
    assert record.source_type == "decision"
    assert record.authority is Authority.ADVISORY
    assert record.evidence_class == "[H]"


def test_record_carries_aio_actor_and_org_root_scope():
    record = di.derive_decision_record(_decision())
    # Scope is structural on the record: the org id as repository_id, the org-root AIO scope as
    # acl_scope — distinct from the corpus's "public" acl rows and from any self-* cell scope.
    assert record.repository_id == REPOSITORY_ID
    assert record.acl_scope == aio_acl_scope(REPOSITORY_ID)
    # And self-describing in the body: actor + scope keys are part of the hashed payload.
    payload = _payload(record)
    assert payload["actor"] == "aio"
    assert payload["scope"] == record.acl_scope


def test_repository_override_rescopes_the_record():
    record = di.derive_decision_record(_decision(), repository_id="another-org")
    assert record.repository_id == "another-org"
    assert record.acl_scope == "org:another-org"
    assert _payload(record)["scope"] == "org:another-org"


def test_cell_scoped_retrieval_excludes_the_aio_record():
    # Actor layering, deterministic at the type: the record lives at the org root (repository_id
    # "agentic-dynamics"), so the retrieval hard pre-filter (scope_excluded) excludes it from any
    # cell/workload query — a cell agent cannot resolve the AIO's decision records.
    from agentic_dynamics.knowledge.retrieval import scope_excluded

    record = di.derive_decision_record(_decision())
    assert scope_excluded(record.repository_id, requested_scope="self-wt_03")
    assert scope_excluded(record.repository_id, requested_scope="org:agentic-dynamics/workload:x")
    assert not scope_excluded(record.repository_id, requested_scope="")
    assert not scope_excluded("", requested_scope="agentic-dynamics")


def test_verified_command_actor_rides_the_same_org_root():
    # s2b emits at the verified-command call sites with actor "verified_command"; the scope stays
    # the org root (the record remains a controller/AIO read, never a cell's).
    record = di.derive_decision_record(_decision(actor="verified_command"))
    assert _payload(record)["actor"] == "verified_command"
    assert record.repository_id == REPOSITORY_ID
    assert record.acl_scope == aio_acl_scope(REPOSITORY_ID)


# ── The content fields round-trip ───────────────────────────────


def test_content_fields_round_trip_through_artifact_and_event():
    decision = _decision()
    record = di.derive_decision_record(decision)

    artifact = record_to_artifact(record)
    event = record_to_event(record)
    extracted = extract_record(event, artifact)

    assert extracted.knowledge_id == record.knowledge_id
    assert extracted.content_hash == record.content_hash
    assert extracted.entity_id == record.entity_id
    assert extracted.acl_scope == record.acl_scope
    assert extracted.text == record.text

    payload = _payload(extracted)
    assert payload["what"] == decision["what"]
    assert payload["why"] == decision["why"]
    assert payload["alternatives"] == decision["alternatives"]
    assert payload["category"] == decision["category"]
    assert payload["decided_at"] == decision["decided_at"]
    assert payload["actor"] == decision["actor"]

    # The standard pointer contract: content_hash is the sha256 of the artifact, the event names
    # the per-record artifact URI, observed_at round-trips the decision's own moment.
    assert event.knowledge_id == record.knowledge_id
    assert event.operation == "upsert"
    assert event.source_uri == f"file://experiments/results/kb/{record.knowledge_id}.json"
    assert event.source_revision == record.commit_sha == ""
    assert event.content_hash == hashlib.sha256(artifact).hexdigest()
    assert event.observed_at == decision["decided_at"]
    assert extracted.observed_at == decision["decided_at"]


def test_full_dict_round_trip_is_lossless():
    from agentic_dynamics.knowledge.knowledge import KnowledgeRecord

    record = di.derive_decision_record(_decision())
    restored = KnowledgeRecord.from_dict(record.to_dict())
    assert restored == record


def test_derive_and_build_delegate_to_the_same_record():
    decision = _decision()
    a = di.derive_decision_record(decision)
    b = di.build_decision_record(decision)
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
    first = di.derive_decision_record(_decision())
    second = di.derive_decision_record(_decision())
    assert second.knowledge_id == first.knowledge_id
    assert second.entity_id == first.entity_id
    assert second.content_hash == first.content_hash


def test_changed_rationale_rekeys_knowledge_id_but_not_entity_id():
    first = di.derive_decision_record(_decision())
    second = di.derive_decision_record(_decision(why="changed my mind"))
    # A changed body is a NEW immutable knowledge_id for the SAME decision event slot.
    assert second.entity_id == first.entity_id
    assert second.knowledge_id != first.knowledge_id
    assert second.content_hash != first.content_hash


def test_re_decision_at_a_new_moment_is_a_new_independent_fact():
    # Identity folds decided_at (observation/actuation per-event contract): deciding the SAME
    # subject at a NEW moment is a NEW decision, never a collision/overwrite of the earlier one.
    first = di.derive_decision_record(_decision())
    later = di.derive_decision_record(_decision(decided_at="2026-09-04T12:00:00+00:00"))
    assert later.entity_id != first.entity_id
    assert later.knowledge_id != first.knowledge_id


def test_identity_is_namespace_distinct_from_observation_and_session():
    # The decision family is decision:<id> + decision/v1 — never colliding with the observation
    # producer's observation:<assessment> or the session spine's session:<slug> on identity.
    from agentic_dynamics.knowledge.session_ingestion import build_session_record

    decision = di.derive_decision_record(_decision())
    session = build_session_record(
        {
            "session_date": "2026-09-03",
            "slug": decision.logical_locator,
            "waves_run": [],
        }
    )
    assert decision.source_uri.startswith("decision:")
    assert decision.extractor_version == "decision/v1"
    assert session.source_uri.startswith("session:")
    assert decision.entity_id != session.entity_id
    assert decision.knowledge_id != session.knowledge_id


# ── Bindings + normalization ────────────────────────────────────


def test_bound_run_id_and_candidate_sha_ride_in_the_payload():
    record = di.derive_decision_record(
        _decision(run_id="run-abc123", candidate_sha="0123456789abcdef0123456789abcdef01234567")
    )
    payload = _payload(record)
    assert payload["run_id"] == "run-abc123"
    assert payload["candidate_sha"] == "0123456789abcdef0123456789abcdef01234567"


def test_unbound_decision_omits_the_binding_keys():
    payload = _payload(di.derive_decision_record(_decision()))
    assert "run_id" not in payload
    assert "candidate_sha" not in payload


def test_alternatives_normalize_and_keep_caller_order():
    record = di.derive_decision_record(_decision(alternatives=("keep it live", "promote it")))
    assert _payload(record)["alternatives"] == ["keep it live", "promote it"]
    record = di.derive_decision_record(_decision(alternatives="single"))
    assert _payload(record)["alternatives"] == ["single"]


# ── Validation ──────────────────────────────────────────────────


def test_missing_what_raises_value_error():
    with pytest.raises(ValueError, match="what"):
        di.derive_decision_record(_decision(what=""))


def test_missing_category_raises_value_error():
    with pytest.raises(ValueError, match="category"):
        di.derive_decision_record(_decision(category=None))


def test_missing_decided_at_raises_value_error():
    with pytest.raises(ValueError, match="decided_at"):
        di.derive_decision_record(_decision(decided_at=""))


def test_unknown_category_is_accepted_but_retrievable():
    # Categories are open by design (the --category ellipsis); the canonical tuple is
    # documentation, and retrieval is exact-string on whatever category was recorded.
    record = di.derive_decision_record(_decision(category="architecture"))
    assert _payload(record)["category"] == "architecture"


# ═════════════════════════════════════════════════════════════════════════════
# s2a — the decision-record emission seam (record_decision) + command cases
# ═════════════════════════════════════════════════════════════════════════════


class TestRecordDecision:
    def test_record_writes_durable_artifact_and_pointer_event(self, tmp_path):
        """DONE_WHEN (1): the record lands BOTH halves — artifact and event."""
        decision = _decision()
        redis = _FakeRedis()
        result = _record(decision, tmp_path, redis)

        assert result.status == "recorded"
        assert result.warnings == []
        record = result.record

        assert result.artifact_path == tmp_path / f"{record.knowledge_id}.json"
        assert result.artifact_path.is_file()
        assert result.artifact_path.read_bytes() == record_to_artifact(record)

        assert len(redis.stream) == 1
        event = next(iter(redis.stream.values()))
        assert event["knowledge_id"] == record.knowledge_id
        assert event["entity_id"] == record.entity_id
        assert event["operation"] == "upsert"
        assert redis.hash.get(record.knowledge_id)

        payload = _payload(record)
        assert payload["actor"] == "aio"
        assert payload["scope"] == "org:agentic-dynamics"
        assert record.acl_scope == payload["scope"]

    def test_repeat_record_of_the_same_decision_is_a_noop(self, tmp_path):
        """DONE_WHEN (2): re-recording an identical decision is a rerun-safe no-op."""
        decision = _decision()
        redis = _FakeRedis()
        first = _record(decision, tmp_path, redis)
        second = _record(decision, tmp_path, redis)

        assert first.status == "recorded"
        assert first.entry_id
        assert second.status == "no-op"
        assert second.entry_id == ""
        assert second.warnings == []
        assert second.record.knowledge_id == first.record.knowledge_id
        assert len(redis.stream) == 1
        assert second.artifact_path.read_bytes() == first.artifact_path.read_bytes()

    def test_record_of_a_changed_decision_body_is_a_new_version_not_a_noop(self, tmp_path):
        redis = _FakeRedis()
        first = _record(_decision(), tmp_path, redis)
        second = _record(_decision(why="changed my mind"), tmp_path, redis)

        assert first.status == "recorded"
        assert second.status == "recorded"
        assert second.record.entity_id == first.record.entity_id
        assert second.record.knowledge_id != first.record.knowledge_id
        assert len(redis.stream) == 2

    def test_producer_failure_is_a_warning_never_a_crash(self, tmp_path):
        """DONE_WHEN (3): a downed stream degrades to a warning — the record is never lost."""

        def down():
            raise ConnectionError("knowledge stream is down")

        result = di.record_decision(_decision(), artifact_dir=tmp_path, connect_fn=down)

        assert result.status == "degraded"
        assert result.warnings
        assert result.entry_id == ""
        assert result.artifact_path.is_file()
        assert result.artifact_path.read_bytes() == record_to_artifact(result.record)

    def test_rerecord_repairs_a_partial_failure_once_the_stream_returns(self, tmp_path):
        def down():
            raise ConnectionError("knowledge stream is down")

        degraded = di.record_decision(_decision(), artifact_dir=tmp_path, connect_fn=down)
        assert degraded.status == "degraded"

        redis = _FakeRedis()
        repaired = di.record_decision(_decision(), artifact_dir=tmp_path, connect_fn=lambda: redis)

        assert repaired.status == "recorded"
        assert repaired.record.knowledge_id == degraded.record.knowledge_id
        assert len(redis.stream) == 1

    def test_record_rejects_a_decision_with_no_what(self, tmp_path):
        redis = _FakeRedis()
        with pytest.raises(ValueError, match="what"):
            di.record_decision(_decision(what=""), artifact_dir=tmp_path, connect_fn=lambda: redis)


# ═════════════════════════════════════════════════════════════════════════════
# s2a — retrievable-by-category (the read seam)
# ═════════════════════════════════════════════════════════════════════════════


class TestRetrievalByCategory:
    def test_records_are_retrievable_by_category(self, tmp_path):
        redis = _FakeRedis()
        _record(_decision(what="park the fleet", category="park"), tmp_path, redis)
        _record(_decision(what="flash over sonnet", category="model"), tmp_path, redis)

        park, park_warnings = di.scan_decision_records(category="park", artifact_dir=tmp_path)
        assert park_warnings == []
        assert len(park) == 1
        assert park[0][2]["what"] == "park the fleet"
        assert park[0][2]["category"] == "park"

        model, _ = di.scan_decision_records(category="model", artifact_dir=tmp_path)
        assert len(model) == 1
        assert model[0][2]["what"] == "flash over sonnet"

        none, _ = di.scan_decision_records(category="scope", artifact_dir=tmp_path)
        assert none == []

    def test_scan_without_category_returns_all_org_decision_records(self, tmp_path):
        redis = _FakeRedis()
        _record(_decision(what="park the fleet", category="park"), tmp_path, redis)
        _record(_decision(what="flash over sonnet", category="model"), tmp_path, redis)

        all_records, warnings = di.scan_decision_records(artifact_dir=tmp_path)
        assert warnings == []
        assert len(all_records) == 2

    def test_foreign_and_other_family_artifacts_are_not_candidates(self, tmp_path):
        redis = _FakeRedis()
        _record(_decision(what="park the fleet", category="park"), tmp_path, redis)

        # A decision/v1 record of ANOTHER repository is foreign, never a candidate.
        foreign = di.derive_decision_record(
            _decision(what="cell decision"), repository_id="self-wt_03"
        )
        (tmp_path / f"{foreign.knowledge_id}.json").write_bytes(record_to_artifact(foreign))

        # A session/v1 artifact (same org, different family) is foreign by extractor_version.
        from agentic_dynamics.knowledge.session_ingestion import build_session_record

        session = build_session_record(
            {"session_date": "2026-09-03", "slug": "wt_selfk_s2a", "waves_run": []}
        )
        (tmp_path / f"{session.knowledge_id}.json").write_bytes(record_to_artifact(session))

        # An undecodable file is foreign.
        (tmp_path / "not-json.json").write_bytes(b"{")

        records, warnings = di.scan_decision_records(category="park", artifact_dir=tmp_path)
        assert warnings == []
        assert len(records) == 1
        assert records[0][2]["what"] == "park the fleet"

    def test_org_decision_artifact_with_a_foreign_scope_is_warned_not_selected(self, tmp_path):
        _record(_decision(what="park the fleet", category="park"), tmp_path, _FakeRedis())

        data = json.loads(record_to_artifact(di.derive_decision_record(_decision(what="impostor"))))
        payload = json.loads(data["text"])
        payload["scope"] = "self-wt_03"  # a layering violation — not the org root
        data["text"] = json.dumps(payload)
        (tmp_path / "impostor.json").write_bytes(json.dumps(data, sort_keys=True).encode())

        records, warnings = di.scan_decision_records(artifact_dir=tmp_path)
        assert len(records) == 1
        assert records[0][2]["what"] == "park the fleet"
        assert any("impostor.json" in warning for warning in warnings)

    def test_round_trip_record_then_scan_is_exact(self, tmp_path):
        decision = _decision()
        result = _record(decision, tmp_path, _FakeRedis())

        records, warnings = di.scan_decision_records(category="park", artifact_dir=tmp_path)
        assert warnings == []
        assert len(records) == 1
        path, artifact, payload = records[0]
        assert path == result.artifact_path
        assert payload == _payload(result.record)
        # The decoded body is byte-identical to the recorded record's own canonical payload.
        assert payload == json.loads(result.record.text)


# ═════════════════════════════════════════════════════════════════════════════
# s2a — the ``agentic-dynamics decision record`` command (CLI shell)
# ═════════════════════════════════════════════════════════════════════════════


class TestDecisionRecordCommand:
    def test_command_resolves_to_decision_record_script(self):
        from agentic_dynamics import cli

        assert cli._resolve(["decision", "record"]) == ("decision_record.py", [])
        assert (ROOT / "scripts" / "decision_record.py").is_file()

    def test_command_end_to_end_writes_into_the_kb(self, tmp_path, monkeypatch, capsys):
        """Run the REAL command against a fake stream + tmp artifact dir: artifact + event land."""
        from agentic_dynamics.core import paths as core_paths
        from agentic_dynamics.knowledge import knowledge_stream as ks

        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import decision_record as dr

        redis = _FakeRedis()
        monkeypatch.setattr(ks, "connect", lambda: redis)
        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)

        rc = dr.main(
            [
                "--what",
                "park the fleet",
                "--why",
                "the lane is dormant",
                "--alternatives",
                "keep it live, promote it",
                "--category",
                "park",
                "--decided-at",
                "2026-09-03T12:00:00+00:00",
            ]
        )
        assert rc == 0
        assert len(redis.stream) == 1
        artifacts = list(tmp_path.glob("*.json"))
        assert len(artifacts) == 1

        record = di.derive_decision_record(
            {
                "what": "park the fleet",
                "why": "the lane is dormant",
                "alternatives": ["keep it live", "promote it"],
                "category": "park",
                "decided_at": "2026-09-03T12:00:00+00:00",
            }
        )
        assert artifacts[0].name == f"{record.knowledge_id}.json"
        assert next(iter(redis.stream.values()))["knowledge_id"] == record.knowledge_id
        assert "recorded" in capsys.readouterr().out

    def test_command_rerun_is_a_noop(self, tmp_path, monkeypatch):
        from agentic_dynamics.core import paths as core_paths
        from agentic_dynamics.knowledge import knowledge_stream as ks

        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import decision_record as dr

        redis = _FakeRedis()
        monkeypatch.setattr(ks, "connect", lambda: redis)
        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)

        argv = [
            "--what",
            "park the fleet",
            "--category",
            "park",
            "--decided-at",
            "2026-09-03T12:00:00+00:00",
        ]
        assert dr.main(argv) == 0
        assert dr.main(argv) == 0
        assert len(redis.stream) == 1
        assert len(list(tmp_path.glob("*.json"))) == 1

    def test_command_downed_stream_is_a_warning_and_exits_zero(self, tmp_path, monkeypatch, capsys):
        from agentic_dynamics.core import paths as core_paths
        from agentic_dynamics.knowledge import knowledge_stream as ks

        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import decision_record as dr

        def down():
            raise ConnectionError("knowledge stream is down")

        monkeypatch.setattr(ks, "connect", down)
        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)

        rc = dr.main(
            ["--what", "park the fleet", "--category", "park", "--decided-at", "2026-09-03"]
        )
        assert rc == 0  # never a crash
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()
        assert "degraded" in captured.out or "NOT published" in captured.out
        assert len(list(tmp_path.glob("*.json"))) == 1

    def test_command_missing_what_is_a_usage_error(self, capsys):
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import decision_record as dr

        with pytest.raises(SystemExit) as exc:
            dr.main(["--category", "park"])
        assert exc.value.code == 2  # argparse usage error

    def test_command_emits_json_report_with_all_fields(self, tmp_path, monkeypatch, capsys):
        from agentic_dynamics.core import paths as core_paths
        from agentic_dynamics.knowledge import knowledge_stream as ks

        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import decision_record as dr

        redis = _FakeRedis()
        monkeypatch.setattr(ks, "connect", lambda: redis)
        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path)

        rc = dr.main(
            [
                "--what",
                "flash over sonnet",
                "--why",
                "it converges in ~1 wave on in-process work",
                "--alternatives",
                "sonnet, terra",
                "--category",
                "model",
                "--decided-at",
                "2026-09-03T12:00:00+00:00",
                "--run-id",
                "run-c8d98f56a124",
                "--candidate-sha",
                "0123456789abcdef0123456789abcdef01234567",
                "--json",
            ]
        )
        assert rc == 0
        report = json.loads(capsys.readouterr().out)
        assert report["schema"] == "decision-record/v1"
        assert report["status"] == "recorded"
        assert report["what"] == "flash over sonnet"
        assert report["category"] == "model"
        assert report["decided_at"] == "2026-09-03T12:00:00+00:00"
        assert report["actor"] == "aio"
        assert report["knowledge_id"]
        assert report["entity_id"]
        assert report["warnings"] == []

        # And the full payload (bindings included) is retrievable by category from the artifact.
        records, warnings = di.scan_decision_records(category="model", artifact_dir=tmp_path)
        assert warnings == []
        assert len(records) == 1
        payload = records[0][2]
        assert payload["what"] == "flash over sonnet"
        assert payload["run_id"] == "run-c8d98f56a124"
        assert payload["candidate_sha"] == "0123456789abcdef0123456789abcdef01234567"


# ═════════════════════════════════════════════════════════════════════════════
# s2b — the verified-command call-site emission cases (promote.py + publish_release.py)
# ═════════════════════════════════════════════════════════════════════════════

# The s2b DONE_WHEN: a promote invocation emits a decision record bound to its run_id +
# candidate_sha; a publish invocation emits its own. The emissions are DEFAULT-ON (wired inside
# the verified commands, actor ``verified_command``, org-root scope) and BEST-EFFORT (a failed
# record never blocks the promote/publish). The seams are injectable on purpose — the same
# pattern the a5 emitters use — so the tests drive the REAL call-site functions while pointing
# the record seam at a tmp artifact dir + a fake stream (hermetic: nothing touches the live KB).


def _noop_emitter(label=""):
    def emit_decision(decision):
        return {"observation_id": f"{label}-obs", "entry_ids": []}

    def emit_act(decision, *, causes):
        return {"actuation_id": f"{label}-act", "entry_ids": []}

    return emit_decision, emit_act


class _RecordingRecordSeam:
    """A record_decision seam that captures every decision AND lands it for real (tmp + fake).

    The s2b tests need both halves: proof that the call site INVOKED the seam with a decision
    bound to run_id + candidate_sha (the captured dict), and proof that such a decision is a
    real org-root decision record (the durable artifact the seam's delegate writes). The
    delegate is ``decision_ingestion.record_decision`` against a tmp artifact dir + fake redis,
    exactly as the s2a seam tests use.
    """

    def __init__(self, artifact_dir: Path, redis):
        self.artifact_dir = artifact_dir
        self.redis = redis
        self.decisions: list[dict] = []

    def __call__(self, decision: dict) -> dict:
        self.decisions.append(dict(decision))
        result = di.record_decision(
            decision, artifact_dir=self.artifact_dir, connect_fn=lambda: self.redis
        )
        return {
            "status": result.status,
            "knowledge_id": result.record.knowledge_id,
            "artifact": str(result.artifact_path),
            "warnings": list(result.warnings),
        }


def _candidate_worktree(tmp_path: Path) -> tuple[Path, str]:
    """A real git worktree: main at a base commit + a feature branch with one [workflow] commit.

    Mirrors ``test_aio_emission``'s fixture: the promote real path needs a candidate whose
    base..HEAD diff is non-empty and whose HEAD is the ledger's ``git_sha``.
    """
    wt = tmp_path / "candidate"
    wt.mkdir()
    for argv in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
    ):
        subprocess.run(argv, cwd=wt, check=True)
    (wt / "base.py").write_text("BASE = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=wt, check=True)
    subprocess.run(["git", "branch", "-m", "main"], cwd=wt, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "feature"], cwd=wt, check=True)
    (wt / "calc.py").write_text("def add(a, b): return a + b\n")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "[workflow] scope — g"], cwd=wt, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True, check=True
    ).stdout.strip()
    return wt, head


def _promote_args(tmp_path: Path, wt: Path, ledger: dict, **overrides):
    from types import SimpleNamespace

    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps(ledger))
    args = {
        "spec": "promote_emit_test",
        "workdir": str(wt),
        "ledger": str(ledger_path),
        "approval": None,
        "base": "main",
        "operator": "drseuss",
        "dry_run": False,
    }
    args.update(overrides)
    return SimpleNamespace(**args)


def _promote_ledger(head_sha: str, **overrides) -> dict:
    data = {
        "spec_name": "promote_emit_test",
        "spec_id": "promote_emit_test@0.1",
        "git_sha": head_sha,
        "ok": True,
        "state": "succeeded",
        "total_cost_usd": 0.001,
        "phases": [
            {"phase": "scope", "kind": "agent", "status": "ok",
             "commit_hash": head_sha, "test_executed_success": None},
            {"phase": "verify", "kind": "test", "status": "ok",
             "commit_hash": head_sha, "test_executed_success": True},
        ],
    }
    data.update(overrides)
    return data


class TestPromoteEmission:
    def test_promote_invocation_emits_a_decision_record_bound_to_run_and_candidate(self, tmp_path):
        """s2b DONE_WHEN (promote): running the real promote path records an org-root decision.

        The decision the seam receives must carry actor=verified_command and be bound to the
        ledger's run_id + the candidate sha the promotion acted on; the durable artifact must be
        a real ``decision``/``decision/v1`` record retrievable by category.
        """
        from promote import _run_promotion

        wt, head = _candidate_worktree(tmp_path)
        ledger = _promote_ledger(head)
        redis = _FakeRedis()
        seam = _RecordingRecordSeam(tmp_path / "kb", redis)
        emit_decision, emit_act = _noop_emitter("promote")

        pushes: list = []

        def fake_push(workdir, base, subject, candidate):
            pushes.append((str(workdir), base, subject, candidate))
            return "feedfacefeedfacefeedface"

        _run_promotion(
            _promote_args(tmp_path, wt, ledger),
            push=fake_push, emit_decision=emit_decision, emit_act=emit_act,
            record_decision=seam,
        )

        assert len(pushes) == 1  # the promotion happened
        # The emission seam was invoked exactly once, with a decision bound to the run + candidate.
        assert len(seam.decisions) == 1
        decision = seam.decisions[0]
        assert decision["actor"] == "verified_command"
        assert decision["run_id"] == "promote_emit_test@0.1"
        assert decision["candidate_sha"] == head
        assert decision["category"] == "promote"
        assert "promote" in decision["what"]

        # And the recorded record is a real org-root decision artifact, retrievable by category.
        records, warnings = di.scan_decision_records(category="promote", artifact_dir=tmp_path / "kb")
        assert warnings == []
        assert len(records) == 1
        payload = records[0][2]
        assert payload["actor"] == "verified_command"
        assert payload["run_id"] == "promote_emit_test@0.1"
        assert payload["candidate_sha"] == head
        assert payload["scope"] == aio_acl_scope(REPOSITORY_ID)

    def test_failed_record_never_blocks_a_verified_promotion(self, tmp_path):
        """s2b best-effort: a raising record seam cannot stop the push (the durable act)."""
        from promote import _run_promotion

        wt, head = _candidate_worktree(tmp_path)
        ledger = _promote_ledger(head)
        emit_decision, emit_act = _noop_emitter("promote")
        pushes: list = []

        def fake_push(workdir, base, subject, candidate):
            pushes.append(candidate)
            return "feedfacefeedfacefeedface"

        def boom(decision):
            raise RuntimeError("record seam exploded")

        # must not raise — the promotion proceeds even though the record failed.
        _run_promotion(
            _promote_args(tmp_path, wt, ledger),
            push=fake_push, emit_decision=emit_decision, emit_act=emit_act,
            record_decision=boom,
        )
        assert len(pushes) == 1

    def test_promote_dry_run_emits_no_decision_record(self, tmp_path):
        """A dry run is a plan, not a permanence decision — no s2b record is emitted."""
        from promote import _run_promotion

        wt, head = _candidate_worktree(tmp_path)
        ledger = _promote_ledger(head)
        calls: list = []
        emit_decision, emit_act = _noop_emitter("promote")

        _run_promotion(
            _promote_args(tmp_path, wt, ledger, dry_run=True),
            push=lambda *a, **kw: (_ for _ in ()).throw(AssertionError("no push on dry run")),
            emit_decision=emit_decision, emit_act=emit_act,
            record_decision=lambda d: calls.append(d) or {},
        )
        assert calls == []  # nothing recorded, nothing emitted

    def test_default_on_seam_is_the_real_producer(self, tmp_path, monkeypatch):
        """Default-on proof: with NO record_decision injected, the promote still records.

        The real default seam (``_default_decision_record`` → ``decision_ingestion.record_decision``)
        runs; pointing the KB artifact dir + stream at a tmp dir + fake redis keeps it hermetic
        while proving the emission is armed by default, not gated behind a flag or an injectable.
        """
        from promote import _run_promotion

        from agentic_dynamics.core import paths as core_paths
        from agentic_dynamics.knowledge import knowledge_stream as ks

        wt, head = _candidate_worktree(tmp_path)
        ledger = _promote_ledger(head)
        redis = _FakeRedis()
        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path / "kb")
        monkeypatch.setattr(ks, "connect", lambda: redis)
        emit_decision, emit_act = _noop_emitter("promote")

        pushes: list = []

        def fake_push(workdir, base, subject, candidate):
            pushes.append(candidate)
            return "feedfacefeedfacefeedface"

        # record_decision NOT injected → the default seam runs for real.
        _run_promotion(
            _promote_args(tmp_path, wt, ledger),
            push=fake_push, emit_decision=emit_decision, emit_act=emit_act,
        )
        assert len(pushes) == 1
        records, warnings = di.scan_decision_records(category="promote", artifact_dir=tmp_path / "kb")
        assert warnings == []
        assert len(records) == 1
        payload = records[0][2]
        assert payload["actor"] == "verified_command"
        assert payload["run_id"] == "promote_emit_test@0.1"
        assert payload["candidate_sha"] == head


def _publish_env(tmp_path: Path, monkeypatch) -> Path:
    """A ready real-publish-path environment (mirrors test_aio_emission's fixture)."""
    import datetime

    import publish_release as pr_mod

    from agentic_dynamics.control import publication as pub
    from agentic_dynamics.control.control_db import ControlDB

    db_path = tmp_path / "control.db"
    with ControlDB.open(db_path) as db:
        for proj in ("registry", "chroma", "neo4j"):
            db.record_watermark(
                proj, last_event_id="e1", source_head_event_id="e1",
                lag_events=0,
                last_success_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<p>1,027 story sessions</p>")
    (site / "data.js").write_text(
        "window.DYNAMICS_DATA = " + json.dumps({"public_statistics": {"story_sessions": 1027}}) + ";\n"
    )
    monkeypatch.setattr(pr_mod, "read_head_sha", lambda: "deadbeef1234567890abcdef")
    monkeypatch.setattr(pub, "SITE_ROOT", site)
    monkeypatch.setattr(pub, "DATA_JS", site / "data.js")
    return db_path


class TestPublishEmission:
    def test_publish_invocation_emits_a_decision_record_bound_to_run_and_candidate(
        self, tmp_path, monkeypatch
    ):
        """s2b DONE_WHEN (publish): a real publish path records its own org-root decision.

        The decision the seam receives must carry actor=verified_command, the --run-id binding
        and the candidate sha being published; the durable artifact is retrievable by category.
        """
        import publish_release as pr_mod

        db_path = _publish_env(tmp_path, monkeypatch)
        redis = _FakeRedis()
        seam = _RecordingRecordSeam(tmp_path / "kb", redis)
        emit_decision, emit_act = _noop_emitter("publish")

        def deploy(host):
            return pr_mod.DeployOutcome(host, True, f"rel-{host.role}", "")

        rc = pr_mod.main(
            ["--candidate-sha", "deadbeef", "--run-id", "publish_run_9",
             "--operator", "operator-test", "--db", str(db_path)],
            deployer=deploy, builder=lambda: (True, "built"),
            live_checker=lambda host, receipt: "",
            emit_decision=emit_decision, emit_act=emit_act,
            record_decision=seam,
        )
        assert rc == pr_mod.EXIT_OK
        assert len(seam.decisions) == 1
        decision = seam.decisions[0]
        assert decision["actor"] == "verified_command"
        assert decision["run_id"] == "publish_run_9"
        assert decision["candidate_sha"] == "deadbeef"
        assert decision["category"] == "publish"
        assert "publish" in decision["what"]

        records, warnings = di.scan_decision_records(category="publish", artifact_dir=tmp_path / "kb")
        assert warnings == []
        assert len(records) == 1
        payload = records[0][2]
        assert payload["actor"] == "verified_command"
        assert payload["run_id"] == "publish_run_9"
        assert payload["candidate_sha"] == "deadbeef"
        assert payload["scope"] == aio_acl_scope(REPOSITORY_ID)

    def test_failed_record_never_blocks_a_verified_publish(self, tmp_path, monkeypatch):
        """s2b best-effort: a raising record seam cannot stop the deploy."""
        import publish_release as pr_mod

        db_path = _publish_env(tmp_path, monkeypatch)
        emit_decision, emit_act = _noop_emitter("publish")

        def deploy(host):
            return pr_mod.DeployOutcome(host, True, f"rel-{host.role}", "")

        def boom(decision):
            raise RuntimeError("record seam exploded")

        rc = pr_mod.main(
            ["--candidate-sha", "deadbeef", "--operator", "operator-test", "--db", str(db_path)],
            deployer=deploy, builder=lambda: (True, "built"),
            live_checker=lambda host, receipt: "",
            emit_decision=emit_decision, emit_act=emit_act,
            record_decision=boom,
        )
        assert rc == pr_mod.EXIT_OK  # published despite the record failure

    def test_publish_dry_run_emits_no_decision_record(self, tmp_path, monkeypatch):
        """A dry run is a plan, not a permanence decision — no s2b record is emitted."""
        import publish_release as pr_mod

        db_path = _publish_env(tmp_path, monkeypatch)
        calls: list = []
        emit_decision, emit_act = _noop_emitter("publish")

        def deploy(host):
            return pr_mod.DeployOutcome(host, True, "rel", "")

        rc = pr_mod.main(
            ["--candidate-sha", "deadbeef", "--dry-run", "--db", str(db_path)],
            deployer=deploy, builder=lambda: (True, "built"),
            live_checker=lambda host, receipt: "",
            emit_decision=emit_decision, emit_act=emit_act,
            record_decision=lambda d: calls.append(d) or {},
        )
        assert rc == pr_mod.EXIT_OK
        assert calls == []  # nothing recorded on a dry run

    def test_default_on_seam_is_the_real_producer(self, tmp_path, monkeypatch):
        """Default-on proof: with NO record_decision injected, the publish still records."""
        import publish_release as pr_mod

        from agentic_dynamics.core import paths as core_paths
        from agentic_dynamics.knowledge import knowledge_stream as ks

        db_path = _publish_env(tmp_path, monkeypatch)
        redis = _FakeRedis()
        monkeypatch.setattr(core_paths, "KB_ARTIFACT_DIR", tmp_path / "kb")
        monkeypatch.setattr(ks, "connect", lambda: redis)
        emit_decision, emit_act = _noop_emitter("publish")

        def deploy(host):
            return pr_mod.DeployOutcome(host, True, f"rel-{host.role}", "")

        rc = pr_mod.main(
            ["--candidate-sha", "deadbeef", "--run-id", "publish_run_9",
             "--operator", "operator-test", "--db", str(db_path)],
            deployer=deploy, builder=lambda: (True, "built"),
            live_checker=lambda host, receipt: "",
            emit_decision=emit_decision, emit_act=emit_act,
        )
        assert rc == pr_mod.EXIT_OK
        records, warnings = di.scan_decision_records(category="publish", artifact_dir=tmp_path / "kb")
        assert warnings == []
        assert len(records) == 1
        payload = records[0][2]
        assert payload["actor"] == "verified_command"
        assert payload["run_id"] == "publish_run_9"
        assert payload["candidate_sha"] == "deadbeef"
