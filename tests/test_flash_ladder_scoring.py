"""Pure-logic tests for the ladder cell scorer (layouts + decision rule)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "score_flash_ladder", _REPO / "scripts" / "score_flash_ladder.py"
)
assert _SPEC is not None and _SPEC.loader is not None
mod = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = mod
_SPEC.loader.exec_module(mod)

pytestmark = pytest.mark.fast


def test_collect_package_files_top_level_layout(tmp_path):
    package = tmp_path / "taskman"
    package.mkdir()
    (package / "__init__.py").write_text("x = 1\n")
    (package / "manager.py").write_text("y = 2\n")
    assert [rel for _, rel in mod.collect_package_files(tmp_path)] == [
        "taskman/__init__.py",
        "taskman/manager.py",
    ]
    blob = mod.blob_from_tree(tmp_path)
    assert blob is not None and blob.startswith("# === taskman/__init__.py ===")


def test_collect_package_files_src_layout_and_single_file(tmp_path):
    src = tmp_path / "src" / "taskman"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("x = 1\n")
    assert [rel for _, rel in mod.collect_package_files(tmp_path)] == ["src/taskman/__init__.py"]

    other = tmp_path / "other"
    other.mkdir()
    (other / "taskman.py").write_text("x = 1\n")
    rels = {rel for _, rel in mod.collect_package_files(tmp_path)}
    assert "other/taskman.py" in rels


def test_blob_none_without_sources(tmp_path):
    assert mod.blob_from_tree(tmp_path) is None


def test_decision_escalates_on_quality_delta():
    conditions = [
        {"condition": "C0", "D": 0.30, "Q": 3},
        {"condition": "C1", "D": 0.31, "Q": 2},
    ]
    decision = mod.build_decision(conditions)
    assert decision["escalate"] is True
    assert decision["largest_effect"] == "C1"


def test_decision_escalates_on_diversity_margin():
    conditions = [
        {"condition": "C0", "D": 0.30, "Q": 3},
        {"condition": "C2", "D": 0.41, "Q": 3},
    ]
    assert mod.build_decision(conditions)["escalate"] is True


def test_decision_flat_within_margin():
    conditions = [
        {"condition": "C0", "D": 0.30, "Q": 3},
        {"condition": "C1", "D": 0.35, "Q": 3},
        {"condition": "C3", "D": 0.39, "Q": 3},
    ]
    decision = mod.build_decision(conditions)
    assert decision["escalate"] is False
    assert "no policy claim" in decision["adaptive_directive"]
