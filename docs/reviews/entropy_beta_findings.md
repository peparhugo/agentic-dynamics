---
status: accepted
---

# entropy_beta_findings — the Δ-entropy quadrants and the β coordination tax, measured

**Findings for the `entropy_beta_instruments` spec** (`workflows/repository/entropy_beta_instruments.yaml`,
SHA256 `eb20ac8305…`, `entropy_beta_instruments@0.1`). Written from p2's committed outputs — no
re-computation. The two mandate designs are `docs/designs/proposed/neo4j_graph_analysis_design.md`
§3 (the Δ-entropy instrument) and `docs/designs/proposed/beta_snowball_measurement_design.md` §2-3
(the β coordination tax). Every number below cites a field in
`experiments/results/entropy_beta/delta_entropy.json` (schema `delta_entropy/v1`) or
`experiments/results/entropy_beta/coordination_overhead.json` (schema `coordination_overhead/v1`).

## 1. Methodology

**The Δ-entropy instrument** (`scripts/measure_delta_entropy.py` → `src/agentic_dynamics/measurement/delta_entropy.py`)
implements the design §3 pins:

- **The solution/test split (the confound fix).** The whole-tree `compute_entropy` walk silently
  includes test files; the instrument measures two dimensions separately — `ΔH_solution`
  (production code only, test files excluded by naming + `tests/`-dir rules) as the primary axis,
  and `ΔH_tests` (the test tree's own structural entropy) as a secondary work-product signal.
  Each is `ΔH = H(final) − H(baseline)` over the five entropy dimensions (`entropy.py`).
- **The three-axis join.** `ΔH_solution` (structure) · `changed_symbols_with_tests_ratio` (linkage,
  the code-change seam's TESTED_BY term) · `test_executed_success` (outcome, the independent
  runner). A ΔH row without both join axes is recorded `test_join_complete=false` with
  `quadrant=null` — the contract is law: **ΔH without the test-join is a FAILED finding, never a
  quadrant** (design §3.3, §6).
- **The four-quadrant table** (design §3.3): high/low `ΔH_solution` (cut = sign of ΔH, `[P]`) ×
  tests pass/fail → `messy_but_right` · `messy_and_broken` · `clean_and_right` · **`clean_but_wrong`**
  (the 2d/2e unseen-family wall — structurally clean, semantically wrong).

**The β coordination-tax instrument** (`scripts/compute_coordination_overhead.py` →
`src/agentic_dynamics/measurement/coordination_overhead.py`) implements the design §2 formula:

```
coordination_overhead(campaign) = (wrapper + merge + chain + review) / cell
```

Only `wrapper` and `cell` carry a measured USD cost (the phase-ledger
`total_measured_cost_breakdown`; `cell` = `implement + rework`, `wrapper` = everything else —
a declared `[P]` choice). The `merge`/`chain`/`review` terms are **event counts** (git
merge/conflict commits, data-chain commits, review files), reported alongside and **never blended**
into the cost ratio (design §6: measured, never blended).

**Coverage (exact — never imputed):**

| corpus | on disk | measured | skipped (reason) |
|---|---|---|---|
| story cells | 244 story result JSONs | 235 | 9 `baseline_missing` |
| campaign cells | 5 campaign dirs (`cap_2b`, `cap_adaptive_2c/2d/2e/2f`) | 86 | — |
| **ΔH total** | | **321** | |
| test-join complete | | 126 (39.3%) | |
| test-join incomplete | | 195 | quadrant deferred = FAILED finding |
| β campaigns | phase ledgers with `total_measured_cost_breakdown` | 6 | 53 other `*phase_ledger*.json` files carry a different schema |

## 2. The ΔH results

### 2.1 Per-model quadrant distribution (126 join-complete cells)

| bucket | messy_but_right | messy_and_broken | clean_and_right | clean_but_wrong | total |
|---|---|---|---|---|---|
| campaign (mixed-model) | 52 | 16 | 4 | 0 | 72 |
| claude-haiku-4-5 | 20 | 3 | 0 | **1** | 24 |
| claude-sonnet-5 | 5 | 0 | 0 | 0 | 5 |
| deepseek-v4-flash | 3 | 0 | 0 | 0 | 3 |
| deepseek-v4-pro | 7 | 0 | 0 | 0 | 7 |
| gpt-5.6-luna | 4 | 0 | 1 | 0 | 5 |
| gpt-5.6-sol | 6 | 0 | 0 | 0 | 6 |
| gpt-5.6-terra | 2 | 2 | 0 | 0 | 4 |
| **total** | **99 (78.6%)** | **21 (16.7%)** | **5 (4.0%)** | **1 (0.8%)** | **126** |

The dominant quadrant is **messy-but-right** (78.6%) — the agent introduces net disorder in the
solution tree (ΔH_solution > 0) but the tests still pass. This is the flash hygiene texture the
design anticipated (design §3.3's "messy but right — the hygiene texture"), observed here across
every model, not only flash. Only 4.0% land clean-and-right, and only 0.8% are clean-but-wrong.

**Caveat on attribution.** The `campaign` bucket (72/126 = 57%) is mixed-model — the campaign cell
records do not carry a per-cell model id, so they are reported as one bucket, not per model. The
per-model picture is driven by the 54 join-complete *story* cells across seven models.

### 2.2 The "clean but wrong" count — the 2e wall's prevalence

Exactly **1** join-complete cell is `clean_but_wrong` (ΔH low + tests fail): cell
`20bbc6ce7c40` — `claude-haiku-4-5`, story `notification_service`, condition `early_degrade`,
`ΔH_solution = −0.0543`, `ΔH_tests = +0.2482`, `changed_symbols_with_tests_ratio = 0.2542`,
`test_executed_success = false`. It is the blind-spot case the design named: the solution tree is
structurally *cleaner* than its baseline while the meaning is broken. In this corpus the wall is a
**low-frequency** event — but see §5: the test-join is only 39% complete, so 1 is a floor, not a
prevalence estimate.

### 2.3 Does the solution mess track the test mess?

Across all 321 measured cells, `ΔH_solution` and `ΔH_tests` are **weakly** correlated: Pearson
`r = 0.23` (`[C]`, over the `delta_h_solution`/`delta_h_tests` pairs in `delta_entropy.json`).
Both dimensions are overwhelmingly positive — 299/321 (93.1%) solution cells and 277/321 (86.3%)
test cells introduced net disorder; means `ΔH_solution = +0.203`, `ΔH_tests = +0.213`. The weak
correlation means the two are largely **independent work-product signals**: a messy solution does
not imply a messy test suite, and vice-versa. The split is therefore not redundant — `ΔH_tests`
carries information `ΔH_solution` does not.

## 3. The β results

### 3.1 Per-campaign coordination overhead

| campaign | cell (USD) | wrapper (USD) | β (wrapper/cell) | wrapper share | merge | chain | review |
|---|---|---|---|---|---|---|---|
| cap_2a_rerun | 0.00356 | 0.00502 | 1.410 | 58.5% | 3 | 1 | 6 |
| cap_2a_rerun2 | 0.00631 | 0.00656 | 1.040 | 51.0% | 1 | 0 | 2 |
| cap_2a_rerun3 | 0.00745 | 0.00950 | 1.275 | 56.0% | 1 | 1 | 2 |
| cap_2a_shadow_calibration | 0.00116 | 0.20124 | 172.885 | 99.4% | 1 | 0 | 2 |
| cap_2b | 0.00359 | 0.00519 | 1.443 | 59.1% | 1 | 1 | 2 |
| cap_adaptive_2c | 0.01585 | 0.00 | 0.000 | 0.0% | 1 | 1 | 2 |

### 3.2 The measured β curve

The four *real grid* campaigns (2a rerun ×3 + 2b) cluster tightly: **β ≈ 1.0–1.44, wrapper share
51–59%** — the coordination tax is roughly **half of every campaign's spend**. Two rows are
artifacts, not signal: `cap_2a_shadow_calibration` (β = 172.9) is a calibration probe whose cell
cost ($0.00116) is negligible next to its verification spend ($0.20124); `cap_adaptive_2c`
(β = 0.0) has `verify = null` in its phase ledger, so its wrapper cost is unmeasured, not zero.

**This is not the concurrency ladder** (design §3) — the design's β *curve* is `overhead(concurrency)`
at 1/2/4/8 rungs, still preregistered and not yet run. The numbers above are a cross-campaign
scatter of the tax, which the design §2 intended as the immediate, no-new-runs computation. They
establish the tax's magnitude, not its N² shape.

### 3.3 The 2b 63% prior — confirmed or corrected?

The design cites the 2b prior as **63%** ($0.17 of $0.27 — phases, not cells). Re-derived from the
one 2b phase ledger still on disk (`total_measured_cost_breakdown` = `implement 0.003595` +
`test 0.0` + `verify 0.005187`): wrapper share = **59.1%** (β = 1.443). Verdict:
**directionally confirmed, not numerically reproduced** — the wrapper is a clear majority of
campaign spend as the prior asserted, but at 59% rather than 63%, and at a different dollar scale
than the prior's $0.17/$0.27. The prior's qualitative claim (coordination dominates) survives; its
exact figure does not.

## 4. Routing / process implications (scoped to the evidence)

1. **Messy-but-right is the norm, not the pathology.** 78.6% of join-complete work is
   high-ΔH + passing-tests. A process that flags "high ΔH" as a defect would flag 4 out of 5
   correct outcomes; ΔH alone is not a correctness signal. It is a *hygiene* texture signal, and
   the review/debt axis it should feed is the design's F4 texture — not a gate. `[C]`+`[H]`.
2. **The tests are the blind-spot corrector, and the join is the bottleneck.** The one
   clean-but-wrong cell is exactly the design's wall, but the join is only 39% complete. The
   cheapest way to see more of the blind-spot is not more ΔH measurement — it is closing the
   test-join: the campaign cells that lack `test_executed_success` and the story cells that lack a
   computable `changed_symbols_with_tests_ratio`. `[H]`.
3. **The coordination tax is real and large (~50–59% of spend).** For the four real grids, the
   wrapper phase costs as much as the cells themselves. This is a measured confirmation of the
   operator's lived observation (coordination snowballing) and of the β countermeasure thesis —
   small, scoped, parallel units — but it is a *cross-campaign* magnitude, not the N² curve that
   would prove the thesis. The ladder re-measurement (design §3-4) is the verification that is
   still owed. `[C]`+`[P]`.
4. **The split is non-redundant** (r = 0.23): `ΔH_solution` and `ΔH_tests` carry distinct
   information. A hygiene metric that wants to track test-suite structure should measure
   `ΔH_tests` directly rather than assume it follows the solution's disorder. `[C]`.

## 5. Honest limits

- **Join coverage is the binding limit.** 195/321 (60.7%) of measured cells have ΔH but no
  quadrant — they are a FAILED finding by the contract, recorded as such, never silently filled.
  The per-model distribution and the clean-but-wrong count are therefore conditional on the 39%
  join-complete subsample, and the `campaign` bucket (57% of it) is unattributable to a model.
- **The clean-but-wrong count of 1 is a floor.** The wall is defined by the join; the join is
  incomplete; the true prevalence among all 321 cells is unknown, not zero.
- **Small n and heterogeneity.** 54 story cells span seven models, three stories, and four
  perturbation conditions; per-model cells are in the single digits. No model-level claim is
  statistically meaningful here.
- **The β "curve" is 6 points, 2 of which are schema/probe artifacts.** It is not the concurrency
  ladder; the N² shape the operator's lived ceiling predicts is unmeasured.
- **ΔH threshold is a policy choice.** The sign-of-delta cut is the instrument's declared `[P]`
  default (the design leaves the cut unspecified); a different cut would move cells across the
  high/low boundary.
- **Entropy ≠ semantics.** ΔH measures structural disorder; the "wrong" in clean-but-wrong is
  established by `test_executed_success` alone. A behavior-preserving structural change (the 2d/2e
  lesson) can read "clean" here by construction.
- The neo4j-dependent family (the persistent code graph, the lineage walks, the trajectory graph)
  is out of scope — it waits for the fleet ladder's slice 3.

**LOG:** findings written from p2's committed outputs; 5 sections per the spec (methodology, ΔH,
β, implications, limits); every figure cited to `delta_entropy.json` / `coordination_overhead.json`;
the four-quadrant contract and measured-not-estimated rule carried through. **PASS.**
