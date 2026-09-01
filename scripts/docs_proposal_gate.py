#!/usr/bin/env python3
"""Docs-drift proposal gate — the machine proposes, the controller decides (``automatic_docs_sync`` p3).

WHAT THIS IS
------------
:mod:`scripts.scan_docs_drift` (p1) is the *instrument*: it turns "are the docs current?" into a
reproducible number. :mod:`scripts.docs_drift_watchdog` (p2) is the *cadence + rail*: it runs the
instrument unattended and carries its answer to the flags surface and the board. Neither of them
does anything about the drift they find — by contract (hard rule 2: drift is a finding, not a
verdict).

This module is the *policy*. It reads the watchdog's level report and answers one question:

    Is the drift bad enough that the ready-made remediation workflow should be RUN?

…and then, crucially, **does not run it**. It writes a proposal. The remediation is queued only
after the controller signs an explicit approval, and then exactly once.

THE THREE-PARTY SPLIT (why this is a separate module and not a watchdog flag)
------------------------------------------------------------------------------
* the **instrument** (p1) measures — it has no opinion,
* the **rail** (p2) observes and notifies — it has no authority,
* the **gate** (p3, here) proposes and, on an explicit signature, dispatches — it has authority
  but no initiative.

Keeping the third role in its own module is what makes "machine proposes, controller decides"
auditable rather than aspirational: every path that could possibly spend money lives in one file,
and there is exactly one function in it (:func:`dispatch`) that can enqueue anything.

HARD RULE 3, MECHANISED
-----------------------
The spec's hard rule 3 says the controller's approval is *required* before any remediation
workflow is queued. Three mechanisms enforce it here, and they are independent:

1. :func:`propose` has no code path that enqueues. Its :class:`GateDecision` carries
   ``enqueued=False`` unconditionally — the field exists so a test (and a reader) can assert the
   propose-without-running property directly rather than inferring it from an absence.
2. :func:`dispatch` refuses unless it finds an approval record whose ``proposal_id`` matches the
   *current* proposal. A stale approval — one the controller signed against a different drift
   inventory — is refused, not honoured. The controller approves **this** inventory, never
   "docs remediation" in the abstract.
3. The approval is an explicit, durable, attributed record (``approvals.jsonl`` + the
   ``docs:remediation:approved`` Redis key), not a mode, a flag file, or an env var.

APPROVE-RUNS-ONCE: AN ATOMIC FILESYSTEM CLAIM
-----------------------------------------------
The idempotence contract is "an approved gate enqueues exactly the remediation, once — a second
approval is a no-op while one is in flight". It is implemented by ``os.open(lock, O_CREAT |
O_EXCL)``: POSIX guarantees that exactly one caller creates the file and every other caller gets
``FileExistsError``. The winner dispatches; every loser reports ``already_in_flight`` and enqueues
nothing.

The claim is a FILE and not a Redis ``SET NX`` for the same reason the watchdog reads its prior
flag state from disk: Redis db1 is a live surface that can be flushed or restarted, and a claim
that evaporated on a Redis restart would let a second approval launch a second remediation
against the same worktree. The Redis key is a mirror for the portal; the file is the authority.

A claim is never broken automatically. A dispatch whose run died leaves the lock held, and
:func:`dispatch` reports it as ``already_in_flight`` (noting whether it is past its expiry) until
a human runs ``release``. Auto-breaking an expired claim is exactly how a rail double-launches a
remediation, so the stale case is surfaced and left to the controller — the same authority split
the rest of this module implements.

The one place the claim IS released automatically is a *failed* dispatch: if the claim is taken
and the enqueue then raises, the claim is rolled back before the error is reported. Otherwise a
transient Redis blip during submit would wedge the rail permanently behind a lock that guards
nothing.

WHAT "THE PROPOSAL" ACTUALLY IS
---------------------------------
A proposal names a specific set of findings. Its identity — ``proposal_id`` — is a hash over the
remediation spec's name plus the sorted ``check_id``s of the findings, and deliberately NOT over
the git SHA:

* the same drift measured at a later commit is the **same** proposal (a re-scan must not
  invalidate an approval the controller signed minutes ago), but
* a **different** set of findings is a **different** proposal (if new drift appears after the
  signature, the controller is asked again).

That is the whole point of binding approval to the fingerprint rather than to a boolean.

"COULD NOT MEASURE" IS NOT "NOTHING TO PROPOSE" (inherited from p1/p2)
------------------------------------------------------------------------
A report with errored axes yields the ``unmeasured`` outcome: the gate refuses to decide. It
neither raises a new proposal (there is no trustworthy inventory to attach) nor withdraws a
standing one (absence of evidence never retires a finding). A *missing* report is treated the
same way and is likewise never read as "clean" — a gate that proposed nothing because nobody had
scanned would be indistinguishable from a gate that proposed nothing because the docs were fine.

USAGE
-----
    python scripts/docs_proposal_gate.py status            # what does the gate currently hold?
    python scripts/docs_proposal_gate.py propose           # decide + surface; queues NOTHING
    python scripts/docs_proposal_gate.py propose --dry-run # the honest preview
    python scripts/docs_proposal_gate.py approve --by alice --reason "signed off 2026-09-01"
    python scripts/docs_proposal_gate.py approve --no-dispatch    # sign now, launch later
    python scripts/docs_proposal_gate.py dispatch          # launch a standing approval
    python scripts/docs_proposal_gate.py release --status completed

Exit codes:
    0  the verb did what it says (including "nothing warranted" and "already in flight" — a
       no-op that upholds the contract is a success, not an error).
    1  the verb was REFUSED (no proposal, stale approval, dispatch failed).
    2  the gate could not decide (no report, or an unmeasured one).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent

try:
    import _bootstrap  # noqa: F401  # direct run: scripts/ is sys.path[0]; inserts src/
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: F401

# The watchdog is a sibling script, not a package module. Importing it (rather than re-declaring
# its constants) is deliberate: the results directory, the report filename, the board key, the
# Redis connection contract and the UTC stamp format are ONE definition, owned by p2. The
# dependency runs gate -> watchdog and never back; p2 reads this module's proposal file by name,
# so there is no import cycle.
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import docs_drift_watchdog as watchdog  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────────────────────
# Contract constants — the keys, paths and vocabulary this gate owns
# ─────────────────────────────────────────────────────────────────────────────────────────────

#: The gate's durable surfaces, alongside the watchdog's (same directory: one rail, one place).
RESULTS_DIR = watchdog.RESULTS_DIR

#: The current proposal — LEVEL state, rewritten on every decision. Read by the watchdog when it
#: assembles the board row (``docs_drift_watchdog.read_proposal``) and by the p4 portal panel.
PROPOSAL_FILE = watchdog.PROPOSAL_FILE
#: One line per controller signature — EDGE, append-only. The audit trail of who authorised what.
APPROVALS_FILE = "approvals.jsonl"
#: One line per run lifecycle transition (dispatched / completed / failed) — EDGE, append-only.
RUNS_FILE = "runs.jsonl"
#: The atomic claim. Present on disk iff a remediation run is in flight. See the module docstring.
RUN_LOCK_FILE = "remediation.lock"

#: The controller's approval, mirrored live. This key name is fixed by the workflow spec.
APPROVAL_KEY = "docs:remediation:approved"
#: The current proposal, mirrored live for the portal.
PROPOSAL_KEY = "docs:remediation:proposal"
#: The in-flight run, mirrored live. A MIRROR — the lock file is the authority.
RUN_KEY = "docs:remediation:run"

#: The ready-made remediation this gate proposes: the F1-F5 acceptance-gate workflow that was
#: authored, executed and gate-passed on 2026-09-01. The gate proposes an EXISTING work order; it
#: never authors one, which is what makes the proposal reviewable before it is approved.
REMEDIATION_SPEC = "workflows/repository/docs_refresh_remediation.yaml"

#: Drift strictly ABOVE this is warranted. Default 0 ⇒ any finding warrants the proposal — which
#: is safe precisely because a proposal costs nothing: it queues no work and spends no money.
#: Thresholding higher trades earlier signal for fewer board rows, and is the controller's call.
DEFAULT_THRESHOLD = 0

#: How long a dispatched run may hold the claim before ``status``/``dispatch`` start calling it
#: stale. Sized off the remediation spec's own phase timeouts (4 phases, 5400s each = 6h) plus
#: headroom — a claim younger than this is presumed alive. Expiry is REPORTED, never acted on.
CLAIM_TTL_SECONDS = 8 * 3600

#: How many findings ride along in the dispatched goal text. The full inventory is always one
#: path away in ``latest.json`` (which the goal names); this bound keeps the prompt a brief, not
#: a data dump. Same reasoning as the watchdog's ``INVENTORY_LIMIT``.
GOAL_INVENTORY_LIMIT = 25

# ── the proposal-state vocabulary (the value the board row's ``proposal_state`` carries) ──
#: No proposal stands: the drift is at or below the threshold.
PROPOSAL_NONE = "none"
#: Drift crossed the threshold. The remediation is surfaced on the board. NOTHING is queued.
PROPOSAL_WARRANTED = "warranted"
#: The controller signed, but dispatch was deferred (``approve --no-dispatch``).
PROPOSAL_APPROVED = "approved"
#: The remediation has been enqueued and the claim is held.
PROPOSAL_IN_FLIGHT = "in_flight"
#: Terminal, recorded by ``release``.
PROPOSAL_COMPLETED = "completed"
PROPOSAL_FAILED = "failed"
#: The scan could not measure. The gate declines to decide in either direction.
PROPOSAL_UNMEASURED = "unmeasured"

#: The states in which a run holds the claim and no new dispatch may start.
ACTIVE_STATES = (PROPOSAL_IN_FLIGHT,)

#: Dispatch modes. ``fleet`` is the reference path (the containerised orchestrator, via the
#: existing ``fleet:commands`` submit); ``command`` is the documented in-process fallback, where
#: the gate still takes the claim (so "once" still holds) but records the ready-to-run command
#: line instead of queueing it, leaving the launch in the controller's hands.
DISPATCH_FLEET = "fleet"
DISPATCH_COMMAND = "command"
DISPATCH_MODES = (DISPATCH_FLEET, DISPATCH_COMMAND)


def now() -> str:
    """Canonical UTC stamp — the watchdog's format exactly, so the rail's records interleave."""
    return watchdog.now()


def log(msg: str) -> None:
    """Single-prefix stdout line, matching the watchdog's journal prefix family."""
    print(f"[docs-gate] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────────────────────────────────────


@dataclass
class GateDecision:
    """The outcome of one gate call — everything a caller, a test, or the portal needs.

    Attributes:
        verb: ``propose`` | ``approve`` | ``dispatch`` | ``release`` | ``status``.
        at: UTC stamp of the call.
        state: The proposal state AFTER this call.
        prior_state: The proposal state before it.
        proposal_id: Fingerprint of the finding set this decision concerns (``""`` when none).
        drift: The scanned stale+missing total this decision was made against.
        threshold: The threshold it was compared to.
        outcome: A short machine word naming what happened — the field to assert on.
        enqueued: **The propose-without-running proof.** True iff this call actually put work on
            a queue. :func:`propose` can never set it; only a successful :func:`dispatch` does.
        detail: One human sentence, for the log line and the portal.
        proposal: The proposal document as it now stands (``{}`` when none).
        run: The run record this call created or found (``{}`` when none).
        written: Repo-relative paths this call wrote (empty under ``--dry-run``).
        redis_available: False when the live mirrors were skipped; durable writes still ran.
    """

    verb: str
    at: str
    state: str
    prior_state: str
    proposal_id: str = ""
    drift: int = 0
    threshold: int = DEFAULT_THRESHOLD
    outcome: str = ""
    enqueued: bool = False
    detail: str = ""
    proposal: dict = field(default_factory=dict)
    run: dict = field(default_factory=dict)
    written: list[str] = field(default_factory=list)
    redis_available: bool = False

    def to_json(self) -> dict:
        """Serialise for ``--json`` and for the p4 route, which renders this shape directly."""
        return {
            "verb": self.verb,
            "at": self.at,
            "state": self.state,
            "prior_state": self.prior_state,
            "proposal_id": self.proposal_id,
            "drift": self.drift,
            "threshold": self.threshold,
            "outcome": self.outcome,
            "enqueued": self.enqueued,
            "detail": self.detail,
            "proposal": self.proposal,
            "run": self.run,
            "written": self.written,
            "redis_available": self.redis_available,
        }


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Reading the instrument's output
# ─────────────────────────────────────────────────────────────────────────────────────────────


def read_latest_report(results_dir: Path | None = None) -> dict | None:
    """Read the watchdog's level report (``latest.json``), or None when there isn't one.

    Returns None both when the file is absent and when it is unparseable, and the caller treats
    both as ``unmeasured`` rather than as ``clean``. This is the same refusal the scanner makes
    with an errored axis and the watchdog makes with an unmeasured pass: *not having looked* must
    never be able to render as *looked and found nothing*, because the two are indistinguishable
    on a dashboard and only one of them is safe to act on.
    """
    results_dir = results_dir or RESULTS_DIR
    path = results_dir / watchdog.LATEST_FILE
    if not path.exists():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def report_is_measured(report: dict) -> bool:
    """True when every requested axis ran — i.e. the report's drift score can be acted on.

    Mirrors ``docs_drift_watchdog.decide_state``'s ``unmeasured`` test. Kept as its own predicate
    because the gate consults it three times (propose, approve, dispatch) and each of those is a
    place where treating a partial scan as authoritative would spend money on a guess.
    """
    return not report.get("errors") and not (report.get("score") or {}).get("axes_errored")


def summarise_score(score: dict) -> str:
    """One sentence naming the drift total and the axes it came from.

    A score-dict twin of ``docs_drift_watchdog._summarise`` (which takes a live ``DriftReport``).
    The gate works from the serialised report on disk rather than from a fresh scan — it is a
    policy over the instrument's output, not a second instrument — so it needs this form.
    """
    drift = int(score.get("drift", 0))
    if not drift:
        return "docs-drift scan clean: every anchored claim reproduces against the code"
    hot = sorted(
        ((axis, int(b.get("drift", 0))) for axis, b in (score.get("per_axis") or {}).items()
         if b.get("drift")),
        key=lambda kv: (-kv[1], kv[0]),
    )
    axes = ", ".join(f"{a} {n}" for a, n in hot)
    return f"{drift} docs-drift finding(s) across {len(hot)} axis/axes ({axes})"


# ─────────────────────────────────────────────────────────────────────────────────────────────
# The remediation being proposed — read from the spec, never hardcoded
# ─────────────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Remediation:
    """The work order this gate proposes, as read from its own spec file.

    Every field here is *derived from the spec on disk* rather than written into this module. That
    is hard rule 4 (anchored or not merged) applied to the gate itself: the budget the board shows
    the controller is the number the run will actually be bounded by, re-derivable with
    ``grep '^stop:' workflows/repository/docs_refresh_remediation.yaml``. A hardcoded estimate
    would drift from the spec — which is precisely the failure class this whole rail exists to
    catch, and it would be embarrassing to reproduce it in the catcher.

    Attributes:
        spec: Repo-relative path of the spec.
        name: The spec's declared name.
        model: The model factor level the spec declares (the run's arm).
        budget_usd: ``stop.budget_usd`` — the budget estimate surfaced with the proposal.
        max_attempts: ``stop.max_attempts``.
        phases: The declared phase names, in order.
        basis: How to re-derive all of the above by hand.
    """

    spec: str
    name: str
    model: str
    budget_usd: float
    max_attempts: int
    phases: tuple[str, ...]
    basis: str

    def to_json(self) -> dict:
        """Board/portal projection — the 'proposed action' a controller reads before signing."""
        return {
            "spec": self.spec,
            "name": self.name,
            "model": self.model,
            "budget_usd": self.budget_usd,
            "max_attempts": self.max_attempts,
            "phases": list(self.phases),
            "basis": self.basis,
        }


def load_remediation(root: Path | None = None, spec_rel: str = REMEDIATION_SPEC) -> Remediation:
    """Parse the remediation spec into a :class:`Remediation`.

    Raises:
        FileNotFoundError: when the spec is missing. Deliberately fatal rather than degraded: a
            gate that proposed a workflow it could not find would surface an un-runnable action
            to the controller, and "the button did nothing" is worse than "the gate refused".
    """
    root = root or ROOT
    path = root / spec_rel
    if not path.exists():
        raise FileNotFoundError(f"remediation spec not found: {spec_rel}")

    import yaml

    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    stop = doc.get("stop") or {}

    # The model is a FACTOR LEVEL, not a config key — read it the way the compiler does, taking
    # the first level of the ``model`` factor. A grid with several model levels is not meaningful
    # for a one-shot remediation, so the first level is the arm.
    model = ""
    for factor in doc.get("factors") or []:
        if isinstance(factor, dict) and factor.get("name") == "model":
            levels = factor.get("levels") or []
            if levels:
                model = str(levels[0])
            break

    phases = tuple(
        str(p.get("name"))
        for p in (((doc.get("workflow") or {}).get("params") or {}).get("phases") or [])
        if isinstance(p, dict) and p.get("name")
    )

    return Remediation(
        spec=spec_rel,
        name=str(doc.get("name") or path.stem),
        model=model,
        budget_usd=float(stop.get("budget_usd") or 0.0),
        max_attempts=int(stop.get("max_attempts") or 1),
        phases=phases,
        basis=f"yaml: name/factors[model].levels[0]/stop/workflow.params.phases[].name in {spec_rel}",
    )


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Proposal identity
# ─────────────────────────────────────────────────────────────────────────────────────────────


def compute_proposal_id(spec_name: str, check_ids: list[str]) -> str:
    """Fingerprint a proposal: the remediation being proposed + the exact findings it addresses.

    The git SHA is deliberately EXCLUDED. Two consequences, both wanted:

    * the same findings measured again at a later commit hash to the same id, so an approval the
      controller signed minutes ago survives the next hourly scan (an approval invalidated by a
      re-measurement of the same problem would be unusable in practice — the watchdog re-scans
      every hour, and the controller would be racing it);
    * a different finding set hashes differently, so drift that appeared *after* the signature
      makes the standing approval stale and :func:`dispatch` asks again. The controller approved
      remediating the findings they were shown, not whatever the docs look like at dispatch time.

    ``check_id``s are sorted before hashing so the id depends on the SET of findings, not on the
    order the scanner happened to emit them in.
    """
    payload = spec_name + "\n" + "\n".join(sorted(check_ids))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def findings_of(report: dict) -> list[dict]:
    """The report's finding rows (defensively typed — a malformed report yields no findings)."""
    findings = report.get("findings")
    return [f for f in findings if isinstance(f, dict)] if isinstance(findings, list) else []


# ─────────────────────────────────────────────────────────────────────────────────────────────
# The goal context — the drift inventory, handed to the remediation as its brief
# ─────────────────────────────────────────────────────────────────────────────────────────────


def build_goal(proposal: dict, remediation: Remediation) -> str:
    """Compose the ``--goal`` text the remediation run is dispatched with.

    This is the "with the drift inventory as its goal context" half of the spec's dispatch clause.
    Each finding is rendered with all four of the scanner's anchored fields — claim, code truth,
    basis, source — because the *basis* is what lets the remediation agent re-derive the finding
    itself instead of trusting this brief. A goal that said only "9 anchors are stale" would send
    an agent hunting; a goal that says which anchors, what they point at, what the code actually
    says, and the one-line command that proves it, is a work order.

    **The inventory comes from the PROPOSAL, not from ``latest.json``.** That is the whole point:
    the watchdog rewrites the report every hour, so re-reading it at dispatch time would let the
    agent be briefed on a *different* set of findings than the controller signed for — and, if
    the report were missing or unreadable, would silently dispatch a brief with no findings at
    all. The proposal carries the finding rows it was raised on; the approval binds to those rows;
    the goal renders exactly them. (The full, current report is still NAMED for an agent that
    wants the rest, but it is context, not the brief.)

    Bounded at :data:`GOAL_INVENTORY_LIMIT` rows when the proposal is built, with the overflow
    counted. A prompt is a brief, not a database dump.
    """
    findings = [f for f in (proposal.get("findings") or []) if isinstance(f, dict)]
    total = int(proposal.get("finding_count", len(findings)))
    lines = [
        f"Execute the docs-refresh remediation ({remediation.name}) against the docs-drift "
        f"inventory measured by the deterministic scanner at "
        f"{proposal.get('git_sha', 'unknown')} (proposal {proposal.get('proposal_id', '')}).",
        "",
        f"DRIFT: {proposal.get('why', '')}",
        f"FULL INVENTORY: {proposal.get('report', watchdog.LATEST_REPORT_REL)} "
        f"(schema docs-drift/v1)",
        "",
        f"FINDINGS ({len(findings)} of {total}):",
    ]
    for finding in findings:
        lines += [
            f"  [{finding.get('status')}] {finding.get('check_id')}",
            f"      claim      : {finding.get('claim')}",
            f"      code truth : {finding.get('code_truth')}",
            f"      basis      : {finding.get('basis')}",
            f"      source     : {finding.get('source')}",
        ]
    if total > len(findings):
        lines.append(f"  … {total - len(findings)} further finding(s) — see "
                     f"{proposal.get('report', watchdog.LATEST_REPORT_REL)}")
    lines += [
        "",
        "Fix exactly these findings — remediation, not rework. Every fix must itself carry an "
        "anchored, re-derivable claim (hard rule 4); derived surfaces go through their "
        "generators, never a hand-edit (hard rule 5).",
        "ACCEPTANCE: `agentic-dynamics docs scan --fail-on-drift` returns clean for the axes "
        "named above — the scanner that raised this proposal is the gate that retires it.",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Durable state: the proposal (level), the approvals and runs (edge), the claim (atomic)
# ─────────────────────────────────────────────────────────────────────────────────────────────


def read_proposal(results_dir: Path | None = None) -> dict:
    """Read the current proposal document ( ``{}`` when there is none or it is unreadable).

    Degrades to ``{}`` rather than raising for the same reason the watchdog's state read does: a
    corrupt memory must not stop the gate from reporting, and ``{}`` is the safe default — it
    means "no proposal stands", which authorises nothing.
    """
    results_dir = results_dir or RESULTS_DIR
    return watchdog.read_proposal(results_dir)


def write_proposal(results_dir: Path, proposal: dict) -> Path:
    """Persist the proposal document (level state — rewritten on every decision)."""
    path = results_dir / PROPOSAL_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def append_line(results_dir: Path, filename: str, line: dict) -> Path:
    """Append one JSON line to an edge-triggered audit file, creating it if needed."""
    path = results_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")
    return path


def read_approval(results_dir: Path | None = None) -> dict:
    """Return the most recent approval record, or ``{}``.

    Reads the LAST line of ``approvals.jsonl``. The file is the standing signature; earlier lines
    are history. Reading the file (not the Redis key) keeps the authority on disk, so a flushed
    Redis cannot manufacture — nor erase — a controller's signature.
    """
    results_dir = results_dir or RESULTS_DIR
    path = results_dir / APPROVALS_FILE
    if not path.exists():
        return {}
    latest: dict = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                doc = json.loads(raw)
            except ValueError:
                continue  # a torn line is skipped, never fatal — the rest is still an audit trail
            if isinstance(doc, dict):
                latest = doc
    except OSError:
        return {}
    return latest


def read_claim(results_dir: Path | None = None) -> dict:
    """Read the in-flight run claim, or ``{}`` when no run holds it."""
    results_dir = results_dir or RESULTS_DIR
    path = results_dir / RUN_LOCK_FILE
    if not path.exists():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # A claim we cannot parse is still a claim: the file's EXISTENCE is the lock, and its
        # contents are only description. Returning a marker (rather than {}) keeps a corrupt lock
        # blocking, because the alternative — treating it as absent — would allow the double
        # dispatch the lock exists to prevent.
        return {"run_id": "unreadable", "at": "", "unreadable": True}
    return doc if isinstance(doc, dict) else {"run_id": "unreadable", "at": "", "unreadable": True}


def claim_run(results_dir: Path, claim: dict) -> bool:
    """Atomically take the dispatch claim. True iff THIS caller took it.

    ``O_CREAT | O_EXCL`` is the entire idempotence mechanism: the kernel guarantees that of any
    number of concurrent callers exactly one creates the file and the rest raise
    ``FileExistsError``. No lease, no compare-and-swap, no Redis round trip — and it holds across
    processes, across a Redis outage, and across a reboot, because the filesystem is where the
    claim lives.
    """
    path = results_dir / RUN_LOCK_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(claim, indent=2, sort_keys=True) + "\n")
    return True


def release_claim(results_dir: Path) -> dict:
    """Drop the claim, returning what it held (``{}`` when nothing was held).

    Called on two paths: a terminal ``release`` (the run finished) and a dispatch rollback (the
    enqueue failed after the claim was taken). Both are explicit; nothing here expires a claim on
    a timer.
    """
    held = read_claim(results_dir)
    path = results_dir / RUN_LOCK_FILE
    try:
        path.unlink()
    except FileNotFoundError:
        return {}
    return held


def claim_is_expired(claim: dict, *, ttl_seconds: int = CLAIM_TTL_SECONDS,
                     at: str | None = None) -> bool:
    """True when a held claim is older than the TTL — i.e. its run probably died.

    Purely INFORMATIONAL. Nothing in this module acts on the answer: an expired claim still blocks
    dispatch, and only an explicit ``release`` clears it. The flag exists so ``status`` can tell a
    controller "this has been held for 11 hours, you may want to look" instead of leaving them to
    compare timestamps by hand.
    """
    from datetime import datetime, timezone

    stamp = claim.get("at")
    if not stamp:
        return False
    try:
        started = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return False
    reference = datetime.now(timezone.utc)
    if at:
        try:
            reference = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError:
            pass
    return (reference - started).total_seconds() > ttl_seconds


def _expiry_note(claim: dict, at: str | None = None) -> str:
    """The " (past its expiry…)" suffix, or "" — so every refusal annotates a dead-looking run.

    Factored because the annotation was originally attached to only one of the two
    already-in-flight paths, and it was the path a controller almost never reaches: with a
    standing ``in_flight`` proposal, dispatch refuses at the state check long before it tries the
    claim. A warning on the unreachable branch is not a warning.
    """
    if claim and claim_is_expired(claim, at=at):
        return " (past its expiry — `release` it explicitly if the run is dead)"
    return ""


# ─────────────────────────────────────────────────────────────────────────────────────────────
# The live mirrors (best-effort — the durable files are the truth)
# ─────────────────────────────────────────────────────────────────────────────────────────────


def _connect(use_redis: bool, client: Any = None) -> Any:
    """Resolve a Redis client, or None. Never raises — file-only mode is a supported degradation."""
    if not use_redis:
        return None
    if client is not None:
        return client
    try:
        client = watchdog._redis()
        client.ping()
        return client
    except Exception:  # noqa: BLE001 — the gate's authority is on disk; a mirror is a bonus
        log("framework Redis unavailable — durable writes done, live mirrors skipped")
        return None


def publish_proposal(client, proposal: dict) -> bool:
    """Mirror the proposal onto its live key for the portal. Best-effort."""
    if client is None:
        return False
    try:
        client.set(PROPOSAL_KEY, json.dumps(proposal))
        return True
    except Exception:  # noqa: BLE001
        return False


def publish_approval(client, approval: dict) -> bool:
    """Mirror the controller's signature onto ``docs:remediation:approved``. Best-effort.

    The key the workflow spec names. It is a MIRROR of ``approvals.jsonl``, never the source of
    truth — :func:`dispatch` reads the file. That direction matters: if the live key were
    authoritative, anything able to write db1 could authorise a spend, and a flushed db1 could
    erase a signature the audit trail should keep forever.
    """
    if client is None:
        return False
    try:
        client.set(APPROVAL_KEY, json.dumps(approval))
        return True
    except Exception:  # noqa: BLE001
        return False


def publish_run(client, run: dict) -> bool:
    """Mirror the in-flight run record. Best-effort; the lock file is the authority."""
    if client is None:
        return False
    try:
        client.set(RUN_KEY, json.dumps(run))
        return True
    except Exception:  # noqa: BLE001
        return False


def patch_board_row(client, proposal: dict) -> bool:
    """Patch the live docs-drift board row's proposal fields in place. Best-effort.

    The gate does NOT rebuild the row: it did not re-scan, so the row's drift numbers are the
    watchdog's to own and would be a fabrication coming from here. It patches only the two fields
    it owns (``proposal_state`` and ``proposed_action``) plus the stamp, so the board reflects a
    fresh proposal immediately instead of waiting up to an hour for the next watchdog pass.

    If the row is absent (no scan has run on this host), nothing is patched — the gate must not
    conjure a board row implying a scan that never happened. The next watchdog pass will build a
    complete row and pick the proposal state up from the durable file.
    """
    if client is None:
        return False
    try:
        raw = client.get(watchdog.DOCS_DRIFT_BOARD_KEY)
        if not raw:
            return False
        row = json.loads(raw)
        if not isinstance(row, dict):
            return False
        row["proposal_state"] = proposal.get("state", PROPOSAL_NONE)
        row["proposed_action"] = proposal.get("action", {})
        row["proposal_ts"] = proposal.get("at", "")
        client.set(watchdog.DOCS_DRIFT_BOARD_KEY, json.dumps(row))
        return True
    except Exception:  # noqa: BLE001
        return False


# ─────────────────────────────────────────────────────────────────────────────────────────────
# propose — the machine's half. Surfaces the remediation. Queues NOTHING.
# ─────────────────────────────────────────────────────────────────────────────────────────────


def build_proposal(report: dict, remediation: Remediation, *, threshold: int,
                   state: str, at: str, proposal_id: str) -> dict:
    """Assemble the proposal document written to ``proposal.json`` and shown on the board.

    ``action`` is the part a controller reads before signing: which spec, which model, what it is
    bounded to spend, how many phases, and the basis for all of it. Attaching the budget to the
    proposal — rather than making the controller go look it up — is what makes the approval an
    informed one rather than a reflex.
    """
    score = report.get("score") or {}
    findings = findings_of(report)
    return {
        "schema": "docs-proposal/v1",
        "at": at,
        "state": state,
        "proposal_id": proposal_id,
        "threshold": threshold,
        "drift": int(score.get("drift", 0)),
        "stale": int(score.get("total_stale", 0)),
        "missing": int(score.get("total_missing", 0)),
        "per_axis": {a: int(b.get("drift", 0)) for a, b in (score.get("per_axis") or {}).items()},
        "git_sha": report.get("git_sha", "unknown"),
        "why": summarise_score(score),
        "report": watchdog.LATEST_REPORT_REL,
        "finding_count": len(findings),
        "check_ids": [str(f.get("check_id")) for f in findings],
        # The rows the dispatched brief is built from — frozen at propose time so the run is
        # briefed on the inventory the controller approved, not on whatever the hourly watchdog
        # happens to have written to latest.json by dispatch time. Bounded; the overflow is
        # counted by ``finding_count`` and the full report is named above.
        "findings": findings[:GOAL_INVENTORY_LIMIT],
        # The proposed action — the remediation, with its budget estimate, read from its spec.
        "action": remediation.to_json(),
        # Filled by approve/dispatch; declared here so the document's shape is stable for the
        # portal panel regardless of which state it is in.
        "approval": {},
        "run": {},
    }


def propose(
    *,
    results_dir: Path | None = None,
    root: Path | None = None,
    threshold: int = DEFAULT_THRESHOLD,
    report: dict | None = None,
    remediation: Remediation | None = None,
    client: Any = None,
    use_redis: bool = True,
    dry_run: bool = False,
) -> GateDecision:
    """Decide whether the standing drift warrants the remediation, and surface it. Queues nothing.

    This function has **no code path that enqueues work** — that is its contract, not an emergent
    property. The returned :class:`GateDecision` always carries ``enqueued=False``, so the
    propose-without-running property is directly assertable rather than inferred.

    The decision table:

    ================================  ==========================================================
    situation                         outcome
    ================================  ==========================================================
    no report / unmeasured report     ``unmeasured`` — decline to decide; leave any standing
                                      proposal exactly as it is (absence of evidence neither
                                      raises nor retires a finding)
    a run is in flight                ``already_in_flight`` — the standing run is not disturbed,
                                      whatever the latest scan says
    drift > threshold                 ``warranted`` (or ``unchanged`` when the same proposal
                                      already stands) — the remediation is surfaced
    drift <= threshold, proposal held  ``withdrawn`` — the drift it named is gone, so the
                                      proposal is retired without anyone having to do it by hand
    drift <= threshold, nothing held  ``none`` — nothing to do
    ================================  ==========================================================

    Args:
        results_dir: Override the state directory (tests point this at a tmp_path).
        root: Override the repo root used to locate the remediation spec.
        threshold: Drift strictly above this is warranted.
        report: A pre-read report, injected instead of reading ``latest.json``.
        remediation: A pre-loaded remediation, injected instead of parsing the spec.
        client: A Redis client (or a fake); None + ``use_redis`` means "connect for me".
        use_redis: False to skip the live mirrors entirely.
        dry_run: Decide and report, write nothing.
    """
    results_dir = results_dir or RESULTS_DIR
    at = now()
    prior = read_proposal(results_dir)
    prior_state = str(prior.get("state", PROPOSAL_NONE))

    if report is None:
        report = read_latest_report(results_dir)

    # ── unmeasured: decline to decide, in EITHER direction ──
    if report is None or not report_is_measured(report):
        detail = (
            "no drift report on disk — run the watchdog first (a missing report is not a clean "
            "one)" if report is None else
            f"scan could not measure ({report.get('errors') or (report.get('score') or {}).get('axes_errored')})"
        )
        return GateDecision(
            verb="propose", at=at, state=prior_state or PROPOSAL_NONE, prior_state=prior_state,
            proposal_id=str(prior.get("proposal_id", "")), threshold=threshold,
            drift=int(prior.get("drift", 0)), outcome=PROPOSAL_UNMEASURED, enqueued=False,
            detail=detail, proposal=prior,
        )

    if remediation is None:
        remediation = load_remediation(root)

    score = report.get("score") or {}
    drift = int(score.get("drift", 0))
    check_ids = [str(f.get("check_id")) for f in findings_of(report)]
    proposal_id = compute_proposal_id(remediation.name, check_ids) if drift > threshold else ""

    # ── a run holds the claim: report and stand down ──
    # Re-proposing over an in-flight run would either clobber the run record on the proposal
    # document or hand the controller an "approve" affordance for work already running. The
    # standing run is authoritative until `release` retires it.
    claim = read_claim(results_dir)
    if claim and prior_state in ACTIVE_STATES:
        moved = bool(proposal_id) and proposal_id != str(prior.get("proposal_id", ""))
        return GateDecision(
            verb="propose", at=at, state=prior_state, prior_state=prior_state,
            proposal_id=str(prior.get("proposal_id", "")), drift=drift, threshold=threshold,
            outcome="already_in_flight", enqueued=False,
            detail=(
                f"remediation run {claim.get('run_id')} is in flight; proposal untouched"
                + (" (the drift inventory has since changed — a fresh proposal will be raised "
                   "once this run is released)" if moved else "")
            ),
            proposal=prior, run=claim,
        )

    # ── below threshold ──
    if drift <= threshold:
        if prior_state in (PROPOSAL_WARRANTED, PROPOSAL_APPROVED):
            # The findings this proposal named are gone. Retire it — the same lifecycle discipline
            # the watchdog's flag follows: raised by a finding, cleared by positive evidence.
            withdrawn = build_proposal(report, remediation, threshold=threshold,
                                       state=PROPOSAL_NONE, at=at, proposal_id="")
            withdrawn["withdrew"] = {
                "proposal_id": str(prior.get("proposal_id", "")),
                "was": prior_state,
                "why": "drift returned to or below the threshold",
            }
            decision = GateDecision(
                verb="propose", at=at, state=PROPOSAL_NONE, prior_state=prior_state,
                drift=drift, threshold=threshold, outcome="withdrawn", enqueued=False,
                detail=f"proposal {prior.get('proposal_id', '')} withdrawn: {summarise_score(score)}",
                proposal=withdrawn,
            )
            if not dry_run:
                decision.written.append(str(write_proposal(results_dir, withdrawn)))
                client = _connect(use_redis, client)
                decision.redis_available = client is not None
                publish_proposal(client, withdrawn)
                patch_board_row(client, withdrawn)
            log(decision.detail)
            return decision

        clean = build_proposal(report, remediation, threshold=threshold, state=PROPOSAL_NONE,
                               at=at, proposal_id="")
        decision = GateDecision(
            verb="propose", at=at, state=PROPOSAL_NONE, prior_state=prior_state, drift=drift,
            threshold=threshold, outcome=PROPOSAL_NONE, enqueued=False,
            detail=f"nothing warranted (drift {drift} <= threshold {threshold})", proposal=clean,
        )
        if not dry_run:
            decision.written.append(str(write_proposal(results_dir, clean)))
            client = _connect(use_redis, client)
            decision.redis_available = client is not None
            publish_proposal(client, clean)
            patch_board_row(client, clean)
        log(decision.detail)
        return decision

    # ── warranted ──
    unchanged = prior_state == PROPOSAL_WARRANTED and str(prior.get("proposal_id", "")) == proposal_id
    proposal = build_proposal(report, remediation, threshold=threshold, state=PROPOSAL_WARRANTED,
                              at=at, proposal_id=proposal_id)
    # An approval signed against THIS proposal survives a re-propose: the fingerprint is the whole
    # reason the id excludes the git SHA, and dropping the signature on every hourly re-scan would
    # make an approval un-actable in practice.
    standing = read_approval(results_dir)
    if standing.get("proposal_id") == proposal_id:
        proposal["approval"] = standing
        proposal["state"] = PROPOSAL_APPROVED

    decision = GateDecision(
        verb="propose", at=at, state=proposal["state"], prior_state=prior_state,
        proposal_id=proposal_id, drift=drift, threshold=threshold,
        outcome="unchanged" if unchanged else PROPOSAL_WARRANTED, enqueued=False,
        detail=(
            f"remediation WARRANTED: {summarise_score(score)} — proposing {remediation.name} "
            f"(~${remediation.budget_usd:.2f}, {len(remediation.phases)} phases). "
            f"Queued nothing; the controller decides."
        ),
        proposal=proposal,
    )
    if not dry_run:
        decision.written.append(str(write_proposal(results_dir, proposal)))
        client = _connect(use_redis, client)
        decision.redis_available = client is not None
        publish_proposal(client, proposal)
        patch_board_row(client, proposal)
    log(decision.detail)
    return decision


# ─────────────────────────────────────────────────────────────────────────────────────────────
# The dispatch target — where an approved remediation actually gets queued
# ─────────────────────────────────────────────────────────────────────────────────────────────


def default_workdir() -> str:
    """The worktree the remediation run is dispatched into.

    Under ``FINOPS_WORKTREE_ROOT`` (default ``/tmp``), matching the rule
    ``scripts/fleet/spawn_wrapper.py:validate_submit_request`` enforces on every submitted job.
    The gate does NOT create the worktree: creating a branch is a repository mutation, and this
    module's entire premise is that it mutates nothing without a signature. Provisioning belongs
    to whoever executes the run.
    """
    from agentic_dynamics.core.constants import WORKTREE_ROOT

    return str(Path(WORKTREE_ROOT) / "wt_docs_remediation")


def check_workdir(workdir: str) -> str:
    """Return an empty string when the workdir is dispatchable, else why it is not.

    Mirrors the orchestrator's "strictly UNDER ``FINOPS_WORKTREE_ROOT``" rule so that a request
    the orchestrator would reject is rejected *here*, where the controller is standing and can
    read the reason — instead of being accepted, queued, and silently dead-lettered later. It is
    a shape check only: existence is the executor's business, since it may provision the tree.
    """
    from agentic_dynamics.core.constants import WORKTREE_ROOT

    root = Path(WORKTREE_ROOT).resolve()
    candidate = Path(workdir).resolve()
    if candidate == root:
        return f"workdir must be strictly under {root}, not the root itself"
    if root not in candidate.parents:
        return f"workdir {candidate} is not under FINOPS_WORKTREE_ROOT ({root})"
    return ""


def fleet_submit(*, spec: str, goal: str, model: str, workdir: str) -> dict:
    """Enqueue the remediation through the EXISTING fleet submit path. The one spending call.

    No new transport: this LPUSHes the same ``fleet:commands`` submit command
    ``scripts/fleet/fleet_manager.py`` already mints for every other workflow job, so the
    remediation is validated (``spawn_wrapper.validate_submit_request``), admitted (the lease
    gate), and boarded (``fleet:jobs``) by exactly the machinery every other job goes through.
    A bespoke launcher here would be a second, less-guarded way to spend money.

    Raises whatever the fleet path raises — the caller (:func:`dispatch`) catches it and rolls the
    claim back, so a failed enqueue never leaves the rail wedged behind a lock guarding nothing.
    """
    fleet_dir = str(ROOT / "scripts" / "fleet")
    if fleet_dir not in sys.path:
        sys.path.insert(0, fleet_dir)
    import fleet_manager  # noqa: PLC0415 — lazy: importing it costs a redis connection module

    client = fleet_manager._connect()
    return fleet_manager._send_submit_command(
        client, spec=spec, goal=goal, model=model, workdir=workdir
    )


# ─────────────────────────────────────────────────────────────────────────────────────────────
# dispatch — the ONLY function in this module that can enqueue anything
# ─────────────────────────────────────────────────────────────────────────────────────────────


def dispatch(
    *,
    results_dir: Path | None = None,
    root: Path | None = None,
    workdir: str | None = None,
    mode: str = DISPATCH_FLEET,
    submit_fn: Callable[..., dict] | None = None,
    client: Any = None,
    use_redis: bool = True,
    dry_run: bool = False,
    at: str | None = None,
) -> GateDecision:
    """Launch the approved remediation — at most once, ever, per proposal.

    Refuses unless ALL of the following hold, checked in this order so the most informative
    refusal wins:

    1. a proposal stands (``warranted`` or ``approved``),
    2. a controller approval exists whose ``proposal_id`` matches that proposal,
    3. no run currently holds the claim.

    Then it takes the claim atomically and enqueues. If the enqueue raises, the claim is rolled
    back and the failure is reported — a claim that guards no running work would block the rail
    forever, and a rail nobody can unblock gets bypassed.

    Args:
        workdir: The worktree to run in (default: :func:`default_workdir`).
        mode: ``fleet`` (queue it) or ``command`` (record the ready-to-run command line for the
            controller's own hands — the documented in-process fallback). ``command`` still takes
            the claim, so "once" holds in both modes; it simply reports ``enqueued=False``,
            because recording a command is not queueing work and must not be logged as if it were.
        submit_fn: Injected enqueue function (tests count its calls — that count IS the
            approve-runs-once proof). None means :func:`fleet_submit`.
    """
    results_dir = results_dir or RESULTS_DIR
    at = at or now()
    proposal = read_proposal(results_dir)
    prior_state = str(proposal.get("state", PROPOSAL_NONE))
    proposal_id = str(proposal.get("proposal_id", ""))

    def refuse(outcome: str, detail: str, run: dict | None = None) -> GateDecision:
        """Every refusal path returns through here, so none of them can accidentally enqueue."""
        log(f"REFUSED ({outcome}): {detail}")
        return GateDecision(
            verb="dispatch", at=at, state=prior_state, prior_state=prior_state,
            proposal_id=proposal_id, drift=int(proposal.get("drift", 0)),
            threshold=int(proposal.get("threshold", DEFAULT_THRESHOLD)), outcome=outcome,
            enqueued=False, detail=detail, proposal=proposal, run=run or {},
        )

    # 1 ── a proposal must stand.
    if prior_state not in (PROPOSAL_WARRANTED, PROPOSAL_APPROVED):
        if prior_state in ACTIVE_STATES:
            # Annotate expiry HERE too, not only on the claim-collision path below. In the normal
            # case the standing proposal already reads ``in_flight``, so this is the branch a
            # controller actually hits — and a note about a dead-looking run that only appears on
            # the rarer path is a note nobody ever reads.
            return refuse("already_in_flight",
                          f"a remediation run is already in flight; nothing enqueued"
                          f"{_expiry_note(read_claim(results_dir), at)}",
                          read_claim(results_dir))
        return refuse("refused_no_proposal",
                      f"no proposal stands (state={prior_state or PROPOSAL_NONE}) — run "
                      f"`docs_proposal_gate.py propose` first")

    # 2 ── the approval must be the controller's signature on THIS inventory.
    approval = read_approval(results_dir)
    if not approval:
        return refuse("refused_no_approval",
                      "no controller approval on record — the gate proposes, it does not decide")
    if str(approval.get("proposal_id", "")) != proposal_id:
        return refuse(
            "refused_stale_approval",
            f"the standing approval is for proposal {approval.get('proposal_id')!r}, but the "
            f"current proposal is {proposal_id!r} — the drift inventory changed since it was "
            f"signed, so the controller is asked again",
        )

    # 3 ── the workdir must be one the executor would accept.
    workdir = workdir or default_workdir()
    problem = check_workdir(workdir)
    if problem:
        return refuse("refused_bad_workdir", problem)

    if mode not in DISPATCH_MODES:
        return refuse("refused_bad_mode", f"unknown dispatch mode {mode!r} (expected {DISPATCH_MODES})")

    remediation = load_remediation(root)
    goal = build_goal(proposal, remediation)
    run_id = hashlib.sha256(f"{proposal_id}|{at}".encode("utf-8")).hexdigest()[:12]
    command = [
        "python3", "scripts/run_workflow.py",
        "--spec", remediation.spec,
        "--goal", goal,
        "--model", remediation.model,
        "--workdir", workdir,
    ]
    run = {
        "run_id": run_id,
        "at": at,
        "proposal_id": proposal_id,
        "spec": remediation.spec,
        "model": remediation.model,
        "workdir": workdir,
        "budget_usd": remediation.budget_usd,
        "mode": mode,
        "status": PROPOSAL_IN_FLIGHT,
        "approved_by": approval.get("by", ""),
        "approved_at": approval.get("at", ""),
        "goal_chars": len(goal),
        "command": command,
    }

    if dry_run:
        return GateDecision(
            verb="dispatch", at=at, state=prior_state, prior_state=prior_state,
            proposal_id=proposal_id, drift=int(proposal.get("drift", 0)),
            threshold=int(proposal.get("threshold", DEFAULT_THRESHOLD)),
            outcome="would_dispatch", enqueued=False,
            detail=f"dry-run: would dispatch {remediation.name} via {mode} (nothing claimed)",
            proposal=proposal, run=run,
        )

    # 4 ── THE CLAIM. Atomic; exactly one caller proceeds past this line per proposal.
    if not claim_run(results_dir, run):
        held = read_claim(results_dir)
        return refuse("already_in_flight",
                      f"run {held.get('run_id')} already holds the claim"
                      f"{_expiry_note(held, at)}; nothing enqueued",
                      held)

    # 5 ── THE ENQUEUE. The only spending call, and it is now guarded by a held claim.
    submitted: dict = {}
    if mode == DISPATCH_FLEET:
        try:
            submitted = (submit_fn or fleet_submit)(
                spec=remediation.spec, goal=goal, model=remediation.model, workdir=workdir
            )
        except Exception as exc:  # noqa: BLE001 — every failure mode rolls the claim back
            release_claim(results_dir)
            return refuse("dispatch_failed",
                          f"enqueue failed, claim rolled back (the rail stays dispatchable): {exc!r}")
        run["submitted"] = submitted if isinstance(submitted, dict) else {"result": str(submitted)}
        run["job_id"] = (submitted or {}).get("job_id", "") if isinstance(submitted, dict) else ""
        enqueued = True
    else:
        # ``command`` mode: the claim is held (so a second approval is still a no-op) but nothing
        # was queued. Saying enqueued=False here is the honest report, and it is what keeps the
        # propose/dispatch accounting trustworthy.
        enqueued = False

    # 6 ── Record it. Durable first, mirrors after (the rail's standing convention).
    written = [str(append_line(results_dir, RUNS_FILE, run))]
    proposal = dict(proposal)
    proposal["state"] = PROPOSAL_IN_FLIGHT
    proposal["run"] = run
    proposal["at"] = at
    written.append(str(write_proposal(results_dir, proposal)))

    client = _connect(use_redis, client)
    publish_run(client, run)
    publish_proposal(client, proposal)
    patch_board_row(client, proposal)

    detail = (
        f"DISPATCHED {remediation.name} run {run_id} for proposal {proposal_id} "
        f"(~${remediation.budget_usd:.2f}, approved by {approval.get('by', '?')})"
        if enqueued else
        # The goal is a multi-KB brief; printing it into a journal line would bury the message.
        # Name its size and where the full command is recorded instead.
        f"CLAIMED run {run_id} for proposal {proposal_id} in `command` mode — nothing queued. "
        f"Run: run_workflow.py --spec {remediation.spec} --model {remediation.model} "
        f"--workdir {workdir} --goal <{len(goal)} chars, see {RUNS_FILE}:{run_id}>"
    )
    log(detail)
    return GateDecision(
        verb="dispatch", at=at, state=PROPOSAL_IN_FLIGHT, prior_state=prior_state,
        proposal_id=proposal_id, drift=int(proposal.get("drift", 0)),
        threshold=int(proposal.get("threshold", DEFAULT_THRESHOLD)), outcome="dispatched",
        enqueued=enqueued, detail=detail, proposal=proposal, run=run, written=written,
        redis_available=client is not None,
    )


# ─────────────────────────────────────────────────────────────────────────────────────────────
# approve — the controller's half
# ─────────────────────────────────────────────────────────────────────────────────────────────


def approve(
    *,
    by: str,
    reason: str = "",
    proposal_id: str | None = None,
    results_dir: Path | None = None,
    root: Path | None = None,
    workdir: str | None = None,
    mode: str = DISPATCH_FLEET,
    submit_fn: Callable[..., dict] | None = None,
    do_dispatch: bool = True,
    client: Any = None,
    use_redis: bool = True,
    dry_run: bool = False,
) -> GateDecision:
    """Record the controller's signature and (by default) dispatch the remediation.

    The signature is an explicit, attributed, durable record — ``by`` is required, because an
    unattributed approval is not an approval, it is a state change. It is appended to
    ``approvals.jsonl`` (the permanent audit trail) and mirrored to ``docs:remediation:approved``.

    **The idempotence contract lives here.** A second approval arriving while a run is in flight
    returns ``already_in_flight``, writes no approval record, and enqueues nothing. That is
    checked before anything is written, and again — atomically, against concurrent callers — by
    the claim inside :func:`dispatch`. Two independent guards, because this is the one property
    whose failure spends real money twice.

    Args:
        by: Who is signing. Required.
        reason: Free text recorded with the signature.
        proposal_id: When given, the approval must match the proposal currently on disk. This is
            what the Control Room's approve affordance sends: it echoes the id it *rendered*, so
            an approval clicked against a proposal that has since changed underneath the operator
            is refused rather than silently applied to different findings.
        do_dispatch: False to sign now and launch later (``approve --no-dispatch``), which is the
            path for a controller who wants the signature recorded before the worktree exists.
    """
    results_dir = results_dir or RESULTS_DIR
    at = now()
    proposal = read_proposal(results_dir)
    prior_state = str(proposal.get("state", PROPOSAL_NONE))
    current_id = str(proposal.get("proposal_id", ""))

    # ── the idempotence guard: a run already holds the rail ──
    if prior_state in ACTIVE_STATES:
        held = read_claim(results_dir)
        detail = (f"remediation run {held.get('run_id')} is already in flight — approval is a "
                  f"no-op; nothing recorded, nothing enqueued")
        log(detail)
        return GateDecision(
            verb="approve", at=at, state=prior_state, prior_state=prior_state,
            proposal_id=current_id, drift=int(proposal.get("drift", 0)),
            threshold=int(proposal.get("threshold", DEFAULT_THRESHOLD)),
            outcome="already_in_flight", enqueued=False, detail=detail, proposal=proposal, run=held,
        )

    # ── there must be something to approve ──
    if prior_state not in (PROPOSAL_WARRANTED, PROPOSAL_APPROVED) or not current_id:
        detail = (f"nothing to approve (state={prior_state or PROPOSAL_NONE}) — the gate proposes "
                  f"only when measured drift crosses the threshold")
        log(f"REFUSED (refused_no_proposal): {detail}")
        return GateDecision(
            verb="approve", at=at, state=prior_state, prior_state=prior_state,
            proposal_id=current_id, outcome="refused_no_proposal", enqueued=False,
            detail=detail, proposal=proposal,
        )

    # ── the signature must be for the inventory the controller was shown ──
    if proposal_id is not None and proposal_id != current_id:
        detail = (f"approval names proposal {proposal_id!r} but {current_id!r} stands — the "
                  f"drift inventory changed; re-read the proposal and sign again")
        log(f"REFUSED (refused_stale_approval): {detail}")
        return GateDecision(
            verb="approve", at=at, state=prior_state, prior_state=prior_state,
            proposal_id=current_id, outcome="refused_stale_approval", enqueued=False,
            detail=detail, proposal=proposal,
        )

    approval = {
        "at": at,
        "proposal_id": current_id,
        "by": by,
        "reason": reason,
        "drift": int(proposal.get("drift", 0)),
        "check_ids": proposal.get("check_ids", []),
        "action": proposal.get("action", {}),
        "report": proposal.get("report", watchdog.LATEST_REPORT_REL),
    }

    if dry_run:
        return GateDecision(
            verb="approve", at=at, state=PROPOSAL_APPROVED, prior_state=prior_state,
            proposal_id=current_id, drift=approval["drift"],
            threshold=int(proposal.get("threshold", DEFAULT_THRESHOLD)),
            outcome="would_approve", enqueued=False,
            detail=f"dry-run: would approve proposal {current_id} as {by} (nothing written)",
            proposal=proposal,
        )

    written = [str(append_line(results_dir, APPROVALS_FILE, approval))]
    proposal = dict(proposal)
    proposal["state"] = PROPOSAL_APPROVED
    proposal["approval"] = approval
    proposal["at"] = at
    written.append(str(write_proposal(results_dir, proposal)))

    client = _connect(use_redis, client)
    publish_approval(client, approval)
    publish_proposal(client, proposal)
    patch_board_row(client, proposal)
    log(f"APPROVED proposal {current_id} by {by}"
        f"{' — ' + reason if reason else ''}")

    if not do_dispatch:
        return GateDecision(
            verb="approve", at=at, state=PROPOSAL_APPROVED, prior_state=prior_state,
            proposal_id=current_id, drift=approval["drift"],
            threshold=int(proposal.get("threshold", DEFAULT_THRESHOLD)), outcome="approved",
            enqueued=False, detail=f"approved by {by}; dispatch deferred (--no-dispatch)",
            proposal=proposal, written=written, redis_available=client is not None,
        )

    result = dispatch(results_dir=results_dir, root=root, workdir=workdir, mode=mode,
                      submit_fn=submit_fn, client=client, use_redis=use_redis)
    # Report the whole transaction under the verb the caller asked for, keeping the dispatch's
    # outcome/enqueued verbatim: the approval succeeded even if the launch was refused, and
    # collapsing the two would hide which half failed.
    result.verb = "approve"
    result.prior_state = prior_state
    result.written = written + result.written
    return result


# ─────────────────────────────────────────────────────────────────────────────────────────────
# release — the terminal transition
# ─────────────────────────────────────────────────────────────────────────────────────────────


def release(
    *,
    status: str = PROPOSAL_COMPLETED,
    note: str = "",
    results_dir: Path | None = None,
    client: Any = None,
    use_redis: bool = True,
) -> GateDecision:
    """Retire an in-flight run: drop the claim and record how it ended.

    The one operation that makes the rail dispatchable again, and it is deliberately manual. The
    gate does not watch the run it launched — watching is the fleet board's job (``fleet:jobs``
    carries the job's own lifecycle), and a gate that inferred completion from a queue state would
    be guessing about whether it is safe to spend again.

    After a ``completed`` release, the *next* watchdog pass plus ``propose`` closes the loop
    honestly: if the remediation worked, the scan measures zero drift and no proposal is raised;
    if it did not, the same findings raise a new proposal and the controller is asked again. The
    scanner that raised the proposal is the thing that retires it — never this function's opinion.
    """
    results_dir = results_dir or RESULTS_DIR
    at = now()
    proposal = read_proposal(results_dir)
    prior_state = str(proposal.get("state", PROPOSAL_NONE))
    held = read_claim(results_dir)

    if not held:
        detail = "no run holds the claim; nothing to release"
        log(detail)
        return GateDecision(verb="release", at=at, state=prior_state, prior_state=prior_state,
                            proposal_id=str(proposal.get("proposal_id", "")),
                            outcome="not_held", enqueued=False, detail=detail, proposal=proposal)

    if status not in (PROPOSAL_COMPLETED, PROPOSAL_FAILED):
        detail = f"release status must be {PROPOSAL_COMPLETED!r} or {PROPOSAL_FAILED!r}, got {status!r}"
        log(f"REFUSED (refused_bad_status): {detail}")
        return GateDecision(verb="release", at=at, state=prior_state, prior_state=prior_state,
                            proposal_id=str(proposal.get("proposal_id", "")),
                            outcome="refused_bad_status", enqueued=False, detail=detail,
                            proposal=proposal)

    released = release_claim(results_dir)
    terminal = dict(held or released)
    terminal.update({"status": status, "released_at": at, "note": note})
    written = [str(append_line(results_dir, RUNS_FILE, terminal))]

    proposal = dict(proposal)
    proposal["state"] = status
    proposal["run"] = terminal
    proposal["at"] = at
    written.append(str(write_proposal(results_dir, proposal)))

    client = _connect(use_redis, client)
    publish_run(client, terminal)
    publish_proposal(client, proposal)
    patch_board_row(client, proposal)

    detail = f"released run {terminal.get('run_id')} as {status}{' — ' + note if note else ''}"
    log(detail)
    return GateDecision(verb="release", at=at, state=status, prior_state=prior_state,
                        proposal_id=str(proposal.get("proposal_id", "")), outcome="released",
                        enqueued=False, detail=detail, proposal=proposal, run=terminal,
                        written=written, redis_available=client is not None)


# ─────────────────────────────────────────────────────────────────────────────────────────────
# status — a pure read
# ─────────────────────────────────────────────────────────────────────────────────────────────


def status(*, results_dir: Path | None = None) -> GateDecision:
    """Report what the gate currently holds. Writes nothing, connects to nothing.

    This is the shape the p4 ``/api/docs-health`` route serves for the proposal half of the panel,
    which is why it is a pure read: a dashboard poll must never be able to change the state it is
    displaying.
    """
    results_dir = results_dir or RESULTS_DIR
    at = now()
    proposal = read_proposal(results_dir)
    state = str(proposal.get("state", PROPOSAL_NONE))
    held = read_claim(results_dir)
    approval = read_approval(results_dir)

    if held:
        detail = (f"run {held.get('run_id')} in flight since {held.get('at')}"
                  + (" — PAST ITS EXPIRY; release it explicitly if the run is dead"
                     if claim_is_expired(held, at=at) else ""))
    elif state in (PROPOSAL_WARRANTED, PROPOSAL_APPROVED):
        action = proposal.get("action", {})
        # A signature on record for a DIFFERENT proposal is worth surfacing: it is the state in
        # which a controller would otherwise click "approve" expecting it to launch, and be told
        # the approval is stale only at dispatch time.
        signed = (" — signed by " + str(approval.get("by"))
                  if approval.get("proposal_id") == str(proposal.get("proposal_id", "")) else "")
        detail = (f"proposal {proposal.get('proposal_id')} {state}: {proposal.get('why', '')} — "
                  f"{action.get('name', '?')} (~${float(action.get('budget_usd', 0)):.2f}) "
                  f"awaiting {'dispatch' if state == PROPOSAL_APPROVED else 'the controller'}"
                  f"{signed}")
    else:
        detail = f"no proposal stands (state={state})"

    return GateDecision(
        verb="status", at=at, state=state, prior_state=state,
        proposal_id=str(proposal.get("proposal_id", "")), drift=int(proposal.get("drift", 0)),
        threshold=int(proposal.get("threshold", DEFAULT_THRESHOLD)), outcome=state,
        enqueued=False, detail=detail, proposal=proposal, run=held,
    )


# ─────────────────────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────────────────────

#: Outcomes that mean "the gate refused" — exit 1. Every other outcome is either a success or a
#: contract-upholding no-op (``already_in_flight``, ``none``, ``unchanged``), which is exit 0: a
#: rail that returned non-zero every time it correctly declined to act would train its operator
#: to ignore its exit code.
REFUSAL_OUTCOMES = frozenset({
    "refused_no_proposal",
    "refused_no_approval",
    "refused_stale_approval",
    "refused_bad_workdir",
    "refused_bad_mode",
    "refused_bad_status",
    "dispatch_failed",
})


def _add_common(parser: argparse.ArgumentParser) -> None:
    """Flags every mutating verb shares."""
    parser.add_argument("--results-dir",
                        help="override the state directory "
                             "(default: experiments/results/docs_drift)")
    parser.add_argument("--no-redis", action="store_true",
                        help="skip the live mirrors (durable writes only)")
    parser.add_argument("--json", action="store_true", help="emit the decision as JSON")


def _add_dispatch_flags(parser: argparse.ArgumentParser) -> None:
    """Flags shared by the two verbs that can reach :func:`dispatch`."""
    parser.add_argument("--workdir", default=None,
                        help="worktree to run the remediation in "
                             "(default: $FINOPS_WORKTREE_ROOT/wt_docs_remediation)")
    parser.add_argument("--mode", default=DISPATCH_FLEET, choices=list(DISPATCH_MODES),
                        help="fleet: enqueue on fleet:commands (default); "
                             "command: take the claim and record the run command instead")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. See the module docstring for the verbs and exit codes."""
    parser = argparse.ArgumentParser(
        description="Docs-drift proposal gate — the machine proposes, the controller decides.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="verb", required=True)

    p_status = sub.add_parser("status", help="what the gate currently holds (pure read)")
    p_status.add_argument("--results-dir", help="override the state directory")
    p_status.add_argument("--json", action="store_true", help="emit the decision as JSON")

    p_propose = sub.add_parser(
        "propose", help="decide whether the drift warrants the remediation; queues NOTHING")
    p_propose.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                           help=f"drift strictly above this is warranted (default {DEFAULT_THRESHOLD})")
    p_propose.add_argument("--dry-run", action="store_true", help="decide and report; write nothing")
    _add_common(p_propose)

    p_approve = sub.add_parser(
        "approve", help="record the controller's signature and (by default) dispatch")
    p_approve.add_argument("--by", required=True, help="who is approving (an unattributed "
                                                       "approval is not an approval)")
    p_approve.add_argument("--reason", default="", help="free text recorded with the signature")
    p_approve.add_argument("--proposal-id", default=None,
                           help="require the standing proposal to be this one (the portal "
                                "affordance echoes the id it rendered)")
    p_approve.add_argument("--no-dispatch", action="store_true",
                           help="record the approval but do not launch yet")
    p_approve.add_argument("--dry-run", action="store_true", help="decide and report; write nothing")
    _add_dispatch_flags(p_approve)
    _add_common(p_approve)

    p_dispatch = sub.add_parser("dispatch", help="launch a standing approval (at most once)")
    p_dispatch.add_argument("--dry-run", action="store_true",
                            help="report what would be dispatched; claim nothing")
    _add_dispatch_flags(p_dispatch)
    _add_common(p_dispatch)

    p_release = sub.add_parser("release", help="retire an in-flight run and drop the claim")
    p_release.add_argument("--status", default=PROPOSAL_COMPLETED,
                           choices=[PROPOSAL_COMPLETED, PROPOSAL_FAILED],
                           help="how the run ended")
    p_release.add_argument("--note", default="", help="free text recorded with the release")
    _add_common(p_release)

    args = parser.parse_args(argv)
    results_dir = Path(args.results_dir) if getattr(args, "results_dir", None) else None
    use_redis = not getattr(args, "no_redis", False)

    if args.verb == "status":
        decision = status(results_dir=results_dir)
    elif args.verb == "propose":
        decision = propose(results_dir=results_dir, threshold=args.threshold,
                           use_redis=use_redis, dry_run=args.dry_run)
    elif args.verb == "approve":
        decision = approve(by=args.by, reason=args.reason, proposal_id=args.proposal_id,
                           results_dir=results_dir, workdir=args.workdir, mode=args.mode,
                           do_dispatch=not args.no_dispatch, use_redis=use_redis,
                           dry_run=args.dry_run)
    elif args.verb == "dispatch":
        decision = dispatch(results_dir=results_dir, workdir=args.workdir, mode=args.mode,
                            use_redis=use_redis, dry_run=args.dry_run)
    else:
        decision = release(status=args.status, note=args.note, results_dir=results_dir,
                           use_redis=use_redis)

    if getattr(args, "json", False):
        print(json.dumps(decision.to_json(), indent=2, sort_keys=True))
    elif args.verb == "status":
        print(f"[docs-gate] {decision.detail}")

    if decision.outcome == PROPOSAL_UNMEASURED:
        return 2
    if decision.outcome in REFUSAL_OUTCOMES:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
