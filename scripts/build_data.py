#!/usr/bin/env python3
"""Build data.js for the Agentic Dynamics website.

Reads inventory.json, _results_summary.json, and opencode.db,
produces a single data.js with window.DYNAMICS_DATA containing
all measured/computed/derived values with provenance tags.

Usage:
    python scripts/build_data.py              # Write firebase/public/data.js
    python scripts/build_data.py --dry-run    # Print what would be written
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
INVENTORY_PATH = ROOT / "experiments" / "inventory.json"
SUMMARY_PATH = ROOT / "experiments" / "results" / "_results_summary.json"
REPORTS_DIR = ROOT / "experiments" / "results" / "reports"
DB_PATH = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
OUTPUT_PATH = ROOT / "firebase" / "public" / "data.js"

DATA_DIR = ROOT / "experiments" / "data"

from _constants import MODEL_LABELS, WORKTREE_ROOT, bootstrap_ci, probe_session_schema

from instrument.routing import compute_routing  # noqa: E402
from instrument.solution import COMPOSITE_WEIGHTS  # noqa: E402

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


def _load_grit_matrix():
    """Load lab_grit_matrix.json for the Grit bubble chart."""
    grit_path = ROOT / "experiments" / "results" / "lab_grit_matrix.json"
    if not grit_path.exists():
        return []
    try:
        data = json.loads(grit_path.read_text())
        return data.get("points", [])
    except Exception:
        return []


def _compute_sonar(entries):
    """Per-model SonarQube quality aggregates, excluding known library-copy outliers."""
    from collections import defaultdict

    SONAR_OUTLIERS = {"exp_batch_fastapi_maintenance_natural"}  # noqa: N806
    models = defaultdict(lambda: {"bugs": [], "smells": [], "ncloc": [],
                                   "scores": [], "ratings": [], "gates_ok": 0, "total": 0})

    for e in entries:
        if not e.get("sonar_analyzed"):
            continue
        if e.get("worktree_name", "") in SONAR_OUTLIERS:
            continue
        model = e.get("model", "unknown")
        m = models[model]
        m["bugs"].append(e.get("sonar_bugs", 0))
        m["smells"].append(e.get("sonar_code_smells", 0))
        m["ncloc"].append(e.get("sonar_ncloc", 0))
        m["scores"].append(e.get("sonar_quality_score", 0))
        m["ratings"].append(e.get("sonar_maintainability_rating", ""))
        m["total"] += 1
        if e.get("sonar_quality_gate", "").upper() == "OK":
            m["gates_ok"] += 1

    result = {}
    for mid, v in sorted(models.items()):
        if not v["ncloc"]:
            continue
        total_loc = sum(v["ncloc"])
        label = mid.split("/")[-1]
        result[label] = {
            "avg_bugs": round(sum(v["bugs"]) / len(v["bugs"]), 1),
            "avg_smells": round(sum(v["smells"]) / len(v["smells"]), 1),
            "avg_loc": round(total_loc / len(v["ncloc"])),
            "bugs_per_kloc": round(sum(v["bugs"]) / max(total_loc, 1) * 1000, 1),
            "smells_per_kloc": round(sum(v["smells"]) / max(total_loc, 1) * 1000, 1),
            "avg_quality_score": round(sum(v["scores"]) / len(v["scores"]), 3),
            "maintainability": max(set(v["ratings"]), key=v["ratings"].count) if v["ratings"] else "?",
            "gate_pass_rate": round(v["gates_ok"] / v["total"] * 100) if v["total"] > 0 else 0,
            "worktrees_analyzed": v["total"],
        }
    return result


def count_game_reports():

    if not REPORTS_DIR.exists():
        return 0
    return len([f for f in REPORTS_DIR.iterdir() if f.suffix == ".md"])


def query_token_breakdown():
    """Get per-model token aggregates from opencode DB."""
    if not DB_PATH.exists():
        print(f"WARNING: opencode DB not found at {DB_PATH}", file=sys.stderr)
        return {}
    probe_session_schema(
        str(DB_PATH),
        ("model", "directory", "cost", "tokens_input", "tokens_output",
         "tokens_reasoning", "tokens_cache_read", "tokens_cache_write"),
    )
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT json_extract(model,'$.id') as model_id, "
        "SUM(tokens_input) as total_input, SUM(tokens_output) as total_output, "
        "SUM(tokens_reasoning) as total_reasoning, "
        "SUM(tokens_cache_read) as cache_read, SUM(tokens_cache_write) as cache_write, "
        "SUM(cost) as total_cost, COUNT(*) as sessions "
        f"FROM session WHERE directory LIKE '{WORKTREE_ROOT}/exp_%' AND cost > 0 "
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
        inv = model_breakdown.get(mid, {})
        label = MODEL_LABELS.get(mid, mid)
        provider = get_provider(mid)

        db_breakdown.get(mid, {})
        entries = summary.get("entries", summary) if isinstance(summary, dict) else []
        reports = [r for r in entries if _parse_model_id(r.get("model", "")) == mid]

        valid = [r for r in reports if not r.get("narration_failure") and r.get("correctness", 0) >= 0]
        narrated = [r for r in reports if r.get("narration_failure")]

        avg_cost = _fmt_usd(sum(r.get("cost", 0) for r in valid) / max(len(valid), 1))
        total_cost = _fmt_usd(inv.get("cost", 0) if inv else sum(r.get("cost", 0) for r in reports))

        pass_rate_val = None
        total_tests = 0
        total_passed = 0
        n_tested = 0
        n_heuristic = 0
        for r in valid:
            tr = r.get("test_results")
            if tr and tr.get("total", 0) > 0:
                total_tests += tr["total"]
                total_passed += tr["passed"]
                n_tested += 1
            elif r.get("evaluator_source") == "heuristic":
                n_heuristic += 1
        if total_tests > 0:
            tag = " [mixed]" if n_heuristic > 0 else " [tests]"
            pass_rate_val = f"{total_passed / total_tests:.0%} ({total_passed}/{total_tests}){tag}"
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
        correctness_per_dollar = round(sum(r.get("correctness_per_dollar", 0) for r in valid) / max(len(valid), 1), 4)
        avg_joules_per_loc = round(sum(r.get("quality_per_joule", 0) for r in valid) / max(len(valid), 1), 4)

        # AST-derived aggregates
        ast_files = round(sum((r.get("ast", {}) or {}).get("py_files", 0) + (r.get("ast", {}) or {}).get("ts_files", 0) for r in valid) / max(len(valid), 1), 1)
        ast_functions = round(sum((r.get("ast", {}) or {}).get("total_functions", 0) for r in valid) / max(len(valid), 1))
        ast_classes = round(sum((r.get("ast", {}) or {}).get("total_classes", 0) for r in valid) / max(len(valid), 1))
        ast_type_hint_pct = round(sum((r.get("ast", {}) or {}).get("type_hint_pct", 0) for r in valid) / max(len(valid), 1)) if valid else 0
        ast_docstring_pct = round(sum((r.get("ast", {}) or {}).get("docstring_pct", 0) for r in valid) / max(len(valid), 1)) if valid else 0
        avg_constraints_met = round(sum(r.get("constraints_met", 0) for r in valid) / max(len(valid), 1), 1)
        avg_constraints_total = round(sum(r.get("constraints_total", 0) for r in valid) / max(len(valid), 1), 1)

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

        models.append({
            "id": mid,
            "label": label,
            "provider": provider,
            "sessions": inv.get("sessions", len(reports)),
            "n_reports": len(reports),
            "n_valid": len(valid),
            "n_narrated": len(narrated),
            "reports": len(reports),
            "reports_valid": len(valid),
            "reports_narrated": len(narrated),
            "avg_cost": avg_cost,
            "total_cost": total_cost,
            "cost_ci95": bootstrap_ci([r.get("cost", 0) for r in valid]) if len(valid) >= 5 else None,
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
            "correctness_per_dollar": correctness_per_dollar,
            "avg_quality_per_joule": avg_joules_per_loc,
            "narration_rate": narration_rate,
            "ast_files": ast_files,
            "ast_functions": ast_functions,
            "ast_classes": ast_classes,
            "ast_type_hint_pct": ast_type_hint_pct,
            "ast_docstring_pct": ast_docstring_pct,
            "avg_constraints_met": avg_constraints_met,
            "avg_constraints_total": avg_constraints_total,
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
            "_provenance": {
                "sessions": "M", "n_reports": "M", "n_valid": "M", "n_narrated": "M",
                "total_cost": "M", "tokens_input": "M", "tokens_output": "M",
                "tokens_reasoning": "M", "tokens_cache_read": "M", "tokens_cache_write": "M",
                "tokens_total": "M",
                "avg_cost": "C", "cost_ci95": "C", "avg_loc": "C",
                "avg_thinking_ratio": "C", "avg_escape": "C", "avg_narration_penalty": "C",
                "avg_arch_divergence": "C", "avg_struct_divergence": "C",
                "avg_composite_score": "C", "avg_code_quality": "C", "avg_comment_ratio": "C",
                "avg_energy_j": "C", "avg_energy_j_per_loc": "C",
                "avg_quality_per_joule": "C",
                "correctness_per_dollar": "C", "ast_files": "C", "ast_functions": "C",
                "ast_classes": "C", "ast_type_hint_pct": "C", "ast_docstring_pct": "C",
                "avg_constraints_met": "C", "avg_constraints_total": "C",
                "narration_rate": "C",
                "cost_input": "C", "cost_output": "C", "cost_reasoning": "C", "cost_cache": "C",
                "strategy_cons": "C", "strategy_expl": "C", "strategy_waste": "C", "strategy_efficient": "C",
                "pass_rate": "H" if total_tests == 0 else ("M/C" if n_heuristic > 0 else "M"),
            }
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
    if cheapest > 0:
        esc_tiers.append({"m": "→Human ($5/job)", "e": round(5 / cheapest, 1)})
    else:
        esc_tiers.append({"m": "→Human ($5/job)", "e": 0})

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
    inventory.get("counts", {})
    inventory.get("costs", {})

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
        tag = " [mixed]" if total_model_weight > 0 else " [tests]"
        overall_pass_rate = f"{valid_tests / total_tests_sum:.1%} ({valid_tests}/{total_tests_sum}){tag}"
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
        "total_cost_all_models": _fmt_usd(sum(m["total_cost"] for m in models)),
        "total_cost_deepseek": _fmt_usd(sum(m["total_cost"] for m in models if "deepseek" in m["id"])),
        "total_cost_claude": _fmt_usd(sum(m["total_cost"] for m in models if "claude" in m["id"])),
        "total_narrated": total_narrated,
        "total_valid_reports": total_valid,
        "total_reports_analyzed": total_reports,
        "_provenance": {
            "cost_gap": "C", "overall_pass_rate": "C",
            "total_tests_passed": "M", "total_tests_run": "M",
            "total_cost_all_models": "M", "total_cost_deepseek": "M",
            "total_cost_claude": "M",
            "total_narrated": "M", "total_valid_reports": "M",
            "total_reports_analyzed": "M",
        },
    }


def _load_review_data() -> dict:
    """Aggregate the review-agent corpus into per-model quality metrics.

    The review agent (DeepSeek Flash) reviews every commit and every story.
    Returns per-reviewed-model: coherence, architectural_fit, convention
    adherence, better/worse distribution, and top compounding-issue themes.
    """
    import statistics
    from collections import Counter

    reviews_dir = ROOT / "experiments" / "results" / "reviews"
    stories_dir = ROOT / "experiments" / "results" / "stories"

    sid_to_model = {}
    for f in stories_dir.glob("*.json"):
        if "dvs" in f.name or "log" in f.name:
            continue
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        sid = f.stem.split("_")[-1]
        if len(sid) >= 8:
            sid_to_model[sid] = d.get("model", "?")

    by_model = {}
    total_commit_reviews = 0
    total_story_reviews = 0

    for f in reviews_dir.glob("review_*.json"):
        # Skip per-session files (review_{id}_S{n}.json) and story files
        # (review_{id}_story.json) — only aggregate review_{id}.json counts.
        if "_S" in f.stem or f.stem.endswith("_story"):
            continue
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        sid = d.get("story_id", "")
        reviewed = sid_to_model.get(sid, "?").split("/")[-1]
        m = by_model.setdefault(reviewed, {
            "model": reviewed, "stories": 0, "coherence": [],
            "arch_fit": [], "convention": [], "bow": Counter(),
            "issue_themes": Counter(),
        })
        sr = d.get("story_review")
        if sr:
            m["stories"] += 1
            total_story_reviews += 1
            coh = sr.get("overall_coherence")
            if coh is not None:
                m["coherence"].append(coh)
            for issue in sr.get("compounding_issues", []):
                m["issue_themes"][_classify_issue(issue)] += 1
        for cr in d.get("commit_reviews", []):
            total_commit_reviews += 1
            af = cr.get("architectural_fit")
            ca = cr.get("convention_adherence")
            if af is not None:
                m["arch_fit"].append(af)
            if ca is not None:
                m["convention"].append(ca)
            m["bow"][cr.get("better_or_worse", "?")] += 1

    models = []
    for reviewed, m in by_model.items():
        total_bow = sum(m["bow"].values()) or 1
        label = _short_model_label(reviewed)
        models.append({
            "model": reviewed,
            "label": label,
            "stories": m["stories"],
            "overall_coherence": round(statistics.mean(m["coherence"]), 3) if m["coherence"] else None,
            "architectural_fit": round(statistics.mean(m["arch_fit"]), 3) if m["arch_fit"] else None,
            "convention_adherence": round(statistics.mean(m["convention"]), 3) if m["convention"] else None,
            "better_pct": round(m["bow"].get("better", 0) / total_bow * 100, 1),
            "worse_pct": round(m["bow"].get("worse", 0) / total_bow * 100, 1),
            "neutral_pct": round(m["bow"].get("neutral", 0) / total_bow * 100, 1),
            "top_issues": [
                {"theme": t, "count": c}
                for t, c in m["issue_themes"].most_common(5)
            ],
        })
    models.sort(key=lambda x: x.get("overall_coherence") or 0, reverse=True)

    return {
        "models": models,
        "commit_reviews": total_commit_reviews,
        "story_reviews": total_story_reviews,
        "reviewer": "deepseek/deepseek-v4-flash",
    }


def _classify_issue(text: str) -> str:
    low = text.lower()
    if any(k in low for k in ("secret", "hard-coded", "hardcoded", "auth", "jwt", "password")):
        return "security"
    if "test" in low:
        return "test gaps"
    if any(k in low for k in ("migration", "schema", "alter table")):
        return "schema drift"
    if any(k in low for k in ("coupl", "orchestrat")):
        return "coupling"
    if any(k in low for k in ("refactor", "repository", "layer")):
        return "incomplete refactor"
    if any(k in low for k in ("pagination", "delete", "missing", "rate limit")):
        return "missing surface"
    return "other"


def _load_analysis_data() -> dict:
    """Aggregate AST + SonarQube + convention data from analysis files."""
    from collections import Counter

    analysis_dir = ROOT / "experiments" / "results" / "analysis"
    stories_dir = ROOT / "experiments" / "results" / "stories"

    sid_to_model = {}
    for f in stories_dir.glob("*.json"):
        if "dvs" in f.name or "log" in f.name:
            continue
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        sid = f.stem.split("_")[-1]
        if len(sid) >= 8:
            sid_to_model[sid] = d.get("model", "?")

    by_model = {}
    n_analysis = 0
    n_sonar_available = 0
    n_commits = 0

    for f in analysis_dir.glob("*.json"):
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        n_analysis += 1
        sid = d.get("story_id", "")
        reviewed = sid_to_model.get(sid, "?").split("/")[-1]
        m = by_model.setdefault(reviewed, {
            "model": reviewed, "commits": 0,
            "lines_added": 0, "lines_removed": 0,
            "functions_added": 0, "functions_removed": 0,
            "classes_added": 0, "imports_added": 0,
            "sonar_available": 0,
            "sonar_bugs_delta": 0, "sonar_smells_delta": 0,
            "sonar_complexity_delta": 0,
            "convention_scores": [],
            "deep_cells": 0, "lsp_available": 0, "lsp_errors": 0, "lsp_warnings": 0,
            "solution_correctness": [], "solution_constraints": [],
            "solution_quality": [], "solution_novelty": [], "solution_composite": [],
            "basin_escape": [],
            "strategies": Counter(),
        })
        summary = d.get("summary", {})
        conv = summary.get("average_convention_score")
        if conv is not None:
            m["convention_scores"].append(conv)
        for c in d.get("commits", []):
            m["commits"] += 1
            n_commits += 1
            ast = c.get("ast", {})
            m["lines_added"] += ast.get("lines_added", 0)
            m["lines_removed"] += ast.get("lines_removed", 0)
            m["functions_added"] += ast.get("functions_added", 0)
            m["functions_removed"] += ast.get("functions_removed", 0)
            m["classes_added"] += ast.get("classes_added", 0)
            m["imports_added"] += ast.get("imports_added", 0)
            sonar = c.get("sonar", {})
            if sonar.get("available"):
                m["sonar_available"] += 1
                n_sonar_available += 1
                m["sonar_bugs_delta"] += sonar.get("bugs_delta", 0)
                m["sonar_smells_delta"] += sonar.get("smells_delta", 0)
                m["sonar_complexity_delta"] += sonar.get("complexity_delta", 0)

        deep = d.get("deep", {})
        if deep:
            m["deep_cells"] += 1
            lsp = deep.get("lsp", {})
            if lsp.get("available"):
                m["lsp_available"] += 1
            m["lsp_errors"] += lsp.get("errors", 0) or 0
            m["lsp_warnings"] += lsp.get("warnings", 0) or 0
            sol = deep.get("solution", {})
            m["solution_correctness"].append(sol.get("correctness_score", 0) or 0)
            m["solution_constraints"].append(sol.get("constraint_score", 0) or 0)
            m["solution_quality"].append(sol.get("code_quality_score", 0) or 0)
            m["solution_novelty"].append(sol.get("novelty_score", 0) or 0)
            m["solution_composite"].append(sol.get("composite_score", 0) or 0)
            basin = deep.get("basin", {})
            m["basin_escape"].append(basin.get("escape_score", 0) or 0)
            m["strategies"][deep.get("strategy", {}).get("strategy", "?")] += 1

    def _avg(lst):
        return round(sum(lst) / len(lst), 3) if lst else None

    models = []
    for reviewed, m in by_model.items():
        n = len(m["convention_scores"])
        cells = m["deep_cells"] or 1
        models.append({
            "model": reviewed,
            "label": _short_model_label(reviewed),
            "commits": m["commits"],
            "lines_added": m["lines_added"],
            "lines_removed": m["lines_removed"],
            "functions_added": m["functions_added"],
            "classes_added": m["classes_added"],
            "imports_added": m["imports_added"],
            "sonar_available": m["sonar_available"],
            "sonar_bugs_delta": m["sonar_bugs_delta"],
            "sonar_smells_delta": m["sonar_smells_delta"],
            "sonar_complexity_delta": m["sonar_complexity_delta"],
            "avg_convention": round(sum(m["convention_scores"]) / n, 3) if n else None,
            "deep_cells": m["deep_cells"],
            "lsp_available": m["lsp_available"],
            "lsp_errors_per_cell": round(m["lsp_errors"] / cells, 1),
            "lsp_warnings_per_cell": round(m["lsp_warnings"] / cells, 1),
            "solution_correctness": _avg(m["solution_correctness"]),
            "solution_constraints": _avg(m["solution_constraints"]),
            "solution_quality": _avg(m["solution_quality"]),
            "solution_novelty": _avg(m["solution_novelty"]),
            "solution_composite": _avg(m["solution_composite"]),
            "basin_escape": _avg(m["basin_escape"]),
            "strategies": dict(m["strategies"]),
        })
    models.sort(key=lambda x: -(x["lines_added"]))

    return {
        "models": models,
        "stories_analyzed": n_analysis,
        "commits_analyzed": n_commits,
        "sonar_commits_available": n_sonar_available,
    }


def _load_labs() -> dict:
    """Load the story-era lab book outputs for the evidence page.

    Each lab writes experiments/results/lab_<name>.json. Absent labs are skipped
    so build_data never hard-fails on a missing analysis artifact.
    """
    lab_names = [
        "verification_frontier", "story_arc", "condition_effects",
        "verification_value", "cache_economics", "quality_frontier",
    ]
    labs = {}
    results_dir = ROOT / "experiments" / "results"
    for name in lab_names:
        p = results_dir / f"lab_{name}.json"
        if not p.exists():
            continue
        try:
            labs[name] = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
    return labs


def _short_model_label(model_id: str) -> str:
    mapping = {
        "deepseek-v4-pro": "DeepSeek v4 Pro",
        "gpt-5.6-luna": "GPT-5.6 Luna",
        "claude-sonnet-5": "Claude Sonnet 5",
        "deepseek-v4-flash": "DeepSeek v4 Flash",
        "claude-fable-5": "Claude Fable 5",
    }
    if model_id in mapping:
        return mapping[model_id]
    for full, label in MODEL_LABELS.items():
        if model_id in full:
            return label
    return model_id


def _load_story_data() -> dict:
    """Load story pipeline data from parquet for the website."""
    sessions_path = DATA_DIR / "sessions.parquet"
    stories_path = DATA_DIR / "stories.parquet"

    if not sessions_path.exists() or not stories_path.exists():
        return {"_note": "Run scripts/sync_data.py first"}

    import duckdb
    conn = duckdb.connect()

    sessions_table = f"read_parquet('{sessions_path}')"
    stories_table = f"read_parquet('{stories_path}')"

    # Per-model aggregates
    models = []
    for row in conn.execute(f"""
        SELECT model, count(*) as cells, round(sum(total_cost), 6) as total_cost,
               round(avg(total_cost), 6) as avg_cost, sum(total_tokens) as total_tokens,
               round(avg(cache_hit_rate), 3) as avg_cache_hit,
               round(avg(total_duration), 0) as avg_duration_s
        FROM {stories_table} GROUP BY model ORDER BY total_cost
    """).fetchall():
        models.append({
            "model": row[0], "cells": row[1], "total_cost": row[2],
            "avg_cost": row[3], "total_tokens": row[4],
            "avg_cache_hit": row[5], "avg_duration_s": row[6],
        })

    # Condition comparison
    conditions = []
    for row in conn.execute(f"""
        SELECT condition, count(*) as cells, count(distinct story_name||tier||quality) as variants,
               round(sum(total_cost), 6) as total_cost, round(avg(total_cost), 6) as avg_cost,
               cast(sum(case when all_successful then 1 else 0 end) as int) as success,
               cast(sum(case when not all_successful then 1 else 0 end) as int) as fail
        FROM {stories_table} GROUP BY condition ORDER BY condition
    """).fetchall():
        conditions.append({
            "condition": row[0], "cells": row[1], "variants": row[2],
            "total_cost": row[3], "avg_cost": row[4],
            "success": row[5], "fail": row[6],
        })

    # Story type comparison
    stories = []
    for row in conn.execute(f"""
        SELECT story_name, count(*) as cells,
               round(sum(total_cost), 6) as total_cost, round(avg(total_cost), 6) as avg_cost,
               sum(session_count) as sessions,
               round(avg(total_duration), 0) as avg_duration_s,
               round(avg(total_tokens * 1.0 / session_count), 0) as avg_tokens_per_session
        FROM {stories_table} GROUP BY story_name ORDER BY total_cost
    """).fetchall():
        stories.append({
            "story": row[0], "cells": row[1], "total_cost": row[2],
            "avg_cost": row[3], "sessions": row[4],
            "avg_duration_s": row[5], "avg_tokens_per_session": row[6],
        })

    # Per-session stats
    session_stats = list(conn.execute(f"""
        SELECT count(*) as total, sum(cost_usd) as total_cost,
               sum(total_tokens) as total_tokens,
               sum(cache_read_tokens) as total_cache_reads,
               coalesce(sum(cache_read_tokens) * 1.0 / nullif(sum(cache_read_tokens) + sum(prompt_tokens), 0), 0)
                   as cache_hit_rate,
               sum(duration_s) as duration_s,
               sum(case when exit_code = 0 then 1 else 0 end) as successful,
               sum(case when exit_code != 0 then 1 else 0 end) as failed
        FROM {sessions_table}
    """).fetchone())

    # Tier comparison
    tiers = []
    for row in conn.execute(f"""
        SELECT tier, quality, count(*) as cells, round(avg(total_cost), 6) as avg_cost,
               round(avg(total_tokens * 1.0 / session_count), 0) as avg_tokens_per_session,
               round(avg(total_duration / session_count), 0) as avg_session_duration_s
        FROM {stories_table} GROUP BY tier, quality ORDER BY tier, quality
    """).fetchall():
        tiers.append({
            "tier": row[0], "quality": row[1], "cells": row[2],
            "avg_cost": row[3], "avg_tokens_per_session": row[4],
            "avg_session_duration_s": row[5],
        })

    conn.close()

    return {
        "_provenance": "[M] token counts from session.jsonl; cost from opencode DB verified",
        "models": models,
        "conditions": conditions,
        "stories": stories,
        "tiers": tiers,
        "sessions": {
            "total": session_stats[0], "total_cost": session_stats[1],
            "total_tokens": session_stats[2], "total_cache_reads": session_stats[3],
            "cache_hit_rate": round(session_stats[4], 3), "duration_s": session_stats[5],
            "successful": session_stats[6], "failed": session_stats[7],
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _honest_pass_rate(passed: int, run: int) -> str:
    """Honest pass-rate string. Never fabricates 100% from unmeasured data."""
    if run <= 0:
        return "unknown"
    return f"{passed / run:.0%} ({passed}/{run})"


def _merge_story_strategy(story_models: list[dict], analysis_data: dict) -> None:
    """Attach real strategy-archetype counts to story models.

    compute_story_models cannot source strategy (it lives in the deep-metrics
    analysis), so merge it here instead of fabricating zeros.
    """
    strat_by_model = {
        m["model"]: m.get("strategies", {})
        for m in analysis_data.get("models", [])
    }
    for sm in story_models:
        strat = strat_by_model.get(sm["id"].split("/")[-1], {})
        sm["strategy_cons"] = strat.get("conservative", 0)
        sm["strategy_expl"] = strat.get("exploratory", 0)
        sm["strategy_waste"] = strat.get("wasteful", 0)
        sm["strategy_efficient"] = strat.get("efficient", 0)


def compute_story_models() -> list[dict]:
    """Build the model comparison from stories.parquet (source of truth)."""
    stories_path = DATA_DIR / "stories.parquet"
    sessions_path = DATA_DIR / "sessions.parquet"
    if not stories_path.exists():
        return []

    import duckdb
    conn = duckdb.connect()

    # Real test pass/fail + token splits per model, from the session transcripts.
    test_by_model = {}
    if sessions_path.exists():
        for r in conn.execute(f"""
            SELECT model, sum(tests_passed) as passed, sum(tests_total) as run,
                   sum(prompt_tokens) as prompt, sum(completion_tokens) as completion,
                   sum(reasoning_tokens) as reasoning
            FROM read_parquet('{sessions_path}')
            GROUP BY model
        """).fetchall():
            test_by_model[r[0]] = {
                "passed": int(r[1] or 0), "run": int(r[2] or 0),
                "prompt": int(r[3] or 0), "completion": int(r[4] or 0),
                "reasoning": int(r[5] or 0),
            }

    models = []
    for row in conn.execute(f"""
        SELECT model, count(*) as total_runs,
               count(distinct cell_key) as unique_cells,
               sum(session_count) as sessions,
               round(sum(total_cost), 6) as total_cost,
               round(avg(total_cost) FILTER (WHERE cost_captured), 6) as avg_cost,
               sum(case when cost_captured then 1 else 0 end) as cost_cells,
               round(avg(cache_hit_rate), 3) as avg_cache_hit,
               round(avg(test_count), 1) as avg_tests,
               round(avg(test_code_ratio), 3) as avg_test_code_ratio,
               round(avg(total_tokens * 1.0 / session_count), 0) as avg_tok_per_session,
               round(avg(total_duration), 0) as avg_duration_s,
               round(avg(code_lines), 0) as avg_code_lines,
               sum(test_count) as total_tests
          FROM read_parquet('{stories_path}')
          GROUP BY model ORDER BY avg_cost
    """).fetchall():
        mid = row[0]
        label = MODEL_LABELS.get(mid, mid)
        total_runs = row[1]
        unique_cells = row[2]
        t = test_by_model.get(mid, {"passed": 0, "run": 0, "prompt": 0, "completion": 0, "reasoning": 0})
        avg_loc = row[12]
        # Energy is a [C]omputed estimate from measured tokens (J per token).
        avg_energy_j = round(
            (t["prompt"] * 0.08 + t["completion"] * 0.23 + t["reasoning"] * 0.47)
            / max(total_runs, 1), 1
        )
        models.append({
            "id": mid,
            "label": label,
            "provider": get_provider(mid),
            "cells": total_runs,
            "unique_cells": unique_cells,
            "re_runs": total_runs - unique_cells,
            "sessions": row[3],
            "total_cost": row[4],
            "avg_cost": row[5],
            "cost_cells": row[6],
            "avg_cache_hit": row[7],
            "avg_tests": row[8],
            "avg_test_code_ratio": row[9],
            "avg_tok_per_session": row[10],
            "avg_duration_s": row[11],
            "avg_code_lines": avg_loc,
            "tests_total": row[13],
            "tests_passed": t["passed"],
            "tests_run": t["run"],
            "pass_rate": _honest_pass_rate(t["passed"], t["run"]),
            # keep legacy keys populated for existing charts
            "avg_cost_per_session": round(row[5] / max(row[3] / max(total_runs, 1), 1), 6),
            "avg_loc": avg_loc,
            "avg_energy_j": avg_energy_j,
            "avg_energy_j_per_loc": round(avg_energy_j / max(avg_loc, 1), 2),
            # Not measured for the story corpus — do not fabricate zeros.
            "narration_rate": None,
            "avg_narration_penalty": None,
            "strategy_cons": 0, "strategy_expl": 0,
            "strategy_waste": 0, "strategy_efficient": 0,
            "reports": total_runs, "reports_valid": total_runs, "reports_narrated": 0,
        })

    conn.close()
    return models


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
    perturbation_models = models  # preserve real perturbation metrics (energy/strategy/narration)
    print(f"  Computed: {len(models)} models")

    # Story pipeline models are the source of truth for cross-model comparison.
    # The perturbation models are preserved under a separate key — never discarded.
    story_models = compute_story_models()
    analysis_data = _load_analysis_data()
    if story_models:
        _merge_story_strategy(story_models, analysis_data)
        models = story_models
        print(f"  Story models: {len(models)} (from stories.parquet)")

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

    # ── Perturbation class breakdown — specification / objective / process vs baseline ──
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
                "cost_ci95": bootstrap_ci(pb["costs"]) if n >= 5 else None,
                "avg_escape": round(sum(pb["escapes"]) / n, 2),
                "escape_ci95": bootstrap_ci(pb["escapes"]) if n >= 5 else None,
                "avg_correctness": round(sum(pb["correctness"]) / n, 2),
                "correctness_ci95": bootstrap_ci(pb["correctness"]) if n >= 5 else None,
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
    inventory.get("costs", {})

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
            "sessions_total": sum(m.get("sessions", 0) for m in models),
            "game_reports": report_count,
            "total_cost": _fmt_usd(sum(m.get("total_cost", 0) for m in models)),
            "architectures": 3,
            "variants": len(story_models) if story_models else 8,
            "stories_total": sum(m.get("cells", 0) for m in models),
            "stories_unique": sum(m.get("unique_cells", 0) for m in models),
            "stories_re_runs": sum(m.get("re_runs", 0) for m in models),
            "story_sessions": sum(m.get("sessions", 0) for m in models),
            "story_total_cost": _fmt_usd(sum(m.get("total_cost", 0) for m in models)),
            "configs": counts.get("config_files", 0),
            "_provenance": {
                "worktrees_total": "M", "sessions_total": "M", "game_reports": "M",
                "total_cost": "M", "architectures": "M", "variants": "M",
                "stories_total": "C", "stories_unique": "C", "stories_re_runs": "C",
                "story_sessions": "C", "story_total_cost": "C",
                "configs": "M",
            },
        },
        "models": models,
        "perturbation_models": perturbation_models,
        "charts": charts,
        "calculator": calculator,
        "derived": derived,
        "operator_comparison": op_comparison,
        "perturbation_class_breakdown": pert_class_summary,
        "energy_ranking": energy_ranking,
        "strategy_distribution": summary.get("strategy_distribution", {}),
        "routing": compute_routing(entries),
        "grit_matrix": _load_grit_matrix(),
        "sonar": _compute_sonar(entries),
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
                **COMPOSITE_WEIGHTS,
                "provenance": "design",
            },
        },
        "external_sources": {
            "epm_baseline": {"value": "1.6%/yr", "provenance": "X", "source": "IEA World Energy Outlook 2024"},
            "epm_aggressive": {"value": "2.5%/yr", "provenance": "X", "source": "Aggressive scenario"},
            "energy_per_token_prompt": {"value": 0.08, "unit": "J", "provenance": "X", "source": "TokenPowerBench (Niu et al., AAAI 2026)"},
            "energy_per_token_output": {"value": 0.23, "unit": "J", "provenance": "X", "source": "TokenPowerBench (Niu et al., AAAI 2026)"},
            "energy_per_token_reasoning": {"value": 0.47, "unit": "J", "provenance": "X", "source": "TokenPowerBench (Niu et al., AAAI 2026)"},
            "energy_model_available": {"value": False, "provenance": "X", "note": "Claude/GPT architecture undisclosed — energy model disabled"},
            "deepseek_active_params": {"value": "49e9", "provenance": "X", "note": "MoE V4 Pro, publicly disclosed (49B active)"},
        },
        "stories": _load_story_data(),
        "reviews": _load_review_data(),
        "analysis": analysis_data,
        "labs": _load_labs(),
    }

    import math
    # Strip NaN values (replace with null) and remove local paths
    def _clean_value(obj):
        if isinstance(obj, float) and math.isnan(obj):
            return None
        if isinstance(obj, dict):
            return {k: _clean_value(v) for k, v in obj.items() if k not in ('source_inventory', 'source_summary', 'source_db')}
        if isinstance(obj, list):
            return [_clean_value(v) for v in obj]
        if isinstance(obj, str):
            return obj.replace(str(ROOT), '.').replace(str(Path.home()), '~')
        return obj
    clean_data = _clean_value(data)

    js = f"/* Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} by build_data.py */\n"
    js += "/* DO NOT EDIT — regenerate with: python scripts/build_data.py */\n"
    js += "window.DYNAMICS_DATA = " + json.dumps(clean_data, indent=2, default=str) + ";\n"

    return js, data


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build data.js for the Agentic Dynamics website")
    parser.add_argument("--dry-run", action="store_true", help="Print instead of writing")
    args = parser.parse_args()

    if not INVENTORY_PATH.exists() and os.environ.get("ALLOW_MISSING_EXPERIMENT_DATA"):
        print(
            "SKIP: experiment inventory not present "
            "(ALLOW_MISSING_EXPERIMENT_DATA set) — exiting without building data.js.",
            file=sys.stderr,
        )
        return

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
