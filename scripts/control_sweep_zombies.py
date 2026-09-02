#!/usr/bin/env python3
"""Sweep zombie ``running`` control runs to ``CANCELLED`` (``control_db_evidence`` e2).

    agentic-dynamics control sweep-zombies                # cancel every stale run
    agentic-dynamics control sweep-zombies --dry-run      # preview, cancel nothing
    agentic-dynamics control sweep-zombies --json         # machine report

A killed orchestrator leaves its run's control row dangling in ``running`` forever (proven
2026-09-02: two killed runs needed manual cancellation via ``transition_run`` — see the deep
review). That dangling row pollutes the packet's ``active_runs`` and, because every transition
bumps the control epoch, keeps inflating a counter that is supposed to describe real state
changes.

This command is the mechanical replacement for the manual cancellation. It finds ``running``
runs whose **run heartbeat** has expired (``last_seen_at`` older than the staleness window — the
heartbeat a live orchestrator writes via ``run_lifecycle.RunHeartbeatThread``) and transitions
each to ``CANCELLED`` with a reason naming the staleness evidence. Every transition goes through
:meth:`~agentic_dynamics.control.control_db.ControlDB.transition_run`, the same legitimate API
governed by :data:`~agentic_dynamics.control.control_db.ALLOWED_TRANSITIONS` the packet's
``safe_actions`` derive from — never raw SQL, so the append-only ``run_transitions`` log stays
the single honest history. The sweep is flag/transition-only in the supervisor sense: it never
steers a run with a fresh heartbeat, and it reports rather than steering anything else.

Liveness is three-valued (see ``control/run_lifecycle.py`` for the reasoning):

* ``live`` — heartbeat fresh: untouched.
* ``zombie`` — heartbeat expired: cancelled (or listed under ``would_cancel`` with ``--dry-run``).
* ``unknown`` — no heartbeat row at all: untouched and reported. Absence of evidence of life is
  not evidence of death; a run the sweep cannot judge is a run the sweep must not guess about.

Exit codes: ``0`` a sweep ran (even with zero cancellations); ``3`` no control database; ``2`` a
database refusal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: F401  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: F401

from agentic_dynamics.control.control_db import (  # noqa: E402
    ControlDB,
    ControlDBError,
    resolve_db_path,
)
from agentic_dynamics.control.run_lifecycle import (  # noqa: E402
    SWEEP_ACTOR,
    stale_after_s,
    sweep_zombie_runs,
)

#: Schema tag on the machine report.
SWEEP_SCHEMA = "control-zombie-sweep/v1"

EXIT_NO_CONTROL_DB = 3
EXIT_REFUSED = 2


def run_sweep(
    db: ControlDB,
    *,
    stale_after_minutes: int | None = None,
    actor: str = SWEEP_ACTOR,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run one sweep pass and return the report document (thin wrapper, JSON-ready)."""
    report = sweep_zombie_runs(
        db,
        stale_after_seconds=None if stale_after_minutes is None else stale_after_minutes * 60,
        actor=actor,
        dry_run=dry_run,
    )
    doc = report.to_dict()
    doc["schema"] = SWEEP_SCHEMA
    doc["control_db"] = str(db.path)
    doc["dry_run"] = bool(dry_run)
    doc["stale_after_seconds"] = stale_after_s() if stale_after_minutes is None else stale_after_minutes * 60
    return doc


def _human(doc: dict[str, Any]) -> str:
    """A compact operator-readable rendering of the sweep report."""
    lines: list[str] = []
    verb = "would cancel" if doc["dry_run"] else "cancelled"
    if doc["cancelled"] or doc["would_cancel"]:
        for entry in doc["cancelled"] + doc["would_cancel"]:
            lines.append(
                f"{verb}: {entry['run_id']} "
                f"({entry['from_state']} -> cancelled) — {entry['reason']}"
            )
    else:
        lines.append(f"zombie sweep: no stale running runs (examined {doc['examined']})")
    lines.append(
        f"  live {len(doc['live'])} · unknown {len(doc['unknown'])}"
        f" · examined {doc['examined']}"
    )
    for error in doc["errors"]:
        lines.append(f"  error: {error}")
    return "\n".join(lines)


def _error_envelope(message: str, *, db_path: str) -> dict[str, object]:
    return {
        "schema": SWEEP_SCHEMA,
        "error": "control_db_unavailable",
        "detail": message,
        "control_db": db_path,
    }


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface."""
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics control sweep-zombies",
        description=(
            "Transition stale 'running' control runs (expired heartbeat) to CANCELLED via the "
            "legitimate transition API; report live/unknown/zombie honestly."
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
        "--stale-after-min",
        type=int,
        default=None,
        help=f"staleness window in minutes (default: {stale_after_s() // 60}, from "
        f"FINOPS_RUN_STALE_S)",
    )
    parser.add_argument(
        "--actor",
        default=SWEEP_ACTOR,
        help=f"actor stamped on each cancellation (default: {SWEEP_ACTOR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report the runs the sweep would cancel without transitioning anything",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point: open the control db (never create it) and run one sweep pass."""
    args = build_parser().parse_args(argv)

    path = resolve_db_path(args.db)
    if not path.exists():
        envelope = _error_envelope(
            f"no control database at {path} — a sweep command never creates one",
            db_path=str(path),
        )
        if args.json:
            print(json.dumps(envelope, indent=2, ensure_ascii=False))
        else:
            print(f"control sweep-zombies: {envelope['detail']}", file=sys.stderr)
        return EXIT_NO_CONTROL_DB

    try:
        with ControlDB.open(args.db) as db:
            doc = run_sweep(
                db,
                stale_after_minutes=args.stale_after_min,
                actor=args.actor,
                dry_run=args.dry_run,
            )
    except (ControlDBError, OSError, ValueError) as exc:
        envelope = _error_envelope(str(exc), db_path=str(args.db or ""))
        if args.json:
            print(json.dumps(envelope, indent=2, ensure_ascii=False))
        else:
            print(f"control sweep-zombies: {exc}", file=sys.stderr)
        return EXIT_REFUSED

    if args.json:
        print(json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=False))
    else:
        print(_human(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
