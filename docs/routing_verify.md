# Per-Step Model Routing + Cache-Aware Forking — Verification

Status: verify (phase 4 of `experiments/specs/workflow_step_routing.yaml`) · Preceded by
`docs/routing_survey.md` (survey), `docs/routing_design.md` (design). Verifies the phase‑3
implementation of `docs/routing_design.md`.

---

## Verdict

**PASS.** The per-step routing layer is implemented exactly as designed: three-step
selection semantics (pin / `allowed_models` subset / full pool), a preference-scoring
function over *measured* experiment signals, and a cache-aware switch penalty that prices a
model change against the lost cache prefix. All routing-relevant tests pass, and the two
unmeasured signals (`edge_case_coverage`, `confidence`) are correctly gated/forbidden rather
than consumed.

## Test command + results

Run **only** the routing-relevant files (never a bare suite — see the collection note at the
end of this document):

```
python3 -m pytest tests/test_routing.py tests/test_workflow_runner.py tests/test_backends.py tests/test_claude_adapter.py tests/test_experiment_spec.py tests/test_compile_experiment.py -q
# => 58 passed in 2.24s
```

The new routing test module is run explicitly as well:

```
python3 -m pytest tests/test_step_routing.py -q
# => 24 passed in 0.65s
```

Combined routing-relevant set (the six files above plus the new `test_step_routing.py`):

```
python3 -m pytest tests/test_step_routing.py tests/test_routing.py tests/test_workflow_runner.py tests/test_backends.py tests/test_claude_adapter.py tests/test_experiment_spec.py tests/test_compile_experiment.py -q
# => 82 passed in 2.49s
```

All commands completed with **0 failures**. `ruff check` on the touched files
(`step_routing.py`, `workflow_runner.py`, `__init__.py`, `test_step_routing.py`) is clean.

## Checks

| Check | Result | Evidence |
|---|---|---|
| Three-step semantics are tested | **PASS** | Pin: `test_pin_wins` (`tests/test_step_routing.py:60`) — a pin is returned verbatim even when another candidate is strictly better on every signal. Subset: `test_allowed_models_restricts_the_subset` (`:67`) — the cheapest in-pool model is *outside* the subset and is ignored. Full pool: `test_unconstrained_draws_from_full_pool` (`:80`). Selection logic lives in `route_step` (`step_routing.py:473-519`) via `parse_step_selector` (`:217`). |
| `allowed_models` validation rejects unknown ids and empty subsets | **PASS** | `validate_step_selector` (`step_routing.py:224-249`) errors on an empty list (`"non-empty"`), unknown ids (`"not in model_pool"`), duplicate ids, and a phase declaring both `model` and `allowed_models`. Covered by `test_validate_step_selector_rejects_empty_and_unknown` (`tests/test_step_routing.py:184`) and `test_validate_step_selector_rejects_both_keys` (`:179`). |
| Preferences block maps to a scoring function over MEASURED signals | **PASS** | `RoutingPreferences`/`Objective` parse the `{objectives: [{signal, direction, weight}]}` block (`step_routing.py:78-133`); `_score_eligible` (`:400`) + `_normalize` (`:392`) implement the direction-aware min-max score, re-normalized over present objectives. `MEASURED_SIGNALS` (`:64`) is exactly the 8 measured signals (correctness, cost, efficiency, cache_hit_rate, constraint_score, code_quality_score, novelty_score, composite_score). Scored by `test_lowest_cost_preference_selects_cheapest` (`:93`), `test_highest_correctness_preference` (`:98`), `test_weighted_preferences_flip_the_choice` (`:103`). |
| "lowest cost + highest edge-case coverage" gates cleanly when unmeasured | **PASS** | `edge_case_coverage` is *not* in `MEASURED_SIGNALS` (`step_routing.py:64-66`). `validate_preferences` (`:256`) refuses it with a "not produced … instrument it first" error unless a measurement rule `produces` it (`test_edge_case_coverage_is_gated_without_measurement_rule`, `tests/test_step_routing.py:115`; `test_edge_case_coverage_admitted_when_produced`, `:121`). Once produced it scores normally: `test_coverage_objective_scores_when_measured` (`:126`) exercises the `{cost: minimize}` + `{edge_case_coverage: maximize}` example. |
| Cache-aware forking still works end to end (`fork: true`) | **PASS** | `test_run_workflow_forks_when_model_unchanged` (`tests/test_step_routing.py:305`) drives a 2-phase spec with `fork: true`: the second phase passes `fork=True` and `session_id="sess_1"` (the prior phase's session). The fork guard is unchanged in the runner (`workflow_runner.py:348-354`, `prev_model == model_i`). |
| A model switch is priced against the lost cache prefix | **PASS** | `cache_switch_penalty` (`step_routing.py:347`) computes `prev_cache_read_tokens · (input − cache_read)/1M` from `PROVIDER_PRICING`; `_effective_cost` (`:384`) folds it into the `cost` signal. `test_cache_switch_penalty_uses_deepseek_spread` (`:139`) asserts the $0.431375/1M DeepSeek spread; `test_switch_penalty_keeps_router_on_prior_model` (`:145`) shows the router stays on the prior model when switching would forfeit a large cache read, and `test_no_prior_prefix_routes_to_cheaper_model` (`:153`) shows it switches freely when there is no prefix to lose. |
| Router reads only measured signals and never references `confidence` | **PASS** | `FORBIDDEN_SIGNALS = frozenset({"confidence"})` (`step_routing.py:69`); `confidence` is absent from `MEASURED_SIGNALS`. `validate_preferences` refuses `confidence` unconditionally (`:256-262`), covered by `test_validate_preferences_forbids_confidence` (`tests/test_step_routing.py:191`). Runtime check: `'confidence' in MEASURED_SIGNALS` is `False`. |
| `experiment_spec` still imports and validates | **PASS** | `python3 -c "from instrument.experiment_spec import validate_spec"` succeeds and `validate_spec` is callable. (Note: `python` is not on PATH; `python3` used. A bare `python3 -c` resolves `instrument` to a sibling worktree via a `site-packages/*.pth`; prefixing `PYTHONPATH=src` targets this repo's module, confirmed by `experiment_spec.__file__`. `validate_spec` is also exercised by `tests/test_experiment_spec.py`.) |
| Existing routing consumers unbroken | **PASS** | `routing.py` (`compute_routing`, `recommend_route`, `simulate_strategies`) is untouched; `tests/test_routing.py` passes (6/6). `scripts/build_data.py` continues to import `compute_routing` unchanged. |

## Summary of what changed

Phase 3 added a thin routing layer **on top of** the existing `routing.py` aggregators (which
were left untouched, per the design's "reuse, not re-derive" rule):

- **`src/instrument/step_routing.py`** (new) — `Objective`/`RoutingPreferences` (preferences
  block), `ModelSignals` (per-model measured signals), `StepSelector`/`parse_step_selector`/
  `validate_step_selector` (pin/subset/pool + load-time validation), `route_step` (pure argmax
  selector with deterministic tie-break), `cache_switch_penalty` (prefix-loss pricing),
  `validate_preferences`/`validate_workflow_routing` (the requires/produces gate), and
  `build_signal_store` (aggregates `_results_summary.json` entries into per-model signals).
- **`src/instrument/workflow_runner.py`** — the phase loop now selects `model_i = route_step(...)`
  per step instead of a single workflow `model`, while the existing `prev_model == model_i` fork
  guard is unchanged. The runner stays single-model (backward compatible) when no `model_pool`
  is declared.
- **`src/instrument/__init__.py`** — exports the new module.
- **`tests/test_step_routing.py`** (new) — 24 tests covering the full deliverable: three-step
  semantics, preference scoring, edge-case-coverage gating, cache-switch pricing, cold-start
  fallback, and end-to-end fork chaining through `run_workflow`.
- **`docs/routing_verify.md`** — this document.

Two review fixes from this verification pass (no test behavior change): `ModelSignals.from_dict`
renamed its loop variables to stop shadowing `dataclasses.field` (F402) and an unused `signal`
(B007), and `build_signal_store` now also aggregates the SolutionMetrics quality dimensions
(`constraint_score`, `code_quality_score`, `novelty_score`, `composite_score`) via a NaN-aware
mean, so those measured signals are actually consumable end to end.

### Collection note (bare suite is not a meaningful signal)

An unscoped `python3 -m pytest` / `python3 -m pytest tests/ -q` was intentionally **not** run:
pytest recursively collects generated third-party experiment code under
`experiments/results/reports/` and stops with hundreds of collection errors before executing.
This is a pre-existing discovery limitation (documented in `docs/verify.md`), not a routing
regression. Verification was therefore scoped to the routing-relevant files listed above.
