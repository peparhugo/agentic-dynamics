"""Result-shape regressions for scripts/run.py (the g5 F4 finding).

An attempt with no collectable source must persist ``solution_code: null`` — never ``""``,
which is indistinguishable from an intentionally empty solution and would let a ladder
scorer count an uncollected attempt as empty source.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("run_module", _REPO_ROOT / "scripts" / "run.py")
assert _SPEC is not None and _SPEC.loader is not None
run_module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(run_module)


def test_serialize_solution_code_null_for_uncollected_source():
    assert run_module._serialize_solution_code(None) is None
    assert run_module._serialize_solution_code({}) is None


def test_serialize_solution_code_deterministic_headers():
    text = run_module._serialize_solution_code({"b.py": "b = 1\n", "a.py": "a = 1\n"})
    assert text is not None
    assert text.startswith("# === a.py ===")
    assert "# === b.py ===" in text
