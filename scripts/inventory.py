#!/usr/bin/env python3
"""Experiment/Worktree Inventory Registry.

A persistent inventory of all experiments, worktrees, and opencode sessions.
Rebuild with `refresh`, then query instantly with `list`, `stats`, `worktrees`, `report`.

Sources: opencode.db SQLite, /tmp/exp_* worktrees, experiments/results/*.json, experiments/configs/*.yaml
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INVENTORY_PATH = PROJECT_ROOT / "experiments" / "inventory.json"
OPENSCODE_DB = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"
CONFIGS_DIR = PROJECT_ROOT / "experiments" / "configs"
WORKTREE_GLOB = "/tmp/exp_*"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _fmt_usd(v):
    if v is None:
        return "—"
    return f"${v:,.2f}"


def _fmt_int(v):
    if v is None:
        return "—"
    return f"{v:,}"


from _constants import EXPERIMENT_SESSION_PATTERNS


def _is_experiment_title(title: str) -> bool:
    """Classify a session title as experiment or non-experiment."""
    t = (title or "").lower()
    if not t:
        return False
    if t.startswith("["):
        return True
    return any(k in t for k in EXPERIMENT_SESSION_PATTERNS)


def refresh():
    """Rebuild the inventory from all data sources."""
    print("Scanning opencode DB ...")
    db_sessions = _scan_db()

    print(f"  {len(db_sessions)} sessions found")

    print("Scanning worktrees ...")
    worktrees = _scan_worktrees()

    print(f"  {len(worktrees)} worktrees found")

    print("Scanning result JSONs ...")
    results = _scan_results()

    print(f"  {len(results)} result files found")

    print("Scanning config YAMLs ...")
    configs = _scan_configs()

    print(f"  {len(configs)} config files found")

    # Match sessions to worktrees via directory path
    session_by_dir = {}
    for s in db_sessions:
        d = s.get("directory", "")
        if d:
            session_by_dir[d] = s

    # Classify sessions as experiment or non-experiment
    exp_sessions = [s for s in db_sessions if _is_experiment_title(s.get("title") or "")]
    other_sessions = [s for s in db_sessions if s not in exp_sessions]

    # Classify worktrees
    exp_worktrees = []
    other_worktrees = []
    for wt in worktrees:
        wt_path = wt["path"]
        if wt_path in session_by_dir:
            s = session_by_dir[wt_path]
            if _is_experiment_title(s.get("title") or ""):
                exp_worktrees.append({**wt, "session": s})
            else:
                other_worktrees.append({**wt, "session": s})
        else:
            other_worktrees.append(wt)

    # Aggregate costs
    total_cost_all = sum(s.get("cost") or 0 for s in db_sessions)
    total_cost_exp = sum(s.get("cost") or 0 for s in exp_sessions)
    total_tokens_all = sum((s.get("tokens_input") or 0) + (s.get("tokens_output") or 0)
                           + (s.get("tokens_reasoning") or 0) for s in db_sessions)
    total_tokens_exp = sum((s.get("tokens_input") or 0) + (s.get("tokens_output") or 0)
                           + (s.get("tokens_reasoning") or 0) for s in exp_sessions)

    # Model breakdown
    model_counts = {}
    for s in exp_sessions:
        prov = (s.get("provider") or "unknown")
        mid = (s.get("model_id") or "unknown")
        key = f"{prov}/{mid}"
        if key not in model_counts:
            model_counts[key] = {"sessions": 0, "cost": 0.0, "tokens": 0}
        model_counts[key]["sessions"] += 1
        model_counts[key]["cost"] += s.get("cost") or 0
        model_counts[key]["tokens"] += (s.get("tokens_input") or 0) + (
            s.get("tokens_output") or 0) + (s.get("tokens_reasoning") or 0)

    inventory = {
        "generated_at": _now(),
        "counts": {
            "db_sessions_total": len(db_sessions),
            "db_sessions_experiments": len(exp_sessions),
            "worktrees_total": len(worktrees),
            "worktrees_experiments": len(exp_worktrees),
            "worktrees_other": len(other_worktrees),
            "result_files": len(results),
            "config_files": len(configs),
        },
        "costs": {
            "total_all_sessions": round(total_cost_all, 4),
            "total_experiment_sessions": round(total_cost_exp, 4),
            "tokens_all_sessions": total_tokens_all,
            "tokens_experiment_sessions": total_tokens_exp,
        },
        "model_breakdown": {
            k: {"sessions": v["sessions"], "cost": round(v["cost"], 4),
                "tokens": v["tokens"]}
            for k, v in sorted(model_counts.items(), key=lambda x: -x[1]["cost"])
        },
        "results": results,
        "configs": configs,
        "experiment_worktrees": exp_worktrees,
        "other_worktrees": other_worktrees,
        "experiment_session_titles": [
            {"title": s["title"], "provider": s["provider"], "model_id": s["model_id"],
             "cost": s["cost"], "tokens_output": s["tokens_output"]}
            for s in sorted(exp_sessions, key=lambda x: x.get("time_created") or "")
        ],
    }

    INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INVENTORY_PATH, "w") as f:
        json.dump(inventory, f, indent=2)

    print(f"\nInventory written to {INVENTORY_PATH}")
    print(f"  {len(exp_sessions)} experiment sessions")
    print(f"  {len(exp_worktrees)} experiment worktrees")
    print(f"  {len(other_worktrees)} non-experiment worktrees")
    print(f"  Total experiment cost: {_fmt_usd(total_cost_exp)}")
    return inventory


def _scan_db():
    if not OPENSCODE_DB.exists():
        print("  Warning: opencode db not found at", OPENSCODE_DB)
        return []
    db = sqlite3.connect(str(OPENSCODE_DB))
    db.row_factory = sqlite3.Row
    rows = db.execute("""
        SELECT id, directory, title, cost, tokens_input, tokens_output, tokens_reasoning,
               tokens_cache_read, tokens_cache_write,
               json_extract(model, '$.providerID') as provider,
               json_extract(model, '$.id') as model_id,
               time_created, time_updated
        FROM session WHERE cost > 0 OR tokens_output > 0
        ORDER BY time_created
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]


def _scan_worktrees():
    import glob
    wts = []
    for path in sorted(glob.glob(WORKTREE_GLOB)):
        p = Path(path)
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()
        files = list(p.rglob("*"))
        py_files = [f for f in files if f.suffix == ".py" and f.is_file()]
        wts.append({
            "path": path,
            "name": p.name,
            "mtime": mtime,
            "total_files": len([f for f in files if f.is_file()]),
            "py_files": len(py_files),
        })
    return wts


def _scan_results():
    results = []
    if not RESULTS_DIR.exists():
        return results
    for f in sorted(RESULTS_DIR.glob("*.json")):
        if f.name == "inventory.json":
            continue
        try:
            with open(f) as fh:
                data = json.load(fh)
            runs = data.get("runs", [])
            total_cost = sum(r.get("cost_usd", 0) or 0 for r in runs)
            results.append({
                "file": str(f.relative_to(PROJECT_ROOT)),
                "experiment": data.get("experiment"),
                "model": data.get("model"),
                "num_runs": len(runs),
                "total_cost": round(total_cost, 4),
                "operators": list(set(r.get("operator", "") for r in runs)),
            })
        except Exception as e:
            results.append({"file": str(f.relative_to(PROJECT_ROOT)), "error": str(e)})
    return results


def _scan_configs():
    configs = []
    if not CONFIGS_DIR.exists():
        return configs
    for f in sorted(CONFIGS_DIR.glob("*.yaml")):
        try:
            import yaml
            with open(f) as fh:
                data = yaml.safe_load(fh)
            configs.append({
                "file": str(f.relative_to(PROJECT_ROOT)),
                "name": data.get("name"),
                "model": data.get("model"),
                "task_preview": (data.get("task") or "")[:120] + "..." if len(data.get("task") or "") > 120 else data.get("task"),
                "constraints": len(data.get("constraints") or []),
                "operators": data.get("operators") or [],
            })
        except Exception:
            configs.append({"file": str(f.relative_to(PROJECT_ROOT)), "error": "parse failure"})
    return configs


def _load_inventory():
    if not INVENTORY_PATH.exists():
        print("No inventory found. Run `python scripts/inventory.py refresh` first.")
        sys.exit(1)
    with open(INVENTORY_PATH) as f:
        return json.load(f)


def cmd_list(args):
    inv = _load_inventory()
    print(f"\nInventory from {inv['generated_at']}\n")
    c = inv["counts"]
    print(f"  {c['db_sessions_total']} total DB sessions  →  {c['db_sessions_experiments']} experiment sessions")
    print(f"  {c['worktrees_total']} worktrees on disk    →  {c['worktrees_experiments']} experiment worktrees")
    print(f"  {c['worktrees_other']} non-experiment worktrees")
    print(f"  {c['result_files']} result JSON files")
    print(f"  {c['config_files']} config YAML files")
    print()

    # Model breakdown
    print(f"{'Model':<35} {'Sessions':>8} {'Cost':>12}  {'Tokens':>10}")
    print("-" * 70)
    for key, v in inv["model_breakdown"].items():
        print(f"  {key:<33} {v['sessions']:>8}  {_fmt_usd(v['cost']):>10}  {_fmt_int(v['tokens']):>10}")
    print("-" * 70)
    total_sessions = sum(v["sessions"] for v in inv["model_breakdown"].values())
    total_cost = sum(v["cost"] for v in inv["model_breakdown"].values())
    total_tokens = sum(v["tokens"] for v in inv["model_breakdown"].values())
    print(f"  {'TOTAL':<33} {total_sessions:>8}  {_fmt_usd(total_cost):>10}  {_fmt_int(total_tokens):>10}")

    if args.verbose:
        print("\nExperiment Sessions:")
        print(f"  {'Title':<60} {'Provider':<15} {'Cost':>10}")
        print("  " + "-" * 88)
        for s in inv.get("experiment_session_titles", []):
            title = (s["title"] or "")[:58]
            print(f"  {title:<60} {(s['provider'] or '')[:13]:<15} {_fmt_usd(s['cost']):>10}")


def cmd_stats(args):
    inv = _load_inventory()
    c = inv["counts"]
    co = inv["costs"]

    print()
    print(f"  Worktrees:  {c['worktrees_total']} total")
    print(f"    Experiment:  {c['worktrees_experiments']}")
    print(f"    Other:       {c['worktrees_other']}")
    print(f"  DB Sessions: {c['db_sessions_total']} total  ({c['db_sessions_experiments']} experiments)")
    print(f"  Configs:     {c['config_files']}")
    print(f"  Results:     {c['result_files']}")
    print(f"  Total cost:  {_fmt_usd(co['total_all_sessions'])} (all), "
          f"{_fmt_usd(co['total_experiment_sessions'])} (experiments only)")
    print()


def cmd_worktrees(args):
    inv = _load_inventory()
    exp_wts = inv.get("experiment_worktrees", [])
    other_wts = inv.get("other_worktrees", [])

    if not args.all:
        print(f"\n  {len(other_wts)} non-experiment worktrees:")
        for wt in other_wts:
            s = wt.get("session", {})
            title = (s.get("title") or "no opencode session")[:60]
            print(f"    {wt['name']}  —  {title}")
        print(f"\n  {len(exp_wts)} experiment worktrees (use --all to show)")
    else:
        print(f"\n  {len(exp_wts)} experiment worktrees:")
        for wt in exp_wts:
            s = wt.get("session", {})
            title = (s.get("title") or "?")[:50]
            print(f"    {wt['name']}  cost={_fmt_usd(s.get('cost'))}  {title}")
        print(f"\n  {len(other_wts)} non-experiment worktrees:")
        for wt in other_wts:
            s = wt.get("session", {})
            title = (s.get("title") or "no opencode session")[:60]
            print(f"    {wt['name']}  —  {title}")

    print()


def cmd_report(args):
    """Print the numbers needed for the evidence page."""
    inv = _load_inventory()
    c = inv["counts"]
    co = inv["costs"]

    print()
    print(f"  Worktrees analyzed:     {c['worktrees_total']}")
    print(f"  Instrumented sessions:  {c['db_sessions_experiments']}")
    print(f"  Non-experiment wts:     {c['worktrees_other']}")
    print(f"  Total experiment cost:  {_fmt_usd(co['total_experiment_sessions'])}")
    print()

    # Explain the 186 vs 178
    total_wt = c['worktrees_total']
    exp_sessions = c['db_sessions_experiments']
    other_wt = c['worktrees_other']
    print(f"  The {total_wt} worktrees include {other_wt} non-experiment worktrees")
    print(f"  (personal sessions, site builds, tooling experiments).")
    print(f"  The {exp_sessions} instrumented experiment sessions are the validated corpus.")
    print()


def main():
    parser = argparse.ArgumentParser(description="Experiment/Worktree Inventory Registry")
    sub = parser.add_subparsers(dest="command")

    p_refresh = sub.add_parser("refresh", help="Rebuild inventory from all data sources")

    p_list = sub.add_parser("list", help="List all experiments and model breakdown")
    p_list.add_argument("-v", "--verbose", action="store_true", help="Show session titles")

    sub.add_parser("stats", help="Show aggregate statistics")

    p_wt = sub.add_parser("worktrees", help="List worktrees")
    p_wt.add_argument("-a", "--all", action="store_true", help="Show experiment worktrees too")

    sub.add_parser("report", help="Print numbers formatted for the evidence page")

    args = parser.parse_args()

    if args.command == "refresh":
        refresh()
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "worktrees":
        cmd_worktrees(args)
    elif args.command == "report":
        cmd_report(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
