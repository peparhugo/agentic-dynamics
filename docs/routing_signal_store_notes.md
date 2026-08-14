# Signal Store — Notes

> Item 1 of `docs/routing_next_steps.md`: **wire the signal store into the run path.**
> The router (`step_routing.route_step`) always accepted a `dict[str, ModelSignals]`, but
> nothing in the run path built one from the measured corpus, so per-step routing started
> cold and fell back to `prev_model` / `pool[0]`. This change closes that gap.

## What changed

| File | Change |
|---|---|
| `src/instrument/signal_store.py` | **new** — `load_results`, `derive_cache_hit_rate`, `derive_constraint_score`, `MODEL_ALIASES`, `normalize_model_id`, `_mean_present`, `build_signal_store` |
| `src/instrument/step_routing.py` | removed `_mean_present` + `build_signal_store` (moved to `signal_store.py`); the router now only *consumes* the store |
| `src/instrument/__init__.py` | export the new module's symbols; `build_signal_store` now sourced from `.signal_store` |
| `scripts/run_workflow.py` | auto-build the store for routing-active specs; `--signals` override hook |
| `tests/test_signal_store.py` | **new** — 15 tests for derivation, aliasing, aggregation |
| `tests/test_step_routing.py` | `build_signal_store` tests updated to the new derivation semantics |

## Field-name mismatch (the derivations)

`ModelSignals` fields do not line up 1:1 with `_results_summary.json` entries. Two signals
must be **derived** per entry; the rest are read directly and averaged.

| `ModelSignals` field | present in entries? | derivation / source |
|---|---|---|
| `correctness` | yes (`correctness`) | NaN/None-aware mean |
| `cost` | yes (`cost`) | NaN/None-aware mean |
| `efficiency` | no | `correctness / cost` (only when both measured and `cost > 0`) |
| `code_quality_score` | yes | NaN/None-aware mean |
| `novelty_score` | yes | NaN/None-aware mean |
| `composite_score` | yes | NaN/None-aware mean |
| `constraint_score` | **no** | `constraints_met / constraints_total` |
| `cache_hit_rate` | **no** | `tokens_cache_read / (tokens_input + tokens_cache_read)` |
| `edge_case_coverage` | no (unmeasured) | **never touched** — stays `None` until instrumented (item 3) |

Both derivations return `None` on a zero denominator or a missing field, so an unmeasured
dimension is never fabricated as `0.0`:

```python
def derive_cache_hit_rate(e):      # read/(input+read); None on zero denom
def derive_constraint_score(e):    # met/total; None when total == 0
```

## Model-id mismatch (the alias layer)

The spec's `model_pool` uses the current ids (`openai/gpt-5.6-sol|luna|terra`, …) but the
perturbation corpus recorded the consolidated `openai/gpt-5.6` before the split. The mapping
is `pool id → legacy result id(s)`:

```python
MODEL_ALIASES = {"openai/gpt-5.6-sol": ["openai/gpt-5.6"]}
```

`normalize_model_id(model)` canonicalizes **any** id to its **pool** form:

- a pool id passes through unchanged (`openai/gpt-5.6-sol` → `openai/gpt-5.6-sol`);
- a legacy result id resolves to its pool id (`openai/gpt-5.6` → `openai/gpt-5.6-sol`);
- an id that already matches on both sides is unchanged (`deepseek/deepseek-v4-pro`).

Direction note: the key is the pool id, the value is the legacy id — but `normalize_model_id`
returns the **pool** id, because the store must be keyed by pool id for `route_step` to look
up any `model_pool` entry directly. (The doc's "e.g. `openai/gpt-5.6-sol → openai/gpt-5.6`"
describes the dict mapping; the canonicalization runs legacy → pool.)

Verified against `experiments/results/_results_summary.json` (227 entries): `by_model` keys are
`openai/gpt-5.6`, `openai/gpt-5.6-fast`, `deepseek/deepseek-v4-pro`, `anthropic/claude-fable-5`,
… — a different granularity than the pool. After aliasing, `build_signal_store(load_results())`
produces `openai/gpt-5.6-sol` (with `constraint_score` and `cache_hit_rate` non-`None`), and
`openai/gpt-5.6` is *not* a key.

## Aggregation (item 5.3 fix folded in)

`build_signal_store(entries, *, aliases=MODEL_ALIASES)`:

1. for each entry, derive `cache_hit_rate` and `constraint_score` and normalize the model id
   (`openai/gpt-5.6` → `openai/gpt-5.6-sol`) — **before** grouping, so legacy and pool ids merge;
2. group by normalized id;
3. average every dimension through `_mean_present` (NaN/None skip) — including `correctness`
   and `cost`, which previously used `or 0` defaults and let sparse entries bias the mean.

`confidence` and `edge_case_coverage` are never read here (the load-bearing rule).

## Wiring (`scripts/run_workflow.py`)

```python
spec = load_spec(Path(args.spec))
signals = None
if args.signals:
    signals = _load_signals(args.signals)          # explicit override (JSON: {model: {field: v}})
elif _spec_declares_routing(spec):                 # model_pool | per-phase selector | preferences
    try:
        signals = build_signal_store(load_results())
    except (FileNotFoundError, json.JSONDecodeError):
        signals = None                              # no corpus → cold-start deterministically
run_workflow(..., signals=signals)
```

`_spec_declares_routing` mirrors `step_routing.validate_workflow_routing`'s activation check.
Single-model specs (`code_review.yaml`, `design_sessions.yaml`, …) are routing-inactive and
run unchanged — `signals=None` falls through to `workflow_runner`'s existing
`workflow.params.signals` static fallback. `run_workflow`'s explicit `signals`/`preferences`
kwargs remain the override hook. `build_data.py` / `analyze_worktrees.py` are untouched (the
`_results_summary.json` shape is read-only here).

## Tests

```bash
python3 -m pytest tests/test_signal_store.py tests/test_step_routing.py -q   # 39 passed
```

- derivation incl. div-by-zero (`derive_cache_hit_rate`, `derive_constraint_score`);
- alias resolution: `normalize_model_id("openai/gpt-5.6") == "openai/gpt-5.6-sol"`, pool/matching ids unchanged;
- a model measured only under the legacy id resolves into the store under its pool id;
- `correctness`/`cost` skip NaN/None rows instead of defaulting to 0.

Full routing-relevant set (97 passed):

```bash
python3 -m pytest tests/test_signal_store.py tests/test_step_routing.py tests/test_routing.py \
  tests/test_workflow_runner.py tests/test_backends.py tests/test_claude_adapter.py \
  tests/test_experiment_spec.py tests/test_compile_experiment.py -q
```

## Remaining follow-ups

- **Item 3** — instrument `edge_case_coverage` (branch coverage or mutation-test kill rate) and
  emit it into `SolutionMetrics` + `_results_summary.json` before the `{cost, edge_case_coverage}`
  preference can be admitted. `confidence` stays forbidden.
- **Item 4** — author the routing arms (`static_pro` vs `routed_lowest_cost` vs
  `routed_preference`) and run the campaign once the store is live.
- **Item 2** — surface `validate_workflow_routing` in the Control Room draft validation
  (`admin/design_sessions.py`) — independent of this change.
- **Item 5** — hygiene (`.instrument/` gitignore, `_init_git_workdir` unconditional commit).
  Note 5.3 is folded into this change: `build_signal_store` now routes `correctness`/`cost`
  through `_mean_present`.
