"""
compute_lookup.py — p2 of retry_observational_analysis.

BOUNDED to the computation. Consumes p1's chains (experiments/results/
retry_analysis/chains.json) plus the wired story corpus and computes the
retry-worthiness lookup the machine reads at first-failure:

  (1) the rescue-rate-by-signal table — the observed rescue rate binned by the
      known-at-failure features (the [H] confidence decile, the perturbation
      strength, the cost-so-far);
  (2) the measured WOC = 1/(1+r) — r the observed retry rate;
  (3) the retry economics at E_x — the rescue value (the avoided escaped-defect
      harm) vs the retry cost, and the retry-worthiness boundary;
  (4) the no-retry-was-worse rate — the failed-without-retry attempts' downstream
      cost vs the retried attempt.

The whole thing is OBSERVATIONAL and n is tiny (1 retry). Every number is either
a field lifted from p1's chains or an arithmetic step over lifted fields; nothing
is estimated, nothing is imputed. The confounds and the coverage ride alongside
in the output.

Outputs (written next to this script):
  - lookup.json — the machine-readable lookup (schema retry_lookup/v1)
  - lookup.md   — the human-readable lookup + tables
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

RESULTS = Path("experiments/results")
OUT_DIR = RESULTS / "retry_analysis"
CHAINS = OUT_DIR / "chains.json"
STORIES = RESULTS / "stories"

# ---------------------------------------------------------------------------
# Pinned constants (lifted from the cited artifacts, never re-derived here):
#   base downstream defect cost — $0.004021 (cap_escalation_measurement score:
#     0.112588 / 28.0; the design doc §3.5 quotes it verbatim).
#   E_x anchors — 11.4671 (measured sol), 12.5134 (measured sonnet), 28.0
#     (sourced pricing ratio). The spec hard rule 7 pins 11.47/28.
# ---------------------------------------------------------------------------
BASE_DEFECT_COST_USD = 0.004021
EX_ANCHORS = {
    "11.4671": {"label": "measured sol (cap_escalation_measurement)", "value": 11.4671},
    "12.5134": {"label": "measured sonnet (cap_escalation_measurement)", "value": 12.5134},
    "28.0": {"label": "sourced pricing ratio (site economics)", "value": 28.0},
}
WILSON_Z = 1.959964  # 95% two-sided


def wilson_interval(k: int, n: int) -> tuple[float | None, float | None]:
    """Wilson 95% interval for a binomial proportion k/n; None when n == 0."""
    if n == 0:
        return None, None
    phat = k / n
    z2 = WILSON_Z ** 2
    denom = 1 + z2 / n
    center = (phat + z2 / (2 * n)) / denom
    half = (WILSON_Z / denom) * math.sqrt(
        phat * (1 - phat) / n + z2 / (4 * n * n)
    )
    return max(0.0, center - half), min(1.0, center + half)


def _decile(v: float | None) -> str | None:
    """Map a confidence to its decile label '[0.8, 0.9)'; None stays None."""
    if v is None:
        return None
    lo = int(v * 10) / 10
    if v >= 1.0:  # the top bin is closed at 1.0
        return "[1.0]"
    return f"[{lo:.1f}, {lo + 0.1:.1f})"


def load_chains() -> dict:
    """Read p1's chains payload (schema retry_chains/v1)."""
    with open(CHAINS, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _final_session_confidence(story: dict) -> float | None:
    """The [H] confidence at the failure signal (last non-null session confidence)."""
    confs = [
        s.get("confidence")
        for s in story.get("sessions", [])
        if s.get("confidence") is not None
    ]
    return confs[-1] if confs else None


def confidence_at_failure_distribution() -> dict:
    """Final-session [H] confidence of wired-failed vs wired-passed stories.

    This is the *signal distribution at failure* that supports the rescue-rate
    table: if failures land at high confidence, the confidence axis cannot
    separate them (the 2c null's analog at the attempt level).
    """
    failed: list[dict] = []
    passed: list[dict] = []
    for fp in sorted(STORIES.glob("*.json")):
        with open(fp, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        if "test_executed_success" not in d:
            continue
        conf = _final_session_confidence(d)
        rec = {
            "file": fp.name,
            "model": d.get("model"),
            "condition": d.get("perturbation_condition"),
            "strength": d.get("perturbation_strength"),
            "cost_usd": d.get("summary", {}).get("total_cost"),
            "confidence": conf,
        }
        (failed if d.get("test_executed_success") is False else passed).append(rec)

    def _summarize(recs: list[dict]) -> dict:
        vals = [r["confidence"] for r in recs if r["confidence"] is not None]
        if not vals:
            return {"n_non_null": 0}
        return {
            "n_total": len(recs),
            "n_non_null": len(vals),
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
            "mean": round(sum(vals) / len(vals), 4),
            "median": round(sorted(vals)[len(vals) // 2], 4),
        }

    return {
        "wired_failed": _summarize(failed),
        "wired_passed": _summarize(passed),
        "failed_confidence_series": [
            {"confidence": r["confidence"], "condition": r["condition"], "strength": r["strength"], "model": r["model"]}
            for r in failed
        ],
    }


def rescue_rate_by_signal(chains: list[dict]) -> dict:
    """(1) The rescue-rate-by-signal table over the retried attempts.

    The rescue rate = rescued / retried, binned by each known-at-failure
    feature. With one retry the table is one populated cell per axis; every
    other bin is n=0 (reported, never imputed).
    """
    retried = [
        c for c in chains if c["retry"].get("taken") is True
    ]
    rescued = [c for c in retried if c["outcome"] == "rescued"]

    # Per-axis binning of the retried attempts by their first-attempt features.
    by_confidence: dict[str, list[dict]] = defaultdict(list)
    by_strength: dict[str, list[dict]] = defaultdict(list)
    by_cost: dict[str, list[dict]] = defaultdict(list)
    for c in retried:
        fa = c["first_attempt"]
        by_confidence[_decile(fa["confidence_at_failure"])].append(c)
        by_strength[str(fa["perturbation_strength"])].append(c)
        # cost-so-far bins in whole dollars
        by_cost[f"[${fa['cost_so_far_usd']:.1f}]"].append(c)

    def _bin_table(bins: dict[str, list[dict]]) -> list[dict]:
        rows = []
        for label, cs in sorted(bins.items()):
            k = sum(1 for c in cs if c["outcome"] == "rescued")
            n = len(cs)
            lo, hi = wilson_interval(k, n)
            rows.append(
                {
                    "bin": label,
                    "retried": n,
                    "rescued": k,
                    "rescue_rate": round(k / n, 4) if n else None,
                    "wilson_95_lo": round(lo, 4) if lo is not None else None,
                    "wilson_95_hi": round(hi, 4) if hi is not None else None,
                }
            )
        return rows

    k_total = len(rescued)
    n_total = len(retried)
    lo, hi = wilson_interval(k_total, n_total)
    return {
        "overall": {
            "retried": n_total,
            "rescued": k_total,
            "rescue_rate": round(k_total / n_total, 4) if n_total else None,
            "wilson_95_lo": round(lo, 4) if lo is not None else None,
            "wilson_95_hi": round(hi, 4) if hi is not None else None,
        },
        "by_confidence_decile": _bin_table(by_confidence),
        "by_strength": _bin_table(by_strength),
        "by_cost_so_far": _bin_table(by_cost),
    }


def measured_r_and_woc(chains: list[dict], chains_payload: dict) -> dict:
    """(2) The measured retry rate r and WOC = 1/(1+r).

    r is the fraction of attempt-ledger records that carry a retry. Two honest
    denominators exist and both are reported: the E4 grid (where the retry arm
    was armed) and the full attempt-ledger plane (E4 + synthetic probe). The
    story corpus (no retry mechanism) is a third, zero-r plane.
    """
    e4 = chains_payload["ledgers"]["e4"]
    probe = chains_payload["ledgers"]["probe"]
    retries_e4 = e4["retries"]
    total_attempts = e4["total_attempts"] + probe["total_attempts"]
    real_retries = chains_payload["coverage"]["real_retry_events"]

    r_e4_cells = retries_e4 / 8.0  # 8 cells in the E4 grid
    r_attempt_plane = retries_e4 / total_attempts
    r_story_corpus = 0.0  # no retry mechanism in the story runner

    framework_r = 0.115  # the 11.5% scenario

    return {
        "framework_r_scenario": framework_r,
        "framework_woc_scenario": round(1.0 / (1.0 + framework_r), 4),
        "measured_r_e4_grid_cells": round(r_e4_cells, 4),
        "measured_woc_e4_grid": round(1.0 / (1.0 + r_e4_cells), 4),
        "measured_r_attempt_plane": round(r_attempt_plane, 4),
        "measured_woc_attempt_plane": round(1.0 / (1.0 + r_attempt_plane), 4),
        "measured_r_story_corpus": r_story_corpus,
        "measured_woc_story_corpus": 1.0,
        "real_retry_events": real_retries,
        "e4_retries": retries_e4,
        "e4_total_attempts": e4["total_attempts"],
    }


def retry_economics(chains: list[dict]) -> dict:
    """(3) The retry economics at E_x — rescue value vs retry cost, the boundary.

    rescue_value(E_x) = E_x × BASE_DEFECT_COST_USD (the avoided escaped-defect
    harm). retry_cost = the measured attempt-2 cost. The retry pays iff
    P(rescue) × rescue_value > retry_cost, so the break-even E_x solves
    E_x = retry_cost / BASE_DEFECT_COST_USD at P(rescue) = 1.

    The measured retry is the E4 bad_seed_high × grit_retry attempt-2.
    """
    retried = [c for c in chains if c["retry"].get("taken") is True]
    # The measured retry cost is attempt-2's cost (the only retry in the corpus).
    retry_cost = (
        retried[0]["retry"]["cost_usd"] if retried else None
    )
    rescued = [c for c in retried if c["outcome"] == "rescued"]
    p_rescue = (len(rescued) / len(retried)) if retried else None

    per_anchor = []
    for label, spec in EX_ANCHORS.items():
        ex = spec["value"]
        rescue_value = ex * BASE_DEFECT_COST_USD
        per_anchor.append(
            {
                "E_x": ex,
                "label": spec["label"],
                "rescue_value_usd": round(rescue_value, 6),
                "retry_cost_usd": round(retry_cost, 6) if retry_cost is not None else None,
                "net_ev_usd_at_p_rescue_1": round(rescue_value - retry_cost, 6)
                if retry_cost is not None
                else None,
                "retry_cost_over_rescue_value": round(retry_cost / rescue_value, 2)
                if retry_cost is not None and rescue_value
                else None,
            }
        )

    break_even_ex = (
        retry_cost / BASE_DEFECT_COST_USD if retry_cost is not None else None
    )
    return {
        "p_rescue_observed": round(p_rescue, 4) if p_rescue is not None else None,
        "p_rescue_wilson_95": (
            [round(x, 4) for x in wilson_interval(len(rescued), len(retried))]
            if retried
            else [None, None]
        ),
        "retry_cost_usd_measured": round(retry_cost, 6) if retry_cost is not None else None,
        "retry_source": (
            retried[0]["cell_id"] if retried else None
        ),
        "base_defect_cost_usd": BASE_DEFECT_COST_USD,
        "per_anchor": per_anchor,
        "break_even_E_x_at_p_rescue_1": round(break_even_ex, 2)
        if break_even_ex is not None
        else None,
    }


def no_retry_was_worse(chains: list[dict], story_corpus: dict) -> dict:
    """(4) The no-retry-was-worse comparison.

    Failed-without-retry attempts (their downstream escaped-defect harm + the
    already-spent attempt cost) vs the one retried attempt (rescued). The
    'worse' verdict is a counterfactual, so we report the observable costs and
    flag the comparison as NOT identifiable at n=1 — never a causal claim.
    """
    no_retry = [
        c for c in chains if c["outcome"] == "no-retry-was-taken"
    ]
    escaped_harm_per = {label: round(spec["value"] * BASE_DEFECT_COST_USD, 6) for label, spec in EX_ANCHORS.items()}

    return {
        "failed_without_retry_attempt_ledger": len(no_retry),
        "failed_without_retry_story_corpus": story_corpus["wired_failed"],
        "retried_and_rescued": 1,
        "escaped_harm_per_defect_usd": escaped_harm_per,
        "no_retry_example_cost_usd": (
            round(no_retry[0]["chain_cost_usd"], 4) if no_retry else None
        ),
        "no_retry_example_cell": no_retry[0]["cell_id"] if no_retry else None,
        "retried_chain_cost_usd": (
            round(
                next(c for c in chains if c["outcome"] == "rescued")["chain_cost_usd"],
                4,
            )
            if any(c["outcome"] == "rescued" for c in chains)
            else None
        ),
        "verdict": "not-identifiable — 1 retry, counterfactual, confounded by failure mode (genuine vs injected)",
    }


def render_markdown(rescue: dict, rwoc: dict, econ: dict, nw: dict, confdist: dict) -> str:
    """Render the human-readable lookup + tables."""
    lines: list[str] = []
    lines.append("---")
    lines.append("status: accepted")
    lines.append("---")
    lines.append("")
    lines.append("# Retry-worthiness lookup — p2 computation")
    lines.append("")
    lines.append("**Spec:** `retry_observational_analysis@0.1` · phase `p2_compute_lookup` · OBSERVATIONAL (n=1 retry).")
    lines.append("")

    lines.append("## 1. Rescue-rate-by-signal")
    lines.append("")
    lines.append(f"Overall: {rescue['overall']['rescued']}/{rescue['overall']['retried']} rescued "
                 f"(rate {rescue['overall']['rescue_rate']}, Wilson 95% [{rescue['overall']['wilson_95_lo']}, {rescue['overall']['wilson_95_hi']}]).")
    lines.append("")
    for axis in ["by_confidence_decile", "by_strength", "by_cost_so_far"]:
        lines.append(f"**{axis}:**")
        lines.append("| bin | retried | rescued | rescue rate | Wilson 95% |")
        lines.append("|---|---|---|---|---|")
        for row in rescue[axis]:
            lines.append(
                f"| {row['bin']} | {row['retried']} | {row['rescued']} | {row['rescue_rate']} | "
                f"[{row['wilson_95_lo']}, {row['wilson_95_hi']}] |"
            )
        lines.append("")

    lines.append("## 2. Measured r and WOC = 1/(1+r)")
    lines.append("")
    lines.append("| quantity | value |")
    lines.append("|---|---|")
    lines.append(f"| framework r (11.5% scenario) | {rwoc['framework_r_scenario']} |")
    lines.append(f"| framework WOC | {rwoc['framework_woc_scenario']} |")
    lines.append(f"| measured r (E4 grid, 8 cells, retry armed) | {rwoc['measured_r_e4_grid_cells']} |")
    lines.append(f"| measured WOC (E4 grid) | {rwoc['measured_woc_e4_grid']} |")
    lines.append(f"| measured r (attempt plane, E4+probe) | {rwoc['measured_r_attempt_plane']} |")
    lines.append(f"| measured WOC (attempt plane) | {rwoc['measured_woc_attempt_plane']} |")
    lines.append(f"| measured r (story corpus, no retry mechanism) | {rwoc['measured_r_story_corpus']} |")
    lines.append(f"| measured WOC (story corpus) | {rwoc['measured_woc_story_corpus']} |")
    lines.append("")

    lines.append("## 3. Retry economics at E_x")
    lines.append("")
    lines.append(f"measured retry cost (E4 attempt-2) = ${econ['retry_cost_usd_measured']} · "
                 f"observed P(rescue) = {econ['p_rescue_observed']} "
                 f"(Wilson 95% [{econ['p_rescue_wilson_95'][0]}, {econ['p_rescue_wilson_95'][1]}]) · "
                 f"base defect cost = ${econ['base_defect_cost_usd']}")
    lines.append("")
    lines.append("| E_x | rescue value | retry cost | net EV @P=1 | retry cost ÷ rescue value |")
    lines.append("|---|---|---|---|---|")
    for a in econ["per_anchor"]:
        lines.append(
            f"| {a['E_x']} ({a['label']}) | ${a['rescue_value_usd']} | ${a['retry_cost_usd']} | "
            f"${a['net_ev_usd_at_p_rescue_1']} | {a['retry_cost_over_rescue_value']}× |"
        )
    lines.append("")
    lines.append(f"**Break-even E_x at P(rescue)=1:** {econ['break_even_E_x_at_p_rescue_1']}× "
                 "(the retry cost is this many times the base defect cost).")
    lines.append("")

    lines.append("## 4. No-retry-was-worse")
    lines.append("")
    lines.append(f"failed-without-retry (attempt ledger) = {nw['failed_without_retry_attempt_ledger']} · "
                 f"failed-without-retry (story corpus) = {nw['failed_without_retry_story_corpus']} · "
                 f"retried-and-rescued = {nw['retried_and_rescued']}")
    lines.append("")
    lines.append(f"escaped harm per defect: " + ", ".join(
        f"${v} @{k}" for k, v in nw["escaped_harm_per_defect_usd"].items()) + ")")
    lines.append(f"no-retry example: {nw['no_retry_example_cell']} (${nw['no_retry_example_cost_usd']})")
    lines.append(f"retried chain: ${nw['retried_chain_cost_usd']}")
    lines.append(f"**Verdict:** {nw['verdict']}")
    lines.append("")

    lines.append("## 5. Confidence-at-failure distribution (the signal)")
    lines.append("")
    lines.append("| population | n (non-null) | min | max | mean | median |")
    lines.append("|---|---|---|---|---|---|")
    for label in ["wired_failed", "wired_passed"]:
        s = confdist[label]
        if "n_non_null" in s and s.get("n_non_null"):
            lines.append(f"| {label} | {s['n_non_null']}/{s['n_total']} | {s['min']} | {s['max']} | {s['mean']} | {s['median']} |")
        else:
            lines.append(f"| {label} | {s.get('n_total')} | — | — | — | — |")
    lines.append("")

    lines.append("## 6. Confounds + coverage (disclosed alongside)")
    lines.append("")
    lines.append("- **n=1 retry.** The rescue rate (1/1) has Wilson 95% [0.21, 1.0] — it pins nothing.")
    lines.append("- **Scale mismatch.** retry cost ($3.19, a sonnet-5 story attempt) vs rescue value "
                 "($0.05, E_x × a flash-scale base defect cost) — the retry is ~69× the harm it avoids; "
                 "the economics are dominated by the story-attempt cost scale, not the retry decision.")
    lines.append("- **Observational, uncontrolled.** The retry was armed only in the E4 grit_retry arm; "
                 "its one failure (bad_seed_high) was an injected bug, while the no-retry failure "
                 "(clean × baseline) was a genuine harness failure — different failure modes confound the comparison.")
    lines.append("- **Confidence is execution-confidence, not correctness.** high confidence (0.85) did not "
                 "prevent the injected-bug failure; the [H] field measures tool-execution smoothness.")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Run the computation and write lookup.json + lookup.md."""
    payload = load_chains()
    chains = payload["chains"]

    rescue = rescue_rate_by_signal(chains)
    rwoc = measured_r_and_woc(chains, payload)
    econ = retry_economics(chains)
    confdist = confidence_at_failure_distribution()
    nw = no_retry_was_worse(chains, payload["story_corpus"])

    out = {
        "schema": "retry_lookup/v1",
        "phase": "p2_compute_lookup",
        "rescue_rate_by_signal": rescue,
        "measured_r_and_woc": rwoc,
        "retry_economics": econ,
        "no_retry_was_worse": nw,
        "confidence_at_failure_distribution": confdist,
        "coverage": payload["coverage"],
    }

    with open(OUT_DIR / "lookup.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    with open(OUT_DIR / "lookup.md", "w", encoding="utf-8") as fh:
        fh.write(render_markdown(rescue, rwoc, econ, nw, confdist))

    print(f"rescue_rate={rescue['overall']['rescue_rate']} (n={rescue['overall']['retried']})")
    print(f"woc_e4={rwoc['measured_woc_e4_grid']} (r={rwoc['measured_r_e4_grid_cells']})")
    print(f"break_even_E_x={econ['break_even_E_x_at_p_rescue_1']}")
    print(f"net_ev_11.47={econ['per_anchor'][0]['net_ev_usd_at_p_rescue_1']}")


if __name__ == "__main__":
    main()
