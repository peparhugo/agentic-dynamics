---
name: review
description: Run the commit/story review pipeline across 5 scripts (review_all.py, review_stories.py, trigger_reviews.py, enqueue_reviews.py, finalize_reviews.py) with 3 different invocation shapes (sync ThreadPoolExecutor, backgrounded Redis workers, plain run). Use when asked to review experiment commits/stories, trigger review workers, or finalize per-session review files into aggregates.
disable-model-invocation: false
user-invocable: false
argument-hint: ""
---

# Review Skill — Commit/Story Review Pipeline

5 scripts, 3 distinct invocation shapes. Pick the path that matches the situation:

- **No Redis / small batch → `review_all.py`** (synchronous, `ThreadPoolExecutor`, blocks
  until done).
- **No Redis / batch commit+story review → `review_stories.py`** (synchronous, no queue).
- **Redis available / want backgrounded parallel review workers → `trigger_reviews.py`**
  (two-stage: blocking enqueue, then runs `review_all.py`).
- **After any Redis-based review run → `finalize_reviews.py`** to merge per-session review
  files into aggregates.

## `review_all.py` — synchronous, all-in-one

Confirmed `scripts/review_all.py:119-122`:

```
--workers INT    default: 6
--story STR      default: "" — substring filter on story name
--dry-run        flag
```

```bash
python3 scripts/review_all.py                              # all stories, 6 workers, ThreadPoolExecutor
python3 scripts/review_all.py --workers 3 --story task_manager --dry-run
```

## `review_stories.py` — synchronous batch, no Redis

Manual parse, confirmed `scripts/review_stories.py:20`:

```
--dry-run   in sys.argv
```

```bash
python3 scripts/review_stories.py [--dry-run]   # batch commit + story review, no Redis
```

## `trigger_reviews.py` — two-stage, Redis-backed

Zero CLI flags (confirmed: no `add_argument` anywhere in the file). Reads `REVIEW_WORKERS`
env var, default `4` (`scripts/trigger_reviews.py:26`).

**Two-stage behavior, not obvious from the flag list alone**
(`scripts/trigger_reviews.py:60-77`):
1. Polls `analysis_jobs`/`analysis_status` Redis keys until drained.
2. Runs `enqueue_reviews.py` as a **blocking** subprocess (waits for it to finish filling
   `review_jobs`).
3. Then runs `review_all.py` **synchronously** (the review runner; `review_worker.py` was
   retired in Stage 3).

```bash
python3 scripts/trigger_reviews.py              # default 4 review workers, backgrounded
REVIEW_WORKERS=6 python3 scripts/trigger_reviews.py &
```

Because step 3 detaches workers, `trigger_reviews.py` returning does not mean review is
done — check queue drain via the `queue` skill's `monitor.py` (against `review_jobs`), or
run `finalize_reviews.py` once workers finish.

## `enqueue_reviews.py` — populate the review queue only

Manual parse, confirmed `scripts/enqueue_reviews.py:61`:

```
--dry-run   in sys.argv
```

```bash
python3 scripts/enqueue_reviews.py [--dry-run]   # populate review_jobs queue
```

Use `enqueue_reviews.py` directly when you want to fill the queue and run `review_all.py`
yourself (the retired `review_worker.py` was the Redis worker).

## `finalize_reviews.py` — merge results

Zero CLI flags (confirmed: no `add_argument`/`sys.argv` parsing in the file).

```bash
python3 scripts/finalize_reviews.py              # merge per-session review files into aggregates
```

Run this after any Redis-based review pass (`trigger_reviews.py` or manual
`enqueue_reviews.py` + workers) finishes draining, to produce the aggregate review output
that downstream analysis (the `analyze` skill) consumes.

## Ordering summary

```
review_all.py            — standalone, synchronous, no ordering
review_stories.py        — standalone, synchronous, no ordering
enqueue_reviews.py → review_all.py (synchronous) → finalize_reviews.py
trigger_reviews.py  (wraps the enqueue step + runs review_all.py) → finalize_reviews.py
```

## Common gotchas

- `trigger_reviews.py`'s worker spawn is detached (`nohup`) — the script returning is not
  the same as review being complete. Check the queue or wait before running
  `finalize_reviews.py`.
- `review_all.py`/`review_stories.py` don't touch Redis at all — don't mix them with the
  Redis-backed `enqueue_reviews.py`/`trigger_reviews.py` path in the same run.
- Always `--dry-run` first on any of the 3 scripts that support it before a real run
  against unfamiliar data.
