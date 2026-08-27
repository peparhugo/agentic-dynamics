"""Server-level orphan sweep daemon (cap_runner_hardening2 §Gap 1) — FLAG-ONLY, never steer.

Observes the opencode server's session store (the same surface the Control Room's supervisor
rail reads) and detects orphaned delegations: a task whose parent session has no meaningful
step after the task's spawn time AND whose subagent session/process has terminated
(completed or crashed). On detection it records the orphan on the durable ledger
(``experiments/results/orphans/orphans.jsonl``) + the bounded Redis ``orphan_events`` hot
list + the canonical registry, reaps the orphaned subagent's process if still alive, and
surfaces the record.

No steering: the sweep never restarts, retries, resumes, or steers a session. The one
"actuation" is zombie reaping (SIGTERM of a leaked process that references an already-
terminated subagent), which is observation + reaping, not control.

Cadence: a periodic sweep (default every 5 min, ``ORPHAN_SWEEP_INTERVAL``); detection is a
deterministic function of the transcript timestamps (see
``agentic_dynamics/control/orphan_sweep.py``).
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.control.orphan_sweep import (  # noqa: E402
    CRASH_GRACE_S,
    SWEEP_INTERVAL_S,
    OrphanRecord,
    SQLiteSessionStore,
    sweep_once,
)

#: The opencode server's session store — same DB every Control Room surface reads.
OPENCODE_DB = Path(os.environ.get("OPENCODE_DB", str(Path.home() / ".local/share/opencode/opencode.db")))
#: The durable orphan ledger (append-only JSONL — the "dated, flagged events" requirement).
LEDGER = ROOT / "experiments" / "results" / "orphans" / "orphans.jsonl"
INTERVAL = int(os.environ.get("ORPHAN_SWEEP_INTERVAL", str(SWEEP_INTERVAL_S)))
CRASH_GRACE = int(os.environ.get("ORPHAN_SWEEP_CRASH_GRACE", str(CRASH_GRACE_S)))


def _redis():
    """Framework Redis client (6380/DB 1) for the hot path; file + registry stay useful."""
    import redis

    return redis.Redis(
        host=os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1"),
        port=int(os.environ.get("FINOPS_REDIS_PORT", "6380")),
        db=int(os.environ.get("FINOPS_REDIS_DB", "1")),
        decode_responses=True,
        socket_connect_timeout=2,
    )


def log(msg: str) -> None:
    print(f"[orphan-sweep] {msg}", flush=True)


def sweep(*, db_path: Path, ledger_path: Path, now_ms: int | None = None) -> list[OrphanRecord]:
    """One full sweep over the live session store: observe → detect → reap → record → surface."""
    import contextlib

    redis_client = None
    with contextlib.suppress(Exception):  # noqa: BLE001 — file + registry stay useful when Redis is down
        redis_client = _redis()
    store = SQLiteSessionStore(db_path)
    try:
        return sweep_once(
            store,
            ledger_path=ledger_path,
            redis_client=redis_client,
            now_ms=now_ms,
            crash_grace_s=CRASH_GRACE,
        )
    finally:
        store.close()


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Server-level orphan sweep — observe the opencode session store, flag "
                    "orphaned delegations. FLAG-ONLY, never steers."
    )
    ap.add_argument("--once", action="store_true", help="run one sweep and exit")
    ap.add_argument("--db", default=str(OPENCODE_DB), help="opencode session store path")
    ap.add_argument("--ledger", default=str(LEDGER), help="orphan ledger JSONL path")
    ap.add_argument(
        "--interval",
        type=int,
        default=INTERVAL,
        help="sweep cadence in seconds (default: ORPHAN_SWEEP_INTERVAL, else 300)",
    )
    ap.add_argument(
        "--crash-grace",
        type=int,
        default=CRASH_GRACE,
        help="subagent crash grace in seconds (default: ORPHAN_SWEEP_CRASH_GRACE, else 300)",
    )
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        log(f"session store not found at {db_path}; sweep cannot observe")
        raise SystemExit(1)
    log(f"orphan sweep watching {db_path}; cadence {args.interval}s; ledger -> {args.ledger}")

    while True:
        try:
            surfaced = sweep(db_path=db_path, ledger_path=Path(args.ledger))
        except Exception as e:  # noqa: BLE001 — a bad cycle must not kill the daemon
            log(f"error: {e!r}")
            surfaced = []
        if surfaced:
            for orphan in surfaced:
                log(
                    f"[ORPHAN] {orphan.subagent_session_id} (child of {orphan.parent_session_id}): "
                    f"{orphan.terminated_reason}, idle {orphan.idle_minutes:.1f}m, "
                    f"result_available={orphan.result_available}"
                )
        else:
            log("no new orphans")
        if args.once:
            return
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    main()
