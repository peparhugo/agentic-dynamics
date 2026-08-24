"""CAP addendum I9 — the ``pattern/v1`` reducer (design §3, D7).

Compresses measured campaign experience into citable ``pattern`` facts. Per the accepted
addendum design (`docs/designs/current/context_abstraction_addendum_design.md` §3.3), this is
the SOLE registered producer of the ``pattern`` predicate (``FACT_PREDICATES["pattern"].
produced_by == ("pattern/v1",)``) — hard rule 3 ("only a registered deterministic reducer mints
a canonical fact") made concrete for this class, and the reason ``verify_chain`` (not
``is_canonical`` alone) is mandatory before a ``pattern`` fact may enter a snapshot (design D3).

**Input door — the canonical corpus, never the retired summary.** ``PATTERN_V1.consumes``
names the canonical-corpus tables (``canonical_corpus.TABLES``, review constraint 4): ``finding``
carries the structured ``test_executed_success``/``confidence``/``perturbation_strength`` fields
a pattern needs (design §3.3); ``review``/``analysis`` rows do not, so a v1 pattern is mined only
from ``finding`` evidence — accepting (never crashing on) ``review``/``analysis`` items handed
in, exactly the same "nothing to compute over -> skip, never fabricate" posture the coverage
invariant already requires for an empty slice.

**The population slice.** Findings are grouped by ``(task, perturbation_class)`` — ``task`` is
the finding's parent experiment name (``row["_experiment"]``,
``canonical_corpus.resolve_findings``), ``perturbation_class`` is the operator family
(``process_perturbation`` / ``specification_corruption`` / ``objective_mutation`` / ...). A row
missing either key cannot be addressed to a slice and is skipped, never guessed.

**The coverage invariant, applied twice (design §3.3, REUSE ``measurement_coverage.py:20-21``):**
(a) an empty slice — zero finding rows — emits NO fact, never a ``support=0`` fact (a different
claim than "zero successes"); (b) a row whose ``test_executed_success`` is not a real ``bool``
(unmeasured) is excluded from the slice entirely, never coerced into a "non-match" that would
silently dilute the observed rate — the same null-is-not-zero rule ``MeasurementCoverage``
enforces for cost/quality averages, applied here to a proportion's population.

**Determinism (design §4.1, restated because it is load-bearing for a citable fact):** no wall
clock read (``inp.now`` only), a total function (no group ever raises), and duplicate input rows
(the SAME finding record handed in twice — an upstream artifact or caller bug) are deduped by
their lab-contract ref before counting, mirroring ``workflow_facts_v1``'s own r4 defense against
double-counting a duplicated artifact.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from typing import Any

from agentic_dynamics.control.facts import (
    EPISTEMIC_MAP,
    FACT_PREDICATES,
    CanonicalFact,
    EvidenceItem,
    PatternPayload,
    ReducerInput,
    ReducerSpec,
    compute_fact_entity_id,
    recompute_inputs_digest,
)
from agentic_dynamics.control.reducers._common import REVISION_FALLBACK
from agentic_dynamics.reporting.lab_contract import record_id

# ── Reducer declaration ─────────────────────────────────────────

VERSION = "pattern/v1"

_PRODUCES = ("pattern",)

PATTERN_V1 = ReducerSpec(
    name="pattern",
    version=VERSION,
    level="workload",
    scope_type="workload",
    # The CANONICAL CORPUS tables (canonical_corpus.TABLES), NOT the retired
    # _results_summary.json (review constraint 4) — see the module docstring for which of the
    # three this v1 implementation actually mines.
    consumes=("finding", "review", "analysis"),
    produces=_PRODUCES,
    determinism="pure_with_injected_clock",
)

#: A pattern is a compressed abstraction over measured evidence, computed by a deterministic
#: reducer — DERIVED/[C] (design §3.1). No new EPISTEMIC_MAP row (D7): this reuses the existing
#: "derived" row verbatim.
_EPISTEMIC_STATUS = "derived"
_AUTHORITY, _EVIDENCE_CLASS = EPISTEMIC_MAP[_EPISTEMIC_STATUS]

#: The minimum number of real, measured records a slice must carry before `uncertainty` is
#: estimable (design §3.3: "None when the slice is too small to estimate"). Matches the
#: addendum's own evidence-seed experiment's repetition floor (design §4.4/F5's fix: "3
#: attempts/cell -> the uncertainty term is estimable") — the same minimum, for the same reason.
MIN_SUPPORT_FOR_UNCERTAINTY = 3

#: The matching predicate every v1 pattern claim tests for (design §3.3's `conditions` field —
#: what a record must satisfy to count toward `support`). One condition today; a future
#: increment that mines a different claim shape adds to this, it never overloads this one.
_MATCH_CONDITIONS: tuple[str, ...] = ("test_executed_success=true",)


# ── Population slicing (pure) ───────────────────────────────────


def _slug(value: str) -> str:
    """Sanitize one slice-key segment for use inside a ``/``-joined identity string.

    Mirrors ``_common.cell_id``'s own non-alnum -> ``_`` sanitization verbatim (same rationale:
    a raw ``/`` inside ``task`` or ``perturbation_class`` would otherwise let two DIFFERENT
    slices collide on the same ``fact_entity_id`` — the same defensive posture the existing
    per-cell identity helper already takes for spec name + model)."""
    return "".join(ch if ch.isalnum() else "_" for ch in value)


def _population_key(row: dict[str, Any]) -> tuple[str, str]:
    """The ``(task, perturbation_class)`` slice a finding row belongs to, or ``("", "")`` when
    either axis is unaddressable (the row is then skipped by the caller, never guessed)."""
    return str(row.get("_experiment") or ""), str(row.get("perturbation_class") or "")


def _population_label(task: str, perturbation_class: str) -> str:
    """The human-readable, reproducible slice descriptor (design §3.3's `population` field)."""
    return f"finding:task={task},perturbation_class={perturbation_class}"


def _claim(perturbation_class: str) -> str:
    """The compressed abstraction name for a slice (design §3.2's `claim` field)."""
    return f"recovers_under_{perturbation_class}"


def _is_measured_outcome(row: dict[str, Any]) -> bool:
    """True when ``row`` carries a REAL measured ``test_executed_success`` (a ``bool``, not
    ``None``/absent) — the coverage-invariant filter (b) from the module docstring."""
    return isinstance(row.get("test_executed_success"), bool)


def _matches(row: dict[str, Any]) -> bool:
    """True when ``row`` satisfies :data:`_MATCH_CONDITIONS` — only called on rows that already
    passed :func:`_is_measured_outcome`, so this is a plain equality check, never a coercion."""
    return row.get("test_executed_success") is True


# ── The Wilson interval (the deterministic `uncertainty` statistic) ─


def _wilson_interval_width(successes: int, total: int, *, z: float = 1.959963984540054) -> float:
    """The width of the 95% Wilson score interval for a binomial proportion.

    Chosen over the naive normal approximation because it stays well-behaved at the small ``n``
    a campaign slice realistically has (design §3.3 explicitly anticipates "too small to
    estimate" as the common case) and never produces a bound outside ``[0, 1]``. ``z`` is the
    97.5th percentile of the standard normal (a 95% two-sided interval) — a fixed constant, not
    a measured value, so it introduces no non-determinism.
    """
    p = successes / total
    denom = 1 + (z * z) / total
    center = (p + (z * z) / (2 * total)) / denom
    margin = (z / denom) * math.sqrt((p * (1 - p) / total) + (z * z) / (4 * total * total))
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return upper - lower


# ── Payload <-> JSON (payload-in-value, design §3.2) ────────────


def _payload_to_json(payload: PatternPayload) -> str:
    """The canonical (sorted-key) JSON encoding of a `PatternPayload` — deterministic, so the
    same payload always renders to the same bytes and `fact_id` stays reproducible."""
    return json.dumps(
        {
            "claim": payload.claim,
            "population": payload.population,
            "conditions": list(payload.conditions),
            "support": payload.support,
            "uncertainty": payload.uncertainty,
            "validity_window": payload.validity_window,
            "source_experiment": payload.source_experiment,
        },
        sort_keys=True,
    )


def decode_pattern_payload(value: str) -> PatternPayload:
    """Inverse of :func:`_payload_to_json` — the one place a consumer decodes a ``pattern``
    fact's ``value`` back into a typed :class:`PatternPayload`, so no second ad hoc JSON schema
    for this predicate grows elsewhere in the plane."""
    data = json.loads(value)
    uncertainty = data.get("uncertainty")
    return PatternPayload(
        claim=str(data["claim"]),
        population=str(data["population"]),
        conditions=tuple(data.get("conditions") or ()),
        support=int(data["support"]),
        uncertainty=None if uncertainty is None else float(uncertainty),
        validity_window=str(data["validity_window"]),
        source_experiment=str(data["source_experiment"]),
    )


# ── Fact construction ───────────────────────────────────────────


def _fact_for_group(
    rows: list[dict[str, Any]],
    task: str,
    perturbation_class: str,
    inp: ReducerInput,
) -> CanonicalFact | None:
    """Build one ``pattern`` fact for a ``(task, perturbation_class)`` slice, or ``None`` when
    the slice has no real support — the coverage invariant's fabrication boundary (§3.3)."""
    if not rows:
        return None
    # r4-style dedup (workflow_facts_v1's own precedent): the SAME finding record handed in
    # twice must never double-count. Keyed by the lab-contract ref, first occurrence wins.
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        deduped.setdefault(record_id(row), row)
    if not deduped:
        return None

    refs = sorted(deduped)
    support = sum(1 for row in deduped.values() if _matches(row))
    total = len(deduped)
    uncertainty = (
        _wilson_interval_width(support, total) if total >= MIN_SUPPORT_FOR_UNCERTAINTY else None
    )

    payload = PatternPayload(
        claim=_claim(perturbation_class),
        population=_population_label(task, perturbation_class),
        conditions=_MATCH_CONDITIONS,
        support=support,
        uncertainty=uncertainty,
        validity_window=inp.source_revision or REVISION_FALLBACK,
        source_experiment=refs[0],  # deterministic: lexicographically smallest ref
    )

    subject_id = f"pattern/{_slug(task)}/{_slug(perturbation_class)}"
    spec = FACT_PREDICATES["pattern"]
    fact = CanonicalFact(
        fact_entity_id=compute_fact_entity_id(
            repository_id=inp.repository_id,
            scope_type="workload",
            scope_id=subject_id,
            predicate="pattern",
            subject_type="workload",
            subject_id=subject_id,
        ),
        fact_id="",  # finalized at persistence — the record's knowledge_id IS the fact_id
        subject_type="workload",
        subject_id=subject_id,
        predicate="pattern",
        value=_payload_to_json(payload),
        value_type=spec.value_type,
        unit=spec.unit,
        scope_type="workload",
        scope_id=subject_id,
        scope_path=f"org:{inp.repository_id}/workload:{subject_id}",
        abstraction_level=spec.abstraction_level,
        epistemic_status=_EPISTEMIC_STATUS,
        authority=_AUTHORITY,
        evidence_class=_EVIDENCE_CLASS,
        observed_at=inp.now,
        valid_from=inp.now,
        valid_to=None,
        expires_at=None,
        reducer="pattern",
        reducer_version=VERSION,
        evidence_ids=tuple(refs),
        inputs_digest="",  # back-filled below from evidence_ids + reducer_version
        supersedes=None,  # the producer links a predecessor via the registry, not the reducer
        source_revision=inp.source_revision or REVISION_FALLBACK,
        repository_id=inp.repository_id,
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


# ── The reducer (pure) ──────────────────────────────────────────


def pattern_v1(inp: ReducerInput) -> list[CanonicalFact]:
    """Emit ``pattern`` facts from measured ``finding`` records in ``inp.evidence``.

    Pure and total (design §4.1): groups measured-outcome finding rows by
    ``(task, perturbation_class)``, emits one fact per NON-EMPTY group, in a stable
    (sorted-key) order so the same evidence set always yields byte-identical facts regardless
    of input order — the re-derivation stability the design's citability claim depends on.
    ``review``/``analysis`` evidence items and rows with an unaddressable slice or an
    unmeasured outcome are skipped, never guessed at.
    """
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in inp.evidence:
        if not isinstance(item, EvidenceItem) or item.source_type != "finding":
            continue
        row = item.payload
        if not isinstance(row, dict) or not _is_measured_outcome(row):
            continue
        key = _population_key(row)
        if not key[0] or not key[1]:
            continue
        groups.setdefault(key, []).append(row)

    facts: list[CanonicalFact] = []
    for task, perturbation_class in sorted(groups):
        fact = _fact_for_group(groups[(task, perturbation_class)], task, perturbation_class, inp)
        if fact is not None:
            facts.append(fact)
    return facts
