"""CAP I3 — the ``policy_facts/v1`` reducer (declared L5).

Reads the *declared* L5 configuration — ``StopSpec.budget_usd`` / ``max_attempts`` and the model
pool — into ``policy``-abstraction facts at workload scope. Unlike every other reducer, its facts
are ``declared`` (POLICY/[P]): a budget ceiling or an allowed-model set is an authored constraint,
not a measurement, and the ``Authority`` ordering makes that load-bearing — policy outranks any
controller (§8.6, check C8).

The reducer is still pure (design §4.1): the caller resolves the spec configs and hands them in;
the reducer only maps ``config → declared facts``. The config projection is deliberately small
(``name`` + the three L5 fields) so the reducer does not drag the whole ``ExperimentSpec`` in.

Monotone tightening (§10.2 rule 4) is the read-time resolution of these facts — a descendant may
narrow an inherited constraint, never widen it: ``max_spend_usd``/``max_attempts`` resolve to the
``min`` over the ancestor chain, ``allowed_models`` to the ``intersection``. :func:`tighten`
implements that resolution as a pure helper, so the semantic is testable before the I4 Context
Compiler consumes it.
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
from agentic_dynamics.control.reducers._common import as_dict, encode_value

# ── Reducer declaration ─────────────────────────────────────────

VERSION = "policy_facts/v1"

_PRODUCES = ("allowed_models", "max_spend_usd", "max_attempts")

POLICY_FACTS_V1 = ReducerSpec(
    name="policy_facts",
    version=VERSION,
    level="policy",
    scope_type="workload",
    consumes=("spec",),  # the declared spec config (StopSpec + model pool)
    produces=_PRODUCES,
    determinism="pure",
)

#: A policy fact is a human/operator declaration — DECLARED (POLICY/[P]).
_EPISTEMIC_STATUS = "declared"
_AUTHORITY, _EVIDENCE_CLASS = EPISTEMIC_MAP[_EPISTEMIC_STATUS]


# ── Fact construction ───────────────────────────────────────────


def _fact(
    name: str,
    inp: ReducerInput,
    predicate: str,
    value: str,
) -> CanonicalFact:
    """Build one declared policy fact at workload scope ``name``."""
    spec = FACT_PREDICATES[predicate]
    fact = CanonicalFact(
        fact_entity_id=compute_fact_entity_id(
            repository_id=inp.repository_id,
            scope_type="workload",
            scope_id=name,
            predicate=predicate,
            subject_type="policy",
            subject_id=name,
        ),
        fact_id="",  # finalized at persistence — the record's knowledge_id IS the fact_id
        subject_type="policy",
        subject_id=name,
        predicate=predicate,
        value=value,
        value_type=spec.value_type,
        unit=spec.unit,
        scope_type="workload",
        scope_id=name,
        scope_path=f"org:{inp.repository_id}/workload:{name}",
        abstraction_level=spec.abstraction_level,
        epistemic_status=_EPISTEMIC_STATUS,
        authority=_AUTHORITY,
        evidence_class=_EVIDENCE_CLASS,
        observed_at=inp.now,
        valid_from=inp.now,
        valid_to=None,
        expires_at=None,
        reducer="policy_facts",
        reducer_version=VERSION,
        evidence_ids=(),  # declared, not reduced from evidence
        inputs_digest="",  # back-filled below from evidence_ids + reducer_version
        supersedes=None,  # the producer links a predecessor via the registry, not the reducer
        source_revision=inp.source_revision,
        repository_id=inp.repository_id,
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


# ── Per-config derivation ───────────────────────────────────────


def _facts_for_config(config: dict[str, Any], inp: ReducerInput) -> list[CanonicalFact]:
    """Emit the declared L5 facts one config pins, honouring absent-means-undeclared."""
    name = str(config.get("name") or "")
    if not name:
        return []
    facts: list[CanonicalFact] = []

    budget = config.get("budget_usd")
    if isinstance(budget, (int, float)) and budget >= 0:
        facts.append(_fact(name, inp, "max_spend_usd", encode_value(budget, "usd")))
    max_attempts = config.get("max_attempts")
    if isinstance(max_attempts, int) and max_attempts >= 0:
        facts.append(_fact(name, inp, "max_attempts", encode_value(max_attempts, "int")))
    pool = config.get("model_pool") or config.get("allowed_models")
    if isinstance(pool, (list, tuple)) and pool:
        facts.append(_fact(name, inp, "allowed_models", encode_value(list(pool), "enum-list")))
    return facts


# ── The reducer (pure) ──────────────────────────────────────────


def policy_facts_v1(inp: ReducerInput) -> list[CanonicalFact]:
    """Emit declared policy facts for every spec config in ``inp.evidence``.

    Pure and total: every config with a name and at least one declared L5 field yields facts; a
    nameless or empty config is skipped. Deterministic: the same ``ReducerInput`` yields
    byte-identical facts in input order.
    """
    facts: list[CanonicalFact] = []
    for item in inp.evidence:
        if not isinstance(item, EvidenceItem):
            continue
        config = as_dict(item.payload)
        if config is not None:
            facts.extend(_facts_for_config(config, inp))
    return facts


# ── Monotone tightening (§10.2 rule 4) ──────────────────────────


def tighten(candidates: list[CanonicalFact], predicate: str) -> str | None:
    """Resolve a set of same-predicate policy facts by monotone tightening.

    ``max_spend_usd``/``max_attempts`` resolve to the ``min`` over the ancestor chain;
    ``allowed_models`` to the ``intersection``. Returns the canonical STRING value, or ``None``
    when there is nothing to tighten (an empty candidate set, or an empty intersection). A
    descendant can never *widen* an inherited constraint — that is the whole point (§10.2.4).
    """
    if not candidates:
        return None
    if predicate == "allowed_models":
        sets = [set(f.value.split(",")) for f in candidates if f.value]
        if not sets:
            return None
        return encode_value(sorted(set.intersection(*sets)), "enum-list")
    numeric = [float(f.value) for f in candidates]
    if FACT_PREDICATES[predicate].value_type == "int":
        return encode_value(int(min(numeric)), "int")
    return encode_value(min(numeric), FACT_PREDICATES[predicate].value_type)
