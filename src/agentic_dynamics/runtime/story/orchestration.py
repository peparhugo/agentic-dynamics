"""Story orchestration — the run loop and per-session execution.

Extracted from ``runtime/story.py`` (refactor-repair Debt-1). ``run_story`` clones a codebase
into a worktree, applies the condition, runs each session, and independently verifies the tests;
``_run_session`` runs one agentic session and commits it.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from agentic_dynamics.adapters.backends import run_agentic
from agentic_dynamics.measurement.mutation import MutationArtifact, apply_mutation
from agentic_dynamics.runtime.story.conditions import (
    CONDITION_STRENGTH,
    PerturbationCondition,
    condition_to_mutations,
)
from agentic_dynamics.runtime.story.models import (
    SessionResult,
    SessionSpec,
    StoryConfig,
    StoryResult,
    session_token_split,
)
from agentic_dynamics.runtime.story.persistence import (
    _detect_or_use,
    _estimate_session_cost,
    _estimate_subagent_cost,
    _extract_session_id_from_stdout,
    _git,
    _list_tracked_files,
    _read_session_id,
    _sum_billed_tokens_from_jsonl,
)
from agentic_dynamics.runtime.test_runner import run_suite, suite_succeeded


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

    # BAD_SEED condition: use the pre-generated bad variant on disk, UNLESS the caller
    # supplies an explicit mutation artifact (the documented override seam — "overrides
    # condition"). When ``mutation`` is provided it REPLACES the condition's own
    # degradation entirely: the good codebase is used as the seed and the artifact is
    # applied on top (its strength becomes ``perturbation_strength``). Previously the
    # parameter was only read as a gate (`if mutation is None and ...`) and the supplied
    # artifact was never applied to the worktree — the docstring promised an override that
    # the implementation dropped. See docs/designs/current/cap_grit_grid_runplan.md finding
    # F2 (E4 run plan, x1).
    actual_codebase_path = codebase_path
    if condition == PerturbationCondition.BAD_SEED and mutation is None:
        bad_path = codebase_path_obj.parent / "bad"
        if bad_path.exists() and any(bad_path.iterdir()):
            actual_codebase_path = str(bad_path)

    story_specs = [s.prompt for s in story.sessions]
    codebase_mutation = None
    spec_mutations = {}
    if mutation is not None:
        codebase_mutation = mutation
    elif condition != PerturbationCondition.CLEAN:
        codebase_mutation, spec_mutations = condition_to_mutations(
            condition,
            codebase_path_obj,
            story_specs,
        )

    # The strength axis follows the effective degradation: an explicit mutation's own
    # strength, else the condition's canonical value (0.0 for CLEAN, CONDITION_STRENGTH
    # for every degrading condition). Previously always CONDITION_STRENGTH for any
    # non-CLEAN condition even when an explicit artifact carried a different strength
    # (runplan finding F3).
    perturbation_strength = (
        mutation.strength
        if mutation is not None
        else (0.0 if condition == PerturbationCondition.CLEAN else CONDITION_STRENGTH)
    )

    result = StoryResult(
        story_name=story.name,
        story_id=story_id,
        codebase_path=codebase_path,
        language=story.language,
        model=model,
        mutation_id=mutation.mutation_id if mutation is not None else "",
        perturbation_condition=condition.value,
        perturbation_strength=perturbation_strength,
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
        tokens=session_token_split(agentic),
    )

