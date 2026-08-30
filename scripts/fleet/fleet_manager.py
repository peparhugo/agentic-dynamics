#!/usr/bin/env python3
"""The fleet manager — the supervisor-tier daemon (proposal §2/D-14, §7 slice 1).

The supervisor is the fleet manager, **not an execution container**. It holds NO docker
socket (D-3/D-14): the pools are static (compose ``--scale`` counts), routine restarts are
docker's own ``restart: on-failure`` policies, and a fleet-level resize/drain is the
supervisor **commanding the orchestrator** (the socket-holder) over Redis ``fleet:commands``
(db1 / 6380) — the orchestrator's spawn-wrapper validates the request before any socket call.

This daemon does three things, all **read-only** with respect to spawning:

    watch     — the read-only watcher: queue depths + worker heartbeats + DLQ counts ->
                the board (a Redis JSON key + a per-line log), on a fixed cadence. It never
                spawns anything.
    status    — one-shot dump of the board (machine-readable JSON with ``--json``).
    resize / drain / restart — LPUSH a bounded command onto ``fleet:commands`` for the
                orchestrator to validate and execute (the supervisor's "hands", D-14).

The board is the supervisor's report surface: the Control Room portal and the game-board
snapshot read the ``fleet:board`` key, so the operator sees depth/heartbeats/DLQ live —
the visibility the bare ``setsid nohup`` workers never had.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# scripts/fleet/ -> add scripts/ to the path, then reuse the shared bootstrap.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import redis  # noqa: E402

import dlq  # noqa: E402  (scripts/fleet/ is this module's dir)
import heartbeat  # noqa: E402

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))

BOARD_KEY = "fleet:board"
COMMANDS_KEY = "fleet:commands"
DEFAULT_INTERVAL = 15.0  # seconds between board refreshes

# The queues the watcher surfaces (mirrors dlq.QUEUE_KEYS).
STATUS_KEYS = {
    "story_jobs": "story_status",
    "analysis_jobs": "analysis_status",
    "review_jobs": "review_status",
}

# Staleness threshold: a worker whose last heartbeat is older than this is "dead" on the
# board (the heartbeat cadence is 10s; 3 missed beats is generous for a busy worker).
STALE_SECONDS = 45.0


def _connect() -> redis.Redis:
    """Connect to the framework Redis (db1 / 6380), retrying with backoff like the workers."""
    delay = 2.0
    while True:
        try:
            client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
                decode_responses=True, socket_connect_timeout=5,
            )
            client.ping()
            return client
        except Exception as exc:  # noqa: BLE001 — the manager must survive a Redis blip
            print(f"[fleet-manager] redis unavailable ({exc}); retrying in {delay:.0f}s",
                  flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30.0)


def _queue_depth(client: redis.Redis, queue_key: str) -> int:
    try:
        return int(client.llen(queue_key))
    except Exception:  # noqa: BLE001
        return 0


def _status_counts(client: redis.Redis, status_key: str) -> dict[str, int]:
    """Tally a status hash (e.g. ``story_status``) by value: done/failed/running/queued."""
    counts: dict[str, int] = {}
    try:
        for v in client.hvals(status_key):
            counts[v] = counts.get(v, 0) + 1
    except Exception:  # noqa: BLE001
        pass
    return counts


def build_board(client: redis.Redis) -> dict:
    """Assemble the current board snapshot (pure read — never spawns)."""
    now = time.time()
    workers: list[dict] = []
    for k, hb in heartbeat.read_all(client).items():
        last_seen = float(hb.get("last_seen", 0) or 0)
        workers.append({
            "key": k,
            "last_seen": last_seen,
            "age_s": round(now - last_seen, 1),
            "alive": (now - last_seen) < STALE_SECONDS,
            "jobs": int(hb.get("jobs", 0) or 0),
            "pid": hb.get("pid"),
        })
    workers.sort(key=lambda w: w["key"])

    queues = {}
    for q, s in STATUS_KEYS.items():
        queues[q] = {
            "depth": _queue_depth(client, q),
            "status": _status_counts(client, s),
        }

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "queues": queues,
        "workers": workers,
        "alive_workers": sum(1 for w in workers if w["alive"]),
        "dead_workers": sum(1 for w in workers if not w["alive"]),
        "dlq": dlq.dead_counts(client),
    }


def publish_board(client: redis.Redis, board: dict) -> None:
    """Write the board snapshot to Redis (db1) for the Control Room / game board."""
    client.set(BOARD_KEY, json.dumps(board))


def watch(client: redis.Redis, interval: float, once: bool = False) -> None:
    """The read-only watcher loop: refresh the board on a cadence (``--once`` for one pass)."""
    print(f"[fleet-manager] watcher started (interval {interval}s, board -> {BOARD_KEY})",
          flush=True)
    while True:
        board = build_board(client)
        publish_board(client, board)
        print(f"[fleet-manager] board: {json.dumps(board, sort_keys=True)}", flush=True)
        if once:
            return
        time.sleep(interval)


def _send_command(client: redis.Redis, action: str, service: str, count: int | None,
                  backoff: int | None) -> dict:
    """LPUSH a bounded command onto ``fleet:commands`` (the supervisor's only hands, D-14)."""
    command = {
        "action": action,
        "service": service,
        "count": count,
        "backoff": backoff,
        "ts": time.time(),
        "nonce": uuid.uuid4().hex[:12],
    }
    client.lpush(COMMANDS_KEY, json.dumps(command))
    return command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The fleet manager (supervisor tier).")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("watch", help="read-only watcher loop (the board)")
    sub.add_parser("status", help="one-shot board dump")
    p_resize = sub.add_parser("resize", help="command the orchestrator to scale a service")
    p_resize.add_argument("--service", required=True)
    p_resize.add_argument("--count", type=int, required=True)
    p_drain = sub.add_parser("drain", help="command the orchestrator to drain a service")
    p_drain.add_argument("--service", required=True)
    p_restart = sub.add_parser("restart", help="command a restart-with-backoff")
    p_restart.add_argument("--service", required=True)
    p_restart.add_argument("--backoff", type=int, default=5, help="initial backoff seconds")

    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--json", action="store_true", help="status: emit JSON only")

    args = parser.parse_args(argv)
    client = _connect()

    if args.command == "watch":
        watch(client, args.interval, once=args.once)
        return 0

    if args.command == "status":
        board = build_board(client)
        if args.json:
            print(json.dumps(board, indent=2))
        else:
            for q, meta in board["queues"].items():
                print(f"{q}: depth={meta['depth']} status={meta['status']}")
            print(f"workers: alive={board['alive_workers']} dead={board['dead_workers']}")
            for w in board["workers"]:
                state = "alive" if w["alive"] else "DEAD "
                print(f"  [{state}] {w['key']} jobs={w['jobs']} age={w['age_s']}s pid={w['pid']}")
            print(f"dlq: {board['dlq']}")
        return 0

    if args.command == "resize":
        cmd = _send_command(client, "scale", args.service, args.count, None)
        print(f"fleet:commands <- {json.dumps(cmd)}")
        return 0

    if args.command == "drain":
        cmd = _send_command(client, "drain", args.service, None, None)
        print(f"fleet:commands <- {json.dumps(cmd)}")
        return 0

    if args.command == "restart":
        cmd = _send_command(client, "restart", args.service, None, args.backoff)
        print(f"fleet:commands <- {json.dumps(cmd)}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
