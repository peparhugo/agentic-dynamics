"""rescore_conventions.py — Re-run convention scoring on all worktrees.

Updates the convention score + violations in analysis_{story_id}.json
without re-running AST or SonarQube (which are unaffected by the
score_conventions fix).

Usage:
  python3 scripts/rescore_conventions.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument.commit_analysis import score_conventions
from instrument.language import detect_language

STORIES_DIR = Path(__file__).resolve().parent.parent / "experiments" / "results" / "stories"
ANALYSIS_DIR = Path(__file__).resolve().parent.parent / "experiments" / "results" / "analysis"


def main() -> None:
    updated = 0
    for f in sorted(STORIES_DIR.glob("*.json")):
        if "dvs" in f.name or "log" in f.name:
            continue
        d = json.loads(f.read_text())
        wt = Path(d.get("worktree", ""))
        if not wt.exists():
            continue
        sid = f.stem.split("_")[-1]
        af = ANALYSIS_DIR / f"analysis_{sid}.json"
        if not af.exists():
            continue

        profile = detect_language(wt)
        score, violations = score_conventions(wt, profile=profile)

        a = json.loads(af.read_text())
        # Update per-commit convention entries
        for c in a.get("commits", []):
            c["convention"] = {"score": score, "violations": violations}
        # Update summary average
        a.setdefault("summary", {})["average_convention_score"] = round(score, 3)

        af.write_text(json.dumps(a, indent=2))
        updated += 1

    print(f"Rescored conventions for {updated} stories")


if __name__ == "__main__":
    main()
