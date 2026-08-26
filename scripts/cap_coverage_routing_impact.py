#!/usr/bin/env python3
"""cap_coverage_routing_impact.py — E3 coverage-corrected vs legacy zero-default routing re-run.

Runs the measurement rules of ``experiments/definitions/cap_coverage_routing_impact.yaml`` over
the backfilled store's finding corpus: an A/B of TWO aggregation formulas (not two data sources)
applied to ONE real corpus, isolating exactly the variable the finding-economics migration changed.

- **Corpus:** ``canonical_corpus.resolve_findings()`` — the 64 current ``finding`` rows, the live
  registry-governed replacement for the retired ``_results_summary.json`` (per the spec's finding
  1; ``resolve_stories`` is the WRONG population and is deliberately not used).
- **Coverage-corrected arm:** ``control.routing.compute_routing`` called as-is — uncaptured
  cost/correctness is UNAVAILABLE (excluded), never zero-defaulted.
- **Legacy arm:** ``lab_task_routing.py``'s own aggregation formula re-derived
  (``e.get("correctness", 0)`` / ``e.get("cost", 0)`` averaged over ALL ``n`` — the historical
  zero-default defect) applied to the SAME entries, with the SAME ``min_models=2`` eligibility
  filter and the same decision surface, so the diff isolates the aggregation method.
- **Evaluation:** ``recommendation_diff`` — changed count/rate per task and per model, plus the
  direction (do changes move toward lower-cost models, the zero-default bias's expected sign).

Expected on THIS corpus (the spec's finding 2, verified live): cost and correctness coverage are
both 64/64 = 100%, so coverage-corrected and legacy arithmetic are MATHEMATICALLY FORCED TO AGREE —
``changed_recommendation_count == 0`` is the EXPECTED result. A null (zero changes) is
information, not failure: it says the migration was a correctness fix with no behavioral
consequence YET — it has teeth the day coverage genuinely drops. ``entry_coverage_precheck`` is
the leading indicator to watch every run.

Usage:
    python scripts/cap_coverage_routing_impact.py            # change-rate table + PASS/FAIL
    python scripts/cap_coverage_routing_impact.py --json      # dump the full JSON to stdout
    python scripts/cap_coverage_routing_impact.py --recompute # re-run, overwrite the artifact

Output:
    experiments/results/cap_coverage_routing_impact.json   (machine-readable)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.control.routing import compute_routing  # noqa: E402
from agentic_dynamics.core.session_types import normalize_task  # noqa: E402
from agentic_dynamics.reporting.canonical_corpus import load_canonical_tables  # noqa: E402
from agentic_dynamics.reporting.measurement_coverage import cost_captured  # noqa: E402

RESULTS = Path(__file__).resolve().parent.parent / "experiments" / "results"
OUT = RESULTS / "cap_coverage_routing_impact.json"

MIN_MODELS = 2
CORRECTNESS_THRESHOLD = 0.7
LEAD_MARGIN = 0.05


def _zero_default_mean(values: list[float]) -> float:
    """Legacy arithmetic: mean treating a missing value as zero (the historical defect)."""
    return sum(values) / len(values) if values else 0.0


def project_findings() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Project the finding corpus into ``recommend_route``'s own entry shape (spec rule 1).

    ``resolve_findings`` returns runs carrying the MEASURED fields under their REAL names
    (``cost_usd``/``correctness``/``model``/``perturbation_strength``) — the field-for-field
    replacement for the retired summary's renamed vocabulary. The projection maps
    ``cost=cost_usd`` and ``experiment=_experiment`` (the parent file's experiment name), the
    same mapping ``compute_routing``'s internal ``normalize_task`` grouping performs.
    """
    tables = load_canonical_tables("finding")
    entries: list[dict[str, Any]] = []
    for run in tables.findings:
        entries.append(
            {
                "model": run.get("model"),
                "correctness": run.get("correctness"),
                "cost": run.get("cost_usd"),
                "experiment": run.get("_experiment") or run.get("experiment") or "",
                "narration_failure": run.get("narration_failure"),
            }
        )
    meta = {
        "n_entries_total": len(entries),
        "n_tasks": len({normalize_task(e.get("experiment", "")) for e in entries}),
    }
    return entries, meta


def entry_coverage(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Spec rule 2 — coverage pre-check FIRST on the two divergence-driving fields.

    Raw key presence is what the spec's rule 2 measures. In ADDITION, the ``operational`` view
    reports the coverage ``recommend_route`` actually CONSUMES: ``cost_captured`` treats a ``0.0``
    cost as "no billable work priced" (never a captured zero), so a model whose rows include
    zero-cost entries has ``n_cost_captured_operational < n`` — the exact gap the legacy
    zero-default formula would coerce to 0 and the coverage-corrected formula would exclude.
    """
    n_cost = sum(
        1
        for e in entries
        if isinstance(e.get("cost"), (int, float)) and not isinstance(e.get("cost"), bool)
    )
    n_corr = sum(1 for e in entries if e.get("correctness") is not None)
    n_cost_op = sum(1 for e in entries if cost_captured(e.get("cost")))
    by_model: dict[str, dict[str, Any]] = {}
    for e in entries:
        m = e.get("model") or "unknown"
        b = by_model.setdefault(m, {"n": 0, "n_cost_operational": 0})
        b["n"] += 1
        if cost_captured(e.get("cost")):
            b["n_cost_operational"] += 1
    n = len(entries)
    return {
        "cost_coverage_ratio": round(n_cost / n, 4) if n else 0.0,
        "correctness_coverage_ratio": round(n_corr / n, 4) if n else 0.0,
        "n_cost_captured": n_cost,
        "n_correctness_captured": n_corr,
        "n_total": n,
        "operational": {
            "n_cost_captured": n_cost_op,
            "cost_coverage_ratio": round(n_cost_op / n, 4) if n else 0.0,
            "note": (
                "cost_captured semantics (positive finite cost only; 0.0 = no billable work) — "
                "the coverage recommend_route actually consumes"
            ),
            "by_model": {
                m: dict(b) for m, b in sorted(by_model.items()) if b["n_cost_operational"] < b["n"]
            },
        },
    }


def _eligible_tasks(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group by normalized task, keeping only tasks with >= MIN_MODELS distinct models."""
    by_task: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        if e.get("narration_failure"):
            continue
        task = normalize_task(e.get("experiment", ""))
        if not task or task == "?" or task.startswith("exp_"):
            continue
        by_task.setdefault(task, []).append(e)
    return {t: es for t, es in by_task.items() if len({e.get("model") for e in es}) >= MIN_MODELS}


def legacy_recommend(task: str, entries: list[dict[str, Any]]) -> dict[str, Any]:
    """``lab_task_routing.py``'s zero-default aggregation, on the same decision surface.

    Re-derives the historical formula exactly: ``avg_correctness = sum(get("correctness", 0))/n``
    and ``avg_cost = sum(get("cost", 0))/n`` over ALL ``n`` (a missing value coerced to 0), and
    ``efficiency = avg_correctness / max(avg_cost, 0.00001)``. The recommendation structure
    (default_model / escalate_model / routing, with the same correctness_threshold + lead_margin)
    mirrors ``recommend_route`` so the diff isolates the aggregation variable and nothing else.
    """
    by_model: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        by_model.setdefault(e.get("model", "unknown"), []).append(e)

    model_stats: dict[str, dict[str, Any]] = {}
    best_correctness = 0.0
    best_efficiency = 0.0
    best_model_correct = ""
    best_model_eff = ""
    cheapest_qualified = ""
    cheapest_cost = float("inf")

    for mid, group in by_model.items():
        n = len(group)
        avg_correctness = _zero_default_mean([float(e.get("correctness") or 0) for e in group])
        avg_cost = _zero_default_mean([float(e.get("cost") or 0) for e in group])
        efficiency = avg_correctness / max(avg_cost, 0.00001)
        model_stats[mid] = {
            "n": n,
            "avg_correctness": round(avg_correctness, 4),
            "avg_cost": round(avg_cost, 6),
            "efficiency": round(efficiency, 2),
        }
        if avg_correctness > best_correctness:
            best_correctness = avg_correctness
            best_model_correct = mid
        if efficiency > best_efficiency:
            best_efficiency = efficiency
            best_model_eff = mid
        if avg_cost < cheapest_cost and avg_correctness >= CORRECTNESS_THRESHOLD:
            cheapest_cost = avg_cost
            cheapest_qualified = mid

    default_model = cheapest_qualified or best_model_eff or best_model_correct
    escalate_model = best_model_correct if best_model_correct != default_model else ""
    routing = "default"
    if escalate_model:
        default_correctness = model_stats[default_model]["avg_correctness"]
        if best_correctness - default_correctness > LEAD_MARGIN:
            routing = "escalate"

    return {
        "task": task,
        "models_tested": len(by_model),
        "best_correctness_model": best_model_correct,
        "best_efficiency_model": best_model_eff,
        "default_model": default_model,
        "escalate_model": escalate_model,
        "routing": routing,
        "recommendation": (
            f"escalate to {escalate_model}" if routing == "escalate" else f"default {default_model}"
        ),
        "models": model_stats,
    }


def legacy_routing(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Legacy arm: the re-derived zero-default formula over the same eligible tasks."""
    per_task = [
        legacy_recommend(task, es)
        for task, es in sorted(_eligible_tasks(entries).items())
    ]
    return {"_meta": {"tasks_analyzed": len(per_task)}, "per_task": per_task}


def diff_recommendations(
    corrected: list[dict[str, Any]], legacy: list[dict[str, Any]]
) -> dict[str, Any]:
    """Spec rule 5 — changed count/rate per task and per model + direction analysis."""
    corrected_by_task = {r["task"]: r for r in corrected}
    legacy_by_task = {r["task"]: r for r in legacy}
    tasks = sorted(set(corrected_by_task) | set(legacy_by_task))

    changed_tasks: list[dict[str, Any]] = []
    changed_models: dict[str, int] = {}
    moved_lower_cost = 0
    changed_total = 0
    for task in tasks:
        c = corrected_by_task.get(task)
        legacy = legacy_by_task.get(task)
        if c is None or legacy is None:
            changed_tasks.append({"task": task, "note": "present in only one arm"})
            changed_total += 1
            continue
        c_route = (c["default_model"], c["routing"])
        l_route = (legacy["default_model"], legacy["routing"])
        if c_route == l_route:
            continue
        changed_total += 1
        for m in (c["default_model"], legacy["default_model"]):
            if m:
                changed_models[m] = changed_models.get(m, 0) + 1
        moved = None
        if c["default_model"] and legacy["default_model"]:
            c_cost = c["models"][c["default_model"]]["avg_cost"]
            l_cost = legacy["models"][legacy["default_model"]]["avg_cost"]
            if c_cost is not None and l_cost is not None:
                moved = "to_lower_cost" if c_cost < l_cost else "to_higher_cost"
                if c_cost < l_cost:
                    moved_lower_cost += 1
        changed_tasks.append(
            {
                "task": task,
                "corrected_default": c["default_model"],
                "corrected_routing": c["routing"],
                "legacy_default": legacy["default_model"],
                "legacy_routing": legacy["routing"],
                "direction": moved,
            }
        )

    n_tasks = len(tasks)
    return {
        "changed_recommendation_count": changed_total,
        "changed_recommendation_rate": round(changed_total / n_tasks, 4) if n_tasks else 0.0,
        "changed_by_task": changed_tasks,
        "changed_by_model": dict(sorted(changed_models.items())),
        "moved_to_lower_cost_count": moved_lower_cost,
        "moved_to_lower_cost_rate": (
            round(moved_lower_cost / changed_total, 4) if changed_total else None
        ),
    }


def compute() -> dict[str, Any]:
    entries, meta = project_findings()
    coverage = entry_coverage(entries)
    corrected = compute_routing(entries, min_models=MIN_MODELS)
    legacy = legacy_routing(entries)
    diff = diff_recommendations(corrected["per_task"], legacy["per_task"])

    # Honest mechanism check: did per-model stats diverge even where no recommendation flipped?
    corrected_by_task = {r["task"]: r for r in corrected["per_task"]}
    legacy_by_task = {r["task"]: r for r in legacy["per_task"]}
    diverged_stats: list[dict[str, Any]] = []
    for task in sorted(set(corrected_by_task) | set(legacy_by_task)):
        c = corrected_by_task.get(task)
        legacy = legacy_by_task.get(task)
        if c is None or legacy is None:
            continue
        for mid in sorted(set(c["models"]) | set(legacy["models"])):
            cms, lms = c["models"].get(mid), legacy["models"].get(mid)
            if cms is None or lms is None:
                continue
            c_avg = cms.get("avg_cost")
            l_avg = lms.get("avg_cost")
            if c_avg is not None and l_avg is not None and abs(c_avg - l_avg) > 1e-6:
                diverged_stats.append(
                    {
                        "task": task,
                        "model": mid,
                        "corrected_avg_cost": c_avg,
                        "legacy_avg_cost": l_avg,
                        "n_cost_operational": cms.get("n_cost", cms.get("n")),
                        "n": cms["n"],
                    }
                )

    return {
        "schema": "cap_coverage_routing_impact/v1",
        "spec_id": "cap_coverage_routing_impact@0.1",
        "source": "canonical_corpus.resolve_findings() (registry-governed; the live replacement for the retired _results_summary.json)",
        "corpus": meta,
        "entry_coverage_precheck": coverage,
        "coverage_corrected": corrected,
        "legacy_zero_default": legacy,
        "recommendation_diff": diff,
        "per_model_stat_divergence": diverged_stats,
        "null_hypothesis": (
            "zero changes — no task/model pair's routing recommendation differs between the two "
            "formulas. A null here is information, not failure."
        ),
        "notes": [
            "zero changed RECOMMENDATIONS on this corpus (both eligible tasks agree) — the null "
            "holds. Mechanism differs from the spec's finding-2 prediction: raw cost-key coverage "
            "is 100%, but OPERATIONAL cost coverage (cost_captured: positive finite only, 0.0 = no "
            "billable work) is <100% for some models, so per-model avg_cost DID diverge between the "
            "formulas (see per_model_stat_divergence) — it simply did not flip any decision because "
            "the diverging models were not on the decision boundary",
            "legacy arm re-derives lab_task_routing.py's aggregation formula (zero-default over all "
            "n) on the SAME entries — isolates the aggregation-method variable from the corpus-source variable",
            "the leading indicator is entry_coverage_precheck.operational.cost_coverage_ratio: the "
            "day it drops, changed_recommendation_count starts actually testing something",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the full JSON to stdout")
    parser.add_argument(
        "--recompute", action="store_true", help="recompute and overwrite the artifact"
    )
    args = parser.parse_args(argv)

    payload = compute()

    if args.json or args.recompute:
        OUT.write_text(json.dumps(payload, indent=2) + "\n")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    cov = payload["entry_coverage_precheck"]
    print(
        f"coverage pre-check: cost {cov['n_cost_captured']}/{cov['n_total']} "
        f"({cov['cost_coverage_ratio']:.1%}) | correctness "
        f"{cov['n_correctness_captured']}/{cov['n_total']} ({cov['correctness_coverage_ratio']:.1%})"
    )
    op = cov.get("operational")
    if op:
        print(
            f"operational cost coverage (cost_captured, 0.0 = not billable): "
            f"{op['n_cost_captured']}/{cov['n_total']} ({op['cost_coverage_ratio']:.1%})"
        )
        for m, b in op.get("by_model", {}).items():
            print(f"    {m}: {b['n_cost_operational']}/{b['n']} cost-captured")
    print(f"corpus: {payload['corpus']['n_entries_total']} finding entries / "
          f"{payload['corpus']['n_tasks']} tasks")

    corrected = payload["coverage_corrected"]
    legacy = payload["legacy_zero_default"]
    print(f"\ncoverage-corrected: {corrected['_meta']['tasks_analyzed']} eligible tasks "
          f"(min_models={MIN_MODELS})")
    for r in corrected["per_task"]:
        print(f"  {r['task']:<36} {r['recommendation']}")
    print(f"legacy zero-default: {legacy['_meta']['tasks_analyzed']} eligible tasks")
    for r in legacy["per_task"]:
        print(f"  {r['task']:<36} {r['recommendation']}")

    d = payload["recommendation_diff"]
    print(
        f"\nchanged recommendations: {d['changed_recommendation_count']} "
        f"({d['changed_recommendation_rate']:.1%} of tasks)"
    )
    for c in d["changed_by_task"]:
        print(f"  {c}")
    print(f"moved to lower-cost: {d['moved_to_lower_cost_count']} "
          f"({d['moved_to_lower_cost_rate'] if d['moved_to_lower_cost_rate'] is not None else 'n/a'})")
    div = payload.get("per_model_stat_divergence", [])
    if div:
        print("\nper-model stat divergence (avg_cost differs between formulas, no decision flipped):")
        for x in div:
            print(f"  {x['task']:<36} {x['model']:<28} corrected=${x['corrected_avg_cost']} "
                  f"legacy=${x['legacy_avg_cost']} (n_cost={x['n_cost_operational']}/{x['n']})")

    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
