"""Tests for the producer-side measured-finding derivation (knowledge_ingestion).

Covers the extractor contract constants, the identity derivation (ids stable across call
sites, content hash recomputable from text, extractor-version bump → new knowledge_id), the
``MEASURED`` authority / ``[M]`` evidence class, that confidence/perturbation_strength/
test_executed_success are carried through, that the event is pointer-only, the batch
``derive_records`` filtering, and the batch producer's pure emission planning + dry-run smoke.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

import pytest

from instrument.knowledge import (
    SCHEMA_VERSION,
    Authority,
    KnowledgeEvent,
    KnowledgeRecord,
    compute_entity_id,
    compute_knowledge_id,
)
from instrument.knowledge_ingestion import (
    ACL_SCOPE,
    EXTRACTOR_VERSION,
    REPOSITORY_ID,
    RESULT_VERSION,
    SOURCE_TYPE,
    SOURCE_URI,
    artifact_uri,
    build_record,
    derive_records,
    extract_record,
    record_to_artifact,
    record_to_event,
)

MODEL = "deepseek/deepseek-v4-pro"
OPERATOR = "perturbed"

REPO_ROOT = Path(__file__).resolve().parent.parent
KB_PRODUCE = REPO_ROOT / "scripts" / "kb_produce.py"


def _load_kb_produce():
    """Load ``scripts/kb_produce.py`` as a module for pure-logic tests (no subprocess)."""
    spec = importlib.util.spec_from_file_location("kb_produce", KB_PRODUCE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod



def _entry(**overrides) -> dict:
    """A minimal valid results entry, overridable per field for focused tests."""
    entry = {
        "worktree_name": "exp_05ngi4l9",
        "run_id": "exp_05ngi4l9",
        "model": MODEL,
        "operator": OPERATOR,
        "perturbation_class": "semantic",
        "strategy": "exploratory",
        "correctness": 0.8,
        "cost": 0.033537746,
        "escape": 0.7486509085783121,
        "flail": 0.62,
        "narration_failure": False,
        "test_executed_success": None,
        "confidence": None,
        "perturbation_strength": None,
        "outcome_id": "",
    }
    entry.update(overrides)
    return entry


# ── Extractor contract constants ────────────────────────────────


def test_extractor_version_is_explicit_and_stable():
    assert EXTRACTOR_VERSION == "measured-finding/v1"
    # The source is a durable locator; the repo id a stable component of entity_id.
    assert SOURCE_URI == "file://experiments/results/_results_summary.json"
    assert SOURCE_TYPE == "finding"


# ── Identity derivation ─────────────────────────────────────────


def test_record_authority_measured_and_evidence_class_m():
    record = build_record(_entry())
    assert record.authority is Authority.MEASURED
    assert record.evidence_class == "[M]"


def test_ids_stable_across_call_sites():
    # Two independent derivations of the same entry converge on one identity pair.
    # content_hash now covers the durable artifact (which includes the observation
    # timestamp), so pin `now` to make the derivation deterministic.
    from datetime import datetime, timezone

    pinned = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    a = build_record(_entry(), now=pinned)
    b = build_record(_entry(), now=pinned)
    assert a.entity_id == b.entity_id
    assert a.knowledge_id == b.knowledge_id
    # And they are real sha256 digests.
    assert len(a.entity_id) == 64
    assert len(a.knowledge_id) == 64


def test_entity_id_uses_repository_source_and_locator():
    record = build_record(_entry(worktree_name="exp_abc", run_id="exp_abc"))
    expected = compute_entity_id(REPOSITORY_ID, SOURCE_URI, "exp_abc")
    assert record.entity_id == expected


def test_content_hash_is_artifact_hash():
    record = build_record(_entry())
    # content_hash is the sha256 of the durable per-record artifact — not of the finding text.
    assert record.content_hash == hashlib.sha256(record_to_artifact(record)).hexdigest()
    # The artifact serialization excludes the two derived ids so the hash is not
    # self-referential: re-serializing the *final* record (with its real ids) still hashes
    # to the same bytes.
    assert record_to_artifact(record) == record_to_artifact(
        KnowledgeRecord.from_dict(record.to_dict())
    )


def test_knowledge_id_folds_revision_hash_and_extractor():
    record = build_record(_entry())
    expected = compute_knowledge_id(
        record.entity_id,
        record.commit_sha,  # commit_sha stores the source_revision
        record.content_hash,
        EXTRACTOR_VERSION,
    )
    assert record.knowledge_id == expected


def test_extractor_version_bump_changes_knowledge_id(monkeypatch):
    entry = _entry()
    record_v1 = build_record(entry)
    monkeypatch.setattr("instrument.knowledge_ingestion.EXTRACTOR_VERSION", "measured-finding/v2")
    record_v2 = build_record(entry)
    # A new extractor generation yields a new knowledge_id ...
    assert record_v2.knowledge_id != record_v1.knowledge_id
    # ... while the logical identity stays stable.
    assert record_v2.entity_id == record_v1.entity_id
    assert record_v2.extractor_version == "measured-finding/v2"


def test_source_revision_falls_back_to_result_version_when_no_commit():
    record = build_record(_entry())  # no git_sha/commit/commit_sha
    assert record.commit_sha == RESULT_VERSION


def test_source_revision_uses_commit_when_stamped():
    record = build_record(_entry(git_sha="abc1234"))
    assert record.commit_sha == "abc1234"
    # The knowledge_id must fold the commit, not the fallback version.
    assert compute_knowledge_id(
        record.entity_id, "abc1234", record.content_hash, EXTRACTOR_VERSION
    ) == record.knowledge_id


# ── Ledger signals carried through ──────────────────────────────


def test_confidence_perturbation_strength_carried_through_text():
    record = build_record(_entry(confidence=0.82, perturbation_strength=0.5))
    # confidence [H] and perturbation_strength [M] are carried through the rendered finding.
    assert "confidence 0.82" in record.text
    assert "perturb_strength 0.50" in record.text


def test_confidence_absent_renders_em_dash_not_zero():
    record = build_record(_entry(confidence=None))
    assert "confidence —" in record.text
    assert "confidence 0.00" not in record.text


def test_confidence_and_perturbation_strength_are_structured():
    record = build_record(_entry(confidence=0.82, perturbation_strength=0.5))
    # The ledger signals are now structural fields on the record — not only the prose.
    assert record.confidence == 0.82
    assert record.perturbation_strength == 0.5


def test_absent_signals_stay_none_not_zero():
    record = build_record(_entry())
    # Unmeasured stays None (never a fabricated 0.0), mirroring test_executed_success.
    assert record.confidence is None
    assert record.perturbation_strength is None


def test_non_finite_signals_coerce_to_none():
    record = build_record(_entry(confidence=float("nan"), perturbation_strength=float("inf")))
    assert record.confidence is None
    assert record.perturbation_strength is None


def test_structured_signals_round_trip_to_dict_from_dict_and_artifact():
    record = build_record(_entry(confidence=0.82, perturbation_strength=0.5))
    # to_dict / from_dict round-trips the two new fields.
    restored = KnowledgeRecord.from_dict(record.to_dict())
    assert restored.confidence == 0.82
    assert restored.perturbation_strength == 0.5
    assert restored == record
    # The durable artifact carries them too, so extract_record reconstructs them.
    event = record_to_event(record)
    artifact = record_to_artifact(record)
    extracted = extract_record(event, artifact)
    assert extracted.confidence == 0.82
    assert extracted.perturbation_strength == 0.5
    assert extracted == record


def test_absent_signals_round_trip_stay_none_through_artifact():
    record = build_record(_entry())
    assert record.confidence is None and record.perturbation_strength is None
    restored = KnowledgeRecord.from_dict(record.to_dict())
    assert restored.confidence is None and restored.perturbation_strength is None
    extracted = extract_record(record_to_event(record), record_to_artifact(record))
    assert extracted.confidence is None and extracted.perturbation_strength is None


def test_test_executed_success_carried_through():
    record_true = build_record(_entry(test_executed_success=True))
    assert record_true.test_executed_success is True
    assert "tests pass" in record_true.text

    record_false = build_record(_entry(test_executed_success=False))
    assert record_false.test_executed_success is False
    assert "tests FAIL (unverified)" in record_false.text

    record_none = build_record(_entry(test_executed_success=None))
    assert record_none.test_executed_success is None


def test_outcome_id_carried_through():
    record = build_record(_entry(outcome_id="outcome-42"))
    assert record.outcome_id == "outcome-42"


# ── Record metadata consistency ─────────────────────────────────


def test_record_text_is_evidence_card_oneliner():
    record = build_record(_entry())
    assert record.text.startswith(f"{MODEL} under {OPERATOR} (class semantic) -> correctness")
    assert record.token_count == max(1, len(record.text.split()))
    assert record.acl_scope == ACL_SCOPE
    assert record.source_uri == SOURCE_URI
    assert record.repository_id == REPOSITORY_ID
    assert record.logical_locator == "exp_05ngi4l9"
    assert record.valid_to is None
    assert record.valid_from and record.observed_at and record.indexed_at


def test_record_round_trip_preserves_measured_fields():
    record = build_record(_entry(test_executed_success=True, outcome_id="o1"))
    restored = KnowledgeRecord.from_dict(record.to_dict())
    assert restored == record
    assert restored.authority is Authority.MEASURED
    assert restored.test_executed_success is True


# ── Event is pointer-only ───────────────────────────────────────


def test_event_has_no_body():
    record = build_record(_entry())
    event = record_to_event(record)
    assert not hasattr(event, "text")
    assert not hasattr(event, "body")
    assert "text" not in fields(KnowledgeEvent)
    assert "body" not in fields(KnowledgeEvent)


def test_event_carries_identity_and_pointers():
    record = build_record(_entry())
    event = record_to_event(record)
    assert event.knowledge_id == record.knowledge_id
    assert event.entity_id == record.entity_id
    assert event.operation == "upsert"
    assert event.source_uri == artifact_uri(record.knowledge_id)
    assert event.source_revision == record.commit_sha
    assert event.content_hash == record.content_hash
    assert event.schema_version == SCHEMA_VERSION
    assert event.occurred_at  # producer timestamp is set
    # event_id is a deterministic tracing id (NOT the idempotence key — knowledge_id is).
    assert event.event_id == record.knowledge_id


def test_event_occurred_at_respects_injected_now():
    from datetime import datetime, timezone

    pinned = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    record = build_record(_entry(), now=pinned)
    event = record_to_event(record, now=pinned)
    assert event.occurred_at == pinned.isoformat()


def test_observed_at_prefers_entry_timestamp_else_falls_back_to_now():
    from datetime import datetime, timezone

    pinned = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    # The real _results_summary.json has no per-entry timestamp → fall back to producer now.
    record = build_record(_entry(), now=pinned)
    assert record.observed_at == pinned.isoformat()
    # A stamped entry timestamp is honored verbatim (not fabricated, not reclocked).
    record = build_record(_entry(ended_at="2026-08-14T09:30:00+00:00"), now=pinned)
    assert record.observed_at == "2026-08-14T09:30:00+00:00"
    # valid_from / indexed_at describe *this* derivation pass, so they stay the producer now.
    assert record.valid_from == pinned.isoformat()
    assert record.indexed_at == pinned.isoformat()


# ── Batch derivation filters like build_evidence_cards ──────────


def test_derive_records_skips_narration_failure_and_bad_correctness():
    entries = [
        _entry(worktree_name="exp_good", run_id="exp_good"),
        _entry(worktree_name="exp_narr", run_id="exp_narr", narration_failure=True),
        _entry(worktree_name="exp_neg", run_id="exp_neg", correctness=-1.0),
        _entry(worktree_name="exp_none", run_id="exp_none", correctness=None),
        _entry(worktree_name="exp_nan", run_id="exp_nan", correctness=float("nan")),
    ]
    records = derive_records(entries)
    assert [r.logical_locator for r in records] == ["exp_good"]


def test_derive_records_preserves_input_order():
    entries = [
        _entry(worktree_name="exp_a", run_id="exp_a"),
        _entry(worktree_name="exp_b", run_id="exp_b"),
    ]
    records = derive_records(entries)
    assert [r.logical_locator for r in records] == ["exp_a", "exp_b"]


def test_derive_records_empty_and_all_invalid():
    assert derive_records([]) == []
    assert derive_records([_entry(narration_failure=True)]) == []


# ── build_record rejects invalid entries loudly ─────────────────


def test_build_record_raises_on_skipped_entry():
    with pytest.raises(ValueError):
        build_record(_entry(narration_failure=True))
    with pytest.raises(ValueError):
        build_record(_entry(correctness=None))
    with pytest.raises(ValueError):
        build_record(_entry(correctness=-0.5))


# ── build_record / derive_records repository override ───────────


def test_build_record_repository_id_override_changes_identity():
    default = build_record(_entry())
    scoped = build_record(_entry(), repository_id="other-repo")
    # A different repository id yields a different logical entity (and thus knowledge id) ...
    assert scoped.repository_id == "other-repo"
    assert scoped.entity_id != default.entity_id
    # ... and the entity id is the sha256 over the *overridden* id.
    assert scoped.entity_id == compute_entity_id("other-repo", SOURCE_URI, "exp_05ngi4l9")


def test_derive_records_repository_id_threads_through():
    records = derive_records([_entry()], repository_id="other-repo")
    assert records[0].repository_id == "other-repo"


# ── Batch producer pure logic (scripts/kb_produce.py) ───────────


def test_plan_emissions_caps_and_dedupes_in_process():
    kb = _load_kb_produce()
    a = build_record(_entry(worktree_name="exp_a", run_id="exp_a"))
    b = build_record(_entry(worktree_name="exp_b", run_id="exp_b"))
    c = build_record(_entry(worktree_name="exp_c", run_id="exp_c"))
    # Duplicate of `a` appears again in-process → first occurrence wins.
    plan = kb.plan_emissions([a, b, a, c], limit=0)
    assert [r.logical_locator for r in plan] == ["exp_a", "exp_b", "exp_c"]


def test_plan_emissions_limit_caps_before_dedupe():
    kb = _load_kb_produce()
    a = build_record(_entry(worktree_name="exp_a", run_id="exp_a"))
    b = build_record(_entry(worktree_name="exp_b", run_id="exp_b"))
    c = build_record(_entry(worktree_name="exp_c", run_id="exp_c"))
    assert [r.logical_locator for r in kb.plan_emissions([a, b, c], limit=2)] == ["exp_a", "exp_b"]
    assert kb.plan_emissions([a, b, c], limit=0) == [a, b, c]


def test_plan_emissions_known_ids_seed_the_dedupe():
    kb = _load_kb_produce()
    a = build_record(_entry(worktree_name="exp_a", run_id="exp_a"))
    b = build_record(_entry(worktree_name="exp_b", run_id="exp_b"))
    plan = kb.plan_emissions([a, b], known_ids={a.knowledge_id})
    assert [r.logical_locator for r in plan] == ["exp_b"]


# ── Dry-run smoke (no live Redis) ───────────────────────────────


def test_kb_produce_dry_run_smoke(tmp_path):
    """``--dry-run`` reports the would-emit count and samples without touching Redis.

    A bogus ``FINOPS_REDIS_PORT`` proves the dry-run path never connects: a connection
    attempt would raise (fail fast) and produce a non-zero exit.
    """
    results = tmp_path / "_results_summary.json"
    results.write_text(json.dumps({
        "entries": [
            _entry(worktree_name="exp_good_a", run_id="exp_good_a"),
            # Skipped upstream (narration failure) — must not count toward the emit total.
            _entry(worktree_name="exp_narr", run_id="exp_narr", narration_failure=True),
            _entry(worktree_name="exp_good_b", run_id="exp_good_b"),
        ]
    }))
    proc = subprocess.run(
        [
            sys.executable, str(KB_PRODUCE),
            "--dry-run",
            "--results", str(results),
            "--repository-id", "test-repo",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "FINOPS_REDIS_PORT": "63999"},
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    # 2 valid entries → 2 would-be emitted records; the narration_failure row is skipped.
    assert "would emit 2 record(s)" in out
    assert "repository-id='test-repo'" in out
    assert "exp_good_a" in out
    assert "exp_good_b" in out
    assert "exp_narr" not in out


# ── Producer → consumer boundary (the bug the original run missed) ──


def test_producer_emitted_event_verifies_and_lands_measured(tmp_path, monkeypatch):
    """Drive the full boundary: producer emits, consumer reads/verifies/extracts/upserts.

    This is the end-to-end contract the original run broke — the producer hashed the
    one-line finding text but pointed ``source_uri`` at the whole ``_results_summary.json``,
    so ``verify_content_hash`` could never match and every event retried forever. Here the
    producer writes the per-record JSON artifact and hashes *its* bytes; the consumer reads
    those same bytes, verifies, and reconstructs a ``MEASURED`` record via ``extract_record``.
    """
    from instrument import knowledge_stream as ks

    # 1. Producer path — derive, serialize, and durably write the per-record artifact.
    record = build_record(_entry(worktree_name="exp_int", run_id="exp_int"))
    artifact = record_to_artifact(record)
    rel_path = artifact_uri(record.knowledge_id)[len("file://"):]
    artifact_path = tmp_path / rel_path
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(artifact)
    event = record_to_event(record)

    # The event points at the per-record artifact and hashes those exact bytes.
    assert event.source_uri == artifact_uri(record.knowledge_id)
    assert event.content_hash == hashlib.sha256(artifact).hexdigest()
    assert ks.verify_content_hash(artifact, event.content_hash)

    # 2. Consumer path — resolve the artifact from the event's source_uri (relative to the
    #    checkout root, which we chdir to), verify, extract, and upsert into a store double.
    monkeypatch.chdir(tmp_path)

    class Store:
        def __init__(self):
            self.docs = {}

        def upsert(self, rec):
            self.docs[rec.knowledge_id] = rec

    class _FakeRedis:
        def xack(self, *args, **kwargs):
            return 1

    store = Store()
    outcome = ks.process_entry(
        _FakeRedis(), "kb-int", "0-1", event, store.upsert,
        extractor=extract_record,
    )
    assert outcome == "ok"

    upserted = store.docs[record.knowledge_id]
    assert upserted.authority is Authority.MEASURED
    assert upserted.text == record.text
    assert upserted.knowledge_id == record.knowledge_id
    assert upserted.content_hash == record.content_hash

