"""Silent mode sweep — measures natural vs forced-silent cost gap across models.

This is the key experiment for decomposing the Explanation Tax:
  Natural cost = Architecture × Verbosity × (1 + Explanation Tax)
  Forced cost   = Architecture × Verbosity (tax removed)
  Therefore: Explanation Tax = (Natural cost / Forced cost) - 1

Usage:
  python3 scripts/sweep_silent_mode.py              # run all
  python3 scripts/sweep_silent_mode.py --dry-run    # show plan
  python3 scripts/sweep_silent_mode.py --limit 1    # run 1 model
"""

import contextlib
import hashlib
import json
import os
import time
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


OPENSCODE_DB = Path.home() / ".local/share/opencode/opencode.db"

from agentic_dynamics.adapters.opencode import run_opencode_agentic
from agentic_dynamics.control.model_policy import ensure_model_allowed
from agentic_dynamics.measurement.constraint_detection import detect_constraints
from agentic_dynamics.measurement.efficiency import compute_efficiency
from agentic_dynamics.measurement.perturb import build_operators, derive_seed, perturb_prompt
from agentic_dynamics.measurement.recovery_cost import compute_recovery_cost
from agentic_dynamics.measurement.semantic_validation import analyze_markers
from agentic_dynamics.measurement.solution import evaluate_solution

# Core models for the sweep
DEFAULT_MODELS = [
    ("deepseek/deepseek-v4-flash", "DeepSeek v4 Flash"),
    ("anthropic/claude-fable-5", "Claude Fable 5"),
    ("openai/gpt-5.6", "GPT-5.6"),
    ("openai/gpt-5-mini", "GPT-5-mini"),
]

TASK = """Build an authenticated REST API with these requirements:
1. JWT-based user auth with refresh tokens
2. Rate limiting on login endpoint (5 attempts/minute/IP)
3. Input validation on all endpoints
4. Paginated list responses (20 items/page, max 100)
5. Comprehensive error handling with proper HTTP status codes
6. Audit logging of all mutation operations
7. API versioning via URL prefix (/v1/...)
Use Python/Flask + SQLAlchemy + pytest."""

CONSTRAINTS = [
    "JWT auth with refresh tokens", "Rate limiting on login",
    "Input validation on all endpoints", "Paginated list responses",
    "Error handling with proper HTTP codes", "Audit logging of mutations",
    "API versioning via URL prefix",
]


def run_sweep(models=None, dry_run=False, limit=0, timeout=200):
    models = models or DEFAULT_MODELS
    if limit:
        models = models[:limit]

    total = len(models) * 2 * 2  # models × silent_modes × operators
    print(f"\n{'='*80}")
    print(f"SILENT MODE SWEEP — {len(models)} models × 2 silent modes × 2 operators = {total} runs")
    if dry_run:
        print("DRY RUN — showing plan only")
        for _, label in models:
            for _, mode_label in [(None, "natural"), (True, "forced-silent")]:
                print(f"  {label:>20} | {mode_label:>14} | baseline + remove_critical_constraint")
        return []

    print(f"{'='*80}")
    results = []

    for model_id, label in models:
        ensure_model_allowed(model_id)
        for silent_mode, _ in [(None, "natural"), (True, "forced-silent")]:
            sm_str = "natural" if silent_mode is None else "forced-silent"

            # --- Baseline ---
            session_name = f"[silent_sweep:baseline:{sm_str}] {label.lower().replace(' ','_')}"
            print(f"\n[{session_name}]")

            # Skip if already completed successfully
            import sqlite3 as _sql
            _c = _sql.connect(str(OPENSCODE_DB))
            _cur = _c.cursor()
            _cur.execute("SELECT cost FROM session WHERE title = ? AND cost > 0 LIMIT 1", (session_name,))
            if _cur.fetchone():
                print("  [SKIP — existing session found]")
                _c.close()
                continue
            _c.close()

            r_base = run_opencode_agentic(
                TASK, model=model_id, timeout=timeout,
                silent_mode=silent_mode, standardize=True, enforce_pytest=True,
                session_name=session_name,
            )
            sol_base = evaluate_solution(r_base.final_response, CONSTRAINTS)
            eff_base = compute_efficiency(
                prompt_tokens=r_base.prompt_tokens, completion_tokens=r_base.completion_tokens,
                reasoning_tokens=r_base.reasoning_tokens, total_tokens=r_base.total_tokens,
                solution=sol_base,
            )
            det_base = detect_constraints(r_base.final_response, CONSTRAINTS,
                                          code_files=_collect(r_base))
            markers_base = analyze_markers(r_base.final_response)

            baseline_row = {
                "model": model_id, "label": label, "silent_mode": sm_str,
                "operator": "baseline", "type": "baseline",
                "cost": r_base.estimated_cost_usd, "total_tokens": r_base.total_tokens,
                "reasoning_tokens": r_base.reasoning_tokens,
                "thinking_ratio": eff_base.thinking_ratio,
                "tests_passed": r_base.tests_passed, "tests_total": r_base.tests_total,
                "correctness": sol_base.correctness_score,
                "tools": r_base.total_tool_calls, "retries": r_base.retry_loops,
                "marker_expl": markers_base.explanatory_ratio,
                "marker_const": markers_base.constraint_ratio,
                "detected": det_base.constraints_detected,
                "detection_rate": det_base.detection_rate,
            }
            results.append(baseline_row)
            print(f"  BASELINE: ${r_base.estimated_cost_usd:.4f} {r_base.total_tokens:,}tok "
                  f"correct={sol_base.correctness_score:.0%} "
                  f"tests={r_base.tests_passed}/{r_base.tests_total} "
                  f"think={eff_base.thinking_ratio:.0%} "
                  f"markers: expl={markers_base.explanatory_ratio:.1f} const={markers_base.constraint_ratio:.1f}")
            time.sleep(2)

            # --- Perturbed ---
            ops = build_operators()
            op_name = "remove_critical_constraint"
            pert_class = ops[op_name].perturbation_class
            # Seed is a pure function of the cell (task|operator|strength|seed_variant),
            # identical across models/silent-modes so the perturbed prompt is held
            # constant for cross-model comparison (seed_variant = 0, single starting point).
            perturbed_task, _ = perturb_prompt(
                TASK, op_name, strength=0.5,
                rng_seed=derive_seed(TASK, op_name, 0.5, 0),
            )
            perturbed_prompt_sha256 = hashlib.sha256(perturbed_task.encode("utf-8")).hexdigest()
            session_name_p = f"[silent_sweep:perturbed:{sm_str}] {label.lower().replace(' ','_')}"

            # Skip if already completed
            import sqlite3 as _sql2
            _c2 = _sql2.connect(str(OPENSCODE_DB))
            _cur2 = _c2.cursor()
            _cur2.execute("SELECT cost FROM session WHERE title = ? AND cost > 0 LIMIT 1", (session_name_p,))
            if _cur2.fetchone():
                print("  [SKIP — existing perturbed session]")
                _c2.close()
                continue
            _c2.close()

            print(f"  [perturbed] {op_name}...", end=" ", flush=True)
            r_pert = run_opencode_agentic(
                perturbed_task, model=model_id, timeout=timeout,
                silent_mode=silent_mode, standardize=True, enforce_pytest=True,
                session_name=session_name_p,
            )
            sol_pert = evaluate_solution(r_pert.final_response, CONSTRAINTS,
                                         baseline_code=r_base.final_response)
            eff_pert = compute_efficiency(
                prompt_tokens=r_pert.prompt_tokens, completion_tokens=r_pert.completion_tokens,
                reasoning_tokens=r_pert.reasoning_tokens, total_tokens=r_pert.total_tokens,
                solution=sol_pert,
            )
            rc = compute_recovery_cost(
                baseline_tokens=r_base.total_tokens,
                perturbed_tokens=r_pert.total_tokens,
                baseline_cost_usd=r_base.estimated_cost_usd,
                perturbed_cost_usd=r_pert.estimated_cost_usd,
                baseline_correctness=sol_base.correctness_score,
                perturbed_correctness=sol_pert.correctness_score,
                operator=op_name,
                perturbation_class=pert_class,
                strength=0.5,
            )
            markers_pert = analyze_markers(r_pert.final_response)

            pert_row = {
                "model": model_id, "label": label, "silent_mode": sm_str,
                "operator": op_name, "type": "perturbed",
                "perturbed_prompt_sha256": perturbed_prompt_sha256,
                "cost": r_pert.estimated_cost_usd, "total_tokens": r_pert.total_tokens,
                "reasoning_tokens": r_pert.reasoning_tokens,
                "thinking_ratio": eff_pert.thinking_ratio,
                "tests_passed": r_pert.tests_passed, "tests_total": r_pert.tests_total,
                "correctness": sol_pert.correctness_score,
                "tools": r_pert.total_tool_calls, "retries": r_pert.retry_loops,
                "recovery_cost": rc.recovery_cost_usd,
                "recovery_factor": rc.recovery_cost_ratio,
                "marker_expl": markers_pert.explanatory_ratio,
                "marker_const": markers_pert.constraint_ratio,
            }
            results.append(pert_row)
            print(f"${r_pert.estimated_cost_usd:.4f} {r_pert.total_tokens:,}tok "
                  f"correct={sol_pert.correctness_score:.0%} "
                  f"recovery={rc.recovery_cost_usd:.4f} "
                  f"ratio={(f'{rc.recovery_cost_ratio:.2f}x' if rc.recovery_cost_ratio is not None else 'n/a')} "
                  f"tests={r_pert.tests_passed}/{r_pert.tests_total}")
            time.sleep(2)

    # --- Summary ---
    _print_matrix(results)
    _save_results(results)
    return results


def _print_matrix(results):
    print(f"\n{'='*120}")
    print("SILENT MODE SWEEP — Results Matrix")
    print(f"{'='*120}")

    # Compute explanation tax per model: (natural_cost / forced_cost) - 1
    by_natural = {}
    by_forced = {}
    for r in results:
        if r["type"] == "baseline":
            key = r["model"]
            if r["silent_mode"] == "natural":
                by_natural[key] = r
            else:
                by_forced[key] = r

    print(f"\n{'Model':<20} {'Nat $':>8} {'Force $':>8} {'Expl Tax':>8} {'Nat cor':>9} {'Nat Tests':>12} {'Nat Think':>9} {'Nat Mkr':>7}")
    print("-" * 100)
    for model_id, _ in DEFAULT_MODELS:
        n = by_natural.get(model_id)
        f = by_forced.get(model_id)
        if n and f:
            tax = (n["cost"] / max(f["cost"], 0.0001)) - 1
            print(f"{n['label']:<20} ${n['cost']:>7.4f} ${f['cost']:>7.4f} {tax:>7.1%} {n['correctness']:>8.0%} "
                  f"{n['tests_passed']:>3}/{n['tests_total']:>3} {n['thinking_ratio']:>8.0%} {n['marker_const']:>6.1f}")
    print()

    # Key insight
    ds_n = by_natural.get("deepseek/deepseek-v4-pro")
    ds_f = by_forced.get("deepseek/deepseek-v4-pro")
    cl_n = by_natural.get("anthropic/claude-fable-5")
    cl_f = by_forced.get("anthropic/claude-fable-5")

    if ds_n and ds_f and cl_n and cl_f:
        ds_tax = (ds_n["cost"] / max(ds_f["cost"], 0.0001)) - 1
        cl_tax = (cl_n["cost"] / max(cl_f["cost"], 0.0001)) - 1
        print(f"DeepSeek Explanation Tax: {ds_tax:+.1%}  (natural ${ds_n['cost']:.4f} vs forced ${ds_f['cost']:.4f})")
        print(f"Claude Explanation Tax:  {cl_tax:+.1%}  (natural ${cl_n['cost']:.4f} vs forced ${cl_f['cost']:.4f})")
        print(f"→ Claude pays {cl_tax-ds_tax:+.1%} more explanation tax than DeepSeek")


def _save_results(results):
    results_dir = Path("experiments/results")
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / "silent_mode_sweep.json"
    path.write_text(json.dumps({
        "experiment": "silent_mode_sweep",
        "description": "Measures natural vs forced-silent cost gap to decompose Explanation Tax",
        "runs": results,
    }, indent=2, default=str))
    print(f"\nResults saved: {path}")


def _collect(result):
    wd = getattr(result, 'workdir', '')
    if not wd or not os.path.isdir(wd):
        return None
    code = {}
    for root, dirs, files in os.walk(wd):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for f in files:
            if f.endswith('.py') and not f.startswith('.'):
                with contextlib.suppress(OSError, UnicodeDecodeError):
                    code[f] = Path(os.path.join(root, f)).read_text()
    return code if code else None


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=200)
    ap.add_argument("--models", nargs="*")
    args = ap.parse_args()

    models = None
    if args.models:
        models = [(f"{m.split(':')[0]}/{m.split(':')[1]}" if ":" in m else m, m) for m in args.models]

    run_sweep(models=models, dry_run=args.dry_run, limit=args.limit, timeout=args.timeout)
