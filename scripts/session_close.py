"""session_close.py — the session CLOSE command (``agentic-dynamics session close``).

The s1b deliverable of the ``self_knowledge_layer`` wave (design
``docs/designs/proposed/self_knowledge_layer.md``): closes the current session by writing its
record through the s1a session-spine type (:mod:`agentic_dynamics.knowledge.session_ingestion`).
The record carries what ran (waves), what merged, what got parked, the open threads, and the
AIO's self-notes (what it got wrong — the reflection seed). Default-on at session end: the AIO's
operating cadence closes every session it opens, so the next session (s1c ``open``) can retrieve
its predecessor's posterior instead of starting from a fresh prior.

The command is a thin CLI shell over :func:`session_ingestion.close_session` — the emission seam
that writes the durable per-record artifact and publishes the pointer event, rerun-safe and
best-effort (see its docstring for the exact no-op + degraded semantics). This script owns only
argument parsing, the session-payload assembly from flags, and the human/machine report.

    agentic-dynamics session close --slug wt_selfk_s1b_close_writer \\
        --wave "self_knowledge_layer/s1a_session_record_type" \\
        --merged "2026-08-14_experiment-spec-and-compiler-design" \\
        --self-notes "I re-derived the wave verdict by grep instead of reading a record."

``--slug`` is the session's logical identity (required — a session with no name cannot be
registered); ``--session-date`` defaults to today (UTC). Every list field is repeatable and
optional: a session that ran nothing and parked nothing is still a session.

Exit codes: 0 on every completed close — a producer failure (downed knowledge stream) is a
WARNING, never a crash: the durable artifact still lands and ``--json`` reports
``status: degraded`` so the caller can re-run once the stream is back. 2 on a usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.knowledge import session_ingestion as si  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics session close",
        description="Close the current session: write its session-spine record into the KB "
        "(what ran, what merged, what parked, open threads, self-notes).",
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="the session's logical identity (e.g. wt_selfk_s1b_close_writer) — folded into "
        "the record's entity_id, so an identical re-close is a rerun-safe no-op",
    )
    parser.add_argument(
        "--session-date",
        default=datetime.now(timezone.utc).date().isoformat(),
        help="the session's own date YYYY-MM-DD (default: today, UTC)",
    )
    parser.add_argument(
        "--wave",
        action="append",
        default=[],
        metavar="WAVE",
        help="a wave that ran this session (repeatable, chronological)",
    )
    parser.add_argument(
        "--merged",
        action="append",
        default=[],
        metavar="ITEM",
        help="something that merged this session (repeatable)",
    )
    parser.add_argument(
        "--parked",
        action="append",
        default=[],
        metavar="ITEM",
        help="something parked this session (repeatable)",
    )
    parser.add_argument(
        "--open-thread",
        action="append",
        default=[],
        metavar="THREAD",
        help="an open thread carried into the next session (repeatable)",
    )
    parser.add_argument(
        "--self-notes",
        default="",
        help="the AIO's self-notes: what it got wrong this session (the reflection seed)",
    )
    parser.add_argument(
        "--repository-id",
        default=si.REPOSITORY_ID,
        help=f"repository identity folded into entity_id (default: {si.REPOSITORY_ID!r})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable session-close/v1 report instead of the human summary",
    )
    return parser


def _report(result: si.SessionCloseResult) -> dict:
    """The machine report: what the close did, plus the record's durable identity."""
    return {
        "schema": "session-close/v1",
        "status": result.status,
        "slug": result.record.logical_locator,
        "knowledge_id": result.record.knowledge_id,
        "entity_id": result.record.entity_id,
        "artifact": str(result.artifact_path),
        "entry_id": result.entry_id,
        "warnings": list(result.warnings),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    session = {
        "slug": args.slug,
        "session_date": args.session_date,
        "waves_run": args.wave,
        "merged": args.merged,
        "parked": args.parked,
        "open_threads": args.open_thread,
        "self_notes": args.self_notes,
    }
    try:
        result = si.close_session(session, repository_id=args.repository_id)
    except ValueError as exc:
        # A session with no slug / no session_date is a caller error, not a close to record.
        print(f"session close: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(_report(result), indent=2))
    else:
        status = result.status
        slug = result.record.logical_locator
        kid = result.record.knowledge_id
        if status == "no-op":
            print(f"[session-close] {slug}: already closed (no-op — {kid[:12]})")
        elif status == "degraded":
            print(
                f"[session-close] {slug}: record written to {result.artifact_path} but the "
                f"event was NOT published — re-run once the knowledge stream is back "
                f"(knowledge_id {kid[:12]})"
            )
        else:
            event = f", event {result.entry_id}" if result.entry_id else ""
            print(
                f"[session-close] {slug}: closed (knowledge_id {kid[:12]} -> "
                f"{result.artifact_path.name}{event})"
            )
    for warning in result.warnings:
        print(f"[session-close] warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
