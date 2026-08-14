"""Live telemetry — Redis Pub/Sub publisher for background experiment progress.

No-ops gracefully when Redis is unavailable or ``FINOPS_CELL_ID`` is unset, so
an experiment run never fails because the dashboard is down. Channels mirror
``scripts/monitor.py``:

    - status hash:      ``story_status``         (cell_id -> queued|running|done|failed|timeout)
    - pub/sub channel:  ``status``               (status transitions)
    - pub/sub channel:  ``events:{cell_id}``     (per-cell session event stream)
"""

from __future__ import annotations

import json
import os
from typing import Any

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
STATUS_KEY = "story_status"
STATUS_CHANNEL = "status"
EVENT_CHANNEL_PREFIX = "events:"
EVENT_LOG_PREFIX = "events_log:"
EVENT_LOG_MAX = 500


def _connect() -> Any:
    """Connect to Redis, returning None if unavailable (never raises)."""
    try:
        import redis

        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_keepalive=False,
        )
        r.ping()
        return r
    except Exception:
        return None


class LivePublisher:
    """Publish live experiment progress to Redis Pub/Sub.

    Disables itself permanently after the first failure so a downed Redis
    server costs one attempt, not one per event.
    """

    def __init__(self, cell_id: str | None = None) -> None:
        self.cell_id = cell_id or os.environ.get("FINOPS_CELL_ID", "").strip()
        self._r = _connect() if self.cell_id else None
        self._disabled = self._r is None

    @property
    def enabled(self) -> bool:
        return not self._disabled and bool(self.cell_id)

    def publish_status(self, status: str) -> None:
        """Publish a cell status transition to the ``status`` channel."""
        if not self.enabled:
            return
        try:
            self._r.publish(STATUS_CHANNEL, json.dumps({"cell_id": self.cell_id, "status": status}))
        except Exception:
            self._disabled = True

    def set_status(self, status: str) -> None:
        """Record status in the ``story_status`` hash AND publish the transition.

        The portal's fleet reads the hash (``GET /api/matrix``); the live stream reads
        the channel (``GET /api/status``). Both must be updated for a cell to appear.
        """
        if not self.enabled:
            return
        try:
            self._r.hset(STATUS_KEY, self.cell_id, status)
            self._r.publish(STATUS_CHANNEL, json.dumps({"cell_id": self.cell_id, "status": status}))
        except Exception:
            self._disabled = True

    def publish_event(self, event: dict[str, Any] | str) -> None:
        """Publish a single session event to ``events:{cell_id}``.

        Also appends to a bounded history list (``events_log:{cell_id}``) so a
        portal can replay the tail before subscribing — Redis pub/sub has no
        message history.
        """
        if not self.enabled:
            return
        payload = event if isinstance(event, str) else json.dumps(event)
        channel = f"{EVENT_CHANNEL_PREFIX}{self.cell_id}"
        log_key = f"{EVENT_LOG_PREFIX}{self.cell_id}"
        try:
            self._r.publish(channel, payload)
            self._r.lpush(log_key, payload)
            self._r.ltrim(log_key, 0, EVENT_LOG_MAX - 1)
        except Exception:
            self._disabled = True


def make_publisher() -> LivePublisher | None:
    """Return a LivePublisher for the current cell, or None if disabled.

    Driven by the ``FINOPS_CELL_ID`` env var (set by the experiment worker so
    every backend session in the process tree publishes to the right cell).
    """
    cell_id = os.environ.get("FINOPS_CELL_ID", "").strip()
    if not cell_id:
        return None
    return LivePublisher(cell_id)
