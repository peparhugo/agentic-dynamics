"""Enqueue experiment cells into Redis for parallel execution.

Usage:
    python scripts/enqueue.py                      # Fill queue with all cells (DeepSeek)
    python scripts/enqueue.py --model anthropic/claude-sonnet-4-5   # Claude cells
    python scripts/enqueue.py --missing-only       # Skip cells that already have a result
    python scripts/enqueue.py --interleave         # Weave new cells across models/providers
    python scripts/enqueue.py --dry-run            # Print the plan without enqueueing
    python scripts/enqueue.py --clear              # Clear the queue (reset)

Model is read from FINOPS_MODEL env var or --model flag.

Admission (``admission_leases`` p2): when the spend gate is armed
(``FINOPS_ADMISSION_REQUIRED=1``) every cell gets a **budget lease reserved at queue-fill
time**, and the lease block rides on the job JSON — so the queue can never carry unbudgeted
work. The reservation is all-or-nothing across the batch: if any cell is denied, every lease
already taken for the batch is released and nothing is enqueued, because a half-budgeted queue
is worse than an empty one (a worker cannot tell which of its jobs were paid for). No
concurrency lease is taken here: filling a queue occupies no execution slot — the worker takes
that lease when it actually starts the cell. With the gate disarmed this file behaves exactly
as it did before.

Cell ids are namespaced by model slug (``<slug>_<story>_<tier>_<quality>_<condition>``)
so multiple models can share a queue without colliding on ``story_status`` fields
or worker log filenames. ``--missing-only`` skips cells whose result JSON already
exists under ``experiments/results/stories/`` for the target model. ``--interleave``
merges the new cells into the existing queue and round-robins across models so
concurrent workers spread across providers instead of hammering one.
"""

import json
import os
import sys
from collections import deque
from pathlib import Path
from typing import Any

import redis

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.control.admission import (
    AdmissionDenied,
    AdmissionRequest,
    default_controller,
)
from agentic_dynamics.control.model_policy import SUBSCRIPTION_DEFAULT, ensure_model_allowed
from agentic_dynamics.core.admission_context import admission_required
from agentic_dynamics.core.constants import model_slug

# ── Matrix Definition ──────────────────────────────────────────

STORIES = ["task_manager_api", "static_site_gen", "notification_service"]
TIERS = ["tier1_minimal", "tier2_small"]
MODEL = os.environ.get("FINOPS_MODEL", SUBSCRIPTION_DEFAULT)
ensure_model_allowed(MODEL)

GOOD_CONDITIONS = ["clean", "bad_seed", "early_degrade"]
BAD_CONDITIONS = ["clean", "early_degrade"]

REDIS_HOST = "127.0.0.1"
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
QUEUE_KEY = "story_jobs"
STATUS_KEY = "story_status"       # Redis hash: cell_id -> status
RESULTS_KEY = "story_results"     # Redis hash: cell_id -> result path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "experiments" / "results" / "stories"

PROVIDER_PRIORITY = {"deepseek": 0, "anthropic": 1, "openai": 2}

#: How long a queued cell's budget lease stays outstanding. Much longer than the registry's
#: 1-hour default because a queued job legitimately waits for a free worker — a lease that
#: expired while the job was still in the queue would hand its headroom to someone else and
#: leave the job unbudgeted at pick-up time. 24h is the practical drain horizon for a full
#: matrix; past that the sweeper reclaims it and the job is re-filled rather than silently run.
QUEUE_LEASE_TTL_SECONDS = int(os.environ.get("FINOPS_QUEUE_LEASE_TTL", str(24 * 3600)))


def completed_cells(model: str) -> set[str]:
    """Return ``story|tier|quality|condition`` keys already saved for ``model``."""
    completed: set[str] = set()
    if not RESULTS_DIR.is_dir():
        return completed
    for f in RESULTS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("model") != model:
            continue
        story = data.get("story_name")
        if not story:
            continue
        condition = data.get("perturbation_condition") or ""
        if not condition:
            for cond in ("bad_seed", "early_degrade", "clean"):
                if cond in f.name:
                    condition = cond
                    break
        parts = (data.get("codebase_path") or "").split("/")
        tier = parts[-2] if len(parts) >= 2 else "?"
        quality = parts[-1] if len(parts) >= 1 else "?"
        completed.add(f"{story}|{tier}|{quality}|{condition}")
    return completed


def build_cells(model: str = MODEL, missing_only: bool = False) -> list[dict[str, Any]]:
    """Build the full experiment matrix, optionally skipping completed cells."""
    done = completed_cells(model) if missing_only else set()
    slug = model_slug(model)

    cells = []
    for story in STORIES:
        for tier in TIERS:
            for quality in ["good", "bad"]:
                conds = GOOD_CONDITIONS if quality == "good" else BAD_CONDITIONS
                for condition in conds:
                    if f"{story}|{tier}|{quality}|{condition}" in done:
                        continue
                    cells.append({
                        "cell_id": f"{slug}_{story}_{tier}_{quality}_{condition}",
                        "story": story,
                        "tier": tier,
                        "quality": quality,
                        "condition": condition,
                        "model": model,
                    })
    return cells


def _provider(model: str) -> str:
    return model.split("/", 1)[0]


def _spread_order(models: list[str]) -> list[str]:
    """Order model ids so consecutive entries spread across providers."""
    buckets: dict[str, list[str]] = {}
    for m in models:
        buckets.setdefault(_provider(m), []).append(m)
    providers = sorted(buckets, key=lambda p: PROVIDER_PRIORITY.get(p, 99))
    for p in providers:
        buckets[p].sort()
    order: list[str] = []
    idx = {p: 0 for p in providers}
    remaining = sum(len(v) for v in buckets.values())
    while len(order) < remaining:
        for p in providers:
            if idx[p] < len(buckets[p]):
                order.append(buckets[p][idx[p]])
                idx[p] += 1
    return order


def interleave_cells(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Round-robin ``cells`` across models, spreading providers."""
    pools: dict[str, deque] = {}
    for cell in cells:
        pools.setdefault(cell["model"], deque()).append(cell)
    order = _spread_order(list(pools.keys()))
    out: list[dict[str, Any]] = []
    while any(pools.values()):
        for m in order:
            if pools[m]:
                out.append(pools[m].popleft())
    return out


def admit_cells(
    cells: list[dict[str, Any]],
    *,
    controller: Any = None,
    ttl_seconds: int = QUEUE_LEASE_TTL_SECONDS,
) -> list[dict[str, Any]]:
    """Reserve a budget lease per cell and stamp the lease block onto each job.

    Returns the cells with the five ``LEASE_REQUEST_FIELDS`` (plus ``admission_run_id``) added,
    so the worker that later pops a job can see — and re-verify — the budget it was queued
    under. Returns the cells unchanged when the gate is disarmed.

    Batch-atomic on purpose. The loop reserves cell by cell, but a denial anywhere releases
    every lease already taken and re-raises: a queue holding 12 budgeted cells and 6 unbudgeted
    ones is indistinguishable, to a worker, from a queue holding 18 budgeted ones — the failure
    would surface as overspend at drain time rather than as a refusal at fill time. Refusing the
    whole fill keeps the failure where the operator can act on it (raise the cap, or enqueue
    fewer cells).

    Concurrency is deliberately NOT reserved here: a queued job occupies no execution slot. The
    worker takes the concurrency lease when it starts the cell (``scripts/worker.py``), which is
    also where the slot is actually consumed.
    """
    if not admission_required():
        return cells

    ctrl = controller or default_controller()
    admissions = []
    stamped: list[dict[str, Any]] = []
    try:
        for cell in cells:
            request = AdmissionRequest(
                run_id=cell["cell_id"],
                model=cell["model"],
                # Both quarantine handles are the cell id: a story cell's worktree and its
                # result file are both named after it, so phase 4 can find either from a lease.
                worktree_identity=cell["cell_id"],
                result_namespace=f"stories/{cell['cell_id']}",
                enforce_concurrency=False,
                ttl_seconds=ttl_seconds,
                metadata={
                    "source": "enqueue",
                    "story": cell.get("story", ""),
                    "condition": cell.get("condition", ""),
                },
            )
            admission = ctrl.admit(request)
            admissions.append(admission)
            stamped.append({
                **cell,
                **admission.context().to_request_fields(),
                "admission_run_id": admission.run_id,
            })
    except AdmissionDenied:
        # Unwind the whole batch. Best-effort by necessity — the registry may be the thing that
        # failed — and the TTL reclaims anything this misses.
        for admission in admissions:
            try:
                ctrl.release(admission)
            except Exception as exc:  # noqa: BLE001 — never mask the denial with a release error
                print(f"warning: could not release {admission.run_id}: {exc}", file=sys.stderr)
        raise
    return stamped


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    clear = "--clear" in sys.argv
    missing_only = "--missing-only" in sys.argv
    interleave = "--interleave" in sys.argv
    model = MODEL
    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        if idx + 1 < len(sys.argv):
            model = sys.argv[idx + 1]

    cells = build_cells(model=model, missing_only=missing_only)
    total = len(cells)

    # Admission (p2) — every cell's budget is reserved BEFORE it enters the queue. Skipped for
    # --dry-run (a read-only flag must not take real leases) and for --clear (which enqueues
    # nothing). A denial exits non-zero with the reason and leaves the queue untouched.
    if not dry_run and not clear:
        try:
            cells = admit_cells(cells)
        except AdmissionDenied as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            raise SystemExit(2) from exc

    r = None
    if interleave or not dry_run:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

    final_cells = cells
    if interleave:
        existing = [json.loads(c) for c in reversed(r.lrange(QUEUE_KEY, 0, -1))]
        final_cells = interleave_cells(existing + cells)

    if dry_run:
        mode = " (missing-only)" if missing_only else ""
        if interleave:
            print(f"Would interleave {total} new cells into {len(existing)} queued → {len(final_cells)} total:")
            for i, cell in enumerate(final_cells[:15]):
                print(f"  [{i+1}] {cell['model'].split('/')[-1]:20s} {cell['cell_id']}")
            if len(final_cells) > 15:
                print(f"  ... (+{len(final_cells) - 15} more)")
        else:
            print(f"Would enqueue {total} cells (model={model}){mode}:")
            for i, cell in enumerate(cells):
                print(f"  [{i+1}/{total}] {cell['cell_id']}")
        return

    if clear:
        r.delete(QUEUE_KEY)
        r.delete(STATUS_KEY)
        r.delete(RESULTS_KEY)
        print("Queue cleared.")
        return

    if interleave:
        r.delete(QUEUE_KEY)
        for cell in final_cells:
            r.lpush(QUEUE_KEY, json.dumps(cell))
        for cell in cells:
            r.hset(STATUS_KEY, cell["cell_id"], "queued")
        print(f"Interleaved {total} new cells into queue (now {len(final_cells)} total) (model={model})")
    else:
        for cell in cells:
            r.lpush(QUEUE_KEY, json.dumps(cell))
            r.hset(STATUS_KEY, cell["cell_id"], "queued")
        print(f"Enqueued {total} cells into '{QUEUE_KEY}' (model={model})")

    print(f"Status tracker: '{STATUS_KEY}'")
    print()
    print("Start workers with:")
    print("  python scripts/worker.py &")
    print("Monitor progress with:")
    print("  python scripts/monitor.py --watch")


if __name__ == "__main__":
    main()
