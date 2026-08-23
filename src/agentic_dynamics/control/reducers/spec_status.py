"""CAP I1 — the first reducer: ``spec_status/v1``.

Derives canonical spec-status facts from the spec-lifecycle index
(``agentic_dynamics.experiment.spec_status``'s ``SpecStatusEntry``, the machine schema the
``experiments/specs/index.json`` artifact carries). It is the design's §9 I1 reducer and the
shape every later reducer copies: a **pure function** — no I/O, no RNG, an injected clock and
revision — so it is trivially unit-testable and replayable against historical evidence
(design §4.1, copied from ``step_routing``'s pure-function contract).

The reducer consumes the *derived index* (not the individual spec YAMLs or run ledgers): that
join already happened in ``spec_status.collect_entries``, and re-deriving it here would give the
fact plane a second, drift-prone opinion about what "done" means. The caller resolves inputs and
persists outputs; the reducer only maps ``index entry → facts``.

One fact per ``(spec, predicate)`` that carries a value. The two always-known predicates
(``spec_status``, ``spec_n_runs``) are emitted for every spec; the measured run-derived predicates
(``spec_last_run_at`` / ``spec_latest_ok`` / ``spec_latest_model`` / ``spec_latest_cost_usd``) and
the supersession predicates (``spec_superseded_by`` / ``spec_supersedes``) are emitted only when
they actually have a value — an unmeasured field is *absent* (the Context Compiler later reads
"no fact" as ``unknown``), never a fabricated ``0``/``false``/``""`` (the closure's
measurement-coverage primitive, Addendum A.5). ``evidence_ids`` is empty: the reducer consumes the
derived index directly, not individual knowledge records, so there are no ``knowledge_id``s to
cite — the derivation is anchored by ``source_revision`` (git HEAD, folded into ``fact_id``) and
by the fact's own supersession chain.

``fact_id`` is emitted empty and finalized at persistence: it folds the record's ``content_hash``
(design §3.3), which only ``fact_ingestion.build_fact_record`` computes — the record's
``knowledge_id`` *is* the fact's ``fact_id``.
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

# ── Reducer declaration ─────────────────────────────────────────

#: The reducer version string — the one folded into every ``fact_id`` (design §3.1).
VERSION = "spec_status/v1"

#: The predicate this reducer emits into. Every name must exist in ``FACT_PREDICATES`` (the
#: ``produced_by`` invariant that makes "declared but written by nothing" unrepresentable).
_PRODUCES = (
    "spec_status",
    "spec_superseded_by",
    "spec_supersedes",
    "spec_last_run_at",
    "spec_latest_ok",
    "spec_latest_model",
    "spec_latest_cost_usd",
    "spec_n_runs",
)

#: The declarative reducer spec, registered in ``control.reducers.REDUCERS``.
SPEC_STATUS_V1 = ReducerSpec(
    name="spec_status",
    version=VERSION,
    level="fact",
    scope_type="workload",
    consumes=("spec",),  # the spec-lifecycle source (SpecStatusEntry)
    produces=_PRODUCES,
    determinism="pure",
)

#: Every fact this reducer mints is "derived" — computed by a deterministic versioned reducer
#: from evidence (design §3.4). authority/evidence_class are DERIVED from that, never chosen.
_EPISTEMIC_STATUS = "derived"
_AUTHORITY, _EVIDENCE_CLASS = EPISTEMIC_MAP[_EPISTEMIC_STATUS]


# ── Value encoding (canonical STRING, typed by ``value_type``) ──


def _encode(value: Any, value_type: str) -> str:
    """Encode one measured value into its canonical STRING form (design §3.1).

    Deterministic by construction: the same value always renders to the same string, which is
    what keeps ``fact_id`` (via the hashed payload) reproducible across re-derivations.
    """
    if value_type == "bool":
        return "true" if value else "false"
    if value_type == "int":
        return str(int(value))
    if value_type in ("float", "usd"):
        return str(value)  # str(float) is the shortest round-trip form; deterministic
    if value_type == "enum-list":
        return ",".join(str(v) for v in value)
    return str(value)  # str | enum | timestamp


# ── The reducer (pure) ──────────────────────────────────────────


def _as_entry(payload: Any) -> dict[str, Any] | None:
    """Coerce one evidence payload into a plain field dict (accepts a dict or a
    ``to_dict()``-carrying object such as ``SpecStatusEntry``)."""
    if isinstance(payload, dict):
        return payload
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        coerced = to_dict()
        return coerced if isinstance(coerced, dict) else None
    return None


def _fact(
    entry: dict[str, Any],
    inp: ReducerInput,
    predicate: str,
    value: str,
) -> CanonicalFact:
    """Build one scoped fact for ``predicate`` at scope ``workload:<spec-name>`` (design §10)."""
    name = str(entry["name"])
    spec = FACT_PREDICATES[predicate]
    # The underlying evidence was the spec's latest run when one exists; a never-run spec has
    # no measurement moment, so the injected derivation clock stands in (never a fabricated run).
    observed_at = str(entry.get("last_run_at") or inp.now)
    fact = CanonicalFact(
        fact_entity_id=compute_fact_entity_id(
            repository_id=inp.repository_id,
            scope_type="workload",
            scope_id=name,
            predicate=predicate,
            subject_type="spec",
            subject_id=name,
        ),
        fact_id="",  # finalized at persistence — the record's knowledge_id IS the fact_id
        subject_type="spec",
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
        observed_at=observed_at,
        valid_from=observed_at,
        valid_to=None,
        expires_at=None,
        reducer=SPEC_STATUS_V1.name,
        reducer_version=VERSION,
        evidence_ids=(),  # consumes the derived index, not individual knowledge records
        inputs_digest="",  # back-filled below from evidence_ids + reducer_version
        supersedes=None,  # the producer links a predecessor via the registry, not the reducer
        source_revision=inp.source_revision,
        repository_id=inp.repository_id,
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


def _facts_for_entry(entry: dict[str, Any], inp: ReducerInput) -> list[CanonicalFact]:
    """Emit the facts one index entry pins, honouring measured-or-absent semantics."""
    name = str(entry.get("name") or "")
    if not name:
        return []
    facts: list[CanonicalFact] = [
        # Always known: the derived lifecycle status and the run count (0 = never run).
        _fact(entry, inp, "spec_status", _encode(entry.get("status", ""), "enum")),
        _fact(entry, inp, "spec_n_runs", _encode(int(entry.get("n_runs", 0)), "int")),
    ]
    # Supersession — emitted only when a successor/predecessor actually exists (absence means
    # "no successor"/"replaces nothing", which is NOT the same as "unknown").
    if entry.get("superseded_by"):
        facts.append(
            _fact(entry, inp, "spec_superseded_by", _encode(entry["superseded_by"], "str"))
        )
    supersedes = entry.get("supersedes") or []
    if supersedes:
        facts.append(_fact(entry, inp, "spec_supersedes", _encode(supersedes, "enum-list")))
    # Measured run-derived fields — emitted only when measured, never fabricated.
    if entry.get("last_run_at"):
        facts.append(
            _fact(entry, inp, "spec_last_run_at", _encode(entry["last_run_at"], "timestamp"))
        )
    if isinstance(entry.get("latest_ok"), bool):
        facts.append(_fact(entry, inp, "spec_latest_ok", _encode(entry["latest_ok"], "bool")))
    if entry.get("latest_model"):
        facts.append(_fact(entry, inp, "spec_latest_model", _encode(entry["latest_model"], "str")))
    if entry.get("latest_cost_usd") is not None:
        facts.append(
            _fact(
                entry,
                inp,
                "spec_latest_cost_usd",
                _encode(entry["latest_cost_usd"], "usd"),
            )
        )
    return facts


def spec_status_v1(inp: ReducerInput) -> list[CanonicalFact]:
    """Emit canonical spec-status facts for every index entry in ``inp.evidence``.

    Pure and total: every entry yields at least the two always-known facts (or is silently
    skipped when it has no name), every emitted fact carries a value, and an unmeasured field is
    absent rather than defaulted. Deterministic: the same ``ReducerInput`` yields byte-identical
    facts, in input order.
    """
    facts: list[CanonicalFact] = []
    for item in inp.evidence:
        if not isinstance(item, EvidenceItem):
            continue
        entry = _as_entry(item.payload)
        if entry is None:
            continue
        facts.extend(_facts_for_entry(entry, inp))
    return facts
