"""
Lab Book: Grit — the formal metric, G(s) = P(test_executed_success | perturbation_strength = s).

WHY THIS LAB EXISTS (semantic-integrity release, phase s4)
----------------------------------------------------------
``docs/review/semantic_integrity_review.md`` P0 found that **Grit had two meanings**: the
README and the website define it formally as the probability of test-executed success at a
given perturbation strength, while ``lab_grit_matrix.py`` classified correctness x escape
quadrants and called one of them ``high_grit``. Nothing computed the formal metric — the
site published a definition with no implementation behind it.

Phase s4 resolves the collision both ways at once:

* this lab implements the formal G(s) from canonical records, and
* the quadrant analysis was renamed ``lab_correctness_escape_quadrants.py`` and no longer
  uses the word.

After s4 there is exactly one Grit.

WHAT THE DATA SUPPORTS (the decision the review asked us to ground)
-------------------------------------------------------------------
The metric needs two measured fields on the same cell: ``perturbation_strength`` and
``test_executed_success`` (the independent test runner's verdict — never the agent's
self-report). Both are instrumented, and the canonical registry currently yields **144
such cells**: 64 ``finding`` cells (the single-task perturbation corpus, which carries the
operator and the strength) and 80 ``story`` cells. That is enough to compute G(s), a
per-model ranking, and a per-perturbation-class breakdown — so option (b), implement the
formal metric, is the option the data supports.

Two honest limits, reported in the output rather than smoothed over:

1. **Only two strength levels exist** (0.0 and 0.5). G(s) is two points, not a curve, and
   no dose-response shape can be claimed.
2. **The two levels are not drawn from the same design.** s=0.0 is baseline-only and comes
   entirely from the ``finding`` corpus; s=0.5 mixes ``finding`` and ``story`` cells.
   Comparing them directly confounds strength with corpus. The output therefore carries a
   second, *design-controlled* comparison restricted to the ``finding`` corpus, where both
   levels were produced by the same experiment — that is the comparison to read.

CANONICAL INPUT: the registry resolver only (current ``finding`` + ``story`` rows). The
output embeds a ``lab_contract`` block; ``build_data.py`` re-validates it before publishing.

Usage:
    python scripts/lab_grit.py

Output:
    experiments/results/lab_grit.json
"""

import json
import math
from collections import Counter, defaultdict
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

#: This script's name, as classified in scripts/lab_manifest.json — the contract key.
LAB = "lab_grit.py"
OUTPUT_PATH = Path("experiments/results/lab_grit.json")

#: The metric definition, carried in the output so a reader never has to look it up — and
#: so a guard test can assert the README, the website and this lab state the same thing.
METRIC_DEFINITION = "G(s) = P(test_executed_success | perturbation_strength = s)"

#: Minimum cells before a breakdown row is reported as a rate. Below this a proportion is
#: noise; the row is still emitted (with ``grit: null``) so the gap is visible rather than
#: silently dropped.
MIN_CELLS_FOR_RATE = 5


def _short_model(model: str) -> str:
    return model.split("/")[-1]


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion.

    Chosen over a bootstrap for two reasons: it is **deterministic** (the lab must produce
    byte-identical output across runs — see the s3 determinism check), and it behaves
    correctly at the extremes, where several of these cells sit (a normal-approximation
    interval around p=1.0 would extend above 1).
    """
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
    return (round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4))


def _rate_row(label_key: str, label: str | float, successes: int, n: int, **extra) -> dict:
    """One reported proportion, with its interval and an explicit small-sample marker."""
    lo, hi = wilson_interval(successes, n)
    sufficient = n >= MIN_CELLS_FOR_RATE
    return {
        label_key: label,
        "n": n,
        "successes": successes,
        # None below the threshold: an under-powered proportion is not a measurement.
        "grit": round(successes / n, 4) if (n and sufficient) else None,
        "ci95_lo": lo if sufficient else None,
        "ci95_hi": hi if sufficient else None,
        "insufficient_support": not sufficient,
        **extra,
    }


def _exclusion_reason(has_strength: bool, has_verdict: bool) -> str:
    """The canonical reason a cell was excluded from the metric.

    Both ``perturbation_strength`` and ``test_executed_success`` are required; missing
    either (or both) is one canonical reason — ``missing_required_field`` — the public-truth
    review's P1 vocabulary (the finer strength-vs-verdict split was informational only and
    is folded here so the contract uses exactly the four named reasons).
    """
    return "missing_required_field"


def collect_cells(
    findings: list[dict], stories: list[dict]
) -> tuple[list[dict], dict[str, int], list[str], list[str]]:
    """Every canonical cell carrying BOTH fields the metric needs, plus the exclusion tally.

    A cell missing either field is excluded outright — the metric is a conditional
    probability, and a cell with no strength or no executed verdict cannot condition on
    anything. It is never imputed to 0.0 / False. The returned ``exclusions`` maps each
    reason to its count, so the lab's contract can report *why* cells dropped out (review
    P2: ``n_resolved`` vs ``n_eligible`` vs ``n_excluded``). The returned ``used_refs`` /
    ``excluded_refs`` are the table-qualified record refs of the cells that DID / did NOT
    contribute (m3 ContributionReport; f2 exact contributor attestation).
    """
    cells: list[dict] = []
    exclusions: Counter = Counter()
    used_refs: list[str] = []
    excluded_refs: list[str] = []

    for run in findings:
        strength = run.get("perturbation_strength")
        verdict = run.get("test_executed_success")
        if not isinstance(strength, (int, float)) or not isinstance(verdict, bool):
            exclusions[
                _exclusion_reason(isinstance(strength, (int, float)), isinstance(verdict, bool))
            ] += 1
            excluded_refs.append(record_id(run))
            continue
        used_refs.append(record_id(run))
        cells.append(
            {
                "source": "finding",
                "strength": float(strength),
                "success": verdict,
                "model": _short_model(str(run.get("model") or "unknown")),
                "perturbation_class": run.get("perturbation_class") or "unknown",
                "operator": run.get("operator") or "unknown",
            }
        )

    for story in stories:
        strength = story.get("perturbation_strength")
        verdict = story.get("test_executed_success")
        if not isinstance(strength, (int, float)) or not isinstance(verdict, bool):
            exclusions[
                _exclusion_reason(isinstance(strength, (int, float)), isinstance(verdict, bool))
            ] += 1
            excluded_refs.append(record_id(story))
            continue
        used_refs.append(record_id(story))
        cells.append(
            {
                "source": "story",
                "strength": float(strength),
                "success": verdict,
                "model": _short_model(str(story.get("model") or "unknown")),
                # Stories carry a condition, not an operator class; label it as such rather
                # than forcing it into the finding corpus's vocabulary.
                "perturbation_class": f"story:{story.get('_canonical_condition') or 'clean'}",
                "operator": "story_condition",
            }
        )

    return cells, dict(exclusions), used_refs, excluded_refs


def _group_rates(cells: list[dict], key: str, label_key: str) -> list[dict]:
    """Grit per distinct value of ``key``, sorted by that value.

    Labels keep their original type (``strength`` stays a float, ``model`` stays a string)
    so a consumer never has to guess whether ``"0.5"`` or ``0.5`` will come back.
    """
    groups: dict[str | float, list[dict]] = defaultdict(list)
    for c in cells:
        groups[c[key]].append(c)
    rows = [
        _rate_row(label_key, label, sum(1 for c in items if c["success"]), len(items))
        for label, items in groups.items()
    ]
    rows.sort(key=lambda r: str(r[label_key]))
    return rows


def compute(findings: list[dict], stories: list[dict]) -> tuple[dict, ContributionReport]:
    """Compute the formal Grit metric over the canonical corpus.

    Returns ``(result, contribution)`` (m3): used = cells carrying both fields; excluded
    = cells missing either field (``missing_required_field``).

    Split out of :func:`main` so the analysis is testable without touching the registry.
    """
    cells, exclusions, used_refs, excluded_refs = collect_cells(findings, stories)

    # ── G(s) overall, per strength level ────────────────────────────────────────────
    by_strength: dict[float, list[dict]] = defaultdict(list)
    for c in cells:
        by_strength[c["strength"]].append(c)

    strength_rows = []
    for s in sorted(by_strength):
        items = by_strength[s]
        row = _rate_row(
            "strength",
            s,
            sum(1 for c in items if c["success"]),
            len(items),
            sources={
                "finding": sum(1 for c in items if c["source"] == "finding"),
                "story": sum(1 for c in items if c["source"] == "story"),
            },
        )
        strength_rows.append(row)

    # ── the design-controlled comparison: finding corpus only ───────────────────────
    # Both strength levels exist inside the finding corpus, produced by the same
    # experiment design, so this is the comparison that isolates strength from corpus.
    finding_cells = [c for c in cells if c["source"] == "finding"]
    controlled = _group_rates(finding_cells, "strength", "strength")

    controlled_delta = None
    if len(controlled) == 2 and all(r["grit"] is not None for r in controlled):
        # G(high) - G(low). Reported with both intervals so the reader can see the overlap.
        controlled_delta = round(controlled[-1]["grit"] - controlled[0]["grit"], 4)

    # ── breakdowns ──────────────────────────────────────────────────────────────────
    # Per model, at the perturbed level only: s=0.0 has 1-2 cells per model, far too few
    # to report a per-model baseline.
    perturbed = [c for c in cells if c["strength"] > 0]
    by_model = _group_rates(perturbed, "model", "model")
    by_model.sort(key=lambda r: (r["grit"] is None, -(r["grit"] or 0)))

    by_class = _group_rates(perturbed, "perturbation_class", "perturbation_class")
    by_operator = _group_rates(
        [c for c in perturbed if c["source"] == "finding"], "operator", "operator"
    )

    overall_n = len(cells)
    overall_success = sum(1 for c in cells if c["success"])

    result = {
        "experiment_id": "lab_grit",
        "generated_at": datetime.now().isoformat(),
        "metric_definition": METRIC_DEFINITION,
        "summary": {
            "cells": overall_n,
            "successes": overall_success,
            "grit_overall": round(overall_success / overall_n, 4) if overall_n else None,
            "strength_levels": sorted(by_strength),
            "findings": len(findings),
            "stories": len(stories),
            # The controlled comparison is the headline; the overall one is descriptive.
            "controlled_delta_grit": controlled_delta,
            # Record-count scope (review P2): why resolved cells dropped out of the metric.
            "excluded": sum(exclusions.values()),
            "exclusions": exclusions,
        },
        "by_strength": strength_rows,
        "by_strength_finding_corpus": controlled,
        "by_model_perturbed": by_model,
        "by_perturbation_class_perturbed": by_class,
        "by_operator_perturbed": by_operator,
        "caveats": [
            "Only two perturbation strengths exist in the canonical corpus (0.0 and 0.5); "
            "G(s) is two points, not a dose-response curve.",
            "The s=0.0 level is baseline-only and comes entirely from the finding corpus, "
            "while s=0.5 mixes finding and story cells — read 'by_strength_finding_corpus' "
            "for the design-controlled comparison.",
            "A cell missing perturbation_strength or test_executed_success is excluded, "
            "never imputed; test_executed_success is the independent runner's verdict, "
            "never the agent's self-report.",
            f"Rows with fewer than {MIN_CELLS_FOR_RATE} cells report grit=null "
            "(insufficient_support) rather than an under-powered proportion.",
            "Observational corpus: no multiple-comparison correction across models, "
            "operators, or classes; differences are not claimed to be causal.",
        ],
    }
    contribution = ContributionReport.of(
        used_record_refs=used_refs,
        excluded_record_refs=excluded_refs,
        exclusion_reasons={"missing_required_field": sum(exclusions.values())},
    )
    return result, contribution


def main():
    tables = load_canonical_tables("finding", "story")
    output, contribution = compute(tables.findings, tables.stories)
    attach_contribution(output, LAB, tables, contribution)

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Saved: {OUTPUT_PATH}")
    print(
        f"  canonical input: {len(tables.findings)} findings + {len(tables.stories)} stories "
        f"({tables.identity.registry_version})"
    )
    print(f"  metric: {METRIC_DEFINITION}")
    for row in output["by_strength"]:
        grit = "—" if row["grit"] is None else f"{row['grit']:.3f}"
        print(
            f"    s={row['strength']:<4} n={row['n']:<4} G={grit:>6s} "
            f"(finding={row['sources']['finding']}, story={row['sources']['story']})"
        )
    print("  design-controlled (finding corpus only):")
    for row in output["by_strength_finding_corpus"]:
        grit = "—" if row["grit"] is None else f"{row['grit']:.3f}"
        print(
            f"    s={row['strength']:<4} n={row['n']:<4} G={grit:>6s} "
            f"[{row['ci95_lo']}, {row['ci95_hi']}]"
        )
    print(f"  delta G(0.5) - G(0.0) = {output['summary']['controlled_delta_grit']}")


if __name__ == "__main__":
    main()
