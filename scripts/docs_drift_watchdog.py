#!/usr/bin/env python3
"""Docs-drift watchdog — the cadence + observation rail of ``automatic_docs_sync`` (p2).

WHAT THIS IS
------------
:mod:`scripts.scan_docs_drift` (p1) is the *instrument*: it turns "are the docs current?" into
a reproducible number. This module is the *cadence* that runs it unattended and the *rail* that
carries its answer to the places a human already looks — so a drifting doc announces itself
instead of waiting to be stumbled over.

One pass (:func:`run_once`) does exactly four things, in this order:

1. **Scan.** Run the deterministic scanner in-process and get a
   :class:`~scan_docs_drift.DriftReport`.
2. **Persist.** Write ``experiments/results/docs_drift/latest.json`` (the report the proposal
   gate and the Control Room panel read) and append one compact line to ``history.jsonl``
   (the trend — every run, clean or not).
3. **Flag lifecycle.** Compare the score to the flag's prior state and, *only on a transition*,
   raise or clear the docs-drift flag on the observation rail.
4. **Board row.** Publish the live docs-drift row for the supervisor board, every cycle.

THE ZERO-MODEL-CALL GUARANTEE IS INHERITED (spec hard rule 1)
--------------------------------------------------------------
This module adds no model call. It runs the scanner *in-process* rather than shelling out —
so the report arrives as a typed object rather than re-parsed JSON, and there is no second
Python interpreter to keep in sync about which axes ran.

DRIFT IS A FINDING, NOT A VERDICT (spec hard rule 2)
------------------------------------------------------
Nothing here edits a document, touches a branch, or runs a remediation. The watchdog's entire
output is a report, a flag, and a board row. Proposing the remediation is the p3 gate's job;
approving it is the controller's.

LEVEL-TRIGGERED STATE, EDGE-TRIGGERED RECORDS
----------------------------------------------
This is the central design decision, and it is what makes an hourly timer tolerable:

* The **board row** and ``latest.json`` are *level* — rewritten every cycle, because they answer
  "what is true right now?" and a stale answer is worse than a repeated one.
* The **flag** is an *edge* — a durable record is appended, the supervisor hot list is pushed,
  and a knowledge record is registered **only when the state changes**. An hourly watchdog that
  re-raised an unchanged flag 24 times a day would bury the supervisor's real flags under its
  own noise, and the flags surface would become the thing operators learn to ignore.

So the flag's *state* is continuously maintained, while the flag's *history* records only
transitions: raised by a finding, cleared by a clean scan, never hand-held.

"COULD NOT MEASURE" IS NOT "CLEAN" (mirrors the scanner's exit 2)
-------------------------------------------------------------------
When an axis errors, the scanner refuses to score it zero, because a partial scan reporting
"drift 0" reads exactly like a clean tree. The watchdog inherits that refusal and goes one step
further: an ``unmeasured`` pass **never clears a raised flag**. A flag must be retired by
positive evidence that the drift is gone — never by the absence of evidence.

DURABLE FILE IS THE TRUTH; REDIS IS THE HOT PATH
--------------------------------------------------
Same convention as ``scripts/supervise.py:emit_flag``: the JSONL/JSON writes on disk are the
authority and always happen; the Redis mirrors are best-effort. A downed framework Redis
degrades the live surface but never costs the watchdog its durable record, and the next pass
re-publishes the row from the file-held state.

USAGE
-----
    python scripts/docs_drift_watchdog.py                  # one pass: scan, persist, flag, board
    python scripts/docs_drift_watchdog.py --dry-run        # scan + report only; writes nothing
    python scripts/docs_drift_watchdog.py --check anchor_integrity   # one axis (repeatable)
    python scripts/docs_drift_watchdog.py --fail-on-drift  # exit 1 when the flag is raised

Exit codes (chosen for a systemd timer, see ``infrastructure/docs-drift-scan.service``):
    0  the pass completed — whether the flag ended up clear OR raised.
    1  the flag is raised AND ``--fail-on-drift`` was given (CI use).
    2  the scan could not measure (an axis errored) — a genuine service failure.

Drift itself is deliberately NOT a non-zero exit by default: a timer unit that goes ``failed``
because the docs drifted would conflate "the watchdog broke" with "the watchdog worked and
found something", and hard rule 2 says drift is a finding, not a failure.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

try:
    import _bootstrap  # noqa: F401  # direct run: scripts/ is sys.path[0]; inserts src/
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: F401

# The scanner is a sibling script, not a package module, so make ``scripts/`` importable for the
# ``import scan_docs_drift`` below regardless of how this file was invoked.
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import scan_docs_drift  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────────────────────
# Contract constants — the keys and paths this rail owns
# ─────────────────────────────────────────────────────────────────────────────────────────────

#: Everything this rail writes lives here (the scanner's p1 baseline is its neighbour).
RESULTS_DIR = ROOT / "experiments" / "results" / "docs_drift"

#: The current report — what the p3 proposal gate and the p4 Control Room panel read.
LATEST_FILE = "latest.json"
#: The report's repo-relative path, as a literal. Named in the flag line and the board row so
#: a reader can find the full evidence behind a bounded summary. Deliberately NOT derived via
#: ``RESULTS_DIR.relative_to(ROOT)``: that coupled the string to whatever ``ROOT`` happened to
#: be and raised when a caller redirected the results directory.
LATEST_REPORT_REL = "experiments/results/docs_drift/latest.json"
#: One compact line per pass (clean or not) — the trend, not the detail.
HISTORY_FILE = "history.jsonl"
#: One line per flag TRANSITION — the audit trail of the lifecycle.
FLAGS_FILE = "flags.jsonl"
#: The durable flag state — the authority the Redis mirror is derived from.
STATE_FILE = "flag_state.json"

#: Live flag state for the portal. The ``docs:`` namespace is the one p3's approval flag
#: (``docs:remediation:approved``) also lives in, keeping the rail's keys greppable as a set.
DRIFT_FLAG_KEY = "docs:drift:flag"

#: The board row's own key.
#:
#: It is deliberately NOT written into ``fleet:board`` directly: ``fleet_manager.build_board``
#: rebuilds that snapshot wholesale every 15 seconds, so a row written there would survive at
#: most one watcher tick. This mirrors the reasoning ``fleet_manager`` already applies to
#: ``fleet:jobs`` — state written by whoever observes a transition lives in its own key and is
#: MERGED into the snapshot at build time (see ``fleet_manager._docs_drift_row``).
DOCS_DRIFT_BOARD_KEY = "fleet:docs_drift"

#: The stable subject identity of this flag. The observation rail keys a flag record by
#: ``session_id``; using one fixed pseudo-session means every raise and clear is a new VERSION
#: of the same knowledge entity rather than a pile of unrelated records — which is precisely
#: what a lifecycle is.
DOCS_DRIFT_SUBJECT = "docs-drift"

#: The flag's own state vocabulary (distinct from the status word put on the record below).
STATE_CLEAR = "clear"
STATE_RAISED = "raised"
STATE_UNMEASURED = "unmeasured"

#: The status word carried on the flag record. We reuse the supervisor's *attention* vocabulary
#: (``healthy`` | ``stalled`` | ``off_track`` — ``scripts/supervise.py:MONITOR_ROLE``) rather
#: than inventing docs-specific words, so the flags surface renders this row with the same chips
#: as every other flag (``apps/control_room/static/board-fleet.js:ATTENTION``). "off_track" is
#: also simply accurate: the docs are off-track relative to the code.
STATUS_RAISED = "off_track"
STATUS_CLEARED = "healthy"

#: How many finding rows ride along on the durable flag line. The full inventory is always in
#: ``latest.json``; this bound keeps one JSONL line readable (and the Redis push small) when a
#: badly-drifted tree produces hundreds of findings.
INVENTORY_LIMIT = 50


def now() -> str:
    """Canonical UTC stamp, matching the supervisor rail's format exactly (``…Z``)."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _redis():
    """Construct the framework Redis client lazily so file-only mode still works.

    Identical connection contract to ``scripts/supervise.py:_redis`` — the framework queue on
    6380/db1, never the story-agents' 6379 instance (which they ``flushdb``).
    """
    import redis

    return redis.Redis(
        host=os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1"),
        port=int(os.environ.get("FINOPS_REDIS_PORT", "6380")),
        db=int(os.environ.get("FINOPS_REDIS_DB", "1")),
        decode_responses=True,
        socket_connect_timeout=2,
    )


def log(msg: str) -> None:
    """Single-prefix stdout line — this is what ``journalctl --user -u docs-drift-scan`` shows."""
    print(f"[docs-drift] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────────────────────────────────────


@dataclass
class WatchdogResult:
    """The outcome of one pass — everything a caller or a test needs to assert on.

    Attributes:
        at: UTC stamp of the pass.
        git_sha: HEAD at scan time, copied from the report.
        score: The scanner's machine-readable score (totals + per-axis breakdown).
        state: The flag state AFTER this pass (``clear`` | ``raised`` | ``unmeasured``).
        prior_state: The flag state before it, as read from the durable state file.
        transition: ``"raised"``, ``"cleared"``, or ``None`` when the state did not change.
            This is the edge that gates every flag-history write.
        board_row: The row published for the supervisor board.
        kb_registered: True when a knowledge record was actually registered (transition +
            ``FINOPS_KB_WRITE=1`` + a reachable stream).
        redis_available: False when the Redis mirrors were skipped; the durable writes still ran.
        errors: Axes that could not run, verbatim from the scanner.
        written: Repo-relative paths this pass wrote (empty under ``--dry-run``).
    """

    at: str
    git_sha: str
    score: dict
    state: str
    prior_state: str
    transition: str | None
    board_row: dict
    kb_registered: bool = False
    redis_available: bool = False
    errors: dict = field(default_factory=dict)
    written: list[str] = field(default_factory=list)

    @property
    def drift(self) -> int:
        """The headline number: stale + missing across every axis that ran."""
        return int(self.score.get("drift", 0))


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Flag state — durable file is the authority, Redis is the mirror
# ─────────────────────────────────────────────────────────────────────────────────────────────


def read_flag_state(results_dir: Path) -> dict:
    """Read the durable flag state, or the clean-slate default when there is none yet.

    Deliberately reads the FILE, not Redis. Redis db1 is a live surface that can be flushed or
    restarted; if the watchdog took its "prior state" from there, a Redis restart would silently
    look like "the flag was never raised" and the next pass would re-raise an already-known
    finding — re-notifying the operator about something they already saw. The file is the memory.

    A corrupt or unreadable state file degrades to the clean-slate default rather than raising:
    a broken memory must not stop the watchdog from measuring and publishing.
    """
    path = results_dir / STATE_FILE
    if not path.exists():
        return {"state": STATE_CLEAR, "since": "", "drift": 0, "at": ""}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"state": STATE_CLEAR, "since": "", "drift": 0, "at": ""}
    if not isinstance(doc, dict) or "state" not in doc:
        return {"state": STATE_CLEAR, "since": "", "drift": 0, "at": ""}
    return doc


def write_flag_state(results_dir: Path, state_doc: dict) -> Path:
    """Persist the flag state atomically-enough for a once-an-hour writer.

    A plain write is sufficient here: this file has exactly one writer (the timer-driven pass,
    which systemd will not run concurrently with itself) and every reader tolerates a malformed
    document by falling back to the clean slate.
    """
    path = results_dir / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def decide_state(report: scan_docs_drift.DriftReport) -> str:
    """Map a scan report to the flag state this pass should hold.

    Three outcomes, and the third is the one that matters:

    * every axis ran and found nothing  -> ``clear``
    * every axis ran and found something -> ``raised``
    * an axis could not run              -> ``unmeasured``

    ``unmeasured`` exists so that a scan which *failed to look* can never be mistaken for a scan
    that *looked and found nothing*. :func:`run_once` then refuses to let it clear a raised flag.
    """
    if report.errors:
        return STATE_UNMEASURED
    return STATE_RAISED if report.score()["drift"] > 0 else STATE_CLEAR


def resolve_transition(prior_state: str, scanned_state: str) -> tuple[str, str | None]:
    """Fold the scanned state into the prior one, returning ``(effective_state, transition)``.

    The one non-obvious rule: an ``unmeasured`` pass INHERITS the prior state rather than
    replacing it. A flag is a claim about the docs, and a pass that could not read the docs has
    no new claim to make — so a raised flag stays raised (never cleared by ignorance) and a clear
    flag stays clear (an inability to scan is a service problem, surfaced by exit code 2, not a
    docs-drift finding).

    ``transition`` is non-None only on a genuine edge, and it is what gates every history write.
    """
    if scanned_state == STATE_UNMEASURED:
        return prior_state, None
    if scanned_state == prior_state:
        return scanned_state, None
    return scanned_state, ("raised" if scanned_state == STATE_RAISED else "cleared")


# ─────────────────────────────────────────────────────────────────────────────────────────────
# The flag record — the observation rail
# ─────────────────────────────────────────────────────────────────────────────────────────────


def _summarise(report: scan_docs_drift.DriftReport) -> str:
    """One-sentence ``why`` for the flag: the count plus the axes it came from.

    Kept short on purpose — it is rendered in a flag chip and read aloud by a screen reader.
    The full evidence is one path away, named in the flag line's ``report`` field.
    """
    score = report.score()
    drift = score["drift"]
    if not drift:
        return "docs-drift scan clean: every anchored claim reproduces against the code"
    hot = sorted(
        ((a, b["drift"]) for a, b in score["per_axis"].items() if b["drift"]),
        key=lambda kv: (-kv[1], kv[0]),
    )
    axes = ", ".join(f"{a} {n}" for a, n in hot)
    return f"{drift} docs-drift finding(s) across {len(hot)} axis/axes ({axes})"


def build_flag_line(
    report: scan_docs_drift.DriftReport,
    *,
    transition: str,
    at: str | None = None,
    inventory_limit: int = INVENTORY_LIMIT,
) -> dict:
    """Build the ``flags.jsonl``-shaped line for one lifecycle transition.

    The first six keys are exactly the projection
    ``control.observation_ingestion.build_flag_record`` consumes (``at``, ``session_id``,
    ``title``, ``model``, ``status``, ``why``); everything after them is extra context that is
    durable on disk and ignored by the record builder's fixed projection.

    That split is why the inventory is "attached" the way it is: the knowledge record carries the
    bounded summary (its ``text`` is built from ``title``/``model``/``status``/``why``), while the
    full finding inventory rides on the durable line and in ``latest.json``, which the line names.
    Putting hundreds of finding rows inside a knowledge record's text would make the record
    unembeddable and unreadable; naming the report keeps the evidence one hop away.

    ``model`` is not a model id because there is no model: the field records the *instrument*
    that produced the verdict, honouring hard rule 1 rather than pretending an LLM was consulted.
    """
    stamp = at or now()
    score = report.score()
    findings = report.findings
    return {
        # ── the projection the observation rail reads ──
        "at": stamp,
        "session_id": DOCS_DRIFT_SUBJECT,
        "title": "docs drift (deterministic scan)",
        "model": "none/scan_docs_drift",
        "status": STATUS_RAISED if transition == "raised" else STATUS_CLEARED,
        "why": _summarise(report),
        # ── durable context, ignored by build_flag_record ──
        "transition": transition,
        "git_sha": report.to_json().get("git_sha", "unknown"),
        "drift": score["drift"],
        "per_axis": {a: b["drift"] for a, b in score["per_axis"].items()},
        "report": LATEST_REPORT_REL,
        "inventory": [asdict(c) for c in findings[:inventory_limit]],
        "inventory_truncated": max(0, len(findings) - inventory_limit),
    }


def register_flag_record(flag_line: dict) -> bool:
    """Register the transition on the knowledge rail. Returns True when a record was published.

    Gated and best-effort, exactly like ``scripts/supervise.py:emit_flag``'s registry emit: the
    durable ``flags.jsonl`` write has already happened by the time this runs, and a downed DB2
    knowledge stream must never cost the watchdog its audit trail. ``FINOPS_KB_WRITE=1`` is the
    opt-in every write-time registration call site in this repo checks.
    """
    if os.environ.get("FINOPS_KB_WRITE") != "1":
        return False
    try:
        from agentic_dynamics.control.observation_ingestion import derive_flag_record
        from agentic_dynamics.knowledge import knowledge_ingestion as ki
        from agentic_dynamics.knowledge import knowledge_stream as ks
        from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID

        record = derive_flag_record(flag_line, repository_id=REPOSITORY_ID)

        # Write the ARTIFACT BEFORE publishing the pointer, per the producer pipe every
        # kb_produce* script follows (``derive -> record_to_artifact -> record_to_event ->
        # publish_event``). The event is only a pointer: its ``source_uri`` names this file and
        # its ``content_hash`` covers these exact bytes, so a consumer that reaches the pointer
        # before the bytes exist cannot verify the hash and dead-letters the record.
        #
        # This is the step ``scripts/supervise.py:emit_flag`` omits, which is why no
        # ``source_type=flag`` record has ever materialised in the registry index (measured
        # 2026-09-01: 0 of 18136 artifacts). That gap is the supervisor rail's to close — this
        # producer simply does not reproduce it, so a docs-drift flag is genuinely queryable
        # rather than a pointer into thin air.
        artifact_dir = ROOT / "experiments" / "results" / "kb"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / f"{record.knowledge_id}.json").write_bytes(ki.record_to_artifact(record))

        ks.register_records([record], fail_loud=False)
        return True
    except Exception as e:  # noqa: BLE001 — the rail is best-effort by contract
        log(f"registry emit error for the docs-drift flag: {e!r}")
        return False


def push_supervisor_flag(client, flag_line: dict) -> bool:
    """Mirror the transition onto the supervisor's bounded hot list. Best-effort.

    Reuses ``SUPERVISOR_FLAGS_KEY`` (and its 200-entry trim) rather than opening a parallel list,
    so a docs-drift transition appears on the same Flags board an operator already watches. Only
    transitions land here — see the module docstring on edge-triggering; the *current* state has
    its own key and does not belong in an append-only list.
    """
    if client is None:
        return False
    try:
        from agentic_dynamics.control.supervisor import (
            SUPERVISOR_FLAGS_KEY,
            SUPERVISOR_FLAGS_MAX,
            canonical_json,
        )

        # The hot list is bounded and rendered as chips: push the projection, not the inventory.
        hot = {k: v for k, v in flag_line.items() if k != "inventory"}
        client.lpush(SUPERVISOR_FLAGS_KEY, canonical_json(hot))
        client.ltrim(SUPERVISOR_FLAGS_KEY, 0, SUPERVISOR_FLAGS_MAX - 1)
        return True
    except Exception:  # noqa: BLE001 — a Redis blip never costs the durable write
        return False


# ─────────────────────────────────────────────────────────────────────────────────────────────
# The board row — the supervisor tier's live surface
# ─────────────────────────────────────────────────────────────────────────────────────────────


def build_board_row(
    report: scan_docs_drift.DriftReport,
    *,
    state: str,
    since: str,
    at: str | None = None,
) -> dict:
    """Assemble the live docs-drift row published for the supervisor board.

    Level-triggered: rewritten every cycle so "last scanned" is always honest. ``health`` is the
    green/yellow/red the p4 panel renders, computed here rather than in the browser so the CLI,
    the board, and the portal cannot disagree about what a score means.

    Note ``proposal_state`` is present and pinned to ``"none"``: the p3 gate owns that field, and
    declaring it here (rather than letting p3 bolt a key on later) keeps the row's shape stable
    for the panel that reads it. This watchdog proposes nothing — hard rule 3.
    """
    score = report.score()
    return {
        "ts": at or now(),
        "subject": DOCS_DRIFT_SUBJECT,
        "state": state,
        "since": since,
        "health": {
            STATE_CLEAR: "green",
            STATE_RAISED: "yellow",
            STATE_UNMEASURED: "red",
        }.get(state, "red"),
        "drift": score["drift"],
        "stale": score["total_stale"],
        "missing": score["total_missing"],
        "checked": score["total_checked"],
        "per_axis": {a: b["drift"] for a, b in score["per_axis"].items()},
        "axes_errored": score["axes_errored"],
        "git_sha": report.to_json().get("git_sha", "unknown"),
        "report": LATEST_REPORT_REL,
        # Owned by the p3 proposal gate; never set by the watchdog (machine proposes ≠ scanner
        # proposes — the scan is an instrument, the gate is the policy).
        "proposal_state": "none",
    }


def publish_board_row(client, row: dict) -> bool:
    """Write the row to its own Redis key for ``fleet_manager.build_board`` to merge in.

    See :data:`DOCS_DRIFT_BOARD_KEY` for why this is a separate key rather than a mutation of
    ``fleet:board``.
    """
    if client is None:
        return False
    try:
        client.set(DOCS_DRIFT_BOARD_KEY, json.dumps(row))
        return True
    except Exception:  # noqa: BLE001
        return False


def publish_flag_state(client, state_doc: dict) -> bool:
    """Mirror the durable flag state onto its live key (the portal's read). Best-effort."""
    if client is None:
        return False
    try:
        client.set(DRIFT_FLAG_KEY, json.dumps(state_doc))
        return True
    except Exception:  # noqa: BLE001
        return False


# ─────────────────────────────────────────────────────────────────────────────────────────────
# One pass
# ─────────────────────────────────────────────────────────────────────────────────────────────


def run_once(
    *,
    axes: tuple[str, ...] = scan_docs_drift.AXES,
    results_dir: Path | None = None,
    report: scan_docs_drift.DriftReport | None = None,
    client: Any = None,
    use_redis: bool = True,
    dry_run: bool = False,
    include_current: bool = False,
) -> WatchdogResult:
    """Run one watchdog pass: scan, persist, resolve the flag lifecycle, publish the board row.

    Args:
        axes: Which scanner axes to run. Narrowing this is how a caller asks a *real* question
            about a subset of the tree (the tests use it to obtain a genuinely clean scan of the
            four axes that are clean, rather than fabricating a report).
        results_dir: Override the output directory — the tests point this at a tmp_path so a
            test run can never disturb the repository's real flag state.
        report: A pre-computed report, injected instead of scanning. Lets tests drive both
            lifecycle directions deterministically and in milliseconds; a full scan is minutes.
        client: A Redis client (or a fake). ``None`` + ``use_redis`` means "connect for me".
        use_redis: Set False to skip the live mirrors entirely (file-only mode).
        dry_run: Scan and compute everything, write nothing. The honest preview.
        include_current: Serialise every check row into ``latest.json``, not just the findings.

    Returns:
        A :class:`WatchdogResult` describing the pass.
    """
    results_dir = results_dir or RESULTS_DIR
    at = now()

    # 1 ── SCAN. In-process; zero model calls (inherited guarantee).
    if report is None:
        report = scan_docs_drift.scan(axes)
    payload = report.to_json(include_current=include_current)
    score = report.score()

    # 2 ── FLAG LIFECYCLE. Resolve the edge before writing anything, so the persistence step
    #      below knows whether this pass is a transition (history) or a repeat (level only).
    prior = read_flag_state(results_dir)
    prior_state = str(prior.get("state", STATE_CLEAR))
    scanned_state = decide_state(report)
    state, transition = resolve_transition(prior_state, scanned_state)

    # "since" tracks how long the CURRENT state has held — reset on a transition, carried across
    # a repeat. It is what lets the panel say "clean for 3 days" instead of "clean as of now",
    # which is the difference between a trend and a snapshot.
    since = at if transition else (str(prior.get("since") or "") or at)

    state_doc = {
        "state": state,
        "since": since,
        "at": at,
        "drift": score["drift"],
        "scanned_state": scanned_state,
        "git_sha": payload.get("git_sha", "unknown"),
        "why": _summarise(report),
        "axes_errored": score["axes_errored"],
    }
    row = build_board_row(report, state=state, since=since, at=at)

    result = WatchdogResult(
        at=at,
        git_sha=payload.get("git_sha", "unknown"),
        score=score,
        state=state,
        prior_state=prior_state,
        transition=transition,
        board_row=row,
        errors=dict(report.errors),
    )

    if dry_run:
        log(
            f"dry-run: drift={score['drift']} scanned={scanned_state} "
            f"state={prior_state}->{state} transition={transition or 'none'} (nothing written)"
        )
        return result

    # 3 ── PERSIST (level). The report and the trend line are written on EVERY pass, clean or
    #      not: "the last scan was clean, an hour ago" is itself the answer the panel needs.
    results_dir.mkdir(parents=True, exist_ok=True)
    latest = results_dir / LATEST_FILE
    latest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    result.written.append(str(latest))

    history = results_dir / HISTORY_FILE
    with open(history, "a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "at": at,
                    "git_sha": result.git_sha,
                    "drift": score["drift"],
                    "state": state,
                    "scanned_state": scanned_state,
                    "transition": transition,
                    "per_axis": {a: b["drift"] for a, b in score["per_axis"].items()},
                    "axes_errored": score["axes_errored"],
                },
                sort_keys=True,
            )
            + "\n"
        )
    result.written.append(str(history))

    result.written.append(str(write_flag_state(results_dir, state_doc)))

    # 4 ── The Redis mirrors (best-effort, never fatal).
    if use_redis and client is None:
        try:
            client = _redis()
            client.ping()
        except Exception:  # noqa: BLE001 — file-only mode is a supported degradation
            client = None
            log("framework Redis unavailable — durable writes done, live mirrors skipped")
    if not use_redis:
        client = None
    result.redis_available = client is not None

    publish_flag_state(client, state_doc)
    publish_board_row(client, row)

    # 5 ── The flag TRANSITION records (edge-triggered — this block is the whole reason the
    #      lifecycle is not noise). Durable line first, then the mirrors, then the KB.
    if transition:
        flag_line = build_flag_line(report, transition=transition, at=at)
        flags_path = results_dir / FLAGS_FILE
        with open(flags_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(flag_line, sort_keys=True) + "\n")
        result.written.append(str(flags_path))

        push_supervisor_flag(client, flag_line)
        result.kb_registered = register_flag_record(flag_line)

        verb = "RAISED" if transition == "raised" else "CLEARED"
        log(f"[FLAG {verb}] {flag_line['why']}")
    else:
        log(
            f"state={state} (unchanged since {since}) drift={score['drift']} "
            f"checked={score['total_checked']}"
        )

    return result


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. See the module docstring for usage and exit codes."""
    parser = argparse.ArgumentParser(
        description="Docs-drift watchdog — scan on a cadence, maintain the flag lifecycle.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--check",
        action="append",
        choices=scan_docs_drift.AXES,
        help="run only this axis (repeatable); default: all six",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="scan and report the would-be transition; write nothing",
    )
    parser.add_argument(
        "--no-redis", action="store_true", help="skip the live mirrors (durable writes only)"
    )
    parser.add_argument(
        "--include-current",
        action="store_true",
        help="serialize every check row into latest.json, not just the findings",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="exit 1 when the flag ends the pass raised (CI use; the timer does not set this)",
    )
    parser.add_argument(
        "--results-dir", help="override the output directory (default: experiments/results/docs_drift)"
    )
    args = parser.parse_args(argv)

    result = run_once(
        axes=tuple(args.check) if args.check else scan_docs_drift.AXES,
        results_dir=Path(args.results_dir) if args.results_dir else None,
        use_redis=not args.no_redis,
        dry_run=args.dry_run,
        include_current=args.include_current,
    )

    # An unmeasured pass is a genuine service failure — it is the one case where the operator
    # should see the unit go red, because the instrument itself is broken.
    if result.state == STATE_UNMEASURED or result.errors:
        log(f"scan could not measure: {result.errors}")
        return 2
    if args.fail_on_drift and result.state == STATE_RAISED:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
