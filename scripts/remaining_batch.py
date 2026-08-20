"""Run remaining experiment cells — one at a time, no parallelism, no fuss."""
import os
import sqlite3
import subprocess
import time
from pathlib import Path

import yaml
from agentic_dynamics.core.constants import WORKTREE_ROOT

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Configs are split (design §4): measurement configs under experiments/definitions/configs/
# and grid/sweep configs under experiments/campaigns/. Resolve a name across both.
CONFIG_DIRS = [
    PROJECT_ROOT / "experiments" / "definitions" / "configs",
    PROJECT_ROOT / "experiments" / "campaigns",
]


def _config_path(name: str) -> Path:
    """Resolve a config filename across the split config layout."""
    for d in CONFIG_DIRS:
        p = d / name
        if p.exists():
            return p
    return CONFIG_DIRS[0] / name

OPENSCODE_DB = Path.home() / ".local/share/opencode/opencode.db"
OPENCODE_BIN = os.environ.get("OPENCODE_BIN", str(Path.home() / ".opencode/bin/opencode"))

def load_task(config_filename):
    with open(_config_path(config_filename)) as f:
        cfg = yaml.safe_load(f)
    return cfg["task"].strip()

def cell_done(title):
    conn = sqlite3.connect(str(OPENSCODE_DB))
    r = conn.execute("SELECT tokens_output FROM session WHERE title=? AND tokens_output>0 ORDER BY time_created DESC LIMIT 1", (title,)).fetchone()
    conn.close()
    return r is not None

def get_session(title):
    conn = sqlite3.connect(str(OPENSCODE_DB))
    r = conn.execute("SELECT cost,tokens_output FROM session WHERE title=? ORDER BY time_created DESC LIMIT 1", (title,)).fetchone()
    conn.close()
    return r

def run_cell(model_id, title, config_file, timeout=400):
    if cell_done(title):
        print(f"SKIP: {title}")
        return

    task = load_task(config_file)
    prompt = f"[STANDARDIZED CONSTRAINTS]\n- Write ALL code files. Run pytest. Fix failures until all tests pass.\n- End with EXACTLY: \"TESTS: N passed, M failed\"\n\n{task}"
    workdir = f"{WORKTREE_ROOT}/exp_batch_{title.replace('[','').replace(']','').replace(':','_')[:40]}"
    os.makedirs(workdir, exist_ok=True)

    print(f"RUN: {title}", flush=True)
    t0 = time.monotonic()
    try:
        subprocess.run([
            OPENCODE_BIN, "run",
            "--model", model_id, "--title", title,
            "--format", "json", "--auto", "--dir", workdir,
            prompt,
        ], capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after {timeout}s")
        return

    elapsed = time.monotonic() - t0
    s = get_session(title)
    if s:
        print(f"  OK ${s[0]:.4f} {s[1]:,}tok ({elapsed:.0f}s)", flush=True)
    else:
        print(f"  ERR no DB record ({elapsed:.0f}s)", flush=True)
    time.sleep(3)


# Batch 1: GPT-5.6 cross-domain (3 key configs)
BATCH1 = [
    ("openai/gpt-5.6", "[batch:task_manager:baseline] gpt_5_6", "task_manager.yaml", 600),
    ("openai/gpt-5.6", "[batch:data_table:baseline] gpt_5_6", "data_table.yaml", 350),
    ("openai/gpt-5.6", "[batch:collaborative_editor:baseline] gpt_5_6", "collaborative_editor.yaml", 400),
    ("openai/gpt-5-mini", "[batch:task_manager:baseline] gpt_5_mini", "task_manager.yaml", 600),
]

print("=== BATCH 1: GPT-5.6 + GPT-5-mini cross-domain ===")
for model, title, cfg, timeout in BATCH1:
    run_cell(model, title, cfg, timeout)

# Batch 2: Claude cross-domain (3 key configs)
BATCH2 = [
    ("anthropic/claude-fable-5", "[batch:task_manager:baseline] claude_fable_5", "task_manager.yaml", 600),
    ("anthropic/claude-fable-5", "[batch:data_table:baseline] claude_fable_5", "data_table.yaml", 350),
    ("anthropic/claude-fable-5", "[batch:collaborative_editor:baseline] claude_fable_5", "collaborative_editor.yaml", 400),
]

print("\n=== BATCH 2: Claude cross-domain ===")
for model, title, cfg, timeout in BATCH2:
    run_cell(model, title, cfg, timeout)

print("\n=== ALL DONE ===")
