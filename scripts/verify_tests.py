"""Independent test execution — run each story cell's test suite ourselves.

The ``test_executed_success`` ledger field must be measured by the harness, not taken
from the model's self-reported ``tests_passed``/``tests_total`` (which the Claude CLI
adapter drops). This script runs the appropriate test framework against the final state
of each story worktree and writes ``experiments/results/verified_tests.json``.

Runners, keyed off ``language.py``:
  - python     → ``python3 -m pytest``
  - typescript → ``node <worktree>/node_modules/jest/bin/jest.js --ci --silent``
  - go/rust    → ``go test`` / ``cargo test`` (not yet exercised by the story corpus)

``test_executed_success = total > 0 and failed == 0 and errors == 0`` — a cell whose
suite collects import/collection errors (often missing deps) is recorded as *not*
succeeded, with the note field carrying the tail for triage.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORIES_DIR = ROOT / "experiments" / "results" / "stories"
OUT_PATH = ROOT / "experiments" / "results" / "verified_tests.json"
TIMEOUT = 300


def resolve_node() -> str | None:
    """Locate a node binary (nvm installs are not on PATH by default)."""
    node = shutil.which("node")
    if node:
        return node
    nvm_roots = [Path.home() / ".nvm" / "versions" / "node"]
    candidates: list[Path] = []
    for root in nvm_roots:
        if root.is_dir():
            candidates.extend(sorted(root.glob("*/bin/node"), reverse=True))
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None


def run_pytest(workdir: Path) -> dict:
    """Run pytest in a Python story worktree; parse passed/failed/error counts."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short", "."],
        cwd=workdir, capture_output=True, text=True, timeout=TIMEOUT,
    )
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return _parse_pytest(output)


def _parse_pytest(output: str) -> dict:
    passed = _int_from(r"(\d+)\s+passed", output)
    failed = _int_from(r"(\d+)\s+failed", output)
    errors = _int_from(r"(\d+)\s+error", output)
    total = passed + failed + errors
    return {
        "runner": "pytest",
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": total,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "tail": output[-600:],
    }


def run_jest(workdir: Path, node: str) -> dict:
    """Run jest in a TypeScript story worktree; parse the Tests: summary line."""
    jest_bin = workdir / "node_modules" / "jest" / "bin" / "jest.js"
    if not jest_bin.is_file():
        return {"runner": "jest", "passed": 0, "failed": 0, "errors": 1, "total": 0,
                "pass_rate": 0.0, "tail": "jest.js not found in node_modules"}
    try:
        proc = subprocess.run(
            [node, str(jest_bin), "--ci", "--silent"],
            cwd=workdir, capture_output=True, text=True, timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {"runner": "jest", "passed": 0, "failed": 0, "errors": 1, "total": 0,
                "pass_rate": 0.0, "tail": f"timeout after {TIMEOUT}s"}
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    m = re.search(r"Tests:\s+(\d+)\s+failed,\s+(\d+)\s+passed,\s+(\d+)\s+total", output)
    if m:
        failed, passed, total = int(m.group(1)), int(m.group(2)), int(m.group(3))
        errors = 0
    else:
        m2 = re.search(r"Tests:\s+(\d+)\s+passed,\s+(\d+)\s+total", output)
        if m2:
            passed, total = int(m2.group(1)), int(m2.group(2))
            failed, errors = 0, 0
        else:
            passed = total = 0
            failed = errors = 1
    return {
        "runner": "jest",
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": total,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "tail": output[-600:],
    }


def _int_from(pattern: str, text: str) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0


def load_cells() -> list[dict]:
    cells: list[dict] = []
    for f in sorted(STORIES_DIR.glob("*.json")):
        if "log" in f.name:
            continue
        d = json.loads(f.read_text())
        d["_file"] = f.name
        cells.append(d)
    return cells


def verify_cell(d: dict, node: str) -> dict:
    cell_id = Path(d.get("_file", "")).stem
    worktree = d.get("worktree")
    language = d.get("language", "python")
    result: dict = {
        "cell_id": cell_id,
        "story": d.get("story_name"),
        "model": d.get("model"),
        "condition": d.get("perturbation_condition"),
        "language": language,
        "worktree": worktree,
        "commit": (d.get("sessions") or [{}])[-1].get("commit_hash", ""),
    }
    if not worktree or not os.path.isdir(worktree):
        result.update({"passed": 0, "failed": 0, "errors": 1, "total": 0,
                       "pass_rate": 0.0, "test_executed_success": False,
                       "note": "worktree missing"})
        return result

    t0 = time.time()
    if language == "typescript":
        r = run_jest(Path(worktree), node)
    elif language == "go":
        r = _run_framework(Path(worktree), ["go", "test", "./..."], "go test")
    elif language == "rust":
        r = _run_framework(Path(worktree), ["cargo", "test", "--quiet"], "cargo test")
    else:
        r = run_pytest(Path(worktree))
    result.update(r)
    result["test_executed_success"] = bool(r["total"] > 0 and r["failed"] == 0 and r["errors"] == 0)
    result["duration_s"] = round(time.time() - t0, 2)
    if not result["test_executed_success"] and r.get("tail"):
        result["note"] = r["tail"][-400:]
    return result


def _run_framework(workdir: Path, cmd: list[str], runner: str) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"runner": runner, "passed": 0, "failed": 0, "errors": 1, "total": 0,
                "pass_rate": 0.0, "tail": f"timeout after {TIMEOUT}s"}
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    passed = _int_from(r"(\d+)\s+passed", output)
    failed = _int_from(r"(\d+)\s+failed", output) + _int_from(r"(\d+)\s+FAIL", output)
    total = passed + failed
    errors = 0 if proc.returncode == 0 or total else 1
    return {"runner": runner, "passed": passed, "failed": failed, "errors": errors,
            "total": total, "pass_rate": round(passed / total, 4) if total else 0.0,
            "tail": output[-600:]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only verify first N cells")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    node = resolve_node()
    if node is None:
        print("ERROR: node binary not found — required for TypeScript (jest) cells")
        sys.exit(1)

    cells = load_cells()
    if args.limit:
        cells = cells[: args.limit]
    print(f"verifying {len(cells)} cells (node={node})")

    if args.dry_run:
        for d in cells[:5]:
            print("  would verify:", d.get("worktree"), d.get("language"))
        return

    records = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(verify_cell, d, node): d for d in cells}
        for idx, fut in enumerate(as_completed(futs), start=1):
            records.append(fut.result())
            if idx % 25 == 0 or idx == len(cells):
                print(f"  {idx}/{len(cells)} verified")

    records.sort(key=lambda r: (r.get("story") or "", r.get("model") or "", r.get("condition") or ""))
    succ = sum(1 for r in records if r.get("test_executed_success"))
    errs = sum(1 for r in records if r.get("errors", 0) > 0)
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cells_total": len(records),
        "test_executed_success": succ,
        "with_errors": errs,
        "runner": {"python": "pytest", "typescript": "jest"},
    }
    OUT_PATH.write_text(json.dumps({"_meta": meta, "cells": records}, indent=2))
    print(f"\nwrote {OUT_PATH}")
    print(f"  test_executed_success: {succ}/{len(records)}   with_errors: {errs}")


if __name__ == "__main__":
    main()
