"""backfill_costs.py — Fix story result costs + test metrics from opencode DB + worktrees.

Story result JSONs have buggy costs (old parser) and missing test metrics.
The opencode DB has correct per-session costs. Worktrees have test/line counts.

Updates story JSONs in-place (with backup).

Usage:
  python3 scripts/backfill_costs.py --dry-run  # preview changes
  python3 scripts/backfill_costs.py            # apply fixes
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from instrument.opencode import AgenticResult, _parse_session_output
from instrument.story import _count_tests
from instrument.efficiency import compute_cost_estimate

RESULTS_DIR = ROOT / "experiments" / "results" / "stories"
BACKUP_DIR = RESULTS_DIR / ".backfill_backup"
DB_PATH = Path.home() / ".local" / "share" / "opencode" / "opencode.db"


def _get_db_sessions(conn: sqlite3.Connection, worktree: str) -> list[dict]:
    """Get all session costs from the DB for a worktree."""
    rows = conn.execute(
        "SELECT id, title, cost, tokens_input, tokens_output, "
        "tokens_reasoning, tokens_cache_read, tokens_cache_write "
        "FROM session WHERE directory = ? ORDER BY time_updated",
        (worktree,),
    ).fetchall()
    return [
        {
            "id": r[0],
            "title": r[1] or "",
            "cost": float(r[2] or 0),
            "tokens_input": r[3] or 0,
            "tokens_output": r[4] or 0,
            "tokens_reasoning": r[5] or 0,
            "tokens_cache_read": r[6] or 0,
            "tokens_cache_write": r[7] or 0,
        }
        for r in rows
    ]


def _match_db_to_session(
    db_sessions: list[dict], session_number: int
) -> dict | None:
    """Match a DB session to a story session by number in title."""
    for s in db_sessions:
        if f"Session {session_number}:" in s["title"]:
            return s
    return None


def backfill(dry_run: bool = False) -> dict:
    """Fix all story result costs from DB + session.jsonl re-parse."""
    conn = sqlite3.connect(str(DB_PATH))
    updated = 0
    skipped = 0
    total_cost_before = 0.0
    total_cost_after = 0.0

    if not dry_run:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(
        f for f in RESULTS_DIR.glob("*.json")
        if "dvs" not in f.name and "log" not in f.name
    )

    for f in files:
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            skipped += 1
            continue

        worktree = d.get("worktree", "")
        if not worktree:
            skipped += 1
            continue

        db_sessions = _get_db_sessions(conn, worktree)
        if not db_sessions:
            skipped += 1
            continue

        # Re-parse the last session's JSONL for token/cache detail
        jsonl_path = Path(worktree) / ".instrument" / "session.jsonl"
        last_agentic: AgenticResult | None = None
        if jsonl_path.exists():
            last_agentic = AgenticResult()
            _parse_session_output(jsonl_path.read_text(), last_agentic)

        old_summary_cost = d.get("summary", {}).get("total_cost", 0)

        # Count story sessions (exclude @explore subagent sessions)
        story_sessions = [
            s for s in d.get("sessions", [])
        ]
        main_db_sessions = [
            s for s in db_sessions
            if "Session" in s["title"] and "@explore" not in s["title"].lower()
        ]

        if not story_sessions:
            skipped += 1
            continue

        # Update each session from DB data
        model = d.get("model", "")
        provider, _, model_id = model.partition("/")

        for ses in story_sessions:
            sn = ses.get("session_number", 0)
            db_match = _match_db_to_session(db_sessions, sn)
            
            if db_match:
                db_cost = float(db_match["cost"] or 0)
                if db_cost > 0:
                    ses["cost_usd"] = round(db_cost, 8)
                else:
                    # DB recorded zero cost (e.g. gpt-5.6-sol/terra unpriced at
                    # run time) — estimate from token counts at provider rates.
                    est = compute_cost_estimate(
                        prompt_tokens=db_match["tokens_input"],
                        completion_tokens=db_match["tokens_output"],
                        reasoning_tokens=db_match["tokens_reasoning"],
                        cache_read_tokens=db_match["tokens_cache_read"],
                        cache_write_tokens=db_match["tokens_cache_write"],
                        context_tokens=(db_match["tokens_input"]
                                        + db_match["tokens_cache_read"]
                                        + db_match["tokens_cache_write"]),
                        provider=provider, model=model_id,
                    )
                    ses["cost_usd"] = est["total_cost_usd"]

                # If this is the last session AND we parsed its JSONL, use detail
                if sn == story_sessions[-1].get("session_number") and last_agentic:
                    a = ses.get("agentic", {})
                    if a:
                        a["prompt_tokens"] = last_agentic.prompt_tokens
                        a["completion_tokens"] = last_agentic.completion_tokens
                        a["reasoning_tokens"] = last_agentic.reasoning_tokens
                        a["total_tokens"] = last_agentic.total_tokens
                        a["cache_read_tokens"] = last_agentic.cache_read_tokens
                        a["cache_write_tokens"] = last_agentic.cache_write_tokens
                        a["context_tokens"] = last_agentic.context_tokens
                        a["cache_hit_rate"] = round(last_agentic.cache_hit_rate, 3)
                        a["estimated_cost_usd"] = last_agentic.estimated_cost_usd
                        ses["agentic"] = a
                else:
                    # Use DB data for other sessions
                    a = ses.get("agentic", {})
                    if a and isinstance(a, dict) and not a.get("total_tokens"):
                        a["prompt_tokens"] = db_match["tokens_input"]
                        a["completion_tokens"] = db_match["tokens_output"]
                        a["reasoning_tokens"] = db_match["tokens_reasoning"]
                        a["total_tokens"] = (
                            db_match["tokens_input"]
                            + db_match["tokens_output"]
                            + db_match["tokens_reasoning"]
                        )
                        a["cache_read_tokens"] = db_match["tokens_cache_read"]
                        a["cache_write_tokens"] = db_match["tokens_cache_write"]
                        ses["agentic"] = a

        # Count test/line metrics from worktree (represents final accumulated state)
        test_count, test_lines, code_lines = 0, 0, 0
        if Path(worktree).exists():
            test_count, test_lines, code_lines = _count_tests(Path(worktree))
            # Store on the last session
            if story_sessions:
                story_sessions[-1]["test_count"] = test_count
                story_sessions[-1]["test_lines"] = test_lines
                story_sessions[-1]["code_lines"] = code_lines

        # Recompute summary
        all_sessions = d.get("sessions", [])
        total_cost = sum(s.get("cost_usd", 0) for s in all_sessions)
        total_tokens = sum(
            (s.get("agentic", {}).get("total_tokens", 0) or 0)
            for s in all_sessions
            if isinstance(s.get("agentic"), dict)
        )
        total_cache_reads = sum(
            (s.get("agentic", {}).get("cache_read_tokens", 0) or 0)
            for s in all_sessions
            if isinstance(s.get("agentic"), dict)
        )
        total_cache_writes = sum(
            (s.get("agentic", {}).get("cache_write_tokens", 0) or 0)
            for s in all_sessions
            if isinstance(s.get("agentic"), dict)
        )
        total_context = total_tokens + total_cache_reads
        cache_hit_rate = (
            total_cache_reads / total_context if total_context > 0 else 0.0
        )

        total_cost_before += d.get("summary", {}).get("total_cost", 0)
        total_cost_after += total_cost

        d["summary"] = {
            **d.get("summary", {}),
            "total_cost": round(total_cost, 8),
            "total_tokens": total_tokens,
            "total_cache_reads": total_cache_reads,
            "total_cache_writes": total_cache_writes,
            "total_context_tokens": total_context,
            "cache_hit_rate": round(cache_hit_rate, 3),
            "test_count": test_count,
            "test_lines": test_lines,
            "code_lines": code_lines,
            "test_code_ratio": round(test_lines / code_lines, 3) if code_lines > 0 else 0.0,
        }

        if dry_run:
            delta = total_cost - old_summary_cost
            if abs(delta) > 0.0001:
                print(f"  {f.name[:55]}: ${old_summary_cost:.6f} → ${total_cost:.6f} (Δ{delta:+.6f})")
                updated += 1
        else:
            backup_path = BACKUP_DIR / f.name
            shutil.copy2(f, backup_path)
            f.write_text(json.dumps(d, indent=2, default=str))
            updated += 1

    conn.close()

    return {
        "updated": updated,
        "skipped": skipped,
        "total_before": total_cost_before,
        "total_after": total_cost_after,
    }


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    print(f"{'DRY RUN: ' if dry_run else ''}Fixing costs from opencode DB...")
    result = backfill(dry_run=dry_run)
    print(f"\nDone: {result['updated']} updated, {result['skipped']} skipped")
    if result["updated"]:
        print(f"  Cost before: ${result['total_before']:.4f}")
        print(f"  Cost after:  ${result['total_after']:.4f}")
        print(f"  Delta:       ${result['total_after'] - result['total_before']:+.4f}")
    if not dry_run:
        print(f"  Backups: {BACKUP_DIR}")


if __name__ == "__main__":
    main()
