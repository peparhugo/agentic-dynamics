"""DVS analysis worker — pop cell, run analysis, save DVS to Redis.

Usage:
    python scripts/worker_dvs.py &
    python scripts/worker_dvs.py &  # multiple workers for parallel analysis
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import redis

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from instrument.story import load_story_result
from instrument.commit_analysis import analyze_story_worktree
from instrument.entropy import compute_entropy, entropy_delta
from instrument.codebase_graph import build_graph, compute_metrics
from instrument.value_score import compute_story_dvs
from instrument.review import review_commit

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6379"))
QUEUE_KEY = "dvs_jobs"
STATUS_KEY = "dvs_status"
RESULTS_KEY = "dvs_results"
BLOCK_TIMEOUT = 5
IDLE_EXIT = 12  # polls before exit


def main() -> None:
    worker_id = os.getpid()
    print(f"[dvs W{worker_id}] Started")

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    completed = 0
    failed = 0
    empty_polls = 0

    while True:
        result = r.brpop(QUEUE_KEY, timeout=BLOCK_TIMEOUT)
        if result is None:
            empty_polls += 1
            if empty_polls >= IDLE_EXIT:
                if r.llen(QUEUE_KEY) == 0:
                    print(f"[dvs W{worker_id}] Done: {completed} ok, {failed} failed")
                    break
                empty_polls = 0
            continue
        empty_polls = 0

        _, file_path = result
        rf = Path(file_path)
        r.hset(STATUS_KEY, rf.name, "running")

        try:
            cell = _compute_dvs(rf)
            if cell:
                r.hset(RESULTS_KEY, rf.name, json.dumps(cell))
                r.hset(STATUS_KEY, rf.name, "done")
                completed += 1
                print(f"[dvs W{worker_id}] {rf.name[:40]}: DVS={cell['dvs']['score']:.3f} ({completed+failed})")
            else:
                r.hset(STATUS_KEY, rf.name, "failed")
                failed += 1
        except Exception as e:
            r.hset(STATUS_KEY, rf.name, "failed")
            failed += 1


def _compute_dvs(rf: Path) -> dict | None:
    story = load_story_result(rf)
    worktree = Path(story.worktree)
    if not worktree.exists():
        return None

    # Per-commit analysis
    analysis = analyze_story_worktree(worktree)

    # Entropy
    try:
        ep = compute_entropy(worktree)
    except Exception:
        ep = None

    # Graph metrics
    try:
        graph = build_graph(worktree)
        metrics = compute_metrics(graph)
    except Exception:
        metrics = None

    # Collect values for DVS
    costs = [s.cost_usd for s in story.sessions]
    correctness_values = []
    for s in story.sessions:
        if s.agentic and s.agentic.tests_total > 0:
            correctness_values.append(s.agentic.correctness)
        else:
            correctness_values.append(0.0)

    # Architectural fit: review first and last session commits
    arch_fit_values = []
    session_commits = _get_session_commits(worktree)
    for session_num in range(1, len(story.sessions) + 1):
        commit = session_commits.get(session_num)
        if commit and (session_num == 1 or session_num == len(story.sessions)):
            try:
                review = review_commit(worktree, commit, story_name=story.story_name, session_number=session_num)
                arch_fit_values.append(review.architectural_fit)
            except Exception:
                arch_fit_values.append(0.5)
        else:
            arch_fit_values.append(0.5)

    # Convention values from commit analysis
    if analysis.commits:
        convention_values = [c.convention_score for c in analysis.commits]
        # Pad or trim to match session count
        while len(convention_values) < len(story.sessions):
            convention_values.append(convention_values[-1] if convention_values else 0.5)
        convention_values = convention_values[:len(story.sessions)]
    else:
        convention_values = [0.5] * len(story.sessions)

    # Entropy delta: seed codebase vs final worktree
    entropy_d = 0.0
    codebase_seed = Path(story.codebase_path)
    if codebase_seed.exists():
        try:
            seed_ep = compute_entropy(codebase_seed)
            worktree_ep = compute_entropy(worktree)
            entropy_d = entropy_delta(seed_ep, worktree_ep)
        except Exception:
            pass

    dvs = compute_story_dvs(
        costs, correctness_values, arch_fit_values, convention_values,
        entropy_delta=entropy_d,
    )

    return {
        "story": story.story_name,
        "story_id": story.story_id,
        "condition": story.perturbation_condition or "clean",
        "model": story.model,
        "sessions": story.session_count,
        "all_successful": story.all_successful,
        "cascade_recovery": story.cascade_recovery,
        "total_cost": round(story.total_cost, 6),
        "total_tokens": story.total_tokens,
        "dvs": dvs.to_dict(),
        "commits": len(analysis.commits),
        "net_lines": analysis.net_lines,
        "avg_convention": round(sum(c.convention_score for c in analysis.commits) / max(len(analysis.commits), 1), 3),
        "graph": metrics.to_dict() if metrics else {},
    }


if __name__ == "__main__":
    main()


def _get_session_commits(worktree: Path) -> dict[int, str]:
    """Get commit hashes for each session in a story worktree.

    Returns {session_number: commit_hash}.
    """
    proc = subprocess.run(
        ["git", "-C", str(worktree), "log", "--reverse", "--format=%H %s"],
        capture_output=True, text=True, timeout=10,
    )
    commits = {}
    session_num = 0
    for line in proc.stdout.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2 and ("[story]" in parts[1] or "Session" in parts[1]):
            session_num += 1
            commits[session_num] = parts[0]
    return commits
