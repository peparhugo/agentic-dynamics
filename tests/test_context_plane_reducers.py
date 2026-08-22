"""Tests for CAP I1–I2 — the fact reducers, fact ingestion, and the facts producer.

I1 (``spec_status/v1``): the reducer's declaration, purity and determinism, the measured-or-absent
semantics (an unmeasured run field is *absent*, never a fabricated ``0``/``false``), the fact shape
(workload scope, ``derived`` epistemics, time-invariant ``fact_entity_id``), the fact-ingestion
mapping (``fact_id`` IS the record's ``knowledge_id``, the canonical JSON payload, the
registry-driven supersede chain), the downstream payoff (``generate_manifest.py`` derives
``current`` vs ``superseded``), and corpus coverage.

I2 (``attempt_facts/v1`` + ``job_facts/v1``): per-phase and per-run facts over the typed workflow
run artifacts, the per-predicate epistemics (``observed``/``verified``/``advisory``), the
job-qualified attempt scope, and — the I2 gate — byte-for-byte re-derivation stability (two runs
over identical run JSONs yield identical fact values and ``knowledge_id``s).

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
    fact_state,
    verify_chain,
)
from agentic_dynamics.control.reducers import (
    ATTEMPT_FACTS_V1,
    JOB_FACTS_V1,
    POLICY_FACTS_V1,
    REDUCERS,
    SPEC_STATUS_V1,
    WORKFLOW_FACTS_V1,
    attempt_facts_v1,
    get_reducer,
    job_facts_v1,
    policy_facts_v1,
    spec_status_v1,
    workflow_facts_v1,
)
from agentic_dynamics.control.reducers.policy_facts import tighten
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


# ── I2: attempt_facts/v1 + job_facts/v1 over the typed run artifacts ──

#: The two I2 reducer versions.
ATTEMPT_FACTS_PRODUCES = {
    "phase_status",
    "attempt_model",
    "attempt_tokens_in",
    "attempt_tokens_out",
    "attempt_cost_usd",
    "attempt_cache_hit_rate",
    "phase_test_verified",
    "attempt_confidence",
    "phase_commit",
}
JOB_FACTS_PRODUCES = {"current_commit", "job_accumulated_cost_usd", "job_status", "job_n_phases"}


def _run(**overrides) -> dict:
    """A minimal typed run artifact — the ``WorkflowRunResult.to_dict()`` shape."""
    base = {
        "spec_name": "foo",
        "spec_id": "foo@1.0",
        "model": "deepseek/deepseek-v4-pro",
        "workdir": "/tmp/pipeline/feature_foo",
        "goal": "build foo",
        "git_sha": "abc123",
        "started_at": "2026-08-22T00:00:00+00:00",
        "ended_at": "2026-08-22T00:10:00+00:00",
        "total_cost_usd": 1.5,
        "ok": True,
        "phases": [
            {
                "phase": "implement",
                "kind": "agent",
                "status": "ok",
                "model": "deepseek/deepseek-v4-pro",
                "commit_hash": "abc123",
                "tokens": {"in": 100, "out": 50},
                "cost_usd": 1.0,
                "cache_hit_rate": 0.5,
                "confidence": 0.9,
            },
            {
                "phase": "test",
                "kind": "test",
                "status": "ok",
                "test_executed_success": True,
            },
        ],
    }
    base.update(overrides)
    return base


def _runs_inp(*runs: dict, repository_id: str = REPO, now: str = NOW) -> ReducerInput:
    """Build a ReducerInput whose evidence is the given run JSONs (the I2 producer's shape)."""
    return ReducerInput(
        scope_path=f"org:{repository_id}",
        scope_type="workload",
        scope_id="",
        repository_id=repository_id,
        evidence=tuple(
            EvidenceItem(
                source_type="workflow_run",
                evidence_id=f"workflow:{r.get('spec_name') or '?'}",
                payload=r,
            )
            for r in runs
        ),
        facts=(),
        now=now,
        source_revision=REVISION,
    )


def test_i2_reducers_are_registered():
    assert REDUCERS[ATTEMPT_FACTS_V1.version] is ATTEMPT_FACTS_V1
    assert ATTEMPT_FACTS_V1.name == "attempt_facts"
    assert ATTEMPT_FACTS_V1.level == "fact"
    assert ATTEMPT_FACTS_V1.scope_type == "attempt"
    assert ATTEMPT_FACTS_V1.consumes == ("workflow_run",)
    assert set(ATTEMPT_FACTS_V1.produces) == ATTEMPT_FACTS_PRODUCES

    assert REDUCERS[JOB_FACTS_V1.version] is JOB_FACTS_V1
    assert JOB_FACTS_V1.name == "job_facts"
    assert JOB_FACTS_V1.level == "job"
    assert JOB_FACTS_V1.scope_type == "job"
    assert JOB_FACTS_V1.consumes == ("workflow_run",)
    assert set(JOB_FACTS_V1.produces) == JOB_FACTS_PRODUCES

    assert callable(get_reducer("attempt_facts/v1"))
    assert callable(get_reducer("job_facts/v1"))


def test_attempt_facts_emit_per_phase_and_per_predicate():
    facts = attempt_facts_v1(_runs_inp(_run()))
    by = _by_predicate(facts)
    # Agent phase: 8 predicates (no test_executed_success); test phase: 2 (status + verified).
    assert by["phase_status"] and len(by["phase_status"]) == 2
    assert by["attempt_model"][0].value == "deepseek/deepseek-v4-pro"
    assert by["attempt_tokens_in"][0].value == "100"
    assert by["attempt_tokens_out"][0].value == "50"
    assert by["attempt_cost_usd"][0].value == "1.0"
    assert by["attempt_cache_hit_rate"][0].value == "0.5"
    assert by["attempt_confidence"][0].value == "0.9"
    assert by["phase_commit"][0].value == "abc123"
    assert by["phase_test_verified"][0].value == "true"


def test_attempt_fact_scope_is_job_qualified():
    facts = attempt_facts_v1(_runs_inp(_run()))
    status = _by_predicate(facts)["phase_status"][0]
    # scope attempt:<phase> under job:<workflow-cell> — the workflow cell is wf_<spec>_<model>.
    assert status.scope_type == "attempt"
    assert status.scope_id == "wf_foo_deepseek_deepseek_v4_pro:implement"
    assert status.scope_path == (
        "org:agentic-dynamics/workload:foo/job:wf_foo_deepseek_deepseek_v4_pro/attempt:implement"
    )
    assert status.subject_type == "attempt"
    assert status.subject_id == "implement"


def test_attempt_fact_epistemics_follow_the_design():
    by = _by_predicate(attempt_facts_v1(_runs_inp(_run())))
    # measured -> observed [M]; confidence -> advisory [H]; test_executed_success -> verified [M].
    assert by["attempt_cost_usd"][0].epistemic_status == "observed"
    assert by["attempt_cost_usd"][0].authority is Authority.MEASURED
    assert by["attempt_cost_usd"][0].evidence_class == "[M]"
    assert by["attempt_confidence"][0].epistemic_status == "advisory"
    assert by["attempt_confidence"][0].authority is Authority.ADVISORY
    assert by["attempt_confidence"][0].evidence_class == "[H]"
    assert by["phase_test_verified"][0].epistemic_status == "verified"
    assert by["phase_test_verified"][0].authority is Authority.MEASURED


def test_attempt_confidence_is_not_canonical():
    # design §5: confidence is ADVISORY — stored, but is_canonical() refuses it.
    from agentic_dynamics.control.facts import is_canonical

    fact = _by_predicate(attempt_facts_v1(_runs_inp(_run())))["attempt_confidence"][0]
    assert not is_canonical(fact)


def test_attempt_facts_are_measured_or_absent():
    # A test phase carries no model/tokens/cost/cache/confidence — none must be fabricated.
    run = _run(
        phases=[
            {"phase": "test", "kind": "test", "status": "failed", "test_executed_success": False}
        ]
    )
    facts = attempt_facts_v1(_runs_inp(run))
    preds = {f.predicate for f in facts}
    assert preds == {"phase_status", "phase_test_verified"}
    assert _by_predicate(facts)["phase_test_verified"][0].value == "false"


def test_attempt_fact_identity_is_time_invariant():
    # entity_id is keyed by (repo, scope_id, subject, predicate) — never by ended_at/revision.
    a = _by_predicate(attempt_facts_v1(_runs_inp(_run())))["attempt_cost_usd"][0]
    b = attempt_facts_v1(_runs_inp(_run(), now="2027-01-01T00:00:00+00:00"))
    b = _by_predicate(b)["attempt_cost_usd"][0]
    assert a.fact_entity_id == b.fact_entity_id
    assert a.fact_entity_id == compute_fact_entity_id(
        repository_id=REPO,
        scope_type="attempt",
        scope_id="wf_foo_deepseek_deepseek_v4_pro:implement",
        predicate="attempt_cost_usd",
        subject_type="attempt",
        subject_id="implement",
    )


def test_job_facts_emit_the_four_per_run_facts():
    facts = job_facts_v1(_runs_inp(_run()))
    by = _by_predicate(facts)
    assert set(by) == JOB_FACTS_PRODUCES
    assert by["current_commit"][0].value == "abc123"
    assert by["job_accumulated_cost_usd"][0].value == "1.5"
    assert by["job_status"][0].value == "ok"
    assert by["job_n_phases"][0].value == "2"


def test_job_fact_scope_and_epistemics():
    fact = job_facts_v1(_runs_inp(_run()))[0]
    assert fact.scope_type == "job"
    assert fact.scope_id == "wf_foo_deepseek_deepseek_v4_pro"
    assert (
        fact.scope_path == "org:agentic-dynamics/workload:foo/job:wf_foo_deepseek_deepseek_v4_pro"
    )
    assert fact.subject_type == "job"
    assert fact.subject_id == "wf_foo_deepseek_deepseek_v4_pro"
    assert fact.epistemic_status == "observed"
    assert fact.authority is Authority.MEASURED
    assert fact.evidence_class == "[M]"
    assert fact.source_revision == "abc123"  # the run's git_sha, not the producer's revision


def test_job_status_is_enum_not_bool():
    by = _by_predicate(job_facts_v1(_runs_inp(_run(ok=False))))
    assert by["job_status"][0].value == "failed"
    assert by["job_status"][0].value_type == "enum"


def test_unaddressable_run_yields_no_job_facts():
    # No spec_name/model means no cell identity — the run is skipped, never crashed on.
    assert job_facts_v1(_runs_inp({})) == []
    assert attempt_facts_v1(_runs_inp({})) == []


# ── I2 gate: byte-for-byte re-derivation ────────────────────────


def test_re_derivation_is_byte_for_byte_stable():
    """The §9 I2 gate: two runs over identical run JSONs yield identical facts AND knowledge_ids.

    Byte-identity is the whole point: the reducer is pure (no wall clock, no RNG), the fact's
    ``observed_at``/``source_revision`` come from the run JSON itself (not the producer clock),
    and the record's ``knowledge_id`` folds only stable fields (the record factory blanks the
    volatile timestamps). So a re-run is a genuine no-op.
    """
    run = _run()
    first_attempt = attempt_facts_v1(_runs_inp(run))
    second_attempt = attempt_facts_v1(_runs_inp(run))
    first_job = job_facts_v1(_runs_inp(run))
    second_job = job_facts_v1(_runs_inp(run))

    for first, second in (first_attempt, second_attempt), (first_job, second_job):
        assert len(first) == len(second)
        for a, b in zip(first, second, strict=True):
            assert a.predicate == b.predicate
            assert a.value == b.value
            assert a.fact_entity_id == b.fact_entity_id
            assert a.inputs_digest == b.inputs_digest
            # The persistable record — and therefore the fact_id — must be byte-identical too.
            ra, rb = fi.build_fact_record(a), fi.build_fact_record(b)
            assert ra.knowledge_id == rb.knowledge_id
            assert ra.content_hash == rb.content_hash
            assert fi.fact_fingerprint(ra) == fi.fact_fingerprint(rb)


def test_verify_chain_accepts_i2_facts():
    attempt = _by_predicate(attempt_facts_v1(_runs_inp(_run())))["attempt_cost_usd"][0]
    job = job_facts_v1(_runs_inp(_run()))[0]
    for fact in (attempt, job):
        finalized = fi.finalize_fact(fact, fi.build_fact_record(fact))
        assert verify_chain(finalized, REDUCERS) == []


# ── I3: workflow_facts/v1 + policy_facts/v1 + the staleness cascade ──

WORKFLOW_FACTS_PRODUCES = {
    "workflow_phases_completed",
    "workflow_phases_remaining",
    "workflow_status",
    "workflow_health",
    "projected_budget_overrun",
}
POLICY_FACTS_PRODUCES = {"allowed_models", "max_spend_usd", "max_attempts"}


def _config(**overrides) -> dict:
    """A declared L5 config projection — the shape the producer hands ``policy_facts/v1``."""
    base = {
        "name": "foo",
        "budget_usd": 2.0,
        "max_attempts": 5,
        "model_pool": ["deepseek/deepseek-v4-pro", "anthropic/claude-haiku-4-5"],
    }
    base.update(overrides)
    return base


def _policy_inp(*configs: dict) -> ReducerInput:
    return ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workload",
        scope_id="",
        repository_id=REPO,
        evidence=tuple(
            EvidenceItem(source_type="spec", evidence_id=f"spec:{c.get('name') or '?'}", payload=c)
            for c in configs
        ),
        facts=(),
        now=NOW,
        source_revision=REVISION,
    )


def _workflow(run: dict, config: dict | None = None) -> list[CanonicalFact]:
    """Run the full reduction LADDER over one run + config; return the workflow facts."""
    run_inp = _runs_inp(run)
    lower = attempt_facts_v1(run_inp) + job_facts_v1(run_inp)
    if config is not None:
        lower += policy_facts_v1(_policy_inp(config))
    finalized = [fi.finalize_fact(f, fi.build_fact_record(f)) for f in lower]
    wf_inp = ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workflow",
        scope_id="",
        repository_id=REPO,
        evidence=(),
        facts=tuple(finalized),
        now=NOW,
        source_revision=REVISION,
    )
    return workflow_facts_v1(wf_inp)


def test_i3_reducers_are_registered():
    assert REDUCERS[WORKFLOW_FACTS_V1.version] is WORKFLOW_FACTS_V1
    assert WORKFLOW_FACTS_V1.level == "workflow"
    assert WORKFLOW_FACTS_V1.scope_type == "workflow"
    assert set(WORKFLOW_FACTS_V1.produces) == WORKFLOW_FACTS_PRODUCES
    # consumes names the lower-fact predicates (the reduction ladder, §10.2.3).
    assert "phase_status" in WORKFLOW_FACTS_V1.consumes
    assert "job_accumulated_cost_usd" in WORKFLOW_FACTS_V1.consumes
    assert "max_spend_usd" in WORKFLOW_FACTS_V1.consumes

    assert REDUCERS[POLICY_FACTS_V1.version] is POLICY_FACTS_V1
    assert POLICY_FACTS_V1.level == "policy"
    assert POLICY_FACTS_V1.scope_type == "workload"
    assert POLICY_FACTS_V1.consumes == ("spec",)
    assert set(POLICY_FACTS_V1.produces) == POLICY_FACTS_PRODUCES


def test_workflow_predicates_declare_aggregates_from():
    from agentic_dynamics.control.facts import FACT_PREDICATES

    assert FACT_PREDICATES["workflow_phases_completed"].aggregates_from == "phase_status"
    assert FACT_PREDICATES["workflow_phases_remaining"].aggregates_from == "phase_status"
    assert FACT_PREDICATES["workflow_status"].aggregates_from == "job_status"
    assert FACT_PREDICATES["projected_budget_overrun"].aggregates_from == "job_accumulated_cost_usd"


def test_policy_facts_emit_declared_l5_at_workload_scope():
    facts = policy_facts_v1(_policy_inp(_config()))
    by = _by_predicate(facts)
    assert set(by) == POLICY_FACTS_PRODUCES
    assert by["max_spend_usd"][0].value == "2.0"
    assert by["max_attempts"][0].value == "5"
    assert by["allowed_models"][0].value == "deepseek/deepseek-v4-pro,anthropic/claude-haiku-4-5"
    for fact in facts:
        assert fact.scope_type == "workload"
        assert fact.scope_id == "foo"
        assert fact.subject_type == "policy"
        assert fact.epistemic_status == "declared"
        assert fact.authority is Authority.POLICY
        assert fact.evidence_class == "[P]"
        assert fact.evidence_ids == ()  # declared, not reduced from evidence


def test_policy_facts_are_absent_when_undeclared():
    facts = policy_facts_v1(
        _policy_inp(_config(name="bar", budget_usd=None, max_attempts=None, model_pool=[]))
    )
    assert facts == []


def test_tighten_resolves_max_spend_to_the_min_over_the_chain():
    a = _by_predicate(policy_facts_v1(_policy_inp(_config(name="org", budget_usd=10.0))))[
        "max_spend_usd"
    ]
    b = _by_predicate(policy_facts_v1(_policy_inp(_config(name="foo", budget_usd=3.0))))[
        "max_spend_usd"
    ]
    assert tighten(a + b, "max_spend_usd") == "3.0"  # min over the ancestor chain


def test_tighten_resolves_allowed_models_to_the_intersection():
    a = _by_predicate(
        policy_facts_v1(_policy_inp(_config(name="a", model_pool=["m1", "m2", "m3"])))
    )["allowed_models"]
    b = _by_predicate(
        policy_facts_v1(_policy_inp(_config(name="b", model_pool=["m2", "m3", "m4"])))
    )["allowed_models"]
    assert tighten(a + b, "allowed_models") == "m2,m3"


def test_workflow_facts_compute_phase_completion_counts():
    by = _by_predicate(_workflow(_run()))
    assert by["workflow_phases_completed"][0].value == "2"
    assert by["workflow_phases_remaining"][0].value == "0"


def test_workflow_status_and_health():
    by = _by_predicate(_workflow(_run()))
    assert by["workflow_status"][0].value == "completed"
    assert by["workflow_health"][0].value == "healthy"


def test_workflow_health_is_at_risk_when_a_phase_failed():
    run = _run(
        ok=False,
        phases=[
            {
                "phase": "implement",
                "kind": "agent",
                "status": "failed",
                "model": "m",
                "commit_hash": "x",
                "tokens": {"in": 1, "out": 1},
                "cost_usd": 1.0,
            },
            {"phase": "test", "kind": "test", "status": "failed", "test_executed_success": False},
        ],
    )
    by = _by_predicate(_workflow(run))
    assert by["workflow_status"][0].value == "failed"
    assert by["workflow_health"][0].value == "at_risk"


def test_projected_budget_overrun_when_inputs_exist():
    # cost 1.5 vs budget 2.0 → no overrun. cost 1.5 vs budget 1.0 → overrun 0.5.
    run = _run(total_cost_usd=1.5)
    assert (
        _by_predicate(_workflow(run, _config(budget_usd=2.0)))["projected_budget_overrun"][0].value
        == "0.0"
    )
    assert (
        _by_predicate(_workflow(run, _config(budget_usd=1.0)))["projected_budget_overrun"][0].value
        == "0.5"
    )


def test_projected_budget_overrun_is_absent_without_a_ceiling():
    by = _by_predicate(_workflow(_run()))  # no config -> no max_spend_usd
    assert "projected_budget_overrun" not in by


def test_workflow_facts_carry_evidence_ids_and_derived_epistemics():
    facts = _workflow(_run(), _config())
    for fact in facts:
        assert fact.scope_type == "workflow"
        assert fact.scope_id == "wf_foo_deepseek_deepseek_v4_pro"
        assert fact.subject_type == "workflow"
        assert fact.epistemic_status == "derived"
        assert fact.authority is Authority.DERIVED
        assert fact.evidence_class == "[C]"
        # Aggregation carries the child fact_ids (the cascade backbone), never child identities.
        assert fact.evidence_ids  # non-empty
        assert all(isinstance(eid, str) and len(eid) == 64 for eid in fact.evidence_ids)


# ── fact_state (§4.5) — the staleness cascade ──────────────────


def _resolve(rows: dict[str, dict]) -> callable:
    def resolve(eid: str) -> dict | None:
        return rows.get(eid)

    return resolve


def test_fact_state_current():
    fact = _workflow(_run())[0]
    fact = fi.finalize_fact(fact, fi.build_fact_record(fact))
    assert (
        fact_state(fact, now=NOW, resolve=_resolve({fact.fact_id: {"lifecycle_state": "current"}}))
        == "current"
    )


def test_fact_state_superseded_and_tombstoned():
    fact = fi.finalize_fact(_workflow(_run())[0], fi.build_fact_record(_workflow(_run())[0]))
    assert (
        fact_state(
            fact, now=NOW, resolve=_resolve({fact.fact_id: {"lifecycle_state": "superseded"}})
        )
        == "superseded"
    )
    assert (
        fact_state(
            fact, now=NOW, resolve=_resolve({fact.fact_id: {"lifecycle_state": "tombstoned"}})
        )
        == "tombstoned"
    )


def test_fact_state_conflicted():
    fact = fi.finalize_fact(_workflow(_run())[0], fi.build_fact_record(_workflow(_run())[0]))
    rows = (
        {"knowledge_id": fact.fact_id, "lifecycle_state": "current"},
        {"knowledge_id": "other_fact_id", "lifecycle_state": "current"},
    )
    state = fact_state(
        fact,
        now=NOW,
        resolve=_resolve({fact.fact_id: {"lifecycle_state": "current"}}),
        current_versions=lambda _eid: rows,
    )
    assert state == "conflicted"


def test_fact_state_expired_fact_is_stale():
    fact = fi.finalize_fact(_workflow(_run())[0], fi.build_fact_record(_workflow(_run())[0]))
    from dataclasses import replace

    expired = replace(fact, expires_at="2026-01-01T00:00:00+00:00")
    assert fact_state(expired, now=NOW, resolve=_resolve({})) == "stale"


def test_staleness_cascade_superseding_an_l1_fact_makes_the_l3_fact_stale():
    """The §9 I3 gate: supersede an L1 fact; the L3 workflow fact that cites it resolves stale.

    The workflow fact's ``evidence_ids`` carry the finalized L1 ``phase_status`` fact_id. When
    that L1 fact is superseded (its registry row now reads ``superseded``), ``fact_state`` walks
    the evidence set, finds a non-current input, and marks the L3 fact stale — with no write and
    no scheduler (read-time derivation, §4.5).
    """
    run = _run()
    # The L1 rung: one phase_status fact, finalized (fact_id == the record's knowledge_id).
    l1 = _by_predicate(attempt_facts_v1(_runs_inp(run)))["phase_status"][0]
    l1 = fi.finalize_fact(l1, fi.build_fact_record(l1))

    # The L3 rung: the workflow fact, whose evidence_ids cite l1.fact_id.
    l3 = _workflow(run)[0]
    l3 = fi.finalize_fact(l3, fi.build_fact_record(l3))
    assert l1.fact_id in l3.evidence_ids  # the citation that makes the cascade transitive

    # Before the supersede: everything resolves current -> the L3 fact is current.
    rows = {eid: {"lifecycle_state": "current"} for eid in l3.evidence_ids}
    assert fact_state(l3, now=NOW, resolve=_resolve(rows)) == "current"

    # Supersede the L1 fact: its own row now reads "superseded".
    rows[l1.fact_id] = {"lifecycle_state": "superseded"}
    assert fact_state(l3, now=NOW, resolve=_resolve(rows)) == "stale"


def test_verify_chain_accepts_i3_facts():
    for fact in _workflow(_run(), _config()):
        finalized = fi.finalize_fact(fact, fi.build_fact_record(fact))
        assert verify_chain(finalized, REDUCERS) == []
    for fact in policy_facts_v1(_policy_inp(_config())):
        finalized = fi.finalize_fact(fact, fi.build_fact_record(fact))
        assert verify_chain(finalized, REDUCERS) == []
