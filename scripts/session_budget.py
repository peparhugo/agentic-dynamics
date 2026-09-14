#!/usr/bin/env python3
"""session_budget.py — the AIO's session budget check (remediation closed-loop, decision f987cde9).

The 25-hour 2026-09-13 session ran to ~698K context tokens with zero compactions and its own
reasoning repeating "context budget is nearly exhausted" for the last six hours — while it kept
accepting new work. The failure class is now a rule, and the rule is now executable: the AIO runs
this check with the control packet at the start of every decision turn.

    agentic-dynamics session budget            # human verdict: OK / WARN / CLOSE
    agentic-dynamics session budget --json     # machine surface: session-budget/v1

Judgment (context = the last assistant message's input + cache read + cache write — what the
model would process on the next turn; turns = assistant messages so far):

* ``OK``    — below 80% of either budget: keep working.
* ``WARN``  — at or above 80% of either budget: no new work — wrap up, close the session, hand off.
* ``CLOSE`` — at or above either budget: the session must close NOW and hand off to a fresh one.
* ``UNJUDGED`` — the session database cannot be read. Exit code 1, deliberately: an unknown
  budget is never treated as unlimited (the same rule as unknown cost).

Exit codes: 0 = OK, 1 = WARN, 2 = CLOSE. Every judgment appends one line to the session-budget
journal (append-only; override the path with ``FINOPS_SESSION_BUDGET_JOURNAL`` for tests).

The verdict is derived from the opencode session database (``~/.local/share/opencode/opencode.db``
by default; ``FINOPS_OPENCODE_DB`` overrides). The session under judgment is ``--session-id``, or
the most recently updated session when omitted — which is the AIO's own session while it runs.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ImportError:
    from scripts import _bootstrap  # noqa: F401

SCHEMA_ID = "session-budget/v1"

#: The re-baselined defaults (decision f987cde9): close at 200K context tokens or 80 assistant
#: turns — the size at which the prior session's judgment measurably degraded.
DEFAULT_CTX_BUDGET = 200_000
DEFAULT_TURN_BUDGET = 80
WARN_FRACTION = 0.8

#: The journal each judgment appends to (append-only; a budget observation is never rewritten).
JOURNAL_DEFAULT = (
    Path(__file__).resolve().parent.parent
    / "experiments" / "results" / "control" / "session_budget.jsonl"
)


def _default_db() -> Path:
    return Path(os.environ.get("FINOPS_OPENCODE_DB") or Path.home() / ".local/share/opencode/opencode.db")


def _select_session(db_path: Path, session_id: str | None) -> str | None:
    """The session under judgment: ``session_id`` or the most recently updated row."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        if session_id:
            cur.execute("SELECT id FROM session WHERE id=?", (session_id,))
        else:
            cur.execute("SELECT id FROM session ORDER BY time_updated DESC LIMIT 1")
        row = cur.fetchone()
        return str(row[0]) if row else None
    finally:
        con.close()


def _measure(db_path: Path, session_id: str) -> tuple[int, int]:
    """(turns, context) for the session — assistant messages and the live context size."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT data FROM message WHERE session_id=? ORDER BY time_created",
            (session_id,),
        )
        turns = 0
        context = 0
        for (blob,) in cur.fetchall():
            try:
                data = json.loads(blob)
            except (json.JSONDecodeError, TypeError):
                continue
            if data.get("role") != "assistant":
                continue
            turns += 1
            tokens = data.get("tokens") or {}
            cache = tokens.get("cache") or {}
            context = int(tokens.get("input", 0)) + int(cache.get("read", 0)) + int(cache.get("write", 0))
        return turns, context
    finally:
        con.close()


def judge(*, turns: int, context: int, ctx_budget: int, turn_budget: int) -> str:
    """The verdict. CLOSE dominates WARN dominates OK — a near-budget turn is a warning even
    under the token budget, exactly as a near-deadline cost is a warning under the dollar cap."""
    if context >= ctx_budget or turns >= turn_budget:
        return "CLOSE"
    if context >= WARN_FRACTION * ctx_budget or turns >= WARN_FRACTION * turn_budget:
        return "WARN"
    return "OK"


def _append_journal(entry: dict[str, object]) -> None:
    path = Path(os.environ.get("FINOPS_SESSION_BUDGET_JOURNAL") or JOURNAL_DEFAULT)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics session budget",
        description="Judge the AIO's session budget: OK / WARN / CLOSE (session-budget/v1).",
    )
    parser.add_argument("--db", default=None, help=f"opencode session db (default: {_default_db()})")
    parser.add_argument("--session-id", default=None, help="session id to judge (default: most recently updated)")
    parser.add_argument("--ctx-budget", type=int, default=DEFAULT_CTX_BUDGET, help=f"context-token budget (default {DEFAULT_CTX_BUDGET})")
    parser.add_argument("--turn-budget", type=int, default=DEFAULT_TURN_BUDGET, help=f"assistant-turn budget (default {DEFAULT_TURN_BUDGET})")
    parser.add_argument("--json", action="store_true", help="emit session-budget/v1 JSON")
    parser.add_argument("--no-journal", action="store_true", help="skip the journal append")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db_path = Path(args.db) if args.db else _default_db()

    verdict = "UNJUDGED"
    turns = 0
    context = 0
    session_id = args.session_id or ""
    reason = ""
    try:
        if not db_path.is_file():
            raise FileNotFoundError(f"session db {db_path} not found")
        session_id = args.session_id or _select_session(db_path, args.session_id)
        if not session_id:
            raise LookupError("no session row to judge")
        turns, context = _measure(db_path, session_id)
        verdict = judge(
            turns=turns, context=context,
            ctx_budget=args.ctx_budget, turn_budget=args.turn_budget,
        )
    except Exception as exc:  # noqa: BLE001 — an unreadable budget is UNJUDGED, never OK
        reason = f"{type(exc).__name__}: {exc}"

    now = datetime.now(timezone.utc).isoformat()
    result = {
        "schema": SCHEMA_ID,
        "ts": now,
        "session_id": session_id,
        "turns": turns,
        "context_tokens": context,
        "ctx_budget": args.ctx_budget,
        "turn_budget": args.turn_budget,
        "verdict": verdict,
        "reason": reason,
    }
    if not args.no_journal:
        # The verdict must render even when the journal cannot.
        with contextlib.suppress(OSError):
            _append_journal(result)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(
            f"session budget: {verdict} — turns {turns}/{args.turn_budget}, "
            f"context {context}/{args.ctx_budget}"
            + (f" ({reason})" if reason else "")
        )
    return {"OK": 0, "WARN": 1, "CLOSE": 2}.get(verdict, 1)


if __name__ == "__main__":
    raise SystemExit(main())
