#!/usr/bin/env python3
"""Recording sweep — the deterministic rail for decision-record coverage.

Scans the machine's own record surfaces and reconciles them:

* **Day coverage**: for each day with main commits, does the record layer show a decision
  record or a session close that accounts for it? A commit-heavy day with zero decisions
  AND no covering close is a recording gap (the 2026-09-08 discipline audit's class: the
  acts happened, nothing recorded them until a manual backfill). **A close covers the days
  BEFORE it, never its own day** (see :func:`scan`: the close written for day D is the act
  being audited, not evidence that D's acts were recorded at the moment — otherwise the
  close written at close-time would self-mask the very gap it is meant to catch, the
  ``aio_controller_postmortem`` A1 finding).
* **Close claims** (rail B): a session close whose ``merged``/``open_threads`` text cites
  a ``decision record <id>`` must have that artifact on disk — a phantom claim (the
  ``80f02d3ce5`` class) is flagged.

Modes:

    python3 scripts/recording_sweep.py --scan      # report gaps, exit 1 if any (2 = unmeasured)
    python3 scripts/recording_sweep.py --backfill  # record a decision per gap day
    python3 scripts/recording_sweep.py --report    # write experiments/results/recording/audit.json

**Unmeasured is a first-class result (A7).** The post-migration data root
(``experiments/results/kb``) is untracked runtime state: a source checkout has no corpus,
so a sweep there can only fabricate gaps from commits it cannot reconcile. On absent
runtime data every mode returns ``status: unmeasured`` and exits 2 — ``--report`` writes
nothing and ``--backfill`` refuses to mutate (reconstructed decisions are the machine's
account of acts; minting them without evidence is exactly the record-layer lie this rail
exists to catch).

The sweep is the machine proposing: backfilled decisions are reconstructed rationale
(what/why from the commit messages + transition reasons), actor ``recording-sweep``,
never fabricated intent. Zero model calls; deterministic; rerun-safe (a day already
accounted for is never re-recorded).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTOR = "recording-sweep"
LOOKBACK_DAYS = 14
AUDIT_PATH = ROOT / "experiments" / "results" / "recording" / "audit.json"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True
    ).stdout


def _decision_days() -> set[str]:
    """Days (YYYY-MM-DD) that have at least one decision record artifact."""
    days: set[str] = set()
    for path in (ROOT / "experiments/results/kb").glob("*.json"):
        try:
            d = json.loads(path.read_text())
            text = d.get("text") or ""
            if '"category"' not in text or "decided_at" not in text:
                continue
            body = json.loads(text)
            if body.get("decided_at"):
                days.add(str(body["decided_at"])[:10])
        except Exception:
            continue
    return days


def _close_days() -> set[str]:
    """Days that have at least one session close (meta_session) artifact.

    A close's ``text`` is the retrieval prose summary (the F3 fix) that opens with
    ``session close <session_date>`` — legacy ledger ``meta_session`` attempt records
    share the source_type, so the prefix is the discriminator, never the JSON body.
    """
    days: set[str] = set()
    for path in (ROOT / "experiments/results/kb").glob("*.json"):
        try:
            d = json.loads(path.read_text())
            if d.get("source_type") != "meta_session":
                continue
            text = d.get("text") or ""
            m = re.match(r"session close (\d{4}-\d{2}-\d{2})\b", text)
            if m:
                days.add(m.group(1))
        except Exception:
            continue
    return days


def _main_commits_by_day() -> dict[str, list[str]]:
    """First-parent main commits (subject + date) over the lookback window."""
    since = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    out = _git(
        "log",
        "--first-parent",
        "--since=" + since,
        "--format=%ad|%h|%s",
        "--date=format:%Y-%m-%d",
        "main",
    )
    by_day: dict[str, list[str]] = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        day, sha, subject = line.split("|", 2)
        by_day.setdefault(day, []).append(f"{sha[:8]} {subject[:90]}")
    return by_day


def _phantom_close_claims() -> list[str]:
    """Close records citing ``decision record <id>`` whose artifact is missing.

    The citation is matched as a **prefix** (6–64 hex), not only as a full 64-char id: closes
    in this corpus cite the short human form (``…, decision record 80f02d3ce5``), and the
    artifact filename IS the 64-char ``knowledge_id``. A cited id is a phantom when no known
    artifact stem starts with it. This prefix form was the verified fix of the
    ``aio_controller_postmortem`` p5 replay (the original 64-hex-only regex never fired on the
    historical citation that a backfill later had to repair).
    """
    known = {p.stem for p in (ROOT / "experiments/results/kb").glob("*.json")}
    phantoms: list[str] = []
    for path in (ROOT / "experiments/results/kb").glob("*.json"):
        try:
            text = path.read_text()
        except Exception:
            continue
        for m in re.finditer(r"decision record ([0-9a-f]{6,64})", text):
            cited = m.group(1)
            if not any(stem.startswith(cited) for stem in known):
                phantoms.append(f"{path.stem[:12]}: cites {cited[:16]}... (no artifact)")
    return phantoms


def _kb_dir() -> Path:
    """The runtime KB artifact directory the coverage scan reads (untracked post-migration)."""
    return ROOT / "experiments" / "results" / "kb"


def _unmeasured_report(reason: str) -> dict:
    """The explicit "cannot measure" result — never a fabricated empty gap set.

    The callers treat ``status: unmeasured`` as a refusal (exit 2), so a source checkout can
    neither report a false gap nor backfill a reconstruction it has no evidence for (A7).
    """
    return {
        "status": "unmeasured",
        "reason": reason,
        "generated_at": datetime.now(timezone_utc()).isoformat(),
        "window_days": LOOKBACK_DAYS,
        "commit_days": 0,
        "decided_days": 0,
        "closed_days": 0,
        "gap_days": [],
        "gaps": {},
        "phantom_close_claims": [],
    }


def scan() -> dict:
    """The gap report: commit-days without decision/close coverage + phantom claims.

    ``status`` is ``"measured"`` on a real scan and ``"unmeasured"`` (with a ``reason``) when
    the runtime data root is absent or git is unavailable — the caller must not read a
    measurement out of an unmeasured report.

    **Coverage invariant (A1).** A commit-day is covered by a decision record dated that day,
    or by a session close dated **strictly later** than the day. A close is a retrospective
    attestation of the days it follows; it never covers its own day. The close-time probe
    runs *after* the close is written, so the pre-fix ``day in closed`` check made the close
    being audited satisfy its own audit (a same-day close always "covered" the day it was
    checking). The strict-later rule removes that self-mask.
    """
    if not _kb_dir().is_dir():
        return _unmeasured_report("no KB artifact dir on disk")
    try:
        commits = _main_commits_by_day()
    except Exception as exc:  # noqa: BLE001 — git unavailable is an unmeasured state, not a crash
        return _unmeasured_report(f"git unavailable: {type(exc).__name__}: {exc}")
    decided = _decision_days()
    closed = _close_days()
    gaps = {
        day: commits[day]
        for day in sorted(commits)
        if day not in decided and not any(close_day > day for close_day in closed)
    }
    return {
        "status": "measured",
        "generated_at": datetime.now(timezone_utc()).isoformat(),
        "window_days": LOOKBACK_DAYS,
        "commit_days": len(commits),
        "decided_days": len(decided),
        "closed_days": len(closed),
        "gap_days": list(gaps.keys()),
        "gaps": gaps,
        "phantom_close_claims": _phantom_close_claims(),
    }


def timezone_utc():
    return datetime.now().astimezone().tzinfo


def backfill(report: dict) -> list[str]:
    """Record one decision per gap day (reconstructed rationale, rerun-safe).

    Refuses outright on an unmeasured report: a reconstruction is only legitimate when the
    sweep actually measured the gap. Minting one from an unmeasured sweep would write the
    record-layer lie (a decision for a day we did not inspect) this rail exists to prevent.
    """
    if report.get("status") != "measured":
        raise ValueError("refusing to backfill on an unmeasured report")
    recorded: list[str] = []
    for day in report.get("gap_days", []):
        subjects = report["gaps"][day]
        what = f"recording-sweep coverage backfill for {day} ({len(subjects)} main commits)"
        why = (
            "day had main commits but no decision record and no session close; "
            + ("; ".join(subjects)[:400])
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/decision_record.py"),
                "--what",
                what,
                "--why",
                why,
                "--category",
                "recording",
                "--actor",
                ACTOR,
                "--decided-at",
                day + "T23:59:59+00:00",
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            recorded.append(day)
    return recorded


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    report = scan()
    if report.get("status") == "unmeasured":
        # A7: no runtime data => no measurement. Refuse every mutation (the audit write and
        # the decision backfill) and never report a gap we did not measure. Exit 2 is the
        # house "unmeasurable" code (distinct from 0 clean / 1 measured-gap).
        print(
            f"recording_sweep: UNMEASURED — {report.get('reason')}; refused to report or backfill",
            file=sys.stderr,
        )
        return 2
    if args.report or not (args.scan or args.backfill):
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        AUDIT_PATH.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    if args.scan and report["gap_days"]:
        print(f"GAPS: {len(report['gap_days'])} uncovered day(s)", file=sys.stderr)
        return 1
    if args.backfill:
        recorded = backfill(report)
        print(f"backfilled {len(recorded)} day(s): {recorded}")
        return 0 if recorded or not report["gap_days"] else 1
    return 0 if not report["gap_days"] else 1


if __name__ == "__main__":
    sys.exit(main())
