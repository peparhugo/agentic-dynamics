"""Portfolio scorer tests (g5 round-2 F2/F4): result JSON -> conditions, null exclusion."""

from __future__ import annotations

import json
from pathlib import Path

from agentic_dynamics.measurement.portfolio_score import score_result_files

A = "def f():\n    return 1\n"
B = "class G:\n    def run(self):\n        return 2\n"


def _write(path: Path, runs: list[dict]) -> None:
    path.write_text(json.dumps({"experiment": "fixture", "model": "m", "runs": runs}))


def test_scorer_excludes_null_source_and_reports_coverage(tmp_path):
    results = tmp_path / "flash_x.json"
    _write(results, [
        {"operator": "framing", "strength": 1.0, "solution_code": A},
        {"operator": "framing", "strength": 1.0, "solution_code": B},
        {"operator": "framing", "strength": 1.0, "solution_code": None},
    ])
    score = score_result_files([results], group_by=("operator", "strength"))
    (cond,) = score.conditions
    assert cond.condition == "operator=framing|strength=1.0"
    assert cond.n_attempts == 3
    assert cond.n_scored == 2
    assert cond.excluded_null_source == 1
    assert cond.diversity.coverage == "full"
    assert cond.diversity.mean_composite is not None and cond.diversity.mean_composite > 0


def test_scorer_all_null_is_empty_not_zero(tmp_path):
    results = tmp_path / "flash_y.json"
    _write(results, [
        {"operator": "thinking", "strength": 1.0, "solution_code": None},
        {"operator": "thinking", "strength": 1.0, "solution_code": None},
    ])
    score = score_result_files([results], group_by=("operator", "strength"))
    (cond,) = score.conditions
    assert cond.excluded_null_source == 2
    assert cond.diversity.coverage == "empty"
    assert cond.diversity.mean_composite is None


def test_scorer_persists_input_hashes_and_code_sha(tmp_path):
    results = tmp_path / "flash_z.json"
    _write(results, [{"operator": "op", "strength": 0.5, "solution_code": A}])
    payload = score_result_files([results]).to_dict()
    assert payload["inputs"][0]["path"].endswith("flash_z.json")
    assert len(payload["inputs"][0]["sha256"]) == 64
    assert payload["code_sha"]
    assert payload["conditions"][0]["n_attempts"] == 1


def test_scorer_reports_invalid_source_separately(tmp_path):
    """Omitted or malformed source fields are counted, never silently unscored (F2-round-2)."""
    results = tmp_path / "flash_w.json"
    _write(results, [
        {"operator": "op", "strength": 1.0, "solution_code": None},
        {"operator": "op", "strength": 1.0, "solution_code": A},
        {"operator": "op", "strength": 1.0},
        {"operator": "op", "strength": 1.0, "solution_code": 42},
    ])
    (cond,) = score_result_files([results]).conditions
    assert cond.n_attempts == 4
    assert cond.n_scored == 1
    assert cond.excluded_null_source == 1
    assert cond.excluded_invalid_source == 2
    assert cond.diversity.coverage == "single"
    assert cond.diversity.mean_composite is None
