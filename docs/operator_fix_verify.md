---
status: accepted
---
# Operator Fix — Verification Report

Verifies the four-phase fix (assess → fix_operators → seed_cell_identity → add_tests)
against the concrete bugs found in `docs/operator_audit.md`. Each check below is marked
PASS or FAIL with the exact command and result.

## Commands run

| # | Command | Result |
|---|---------|--------|
| 1 | `python3 -m pytest tests/test_perturb.py -v` | **43 passed** in 0.58s |
| 2 | `python3 -m pytest tests/test_strategy.py tests/test_data_integrity.py tests/test_correctness_lineage.py -v` | **22 passed** in 0.58s |

> Note: `tests/test_basin.py` does not exist in this repo. Basin behavior is covered by
> `tests/test_perturb.py` (`test_basin_verdict_*`), `tests/test_data_integrity.py`
> (`test_basin_cost_fallback_uses_get_pricing`), and `tests/test_correctness_lineage.py`
> (`test_basin_receives_post_test_correctness`), all of which passed above. No downstream
> regression was introduced by this work.

## Checks

### Check 1 — Target tests pass: PASS

`python3 -m pytest tests/test_perturb.py -v` → `43 passed` (10 pre-existing + 33 new regression tests).

### Check 2 — Downstream regression: PASS

`python3 -m pytest tests/test_strategy.py tests/test_data_integrity.py tests/test_correctness_lineage.py -v` → `22 passed`.
No failures to fix.

### Check 3 — All 10 operators pass the smoke test: PASS

`test_operator_smoke` is parametrized over `build_operators()` (10 operators) and asserts,
at `strength=0.5`, that output is non-empty, differs from the base prompt, and carries a
canonical `perturbation_class`. All 10 parametrizations passed.

### Check 4 — All operators are no-ops at strength 0: PASS

`test_strength_zero_is_noop` is parametrized over `build_operators()` and asserts that
`perturb_prompt(base, op, strength=0.0)` returns the base prompt unchanged with
`noop_reason == "strength 0.0 (no-op)"`. All 10 parametrizations passed.

> Note: the requirement phrased this as "all 9 non-baseline operators"; the registry actually
> contains 10 operators (baseline is a pseudo-operator handled inside `perturb_prompt`, not a
> registered operator). All 10 registered operators are now strength-0 no-ops.

### Check 5 — alien_vocab matches its documentation: PASS

`test_alien_vocab_injects_cross_domain_terms` asserts the main path substitutes terms drawn
from `ALIEN_VOCABULARIES` (a cross-domain word set), that `vocab_domain` is a valid key, that
the output contains an alien term, and that `injected_tokens` records only words from the chosen
domain. The operator was fixed (not renamed): the name and docstring now describe the actual
cross-domain substitution behavior.

### Check 6 — reverse_causality no longer duplicates: PASS

`test_reverse_causality_no_duplication` asserts the task-description sentence appears exactly
once at strengths 0.1, 0.5, 0.8, and 1.0. The dead-code branch (`preamble`/`remaining`/
`task_start`) was removed and the prompt is now partitioned into disjoint sections.

### Check 7 — Seed is a pure function of the cell: PASS

`test_cross_model_same_cell_same_seed` asserts `derive_seed(task, operator, strength, repetition)`
equals the documented formula
`int(sha256(f"{task}|{operator}|{strength}|{repetition}")[:8], 16)` and is deterministic.
`derive_seed` takes no model argument, so the same cell yields the same seed regardless of model,
loop order, or `run_idx` slot.

### Check 8 — sha256 persisted: PASS

`scripts/run.py::_run_perturbed` now derives the seed and persists reproducibility evidence into
every result record (verified by inspection, `scripts/run.py:186-189, 252-254`):

- `rng_seed` ← `derive_seed(task, op_name, strength, rep)`
- `perturbed_prompt` ← the exact perturbed text sent to the model
- `perturbed_prompt_sha256` ← `sha256(perturbed_prompt)`

`scripts/sweep_silent_mode.py` persists `perturbed_prompt_sha256` per perturbed row, and
`src/instrument/experiment.py` (deprecated) uses the same `derive_seed` derivation.

## One-line summary of each fixed operator

| Operator | What it now does |
|----------|------------------|
| `inject_alien_vocab` | Substitutes the prompt's tech terms with cross-domain `ALIEN_VOCABULARIES` words; records actual injected tokens + domain. |
| `inject_false_premise` | Appends a plausible-but-false assumption (strength buckets mild/medium/strong); no-op at strength ≤ 0. |
| `shift_framing` | Appends a falsification-stance reframe directive; no-op at strength ≤ 0. |
| `invert_constraint` | Inverts **every** applicable term in each selected constraint sentence (no more first-match-only `break`); no-op at strength ≤ 0. |
| `insert_contradiction` | Inserts a pair of conflicting requirements near the constraints section; no-op at strength ≤ 0. |
| `remove_critical_constraint` | Silently drops a severity-scored constraint; no-op at strength ≤ 0. |
| `inject_phantom_success` | Appends a false intermediate result for the model to question; no-op at strength ≤ 0. |
| `reverse_causality` | Reorders constraints/output before the task, emitting each input line exactly once (no duplication); no-op at strength ≤ 0. |
| `inject_competing_goal` | Appends a conflicting secondary goal (mild/sharp/direct); no-op at strength ≤ 0. |
| `force_abandonment` | Appends a generate-N-discard-then-redo directive; no-op at strength ≤ 0. |

All 10 operators are now pure functions of `(prompt, strength, rng)` with a shared strength-≤-0
no-op guard in `perturb_prompt`, and their perturbation is seeded deterministically from the cell
identity via `derive_seed`.
