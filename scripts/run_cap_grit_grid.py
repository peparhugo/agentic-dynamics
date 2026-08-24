"""E4 live-grid executor — run cap_grit_strength_grid cells sequentially on sonnet-5.

Phase x2 of ``cap_grit_grid_execute`` (see ``docs/designs/current/cap_grit_grid_runplan.md``):
runs the 8 cells SEQUENTIALLY, one story (``task_manager_api``) per cell, on
``anthropic/claude-sonnet-5`` via ``claude_cli``. Applies the spec's declared retry policy
(finding 4) at the ledger level, records ``LEDGER_FIELDS``-compliant attempt rows into
``experiments/results/cap_grit_grid_ledger.json``, and commits progress per cell.

F1/F2 resolution (runplan §3): the ``bad_seed`` operator is not compilable and the
``run_story(mutation=...)`` seam was gate-only. This executor uses verified ``inject_bug``
artifacts at the declared strengths (``experiments/results/cap_grit_grid_mutations/``) via the
now-wired seam, and patches ``perturbation_strength`` per F3.

Usage:
    python scripts/run_cap_grit_grid.py            # run all pending cells, commit per cell
    python scripts/run_cap_grit_grid.py --cell 3   # run a single cell by 0-based index
    python scripts/run_cap_grit_grid.py --dry-run  # print the plan, touch nothing
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import _bootstrap  # noqa: E402
except ImportError:
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.core.constants import SESSION_TIMEOUT, model_slug
from agentic_dynamics.measurement.mutation import MutationArtifact
from agentic_dynamics.runtime.story import (
    BUILTIN_STORIES,
    PerturbationCondition,
    run_story,
    save_story_result,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = REPO_ROOT / "experiments/results/cap_grit_grid_ledger.json"
STORIES_DIR = REPO_ROOT / "experiments/results/stories"
MUTATIONS_DIR = REPO_ROOT / "experiments/results/cap_grit_grid_mutations"
CODEBASE = REPO_ROOT / "experiments/codebases/python/tier1_minimal/good"

CELL_MODEL = "anthropic/claude-sonnet-5"
CELL_BACKEND = "claude_cli"

#: Declared strength per condition_strength factor level (spec finding 1/2).
STRENGTH_BY_LEVEL = {"clean": 0.0, "bad_seed_low": 0.2, "bad_seed_mid": 0.5, "bad_seed_high": 0.8}

#: Claude usage-cap error substrings — on any of these, commit + STOP cleanly (resumable).
CAP_ERROR_HINTS = ("429", "rate_limit", "rate limit", "usage", "capacity", "overloaded",
                   "resource_exhausted", "quota")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_ledger() -> dict:
    return json.loads(LEDGER_PATH.read_text())


def write_ledger(ledger: dict) -> None:
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2))


def pick_mutation(condition_strength: str) -> MutationArtifact | None:
    """Load the verified mutation artifact for low/high cells (finding F1/F2 resolution)."""
    if condition_strength == "bad_seed_low":
        files = [p for p in MUTATIONS_DIR.glob("*.json")]
        arts = [MutationArtifact.load(p) for p in files]
        match = next((a for a in arts if abs(a.strength - 0.2) < 1e-9), None)
        if match is None:
            raise SystemExit(f"no s=0.2 mutation artifact in {MUTATIONS_DIR}")
        return match
    if condition_strength == "bad_seed_high":
        files = [p for p in MUTATIONS_DIR.glob("*.json")]
        arts = [MutationArtifact.load(p) for p in files]
        match = next((a for a in arts if abs(a.strength - 0.8) < 1e-9), None)
        if match is None:
            raise SystemExit(f"no s=0.8 mutation artifact in {MUTATIONS_DIR}")
        return match
    return None


def condition_for(level: str) -> PerturbationCondition:
    if level == "clean":
        return PerturbationCondition.CLEAN
    return PerturbationCondition.BAD_SEED


def is_cap_error(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(h in lower for h in CAP_ERROR_HINTS)


def build_attempt_row(
    cell: dict, result, attempt_number: int, parent_attempt_id: str | None, retry_reason: str,
) -> dict:
    """Map a StoryResult into a LEDGER_FIELDS-compliant attempt row (spec finding 3)."""
    summary = result.summary if hasattr(result, "summary") else (result.to_dict().get("summary") or {})
    total_cost = summary.get("total_cost", result.total_cost)
    continuation = summary.get("total_continuation_cost", 0.0)
    subagent = summary.get("total_subagent_cost", 0.0)
    return {
        "job_id": cell["cell_id"],
        "spec_id": "cap_grit_strength_grid@0.1",
        "policy_arm": cell["policy_arm"],
        "model": result.model,
        "condition": cell["condition"],
        "strength": cell["strength"],
        "perturbation_strength": cell["strength"],
        "attempt_id": f"{cell['cell_id']}_a{attempt_number}",
        "attempt_number": attempt_number,
        "parent_attempt_id": parent_attempt_id,
        "retry_reason": retry_reason,
        "started_at": result.started_at,
        "ended_at": result.completed_at,
        "actual_cost": round(total_cost, 8),
        "rework_cost": round(continuation + subagent, 8),
        "test_executed_success": result.test_executed_success,
        "status": "accepted" if result.test_executed_success else "failed",
        "story_id": result.story_id,
        "worktree": result.worktree,
        "mutation_id": result.mutation_id,
        "result_path": "",
    }


def run_one_cell(cell: dict, dry_run: bool = False) -> None:
    """Run one cell's story (attempt 1), applying the grit_retry policy for that arm."""
    cell_id = cell["cell_id"]
    level = cell["condition_strength"]
    arm = cell["policy_arm"]
    strength = cell["strength"]
    story = BUILTIN_STORIES["task_manager_api"]

    mutation = pick_mutation(level)
    condition = condition_for(level)

    print(f"\n=== CELL {cell_id} ===")
    print(f"  level={level} arm={arm} strength={strength} mutation={mutation.mutation_id if mutation else None}")

    if dry_run:
        cell["status"] = "dry_run"
        return

    if not CODEBASE.exists():
        raise SystemExit(f"codebase not found: {CODEBASE}")

    if not os.environ.get("CLAUDE_BIN"):
        print("  WARNING: CLAUDE_BIN not set in environment — claude_cli backend may fail", file=sys.stderr)

    # ── attempt 1 ──────────────────────────────────────────────
    print("  [cost before] logging...")
    t0 = time.monotonic()
    result = run_story(
        story,
        codebase_path=str(CODEBASE),
        model=CELL_MODEL,
        condition=condition,
        mutation=mutation,
        worktree_root="/tmp",
        timeout=SESSION_TIMEOUT,
        backend=CELL_BACKEND,
        enforce_pytest=True,
    )
    cost1 = round(result.total_cost, 8)
    duration1 = round(time.monotonic() - t0, 1)
    ok1 = result.test_executed_success
    print(f"  [attempt 1] cost=${cost1} duration={duration1}s test_executed_success={ok1}")
    if result.error:
        print(f"  [attempt 1] error={result.error[:200]}")

    slug = model_slug(result.model)
    out1 = STORIES_DIR / f"{story.name}_{slug}_{result.perturbation_condition}_{result.story_id}.json"
    save_story_result(result, out1)
    attempt1 = build_attempt_row(cell, result, 1, None, "")
    attempt1["result_path"] = str(out1.relative_to(REPO_ROOT))

    cell["attempts"] = [attempt1]
    cell["status"] = "accepted" if ok1 else "failed"
    cell["realized_cost"] = cost1
    cell["realized_duration_s"] = duration1

    # ── retry policy (finding 4): grit_retry only, only on failure ──
    if arm == "grit_retry" and ok1 is False:
        print("  [retry] first attempt failed — queuing attempt 2")
        t0 = time.monotonic()
        result2 = run_story(
            story,
            codebase_path=str(CODEBASE),
            model=CELL_MODEL,
            condition=condition,
            mutation=mutation,
            worktree_root="/tmp",
            timeout=SESSION_TIMEOUT,
            backend=CELL_BACKEND,
            enforce_pytest=True,
        )
        cost2 = round(result2.total_cost, 8)
        duration2 = round(time.monotonic() - t0, 1)
        ok2 = result2.test_executed_success
        print(f"  [attempt 2] cost=${cost2} duration={duration2}s test_executed_success={ok2}")
        if result2.error:
            print(f"  [attempt 2] error={result2.error[:200]}")

        out2 = STORIES_DIR / f"{story.name}_{slug}_{result2.perturbation_condition}_{result2.story_id}.json"
        save_story_result(result2, out2)
        attempt2 = build_attempt_row(
            cell, result2, 2, attempt1["attempt_id"], "first_attempt_test_failure"
        )
        attempt2["result_path"] = str(out2.relative_to(REPO_ROOT))
        cell["attempts"].append(attempt2)
        cell["status"] = "accepted" if ok2 else "failed"
        cell["realized_cost"] = round(cost1 + cost2, 8)
        cell["realized_duration_s"] = round(duration1 + duration2, 1)

    cell["completed_at"] = now_iso()

    # ── usage-cap check: commit + STOP cleanly (resumable) ────
    all_errors = " ".join(a.get("error", "") for a in cell["attempts"]) + (result.error or "")
    if is_cap_error(all_errors):
        print("  !! Claude usage-cap signal detected — commit + STOP (resumable)", file=sys.stderr)
        cell["status"] = "paused_cap"
        return


def git_commit_per_cell(cell_id: str, msg: str) -> None:
    """Commit the ledger + story artifacts for this cell (workflow hard rule 1)."""
    subprocess.run(["git", "add", str(LEDGER_PATH.relative_to(REPO_ROOT)),
                    "experiments/results/stories", "experiments/results/cap_grit_grid_mutations"],
                   cwd=REPO_ROOT, check=False, capture_output=True)
    subprocess.run(["git", "commit", "-m", f"[workflow] x2_run_cells — {cell_id}\n\n{msg}"],
                   cwd=REPO_ROOT, check=False, capture_output=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell", type=int, default=-1,
                        help="run a single cell by 0-based index (default: all pending, in order)")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, touch nothing")
    args = parser.parse_args()

    ledger = load_ledger()
    cells = ledger["cells"]

    if args.dry_run:
        for c in cells:
            m = pick_mutation(c["condition_strength"])
            print(f"cell[{cells.index(c)}] {c['cell_id'][:64]} | "
                  f"cond={c['condition']} mut={m.mutation_id if m else None} "
                  f"s={c['strength']} ma={c['max_attempts']} arm={c['policy_arm']}")
        return

    indices = [args.cell] if args.cell >= 0 else [i for i, c in enumerate(cells) if c["status"] == "pending"]

    for idx in indices:
        cell = cells[idx]
        if cell["status"] not in ("pending", "paused_cap"):
            print(f"  skip cell[{idx}] — status={cell['status']}")
            continue
        run_one_cell(cell)
        write_ledger(ledger)
        git_commit_per_cell(cell["cell_id"], f"status={cell['status']} cost=${cell.get('realized_cost','?')} "
                                             f"attempts={len(cell.get('attempts', []))}")

    if args.cell < 0:
        pending = [c for c in cells if c["status"] == "pending"]
        done = [c for c in cells if c["status"] in ("accepted", "failed")]
        paused = [c for c in cells if c["status"] == "paused_cap"]
        print(f"\nDONE: {len(done)}/8 cells finished, {len(pending)} pending, {len(paused)} paused_cap")
        total = round(sum(c.get("realized_cost", 0.0) for c in cells), 4)
        print(f"REALIZED TOTAL COST: ${total} (ceiling $10.00)")


if __name__ == "__main__":
    main()
