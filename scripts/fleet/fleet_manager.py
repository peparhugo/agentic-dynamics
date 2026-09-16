#!/usr/bin/env python3
"""The fleet manager — the supervisor-tier daemon (proposal §2/D-14, §7 slice 1).

The supervisor is the fleet manager, **not an execution container**. It holds NO docker
socket (D-3/D-14): the pools are static (compose ``--scale`` counts), routine restarts are
docker's own ``restart: on-failure`` policies, and a fleet-level resize/drain is the
supervisor **commanding the orchestrator** over Redis ``fleet:commands``
(db1 / 6380) — the orchestrator's spawn-wrapper validates the request and emits it to the
host-side launch broker (the docker socket's only home; fb2_broker_hostside) before any
docker call happens.

This daemon does three things, all **read-only** with respect to spawning:

    watch     — the read-only watcher: queue depths + worker heartbeats + DLQ counts ->
                the board (a Redis JSON key + a per-line log), on a fixed cadence. It never
                spawns anything.
    status    — one-shot dump of the board (machine-readable JSON with ``--json``).
    resize / drain / restart — LPUSH a bounded command onto ``fleet:commands`` for the
                orchestrator to validate and execute (the supervisor's "hands", D-14).
    submit    — LPUSH a spec/goal/model/workdir submit command onto ``fleet:commands`` and
                record a "launching" job on the board; the orchestrator's spawn-wrapper
                (``scripts/fleet/spawn_wrapper.py:validate_submit_request``) is what actually
                validates it BEFORE any container exists. This command never blocks or refuses
                on a concurrent submit — there is no orchestrator lock (the isolation the
                docker layer buys is a per-request property, not a scheduling one).

A submitted job's board record then moves through ``launching -> running ->
completed/failed`` as the spawn-wrapper's BRPOP consumer observes each transition
(:func:`record_job_status`, p2_launch_handler) — a refusal before the socket call and a
nonzero compose exit both land on "failed" (plus a ``fleet_jobs`` dead-letter entry,
``scripts/fleet/dlq.py``), and a successful run's "completed" record carries the run's ledger
pointer (the per-phase JSON ``run_workflow.py`` writes under
``experiments/results/workflows/<spec>/``).

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

import broker_contract  # noqa: E402  (scripts/fleet/ is this module's dir)
import dlq  # noqa: E402  (scripts/fleet/ is this module's dir)
import heartbeat  # noqa: E402
import redis  # noqa: E402

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))

BOARD_KEY = "fleet:board"
COMMANDS_KEY = "fleet:commands"
#: The submit job board — one hash field per job id, holding the latest lifecycle record
#: (``{job_id, spec, model, status, ts}``). Separate from BOARD_KEY (the queue/worker snapshot)
#: because a job's lifecycle is written by whoever observes each transition (this module writes
#: "launching" at submit time; the orchestrator/downstream tooling would write "running"/
#: "completed"/"failed" as those are observed), not recomputed wholesale on each watch cycle.
JOBS_KEY = "fleet:jobs"
#: The caller-stable request index (2026-09-16 delivery simplification, Unit 2): one hash field
#: per ``request_key`` -> ``job_id``. A submit that names a request key claims it atomically
#: with its LPUSH; a RETRY with the same key reconciles to the existing job instead of minting
#: a second one. The key is explicitly caller-supplied — this is NOT content deduplication
#: (identical goal text may be an intentional new run); a caller that wants a new run mints a
#: new key, a caller retrying an ambiguous submit reuses its retained key.
REQUESTS_KEY = "fleet:requests"
#: The docs-drift row (``automatic_docs_sync`` p2). Written by
#: ``scripts/docs_drift_watchdog.py`` on its own cadence and merged into the board snapshot
#: here, for exactly the reason JOBS_KEY is separate: this watcher rebuilds BOARD_KEY
#: wholesale every cycle, so state owned by another observer must live in its own key or it
#: would survive at most one tick.
DOCS_DRIFT_KEY = "fleet:docs_drift"
DEFAULT_INTERVAL = 15.0  # seconds between board refreshes

# The queues the watcher surfaces (mirrors dlq.QUEUE_KEYS).
STATUS_KEYS = {
    "story_jobs": "story_status",
    "story_jobs_batch": "story_status",  # the deferred batch lane (rule 6); same tracker
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
                socket_timeout=broker_contract.FLEET_REDIS_SOCKET_TIMEOUT,
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


def _job_records(client: redis.Redis) -> list[dict]:
    """Read every job's latest lifecycle record from ``fleet:jobs`` (newest first).

    A malformed field (should never happen — only this module and the orchestrator write
    here) is skipped rather than raised: the board must stay renderable even if one job's
    record is corrupt, the same "pure read, never raises" contract ``build_board`` already
    holds for queues/workers/DLQ.
    """
    jobs: list[dict] = []
    try:
        raw_values = client.hvals(JOBS_KEY)
    except Exception:  # noqa: BLE001 — the board must survive a Redis blip
        return jobs
    for raw in raw_values:
        try:
            jobs.append(json.loads(raw))
        except (TypeError, ValueError):
            continue
    jobs.sort(key=lambda j: j.get("ts", 0), reverse=True)
    return jobs


def _docs_drift_row(client: redis.Redis) -> dict:
    """Read the docs-drift row from ``fleet:docs_drift`` (empty dict when absent or malformed).

    The docs-drift watchdog (``scripts/docs_drift_watchdog.py``) publishes one row per scan:
    ``{ts, state, health, drift, per_axis, ...}`` — "are the docs current?" as a live number on
    the supervisor tier, beside the queue depths and worker heartbeats.

    Absent is the normal state on a host where the timer is not installed, and it is reported as
    ``{}`` rather than a fabricated "clean" row: the board must never imply a scan happened when
    none did. Same "pure read, never raises" contract ``build_board`` holds for queues, workers,
    the DLQ, and jobs — a Redis blip or a corrupt row costs this section, not the board.
    """
    try:
        raw = client.get(DOCS_DRIFT_KEY)
    except Exception:  # noqa: BLE001 — the board must survive a Redis blip
        return {}
    if not raw:
        return {}
    try:
        row = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return row if isinstance(row, dict) else {}


def _job_launch_record(command: dict) -> dict:
    """The board's "launching" record for a submit command (the request key rides along)."""
    record = {
        "job_id": command["job_id"],
        "spec": command["spec"],
        "model": command["model"],
        "status": "launching",
        "ts": command["ts"],
    }
    if command.get("request_key"):
        record["request_key"] = command["request_key"]
    return record


def record_job_launch(client: redis.Redis, command: dict) -> dict:
    """Write a submitted job's "launching" record onto the board (``fleet:jobs``).

    This is the ONLY lifecycle transition the fleet-manager itself writes — it observes its
    own LPUSH, nothing more. Later transitions (running/completed/failed) are the
    orchestrator's / downstream tooling's to write as they observe them; this function does
    not wait for or assume any of that (submit is fire-and-forget onto the queue, matching
    resize/drain/restart's own "LPUSH and return" shape).
    """
    record = _job_launch_record(command)
    client.hset(JOBS_KEY, mapping={command["job_id"]: json.dumps(record)})
    return record


class RequestKeyConflictError(ValueError):
    """A caller-stable request key was reused for a DIFFERENT submission.

    A request key identifies exactly ONE submission; reconciling a keyed retry to a job for a
    different spec would silently drop the new request, so the conflict refuses loudly.
    """


#: The request-keyed submit, ATOMICALLY (one server-side script): the request->job
#: association, the command LPUSH, and the board record commit together — a key is either
#: fully claimed-and-queued, or not claimed at all. A concurrent same-key submitter observes
#: the winner's job and reconciles; a retry can never double-queue. Returns
#: ``{job_id, record_json}``: the NEW job on the claim path, the EXISTING job's record on the
#: reconcile path (empty string when the record is missing/unreadable).
_SUBMIT_LUA = """
local existing = redis.call('HGET', KEYS[1], ARGV[1])
if existing then
  return {existing, redis.call('HGET', KEYS[3], existing) or ''}
end
redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
redis.call('LPUSH', KEYS[2], ARGV[3])
redis.call('HSET', KEYS[3], ARGV[2], ARGV[4])
return {ARGV[2], ARGV[4]}
"""


def record_job_status(client: redis.Redis, job_id: str, status: str, **fields) -> dict:
    """Update a submitted job's board record with an OBSERVED lifecycle transition.

    Reads back whatever record already exists (written by :func:`record_job_launch` or a
    previous call to this function) so a later transition never drops the job's identifying
    fields (``spec``/``model``) — only ``status``/``ts`` and whatever ``fields`` the caller
    passes (e.g. ``returncode``, ``ledger``, ``error``) change. This is the write side of
    "launching -> running -> completed/failed" (p2_launch_handler): the spawn-wrapper's BRPOP
    consumer calls it as it observes each transition (the orchestrator's own phase-by-phase
    publications go over ``control.live``, a separate unscoped telemetry channel — this hash is
    the coarser per-JOB lifecycle the board renders, not a mirror of every phase event). This
    module's own :func:`_send_submit_command` never calls it — that stays
    :func:`record_job_launch`'s one-shot "launching" write.
    """
    raw = client.hget(JOBS_KEY, job_id)
    try:
        record = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        record = {}
    record.setdefault("job_id", job_id)
    record["status"] = status
    record["ts"] = time.time()
    record.update(fields)
    client.hset(JOBS_KEY, mapping={job_id: json.dumps(record)})
    return record


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
        "jobs": _job_records(client),
        "docs_drift": _docs_drift_row(client),
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


def _send_submit_command(client: redis.Redis, *, spec: str, goal: str, model: str,
                         workdir: str, image: str | None = None,
                         spec_sha256: str | None = None,
                         resume: bool = False,
                         parent_run_id: str | None = None,
                         admission: dict | None = None,
                         execution: dict | None = None,
                         aio: dict | None = None,
                         request_key: str | None = None) -> dict:
    """LPUSH a submit command onto ``fleet:commands`` and record its "launching" board entry.

    The fleet-manager mints the ``job_id`` (the board's join key) but does NOT validate the
    request — that stays the orchestrator's job (``spawn_wrapper.validate_submit_request``),
    exactly as resize/drain/restart's validation stays with the orchestrator, never the
    supervisor. Nothing here refuses a concurrent submit for the same or another spec; there is
    no lock (the design's "ZERO refusing of concurrency" rule) — every submit is independently
    LPUSHed and independently validated when it is popped.

    ``request_key`` (2026-09-16, Unit 2) is the caller-stable retry identity: when supplied,
    the association + LPUSH + board record commit ATOMICALLY (one server-side script). A
    retry with the SAME key returns the EXISTING job (``reconciled: true``) and queues
    nothing; reusing a key for a different spec refuses (:class:`RequestKeyConflictError`). No
    key = the caller wants an independent submission (identical goal text may be an
    intentional new run — this is not content deduplication).

    ``image`` (p3_base_image_caching) is the optional per-job image the submitted spec's phase
    cells should run — the fleet-manager passes it through UNCHECKED, same as every other
    field; it is ``validate_submit_request``'s step 8 (``fleet/job-<name>`` only) that decides
    whether it is actually honored.

    The extended identity fields (AIO remediation 2026-09-14) pass through the same
    UNCHECKED way — ``spec_sha256`` (source/spec identity), ``resume``/``parent_run_id``
    (continuation identity), ``admission`` (the applicable admission settings), and
    ``execution`` (the per-run execution settings: backend, thinking effort/budget, output
    limit, phase timeout, no_commit) — because the orchestrator + broker re-validate them at
    the two later gates. The manager's job is that they SURVIVE the hop, not that they are
    already proven. A caller that does not supply ``execution`` receives the orchestrator's
    own defaults — never a silently different behavior.
    """
    job_id = uuid.uuid4().hex[:12]
    command = {
        "action": "submit",
        "job_id": job_id,
        "spec": spec,
        "goal": goal,
        "model": model,
        "workdir": workdir,
        "ts": time.time(),
        "nonce": uuid.uuid4().hex[:12],
    }
    if image:
        command["image"] = image
    if spec_sha256:
        command["spec_sha256"] = spec_sha256
    if resume:
        command["resume"] = True
    if parent_run_id:
        command["parent_run_id"] = parent_run_id
    if admission:
        command["admission"] = dict(admission)
    if execution:
        command["execution"] = dict(execution)
    # The AIO binding identity (Unit D) survives the hop in the SAME unchecked way: the
    # manager never validates it — the wrapper and the broker each resolve the binding from
    # the durable store by identity and refuse what does not match.
    if aio:
        command["actor"] = "aio"
        command["aio"] = dict(aio)
    key = str(request_key or "").strip() or None
    if key:
        command["request_key"] = key
    if key:
        result = client.eval(
            _SUBMIT_LUA, 3, REQUESTS_KEY, COMMANDS_KEY, JOBS_KEY,
            key, command["job_id"], json.dumps(command),
            json.dumps(_job_launch_record(command)),
        )
        existing_id = str(result[0] or "")
        if existing_id and existing_id != command["job_id"]:
            # The reconcile path: this key already names a job. Return it — never queue a
            # second command — but refuse if the key is being reused for a DIFFERENT request
            # (silently ignoring the new spec would be worse than a loud refusal).
            raw_record = str(result[1] or "")
            try:
                existing = json.loads(raw_record) if raw_record else {}
            except (TypeError, ValueError):
                existing = {}
            if not isinstance(existing, dict) or not existing:
                existing = {"job_id": existing_id}
            existing_spec = str(existing.get("spec") or "")
            if existing_spec and existing_spec != spec:
                raise RequestKeyConflictError(
                    f"request key {key!r} already maps to job {existing_id} for spec "
                    f"{existing_spec!r} — a request key identifies ONE submission; a "
                    "different request needs a new key"
                )
            existing["job_id"] = existing_id
            existing["reconciled"] = True
            return existing
        return command
    client.lpush(COMMANDS_KEY, json.dumps(command))
    record_job_launch(client, command)
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
    p_submit = sub.add_parser(
        "submit", help="command the orchestrator to validate and launch a workflow job"
    )
    p_submit.add_argument("--spec", required=True, help="spec path, e.g. workflows/repository/<name>.yaml")
    p_submit.add_argument("--goal", required=True)
    p_submit.add_argument("--model", required=True)
    p_submit.add_argument("--workdir", required=True, help="a worktree path under FINOPS_WORKTREE_ROOT")
    p_submit.add_argument("--image", default=None,
                          help="optional per-job image for the spec's phase cells "
                               "(fleet/job-<name>, built via scripts/fleet/build.sh job <name> "
                               "— p3_base_image_caching); default: fleet/base")
    p_submit.add_argument("--spec-sha256", default=None,
                          help="sha256 of the spec file's bytes (source/spec identity — "
                               "verified by the broker before the compose call)")
    p_submit.add_argument("--resume", action="store_true",
                          help="the submit resumes an existing run (continuation identity — "
                               "the broker skips the main-freshness refusal)")
    p_submit.add_argument("--parent-run-id", default=None,
                          help="the control-db run id this submit continues (requires --resume)")
    p_submit.add_argument("--admission-required", action="store_true",
                          help="arm the admission gate in the orchestrator container "
                               "(FINOPS_ADMISSION_REQUIRED=1 — a submit WITHOUT this flag "
                               "while the host gate is armed is refused by the broker)")
    p_submit.add_argument("--campaign-budget-usd", type=float, default=None,
                          help="the campaign budget ceiling the run applies to the lease "
                               "registry (distinct from any daily real-cash allowance)")
    p_submit.add_argument("--campaign-concurrency", type=int, default=None,
                          help="the campaign concurrency cap the run applies to the lease "
                               "registry")
    p_submit.add_argument("--reserve-usd", type=float, default=None,
                          help="per-phase dollar reservation for per-token models "
                               "(FINOPS_RESERVE_USD — the armed gate DENIES without a stated "
                               "reserve: an unknown cost is never free)")
    p_submit.add_argument("--hard-cap-usd", type=float, default=None,
                          help="per-lease dollar ceiling for per-token models "
                               "(FINOPS_HARD_CAP_USD)")
    p_submit.add_argument("--backend", default=None, choices=["opencode", "claude_cli"],
                          help="the execution backend (pass-through; the orchestrator "
                               "default is auto-routing)")
    p_submit.add_argument("--thinking-effort", default=None,
                          help="the thinking effort level (pass-through)")
    p_submit.add_argument("--thinking-budget-tokens", type=int, default=None,
                          help="the thinking token budget (pass-through)")
    p_submit.add_argument("--output-token-limit", type=int, default=None,
                          help="the output token limit (pass-through)")
    p_submit.add_argument("--timeout-seconds", type=int, default=None,
                          help="the per-phase timeout in seconds (pass-through)")
    p_submit.add_argument("--no-commit", action="store_true",
                          help="run phases without runner commits (pass-through)")
    # The AIO binding identity (Unit D). The tool derives these from the NATIVE context
    # (ctx.sessionID / ctx.agent) plus the durable binding read — never from model-supplied
    # fields. Presence of --aio-session-id marks the submit as the AIO actor; the orchestrator
    # and the broker then resolve + validate the binding by identity before any launch.
    p_submit.add_argument("--aio-session-id", default=None,
                          help="the native opencode session id the AIO submit runs as "
                               "(presence marks the AIO actor)")
    p_submit.add_argument("--aio-agent", default=None,
                          help="the resolved native agent (must match the binding)")
    p_submit.add_argument("--binding-id", default=None,
                          help="the durable AIO binding record id (validated against the store)")
    p_submit.add_argument("--task-revision", type=int, default=None,
                          help="the binding's task/acceptance context version (stale revisions "
                               "are refused)")
    p_submit.add_argument("--request-key", default=None,
                          help="a caller-stable request key: a retry with the SAME key "
                               "reconciles to the existing job instead of minting a second one "
                               "(retain the key before sending; reuse it after an ambiguous or "
                               "lost submit response)")

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
            if board["jobs"]:
                print("jobs:")
                for j in board["jobs"]:
                    print(f"  [{j.get('status')}] {j.get('job_id')} spec={j.get('spec')} "
                          f"model={j.get('model')}")
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

    if args.command == "submit":
        admission: dict | None = None
        if args.admission_required or args.campaign_budget_usd is not None or (
            args.campaign_concurrency is not None
        ):
            admission = {"required": bool(args.admission_required)}
            if args.campaign_budget_usd is not None:
                admission["campaign_budget_usd"] = args.campaign_budget_usd
            if args.campaign_concurrency is not None:
                admission["campaign_concurrency"] = args.campaign_concurrency
            if args.reserve_usd is not None:
                admission["reserve_usd"] = args.reserve_usd
            if args.hard_cap_usd is not None:
                admission["hard_cap_usd"] = args.hard_cap_usd
        execution: dict | None = None
        if any(value is not None for value in (
            args.backend, args.thinking_effort, args.thinking_budget_tokens,
            args.output_token_limit, args.timeout_seconds,
        )) or args.no_commit:
            execution = {}
            if args.backend is not None:
                execution["backend"] = args.backend
            if args.thinking_effort is not None:
                execution["thinking_effort"] = args.thinking_effort
            if args.thinking_budget_tokens is not None:
                execution["thinking_budget_tokens"] = args.thinking_budget_tokens
            if args.output_token_limit is not None:
                execution["output_token_limit"] = args.output_token_limit
            if args.timeout_seconds is not None:
                execution["timeout_seconds"] = args.timeout_seconds
            if args.no_commit:
                execution["no_commit"] = True
        aio: dict | None = None
        if args.aio_session_id:
            aio = {
                "native_session_id": args.aio_session_id,
                "agent": args.aio_agent or "",
                "binding_id": args.binding_id or "",
                "task_revision": args.task_revision,
            }
        try:
            cmd = _send_submit_command(
                client, spec=args.spec, goal=args.goal, model=args.model, workdir=args.workdir,
                image=args.image, spec_sha256=args.spec_sha256, resume=args.resume,
                parent_run_id=args.parent_run_id, admission=admission, execution=execution,
                aio=aio, request_key=args.request_key,
            )
        except RequestKeyConflictError as exc:
            print(f"fleet:submit refused: {exc}", file=sys.stderr)
            return 2
        if cmd.get("reconciled"):
            # A keyed retry: NOTHING was queued — the existing job is the submission. The
            # echoed line keeps the tool's ``fleet:jobs[<id>]`` parse working under the same
            # identity, and the status tells the caller how far the original submit got.
            print(f"fleet:jobs[{cmd['job_id']}] <- reconciled (status: {cmd.get('status') or 'unknown'})")
        else:
            print(f"fleet:commands <- {json.dumps(cmd)}")
            print(f"fleet:jobs[{cmd['job_id']}] <- launching")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
