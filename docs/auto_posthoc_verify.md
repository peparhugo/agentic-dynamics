---
status: accepted
---
# Auto Post-Hoc Verify

Verification of the auto-triggered `execute → analyze → review` handoff
(implemented in `src/instrument/posthoc.py` + `scripts/worker.py` +
`scripts/analysis_worker.py`; survey in `docs/auto_posthoc_survey.md`).

**Result: PASS — all four required checks verified.**

## Commands run

```bash
# 1. The new test file (all four required checks)
python3 -m pytest tests/test_auto_posthoc.py -v

# 2. Regression: modules adjacent to the changed wiring
python3 -m pytest tests/test_live.py tests/test_story.py \
    tests/test_review_agent.py tests/test_commit_analysis.py -q

# 3. Regression: spec/compiler + workflow (src/instrument/__init__.py was touched)
python3 -m pytest tests/test_experiment_spec.py tests/test_compile_experiment.py \
    tests/test_workflow_runner.py tests/test_supervise.py -q
```

## Results

| Command | Result |
|---|---|
| `tests/test_auto_posthoc.py -v` | **13 passed** |
| live/story/review_agent/commit_analysis | **64 passed** |
| experiment_spec/compile/workflow_runner/supervise | **55 passed** |
| **Total targeted** | **132 passed, 0 failed** |

> Note: a bare `python3 -m pytest` (no path) over-collects generated artifacts
> under `experiments/results/reports/**/code/tests` and errors — pre-existing,
> unrelated to this change. The canonical invocation is `pytest tests/`.

## Per-check verification

### Check 1 — worker auto-enqueues analysis after a cell — PASS

- `test_result_path_from_stdout_parses_run_story_line` — `worker._result_path_from_stdout`
  extracts the saved result path from `run_story.py`'s `  Results: <path>` line.
- `test_result_path_from_stdout_returns_none_without_results_line` — missing line → `None`.
- `test_worker_triggers_analysis_after_cell` — a completed cell enqueues exactly one
  `analysis_jobs` entry with the correct `story_id`/`worktree`/`result_path` and seeds
  `analysis_status[s1] = queued`.
- `test_worker_trigger_skips_when_no_result_line` — no result line → no-op, no crash.

### Check 2 — analysis worker auto-enqueues review after analysis — PASS

- `test_analysis_worker_triggers_reviews_after_analysis` — one commit job per session
  commit (`s1_1`, `s1_2`) plus a story-level job (`s1_story`); all use
  `DEFAULT_REVIEW_MODEL`; every `review_status[job_id]` seeded `queued`.
- `test_analysis_worker_skips_reviews_when_no_commits` — a worktree with no session
  commits produces zero review jobs (mirrors `enqueue_reviews.py`).

### Check 3 — trigger failure does not fail the cell — PASS

- `test_worker_trigger_failure_is_swallowed` — a raising `trigger_analysis` is caught
  by `worker._trigger_analysis`; no exception propagates (the `completed += 1` path
  continues).
- `test_analysis_worker_trigger_failure_is_swallowed` — a raising `trigger_reviews` is
  caught by `analysis_worker._trigger_reviews`; analysis still completes.
- `test_posthoc_trigger_analysis_returns_false_for_bad_input` — malformed result
  (missing `story_id`) returns `False` rather than raising.

### Check 4 — backfill scripts still work (same job shape, no drift) — PASS

- `test_enqueue_analysis_build_jobs_uses_shared_helper` — `build_jobs` emits the shared
  `{story_id, worktree, result_path}` shape and honors `skip_existing`.
- `test_enqueue_analysis_main_enqueues_via_shared_path` — the analysis backfill still
  `lpush`+`hset` the exact job dict through `enqueue_job`.
- `test_enqueue_reviews_main_still_works` — the review backfill builds the same commit +
  story job set (`s1_1`, `s1_2`, `s1_story`) via the shared builders.
- `test_scripts_share_posthoc_constants` — the scripts import (never redefine) the
  canonical queue/status keys, model, `worktree_commits`, and job builders, so the
  backfill tools and the worker triggers cannot drift.

## Files

- `tests/test_auto_posthoc.py` — 13 tests covering the four required checks.
- No production code was modified in this phase.
