"""Session-budget tests — ``session-budget/v1`` (remediation closed-loop, decision f987cde9).

The rule the 25-hour 2026-09-13 session burned six hours to teach, now executable: a session
past its context/turn budget must CLOSE, not keep accepting work. Driven in both directions:
the positive half proves the verdicts (OK/WARN/CLOSE) move with the measured state, and the
negative half proves an unreadable budget is UNJUDGED (exit 1) — never silently OK, exactly as
an unknown cost is never zero. The journal is append-only by construction and is asserted as
such: every judgment appends one line, and a rerun appends another — never rewrites.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.session_budget import (
    SCHEMA_ID,
    _measure,
    _select_session,
    judge,
    main,
)

ROOT = Path(__file__).resolve().parent.parent


def _make_session_db(path: Path, *, turns: int, context: int) -> tuple[str, str]:
    """A synthetic opencode-shaped session db: two sessions, the judged one newest."""
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE session (id TEXT, time_updated INTEGER)")
    con.execute("CREATE TABLE message (session_id TEXT, time_created INTEGER, data TEXT)")
    sid = "ses_judged"
    con.execute("INSERT INTO session VALUES (?, ?)", (sid, 200))
    con.execute("INSERT INTO session VALUES (?, ?)", ("ses_old", 100))
    for i in range(turns - 1):
        con.execute(
            "INSERT INTO message VALUES (?, ?, ?)",
            (sid, i, json.dumps({"role": "assistant", "tokens": {"input": 10, "cache": {"read": 10, "write": 0}}})),
        )
    # The LAST assistant message carries the live context size.
    con.execute(
        "INSERT INTO message VALUES (?, ?, ?)",
        (sid, turns, json.dumps({"role": "assistant", "tokens": {"input": context, "cache": {"read": 0, "write": 0}}})),
    )
    con.execute(
        "INSERT INTO message VALUES (?, ?, ?)",
        (sid, turns + 1, json.dumps({"role": "user", "tokens": {"input": 5}})),
    )
    con.commit()
    con.close()
    return sid, path.name


# ── the verdict function ────────────────────────────────────────────────────────


def test_judge_ok_below_both_budgets():
    assert judge(turns=10, context=100_000, ctx_budget=200_000, turn_budget=80) == "OK"


def test_judge_warn_at_the_warn_fraction():
    assert judge(turns=64, context=50_000, ctx_budget=200_000, turn_budget=80) == "WARN"  # 0.8 × 80
    assert judge(turns=10, context=160_000, ctx_budget=200_000, turn_budget=80) == "WARN"  # 0.8 × 200K


def test_judge_close_at_either_budget():
    assert judge(turns=80, context=10_000, ctx_budget=200_000, turn_budget=80) == "CLOSE"
    assert judge(turns=10, context=200_000, ctx_budget=200_000, turn_budget=80) == "CLOSE"


# ── measurement against a real (synthetic) database ─────────────────────────────


def test_measure_and_select_read_the_open_code_shape(tmp_path: Path):
    db = tmp_path / "opencode.db"
    sid, _ = _make_session_db(db, turns=7, context=42_000)
    assert _select_session(db, None) == sid
    turns, context = _measure(db, sid)
    assert turns == 7
    assert context == 42_000


# ── the CLI ──────────────────────────────────────────────────────────────────────


def test_main_reports_ok_and_appends_one_journal_line(tmp_path: Path, monkeypatch):
    db = tmp_path / "opencode.db"
    sid, _ = _make_session_db(db, turns=5, context=30_000)
    journal = tmp_path / "budget.jsonl"
    monkeypatch.setenv("FINOPS_SESSION_BUDGET_JOURNAL", str(journal))
    rc = main(["--db", str(db), "--session-id", sid, "--ctx-budget", "200000",
               "--turn-budget", "80"])
    assert rc == 0
    lines = journal.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["verdict"] == "OK" and entry["schema"] == SCHEMA_ID
    assert entry["turns"] == 5 and entry["context_tokens"] == 30_000


def test_main_rerun_appends_never_rewrites(tmp_path: Path, monkeypatch):
    """The journal is append-only: a second judgment is a second line."""
    db = tmp_path / "opencode.db"
    sid, _ = _make_session_db(db, turns=5, context=30_000)
    journal = tmp_path / "budget.jsonl"
    monkeypatch.setenv("FINOPS_SESSION_BUDGET_JOURNAL", str(journal))
    main(["--db", str(db), "--session-id", sid])
    main(["--db", str(db), "--session-id", sid])
    assert len(journal.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_main_close_exits_two(tmp_path: Path, monkeypatch):
    """The exact failure class: context at/over budget exits 2 — the turn must close."""
    db = tmp_path / "opencode.db"
    sid, _ = _make_session_db(db, turns=5, context=200_000)
    monkeypatch.setenv("FINOPS_SESSION_BUDGET_JOURNAL", str(tmp_path / "budget.jsonl"))
    rc = main(["--db", str(db), "--session-id", sid, "--json"])
    assert rc == 2


def test_main_unreadable_budget_is_unjudged_never_ok(tmp_path: Path, monkeypatch):
    """A missing database is UNJUDGED (exit 1) — an unknown budget is never unlimited."""
    monkeypatch.setenv("FINOPS_SESSION_BUDGET_JOURNAL", str(tmp_path / "budget.jsonl"))
    rc = main(["--db", str(tmp_path / "absent.db"), "--json"])
    assert rc == 1
