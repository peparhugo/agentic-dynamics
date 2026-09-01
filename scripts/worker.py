"""Experiment worker — pop cell from Redis, run 5-session story, save result.

Designed to run in parallel on the same host. Each worker uses Redis BRPOP
for atomic job distribution. Logs to stdout (redirect to file with nohup).

Reliability: retries Redis connections with exponential backoff, recreates
client after long subprocess runs to avoid stale connections.

Admission (``admission_leases`` p2) — lease before spawn, release after the cell settles.
When the gate is armed (``FINOPS_ADMISSION_REQUIRED=1``) no ``run_story.py`` subprocess is
spawned until this worker holds the cell's leases, and the lease context is stamped into the
subprocess's environment so the adapter's bypass guard downstream sees an admitted run:

* **Budget** — *reused, not re-reserved*, when the job carries the lease block
  ``scripts/enqueue.py`` stamped on it at fill time. Reserving again would double-count the
  same cell's dollars against the same cap. Only a job with no lease block (an older queue
  entry, or a hand-pushed job) takes a fresh budget lease here.
* **Concurrency** — always taken here, never at fill time: queueing occupies no execution
  slot, starting a cell does. Two scopes, both required: the fleet-wide slot counter and the
  per-provider one, so one provider's cells cannot consume the whole fleet.

A denial does NOT dead-letter the cell. The job is pushed back onto the queue and the worker
backs off, because the overwhelmingly common denial is transient (the fleet is momentarily
full) and dead-lettering a perfectly good cell for it would be destructive. A worker that is
denied :data:`MAX_CONSECUTIVE_DENIALS` times in a row exits instead of spinning — that pattern
means a *cap*, not a queue, and a caps problem needs an operator, not a retry loop.

With the gate disarmed this file behaves exactly as it did before.
"""

import contextlib
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

import redis

# The fleet heartbeat + dead-letter helpers are dependency-light (redis only) and live in
# scripts/fleet/ (a dir, not a package). Add that dir to sys.path so they import beside the
# other scripts — the same convention fleet_manager.py uses.
sys.path.insert(0, str(Path(__file__).resolve().parent / "fleet"))
import dlq  # noqa: E402       (job dead-letter surface, R4)
import heartbeat  # noqa: E402  (worker:<type>:<id> liveness -> fleet:board, slice 1)

from agentic_dynamics.control.admission import (
    AdmissionDenied,
    AdmissionRequest,
    admitted,
    default_controller,
)
from agentic_dynamics.control.lease_registry import (
    AdmissionError,
    LeaseRegistry,
    LeaseScope,
    ScopeKind,
)
from agentic_dynamics.core.admission_context import (
    LeaseContext,
    admission_required,
    bind_context,
    validate_lease_fields,
)
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

#: Seconds to wait after an admission denial before taking the next job. Long enough that a
#: full fleet has a realistic chance of freeing a slot, short enough that a worker is not
#: parked for a whole cell's duration on one transient refusal.
DENIAL_BACKOFF_SECONDS = 30.0

#: Consecutive denials before the worker gives up and exits. A transient "fleet is full"
#: clears within a few of these; ten in a row means the cap itself is the constraint, and a
#: worker that keeps re-queueing against a hard cap is just a busy loop with extra steps.
MAX_CONSECUTIVE_DENIALS = 10

#: The concurrency lease's lifetime. Slightly longer than the per-cell timeout so a cell that
#: runs to the very edge of its budget still holds its slot until the subprocess is reaped —
#: a lease that expired mid-cell would let a second worker start against a full fleet, and
#: would (correctly, per phase 4) mark this cell's output as quarantine-worthy.
CELL_LEASE_TTL_SECONDS = TIMEOUT_PER_CELL + 600

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


def _safe_record_dead(r: redis.Redis, queue_key: str, job: object, reason: str) -> None:
    """Record a terminal failure to the queue's dead-letter list (best-effort, R4).

    A DLQ write must never take down the worker it is reporting on, so any Redis
    error is logged and swallowed — the status hash still carries the ``failed`` row.
    """
    for attempt in range(2):
        try:
            dlq.record_dead(r, queue_key, job, reason)
            return
        except Exception as e:  # noqa: BLE001 — best-effort DLQ
            log(f"DLQ record error (attempt {attempt+1}/2): {e}")
            time.sleep(1)


def _cell_concurrency_scopes(model: str) -> tuple[LeaseScope, ...]:
    """The slot counters a running cell must fit inside: fleet-wide AND per-provider.

    Both are required (the audit's "refuse if either reservation fails" generalised over
    scopes). The pairing is what stops one provider's cells from consuming the whole fleet
    while still bounding total width — a per-provider cap alone would let three providers
    together exceed the machine, and a fleet cap alone would let DeepSeek starve Anthropic.

    Size the fleet cap with ``control.lease_registry.recommended_concurrency()``: the measured
    β_tokens = 0.80 puts fleet throughput at N^0.20, so the knee is around 6 workers. The
    coordination tax is paid in throughput, not dollars.
    """
    fleet = os.environ.get("FINOPS_FLEET_SCOPE", "").strip() or "default"
    provider = model.split("/", 1)[0] if "/" in model else model
    return (
        LeaseScope(ScopeKind.FLEET, fleet),
        LeaseScope(ScopeKind.PROVIDER, provider),
    )


def _queued_budget_context(cell: dict) -> LeaseContext | None:
    """The budget lease ``enqueue.py`` stamped on this job, or ``None`` if it carries none.

    A *malformed* block is not ``None``: it raises :class:`AdmissionDenied`. A job that looks
    budgeted but is not is precisely the state the gate exists to catch — silently re-reserving
    it would paper over a producer bug, and silently running it would be the unbudgeted run.
    """
    errors = validate_lease_fields(cell, required=False)
    if errors:
        raise AdmissionDenied(
            f"queued job {cell.get('cell_id')!r} carries an invalid lease block: "
            + "; ".join(errors)
        )
    if "budget_lease_id" not in cell:
        return None
    return LeaseContext.from_request_fields(
        cell,
        run_id=str(cell.get("admission_run_id") or cell.get("cell_id") or ""),
        model=str(cell.get("model") or ""),
    )


@contextlib.contextmanager
def cell_admission(cell: dict, *, controller=None, registry=None):
    """Hold this cell's leases for the duration of the block; yield the subprocess env block.

    Yields ``{}`` when the gate is disarmed (nothing reserved, nothing to stamp), otherwise the
    ``FINOPS_ADMISSION_*`` env dict to merge into the ``run_story.py`` launch envelope — that
    stamp is what makes the child's adapter-level bypass guard see an admitted run.

    Two paths, because the budget may already be claimed:

    * **Job carries a budget lease** (the normal path — ``enqueue.py`` reserved it at fill
      time): reuse it and take only the concurrency leases. Re-reserving would double-count
      the same cell's dollars against the same cap.
    * **Job carries none** (an older queue entry, or a hand-pushed job): a full admission —
      budget + concurrency — through the controller.

    Releases on exit in both paths, including on an exception. A release failure is swallowed:
    the lease TTL is the guarantee, and masking the body's exception with a bookkeeping error
    is how a diagnosis gets lost.
    """
    if not admission_required():
        yield {}
        return

    model = str(cell.get("model") or "")
    scopes = _cell_concurrency_scopes(model)
    queued = _queued_budget_context(cell)

    if queued is None:
        # No queue-time budget: admit the whole thing here.
        request = AdmissionRequest(
            run_id=str(cell.get("cell_id") or ""),
            model=model,
            worktree_identity=str(cell.get("cell_id") or ""),
            result_namespace=f"stories/{cell.get('cell_id')}",
            concurrency_scopes=scopes,
            ttl_seconds=CELL_LEASE_TTL_SECONDS,
            metadata={"source": "worker", "story": cell.get("story", "")},
        )
        with admitted(request, controller=controller or default_controller()) as admission:
            yield admission.env()
        return

    # Budget already reserved at fill time — take only the slots.
    reg = registry or LeaseRegistry.from_env()
    leases = []
    try:
        for scope in scopes:
            leases.append(
                reg.reserve_concurrency(
                    scope,
                    1,
                    run_id=queued.run_id,
                    ttl_seconds=CELL_LEASE_TTL_SECONDS,
                    metadata={"source": "worker", "cell_id": cell.get("cell_id", "")},
                )
            )
    except AdmissionError as exc:
        # All-or-nothing: unwind the slots already taken. The BUDGET lease is deliberately NOT
        # released — it belongs to the queued job, which is about to be pushed back onto the
        # queue and must still be budgeted when another worker picks it up.
        for lease in leases:
            with contextlib.suppress(AdmissionError):
                reg.release(lease.lease_id)
        raise AdmissionDenied(
            f"concurrency denied for cell {cell.get('cell_id')!r}: {exc}", cause=exc
        ) from exc

    context = replace(
        queued, concurrency_lease_ids=tuple(lease.lease_id for lease in leases)
    )
    try:
        with bind_context(context):
            yield context.to_env()
    finally:
        for lease in leases:
            with contextlib.suppress(AdmissionError):
                reg.release(lease.lease_id)


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
    #: Consecutive admission refusals. Reset by any successful admission; at
    #: MAX_CONSECUTIVE_DENIALS the worker exits (see the denial handler below).
    consecutive_denials = 0

    # Worker liveness (slice 1): a daemon heartbeat thread beats every 10s so the fleet
    # manager's read-only watcher can surface this worker on the board. The thread owns its
    # own Redis connection (the main loop reconnects after long subprocess runs).
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    heartbeat.HeartbeatThread(
        "story", worker_id, jobs_counter=lambda: completed + failed,
    ).start()
    log(f"heartbeat: worker:story:{worker_id}")

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
        # The spend gate (admission_leases p2). An ExitStack so the leases are released by the
        # same ``finally`` on every path — success, failure, timeout, or refusal.
        admission_gate = contextlib.ExitStack()

        # P0-3 (control-plane stabilization): a FRESH CLI-state namespace per accepted job —
        # <state_root>/jobs/<cell_id>/, with XDG_DATA_HOME/XDG_CONFIG_HOME/XDG_CACHE_HOME
        # pointed into it. The pool's mount is the state ROOT (/state, rw); the job namespace
        # is minted HERE so two concurrent replicas (or two jobs on one replica) can never
        # read/write the same opencode session DB, SQLite/WAL, or compaction state.
        state_root = Path(os.environ.get("FINOPS_OPENCODE_STATE_ROOT", "/state"))
        job_state = state_root / "jobs" / cell_id
        job_state.mkdir(parents=True, exist_ok=True)
        state_env = {
            "XDG_DATA_HOME": str(job_state / "data"),
            "XDG_CONFIG_HOME": str(job_state / "config"),
            "XDG_CACHE_HOME": str(job_state / "cache"),
            "FINOPS_OPENCODE_STATE_DIR": str(job_state / "data"),
        }

        try:
            # LEASE BEFORE SPAWN. A refusal raises here, before subprocess.run is reached, so
            # "denied" provably means no run_story.py process ever existed. The returned env
            # block is merged into the child's environment: that is how the admission crosses
            # the process boundary to the adapter's bypass guard.
            admission_env = admission_gate.enter_context(cell_admission(cell))
            consecutive_denials = 0
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
                env={**os.environ, "FINOPS_CELL_ID": cell_id, **admission_env, **state_env},
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
                                        ((x.get("tokens") or {}).get("out") or 0) > 0
                                        or ((x.get("tokens") or {}).get("in") or 0) > 0
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
                    _safe_record_dead(r, QUEUE_KEY, cell, "silent dead sessions (not a real run)")
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
                _safe_record_dead(r, QUEUE_KEY, cell, f"run_story returned {proc.returncode}")
                error_log = log_dir / f"{cell_id}.error.log"
                error_log.write_text(proc.stderr or proc.stdout)
                failed += 1

        except AdmissionDenied as e:
            # REFUSED — nothing was spawned and nothing was spent. The cell is NOT dead-lettered:
            # the usual cause is a momentarily full fleet, so the job goes back on the queue and
            # this worker backs off. Its queue-time budget lease is untouched and still valid,
            # so whichever worker picks it up next is still budgeted.
            consecutive_denials += 1
            log(f"[{cell_id}] ADMISSION DENIED ({consecutive_denials}/"
                f"{MAX_CONSECUTIVE_DENIALS}): {e}")
            _safe_hset(r, STATUS_KEY, cell_id, "queued")
            publisher.publish_status("queued")
            try:
                # LPUSH against a BRPOP consumer puts it at the BACK of the queue, so the other
                # jobs get a turn before this one is retried.
                r.lpush(QUEUE_KEY, job_json)
            except Exception as exc:  # noqa: BLE001 — a lost re-queue must not kill the worker
                log(f"[{cell_id}] could not re-queue after denial: {exc}")
                _safe_record_dead(r, QUEUE_KEY, cell, f"admission denied + re-queue failed: {e}")
            if consecutive_denials >= MAX_CONSECUTIVE_DENIALS:
                # A cap, not a queue. Exit rather than spin — this needs an operator.
                log(f"{MAX_CONSECUTIVE_DENIALS} consecutive admission denials — the constraint "
                    f"is a cap, not contention. Exiting for the operator.")
                # No explicit close needed: ``break`` still runs the ``finally`` below.
                break
            time.sleep(DENIAL_BACKOFF_SECONDS)
            continue

        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - t0
            log(f"[{cell_id}] TIMEOUT ({elapsed:.0f}s)")
            r = _connect_redis()
            _safe_hset(r, STATUS_KEY, cell_id, "timeout")
            publisher.publish_status("timeout")
            _safe_record_dead(r, QUEUE_KEY, cell, "timeout")
            failed += 1

        except Exception as e:
            log(f"[{cell_id}] EXCEPTION: {e}")
            _safe_hset(r, STATUS_KEY, cell_id, "failed")
            publisher.publish_status("failed")
            _safe_record_dead(r, QUEUE_KEY, cell, f"exception: {e}")
            failed += 1
            # Reconnect — the exception may have been a Redis error mid-run
            r = _connect_redis()

        finally:
            # Release the cell's concurrency lease the moment the cell settles — success,
            # failure, timeout, or refusal. (Release is the fast path; the lease TTL is the
            # guarantee if this process dies before reaching it.)
            admission_gate.close()

    log(f"Done: {completed} ok, {failed} failed, {completed+failed} total")


if __name__ == "__main__":
    main()
