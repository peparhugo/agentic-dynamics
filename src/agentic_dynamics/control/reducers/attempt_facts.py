"""CAP I2 — the ``attempt_facts/v1`` reducer.

Derives per-phase (attempt) facts from the typed workflow run artifacts — the
``WorkflowRunResult`` / ``PhaseResult`` JSON shape ``scripts/run_workflow.py:108`` writes to
``experiments/results/workflows/<spec>/<ts>.json``. It is the subject/predicate/value layer
ABOVE ``ledger_ingestion``: the ledger records are prose-typed (cost/tokens embedded in a
formatted ``text`` string — the review's prose-projection defect §3d(iv)); this reducer re-reads
the *typed* artifact and mints one :class:`CanonicalFact` per measured field, so the numbers are
machine-readable without parsing prose.

Pure and deterministic (design §4.1): no I/O, no RNG; the caller resolves the run JSONs and hands
them in via ``ReducerInput.evidence``; the reducer only maps ``run → facts``. The injected
``inp.now`` is a fallback for a run whose ledger has no ``ended_at``/``started_at`` — a properly
stamped run never depends on the producer clock, which is what makes re-derivation byte-for-byte
stable (the I2 gate).

Scope (task's I2 semantics): each fact is scoped ``attempt:<phase>`` under ``job:<cell>`` where
``<cell> = wf_<spec>_<model>`` (the workflow cell, §10.1). The attempt ``scope_id`` is
job-qualified (``<cell>:<phase>``) so two runs of the same phase name never collide on
``fact_entity_id``.

Epistemics are a pure function of the predicate (§3.4): the measured fields are ``observed``
(MEASURED/[M]), ``phase_test_verified`` is ``verified`` (MEASURED/[M] — the independent
test_runner), and ``attempt_confidence`` is ``advisory`` (ADVISORY/[H] — a self-report, the
design §5's explicit flag). ``fact_id`` is emitted empty and finalized at persistence.
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

VERSION = "attempt_facts/v1"

#: The nine per-phase predicates the reducer emits. Every name exists in FACT_PREDICATES.
_PRODUCES = (
    "phase_status",
    "attempt_model",
    "attempt_tokens_in",
    "attempt_tokens_out",
    "attempt_cost_usd",
    "attempt_cache_hit_rate",
    "phase_test_verified",
    "attempt_confidence",
    "phase_commit",
)

ATTEMPT_FACTS_V1 = ReducerSpec(
    name="attempt_facts",
    version=VERSION,
    level="fact",
    scope_type="attempt",
    consumes=("workflow_run",),  # the typed run artifact (WorkflowRunResult JSON)
    produces=_PRODUCES,
    determinism="pure",
)

#: The single-discriminator epistemic mapping, specialised per predicate (design §3.4 / §5).
#: ``attempt_confidence`` is the one ADVISORY attempt fact (self-report, never canonical);
#: ``phase_test_verified`` is VERIFIED (the independent test_runner); everything else is OBSERVED
#: (recorded by the system). authority/evidence_class are DERIVED from these, never chosen.
_OBSERVED = "observed"
_VERIFIED = "verified"
_ADVISORY = "advisory"

#: The per-predicate epistemic status — the ONLY place this table lives, so it cannot drift.
_EPISTEMIC_BY_PREDICATE: dict[str, str] = {
    "attempt_confidence": _ADVISORY,
    "phase_test_verified": _VERIFIED,
}


def _epistemic(predicate: str) -> str:
    """The epistemic status for a predicate: the two flagged exceptions, else ``observed``."""
    return _EPISTEMIC_BY_PREDICATE.get(predicate, _OBSERVED)


# ── Fact construction ───────────────────────────────────────────


def _fact(
    run: dict[str, Any],
    phase_name: str,
    scope_id: str,
    inp: ReducerInput,
    predicate: str,
    value: str,
) -> CanonicalFact:
    """Build one attempt-scoped fact for ``predicate`` (design §10's scope hierarchy).

    ``epistemic_status`` is derived INSIDE here (from the predicate) rather than passed alongside,
    so a call site can never disagree with the predicate's declared epistemology (§3.4).
    """
    spec = FACT_PREDICATES[predicate]
    epistemic_status = _epistemic(predicate)
    authority, evidence_class = EPISTEMIC_MAP[epistemic_status]
    cell = cell_id(str(run.get("spec_name") or ""), str(run.get("model") or ""))
    observed_at = str(run.get("ended_at") or run.get("started_at") or inp.now)
    fact = CanonicalFact(
        fact_entity_id=compute_fact_entity_id(
            repository_id=inp.repository_id,
            scope_type="attempt",
            scope_id=scope_id,  # job-qualified: "<cell>:<phase>"
            predicate=predicate,
            subject_type="attempt",
            subject_id=phase_name,
        ),
        fact_id="",  # finalized at persistence — the record's knowledge_id IS the fact_id
        subject_type="attempt",
        subject_id=phase_name,
        predicate=predicate,
        value=value,
        value_type=spec.value_type,
        unit=spec.unit,
        scope_type="attempt",
        scope_id=scope_id,
        scope_path=(
            f"org:{inp.repository_id}/workload:{run.get('spec_name')}"
            f"/job:{cell}/attempt:{phase_name}"
        ),
        abstraction_level=spec.abstraction_level,
        epistemic_status=epistemic_status,
        authority=authority,
        evidence_class=evidence_class,
        observed_at=observed_at,
        valid_from=observed_at,
        valid_to=None,
        expires_at=None,
        reducer="attempt_facts",
        reducer_version=VERSION,
        evidence_ids=(),  # consumes the run artifact directly, not knowledge records
        inputs_digest="",  # back-filled below from evidence_ids + reducer_version
        supersedes=None,  # the producer links a predecessor via the registry, not the reducer
        source_revision=str(run.get("git_sha") or REVISION_FALLBACK),
        repository_id=inp.repository_id,
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


# ── Per-phase derivation ────────────────────────────────────────


def _facts_for_phase(
    run: dict[str, Any], phase: dict[str, Any], inp: ReducerInput
) -> list[CanonicalFact]:
    """Emit the facts one phase pins, honouring measured-or-absent semantics."""
    phase_name = str(phase.get("phase") or "")
    if not phase_name:
        return []
    cell = cell_id(str(run.get("spec_name") or ""), str(run.get("model") or ""))
    scope_id = f"{cell}:{phase_name}"

    facts: list[CanonicalFact] = []
    status = str(phase.get("status") or "")
    if status:
        facts.append(
            _fact(run, phase_name, scope_id, inp, "phase_status", encode_value(status, "enum"))
        )
    commit = str(phase.get("commit_hash") or "")
    if commit:
        facts.append(
            _fact(run, phase_name, scope_id, inp, "phase_commit", encode_value(commit, "str"))
        )

    # Agent-phase measurements (model/tokens/cost/cache/confidence). Test phases carry none of
    # these, so gating on ``kind`` keeps an absent measurement absent rather than a defaulted 0.
    if str(phase.get("kind") or "agent") == "agent":
        model = str(phase.get("model") or "")
        if model:
            facts.append(
                _fact(run, phase_name, scope_id, inp, "attempt_model", encode_value(model, "str"))
            )
        tokens = phase.get("tokens") or {}
        if isinstance(tokens, dict):
            if tokens.get("in"):
                facts.append(
                    _fact(
                        run,
                        phase_name,
                        scope_id,
                        inp,
                        "attempt_tokens_in",
                        encode_value(tokens.get("in"), "int"),
                    )
                )
            if tokens.get("out"):
                facts.append(
                    _fact(
                        run,
                        phase_name,
                        scope_id,
                        inp,
                        "attempt_tokens_out",
                        encode_value(tokens.get("out"), "int"),
                    )
                )
        cost = phase.get("cost_usd")
        if isinstance(cost, (int, float)):
            facts.append(
                _fact(run, phase_name, scope_id, inp, "attempt_cost_usd", encode_value(cost, "usd"))
            )
        cache = phase.get("cache_hit_rate")
        if isinstance(cache, (int, float)):
            facts.append(
                _fact(
                    run,
                    phase_name,
                    scope_id,
                    inp,
                    "attempt_cache_hit_rate",
                    encode_value(cache, "float"),
                )
            )
        confidence = phase.get("confidence")
        if confidence is not None:
            facts.append(
                _fact(
                    run,
                    phase_name,
                    scope_id,
                    inp,
                    "attempt_confidence",
                    encode_value(confidence, "float"),
                )
            )

    # Independent test verification (a bool is a real measurement; None is "not verified").
    if isinstance(phase.get("test_executed_success"), bool):
        facts.append(
            _fact(
                run,
                phase_name,
                scope_id,
                inp,
                "phase_test_verified",
                encode_value(phase.get("test_executed_success"), "bool"),
            )
        )
    return facts


# ── The reducer (pure) ──────────────────────────────────────────


def attempt_facts_v1(inp: ReducerInput) -> list[CanonicalFact]:
    """Emit per-phase attempt facts for every run JSON in ``inp.evidence``.

    Pure and total: every phase with a name yields at least a ``phase_status`` fact; a phase (or
    run) that is not a field dict is skipped, never crashed on. Deterministic: the same
    ``ReducerInput`` yields byte-identical facts in input order.
    """
    facts: list[CanonicalFact] = []
    for item in inp.evidence:
        if not isinstance(item, EvidenceItem):
            continue
        run = as_dict(item.payload)
        if run is None:
            continue
        phases = run.get("phases") or []
        if not isinstance(phases, list):
            continue
        for phase in phases:
            if isinstance(phase, dict):
                facts.extend(_facts_for_phase(run, phase, inp))
    return facts
