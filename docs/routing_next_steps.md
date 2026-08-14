# Routing — Next Steps (post-merge)

Status: per-step routing is implemented and tested on `feature/workflow-step-routing`
(82 tests, `src/instrument/step_routing.py`). It is **dormant** until a spec declares
`model_pool` + `preferences` + `signals`; the current `workflow_step_routing` spec is
single-model and routes deterministically to `pool[0]` (backward compatible). The router
is a pure function (`route_step(job, state, prefs, signals=…)`) layered on the untouched
`routing.py`. These are the ordered steps to turn it into a real, end-to-end control loop.

---

## 1. Wire the signal store into the execution path (P0)

**Problem.** The router consumes a `signals: dict[str, ModelSignals]` store, and
`build_signal_store(entries)` already builds it from `_results_summary.json` rows. But
nothing calls `build_signal_store` in the run path today: `run_workflow` only reads a
static `workflow.params.signals` block or an explicitly passed argument. So in a real run
the router is cold (falls back to the prior model / `pool[0]`), and "intelligent routing
consuming experiment outputs & costs" is not yet automatic.

**Work.**

1. Add a loader that reads `experiments/results/_results_summary.json` (and, where
   relevant, `experiments/results/lab_cache_economics.json` and `compute_routing()` model
   stats) into the list-of-dicts shape `build_signal_store` expects. Reuse the parsing
   already done in `scripts/build_data.py` / `scripts/analyze_worktrees.py` rather than
   re-implementing it.
2. Thread it into the orchestration layer so `run_workflow(signals=…)` is populated
   automatically when the spec declares routing. The design doc (§2.2) assigns this to the
   compiler/enqueue boundary, not inside `run_workflow`; put the loader next to
   `experiment_matrix`/`enqueue` so the same store feeds enqueue-time routing, the
   runner, and `compare_arms`.
3. Keep `run_workflow`'s explicit `signals`/`preferences` kwargs as the override hook
   (tests + manual calls), but add the auto-load as the default for spec-driven runs.

**Acceptance.** A spec with `model_pool` + `preferences` and *no* embedded `signals` block
routes on real measured data; a `run_workflow` run logs which model each phase selected and
the effective-cost breakdown (per-signal score + cache penalty).

## 2. Expose routing validation in the Control Room (P1)

**Problem.** `run_workflow` calls `validate_spec` + `validate_workflow_routing`, but the
portal's draft validation (`admin/design_sessions.py` `draft_state`, ~line 516) calls only
`validate_spec`. A spec with an invalid `allowed_models` id, a duplicate `model_pool`, or a
forbidden/unknown preference signal passes draft review and only fails at run time.

**Work.**

1. Compose `validate_workflow_routing(spec, default_model=…)` into `draft_state`'s error
   list (and into `scripts/` spec loading where specs are validated before enqueue).
2. Surface the errors in the existing `validation.errors` + `capabilities` UI so the
   operator sees them before Save/Run.
3. Add a `test_admin_design_sessions` case for a workflow draft with a bad selector.

**Acceptance.** A draft with `allowed_models: [unknown/model]` shows a routing error in the
portal before Save, and `/api/design-sessions/<id>/spec` returns it.

## 3. Instrument the missing signals (P0 — gates policy arms)

The load-bearing rule is enforced in code: the router refuses `confidence` and gates
`edge_case_coverage` until a measurement rule `produces` them. Instrument them next so the
preferences people actually want are consumable.

- **`edge_case_coverage`** — needed for the "lowest cost + highest edge-case coverage"
  preference. Define the measurement: branch coverage (via `coverage.py`) or a
  mutation-test kill rate on generated solutions. Add a measurement `RuleSpec` that
  `produces: [edge_case_coverage]`, emit it in the ledger, and aggregate it in
  `build_signal_store` (the `ModelSignals.edge_case_coverage` field already exists).
- **`confidence`** — the known gap for the `model_cascade`/`dynamics` control arms
  (`src/instrument/CONTEXT.md`). Instrument it on `AttemptRecord` before authoring those
  arms; until then it stays in `FORBIDDEN_SIGNALS`.

**Acceptance.** `validate_preferences` admits `edge_case_coverage` once the measurement
rule is present, and a `{cost: minimize, edge_case_coverage: maximize}` preference scores
against real numbers.

## 4. Author the routing policy arms and run the campaign (P1)

With the signal store wired and the signals measured, close the loop:

1. Add a `preferences` block + per-phase `allowed_models`/`model` selectors to a real spec
   (e.g. a build/verify-heavy `agent_task`) and declare the `model_pool`.
2. Define the policy as a *factor level* in the grid: `static_pro` vs `routed_lowest_cost`
   vs `routed_preference`, and compare arms via `compare_arms`
   (`routing.simulate_strategies` generalizes to `compile_experiment.compare_arms`).
3. Report the cache-hit delta from `fork: true` chaining vs model-switch churn — the
   `cache_switch_penalty` already prices this; the campaign should confirm the prediction
   against the measured `cache_read_tokens`/`cache_hit_rate` ledger fields.

**Acceptance.** A campaign tweaking one routing variable (preference weights, pool size, or
fork on/off) shows the measured cost/coverage/cache trade-off, feeding a lab-book writeup.

## 5. Hygiene / correctness cleanups (P2)

- **`.instrument/session.jsonl` is tracked.** `run_workflow`'s phase commit does
  `git add -A`, and `_init_git_workdir` (`src/instrument/opencode.py:351-363`) also
  commits unconditionally. The repo already tracks `.instrument/session.jsonl`; add
  `.instrument/` to `.gitignore` and `git rm --cached` it so transcripts stop entering
  history.
- **`_init_git_workdir` unconditional "Initial" commit.** It runs `git add -A && git
  commit -m "Initial"` even when the worktree already has commits, which swept a killed
  run's leftover work into a misnamed commit and can interfere with `[workflow] <phase>`
  commit detection on resume. Make it a no-op when `git rev-parse HEAD` already succeeds
  (and skip the commit when there is nothing staged).
- **`build_signal_store` mean consistency.** `correctness`/`cost` use `or 0` defaults
  (missing → 0.0 averaged in), while the quality dimensions use the NaN-skipping
  `_mean_present`. Route correctness/cost through the same NaN/None-aware mean so a sparse
  entry can't bias the aggregate.
