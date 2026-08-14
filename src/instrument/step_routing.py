"""Per-step model routing for the workflow layer.

Implements ``docs/routing_design.md``: an intelligent, preference-driven router that
selects a model per workflow step (phase), honoring three selection semantics
(pin / ``allowed_models`` subset / full pool), scoring candidates over *measured*
experiment signals, and pricing the cache-prefix loss that a model switch incurs
(see ``workflow_runner.run_workflow``, which already forks each step off the prior
session when the model is unchanged).

This module is a thin layer *on top* of ``routing.py`` (``recommend_route`` /
``compute_routing`` remain the per-task signal aggregators and are unchanged). The
router is a **pure function** — no I/O, no RNG — so it is trivially unit-testable and
reusable at enqueue time, in ``run_workflow``, and in the compiler's ``compare_arms``.

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

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .efficiency import get_pricing

if TYPE_CHECKING:  # pragma: no cover - import only for static typing
    from .experiment_spec import ExperimentSpec

# ── Signal vocabulary ───────────────────────────────────────────
#
# The signals a routing policy may consume today. ``edge_case_coverage`` is deliberately
# ABSENT: it is not yet measured and must be gated behind a measurement rule (see
# ``validate_preferences``). ``confidence`` is FORBIDDEN — it remains unmeasured and is
# reserved for the ``model_cascade``/``dynamics`` control arms.

# Map a signal name to the ``ModelSignals`` field that carries it. ``edge_case_coverage`` is
# listed so a ``ModelSignals`` object can carry it once instrumented, but it is NOT in
# ``MEASURED_SIGNALS`` and therefore cannot be consumed until ``produced`` admits it.
SIGNAL_FIELDS: dict[str, str] = {
    "correctness": "correctness",
    "cost": "cost",
    "efficiency": "efficiency",
    "cache_hit_rate": "cache_hit_rate",
    "constraint_score": "constraint_score",
    "code_quality_score": "code_quality_score",
    "novelty_score": "novelty_score",
    "composite_score": "composite_score",
    "edge_case_coverage": "edge_case_coverage",
}

# Measured today: everything in SIGNAL_FIELDS except edge_case_coverage.
MEASURED_SIGNALS: frozenset[str] = frozenset(
    s for s in SIGNAL_FIELDS if s != "edge_case_coverage"
)

# Never consumable by the routing policy (unmeasured, reserved for model_cascade).
FORBIDDEN_SIGNALS: frozenset[str] = frozenset({"confidence"})

_DIRECTIONS: frozenset[str] = frozenset({"minimize", "maximize"})


# ── Preferences ─────────────────────────────────────────────────


@dataclass
class Objective:
    """One weighted objective over a measured signal."""

    signal: str
    direction: str = "maximize"  # "minimize" | "maximize"
    weight: float = 1.0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Objective:
        """Build an objective from the preferences YAML form ``{signal, direction, weight}``."""
        if "signal" not in d:
            raise ValueError("Objective missing required field: signal")
        return cls(
            signal=str(d["signal"]),
            direction=str(d.get("direction", "maximize")),
            weight=float(d.get("weight", 1.0)),
        )


@dataclass
class RoutingPreferences:
    """The parsed ``preferences`` block: an ordered list of weighted objectives."""

    objectives: list[Objective] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> RoutingPreferences:
        """Parse ``{objectives: [...]}``; missing/None yields an empty preference set."""
        if not d:
            return cls()
        raw = d.get("objectives") or []
        return cls(objectives=[Objective.from_dict(o) for o in raw])


# ── Measured signals per model ──────────────────────────────────


@dataclass
class ModelSignals:
    """Measured experiment signals for one model (aggregated from ``_results_summary.json``).

    Every signal field is ``None`` when unmeasured. ``edge_case_coverage`` is included so it
    can be carried once instrumented, but the validator refuses to *consume* it until a
    measurement rule ``produces`` it.
    """

    model: str = ""
    correctness: float | None = None
    cost: float | None = None
    efficiency: float | None = None
    cache_hit_rate: float | None = None
    constraint_score: float | None = None
    code_quality_score: float | None = None
    novelty_score: float | None = None
    composite_score: float | None = None
    edge_case_coverage: float | None = None

    def get(self, signal: str) -> float | None:
        """Return the measured value for ``signal``, or ``None`` when unmeasured/unknown."""
        field = SIGNAL_FIELDS.get(signal)
        if field is None:
            return None
        return getattr(self, field, None)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ModelSignals:
        """Build from a flat dict keyed by signal field names (``model`` included)."""
        kwargs: dict[str, Any] = {"model": d.get("model", "")}
        for _signal, field_name in SIGNAL_FIELDS.items():
            if field_name in d:
                kwargs[field_name] = d.get(field_name)
        return cls(**kwargs)


# The signal store (build_signal_store + the per-entry derivations + the model-id alias
# layer) lives in ``.signal_store`` — see ``docs/routing_next_steps.md`` item 1. It imports
# ``ModelSignals`` from this module, so keep this module free of an import back into it (no
# cycle): the router here consumes the store but does not build it.


# ── Step selector ───────────────────────────────────────────────


@dataclass
class StepSelector:
    """A phase's model selector: a pin and/or an allowed subset (both empty = full pool)."""

    pinned: str | None = None
    allowed: frozenset[str] = frozenset()


def parse_step_selector(phase: dict[str, Any]) -> StepSelector:
    """Extract the step selector from a phase dict (``model`` and/or ``allowed_models``)."""
    pinned = phase.get("model")
    allowed = phase.get("allowed_models") or []
    return StepSelector(pinned=str(pinned) if pinned else None, allowed=frozenset(allowed))


def validate_step_selector(phase: dict[str, Any], pool: list[str]) -> list[str]:
    """Validate a phase's selector against the model pool (empty list = valid).

    Enforces: at most one of ``model``/``allowed_models``; pinned id ∈ pool; ``allowed_models``
    is a non-empty, duplicate-free list whose ids are all ∈ pool.
    """
    errors: list[str] = []
    has_pin = "model" in phase
    has_allowed = "allowed_models" in phase
    if has_pin and has_allowed:
        errors.append("phase declares both 'model' and 'allowed_models'; use exactly one")
    if has_pin:
        mid = str(phase["model"])
        if mid not in pool:
            errors.append(f"pinned model {mid!r} is not in model_pool")
    if has_allowed:
        allowed = phase.get("allowed_models")
        if not isinstance(allowed, list) or not allowed:
            errors.append("allowed_models must be a non-empty list")
        else:
            ids = [str(x) for x in allowed]
            if len(set(ids)) != len(ids):
                errors.append("allowed_models contains duplicate ids")
            for mid in ids:
                if mid not in pool:
                    errors.append(f"allowed_models entry {mid!r} is not in model_pool")
    return errors


# ── Validation (the load-bearing gate for preferences) ──────────


def validate_preferences(
    prefs: RoutingPreferences,
    *,
    produced: frozenset[str] | set[str] | tuple[str, ...] = (),
) -> list[str]:
    """Validate a preferences block against the measured signal vocabulary.

    ``produced`` is the set of information a measurement rule ``produces`` in the same spec;
    ``edge_case_coverage`` is admissible only when present there. ``confidence`` is always
    refused. Returns a list of error strings (empty = valid).
    """
    errors: list[str] = []
    available = set(MEASURED_SIGNALS) | set(produced)
    for obj in prefs.objectives:
        if obj.signal in FORBIDDEN_SIGNALS:
            errors.append(
                f'preference objective {obj.signal!r} is forbidden: it is unmeasured and '
                f'must not be consumed by a routing policy.'
            )
        elif obj.signal not in available:
            errors.append(
                f'preference objective {obj.signal!r} is not produced by the ledger or any '
                f'measurement rule. Instrument it first (docs/routing_design.md §5).'
            )
        if obj.direction not in _DIRECTIONS:
            errors.append(
                f'preference objective {obj.signal!r}: direction {obj.direction!r} is not '
                f'one of {sorted(_DIRECTIONS)}'
            )
        if obj.weight < 0:
            errors.append(f'preference objective {obj.signal!r}: weight must be >= 0')
    return errors


def _produced_signals(spec: ExperimentSpec) -> frozenset[str]:
    """Union of ``produces`` across the spec's measurement rules."""
    produced: set[str] = set()
    for rule in spec.rules:
        if rule.plane == "measurement":
            produced.update(rule.produces)
    return frozenset(produced)


def resolve_pool(spec: ExperimentSpec, *, default_model: str = "") -> list[str]:
    """Resolve the routing pool: ``workflow.params.model_pool``, else the single run model.

    Routing is only *active* when a ``model_pool`` is declared; otherwise the workflow is
    single-model (backward compatible) and the pool is just ``[default_model]``.
    """
    pool = spec.workflow.params.get("model_pool")
    if pool:
        return [str(m) for m in pool]
    return [default_model] if default_model else []


def validate_workflow_routing(spec: ExperimentSpec, *, default_model: str = "") -> list[str]:
    """Validate pool, per-phase selectors, and preferences for an ``agent_task`` workflow.

    Returns a list of error strings (empty = valid). Callers compose this with
    ``validate_spec`` before executing. Routing-inactive specs (no ``model_pool``, no per-phase
    selector, no ``preferences``) validate trivially.
    """
    errors: list[str] = []
    params = spec.workflow.params
    pool = resolve_pool(spec, default_model=default_model)

    has_pool = bool(params.get("model_pool"))
    has_selectors = any(
        ("model" in p or "allowed_models" in p) for p in (params.get("phases") or [])
    )
    has_prefs = bool(params.get("preferences"))
    if not (has_pool or has_selectors or has_prefs):
        return []

    if has_pool:
        if not pool:
            errors.append("workflow.params.model_pool is empty")
        elif len(set(pool)) != len(pool):
            errors.append("workflow.params.model_pool contains duplicate ids")

    for phase in params.get("phases") or []:
        errors.extend(validate_step_selector(phase, pool))

    prefs = RoutingPreferences.from_dict(params.get("preferences"))
    errors.extend(validate_preferences(prefs, produced=_produced_signals(spec)))
    return errors


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


# ── Routing state ───────────────────────────────────────────────


@dataclass
class RouteState:
    """Fork-chain state the router needs: the pool and the prior step's session/footprint."""

    pool: list[str]
    prev_model: str | None = None
    prev_session_id: str = ""
    prev_cache_read_tokens: int = 0
    context_tokens: int = 0


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
