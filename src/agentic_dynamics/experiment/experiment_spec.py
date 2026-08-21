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

import warnings
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
ADAPT_SELECTIONS = frozenset({"highest_uncertainty", "highest_regret", "largest_effect"})

# ── Artifact identity (refactor-repair P1-3) ─────────────────────
#
# Identity used to be guessed from the question text (a substring classifier) — fragile and
# wrong for real specs like ``posthoc_pipeline`` (operational) and ``workflow_step_routing``
# (source-modifying). Now it is explicit, validated metadata on the spec:
#
#   artifact_kind  experiment | workflow   — what the artifact IS.
#   intent         measure    | mutate     — what it DOES (measure a phenomenon, or change source).
#   side_effects   {repository, external_services} — where it writes / what it talks to.
#   repeatable     bool       — safe to run repeatedly (experiments) vs one-shot (workflows).
#
# Defaults are the benign "nothing asserted" values, so the 77 committed specs (none of which
# carry the fields yet — the P1-3 backfill lands later) load and validate unchanged.
ARTIFACT_KINDS = frozenset({"experiment", "workflow"})
INTENTS = frozenset({"measure", "mutate"})

# ── Spec lifecycle vocabulary ───────────────────────────────────
#
# A spec's lifecycle is *authored* in the YAML when the operator already knows it and
# *derived* otherwise (see :mod:`instrument.spec_status`, which turns the spec corpus plus
# the run ledgers into ``experiments/specs/index.json`` + ``STATUS.md``). The vocabulary
# lives here — beside the other validated enums — so ``validate_spec`` stays the single
# gate for it and the derived index imports this frozenset instead of re-listing it.
#
# Per-kind semantics (refactor-repair P1-4; review item 8): a *repeatable* spec (an
# experiment, or an idempotent operation) is always ``runnable``; a *non-repeatable* workflow
# derives the work-order states, where ``completed``/``failed``/``blocked``/``running`` are
# DERIVED from the run ledgers (and ``running`` requires current-execution evidence), not
# authored:
#
#   draft       — authored, never run to completion; not yet a claim about anything.
#   runnable    — never run (a non-repeatable workflow), or a repeatable spec; ready to run.
#   running     — a non-repeatable workflow currently executing (an open, recent run).
#   failed      — a non-repeatable workflow whose run(s) recorded a definitive failure.
#   blocked     — a non-repeatable workflow with runs that started but never resolved.
#   completed   — a non-repeatable workflow whose run succeeded (derived from the ledgers).
#   superseded  — a later spec took over its question (see ``superseded_by``).
#   tombstoned  — retired; kept for lineage, never to be run again.
SPEC_STATUSES = frozenset(
    {
        "draft",
        "runnable",
        "running",
        "failed",
        "blocked",
        "completed",
        "superseded",
        "tombstoned",
    }
)

#: Every top-level key a spec YAML may carry. ``from_dict`` warns (loudly, via
#: :mod:`warnings`) about anything outside this set rather than dropping it silently —
#: a typo'd ``supercedes:`` used to vanish without a trace.
SPEC_KEYS: frozenset[str] = frozenset(
    {
        # core
        "name",
        "question",
        "version",
        "workflow",
        "factors",
        "design",
        "rules",
        "metrics",
        "comparison",
        "writeup",
        "stop",
        "adapt",
        "git_sha",
        "pricing_version",
        "seed",
        # lifecycle
        "status",
        "supersedes",
        "superseded_by",
        "completed_at",
        "last_run_at",
        "results_pointer",
        # artifact identity (refactor-repair P1-3)
        "artifact_kind",
        "intent",
        "side_effects",
        "repeatable",
        "sandboxed",
    }
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
#
# The *single source of truth* for a signal's measured status, evidence class, and permitted
# consumers is ``measurement/signal_registry.py`` (refactor-repair Debt-3) — this frozenset is
# the ledger field list, and the registry's measured signals are checked against it in the tests.
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


def _as_name_list(value: Any) -> list[str]:
    """Normalize a spec-name field that may be a bare string, a list, or absent.

    ``supersedes`` is authored either way in practice (``supersedes: old_spec`` and
    ``supersedes: [a, b]`` are both natural YAML), so normalize to a list once, here,
    rather than making every consumer branch on the type.
    """
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def _as_optional_str(value: Any) -> str | None:
    """Normalize an optional scalar field: ``None``/``""`` both mean "unset"."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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
        return cls(
            strategy=d.get("strategy", "manual"), selection=d.get("selection", "highest_regret")
        )


@dataclass
class SideEffects:
    """The side-effect surface a spec's workflow is allowed to touch (P1-3).

    ``repository`` — the workflow writes files inside the checkout (source, or derived data like
    ``apps/website/data.js``). ``external_services`` — it talks to Redis/Firebase/etc. Both default
    to ``False`` ("nothing asserted"), so specs authored before this field existed keep loading
    unchanged. The validator uses ``repository`` (alongside ``intent=mutate``) to reject a pure
    ``experiment`` that would modify the repository.
    """

    repository: bool = False
    external_services: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {"repository": self.repository, "external_services": self.external_services}

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> SideEffects:
        d = d or {}
        return cls(
            repository=bool(d.get("repository", False)),
            external_services=bool(d.get("external_services", False)),
        )


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

    # ── artifact identity (refactor-repair P1-3) ──────────────────────────────
    # Explicit, validated identity metadata. Defaults are the benign "nothing asserted"
    # values so the pre-P1-3 corpus (no such fields) loads and validates unchanged; the
    # P1-3 backfill writes the real values into each spec.
    artifact_kind: str = "experiment"  # experiment | workflow
    intent: str = "measure"  # measure | mutate (mutate = the workflow has source-modifying phases)
    side_effects: SideEffects = field(default_factory=SideEffects)
    repeatable: bool = True  # experiments are re-runnable; one-shot workflows are not
    sandboxed: bool = False  # runs in a disposable worktree, so mutations never touch the main tree

    # ── lifecycle (the status layer) ──────────────────────────────────────────
    # Authored in the YAML when known; otherwise derived by :mod:`instrument.spec_status`.
    # ``status`` is deliberately allowed to be "" (unset) so that the 63 committed specs,
    # none of which carry the field, keep loading and validating unchanged — the index
    # derives their status instead of the YAML asserting it.
    status: str = ""
    supersedes: list[str] = field(default_factory=list)  # spec name(s) this one replaces
    superseded_by: str | None = None  # the spec that replaced this one, if any
    completed_at: str | None = None  # ISO-8601 — when the spec's work was declared done
    last_run_at: str | None = None  # ISO-8601 — last observed run (index refreshes this)
    results_pointer: str | None = None  # repo-relative path to the latest run ledger

    @property
    def spec_id(self) -> str:
        """The ledger's ``spec_id`` for this spec: ``"<name>@<version>"``.

        ``spec_id`` has been declared in :data:`LEDGER_FIELDS` since the schema was
        written but was never actually emitted; this is the one canonical way to build
        it, so job and attempt records cannot drift into two different formats.
        """
        return f"{self.name}@{self.version}"

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
            # artifact identity — always emitted (like the lifecycle block) so the
            # serialized schema is stable for the index/registry consumers.
            "artifact_kind": self.artifact_kind,
            "intent": self.intent,
            "side_effects": self.side_effects.to_dict(),
            "repeatable": self.repeatable,
            "sandboxed": self.sandboxed,
            # lifecycle — always emitted so the serialized schema is stable for the
            # index/registry consumers, even when every value is at its unset default.
            "status": self.status,
            "supersedes": list(self.supersedes),
            "superseded_by": self.superseded_by,
            "completed_at": self.completed_at,
            "last_run_at": self.last_run_at,
            "results_pointer": self.results_pointer,
        }
        if self.comparison is not None:
            out["comparison"] = self.comparison.to_dict()
        if self.writeup is not None:
            out["writeup"] = self.writeup.to_dict()
        return out

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExperimentSpec:
        missing = [
            k
            for k in ("name", "question", "version", "workflow", "factors", "design")
            if k not in d
        ]
        if missing:
            raise ValueError(f"ExperimentSpec missing required fields: {missing}")

        # Unknown top-level keys used to be dropped silently, so a typo'd lifecycle key
        # (``supercedes:``) looked like it had been honoured. Warn instead: visible on the
        # CLI, catchable by ``pytest.warns``, and still non-fatal so an unrecognized key
        # from a newer spec version never bricks an older checkout.
        unknown = sorted(k for k in d if k not in SPEC_KEYS)
        if unknown:
            warnings.warn(
                f"spec {d.get('name', '<unnamed>')!r}: unknown top-level key(s) {unknown} "
                f"— ignored. Check for a typo, or add the field to ExperimentSpec.",
                UserWarning,
                stacklevel=2,
            )

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
            artifact_kind=str(d.get("artifact_kind") or "experiment"),
            intent=str(d.get("intent") or "measure"),
            side_effects=SideEffects.from_dict(d.get("side_effects")),
            repeatable=bool(d.get("repeatable", True)),
            sandboxed=bool(d.get("sandboxed", False)),
            status=str(d.get("status") or ""),
            supersedes=_as_name_list(d.get("supersedes")),
            superseded_by=_as_optional_str(d.get("superseded_by")),
            completed_at=_as_optional_str(d.get("completed_at")),
            last_run_at=_as_optional_str(d.get("last_run_at")),
            results_pointer=_as_optional_str(d.get("results_pointer")),
        )

    @classmethod
    def from_yaml(cls, path: Path) -> ExperimentSpec:
        with open(path) as f:
            return cls.from_dict(yaml.safe_load(f))

    def to_yaml(self, path: Path) -> None:
        path.write_text(yaml.dump(self.to_dict(), sort_keys=False))


def load_spec(path: Path) -> ExperimentSpec:
    """Load an ExperimentSpec from a YAML file (``experiments/definitions/*.yaml`` + ``workflows/**/*.yaml``)."""
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
            errors.append(f"duplicate rule name {rule.name!r}")
        seen.add(rule.name)
        if rule.plane not in PLANES:
            errors.append(
                f'rule "{rule.name}": plane {rule.plane!r} is not one of {sorted(PLANES)}'
            )
        if rule.evidence_class not in EVIDENCE_CLASSES:
            errors.append(
                f'rule "{rule.name}": evidence_class {rule.evidence_class!r} '
                f"is not one of {sorted(EVIDENCE_CLASSES)}"
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
                    f"or any measurement rule in this spec. Instrument it first."
                )
    return errors


def validate_spec(spec: ExperimentSpec) -> list[str]:
    """Structural validation plus the requires/produces gate. Empty list = valid."""
    errors: list[str] = []

    if spec.workflow.kind not in WORKFLOW_KINDS:
        errors.append(
            f"workflow.kind {spec.workflow.kind!r} is not one of {sorted(WORKFLOW_KINDS)}"
        )
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
            f"comparison.arm_factor {spec.comparison.arm_factor!r} is not a declared factor "
            f"({factor_names})"
        )

    for m in spec.metrics:
        if m.agg not in METRIC_AGGS:
            errors.append(f'metric "{m.name}": agg {m.agg!r} is not one of {sorted(METRIC_AGGS)}')
        if m.over not in METRIC_OVERS:
            errors.append(
                f'metric "{m.name}": over {m.over!r} is not one of {sorted(METRIC_OVERS)}'
            )

    if spec.adapt.strategy not in ADAPT_STRATEGIES:
        errors.append(
            f"adapt.strategy {spec.adapt.strategy!r} is not one of {sorted(ADAPT_STRATEGIES)}"
        )
    if spec.adapt.selection not in ADAPT_SELECTIONS:
        errors.append(
            f"adapt.selection {spec.adapt.selection!r} is not one of {sorted(ADAPT_SELECTIONS)}"
        )

    # Lifecycle gate: "" means unset (the index derives it) — any other value must be one
    # of the four defined states, so a spec can never claim a status nothing understands.
    if spec.status and spec.status not in SPEC_STATUSES:
        errors.append(f"status {spec.status!r} is not one of {sorted(SPEC_STATUSES)}")
    if spec.superseded_by is not None and spec.superseded_by == spec.name:
        errors.append(f"superseded_by {spec.superseded_by!r} points at the spec itself")
    if spec.name in spec.supersedes:
        errors.append(f"supersedes lists the spec itself ({spec.name!r})")

    # ── Artifact-identity gate (refactor-repair P1-3) ─────────────────────────
    # Identity is declared, not guessed. ``artifact_kind``/``intent`` are validated enums.
    if spec.artifact_kind not in ARTIFACT_KINDS:
        errors.append(
            f"artifact_kind {spec.artifact_kind!r} is not one of {sorted(ARTIFACT_KINDS)}"
        )
    if spec.intent not in INTENTS:
        errors.append(f"intent {spec.intent!r} is not one of {sorted(INTENTS)}")

    # An "experiment" is a pure measurement: it must not mutate source (``intent=mutate``) and
    # must not write to the repository (``side_effects.repository``). Such an artifact is a
    # workflow — declare ``artifact_kind: workflow`` — UNLESS it is explicitly ``sandboxed``
    # (runs in a disposable git worktree, so its mutations never touch the main tree). This is
    # the compiler-side half of "stop letting a substring classifier decide identity".
    if spec.artifact_kind == "experiment":
        reasons = []
        if spec.intent == "mutate":
            reasons.append("intent=mutate (source-modification phases)")
        if spec.side_effects.repository:
            reasons.append("side_effects.repository=true")
        if reasons and not spec.sandboxed:
            errors.append(
                f'artifact_kind "experiment" but {" and ".join(reasons)} — an experiment '
                f'measures, it does not modify the repository; declare artifact_kind "workflow" '
                f"or set sandboxed: true"
            )

    errors.extend(validate_rules(spec))
    return errors
