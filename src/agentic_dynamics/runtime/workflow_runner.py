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
                    ar = run_agent(prompt, **agent_kwargs)
                finally:
                    if prev_cell is None:
                        os.environ.pop("FINOPS_CELL_ID", None)
                    else:
                        os.environ["FINOPS_CELL_ID"] = prev_cell
                pr.model = model_i
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
