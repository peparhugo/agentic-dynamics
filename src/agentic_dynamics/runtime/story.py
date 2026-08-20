"""Multi-session story orchestrator — sequential agentic sessions with git history.

Each experiment cell is a *story* — N sequential coding sessions, each building
on the prior session's git commit. This captures compounding effects
(architectural drift, convention erosion, decision cascading) that single-session
experiments cannot observe.

Architecture:
    Session 1 → git commit A → Session 2 (starts from A) → git commit B → ...
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from agentic_dynamics.adapters.backends import run_agentic
from agentic_dynamics.core.language import detect_language
from agentic_dynamics.measurement.mutation import (
    MutationArtifact,
    apply_mutation,
    compile_mutation,
)
from agentic_dynamics.adapters.opencode import AgenticResult
from agentic_dynamics.core.session_types import DEFAULT_TASK_TYPE
from agentic_dynamics.runtime.test_runner import run_suite, suite_succeeded

# ── Perturbation Condition ─────────────────────────────────────


class PerturbationCondition(str, Enum):
    """Experimental conditions for perturbing multi-session stories."""

    CLEAN = "clean"  # No mutation, no codebase degradation
    BAD_SEED = "bad_seed"  # Codebase degraded before session 1
    EARLY_DEGRADE = "early_degrade"  # Session 1 spec corrupted only
    LATE_DEGRADE = "late_degrade"  # Session 4 spec corrupted only (v1.5)


# Canonical mutation strength for the degrading conditions (BAD_SEED / EARLY_DEGRADE /
# LATE_DEGRADE). The strength axis is a first-class ledger field: CLEAN maps to
# s = 0.0 (the unperturbed baseline) and every degrading condition to this value,
# so a story result carries a numeric ``perturbation_strength``, not just the
# categorical ``perturbation_condition`` string.
CONDITION_STRENGTH = 0.5


def condition_to_mutations(
    condition: PerturbationCondition,
    codebase_path: Path,
    story_specs: list[str],
    *,
    compiler_model: str = "deepseek/deepseek-v4-flash",
    cache_dir: Path | None = None,
) -> tuple[MutationArtifact | None, dict[int, MutationArtifact]]:
    """Map a perturbation condition to specific mutations.

    For BAD_SEED: looks for a pre-generated 'bad/' variant at the same
    directory level. If found, returns a no-op artifact (the codebase
    is pre-degraded on disk). If not found, returns None (skip BAD_SEED).

    For EARLY_DEGRADE / LATE_DEGRADE: compiles spec mutations via Flash V4
    at runtime (these are cheap, single-prompt calls).

    Args:
        condition: Experimental condition.
        codebase_path: Path to seed codebase.
        story_specs: Session prompts in order.
        compiler_model: Model for mutation compilation.
        cache_dir: Optional cache directory.

    Returns:
        (codebase_mutation, {session_number: spec_mutation})
    """
    cache = cache_dir or Path("experiments/codebases/.mutation_cache")
    cache.mkdir(parents=True, exist_ok=True)

    if condition == PerturbationCondition.CLEAN:
        return None, {}

    if condition == PerturbationCondition.BAD_SEED:
        # Look for pre-generated bad variant on disk
        # e.g. ".../tier1_minimal/good" -> ".../tier1_minimal/bad"
        bad_path = codebase_path.parent / "bad"
        if bad_path.exists() and any(bad_path.iterdir()):
            return MutationArtifact(
                mutation_id="bad_seed_pregen",
                operator="bad_seed",
                operator_class="codebase",
                strength=CONDITION_STRENGTH,
                original_spec="Pre-generated bad variant",
                codebase_patch=f"Using pre-generated variant at {bad_path}",
            ), {}
        return None, {}

    if condition == PerturbationCondition.EARLY_DEGRADE:
        if not story_specs:
            return None, {}
        artifact = compile_mutation(
            specification=story_specs[0],
            operator="inject_false_premise",
            strength=CONDITION_STRENGTH,
            model=compiler_model,
            cache_dir=cache,
        )
        return None, {1: artifact}

    if condition == PerturbationCondition.LATE_DEGRADE:
        if len(story_specs) < 4:
            return None, {}
        artifact = compile_mutation(
            specification=story_specs[3],
            operator="remove_constraint",
            strength=CONDITION_STRENGTH,
            model=compiler_model,
            cache_dir=cache,
        )
        return None, {4: artifact}

    return None, {}


# ── Data Structures ────────────────────────────────────────────


@dataclass
class SessionSpec:
    """Definition of one session in a story."""

    session_number: int
    task_type: str  # see instrument.session_types.TASK_TYPES (greenfield, feature_addition, ...)
    prompt: str  # the actual task prompt for this session
    description: str = ""  # human-readable description

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_number": self.session_number,
            "task_type": self.task_type,
            "prompt": self.prompt,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SessionSpec:
        missing = [k for k in ("session_number", "prompt") if k not in d]
        if missing:
            raise ValueError(f"SessionSpec missing required fields: {missing}")
        return cls(
            session_number=d["session_number"],
            task_type=d.get("task_type", DEFAULT_TASK_TYPE),
            prompt=d["prompt"],
            description=d.get("description", ""),
        )


@dataclass
class StoryConfig:
    """Complete definition of a multi-session story.

    Can be loaded from YAML or constructed programmatically.
    """

    name: str
    description: str = ""
    language: str = "python"
    sessions: list[SessionSpec] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "language": self.language,
            "constraints": self.constraints,
            "sessions": [s.to_dict() for s in self.sessions],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StoryConfig:
        return cls(
            name=d["name"],
            description=d.get("description", ""),
            language=d.get("language", "python"),
            constraints=d.get("constraints", []),
            sessions=[SessionSpec.from_dict(s) for s in d.get("sessions", [])],
        )

    @classmethod
    def from_yaml(cls, path: Path) -> StoryConfig:
        with open(path) as f:
            return cls.from_dict(yaml.safe_load(f))

    def to_yaml(self, path: Path) -> None:
        path.write_text(yaml.dump(self.to_dict(), sort_keys=False))


@dataclass
class SessionResult:
    """Results from one session within a story."""

    session_number: int
    task_type: str
    prompt: str
    commit_hash: str = ""
    commit_message: str = ""
    agentic: AgenticResult | None = None
    cost_usd: float = 0.0
    total_tokens: int = 0
    duration_s: float = 0.0
    files_changed: int = 0
    exit_code: int = 0
    error: str = ""
    continuation_used: bool = False
    continuation_cost_usd: float = 0.0
    subagent_cost_usd: float = 0.0
    subagent_sessions: int = 0
    test_count: int = 0
    test_lines: int = 0
    code_lines: int = 0
    # Instrumented ledger fields (attempt-level).
    confidence: float | None = None  # [H] execution-confidence signal (opencode.AgenticResult.confidence)
    answer_tokens: int = 0  # output tokens → deliverable (tool-call steps)
    explanation_tokens: int = 0  # output tokens → prose narration

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "session_number": self.session_number,
            "task_type": self.task_type,
            "prompt": self.prompt[:200],
            "commit_hash": self.commit_hash,
            "commit_message": self.commit_message,
            "cost_usd": self.cost_usd,
            "total_tokens": self.total_tokens,
            "duration_s": self.duration_s,
            "files_changed": self.files_changed,
            "exit_code": self.exit_code,
            "error": self.error,
            "continuation_used": self.continuation_used,
            "continuation_cost_usd": self.continuation_cost_usd,
            "subagent_cost_usd": self.subagent_cost_usd,
            "subagent_sessions": self.subagent_sessions,
            "test_count": self.test_count,
            "test_lines": self.test_lines,
            "code_lines": self.code_lines,
            "confidence": self.confidence,
            "answer_tokens": self.answer_tokens,
            "explanation_tokens": self.explanation_tokens,
        }
        if self.agentic:
            d["agentic"] = {
                "tests_passed": self.agentic.tests_passed,
                "tests_total": self.agentic.tests_total,
                "tool_calls": self.agentic.total_tool_calls,
                "retries": self.agentic.retry_loops,
                "depth": self.agentic.iteration_depth,
                "files_created": self.agentic.files_created,
                "prompt_tokens": self.agentic.prompt_tokens,
                "completion_tokens": self.agentic.completion_tokens,
                "reasoning_tokens": self.agentic.reasoning_tokens,
                "answer_tokens": self.agentic.answer_tokens,
                "explanation_tokens": self.agentic.explanation_tokens,
                "total_tokens": self.agentic.total_tokens,
                "estimated_cost_usd": self.agentic.estimated_cost_usd,
                "cache_read_tokens": self.agentic.cache_read_tokens,
                "cache_write_tokens": self.agentic.cache_write_tokens,
                "context_tokens": self.agentic.context_tokens,
                "cache_hit_rate": round(self.agentic.cache_hit_rate, 3),
                "confidence": self.agentic.confidence,
            }
        return d


@dataclass
class StoryResult:
    """Aggregate results across all sessions in a story."""

    story_name: str
    story_id: str = ""
    codebase_path: str = ""
    language: str = ""
    model: str = ""
    mutation_id: str = ""
    perturbation_condition: str = ""
    started_at: str = ""
    completed_at: str = ""
    worktree: str = ""
    sessions: list[SessionResult] = field(default_factory=list)
    error: str = ""
    # Instrumented ledger fields (cell-level).
    perturbation_strength: float = 0.0  # the numeric strength axis (0.0 = CLEAN)
    test_executed_success: bool | None = None  # independently verified (test_runner), never self-report

    @property
    def total_cost(self) -> float:
        return sum(s.cost_usd for s in self.sessions)

    @property
    def total_continuation_cost(self) -> float:
        return sum(s.continuation_cost_usd for s in self.sessions)

    @property
    def total_subagent_cost(self) -> float:
        return sum(s.subagent_cost_usd for s in self.sessions)

    @property
    def total_subagent_sessions(self) -> int:
        return sum(s.subagent_sessions for s in self.sessions)

    @property
    def total_tokens(self) -> int:
        return sum(s.total_tokens for s in self.sessions)

    @property
    def total_cache_reads(self) -> int:
        return sum(s.agentic.cache_read_tokens for s in self.sessions if s.agentic)

    @property
    def total_cache_writes(self) -> int:
        return sum(s.agentic.cache_write_tokens for s in self.sessions if s.agentic)

    @property
    def total_context_tokens(self) -> int:
        return self.total_tokens + self.total_cache_reads

    @property
    def cache_hit_rate(self) -> float:
        total_context = self.total_context_tokens
        if total_context == 0:
            return 0.0
        return self.total_cache_reads / total_context

    @property
    def total_duration(self) -> float:
        return sum(s.duration_s for s in self.sessions)

    @property
    def session_count(self) -> int:
        return len(self.sessions)

    @property
    def all_successful(self) -> bool:
        return all(s.exit_code == 0 for s in self.sessions)

    @property
    def cascade_recovery(self) -> bool | None:
        """If session 1 had low correctness, did later sessions recover?

        Returns True if correctness improved from session 1 to last session.
        Returns False if it degraded or stayed the same.
        Returns None if no cascade data available.
        """
        if len(self.sessions) < 2:
            return None
        first = self.sessions[0]
        last = self.sessions[-1]
        if first.agentic is None or last.agentic is None:
            return None
        first_correctness = first.agentic.correctness
        last_correctness = last.agentic.correctness
        if first_correctness >= last_correctness:
            return False
        # Find the session where correctness stabilized
        for _i, s in enumerate(self.sessions):
            if s.agentic and s.agentic.correctness > first_correctness:
                return True
        return None

    @property
    def total_test_count(self) -> int:
        return sum(s.test_count for s in self.sessions)

    @property
    def total_test_lines(self) -> int:
        return sum(s.test_lines for s in self.sessions)

    @property
    def total_code_lines(self) -> int:
        return sum(s.code_lines for s in self.sessions)

    @property
    def test_code_ratio(self) -> float:
        if self.total_code_lines == 0:
            return 0.0
        return self.total_test_lines / self.total_code_lines

    def to_dict(self) -> dict[str, Any]:
        return {
            "story_name": self.story_name,
            "story_id": self.story_id,
            "codebase_path": self.codebase_path,
            "language": self.language,
            "model": self.model,
            "mutation_id": self.mutation_id,
            "perturbation_condition": self.perturbation_condition,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "worktree": self.worktree,
            "error": self.error,
            "perturbation_strength": self.perturbation_strength,
            "test_executed_success": self.test_executed_success,
            "summary": {
                "total_cost": self.total_cost,
                "total_continuation_cost": self.total_continuation_cost,
                "total_subagent_cost": self.total_subagent_cost,
                "total_subagent_sessions": self.total_subagent_sessions,
                "total_tokens": self.total_tokens,
                "total_cache_reads": self.total_cache_reads,
                "total_cache_writes": self.total_cache_writes,
                "total_context_tokens": self.total_context_tokens,
                "cache_hit_rate": round(self.cache_hit_rate, 3),
                "test_count": self.total_test_count,
                "test_lines": self.total_test_lines,
                "code_lines": self.total_code_lines,
                "test_code_ratio": round(self.test_code_ratio, 3),
                "total_duration": self.total_duration,
                "session_count": self.session_count,
                "all_successful": self.all_successful,
                "cascade_recovery": self.cascade_recovery,
            },
            "sessions": [s.to_dict() for s in self.sessions],
        }


# ── Story Runner ───────────────────────────────────────────────


def run_story(
    story: StoryConfig,
    *,
    codebase_path: str,
    model: str = "deepseek/deepseek-v4-pro",
    condition: PerturbationCondition = PerturbationCondition.CLEAN,
    mutation: MutationArtifact | None = None,
    worktree_root: str = "/tmp",
    timeout: int = 600,
    thinking_budget_tokens: int = 0,
    output_token_limit: int = 0,
    silent_mode: bool | None = None,
    standardize: bool = True,
    enforce_pytest: bool = True,
    backend: str | None = None,
) -> StoryResult:
    """Run a complete multi-session story.

    Creates an isolated worktree, clones the codebase, applies condition,
    then runs each session sequentially with git commits between sessions.

    Args:
        story: StoryConfig defining session sequence and prompts.
        codebase_path: Path to the seed codebase to clone.
        model: Model ID for all sessions.
        condition: PerturbationCondition to apply.
        mutation: Optional explicit MutationArtifact (overrides condition).
        worktree_root: Parent directory for isolated worktrees.
        timeout: Per-session timeout in seconds.
        thinking_budget_tokens: Token budget for reasoning.
        output_token_limit: Output token limit.
        silent_mode: None=natural, True=forced-silent, False=forced-verbose.
        standardize: Apply standardized prompt constraints.
        enforce_pytest: Require pytest execution.
        backend: Optional backend override (``opencode`` or ``claude_cli``);
            defaults to auto-routing via ``get_backend_for_model``.

    Returns:
        StoryResult with per-session results and aggregate summary.
    """
    if not story.sessions:
        raise ValueError(f"Story '{story.name}' has no sessions defined")

    story_id = hashlib.sha256(
        f"{story.name}|{model}|{codebase_path}|{condition.value}|{time.monotonic()}".encode()
    ).hexdigest()[:12]

    worktree = Path(worktree_root) / f"story_{story_id}"
    if worktree.exists():
        shutil.rmtree(worktree)

    # Resolve condition to mutations
    codebase_path_obj = Path(codebase_path)

    # BAD_SEED condition: use the pre-generated bad variant on disk
    actual_codebase_path = codebase_path
    if condition == PerturbationCondition.BAD_SEED:
        bad_path = codebase_path_obj.parent / "bad"
        if bad_path.exists() and any(bad_path.iterdir()):
            actual_codebase_path = str(bad_path)

    story_specs = [s.prompt for s in story.sessions]
    codebase_mutation = None
    spec_mutations = {}
    if mutation is None and condition != PerturbationCondition.CLEAN:
        codebase_mutation, spec_mutations = condition_to_mutations(
            condition,
            codebase_path_obj,
            story_specs,
        )

    result = StoryResult(
        story_name=story.name,
        story_id=story_id,
        codebase_path=codebase_path,
        language=story.language,
        model=model,
        mutation_id="",
        perturbation_condition=condition.value,
        perturbation_strength=0.0 if condition == PerturbationCondition.CLEAN else CONDITION_STRENGTH,
        started_at=datetime.now(timezone.utc).isoformat(),
        worktree=str(worktree),
    )

    try:
        _prepare_worktree(
            actual_codebase_path,
            worktree,
            codebase_mutation
            if codebase_mutation and codebase_mutation.would_produce_changes()
            else None,
        )
        result.language = _detect_or_use(worktree, story.language)

        for spec in story.sessions:
            # Check if this session has a spec-level mutation
            session_mutation = spec_mutations.get(spec.session_number)
            session_prompt = spec.prompt
            if session_mutation and session_mutation.mutated_spec:
                session_prompt = session_mutation.mutated_spec
                result.mutation_id = session_mutation.mutation_id

            session_result = _run_session(
                spec=SessionSpec(
                    session_number=spec.session_number,
                    task_type=spec.task_type,
                    prompt=session_prompt,
                    description=spec.description,
                ),
                worktree=worktree,
                model=model,
                session_name=f"[{story.name}] Session {spec.session_number}: {spec.task_type}",
                timeout=timeout,
                thinking_budget_tokens=thinking_budget_tokens,
                output_token_limit=output_token_limit,
                silent_mode=silent_mode,
                standardize=standardize,
                enforce_pytest=enforce_pytest,
                backend=backend,
            )
            result.sessions.append(session_result)

            if session_result.error:
                result.error = f"Session {spec.session_number} failed: {session_result.error}"
                break

    except Exception as e:
        result.error = str(e)
    finally:
        result.completed_at = datetime.now(timezone.utc).isoformat()

    # Independently verify the story's tests against the final worktree state.
    # ``test_executed_success`` is measured by the harness (test_runner.run_suite),
    # never the model's self-reported tests_passed/tests_total. It runs even when a
    # session errored — a failed story simply fails its suite — so every cell
    # records a verified bool.
    try:
        suite = run_suite(worktree, result.language or "python")
        result.test_executed_success = suite_succeeded(suite)
    except Exception:
        result.test_executed_success = False

    return result


def _prepare_worktree(
    codebase_path: str,
    worktree: Path,
    mutation: MutationArtifact | None,
) -> None:
    """Clone codebase into worktree, init git, apply mutation."""
    src = Path(codebase_path)
    if not src.exists():
        raise FileNotFoundError(f"Codebase not found: {codebase_path}")

    shutil.copytree(src, worktree)

    # Init git repo
    _git(worktree, "init")
    _git(worktree, "config", "user.email", "instrument@ai-finops.dynamics")
    _git(worktree, "config", "user.name", "AI FinOps Dynamics Instrument")
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "-m", "Initial seed codebase")

    # Apply mutation before first session
    if mutation and mutation.would_produce_changes():
        apply_mutation(mutation, worktree)
        _git(worktree, "add", "-A")
        _git(worktree, "commit", "-m", f"[mutation] {mutation.operator} s={mutation.strength}")


def _count_tests(worktree: Path) -> tuple[int, int, int]:
    """Count test functions, test lines, and non-test code lines in worktree."""
    import re as _re
    test_count = 0
    test_lines = 0
    code_lines = 0
    for f in worktree.rglob("*.py"):
        if "__pycache__" in str(f) or ".pytest_cache" in str(f):
            continue
        try:
            content = f.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        n = len(content.splitlines())
        if "test" in f.name.lower() or f.parent.name == "tests":
            test_lines += n
            test_count += len(_re.findall(r"def test_\w+", content))
        else:
            code_lines += n
    return test_count, test_lines, code_lines


def _run_session(
    spec: SessionSpec,
    worktree: Path,
    model: str,
    session_name: str,
    timeout: int,
    thinking_budget_tokens: int,
    output_token_limit: int,
    silent_mode: bool | None,
    standardize: bool,
    enforce_pytest: bool,
    backend: str | None = None,
) -> SessionResult:
    """Run one session in the story and commit its output.

    If the session times out, automatically runs a continuation via
    opencode's --session --fork mechanism to recover the work. The
    combined cost (original + continuation) is recorded.
    """
    files_before = _list_tracked_files(worktree)
    t0 = time.monotonic()

    # Per-session transcript, preserved across sessions (each session would
    # otherwise overwrite the single .instrument/session.jsonl file).
    transcript_path = worktree / ".instrument" / f"session_{spec.session_number}.jsonl"

    agentic = run_agentic(
        spec.prompt,
        model=model,
        workdir=str(worktree),
        timeout=timeout,
        thinking_budget_tokens=thinking_budget_tokens,
        output_token_limit=output_token_limit,
        silent_mode=silent_mode,
        standardize=standardize,
        enforce_pytest=enforce_pytest,
        session_name=session_name,
        backend=backend,
        transcript_path=str(transcript_path),
    )

    # Mirror the current session's transcript to the canonical session.jsonl so
    # single-file consumers (continuation logic, artifact bundling) keep working.
    if transcript_path.exists():
        shutil.copy2(transcript_path, worktree / ".instrument" / "session.jsonl")

    total_cost = agentic.estimated_cost_usd if agentic else 0.0
    total_tokens = agentic.total_tokens if agentic else 0
    continuation_used = False
    continuation_cost = 0.0
    continuation_tokens = 0

    # Primary session id — needed for subagent cost capture and fork continuation.
    jsonl_path = worktree / ".instrument" / "session.jsonl"
    primary_session_id = _read_session_id(jsonl_path)
    if not primary_session_id and transcript_path.exists():
        primary_session_id = _read_session_id(transcript_path)

    # Capture @explore (and other) subagent sessions spawned via the task tool.
    # These live in opencode.db with parent_id = primary session id.
    subagent_cost, subagent_sessions = _estimate_subagent_cost(primary_session_id)

    # If timed out, automatically continue the session. This continuation uses
    # opencode's --session --fork mechanism, so it only applies to the opencode
    # backend (Claude CLI has no equivalent forkable session id).
    if (
        agentic is not None
        and agentic.error
        and "timeout" in agentic.error.lower()
        and (backend or "").lower() not in ("claude_cli", "claude")
        and primary_session_id
    ):
        opencode_bin = os.environ.get(
            "OPENCODE_BIN", str(Path.home() / ".opencode/bin/opencode")
        )
        try:
            cont_result = subprocess.run(
                [
                    opencode_bin,
                    "run",
                    "--session",
                    primary_session_id,
                    "--fork",
                    "--dir",
                    str(worktree),
                    "--model",
                    model,
                    "--format",
                    "json",
                    "--auto",
                    "Continue. Complete the task. Run tests and finish.",
                ],
                capture_output=True,
                text=True,
                timeout=timeout * 2,
            )
        except subprocess.TimeoutExpired:
            cont_result = None
            print(
                f"[story] continuation failed: subprocess timed out (session {primary_session_id})",
                file=sys.stderr,
            )

        if cont_result is not None:
            continuation_used = True

            # The fork creates a NEW session. Bill the fork's own id, not the
            # primary's — querying the primary again double-counted its cost.
            fork_session_id = _extract_session_id_from_stdout(cont_result.stdout)
            cont_cost = _estimate_session_cost(fork_session_id or primary_session_id)
            continuation_cost += cont_cost

            cont_tokens = _sum_billed_tokens_from_jsonl(cont_result.stdout)
            continuation_tokens += cont_tokens

            if cont_result.returncode == 0:
                agentic.error = ""
                agentic.exit_code = 0

    duration = time.monotonic() - t0

    # Commit all changes
    commit_hash = ""
    commit_msg = f"[story] Session {spec.session_number}: {spec.task_type}"
    _git(worktree, "add", "-A")

    status = _git(worktree, "status", "--porcelain")
    if status.strip():
        _git(worktree, "commit", "-m", commit_msg, "--allow-empty")
        commit_hash = _git(worktree, "rev-parse", "HEAD").strip()

    files_after = _list_tracked_files(worktree)
    files_changed = len(files_after.symmetric_difference(files_before))

    test_count, test_lines, code_lines = _count_tests(worktree)

    return SessionResult(
        session_number=spec.session_number,
        task_type=spec.task_type,
        prompt=spec.prompt,
        commit_hash=commit_hash,
        commit_message=commit_msg,
        agentic=agentic,
        cost_usd=round(total_cost + continuation_cost + subagent_cost, 8),
        total_tokens=total_tokens + continuation_tokens,
        duration_s=duration,
        files_changed=files_changed,
        exit_code=agentic.exit_code if agentic else -1,
        error=agentic.error if agentic else "",
        continuation_used=continuation_used,
        continuation_cost_usd=round(continuation_cost, 8),
        subagent_cost_usd=round(subagent_cost, 8),
        subagent_sessions=subagent_sessions,
        test_count=test_count,
        test_lines=test_lines,
        code_lines=code_lines,
        confidence=agentic.confidence if agentic else None,
        answer_tokens=agentic.answer_tokens if agentic else 0,
        explanation_tokens=agentic.explanation_tokens if agentic else 0,
    )


def _opencode_db() -> Path:
    """Path to opencode's SQLite database (session cost/token ground truth)."""
    return Path.home() / ".local/share/opencode/opencode.db"


def _read_session_id(transcript_path: Path) -> str:
    """Extract the sessionID from the first JSONL line of a transcript."""
    if not transcript_path.exists():
        return ""
    try:
        with open(transcript_path) as f:
            first = json.loads(f.readline())
            return first.get("sessionID", "")
    except (json.JSONDecodeError, OSError):
        return ""


def _extract_session_id_from_stdout(stdout: str) -> str:
    """Extract the sessionID from the first JSONL event in a subprocess stdout."""
    if not stdout:
        return ""
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = obj.get("sessionID", "")
        if sid:
            return sid
    return ""


def _sum_billed_tokens_from_jsonl(stdout: str) -> int:
    """Sum billed tokens from step_finish events in a JSONL stdout.

    Billed tokens = prompt + completion + reasoning (cache reads excluded),
    matching the primary-run accounting in opencode.py.
    """
    total = 0
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "step_finish":
            continue
        part = obj.get("part", {})
        tokens = part.get("tokens", {}) if isinstance(part, dict) else {}
        if isinstance(tokens, dict):
            total += (
                (tokens.get("input", 0) or 0)
                + (tokens.get("output", 0) or 0)
                + (tokens.get("reasoning", 0) or 0)
            )
    return total


def _estimate_session_cost(session_id: str) -> float:
    """Estimate the cost of a session from opencode's database (exact id match).

    The session id must be the exact id of the session whose cost we want.
    No LIKE fallback — that matched the wrong session and double-counted.
    """
    import sqlite3 as _sql

    db_path = _opencode_db()
    if not session_id or not db_path.exists():
        return 0.0
    try:
        conn = _sql.connect(str(db_path))
        rows = conn.execute(
            "SELECT cost FROM session WHERE id = ?",
            (session_id,),
        ).fetchall()
        conn.close()
        if rows and rows[0][0] is not None:
            return float(rows[0][0])
    except Exception:
        pass
    return 0.0


def _estimate_subagent_cost(parent_session_id: str) -> tuple[float, int]:
    """Sum cost and count of subagent sessions spawned by a parent session.

    Subagent sessions (e.g. @explore) have parent_id set in the DB, unlike
    fork continuations which have parent_id = NULL.
    """
    import sqlite3 as _sql

    db_path = _opencode_db()
    if not parent_session_id or not db_path.exists():
        return 0.0, 0
    try:
        conn = _sql.connect(str(db_path))
        rows = conn.execute(
            "SELECT COALESCE(SUM(cost), 0), COUNT(*) FROM session WHERE parent_id = ?",
            (parent_session_id,),
        ).fetchall()
        conn.close()
        if rows:
            return float(rows[0][0] or 0.0), int(rows[0][1] or 0)
    except Exception:
        pass
    return 0.0, 0


# ── Git Helpers ────────────────────────────────────────────────


def _git(worktree: Path, *args: str) -> str:
    """Run a git command in the worktree. Returns stdout. Raises on failure.

    A git failure is fatal for the instrument — returning error text through a
    value channel previously leaked "git error: …" into commit_hash and diff
    counts (P1-2). Fail loudly instead.
    """
    proc = subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
        cwd=str(worktree),
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (exit {proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout


def _detect_or_use(worktree: Path, fallback: str) -> str:
    """Detect language from worktree files, fall back to configured value."""
    profile = detect_language(worktree)
    return profile.name if profile else fallback


def _list_tracked_files(worktree: Path) -> set[str]:
    """List all files tracked by git in the worktree."""
    out = _git(worktree, "ls-files")
    return {f for f in out.splitlines() if f.strip()}


# ── Story Persistence ─────────────────────────────────────────


def save_story_result(result: StoryResult, path: Path) -> None:
    """Save a StoryResult as JSON, then register it inline (write-time registration).

    canonical-state round 2, plan step 10 (Delta 1): this call site is why
    finding-1-style stranding cannot recur — a *scan* would only discover a story JSON if
    it happened to be pointed at the right worktree (which is exactly what stranded the
    original ~59), but this inline emit always fires the moment the file is durably
    written, regardless of which worktree that happens to be.

    Gated on ``FINOPS_KB_WRITE`` (opt-in, same convention as every existing KB writer in
    this package) so a plain ``save_story_result`` call from a test or a read-only tool
    never accidentally emits. Deliberately UNWRAPPED in a try/except once the flag is
    set — ``knowledge_stream.connect()``'s own documented contract is "a downed stream
    must be visible, not silently dropped" (unlike ``live.py``'s best-effort telemetry
    connect), and every other batch producer in this package (``kb_produce.py``,
    ``kb_produce_sources.py``, ``kb_produce_registry.py``) already honors that contract by
    letting a connection failure raise. An operator who has explicitly opted into
    ``FINOPS_KB_WRITE=1`` gets the same loud-failure guarantee here. Contrast this with
    ``scripts/supervise.py``'s inline emit (plan step 13): that IS best-effort, because it
    sits inside a live, always-running assessment loop where crashing on a downed KB
    stream would take down the flag-only supervisor's actual job — a fundamentally
    different availability trade-off than a one-shot story run's final persistence step.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2))

    if os.environ.get("FINOPS_KB_WRITE") == "1":
        from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID
        from agentic_dynamics.knowledge.knowledge_stream import register_records
        from agentic_dynamics.knowledge.story_ingestion import derive_story_records

        register_records(
            derive_story_records(result.to_dict(), repository_id=REPOSITORY_ID),
            fail_loud=True,
        )


def load_story_result(path: Path) -> StoryResult:
    """Load a StoryResult from JSON."""
    with open(path) as f:
        d = json.load(f)
    result = StoryResult(
        story_name=d["story_name"],
        story_id=d.get("story_id", ""),
        codebase_path=d.get("codebase_path", ""),
        language=d.get("language", ""),
        model=d.get("model", ""),
        mutation_id=d.get("mutation_id", ""),
        perturbation_condition=d.get("perturbation_condition", ""),
        started_at=d.get("started_at", ""),
        completed_at=d.get("completed_at", ""),
        worktree=d.get("worktree", ""),
        error=d.get("error", ""),
        perturbation_strength=d.get("perturbation_strength", 0.0),
        test_executed_success=d.get("test_executed_success"),
    )
    for s in d.get("sessions", []):
        # Rebuild AgenticResult from JSON if present
        agentic = None
        if "agentic" in s and s["agentic"]:
            a = s["agentic"]
            agentic = AgenticResult(
                tests_passed=a.get("tests_passed", 0),
                tests_total=a.get("tests_total", 0),
                answer_tokens=a.get("answer_tokens", 0),
                explanation_tokens=a.get("explanation_tokens", 0),
            )
        result.sessions.append(
            SessionResult(
                session_number=s["session_number"],
                task_type=s.get("task_type", ""),
                prompt=s.get("prompt", ""),
                commit_hash=s.get("commit_hash", ""),
                commit_message=s.get("commit_message", ""),
                cost_usd=s.get("cost_usd", 0.0),
                total_tokens=s.get("total_tokens", 0),
                duration_s=s.get("duration_s", 0.0),
                files_changed=s.get("files_changed", 0),
                exit_code=s.get("exit_code", 0),
                error=s.get("error", ""),
                continuation_used=s.get("continuation_used", False),
                continuation_cost_usd=s.get("continuation_cost_usd", 0.0),
                subagent_cost_usd=s.get("subagent_cost_usd", 0.0),
                subagent_sessions=s.get("subagent_sessions", 0),
                agentic=agentic,
                confidence=s.get("confidence"),
                answer_tokens=s.get("answer_tokens", 0),
                explanation_tokens=s.get("explanation_tokens", 0),
            )
        )
    return result


# ── Built-in Story Catalog ─────────────────────────────────────


def task_manager_story() -> StoryConfig:
    """A 5-session story building a task management API.

    Session 1: Core models + CRUD (greenfield)
    Session 2: JWT authentication (feature addition)
    Session 3: Async notification worker (integration)
    Session 4: Repository pattern refactor (refactor)
    Session 5: Rate limiting + pagination (cross-cutting)
    """
    return StoryConfig(
        name="task_manager_api",
        description="Build a task management API across 5 sessions",
        language="python",
        constraints=[
            "All endpoints return JSON",
            "Use SQLite for persistence",
            "Include error handling for all endpoints",
        ],
        sessions=[
            SessionSpec(
                session_number=1,
                task_type="greenfield",
                description="Core models and CRUD endpoints",
                prompt=(
                    "Create a Flask API for task management with the following requirements:\n\n"
                    "MODELS:\n"
                    "- Task: id (int, auto), title (str), status (str, default 'pending'), "
                    "created_at (datetime)\n\n"
                    "ENDPOINTS:\n"
                    "- POST /tasks — create a task (JSON body: {title: str})\n"
                    "- GET /tasks — list all tasks ordered by created_at desc\n"
                    "- GET /tasks/{id} — get a single task\n"
                    "- PUT /tasks/{id} — update task title and/or status\n\n"
                    "STORAGE:\n"
                    "- Use SQLite. Initialize the schema on startup.\n\n"
                    "ERROR HANDLING:\n"
                    "- Return 400 for missing title on POST\n"
                    "- Return 404 when task not found\n"
                    "- Return proper JSON error messages\n\n"
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=2,
                task_type="feature_addition",
                description="JWT authentication middleware",
                prompt=(
                    "Add JWT authentication to the existing task management API.\n\n"
                    "NEW MODEL:\n"
                    "- User: id (int, auto), username (str, unique), password_hash (str)\n\n"
                    "NEW ENDPOINTS:\n"
                    "- POST /auth/register — create user (JSON: {username, password})\n"
                    "- POST /auth/login — return JWT token (JSON: {username, password})\n\n"
                    "PROTECT EXISTING ENDPOINTS:\n"
                    "- All /tasks/* endpoints require a valid JWT in Authorization header\n"
                    "- Return 401 for missing/invalid tokens\n"
                    "- Each user sees only their own tasks\n\n"
                    "SECURITY:\n"
                    "- Hash passwords with bcrypt or werkzeug\n"
                    "- Add a Task.owner_id field to associate tasks with users\n"
                    "- Add a migration step that doesn't break existing data\n\n"
                    "Write ALL code. Update existing tests. Add auth tests. "
                    "Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=3,
                task_type="integration",
                description="Async notification worker integration",
                prompt=(
                    "Add an async email notification system to the task management API.\n\n"
                    "REQUIREMENT:\n"
                    "When a task's status changes to 'completed', send a notification email "
                    "to the task owner asynchronously (do not block the API response).\n\n"
                    "IMPLEMENTATION:\n"
                    "- Use Celery with Redis as the message broker\n"
                    "- Create a Celery task: send_notification_email(user_email, task_title)\n"
                    "- Trigger the Celery task from the PUT /tasks/{id} endpoint when "
                    "status changes to 'completed'\n"
                    "- The email sending can be a mock (print to console or log)\n"
                    "- Add a celery_config.py with broker URL, result backend, task routes\n\n"
                    "DO NOT BREAK existing endpoints or auth. Keep all existing tests passing.\n"
                    "Add tests for the notification trigger logic.\n\n"
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=4,
                task_type="refactor",
                description="Repository pattern refactor",
                prompt=(
                    "Refactor the data access layer to use the Repository pattern.\n\n"
                    "REQUIREMENT:\n"
                    "Extract all database operations into repository classes. "
                    "The API routes should NOT directly access SQLite.\n\n"
                    "IMPLEMENTATION:\n"
                    "- Create a BaseRepository abstract class with common CRUD operations\n"
                    "- Create TaskRepository that extends BaseRepository\n"
                    "- Create UserRepository that extends BaseRepository\n"
                    "- Move ALL SQL queries out of route handlers into repositories\n"
                    "- Route handlers should call repository methods, not raw SQL\n"
                    "- The external API behavior MUST remain identical (same responses)\n"
                    "- All existing tests MUST pass without modification\n\n"
                    "This is a pure refactor. Do NOT add new features or change API behavior.\n\n"
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=5,
                task_type="cross_cutting",
                description="Rate limiting and cursor-based pagination",
                prompt=(
                    "Add rate limiting and pagination to the task management API.\n\n"
                    "RATE LIMITING:\n"
                    "- Limit each authenticated user to 100 requests per minute\n"
                    "- Use Flask-Limiter with Redis as the storage backend\n"
                    "- Return 429 with Retry-After header when limit exceeded\n"
                    "- Apply rate limiting to ALL endpoints including auth\n\n"
                    "PAGINATION:\n"
                    "- Replace GET /tasks (return all) with cursor-based pagination\n"
                    "- Query params: ?cursor=<id>&limit=<n> (default limit=20, max=100)\n"
                    "- Response format: {data: [...], next_cursor: str|null, total: int}\n"
                    "- Cursor is the id of the last item in the current page\n"
                    "- GET /tasks without cursor returns the first page\n\n"
                    "DO NOT BREAK existing functionality. Keep auth and repository pattern intact.\n"
                    "Write pytest tests for rate limiting and pagination.\n"
                    "Focus on a working implementation — skip optimization."
                ),
            ),
        ],
    )


def static_site_gen_story() -> StoryConfig:
    """A 5-session story building a static site generator in TypeScript.

    Session 1: Markdown parsing + HTML rendering (greenfield)
    Session 2: Template engine + layout support (feature addition)
    Session 3: Live reload dev server (integration)
    Session 4: Plugin system refactor (refactor)
    Session 5: Incremental builds + caching (cross-cutting)
    """
    return StoryConfig(
        name="static_site_gen",
        description="Build a static site generator CLI across 5 sessions",
        language="typescript",
        constraints=[
            "All output goes to ./dist by default",
            "CLI interface via commander or yargs",
            "TypeScript with strict mode enabled",
        ],
        sessions=[
            SessionSpec(
                session_number=1,
                task_type="greenfield",
                description="Markdown parsing and HTML rendering",
                prompt=(
                    "Build a static site generator CLI in TypeScript.\n\n"
                    "CORE FEATURES:\n"
                    "- Read Markdown files from a content directory (default: ./content)\n"
                    "- Parse Markdown to HTML with frontmatter support (title, date, tags)\n"
                    "- Generate an index.html listing all pages\n"
                    "- Each page gets its own HTML file in ./dist\n\n"
                    "CLI:\n"
                    "- npx ssg build — generate the site\n"
                    "- Options: --content <dir>, --output <dir>\n\n"
                    "TECH:\n"
                    "- TypeScript with strict mode\n"
                    "- Use marked or markdown-it for parsing\n"
                    "- Use gray-matter for frontmatter\n"
                    "- Tests with jest\n\n"
                    "Write ALL code. Run jest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=2,
                task_type="feature_addition",
                description="Template engine and layout support",
                prompt=(
                    "Add template engine and layout support to the static site generator.\n\n"
                    "TEMPLATES:\n"
                    "- Support Handlebars (.hbs) or EJS templates\n"
                    "- Each page can specify a template in its frontmatter\n"
                    "- Default template if none specified\n"
                    "- Layout templates with {{{body}}} placeholder for page content\n"
                    "- Support partials/includes (header, footer, nav)\n\n"
                    "DIRECTORY STRUCTURE:\n"
                    "- ./templates/ — template files\n"
                    "- ./templates/layouts/ — layout templates\n"
                    "- ./templates/partials/ — reusable partials\n\n"
                    "EXISTING FUNCTIONALITY must continue working.\n"
                    "Update tests. Add template-specific tests.\n\n"
                    "Write ALL code. Run jest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=3,
                task_type="integration",
                description="Live reload development server",
                prompt=(
                    "Add a live-reload development server to the SSG.\n\n"
                    "DEV SERVER:\n"
                    "- npx ssg serve — start dev server on localhost:3000\n"
                    "- Watch content/ and templates/ directories for changes\n"
                    "- Rebuild on file change\n"
                    "- Inject a WebSocket script into served pages for live reload\n"
                    "- Reload browser automatically when rebuild completes\n\n"
                    "TECH:\n"
                    "- Use chokidar for file watching\n"
                    "- Use ws or socket.io for WebSocket\n"
                    "- Serve from ./dist directory\n"
                    "- Add --port option to serve command\n\n"
                    "DO NOT BREAK the build command. Keep all existing tests passing.\n\n"
                    "Write ALL code. Run jest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=4,
                task_type="refactor",
                description="Plugin system architecture",
                prompt=(
                    "Refactor the SSG to use a plugin system for extensibility.\n\n"
                    "PLUGIN SYSTEM:\n"
                    "- Define a Plugin interface with lifecycle hooks:\n"
                    "  - onStart(), beforeBuild(), afterBuild(), onFile(page), onEnd()\n"
                    "- Plugins are TypeScript modules in ./plugins/\n"
                    "- Load plugins from a config file (ssg.config.ts)\n"
                    "- Plugin pipeline: each hook runs all plugin hooks in order\n"
                    "- Existing features (markdown, templates, live reload) become built-in plugins\n\n"
                    "REFACTOR:\n"
                    "- Extract markdown parsing into MarkdownPlugin\n"
                    "- Extract template rendering into TemplatePlugin\n"
                    "- Extract dev server into DevServerPlugin\n"
                    "- The core SSG engine orchestrates the plugin pipeline\n"
                    "- External API behavior MUST remain identical\n\n"
                    "Write ALL code. Run jest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=5,
                task_type="cross_cutting",
                description="Incremental builds and content caching",
                prompt=(
                    "Add incremental builds and caching to the SSG.\n\n"
                    "INCREMENTAL BUILDS:\n"
                    "- npx ssg build --incremental — only rebuild changed pages\n"
                    "- Track file hashes in a .ssg-cache.json manifest\n"
                    "- Skip rebuild of pages whose source and template haven't changed\n"
                    "- Clean build if cache is missing or --clean flag is passed\n\n"
                    "CACHING:\n"
                    "- Cache rendered HTML in memory or on disk\n"
                    "- Cache parsed frontmatter\n"
                    "- Invalidate cache entries when source or template changes\n"
                    "- Report build stats: pages built, pages skipped, time saved\n\n"
                    "DO NOT BREAK existing functionality. Keep plugin architecture intact.\n"
                    "Write jest tests for incremental build correctness. Focus on working implementation."
                    "Write ALL code. Run jest. Fix failures until all tests pass."
                ),
            ),
        ],
    )


def notification_service_story() -> StoryConfig:
    """A 5-session story building a real-time notification delivery service.

    Session 1: Core WebSocket server + client (greenfield)
    Session 2: Channel subscriptions + message routing (feature addition)
    Session 3: Redis pub/sub integration (integration)
    Session 4: Extract protocol layer (refactor)
    Session 5: Rate limiting + message persistence (cross-cutting)
    """
    return StoryConfig(
        name="notification_service",
        description="Build a real-time notification delivery service across 5 sessions",
        language="python",
        constraints=[
            "All communication via WebSocket",
            "Use Redis for pub/sub and rate limiting",
            "SQLite for message persistence",
        ],
        sessions=[
            SessionSpec(
                session_number=1,
                task_type="greenfield",
                description="Core WebSocket server with broadcast",
                prompt=(
                    "Build a WebSocket-based notification server in Python.\n\n"
                    "CORE FEATURES:\n"
                    "- Accept WebSocket connections from clients\n"
                    "- Assign each client a unique ID on connect\n"
                    "- Broadcast a message to ALL connected clients\n"
                    "- Handle client disconnect (clean removal)\n"
                    "- REST endpoint: GET /health — returns connected client count\n\n"
                    "MESSAGE FORMAT:\n"
                    "- All messages are JSON: {type: str, payload: dict, timestamp: str}\n"
                    "- Supported types: 'broadcast', 'direct', 'system'\n\n"
                    "TECH:\n"
                    "- Use websockets library (not Flask-SocketIO)\n"
                    "- Async with asyncio\n"
                    "- Thread-safe client registry\n"
                    "- Tests with pytest + pytest-asyncio\n\n"
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=2,
                task_type="feature_addition",
                description="Channel subscriptions and targeted routing",
                prompt=(
                    "Add channel-based subscriptions to the notification server.\n\n"
                    "CHANNELS:\n"
                    "- Clients subscribe to named channels (e.g. 'alerts', 'system', 'chat')\n"
                    "- Messages are delivered ONLY to clients subscribed to that channel\n"
                    "- Clients can subscribe/unsubscribe dynamically\n"
                    "- A client can be subscribed to multiple channels\n\n"
                    "MESSAGE TYPES:\n"
                    "- Add 'subscribe' and 'unsubscribe' message types\n"
                    "- Messages with a 'channel' field route only to that channel's subscribers\n"
                    "- Messages without a channel still broadcast to all\n\n"
                    "REST ENDPOINTS:\n"
                    "- GET /channels — list active channels and subscriber counts\n"
                    "- GET /channels/{name}/subscribers — list subscriber IDs\n\n"
                    "DO NOT BREAK existing functionality. All tests must pass.\n\n"
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=3,
                task_type="integration",
                description="Redis pub/sub message backbone",
                prompt=(
                    "Integrate Redis pub/sub as the message backbone.\n\n"
                    "REDIS INTEGRATION:\n"
                    "- Use Redis pub/sub channels for message distribution\n"
                    "- Server publishes to Redis channel; workers subscribe and deliver\n"
                    "- Multiple server instances can share the same Redis backbone\n"
                    "- Client connection state stored in Redis (survives server restart)\n\n"
                    "PERSISTENCE:\n"
                    "- Store all messages in SQLite for history\n"
                    "- REST endpoint: GET /messages?limit=50&offset=0\n"
                    "- Messages table: id, channel, type, payload, timestamp\n\n"
                    "CONFIG:\n"
                    "- REDIS_URL env var for broker connection\n"
                    "- DATABASE_URL env var for SQLite path\n\n"
                    "DO NOT BREAK existing behavior. All tests must pass.\n"
                    "Add integration tests for Redis pub/sub and message persistence.\n\n"
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=4,
                task_type="refactor",
                description="Extract protocol layer into pluggable transports",
                prompt=(
                    "Refactor the notification server to use a pluggable transport layer.\n\n"
                    "REQUIREMENT:\n"
                    "Extract the WebSocket transport behind a Transport interface so\n"
                    "different transport mechanisms (SSE, polling, raw TCP) can be added\n"
                    "without modifying the core notification logic.\n\n"
                    "IMPLEMENTATION:\n"
                    "- Create BaseTransport abstract class:\n"
                    "  - on_connect(), on_disconnect(), send_message(), broadcast()\n"
                    "- Move WebSocket logic into WebSocketTransport\n"
                    "- The core NotificationServer should work with any Transport\n"
                    "- Transport is selected by config (TRANSPORT env var)\n"
                    "- WebSocketTransport is the default\n\n"
                    "API MUST remain identical. All existing tests must pass without\n"
                    "modification. Client behavior must not change.\n\n"
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
            SessionSpec(
                session_number=5,
                task_type="cross_cutting",
                description="Rate limiting + persistent message history",
                prompt=(
                    "Add rate limiting and persistent message history.\n\n"
                    "RATE LIMITING:\n"
                    "- Limit each client to 100 messages per minute\n"
                    "- Limits enforced per-client-ID using Redis counters\n"
                    "- Return error message on rate limit exceeded (no drop)\n"
                    "- Configurable via RATE_LIMIT env var\n\n"
                    "MESSAGE HISTORY:\n"
                    "- REST endpoint: GET /history?channel=X&since=ISO_TIMESTAMP&limit=50\n"
                    "- Returns messages for a specific channel/time range\n"
                    "- Paginated with has_more boolean\n"
                    "- Messages returned in chronological order\n\n"
                    "SYSTEM MESSAGE EXPIRY:\n"
                    "- Messages older than 7 days are automatically cleaned up\n"
                    "- Cleanup runs as a background task on server startup\n"
                    "- Configurable via MESSAGE_TTL_DAYS env var\n\n"
                    "DO NOT BREAK existing functionality. Keep transport layer and pub/sub intact.\n"
                    "Write pytest tests for rate limiting and history queries. Focus on working implementation."
                    "Write ALL code. Run pytest. Fix failures until all tests pass."
                ),
            ),
        ],
    )


BUILTIN_STORIES: dict[str, StoryConfig] = {
    "task_manager_api": task_manager_story(),
    "static_site_gen": static_site_gen_story(),
    "notification_service": notification_service_story(),
}
