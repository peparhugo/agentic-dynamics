"""The routing *contract* — data model, validation mechanics, and the ``Router`` seam.

This module is the runtime-owned half of the per-step routing split (refactor-repair Debt-2):
it holds everything the executor needs to *describe* and *validate* routing, and the ``Router``
protocol that declares the *decision* the control plane supplies. The decision itself —
``route_step`` (the preference-scored, cache-priced policy) — lives in
``control.step_routing`` and is injected at the composition root (``scripts/run_workflow.py``),
so ``runtime`` never imports ``control``.

Split rule: the data model + validation here are *mechanics* (pure, no policy); the scoring /
selection in ``control.step_routing`` is *policy* (it consumes measured signals and prices a
model switch). ``docs/routing_design.md`` §1–§5 define both sides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from agentic_dynamics.measurement.signal_registry import (
    ROUTING,
    reserved_for_other,
    signals_for,
)

if TYPE_CHECKING:  # pragma: no cover - import only for static typing
    from agentic_dynamics.experiment.experiment_spec import ExperimentSpec

# ── Signal vocabulary ───────────────────────────────────────────
#
# The signals a routing policy may consume today, DERIVED from the signal registry
# (refactor-repair Debt-3) — never hand-listed here, so the routing vocabulary can no longer
# drift from the ledger's "measured" facts. ``edge_case_coverage`` is unmeasured and must be
# gated behind a measurement rule (see ``validate_preferences``). ``confidence`` IS measured
# [H], but it is reserved for the ``model_cascade``/``dynamics`` control arms, so it is not
# permitted for generic model routing.

# Map a signal name to the ``ModelSignals`` field that carries it. ``edge_case_coverage`` is
# listed so a ``ModelSignals`` object can carry it once instrumented, but it is NOT in
# ``MEASURED_SIGNALS`` (the registry marks it unmeasured) and therefore cannot be consumed until
# ``produced`` admits it.
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

# Measured *and* routing-permitted today (the registry is the source of truth).
MEASURED_SIGNALS: frozenset[str] = signals_for(ROUTING)

# Measured, but the routing policy may not consume them — ``confidence`` is reserved for the
# cascade control arms (measured [H], not "unmeasured").
FORBIDDEN_SIGNALS: frozenset[str] = reserved_for_other(ROUTING)

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
    ``edge_case_coverage`` is admissible only when present there. A signal the registry marks
    measured but reserves for another consumer (``confidence`` → cascade) is refused with a
    *reservation* error — never a false "unmeasured" one. Returns a list of error strings.
    """
    errors: list[str] = []
    available = set(MEASURED_SIGNALS) | set(produced)
    for obj in prefs.objectives:
        if obj.signal in FORBIDDEN_SIGNALS:
            errors.append(
                f'preference objective {obj.signal!r} is measured but reserved for the '
                f'cascade control arms — it is not permitted for generic model routing.'
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


# ── Routing state ───────────────────────────────────────────────


@dataclass
class RouteState:
    """Fork-chain state the router needs: the pool and the prior step's session/footprint."""

    pool: list[str]
    prev_model: str | None = None
    prev_session_id: str = ""
    prev_cache_read_tokens: int = 0
    context_tokens: int = 0


# ── The seam ────────────────────────────────────────────────────


class Router(Protocol):
    """The per-step routing decision — a callable matching ``control.step_routing.route_step``.

    Runtime owns the contract (this protocol + the data model above); control supplies the
    implementation, injected at the composition root (``scripts/run_workflow.py``). This is the
    dependency inversion that lets ``runtime`` depend on the protocol instead of on ``control``.
    """

    def __call__(
        self,
        job: dict[str, Any],
        state: RouteState,
        prefs: RoutingPreferences,
        *,
        signals: dict[str, ModelSignals] | None = None,
    ) -> str: ...
