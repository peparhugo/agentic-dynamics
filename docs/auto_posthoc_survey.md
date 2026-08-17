# Auto Post-Hoc Wiring Survey

Map of the `execute → analyze → review` handoff and the exact trigger points where
the post-hoc phases can be auto-triggered per worktree, async, without new transport
machinery. All paths are `file:line` against the current tree.

**No code is modified here** — this is a touchpoint map only.

---

## 1. Handoff chain (today)

```
execute                 analyze                review                 finalize
────────                ───────                ──────                 ────────
enqueue.py ──▶ worker.py ──▶ run_story.py      (manual today)          (manual today)
              (BRPOP        writes *.json      enqueue_analysis.py     enqueue_reviews.py
               story_jobs)  into stories/      analysis_worker.py      review_worker.py
                                              (BRPOP analysis_jobs)    (BRPOP review_jobs)
                                                                       finalize_reviews.py
```

Three Redis queues on the **isolated framework instance** (`finops-queue`, DB 1, port 6380):

| Phase | Queue key | Status hash | Producer | Consumer |
|---|---|---|---|---|
| execute | `story_jobs` | `story_status` | `enqueue.py:189/195` | `worker.py:93` |
| analyze | `analysis_jobs` | `analysis_status` | `enqueue_analysis.py:77-78` | `analysis_worker.py:88` |
| review | `review_jobs` | `review_status` | `enqueue_reviews.py:115-116/132-133` | `review_worker.py:114` |

All three use `REDIS_DB = 1` (`worker.py:23`, `analysis_worker.py:35`,
`enqueue_analysis.py:25`, `enqueue_reviews.py:27`, `review_worker.py:33`).

---

## 2. Handoff 1 — execute → analyze

### Trigger point (a): worker.py after `run_story` saves its result

`worker.py` shells out to `run_story.py` (`worker.py:131-145`), which writes the
story result to `experiments/results/stories/{name}_{slug}_{condition}_{story_id}.json`
(`run_story.py:166-170`, `save_story_result` at `run_story.py:170`).

The success branch is the exact auto-enqueue seam:

```
worker.py:159    ok = proc.returncode == 0 and "ERROR" not in proc.stdout
worker.py:160    if ok:
worker.py:161        log(f"[{cell_id}] OK ...")
worker.py:162        _safe_hset(r, STATUS_KEY, cell_id, "done")
worker.py:163        publisher.publish_status("done")
worker.py:164        completed += 1
                 ◀── AUTO-ENQUEUE ANALYSIS JOB HERE
```

**Exact insertion point:** `worker.py:162-164` — immediately after `_safe_hset(..., "done")`
and `publish_status("done")`, before `completed += 1` (or immediately after; the only
requirement is that the result file already exists, which it does once `proc` returned 0).

### What the analysis job must look like

The analysis job shape is defined inline in `enqueue_analysis.build_jobs`:

```
enqueue_analysis.py:46-50
    jobs.append({
        "story_id":    story_id,
        "worktree":    data.get("worktree", ""),
        "result_path": str(f),
    })
```

and consumed by `analysis_worker.py`:

```
analysis_worker.py:110   story_id = job["story_id"]
analysis_worker.py:116   worktree = Path(job.get("worktree", ""))
analysis_worker.py:120   story_result = load_story_result(Path(job["result_path"]))
```

### Gap to close for auto-enqueue

`worker.py` knows the **cell** (`story`, `model`, `tier`, `quality`, `condition`,
`cell_id`) but **not** the generated `story_id` or the worktree path — those are produced
inside `run_story.py` and only persisted in the result JSON. To build the analysis job
from the worker, one of:

1. **Parse `proc.stdout`** — `run_story.py` already prints `Results: {out_path}`
   (`run_story.py:181`); read that path, `json.loads` it, extract `story_id` + `worktree`
   (both are top-level fields of the result: `story.py:399-408`).
2. **Derive the path** — the worker knows `model`, `condition`, `story`, but *not* the
   random `story_id` slug, so the glob/read approach is the reliable one.
3. **Have `run_story.py` emit the fields** — e.g. `FINOPS_RESULT_PATH` on stdout, which
   the worker already captures (`capture_output=True`, `worker.py:141`).

The dedupe check `enqueue_analysis.build_jobs` uses (`skip_existing` → skip if
`analysis_{story_id}.json` exists, `enqueue_analysis.py:44`) must also be applied at the
auto-enqueue site so re-runs and `--missing-only` enqueues don't double-fire.

---

## 3. Handoff 2 — analyze → review

### Trigger point (b): analysis_worker.py after analysis completes

`analysis_worker.py` writes `analysis_{story_id}.json` and marks the status done:

```
analysis_worker.py:135   out_path = ANALYSIS_DIR / f"analysis_{story_id}.json"
analysis_worker.py:136   out_path.parent.mkdir(...)
analysis_worker.py:137   out_path.write_text(json.dumps(analysis_dict, indent=2))
analysis_worker.py:139   _safe_hset(r, STATUS_KEY, story_id, "done")
analysis_worker.py:140   completed += 1
analysis_worker.py:141   log(f"[{story_id}] OK ...")
                    ◀── AUTO-ENQUEUE REVIEW JOBS HERE
```

**Exact insertion point:** `analysis_worker.py:139-141` — after the analysis JSON is
written (`:137`) and the status flipped to `"done"` (`:139`). At this point the worker
already holds everything review needs:

```
analysis_worker.py:116   worktree = Path(job.get("worktree", ""))
analysis_worker.py:120   story_result = load_story_result(...)   # .story_name, .story_id, .model
```

### What the review jobs must look like

Defined inline in `enqueue_reviews.py` — one commit job per session commit, plus a
story-level job:

```
enqueue_reviews.py:104-113   # per-commit job
    {
        "job_id":          f"{story.story_id}_{sn}",
        "story_name":      story.story_name,
        "story_id":        story.story_id,
        "worktree":        str(worktree),
        "commit_hash":     ch,
        "commit_message":  cm,
        "session_number":  sn,
        "model":           MODEL,
    }

enqueue_reviews.py:120-130  # story-level job
    {
        "job_id":          f"{story.story_id}_story",
        ...,
        "commit_hash":     "",
        "session_number":  0,
        "job_type":        "story_review",
    }
```

and consumed by `review_worker.py`:

```
review_worker.py:143   job_id = job["job_id"]
review_worker.py:144   story_id = job["story_id"]
review_worker.py:145   worktree = Path(job["worktree"])
review_worker.py:159   if job.get("job_type") == "story_review": ...
review_worker.py:165   review_commit(worktree, job["commit_hash"], ...)
```

### Commit discovery is the reusable dependency

The per-commit jobs come from `_get_worktree_commits(worktree)`:

```
enqueue_reviews.py:36-57   git log --reverse --format=%H|%s → [(hash, msg, session_num), ...]
```

`analysis_worker.py` has the same `worktree` in hand, so the commit-discovery logic is the
piece to reuse for the auto-enqueue site. Note `analysis_worker.py` already runs
`analyze_story_worktree(worktree, run_sonar=True)` (`analysis_worker.py:121`), which
itself walks the same `git log` internally (`commit_analysis.py:604`).

### Gap to close for auto-enqueue

- `analysis_worker.py` does not currently import `review` or any review-job builder; it
  only imports from `instrument.commit_analysis` (`analysis_worker.py:26-30`).
- The dedupe guard in `enqueue_reviews.py:93-101` (skip if `review_{story_id}.json` already
  has ≥ N commit reviews + story review) must be replicated at the auto-enqueue site.
- `finalize_reviews.py` is still a separate, idempotent, manual step (`finalize_reviews.py:1-8`)
  that merges per-session files into the aggregate `review_{story_id}.json`. Auto-triggering
  *finalize* is a second-level concern (it is safe to run anytime, `finalize_reviews.py:7`),
  but the merge itself is not a queued job today.

---

## 4. Shared helper to extract — requirement (c)

Today the job shape is **triplicated**: built inline in `enqueue_analysis.py` /
`enqueue_reviews.py`, and parsed inline in `analysis_worker.py` / `review_worker.py`.
Auto-enqueue requires the producer and consumer to agree on the exact dict keys and the
queue/status key names. Extract one shared module (e.g. `scripts/posthoc_jobs.py` or
`src/instrument/posthoc.py`) holding:

### 4.1 The two job builders

```
build_analysis_job(result_path: Path, data: dict) -> dict
    # ← move enqueue_analysis.py:46-50 here (story_id, worktree, result_path)

build_review_jobs(story_id, story_name, worktree, model,
                  commits: list[tuple[str,str,int]]) -> list[dict]
    # ← move enqueue_reviews.py:104-134 here (per-commit + story_review dicts)

worktree_commits(worktree: Path) -> list[tuple[str,str,int]]
    # ← move enqueue_reviews.py:36-57 here (git log → [(hash, msg, session_num)])
```

### 4.2 The enqueue primitive (single canonical write path)

Both producers must share one "push a job" routine so the `lpush` + `hset` pair and the
queue/status key names are never re-derived:

```
enqueue_job(r, queue_key, status_key, job: dict, status_field: str) -> None
    r.lpush(queue_key, json.dumps(job))
    r.hset(status_key, status_field, "queued")
    # ← consolidate enqueue_analysis.py:77-78 and enqueue_reviews.py:115-116/132-133
```

### 4.3 Shared queue/status constants

| Constant | Value | Defined at |
|---|---|---|
| `ANALYSIS_QUEUE` / `ANALYSIS_STATUS` | `analysis_jobs` / `analysis_status` | `enqueue_analysis.py:26-27`, `analysis_worker.py:36-37` |
| `REVIEW_QUEUE` / `REVIEW_STATUS` | `review_jobs` / `review_status` | `enqueue_reviews.py:28-29`, `review_worker.py:34-35` |
| `REDIS_DB` | `1` (port 6380) | all five scripts |

`enqueue_analysis.py` and `enqueue_reviews.py` already hardcode the same DB/port, so a
single shared constants block eliminates the drift risk (note the current inconsistency:
`enqueue_reviews.py:25` and `review_worker.py:31` hardcode host `"127.0.0.1"` while
`enqueue_analysis.py:23` and `analysis_worker.py:33` honor `FINOPS_REDIS_HOST`).

---

## 5. Touchpoint map (summary)

| # | Touchpoint | File:line | Action to wire |
|---|---|---|---|
| E1 | result saved | `run_story.py:169-170` | (source of truth for story_id/worktree) |
| E2 | **auto-enqueue analysis** | `worker.py:162-164` | after status `done`; build analysis job from `proc.stdout` result path |
| A1 | analysis job built | `enqueue_analysis.py:46-50` | extract to `build_analysis_job` |
| A2 | analysis job consumed | `analysis_worker.py:110-120` | unchanged if shape is shared |
| A3 | analysis output written | `analysis_worker.py:135-137` | prerequisite for review |
| A4 | **auto-enqueue review** | `analysis_worker.py:139-141` | after status `done`; build review jobs from in-hand `worktree` + commits |
| R1 | commits discovered | `enqueue_reviews.py:36-57` | extract to `worktree_commits` |
| R2 | review jobs built | `enqueue_reviews.py:104-134` | extract to `build_review_jobs` |
| R3 | review job consumed | `review_worker.py:143-146` | unchanged if shape is shared |
| F1 | aggregate merge | `finalize_reviews.py:68-84` | idempotent; still manual (or piggyback on a later step) |

## 6. Existing async handoff (reference pattern)

`trigger_reviews.py` already demonstrates the drain-then-enqueue pattern that the worker
auto-triggers replace:

```
trigger_reviews.py:39-43   _analysis_done(): queue empty + no queued/running status
trigger_reviews.py:52-53    poll until analysis drains
trigger_reviews.py:62        subprocess enqueue_reviews.py
trigger_reviews.py:66-74     spawn N detached review_worker.py
```

The auto-trigger wires the same enqueue calls **into the worker completion paths**
(handoff 1 at `worker.py:162-164`, handoff 2 at `analysis_worker.py:139-141`) instead of a
separate drain-monitor process, so analyze and review fire per worktree as soon as their
upstream phase lands — no `trigger_reviews.py` poll loop needed.
