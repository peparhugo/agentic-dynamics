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
correct message; the enforcement catches MANUAL agent commits.

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
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_dynamics.adapters.backends import run_agentic
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
        }


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

    @property
    def total_cost_usd(self) -> float:
        return round(sum(p.cost_usd for p in self.phases), 6)

    @property
    def ok(self) -> bool:
        return bool(self.phases) and all(p.status == "ok" for p in self.phases)

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
            "total_cost_usd": self.total_cost_usd,
            "ok": self.ok,
            "phases": [p.to_dict() for p in self.phases],
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
    goal_prefix = goal[:40]
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
        if str(payload.get("goal", ""))[:40] != goal[:40]:
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
            # was invoked, so catch it there when the literal command did not match.
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


def _git_log_subjects(workdir: Path, rev_range: str) -> list[tuple[str, str]]:
    """``(subject, author_email)`` pairs for commits in ``rev_range``, or [] on any git problem.

    Author email rides along so the enforcement can exempt the runner's OWN execution-layer
    commits (the adapter's fresh-worktree ``Initial`` commit) from the pattern check — it is
    not a manual agent commit, exactly like ``_git_commit``'s message (exempt by matching).
    """
    try:
        log = subprocess.run(
            ["git", "log", "--format=%s|%ae", rev_range],
            cwd=workdir, capture_output=True, text=True, timeout=30,
        )
    except Exception:  # noqa: BLE001 — a git problem degrades to "no commits to check"
        return []
    if log.returncode != 0:
        return []
    out: list[tuple[str, str]] = []
    for line in log.stdout.splitlines():
        if not line.strip():
            continue
        subject, _, email = line.partition("|")
        out.append((subject.strip(), email.strip()))
    return out


#: The adapter's worktree-initialization identity (``opencode._init_git_workdir``): the
#: ``Initial`` commit it creates in a genuinely-new worktree is the runner's own execution-layer
#: artifact, not a manual agent commit — the commit-prefix enforcement exempts it by author.
RUNNER_INIT_AUTHOR_EMAIL = "experiment@instrument.local"


def _enforce_commit_prefix(
    pr: PhaseResult, wd: Path, phase_name: str, goal: str, pre_head: str
) -> None:
    """Post-phase commit-prefix enforcement (cap_runner_hardening p3).

    Every commit the agent made during the phase (``git log pre_head..HEAD``; when there was
    no pre-phase HEAD — a fresh worktree — all of HEAD's commits) must match
    ``[workflow] <phase-name> — <goal prefix>``. A commit that does not fails the phase with
    reason ``COMMIT_PREFIX`` + the offending subjects as evidence, even if the phase otherwise
    succeeded — the phase flips to failed and ``stop_on_error`` stops the campaign for the
    operator. Agent phases only. The runner's OWN commits are exempt by construction: the
    runner's ``_git_commit`` message matches the pattern (and runs AFTER this check), and the
    adapter's fresh-worktree ``Initial`` commit is exempted by its author identity
    (``RUNNER_INIT_AUTHOR_EMAIL``) — the enforcement catches MANUAL agent commits. Best-effort:
    an unreadable git state degrades to "no commits to check".
    """
    goal_prefix = goal[:40]
    commits = (
        _git_log_subjects(wd, f"{pre_head}..HEAD")
        if pre_head
        else _git_log_subjects(wd, "HEAD")
    )
    bad = [
        s
        for s, author in commits
        if not (author == RUNNER_INIT_AUTHOR_EMAIL and s == "Initial")
        and not _commit_subject_matches(s, phase_name, goal_prefix)
    ]
    if not bad:
        return
    expected = f"[workflow] {phase_name} — {goal_prefix}"
    pr.commit_gate = {
        "reason": "COMMIT_PREFIX",
        "subjects": bad,
        "expected_prefix": expected,
    }
    msg = (
        f"COMMIT_PREFIX — commits made during phase '{phase_name}' do not match "
        f"'{expected}': {bad}"
    )
    if pr.status == "ok":
        pr.status = "failed"
        pr.error = msg
    else:
        pr.error = f"{pr.error}\n{msg}"


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
    phase_watchdog_min: float | None = None,
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
        pr = PhaseResult(phase=name, kind=kind, status="ok", spec_id=spec.spec_id)
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
                        model_i = model_pool[0] if model_pool else model
                    else:
                        raise ValueError(
                            "spec declares a multi-model model_pool but no router was injected "
                            "— inject control.step_routing.route_step at the composition root"
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

    result.ended_at = _now()
    result.git_sha = _git_head(wd)
    if publisher is not None and publisher.enabled:
        publisher.set_status("done" if result.ok else "failed")
    return result
