"""Lease expiry watchdog — FLAG-ONLY, never steers (admission_leases phase 4).

Sweeps the framework Redis lease registry (6380 db1 — never the story-agent sandbox on 6379) for
expired leases and turns each one into an advisory record:

* an expired **concurrency** lease → a supervisor flag (a worker outlived its execution slot);
* an expired **budget** lease → a supervisor flag *and* a quarantine entry against the run's
  worktree and results namespace (work that outlived its spend reservation produced output the
  system never admitted — the audit's "contaminated", item 8).

No steering. The sweep never kills a process, never retries, never resumes, never reschedules.
It extends the supervisor's observe-only rail (``docs/architecture/current/supervisor_design.md``)
and the quarantine marks it writes are consumed by the *permanence gate* and the *analyze chain*
(``scripts/analyze_worktrees.py``, ``scripts/inventory.py``, ``scripts/system_snapshot.py``),
which decide what to do about them. The controller remains the only thing that makes anything
permanent.

Cadence: a periodic pass (default every 5 min, ``FINOPS_LEASE_WATCHDOG_INTERVAL``). Because each
pass sweeps every scope reachable from the registry index, an expired lease is flagged within one
interval regardless of when it expired — that bound is the work order's verification target.

Rules live in ``agentic_dynamics/control/lease_watchdog.py``; the contamination ledger in
``agentic_dynamics/control/quarantine.py``. This file is the CLI shell around them.

    agentic-dynamics supervise leases --once
    agentic-dynamics supervise leases --once --json
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


from agentic_dynamics.control.lease_registry import (  # noqa: E402
    AdmissionError,
    LeaseRegistry,
)
from agentic_dynamics.control.lease_watchdog import (  # noqa: E402
    WATCHDOG_INTERVAL_S,
    WatchdogResult,
    format_report,
    report_json,
    sweep_once,
)
from agentic_dynamics.control.quarantine import (  # noqa: E402
    QUARANTINE_LEDGER_PATH,
    QuarantineRegistry,
)

#: The supervisor's durable flag ledger — lease flags land in the SAME file as session flags so
#: an operator reads one board, not two (``scripts/supervise.py:FLAGS_FILE``).
FLAGS_FILE = ROOT / "experiments" / "results" / "supervisor" / "flags.jsonl"
INTERVAL = int(os.environ.get("FINOPS_LEASE_WATCHDOG_INTERVAL", str(WATCHDOG_INTERVAL_S)))


def _redis():
    """Framework Redis client (6380/db1) for the flags + quarantine hot paths.

    Returns ``None`` rather than raising when Redis is unreachable: the durable JSONL writes are
    the authority and remain fully functional, so a downed hot path degrades the *board*, never
    the record. The lease registry itself is a different matter — see :func:`_registry`.
    """
    try:
        import redis

        client = redis.Redis(
            host=os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1"),
            port=int(os.environ.get("FINOPS_REDIS_PORT", "6380")),
            db=int(os.environ.get("FINOPS_REDIS_DB", "1")),
            decode_responses=True,
            socket_connect_timeout=2,
        )
        client.ping()
        return client
    except Exception as exc:  # noqa: BLE001 — degrade to durable-only, loudly
        log(f"framework Redis unavailable ({exc!r}); durable writes only")
        return None


def _registry() -> LeaseRegistry:
    """The lease registry to sweep. Unlike the hot path this one is mandatory.

    The registry IS the state being observed — with no registry there are no leases to sweep, and
    an "everything is fine" pass over a registry we could not read would be a fabricated clean
    bill of health. Fail loudly instead (``LeaseRegistry.from_env`` also refuses the story-agent
    sandbox at construction time).
    """
    return LeaseRegistry.from_env()


def log(msg: str) -> None:
    """One prefixed line to stdout — the operator-visible trace of an advisory pass."""
    print(f"[lease-watchdog] {msg}", flush=True)


def sweep(*, ledger_path: Path, flags_path: Path, redis_client=None) -> WatchdogResult:
    """Run one pass against the live registry, writing flags and quarantine entries."""
    return sweep_once(
        _registry(),
        QuarantineRegistry(ledger_path=ledger_path, redis_client=redis_client),
        redis_client=redis_client,
        flags_path=flags_path,
    )


def main() -> None:
    """Parse args and run the watchdog, once or on a cadence."""
    ap = argparse.ArgumentParser(
        description="Lease expiry watchdog — sweep expired admission leases, flag them, and "
                    "quarantine the output of work that outlived its budget lease. "
                    "FLAG-ONLY, never steers."
    )
    ap.add_argument("--once", action="store_true", help="run one pass and exit")
    ap.add_argument(
        "--quarantine-ledger",
        default=str(QUARANTINE_LEDGER_PATH),
        help="durable quarantine JSONL path (default: experiments/results/quarantine/)",
    )
    ap.add_argument(
        "--flags",
        default=str(FLAGS_FILE),
        help="durable supervisor flags JSONL path (shared with supervise.py)",
    )
    ap.add_argument(
        "--interval",
        type=int,
        default=INTERVAL,
        help="pass cadence in seconds (default: FINOPS_LEASE_WATCHDOG_INTERVAL, else 300)",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="print the machine-readable pass report instead of the human summary",
    )
    args = ap.parse_args()

    ledger_path = Path(args.quarantine_ledger)
    flags_path = Path(args.flags)
    redis_client = _redis()
    log(
        f"watching the lease registry; cadence {args.interval}s; "
        f"quarantine -> {ledger_path}; flags -> {flags_path}"
    )

    while True:
        try:
            result = sweep(
                ledger_path=ledger_path, flags_path=flags_path, redis_client=redis_client
            )
        except AdmissionError as exc:
            # The registry is the observed state; losing it is a loud, retried condition, not a
            # clean pass. A daemon must not die on it, and --once must not exit 0 on it.
            log(f"registry unavailable, nothing could be observed: {exc}")
            if args.once:
                raise SystemExit(1) from exc
            time.sleep(max(1, args.interval))
            continue
        except Exception as exc:  # noqa: BLE001 — a bad cycle must not kill the daemon
            log(f"error: {exc!r}")
            if args.once:
                raise SystemExit(1) from exc
            time.sleep(max(1, args.interval))
            continue

        print(report_json(result) if args.json else format_report(result), flush=True)
        if args.once:
            return
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    main()
