"""backfill_deep_metrics.py — add LSP + solution + basin + strategy to existing analysis files.

The deep metrics (LSP diagnostics, solution evaluation, basin escape, strategy
classification) were added to the story analysis after the first analysis pass.
This backfills them into existing ``analysis_{story_id}.json`` files without
re-running SonarQube (the deep metrics are cheap — file reads + LSP + computation).

Usage:
    python3 scripts/backfill_deep_metrics.py --dry-run   # preview
    python3 scripts/backfill_deep_metrics.py             # apply

Requires LSP tools on PATH: pyright (Python), tsc (TypeScript).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from instrument.commit_analysis import compute_deep_metrics, agentic_token_dicts
from instrument.story import load_story_result

RESULTS_DIR = ROOT / "experiments" / "results" / "stories"
ANALYSIS_DIR = ROOT / "experiments" / "results" / "analysis"


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    done = skipped = failed = 0

    for f in sorted(RESULTS_DIR.glob("*.json")):
        sr = load_story_result(f)
        out = ANALYSIS_DIR / f"analysis_{sr.story_id}.json"
        if not out.exists():
            skipped += 1
            continue

        existing = json.loads(out.read_text())
        if "deep" in existing:
            skipped += 1
            continue

        worktree = Path(sr.worktree)
        if not worktree.exists():
            failed += 1
            continue

        deep = compute_deep_metrics(
            worktree,
            story_name=sr.story_name,
            model=sr.model,
            test_passed=sr.all_successful,
            total_cost_usd=sr.total_cost,
            session_token_data=agentic_token_dicts(sr.sessions),
        )
        existing["deep"] = deep
        if not dry_run:
            out.write_text(json.dumps(existing, indent=2))
        done += 1
        print(
            f"  {sr.story_id[:8]} {sr.story_name:20s} {sr.model.split('/')[-1]:12s} "
            f"strategy={deep['strategy'].get('strategy','?')} "
            f"basin={deep['basin'].get('escape_score', 0):.2f} "
            f"lsp={deep['lsp']['available']} ({deep['lsp'].get('errors',0)}e/{deep['lsp'].get('warnings',0)}w)"
        )

    print(f"Done: {done} updated, {skipped} skipped, {failed} failed" + (" (dry-run)" if dry_run else ""))


if __name__ == "__main__":
    main()
