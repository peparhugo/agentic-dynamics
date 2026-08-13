# Phase-1 Data-Integrity Remediation — Status

Tracks the P0 fixes from `2026-08-13_architecture-hardening-review.md` (Phase 1: data integrity).

| Finding | Status | Fix |
|---|---|---|
| P0-1 fabricated 100% pass rate | ✅ Fixed | `compute_story_models` now reads real `tests_passed`/`tests_run` from `sessions.parquet`; `_honest_pass_rate()` returns `"unknown"` when nothing ran. `compute_model_data` output preserved under `perturbation_models` key (never silently discarded). |
| P0-2 conflicting pricing sources | ✅ Fixed | Deleted `_constants.PROVIDER_PRICING`; `basin.py` cost fallback now uses `efficiency.get_pricing`; `build_data.py`/`lab_claude_audit.py` no longer import the stale dict. `efficiency.py` is the single source of truth (already had `get_pricing` + `test_pricing.py`). |
| P0-3 resurrected arch constants | ✅ Fixed | Removed `claude_active_params: 500B` and `37B` from `external_sources`; now emits `energy_model_available: false` + `deepseek_active_params: 49e9`. |
| P0-6 mutation cache never writes | ✅ Fixed | `compile_mutation` now `artifact.save(cache_path)` after compilation (both spec and codebase branches). |
| P0-7 silent clean-cell on compiler failure | ✅ Fixed | `_compile_spec_mutation`/`_compile_codebase_mutation` raise `ValueError("...compilation failed...")` when `_call_opencode` returns None/empty — no silent fallback to the clean spec. |

## Verification

- `tests/test_mutation.py` — added `test_cache_writes_and_hits` (asserts single compile on repeat) and `test_raises_on_compiler_failure`.
- `tests/test_data_integrity.py` — new regression guards: no duplicate pricing in `_constants`, no fabricated pass rate in `build_data`, basin uses `get_pricing`, no resurrected arch constants.
- `tests/test_pricing.py` — unchanged, still green (39 → 110 relevant tests pass).

## Result (data.js)

- `overall_pass_rate` was fabricated `100% (10412/10412)` → now **measured `99.9% (10726/10738) [tests]`**.
- Claude Haiku's `pass_rate` is `"unknown"` (no in-session test data) instead of a fabricated `100%`.
- Strategy counts and energy are now real (from analysis + measured tokens), not zeroed.

## Not in this batch (future phases)

- P0-4 (strategy absolute $ thresholds), P0-8…P0-12, P1, P2 — per the review's phases 2–5.
- Note: story pass rates remain ~100% because the tests are **agent-authored** (the review's "binary correctness" limitation). Honest *independent* pass/fail requires `scripts/validate_session.py` re-runs — deferred.

## Phase 2 — P0-4 strategy thresholds (done 2026-08-13)

`classify_strategy` no longer uses absolute USD thresholds. Replaced `cost >= 0.01` / `cost <= 0.003` / `cost >= 0.005` with behavioral signals (`thinking_ratio`, correctness, escape, novelty), so the archetype is invariant under uniform price rescaling and unbiased across providers. The `strategy_score` cost-penalty term was removed for the same reason.

- `tests/test_strategy.py` — locks in: expected archetypes, price-rescale invariance, and "cheap model can be wasteful / expensive model can be efficient".
- **Deferred:** existing `analysis/*.json` store the pre-fix strategy labels; re-running `analyze_stories.py` will propagate the corrected classification into `data.js`.

## Phase 3 (partial) — P0-11 + P0-12 (done 2026-08-13)

- **P0-11 provenance `[M]` overclaim** — `game_report.py` correctness tag now uses `sol.evaluator_independent` (`[M]` only when independent, else `[H]`), not `tests_total > 0`. Agent-authored tests are no longer tagged "measured".
- **P0-12 pytest errors dropped from denominator** — `analyze_worktrees.py` `run_pytest` now sets `total = passed + failed + errors`, so an errored run can no longer report 100%.
- Regression guards added to `tests/test_data_integrity.py`.

Remaining in Phase 3: P0-8 (baseline contamination), P0-9 (convention rubric), P0-10 (regex "AST" diff).

## Phase 3 (complete) — P0-8, P0-9, P0-10 (done 2026-08-13)

- **P0-8 baseline cross-contamination** — removed the "any baseline for same model" cross-experiment fallback in `analyze_worktrees.py`; raised the fingerprint threshold 0.25 → 0.5.
- **P0-9 convention rubric** — `score_conventions` now uses a `violations_weight` key (forbidden patterns were mis-keyed to `structure_weight`); removed the unimplemented `structure/documentation/type_safety/error_handling` weights from `conventions/*.yaml` so the rubric matches reality (naming + violations only).
- **P0-10 regex "AST" diff** — added Go (`func`/`type`/`import`) and Rust (`fn`/`struct|enum|impl|trait`/`use`) patterns so Go/Rust are no longer miscounted as zero; docstring now says it's a diff-stat heuristic, not a tree-sitter AST.
- Tests: `tests/test_commit_analysis.py` (Go + Rust counting), `tests/test_data_integrity.py` (baseline fallback + Go/Rust pattern guards).

Phase 3 complete. Phase 4 (robustness P1-1…P1-5) and Phase 5 (cleanup P2-1…P2-6) remain.

## Phase 4 (partial) — P1-1, P1-2, P1-3, P1-5 (done 2026-08-13)

- **P1-1 process-group kill** — `stream_subprocess` uses `start_new_session=True` + `os.killpg` on timeout (kills spawned test runners, not just the child); reader threads join without a fixed deadline.
- **P1-2 error-as-value** — `story._git` and `commit_analysis._run_git` now raise on non-zero exit (no more `"git error: …"` leaking into `commit_hash`); `apply_mutation` returns `bool` and checks the patch return code.
- **P1-3 SQLite schema probe** — `probe_session_schema()` in `_constants.py`, called by `load_db_sessions` and `query_token_breakdown`, fails loudly on schema drift instead of returning zero sessions/tokens.
- **P1-5 config unification** — `model_slug()` + `SESSION_TIMEOUT`/`STORY_SESSIONS` centralized in `_constants.py`; `run_story.py` exposes `late_degrade`; `worker.py` derives `TIMEOUT_PER_CELL` from the session timeout; `story.py` honors `OPENCODE_BIN`.

P1-4 (pipeline watchdog/PID tracking) deferred. Phase 5 (P2) remains.
