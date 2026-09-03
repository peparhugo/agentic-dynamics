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

The close ALSO appends the session's self-notes into the session-keyed reflection series (the
s6a deliverable of the same wave, ``reflection_ingestion.append_reflection``): the reflection
seed the s1a type names lands as a ``reflection`` record — one entry per session, never
overwriting a prior session's — so the series accumulates across closes for the next session to
contemplate. The append is default-on, rerun-safe (an identical re-close re-appends nothing),
and best-effort (a failed append is a warning, never a failed close); a session closed with NO
self-notes reflects nothing — the command reports ``no-notes`` rather than minting an empty
entry.

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
from typing import Any

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.knowledge import reflection_ingestion as ri  # noqa: E402
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
        help="the AIO's self-notes: what it got wrong this session — appended into the "
        "session-keyed reflection series as this session's reflection entry (s6a); a session "
        "with no self-notes reflects nothing",
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


def _report(result: si.SessionCloseResult, reflection: ri.ReflectionAppendResult) -> dict:
    """The machine report: what the close did, plus the record's durable identity.

    ``reflection`` is the s6a reflection-append half of the close. Its block names the
    append's ``status`` (``appended``/``no-op``/``degraded``/``no-notes``) and — when an entry
    was written — the reflection record's own durable identity. ``no-notes`` (a session with
    empty self-notes) carries ``null`` identities: nothing was derived, which is the honest
    report, never a fabricated entry id.
    """
    reflection_block: dict[str, Any] = {"status": reflection.status}
    if reflection.record is not None:
        reflection_block.update(
            {
                "knowledge_id": reflection.record.knowledge_id,
                "entity_id": reflection.record.entity_id,
                "artifact": str(reflection.artifact_path),
                "entry_id": reflection.entry_id,
            }
        )
    return {
        "schema": "session-close/v1",
        "status": result.status,
        "slug": result.record.logical_locator,
        "knowledge_id": result.record.knowledge_id,
        "entity_id": result.record.entity_id,
        "artifact": str(result.artifact_path),
        "entry_id": result.entry_id,
        "reflection": reflection_block,
        "warnings": list(result.warnings) + list(reflection.warnings),
    }


def _reflection_lines(reflection: ri.ReflectionAppendResult) -> list[str]:
    """The human reflection-half summary lines for the close report."""
    status = reflection.status
    if status == "no-notes":
        return ["[session-close] reflection: no self-notes — nothing reflected"]
    if reflection.record is None:
        # Only reachable on an unexpected derivation error (surfaced to stderr by main);
        # render a degraded line naming the failure rather than a fabricated identity.
        return ["[session-close] reflection: append degraded — see the warning above"]
    kid = reflection.record.knowledge_id
    if status == "no-op":
        return [f"[session-close] reflection: already reflected (no-op — {kid[:12]})"]
    if status == "degraded":
        return [
            f"[session-close] reflection: entry written to {reflection.artifact_path.name} but "
            f"the event was NOT published — re-run once the knowledge stream is back "
            f"(knowledge_id {kid[:12]})"
        ]
    event = f", event {reflection.entry_id}" if reflection.entry_id else ""
    return [
        f"[session-close] reflection: appended ({kid[:12]} -> "
        f"{reflection.artifact_path.name}{event})"
    ]


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

    # s6a — the close appends its self-notes into the session-keyed reflection series.
    # Default-on + best-effort: the spine close already validated slug/session_date, so an
    # append can only fail on a producer/store fault, which append_reflection degrades into
    # warnings itself; a genuinely unexpected derivation error is a warning, never a failed
    # close (the reflection must never cost the session its spine record).
    try:
        reflection = ri.append_reflection(session, repository_id=args.repository_id)
    except ValueError as exc:
        # Surfaced as a degraded append with the reason in `warnings` (printed below) — the
        # reflection must never cost the session its spine record.
        reflection = ri.ReflectionAppendResult(record=None, status="degraded", warnings=[str(exc)])

    if args.json:
        print(json.dumps(_report(result, reflection), indent=2))
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
        for line in _reflection_lines(reflection):
            print(line)
    for warning in list(result.warnings) + list(reflection.warnings):
        print(f"[session-close] warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
