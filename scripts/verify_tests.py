"""Independent test execution — run each story cell's test suite ourselves.

The ``test_executed_success`` ledger field must be measured by the harness, not taken
from the model's self-reported ``tests_passed``/``tests_total`` (which the Claude CLI
adapter drops). This script runs the appropriate test framework against the final state
of each story worktree and writes ``experiments/results/verified_tests.json``.

The suite-running logic lives in ``instrument.test_runner.run_suite`` (single source of
truth, shared with ``workflow_runner``'s ``verify`` phase).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.runtime.test_runner import resolve_node, run_suite, suite_succeeded  # noqa: E402

STORIES_DIR = ROOT / "experiments" / "results" / "stories"
OUT_PATH = ROOT / "experiments" / "results" / "verified_tests.json"


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
    r = run_suite(Path(worktree), language, node=node)
    result.update(r)
    result["test_executed_success"] = suite_succeeded(r)
    result["duration_s"] = round(time.time() - t0, 2)
    if not result["test_executed_success"] and r.get("tail"):
        result["note"] = r["tail"][-400:]
    return result


def _write_partial(records: list[dict], *, final: bool = False) -> None:
    succ = sum(1 for r in records if r.get("test_executed_success"))
    errs = sum(1 for r in records if r.get("errors", 0) > 0)
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cells_total": len(records),
        "test_executed_success": succ,
        "with_errors": errs,
        "runner": {"python": "pytest", "typescript": "jest"},
        "partial": not final,
    }
    OUT_PATH.write_text(json.dumps({"_meta": meta, "cells": records}, indent=2))


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
            try:
                records.append(fut.result())
            except Exception as exc:  # one bad cell must not sink the run
                d = futs[fut]
                records.append({
                    "cell_id": Path(d.get("_file", "")).stem,
                    "story": d.get("story_name"),
                    "model": d.get("model"),
                    "condition": d.get("perturbation_condition"),
                    "language": d.get("language"),
                    "worktree": d.get("worktree"),
                    "runner": "unknown", "passed": 0, "failed": 0, "errors": 1,
                    "total": 0, "pass_rate": 0.0, "test_executed_success": False,
                    "note": f"exception: {exc!r}",
                })
            if idx % 25 == 0 or idx == len(cells):
                print(f"  {idx}/{len(cells)} verified")
                _write_partial(records)

    records.sort(key=lambda r: (r.get("story") or "", r.get("model") or "", r.get("condition") or ""))
    _write_partial(records, final=True)
    succ = sum(1 for r in records if r.get("test_executed_success"))
    errs = sum(1 for r in records if r.get("errors", 0) > 0)
    print(f"\nwrote {OUT_PATH}")
    print(f"  test_executed_success: {succ}/{len(records)}   with_errors: {errs}")


if __name__ == "__main__":
    main()
