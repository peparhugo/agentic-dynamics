"""Multi-phase iterative development experiment.

Each phase gets the output of the previous phase. Measures cumulative
cost, correctness, and compounding effects across iterations.
Exposes the real cost differential of session-based pricing.
"""

import time

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.adapters.opencode import run_opencode_agentic
from agentic_dynamics.control.model_policy import SUBSCRIPTION_DEFAULT, ensure_model_allowed
from agentic_dynamics.measurement.solution import evaluate_solution

PHASES = [
    ("build", "Build a team collaboration platform with Python/Flask and SQLite. "
     "Include: JWT auth, project CRUD, tasks within projects, comments, file attachment paths, "
     "team roles (admin/member/viewer), and pytest tests. Write ALL the code and run the tests."),

    ("refactor", "The previous session built a collaboration platform. The code is "
     "already in this directory. Refactor the storage layer to use SQLAlchemy abstractions "
     "that support both SQLite AND PostgreSQL. Don't break anything. Run the tests after."),

    ("add_feature", "The previous session built a collaboration platform with SQLAlchemy. "
     "Add real-time comment notifications using Flask-SocketIO. When a user adds a comment, "
     "all team members viewing that task should see it immediately. Don't break existing tests. "
     "Add new tests for the WebSocket functionality."),

    ("verify", "The previous sessions built a collaboration platform with WebSocket notifications. "
     "Run ALL tests. Fix any failures. Verify the full feature set works end-to-end. "
     "Then write a brief summary of what was built across all phases."),
]


def run_multi_phase(model_id: str, label: str, timeout: int = 300):
    """Run all phases sequentially, each building on the previous output."""
    import tempfile

    workdir = tempfile.mkdtemp(prefix=f"iterative_{label}_")
    subprocess = __import__("subprocess")
    subprocess.run(["git", "init"], cwd=workdir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "exp@test"], cwd=workdir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Experiment"], cwd=workdir, capture_output=True)

    results = []
    cumulative_cost = 0.0
    cumulative_tokens = 0

    for phase_num, (phase_name, phase_task) in enumerate(PHASES):
        print(f"\n  Phase {phase_num+1}/{len(PHASES)}: {phase_name}...", end=" ", flush=True)
        t0 = time.monotonic()

        # Give the model context about what exists
        prompt = (f"Phase {phase_num+1} of building a collaboration platform.\n\n"
                  f"{phase_task}\n\n"
                  f"The codebase from previous phases is already in this directory. "
                  f"Review existing code, make changes, and run tests.")

        r = run_opencode_agentic(prompt, model=model_id, workdir=workdir,
                                 timeout=timeout, init_git=False)
        elapsed = time.monotonic() - t0

        cumulative_cost += r.estimated_cost_usd
        cumulative_tokens += r.total_tokens

        has_tests = any("test" in f.lower() for f in r.files_created)
        evaluate_solution(r.final_response, [])

        print(f"tok={r.total_tokens:,} ${r.estimated_cost_usd:.4f} "
              f"tools={r.total_tool_calls} tests={'YES' if has_tests else 'no'} "
              f"cumulative=${cumulative_cost:.4f}")

        results.append({
            "phase": phase_name, "phase_num": phase_num + 1,
            "tokens": r.total_tokens, "cost": r.estimated_cost_usd,
            "tools": r.total_tool_calls, "retries": r.retry_loops,
            "depth": r.iteration_depth, "has_tests": has_tests,
            "duration_s": elapsed,
            "cumulative_cost": cumulative_cost,
            "cumulative_tokens": cumulative_tokens,
        })

        # Commit changes so next phase sees them
        subprocess.run(["git", "add", "-A"], cwd=workdir, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"Phase {phase_num+1}: {phase_name}"],
                      cwd=workdir, capture_output=True)

        time.sleep(2)

    # Summary
    print(f"\n  {'='*60}")
    print(f"  MULTI-PHASE SUMMARY — {label}")
    print(f"  {'='*60}")
    print(f"  {'Phase':<12} {'Tokens':>8} {'Cost':>9} {'Tools':>6} {'Depth':>6} {'Cum $':>9} {'Cum Tok':>9}")
    print(f"  {'-'*60}")
    for r in results:
        print(f"  {r['phase']:<12} {r['tokens']:>8,} ${r['cost']:>9.4f} {r['tools']:>6} {r['depth']:>6} ${r['cumulative_cost']:>9.4f} {r['cumulative_tokens']:>9,}")

    print(f"\n  Total: ${cumulative_cost:.4f} | {cumulative_tokens:,} tokens | "
          f"{len(PHASES)} phases")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=SUBSCRIPTION_DEFAULT)
    parser.add_argument("--compare", nargs="*")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    for model_id in (args.compare or [args.model]):
        ensure_model_allowed(model_id)

    if args.compare:
        for model_id in args.compare:
            label = model_id.split("/")[-1]
            print(f"\n{'#'*80}")
            print(f"# {label}")
            print(f"{'#'*80}")
            run_multi_phase(model_id, label, args.timeout)
    else:
        run_multi_phase(args.model, args.model.split("/")[-1], args.timeout)
