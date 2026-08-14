"""Execute an ``agent_task`` workflow — the ``execute`` phase of the spec/compiler DAG.

Drives an agent through a workflow's phases inside a git worktree, commits after each
phase, and records the ledger (tokens, cost, ``test_executed_success``) per phase. This
is the reusable-workflow engine: compile a spec, then run it against any goal / model /
worktree.

Phase kinds (from ``workflow.params.phases``):
  - ``agent`` (default) — invoke the LLM with the phase prompt. The prompt may use the
    ``{goal}`` and ``{prior_phases}`` placeholders.
  - ``test`` — run the language's suite independently (via ``test_runner.run_suite``)
    and record ``test_executed_success``. No LLM involved.

The agent works directly in ``workdir``; prior-phase artifacts are committed there, so
later phases read them from the repo. Fails fast by default (``stop_on_error``).
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backends import run_agentic
from .experiment_spec import ExperimentSpec, validate_spec
from .language import detect_language
from .live import LivePublisher
from .test_runner import run_suite, suite_succeeded


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PhaseResult:
    """Ledger record for one phase of a workflow run."""

    phase: str
    kind: str  # agent | test
    status: str  # ok | failed
    model: str = ""
    duration_s: float = 0.0
    commit_hash: str = ""
    error: str = ""
    # agent phases
    tokens: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    final_response: str = ""
    # test phases
    test_executed_success: bool | None = None
    tests_passed: int = 0
    tests_total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "kind": self.kind,
            "status": self.status,
            "model": self.model,
            "duration_s": self.duration_s,
            "commit_hash": self.commit_hash,
            "error": self.error,
            "tokens": self.tokens,
            "cost_usd": self.cost_usd,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "test_executed_success": self.test_executed_success,
            "tests_passed": self.tests_passed,
            "tests_total": self.tests_total,
        }


@dataclass
class WorkflowRunResult:
    """Ledger for a full workflow run."""

    spec_name: str
    model: str
    workdir: str
    goal: str
    phases: list[PhaseResult] = field(default_factory=list)
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
    """Stage and commit the worktree; return the short hash, or "" if nothing to commit."""
    try:
        subprocess.run(["git", "add", "-A"], cwd=workdir, capture_output=True, timeout=60)
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
    commit: bool = True,
    stop_on_error: bool = True,
    resume: bool = False,
    publish: bool = True,
    run_agentic_fn: Callable[..., Any] | None = None,
) -> WorkflowRunResult:
    """Run a compiled ``agent_task`` spec against a goal in a git worktree.

    ``resume=True`` skips phases that already have a ``[workflow] <phase>`` commit and
    re-enters from the first incomplete phase (carrying prior-phase context).
    ``publish=True`` emits live telemetry to Redis so the Control Room shows the run as a
    cell (``story_status`` hash + ``status``/``events:<cell>`` channels). Each phase
    publishes a ``step_finish`` event carrying its tokens/cost, which feeds the ticker.
    ``run_agentic_fn`` is injectable so tests can substitute a fake agent (no LLM).
    """
    errors = validate_spec(spec)
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
    result = WorkflowRunResult(
        spec_name=spec.name, model=model, workdir=str(wd), goal=goal, started_at=_now()
    )

    cell_id = _cell_id(spec.name, model)
    publisher = LivePublisher(cell_id) if publish else None
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
        completed = _completed_phases(wd, phase_names, goal)
        for i, phase_def in enumerate(phases):
            name = str(phase_def.get("name", "?"))
            if name in completed:
                prior.append(f"{name} (ok)")
                start_idx = i + 1
            else:
                break

    for phase_def in phases[start_idx:]:
        name = str(phase_def.get("name", "?"))
        kind = str(phase_def.get("kind", "agent"))
        phase_timeout = int(phase_def.get("timeout", timeout))
        pr = PhaseResult(phase=name, kind=kind, status="ok")
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
                    ar = run_agent(
                        prompt,
                        model=model,
                        backend=backend,
                        workdir=str(wd),
                        thinking_effort=thinking_effort,
                        thinking_budget_tokens=thinking_budget_tokens,
                        output_token_limit=output_token_limit,
                        timeout=phase_timeout,
                        silent_mode=silent_mode,
                    )
                finally:
                    if prev_cell is None:
                        os.environ.pop("FINOPS_CELL_ID", None)
                    else:
                        os.environ["FINOPS_CELL_ID"] = prev_cell
                pr.model = model
                pr.tokens = {
                    "in": getattr(ar, "prompt_tokens", 0),
                    "out": getattr(ar, "completion_tokens", 0),
                    "reasoning": getattr(ar, "reasoning_tokens", 0),
                    "total": getattr(ar, "total_tokens", 0),
                }
                pr.cost_usd = getattr(ar, "estimated_cost_usd", 0.0)
                pr.files_created = list(getattr(ar, "files_created", []) or [])
                pr.files_modified = list(getattr(ar, "files_modified", []) or [])
                pr.final_response = getattr(ar, "final_response", "")
                if not getattr(ar, "ok", True):
                    pr.status = "failed"
                    pr.error = getattr(ar, "error", "") or f"exit_code={getattr(ar, 'exit_code', '?')}"
        except Exception as exc:  # one bad phase must not crash the runner
            pr.status = "failed"
            pr.error = repr(exc)

        pr.duration_s = round(time.time() - t0, 2)
        if commit and pr.status == "ok":
            pr.commit_hash = _git_commit(wd, name, goal)

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
