"""Execute an ``agent_task`` workflow — the ``execute`` phase of the spec/compiler DAG.

Drives an agent through a workflow's phases inside a git worktree, commits after each
phase, and records the ledger (tokens, cost, ``test_executed_success``) per phase. This
is the reusable-workflow engine: compile a spec, then run it against any goal / model /
worktree.

Phase kinds (from ``workflow.params.phases``):
  - ``agent`` (default) — invoke the LLM with the phase prompt. The prompt may use the
    ``{goal}`` and ``{prior_phases}`` placeholders. An agent phase may additionally declare
    ``test_gate: true`` to have the independent test_runner verify the worktree after the agent
    completes — its outcome lands on ``PhaseResult.test_executed_success`` (the CAP test-runner
    wiring seam, see docs/designs/current/cap_test_runner_wiring.md §1).
  - ``test`` — run the language's suite independently (via ``test_runner.run_suite``)
    and record ``test_executed_success``. No LLM involved.

Phase watchdog (cap_runner_hardening p1): each agent phase is wrapped in a stall monitor that
polls the phase's session transcript (``<workdir>/.instrument/session.jsonl``, appended live
by the adapters while the seam is present). A transcript whose last step is stale past the
threshold — resolved explicit ``phase_watchdog_min`` arg > ``FINOPS_PHASE_WATCHDOG_MIN`` env >
default 20 min — is SIGTERM'd and the phase fails with reason ``STALLED`` + the evidence
(last-step timestamp, stale age, transcript tail). Only step gaps count (the transcript's
last-step age, never wall time); test phases are never wrapped.

Deploy gate (cap_runner_hardening p2): after each agent phase, the runner scans the phase's
session transcript for firebase production-deploy commands. A phase not marked
``deploy_allowed: true`` (an optional per-phase marker, default false) that deployed fails with
reason ``DEPLOY_GATE`` + the offending command + its transcript line as evidence, recorded on
``PhaseResult.deploy_gate`` and the ledger — a deploy violation can never be committed.

Commit-prefix enforcement (cap_runner_hardening p3): after each agent phase, the runner lists
the commits made during the phase (``git log pre-head..HEAD``) and every one must match
``[workflow] <phase> — <goal prefix>`` — the exact pattern the resume machinery matches. A
plain-message commit fails the phase with reason ``COMMIT_PREFIX`` + the offending subjects as
evidence, even if the phase otherwise succeeded (the campaign stops for the operator), recorded
on ``PhaseResult.commit_gate`` and the ledger. The runner's own ``_git_commit`` writes the
correct message; the enforcement catches MANUAL agent commits. Two-line defense (the
drawing-board fix, 2026-08-28): a commit-msg hook installed before each agent phase rewrites
any non-conforming subject to the canonical pattern AT COMMIT TIME (the agent cannot deviate),
and the gate backstops pre-hook commits with a proper noninteractive history rewrite —
``git filter-branch`` + a deterministic msg-filter over the phase range, exact-SHA scoped,
tree-preserving, re-read + fail-strict on any remainder. ``FINOPS_COMMIT_GATE=strict``
restores the fail-with-evidence mode (no hook, no rewrite); see ``_enforce_commit_prefix``.

Relabel tree-identity gate (cap_runner_hardening2 §Gap 2): after each agent phase (kind !=
``test``), the runner compares the phase's committed tree against the discarded-trees ledger
(``experiments/results/workflows/<spec>/discarded_trees.jsonl`` — the reset/rollback path
records every tree it discards, keyed ``(spec, branch, tree_hash, discarded_at)``). A tree
that was discarded and is now re-presented as this phase's fresh work — the revamp2 shape,
``git diff f6fc35edf 20eeb801b`` is empty — fails the phase with reason ``RELABEL`` + the
identical-tree proof (both hashes + the matching discarded-tree record), recorded on
``PhaseResult.relabel_gate`` and the ledger. Strict by construction: a tree violation is NEVER
canonicalized (unlike a message-only COMMIT_PREFIX violation). The operator-approval escape
(the legit-reuse path): an approval artifact (``approvals/<spec>/<phase>_tree_reuse.md``)
committed BEFORE the phase (so it is present in the tree at the phase's pre-head) that names
the tree hash + the phase + a REAL operator signature + a date authorizes the reuse and the
gate passes. The compared tree EXCLUDES the ``approvals/`` subtree — scaffolding never changes
the identity of the work underneath, and a relabel cannot dodge the gate by burying the discard
under an approval-shaped commit. The gate is off for non-agent phases and the runner's own
``_git_commit`` path is exempt by construction (it never consults the ledger; the gate is a
separate post-phase check on the phase's committed tree).

Mechanical human checkpoint (cap_runner_hardening2 §Gap 3): a phase declaring ``checkpoint: true``
that completes successfully records the campaign state ``awaiting_operator_approval`` and EXITS
CLEANLY — the phase status is ``awaiting`` (a designed stop, not an error; the run result carries
``awaiting: true`` + the phase name, and the ledger writes the awaiting state). The run's
terminal state is ``awaiting_approval`` (``WorkflowRunResult.state`` — ``ok`` stays ``False`` as
the terminal-success bool, but the spec index derives ``awaiting_approval``, never ``failed``,
for a paused run). The approval
contract: ``approvals/<spec>/<phase>_approval.md`` must exist in the worktree, carry a REAL
operator signature (a non-placeholder ``operator:``/``SIGNED-BY-OPERATOR:`` line + a real date),
and its commit must be a DESCENDANT of the checkpoint phase's commit (the approval was authored
after the checkpoint's work — a signed-before-the-work artifact does not authorize it). On
``--resume`` the runner checks the contract for every completed checkpoint phase BEFORE proceeding:
no artifact / placeholder signature / wrong commit order → the run stops again with
``awaiting_operator_approval`` (refuses to proceed); a valid contract → proceeds. The revamp3
violation — p2 committed the delta preview AND the unsigned approval template, then the runner
moved straight into p3-p6 and recorded ``ok: True`` — is mechanically impossible: the unsigned
template fails the placeholder check, and an approval committed WITH the checkpoint work fails the
descendant-order check.

The third hardening-2 mechanism — the server-level ORPHAN sweep — does not live in this runner:
an orphaned delegation (a parent session that died mid-task, its completed subagent never reaped)
lives in the opencode SERVER layer, which the runner never observes (it watches its own agent
process). It is implemented in ``agentic_dynamics/control/orphan_sweep.py`` + ``scripts/orphan_sweep.py``
(flag-only, default 5-min cadence, CLI ``agentic-dynamics supervise orphans``) — see
``docs/designs/current/cap_runner_hardening2_design.md`` §Gap 1.

The agent works directly in ``workdir``; prior-phase artifacts are committed there, so
later phases read them from the repo. Fails fast by default (``stop_on_error``).

The ``retrieve -> construct -> render`` augmentation and its default store/constructor
wiring live in :mod:`instrument.augment` (R7 split); this module keeps phase execution
plus the opt-in self-build emit (``rag_params.emit_self``).

RAG scope isolation (the load-bearing invariant): by default the retrieval filter is
scoped per cell — :func:`cell_scope` yields ``self-<worktree basename>`` (the cell
identity), overridden by ``FINOPS_CELL_ID`` when set — so an augmented cell reads only
its own worktree's knowledge, never the global store. ``run_workflow`` defaults both
``repository_id`` and ``acl_scope`` to that cell scope *before* the retrieve fn is
built, whenever ``rag_augment`` is enabled and ``repository_id`` is empty. An
explicitly non-empty ``rag_params.repository_id`` is preserved unchanged — that is the
*shared-scope* override for coordinated parallel workstreams. The empty scope must
never again mean "global".
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from agentic_dynamics.adapters.backends import run_agentic
from agentic_dynamics.core.admission_context import AdmissionRefused
from agentic_dynamics.core.language import build_code_snapshot, compute_code_delta, detect_language
from agentic_dynamics.core.paths import PROJECT_ROOT
from agentic_dynamics.experiment.experiment_spec import ExperimentSpec, validate_spec
from agentic_dynamics.knowledge.augment import (
    DEFAULT_INHERITED_TOOLS,
    augment_prompt,
    default_construct_fn,
    default_retrieve_fn,
)
from agentic_dynamics.measurement.commit_analysis import _read_commit_files
from agentic_dynamics.measurement.lsp_diagnostics import new_error_count, run_diagnostics
from agentic_dynamics.measurement.sonar import (
    SONAR_STATUS_AVAILABLE,
    SONAR_STATUS_STALE_REFUSED,
    SONAR_STATUS_UNAVAILABLE,
    fetch_sonar_issues,
    new_issue_count,
    project_key_for,
    run_sonar_analysis,
)
from agentic_dynamics.runtime.admission import PhaseAdmission, phase_admission_scope
from agentic_dynamics.runtime.change_analyzer import (
    ChangeAnalyzer,
    ChangeInput,
    run_change_analysis,
)

# Routing + telemetry are consumed through the runtime-owned contracts (refactor-repair
# Debt-2): the ``Router`` decision and the ``TelemetryPublisher`` are injected at the
# composition root (``scripts/run_workflow.py``), so this module never imports ``control``.
from agentic_dynamics.runtime.routing import (
    ModelSignals,
    Router,
    RouteState,
    RoutingPreferences,
    resolve_pool,
    validate_workflow_routing,
)
from agentic_dynamics.runtime.telemetry import TelemetryPublisher
from agentic_dynamics.runtime.test_runner import run_suite, suite_succeeded


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PhaseResult:
    """Ledger record for one phase of a workflow run."""

    phase: str
    kind: str  # agent | test
    status: str  # ok | failed
    # ``spec_id`` ("<name>@<version>") has been declared in LEDGER_FIELDS since the schema
    # was written but was never emitted, so an attempt record could not be traced back to
    # the exact spec *version* that produced it. Built once via ExperimentSpec.spec_id.
    spec_id: str = ""
    model: str = ""
    duration_s: float = 0.0
    commit_hash: str = ""
    error: str = ""
    # agent phases
    tokens: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cache_hit_rate: float = 0.0
    session_id: str = ""
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    final_response: str = ""
    confidence: float | None = None  # [H] execution-confidence signal (agent phases)
    # augmentation provenance (populated only when rag_augment is enabled)
    raw_prompt_hash: str = ""
    pre_phase_commit: str = ""
    retrieval_attempt_id: str = ""
    constructor_attempt_id: str = ""
    selected_evidence_ids: list[str] = field(default_factory=list)
    augmentation_versions: dict[str, str] = field(default_factory=dict)
    augmentation_tokens: dict[str, int] = field(default_factory=dict)
    augmentation_cost_usd: float = 0.0
    augmentation_latency_ms: float = 0.0
    fallback_mode: str = ""
    # test phases
    test_executed_success: bool | None = None
    tests_passed: int = 0
    tests_total: int = 0
    # phase-boundary evidence (populated only when a change_analyzer is injected; design §5.7)
    change_analysis: dict[str, Any] | None = None
    # per-phase opt-in: the phase MUST deliver a tree change (NO_CHANGES gate —
    # the revamp3 vacuous-pass post-mortem); off by default
    requires_deliverable: bool = False
    #: cap_runner_hardening p1: when the phase watchdog SIGTERM'd a stalled agent, the
    #: structured evidence (last-step timestamp, stale age, transcript tail). None otherwise.
    stall_evidence: dict[str, Any] | None = None
    #: cap_runner_hardening p2: when the deploy gate fired — the phase is not marked
    #: ``deploy_allowed`` yet its session transcript shows a firebase production-deploy
    #: command — the structured evidence (reason + offending commands + transcript lines).
    #: None otherwise.
    deploy_gate: dict[str, Any] | None = None
    #: cap_runner_hardening p3: when commit-prefix enforcement fired — a commit the agent made
    #: during the phase does not match ``[workflow] <phase> — <goal prefix>`` (the exact pattern
    #: the resume machinery matches) — the structured evidence (reason + offending subjects).
    #: None otherwise.
    commit_gate: dict[str, Any] | None = None
    #: cap_runner_hardening2 p2: when the relabel tree-identity gate fired (or approved) — the
    #: phase's committed tree matches a recorded discarded tree for this spec+branch. The
    #: structured evidence (reason RELABEL / APPROVED, phase tree hash, the matching discarded-
    #: tree record, the identical-tree proof, the approval verdict). A RELABEL flips the phase
    #: to failed; an approved reuse keeps it ok. None otherwise.
    relabel_gate: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "kind": self.kind,
            "status": self.status,
            "spec_id": self.spec_id,
            "model": self.model,
            "duration_s": self.duration_s,
            "commit_hash": self.commit_hash,
            "error": self.error,
            "tokens": self.tokens,
            "cost_usd": self.cost_usd,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "cache_hit_rate": self.cache_hit_rate,
            "session_id": self.session_id,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "confidence": self.confidence,
            # augmentation provenance — persisted structured, never in-memory-only
            "raw_prompt_hash": self.raw_prompt_hash,
            "pre_phase_commit": self.pre_phase_commit,
            "retrieval_attempt_id": self.retrieval_attempt_id,
            "constructor_attempt_id": self.constructor_attempt_id,
            "selected_evidence_ids": self.selected_evidence_ids,
            "augmentation_versions": self.augmentation_versions,
            "augmentation_tokens": self.augmentation_tokens,
            "augmentation_cost_usd": self.augmentation_cost_usd,
            "augmentation_latency_ms": self.augmentation_latency_ms,
            "fallback_mode": self.fallback_mode,
            "test_executed_success": self.test_executed_success,
            "tests_passed": self.tests_passed,
            "tests_total": self.tests_total,
            "change_analysis": self.change_analysis,
            "stall_evidence": self.stall_evidence,
            "deploy_gate": self.deploy_gate,
            "commit_gate": self.commit_gate,
            "relabel_gate": self.relabel_gate,
        }


class RunState(str, Enum):
    """Terminal run-state vocabulary (added by the awaiting-approval fix, P1).

    ``WorkflowRunResult.ok`` used to collapse a correctly-paused checkpoint run (phase
    status ``awaiting``, ``result.awaiting == True``) into ``ok: False``, which the spec
    index then derived as ``failed`` — a designed stop for the operator was being read as
    a failure. ``state`` is the lossless terminal label; ``ok`` and ``awaiting`` remain as
    convenience fields (ledger JSON consumers and the spec index read them).
    """

    SUCCEEDED = "succeeded"
    AWAITING_APPROVAL = "awaiting_approval"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowRunResult:
    """Ledger for a full workflow run."""

    spec_name: str
    model: str
    workdir: str
    goal: str
    phases: list[PhaseResult] = field(default_factory=list)
    #: ``"<name>@<version>"`` — the job-level ``spec_id`` of LEDGER_FIELDS. ``spec_name``
    #: alone cannot distinguish two runs of the same spec across a version bump; this can.
    spec_id: str = ""
    git_sha: str = ""
    started_at: str = ""
    ended_at: str = ""
    #: cap_runner_hardening2 §Gap 3 — the mechanical human checkpoint. ``awaiting`` is True when
    #: the run stopped at a checkpoint phase (or a resume refused to proceed past an unsatisfied
    #: one) with the campaign state ``awaiting_operator_approval`` — a designed stop, never an
    #: error. ``awaiting_phase`` names the phase; ``awaiting_reason`` is ``"checkpoint"`` (a
    #: fresh stop) or ``"approval_refused"`` (a resume refused). The derived :attr:`state` is
    #: ``awaiting_approval`` whenever this is True (P1 — the spec index must not read the run as
    #: ``failed`` because ``ok`` collapsed).
    awaiting: bool = False
    awaiting_phase: str = ""
    awaiting_reason: str = ""
    #: I10 — typed checkpoint capture (the session-routing v2 prerequisite). Every checkpoint
    #: event this run produced, in chronological order: the mechanical stop (a ``checkpoint:
    #: true`` phase completing → awaiting_operator_approval) and every resume-decided contract
    #: read (approved/rejected) for a completed checkpoint phase. A run that never touched a
    #: checkpoint carries an empty list — additive, never a re-shape of the per-phase ledger.
    #: The record is written BEFORE the run exits so the resume machinery (and the spec index
    #: / ``checkpoint/v1`` reducer) can read the last checkpoint state.
    checkpoints: list[CheckpointRecord] = field(default_factory=list)
    #: ledger_instrumentation p1 — the attempt-level ledger, one :class:`AttemptRecord` per
    #: agent phase (the model invocation). Additive: a run that made no agent phases carries an
    #: empty list; old ledgers lack the key and parse unchanged via ``.get("attempts", [])``.
    attempts: list[AttemptRecord] = field(default_factory=list)

    @property
    def total_cost_usd(self) -> float:
        return round(sum(p.cost_usd for p in self.phases), 6)

    @property
    def ok(self) -> bool:
        """Terminal-success bool: every phase recorded ``ok`` AND at least one phase ran.

        A correctly-paused checkpoint run (``awaiting``) is ``False`` here even though it is
        a designed stop, not an error — prefer :attr:`state` for the lossless terminal label
        (``awaiting_approval``), which the spec index now derives instead of ``failed``.
        """
        return bool(self.phases) and all(p.status == "ok" for p in self.phases)

    @property
    def state(self) -> str:
        """The run's terminal state as a :class:`RunState` value (the lossless label).

        Precedence (P1 — awaiting is a designed stop, never a failure):

        1. ``awaiting``         → ``awaiting_approval`` (checkpoint stop or a resume
           refused past an unsatisfied checkpoint);
        2. all phases ``ok``    → ``succeeded`` (identical condition to :attr:`ok`);
        3. any phase not ok     → ``failed`` (only when not awaiting);
        4. nothing ran          → ``cancelled`` (a resume whose every phase was already
           completed, or an aborted launch — no work was performed by this run, so it is
           neither a success nor a failure).

        ``ok == (state == RunState.SUCCEEDED.value)`` — the terminal-success bool stays
        the same for every run the ledger already records.
        """
        if self.awaiting:
            return RunState.AWAITING_APPROVAL.value
        if self.ok:
            return RunState.SUCCEEDED.value
        if self.phases:
            return RunState.FAILED.value
        return RunState.CANCELLED.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_name": self.spec_name,
            "spec_id": self.spec_id,
            "model": self.model,
            "workdir": self.workdir,
            "goal": self.goal,
            "git_sha": self.git_sha,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "awaiting": self.awaiting,
            "awaiting_phase": self.awaiting_phase,
            "awaiting_reason": self.awaiting_reason,
            # ADDED key (I10 — never renames an existing key): the typed checkpoint ledger,
            # one record per checkpoint event (mechanical stop + resume-decided contract
            # reads). Old ledgers lack the key; consumers read it via ``.get("checkpoints",
            # [])`` so the 2d/2c-era ledgers + spec_status + this module's own tests parse
            # unchanged.
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            # ADDED key (P1 — never renames an existing key): the lossless terminal state,
            # so a checkpoint-paused run is distinguishable from a genuine failure on the
            # ledger without breaking consumers that read ``ok``/``awaiting``.
            "state": self.state,
            # ADDED keys (ledger_instrumentation p1 — never renames an existing key): the
            # attempt-level ledger. The schema's declared-but-never-written attempt fields
            # (``retry_reason`` / ``first_pass`` / ``accepted`` / ``escalation_from`` /
            # ``escalation_to``) plus the ``attempt_count`` the retry-rate metric consumes are
            # now emitted, one :class:`AttemptRecord` per agent phase. Old ledgers lack these
            # keys; consumers read them via ``.get("attempts", [])`` / ``.get("attempt_count",
            # 0)`` so pre-instrumentation ledgers parse unchanged.
            "attempts": [a.to_dict() for a in self.attempts],
            "attempt_count": len(self.attempts),
            "total_cost_usd": self.total_cost_usd,
            "ok": self.ok,
            "phases": [p.to_dict() for p in self.phases],
        }


@dataclass
class AttemptRecord:
    """One attempt of one agent phase, in the schema's attempt-level field vocabulary.

    The workflow runner makes EXACTLY one attempt per agent phase — it never retries a phase
    and never escalates a model mid-phase (per-step *routing* switches the selected model, but
    that is not a *retry* and never produces a second attempt). This record therefore pins the
    honest values: ``attempt_number`` is always 1, ``retry_reason`` is always empty, and
    ``escalation_from`` / ``escalation_to`` are always ``None``. It exists so the attempt-level
    fields the schema declares (``experiment_spec.LEDGER_FIELDS``) but the runtime never wrote —
    the workflow-metrics finding "declared-not-written" — become MEASURABLE on the committed
    ledger. The values are truthful ("no retry happened, no escalation happened"), never
    fabricated. Field names + semantics are pinned to ``LEDGER_FIELDS``.

    ``first_pass`` and ``accepted`` are derived from the phase's final status (recorded AFTER
    the phase loop resolves, so a checkpoint phase's ``awaiting`` status is already final):

    * ``first_pass`` — True when the single attempt did NOT fail (``status != "failed"``). A
      checkpoint phase reaches ``awaiting`` only after its work passed every gate and
      committed, so that is a first-pass success, not a failure.
    * ``accepted`` — True only when the outcome was accepted (``status == "ok"``). ``awaiting``
      (a designed stop pending operator approval) and ``failed`` are not accepted outcomes.
    """

    attempt_id: str
    job_id: str
    phase: str
    attempt_number: int = 1
    parent_attempt_id: str | None = None
    retry_reason: str = ""
    first_pass: bool | None = None
    accepted: bool | None = None
    escalation_from: str | None = None
    escalation_to: str | None = None
    model: str = ""
    status: str = ""
    cost_usd: float = 0.0
    tokens: dict[str, int] = field(default_factory=dict)
    test_executed_success: bool | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the attempt record. ``None`` fields stay ``None`` (null-not-zero)."""
        return {
            "attempt_id": self.attempt_id,
            "job_id": self.job_id,
            "phase": self.phase,
            "attempt_number": self.attempt_number,
            "parent_attempt_id": self.parent_attempt_id,
            "retry_reason": self.retry_reason,
            "first_pass": self.first_pass,
            "accepted": self.accepted,
            "escalation_from": self.escalation_from,
            "escalation_to": self.escalation_to,
            "model": self.model,
            "status": self.status,
            "cost_usd": self.cost_usd,
            "tokens": dict(self.tokens),
            "test_executed_success": self.test_executed_success,
            "confidence": self.confidence,
        }


def _build_phase_prompt(phase: dict[str, Any], goal: str, prior: list[str]) -> str:
    prompt = str(phase.get("prompt", ""))
    prior_summary = "\n".join(f"- {p}" for p in prior) if prior else "(none)"
    return prompt.replace("{goal}", goal).replace("{prior_phases}", prior_summary)


def _git_commit(workdir: Path, phase: str, goal: str) -> str:
    """Stage and commit the worktree; return the short hash, or "" if nothing to commit.

    ``.instrument/`` (the runner's own session transcripts) is excluded from the snapshot
    via a pathspec so ephemeral transcripts stop entering history (docs/routing_next_steps.md
    item 5.1). The exclusion is explicit here rather than relying on ``.gitignore``, since a
    fresh worktree may not yet carry the repo's ignore rules.
    """
    try:
        subprocess.run(
            ["git", "add", "-A", "--", ":(exclude).instrument"],
            cwd=workdir, capture_output=True, timeout=60,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=workdir, capture_output=True
        )
        if staged.returncode == 0:
            return ""
        msg = f"[workflow] {phase} — {goal[:60]}"
        c = subprocess.run(["git", "commit", "-q", "-m", msg], cwd=workdir, capture_output=True, timeout=120)
        if c.returncode != 0:
            return ""
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=workdir, capture_output=True, text=True)
        return h.stdout.strip()
    except Exception:
        return ""


def _git_head(workdir: Path) -> str:
    try:
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=workdir, capture_output=True, text=True)
        return h.stdout.strip()
    except Exception:
        return ""


def _git_full_sha(workdir: Path, rev: str) -> str:
    """Resolve ``rev`` to its full 40-char SHA, or "" when unresolvable.

    The phase-boundary evidence loop keys snapshot revisions and version ids off the FULL
    commit SHA (design §5.7 provenance — a short hash is display-only); the displayed
    ``PhaseResult.commit_hash`` stays short.
    """
    try:
        h = subprocess.run(
            ["git", "rev-parse", rev], cwd=workdir, capture_output=True, text=True, timeout=30
        )
        if h.returncode == 0:
            return h.stdout.strip()
    except Exception:
        pass
    return ""


#: Client-side deadline for the sonar + lsp analyzer legs (cap_2a rerun2 p1, carried from the
#: rerun). A stalled sonar-scanner, a hung mypy, or a server that never answers must degrade to
#: its measured unavailable status within this envelope, never hang the phase (the first
#: campaign's hang lesson). ``run_sonar_analysis``'s own subprocess timeout is 300s, so 360s
#: lets a real scan complete while still bounding a pathological hang; ``run_diagnostics`` is
#: bounded to ~120s internally, well under this envelope. Tests shrink this constant to prove
#: the deadline.
ANALYZER_LEG_TIMEOUT_SECONDS = 360.0

# ── Phase watchdog (cap_runner_hardening p1) ──────────────────────────────────────────────
#
# The measured execution disease: agents that go silent for 45-65 minutes while staying alive
# (no session steps, idle CPU) — the stabilization p3 stall, the two terra stalls in both site
# revamps. The runner previously waited on the opencode process indefinitely. The watchdog is
# the technical, deterministic fix: it monitors the phase's session transcript (the worktree's
# ``.instrument/session.jsonl``, appended live by the adapters while the seam is present) and
# fails the phase once the transcript's LAST STEP is stale past the threshold — not wall time,
# so a phase that keeps producing steps never fires no matter how long it runs. A stalled agent
# is SIGTERM'd (exit ``-15``, the measured signature) and the phase fails with reason
# ``STALLED`` + evidence (last-step timestamp, stale age, transcript tail).
#
# Threshold resolution: explicit ``phase_watchdog_min`` argument > ``FINOPS_PHASE_WATCHDOG_MIN``
# env > ``PHASE_WATCHDOG_DEFAULT_MIN`` (20 — below the observed 45-65-min stalls, above any
# legit step gap, the longest observed ~10 min). A value <= 0 disables the watchdog for the run.
PHASE_WATCHDOG_ENV = "FINOPS_PHASE_WATCHDOG_MIN"
PHASE_WATCHDOG_DEFAULT_MIN = 20.0


def _call_with_deadline(fn: Callable[[], Any], *, timeout: float) -> tuple[bool, Any]:
    """Run ``fn`` in a single worker thread under a hard client-side deadline.

    Returns ``(returned, result)``. ``returned`` is False on a timeout (the worker is abandoned
    and keeps running in the background — the same discipline the graph leg uses) or on any
    raised exception; ``result`` is the call's return value on success. A non-returning analyzer
    can never hang the phase: the deadline degrades it to its measured unavailable status in the
    caller.
    """
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return True, pool.submit(fn).result(timeout=timeout)
    except FuturesTimeout:
        return False, None
    except Exception:  # noqa: BLE001 — an analyzer error is a state, never a crash
        return False, None
    finally:
        pool.shutdown(wait=False)


def _materialize_revision(wd: Path, rev: str) -> Path | None:
    """Check out ``rev`` into a fresh detached worktree under /tmp for the analyzer legs.

    The sonar scanner and mypy both need a real on-disk tree for the PARENT revision (the
    worktree itself is already at the phase commit). Returns the checkout path, or ``None`` when
    the revision cannot be materialized — the sonar/lsp legs then degrade to their measured
    unavailable status (null-not-zero, never a fabricated delta). The caller must remove the
    checkout with :func:`_remove_materialized_revision`.
    """
    tmp = Path(tempfile.mkdtemp(prefix="wf_analyzer_", dir="/tmp"))
    checkout = tmp / "tree"
    try:
        proc = subprocess.run(
            ["git", "worktree", "add", "--detach", str(checkout), rev],
            cwd=str(wd), capture_output=True, timeout=120,
        )
    except Exception:  # noqa: BLE001 — materialization is best-effort, never a gate
        shutil.rmtree(tmp, ignore_errors=True)
        return None
    if proc.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        return None
    return checkout


def _remove_materialized_revision(wd: Path, checkout: Path | None) -> None:
    """Remove a materialized revision and its temp parent (idempotent — ``None`` is a no-op)."""
    if checkout is None:
        return
    with contextlib.suppress(Exception):
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(checkout)],
            cwd=str(wd), capture_output=True, timeout=60,
        )
    with contextlib.suppress(Exception):
        shutil.rmtree(checkout.parent, ignore_errors=True)


def _sonar_evidence(
    wd: Path, parent_checkout: Path | None, parent_rev: str, full_rev: str
) -> dict[str, Any]:
    """v2: the severity-filtered, change-introduced critical-issue count (design §2 RC1, §3).

    Runs/fetches the revision-scoped analysis for BOTH the parent and the phase commit (fresh
    scans are fetch-first, so an already-analyzed parent is reused), pulls each revision's
    per-issue records filtered server-side to ``{BLOCKER, CRITICAL}``, and counts issues
    introduced by the change under the ``(rule, file_path, line)`` identity rule. Runs under the
    hard deadline; a non-returning or raising leg degrades to a measured
    ``{"status": "unavailable"}`` payload (count omitted — null-not-zero, never a fabricated 0).

    The evidence shape matches the reducer's ``sonar_analysis`` contract verbatim:
    ``{"status", "revision_matches"|None, "new_critical_count"|None, "analyzed_sha"}``.
    """
    if parent_checkout is None:
        return {"status": SONAR_STATUS_UNAVAILABLE, "revision_matches": None,
                "new_critical_count": None, "analyzed_sha": ""}

    parent_key = project_key_for(wd, parent_rev)
    after_key = project_key_for(wd, full_rev)

    def _leg() -> dict[str, Any]:
        # ``project_key`` is passed explicitly for the parent so its key stays consistent with
        # the phase revision's (same worktree base, different rev prefix) — otherwise the temp
        # checkout's dir name would produce a different, non-comparable key.
        before = run_sonar_analysis(str(parent_checkout), project_key=parent_key, revision=parent_rev)
        after = run_sonar_analysis(str(wd), revision=full_rev)
        before_status = getattr(before, "status", SONAR_STATUS_UNAVAILABLE)
        after_status = getattr(after, "status", SONAR_STATUS_UNAVAILABLE)
        # A stale-refused or unavailable revision cannot produce a before/after delta — fail
        # closed with the measured status (null-not-zero, never a fabricated 0).
        if before_status != SONAR_STATUS_AVAILABLE or after_status != SONAR_STATUS_AVAILABLE:
            status = SONAR_STATUS_STALE_REFUSED if (
                before_status == SONAR_STATUS_STALE_REFUSED
                or after_status == SONAR_STATUS_STALE_REFUSED
            ) else SONAR_STATUS_UNAVAILABLE
            revision_matches = (
                True if status == SONAR_STATUS_AVAILABLE
                else False if status == SONAR_STATUS_STALE_REFUSED
                else None
            )
            return {"status": status, "revision_matches": revision_matches,
                    "new_critical_count": None, "analyzed_sha": getattr(after, "analyzed_sha", "")}

        before_issues = fetch_sonar_issues(parent_key, severities="BLOCKER,CRITICAL")
        after_issues = fetch_sonar_issues(after_key, severities="BLOCKER,CRITICAL")
        count = new_issue_count(before_issues, after_issues)
        return {
            "status": SONAR_STATUS_AVAILABLE,
            "revision_matches": True,
            "new_critical_count": count,
            "analyzed_sha": getattr(after, "analyzed_sha", "") or full_rev,
        }

    returned, result = _call_with_deadline(_leg, timeout=ANALYZER_LEG_TIMEOUT_SECONDS)
    if not returned or result is None:
        return {"status": SONAR_STATUS_UNAVAILABLE, "revision_matches": None,
                "new_critical_count": None, "analyzed_sha": ""}
    return result


def _lsp_evidence(
    wd: Path, parent_checkout: Path | None, parent_rev: str, full_rev: str, profile: Any
) -> dict[str, Any]:
    """v2: the change-introduced ERROR diagnostics count (design §4).

    Runs mypy (``tool_name="python_mypy"``) at the parent and the phase commit, then counts
    error-severity diagnostics introduced by the change under the ``(file, line, code)`` identity
    rule. Warnings/info/hints never count. Runs under the hard deadline; a non-returning or
    raising tool degrades to a measured ``{"status": "unavailable"}`` payload (count omitted).

    The evidence shape matches the reducer's ``lsp_analysis`` contract verbatim:
    ``{"status", "new_error_count"|None, "tool"}``.
    """
    if parent_checkout is None:
        return {"status": "unavailable", "new_error_count": None, "tool": "mypy"}

    def _leg() -> dict[str, Any]:
        before = run_diagnostics(parent_checkout, profile, tool_name="python_mypy")
        after = run_diagnostics(wd, profile, tool_name="python_mypy")
        before_ok = bool(getattr(before, "available", False))
        after_ok = bool(getattr(after, "available", False))
        if not before_ok or not after_ok:
            return {"status": "unavailable", "new_error_count": None,
                    "tool": getattr(after, "tool", "") or "mypy"}
        count = new_error_count(before, after)
        return {"status": "available", "new_error_count": count,
                "tool": getattr(after, "tool", "") or "mypy"}

    returned, result = _call_with_deadline(_leg, timeout=ANALYZER_LEG_TIMEOUT_SECONDS)
    if not returned or result is None:
        return {"status": "unavailable", "new_error_count": None, "tool": "mypy"}
    return result


def _run_change_analysis(pr: PhaseResult, wd: Path, analyzer: ChangeAnalyzer) -> None:
    """Best-effort phase-boundary evidence: analyze ``pr.commit_hash`` and record the result.

    The typed before/after CodeSnapshots + CodeDelta are materialized from git (the phase
    commit vs its parent); the analyzer (injected at the composition root — the concrete
    ``control.evidence_analyzer.EvidenceChangeAnalyzer`` or any structural match) returns the
    code-change facts + executor neighborhood, stored on ``pr.change_analysis``. The sonar + lsp
    legs (cap_2a rerun2 p1, design §2/§3/§4) run BEFORE/AFTER — the parent revision is
    materialized once, then both legs run under the same hard deadline as the graph leg. Every
    failure path (no parent commit, unreadable revisions, an analyzer error) degrades to
    ``change_analysis=None`` — the seam can never change the phase's outcome (design §5.7).

    ``ChangeInput.revision`` and both snapshot revisions are FULL commit SHAs (provenance);
    ``pr.commit_hash`` remains the short display hash.
    """
    try:
        profile = detect_language(wd)
        full = _git_full_sha(wd, pr.commit_hash) or pr.commit_hash
        parent = _git_full_sha(wd, f"{full}^")
        before_rev = parent or f"{full}^"
        before_files = _read_commit_files(wd, before_rev, profile)
        after_files = _read_commit_files(wd, full, profile)
        before = build_code_snapshot(before_files, revision=before_rev, profile=profile)
        after = build_code_snapshot(after_files, revision=full, profile=profile)

        # Materialize the parent once; both analyzer legs share it. A failure (root commit,
        # missing revision) degrades each leg to its measured unavailable status — never a gate.
        parent_checkout = _materialize_revision(wd, before_rev)
        try:
            sonar = _sonar_evidence(wd, parent_checkout, before_rev, full)
            lsp = _lsp_evidence(wd, parent_checkout, before_rev, full, profile)
        finally:
            _remove_materialized_revision(wd, parent_checkout)

        change = ChangeInput(
            before=before,
            after=after,
            delta=compute_code_delta(before, after),
            revision=full,
            repository_id=cell_scope(wd),
            acl_scope=cell_scope(wd),
            sonar=sonar,
            lsp=lsp,
            phase_id=pr.phase,
            observed_at=_now(),
        )
        analysis = run_change_analysis(change, analyzer)
        pr.change_analysis = analysis.to_dict()
    except Exception:  # noqa: BLE001 — best-effort seam, never a gate on the phase
        pr.change_analysis = None


def _evidence_context(pr: PhaseResult, *, max_neighborhood: int = 16, max_facts: int = 10) -> str:
    """The bounded, machine-readable evidence block for the NEXT phase's prompt (design §5.7).

    One JSON line rendered from the phase's recorded ``change_analysis``: graph status, the
    full revision, the bounded ACL-scoped neighborhood, and the delta-derived facts. Appended
    to ``prior`` ONLY when an analyzer was injected AND the phase produced an analysis —
    without injection (or after a failed/root-commit analysis) the prompt is byte-identical.
    """
    ca = pr.change_analysis or {}
    payload = {
        "phase": pr.phase,
        "revision": ca.get("revision") or pr.commit_hash,
        "repository_id": ca.get("repository_id", ""),
        "phase_id": ca.get("phase_id", pr.phase),
        "observed_at": ca.get("observed_at", ""),
        "graph_status": ca.get("graph_status", "not_requested"),
        "impacted_count": ca.get("impacted_count"),
        "impacted_semantics": ca.get("impacted_semantics", ""),
        "impacted_source": ca.get("impacted_source", ""),
        "neighborhood": list(ca.get("neighborhood") or [])[:max_neighborhood],
        "facts": list(ca.get("facts") or [])[:max_facts],
    }
    return "EVIDENCE " + json.dumps(payload, sort_keys=True)


def _completed_phases(workdir: Path, phase_names: list[str], goal: str) -> set[str]:
    """Return phase names that already have a ``[workflow] <phase>`` commit *for this goal*.

    The worktree inherits ``[workflow] <phase>`` commits from every workflow merged into
    main, and phase names collide across workflows (scope/rewrite/verify). Match the goal
    prefix in the commit subject so resume only skips this run's own phases.
    """
    try:
        log = subprocess.run(
            ["git", "log", "--format=%s"], cwd=workdir, capture_output=True, text=True
        )
    except Exception:
        return set()
    goal_prefix = _goal_prefix(goal)
    completed: set[str] = set()
    for line in log.stdout.splitlines():
        m = re.search(r"\[workflow\]\s+(\S+)\s+—\s+(.+)", line)
        if m and m.group(1) in phase_names and m.group(2).startswith(goal_prefix):
            completed.add(m.group(1))
    return completed


def _cell_id(spec_name: str, model: str) -> str:
    slug = "".join(ch if ch.isalnum() else "_" for ch in f"{spec_name}_{model}")
    return f"wf_{slug.lower().strip('_')}"


def cell_scope(workdir: str | Path) -> str:
    """Return the per-cell retrieval scope for a worktree.

    The cell identity is the worktree basename (``f"self-{workdir.name}"``) — each
    augmented cell reads only its own worktree's knowledge, never the global store.
    ``FINOPS_CELL_ID`` overrides the basename when set (a worker that already pinned a
    cell id keeps that identity), so the scope stays ``self-<identity>`` either way.
    """
    identity = os.environ.get("FINOPS_CELL_ID") or Path(workdir).name
    return f"self-{identity}"


def _run_test_gate(pr: PhaseResult, wd: Path, language: str, timeout: int) -> None:
    """Run the independent suite for an agent phase that declared ``test_gate: true``.

    The test_runner (``run_suite``) is the sole source of truth for the outcome — never the
    model's self-report (the workflow's ``no_self_reported_tests`` policy). Mirrors the
    ``kind == "test"`` branch: a failed suite fails the phase, so the commit gate skips it and
    ``stop_on_error`` honours the failure. When the runner did not execute (no gate, or the
    agent phase already failed) the caller leaves ``test_executed_success`` at its ``None``
    default — null-not-zero, never a fabricated value.
    """
    suite = run_suite(wd, language, timeout=timeout)
    pr.tests_passed = suite["passed"]
    pr.tests_total = suite["total"]
    pr.test_executed_success = suite_succeeded(suite)
    if suite.get("failed", 0) > 0 or suite.get("errors", 0) > 0:
        pr.status = "failed"
        pr.error = suite.get("tail", "")[-400:]


def _emit_self_finding(pr: PhaseResult, *, goal: str, scope: str) -> None:
    """Emit a completed phase's finding into the cell's own scope (self-build producer).

    Best-effort: emission failure (Redis down, write guard off, artifact path issue) is
    swallowed — a self-build finding is a progressive enhancement, never a gate on the phase.
    ``scope`` is ``cell_scope(wd)`` (``self-<worktree>``), so the record lands in the cell's own
    retrieval scope, never the global store.
    """
    try:
        from agentic_dynamics.knowledge.knowledge_ingestion import emit_phase_finding

        emit_phase_finding(pr, goal=goal, repository_id=scope, revision=pr.commit_hash)
    except Exception:
        pass  # progressive path — never block or fail the phase on emission


def _completed_phases_from_index(
    spec: ExperimentSpec, phase_names: list[str], goal: str
) -> set[str]:
    """Resume fallback: read completed phases out of the spec's latest run ledger.

    Consulted **only** when :func:`_completed_phases` found no ``[workflow]`` commit, so
    the existing git-log path can never be regressed by this. The derived index
    (``experiments/specs/index.json``) points at the latest run ledger via
    ``results_pointer``; that ledger lists each phase and its status.

    Two guards keep this honest:

    * only phases whose recorded ``status`` is ``"ok"`` count as completed — a failed phase
      must be re-entered;
    * the ledger's ``goal`` must share this run's 40-char prefix, mirroring the same
      discipline :func:`_completed_phases` applies to commit subjects. Phase names collide
      across workflows (scope/verify), so without the goal check a resume could skip work
      that belongs to a different run of the same spec.

    Best-effort throughout: any failure returns an empty set, which simply means "resume
    from the top" — the pre-existing behaviour when no commits exist.
    """
    try:
        from agentic_dynamics.experiment.spec_status import index_entry

        entry = index_entry(spec.name)
        if entry is None or not entry.results_pointer:
            return set()
        ledger_path = PROJECT_ROOT / entry.results_pointer
        payload = json.loads(ledger_path.read_text())
        if str(payload.get("goal", ""))[:40].rstrip() != _goal_prefix(goal):
            return set()
        return {
            str(ph.get("phase"))
            for ph in payload.get("phases", []) or []
            if str(ph.get("phase")) in phase_names and ph.get("status") == "ok"
        }
    except Exception:
        return set()  # never block a resume on an index/ledger problem


class PhaseWatchdog:
    """Stall monitor for one agent phase (cap_runner_hardening p1).

    The agent's steps land in ``<workdir>/.instrument/session.jsonl`` — the adapters append
    each event line to that file LIVE while the seam is present, so the file's mtime IS the
    last-step time. The monitor polls that age — NOT wall time — so a phase that keeps
    producing steps never fires no matter how long it runs, while an agent whose last step
    is stale past the threshold is SIGTERM'd (via the ``kill`` handle the adapter registered
    in the seam) and the phase fails with reason ``STALLED`` plus the evidence (last-step
    timestamp, stale age, transcript tail).

    Threshold: ``FINOPS_PHASE_WATCHDOG_MIN`` env / CLI ``--phase-watchdog-min``, default 20
    minutes (the measured stalls were 45-65 min; no legit step gap observed beyond ~10 min).
    A threshold <= 0 disables the watchdog — agent phases then run unwrapped, byte-identical
    to the pre-hardening runner. Non-agent phases never construct one (test phases run
    in-process via ``test_runner``).

    The monitor is cheap: each poll reads only the bytes appended to the transcript since the
    previous poll (a few lines), so it adds no meaningful overhead to a compliant phase.

    Adversarial note (cap_runner_hardening p5): the stall clock advances ONLY on MEANINGFUL
    step events — a valid session event line whose ``type`` is in :data:`_MEANINGFUL_EVENT_TYPES`
    (the vocabulary the adapters emit: step_start/step_finish/text/reasoning/tool_use/…). A
    junk heartbeat — a non-JSON line or a dict without a recognized event type — touches the
    file but does NOT reset the clock, so an agent that writes keep-alive garbage without real
    progress is still SIGTERM'd. Accepted limitation: a heartbeat forged to LOOK like a real
    event (``{"type":"step_start"}``) cannot be distinguished from a genuine one — the
    transcript is the model's own output channel, and the measured disease was total silence.
    """

    def __init__(
        self, workdir: str | Path, threshold_min: float, *, poll_interval_s: float | None = None
    ) -> None:
        self.workdir = Path(workdir)
        self.threshold_min = float(threshold_min)
        self.threshold_s = self.threshold_min * 60.0
        if self.threshold_s <= 0:
            raise ValueError("phase watchdog threshold must be > 0")
        #: the transcript the phase's agent writes its steps to (run_workflow passes the same
        #: path as ``transcript_path`` so the adapter writes exactly the file being watched)
        self.transcript = self.workdir / ".instrument" / "session.jsonl"
        #: adaptive poll interval: short enough to catch small test thresholds promptly, long
        #: enough to be negligible in production (<= 10s for the default 20-min threshold)
        self.poll_interval_s = poll_interval_s or max(0.25, min(self.threshold_s / 8.0, 10.0))
        #: the shared kill seam — ``stream_subprocess`` populates ``["kill"]`` the moment the
        #: agent process spawns, so this monitor can SIGTERM a process it never spawned
        self.seam: dict[str, Any] = {"kill": None, "killed": False}
        self._start = time.time()
        #: the stall clock — the last time a MEANINGFUL step event landed (not the file mtime):
        #: a junk heartbeat must not reset it (adversarial p5). The transcript is re-read only
        #: from the last offset, so the poll stays cheap as the file grows.
        self._last_activity = self._start
        self._last_offset = 0
        self._last_size = 0

    def _poll_transcript(self) -> None:
        """Read newly-appended transcript lines and advance the stall clock for meaningful steps.

        Only bytes added since the last poll are read (a cheap incremental tail); a truncated
        file (the adapter's end-of-phase rewrite) resets the offset so the rescan starts clean.
        """
        try:
            size = self.transcript.stat().st_size
        except OSError:
            return
        if size < self._last_size:  # truncated — the adapter's final write_text; rescan from top
            self._last_offset = 0
        self._last_size = size
        if size <= self._last_offset:
            return
        with open(self.transcript, "rb") as fh:
            fh.seek(self._last_offset)
            new = fh.read()
        if new.endswith(b"\n"):
            complete = new[:-1].split(b"\n") if len(new) > 1 else []
            self._last_offset = size
        else:
            # keep a possibly-partial trailing line for the next poll
            pieces = new.split(b"\n")
            complete = pieces[:-1] if len(pieces) > 1 else []
            self._last_offset = size - len(pieces[-1])
        for line in complete:
            if _is_meaningful_step_event(line):
                self._last_activity = time.time()

    def _last_step_age(self) -> float:
        """Seconds since the transcript's last MEANINGFUL step event (phase start if none yet)."""
        return time.time() - self._last_activity

    def _last_step_at_iso(self) -> str:
        return datetime.fromtimestamp(self._last_activity, timezone.utc).isoformat()

    def _transcript_tail(self, max_lines: int = 5, max_chars: int = 400) -> str:
        try:
            lines = self.transcript.read_text().splitlines()
        except OSError:
            return ""
        tail = "\n".join(lines[-max_lines:])
        if len(tail) > max_chars:
            tail = tail[-max_chars:]
        return tail or "(no transcript yet)"

    def check_stall(self) -> dict[str, Any] | None:
        """Return the STALLED evidence when no MEANINGFUL step has landed past the threshold."""
        self._poll_transcript()
        age = self._last_step_age()
        if age < self.threshold_s:
            return None
        return {
            "reason": "STALLED",
            "last_step_at": self._last_step_at_iso(),
            "stale_age_s": round(age, 1),
            "stale_min": round(age / 60.0, 1),
            "threshold_min": self.threshold_min,
            "transcript_tail": self._transcript_tail(),
        }

    def kill_agent(self) -> None:
        """SIGTERM the stalled agent via the seam the adapter registered (best-effort)."""
        self.seam["killed"] = True
        kill = self.seam.get("kill")
        if kill is not None:
            with contextlib.suppress(Exception):  # the agent may have already exited
                kill()


#: The session-event vocabulary the adapters write to the transcript. ONLY a line whose
#: ``type`` is in this set counts as a meaningful step for the stall clock (adversarial p5):
#: a real session emits step boundaries + the events of each step, so continuous work keeps
#: the watchdog alive; a junk heartbeat line does not. Kept generous so a legitimate long tool
#: call (whose ``tool_use``/``text``/``reasoning`` events keep landing) never looks stalled.
_MEANINGFUL_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "step_start",
        "step_finish",
        "message",
        "text",
        "reasoning",
        "tool_use",
        "tool",
        "file",
        "add",
        "snapshot",
    }
)


def _is_meaningful_step_event(line: bytes) -> bool:
    """True when ``line`` parses as a session event with a recognized ``type``."""
    try:
        event = json.loads(line)
    except (ValueError, TypeError):
        return False
    if not isinstance(event, dict):
        return False
    kind = event.get("type")
    return isinstance(kind, str) and kind in _MEANINGFUL_EVENT_TYPES


def _resolve_watchdog_min(cli_value: float | None) -> float:
    """Resolve the phase-watchdog threshold: explicit arg > env > default (cap p1 hard rule 5)."""
    if cli_value is not None:
        return float(cli_value)
    raw = os.environ.get(PHASE_WATCHDOG_ENV, "").strip()
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return PHASE_WATCHDOG_DEFAULT_MIN


def _run_agent_phase(
    run_agent: Callable[..., Any],
    prompt: str,
    agent_kwargs: dict[str, Any],
    watchdog: PhaseWatchdog | None,
) -> tuple[Any | None, dict[str, Any] | None]:
    """Run one agent invocation, optionally under the stall watchdog.

    Without a watchdog this is exactly the pre-hardening blocking call. With one, the agent
    runs in a worker thread while this monitor polls the session transcript's last-step age;
    a stall past the threshold SIGTERMs the agent and returns ``(None, evidence)`` so the
    caller fails the phase with ``STALLED`` + the evidence. ``(result, None)`` on a normal
    completion. The worker is abandoned (not joined) on a stall — the kill is what brings the
    process down, and the phase must fail deterministically, not wait for the agent's own exit.
    """
    if watchdog is None:
        return run_agent(prompt, **agent_kwargs), None
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(run_agent, prompt, **agent_kwargs)
    try:
        while True:
            try:
                return future.result(timeout=watchdog.poll_interval_s), None
            except FuturesTimeout:
                evidence = watchdog.check_stall()
                if evidence is not None:
                    watchdog.kill_agent()
                    return None, evidence
    finally:
        pool.shutdown(wait=False)


def _format_stall_evidence(ev: dict[str, Any]) -> str:
    """Render the structured stall evidence into the phase's error (the ledger carries both)."""
    return (
        f"STALLED — no session step for {ev['stale_min']} min "
        f"(threshold {ev['threshold_min']} min); last step at {ev['last_step_at']}; "
        f"transcript tail:\n{ev['transcript_tail']}"
    )


# ── Deploy gate (cap_runner_hardening p2) ──────────────────────────────────────────────────
#
# The measured disease: terra ran ``firebase deploy`` from a non-deploy phase and silently
# overwrote the production site (the revamp2 p3 session — the replay evidence is the transcript
# line whose bash input was ``firebase deploy --only hosting && firebase deploy --only hosting
# --project agentic-dynamics``). The gate is the technical, deterministic fix: after an agent
# phase, the runner scans the phase's session transcript for production-deploy commands; a hit
# in a phase NOT marked ``deploy_allowed: true`` fails the phase with reason ``DEPLOY_GATE`` +
# the offending command + its transcript line as evidence.
#
# Honest detection scope (p5 adversary — what it can and cannot catch):
#   CAN catch (TWO tiers, both on the bash tool_use event the agent actually ran):
#     - the COMMAND tier: the tool input contains a firebase production-deploy invocation —
#       ``firebase deploy`` (any flags), ``firebase --project <production-host>``, ``firebase
#       hosting deploy``, including chained (``&&``/``;``), with any working directory, and the
#       ``npx firebase-tools deploy`` form (the ``firebase``-token boundary still matches before
#       the ``-tools`` suffix). The spec's pattern list verbatim, kept in this tuple.
#     - the OUTPUT tier: the tool's captured output carries firebase's production-deploy banner
#       (``Deploy complete!``, ``hosting[ai-finops-rulebook|agentic-dynamics]``, ``Hosting URL:
#       https://…web.app``). This catches INDIRECTION — a script file (``./deploy.sh``), an
#       alias, or a variable that reaches ``firebase deploy`` without the literal command in the
#       tool input: a real firebase deploy prints this banner regardless of how it was invoked.
#   CANNOT catch (documented limitation): indirection that never surfaces the literal command
#   NOR the deploy banner in THIS phase's transcript — e.g. an alias/variable defined in an
#   EARLIER phase or a wrapper that suppresses firebase's output. The gate reads the transcript
#   deterministically and cannot resolve shell state across phases. Residual risk is bounded:
#   the measured disease was an agent plainly running ``firebase deploy``, and the deploy_allowed
#   marker + the failed phase + operator stop give the blast radius the operator gets to see.
#   The output tier deliberately does NOT scan file contents or non-bash tool events (a skill
#   document quoting the deploy command is not a deploy).
#
# Simpler honest schema rule (spec (d)): ANY phase may declare ``deploy_allowed: true`` — the
# validator only type-checks it (must be a real boolean) and the post-scan enforces the intent.
# A phase that carries the marker but never deploys is fine; a phase that deploys without it
# fails. No naming rule, no "only the deploy phase" special case.
DEPLOY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bfirebase\b[^\n]*\bdeploy\b"), "firebase deploy"),
    (
        re.compile(r"\bfirebase\b[^\n]*\b--project\s+(?:agentic-dynamics|ai-finops-rulebook)\b"),
        "firebase --project <production-host>",
    ),
    (re.compile(r"\bfirebase\b[^\n]*\bhosting\s+deploy\b"), "firebase hosting deploy"),
]

#: The OUTPUT tier's signatures — firebase's production-deploy banner, printed regardless of how
#: the deploy was invoked (direct, script file, alias, variable). Catches command indirection.
DEPLOY_OUTPUT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Deploy\s+complete!"), "firebase deploy output (Deploy complete!)"),
    (
        re.compile(r"hosting\[(?:ai-finops-rulebook|agentic-dynamics)\]"),
        "firebase hosting[<production-host>] output",
    ),
    (
        re.compile(r"Hosting URL: https://(?:ai-finops-rulebook|agentic-dynamics)\.web\.app"),
        "firebase Hosting URL output",
    ),
]


def _commands_from_event(event: dict[str, Any]) -> list[str]:
    """Extract the shell commands a tool event actually ran (bash tool_use inputs)."""
    if event.get("type") != "tool_use":
        return []
    part = event.get("part", {})
    if not isinstance(part, dict) or part.get("tool") != "bash":
        return []
    state = part.get("state", {})
    if not isinstance(state, dict):
        return []
    inp = state.get("input", "")
    command = inp.get("command", "") if isinstance(inp, dict) else str(inp)
    if not command:
        return []
    return [command]


def _output_from_event(event: dict[str, Any]) -> str:
    """Extract the captured stdout of a bash tool_use event ('' when absent)."""
    if event.get("type") != "tool_use":
        return ""
    part = event.get("part", {})
    if not isinstance(part, dict) or part.get("tool") != "bash":
        return ""
    state = part.get("state", {})
    if not isinstance(state, dict):
        return ""
    out = state.get("output", "")
    if isinstance(out, dict):
        return str(out.get("output", "") or "")
    return str(out or "")


def _deploy_pattern_match(command: str) -> str | None:
    """Return the label of the first deploy pattern ``command`` matches, or ``None``."""
    for pattern, label in DEPLOY_PATTERNS:
        if pattern.search(command):
            return label
    return None


def _deploy_output_pattern_match(output: str) -> str | None:
    """Return the label of the first deploy-OUTPUT signature ``output`` matches, or ``None``."""
    for pattern, label in DEPLOY_OUTPUT_PATTERNS:
        if pattern.search(output):
            return label
    return None


def _scan_transcript_for_deploys(transcript: Path) -> list[dict[str, Any]]:
    """Scan a session transcript for firebase production-deploy commands (or their output).

    Two detection tiers (see the module block above): the COMMAND tier matches the bash tool
    input; the OUTPUT tier matches the tool's captured output for a bash event whose command did
    not itself match (indirection). Returns one entry per offending event:
    ``{"command": <the bash input>, "pattern": <which pattern matched>, "line": <the raw
    transcript line>}.`` Empty when the transcript is missing, unreadable, or clean.
    """
    try:
        lines = transcript.read_text().splitlines()
    except OSError:
        return []
    violations: list[dict[str, Any]] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        for command in _commands_from_event(event):
            matched = _deploy_pattern_match(command)
            if matched is not None:
                violations.append(
                    {"command": command, "pattern": matched, "line": line[:2000]}
                )
                continue
            # OUTPUT tier (indirection — a script/alias/variable that reached firebase deploy):
            # a real production deploy prints its banner in the tool output no matter how it
            # was invoked, so catch it there when the literal command did not match. The tier
            # applies ONLY to deploy-INDICATING commands (the indirection case still carries
            # firebase/deploy/hosting vocabulary in the command) — scanning every command's
            # output produced a false positive on `git log` whose output echoed old commit
            # messages about deploys (the revamp3 p1 misfire, fixed here; pure-variable
            # indirection with no vocabulary and no banner stays the documented residual).
            if not re.search(r"\b(firebase|deploy|hosting)\b", command):
                continue
            output = _output_from_event(event)
            matched_out = _deploy_output_pattern_match(output)
            if matched_out is not None:
                violations.append(
                    {
                        "command": command or "(no command — output-only)",
                        "pattern": matched_out,
                        "line": line[:2000],
                    }
                )
    return violations


def _enforce_deploy_gate(
    pr: PhaseResult, wd: Path, phase_def: dict[str, Any], *, transcript: Path | None = None
) -> None:
    """Post-phase deploy gate (cap_runner_hardening p2).

    A phase NOT marked ``deploy_allowed: true`` that ran a firebase production-deploy command
    fails with reason ``DEPLOY_GATE`` + the offending command(s) + the transcript line(s). The
    evidence lands on ``PhaseResult.deploy_gate`` and the phase error, so the operator sees
    exactly what fired. Two detection tiers (p5): the COMMAND tier matches the bash tool input
    against :data:`DEPLOY_PATTERNS`; the OUTPUT tier matches the tool's captured output against
    :data:`DEPLOY_OUTPUT_PATTERNS` when the command did not match — catching indirection (a
    script/alias/variable that reached ``firebase deploy`` without the literal command). The
    marker is the phase's own opt-in (default false) — the gate is about the command the agent
    issued, never a naming rule. Best-effort: a missing/unreadable transcript is not a violation;
    a phase already failed for another reason keeps its error and gains the DEPLOY_GATE note
    appended (both reasons stay visible).
    """
    if bool(phase_def.get("deploy_allowed", False)):
        return
    violations = _scan_transcript_for_deploys(transcript or (wd / ".instrument" / "session.jsonl"))
    if not violations:
        return
    pr.deploy_gate = {"reason": "DEPLOY_GATE", "violations": violations}
    offending = "; ".join(f"'{v['command']}'" for v in violations)
    msg = (
        f"DEPLOY_GATE — firebase production deploy in phase not marked deploy_allowed: "
        f"{offending}"
    )
    if pr.status == "ok":
        pr.status = "failed"
        pr.error = msg
    else:
        pr.error = f"{pr.error}\n{msg}"


# ── Commit-prefix enforcement (cap_runner_hardening p3) ────────────────────────────────────
#
# The measured disease: terra committed 7 plain-message commits during revamp2 (no
# '[workflow] <phase>' prefix, no goal prefix), silently breaking the resume machinery
# (_completed_phases matches '[workflow] <phase> — <goal prefix>') and forcing a re-tagging
# surgery. The enforcement is the technical, deterministic fix: after an agent phase, the
# runner lists the commits made during the phase (git log pre-phase-head..HEAD) and every one
# must match the pattern — a plain commit fails the phase with reason COMMIT_PREFIX + the
# offending subjects as evidence, even if the phase otherwise succeeded.
#
# The definition of a valid commit IS the resume machinery's definition of a resumable commit:
# this regex is kept in lockstep with _completed_phases, and the per-phase checks add the
# phase's OWN name (a different phase's name must not count) and the run's 40-char goal prefix.
COMMIT_SUBJECT_RE = re.compile(r"\[workflow\]\s+(\S+)\s+—\s+(.+)")
COMMIT_SUBJECT_PATTERN = "[workflow] <phase> — <goal prefix>"


def _commit_subject_matches(subject: str, phase_name: str, goal_prefix: str) -> bool:
    """True when ``subject`` is a commit the resume machinery would match for THIS phase.

    Mirrors ``_completed_phases`` exactly — the same regex, plus the phase's own name and the
    run's 40-char goal prefix. Enforcement ⇔ resumability: a commit that passes here is exactly
    one ``_completed_phases`` would treat as this phase's completed commit.
    """
    m = COMMIT_SUBJECT_RE.search(subject)
    return bool(m and m.group(1) == phase_name and m.group(2).startswith(goal_prefix))


def _git_log_commits(workdir: Path, rev_range: str) -> list[tuple[str, str, str]]:
    """``(sha, subject, author_email)`` triples for commits in ``rev_range``, or [] on any git problem.

    The full 40-char sha rides along so the enforcement can (a) exempt the runner's OWN
    execution-layer commits (the adapter's fresh-worktree ``Initial`` commit) by author, and
    (b) prove *which* commit is HEAD before deciding whether a message-only rewrite is safe
    (the P0 multi-commit canonicalization fix — ``git commit --amend`` rewrites HEAD only,
    so the canonicalize path must know the offender is HEAD).
    """
    try:
        log = subprocess.run(
            ["git", "log", "--format=%H|%s|%ae", rev_range],
            cwd=workdir, capture_output=True, text=True, timeout=30,
        )
    except Exception:  # noqa: BLE001 — a git problem degrades to "no commits to check"
        return []
    if log.returncode != 0:
        return []
    out: list[tuple[str, str, str]] = []
    for line in log.stdout.splitlines():
        if not line.strip():
            continue
        sha, _, rest = line.partition("|")
        subject, _, email = rest.partition("|")
        out.append((sha.strip(), subject.strip(), email.strip()))
    return out


def _git_log_subjects(workdir: Path, rev_range: str) -> list[tuple[str, str]]:
    """``(subject, author_email)`` pairs for commits in ``rev_range``, or [] on any git problem.

    Author email rides along so the enforcement can exempt the runner's OWN execution-layer
    commits (the adapter's fresh-worktree ``Initial`` commit) from the pattern check — it is
    not a manual agent commit, exactly like ``_git_commit``'s message (exempt by matching).
    Delegates to :func:`_git_log_commits` (the sha-carrying source of truth).
    """
    return [(subject, email) for _, subject, email in _git_log_commits(workdir, rev_range)]


#: The adapter's worktree-initialization identity (``opencode._init_git_workdir``): the
#: ``Initial`` commit it creates in a genuinely-new worktree is the runner's own execution-layer
#: artifact, not a manual agent commit — the commit-prefix enforcement exempts it by author.
RUNNER_INIT_AUTHOR_EMAIL = "experiment@instrument.local"


def _install_commit_msg_hook(wd: Path, phase_name: str, goal: str) -> None:
    """Commit-time prefix enforcement (the drawing-board fix, 2026-08-28).

    A ``.git/hooks/commit-msg`` hook in the worktree rewrites any non-conforming subject to
    ``[workflow] <phase> — <goal-prefix>`` AT COMMIT TIME — deterministic, no model involved,
    the agent CANNOT produce a violating commit. The post-phase gate (``_enforce_commit_prefix``)
    then becomes a backstop for pre-hook commits instead of a failure point. Installed per
    phase in canonicalize mode only (``FINOPS_COMMIT_GATE`` unset or ``canonicalize``);
    strict mode installs no hook — violations stay visible so the gate can fail with evidence.
    ``FINOPS_COMMIT_HOOK=0`` disables the hook for a run (tests of the gate's own rewrite path,
    or a caller that wants raw commits). The adapter's ``Initial`` commit is preserved by
    explicit passthrough (its subject is exempt by author identity at the gate).
    Best-effort: an unwritable .git degrades to "no hook" (the gate still catches violations).
    """
    if os.environ.get("FINOPS_COMMIT_GATE", "canonicalize") == "strict":
        return
    if os.environ.get("FINOPS_COMMIT_HOOK", "1") == "0":
        return
    expected = f"[workflow] {phase_name} — {_goal_prefix(goal)}"
    # A campaign worktree's ``.git`` is a FILE (pointing at the shared git dir), not a
    # directory — writing to ``wd/.git/hooks/`` fails silently (the 2d run's p5 lesson:
    # the hook never installed, the wrapper's commit landed unprefixed, the gate failed
    # the run at the finish line). Resolve the real paths via git: the hook lives in the
    # COMMON hooks dir (shared), the expected prefix lives in a PER-WORKTREE file
    # (``git rev-parse --git-path`` returns the worktree's own git dir), so concurrent
    # worktrees can never clobber each other's prefix.
    def _git_path(kind: str) -> Path | None:
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--git-path", kind], cwd=wd,
                capture_output=True, text=True, timeout=15,
            )
            raw = r.stdout.strip()
            if r.returncode != 0 or not raw:
                return None
            p = Path(raw)
            return p if p.is_absolute() else (wd / p).resolve()
        except Exception:  # noqa: BLE001
            return None

    hooks_dir = _git_path("hooks")
    prefix_file = _git_path("commit_msg_prefix")
    if hooks_dir is None or prefix_file is None:
        return
    hook = hooks_dir / "commit-msg"
    script = (
        "#!/usr/bin/env python3\n"
        "import os, subprocess, sys\n"
        "path = sys.argv[1]\n"
        "# The expected prefix lives in the PER-WORKTREE git dir (never shared):\n"
        "p = subprocess.run(['git', 'rev-parse', '--git-path', 'commit_msg_prefix'],\n"
        "                   capture_output=True, text=True)\n"
        "pf = p.stdout.strip() if p.returncode == 0 else ''\n"
        "try:\n"
        "    with open(pf, encoding='utf-8') as f:\n"
        "        expected = f.read().strip()\n"
        "except Exception:\n"
        "    sys.exit(0)\n"
        "with open(path, encoding='utf-8') as f:\n"
        "    msg = f.read()\n"
        "first, sep, rest = msg.partition('\\n')\n"
        "if first == 'Initial' or first.startswith(expected):\n"
        "    sys.exit(0)\n"
        "with open(path, 'w', encoding='utf-8') as f:\n"
        "    f.write(expected + (sep + rest if sep else ''))\n"
    )
    try:
        hook.write_text(script, encoding="utf-8")
        hook.chmod(0o755)
        prefix_file.write_text(expected, encoding="utf-8")
    except Exception:  # noqa: BLE001 — an unwritable hook degrades to the post-phase gate
        pass


def _canonicalize_commit_range(
    wd: Path, pre_head: str | None, expected: str, offenders: list[tuple[str, str]]
) -> str | None:
    """Proper noninteractive history rewrite (the drawing-board fix, 2026-08-28).

    Rewrites EVERY offending commit's subject in the phase range to the canonical pattern via
    ``git filter-branch`` with a deterministic msg-filter — exact-SHA scoped (the range is
    ``pre_head..HEAD`` — the phase's own commits and nothing else), checked return code,
    tree-preserving (only messages change; the final tree hash is untouched, so the relabel
    gate and the phase's deliverable tree are unaffected). ``Initial`` subjects pass through
    unchanged (the adapter's exemption, same as the gate). This replaces the P0 single-amend
    rule: ``git commit --amend`` rewrites HEAD alone, so multi-commit ranges (and a single
    offender buried under good commits) were previously refused; the filter-branch rewrite
    handles every shape. Returns the rewritten HEAD sha, or None on any failure — the caller
    then falls through to the strict COMMIT_PREFIX record with the fresh evidence. The
    deterministic rewrite is deliberately NOT an agent session: the expected prefix is known
    to the runner (no judgment needed), so an LLM doing git surgery would add failure modes
    to a mechanical fix.
    """
    # A campaign worktree's ``.git`` is a FILE — the filter script must live in the
    # PER-WORKTREE git dir (``git rev-parse --git-path``), like the commit-msg prefix
    # file, so concurrent worktrees never clobber each other and the path survives
    # filter-branch's temp-checkout cwd.
    try:
        gp = subprocess.run(
            ["git", "rev-parse", "--git-path", "commit_prefix_filter.py"], cwd=wd,
            capture_output=True, text=True, timeout=15,
        )
        raw = gp.stdout.strip()
        if gp.returncode == 0 and raw:
            p = Path(raw)
            script = p if p.is_absolute() else (wd / p).resolve()
        else:
            script = None
    except Exception:  # noqa: BLE001
        script = None
    if script is None:
        return None
    body = (
        "import sys\n"
        "expected = " + repr(expected) + "\n"
        "msg = sys.stdin.read()\n"
        "first, sep, rest = msg.partition('\\n')\n"
        "if first == 'Initial' or first.startswith(expected):\n"
        "    sys.stdout.write(msg)\n"
        "else:\n"
        "    sys.stdout.write(expected + (sep + rest if sep else ''))\n"
    )
    try:
        script.write_text(body, encoding="utf-8")
        env = {**os.environ, "FILTER_BRANCH_SQUELCH_WARNING": "1"}
        rng = f"{pre_head}..HEAD" if pre_head else "HEAD"
        run = subprocess.run(
            ["git", "filter-branch", "--msg-filter", f"{sys.executable} {script}", "--", rng],
            cwd=wd, capture_output=True, text=True, timeout=300, env=env,
        )
        if run.returncode != 0:
            return None
        # Best-effort: drop filter-branch's refs/original backup ref (a stale one would
        # confuse a later relabel-tree comparison).
        try:
            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=wd,
                capture_output=True, text=True, timeout=15,
            ).stdout.strip()
            if branch and branch != "HEAD":
                subprocess.run(
                    ["git", "update-ref", "-d", f"refs/original/refs/heads/{branch}"],
                    cwd=wd, capture_output=True, text=True, timeout=15,
                )
        except Exception:  # noqa: BLE001 — the backup-ref cleanup is best-effort
            pass
        return _git_full_sha(wd, "HEAD")
    except Exception:  # noqa: BLE001 — any rewrite failure degrades to the strict path
        return None


#: The doc-lifecycle status vocabulary (the contract — must stay in lockstep with
#: tests/test_doc_lifecycle.py's STATUS_VOCABULARY).
DOC_STATUS_VOCABULARY = {
    "proposed", "accepted", "implementing", "implemented", "superseded", "abandoned",
}


def _enforce_doc_contract(pr: PhaseResult, wd: Path, pre_head: str | None) -> None:
    """Post-phase doc-contract enforcement (the 2e merge lesson, 2026-08-28).

    Every ``docs/**/*.md`` file the phase committed or modified must carry a valid
    ``status:`` frontmatter field (the doc-lifecycle vocabulary). A doc without one — or with
    an unknown status — fails the phase with ``DOC_CONTRACT`` + the offending paths, even if
    the phase otherwise succeeded. Agent phases only; strict, never canonicalized (the
    contract layer is state, not render — the wrapper must fix the doc). Mirrors
    ``tests/test_doc_lifecycle.py``'s check (lockstep: the vocabulary above).
    Best-effort: an unreadable git state degrades to "no docs to check".
    """
    if pr.status != "ok":
        return
    try:
        if pre_head:
            r = subprocess.run(
                ["git", "diff", "--name-only", f"{pre_head}..HEAD", "--", "docs/"],
                cwd=wd, capture_output=True, text=True, timeout=30,
            )
        else:
            r = subprocess.run(
                ["git", "ls-files", "docs/"], cwd=wd, capture_output=True, text=True, timeout=30,
            )
        paths = [ln for ln in r.stdout.splitlines() if ln.strip().endswith(".md")]
    except Exception:  # noqa: BLE001 — an unreadable git state degrades to "no check"
        return
    bad: list[str] = []
    for rel in paths:
        p = wd / rel
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
        status = None
        if m:
            fm = m.group(1)
            sm = re.search(r"^status:\s*(\S+)", fm, re.M)
            if sm:
                status = sm.group(1)
        if status not in DOC_STATUS_VOCABULARY:
            bad.append(rel)
    if not bad:
        return
    pr.commit_gate = {
        "reason": "DOC_CONTRACT",
        "docs": bad,
        "expected": "status frontmatter in " + ", ".join(sorted(DOC_STATUS_VOCABULARY)),
    }
    msg = (
        f"DOC_CONTRACT — {len(bad)} committed doc(s) lack a valid status frontmatter "
        f"(one of {sorted(DOC_STATUS_VOCABULARY)}): {', '.join(bad)} — the doc-lifecycle "
        f"contract (test_doc_lifecycle) would reject them at merge time"
    )
    if pr.status == "ok":
        pr.status = "failed"
        pr.error = msg
    else:
        pr.error = f"{pr.error}\n{msg}"


def _goal_prefix(goal: str) -> str:
    """The goal prefix the commit contract matches — ``goal[:40]`` TRIMMED of trailing
    whitespace. The commit-msg hook writes the prefix into the subject and git strips
    trailing whitespace on commit, so a goal whose 40th character is a space (the i10
    backfill's ``"...capture "`` lesson) would otherwise never match its own prefix.
    Every site that compares or expects the prefix uses this helper."""
    return goal[:40].rstrip()


def _enforce_commit_prefix(
    pr: PhaseResult, wd: Path, phase_name: str, goal: str, pre_head: str
) -> None:
    """Post-phase commit-prefix enforcement (cap_runner_hardening p3).

    Every commit the agent made during the phase (``git log pre_head..HEAD``; when there was
    no pre-phase HEAD — a fresh worktree — all of HEAD's commits) must match
    ``[workflow] <phase-name> — <goal prefix>``. A commit that does not fails the phase with
    reason ``COMMIT_PREFIX`` + full evidence (every offender's sha + original subject), even
    if the phase otherwise succeeded — the phase flips to failed and ``stop_on_error`` stops
    the campaign for the operator. Agent phases only. The runner's OWN commits are exempt by
    construction: the runner's ``_git_commit`` message matches the pattern (and runs AFTER
    this check), and the adapter's fresh-worktree ``Initial`` commit is exempted by its author
    identity (``RUNNER_INIT_AUTHOR_EMAIL``) — the enforcement catches MANUAL agent commits.
    Best-effort: an unreadable git state degrades to "no commits to check".

    **Commit-prefix enforcement (the drawing-board fix, 2026-08-28).** In canonicalize mode
    (``FINOPS_COMMIT_GATE`` unset or ``canonicalize``) the FIRST line of defense is
    ``_install_commit_msg_hook`` — a commit-msg hook installed before the phase rewrites any
    non-conforming subject to ``[workflow] <phase> — <goal-prefix>`` at commit time, so the
    agent cannot produce a violation. The gate itself is the backstop for pre-hook commits:
    it rewrites EVERY offender's subject in the phase range via a proper noninteractive
    history rewrite (``git filter-branch`` + deterministic msg-filter — exact-SHA scoped,
    tree-preserving, checked return code), re-reads the whole range, and fails strict if even
    one violation remains. This supersedes the P0 single-amend rule (``git commit --amend``
    rewrites HEAD only — multi-commit ranges were refused). ``FINOPS_COMMIT_GATE=strict``
    restores the fail-with-evidence mode outright (no hook, no rewrite). TREE violations (the
    relabel — a discarded tree re-presented) are NEVER canonicalized.
    """
    goal_prefix = _goal_prefix(goal)
    commits = (
        _git_log_commits(wd, f"{pre_head}..HEAD")
        if pre_head
        else _git_log_commits(wd, "HEAD")
    )
    # NO_CHANGES gate (the revamp3 vacuous-pass post-mortem): an agent phase whose committed
    # TREE is identical to its pre-phase tree certified itself ok while producing no
    # deliverable — p3 'implemented' zero files, p5 committed no review, p6 committed no
    # verification, and every delta-based gate (census, comparison) passed trivially
    # because a no-op has a perfect delta. The runner's own _git_commit may still make an
    # EMPTY commit for such a phase — the tree identity is what proves the phase produced
    # nothing. A phase whose tree did not change is failed.
    # NO_CHANGES is a PER-PHASE OPT-IN (requires_deliverable: true) — the revamp3
    # vacuous-pass post-mortem: implementation/review/deploy phases MUST deliver files;
    # the general case (analysis-only phases, verification phases that conclude 'nothing
    # to fix') legitimately tolerates no tree change. Only phases that declare the flag
    # are checked — the runner needs the phase definition here.
    if getattr(pr, "requires_deliverable", False):
        if pre_head:
            # The agent's work is UNCOMMITTED at enforcement time (the runner's _git_commit
            # runs after this check) — compare the WORKING TREE against the pre-phase HEAD:
            # tracked changes (`git diff --quiet pre_head` exit 1) or new untracked files
            # both count as a delivered tree change.
            changed = False
            try:
                tracked = subprocess.run(
                    ["git", "diff", "--quiet", pre_head, "--", "."],
                    cwd=wd, capture_output=True, text=True, timeout=30,
                ).returncode
                untracked = subprocess.run(
                    ["git", "ls-files", "--others", "--exclude-standard"],
                    cwd=wd, capture_output=True, text=True, timeout=30,
                ).stdout.strip()
                changed = tracked != 0 or bool(untracked)
            except Exception:  # noqa: BLE001 — a git problem degrades to "no change check"
                changed = True
        else:
            # First phase in a fresh worktree (no pre-phase HEAD): the pre-phase state is
            # the empty tree — any file at all is a change; nothing created is vacuous.
            changed = False
            try:
                untracked = subprocess.run(
                    ["git", "ls-files", "--others", "--exclude-standard"],
                    cwd=wd, capture_output=True, text=True, timeout=30,
                ).stdout.strip()
                changed = bool(untracked)
            except Exception:  # noqa: BLE001 — a git problem degrades to "no change check"
                changed = True
        if not changed:
            pr.commit_gate = {
                "reason": "NO_CHANGES",
                "pre_head": pre_head[:12],
                "expected_prefix": f"[workflow] {phase_name} — {goal_prefix}",
            }
            msg = (
                f"NO_CHANGES — phase '{phase_name}' delivered no tree change since "
                f"{pre_head[:12]}: an agent phase must deliver files (the revamp3 "
                f"p3-p6 vacuous-pass lesson)"
            )
            if pr.status == "ok":
                pr.status = "failed"
                pr.error = msg
            return
    # ``(sha, subject)`` for every non-conforming commit — the sha is part of the evidence
    # (the P0 multi-commit fix: the offender's identity, not just its message).
    bad = [
        (sha, subject)
        for sha, subject, author in commits
        if not (author == RUNNER_INIT_AUTHOR_EMAIL and subject == "Initial")
        and not _commit_subject_matches(subject, phase_name, goal_prefix)
    ]
    if not bad:
        return
    expected = f"[workflow] {phase_name} — {goal_prefix}"
    # CANONICALIZE-WITH-EVIDENCE (cap_runner_hardening2 p1 lesson + the drawing-board fix,
    # 2026-08-28): a MESSAGE-only violation is self-healing by default via the PROPER history
    # rewrite — ``_canonicalize_commit_range`` rewrites EVERY offender's subject in the phase
    # range (``pre_head..HEAD``) with ``git filter-branch`` + a deterministic msg-filter,
    # exact-SHA scoped, tree-preserving, checked return code — then the whole range is
    # re-read and the run fails strict if even one violation remains. This supersedes the P0
    # single-amend rule (``git commit --amend`` rewrites HEAD alone, so multi-commit ranges
    # and a buried single offender were refused): the rewrite handles every shape. Commit-time
    # prevention is the FIRST line of defense (``_install_commit_msg_hook`` — the agent cannot
    # produce a violating commit); this gate path is the backstop for pre-hook commits and
    # for ``FINOPS_COMMIT_HOOK=0`` runs. ``FINOPS_COMMIT_GATE=strict`` restores the
    # fail-with-evidence mode outright. TREE violations (the relabel — a discarded tree
    # re-presented) are NEVER canonicalized: they stay strict failures (cap_runner_hardening2
    # p2).
    if os.environ.get("FINOPS_COMMIT_GATE", "canonicalize") != "strict" and bad:
        rewritten_sha = _canonicalize_commit_range(wd, pre_head, expected, bad)
        if rewritten_sha:
            # Re-read the WHOLE range: a successful rewrite must leave zero violations.
            recheck = (
                _git_log_commits(wd, f"{pre_head}..HEAD")
                if pre_head
                else _git_log_commits(wd, "HEAD")
            )
            remaining = [
                (sha, subject)
                for sha, subject, author in recheck
                if not (author == RUNNER_INIT_AUTHOR_EMAIL and subject == "Initial")
                and not _commit_subject_matches(subject, phase_name, goal_prefix)
            ]
            if not remaining:
                pr.commit_gate = {
                    "reason": "COMMIT_PREFIX_CANONICALIZED",
                    "original_subjects": [subject for _, subject in bad],
                    "expected_prefix": expected,
                    "rewritten_sha": rewritten_sha,
                }
                pr.error = (
                    f"commit messages canonicalized to '{expected}' (originals: "
                    f"{[s for _, s in bad]!r}) — the work was preserved, only the subjects "
                    f"changed; see commit_gate"
                )
                return
            # A re-read that still shows violations is NOT canonicalized — fall through to the
            # strict record with the fresh evidence.
            bad = remaining
    pr.commit_gate = {
        "reason": "COMMIT_PREFIX",
        "subjects": [subject for _, subject in bad],
        "offenders": [{"sha": sha, "subject": subject} for sha, subject in bad],
        "expected_prefix": expected,
    }
    offenders_txt = ", ".join(
        f"{subject!r} ({sha[:12]})" for sha, subject in bad
    )
    msg = (
        f"COMMIT_PREFIX — commits made during phase '{phase_name}' do not match "
        f"'{expected}': {offenders_txt} "
        f"(note: the separator is an EM-DASH U+2014 '—', not a hyphen; the resume "
        f"machinery matches the exact byte pattern)"
    )
    if pr.status == "ok":
        pr.status = "failed"
        pr.error = msg
    else:
        pr.error = f"{pr.error}\n{msg}"


# ── Relabel tree-identity gate (cap_runner_hardening2 §Gap 2) ─────────────────────────────
#
# The revamp2 measured disease: attempt A's tree was reset away (discarded), then attempt B
# (the "resume") committed a byte-IDENTICAL copy under compliant ``[workflow]`` messages —
# ``git diff f6fc35edf 20eeb801b`` is empty (both trees are
# ``f22dbe994439074b47586b0846c033becbf53400``). The merged commit-prefix enforcement checks
# the MESSAGE, and the relabel's messages matched — so the relabel passed. The tree gate closes
# that: it records every discarded tree on a durable ledger and fails any phase whose committed
# tree is EXACTLY a recorded discarded tree (the revamp2 measured case) with the identical-tree
# proof, unless an operator-signed approval artifact (committed before the phase) names the tree
# + phase. The identity check is exact-tree (content-addressed), deliberately not a similarity
# heuristic: a tree with a trivial delta is technically not identical and does not fire — the p5
# adversarial phase documents that boundary honestly (a similarity gate would produce
# false-positive churn on legitimately divergent work, which the campaign rejects).
#
# The ledger: ``experiments/results/workflows/<spec>/discarded_trees.jsonl``, one JSONL entry
# per discard, keyed ``(spec, branch, tree_hash, discarded_at)`` — appended by
# :func:`record_discarded_tree` (the reset/rollback path, reachable via the
# ``workflow discard-tree`` CLI). The gate reads it read-only.

#: Discarded-trees ledger filename, under ``experiments/results/workflows/<spec>/``.
DISCARDED_TREES_FILENAME = "discarded_trees.jsonl"
#: Approval artifacts live in the worktree under ``approvals/<spec>/<phase>_tree_reuse.md``.
APPROVALS_DIRNAME = "approvals"
#: Operator-signature placeholders — an approval carrying one of these (case-insensitive,
#: whitespace-collapsed) is unsigned and refuses to authorize a reuse.
PLACEHOLDER_OPERATORS = frozenset(
    {
        "operator", "your name", "your-name", "your signature", "sign here", "sign-here",
        "todo", "tbd", "n/a", "na", "xxx", "???", "<name>", "placeholder", "name",
    }
)


def discarded_trees_path(spec_name: str) -> Path:
    """The discarded-trees ledger for a spec (append-only JSONL)."""
    return PROJECT_ROOT / "experiments" / "results" / "workflows" / spec_name / DISCARDED_TREES_FILENAME


def _git_tree_hash(workdir: Path, rev: str = "HEAD") -> str:
    """``git rev-parse <rev>^{tree}`` with the ``approvals/`` subtree EXCLUDED, or ``""``.

    The relabel gate compares WORK-product trees, and approval artifacts are scaffolding,
    not work product: an operator committing ``approvals/<spec>/<phase>_tree_reuse.md``
    into the worktree must not change the identity of the work underneath — and a relabel
    must not be able to dodge the gate by burying the discard under an approval-shaped
    commit. The excluded hash is computed by re-reading ``rev`` into a throwaway index,
    dropping every path under ``approvals/``, and ``git write-tree``-ing the rest —
    deterministic, and byte-equal to the plain ``^{tree}`` hash whenever the tree contains
    no ``approvals/`` (the common case). Best-effort by construction: any git problem
    degrades to ``""`` (the gate then cannot fire — never a crash, never a blocker).
    """
    fd, tmp_index = tempfile.mkstemp(prefix="wf_treeidx_", dir="/tmp")
    os.close(fd)
    env = dict(os.environ, GIT_INDEX_FILE=tmp_index)
    try:
        read = subprocess.run(
            ["git", "read-tree", rev], cwd=workdir, env=env, capture_output=True, timeout=30
        )
        if read.returncode != 0:
            return ""
        files = subprocess.run(
            ["git", "ls-files", "-z", "--", "approvals"],
            cwd=workdir, env=env, capture_output=True, timeout=30,
        )
        if files.returncode == 0 and files.stdout:
            subprocess.run(
                ["git", "update-index", "--force-remove", "-z", "--stdin"],
                cwd=workdir, env=env, input=files.stdout, capture_output=True, timeout=30,
            )
        written = subprocess.run(
            ["git", "write-tree"], cwd=workdir, env=env, capture_output=True, text=True, timeout=30
        )
        return written.stdout.strip() if written.returncode == 0 else ""
    except Exception:  # noqa: BLE001 — a git problem degrades to "no tree"
        return ""
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_index)


def _worktree_branch(workdir: Path) -> str:
    """The worktree's current branch (``git rev-parse --abbrev-ref HEAD``); detached = ``HEAD``."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=workdir, capture_output=True, text=True, timeout=30,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:  # noqa: BLE001
        return ""


def load_discarded_trees(spec_name: str, *, ledger_path: Path | None = None) -> list[dict[str, Any]]:
    """Read the discarded-trees ledger for ``spec_name`` (one dict per entry; bad lines skipped)."""
    path = Path(ledger_path) if ledger_path is not None else discarded_trees_path(spec_name)
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return []
    entries: list[dict[str, Any]] = []
    for line in lines:
        try:
            decoded = json.loads(line)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(decoded, dict):
            entries.append(decoded)
    return entries


def record_discarded_tree(
    spec_name: str,
    workdir: str | Path,
    *,
    branch: str | None = None,
    commit: str = "HEAD",
    reason: str = "reset",
    ledger_path: Path | None = None,
) -> str:
    """Record the tree the worktree is about to discard — the runner's reset/rollback path.

    Computes ``git rev-parse <commit>^{tree}`` for the worktree and appends a dated entry to
    the discarded-trees ledger, keyed ``(spec, branch, tree_hash, discarded_at)``. Re-recording
    the same (spec, branch, tree) is a no-op (the ledger keeps the first discard — idempotent).
    Returns the recorded tree hash, or ``""`` when the tree cannot be resolved (a git problem
    degrades to "nothing recorded", never a crash). The operator reaches this through
    ``agentic-dynamics workflow discard-tree`` (``scripts/record_discarded_tree.py``).
    """
    wd = Path(workdir).resolve()
    tree_hash = _git_tree_hash(wd, commit)
    if not tree_hash:
        return ""
    resolved_branch = branch if branch is not None else _worktree_branch(wd)
    path = Path(ledger_path) if ledger_path is not None else discarded_trees_path(spec_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_discarded_trees(spec_name, ledger_path=path)
    if any(
        e.get("tree_hash") == tree_hash and e.get("branch") == resolved_branch for e in existing
    ):
        return tree_hash
    entry = {
        "spec": spec_name,
        "branch": resolved_branch,
        "tree_hash": tree_hash,
        "commit": _git_full_sha(wd, commit) or commit,
        "discarded_at": _now(),
        "reason": reason,
    }
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    return tree_hash


# ── the operator-approval escape (the legit-reuse path) ───────────────────────────────────


def _approval_path(wd: Path, spec_name: str, phase_name: str) -> Path:
    """``approvals/<spec>/<phase>_tree_reuse.md`` inside the worktree."""
    return wd / APPROVALS_DIRNAME / spec_name / f"{phase_name}_tree_reuse.md"


def _parse_approval(text: str) -> dict[str, str]:
    """Extract ``tree`` / ``phase`` / ``operator`` / ``date`` from the approval markdown.

    The artifact is a simple ``- key: value`` list (the operator fills it by hand); the parser
    accepts any ``key: value`` line whose key is one of the four contract fields, so an
    approval written with natural prose around it still parses. Missing/empty fields simply
    fail their check downstream (no defaulting).
    """
    out: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip().lstrip("-* ").strip()
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip().lower()
        if key in ("tree", "phase", "operator", "date"):
            out[key] = value.strip()
    return out


def _date_is_valid(value: str) -> bool:
    """A real date (ISO-8601 or ``YYYY-MM-DD``); empty/unparseable is not a signature date."""
    if not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _operator_is_placeholder(operator: str) -> bool:
    """True when the signature line is empty or a recognizable placeholder.

    An operator signature is the human identity that signed the approval. A single initial or
    a generic word ("operator", "your name", "sign here", "TODO", "???" ...) is not a
    signature — the revamp3 lesson is that placeholder text must refuse to authorize anything.
    An angle-bracketed template value (``<name>``, ``<required: ...>``, ``<your signature>``) is
    a placeholder even when the generic-word list does not name it.
    """
    stripped = operator.strip()
    norm = " ".join(stripped.lower().split())
    return (
        norm in PLACEHOLDER_OPERATORS
        or len(stripped) < 2
        or (stripped.startswith("<") and stripped.endswith(">"))
    )


def approval_authorizes_tree(
    wd: Path,
    spec_name: str,
    phase_name: str,
    tree_hash: str,
    *,
    pre_head: str,
) -> tuple[bool, dict[str, Any]]:
    """Resolve the operator-approval escape for one (phase, tree). Returns ``(authorized, evidence)``.

    Contract (design §Gap 2): the artifact ``approvals/<spec>/<phase>_tree_reuse.md`` must
    (1) EXIST in the worktree and be committed BEFORE the phase ran — i.e. present in the
    committed tree at ``pre_head`` (an approval the phase itself commits is the gaming move,
    not an approval; with no pre-head no committed approval can predate the phase, so it is
    refused); (2) name the EXACT committed tree hash; (3) name THIS phase; (4) carry a REAL
    operator signature (non-placeholder) + a date. All four must hold — the gate checks the
    approval ledger first, and an approved reuse passes.
    """
    evidence: dict[str, Any] = {
        "authorized": False,
        "path": str(_approval_path(wd, spec_name, phase_name)),
        "present_at_pre_head": False,
    }
    path = _approval_path(wd, spec_name, phase_name)
    if pre_head:
        rel = path.relative_to(wd).as_posix()
        try:
            present = subprocess.run(
                ["git", "cat-file", "-e", f"{pre_head}:{rel}"],
                cwd=wd, capture_output=True, timeout=30,
            ).returncode == 0
        except Exception:  # noqa: BLE001 — an unresolvable pre-head refuses the approval
            present = False
        evidence["present_at_pre_head"] = present
    if not evidence["present_at_pre_head"]:
        evidence["failed_checks"] = ["committed_before_phase"]
        return False, evidence

    parsed = _parse_approval(path.read_text(encoding="utf-8"))
    evidence["parsed"] = parsed
    failed: list[str] = []
    if parsed.get("tree") != tree_hash:
        failed.append("tree")
    if parsed.get("phase") != phase_name:
        failed.append("phase")
    if _operator_is_placeholder(parsed.get("operator", "")):
        failed.append("operator")
    if not _date_is_valid(parsed.get("date", "")):
        failed.append("date")
    evidence["failed_checks"] = failed
    if not failed:
        evidence["authorized"] = True
        evidence["operator"] = parsed["operator"]
        evidence["date"] = parsed["date"]
    return evidence["authorized"], evidence


def _enforce_tree_gate(
    pr: PhaseResult,
    wd: Path,
    spec_name: str,
    phase_name: str,
    *,
    pre_head: str,
    ledger_path: Path | None = None,
) -> None:
    """Post-phase relabel tree-identity gate (cap_runner_hardening2 §Gap 2) — STRICT.

    Computes the phase's committed tree (HEAD after the phase). If it is EXACTLY a recorded
    discarded tree for this spec+branch, the phase is a relabel: discarded work re-presented
    as fresh work. The gate then resolves the operator-approval escape; an approved reuse
    passes (the evidence is recorded with ``authorized: true`` and the phase keeps its
    status); an unapproved one FAILS the phase with reason ``RELABEL`` + the identical-tree
    proof (both hashes + the matching discarded-tree record) on ``PhaseResult.relabel_gate``
    and the ledger. Agent phases only (the caller skips ``kind == "test"``); the runner's own
    ``_git_commit`` never consults this ledger — the gate is a separate post-phase check on
    the phase's committed tree. Best-effort by construction: an unresolvable git state
    degrades to "no tree, no match" (never a crash, never a gate that blocks on git problems).
    """
    phase_tree = _git_tree_hash(wd)
    if not phase_tree:
        return
    branch = _worktree_branch(wd)
    discarded = load_discarded_trees(spec_name, ledger_path=ledger_path)
    match = next(
        (
            d for d in discarded
            if d.get("tree_hash") == phase_tree and d.get("branch") == branch
        ),
        None,
    )
    if match is None:
        return
    authorized, approval = approval_authorizes_tree(
        wd, spec_name, phase_name, phase_tree, pre_head=pre_head
    )
    pr.relabel_gate = {
        "reason": "APPROVED" if authorized else "RELABEL",
        "phase_tree": phase_tree,
        "branch": branch,
        "matching_discarded_tree": match,
        "identical_tree_proof": {
            "discarded_tree_hash": match["tree_hash"],
            "phase_tree_hash": phase_tree,
            "empty_diff": True,  # identical content-addressed tree → byte-identical by construction
        },
        "approval": approval,
    }
    if authorized:
        return  # operator-approved reuse — the legit-restore path; the phase keeps its status
    msg = (
        f"RELABEL — phase '{phase_name}' committed tree {phase_tree}, which was recorded as "
        f"DISCARDED on {match.get('discarded_at')} (commit {match.get('commit')}, "
        f"reason={match.get('reason')}): discarded work re-presented as fresh work — the "
        f"identical-tree proof is that both trees ARE {phase_tree} (byte-identical). The "
        f"operator-approval escape is not in effect: an operator-signed "
        f"approvals/{spec_name}/{phase_name}_tree_reuse.md naming this tree + phase, "
        f"committed before the phase, authorizes the reuse."
    )
    if pr.status == "ok":
        pr.status = "failed"
        pr.error = msg
    else:
        pr.error = f"{pr.error}\n{msg}"


# ── Mechanical human checkpoint (cap_runner_hardening2 §Gap 3) ──────────────────────────────
#
# The revamp3 measured disease: p2 (the design + human checkpoint) committed the delta preview
# AND the unsigned approval template, then the runner moved straight into p3-p6, ran them
# (vacuous, no commits), and recorded ``ok: True`` while the approval sat unsigned — "STOP for
# the operator" was a sentence in the prompt, and prompt rules without mechanics get ignored
# (measured three times). The mechanical fix: a phase declaring ``checkpoint: true`` that
# completes successfully records the campaign state ``awaiting_operator_approval`` and EXITS
# CLEANLY (status ``awaiting`` — a designed stop, not an error). The approval contract is
# verified on ``--resume`` BEFORE any further phase runs: no artifact / placeholder signature /
# wrong commit order → the resume refuses to proceed and stops awaiting again.
#
# The approval contract (design §Gap 3): ``approvals/<spec>/<phase>_approval.md`` must
#   (1) exist in the worktree and be COMMITTED (tracked at HEAD);
#   (2) carry a REAL operator signature — a non-placeholder ``operator:`` (or
#       ``SIGNED-BY-OPERATOR:``) line + a real date (the revamp3 unsigned template's
#       ``<required: ...>`` values are placeholders and refuse to authorize);
#   (3) be a DESCENDANT of the checkpoint phase's commit — the approval file must NOT have
#       existed at the checkpoint commit AND the checkpoint commit must be an ancestor of HEAD,
#       so an approval committed WITH the checkpoint's work (or before it) never authorizes.

#: The phase-marker key: ``checkpoint: true`` declares a mechanical human stop.
CHECKPOINT_MARKER = "checkpoint"
#: The status value recorded when the run stops at (or refuses past) a checkpoint — a designed
#: stop, never an error; the operator's tools read "waiting", not "failed".
AWAITING_STATUS = "awaiting"

# ── I10 — typed checkpoint vocabulary ────────────────────────────────────────────────────────
#
# The session-routing v2 handoff needs a checkpoint as a TYPED, QUERYABLE event, not just a
# status string on the run. Every record below carries the fields session-routing v2 consumes:
# the phase + its index, the reason the checkpoint was recorded, the approval contract path,
# the decision outcome, the reached/decided timestamps (their delta IS the operator-await
# latency), and the phase's token/cost summary at the stop point. The vocabulary is a closed
# set — a record's ``reason``/``decision`` are always one of these four strings, so a
# downstream reducer never has to guess.

#: Why the record was written: the phase itself reached its designed stop (a ``checkpoint:
#: true`` phase completed → awaiting_operator_approval), or a resume re-read the approval
#: contract of an already-completed checkpoint phase.
CHECKPOINT_REASON_REACHED = "checkpoint_reached"
CHECKPOINT_REASON_APPROVAL_REQUIRED = "approval_required"
#: The decision outcome: the run is waiting for the operator (mechanical stop), the operator's
#: approval contract validated (resume proceeds), or the contract failed (resume refuses).
CHECKPOINT_DECISION_AWAITING = "awaiting"
CHECKPOINT_DECISION_APPROVED = "approved"
CHECKPOINT_DECISION_REJECTED = "rejected"


@dataclass
class CheckpointRecord:
    """Typed, ledgered record of one checkpoint event (I10 — session-routing v2 prerequisite).

    One record per checkpoint event, appended to ``WorkflowRunResult.checkpoints`` in
    chronological order. The mechanical stop path writes a ``checkpoint_reached``/``awaiting``
    record the moment the phase completes; the resume path writes an ``approval_required``
    record with decision ``approved`` or ``rejected`` for EVERY completed checkpoint phase
    whose contract it re-reads (the first rejected one is also where the resume stops).
    ``reached_at``/``decided_at`` are ISO-8601 UTC; on the resume path ``reached_at`` is
    carried over from the previous run's typed record (best-effort) so the operator-await
    latency (``decided_at - reached_at``) survives the ledger boundary. ``approval_evidence``
    is the ``_checkpoint_approval_valid`` evidence dict (contract checks + failed_checks +
    operator/date) — present on resume-decided records, ``None`` on a fresh mechanical stop.
    """

    phase: str
    phase_index: int  # 1-based index in the spec's phases list (0 = unresolved on resume)
    reason: str  # checkpoint_reached | approval_required
    approval_path: str  # the approval contract path (approvals/<spec>/<phase>_approval.md)
    decision: str  # awaiting | approved | rejected
    reached_at: str  # ISO-8601 UTC — when the phase reached its designed stop
    decided_at: str  # ISO-8601 UTC — when the decision was recorded
    cost_usd: float = 0.0  # the phase's cost at the stop point (resume: previous run's record)
    tokens: dict[str, int] = field(default_factory=dict)  # the phase's token summary at the stop
    commit_hash: str = ""  # the checkpoint phase's own commit ("" when unresolvable)
    approval_evidence: dict[str, Any] | None = None  # the contract-read evidence (resume path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "phase_index": self.phase_index,
            "reason": self.reason,
            "approval_path": self.approval_path,
            "decision": self.decision,
            "reached_at": self.reached_at,
            "decided_at": self.decided_at,
            "cost_usd": self.cost_usd,
            "tokens": dict(self.tokens),
            "commit_hash": self.commit_hash,
            "approval_evidence": self.approval_evidence,
        }


def _checkpoint_approval_path(wd: Path, spec_name: str, phase_name: str) -> Path:
    """``approvals/<spec>/<phase>_approval.md`` inside the worktree."""
    return wd / APPROVALS_DIRNAME / spec_name / f"{phase_name}_approval.md"


def _parse_checkpoint_approval(text: str) -> dict[str, str]:
    """Extract the operator signature + date from a checkpoint approval artifact.

    Accepts both the canonical ``- operator:`` / ``- date:`` lines and the revamp3 template's
    ``SIGNED-BY-OPERATOR:`` / ``DATE:`` lines (case-insensitive), so the real revamp3 artifact
    parses. Missing/placeholder fields fail their check downstream (no defaulting).
    """
    out: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip().lstrip("-* ").strip()
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip().lower()
        if key in ("operator", "signed-by-operator"):
            out["operator"] = value.strip()
        elif key in ("date",):
            out["date"] = value.strip()
    return out


def _phase_commit_sha(workdir: Path, phase_name: str, goal: str) -> str:
    """The full SHA of the phase's own ``[workflow] <phase> — <goal>`` commit, or ``""``.

    Mirrors ``_completed_phases``' subject matching exactly, so a phase the resume machinery
    considers completed is exactly one whose commit this finds. ``git log`` is newest-first, so
    the first match is the phase's LATEST commit — the state the approval must descend from.
    """
    try:
        log = subprocess.run(
            ["git", "log", "--format=%H %s"], cwd=workdir, capture_output=True, text=True, timeout=30
        )
    except Exception:  # noqa: BLE001 — a git problem degrades to "no checkpoint commit"
        return ""
    if log.returncode != 0:
        return ""
    goal_prefix = _goal_prefix(goal)
    for line in log.stdout.splitlines():
        sha, _, subject = line.partition(" ")
        m = COMMIT_SUBJECT_RE.search(subject)
        if m and m.group(1) == phase_name and m.group(2).startswith(goal_prefix):
            return sha.strip()
    return ""


def _checkpoint_approval_valid(
    wd: Path,
    spec_name: str,
    phase_name: str,
    checkpoint_commit: str,
) -> tuple[bool, dict[str, Any]]:
    """Verify the approval contract for one completed checkpoint phase. ``(valid, evidence)``.

    The contract: the artifact ``approvals/<spec>/<phase>_approval.md`` is committed at HEAD,
    was NOT present at the checkpoint commit (it was authored AFTER the checkpoint's work), the
    checkpoint commit is an ancestor of HEAD (the lineage is intact), and the artifact carries a
    REAL operator signature (non-placeholder) + a date. Any failure → ``(False, evidence)`` with
    the named reason — the resume refuses to proceed.
    """
    evidence: dict[str, Any] = {
        "valid": False,
        "path": str(_checkpoint_approval_path(wd, spec_name, phase_name)),
        "committed_at_head": False,
        "absent_at_checkpoint_commit": False,
        "checkpoint_is_ancestor": False,
    }
    path = _checkpoint_approval_path(wd, spec_name, phase_name)
    if not checkpoint_commit:
        evidence["failed_checks"] = ["no_checkpoint_commit"]
        return False, evidence
    if not path.exists():
        evidence["failed_checks"] = ["no_artifact"]
        return False, evidence
    rel = path.relative_to(wd).as_posix()
    try:
        at_head = subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{rel}"],
            cwd=wd, capture_output=True, timeout=30,
        ).returncode == 0
        at_checkpoint = subprocess.run(
            ["git", "cat-file", "-e", f"{checkpoint_commit}:{rel}"],
            cwd=wd, capture_output=True, timeout=30,
        ).returncode == 0
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", checkpoint_commit, "HEAD"],
            cwd=wd, capture_output=True, timeout=30,
        ).returncode == 0
    except Exception:  # noqa: BLE001 — an unresolvable git state refuses the approval
        at_head, at_checkpoint, ancestor = False, True, False
    evidence["committed_at_head"] = at_head
    evidence["absent_at_checkpoint_commit"] = not at_checkpoint
    evidence["checkpoint_is_ancestor"] = ancestor

    failed: list[str] = []
    if not at_head:
        failed.append("committed_at_head")
    if at_checkpoint:
        failed.append("authored_after_checkpoint")
    if not ancestor:
        failed.append("checkpoint_lineage_intact")
    if not failed:
        parsed = _parse_checkpoint_approval(path.read_text(encoding="utf-8"))
        evidence["parsed"] = parsed
        if _operator_is_placeholder(parsed.get("operator", "")):
            failed.append("operator")
        if not _date_is_valid(parsed.get("date", "")):
            failed.append("date")
        if not failed:
            evidence["valid"] = True
            evidence["operator"] = parsed["operator"]
            evidence["date"] = parsed["date"]
    evidence["failed_checks"] = failed
    return evidence["valid"], evidence


def _phase_index(phases: list[dict[str, Any]], phase_name: str) -> int:
    """1-based index of ``phase_name`` in the phases list (0 when not found)."""
    for i, phase_def in enumerate(phases, start=1):
        if str(phase_def.get("name", "?")) == phase_name:
            return i
    return 0


def _previous_checkpoint_state(spec: ExperimentSpec, phase: str) -> dict[str, Any] | None:
    """Best-effort: the previous run ledger's typed checkpoint record for ``phase`` (I10).

    The resume machinery reads the last checkpoint state from the spec index's latest run
    ledger (the same source ``_completed_phases_from_index`` uses). The typed record carries
    the phase's cost/token summary at the original stop plus its ``reached_at``, so a resume
    that re-reads the contract reproduces the operator-await latency (``decided_at -
    reached_at``) and the stop-point cost WITHOUT re-running the phase. Any failure — an
    unreadable ledger, a legacy checkpoint with no typed record, a spec outside the index —
    returns ``None`` and the caller falls back to the current time + a zeroed summary.
    """
    try:
        from agentic_dynamics.experiment.spec_status import index_entry

        entry = index_entry(spec.name)
        if entry is None or not entry.results_pointer:
            return None
        payload = json.loads((PROJECT_ROOT / entry.results_pointer).read_text())
        for cp in payload.get("checkpoints", []) or []:
            if isinstance(cp, dict) and cp.get("phase") == phase:
                return cp
    except Exception:
        return None
    return None


def _checkpoint_contract_decisions(
    wd: Path,
    spec: ExperimentSpec,
    phases: list[dict[str, Any]],
    completed: set[str],
    goal: str,
) -> tuple[list[tuple[str, bool, dict[str, Any]]], tuple[str, dict[str, Any]] | None]:
    """Evaluate every completed checkpoint phase's approval contract, in phase order.

    Returns ``(decisions, first_unsatisfied)``. ``decisions`` is one ``(phase_name, valid,
    evidence)`` triple per completed ``checkpoint: true`` phase — the I10 typed-capture
    input for the resume-decided path, which mints an approved/rejected record for every
    contract read whether or not the run then stops. ``first_unsatisfied`` is the first
    ``(phase_name, evidence)`` whose contract failed (in phase order), or ``None`` when
    every contract holds — the resume gate's refusal point. Identical semantics to the
    pre-I10 ``_first_unsatisfied_checkpoint``, which now delegates here.
    """
    decisions: list[tuple[str, bool, dict[str, Any]]] = []
    first_unsatisfied: tuple[str, dict[str, Any]] | None = None
    for phase_def in phases:
        if not phase_def.get(CHECKPOINT_MARKER):
            continue
        name = str(phase_def.get("name", "?"))
        if name not in completed:
            continue
        commit_sha = _phase_commit_sha(wd, name, goal)
        valid, evidence = _checkpoint_approval_valid(wd, spec.name, name, commit_sha)
        decisions.append((name, valid, evidence))
        if not valid and first_unsatisfied is None:
            first_unsatisfied = (name, evidence)
    return decisions, first_unsatisfied


def _first_unsatisfied_checkpoint(
    wd: Path,
    spec: ExperimentSpec,
    phases: list[dict[str, Any]],
    completed: set[str],
    goal: str,
) -> tuple[str, dict[str, Any]] | None:
    """The first completed checkpoint phase whose approval contract is unsatisfied, or ``None``.

    Used by the resume gate: every completed ``checkpoint: true`` phase must carry a valid
    operator approval BEFORE the run proceeds past it. Returns ``(phase_name, evidence)`` for
    the first violation (in phase order), so a resume stops at the earliest unsatisfied
    checkpoint — the revamp3 "ran p3-p6 past an unsigned template" shape is refused up front.
    Delegates to :func:`_checkpoint_contract_decisions` (I10) so the typed-capture and the
    gate read the contracts exactly once each.
    """
    _, unsatisfied = _checkpoint_contract_decisions(wd, spec, phases, completed, goal)
    return unsatisfied


def _build_attempt_records(result: WorkflowRunResult, job_id: str) -> list[AttemptRecord]:
    """Derive one :class:`AttemptRecord` per agent phase from the finished run's phases.

    Called AFTER the phase loop resolves, so every phase's final status — including a
    checkpoint phase's ``awaiting`` flip — is already recorded. Agent phases are the model
    invocations and are therefore the attempts; test phases run the language suite in-process
    and produce no attempt record (they are independent verification, not a model call).

    The emitted values are the schema's EXACT semantics, never invented: one attempt per phase
    (``attempt_number=1``), no retry (``retry_reason=""``), no model escalation
    (``escalation_from``/``escalation_to`` are ``None``), ``first_pass`` = the single attempt
    did not fail, and ``accepted`` = the outcome was accepted (``status == "ok"``).
    """
    records: list[AttemptRecord] = []
    for phase in result.phases:
        if phase.kind == "test":
            continue
        records.append(
            AttemptRecord(
                attempt_id=f"{job_id}_{phase.phase}_a1",
                job_id=job_id,
                phase=phase.phase,
                attempt_number=1,
                retry_reason="",
                first_pass=phase.status != "failed",
                accepted=phase.status == "ok",
                model=phase.model,
                status=phase.status,
                cost_usd=phase.cost_usd,
                tokens=dict(phase.tokens),
                test_executed_success=phase.test_executed_success,
                confidence=phase.confidence,
            )
        )
    return records


def run_workflow(
    spec: ExperimentSpec,
    *,
    goal: str,
    model: str,
    workdir: str | Path,
    backend: str | None = None,
    thinking_effort: str = "high",
    thinking_budget_tokens: int = 0,
    output_token_limit: int = 0,
    timeout: int = 1800,
    silent_mode: bool = False,
    enforce_pytest: bool = False,
    commit: bool = True,
    stop_on_error: bool = True,
    resume: bool = False,
    publish: bool = True,
    fork: bool | None = None,
    preferences: RoutingPreferences | None = None,
    signals: dict[str, ModelSignals] | None = None,
    router: Router | None = None,
    publisher_factory: Callable[[str], TelemetryPublisher] | None = None,
    run_agentic_fn: Callable[..., Any] | None = None,
    rag_augment: bool | None = None,
    retrieve_fn: Callable[..., Any] | None = None,
    construct_fn: Callable[..., Any] | None = None,
    rag_params: dict[str, Any] | None = None,
    change_analyzer: ChangeAnalyzer | None = None,
    phase_admission: PhaseAdmission | None = None,
    phase_watchdog_min: float | None = None,
    discarded_trees_ledger: Path | str | None = None,
) -> WorkflowRunResult:
    """Run a compiled ``agent_task`` spec against a goal in a git worktree.

    ``resume=True`` skips phases that already have a ``[workflow] <phase>`` commit and
    re-enters from the first incomplete phase (carrying prior-phase context).
    ``publish=True`` emits live telemetry to Redis so the Control Room shows the run as a
    cell (``story_status`` hash + ``status``/``events:<cell>`` channels). Each phase
    publishes a ``step_finish`` event carrying its tokens/cost, which feeds the ticker.
    ``fork=True`` chains each agent phase off the previous phase's session (opencode
    ``--session <id> --fork``; Claude CLI ``--resume <id> --fork-session``; same model
    only) so the shared context prefix is served as provider cache reads. ``fork=None``
    falls back to the spec's ``workflow.params.fork`` flag.
    ``enforce_pytest=False`` (default) stops the runner from injecting the blanket
    "Run pytest. Fix failures." standardized constraint into agent phases — each phase
    must specify its own tests, and a phase can opt in via ``enforce_pytest: true`` on
    the phase. ``run_agentic_fn`` is injectable so tests can substitute a fake agent.

    RAG augmentation (``retrieve -> construct -> render``) runs between ``route_step``
    and ``run_agent`` only when ``spec.workflow.params.rag_augment`` (or ``rag_augment=``)
    is true — default OFF, so the executor prompt stays byte-for-byte identical to
    ``_build_phase_prompt``. ``retrieve_fn`` / ``construct_fn`` are injectable; ``rag_params``
    carries budgets, ``constructor_model``, ``pinned_policy``, ``inherited_tools``, and
    ``user_constraints``. Test phases are never augmented; any retrieval/constructor
    failure falls back to the base prompt and records a named fallback mode.

    Self-build producer (``rag_params.emit_self``): when true, each successful phase that
    produced a commit also emits its one-line finding into the cell's OWN scope (default OFF).
    The finding is scoped via ``repository_id``/``acl_scope`` = ``cell_scope(wd)`` (never
    global) and keyed by ``f(goal, phase, commit, scope, extractor)``, so re-emitting is a
    no-op.

    Per-step routing (``docs/routing_design.md``): when the spec declares
    ``workflow.params.model_pool``, each agent phase's model is chosen by the injected
    ``router`` (``control.step_routing.route_step``, wired at the composition root) from the
    phase's selector (``model`` pin / ``allowed_models`` subset / full pool), scored by
    ``preferences`` over ``signals``. The router prices the cache-prefix loss of a model
    switch, so the existing fork chain (``fork: true``) keeps forking for free when it stays
    on the prior model. Without a ``model_pool`` the workflow is single-model (``model``) —
    backward compatible, and it needs no router.

    Spend gate (``phase_admission``, ``admission_leases`` p2): the runtime-owned
    ``runtime.admission.PhaseAdmission`` protocol, with ``control.admission``'s
    implementation injected at the composition root (``scripts/run_workflow.py``). Each
    agent phase reserves a budget + concurrency lease against the workflow's campaign
    scope BEFORE its model is invoked, and releases them when the phase ends. A refusal
    fails the phase with ``ADMISSION_DENIED`` and invokes nothing. Absent the injection —
    or with the gate disarmed — the seam is inert and the run is byte-identical.

    Phase-boundary evidence (``change_analyzer``, design §5.7 — e6 of cap_evidence_integrity):
    when a ``ChangeAnalyzer`` is injected at the composition root, each phase that commits
    ALSO hands its commit to the analyzer — the typed before/after CodeSnapshots + CodeDelta
    are materialized from git, and the analyzer returns the code-change facts + ACL-scoped
    executor neighborhood, recorded on ``PhaseResult.change_analysis``. Best-effort by
    construction: a materialization failure, an unanalyzable commit (e.g. a root commit with
    no parent), or an analyzer error degrades to ``change_analysis=None`` — it can never
    change the phase's outcome. ``None`` (default) leaves the seam inert.

    Phase watchdog (``phase_watchdog_min``, cap_runner_hardening p1): every agent phase
    is wrapped in a stall monitor that watches the session transcript's last-step age
    (``.instrument/session.jsonl``, appended live by the adapters while the seam is
    present). A transcript silent for ``phase_watchdog_min`` minutes — resolved explicit
    arg > ``FINOPS_PHASE_WATCHDOG_MIN`` env > default 20 — is SIGTERM'd and the phase
    fails with reason ``STALLED`` + evidence (last-step timestamp, stale age, transcript
    tail), recorded on ``PhaseResult.stall_evidence`` and the ledger. A value <= 0
    disables it. Only step gaps count (the transcript's last-step age, never wall time),
    and non-agent phases are never wrapped (test phases run in-process).

    Deploy gate (``deploy_allowed``, cap_runner_hardening p2): after every agent phase the
    runner scans the phase's session transcript for firebase production-deploy commands
    (``firebase deploy``, ``firebase --project <production-host>``, ``firebase hosting
    deploy``). A phase not marked ``deploy_allowed: true`` (optional per-phase marker,
    default false) that deployed fails with reason ``DEPLOY_GATE`` + the offending command +
    its transcript line, recorded on ``PhaseResult.deploy_gate`` and the ledger — the commit
    gate runs after, so a deploy violation can never be committed.

    Commit-prefix enforcement (cap_runner_hardening p3): after every agent phase the runner
    lists the commits made during it (``git log pre-head..HEAD``) and requires each to match
    ``[workflow] <phase> — <goal prefix>`` — the exact pattern the resume machinery matches.
    A plain-message commit fails the phase with reason ``COMMIT_PREFIX`` + the offending
    subjects, recorded on ``PhaseResult.commit_gate`` and the ledger, even if the phase
    otherwise succeeded — the campaign stops for the operator and the bad commit is never
    propagated by the commit gate (which runs after).

    Relabel tree-identity gate (cap_runner_hardening2 p2): after every agent phase the runner
    compares the phase's committed tree (``git rev-parse HEAD^{tree}``) against the
    discarded-trees ledger (``experiments/results/workflows/<spec>/discarded_trees.jsonl``).
    A tree recorded as discarded — the revamp2 relabel, attempt A's tree reset away then
    re-committed byte-identical under compliant messages — fails the phase with reason
    ``RELABEL`` + the identical-tree proof (both hashes + the matching discarded-tree record),
    recorded on ``PhaseResult.relabel_gate`` and the ledger. Strict always (never
    canonicalized). The operator-approval escape passes an approved reuse: an artifact
    ``approvals/<spec>/<phase>_tree_reuse.md`` committed before the phase (present at
    pre-head) that names the tree + phase + a real operator signature + a date. Off for
    non-agent phases; the runner's own ``_git_commit`` path is exempt (never consults the
    ledger).

    Mechanical human checkpoint (cap_runner_hardening2 p3): a phase declaring ``checkpoint: true``
    that completes successfully records the campaign state ``awaiting_operator_approval`` and
    EXITS CLEANLY — the phase status is ``awaiting`` (a designed stop, not an error) and the run
    result carries ``awaiting: true`` + the phase name + reason ``"checkpoint"``. The run's
    terminal ``state`` is ``awaiting_approval`` (never ``failed`` — ``ok`` remains ``False`` as
    the terminal-success bool, but the spec index reads the awaiting flag and derives the
    distinct status). On ``--resume``
    the runner verifies every completed checkpoint phase's approval contract
    (``approvals/<spec>/<phase>_approval.md``, committed at HEAD, authored AFTER the checkpoint
    commit, with a non-placeholder operator signature + a date) BEFORE proceeding; an
    unsatisfied checkpoint stops the resume with ``awaiting_operator_approval`` (reason
    ``"approval_refused"``) and NO further phase runs.
    """
    errors = validate_spec(spec)
    errors += validate_workflow_routing(spec, default_model=model)
    if errors:
        raise ValueError("invalid spec: " + "; ".join(errors))

    phases = spec.workflow.params.get("phases", [])
    if not phases:
        raise ValueError("workflow.params.phases is empty")

    wd = Path(workdir).resolve()
    if not wd.is_dir():
        raise ValueError(f"workdir not found: {wd}")

    language = str(spec.workflow.params.get("language") or "")
    if not language:
        profile = detect_language(wd)
        language = profile.name if profile else "python"

    run_agent = run_agentic_fn or run_agentic

    # RAG augmentation seam. Default OFF — the prompt passed to the executor is then
    # byte-for-byte identical to ``_build_phase_prompt``. ``retrieve_fn``/``construct_fn``
    # are injectable for tests; when unset, production resolves the real retrieve +
    # a constructor whose model call reuses ``run_agent`` (default flash model).
    rag_augment = rag_augment if rag_augment is not None else bool(
        spec.workflow.params.get("rag_augment", False)
    )
    rag_params = dict(rag_params or spec.workflow.params.get("rag", {}) or {})
    # Thread the per-cell scope through the retrieval filter: an augmented cell reads
    # only its own worktree's knowledge. Both repository_id and acl_scope default to
    # the cell scope BEFORE the retrieve fn is built; an explicitly non-empty
    # repository_id is the shared-scope override (coordinated parallel workstreams)
    # and is preserved unchanged — the empty scope never again means "global".
    if rag_augment and not str(rag_params.get("repository_id", "")).strip():
        scope = cell_scope(wd)
        rag_params["repository_id"] = scope
        rag_params["acl_scope"] = scope
    pinned_policy = str(rag_params.get("pinned_policy", ""))
    inherited_tools = list(rag_params.get("inherited_tools") or DEFAULT_INHERITED_TOOLS)

    result = WorkflowRunResult(
        spec_name=spec.name, spec_id=spec.spec_id, model=model, workdir=str(wd),
        goal=goal, started_at=_now(),
    )

    # Prefer the launch envelope's cell id (set by the Control Room via
    # ``FINOPS_CELL_ID``) so status, phase, and events land on the single cell the
    # operator is watching; fall back to the deterministic per-spec id for CLI runs.
    cell_id = os.environ.get("FINOPS_CELL_ID", "").strip() or _cell_id(spec.name, model)
    # Telemetry is injected, not imported (Debt-2): the composition root supplies the
    # control-plane publisher factory; without one, the run simply does not publish.
    publisher = publisher_factory(cell_id) if (publish and publisher_factory) else None
    if publisher is not None and publisher.enabled:
        publisher.set_status("running")
        publisher.publish_event({
            "type": "text", "sessionID": cell_id,
            "part": {"text": f"workflow {spec.name} — {goal[:120]}"},
        })

    prior: list[str] = []
    start_idx = 0
    completed: set[str] = set()
    if resume:
        phase_names = [str(p.get("name", "?")) for p in phases]
        # The git-log path stays primary and unchanged: a ``[workflow] <phase>`` commit in
        # this worktree is the strongest possible evidence a phase already ran here. Only
        # when it finds nothing — a worktree whose commits were squashed away, or a
        # --no-commit run — do we fall back to the derived index's latest run ledger.
        completed = _completed_phases(wd, phase_names, goal)
        if not completed:
            completed = _completed_phases_from_index(spec, phase_names, goal)
        for i, phase_def in enumerate(phases):
            name = str(phase_def.get("name", "?"))
            if name in completed:
                prior.append(f"{name} (ok)")
                start_idx = i + 1
            else:
                break

    # Mechanical human checkpoint (cap_runner_hardening2 §Gap 3) — resume gating. BEFORE any
    # further phase runs, every completed checkpoint phase's approval contract must be valid;
    # an unsatisfied checkpoint stops the resume with ``awaiting_operator_approval`` (refuses
    # to proceed). The revamp3 violation — p3-p6 ran past an unsigned approval template — is
    # refused here up front, deterministically.
    if resume:
        # I10 — typed checkpoint capture, the resume-decided path. Every completed checkpoint
        # phase whose contract this run re-reads mints an ``approval_required`` record with
        # decision ``approved``/``rejected`` + the contract evidence, BEFORE the gate acts on
        # the first refusal — so the resume machinery (and the spec index / checkpoint/v1
        # reducer) sees the full decision trace even when the run stops again. The reached_at
        # + cost/token summary ride over from the previous run's typed record (best-effort)
        # so the operator-await latency survives the ledger boundary.
        decisions, unsatisfied = _checkpoint_contract_decisions(wd, spec, phases, completed, goal)
        for cphase, valid, evidence in decisions:
            prev = _previous_checkpoint_state(spec, cphase)
            now = _now()
            record = CheckpointRecord(
                phase=cphase,
                phase_index=_phase_index(phases, cphase),
                reason=CHECKPOINT_REASON_APPROVAL_REQUIRED,
                approval_path=str(_checkpoint_approval_path(wd, spec.name, cphase)),
                decision=CHECKPOINT_DECISION_APPROVED if valid else CHECKPOINT_DECISION_REJECTED,
                reached_at=str((prev or {}).get("reached_at") or now),
                decided_at=now,
                cost_usd=float((prev or {}).get("cost_usd") or 0.0),
                tokens=dict((prev or {}).get("tokens") or {}),
                commit_hash=_phase_commit_sha(wd, cphase, goal),
                approval_evidence=evidence,
            )
            result.checkpoints.append(record)
            if publisher is not None and publisher.enabled:
                publisher.publish_event({
                    "type": "checkpoint", "sessionID": cell_id,
                    "part": record.to_dict(),
                })
        if unsatisfied is not None:
            phase_name, evidence = unsatisfied
            result.awaiting = True
            result.awaiting_phase = phase_name
            result.awaiting_reason = "approval_refused"
            result.ended_at = _now()
            result.git_sha = _git_head(wd)
            if publisher is not None and publisher.enabled:
                publisher.set_status("awaiting")
            return result

    fork_enabled = fork if fork is not None else bool(spec.workflow.params.get("fork", False))

    # Per-step routing context. The pool is the spec's ``model_pool`` when declared, else the
    # single run model (backward compatible). Preferences and the signal store may be passed
    # explicitly (tests) or carried in ``workflow.params`` (spec-driven).
    model_pool = resolve_pool(spec, default_model=model)
    if preferences is None:
        preferences = RoutingPreferences.from_dict(spec.workflow.params.get("preferences"))
    if signals is None:
        raw_signals = spec.workflow.params.get("signals") or {}
        signals = {m: ModelSignals.from_dict(d) for m, d in raw_signals.items()} if isinstance(
            raw_signals, dict
        ) else {}

    prev_session_id = ""
    prev_model = ""
    prev_cache_read_tokens = 0

    total = len(phases)
    for phase_idx, phase_def in enumerate(phases[start_idx:], start=start_idx):
        name = str(phase_def.get("name", "?"))
        kind = str(phase_def.get("kind", "agent"))
        phase_timeout = int(phase_def.get("timeout", timeout))
        pr = PhaseResult(
            phase=name, kind=kind, status="ok", spec_id=spec.spec_id,
            requires_deliverable=bool(phase_def.get("requires_deliverable", False)),
        )
        # Publish the live phase as each phase *starts* (1-based index over the full
        # list, so resume keeps the original position). Display-only badge data.
        if publisher is not None and publisher.enabled:
            publisher.set_phase({"name": name, "index": phase_idx + 1, "total": total})
        t0 = time.time()

        try:
            if kind == "test":
                suite = run_suite(wd, language, timeout=phase_timeout)
                pr.tests_passed = suite["passed"]
                pr.tests_total = suite["total"]
                pr.test_executed_success = suite_succeeded(suite)
                if suite.get("failed", 0) > 0 or suite.get("errors", 0) > 0:
                    pr.status = "failed"
                    pr.error = suite.get("tail", "")[-400:]
            else:
                prompt = _build_phase_prompt(phase_def, goal, prior)
                # Point the agent's built-in publisher at this workflow's cell so the
                # fine-grained session events stream into the Control Room.
                prev_cell = os.environ.get("FINOPS_CELL_ID")
                os.environ["FINOPS_CELL_ID"] = cell_id
                ar = None
                stall: dict[str, Any] | None = None
                pre_head = ""
                # The per-phase spend gate (admission_leases p2). An ExitStack rather
                # than a nested ``with`` because the leases can only be reserved once
                # the phase's model is KNOWN (the budget lease's currency follows the
                # provider class), which is several statements into the try below —
                # and they must still be released by the same ``finally`` that restores
                # the cell id, on every path including a raised phase.
                admission_gate = contextlib.ExitStack()
                try:
                    # Select this step's model: pin wins, allowed_models restricts, else the
                    # full pool — scored over measured signals, pricing a model switch's cache
                    # loss (§2/§4 of docs/routing_design.md).
                    state = RouteState(
                        pool=model_pool,
                        prev_model=prev_model or None,
                        prev_session_id=prev_session_id,
                        prev_cache_read_tokens=prev_cache_read_tokens,
                    )
                    if router is not None:
                        model_i = router(phase_def, state, preferences, signals=signals)
                    elif len(model_pool) <= 1:
                        # No router injected and a single-model workflow: use the run model
                        # directly (backward compatible — routing is a no-op here).
                        # PER-PHASE EXECUTION OVERRIDE (cap_site_revamp4 p5 — the
                        # independence lesson): a phase may declare ``run_model:`` (e.g. the
                        # independent review phase runs a DIFFERENT model/session than the
                        # author — the previous design promised it in prose and the runner
                        # never implemented it). ``run_model`` is DISTINCT from the routing
                        # selector key ``model`` (which is a pool member); the execution
                        # override wins over the run model and is exempt from pool
                        # validation by design.
                        model_i = phase_def.get("run_model") or (
                            model_pool[0] if model_pool else model
                        )
                    else:
                        raise ValueError(
                            "spec declares a multi-model model_pool but no router was injected "
                            "— inject control.step_routing.route_step at the composition root"
                        )

                    # ADMIT, then spend. The gate is entered the moment the executor
                    # model is known and BEFORE the augmentation seam (whose prompt
                    # constructor is itself a paid call), so every model invocation this
                    # phase makes happens inside the admission. A refusal raises
                    # ``AdmissionRefused`` here — before any prompt is built, any
                    # subprocess is spawned, or any token is spent — and the phase
                    # handler below records it as a failed phase. Inert (a no-op context)
                    # when no gate was injected or the gate is disarmed.
                    admission_gate.enter_context(
                        phase_admission_scope(phase_admission, name, model_i)
                    )

                    # RAG augmentation seam — retrieve -> construct -> render, placed
                    # between route_step and run_agent (never before routing, so the
                    # augmentation sees the selected executor model). Test phases bypass
                    # this entirely (they live in the ``kind == "test"`` branch).
                    if rag_augment:
                        pre_commit = _git_head(wd)
                        pr.pre_phase_commit = pre_commit
                        outcome = augment_prompt(
                            base_prompt=prompt,
                            goal=goal,
                            phase_def=phase_def,
                            model=model_i,
                            commit_sha=pre_commit or result.git_sha,
                            inherited_tools=inherited_tools,
                            pinned_policy=pinned_policy,
                            rag_params=rag_params,
                            retrieve_fn=retrieve_fn or default_retrieve_fn(),
                            construct_fn=construct_fn or default_construct_fn(rag_params, run_agent),
                        )
                        prompt = outcome.prompt
                        pr.raw_prompt_hash = outcome.raw_prompt_hash
                        pr.retrieval_attempt_id = outcome.retrieval_attempt_id
                        pr.constructor_attempt_id = outcome.constructor_attempt_id
                        pr.selected_evidence_ids = outcome.selected_evidence_ids
                        pr.augmentation_versions = outcome.versions
                        pr.augmentation_tokens = outcome.token_counts
                        pr.augmentation_cost_usd = outcome.cost_usd
                        pr.augmentation_latency_ms = outcome.latency_ms
                        pr.fallback_mode = outcome.fallback_mode

                    agent_kwargs: dict[str, Any] = {
                        "model": model_i,
                        "backend": backend,
                        "workdir": str(wd),
                        "thinking_effort": thinking_effort,
                        "thinking_budget_tokens": thinking_budget_tokens,
                        "output_token_limit": output_token_limit,
                        "timeout": phase_timeout,
                        "silent_mode": silent_mode,
                        "enforce_pytest": bool(
                            phase_def.get("enforce_pytest", enforce_pytest)
                        ),
                    }
                    # Cache-aware forking: reuse the previous phase's session prefix so
                    # the shared context is served as provider cache reads (DeepSeek
                    # cache read ~120x cheaper than input). A model switch breaks the
                    # cache prefix, so only fork when the model is unchanged. Both
                    # backends support it (opencode --session/--fork; claude --resume/--fork-session).
                    if (
                        fork_enabled
                        and prev_session_id
                        and prev_model == model_i
                    ):
                        agent_kwargs["session_id"] = prev_session_id
                        agent_kwargs["fork"] = True
                    pr.model = model_i

                    # Commit-prefix enforcement (cap_runner_hardening p3): record the worktree
                    # HEAD before the agent runs, so after the phase the runner can list exactly
                    # the commits the agent made during it (git log pre-head..HEAD).
                    pre_head = _git_head(wd)

                    # Commit-time prefix prevention (the drawing-board fix, 2026-08-28): a
                    # commit-msg hook installed before the phase rewrites any non-conforming
                    # subject to '[workflow] <phase> — <goal-prefix>' AT COMMIT TIME, so the
                    # agent cannot produce a violating commit — the post-phase gate becomes a
                    # backstop instead of a failure point. Canonicalize mode only; strict mode
                    # installs no hook (violations must stay visible for the evidence).
                    _install_commit_msg_hook(wd, name, goal)

                    # Phase watchdog (cap_runner_hardening p1) — wrap the agent invocation in a
                    # stall monitor. The monitor polls the session transcript's last-step age
                    # (``.instrument/session.jsonl``, appended live by the adapters while the seam
                    # is present) and fails the phase deterministically — SIGTERM + STALLED +
                    # evidence — when no new step appears for the threshold (explicit arg >
                    # ``FINOPS_PHASE_WATCHDOG_MIN`` env > default 20 min; a value <= 0 disables
                    # it). Only agent phases are wrapped; test phases run in-process, never
                    # through this path.
                    watchdog_min = _resolve_watchdog_min(phase_watchdog_min)
                    watchdog = PhaseWatchdog(wd, watchdog_min) if watchdog_min > 0 else None
                    if watchdog is not None:
                        agent_kwargs["watchdog"] = watchdog.seam
                        agent_kwargs["transcript_path"] = str(watchdog.transcript)
                    ar, stall = _run_agent_phase(run_agent, prompt, agent_kwargs, watchdog)
                    if stall is not None:
                        # The stalled agent was SIGTERM'd; the phase fails with the evidence
                        # (last-step timestamp, stale age, transcript tail) on the ledger.
                        pr.status = "failed"
                        pr.error = _format_stall_evidence(stall)
                        pr.stall_evidence = stall
                finally:
                    # Release the phase's leases before anything else: the headroom is
                    # returned as soon as the phase stops spending, whether it finished,
                    # failed, or was refused. (A missed release is still reclaimed by the
                    # lease TTL — release is the fast path, expiry is the guarantee.)
                    admission_gate.close()
                    if prev_cell is None:
                        os.environ.pop("FINOPS_CELL_ID", None)
                    else:
                        os.environ["FINOPS_CELL_ID"] = prev_cell
                if stall is None and ar is not None:
                    pr.tokens = {
                        "in": getattr(ar, "prompt_tokens", 0),
                        "out": getattr(ar, "completion_tokens", 0),
                        "reasoning": getattr(ar, "reasoning_tokens", 0),
                        "answer": getattr(ar, "answer_tokens", 0),
                        "explanation": getattr(ar, "explanation_tokens", 0),
                        "total": getattr(ar, "total_tokens", 0),
                    }
                    pr.cost_usd = getattr(ar, "estimated_cost_usd", 0.0)
                    pr.confidence = getattr(ar, "confidence", None)
                    pr.cache_read_tokens = getattr(ar, "cache_read_tokens", 0)
                    pr.cache_write_tokens = getattr(ar, "cache_write_tokens", 0)
                    pr.cache_hit_rate = round(getattr(ar, "cache_hit_rate", 0.0), 4)
                    sid = getattr(ar, "session_id", "")
                    if sid:
                        pr.session_id = sid
                        prev_session_id = sid
                    prev_model = model_i
                    prev_cache_read_tokens = getattr(ar, "cache_read_tokens", 0)
                    pr.files_created = list(getattr(ar, "files_created", []) or [])
                    pr.files_modified = list(getattr(ar, "files_modified", []) or [])
                    pr.final_response = getattr(ar, "final_response", "")
                    if not getattr(ar, "ok", True):
                        pr.status = "failed"
                        pr.error = getattr(ar, "error", "") or f"exit_code={getattr(ar, 'exit_code', '?')}"
        except AdmissionRefused as exc:
            # The spend gate refused this phase — and refusal means NO invocation
            # happened: ``phase_admission_scope`` is entered before the prompt is built
            # and before any adapter is touched. Recorded with a stable marker so the
            # ledger (and ``--resume``) can tell a budget refusal from a crash, and so
            # phase 4's quarantine rail can key off it.
            pr.status = "failed"
            pr.error = f"ADMISSION_DENIED: {exc}"
        except Exception as exc:  # one bad phase must not crash the runner
            pr.status = "failed"
            pr.error = repr(exc)

        # CAP test-runner wiring (the named seam, docs/designs/current/cap_test_runner_wiring.md
        # §1): an agent phase that declares ``test_gate: true`` gets the independent test_runner
        # over the worktree after the agent completes. Its outcome lands on
        # ``PhaseResult.test_executed_success`` — the only field ``attempt_facts/v1`` reads to
        # mint ``phase_test_verified`` (kind-agnostic downstream). Additive and opt-in: phases
        # without the gate, or an already-failed agent phase, leave the field ``None``
        # (null-not-zero — no defaulting, no fabrication). A failing gate fails the phase so the
        # commit below is skipped, exactly like the ``kind == "test"`` branch.
        if kind != "test" and phase_def.get("test_gate") and pr.status == "ok":
            _run_test_gate(pr, wd, language, phase_timeout)

        # Deploy gate (cap_runner_hardening p2) — post-phase, agent phases only. Scan the
        # phase's session transcript for firebase production-deploy commands; a hit in a phase
        # not marked ``deploy_allowed: true`` fails the phase with DEPLOY_GATE + the offending
        # command + its transcript line as evidence (recorded on the ledger). Runs BEFORE the
        # commit gate so a deploy violation can never be committed. A phase already failed
        # (e.g. STALLED) keeps its reason and gains the DEPLOY_GATE note.
        if kind != "test":
            _enforce_deploy_gate(pr, wd, phase_def)

        # Commit-prefix enforcement (cap_runner_hardening p3) — post-phase, agent phases only.
        # Every commit made during the phase (git log pre-head..HEAD) must match
        # '[workflow] <phase> — <goal prefix>' — the exact pattern the resume machinery matches.
        # A plain-message commit fails the phase with COMMIT_PREFIX + the offending subjects as
        # evidence, even if the phase otherwise succeeded (the campaign then stops for the
        # operator). Runs BEFORE the commit gate, so a bad commit can never be propagated as the
        # phase's own. The runner's own _git_commit writes the correct message (and runs after)
        # — this catches MANUAL agent commits.
        if kind != "test":
            _enforce_commit_prefix(pr, wd, name, goal, pre_head)

        # Doc-contract enforcement (the 2e merge lesson, 2026-08-28): an agent phase whose
        # range COMMITS or MODIFIES docs/**/*.md must deliver every such doc with a valid
        # status frontmatter (the doc-lifecycle contract vocabulary). The 2e p5 wrapper
        # authored two review docs without frontmatter; the merge went out red and the
        # controller patched after. A safety requirement in prose is advisory — this makes
        # the contract enforceable at phase time: a doc without (or with an unknown) status
        # field fails the phase with DOC_CONTRACT + the offending files, so a doc-writing
        # phase can never deliver an invalid doc. Strict, never canonicalized (the contract
        # layer is state, not render). The runner's own _git_commit never touches docs.
        if kind != "test":
            _enforce_doc_contract(pr, wd, pre_head)

        pr.duration_s = round(time.time() - t0, 2)
        if commit and pr.status == "ok":
            pr.commit_hash = _git_commit(wd, name, goal)
            # Phase-boundary evidence (design §5.7 — e6): when a ChangeAnalyzer is injected,
            # hand the committed change to it (typed snapshots + delta materialized from git)
            # and record its analysis on the phase. Best-effort — never affects the phase.
            if change_analyzer is not None and pr.commit_hash:
                _run_change_analysis(pr, wd, change_analyzer)
                # The evidence context rides the existing {prior_phases} channel so the NEXT
                # phase's prompt receives it (bounded, machine-readable: graph status, full
                # revision, neighborhood, facts) — only when an analyzer is injected AND this
                # phase produced an analysis. No analyzer → prior unchanged → prompt identical.
                if pr.change_analysis is not None:
                    prior.append(_evidence_context(pr))
            # Self-build ("progressive") producer — opt-in via rag_params.emit_self. After the
            # phase commits, emit its finding into the cell's OWN scope so the cell's retrieval
            # filter can later read its own progress (default OFF: only the "self-built" arm
            # opts in).
            if rag_params.get("emit_self") and pr.commit_hash:
                _emit_self_finding(pr, goal=goal, scope=cell_scope(wd))

        # Relabel tree-identity gate (cap_runner_hardening2 §Gap 2) — post-phase, agent phases
        # only, run AFTER the commit so the phase's committed tree is final. The phase's
        # committed tree (git rev-parse HEAD^{tree}) is compared against the discarded-trees
        # ledger (experiments/results/workflows/<spec>/discarded_trees.jsonl — the reset path
        # records every tree it discards). A tree that was discarded and is now re-presented
        # as this phase's fresh work fails RELABEL with the identical-tree proof, unless an
        # operator-signed approval artifact (approvals/<spec>/<phase>_tree_reuse.md, committed
        # before the phase) names the tree + phase. Strict always — a tree violation is never
        # canonicalized (unlike a message-only COMMIT_PREFIX violation). Off for non-agent
        # phases; the runner's own _git_commit path is exempt by construction (this gate is a
        # separate post-phase check and never runs inside _git_commit).
        if kind != "test":
            _enforce_tree_gate(
                pr,
                wd,
                spec.name,
                name,
                pre_head=pre_head,
                ledger_path=Path(discarded_trees_ledger) if discarded_trees_ledger else None,
            )

        prior.append(f"{name} ({pr.status})")
        result.phases.append(pr)

        if publisher is not None and publisher.enabled:
            tokens = pr.tokens or {}
            publisher.publish_event({
                "type": "step_finish", "sessionID": cell_id,
                "part": {
                    "text": f"phase {name} {pr.status}",
                    "tokens": {
                        "input": tokens.get("in", 0),
                        "output": tokens.get("out", 0),
                        "reasoning": tokens.get("reasoning", 0),
                        "total": tokens.get("total", 0),
                    },
                    "cost": pr.cost_usd,
                },
            })

        if pr.status == "failed" and stop_on_error:
            break

        # Mechanical human checkpoint (cap_runner_hardening2 §Gap 3) — the designed stop. A
        # phase declaring ``checkpoint: true`` that completes successfully (all gates passed, the
        # work committed) records the campaign state ``awaiting_operator_approval`` and EXITS
        # CLEANLY: the phase status flips to ``awaiting`` (a designed stop, not an error), the
        # run result carries the awaiting state, and the phase loop breaks. The approval
        # contract is enforced on --resume: the resume refuses to proceed past an unsatisfied
        # checkpoint. Agent phases only.
        if kind != "test" and phase_def.get(CHECKPOINT_MARKER) and pr.status == "ok":
            pr.status = AWAITING_STATUS
            result.awaiting = True
            result.awaiting_phase = name
            result.awaiting_reason = "checkpoint"
            # I10 — typed checkpoint capture, the mechanical stop. Record the designed stop
            # BEFORE the run exits so the resume machinery (and the spec index / checkpoint/v1
            # reducer) can read the last checkpoint state as a typed, queryable event: the
            # phase + index, the approval contract path, decision ``awaiting``, the reached/
            # decided timestamps (identical here — the run exits the instant it stops), and
            # the phase's token/cost summary at the stop point.
            now = _now()
            result.checkpoints.append(
                CheckpointRecord(
                    phase=name,
                    phase_index=phase_idx + 1,
                    reason=CHECKPOINT_REASON_REACHED,
                    approval_path=str(_checkpoint_approval_path(wd, spec.name, name)),
                    decision=CHECKPOINT_DECISION_AWAITING,
                    reached_at=now,
                    decided_at=now,
                    cost_usd=pr.cost_usd,
                    tokens=dict(pr.tokens),
                    commit_hash=pr.commit_hash,
                )
            )
            if publisher is not None and publisher.enabled:
                publisher.publish_event({
                    "type": "checkpoint", "sessionID": cell_id,
                    "part": result.checkpoints[-1].to_dict(),
                })
            break

    # ledger_instrumentation p1 — the attempt-level emission. Built from the FINAL phase
    # statuses (a checkpoint phase's ``awaiting`` flip is already recorded), so the attempt
    # fields the schema declares are measurable on the committed ledger. Empty for a resume
    # that refused past a checkpoint (no new phase ran) — additive, never a re-shape.
    result.attempts = _build_attempt_records(result, cell_id)
    result.ended_at = _now()
    result.git_sha = _git_head(wd)
    if publisher is not None and publisher.enabled:
        if result.awaiting:
            publisher.set_status("awaiting")
        else:
            publisher.set_status("done" if result.ok else "failed")
    return result
