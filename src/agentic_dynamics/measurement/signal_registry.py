"""The single registry of measured signals (refactor-repair Debt-3).

Before this module the vocabulary was split-brained: ``experiment_spec.py`` (the ledger) declared
``confidence`` measured [H], while ``control/step_routing.py`` (now ``runtime/routing.py``) and
``control/signal_store.py`` still described it as "unmeasured". A control rule whose ``requires``
are unmeasured is unwritable — so whether a signal is *measured* must be one fact, not two.

This module is that fact. Every signal is registered once with its full contract:

* ``name`` — the canonical signal name (the ledger / ``ModelSignals`` field).
* ``producer`` — what emits it (a module + symbol, or a derived formula).
* ``evidence_class`` — ``[M]`` measured / ``[C]`` computed / ``[H]`` heuristic / ``[P]`` policy.
* ``scope`` — the granularity the value is measured at (``attempt`` / ``model`` / ``job`` / …).
* ``value_type`` — ``float`` / ``bool`` / ``int`` / ``str``.
* ``measured`` — whether the ledger actually produces it.
* ``permitted_consumers`` — which policy/control consumers may consume it.
* ``freshness`` — how current a value is (``per-attempt`` / ``per-model aggregate`` / …).

It is deliberately a *leaf* module (imports only the stdlib) so both ``experiment`` and ``control``
can import it without a cycle. ``runtime/routing.py`` derives its measured/forbidden vocabulary
from it; ``experiment_spec.py``'s ``LEDGER_FIELDS`` is checked against it in the tests; the
reconciliation rule is: **a signal may be "reserved for another consumer", but never "unmeasured"
when the registry says measured.**
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Consumer labels ─────────────────────────────────────────────

#: The generic per-step model-routing policy (``route_step`` / ``validate_preferences``).
ROUTING = "routing"

#: The cascade/dynamics control arms (``model_cascade`` / ``dynamics``) that escalate on
#: measured confidence — the consumer ``confidence`` is *reserved* for.
CASCADE = "cascade"


@dataclass(frozen=True)
class Signal:
    """One measured signal and its full contract (refactor-repair Debt-3)."""

    name: str
    producer: str
    evidence_class: str
    scope: str
    value_type: str
    measured: bool
    permitted_consumers: frozenset[str]
    freshness: str


#: The registry, keyed by canonical signal name. The routing signals live alongside the four
#: formerly-missing measured signals (confidence, perturbation_strength, test_executed_success,
#: the answer/explanation token split) so the routing vocabulary and the ledger vocabulary can
#: never disagree again.
SIGNALS: dict[str, Signal] = {
    # ── routing signals (measured, consumed by the routing policy) ──
    "correctness": Signal(
        "correctness", "solution.py SolutionMetrics", "[M]", "model", "float",
        True, frozenset({ROUTING}), "per-model aggregate",
    ),
    "cost": Signal(
        "cost", "efficiency.py EfficiencyMetrics", "[M]", "model", "float",
        True, frozenset({ROUTING}), "per-model aggregate",
    ),
    "efficiency": Signal(
        "efficiency", "correctness / cost (derived)", "[C]", "model", "float",
        True, frozenset({ROUTING}), "per-model aggregate",
    ),
    "cache_hit_rate": Signal(
        "cache_hit_rate", "ledger tokens (cache read / input)", "[M]", "attempt", "float",
        True, frozenset({ROUTING}), "per-attempt",
    ),
    "constraint_score": Signal(
        "constraint_score", "solution.py SolutionMetrics", "[M]", "attempt", "float",
        True, frozenset({ROUTING}), "per-attempt",
    ),
    "code_quality_score": Signal(
        "code_quality_score", "solution.py SolutionMetrics", "[M]", "attempt", "float",
        True, frozenset({ROUTING}), "per-attempt",
    ),
    "novelty_score": Signal(
        "novelty_score", "solution.py SolutionMetrics", "[M]", "attempt", "float",
        True, frozenset({ROUTING}), "per-attempt",
    ),
    "composite_score": Signal(
        "composite_score", "solution.py SolutionMetrics", "[M]", "attempt", "float",
        True, frozenset({ROUTING}), "per-attempt",
    ),
    # ── not yet instrumented ──
    "edge_case_coverage": Signal(
        "edge_case_coverage", "(none — not yet instrumented)", "[M]", "attempt", "float",
        False, frozenset(), "not instrumented",
    ),
    # ── the formerly-missing measured signals (instrumentation step 3) ──
    "confidence": Signal(
        "confidence", "opencode.AgenticResult.confidence", "[H]", "attempt", "float",
        True, frozenset({CASCADE}), "per-attempt",
    ),
    "perturbation_strength": Signal(
        "perturbation_strength", "story/run ledger (strength axis, s=0.0 baseline)", "[M]",
        "attempt", "float", True, frozenset(), "per-attempt",
    ),
    "test_executed_success": Signal(
        "test_executed_success", "test_runner.run_suite (independent, not self-report)", "[M]",
        "attempt", "bool", True, frozenset(), "per-attempt",
    ),
    "tokens_answer": Signal(
        "tokens_answer", "ledger token split (tokens in steps that wrote files)", "[M]",
        "attempt", "int", True, frozenset(), "per-attempt",
    ),
    "tokens_explanation": Signal(
        "tokens_explanation", "ledger token split (tokens in prose-only steps)", "[M]",
        "attempt", "int", True, frozenset(), "per-attempt",
    ),
}


# ── Queries ─────────────────────────────────────────────────────


def get(name: str) -> Signal | None:
    """The :class:`Signal` for ``name``, or ``None`` if it is not registered."""
    return SIGNALS.get(name)


def is_measured(name: str) -> bool:
    """True when the registry marks ``name`` measured (the ledger produces it)."""
    sig = SIGNALS.get(name)
    return sig is not None and sig.measured


def is_permitted(name: str, consumer: str) -> bool:
    """True when ``name`` is measured *and* ``consumer`` may consume it."""
    sig = SIGNALS.get(name)
    return sig is not None and sig.measured and consumer in sig.permitted_consumers


def measured_signals() -> frozenset[str]:
    """Every signal the registry marks measured."""
    return frozenset(name for name, sig in SIGNALS.items() if sig.measured)


def signals_for(consumer: str) -> frozenset[str]:
    """Measured signals ``consumer`` is permitted to consume."""
    return frozenset(
        name for name, sig in SIGNALS.items() if sig.measured and consumer in sig.permitted_consumers
    )


def measured_but_not_permitted(consumer: str) -> frozenset[str]:
    """Measured signals ``consumer`` is NOT permitted to consume.

    Broad: includes signals with no control consumer at all (``perturbation_strength``,
    ``test_executed_success``, the token split — consumed by measurement rules, not policies).
    """
    return frozenset(
        name for name, sig in SIGNALS.items() if sig.measured and consumer not in sig.permitted_consumers
    )


def reserved_for_other(consumer: str) -> frozenset[str]:
    """Measured signals *reserved for a different* consumer than ``consumer``.

    Narrow: only signals that actually name another policy consumer (e.g. ``confidence`` is
    reserved for ``cascade``). This is the routing ``FORBIDDEN_SIGNALS`` set — signals the
    router must refuse with a *reservation* error, not an "unmeasured" one.
    """
    return frozenset(
        name
        for name, sig in SIGNALS.items()
        if sig.measured and sig.permitted_consumers and consumer not in sig.permitted_consumers
    )


def unmeasured_signals() -> frozenset[str]:
    """Every registered signal the registry marks not-yet-measured."""
    return frozenset(name for name, sig in SIGNALS.items() if not sig.measured)
