"""sync_data.py — Normalize all story results into Parquet for clean querying.

Reads every stories/*.json, flattens sessions into one row per session,
writes two tables to experiments/data/:

  sessions.parquet  — one row per session (cost, tokens, cache, correctness, model)
  stories.parquet   — one row per story cell (aggregated totals)

Usage:
  python3 scripts/sync_data.py          # sync all results
  python3 scripts/sync_data.py --check  # verify parquet vs source
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

RESULTS_DIR = Path(__file__).resolve().parent.parent / "experiments" / "results" / "stories"
DATA_DIR = Path(__file__).resolve().parent.parent / "experiments" / "data"

SESSION_SCHEMA = pa.schema([
    pa.field("session_id", pa.string()),
    pa.field("story_name", pa.string()),
    pa.field("tier", pa.string()),
    pa.field("quality", pa.string()),
    pa.field("condition", pa.string()),
    pa.field("session_number", pa.int32()),
    pa.field("task_type", pa.string()),
    pa.field("model", pa.string()),
    pa.field("prompt_tokens", pa.int64()),
    pa.field("completion_tokens", pa.int64()),
    pa.field("reasoning_tokens", pa.int64()),
    pa.field("total_tokens", pa.int64()),
    pa.field("cache_read_tokens", pa.int64()),
    pa.field("cache_write_tokens", pa.int64()),
    pa.field("context_tokens", pa.int64()),
    pa.field("cache_hit_rate", pa.float64()),
    pa.field("cost_usd", pa.float64()),
    pa.field("duration_s", pa.float64()),
    pa.field("exit_code", pa.int32()),
    pa.field("tool_calls", pa.int32()),
    pa.field("depth", pa.int32()),
    pa.field("retries", pa.int32()),
    pa.field("tests_passed", pa.int32()),
    pa.field("tests_total", pa.int32()),
    pa.field("files_changed", pa.int32()),
    pa.field("error", pa.string()),
    pa.field("continuation_used", pa.bool_()),
    pa.field("worktree", pa.string()),
    pa.field("started_at", pa.string()),
    pa.field("test_count", pa.int32()),
    pa.field("test_lines", pa.int32()),
    pa.field("code_lines", pa.int32()),
])

STORY_SCHEMA = pa.schema([
    pa.field("story_name", pa.string()),
    pa.field("tier", pa.string()),
    pa.field("quality", pa.string()),
    pa.field("condition", pa.string()),
    pa.field("model", pa.string()),
    pa.field("session_count", pa.int32()),
    pa.field("total_tokens", pa.int64()),
    pa.field("total_cache_reads", pa.int64()),
    pa.field("total_cache_writes", pa.int64()),
    pa.field("total_context_tokens", pa.int64()),
    pa.field("cache_hit_rate", pa.float64()),
    pa.field("total_cost", pa.float64()),
    pa.field("total_duration", pa.float64()),
    pa.field("all_successful", pa.bool_()),
    pa.field("cascade_recovery", pa.bool_()),
    pa.field("worktree", pa.string()),
    pa.field("test_count", pa.int32()),
    pa.field("test_lines", pa.int32()),
    pa.field("code_lines", pa.int32()),
    pa.field("test_code_ratio", pa.float64()),
])


def _extract_tier_quality(codebase_path: str) -> tuple[str, str]:
    parts = Path(codebase_path).parts
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return "", ""


def _extract_condition(d: dict, filename: str) -> str:
    cond = d.get("perturbation_condition", "")
    if cond:
        return cond
    for candidate in ["bad_seed", "early_degrade", "clean"]:
        if candidate in filename:
            return candidate
    return ""


def sync() -> dict[str, int]:
    """Sync all story results to parquet. Returns row counts."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    session_rows: list[dict[str, Any]] = []
    story_rows: list[dict[str, Any]] = []

    for f in sorted(RESULTS_DIR.glob("*.json")):
        if "dvs" in f.name or "log" in f.name:
            continue

        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        story_name = d.get("story_name", "")
        model = d.get("model", "")
        tier, quality = _extract_tier_quality(d.get("codebase_path", ""))
        condition = _extract_condition(d, f.name)
        summary = d.get("summary", {})
        worktree = d.get("worktree", "")

        story_rows.append({
            "story_name": story_name,
            "tier": tier,
            "quality": quality,
            "condition": condition,
            "model": model,
            "session_count": summary.get("session_count", len(d.get("sessions", []))),
            "total_tokens": summary.get("total_tokens", 0),
            "total_cache_reads": summary.get("total_cache_reads", 0),
            "total_cache_writes": summary.get("total_cache_writes", 0),
            "total_context_tokens": summary.get("total_context_tokens", 0),
            "cache_hit_rate": summary.get("cache_hit_rate", 0.0),
            "total_cost": summary.get("total_cost", 0.0),
            "total_duration": summary.get("total_duration", 0.0),
            "all_successful": summary.get("all_successful", False),
            "cascade_recovery": summary.get("cascade_recovery", False),
            "worktree": worktree,
            "test_count": summary.get("test_count", 0) or 0,
            "test_lines": summary.get("test_lines", 0) or 0,
            "code_lines": summary.get("code_lines", 0) or 0,
            "test_code_ratio": summary.get("test_code_ratio", 0.0) or 0.0,
        })

        for s in d.get("sessions", []):
            a = s.get("agentic", {})
            session_rows.append({
                "session_id": f"{Path(f.name).stem}_{s.get('session_number', 0)}",
                "story_name": story_name,
                "tier": tier,
                "quality": quality,
                "condition": condition,
                "session_number": s.get("session_number", 0),
                "task_type": s.get("task_type", ""),
                "model": model,
                "prompt_tokens": a.get("prompt_tokens", 0) or 0,
                "completion_tokens": a.get("completion_tokens", 0) or 0,
                "reasoning_tokens": a.get("reasoning_tokens", 0) or 0,
                "total_tokens": a.get("total_tokens", 0) or 0,
                "cache_read_tokens": a.get("cache_read_tokens", 0) or 0,
                "cache_write_tokens": a.get("cache_write_tokens", 0) or 0,
                "context_tokens": a.get("context_tokens", 0) or 0,
                "cache_hit_rate": a.get("cache_hit_rate", 0.0) or 0.0,
                "cost_usd": s.get("cost_usd", 0.0),
                "duration_s": s.get("duration_s", 0.0),
                "exit_code": s.get("exit_code", 0),
                "tool_calls": a.get("tool_calls", 0) or 0,
                "depth": a.get("depth", 0) or 0,
                "retries": a.get("retries", 0) or 0,
                "tests_passed": a.get("tests_passed", 0) or 0,
                "tests_total": a.get("tests_total", 0) or 0,
                "files_changed": s.get("files_changed", 0),
                "error": s.get("error", ""),
                "continuation_used": s.get("continuation_used", False),
                "worktree": worktree,
                "started_at": d.get("started_at", ""),
                "test_count": s.get("test_count", 0) or 0,
                "test_lines": s.get("test_lines", 0) or 0,
                "code_lines": s.get("code_lines", 0) or 0,
            })

    if session_rows:
        table = pa.Table.from_pylist(session_rows, schema=SESSION_SCHEMA)
        pq.write_table(table, DATA_DIR / "sessions.parquet", compression="zstd")

    if story_rows:
        table = pa.Table.from_pylist(story_rows, schema=STORY_SCHEMA)
        pq.write_table(table, DATA_DIR / "stories.parquet", compression="zstd")

    return {"sessions": len(session_rows), "stories": len(story_rows)}


def query(parquet_path: Path, sql: str) -> str:
    """Run a duckdb query against a parquet file."""
    conn = duckdb.connect()
    result = conn.execute(f"SELECT * FROM read_parquet('{parquet_path}') {sql}").fetchdf()
    conn.close()
    return result.to_string()


def main() -> None:
    import sys

    if "--check" in sys.argv:
        if not (DATA_DIR / "sessions.parquet").exists():
            print("No parquet files. Run without --check first.")
            return
        conn = duckdb.connect()
        for table in ["sessions", "stories"]:
            path = DATA_DIR / f"{table}.parquet"
            count = conn.execute(f"SELECT count(*) FROM read_parquet('{path}')").fetchone()[0]
            print(f"  {table}.parquet: {count:,} rows")
        conn.close()
        return

    if "--query" in sys.argv and len(sys.argv) > 2:
        sql = sys.argv[-1]
        for table in ["sessions", "stories"]:
            path = DATA_DIR / f"{table}.parquet"
            if path.exists():
                print(f"\n=== {table} ===")
                print(query(path, sql))
        return

    counts = sync()
    print(f"Synced: {counts['sessions']} sessions, {counts['stories']} stories")
    print(f"Output: {DATA_DIR}/sessions.parquet, {DATA_DIR}/stories.parquet")


if __name__ == "__main__":
    main()
