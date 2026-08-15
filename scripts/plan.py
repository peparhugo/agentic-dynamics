"""plan.py — Phase-based experiment orchestration with dependency tracking.

Defines multi-phase experiment plans and executes them via Redis workers.
Each phase: enqueue jobs → workers drain → verify completion → advance.
Auto-restarts dead workers while jobs remain in queue.

Usage:
  python3 scripts/plan.py                # run default plan
  python3 scripts/plan.py --dry-run      # preview
  python3 scripts/plan.py --phase reviews # start from a phase
  python3 scripts/plan.py --reset         # reset state
  python3 scripts/plan.py --status        # show current state
"""

from __future__ import annotations

import abc
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import redis

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

REDIS_HOST = "127.0.0.1"
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))

PLAN_PHASE_KEY = "plan:current_phase"
PLAN_STATE_PREFIX = "plan:phase"

# Queue keys — different phases use different queues
STORY_QUEUE = "story_jobs"
STORY_STATUS = "story_status"
REVIEW_QUEUE = "review_jobs"
REVIEW_STATUS = "review_status"

LOG_DIR = ROOT / "experiments" / "results" / "stories" / "logs"


def _r() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


# ── Matrix helpers ─────────────────────────────────────────────────

_STORIES = ["task_manager_api", "static_site_gen", "notification_service"]
_TIERS = ["tier1_minimal", "tier2_small"]
_GOOD = ["clean", "bad_seed", "early_degrade"]
_BAD = ["clean", "early_degrade"]


def _completed_cells(model_filter: str) -> set[str]:
    """Find which matrix cells already have results on disk."""
    from instrument.story import load_story_result

    completed = set()
    results_dir = ROOT / "experiments" / "results" / "stories"
    for f in results_dir.glob("*.json"):
        if "dvs" in f.name or "log" in f.name:
            continue
        try:
            story = load_story_result(f)
        except Exception:
            continue
        if model_filter not in (story.model or "").lower():
            continue
        cp = Path(story.codebase_path or "")
        tier = cp.parts[-2] if len(cp.parts) >= 2 else "?"
        quality = cp.parts[-1] if len(cp.parts) >= 2 else "?"
        condition = story.perturbation_condition or ""
        if not condition:
            for cond in ["bad_seed", "early_degrade", "clean"]:
                if cond in f.name:
                    condition = cond
                    break
        completed.add(f"{story.story_name}|{tier}|{quality}|{condition}")
    return completed


def _build_cells(model: str, model_filter: str) -> list[dict]:
    """Build job cells for missing matrix entries."""
    completed = _completed_cells(model_filter)
    jobs = []
    for story in _STORIES:
        for tier in _TIERS:
            for quality, conds in [("good", _GOOD), ("bad", _BAD)]:
                for condition in conds:
                    key = f"{story}|{tier}|{quality}|{condition}"
                    if key in completed:
                        continue
                    short = f"{story[:3]}_{tier[:2]}_{quality[:2]}_{condition[:3]}"
                    jobs.append({
                        "cell_id": short,
                        "story": story, "tier": tier,
                        "quality": quality, "condition": condition,
                        "model": model,
                    })
    return jobs


# ── Phase Definition ──────────────────────────────────────────────


@dataclass
class Phase(abc.ABC):
    id: str
    name: str
    description: str = ""
    depends_on: list[str] = field(default_factory=list)
    worker_count: int = 4
    worker_script: str = "scripts/worker.py"
    queue_key: str = STORY_QUEUE
    status_key: str = STORY_STATUS

    @abc.abstractmethod
    def generate_jobs(self) -> list[dict]:
        ...

    @abc.abstractmethod
    def is_complete(self) -> bool:
        ...


# ── Concrete Phases ───────────────────────────────────────────────


class BaselineDSPhase(Phase):
    def __init__(self):
        super().__init__(
            id="baseline_ds", name="DeepSeek Baseline",
            description="30-cell matrix: DeepSeek v4 Pro",
        )

    def generate_jobs(self) -> list[dict]:
        return _build_cells("deepseek/deepseek-v4-pro", "deepseek")

    def is_complete(self) -> bool:
        return len(self.generate_jobs()) == 0


class CrossModelLunaPhase(Phase):
    def __init__(self):
        super().__init__(
            id="cross_luna", name="GPT-5.6 Luna",
            description="30-cell matrix: Luna cross-model",
            depends_on=["baseline_ds"],
        )

    def generate_jobs(self) -> list[dict]:
        return _build_cells("openai/gpt-5.6-luna", "luna")

    def is_complete(self) -> bool:
        return len(self.generate_jobs()) == 0


class CrossModelSonnetPhase(Phase):
    def __init__(self):
        super().__init__(
            id="cross_sonnet", name="Claude Sonnet 5",
            description="30-cell matrix: Sonnet 5 cross-model ($70+)",
            depends_on=["cross_luna"],
        )

    def generate_jobs(self) -> list[dict]:
        return _build_cells("anthropic/claude-sonnet-5", "sonnet")

    def is_complete(self) -> bool:
        return len(self.generate_jobs()) == 0


class AnalyzePhase(Phase):
    """Run AST + conventions + SonarQube on all worktrees."""

    def __init__(self):
        super().__init__(
            id="analyze", name="AST + SonarQube",
            description="Analyze all worktrees: AST diffs, conventions, code quality",
            worker_count=0,  # runs in-process
        )

    def generate_jobs(self) -> list[dict]:
        return []

    def is_complete(self) -> bool:
        analysis_dir = ROOT / "experiments" / "results" / "analysis"
        if not analysis_dir.exists():
            return False
        # Check if all story results have analysis files
        stories_dir = ROOT / "experiments" / "results" / "stories"
        for f in stories_dir.glob("*.json"):
            if "dvs" in f.name or "log" in f.name:
                continue
            story_id = f.stem.split("_")[-1]  # last segment is story hash
            if len(story_id) < 8:
                continue
            analysis_file = analysis_dir / f"analysis_{story_id}.json"
            if not analysis_file.exists():
                return False
        return True


class ReviewPhase(Phase):
    def __init__(self):
        super().__init__(
            id="reviews", name="Review Agent",
            description="DeepSeek Flash reviews on all worktrees",
            depends_on=["analyze"],
            worker_script="scripts/review_worker.py",
            queue_key=REVIEW_QUEUE,
            status_key=REVIEW_STATUS,
        )

    def generate_jobs(self) -> list[dict]:
        from instrument.story import load_story_result

        results_dir = ROOT / "experiments" / "results" / "stories"
        reviews_dir = ROOT / "experiments" / "results" / "reviews"
        MODEL = "deepseek/deepseek-v4-flash"  # noqa: N806

        jobs = []
        for rf in sorted(results_dir.glob("*.json")):
            if "dvs" in rf.name or "log" in rf.name:
                continue
            try:
                story = load_story_result(rf)
            except Exception:
                continue
            wt = Path(story.worktree) if story.worktree else None
            if not wt or not wt.exists():
                continue

            review_path = reviews_dir / f"review_{story.story_id}.json"
            if review_path.exists():
                try:
                    existing = json.loads(review_path.read_text())
                    # Complete if story review exists AND commit reviews
                    # cover at least session_count - 1 (some stories terminate early).
                    session_count = story.session_count or 5
                    needed = max(3, session_count - 1)
                    if (existing.get("story_review")
                            and len(existing.get("commit_reviews", [])) >= needed):
                        continue
                except (json.JSONDecodeError, OSError):
                    pass

            try:
                log = subprocess.run(
                    ["git", "-C", str(wt), "log", "--reverse", "--format=%H|%s"],
                    capture_output=True, text=True, timeout=10,
                ).stdout
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue

            import re
            for line in log.strip().splitlines():
                if "|" not in line or "Session" not in line:
                    continue
                ch, cm = line.split("|", 1)
                m = re.search(r"Session\s+(\d+)", cm)
                sn = int(m.group(1)) if m else 0
                jobs.append({
                    "job_id": f"{story.story_id}_{sn}",
                    "story_name": story.story_name, "story_id": story.story_id,
                    "worktree": str(wt), "commit_hash": ch,
                    "commit_message": cm, "session_number": sn,
                    "model": MODEL,
                })

            jobs.append({
                "job_id": f"{story.story_id}_story",
                "story_name": story.story_name, "story_id": story.story_id,
                "worktree": str(wt), "commit_hash": "", "commit_message": "",
                "session_number": 0, "model": MODEL,
                "job_type": "story_review",
            })
        return jobs

    def is_complete(self) -> bool:
        return len(self.generate_jobs()) == 0


class RegeneratePhase(Phase):
    def __init__(self):
        super().__init__(
            id="regenerate", name="Regenerate Data",
            description="backfill → sync → build → lab book",
            depends_on=["reviews"],
            worker_count=0,
        )

    def generate_jobs(self) -> list[dict]:
        return []

    def is_complete(self) -> bool:
        return False


# ── Orchestration ─────────────────────────────────────────────────


def _state_key(phase_id: str) -> str:
    return f"{PLAN_STATE_PREFIX}:{phase_id}"


def _get_state(r: redis.Redis, phase_id: str) -> dict:
    raw = r.hgetall(_state_key(phase_id))
    return {
        "status": raw.get("status", "pending"),
        "jobs_total": int(raw.get("jobs_total", 0)),
        "jobs_done": int(raw.get("jobs_done", 0)),
    }


def _set_state(r: redis.Redis, phase_id: str, **kwargs) -> None:
    r.hset(_state_key(phase_id), mapping={k: str(v) for k, v in kwargs.items()})


def _spawn_workers(phase: Phase) -> list[subprocess.Popen]:
    procs = []
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(phase.worker_count):
        log_file = LOG_DIR / f"worker_{phase.id}_{i + 1}.log"
        with open(log_file, "w") as f:
            p = subprocess.Popen(
                ["nohup", sys.executable, phase.worker_script],
                stdout=f,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            procs.append(p)
    return procs


def _workers_alive(phase: Phase) -> int:
    result = subprocess.run(
        ["pgrep", "-f", phase.worker_script],
        capture_output=True, text=True,
    )
    return len(result.stdout.strip().splitlines()) if result.returncode == 0 else 0


def _execute_phase(phase: Phase, r: redis.Redis, dry_run: bool,
                   worker_pids: list) -> bool:
    # Check dependencies
    for dep_id in phase.depends_on:
        dep_state = _get_state(r, dep_id)
        if dep_state["status"] != "done":
            return False

    state = _get_state(r, phase.id)

    if state["status"] == "done":
        return True

    if state["status"] == "pending":
        jobs = phase.generate_jobs()

        if phase.is_complete() and not jobs:
            _set_state(r, phase.id, status="done")
            return True

        if dry_run:
            print(f"  Would enqueue {len(jobs)} jobs")
            return True

        for job in jobs:
            r.lpush(phase.queue_key, json.dumps(job))
            jid = job.get("job_id") or job.get("cell_id", "?")
            r.hset(phase.status_key, jid, "queued")

        _set_state(r, phase.id, status="running", jobs_total=len(jobs))
        r.set(PLAN_PHASE_KEY, phase.id)

        # Spawn workers
        alive = _workers_alive(phase)
        needed = phase.worker_count - alive
        if needed > 0 and phase.worker_count > 0:
            print(f"  Launching {needed} workers...")
            _spawn_workers(phase)

    if state["status"] == "running":
        # Restart dead workers if jobs remain
        queue_size = r.llen(phase.queue_key)
        alive = _workers_alive(phase)

        # Self-heal: if queue is empty but work remains (jobs lost mid-run),
        # re-generate and re-enqueue the missing jobs.
        if queue_size == 0 and alive == 0 and not phase.is_complete():
            missing = phase.generate_jobs()
            print(f"  Re-enqueuing {len(missing)} lost jobs...")
            for job in missing:
                r.lpush(phase.queue_key, json.dumps(job))
                jid = job.get("job_id") or job.get("cell_id", "?")
                r.hset(phase.status_key, jid, "queued")
            queue_size = len(missing)

        if queue_size > 0 and alive < phase.worker_count:
            needed = phase.worker_count - alive
            print(f"  {alive}/{phase.worker_count} workers alive, restarting {needed}...")
            _spawn_workers(phase)

        done = sum(1 for v in r.hgetall(phase.status_key).values()
                   if v in ("done", "failed"))
        total = state["jobs_total"]
        print(f"  {done}/{total} done, {queue_size} in queue, {alive} workers")

        if queue_size == 0 and done >= total:
            _set_state(r, phase.id, status="done", jobs_done=done)
            return True

        # Fallback: status hash is unreliable (Redis can lose entries).
        # If queue is empty and no workers are alive, verify against disk.
        if queue_size == 0 and alive == 0 and phase.is_complete():
            _set_state(r, phase.id, status="done", jobs_done=done)
            return True

    return False


def run_plan(plan, start_from=None, dry_run=False, reset=False):
    r = _r()
    r.ping()

    if reset:
        for phase in plan.phases:
            r.delete(_state_key(phase.id))
        r.delete(PLAN_PHASE_KEY)
        print("Plan state reset.")

    skip = start_from
    r.get(PLAN_PHASE_KEY) or ""
    worker_pids: list = []

    for phase in plan.phases:
        if skip and phase.id != skip:
            continue
        skip = None

        print(f"\n{'=' * 60}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {phase.id} — {phase.name}")
        print(f"  Deps: {phase.depends_on or 'none'}")

        # In-process phases
        if phase.worker_count == 0:
            # Skip if already done (idempotency for restarts)
            if _get_state(r, phase.id)["status"] == "done":
                print("  Already done.")
                continue
            if isinstance(phase, AnalyzePhase):
                print("  Running analyze_stories.py...")
                if not dry_run:
                    subprocess.run(
                        [sys.executable, "scripts/analyze_stories.py"],
                        cwd=str(ROOT), timeout=600,
                    )
                _set_state(r, phase.id, status="done")
            elif isinstance(phase, RegeneratePhase):
                print("  Running backfill → sync → build → lab...")
                if not dry_run:
                    for script in [
                        "scripts/backfill_costs.py",
                        "scripts/sync_data.py",
                        "scripts/build_data.py",
                        "scripts/lab_story_review.py",
                    ]:
                        print(f"    {script}...")
                        subprocess.run(
                            [sys.executable, script],
                            cwd=str(ROOT), timeout=300,
                        )
                _set_state(r, phase.id, status="done")
                print("  Done.")
            continue

        r.set(PLAN_PHASE_KEY, phase.id)

        while not _execute_phase(phase, r, dry_run, worker_pids):
            time.sleep(30)

        if dry_run:
            break

    print(f"\n{'=' * 60}")
    print(f"Plan '{plan.name}' complete.")


def show_status(plan):
    r = _r()
    try:
        r.ping()
    except Exception as e:
        print(f"Redis unavailable: {e}")
        return

    current = r.get(PLAN_PHASE_KEY) or "(none)"
    print(f"Plan: {plan.name}  |  Current phase: {current}\n")

    for phase in plan.phases:
        state = _get_state(r, phase.id)
        marker = "→" if phase.id == current else " "
        queue = r.llen(phase.queue_key)
        s = state["status"]
        d = state.get("jobs_done", 0)
        t = state.get("jobs_total", 0)
        workers = _workers_alive(phase)
        print(f"  {marker} {phase.id:20s} {s:10s}  {d}/{t} done  q={queue}  workers={workers}")


DEFAULT_PLAN = type("Plan", (), {
    "name": "full_matrix",
    "description": "DS → Luna → Analyze → Reviews → Regenerate",
    "phases": [
        BaselineDSPhase(),
        CrossModelLunaPhase(),
        # CrossModelSonnetPhase(),  # $70+ — enable when ready
        AnalyzePhase(),
        ReviewPhase(),
        RegeneratePhase(),
    ],
})()


def main():
    args = sys.argv[1:]

    if "--status" in args:
        show_status(DEFAULT_PLAN)
        return

    dry_run = "--dry-run" in args
    reset = "--reset" in args

    start_from = None
    for arg in args:
        if arg.startswith("--phase"):
            start_from = arg.split("=", 1)[1] if "=" in arg else None

    run_plan(DEFAULT_PLAN, start_from=start_from, dry_run=dry_run, reset=reset)


if __name__ == "__main__":
    main()
