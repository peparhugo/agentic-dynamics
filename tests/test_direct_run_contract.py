"""Clean-environment invocation guards for the documented direct-run commands.

The 2026-09-12 review's reproduction: ``env -u PYTHONPATH python scripts/run_workflow.py
--help`` raised ``ModuleNotFoundError: No module named 'workflows'`` because ``_bootstrap``
added ``src/`` but not the repo root that hosts the top-level ``workflows/`` namespace package.
Pytest put the root on ``sys.path`` itself, masking the gap.

These subprocess tests run the commands with PYTHONPATH REMOVED and the parent's environment
otherwise intact — the shape an operator gets — so a future import that only resolves under
pytest fails here instead of in the field.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


@pytest.mark.parametrize(
    "script",
    ["scripts/run_workflow.py", "scripts/promote.py", "scripts/publish_release.py"],
)
def test_help_works_without_pythonpath(script):
    result = subprocess.run(
        [sys.executable, str(_ROOT / script), "--help"],
        cwd=_ROOT,
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"{script} --help failed:\n{result.stderr[-800:]}"
    assert "usage" in result.stdout.lower()
