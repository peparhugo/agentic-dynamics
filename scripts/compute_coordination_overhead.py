"""The β coordination-tax instrument driver — coordination_overhead per campaign.

Design: ``docs/designs/proposed/beta_snowball_measurement_design.md`` §2.

    coordination_overhead(campaign) = (wrapper + merge + chain + review) / (cell)

Computed per campaign from the accessible ledgers + git + review records, with the
measured-not-estimated rule (design §6) enforced: only ``wrapper`` and ``cell`` carry a
measured USD cost (the phase-ledger ``total_measured_cost_breakdown``); the merge/chain/review
terms are EVENT COUNTS from their own records, reported alongside — never blended into the
cost ratio. A campaign with no phase-ledger breakdown has ``cell_cost=null`` and ``β=null``
(unmeasured, not zero).

The 2b prior (63% wrapper share, $0.17 of $0.27) is re-derived against the one 2b phase
ledger still on disk and reported as confirmed/corrected/unreproducible.

Usage:
    python scripts/compute_coordination_overhead.py [--json]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import _bootstrap  # noqa: E402
except ImportError:
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.measurement.coordination_overhead import (
    CoordinationComponents,
    coordination_overhead,
    split_breakdown,
    wrapper_share,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "experiments/results"
REVIEWS_DIR = REPO_ROOT / "docs/reviews"
OUT_DIR = REPO_ROOT / "experiments/results/entropy_beta"
OUT_JSON = OUT_DIR / "coordination_overhead.json"
OUT_MD = OUT_DIR / "coordination_overhead.md"

#: The 2b prior quoted by the design — wrapper share 63% ($0.17 of $0.27).
B2B_PRIOR = {"wrapper_share": 0.63, "wrapper_usd": 0.17, "total_usd": 0.27}

#: Campaign → git feature-branch marker (used to count merge/chain/review events per campaign).
CAMPAIGN_MARKERS = {
    "cap_2a_shadow_calibration": "shadow-calibration",
    "cap_2a_rerun": "2a-rerun",
    "cap_2a_rerun2": "2a-rerun2",
    "cap_2a_rerun3": "2a-rerun3",
    "cap_2b": "cap-2b",
    "cap_adaptive_2c": "cap-adaptive-2c",
    "cap_adaptive_2d": "cap-adaptive-2d",
    "cap_adaptive_2e": "cap-adaptive-2e",
    "cap_adaptive_2f": "cap-adaptive-2f",
}


def _git_log(subject_grep: str | None = None, merges_only: bool = False) -> list[str]:
    cmd = ["git", "-C", str(REPO_ROOT), "log", "--pretty=%s"]
    if merges_only:
        cmd.append("--merges")
    out = subprocess.run(cmd, capture_output=True, text=True)
    subjects = [l for l in out.stdout.splitlines() if l.strip()]
    if subject_grep:
        subjects = [s for s in subjects if subject_grep in s]
    return subjects


def _merge_events(marker: str) -> int:
    return len(_git_log(subject_grep=marker, merges_only=True))


def _chain_events(marker: str) -> int:
    """Data-chain (sync/build/manifest) commits referencing the campaign marker.

    The data chain is single-writer and repo-wide; only commits whose message names BOTH the
    campaign AND a chain ritual are attributable to that campaign. Returns the count.
    """
    subjects = _git_log(subject_grep=marker)
    chain = [s for s in subjects if ("data chain" in s or "sync" in s or "manifest" in s or "regen" in s)]
    return len(chain)


def _review_rounds(campaign: str) -> int:
    """Count the review documents for a campaign (known_safe + adversary + any review)."""
    n = 0
    for review in REVIEWS_DIR.glob(f"*{campaign}*.md"):
        n += 1
    # also count the *_known_safe / *_adversary naming that uses the marker, not the campaign id
    return n


def _collect_phase_ledger_breakdowns() -> dict[str, list[dict]]:
    """campaign → list of phase-ledger ``total_measured_cost_breakdown`` dicts."""
    by_campaign: dict[str, list[dict]] = defaultdict(list)
    for root, _dirs, files in __import__("os").walk(RESULTS):
        for fname in files:
            if "phase_ledger" not in fname or not fname.endswith(".json"):
                continue
            path = Path(root) / fname
            try:
                d = json.loads(path.read_text())
            except json.JSONDecodeError:
                continue
            bd = d.get("total_measured_cost_breakdown")
            if not bd:
                continue
            campaign = d.get("campaign") or path.parent.name
            by_campaign[campaign].append(bd)
    return dict(by_campaign)


def _campaign_components(campaign: str, breakdowns: list[dict]) -> CoordinationComponents:
    cell = 0.0
    wrapper = 0.0
    merged_bd: dict[str, float] = defaultdict(float)
    for bd in breakdowns:
        c, w = split_breakdown(bd)
        cell += c
        wrapper += w
        for k, v in bd.items():
            if v is None:
                # Preserve "this phase did not run / was unmeasured" as null — a reader must
                # see the difference between "0.0 measured" and "null (unmeasured)", never a
                # fabricated zero.
                merged_bd.setdefault(k, None)
            else:
                merged_bd[k] = merged_bd.get(k, 0.0) + float(v)
    marker = CAMPAIGN_MARKERS.get(campaign, campaign)
    return CoordinationComponents(
        campaign=campaign,
        cell_cost=round(cell, 8),
        wrapper_cost=round(wrapper, 8),
        merge_events=_merge_events(marker),
        chain_events=_chain_events(marker),
        review_rounds=_review_rounds(campaign),
        cell_source="phase-ledger total_measured_cost_breakdown (CELL_PHASE_KEYS = implement + rework)",
        wrapper_source="phase-ledger total_measured_cost_breakdown (non-cell keys)",
        merge_source="git log --merges (subject contains campaign marker)",
        chain_source="git log (data-chain commits naming campaign)",
        review_source=f"docs/reviews/*{campaign}*.md",
        breakdown=dict(merged_bd),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine JSON to stdout")
    args = parser.parse_args()

    by_campaign = _collect_phase_ledger_breakdowns()
    components: dict[str, CoordinationComponents] = {}
    for campaign, breakdowns in sorted(by_campaign.items()):
        components[campaign] = _campaign_components(campaign, breakdowns)

    rows = []
    for campaign, comp in components.items():
        beta = coordination_overhead(comp.cell_cost, comp.wrapper_cost)
        share = wrapper_share(comp.cell_cost, comp.wrapper_cost)
        rows.append({
            **comp.to_dict(),
            "coordination_overhead_beta": round(beta, 6) if beta is not None else None,
            "wrapper_share": round(share, 6) if share is not None else None,
        })

    # The 2b prior re-derivation.
    b2b = next((r for r in rows if r["campaign"] == "cap_2b"), None)
    if b2b is not None and b2b["wrapper_share"] is not None:
        if abs(b2b["wrapper_share"] - B2B_PRIOR["wrapper_share"]) < 0.01:
            b2b_verdict = "confirmed"
        elif b2b["wrapper_share"] > 0.5:
            b2b_verdict = "directionally_confirmed_not_numerically_reproduced"
        else:
            b2b_verdict = "corrected"
    else:
        b2b_verdict = "unreproducible"

    result = {
        "schema": "coordination_overhead/v1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "formula": "coordination_overhead = (wrapper + merge + chain + review) / cell",
        "cell_phase_keys": ["implement", "rework"],
        "note": (
            "wrapper/cell are measured USD from phase-ledger total_measured_cost_breakdown; "
            "merge/chain/review are event counts (a different unit), reported separately, "
            "never blended into the cost ratio (design §6: measured, never blended)."
        ),
        "b2b_prior": B2B_PRIOR,
        "b2b_rederivation": {
            "campaign": "cap_2b",
            "wrapper_share_measured": b2b["wrapper_share"] if b2b else None,
            "coordination_overhead_beta": b2b["coordination_overhead_beta"] if b2b else None,
            "breakdown": b2b["breakdown"] if b2b else None,
            "verdict": b2b_verdict,
        },
        "campaigns": rows,
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2))
    _write_markdown(result)
    print(f"wrote {OUT_JSON.relative_to(REPO_ROOT)}")
    print(f"wrote {OUT_MD.relative_to(REPO_ROOT)}")
    for r in rows:
        beta = r["coordination_overhead_beta"]
        share = r["wrapper_share"]
        print(f"  {r['campaign']:28s} cell=${r['cell_cost']} wrapper=${r['wrapper_cost']} "
              f"beta={beta} share={share} merge={r['merge_events']} chain={r['chain_events']} review={r['review_rounds']}")


def _write_markdown(result: dict) -> None:
    lines = [
        "# β coordination-tax instrument — corpus measurement",
        "",
        f"schema `coordination_overhead/v1` · generated {result['generated_at']}",
        "",
        f"formula: `{result['formula']}`",
        "",
        result["note"],
        "",
        "## Per-campaign β curve",
        "",
        "| campaign | cell (USD) | wrapper (USD) | β (wrapper/cell) | wrapper share | merge | chain | review |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in result["campaigns"]:
        beta = "—" if r["coordination_overhead_beta"] is None else f"{r['coordination_overhead_beta']:.3f}"
        share = "—" if r["wrapper_share"] is None else f"{r['wrapper_share']:.1%}"
        lines.append(
            f"| {r['campaign']} | {r['cell_cost']} | {r['wrapper_cost']} | {beta} | {share} "
            f"| {r['merge_events']} | {r['chain_events']} | {r['review_rounds']} |"
        )
    lines += [
        "",
        "## The 2b prior re-derivation",
        "",
        f"- prior: wrapper share **{result['b2b_prior']['wrapper_share']:.0%}** "
        f"(${result['b2b_prior']['wrapper_usd']} of ${result['b2b_prior']['total_usd']})",
        f"- re-derived from the one 2b phase ledger on disk: "
        f"share {result['b2b_rederivation']['wrapper_share_measured']}",
        f"- verdict: **{result['b2b_rederivation']['verdict']}**",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
