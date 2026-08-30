"""CAP fact-auto-emit adversarial verification (``f3_adversarial_verify``, design:
``docs/architecture/current/cap_fact_auto_emit_design.md``).

ROLE: adversarial verifier. This file exists to try to FALSIFY the fact-auto-emit hook's five
hard-rule guarantees (idempotence, failure-tolerance, flag precedence, no reducer/transport
changes) against the six attacks the phase spec names: double-emit from a copied artifact;
concurrent runs of one cell emitting interleaved; partial registry writes; emit of a run whose
phases changed after finalize; flag precedence confusion; a regression in ``fact_ingestion``'s
in-batch chaining or dedup guard.

**One genuine defect was found and fixed here**: out-of-order run COMPLETION (not merely a
write race) silently regressed a cell's registered "current" job/workflow state — reproduced
below in ``test_attack2a_...`` before the fix (``kb_produce_facts._registered_observed_at`` +
the guard in ``derive_run_facts``) closed it. See that test's docstring and the design doc's log
for the full mechanism. The other five attacks were already closed by the f1/f2 design +
implementation and are re-verified here from an adversarial angle (a different construction than
``tests/test_fact_auto_emit.py``'s happy-path suite used), or are accepted limitations with a
documented reason (module-level comments at each such test) — mirroring
``tests/test_cap_i0_i3_adversarial.py``'s own convention for this repo.

No Redis/network.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

from agentic_dynamics.control import fact_ingestion as fi
from agentic_dynamics.control.facts import fact_state
from agentic_dynamics.experiment.experiment_spec import ExperimentSpec, StopSpec, Workflow
from agentic_dynamics.runtime.workflow_runner import PhaseResult, WorkflowRunResult

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO = "self-test-cell"
REVISION = "0123456789abcdef0123456789abcdef01234567"


# ── Module loaders + shared fixtures (mirrors test_fact_auto_emit.py's, distinct module names
#    so importlib doesn't collide with that file's own hermetic instances) ──


def _load_module(rel_path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / rel_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def kpf(tmp_path, monkeypatch):
    module = _load_module("scripts/kb_produce_facts.py", "kb_produce_facts_under_test_fae_adv")
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "REGISTRY_INDEX_PATH", tmp_path / "registry_index.jsonl")
    return module


def _spec(name: str = "demo_spec", *, budget_usd: float = 100.0, max_attempts: int = 3) -> ExperimentSpec:
    return ExperimentSpec(
        name=name,
        question="does the hook survive an attack",
        version="1.0",
        workflow=Workflow(kind="agent_task", params={"model_pool": ["deepseek/deepseek-v4-pro"]}),
        factors=[],
        design="factorial",
        stop=StopSpec(budget_usd=budget_usd, max_attempts=max_attempts),
    )


def _result(
    spec_name: str = "demo_spec",
    *,
    ok_phase: bool = True,
    git_sha: str = "abc123",
    cost_usd: float = 1.5,
    started_at: str = "2026-08-24T00:00:00+00:00",
    ended_at: str = "2026-08-24T00:00:00+00:00",
) -> WorkflowRunResult:
    return WorkflowRunResult(
        spec_name=spec_name,
        model="deepseek/deepseek-v4-pro",
        workdir="/tmp/x",
        goal="build it",
        git_sha=git_sha,
        started_at=started_at,
        ended_at=ended_at,
        phases=[
            PhaseResult(
                phase="implement",
                kind="agent",
                status="ok" if ok_phase else "failed",
                model="deepseek/deepseek-v4-pro",
                commit_hash="deadbeef",
                cost_usd=cost_usd,
            ),
        ],
    )


def _registration_line(record) -> dict:
    """The line ``kb_worker.py``'s ``kb-registry-v1`` handler would append for one record —
    field-for-field identical to the real handler (``scripts/kb_worker.py:277-289``), including
    ``observed_at`` (load-bearing for the out-of-order-completion guard under test below)."""
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
    lines = "".join(json.dumps(_registration_line(r)) + "\n" for r in records)
    with registry_path.open("a") as f:
        f.write(lines)


def _by_predicate(records) -> dict[str, dict]:
    return {json.loads(r.text)["predicate"]: json.loads(r.text) for r in records}


def _by_predicate_records(records) -> dict[str, object]:
    return {json.loads(r.text)["predicate"]: r for r in records}


# ── Attack 1: double-emit from a copied artifact ──────────────────────────────────────────
#
# tests/test_fact_auto_emit.py's own no-op test reuses the SAME `result` object across both
# derive_run_facts calls. Adversarial re-check: two INDEPENDENTLY CONSTRUCTED objects with
# identical content (never `result_a is result_b`), proving idempotence is content-addressed
# (run_artifact_id -> fact_fingerprint), not merely stable because Python handed back the same
# object — the actual shape of a "copied artifact" (e.g. a run JSON re-read from disk, or a
# retried invocation building its own WorkflowRunResult from the same ledger row).


def test_attack1_double_emit_from_an_independently_constructed_copy(kpf, tmp_path):
    spec = _spec()
    result_a = _result(cost_usd=3.0, git_sha="c0ffee")
    result_b = _result(cost_usd=3.0, git_sha="c0ffee")  # a fresh object, same content
    assert result_a is not result_b

    round_a = kpf.derive_run_facts(result_a, spec, repository_id=REPO, revision=REVISION, now="2026-08-24T00:00:01+00:00")
    assert round_a
    _persist(kpf.REGISTRY_INDEX_PATH, *round_a)

    # The "copy" (independently built, byte-identical content) arrives later and re-derives.
    round_b = kpf.derive_run_facts(result_b, spec, repository_id=REPO, revision=REVISION, now="2026-08-24T00:00:02+00:00")
    assert round_b == [], "a content-identical copy must be a pure no-op, not a second registration"


# ── Attack 2a: concurrent runs of one cell — OUT-OF-ORDER COMPLETION (the defect found+fixed) ──
#
# This is the sharper, fully-deterministic form of "concurrent runs emitting interleaved": no
# true concurrency or write race is even needed. `attempt_facts_v1`/`job_facts_v1` key
# `observed_at` off the RUN's own `ended_at`/`started_at` (facts.py: "when the underlying
# evidence was observed, NOT when reduced") — but the auto-emit hook calls
# `fact_ingestion.derive_fact_records` ONCE PER RUN, from separate process invocations, each of
# which only ever compares CONTENT against the currently-registered head, never RECENCY. Before
# the fix, a run that STARTED earlier but FINISHED later (a slow worker, a delayed retry, or two
# workers racing to different completion times) silently overwrote a newer run's correct
# "current" state with stale values the moment its hook fired.


def test_attack2a_out_of_order_completion_previously_regressed_current_state_now_guarded(kpf, tmp_path):
    spec = _spec()

    # Run T2: started later, finishes FIRST (fast worker) — the TRUE latest observation.
    run_t2 = _result(cost_usd=9.0, git_sha="fedcba", ok_phase=True,
                      started_at="2026-08-24T00:10:00+00:00", ended_at="2026-08-24T00:20:00+00:00")
    recs_t2 = kpf.derive_run_facts(run_t2, spec, repository_id=REPO, revision=REVISION, now="2026-08-24T00:20:05+00:00")
    assert recs_t2
    _persist(kpf.REGISTRY_INDEX_PATH, *recs_t2)
    by_t2 = _by_predicate(recs_t2)
    assert by_t2["job_status"]["value"] == "ok"
    assert by_t2["job_accumulated_cost_usd"]["value"] == "9.0"

    # Run T1: STARTED earlier, finishes SECOND (slow worker / delayed retry) — a STALE
    # observation processed after T2 is already registered.
    run_t1 = _result(cost_usd=1.0, git_sha="abc123", ok_phase=False,
                      started_at="2026-08-24T00:00:00+00:00", ended_at="2026-08-24T00:05:00+00:00")
    recs_t1 = kpf.derive_run_facts(run_t1, spec, repository_id=REPO, revision=REVISION, now="2026-08-24T00:25:00+00:00")

    # THE FIX: the stale run derives NOTHING — it must never be allowed to set the cell's
    # "current" state, even though its own hook invocation happened chronologically LAST.
    assert recs_t1 == []

    # Sanity: a GENUINELY newer run (later `ended_at` than T2) must still supersede normally —
    # the guard must not become "never updates again".
    run_t3 = _result(cost_usd=20.0, git_sha="aaaaaa", ok_phase=True,
                      started_at="2026-08-24T00:30:00+00:00", ended_at="2026-08-24T00:40:00+00:00")
    recs_t3 = kpf.derive_run_facts(run_t3, spec, repository_id=REPO, revision=REVISION, now="2026-08-24T00:40:05+00:00")
    by_t3 = _by_predicate_records(recs_t3)
    assert by_t3["job_accumulated_cost_usd"].supersedes == _by_predicate_records(recs_t2)["job_accumulated_cost_usd"].knowledge_id
    assert json.loads(by_t3["job_accumulated_cost_usd"].text)["value"] == "20.0"


def test_attack2a_guard_only_fires_when_a_head_is_already_registered(kpf, tmp_path):
    """The guard must not suppress a cell's FIRST-EVER emission — there is no head to be stale
    against yet, however "old" the run's own timestamp looks in isolation."""
    spec = _spec()
    old_run = _result(cost_usd=1.0, started_at="2020-01-01T00:00:00+00:00", ended_at="2020-01-01T00:00:00+00:00")
    records = kpf.derive_run_facts(old_run, spec, repository_id=REPO, revision=REVISION, now="2026-08-24T00:00:00+00:00")
    assert records  # first version of every entity — nothing registered yet to be "stale" against


# ── Attack 2b: concurrent runs of one cell — REGISTRY-WRITE RACE (accepted limitation) ──────
#
# ACCEPTED LIMITATION (reason-bearing, matching test_cap_i0_i3_adversarial.py's vector-3
# convention): two hook invocations for the SAME cell whose runs are GENUINELY simultaneous
# (identical `ended_at`, i.e. neither is "older" — 2a's guard correctly does not apply) and whose
# `derive_fact_records` calls BOTH read the registry before EITHER has been durably registered
# (the registry line is appended by the async `kb-registry-v1` stream consumer, not synchronously
# by `emit_records` — knowledge_stream.py's own docstring: consumers ack only after their own
# destination confirms) will both see the SAME stale head and both decide "supersedes X",
# producing two unlinked "current" rows for one `fact_entity_id`. This is NOT a new risk this
# hook introduces — `kb_produce_facts.py --reducer job_facts/v1`'s own batch `main()` has the
# identical race across two concurrently-run processes today, undocumented and untested before
# this file. Verified below: the race does NOT corrupt data or raise — it converges to the
# `conflicted` lifecycle state `facts.fact_state` was built to represent (design §9/§10's
# explicitly-flagged open item, confirmed here as outcome (b): "resolved as conflicted... rather
# than data loss"). A durable fix (e.g. an optimistic registry-write CAS) is out of scope for a
# hook-local, no-new-transport phase (hard rule 5) and is recorded here as follow-up work, not
# silently assumed safe.


def _job_cost_fact(kpf, spec, run, repository_id, revision, now):
    """Re-derive the raw (unfinalized) ``CanonicalFact`` for ``job_accumulated_cost_usd`` off the
    same run, so the test below can hand ``fact_state`` a real ``CanonicalFact`` — ``finalize_fact``
    needs the ORIGINAL fact object, not just its already-persisted ``KnowledgeRecord``."""
    from agentic_dynamics.control.facts import ReducerInput
    from agentic_dynamics.control.reducers import job_facts_v1

    run_dict = run.to_dict()
    inp = ReducerInput(
        scope_path=f"org:{repository_id}/workload:{spec.name}",
        scope_type="workload",
        scope_id="",
        repository_id=repository_id,
        evidence=kpf._run_evidence([run_dict]),
        facts=(),
        now=now,
        source_revision=revision,
    )
    return next(f for f in job_facts_v1(inp) if f.predicate == "job_accumulated_cost_usd")


def test_attack2b_simultaneous_racing_derivations_converge_to_conflicted_not_corruption(kpf, tmp_path):
    spec = _spec()

    baseline = _result(cost_usd=1.0, git_sha="base00",
                        started_at="2026-08-24T00:00:00+00:00", ended_at="2026-08-24T00:00:00+00:00")
    recs_baseline = kpf.derive_run_facts(baseline, spec, repository_id=REPO, revision=REVISION, now="2026-08-24T00:00:01+00:00")
    _persist(kpf.REGISTRY_INDEX_PATH, *recs_baseline)

    # Two processes, A and B, both finish at the SAME instant (no out-of-order-completion signal
    # for 2a's guard to catch) and both call derive_run_facts BEFORE either's registry line lands
    # — simulated here by deriving both against the identical, still-baseline-only registry file.
    same_instant = "2026-08-24T00:10:00+00:00"
    run_a = _result(cost_usd=5.0, git_sha="aaaaaa", started_at=same_instant, ended_at=same_instant)
    run_b = _result(cost_usd=7.0, git_sha="bbbbbb", started_at=same_instant, ended_at=same_instant)

    recs_a = kpf.derive_run_facts(run_a, spec, repository_id=REPO, revision=REVISION, now="2026-08-24T00:10:01+00:00")
    recs_b = kpf.derive_run_facts(run_b, spec, repository_id=REPO, revision=REVISION, now="2026-08-24T00:10:02+00:00")
    assert recs_a and recs_b  # neither is dropped by the 2a guard — both are genuinely "newer"

    cost_a = _by_predicate_records(recs_a)["job_accumulated_cost_usd"]
    cost_b = _by_predicate_records(recs_b)["job_accumulated_cost_usd"]
    baseline_cost = _by_predicate_records(recs_baseline)["job_accumulated_cost_usd"]

    # Both raced against the SAME (baseline) head — neither knows about the other.
    assert cost_a.supersedes == baseline_cost.knowledge_id
    assert cost_b.supersedes == baseline_cost.knowledge_id
    assert cost_a.knowledge_id != cost_b.knowledge_id  # two DISTINCT versions, not a collision
    assert cost_a.entity_id == cost_b.entity_id == baseline_cost.entity_id  # same logical slot

    # No exception, no data loss: persisting both (as the async registry consumer eventually
    # would, processing each event independently) round-trips both records safely.
    _persist(kpf.REGISTRY_INDEX_PATH, cost_a)
    _persist(kpf.REGISTRY_INDEX_PATH, cost_b)

    rows = {
        cost_a.knowledge_id: {"lifecycle_state": "current"},
        cost_b.knowledge_id: {"lifecycle_state": "current"},
    }
    current_rows = (
        {"knowledge_id": cost_a.knowledge_id, "lifecycle_state": "current"},
        {"knowledge_id": cost_b.knowledge_id, "lifecycle_state": "current"},
    )
    raw_fact_a = _job_cost_fact(kpf, spec, run_a, REPO, REVISION, "2026-08-24T00:10:01+00:00")
    fact_a = fi.finalize_fact(raw_fact_a, cost_a)
    state = fact_state(
        fact_a,
        now="2026-08-24T00:11:00+00:00",
        resolve=lambda eid: rows.get(eid),
        current_versions=lambda entity_id: current_rows if entity_id == fact_a.fact_entity_id else (),
    )
    assert state == "conflicted"  # the race is VISIBLE and classified, never silent data loss


# ── Attack 3: partial registry writes ──────────────────────────────────────────────────────


def test_attack3_truncated_last_line_degrades_to_no_head_not_a_crash(kpf, tmp_path):
    """Simulates a crash mid-write: the registry file's LAST line is a truncated JSON fragment
    (as a process killed mid-`f.write()` would leave it). `registry_head`/the new
    `_registered_observed_at` helper must skip it, not raise — and must not lose an earlier,
    well-formed line for the SAME entity."""
    spec = _spec()
    result = _result(cost_usd=1.0)
    records = kpf.derive_run_facts(result, spec, repository_id=REPO, revision=REVISION, now="2026-08-24T00:00:01+00:00")
    _persist(kpf.REGISTRY_INDEX_PATH, *records)

    # Append a truncated fragment — exactly what a crash mid-append would leave on disk.
    with kpf.REGISTRY_INDEX_PATH.open("a") as f:
        f.write('{"knowledge_id": "deadbe', )  # no closing brace, no trailing newline

    cost_record = _by_predicate_records(records)["job_accumulated_cost_usd"]
    observed = kpf._registered_observed_at(cost_record.entity_id, registry_path=kpf.REGISTRY_INDEX_PATH)
    assert observed == cost_record.observed_at  # the earlier well-formed line still resolves fine

    # derive_run_facts over a NEW, genuinely later run must still work — no exception, correct
    # supersession off the well-formed line, truncated fragment silently ignored.
    newer = _result(cost_usd=8.0, git_sha="fedcba",
                     started_at="2026-08-24T00:10:00+00:00", ended_at="2026-08-24T00:10:00+00:00")
    round_2 = kpf.derive_run_facts(newer, spec, repository_id=REPO, revision=REVISION, now="2026-08-24T00:10:01+00:00")
    by2 = _by_predicate_records(round_2)
    assert json.loads(by2["job_accumulated_cost_usd"].text)["value"] == "8.0"


def test_attack3_missing_registry_file_and_missing_parent_directory_is_a_first_version_not_a_crash(kpf, tmp_path):
    """`REGISTRY_INDEX_PATH` pointing at a path whose PARENT DIRECTORY doesn't exist yet (a
    fresh checkout / first-ever run for this repo) must degrade to "no head", never raise."""
    spec = _spec()
    kpf.REGISTRY_INDEX_PATH = tmp_path / "nonexistent_dir" / "registry_index.jsonl"
    assert not kpf.REGISTRY_INDEX_PATH.parent.exists()

    records = kpf.derive_run_facts(_result(), spec, repository_id=REPO, revision=REVISION, now="2026-08-24T00:00:00+00:00")
    assert records  # first version — no crash despite a wholly absent registry tree


# ── Attack 4: emit of a run whose phases changed after finalize ───────────────────────────
#
# ACCEPTED as verified-safe-by-construction, with a STRUCTURAL regression guard rather than a
# behavioral test: `_emit_workflow_facts(spec, args, result)` is called synchronously, in the
# SAME process, on the SAME `result` object `run_workflow()` just returned — there is no
# intervening code that could mutate `result.phases` between "the run finished" and "the hook
# read it" (unlike the manual batch job, which re-reads whatever is on disk at scan time and
# COULD race a concurrent writer). This is a claim about the CALL SITE'S SHAPE, not about
# `derive_run_facts`'s logic, so the strongest test available is a source-adjacency check that
# fails loudly if a future change inserts phase-mutating code between the two calls.


def test_attack4_no_mutation_window_between_run_completion_and_fact_emission():
    source = (PROJECT_ROOT / "scripts" / "run_workflow.py").read_text()
    anchor = (
        "    _refresh_index(spec.name)\n"
        "    _emit_spec_record(spec.name, revision=result.git_sha)\n"
        "    if _fact_auto_emit_enabled(args):\n"
        "        _emit_workflow_facts(spec, args, result)\n"
    )
    assert anchor in source, (
        "the fact-emit hook must fire immediately after the ledger/spec-record writes with no "
        "intervening code that could mutate `result` — re-verify Attack 4's 'no mutation window' "
        "claim in the design doc if this block changed"
    )


# ── Attack 5: flag precedence confusion — adversarial edge cases ──────────────────────────
#
# tests/test_fact_auto_emit.py already covers the documented cases ("0" disables; "1"/"true"/
# unset stay on; CLI beats env). Adversarial extension: values an implementer might ACCIDENTALLY
# treat as falsy/disabling if they reached for `bool(...)`/`int(...)` instead of the exact
# string-equality check the design mandates.


def test_attack5_only_the_exact_literal_zero_disables(kpf):
    rw = _load_module("scripts/run_workflow.py", "run_workflow_under_test_fae_adv")
    rw.kb_produce_facts = kpf

    class _Args:
        no_fact_emit = False

    adversarial_on_values = ["", "0.0", " 0", "0 ", "00", "False", "no", "0x0"]
    for value in adversarial_on_values:
        os.environ[rw.FACT_AUTO_EMIT_ENV] = value
        try:
            assert rw._fact_auto_emit_enabled(_Args()) is True, (
                f"{value!r} must NOT disable the hook — only the exact literal '0' does"
            )
        finally:
            del os.environ[rw.FACT_AUTO_EMIT_ENV]


# ── Attack 6: regression in fact_ingestion's in-batch chaining or dedup guard ──────────────
#
# The hook's NEW code lives entirely in scripts/kb_produce_facts.py (derive_run_facts,
# _registered_observed_at) and scripts/run_workflow.py (_emit_workflow_facts,
# _fact_auto_emit_enabled) — both producer/composition-root scripts, never
# control/fact_ingestion.py or control/reducers/*.py themselves (hard rule 5). The regression
# check is therefore: (a) the shared module's own chaining/dedup behavior, re-exercised from
# this hook's NEW call shape (one derive_run_facts call per run rather than one batch call), and
# (b) the full existing CAP suite staying green — asserted via a live pytest run in the phase
# log, not duplicated here as a third copy of the same assertions.


def test_attack6_in_batch_chaining_still_dedupes_across_the_four_fact_families_in_one_call(kpf, tmp_path):
    """`derive_run_facts` hands FOUR fact families (attempt/job/policy/workflow) to ONE
    `fi.derive_fact_records` call — re-confirms `fact_ingestion.py`'s in-batch `pending_head`
    chaining (unchanged) still dedupes correctly across a MIXED batch, the exact shape this hook
    depends on and the shape most likely to regress silently if a future edit reordered the
    ladder or split the call."""
    spec = _spec()
    result = _result(cost_usd=2.0)
    records = kpf.derive_run_facts(result, spec, repository_id=REPO, revision=REVISION, now="2026-08-24T00:00:00+00:00")
    entity_ids = [r.entity_id for r in records]
    assert len(entity_ids) == len(set(entity_ids)), "one derive_run_facts call must never register two rows for the same entity"
