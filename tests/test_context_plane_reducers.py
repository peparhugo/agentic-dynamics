"""Tests for CAP I1 — the ``spec_status/v1`` reducer, fact ingestion, and the facts producer.

Covers the reducer's declaration (registered in ``REDUCERS``, the pinned predicate set), its
purity and determinism, the measured-or-absent semantics (an unmeasured run field is *absent*,
never a fabricated ``0``/``false``), the fact shape (workload scope, ``derived`` epistemics,
time-invariant ``fact_entity_id``), the fact-ingestion mapping (``fact_id`` IS the record's
``knowledge_id``, the canonical JSON payload, the registry-driven supersede chain), the downstream
payoff (``generate_manifest.py`` derives ``current`` vs ``superseded`` from the fact chain), and
that the reducer covers every spec in the real ``experiments/specs/index.json``.

Everything runs against fixture entries and a ``tmp_path`` registry; nothing here needs Redis, an
LLM, or the live corpus (except the one corpus-coverage test, which reads the generated index).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from agentic_dynamics.control import fact_ingestion as fi
from agentic_dynamics.control.facts import (
    Authority,
    CanonicalFact,
    EvidenceItem,
    ReducerInput,
    compute_fact_entity_id,
    verify_chain,
)
from agentic_dynamics.control.reducers import (
    REDUCERS,
    SPEC_STATUS_V1,
    get_reducer,
    spec_status_v1,
)
from agentic_dynamics.experiment.spec_status import SpecStatusEntry
from agentic_dynamics.knowledge.spec_ingestion import load_index_entries, registry_head

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REVISION = "0123456789abcdef0123456789abcdef01234567"
NOW = "2026-08-22T00:00:00+00:00"
REPO = "agentic-dynamics"

#: The eight predicates the design pins for spec_status/v1 (design §3.5 + §9 I1).
PINNED_PREDICATES = {
    "spec_status",
    "spec_superseded_by",
    "spec_supersedes",
    "spec_last_run_at",
    "spec_latest_ok",
    "spec_latest_model",
    "spec_latest_cost_usd",
    "spec_n_runs",
}


# ── Fixtures ────────────────────────────────────────────────────


def _entry(name: str = "alpha", **overrides) -> dict:
    """A minimal index entry — the dict shape ``index.json`` hands the producer."""
    base: dict = {
        "name": name,
        "version": "0.2",
        "status": "runnable",
        "supersedes": [],
        "superseded_by": None,
        "last_run_at": None,
        "latest_ok": None,
        "latest_model": None,
        "latest_cost_usd": None,
        "n_runs": 0,
    }
    base.update(overrides)
    return base


def _full_entry(**overrides) -> dict:
    """A fully-populated entry — a spec that has run and been superseded."""
    base = dict(
        name="alpha",
        version="0.2",
        status="superseded",
        supersedes=["alpha_v1"],
        superseded_by="alpha_v3",
        last_run_at="2026-08-18T15:30:00+00:00",
        latest_ok=True,
        latest_model="anthropic/claude-opus-5",
        latest_cost_usd=2.5,
        n_runs=2,
    )
    base.update(overrides)
    return base


def _inp(*entries: dict, revision: str = REVISION, now: str = NOW) -> ReducerInput:
    """Build the reducer's input: one ``EvidenceItem`` per entry, injected clock + revision."""
    return ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workload",
        scope_id="",
        repository_id=REPO,
        evidence=tuple(
            EvidenceItem(source_type="spec", evidence_id=f"spec:{e['name']}", payload=e)
            for e in entries
        ),
        facts=(),
        now=now,
        source_revision=revision,
    )


def _reduce(*entries: dict) -> list[CanonicalFact]:
    return spec_status_v1(_inp(*entries))


def _by_predicate(facts: list[CanonicalFact]) -> dict[str, list[CanonicalFact]]:
    out: dict[str, list[CanonicalFact]] = {}
    for fact in facts:
        out.setdefault(fact.predicate, []).append(fact)
    return out


_NO_REASON = object()


def _registration_line(record, *, reason=_NO_REASON) -> dict:
    """The line ``kb_worker.py``'s kb-registry-v1 handler appends for one record.

    Mirrored field-for-field (rather than importing the worker, which needs Redis) so a drift
    between what the worker writes and what ``registry_head`` reads shows up as a test failure.
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
        "reason": fi.fact_reason(record) if reason is _NO_REASON else reason,
    }


def _registry(tmp_path: Path, *rows: dict) -> Path:
    """Write a fixture ``registry_index.jsonl`` and return its path."""
    path = tmp_path / "registry_index.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def _load_manifest_module():
    """Import ``scripts/generate_manifest.py`` as a module (it is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "generate_manifest", PROJECT_ROOT / "scripts" / "generate_manifest.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── Reducer declaration (§4.1, §9 I1) ───────────────────────────


def test_reducer_is_registered_with_its_pinned_predicates():
    assert REDUCERS[SPEC_STATUS_V1.version] is SPEC_STATUS_V1
    assert SPEC_STATUS_V1.name == "spec_status"
    assert SPEC_STATUS_V1.level == "fact"
    assert SPEC_STATUS_V1.scope_type == "workload"
    assert SPEC_STATUS_V1.consumes == ("spec",)
    assert set(SPEC_STATUS_V1.produces) == PINNED_PREDICATES
    assert callable(get_reducer("spec_status/v1"))
    assert get_reducer("ghost/v1") is None


def test_every_produced_predicate_is_declared_in_the_registry():
    # The produced_by invariant, checked in the other direction: every predicate a reducer emits
    # must exist in FACT_PREDICATES with this reducer named as its producer.
    from agentic_dynamics.control.facts import FACT_PREDICATES

    for predicate in SPEC_STATUS_V1.produces:
        assert predicate in FACT_PREDICATES
        assert "spec_status/v1" in FACT_PREDICATES[predicate].produced_by


# ── The reducer (pure) ──────────────────────────────────────────


def test_reducer_emits_the_two_always_known_facts_for_a_never_run_spec():
    facts = _reduce(_entry(name="alpha", status="runnable", n_runs=0))
    assert {f.predicate for f in facts} == {"spec_status", "spec_n_runs"}


def test_reducer_emits_every_pinned_predicate_for_a_full_entry():
    assert {f.predicate for f in _reduce(_full_entry())} == PINNED_PREDICATES


def test_unmeasured_fields_are_absent_not_fabricated():
    # The closure's measurement-coverage primitive (Addendum A.5): an unmeasured field is
    # absent (the compiler later reads "no fact" as unknown), never a defaulted 0/false.
    facts = _reduce(_entry(name="alpha", n_runs=0))
    preds = {f.predicate for f in facts}
    for absent in (
        "spec_last_run_at",
        "spec_latest_ok",
        "spec_latest_model",
        "spec_latest_cost_usd",
    ):
        assert absent not in preds


def test_value_encoding_is_canonical():
    by = _by_predicate(_reduce(_full_entry()))
    assert by["spec_status"][0].value == "superseded"
    assert by["spec_n_runs"][0].value == "2"
    assert by["spec_superseded_by"][0].value == "alpha_v3"
    assert by["spec_supersedes"][0].value == "alpha_v1"
    assert by["spec_last_run_at"][0].value == "2026-08-18T15:30:00+00:00"
    assert by["spec_latest_ok"][0].value == "true"
    assert by["spec_latest_model"][0].value == "anthropic/claude-opus-5"
    assert by["spec_latest_cost_usd"][0].value == "2.5"


def test_supersedes_list_encodes_as_an_enum_list():
    fact = _by_predicate(_reduce(_full_entry(supersedes=["a", "b"])))["spec_supersedes"][0]
    assert fact.value == "a,b"
    assert fact.value_type == "enum-list"


def test_fact_scope_subject_and_epistemics():
    fact = _reduce(_entry(name="alpha"))[0]
    assert fact.scope_type == "workload"
    assert fact.scope_id == "alpha"
    assert fact.scope_path == "org:agentic-dynamics/workload:alpha"
    assert fact.subject_type == "spec"
    assert fact.subject_id == "alpha"
    assert fact.abstraction_level == "fact"
    assert fact.epistemic_status == "derived"
    assert fact.authority is Authority.DERIVED
    assert fact.evidence_class == "[C]"
    assert fact.reducer == "spec_status"
    assert fact.reducer_version == "spec_status/v1"
    assert fact.repository_id == REPO
    assert fact.source_revision == REVISION
    assert fact.evidence_ids == ()
    assert fact.fact_id == ""  # finalized at persistence (the record's knowledge_id)


def test_fact_entity_id_is_stable_and_matches_the_identity_formula():
    a = _reduce(_entry(name="alpha"))[0]
    # A different clock and revision must NOT move the entity slot (keyed by scope/subject/
    # predicate, never by time or revision — design §3.2).
    b = spec_status_v1(
        _inp(_entry(name="alpha"), revision="feedface", now="2027-01-01T00:00:00+00:00")
    )[0]
    assert a.fact_entity_id == b.fact_entity_id
    assert a.fact_entity_id == compute_fact_entity_id(
        repository_id=REPO,
        scope_type="workload",
        scope_id="alpha",
        predicate=a.predicate,
        subject_type="spec",
        subject_id="alpha",
    )


def test_reducer_is_deterministic():
    a = _reduce(_full_entry(), _entry(name="beta"))
    b = _reduce(_full_entry(), _entry(name="beta"))
    assert [(f.predicate, f.value, f.fact_entity_id, f.inputs_digest) for f in a] == [
        (f.predicate, f.value, f.fact_entity_id, f.inputs_digest) for f in b
    ]


def test_reducer_is_total_over_empty_and_nameless_evidence():
    assert _reduce() == []
    # An evidence item whose entry has no name is skipped, not crashed on.
    inp = ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workload",
        scope_id="",
        repository_id=REPO,
        evidence=(EvidenceItem(source_type="spec", evidence_id="spec:?", payload={"status": "x"}),),
        facts=(),
        now=NOW,
        source_revision=REVISION,
    )
    assert spec_status_v1(inp) == []


def test_reducer_accepts_a_spec_status_entry_object():
    entry = SpecStatusEntry(
        name="alpha", version="0.2", status="runnable", spec_path="experiments/specs/alpha.yaml"
    )
    inp = ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workload",
        scope_id="",
        repository_id=REPO,
        evidence=(EvidenceItem(source_type="spec", evidence_id="spec:alpha", payload=entry),),
        facts=(),
        now=NOW,
        source_revision=REVISION,
    )
    assert {f.predicate for f in spec_status_v1(inp)} == {"spec_status", "spec_n_runs"}


# ── fact ingestion: the CanonicalFact → KnowledgeRecord mapping ──


def test_build_fact_record_maps_to_source_type_fact():
    fact = _reduce(_entry(name="alpha"))[0]
    record = fi.build_fact_record(fact)
    assert record.source_type == "fact"
    assert record.entity_id == fact.fact_entity_id
    assert record.extractor_version == "spec_status/v1"
    assert record.authority is Authority.DERIVED
    assert record.evidence_class == "[C]"
    assert record.source_uri == f"fact://workload/alpha/{fact.predicate}"
    assert record.logical_locator == f"spec:alpha#{fact.predicate}"
    assert record.valid_from == fact.valid_from
    assert record.valid_to is None


def test_fact_id_is_the_record_knowledge_id_and_verify_chain_accepts():
    # The design §3.3 invariant: the record's knowledge_id IS the fact's fact_id, and the
    # finalized fact passes verify_chain against the REDUCERS registry (the full reducer →
    # fact → record → fact_id loop).
    fact = _reduce(_full_entry())[0]
    record = fi.build_fact_record(fact)
    finalized = fi.finalize_fact(fact, record)
    assert finalized.fact_id == record.knowledge_id
    assert verify_chain(finalized, REDUCERS) == []


def test_payload_is_canonical_json_with_sorted_keys():
    fact = _reduce(_full_entry())[0]
    payload = json.loads(fi.build_fact_record(fact).text)
    assert payload["predicate"] == "spec_status"
    assert payload["value"] == "superseded"
    assert payload["subject_type"] == "spec"
    assert payload["subject_id"] == "alpha"
    assert payload["scope_path"] == "org:agentic-dynamics/workload:alpha"
    assert payload["reducer_version"] == "spec_status/v1"
    assert payload["evidence_ids"] == []
    assert list(payload) == sorted(payload)  # sorted keys — deterministic


def test_fact_operation_and_reason():
    plain = fi.build_fact_record(_reduce(_entry())[0])
    assert fi.fact_operation(plain) == "upsert"
    assert fi.fact_event(plain).operation == "upsert"

    linked = fi.build_fact_record(_reduce(_entry())[0], supersedes=plain.knowledge_id)
    assert fi.fact_operation(linked) == "supersede"
    assert fi.fact_event(linked).operation == "supersede"
    assert fi.fact_event(linked).reason.startswith(fi.REASON_PREFIX)


def test_fact_fingerprint_ignores_the_chain_position():
    # The convergence guard depends on this exactly: linking a predecessor changes the id, but
    # must NOT change the "did the fact change?" answer.
    plain = fi.build_fact_record(_reduce(_entry())[0])
    linked = fi.build_fact_record(_reduce(_entry())[0], supersedes=plain.knowledge_id)
    assert fi.fact_fingerprint(plain) == fi.fact_fingerprint(linked)
    assert plain.knowledge_id != linked.knowledge_id


# ── derive_fact_records: the supersede chain ────────────────────


def test_derive_first_version_is_upsert(tmp_path: Path):
    facts = _reduce(_entry(name="alpha", n_runs=0))
    records = fi.derive_fact_records(facts, registry_path=tmp_path / "r.jsonl")
    assert len(records) == 2  # spec_status + spec_n_runs
    assert all(r.supersedes is None for r in records)
    assert all(fi.fact_operation(r) == "upsert" for r in records)


def test_derive_changed_value_supersedes_the_predecessor(tmp_path: Path):
    v1 = fi.derive_fact_records(
        _reduce(_entry(name="alpha", status="runnable", n_runs=0)),
        registry_path=tmp_path / "r.jsonl",
    )
    v1_by_locator = {r.logical_locator: r for r in v1}
    path = _registry(tmp_path, *[_registration_line(r) for r in v1])

    # The spec has since run and been superseded: the always-known predicates change, and the
    # measured predicates are new.
    v2 = fi.derive_fact_records(
        _reduce(
            _full_entry(
                name="alpha", status="completed", n_runs=1, supersedes=[], superseded_by=None
            )
        ),
        registry_path=path,
    )
    for record in v2:
        if record.logical_locator in v1_by_locator:
            # Changed value: links its predecessor (the same-entity version chain).
            assert record.supersedes == v1_by_locator[record.logical_locator].knowledge_id
            assert fi.fact_operation(record) == "supersede"
        else:
            # Newly-measured predicate: a first version, no predecessor.
            assert record.supersedes is None
            assert fi.fact_operation(record) == "upsert"
    assert any(fi.fact_operation(r) == "supersede" for r in v2)


def test_derive_unchanged_value_is_a_no_op(tmp_path: Path):
    facts = _reduce(_entry(name="alpha", n_runs=0))
    v1 = fi.derive_fact_records(facts, registry_path=tmp_path / "r.jsonl")
    path = _registry(tmp_path, *[_registration_line(r) for r in v1])
    assert fi.derive_fact_records(facts, registry_path=path) == []


def test_chain_converges_over_repeated_rounds(tmp_path: Path):
    path = tmp_path / "r.jsonl"
    rows: list[dict] = []

    def round_(entry) -> list:
        emitted = fi.derive_fact_records(_reduce(entry), registry_path=path)
        rows.extend(_registration_line(r) for r in emitted)
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
        return emitted

    first = round_(_entry(name="alpha", status="runnable", n_runs=0))
    unchanged = round_(_entry(name="alpha", status="runnable", n_runs=0))
    changed = round_(_entry(name="alpha", status="completed", n_runs=1))
    settled = round_(_entry(name="alpha", status="completed", n_runs=1))

    assert len(first) == 2 and all(r.supersedes is None for r in first)
    assert unchanged == []
    superseded = [r for r in changed if r.supersedes is not None]
    assert {r.logical_locator for r in superseded} == {
        "spec:alpha#spec_status",
        "spec:alpha#spec_n_runs",
    }
    assert settled == []


def test_registry_head_parses_the_fact_fingerprint_prefix(tmp_path: Path):
    record = fi.build_fact_record(_reduce(_entry())[0])
    path = _registry(tmp_path, _registration_line(record))
    head = registry_head(record.entity_id, registry_path=path, reason_prefix=fi.REASON_PREFIX)
    assert head.knowledge_id == record.knowledge_id
    assert head.fingerprint == fi.fact_fingerprint(record)


# ── generate_manifest lifecycle derivation over the fact chain ──


def test_manifest_compaction_derives_current_vs_superseded_for_facts(tmp_path: Path):
    gm = _load_manifest_module()

    v1_status = fi.build_fact_record(_reduce(_entry(name="alpha", status="runnable", n_runs=0))[0])
    v2_status = fi.build_fact_record(
        _reduce(_entry(name="alpha", status="completed", n_runs=1))[0],
        supersedes=v1_status.knowledge_id,
    )
    path = _registry(tmp_path, _registration_line(v1_status), _registration_line(v2_status))

    compacted = gm._compact_registry_index(path)
    rows = {r["entity_id"]: r for r in compacted}
    assert set(rows) == {v1_status.entity_id}  # one row per entity_id
    assert rows[v1_status.entity_id]["knowledge_id"] == v2_status.knowledge_id
    assert rows[v1_status.entity_id]["lifecycle_state"] == "current"

    # The predecessor is derived as superseded, whatever its own line said.
    state, _valid_to = gm._derive_lifecycle(
        {
            "knowledge_id": v1_status.knowledge_id,
            "entity_id": v1_status.entity_id,
            "lifecycle_state": "current",
        },
        {v1_status.knowledge_id: {"observed_at": v2_status.observed_at}},
    )
    assert state == "superseded"


# ── Corpus coverage (the §9 I1 gate's dry-run claim) ────────────


def test_reducer_covers_every_spec_in_the_real_index():
    entries = load_index_entries()
    assert entries, "run `python scripts/spec_status.py` to generate experiments/specs/index.json"
    facts = spec_status_v1(_inp(*[e.to_dict() for e in entries]))
    by = _by_predicate(facts)
    assert len(by["spec_status"]) == len(entries)  # one spec_status fact per spec
    assert len(by["spec_n_runs"]) == len(entries)  # ... and one spec_n_runs fact per spec
    # Every fact is scoped to its spec's workload scope.
    assert {f.scope_id for f in facts} == {e.name for e in entries}
