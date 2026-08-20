"""Per-step model routing — the *policy* half of the routing split (refactor-repair Debt-2).

Implements ``docs/routing_design.md``: an intelligent, preference-driven router that
selects a model per workflow step (phase), honoring three selection semantics
(pin / ``allowed_models`` subset / full pool), scoring candidates over *measured*
experiment signals, and pricing the cache-prefix loss that a model switch incurs
(see ``workflow_runner.run_workflow``, which forks each step off the prior session when the
model is unchanged).

The routing *contract* (data model, validation mechanics, and the ``Router`` protocol) lives in
``runtime.routing``; this module is only the *decision* — the pure ``route_step`` policy. It is
injected into ``run_workflow`` at the composition root (``scripts/run_workflow.py``), so
``runtime`` depends on the protocol rather than on ``control``. The moved names are re-exported
below so existing control-side importers (``signal_store``) and the CLI keep their import paths.

Design decisions, per ``docs/routing_design.md``:

- **Three-step semantics** (§1): ``model`` pins exactly one model (returned verbatim);
  ``allowed_models`` restricts the eligible set to a subset; neither draws from the full
  pool. The choice is the argmax of a preference score — never random, never first-element.
- **Preference scoring** (§3): objectives are weighted signals, normalized per-step over the
  eligible set (min-max, direction-aware), summed and re-normalized. Missing signals drop
  their objective; zero-variance signals contribute 0.5.
- **Cache-aware trade-off** (§4): a candidate whose model differs from the prior step's pays
  the re-read cost of the shared prefix (``PROVIDER_PRICING`` input vs cache_read spread),
  folded into the ``cost`` signal so "lowest cost" naturally punishes churn.
- **Load-bearing rule** (§5): only measured signals may be consumed. ``confidence`` is
  forbidden; ``edge_case_coverage`` is gated behind a measurement rule that ``produces`` it.
"""

from __future__ import annotations

from typing import Any

from agentic_dynamics.measurement.efficiency import get_pricing
from agentic_dynamics.runtime.routing import (
    FORBIDDEN_SIGNALS,
    MEASURED_SIGNALS,
    SIGNAL_FIELDS,
    ModelSignals,
    Objective,
    RouteState,
    RoutingPreferences,
    StepSelector,
    parse_step_selector,
    resolve_pool,
    validate_preferences,
    validate_step_selector,
    validate_workflow_routing,
)

# Re-export the contract so control-side importers (``signal_store``) and the CLI keep their
# import paths unchanged. The moved names live in ``runtime.routing``; this re-export is a
# backward-compat shim, not a second home for the contract.
__all__ = [
    "FORBIDDEN_SIGNALS",
    "MEASURED_SIGNALS",
    "SIGNAL_FIELDS",
    "ModelSignals",
    "Objective",
    "RouteState",
    "RoutingPreferences",
    "StepSelector",
    "parse_step_selector",
    "resolve_pool",
    "validate_preferences",
    "validate_step_selector",
    "validate_workflow_routing",
    "route_step",
    "cache_switch_penalty",
]

# ── Cache-aware switch penalty ──────────────────────────────────


def cache_switch_penalty(prev_model: str, prev_cache_read_tokens: int) -> float:
    """Cost (USD) of breaking the prior step's cache prefix by switching model.

    Re-reads the shared prefix at ``input`` instead of ``cache_read`` rates, using the *prior*
    provider's ``PROVIDER_PRICING`` spread (``efficiency.py``) — the savings forgone by not
    staying on ``prev_model``. Returns 0.0 when there is no prior model, no cache reads, or the
    provider is unknown.
    """
    if not prev_model or prev_cache_read_tokens <= 0:
        return 0.0
    provider, _, model_id = prev_model.partition("/")
    provider = provider or prev_model
    try:
        pricing = get_pricing(provider, model_id)
    except ValueError:
        return 0.0
    spread = max(pricing.get("input", 0.0) - pricing.get("cache_read", 0.0), 0.0)
    return prev_cache_read_tokens * spread / 1_000_000


# ── Scoring ─────────────────────────────────────────────────────


def _effective_cost(model: str, sig: ModelSignals, state: RouteState) -> float:
    """Measured cost plus the cache-prefix penalty when the candidate switches model."""
    cost = sig.cost if sig.cost is not None else 0.0
    if state.prev_model and model != state.prev_model:
        cost += cache_switch_penalty(state.prev_model, state.prev_cache_read_tokens)
    return cost


def _normalize(value: float, lo: float, hi: float, direction: str) -> float:
    """Normalize ``value`` into [0,1] over [lo,hi], honoring direction. Zero variance → 0.5."""
    if hi - lo < 1e-12:
        return 0.5
    v = (value - lo) / (hi - lo)
    return v if direction == "maximize" else (1.0 - v)


def _score_eligible(
    eligible: list[str],
    signals: dict[str, ModelSignals],
    prefs: RoutingPreferences,
    state: RouteState,
) -> list[tuple[str, float, float, ModelSignals]]:
    """Score each eligible candidate; returns ``(model, score, effective_cost, signals)``.

    Only candidates with at least one measured signal are scored (un-measured candidates are
    dropped from consideration — §6.4). The ``cost`` objective uses ``_effective_cost`` so the
    model-switch penalty is priced in.
    """
    valid = [o for o in prefs.objectives if o.signal in SIGNAL_FIELDS]

    # Per-signal min/max across candidates that actually carry a measured value, so each
    # signal is normalized over the range it is observed in (not a global constant).
    ranges: dict[str, tuple[float, float]] = {}
    for obj in valid:
        vals: list[float] = []
        for m in eligible:
            sig = signals.get(m)
            if sig is None:
                continue
            v = sig.get(obj.signal)
            if v is None:
                continue
            vals.append(_effective_cost(m, sig, state) if obj.signal == "cost" else v)
        if vals:
            ranges[obj.signal] = (min(vals), max(vals))

    scored: list[tuple[str, float, float, ModelSignals]] = []
    for m in eligible:
        sig = signals.get(m)
        if sig is None:
            continue
        total_w = 0.0
        weighted = 0.0
        for obj in valid:
            if obj.signal not in ranges:
                continue
            v = sig.get(obj.signal)
            if v is None:
                continue
            v = _effective_cost(m, sig, state) if obj.signal == "cost" else v
            lo, hi = ranges[obj.signal]
            weighted += obj.weight * _normalize(v, lo, hi, obj.direction)
            total_w += obj.weight
        if total_w <= 0:
            continue
        scored.append((m, weighted / total_w, _effective_cost(m, sig, state), sig))
    return scored


def _select(
    scored: list[tuple[str, float, float, ModelSignals]],
    state: RouteState,
) -> str:
    """Deterministic argmax: highest score → continuity → lower cost → lexicographic id.

    The list is pre-sorted ascending by model id, and ``max`` returns the first maximal element,
    so the final arbiter among equal ``(score, continuity, -cost)`` is the smallest model id.
    """
    ordered = sorted(scored, key=lambda t: t[0])
    best = max(
        ordered,
        key=lambda t: (t[1], 1 if t[0] == state.prev_model else 0, -t[2]),
    )
    return best[0]


# ── The router ──────────────────────────────────────────────────


def route_step(
    job: dict[str, Any],
    state: RouteState,
    prefs: RoutingPreferences,
    *,
    signals: dict[str, ModelSignals] | None = None,
) -> str:
    """Select the model for one workflow step.

    Args:
        job: the phase dict (may carry ``model`` / ``allowed_models``).
        state: the fork-chain state (pool + prior step's model/session/cache footprint).
        prefs: the parsed preferences block (empty = no objectives → fallback).
        signals: per-model measured signals (``{model: ModelSignals}``). Empty/None → cold start.

    Returns:
        The selected model id. A pinned ``model`` is returned verbatim; otherwise the eligible
        set (subset or full pool) is scored and the argmax wins. When nothing is measurable the
        router falls back to the prior model (cache continuity) and then the pool's first entry —
        deterministic, never random.
    """
    store = signals or {}
    selector = parse_step_selector(job)
    if selector.pinned:
        return selector.pinned

    if selector.allowed:
        eligible = [m for m in state.pool if m in selector.allowed]
    else:
        eligible = list(state.pool)

    if not eligible:
        raise ValueError(
            "no eligible model for step: allowed_models intersects the pool empty (validate at load)"
        )

    scored = _score_eligible(eligible, store, prefs, state)
    if scored:
        return _select(scored, state)

    # Cold start: no measured signal for any candidate. Prefer the prior model (free fork,
    # keeps the cache prefix); otherwise take the pool's first entry — a deterministic
    # last resort, not a random pick (§6.4).
    if state.prev_model and state.prev_model in eligible:
        return state.prev_model
    return eligible[0]
