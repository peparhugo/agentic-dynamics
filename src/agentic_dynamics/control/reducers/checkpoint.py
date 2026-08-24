"""CAP addendum I10 — the ``checkpoint/v1`` reducer (design §4.1, reserved home per design §6).

Two jobs, both pure (design §4.1 — no I/O, no wall clock beyond ``inp.now``):

1. **Mint the canonical ``session_checkpoint`` fact** from a typed ``WorkflowRunResult`` JSON —
   the SAME evidence shape ``job_facts_v1``/``attempt_facts_v1`` already read
   (``source_type="workflow_run"``, ``EvidenceItem`` payload from ``WorkflowRunResult.to_dict()``,
   the ``kb_produce_facts.py`` convention). Only :data:`control.checkpoint.DERIVED_FIELDS` are
   folded into the fact's JSON ``value`` — never the ADVISORY narrative fields (design D5).

2. **Mint the five POSITIVE-MARKER booleans** the ``session_routing`` contract's decision logic
   reads (``checkpoint_present``, ``checkpoint_goal_unchanged``, ``checkpoint_phase_unchanged``,
   ``checkpoint_model_unchanged``, ``model_change_required``) by comparing a checkpoint's own
   captured state against a SECOND, freshly-supplied "the decision being evaluated right now"
   evidence item (``source_type="session_current"`` — a NEW, reducer-local ``EvidenceItem`` tag;
   this is NOT a ``knowledge.SOURCE_TYPES`` row and touches no transport, see
   ``control.facts.EvidenceItem``'s own docstring: ``source_type`` "names the evidence family",
   a vocabulary each reducer is free to extend for its own inputs).

**The positive-marker convention (load-bearing for how the contract stays sound — see the
module's own note in ``experiments/contexts/session_routing.yaml`` for the FULL reasoning): each
of these five predicates is emitted ONLY as ``"true"``, and ONLY when the reducer has REAL
evidence for it.** A false/changed/unmeasured/no-checkpoint condition is represented by the
fact's ABSENCE, never by an emitted ``"false"`` value. This is what makes
``on_missing: halt``/``on_missing: classify`` (design's own vocabulary, ``core/contracts.py``)
correctly capture BOTH "no evidence exists" and "the condition doesn't hold" as the identical,
correct refusal path — no separate ``on_ne``/"value is false" branching is needed anywhere in the
contract or the validator.

**Why ``checkpoint_snapshot_identity`` is declared but NEVER emitted here (v1):** design D2 — no
snapshot producer exists yet (``control/context_compiler.py`` has not wired a capture call site).
Structurally identical to ``SessionCheckpoint.context_snapshot_id`` always being ``None``: the
predicate is registered (so the contract's ``requires_facts`` entry for it is representable and
legitimately degrades via ``on_missing: classify``) but this reducer's ``produces`` never actually
emits a fact for it — the same "declared producer, v1 chooses not to fire it" posture
``current_commit`` already takes in ``job_facts.py`` (``if git_sha:``), generalized to "always
absent, by design, until its own producer lands".
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from agentic_dynamics.control.checkpoint import SessionCheckpoint, derived_payload
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
    run_recency_key,
)

# ── Reducer declaration ─────────────────────────────────────────

VERSION = "checkpoint/v1"

#: ``checkpoint_snapshot_identity`` is declared here (this reducer is its ONLY legal producer,
#: per the FACT_PREDICATES invariant) but never appears in an ACTUAL ``pattern_v1``-style emit
#: list below — see the module docstring's "never emitted here" note.
_PRODUCES = (
    "session_checkpoint",
    "checkpoint_present",
    "checkpoint_goal_unchanged",
    "checkpoint_phase_unchanged",
    "checkpoint_model_unchanged",
    "model_change_required",
    "checkpoint_snapshot_identity",
)

CHECKPOINT_V1 = ReducerSpec(
    name="checkpoint",
    version=VERSION,
    level="job",
    scope_type="job",
    # "workflow_run" is the EXISTING kb_produce_facts.py evidence tag (job_facts.py/
    # attempt_facts.py already consume it); "session_current" is NEW here — the freshly-supplied
    # comparison state for a decision being evaluated right now (module docstring).
    consumes=("workflow_run", "session_current"),
    produces=_PRODUCES,
    determinism="pure",
)

#: The raw ``session_checkpoint`` payload fact is a recorded measurement projection — OBSERVED
#: would overclaim (it's a DERIVED reshaping of several observed fields, not one raw observation);
#: DERIVED/[C] matches design §4.1's own grade for every field this fact actually carries.
_EPISTEMIC_STATUS = "derived"
_AUTHORITY, _EVIDENCE_CLASS = EPISTEMIC_MAP[_EPISTEMIC_STATUS]


# ── Deriving a SessionCheckpoint from one WorkflowRunResult (pure) ─


def _completed_phase_names(run: dict[str, Any]) -> tuple[str, ...]:
    """Phase names with ``status == "ok"`` — the pure, non-I/O proxy for the addendum's git-log
    ``_completed_phases`` (module docstring's ``completed`` field note)."""
    phases = run.get("phases") or []
    return tuple(
        str(p.get("phase"))
        for p in phases
        if isinstance(p, dict) and p.get("status") == "ok" and p.get("phase")
    )


def _acceptance_state(run: dict[str, Any]) -> str:
    """One of ``verified_pass`` / ``verified_fail`` / ``unverified_ok`` / ``unverified_fail`` —
    combines the run's OWN ``ok`` (`WorkflowRunResult.ok`, design's ``status`` citation) with
    whether ANY phase carried a real, independent ``test_executed_success`` (design's own
    citation, `workflow_runner.py:113`). "Verified" means independently tested, not merely that
    every phase reported ``ok`` — the same MEASURED-vs-DERIVED distinction the ledger schema
    itself already draws (`experiment_spec.py`'s ``test_executed_success`` field)."""
    phases = run.get("phases") or []
    tested = [p for p in phases if isinstance(p, dict) and p.get("test_executed_success") is not None]
    ok = bool(run.get("ok"))
    if tested:
        verified_ok = all(p.get("test_executed_success") for p in tested)
        return "verified_pass" if verified_ok else "verified_fail"
    return "unverified_ok" if ok else "unverified_fail"


def checkpoint_from_run(run: dict[str, Any]) -> SessionCheckpoint:
    """Pure ``WorkflowRunResult`` dict -> :class:`SessionCheckpoint`. Populates ONLY the DERIVED
    fields (design §4.1); every ADVISORY field is left at its default (empty/blank) — this
    function is not where narrative capture would happen (out of this increment's scope, per the
    module docstring and design §7 item 8)."""
    return SessionCheckpoint(
        goal=str(run.get("goal") or ""),
        completed=_completed_phase_names(run),
        current_revision=str(run.get("git_sha") or ""),
        acceptance_state=_acceptance_state(run),
        context_snapshot_id=None,  # v1: always None (D2)
        snapshot_available=False,  # v1: always False (D2)
    )


# ── Fact construction (shared identity/scope shape) ─────────────


def _base_fact_kwargs(
    *,
    cell: str,
    predicate: str,
    value: str,
    inp: ReducerInput,
    evidence_ids: tuple[str, ...],
    observed_at: str,
    source_revision: str,
) -> dict[str, Any]:
    spec = FACT_PREDICATES[predicate]
    return dict(
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
        scope_path=f"org:{inp.repository_id}/workload:{cell}/job:{cell}",
        abstraction_level=spec.abstraction_level,
        epistemic_status=_EPISTEMIC_STATUS,
        authority=_AUTHORITY,
        evidence_class=_EVIDENCE_CLASS,
        observed_at=observed_at,
        valid_from=observed_at,
        valid_to=None,
        expires_at=None,
        reducer="checkpoint",
        reducer_version=VERSION,
        evidence_ids=evidence_ids,
        inputs_digest="",  # back-filled below from evidence_ids + reducer_version
        supersedes=None,  # the producer links a predecessor via the registry, not the reducer
        source_revision=source_revision,
        repository_id=inp.repository_id,
    )


def _fact(**kwargs: Any) -> CanonicalFact:
    fact = CanonicalFact(**kwargs)
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


def _bool_marker_fact(
    *, cell: str, predicate: str, inp: ReducerInput, evidence_ids: tuple[str, ...],
    observed_at: str, source_revision: str,
) -> CanonicalFact:
    """One POSITIVE-MARKER boolean fact — ALWAYS ``value="true"`` (module docstring's
    convention: a marker predicate is only ever emitted when it holds; absence is how "false"
    is represented, so this helper has no ``value`` parameter to get wrong)."""
    return _fact(
        **_base_fact_kwargs(
            cell=cell, predicate=predicate, value="true", inp=inp,
            evidence_ids=evidence_ids, observed_at=observed_at, source_revision=source_revision,
        )
    )


# ── The reducer (pure) ──────────────────────────────────────────


def checkpoint_v1(inp: ReducerInput) -> list[CanonicalFact]:
    """Emit ``session_checkpoint`` plus the marker booleans, one cell at a time.

    Pure and total (design §4.1): for each cell (``spec_name``+``model``, ``_common.cell_id``)
    with at least one ``workflow_run`` evidence item, the MOST RECENTLY RECORDED run
    (``_common.run_recency_key`` — the run's own recorded ``ended_at``/``started_at``, never wall
    clock) is treated as that cell's checkpoint. ``checkpoint_present`` and
    ``session_checkpoint`` are emitted from that alone; the three ``checkpoint_*_unchanged``
    markers and ``model_change_required`` are additionally emitted ONLY when a
    ``session_current`` evidence item for the SAME cell is also present — no phantom comparison
    against a "current" state that was never supplied (the same no-fabrication discipline
    ``control/reducers/pattern.py`` already established for I9).
    """
    runs_by_cell: dict[str, list[dict[str, Any]]] = {}
    current_by_session: dict[str, dict[str, Any]] = {}
    for item in inp.evidence:
        if not isinstance(item, EvidenceItem):
            continue
        payload = as_dict(item.payload)
        if payload is None:
            continue
        spec_name = str(payload.get("spec_name") or "")
        model = str(payload.get("model") or "")
        if not spec_name or not model:
            continue  # unaddressable — no cell identity, no fact (mirrors job_facts_v1)
        if item.source_type == "workflow_run":
            cell = cell_id(spec_name, model)
            runs_by_cell.setdefault(cell, []).append(payload)
        elif item.source_type == "session_current":
            # Joined by `spec_name` ALONE — NOT `cell_id(spec_name, model)`. This is deliberate,
            # not an oversight: `model_change_required` exists to detect exactly the case where
            # the "current" proposal names a DIFFERENT model than the checkpoint's own — and this
            # plane's own job-scope convention folds `model` into `cell_id` everywhere else
            # (job_facts.py, attempt_facts.py, policy_facts.py). Joining on the FULL cell id would
            # make the one case this predicate exists to catch structurally unjoinable (the
            # checkpoint and its "current" comparison would compute to two DIFFERENT cells the
            # moment the model actually changes). The checkpoint's OWN fact identity below still
            # uses its own `cell_id(spec_name, model)` — only this comparison join uses the
            # narrower, session-level key. Last-one-wins on a duplicate "current" item for the
            # same session (a caller bug, not a real scenario) — deterministic, never a crash.
            current_by_session[spec_name] = payload

    facts: list[CanonicalFact] = []
    for cell in sorted(runs_by_cell):
        latest_run = max(runs_by_cell[cell], key=run_recency_key)
        checkpoint = checkpoint_from_run(latest_run)
        observed_at = str(latest_run.get("ended_at") or latest_run.get("started_at") or inp.now)
        source_revision = str(latest_run.get("git_sha") or REVISION_FALLBACK)
        run_evidence_id = f"workflow_run:{cell}"

        facts.append(
            _fact(
                **_base_fact_kwargs(
                    cell=cell, predicate="session_checkpoint",
                    value=json.dumps(derived_payload(checkpoint), sort_keys=True),
                    inp=inp, evidence_ids=(run_evidence_id,),
                    observed_at=observed_at, source_revision=source_revision,
                )
            )
        )
        facts.append(
            _bool_marker_fact(
                cell=cell, predicate="checkpoint_present", inp=inp,
                evidence_ids=(run_evidence_id,), observed_at=observed_at,
                source_revision=source_revision,
            )
        )

        current = current_by_session.get(str(latest_run.get("spec_name") or ""))
        if current is None:
            continue  # no comparison possible — no phantom checkpoint_*_unchanged fact
        current_evidence_id = f"session_current:{cell}"
        both_ids = (run_evidence_id, current_evidence_id)
        last_phase = latest_run.get("phases")[-1].get("phase") if latest_run.get("phases") else None

        if checkpoint.goal and str(current.get("goal") or "") == checkpoint.goal:
            facts.append(
                _bool_marker_fact(
                    cell=cell, predicate="checkpoint_goal_unchanged", inp=inp,
                    evidence_ids=both_ids, observed_at=observed_at,
                    source_revision=source_revision,
                )
            )
        if last_phase and str(current.get("phase") or "") == last_phase:
            facts.append(
                _bool_marker_fact(
                    cell=cell, predicate="checkpoint_phase_unchanged", inp=inp,
                    evidence_ids=both_ids, observed_at=observed_at,
                    source_revision=source_revision,
                )
            )
        checkpoint_model = str(latest_run.get("model") or "")
        current_model = str(current.get("model") or "")
        if checkpoint_model and current_model == checkpoint_model:
            facts.append(
                _bool_marker_fact(
                    cell=cell, predicate="checkpoint_model_unchanged", inp=inp,
                    evidence_ids=both_ids, observed_at=observed_at,
                    source_revision=source_revision,
                )
            )
        elif checkpoint_model and current_model and current_model != checkpoint_model:
            facts.append(
                _bool_marker_fact(
                    cell=cell, predicate="model_change_required", inp=inp,
                    evidence_ids=both_ids, observed_at=observed_at,
                    source_revision=source_revision,
                )
            )
    return facts
