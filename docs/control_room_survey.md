---
status: accepted
---
# Control Room Queue Surface — Touchpoint Map

**Purpose.** Locate every place the *story* queue is read and rendered, and mark exactly
where the two post-hoc queues (`analysis_jobs`/`analysis_status`, `review_jobs`/`review_status`)
are absent and would need to slot in to form the three-stage pipeline view
(execute → analyze → review).

This is a **read-only survey**. No code is modified.

---

## 0. The three Redis key pairs (all on 6380, db 1)

| Stage | Queue (list) | Status (hash) | Status hash *field* key | Status values written |
|---|---|---|---|---|
| execute | `story_jobs` | `story_status` | `cell_id` (`<model>_<story>_<tier>_<quality>_<condition>`) | `queued`, `running`, `done`, `failed`, `timeout` |
| analyze | `analysis_jobs` | `analysis_status` | `story_id` | `queued`, `running`, `done`, `failed` |
| review | `review_jobs` | `review_status` | `job_id` (`<story_id>_S<n>` or `<story_id>_story`) | `queued`, `running`, `done`, `failed`, `retry_1`, `retry_2`, `retry_3` |

References:
- `scripts/enqueue.py:43-44` (`QUEUE_KEY`, `STATUS_KEY`); `scripts/worker.py:24-25` (writes
  `running`/`done`/`failed`/`timeout` at `worker.py:123,162,167,177,183`).
- `scripts/enqueue_analysis.py:26-27`; `scripts/analysis_worker.py:36-37` (writes
  `running`/`done`/`failed` at `analysis_worker.py:111,139,143`).
- `scripts/enqueue_reviews.py:28-29`; `scripts/review_worker.py:34-35` (writes
  `running`/`done`/`failed` and `retry_N` at `review_worker.py:97,156,174,181`).
- `pipeline.py:62-65` and `plan.py:40-43` mirror the same four-key constants for the
  orchestrator phases.

**Two things that make the post-hoc stages structurally different from the story stage:**

1. **No results hash.** The story stage has `story_results` (`live.py`/`monitor.py:23`),
   which drives `results_saved`. The analyze/review stages have *no* Redis results hash —
   their outputs are filesystem artifacts (`experiments/results/analysis/analysis_<id>.json`,
   `experiments/results/reviews/review_<id>_S<n>.json`). A `results_saved` analog for these
   stages must count files, not a Redis hash.
2. **No pub/sub channel.** Only the story stage publishes to the `status` channel
   (`live.py:77,91`). `analysis_worker.py` and `review_worker.py` only `hset` and never
   `publish`, so there is **no SSE stream** for post-hoc transitions — the Control Room can
   only see them via the 5-second `/api/matrix` poll.

---

## 1. `admin/server.py` — where the story queue is read/rendered

| Line | What it is | Post-hoc slot |
|---|---|---|
| `60` | `STATUS_KEY` imported from `instrument.live` (resolves to `story_status`) | Import or define `ANALYSIS_QUEUE/STATUS`, `REVIEW_QUEUE/STATUS` beside it |
| `103` | `QUEUE_KEY = "story_jobs"` | Add `ANALYSIS_QUEUE_KEY`, `REVIEW_QUEUE_KEY` |
| `104` | `RESULTS_KEY = "story_results"` | (no results-hash analog for analyze/review — see §0) |
| `662-742` | `_retained_telemetry()` — reads `events_log:<cell>` for **story** cell ids only | Post-hoc jobs have no `events_log:*` entries; the three-stage view must not feed their ids into this function |
| `745-783` | `GET /api/matrix` (`api_matrix`) — **the single read point**. `r.llen(QUEUE_KEY)` (`750`), `r.hgetall(STATUS_KEY)` (`751`), `r.hgetall(RESULTS_KEY)` (`752`), then builds `response` with `total/remaining_in_queue/queued/running/done/failed/timeout/completed/results_saved/cells` (`760-771`) | **Primary insertion point.** Read `llen("analysis_jobs")`, `hgetall("analysis_status")`, `llen("review_jobs")`, `hgetall("review_status")` here and emit a `stages` (or `pipeline`) block alongside the existing flat fields, e.g. `{execute:{…}, analyze:{…}, review:{…}}` |
| `786-809` | `GET /api/status` (`api_status`) — SSE subscribing only to `STATUS_CHANNEL` (`792`) | Post-hoc workers do not publish (see §0.2); nothing to subscribe to unless the workers are later instrumented to publish |
| `887-907` | `POST /api/experiments` — enqueue/clear runs `scripts/enqueue.py` only (`897`) | Out of scope for the view; the analyze/review enqueuers are not wired here |
| `910-918+` | `POST /api/queue/reinterleave` — reorders `story_jobs` only | Out of scope |

The matrix JSON shape consumed by the client is produced **only** at `api_matrix`
(`server.py:760-771`) — that is the single server-side choke point for the new stages.

---

## 2. `admin/static/` — where the story matrix is rendered

### `index.html`

| Line | What it is | Post-hoc slot |
|---|---|---|
| `42-130` | `#fleet` pane — the whole matrix surface | Three-stage headings/counts live here (or in a new sibling pane) |
| `47` | `#fleet-total` — "N CELLS" count | Add `#analyze-total`, `#review-total` (or per-stage count nodes) |
| `51-61` | `.fleet-controls` — filter chips (`data-filter` all/running/risk) + `#cell-search` | Decide whether stage filter/search applies to post-hoc rows |
| `62-66` | `#fleet-grid` — the card grid | Post-hoc stage cards (or a parallel grid) render here |
| `67` | `#fleet-counts` — status-count footer | Add analyze/review count lines |
| `37` | `#running-count` in the command rail (execution running) | Optionally split into per-stage running counts |
| `366-373` | Queue actions (enqueue/clear) — execution only | Out of scope |

### `app.js`

| Line | What it is | Post-hoc slot |
|---|---|---|
| `24-31` | `STATUS_SYMBOLS` (queued/running/done/failed/timeout/unknown) | Add a `retry` symbol or map `retry_N` → running |
| `33-97` | `state` — `cells` (`34`) and `telemetry` (`36`) are the **only** queue state | Add `state.analysis`, `state.review` (or a `state.stages` object) |
| `155-159` | `statusCounts()` — counts over `state.cells` only | Extend to count analysis/review statuses |
| `170-198` | `renderRail()` — spend/tokens/running-count from `state.telemetry` | Post-hoc stages have no cost telemetry; leave rail, or add stage counts |
| `292-364` | `renderFleet()` — builds the card grid from `state.cells` (`305`), empty states (`313-317`), status cards (`319-347`), count footer (`357-362`) | **Primary insertion point** for rendering the analyze/review stages |
| `1207-1247` | `loadMatrix()` — `fetch("/api/matrix")` (`1213`); `data.cells → state.cells` (`1222-1223`); `data.telemetry → state.telemetry` (`1224-1226`); auto-select running cell (`1234-1237`) | **Primary insertion point** for parsing the new `stages`/`pipeline` block from the response |
| `1302-1331` | `connectStatusStream()` — `EventSource("/api/status")` (`1304`); `onmessage` mutates `state.cells` (`1313-1317`) | No post-hoc stream exists; status overrides only make sense for the story stage |

### `control-room-core.js`

| Line | What it is | Post-hoc slot |
|---|---|---|
| `10-11` | `TERMINAL_STATUSES` / `STATUS_ORDER` (running/failed/timeout/queued/done/unknown) | Add `retry` (or fold `retry_N` into `running`) |
| `19-22` | `normalizeStatus()` — maps arbitrary producer strings into the finite vocabulary | Must be taught `retry_1/2/3` (review worker emits them, `review_worker.py:97`) |
| `253-258` | `sortCellIds()` — urgency sort over `cells` | Reuse or parallelize for post-hoc id ordering |

---

## 3. `scripts/monitor.py` — where the story status is surfaced (CLI + machine)

| Line | What it is | Post-hoc slot |
|---|---|---|
| `21-23` | `QUEUE_KEY = "story_jobs"`, `STATUS_KEY = "story_status"`, `RESULTS_KEY = "story_results"` | Add `ANALYSIS_QUEUE/STATUS`, `REVIEW_QUEUE/STATUS` |
| `42-78` | `get_status()` — `llen(QUEUE_KEY)` (`44`), `hgetall(STATUS_KEY)` (`45`), `hgetall(RESULTS_KEY)` (`46`); builds counts (`48-49`) and `by_model/by_story/by_condition/by_tier` (`52-62`); returns the flat dict (`64-78`) | **Primary insertion point.** Read the two extra queue/status pairs and emit a `stages` structure (or three sibling dicts) |
| `81-110` | `print_status()` — human-readable: progress bar (`93-95`), counts (`100-101`), `by_*` lines (`105-110`) | Add analyze/review count lines + breakdowns |
| `113-140` | `main()` — `--json` prints `json.dumps(status)` (`128-130`); `--clear` deletes the story keys only (`120-125`) | `--json` gains the stages; `--clear` should also clear the analysis/review keys (or document why not) |

`--json` is the **machine-readable canonical** consumed by the agent tools below; any
stages added here automatically surface to those tools.

---

## 4. Agent tools (passthrough consumers — no change needed, but they inherit the change)

| File | What it is |
|---|---|
| `.opencode/tools/dashboard.ts:17` | Runs `python3 scripts/monitor.py --json` — returns raw stdout unchanged |
| `.opencode/tools/monitor.ts:17` | Runs `python3 scripts/monitor.py` (human-readable) — returns raw stdout unchanged |

Both are thin wrappers around `monitor.py`; extending `monitor.py` extends these for free.
No edits required.

---

## 5. Producer/writer side (context — where statuses originate)

| File | What it writes |
|---|---|
| `src/instrument/live.py:23-24` | `STATUS_KEY = "story_status"`, `STATUS_CHANNEL = "status"`; `set_status()` (`81-91`) does `hset` **and** `publish` |
| `scripts/worker.py:123,162,167,177,183` | story status transitions (hset + publish) |
| `scripts/enqueue.py:44` | seeds `story_status[cell_id] = "queued"` |
| `scripts/analysis_worker.py:111,139,143` | hset only (no publish) |
| `scripts/review_worker.py:97,156,174,181` | hset only (no publish); `retry_N` values |
| `scripts/trigger_reviews.py:26-27` | polls `analysis_jobs`/`analysis_status` then hands off to reviews |

**Implication for the survey's "slot-in" plan:** a live three-stage view is limited to
poll-driven updates from `/api/matrix` (5 s, `app.js:16`) unless `analysis_worker.py` and
`review_worker.py` are later instrumented to publish to their own channels.

---

## 6. Tests that will need updating

### `tests/test_admin_server.py` (WILL need changes)

- `FakeRedis.llen` (`44-46`) asserts `key == "story_jobs"` — will **fail** once
  `/api/matrix` calls `llen` on `analysis_jobs`/`review_jobs`.
- `FakeRedis.hgetall` (`48-52`) asserts keys are only `story_status` or `story_results` —
  will **fail** once `analysis_status`/`review_status` are read.
- `test_matrix_preserves_legacy_fields_and_adds_retained_telemetry` (`143-185`) asserts the
  exact legacy field set (`163-177`) — must be extended (or a new test added) to assert the
  new `stages` block while preserving the flat legacy fields.
- `test_matrix_redis_failure_keeps_existing_503_contract` (`211-218`) asserts the 503 body
  is `{"error", "cells"}` — update if the error shape grows stage keys.
- `QueueRedis.lrange` (`115-119`) special-cases `story_jobs` — unaffected unless
  reinterleave expands.
- The `FakeRedis`/`FakePipeline` fixtures (both classes) will need `analysis_*`/`review_*`
  seeding support.

### `tests/test_admin_frontend.py` (WILL need changes)

- `test_control_room_shell_exposes_all_required_operational_regions` (`14-31`) asserts the
  set of required DOM ids — add the new stage ids once `index.html` gains them.
- `test_client_keeps_one_status_source_and_replaces_selected_source` (`34-45`) is
  stream-specific; unaffected unless a new SSE endpoint is added.
- `test_client_bounds_transcript_and_preserves_empty_error_states` (`48-62`) — add the
  empty-state strings for the new analyze/review stages.

### No monitor test exists

`ls tests/ | grep -i monitor` → none. There is no unit test for `monitor.py`; any `--json`
shape change is currently unverified by pytest (the agent tools only echo stdout).

---

## 7. Summary of the three-stage insertion points

| Surface | Execute (story) — today | Analyze — slot in | Review — slot in |
|---|---|---|---|
| `admin/server.py` | `api_matrix` reads `story_jobs`/`story_status`/`story_results` (`750-752`) | `llen("analysis_jobs")` + `hgetall("analysis_status")` in `api_matrix` | `llen("review_jobs")` + `hgetall("review_status")` in `api_matrix` |
| `admin/static/app.js` | `loadMatrix` (`1213-1226`) → `renderFleet` (`292-364`) | parse `stages.analyze` → render analyze cards/counts | parse `stages.review` → render review cards/counts |
| `admin/static/index.html` | `#fleet-grid` (`62`), `#fleet-counts` (`67`) | new analyze section/counts | new review section/counts |
| `admin/static/control-room-core.js` | `normalizeStatus`/`STATUS_ORDER` (`10-22`) | reuse (statuses are a subset) | add `retry_N` handling (`review_worker.py:97`) |
| `scripts/monitor.py` | `get_status` (`42-78`) → `print_status` (`81-110`) → `--json` (`128-130`) | add analyze reads + breakdown | add review reads + breakdown |

**Two non-negotiable deltas for the implementer:** (1) analyze/review have *no* results hash
and *no* pub/sub channel (§0), so `results_saved` must become a filesystem count and the view
will be poll-only; (2) review statuses include `retry_1..3`, which the client's
`normalizeStatus` does not yet know.
