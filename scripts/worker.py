"""Experiment worker — pop cell from Redis, run 5-session story, save result.

Designed to run in parallel on the same host. Each worker uses Redis BRPOP
for atomic job distribution. Logs to stdout (redirect to file with nohup).

Reliability: retries Redis connections with exponential backoff, recreates
client after long subprocess runs to avoid stale connections.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

import redis

from agentic_dynamics.core.constants import SESSION_TIMEOUT, STORY_SESSIONS

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
QUEUE_KEY = "story_jobs"
STATUS_KEY = "story_status"
WORKER_PREFIX = "worker"

TIMEOUT_PER_CELL = STORY_SESSIONS * SESSION_TIMEOUT + 3000  # 5 sessions × 1200s + margin
BLOCK_TIMEOUT = 10
IDLE_POLLS_BEFORE_EXIT = 12  # 12 × 10s = 2 minutes idle → exit
REDIS_MAX_RETRIES = 10
REDIS_BASE_DELAY = 2.0  # seconds, doubled each retry

from agentic_dynamics.control.live import LivePublisher  # noqa: E402
from agentic_dynamics.runtime.posthoc import trigger_analysis  # noqa: E402


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][{WORKER_PREFIX}] {msg}", flush=True)


def _connect_redis() -> redis.Redis:
    """Connect to Redis with exponential backoff. Never exits — retries forever."""
    delay = REDIS_BASE_DELAY
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
            if attempts < REDIS_MAX_RETRIES:
                log(f"  retrying in {delay:.0f}s")
            time.sleep(delay)
            delay = min(delay * 2, 60.0)


def _safe_hset(r: redis.Redis, key: str, field: str, value: str) -> bool:
    """Set a Redis hash field with retry. Returns True on success."""
    for attempt in range(3):
        try:
            r.hset(key, field, value)
            return True
        except Exception as e:
            log(f"Redis hset error (attempt {attempt+1}/3): {e}")
            time.sleep(2 ** attempt)
    return False


def _result_path_from_stdout(stdout: str) -> Path | None:
    """Extract the saved result path from run_story.py's stdout.

    run_story.py emits a machine-readable JSON line ``{"result_path": "..."}``
    once it has saved the cell, so the worker can enqueue that worktree's
    analysis job without re-scanning the corpus. Falls back to the older
    human-readable ``Results: <path>`` line for backward compatibility.
    Returns ``None`` when no result line is present.
    """
    for line in (stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("result_path"):
                return Path(obj["result_path"])
        if "Results:" in line:
            path = line.split("Results:", 1)[1].strip()
            if path:
                return Path(path)
    return None


def _trigger_analysis(r: redis.Redis, stdout: str, cell_id: str) -> None:
    """Enqueue the just-completed cell's analysis job (best-effort).

    A trigger failure must not fail the cell — ``enqueue_analysis.py`` is the
    backfill safety net — so any error is logged and swallowed.
    """
    try:
        result_path = _result_path_from_stdout(stdout)
        if result_path is None:
            log(f"[{cell_id}] no result path in stdout — skipping analysis trigger")
            return
        if trigger_analysis(r, result_path):
            log(f"[{cell_id}] enqueued analysis job")
        else:
            log(f"[{cell_id}] analysis job not enqueued (missing story_id/worktree)")
    except Exception as e:
        log(f"[{cell_id}] analysis trigger failed (non-fatal): {e}")


def main() -> None:
    log(f"Started (pid={os.getpid()})")

    r = _connect_redis()
    log("Redis connected")

    completed = 0
    failed = 0
    empty_polls = 0

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
                try:
                    remaining = r.llen(QUEUE_KEY)
                except Exception:
                    remaining = 0
                if remaining == 0:
                    log(f"Queue empty after {empty_polls} polls. Exiting.")
                    break
                empty_polls = 0
            continue

        empty_polls = 0
        _, job_json = result

        try:
            cell = json.loads(job_json)
        except json.JSONDecodeError:
            log("Invalid job JSON, skipping")
            continue

        cell_id = cell["cell_id"]
        _safe_hset(r, STATUS_KEY, cell_id, "running")
        publisher = LivePublisher(cell_id)
        publisher.publish_status("running")
        log(f"[{cell_id}] Starting ({completed+failed+1}/30)")

        t0 = time.monotonic()

        try:
            proc = subprocess.run(
                [
                    sys.executable, "scripts/run_story.py",
                    cell["story"],
                    "--model", cell["model"],
                    "--tier", cell["tier"],
                    "--codebase-quality", cell["quality"],
                    "--condition", cell["condition"],
                    "--timeout", str(SESSION_TIMEOUT),
                ],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_PER_CELL,
                env={**os.environ, "FINOPS_CELL_ID": cell_id},
            )

            elapsed = time.monotonic() - t0

            # Reconnect after a potentially long subprocess — the old
            # connection is almost certainly dead after 15+ minutes.
            r = _connect_redis()

            # Save log
            log_dir = Path("experiments/results/stories/logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{cell_id}.log"
            log_file.write_text(proc.stdout)

            ok = proc.returncode == 0 and "ERROR" not in proc.stdout
            if ok:
                # The re-measurement lesson (2026-08-28): a story whose sessions ALL died
                # silently (the Claude CLI auth failure ran 5 sessions of 0.0s each, exit
                # code -2/1, zero tokens, zero cost) still made run_story exit 0, and the
                # old check marked it done — 60 junk zero-cost results polluted the corpus.
                # A cell is done ONLY when the result it wrote is a REAL run: at least one
                # session with real activity (duration > 1s or tokens > 0) or a positive
                # measured cost, or the story's tests actually executed.
                real_run = False
                try:
                    import json as _json
                    for line in proc.stdout.splitlines():
                        if '"result_path"' in line:
                            rp = _json.loads(line).get("result_path")
                            if rp and Path(rp).exists():
                                result = _json.loads(Path(rp).read_text())
                                s = result.get("summary") or {}
                                sessions = result.get("sessions") or []
                                real_run = (
                                    (s.get("total_cost") or 0) > 0
                                    or any(
                                        (x.get("duration_s") or 0) > 1 or (x.get("tokens") or 0) > 0
                                        for x in sessions
                                    )
                                    or s.get("all_successful") is True
                                )
                            break
                except Exception:  # noqa: BLE001 — an unreadable result is NOT a real run
                    real_run = False
                if not real_run:
                    log(f"[{cell_id}] NOT A REAL RUN (silent dead sessions) ret={proc.returncode}")
                    _safe_hset(r, STATUS_KEY, cell_id, "failed")
                    publisher.publish_status("failed")
                    error_log = log_dir / f"{cell_id}.error.log"
                    error_log.write_text(proc.stderr or proc.stdout)
                    failed += 1
                    continue
                log(f"[{cell_id}] OK ({elapsed:.0f}s)")
                _safe_hset(r, STATUS_KEY, cell_id, "done")
                publisher.publish_status("done")
                _trigger_analysis(r, proc.stdout, cell_id)
                completed += 1
            else:
                log(f"[{cell_id}] FAILED ret={proc.returncode} ({elapsed:.0f}s)")
                _safe_hset(r, STATUS_KEY, cell_id, "failed")
                publisher.publish_status("failed")
                error_log = log_dir / f"{cell_id}.error.log"
                error_log.write_text(proc.stderr or proc.stdout)
                failed += 1

        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - t0
            log(f"[{cell_id}] TIMEOUT ({elapsed:.0f}s)")
            r = _connect_redis()
            _safe_hset(r, STATUS_KEY, cell_id, "timeout")
            publisher.publish_status("timeout")
            failed += 1

        except Exception as e:
            log(f"[{cell_id}] EXCEPTION: {e}")
            _safe_hset(r, STATUS_KEY, cell_id, "failed")
            publisher.publish_status("failed")
            failed += 1
            # Reconnect — the exception may have been a Redis error mid-run
            r = _connect_redis()

    log(f"Done: {completed} ok, {failed} failed, {completed+failed} total")


if __name__ == "__main__":
    main()
