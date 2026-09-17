#!/usr/bin/env python3
"""session_cache_report.py — the provider cache-accounting join for AIO sessions.

Why this exists (the gap it closes): the 2026-09-17 review found the AIO capsule plugin
inserted a VOLATILE snapshot (observation timestamp, budget counters, control-packet state)
into the SYSTEM prompt, ahead of the conversation. DeepSeek matches PREFIXES for prompt
caching, so the changing prefix re-billed the entire conversation on every capsule refresh
(measured on this deployment: sessions with 28-35% token-weighted miss rates and hundreds of
full-context misses). Nothing in the repo joined prompt composition to the provider's own
cache accounting — this report IS that join, and it is the repair's acceptance measurement:
a capsule refresh must add new context without rewriting previously sent context, and the
measured input cost must improve.

The measurement (the reviewer's formula, token-weighted):

    miss_rate = sum(prompt_cache_miss_tokens)
                / (sum(prompt_cache_hit_tokens) + sum(prompt_cache_miss_tokens))

read from the opencode session database — the runtime's own accounting. Per assistant message
with a COMPLETED usage sample: ``tokens.input`` is the cache-miss input (DeepSeek's
``prompt_cache_miss_tokens``; it excludes cache reads — verified: input + cache.read + output
+ reasoning == tokens.total), and ``tokens.cache.read`` is the hit (``prompt_cache_hit_tokens``).
A message whose usage is still the pending zero block is skipped, never counted as a miss.

Cohorts, grouped by what the PLUGIN did (the delivery journal the repair adds,
``.opencode/aio-context-events.jsonl`` — one line per ``messages.transform`` delivery):

* ``refresh``      — the request carried a NEW capsule observation (journal kind ``refresh``);
* ``continuation`` — the request re-delivered an unchanged snapshot (journal kind
                     ``continuation``) or the capsule was unavailable (kind ``unavailable``);
* ``compaction``   — the compaction summary generation call, plus the first request after it
                     (the post-compaction recovery request), classified from the session DB
                     itself (``mode == "compaction"`` / a preceding summary);
* ``unclassified`` — no journal event could be joined (pre-repair traffic, or a missing
                     journal file) — reported honestly, never silently folded in.

The join is a heuristic over delivery events from the two plugin surfaces that place the
snapshot into a conversation: a ``chat.message`` ATTACH (the persisted part on the incoming
user message — written just before that message's assistant request) and a
``messages.transform`` APPEND (the post-compaction recovery fallback — written just before
the model call it accompanies). For each measured request, the LAST attach in the window
ending at its assistant-message creation classifies it; only if none exists, the FIRST
append in the window after that creation is used. Events emitted by the compaction hook
(``session.compacting``) are excluded — they are not conversation deliveries.

    agentic-dynamics session cache-report                          # the recent sessions
    agentic-dynamics session cache-report --session ses_... --json # one session, machine form
    agentic-dynamics session cache-report --all                    # every session in the db

Every run appends the report to the append-only journal
(``experiments/results/control/session_cache_reports.jsonl``;
``FINOPS_SESSION_CACHE_JOURNAL`` overrides; ``--no-journal`` skips).

Exit codes: 0 = report rendered; 1 = no measured requests (an honest empty report — never a
fabricated rate); 2 = the session db is missing or unreadable.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

SCHEMA_ID = "session-cache-report/v1"

#: The opencode session database (the runtime's accounting home).
DB_ENV = "FINOPS_OPENCODE_DB"

#: The delivery journal the plugin appends to (its worktree-relative default).
EVENTS_ENV = "FINOPS_AIO_CONTEXT_EVENTS"

#: A request at/above this miss count is a FULL-CONTEXT miss — the defect's signature.
BIG_MISS_TOKENS = 50_000

#: A delivery event older than this does not classify a request (the join is a window
#: heuristic; a stale attach from a much earlier turn must not lend its cohort).
_JOIN_WINDOW_MS = 30 * 60 * 1000

#: The journal each report appends to (append-only; a measurement is never rewritten).
REPORT_JOURNAL_DEFAULT = (
    Path(__file__).resolve().parent.parent
    / "experiments" / "results" / "control" / "session_cache_reports.jsonl"
)

COHORT_ORDER = ("refresh", "compaction", "continuation", "unclassified")


def _default_db() -> Path:
    return Path(
        os.environ.get(DB_ENV) or Path.home() / ".local/share/opencode/opencode.db"
    )


def _default_events() -> Path:
    env = os.environ.get(EVENTS_ENV)
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / ".opencode" / "aio-context-events.jsonl"


def _blank_cohort() -> dict:
    return {"requests": 0, "hit_tokens": 0, "miss_tokens": 0, "big_misses": 0}


def _finish_cohort(bucket: dict, *, big_miss_tokens: int) -> dict:
    total = bucket["hit_tokens"] + bucket["miss_tokens"]
    bucket["miss_rate"] = (bucket["miss_tokens"] / total) if total else None
    bucket["big_miss_threshold"] = big_miss_tokens
    return bucket


def _usage_of(message: dict) -> tuple[int, int] | None:
    """(hit, miss) for ONE assistant message, or None when no completed sample exists.

    ``tokens.total`` zero (or absent) is the runtime's pending block — an unfinished request
    must never be counted as a full miss.
    """
    tokens = message.get("tokens") or {}
    total = tokens.get("total") or 0
    if not total:
        return None
    cache = tokens.get("cache") or {}
    hit = int(cache.get("read") or 0)
    miss = int(tokens.get("input") or 0)
    if hit + miss <= 0:
        return None
    # Defensive normalization: if a provider reported input INCLUSIVE of cache reads, the
    # cache-hit portion must not be double-counted as a miss.
    output = int(tokens.get("output") or 0)
    reasoning = int(tokens.get("reasoning") or 0)
    if miss + hit + output + reasoning > total:
        miss = max(total - hit - output - reasoning, 0)
    return hit, miss


def _read_events(path: Path) -> dict[str, list[dict]]:
    """Delivery events per session, ordered by time. A missing/unreadable journal is an
    empty map — cohorts fall back to ``unclassified`` with a note, never an invented kind."""
    per_session: dict[str, list[dict]] = {}
    if not path.is_file():
        return per_session
    with contextlib.suppress(OSError):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue  # a torn write is skipped, never fatal
            if not isinstance(event, dict) or event.get("schema") != "aio-context-event/v1":
                continue
            surface = str(event.get("surface") or "")
            if surface not in ("chat.message", "messages.transform"):
                continue  # the compaction hook's event is not a conversation delivery
            session = str(event.get("session") or "").strip()
            at = _ms(event.get("at"))
            if not session or at is None:
                continue
            per_session.setdefault(session, []).append(
                {"at": at, "kind": str(event.get("kind") or ""), "surface": surface}
            )
    for events in per_session.values():
        events.sort(key=lambda item: item["at"])
    return per_session


def _ms(value: object) -> int | None:
    """ISO-8601 (the plugin's journal) → epoch milliseconds; None when unparseable."""
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def _select_sessions(db: Path, *, session_ids: list[str], recent: int, everything: bool) -> list[str]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        if session_ids:
            return session_ids
        if everything:
            rows = con.execute("SELECT id FROM session ORDER BY time_updated DESC").fetchall()
            return [row[0] for row in rows]
        rows = con.execute(
            "SELECT id FROM session ORDER BY time_updated DESC LIMIT ?", (max(recent, 1),)
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        con.close()


def _load_session(db: Path, session_id: str) -> list[dict]:
    """Every message of one session, time-ordered, with its parsed data.

    Both roles are needed: assistant messages carry the usage being measured, and user
    messages give the per-turn timeline the attach join is anchored on.
    """
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT id, time_created, data FROM message WHERE session_id = ? "
            "ORDER BY time_created, id",
            (session_id,),
        ).fetchall()
    finally:
        con.close()
    messages: list[dict] = []
    for message_id, created, data in rows:
        try:
            parsed = json.loads(data)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(parsed, dict) or parsed.get("role") not in ("user", "assistant"):
            continue
        messages.append({"id": message_id, "created": int(created or 0), "data": parsed})
    return messages


def _classify_session(messages: list[dict], events: list[dict]) -> list[dict]:
    """One row per measured request: (created, hit, miss, cohort, detail).

    The attach join is anchored on the per-turn USER message: an attach is written just
    before its turn's user message is saved, so the turn's delivery event is the last
    ``chat.message`` event in (previous user message, this user message]. Every request of
    the turn — including tool-loop steps — inherits that turn's cohort. A request whose
    turn carries no attach (the post-compaction synthetic continuation, a restored message,
    legacy history) falls back to the first ``messages.transform`` append in its own window.
    """
    rows: list[dict] = []
    summary_positions = [
        index
        for index, message in enumerate(messages)
        if message["data"].get("mode") == "compaction" or message["data"].get("summary") is True
    ]
    post_compaction: set[int] = set()
    for position in summary_positions:
        for later in range(position + 1, len(messages)):
            if messages[later]["data"].get("role") == "assistant":
                post_compaction.add(later)  # the first assistant request after the summary
                break
    user_positions = [
        index for index, message in enumerate(messages) if message["data"].get("role") == "user"
    ]
    for index, message in enumerate(messages):
        if message["data"].get("role") != "assistant":
            continue
        usage = _usage_of(message["data"])
        if usage is None:
            continue
        hit, miss = usage
        if index in summary_positions:
            cohort = "compaction"
            detail = "summary generation"
        elif index in post_compaction:
            cohort = "compaction"
            detail = "post-compaction request"
        elif events:
            created = message["created"]
            next_created = messages[index + 1]["created"] if index + 1 < len(messages) else None
            turn_users = [position for position in user_positions if position < index]
            attaches: list[dict] = []
            if turn_users:
                user_position = turn_users[-1]
                user_created = messages[user_position]["created"]
                earlier_users = [position for position in turn_users if position < user_position]
                lower = messages[earlier_users[-1]]["created"] if earlier_users else user_created - _JOIN_WINDOW_MS
                attaches = [
                    event
                    for event in events
                    if event["surface"] == "chat.message"
                    and lower < event["at"] <= user_created
                ]
            appends = [
                event
                for event in events
                if event["surface"] == "messages.transform"
                and created < event["at"]
                and (next_created is None or event["at"] < next_created)
            ]
            kind = attaches[-1]["kind"] if attaches else (appends[0]["kind"] if appends else "")
            if kind == "refresh":
                cohort, detail = "refresh", "new observation"
            elif kind == "continuation":
                cohort, detail = "continuation", "unchanged snapshot"
            elif kind == "unavailable":
                cohort, detail = "continuation", "capsule unavailable"
            else:
                cohort, detail = "unclassified", "no delivery event joined"
        else:
            cohort, detail = "unclassified", "no delivery journal"
        rows.append(
            {
                "created": message["created"],
                "hit": hit,
                "miss": miss,
                "cohort": cohort,
                "detail": detail,
                "summary": index in summary_positions,
            }
        )
    return rows


def build_report(
    db_path: Path,
    events_path: Path,
    *,
    session_ids: list[str],
    recent: int,
    everything: bool,
    big_miss_tokens: int = BIG_MISS_TOKENS,
) -> dict:
    events = _read_events(events_path)
    selected = _select_sessions(db_path, session_ids=session_ids, recent=recent, everything=everything)
    cohorts = {name: _blank_cohort() for name in COHORT_ORDER}
    sessions: list[dict] = []
    unreadable: list[str] = []
    for session_id in selected:
        try:
            messages = _load_session(db_path, session_id)
        except sqlite3.Error:
            unreadable.append(session_id)
            continue
        rows = _classify_session(messages, events.get(session_id, []))
        if not rows:
            continue
        session_hit = sum(row["hit"] for row in rows)
        session_miss = sum(row["miss"] for row in rows)
        session_big = sum(1 for row in rows if row["miss"] >= big_miss_tokens)
        total = session_hit + session_miss
        sessions.append(
            {
                "session_id": session_id,
                "requests": len(rows),
                "hit_tokens": session_hit,
                "miss_tokens": session_miss,
                "miss_rate": (session_miss / total) if total else None,
                "big_misses": session_big,
            }
        )
        for row in rows:
            bucket = cohorts[row["cohort"]]
            bucket["requests"] += 1
            bucket["hit_tokens"] += row["hit"]
            bucket["miss_tokens"] += row["miss"]
            if row["miss"] >= big_miss_tokens:
                bucket["big_misses"] += 1

    for name in COHORT_ORDER:
        _finish_cohort(cohorts[name], big_miss_tokens=big_miss_tokens)
    overall_hit = sum(session["hit_tokens"] for session in sessions)
    overall_miss = sum(session["miss_tokens"] for session in sessions)
    overall_total = overall_hit + overall_miss

    notes: list[str] = []
    if not events_path.is_file():
        notes.append(
            f"no delivery journal at {events_path}: refresh/continuation cohorts are "
            "unavailable (pre-repair traffic); compaction + overall are DB-measured"
        )
    if unreadable:
        notes.append(f"unreadable sessions skipped: {', '.join(unreadable)}")
    if not sessions:
        notes.append("no measured (completed-usage) requests in the selected sessions")

    return {
        "schema": SCHEMA_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db": str(db_path),
        "events": str(events_path),
        "big_miss_threshold": big_miss_tokens,
        "formula": "sum(miss_tokens) / (sum(hit_tokens) + sum(miss_tokens))",
        "sessions": sessions,
        "cohorts": cohorts,
        "overall": {
            "requests": sum(session["requests"] for session in sessions),
            "hit_tokens": overall_hit,
            "miss_tokens": overall_miss,
            "miss_rate": (overall_miss / overall_total) if overall_total else None,
            "big_misses": sum(session["big_misses"] for session in sessions),
        },
        "notes": notes,
    }


def _append_journal(report: dict) -> None:
    path = Path(os.environ.get("FINOPS_SESSION_CACHE_JOURNAL") or REPORT_JOURNAL_DEFAULT)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False) + "\n")


def _render_human(report: dict) -> str:
    lines: list[str] = []
    overall = report["overall"]
    sessions = report["sessions"]
    lines.append(
        f"session cache report — {len(sessions)} session(s), {overall['requests']} measured "
        f"request(s) · big-miss threshold {report['big_miss_threshold']:,} tokens"
    )
    if overall["miss_rate"] is None:
        lines.append("  no measured requests — nothing to report (never a fabricated rate)")
    else:
        lines.append(
            f"  miss rate: {overall['miss_rate'] * 100:.2f}%  "
            f"(miss {overall['miss_tokens']:,} / hit {overall['hit_tokens']:,} + miss "
            f"{overall['miss_tokens']:,}) · full-context misses: {overall['big_misses']}"
        )
    lines.append("")
    header = f"  {'cohort':<14}{'requests':>9}{'hit tokens':>14}{'miss tokens':>14}{'miss rate':>11}{'big misses':>12}"
    lines.append(header)
    for name in COHORT_ORDER:
        bucket = report["cohorts"][name]
        rate = "—" if bucket["miss_rate"] is None else f"{bucket['miss_rate'] * 100:.2f}%"
        lines.append(
            f"  {name:<14}{bucket['requests']:>9,}{bucket['hit_tokens']:>14,}"
            f"{bucket['miss_tokens']:>14,}{rate:>11}{bucket['big_misses']:>12,}"
        )
    lines.append("")
    lines.append("  sessions:")
    for session in sessions:
        rate = "—" if session["miss_rate"] is None else f"{session['miss_rate'] * 100:.2f}%"
        lines.append(
            f"    {session['session_id']}  {session['requests']:>5} req  {rate:>7}  "
            f"{session['big_misses']:>4} big misses"
        )
    for note in report["notes"]:
        lines.append(f"  note: {note}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics session cache-report",
        description="Join the AIO capsule delivery journal with the opencode session DB and "
        "report the token-weighted provider cache-miss rate "
        "(sum(miss)/sum(hit+miss)), grouped by refresh / compaction / continuation.",
    )
    parser.add_argument("--db", default=None, help=f"opencode session db (default: {_default_db()})")
    parser.add_argument(
        "--events",
        default=None,
        help=f"the plugin delivery journal (default: {_default_env_display()})",
    )
    parser.add_argument(
        "--session",
        action="append",
        default=[],
        help="session id to measure (repeatable; default: the most recent sessions)",
    )
    parser.add_argument("--recent", type=int, default=5, help="recent sessions to measure (default: 5)")
    parser.add_argument("--all", action="store_true", help="measure every session in the db")
    parser.add_argument(
        "--big-miss",
        type=int,
        default=BIG_MISS_TOKENS,
        help=f"the full-context-miss threshold (default: {BIG_MISS_TOKENS:,})",
    )
    parser.add_argument("--json", action="store_true", help=f"emit {SCHEMA_ID} JSON")
    parser.add_argument("--no-journal", action="store_true", help="skip the journal append")
    return parser


def _default_env_display() -> str:
    return os.environ.get(EVENTS_ENV) or str(_default_events())


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db_path = Path(args.db) if args.db else _default_db()
    if not db_path.is_file():
        print(f"session cache report: no session db at {db_path}", file=sys.stderr)
        return 2
    events_path = Path(args.events) if args.events else _default_events()

    try:
        report = build_report(
            db_path,
            events_path,
            session_ids=[str(session).strip() for session in args.session if str(session).strip()],
            recent=args.recent,
            everything=args.all,
            big_miss_tokens=max(int(args.big_miss), 0),
        )
    except sqlite3.Error as error:
        print(f"session cache report: unreadable session db: {error}", file=sys.stderr)
        return 2

    if not args.no_journal:
        with contextlib.suppress(OSError):
            _append_journal(report)

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(_render_human(report))
    return 0 if report["overall"]["requests"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
