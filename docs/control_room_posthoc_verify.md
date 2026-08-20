---
status: accepted
---
# Control Room Post-Hoc Visibility — Verification Report

**Feature.** Surface the analysis + review queues in the Control Room matrix and
`monitor.py` as a three-stage pipeline view (execute → analyze → review).

**Prior phases.** survey (`docs/control_room_survey.md`) — ok; implement — ok.

**Status.** All checks **PASS**.

---

## 1. Tests added / extended

| File | Change | New coverage |
|---|---|---|
| `tests/test_admin_server.py` | Extended `FakeRedis` (`llen`/`hgetall` now dispatch on all six keys, lines 34-64) + 3 new tests | `test_matrix_surfaces_three_stage_pipeline` (227), `test_matrix_posthoc_queues_report_remaining_and_empty_stages` (263), `test_matrix_review_retry_folds_multiple_into_running` (293) |
| `tests/test_admin_frontend.py` | 1 new test | `test_pipeline_stages_surface_three_stage_view` (167) |
| `tests/test_monitor.py` | **New file** (6 tests) | `get_status` stages, retry folding, empty stages, `print_status` stage lines + retry, `--clear` drops all six keys |

---

## 2. Verification checks

| # | Check | Result |
|---|---|---|
| 1 | `/api/matrix` emits `stages` with `execute`/`analyze`/`review` | PASS |
| 2 | Legacy flat fields (`total`, `queued`, `running`, `done`, `failed`, `timeout`, `completed`, `results_saved`, `cells`) unchanged | PASS |
| 3 | Analyze stage reports `results_saved: null` (no results hash) | PASS |
| 4 | Review stage folds `retry_N` into `running` and reports a separate `retry` count | PASS |
| 5 | Empty post-hoc stages still render (zero counts, `cells: {}`, queue length surfaced) | PASS |
| 6 | Redis failure keeps the existing 503 `{error, cells}` contract | PASS |
| 7 | Frontend shell exposes `#pipeline-stages` with EXECUTE / ANALYZE / REVIEW | PASS |
| 8 | Client parses `state.stages` and calls `renderPipelineStages()` | PASS |
| 9 | `normalizeStatus` recognizes the review worker's `retry_*` statuses | PASS |
| 10 | `monitor.py --json` (`get_status`) returns the `stages` block alongside legacy fields | PASS |
| 11 | `monitor.py` human output prints a "Pipeline stages:" block naming all three stages | PASS |
| 12 | `monitor.py --clear` deletes all six queue/status keys | PASS |
| 13 | No new lint (ruff) errors introduced by the new test/code | PASS |

---

## 3. Exact commands + results

```bash
# Targeted: the three files this phase owns
python3 -m pytest tests/test_admin_server.py tests/test_admin_frontend.py tests/test_monitor.py -v
# => 30 passed in 0.43s

# Full Control Room surface (all admin/ modules + monitor)
python3 -m pytest \
  tests/test_admin_server.py tests/test_admin_frontend.py \
  tests/test_admin_supervisor.py tests/test_admin_design_sessions.py \
  tests/test_admin_claude_agents.py tests/test_admin_claude_agents_frontend.py \
  tests/test_monitor.py -q
# => 97 passed in 0.58s

# Related producers of story_status / STATUS_KEY (regression check)
python3 -m pytest tests/test_live.py tests/test_supervise.py tests/test_reinterleave_queue.py -q
# => 15 passed in 0.19s

# Lint on the new test file (clean)
python3 -m ruff check tests/test_monitor.py
# => All checks passed!
```

---

## 4. Notes / limitations

- **Pre-existing lint debt** (not introduced here): `tests/test_admin_server.py` still has
  3 ruff findings in unrelated code — `B007` unused loop vars in `QueuePipeline.execute`
  (lines 117, 119) and `B905` `zip()` without `strict=` (line 442). Left untouched to keep
  this phase scoped.
- **Poll-only, by design.** The post-hoc workers (`analysis_worker.py`, `review_worker.py`)
  do not publish to a pub/sub channel, so the analyze/review stages refresh only through the
  5-second `/api/matrix` poll — no SSE stream exists for them (see `docs/control_room_survey.md` §0).
- **No per-cell inspectability for post-hoc stages.** Analyze/review cells (keyed by `story_id`
  and `job_id` respectively) have no `events_log:*` entries, so the three-stage view renders
  them as counts in the `#pipeline-stages` strip rather than as clickable transcript cards.
  The execute stage keeps its existing card grid + transcript behavior unchanged.
- **`results_saved` is `null`** (not `0`) for analyze/review to distinguish "not applicable"
  from "zero results saved".
