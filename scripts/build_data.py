#!/usr/bin/env python3
"""Build data.js for the AI FinOps Framework website.

Reads inventory.json, _results_summary.json, and opencode.db,
produces a single data.js with window.FRAMEWORK_DATA containing
all measured/computed/derived values with provenance tags.

Usage:
    python scripts/build_data.py              # Write firebase/public/data.js
    python scripts/build_data.py --dry-run    # Print what would be written
"""

import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
INVENTORY_PATH = ROOT / "experiments" / "inventory.json"
SUMMARY_PATH = ROOT / "experiments" / "results" / "_results_summary.json"
REPORTS_DIR = ROOT / "experiments" / "results" / "reports"
DB_PATH = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
OUTPUT_PATH = ROOT / "firebase" / "public" / "data.js"

MODEL_LABELS = {
    "deepseek/deepseek-v4-pro": "DeepSeek v4 Pro",
    "openai/gpt-5-nano": "GPT-5-nano",
    "openai/gpt-5-mini": "GPT-5-mini",
    "openai/gpt-5": "GPT-5",
    "openai/gpt-5.5": "GPT-5.5",
    "openai/gpt-5.6": "GPT-5.6",
    "openai/gpt-5.6-fast": "GPT-5.6-fast",
    "anthropic/claude-fable-5": "Claude Fable 5",
}

MODEL_DISPLAY_ORDER = [
    "deepseek/deepseek-v4-pro",
    "openai/gpt-5-nano",
    "openai/gpt-5-mini",
    "openai/gpt-5",
    "openai/gpt-5.5",
    "openai/gpt-5.6",
    "openai/gpt-5.6-fast",
    "anthropic/claude-fable-5",
]

PROVIDER_PRICING = {
    "deepseek": {"input": 0.27, "output": 1.10, "cache_read": 0.14, "cache_write": 0.27},
    "anthropic": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "openai": {"input": 1.25, "output": 10.00, "cache_read": 0.625, "cache_write": 2.50},
}


def _fmt_usd(v):
    return round(v, 4)


def _parse_model_id(model_str):
    if model_str in MODEL_LABELS:
        return model_str
    sorted_ids = sorted(MODEL_LABELS.keys(), key=lambda k: len(k), reverse=True)
    for mid in sorted_ids:
        if mid in model_str:
            return mid
    return model_str


def _bootstrap_ci(vals, n_resamples=1000, ci=95):
    """Compute bootstrap confidence interval for the mean."""
    import random as _rnd
    if len(vals) < 2:
        return None, None
    _rng = _rnd.Random(42)
    means = []
    for _ in range(n_resamples):
        sample = [_rng.choice(vals) for _ in range(len(vals))]
        means.append(sum(sample) / len(sample))
    means.sort()
    lo_idx = int((100 - ci) / 2 * n_resamples / 100)
    hi_idx = n_resamples - lo_idx - 1
    return round(means[lo_idx], 4), round(means[hi_idx], 4)


def load_inventory():
    if not INVENTORY_PATH.exists():
        print(f"ERROR: inventory.json not found at {INVENTORY_PATH}", file=sys.stderr)
        print("  Run: python scripts/inventory.py refresh", file=sys.stderr)
        sys.exit(1)
    return json.loads(INVENTORY_PATH.read_text())


def load_summary():
    if not SUMMARY_PATH.exists():
        print(f"WARNING: _results_summary.json not found at {SUMMARY_PATH}", file=sys.stderr)
        print("  Run: python scripts/analyze_worktrees.py", file=sys.stderr)
        return {"entries": [], "by_model": {}, "by_operator": {}, "by_operator_model": {}, "strategy_distribution": {}}
    data = json.loads(SUMMARY_PATH.read_text())
    if "entries" in data:
        return data
    return {"entries": data, "by_model": {}, "by_operator": {}, "by_operator_model": {}, "strategy_distribution": {}}


def count_game_reports():
    if not REPORTS_DIR.exists():
        return 0
    return len([f for f in REPORTS_DIR.iterdir() if f.suffix == ".md"])


def query_token_breakdown():
    """Get per-model token aggregates from opencode DB."""
    if not DB_PATH.exists():
        print(f"WARNING: opencode DB not found at {DB_PATH}", file=sys.stderr)
        return {}
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT json_extract(model,'$.id') as model_id, "
        "SUM(tokens_input) as total_input, SUM(tokens_output) as total_output, "
        "SUM(tokens_reasoning) as total_reasoning, "
        "SUM(tokens_cache_read) as cache_read, SUM(tokens_cache_write) as cache_write, "
        "SUM(cost) as total_cost, COUNT(*) as sessions "
        "FROM session WHERE directory LIKE '/tmp/exp_%' AND cost > 0 "
        "GROUP BY 1 ORDER BY SUM(cost) ASC"
    ).fetchall()
    conn.close()
    result = {}
    for row in rows:
        mid = row["model_id"]
        if mid:
            result[mid] = dict(row)
    return result


def get_provider(model_id):
    if "deepseek" in model_id:
        return "deepseek"
    if "anthropic" in model_id or "claude" in model_id:
        return "anthropic"
    return "openai"


def compute_model_data(inventory, summary, db_breakdown):
    """Compute per-model aggregate metrics."""
    model_breakdown = inventory.get("model_breakdown", {})
    models = []

    for mid in MODEL_DISPLAY_ORDER:
        if mid not in model_breakdown:
            continue
        inv = model_breakdown[mid]
        label = MODEL_LABELS.get(mid, mid)
        provider = get_provider(mid)
        pricing = PROVIDER_PRICING[provider]

        db_data = db_breakdown.get(mid, {})
        entries = summary.get("entries", summary) if isinstance(summary, dict) else []
        reports = [r for r in entries if _parse_model_id(r.get("model", "")) == mid]

        valid = [r for r in reports if not r.get("narration_failure") and r.get("correctness", 0) >= 0]
        narrated = [r for r in reports if r.get("narration_failure")]

        avg_cost = _fmt_usd(sum(r.get("cost", 0) for r in valid) / max(len(valid), 1))
        total_cost = _fmt_usd(inv.get("cost", 0))

        pass_rate_val = None
        total_tests = 0
        total_passed = 0
        for r in valid:
            tr = r.get("test_results")
            if tr and tr.get("total", 0) > 0:
                total_tests += tr["total"]
                total_passed += tr["passed"]
        if total_tests > 0:
            pass_rate_val = f"{total_passed / total_tests:.0%} ({total_passed}/{total_tests})"
        elif valid:
            pass_rate_val = f"{(sum(r['correctness'] for r in valid) / len(valid)):.0%} [H]"

        strategies = {"conservative": 0, "exploratory": 0, "wasteful": 0, "efficient": 0}
        for r in valid:
            s = (r.get("strategy", "") or "").lower()
            if s in strategies:
                strategies[s] += 1

        avg_loc = round(sum(r.get("code_lines", 0) for r in valid) / max(len(valid), 1))
        avg_thinking = round(sum(r.get("thinking_ratio", 0) for r in valid) / max(len(valid), 1), 3)
        avg_escape = round(sum(r.get("escape", 0) for r in valid) / max(len(valid), 1), 2)
        avg_narration = round(sum(r.get("narration_penalty", 0) for r in valid) / max(len(valid), 1), 2)
        avg_arch_div = round(sum(r.get("architecture_divergence", 0) for r in valid) / max(len(valid), 1), 3)
        avg_struct_div = round(sum(r.get("structure_divergence", 0) for r in valid) / max(len(valid), 1), 3)
        avg_composite = round(sum(r.get("composite_score", 0) for r in valid) / max(len(valid), 1), 3)
        avg_code_quality = round(sum(r.get("code_quality_score", 0) for r in valid) / max(len(valid), 1), 3)
        avg_comment_ratio = round(sum(r.get("comment_ratio", 0) for r in valid) / max(len(valid), 1), 3)

        avg_energy = round(sum(r.get("energy_total_j", 0) for r in valid) / max(len(valid), 1), 1)
        avg_energy_per_loc = round(avg_energy / max(avg_loc, 1), 2)
        avg_cost_per_joule = round(sum(r.get("correctness_per_dollar", 0) for r in valid) / max(len(valid), 1), 4)
        avg_joules_per_loc = round(sum(r.get("quality_per_joule", 0) for r in valid) / max(len(valid), 1), 4)

        cost_in = _fmt_usd(sum(r.get("cost_input_usd", 0) for r in valid))
        cost_out = _fmt_usd(sum(r.get("cost_output_usd", 0) for r in valid))
        cost_reason = _fmt_usd(sum(r.get("cost_reasoning_usd", 0) for r in valid))
        cost_cache_actual = _fmt_usd(sum(r.get("cost_cache_usd", 0) for r in valid))

        narration_rate = round(len(narrated) / max(len(reports), 1) * 100) if reports else 0

        tokens_in = sum(r.get("tokens_input", 0) for r in valid)
        tokens_out = sum(r.get("tokens_output", 0) for r in valid)
        tokens_reason = sum(r.get("tokens_reasoning", 0) for r in valid)
        cache_r = sum(r.get("tokens_cache_read", 0) for r in valid)
        cache_w = sum(r.get("tokens_cache_write", 0) for r in valid)

        total_tok = tokens_in + tokens_out + tokens_reason
        if total_tok > 0:
            cost_input = _fmt_usd(total_cost * tokens_in / total_tok) if tokens_in else 0
            cost_output = _fmt_usd(total_cost * tokens_out / total_tok) if tokens_out else 0
            cost_reasoning = _fmt_usd(total_cost * tokens_reason / total_tok) if tokens_reason else 0
            cost_cache = _fmt_usd(total_cost - cost_input - cost_output - cost_reasoning)
            if cost_cache < 0:
                cost_cache = 0
        else:
            cost_input = cost_output = cost_reasoning = cost_cache = 0

        models.append({
            "id": mid,
            "label": label,
            "provider": provider,
            "sessions": inv.get("sessions", 0),
            "n_reports": len(reports),
            "n_valid": len(valid),
            "n_narrated": len(narrated),
            "reports": len(reports),
            "reports_valid": len(valid),
            "reports_narrated": len(narrated),
            "avg_cost": avg_cost,
            "total_cost": total_cost,
            "cost_ci95": list(_bootstrap_ci([r.get("cost", 0) for r in valid])) if len(valid) >= 5 else None,
            "pass_rate": pass_rate_val or "N/A",
            "strategy_cons": strategies["conservative"],
            "strategy_expl": strategies["exploratory"],
            "strategy_waste": strategies["wasteful"],
            "strategy_efficient": strategies["efficient"],
            "avg_loc": avg_loc,
            "avg_thinking_ratio": avg_thinking,
            "avg_escape": avg_escape,
            "avg_narration_penalty": avg_narration,
            "avg_arch_divergence": avg_arch_div,
            "avg_struct_divergence": avg_struct_div,
            "avg_composite_score": avg_composite,
            "avg_code_quality": avg_code_quality,
            "avg_comment_ratio": avg_comment_ratio,
            "avg_energy_j": avg_energy,
            "avg_energy_j_per_loc": avg_energy_per_loc,
            "avg_cost_per_joule": avg_cost_per_joule,
            "avg_quality_per_joule": avg_joules_per_loc,
            "narration_rate": narration_rate,
            "cost_input": cost_in,
            "cost_output": cost_out,
            "cost_reasoning": cost_reason,
            "cost_cache": cost_cache_actual,
            "tokens_total": total_tok,
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "tokens_reasoning": tokens_reason,
            "tokens_cache_read": cache_r,
            "tokens_cache_write": cache_w,
        })

    return models


def compute_charts(models):
    labels = [m["label"] for m in models]
    cost_data = [m["avg_cost"] for m in models]
    narr_data = [m["narration_rate"] for m in models]
    loc_data = [m["avg_loc"] for m in models]
    reports = [m["reports"] for m in models]
    return {
        "labels": labels,
        "costData": cost_data,
        "narrData": narr_data,
        "locData": loc_data,
        "costY": cost_data,
        "reports": reports,
    }


def compute_calculator(models):
    model_costs = [
        {"n": m["label"], "c": m["avg_cost"], "p": float(str(m.get("pass_rate", "0")).split("%")[0]) / 100 if "%" in str(m.get("pass_rate", "")) else 0}
        for m in models
    ]

    cheapest = model_costs[0]["c"] if model_costs else 0.001
    esc_tiers = []
    for mc in model_costs[1:]:
        if cheapest > 0:
            esc_tiers.append({
                "m": f"DS→{mc['n'].replace('DeepSeek v4 Pro→','').split(' ')[-1] if 'DeepSeek' in model_costs[0]['n'] else mc['n']}",
                "e": round(mc["c"] / cheapest, 1),
            })
    esc_tiers.append({"m": "→Human ($5/job)", "e": round(5 / cheapest, 1)})

    narrated = sum(1 for m in models for r in range(m.get("reports_narrated", 0)))
    total_runs = sum(m["reports"] for m in models)
    retry_rate = round(narrated / max(total_runs, 1), 3)
    woc = round(1 / (1 + retry_rate), 2)

    return {
        "model_costs": model_costs,
        "escalation_tiers": esc_tiers,
        "retry_rate_measured": retry_rate,
        "woc_ratio": woc,
    }


def compute_derived(models, inventory, report_count):
    counts = inventory.get("counts", {})
    costs = inventory.get("costs", {})

    valid_tests = 0
    total_tests_sum = 0
    total_model_correctness = 0
    total_model_weight = 0
    for m in models:
        pr = m.get("pass_rate", "")
        if "(" in str(pr) and "/" in str(pr):
            parts = str(pr).split("(")[1].split(")")[0].split("/")
            if len(parts) == 2:
                try:
                    total_tests_sum += int(parts[1])
                    valid_tests += int(parts[0])
                except ValueError:
                    pass
        elif "%" in str(pr) and m["reports_valid"] > 0:
            try:
                val = float(str(pr).split("%")[0])
                if val > 1:
                    val = val / 100
                total_model_correctness += val * m["reports_valid"]
                total_model_weight += m["reports_valid"]
            except ValueError:
                pass

    if total_tests_sum > 0:
        overall_pass_rate = f"{valid_tests / total_tests_sum:.1%} ({valid_tests}/{total_tests_sum})"
    elif total_model_weight > 0:
        avg_correctness = total_model_correctness / total_model_weight
        overall_pass_rate = f"{avg_correctness:.1%} [H]"
    else:
        overall_pass_rate = "N/A"

    claude = next((m for m in models if "claude" in m["id"]), None)
    deepseek = next((m for m in models if "deepseek" in m["id"]), None)
    cost_gap = None
    cost_gap_computation = None
    if claude and deepseek and deepseek["avg_cost"] > 0:
        gap = claude["avg_cost"] / deepseek["avg_cost"]
        cost_gap = f"{round(gap)}×"
        cost_gap_computation = f"${claude['avg_cost']} / ${deepseek['avg_cost']} = {gap:.1f}×"

    total_narrated = sum(m["reports_narrated"] for m in models)
    total_valid = sum(m["reports_valid"] for m in models)
    total_reports = sum(m["reports"] for m in models)

    return {
        "cost_gap": cost_gap or "N/A",
        "cost_gap_computation": cost_gap_computation or "",
        "overall_pass_rate": overall_pass_rate,
        "total_tests_passed": valid_tests,
        "total_tests_run": total_tests_sum,
        "total_cost_all_models": _fmt_usd(costs.get("total_experiment_sessions", 0)),
        "total_cost_deepseek": _fmt_usd(sum(m["total_cost"] for m in models if "deepseek" in m["id"])),
        "total_cost_claude": _fmt_usd(sum(m["total_cost"] for m in models if "claude" in m["id"])),
        "total_narrated": total_narrated,
        "total_valid_reports": total_valid,
        "total_reports_analyzed": total_reports,
    }


def build():
    print("Building data.js...")

    inventory = load_inventory()
    print(f"  Loaded inventory: {inventory['counts']['db_sessions_experiments']} experiment sessions")

    summary = load_summary()
    entries = summary.get("entries", [])
    print(f"  Loaded summary: {len(entries)} worktree entries")

    report_count = count_game_reports()
    print(f"  Game reports on disk: {report_count}")

    db_breakdown = query_token_breakdown()
    print(f"  DB query: {len(db_breakdown)} models with token data")

    models = compute_model_data(inventory, summary, db_breakdown)
    print(f"  Computed: {len(models)} models")

    charts = compute_charts(models)
    calculator = compute_calculator(models)
    derived = compute_derived(models, inventory, report_count)

    # ── Operator comparison — per-operator × per-model matrices ──
    by_op_model = summary.get("by_operator_model", {})
    op_comparison = {}
    for key, agg in by_op_model.items():
        parts = key.split("|", 2)
        if len(parts) >= 3:
            op = parts[0]
            pc = parts[1]
            mdl = parts[2]
            model_label = MODEL_LABELS.get(mdl, mdl)
            if op not in op_comparison:
                op_comparison[op] = {"perturbation_class": pc, "models": {}}
            op_comparison[op]["models"][model_label] = {
                "n": agg.get("n", agg.get("count", 0)),
                "avg_cost": agg.get("cost_avg", 0),
                "cost_ci95": [agg.get("cost_ci95_lo"), agg.get("cost_ci95_hi")] if agg.get("cost_ci95_lo") is not None else None,
                "avg_escape": agg.get("escape_avg", 0),
                "escape_ci95": [agg.get("escape_ci95_lo"), agg.get("escape_ci95_hi")] if agg.get("escape_ci95_lo") is not None else None,
                "avg_correctness": agg.get("correctness_avg", 0),
                "correctness_ci95": [agg.get("correctness_ci95_lo"), agg.get("correctness_ci95_hi")] if agg.get("correctness_ci95_lo") is not None else None,
                "avg_thinking_ratio": agg.get("thinking_ratio_avg", 0),
                "avg_energy_j": agg.get("energy_total_j_avg", 0),
                "low_n": (agg.get("n", agg.get("count", 0)) < 5),
            }

    # ── Perturbation class breakdown — manifold vs semantic vs baseline ──
    pert_class_breakdown = {}
    for e in entries:
        if e.get("narration_failure"):
            continue
        pc = e.get("perturbation_class", "unknown")
        mdl = e.get("model", "unknown")
        if pc not in pert_class_breakdown:
            pert_class_breakdown[pc] = {}
        model_label = MODEL_LABELS.get(mdl, mdl)
        if model_label not in pert_class_breakdown[pc]:
            pert_class_breakdown[pc][model_label] = {"count": 0, "costs": [], "escapes": [],
                "correctness": [], "thinking_ratios": [], "locs": [], "tokens": [], "narration_penalties": []}
        pb = pert_class_breakdown[pc][model_label]
        pb["count"] += 1
        pb["costs"].append(e.get("cost", 0))
        pb["escapes"].append(e.get("escape", 0))
        pb["correctness"].append(e.get("correctness", 0))
        pb["thinking_ratios"].append(e.get("thinking_ratio", 0))
        pb["locs"].append(e.get("code_lines", 0))
        pb["tokens"].append(e.get("tokens", 0))
        pb["narration_penalties"].append(e.get("narration_penalty", 0))

    pert_class_summary = {}
    for pc, pc_models in pert_class_breakdown.items():
        pert_class_summary[pc] = {}
        for label, pb in pc_models.items():
            n = pb["count"]
            pert_class_summary[pc][label] = {
                "n": n,
                "low_n": n < 5,
                "avg_cost": round(sum(pb["costs"]) / n, 4),
                "cost_ci95": list(_bootstrap_ci(pb["costs"])) if n >= 5 else None,
                "avg_escape": round(sum(pb["escapes"]) / n, 2),
                "escape_ci95": list(_bootstrap_ci(pb["escapes"])) if n >= 5 else None,
                "avg_correctness": round(sum(pb["correctness"]) / n, 2),
                "correctness_ci95": list(_bootstrap_ci(pb["correctness"])) if n >= 5 else None,
                "avg_thinking_ratio": round(sum(pb["thinking_ratios"]) / n, 3),
                "avg_loc": round(sum(pb["locs"]) / n),
                "avg_tokens": round(sum(pb["tokens"]) / n),
                "avg_narration_penalty": round(sum(pb["narration_penalties"]) / n, 2),
            }

    # ── Energy ranking — per-model energy metrics ──
    energy_ranking = sorted(
        [{"id": m["id"], "label": m["label"], "avg_energy_j": m["avg_energy_j"],
          "avg_energy_j_per_loc": m["avg_energy_j_per_loc"],
          "avg_cost": m["avg_cost"], "avg_loc": m["avg_loc"]}
         for m in models if m["avg_energy_j"] > 0],
        key=lambda x: x["avg_energy_j_per_loc"]
    )

    counts = inventory.get("counts", {})
    costs = inventory.get("costs", {})

    data = {
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_inventory": str(INVENTORY_PATH),
            "source_summary": str(SUMMARY_PATH),
            "source_db": str(DB_PATH),
            "provenance_note": "All values tagged [M]easured, [C]omputed, [H]euristic, or e[X]ternal. See methodology.html.",
        },
        "summary": {
            "worktrees_total": counts.get("worktrees_total", 0),
            "sessions_total": counts.get("db_sessions_experiments", 0),
            "game_reports": report_count,
            "total_cost": _fmt_usd(costs.get("total_experiment_sessions", 0)),
            "architectures": 3,
            "variants": 8,
            "configs": counts.get("config_files", 0),
        },
        "models": models,
        "charts": charts,
        "calculator": calculator,
        "derived": derived,
        "operator_comparison": op_comparison,
        "perturbation_class_breakdown": pert_class_summary,
        "energy_ranking": energy_ranking,
        "strategy_distribution": summary.get("strategy_distribution", {}),
        "design_parameters": {
            "beta": {"value": 0.001, "provenance": "design", "note": "Context inflation rate — calibrate to your codebase"},
            "woc_healthy": {"value": 0.85, "provenance": "design"},
            "woc_critical": {"value": 0.70, "provenance": "design"},
            "strategy_thresholds": {
                "correctness_min": 0.7, "escape_min": 0.5, "novelty_min": 0.4,
                "efficient_cost_max": 0.003, "wasteful_correctness_max": 0.3,
                "provenance": "design",
            },
            "composite_weights": {
                "correctness": 0.35, "constraint": 0.30, "quality": 0.20, "novelty": 0.15,
                "provenance": "design",
            },
        },
        "external_sources": {
            "epm_baseline": {"value": "1.6%/yr", "provenance": "X", "source": "IEA World Energy Outlook 2024"},
            "epm_aggressive": {"value": "2.5%/yr", "provenance": "X", "source": "Aggressive scenario"},
            "energy_per_token_prompt": {"value": 0.08, "unit": "J", "provenance": "X", "source": "TokenPowerBench (Niu et al., AAAI 2026)"},
            "energy_per_token_output": {"value": 0.23, "unit": "J", "provenance": "X", "source": "TokenPowerBench (Niu et al., AAAI 2026)"},
            "energy_per_token_reasoning": {"value": 0.47, "unit": "J", "provenance": "X", "source": "TokenPowerBench (Niu et al., AAAI 2026)"},
            "claude_active_params": {"value": "500B", "provenance": "X", "note": "Conservative estimate"},
            "deepseek_active_params": {"value": "37B", "provenance": "X", "note": "MoE, ~3% active at inference"},
        },
    }

    js = f"/* Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} by build_data.py */\n"
    js += "/* DO NOT EDIT — regenerate with: python scripts/build_data.py */\n"
    js += "window.FRAMEWORK_DATA = " + json.dumps(data, indent=2, default=str) + ";\n"

    return js, data


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build data.js for the AI FinOps Framework website")
    parser.add_argument("--dry-run", action="store_true", help="Print instead of writing")
    args = parser.parse_args()

    js, data = build()

    if args.dry_run:
        print("\n--- DRY RUN: data.js would contain ---\n")
        print(json.dumps(data, indent=2, default=str)[:8000])
        if len(json.dumps(data, indent=2)) > 8000:
            print(f"\n... ({len(json.dumps(data, indent=2))} chars total, truncated)")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(js)
    print(f"\nWrote {OUTPUT_PATH} ({len(js)} bytes)")


if __name__ == "__main__":
    main()
