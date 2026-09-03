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

import hashlib
import json
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agentic_dynamics.core.contracts import (
    FactRequirement,
    normalize_requirement,
    validate_fact_contracts,
)

# ── Constants ───────────────────────────────────────────────────

WORKFLOW_KINDS = frozenset({"story", "task", "experiment", "agent_task"})
PLANES = frozenset({"measurement", "control"})
EVIDENCE_CLASSES = frozenset({"[M]", "[C]", "[H]", "[P]", "[X]"})
METRIC_AGGS = frozenset({"mean", "distribution", "ratio"})
METRIC_OVERS = frozenset({"outcome", "attempt", "job", "cell"})
ADAPT_STRATEGIES = frozenset({"coordinate_descent", "manual"})
ADAPT_SELECTIONS = frozenset({"highest_uncertainty", "highest_regret", "largest_effect"})

# ── The per-step scope model (D-16, proposal §5) ─────────────────────────────
#
# Every workflow phase MAY declare a ``scope:`` from a CLOSED five-scope vocabulary. Each
# scope resolves to a declared config (``results_mode`` / ``network`` / ``write_flag`` /
# ``capabilities``); the orchestrator's spawn-wrapper (``scripts/fleet/spawn_wrapper.py``)
# validates a spawn request against it BEFORE the docker socket call — a phase requesting an
# undeclared or unauthorized scope fails at validation, never at the socket (the isolation
# story's runtime half). Every scope's mounts stay a subset of the four-mount contract + the
# D-2 auth set (``results_mode`` is the only mount that varies, ro vs rw).

#: The closed five-scope vocabulary (proposal §5, D-16) — no others exist; a phase declaring
#: an undeclared scope is a validation error.
SCOPE_VOCABULARY: frozenset[str] = frozenset(
    {
        "research_readonly",
        "implementation",
        "review_readonly",
        "proposal_write",
        "adversarial_readonly",
    }
)

#: The declared config per scope (proposal §5 table, made machine-readable). ``results_mode``
#: is ro/rw over the results mount; ``network`` is the scope's allowed attachment (always
#: ``fleet-net`` — the cell net carries the retrieval stores + queue redis + sonar + egress);
#: ``write_flag`` says whether ``FINOPS_KB_WRITE=1`` MAY appear in the scope's env (only the
#: ``implementation`` scope, and only when the phase emits P1-P11); ``capabilities`` is the
#: descriptive closed what-it-may-do list.
SCOPE_CONFIGS: dict[str, dict[str, Any]] = {
    "research_readonly": {
        "results_mode": "ro",
        "network": "fleet-net",
        "write_flag": False,
        "capabilities": ("kb_read",),
    },
    "implementation": {
        "results_mode": "rw",
        "network": "fleet-net",
        "write_flag": True,
        "capabilities": ("run_code", "git_commit", "emit_findings"),
    },
    "review_readonly": {
        "results_mode": "rw",
        "network": "fleet-net",
        "write_flag": False,
        "capabilities": ("read_artifacts", "emit_review_records"),
    },
    "proposal_write": {
        "results_mode": "rw",
        "network": "fleet-net",
        "write_flag": False,
        "capabilities": ("assemble_docs", "git_commit"),
    },
    "adversarial_readonly": {
        "results_mode": "ro",
        "network": "fleet-net",
        "write_flag": False,
        "capabilities": ("read_only_attack",),
    },
}

#: The phase → scope authorization table (proposal §5's example, plus the implementation
#: workflow's own phases). A phase's DECLARED ``scope:`` in the spec wins over this table;
#: the table is the fallback the spawn-wrapper checks when the spec does not declare one. The
#: proposal's own ``fleet_ladder_plan`` phases (p1_research_infra/p2_research_kb_access →
#: research_readonly, p3_review → review_readonly, p4_proposal → proposal_write,
#: p5_adversarial → adversarial_readonly; the execution slices → implementation) are the
#: worked example the proposal cites.
PHASE_SCOPE_AUTHORIZATION: dict[str, str] = {
    "p1_research_infra": "research_readonly",
    "p2_research_kb_access": "research_readonly",
    "p3_review": "review_readonly",
    "p4_proposal": "proposal_write",
    "p5_adversarial": "adversarial_readonly",
    # the implementation workflow's own phases (the running example)
    "p0_pin_mandate": "proposal_write",
    "p1_slice1_base_supervisor": "implementation",
    "p2_slice1_workers_live": "implementation",
    "p3_slice2_orchestrator": "implementation",
    "p4_slice3_neo4j": "implementation",
    "p5_slice4_guards": "implementation",
    "p6_adversarial": "adversarial_readonly",
    "p7_smoke_handoff": "proposal_write",
    # the green_main_closure workflow's phases (the red-suite repair — repo edits + commits)
    "p1_review_authority": "implementation",
    "p2_publication_closure": "implementation",
    "p3_full_suite_guards": "implementation",
    "p4_final_verify": "implementation",
    # the admission_leases workflow's phases (the fail-closed spend gate)
    "p1_lease_registry": "implementation",
    "p2_admission_controller": "implementation",
    "p3_cost_provenance": "implementation",
    "p4_expiry_and_quarantine": "implementation",
    "p5_suite_and_closure": "implementation",
    # the fleet_job_submission workflow's phases (the submit verb + the base-image cache root)
    "p1_submit_contract": "implementation",
    "p2_launch_handler": "implementation",
    "p3_base_image_caching": "implementation",
    "p4_isolation_guards": "implementation",
    "p5_egress_proxy_enforcement": "implementation",
    # the 2026-09-01 gate restoration: the kind: test gate phases the recent specs regained
    # (degradation-review 3b.1 fix — a harness-run run_suite recording test_executed_success).
    # They verify the implementation's output inside the worktree, so they carry the
    # implementation scope like the phases they gate.
    "p3_test_gate": "implementation",
    "p5_test_gate": "implementation",
    "p6_test_gate": "implementation",
    # the docs_refresh_remediation workflow's phases (the drift rail's remediation — the
    # submit gate refused the queued remediation because these were missing, 2026-09-01)
    "p1_doc_findings": "implementation",
    "p2_context_claim": "implementation",
    "p3_mount_guard": "implementation",
    "p4_acceptance_gate": "research_readonly",
    # p2_launch_handler's own dry-run proof fixture (workflows/repository/
    # launch_handler_dry_run.yaml) — a trivial single no-op phase used to exercise the
    # submit -> validate -> launch -> board lifecycle end-to-end without spending a real
    # agent turn on anything but a no-op prompt.
    "p_launch_handler_noop": "implementation",
}

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

# ── Revision identity (w2 — completion follows the revision) ─────────────────
#
# ``workflow_revision_id`` is the canonicalized digest of a spec's *definition* — the
# structural YAML that says what work the spec does and how (name, version, the workflow
# block with its phases, factors, rules, stop, adapt, …). It deliberately EXCLUDES the
# lifecycle/metadata layer (``status``, supersedes pointers, run stamps, git/pricing pins):
# those are prose-or-bookkeeping, and the w2 rule is that prose never decides completion.
#
# Canonicalization drops comments and whitespace implicitly (YAML parse) and every
# authored-but-not-definitional key explicitly, then hashes a deterministic (sorted,
# compact) JSON rendering of what remains. A cosmetic edit (comment/whitespace) therefore
# leaves the digest untouched; a structural edit (a phase added, a gate appended, a rule
# changed) changes it — so an edited spec shows its own run state, never the earlier
# revision's completion.

#: Top-level spec keys that do NOT define the work and therefore never change the revision
#: digest. Authored lifecycle (the seed), authoring provenance, and generated stamps are
#: volatile; a revision is what the spec WOULD DO, which none of these keys change.
REVISION_VOLATILE_KEYS: frozenset[str] = frozenset(
    {
        "status",
        "supersedes",
        "superseded_by",
        "completed_at",
        "last_run_at",
        "results_pointer",
        "git_sha",
        "pricing_version",
        "generated_at",
    }
)


def _canonical_json(mapping: dict[str, Any]) -> str:
    """Deterministic compact JSON for a mapping: keys sorted at every level, no spaces.

    The one canonical text a given spec definition maps to, so the digest is stable across
    comment/whitespace/key-order edits and only changes when the definition itself does.
    """
    return json.dumps(mapping, sort_keys=True, separators=(",", ":"), default=str)


def canonical_spec_definition(spec: ExperimentSpec) -> dict[str, Any]:
    """The spec's *definitional* mapping — ``to_dict()`` minus the volatile/lifecycle keys.

    This is the canonicalization the revision digest hashes. Everything that defines what the
    workflow does is retained (name, question, version, workflow with its phases, factors,
    design, rules, metrics, comparison, writeup, stop, adapt, artifact identity, …); the
    lifecycle/authoring keys in :data:`REVISION_VOLATILE_KEYS` are dropped so editing them
    never re-keys a revision.
    """
    return {k: v for k, v in spec.to_dict().items() if k not in REVISION_VOLATILE_KEYS}


def compute_workflow_revision_id(spec: ExperimentSpec) -> str:
    """``sha256(canonicalized spec definition)`` — the identity a run's digest is keyed to.

    Stable across cosmetic edits (comments/whitespace vanish at parse, keys are sorted),
    changed by structural edits (a phase added, a gate appended). Exposed on the spec object
    as :attr:`ExperimentSpec.workflow_revision_id` and recorded on run ledgers + control-db
    runs, so completion can follow the revision rather than the prose.
    """
    text = _canonical_json(canonical_spec_definition(spec))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
        # I10 — the workflow-run ledger's typed checkpoint array (one CheckpointRecord per
        # checkpoint event: mechanical stop + resume-decided contract reads, with reason,
        # decision, approval_path, reached_at/decided_at, and the stop-point cost/token
        # summary). Additive: the run ledger emits it since I10; a rule may require it once a
        # measurement rule turns the records into derived signals (e.g. operator-await
        # latency for session-routing v2). Old ledgers lack the key — consumers read it via
        # ``.get("checkpoints", [])``.
        "checkpoints",
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
        # Cost provenance (admission_leases p3). The cost fields above are floats and cannot
        # express "no figure was reported" — these three say whether to believe them, and
        # they are what the admission gate reads before spending real per-token dollars.
        #   cost_source        — metered | estimated | unknown | reconciled
        #   estimation_method  — how, when estimated/reconciled (a closed vocabulary)
        #   reported_cost_usd  — the backend's verbatim figure; None = nothing reported,
        #                        0.0 = a reported zero. The pair with cost_inference is what
        #                        keeps a metered $0 distinguishable from an unmeasured one.
        #   settled_cost_usd / settlement_status — the post-run reconciliation against the
        #                        provider's meter (see ``control.settlement``).
        "cost_source",
        "estimation_method",
        "reported_cost_usd",
        "settled_cost_usd",
        "settlement_status",
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
    """A measurement rule (produces information) or control rule (consumes it).

    ``requires_facts`` (CAP I5, design §7.1) is the fact-level generalization of ``requires``:
    a NEW, additive field — ``requires`` (legacy ledger field names) is untouched, so every spec
    committed before this design keeps validating unchanged. A control rule binding to a
    decision-type contract (design §7.2) also names ``decision_type`` — the contract file
    ``experiments/contexts/<decision_type>.yaml`` the I4 Context Compiler loads.
    """

    name: str
    plane: str  # measurement | control
    evidence_class: str  # [M] [C] [H] [P] [X]
    requires: list[str] = field(default_factory=list)  # information this rule CONSUMES
    produces: list[str] = field(default_factory=list)  # information this rule EMITS
    requires_facts: list[FactRequirement] = field(default_factory=list)  # NEW (I5, design §7.1)
    decision_type: str = ""  # NEW (I5) — binds a control rule to a context contract (design §7.2)

    def __post_init__(self) -> None:
        # Normalize on EVERY construction path, not just from_dict() — a bare string or a plain
        # dict passed directly to the dataclass constructor (as `from_dict` itself does, and as
        # any other caller may) still becomes a real FactRequirement, so validate_fact_contracts
        # never has to guess at the entry's shape.
        self.requires_facts = [normalize_requirement(e) for e in self.requires_facts]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "plane": self.plane,
            "evidence_class": self.evidence_class,
            "requires": self.requires,
            "produces": self.produces,
            "requires_facts": [r.to_dict() for r in self.requires_facts],
            "decision_type": self.decision_type,
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
            requires_facts=[
                normalize_requirement(e) for e in d.get("requires_facts", []) or []
            ],
            decision_type=str(d.get("decision_type", "") or ""),
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

    @property
    def workflow_revision_id(self) -> str:
        """``sha256(canonicalized spec definition)`` — this spec's current revision digest.

        See :func:`compute_workflow_revision_id`. Completion follows this digest: a run
        ledger records the revision it executed, and ``spec_status`` only lets runs whose
        recorded revision equals the current digest certify the current definition.
        Computed on demand so it is always correct for any construction path.
        """
        return compute_workflow_revision_id(self)

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


def phase_scope(phase: dict[str, Any], *, phase_name: str | None = None) -> str | None:
    """Resolve a phase's authorized scope: its declared ``scope:``, else the authorization table.

    The resolution order is the spawn-wrapper's step-2 check in reverse: a phase's DECLARED
    ``scope:`` in the spec wins; when absent, :data:`PHASE_SCOPE_AUTHORIZATION` (the proposal's
    phase→scope example table) supplies the fallback. Returns ``None`` when neither is present —
    the spawn-wrapper then refuses the spawn at its step 2 (no phase is authorized for an
    undeclared scope by default; an authorization must exist, not be assumed).
    """
    declared = phase.get("scope") if isinstance(phase, dict) else None
    if declared in SCOPE_VOCABULARY:
        return declared
    name = phase_name or (phase.get("name") if isinstance(phase, dict) else None)
    if name:
        table_scope = PHASE_SCOPE_AUTHORIZATION.get(name)
        if table_scope in SCOPE_VOCABULARY:
            return table_scope
    return None


# ── The validator (the load-bearing gate) ───────────────────────


def validate_rules(
    spec: ExperimentSpec,
    *,
    fact_predicates: dict[str, Any] | None = None,
    fact_reducers: dict[str, Any] | None = None,
    fact_contracts: dict[str, Any] | None = None,
) -> list[str]:
    """Validate requires/produces. Returns a list of error strings (empty = valid).

    The available information is the ledger schema plus the ``produces`` of every
    measurement rule in the spec. A rule whose ``requires`` are not all available is
    refused — measurement first, policy second.

    The three ``fact_*`` keyword-only arguments are the CAP I5 gate (design §7.3,
    ``core.contracts.validate_fact_contracts``'s ``predicates``/``reducers``/``contracts``).
    They default to ``None``, which SKIPS the I5 gate entirely — ``experiment`` (tier 1) may
    not import ``control.facts``/``control.reducers`` (tier 2;
    ``tests/test_dependency_direction.py``'s ``test_experiment_does_not_import_control``), so
    the real registries cannot be supplied from inside this module. This keeps every spec
    committed before I5 validating byte-for-byte unchanged when ``validate_spec(spec)`` is
    called with no extra arguments (as ``compile_experiment.compile_spec`` already does
    everywhere). A caller in a tier that may see both ``core`` and ``control`` —
    ``control.context_compiler.validate_spec_fact_contracts`` — supplies the real
    ``FACT_PREDICATES``/``REDUCERS``/loaded contracts and is the actual I5 compile-time gate.
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

    if fact_predicates is not None and fact_reducers is not None:
        errors.extend(
            validate_fact_contracts(
                spec,
                predicates=fact_predicates,
                reducers=fact_reducers,
                contracts=fact_contracts,
            )
        )
    return errors


def _prose_safety_violations(spec: ExperimentSpec) -> list[str]:
    """Prose-vs-schema safety gate (review P1) — errors, or [].

    A phase whose prompt ORDERS an operator halt without declaring ``checkpoint: true``, or
    ISSUES a production firebase deploy command without declaring ``deploy_allowed: true``,
    is a safety requirement expressed in prose only — the runner's mechanical gates never
    engage, exactly the cap_site_revamp4_diagrams regression (its prompts said "STOP THE
    CAMPAIGN" / "ONLY AFTER the operator's signed approval" with no markers anywhere).

    Detection is deliberately narrow and tuned against the committed corpus:

    * CHECKPOINT: halt-instruction language — ``stop``/``halt``/``await`` within a short
      window of the operator/human + approval vocabulary. A line that mentions the
      machinery itself (the word ``checkpoint``) is never a halt instruction — the
      runner-hardening specs discuss the checkpoint phase kind as their subject.
    * DEPLOY: the same production-deploy command shapes the runner's gate matches
      (``firebase ... deploy`` / ``firebase --project <production-host>`` /
      ``firebase hosting deploy`` — kept in lockstep with
      :data:`agentic_dynamics.runtime.workflow_runner.DEPLOY_PATTERNS`, which cannot be
      imported here without a cycle), minus dry-runs and minus lines whose subject is the
      deploy gate itself (``deploy gate``/``DEPLOY_GATE``/``bypass``/``detection``/
      ``may run``/``implement``/``patterns``) — the hardening specs quote deploy commands
      while implementing their detection.

    The rule fires only for phases WITHOUT the marker — a phase that declares the marker
    is valid regardless of its prose (the runner's post-phase gates enforce the intent).
    """
    errors: list[str] = []
    # Lockstep with runtime.workflow_runner.DEPLOY_PATTERNS (:1060), narrowed to the repo's
    # actual production invocations: `firebase deploy --only ...` / `firebase --project
    # <production-host>`. A bare `firebase deploy` mention (the hardening specs' evasion
    # lists: "an alias, 'firebase --help > /dev/null && firebase deploy'") is prose ABOUT
    # commands, not a command — it carries no --only/--project, so it never matches here.
    # A leading negative lookbehind additionally skips quoted/backticked occurrences.
    deploy_patterns = [
        re.compile(r'(?<![\w`"\'])\bfirebase\b[^\n]*\bdeploy\b[^\n]*--only\b'),
        re.compile(
            r'(?<![\w`"\'])\bfirebase\b[^\n]*--project\s+'
            r"(?:agentic-dynamics|ai-finops-rulebook)\b"
        ),
    ]
    deploy_subject_excludes = ("--dry-run", "deploy gate", "DEPLOY_GATE")
    checkpoint_patterns = [
        re.compile(r"(?i)\bstop\b[^\n.]{0,80}\b(?:the\s+)?(?:operator|human)\b"),
        re.compile(r"(?i)\bhalt\b[^\n.]{0,80}\b(?:operator|human|approval|campaign)\b"),
        re.compile(
            r"(?i)\bawait(?:ing)?\s+(?:the\s+)?(?:operator|human)\b[^\n.]{0,60}\bapproval\b"
        ),
    ]
    for ph in spec.workflow.params.get("phases") or []:
        if not isinstance(ph, dict):
            continue
        name = ph.get("name", "?")
        prompt = ph.get("prompt") or ""
        for line in str(prompt).splitlines():
            if "checkpoint" in line:
                continue
            if not ph.get("checkpoint") and any(
                pat.search(line) for pat in checkpoint_patterns
            ):
                errors.append(
                    f'phase "{name}" orders an operator halt in prose '
                    f'("{line.strip()[:80]}") but does not declare checkpoint: true — '
                    f"the mechanical stop (cap_runner_hardening2) never engages"
                )
            if ph.get("deploy_allowed"):
                continue
            if any(exc in line for exc in deploy_subject_excludes):
                continue
            if any(pat.search(line) for pat in deploy_patterns):
                errors.append(
                    f'phase "{name}" issues a production deploy command in prose '
                    f'("{line.strip()[:80]}") but does not declare deploy_allowed: true — '
                    f"the deploy gate (cap_runner_hardening p2) never engages"
                )
    return errors


def validate_spec(
    spec: ExperimentSpec,
    *,
    fact_predicates: dict[str, Any] | None = None,
    fact_reducers: dict[str, Any] | None = None,
    fact_contracts: dict[str, Any] | None = None,
) -> list[str]:
    """Structural validation plus the requires/produces gate. Empty list = valid.

    The three ``fact_*`` keyword-only arguments thread straight through to
    :func:`validate_rules` (see its docstring) — ``None`` (the default) skips the CAP I5 gate,
    so every spec committed before I5 (and every existing ``validate_spec(spec)`` call site)
    validates unchanged.
    """
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

    # ── Phase-level gate: ``deploy_allowed`` (cap_runner_hardening p2) ────────
    # Optional per-phase marker, default false. The simpler honest rule: ANY phase may set it —
    # the runner's post-phase deploy gate enforces the intent (a phase that deploys without the
    # marker fails DEPLOY_GATE; a phase that carries it but never deploys is fine). The
    # validator's job here is type-safety only: a typo'd ``deploy_allowed: "true"``/``1`` would
    # silently disable the gate, so the marker, when present, must be a real boolean.
    for ph in spec.workflow.params.get("phases") or []:
        if not isinstance(ph, dict):
            continue
        if "deploy_allowed" in ph and not isinstance(ph.get("deploy_allowed"), bool):
            errors.append(
                f'phase "{ph.get("name", "?")}": deploy_allowed must be a boolean '
                f"(got {ph.get('deploy_allowed')!r})"
            )

    # ── Phase-level gate: ``checkpoint`` (cap_runner_hardening2 §Gap 3) ───────
    # Optional per-phase marker, default false. A ``checkpoint: true`` phase stops the run with
    # awaiting_operator_approval on success and gates resumes on the operator approval contract.
    # Same type-safety-only rule as ``deploy_allowed``: a typo'd string would silently make the
    # mechanical stop inert (the revamp3 violation), so it must be a real boolean.
    for ph in spec.workflow.params.get("phases") or []:
        if not isinstance(ph, dict):
            continue
        if "checkpoint" in ph and not isinstance(ph.get("checkpoint"), bool):
            errors.append(
                f'phase "{ph.get("name", "?")}": checkpoint must be a boolean '
                f"(got {ph.get('checkpoint')!r})"
            )

    # ── Phase-level gate: ``no_emit`` (kb_finding_layer k1) ─────────────
    # Optional per-phase marker, default false. Findings are the DEFAULT for workflow runs
    # (every successful committed phase emits its scoped finding); a phase that must not emit
    # opts out with ``no_emit: true`` — explicitly, never silently. Same type-safety-only rule
    # as ``deploy_allowed``/``checkpoint``: a typo'd ``no_emit: "false"`` is a truthy string
    # that would silently suppress a phase's finding (a KB data loss), so the marker, when
    # present, must be a real boolean.
    for ph in spec.workflow.params.get("phases") or []:
        if not isinstance(ph, dict):
            continue
        if "no_emit" in ph and not isinstance(ph.get("no_emit"), bool):
            errors.append(
                f'phase "{ph.get("name", "?")}": no_emit must be a boolean '
                f"(got {ph.get('no_emit')!r})"
            )

    # ── Phase-level gate: ``scope`` (D-16, proposal §5) ──────────────────
    # Optional per-phase scope from the closed five-scope vocabulary. A phase's declared scope
    # must be a real vocabulary member — a typo'd string is a scope the spawn-wrapper can never
    # authorize (its step-1 membership check fails), so catch it at spec load time instead of
    # leaving it to fail at spawn time. Membership only: the phase→scope *authorization* is the
    # spawn-wrapper's step-2 check (a phase may declare any vocabulary member; whether it is
    # *authorized* for it is what the spawn request's phase+scope pair is validated against).
    for ph in spec.workflow.params.get("phases") or []:
        if not isinstance(ph, dict):
            continue
        if "scope" in ph and ph.get("scope") not in SCOPE_VOCABULARY:
            errors.append(
                f'phase "{ph.get("name", "?")}": scope {ph.get("scope")!r} is not one of '
                f"{sorted(SCOPE_VOCABULARY)}"
            )

    # ── Phase-level gate: prose-required safety (review P1) ──────────────────
    # The principle: a safety requirement expressed only in natural-language prompt text is
    # ADVISORY; a safety requirement expressed in the workflow schema is ENFORCEABLE. A phase
    # that orders an operator halt ("STOP for the operator's approval") must declare
    # ``checkpoint: true`` (the mechanical stop), and a phase that issues a production deploy
    # command must declare ``deploy_allowed: true`` (the deploy gate) — otherwise the runner's
    # gates never engage. The detector is deliberately narrow: it flags halt-INSTRUCTION
    # language and deploy COMMANDS, never mentions of the machinery itself (lines that discuss
    # checkpoints/deploy gates as their subject are excluded, so the runner-hardening specs
    # stay valid). :func:`_prose_safety_violations` is the single implementation.
    errors.extend(_prose_safety_violations(spec))

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

    errors.extend(
        validate_rules(
            spec,
            fact_predicates=fact_predicates,
            fact_reducers=fact_reducers,
            fact_contracts=fact_contracts,
        )
    )
    return errors
