"""Unit tests for the Δ-entropy instrument (the solution/test split + four-quadrant contract).

Design: ``docs/designs/proposed/neo4j_graph_analysis_design.md`` §3.
"""

import tempfile
from pathlib import Path

from agentic_dynamics.core.language import _PROFILES
from agentic_dynamics.measurement.delta_entropy import (
    CLEAN_AND_RIGHT,
    CLEAN_BUT_WRONG,
    MESSY_AND_BROKEN,
    MESSY_BUT_RIGHT,
    classify_quadrant,
    compute_split_entropy,
    delta_split_entropy,
    is_test_file,
    split_files,
)

PY = _PROFILES["python"]
TS = _PROFILES["typescript"]
GO = _PROFILES["go"]


class TestIsTestFile:
    """The split rule — naming + tests/-dir, never a silent inclusion."""

    def test_python_test_prefix_is_test(self):
        assert is_test_file(Path("test_app.py"), PY)
        assert is_test_file(Path("test_utils.py"), PY)

    def test_python_test_dir_is_test(self):
        assert is_test_file(Path("tests/test_app.py"), PY)
        assert is_test_file(Path("pkg/tests/test_app.py"), PY)

    def test_python_solution_files_are_not_test(self):
        assert not is_test_file(Path("app.py"), PY)
        assert not is_test_file(Path("server.py"), PY)
        assert not is_test_file(Path("pkg/utils.py"), PY)

    def test_go_rust_suffix_is_test(self):
        assert is_test_file(Path("foo_test.go"), GO)

    def test_typescript_dot_test_is_test(self):
        assert is_test_file(Path("app.test.ts"), TS)
        assert is_test_file(Path("app.test.tsx"), TS)  # the .test. infix variant

    def test_solution_name_with_test_substring_is_not_test(self):
        # "contest.py" / "latest.py" contain "test" but are not test files by the rule.
        assert not is_test_file(Path("contest.py"), PY)
        assert not is_test_file(Path("latest.py"), PY)


class TestSplitFiles:
    def test_partition(self):
        files = [Path("app.py"), Path("test_app.py"), Path("tests/util_test.py"), Path("server.py")]
        solution, tests = split_files(files, PY)
        assert solution == [Path("app.py"), Path("server.py")]
        assert tests == [Path("test_app.py"), Path("tests/util_test.py")]


class TestComputeSplitEntropy:
    def _codebase(self, d: Path) -> None:
        (d / "app.py").write_text(
            "import os\n\n"
            "def add(a, b):\n    return a + b\n\n"
            "class Calc:\n    pass\n"
        )
        (d / "test_app.py").write_text(
            "import app\n\n"
            "def test_add():\n    assert app.add(1, 2) == 3\n\n"
            "def test_add_again():\n    assert app.add(2, 2) == 4\n"
        )

    def test_solution_profile_excludes_test_files(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            self._codebase(dp)
            split = compute_split_entropy(dp, PY)
            # The solution profile's import-edge bookkeeping records ONLY app.py (the test
            # file is excluded from the solution dimension).
            assert "app.py" in split.solution.imports_per_file
            assert "test_app.py" not in split.solution.imports_per_file
            # The tests profile records ONLY the test tree.
            assert "test_app.py" in split.tests.imports_per_file
            assert "app.py" not in split.tests.imports_per_file

    def test_delta_split_entropy_sign(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            base = Path(d1)
            final = Path(d2)
            (base / "app.py").write_text("def f():\n    pass\n")
            self._codebase(final)
            base_split = compute_split_entropy(base, PY)
            final_split = compute_split_entropy(final, PY)
            deltas = delta_split_entropy(base_split, final_split)
            assert "delta_h_solution" in deltas
            assert "delta_h_tests" in deltas


class TestClassifyQuadrant:
    """The four-quadrant decision table + the contract (ΔH without test-join = FAILED)."""

    def test_messy_but_right(self):
        assert classify_quadrant(0.5, 0.5, True) == MESSY_BUT_RIGHT

    def test_messy_and_broken(self):
        assert classify_quadrant(0.5, 0.5, False) == MESSY_AND_BROKEN

    def test_clean_and_right(self):
        assert classify_quadrant(-0.1, 1.0, True) == CLEAN_AND_RIGHT

    def test_clean_but_wrong_is_the_blind_spot(self):
        # ΔH low, tests fail — the 2d/2e unseen-family wall.
        assert classify_quadrant(-0.1, 0.5, False) == CLEAN_BUT_WRONG

    def test_threshold_boundary(self):
        # At exactly the threshold, ΔH is "low" (not strictly high).
        assert classify_quadrant(0.0, 1.0, False) == CLEAN_BUT_WRONG
        assert classify_quadrant(0.0, 1.0, True) == CLEAN_AND_RIGHT

    def test_missing_test_join_is_none(self):
        # The contract: a ΔH without the test-join is a FAILED finding (None), never a quadrant.
        assert classify_quadrant(0.5, None, True) is None       # linkage deferred
        assert classify_quadrant(0.5, 0.5, None) is None        # outcome unmeasured
        assert classify_quadrant(0.5, None, None) is None       # both absent

    def test_nonzero_threshold(self):
        assert classify_quadrant(0.01, 1.0, True, delta_h_threshold=0.05) == CLEAN_AND_RIGHT
        assert classify_quadrant(0.10, 1.0, True, delta_h_threshold=0.05) == MESSY_BUT_RIGHT
