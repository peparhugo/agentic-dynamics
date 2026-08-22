"""CAP I3 — the ``workflow_facts/v1`` reducer (the L3 aggregation rung).

This is the first reducer that consumes *facts*, not raw evidence. ``attempt_facts/v1`` and
``job_facts/v1`` mint the L1/L2 facts over the typed run JSONs (I2); this reducer sits above them
and rolls the per-phase / per-run facts up into L3 workflow-scope facts — the phase-completion
counts, the workflow status, a health reading, and the projected budget overrun. It is the
"abstract" rung the design's loop calls for (§2 stage 3), and the reason the ladder matters:
workflow facts cite the L2/L1 ``fact_id``s they consumed, so superseding a lower fact makes the
workflow fact resolve ``stale`` on the next read (the §9 I3 gate, via ``facts.fact_state``).

Scope (§10.1, reconciled with the I2 task's "job:<workflow-cell>"): the workflow-cell
``wf_<spec>_<model>`` is the shared address. I2 scoped job facts at ``scope_type="job"`` with that
id; this reducer emits at ``scope_type="workflow"`` with the SAME id — the workflow scope is the
workflow-level view of the cell, one rung up the abstraction ladder (``job`` → ``workflow``).

Aggregation (§10.2.3): a workflow fact exposes the value, the count (``len(evidence_ids)``), and
the ``evidence_ids`` — the child ``fact_id``s it consumed — but never child identities (subject ids
or scope paths) in its payload. ``aggregates_from`` is declared on the predicates in
``FACT_PREDICATES``.

Determinism (the §4.2 contract, verbatim): total order over inputs (children are sorted by
``fact_id`` before being folded into ``evidence_ids`` and the digest), no wall-clock read
(``inp.now`` only), and a total function — every branch emits the four always-known facts (a
cell with no phases yields the empty state, not silence).

Epistemics: every workflow fact is ``derived`` (DERIVED/[C]) — computed by this deterministic
reducer from lower-level facts. ``fact_id`` is emitted empty and finalized at persistence.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from agentic_dynamics.control.facts import (
    EPISTEMIC_MAP,
    FACT_PREDICATES,
    CanonicalFact,
    ReducerInput,
    ReducerSpec,
    compute_fact_entity_id,
    recompute_inputs_digest,
)
from agentic_dynamics.control.reducers._common import cell_id as _cell_id_str
from agentic_dynamics.control.reducers._common import encode_value

# ── Reducer declaration ─────────────────────────────────────────

VERSION = "workflow_facts/v1"

#: The five workflow predicates the reducer emits. Every name exists in FACT_PREDICATES.
_PRODUCES = (
    "workflow_phases_completed",
    "workflow_phases_remaining",
    "workflow_status",
    "workflow_health",
    "projected_budget_overrun",
)

WORKFLOW_FACTS_V1 = ReducerSpec(
    name="workflow_facts",
    version=VERSION,
    level="workflow",
    scope_type="workflow",
    # Lower-level fact predicates this rung aggregates (the reduction ladder, §10.2.3):
    # phase completion from attempt facts, job state from job facts, the ceiling from policy
    # facts, and spec_status for the "where declared" case.
    consumes=(
        "phase_status",
        "job_status",
        "job_n_phases",
        "job_accumulated_cost_usd",
        "current_commit",
        "max_spend_usd",
        "spec_status",
    ),
    produces=_PRODUCES,
    determinism="pure",
)

#: A workflow fact is computed by a deterministic reducer — DERIVED (DERIVED/[C]).
_EPISTEMIC_STATUS = "derived"
_AUTHORITY, _EVIDENCE_CLASS = EPISTEMIC_MAP[_EPISTEMIC_STATUS]


# ── Scope-path parsing (the reducer's only grouping primitive) ──


def _segments(scope_path: str) -> dict[str, str]:
    """Parse ``org:r/workload:s/job:c/attempt:p`` into ``{scope_type: id}``."""
    out: dict[str, str] = {}
    for seg in scope_path.split("/"):
        if ":" in seg:
            key, _, value = seg.partition(":")
            out[key] = value
    return out


# ── Fact construction ───────────────────────────────────────────


def _fact(
    workload: str,
    cell: str,
    inp: ReducerInput,
    predicate: str,
    value: str,
    evidence_ids: tuple[str, ...],
) -> CanonicalFact:
    """Build one workflow-scoped fact for ``predicate`` (design §10's scope hierarchy)."""
    spec = FACT_PREDICATES[predicate]
    fact = CanonicalFact(
        fact_entity_id=compute_fact_entity_id(
            repository_id=inp.repository_id,
            scope_type="workflow",
            scope_id=cell,
            predicate=predicate,
            subject_type="workflow",
            subject_id=cell,
        ),
        fact_id="",  # finalized at persistence — the record's knowledge_id IS the fact_id
        subject_type="workflow",
        subject_id=cell,
        predicate=predicate,
        value=value,
        value_type=spec.value_type,
        unit=spec.unit,
        scope_type="workflow",
        scope_id=cell,
        scope_path=f"org:{inp.repository_id}/workload:{workload}/workflow:{cell}",
        abstraction_level=spec.abstraction_level,
        epistemic_status=_EPISTEMIC_STATUS,
        authority=_AUTHORITY,
        evidence_class=_EVIDENCE_CLASS,
        observed_at=inp.now,
        valid_from=inp.now,
        valid_to=None,
        expires_at=None,
        reducer="workflow_facts",
        reducer_version=VERSION,
        evidence_ids=evidence_ids,  # the child fact_ids — the staleness cascade's backbone
        inputs_digest="",  # back-filled below from evidence_ids + reducer_version
        supersedes=None,  # the producer links a predecessor via the registry, not the reducer
        source_revision=inp.source_revision,
        repository_id=inp.repository_id,
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


# ── Per-cell derivation ─────────────────────────────────────────


def _facts_for_cell(
    workload: str,
    cell: str,
    cell_facts: list[CanonicalFact],
    policies: dict[str, CanonicalFact],
    inp: ReducerInput,
) -> list[CanonicalFact]:
    """Emit the five workflow facts for one cell, honouring the aggregation rules."""
    phase_status = [f for f in cell_facts if f.predicate == "phase_status"]
    jobs = {f.predicate: f for f in cell_facts if f.scope_type == "job"}
    max_spend = policies.get("max_spend_usd")

    # evidence_ids = the FULL input set (§3.1) the reducer consumed for this cell — every lower
    # fact (job + attempt) plus the workload ceiling when one exists — sorted for a total order
    # (§4.2). Empty ids are dropped (a child that was never finalized has no citable identity).
    inputs = list(cell_facts)
    if max_spend is not None:
        inputs.append(max_spend)
    evidence_ids = tuple(sorted(f.fact_id for f in inputs if f.fact_id))

    completed = sum(1 for f in phase_status if f.value == "ok")
    failed = any(f.value == "failed" for f in phase_status)

    total_fact = jobs.get("job_n_phases")
    total = int(total_fact.value) if total_fact else len(phase_status)
    remaining = max(0, total - completed)

    # workflow_status: failed dominates; then completed; then in_progress; then unknown.
    if failed:
        status = "failed"
    elif completed > 0 and remaining == 0:
        status = "completed"
    elif phase_status or jobs:
        status = "in_progress"
    else:
        status = "unknown"

    # Spend-against-declared-ceiling (§4.2's substitution for the unproducible deadline_slack).
    cost_fact = jobs.get("job_accumulated_cost_usd")
    overrun = 0.0
    if cost_fact is not None and max_spend is not None:
        overrun = max(0.0, float(cost_fact.value) - float(max_spend.value))

    if overrun > 0.0 or failed:
        health = "at_risk"
    elif status in ("in_progress", "unknown"):
        health = "degraded"
    else:
        health = "healthy"

    facts = [
        _fact(
            workload,
            cell,
            inp,
            "workflow_phases_completed",
            encode_value(completed, "int"),
            evidence_ids,
        ),
        _fact(
            workload,
            cell,
            inp,
            "workflow_phases_remaining",
            encode_value(remaining, "int"),
            evidence_ids,
        ),
        _fact(workload, cell, inp, "workflow_status", encode_value(status, "enum"), evidence_ids),
        _fact(workload, cell, inp, "workflow_health", encode_value(health, "enum"), evidence_ids),
    ]
    # projected_budget_overrun is emitted ONLY when a ceiling exists (§5: "when inputs exist").
    if max_spend is not None:
        facts.append(
            _fact(
                workload,
                cell,
                inp,
                "projected_budget_overrun",
                encode_value(overrun, "usd"),
                evidence_ids,
            )
        )
    return facts


# ── The reducer (pure) ──────────────────────────────────────────


def workflow_facts_v1(inp: ReducerInput) -> list[CanonicalFact]:
    """Emit workflow facts for every cell represented in ``inp.facts``.

    ``inp.facts`` carries the FINALIZED lower-level facts (attempt/job/policy — the producer runs
    the lower reducers and attaches ``fact_id`` first, so the aggregation can cite them). The
    reducer groups them by cell (via the ``job``/``workflow`` scope-path segment), joins the
    workload's policy ceiling, and emits the five workflow facts per cell. Pure, total, and
    deterministic: the same ``ReducerInput`` yields byte-identical facts in cell-sorted order.
    """
    by_cell: dict[str, dict[str, Any]] = {}
    policy_by_workload: dict[str, dict[str, CanonicalFact]] = {}

    for fact in inp.facts:
        seg = _segments(fact.scope_path)
        if fact.scope_type == "workload" and fact.predicate in ("max_spend_usd", "spec_status"):
            policy_by_workload.setdefault(fact.scope_id, {})[fact.predicate] = fact
            continue
        cell = seg.get("job") or seg.get("workflow")
        if not cell:
            continue  # a job/attempt/workflow fact must name its cell; anything else is skipped
        bucket = by_cell.setdefault(cell, {"workload": seg.get("workload", ""), "facts": []})
        bucket["facts"].append(fact)

    facts: list[CanonicalFact] = []
    for cell in sorted(by_cell):
        bucket = by_cell[cell]
        workload = str(bucket["workload"])
        policies = policy_by_workload.get(workload, {})
        facts.extend(_facts_for_cell(workload, cell, bucket["facts"], policies, inp))
    return facts


# re-export the cell-id helper under the reducer's namespace (used by the producer + tests).
cell_id = _cell_id_str
