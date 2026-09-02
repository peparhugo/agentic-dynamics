#!/usr/bin/env python3
"""Drain the control outbox to empty — the operator's recovery command (``control_db_evidence`` e2).

    agentic-dynamics control drain-outbox            # human report
    agentic-dynamics control drain-outbox --json     # machine report

The outbox's at-least-once delivery works in the run path (verified 2026-09-02: the followups
run's terminal write delivered all 68 rows at ``scripts/run_workflow.py:_control_terminal_write``
— that drain is NOT rebuilt here). But when the knowledge stream was down at the moment of a
terminal write, the rows it owed stayed ``pending`` in the table, and before this command there
was NO operator-visible way to deliver them once the stream returned: the only drain call in the
codebase lived inside the run path, and it ran once, at the moment the run ended.

This script is that missing recovery path — a thin CLI over the SAME
:class:`~agentic_dynamics.control.outbox.OutboxPublisher` the run path uses, with the SAME
authorization posture (``_authorized_kb_write()`` for the duration of the drain). It does not
re-implement delivery; it re-runs it on demand. What it adds is honest reporting: the command
prints BOTH the pass-level accounting (``drained`` — delivered/skipped/retried/dead/stream_error
from :meth:`OutboxPublisher.drain`) AND the table-level state before and after (``outbox_before``
/ ``outbox_after`` — pending/delivered/dead from :func:`outbox.summarize`), so an operator can
see not just "the pass delivered N" but "the obligation is now discharged / still pending".

Exit codes:

* ``0`` — the drain ran and a report was produced. A report whose ``drained.stream_error`` is
  set is still a produced report: the rows honestly remain ``pending`` (visible in
  ``outbox_after.pending``) for the next drain — this command never lies that a drain that could
  not reach the stream emptied the table.
* ``3`` — there is no control database to drain (mirrors ``control status``'s exit for a missing
  control plane; this command must never CREATE one, because an outbox that does not exist has
  nothing in it to owe).
* ``2`` — an argument or database error refused the drain.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: F401  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: F401

from agentic_dynamics.control import outbox as ob  # noqa: E402
from agentic_dynamics.control.control_db import (  # noqa: E402
    ControlDB,
    ControlDBError,
    resolve_db_path,
)
from agentic_dynamics.knowledge.knowledge_ingestion import _authorized_kb_write  # noqa: E402

#: Schema tag on the machine report, so a consumer can tell what document it received.
DRAIN_SCHEMA = "control-drain-outbox/v1"

#: Exit code for "no control database to drain" — mirrors ``control status``.
EXIT_NO_CONTROL_DB = 3

#: Exit code for an argument/database refusal.
EXIT_REFUSED = 2


def run_drain(
    db: ControlDB,
    *,
    connect: Callable[[], Any] | None = None,
    publish: Callable[..., Any] | None = None,
    policy: Any | None = None,
    limit: int | None = None,
    artifact_dir: Path | str | None = None,
    registry_path: Path | str | None = None,
    checkpoint_key: str | None = None,
    authorized: bool = True,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Drain the outbox through the real publisher; return the honest report document.

    Every stream-facing seam is injectable (the same parameters
    :class:`~agentic_dynamics.control.outbox.OutboxPublisher` accepts) so the command's reporting
    contract is provable without a live Redis — the operator path and the test path differ only
    in what they inject, never in the reporting code. The authorization posture is the run path's
    own: the drain is wrapped in ``_authorized_kb_write()`` and the publisher is ``authorized``,
    exactly like ``_control_terminal_write``, so an operator drain emits what a run's terminal
    drain would have.

    The report carries the pass accounting and the table state BOTH before and after, because the
    two answer different questions and only both are honest: ``drained`` says what THIS pass did;
    ``outbox_after.pending`` says what the table still owes. A drain that could not reach the
    stream reports ``drained.stream_error`` and ``outbox_after.pending > 0`` together — never a
    delivered count that implies delivery happened.
    """
    before = ob.summarize(db).to_dict()
    with _authorized_kb_write():
        report = ob.OutboxPublisher(
            db,
            connect=connect,
            publish=publish,
            policy=policy,
            artifact_dir=artifact_dir,
            registry_path=registry_path,
            checkpoint_key=checkpoint_key,
            authorized=authorized,
            log=log,
        ).drain(limit=limit)
    after = ob.summarize(db).to_dict()
    return {
        "schema": DRAIN_SCHEMA,
        "control_db": str(db.path),
        "drained": report.to_dict(),
        "outbox_before": before,
        "outbox_after": after,
    }


def _human(doc: dict[str, Any]) -> str:
    """A compact operator-readable rendering of the drain report (the glance, not the record)."""
    drained = doc["drained"]
    after = doc["outbox_after"]
    if drained.get("stream_error"):
        line = (
            f"outbox: stream unreachable ({drained['stream_error']}) — "
            f"nothing delivered, {after['pending']} row(s) stay pending for the next drain"
        )
    else:
        line = (
            f"outbox: delivered {drained['delivered']} · skipped {drained['skipped']} · "
            f"retried {drained['retried']} · dead {drained['dead']} "
            f"| table now: pending {after['pending']} · delivered {after['delivered']} · "
            f"dead {after['dead']}"
        )
    if after["dead_event_ids"]:
        line += f"\noutbox: DEAD ids — {', '.join(after['dead_event_ids'])}"
    return line


def _error_envelope(message: str, *, db_path: str) -> dict[str, object]:
    """The payload emitted when there is no control database."""
    return {
        "schema": DRAIN_SCHEMA,
        "error": "control_db_unavailable",
        "detail": message,
        "control_db": db_path,
    }


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface."""
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics control drain-outbox",
        description=(
            "Deliver every eligible pending outbox row to the knowledge stream (the operator "
            "recovery drain) and report delivered/dead/pending honestly."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable report instead of the human summary",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="explicit control database path (default: $FINOPS_CONTROL_DB, else "
        "experiments/results/control/control.db)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="deliver at most N pending rows this pass (default: all eligible)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point: open the control db (never create it) and drain the outbox."""
    args = build_parser().parse_args(argv)

    path = resolve_db_path(args.db)
    if not path.exists():
        envelope = _error_envelope(
            f"no control database at {path} — a drain command never creates one",
            db_path=str(path),
        )
        if args.json:
            print(json.dumps(envelope, indent=2, ensure_ascii=False))
        else:
            print(f"control drain-outbox: {envelope['detail']}", file=sys.stderr)
        return EXIT_NO_CONTROL_DB

    try:
        with ControlDB.open(args.db) as db:
            doc = run_drain(db, limit=args.limit)
    except (ControlDBError, OSError, ValueError) as exc:
        envelope = _error_envelope(str(exc), db_path=str(args.db or ""))
        if args.json:
            print(json.dumps(envelope, indent=2, ensure_ascii=False))
        else:
            print(f"control drain-outbox: {exc}", file=sys.stderr)
        return EXIT_REFUSED

    if args.json:
        print(json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=False))
    else:
        print(_human(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
