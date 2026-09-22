#!/usr/bin/env python3
"""abandon_run.py — cancel stale ``promotable`` control runs (the missing abandon half).

A workflow run that finished with a verified candidate has exactly two terminal decisions:
PROMOTE it (``scripts/promote.py`` — merge the candidate onto the base) or ABANDON it (this
command — cancel the row). Until 2026-09-22 there was no command for the second decision:
``promotable`` rows could only be cancelled "by hand" through the transition API, so 38 of
them accumulated across the August/September experiment waves (the 2026-09-22 triage).

This rail is deliberately small and keeps the promote rail's invariants:

* it NEVER touches git. The candidate's durability is the ARCHIVE's business
  (``refs/experiments/<spec>/<run_id>`` on the canonical remote, pushed before abandonment);
* it transitions ``promotable -> cancelled`` through the control db's OWN enforced API, with
  the operator and a REQUIRED reason recorded on the transition;
* it REFUSES any row that is not ``promotable`` (a running/merged/failed/promoting row is not
  this command's business) and reports unknown run ids — refusals are reported, never silent;
* dry-run by DEFAULT; ``--apply`` writes.

Usage::

    python3 scripts/abandon_run.py --run-id run-x --run-id run-y --reason "..." [--apply]
    python3 scripts/abandon_run.py --spec prompt_branch_pilot --reason "..." [--apply]
    python3 scripts/abandon_run.py --all-stale --reason "..." [--apply]

Exit codes: ``0`` a pass ran; ``2`` a database refusal.
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
)

#: Schema tag on the machine report.
ABANDON_SCHEMA = "control-run-abandon/v1"

EXIT_REFUSED = 2


def run_abandon(
    db: Any,
    *,
    run_ids: tuple[str, ...] = (),
    spec: str = "",
    all_stale: bool = False,
    reason: str,
    operator: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Select the target rows and cancel them (or report what would be cancelled).

    Selection: explicit ``run_ids``; or every promotable row of one ``spec``; or every
    promotable row (``all_stale``). A refusal is per row, so one ineligible id in a batch
    never blocks the rest.
    """
    if run_ids:
        selected: list[Any] = [db.get_run(run_id) for run_id in run_ids]
    else:
        selected = list(db.runs(state="promotable", spec_name=spec or None))
    doc: dict[str, Any] = {
        "schema": ABANDON_SCHEMA,
        "control_db": str(getattr(db, "path", "")),
        "dry_run": bool(dry_run),
        "operator": operator,
        "reason": reason,
        "cancelled": [],
        "would_cancel": [],
        "refused": [],
        "missing": [],
    }
    for run in selected:
        if run is None:
            doc["missing"].append("(unknown run id)")
            continue
        state = run.state.value if hasattr(run.state, "value") else str(run.state)
        entry = {
            "run_id": run.run_id,
            "spec_name": run.spec_name,
            "from_state": state,
            "candidate_sha": run.candidate_sha,
        }
        if state != "promotable":
            entry["reason"] = (
                f"refused: the row is {state}, not promotable — this command cancels only "
                "promotable rows"
            )
            doc["refused"].append(entry)
            continue
        if dry_run:
            doc["would_cancel"].append(entry)
            continue
        db.transition_run(
            run.run_id,
            "cancelled",
            reason=f"abandoned by {operator}: {reason}",
            actor=operator,
        )
        doc["cancelled"].append(entry)
    return doc


def _human(doc: dict[str, Any]) -> str:
    verb = "would cancel" if doc["dry_run"] else "cancelled"
    lines: list[str] = []
    for entry in doc["cancelled"] + doc["would_cancel"]:
        lines.append(f"{verb}: {entry['run_id']} ({entry['spec_name']}) — {doc['reason'][:90]}")
    for entry in doc["refused"]:
        lines.append(f"refused: {entry['run_id']} — {entry['reason']}")
    if doc["missing"]:
        lines.append(f"missing: {len(doc['missing'])} unknown run id(s)")
    if not lines:
        lines.append("abandon: no promotable rows matched the selection")
    lines.append(
        f"  {verb} {len(doc['cancelled']) + len(doc['would_cancel'])} · "
        f"refused {len(doc['refused'])} · dry_run {doc['dry_run']}"
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Cancel stale promotable control runs (the abandon half of promote-or-abandon). "
            "Dry-run by default; --apply writes. Archive candidates to "
            "refs/experiments/<spec>/<run_id> BEFORE abandoning when their clones still exist."
        )
    )
    parser.add_argument("--run-id", action="append", default=[], help="cancel this run (repeatable)")
    parser.add_argument("--spec", default="", help="cancel every promotable run of this spec")
    parser.add_argument("--all-stale", action="store_true", help="cancel EVERY promotable run")
    parser.add_argument("--reason", required=True, help="why these runs are abandoned (recorded)")
    parser.add_argument("--operator", default="", help="the operator this abandonment carries")
    parser.add_argument("--db", default=None, help="control db path (default: the resolved one)")
    parser.add_argument("--apply", action="store_true", help="write the cancellations")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with ControlDB.open(args.db) as db:
            doc = run_abandon(
                db,
                run_ids=tuple(args.run_id),
                spec=args.spec,
                all_stale=bool(args.all_stale),
                reason=args.reason,
                operator=args.operator or "aio",
                dry_run=not args.apply,
            )
    except (ControlDBError, OSError, ValueError) as exc:
        envelope = {"schema": ABANDON_SCHEMA, "error": "abandon_refused", "detail": str(exc)}
        if args.json:
            print(json.dumps(envelope, indent=2, ensure_ascii=False))
        else:
            print(f"abandon: {exc}", file=sys.stderr)
        return EXIT_REFUSED

    if args.json:
        print(json.dumps(doc, indent=2, ensure_ascii=False))
    else:
        print(_human(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
