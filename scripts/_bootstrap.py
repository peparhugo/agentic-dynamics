"""Shared sys.path bootstrap for `python scripts/*.py` direct runs.

Inserts the repo's ``src/`` directory onto ``sys.path`` so the package resolves
without an editable install. Consolidates the ~55 per-file
``sys.path.insert(0, str(... / "src"))`` lines (consolidation Stage 1, phase C).
Imported by scripts as a side-effecting module:

    import _bootstrap  # noqa: E402  (inserts src/ onto sys.path)

The direct-run contract is unchanged: ``python scripts/foo.py`` still works, because
Python puts ``scripts/`` on ``sys.path[0]`` and this module lives beside them.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
