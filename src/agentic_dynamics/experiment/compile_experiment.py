"""Compile an ExperimentSpec into an execution DAG.

The compiler is the executable form of "to make policies, we need information." It
first runs :func:`validate_spec` (the requires/produces gate) and *refuses* to emit a
DAG if any control rule consumes information the ledger doesn't produce. On success it
returns a DAG whose phases are: validate → cells → execute → measure → compare →
writeup → adapt, with a campaign-loop feedback edge from ``adapt`` back to ``cells``.

Reuse (no new transport machinery — see the design doc §6):

- :func:`experiment_matrix` generalizes ``_gen_matrix_cells`` (``pipeline.py:394``)
  plus ``enqueue.py``'s matrix: any factor cross-product, not the hardcoded
  story×tier×quality×condition.
- :func:`compare_arms` generalizes ``routing.simulate_strategies`` (``routing.py:98``):
  arms become data (any ``ComparisonSpec.arm_factor``), compared by a weighted ``loss``.
- :func:`evaluate_rules` drives measurement rules over the ledger; these are the lab
  books, expressed as ``spec.rules``.

Design: ``code_reviews/2026-08-14_experiment-spec-and-compiler-design.md``.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from agentic_dynamics.experiment.experiment_spec import ExperimentSpec, validate_spec

# ── DAG ─────────────────────────────────────────────────────────

# Phase order is fixed; ``adapt`` feeds back into ``cells`` to form the campaign loop.
PHASES: tuple[str, ...] = ("validate", "cells", "execute", "measure", "compare", "writeup", "adapt")


class SpecError(ValueError):
    """Raised when :func:`compile_spec` refuses an invalid spec."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


@dataclass
class Phase:
    """One node in the compiled DAG."""

    name: str
    kind: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class DAG:
    """A compiled experiment DAG: phases, forward edges, and campaign feedback edges."""

    phases: list[Phase]
    edges: list[tuple[str, str]] = field(default_factory=list)
    feedback: list[tuple[str, str]] = field(default_factory=list)

    def names(self) -> list[str]:
        return [p.name for p in self.phases]

    def topological_order(self) -> list[str]:
        """Topological sort over forward edges only (feedback edges excluded)."""
        indeg = {p.name: 0 for p in self.phases}
        adj: dict[str, list[str]] = {p.name: [] for p in self.phases}
        for src, dst in self.edges:
            adj[src].append(dst)
            indeg[dst] += 1
        queue = deque(name for name, deg in indeg.items() if deg == 0)
        order: list[str] = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for nxt in adj[node]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    queue.append(nxt)
        return order


# ── The compiler ────────────────────────────────────────────────


def compile_spec(spec: ExperimentSpec) -> DAG:
    """Compile a spec into a DAG, refusing (via :class:`SpecError`) if validation fails."""
    errors = validate_spec(spec)
    if errors:
        raise SpecError(errors)

    phases = [Phase(name=k, kind=k, params={}) for k in PHASES]
    edges = [(PHASES[i], PHASES[i + 1]) for i in range(len(PHASES) - 1)]
    feedback = [("adapt", "cells")]
    return DAG(phases=phases, edges=edges, feedback=feedback)


# ── experiment_matrix ───────────────────────────────────────────


def _slugify(value: str) -> str:
    out = "".join(ch if ch.isalnum() else "_" for ch in value).strip("_")
    return out.lower() or "cell"


def experiment_matrix(spec: ExperimentSpec) -> list[dict[str, Any]]:
    """Cross-product of the active factors → cells (generalizes ``_gen_matrix_cells``).

    Each cell is a flat dict carrying one level per active factor, plus a deterministic
    ``cell_id`` derived from the spec name and the factor assignment.
    """
    active = [f for f in spec.factors if f.active]
    cells: list[dict[str, Any]] = [{}]
    for factor in active:
        cells = [
            {**cell, factor.name: level}
            for cell in cells
            for level in factor.levels
        ]

    out: list[dict[str, Any]] = []
    for assignment in cells:
        cell = dict(assignment)
        slug = "_".join(f"{_slugify(k)}_{_slugify(v)}" for k, v in assignment.items())
        cell["cell_id"] = f"{_slugify(spec.name)}_{slug}"
        out.append(cell)
    return out


# ── compare_arms ────────────────────────────────────────────────

DEFAULT_OBJECTIVE_FIELDS: dict[str, str] = {
    "cost": "cost",
    "quality": "correctness",
    "latency": "latency",
    "sla": "sla",
    "value": "value",
}


def compare_arms(
    results: list[dict[str, Any]],
    *,
    arm_factor: str,
    loss: dict[str, float],
    objective_fields: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Compare arms by weighted loss and regret (generalizes ``simulate_strategies``).

    ``results`` is a list of outcome records, each carrying the ``arm_factor`` value plus
    numeric metric fields. ``loss`` maps objective names to weights (positive = cost to
    minimize, negative = benefit to maximize). Regret is each arm's weighted loss minus
    the best arm's.

    Returns ``{arm_factor, loss, arms, best_arm, regrets}``.
    """
    fields = dict(DEFAULT_OBJECTIVE_FIELDS)
    if objective_fields:
        fields.update(objective_fields)

    arms: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in results:
        arm = r.get(arm_factor)
        if arm is not None:
            arms[str(arm)].append(r)

    objectives = [
        obj
        for obj in loss
        if obj in fields and any(fields[obj] in r for r in results)
    ]

    arm_stats: dict[str, dict[str, Any]] = {}
    for arm, group in arms.items():
        stats: dict[str, Any] = {"n": len(group)}
        weighted = 0.0
        for obj in objectives:
            fld = fields[obj]
            vals = [r[fld] for r in group if fld in r]
            if not vals:
                continue
            mean = sum(vals) / len(vals)
            stats[f"avg_{fld}"] = round(mean, 4)
            weighted += loss[obj] * mean
        stats["weighted_loss"] = round(weighted, 4)
        arm_stats[arm] = stats

    if not arm_stats:
        return {
            "arm_factor": arm_factor,
            "loss": loss,
            "arms": {},
            "best_arm": None,
            "regrets": {},
        }

    best_arm = min(arm_stats, key=lambda a: arm_stats[a]["weighted_loss"])
    regrets = {
        arm: round(arm_stats[arm]["weighted_loss"] - arm_stats[best_arm]["weighted_loss"], 4)
        for arm in arm_stats
    }
    return {
        "arm_factor": arm_factor,
        "loss": loss,
        "arms": arm_stats,
        "best_arm": best_arm,
        "regrets": regrets,
    }


# ── rule evaluator ──────────────────────────────────────────────


@dataclass
class RuleResult:
    """What a measurement rule emits: a scalar metric plus the information it produces."""

    rule: str
    metric: float
    evidence_class: str
    uncertainty: float = 0.0
    produces: dict[str, Any] = field(default_factory=dict)


def first_pass_quality(attempts: list[dict[str, Any]]) -> RuleResult:
    """Measurement rule: fraction of first attempts accepted + overall accepted rate."""
    n = len(attempts)
    first_pass_ok = sum(
        1 for a in attempts if a.get("attempt_number", 1) == 1 and a.get("accepted")
    )
    accepted = sum(1 for a in attempts if a.get("accepted"))
    first_pass_rate = first_pass_ok / n if n else 0.0
    accepted_outcome = accepted / n if n else 0.0
    return RuleResult(
        rule="first_pass_quality",
        metric=round(first_pass_rate, 4),
        evidence_class="[M]",
        produces={
            "first_pass_rate": round(first_pass_rate, 4),
            "accepted_outcome": round(accepted_outcome, 4),
        },
    )


def _retention_auc(retention: dict[float, float]) -> float:
    """Trapezoidal area under the retention curve R(s), over sorted strengths."""
    points = sorted(retention.items())
    area = 0.0
    for i in range(len(points) - 1):
        s0, r0 = points[i]
        s1, r1 = points[i + 1]
        area += (r0 + r1) / 2.0 * (s1 - s0)
    return area


def grit(attempts: list[dict[str, Any]]) -> RuleResult:
    """Measurement rule implementing the operational Grit definition (basin.py:6-10).

    Grit(s) = P(test_executed_success | perturbation_strength=s)
    retention R(s) = G(s) / G(0)
    grit_auc = area under the retention curve
    recovery_premium = C(successful_perturbed) / C(successful_baseline)

    Requires each attempt to carry ``perturbation_strength`` and ``test_executed_success``
    (and ``cost`` for the premium) — both are now ledger-measured. If a specific
    attempts list lacks those fields, it returns an explicit "unmeasured" result
    (NaN, uncertainty 1.0). It never substitutes a proxy like "fraction of attempts
    completed."
    """
    if not attempts or not all(
        "perturbation_strength" in a and "test_executed_success" in a for a in attempts
    ):
        return RuleResult(
            rule="grit",
            metric=float("nan"),
            evidence_class="[M]",
            uncertainty=1.0,
            produces={},
        )

    by_strength: dict[float, list[bool]] = defaultdict(list)
    for a in attempts:
        by_strength[float(a["perturbation_strength"])].append(bool(a["test_executed_success"]))

    g = {s: sum(v) / len(v) for s, v in sorted(by_strength.items())}
    baseline = g.get(0.0)
    if baseline is None or baseline == 0.0:
        return RuleResult(
            rule="grit",
            metric=float("nan"),
            evidence_class="[M]",
            uncertainty=1.0,
            produces={},
        )

    retention = {s: g[s] / baseline for s in g}
    grit_auc = _retention_auc(retention)

    baseline_costs = [
        a["cost"]
        for a in attempts
        if float(a["perturbation_strength"]) == 0.0
        and a["test_executed_success"]
        and "cost" in a
    ]
    perturbed_costs = [
        a["cost"]
        for a in attempts
        if float(a["perturbation_strength"]) != 0.0
        and a["test_executed_success"]
        and "cost" in a
    ]
    recovery_premium = None
    if baseline_costs and perturbed_costs:
        recovery_premium = (sum(perturbed_costs) / len(perturbed_costs)) / (
            sum(baseline_costs) / len(baseline_costs)
        )

    return RuleResult(
        rule="grit",
        metric=round(grit_auc, 4),
        evidence_class="[M]",
        produces={
            "grit": {s: round(v, 4) for s, v in g.items()},
            "retention": {s: round(v, 4) for s, v in retention.items()},
            "grit_auc": round(grit_auc, 4),
            "recovery_premium": round(recovery_premium, 4) if recovery_premium is not None else float("nan"),
        },
    )


def decision_calibration(decisions: list[dict[str, Any]]) -> RuleResult:
    """Measurement rule ([C], CAP I6 F3): scores shadow ``ControlDecision``s against the
    deterministic baseline (``control.step_routing.route_step``) they ran BESIDE, producing
    ``decision_regret`` — design §9 I6's own gate ("agreement/divergence vs step_routing
    measurable"), expressed as a named measurement rule so it flows through the SAME
    ``evaluate_rules``/``compare_arms`` machinery every other rule does, rather than an ad-hoc
    report (F3, ``docs/context_abstraction/implementation_notes.md``).

    ``decisions`` — one dict per recorded shadow decision:
    ``{"action", "baseline_action", "model": <route's proposed model, if action == "route">,
    "baseline_model": <what route_step actually chose>}`` (the shape
    ``control.rules.make_shadow_router`` writes into ``ControlDecision.parameters``).
    ``decision_regret`` is the fraction whose action OR proposed model diverges from the
    baseline — 0.0 is perfect agreement. Measure-before-policy applied to the plane's own
    controller: nothing may consume ``decision_regret`` as a policy signal until it exists,
    exactly like every other rule in this module.
    """
    if not decisions:
        return RuleResult(
            rule="decision_calibration", metric=float("nan"), evidence_class="[C]",
            uncertainty=1.0, produces={},
        )
    disagreements = sum(
        1
        for d in decisions
        if d.get("action") != d.get("baseline_action")
        or (d.get("action") == "route" and d.get("model") != d.get("baseline_model"))
    )
    n = len(decisions)
    regret = disagreements / n
    return RuleResult(
        rule="decision_calibration",
        metric=round(regret, 4),
        evidence_class="[C]",
        produces={"decision_regret": round(regret, 4), "n_decisions": n},
    )


MEASUREMENT_RULES: dict[str, Callable[..., RuleResult]] = {
    "first_pass_quality": first_pass_quality,
    "grit": grit,
    "decision_calibration": decision_calibration,
}
# ``grit`` is re-admitted: ``perturbation_strength`` and ``test_executed_success`` are
# now ledger-measured (LEDGER_FIELDS), so the validator accepts a spec whose grit rule
# requires them. The evaluator still returns an unmeasured result if a concrete attempts
# list omits the fields — it never fabricates a "completed/n" proxy.


def evaluate_rules(
    spec: ExperimentSpec,
    attempts: list[dict[str, Any]],
    *,
    registry: dict[str, Callable[..., RuleResult]] | None = None,
) -> list[RuleResult]:
    """Run the spec's measurement rules over the ledger (attempts) → information.

    Control rules are skipped here — they consume information and are evaluated at
    enqueue/lease time, not during measurement. A measurement rule with no registered
    implementation yields an explicit "unmeasured" result (``metric`` is NaN,
    ``uncertainty`` is 1.0) — never a fabricated number.
    """
    reg = dict(MEASUREMENT_RULES)
    if registry:
        reg.update(registry)

    out: list[RuleResult] = []
    for rule in spec.rules:
        if rule.plane != "measurement":
            continue
        fn = reg.get(rule.name)
        if fn is None:
            out.append(
                RuleResult(
                    rule=rule.name,
                    metric=float("nan"),
                    evidence_class=rule.evidence_class,
                    uncertainty=1.0,
                    produces={},
                )
            )
            continue
        out.append(fn(attempts))
    return out
