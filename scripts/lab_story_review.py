"""
Lab Book 14: Multi-Session Story Review — condition comparison tables, cascade
analysis, and cost summary over the canonical story corpus.

CANONICAL INPUT (semantic-integrity release, phase s2): publication-eligible, so the
input is the registry resolver only (``lifecycle_state == "current"`` story rows). The
typed ``load_story_result`` loader is still used, but on the paths the REGISTRY resolved
(``_source_path``) — never on a directory glob. Conditions come from the resolver's
no-op relabel (``_canonical_condition``).

The output embeds a ``lab_contract`` block that ``build_data.py`` re-validates.

Usage:
    python scripts/lab_story_review.py

Output:
    experiments/results/lab_story_review.json
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.reporting.canonical_corpus import load_canonical_tables
from agentic_dynamics.reporting.lab_contract import attach_contract
from agentic_dynamics.runtime.story import load_story_result

#: This script's name, as classified in scripts/lab_manifest.json — the contract key.
LAB = "lab_story_review.py"
OUTPUT_PATH = Path("experiments/results/lab_story_review.json")


def _collect_cells(story_payloads: list[dict]) -> list[dict]:
    """Build the per-story cell rows from the canonical payloads.

    Split out of :func:`main` so the analysis is testable without touching the registry.
    """
    cells = []

    for d in story_payloads:
        source_path = d.get("_source_path")
        if not source_path:
            continue
        story = load_story_result(Path(source_path))
        # The resolver's relabelled condition, not the raw field.
        cond = d.get("_canonical_condition") or "clean"

        # Test results
        correctness_values = []
        for s in story.sessions:
            if s.agentic and s.agentic.tests_total > 0:
                correctness_values.append(s.agentic.correctness)
            else:
                correctness_values.append(0.0)

        avg_correctness = sum(correctness_values) / len(correctness_values) if correctness_values else 0.0

        # Timeout detection
        timeout_sessions = []
        for s in story.sessions:
            if s.exit_code != 0 and "timeout" in str(s.error).lower():
                timeout_sessions.append(s.session_number)

        cells.append({
            "story": story.story_name,
            "condition": cond,
            "sessions": story.session_count,
            "correctness": avg_correctness,
            "correctness_values": correctness_values,
            "all_successful": story.all_successful,
            "cascade_recovery": story.cascade_recovery,
            "timeouts": timeout_sessions,
            "total_cost": story.total_cost,
            "total_tokens": story.total_tokens,
            "worktree": story.worktree,
            "result_file": str(source_path),
        })

    return cells


def main():
    tables = load_canonical_tables("story")
    cells = _collect_cells(tables.stories)
    print(f"canonical input: {len(tables.stories)} stories "
          f"({tables.identity.registry_version})")

    # ── Table 1: Condition Comparison ──
    print("=" * 70)
    print("TABLE 1: Condition Comparison")
    print("=" * 70)

    by_condition = defaultdict(list)
    for c in cells:
        by_condition[c["condition"]].append(c)

    for cond in ["clean", "early_degrade", "bad_seed"]:
        items = by_condition.get(cond, [])
        if not items:
            continue
        avg_cost = sum(c["total_cost"] for c in items) / len(items)
        success = sum(1 for c in items if c["all_successful"])
        timeout = sum(len(c["timeouts"]) for c in items)
        total_sessions = sum(c["sessions"] for c in items)
        print(f"  {cond:15s}: {len(items):2d} cells | "
              f"success={success}/{len(items)} ({100*success//max(len(items),1)}%) | "
              f"timeouts={timeout}/{total_sessions} sessions | "
              rf"avg_cost=\${avg_cost:.4f}")

    # ── Table 2: Story Type Comparison ──
    print()
    print("=" * 70)
    print("TABLE 2: Story Type Comparison")
    print("=" * 70)

    by_story = defaultdict(list)
    for c in cells:
        by_story[c["story"]].append(c)

    for story in sorted(by_story):
        items = by_story[story]
        avg_cost = sum(c["total_cost"] for c in items) / len(items)
        success = sum(1 for c in items if c["all_successful"])
        timeout = sum(len(c["timeouts"]) for c in items)
        total_sessions = sum(c["sessions"] for c in items)
        avg_corr = sum(c["correctness"] for c in items) / len(items)
        print(f"  {story:25s}: {len(items):2d} cells | "
              f"success={success}/{len(items)} ({100*success//max(len(items),1)}%) | "
              f"avg_correctness={avg_corr:.2f} | "
              f"timeouts={timeout}/{total_sessions} | "
              rf"avg_cost=\${avg_cost:.4f}")

    # ── Table 3: Session Type Timeout Analysis ──
    print()
    print("=" * 70)
    print("TABLE 3: Session Type Timeout Analysis")
    print("=" * 70)

    by_session = defaultdict(list)
    for c in cells:
        for s_num in c["timeouts"]:
            by_session[s_num].append(c["story"])

    session_labels = {1: "greenfield", 2: "feature_addition", 3: "integration",
                      4: "refactor", 5: "cross_cutting"}
    for sn in sorted(by_session):
        stories = by_session[sn]
        rate = len(stories) / len(cells)
        label = session_labels.get(sn, f"session_{sn}")
        print(f"  Session {sn} ({label:20s}): timeout_rate={rate:.0%} "
              f"({len(stories)}/{len(cells)} cells): {', '.join(sorted(set(stories))[:3])}")

    # ── Table 4: Cascade Analysis (EARLY_DEGRADE) ──
    print()
    print("=" * 70)
    print("TABLE 4: Cascade Analysis (EARLY_DEGRADE Only)")
    print("=" * 70)

    early_cells = [c for c in cells if c["condition"] == "early_degrade"]
    for c in early_cells:
        s1 = c["correctness_values"][0] if c["correctness_values"] else 0
        s5 = c["correctness_values"][-1] if len(c["correctness_values"]) >= 5 else s1
        recovered = s5 > s1
        degraded = s5 < s1
        status = "recovered" if recovered else ("degraded" if degraded else "same")
        print(f"  {c['story'][:25]:25s} S1={s1:.2f} S5={s5:.2f} ({status})")

    # ── Table 5 (REMOVED) ──
    # A hard-coded "Most Common Reviewer-Identified Problems" table used to be printed
    # here with the comment "Simulated — in reality these come from parsing review
    # outputs", and percentages computed against a hard-coded n=26. Under the canonical
    # lab contract a publication-eligible lab may not emit invented numbers, not even to
    # stdout. Deriving the real distribution requires parsing review findings text; until
    # that is measured, the signal is simply absent.

    # ── Cost Summary ──
    print()
    print("=" * 70)
    print("COST SUMMARY")
    print("=" * 70)
    total_cost = sum(c["total_cost"] for c in cells)
    total_tokens = sum(c["total_tokens"] for c in cells)
    total_sessions = sum(c["sessions"] for c in cells)
    print(f"  Cells: {len(cells)}")
    print(f"  Sessions: {total_sessions}")
    print(rf"  Total cost: \${total_cost:.4f}")
    print(f"  Total tokens: {total_tokens:,}")
    print(rf"  Avg cost/cell: \${total_cost/len(cells):.4f}")
    print(rf"  Avg cost/session: \${total_cost/total_sessions:.4f}")

    # ── JSON Output ──
    output = {
        "experiment_id": "lab_story_review",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "cells": len(cells),
            "sessions": total_sessions,
            "total_cost": round(total_cost, 6),
            "total_tokens": total_tokens,
            "by_condition": {
                cond: {
                    "count": len(items),
                    "success_rate": round(sum(1 for c in items if c["all_successful"]) / max(len(items), 1), 2),
                    "avg_cost": round(sum(c["total_cost"] for c in items) / len(items), 6),
                }
                for cond, items in by_condition.items()
            },
            "by_story": {
                story: {
                    "count": len(items),
                    "success_rate": round(sum(1 for c in items if c["all_successful"]) / max(len(items), 1), 2),
                    "avg_correctness": round(sum(c["correctness"] for c in items) / len(items), 2),
                    "avg_cost": round(sum(c["total_cost"] for c in items) / len(items), 6),
                }
                for story, items in by_story.items()
            },
        },
        "cells": cells,
    }

    attach_contract(output, LAB, tables, n_input_records=len(tables.stories))
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"\nSaved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
