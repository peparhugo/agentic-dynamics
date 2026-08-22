"""sync_data.py — Normalize canonical story results into Parquet for clean querying.

Reads the **registry-selected** story payloads (never a raw ``stories/*.json`` glob) via
``agentic_dynamics.reporting.canonical_corpus``, flattens sessions into one row per
session, writes two tables to experiments/data/:

  sessions.parquet  — one row per session (cost, tokens, cache, correctness, model)
  stories.parquet   — one row per story cell (aggregated totals)

The condition a cell carries is ``_canonical_condition`` — the resolver's no-op relabel
(``early_degrade``/``bad_seed`` no-ops and absent labels count as ``clean``), so the
parquet agrees with the canonical lab corpus instead of contradicting it.

Usage:
  python3 scripts/sync_data.py          # sync all canonical results
  python3 scripts/sync_data.py --check  # verify parquet vs source
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.reporting.canonical_corpus import load_canonical_tables  # noqa: E402
from agentic_dynamics.reporting.measurement_coverage import cost_captured  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "experiments" / "data"

#: The source-identity sidecar written alongside the parquet — records WHICH canonical
#: source produced the tables, so ``--check`` can prove the parquet is current without
#: re-deriving every row (public-truth review "smaller": a real parity check, not a row
#: count that a stale file would also pass).
SYNC_IDENTITY_PATH = DATA_DIR / "sync_identity.json"

SESSION_SCHEMA = pa.schema(
    [
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
    ]
)

STORY_SCHEMA = pa.schema(
    [
        pa.field("story_name", pa.string()),
        pa.field("tier", pa.string()),
        pa.field("quality", pa.string()),
        pa.field("condition", pa.string()),
        pa.field("model", pa.string()),
        pa.field("cell_key", pa.string()),
        pa.field("repetition", pa.int32()),
        pa.field("session_count", pa.int32()),
        pa.field("total_tokens", pa.int64()),
        pa.field("total_cache_reads", pa.int64()),
        pa.field("total_cache_writes", pa.int64()),
        pa.field("total_context_tokens", pa.int64()),
        pa.field("cache_hit_rate", pa.float64()),
        pa.field("total_cost", pa.float64()),
        pa.field("cost_captured", pa.bool_()),
        pa.field("total_duration", pa.float64()),
        pa.field("all_successful", pa.bool_()),
        pa.field("cascade_recovery", pa.bool_()),
        pa.field("worktree", pa.string()),
        pa.field("test_count", pa.int32()),
        pa.field("test_lines", pa.int32()),
        pa.field("code_lines", pa.int32()),
        pa.field("test_code_ratio", pa.float64()),
    ]
)


def _extract_tier_quality(codebase_path: str) -> tuple[str, str]:
    parts = Path(codebase_path).parts
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return "", ""


def _analysis_loc(analysis: list[dict]) -> dict[str, int]:
    """Map story_id -> final lines_of_code from the canonical analysis payloads.

    The summary.code_lines field is populated by _count_tests(worktree), which returns 0
    once the /tmp worktree is cleaned. The analysis payloads persist
    deep.solution.lines_of_code for every story, so it is the reliable fallback. The
    resolver already filtered these to the current story registry, so this map is
    canonical by construction — no raw ``analysis/*.json`` glob.
    """
    loc: dict[str, int] = {}
    for a in analysis:
        sid = str(a.get("_story_id") or a.get("story_id") or "")
        sol = (a.get("deep", {}) or {}).get("solution", {}) or {}
        n = sol.get("lines_of_code", 0)
        if sid and n:
            loc[sid] = int(n)
    return loc


def _build_rows(tables) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Flatten the canonical story payloads into ``(session_rows, story_rows)``.

    Split out of :func:`sync` so ``--check`` can recompute the expected rows (and prove the
    parquet matches the current resolver output) without writing anything.
    """
    stories = tables.stories

    session_rows: list[dict[str, Any]] = []
    story_rows: list[dict[str, Any]] = []

    cell_counts: Counter[str] = Counter()
    analysis_loc = _analysis_loc(tables.analysis)

    for d in stories:
        story_name = d.get("story_name", "")
        model = d.get("model", "")
        tier, quality = _extract_tier_quality(d.get("codebase_path", ""))
        condition = d.get("_canonical_condition") or "clean"
        summary = d.get("summary", {})
        worktree = d.get("worktree", "")
        story_id = d.get("story_id", "")

        # Recover test counts that summary.test_count dropped (worktree cleaned).
        # agentic.tests_total is measured in-session and survives worktree cleanup;
        # use the peak across sessions as the floor for "tests written".
        sessions = d.get("sessions", [])
        agentic_test_floor = max(
            [(s.get("agentic", {}) or {}).get("tests_total", 0) or 0 for s in sessions] + [0]
        )
        recovered_tests = summary.get("test_count", 0) or agentic_test_floor
        recovered_loc = summary.get("code_lines", 0) or analysis_loc.get(story_id, 0)
        # m2 null-not-zero: a cost is *captured* only when it is a finite, positive real
        # number — inferred from the shared primitive, never from ``> 0`` (the review's P1
        # denominator-policy split). The raw ``total_cost`` is kept (None when absent), and
        # ``cost_captured`` flags it explicitly for the parquet reader.
        story_cost = summary.get("total_cost")
        cost_captured_flag = cost_captured(story_cost)

        # Cell identity: story × model × tier × quality × canonical condition.
        # Re-runs of the same cell share cell_key but get an increasing repetition
        # index (0 = first run, 1 = re-run, ...).
        cell_key = f"{story_name}|{model}|{tier}|{quality}|{condition}"
        repetition = cell_counts[cell_key]
        cell_counts[cell_key] += 1

        story_rows.append(
            {
                "story_name": story_name,
                "tier": tier,
                "quality": quality,
                "condition": condition,
                "model": model,
                "cell_key": cell_key,
                "repetition": repetition,
                "session_count": summary.get("session_count", len(d.get("sessions", []))),
                "total_tokens": summary.get("total_tokens", 0),
                "total_cache_reads": summary.get("total_cache_reads", 0),
                "total_cache_writes": summary.get("total_cache_writes", 0),
                "total_context_tokens": summary.get("total_context_tokens", 0),
                "cache_hit_rate": summary.get("cache_hit_rate", 0.0),
                "total_cost": story_cost,
                "cost_captured": cost_captured_flag,
                "total_duration": summary.get("total_duration", 0.0),
                "all_successful": summary.get("all_successful", False),
                "cascade_recovery": summary.get("cascade_recovery", False),
                "worktree": worktree,
                "test_count": recovered_tests,
                "test_lines": summary.get("test_lines", 0) or 0,
                "code_lines": recovered_loc,
                "test_code_ratio": summary.get("test_code_ratio", 0.0) or 0.0,
            }
        )

        for s in d.get("sessions", []):
            a = s.get("agentic", {})
            session_rows.append(
                {
                    "session_id": f"{story_id}_{s.get('session_number', 0)}",
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
                    "total_tokens": a.get("total_tokens"),
                    "cache_read_tokens": a.get("cache_read_tokens", 0) or 0,
                    "cache_write_tokens": a.get("cache_write_tokens", 0) or 0,
                    "context_tokens": a.get("context_tokens", 0) or 0,
                    "cache_hit_rate": a.get("cache_hit_rate"),
                    "cost_usd": s.get("cost_usd"),
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
                }
            )

    return session_rows, story_rows


def _write_parquet_atomic(rows: list[dict[str, Any]], schema: pa.Schema, final_path: Path) -> None:
    """Write a parquet table atomically — temp file + rename, never a partial write.

    Writes an EMPTY (zero-row) table when ``rows`` is empty, so an empty canonical source
    overwrites a stale parquet rather than leaving the older table in place (public-truth
    review "smaller").
    """
    tmp_path = final_path.with_suffix(final_path.suffix + ".tmp")
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, tmp_path, compression="zstd")
    os.replace(tmp_path, final_path)


def _content_sha256(rows: list[dict[str, Any]]) -> str:
    """Deterministic content hash of the flattened rows (m4 sidecar field).

    Hashing the *rows* (not the parquet bytes) makes the hash independent of pyarrow's
    serialization metadata, so ``--check`` can recompute it from ``_build_rows`` alone.
    """
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _transform_sha256() -> str:
    """Hash of the sync transform code — this file (m4 sidecar field)."""
    return hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()


def _schema_sha256() -> str:
    """Hash of the two table schemas, field name + type (m4 sidecar field)."""

    def _fields(schema: pa.Schema) -> list[tuple[str, str]]:
        return [(f.name, str(f.type)) for f in schema]

    return hashlib.sha256(
        json.dumps(
            {"sessions": _fields(SESSION_SCHEMA), "stories": _fields(STORY_SCHEMA)},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _write_identity_sidecar(tables, counts: dict[str, int], session_rows, story_rows) -> None:
    """Write the source-identity sidecar alongside the parquet (atomic, like the tables).

    m4: the sidecar now carries content hashes — the sessions/stories row digests, the sync
    transform's own source hash, and the schema hash — so ``--check`` proves not just "the
    row counts match" but "the rows, the transform, and the schema are all unchanged".
    """
    sidecar = {
        "schema_version": "sync-identity/v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry_identity_sha256": tables.identity.registry_identity_sha256,
        "resolved_input_sha256": tables.resolved_input_sha256,
        "rows": counts,
        "sessions_rows_sha256": _content_sha256(session_rows),
        "stories_rows_sha256": _content_sha256(story_rows),
        "sync_transform_sha256": _transform_sha256(),
        "schema_sha256": _schema_sha256(),
    }
    tmp_path = SYNC_IDENTITY_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    os.replace(tmp_path, SYNC_IDENTITY_PATH)


def sync() -> dict[str, int]:
    """Sync the canonical story payloads to parquet (atomic) + a source-identity sidecar.

    Returns row counts.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tables = load_canonical_tables("story", "analysis")
    session_rows, story_rows = _build_rows(tables)

    _write_parquet_atomic(session_rows, SESSION_SCHEMA, DATA_DIR / "sessions.parquet")
    _write_parquet_atomic(story_rows, STORY_SCHEMA, DATA_DIR / "stories.parquet")

    counts = {"sessions": len(session_rows), "stories": len(story_rows)}
    _write_identity_sidecar(tables, counts, session_rows, story_rows)
    return counts


def check() -> int:
    """Real parity check: parquet rows + identities vs the current resolver output.

    Returns exit code (0 = current, 1 = stale). A stale sync is detected when the sidecar's
    registry/resolved-input identity differs from the resolver's, or when a parquet row count
    differs from the freshly recomputed row count — not merely that a file exists.
    """
    tables = load_canonical_tables("story", "analysis")
    session_rows, story_rows = _build_rows(tables)
    expected = {"sessions": len(session_rows), "stories": len(story_rows)}

    if not SYNC_IDENTITY_PATH.exists():
        print("FAIL: no sync_identity.json sidecar — run sync first")
        return 1
    try:
        sidecar = json.loads(SYNC_IDENTITY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("FAIL: sync_identity.json is unreadable — run sync first")
        return 1

    problems: list[str] = []
    if sidecar.get("registry_identity_sha256") != tables.identity.registry_identity_sha256:
        problems.append("registry identity mismatch — the parquet is stale")
    if sidecar.get("resolved_input_sha256") != tables.resolved_input_sha256:
        problems.append("resolved-input identity mismatch — the parquet is stale")

    # ── m4 content hashes: the rows, the transform, and the schema are all unchanged ──
    for field, recomputed in (
        ("sessions_rows_sha256", _content_sha256(session_rows)),
        ("stories_rows_sha256", _content_sha256(story_rows)),
        ("sync_transform_sha256", _transform_sha256()),
        ("schema_sha256", _schema_sha256()),
    ):
        if sidecar.get(field) != recomputed:
            problems.append(f"{field} mismatch — re-run sync (the transform/schema/rows changed)")

    conn = duckdb.connect()
    try:
        for table, expected_n in expected.items():
            path = DATA_DIR / f"{table}.parquet"
            if not path.exists():
                problems.append(f"{table}.parquet is missing")
                continue
            actual_n = conn.execute(f"SELECT count(*) FROM read_parquet('{path}')").fetchone()[0]
            print(f"  {table}.parquet: {actual_n:,} rows (expected {expected_n:,})")
            if actual_n != expected_n:
                problems.append(f"{table}.parquet has {actual_n} rows, expected {expected_n}")
            if sidecar.get("rows", {}).get(table) != actual_n:
                problems.append(
                    f"{table}.parquet rows {actual_n} != sidecar "
                    f"{sidecar.get('rows', {}).get(table)}"
                )
    finally:
        conn.close()

    if problems:
        print("FAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("OK: parquet matches the current canonical source")
    return 0


def query(parquet_path: Path, sql: str) -> str:
    """Run a duckdb query against a parquet file."""
    conn = duckdb.connect()
    result = conn.execute(f"SELECT * FROM read_parquet('{parquet_path}') {sql}").fetchdf()
    conn.close()
    return result.to_string()


def main() -> None:
    import sys

    if "--check" in sys.argv:
        sys.exit(check())

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
