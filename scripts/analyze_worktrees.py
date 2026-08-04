#!/usr/bin/env python3
"""Post-hoc analysis of experiment worktrees — generate Game Reports from existing sessions.

Problem: 95% of experiment sessions were run via batch/sweep scripts that only collected
raw cost/token data from the opencode DB. They never ran the analysis pipeline (solution
evaluation, basin escape, strategy classification, game reports).

This script fills that gap. It takes existing worktree directories, reads the generated
code, runs the full analysis stack, and produces GameReport markdown files.

Usage:
  python scripts/analyze_worktrees.py                    # analyze all experiment worktrees
  python scripts/analyze_worktrees.py --worktree /tmp/exp_xyz  # analyze one worktree
  python scripts/analyze_worktrees.py --limit 5           # analyze first 5
  python scripts/analyze_worktrees.py --dry-run            # show what would be analyzed
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from instrument import (
    evaluate_solution, compute_efficiency, measure_basin_escape,
    classify_strategy, GameReport, SolutionMetrics, EfficiencyMetrics, BasinMetrics,
    StrategyReport,
)

OPENSCODE_DB = Path.home() / ".local/share/opencode/opencode.db"
RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"
REPORTS_DIR = RESULTS_DIR / "reports"
CONFIGS_DIR = PROJECT_ROOT / "experiments" / "configs"


# ── Utility ──────────────────────────────────────────────────────────────────

def _fmt_usd(v): return f"${v:,.4f}" if v is not None else "—"
def _fmt_int(v): return f"{v:,}" if v is not None else "—"


def _now(): return datetime.now(timezone.utc).isoformat()


# ── Data Loading ─────────────────────────────────────────────────────────────

def load_db_sessions():
    """Load all sessions with cost data from the opencode DB."""
    if not OPENSCODE_DB.exists():
        print("Error: opencode DB not found at", OPENSCODE_DB)
        return []
    db = sqlite3.connect(str(OPENSCODE_DB))
    db.row_factory = sqlite3.Row
    rows = db.execute("""
        SELECT id, directory, title, cost, tokens_input, tokens_output, tokens_reasoning,
               tokens_cache_read, tokens_cache_write,
               json_extract(model, '$.providerID') as provider,
               json_extract(model, '$.id') as model_id,
               time_created
        FROM session WHERE cost > 0 OR tokens_output > 0
        ORDER BY time_created
    """).fetchall()
    db.close()
    return {s["directory"]: dict(s) for s in rows if s["directory"]}


def load_config_constraints(config_name: str) -> list[str]:
    """Load constraints from a YAML config file."""
    config_path = CONFIGS_DIR / config_name
    if not config_path.exists():
        return []
    try:
        import yaml
        with open(config_path) as f:
            data = yaml.safe_load(f)
        return data.get("constraints", [])
    except Exception:
        return []


def read_worktree_code(worktree_path: str) -> str:
    """Concatenate project .py files in a worktree (skip venv, site-packages, tests)."""
    p = Path(worktree_path)
    if not p.exists():
        return ""
    code_parts = []
    skip_dirs = {"__pycache__", ".git", "venv", ".venv", "env", "site-packages",
                 "node_modules", ".mypy_cache", ".pytest_cache", "dist", "build",
                 "Lib", "lib", "include"}
    for f in sorted(p.rglob("*.py")):
        parts = set(f.parts)
        if parts & skip_dirs:
            continue
        try:
            content = f.read_text(errors="replace")
            if content.strip() and len(content) > 20:
                rel = f.relative_to(p)
                code_parts.append(f"# {rel}\n{content}")
        except Exception:
            pass
        if len(code_parts) > 200:  # safety cap: don't read 1000+ files
            break
    return "\n\n".join(code_parts)


DEFAULT_CONSTRAINTS = [
    "JWT auth with refresh tokens",
    "Rate limiting on login endpoint",
    "Input validation on all endpoints",
    "Paginated list responses",
    "Error handling with proper HTTP status codes",
    "Audit logging of mutations",
    "API versioning via URL prefix",
]


def infer_constraints(worktree_path: str, title: str = "") -> list[str]:
    """Infer constraints from worktree contents or session title."""
    constraints = DEFAULT_CONSTRAINTS.copy()

    t = (title or worktree_path).lower()
    if "url_shortener" in t or "url shortener" in t:
        constraints = [
            "REST API with CRUD endpoints",
            "URL shortening with hash generation",
            "Redirect handling",
            "Analytics/stats tracking",
            "Rate limiting",
            "Input validation",
        ]
    elif "data_table" in t or "data table" in t:
        constraints = [
            "Sortable data table component",
            "Pagination with page/limit controls",
            "Filter/search functionality",
            "Responsive design",
        ]
    elif "collaborat" in t or "editor" in t:
        constraints = [
            "Real-time collaborative editing",
            "Conflict resolution / OT",
            "User presence tracking",
            "Auto-save and persistence",
        ]

    return constraints


def parse_session_title_info(title: str) -> dict:
    """Extract experiment and model metadata from session title.
    
    Returns: {experiment, operator, silent_mode, model_short}
    """
    info = {"experiment": "", "operator": "baseline", "silent_mode": "natural",
            "model_short": ""}
    t = title or ""

    bracket_tags = re.findall(r'\[([^\]]+)\]', t)
    if bracket_tags:
        first_tag = bracket_tags[0]
        parts = first_tag.split(":")

        if len(parts) == 1:
            tag = parts[0]
            if "baseline" in tag:
                info["operator"] = "baseline"
            elif any(k in tag for k in ["inject_", "remove_", "invert_", "shift_",
                                          "alien_", "false_", "competing", "phantom",
                                          "force_", "reverse_", "probe", "std_",
                                          "standardized", "perturbed"]):
                info["operator"] = "perturbed"
                info["experiment"] = tag
        elif len(parts) >= 2:
            info["experiment"] = parts[1]
            if len(parts) >= 3:
                info["operator"] = parts[2] if parts[2] in ("baseline", "perturbed") else "baseline"
            if "forced" in first_tag:
                info["silent_mode"] = "forced-silent"
            elif "natural" in first_tag:
                info["silent_mode"] = "natural"

    after_brackets = re.sub(r'\[[^\]]+\]\s*', '', t).strip()
    info["model_short"] = after_brackets

    if not info["experiment"]:
        for pattern, exp_name in [
            ("task_manage", "task_manager"), ("task manager", "task_manager"),
            ("task api", "task_manager"), ("collaborative", "collaborative_editor"),
            ("data_table", "data_table"), ("data table", "data_table"),
            ("url_shortener", "url_shortener"), ("url shortener", "url_shortener"),
            ("silent_sweep", "silent_sweep"),
        ]:
            if pattern in t.lower():
                info["experiment"] = exp_name
                break

    return info


# ── Analysis ─────────────────────────────────────────────────────────────────

def analyze_worktree(worktree_path: str, session: dict = None, baseline_code: str = "",
                     config_name: str = ""):
    """Run the full analysis pipeline on a single worktree.

    Returns:
        (GameReport, dict of metrics) or (None, error_dict)
    """
    wt = Path(worktree_path)
    if not wt.exists():
        return None, {"error": "worktree not found"}

    # Read code
    code = read_worktree_code(worktree_path)
    if not code:
        return None, {"error": "no Python files found"}

    # Session metadata
    title = session.get("title", "") if session else ""
    info = parse_session_title_info(title)

    # Constraints
    constraints = infer_constraints(worktree_path, title)
    if config_name:
        config_constraints = load_config_constraints(config_name)
        if config_constraints:
            constraints = config_constraints

    # ── Solution Evaluation ──
    solution = evaluate_solution(code, constraints, baseline_code=baseline_code)

    # ── Efficiency ──
    prompt_tok = session.get("tokens_input", 0) or 0 if session else 0
    completion_tok = session.get("tokens_output", 0) or 0 if session else 0
    reasoning_tok = session.get("tokens_reasoning", 0) or 0 if session else 0
    total_tok = prompt_tok + completion_tok + reasoning_tok

    # Use DB cost if available, otherwise estimate
    db_cost = session.get("cost", 0) or 0 if session else 0
    efficiency = compute_efficiency(
        prompt_tokens=prompt_tok, completion_tokens=completion_tok,
        reasoning_tokens=reasoning_tok, total_tokens=total_tok,
        solution=solution,
    )
    if db_cost > 0:
        efficiency.total_cost_usd = db_cost

    # ── Basin Escape ──
    pert_class = "manifold" if any(k in info.get("operator", "") for k in
                                   ["alien_vocab", "shift_framing", "reverse_causality",
                                    "force_abandonment"]) else "semantic"
    basin = measure_basin_escape(
        baseline_code=baseline_code or code,  # self-comparison if no baseline
        perturbed_code=code,
        baseline_correctness=solution.correctness_score,
        perturbed_correctness=solution.correctness_score,
        baseline_constraints_met=solution.constraints_met,
        perturbed_constraints_met=solution.constraints_met,
        baseline_loc=solution.lines_of_code,
        perturbed_loc=solution.lines_of_code,
        prompt_tokens=prompt_tok,
        completion_tokens=completion_tok,
        reasoning_tokens=reasoning_tok,
        perturbation_operator=info.get("operator", "baseline"),
        perturbation_class=pert_class,
        perturbation_strength=0.5,
        model=session.get("model_id", "") if session else "",
    )

    # ── Strategy ──
    strategy = classify_strategy(basin, solution, efficiency, pert_class)

    # ── Game Report ──
    experiment_id = info.get("experiment", wt.name) or wt.name
    report = GameReport(
        experiment_id=f"{experiment_id}-{info.get('operator', '?')}",
        model=str(session.get("provider", "") or "") + "/" + str(session.get("model_id", "") or "")
               if session and (session.get("provider") or session.get("model_id")) else wt.name,
        task=title[:200] if title else str(wt.name),
        operator=info.get("operator", "baseline"),
        perturbation_class=pert_class,
        reasoning=basin, solution=solution, efficiency=efficiency,
        strategy=strategy,
    )

    return report, {
        "experiment": experiment_id,
        "operator": info["operator"],
        "silent_mode": info["silent_mode"],
        "code_lines": solution.lines_of_code,
        "cost": efficiency.total_cost_usd,
        "tokens": total_tok,
        "thinking_ratio": efficiency.thinking_ratio,
        "correctness": solution.correctness_score,
        "constraints": f"{solution.constraints_met}/{solution.constraints_total}",
        "escape": basin.escape_score,
        "strategy": strategy.strategy.value if strategy else "?",
    }


# ── Worktree Discovery ───────────────────────────────────────────────────────

def discover_worktrees(sessions_by_dir: dict) -> list[dict]:
    """Discover experiment worktrees and match to DB sessions."""
    import glob
    worktrees = []
    for path in sorted(glob.glob("/tmp/exp_*")):
        wt = {"path": path, "name": Path(path).name}
        if path in sessions_by_dir:
            wt["session"] = sessions_by_dir[path]
        worktrees.append(wt)
    return worktrees


def build_baseline_index(worktrees: list[dict]) -> dict:
    """Index baselines by (experiment|model_short) -> code."""
    index = {}
    for wt in worktrees:
        s = wt.get("session", {})
        title = s.get("title", "") or ""
        info = parse_session_title_info(title)
        if info["operator"] != "baseline":
            continue
        exp = info["experiment"]; ms = info["model_short"]
        prov = s.get("provider", ""); mid = s.get("model_id", "")
        keys = []
        if exp and ms: keys.append(f"{exp}|{ms}")
        if exp and prov and mid: keys.append(f"{exp}|{prov}/{mid}")
        for key in keys:
            if key not in index:
                code = read_worktree_code(wt["path"])
                if code: index[key] = code
    return index


def find_baseline_code(worktree_title: str, session: dict,
                       baseline_index: dict) -> str:
    """Find matching baseline code for a worktree using the index.
    
    Tries exact experiment+model match first, then falls back to
    same-model matching (useful when perturbed worktrees use operator
    names as experiment IDs).
    """
    info = parse_session_title_info(worktree_title)
    if info["operator"] == "baseline":
        return ""

    ms = info["model_short"]; exp = info["experiment"]
    prov = session.get("provider", ""); mid = session.get("model_id", "")

    if exp and ms:
        code = baseline_index.get(f"{exp}|{ms}")
        if code: return code
    if exp and prov and mid:
        code = baseline_index.get(f"{exp}|{prov}/{mid}")
        if code: return code

    # Fuzzy: partial model_short overlap within same experiment
    if exp and ms:
        ms_words = set(ms.lower().replace("_", " ").split())
        for key, code in baseline_index.items():
            key_exp, key_ms = key.split("|", 1)
            if key_exp == exp:
                kw = set(key_ms.lower().replace("_", " ").split())
                if ms_words & kw: return code
                if ms.lower() in key_ms.lower() or key_ms.lower() in ms.lower():
                    return code

    # Fallback: any baseline for the same model provider/ID
    if prov and mid:
        key = f"{prov}/{mid}"
        for bk, code in baseline_index.items():
            if key in bk:
                return code
    if prov:
        for bk, code in baseline_index.items():
            if prov in bk:
                return code

    return ""


def find_baseline_worktree(worktrees: list[dict], experiment: str) -> str:
    """Find a baseline worktree for the given experiment name."""
    baselines = [wt for wt in worktrees
                 if experiment in (wt.get("session", {}).get("title", "") or "").lower()
                 and "baseline" in (wt.get("session", {}).get("title", "") or "").lower()]
    if baselines:
        return read_worktree_code(baselines[0]["path"])
    return ""


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Post-hoc analysis of experiment worktrees")
    ap.add_argument("--worktree", help="Analyze a single worktree path")
    ap.add_argument("--limit", type=int, default=0, help="Max worktrees to analyze")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be analyzed")
    ap.add_argument("--baseline", help="Baseline worktree path for comparison")
    args = ap.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load sessions from DB
    print("Loading session data from opencode DB...")
    sessions_by_dir = load_db_sessions()
    print(f"  {len(sessions_by_dir)} sessions with directory paths")

    if args.worktree:
        worktrees = [{"path": args.worktree, "name": Path(args.worktree).name,
                       "session": sessions_by_dir.get(args.worktree)}]
    else:
        print("Discovering worktrees...")
        worktrees = discover_worktrees(sessions_by_dir)
        print(f"  {len(worktrees)} worktrees found")

    # Filter to only ones with sessions and experiment-like titles
    exp_wts = [wt for wt in worktrees if wt.get("session")]
    EXP_PATTERNS = ["flask", "api", "rest", "task", "url", "sweep", "batch", "config",
                     "silent", "constraint", "recovery", "baseline", "perturb", "inject",
                     "phantom", "remove_critical", "invert", "shift_framing", "alien",
                     "false_premise", "competing", "data_table", "collaborat"]

    analyzed = [wt for wt in exp_wts if any(
        p in (wt.get("session", {}).get("title", "") or "").lower()
        for p in EXP_PATTERNS
    ) or ((wt.get("session", {}).get("title", "") or "").startswith("["))]
    print(f"  {len(analyzed)} experiment worktrees")

    if args.limit:
        analyzed = analyzed[:args.limit]
        print(f"  limited to {args.limit}")

    if args.dry_run:
        print("\n=== DRY RUN — would analyze these worktrees ===\n")
        for i, wt in enumerate(analyzed):
            s = wt.get("session", {})
            title = (s.get("title", "") or "?")[:70]
            cost = s.get("cost", 0) or 0
            print(f"  {i+1:3d}. {wt['name']:<20} ${cost:>7.4f}  {title}")
        print(f"\n  Total: {len(analyzed)} worktrees")
        return

    # Build baseline index from ALL worktrees (not just the limited subset)
    print("Building baseline index...")
    all_worktrees = discover_worktrees(sessions_by_dir)
    all_with_sessions = [wt for wt in all_worktrees if wt.get("session")]
    baseline_index = build_baseline_index(all_with_sessions)
    print(f"  {len(baseline_index)} baselines indexed")

    # Analyze each worktree
    results = []

    print(f"\n{'='*100}")
    print(f"ANALYZING {len(analyzed)} WORKTREES")
    print(f"{'='*100}\n")

    for i, wt in enumerate(analyzed):
        s = wt.get("session", {})
        title = (s.get("title", "") or "")[:60]

        # Find matching baseline via smart index
        baseline_code = find_baseline_code(title, s, baseline_index)
        if args.baseline and not baseline_code:
            baseline_code = read_worktree_code(args.baseline)

        report, metrics = analyze_worktree(wt["path"], s, baseline_code=baseline_code)

        if report:
            # Save markdown report
            safe_name = wt["name"].replace("/", "_")[:60]
            md_path = REPORTS_DIR / f"{safe_name}.md"
            md_path.write_text(report.to_markdown())

            results.append(metrics)

            strat_icon = {"conservative": "C", "exploratory": "E",
                          "wasteful": "W", "efficient": "✓"}.get(
                (metrics.get("strategy") or "").lower()[:1], "?")
            print(f"  {i+1:3d}/{len(analyzed)} {strat_icon} {wt['name']:<18} "
                  f"${metrics['cost']:>7.4f} cor={metrics['correctness']:.0%} "
                  f"esc={metrics['escape']:.2f} [{metrics['constraints']}] "
                  f"→ {safe_name}.md")
        else:
            err = metrics.get("error", "unknown")
            if args.worktree:
                print(f"  Error: {err}")
            else:
                pass  # quiet for batch

    # Summary
    if results:
        print(f"\n{'='*100}")
        print(f"SUMMARY — {len(results)} reports generated")
        print(f"{'='*100}")

        total_cost = sum(r["cost"] for r in results)
        avg_correct = sum(r["correctness"] for r in results) / len(results)
        avg_escape = sum(r["escape"] for r in results) / len(results)
        strategies = {}
        for r in results:
            s = r.get("strategy", "?")
            strategies[s] = strategies.get(s, 0) + 1

        print(f"  Total cost analyzed: {_fmt_usd(total_cost)}")
        print(f"  Avg correctness:     {avg_correct:.1%}")
        print(f"  Avg escape score:    {avg_escape:.2f}")
        print(f"  Strategy breakdown:  {strategies}")
        print(f"\n  Reports saved to: {REPORTS_DIR}/")
    else:
        print("\nNo worktrees analyzed.")


if __name__ == "__main__":
    main()
