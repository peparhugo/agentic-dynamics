"""CAP I6 — ``ControlValidator``: ``validate_decision()`` implementing checks C1-C10.

Admit or refuse a :class:`~agentic_dynamics.control.decisions.ControlDecision` against the
:class:`~agentic_dynamics.control.context_compiler.ControlContext` it claims to have been made
from (design §8.3). Deterministic, total, and ORDERED — the first failing check short-circuits
the rest, so a refusal names the most basic thing that was wrong rather than an incidental
downstream symptom (design's own framing).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from agentic_dynamics.control.context_compiler import (
    ContractSpec,
    ControlContext,
    FactStore,
    parse_scope_path,
)
from agentic_dynamics.control.decisions import AUTOMATABLE_ACTIONS, ControlDecision
from agentic_dynamics.control.facts import FactRef, verify_chain


@dataclass(frozen=True)
class ValidationResult:
    """The validator's verdict: admitted, or the first check that refused and why."""

    admitted: bool
    check: str  # "C1".."C10", "" when admitted
    reason: str  # "" when admitted


def _parse_iso(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _all_canonical_refs(snapshot: ControlContext) -> tuple[FactRef, ...]:
    """Every citable fact in the snapshot — invariants + the four abstraction-level buckets.
    Deliberately excludes ``.advisory`` (never citable — that IS what check C5 enforces)."""
    return (
        *snapshot.invariants,
        *snapshot.workload,
        *snapshot.workflow,
        *snapshot.job,
        *snapshot.resource,
    )


def _op_holds(actual_raw: str, op: str, expected: Any) -> bool:
    """Evaluate one :class:`~agentic_dynamics.control.decisions.Precondition` op against a
    fresh :class:`FactRef`'s canonical STRING value (design §3.1's encoding)."""
    if op == "is_true":
        return actual_raw == "true"
    if op == "is_false":
        return actual_raw == "false"
    if op == "in":
        return actual_raw in expected
    try:
        actual: Any = float(actual_raw)
        target: Any = float(expected)
    except (TypeError, ValueError):
        actual, target = actual_raw, expected
    if op == "eq":
        return actual == target
    if op == "ne":
        return actual != target
    if op == "lt":
        return actual < target
    if op == "lte":
        return actual <= target
    if op == "gt":
        return actual > target
    if op == "gte":
        return actual >= target
    return False  # an op outside PRECONDITION_OPS can never hold


# ── The ten checks (design §8.3's table, in order) ────────────────


def _c1_snapshot_binding(decision: ControlDecision, snapshot: ControlContext) -> str | None:
    if decision.snapshot_id != snapshot.snapshot_id:
        return (
            f"decision.snapshot_id {decision.snapshot_id!r} does not match the supplied "
            f"snapshot {snapshot.snapshot_id!r}"
        )
    if decision.decision_type != snapshot.decision_type:
        return (
            f"decision.decision_type {decision.decision_type!r} does not match the snapshot's "
            f"{snapshot.decision_type!r}"
        )
    return None


def _c2_snapshot_admissibility(snapshot: ControlContext) -> str | None:
    if not snapshot.admissible:
        return f"snapshot is not admissible: {snapshot.refusal}"
    return None


def _c3_action_vocabulary(decision: ControlDecision, contract: ContractSpec) -> str | None:
    if decision.action not in contract.allowed_actions:
        return (
            f"action {decision.action!r} is not in the contract's allowed_actions "
            f"{contract.allowed_actions}"
        )
    return None


def _c4_target_scope(decision: ControlDecision, snapshot: ControlContext) -> str | None:
    ids = {v for _, v in parse_scope_path(snapshot.scope_path)}
    if decision.target_id not in ids:
        return (
            f"target {decision.target_id!r} is not within the snapshot's scope_path "
            f"{snapshot.scope_path!r}"
        )
    return None


def _c5_facts_citation(decision: ControlDecision, snapshot: ControlContext) -> str | None:
    canonical = {f.fact_id for f in _all_canonical_refs(snapshot)}
    advisory = {f.fact_id for f in snapshot.advisory}
    for fid in decision.facts_used:
        if fid in advisory:
            return f"facts_used cites {fid!r} — an ADVISORY fact, never citable (hard rule 3)"
        if fid not in canonical:
            return f"facts_used cites {fid!r} — not a canonical fact in this snapshot"
    # F2 (implementation_notes.md): a route citing no facts breaks the §8.5 provenance chain and
    # makes expected_effect unscoreable. `continue` is the null action and is exempt.
    if decision.action != "continue" and not decision.facts_used:
        return (
            f"action {decision.action!r} cites no facts — facts_used must be non-empty for any "
            f"action other than continue (F2)"
        )
    return None


def _c6_derivation_chains(
    decision: ControlDecision, snapshot: ControlContext, store: FactStore | None
) -> str | None:
    if store is None:
        # Nothing further is checkable without a store to re-resolve a full CanonicalFact from
        # (a FactRef alone lacks inputs_digest/abstraction_level — the fields verify_chain
        # needs). Documented degradation, not a silent pass: C5 already confirmed every cited id
        # is a canonical member of THIS snapshot, and the snapshot itself was only ever
        # populated with chain-verified facts (I4's compile_context step 5) — this check adds a
        # SECOND, independent re-verification when a store is available, exactly as
        # publish_event's belt-and-braces lineage gate does.
        return None
    from agentic_dynamics.control.reducers import REDUCERS

    refs_by_id = {f.fact_id: f for f in _all_canonical_refs(snapshot)}
    for fid in decision.facts_used:
        ref = refs_by_id.get(fid)
        if ref is None:
            continue  # already refused by C5
        candidates = store.current_facts(ref.predicate)
        fact = next((f for f in candidates if f.fact_id == fid), None)
        if fact is None:
            return f"cited fact {fid!r} could not be re-resolved from the store"
        errors = verify_chain(fact, REDUCERS, resolve=store.resolve)
        if errors:
            return f"cited fact {fid!r} failed verify_chain: {errors[0]}"
    return None


def _c7_freshness_and_preconditions(
    decision: ControlDecision,
    snapshot: ControlContext,
    fresh_snapshot: ControlContext,
    contract: ContractSpec,
    now: str,
) -> str | None:
    compiled = _parse_iso(snapshot.compiled_at)
    current = _parse_iso(now)
    if (
        compiled is not None
        and current is not None
        and contract.max_snapshot_age_seconds is not None
    ):
        age = (current - compiled).total_seconds()
        if age > contract.max_snapshot_age_seconds:
            return (
                f"snapshot age {age:.0f}s exceeds contract max_snapshot_age_seconds "
                f"{contract.max_snapshot_age_seconds} — the TOCTOU guard"
            )
    fresh_by_predicate = {f.predicate: f for f in _all_canonical_refs(fresh_snapshot)}
    for pre in decision.preconditions:
        fresh = fresh_by_predicate.get(pre.fact)
        if fresh is None:
            return f"precondition on {pre.fact!r} has no fresh value to re-check"
        if not _op_holds(fresh.value, pre.op, pre.value):
            return (
                f"precondition {pre.fact!r} {pre.op} {pre.value!r} failed against fresh value "
                f"{fresh.value!r}"
            )
    return None


def _c8_policy_invariants(decision: ControlDecision, snapshot: ControlContext) -> str | None:
    by_predicate = {f.predicate: f for f in snapshot.invariants}
    if decision.action == "route":
        allowed = by_predicate.get("allowed_models")
        model = decision.parameters.get("model")
        if allowed is not None and model is not None:
            models = [m for m in allowed.value.split(",") if m]
            if models and model not in models:
                return (
                    f"proposed model {model!r} is not in the allowed_models invariant {models} "
                    f"— policy outranks the controller"
                )
    max_spend = by_predicate.get("max_spend_usd")
    cost = next((f for f in snapshot.job if f.predicate == "job_accumulated_cost_usd"), None)
    if max_spend is not None and cost is not None:
        try:
            if float(cost.value) > float(max_spend.value):
                return (
                    f"accumulated cost {cost.value} already exceeds max_spend_usd invariant "
                    f"{max_spend.value}"
                )
        except ValueError:
            pass
    return None


def _c9_actuation_authorization(decision: ControlDecision) -> str | None:
    is_human = decision.proposed_by.startswith("operator:")
    if decision.action not in AUTOMATABLE_ACTIONS and not is_human:
        return (
            f"action {decision.action!r} is not in AUTOMATABLE_ACTIONS "
            f"{sorted(AUTOMATABLE_ACTIONS)} and was not proposed by a human operator "
            f"(proposed_by={decision.proposed_by!r})"
        )
    return None


def _c10_recordability(decision: ControlDecision) -> str | None:
    if not decision.decision_id:
        return "decision has no decision_id"
    if not decision.snapshot_id:
        return "decision has no snapshot_id — the actuation record's `causes` would be unresolvable"
    if not decision.target_type or not decision.target_id:
        return "decision has no target — cannot be recorded"
    return None


#: (check code, check function) in design §8.3's fixed order. Each takes the full argument set
#: for uniform dispatch; unused parameters are ignored by checks that do not need them.
_CHECKS: tuple[tuple[str, Callable[..., str | None]], ...] = (
    ("C1", lambda d, s, fs, c, n, store: _c1_snapshot_binding(d, s)),
    ("C2", lambda d, s, fs, c, n, store: _c2_snapshot_admissibility(s)),
    ("C3", lambda d, s, fs, c, n, store: _c3_action_vocabulary(d, c)),
    ("C4", lambda d, s, fs, c, n, store: _c4_target_scope(d, s)),
    ("C5", lambda d, s, fs, c, n, store: _c5_facts_citation(d, s)),
    ("C6", lambda d, s, fs, c, n, store: _c6_derivation_chains(d, s, store)),
    ("C7", lambda d, s, fs, c, n, store: _c7_freshness_and_preconditions(d, s, fs, c, n)),
    ("C8", lambda d, s, fs, c, n, store: _c8_policy_invariants(d, s)),
    ("C9", lambda d, s, fs, c, n, store: _c9_actuation_authorization(d)),
    ("C10", lambda d, s, fs, c, n, store: _c10_recordability(d)),
)


def validate_decision(
    decision: ControlDecision,
    *,
    snapshot: ControlContext,
    fresh_snapshot: ControlContext,
    contract: ContractSpec,
    now: str,
    store: FactStore | None = None,
) -> ValidationResult:
    """Admit or refuse. Deterministic, total, and ordered — first failure short-circuits
    (design §8.3): a refusal names the most basic thing that was wrong, not an incidental
    downstream symptom. ``store`` is optional; when omitted, C6's independent re-verification
    degrades to a documented no-op (see its docstring) rather than failing closed on a check
    this function cannot itself perform without one.
    """
    for code, check in _CHECKS:
        reason = check(decision, snapshot, fresh_snapshot, contract, now, store)
        if reason is not None:
            return ValidationResult(admitted=False, check=code, reason=reason)
    return ValidationResult(admitted=True, check="", reason="")
