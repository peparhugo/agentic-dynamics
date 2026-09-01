"""Tests for the docs-drift proposal gate (``automatic_docs_sync`` p3).

The workflow spec asks for one property in each direction, and they are the two headings below:

* **propose-without-running** — a non-zero scan proposes the remediation and queues NOTHING;
* **approve-runs-once** — an approved gate enqueues exactly the remediation, once, and a second
  approval is a no-op while one is in flight.

Everything else here defends those two: the refusals that make an approval mean something (no
approval, a stale one, a bad workdir), the failure paths that must not wedge the rail (a failed
enqueue rolls the claim back), and the "could not measure is not clean" discipline the gate
inherits from the scanner and the watchdog.

The enqueue is always an INJECTED ``submit_fn`` whose calls are counted. That count is the
evidence: "queued nothing" is asserted as ``calls == 0`` against a function that would have
recorded a call, not as the absence of a side effect nobody looked for.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import docs_drift_watchdog as watchdog  # noqa: E402
import docs_proposal_gate as gate  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Fixtures — synthetic reports in the scanner's real ``docs-drift/v1`` shape
# ─────────────────────────────────────────────────────────────────────────────────────────────


def make_finding(check_id: str, *, axis: str = "anchor_integrity", status: str = "stale") -> dict:
    """One finding row, carrying all four anchored fields the scanner emits."""
    return {
        "check_id": check_id,
        "axis": axis,
        "status": status,
        "claim": f"doc claims {check_id}",
        "code_truth": f"code says otherwise for {check_id}",
        "basis": f"wc -l {check_id}  # must be >= 99999",
        "source": f"docs/architecture/current/{axis}.md:1",
    }


def make_report(findings: list[dict], *, errors: dict | None = None,
                git_sha: str = "abc1234") -> dict:
    """Assemble a report in the shape ``scan_docs_drift.DriftReport.to_json`` produces.

    Built by hand rather than by running the scanner: these tests exercise the *policy*, and a
    real scan is minutes of work whose findings would change with the tree. The shape is pinned
    by :func:`test_report_shape_matches_the_scanner` below, so a scanner-side change that broke
    this fixture cannot pass silently.
    """
    per_axis: dict[str, dict] = {}
    for finding in findings:
        bucket = per_axis.setdefault(
            finding["axis"], {"current": 0, "stale": 0, "missing": 0, "checked": 0, "drift": 0}
        )
        bucket[finding["status"]] += 1
        bucket["checked"] += 1
        bucket["drift"] += 1
    stale = sum(1 for f in findings if f["status"] == "stale")
    missing = sum(1 for f in findings if f["status"] == "missing")
    return {
        "schema": "docs-drift/v1",
        "root": str(ROOT),
        "git_sha": git_sha,
        "score": {
            "total_checked": 1000,
            "total_current": 1000 - len(findings),
            "total_stale": stale,
            "total_missing": missing,
            "drift": len(findings),
            "per_axis": per_axis,
            "axes_errored": sorted(errors or {}),
        },
        "errors": dict(errors or {}),
        "findings": findings,
        "includes_current_rows": False,
    }


@pytest.fixture
def results_dir(tmp_path: Path) -> Path:
    """An isolated state directory — never the repository's real docs_drift results."""
    d = tmp_path / "docs_drift"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def remediation() -> gate.Remediation:
    """The real remediation, parsed from the real spec (this is also its regression test)."""
    return gate.load_remediation(ROOT)


@pytest.fixture
def workdir_root(tmp_path, monkeypatch) -> Path:
    """Point the workdir rule at a tmp root so dispatch tests need no real worktree tree."""
    from agentic_dynamics.core import constants

    root = tmp_path / "worktrees"
    root.mkdir()
    monkeypatch.setattr(constants, "WORKTREE_ROOT", str(root))
    return root


class Submitter:
    """A counting stand-in for the fleet submit path.

    The whole idempotence proof reduces to :attr:`calls` on one of these. It is deliberately
    *recording* rather than merely mock-asserted, so a test can show WHAT was enqueued (the spec,
    the model, the goal) and not just how often.
    """

    def __init__(self, *, explode: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.explode = explode
        self._lock = threading.Lock()

    def __call__(self, *, spec: str, goal: str, model: str, workdir: str) -> dict:
        with self._lock:
            self.calls.append({"spec": spec, "goal": goal, "model": model, "workdir": workdir})
            n = len(self.calls)
        if self.explode is not None:
            raise self.explode
        return {"job_id": f"job{n:03d}", "action": "submit", "spec": spec}


def seed_proposal(results_dir: Path, report: dict, remediation: gate.Remediation,
                  *, threshold: int = 0) -> gate.GateDecision:
    """Run ``propose`` against an injected report — the common setup for the approve tests."""
    return gate.propose(results_dir=results_dir, report=report, remediation=remediation,
                        threshold=threshold, use_redis=False)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# DIRECTION 1 — a non-zero scan PROPOSES WITHOUT RUNNING
# ═════════════════════════════════════════════════════════════════════════════════════════════


def test_propose_on_drift_warrants_and_queues_nothing(results_dir, remediation):
    """The headline property: drift crosses the threshold, the remediation is surfaced, and
    nothing whatsoever is queued or claimed."""
    report = make_report([make_finding(f"a/{i}") for i in range(9)])

    decision = seed_proposal(results_dir, report, remediation)

    assert decision.state == gate.PROPOSAL_WARRANTED
    assert decision.outcome == "warranted"
    assert decision.drift == 9
    # ── the propose-without-running evidence, three independent ways ──
    assert decision.enqueued is False, "propose must never enqueue"
    assert not (results_dir / gate.RUN_LOCK_FILE).exists(), "propose must not take the claim"
    assert not (results_dir / gate.RUNS_FILE).exists(), "propose must not open a run record"
    assert not (results_dir / gate.APPROVALS_FILE).exists(), "propose must not self-approve"
    # ── and it DID surface something actionable ──
    on_disk = json.loads((results_dir / gate.PROPOSAL_FILE).read_text())
    assert on_disk["state"] == gate.PROPOSAL_WARRANTED
    assert on_disk["finding_count"] == 9
    assert on_disk["action"]["spec"] == gate.REMEDIATION_SPEC


def test_propose_cannot_enqueue_even_with_a_standing_approval(results_dir, remediation):
    """Structural: an approval on record does not turn ``propose`` into a launcher.

    ``fleet_submit`` is replaced with a function that fails the test if it is ever reached, so
    this asserts the absence of an enqueue PATH, not merely of an enqueue in this scenario.
    """
    report = make_report([make_finding("a/1")])
    seed_proposal(results_dir, report, remediation)
    gate.approve(by="controller", results_dir=results_dir, do_dispatch=False, use_redis=False)

    def never(**_kwargs):
        raise AssertionError("propose reached the enqueue path")

    original = gate.fleet_submit
    gate.fleet_submit = never
    try:
        decision = seed_proposal(results_dir, report, remediation)
    finally:
        gate.fleet_submit = original

    assert decision.enqueued is False
    assert not (results_dir / gate.RUN_LOCK_FILE).exists()


def test_propose_surfaces_the_budget_read_from_the_spec(results_dir, remediation):
    """The budget on the board is the spec's own ``stop.budget_usd``, re-derived here by hand.

    Hard rule 4 applied to the gate: the number a controller sees before signing must be the
    number the run is bounded by, and it must be re-derivable. This test IS that re-derivation.
    """
    import yaml

    spec_doc = yaml.safe_load((ROOT / gate.REMEDIATION_SPEC).read_text())
    decision = seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)

    action = decision.proposal["action"]
    assert action["budget_usd"] == float(spec_doc["stop"]["budget_usd"])
    assert action["model"] == spec_doc["factors"][0]["levels"][0]
    assert action["phases"] == [p["name"] for p in spec_doc["workflow"]["params"]["phases"]]
    assert action["name"] == spec_doc["name"]


def test_propose_below_threshold_proposes_nothing(results_dir, remediation):
    """A clean scan warrants nothing — and says so, rather than staying silent."""
    decision = seed_proposal(results_dir, make_report([]), remediation)
    assert decision.state == gate.PROPOSAL_NONE
    assert decision.outcome == gate.PROPOSAL_NONE
    assert decision.enqueued is False


def test_propose_respects_a_raised_threshold(results_dir, remediation):
    """Drift at the threshold is not *above* it — the comparison is strict, as documented."""
    report = make_report([make_finding(f"a/{i}") for i in range(3)])
    assert seed_proposal(results_dir, report, remediation, threshold=3).state == gate.PROPOSAL_NONE
    assert seed_proposal(results_dir, report, remediation, threshold=2).state == gate.PROPOSAL_WARRANTED


def test_propose_withdraws_a_proposal_whose_drift_is_gone(results_dir, remediation):
    """The proposal lifecycle mirrors the flag's: raised by a finding, retired by evidence."""
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    assert gate.read_proposal(results_dir)["state"] == gate.PROPOSAL_WARRANTED

    decision = seed_proposal(results_dir, make_report([]), remediation)

    assert decision.outcome == "withdrawn"
    assert decision.state == gate.PROPOSAL_NONE
    assert decision.proposal["withdrew"]["was"] == gate.PROPOSAL_WARRANTED


def test_missing_report_is_unmeasured_not_clean(results_dir, remediation):
    """No scan on disk must never render as a clean scan — the rail's founding distinction."""
    decision = gate.propose(results_dir=results_dir, remediation=remediation, use_redis=False)

    assert decision.outcome == gate.PROPOSAL_UNMEASURED
    assert decision.state == gate.PROPOSAL_NONE
    assert not (results_dir / gate.PROPOSAL_FILE).exists(), "declining to decide writes nothing"


def test_errored_report_leaves_a_standing_proposal_untouched(results_dir, remediation):
    """An unmeasured pass neither raises a proposal nor withdraws one.

    The asymmetry matters: if a broken axis could withdraw a proposal, a scanner bug would
    silently retire real findings, which is precisely the failure the ``unmeasured`` state exists
    to prevent.
    """
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    before = gate.read_proposal(results_dir)

    decision = gate.propose(results_dir=results_dir, remediation=remediation, use_redis=False,
                            report=make_report([], errors={"anchor_integrity": "boom"}))

    assert decision.outcome == gate.PROPOSAL_UNMEASURED
    assert gate.read_proposal(results_dir) == before, "the standing proposal must be untouched"


def test_goal_carries_the_inventory_with_its_bases(results_dir, remediation):
    """The dispatched brief names each finding's claim, code truth, basis and source.

    The ``basis`` is the load-bearing one: it is what lets the remediation agent re-derive the
    finding instead of taking this brief on faith.
    """
    decision = seed_proposal(results_dir, make_report([make_finding("anchor/x")]), remediation)
    goal = gate.build_goal(decision.proposal, remediation)

    assert "anchor/x" in goal
    assert "wc -l anchor/x" in goal, "the re-derivable basis must ride along"
    assert watchdog.LATEST_REPORT_REL in goal, "the full inventory must be named"
    assert "remediation, not rework" in goal


def test_goal_bounds_the_inventory_and_counts_the_overflow(results_dir, remediation):
    """A prompt is a brief, not a data dump — but the truncation is stated, never silent."""
    findings = [make_finding(f"a/{i}") for i in range(gate.GOAL_INVENTORY_LIMIT + 15)]
    decision = seed_proposal(results_dir, make_report(findings), remediation)
    goal = gate.build_goal(decision.proposal, remediation)

    assert f"FINDINGS ({gate.GOAL_INVENTORY_LIMIT} of {len(findings)})" in goal
    assert "15 further finding(s)" in goal


def test_the_dispatched_brief_is_the_APPROVED_inventory(results_dir, remediation, workdir_root):
    """The brief renders the findings the controller signed for, not the current report file.

    The watchdog rewrites ``latest.json`` every hour. If the goal were rebuilt from that file at
    dispatch time, a scan landing between the signature and the launch would silently re-aim the
    remediation at a different inventory — and a missing or unreadable report would dispatch a
    brief containing no findings at all, which is how an approved run quietly does nothing.
    """
    seed_proposal(results_dir, make_report([make_finding("approved/finding")]), remediation)
    gate.approve(by="controller", results_dir=results_dir, do_dispatch=False, use_redis=False)

    # A watchdog pass lands underneath the standing signature, reporting different drift.
    (results_dir / watchdog.LATEST_FILE).write_text(
        json.dumps(make_report([make_finding("unrelated/later")])))

    submit = Submitter()
    decision = gate.dispatch(results_dir=results_dir, workdir=str(workdir_root / "wt"),
                             submit_fn=submit, use_redis=False)

    assert decision.outcome == "dispatched"
    goal = submit.calls[0]["goal"]
    assert "approved/finding" in goal, "the approved inventory must be the brief"
    assert "unrelated/later" not in goal, "a later scan must not re-aim an approved run"


# ═════════════════════════════════════════════════════════════════════════════════════════════
# DIRECTION 2 — an APPROVED gate enqueues exactly the remediation, ONCE
# ═════════════════════════════════════════════════════════════════════════════════════════════


def test_approve_enqueues_exactly_the_remediation_once(results_dir, remediation, workdir_root):
    """The headline property: one approval, one enqueue, and it is the right workflow."""
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    submit = Submitter()

    decision = gate.approve(by="controller", reason="signed", results_dir=results_dir,
                            workdir=str(workdir_root / "wt_docs"), submit_fn=submit,
                            use_redis=False)

    assert decision.outcome == "dispatched"
    assert decision.enqueued is True
    assert len(submit.calls) == 1, "exactly one enqueue"
    # …and it enqueued the REMEDIATION, not something else.
    assert submit.calls[0]["spec"] == gate.REMEDIATION_SPEC
    assert submit.calls[0]["model"] == remediation.model
    assert "a/1" in submit.calls[0]["goal"], "the drift inventory is the goal context"
    assert (results_dir / gate.RUN_LOCK_FILE).exists(), "the claim is held while in flight"
    assert gate.read_proposal(results_dir)["state"] == gate.PROPOSAL_IN_FLIGHT


def test_second_approval_while_in_flight_is_a_noop(results_dir, remediation, workdir_root):
    """THE idempotence assertion: approving again changes nothing and enqueues nothing."""
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    submit = Submitter()
    workdir = str(workdir_root / "wt_docs")
    gate.approve(by="controller", results_dir=results_dir, workdir=workdir, submit_fn=submit,
                 use_redis=False)
    approvals_before = (results_dir / gate.APPROVALS_FILE).read_text()
    runs_before = (results_dir / gate.RUNS_FILE).read_text()

    second = gate.approve(by="someone-else", results_dir=results_dir, workdir=workdir,
                          submit_fn=submit, use_redis=False)

    assert second.outcome == "already_in_flight"
    assert second.enqueued is False
    assert len(submit.calls) == 1, "the second approval must not enqueue a second remediation"
    assert (results_dir / gate.APPROVALS_FILE).read_text() == approvals_before, \
        "a no-op approval records no signature"
    assert (results_dir / gate.RUNS_FILE).read_text() == runs_before


def test_repeated_approvals_never_exceed_one_enqueue(results_dir, remediation, workdir_root):
    """Sequential hammering — five approvals, one run. The property under repetition."""
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    submit = Submitter()
    workdir = str(workdir_root / "wt_docs")

    outcomes = [
        gate.approve(by=f"c{i}", results_dir=results_dir, workdir=workdir, submit_fn=submit,
                     use_redis=False).outcome
        for i in range(5)
    ]

    assert outcomes[0] == "dispatched"
    assert set(outcomes[1:]) == {"already_in_flight"}
    assert len(submit.calls) == 1
    assert len((results_dir / gate.RUNS_FILE).read_text().strip().splitlines()) == 1


def test_concurrent_dispatch_claims_exactly_once(results_dir, remediation, workdir_root):
    """The ATOMICITY proof: eight threads race ``dispatch``; exactly one enqueues.

    This is what the ``O_CREAT | O_EXCL`` claim buys and a read-then-write check would not: the
    losers here may lose at the state read OR at the claim, and the property holds either way.
    """
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    gate.approve(by="controller", results_dir=results_dir, do_dispatch=False, use_redis=False)
    submit = Submitter()
    workdir = str(workdir_root / "wt_docs")
    barrier = threading.Barrier(8)
    outcomes: list[str] = []
    lock = threading.Lock()

    def racer() -> None:
        barrier.wait()  # release all eight at the same instant
        result = gate.dispatch(results_dir=results_dir, workdir=workdir, submit_fn=submit,
                               use_redis=False)
        with lock:
            outcomes.append(result.outcome)

    threads = [threading.Thread(target=racer) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(submit.calls) == 1, f"exactly one enqueue, got {len(submit.calls)}: {outcomes}"
    assert outcomes.count("dispatched") == 1
    assert set(outcomes) <= {"dispatched", "already_in_flight"}


def test_dispatch_without_an_approval_is_refused(results_dir, remediation, workdir_root):
    """Hard rule 3: a warranted proposal alone authorises nothing."""
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    submit = Submitter()

    decision = gate.dispatch(results_dir=results_dir, workdir=str(workdir_root / "wt"),
                             submit_fn=submit, use_redis=False)

    assert decision.outcome == "refused_no_approval"
    assert decision.enqueued is False
    assert submit.calls == []
    assert not (results_dir / gate.RUN_LOCK_FILE).exists()


def test_an_approval_for_different_drift_is_refused(results_dir, remediation, workdir_root):
    """New drift after the signature makes the approval stale — the controller is asked again.

    This is the reason ``proposal_id`` fingerprints the finding SET. Without it, a signature given
    for four cosmetic anchors would silently authorise a run against a completely different, much
    larger inventory the controller never saw.
    """
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    gate.approve(by="controller", results_dir=results_dir, do_dispatch=False, use_redis=False)
    signed_id = gate.read_proposal(results_dir)["proposal_id"]

    # Drift changes underneath the standing signature.
    seed_proposal(results_dir, make_report([make_finding("a/1"), make_finding("b/2")]), remediation)
    assert gate.read_proposal(results_dir)["proposal_id"] != signed_id

    submit = Submitter()
    decision = gate.dispatch(results_dir=results_dir, workdir=str(workdir_root / "wt"),
                             submit_fn=submit, use_redis=False)

    assert decision.outcome == "refused_stale_approval"
    assert submit.calls == []


def test_a_re_scan_of_the_same_drift_keeps_the_signature(results_dir, remediation, workdir_root):
    """The other side of the fingerprint rule: an hourly re-scan must not invalidate a signature.

    The watchdog re-scans every hour; if measuring the same problem again retired the approval,
    the controller would be racing the timer and the affordance would be unusable in practice.
    """
    report = make_report([make_finding("a/1")], git_sha="sha-one")
    seed_proposal(results_dir, report, remediation)
    gate.approve(by="controller", results_dir=results_dir, do_dispatch=False, use_redis=False)

    # Same findings, later commit — the id must not move, and the approval must survive.
    again = seed_proposal(results_dir, make_report([make_finding("a/1")], git_sha="sha-two"),
                          remediation)
    assert again.state == gate.PROPOSAL_APPROVED
    assert again.proposal["approval"]["by"] == "controller"

    submit = Submitter()
    decision = gate.dispatch(results_dir=results_dir, workdir=str(workdir_root / "wt"),
                             submit_fn=submit, use_redis=False)
    assert decision.outcome == "dispatched"
    assert len(submit.calls) == 1


def test_approve_with_a_mismatched_proposal_id_is_refused(results_dir, remediation, workdir_root):
    """The portal affordance echoes the id it rendered; a moved proposal is refused, not applied."""
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    submit = Submitter()

    decision = gate.approve(by="controller", proposal_id="not-the-standing-one",
                            results_dir=results_dir, workdir=str(workdir_root / "wt"),
                            submit_fn=submit, use_redis=False)

    assert decision.outcome == "refused_stale_approval"
    assert submit.calls == []
    assert not (results_dir / gate.APPROVALS_FILE).exists()


def test_approving_when_nothing_is_proposed_is_refused(results_dir, remediation):
    """You cannot pre-authorise. Approval is a signature on a specific standing inventory."""
    seed_proposal(results_dir, make_report([]), remediation)
    submit = Submitter()

    decision = gate.approve(by="controller", results_dir=results_dir, submit_fn=submit,
                            use_redis=False)

    assert decision.outcome == "refused_no_proposal"
    assert submit.calls == []


def test_a_failed_enqueue_rolls_the_claim_back(results_dir, remediation, workdir_root):
    """A claim that guards nothing must not wedge the rail — and a retry must then work."""
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    workdir = str(workdir_root / "wt")
    exploding = Submitter(explode=RuntimeError("redis is down"))

    failed = gate.approve(by="controller", results_dir=results_dir, workdir=workdir,
                          submit_fn=exploding, use_redis=False)

    assert failed.outcome == "dispatch_failed"
    assert failed.enqueued is False
    assert not (results_dir / gate.RUN_LOCK_FILE).exists(), "the claim must be rolled back"

    # The signature is on record and the rail is dispatchable again.
    healthy = Submitter()
    retry = gate.dispatch(results_dir=results_dir, workdir=workdir, submit_fn=healthy,
                          use_redis=False)
    assert retry.outcome == "dispatched"
    assert len(healthy.calls) == 1


def test_release_frees_the_claim_and_records_the_terminal_state(results_dir, remediation,
                                                                workdir_root):
    """``release`` is the only thing that retires a run — deliberately manual."""
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    submit = Submitter()
    gate.approve(by="controller", results_dir=results_dir, workdir=str(workdir_root / "wt"),
                 submit_fn=submit, use_redis=False)

    decision = gate.release(status=gate.PROPOSAL_COMPLETED, note="gate passed",
                            results_dir=results_dir, use_redis=False)

    assert decision.outcome == "released"
    assert decision.state == gate.PROPOSAL_COMPLETED
    assert not (results_dir / gate.RUN_LOCK_FILE).exists()
    lines = [json.loads(x) for x in
             (results_dir / gate.RUNS_FILE).read_text().strip().splitlines()]
    assert [x["status"] for x in lines] == [gate.PROPOSAL_IN_FLIGHT, gate.PROPOSAL_COMPLETED]


def test_release_without_a_claim_is_a_noop(results_dir, remediation):
    """Nothing held, nothing to free — reported, not raised."""
    decision = gate.release(results_dir=results_dir, use_redis=False)
    assert decision.outcome == "not_held"


def test_command_mode_claims_but_reports_nothing_enqueued(results_dir, remediation, workdir_root):
    """The in-process fallback still holds the claim (so "once" holds) and says so honestly."""
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    submit = Submitter()

    decision = gate.approve(by="controller", results_dir=results_dir, mode=gate.DISPATCH_COMMAND,
                            workdir=str(workdir_root / "wt"), submit_fn=submit, use_redis=False)

    assert decision.outcome == "dispatched"
    assert decision.enqueued is False, "recording a command is not queueing work"
    assert submit.calls == []
    assert (results_dir / gate.RUN_LOCK_FILE).exists()
    assert decision.run["command"][:2] == ["python3", "scripts/run_workflow.py"]


def test_approve_no_dispatch_records_only_the_signature(results_dir, remediation):
    """Sign now, launch later — the signature is durable and the claim is untouched."""
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)

    decision = gate.approve(by="controller", reason="will launch tomorrow",
                            results_dir=results_dir, do_dispatch=False, use_redis=False)

    assert decision.outcome == "approved"
    assert decision.enqueued is False
    assert not (results_dir / gate.RUN_LOCK_FILE).exists()
    assert gate.read_approval(results_dir)["by"] == "controller"


def test_a_workdir_outside_the_worktree_root_is_refused(results_dir, remediation, workdir_root,
                                                        tmp_path):
    """The orchestrator's rule, enforced early — where the controller can read the reason."""
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    gate.approve(by="controller", results_dir=results_dir, do_dispatch=False, use_redis=False)
    submit = Submitter()

    decision = gate.dispatch(results_dir=results_dir, workdir=str(tmp_path / "elsewhere"),
                             submit_fn=submit, use_redis=False)

    assert decision.outcome == "refused_bad_workdir"
    assert submit.calls == []
    assert not (results_dir / gate.RUN_LOCK_FILE).exists()


# ═════════════════════════════════════════════════════════════════════════════════════════════
# The contracts the two directions rest on
# ═════════════════════════════════════════════════════════════════════════════════════════════


def test_proposal_id_tracks_findings_not_the_commit():
    """The fingerprint rule, stated directly."""
    a = gate.compute_proposal_id("rem", ["x", "y"])
    assert a == gate.compute_proposal_id("rem", ["y", "x"]), "order must not matter"
    assert a != gate.compute_proposal_id("rem", ["x", "y", "z"]), "a new finding is a new proposal"
    assert a != gate.compute_proposal_id("other", ["x", "y"]), "a different remediation differs"


def test_the_approval_authority_is_the_file_not_redis(results_dir, remediation, workdir_root):
    """A forged live key cannot authorise a spend; only ``approvals.jsonl`` can.

    If the Redis mirror were authoritative, anything able to write db1 could authorise a
    remediation run, and a ``flushdb`` could erase a signature the audit trail must keep.
    """
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    proposal_id = gate.read_proposal(results_dir)["proposal_id"]

    class ForgedRedis:
        """Claims the proposal is approved. The gate must not believe it."""

        def __init__(self) -> None:
            self.store = {gate.APPROVAL_KEY: json.dumps({"proposal_id": proposal_id,
                                                         "by": "an-impostor"})}

        def get(self, key):
            return self.store.get(key)

        def set(self, key, value):
            self.store[key] = value

    submit = Submitter()
    decision = gate.dispatch(results_dir=results_dir, workdir=str(workdir_root / "wt"),
                             submit_fn=submit, client=ForgedRedis(), use_redis=True)

    assert decision.outcome == "refused_no_approval"
    assert submit.calls == []


def test_an_unreadable_claim_still_blocks(results_dir, remediation, workdir_root):
    """The lock's EXISTENCE is the lock; its contents are only description.

    Treating a corrupt lock as absent would allow exactly the double dispatch it exists to
    prevent, so the corrupt case fails closed.
    """
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    gate.approve(by="controller", results_dir=results_dir, do_dispatch=False, use_redis=False)
    (results_dir / gate.RUN_LOCK_FILE).write_text("{ not json")
    submit = Submitter()

    decision = gate.dispatch(results_dir=results_dir, workdir=str(workdir_root / "wt"),
                             submit_fn=submit, use_redis=False)

    assert decision.outcome == "already_in_flight"
    assert submit.calls == []


def test_an_expired_claim_is_reported_but_never_auto_broken(results_dir, remediation,
                                                            workdir_root):
    """Auto-breaking a stale claim is how a rail double-launches. It is surfaced instead."""
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    submit = Submitter()
    gate.approve(by="controller", results_dir=results_dir, workdir=str(workdir_root / "wt"),
                 submit_fn=submit, use_redis=False)
    # Backdate the claim well past its TTL.
    claim = json.loads((results_dir / gate.RUN_LOCK_FILE).read_text())
    claim["at"] = "2020-01-01T00:00:00Z"
    (results_dir / gate.RUN_LOCK_FILE).write_text(json.dumps(claim))

    assert gate.claim_is_expired(gate.read_claim(results_dir)) is True
    retry = gate.dispatch(results_dir=results_dir, workdir=str(workdir_root / "wt"),
                          submit_fn=submit, use_redis=False)

    assert retry.outcome == "already_in_flight"
    assert "past its expiry" in retry.detail
    assert len(submit.calls) == 1, "the expired claim still blocks"
    assert (results_dir / gate.RUN_LOCK_FILE).exists()


def test_status_is_a_pure_read(results_dir, remediation):
    """A dashboard poll must never change the state it displays."""
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    before = sorted(p.name for p in results_dir.iterdir())
    snapshot = (results_dir / gate.PROPOSAL_FILE).read_text()

    decision = gate.status(results_dir=results_dir)

    assert decision.state == gate.PROPOSAL_WARRANTED
    assert decision.written == []
    assert sorted(p.name for p in results_dir.iterdir()) == before
    assert (results_dir / gate.PROPOSAL_FILE).read_text() == snapshot


def test_propose_stands_down_while_a_run_is_in_flight(results_dir, remediation, workdir_root):
    """A re-scan mid-run does not disturb the standing run or its record."""
    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    submit = Submitter()
    gate.approve(by="controller", results_dir=results_dir, workdir=str(workdir_root / "wt"),
                 submit_fn=submit, use_redis=False)
    in_flight = gate.read_proposal(results_dir)

    decision = seed_proposal(results_dir, make_report([make_finding("c/9")]), remediation)

    assert decision.outcome == "already_in_flight"
    assert decision.enqueued is False
    assert "inventory has since changed" in decision.detail
    assert gate.read_proposal(results_dir) == in_flight


# ═════════════════════════════════════════════════════════════════════════════════════════════
# Wiring — the board row, the CLI, and the fixture's fidelity to the real scanner
# ═════════════════════════════════════════════════════════════════════════════════════════════


def test_board_row_renders_the_gate_proposal_state(results_dir, remediation):
    """p2's level row picks the proposal up from the gate's file rather than pinning "none".

    Without this, the watchdog's hourly wholesale rewrite of ``fleet:docs_drift`` would erase the
    proposal state from the board within the hour — the row and the gate would disagree, and the
    p4 panel reads the row.
    """
    import scan_docs_drift

    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    report = scan_docs_drift.DriftReport()

    bare = watchdog.build_board_row(report, state=watchdog.STATE_RAISED, since="t0")
    assert bare["proposal_state"] == "none", "no proposal file ⇒ none, never a fabrication"

    wired = watchdog.build_board_row(report, state=watchdog.STATE_RAISED, since="t0",
                                     proposal=watchdog.read_proposal(results_dir))
    assert wired["proposal_state"] == gate.PROPOSAL_WARRANTED
    assert wired["proposed_action"]["spec"] == gate.REMEDIATION_SPEC
    assert wired["proposed_action"]["budget_usd"] == remediation.budget_usd


def test_watchdog_run_once_publishes_the_gate_state(results_dir, remediation):
    """End to end through the watchdog's own pass: the row carries the standing proposal."""
    import scan_docs_drift

    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    result = watchdog.run_once(report=scan_docs_drift.DriftReport(), results_dir=results_dir,
                               use_redis=False)

    assert result.board_row["proposal_state"] == gate.PROPOSAL_WARRANTED
    assert result.board_row["proposal_id"] == gate.read_proposal(results_dir)["proposal_id"]


def test_cli_resolves_the_gate_verbs():
    """``agentic-dynamics docs gate <verb>`` forwards the verb to the script's own parser."""
    from agentic_dynamics import cli

    assert cli._resolve(["docs", "gate", "propose"]) == ("docs_proposal_gate.py", ["propose"])
    assert cli._resolve(["docs", "gate", "approve", "--by", "x"]) == (
        "docs_proposal_gate.py", ["approve", "--by", "x"])
    assert cli._resolve(["docs", "watch"]) == ("docs_drift_watchdog.py", [])


def test_report_shape_matches_the_scanner():
    """The hand-built fixture must stay faithful to what the scanner actually emits.

    Every test above runs against :func:`make_report`. If the scanner's serialisation moved and
    this fixture did not, the whole file would be testing a shape that no longer exists — so the
    fixture's keys are checked against a REAL (empty) scan.
    """
    import scan_docs_drift

    real = scan_docs_drift.DriftReport().to_json()
    fake = make_report([])

    assert set(real) <= set(fake), f"fixture is missing report keys: {set(real) - set(fake)}"
    assert set(real["score"]) == set(fake["score"])


def test_the_gate_never_calls_a_model(monkeypatch, results_dir, remediation, workdir_root):
    """Hard rule 1 is inherited, and asserted structurally rather than assumed.

    The gate is a policy over the scanner's output; if it ever grew a model call, the rail's
    "deterministic, reproducible, free to run hourly" property would quietly die. Any subprocess
    at all is a failure here — the gate shells out to nothing.
    """
    import subprocess

    def forbidden(*args, **kwargs):
        raise AssertionError(f"the gate spawned a subprocess: {args!r}")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "check_output", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)

    seed_proposal(results_dir, make_report([make_finding("a/1")]), remediation)
    gate.approve(by="controller", results_dir=results_dir, workdir=str(workdir_root / "wt"),
                 submit_fn=Submitter(), use_redis=False)
    gate.release(results_dir=results_dir, use_redis=False)
    gate.status(results_dir=results_dir)
