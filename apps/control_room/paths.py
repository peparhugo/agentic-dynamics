"""Filesystem paths for the Control Room (refactor-repair Debt-1).

The repo-root-relative files the Control Room reads by default. Extracted out of ``server.py``
so a path change never has to touch the route handlers. ``server`` re-exports these names, so
the tests that monkeypatch ``server.DATA_MANIFEST_PATH`` / ``server.SUPERVISOR_FLAGS_FILE``
keep working unchanged.
"""

from __future__ import annotations

import os

from agentic_dynamics.core.paths import PROJECT_ROOT

#: Repository root. Re-pointed to the single source of truth
#: (``agentic_dynamics.core.paths.PROJECT_ROOT``) after the admin/ → apps/control_room/
#: move — the former ``Path(__file__).resolve().parent.parent`` resolved to
#: ``<repo>/apps``, which silently re-homed every default path below under
#: ``apps/experiments/...`` (refactor-repair P0-3).
ROOT = PROJECT_ROOT

SUPERVISOR_FLAGS_FILE = ROOT / "experiments" / "results" / "supervisor" / "flags.jsonl"
SUPERVISOR_FILE_TAIL_BYTES = 512 * 1024
SUPERVISOR_ACTIVE_WINDOW_SECONDS = int(os.environ.get("SUPERVISOR_ACTIVE_WINDOW", "900"))

#: Where generate_manifest.py writes the compacted registry array the /api/registry* routes
#: read. Same file scripts/registry.py's CLI reads (registry_cli.DATA_MANIFEST_PATH) — this is
#: the Control Room's own copy of that constant so a test can monkeypatch it independently.
DATA_MANIFEST_PATH = ROOT / "experiments" / "data_manifest.json"
