"""decision_record.py — the decision-record command (``agentic-dynamics decision record``).

The s2a deliverable of the ``self_knowledge_layer`` wave (design
``docs/designs/proposed/self_knowledge_layer.md``): records a decision at the moment of
decision — what was decided, why, and the alternatives weighed — through the s2a decision
record type (:mod:`agentic_dynamics.knowledge.decision_ingestion`). A decision IS an
observation with intent: the record is observation-family (ADVISORY ``[H]``, org-root scope),
produced by the AIO and visible to the controller + AIO, never resolved by cell agents.

    agentic-dynamics decision record --what "park the fleet" \\
        --why "lane is dormant and burning ~$1.1/hr" \\
        --alternatives "keep it live, promote it" --category park

The command is a thin CLI shell over :func:`decision_ingestion.record_decision` — the emission
seam that writes the durable per-record artifact and publishes the pointer event, rerun-safe
and best-effort (an identical re-record is a no-op; a producer failure is a warning, never a
crash — the durable record still lands). This script owns only argument parsing, the
decision-payload assembly from flags, and the human/machine report.

``--what`` is the decision's subject (required — a decision with no subject cannot be
registered); ``--category`` is its retrieval axis (required; canonical values park/model/name/
scope, open by design). ``--alternatives`` is a comma-separated list of the alternatives
weighed (repeatable). ``--decided-at`` defaults to the decision moment (now, UTC ISO) — pin it
to make a re-record a rerun-safe no-op. ``--run-id`` / ``--candidate-sha`` bind the record to
the run/candidate a permanence decision acts on (the s2b verified-command emissions).

Exit codes: 0 on every completed record — a producer failure (downed knowledge stream) is a
WARNING, never a crash: the durable record still lands and ``--json`` reports
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

from agentic_dynamics.knowledge import decision_ingestion as di  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics decision record",
        description="Record a decision at the moment of decision: what was decided, why, and "
        "the alternatives weighed (a decision IS an observation with intent).",
    )
    parser.add_argument(
        "--what",
        required=True,
        help="the decision's subject — what was decided (folded into the record's identity, so "
        "an identical re-record with the same --decided-at is a rerun-safe no-op)",
    )
    parser.add_argument(
        "--why",
        default="",
        help="the rationale for the decision (free text)",
    )
    parser.add_argument(
        "--alternatives",
        action="append",
        default=[],
        metavar="A[,B...]",
        help="an alternative that was weighed (comma-separated; repeatable)",
    )
    parser.add_argument(
        "--category",
        required=True,
        help="the decision's retrieval category — canonical values: "
        + ", ".join(di.DECISION_CATEGORIES)
        + " (open by design)",
    )
    parser.add_argument(
        "--decided-at",
        default=datetime.now(timezone.utc).isoformat(),
        help="when the decision was made, ISO-8601 (default: now, UTC) — pin it to make a "
        "re-record a rerun-safe no-op",
    )
    parser.add_argument(
        "--actor",
        default=di.ACTOR,
        help=f"who recorded the decision (default: {di.ACTOR!r}; the s2b verified-command "
        "emissions record 'verified_command')",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="the run the decision is bound to (when the decision acts on a run)",
    )
    parser.add_argument(
        "--candidate-sha",
        default="",
        help="the candidate sha the decision is bound to (when the decision acts on a candidate)",
    )
    parser.add_argument(
        "--repository-id",
        default=di.REPOSITORY_ID,
        help=f"repository identity folded into entity_id (default: {di.REPOSITORY_ID!r})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable decision-record/v1 report instead of the human summary",
    )
    return parser


def _alternatives(args_values: list[str]) -> list[str]:
    """Split comma-separated alternative groups into the ordered list, stripped."""
    out: list[str] = []
    for group in args_values:
        for item in group.split(","):
            item = item.strip()
            if item:
                out.append(item)
    return out


def _report(result: di.DecisionRecordResult) -> dict:
    """The machine report: what the record holds, plus its durable identity."""
    return {
        "schema": "decision-record/v1",
        "status": result.status,
        "what": json.loads(result.record.text).get("what"),
        "category": json.loads(result.record.text).get("category"),
        "decided_at": json.loads(result.record.text).get("decided_at"),
        "actor": json.loads(result.record.text).get("actor"),
        "knowledge_id": result.record.knowledge_id,
        "entity_id": result.record.entity_id,
        "artifact": str(result.artifact_path),
        "entry_id": result.entry_id,
        "warnings": list(result.warnings),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    decision = {
        "what": args.what,
        "why": args.why,
        "alternatives": _alternatives(args.alternatives),
        "category": args.category,
        "decided_at": args.decided_at,
        "actor": args.actor,
        "run_id": args.run_id,
        "candidate_sha": args.candidate_sha,
    }
    try:
        result = di.record_decision(decision, repository_id=args.repository_id)
    except ValueError as exc:
        # A decision with no what / no category / no decided_at is a caller error, not a record.
        print(f"decision record: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(_report(result), indent=2))
    else:
        payload = json.loads(result.record.text)
        what = payload.get("what")
        category = payload.get("category")
        actor = payload.get("actor")
        kid = result.record.knowledge_id
        status = result.status
        if status == "no-op":
            print(f"[decision-record] {what} [{category}]: already recorded (no-op — {kid[:12]})")
        elif status == "degraded":
            print(
                f"[decision-record] {what} [{category}]: record written to "
                f"{result.artifact_path} but the event was NOT published — re-run once the "
                f"knowledge stream is back (knowledge_id {kid[:12]})"
            )
        else:
            event = f", event {result.entry_id}" if result.entry_id else ""
            print(
                f"[decision-record] {what} [{category}] by {actor}: recorded "
                f"(knowledge_id {kid[:12]} -> {result.artifact_path.name}{event})"
            )
    for warning in result.warnings:
        print(f"[decision-record] warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
