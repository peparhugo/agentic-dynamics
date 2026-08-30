#!/usr/bin/env python3
"""Worker heartbeats — the fleet's liveness signal (design §4, proposal §7 slice 1).

Each worker (story / analysis / review / kb consumer) writes a heartbeat key
``worker:<type>:<id>`` -> ``{last_seen, jobs, pid, started_at}`` on Redis db1 / 6380. The
fleet manager's read-only watcher surfaces these to the game board; a worker whose
``last_seen`` is stale is a dead worker (the fleet previously had no way to see this — the
"fleet has no watcher" gap).

This module is deliberately dependency-light (only ``redis``, a pyproject dependency) so it
runs both on the host and inside the ``fleet/base`` container. It exposes:

    publish(client, worker_type, worker_id, *, jobs=0, pid=None)   — one heartbeat
    HeartbeatThread(worker_type, worker_id, *, interval)           — a daemon thread loop
    read_all(client) -> dict                                       — the watcher's reader
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone

import redis

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
HEARTBEAT_PREFIX = "worker"

DEFAULT_INTERVAL = 10.0  # seconds between beats


def key(worker_type: str, worker_id: str) -> str:
    """The Redis key for a worker's heartbeat (``worker:<type>:<id>``)."""
    return f"{HEARTBEAT_PREFIX}:{worker_type}:{worker_id}"


def publish(client: redis.Redis, worker_type: str, worker_id: str, *,
            jobs: int = 0, pid: int | None = None) -> None:
    """Write one heartbeat for a worker.

    ``last_seen`` is epoch seconds (the watcher compares it against ``now``); ``jobs`` is
    the number of jobs the worker has completed; ``pid`` is the worker's OS pid (for the
    autopsies the bare processes lacked).
    """
    now = time.time()
    payload = {
        "last_seen": f"{now:.3f}",
        "jobs": str(jobs),
        "pid": str(pid if pid is not None else os.getpid()),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    client.hset(key(worker_type, worker_id), mapping=payload)


def read_all(client: redis.Redis) -> dict[str, dict]:
    """Read every worker heartbeat for the watcher.

    Returns a dict keyed by the full key, each value a decoded ``{last_seen, jobs, pid,
    started_at}``. Workers that never beat are simply absent — the manager's staleness
    check is what distinguishes a dead worker from a missing one.
    """
    out: dict[str, dict] = {}
    for k in client.scan_iter(match=f"{HEARTBEAT_PREFIX}:*", count=100):
        # `type()` returns bytes (b"hash") with decode_responses=False and str ("hash") with
        # decode_responses=True — accept both so the reader is client-configuration-agnostic.
        if client.type(k) in (b"hash", "hash"):
            out[k] = client.hgetall(k)
    return out


class HeartbeatThread(threading.Thread):
    """A daemon thread that publishes a heartbeat on a fixed cadence.

    Attached to a worker process; never raises (a Redis blip logs and continues — the
    next beat will land when the store recovers, exactly like the worker loops' own
    reconnection backoff).
    """

    def __init__(self, worker_type: str, worker_id: str, *,
                 client: redis.Redis | None = None,
                 interval: float = DEFAULT_INTERVAL,
                 jobs_counter: Callable[[], int] | None = None) -> None:
        super().__init__(daemon=True, name=f"heartbeat:{worker_type}:{worker_id}")
        self.worker_type = worker_type
        self.worker_id = worker_id
        self.interval = interval
        self.client = client
        # A zero-arg callable returning the current completed-job count, if the caller
        # tracks it; None means the worker process does not expose a counter.
        self.jobs_counter = jobs_counter
        self._stop = threading.Event()

    def stop(self) -> None:
        """Signal the loop to exit (the thread is a daemon, so this is optional)."""
        self._stop.set()

    def run(self) -> None:
        client = self.client or redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
            decode_responses=True, socket_connect_timeout=5,
        )
        while not self._stop.is_set():
            try:
                jobs = int(self.jobs_counter()) if self.jobs_counter else 0
                publish(client, self.worker_type, self.worker_id, jobs=jobs)
            except Exception as exc:  # noqa: BLE001 — a heartbeat must never kill a worker
                print(f"[heartbeat] publish failed: {exc}", flush=True)
            self._stop.wait(self.interval)
