"""reflect.py — the reflection READ command (``agentic-dynamics reflect --read``).

The s6b deliverable of the ``self_knowledge_layer`` wave (design
``docs/designs/proposed/self_knowledge_layer.md``): reads the accumulated reflection series and
renders it in order, so a session can contemplate across its predecessors. The reflection series
is the REFLEXIVE layer of the self-knowledge loop — what the AIO got wrong, what surprised it,
what it would change about its own process — and it accumulates across sessions: every session
close (s1b) appends its self-notes as one session-keyed ``reflection`` entry (s6a), never
overwriting a prior session's. This read command is the other half of that accumulation: a
session reads what the machine has reflected, in the order the sessions happened. The
accumulated reflections feed the next session's open context (s1c) and the belief seeds (s4c);
this command is where a session reads them.

The command is a thin CLI shell over :func:`reflection_ingestion.read_reflection_series` — the
direct read seam over the durable KB artifacts (the same store the append writes, filtered to
the AIO's org-root ``reflection/v1`` family) — and :func:`reflection_ingestion.render_reflection_series`.
This script owns only argument parsing and the human/machine report.

    agentic-dynamics reflect --read              # the accumulated series, in session order
    agentic-dynamics reflect                     # same read (read is the command's only operation)
    agentic-dynamics reflect --read --json       # the machine reflect/v1 report

An empty series renders a clear empty state — never an error (exit 0): no session has closed
with self-notes yet, which is the correct "nothing to contemplate across" answer, and a
layering anomaly (a ``reflection/v1`` artifact of this org that is not a readable AIO record)
is a warning on stderr, never part of the series.

Exit codes: 0 on every completed read. 2 on a usage error.
"""

from __future__ import annotations

import argparse
import json
import sys

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.knowledge import reflection_ingestion as ri  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics reflect",
        description="Read the accumulated reflection series: render every session's reflection "
        "entry in the order the sessions happened, so a session can contemplate across its "
        "predecessors. An empty series renders a clear empty state.",
    )
    parser.add_argument(
        "--read",
        action="store_true",
        help="read + render the accumulated reflection series — the command's only operation "
        "(read is also the default; the flag makes the s6b surface explicit)",
    )
    parser.add_argument(
        "--repository-id",
        default=ri.REPOSITORY_ID,
        help=f"repository identity the org-root read filters on (default: {ri.REPOSITORY_ID!r})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable reflect/v1 report instead of the human rendering",
    )
    return parser


def _report(result: ri.ReflectionReadResult, *, repository_id: str) -> dict:
    """The machine report: the resolved series, one entry per session, in chronological order.

    Each entry carries its content fields (from the payload) plus its durable identity (the
    ``knowledge_id`` the append addressed and the ``entity_id`` naming the session slot) so a
    machine reader can correlate the read with the artifacts behind it.
    """
    return {
        "schema": "reflect/v1",
        "status": result.status,
        "count": result.count,
        "actor": ri.ACTOR,
        "scope": ri.aio_acl_scope(repository_id),
        "entries": [
            {
                "session_date": payload.get("session_date"),
                "slug": payload.get("slug"),
                "self_notes": payload.get("self_notes", ""),
                "actor": payload.get("actor"),
                "scope": payload.get("scope"),
                "knowledge_id": path.stem,
                "entity_id": artifact.get("entity_id") or "",
                "artifact": str(path),
            }
            for path, artifact, payload in result.entries
        ],
        "warnings": list(result.warnings),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = ri.read_reflection_series(repository_id=args.repository_id)

    if args.json:
        print(json.dumps(_report(result, repository_id=args.repository_id), indent=2))
    else:
        print(ri.render_reflection_series(result))
    for warning in result.warnings:
        print(f"[reflect] warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
