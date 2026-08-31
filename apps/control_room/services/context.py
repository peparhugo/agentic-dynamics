"""The Control Room's explicit application context (review P2 — the service locator).

The composition root (``apps.control_room.server``) used to hand its dependencies to the route
modules implicitly: every route module did ``from apps.control_room import server`` and read
``server._redis`` / ``server._design_sessions`` / ``server._DUCK`` / ``server._DEMO_MODE`` … at
request time. That is the composition root used as a service locator — a circular conceptual
dependency between the routes and the server, with the tests only passing because they
monkeypatch the server module's private names.

This dataclass makes the dependencies explicit. ``server.py`` builds ONE instance (see
:func:`build_services`) and passes it into ``routes.register(app, services)``; each route module
stores it and reads ``services.redis()`` / ``services.design_manager()`` /
``services.supervisor`` … instead of reaching into the server module.

**Behaviour-identical by construction.** Every *lazy* accessor delegates to the ``server`` module
at call time (not at import/construction), so a test's ``monkeypatch.setattr(server, "_redis", …)``
keeps working unchanged — the injected service resolves the monkeypatched name on each call rather
than snapshotting it at import. Stable configuration (Redis keys, byte caps, advisory sets) is
copied once at construction: it never changes within a process and is never monkeypatched, so a
plain field is honest where a lazy property would be ceremony.

This is a *local* change — the five route modules swap one import and one accessor prefix; no
other module changes shape.

**Injected data sources.** Beyond the service modules and the lazy ``server`` accessors, the
context also carries the *authorities* a route consults for a derived population — currently
:attr:`ControlRoomServices.review_stage_source`. A route must never hard-wire which authority
answers "how many reviews are there?": that binding is a composition-root decision, so it lives
here as an explicit, overridable field. Production binds the file-derived
``pipeline_status.review_stage_summary`` (the reviews on disk are the single source of truth the
pipeline actually writes); a test binds whatever authority it wants and can therefore isolate the
route from the filesystem *completely* — no monkeypatching of module globals, no partial
stubbing. The field is deliberately REQUIRED (no dataclass default) so that dropping the
injection is a loud ``TypeError`` at construction rather than a silent fallback to the real
filesystem, which would let a route quietly re-acquire the dependency the injection removed.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from agentic_dynamics.control.pipeline_status import review_stage_summary
from apps.control_room import server
from apps.control_room.services import design_sessions, mutations, registry, supervisor, telemetry

#: An authority that answers "what is the review-stage population?".
#:
#: Takes the request's Redis client and returns one pipeline-stage summary dict (the same shape
#: ``pipeline_status.stage_summary`` returns: ``total``/``queued``/``running``/``done``/… ). The
#: client is passed even to sources that ignore it (the production file-derived source does), so
#: every source shares one signature and a Redis-backed authority stays swappable in.
ReviewStageSource = Callable[[Any], dict[str, Any]]


@dataclass
class ControlRoomServices:
    """The Control Room's injected application context."""

    # -- service modules (the business logic extracted in refactor-repair Debt-1) --
    telemetry: ModuleType
    registry: ModuleType
    supervisor: ModuleType
    design_sessions: ModuleType
    mutations: ModuleType

    # -- stable configuration (copied once at build; never monkeypatched) --
    queue_key: str
    results_key: str
    analysis_queue_key: str
    analysis_status_key: str
    review_queue_key: str
    review_status_key: str
    heartbeat_seconds: int
    root: Path
    max_design_prompt_chars: int
    design_delivery_modes: tuple[str, ...]
    claude_agent_advisors: frozenset[str]
    claude_agent_advisor_id_pattern: re.Pattern[str]
    max_claude_agent_log_bytes: int
    max_claude_agent_task_chars: int

    # -- injected data sources (the authority a route consults, chosen by the composition root) --

    #: The authority for the review-stage population served by ``GET /api/matrix``.
    #:
    #: REQUIRED on purpose — see the module docstring. Production binds the file-derived
    #: ``review_stage_summary``; tests bind their own source to isolate the route from disk.
    review_stage_source: ReviewStageSource

    # -- lazy server accessors (delegate at call time so monkeypatch still wins) --

    def redis(self) -> Any:
        """A fresh Redis client from the server's factory (``server._redis``, monkeypatched)."""
        return server._redis()

    def design_manager(self) -> Any:
        """The process-local ``DesignSessionManager`` (``server._design_sessions``)."""
        return server._design_sessions()

    def opencode_client(self) -> Any:
        """The server-side OpenCode control client (``server._opencode_client``)."""
        return server._opencode_client()

    def claude_agents(self) -> Any:
        """The one-shot ``claude`` CLI wrapper (``server._claude_agents``)."""
        return server._claude_agents()

    def claude_agent_workdirs(self) -> dict[str, Path]:
        """The approved-workdir allowlist, keyed by workdir label."""
        return server._claude_agent_workdirs()

    def load_supervisor_flags(self, limit: int) -> tuple[Any, int]:
        """Read retained supervisor flags (``server._load_supervisor_flags``)."""
        return server._load_supervisor_flags(limit)

    def authorize_supervisor_action(self, session_id: str, cell_id: str) -> tuple[Any, Any]:
        """Recheck ownership before a steer/interrupt (``server._authorize_supervisor_action``)."""
        return server._authorize_supervisor_action(session_id, cell_id)

    def emit_actuation_record(self, *args: Any, **kwargs: Any) -> Any:
        """Best-effort actuation emit (``server._emit_actuation_record``, monkeypatched)."""
        return server._emit_actuation_record(*args, **kwargs)

    @property
    def data_manifest_path(self) -> Path:
        """The manifest path (``server.DATA_MANIFEST_PATH``, monkeypatched in the registry tests)."""
        return server.DATA_MANIFEST_PATH


def build_services() -> ControlRoomServices:
    """Build the application context from the server module's live configuration.

    Called once from ``server.py``'s composition root, after every config constant and factory is
    defined. Service modules and stable config are resolved eagerly; the lazy accessors resolve
    through ``server`` on every later call.
    """
    return ControlRoomServices(
        telemetry=telemetry,
        registry=registry,
        supervisor=supervisor,
        design_sessions=design_sessions,
        mutations=mutations,
        queue_key=server.QUEUE_KEY,
        results_key=server.RESULTS_KEY,
        analysis_queue_key=server.ANALYSIS_QUEUE_KEY,
        analysis_status_key=server.ANALYSIS_STATUS_KEY,
        review_queue_key=server.REVIEW_QUEUE_KEY,
        review_status_key=server.REVIEW_STATUS_KEY,
        heartbeat_seconds=server.HEARTBEAT_SECONDS,
        root=server.ROOT,
        max_design_prompt_chars=server.MAX_DESIGN_PROMPT_CHARS,
        design_delivery_modes=server.DESIGN_DELIVERY_MODES,
        claude_agent_advisors=frozenset(server.CLAUDE_AGENT_ADVISORS),
        claude_agent_advisor_id_pattern=server.CLAUDE_AGENT_ADVISOR_ID_PATTERN,
        max_claude_agent_log_bytes=server.MAX_CLAUDE_AGENT_LOG_BYTES,
        max_claude_agent_task_chars=server.MAX_CLAUDE_AGENT_TASK_CHARS,
        # The production review authority: the review FILES on disk. The legacy
        # review_jobs/review_status Redis state was retired from the display (the trigger →
        # review_all cut-over never wrote it), so binding it here would report a stale zero.
        review_stage_source=review_stage_summary,
    )
