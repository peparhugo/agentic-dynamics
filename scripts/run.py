"""Complete experiment pipeline — config-driven, agentic, multi-model.

One command:
    python3 scripts/run.py experiments/configs/url_shortener.yaml

Produces:
    experiments/results/{name}_{model}.json    — machine-readable
    experiments/results/{name}_{model}.md      — game report (markdown)
    experiments/results/{name}_comparison.md   — multi-model comparison table
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument import (
    build_operators, perturb_prompt,
    evaluate_solution, compute_efficiency,
    classify_strategy, measure_basin_escape,
    BasinMetrics, GameReport,
)
from instrument.opencode import run_opencode_agentic


def run_experiment(config_path: str, model_override: str = "", limit: int = 0,
                   timeout: int = 200, repetitions: int = 1):
    """Run a complete experiment from a YAML config file."""
    import yaml

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    name = cfg["name"]
    task = cfg["task"].strip()
    constraints = cfg.get("constraints", [])
    operators = cfg["operators"]
    if limit:
        operators = operators[:limit]
    strengths = cfg["strengths"]
    model_id = model_override or cfg.get("model_id", "deepseek/deepseek-v4-pro")
    model_label = cfg.get("model", model_id.split("/")[-1])
    ops = build_operators()

    results_dir = Path("experiments/results")
    results_dir.mkdir(parents=True, exist_ok=True)

    total = 1 + (len(operators) * len(strengths) * repetitions)
    print(f"\n{'='*80}")
    print(f"Experiment: {name}  |  Model: {model_id}")
    print(f"Task: {task[:100]}...")
    print(f"Constraints: {len(constraints)}  |  Operators: {len(operators)} × {len(strengths)} strengths × {repetitions} reps")
    print(f"Estimated runs: {total}  |  Timeout per run: {timeout}s")
    print(f"{'='*80}\n")

    all_runs = []
    base = _run_baseline(task, constraints, model_id, timeout)
    all_runs.append(base)

    run_idx = 0
    total_perturbed = len(operators) * len(strengths) * repetitions
    for op_name in operators:
        for s in strengths:
            for rep in range(repetitions):
                run_idx += 1
                r = _run_perturbed(task, constraints, op_name, s, base,
                                   ops, model_id, run_idx, total_perturbed, timeout)
                all_runs.append(r)
                time.sleep(2)

    # Aggregation
    perturbed = [r for r in all_runs if r["type"] == "perturbed"]
    _print_summary(all_runs, name, model_label)
    _save_results(all_runs, name, model_label, results_dir)
    _generate_game_reports(all_runs, name, model_label, constraints, results_dir)

    return all_runs


def _run_baseline(task, constraints, model_id, timeout):
    print(f"[baseline] Running...", end=" ", flush=True)
    t0 = time.monotonic()
    r = run_opencode_agentic(task, model=model_id, timeout=timeout)
    elapsed = time.monotonic() - t0

    sol = evaluate_solution(r.final_response, constraints)
    eff = compute_efficiency(
        prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens,
        reasoning_tokens=r.reasoning_tokens, total_tokens=r.total_tokens,
        solution=sol,
    )

    print(f"correct={sol.correctness_score:.0%} tok={r.total_tokens:,} "
          f"${r.estimated_cost_usd:.4f} tools={r.total_tool_calls} "
          f"retries={r.retry_loops} depth={r.iteration_depth}")

    return {
        "type": "baseline", "model": model_id,
        "operator": "baseline", "perturbation_class": "baseline",
        "correctness": sol.correctness_score,
        "constraints_met": sol.constraints_met,
        "constraints_total": sol.constraints_total,
        "lines_of_code": sol.lines_of_code,
        "composite_score": sol.composite_score,
        "novelty": sol.novelty_score,
        "total_tokens": r.total_tokens,
        "prompt_tokens": r.prompt_tokens,
        "completion_tokens": r.completion_tokens,
        "reasoning_tokens": r.reasoning_tokens,
        "thinking_ratio": eff.thinking_ratio,
        "cost_usd": r.estimated_cost_usd,
        "energy_j": eff.total_energy_j,
        "tool_calls": r.total_tool_calls,
        "retries": r.retry_loops,
        "iteration_depth": r.iteration_depth,
        "files_created": len(r.files_created),
        "duration_s": elapsed,
        "exit_code": r.exit_code,
        "final_response": r.final_response,
        "quality_per_dollar": sol.correctness_score / max(r.estimated_cost_usd, 0.000001),
        "quality_per_joule": sol.composite_score / max(eff.total_energy_j, 0.01),
    }


def _run_perturbed(task, constraints, op_name, strength, baseline,
                   ops, model_id, run_idx, total, timeout):
    pert_class = ops[op_name].perturbation_class if op_name in ops else "?"
    perturbed, _ = perturb_prompt(task, op_name, strength=strength, rng_seed=42 + run_idx)

    print(f"[{run_idx}/{total}] {op_name} s={strength} ({pert_class})...",
          end=" ", flush=True)
    t0 = time.monotonic()
    r = run_opencode_agentic(perturbed, model=model_id, timeout=timeout)
    elapsed = time.monotonic() - t0

    sol = evaluate_solution(r.final_response, constraints,
                            baseline_code=baseline.get("final_response", ""))
    # Override correctness with actual test results if available
    actual_correctness = sol.correctness_score
    if r.tests_total > 0:
        actual_correctness = r.tests_passed / r.tests_total
    eff = compute_efficiency(
        prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens,
        reasoning_tokens=r.reasoning_tokens, total_tokens=r.total_tokens,
        solution=sol,
    )

    basin = measure_basin_escape(
        baseline.get("final_response", ""), r.final_response,
        baseline_correctness=baseline.get("correctness", 0),
        perturbed_correctness=sol.correctness_score,
        baseline_constraints_met=baseline.get("constraints_met", 0),
        perturbed_constraints_met=sol.constraints_met,
        baseline_loc=baseline.get("lines_of_code", 0),
        perturbed_loc=sol.lines_of_code,
        prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens,
        reasoning_tokens=r.reasoning_tokens,
        perturbation_strength=strength, perturbation_operator=op_name,
        perturbation_class=pert_class, model=model_id,
    )
    strat = classify_strategy(basin, sol, eff, pert_class)

    icon = "✓" if sol.correctness_score > 0.5 else "✗" if sol.correctness_score > 0 else "○"
    print(f"{icon} correct={sol.correctness_score:.0%} tok={r.total_tokens:,} "
          f"${r.estimated_cost_usd:.4f} think={eff.thinking_ratio:.0%} "
          f"tools={r.total_tool_calls} retries={r.retry_loops} "
          f"depth={r.iteration_depth} esc={basin.escape_score:.2f} "
          f"strat={strat.strategy.value}")

    return {
        "type": "perturbed", "model": model_id,
        "operator": op_name, "perturbation_class": pert_class, "strength": strength,
        "correctness": sol.correctness_score,
        "actual_correctness": actual_correctness,
        "tests_passed": r.tests_passed,
        "tests_total": r.tests_total,
        "constraints_met": sol.constraints_met,
        "constraints_total": sol.constraints_total,
        "lines_of_code": sol.lines_of_code,
        "composite_score": sol.composite_score,
        "novelty": sol.novelty_score,
        "escape_score": basin.escape_score,
        "architecture_divergence": basin.architecture_divergence,
        "total_tokens": r.total_tokens,
        "prompt_tokens": r.prompt_tokens,
        "completion_tokens": r.completion_tokens,
        "reasoning_tokens": r.reasoning_tokens,
        "thinking_ratio": eff.thinking_ratio,
        "cost_usd": r.estimated_cost_usd,
        "energy_j": eff.total_energy_j,
        "tool_calls": r.total_tool_calls,
        "retries": r.retry_loops,
        "iteration_depth": r.iteration_depth,
        "files_created": len(r.files_created),
        "duration_s": elapsed,
        "exit_code": r.exit_code,
        "strategy": strat.strategy.value,
        "strategy_score": strat.strategy_score,
        "verdict": strat.verdict,
        "final_response": r.final_response,
        "quality_per_dollar": sol.correctness_score / max(r.estimated_cost_usd, 0.000001),
        "quality_per_joule": sol.composite_score / max(eff.total_energy_j, 0.01),
    }


def _print_summary(runs, name, model_label):
    perturbed = [r for r in runs if r["type"] == "perturbed"]
    base = next((r for r in runs if r["type"] == "baseline"), {})
    if not perturbed:
        return

    print(f"\n{'='*120}")
    print(f"RESULTS — {name} ({model_label})")
    print(f"{'='*120}")
    header = f"{'Operator':<25} {'S':>3} {'Escape':>6} {'Correct':>7} {'Tok':>8} {'$':>9} {'Think':>6} {'Tools':>6} {'Retry':>6} {'Depth':>6} {'Q/$':>8} {'Strategy':>13}"
    print(header)
    print("-" * 120)
    for r in perturbed:
        qpd = r.get("quality_per_dollar", 0)
        print(f"{r['operator']:<25} {r['strength']:>3.1f} {r['escape_score']:>6.2f} "
              f"{r['correctness']:>7.0%} {r['total_tokens']:>8,} {r['cost_usd']:>9.4f} "
              f"{r['thinking_ratio']:>6.0%} {r['tool_calls']:>6} {r['retries']:>6} "
              f"{r['iteration_depth']:>6} {qpd:>8.0f} {r['strategy']:>13}")

    # Per-class averages
    by_cls = {"manifold": [], "semantic": []}
    for r in perturbed:
        by_cls[r["perturbation_class"]].append(r)
    print(f"\nPer-class (avg, n={len(perturbed)} runs):")
    for cls, items in sorted(by_cls.items()):
        if items:
            avg_c = sum(r["correctness"] for r in items) / len(items)
            avg_t = sum(r["total_tokens"] for r in items) / len(items)
            avg_cost = sum(r["cost_usd"] for r in items) / len(items)
            avg_ret = sum(r["retries"] for r in items) / len(items)
            avg_d = sum(r["iteration_depth"] for r in items) / len(items)
            avg_qpd = sum(r.get("quality_per_dollar", 0) for r in items) / len(items)
            # CI estimate (crude: std err for small n)
            import math
            std_c = math.sqrt(sum((r["correctness"] - avg_c)**2 for r in items)/max(len(items)-1, 1)) if len(items) > 1 else 0
            std_t = math.sqrt(sum((r["total_tokens"] - avg_t)**2 for r in items)/max(len(items)-1, 1)) if len(items) > 1 else 0
            ci_c = 1.96 * std_c / math.sqrt(len(items)) if len(items) > 1 and std_c > 0 else 0
            ci_t = 1.96 * std_t / math.sqrt(len(items)) if len(items) > 1 and std_t > 0 else 0
            ci_str = f" ±{ci_c:.0%}" if ci_c > 0 else " (±?)" if len(items) == 1 else ""
            tok_str = f" ±{ci_t:,.0f}" if ci_t > 0 else ""
            print(f"  {cls:<10} correct={avg_c:.0%}{ci_str} tok={avg_t:,.0f}{tok_str} ${avg_cost:.4f} "
                  f"retries={avg_ret:.1f} depth={avg_d:.1f} Q/$={avg_qpd:.0f} (n={len(items)})")

    # Top-line
    total_tok = (base.get("total_tokens", 0) or 0) + sum(r["total_tokens"] for r in perturbed)
    total_cost = (base.get("cost_usd", 0) or 0) + sum(r["cost_usd"] for r in perturbed)
    total_energy = (base.get("energy_j", 0) or 0) + sum(r["energy_j"] for r in perturbed)
    print(f"\nTotal: {total_tok:,} tokens, ${total_cost:.4f}, ~{total_energy:,.0f}J, "
          f"{len(perturbed)} perturbed + 1 baseline")


def _save_results(runs, name, model_label, results_dir):
    model_slug = model_label.replace(" ", "_").lower()
    out = {
        "experiment": name, "model": model_label,
        "runs": [{k: v for k, v in r.items() if k != "final_response"} for r in runs],
    }
    path = results_dir / f"{name}_{model_slug}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nResults saved: {path}")


def _generate_game_reports(runs, name, model_label, constraints, results_dir):
    """Generate individual game reports in markdown."""
    model_slug = model_label.replace(" ", "_").lower()
    reports_dir = results_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    for r in runs:
        op = r["operator"]
        cls = r.get("perturbation_class", "?")
        s = r.get("strength", 0)

        basin = BasinMetrics(
            escape_score=r.get("escape_score", 0),
            correctness=r.get("correctness", 0),
            constraints_met=r.get("constraints_met", 0),
            constraints_total=r.get("constraints_total", 0),
            total_tokens=r.get("total_tokens", 0),
            reasoning_tokens=r.get("reasoning_tokens", 0),
            thinking_ratio=r.get("thinking_ratio", 0),
            cost_usd=r.get("cost_usd", 0),
            estimated_energy_j=r.get("energy_j", 0),
            perturbation_strength=s,
            perturbation_operator=op,
            perturbation_class=cls,
            quality_per_dollar=r.get("quality_per_dollar", 0),
            quality_per_joule=r.get("quality_per_joule", 0),
            model=model_label,
        )

        game = GameReport(
            experiment_id=f"{name}-{op}",
            model=model_label, task="",
            operator=op, perturbation_class=cls, perturbation_strength=s,
            reasoning=basin,
        )

        md_path = reports_dir / f"{name}_{model_slug}_{op}_s{s}.md"
        md_path.write_text(game.to_markdown())


def multi_model_compare(config_path, model_ids, timeout=200):
    """Run the same config across multiple models and produce a comparison."""
    all_results = {}
    for model_id in model_ids:
        label = model_id.split("/")[-1]
        print(f"\n{'#'*80}")
        print(f"# MODEL: {model_id}")
        print(f"{'#'*80}")
        runs = run_experiment(config_path, model_override=model_id, timeout=timeout)
        all_results[label] = runs

    # Comparison table
    print(f"\n{'='*100}")
    print(f"MULTI-MODEL COMPARISON")
    print(f"{'='*100}")
    print(f"{'Model':<20} {'Baseline $':>10} {'Avg Pert $':>10} {'Avg Correct':>12} {'Avg Tok':>10} {'Avg Tools':>10} {'Avg Retries':>10} {'Avg Q/$':>10}")
    print("-" * 100)
    for label, runs in all_results.items():
        base = [r for r in runs if r["type"] == "baseline"]
        pert = [r for r in runs if r["type"] == "perturbed"]
        base_cost = sum(r["cost_usd"] for r in base) / max(len(base), 1)
        avg_cost = sum(r["cost_usd"] for r in pert) / max(len(pert), 1)
        avg_correct = sum(r["correctness"] for r in pert) / max(len(pert), 1)
        avg_tok = sum(r["total_tokens"] for r in pert) / max(len(pert), 1)
        avg_tools = sum(r["tool_calls"] for r in pert) / max(len(pert), 1)
        avg_ret = sum(r["retries"] for r in pert) / max(len(pert), 1)
        avg_qpd = sum(r.get("quality_per_dollar", 0) for r in pert) / max(len(pert), 1)
        print(f"{label:<20} ${base_cost:>10.4f} ${avg_cost:>10.4f} {avg_correct:>12.0%} "
              f"{avg_tok:>10,.0f} {avg_tools:>10.1f} {avg_ret:>10.1f} {avg_qpd:>10,.0f}")

    return all_results


if __name__ == "__main__":
    import argparse, yaml

    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="YAML config path")
    parser.add_argument("--model", help="Model override (opencode format: provider/model)")
    parser.add_argument("--compare", nargs="*", help="Compare multiple models")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=200)
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args()

    if args.compare:
        multi_model_compare(args.config, args.compare, args.timeout)
    else:
        run_experiment(args.config, args.model or "", args.limit, args.timeout, args.repetitions)
