"""Tests for the producer-side spec-lifecycle derivation (``instrument.spec_ingestion``).

Covers the extractor contract constants, the record shape (entity key, locator, source URI,
the structured-field mapping and the parseable body), the ``POLICY``/``[P]`` authority and
observation-family classification, the supersede chain (a second derivation over a changed
lifecycle emits a record linking its predecessor with ``operation="supersede"``), the
convergence guard (an unchanged lifecycle emits nothing), and the downstream half — that a
registry append over fixture records makes ``generate_manifest.py``'s compaction derive
``current`` vs ``superseded`` correctly.

Everything runs against fixture entries and a ``tmp_path`` registry file; nothing here needs
Redis, an LLM, or the real corpus.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentic_dynamics.knowledge.knowledge import (
    ACTUATION_TYPES,
    OBSERVATION_TYPES,
    SCHEMA_VERSION,
    SOURCE_TYPES,
    Authority,
    compute_knowledge_id,
    message_family,
)
from agentic_dynamics.knowledge.knowledge_ingestion import artifact_uri, extract_record, record_to_artifact
from agentic_dynamics.knowledge.spec_ingestion import (
    ACL_SCOPE,
    EXTRACTOR_VERSION,
    REASON_PREFIX,
    SOURCE_TYPE,
    RegistryHead,
    build_spec_record,
    derive_spec_records,
    emit_spec_record,
    lifecycle_fingerprint,
    load_index_entries,
    parse_spec_text,
    registry_head,
    spec_entity_id,
    spec_event,
    spec_operation,
    spec_reason,
    spec_text,
)
from agentic_dynamics.experiment.spec_status import SpecStatusEntry

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REVISION = "0123456789abcdef0123456789abcdef01234567"


# ── Fixtures ────────────────────────────────────────────────────


def _entry(name: str = "alpha", **overrides) -> SpecStatusEntry:
    """A fully-populated index entry — the shape ``index.json`` hands the producer."""
    base = dict(
        name=name,
        version="0.2",
        status="runnable",
        spec_path=f"experiments/specs/{name}.yaml",
        supersedes=["alpha_v1"],
        superseded_by=None,
        completed_at=None,
        last_run_at="2026-08-18T15:30:00+00:00",
        latest_ok=True,
        latest_model="anthropic/claude-opus-5",
        latest_cost_usd=2.5,
        latest_git_sha="ccc3333",
        results_pointer=f"experiments/results/workflows/{name}/20260818T153000Z.json",
        n_runs=2,
    )
    base.update(overrides)
    return SpecStatusEntry(**base)


def _registry(tmp_path: Path, *rows: dict) -> Path:
    """Write a fixture ``registry_index.jsonl`` and return its path."""
    path = tmp_path / "registry_index.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


_NO_REASON = object()  # sentinel: distinguishes "default" from an explicit empty reason


def _registration_line(record, *, reason=_NO_REASON) -> dict:
    """The line ``kb_worker.py``'s kb-registry-v1 handler appends for one record.

    Mirrored here field-for-field (rather than importing the worker, which needs Redis) so a
    drift between what the worker writes and what ``registry_head`` reads shows up as a test
    failure rather than as a silently broken chain.
    """
    return {
        "knowledge_id": record.knowledge_id,
        "entity_id": record.entity_id,
        "source_type": record.source_type,
        "logical_locator": record.logical_locator,
        "source_uri": record.source_uri,
        "lifecycle_state": "current",
        "observed_at": record.observed_at,
        "indexed_at": record.indexed_at,
        "supersedes": record.supersedes,
        "causes": record.causes,
        "reason": spec_reason(record) if reason is _NO_REASON else reason,
    }


# ── Contract constants + vocabulary ─────────────────────────────


def test_extractor_contract_constants():
    assert EXTRACTOR_VERSION == "spec-lifecycle/v1"
    assert SOURCE_TYPE == "spec"
    assert ACL_SCOPE == "public"


def test_spec_is_a_registered_observation_type():
    # A spec record says what a spec IS — never an instruction to act on it. The closed-by-
    # default actuation gate must stay closed for this type.
    assert SOURCE_TYPES[SOURCE_TYPE].authority is Authority.POLICY
    assert SOURCE_TYPES[SOURCE_TYPE].evidence_class == "[P]"
    assert message_family(SOURCE_TYPE) == "observation"
    assert SOURCE_TYPE in OBSERVATION_TYPES
    assert SOURCE_TYPE not in ACTUATION_TYPES


# ── Record shape ────────────────────────────────────────────────


def test_entity_id_is_the_readable_spec_key():
    record = build_spec_record(_entry(), revision=REVISION)
    assert record.entity_id == "spec:alpha" == spec_entity_id("alpha")


def test_entity_id_is_stable_across_lifecycle_changes():
    # The whole supersede chain hangs off this: the entity must not move when the lifecycle
    # does, or every version would look like a brand-new entity.
    a = build_spec_record(_entry(status="runnable"), revision=REVISION)
    b = build_spec_record(_entry(status="superseded", n_runs=9), revision="deadbeef")
    assert a.entity_id == b.entity_id
    assert a.knowledge_id != b.knowledge_id


def test_record_authority_and_evidence_class():
    record = build_spec_record(_entry(), revision=REVISION)
    assert record.authority is Authority.POLICY
    assert record.evidence_class == "[P]"
    assert record.source_type == "spec"


def test_locator_and_source_uri():
    record = build_spec_record(_entry(), revision=REVISION)
    assert record.logical_locator == "alpha"                       # the spec NAME
    assert record.source_uri == "file://experiments/specs/alpha.yaml"


def test_structured_fields_carry_the_lifecycle():
    record = build_spec_record(_entry(), revision=REVISION)
    assert record.subject_status == "runnable"                       # the derived status
    assert record.subject_id.endswith("20260818T153000Z.json")     # the run it derived from
    assert record.observed_at == "2026-08-18T15:30:00+00:00"       # last_run_at, not now
    assert record.symbols == ["alpha_v1"]                          # the supersedes lineage
    assert record.outcome_id == "alpha@0.2"                        # the ledger's spec_id
    assert record.language == "yaml"
    assert record.acl_scope == ACL_SCOPE
    assert record.commit_sha == REVISION


def test_test_executed_success_is_never_fabricated_from_latest_ok():
    # `latest_ok` means "every phase of the last run succeeded" — NOT "a suite was
    # independently executed and passed". Conflating them would fabricate a measurement.
    record = build_spec_record(_entry(latest_ok=True), revision=REVISION)
    assert record.test_executed_success is None
    assert parse_spec_text(record.text)["latest_ok"] == "true"


def test_observed_at_falls_back_to_now_for_a_never_run_spec():
    record = build_spec_record(_entry(last_run_at=None, n_runs=0), revision=REVISION)
    assert record.observed_at  # non-empty (the producer clock), never a fabricated run time
    assert parse_spec_text(record.text)["last_run_at"] == "-"


def test_body_is_parseable_and_round_trips_every_lifecycle_field():
    entry = _entry()
    parsed = parse_spec_text(spec_text(entry))
    assert parsed["name"] == "alpha"
    assert parsed["version"] == "0.2"
    assert parsed["status"] == "runnable"
    assert parsed["supersedes"] == "alpha_v1"
    assert parsed["superseded_by"] == "-"          # absent renders as one fixed placeholder
    assert parsed["completed_at"] == "-"
    assert parsed["last_run_at"] == "2026-08-18T15:30:00+00:00"
    assert parsed["latest_ok"] == "true"
    assert parsed["latest_model"] == "anthropic/claude-opus-5"
    assert parsed["latest_cost_usd"] == "2.5"
    assert parsed["n_runs"] == "2"
    assert parsed["results_pointer"].endswith("20260818T153000Z.json")
    assert parsed["spec_path"] == "experiments/specs/alpha.yaml"


def test_build_accepts_a_plain_index_dict():
    # index.json hands out dicts; a caller must not have to pre-convert them. `now` is pinned
    # because record equality covers the volatile indexed_at/valid_from timestamps too.
    entry = _entry()
    clock = datetime(2026, 8, 20, tzinfo=timezone.utc)
    assert build_spec_record(entry.to_dict(), revision=REVISION, now=clock) == build_spec_record(
        entry, revision=REVISION, now=clock
    )


# ── Identity determinism ────────────────────────────────────────


def test_knowledge_id_follows_the_canonical_formula():
    record = build_spec_record(_entry(), revision=REVISION)
    assert record.knowledge_id == compute_knowledge_id(
        record.entity_id, REVISION, record.content_hash, EXTRACTOR_VERSION
    )
    assert record.content_hash and len(record.content_hash) == 64


def test_identity_is_reproducible_across_call_sites():
    # Same input, same ids — this is what makes the producer's checkpoint able to skip.
    a = build_spec_record(_entry(), revision=REVISION)
    b = build_spec_record(_entry(), revision=REVISION)
    assert (a.entity_id, a.content_hash, a.knowledge_id) == (
        b.entity_id, b.content_hash, b.knowledge_id
    )


def test_revision_and_extractor_are_folded_into_the_id():
    base = build_spec_record(_entry(), revision=REVISION)
    other_rev = build_spec_record(_entry(), revision="feedface")
    # The revision reaches the id twice — directly, and through `commit_sha`, which the
    # factory stamps from it and which IS part of the hashed artifact.
    assert other_rev.knowledge_id != base.knowledge_id
    assert other_rev.content_hash != base.content_hash
    assert other_rev.commit_sha == "feedface"
    # The lifecycle body, however, is revision-independent — which is what the convergence
    # guard fingerprints.
    assert lifecycle_fingerprint(other_rev) == lifecycle_fingerprint(base)


def test_artifact_round_trips_through_the_shared_contract():
    record = build_spec_record(_entry(), revision=REVISION)
    event = spec_event(record)
    restored = extract_record(event, record_to_artifact(record))
    assert restored.knowledge_id == record.knowledge_id
    assert restored.entity_id == record.entity_id
    assert restored.authority is Authority.POLICY
    assert restored.subject_status == "runnable"
    assert restored.text == record.text


# ── The pointer event ───────────────────────────────────────────


def test_event_is_pointer_only_and_points_at_the_durable_artifact():
    record = build_spec_record(_entry(), revision=REVISION)
    event = spec_event(record)
    assert event.source_uri == artifact_uri(record.knowledge_id)
    assert event.schema_version == SCHEMA_VERSION
    assert event.content_hash and not hasattr(event, "text")
    assert event.observed_at == record.observed_at


def test_event_operation_is_derived_from_the_record():
    plain = build_spec_record(_entry(), revision=REVISION)
    assert spec_operation(plain) == "upsert"
    assert spec_event(plain).operation == "upsert"

    linked = build_spec_record(_entry(), revision=REVISION, supersedes=plain.knowledge_id)
    assert spec_operation(linked) == "supersede"
    assert spec_event(linked).operation == "supersede"
    assert spec_event(linked).reason.startswith(REASON_PREFIX)


def test_lifecycle_fingerprint_ignores_the_chain_position():
    # The convergence guard depends on this exactly: linking a predecessor changes the id,
    # but must NOT change the "did the lifecycle move?" answer.
    plain = build_spec_record(_entry(), revision=REVISION)
    linked = build_spec_record(_entry(), revision=REVISION, supersedes=plain.knowledge_id)
    assert lifecycle_fingerprint(plain) == lifecycle_fingerprint(linked)
    assert plain.knowledge_id != linked.knowledge_id
    # ... and a real lifecycle change does move it.
    changed = build_spec_record(_entry(status="superseded"), revision=REVISION)
    assert lifecycle_fingerprint(changed) != lifecycle_fingerprint(plain)


# ── registry_head ───────────────────────────────────────────────


def test_registry_head_is_none_without_a_registry(tmp_path: Path):
    assert registry_head("spec:alpha", registry_path=tmp_path / "missing.jsonl") is None


def test_registry_head_finds_the_only_version(tmp_path: Path):
    record = build_spec_record(_entry(), revision=REVISION)
    path = _registry(tmp_path, _registration_line(record))
    head = registry_head("spec:alpha", registry_path=path)
    assert head == RegistryHead(record.knowledge_id, lifecycle_fingerprint(record))


def test_registry_head_skips_a_superseded_version(tmp_path: Path):
    v1 = build_spec_record(_entry(), revision=REVISION)
    v2 = build_spec_record(
        _entry(status="superseded"), revision=REVISION, supersedes=v1.knowledge_id
    )
    path = _registry(
        tmp_path,
        _registration_line(v1),
        _registration_line(v2),
        # kb_worker.py also appends this marker for the predecessor at supersede time.
        {"knowledge_id": v1.knowledge_id, "entity_id": v1.entity_id,
         "lifecycle_state": "superseded", "valid_to": v2.valid_from},
    )
    head = registry_head("spec:alpha", registry_path=path)
    assert head.knowledge_id == v2.knowledge_id


def test_registry_head_ignores_other_entities_and_broken_lines(tmp_path: Path):
    mine = build_spec_record(_entry(), revision=REVISION)
    theirs = build_spec_record(_entry("beta"), revision=REVISION)
    path = tmp_path / "registry_index.jsonl"
    path.write_text(
        json.dumps(_registration_line(theirs)) + "\n"
        + "{ truncated line\n"                       # must not hide the rest of the history
        + "\n"
        + json.dumps(_registration_line(mine)) + "\n"
    )
    assert registry_head("spec:alpha", registry_path=path).knowledge_id == mine.knowledge_id
    assert registry_head("spec:beta", registry_path=path).knowledge_id == theirs.knowledge_id
    assert registry_head("spec:nope", registry_path=path) is None


# ── derive_spec_records: the supersede chain ────────────────────


def test_first_derivation_is_a_plain_upsert(tmp_path: Path):
    records = derive_spec_records(
        [_entry()], revision=REVISION, registry_path=tmp_path / "empty.jsonl"
    )
    assert len(records) == 1
    assert records[0].supersedes is None
    assert spec_operation(records[0]) == "upsert"


def test_changed_lifecycle_emits_a_supersede_linking_the_predecessor(tmp_path: Path):
    # Round 1: nothing registered -> a first version.
    v1 = derive_spec_records(
        [_entry()], revision=REVISION, registry_path=tmp_path / "reg.jsonl"
    )[0]
    path = _registry(tmp_path, _registration_line(v1))
    path.rename(tmp_path / "reg.jsonl")

    # Round 2: the spec has been superseded by a later one -> a NEW version linking v1.
    v2 = derive_spec_records(
        [_entry(status="superseded", superseded_by="alpha_v3")],
        revision=REVISION,
        registry_path=tmp_path / "reg.jsonl",
    )[0]

    assert v2.supersedes == v1.knowledge_id       # the same-entity version chain link
    assert v2.entity_id == v1.entity_id           # ... same entity, by construction
    assert v2.knowledge_id != v1.knowledge_id
    assert spec_operation(v2) == "supersede"
    assert spec_event(v2).operation == "supersede"
    assert spec_event(v2).reason == spec_reason(v2)


def test_unchanged_lifecycle_emits_nothing(tmp_path: Path):
    """The convergence guard — a re-run over an unchanged corpus is a genuine no-op.

    Without it, linking a predecessor would move the ``knowledge_id`` every round and the
    chain would grow forever even though nothing about the spec had changed.
    """
    v1 = build_spec_record(_entry(), revision=REVISION)
    path = _registry(tmp_path, _registration_line(v1))
    assert derive_spec_records([_entry()], revision=REVISION, registry_path=path) == []


def test_chain_converges_over_repeated_rounds(tmp_path: Path):
    """Three rounds, one real change: exactly two versions, linked, then silence."""
    path = tmp_path / "reg.jsonl"
    rows: list[dict] = []

    def round_(entry) -> list:
        emitted = derive_spec_records([entry], revision=REVISION, registry_path=path)
        rows.extend(_registration_line(r) for r in emitted)
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
        return emitted

    first = round_(_entry())
    unchanged = round_(_entry())
    changed = round_(_entry(status="tombstoned"))
    settled = round_(_entry(status="tombstoned"))

    assert len(first) == 1 and first[0].supersedes is None
    assert unchanged == []
    assert len(changed) == 1 and changed[0].supersedes == first[0].knowledge_id
    assert settled == []


def test_derive_handles_a_head_without_a_fingerprint(tmp_path: Path):
    # A registry line written before the reason annotation existed carries no fingerprint, so
    # "unchanged" cannot be proven. With genuinely different content the safe reading is
    # "assume it moved" — emit a new version linking the predecessor.
    v1 = build_spec_record(_entry(), revision=REVISION)
    path = _registry(tmp_path, _registration_line(v1, reason=""))
    emitted = derive_spec_records(
        [_entry(status="tombstoned")], revision=REVISION, registry_path=path
    )
    assert len(emitted) == 1
    assert emitted[0].supersedes == v1.knowledge_id


def test_byte_identical_head_is_a_no_op_even_without_a_fingerprint(tmp_path: Path):
    # The second guard: when the head's knowledge_id already equals what we would derive, the
    # entity is provably up to date whether or not the line carries a fingerprint. Emitting a
    # link here would add a version that says exactly what its predecessor already said.
    v1 = build_spec_record(_entry(), revision=REVISION)
    path = _registry(tmp_path, _registration_line(v1, reason=""))
    assert derive_spec_records([_entry()], revision=REVISION, registry_path=path) == []


def test_derive_is_one_record_per_spec_in_input_order(tmp_path: Path):
    entries = [_entry("alpha"), _entry("beta"), _entry("gamma")]
    records = derive_spec_records(
        entries, revision=REVISION, registry_path=tmp_path / "none.jsonl"
    )
    assert [r.logical_locator for r in records] == ["alpha", "beta", "gamma"]
    assert [r.entity_id for r in records] == ["spec:alpha", "spec:beta", "spec:gamma"]


# ── generate_manifest lifecycle derivation over the fixture chain ──


def _load_manifest_module():
    """Import ``scripts/generate_manifest.py`` as a module (it is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "generate_manifest", PROJECT_ROOT / "scripts" / "generate_manifest.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_compaction_derives_current_vs_superseded(tmp_path: Path):
    """The downstream payoff: the chain makes the manifest report exactly one current row.

    This is why ``operation="supersede"`` + ``supersedes`` matter at all — it is
    ``generate_manifest.py``'s compaction, not the producer, that turns the append-only
    lineage into ``lifecycle_state``.
    """
    gm = _load_manifest_module()

    v1 = build_spec_record(_entry(), revision=REVISION)
    v2 = build_spec_record(
        _entry(status="superseded"), revision=REVISION, supersedes=v1.knowledge_id
    )
    path = _registry(tmp_path, _registration_line(v1), _registration_line(v2))

    compacted = gm._compact_registry_index(path)
    rows = {r["entity_id"]: r for r in compacted}
    assert set(rows) == {"spec:alpha"}                 # one row per entity_id
    assert rows["spec:alpha"]["knowledge_id"] == v2.knowledge_id
    assert rows["spec:alpha"]["lifecycle_state"] == "current"

    # And the predecessor is derived as superseded, whatever its own line said.
    state, _valid_to = gm._derive_lifecycle(
        {"knowledge_id": v1.knowledge_id, "entity_id": v1.entity_id, "lifecycle_state": "current"},
        {v1.knowledge_id: {"observed_at": v2.observed_at}},
    )
    assert state == "superseded"


# ── Index loading + the best-effort run-time emit ───────────────


def test_load_index_entries_reads_the_real_repo_index():
    entries = load_index_entries(root=PROJECT_ROOT)
    assert entries, "run `python scripts/spec_status.py` to generate experiments/specs/index.json"
    assert all(isinstance(e, SpecStatusEntry) and e.name for e in entries)


def test_load_index_entries_tolerates_a_missing_or_broken_index(tmp_path: Path):
    assert load_index_entries(root=tmp_path) == []
    specs = tmp_path / "experiments" / "specs"
    specs.mkdir(parents=True)
    (specs / "index.json").write_text("{ not json")
    assert load_index_entries(root=tmp_path) == []


def test_emit_returns_none_for_an_unknown_spec(tmp_path: Path):
    # Nothing to emit is not a failure — a spec can be run from outside the corpus.
    assert emit_spec_record("not_a_spec", root=tmp_path) is None


def test_emit_never_raises_when_the_stream_is_unreachable(tmp_path: Path, monkeypatch):
    """The end-of-run hook must degrade to ``None``, never propagate — the run is over."""
    specs = tmp_path / "experiments" / "specs"
    specs.mkdir(parents=True)
    (specs / "index.json").write_text(
        json.dumps({"schema_version": "spec-status/v1", "n_specs": 1,
                    "specs": [_entry().to_dict()]})
    )
    import agentic_dynamics.knowledge.knowledge_stream as ks
    import agentic_dynamics.knowledge.spec_ingestion as si

    # The artifact is written BEFORE the publish (the ordering contract), so redirect the
    # artifact directory too — otherwise this test litters the real experiments/results/kb/.
    monkeypatch.setattr(si, "KB_ARTIFACT_DIR", tmp_path / "kb")

    def boom(*a, **k):
        raise RuntimeError("stream down")

    monkeypatch.setattr(ks, "connect", boom)
    assert emit_spec_record("alpha", root=tmp_path, registry_path=tmp_path / "r.jsonl") is None


def test_emit_writes_the_artifact_before_publishing(tmp_path: Path, monkeypatch):
    """Ordering contract: the durable bytes must exist by the time the pointer lands."""
    specs = tmp_path / "experiments" / "specs"
    specs.mkdir(parents=True)
    (specs / "index.json").write_text(
        json.dumps({"schema_version": "spec-status/v1", "n_specs": 1,
                    "specs": [_entry().to_dict()]})
    )

    import agentic_dynamics.knowledge.knowledge_stream as ks
    import agentic_dynamics.knowledge.spec_ingestion as si

    artifact_dir = tmp_path / "kb"
    monkeypatch.setattr(si, "KB_ARTIFACT_DIR", artifact_dir)
    monkeypatch.setattr(ks, "connect", lambda *a, **k: object())

    published: list = []

    def capture(_client, event, *, source_type):
        # The artifact must already be readable at this point.
        assert (artifact_dir / f"{event.knowledge_id}.json").is_file()
        published.append((event, source_type))

    monkeypatch.setattr(ks, "publish_event", capture)

    record = emit_spec_record("alpha", root=tmp_path, registry_path=tmp_path / "r.jsonl")
    assert record is not None
    assert len(published) == 1
    event, source_type = published[0]
    assert source_type == "spec"
    assert event.operation == "upsert"
    assert event.knowledge_id == record.knowledge_id
    # The write guard is set for the emit only and restored afterwards.
    import os
    assert os.environ.get("FINOPS_KB_WRITE") is None


def test_emit_returns_none_when_the_lifecycle_is_unchanged(tmp_path: Path, monkeypatch):
    specs = tmp_path / "experiments" / "specs"
    specs.mkdir(parents=True)
    (specs / "index.json").write_text(
        json.dumps({"schema_version": "spec-status/v1", "n_specs": 1,
                    "specs": [_entry().to_dict()]})
    )
    v1 = build_spec_record(_entry(), revision=REVISION)
    path = _registry(tmp_path, _registration_line(v1))

    import agentic_dynamics.knowledge.knowledge_stream as ks

    monkeypatch.setattr(ks, "connect", lambda *a, **k: pytest.fail("must not connect"))
    assert emit_spec_record("alpha", root=tmp_path, revision=REVISION, registry_path=path) is None
