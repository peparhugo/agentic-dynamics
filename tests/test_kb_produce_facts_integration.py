"""Hermetic integration test for ``scripts/kb_produce_facts.py`` — CAP I0-I3 end-to-end (r3).

``tests/test_context_plane_reducers.py`` already exercises the pure reducers (I1-I3) and
``fact_ingestion`` in isolation — a caller builds a ``ReducerInput`` by hand and inspects the
output. This file is deliberately different: it exercises the PRODUCER layer
(``kb_produce_facts.load_run_jsons`` -> ``_run_evidence`` -> ``derive_facts`` /
``_derive_workflow_facts``) against REAL typed workflow-run JSON files written to a temporary
``experiments/results/workflows/<spec>/<ts>.json`` tree, with a temporary
``registry_index.jsonl`` standing in for the durable registry. This is the layer that reads from
disk, computes real ``run_artifact_id``s from file content, and decides supersession against a
(fixture) registry — the layer the reducer-only tests cannot reach because they never touch
``load_run_jsons`` or ``derive_fact_records`` together against real files.

GUARD (no Redis/network): the test never calls ``kb_produce_facts.main()``/``emit_records()``
(which need a live Redis connection to publish events and read the checkpoint hash) — only the
pure derivation path (``load_run_jsons`` -> ``derive_facts``), which does real filesystem I/O but
no network I/O. Registry persistence is simulated by writing the SAME registration-line shape
``kb_worker.py``'s ``kb-registry-v1`` consumer would append (mirrored field-for-field, exactly as
``test_context_plane_reducers.py``'s ``_registration_line`` helper does), so a producer "round"
looks, to ``fact_ingestion.derive_fact_records``, exactly like it would after a real (Redis-backed)
round had already run and been compacted.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from agentic_dynamics.control import fact_ingestion as fi
from agentic_dynamics.control.facts import EvidenceItem, ReducerInput, fact_state
from agentic_dynamics.control.reducers import attempt_facts_v1, job_facts_v1, workflow_facts_v1
from agentic_dynamics.control.reducers._common import run_artifact_id

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO = "agentic-dynamics"
REVISION = "0123456789abcdef0123456789abcdef01234567"
NOW = "2026-08-23T00:00:00+00:00"


# ── Fixtures / helpers ───────────────────────────────────────────


def _load_kb_produce_facts():
    """Import ``scripts/kb_produce_facts.py`` as a module (mirrors the existing
    ``_load_manifest_module`` pattern in ``test_context_plane_reducers.py``) — it is not a
    package, so this is the only way to reach its functions without shelling out."""
    spec = importlib.util.spec_from_file_location(
        "kb_produce_facts_under_test", PROJECT_ROOT / "scripts" / "kb_produce_facts.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def kpf(tmp_path, monkeypatch):
    """A fresh ``kb_produce_facts`` module, hermetically re-rooted at ``tmp_path``.

    ``REPO_ROOT`` drives ``load_run_jsons``/``load_spec_configs``; ``REGISTRY_INDEX_PATH`` drives
    every ``fact_ingestion.derive_fact_records`` call the module makes. Neither the real repo's
    ``experiments/results/workflows/`` nor its ``registry_index.jsonl`` is ever touched.
    """
    module = _load_kb_produce_facts()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    return module


def _write_run(tmp_path: Path, spec_name: str, ts: str, **overrides) -> dict:
    """Write one typed ``WorkflowRunResult.to_dict()``-shaped run JSON to the hermetic tree and
    return the dict written (so a test can assert against the exact bytes on disk)."""
    run: dict = {
        "spec_name": spec_name,
        "spec_id": f"{spec_name}@1.0",
        "model": "deepseek/deepseek-v4-pro",
        "workdir": "/tmp/x",
        "goal": "build it",
        "git_sha": "abc123",
        "started_at": ts,
        "ended_at": ts,
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
                "cost_usd": 1.5,
                "cache_hit_rate": 0.5,
                "confidence": 0.9,
            },
        ],
    }
    run.update(overrides)
    out_dir = tmp_path / "experiments" / "results" / "workflows" / spec_name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{ts}.json").write_text(json.dumps(run))
    return run


def _registration_line(record) -> dict:
    """The line ``kb_worker.py``'s ``kb-registry-v1`` handler would append for one record —
    mirrored field-for-field rather than importing the (Redis-dependent) worker, exactly as
    ``test_context_plane_reducers.py``'s helper of the same name does."""
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
        "reason": fi.fact_reason(record),
    }


def _persist(registry_path: Path, *records) -> None:
    """Append registration lines for ``records`` to the hermetic registry (simulates a completed,
    Redis-backed producer round without needing Redis)."""
    lines = "".join(json.dumps(_registration_line(r)) + "\n" for r in records)
    with registry_path.open("a") as f:
        f.write(lines)


# ── 1. load_run_jsons / _run_evidence: exact artifact identity, hermetic I/O ──


def test_load_run_jsons_is_hermetic_and_evidence_identity_is_exact(kpf, tmp_path):
    run = _write_run(tmp_path, "demo", "20260820T000000Z")
    runs = kpf.load_run_jsons()
    assert runs == [run]  # exact round-trip — no mutation, no extra/missing fields

    evidence = kpf._run_evidence(runs)
    assert len(evidence) == 1
    assert isinstance(evidence[0], EvidenceItem)
    # Exact artifact identity: the SAME formula _common.run_artifact_id computes independently.
    assert evidence[0].evidence_id == f"workflow_run:{run_artifact_id(run)}"

    resolve = kpf.evidence_resolver(evidence)
    assert resolve(evidence[0].evidence_id) == run
    assert resolve("workflow_run:doesnotexist") is None


def test_load_run_jsons_orders_deterministically_by_recorded_recency(kpf, tmp_path):
    # Write the LATER run first (lexicographically-earlier filename would sort it first if the
    # loader trusted filesystem order) to prove ordering comes from the run's OWN timestamps.
    later = _write_run(tmp_path, "demo", "aaa_written_first", ended_at="2026-08-22T00:00:00+00:00")
    earlier = _write_run(
        tmp_path, "demo", "zzz_written_second", ended_at="2026-08-20T00:00:00+00:00"
    )
    runs = kpf.load_run_jsons()
    assert runs == [earlier, later]  # oldest-recorded-run-first, not filename order


# ── 2. Full producer round trip: identity, provenance, stability, no-op republication ──


def test_end_to_end_ladder_round_trip(kpf, tmp_path):
    """The INVARIANT, exercised through the real producer: typed run artifact -> evidence item ->
    lower facts -> finalized fact records -> workflow facts -> derivation-chain verification."""
    _write_run(tmp_path, "demo", "20260820T000000Z")

    # --- round 1: derive over an EMPTY registry -> everything is a first version ---
    attempt_records_1 = kpf.derive_facts("attempt_facts/v1", REPO, REVISION, NOW)
    job_records_1 = kpf.derive_facts("job_facts/v1", REPO, REVISION, NOW)
    workflow_records_1 = kpf.derive_facts("workflow_facts/v1", REPO, REVISION, NOW)
    assert attempt_records_1 and job_records_1 and workflow_records_1
    assert all(r.supersedes is None for r in attempt_records_1 + job_records_1)

    # Cross-check against an independently-built raw fact: final fact_id == knowledge_id, and the
    # producer's identity matches the pure reducer's identity for the SAME evidence.
    run_inp = ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workload",
        scope_id="",
        repository_id=REPO,
        evidence=kpf._run_evidence(kpf.load_run_jsons()),
        facts=(),
        now=NOW,
        source_revision=REVISION,
    )
    raw_attempt_facts = attempt_facts_v1(run_inp)
    expected_ids = {fi.build_fact_record(f).knowledge_id for f in raw_attempt_facts}
    assert {r.knowledge_id for r in attempt_records_1} == expected_ids
    for record in attempt_records_1:
        # evidence_ids non-empty and resolvable via the SAME evidence sequence the producer used.
        payload = json.loads(record.text)
        assert payload["evidence_ids"]
        resolve = kpf.evidence_resolver(run_inp.evidence)
        assert all(resolve(eid) is not None for eid in payload["evidence_ids"])

    # The workflow fact's evidence_ids must cite REAL lower fact_ids that were actually finalized
    # this round — the staleness-cascade backbone must be genuinely traceable, not just non-empty.
    # ``derive_facts("workflow_facts/v1")`` returns the FULL ladder (lower_records + wf_records,
    # the p5 registered-id refactor), so pick the workflow-scope records out of it.
    wf_records_1 = [
        r for r in workflow_records_1
        if json.loads(r.text)["predicate"].startswith("workflow_")
        or json.loads(r.text)["predicate"] == "projected_budget_overrun"
    ]
    assert wf_records_1
    lower_ids = {r.knowledge_id for r in attempt_records_1 + job_records_1}
    wf_payload = json.loads(wf_records_1[0].text)
    assert wf_payload["evidence_ids"]
    assert set(wf_payload["evidence_ids"]) <= lower_ids
    assert set(wf_payload["evidence_ids"]) & lower_ids  # genuinely overlaps, not disjoint

    # --- stable re-derivation: same artifact, still-empty registry -> byte-identical ids ---
    attempt_records_1b = kpf.derive_facts("attempt_facts/v1", REPO, REVISION, NOW)
    assert {r.knowledge_id for r in attempt_records_1b} == {
        r.knowledge_id for r in attempt_records_1
    }

    # --- persist round 1, re-derive the SAME artifact -> no publication of unchanged facts ---
    _persist(kpf.REGISTRY_INDEX_PATH, *attempt_records_1, *job_records_1, *workflow_records_1)
    assert kpf.derive_facts("attempt_facts/v1", REPO, REVISION, NOW) == []
    assert kpf.derive_facts("job_facts/v1", REPO, REVISION, NOW) == []
    assert kpf.derive_facts("workflow_facts/v1", REPO, REVISION, NOW) == []

    # --- round 2: a genuinely NEW run of the SAME cell, different cost ---
    _write_run(tmp_path, "demo", "20260822T000000Z", total_cost_usd=9.0)
    attempt_records_2 = kpf.derive_facts("attempt_facts/v1", REPO, REVISION, NOW)
    job_records_2 = kpf.derive_facts("job_facts/v1", REPO, REVISION, NOW)

    # Attempt facts are PER-RUN: round 1's phases stay silent (unchanged), round 2's are entirely
    # NEW, distinct entities — never superseding round 1's (never collide, never merge).
    assert attempt_records_2  # the new run's phases are freshly derived
    assert all(r.supersedes is None for r in attempt_records_2)
    assert {r.entity_id for r in attempt_records_2}.isdisjoint(
        {r.entity_id for r in attempt_records_1}
    )

    # Job facts are CURRENT-PER-CELL: the new run's different cost supersedes round 1's head.
    job_cost_2 = [
        r for r in job_records_2 if json.loads(r.text)["predicate"] == "job_accumulated_cost_usd"
    ]
    assert len(job_cost_2) == 1
    job_cost_1 = [
        r for r in job_records_1 if json.loads(r.text)["predicate"] == "job_accumulated_cost_usd"
    ][0]
    assert job_cost_2[0].supersedes == job_cost_1.knowledge_id
    assert job_cost_2[0].entity_id == job_cost_1.entity_id  # same logical slot


def test_re_derivation_over_registered_multi_run_cell_is_idempotent(kpf, tmp_path):
    """CAP fact backfill p5 idempotency: re-deriving a MULTI-RUN cell's current-per-cell job facts
    after they were already registered must publish NOTHING (the stale-observation guard). Without
    the guard, the OLDER run's fact re-chains onto the newer registered head and mints fresh
    knowledge_ids every pass (the supersede link is hashed into the artifact)."""
    # Two runs of the SAME cell: older cost 5, newer cost 9.
    _write_run(tmp_path, "demo", "20260820T000000Z", total_cost_usd=5.0)
    _write_run(tmp_path, "demo", "20260822T000000Z", total_cost_usd=9.0)

    # Round 1: fresh registry -> the older run is the first version, the newer supersedes it.
    round_1 = kpf.derive_facts("job_facts/v1", REPO, REVISION, NOW)
    _persist(kpf.REGISTRY_INDEX_PATH, *round_1)

    # Round 2: re-derive BOTH runs over the now-populated registry -> the current value is
    # unchanged, so NOTHING is published (idempotent re-derivation, not a fresh re-chain).
    assert kpf.derive_facts("job_facts/v1", REPO, REVISION, NOW) == []

    # A genuinely NEW run (newer still, cost 12) still supersedes the current head normally.
    _write_run(tmp_path, "demo", "20260824T000000Z", total_cost_usd=12.0)
    round_3 = kpf.derive_facts("job_facts/v1", REPO, REVISION, NOW)
    cost_3 = [
        r for r in round_3 if json.loads(r.text)["predicate"] == "job_accumulated_cost_usd"
    ]
    assert len(cost_3) == 1
    # It supersedes round 1's current head (the newest run), not the stale older run.
    current_head = [r for r in round_1 if json.loads(r.text)["predicate"] == "job_accumulated_cost_usd"][-1]
    assert cost_3[0].supersedes == current_head.knowledge_id


def test_multi_run_workflow_fact_cites_registered_lower_ids(kpf, tmp_path):
    """CAP fact backfill p5 provenance: a multi-run cell's workflow facts must cite the LOWER
    facts' REGISTERED knowledge_ids. A current-per-cell job fact is registered under its content
    identity (the supersede link is a chain position, not content — see the linked-record fix in
    ``fact_ingestion.derive_fact_records``), so ``workflow_facts/v1``'s citation of that id
    resolves against the records actually registered in the same batch."""
    _write_run(tmp_path, "demo", "20260820T000000Z", total_cost_usd=5.0)
    _write_run(tmp_path, "demo", "20260822T000000Z", total_cost_usd=9.0)

    run_inp = ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workload",
        scope_id="",
        repository_id=REPO,
        evidence=kpf._run_evidence(kpf.load_run_jsons()),
        facts=(),
        now=NOW,
        source_revision=REVISION,
    )
    lower = attempt_facts_v1(run_inp) + job_facts_v1(run_inp)
    # Use the producer's actual finalization (registered-id mapping via ``identity_out``), not the
    # naive ``build_fact_record`` path: a current-per-cell job fact is registered under its content
    # identity, and the naive path mints an UNREGISTERED knowledge_id for the converged case.
    identity_out: dict[int, str] = {}
    lower_records = fi.derive_fact_records(
        lower, registry_path=kpf.REGISTRY_INDEX_PATH, identity_out=identity_out
    )
    registered_ids = {r.knowledge_id for r in lower_records}
    finalized = kpf._finalize_to_registered(lower, identity_out)
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
    wf_facts = workflow_facts_v1(wf_inp)
    # Every workflow-fact evidence_id must name a lower fact that is REGISTERED this batch.
    for f in wf_facts:
        assert f.evidence_ids
        assert set(f.evidence_ids) <= registered_ids


def test_workflow_facts_use_only_the_current_run(kpf, tmp_path):
    """Current-run aggregation, through the real producer: adding an OLDER failed run of the SAME
    cell must not retroactively appear in a re-derived workflow fact once a newer run exists."""
    _write_run(
        tmp_path,
        "demo",
        "20260820T000000Z",
        ok=False,
        phases=[{"phase": "implement", "kind": "agent", "status": "failed"}],
    )
    _write_run(tmp_path, "demo", "20260822T000000Z")  # a clean, later run of the same cell
    by = {
        json.loads(r.text)["predicate"]: json.loads(r.text)
        for r in kpf.derive_facts("workflow_facts/v1", REPO, REVISION, NOW)
    }
    assert by["workflow_status"]["value"] == "completed"
    assert by["workflow_phases_completed"]["value"] == "1"


# ── 3. Staleness cascade, sourced from the real on-disk artifact ──


def test_staleness_cascade_from_real_producer_evidence(kpf, tmp_path):
    run = _write_run(tmp_path, "demo", "20260820T000000Z")

    # Load through the REAL producer path, then run the ladder ourselves (mirroring
    # kb_produce_facts._derive_workflow_facts's own steps) so we can inspect the intermediate
    # CanonicalFact objects fact_state() needs (fact_id/evidence_ids), which the persisted
    # KnowledgeRecord alone does not carry.
    run_inp = ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workload",
        scope_id="",
        repository_id=REPO,
        evidence=kpf._run_evidence(kpf.load_run_jsons()),
        facts=(),
        now=NOW,
        source_revision=REVISION,
    )
    assert run_inp.evidence and run_inp.evidence[0].payload == run  # real disk-loaded evidence
    lower = attempt_facts_v1(run_inp) + job_facts_v1(run_inp)
    finalized_lower = [fi.finalize_fact(f, fi.build_fact_record(f)) for f in lower]
    wf_inp = ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workflow",
        scope_id="",
        repository_id=REPO,
        evidence=(),
        facts=tuple(finalized_lower),
        now=NOW,
        source_revision=REVISION,
    )
    l3 = workflow_facts_v1(wf_inp)[0]
    l3 = fi.finalize_fact(l3, fi.build_fact_record(l3))
    assert l3.evidence_ids

    l1 = next(f for f in finalized_lower if f.predicate == "phase_status")
    assert l1.fact_id in l3.evidence_ids  # the citation that makes the cascade transitive

    def _resolve(rows):
        return rows.get

    rows = {eid: {"lifecycle_state": "current"} for eid in l3.evidence_ids}
    assert fact_state(l3, now=NOW, resolve=_resolve(rows)) == "current"
    rows[l1.fact_id] = {"lifecycle_state": "superseded"}
    assert fact_state(l3, now=NOW, resolve=_resolve(rows)) == "stale"


# ── 4. Content identity vs run identity, through derive_facts (not just the reducer) ──


def test_fingerprint_ignores_run_identity_through_the_real_producer(kpf, tmp_path):
    """CHECK: fingerprint/supersession must stay byte-stable and never confuse content identity
    with run identity — verified here via the ACTUAL kb_produce_facts.derive_facts entrypoint
    (registry-aware), not a hand-built ReducerInput."""
    _write_run(tmp_path, "demo", "20260820T000000Z", total_cost_usd=1.5)
    round_1 = kpf.derive_facts("job_facts/v1", REPO, REVISION, NOW)
    _persist(kpf.REGISTRY_INDEX_PATH, *round_1)

    # A second run of the SAME cell, SAME cost — different run identity, same content identity.
    _write_run(tmp_path, "demo", "20260822T000000Z", total_cost_usd=1.5)
    round_2 = kpf.derive_facts("job_facts/v1", REPO, REVISION, NOW)
    assert round_2 == []  # re-confirming an unchanged value publishes nothing

    # A third run, cost genuinely changes -> a real new version, correctly chained.
    _write_run(tmp_path, "demo", "20260824T000000Z", total_cost_usd=4.0)
    round_3 = kpf.derive_facts("job_facts/v1", REPO, REVISION, NOW)
    cost_3 = [
        r for r in round_3 if json.loads(r.text)["predicate"] == "job_accumulated_cost_usd"
    ]
    cost_1 = [
        r for r in round_1 if json.loads(r.text)["predicate"] == "job_accumulated_cost_usd"
    ][0]
    assert len(cost_3) == 1
    assert cost_3[0].supersedes == cost_1.knowledge_id


# ── 5. pattern/v1 (CAP addendum I9) through the real producer ──

#: The finding-row shape the canonical resolver produces (``_table`` / ``_registry`` provenance,
#: ``_experiment`` = the task, ``perturbation_class``, measured ``test_executed_success``) —
#: mirrors ``tests/test_context_plane_pattern.py``'s ``_finding`` fixture. The producer's
#: ``_pattern_finding_evidence`` reads ``cc.load_canonical_tables("finding").findings``; the stub
#: below stands in for the (non-hermetic) real manifest read.
PATTERN_FINDINGS = [
    {
        "_table": "finding",
        "_registry": {"entity_id": f"entity_k{i}", "knowledge_id": f"kid_{i}"},
        "_experiment": "task_manager",
        "perturbation_class": "objective_mutation",
        "operator": "invert_constraint",
        "test_executed_success": i % 2 == 0,
        "confidence": 0.5,
        "perturbation_strength": 0.5,
    }
    for i in range(6)
]


def test_pattern_v1_producer_branch(kpf, tmp_path, monkeypatch):
    """The ``pattern/v1`` producer branch (I9): ``derive_facts("pattern/v1", ...)`` loads the
    canonical finding corpus as evidence, mints pattern facts through ``pattern_v1``, and derives
    their records — DERIVED/[C], supersede-free first versions, idempotent re-derivation.

    This is the producer-wiring half the pattern tests referenced (``pattern_v1`` had no call site
    feeding it real evidence); ``derive_facts`` is that call site. Every assertion runs through
    the ACTUAL producer entrypoint (registry-aware), not a hand-built ``ReducerInput``.
    """

    class _StubTables:
        findings = PATTERN_FINDINGS

    monkeypatch.setattr(kpf.cc, "load_canonical_tables", lambda *a, **k: _StubTables())

    # --- round 1: empty registry -> every pattern fact is a first version ---
    records = kpf.derive_facts("pattern/v1", REPO, REVISION, NOW)
    assert records, "the pattern/v1 branch must mint facts from measured finding evidence"
    assert all(r.supersedes is None for r in records)
    for record in records:
        assert record.source_type == "fact"
        payload = json.loads(record.text)
        assert payload["predicate"] == "pattern"
        assert payload["reducer_version"] == "pattern/v1"
        assert payload["abstraction_level"] == "workload"
        # DERIVED/[C] (D7 — the existing epistemic row, never a new one).
        assert record.authority.name == "DERIVED"
        assert record.evidence_class == "[C]"
        assert payload["evidence_ids"]  # every real finding row cited
        value = json.loads(payload["value"])
        assert value["conditions"] == ["test_executed_success=true"]
        assert value["source_experiment"] in payload["evidence_ids"]

    # --- stable re-derivation over the still-empty registry: byte-identical ids ---
    records_b = kpf.derive_facts("pattern/v1", REPO, REVISION, NOW)
    assert {r.knowledge_id for r in records_b} == {r.knowledge_id for r in records}

    # --- persist round 1, re-derive -> no republication of unchanged facts ---
    _persist(kpf.REGISTRY_INDEX_PATH, *records)
    assert kpf.derive_facts("pattern/v1", REPO, REVISION, NOW) == []

