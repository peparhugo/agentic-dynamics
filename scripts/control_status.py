#!/usr/bin/env python3
"""The ONE control packet, on the command line (``control_db_publication`` p4).

    agentic-dynamics control status            # human glance
    agentic-dynamics control status --json     # control-status/v1, the machine surface

This file is the *shell*. Every derivation lives in
:mod:`agentic_dynamics.control.control_status`, which the Control Room portal and the supervisor
import directly rather than shelling out — the same split the rest of the control plane uses
(``lease_watchdog.py`` over ``control.lease_watchdog``, ``supervise.py`` over
``control.supervisor``). What this script owns is exactly the impure part: opening the database
read-only, collecting the two out-of-band inputs (the checkout's HEAD sha, the fleet's worker
heartbeats), and printing.

Read-only, always. The packet is a *reader* of the control plane; it opens the database with
SQLite ``mode=ro`` via ``ControlDB.open_read_only``, so this command can never create, migrate,
or mutate the control state — not even by accident, and not even if a future edit here calls a
writer method (the handle refuses it). That matters more than it sounds: an observer that
auto-created an empty database would turn "the orchestrator has never run" into "there are no
runs", which is a lie an actor would act on.

Exit codes — the packet's own status line, so a caller can branch without parsing JSON:

* ``0`` — a packet was rendered.
* ``2`` — the rendered packet failed its own schema validation. This should be impossible; it
  exists so that a builder bug surfaces as a loud nonzero exit rather than as a subtly malformed
  packet an actor then reasons from.
* ``3`` — there is no control database to read. Distinct from "an empty packet", deliberately:
  a *missing control plane* and a *quiet control plane* call for opposite responses. The JSON
  emitted in this case is an error envelope, not a ``control-status/v1`` packet.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: F401  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: F401


from agentic_dynamics.control import control_status as cs  # noqa: E402
from agentic_dynamics.control.control_db import ControlDB, ControlDBError  # noqa: E402

#: Exit code for "no control database". Named rather than inline so the tests and any caller
#: branch on the same constant.
EXIT_NO_CONTROL_DB = 3

#: Exit code for "the packet we built does not satisfy its own schema" — a builder bug.
EXIT_INVALID_PACKET = 2

#: Where each successful packet read appends its observation line (remediation closed-loop,
#: decision f987cde9: a turn that skipped the packet is now visible, because the AIO's own
#: counter shows it did not read). Overridable via ``FINOPS_PACKET_READS_PATH`` for tests.
#: Append-only, best-effort — the read itself must never fail on the counter.
PACKET_READS_DEFAULT = ROOT / "experiments" / "results" / "control" / "packet_reads.jsonl"


def _append_packet_read(*, epoch: object, repo_head_sha: str, db_path: str) -> None:
    """Append one packet-read observation line. Raises on failure — callers catch.

    One line per invocation: ``{ts, schema, epoch, repo_head_sha, db, session_id, actor}``.
    The counter is the packet's own observation of itself (the CLI is ours), so it writes a
    side file — never the control database, which stays read-only for this command.

    The session/action identity (AIO remediation 2026-09-14): a GLOBAL count of reads cannot
    establish that a particular decision consumed a valid packet. ``session_id`` comes from
    the runtime's explicit identity (``FINOPS_SESSION_ID``) and ``actor`` from ``FINOPS_ACTOR``
    (default ``aio``) — so a consequential act's decision record can be matched to the packet
    observation by (session, actor, epoch), never by "there have been N reads in total".
    Absent identity the fields are ``""`` — recorded as absent, never fabricated.
    """
    from datetime import datetime, timezone

    counter_path = Path(
        os.environ.get("FINOPS_PACKET_READS_PATH") or PACKET_READS_DEFAULT
    )
    counter_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "schema": cs.SCHEMA_ID,
            "epoch": epoch,
            "repo_head_sha": repo_head_sha,
            "db": db_path,
            "session_id": os.environ.get("FINOPS_SESSION_ID", "") or "",
            "actor": os.environ.get("FINOPS_ACTOR", "aio") or "aio",
        },
        ensure_ascii=False,
    )
    with open(counter_path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _error_envelope(message: str, *, db_path: str) -> dict[str, object]:
    """The payload emitted when there is no control database.

    Carries ``schema`` so a consumer can tell what kind of document it received, and an explicit
    ``error`` key so it can never be mistaken for a packet with no runs. The Control Room's
    ``/api/projections`` route uses the same ``control_db_unavailable`` vocabulary (p3), kept
    identical here so one word means one thing across the control plane's surfaces.
    """
    return {
        "schema": cs.SCHEMA_ID,
        "error": "control_db_unavailable",
        "detail": message,
        "control_db": db_path,
    }


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface. Kept small: this command is read-only and has nothing to configure."""
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics control status",
        description="Render the ONE control packet (control-status/v1) from the control database.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable control-status/v1 packet instead of the human summary",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="explicit control database path (default: $FINOPS_CONTROL_DB, else "
        "experiments/results/control/control.db)",
    )
    parser.add_argument(
        "--failed-limit",
        type=int,
        default=cs.DEFAULT_FAILED_LIMIT,
        help=f"how many recent failed runs to carry (default: {cs.DEFAULT_FAILED_LIMIT}); "
        "truncation is reported in the packet's `degraded` list, never silently",
    )
    parser.add_argument(
        "--no-workers",
        action="store_true",
        help="skip the Redis worker-heartbeat read; the packet then records "
        "'workers were not observed' in `degraded` rather than claiming an empty unhealthy list",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="with --json, emit one line (no indentation) — for piping and for diffing turns",
    )
    parser.add_argument(
        "--no-counter",
        action="store_true",
        help="skip the packet-read counter append (tests and programmatic readers only — the "
        "AIO's contract requires the counter, so a turn that passes this flag has explaining "
        "to do)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point: collect the impure inputs, build the packet, print it, and exit."""
    args = build_parser().parse_args(argv)

    # `degraded` notes accumulate from the collectors below. Each one names a surface that could
    # not be read, so an empty result for that surface is never read as good news.
    degraded: list[dict[str, str]] = []

    # (1) The checkout's HEAD. Never fabricated — an unreadable git yields "" plus a note.
    repo_head_sha, git_error = cs.read_repo_head_sha()
    if git_error:
        degraded.append({"surface": "repo_head_sha", "reason": git_error})

    # (2) The fleet's worker heartbeats. `None` (not `{}`) means "not collected", which
    #     build_packet turns into its own note — the distinction the whole surface rests on.
    heartbeats: dict | None
    if args.no_workers:
        heartbeats = None
    else:
        heartbeats, redis_error = cs.read_worker_heartbeats()
        if redis_error:
            # Observed-and-failed is still not-observed: drop to None so the packet says so.
            heartbeats = None
            degraded.append({"surface": "unhealthy_workers", "reason": redis_error})

    try:
        # Read-only: this command is an observer of the control plane, never a writer.
        with ControlDB.open_read_only(args.db) as db:
            packet = cs.build_packet(
                db,
                repo_head_sha=repo_head_sha,
                heartbeats=heartbeats,
                failed_limit=args.failed_limit,
                degraded=degraded,
            )
    except ControlDBError as exc:
        envelope = _error_envelope(str(exc), db_path=str(args.db or ""))
        if args.json:
            print(json.dumps(envelope, indent=None if args.compact else 2, ensure_ascii=False))
        else:
            print(f"control status: {exc}", file=sys.stderr)
        return EXIT_NO_CONTROL_DB

    # Self-check. The builder and the validator are independent encodings of one contract, so a
    # failure here means one of them is wrong — which an actor downstream must never discover by
    # acting on a malformed packet. Printed to stderr so --json's stdout stays parseable.
    errors = cs.validate_packet(packet)

    # Packet-read counter (remediation closed-loop, decision f987cde9): every successful read
    # appends one observation line, so a turn that skipped the packet is visible to the
    # controller, the supervisor, and the AIO's own next session. Best-effort — the read itself
    # must never fail on the counter, and the packet's JSON surface is untouched.
    if not args.no_counter:
        # An unwritable counter must not make the packet unreadable.
        with contextlib.suppress(OSError):
            _append_packet_read(
                epoch=packet.get("control_epoch"),
                repo_head_sha=str(packet.get("repo_head_sha", "") or ""),
                db_path=str(args.db or ""),
            )

    if args.json:
        print(cs.packet_json(packet, indent=None if args.compact else 2))
    else:
        print(cs.format_packet(packet))

    if errors:
        for error in errors:
            print(f"control status: INVALID PACKET: {error}", file=sys.stderr)
        return EXIT_INVALID_PACKET
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
