"""Task-optimal routing — recommend a model per task type from experiment results.

Generalized, provider-agnostic version of the routing logic originally in
``scripts/lab_task_routing.py``. Consumes experiment entries (e.g. from
``_results_summary.json``), groups by normalized task, and produces per-task
routing recommendations plus aggregate strategy simulations.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .session_types import normalize_task


def recommend_route(
    task_type: str,
    entries: list[dict[str, Any]],
    *,
    correctness_threshold: float = 0.7,
    lead_margin: float = 0.05,
) -> dict[str, Any]:
    """Recommend a route (default vs escalate) for one task type.

    Args:
        task_type: normalized task name.
        entries: experiment entries for this task, each carrying at least
            ``model``, ``correctness``, and ``cost``.
        correctness_threshold: minimum correctness for a model to be eligible
            as the cheap default.
        lead_margin: correctness delta above which a higher-correctness model
            becomes the escalate target.

    Returns:
        Recommendation dict with per-model stats and a routing decision.
    """
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in entries:
        by_model[e.get("model", "unknown")].append(e)

    model_stats: dict[str, dict[str, Any]] = {}
    best_correctness = 0.0
    best_efficiency = 0.0
    best_model_correct = ""
    best_model_eff = ""
    cheapest_qualified = ""
    cheapest_cost = float("inf")

    for mid, group in by_model.items():
        n = len(group)
        avg_correctness = sum(e.get("correctness", 0) for e in group) / n
        avg_cost = sum(e.get("cost", 0) for e in group) / n
        efficiency = avg_correctness / max(avg_cost, 1e-6)
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
        if avg_cost < cheapest_cost and avg_correctness >= correctness_threshold:
            cheapest_cost = avg_cost
            cheapest_qualified = mid

    default_model = cheapest_qualified or best_model_eff or best_model_correct
    escalate_model = best_model_correct if best_model_correct != default_model else ""
    routing = "default"
    if escalate_model and default_model in model_stats:
        default_correctness = model_stats[default_model]["avg_correctness"]
        if best_correctness - default_correctness > lead_margin:
            routing = "escalate"

    return {
        "task": task_type,
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


def simulate_strategies(
    entries: list[dict[str, Any]],
    per_task: list[dict[str, Any]],
    by_task: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Simulate single-model and grit-routed strategies across the corpus."""
    models = sorted({e.get("model", "unknown") for e in entries})
    strategies: dict[str, Any] = {}

    for mid in models:
        subset = [e for e in entries if e.get("model") == mid]
        n = len(subset)
        total_cost = sum(e.get("cost", 0) for e in subset)
        avg_correctness = sum(e.get("correctness", 0) for e in subset) / max(n, 1)
        strategies[f"{mid}_only"] = {
            "n": n,
            "total_cost": round(total_cost, 6),
            "avg_cost": round(total_cost / max(n, 1), 6),
            "avg_correctness": round(avg_correctness, 4),
        }

    routed_cost = 0.0
    routed_correctness_sum = 0.0
    routed_n = 0
    distribution: dict[str, int] = defaultdict(int)
    for rec in per_task:
        model = rec["escalate_model"] if rec["routing"] == "escalate" else rec["default_model"]
        if not model:
            continue
        subset = [e for e in by_task.get(rec["task"], []) if e.get("model") == model]
        routed_cost += sum(e.get("cost", 0) for e in subset)
        routed_correctness_sum += sum(e.get("correctness", 0) for e in subset)
        routed_n += len(subset)
        distribution[model] += len(subset)

    strategies["grit_routed"] = {
        "n": routed_n,
        "total_cost": round(routed_cost, 6),
        "avg_cost": round(routed_cost / max(routed_n, 1), 6),
        "avg_correctness": round(routed_correctness_sum / max(routed_n, 1), 4),
        "routing_distribution": dict(distribution),
    }
    return strategies


def compute_routing(entries: list[dict[str, Any]], *, min_models: int = 2) -> dict[str, Any]:
    """Compute the full routing report from experiment entries.

    Args:
        entries: experiment entries (each with model, correctness, cost,
            experiment name).
        min_models: minimum number of distinct models required for a task to
            be considered.

    Returns:
        dict with ``_meta``, ``per_task`` recommendations, ``strategies``,
        and ``routing_distribution``.
    """
    valid = [e for e in entries if not e.get("narration_failure") and e.get("correctness", 0) >= 0]

    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in valid:
        task = normalize_task(e.get("experiment", ""))
        by_task[task].append(e)

    per_task = []
    for task in sorted(by_task):
        if not task or task == "?" or task.startswith("exp_"):
            continue
        task_entries = by_task[task]
        models_in_task = {e.get("model", "unknown") for e in task_entries}
        if len(models_in_task) < min_models:
            continue
        per_task.append(recommend_route(task, task_entries))

    strategies = simulate_strategies(valid, per_task, by_task)

    rec_counts: dict[str, int] = defaultdict(int)
    for rec in per_task:
        rec_counts[rec["routing"]] += 1

    return {
        "_meta": {
            "tasks_analyzed": len(per_task),
            "total_valid_entries": len(valid),
        },
        "per_task": sorted(per_task, key=lambda x: x["task"]),
        "strategies": strategies,
        "routing_distribution": dict(rec_counts),
    }
