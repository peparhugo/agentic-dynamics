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
import json
import subprocess
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

    # 1b ── persist the command's INTENT before the act (step 2e: recording is part of the
    # act). If this process dies between here and the commit, the row survives with
    # state=intent — an uncertain outcome made visible, never a vanished act.
    command = None
    if not args.dry_run:
        with ControlDB.open() as db:
            command = db.record_command_intent(
                "approve",
                actor="aio",
                rationale=args.reason,
                run_id=args.run_id,
                candidate_sha=args.candidate_sha,
                target_kind="gate",
                target_id=args.gate_id or f"{args.spec}/{args.phase}",
                idempotency_key=f"approve:{args.run_id}:{args.candidate_sha}",
                detail={
                    "gate_id": args.gate_id,
                    "spec": args.spec,
                    "phase": args.phase,
                    "operator": args.operator,
                },
            )

    # 2 ── write AND COMMIT the operator-signed artifact in the run's worktree. The resume
    # path requires the approval committed at HEAD (absent at the checkpoint commit); an
    # uncommitted artifact can never authorize, and the commit must land on the exact
    # candidate the approval names — a rewritten worktree refuses.
    try:
        artifact = _write_artifact(args)
        artifact_commit = ""
        if not args.dry_run:
            artifact_commit = _commit_artifact(args, artifact)

        # 3 ── record the approval in the control db (operator + candidate bound).
        if not args.dry_run:
            decision_record = {
                "schema": "approval-decision/v1",
                "purpose": "checkpoint",
                "run_id": args.run_id,
                "gate_id": args.gate_id,
                "candidate_sha": args.candidate_sha,
                "operator": args.operator,
                "date": _today(),
                "artifact": str(artifact),
                "artifact_commit": artifact_commit,
                "status": "approved",
            }
            with ControlDB.open() as db:
                approval = db.record_approval(
                    args.run_id,
                    gate_id=args.gate_id,
                    candidate_sha=args.candidate_sha,
                    operator=args.operator,
                    artifact_path=str(artifact),
                    purpose="checkpoint",
                    decision_json=json.dumps(decision_record, sort_keys=True),
                )
        else:
            approval = None

        # 4 ── emit the decision (verb=approve) so the AIO's approval is observable.
        emission = (
            _emit_approval_decision(
                args, command_id=getattr(command, "command_id", "") if command else ""
            )
            if not args.dry_run
            else {}
        )
    except Exception as exc:
        if command is not None:
            try:
                with ControlDB.open() as db:
                    db.complete_command(
                        command.command_id,
                        state="refused" if isinstance(exc, _ApproveRefusedError) else "failed",
                        receipt={"error": str(exc)[:400]},
                    )
            except Exception:  # the receipt write must never mask the refusal
                pass
        raise

    # 5 ── the durable receipt: the observed outcome, recorded at the moment of the act.
    if command is not None:
        with ControlDB.open() as db:
            db.complete_command(
                command.command_id,
                state="completed",
                receipt={
                    "approval_id": approval.approval_id if approval else "",
                    "artifact": str(artifact),
                    "artifact_commit": artifact_commit,
                },
            )

    print(
        f"approve: run {args.run_id} approved by {args.operator} "
        f"(candidate {args.candidate_sha[:12]})"
        + (f" — approval {approval.approval_id}" if approval else " — dry-run, nothing written")
        + (f" — committed {artifact_commit[:12]}" if artifact_commit else "")
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
    # Wave A4: the artifact binds EVERY field the contract validates — spec/phase (also in
    # the path, but the CONTENT must name them or a moved/renamed artifact would still read
    # as binding), the run, the gate, the candidate sha, and the candidate's TREE (immutable
    # content identity, not just the sha label).
    tree = ""
    try:
        tree = subprocess.run(
            ["git", "rev-parse", f"{args.candidate_sha}^{{tree}}"],
            cwd=workdir, capture_output=True, text=True, timeout=30,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        tree = ""
    if not args.dry_run:
        artifact.write_text(
            f"---\nstatus: accepted\n---\n\n# Approval\n\n"
            f"spec: {args.spec}\n"
            f"phase: {args.phase}\n"
            f"run: {args.run_id}\n"
            f"purpose: checkpoint\n"
            f"gate: {args.gate_id or '(the run approval gate)'}\n"
            f"candidate: {args.candidate_sha}\n"
            f"tree: {tree}\n"
            f"operator: {args.operator}\n"
            f"date: {_today()}\n"
            f"reason: {args.reason or 'operator approval'}\n"
        )
    return artifact


def _commit_artifact(args: argparse.Namespace, artifact: Path) -> str:
    """Commit the approval in the run's worktree; refuse unless HEAD is the bound candidate.

    The commit carries the operator's name (the signer is the act's author) and the resume
    path's contract checks it lands after the checkpoint commit and is absent at it. A HEAD
    that no longer matches the candidate the approval names refuses — approving a rewritten
    worktree would bind a signature to work nobody verified.
    """
    workdir = Path(args.workdir)

    def _git(*argv: str) -> str:
        run = subprocess.run(
            ["git", *argv], cwd=workdir, capture_output=True, text=True, timeout=60
        )
        if run.returncode != 0:
            raise _ApproveRefusedError(
                f"git {' '.join(argv)} failed in {workdir}: "
                f"{(run.stderr or '').strip()[:300]}"
            )
        return run.stdout.strip()

    head = _git("rev-parse", "HEAD")
    if not (head.startswith(args.candidate_sha) or args.candidate_sha.startswith(head)):
        raise _ApproveRefusedError(
            f"worktree HEAD {head[:12]} is not the candidate this approval binds "
            f"({args.candidate_sha[:12]}) — rebuild or rebind the run before approving"
        )
    # Wave A4 (commit isolation): the approval commit must contain ONLY the approval
    # artifact. A pre-existing staged change would ride along — the review's reproduction
    # showed a staged source edit included in the approval commit, which the checkpoint
    # then accepted. Refuse a dirty index outright.
    staged = _git("diff", "--cached", "--name-only")
    if staged.strip():
        raise _ApproveRefusedError(
            "the worktree index already has staged changes "
            f"({', '.join(staged.splitlines()[:5])}) — commit or unstage them before "
            "approving; an approval commit must contain ONLY its artifact"
        )
    try:
        rel = artifact.resolve().relative_to(workdir.resolve()).as_posix()
    except ValueError:
        raise _ApproveRefusedError(
            f"artifact {artifact} is outside the run worktree {workdir} — the resume "
            f"contract reads approvals from the worktree"
        ) from None
    _git("add", rel)
    _git(
        "-c", f"user.name={args.operator}",
        "-c", "user.email=operator@operators.local",
        "commit", "-m", f"[approval] {args.spec}/{args.phase} — approved by {args.operator}",
    )
    return _git("rev-parse", "HEAD")


def _emit_approval_decision(args: argparse.Namespace, *, command_id: str = "") -> dict:
    """Best-effort AIO decision emission (verb=approve) — never blocks the approval.

    Wave B5: ``why`` is the operator's true ``--reason``; ``command_id`` is the journal receipt
    this approval binds (the emitted decision carries the receipt the command journal recorded).
    """
    from agentic_dynamics.control import aio_emission

    decision = {
        "schema": "aio-decision/v1",
        "verb": "approve",
        "run_id": args.run_id,
        "gate_id": args.gate_id,
        "candidate_sha": args.candidate_sha,
        "operator": args.operator,
        "why": args.reason or "operator approval",
        "status": "approved",
    }
    if command_id:
        decision["command_id"] = command_id
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
