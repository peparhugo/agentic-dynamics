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

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
# The repo root is required by direct-run scripts that import the top-level ``workflows/``
# package (a namespace package beside ``scripts/``) — e.g. ``scripts/run_workflow.py``'s
# ``from workflows.compile_workflow import load_spec_any``. Pytest puts the root on the path,
# which masked the missing entry; a clean ``env -u PYTHONPATH python scripts/...`` run did not.
# ``tests/test_direct_run_contract.py`` pins the clean-environment invocation.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
