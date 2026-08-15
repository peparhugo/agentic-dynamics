"""Re-interleave the story queue round-robin across providers.

Reads every job in ``story_jobs`` (Redis on ``FINOPS_REDIS_PORT``, db
``FINOPS_REDIS_DB``), reorders it so no two consecutive jobs share a provider,
and rewrites the queue atomically (DELETE + RPUSH in a single pipeline).

Usage:
    python scripts/reinterleave_queue.py            # reorder in place
    python scripts/reinterleave_queue.py --dry-run  # preview without writing
    python scripts/reinterleave_queue.py --json     # machine-readable report

Consumption order: ``worker.py`` pops jobs with BRPOP, i.e. from the *tail* of
the list. ``enqueue.py`` pushes with LPUSH (head). So ``lrange(0, -1)`` runs
head -> tail, and the order in which workers will actually pick jobs is the
*reverse* of ``lrange``. Every ordering decision in this script is expressed in
consumption order (the order a worker would pick), then translated back when
writing.
"""

import json
import os
import sys
from collections import Counter, deque
from pathlib import Path
from typing import Any, Callable, Optional

import redis

REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))
REDIS_DB = int(os.environ.get("FINOPS_REDIS_DB", "1"))
QUEUE_KEY = "story_jobs"


def _provider_of(cell: dict[str, Any]) -> str:
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

    counts = Counter(_provider_of(c) for c in cells)
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

    # Group by provider, preserving within-group order and first-appearance
    # provider order.
    groups: dict[str, deque] = {}
    provider_order: list[str] = []
    for cell in cells:
        provider = _provider_of(cell)
        if provider not in groups:
            groups[provider] = deque()
            provider_order.append(provider)
        groups[provider].append(cell)

    remaining = {p: len(q) for p, q in groups.items()}
    out: list[dict[str, Any]] = []
    last: Optional[str] = None

    # Round-robin with largest-remainder priority: prefer the busiest provider
    # that differs from the previous pick, so the final tail never degrades into
    # a long same-provider run.
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


def _read_queue(r: redis.Redis) -> list[dict[str, Any]]:
    """Read queued cells in consumption order (tail-first)."""
    raw = r.lrange(QUEUE_KEY, 0, -1)
    cells = [json.loads(c) for c in raw]
    # BRPOP pops from the tail; lrange runs head -> tail, so consumption order
    # is the reverse. This matches how enqueue.py reads the queue.
    return list(reversed(cells))


def _write_queue(r: redis.Redis, target_order: list[dict[str, Any]]) -> None:
    """Atomically replace the queue so consumption order == ``target_order``.

    ``target_order`` is the consumption order, but Redis stores the list
    head-first. To make BRPOP yield ``target_order`` we must RPUSH its reverse
    (equivalently LPUSH it in order). DELETE + RPUSH run in one pipeline so the
    queue is never observed in a partially-rewritten state.
    """
    pipe = r.pipeline(transaction=True)
    pipe.delete(QUEUE_KEY)
    for cell in reversed(target_order):
        pipe.rpush(QUEUE_KEY, json.dumps(cell))
    pipe.execute()


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    json_out = "--json" in sys.argv

    r = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
    )
    before = _read_queue(r)
    reordered = reinterleave_cells(before)

    if not dry_run:
        _write_queue(r, reordered)

    before_providers = [_provider_of(c) for c in before]
    after_providers = [_provider_of(c) for c in reordered]

    def _runs(providers: list[str]) -> int:
        """Longest run of consecutive identical providers."""
        best = cur = 1 if providers else 0
        for a, b in zip(providers, providers[1:]):
            cur = cur + 1 if a == b else 1
            best = max(best, cur)
        return best

    report = {
        "count": len(before),
        "before_longest_provider_run": _runs(before_providers),
        "after_longest_provider_run": _runs(after_providers),
        "before_by_provider": dict(Counter(before_providers)),
        "after_by_provider": dict(Counter(after_providers)),
        "before_provider_order": before_providers,
        "after_provider_order": after_providers,
        "dry_run": dry_run,
    }

    if json_out:
        print(json.dumps(report, indent=2))
        return

    print(f"Reinterleaved {report['count']} jobs "
          f"({'dry-run, nothing written' if dry_run else 'written to queue'})")
    print(f"  longest same-provider run: "
          f"{report['before_longest_provider_run']} -> {report['after_longest_provider_run']}")
    print(f"  before: {report['before_by_provider']}")
    print(f"  after:  {report['after_by_provider']}")
    print(f"  order:  {' '.join(after_providers[:20])}{' ...' if len(after_providers) > 20 else ''}")


if __name__ == "__main__":
    main()
