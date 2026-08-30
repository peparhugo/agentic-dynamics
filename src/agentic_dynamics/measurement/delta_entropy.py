"""The Δ-entropy instrument — the solution/test split + three-axis join + four-quadrant contract.

Design: ``docs/designs/proposed/neo4j_graph_analysis_design.md`` §3 (Part B).

The instrument measures the structural disorder an agent's work introduced into a
solution, as ``ΔH(cell) = entropy(solution_final) − entropy(solution_baseline)`` — but with
the operator's tests-factoring question pinned (the four §3 pins):

1. **The solution/test split (the confound fix).** The whole-tree ``compute_entropy`` walk
   silently INCLUDES test files (its skip list is only ``__pycache__``/``node_modules``/…).
   This module measures two separate dimensions — :func:`compute_split_entropy` returns a
   ``solution`` profile (production code only, test files excluded by naming + ``tests/``-dir
   rules) and a ``tests`` profile (the test tree's own structural entropy, a secondary
   work-product signal).
2. **The three-axis join.** ΔH_solution (structure) is only interpretable joined with
   ``changed_symbols_with_tests_ratio`` (linkage — the code-change seam's TESTED_BY term) and
   ``test_executed_success`` (outcome — the independent test runner).
3. **The four-quadrant contract.** :func:`classify_quadrant` is the interpretation contract:
   a ΔH without the test-join returns ``None`` — a FAILED finding, never a quadrant. The
   fourth quadrant (ΔH low, tests fail) is the "clean-but-wrong" cell — the 2d/2e unseen-family
   wall: structurally clean, semantically wrong, with the countable facts reading "clean".
4. **Campaign integration.** the ΔH response curve axis for the next calibration campaign.

The split is pure and deterministic; the quadrant is a pure decision table. No I/O, no RNG —
the driver (``scripts/measure_delta_entropy.py``) resolves the corpus and hands over the
measured axes.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

from agentic_dynamics.core.language import LanguageProfile
from agentic_dynamics.measurement.entropy import (
    EntropyProfile,
    compute_entropy,
    entropy_delta,
)

# ── The four-quadrant vocabulary (the interpretation contract, design §3.3) ──────

#: ΔH high + tests pass — messy but right (the hygiene texture).
MESSY_BUT_RIGHT = "messy_but_right"
#: ΔH high + tests fail — messy and broken.
MESSY_AND_BROKEN = "messy_and_broken"
#: ΔH low + tests pass — clean and right.
CLEAN_AND_RIGHT = "clean_and_right"
#: ΔH low + tests fail — clean but wrong: the invisible cell (the 2d/2e wall, design §3.3).
CLEAN_BUT_WRONG = "clean_but_wrong"

QUADRANTS = (MESSY_BUT_RIGHT, MESSY_AND_BROKEN, CLEAN_AND_RIGHT, CLEAN_BUT_WRONG)

#: Directory-name components that mark a file as part of the test tree (the "tests/-dir rule").
_TEST_DIR_NAMES = ("tests", "test")


@dataclass
class SplitEntropy:
    """The solution/test split of one codebase state's structural entropy.

    ``solution`` is the primary axis (production code only); ``tests`` is the recorded
    secondary dimension (the test tree's own structural entropy — an agent work-product
    signal feeding the hygiene texture, design §3.1).
    """

    solution: EntropyProfile
    tests: EntropyProfile


def is_test_file(path: Path, profile: LanguageProfile) -> bool:
    """Classify one source file as test (True) or solution (False) — the split rule.

    Two independent rules, ORed (design §3.1 "naming + ``tests/``-dir rules"):

    * **directory** — any path component named ``tests`` or ``test`` marks the file a test.
    * **naming** — the basename matches the language's ``test_file_pattern`` glob
      (``test_*.py``, ``*.test.ts``, ``*_test.go``, ``*_test.rs``). For typescript the
      ``.test.`` infix also matches, because the profile's ``*.test.ts`` pattern misses
      ``*.test.tsx`` (the same convention ``module_path_from_test_file`` encodes).
    """
    if any(part in _TEST_DIR_NAMES for part in path.parts):
        return True
    name = path.name
    pattern = profile.test_file_pattern
    if pattern and fnmatch.fnmatch(name, pattern):
        return True
    if profile.name == "typescript" and ".test." in name:
        return True
    return False


def split_files(files: list[Path], profile: LanguageProfile) -> tuple[list[Path], list[Path]]:
    """Partition a source-file list into ``(solution_files, test_files)``."""
    solution: list[Path] = []
    tests: list[Path] = []
    for f in files:
        (tests if is_test_file(f, profile) else solution).append(f)
    return solution, tests


def compute_split_entropy(
    codebase_path: Path,
    profile: LanguageProfile | None = None,
) -> SplitEntropy:
    """Compute the solution/test split of a codebase's entropy in two passes.

    The ``solution`` profile is measured over production files only (test files excluded by
    :func:`is_test_file`); the ``tests`` profile over the test tree alone. Both reuse the
    existing five-dimension :func:`compute_entropy` via its ``file_filter`` seam.
    """
    if profile is None:
        from agentic_dynamics.core.language import detect_language

        profile = detect_language(codebase_path)
    if profile is None:
        return SplitEntropy(solution=EntropyProfile(), tests=EntropyProfile())

    solution = compute_entropy(
        codebase_path, profile, file_filter=lambda p: not is_test_file(p, profile)
    )
    tests = compute_entropy(
        codebase_path, profile, file_filter=lambda p: is_test_file(p, profile)
    )
    return SplitEntropy(solution=solution, tests=tests)


def delta_split_entropy(
    baseline: SplitEntropy, final: SplitEntropy
) -> dict[str, float]:
    """ΔH per split dimension: ``final − baseline`` (positive = more disorder introduced)."""
    return {
        "delta_h_solution": round(entropy_delta(baseline.solution, final.solution), 4),
        "delta_h_tests": round(entropy_delta(baseline.tests, final.tests), 4),
    }


def classify_quadrant(
    delta_h_solution: float,
    changed_symbols_with_tests_ratio: float | None,
    test_executed_success: bool | None,
    *,
    delta_h_threshold: float = 0.0,
) -> str | None:
    """The four-quadrant interpretation contract (design §3.3).

    **The contract is law:** a ΔH without the test-join is a FAILED finding, never a
    quadrant. The join requires BOTH the linkage axis (``changed_symbols_with_tests_ratio``)
    and the outcome axis (``test_executed_success``). If either is absent the function
    returns ``None`` — the caller records "ΔH measured, test-join deferred", not a quadrant.

    Args:
        delta_h_solution: ΔH_solution (structure axis). High = ``> delta_h_threshold``.
        changed_symbols_with_tests_ratio: linkage axis (``None`` = deferred by the seam).
        test_executed_success: outcome axis (``None`` = not independently measured).
        delta_h_threshold: the high/low cut (default 0.0 — the sign of ΔH, i.e. whether the
            agent introduced net disorder). ``[P]``: the design leaves the cut unspecified;
            sign-of-delta is the natural reading of "ΔH = the disorder introduced".

    Returns:
        One of :data:`QUADRANTS`, or ``None`` when the test-join is incomplete.
    """
    if test_executed_success is None:
        return None
    if changed_symbols_with_tests_ratio is None:
        return None

    high = delta_h_solution > delta_h_threshold
    if high:
        return MESSY_BUT_RIGHT if test_executed_success else MESSY_AND_BROKEN
    return CLEAN_AND_RIGHT if test_executed_success else CLEAN_BUT_WRONG
