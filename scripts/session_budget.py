#!/usr/bin/env python3
"""session_budget.py — the AIO's session budget check (remediation closed-loop, decision f987cde9).

The 25-hour 2026-09-13 session ran to ~698K context tokens with zero compactions and its own
reasoning repeating "context budget is nearly exhausted" for the last six hours — while it kept
accepting new work. The failure class is now a rule, and the rule is now executable: the AIO runs
this check with the control packet at the start of every decision turn.

    agentic-dynamics session budget                        # human verdict: OK / WARN / CLOSE
    agentic-dynamics session budget --json                 # machine surface: session-budget/v1

Judgment (context = the LAST COMPLETED assistant message's input + cache read + cache write —
what the model would process on the next turn; turns = assistant messages so far):

* ``OK``    — below 80% of either budget: keep working.
* ``WARN``  — at or above 80% of either budget: no new work — wrap up, close the session, hand off.
* ``CLOSE`` — at or above either budget: the session must close NOW and hand off to a fresh one.
* ``UNJUDGED`` — the session cannot be measured. Exit code 1, deliberately: an unknown
  budget is never treated as unlimited (the same rule as unknown cost).

Identity (the AIO remediation 2026-09-14): the session under judgment is the EXPLICIT one —
``--session-id``, else ``FINOPS_SESSION_ID`` (the runtime's AIO session identity). There is NO
most-recently-updated fallback: guessing the newest session measured a CHILD (or the wrong
conversation) as if it were the AIO, and the defect hid behind the 0-context reading it then
produced. An absent identity and a nonexistent id are both UNJUDGED (exit 1) with a reason —
never a silent guess.

Measurement (the zero-overwrite fix): context is derived from a defined COMPLETED usage
sample. An unfinished assistant message (no tokens block — a streaming turn, an unavailable
usage read) must never overwrite a valid reading with zero: the reading falls back to the most
recent COMPLETED sample, and the result carries ``usage_incomplete: true`` so the deviation is
visible, not silent.

The budgets are CONFIGURABLE POLICY (the sizes at which the AIO is directed to close/hand
off) — labelled as such, never as proven model-degradation thresholds.

Exit codes: 0 = OK, 1 = WARN/UNJUDGED, 2 = CLOSE. Every judgment appends one line to the
session-budget journal (append-only; override the path with ``FINOPS_SESSION_BUDGET_JOURNAL``
for tests).

The verdict is derived from the opencode session database (``~/.local/share/opencode/opencode.db``
by default; ``FINOPS_OPENCODE_DB`` overrides).
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

#: The policy budgets (configurable, never measured thresholds): close at 200K context tokens
#: or 80 assistant turns — the policy the AIO is directed to observe, expressed as numbers.
DEFAULT_CTX_BUDGET = 200_000
DEFAULT_TURN_BUDGET = 80
WARN_FRACTION = 0.8

#: The explicit-session environment (the runtime's AIO session identity).
SESSION_ID_ENV = "FINOPS_SESSION_ID"

#: The journal each judgment appends to (append-only; a budget observation is never rewritten).
JOURNAL_DEFAULT = (
    Path(__file__).resolve().parent.parent
    / "experiments" / "results" / "control" / "session_budget.jsonl"
)


def _default_db() -> Path:
    return Path(os.environ.get("FINOPS_OPENCODE_DB") or Path.home() / ".local/share/opencode/opencode.db")


def _resolve_session_id(args_session: str | None, env: dict | None = None) -> str | None:
    """The EXPLICIT session identity: the flag, then the runtime env. ``None`` = not supplied
    (a refusal to guess — never "pick the most recently updated row")."""
    source = os.environ if env is None else env
    return (args_session or source.get(SESSION_ID_ENV) or "").strip() or None


def _session_exists(db_path: Path, session_id: str) -> bool:
    """True when the named session row exists (a nonexistent id is a refusal, not a fallback)."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        cur.execute("SELECT 1 FROM session WHERE id=?", (session_id,))
        return cur.fetchone() is not None
    finally:
        con.close()


def _measure(db_path: Path, session_id: str) -> tuple[int, int, bool]:
    """``(turns, context, usage_incomplete)`` for the session.

    ``turns`` — the assistant messages recorded so far.
    ``context`` — the LAST COMPLETED assistant usage sample (input + cache read + cache write).
    A sample is COMPLETED only when it carries a NON-ZERO value: OpenCode initializes a
    pending message's usage fields to ZERO before the turn finalizes, so
    keys-present-but-all-zero is the real pending shape — treating it as completed is exactly
    the zero-overwrite bug (Astra finding, 2026-09-14: a 240,000 reading followed by a
    pending zero-valued message measured 0/OK). Both shapes — absent fields and all-zero
    fields — leave the reading untouched and set ``usage_incomplete``. A session with no
    completed sample reads (0, 0, True) — an honest "nothing measurable", flagged, never a
    silent zero.
    """
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT data FROM message WHERE session_id=? ORDER BY time_created",
            (session_id,),
        )
        turns = 0
        context = 0
        usage_incomplete = False
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
            values = (
                int(tokens.get("input", 0) or 0),
                int(tokens.get("output", 0) or 0),
                int(tokens.get("reasoning", 0) or 0),
                int(cache.get("read", 0) or 0),
                int(cache.get("write", 0) or 0),
            )
            if not any(value > 0 for value in values):
                # Absent fields AND all-zero fields are both the unfinished shape.
                usage_incomplete = True
                continue
            context = values[0] + values[3] + values[4]  # input + cache read + cache write
        return turns, context, usage_incomplete
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
    parser.add_argument("--session-id", default=None,
                        help="the session id to judge (default: $FINOPS_SESSION_ID — the "
                             "runtime's AIO session identity; there is NO most-recently-updated "
                             "fallback: an absent or nonexistent id is UNJUDGED)")
    parser.add_argument("--ctx-budget", type=int, default=DEFAULT_CTX_BUDGET,
                        help="context-token budget POLICY (default %(default)s — configurable, "
                             "never a measured threshold)")
    parser.add_argument("--turn-budget", type=int, default=DEFAULT_TURN_BUDGET,
                        help="assistant-turn budget POLICY (default %(default)s — configurable, "
                             "never a measured threshold)")
    parser.add_argument("--json", action="store_true", help="emit session-budget/v1 JSON")
    parser.add_argument("--no-journal", action="store_true", help="skip the journal append")
    return parser


def measure_verdict(
    session_id: str | None,
    *,
    db_path: Path | None = None,
    ctx_budget: int = DEFAULT_CTX_BUDGET,
    turn_budget: int = DEFAULT_TURN_BUDGET,
) -> tuple[str, str]:
    """The measurement seam for programmatic callers (the AIO exec-boundary gate).

    Returns ``(verdict, reason)`` with the SAME judgment as the CLI: an absent identity, an
    absent session, or an unreadable db is ``UNJUDGED`` with a reason — never a silent OK
    (an unknown budget is never unlimited). The judged session is the EXPLICIT identity;
    there is no most-recently-updated fallback.
    """
    try:
        path = Path(db_path) if db_path else _default_db()
        if not path.is_file():
            raise FileNotFoundError(f"session db {path} not found")
        sid = (session_id or "").strip()
        if not sid:
            raise LookupError(f"no session identity supplied (--session-id or {SESSION_ID_ENV})")
        if not _session_exists(path, sid):
            raise LookupError(f"session {sid!r} does not exist in {path}")
        turns, context, _incomplete = _measure(path, sid)
        return judge(turns=turns, context=context, ctx_budget=ctx_budget, turn_budget=turn_budget), ""
    except Exception as exc:  # noqa: BLE001 — an unreadable budget is UNJUDGED, never OK
        return "UNJUDGED", f"{type(exc).__name__}: {exc}"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db_path = Path(args.db) if args.db else _default_db()

    verdict = "UNJUDGED"
    turns = 0
    context = 0
    usage_incomplete = False
    session_id = ""
    reason = ""
    try:
        if not db_path.is_file():
            raise FileNotFoundError(f"session db {db_path} not found")
        session_id = _resolve_session_id(args.session_id)
        if not session_id:
            raise LookupError(
                "no session identity supplied — pass --session-id or export "
                f"{SESSION_ID_ENV}; the check never guesses the most recently updated session"
            )
        if not _session_exists(db_path, session_id):
            raise LookupError(f"session {session_id!r} does not exist in {db_path}")
        turns, context, usage_incomplete = _measure(db_path, session_id)
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
        "usage_incomplete": bool(usage_incomplete) and verdict != "UNJUDGED",
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
            + (" (usage incomplete — last completed sample used)" if result["usage_incomplete"] else "")
            + (f" ({reason})" if reason else "")
        )
    return {"OK": 0, "WARN": 1, "CLOSE": 2}.get(verdict, 1)


if __name__ == "__main__":
    raise SystemExit(main())
