#!/usr/bin/env python3
"""Run the pre-registered flash-exploration ladder cells (4 conditions x 3 reps).

The campaign executor for `flash_ladder_bare` / `flash_ladder_kb` (pinned in the
pre-registration addendum). Design goals — the "don't break the back" rails:

* **Sequential dispatch only** (the fleet runs one orchestrator at a time): one
  ``docker-compose run workflow-runner … --orchestrator`` at a time, each with a bounded
  wall-clock timeout; no queue, no parallel cells, no touching the framework Redis.
* **Fresh detached cell worktree per cell** cut from the recorded ladder base SHA; the run's
  own private clone is the world the phases commit in.
* **No live-KB writes from cells**: ``--no-fact-emit`` plus ``FINOPS_EMIT_SELF=0`` (and the
  specs pin ``rag.emit_self: false``).
* **Durable, small per-cell evidence**: the generated ``taskman/`` tree + the diff are exported
  under ``experiments/results/flash_ladder/cells/<cell>/`` so scoring never depends on the
  ephemeral run clone.
* **Resumable + fail-closed**: a recorded cell is skipped unless ``--force``; an infra failure
  halts the campaign by default.

    python3 scripts/run_flash_ladder.py --dry-run
    python3 scripts/run_flash_ladder.py --cells C0-r1,C0-r2
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

REPO_ROOT = Path(__file__).resolve().parent.parent
LADDER_DIR = REPO_ROOT / "experiments" / "results" / "flash_ladder"
CELLS_DIR = LADDER_DIR / "cells"
CELL_WORKTREES = Path("/tmp/flash_ladder_cells")
COMPOSE_FILE = REPO_ROOT / "infrastructure" / "docker-compose.ladder.yml"
MODEL = "deepseek/deepseek-v4-flash"
CONTRACT_TEST = "tests/flash_ladder/taskman_contract_test.py"

BRIEF = (
    "Implement a pure-Python, stdlib-only package `taskman` (with `TaskManager`) in this "
    "worktree that satisfies the behavioural contract in tests/flash_ladder/taskman_contract_test.py. "
    "Do not modify any test file."
)
FRAMING = (
    " Before implementing, enumerate at least three materially different internal designs "
    "(data model, ordering, persistence, cycle detection), then implement the design you judge "
    "most different from the most obvious approach."
)

CONDITIONS: dict[str, dict] = {
    "C0": {"spec": "workflows/repository/flash_ladder_bare.yaml", "goal_suffix": "", "budget": 0},
    "C1": {
        "spec": "workflows/repository/flash_ladder_bare.yaml",
        "goal_suffix": FRAMING,
        "budget": 0,
    },
    "C2": {
        "spec": "workflows/repository/flash_ladder_bare.yaml",
        "goal_suffix": "",
        "budget": 32000,
    },
    "C3": {
        "spec": "workflows/repository/flash_ladder_kb.yaml",
        "goal_suffix": "",
        "budget": 0,
    },
}

#: The pre-registered assignment table, in order: 4 conditions x 3 independent repetitions.
ASSIGNMENT: tuple[tuple[str, str, int], ...] = tuple(
    (f"{condition}-r{rep}", condition, rep)
    for condition in ("C0", "C1", "C2", "C3")
    for rep in (1, 2, 3)
)


@dataclass(frozen=True)
class CellPlan:
    cell_id: str
    condition: str
    rep: int
    spec: str
    goal: str
    thinking_budget: int


def build_cell_plan() -> list[CellPlan]:
    """The 12 cells in the pre-registered order (assignment table, no reseeding)."""
    plans: list[CellPlan] = []
    for cell_id, condition, rep in ASSIGNMENT:
        config = CONDITIONS[condition]
        plans.append(
            CellPlan(
                cell_id=cell_id,
                condition=condition,
                rep=rep,
                spec=str(config["spec"]),
                goal=BRIEF + str(config["goal_suffix"]),
                thinking_budget=int(config["budget"]),
            )
        )
    return plans


def cell_command(plan: CellPlan, *, workdir: Path, deploy_repo: Path) -> list[str]:
    """The documented dispatch command for one cell (compose → orchestrator → sibling cells)."""
    command = [
        "docker-compose",
        "-f",
        str(COMPOSE_FILE),
        "run",
        "--rm",
        "workflow-runner",
        "python3",
        "scripts/run_workflow.py",
        "--orchestrator",
        "--spec",
        plan.spec,
        "--goal",
        plan.goal,
        "--model",
        MODEL,
        "--workdir",
        str(workdir),
        "--no-fact-emit",
    ]
    if plan.thinking_budget:
        command += ["--thinking-budget-tokens", str(plan.thinking_budget)]
    return command


def _cell_env(deploy_repo: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["FINOPS_REPO_DIR"] = str(deploy_repo)
    env["FINOPS_EMIT_SELF"] = "0"
    return env


def _run_worktree_add(base_sha: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "-C", str(REPO_ROOT), "worktree", "add", "--detach", str(path), base_sha],
        check=True,
        capture_output=True,
        text=True,
    )


def _newest_ledger(spec_name: str) -> Path | None:
    ledger_dir = LADDER_DIR.parent / "workflows" / spec_name
    if not ledger_dir.is_dir():
        return None
    ledgers = sorted(ledger_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    return ledgers[-1] if ledgers else None


def _parse_run_id(stdout: str) -> str:
    for line in stdout.splitlines():
        if "control: run " in line and "(running)" in line:
            return line.split("control: run ", 1)[1].split()[0]
    return ""


def _export_cell(run_clone: Path, sha: str, base_sha: str, export_dir: Path) -> dict:
    """Export the generated tree + diff so scoring never depends on the ephemeral clone."""
    export_dir.mkdir(parents=True, exist_ok=True)
    tree = subprocess.run(
        ["git", "-C", str(run_clone), "ls-tree", "-r", "--name-only", sha],
        capture_output=True,
        text=True,
    )
    wanted = [
        name
        for name in tree.stdout.splitlines()
        if name == CONTRACT_TEST
        or name == "taskman.py"
        or name.startswith("taskman/")
        or "/taskman/" in name
        or name.endswith("/taskman.py")
    ]
    archive = subprocess.run(
        ["git", "-C", str(run_clone), "archive", sha, "--", *wanted],
        capture_output=True,
    )
    if archive.returncode == 0 and archive.stdout:
        subprocess.run(["tar", "-x", "-C", str(export_dir)], input=archive.stdout, check=False)
    diff = subprocess.run(
        ["git", "-C", str(run_clone), "diff", base_sha, sha],
        capture_output=True,
        text=True,
    )
    (export_dir / "cell.diff.patch").write_text(diff.stdout)
    changed = subprocess.run(
        ["git", "-C", str(run_clone), "diff", "--name-only", base_sha, sha],
        capture_output=True,
        text=True,
    )
    names = [n for n in changed.stdout.splitlines() if n.strip()]
    return {
        "tests_changed": any(n.startswith("tests/") for n in names),
        "changed_files": names,
        "exported": sorted(str(p.relative_to(export_dir)) for p in export_dir.rglob("*") if p.is_file()),
    }


def run_cell(plan: CellPlan, *, base_sha: str, deploy_repo: Path, timeout_s: int) -> dict:
    workdir = CELL_WORKTREES / plan.cell_id
    if workdir.exists():
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "worktree", "remove", "--force", str(workdir)],
            capture_output=True,
        )
    _run_worktree_add(base_sha, workdir)

    record: dict = {
        "cell_id": plan.cell_id,
        "condition": plan.condition,
        "rep": plan.rep,
        "spec": plan.spec,
        "goal": plan.goal,
        "thinking_budget_tokens": plan.thinking_budget,
        "base_sha": base_sha,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    started = time.time()
    command = cell_command(plan, workdir=workdir, deploy_repo=deploy_repo)
    record["command"] = " ".join(shlex.quote(part) for part in command)
    try:
        proc = subprocess.run(
            command,
            cwd=str(deploy_repo),
            env=_cell_env(deploy_repo),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        record["exit_code"] = proc.returncode
        record["run_id"] = _parse_run_id(proc.stdout)
        (CELLS_DIR / f"{plan.cell_id}.log").write_text(proc.stdout[-20000:] + "\n" + proc.stderr[-20000:])
    except subprocess.TimeoutExpired:
        record["exit_code"] = -1
        record["error"] = f"cell exceeded the {timeout_s}s wall-clock timeout"
    record["duration_s"] = round(time.time() - started, 1)

    ledger = _newest_ledger(Path(plan.spec).stem)
    if ledger is not None:
        record["ledger"] = str(ledger)
        payload = json.loads(ledger.read_text())
        record["git_sha"] = payload.get("git_sha", "")
        record["run_state"] = payload.get("state", "")
        phases = payload.get("phases", [])
        record["test_executed_success"] = next(
            (p.get("test_executed_success") for p in phases if p.get("kind") == "test"), None
        )
        run_id = record.get("run_id") or payload.get("run_id", "")
        record["run_id"] = run_id
        clone = Path(os.environ.get("FINOPS_RUNS_ROOT", "/tmp/agentic-dynamics-runs")) / run_id / "repo"
        if run_id and clone.is_dir() and record.get("git_sha"):
            record.update(_export_cell(clone, record["git_sha"], base_sha, CELLS_DIR / plan.cell_id))
    record["status"] = (
        "ok"
        if record.get("run_state") == "succeeded" and record.get("exit_code") == 0
        else "failed"
    )
    (CELLS_DIR / f"{plan.cell_id}.json").write_text(json.dumps(record, indent=2))
    return record


def _preflight(deploy_repo: Path, base_sha: str) -> list[str]:
    problems: list[str] = []
    required = ("AUTH_HOME", "FINOPS_LAUNCH_BROKER_SOCKET")
    for name in required:
        if not os.environ.get(name):
            problems.append(f"environment variable {name} is not set")
    if not deploy_repo.is_dir():
        problems.append(f"deploy checkout missing: {deploy_repo}")
    else:
        head = subprocess.run(
            ["git", "-C", str(deploy_repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        )
        if head.returncode != 0 or not head.stdout.strip().startswith(base_sha[:12]):
            problems.append(
                f"deploy checkout HEAD {head.stdout.strip()[:12]} != ladder base {base_sha[:12]}"
            )
    if not (deploy_repo / CONTRACT_TEST).is_file():
        problems.append(f"contract test missing at the base: {CONTRACT_TEST}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-sha", default="", help="ladder base SHA (default: HEAD)")
    parser.add_argument(
        "--deploy-repo",
        default=os.environ.get("FINOPS_REPO_DIR", "/tmp/flash_ladder_deploy"),
    )
    parser.add_argument("--cells", default="", help="comma-separated subset (default: all 12)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="re-run already recorded cells")
    parser.add_argument("--timeout-s", type=int, default=9000, help="per-cell wall clock")
    args = parser.parse_args(argv)

    plan = build_cell_plan()
    if args.cells:
        wanted = {c.strip() for c in args.cells.split(",") if c.strip()}
        plan = [p for p in plan if p.cell_id in wanted]
    base_sha = args.base_sha or subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    deploy_repo = Path(args.deploy_repo)

    problems = _preflight(deploy_repo, base_sha)
    print(f"ladder base: {base_sha[:12]}  cells: {len(plan)}")
    for cell in plan:
        print(f"  {cell.cell_id}: spec={cell.spec} budget={cell.thinking_budget}")
    if problems:
        for problem in problems:
            print(f"PREFLIGHT FAIL: {problem}", file=sys.stderr)
        return 2
    if args.dry_run:
        for cell in plan:
            workdir = CELL_WORKTREES / cell.cell_id
            print("  $ " + " ".join(shlex.quote(p) for p in cell_command(cell, workdir=workdir, deploy_repo=deploy_repo)))
        return 0

    CELLS_DIR.mkdir(parents=True, exist_ok=True)
    for cell in plan:
        record_path = CELLS_DIR / f"{cell.cell_id}.json"
        if record_path.is_file() and not args.force:
            existing = json.loads(record_path.read_text())
            if existing.get("status") == "ok":
                print(f"skip {cell.cell_id}: already recorded ok")
                continue
        print(f"run  {cell.cell_id} …", flush=True)
        record = run_cell(cell, base_sha=base_sha, deploy_repo=deploy_repo, timeout_s=args.timeout_s)
        print(f"     -> {record['status']} run={record.get('run_id','?')} sha={record.get('git_sha','')[:9]}")
        if record["status"] != "ok":
            print("HALT: an infra/test failure stops the campaign (resume with the same command).", file=sys.stderr)
            return 1
    print("ladder campaign complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
