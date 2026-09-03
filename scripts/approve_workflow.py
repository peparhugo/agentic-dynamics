"""Approve a gated workflow run (the A2 closure, authoring_product_aio Wave 3).

The AIO's approval path — the P0 controller act the packet's ``safe_actions``
offers for an ``awaiting_approval`` run. This command records the approval in
the control database (bound to the gate + the candidate sha + the operator),
writes the operator-signed approval artifact the resume path requires
(``approvals/<spec>/<phase>_approval.md``), and emits the decision through the
AIO emission seam (``verb=approve``) so the AIO's approvals are observable —
never a silent authority.

The operator name is REQUIRED: an approval with no approver is not an approval,
and the control db's ``record_approval`` makes "the machine approved itself" a
detectable condition (operator is the discriminator). The AIO carries the
controller's name; it never invents one.

Exit codes: 0 approved / 10 not awaiting (no approval needed) / 20 refused
(invalid run, wrong state, placeholder operator, no candidate) / 30 bad usage.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXIT_OK = 0
EXIT_NOT_AWAITING = 10
EXIT_REFUSED = 20
EXIT_USAGE = 30

#: Placeholder operator names that are never a real approval (mirrors the resume
#: path's placeholder check — a non-placeholder operator is REQUIRED).
PLACEHOLDER_OPERATORS = frozenset({"", "operator", "operator-test", "test", "aio", "AIO"})


def main() -> None:
    ap = argparse.ArgumentParser(description="Approve a gated workflow run")
    ap.add_argument("--run-id", required=True, help="the awaiting run's id (from control status --json)")
    ap.add_argument("--gate-id", default="", help="the approval gate id (when the run names one)")
    ap.add_argument("--candidate-sha", required=True, help="the candidate sha the approval binds to")
    ap.add_argument("--spec", required=True, help="the workflow spec name (for the artifact path)")
    ap.add_argument("--phase", required=True, help="the checkpoint phase (for the artifact path)")
    ap.add_argument("--operator", required=True,
                    help="who approves (the AIO carries the controller's name — never invented)")
    ap.add_argument("--reason", default="", help="why (recorded on the decision emission)")
    ap.add_argument("--workdir", default=str(ROOT),
                    help="the worktree holding approvals/ (default: the repo root)")
    ap.add_argument("--dry-run", action="store_true",
                    help="verify everything, write nothing, emit nothing")
    args = ap.parse_args()

    try:
        _run_approval(args)
    except _ApproveRefusedError as exc:
        print(f"approve: REFUSED — {exc}", file=sys.stderr)
        raise SystemExit(EXIT_REFUSED) from None
    except _NotAwaitingError as exc:
        print(f"approve: NOT AWAITING — {exc}", file=sys.stderr)
        raise SystemExit(EXIT_NOT_AWAITING) from None


class _ApproveRefusedError(Exception):
    """The approval cannot be recorded — refused with the evidence."""


class _NotAwaitingError(Exception):
    """The run is not in an awaiting state — no approval is needed or possible."""


def _run_approval(args: argparse.Namespace) -> None:
    from agentic_dynamics.control.control_db import ControlDB, RunState

    if args.operator in PLACEHOLDER_OPERATORS:
        raise _ApproveRefusedError(
            f"operator {args.operator!r} is a placeholder — an approval with no real "
            f"approver is not an approval; the AIO carries the controller's name"
        )
    if args.candidate_sha in ("", "deadbeef") or len(args.candidate_sha) < 7:
        raise _ApproveRefusedError(
            f"candidate_sha {args.candidate_sha!r} is not a real sha — the approval must "
            f"bind a real candidate"
        )

    # 1 ── the run exists and is genuinely awaiting.
    with ControlDB.open_read_only() as db:
        run = db.get_run(args.run_id)
        if run is None:
            raise _ApproveRefusedError(f"no run {args.run_id!r} in the control db")
        if run.state not in (RunState.AWAITING_APPROVAL, RunState.FAILED):
            # An awaiting run (or a failed run awaiting a resume decision) is approvable;
            # a promotable/published/merged run is not awaiting anything.
            raise _NotAwaitingError(
                f"run {args.run_id} is {run.state.value}, not awaiting_approval — "
                f"no approval is needed"
            )

    # 2 ── write the operator-signed artifact the resume path requires.
    artifact = _write_artifact(args)

    # 3 ── record the approval in the control db (operator + candidate bound).
    if not args.dry_run:
        with ControlDB.open() as db:
            approval = db.record_approval(
                args.run_id,
                gate_id=args.gate_id,
                candidate_sha=args.candidate_sha,
                operator=args.operator,
                artifact_path=str(artifact),
            )
    else:
        approval = None

    # 4 ── emit the decision (verb=approve) so the AIO's approval is observable.
    emission = _emit_approval_decision(args) if not args.dry_run else {}

    print(
        f"approve: run {args.run_id} approved by {args.operator} "
        f"(candidate {args.candidate_sha[:12]})"
        + (f" — approval {approval.approval_id}" if approval else " — dry-run, nothing written")
    )
    if emission:
        print(f"approve: decision emitted ({emission.get('observation_id', '')[:16]}…)")


def _write_artifact(args: argparse.Namespace) -> Path:
    """Write the operator-signed approval artifact the resume path checks for.

    Format per the runner's contract (workflow_runner.py): a REAL operator line +
    a real date; the artifact is committed by the operator (or the AIO on the
    controller's instruction) so its commit descends from the checkpoint phase.
    """
    workdir = Path(args.workdir)
    art_dir = workdir / "approvals" / args.spec
    art_dir.mkdir(parents=True, exist_ok=True)
    artifact = art_dir / f"{args.phase}_approval.md"
    if not args.dry_run:
        artifact.write_text(
            f"---\nstatus: accepted\n---\n\n# Approval\n\n"
            f"run: {args.run_id}\n"
             f"gate: {args.gate_id or '(the run approval gate)'}\n"
            f"candidate: {args.candidate_sha}\n"
            f"operator: {args.operator}\n"
            f"date: {_today()}\n"
            f"reason: {args.reason or 'operator approval'}\n"
        )
    return artifact


def _emit_approval_decision(args: argparse.Namespace) -> dict:
    """Best-effort AIO decision emission (verb=approve) — never blocks the approval."""
    from agentic_dynamics.control import aio_emission

    decision = {
        "schema": "aio-decision/v1",
        "verb": "approve",
        "run_id": args.run_id,
        "gate_id": args.gate_id,
        "candidate_sha": args.candidate_sha,
        "operator": args.operator,
        "reason": args.reason,
        "status": "approved",
    }
    try:
        return aio_emission.emit_decision(decision)
    except Exception as exc:  # best-effort by contract
        print(f"warning: approve decision emission failed ({exc}) — approval stands",
              file=sys.stderr)
        return {}


def _today() -> str:
    import datetime

    return datetime.date.today().isoformat()


if __name__ == "__main__":
    main()
