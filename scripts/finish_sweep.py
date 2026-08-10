"""Run remaining silent sweep cells — one at a time, properly."""
import subprocess, time, sqlite3, os, sys
from pathlib import Path
from _constants import WORKTREE_ROOT

OPENCODE_DB = Path.home() / ".local/share/opencode/opencode.db"
OPENCODE_BIN = os.environ.get("OPENCODE_BIN", str(Path.home() / ".opencode/bin/opencode"))

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
    db = sqlite3.connect(str(OPENCODE_DB))
    r = db.execute("SELECT tokens_output FROM session WHERE title=? AND tokens_output>0 ORDER BY time_created DESC LIMIT 1", (title,)).fetchone()
    db.close()
    return r is not None

cells = [
    ("openai/gpt-5.6", "natural", "perturbed"),
    ("openai/gpt-5.6", "forced", "baseline"),
    ("openai/gpt-5.6", "forced", "perturbed"),
    ("openai/gpt-5-mini", "natural", "baseline"),
    ("openai/gpt-5-mini", "natural", "perturbed"),
    ("openai/gpt-5-mini", "forced", "baseline"),
    ("openai/gpt-5-mini", "forced", "perturbed"),
]

for model_id, silent_mode, operator in cells:
    slug = model_id.split("/")[1].replace(".","_").replace("-","_")
    title = f"[silent_sweep:{operator}:{silent_mode}] {slug}"
    
    if cell_done(title):
        print(f"SKIP: {title}")
        continue
    
    workdir = f"{WORKTREE_ROOT}/exp_sweep_{slug}_{silent_mode[0]}{operator[0]}"
    os.makedirs(workdir, exist_ok=True)
    prompt = build_prompt(silent_mode, operator)
    
    print(f"RUN: {title}")
    sys.stdout.flush()
    t0 = time.monotonic()
    r = subprocess.run([
        OPENCODE_BIN, "run",
        "--model", model_id,
        "--title", title,
        "--format", "json",
        "--auto",
        "--dir", workdir,
        prompt,
    ], capture_output=True, text=True, timeout=400, stdin=subprocess.DEVNULL)
    elapsed = time.monotonic() - t0
    
    db = sqlite3.connect(str(OPENCODE_DB))
    row = db.execute("SELECT cost,tokens_output FROM session WHERE title=? ORDER BY time_created DESC LIMIT 1", (title,)).fetchone()
    db.close()
    if row:
        print(f"  OK ${row[0]:.4f} {row[1]}tok ({elapsed:.0f}s)")
    else:
        print(f"  ERR exit={r.returncode} ({elapsed:.0f}s)")
    
    time.sleep(2)

print("\nALL DONE")
