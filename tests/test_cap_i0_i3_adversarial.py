"""CAP I0-I3 adversarial release review (r4) — ROLE: adversarial release reviewer.

This file exists to try to FALSIFY the I0-I3 repair contracts (r1-r3) before I4 is allowed to
begin, per the ten attack vectors the r4 task named. Each test below is named after the vector it
attacks. Two genuine defects were found and fixed here (duplicate evidence inflating workflow
phase counts; out-of-order evidence letting an older observation "win" a supersession race) — see
``docs/context_abstraction/implementation_notes.md`` for the recorded design note. The rest of the
vectors were already closed by r1-r3 and are re-verified here from an adversarial angle (a
different construction than the original repair tests used), or are accepted limitations with a
documented reason (see the module-level comments at each such test).

No Redis/network; no I4 (context_compiler/rules/validator/decisions) imports.
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest

from agentic_dynamics.control import fact_ingestion as fi
from agentic_dynamics.control.facts import (
    EvidenceItem,
    ReducerInput,
    recompute_inputs_digest,
    verify_chain,
)
from agentic_dynamics.control.reducers import (
    REDUCERS,
    attempt_facts_v1,
    job_facts_v1,
    workflow_facts_v1,
)
from agentic_dynamics.control.reducers._common import run_artifact_id

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO = "agentic-dynamics"
REVISION = "0123456789abcdef0123456789abcdef01234567"
NOW = "2026-08-23T00:00:00+00:00"


# ── Shared fixtures ──────────────────────────────────────────────


def _run(**overrides) -> dict:
    base: dict = {
        "spec_name": "demo",
        "spec_id": "demo@1.0",
        "model": "deepseek/deepseek-v4-pro",
        "workdir": "/tmp/x",
        "goal": "build it",
        "git_sha": "abc123",
        "started_at": "2026-08-20T00:00:00+00:00",
        "ended_at": "2026-08-20T00:10:00+00:00",
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
            }
        ],
    }
    base.update(overrides)
    return base


def _evidence(*runs: dict) -> tuple[EvidenceItem, ...]:
    """Build evidence WITHOUT deduping — the raw ``ReducerInput`` shape a caller can hand in,
    used deliberately here (rather than the deduping producer helper) so tests can construct
    adversarial inputs (duplicates, out-of-order) the real producer would normally prevent."""
    return tuple(
        EvidenceItem(
            source_type="workflow_run",
            evidence_id=f"workflow_run:{run_artifact_id(r)}",
            payload=r,
        )
        for r in runs
    )


def _inp(*runs: dict) -> ReducerInput:
    return ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workload",
        scope_id="",
        repository_id=REPO,
        evidence=_evidence(*runs),
        facts=(),
        now=NOW,
        source_revision=REVISION,
    )


def _ladder(*runs: dict):
    """Run attempt+job facts, finalize them, then workflow_facts_v1 — mirrors
    ``kb_produce_facts._derive_workflow_facts`` without the disk/registry I/O."""
    inp = _inp(*runs)
    lower = attempt_facts_v1(inp) + job_facts_v1(inp)
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
    return workflow_facts_v1(wf_inp), finalized


def _load_kb_produce_facts():
    spec = importlib.util.spec_from_file_location(
        "kb_produce_facts_adversarial", PROJECT_ROOT / "scripts" / "kb_produce_facts.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def kpf(tmp_path, monkeypatch):
    module = _load_kb_produce_facts()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    return module


def _write_run(tmp_path: Path, spec_name: str, ts: str, **overrides) -> dict:
    run = _run(spec_name=spec_name, **overrides)
    out_dir = tmp_path / "experiments" / "results" / "workflows" / spec_name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{ts}.json").write_text(json.dumps(run))
    return run


# ── Vector 1: same spec/model/phase across two runs ─────────────
# Already the primary subject of r1 (unique attempt entity per run) and r3 (job supersession).
# Adversarial re-check here: THREE runs (not just two), confirming the chain doesn't short-circuit
# or skip a link when there is more than one supersession in a row.


def test_vector1_job_facts_chain_correctly_across_three_runs(tmp_path: Path):
    run_a = _run(ended_at="2026-08-20T00:00:00+00:00", total_cost_usd=1.0)
    run_b = _run(ended_at="2026-08-21T00:00:00+00:00", total_cost_usd=2.0)
    run_c = _run(ended_at="2026-08-22T00:00:00+00:00", total_cost_usd=3.0)
    inp = _inp(run_a, run_b, run_c)
    facts = job_facts_v1(inp)
    cost_facts = [f for f in facts if f.predicate == "job_accumulated_cost_usd"]
    assert len(cost_facts) == 3
    assert len({f.fact_entity_id for f in cost_facts}) == 1  # one logical slot throughout

    records = fi.derive_fact_records(cost_facts, registry_path=tmp_path / "r.jsonl")
    assert len(records) == 3
    by_value = {json.loads(r.text)["value"]: r for r in records}
    assert by_value["1.0"].supersedes is None
    assert by_value["2.0"].supersedes == by_value["1.0"].knowledge_id
    assert by_value["3.0"].supersedes == by_value["2.0"].knowledge_id  # no skipped link


# ── Vector 2: same artifact re-derived ───────────────────────────
# Covered exhaustively by r1/r3 (byte-identical re-derivation tests). Adversarial re-check:
# re-derive via TWO INDEPENDENT dict objects with identical content (not the same Python object),
# proving identity is content-addressed, not object-identity-addressed.


def test_vector2_rederivation_from_an_independently_constructed_but_identical_dict():
    run_1 = _run()
    run_2 = _run()  # a fresh dict, same content, NOT `run_1 is run_2`
    assert run_1 is not run_2
    assert run_artifact_id(run_1) == run_artifact_id(run_2)
    a = attempt_facts_v1(_inp(run_1))
    b = attempt_facts_v1(_inp(run_2))
    assert [f.fact_entity_id for f in a] == [f.fact_entity_id for f in b]
    ra = [fi.build_fact_record(f) for f in a]
    rb = [fi.build_fact_record(f) for f in b]
    assert [r.knowledge_id for r in ra] == [r.knowledge_id for r in rb]


# ── Vector 3: retry/escalation lineage ───────────────────────────
#
# ACCEPTED LIMITATION (reason-bearing): `attempt_number`/`parent_attempt_id`/`retry_reason`/
# `escalation_from`/`escalation_to` are declared in `experiment_spec.py`'s LEDGER_FIELDS but
# written by NOTHING — `run_workflow.py`/`workflow_runner.py` has no retry loop at all (one pass
# per phase, `stop_on_error`); no such field exists on a WorkflowRunResult JSON today. There is
# therefore no retry/escalation LINEAGE DATA for I0-I3 to carry — instrumenting it is a
# `runtime.workflow_runner` change (retry loop + ledger fields), outside a fact-plane repair's
# scope, and would itself need "measure before policy" sequencing (AGENTS.md's load-bearing rule)
# once it lands. What CAN be verified today is the adjacent claim the repair actually makes: A
# RETRY IS JUST ANOTHER RUN of the same cell, and the content-identity/run-identity split (r3)
# must treat it correctly even when the retry lands on a DIFFERENT commit (the retry's whole
# point) — verified below.


def test_vector3_retry_on_a_new_commit_with_unchanged_value_stays_a_content_identity_no_op(
    tmp_path: Path,
):
    """A "retry" = a new run of the same cell on a NEW commit (git_sha changes) that happens to
    reproduce the SAME measured value. source_revision folds into knowledge_id (so the retry's
    record has a distinct VERSION identity) but must NOT fold into the fingerprint (so an
    unchanged value is still correctly recognized as unchanged) — otherwise every retry that
    doesn't change the number would spuriously supersede, and the registry would grow without
    bound for a cell that is, informationally, standing still."""
    run_a = _run(git_sha="commit1", ended_at="2026-08-20T00:00:00+00:00")
    run_b = _run(git_sha="commit2", ended_at="2026-08-22T00:00:00+00:00")  # retried, same cost
    facts_a = job_facts_v1(_inp(run_a))
    facts_b = job_facts_v1(_inp(run_b))
    cost_a = next(f for f in facts_a if f.predicate == "job_accumulated_cost_usd")
    cost_b = next(f for f in facts_b if f.predicate == "job_accumulated_cost_usd")
    assert cost_a.source_revision != cost_b.source_revision  # the retry's whole point

    record_a, record_b = fi.build_fact_record(cost_a), fi.build_fact_record(cost_b)
    assert record_a.knowledge_id != record_b.knowledge_id  # distinct VERSION (revision differs)
    assert fi.fact_fingerprint(record_a) == fi.fact_fingerprint(record_b)  # same CONTENT

    records = fi.derive_fact_records([cost_a, cost_b], registry_path=tmp_path / "r.jsonl")
    assert len(records) == 1  # the retry does not spuriously supersede an unchanged value


# ── Vector 4: missing vs captured-zero cost ──────────────────────
# r2 covers "missing cost -> no overrun fact". Completing the contrast: a CAPTURED zero cost (a
# real, measured $0.00 run — e.g. a fully cache-served phase) must be emitted, not treated as
# absent, at BOTH the job level and the workflow-overrun level.


def test_vector4_captured_zero_cost_is_emitted_at_job_and_workflow_level():
    run = _run(total_cost_usd=0.0, phases=[{"phase": "implement", "kind": "agent", "status": "ok"}])
    job_facts = job_facts_v1(_inp(run))
    cost_fact = next(f for f in job_facts if f.predicate == "job_accumulated_cost_usd")
    assert cost_fact.value == "0.0"  # present, not silently dropped by a falsy-0.0 check

    config = {"name": "demo", "budget_usd": 2.0, "max_attempts": 5, "model_pool": ["m"]}
    from agentic_dynamics.control.reducers import policy_facts_v1

    policy_inp = ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workload",
        scope_id="",
        repository_id=REPO,
        evidence=(EvidenceItem(source_type="spec", evidence_id="spec:demo", payload=config),),
        facts=(),
        now=NOW,
        source_revision=REVISION,
    )
    inp = _inp(run)
    lower = attempt_facts_v1(inp) + job_facts_v1(inp) + policy_facts_v1(policy_inp)
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
    by = {f.predicate: f.value for f in workflow_facts_v1(wf_inp)}
    assert by["projected_budget_overrun"] == "0.0"  # a real, measured zero — not absent


# ── Vector 5: missing vs measured-zero tokens ────────────────────
# r1 covers the measured-zero half explicitly. Completing the contrast in one place: a phase with
# NO tokens key at all emits neither predicate, while a phase with in=0/out=5 emits BOTH
# correctly (0 present, not merged with the "absent" branch).


def test_vector5_missing_tokens_vs_measured_zero_tokens_side_by_side():
    no_tokens = _run(
        phases=[{"phase": "implement", "kind": "agent", "status": "ok", "model": "m"}]
    )
    zero_in = _run(
        phases=[
            {
                "phase": "implement",
                "kind": "agent",
                "status": "ok",
                "model": "m",
                "tokens": {"in": 0, "out": 5},
            }
        ]
    )
    preds_missing = {f.predicate for f in attempt_facts_v1(_inp(no_tokens))}
    assert "attempt_tokens_in" not in preds_missing
    assert "attempt_tokens_out" not in preds_missing

    by_zero = {f.predicate: f.value for f in attempt_facts_v1(_inp(zero_in))}
    assert by_zero["attempt_tokens_in"] == "0"
    assert by_zero["attempt_tokens_out"] == "5"


# ── Vector 6: job failed while all intermediate phases are ok ────
# Primary coverage lives in r2 (test_job_status_failed_dominates_all_ok_phase_statuses). Adversarial
# re-check with a DIFFERENT construction: a run where a phase's status is a non-"ok"/non-"failed"
# value ("timeout") — the exact scenario the precedence table's rule 1 was written to catch,
# distinct from r2's "phases individually all literally 'ok'" construction.


def test_vector6_a_non_ok_non_failed_phase_status_is_still_caught_via_job_status():
    run = _run(
        ok=False,
        phases=[{"phase": "implement", "kind": "agent", "status": "timeout"}],
    )
    workflow_facts, _ = _ladder(run)
    by = {f.predicate: f.value for f in workflow_facts}
    # A phase-only scan for the literal string "failed" would see "timeout" and think nothing
    # failed; job_status (WorkflowRunResult.ok) is False and must dominate.
    assert by["workflow_status"] == "failed"
    assert by["workflow_health"] == "at_risk"


# ── Vector 7: duplicate / out-of-order evidence — TWO GENUINE DEFECTS FOUND AND FIXED ──


def test_vector7_duplicate_evidence_does_not_inflate_workflow_phase_counts(kpf, tmp_path):
    """FINDING (fixed): two on-disk files with byte-identical run content used to be handed to
    the reducers as two separate EvidenceItems, doubling every phase/job fact they mint. Fixed in
    ``kb_produce_facts._run_evidence`` (dedup by ``run_artifact_id``) plus defense-in-depth in
    ``workflow_facts_v1`` (dedup ``inp.facts`` by ``fact_id``)."""
    run = _write_run(tmp_path, "demo", "20260820T000000Z")
    # A second file, byte-identical content, different filename (a copy/replay on disk).
    demo_dir = tmp_path / "experiments" / "results" / "workflows" / "demo"
    (demo_dir / "20260820T000000Z_copy.json").write_text(json.dumps(run))
    runs = kpf.load_run_jsons()
    assert len(runs) == 2  # both files ARE loaded — the dedup happens at evidence resolution

    evidence = kpf._run_evidence(runs)
    assert len(evidence) == 1  # collapsed to one distinct artifact

    by = {
        json.loads(r.text)["predicate"]: json.loads(r.text)["value"]
        for r in kpf.derive_facts("workflow_facts/v1", REPO, REVISION, NOW)
    }
    assert by["workflow_phases_completed"] == "1"  # not 2


def test_vector7_duplicate_finalized_facts_are_deduped_by_workflow_facts_v1_directly():
    """Defense-in-depth, exercised at the reducer level directly (no producer/disk involved): even
    if duplicate facts somehow reached ``workflow_facts_v1`` (bypassing the producer's own dedup),
    it must not double-count them — proven here by feeding the SAME finalized fact list twice."""
    run = _run()
    inp = _inp(run)
    lower = attempt_facts_v1(inp) + job_facts_v1(inp)
    finalized = [fi.finalize_fact(f, fi.build_fact_record(f)) for f in lower]
    doubled = finalized + finalized
    wf_inp = ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workflow",
        scope_id="",
        repository_id=REPO,
        evidence=(),
        facts=tuple(doubled),
        now=NOW,
        source_revision=REVISION,
    )
    by = {f.predicate: f.value for f in workflow_facts_v1(wf_inp)}
    assert by["workflow_phases_completed"] == "1"


def test_vector7_out_of_order_evidence_still_resolves_to_the_most_recent_value(tmp_path: Path):
    """FINDING (fixed): ``derive_fact_records`` used to trust "last in the given list wins", so a
    caller (or a future producer bug) handing facts newest-first would let an OLDER observation
    become the registered "current" value. Fixed by sorting on ``observed_at`` inside
    ``derive_fact_records`` itself — the guarantee no longer depends on callers behaving."""
    run_a = _run(ended_at="2026-08-20T00:00:00+00:00", total_cost_usd=1.5)  # older
    run_b = _run(ended_at="2026-08-22T00:00:00+00:00", total_cost_usd=9.0)  # newer
    # Evidence handed NEWEST-FIRST — the adversarial ordering.
    inp = ReducerInput(
        scope_path=f"org:{REPO}",
        scope_type="workload",
        scope_id="",
        repository_id=REPO,
        evidence=_evidence(run_b, run_a),
        facts=(),
        now=NOW,
        source_revision=REVISION,
    )
    cost_facts = [f for f in job_facts_v1(inp) if f.predicate == "job_accumulated_cost_usd"]
    assert cost_facts[0].value == "9.0"  # confirms the input really is out of order

    records = fi.derive_fact_records(cost_facts, registry_path=tmp_path / "r.jsonl")
    current = records[-1]  # the final registered head after processing the whole batch
    # The NEWER value wins, not merely the one given last in the input list.
    assert json.loads(current.text)["value"] == "9.0"


# ── Vector 8: a stale/superseded lower fact ──────────────────────
# Primary coverage: the existing
# `test_staleness_cascade_superseding_an_l1_fact_makes_the_l3_fact_stale`
# (test_context_plane_reducers.py) and r3's `test_staleness_cascade_from_real_producer_evidence`
# (sourced from real disk evidence). Adversarial re-check: supersede a JOB-level (not attempt-level)
# lower fact and confirm the cascade still reaches the workflow fact — the existing tests only
# exercised an attempt-level (`phase_status`) citation.


def test_vector8_superseding_a_job_level_lower_fact_makes_the_workflow_fact_stale():
    run = _run()
    workflow_facts, finalized = _ladder(run)
    l3 = fi.finalize_fact(workflow_facts[0], fi.build_fact_record(workflow_facts[0]))
    l2 = next(f for f in finalized if f.predicate == "job_accumulated_cost_usd")
    assert l2.fact_id in l3.evidence_ids  # the job-level citation

    from agentic_dynamics.control.facts import fact_state

    rows = {eid: {"lifecycle_state": "current"} for eid in l3.evidence_ids}
    assert fact_state(l3, now=NOW, resolve=rows.get) == "current"
    rows[l2.fact_id] = {"lifecycle_state": "superseded"}
    assert fact_state(l3, now=NOW, resolve=rows.get) == "stale"


# ── Vector 9: tampered evidence id / digest ──────────────────────
# r1 covers a dangling evidence_id (verify_chain refuses it). Completing the contrast: a
# DIGEST that no longer matches its own evidence_ids (the evidence_ids resolve fine, but the
# digest was computed for a DIFFERENT set) must also be refused — this is what actually detects a
# hand-edited/corrupted artifact per `recompute_inputs_digest`'s docstring.


def test_vector9_verify_chain_flags_a_tampered_inputs_digest():
    run = _run()
    inp = _inp(run)
    fact = next(f for f in attempt_facts_v1(inp) if f.predicate == "attempt_cost_usd")
    finalized = fi.finalize_fact(fact, fi.build_fact_record(fact))
    assert verify_chain(finalized, REDUCERS) == []  # sanity: untampered fact is clean

    # Tamper: swap in a different (still non-empty, still resolvable-shaped) evidence_id WITHOUT
    # recomputing inputs_digest — simulates a hand-edited artifact or a partial/corrupted write.
    tampered = replace(finalized, evidence_ids=("workflow_run:" + "0" * 64,))
    errors = verify_chain(tampered, REDUCERS)
    assert any("inputs_digest mismatch" in e for e in errors)

    # The un-tampered digest recomputed over the TAMPERED evidence_ids would of course match —
    # confirming the check is genuinely comparing against the ORIGINAL stored digest, not
    # silently re-deriving and re-validating a moving target.
    assert recompute_inputs_digest(tampered) != tampered.inputs_digest


def test_vector9_verify_chain_flags_a_dangling_evidence_id_with_a_real_resolver():
    """Re-verified here with an ACTUAL evidence-backed resolver (kb_produce_facts.evidence_resolver
    over real ReducerInput.evidence), not a hand-built dict — closing the gap between "the resolver
    contract is correct in principle" (r1) and "the real resolver genuinely refuses a forged id"."""
    kpf = _load_kb_produce_facts()
    run = _run()
    inp = _inp(run)
    fact = next(f for f in attempt_facts_v1(inp) if f.predicate == "attempt_cost_usd")
    finalized = fi.finalize_fact(fact, fi.build_fact_record(fact))
    resolve = kpf.evidence_resolver(inp.evidence)
    assert verify_chain(finalized, REDUCERS, resolve=resolve) == []  # the real evidence resolves

    forged = replace(finalized, evidence_ids=("workflow_run:" + "f" * 64,))
    forged = replace(forged, inputs_digest=recompute_inputs_digest(forged))  # keep digest honest
    errors = verify_chain(forged, REDUCERS, resolve=resolve)
    assert any("does not resolve" in e for e in errors)


# ── Vector 10: generated-surface or dependency-direction violation ──
# The full guard suites (test_dependency_direction.py, test_script_classification.py,
# test_cli_resolution.py, and the generated-surface consistency checks) are run separately as
# part of the r4 command log — see the commit message. Spot-checked here: no I4 module is
# imported anywhere the r1-r4 repair touched, and no new script/CLI surface was added.


def test_vector10_no_i4_imports_in_the_repaired_modules():
    touched = [
        PROJECT_ROOT / "src" / "agentic_dynamics" / "control" / "reducers" / "attempt_facts.py",
        PROJECT_ROOT / "src" / "agentic_dynamics" / "control" / "reducers" / "job_facts.py",
        PROJECT_ROOT / "src" / "agentic_dynamics" / "control" / "reducers" / "workflow_facts.py",
        PROJECT_ROOT / "src" / "agentic_dynamics" / "control" / "reducers" / "_common.py",
        PROJECT_ROOT / "src" / "agentic_dynamics" / "control" / "fact_ingestion.py",
        PROJECT_ROOT / "scripts" / "kb_produce_facts.py",
    ]
    forbidden = ("context_compiler", "control.rules", "control.validator", "control.decisions")
    for path in touched:
        text = path.read_text()
        for name in forbidden:
            assert name not in text, f"{path} references I4 surface {name!r}"
