"""Dynamic-code admin portal backend (the Control Room).

Serves the admin dashboard and exposes live experiment telemetry over SSE. This module is now
the *composition root* (refactor-repair Debt-1): the 32 routes live in ``routes/``, the business
logic in ``services/``, the external-interface clients in ``clients/``, and the filesystem paths
in ``paths.py``. This file keeps the shared context — configuration constants, the Redis /
manager / client factories, the parsed-manifest cache, and the Flask ``app`` — and builds the
``ControlRoomServices`` application context (review P2) that it injects into route registration,
so the routes receive their dependencies instead of importing this module as a service locator.
It still re-exports the names the tests monkeypatch (``_redis``, ``_design_sessions``,
``DATA_MANIFEST_PATH``, …): the injected services delegate back to those names at call time, so
the existing test suite is behaviour-identical.

Endpoints (32 routes across 6 API categories, plus the static shell):

    Legacy telemetry (7):
        GET  /api/matrix · GET /api/status · GET /api/events/<cell_id>
        GET  /api/projections   (knowledge projection watermarks — control_db_publication p3)
        GET  /api/routing · GET /api/subscription-usage
        POST /api/experiments · POST /api/queue/reinterleave
    Supervisor flags (3):
        GET  /api/flags · POST /api/flags/<session_id>/steer · /interrupt
    Registry (2):
        GET  /api/registry · GET /api/registry/<entity_id>
    Design sessions (7):
        GET/POST /api/design-sessions · /<portal_id>/spec · /input · /interrupt · /save · /run
    Claude background sessions (9):
        GET/POST /api/claude-agents · /<session_id>/logs · /stop · /respawn · /rm · /steer ·
        /daemon · /daemon/stop
    Docs health (2):
        GET  /api/docs-health · POST /api/docs-health/approve
    Static shell (1):
        GET  / — static dashboard (apps/control_room/static)

Run:
    python3 apps/control_room/server.py      # default port 8000 (FINOPS_PORT override)

Deployment note: ``app.run(threaded=True)`` is Flask's built-in single-process development
server, intended for a local operator tool rather than production. For multi-operator use, front
it with a threaded gunicorn:

    gunicorn --worker-class gthread --threads 4 --workers 1 \
      --bind 127.0.0.1:8000 'apps.control_room.server:app'
"""

from __future__ import annotations

import os
import re
import subprocess  # noqa: F401  # re-exported — tests monkeypatch ``server.subprocess.run``
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
# scripts/ is not an importable package (no __init__.py), so the repo root is added here so
# `from scripts import registry` resolves via Python's implicit namespace-package support.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# The routes/services import this module as ``apps.control_room.server``. Under the documented
# ``python3 apps/control_room/server.py`` script launch it runs as ``__main__`` instead, which
# would otherwise double-load this module into a second Flask ``app``. Register the canonical
# name so both entry points share ONE module (and ONE ``app``).
if __name__ == "__main__":  # pragma: no cover - script launch only
    sys.modules["apps.control_room.server"] = sys.modules["__main__"]

from flask import Flask

from agentic_dynamics.control.live import EVENT_LOG_MAX  # noqa: F401  # re-exported for tests
from apps.control_room.clients.claude_agents_client import ClaudeAgentsClient
from apps.control_room.clients.opencode_client import OpenCodeClient
from apps.control_room.paths import (  # noqa: F401  # re-exported for services + tests
    DATA_MANIFEST_PATH,
    DOCS_DRIFT_RESULTS_DIR,
    ROOT,
    SUPERVISOR_ACTIVE_WINDOW_SECONDS,
    SUPERVISOR_FILE_TAIL_BYTES,
    SUPERVISOR_FLAGS_FILE,
)
from apps.control_room.services.design_sessions import DesignSessionManager
from scripts import registry as registry_cli  # noqa: F401  # re-exported for tests

# ── Configuration ────────────────────────────────────────────────

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
QUEUE_KEY = "story_jobs"
RESULTS_KEY = "story_results"
# Post-hoc pipeline stages. The execute stage is the story queue above; the analyze and review
# stages are separate Redis pairs written by enqueue_analysis.py/analysis_worker.py and
# enqueue_reviews.py/review_all.py. None of the post-hoc workers publish to a pub/sub channel,
# so these are only visible through the poll-driven /api/matrix snapshot.
ANALYSIS_QUEUE_KEY = "analysis_jobs"
ANALYSIS_STATUS_KEY = "analysis_status"
REVIEW_QUEUE_KEY = "review_jobs"
REVIEW_STATUS_KEY = "review_status"
HEARTBEAT_SECONDS = 15
MAX_DESIGN_REQUEST_BYTES = 64 * 1024
MAX_DESIGN_PROMPT_CHARS = 12_000
MAX_CLAUDE_AGENT_REQUEST_BYTES = 64 * 1024
MAX_CLAUDE_AGENT_TASK_CHARS = 12_000
MAX_CLAUDE_AGENT_LOG_BYTES = 64 * 1024
#: How many most-recent cost samples the /api/matrix fleet snapshot ships per cell. The full
#: retained window (EVENT_LOG_MAX, 500) would make every 5s poll a ~4 MB download; the fleet
#: sparkline + burn trace only ever render the rolling 60s window, and the full per-cell history
#: is available on demand via /api/events/<cell_id>. Aggregates are still computed over the FULL
#: retained window — only the sample LIST is trimmed.
RETAINED_SAMPLES_MAX = 60
CLAUDE_AGENT_ADVISORS = {"fable", "opus", "sonnet"}
CLAUDE_AGENT_ADVISOR_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,80}$")
IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60

#: The only delivery modes a design-session prompt may be admitted under. The server (not the
#: browser) fixes the allowed set: an unknown value is rejected before any OpenCode side effect.
DESIGN_DELIVERY_MODES = ("queue", "steer")

app = Flask(__name__, static_folder="static", static_url_path="/static")
_design_manager: DesignSessionManager | None = None
_claude_agents_client: ClaudeAgentsClient | None = None

#: Parsed-manifest cache for ``/api/registry*``. Keyed on ``(path, mtime_ns, size)`` — the
#: manifest is only rewritten by ``generate_manifest.py``, so mtime+size is a stronger
#: invalidation signal than a wall-clock TTL.
_REGISTRY_CACHE: dict[tuple[str, int | None, int | None], list[dict[str, Any]]] = {}


def _redis() -> Any:
    # ``redis`` is imported lazily so the server can be imported without the dependency;
    # the connection is only constructed on the first request that touches Redis.
    import redis

    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


def _design_sessions() -> DesignSessionManager:
    """Construct the process-local manager around persistent Redis metadata."""
    global _design_manager
    if _design_manager is None:
        configured = os.environ.get("FINOPS_DESIGN_WORKDIRS")
        paths = (
            [Path(item) for item in configured.split(os.pathsep) if item]
            if configured
            else [ROOT]
        )
        workdirs = {
            "repository" if index == 0 else f"repository-{index + 1}": path
            for index, path in enumerate(paths)
        }
        _design_manager = DesignSessionManager(
            root=ROOT,
            redis_factory=_redis,
            opencode=OpenCodeClient(os.environ.get("OPENCODE_SERVER_URL", "http://127.0.0.1:4096")),
            workdirs=workdirs,
        )
    return _design_manager


def _opencode_client() -> OpenCodeClient:
    """Construct the server-side control client without exposing its URL."""
    return OpenCodeClient(os.environ.get("OPENCODE_SERVER_URL", "http://127.0.0.1:4096"))


def _utc_now() -> str:
    """Return a canonical UTC timestamp for API envelopes."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _claude_agents() -> ClaudeAgentsClient:
    """Construct the process-local ``claude`` CLI wrapper used for one-shot calls.

    Only short, bounded, one-shot mutating commands (start/stop/respawn/rm/daemon status/daemon
    stop) go through this client from Flask request handlers; continuous polling belongs to
    ``scripts/claude_agents_supervisor.py`` (docs/spec.md §2.1).
    """
    global _claude_agents_client
    if _claude_agents_client is None:
        _claude_agents_client = ClaudeAgentsClient()
    return _claude_agents_client


def _claude_agent_workdirs() -> dict[str, Path]:
    """Parse the approved-workdir allowlist independently of ``_design_sessions()``.

    A raw filesystem path from the browser is never accepted; only a key into this dict is,
    mirroring ``DesignSessionManager``'s ``workdir_key`` rule.
    """
    configured = os.environ.get("FINOPS_CLAUDE_AGENT_WORKDIRS")
    paths = [Path(item) for item in configured.split(os.pathsep) if item] if configured else [ROOT]
    return {
        "repository" if index == 0 else f"repository-{index + 1}": path
        for index, path in enumerate(paths)
    }


# Bottom-of-module imports (break the circular import by construction): both happen only after
# every name above is defined. The supervisor service functions are re-exported so the tests'
# monkeypatch of ``server._emit_actuation_record`` / ``server._load_supervisor_flags`` /
# ``server._authorize_supervisor_action`` resolves through this module's namespace; the routes
# are then registered on ``app`` with the explicit application context (review P2 — routes receive
# ``ControlRoomServices`` rather than importing this module as a service locator).
from apps.control_room import routes as _routes  # noqa: E402
from apps.control_room.services.context import build_services  # noqa: E402
from apps.control_room.services.supervisor import (  # noqa: E402,F401
    _authorize_supervisor_action,
    _emit_actuation_record,
    _load_supervisor_flags,
)

_routes.register(app, build_services())


if __name__ == "__main__":
    port = int(os.environ.get("FINOPS_PORT", "8000"))
    # Secure default: loopback only. Bind wider via FINOPS_HOST=0.0.0.0 explicitly.
    host = os.environ.get("FINOPS_HOST", "127.0.0.1")
    app.run(host=host, port=port, threaded=True)
