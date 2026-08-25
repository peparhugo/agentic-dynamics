"""Evidence-integrity e5 — the ``code_change_facts/v1`` reducer (design §5.6).

Derives the ten job-scoped code-change facts from the TYPED CodeDelta (e2) + analyzer statuses.
Minting-order guard (design §5.3): ``changed_symbol_count`` et al. are minted ONLY from the typed
CodeDelta — never from a regex diff-stat. The reducer is pure (design §4.1): no I/O, no RNG; the
caller resolves the delta, analyzer statuses, and the ACL-scoped impacted set and hands them over
as ``EvidenceItem`` payloads.

Evidence contract (``ReducerSpec.consumes``):

* ``code_delta``        — payload is a :class:`~agentic_dynamics.core.language.CodeDelta`.
* ``sonar_analysis``    — payload dict ``{"status", "revision_matches"|None,
  "new_critical_count"|None, "analyzed_sha"}``.
* ``lsp_analysis``      — payload dict ``{"status", "new_error_count"|None, "tool"}``.
* ``impacted_symbols``  — payload dict ``{"count"|None}`` (the 1-2 hop reachable set, bounded by
  the same ACL-scoped expansion, computed by the caller).

SEMANTICS (hard rule 6 + design §5.6, DEFINED here — not delegated to the docstring):

* ``analysis_revision_matches`` — bool; OMITTED when the sonar analysis did not run.
* ``ast_parse_coverage`` — ``parsed_changed_files / changed_files`` where changed_files =
  ``delta.changed_files + delta.added_files``; OMITTED when changed_files == 0 (no denominator).
* ``lsp_analysis_status`` / ``sonar_analysis_status`` — the measured enum
  (``available``/``unavailable``/``stale-refused``), emitted whenever the status is known.
* ``changed_symbol_count`` — from the typed CodeDelta only (minting-order guard).
* ``impacted_symbol_count`` — from the caller's ACL-scoped 1-2 hop set; OMITTED when absent.
* ``new_lsp_error_count`` / ``new_sonar_critical_count`` — OMITTED when the analyzer did not run
  (null-not-zero, never fabricated zeroes).
* ``changed_symbols_with_tests_ratio`` — ``tested_changed_symbols / changed_symbols`` where
  ``tested_changed_symbols`` follows the TESTED_BY rule (test-file→module name matching, §5.4);
  OMITTED when changed_symbols == 0 OR the rule links no changed symbol (DEFERRED — never 0).
* ``code_change_risk`` — v1 formula:
  ``risk = 0.35·min(1, new_sonar_critical/10) + 0.25·min(1, new_lsp_error/10)
          + 0.20·(1 − tests_ratio) + 0.20·min(1, impacted/10)``;
  terms whose analyzer did not run OR whose ratio is deferred are OMITTED and the remaining
  weights RENORMALIZED to sum 1; risk is None (fact omitted) when NO term is measurable. The
  weights are ``[P]`` operator policy — this provenance is the record; a weight change is a
  reducer-version change.
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
    cell_id,
    encode_value,
)
from agentic_dynamics.core.language import (
    tested_symbols as _tested_symbols,
)

# ── Reducer declaration ─────────────────────────────────────────

VERSION = "code_change_facts/v1"

#: The ten code-change predicates this reducer emits. Every name exists in FACT_PREDICATES.
CODE_CHANGE_PREDICATES = (
    "analysis_revision_matches",
    "ast_parse_coverage",
    "lsp_analysis_status",
    "sonar_analysis_status",
    "changed_symbol_count",
    "impacted_symbol_count",
    "new_lsp_error_count",
    "new_sonar_critical_count",
    "changed_symbols_with_tests_ratio",
    "code_change_risk",
)

CODE_CHANGE_FACTS_V1 = ReducerSpec(
    name="code_change_facts",
    version=VERSION,
    level="fact",
    scope_type="job",
    consumes=("code_delta", "sonar_analysis", "lsp_analysis", "impacted_symbols"),
    produces=CODE_CHANGE_PREDICATES,
    determinism="pure",
)

#: Every code-change fact is derived — COMPUTED by a deterministic reducer from measured
#: evidence — so it is DERIVED ([C]) by the §3.4 epistemic map.
_EPISTEMIC_STATUS = "derived"
_AUTHORITY, _EVIDENCE_CLASS = EPISTEMIC_MAP[_EPISTEMIC_STATUS]

#: The ``code_change_risk`` v1 weights — ``[P]`` operator policy. Provenance: this tuple IS the
#: record; the formula is ``sum(w·term)/sum(w)`` over the MEASURABLE terms, renormalized to 1
#: (a term whose analyzer did not run or whose ratio is deferred is omitted).
RISK_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("new_sonar_critical", 0.35),
    ("new_lsp_error", 0.25),
    ("tests_ratio", 0.20),
    ("impacted", 0.20),
)


# ── Small pure helpers ──────────────────────────────────────────


def _evidence(inp: ReducerInput, source_type: str) -> EvidenceItem | None:
    """The first evidence item of ``source_type``, or None."""
    for item in inp.evidence:
        if item.source_type == source_type:
            return item
    return None


def _payload_dict(item: EvidenceItem | None) -> dict[str, Any] | None:
    if item is None or not isinstance(item.payload, dict):
        return None
    return item.payload


def _fact(inp: ReducerInput, predicate: str, value: str, evidence_ids: tuple[str, ...]) -> CanonicalFact:
    """Build one job-scoped derived fact for ``predicate``."""
    spec = FACT_PREDICATES[predicate]
    job_id = inp.scope_id or cell_id("unknown", "unknown")
    observed_at = inp.now
    fact = CanonicalFact(
        fact_entity_id=compute_fact_entity_id(
            repository_id=inp.repository_id,
            scope_type="job",
            scope_id=job_id,
            predicate=predicate,
            subject_type="job",
            subject_id=job_id,
        ),
        fact_id="",  # finalized at persistence — the record's knowledge_id IS the fact_id
        subject_type="job",
        subject_id=job_id,
        predicate=predicate,
        value=value,
        value_type=spec.value_type,
        unit=spec.unit,
        scope_type="job",
        scope_id=job_id,
        scope_path=inp.scope_path or f"org:{inp.repository_id}/job:{job_id}",
        abstraction_level=spec.abstraction_level,
        epistemic_status=_EPISTEMIC_STATUS,
        authority=_AUTHORITY,
        evidence_class=_EVIDENCE_CLASS,
        observed_at=observed_at,
        valid_from=observed_at,
        valid_to=None,
        expires_at=None,
        reducer="code_change_facts",
        reducer_version=VERSION,
        evidence_ids=evidence_ids,
        inputs_digest="",  # back-filled below
        supersedes=None,
        source_revision=inp.source_revision or REVISION_FALLBACK,
        repository_id=inp.repository_id,
    )
    return replace(fact, inputs_digest=recompute_inputs_digest(fact))


def _changed_symbol_names(delta) -> tuple[set[str], set[str]]:
    """The after-state and before-state qualified names of the delta's changed symbols."""
    after = {s.qualified_name for s in delta.added_symbols} | {
        s.qualified_name for s in delta.changed_symbols
    }
    before = {s.qualified_name for s in delta.removed_symbols}
    return after, before


# ── The reducer (pure) ──────────────────────────────────────────


def code_change_facts_v1(inp: ReducerInput) -> list[CanonicalFact]:
    """Derive the ten job-scoped code-change facts from the typed CodeDelta + analyzer statuses.

    Pure and total: an absent evidence family simply omits the facts that depend on it (never a
    fabricated zero, never a crash). Deterministic: the same ``ReducerInput`` yields byte-identical
    facts in a fixed order.
    """
    facts: list[CanonicalFact] = []
    evidence_ids: tuple[str, ...] = tuple(
        item.evidence_id for item in inp.evidence if item.evidence_id
    )

    delta_item = _evidence(inp, "code_delta")
    delta = delta_item.payload if delta_item is not None else None
    sonar = _payload_dict(_evidence(inp, "sonar_analysis"))
    lsp = _payload_dict(_evidence(inp, "lsp_analysis"))
    impacted = _payload_dict(_evidence(inp, "impacted_symbols"))

    # ── Status facts (the measured enums; emitted whenever the status is known) ──
    if sonar is not None and sonar.get("status"):
        facts.append(
            _fact(inp, "sonar_analysis_status", encode_value(sonar["status"], "enum"), evidence_ids)
        )
    if lsp is not None and lsp.get("status"):
        facts.append(
            _fact(inp, "lsp_analysis_status", encode_value(lsp["status"], "enum"), evidence_ids)
        )

    # ── analysis_revision_matches — OMITTED when the analysis did not run ──
    if sonar is not None:
        matches = sonar.get("revision_matches")
        if matches is not None:
            facts.append(
                _fact(inp, "analysis_revision_matches", encode_value(matches, "bool"), evidence_ids)
            )

    # ── ast_parse_coverage — parsed_changed_files / changed_files; omitted when 0 ──
    if delta is not None:
        changed_files = sorted(set(delta.changed_files) | set(delta.added_files))
        if changed_files:
            parsed = [f for f in changed_files if f in delta.after.files]
            coverage = len(parsed) / len(changed_files)
            facts.append(
                _fact(inp, "ast_parse_coverage", encode_value(coverage, "float"), evidence_ids)
            )

    # ── changed_symbol_count — minted ONLY from the typed CodeDelta (minting-order guard) ──
    if delta is not None:
        facts.append(
            _fact(
                inp,
                "changed_symbol_count",
                encode_value(delta.changed_symbol_count, "int"),
                evidence_ids,
            )
        )

    # ── impacted_symbol_count — the caller's ACL-scoped 1-2 hop set; omitted when absent ──
    if impacted is not None and isinstance(impacted.get("count"), int):
        facts.append(
            _fact(inp, "impacted_symbol_count", encode_value(impacted["count"], "int"), evidence_ids)
        )

    # ── new_lsp_error_count / new_sonar_critical_count — omitted when the analyzer did not run ──
    if lsp is not None and isinstance(lsp.get("new_error_count"), int):
        facts.append(
            _fact(inp, "new_lsp_error_count", encode_value(lsp["new_error_count"], "int"), evidence_ids)
        )
    if sonar is not None and isinstance(sonar.get("new_critical_count"), int):
        facts.append(
            _fact(
                inp, "new_sonar_critical_count", encode_value(sonar["new_critical_count"], "int"),
                evidence_ids,
            )
        )

    # ── changed_symbols_with_tests_ratio — DEFERRED (omitted) when not derivable ──
    tests_ratio: float | None = None
    if delta is not None and delta.changed_symbol_count > 0:
        after_tested = _tested_symbols(delta.after) if delta.after else set()
        before_tested = _tested_symbols(delta.before) if delta.before else set()
        after_names, before_names = _changed_symbol_names(delta)
        tested_changed = len((after_names & after_tested) | (before_names & before_tested))
        if tested_changed > 0:
            tests_ratio = tested_changed / delta.changed_symbol_count
            facts.append(
                _fact(
                    inp, "changed_symbols_with_tests_ratio",
                    encode_value(tests_ratio, "float"), evidence_ids,
                )
            )

    # ── code_change_risk — the [P]-weighted v1 formula, renormalized over measurable terms ──
    terms: list[float] = []
    weights: list[float] = []
    if sonar is not None and isinstance(sonar.get("new_critical_count"), int):
        terms.append(min(1.0, sonar["new_critical_count"] / 10.0))
        weights.append(dict(RISK_WEIGHTS)["new_sonar_critical"])
    if lsp is not None and isinstance(lsp.get("new_error_count"), int):
        terms.append(min(1.0, lsp["new_error_count"] / 10.0))
        weights.append(dict(RISK_WEIGHTS)["new_lsp_error"])
    if tests_ratio is not None:
        terms.append(1.0 - tests_ratio)
        weights.append(dict(RISK_WEIGHTS)["tests_ratio"])
    if impacted is not None and isinstance(impacted.get("count"), int):
        terms.append(min(1.0, impacted["count"] / 10.0))
        weights.append(dict(RISK_WEIGHTS)["impacted"])
    if terms:
        risk = sum(w * t for w, t in zip(weights, terms)) / sum(weights)
        facts.append(
            _fact(inp, "code_change_risk", encode_value(round(risk, 4), "float"), evidence_ids)
        )

    return facts
