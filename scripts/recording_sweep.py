#!/usr/bin/env python3
"""Recording sweep — the deterministic rail for decision-record coverage.

Scans the machine's own record surfaces and reconciles them:

* **Day coverage**: for each day with main commits, does the record layer show a decision
  record or a session close that accounts for it? A commit-heavy day with zero decisions
  AND zero closes is a recording gap (the 2026-09-08 discipline audit's class: the acts
  happened, nothing recorded them until a manual backfill).
* **Close claims** (rail B): a session close whose ``merged``/``open_threads`` text cites
  a ``decision record <id>`` must have that artifact on disk — a phantom claim (the
  ``80f02d3ce5`` class) is flagged.

Modes:

    python3 scripts/recording_sweep.py --scan      # report gaps, exit 1 if any
    python3 scripts/recording_sweep.py --backfill  # record a decision per gap day
    python3 scripts/recording_sweep.py --report    # write experiments/results/recording/audit.json

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
        "log", "--first-parent", "--since=" + since,
        "--format=%ad|%h|%s", "--date=format:%Y-%m-%d", "main",
    )
    by_day: dict[str, list[str]] = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        day, sha, subject = line.split("|", 2)
        by_day.setdefault(day, []).append(f"{sha[:8]} {subject[:90]}")
    return by_day


def _phantom_close_claims() -> list[str]:
    """Close records citing ``decision record <id>`` whose artifact is missing."""
    known = {p.stem for p in (ROOT / "experiments/results/kb").glob("*.json")}
    phantoms: list[str] = []
    for path in (ROOT / "experiments/results/kb").glob("*.json"):
        try:
            text = path.read_text()
        except Exception:
            continue
        for m in re.finditer(r"decision record ([0-9a-f]{64})", text):
            if m.group(1) not in known:
                phantoms.append(f"{path.stem[:12]}: cites {m.group(1)[:16]}... (no artifact)")
    return phantoms


def scan() -> dict:
    """The gap report: commit-days without decision/close coverage + phantom claims."""
    commits = _main_commits_by_day()
    decided = _decision_days()
    closed = _close_days()
    gaps = {
        day: commits[day]
        for day in sorted(commits)
        if day not in decided and day not in closed
    }
    return {
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
    """Record one decision per gap day (reconstructed rationale, rerun-safe)."""
    recorded: list[str] = []
    for day in report.get("gap_days", []):
        subjects = report["gaps"][day]
        what = f"recording-sweep coverage backfill for {day} ({len(subjects)} main commits)"
        why = "day had main commits but no decision record and no session close; " + (
            "; ".join(subjects)[:400]
        )
        proc = subprocess.run(
            [
                sys.executable, str(ROOT / "scripts/decision_record.py"),
                "--what", what, "--why", why,
                "--category", "recording", "--actor", ACTOR,
                "--decided-at", day + "T23:59:59+00:00",
            ],
            capture_output=True, text=True,
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
