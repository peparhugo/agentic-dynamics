# cap_2a_rerun — calibration rerun verdict (2b gate)

**Source revision:** `5c23cbf07a7b6374a0b19054173949781e2a7a83` (the commit where all p2/p3 artifacts live; this verdict is written at `fae8ef2d2`).

**Spec version:** `cap_2a_rerun@0.1` (campaign spec); the two bespoke cell specs are `cap_2a_calibration_cell@0.1` and `cap_2a_calibration_cell_divide@0.1`.

**Candidate-manifest SHA256:** `62af69cd940dc30286528325773452279b2bffe4d94835713354cdba1c3ac126` (`experiments/results/cap_2a_rerun/p2_candidate_manifest.json`).

## p4 JSON provenance (every number below cites one of these)

| File | SHA256 |
|---|---|
| `experiments/results/cap_2a_rerun_score_20260826T001107Z.json` (schema `cap_2a_score/v1`) | `59bd15d8b70d11e106aa5569735f9371a5476e1c89b6061fcc39fa55e3225497` |
| `experiments/results/cap_2a_rerun/p4_validation.json` (schema `cap_2a_p4_validation/v1`) | `690e0878776f34ba86ce5dfda3f48409c6f7ac85b248089bfb75a2959ab48957` |
| `experiments/results/cap_2a_rerun/cap2a_p2_bespoke_outcome.json` | `1307c0ca967033faa9d4b471ca91e9717895f0432050135302575017763880cf` |
| `experiments/results/cap_2a_rerun/p2_phase_ledger.json` | `ab0bf33423802c072595c7047c149ba5b8ff9f6547152e560ea8de839d9cde69` |
| `experiments/results/cap_2a_rerun/p3_execution_manifest.json` | `2cf106b6f563db3c2f9314201a2b63566460f7b09ed45a6f87f021c6d819c518` |
| proposal artifacts (per cell, below) | see cells table |

## Cells table

| cell_id | spec | model/backend | baseline | analyzed | graph | sonar | lsp | forecast | actual | proposal (action/depth/scope) | valid | realized outcome (depth, \|set\|) | hit | blast err |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `cap2a_p2_bespoke` | `cap_2a_calibration_cell@0.1` | deepseek-v4-pro / opencode | `4c9d8525` | `f5547d56` | available | available | unavailable | $0.017156 | $0.008578 | verify / 2 / 4 syms | yes | no_rework (0, 0) | miss | 4 |
| `cap2a_p3a` | `cap_2a_calibration_cell@0.1` | deepseek-v4-pro / opencode | `e8339c05` | `790eb68b` | available | available | unavailable | $0.017156 | $0.007816 | verify / 2 / 4 syms | yes | no_rework (0, 0) | miss | 4 |
| `cap2a_p3b` | `cap_2a_calibration_cell_divide@0.1` | deepseek-v4-pro / opencode | `17142923` | `e136ce25` | available | available | unavailable | $0.017156 | $0.008232 | rework / 3 / 4 syms | yes | no_rework (0, 0) | miss | 4 |

- Full revisions, proposal_ids, proposal SHA256s, and code_change_risk values are in the p4 score JSON `cells[]` rows; the short SHA prefix is displayed here for readability only.
- Every proposal validated `applied=false`, schema `verify_code_change_proposal/v1`, contract `verify_code_change/v1`.
- `blast err` = `abs(predicted_impacted_symbol_count − len(realized_symbol_set))` = `|4 − 0| = 4` for each cell (realized set empty — no rework was actually needed).
- Cumulative actual cost `$0.024626` vs forecast envelope `$0.051468`; no cell stopped.

## Analysis

- **proposal hit-rate** = `0 / 3` = **0.0** (p4 `aggregates.n_hits / aggregates.n_scored`).
- **Wilson 95% interval** = **[0.0, 0.5615]** (p4 `aggregates.wilson_95_ci`).
- **Denominators (printed):** `n_scored=3`, `n_unknown_outcome=0`, `n_invalid_join=0`, `n_not_run=0` (p4 `aggregates`). `n_scored + n_unknown + n_invalid + n_not_run == n_ran = 3`.
- **graph-down rate** = `0/3` (all `graph_status=available`); **analyzer-down** = lsp `unavailable` on all 3 cells (pyright not installed — `new_lsp_error_count` omitted, never fabricated).
- **outcome-recorded rate** = `1.0`; **proposal-validation rate** = `1.0` (p4 `aggregates`).
- **risk_mint_rate** = `1.0` (`3/3` cells minted a non-None `code_change_risk`) — p4 `aggregates.risk_mint_rate`.
- **predicted-vs-observed blast radius** = mean `4.0`, median `4`, `n_available=3` (p4 `aggregates`); the verifier predicted a 4-symbol blast radius, the realized rework set was empty in every cell.
- **risk calibration** (p4 `aggregates.risk_calibration`): `[0.15,0.30)` → 2×`no_rework`; `[0.30,0.60)` → 1×`no_rework`. Counterfactual design — **not** causal or predictive.

## Verdict

**The raw 2b calibration threshold (hit-rate >= 0.6) is NOT met.** hit-rate = **0/3** with Wilson 95% interval **[0.0, 0.5615]**; even the upper confidence bound (0.5615) is below 0.6, and **n=3** is below any declared minimum — the result is **descriptive-only** and is not an authorization.

- **p1's wiring worked.** `risk_mint_rate = 1.0` — `code_change_risk` was minted for every ran cell (sonar available, lsp unavailable-but-measured, graph available). The first campaign's named blocker (risk never minted → `record_verify_proposal` refused → zero proposals → hit-rate undefined at n=0) is **fixed and measured**.
- **The blocker moved, not cleared.** The adaptive verifier now emits proposals, but every proposal predicted more intervention than the baseline needed: `verify`/`rework` proposed against a `no_rework` realized outcome in all 3 cells. The sharpest case is `cap2a_p3b`: sonar's `new_sonar_critical_count=1` (rule `python:S1244`, a floating-point-equality style flag on a *test*, not a defect) drove a `rework`(depth 3) proposal while the implementation was correct and 4/4 tests passed. **The verifier's action/depth/scope calibration is the current blocker.**
- **Additional valid outcomes needed:** to reach 0.6 at n=10 with the lower bound above 0.6 would require ≥ 6 additional hits — but additional data alone cannot fix an over-prediction bias; the verifier needs a calibration change (e.g. treat `new_sonar_critical_count` severity/domain-sensitivity, or require criticals to be *newly introduced by this change*, not pre-existing test-style findings) before re-running cells.

## Comparison with the first campaign

| | first campaign (`cap_2a_shadow_calibration`) | rerun (`cap_2a_rerun`) |
|---|---|---|
| risk minted | 0 cells (risk `None`/omitted everywhere) | **3/3 cells (`risk_mint_rate=1.0`)** |
| proposals emitted | 0 (seam refused; n=0) | 3 (`verify`×2, `rework`×1) |
| hit-rate | undefined (n=0) | **0.0** (n=3, Wilson [0.0, 0.5615]) |

The fix path **worked** for the blocker it was built for (sonar+lsp wired → `code_change_risk` mints → the proposal seam emits). The campaign then surfaces the *next* problem: the verifier's proposals do not yet predict the realized outcome (hit-rate 0/3), so the 2b gate remains **not met** — for a different, now-measured reason.

## 2b prerequisites (restated, mandatory — per design §6)

2b launches only after ALL of these are met, and only after an explicit design review — p5 itself never launches a run, flips `control_route`, or arms actuation:

1. **Randomized static-vs-adaptive assignment** on live runs (no self-selection).
2. **Pre-registered non-inferiority margin + outcome metric** declared before data collection.
3. **Independent test execution** (the `runtime.test_runner` verdict, never a model self-report).
4. **Budget/SLA guard** on the adaptive arm.
5. **Outcome non-inferiority under adaptive control** (the adaptive arm must not be worse than the static baseline).

The counterfactual 2a design cannot provide any of these; they are the gating conditions for 2b.

## Guard

Every number above cites a field of the p4 score JSON (paths named inline). No recommendation is made without n, denominator, uncertainty, and flagged-cell treatment. No 2b authorization is implied by this verdict.

**LOG:** hit-rate 0/3 (Wilson [0.0, 0.5615]); blast-radius delta 4 (all cells); `risk_mint_rate=1.0`; flagged cells: 3× lsp-unavailable (none graph-down, none invalid-join, none unknown). **PASS** — the verdict is issued and the gate is honestly reported NOT met.
