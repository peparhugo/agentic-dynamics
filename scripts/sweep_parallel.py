"""Parallel silent-mode sweep — each cell is an independent subprocess run.
No fragile imports. No serial blocking. Just spawn and wait.
"""
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.core.constants import WORKTREE_ROOT

OPENSCODE_DB = Path.home() / ".local/share/opencode/opencode.db"
OPENCODE_BIN = os.environ.get("OPENCODE_BIN", str(Path.home() / ".opencode/bin/opencode"))

MODELS = [
    ("deepseek/deepseek-v4-pro", "DeepSeek_v4_Pro"),
    ("anthropic/claude-fable-5", "Claude_Fable_5"),
    ("openai/gpt-5.6", "GPT_5_6"),
    ("openai/gpt-5-mini", "GPT_5_mini"),
]

TASK = "Build an authenticated REST API with these requirements:\n1. JWT-based user auth with refresh tokens\n2. Rate limiting on login endpoint (5 attempts/minute/IP)\n3. Input validation on all endpoints\n4. Paginated list responses (20 items/page, max 100)\n5. Comprehensive error handling with proper HTTP status codes\n6. Audit logging of all mutation operations\n7. API versioning via URL prefix (/v1/...)\nUse Python/Flask + SQLAlchemy + pytest."

def build_prompt(silent_mode, operator):
    header = "[STANDARDIZED CONSTRAINTS — APPLY TO ALL MODELS]\n"
    if silent_mode == "forced":
        header += "- IMPLEMENTATION-ONLY MODE: do NOT generate docstrings, comments, or explanatory prose. Output ONLY the working code. Optimize for token efficiency.\n"
    header += "- Write ALL code files. Run pytest. Fix failures until all tests pass.\n"
    header += '- At the END of your response, state EXACTLY on one line: "TESTS: N passed, M failed"\n'
    prompt = header + "\n" + TASK
    if operator == "perturbed":
        prompt += "\n\nNOTE: You previously implemented JWT auth. That module is already done and passes all tests. Focus on the remaining requirements."
    return prompt

def cell_done(title):
    """Check if session already exists in DB."""
    try:
        import sqlite3
        c = sqlite3.connect(str(OPENSCODE_DB))
        r = c.execute("SELECT cost FROM session WHERE title = ? AND cost > 0 ORDER BY time_created DESC LIMIT 1", (title,)).fetchone()
        c.close()
        return r is not None
    except Exception:
        return False

def run_cell(model_id, silent_mode, operator, label_slug, timeout=200):
    title = f"[silent_sweep:{operator}:{silent_mode}] {label_slug}"

    if cell_done(title):
        return {"title": title, "status": "skipped", "duration": 0}

    workdir = f"{WORKTREE_ROOT}/exp_swp_{label_slug[:8]}_{silent_mode[0]}{operator[0]}"
    Path(workdir).mkdir(parents=True, exist_ok=True)

    prompt = build_prompt(silent_mode, operator)
    cmd = [
        OPENCODE_BIN, "run",
        "--model", model_id,
        "--title", title,
        "--format", "json",
        "--auto",
        "--dir", workdir,
        prompt,
    ]

    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        duration = time.monotonic() - t0
        return {"title": title, "status": "ok" if r.returncode == 0 else f"exit={r.returncode}", "duration": duration}
    except subprocess.TimeoutExpired:
        return {"title": title, "status": "timeout", "duration": timeout}
    except Exception as e:
        return {"title": title, "status": f"error:{str(e)[:50]}", "duration": time.monotonic()-t0}

def main():
    cells = []
    for model_id, label_slug in MODELS:
        for silent_mode in ("natural", "forced"):
            for operator in ("baseline", "perturbed"):
                cells.append((model_id, silent_mode, operator, label_slug))

    print(f"Launching {len(cells)} cells in parallel...")

    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(run_cell, *c): c for c in cells}
        for f in as_completed(futures):
            r = f.result()
            dur = r.get("duration", 0)
            print(f"  [{r['status']:<8}] {r['title']} ({dur:.0f}s)")

    # Summary from DB
    time.sleep(3)
    import sqlite3
    c = sqlite3.connect(str(OPENSCODE_DB))
    rows = c.execute("SELECT title,cost,json_extract(model,'$.providerID') FROM session WHERE title LIKE '%silent_sweep%' ORDER BY title").fetchall()
    c.close()
    print(f"\n{len(rows)} sessions in DB:")
    for title, cost, prov in rows:
        print(f"  {prov or '?':<11} ${cost:.4f}  {title}")

if __name__ == "__main__":
    main()
