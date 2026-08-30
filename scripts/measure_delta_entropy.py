"""The Δ-entropy instrument driver — compute ΔH_solution / ΔH_tests + the three-axis join +
the four-quadrant classification over the accessible story + campaign worktrees.

Design: ``docs/designs/proposed/neo4j_graph_analysis_design.md`` §3 (Part B).
Output: ``experiments/results/entropy_beta/delta_entropy.json`` (machine) and
``.../delta_entropy.md`` (human table).

Coverage-first (the quadrant contract is law): every measured cell records BOTH ΔH axes and
the test-join (``changed_symbols_with_tests_ratio`` + ``test_executed_success``). A cell
whose join is incomplete is recorded with ``test_join_complete=false`` and ``quadrant=null`` —
a FAILED finding, never a quadrant, never a fabricated ratio. The coverage is recorded
exactly: baseline-missing worktrees are listed, not imputed.

Two corpora:
  * **story** — every ``experiments/results/stories/*.json`` whose worktree is still on disk.
    Baseline = the story's ``codebase_path`` seed directory (on disk); final = the worktree.
  * **campaign** — the cap_2b / cap_adaptive_2c/2d/2e/2f cell worktrees on disk. Baseline =
    the worktree's git root commit (the seeded app); final = worktree HEAD. The linkage +
    outcome axes are read from the campaign's recorded ``facts`` / score (measured there),
    never recomputed.

Usage:
    python scripts/measure_delta_entropy.py [--json] [--stories-only | --campaigns-only]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    import _bootstrap  # noqa: E402
except ImportError:
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.core.language import (
    _should_skip,
    build_code_snapshot,
    compute_code_delta,
    detect_language,
    tested_symbols,
)
from agentic_dynamics.measurement.delta_entropy import (
    classify_quadrant,
    compute_split_entropy,
    delta_split_entropy,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
STORIES_DIR = REPO_ROOT / "experiments/results/stories"
OUT_DIR = REPO_ROOT / "experiments/results/entropy_beta"
OUT_JSON = OUT_DIR / "delta_entropy.json"
OUT_MD = OUT_DIR / "delta_entropy.md"

#: The ΔH high/low cut (the sign of ΔH — whether the agent introduced net disorder). The
#: design leaves the threshold unspecified; this is the instrument's [P] choice.
DELTA_H_THRESHOLD = 0.0

#: Campaign cell result directories that still hold per-cell ``facts`` (the recorded
#: ``changed_symbols_with_tests_ratio``) and a score JSON with ``test_executed_success``.
CAMPAIGN_CELL_DIRS = ("cap_2b", "cap_adaptive_2c", "cap_adaptive_2d", "cap_adaptive_2e", "cap_adaptive_2f")


def _profile_for_dir(path: Path):
    return detect_language(path)


def _snapshot_from_dir(directory: Path, profile, revision: str):
    """Collect every source file (solution + tests) into a typed snapshot."""
    files: dict[str, bytes] = {}
    for file_path in directory.rglob("*"):
        if file_path.is_dir() or _should_skip(file_path):
            continue
        if file_path.suffix not in profile.extensions:
            continue
        try:
            source = file_path.read_bytes()
        except (OSError, UnicodeDecodeError):
            continue
        files[str(file_path.relative_to(directory))] = source
    return build_code_snapshot(files, revision=revision, profile=profile)


def _git_root_commit(worktree: Path) -> str | None:
    out = subprocess.run(
        ["git", "-C", str(worktree), "rev-list", "--max-parents=0", "HEAD"],
        capture_output=True, text=True, timeout=15,
    )
    lines = [l for l in out.stdout.splitlines() if l.strip()]
    return lines[0] if lines else None


def _git_snapshot(worktree: Path, profile, revision: str):
    """Build a typed snapshot of a git revision's source files (the campaign seed)."""
    files: dict[str, bytes] = {}
    out = subprocess.run(
        ["git", "-C", str(worktree), "ls-tree", "-r", "--name-only", revision],
        capture_output=True, text=True, timeout=15,
    )
    for rel in out.stdout.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        p = Path(rel)
        if p.suffix not in profile.extensions or _should_skip(p):
            continue
        shown = subprocess.run(
            ["git", "-C", str(worktree), "show", f"{revision}:{rel}"],
            capture_output=True, timeout=15,
        )
        if shown.returncode == 0:
            files[rel] = shown.stdout
    return build_code_snapshot(files, revision=revision, profile=profile)


def _tests_ratio_from_delta(baseline_snapshot, final_snapshot) -> float | None:
    """``changed_symbols_with_tests_ratio`` per the seam's TESTED_BY semantics (deferred, never 0)."""
    delta = compute_code_delta(baseline_snapshot, final_snapshot)
    if delta.changed_symbol_count == 0:
        return None
    after_tested = tested_symbols(delta.after)
    before_tested = tested_symbols(delta.before)
    after_names = {s.qualified_name for s in delta.added_symbols} | {
        s.qualified_name for s in delta.changed_symbols
    }
    before_names = {s.qualified_name for s in delta.removed_symbols}
    tested_changed = len((after_names & after_tested) | (before_names & before_tested))
    if tested_changed == 0:
        return None
    return tested_changed / delta.changed_symbol_count


def _measure_cell(
    *,
    cell_id: str,
    kind: str,
    model: str,
    baseline_snapshot,
    final_snapshot,
    baseline_split,
    final_split,
    tests_ratio: float | None,
    test_executed_success,
    extra: dict,
) -> dict:
    deltas = delta_split_entropy(baseline_split, final_split)
    quadrant = classify_quadrant(
        deltas["delta_h_solution"], tests_ratio, test_executed_success,
        delta_h_threshold=DELTA_H_THRESHOLD,
    )
    return {
        "cell_id": cell_id,
        "kind": kind,
        "model": model,
        **extra,
        "delta_h_solution": deltas["delta_h_solution"],
        "delta_h_tests": deltas["delta_h_tests"],
        "changed_symbols_with_tests_ratio": (
            round(tests_ratio, 4) if tests_ratio is not None else None
        ),
        "test_executed_success": test_executed_success,
        "test_join_complete": tests_ratio is not None and test_executed_success is not None,
        "quadrant": quadrant,
    }


def _measure_story_cells() -> tuple[list[dict], list[dict]]:
    cells: list[dict] = []
    skipped: list[dict] = []
    profile_cache: dict[str, object] = {}
    baseline_split_cache: dict[str, object] = {}
    baseline_snapshot_cache: dict[str, object] = {}

    for story_file in sorted(STORIES_DIR.glob("*.json")):
        try:
            story = json.loads(story_file.read_text())
        except json.JSONDecodeError:
            continue
        worktree = Path(story.get("worktree") or "")
        if not worktree.is_dir():
            skipped.append({"cell_id": story.get("story_id"), "reason": "worktree_missing"})
            continue
        codebase_path = story.get("codebase_path") or ""
        baseline = Path(codebase_path)
        if not baseline.is_absolute():
            baseline = REPO_ROOT / baseline
        if not baseline.is_dir():
            skipped.append({"cell_id": story.get("story_id"), "reason": "baseline_missing"})
            continue

        profile = _profile_for_dir(worktree)
        if profile is None:
            skipped.append({"cell_id": story.get("story_id"), "reason": "no_language"})
            continue

        cache_key = str(baseline)
        if cache_key not in baseline_split_cache:
            baseline_split_cache[cache_key] = compute_split_entropy(baseline, profile)
            baseline_snapshot_cache[cache_key] = _snapshot_from_dir(baseline, profile, "baseline")
        baseline_split = baseline_split_cache[cache_key]
        baseline_snapshot = baseline_snapshot_cache[cache_key]
        final_split = compute_split_entropy(worktree, profile)
        final_snapshot = _snapshot_from_dir(worktree, profile, "final")

        tests_ratio = _tests_ratio_from_delta(baseline_snapshot, final_snapshot)
        model = (story.get("model") or "").split("/")[-1]
        cells.append(
            _measure_cell(
                cell_id=story.get("story_id") or story_file.stem,
                kind="story",
                model=model,
                baseline_snapshot=baseline_snapshot,
                final_snapshot=final_snapshot,
                baseline_split=baseline_split,
                final_split=final_split,
                tests_ratio=tests_ratio,
                test_executed_success=story.get("test_executed_success"),
                extra={
                    "story": story.get("story_name"),
                    "condition": story.get("perturbation_condition"),
                    "language": profile.name,
                },
            )
        )
    return cells, skipped


def _load_campaign_facts() -> dict[str, dict]:
    """cell_id -> {tests_ratio (from facts), test_executed_success (from score), worktree}."""
    facts: dict[str, dict] = {}
    for campaign in CAMPAIGN_CELL_DIRS:
        base = REPO_ROOT / "experiments/results" / campaign
        # 1. per-cell facts (changed_symbols_with_tests_ratio + worktree)
        cells_dir = base / "cells"
        for cell_file in sorted((cells_dir.glob("*.json") if cells_dir.is_dir() else [])):
            try:
                rec = json.loads(cell_file.read_text())
            except json.JSONDecodeError:
                continue
            cid = rec.get("cell_id")
            if not cid:
                continue
            f = rec.get("facts") or {}
            entry = facts.setdefault(cid, {})
            if "changed_symbols_with_tests_ratio" in f:
                try:
                    entry["tests_ratio"] = float(f["changed_symbols_with_tests_ratio"])
                except (TypeError, ValueError):
                    pass
            entry["worktree"] = rec.get("seeded_app_worktree") or rec.get("worktree")
        # 2. p2_cells_run.json (cap_2b shape) — facts + worktree
        run_file = base / "p2_cells_run.json"
        if run_file.is_file():
            try:
                run = json.loads(run_file.read_text())
            except json.JSONDecodeError:
                run = {}
            for rec in run.get("cells") or []:
                cid = rec.get("cell_id")
                if not cid:
                    continue
                f = rec.get("facts") or {}
                entry = facts.setdefault(cid, {})
                if "changed_symbols_with_tests_ratio" in f:
                    try:
                        entry["tests_ratio"] = float(f["changed_symbols_with_tests_ratio"])
                    except (TypeError, ValueError):
                        pass
                entry.setdefault("worktree", rec.get("seeded_app_worktree"))
        # 3. score JSON — test_executed_success
        for score_file in sorted(base.glob("*_score_*.json")):
            try:
                score = json.loads(score_file.read_text())
            except json.JSONDecodeError:
                continue
            for rec in score.get("per_cell") or []:
                cid = rec.get("cell_id")
                if not cid:
                    continue
                entry = facts.setdefault(cid, {})
                if rec.get("test_executed_success") is not None:
                    entry["test_executed_success"] = rec["test_executed_success"]
                entry["arm"] = rec.get("arm")
                entry["class"] = rec.get("class")
    return facts


def _measure_campaign_cells() -> tuple[list[dict], list[dict]]:
    cells: list[dict] = []
    skipped: list[dict] = []
    facts = _load_campaign_facts()
    for cell_id, meta in sorted(facts.items()):
        worktree = Path(meta.get("worktree") or "")
        if not worktree.is_dir():
            skipped.append({"cell_id": cell_id, "reason": "worktree_missing"})
            continue
        profile = _profile_for_dir(worktree)
        if profile is None:
            skipped.append({"cell_id": cell_id, "reason": "no_language"})
            continue
        seed_rev = _git_root_commit(worktree)
        if seed_rev is None:
            skipped.append({"cell_id": cell_id, "reason": "no_git_root"})
            continue
        baseline_snapshot = _git_snapshot(worktree, profile, seed_rev)
        final_snapshot = _snapshot_from_dir(worktree, profile, "final")
        baseline_split, final_split = _git_split_entropy(worktree, profile, seed_rev)
        cells.append(
            _measure_cell(
                cell_id=cell_id,
                kind="campaign",
                model="",  # campaign cells are mixed-model; recorded in extra
                baseline_snapshot=baseline_snapshot,
                final_snapshot=final_snapshot,
                baseline_split=baseline_split,
                final_split=final_split,
                tests_ratio=meta.get("tests_ratio"),
                test_executed_success=meta.get("test_executed_success"),
                extra={"arm": meta.get("arm"), "class": meta.get("class")},
            )
        )
    return cells, skipped


def _git_split_entropy(worktree: Path, profile, seed_rev: str):
    """Measure split entropy for the seed (via a temp checkout) and the final worktree.

    The seed is a git revision, not a directory, so we materialize its source files into a
    temp directory and run :func:`compute_split_entropy` on it — the same path the story
    cells use. The final split is the worktree itself.
    """
    import tempfile

    final_split = compute_split_entropy(worktree, profile)
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        out = subprocess.run(
            ["git", "-C", str(worktree), "ls-tree", "-r", "--name-only", seed_rev],
            capture_output=True, text=True, timeout=15,
        )
        for rel in out.stdout.splitlines():
            rel = rel.strip()
            if not rel:
                continue
            p = Path(rel)
            if p.suffix not in profile.extensions or _should_skip(p):
                continue
            shown = subprocess.run(
                ["git", "-C", str(worktree), "show", f"{seed_rev}:{rel}"],
                capture_output=True, timeout=15,
            )
            if shown.returncode == 0:
                target = td / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(shown.stdout)
        baseline_split = compute_split_entropy(td, profile)
    return baseline_split, final_split


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine JSON to stdout")
    parser.add_argument("--stories-only", action="store_true")
    parser.add_argument("--campaigns-only", action="store_true")
    args = parser.parse_args()

    story_cells: list[dict] = []
    campaign_cells: list[dict] = []
    skipped: list[dict] = []
    if not args.campaigns_only:
        story_cells, story_skipped = _measure_story_cells()
        skipped += story_skipped
    if not args.stories_only:
        campaign_cells, campaign_skipped = _measure_campaign_cells()
        skipped += campaign_skipped

    cells = story_cells + campaign_cells
    measured = [c for c in cells if c["delta_h_solution"] is not None]
    joined = [c for c in measured if c["test_join_complete"]]

    quadrant_dist = Counter(c["quadrant"] for c in joined)
    # clean-but-wrong = the 2d/2e wall count (the blind-spot case)
    clean_but_wrong = quadrant_dist.get("clean_but_wrong", 0)

    per_model: dict[str, Counter] = {}
    for c in joined:
        per_model.setdefault(c["model"] or c.get("kind") or "?", Counter())[c["quadrant"]] += 1

    result = {
        "schema": "delta_entropy/v1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "delta_h_threshold": DELTA_H_THRESHOLD,
        "delta_h_threshold_provenance": "[P] sign-of-delta (design leaves the cut unspecified)",
        "coverage": {
            "story_cells_measured": len(story_cells),
            "campaign_cells_measured": len(campaign_cells),
            "total_measured": len(measured),
            "test_join_complete": len(joined),
            "test_join_incomplete": len(measured) - len(joined),
            "skipped": skipped,
        },
        "quadrant_distribution": dict(quadrant_dist),
        "clean_but_wrong_count": clean_but_wrong,
        "per_model_quadrant_distribution": {m: dict(c) for m, c in sorted(per_model.items())},
        "cells": cells,
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2))
    _write_markdown(result)
    print(f"wrote {OUT_JSON.relative_to(REPO_ROOT)}")
    print(f"wrote {OUT_MD.relative_to(REPO_ROOT)}")
    print(f"measured {len(measured)} cells ({len(story_cells)} story, {len(campaign_cells)} campaign); "
          f"test-join complete {len(joined)}; clean_but_wrong {clean_but_wrong}")


def _write_markdown(result: dict) -> None:
    lines = [
        "# Δ-entropy instrument — corpus measurement",
        "",
        f"schema `delta_entropy/v1` · generated {result['generated_at']}",
        f"ΔH threshold: `{result['delta_h_threshold']}` ({result['delta_h_threshold_provenance']})",
        "",
        "## Coverage (exact — never imputed)",
        "",
        f"- story cells measured: {result['coverage']['story_cells_measured']}",
        f"- campaign cells measured: {result['coverage']['campaign_cells_measured']}",
        f"- test-join complete: {result['coverage']['test_join_complete']}",
        f"- test-join incomplete (ΔH measured, quadrant FAILED-finding): "
        f"{result['coverage']['test_join_incomplete']}",
        f"- clean-but-wrong count (the 2d/2e wall): {result['clean_but_wrong_count']}",
        "",
        "## Quadrant distribution (joined cells only)",
        "",
    ]
    for q, n in sorted(result["quadrant_distribution"].items()):
        lines.append(f"- {q}: {n}")
    lines += ["", "## Per-model quadrant distribution", ""]
    for model, dist in sorted(result["per_model_quadrant_distribution"].items()):
        lines.append(f"- {model}: {dist}")
    lines += ["", "## Skipped cells", ""]
    for s in result["coverage"]["skipped"]:
        lines.append(f"- {s.get('cell_id')}: {s.get('reason')}")
    OUT_MD.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
