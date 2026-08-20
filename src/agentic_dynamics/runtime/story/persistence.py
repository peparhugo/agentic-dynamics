"""Story persistence + I/O helpers — save/load, git, opencode DB cost accounting.

Extracted from ``runtime/story.py`` (refactor-repair Debt-1). ``save_story_result`` /
``load_story_result`` are the durable JSON round-trip; the remaining helpers read the opencode
SQLite DB (cost/session ids), run git, and detect language.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from agentic_dynamics.adapters.opencode import AgenticResult
from agentic_dynamics.core.language import detect_language
from agentic_dynamics.runtime.story.models import SessionResult, StoryResult


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

