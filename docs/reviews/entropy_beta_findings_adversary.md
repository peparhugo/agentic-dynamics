---
status: accepted
---

# entropy_beta_findings — adversarial review (p4)

**Role:** adversarial verifier — falsify the findings. Spec `entropy_beta_instruments@0.1`
(`workflows/repository/entropy_beta_instruments.yaml`). Findings under review:
`docs/reviews/entropy_beta_findings.md`, grounded in `experiments/results/entropy_beta/delta_entropy.json`
(schema `delta_entropy/v1`) and `.../coordination_overhead.json` (schema `coordination_overhead/v1`).

Every item below was re-derived independently — from the raw ledger JSONs, the story/campaign
worktrees, and the instrument source (`scripts/measure_delta_entropy.py`,
`scripts/compute_coordination_overhead.py`, `src/agentic_dynamics/measurement/{delta_entropy,coordination_overhead}.py`)
— never from the findings doc's own numbers.

## Finding table

| # | check | attempt to falsify | result | finding |
|---|---|---|---|---|
| F1 | **the split** (test-file exclusion really excludes) | probed `is_test_file` against pytest's full convention (`test_*.py`, `*_test.py`, `conftest.py`, `tests/`/`test/` dirs, `.test.ts(x)`, `*_test.go`) and scanned all 244 story worktrees | `test_*.py`, `tests/`+`test/` dirs, `.test.ts(x)`, `*_test.go` are excluded; but **`conftest.py` and `*_test.py` are NOT** — `is_test_file` only matches the profile glob `test_*.py` plus the dir rule. Materialized: `conftest.py` at the top level of **13/244** story worktrees (notification_service ×4, task_manager_api ×9) is classified as *solution* | **FAILED FINDING (split)** |
| F2 | **the quadrant contract** (every ΔH row carries the test-join + quadrant) | checked all 321 rows: `quadrant≠null ⟹ test_join_complete ∧ both axes present`; `test_join_complete ⟹ quadrant≠null`; `quadrant=null ⟹ join incomplete` | 0 violations in either direction; the 195 incomplete rows carry `quadrant=null` (a FAILED finding by contract), never a fabricated quadrant | **CLEAN** |
| F3 | **measured-not-estimated** (every figure traces to a measured field) | traced `ΔH`, `changed_symbols_with_tests_ratio`, `test_executed_success`, and every overhead term to their source fields | ΔH from `compute_entropy` over the trees; ratio is `None` (deferred) when `changed_symbol_count==0` or no changed symbol is test-linked — never defaulted to 0.0; `test_executed_success` is `None` when unmeasured, never defaulted; the ledger terms come from `total_measured_cost_breakdown` | **CLEAN** (one caveat, F3a) |
| F3a | join-axis homogeneity (a sub-check of F3) | compared how `changed_symbols_with_tests_ratio` is obtained for story vs campaign cells | **story** cells recompute the ratio via the instrument's `_tests_ratio_from_delta` (a TESTED_BY approximation); **campaign** cells read the CAP fact-plane's recorded `changed_symbols_with_tests_ratio`. Both measured, but two different ratio definitions are joined under one field name | **CAVEAT (not imputation)** |
| F4 | **the β arithmetic** (re-derive ≥1 campaign from the ledger) | recomputed `cap_2b` from `experiments/results/cap_2b/p1_phase_ledger.json` = `{implement 0.003594637, test 0.0, verify 0.005186592}` | cell = implement = 0.003594637, wrapper = verify = 0.005186592; **share = 0.590645 (exact)**, formula correct. β = 1.442869 at full precision vs committed 1.442868 — the committed β is computed from `cell`/`wrapper` already rounded to 8 decimals, so its 6th decimal is off by one | **CLEAN** (1e-6 precision nit, F4a) |
| F5 | **the citations** (every finding resolves to its rows) | resolved the clean-but-wrong cell id, the campaign names, and the 2b prior | `20bbc6ce7c40` → `experiments/results/stories/notification_service_claude_haiku_4_5_early_degrade_20bbc6ce7c40.json`; the 6 campaign names → phase-ledger dirs; the 2b prior "63% ($0.17 of $0.27)" → design β §1 table | **CLEAN** |
| F6 | **the coverage** (the table is exact) | recounted the corpus and the skip reasons | 244 story JSONs on disk = 235 measured + 9 `baseline_missing` (all 9 baseline seed dirs genuinely absent); 86 campaign cells; no `worktree_missing`/`no_language`/`no_git_root` skips occurred | **CLEAN** |

## Findings (the one real failure, the caveats)

1. **F1 — the split is incomplete, and it materializes (FAILED finding).** The instrument's
   "naming rule" is the language profile's `test_file_pattern` — `test_*.py` for Python — which
   omits pytest's *other* naming conventions `*_test.py` and `conftest.py`. `conftest.py` (the
   root-level pytest fixture/config file) therefore lands in the **solution** profile. In 13 of
   244 story worktrees that file is a test-tree file counted as production code, so the design's
   "ΔH_solution = production code only" guarantee is definitionally violated for those cells. The
   magnitude is bounded — one fixture file per affected codebase, and a large part of its ΔH
   cancels baseline-vs-final — but the split rule itself is wrong, not the fixture. This is the
   one contract breach the p4 role's split attack was designed to catch.

2. **F3a — the join axis mixes two ratio definitions.** For story cells the instrument recomputes
   the linkage ratio; for campaign cells it reads the fact-plane's recorded ratio. The two have
   different TESTED_BY semantics, so the single `changed_symbols_with_tests_ratio` column is not
   homogeneous. This is a *measured* heterogeneity, not an imputation, but a reader should not
   treat the column as one definition across corpora.

3. **F4a — β loses a digit to intermediate rounding.** `coordination_overhead_beta` is computed
   from `cell_cost`/`wrapper_cost` rounded to 8 decimals, so cap_2b's β prints 1.442868 where the
   full-precision quotient is 1.442869. The wrapper share (0.590645) is exact and every
   conclusion is unchanged; it is a display-level nit.

## Attempted (and failed) falsifications of the findings

- **Could the quadrant contract be silently dropping rows?** No — 126 join-complete ↔ 126
  quadrants, bidirectional, and the 195 deferred rows are explicitly `quadrant=null`.
- **Could the 2b share be a coincidence?** Re-derived 0.590645 from the raw ledger fields
  `implement`/`verify` independently; it is the exact wrapper/(wrapper+cell) share.
- **Could any ΔH or ratio be fabricated?** No zero-defaults anywhere; unmeasurable axes are
  `None` and recorded as such.
- **Could the coverage be padded?** 244 story JSONs on disk reconcile to 235 + 9 exactly; the
  9 skips are real missing seed directories.

## Conclusion

Five of six attacks are CLEAN and the findings' central claims survive: the quadrant distribution,
the clean-but-wrong count (1), the β curve (≈1.0–1.44 wrapper share 51–59% for real grids), and
the 2b prior correction (63% → 59.1%) are all reproducible from the raw records. One FAILED
finding is confirmed and should be carried forward: **the split leaks `conftest.py` (and would
leak `*_test.py`) into `ΔH_solution`**, materialized in 13/244 cells. This does not overturn the
quadrant story (the contaminated file's ΔH contribution is small and the affected cells are
overwhelmingly high-ΔH either way), but it is a genuine instrument defect to fix before the
ΔH_solution axis is used as a per-cell gate.

**LOG:** 5/6 adversarial attacks CLEAN (quadrant contract, measured-not-estimated, β arithmetic,
citations, coverage), 1 FAILED finding confirmed (F1: `conftest.py`/`*_test.py` leak into
ΔH_solution in 13 cells), 1 caveat (F3a: heterogeneous join axis), 1 precision nit (F4a). The
findings survive with the split defect recorded. **PARTIAL — deviation recorded; findings stand.**
