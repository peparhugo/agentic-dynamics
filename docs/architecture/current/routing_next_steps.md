---
status: accepted
---
# Routing — Detailed Follow-Up

> Status: per-step routing is **implemented and merged** to `main`
> (`src/instrument/step_routing.py`, 82 tests). It is **dormant** until a spec declares
> `model_pool` + `preferences` + `signals`; today the `workflow_step_routing` spec is
> single-model and routes deterministically to `pool[0]` (backward compatible).
>
> This document is the working list to turn the router from a merged pure function into a
> live, data-driven control loop. Each item has a **Problem**, a **Change** (concrete), the
> **Files**, and a **Definition of Done**. Ordering matters: 1 → 2 → 3 → 4; item 5 is
> independent hygiene.

---

## 1. Wire the signal store into the run path — *P0*

### Problem

`run_workflow(signals=…)` accepts a `dict[str, ModelSignals]`, and
`build_signal_store(entries)` already builds one from `_results_summary.json` rows. But
nothing in the run path calls `build_signal_store` today: `run_workflow`
(`src/instrument/workflow_runner.py:293-297`) only reads a static
`workflow.params.signals` block or an explicitly passed argument. In a real run the router is
cold and falls back to `prev_model` / `pool[0]`, so "intelligent routing consuming experiment
outputs & costs" is not automatic.

### Field-name and model-id mismatches (must be fixed here)

The `ModelSignals` dataclass fields do **not** line up 1:1 with `_results_summary.json`
entries. Verified against `experiments/results/_results_summary.json` (227 `entries`):

| `ModelSignals` field | present in entries? | derivation |
|---|---|---|
| `correctness` | yes (`correctness`) | mean |
| `cost` | yes (`cost`) | mean |
| `efficiency` | no | `correctness / cost` (already computed) |
| `code_quality_score` | yes | mean (NaN-skip) |
| `novelty_score` | yes | mean (NaN-skip) |
| `composite_score` | yes | mean (NaN-skip) |
| `constraint_score` | **no** | derive `constraints_met / constraints_total` |
| `cache_hit_rate` | **no** | derive `tokens_cache_read / (tokens_input + tokens_cache_read)` |
| `edge_case_coverage` | no (unmeasured) | gate until instrumented (item 3) |

**Model-id mismatch.** The spec's `model_pool` uses `openai/gpt-5.6-sol|luna|terra`,
`deepseek/deepseek-v4-pro|flash`, `anthropic/claude-haiku-4-5|sonnet-5|fable-5`, but
`_results_summary.json` `by_model` keys are `openai/gpt-5.6`, `openai/gpt-5`,
`openai/gpt-5.6-fast`, `openai/gpt-5-nano`, `openai/gpt-5-mini`, `openai/gpt-5.5`,
`deepseek/deepseek-v4-pro`, `anthropic/claude-fable-5`, … — a different granularity. A
normalization/aliasing layer is required so the pool can map onto the measured corpus.

### Change

1. Add `src/instrument/signal_store.py` (or extend `step_routing.py`) with:
   - `load_results(path=EXPERIMENTS_RESULTS / "_results_summary.json") -> list[dict]` —
     reads `entries`, no re-parsing of `by_model`.
   - `derive_cache_hit_rate(e) -> float | None` from
     `tokens_cache_read / (tokens_input + tokens_cache_read)` (guard div-by-zero).
   - `derive_constraint_score(e) -> float | None` from
     `constraints_met / constraints_total` (guard `constraints_total == 0`).
   - `MODEL_ALIASES: dict[str, list[str]]` mapping pool ids → legacy result ids (e.g.
     `openai/gpt-5.6-sol → openai/gpt-5.6`), plus a `normalize_model_id(model) -> str`.
   - `build_signal_store(entries, *, aliases=MODEL_ALIASES) -> dict[str, ModelSignals]`
     that applies the derivations + aliases before aggregation (reuse the existing
     `_mean_present` NaN-skip for *all* dimensions, fixing item 5.3).
2. Thread it into the orchestration boundary — the design (`docs/architecture/current/routing_design.md` §2.2)
   assigns this to the compiler/enqueue layer, **not** inside `run_workflow`:
   - `scripts/run_workflow.py`: if the spec declares routing and no `--signals` was passed,
     call `build_signal_store(load_results())` and pass it to `run_workflow(signals=…)`.
   - Keep `run_workflow`'s explicit `signals`/`preferences` kwargs as the override hook.
3. Preserve the `_results_summary.json` shape contract — do not break
   `scripts/build_data.py` / `scripts/analyze_worktrees.py` consumers.

### Definition of done

- A spec with `model_pool` + `preferences` and *no* embedded `signals` routes on real data.
- `build_signal_store(load_results())` returns non-`None` `constraint_score` and
  `cache_hit_rate` for models that have `constraints_total` / `tokens_cache_read`.
- Unit tests cover: derivation (incl. div-by-zero), alias resolution, and that a model with
  only `openai/gpt-5.6` results resolves to `openai/gpt-5.6-sol`.
- `run_workflow` logs the selected model + effective-cost breakdown per phase.

---

## 2. Surface routing validation in the Control Room — *P1*

### Problem

`run_workflow` composes `validate_spec` + `validate_workflow_routing`
(`workflow_runner.py:245-248`), but the portal's draft validation
(`admin/design_sessions.py` `draft_state`, the `validate_spec(spec)` call around line 516)
only runs `validate_spec`. A draft with an unknown `allowed_models` id, a duplicate
`model_pool`, or a forbidden/unknown preference signal passes Save and only fails at run time.

### Change

1. In `admin/design_sessions.py` `draft_state`, after `errors = validate_spec(spec)`:
   ```python
   errors += validate_workflow_routing(spec, default_model=session.get("model", ""))
   ```
   (import `validate_workflow_routing` from `instrument.step_routing`).
2. Also compose it where specs are validated before enqueue in `scripts/` (any
   `load_spec` → run/enqueue path that currently only calls `validate_spec`).
3. Add a test in `tests/test_admin_design_sessions.py`: a workflow draft with
   `allowed_models: ["unknown/model"]` returns a `validation_errors` draft state listing the
   routing error, and `capabilities.save` stays `False`.

### Definition of done

- A bad selector is rejected at Save time in the portal, not at run time.
- `/api/design-sessions/<id>/spec` includes the routing error text.

---

## 3. Instrument the missing signals — *P0 (gates policy arms)*

The router's load-bearing rule is already enforced in code:
`FORBIDDEN_SIGNALS = {"confidence"}`, and `edge_case_coverage` is absent from
`MEASURED_SIGNALS`, so `validate_preferences` refuses both until a measurement rule
`produces` them. Instrument them so the preferences people actually want are consumable.

### 3a. `edge_case_coverage`

- **Define the measurement**: branch coverage (Python `coverage.py` on the generated
  solution's own tests) or a mutation-test kill rate (`mutmut`/`pytest-mutagen`). Pick one,
  document it as the operational definition.
- **Emit it**: add `edge_case_coverage` to `SolutionMetrics` + `_results_summary.json`
  entries (via `analyze_worktrees.py`), and aggregate it in `build_signal_store` (the
  `ModelSignals.edge_case_coverage` field already exists).
- **Declare it**: add a measurement `RuleSpec` that `produces: [edge_case_coverage]` in the
  routing spec, so `validate_preferences(prefs, produced=…)` admits the objective.

### 3b. `confidence`

- The known gap for the `model_cascade`/`dynamics` control arms
  (`src/instrument/CONTEXT.md`). Instrument `confidence: float | None` on
  `AttemptRecord` in the ledger, emitted by the runner from the model's own self-assessment
  or an evaluator score. Until then it stays in `FORBIDDEN_SIGNALS`.

### Definition of done

- `validate_preferences` admits `edge_case_coverage` when the measurement rule is present.
- A `{cost: minimize, edge_case_coverage: maximize}` preference scores against real numbers.
- `confidence` remains rejected until instrumented (no back-door consumption).

---

## 4. Author the routing arms and run the campaign — *P1*

### Problem

Nothing exercises the router end-to-end yet. Close the loop once items 1–3 land.

### Change

1. Add `preferences` + per-phase `allowed_models`/`model` selectors + `model_pool` to a real
   `agent_task` spec (e.g. a build/verify-heavy workflow), e.g.:
   ```yaml
   params:
     model_pool: [deepseek/deepseek-v4-pro, deepseek/deepseek-v4-flash,
                  openai/gpt-5.6-sol, openai/gpt-5.6-luna,
                  anthropic/claude-haiku-4-5, anthropic/claude-sonnet-5]
     preferences:
       objectives:
         - {signal: cost, direction: minimize, weight: 1.0}
         - {signal: edge_case_coverage, direction: maximize, weight: 1.0}
     phases:
       - {name: scope,  kind: agent, allowed_models: [deepseek/deepseek-v4-pro, openai/gpt-5.6-sol]}
       - {name: build,  kind: agent, allowed_models: [deepseek/deepseek-v4-flash, anthropic/claude-haiku-4-5]}
       - {name: verify, kind: agent, model: deepseek/deepseek-v4-pro}
   ```
2. Define the policy as a **factor level** in the grid: `static_pro` vs
   `routed_lowest_cost` vs `routed_preference`, and compare arms via `compare_arms`
   (`routing.simulate_strategies` generalizes to `compile_experiment.compare_arms`).
3. Confirm the cache prediction: `cache_switch_penalty` prices a model switch; the campaign
   should compare the predicted penalty against the measured `cache_read_tokens` /
   `cache_hit_rate` ledger fields per phase.

### Definition of done

- A campaign tweaking one routing variable (preference weights, pool size, fork on/off) shows
  the measured cost / coverage / cache trade-off, feeding a lab-book writeup.

---

## 5. Hygiene / correctness cleanups — *P2 (independent)*

### 5.1 `.instrument/session.jsonl` is tracked in git

`run_workflow`'s phase commit does `git add -A`, and `_init_git_workdir`
(`src/instrument/opencode.py:351-363`) commits unconditionally. `main` already tracks
`.instrument/session.jsonl`; every run rewrites it.

**Change**: add `.instrument/` to `.gitignore` and `git rm --cached .instrument/session.jsonl`,
and exclude it from the runner's commit snapshot.

### 5.2 `_init_git_workdir` unconditional "Initial" commit

It runs `git add -A && git commit -m "Initial"` even when the worktree already has commits.
This swept a killed run's leftover work into a misnamed commit and can confuse
`[workflow] <phase>` commit detection on resume.

**Change**: make it a no-op when `git rev-parse HEAD` already succeeds, and skip the commit
when nothing is staged.

### 5.3 `build_signal_store` mean consistency

`correctness`/`cost` use `or 0` defaults (missing → 0.0 averaged in), while the quality
dimensions use the NaN-skipping `_mean_present`. Route correctness/cost through the same
NaN/None-aware mean so a sparse entry can't bias the aggregate.

**Change**: replace the two ad-hoc means with `_mean_present(group, "correctness")` /
`_mean_present(group, "cost")`.

---

## Sequencing

```
1 (signal store wiring) ──► 3 (instrument signals) ──► 4 (arms + campaign)
        │
        └────────────────────► 2 (portal validation)   [parallel]
5 (hygiene) — independent, can land anytime
```

Items 1 and 3 are the critical path to "routing consumes real measured data"; item 3 is the
load-bearing-rule gate for the two preferences the design was built around
(lowest-cost and edge-case-coverage).
