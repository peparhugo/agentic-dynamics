"""Promote a verified workflow candidate to main (P0-4, control-plane stabilization).

The ONLY path that updates ``main``. Workers, the master controller, and the workflow
engine never push — they produce candidates; this non-LLM command verifies and promotes.

The authority rules (the deep review's P0-4):
- execution produces a candidate, never an authoritative merge;
- the promoter refuses promotion when ANY gate evidence is missing, stale, or bound to
  a different candidate SHA;
- the promoter refuses when the candidate's head does not match the ledger's ``git_sha``
  (the candidate was rewritten after verification → reject, never repair);
- message normalization happens HERE (squash with the canonical subject), never by
  rewriting agent history inside the runtime (the runtime's commit-gate default is now
  strict — see ``workflow_runner._enforce_commit_prefix``);
- approval (when the run stopped awaiting) must bind to the same candidate SHA.

Usage:
    python scripts/promote.py --spec <name> --workdir <worktree> [--ledger <path>]
                              [--approval <path>] [--operator <name>] [--dry-run]
    agentic-dynamics workflow promote --spec <name> --workdir <worktree>

AIO emission (Wave-3 a5): promoting is the AIO's strongest permanence verb, so the decision
and the act are emitted into the knowledge base at this call site — an observation of the
promote decision (with the run identity + candidate sha + operator name) before the push, and
an actuation record whose ``causes`` cites that observation after the push lands. Emission is
BEST-EFFORT: a downed knowledge stream is a warning, never a blocked promotion.

Exit codes (the same vocabulary as run_workflow.py):
    0   promoted (or dry-run: would promote)
    10  awaiting_approval — the run stopped at a checkpoint and no valid approval binds
    20  refused — verification failed (gate evidence missing/stale/mismatched)
    30  invalid_request — bad CLI usage
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    import _bootstrap  # noqa: F401  # direct run: scripts/ is sys.path[0] (adds src/)
except ImportError:  # imported as scripts.promote — repo root is on sys.path
    from scripts import _bootstrap  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent

#: The promotion candidate's commit-subject pattern (the same canonical pattern the
#: workflow engine's commit gate enforces; here it is the SQUASH subject).
PROMOTION_PREFIX = "[workflow]"


def main() -> None:
    ap = argparse.ArgumentParser(description="Promote a verified workflow candidate to main")
    ap.add_argument("--spec", required=True, help="workflow spec name (the ledger's spec_name)")
    ap.add_argument("--workdir", required=True, help="the candidate's git worktree (its HEAD is the candidate)")
    ap.add_argument("--ledger", default=None,
                    help="run ledger JSON (default: the latest under experiments/results/workflows/<spec>/); "
                         "required when the latest ledger does not match the worktree HEAD")
    ap.add_argument("--approval", default=None,
                    help="operator-signed approval artifact for an awaiting run (approvals/<spec>/<phase>_approval.md)")
    ap.add_argument("--base", default="main", help="promotion base branch (default: main)")
    ap.add_argument("--operator", default="",
                    help="who is promoting (the AIO carries the operator's name; recorded on the "
                         "aio emission, never inferred)")
    ap.add_argument("--dry-run", action="store_true",
                    help="verify everything, print the plan, write nothing, push nothing")
    args = ap.parse_args()

    try:
        _run_promotion(args)
    except _PromoteRefusedError as exc:
        print(f"promote: REFUSED — {exc}", file=sys.stderr)
        raise SystemExit(20) from None
    except _PromoteAwaitingError as exc:
        print(f"promote: AWAITING — {exc}", file=sys.stderr)
        raise SystemExit(10) from None


class _PromoteRefusedError(Exception):
    """Verification failed — promotion refused with the evidence."""


class _PromoteAwaitingError(Exception):
    """The run stopped awaiting approval and no valid approval binds the candidate."""


# ── a5 AIO emission (Wave-3 a5_aio_emission) ─────────────────────────────────
# Promoting is the AIO's strongest permanence verb, so the decision and the act emit into the
# knowledge base AT THIS CALL SITE — an observation (observation_ingestion) before the push and
# an actuation (actuation_ingestion's derive_actuation_record, the first permanence caller)
# whose causes cite that observation after the push lands. Emission is BEST-EFFORT by contract:
# every wrapper swallows its failures and prints a warning — a downed knowledge stream can
# never block a verified promotion.


def _promote_decision(
    args: argparse.Namespace,
    ledger: dict,
    candidate: str,
    *,
    status: str,
    requested_action: dict | None = None,
) -> dict:
    """The promote decision/act dict the emission seam consumes (verb/run/candidate/operator).

    ``run_id`` is the ledger's run identity — the ``spec_id`` when the ledger carries one
    (``<name>@<version>``), else the spec name: the identifier the ledger that produced this
    candidate was filed under. The candidate sha is the verified worktree HEAD.
    """
    run_id = str(ledger.get("spec_id") or "") or str(ledger.get("spec_name") or "") or args.spec
    decision = {
        "verb": "promote",
        "run_id": run_id,
        "candidate_sha": candidate,
        "operator": args.operator,
        "status": status,
        "why": f"workflow {args.spec} → {args.base}",
    }
    if requested_action:
        decision["requested_action"] = requested_action
    return decision


def _emit_best_effort(label: str, fn) -> dict | None:
    """Run an emission step, swallowing ANY failure (best-effort is structural, not incidental).

    Even an injected emitter that raises must never block a verified promotion — the a5
    contract is that a failed emit is a warning, never a blocked act.
    """
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - best-effort by contract
        print(f"promote: WARNING — {label} emission failed ({exc}); "
              "proceeding (best-effort, never a blocked promotion)", file=sys.stderr)
        return None


def _aio_emit_decision(decision: dict) -> dict:
    """Default emit_decision: build + publish the promote-decision observation (best-effort).

    Returns ``{"observation_id": ..., "entry_ids": [...]}`` — the observation id survives a
    downed stream (it is derived offline) so the act emission can still cite it. Never raises
    (the publish path swallows its failures; the call site's ``_emit_best_effort`` is the
    backstop).
    """
    from agentic_dynamics.control import aio_emission

    out = aio_emission.emit_decision(decision)
    return {"observation_id": out["observation"].knowledge_id, "entry_ids": out["entry_ids"]}


def _aio_emit_act(decision: dict, *, causes: str) -> dict:
    """Default emit_act: build + publish the promote-act actuation (best-effort). Never raises."""
    from agentic_dynamics.control import aio_emission

    out = aio_emission.emit_act(decision, causes=causes)
    return {"actuation_id": out["actuation"].knowledge_id, "entry_ids": out["entry_ids"]}


def _run_promotion(
    args: argparse.Namespace,
    *,
    push=None,
    emit_decision=None,
    emit_act=None,
) -> None:
    """Verify and promote a candidate. The three side-effecting/emitting steps are injectable.

    ``push`` (the squash-merge + ``git push``) and the two a5 emission steps
    (``emit_decision`` — the promote-decision observation before the push, ``emit_act`` — the
    actuation after a successful push) default to the real implementations; the tests inject
    fakes so the whole transaction is testable without a remote or a live knowledge stream —
    the same injectable pattern ``publish_release.main`` uses for its deployer/builder.
    """
    push = push or _push_squashed
    emit_decision = emit_decision or _aio_emit_decision
    emit_act = emit_act or _aio_emit_act

    workdir = Path(args.workdir).resolve()
    if not workdir.is_dir():
        raise _PromoteRefusedError(f"workdir not found: {workdir}")

    ledger = _load_ledger(args)
    candidate = _git_head(workdir)
    ledger_sha = str(ledger.get("git_sha", "") or "")
    if not ledger_sha:
        raise _PromoteRefusedError("ledger carries no git_sha — no candidate identity to verify")
    if not candidate.startswith(ledger_sha[:7]):
        raise _PromoteRefusedError(
            f"candidate rewritten since verification: worktree HEAD {candidate[:12]} "
            f"!= ledger git_sha {ledger_sha[:12]} — the candidate was modified after its "
            f"gates ran; verify the new head and re-run before promoting"
        )

    # 1 ── every phase gate binds to the candidate and passed.
    phases = ledger.get("phases") or []
    if not phases:
        raise _PromoteRefusedError("ledger has no phases — nothing was run")
    for ph in phases:
        status = str(ph.get("status", ""))
        kind = str(ph.get("kind", ""))
        if status != "ok":
            raise _PromoteRefusedError(
                f"phase '{ph.get('phase')}' recorded {status} — an unverified phase can never "
                f"be promoted"
            )
        if kind == "test" and ph.get("test_executed_success") is not True:
            # A declared test phase must have actually executed and passed — the
            # test_executed_success field is the independent run_suite verdict, never
            # the agent's self-report. None means "never run" (null-not-zero).
                raise _PromoteRefusedError(
                    f"test phase '{ph.get('phase')}' has no independent success verdict "
                    f"(test_executed_success={ph.get('test_executed_success')!r}) — the "
                    f"declared verification never ran; promotion is forbidden"
                )
        commit_hash = str(ph.get("commit_hash", "") or "")
        if not commit_hash:
            raise _PromoteRefusedError(f"phase '{ph.get('phase')}' recorded no commit_hash")

    # 2 ── the run was not left awaiting unless a valid approval binds THIS candidate.
    awaiting = bool(ledger.get("awaiting", False))
    if awaiting:
        approval = _load_approval(args)
        _verify_approval(approval, ledger, candidate)

    # 3 ── the base is present and the promotion is fast-forwardable onto it.
    base = args.base
    _require_branch(workdir, base)

    # 4 ── promote: squash the candidate's phase commits onto the base with the canonical
    # subject. Normalization happens HERE, never in the runtime.
    subject = f"{PROMOTION_PREFIX} {args.spec}"
    print(
        f"promote: verified candidate {candidate[:12]} ({len(phases)} phase(s), "
        f"${float(ledger.get('total_cost_usd', 0) or 0):.4f}) → {base} as '{subject}'"
    )
    if args.dry_run:
        print("promote: dry-run — verified, would squash-merge + push (nothing written)")
        return

    merge_base = _git(workdir, "merge-base", base, "HEAD")
    if not merge_base:
        raise _PromoteRefusedError(f"no merge base between {base} and HEAD — history is unrelated")
    # Squash the candidate's commits (base..HEAD) into ONE commit on the base.
    diff = _git(workdir, "diff", f"{merge_base}..HEAD")
    if not diff:
        raise _PromoteRefusedError("candidate has no changes vs the base — nothing to promote")

    # 5 ── the AIO's decision emits BEFORE the act (best-effort, never blocking): an
    # observation of the promote decision with the run identity + candidate sha + operator.
    # The status reflects what actually authorized this promotion: a run that stopped
    # awaiting operator approval and is now bound by a valid approval promotes as "approved";
    # a straight verified run promotes as "requested" (routed on the packet's promotable_runs).
    decision = _promote_decision(args, ledger, candidate, status="approved" if awaiting else "requested")
    emitted = _emit_best_effort("promote decision", lambda: emit_decision(decision))
    observation_id = (emitted or {}).get("observation_id")

    pushed = push(workdir, base, subject, candidate)
    print(f"promote: pushed {base} → {pushed[:12]} (squash of {candidate[:12]})")

    # 6 ── the act emits AFTER it lands: an actuation record whose ``causes`` links back to
    # the decision observation above (the lineage gate), carrying the pushed sha as the outcome.
    _emit_best_effort(
        "promote act",
        lambda: emit_act(
            _promote_decision(
                args, ledger, candidate, status="approved" if awaiting else "requested",
                requested_action={"outcome": "pushed", "pushed_sha": pushed, "base": base},
            ),
            causes=observation_id or "",
        ),
    )


# ── verification helpers ──────────────────────────────────────────────────────


def _load_ledger(args: argparse.Namespace) -> dict:
    if args.ledger:
        path = Path(args.ledger)
        if not path.is_file():
            raise _PromoteRefusedError(f"ledger not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))
    spec_dir = ROOT / "experiments" / "results" / "workflows" / args.spec
    if not spec_dir.is_dir():
        raise _PromoteRefusedError(f"no ledgers under {spec_dir} — pass --ledger explicitly")
    latest = sorted(spec_dir.glob("*.json"))
    if not latest:
        raise _PromoteRefusedError(f"no ledgers under {spec_dir} — pass --ledger explicitly")
    return json.loads(latest[-1].read_text(encoding="utf-8"))


def _load_approval(args: argparse.Namespace) -> dict:
    """Load the approval artifact (markdown frontmatter + signature lines)."""
    if args.approval:
        path = Path(args.approval)
    else:
        path = ROOT / "approvals" / args.spec / f"{args.spec}_approval.md"
    if not path.is_file():
        raise _PromoteAwaitingError(
            f"run is awaiting operator approval and no approval artifact binds it "
            f"({path} not found)"
        )
    text = path.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return {"path": path, "text": text, "lines": lines}


def _verify_approval(approval: dict, ledger: dict, candidate: str) -> None:
    """The approval must bind THIS candidate (a stale or foreign approval refuses)."""
    text = approval["text"]
    ok_parts = [
        p for p in ("candidate", "sha", "workflow")
        if p.lower() in text.lower()
    ]
    if not ok_parts:
        raise _PromoteRefusedError(
            f"approval {approval['path']} names no candidate — an unsigned or templated "
            f"approval can never authorize a promotion"
        )
    if candidate[:12] not in text and candidate not in text:
        raise _PromoteRefusedError(
            f"approval {approval['path']} binds a DIFFERENT candidate (ledger git_sha "
            f"{candidate[:12]} absent) — approval and candidate must match"
        )
    # A real signature: a non-placeholder operator + a date, in the approval text.
    low = text.lower()
    if "operator" in low and ("operator: " not in low or "placeholder" in low):
        raise _PromoteRefusedError(f"approval {approval['path']} carries no real operator signature")
    if "date" not in low:
        raise _PromoteRefusedError(f"approval {approval['path']} carries no date")


# ── git helpers ───────────────────────────────────────────────────────────────


def _git(workdir: Path, *argv: str, check: bool = True) -> str:
    run = subprocess.run(
        ["git", *argv], cwd=workdir, capture_output=True, text=True, timeout=60,
    )
    if check and run.returncode != 0:
        raise _PromoteRefusedError(f"git {' '.join(argv)} failed: {(run.stderr or '').strip()[:400]}")
    return run.stdout.strip()


def _git_head(workdir: Path) -> str:
    return _git(workdir, "rev-parse", "HEAD")


def _require_branch(workdir: Path, base: str) -> None:
    try:
        _git(workdir, "rev-parse", f"refs/heads/{base}")
    except _PromoteRefusedError:
        raise _PromoteRefusedError(
            f"base branch '{base}' not found in the candidate worktree"
        ) from None


def _push_squashed(workdir: Path, base: str, subject: str, candidate: str) -> str:
    """Squash the candidate onto the base and push it.

    Non-LLM and mechanical: a temporary promotion branch is created at the base, the
    candidate's diff is squash-merged onto it, and the single commit (canonical subject)
    is pushed to the base. ``git push`` is the ONLY write to the remote, and this is the
    sole place in the repo that performs it for promotion. The candidate's own history is
    NEVER rewritten — it becomes one squash commit on the base.
    """
    branch = f"promote-{candidate[:8]}"
    _git(workdir, "checkout", "-q", "-b", branch, base)
    _git(workdir, "merge", "--squash", "--no-commit", candidate)
    _git(workdir, "commit", "-q", "-m", subject)
    pushed = _git(workdir, "rev-parse", "HEAD")
    _git(workdir, "push", "-q", "origin", f"{branch}:{base}")
    return pushed


if __name__ == "__main__":
    main()
