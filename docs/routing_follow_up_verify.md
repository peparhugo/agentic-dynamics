# Routing Follow-Up — Verification

> Status: **verify** (phase 4 of `experiments/specs/routing_follow_up.yaml`). Verifies the
> three implementation phases — signal store (`signal_store`), portal validation
> (`portal_validation`), and hygiene (`hygiene`) — against `docs/routing_next_steps.md` items
> 1, 2, and 5.

## Verdict

**PASS** on all checks. The per-step routing layer is now live end-to-end: the signal store is
built from real measured data and wired into the run path, routing validation is surfaced in
the Control Room at Save time, and the hygiene fixes landed.

---

## Check 1 — Routing-relevant test suite — **PASS**

Exact command (files specified explicitly — no bare suite):

```bash
python3 -m pytest tests/test_signal_store.py tests/test_step_routing.py tests/test_routing.py tests/test_workflow_runner.py tests/test_backends.py tests/test_claude_adapter.py tests/test_experiment_spec.py tests/test_compile_experiment.py tests/test_admin_design_sessions.py tests/test_opencode_events.py -q
# => 133 passed in 3.62s
```

0 failures. The new/changed tests introduced this pass are covered:

- `tests/test_signal_store.py` (15) — derivation, alias resolution, NaN/None-skip aggregation;
- `tests/test_step_routing.py` (24) — `build_signal_store` tests updated to the derivation semantics;
- `tests/test_admin_design_sessions.py` — added `test_draft_state_surfaces_routing_validation_error`
  and `test_draft_state_routing_inactive_workflow_is_unaffected`;
- `tests/test_opencode_events.py` — added `test_init_git_workdir_is_a_noop_when_history_exists`
  and `test_init_git_workdir_skips_empty_initial_commit`;
- `tests/test_workflow_runner.py` — added `test_run_workflow_excludes_instrument_from_commit`.

## Check 2 — Signal store derivations + alias resolution — **PASS**

`build_signal_store(load_results())` (227 entries) returns non-`None` `constraint_score` and
`cache_hit_rate` for every model that carries `constraints_total` / `tokens_cache_read`:

```
models w/ constraint_score: anthropic/claude-fable-5, deepseek/deepseek-v4-pro,
  openai/gpt-5, openai/gpt-5-mini, openai/gpt-5-nano, openai/gpt-5.5,
  openai/gpt-5.6-fast, openai/gpt-5.6-sol
models w/ cache_hit_rate:  (same 8 models)
```

Alias resolution confirmed: `normalize_model_id("openai/gpt-5.6") == "openai/gpt-5.6-sol"`;
the store key is the **pool** id (`openai/gpt-5.6-sol` present, legacy `openai/gpt-5.6` absent).

## Check 3 — `scripts/run_workflow.py` auto-population — **PASS**

`_spec_declares_routing` mirrors `validate_workflow_routing`'s activation check:

- `workflow_step_routing.yaml` (has `model_pool` + phases) → routing declared → store auto-built
  from `load_results()` and passed as `signals=`.
- `code_review.yaml` (single-model) → routing not declared → `signals=None`, the workflow runs
  through the existing `workflow.params.signals` fallback (unchanged).

The explicit `--signals` JSON override and `run_workflow`'s `signals`/`preferences` kwargs
remain the override hooks.

## Check 4 — `.instrument/` untracked + `_init_git_workdir` no "Initial" on existing repo — **PASS**

- `git ls-files .instrument/` → `0` (`.instrument/session.jsonl` removed from the index via
  `git rm --cached`; `.instrument/` added to `.gitignore`, confirmed with `git check-ignore`).
- `_init_git_workdir` is a no-op when `git rev-parse HEAD` succeeds; the empty "Initial" commit
  is skipped when nothing is staged. Covered by
  `test_init_git_workdir_is_a_noop_when_history_exists` and
  `test_init_git_workdir_skips_empty_initial_commit`.
- The runner's `_git_commit` now stages via `git add -A -- ':(exclude).instrument'`
  (`test_run_workflow_excludes_instrument_from_commit`).

## Check 5 — `draft_state` surfaces routing errors — **PASS**

`test_draft_state_surfaces_routing_validation_error`: a workflow draft whose phase declares
`allowed_models: [unknown/model]` returns `draft_state == "validation_errors"`, an error
containing `"unknown/model"` and `"not in model_pool"`, and `capabilities.save is False`.
A routing-inactive draft still validates `valid` / `save: True`
(`test_draft_state_routing_inactive_workflow_is_unaffected`). Implemented in
`admin/design_sessions.py` `draft_state`, composing
`validate_workflow_routing(spec, default_model=session.get("model", ""))` right after
`validate_spec`.

## Check 6 — Spec module imports cleanly — **PASS**

```bash
python3 -c "from instrument.experiment_spec import validate_spec"   # => imports cleanly
```

---

## Summary of what changed

| Phase | File(s) | Change |
|---|---|---|
| signal_store | `src/instrument/signal_store.py` (new) | `load_results`, `derive_cache_hit_rate`, `derive_constraint_score`, `MODEL_ALIASES`, `normalize_model_id`, `_mean_present`, `build_signal_store(entries, *, aliases=…)` — derivations + aliases before grouping, NaN/None-aware mean on every dimension incl. correctness/cost (item 5.3) |
| signal_store | `src/instrument/step_routing.py` | removed the superseded `_mean_present`/`build_signal_store` (router now only consumes the store) |
| signal_store | `src/instrument/__init__.py` | export the new module's symbols |
| signal_store | `scripts/run_workflow.py` | auto-build the store for routing-active specs; `--signals` override hook |
| portal_validation | `admin/design_sessions.py` | compose `validate_workflow_routing` into `draft_state` after `validate_spec` |
| hygiene | `.gitignore` | add `.instrument/` |
| hygiene | `.instrument/session.jsonl` | `git rm --cached` (untracked) |
| hygiene | `src/instrument/workflow_runner.py` | `_git_commit` excludes `.instrument/` via pathspec |
| hygiene | `src/instrument/opencode.py` | `_init_git_workdir` idempotent + skips empty "Initial" commit |
| tests | `tests/test_signal_store.py` (new), `tests/test_step_routing.py`, `tests/test_admin_design_sessions.py`, `tests/test_opencode_events.py`, `tests/test_workflow_runner.py` | derivation/alias/aggregation coverage + routing-validation + hygiene coverage |

Out of scope (deferred, per `docs/routing_next_steps.md`): item 3 (instrument
`edge_case_coverage` / `confidence`) and item 4 (author the routing arms + run the campaign).
