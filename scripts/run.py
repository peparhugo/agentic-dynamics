"""Complete experiment pipeline — opencode agentic backend.

Spawns isolated opencode sessions, captures full tool-call traces,
evaluates solution quality, and produces game reports.

Usage:
    export DEEPSEEK_API_KEY="sk-..."
    python3 scripts/run.py experiments/configs/collaborative_editor.yaml
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument import (
    ExperimentConfig, ExperimentResult, ExperimentRun,
    build_operators, perturb_prompt,
    SolutionMetrics, evaluate_solution,
    EfficiencyMetrics, compute_efficiency,
    StrategyReport, StrategyType, classify_strategy,
    BasinMetrics, measure_basin_escape,
    GameReport,
)
from instrument.opencode import run_opencode_agentic, AgenticResult


def make_opencode_invoke(model_id: str):
    """Build an opencode agentic invoke function."""
    def invoke(prompt, *, model=None, timeout=300):
        effective_model = model or model_id
        result = run_opencode_agentic(prompt, model=effective_model, timeout=timeout)
        # Attach extra attrs for experiment.py compatibility
        result.estimated_cost_usd = result.estimated_cost_usd
        return result
    return invoke


def main():
    import argparse, yaml

    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="YAML experiment config")
    parser.add_argument("--model", help="Model in opencode format (provider/model)")
    parser.add_argument("--limit", type=int, help="Limit operators")
    parser.add_argument("--timeout", type=int, default=300, help="Per-run timeout in seconds")
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    model_id = args.model or cfg.get("model_id", "deepseek/deepseek-v4-pro")
    operators = cfg["operators"][:args.limit] if args.limit else cfg["operators"]
    strengths = cfg["strengths"]
    constraints = cfg.get("constraints", [])
    task = cfg["task"].strip()
    name = cfg["name"]
    repetitions = args.repetitions or cfg.get("repetitions", 1)

    invoke = make_opencode_invoke(model_id)
    ops = build_operators()

    print(f"Experiment: {name}")
    print(f"Model: {model_id}  |  Operators: {len(operators)} × {len(strengths)} strengths × {repetitions} reps")
    print(f"Task: {task[:100]}...")
    print(f"Constraints: {len(constraints)}")
    print()

    # ── Baseline ──
    print("═══ BASELINE ═══")
    bl = invoke(task)
    bl_sol = evaluate_solution(bl.final_response, constraints)
    bl_eff = compute_efficiency(
        prompt_tokens=bl.prompt_tokens, completion_tokens=bl.completion_tokens,
        reasoning_tokens=bl.reasoning_tokens, total_tokens=bl.total_tokens, solution=bl_sol,
    )
    bl_basin = BasinMetrics(escape_score=0.0, correctness=bl_sol.correctness_score,
        constraints_met=bl_sol.constraints_met, total_tokens=bl.total_tokens,
        reasoning_tokens=bl.reasoning_tokens, thinking_ratio=bl_eff.thinking_ratio,
        cost_usd=bl.estimated_cost_usd, estimated_energy_j=bl_eff.total_energy_j,
        lines_of_code=bl_sol.lines_of_code, model=model_id, task=task, run_id="baseline")
    bl_strat = classify_strategy(bl_basin, bl_sol, bl_eff, "baseline")
    print(f"  Correctness: {bl_sol.correctness_score:.0%}  Tokens: {bl.total_tokens:,}  "
          f"Cost: ${bl.estimated_cost_usd:.4f}  Tools: {bl.total_tool_calls}  "
          f"Retries: {bl.retry_loops}  Depth: {bl.iteration_depth}")
    print(f"  Strategy: {bl_strat.strategy.value}")
    print()

    # ── Perturbation runs ──
    runs = []
    total_runs = len(operators) * len(strengths) * repetitions
    idx = 0

    for op_name in operators:
        for s in strengths:
            for rep in range(repetitions):
                idx += 1
                rep_tag = f" rep{rep+1}" if repetitions > 1 else ""
                print(f"[{idx}/{total_runs}] {op_name} s={s}{rep_tag} ", end="", flush=True)
                t0 = time.monotonic()

                op_def = ops.get(op_name)
                pert_class = op_def.perturbation_class if op_def else "semantic"

                # Perturb the prompt
                perturbed, _ = perturb_prompt(task, op_name, strength=s, rng_seed=42 + idx)

                # Run agentic session
                r = invoke(perturbed, timeout=args.timeout)
                elapsed = time.monotonic() - t0

                # Evaluate
                sol = evaluate_solution(r.final_response, constraints, baseline_code=bl.final_response)
                eff = compute_efficiency(
                    prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens,
                    reasoning_tokens=r.reasoning_tokens, total_tokens=r.total_tokens, solution=sol,
                )
                basin = measure_basin_escape(
                    bl.final_response, r.final_response,
                    baseline_correctness=bl_sol.correctness_score,
                    perturbed_correctness=sol.correctness_score,
                    baseline_constraints_met=bl_sol.constraints_met,
                    perturbed_constraints_met=sol.constraints_met,
                    baseline_loc=bl_sol.lines_of_code,
                    perturbed_loc=sol.lines_of_code,
                    prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens,
                    reasoning_tokens=r.reasoning_tokens,
                    perturbation_strength=s, perturbation_operator=op_name,
                    perturbation_class=pert_class, model=model_id, task=task,
                    run_id=f"{op_name}_{s}",
                )
                strat = classify_strategy(basin, sol, eff, pert_class)

                # Game report
                game = GameReport(
                    experiment_id=f"{name}-{op_name}-s{s}",
                    model=model_id, task=task, operator=op_name,
                    perturbation_class=pert_class, perturbation_strength=s,
                    reasoning=basin, solution=sol, efficiency=eff, strategy=strat,
                )

                runs.append({
                    "operator": op_name, "strength": s, "pert_class": pert_class,
                    "correctness": sol.correctness_score,
                    "constraints": f"{sol.constraints_met}/{sol.constraints_total}",
                    "tokens": r.total_tokens,
                    "thinking": eff.thinking_ratio,
                    "cost": r.estimated_cost_usd,
                    "energy": eff.total_energy_j,
                    "tools": r.total_tool_calls,
                    "retries": r.retry_loops,
                    "depth": r.iteration_depth,
                    "escape": basin.escape_score,
                    "strategy": strat.strategy.value,
                    "quality_per_joule": basin.quality_per_joule,
                    "files": len(r.files_created),
                    "duration": elapsed,
                    "game": game,
                })

                icon = "⚠" if strat.strategy == StrategyType.EXPLORATORY else "✓" if sol.correctness_score > 0.7 else "✗"
                print(f"{icon} correct={sol.correctness_score:.0%} tok={r.total_tokens:,} "
                      f"${r.estimated_cost_usd:.4f} think={eff.thinking_ratio:.0%} "
                      f"tools={r.total_tool_calls} retries={r.retry_loops} strat={strat.strategy.value}")

                time.sleep(1)  # rate limit

    # ── Summary ──
    print(f"\n{'='*110}")
    print(f"GAME REPORT — {name}")
    print(f"{'='*110}")
    print(f"{'Operator':<25} {'S':>3} {'Escape':>6} {'Correct':>7} {'Tok':>8} {'Think':>6} {'$':>8} {'Tools':>6} {'Retry':>6} {'Strategy':>13}")
    print('-' * 110)
    for r in runs:
        print(f"{r['operator']:<25} {r['strength']:>3.1f} {r['escape']:>6.3f} {r['correctness']:>7.0%} "
              f"{r['tokens']:>8,} {r['thinking']:>6.0%} {r['cost']:>8.4f} {r['tools']:>6} {r['retries']:>6} {r['strategy']:>13}")

    # Per-class averages
    print(f"\nPer-class averages:")
    by_cls = {"manifold": [], "semantic": []}
    for r in runs:
        by_cls[r["pert_class"]].append(r)
    for cls, items in by_cls.items():
        if items:
            avg_c = sum(r["correctness"] for r in items) / len(items)
            avg_t = sum(r["tokens"] for r in items) / len(items)
            avg_cost = sum(r["cost"] for r in items) / len(items)
            avg_retries = sum(r["retries"] for r in items) / len(items)
            avg_depth = sum(r["depth"] for r in items) / len(items)
            print(f"  {cls:<10} correct={avg_c:.0%} tok={avg_t:.0f} cost=${avg_cost:.4f} "
                  f"retries={avg_retries:.1f} depth={avg_depth:.1f}")

    # Top-line finding
    total_tok = bl.total_tokens + sum(r["tokens"] for r in runs)
    total_cost = bl.estimated_cost_usd + sum(r["cost"] for r in runs)
    print(f"\nTotal: {total_tok:,} tokens, ${total_cost:.4f}, {total_runs} perturbed runs")


if __name__ == "__main__":
    main()
