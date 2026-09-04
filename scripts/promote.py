"""Promote a verified workflow candidate to main (P0-4, control-plane stabilization).

The ONLY path that updates ``main``. Workers, the master controller, and the workflow
engine never push — they produce candidates; this non-LLM command verifies and promotes.

The authority rules (the deep review's P0-4):
- execution produces a candidate, never an authoritative merge;
- the promoter refuses promotion when ANY gate evidence is missing, stale, or bound to
  a different candidate SHA;
- the promoter refuses when the candidate's head does not match the ledger's ``git_sha``
  (the candidate was rewritten after verification → reject, never repair);
- the promoter refuses a STALE candidate whose tree is already the base head's tree (the
  content reached main by an earlier path — a post-promote leftover; cancel the run row,
  never re-promote);
- message normalization happens HERE (squash with the canonical subject), never by
  rewriting agent history inside the runtime (the runtime's commit-gate default is now
  strict — see ``workflow_runner._enforce_commit_prefix``);
- approval (when the run stopped awaiting) must bind to the same candidate SHA.

Usage:
    python scripts/promote.py --spec <name> --workdir <worktree> [--ledger <path>]
                              [--approval <path>] [--operator <name>] [--db <path>] [--dry-run]
    agentic-dynamics workflow promote --spec <name> --workdir <worktree>

AIO emission (Wave-3 a5): promoting is the AIO's strongest permanence verb, so the decision
and the act are emitted into the knowledge base at this call site — an observation of the
promote decision (with the run identity + candidate sha + operator name) before the push, and
an actuation record whose ``causes`` cites that observation after the push lands. Emission is
BEST-EFFORT: a downed knowledge stream is a warning, never a blocked promotion.

Control-row close (promote_row_closeout a1): promoting is ALSO a control-plane verb, and the
run's row must not outlive its content's arrival on main. After the push lands, this command
closes its own control row — ``promotable -> merged`` through the legitimate
``ControlDB.transition_run`` API (the lifecycle routes through ``promoting``), records the
``promotions`` row, and binds everything to the ledger's ``run_id`` + the pushed squash sha.
The close is BEST-EFFORT and ordered AFTER the push: the push has landed; a control-db failure
prints a warning naming the run_id + the close-out sweep as backstop, never raises, never
unwinds a landed push.

Verified-command decision record (s2b, the self-knowledge layer): promoting is also recorded
as an s2 DECISION record (``decision_ingestion.record_decision``, ``actor: verified_command``)
bound to the run_id + candidate_sha this promotion acted on — the org-root "what was promoted
and why" the next session retrieves by category instead of re-deriving by grep. Default-on and
best-effort under the same structural contract: a failed record never blocks a promotion.

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
from datetime import datetime, timezone
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
    ap.add_argument(
        "--workdir", required=True, help="the candidate's git worktree (its HEAD is the candidate)"
    )
    ap.add_argument(
        "--ledger",
        default=None,
        help="run ledger JSON (default: the latest under experiments/results/workflows/<spec>/); "
        "required when the latest ledger does not match the worktree HEAD",
    )
    ap.add_argument(
        "--approval",
        default=None,
        help="operator-signed approval artifact for an awaiting run (approvals/<spec>/<phase>_approval.md)",
    )
    ap.add_argument("--base", default="main", help="promotion base branch (default: main)")
    ap.add_argument(
        "--operator",
        default="",
        help="who is promoting (the AIO carries the operator's name; recorded on the "
        "aio emission, never inferred)",
    )
    ap.add_argument(
        "--db",
        default=None,
        help="control database path (default: FINOPS_CONTROL_DB or "
        "<repo>/experiments/results/control/control.db)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="verify everything, print the plan, write nothing, push nothing",
    )
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
        print(
            f"promote: WARNING — {label} emission failed ({exc}); "
            "proceeding (best-effort, never a blocked promotion)",
            file=sys.stderr,
        )
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


# ── s2b verified-command decision-record emission (self-knowledge layer, loop 2) ──
# Every verified permanence verb records an s2 DECISION record at its own call site — the
# org-root "what was promoted/published and why" the next session retrieves by category instead
# of re-deriving by grep. This is the promote emission: ``decision_ingestion.record_decision``
# with ``actor: verified_command`` and the decision bound to this promotion's run_id +
# candidate_sha. Default-on (no flag arms it) and best-effort (a failed record never blocks a
# verified promotion — the same structural contract as the a5 emissions above).

#: The s2 actor this verified command records (the module docstring's ``verified_command``).
VERIFIED_COMMAND_ACTOR = "verified_command"

#: The retrieval category the promote decisions are filed under — ``scan_decision_records(
#: category="promote")`` resolves every promotion this command has recorded. Categories are open
#: by design (documentation, never a validator); the verb IS the natural retrieval axis here.
DECISION_CATEGORY = "promote"


def _default_decision_record(decision: dict) -> dict:
    """Default record_decision: record ONE s2 decision through the producer seam (best-effort).

    The durable artifact + pointer event are written by ``decision_ingestion.record_decision``
    itself, whose contract is best-effort (a downed stream degrades to a warning, never a
    raise). This wrapper exists so the call site can name one injectable seam.
    """
    from agentic_dynamics.knowledge import decision_ingestion as di

    result = di.record_decision(decision)
    return {
        "status": result.status,
        "knowledge_id": result.record.knowledge_id,
        "artifact": str(result.artifact_path),
        "warnings": list(result.warnings),
    }


def _promote_decision_record(args: argparse.Namespace, ledger: dict, candidate: str) -> dict:
    """The s2 decision dict this promote records: what/why/category/actor + run/candidate.

    ``what`` names the permanence act in human terms; ``why`` is the decision's rationale (the
    candidate passed every gate the promotion verified); ``run_id``/``candidate_sha`` bind the
    record to the exact run + tree the promotion acted on (the DONE_WHEN). ``decided_at`` is the
    moment of the decision — recorded at invocation, not at some later derivation.
    """
    phases = ledger.get("phases") or []
    cost = float(ledger.get("total_cost_usd", 0) or 0)
    run_id = str(ledger.get("spec_id") or "") or str(ledger.get("spec_name") or "") or args.spec
    return {
        "what": f"promote workflow {args.spec} to {args.base}",
        "why": f"candidate {candidate[:12]} passed {len(phases)} verified phase gate(s) "
        f"(${cost:.4f}) — promoted as '{PROMOTION_PREFIX} {args.spec}'",
        "alternatives": [],
        "category": DECISION_CATEGORY,
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "actor": VERIFIED_COMMAND_ACTOR,
        "run_id": run_id,
        "candidate_sha": candidate,
    }


# ── Control-row close (promote_row_closeout a1) ─────────────────────────────────
# The bookkeeping half of a promotion. The push has LANDED; the run's control row must now
# move promotable -> merged and record its promotions row, so the packet stops advertising
# already-merged work (the graph-leg strand: two promotable rows cancelled by hand). The close
# mirrors the emission seams exactly: an injectable `close_row` (tests fake it), a default that
# opens the control db through the legitimate writer API, and a best-effort wrapper so a
# control-db failure is a warning naming the run_id + the close-out sweep as backstop — never
# a raise and never an unwound push.

#: The actor recorded on the run's close transitions (the transition log's lifecycle
#: vocabulary: ``orchestrator`` starts runs, ``controller-close-out`` cancelled stale ones,
#: ``promote`` now closes its own).
ROW_CLOSE_ACTOR = "promote"


def _ledger_run_id(ledger: dict) -> str:
    """The control-db run id the ledger is bound to — ``''`` for a legacy/pre-db ledger.

    ``run_workflow`` stamps the control row's id onto the ledger result (``run_id``), so the
    ledger's ``run_id`` IS the ``runs.run_id`` the terminal write left ``promotable``. A ledger
    without one predates the stamp (or its run's db was down at mint time) and has no row this
    command may close.
    """
    return str(ledger.get("run_id") or "").strip()


def _row_close_reason(base: str, squash_sha: str, candidate_sha: str) -> str:
    """The one-line transition reason — must name the squash sha (the a1 DONE_WHEN)."""
    return f"promoted to {base} as {squash_sha[:12]} (squash of {candidate_sha[:12]})"


def _default_close_row(
    run_id: str,
    *,
    candidate_sha: str,
    base: str,
    base_sha: str,
    squash_sha: str,
    by: str = "",
    db_path=None,
) -> dict:
    """Close the promoted run's control row: ``promotable -> merged`` + the promotions row.

    Best-effort by contract (hard rule 2): the push has LANDED, so every failure below is a
    printed warning naming the run_id + the close-out sweep as backstop — never a raise and
    never an unwound push. Skips (with an honest note) the cases where there is nothing to
    close:

    * no ``run_id`` (legacy/pre-db ledger);
    * the database cannot be opened;
    * the run row is absent;
    * the row's ``candidate_sha`` does not match the promoted tree (never close the wrong row);
    * the row is not ``promotable`` (already merged/cancelled/failed — idempotent, no double
      transition; a re-promote of an already-merged run must not mint a second transition).

    The close uses ``ControlDB.transition_run`` — never raw SQL — so the append-only
    ``run_transitions`` log stays the single history. The lifecycle routes ``promotable``
    through ``promoting`` into ``merged`` (the state machine has no single-hop edge), so the
    two hop transitions and the ``promotions`` insert are committed as ONE transaction: a row
    that reads ``merged`` always carries both hops and its promotion record.
    """
    if not run_id:
        print(
            "promote: ledger carries no control run_id (a legacy or pre-control-db run) — "
            "no control row to close; the close-out sweep remains the backstop",
            file=sys.stderr,
        )
        return {"closed": False, "run_id": "", "reason": "no_ledger_run_id"}

    # Lazy import mirrors the emission seams: the control db is a runtime dependency, not a
    # module-import-time one (promote.py stays importable where agentic_dynamics is absent).
    from agentic_dynamics.control.control_db import ControlDB, RunState

    try:
        with ControlDB.open(db_path) as db:
            run = db.get_run(run_id)
            if run is None:
                print(
                    f"promote: WARNING — control row {run_id} not found in the control db; "
                    "nothing to close — the close-out sweep remains the backstop (the push "
                    "stands)",
                    file=sys.stderr,
                )
                return {"closed": False, "run_id": run_id, "reason": "unknown_run"}
            row_sha = (run.candidate_sha or "").strip()
            if row_sha and not candidate_sha.startswith(row_sha):
                # The row this run_id names is bound to a DIFFERENT tree than the one this
                # promote just pushed. Closing it would record a merge for content that never
                # reached main — refuse the close (never close the wrong row) and leave the
                # mismatch for a human.
                print(
                    f"promote: WARNING — control row {run_id} is bound to candidate "
                    f"{row_sha[:12]}, not the promoted {candidate_sha[:12]} — refusing to "
                    "close the wrong run; the close-out sweep remains the backstop (the push "
                    "stands)",
                    file=sys.stderr,
                )
                return {"closed": False, "run_id": run_id, "reason": "candidate_mismatch"}
            if run.state != RunState.PROMOTABLE:
                # Already terminal on this path, or already moved by another promoter run:
                # there is no promotable row to close, and forcing a transition would be a lie
                # (or an InvalidTransitionError). Idempotence: a re-promote of an already-merged
                # run must not double-transition.
                print(
                    f"promote: control row {run_id} is {run.state.value}, not promotable — "
                    "no close performed (already closed or moved; the push stands)",
                    file=sys.stderr,
                )
                return {"closed": False, "run_id": run_id, "reason": f"state_{run.state.value}"}

            reason = _row_close_reason(base, squash_sha, candidate_sha)
            with db.transaction():
                # Two hops, one transaction: promotable -> promoting -> merged. The state
                # machine has no direct promotable -> merged edge (promoting exists for the
                # promoter's squash-merge), and transition_run enforces the graph.
                db.transition_run(
                    run_id,
                    RunState.PROMOTING,
                    reason=reason,
                    actor=ROW_CLOSE_ACTOR,
                )
                db.transition_run(
                    run_id,
                    RunState.MERGED,
                    reason=reason,
                    actor=ROW_CLOSE_ACTOR,
                )
                db.record_promotion(
                    run_id,
                    candidate_sha=candidate_sha,
                    base_sha=base_sha,
                    squash_sha=squash_sha,
                    by=by,
                )
        print(
            f"promote: closed control row {run_id} (promotable → merged, actor "
            f"{ROW_CLOSE_ACTOR}, promotions row recorded)"
        )
        return {"closed": True, "run_id": run_id, "reason": "closed"}
    except Exception as exc:  # noqa: BLE001 — best-effort by contract (hard rule 2)
        # Any control-db failure AFTER a landed push: warn, name the backstop, exit 0. The
        # push stands — the close is bookkeeping, never a reason to unwind a merged act.
        print(
            f"promote: WARNING — could not close control row {run_id} ({exc}); the close-out "
            "sweep remains the backstop — the push has landed and stands (never unwound)",
            file=sys.stderr,
        )
        return {"closed": False, "run_id": run_id, "reason": "error"}


def _close_row_best_effort(run_id: str, fn):
    """Run the injected close step, swallowing ANY failure (best-effort is structural).

    The default ``_default_close_row`` never raises, but the seam must hold for an injected
    implementation too: a raise here is a bookkeeping failure, not a failed promotion — the
    push already happened.
    """
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - best-effort by contract (hard rule 2)
        print(
            f"promote: WARNING — control-row close failed for run {run_id} ({exc}); the "
            "close-out sweep remains the backstop — the push has landed and stands",
            file=sys.stderr,
        )
        return None


def _run_promotion(
    args: argparse.Namespace,
    *,
    push=None,
    emit_decision=None,
    emit_act=None,
    record_decision=None,
    close_row=None,
) -> None:
    """Verify and promote a candidate. The side-effecting/emitting steps are injectable.

    ``push`` (the squash-merge + ``git push``), the two a5 emission steps
    (``emit_decision`` — the promote-decision observation before the push, ``emit_act`` — the
    actuation after a successful push), the s2b ``record_decision``, and the a1 control-row
    ``close_row`` (``promotable -> merged`` + the promotions row after the push) default to the
    real implementations; the tests inject fakes so the whole transaction is testable without a
    remote, a live knowledge stream, or a control database — the same injectable pattern
    ``publish_release.main`` uses for its deployer/builder.
    """
    push = push or _push_squashed
    emit_decision = emit_decision or _aio_emit_decision
    emit_act = emit_act or _aio_emit_act
    record_decision = record_decision or _default_decision_record
    close_row = close_row or _default_close_row

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

    # 4 ── the stale-candidate guard (promote_row_closeout a2): BEFORE any push — and before the
    # dry-run return, so a dry run refuses too — compare the candidate's tree against the base
    # head's tree. Tree-identical content means the candidate is a post-promote leftover (the
    # graph-leg class: content already on main as a squash, the run row left promotable). Refuse
    # with the evidence + the recommendation to cancel the run row — never a second merge, never
    # an auto-cancel. The refusal writes nothing (no db, no push, no transition row).
    stale = _stale_candidate_refusal(workdir, base, candidate)
    if stale:
        raise _PromoteRefusedError(stale)

    # 5 ── promote: squash the candidate's phase commits onto the base with the canonical
    # subject. Normalization happens HERE, never in the runtime.
    subject = f"{PROMOTION_PREFIX} {args.spec}"
    print(
        f"promote: verified candidate {candidate[:12]} ({len(phases)} phase(s), "
        f"${float(ledger.get('total_cost_usd', 0) or 0):.4f}) → {base} as '{subject}'"
    )
    run_id = _ledger_run_id(ledger)
    if args.dry_run:
        # Dry-run reports the would-be control-row close (a1 DONE_WHEN c) and writes nothing:
        # no db open, no transition, no promotion row — the close is a post-push side effect,
        # and there is no push in a dry run.
        if run_id:
            print(
                f"promote: dry-run — would close control row {run_id} "
                "(promotable → merged + promotions row) after the push (nothing written)"
            )
        else:
            print(
                "promote: dry-run — ledger carries no control run_id; no control row would "
                "be closed (nothing written)"
            )
        print("promote: dry-run — verified, would squash-merge + push (nothing written)")
        return

    merge_base = _git(workdir, "merge-base", base, "HEAD")
    if not merge_base:
        raise _PromoteRefusedError(f"no merge base between {base} and HEAD — history is unrelated")
    # Squash the candidate's commits (base..HEAD) into ONE commit on the base.
    diff = _git(workdir, "diff", f"{merge_base}..HEAD")
    if not diff:
        raise _PromoteRefusedError("candidate has no changes vs the base — nothing to promote")

    # 6 ── the AIO's decision emits BEFORE the act (best-effort, never blocking): an
    # observation of the promote decision with the run identity + candidate sha + operator.
    # The status reflects what actually authorized this promotion: a run that stopped
    # awaiting operator approval and is now bound by a valid approval promotes as "approved";
    # a straight verified run promotes as "requested" (routed on the packet's promotable_runs).
    decision = _promote_decision(
        args, ledger, candidate, status="approved" if awaiting else "requested"
    )
    emitted = _emit_best_effort("promote decision", lambda: emit_decision(decision))
    observation_id = (emitted or {}).get("observation_id")

    # 7 ── the push lands. ``base_head`` is captured BEFORE it (the local base ref does not
    # move on a push): the pre-push base head is the ``base_sha`` the promotions row records,
    # so the merge is independently re-derivable (check out the base, replay the squash).
    base_head = _git(workdir, "rev-parse", base)
    pushed = push(workdir, base, subject, candidate)
    print(f"promote: pushed {base} → {pushed[:12]} (squash of {candidate[:12]})")

    # 8 ── the run's control row closes AFTER the push lands (a1, hard rule 2's ordering): the
    # push has LANDED, so the close is best-effort bookkeeping. A control-db failure prints a
    # warning naming the run_id + the close-out sweep as backstop — never a raise, never an
    # unwound push. A ledger with no run_id closes nothing (there is no control row to close).
    if run_id:
        _close_row_best_effort(
            run_id,
            lambda: close_row(
                run_id,
                candidate_sha=candidate,
                base=base,
                base_sha=base_head,
                squash_sha=pushed,
                by=args.operator,
                db_path=args.db,
            ),
        )

    # 9 ── the s2b DECISION record lands after the push succeeds: the verified command records
    # its own permanence decision (actor: verified_command) bound to this run_id + candidate_sha
    # — what was promoted and why, retrievable by category. Default-on and best-effort: a failed
    # record never blocks (the durable act already happened).
    _emit_best_effort(
        "promote decision record",
        lambda: record_decision(_promote_decision_record(args, ledger, candidate)),
    )

    # 10 ── the act emits AFTER it lands: an actuation record whose ``causes`` links back to
    # the decision observation above (the lineage gate), carrying the pushed sha as the outcome.
    _emit_best_effort(
        "promote act",
        lambda: emit_act(
            _promote_decision(
                args,
                ledger,
                candidate,
                status="approved" if awaiting else "requested",
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
    ok_parts = [p for p in ("candidate", "sha", "workflow") if p.lower() in text.lower()]
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
        raise _PromoteRefusedError(
            f"approval {approval['path']} carries no real operator signature"
        )
    if "date" not in low:
        raise _PromoteRefusedError(f"approval {approval['path']} carries no date")


# ── git helpers ───────────────────────────────────────────────────────────────


def _git(workdir: Path, *argv: str, check: bool = True) -> str:
    run = subprocess.run(
        ["git", *argv],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if check and run.returncode != 0:
        raise _PromoteRefusedError(
            f"git {' '.join(argv)} failed: {(run.stderr or '').strip()[:400]}"
        )
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


# ── stale-candidate guard (promote_row_closeout a2) ────────────────────────────
# A candidate whose TREE is already the base head's tree is a post-promote leftover: the
# content reached main by an earlier path (a squash merge), and re-promoting would land a
# second, empty-of-new-content merge. The refusal compares trees (content identity), never
# commit lineage — a squash on main and the branch tip it came from are different commits with
# the same content, which is exactly the class that stranded the graph-leg rows. The reason
# names the likely merged sha (found via ``git log`` over the base side) + the recommendation
# to cancel the run row, not re-promote. The guard runs BEFORE any push and BEFORE the dry-run
# return, so a dry run refuses too; it writes nothing and never touches the control db.

#: Cap on how far back the ``git log`` equal-tree scan looks. The base head itself always
#: matches when the guard fires (the candidate tree IS the base head tree), so the scan is
#: normally satisfied by the first line; the cap is a bound for pathological histories.
_EQUAL_TREE_SCAN_LIMIT = 200


def _git_is_ancestor(workdir: Path, ancestor: str, descendant: str) -> bool:
    """True when ``ancestor`` is reachable from ``descendant`` (equal commits count).

    ``git merge-base --is-ancestor A B`` exits 0 exactly when A is an ancestor of B (or A == B).
    The candidate being reachable from the base means the base ALREADY contains the candidate
    commit — nothing-new-to-merge (the non-dry path's empty-diff refusal), NOT the stale-leftover
    class this guard exists to refuse (a DIFFERENT commit with the same tree).
    """
    run = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return run.returncode == 0


def _base_side_equal_tree_commit(workdir: Path, base: str, tree: str) -> tuple[str, str] | None:
    """The newest ``base``-side commit whose tree equals ``tree``, as ``(sha, subject)``.

    ``git log`` over the base side, newest first; the first commit whose recorded tree matches
    the candidate's is the likely merged sha the refusal names. ``None`` when no base-side
    commit carries the tree (the refusal then states the equality plainly).
    """
    lines = _git(
        workdir,
        "log",
        base,
        f"--max-count={_EQUAL_TREE_SCAN_LIMIT}",
        "--format=%H%x09%T%x09%s",
    ).splitlines()
    for line in lines:
        parts = line.split("\t", 2)
        if len(parts) >= 2 and parts[1] == tree:
            subject = parts[2] if len(parts) == 3 else ""
            return parts[0], subject
    return None


def _stale_candidate_refusal(workdir: Path, base: str, candidate: str) -> str | None:
    """Return the refusal message when ``candidate``'s tree is already the base head's tree.

    ``None`` when the candidate is genuinely new. Two carve-outs keep the guard honest:

    * the trees differ — nothing stale to refuse;
    * the candidate is reachable from the base (an ancestor, possibly equal) — the base already
      contains the candidate *commit*, which is the nothing-new-to-merge case, not the
      stale-leftover class (a post-squash branch tip is never an ancestor of the squash).

    Refusal evidence: the candidate tree hash, the likely merged sha + subject (via
    ``_base_side_equal_tree_commit``), and the recommendation to cancel the run row — never an
    auto-cancel and never a second merge.
    """
    candidate_tree = _git(workdir, "rev-parse", "HEAD^{tree}")
    base_tree = _git(workdir, "rev-parse", f"{base}^{{tree}}")
    if candidate_tree != base_tree:
        return None
    if _git_is_ancestor(workdir, candidate, base):
        return None
    merged = _base_side_equal_tree_commit(workdir, base, candidate_tree)
    if merged is not None:
        merged_sha, merged_subject = merged
        return (
            f"stale candidate: tree {candidate_tree[:12]} is already on {base} as "
            f"{merged_sha[:12]} ({merged_subject or 'tree-identical'}) — the content reached "
            f"main and this run is a post-promote leftover. Cancel the run's control row, do "
            f"not re-promote"
        )
    return (
        f"stale candidate: tree {candidate_tree[:12]} is identical to the {base} head tree "
        f"({base_tree[:12]}) — the content reached main and this run is a post-promote "
        f"leftover. Cancel the run's control row, do not re-promote"
    )


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
