"""ExperimentSpec — declarative experiment definitions for the information-acquisition machine.

A spec declares the workflow, factors, rules, metrics, comparison, writeup, stop, and
adapt blocks that the compiler turns into a DAG. The load-bearing rule of the design is
enforced here: a ``RuleSpec`` declares ``requires`` (information it consumes) and
``produces`` (information it emits); :func:`validate_rules` refuses a control rule whose
``requires`` are not produced by the ledger schema or by a measurement rule in the same
spec. That refusal is the executable form of "to make policies, we need information."

Design: ``code_reviews/2026-08-14_experiment-spec-and-compiler-design.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ── Constants ───────────────────────────────────────────────────

WORKFLOW_KINDS = frozenset({"story", "task", "experiment", "agent_task"})
PLANES = frozenset({"measurement", "control"})
EVIDENCE_CLASSES = frozenset({"[M]", "[C]", "[H]", "[P]", "[X]"})
METRIC_AGGS = frozenset({"mean", "distribution", "ratio"})
METRIC_OVERS = frozenset({"outcome", "attempt", "job", "cell"})
ADAPT_STRATEGIES = frozenset({"coordinate_descent", "manual"})
ADAPT_SELECTIONS = frozenset(
    {"highest_uncertainty", "highest_regret", "largest_effect"}
)

# Base information fields the ledger emits. Measurement rules consume these directly;
# control rules consume them transitively via a measurement rule's ``produces``.
#
# The four formerly-absent fields are now MEASURED (instrumentation step 3 is done):
#   - ``confidence``            — [H] per-attempt execution-confidence (opencode.py)
#   - ``perturbation_strength`` — the strength axis (s=0.0 baseline) on every result
#   - ``test_executed_success`` — independently verified by test_runner, not self-report
#   - ``tokens_answer`` / ``tokens_explanation`` — the answer/explanation output split
# Because they are ledger-produced, the validator now admits the ``grit`` rule (needs
# perturbation_strength + test_executed_success) and the ``model_cascade``/``dynamics``
# control arms (need confidence).
LEDGER_FIELDS: frozenset[str] = frozenset(
    {
        # job-level
        "job_id",
        "spec_id",
        "policy_arm",
        "policy_id",
        "budget",
        "due_at",
        "forecast_cost",
        "forecast_latency",
        "actual_cost",
        "deadline_slack",
        "status",
        # factor levels
        "model",
        "condition",
        "policy",
        "seed",
        "strength",
        "story",
        "tier",
        # attempt-level
        "attempt_id",
        "attempt_number",
        "parent_attempt_id",
        "retry_reason",
        "escalation_from",
        "escalation_to",
        "provider_model_version",
        "queued_at",
        "leased_at",
        "started_at",
        "first_token_at",
        "ended_at",
        "queue_wait_ms",
        "service_time_ms",
        "cache_hit",
        "tool_calls",
        "completed",
        "first_pass",
        "accepted",
        "evaluator_independent",
        # tokens / cost / value
        "tokens_in",
        "tokens_out",
        "tokens_reasoning",
        "tokens_answer",
        "tokens_explanation",
        "cost_inference",
        "cost_orchestration",
        "value",
        "rework_cost",
        "reuse_value",
        # measured attempt-level signals (previously the instrumentation gap)
        "confidence",
        "perturbation_strength",
        "test_executed_success",
    }
)


# ── Core objects ────────────────────────────────────────────────


@dataclass
class Workflow:
    """What the cells execute. ``kind`` makes the same interpreter run at every scale."""

    kind: str  # story | task | experiment | agent_task
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "params": self.params}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Workflow:
        if "kind" not in d:
            raise ValueError("Workflow missing required field: kind")
        return cls(kind=d["kind"], params=d.get("params", {}) or {})


@dataclass
class Factor:
    """One independent variable of the grid. ``policy`` is a first-class factor."""

    name: str  # model | condition | policy | seed | strength | story | tier
    levels: list[str]
    active: bool = True
    current: Any = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "levels": self.levels,
            "active": self.active,
        }
        if self.current is not None:
            out["current"] = self.current
        return out

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Factor:
        if "name" not in d or "levels" not in d:
            raise ValueError(f"Factor missing required fields: name/levels ({d})")
        return cls(
            name=d["name"],
            levels=[str(x) for x in d["levels"]],
            active=d.get("active", True),
            current=d.get("current"),
        )


@dataclass
class RuleSpec:
    """A measurement rule (produces information) or control rule (consumes it)."""

    name: str
    plane: str  # measurement | control
    evidence_class: str  # [M] [C] [H] [P] [X]
    requires: list[str] = field(default_factory=list)  # information this rule CONSUMES
    produces: list[str] = field(default_factory=list)  # information this rule EMITS

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "plane": self.plane,
            "evidence_class": self.evidence_class,
            "requires": self.requires,
            "produces": self.produces,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RuleSpec:
        missing = [k for k in ("name", "plane", "evidence_class") if k not in d]
        if missing:
            raise ValueError(f"RuleSpec missing required fields: {missing}")
        return cls(
            name=d["name"],
            plane=d["plane"],
            evidence_class=d["evidence_class"],
            requires=list(d.get("requires", []) or []),
            produces=list(d.get("produces", []) or []),
        )


@dataclass
class MetricSpec:
    """One summary a writeup reports, aggregated over some unit."""

    name: str
    agg: str  # mean | distribution | ratio
    over: str  # outcome | attempt | job | cell

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "agg": self.agg, "over": self.over}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MetricSpec:
        missing = [k for k in ("name", "agg", "over") if k not in d]
        if missing:
            raise ValueError(f"MetricSpec missing required fields: {missing}")
        return cls(name=d["name"], agg=d["agg"], over=d["over"])


@dataclass
class ComparisonSpec:
    """How arms are compared. ``loss`` is the policy objective space."""

    kind: str  # routing_regret | policy_diff | effect_size
    arm_factor: str  # the factor being compared (e.g. "policy")
    loss: dict[str, float] = field(default_factory=dict)  # {cost, quality, latency, sla, value}

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "arm_factor": self.arm_factor, "loss": self.loss}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ComparisonSpec:
        missing = [k for k in ("kind", "arm_factor") if k not in d]
        if missing:
            raise ValueError(f"ComparisonSpec missing required fields: {missing}")
        return cls(
            kind=d["kind"],
            arm_factor=d["arm_factor"],
            loss=d.get("loss", {}) or {},
        )


@dataclass
class WriteupSpec:
    """The human-readable information the experiment emits."""

    format: str  # lab_book | ...
    sections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"format": self.format, "sections": self.sections}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WriteupSpec:
        if "format" not in d:
            raise ValueError("WriteupSpec missing required field: format")
        return cls(format=d["format"], sections=list(d.get("sections", []) or []))


@dataclass
class StopSpec:
    """Termination conditions for a grid."""

    budget_usd: float | None = None
    max_attempts: int | None = None
    uncertainty_threshold: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "budget_usd": self.budget_usd,
            "max_attempts": self.max_attempts,
            "uncertainty_threshold": self.uncertainty_threshold,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StopSpec:
        return cls(
            budget_usd=d.get("budget_usd"),
            max_attempts=d.get("max_attempts"),
            uncertainty_threshold=d.get("uncertainty_threshold"),
        )


@dataclass
class AdaptSpec:
    """The campaign loop: tweak one factor, emit the next grid."""

    strategy: str  # coordinate_descent | manual
    selection: str  # highest_uncertainty | highest_regret | largest_effect

    def to_dict(self) -> dict[str, Any]:
        return {"strategy": self.strategy, "selection": self.selection}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AdaptSpec:
        return cls(strategy=d.get("strategy", "manual"), selection=d.get("selection", "highest_regret"))


@dataclass
class ExperimentSpec:
    """A grid of cells — the cross-product of factors — plus the rules/metrics that
    turn its ledger into information and, ultimately, policy arms."""

    name: str
    question: str
    version: str
    workflow: Workflow
    factors: list[Factor]  # policy is a first-class factor here
    design: str  # "factorial" (cross-product) — the cells ARE the grid
    rules: list[RuleSpec] = field(default_factory=list)
    metrics: list[MetricSpec] = field(default_factory=list)
    comparison: ComparisonSpec | None = None
    writeup: WriteupSpec | None = None
    stop: StopSpec = field(default_factory=StopSpec)
    adapt: AdaptSpec = field(default_factory=lambda: AdaptSpec("manual", "highest_regret"))
    git_sha: str = ""
    pricing_version: str = ""
    seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "question": self.question,
            "version": self.version,
            "workflow": self.workflow.to_dict(),
            "factors": [f.to_dict() for f in self.factors],
            "design": self.design,
            "rules": [r.to_dict() for r in self.rules],
            "metrics": [m.to_dict() for m in self.metrics],
            "stop": self.stop.to_dict(),
            "adapt": self.adapt.to_dict(),
            "git_sha": self.git_sha,
            "pricing_version": self.pricing_version,
            "seed": self.seed,
        }
        if self.comparison is not None:
            out["comparison"] = self.comparison.to_dict()
        if self.writeup is not None:
            out["writeup"] = self.writeup.to_dict()
        return out

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExperimentSpec:
        missing = [k for k in ("name", "question", "version", "workflow", "factors", "design") if k not in d]
        if missing:
            raise ValueError(f"ExperimentSpec missing required fields: {missing}")
        comparison = d.get("comparison")
        writeup = d.get("writeup")
        return cls(
            name=d["name"],
            question=d["question"],
            version=d["version"],
            workflow=Workflow.from_dict(d["workflow"]),
            factors=[Factor.from_dict(f) for f in d["factors"]],
            design=d["design"],
            rules=[RuleSpec.from_dict(r) for r in d.get("rules", []) or []],
            metrics=[MetricSpec.from_dict(m) for m in d.get("metrics", []) or []],
            comparison=ComparisonSpec.from_dict(comparison) if comparison else None,
            writeup=WriteupSpec.from_dict(writeup) if writeup else None,
            stop=StopSpec.from_dict(d.get("stop", {}) or {}),
            adapt=AdaptSpec.from_dict(d.get("adapt", {}) or {}),
            git_sha=d.get("git_sha", ""),
            pricing_version=d.get("pricing_version", ""),
            seed=d.get("seed"),
        )

    @classmethod
    def from_yaml(cls, path: Path) -> ExperimentSpec:
        with open(path) as f:
            return cls.from_dict(yaml.safe_load(f))

    def to_yaml(self, path: Path) -> None:
        path.write_text(yaml.dump(self.to_dict(), sort_keys=False))


def load_spec(path: Path) -> ExperimentSpec:
    """Load an ExperimentSpec from a YAML file (``experiments/specs/*.yaml``)."""
    return ExperimentSpec.from_yaml(Path(path))


# ── The validator (the load-bearing gate) ───────────────────────


def validate_rules(spec: ExperimentSpec) -> list[str]:
    """Validate requires/produces. Returns a list of error strings (empty = valid).

    The available information is the ledger schema plus the ``produces`` of every
    measurement rule in the spec. A rule whose ``requires`` are not all available is
    refused — measurement first, policy second.
    """
    errors: list[str] = []
    seen: set[str] = set()

    for rule in spec.rules:
        if rule.name in seen:
            errors.append(f'duplicate rule name {rule.name!r}')
        seen.add(rule.name)
        if rule.plane not in PLANES:
            errors.append(
                f'rule "{rule.name}": plane {rule.plane!r} is not one of {sorted(PLANES)}'
            )
        if rule.evidence_class not in EVIDENCE_CLASSES:
            errors.append(
                f'rule "{rule.name}": evidence_class {rule.evidence_class!r} '
                f'is not one of {sorted(EVIDENCE_CLASSES)}'
            )

    available = set(LEDGER_FIELDS)
    for rule in spec.rules:
        if rule.plane == "measurement":
            available.update(rule.produces)

    for rule in spec.rules:
        for req in rule.requires:
            if req not in available:
                errors.append(
                    f'rule "{rule.name}" requires {req!r} — not produced by the ledger '
                    f'or any measurement rule in this spec. Instrument it first.'
                )
    return errors


def validate_spec(spec: ExperimentSpec) -> list[str]:
    """Structural validation plus the requires/produces gate. Empty list = valid."""
    errors: list[str] = []

    if spec.workflow.kind not in WORKFLOW_KINDS:
        errors.append(f'workflow.kind {spec.workflow.kind!r} is not one of {sorted(WORKFLOW_KINDS)}')
    if spec.design != "factorial":
        errors.append(f'design {spec.design!r} unsupported — only "factorial" is defined')

    factor_names = [f.name for f in spec.factors]
    if len(set(factor_names)) != len(factor_names):
        errors.append(f"duplicate factor names: {factor_names}")
    for f in spec.factors:
        if not f.name:
            errors.append("factor with empty name")
        if not f.levels:
            errors.append(f'factor "{f.name}" has no levels')

    if spec.comparison is not None and spec.comparison.arm_factor not in factor_names:
        errors.append(
            f'comparison.arm_factor {spec.comparison.arm_factor!r} is not a declared factor '
            f'({factor_names})'
        )

    for m in spec.metrics:
        if m.agg not in METRIC_AGGS:
            errors.append(f'metric "{m.name}": agg {m.agg!r} is not one of {sorted(METRIC_AGGS)}')
        if m.over not in METRIC_OVERS:
            errors.append(f'metric "{m.name}": over {m.over!r} is not one of {sorted(METRIC_OVERS)}')

    if spec.adapt.strategy not in ADAPT_STRATEGIES:
        errors.append(
            f'adapt.strategy {spec.adapt.strategy!r} is not one of {sorted(ADAPT_STRATEGIES)}'
        )
    if spec.adapt.selection not in ADAPT_SELECTIONS:
        errors.append(
            f'adapt.selection {spec.adapt.selection!r} is not one of {sorted(ADAPT_SELECTIONS)}'
        )

    errors.extend(validate_rules(spec))
    return errors
