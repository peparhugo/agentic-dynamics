"""Batch run experiment configs on DeepSeek — cheap, parallel, fast."""
import os
import sqlite3
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml
from agentic_dynamics.core.constants import WORKTREE_ROOT

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "experiments/configs"
OPENSCODE_DB = Path.home() / ".local/share/opencode/opencode.db"
OPENCODE_BIN = os.environ.get("OPENCODE_BIN", str(Path.home() / ".opencode/bin/opencode"))
MODEL = "deepseek/deepseek-v4-pro"
TIMEOUT = 250

def get_task(config_name):
    """Extract task text from a YAML config."""
    with open(CONFIG_DIR / config_name) as f:
        cfg = yaml.safe_load(f)
    return cfg["task"].strip(), cfg.get("constraints", []), cfg.get("name", config_name[:-5])

def cell_done(title):
    db = sqlite3.connect(str(OPENSCODE_DB))
    r = db.execute("SELECT tokens_output FROM session WHERE title=? AND tokens_output>0 ORDER BY time_created DESC LIMIT 1", (title,)).fetchone()
    db.close()
    return r is not None

def run_experiment(config_name, operator="baseline", silent=None):
    """Run one experiment cell via opencode subprocess."""
    task, constraints, exp_name = get_task(config_name)
    op_tag = "perturbed" if operator != "baseline" else "baseline"
    sm_tag = "forced" if silent is True else "natural" if silent is None else "verbose"
    title = f"[batch:{exp_name}:{op_tag}] ds_{sm_tag}"

    if cell_done(title):
        return {"status": "skip", "title": title}

    # Build standardized prompt
    prompt = "[STANDARDIZED CONSTRAINTS]\n"
    if silent is True:
        prompt += "- IMPLEMENTATION-ONLY: no docstrings, comments, or explanations. Code only.\n"
    prompt += "- Write ALL code files. Run pytest. Fix failures until all tests pass.\n"
    prompt += '- End with EXACTLY: "TESTS: N passed, M failed"\n\n'
    prompt += task

    if operator == "perturbed":
        prompt += "\n\nNOTE: A previous developer built part of this. JWT auth module already exists and passes tests. Focus on remaining work."

    workdir = f"{WORKTREE_ROOT}/exp_batch_{exp_name}_{sm_tag}"
    os.makedirs(workdir, exist_ok=True)

    t0 = time.monotonic()
    r = subprocess.run([
        OPENCODE_BIN, "run",
        "--model", MODEL, "--title", title,
        "--format", "json", "--auto",
        "--dir", workdir, prompt,
    ], capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
    elapsed = time.monotonic() - t0

    db = sqlite3.connect(str(OPENSCODE_DB))
    row = db.execute("SELECT cost,tokens_output FROM session WHERE title=? ORDER BY time_created DESC LIMIT 1", (title,)).fetchone()
    db.close()

    if row:
        return {"status": "ok", "title": title, "cost": row[0], "tok": row[1], "dur": elapsed}
    else:
        return {"status": f"err_exit={r.returncode}", "title": title, "dur": elapsed}

# Configs to run - all backend + frontend + task_manager
CONFIGS = [
    "task_manager.yaml",
    # Backend
    "twitter_timeline.yaml", "web_crawler.yaml", "search_kv_store.yaml",
    "mint_financial.yaml", "social_graph.yaml",
    # Frontend
    "collaborative_editor.yaml", "data_table.yaml", "form_wizard.yaml",
    "notification_system.yaml", "autocomplete_search.yaml",
    # Research (already partially done)
    "factorial_compound.yaml", "fastapi_maintenance.yaml",
]

print("=== BATCH DEEPSEEK EXPERIMENTS ===")
print(f"Model: {MODEL}")
print(f"Configs: {len(CONFIGS)}")
print("Launching in parallel (max 3 concurrent)...")
print()

results = []
with ThreadPoolExecutor(max_workers=3) as ex:
    futures = {ex.submit(run_experiment, c): c for c in CONFIGS}
    for f in as_completed(futures):
        r = f.result()
        c = futures[f]
        icon = "✓" if r["status"] == "ok" else "⊘" if r["status"] == "skip" else "✗"
        cost_str = f"${r.get('cost',0):.4f}" if r["status"] == "ok" else "-"
        tok_str = f"{r.get('tok',0):,}tok" if r["status"] == "ok" else "-"
        print(f"  {icon} {c[:30]:<30} {cost_str:>10} {tok_str:>10} ({r['dur']:.0f}s) {r['status']}")
        results.append(r)

# Summary
ok = sum(1 for r in results if r["status"] == "ok")
skipped = sum(1 for r in results if r["status"] == "skip")
failed = sum(1 for r in results if r["status"] != "ok" and r["status"] != "skip")
total_cost = sum(r.get("cost",0) for r in results if r["status"] == "ok")

print(f"\nDone: {ok} ok, {skipped} skipped, {failed} failed")
print(f"Total cost: ${total_cost:.4f}")

# Save results
import json

out_path = "/tmp/batch_deepseek_results.json"
with open(out_path, "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"Results: {out_path}")
