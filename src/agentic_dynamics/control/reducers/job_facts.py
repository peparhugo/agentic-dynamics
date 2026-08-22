"""CAP I2 — the ``job_facts/v1`` reducer.

Derives per-run (job) facts from the typed workflow run artifact (``WorkflowRunResult`` JSON).
This is the L2 half of I2: where ``attempt_facts/v1`` mints one fact per measured phase field,
``job_facts/v1`` mints one fact per run-level aggregate — the job's current commit, accumulated
cost, overall status, and phase count — at ``job:<cell>`` scope.

Same purity contract as its sibling (design §4.1): no I/O, no RNG; the caller resolves the run
JSONs; the reducer only maps ``run → facts``. ``inp.now`` is a fallback for a run with no
``ended_at``/``started_at``. Every fact is ``observed`` (MEASURED/[M]) — the value was recorded
by the system in the run artifact — and ``fact_id`` is finalized at persistence.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from agentic_dynamics.control.facts import (
    EPISTEMIC_MAP,
    FACT_PREDICATES,
    CanonicalFact,
    EvidenceItem,
    ReducerInput,
    ReducerSpec,
    compute_fact_entity_id,
    recompute_inputs_digest,
)
from agentic_dynamics.control.reducers._common import (
    REVISION_FALLBACK,
    as_dict,
    cell_id,
    encode_value,
)

# ── Reducer declaration ─────────────────────────────────────────

VERSION = "job_facts/v1"

#: The four per-run predicates the reducer emits. Every name exists in FACT_PREDICATES.
_PRODUCES = (
    "current_commit",
    "job_accumulated_cost_usd",
    "job_status",
    "job_n_phases",
)

JOB_FACTS_V1 = ReducerSpec(
    name="job_facts",
    version=VERSION,
    level="job",
    scope_type="job",
    consumes=("workflow_run",),  # the typed run artifact (WorkflowRunResult JSON)
    produces=_PRODUCES,
    determinism="pure",
)

#: Every job fact is a recorded measurement — OBSERVED (MEASURED/[M]).
_EPISTEMIC_STATUS = "observed"
_AUTHORITY, _EVIDENCE_CLASS = EPISTEMIC_MAP[_EPISTEMIC_STATUS]


def _fact(
    run: dict[str, Any],
    inp: ReducerInput,
    predicate: str,
    value: str,
) -> CanonicalFact:
    """Build one job-scoped fact for ``predicate`` (design §10's scope hierarchy)."""
    spec = FACT_PREDICATES[predicate]
    cell = cell_id(str(run.get("spec_name") or ""), str(run.get("model") or ""))
    observed_at = str(run.get("ended_at") or run.get("started_at") or inp.now)
    fact = CanonicalFact(
        fact_entity_id=compute_fact_entity_id(
            repository_id=inp.repository_id,
            scope_type="job",
            scope_id=cell,
            predicate=predicate,
            subject_type="job",
            subject_id=cell,
        ),
        fact_id="",  # finalized at persistence — the record's knowledge_id IS the fact_id
        subject_type="job",
        subject_id=cell,
        predicate=predicate,
        value=value,
        value_type=spec.value_type,
        unit=spec.unit,
        scope_type="job",
        scope_id=cell,
        scope_path=f"org:{inp.repository_id}/workload:{run.get('spec_name')}/job:{cell}",
        abstraction_level=spec.abstraction_level,
        epistemic_status=_EPISTEMIC_STATUS,
        authority=_AUTHORITY,
        evidence_class=_EVIDENCE_CLASS,
        observed_at=observed_at,
        valid_from=observed_at,
        valid_to=None,
        expires_at=None,
        reducer="job_facts",
        reducer_version=VERSION,
        evidence_ids=(),  # consumes the run artifact directly, not knowledge records
        inputs_digest="",  # back-filled below from evidence_ids + reducer_version
        supersedes=None,  # the producer links a predecessor via the registry, not the reducer
        source_revision=str(run.get("git_sha") or REVISION_FALLBACK),
        repository_id=inp.repository_id,
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


def _facts_for_run(run: dict[str, Any], inp: ReducerInput) -> list[CanonicalFact]:
    """Emit the four per-run facts, honouring measured-or-absent semantics."""
    spec_name = str(run.get("spec_name") or "")
    model = str(run.get("model") or "")
    if not spec_name or not model:
        # No spec/model means no cell identity — the run is not addressable, so no facts.
        return []

    facts: list[CanonicalFact] = []
    git_sha = str(run.get("git_sha") or "")
    if git_sha:
        facts.append(_fact(run, inp, "current_commit", encode_value(git_sha, "str")))
    cost = run.get("total_cost_usd")
    if isinstance(cost, (int, float)):
        facts.append(_fact(run, inp, "job_accumulated_cost_usd", encode_value(cost, "usd")))
    # ``ok`` is a bool; ``job_status`` is the enum reading of it ("ok" | "failed").
    facts.append(_fact(run, inp, "job_status", "ok" if run.get("ok") else "failed"))
    phases = run.get("phases") or []
    n_phases = len(phases) if isinstance(phases, list) else 0
    facts.append(_fact(run, inp, "job_n_phases", encode_value(n_phases, "int")))
    return facts


# ── The reducer (pure) ──────────────────────────────────────────


def job_facts_v1(inp: ReducerInput) -> list[CanonicalFact]:
    """Emit per-run job facts for every run JSON in ``inp.evidence``.

    Pure and total: every addressable run (a spec name + model) yields its four facts; an
    unaddressable or non-dict run is skipped, never crashed on. Deterministic: the same
    ``ReducerInput`` yields byte-identical facts in input order.
    """
    facts: list[CanonicalFact] = []
    for item in inp.evidence:
        if not isinstance(item, EvidenceItem):
            continue
        run = as_dict(item.payload)
        if run is not None:
            facts.extend(_facts_for_run(run, inp))
    return facts
