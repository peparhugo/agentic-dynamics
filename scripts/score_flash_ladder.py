#!/usr/bin/env python3
"""Score the flash-ladder portfolios from persisted run.py results OR workflow cell records.

Two modes:

* ``--inputs <result.json ...>`` — the production scorer for ``run.py`` result files
  (g5 round-2 F2/F4): groups attempts by condition, excludes ``solution_code is None`` and
  malformed sources with their counts, computes portfolio diversity, persists the score.
* ``--cells <dir> --base-sha <sha>`` — the ladder scorer: reads the workflow cell records
  written by ``run_flash_ladder.py``, re-runs the PRISTINE ``taskman`` contract test (restored
  from the ladder base) against every exported tree (the independent quality read — never the
  in-run flag), computes the per-condition portfolio diversity ``D_c`` and quality ``Q_c``,
  bootstrap CIs, and the pre-registered decision rule.

    python3 scripts/score_flash_ladder.py --cells experiments/results/flash_ladder/cells \
        --base-sha 121126df --out experiments/results/flash_ladder/score.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from statistics import median

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.measurement.diversity import portfolio_diversity
from agentic_dynamics.measurement.portfolio_score import score_result_files

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_RELPATH = "tests/flash_ladder/taskman_contract_test.py"
DEFAULT_THRESHOLD = 0.5
ESCALATE_DIVERSITY_DELTA = 0.10  # preregistration §4 decision rule
ESCALATE_QUALITY_DELTA = 1
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260910


def _expand_inputs(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        if any(ch in pattern for ch in "*?["):
            paths.extend(sorted(Path().glob(pattern)))
        else:
            paths.append(Path(pattern))
    return paths


# ── run.py result mode (unchanged production path) ────────────────────────────


def run_result_mode(args: argparse.Namespace) -> int:
    paths = _expand_inputs(args.inputs)
    if not paths:
        print("score_flash_ladder: no input files matched", file=sys.stderr)
        return 2
    group_by = tuple(field for field in args.group_by.split(",") if field)
    score = score_result_files(paths, group_by=group_by, threshold=args.threshold)
    payload = score.to_dict()
    out = _output_path(args, score.generated_at)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    for condition in payload["conditions"]:
        diversity = condition["diversity"]
        print(
            f"{condition['condition']}: n={condition['n_attempts']} "
            f"scored={condition['n_scored']} excluded_null={condition['excluded_null_source']} "
            f"excluded_invalid={condition['excluded_invalid_source']} "
            f"coverage={diversity['coverage']} mean_composite={diversity['mean_composite']} "
            f"distinct_fraction={diversity['distinct_fraction']}"
        )
    print(f"written: {out}")
    return 0


def _output_path(args: argparse.Namespace, generated_at: str) -> Path:
    if args.out:
        return Path(args.out)
    stamp = generated_at.replace(":", "").replace("-", "")
    return REPO_ROOT / "experiments" / "results" / "flash_ladder" / f"flash_ladder_score_{stamp}.json"


# ── ladder cell mode ──────────────────────────────────────────────────────────


def collect_package_files(cell_dir: Path, changed_files: list[str] | None = None) -> list[tuple[Path, str]]:
    """Every GENERATED ``taskman`` source file, ANY layout: a package dir (``taskman/`` or
    ``src/taskman/``) or a single-file module (``taskman.py``). Returns ``(abs_path, relpath)``
    pairs relative to the cell dir. A cell with none is a null-source attempt.

    When the cell record's ``changed_files`` is supplied (the authoritative generated set),
    selection is limited to those paths — a cell's tree may also contain PRE-EXISTING tracked
    packages (the committed ladder evidence under ``experiments/``), which must never be scored
    as the cell's design. The rglob fallback exists only for record-less fixtures and skips
    ``experiments/``.
    """
    if changed_files is not None:
        selected = [
            name
            for name in changed_files
            if name == "taskman.py"
            or name.startswith("taskman/")
            or name.endswith("/taskman.py")
            or "/taskman/" in name
        ]
        matched: list[tuple[Path, str]] = []
        for name in sorted(selected):
            path = cell_dir / name
            if path.is_file() and path.suffix == ".py":
                matched.append((path, name))
        return matched

    package_dirs = sorted(
        {
            p.parent
            for p in cell_dir.rglob("taskman/__init__.py")
            if p.is_file() and "experiments" not in p.parts
        }
    )
    single_files = sorted(
        p
        for p in cell_dir.rglob("taskman.py")
        if p.is_file() and p.parent.name != "taskman" and "experiments" not in p.parts
    )
    matched = []
    for package in package_dirs:
        for path in sorted(package.rglob("*.py")):
            if path.is_file():
                matched.append((path, str(path.relative_to(cell_dir))))
    for path in single_files:
        matched.append((path, str(path.relative_to(cell_dir))))
    return matched


def blob_from_tree(cell_dir: Path, changed_files: list[str] | None = None) -> str | None:
    """Concatenate the cell's generated ``taskman`` sources into one deterministic blob.

    The ``# === <relpath> ===`` headers are the format the diversity contract splits and parses
    per file. A cell with no generated Python is a null-source attempt (reported, never scored).
    """
    files = collect_package_files(cell_dir, changed_files)
    if not files:
        return None
    parts: list[str] = []
    for path, rel in files:
        parts.append(f"# === {rel} ===")
        parts.append(path.read_text())
    return "\n".join(parts)


def run_pristine_contract(
    base_sha: str,
    cell_dir: Path,
    repo: Path,
    *,
    changed_files: list[str] | None = None,
    timeout: int = 300,
) -> dict:
    """Re-run the PRISTINE contract test (restored from the ladder base) against the export."""
    pristine = subprocess.run(
        ["git", "-C", str(repo), "show", f"{base_sha}:{CONTRACT_RELPATH}"],
        capture_output=True,
        text=True,
    )
    if pristine.returncode != 0:
        return {"pass": None, "error": "pristine contract test unavailable at the base"}
    package_files = collect_package_files(cell_dir, changed_files)
    if not package_files:
        return {"pass": None, "error": "no generated taskman sources exported"}
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        test_path = tmp / CONTRACT_RELPATH
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(pristine.stdout)
        python_paths: set[str] = set()
        for source, rel in package_files:
            destination = tmp / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            rel_parts = Path(rel).parts
            if rel_parts[-1] == "__init__.py":
                python_paths.add(str(tmp / Path(*rel_parts[:-1]).parent))
            else:
                python_paths.add(str(destination.parent))
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", CONTRACT_RELPATH, "-q", "-p", "no:cacheprovider"],
            cwd=tmp,
            env={**os.environ, "PYTHONPATH": os.pathsep.join(sorted(python_paths))},
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = proc.stdout + proc.stderr
        passed = int(match.group(1)) if (match := re.search(r"(\d+) passed", output)) else 0
        failed = int(match.group(1)) if (match := re.search(r"(\d+) failed", output)) else 0
        return {
            "pass": proc.returncode == 0,
            "tests_passed": passed,
            "tests_failed": failed,
            "tests_total": passed + failed,
        }


def _ledger_summary(ledger_path: str | None) -> dict:
    if not ledger_path or not Path(ledger_path).is_file():
        return {}
    ledger = json.loads(Path(ledger_path).read_text())
    agent = next((p for p in ledger.get("phases", []) if p.get("kind") == "agent"), {})
    tokens = agent.get("tokens") or {}
    return {
        "cost_usd": ledger.get("total_cost_usd"),
        "run_state": ledger.get("state"),
        "fallback_mode": agent.get("fallback_mode"),
        "augmentation_versions": agent.get("augmentation_versions"),
        "selected_evidence_ids": agent.get("selected_evidence_ids") or [],
        "total_tokens": tokens.get("total"),
    }


def _pairwise_matrix(blobs: list[str]) -> list[list[float]] | None:
    """The scored pairwise composite matrix (self-pairs 0.0), or ``None`` if any pair is
    unsupported — a condition with unscored pairs gets no CI rather than a fabricated one."""
    from agentic_dynamics.measurement.diversity import pairwise_divergence

    n = len(blobs)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            result = pairwise_divergence(blobs[i], blobs[j])
            if not result["scored"]:
                return None
            matrix[i][j] = matrix[j][i] = float(result["composite"])
    return matrix


def _bootstrap_ci(matrix: list[list[float]] | None, *, resamples: int, seed: int) -> list[float] | None:
    """Percentile CI for the condition's mean composite (descriptive at n=3; prereg §4).

    Bootstrap over a precomputed pair matrix: a resampled portfolio's pair values are exactly
    the matrix entries of the resampled indices (self-pairs are 0.0), so the resample never
    re-parses sources.
    """
    if matrix is None or len(matrix) < 2:
        return None
    n = len(matrix)
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(resamples):
        draw = [rng.randrange(n) for _ in range(n)]
        values = [matrix[draw[i]][draw[j]] for i in range(n) for j in range(i + 1, n)]
        means.append(sum(values) / len(values))
    means.sort()
    return [means[int(0.025 * len(means))], means[int(0.975 * len(means)) - 1]]


def score_cells(cells_dir: Path, base_sha: str, repo: Path, *, threshold: float) -> dict:
    records = [json.loads(p.read_text()) for p in sorted(cells_dir.glob("C*.json"))]
    cells: list[dict] = []
    for record in records:
        cell_dir = cells_dir / record["cell_id"]
        changed_files = record.get("changed_files")
        blob = blob_from_tree(cell_dir, changed_files) if cell_dir.is_dir() else None
        pristine = (
            run_pristine_contract(base_sha, cell_dir, repo, changed_files=changed_files)
            if blob is not None
            else {"pass": None, "error": "no generated taskman package exported"}
        )
        cells.append(
            {
                "cell_id": record["cell_id"],
                "condition": record["condition"],
                "rep": record["rep"],
                "git_sha": record.get("git_sha", ""),
                "valid": blob is not None and not record.get("tests_changed", False),
                "tests_changed": record.get("tests_changed", False),
                "in_run_test": record.get("test_executed_success"),
                "pristine": pristine,
                "blob": blob,
                **_ledger_summary(record.get("ledger")),
            }
        )

    conditions: list[dict] = []
    for condition in sorted({c["condition"] for c in cells}):
        rows = [c for c in cells if c["condition"] == condition]
        valid = [c for c in rows if c["valid"]]
        blobs = [c["blob"] for c in valid]
        report = portfolio_diversity(blobs, threshold=threshold)
        pair_matrix = _pairwise_matrix(blobs)
        quality = sum(1 for c in valid if c["pristine"].get("pass") is True)
        costs = [c["cost_usd"] for c in valid if c.get("cost_usd") is not None]
        conditions.append(
            {
                "condition": condition,
                "n_attempts": len(rows),
                "n_valid": len(valid),
                "excluded_null_source": sum(1 for c in rows if not c["valid"]),
                "excluded_invalid_source": 0,
                "Q": quality,
                "D": report.mean_composite,
                "D_ci95": _bootstrap_ci(
                    pair_matrix, resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED
                ),
                "distinct_fraction": report.distinct_fraction,
                "mean_novelty": report.mean_novelty,
                "unsupported_pairs": report.unsupported_pairs,
                "median_cost_usd": median(costs) if costs else None,
                "total_tokens": sum(c.get("total_tokens") or 0 for c in valid) or None,
                "fallback_modes": sorted({c.get("fallback_mode") or "" for c in valid}),
                "diversity": report.to_dict(),
                "cells": [
                    {
                        "cell_id": c["cell_id"],
                        "sha": c["git_sha"],
                        "pristine_pass": c["pristine"].get("pass"),
                        "pristine_tests": (
                            f"{c['pristine'].get('tests_passed')}/{c['pristine'].get('tests_total')}"
                        ),
                        "in_run_test": c["in_run_test"],
                        "cost_usd": c.get("cost_usd"),
                        "tokens": c.get("total_tokens"),
                        "fallback_mode": c.get("fallback_mode"),
                    }
                    for c in rows
                ],
            }
        )

    return {
        "method": "ladder-cells/v1",
        "base_sha": base_sha,
        "threshold": threshold,
        "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED},
        "conditions": conditions,
        "decision": build_decision(conditions),
    }


def build_decision(conditions: list[dict]) -> dict:
    """The pre-registered §4 decision rule, as a pure function of the per-condition aggregates.

    Mutates ``conditions`` with ``delta_D``/``delta_Q`` vs C0, then escalates iff any effect
    reaches the registered margin. Extractable so the arithmetic is testable without a run.
    """
    baseline = next((c for c in conditions if c["condition"] == "C0"), None)
    if baseline is None:
        return {"escalate": False, "rule": "no C0 baseline", "largest_effect": "", "adaptive_directive": ""}
    effects = []
    for condition in conditions:
        if condition["condition"] == "C0":
            condition["delta_D"] = None
            condition["delta_Q"] = 0
            continue
        condition["delta_D"] = (
            None
            if condition["D"] is None or baseline["D"] is None
            else condition["D"] - baseline["D"]
        )
        condition["delta_Q"] = condition["Q"] - baseline["Q"]
        effects.append(condition)
    escalate = any(
        (c["delta_D"] is not None and abs(c["delta_D"]) >= ESCALATE_DIVERSITY_DELTA)
        or abs(c["delta_Q"]) >= ESCALATE_QUALITY_DELTA
        for c in effects
    )
    ranking = sorted(
        effects,
        key=lambda c: (abs(c["delta_D"] or 0.0), abs(c["delta_Q"])),
        reverse=True,
    )
    return {
        "escalate": escalate,
        "rule": (
            f"|delta_D| >= {ESCALATE_DIVERSITY_DELTA} or |delta_Q| >= {ESCALATE_QUALITY_DELTA}"
        ),
        "largest_effect": ranking[0]["condition"] if ranking else "",
        "adaptive_directive": (
            f"confirmatory grid (n=8) on C0 + {ranking[0]['condition']}"
            if escalate and ranking
            else "flat within the registered margin; no policy claim"
        ),
    }


def cells_mode(args: argparse.Namespace) -> int:
    cells_dir = Path(args.cells)
    if not cells_dir.is_dir():
        print(f"score_flash_ladder: cells dir not found: {cells_dir}", file=sys.stderr)
        return 2
    payload = score_cells(cells_dir, args.base_sha, REPO_ROOT, threshold=args.threshold)
    out = _output_path(args, "")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))

    print(f"{'cond':4} {'n':>2} {'valid':>5} {'Q':>2} {'D':>8} {'D_ci95':>18} {'distinct':>8} {'med$':>7}")
    for condition in payload["conditions"]:
        ci = condition["D_ci95"]
        ci_text = f"[{ci[0]:.3f},{ci[1]:.3f}]" if ci else "-"
        d_text = f"{condition['D']:.4f}" if condition["D"] is not None else "None"
        distinct = (
            f"{condition['distinct_fraction']:.3f}"
            if condition["distinct_fraction"] is not None
            else "None"
        )
        cost = f"{condition['median_cost_usd']:.4f}" if condition["median_cost_usd"] else "-"
        print(
            f"{condition['condition']:4} {condition['n_attempts']:>2} {condition['n_valid']:>5} "
            f"{condition['Q']:>2} {d_text:>8} {ci_text:>18} {distinct:>8} {cost:>7}"
        )
    decision = payload["decision"]
    print(
        f"decision: {'ESCALATE' if decision['escalate'] else 'FLAT'} — {decision['adaptive_directive']}"
    )
    print(f"written: {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("inputs", nargs="*", help="result JSON paths or glob patterns")
    parser.add_argument("--cells", default="", help="ladder cells dir (workflow cell mode)")
    parser.add_argument("--base-sha", default="", help="ladder base SHA (cell mode)")
    parser.add_argument(
        "--out", default="", help="output path (default experiments/results/flash_ladder/…)"
    )
    parser.add_argument("--group-by", default="operator,strength")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args(argv)

    if args.cells:
        if not args.base_sha:
            print("score_flash_ladder: --base-sha is required with --cells", file=sys.stderr)
            return 2
        return cells_mode(args)
    if not args.inputs:
        print("score_flash_ladder: provide result files or --cells", file=sys.stderr)
        return 2
    return run_result_mode(args)


if __name__ == "__main__":
    raise SystemExit(main())
