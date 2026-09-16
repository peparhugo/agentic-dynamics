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
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# scripts/fleet/ -> add scripts/ to the path, then reuse the shared bootstrap.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# The repo root + src/ (the same clean-environment bootstrap spawn_wrapper applies): the
# preparation path resolves the shared PathConfig so the derived workspace lands under the
# SAME worktrees root the exec boundary validates against.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

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
    if command.get("task_identity"):
        record["task_identity"] = command["task_identity"]
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

    Reconciliation compares the FULL execution-relevant fingerprint (spec path AND digest,
    goal, model, worktree, continuation, admission/execution settings) — a key reused with
    any changed input is a different request and refuses loudly (reviewer finding,
    2026-09-16: comparing the spec filename alone silently discarded edited requests).
    """


class RequestKeyUnresolvedError(ValueError):
    """A stored request identity cannot be verified — the evidence is missing/corrupt.

    When the retained entry carries no fingerprint (missing evidence), the retry is neither
    reconciled nor re-queued: an explicit unresolved state refuses loudly, naming the key.
    """


def request_fingerprint(
    *,
    spec: str,
    goal: str,
    model: str,
    workdir: str,
    image: str | None = None,
    spec_sha256: str | None = None,
    resume: bool = False,
    parent_run_id: str | None = None,
    admission: dict | None = None,
    execution: dict | None = None,
) -> str:
    """The canonical fingerprint of a submission's EXECUTION-RELEVANT inputs.

    Retained alongside the request identity at claim time and compared at reconcile time: a
    retry reconciles only when every execution-relevant input matches; any change is a
    different request. The AIO binding identity is deliberately NOT part of the fingerprint —
    a legitimate retry after re-binding/compaction carries a newer task revision and must
    still reconcile. Declared inputs only (the tool always supplies ``spec_sha256``; a caller
    that omits it cannot see a same-path edit — the digest is what catches that).
    """
    payload = {
        "spec": str(spec or ""),
        "goal": str(goal or ""),
        "model": str(model or ""),
        "workdir": str(workdir or ""),
        "image": str(image or ""),
        "spec_sha256": str(spec_sha256 or ""),
        "resume": bool(resume),
        "parent_run_id": str(parent_run_id or ""),
        "admission": admission or {},
        "execution": execution or {},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_request_entry(raw: str, key: str) -> dict:
    """Parse a stored request entry ``{job_id, fingerprint}``; missing evidence refuses.

    An unparseable entry or one without a fingerprint is the explicit UNRESOLVED state — the
    retry cannot be verified against anything, and silently reconciling it (or silently
    re-queueing it) would be exactly the ambiguity the request key exists to remove.
    """
    try:
        entry = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise RequestKeyUnresolvedError(
            f"request key {key!r} has an unreadable stored identity ({exc}) — cannot verify "
            "this retry; resolve it from the board or mint a new key"
        ) from exc
    if (
        not isinstance(entry, dict)
        or not entry.get("job_id")
        or not entry.get("fingerprint")
        or not entry.get("workdir")
    ):
        raise RequestKeyUnresolvedError(
            f"request key {key!r} carries no stored fingerprint/workspace (missing evidence) "
            "— cannot verify this retry; resolve it from the board or mint a new key"
        )
    return entry


# ── The workspace preparation path (Unit 2) ────────────────────────────────────
#
# A submit may OMIT --workdir: the preparation path selects/creates the workspace using the
# existing worktree support, instead of every caller assembling one by hand. The derived
# name is DETERMINISTIC for the request's pre-workdir identity, so a retry-safe
# resubmission resolves the SAME candidate path and reconciles by key (no second workspace,
# no mutation). A pre-existing candidate that is not this repo's CLEAN worktree refuses
# loudly — never mutated to fit.
#
# FRESH submissions are bound to the repo's CURRENT main tip: a compatible workspace
# (clean, at/ahead of main) is reused; a stale one is never reset — a separate,
# SHA-suffixed workspace is created beside it. A RETRY must never re-resolve the workspace:
# the submit path's retry pre-check skips preparation entirely when the key already names a
# submission (nothing will run, and re-resolving after a main advance could turn the retry
# into a different request).
#
# CONTINUATIONS (--resume --parent-run-id) work from the parent run's PRIVATE CLONE
# (``runs_root/<parent-id>/repo`` — the repository that actually contains its committed
# phases) at the parent ledger's candidate SHA, verified before any phase is inherited. The
# parent's declared workdir is NEVER the continuation base: its commits are not there.


def _workspace_identity_digest(
    *,
    spec: str,
    goal: str,
    model: str,
    image: str | None = None,
    spec_sha256: str | None = None,
    resume: bool = False,
    parent_run_id: str | None = None,
    admission: dict | None = None,
    execution: dict | None = None,
) -> str:
    """The PRE-workdir digest that names the derived workspace (stable across a retry)."""
    payload = {
        "spec": str(spec or ""), "goal": str(goal or ""), "model": str(model or ""),
        "image": str(image or ""), "spec_sha256": str(spec_sha256 or ""),
        "resume": bool(resume), "parent_run_id": str(parent_run_id or ""),
        "admission": admission or {}, "execution": execution or {},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _git_run(*args: str, cwd: Path, timeout: int = 120) -> tuple[int, str]:
    """One git call for the preparation path; a missing/broken git is a named refusal."""
    try:
        proc = subprocess.run(  # noqa: S603 — the submission tier owns workspace preparation
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, f"git unavailable ({type(exc).__name__}: {exc})"
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def _derived_workspace_path(spec: str, digest: str) -> Path:
    """The deterministic workspace path for a request: worktrees_root/wt_<spec>_<digest8>."""
    from agentic_dynamics.core.paths import PathConfig

    worktrees_root = Path(PathConfig.from_env(require_existing=False).worktrees_root)
    stem = "".join(
        c if (c.isalnum() or c in "-_") else "_" for c in Path(str(spec or "run")).stem
    )[:48] or "run"
    return worktrees_root / f"wt_{stem}_{digest[:8]}"


def _candidate_workspace_path(
    *, spec: str, digest: str, resume: bool = False, parent_run_id: str | None = None
) -> Path:
    """The candidate workspace for a request, WITHOUT touching anything (the retry probe).

    A continuation's candidate is the parent's private clone (the repository that contains
    its committed phases); a fresh submission's is the deterministic derived path.
    """
    if resume and str(parent_run_id or "").strip():
        from agentic_dynamics.runtime.run_clone import run_clone_dir

        return run_clone_dir(str(parent_run_id))
    return _derived_workspace_path(spec, digest)


def _main_tip() -> str:
    """The repo's main tip — the SELECTED SOURCE SHA for a fresh submission ('' if absent)."""
    rc, out = _git_run("rev-parse", "--verify", "main^{commit}", cwd=Path(_REPO_ROOT))
    return out.strip() if rc == 0 else ""


def _workspace_compatible(path: Path, main_sha: str) -> bool:
    """Whether an existing workspace can serve a fresh run: at/ahead of main (or unjudged).

    Mirrors the broker's deployment probe: behind/diverged is stale (a fresh submission must
    not silently reuse it); an unjudgeable state (no main ref, git failure) says nothing and
    is treated as compatible — a fabricated refusal is worse than none.
    """
    if not main_sha:
        return True
    rc, _out = _git_run("merge-base", "--is-ancestor", main_sha, "HEAD", cwd=path)
    if rc == 0:
        return True
    # rc==1 is "behind/diverged" (stale); any other failure (127/128…) is unjudgeable — the
    # broker's probe is equally silent there, and a fabricated refusal is worse than none.
    return rc != 1


def _check_existing_workspace(path: Path) -> list[str]:
    """The reuse checks for an existing candidate: a real, clean worktree or a refusal."""
    if not (path / ".git").exists():
        return [
            f"submit: the derived workspace {path} exists but is not a git worktree — "
            "refusing to reuse or overwrite it; pass an explicit --workdir or move it aside"
        ]
    rc, out = _git_run("status", "--porcelain", cwd=path)
    if rc != 0:
        return [
            f"submit: the derived workspace {path} is not a readable git worktree "
            f"({out or 'git status failed'}) — pass an explicit --workdir"
        ]
    if out.strip():
        return [
            f"submit: the derived workspace {path} has uncommitted changes (a likely "
            "interrupted run) — refusing to mutate it; inspect it, clean it, or pass an "
            "explicit --workdir"
        ]
    return []


def _parent_run_ledger(parent_run_id: str) -> dict | None:
    """The newest parent-run ledger payload under the workflows results tree, or None."""
    root = Path(_REPO_ROOT) / "experiments" / "results" / "workflows"
    try:
        ledgers = sorted(root.glob(f"*/*_{parent_run_id}.json"))
    except OSError:
        return None
    for ledger in reversed(ledgers):
        try:
            data = json.loads(ledger.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return None


def _stamped_provenance(clone: Path) -> str:
    """The clone's stamped project provenance ('' when unstamped)."""
    from agentic_dynamics.runtime.run_clone import PROJECT_PROVENANCE_KEY

    rc, out = _git_run("config", "--get", PROJECT_PROVENANCE_KEY, cwd=clone)
    return out.strip() if rc == 0 else ""


def _canonical_project_token(repo_root: Path) -> str:
    """The canonical project's identity token: its origin URL, else its common git dir."""
    rc, out = _git_run("config", "--get", "remote.origin.url", cwd=repo_root)
    origin = out.strip() if rc == 0 else ""
    if origin:
        return f"origin:{origin}"
    rc, out = _git_run("rev-parse", "--git-common-dir", cwd=repo_root)
    common = out.strip() if rc == 0 else ""
    if not common:
        return ""
    common_path = Path(common)
    if not common_path.is_absolute():
        common_path = (repo_root / common_path).resolve()
    return f"git-dir:{common_path}"


def _ensure_clone_provenance(clone: Path, repo_root: Path) -> list[str]:
    """Verify a PRE-FIX clone's derivation from the canonical project and stamp it.

    A clone created before the provenance stamp carries only git's default LOCAL origin (the
    source path as the creating container saw it, e.g. ``/repo``), which the project
    validator cannot match — validation refused an otherwise valid continuation (round-5
    finding, 2026-09-16). Verification is by SHARED HISTORY: a clone copies its source's
    full history, so a clone derived from THIS project carries this project's root commit;
    a foreign clone carries a different root and refuses. On success the clone is stamped
    exactly as a fresh clone would be; nothing else about it is touched — its candidate
    commits and worktree are preserved.
    """
    if _stamped_provenance(clone):
        return []  # already stamped (validated when written)
    rc, roots_out = _git_run("rev-list", "--max-parents=0", "HEAD", cwd=clone)
    if rc != 0:
        return [
            f"submit: cannot read {clone}'s history to verify its project provenance "
            f"({roots_out or 'git rev-list failed'}) — refusing the continuation"
        ]
    roots = [line.strip() for line in roots_out.splitlines() if line.strip()]
    if not roots:
        return [
            f"submit: {clone} has no root commit — its derivation cannot be verified; "
            "refusing the continuation"
        ]
    verified = any(
        _git_run("cat-file", "-e", f"{root}^{{commit}}", cwd=repo_root)[0] == 0
        for root in roots
    )
    if not verified:
        return [
            f"submit: the parent clone {clone} shares no history with the canonical "
            "repository — its derivation cannot be verified; refusing to continue from it "
            "(a foreign clone is never accepted)"
        ]
    token = _canonical_project_token(repo_root)
    if token:
        from agentic_dynamics.runtime.run_clone import PROJECT_PROVENANCE_KEY

        _git_run("config", PROJECT_PROVENANCE_KEY, token, cwd=clone)
    return []


def _candidate_present(tree: Path, candidate: str) -> list[str]:
    """The candidate commit must EXIST in ``tree`` and be reachable from its HEAD.

    "Verify that candidate before inheriting completed phases": a continuation that skips
    the parent's completed phases must run on a tree that actually contains their commits.
    """
    if not candidate:
        return [
            "submit: the parent ledger records no candidate SHA — the tree containing its "
            "completed work cannot be identified; refusing the continuation"
        ]
    rc, _out = _git_run("cat-file", "-e", f"{candidate}^{{commit}}", cwd=tree)
    if rc != 0:
        return [
            f"submit: the parent's candidate {candidate[:12]} is not present in {tree} — a "
            "continuation cannot inherit completed phases from a tree that does not contain "
            "them"
        ]
    rc, _out = _git_run("merge-base", "--is-ancestor", candidate, "HEAD", cwd=tree)
    if rc != 0:
        return [
            f"submit: the parent's candidate {candidate[:12]} is not reachable from {tree}'s "
            "HEAD — refusing to inherit completed phases from a divergent tree"
        ]
    return []


def prepare_workspace(
    *,
    spec: str,
    goal: str,
    model: str,
    image: str | None = None,
    spec_sha256: str | None = None,
    resume: bool = False,
    parent_run_id: str | None = None,
    admission: dict | None = None,
    execution: dict | None = None,
) -> tuple[Path | None, str, list[str]]:
    """Resolve the workspace for a submit that omits --workdir: ``(path, note, errors)``.

    A continuation reuses the parent run's workdir (from its ledger). Otherwise the derived
    path is reused when it is this repo's clean worktree, and CREATED (branch ``wt_<name>``
    at the repo's main tip — the base the deployment probe requires) when absent. Errors are
    named refusals; the caller prints them and submits nothing.
    """
    if resume and str(parent_run_id or "").strip():
        ledger = _parent_run_ledger(str(parent_run_id))
        if ledger is None:
            return None, "", [
                f"submit: no ledger found for parent run {parent_run_id!r} — its completed "
                "phases cannot be established; pass --workdir explicitly for this continuation"
            ]
        candidate = str(ledger.get("git_sha") or "").strip()
        from agentic_dynamics.runtime.run_clone import run_clone_dir

        clone = run_clone_dir(str(parent_run_id))
        if not (clone / ".git").exists():
            return None, "", [
                f"submit: the parent run's private clone {clone} is gone — its completed "
                f"work lives there, not in the source tree; a continuation cannot be "
                f"prepared without it (candidate {candidate[:12] or 'unknown'})"
            ]
        errors = _candidate_present(clone, candidate)
        if errors:
            return None, "", errors
        # A PRE-FIX clone (created before the provenance stamp) is verified by shared
        # history and stamped here, so validation sees the canonical project identity.
        errors = _ensure_clone_provenance(clone, Path(_REPO_ROOT))
        if errors:
            return None, "", errors
        return clone, (
            f"workspace reused from parent run {parent_run_id}: {clone} "
            f"(candidate {candidate[:12]})"
        ), []

    digest = _workspace_identity_digest(
        spec=spec, goal=goal, model=model, image=image, spec_sha256=spec_sha256,
        resume=resume, parent_run_id=parent_run_id, admission=admission, execution=execution,
    )
    path = _derived_workspace_path(spec, digest)
    main_sha = _main_tip()
    if path.exists():
        errors = _check_existing_workspace(path)
        if errors:
            return None, "", errors
        if _workspace_compatible(path, main_sha):
            return path, f"workspace reused: {path}", []
        # STALE relative to the selected source SHA: never reset it — a fresh submission
        # gets a separate, SHA-suffixed workspace beside it.
        path = path.with_name(f"{path.name}_{main_sha[:7]}")
        if path.exists():
            errors = _check_existing_workspace(path)
            if errors:
                return None, "", errors
            if not _workspace_compatible(path, main_sha):
                return None, "", [
                    f"submit: the SHA-suffixed workspace {path} is also behind the main tip "
                    f"{main_sha[:12]} — refusing to reset existing work; clean or move it aside"
                ]
            return path, f"workspace reused: {path} (suffixed for main {main_sha[:7]})", []

    repo_root = Path(_REPO_ROOT)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return None, "", [f"submit: cannot create the worktrees root {path.parent} ({exc})"]
    branch = path.name
    base = main_sha or "main"
    rc, out = _git_run("worktree", "add", "-b", branch, str(path), base, cwd=repo_root)
    if rc != 0 and "already exists" in out:
        # A leftover branch from a removed worktree: check the branch out at the path
        # instead of resetting it (-B would move the branch under any existing commits).
        rc, out = _git_run("worktree", "add", str(path), branch, cwd=repo_root)
    if rc != 0:
        return None, "", [
            f"submit: workspace preparation failed ({out or 'git worktree add failed'}) — "
            "pass an explicit --workdir"
        ]
    return path, f"workspace prepared: {path} (branch {branch}, base {base[:12]})", []


#: The request-keyed submit, ATOMICALLY (one server-side script): the request->job
#: association, the command LPUSH, and the board record commit together — a key is either
#: fully claimed-and-queued, or not claimed at all. A concurrent same-key submitter observes
#: the winner's identity and reconciles; a retry can never double-queue. Keys[1] stores the
#: JSON entry ``{job_id, fingerprint}`` (the fingerprint is the reconcile evidence — it must
#: survive even when the board record does not). Returns ``{first, record_json}``: the NEW
#: job id on the claim path; the EXISTING entry JSON on the reconcile path (the record follows
#: separately, empty when the board record is missing/unreadable).
_SUBMIT_LUA = """
local existing = redis.call('HGET', KEYS[1], ARGV[1])
if existing then
  local ok, entry = pcall(cjson.decode, existing)
  if ok and type(entry) == 'table' and entry['job_id'] then
    return {existing, redis.call('HGET', KEYS[3], tostring(entry['job_id'])) or ''}
  end
  -- Corrupt/legacy evidence rides back raw; the caller refuses it as UNRESOLVED.
  return {existing, ''}
end
redis.call('HSET', KEYS[1], ARGV[1], ARGV[5])
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


def _derive_request_key(
    *,
    explicit: str | None,
    retry_safe: bool,
    task_identity: str,
    scope_digest: str,
) -> str | None:
    """The effective request key: explicit wins; retry-safe derives per LOGICAL TASK.

    The derived key is scoped by the durable TASK identity (the binding's ``task_identity``,
    passed by the tool) AND the PRE-WORKDIR request digest (spec, goal, model, image, spec
    digest, continuation, admission/execution — everything except the resolved workspace).
    The digest deliberately EXCLUDES the workspace: the workspace is resolved by preparation
    and recorded WITH the submission, so a retry must derive the SAME key no matter how the
    workspace resolution would answer today (reviewer finding, 2026-09-16: a key over the
    resolved path changed when main advanced, so a retry could not find its own record). A
    retry within the same task reconciles; the SAME inputs from a DIFFERENT task/session are
    a different logical submission and get a DIFFERENT identity; a task identity that is
    explicit (not the per-session fallback) also survives session changes. Without a task
    identity (a bare CLI caller), the digest alone scopes the key.
    """
    key = str(explicit or "").strip() or None
    if key is not None:
        return key
    if not retry_safe:
        return None
    scope = str(task_identity or "").strip()
    basis = f"{scope}\x1f{scope_digest}" if scope else scope_digest
    return f"auto:{hashlib.sha256(basis.encode('utf-8')).hexdigest()[:32]}"


def _request_entry_lookup(client: redis.Redis, key: str) -> tuple[bool, dict | None]:
    """The submit path's retry probe: ``(exists, parsed_entry)``.

    A hit means the submission was already claimed: the workspace must NOT be re-prepared —
    the RETRY resolves the workspace from the retained record (nothing will run; the claim
    reconciles or refuses the fingerprint mismatch). An entry that cannot be parsed still
    reports ``exists=True`` so preparation is skipped; the atomic claim refuses it as
    UNRESOLVED. A Redis error reads as "no entry": the submit itself needs Redis, so it will
    fail loudly there.
    """
    try:
        raw = client.hget(REQUESTS_KEY, key)
    except Exception:  # noqa: BLE001 — never invent a new submission on a read blip
        return False, None
    if not raw:
        return False, None
    try:
        entry = json.loads(raw)
    except (TypeError, ValueError):
        return True, None
    return True, entry if isinstance(entry, dict) else None


def _send_submit_command(client: redis.Redis, *, spec: str, goal: str, model: str,
                         workdir: str, image: str | None = None,
                         spec_sha256: str | None = None,
                         resume: bool = False,
                         parent_run_id: str | None = None,
                         admission: dict | None = None,
                         execution: dict | None = None,
                         aio: dict | None = None,
                         request_key: str | None = None,
                         retry_safe: bool = False,
                         task_identity: str | None = None) -> dict:
    """LPUSH a submit command onto ``fleet:commands`` and record its "launching" board entry.

    The fleet-manager mints the ``job_id`` (the board's join key) but does NOT validate the
    request — that stays the orchestrator's job (``spawn_wrapper.validate_submit_request``),
    exactly as resize/drain/restart's validation stays with the orchestrator, never the
    supervisor. Nothing here refuses a concurrent submit for the same or another spec; there is
    no lock (the design's "ZERO refusing of concurrency" rule) — every submit is independently
    LPUSHed and independently validated when it is popped.

    ``request_key`` (2026-09-16, Unit 2) is the caller-stable retry identity: when supplied,
    the association + LPUSH + board record commit ATOMICALLY (one server-side script). A
    retry with the SAME key reconciles ONLY when the FULL execution-relevant fingerprint
    matches — any changed input (spec digest, goal, model, worktree, continuation,
    admission/execution settings) refuses (:class:`RequestKeyConflictError`), and a stored
    entry without a fingerprint is an explicit unresolved state
    (:class:`RequestKeyUnresolvedError`). ``retry_safe=True`` (the ordinary tool path)
    derives the key from the fingerprint SCOPED TO THE LOGICAL TASK (``task_identity``, the
    durable binding's task identity) when the caller supplied none, so an identical retry
    reconciles without the caller having to retain anything — while the SAME inputs from a
    different task/session are a different logical submission and receive a different
    identity; an explicit ``request_key`` always wins (that is how a caller FORCES an
    independent new run of identical inputs). Neither = the caller wants an independent
    submission (identical goal text may be an intentional new run — this is not content
    deduplication).

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
    fingerprint = request_fingerprint(
        spec=spec, goal=goal, model=model, workdir=workdir, image=image,
        spec_sha256=spec_sha256, resume=resume, parent_run_id=parent_run_id,
        admission=admission, execution=execution,
    )
    scope_digest = _workspace_identity_digest(
        spec=spec, goal=goal, model=model, image=image, spec_sha256=spec_sha256,
        resume=resume, parent_run_id=parent_run_id, admission=admission, execution=execution,
    )
    key = _derive_request_key(
        explicit=request_key, retry_safe=retry_safe,
        task_identity=str(task_identity or ""), scope_digest=scope_digest,
    )
    if str(task_identity or "").strip():
        command["task_identity"] = str(task_identity).strip()
    if key:
        command["request_key"] = key
    if key:
        entry = json.dumps({
            "job_id": command["job_id"],
            "fingerprint": fingerprint,
            # The RESOLVED workspace is part of the retained identity (reviewer finding,
            # 2026-09-16): a retry must reuse exactly the workspace the submission was
            # assigned — including a SHA-suffixed one — never re-resolve it.
            "workdir": workdir,
        })
        result = client.eval(
            _SUBMIT_LUA, 3, REQUESTS_KEY, COMMANDS_KEY, JOBS_KEY,
            key, command["job_id"], json.dumps(command),
            json.dumps(_job_launch_record(command)), entry,
        )
        first = str(result[0] or "")
        if first and first != command["job_id"]:
            # The reconcile path: this key already names a job. Never queue a second command
            # — reconcile ONLY against a matching full fingerprint (any changed input is a
            # different request), and refuse explicitly when the stored evidence is missing.
            existing = _parse_request_entry(first, key)
            if existing["fingerprint"] != fingerprint:
                raise RequestKeyConflictError(
                    f"request key {key!r} already maps to job {existing['job_id']} for a "
                    "DIFFERENT request (the execution-relevant fingerprint changed: spec, "
                    "digest, goal, model, worktree, continuation, admission, or execution "
                    "settings) — a request key identifies ONE submission; a changed request "
                    "needs a new key"
                )
            raw_record = str(result[1] or "")
            try:
                record = json.loads(raw_record) if raw_record else {}
            except (TypeError, ValueError):
                record = {}
            if not isinstance(record, dict) or not record:
                # Same request (fingerprint proven), but the board record is gone: reconcile
                # the identity and say the lifecycle is unknown — never fabricate a status.
                record = {
                    "job_id": existing["job_id"],
                    "status": "unknown",
                    "board_record": "missing",
                }
            record["job_id"] = existing["job_id"]
            record["request_key"] = key
            record["reconciled"] = True
            return record
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
    p_submit.add_argument("--workdir", default=None,
                          help="a worktree path under FINOPS_WORKTREE_ROOT; OMITTED, the "
                               "preparation path selects/creates one (deterministic name, "
                               "reused across an identical retry; a continuation works from "
                               "the parent run's private clone at its candidate SHA)")
    p_submit.add_argument("--task-identity", default=None,
                          help="the durable TASK identity the submit belongs to (the AIO "
                               "binding's task_identity): retry-safe keys are scoped by it, "
                               "so identical inputs from a DIFFERENT task are a different "
                               "logical submission")
    p_submit.add_argument("--json", action="store_true",
                          help="emit the machine result (fleet-submit/v1) instead of human lines")
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
                               "lost submit response). Reconciliation compares the FULL "
                               "execution-relevant fingerprint — a changed request refuses.")
    p_submit.add_argument("--retry-safe", action="store_true",
                          help="derive the request key from the submission's execution-"
                               "relevant inputs (the ordinary tool path sets this when the "
                               "caller supplied no explicit key): an identical retry "
                               "reconciles automatically; an explicit --request-key wins")

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
        # The workspace preparation path (Unit 2): an omitted --workdir is resolved here —
        # never a caller obligation to assemble one by hand.
        workdir = str(args.workdir or "").strip()
        prep_note = ""
        task_identity = str(args.task_identity or "").strip()
        if not workdir:
            # RETRY PROBE FIRST: when the derived key already names a submission, this is a
            # retry — reconcile against it and never re-prepare (nothing will run, and
            # re-resolving after a main advance could turn the retry into a different
            # request instead of a reconciliation).
            digest = _workspace_identity_digest(
                spec=args.spec, goal=args.goal, model=args.model, image=args.image,
                spec_sha256=args.spec_sha256, resume=bool(args.resume),
                parent_run_id=args.parent_run_id, admission=admission, execution=execution,
            )
            candidate = _candidate_workspace_path(
                spec=args.spec, digest=digest, resume=bool(args.resume),
                parent_run_id=args.parent_run_id,
            )
            probe_key = _derive_request_key(
                explicit=args.request_key, retry_safe=args.retry_safe,
                task_identity=task_identity, scope_digest=digest,
            )
            probe_exists, probe_entry = (
                _request_entry_lookup(client, probe_key) if probe_key else (False, None)
            )
            if probe_exists:
                # A RETRY: the workspace comes FROM the retained record — never re-resolved.
                # Re-resolving would fingerprint a path the submission was NOT assigned (the
                # reviewer's repro: a SHA-suffixed workspace was recorded, the probe rebuilt
                # the unsuffixed path, and the retry either conflicted or queued a duplicate
                # after another main advance). An unreadable retained identity does not
                # prepare either: the atomic claim refuses it as UNRESOLVED.
                recorded = str((probe_entry or {}).get("workdir") or "").strip()
                workdir = recorded or str(candidate)
                prep_note = (
                    f"retry: reconciling against the existing request {probe_key} "
                    f"(workspace {workdir})"
                )
            else:
                resolved, prep_note, prep_errors = prepare_workspace(
                    spec=args.spec, goal=args.goal, model=args.model, image=args.image,
                    spec_sha256=args.spec_sha256, resume=bool(args.resume),
                    parent_run_id=args.parent_run_id, admission=admission,
                    execution=execution,
                )
                if prep_errors:
                    print(f"fleet:submit refused: {prep_errors[0]}", file=sys.stderr)
                    return 2
                workdir = str(resolved)
        try:
            cmd = _send_submit_command(
                client, spec=args.spec, goal=args.goal, model=args.model, workdir=workdir,
                image=args.image, spec_sha256=args.spec_sha256, resume=args.resume,
                parent_run_id=args.parent_run_id, admission=admission, execution=execution,
                aio=aio, request_key=args.request_key, retry_safe=args.retry_safe,
                task_identity=task_identity,
            )
        except (RequestKeyConflictError, RequestKeyUnresolvedError) as exc:
            print(f"fleet:submit refused: {exc}", file=sys.stderr)
            return 2
        if args.json:
            # The structured result (fleet-submit/v1): job identity, state, resolved
            # source/spec, request identity, and the prep note — machine-first, so no caller
            # parses a human log line as the durable interface.
            print(json.dumps({
                "schema": "fleet-submit/v1",
                "job_id": cmd.get("job_id", ""),
                "reconciled": bool(cmd.get("reconciled")),
                "status": cmd.get("status") or ("unknown" if cmd.get("reconciled") else "launching"),
                "request_key": cmd.get("request_key", ""),
                "task_identity": cmd.get("task_identity", ""),
                "spec": args.spec,
                "spec_sha256": args.spec_sha256 or "",
                "goal": args.goal,
                "model": args.model,
                "workdir": workdir,
                "resume": bool(args.resume),
                "parent_run_id": args.parent_run_id or "",
                "prep_note": prep_note,
            }))
            return 0
        if prep_note:
            print(f"fleet:prep {prep_note}")
        if cmd.get("reconciled"):
            # A keyed retry: NOTHING was queued — the existing job is the submission. The
            # echoed line keeps the tool's ``fleet:jobs[<id>]`` parse working under the same
            # identity, and the status tells the caller how far the original submit got.
            print(
                f"fleet:jobs[{cmd['job_id']}] <- reconciled "
                f"(status: {cmd.get('status') or 'unknown'}; "
                f"request key {cmd.get('request_key') or '?'})"
            )
        else:
            print(f"fleet:commands <- {json.dumps(cmd)}")
            print(f"fleet:jobs[{cmd['job_id']}] <- launching")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
