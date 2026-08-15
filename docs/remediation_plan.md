# Remediation Plan — Instrumentation, Recompute, Re-admit

Assesses the current state of the 2026-08-13 hardening review's P0/P1/P2 findings
against the *actual code*, inventories the four unmeasured ledger fields, and
enumerates the cells that need a genuine re-run. Evidence is `file:line` and was
re-verified in the working tree (not taken on trust from the review or the
phase-1 status doc).

**Verdict in one line:** every P0 that changes *numbers* is FIXED-IN-CODE; the
remaining contamination is **STALE-IN-DATA** (old labels / old basin matches baked
into `_results_summary.json` + `data.js`) plus the four **UNMEASURED** ledger fields
that still gate the `grit` and `model_cascade`/`dynamics` arms.

---

## 1. State table — P0/P1/P2 vs. current code

Legend: **FIXED-IN-CODE** (code corrected, data may need rebuild), **STALE-IN-DATA**
(code fixed but historical results still carry pre-fix numbers), **OPEN** (not done).

### P0 — Measurement integrity

| Finding | Status | Evidence (current state) |
|---|---|---|
| P0-1 fabricated 100% pass rate | **FIXED-IN-CODE** | `scripts/build_data.py:843` `_honest_pass_rate()` returns `"unknown"` on no data; `:941` reads real `tests_passed` from `sessions.parquet`; `:978` preserves `perturbation_models = models` (no override). |
| P0-2 three conflicting pricing sources | **FIXED-IN-CODE** | Single source `src/instrument/efficiency.py:40` `PROVIDER_PRICING` + `:176` `get_pricing()`; `basin.py:238-239` imports `get_pricing`; `scripts/_constants.py` has **no** `PROVIDER_PRICING` (grep confirms only `efficiency.py` defines it). |
| P0-3 resurrected arch constants | **FIXED-IN-CODE** | `scripts/build_data.py:1135` `energy_model_available: false`, `:1136` `deepseek_active_params: "49e9"`. No `claude_active_params`/`37B`. |
| P0-4 absolute USD strategy thresholds | **FIXED-IN-CODE** | `src/instrument/strategy.py:141-145` behavioral signals only (`is_correct/is_novel/is_escaped/is_reasoning_lean/is_wasteful`); `:190-195` `strategy_score` has no cost term; verdict text only reports cost. |
| P0-5 dead `semantic`/`manifold` taxonomy | **FIXED-IN-CODE** (data **STALE**) | `basin.py:80-98` branches on `specification_corruption`/`objective_mutation`/`process_perturbation`; `perturb.py:78-82` `PERTURBATION_CLASSES`, `:99` default `""`. But `_results_summary.json` still holds **16** `perturbation_class: "manifold"` entries (see §3.1). |
| P0-6 mutation cache never writes | **FIXED-IN-CODE** | `mutation.py:236` `artifact.save(cache_path)` after both spec and codebase compilation. |
| P0-7 silent clean cell on compiler failure | **FIXED-IN-CODE** (data **STALE**) | `mutation.py:258-260` and `:302-303` `raise ValueError("…compilation failed…")` when `_call_opencode` returns None/empty. Historical early-degrade cells remain contaminated (§3.2). |
| P0-8 baseline cross-contamination | **FIXED-IN-CODE** (data **STALE**) | `scripts/analyze_worktrees.py:1007` fingerprint threshold `> 0.5` (was 0.25); `:1033-1038` "No cross-experiment fallback" — old Priority-4 removed. Historical basin numbers already computed against wrong baselines (§3.3). |
| P0-9 convention rubric ignores 45% | **FIXED-IN-CODE** | `commit_analysis.py:381-387` uses `violations_weight` (forbidden patterns correctly keyed); unimplemented `structure/documentation/type_safety` weights removed from `conventions/*.yaml`. |
| P0-10 regex "AST" diff miscounts Go/Rust | **FIXED-IN-CODE** | `commit_analysis.py:275` docstring "diff-stat *heuristic*"; `:297-312` Go (`func`/`type`/`import`) and Rust (`fn`/`struct|enum|impl|trait`/`use`) patterns. |
| P0-11 correctness `[M]` overclaim | **FIXED-IN-CODE** | `game_report.py:159` `[M] if sol.evaluator_independent else [H]`. |
| P0-12 pytest errors excluded from total | **FIXED-IN-CODE** | `analyze_worktrees.py:112` `total = passed + failed + errors`; mirrored in `validate_session.py:55` and `test_runner.py:60`. |

### P1 — Robustness & hardening

| Finding | Status | Evidence |
|---|---|---|
| P1-1 no process-group kill | **FIXED-IN-CODE** | `streaming.py:74` `start_new_session=True`; `:116` `os.killpg(os.getpgid(proc.pid), SIGKILL)`. |
| P1-2 error-as-value | **FIXED-IN-CODE** | `story.py:870-888` `_git` raises; `commit_analysis.py:824-841` `_run_git` raises; `mutation.py:382-404` `apply_mutation(...) -> bool` checks patch return code. |
| P1-3 SQLite schema coupling | **FIXED-IN-CODE** | `scripts/_constants.py:64` `probe_session_schema()`; called by `load_db_sessions`/`query_token_breakdown`. |
| P1-4 swallowed control state | **PARTIAL** | `pipeline.py:1024` `MAX_PHASE_WALLCLOCK` + `:1102-1105` watchdog, `:287` `_set_state` now logs Redis failures — **fixed**. Worker PID sidecar + SIGTERM handler in `worker.py` — **still OPEN** (deferred). |
| P1-5 config inconsistency | **FIXED-IN-CODE** | `_constants.py:87` `model_slug()`, `:100-101` `SESSION_TIMEOUT`/`STORY_SESSIONS`; `worker.py:28` derives `TIMEOUT_PER_CELL`; `run_story.py:79` exposes `late_degrade`; `story.py:668` honors `OPENCODE_BIN`. |

### P2 — Maintainability & drift

| Finding | Status | Evidence |
|---|---|---|
| P2-1 deprecated surface / dual orchestration | **OPEN** | `src/instrument/__init__.py` still re-exports `adapter/experiment/lab_book/…`; `plan.py` + `review_worker.py` still present. |
| P2-2 `build_data.py` god script | **OPEN** | `scripts/build_data.py` still ~1188 lines with the three `sid_to_model` derivations. |
| P2-3 composite weights duplicated 4× | **FIXED-IN-CODE** | `solution.py:16` `COMPOSITE_WEIGHTS`, `:19` `COMPOSITE_WEIGHTS_SONAR`; `analyze_worktrees.py` + `build_data.py` reference them. |
| P2-4 hygiene / CI | **FIXED-IN-CODE** | `.gitignore:24` covers `experiments/results/analysis/`; `.github/workflows/pytest.yml:96` runs full `pytest tests/` (+ `:92` ruff). |
| P2-5 schema validation on external input | **FIXED-IN-CODE** | `story.py:147-149` `SessionSpec.from_dict` raises `ValueError` on missing fields; `pipeline.py` `_parse_phase` validated per phase-1 log. |
| P2-6 `rm -rf /tmp/exp_*` scope | **OPEN** | `opencode.json` still a raw glob with `ask`. |

---

## 2. Instrumentation gap analysis — the four unmeasured ledger fields

The ledger schema (`src/instrument/experiment_spec.py:44-97` `LEDGER_FIELDS`) deliberately
omits the four fields; `validate_rules` (`experiment_spec.py:367-403`) refuses any control
rule whose `requires` touch them. Each field is classified (a) recorded anywhere, (b)
recorded but not on the story/single-task path, or (c) entirely absent.

### 2.1 `confidence` — **(c) ENTIRELY ABSENT**

- No attempt-level `confidence: float | None` exists anywhere. The only hits are
  unrelated heuristics: `constraint_detection.py:30` `detection_confidence` and
  `recovery.py:39` segment-classification `confidence` — neither is the model's
  self-assessed confidence that `model_cascade`/`dynamics` consume.
- It is *actively forbidden* in routing: `step_routing.py:68`
  `FORBIDDEN_SIGNALS = frozenset({"confidence"})` and `:215`.
- **Must change:**
  - `src/instrument/opencode.py` `AgenticResult` + `_parse_session_output` (`:507-524`)
    — capture a per-attempt confidence signal from the event stream (e.g. the model's
    own `step_finish`/reasoning trace, or a calibrated proxy), and carry it on `AgenticResult`.
  - `src/instrument/claude_adapter.py` `adapt_usage` — same, for the `claude_cli` backend.
  - `src/instrument/workflow_runner.py` `PhaseResult` (`:49-95`) — surface it per phase.
  - `src/instrument/story.py` `SessionResult` (`:200-262`) — surface it per story session.
  - `src/instrument/experiment_spec.py` `LEDGER_FIELDS` — add `"confidence"`.

### 2.2 `perturbation_strength` — **(b) recorded, but not on the story/single-task LEDGER path**

- Present on the *measurement* dataclasses: `perturb.Perturbation.strength` (`perturb.py:98`),
  `basin.BasinMetrics.perturbation_strength` (`basin.py:28`), `trajectory.ReasoningTrajectory.perturbation_strength`
  (`trajectory.py:56`), `mutation.MutationArtifact.strength` (`mutation.py:107`),
  `game_report.GameReport.perturbation_strength` (`game_report.py:44`).
- **Absent** on the story ledger: `StoryResult`/`SessionResult` record only the string
  `perturbation_condition` and `mutation_id` (`story.py:275,382`), never the numeric
  strength. `condition_to_mutations` hardcodes `strength=0.5` (`story.py:104,117`) and
  does not propagate it.
- **Field-name mismatch:** `LEDGER_FIELDS` has `"strength"` as a factor level
  (`experiment_spec.py:63`), but `grit()` reads `attempts[i]["perturbation_strength"]`
  (`compile_experiment.py:270-283`) — the two names don't reconcile, so the validator
  can never satisfy `grit` even after story-side instrumentation.
- **Must change:**
  - `story.py` `condition_to_mutations` + `run_story` — emit the numeric strength into
    `StoryResult` (e.g. `perturbation_strength = 0.5` for BAD_SEED/EARLY/LATE, `0.0` for CLEAN).
  - The attempt-record writer — map factor `strength` → `perturbation_strength` (rename or
    alias), and add `"perturbation_strength"` to `LEDGER_FIELDS`.

### 2.3 `test_executed_success` — **(b) recorded, but not on the story/single-task path**

- Exists **only** in the `agent_task` workflow: `workflow_runner.py:71` `PhaseResult.test_executed_success`,
  set at `:324` via `test_runner.suite_succeeded` (`test_runner.py:138-140`).
- `scripts/verify_tests.py` computes it for story cells and writes
  `experiments/results/verified_tests.json` — but that file **does not exist**; the script
  has never been run to completion. `test_executed_success` is therefore not actually in
  any results artifact today.
- The story path records only the *model's self-reported* `agentic.tests_passed/tests_total`
  (`story.py:246-247`) — explicitly the thing `test_executed_success` is designed to replace.
  The single-task path (`run.py` / `analyze_worktrees.run_pytest` `:85-116`) computes
  correctness but never emits the boolean.
- **Must change:**
  - `story.py` `_run_session`/`SessionResult` — after the last session, run
    `test_runner.run_suite` on the final worktree and store `test_executed_success` (or run
    `verify_tests.py` as a mandatory post-story step).
  - `analyze_worktrees.run_pytest` (`:85-116`) — add `test_executed_success` to its return.
  - `experiment_spec.py` `LEDGER_FIELDS` — add `"test_executed_success"`.

### 2.4 `answer`/`explanation` token split — **(c) ENTIRELY ABSENT**

- No `answer_tokens`/`explanation_tokens`/`tokens_answer`/`tokens_explanation` anywhere in
  `src/` or `scripts/` (grep returns nothing except an unrelated test fixture).
- `opencode._parse_session_output` (`:507-524`) reads only
  `tokens{input, output, reasoning, cache}`; `sweep_silent_mode.py` measures the
  silent-vs-verbose *gap* but never splits the completion stream into answer vs explanation.
- **Must change:**
  - `opencode.py` `AgenticResult` + `_parse_session_output` — split completion tokens into
    `answer` (code/file-tool payloads) vs `explanation` (prose/`text` events), using the
    `tool_use` vs `text` event types already parsed (`:463-505`).
  - `claude_adapter.py` `adapt_usage` — same split for the Claude stream.
  - `workflow_runner.py`/`story.py`/`commit_analysis.agentic_token_dicts` (`:804`) — carry
    the two new token counters through to the ledger.
  - `experiment_spec.py` `LEDGER_FIELDS` — add `"answer"`/`"explanation"` (or a single
    `tokens_answer`/`tokens_explanation` pair).

**Re-admit sequence** (the load-bearing rule): instrument the four fields into the code
paths above → add them to `LEDGER_FIELDS` (`experiment_spec.py:44`) → then `validate_rules`
will accept `grit` (requires `perturbation_strength` + `test_executed_success`) and
`model_cascade`/`dynamics` (requires `confidence`) in a spec. The `grit` evaluator already
exists and is *gated* (`compile_experiment.py:257-338`), returning an explicit unmeasured
result until its fields exist — no code change needed there beyond the field names.

---

## 3. Re-run inventory — contaminated cells

### 3.1 Manifold cells — **16 cells** (stale taxonomy label)

- **What:** `_results_summary.json` entries with `perturbation_class == "manifold"`, a label
  that no longer exists under the 3-way taxonomy. Breakdown: 10 × `inject_alien_vocab_s0.5`
  + 6 × `shift_framing_s0.5`, all `operator = perturbed`, `model = deepseek/deepseek-v4-pro`.
  Both operators are now `process_perturbation` (`perturb.py:607-624, 649-666`).
- **Worktrees:** `exp_2dqodvt8, exp_2yyxp_8_, exp_5d0kt9ne, exp_73hs5n35, exp_96rfqfgd,
  exp_9uzjxitk, exp_dbzmm0qd, exp_e6nmmhtb, exp_ikhirync, exp_oylan6wf, exp_p31ut41o,
  exp_trdn7iwn, exp_v0u6d7t1, exp_whigxsgm, exp_wmysu1lk, exp_ze0y99pc` — **0 of 16 on disk,
  none archived** (`refs/experiments/` holds only `story_*` refs). Recomputation is impossible.
- **Identification:** `python -c "… filter perturb_class=='manifold' in _results_summary.json"`
  (also reflected as `"perturbation_class": "manifold"` in `firebase/public/data.js`).
- **Action:** genuine re-run of the 16 cells under `process_perturbation` labeling
  (`run.py` with `inject_alien_vocab`/`shift_framing`, strength 0.5).

### 3.2 P0-7 silent-clean fallbacks — early/late-degrade story cells (up to **85**)

- **What:** `experiments/results/stories/*.json` cells whose session-1 (early) / session-4
  (late) spec mutation was a silent no-op because the Flash V4 compiler (`_call_opencode`)
  returned None/empty and the pre-fix `mutated_spec = mutated or specification`
  (`mutation.py`, since fixed at `:258-260`) fell back to the clean spec. The cell is
  recorded as a perturbation but ran as CLEAN.
- **Scope:** `early_degrade` = **85 cells**; `late_degrade` = **0 cells** (never ran in the
  matrix). `bad_seed` with empty `mutation_id` is *not* contamination — that is the
  legitimate "no pre-generated bad variant" skip path (`story.py:83-96`).
- **Identification:** the mutation cache is **empty** (`experiments/codebases/.mutation_cache`
  = 0 artifacts), so there is no persisted artifact to inspect. Two reliable routes:
  1. Re-run `compile_mutation(spec=story_specs[0], operator="inject_false_premise",
     strength=0.5, model="deepseek/deepseek-v4-flash")` post-fix and flag every cell that
     now raises `ValueError("mutation compilation failed")`.
  2. Compare the full session-1 prompt against the canonical `story_specs[0]` (recover the
     prompt from the archived worktree `refs/experiments/story_*` → `.instrument/session_1.jsonl`;
     the result JSON only stores a 200-char-truncated prompt). Byte-identical ⇒ contaminated.
- **Action:** genuine re-run of the flagged early_degrade cells (worktrees are archived —
  84 `story_*` refs — so only the *prompt comparison* is possible, not a re-derivation of
  the mutation; the mutated spec itself is unrecoverable).

### 3.3 P0-8 wrong-baseline cells — cross-matched single-task runs

- **What:** single-task `_results_summary.json` perturbed entries whose basin-escape /
  `basin_verdict` / `novelty_score` / `architecture_divergence` were computed against a
  cross-experiment baseline (old "Priority 4: any baseline for the same model") or a loose
  fingerprint match (`> 0.25`). `find_baseline_code` is now `analyze_worktrees.py:974-1038`
  (threshold `> 0.5`, no cross-experiment fallback).
- **Scope:** all **92** perturbed entries currently report `no_baseline: False`; of the 227
  entries, **64** are solo `exp_*` experiments (single-entry experiments with **no**
  same-experiment baseline) — these necessarily cross-matched under the old code.
- **Identification:** filter `_results_summary.json` for perturbed entries whose `experiment`
  has no `operator == baseline` counterpart (the 64 solo `exp_*` plus any other orphan), or
  re-run `analyze_worktrees` with the fixed matcher and flag entries that now come back
  unmatched while still carrying non-zero basin metrics.
- **Worktrees:** single-task `exp_*` worktrees are deleted and **not archived** (only 1 of
  227 entries has its worktree on disk). Recomputation is impossible.
- **Action:** genuine re-run of the orphaned single-task cells with a true same-experiment
  baseline, so basin numbers are no longer cross-contaminated.

### Recompute feasibility (explicit)

- **Recomputable from archives:** the **84 archived `story_*` worktrees** — restore via
  `archive_worktrees`/`backfill`, then run `verify_tests.py` to populate `test_executed_success`
  and re-run `analyze_stories`/`analyze_worktrees` for corrected derived metrics (P0-11/P0-12
  already make `analyze_worktrees` recomputation correct).
- **NOT recomputable (genuine re-run required):** the 16 manifold cells (§3.1) and the
  ~64+ wrong-baseline single-task cells (§3.3) — their worktrees are gone and unarchived.
- **Regenerate downstream:** after re-runs, `scripts/sync_data.py` → `scripts/build_data.py`
  → `generate_manifest.py` so `data.js` stops emitting `manifold` labels and cross-matched
  basin numbers.
