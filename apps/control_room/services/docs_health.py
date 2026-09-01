"""Docs-health service — "is the docs current?" as a number, for the Control Room panel.

The fourth and last role of the docs-drift rail. The three that precede it each own one verb:

    p1  ``scripts/scan_docs_drift.py``      the INSTRUMENT — measures, has no opinion
    p2  ``scripts/docs_drift_watchdog.py``  the CADENCE + OBSERVATION RAIL — observes, notifies,
                                            has no authority
    p3  ``scripts/docs_proposal_gate.py``   the POLICY — proposes, and on an explicit signature
                                            dispatches

This module is the SURFACE. It owns no verb at all. It reads what the three wrote and composes
one envelope a browser can render, which is why every function here is a pure read of durable
state: a dashboard poll must never be able to change the state it is displaying. That sentence is
p3's, from :func:`scripts.docs_proposal_gate.status`, and it is the load-bearing constraint on
this file — an operator watching the panel must be able to leave the tab open for a week without
that fact altering a single byte of the rail.

WHAT IT READS (all three are durable files; Redis is nowhere in this module)

* ``latest.json``     — p2's LEVEL report: the last scan's score, per-axis counts, findings.
* ``flag_state.json`` — p2's flag lifecycle: raised / clear / unmeasured, and since when.
* ``proposal.json``   — p3's standing proposal, read through the gate's own :func:`status`
                        rather than re-parsed here, so the panel and ``docs gate status``
                        can never disagree about what state the gate holds.

"COULD NOT MEASURE" IS NOT "CLEAN" — the refusal every layer of this rail makes, made again here.
An absent or errored report yields ``unmeasured``, never ``clean``. The two are indistinguishable
on a dashboard by colour alone and only one of them is safe to act on, so they get different words
and different affordances: ``unmeasured`` shows no approve button, because there is no trustworthy
inventory to approve.

Public surface:
    :func:`resolve_condition` / :func:`CONDITIONS`  — the three-state (plus unmeasured) vocabulary
    :func:`load_docs_health`                        — the whole envelope the route serves
    :func:`approve_proposal`                        — the one mutating call, delegated to p3
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from scripts import docs_drift_watchdog as watchdog
from scripts import docs_proposal_gate as gate

#: Schema tag on the envelope. Versioned like ``subscription-usage/v3`` so a client can tell,
#: from the payload alone, which contract it is looking at.
SCHEMA = "docs-health/v1"

#: How many finding rows the envelope carries. The full inventory lives in ``latest.json`` (and
#: is named on the envelope as ``scan.report``); the panel only ever renders a summary plus the
#: head of the list, and a 1000-finding response on a 60s poll would be a self-inflicted denial
#: of service. Truncation is reported (``inventory_truncated``), never silent — a list that
#: quietly stops is a list an operator reads as complete.
INVENTORY_LIMIT = 25

# ─────────────────────────────────────────────────────────────────────────────────────────────
# The vocabulary: four conditions, three colours
# ─────────────────────────────────────────────────────────────────────────────────────────────

#: The panel's condition vocabulary.
#:
#: Each entry carries a ``color`` (the green/yellow/red the panel paints), a ``word`` (what a
#: screen reader announces and what the CLI prints) and a ``headline`` template. Colour is NEVER
#: the only signal — that is ``board-fleet.js``'s standing doctrine for this portal, and it is
#: what makes ``warranted`` and ``unmeasured`` distinguishable even though both are red.
#:
#: The ordering below is the escalation order, worst last.
CONDITIONS: dict[str, dict[str, str]] = {
    # Measured, and every anchored claim reproduces. The only state that means "the docs are
    # current" — and the only one reachable from a scan that actually ran.
    "clean": {"color": "green", "word": "CURRENT", "glyph": "✓"},
    # Measured, drift found, but no proposal stands: the machine has something to show and
    # nothing to ask for. The inventory summary is the whole point of this state.
    "findings": {"color": "yellow", "word": "DRIFTED", "glyph": "▲"},
    # A proposal stands (warranted / approved / in_flight): the remediation is visible and the
    # controller's signature is the next move. This is the only state with an approve affordance.
    "warranted": {"color": "red", "word": "WARRANTED", "glyph": "◆"},
    # The rail could not measure — an errored axis, or no scan on record at all. Red because a
    # blind rail is not a healthy one, and deliberately NOT approvable.
    "unmeasured": {"color": "red", "word": "UNMEASURED", "glyph": "?"},
}

#: Proposal states in which something is actually being asked of, or done for, the controller.
#: ``completed`` and ``failed`` are terminal records of a past decision — they are history, not a
#: standing request, so they fall back to whatever the CURRENT scan says.
STANDING_PROPOSAL_STATES = (
    gate.PROPOSAL_WARRANTED,
    gate.PROPOSAL_APPROVED,
    gate.PROPOSAL_IN_FLIGHT,
)


def resolve_condition(*, measured: bool, drift: int, proposal_state: str) -> str:
    """Map (scan measured?, drift count, proposal state) onto one condition word.

    The order of the tests is the priority order, and each precedence is a decision:

    1. ``unmeasured`` wins over everything. A standing proposal raised against last week's
       inventory must not let a rail that has since gone blind render as if it still knows what
       is true. The proposal is still surfaced in the envelope — it is simply not the headline,
       and not approvable, because approving spends money against an inventory nobody can
       currently confirm.
    2. A standing proposal outranks a bare finding count. Both mean "there is drift", but only
       one of them is *asking the controller for something*, and the panel's job is to make the
       ask visible.
    3. Otherwise the drift count decides, exactly as the watchdog's flag does.

    Note the deliberate relationship to ``docs_drift_watchdog.build_board_row``'s ``health``:
    with no proposal standing, this function's colour is IDENTICAL to the board row's
    (clear→green, raised→yellow, unmeasured→red). The two surfaces can only diverge on the axis
    the board row does not model — whether a proposal stands — and ``tests/test_docs_health.py``
    pins that agreement, so the panel and the supervisor board can never quietly disagree about
    what a score means.
    """
    if not measured:
        return "unmeasured"
    if proposal_state in STANDING_PROPOSAL_STATES:
        return "warranted"
    return "findings" if drift > 0 else "clean"


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Reading the rail
# ─────────────────────────────────────────────────────────────────────────────────────────────


def _int_or_none(value: Any) -> int | None:
    """Coerce to int, or None when the value is not a number at all.

    The strict sibling of :func:`_as_int`. Used where the DIFFERENCE between "this field said 0"
    and "this field could not be read" changes the answer — which, for a health panel, is the
    difference between reporting clean and admitting it does not know.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any, default: int = 0) -> int:
    """Coerce a report field to an int, or fall back to ``default``.

    Every number the panel prints comes out of a JSON file the panel does not write, so each one
    is a place a corrupt or half-written document could otherwise raise ``ValueError`` mid-render
    and turn a docs problem into a portal outage. The scanner and the watchdog are the authorities
    for these values being correct; this module's only job is to be unable to crash on them.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _score_is_substantive(report: dict) -> bool:
    """True when the report carries a score that actually counts something.

    A guard against a false CLEAN, which is the one wrong answer this panel must never give.
    :func:`scripts.docs_proposal_gate.report_is_measured` asks "did every axis run?" by testing
    for the *absence* of errors — so a structurally malformed report (a dict with no ``score``,
    or a score that checked nothing) passes it vacuously and would arrive here as drift 0, i.e.
    as green. That is the same class of failure as treating an absent report as clean, and it
    gets the same answer: a scan that checked nothing has not measured anything.
    """
    score = report.get("score")
    if not isinstance(score, dict):
        return False
    # ``drift`` is the number the entire verdict hangs on, so it is checked for READABILITY, not
    # only for its value. Without this, a wrong-typed drift (a list, a null, a word) falls back
    # through ``_as_int`` to 0 and the panel paints GREEN — a report that plainly failed to say
    # what it found, rendered as a report that found nothing. Same false-clean class as an absent
    # scan, reached by a different route.
    if _int_or_none(score.get("drift")) is None:
        return False
    return _as_int(score.get("total_checked")) > 0


def _scan_block(report: dict | None, flag_doc: dict) -> dict[str, Any]:
    """Normalise p2's ``latest.json`` into the flat block the panel paints.

    Returns a block with ``measured: False`` when there is no usable report — when the file is
    absent (the rail has never run here), when an axis errored, and when the report is present
    but structurally unusable. Those are different *causes* and are named separately in
    ``reason``, but they are one *state*: not having looked can never be allowed to render as
    looked-and-found-nothing.

    Args:
        report: p2's ``latest.json``, or None when absent/unparseable.
        flag_doc: p2's ``flag_state.json``. Consulted ONLY for the scan timestamp: ``latest.json``
            carries no stamp of its own, and ``write_flag_state`` runs in the same pass that
            writes the report (both are level surfaces, rewritten every cycle by the one writer
            systemd will not run concurrently with itself). So the flag doc's ``at`` *is* the
            last-scan time — taking it from there is honest, and inventing a stamp from the
            file's mtime would be a second, quietly different answer to the same question.
    """
    scanned_at = str(flag_doc.get("at", ""))
    if not report:
        return {
            "measured": False,
            "reason": "no docs-drift scan on record — run `agentic-dynamics docs watch`",
            "at": scanned_at,
            "git_sha": "",
            "drift": 0,
            "stale": 0,
            "missing": 0,
            "checked": 0,
            "per_axis": {},
            "axes_errored": [],
            "report": watchdog.LATEST_REPORT_REL,
        }

    # Every field below is coerced by TYPE, not just by truthiness. ``x or {}`` rescues a
    # missing or empty value but happily passes a wrong-typed one straight through to a
    # ``.get`` that does not exist on it — and a malformed report is precisely the input this
    # block exists to survive. A panel that 500s on a corrupt file reports the panel's health.
    score = report.get("score")
    score = score if isinstance(score, dict) else {}
    per_axis = score.get("per_axis")
    per_axis = per_axis if isinstance(per_axis, dict) else {}
    axes_errored_raw = score.get("axes_errored")
    # Elements are stringified, not just collected: they are put through ``set()`` below, and an
    # unhashable element from a corrupt report would raise there — the same crash class, one
    # layer down.
    axes_errored = (
        [str(axis) for axis in axes_errored_raw]
        if isinstance(axes_errored_raw, (list, tuple))
        else []
    )
    # ``report_is_measured`` is p3's predicate, reused rather than re-implemented: the gate and
    # the panel must agree on what "measurable" means, or the panel would show an approve button
    # for an inventory the gate will refuse to act on. The structural check is this module's
    # own addition — see :func:`_score_is_substantive`.
    measured = gate.report_is_measured(report) and _score_is_substantive(report)
    errors_raw = report.get("errors")
    errors = errors_raw if isinstance(errors_raw, dict) else {}
    if measured:
        reason = ""
    elif axes_errored or errors:
        named = ", ".join(sorted(set(axes_errored) | set(errors))) or "unknown axis"
        reason = f"scan incomplete — axes errored: {named}"
    else:
        reason = "scan report carries no counted checks — treating it as unmeasured, not clean"

    return {
        "measured": measured,
        "reason": reason,
        "at": scanned_at,
        "git_sha": str(report.get("git_sha", "")),
        "drift": _as_int(score.get("drift")),
        "stale": _as_int(score.get("total_stale")),
        "missing": _as_int(score.get("total_missing")),
        "checked": _as_int(score.get("total_checked")),
        # Per-axis drift only (not the full current/stale/missing triple): the panel renders one
        # number per axis, and the triple is a click away in the report the block names.
        "per_axis": {
            str(axis): _as_int(body.get("drift")) if isinstance(body, dict) else 0
            for axis, body in per_axis.items()
        },
        "axes_errored": axes_errored,
        "report": watchdog.LATEST_REPORT_REL,
    }


def _flag_block(state_doc: dict) -> dict[str, Any]:
    """Normalise p2's flag lifecycle into the block the panel paints.

    ``raised`` is the observation rail's answer to "has a human been told?" — distinct from the
    scan's answer to "is there drift?", because the flag is EDGE-triggered (raised once and held)
    while the scan is LEVEL state (rewritten every pass). Surfacing both lets an operator see
    that a finding is known and standing, rather than new this hour.
    """
    return {
        "state": str(state_doc.get("state", watchdog.STATE_CLEAR)),
        "raised": str(state_doc.get("state", "")) == watchdog.STATE_RAISED,
        "since": str(state_doc.get("since", "")),
        "at": str(state_doc.get("at", "")),
        "why": str(state_doc.get("why", "")),
        "drift": _as_int(state_doc.get("drift")),
    }


def _inventory(report: dict | None, limit: int = INVENTORY_LIMIT) -> tuple[list[dict], bool]:
    """Return up to ``limit`` finding rows plus whether the list was cut.

    Each row keeps its ``basis`` — the string naming how to re-derive the finding by hand. That
    is p1's hard rule 4 carried all the way to the browser: an operator asked to sign off on
    spending money against this inventory can check any row without trusting the machine that
    produced it. Dropping ``basis`` to save bytes would make the panel an assertion instead of
    evidence.
    """
    findings = gate.findings_of(report or {})
    rows = [
        {
            "check_id": str(row.get("check_id", "")),
            "axis": str(row.get("axis", "")),
            "status": str(row.get("status", "")),
            "source": str(row.get("source", "")),
            "claim": str(row.get("claim", "")),
            "code_truth": str(row.get("code_truth", "")),
            "basis": str(row.get("basis", "")),
        }
        for row in findings[:limit]
    ]
    return rows, len(findings) > limit


def _proposal_block(decision: gate.GateDecision, *, measured: bool) -> dict[str, Any]:
    """Normalise p3's :func:`status` decision into the block the panel paints.

    ``approvable`` is computed here rather than in the browser for the same reason the watchdog
    computes ``health`` server-side: the CLI, the board, and the portal must not be able to
    disagree about whether a signature is currently accepted. It is the AND of three conditions,
    each of which is independently a reason the gate would refuse:

    * the scan is measured (approving against an unconfirmable inventory spends money on a guess),
    * the proposal is in ``warranted`` (``approved`` is already signed; ``in_flight`` is already
      running — offering the button in either state would invite a click whose only possible
      outcome is a no-op),
    * no run currently holds the claim.

    A False here hides the button. It is a *presentation hint*, and the split with the actual
    enforcement is worth stating precisely rather than hand-waving:

    * the proposal state and the claim ARE re-enforced server-side, by the gate, at approve time
      (``already_in_flight`` and ``refused_no_proposal``), so hiding the button is belt-and-braces
      for those two;
    * ``measured`` is NOT re-enforced by the gate, and deliberately so. p3 FREEZES the finding
      rows a proposal was raised on, and the approval binds to those rows — so a scan that has
      since gone blind does not invalidate a standing proposal, it only means the panel cannot
      currently *re-confirm* it. Hiding the affordance is the right caution; refusing a deliberate
      POST would be this surface inventing a policy, and the surface owns no verb.
    """
    proposal = decision.proposal or {}
    action = proposal.get("action") or {}
    approval = proposal.get("approval") or {}
    run = decision.run or {}
    return {
        "state": decision.state,
        "proposal_id": decision.proposal_id,
        "drift": decision.drift,
        "threshold": decision.threshold,
        "why": str(proposal.get("why", "")),
        "detail": decision.detail,
        "at": str(proposal.get("at", "")),
        "finding_count": _as_int(proposal.get("finding_count")),
        "action": {
            "name": str(action.get("name", "")),
            "spec": str(action.get("spec", "")),
            "model": str(action.get("model", "")),
            "budget_usd": float(action.get("budget_usd", 0.0) or 0.0),
            "phases": list(action.get("phases") or []),
            # The derivation of every number above, as recorded by the gate. Same discipline as
            # a finding's ``basis``: the estimate is checkable, not asserted.
            "basis": str(action.get("basis", "")),
        },
        "approved_by": str(approval.get("by", "")),
        "approved_at": str(approval.get("at", "")),
        "run": {
            "run_id": str(run.get("run_id", "")),
            "at": str(run.get("at", "")),
            "status": str(run.get("status", "")),
            "job_id": str(run.get("job_id", "")),
            "workdir": str(run.get("workdir", "")),
        },
        "approvable": bool(
            measured
            and decision.state == gate.PROPOSAL_WARRANTED
            and not run
        ),
    }


def _headline(condition: str, scan: dict, proposal: dict) -> str:
    """One sentence naming the state, for the panel's summary line and for a screen reader.

    Written per condition rather than templated from the numbers, because the four states are
    answering four different questions and a single template would answer none of them well.
    """
    if condition == "unmeasured":
        return scan["reason"] or "the docs-drift rail could not measure"
    if condition == "clean":
        return (
            f"docs current — {scan['checked']} anchored claims reproduce "
            f"against the code at {scan['git_sha'][:9] or 'HEAD'}"
        )
    axes = ", ".join(
        f"{axis} {count}"
        for axis, count in sorted(scan["per_axis"].items(), key=lambda kv: (-kv[1], kv[0]))
        if count
    )
    summary = (
        f"{scan['drift']} drift finding(s) of {scan['checked']} checked"
        + (f" ({axes})" if axes else "")
    )
    if condition == "warranted":
        action = proposal["action"]
        return (
            f"{summary} — {action['name'] or 'remediation'} proposed "
            f"(~${action['budget_usd']:.2f}, {len(action['phases'])} phases), "
            f"{'awaiting the controller' if proposal['approvable'] else proposal['state']}"
        )
    return summary


def load_docs_health(
    results_dir: Path | None = None,
    *,
    inventory_limit: int = INVENTORY_LIMIT,
) -> dict[str, Any]:
    """Compose the whole ``docs-health/v1`` envelope. Reads three files, writes nothing.

    Args:
        results_dir: The rail's state directory. ``None`` means the production
            ``experiments/results/docs_drift``; tests point it at a tmp tree and thereby get
            complete isolation from the repo's real rail state with no monkeypatching.
        inventory_limit: Finding rows to carry. See :data:`INVENTORY_LIMIT`.

    Returns:
        The envelope. Never raises for a missing, empty, or malformed rail directory — a panel
        that 500s when the rail has not run yet would report the panel's health, not the docs'.
    """
    results_dir = results_dir or gate.RESULTS_DIR
    report = gate.read_latest_report(results_dir)
    flag_doc = watchdog.read_flag_state(results_dir)
    scan = _scan_block(report, flag_doc)
    flag = _flag_block(flag_doc)
    decision = gate.status(results_dir=results_dir)
    proposal = _proposal_block(decision, measured=scan["measured"])
    inventory, truncated = _inventory(report, inventory_limit)

    condition = resolve_condition(
        measured=scan["measured"],
        drift=scan["drift"],
        proposal_state=proposal["state"],
    )
    vocabulary = CONDITIONS[condition]

    return {
        "schema": SCHEMA,
        # ``available`` answers "did the rail produce anything at all?", which is a different
        # question from "is it healthy?". A rail that has never run is available=False AND
        # unmeasured; a rail whose last scan errored is available=True and unmeasured. The panel
        # tells those apart in its copy, so an operator knows whether to install the timer or
        # debug the scan.
        "available": report is not None,
        "condition": condition,
        "health": vocabulary["color"],
        "word": vocabulary["word"],
        "glyph": vocabulary["glyph"],
        "headline": _headline(condition, scan, proposal),
        "scan": scan,
        "flag": flag,
        "proposal": proposal,
        "inventory": inventory,
        "inventory_truncated": truncated,
        "inventory_limit": inventory_limit,
    }


# ─────────────────────────────────────────────────────────────────────────────────────────────
# The one mutating call
# ─────────────────────────────────────────────────────────────────────────────────────────────


def approve_proposal(
    *,
    by: str,
    proposal_id: str,
    reason: str = "",
    dispatch: bool = True,
    results_dir: Path | None = None,
    submit_fn: Callable[..., dict] | None = None,
) -> gate.GateDecision:
    """Record the controller's signature through p3's gate and return its verbatim decision.

    A thin delegation on purpose. Every rule that makes an approval safe — the attributed durable
    record, the proposal-id match, the ``already_in_flight`` guard, the ``O_EXCL`` claim that
    makes "runs once" a kernel guarantee rather than a hope — lives in
    :func:`scripts.docs_proposal_gate.approve`. Re-deriving any of it here would create a second,
    less-guarded way to spend money, which is exactly the failure mode p3's ``fleet_submit``
    docstring warns against.

    ``proposal_id`` is REQUIRED (p3 accepts ``None`` and skips the check; this surface does not).
    The browser echoes back the id it rendered, so an approval clicked against a proposal that
    changed underneath the operator is refused rather than silently applied to different findings.
    A panel is precisely where that race happens — the tab was open, the hourly timer fired.

    Args:
        by: Who is signing. Required by the gate; an unattributed approval is a state change.
        dispatch: False signs now and launches later (``approve --no-dispatch``).
        submit_fn: Injected enqueue function, forwarded to the gate. Production passes None (the
            real ``fleet:commands`` submit path); tests pass a double and count its calls — that
            count IS the approve-runs-once proof.
    """
    return gate.approve(
        by=by,
        reason=reason,
        proposal_id=proposal_id,
        results_dir=results_dir or gate.RESULTS_DIR,
        do_dispatch=dispatch,
        submit_fn=submit_fn,
    )
