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
from types import SimpleNamespace

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
    derive_phase_record,
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
    # Two independent derivations of the same entry converge on one identity pair — even
    # with *different* wall-clock times, because content_hash covers only the entry's stable
    # content (the volatile timestamps are blanked out of the artifact). No `now` pin needed.
    a = build_record(_entry())
    b = build_record(_entry())
    assert a.entity_id == b.entity_id
    assert a.knowledge_id == b.knowledge_id
    # And they are real sha256 digests.
    assert len(a.entity_id) == 64
    assert len(a.knowledge_id) == 64


def test_ids_stable_across_runs_with_different_timestamps():
    # The idempotence contract: the *same entry* derived at two different times yields the
    # same knowledge_id (so a re-run's checkpoint HGET finds it and skips it).
    from datetime import datetime, timezone

    t1 = build_record(_entry(), now=datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc))
    t2 = build_record(_entry(), now=datetime(2026, 8, 16, 9, 30, 0, tzinfo=timezone.utc))
    assert t1.valid_from != t2.valid_from  # timestamps DO differ ...
    assert t1.content_hash == t2.content_hash  # ... but the artifact hash does not ...
    assert t1.knowledge_id == t2.knowledge_id  # ... so the idempotence key is stable.


def test_entity_id_uses_repository_source_and_locator():
    record = build_record(_entry(worktree_name="exp_abc", run_id="exp_abc"))
    expected = compute_entity_id(REPOSITORY_ID, SOURCE_URI, "exp_abc")
    assert record.entity_id == expected


def test_content_hash_is_artifact_hash():
    record = build_record(_entry())
    # content_hash is the sha256 of the durable per-record artifact — not of the finding text.
    assert record.content_hash == hashlib.sha256(record_to_artifact(record)).hexdigest()
    # The artifact serialization blanks the derived ids AND the volatile timestamps, so the
    # hash is neither self-referential nor time-dependent: re-serializing the *final* record
    # (with its real ids/timestamps) still hashes to the same bytes.
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
    # to_dict / from_dict round-trips the two new fields (a full, lossless round-trip).
    restored = KnowledgeRecord.from_dict(record.to_dict())
    assert restored.confidence == 0.82
    assert restored.perturbation_strength == 0.5
    assert restored == record
    # The durable artifact carries the stable content; extract_record reattaches the derived
    # ids (from the event) and reconstructs the timestamps (transport metadata). The content,
    # identity, and measured signals survive; observed_at round-trips the producer's own value
    # (via the event's observed_at), while indexed_at is stamped at consumer time by design.
    event = record_to_event(record)
    artifact = record_to_artifact(record)
    extracted = extract_record(event, artifact)
    assert extracted.confidence == 0.82
    assert extracted.perturbation_strength == 0.5
    assert extracted.authority is Authority.MEASURED
    assert extracted.knowledge_id == record.knowledge_id
    assert extracted.content_hash == record.content_hash
    assert extracted.text == record.text
    assert extracted.valid_from == event.occurred_at
    assert extracted.observed_at == record.observed_at
    assert extracted.observed_at == event.observed_at


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


def test_observed_at_round_trips_the_entry_timestamp_not_the_producer_clock():
    # BUG-1 regression: the cell's OWN run timestamp must survive the pointer round-trip,
    # not be silently replaced by the producer's wall-clock (occurred_at).
    from datetime import datetime, timezone

    stamped = "2026-08-01T00:00:00+00:00"
    producer_now = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)

    record = build_record(_entry(ended_at=stamped), now=producer_now)
    assert record.observed_at == stamped

    event = record_to_event(record, now=producer_now)
    # occurred_at is the producer clock (end-to-end lag); observed_at is the real measurement.
    assert event.occurred_at == producer_now.isoformat()
    assert event.observed_at == stamped

    extracted = extract_record(event, record_to_artifact(record))
    # The entry's own timestamp round-trips, not the producer clock.
    assert extracted.observed_at == stamped
    assert extracted.observed_at != event.occurred_at
    # valid_from still reflects the producer derivation pass; the stable content survives.
    assert extracted.valid_from == event.occurred_at
    assert extracted.content_hash == record.content_hash
    assert extracted.knowledge_id == record.knowledge_id


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


def test_build_record_source_uri_override_changes_identity():
    alt = "file://experiments/results/task_manager_deepseek-v4-pro.json"
    record = build_record(_entry(), source_uri=alt)
    assert record.source_uri == alt
    assert record.entity_id == compute_entity_id(REPOSITORY_ID, alt, "exp_05ngi4l9")


def test_derive_records_source_uri_threads_through():
    alt = "file://experiments/results/task_manager_deepseek-v4-pro.json"
    records = derive_records([_entry()], source_uri=alt)
    assert records[0].source_uri == alt


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
    """``--dry-run`` reports the would-emit count and samples without *requiring* Redis.

    The preview reads the checkpoint idempotence hash best-effort; a bogus
    ``FINOPS_REDIS_PORT`` makes that read fail, and the preview degrades to the raw derived
    count (2 valid entries here) instead of raising — proving ``--dry-run`` is side-effect-free
    and still works with the stream down.
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


# ── Self-build (progressive) phase findings ─────────────────────


def _phase_result(**overrides) -> SimpleNamespace:
    """A minimal completed-phase double (mirrors ``workflow_runner.PhaseResult``)."""
    base = dict(
        phase="implement",
        status="ok",
        tokens={"in": 10, "out": 20, "total": 30},
        cost_usd=0.0123,
        test_executed_success=True,
        commit_hash="abc1234",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_derive_phase_record_authority_flips_on_test_executed_success():
    # A bool is an independent measurement → MEASURED; None is self-report → ADVISORY.
    measured = derive_phase_record(
        _phase_result(test_executed_success=True), goal="g", repository_id="self-1", revision="abc"
    )
    assert measured.authority is Authority.MEASURED
    assert measured.evidence_class == "[M]"
    assert measured.test_executed_success is True

    failed = derive_phase_record(
        _phase_result(test_executed_success=False), goal="g", repository_id="self-1", revision="abc"
    )
    assert failed.authority is Authority.MEASURED
    assert failed.test_executed_success is False

    advisory = derive_phase_record(
        _phase_result(test_executed_success=None), goal="g", repository_id="self-1", revision="abc"
    )
    assert advisory.authority is Authority.ADVISORY
    assert advisory.evidence_class == "[H]"
    assert advisory.test_executed_success is None


def test_derive_phase_record_text_and_scoping():
    goal = "build a task manager api with many details"
    rec = derive_phase_record(
        _phase_result(phase="scope", cost_usd=0.01, tokens={"total": 42}, test_executed_success=True),
        goal=goal,
        repository_id="self-cell-1",
        revision="abc1234",
    )
    # goal is truncated at 40 chars; the tail ("details") is dropped.
    assert len(goal) > 40
    assert rec.text.startswith(goal[:40] + " phase scope -> test_executed_success True")
    assert "cost $0.0100" in rec.text
    assert "tokens 42" in rec.text
    assert "details" not in rec.text
    # Every scoping field is the cell scope, never global.
    assert rec.source_type == "finding"
    assert rec.logical_locator == "self-cell-1"
    assert rec.repository_id == "self-cell-1"
    assert rec.acl_scope == "self-cell-1"
    assert rec.commit_sha == "abc1234"
    assert rec.extractor_version == "phase-finding/v1"


def test_derive_phase_record_idempotent():
    a = derive_phase_record(_phase_result(), goal="g", repository_id="self-1", revision="abc")
    b = derive_phase_record(_phase_result(), goal="g", repository_id="self-1", revision="abc")
    assert a.knowledge_id == b.knowledge_id
    assert a.entity_id == b.entity_id
    assert a.content_hash == b.content_hash
    # The idempotence key is f(goal, phase, commit, scope, extractor): each input change
    # yields a new knowledge_id.
    assert derive_phase_record(_phase_result(), goal="other", repository_id="self-1", revision="abc").knowledge_id != a.knowledge_id
    assert derive_phase_record(_phase_result(phase="scope"), goal="g", repository_id="self-1", revision="abc").knowledge_id != a.knowledge_id
    assert derive_phase_record(_phase_result(), goal="g", repository_id="self-1", revision="xyz").knowledge_id != a.knowledge_id
    assert derive_phase_record(_phase_result(), goal="g", repository_id="self-2", revision="abc").knowledge_id != a.knowledge_id


def test_publish_event_write_guard(monkeypatch):
    import instrument.knowledge_stream as ks

    monkeypatch.delenv("FINOPS_KB_WRITE", raising=False)
    event = record_to_event(build_record(_entry()))

    class _R:
        def xadd(self, *a, **kw):
            return "0-1"

    # No flag, no explicit auth → raise.
    with pytest.raises(RuntimeError):
        ks.publish_event(_R(), event)
    # Env flag authorizes.
    monkeypatch.setenv("FINOPS_KB_WRITE", "1")
    assert ks.publish_event(_R(), event) == "0-1"
    # Explicit kwarg authorizes even without the flag.
    monkeypatch.delenv("FINOPS_KB_WRITE", raising=False)
    assert ks.publish_event(_R(), event, authorized=True) == "0-1"


def test_emit_phase_finding_scoped_to_repository_id(tmp_path, monkeypatch):
    import hashlib as _hashlib

    import instrument.knowledge_ingestion as ki
    import instrument.knowledge_stream as ks

    monkeypatch.setattr(ki, "PROJECT_ROOT", tmp_path)
    published = {}

    def _fake_connect():
        return object()

    def _fake_publish(r, event, **kwargs):
        published["event"] = event
        return "0-1"

    monkeypatch.setattr(ks, "connect", _fake_connect)
    monkeypatch.setattr(ks, "publish_event", _fake_publish)

    record = ki.emit_phase_finding(
        _phase_result(test_executed_success=True),
        goal="build a task manager api",
        repository_id="self-cell-1",
        revision="abc1234",
    )

    # Every scoping field is the cell scope — never global.
    assert record.repository_id == "self-cell-1"
    assert record.logical_locator == "self-cell-1"
    assert record.acl_scope == "self-cell-1"
    assert record.commit_sha == "abc1234"

    ev = published["event"]
    assert ev.knowledge_id == record.knowledge_id
    assert ev.source_revision == "abc1234"

    # The durable artifact was written under the (tmp) repo kb dir and its bytes are what
    # content_hash covers.
    artifact_path = tmp_path / "experiments" / "results" / "kb" / f"{record.knowledge_id}.json"
    assert artifact_path.exists()
    assert _hashlib.sha256(artifact_path.read_bytes()).hexdigest() == record.content_hash


def test_emit_phase_finding_idempotent(tmp_path, monkeypatch):
    import instrument.knowledge_ingestion as ki
    import instrument.knowledge_stream as ks

    monkeypatch.setattr(ki, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(ks, "connect", lambda: object())
    events = []
    monkeypatch.setattr(ks, "publish_event", lambda r, e, **kw: events.append(e) or "0-1")

    a = ki.emit_phase_finding(_phase_result(), goal="g", repository_id="self-1", revision="abc")
    b = ki.emit_phase_finding(_phase_result(), goal="g", repository_id="self-1", revision="abc")

    # Re-emitting the same phase derives the same id → the consumer's keyed upsert is a no-op.
    assert a.knowledge_id == b.knowledge_id
    assert len(events) == 2  # both emits published ...
    assert events[0].knowledge_id == events[1].knowledge_id  # ... the same idempotence key.

