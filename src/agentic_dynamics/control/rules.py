"""CAP I6/I7 — the fact-based ``route_next_job`` control rule, the shadow hook, and the apply seam.

``route_next_job_v1`` is the FIRST control rule the plane ships (design §8.4): it consumes a
compiled :class:`~agentic_dynamics.control.context_compiler.ControlContext` (I4) and proposes
``{route, continue}``, exactly ``step_routing.route_step``'s action space. It never replaces
``route_step`` — design §8.4 keeps that the deterministic, measured baseline. Two seams build on
it, in increasing order of consequence:

* :func:`make_shadow_router` (I6) — runs both, validates the plane's proposal
  (``control.validator.validate_decision``), records it, and ALWAYS returns ``route_step``'s
  real choice. Nothing here is ever applied.
* :func:`make_applying_router` (I7) — a strict superset: applies the plane's ``route`` choice
  INSTEAD of ``route_step``'s ONLY when a freshly re-validated decision is admitted AND its
  action is in :data:`~agentic_dynamics.control.decisions.AUTOMATABLE_ACTIONS`; any validation
  failure, an inadmissible snapshot, a ``continue`` proposal, or any internal error falls back to
  ``route_step``'s deterministic choice — the safe path, not a degraded one. Wiring it requires
  an explicit PER-SPEC opt-in (``workflow.params.control_route: true``, design §9 I7); it is
  never the default and no committed spec sets it (``scripts/run_workflow.py``,
  ``docs/context_abstraction/implementation_notes.md``'s flip procedure).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_dynamics.control.actuation_ingestion import (
    EXTRACTOR_VERSION as _ACTUATION_EXTRACTOR_VERSION,
)
from agentic_dynamics.control.context_compiler import (
    CONTRACTS_DIR,
    REVISION_FALLBACK,
    ContextRequest,
    ControlContext,
    FactStore,
    RegistryFactStore,
    compile_context,
    load_contract,
    record_snapshot,
)
from agentic_dynamics.control.decisions import (
    AUTOMATABLE_ACTIONS,
    ControlDecision,
    ExpectedEffect,
    Precondition,
)
from agentic_dynamics.control.facts import FactRef
from agentic_dynamics.control.validator import validate_decision
from agentic_dynamics.core.paths import KB_ARTIFACT_DIR
from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat()


def _find(refs: tuple[FactRef, ...], predicate: str) -> FactRef | None:
    return next((r for r in refs if r.predicate == predicate), None)


def _decision_id(snapshot_id: str, action: str, target_id: str, proposed_at: str) -> str:
    """Deterministic identity for one decision candidate (mirrors ``actuation_ingestion._actuation_id``:
    one identity per candidate, folding in the proposal time)."""
    return hashlib.sha256(
        f"{snapshot_id}|{action}|{target_id}|{proposed_at}".encode()
    ).hexdigest()[:16]


# ── The rule (pure — no I/O, mirrors the reducer/route_step discipline) ─


def route_next_job_v1(
    ctx: ControlContext,
    *,
    target_type: str = "job",
    target_id: str,
    proposed_at: str,
    proposed_by: str = "policy_rule:route_next_job",
) -> ControlDecision:
    """Propose ``{route, continue}`` for one job scope from a compiled ``ControlContext``.

    Deterministic and pure: given the same snapshot it always proposes the same decision. The
    policy is deliberately simple (v1 — a first, measurable baseline, not a scored router): route
    to the lexicographically first ``allowed_models`` entry while phases remain and the snapshot
    is admissible; otherwise ``continue``. Sophistication is earned by MEASURING this rule
    against ``step_routing`` (the shadow comparison, ``compile_experiment.decision_calibration``),
    never by front-loading a heuristic no evidence yet supports.
    """
    decision_id = _decision_id(ctx.snapshot_id, "continue", target_id, proposed_at)
    base = dict(
        snapshot_id=ctx.snapshot_id,
        decision_type=ctx.decision_type,
        contract_version=ctx.contract_version,
        target_type=target_type,
        target_id=target_id,
        proposed_by=proposed_by,
        proposed_at=proposed_at,
    )

    if not ctx.admissible:
        return ControlDecision(
            decision_id=decision_id,
            action="continue",
            parameters={},
            facts_used=(),
            expected_effect=(),
            preconditions=(),
            rationale=f"snapshot inadmissible: {ctx.refusal}",
            **base,
        )

    remaining = _find(ctx.workflow, "workflow_phases_remaining")
    allowed = _find(ctx.invariants, "allowed_models")
    if remaining is None or allowed is None or remaining.value == "0":
        cited = tuple(f.fact_id for f in (remaining, allowed) if f is not None)
        return ControlDecision(
            decision_id=decision_id,
            action="continue",
            parameters={},
            facts_used=cited,
            expected_effect=(),
            preconditions=(),
            rationale=(
                "no phases remaining" if remaining is not None and remaining.value == "0"
                else "workflow_phases_remaining or allowed_models unresolved"
            ),
            **base,
        )

    models = sorted(m for m in allowed.value.split(",") if m)
    if not models:
        return ControlDecision(
            decision_id=decision_id,
            action="continue",
            parameters={},
            facts_used=(remaining.fact_id, allowed.fact_id),
            expected_effect=(),
            preconditions=(),
            rationale="allowed_models invariant is empty",
            **base,
        )

    chosen = models[0]
    cost = _find(ctx.job, "job_accumulated_cost_usd")
    facts_used = tuple(f.fact_id for f in (remaining, allowed, cost) if f is not None)
    expected_effect = (
        ExpectedEffect(
            predicate="workflow_phases_remaining", direction="decrease", magnitude=1.0,
            horizon="next_phase",
        ),
        ExpectedEffect(
            predicate="job_accumulated_cost_usd", direction="increase", magnitude=None,
            horizon="next_phase",
        ),
    )
    preconditions = (
        Precondition(
            fact="workflow_phases_remaining", scope="parent", op="gt", value=0,
            max_age_seconds=600,
        ),
    )
    route_decision_id = _decision_id(ctx.snapshot_id, "route", target_id, proposed_at)
    return ControlDecision(
        decision_id=route_decision_id,
        action="route",
        parameters={"model": chosen},
        facts_used=facts_used,
        expected_effect=expected_effect,
        preconditions=preconditions,
        rationale=(
            f"{remaining.value} phase(s) remaining; routed to {chosen} "
            f"(lexicographically first of {models})"
        ),
        **base,
    )


# ── CAP addendum I10 — the session_routing shadow control rule (design §4.2/§4.3) ─


def session_routing_v1(
    ctx: ControlContext,
    *,
    target_type: str = "job",
    target_id: str,
    proposed_at: str,
    proposed_by: str = "policy_rule:session_routing",
) -> ControlDecision:
    """Propose ``{continue, fork, compress_and_fork, escalate}`` for one session from a compiled
    ``session_routing`` :class:`ControlContext`.

    **Fully shadow, always — this function's own action space is entirely OUTSIDE
    ``AUTOMATABLE_ACTIONS`` (design §4.3, F4's resolution).** The session-continuation
    ``"continue"`` this function may propose is a DIFFERENT decision from the routing null-action
    ``"continue"`` ``route_next_job_v1`` proposes above — same string, different meaning (resuming
    a session is a positive, unmeasured `[H]` trade; the routing ``continue`` is "chose nothing").
    Conflating them under ``AUTOMATABLE_ACTIONS`` would let an automated path apply an unmeasured
    session policy; ``control/decisions.py``'s own comment on ``AUTOMATABLE_ACTIONS`` and this
    module's docstring both say the same thing for exactly this reason. Every proposal this
    function returns is only ever recorded (:func:`record_shadow_decision`, reused verbatim —
    NO new recording path for this decision type) and surfaced — never applied by any code path.

    **Per-action gating happens HERE, not in ``session_routing.yaml``'s ``invariants:``** — see
    that file's own header comment for why combining these five facts as blanket, unconditional
    invariants is logically unsatisfiable (a real adversarial finding, not a style choice). This
    function reads the (possibly-absent) marker facts ``compile_context`` resolved under
    ``requires_facts`` and decides which action to propose, the SAME "soft facts + rule-level
    branching" pattern :func:`route_next_job_v1` already uses for ``workflow_phases_remaining``/
    ``allowed_models`` above.

    Decision policy (v1 — deliberately simple, a first measurable baseline, never front-loaded
    sophistication; sharpened only once the design's own evidence-seed experiment, §4.4, measures
    it against the runner's existing fork-chain incumbent, ``workflow_runner.py:591-597``):

    1. **No checkpoint present at all** (a first phase) → ``continue``. The only safe proposal —
       forking with nothing to fork FROM is refused by construction (there is no ``fork``
       evidence to cite), never attempted.
    2. **Checkpoint present AND goal/phase/model all provably unchanged** (all three marker facts
       resolved) → ``continue``. This is the ONLY case ``continue`` is proposed once a checkpoint
       exists — the addendum's own "requires unchanged goal/phase/model" made mechanical.
    3. **Checkpoint present AND a model change is evidenced** (``model_change_required``
       resolved) → ``escalate``. Never inferred, never assumed from "goal changed" — a model
       change must be a REAL supplied fact.
    4. **Checkpoint present, but goal/phase/model did not all verify unchanged, and no evidenced
       model change** → ``fork``. The safe default once continuation cannot be proven safe.
    5. ``compress_and_fork`` is NEVER proposed by v1. Its trigger (context-token growth past a
       threshold, design §4.4's ``session_context_growth``) has no measured signal yet
       (``cost_inference``/``cache_hit`` etc. are declared-not-written, per the design's own F5
       table) — fabricating a threshold with no real backing would violate the exact
       no-phantom discipline ``control/reducers/pattern.py`` (I9) already established. The
       contract still ALLOWS the action (an operator or a future, evidenced v2 rule may propose
       it); v1's automatic rule simply never reaches for it.
    """
    decision_id = _decision_id(ctx.snapshot_id, "continue", target_id, proposed_at)
    base = dict(
        snapshot_id=ctx.snapshot_id,
        decision_type=ctx.decision_type,
        contract_version=ctx.contract_version,
        target_type=target_type,
        target_id=target_id,
        proposed_by=proposed_by,
        proposed_at=proposed_at,
    )

    if not ctx.admissible:
        return ControlDecision(
            decision_id=decision_id,
            action="continue",
            parameters={},
            facts_used=(),
            rationale=f"snapshot inadmissible: {ctx.refusal}",
            **base,
        )

    present = _find(ctx.job, "checkpoint_present")
    if present is None:
        return ControlDecision(
            decision_id=decision_id,
            action="continue",
            parameters={},
            facts_used=(),
            rationale="no checkpoint present — continuing is the only safe proposal",
            **base,
        )

    goal_ok = _find(ctx.job, "checkpoint_goal_unchanged")
    phase_ok = _find(ctx.job, "checkpoint_phase_unchanged")
    model_ok = _find(ctx.job, "checkpoint_model_unchanged")
    model_change = _find(ctx.job, "model_change_required")

    if goal_ok is not None and phase_ok is not None and model_ok is not None:
        cited = tuple(f.fact_id for f in (present, goal_ok, phase_ok, model_ok))
        # TOCTOU guard (adversarial release verdict, attack 4 — implementation_notes.md §17):
        # a `continue` claim is "the session's context is provably unchanged" — a claim about
        # the WORLD, not just about what THIS snapshot happened to resolve. Without a
        # `preconditions` entry per equality marker, check C7's fresh-snapshot re-check
        # (`validator._c7_freshness_and_preconditions`) degrades to a pure AGE check (was the
        # snapshot compiled too long ago) and does NOTHING to catch "the world changed within
        # the freshness window" — e.g. the goal changed 5 seconds ago but the snapshot was
        # compiled 250 seconds ago, well inside `max_snapshot_age_seconds: 300`. Mirrors
        # `route_next_job_v1`'s own established pattern (`workflow_phases_remaining` above):
        # every marker this decision's SAFETY rests on is re-checked, at apply time, against a
        # FRESH compile — `op="is_true"` matches this reducer's own positive-marker convention
        # (`control/reducers/checkpoint.py`: the fact is present-and-"true", or absent; there is
        # no "false" value to compare against). If the world changed enough that a marker no
        # longer resolves in the fresh snapshot, C7's `fresh is None` branch refuses the stale
        # `continue` outright — exactly the behavior a re-derived snapshot must enforce.
        preconditions = tuple(
            Precondition(fact=marker, scope="self", op="is_true", value="true", max_age_seconds=600)
            for marker in (
                "checkpoint_goal_unchanged", "checkpoint_phase_unchanged", "checkpoint_model_unchanged",
            )
        )
        return ControlDecision(
            decision_id=decision_id,
            action="continue",
            parameters={},
            facts_used=cited,
            preconditions=preconditions,
            rationale="checkpoint present and goal/phase/model provably unchanged",
            **base,
        )

    if model_change is not None:
        escalate_id = _decision_id(ctx.snapshot_id, "escalate", target_id, proposed_at)
        return ControlDecision(
            decision_id=escalate_id,
            action="escalate",
            parameters={},
            facts_used=(present.fact_id, model_change.fact_id),
            rationale="checkpoint present and a model change is evidenced",
            **base,
        )

    fork_id = _decision_id(ctx.snapshot_id, "fork", target_id, proposed_at)
    return ControlDecision(
        decision_id=fork_id,
        action="fork",
        parameters={},
        facts_used=(present.fact_id,),
        rationale=(
            "checkpoint present but goal/phase/model did not all verify unchanged — "
            "proposing fork"
        ),
        **base,
    )


# ── Shadow-mode recording (design §8.1: "proposal only" — recorded, never applied) ─


def decision_payload(decision: ControlDecision) -> dict[str, Any]:
    """The decision's JSON-safe body — what rides in the actuation record's ``requested_action``."""
    return {
        "decision_id": decision.decision_id,
        "snapshot_id": decision.snapshot_id,
        "decision_type": decision.decision_type,
        "contract_version": decision.contract_version,
        "action": decision.action,
        "target_type": decision.target_type,
        "target_id": decision.target_id,
        "parameters": decision.parameters,
        "facts_used": list(decision.facts_used),
        "expected_effect": [
            {
                "predicate": e.predicate, "direction": e.direction, "magnitude": e.magnitude,
                "horizon": e.horizon,
            }
            for e in decision.expected_effect
        ],
        "preconditions": [
            {
                "fact": p.fact, "scope": p.scope, "op": p.op, "value": p.value,
                "max_age_seconds": p.max_age_seconds,
            }
            for p in decision.preconditions
        ],
        "proposed_by": decision.proposed_by,
        "proposed_at": decision.proposed_at,
        "rationale": decision.rationale,
    }


def record_shadow_decision(
    decision: ControlDecision,
    *,
    repository_id: str = REPOSITORY_ID,
    causes: str,
    artifact_dir: Path = KB_ARTIFACT_DIR,
) -> Any | None:
    """Best-effort durable persistence of ONE shadow decision — deliberately WITHOUT arming
    actuation.

    ``ControlDecision`` maps onto ``source_type="actuation"`` (design §8.2, REUSE — see
    ``actuation_ingestion.derive_actuation_record``'s candidate shape). But
    ``knowledge_stream.publish_event``'s actuation gate REQUIRES ``FINOPS_ACTUATION_ARMED=1`` (or
    ``armed=True``) for ANY ``source_type="actuation"`` message — and design §8.6's commitment 1
    is that this plane "does not arm actuation... adds nothing that sets it". So "recorded, never
    applied" for a DECISION means: the durable per-record JSON artifact
    (``record_to_artifact`` -> ``KB_ARTIFACT_DIR/<knowledge_id>.json``) is written — a citable,
    content-addressed, auditable record — but the pointer event is deliberately NEVER published
    to ``kb:v1:changes``, so it never reaches the live registry/stream a real actuation consumer
    would react to, and the armed gate is never even attempted. Stricter than I4's snapshot
    recording (an OBSERVATION-family record with no armed gate, which DOES publish) — a
    documented deviation, ``docs/context_abstraction/implementation_notes.md``.

    Returns the built record on success, ``None`` on any failure — never blocks the routing call
    that triggered it.
    """
    try:
        from agentic_dynamics.control.actuation_ingestion import derive_actuation_record
        from agentic_dynamics.knowledge.record_factory import record_to_artifact

        # Structural marker (design §9 I6 disposition): a shadow decision is PROPOSED-not-executed.
        # Stamp `applied: False` explicitly so the record body is self-describing — a shadow
        # decision is distinguishable from a real actuation by the field, not by its location
        # (artifact-dir-only). The applying seam (`make_applying_router`) stamps `applied: True`
        # when it actually applies; never override a caller that already stamped it.
        if "applied" not in decision.parameters:
            decision = replace(
                decision, parameters={**decision.parameters, "applied": False}
            )
        candidate = {
            "actuation_kind": decision.action,
            "target_session_id": decision.target_id,
            "target_cell_id": decision.target_id,
            "requested_action": decision_payload(decision),
            "requested_by": decision.proposed_by,
            "causes": causes,
        }
        record = derive_actuation_record(candidate, repository_id=repository_id)
        artifact = record_to_artifact(record)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / f"{record.knowledge_id}.json").write_bytes(artifact)
        return record
    except Exception:
        return None


def make_shadow_router(
    *,
    workload: str,
    cell_id: str,
    repository_id: str = REPOSITORY_ID,
    revision: str = REVISION_FALLBACK,
    store: FactStore | None = None,
    contracts_dir: Path = CONTRACTS_DIR,
    record: bool = True,
    now_fn: Callable[[], str] = _now_iso,
) -> Callable[..., str]:
    """Build a drop-in ``Router`` that runs the plane BESIDE ``route_step`` — design §9 I6.

    For every call: (1) ``route_step`` decides the REAL model — unchanged, always returned;
    (2) a ``route_next_job/v1`` snapshot is compiled (I4) and (best-effort) recorded; (3) the
    fact-based rule proposes its OWN decision from that snapshot; (4) the proposal is validated
    (``control.validator.validate_decision``, C1-C10) and (best-effort) recorded as a
    ``source_type="actuation"`` artifact — armed gates OFF, so it can never be applied
    automatically even if some future code tried; (5) the recorded decision's ``parameters``
    additionally carry ``baseline_action``/``baseline_model`` — ``route_step``'s real choice —
    so ``compile_experiment.decision_calibration`` can score agreement without a second join.

    A superset of :func:`~agentic_dynamics.control.context_compiler.make_snapshotting_router`
    (I4): everything I4 does, plus the shadow decision. Injected at the composition root
    (``scripts/run_workflow.py``) exactly where ``route_step`` is injected — ``runtime.workflow_runner``
    still never imports ``control`` (Debt-2).
    """
    from agentic_dynamics.control.step_routing import route_step

    fact_store = store or RegistryFactStore(repository_id=repository_id)
    scope_path = f"org:{repository_id}/workload:{workload}/job:{cell_id}"
    try:
        contract = load_contract("route_next_job", contracts_dir=contracts_dir)
    except ValueError:
        contract = None

    def _router(job: dict, state, prefs, *, signals=None) -> str:
        model = route_step(job, state, prefs, signals=signals)
        if record:
            try:
                now = now_fn()
                request = ContextRequest(
                    decision_type="route_next_job",
                    scope_type="job",
                    scope_id=cell_id,
                    scope_path=scope_path,
                    repository_id=repository_id,
                )
                ctx = compile_context(
                    request, store=fact_store, now=now, contracts_dir=contracts_dir
                )
                snapshot_record = record_snapshot(ctx, repository_id=repository_id, revision=revision)
                decision = route_next_job_v1(ctx, target_id=cell_id, proposed_at=now)
                # Shadow-mode-only bookkeeping (never part of the frozen ControlDecision fields):
                # the baseline route_step chose, for decision_calibration's agreement scoring.
                decision = replace(
                    decision,
                    parameters={
                        **decision.parameters,
                        "baseline_action": "route",
                        "baseline_model": model,
                    },
                )
                if snapshot_record is not None and contract is not None:
                    result = validate_decision(
                        decision, snapshot=ctx, fresh_snapshot=ctx, contract=contract, now=now,
                        store=fact_store,
                    )
                    verdict = "admitted" if result.admitted else f"{result.check}: {result.reason}"
                    decision = replace(decision, rationale=f"{decision.rationale} | {verdict}")
                    record_shadow_decision(
                        decision, repository_id=repository_id, causes=snapshot_record.knowledge_id
                    )
            except Exception:
                pass  # shadow recording is measurement — never blocks the actual route
        return model

    return _router


def load_shadow_decisions(*, artifact_dir: Path = KB_ARTIFACT_DIR) -> list[dict[str, Any]]:
    """Scan ``artifact_dir`` for recorded shadow/applied decision artifacts.

    Returns ``compile_experiment.decision_calibration``-shaped rows:
    ``{action, baseline_action, model, baseline_model, applied}``. A single shared reader for
    both report scripts (``scripts/shadow_decision_report.py``,
    ``scripts/decision_arm_comparison.py``) — decisions are deliberately never published to the
    registry/stream (:func:`record_shadow_decision`'s docstring), so this directory scan is the
    only way to enumerate them; keeping the scan in ONE place means both scripts see identical
    rows.
    """
    if not artifact_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(artifact_dir.glob("*.json")):
        try:
            artifact = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if artifact.get("source_type") != "actuation":
            continue
        if artifact.get("extractor_version") != _ACTUATION_EXTRACTOR_VERSION:
            continue
        try:
            body = json.loads(artifact.get("text") or "{}")
        except json.JSONDecodeError:
            continue
        payload = body.get("requested_action") or {}
        parameters = payload.get("parameters") or {}
        if "baseline_action" not in parameters:
            continue  # an actuation artifact from a different producer, not a shadow decision
        rows.append({
            "action": payload.get("action"),
            "baseline_action": parameters.get("baseline_action"),
            "model": parameters.get("model"),
            "baseline_model": parameters.get("baseline_model"),
            "applied": bool(parameters.get("applied", False)),
        })
    return rows


# ── CAP I7 — the apply seam (design §9 I7, kept OFF by default) ───


def make_applying_router(
    *,
    workload: str,
    cell_id: str,
    repository_id: str = REPOSITORY_ID,
    revision: str = REVISION_FALLBACK,
    store: FactStore | None = None,
    contracts_dir: Path = CONTRACTS_DIR,
    record: bool = True,
    now_fn: Callable[[], str] = _now_iso,
) -> Callable[..., str]:
    """Build a drop-in ``Router`` that MAY apply the plane's ``route`` choice (design §9 I7).

    The only function in this module that can change what actually executes a phase. Applies
    the fact-based rule's proposed model INSTEAD of ``route_step``'s ONLY when ALL of:

    1. the compiled snapshot is admissible;
    2. the proposed decision's action is ``"route"`` (a member of ``AUTOMATABLE_ACTIONS``, but
       ``"continue"`` — the other member — means "use the default", i.e. ``route_step``'s
       choice, by definition, so only ``"route"`` can ever change the outcome);
    3. a FRESH re-compilation (the TOCTOU guard, check C7) still validates the decision through
       ALL of C1-C10.

    Any failure at any point — inadmissible snapshot, a validation refusal, a ``continue``
    proposal, a missing contract, an exception anywhere in the plane — falls back to
    ``route_step``'s deterministic choice. This fallback is the SAFE path, not a degraded one:
    the function never raises past this seam, and the workflow's routing behavior is
    byte-for-byte ``route_step`` whenever the plane has nothing admissible to say.

    Still records the decision (I6's bookkeeping, tagging ``parameters.applied``) so
    ``load_shadow_decisions``/``decision_calibration`` see applied and shadow-only decisions
    uniformly. Wiring this at the composition root requires the PER-SPEC opt-in
    (``workflow.params.control_route: true``) — see ``scripts/run_workflow.py``; never a
    default, and no committed spec sets it (design §9 I7's own gate: "opt in only after the
    shadow comparison shows non-inferior loss" — that campaign data does not exist yet).
    """
    from agentic_dynamics.control.step_routing import route_step

    fact_store = store or RegistryFactStore(repository_id=repository_id)
    scope_path = f"org:{repository_id}/workload:{workload}/job:{cell_id}"
    try:
        contract = load_contract("route_next_job", contracts_dir=contracts_dir)
    except ValueError:
        contract = None

    def _router(job: dict, state, prefs, *, signals=None) -> str:
        baseline_model = route_step(job, state, prefs, signals=signals)
        applied_model = baseline_model
        try:
            request = ContextRequest(
                decision_type="route_next_job",
                scope_type="job",
                scope_id=cell_id,
                scope_path=scope_path,
                repository_id=repository_id,
            )
            ctx = compile_context(
                request, store=fact_store, now=now_fn(), contracts_dir=contracts_dir
            )
            decision = route_next_job_v1(ctx, target_id=cell_id, proposed_at=now_fn())
            applied = False
            verdict = "no contract"
            if contract is not None:
                # A genuinely FRESH re-compilation for C7's TOCTOU re-check — nothing has
                # executed between the two calls, but the fields that matter (now, staleness)
                # are independently recomputed rather than reusing `ctx`.
                fresh_ctx = compile_context(
                    request, store=fact_store, now=now_fn(), contracts_dir=contracts_dir
                )
                result = validate_decision(
                    decision, snapshot=ctx, fresh_snapshot=fresh_ctx, contract=contract,
                    now=now_fn(), store=fact_store,
                )
                verdict = "admitted" if result.admitted else f"{result.check}: {result.reason}"
                if (
                    result.admitted
                    and decision.action in AUTOMATABLE_ACTIONS
                    and decision.action == "route"
                ):
                    applied_model = decision.parameters.get("model", baseline_model)
                    applied = True

            decision = replace(
                decision,
                parameters={
                    **decision.parameters,
                    "baseline_action": "route",
                    "baseline_model": baseline_model,
                    "applied": applied,
                },
                rationale=f"{decision.rationale} | {verdict} | applied={applied}",
            )
            if record:
                snapshot_record = record_snapshot(
                    ctx, repository_id=repository_id, revision=revision
                )
                if snapshot_record is not None:
                    record_shadow_decision(
                        decision, repository_id=repository_id,
                        causes=snapshot_record.knowledge_id,
                    )
        except Exception:
            applied_model = baseline_model  # any failure anywhere -> the safe, unmodified route
        return applied_model

    return _router
