"""Queue re-interleave — round-robin a Redis story queue across providers.

Shared by ``scripts/reinterleave_queue.py`` (the CLI) and the Control Room's
``POST /api/queue/reinterleave`` endpoint, so the two surfaces can never drift.

Consumption order: ``enqueue.py`` pushes with ``LPUSH`` (head) and ``worker.py``
pops with ``BRPOP`` (tail), so workers pick jobs in the *reverse* of ``lrange``.
Every ordering decision here is expressed in consumption order (the order a
worker would pick), then translated back when writing.
"""

from __future__ import annotations

import json
import os
from collections import Counter, deque
from typing import Any

import redis

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
QUEUE_KEY = "story_jobs"


def connect() -> redis.Redis:
    """Return a decoded-response Redis client for the framework queue."""
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


def provider_of(cell: dict[str, Any]) -> str:
    """Return the provider for a job cell (the part before ``/`` in model id).

    Example: ``"openai/gpt-5.6-luna"`` -> ``"openai"``.
    """
    return cell["model"].split("/", 1)[0]


def reinterleave_cells(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reorder ``cells`` so consecutive elements have different providers.

    Strategy — *largest-remainder round-robin*:
      1. Group cells by provider, preserving each group's first-appearance
         order; provider iteration order is also first-appearance order.
      2. At every step pick the provider with the most remaining cells that is
         not the one picked immediately before (falling back to *any* remaining
         provider only when a perfect interleave is impossible).
      3. Pop one cell from that provider's queue.

    This is a round-robin with load balancing: it cycles across providers but
    keeps the heaviest provider from tail-end runs of same-provider cells.

    Guarantee: consecutive cells always differ in provider, *iff* a perfect
    interleave is feasible, i.e. ``2 * max(count) <= total + 1``. If that
    condition fails the reorder is impossible and a ``ValueError`` is raised
    rather than silently emitting adjacent same-provider jobs.

    Job preservation: every input cell appears exactly once in the output (the
    same cell objects are merely re-queued), so no job is lost or duplicated.
    """
    if not cells:
        return []

    counts = Counter(provider_of(c) for c in cells)
    total = len(cells)
    max_count = max(counts.values())

    # Feasibility: the busiest provider must not hold more than half the jobs
    # (allowing for the first/last slot sharing). Otherwise no ordering can keep
    # it from touching itself.
    if 2 * max_count > total + 1:
        offender = max(counts, key=lambda p: counts[p])
        raise ValueError(
            f"Reinterleave impossible: provider {offender!r} has {counts[offender]} "
            f"of {total} cells; need at most {(total + 1) // 2}. "
            "Reduce the imbalance before reinterleaving."
        )

    groups: dict[str, deque] = {}
    provider_order: list[str] = []
    for cell in cells:
        provider = provider_of(cell)
        if provider not in groups:
            groups[provider] = deque()
            provider_order.append(provider)
        groups[provider].append(cell)

    remaining = {p: len(q) for p, q in groups.items()}
    out: list[dict[str, Any]] = []
    last: str | None = None

    while sum(remaining.values()) > 0:
        candidates = [p for p in provider_order if remaining[p] > 0 and p != last]
        if not candidates:
            # Only the previous provider still has cells left — but that is
            # unreachable here (feasibility enforced above); defensive pick.
            candidates = [p for p in provider_order if remaining[p] > 0]
        pick = max(candidates, key=lambda p: remaining[p])
        out.append(groups[pick].popleft())
        remaining[pick] -= 1
        last = pick

    return out


def read_queue(r: redis.Redis) -> list[dict[str, Any]]:
    """Read queued cells in consumption order (tail-first)."""
    raw = r.lrange(QUEUE_KEY, 0, -1)
    cells = [json.loads(c) for c in raw]
    # BRPOP pops from the tail; lrange runs head -> tail, so consumption order
    # is the reverse.
    return list(reversed(cells))


def write_queue(r: redis.Redis, target_order: list[dict[str, Any]]) -> None:
    """Atomically replace the queue so consumption order == ``target_order``.

    ``target_order`` is the consumption order, but Redis stores the list
    head-first. To make BRPOP yield ``target_order`` we must RPUSH its reverse.
    DELETE + RPUSH run in one pipeline so the queue is never observed in a
    partially-rewritten state.
    """
    pipe = r.pipeline(transaction=True)
    pipe.delete(QUEUE_KEY)
    for cell in reversed(target_order):
        pipe.rpush(QUEUE_KEY, json.dumps(cell))
    pipe.execute()


def provider_summary(cells: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize a cell list by provider for the reinterleave report.

    Counts per provider, the consumption order of provider labels, and the
    longest run of consecutive same-provider cells.
    """
    providers = [provider_of(c) for c in cells]
    longest = current = 1 if providers else 0
    for previous, next_ in zip(providers, providers[1:], strict=False):
        current = current + 1 if previous == next_ else 1
        longest = max(longest, current)
    return {
        "by_provider": dict(Counter(providers)),
        "order": providers,
        "longest_provider_run": longest,
    }
