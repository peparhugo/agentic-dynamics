"""session_open.py — the session OPEN command (``agentic-dynamics session open``).

The s1c deliverable of the ``self_knowledge_layer`` wave (design
``docs/designs/proposed/self_knowledge_layer.md``): opens a session by retrieving the LAST
session's close record and rendering it as the session's opening context — decisions (merged),
open threads, parked items, and the AIO's self-notes on what it got wrong. It is the read half
of the session spine: every session the AIO ends is closed (s1b ``session close``), so the next
session opens with its predecessor's posterior instead of a fresh prior. No prior close
renders a clear first-session bootstrap message.

The command is a thin CLI shell over :func:`session_ingestion.open_session` — the direct read
seam over the durable KB artifacts (the same store the close writes, filtered to the AIO's
org-root ``session/v1`` family). This script owns only argument parsing and the human/machine
report; the retrieval semantics (org-scoped direct read, deterministic "last" resolution) live
in the module's docstrings.

    agentic-dynamics session open                 # the last session's close as opening context
    agentic-dynamics session open --slug wt_selfk_s1b_close_writer   # one named session slot

``--slug`` is optional — the default read resolves the LAST session closed; naming a slug
resolves that session slot's most recent close instead. ``--json`` emits the machine
``session-open/v1`` report (status ``opened`` with the full record, or ``bootstrap``).

Exit codes: 0 on every completed open — the bootstrap state (no prior close) is the correct
first-session answer, never an error. 2 on a usage error.
"""

from __future__ import annotations

import argparse
import json
import sys

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.knowledge import session_ingestion as si  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics session open",
        description="Open a session: retrieve the last session's close record (decisions, "
        "open threads, parked items, self-notes) as this session's opening context. No prior "
        "close renders a clear first-session bootstrap message.",
    )
    parser.add_argument(
        "--slug",
        default="",
        help="the session slot to open (default: the LAST session closed — greatest "
        "session_date, deterministic tie-breaks)",
    )
    parser.add_argument(
        "--repository-id",
        default=si.REPOSITORY_ID,
        help=f"repository identity the org-root read filters on (default: {si.REPOSITORY_ID!r})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable session-open/v1 report instead of the human context",
    )
    return parser


def _report(result: si.SessionOpenResult) -> dict:
    """The machine report: what the open resolved, plus the record's durable identity."""
    payload = result.payload or {}
    return {
        "schema": "session-open/v1",
        "status": result.status,
        "slug": result.slug,
        "session_date": payload.get("session_date"),
        "waves_run": payload.get("waves_run", []),
        "merged": payload.get("merged", []),
        "parked": payload.get("parked", []),
        "open_threads": payload.get("open_threads", []),
        "self_notes": payload.get("self_notes", ""),
        "actor": "aio",
        "scope": si.aio_acl_scope(),
        "knowledge_id": result.knowledge_id,
        "entity_id": result.entity_id,
        "artifact": str(result.artifact_path) if result.artifact_path else None,
        "requested_slug": result.requested_slug,
        "candidates": result.candidates,
        "warnings": list(result.warnings),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = si.open_session(slug=args.slug, repository_id=args.repository_id)

    if args.json:
        print(json.dumps(_report(result), indent=2))
    else:
        print(si.render_opening_context(result))
    for warning in result.warnings:
        print(f"[session-open] warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
