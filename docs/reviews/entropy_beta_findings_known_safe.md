---
status: accepted
---

# entropy_beta_findings — known-safe list

**Spec:** `entropy_beta_instruments@0.1`. **Adversarial phase p4.**
Every item below was verified mechanically (re-derivations, fixture probes, worktree scans, JSON
traversal) during the adversarial review (`docs/reviews/entropy_beta_findings_adversary.md`).
Nothing in this list is assumed.

| # | item | evidence |
|---|---|---|
| K1 | The quadrant contract holds in both directions | all 321 `delta_entropy.json` rows: `quadrant≠null` ⟺ `test_join_complete` ∧ both axes present; 195 incomplete rows are `quadrant=null`, never a fabricated quadrant |
| K2 | The measured-not-estimated rule holds — no imputed values | the linkage ratio is `None` (deferred) when `changed_symbol_count==0` or no changed symbol is test-linked; `test_executed_success` is `None` when unmeasured; no zero-defaults anywhere |
| K3 | The β formula is correct and the wrapper/cell share is exact | `cap_2b` re-derived from `p1_phase_ledger.json`: cell=implement=0.003594637, wrapper=verify=0.005186592 → share 0.590645 (matches the committed 0.590645 exactly) |
| K4 | The 2b prior correction is grounded | 63% ($0.17/$0.27, design β §1) vs the re-derived 59.1% — "directionally confirmed, not numerically reproduced" is the honest verdict |
| K5 | The clean-but-wrong cell is real and resolves | `20bbc6ce7c40` → `notification_service_claude_haiku_4_5_early_degrade_20bbc6ce7c40.json`; ΔH_solution −0.054, tests fail |
| K6 | Coverage is exact — 244 story JSONs = 235 measured + 9 `baseline_missing` | all 9 skipped cell ids are genuine missing seed directories; no `worktree_missing`/`no_language`/`no_git_root` skips |
| K7 | Campaign facts coverage is real | the 86 campaign cells come from the recorded `cells/`, `p2_cells_run.json`, and `*_score_*.json` under `cap_2b` + `cap_adaptive_2c/2d/2e/2f` — the linkage + outcome axes read from those records, never recomputed |
| K8 | The β campaign set is exactly the 6 ledgers that carry a cost breakdown | 7 `*phase_ledger*.json` files have `total_measured_cost_breakdown` → 6 campaigns (cap_2a_rerun3 has two); the other 53 phase-ledger files use a different schema, so the 6-campaign coverage is complete, not truncated |
| K9 | The ΔH_solution / ΔH_tests relationship is not an artifact | Pearson r = 0.23 over all 321 cells' `delta_h_solution`/`delta_h_tests` pairs; both axes predominantly positive (299/321 and 277/321) — the weak correlation is a property of the data, not of rounding |
| K10 | Both instruments reproduce exactly | re-run of `measure_delta_entropy.py` (9m17s) and `compute_coordination_overhead.py` reproduced every cell count, quadrant count, and overhead value; only `generated_at` timestamps differ |
| K11 | The unit tests pin the instrument's contract | `tests/test_delta_entropy.py` (split excludes test files, four-quadrant classification, the missing-join→None contract) and `tests/test_coordination_overhead.py` (overhead arithmetic, the 2b share, the cell/wrapper phase split) — 27 tests pass |

**Not known-safe** (deliberately flagged, see the adversary):

- **K-not-safe-1 — the split leaks `conftest.py` (and would leak `*_test.py`) into ΔH_solution.**
  `is_test_file` applies only the profile glob `test_*.py` (Python) plus the `tests/`/`test/` dir
  rule, so pytest's `conftest.py` and `*_test.py` naming are missed. Materialized: `conftest.py`
  at the top level of 13/244 story worktrees is counted as production code. A FAILED finding —
  the split rule needs the `*_test.py`/`conftest.py` patterns added before ΔH_solution is used as
  a per-cell gate. (Magnitude is one fixture file per affected codebase; the quadrant story is
  unaffected in sign.)
- **K-not-safe-2 — the join axis is heterogeneous.** Story cells recompute the linkage ratio via
  the instrument's own TESTED_BY approximation; campaign cells read the CAP fact-plane's recorded
  ratio. Two definitions under one column name — a caveat, not an imputation.
- **K-not-safe-3 — β loses one digit to intermediate rounding.** `coordination_overhead_beta` is
  computed from `cell`/`wrapper` rounded to 8 decimals (cap_2b β = 1.442868 vs 1.442869 at full
  precision). Display-level only; the share and every conclusion are exact.
