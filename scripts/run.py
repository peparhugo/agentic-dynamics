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
    detect_constraints, compute_recovery_cost,
)
from instrument.opencode import run_opencode_agentic


def run_experiment(config_path: str, model_override: str = "", limit: int = 0,
                   timeout: int = 200, repetitions: int = 1,
                   thinking_effort: str = ""):
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
    if model_override:
        model_label = model_override.split("/")[-1].replace(" ", "_").lower()
    else:
        model_label = cfg.get("model", model_id.split("/")[-1]).replace(" ", "_").lower()
    ops = build_operators()

    # Standardized constraints
    std = cfg.get("standardized", {})
    thinking_effort = thinking_effort or std.get("thinking_effort", "") or cfg.get("thinking_effort", "")
    thinking_budget_tokens = std.get("thinking_budget_tokens", 0) or cfg.get("thinking_budget_tokens", 0)
    output_token_limit = std.get("output_token_limit", 0) or cfg.get("output_token_limit", 0)
    standardize = std.get("enabled", True)
    enforce_pytest = std.get("enforce_pytest", True)
    silent_mode = std.get("silent_mode", None)  # None = natural, True = forced-silent, False = forced-verbose

    results_dir = Path("experiments/results")
    results_dir.mkdir(parents=True, exist_ok=True)

    total = 1 + (len(operators) * len(strengths) * repetitions)
    te_str = f" think={thinking_effort}" if thinking_effort else ""
    print(f"\n{'='*80}")
    print(f"Experiment: {name}  |  Model: {model_id}{te_str}")
    print(f"Task: {task[:100]}...")
    print(f"Constraints: {len(constraints)}  |  Operators: {len(operators)} × {len(strengths)} strengths × {repetitions} reps")
    if thinking_budget_tokens:
        print(f"Thinking budget: {thinking_budget_tokens}tok  |  Output limit: {output_token_limit or 'none'}  |  Standardized: {standardize}")
    print(f"Estimated runs: {total}  |  Timeout per run: {timeout}s")
    print(f"{'='*80}\n")

    all_runs = []
    base = _run_baseline(task, constraints, model_id, timeout, name,
                         thinking_effort=thinking_effort,
                         thinking_budget_tokens=thinking_budget_tokens,
                         output_token_limit=output_token_limit,
                         silent_mode=silent_mode,
                         standardize=standardize, enforce_pytest=enforce_pytest)
    all_runs.append(base)

    run_idx = 0
    total_perturbed = len(operators) * len(strengths) * repetitions
    for op_name in operators:
        for s in strengths:
            for rep in range(repetitions):
                run_idx += 1
                r = _run_perturbed(task, constraints, op_name, s, base,
                                   ops, model_id, run_idx, total_perturbed, timeout, name,
                                   thinking_effort=thinking_effort,
                                   thinking_budget_tokens=thinking_budget_tokens,
                                   output_token_limit=output_token_limit,
                                   silent_mode=silent_mode,
                                   standardize=standardize, enforce_pytest=enforce_pytest)
                all_runs.append(r)
                time.sleep(2)

    # Aggregation
    perturbed = [r for r in all_runs if r["type"] == "perturbed"]
    _print_summary(all_runs, name, model_label)
    _save_results(all_runs, name, model_label, results_dir)
    _generate_game_reports(all_runs, name, model_label, constraints, results_dir)

    return all_runs


def _run_baseline(task, constraints, model_id, timeout, exp_name="exp",
                  thinking_effort="", thinking_budget_tokens=0,
                  output_token_limit=0, silent_mode=None,
                  standardize=True, enforce_pytest=True):
    print(f"[baseline] Running...", end=" ", flush=True)
    t0 = time.monotonic()
    r = run_opencode_agentic(task, model=model_id, timeout=timeout,
                             thinking_effort=thinking_effort or None,
                             thinking_budget_tokens=thinking_budget_tokens,
                             output_token_limit=output_token_limit,
                             silent_mode=silent_mode,
                             standardize=standardize, enforce_pytest=enforce_pytest,
                              session_name=f"[baseline] {exp_name}")
    elapsed = time.monotonic() - t0

    sol = evaluate_solution(r.final_response, constraints)
    eff = compute_efficiency(
        prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens,
        reasoning_tokens=r.reasoning_tokens, total_tokens=r.total_tokens,
        solution=sol,
    )
    # Collect code files if workdir available
    code_files = _collect_code(r)
    if code_files:
        # Re-evaluate with code files for richer constraint matching
        sol = evaluate_solution(r.final_response, constraints, code_files=code_files)
    det = detect_constraints(r.final_response, constraints, code_files=code_files)

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
        "workdir": r.workdir,
        "raw_transcript": r.raw_transcript,
    }


def _run_perturbed(task, constraints, op_name, strength, baseline,
                   ops, model_id, run_idx, total, timeout, exp_name="exp",
                   thinking_effort="", thinking_budget_tokens=0,
                   output_token_limit=0, silent_mode=None,
                   standardize=True, enforce_pytest=True):
    pert_class = ops[op_name].perturbation_class if op_name in ops else "?"
    perturbed, _ = perturb_prompt(task, op_name, strength=strength, rng_seed=42 + run_idx)

    print(f"[{run_idx}/{total}] {op_name} s={strength} ({pert_class})...",
          end=" ", flush=True)
    t0 = time.monotonic()
    r = run_opencode_agentic(perturbed, model=model_id, timeout=timeout,
                             thinking_effort=thinking_effort or None,
                             thinking_budget_tokens=thinking_budget_tokens,
                             output_token_limit=output_token_limit,
                             silent_mode=silent_mode,
                             standardize=standardize, enforce_pytest=enforce_pytest,
                              session_name=f"[{op_name}_s{strength}] {exp_name}")
    elapsed = time.monotonic() - t0

    sol = evaluate_solution(r.final_response, constraints,
                            baseline_code=baseline.get("final_response", ""))
    # Override correctness with actual test results if available
    actual_correctness = sol.correctness_score
    if r.tests_total > 0:
        actual_correctness = r.tests_passed / r.tests_total
    # Re-evaluate with code files for richer constraint matching
    code_files = _collect_code(r)
    if code_files:
        sol = evaluate_solution(r.final_response, constraints,
                                baseline_code=baseline.get("final_response", ""),
                                code_files=code_files)
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
        "workdir": r.workdir,
        "raw_transcript": r.raw_transcript,
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
    """Generate individual game reports in markdown with artifacts."""
    import shutil
    import os

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

        # Artifact bundling
        artifact_dir_name = f"{name}_{model_slug}_{op}_s{s}"
        artifact_dir = ""
        has_code = False
        has_session = False
        workdir = r.get("workdir", "")
        transcript = r.get("raw_transcript", "")

        if workdir and os.path.isdir(workdir):
            artifact_path = reports_dir / artifact_dir_name
            code_dest = artifact_path / "code"
            skip = {".git", "__pycache__", ".mypy_cache", ".pytest_cache",
                    "venv", ".venv", "node_modules", ".instrument"}
            file_count = 0
            for item in Path(workdir).rglob("*"):
                if item.is_file() and not (skip & set(item.parts)) \
                        and not item.name.startswith("."):
                    rel = item.relative_to(workdir)
                    dest = code_dest / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy2(item, dest)
                        file_count += 1
                    except Exception:
                        pass

            if file_count > 0:
                has_code = True

            if transcript:
                if not has_code:
                    code_dest.mkdir(parents=True, exist_ok=True)
                (artifact_path / "session.jsonl").write_text(transcript)
                has_session = True

            if has_code or has_session:
                artifact_dir = artifact_dir_name

        game = GameReport(
            experiment_id=f"{name}-{op}",
            model=model_label, task="",
            operator=op, perturbation_class=cls, perturbation_strength=s,
            reasoning=basin,
            artifact_dir=artifact_dir,
            has_code=has_code,
            has_session=has_session,
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


_SOURCE_EXTS = {'.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.rs', '.java', '.rb',
                '.json', '.yaml', '.yml', '.toml', '.proto', '.prisma', '.sql',
                '.css', '.scss', '.html', '.hbs', '.md', '.mjs', '.cjs'}

def _collect_code(result) -> dict[str, str] | None:
    """Collect code file contents from an AgenticResult's workdir."""
    import os, glob
    wd = getattr(result, 'workdir', '')
    if not wd or not os.path.isdir(wd):
        return None
    code = {}
    for root, dirs, files in os.walk(wd):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__'
                    and d != 'node_modules' and d != '.git' and d != 'target']
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in _SOURCE_EXTS and not f.startswith('.'):
                fpath = os.path.join(root, f)
                try:
                    code[os.path.relpath(fpath, wd)] = open(fpath).read()
                except: pass
    return code if code else None


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
