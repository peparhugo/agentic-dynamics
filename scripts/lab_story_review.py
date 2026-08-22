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
from agentic_dynamics.reporting.lab_contract import (
    ContributionReport,
    attach_contribution,
    record_id,
)
from agentic_dynamics.reporting.measurement_coverage import cost_coverage
from agentic_dynamics.runtime.story import load_story_result

#: This script's name, as classified in scripts/lab_manifest.json — the contract key.
LAB = "lab_story_review.py"
OUTPUT_PATH = Path("experiments/results/lab_story_review.json")


def _captured_cost_stats(cells: list[dict]) -> dict:
    """Captured-only cost coverage for a group of cells (m2 null-not-zero).

    A cell whose cost was never captured must not enter the average as ``0`` — the review's
    P1 story-review finding. Delegates to the shared ``cost_coverage`` primitive.
    """
    return cost_coverage([c["total_cost"] for c in cells], n_total=len(cells))


def _captured_correctness(cells: list[dict]) -> float | None:
    """Mean correctness over the cells that *measured* one (m2 null-not-zero)."""
    values = [c["correctness"] for c in cells if c["correctness"] is not None]
    return round(sum(values) / len(values), 2) if values else None


def _collect_cells(story_payloads: list[dict]) -> tuple[list[dict], list[str]]:
    """Build the per-story cell rows from the canonical payloads.

    Returns ``(cells, used_ids)`` (m3) — the cells plus the record id of every story that
    produced one, so the contract's "used" population is derived from the computation.

    Split out of :func:`main` so the analysis is testable without touching the registry.
    """
    cells = []
    used_ids: list[str] = []

    for d in story_payloads:
        source_path = d.get("_source_path")
        if not source_path:
            continue
        used_ids.append(record_id(d))
        story = load_story_result(Path(source_path))
        # The resolver's relabelled condition, not the raw field.
        cond = d.get("_canonical_condition") or "clean"

        # Test results — m2 null-not-zero: a session that ran no tests has *no* measured
        # correctness; it must not be folded in as 0.0 (the review's P2 finding conflating
        # "tests ran and all failed" with "no verified result exists").
        correctness_values = []
        for s in story.sessions:
            if s.agentic and s.agentic.tests_total > 0:
                correctness_values.append(s.agentic.correctness)

        avg_correctness = (
            sum(correctness_values) / len(correctness_values) if correctness_values else None
        )

        # Timeout detection
        timeout_sessions = []
        for s in story.sessions:
            if s.exit_code != 0 and "timeout" in str(s.error).lower():
                timeout_sessions.append(s.session_number)

        cells.append(
            {
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
            }
        )

    return cells, used_ids


def main():
    tables = load_canonical_tables("story")
    cells, used_ids = _collect_cells(tables.stories)
    print(f"canonical input: {len(tables.stories)} stories ({tables.identity.registry_version})")

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
        avg_cost = _captured_cost_stats(items)["avg_captured_cost"]
        cost_disp = "—" if avg_cost is None else f"${avg_cost:.4f}"
        success = sum(1 for c in items if c["all_successful"])
        timeout = sum(len(c["timeouts"]) for c in items)
        total_sessions = sum(c["sessions"] for c in items)
        print(
            f"  {cond:15s}: {len(items):2d} cells | "
            f"success={success}/{len(items)} ({100 * success // max(len(items), 1)}%) | "
            f"timeouts={timeout}/{total_sessions} sessions | "
            rf"avg_cost={cost_disp}"
        )

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
        avg_cost = _captured_cost_stats(items)["avg_captured_cost"]
        cost_disp = "—" if avg_cost is None else f"${avg_cost:.4f}"
        success = sum(1 for c in items if c["all_successful"])
        timeout = sum(len(c["timeouts"]) for c in items)
        total_sessions = sum(c["sessions"] for c in items)
        avg_corr = _captured_correctness(items)
        corr_disp = "—" if avg_corr is None else f"{avg_corr:.2f}"
        print(
            f"  {story:25s}: {len(items):2d} cells | "
            f"success={success}/{len(items)} ({100 * success // max(len(items), 1)}%) | "
            f"avg_correctness={corr_disp} | "
            f"timeouts={timeout}/{total_sessions} | "
            rf"avg_cost={cost_disp}"
        )

    # ── Table 3: Session Type Timeout Analysis ──
    print()
    print("=" * 70)
    print("TABLE 3: Session Type Timeout Analysis")
    print("=" * 70)

    by_session = defaultdict(list)
    for c in cells:
        for s_num in c["timeouts"]:
            by_session[s_num].append(c["story"])

    session_labels = {
        1: "greenfield",
        2: "feature_addition",
        3: "integration",
        4: "refactor",
        5: "cross_cutting",
    }
    for sn in sorted(by_session):
        stories = by_session[sn]
        rate = len(stories) / len(cells)
        label = session_labels.get(sn, f"session_{sn}")
        print(
            f"  Session {sn} ({label:20s}): timeout_rate={rate:.0%} "
            f"({len(stories)}/{len(cells)} cells): {', '.join(sorted(set(stories))[:3])}"
        )

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
    overall_stats = _captured_cost_stats(cells)
    total_cost = overall_stats["total_captured_cost"]
    total_tokens = sum(c["total_tokens"] for c in cells)
    total_sessions = sum(c["sessions"] for c in cells)
    avg_cost_cell = overall_stats["avg_captured_cost"]
    avg_cost_cell_disp = "—" if avg_cost_cell is None else f"${avg_cost_cell:.4f}"
    print(f"  Cells: {len(cells)}")
    print(f"  Sessions: {total_sessions}")
    print(rf"  Total captured cost: \${total_cost:.4f}")
    print(f"  Total tokens: {total_tokens:,}")
    print(rf"  Avg cost/cell (captured only): {avg_cost_cell_disp}")
    print(rf"  Avg cost/session: \${total_cost / total_sessions:.4f}")

    # ── JSON Output ──
    output = {
        "experiment_id": "lab_story_review",
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "cells": len(cells),
            "sessions": total_sessions,
            "total_cost": round(total_cost, 6),
            "avg_captured_cost": avg_cost_cell,
            "total_captured_cost": round(total_cost, 6),
            "cost_captured_records": overall_stats["cost_captured_records"],
            "total_records": overall_stats["total_records"],
            "cost_coverage": overall_stats["cost_coverage"],
            "total_tokens": total_tokens,
            "by_condition": {
                cond: {
                    "count": len(items),
                    "success_rate": round(
                        sum(1 for c in items if c["all_successful"]) / max(len(items), 1), 2
                    ),
                    "avg_cost": _captured_cost_stats(items)["avg_captured_cost"],
                    "avg_captured_cost": _captured_cost_stats(items)["avg_captured_cost"],
                    "cost_captured_records": _captured_cost_stats(items)["cost_captured_records"],
                    "total_records": _captured_cost_stats(items)["total_records"],
                    "cost_coverage": _captured_cost_stats(items)["cost_coverage"],
                }
                for cond, items in by_condition.items()
            },
            "by_story": {
                story: {
                    "count": len(items),
                    "success_rate": round(
                        sum(1 for c in items if c["all_successful"]) / max(len(items), 1), 2
                    ),
                    "avg_correctness": _captured_correctness(items),
                    "avg_cost": _captured_cost_stats(items)["avg_captured_cost"],
                    "avg_captured_cost": _captured_cost_stats(items)["avg_captured_cost"],
                    "cost_captured_records": _captured_cost_stats(items)["cost_captured_records"],
                    "total_records": _captured_cost_stats(items)["total_records"],
                    "cost_coverage": _captured_cost_stats(items)["cost_coverage"],
                }
                for story, items in by_story.items()
            },
        },
        "cells": cells,
    }

    # m3: the contract is derived from the computation's self-report — every story that
    # produced a cell is used; a story without a payload is simply absent from the corpus.
    contribution = ContributionReport.of(used_record_ids=used_ids)
    attach_contribution(output, LAB, tables, contribution)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"\nSaved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
