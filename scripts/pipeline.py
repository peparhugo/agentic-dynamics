"""pipeline.py — YAML-driven phase orchestration with dependency tracking.

Defines multi-phase plans in YAML and executes them. Each phase:
enqueue jobs / run commands → verify completion → advance to next phase.
Auto-restarts dead workers while jobs remain in queue.

Usage:
  python scripts/pipeline.py                    # default (ci) plan
  python scripts/pipeline.py --plan deploy      # named plan
  python scripts/pipeline.py --dry-run          # print DAG, no execution
  python scripts/pipeline.py --graph            # ASCII dependency tree
  python scripts/pipeline.py --from reviews     # start mid-pipeline
  python scripts/pipeline.py --until analyze    # stop after phase
  python scripts/pipeline.py --only lint,test   # run subset
  python scripts/pipeline.py --status           # Redis state
  python scripts/pipeline.py --reset            # clear Redis state
  python scripts/pipeline.py --check-deps       # validate DAG only
  python scripts/pipeline.py --prompt "add foo" # template {prompt} substitution
  python scripts/pipeline.py --workers 8        # override worker count

Phase kinds:
  shell    — subprocess.run(cmd); gates on exit 0
  test     — pytest wrapper with sensible defaults
  lint     — ruff check + optional mypy
  matrix   — build story job cells, enqueue to Redis, spawn workers, poll
  review   — enqueue review jobs, spawn review workers, poll
  pipeline — sequence of shell-like steps executed in order
  ship     — git merge --squash + push (feature branches)
  fan_out  — parallel workstreams, each in a git worktree with its own
             nested phase DAG (spec → implement → test → review → ...)
  conflict_detect — git merge-tree across fan_out branches before PR
  pr_create — create one PR per fan_out branch via gh
  pr_merge  — merge PRs sequentially with conflict retry (rebase/abort)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# ── Redis configuration ──────────────────────────────────────────

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))

STORY_QUEUE = "story_jobs"
STORY_STATUS = "story_status"
REVIEW_QUEUE = "review_jobs"
REVIEW_STATUS = "review_status"

LOG_DIR = ROOT / "experiments" / "results" / "stories" / "logs"

# ── Dataclasses ──────────────────────────────────────────────────


@dataclass
class PlanPhase:
    id: str
    kind: str
    description: str = ""
    depends_on: list[str] = field(default_factory=list)
    kind_params: dict = field(default_factory=dict)


@dataclass
class Workstream:
    name: str
    branch: str
    phases: list[PlanPhase] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


@dataclass
class PlanDefinition:
    name: str
    description: str
    phases: list[PlanPhase]


@dataclass
class PlanState:
    status: str = "pending"
    jobs_total: int = 0
    jobs_done: int = 0

    def to_dict(self) -> dict:
        return {"status": self.status, "jobs_total": str(self.jobs_total), "jobs_done": str(self.jobs_done)}

    @classmethod
    def from_dict(cls, d: dict) -> PlanState:
        return cls(
            status=d.get("status", "pending"),
            jobs_total=int(d.get("jobs_total", 0)),
            jobs_done=int(d.get("jobs_done", 0)),
        )


# ── YAML loader ──────────────────────────────────────────────────


def load_plans(path: Path) -> dict[str, PlanDefinition]:
    with open(path) as f:
        data = yaml.safe_load(f)

    plans: dict[str, PlanDefinition] = {}
    for name, plan_data in data.get("plans", {}).items():
        phases = [_parse_phase(p) for p in plan_data.get("phases", [])]
        plans[name] = PlanDefinition(
            name=name,
            description=plan_data.get("description", ""),
            phases=phases,
        )

    return plans


def _parse_phase(p: dict) -> PlanPhase:
    if "id" not in p or "kind" not in p:
        raise ValueError(f"phase missing required 'id'/'kind': {p!r}")
    reserved = ("id", "kind", "description", "depends_on")
    kind_params = {k: v for k, v in p.items() if k not in reserved}
    if p["kind"] == "fan_out":
        kind_params["workstreams"] = _parse_workstreams(p.get("workstreams", {}))
    return PlanPhase(
        id=p["id"],
        kind=p["kind"],
        description=p.get("description", ""),
        depends_on=p.get("depends_on", []),
        kind_params=kind_params,
    )


def _parse_workstreams(raw: dict) -> dict[str, Workstream]:
    workstreams: dict[str, Workstream] = {}
    for name, ws in raw.items():
        sub_phases = [_parse_phase(sp) for sp in ws.get("phases", [])]
        workstreams[name] = Workstream(
            name=name,
            branch=ws.get("branch", f"feature/{name}"),
            phases=sub_phases,
            depends_on=ws.get("depends_on", []),
        )
    return workstreams


# ── DAG validation ────────────────────────────────────────────────


def validate_plan(plan: PlanDefinition) -> list[str]:
    errors: list[str] = []
    phase_ids = {p.id for p in plan.phases}

    if not phase_ids:
        return ["Plan has no phases"]

    for phase in plan.phases:
        for dep in phase.depends_on:
            if dep not in phase_ids:
                errors.append(f"Phase '{phase.id}' depends on unknown phase '{dep}'")

    cycles = _detect_cycles(plan)
    if cycles:
        errors.append(f"Cycle detected: {' → '.join(cycles)}")

    return errors


def _detect_cycles(plan: PlanDefinition) -> list[str] | None:
    adj = {p.id: list(p.depends_on) for p in plan.phases}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {p.id: WHITE for p in plan.phases}

    def dfs(node: str, path: list[str]) -> list[str] | None:
        color[node] = GRAY
        path.append(node)
        for neighbor in adj.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                idx = path.index(neighbor)
                return path[idx:] + [neighbor]
            if color[neighbor] == WHITE:
                result = dfs(neighbor, list(path))
                if result:
                    return result
        color[node] = BLACK
        return None

    for pid in adj:
        if color[pid] == WHITE:
            result = dfs(pid, [])
            if result:
                return result
    return None


def topological_order(plan: PlanDefinition) -> list[list[str]]:
    in_degree = {p.id: len(p.depends_on) for p in plan.phases}
    dependents: dict[str, list[str]] = {p.id: [] for p in plan.phases}
    for p in plan.phases:
        for dep in p.depends_on:
            dependents[dep].append(p.id)

    levels: list[list[str]] = []
    ready = [pid for pid, deg in in_degree.items() if deg == 0]

    while ready:
        levels.append(sorted(ready))
        next_ready = []
        for pid in ready:
            for dep in dependents[pid]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    next_ready.append(dep)
        ready = next_ready

    return levels


def workstream_waves(workstreams: dict[str, Workstream]) -> list[list[str]]:
    in_degree = {name: len(ws.depends_on) for name, ws in workstreams.items()}
    dependents: dict[str, list[str]] = {name: [] for name in workstreams}
    for name, ws in workstreams.items():
        for dep in ws.depends_on:
            if dep in dependents:
                dependents[dep].append(name)

    waves: list[list[str]] = []
    ready = [name for name, deg in in_degree.items() if deg == 0]

    while ready:
        waves.append(sorted(ready))
        next_ready = []
        for name in ready:
            for dep in dependents.get(name, []):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    next_ready.append(dep)
        ready = next_ready

    return waves


# ── Redis helpers ─────────────────────────────────────────────────

_PLAN_PREFIX = "pipeline"


def _r():
    import redis
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


def _phase_key(plan_name: str, phase_id: str) -> str:
    return f"{_PLAN_PREFIX}:{plan_name}:phase:{phase_id}"


def _current_key(plan_name: str) -> str:
    return f"{_PLAN_PREFIX}:{plan_name}:current"


def _get_state(plan_name: str, phase_id: str) -> PlanState:
    try:
        r = _r()
        raw = r.hgetall(_phase_key(plan_name, phase_id))
        return PlanState.from_dict(raw)
    except Exception:
        return PlanState()


def _set_state(plan_name: str, phase_id: str, **kwargs) -> None:
    try:
        r = _r()
        r.hset(_phase_key(plan_name, phase_id), mapping={k: str(v) for k, v in kwargs.items()})
    except Exception as e:
        # State writes must not be silently swallowed (P1-4): telemetry may
        # no-op, but phase state is the control plane's source of truth.
        print(f"WARNING: failed to write state {plan_name}/{phase_id}: {e}", file=sys.stderr)


# ── Worker lifecycle ──────────────────────────────────────────────


def _workers_alive(worker_script: str) -> int:
    result = subprocess.run(
        ["pgrep", "-f", worker_script],
        capture_output=True, text=True,
    )
    return len(result.stdout.strip().splitlines()) if result.returncode == 0 else 0


def _spawn_workers(worker_script: str, count: int, log_tag: str) -> list[subprocess.Popen]:
    procs = []
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        log_file = LOG_DIR / f"worker_{log_tag}_{i + 1}.log"
        p = subprocess.Popen(
            ["nohup", sys.executable, worker_script],
            stdout=open(log_file, "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        procs.append(p)
    return procs


# ── Phase kind executors ──────────────────────────────────────────


def _substitute_template(cmd: list[str], context: dict) -> list[str]:
    return [arg.format(**context) for arg in cmd]


def _resolve_cwd(phase: PlanPhase, context: dict) -> str:
    return context.get("cwd") or phase.kind_params.get("cwd", str(ROOT))


def _execute_shell(phase: PlanPhase, context: dict) -> bool:
    cmd = _substitute_template(phase.kind_params.get("cmd", []), context)
    if not cmd:
        return True

    cwd = _resolve_cwd(phase, context)
    timeout = phase.kind_params.get("timeout", 600)

    try:
        result = subprocess.run(cmd, cwd=cwd, timeout=timeout)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"  Timed out after {timeout}s")
        return False
    except FileNotFoundError as e:
        print(f"  Command not found: {e}")
        return False


def _execute_test(phase: PlanPhase, context: dict) -> bool:
    cmd = phase.kind_params.get("cmd")
    if cmd:
        test_cmd = _substitute_template(cmd, context)
    else:
        pytest_args = phase.kind_params.get("pytest_args", ["-v"])
        test_cmd = [sys.executable, "-m", "pytest"] + pytest_args

    cwd = _resolve_cwd(phase, context)
    timeout = phase.kind_params.get("timeout", 600)
    try:
        result = subprocess.run(test_cmd, cwd=cwd, timeout=timeout)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"  Tests timed out after {timeout}s")
        return False
    except FileNotFoundError:
        print("  pytest not found")
        return False


def _execute_lint(phase: PlanPhase, context: dict) -> bool:
    ok = True
    cwd = _resolve_cwd(phase, context)

    ruff_args = phase.kind_params.get("ruff_args", ["check", "."])
    ruff_cmd = ["ruff"] + ruff_args
    r = subprocess.run(ruff_cmd, cwd=cwd)
    if r.returncode != 0:
        ok = False

    if phase.kind_params.get("mypy"):
        mypy_dirs = phase.kind_params.get("mypy_dirs", ["src/"])
        mypy_cmd = ["mypy"] + mypy_dirs
        m = subprocess.run(mypy_cmd, cwd=cwd)
        if m.returncode != 0:
            ok = False

    return ok


def _gen_matrix_cells(kind_params: dict) -> list[dict]:
    model = kind_params["model"]
    model_filter = kind_params.get("model_filter", model.split("/")[-1])
    stories = kind_params.get("stories", ["task_manager_api", "static_site_gen", "notification_service"])
    tiers = kind_params.get("tiers", ["tier1_minimal", "tier2_small"])
    conditions = kind_params.get("conditions", {
        "good": ["clean", "bad_seed", "early_degrade"],
        "bad": ["clean", "early_degrade"],
    })

    completed = _completed_cells(model_filter, stories, conditions)
    jobs = []
    for story in stories:
        for tier in tiers:
            for quality, conds in conditions.items():
                for condition in conds:
                    key = f"{story}|{tier}|{quality}|{condition}"
                    if key in completed:
                        continue
                    slug = model.split("/", 1)[-1].replace("-", "_").replace(".", "_")
                    short = f"{slug}_{story}_{tier}_{quality}_{condition}"
                    jobs.append({
                        "cell_id": short,
                        "story": story, "tier": tier,
                        "quality": quality, "condition": condition,
                        "model": model,
                    })
    return jobs


def _completed_cells(model_filter: str, stories: list[str], conditions: dict) -> set[str]:
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
        if story.story_name not in stories:
            continue
        condition = story.perturbation_condition or ""
        if not condition:
            for cond in ["bad_seed", "early_degrade", "clean"]:
                if cond in f.name:
                    condition = cond
                    break
        cp = Path(story.codebase_path or "")
        tier = cp.parts[-2] if len(cp.parts) >= 2 else "?"
        quality = cp.parts[-1] if len(cp.parts) >= 2 else "?"
        completed.add(f"{story.story_name}|{tier}|{quality}|{condition}")
    return completed


def _execute_matrix(phase: PlanPhase, context: dict) -> bool:
    rdb = _r()
    plan_name = context.get("plan_name", "matrix")
    kind_params = phase.kind_params
    workers = kind_params.get("workers", 4)

    state = _get_state(plan_name, phase.id)

    if state.status == "done":
        return True

    if state.status == "pending":
        jobs = _gen_matrix_cells(kind_params)
        if not jobs:
            _set_state(plan_name, phase.id, status="done")
            return True

        for job in jobs:
            rdb.lpush(STORY_QUEUE, json.dumps(job))
            rdb.hset(STORY_STATUS, job["cell_id"], "queued")

        _set_state(plan_name, phase.id, status="running", jobs_total=len(jobs))
        _set_current(plan_name, phase.id)

    if state.status in ("pending", "running"):
        _set_current(plan_name, phase.id)

        alive = _workers_alive("scripts/worker.py")
        queue_size = rdb.llen(STORY_QUEUE)
        if queue_size > 0 and alive < workers:
            needed = workers - alive
            print(f"  Launching {needed} workers...")
            _spawn_workers("scripts/worker.py", needed, phase.id)

        done = sum(1 for v in rdb.hgetall(STORY_STATUS).values()
                   if v in ("done", "failed"))
        total = state.jobs_total or len(_gen_matrix_cells(kind_params)) + done
        pct = f"{done}/{total}" if total > 0 else "?"
        print(f"  {pct} done, {queue_size} in queue, {alive} workers")

        if queue_size == 0 and done >= total and total > 0:
            _set_state(plan_name, phase.id, status="done", jobs_done=done)
            return True

    return False


def _execute_review(phase: PlanPhase, context: dict) -> bool:
    from instrument.story import load_story_result

    rdb = _r()
    plan_name = context.get("plan_name", "review")
    kind_params = phase.kind_params
    workers = kind_params.get("workers", 4)
    review_model = kind_params.get("review_model", "deepseek/deepseek-v4-flash")

    state = _get_state(plan_name, phase.id)

    if state.status == "done":
        return True

    if state.status == "pending":
        jobs = _gen_review_jobs(review_model)
        if not jobs:
            _set_state(plan_name, phase.id, status="done")
            return True

        for job in jobs:
            rdb.lpush(REVIEW_QUEUE, json.dumps(job))
            jid = job.get("job_id", "?")
            rdb.hset(REVIEW_STATUS, jid, "queued")

        _set_state(plan_name, phase.id, status="running", jobs_total=len(jobs))
        _set_current(plan_name, phase.id)

    if state.status in ("pending", "running"):
        _set_current(plan_name, phase.id)

        alive = _workers_alive("scripts/review_worker.py")
        queue_size = rdb.llen(REVIEW_QUEUE)
        if queue_size > 0 and alive < workers:
            needed = workers - alive
            print(f"  Launching {needed} review workers...")
            _spawn_workers("scripts/review_worker.py", needed, phase.id)

        done = sum(1 for v in rdb.hgetall(REVIEW_STATUS).values()
                   if v in ("done", "failed"))
        total = state.jobs_total
        pct = f"{done}/{total}" if total > 0 else "?"
        print(f"  {pct} done, {queue_size} in queue, {alive} workers")

        if queue_size == 0 and done >= total and total > 0:
            _set_state(plan_name, phase.id, status="done", jobs_done=done)
            return True

    return False


def _gen_review_jobs(review_model: str) -> list[dict]:
    from instrument.story import load_story_result

    results_dir = ROOT / "experiments" / "results" / "stories"
    reviews_dir = ROOT / "experiments" / "results" / "reviews"
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
                if existing.get("story_review") and len(existing.get("commit_reviews", [])) >= 4:
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
                "model": review_model,
            })

        jobs.append({
            "job_id": f"{story.story_id}_story",
            "story_name": story.story_name, "story_id": story.story_id,
            "worktree": str(wt), "commit_hash": "", "commit_message": "",
            "session_number": 0, "model": review_model,
            "job_type": "story_review",
        })
    return jobs


def _execute_pipeline(phase: PlanPhase, context: dict) -> bool:
    steps = phase.kind_params.get("steps", [])
    timeout = phase.kind_params.get("timeout", 300)
    cwd = _resolve_cwd(phase, context)

    for step in steps:
        cmd = _substitute_template(step, context)
        print(f"  Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, cwd=cwd, timeout=timeout)
            if result.returncode != 0:
                print(f"  Step failed with exit code {result.returncode}")
                return False
        except subprocess.TimeoutExpired:
            print(f"  Step timed out after {timeout}s")
            return False
        except FileNotFoundError as e:
            print(f"  Command not found: {e}")
            return False

    return True


def _execute_ship(phase: PlanPhase, context: dict) -> bool:
    remote = phase.kind_params.get("remote", "origin")
    cwd = _resolve_cwd(phase, context)

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=cwd, timeout=10,
    )
    if status.stdout.strip():
        print("  Working tree dirty — commit before shipping")
        return False

    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, cwd=cwd, timeout=10,
    ).stdout.strip()

    if branch in ("main", "master"):
        print(f"  On {branch} — ship is for feature branches")
        return False

    print(f"  Merging {branch} into main...")
    subprocess.run(["git", "checkout", "main"], cwd=cwd, timeout=30)
    result = subprocess.run(
        ["git", "merge", "--squash", branch], cwd=cwd, timeout=30,
    )
    if result.returncode != 0:
        print("  Merge conflict — resolve manually")
        subprocess.run(["git", "checkout", branch], cwd=cwd, timeout=10)
        return False

    commit_result = subprocess.run(
        ["git", "commit", "-m", phase.kind_params.get("message", f"Merge {branch}")],
        cwd=cwd, timeout=30,
    )
    push_result = subprocess.run(
        ["git", "push", remote, "main"], cwd=cwd, timeout=60,
    )
    subprocess.run(["git", "checkout", branch], cwd=cwd, timeout=10)
    return push_result.returncode == 0


# ── Workstream sidecar ────────────────────────────────────────────

SIDECAR_DIR = ROOT / "experiments" / "results" / "workstreams"


def _sidecar_path(plan_name: str, phase_id: str) -> Path:
    return SIDECAR_DIR / f"{plan_name}_{phase_id}.json"


def _write_sidecar(plan_name: str, phase_id: str, workstreams: dict[str, dict]) -> None:
    SIDECAR_DIR.mkdir(parents=True, exist_ok=True)
    _sidecar_path(plan_name, phase_id).write_text(json.dumps(workstreams, indent=2))


def _load_sidecar(plan_name: str, phase_id: str) -> dict[str, dict]:
    path = _sidecar_path(plan_name, phase_id)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _default_branch(cwd: str) -> str:
    result = subprocess.run(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        capture_output=True, text=True, cwd=cwd, timeout=10,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().removeprefix("origin/")
    for candidate in ("main", "master"):
        check = subprocess.run(
            ["git", "rev-parse", "--verify", candidate],
            capture_output=True, text=True, cwd=cwd, timeout=10,
        )
        if check.returncode == 0:
            return candidate
    return "main"


def _git_clean(cwd: str) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=cwd, timeout=10,
    )
    return not result.stdout.strip()


def _create_worktree(branch: str, base: str, root: str) -> Path | None:
    wt = Path(root) / branch.replace("/", "_")
    if wt.exists():
        shutil.rmtree(wt)

    result = subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(wt), base],
        capture_output=True, text=True, cwd=str(ROOT), timeout=120,
    )
    if result.returncode != 0:
        print(f"  Failed to create worktree for '{branch}': {result.stderr.strip()}")
        return None
    return wt


def _commit_workstream(wt: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=str(wt), timeout=30)
    subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True, cwd=str(wt), timeout=30,
    )


def _run_workstream(ws: Workstream, wt: Path, context: dict) -> bool:
    print(f"  [{ws.name}] started (branch={ws.branch})")
    ctx = dict(context)
    ctx["cwd"] = str(wt)

    for sub_phase in ws.phases:
        executor = EXECUTORS.get(sub_phase.kind)
        if executor is None:
            print(f"  [{ws.name}] unknown sub-phase kind '{sub_phase.kind}'")
            return False
        print(f"  [{ws.name}] phase '{sub_phase.id}' ({sub_phase.kind})...")
        if not executor(sub_phase, ctx):
            print(f"  [{ws.name}] phase '{sub_phase.id}' FAILED")
            return False

    _commit_workstream(wt, f"workstream: {ws.name}")
    print(f"  [{ws.name}] complete")
    return True


def _execute_fan_out(phase: PlanPhase, context: dict) -> bool:
    plan_name = context.get("plan_name", "plan")
    kind_params = phase.kind_params
    workstreams: dict[str, Workstream] = kind_params.get("workstreams", {})
    base = kind_params.get("base_branch") or _default_branch(str(ROOT))
    worktree_root = kind_params.get("worktree_root", "/tmp/pipeline")

    if not workstreams:
        _set_state(plan_name, phase.id, status="done")
        return True

    if not _git_clean(str(ROOT)):
        print("  Main repo dirty — commit or stash before fan_out")
        return False

    # Create worktrees sequentially (git worktree add is not parallel-safe)
    worktrees: dict[str, Path] = {}
    sidecar: dict[str, dict] = {}
    for name, ws in workstreams.items():
        wt = _create_worktree(ws.branch, base, worktree_root)
        if wt is None:
            print(f"  Workstream '{name}' worktree creation failed")
            return False
        worktrees[name] = wt
        sidecar[name] = {
            "branch": ws.branch,
            "worktree": str(wt),
            "status": "pending",
            "base_branch": base,
        }

    _write_sidecar(plan_name, phase.id, sidecar)
    _set_state(plan_name, phase.id, status="running", jobs_total=len(workstreams))
    _set_current(plan_name, phase.id)

    # Run workstreams in dependency-ordered waves, parallel within each wave
    waves = workstream_waves(workstreams)
    for wave in waves:
        wave_ws = {name: workstreams[name] for name in wave}
        with ThreadPoolExecutor(max_workers=len(wave)) as pool:
            futures = {
                pool.submit(_run_workstream, ws, worktrees[name], context): name
                for name, ws in wave_ws.items()
            }
            for future in as_completed(futures):
                name = futures[future]
                ok = future.result()
                sidecar[name]["status"] = "done" if ok else "failed"
                _write_sidecar(plan_name, phase.id, sidecar)
                if not ok:
                    print(f"  Workstream '{name}' failed — aborting fan_out")
                    pool.shutdown(wait=False, cancel_futures=True)
                    return False

    done = sum(1 for s in sidecar.values() if s["status"] == "done")
    _set_state(plan_name, phase.id, status="done", jobs_done=done)
    print(f"  fan_out complete: {done}/{len(workstreams)} workstreams done")
    return True


def _execute_conflict_detect(phase: PlanPhase, context: dict) -> bool:
    plan_name = context.get("plan_name", "plan")
    kind_params = phase.kind_params
    from_fanout = kind_params.get("from_fanout")
    base = kind_params.get("base_branch") or _default_branch(str(ROOT))
    sidecar = _load_sidecar(plan_name, from_fanout or "")

    if not sidecar:
        print(f"  No workstream sidecar found for fan_out '{from_fanout}'")
        return False

    conflicts = []
    for name, ws in sidecar.items():
        branch = ws["branch"]
        pair = _detect_conflicts(base, branch)
        if pair:
            conflicts.append((name, branch, pair))

    if conflicts:
        print(f"  Conflicts detected:")
        for name, branch, files in conflicts:
            print(f"    {name} ({branch}): {', '.join(files)}")
        return False

    print(f"  No merge conflicts across {len(sidecar)} branches")
    return True


def _detect_conflicts(base: str, branch: str, cwd: str | None = None) -> list[str]:
    repo = cwd or str(ROOT)
    ff = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base, branch],
        capture_output=True, cwd=repo, timeout=30,
    )
    if ff.returncode == 0:
        return []

    mb = subprocess.run(
        ["git", "merge-base", base, branch],
        capture_output=True, text=True, cwd=repo, timeout=30,
    )
    merge_base = mb.stdout.strip()
    if not merge_base:
        return []

    result = subprocess.run(
        ["git", "merge-tree", merge_base, base, branch],
        capture_output=True, text=True, cwd=repo, timeout=60,
    )
    out = result.stdout + result.stderr
    if "changed in both" not in out and "<<<<<<<" not in out:
        return []

    files = set()
    for line in out.splitlines():
        m = re.match(r"\s+(?:base|our|their)\s+\d+\s+[0-9a-f]+\s+(.+)", line)
        if m:
            files.add(m.group(1).strip())
    return sorted(files)


def _execute_pr_create(phase: PlanPhase, context: dict) -> bool:
    plan_name = context.get("plan_name", "plan")
    kind_params = phase.kind_params
    from_fanout = kind_params.get("from_fanout")
    base = kind_params.get("base_branch") or _default_branch(str(ROOT))
    title_template = kind_params.get("title", "Workstream: {name}")
    sidecar = _load_sidecar(plan_name, from_fanout or "")

    if not sidecar:
        print(f"  No workstream sidecar found for fan_out '{from_fanout}'")
        return False

    ok = True
    for name, ws in sidecar.items():
        branch = ws["branch"]
        title = title_template.format(name=name)

        existing = subprocess.run(
            ["gh", "pr", "view", branch, "--json", "url"],
            capture_output=True, text=True, timeout=60,
        )
        if existing.returncode == 0:
            print(f"  PR already exists for {branch} — skipping")
            continue

        push = subprocess.run(
            ["git", "push", "-u", "origin", branch],
            capture_output=True, text=True, timeout=120,
        )
        if push.returncode != 0:
            print(f"  Push failed for {branch}: {push.stderr.strip()}")
            ok = False
            continue

        create = subprocess.run(
            ["gh", "pr", "create", "--base", base, "--head", branch, "--title", title],
            capture_output=True, text=True, timeout=120,
        )
        if create.returncode != 0:
            print(f"  PR creation failed for {branch}: {create.stderr.strip()}")
            ok = False
        else:
            print(f"  PR created for {branch}")

    return ok


def _execute_pr_merge(phase: PlanPhase, context: dict) -> bool:
    plan_name = context.get("plan_name", "plan")
    kind_params = phase.kind_params
    from_fanout = kind_params.get("from_fanout")
    base = kind_params.get("base_branch") or _default_branch(str(ROOT))
    strategy = kind_params.get("conflict_strategy", "rebase")
    squash = kind_params.get("squash", True)
    sidecar = _load_sidecar(plan_name, from_fanout or "")

    if not sidecar:
        print(f"  No workstream sidecar found for fan_out '{from_fanout}'")
        return False

    merge_flag = "--squash" if squash else "--merge"
    ok = True

    for name, ws in sidecar.items():
        branch = ws["branch"]
        merge = subprocess.run(
            ["gh", "pr", "merge", branch, merge_flag],
            capture_output=True, text=True, timeout=180,
        )

        if merge.returncode != 0:
            if strategy == "abort":
                print(f"  Merge failed for {branch}: {merge.stderr.strip()}")
                ok = False
                continue
            print(f"  Merge conflict on {branch} — retrying with {strategy}...")

            subprocess.run(
                ["git", "worktree", "add", "--detach", str(Path("/tmp/pipeline") / f"merge_{name}"), branch],
                capture_output=True, cwd=str(ROOT), timeout=120,
            )
            merge_wt = Path("/tmp/pipeline") / f"merge_{name}"
            rebase = subprocess.run(
                ["git", "rebase", base],
                capture_output=True, text=True, cwd=str(merge_wt), timeout=120,
            )
            if rebase.returncode != 0:
                subprocess.run(["git", "rebase", "--abort"], cwd=str(merge_wt), timeout=30)
                print(f"  Rebase conflict on {branch} — requires manual resolution")
                ok = False
                continue

            push = subprocess.run(
                ["git", "push", "--force-with-lease"],
                capture_output=True, text=True, cwd=str(merge_wt), timeout=120,
            )
            if push.returncode != 0:
                print(f"  Force-push failed for {branch}")
                ok = False
                continue

            merge = subprocess.run(
                ["gh", "pr", "merge", branch, merge_flag],
                capture_output=True, text=True, timeout=180,
            )
            if merge.returncode != 0:
                print(f"  Merge retry failed for {branch}")
                ok = False
                continue

        print(f"  Merged {branch}")

    return ok


# ── Kind dispatch table ────────────────────────────────────────────

EXECUTORS: dict[str, Any] = {
    "shell": _execute_shell,
    "test": _execute_test,
    "lint": _execute_lint,
    "matrix": _execute_matrix,
    "review": _execute_review,
    "pipeline": _execute_pipeline,
    "ship": _execute_ship,
    "fan_out": _execute_fan_out,
    "conflict_detect": _execute_conflict_detect,
    "pr_create": _execute_pr_create,
    "pr_merge": _execute_pr_merge,
}


# ── Plan runner ───────────────────────────────────────────────────

# Max wall-clock (seconds) a polling phase (matrix/review) may run before the
# runner aborts rather than polling forever (P1-4).
MAX_PHASE_WALLCLOCK = int(os.environ.get("FINOPS_MAX_PHASE_WALLCLOCK", str(6 * 3600)))


def _set_current(plan_name: str, phase_id: str) -> None:
    try:
        _r().set(_current_key(plan_name), phase_id)
    except Exception as e:
        print(f"WARNING: failed to set current phase for {plan_name}: {e}", file=sys.stderr)


def _interpolate_levels(levels: list[list[str]], from_phase: str | None,
                        until_phase: str | None, only_phases: list[str] | None) -> list[list[str]]:
    started = from_phase is None
    result = []
    for level in levels:
        if from_phase and not started:
            if from_phase in level:
                started = True
            else:
                continue
        if until_phase and until_phase in level:
            if only_phases:
                level = [p for p in level if p in only_phases]
            result.append(level)
            return result
        if only_phases:
            filtered = [p for p in level if p in only_phases]
            if filtered:
                result.append(filtered)
        else:
            result.append(level)
    return result


def run_plan(plan: PlanDefinition, *, from_phase: str | None = None,
             until_phase: str | None = None, only_phases: list[str] | None = None,
             dry_run: bool = False, prompt: str = "", workers_override: int | None = None):
    rdb = _r()
    try:
        rdb.ping()
    except Exception:
        print("Redis unavailable — required for state tracking")
        return

    levels = topological_order(plan)
    levels = _interpolate_levels(levels, from_phase, until_phase, only_phases)

    phase_map = {p.id: p for p in plan.phases}

    if dry_run:
        print(f"\nPlan: {plan.name} — {plan.description}")
        print(f"Pipeline levels: {len(levels)}")
        for i, level in enumerate(levels):
            print(f"  Level {i + 1}: {', '.join(level)}")
        return

    context = {"plan_name": plan.name, "prompt": prompt}
    if workers_override:
        context["workers_override"] = workers_override

    for level in levels:
        for pid in level:
            phase = phase_map[pid]
            if workers_override:
                phase.kind_params["workers"] = workers_override

            print(f"\n{'=' * 60}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {phase.id} — kind={phase.kind}")
            deps = phase.depends_on or ["none"]
            print(f"  Deps: {deps}")

            executor = EXECUTORS.get(phase.kind)
            if executor is None:
                print(f"  Unknown kind '{phase.kind}' — skipping")
                continue

            if phase.kind in ("matrix", "review"):
                # These executors poll internally — loop until done
                deadline = time.monotonic() + MAX_PHASE_WALLCLOCK
                while not executor(phase, context):
                    if time.monotonic() > deadline:
                        print(f"  Phase '{phase.id}' exceeded {MAX_PHASE_WALLCLOCK}s wall-clock — aborting")
                        return
                    time.sleep(30)
            else:
                # Synchronous executors — run once
                ok = executor(phase, context)
                if not ok:
                    print(f"  Phase '{phase.id}' failed")
                    return
                _set_state(plan.name, phase.id, status="done")

    print(f"\n{'=' * 60}")
    print(f"Plan '{plan.name}' complete.")


# ── Status & utilities ────────────────────────────────────────────


def show_graph(plan: PlanDefinition) -> None:
    levels = topological_order(plan)
    for i, level in enumerate(levels):
        if i == 0:
            prefix = "▶"
        else:
            prefix = " ├─"
        ids = ", ".join(level)
        print(f"  {prefix} {ids}")


def show_status(plan: PlanDefinition) -> None:
    try:
        _r().ping()
    except Exception as e:
        print(f"Redis unavailable: {e}")
        return

    current = _safe_get(_current_key(plan.name), "(none)")
    print(f"Plan: {plan.name}  |  Current phase: {current}\n")

    for phase in plan.phases:
        state = _get_state(plan.name, phase.id)
        marker = "→" if phase.id == current else " "
        workers = 0
        if phase.kind == "matrix":
            workers = _workers_alive("scripts/worker.py")
        elif phase.kind == "review":
            workers = _workers_alive("scripts/review_worker.py")
        s = state.status
        d = state.jobs_done
        t = state.jobs_total
        print(f"  {marker} {phase.id:20s} {s:10s}  {d}/{t} done  workers={workers}")


def _safe_get(key: str, default: str = "") -> str:
    try:
        return _r().get(key) or default
    except Exception:
        return default


def reset_plan(plan: PlanDefinition) -> None:
    try:
        rdb = _r()
        rdb.delete(_current_key(plan.name))
        for phase in plan.phases:
            rdb.delete(_phase_key(plan.name, phase.id))
        print(f"Plan '{plan.name}' state reset.")
    except Exception as e:
        print(f"Redis error: {e}")


# ── CLI ───────────────────────────────────────────────────────────


def main():
    args = sys.argv[1:]
    plan_path = ROOT / "experiments" / "configs" / "plans.yaml"

    if not plan_path.exists():
        print(f"Config not found: {plan_path}")
        sys.exit(1)

    plans = load_plans(plan_path)

    plan_name = "ci"
    for i, arg in enumerate(args):
        if arg == "--plan" and i + 1 < len(args):
            plan_name = args[i + 1]
            break
        elif arg.startswith("--plan="):
            plan_name = arg.split("=", 1)[1]
            break

    if plan_name not in plans:
        print(f"Plan '{plan_name}' not found. Available: {', '.join(sorted(plans))}")
        sys.exit(1)

    plan = plans[plan_name]

    if "--check-deps" in args:
        errors = validate_plan(plan)
        if errors:
            for e in errors:
                print(f"  ERROR: {e}")
            sys.exit(1)
        print("  All dependencies valid, no cycles detected.")
        return

    if "--graph" in args:
        show_graph(plan)
        return

    if "--status" in args:
        show_status(plan)
        return

    if "--reset" in args:
        reset_plan(plan)
        return

    dry_run = "--dry-run" in args

    from_phase = None
    until_phase = None
    only_phases = None
    prompt = ""
    workers_override = None

    for i, arg in enumerate(args):
        if arg.startswith("--from="):
            from_phase = arg.split("=", 1)[1]
        elif arg == "--from" and i + 1 < len(args):
            from_phase = args[i + 1]
        elif arg.startswith("--until="):
            until_phase = arg.split("=", 1)[1]
        elif arg == "--until" and i + 1 < len(args):
            until_phase = args[i + 1]
        elif arg.startswith("--only="):
            only_phases = arg.split("=", 1)[1].split(",")
        elif arg == "--only" and i + 1 < len(args):
            only_phases = args[i + 1].split(",")
        elif arg.startswith("--prompt="):
            prompt = arg.split("=", 1)[1]
        elif arg == "--prompt" and i + 1 < len(args):
            prompt = args[i + 1]
        elif arg.startswith("--workers="):
            workers_override = int(arg.split("=", 1)[1])
        elif arg == "--workers" and i + 1 < len(args):
            workers_override = int(args[i + 1])

    run_plan(
        plan,
        from_phase=from_phase,
        until_phase=until_phase,
        only_phases=only_phases,
        dry_run=dry_run,
        prompt=prompt,
        workers_override=workers_override,
    )


if __name__ == "__main__":
    main()
