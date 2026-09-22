"""The bare positional `check` refuses instead of silently syncing (L28, 2026-09-22).

The L21 retrospective documented `python3 scripts/sync_data.py check` as its parity command;
the positional fell through to a full SYNC — reproduced live: it printed "Synced:" and rewrote
the identity sidecar. Fail-first is deliberately NOT run in-place here (the unguarded form
REWRITES the tracked parquet — the exact defect); the guard's refusal is what this pins.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_a_bare_positional_refuses_instead_of_syncing(tmp_path: Path):
    run = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "sync_data.py"), "check"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run.returncode == 2, run.stderr
    assert "did you mean --check" in run.stderr
    assert "refusing" in run.stderr
