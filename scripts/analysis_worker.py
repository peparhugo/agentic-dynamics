"""analysis_worker.py — Pop analysis jobs from Redis, run AST + SonarQube per story.

Each job: story_id, worktree, result_path. Runs ``analyze_story_worktree``
(AST diff + SonarQube) and writes ``analysis_{story_id}.json``. Status tracked
in the ``analysis_status`` hash so the queue is resumable and monitorable.

Usage:
    python3 scripts/analysis_worker.py     # single worker; run N in parallel

Admission (``admission_leases`` p2) — **concurrency only**. This worker spends no model
dollars (AST diff + SonarQube, no LLM call), so it has no provider class, no budget currency
and no admission record: modelling it as a $0 budget lease would mint exactly the meaningless
zero the audit's cost-provenance finding is about. What it very much does consume is an
execution slot — a fleet of analysis workers starves the story workers of CPU just as
effectively as a fleet of paid cells — so when the gate is armed
(``FINOPS_ADMISSION_REQUIRED=1``) each job holds a concurrency lease on the analysis scope for
its duration, and is refused (job re-queued, worker backs off) when the fleet is full.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

import redis

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


import contextlib

# The fleet heartbeat + dead-letter helpers (redis-only) live in scripts/fleet/ (a dir, not a
# package) — add it to sys.path so they import beside the other scripts (fleet_manager.py's
# convention).
sys.path.insert(0, str(Path(__file__).resolve().parent / "fleet"))
import dlq  # noqa: E402       (job dead-letter surface, R4)
import heartbeat  # noqa: E402  (worker:<type>:<id> liveness -> fleet:board, slice 1)

from agentic_dynamics.control.admission import AdmissionDenied, concurrency_admitted
from agentic_dynamics.control.lease_registry import LeaseScope, ScopeKind
from agentic_dynamics.measurement.commit_analysis import (
    agentic_token_dicts,
    analyze_story_worktree,
    compute_deep_metrics,
)
from agentic_dynamics.runtime.story import load_story_result

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
QUEUE_KEY = "analysis_jobs"
STATUS_KEY = "analysis_status"

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = ROOT / "experiments" / "results" / "analysis"
RESULTS_DIR = ROOT / "experiments" / "results" / "stories"

BLOCK_TIMEOUT = 5
IDLE_POLLS_BEFORE_EXIT = 6

#: The concurrency counter analysis jobs are admitted against. A scope of its own — analysis
#: and story execution compete for the same machine but scale differently (Sonar is IO/CPU
#: bound, a story cell is provider-latency bound), so one shared ceiling would tune neither.
ANALYSIS_SCOPE = LeaseScope(ScopeKind.FLEET, "analysis")

#: Lease lifetime for one analysis job. Generous: a SonarQube pass over a large worktree is
#: minutes, and a lease that expires mid-job would release a slot that is still occupied.
ANALYSIS_LEASE_TTL_SECONDS = 3600

#: Seconds to back off after an admission denial before taking the next job (see the story
#: worker's identical rationale: a denial is usually a momentarily full fleet, not a bad job).
DENIAL_BACKOFF_SECONDS = 15.0


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][analysis] {msg}", flush=True)


def _connect_redis() -> redis.Redis:
    delay = 2.0
    attempts = 0
    while True:
        try:
            r = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
                decode_responses=True, socket_connect_timeout=10,
                socket_keepalive=True, health_check_interval=30,
            )
            r.ping()
            attempts += 1
            if attempts > 1:
                log(f"Redis connected (attempt {attempts})")
            return r
        except Exception as e:
            attempts += 1
            log(f"Redis unavailable (attempt {attempts}): {e}")
            time.sleep(delay)
            delay = min(delay * 2, 30.0)


def _safe_hset(r: redis.Redis, key: str, field: str, value: str) -> None:
    with contextlib.suppress(Exception):
        r.hset(key, field, value)


def _resolve_result(job: dict) -> Path:
    """Locate the story result file, container/host-agnostically.

    The job's ``result_path`` may be a HOST path (jobs enqueued by host-side
    producers like ``enqueue_analysis.py``) that does not resolve inside the
    container's mount namespace. Fall back to scanning the worker's own
    RESULTS_DIR for ``*_<story_id>.json`` — the same pattern the enqueue scan
    uses — so a job never fails on a path-namespace mismatch.
    """
    path = Path(job.get("result_path", ""))
    if path.exists():
        return path
    story_id = job.get("story_id", "")
    matches = sorted(RESULTS_DIR.glob(f"*_{story_id}.json"))
    if matches:
        return matches[0]
    return path


def _trigger_reviews(r: redis.Redis, story_id: str, story_name: str, worktree: Path) -> None:
    """Signal the review-unit after analysis completes (best-effort).

    The review flow is AUTOMATIC since 2026-08-31: a completed analysis LPUSHes the
    review trigger directly onto ``fleet:review_trigger`` (db1 / 6380); the review-unit
    daemon (exactly one runner) consumes it and runs ``review_all --only-missing``. The
    legacy ``review_jobs`` queue is retired from the display and never consumed — a
    trigger failure must not fail the analysis, so any error is logged and swallowed.
    """
    try:
        payload = json.dumps({
            "action": "review",
            "story_id": story_id,
            "story_name": story_name,
            "ts": time.time(),
        })
        r.lpush("fleet:review_trigger", payload)
        log(f"[{story_id}] signalled review-unit")
    except Exception as e:
        log(f"[{story_id}] review trigger failed (non-fatal): {e}")


def main() -> None:
    r = _connect_redis()
    log("Started (queue: " + QUEUE_KEY + ")")

    empty_polls = 0
    completed = 0
    failed = 0

    # Worker liveness (slice 1): a daemon heartbeat thread beats every 10s so the fleet
    # manager's read-only watcher can surface this worker on the board. The thread owns its
    # own Redis connection (the main loop reconnects after long SonarQube runs).
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    heartbeat.HeartbeatThread(
        "analysis", worker_id, jobs_counter=lambda: completed + failed,
    ).start()
    log(f"heartbeat: worker:analysis:{worker_id}")

    while True:
        try:
            result = r.brpop(QUEUE_KEY, timeout=BLOCK_TIMEOUT)
        except Exception as e:
            log(f"Redis brpop error: {e}, reconnecting...")
            time.sleep(10)
            r = _connect_redis()
            continue

        if result is None:
            empty_polls += 1
            if empty_polls >= IDLE_POLLS_BEFORE_EXIT:
                log(f"Queue empty after {empty_polls} polls. Exiting.")
                break
            continue

        empty_polls = 0
        _, job_json = result
        try:
            job = json.loads(job_json)
        except json.JSONDecodeError:
            log("Invalid job JSON, skipping")
            continue

        story_id = job["story_id"]

        # LEASE BEFORE WORK. Concurrency only (no dollars are spent here). A refusal re-queues
        # the job and backs off — the slot will free up as other analyses finish.
        try:
            slot = contextlib.ExitStack()
            slot.enter_context(
                concurrency_admitted(
                    ANALYSIS_SCOPE,
                    1,
                    run_id=f"analysis:{story_id}",
                    ttl_seconds=ANALYSIS_LEASE_TTL_SECONDS,
                    metadata={"source": "analysis_worker", "story_id": story_id},
                )
            )
        except AdmissionDenied as e:
            log(f"[{story_id}] ADMISSION DENIED (analysis slots full): {e}")
            with contextlib.suppress(Exception):
                r.lpush(QUEUE_KEY, job_json)
            time.sleep(DENIAL_BACKOFF_SECONDS)
            continue

        _safe_hset(r, STATUS_KEY, story_id, "running")
        log(f"[{story_id}] Starting")

        t0 = time.monotonic()
        try:
            worktree = Path(job.get("worktree", ""))
            if not worktree.exists():
                raise RuntimeError(f"worktree missing: {worktree}")

            story_result = load_story_result(_resolve_result(job))
            analysis = analyze_story_worktree(worktree, run_sonar=True)
            analysis.story_name = story_result.story_name
            analysis.story_id = story_result.story_id

            analysis_dict = analysis.to_dict()
            analysis_dict["deep"] = compute_deep_metrics(
                worktree,
                story_name=story_result.story_name,
                model=story_result.model,
                test_passed=story_result.all_successful,
                total_cost_usd=story_result.total_cost,
                session_token_data=agentic_token_dicts(story_result.sessions),
            )

            out_path = ANALYSIS_DIR / f"analysis_{story_id}.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(analysis_dict, indent=2))

            _safe_hset(r, STATUS_KEY, story_id, "done")
            completed += 1
            log(f"[{story_id}] OK ({time.monotonic() - t0:.0f}s)")
            _trigger_reviews(r, story_id, story_result.story_name, worktree)
        except Exception as e:
            _safe_hset(r, STATUS_KEY, story_id, "failed")
            failed += 1
            log(f"[{story_id}] FAILED ({time.monotonic() - t0:.0f}s): {e}")
            # R4 — a terminal failure (notably the "worktree missing" class) is recorded to
            # the job-queue dead-letter surface so it no longer silently sits in the status
            # hash as a bare ``failed`` row.
            with contextlib.suppress(Exception):
                dlq.record_dead(r, QUEUE_KEY, job, str(e))
            err_log = ANALYSIS_DIR / f"analysis_{story_id}.error.txt"
            with contextlib.suppress(Exception):
                err_log.write_text(str(e))
        finally:
            # Release the slot the moment the job settles (the TTL is the backstop).
            slot.close()

        # Reconnect after a long SonarQube run — the connection is likely stale.
        try:
            r.ping()
        except Exception:
            r = _connect_redis()

    log(f"Done: {completed} ok, {failed} failed, {completed + failed} total")


if __name__ == "__main__":
    main()
