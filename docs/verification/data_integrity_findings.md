---
status: accepted
---
# Data-integrity findings — the canonical record

**Status:** the authoritative source for which experiment data is trustworthy and why. This
document exists because the boundary lived in the operator's head and was rediscovered the hard
way, repeatedly. Update it when the boundary changes; do not infer it from code.

## What happened

A workflow agent auditing the corpus discovered that the pre-remediation experiment results were
flawed: the *conditions* did not do what they claimed. The remediation then re-ran the affected
cells, producing a small set of genuinely-perturbed, instrumented results. Everything below is the
consequence of that discovery.

## The flaws (why the old data is untrustworthy for perturbation)

| Condition | Claimed | Reality |
|---|---|---|
| `early_degrade` | session-1 spec mutated (false premise injected) | **no-op** — the mutation silently fell back to the clean spec (P0-7) or never degraded; "degraded" cells ran clean |
| `bad_seed` | seeded from a genuinely bad codebase | **not a bad seed** — the "bad" seed was not actually degraded |
| single-task `manifold`/`semantic` | meaningful perturbation taxonomy | **stale 2-way labels** (P0-5) + **cross-matched baselines** (P0-8) + **fabricated 100% pass rate** (P0-1) |

The common thread: the old cells carry a *condition label* that is not backed by a real
perturbation, and the single-task summary carries fabricated provenance.

## The boundary — what is trustworthy, per dimension

The old cells still **really ran**: models spent tokens, cost money, and produced code. So the
validity depends on the *dimension*, not the whole cell:

| Dimension | Old cells (pre-fix) | New cells (re-runs + perturbed) |
|---|---|---|
| **Cost** (tokens, $, cache) | ✅ valid | ✅ valid |
| **Code quality** (loc, tests, AST) | ✅ valid | ✅ valid |
| **Perturbation** (degrade/flail/recovery/narration) | ❌ no-op — never happened | ✅ **the only trustable source** |

## The data inventory

| Set | Count | Verdict |
|---|---|---|
| New instrumented `early_degrade` re-runs | 80 | **canonical perturbation** |
| `task_manager_*.json` single-task re-runs | 7 models | **canonical perturbation** (clean) |
| `process_perturbation_resample_*.json` | pro / fable-5 / sol | **canonical perturbation** (clean) |
| Old non-instrumented story cells (clean 83, bad_seed 41, early_degrade 11) | 135 | **relabel to `clean` (no-op)** — keep cost + code quality only |
| Contaminated `early_degrade` (ran-as-clean) | 77 | **tombstone** (quarantined in `stories/_remediation_contaminated/`) |
| Old single-task `_results_summary.json` | 144 | **retire** — replaced by the clean re-runs, never folded |

## The treatment rules

1. **Relabel, don't delete, the no-op cells.** A story result whose `perturbation_condition` is
   `early_degrade` or `bad_seed` AND which lacks `test_executed_success` (non-instrumented, i.e.
   pre-fix) is a **no-op**: its condition is relabeled to `clean` with a caveat that the original
   label was a no-op. Its cost + code-quality measurements remain valid.
2. **Only instrumented cells carry a perturbation signal.** The 80 re-runs (`test_executed_success`
   present) keep `early_degrade`. The `task_manager_*` + `process_perturbation_resample_*` results
   are the clean single-task perturbation arm.
3. **The 77 contaminated cells are tombstoned** (`delete` + reason = contaminated ran-as-clean).
4. **The 144-entry `_results_summary.json` is retired, not recovered** — the clean re-runs replace
   it. Nothing is folded into it.

## What this means going forward

The canonical corpus is a **large clean baseline + a small but real degraded arm**, not the fake
three-condition grid it was. Future experiments must record, in the ledger, whether a condition
*actually* perturbed (the `test_executed_success` / `mutation_id` presence is the signal). A
condition label without that evidence is a no-op.
