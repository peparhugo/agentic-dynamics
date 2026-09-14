"""Session-budget tests — ``session-budget/v1`` (remediation closed-loop, decision f987cde9).

The rule the 25-hour 2026-09-13 session burned six hours to teach, now executable: a session
past its context/turn budget must CLOSE, not keep accepting work. Driven in both directions:
the positive half proves the verdicts (OK/WARN/CLOSE) move with the measured state, and the
negative half proves an unreadable budget is UNJUDGED (exit 1) — never silently OK, exactly as
an unknown cost is never zero. The journal is append-only by construction and is asserted as
such: every judgment appends one line, and a rerun appends another — never rewrites.

The identity + zero-overwrite fixes (AIO remediation 2026-09-14):

* the session under judgment is the EXPLICIT one (``--session-id`` / ``FINOPS_SESSION_ID``) —
  a newer CHILD session never shadows the AIO's, and an invalid id is a refusal, not a guess;
* an unfinished usage row (a streaming turn with no tokens block) must not overwrite a valid
  reading with zero — the last COMPLETED sample is the reading, flagged ``usage_incomplete``.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.session_budget import (
    SCHEMA_ID,
    SESSION_ID_ENV,
    _measure,
    _resolve_session_id,
    _session_exists,
    judge,
    main,
)

ROOT = Path(__file__).resolve().parent.parent


def _make_session_db(path: Path, *, turns: int, context: int,
                     sid: str = "ses_judged") -> str:
    """A synthetic opencode-shaped session db: the judged session plus an OLDER sibling."""
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE session (id TEXT, time_updated INTEGER)")
    con.execute("CREATE TABLE message (session_id TEXT, time_created INTEGER, data TEXT)")
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
    return sid


def _add_unfinished_assistant_message(path: Path, sid: str, *, zero_valued: bool = False) -> None:
    """Append a STREAMING assistant message after the completed samples.

    ``zero_valued=True`` writes the REAL OpenCode pending shape (Astra finding, 2026-09-14):
    the usage fields EXIST and are initialized to ZERO before the turn finalizes. The check
    must treat that exactly like the absent-fields shape — an unfinished sample, never a
    valid zero reading.
    """
    if zero_valued:
        payload = {"role": "assistant",
                   "tokens": {"input": 0, "output": 0, "reasoning": 0,
                              "cache": {"read": 0, "write": 0}}}
    else:
        payload = {"role": "assistant"}
    con = sqlite3.connect(path)
    con.execute(
        "INSERT INTO message VALUES (?, ?, ?)",
        (sid, 9000, json.dumps(payload)),
    )
    con.commit()
    con.close()


def _add_younger_child_session(path: Path, sid: str) -> str:
    """A NEWER child session (updated after the judged one) — the row a most-recently-updated
    fallback would wrongly pick."""
    con = sqlite3.connect(path)
    con.execute("INSERT INTO session VALUES (?, ?)", ("ses_child_newer", 300))
    con.execute(
        "INSERT INTO message VALUES (?, ?, ?)",
        ("ses_child_newer", 0, json.dumps({"role": "assistant", "tokens": {"input": 1}})),
    )
    con.commit()
    con.close()
    return "ses_child_newer"


# ── the verdict function ────────────────────────────────────────────────────────


def test_judge_ok_below_both_budgets():
    assert judge(turns=10, context=100_000, ctx_budget=200_000, turn_budget=80) == "OK"


def test_judge_warn_at_the_warn_fraction():
    assert judge(turns=64, context=50_000, ctx_budget=200_000, turn_budget=80) == "WARN"  # 0.8 × 80
    assert judge(turns=10, context=160_000, ctx_budget=200_000, turn_budget=80) == "WARN"  # 0.8 × 200K


def test_judge_close_at_either_budget():
    assert judge(turns=80, context=10_000, ctx_budget=200_000, turn_budget=80) == "CLOSE"
    assert judge(turns=10, context=200_000, ctx_budget=200_000, turn_budget=80) == "CLOSE"


# ── identity: the explicit session, never a guess ───────────────────────────────


def test_measure_reads_the_open_code_shape(tmp_path: Path):
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=7, context=42_000)
    turns, context, incomplete = _measure(db, sid)
    assert turns == 7
    assert context == 42_000
    assert incomplete is False


def test_a_newer_child_session_never_shadows_the_explicit_identity(tmp_path: Path):
    """The judged session is the NAMED one — a newer child row does not become the AIO's
    measurement (the most-recently-updated fallback is gone)."""
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=7, context=42_000)
    _add_younger_child_session(db, sid)
    assert _resolve_session_id(sid, env={}) == sid
    assert _session_exists(db, sid)
    assert _session_exists(db, "ses_child_newer")
    turns, context, _ = _measure(db, sid)
    assert turns == 7 and context == 42_000  # the CHILD's 1-token row did not leak in


def test_an_unfinished_usage_row_never_overwrites_a_valid_reading(tmp_path: Path):
    """The zero-overwrite fix: a streaming turn (no tokens) after completed samples keeps the
    last COMPLETED reading and flags the incompleteness — never a silent 0."""
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=7, context=42_000)
    _add_unfinished_assistant_message(db, sid)
    turns, context, incomplete = _measure(db, sid)
    assert turns == 8  # the in-flight turn is still a turn
    assert context == 42_000  # the completed reading survives
    assert incomplete is True


def test_a_pending_zero_valued_message_never_overwrites_a_valid_reading(tmp_path: Path):
    """Astra's reproduction, verbatim shape: OpenCode initializes a pending message's usage
    fields to ZERO. Keys-present-but-all-zero is NOT a completed sample — a 240,000 reading
    followed by a pending zero-valued message must still measure 240,000 (and CLOSE at the
    200K policy budget), never 0/OK."""
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=7, context=240_000)
    _add_unfinished_assistant_message(db, sid, zero_valued=True)
    turns, context, incomplete = _measure(db, sid)
    assert turns == 8
    assert context == 240_000, "the pending zero-valued message overwrote the reading"
    assert incomplete is True
    assert judge(turns=turns, context=context, ctx_budget=200_000, turn_budget=80) == "CLOSE"


def test_no_identity_is_a_refusal_not_a_guess(tmp_path: Path, monkeypatch):
    """No --session-id and no FINOPS_SESSION_ID → UNJUDGED with the named reason; the check
    never picks the globally most recently updated session."""
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000)
    _add_younger_child_session(db, sid)
    monkeypatch.setenv("FINOPS_SESSION_BUDGET_JOURNAL", str(tmp_path / "budget.jsonl"))
    monkeypatch.delenv(SESSION_ID_ENV, raising=False)
    rc = main(["--db", str(db), "--json"])
    assert rc == 1
    journal = (tmp_path / "budget.jsonl").read_text(encoding="utf-8").strip().splitlines()
    entry = json.loads(journal[-1])
    assert entry["verdict"] == "UNJUDGED"
    assert "no session identity supplied" in entry["reason"]


def test_an_invalid_session_id_is_rejected(tmp_path: Path, monkeypatch):
    """A nonexistent id is UNJUDGED with the named reason — never a fallback to some other
    row, never a (0, 0) reading that reads as an empty-but-valid session."""
    db = tmp_path / "opencode.db"
    _make_session_db(db, turns=5, context=30_000)
    monkeypatch.setenv("FINOPS_SESSION_BUDGET_JOURNAL", str(tmp_path / "budget.jsonl"))
    rc = main(["--db", str(db), "--session-id", "ses_nonexistent", "--json"])
    assert rc == 1
    journal = (tmp_path / "budget.jsonl").read_text(encoding="utf-8").strip().splitlines()
    entry = json.loads(journal[-1])
    assert entry["verdict"] == "UNJUDGED"
    assert "does not exist" in entry["reason"]


def test_the_runtime_env_supplies_the_identity(tmp_path: Path, monkeypatch):
    """FINOPS_SESSION_ID (the runtime's explicit AIO session identity) is honored."""
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000)
    monkeypatch.setenv("FINOPS_SESSION_BUDGET_JOURNAL", str(tmp_path / "budget.jsonl"))
    monkeypatch.setenv(SESSION_ID_ENV, sid)
    rc = main(["--db", str(db), "--json"])
    assert rc == 0
    journal = (tmp_path / "budget.jsonl").read_text(encoding="utf-8").strip().splitlines()
    entry = json.loads(journal[-1])
    assert entry["session_id"] == sid and entry["verdict"] == "OK"


# ── the CLI ──────────────────────────────────────────────────────────────────────


def test_main_reports_ok_and_appends_one_journal_line(tmp_path: Path, monkeypatch):
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=30_000)
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
    sid = _make_session_db(db, turns=5, context=30_000)
    journal = tmp_path / "budget.jsonl"
    monkeypatch.setenv("FINOPS_SESSION_BUDGET_JOURNAL", str(journal))
    main(["--db", str(db), "--session-id", sid])
    main(["--db", str(db), "--session-id", sid])
    assert len(journal.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_main_close_exits_two(tmp_path: Path, monkeypatch):
    """The exact failure class: context at/over budget exits 2 — the turn must close."""
    db = tmp_path / "opencode.db"
    sid = _make_session_db(db, turns=5, context=200_000)
    monkeypatch.setenv("FINOPS_SESSION_BUDGET_JOURNAL", str(tmp_path / "budget.jsonl"))
    rc = main(["--db", str(db), "--session-id", sid, "--json"])
    assert rc == 2


def test_main_unreadable_budget_is_unjudged_never_ok(tmp_path: Path, monkeypatch):
    """A missing database is UNJUDGED (exit 1) — an unknown budget is never unlimited."""
    monkeypatch.setenv("FINOPS_SESSION_BUDGET_JOURNAL", str(tmp_path / "budget.jsonl"))
    rc = main(["--db", str(tmp_path / "absent.db"), "--session-id", "ses_x", "--json"])
    assert rc == 1
