# cap_2a_rerun2 — calibration verdict (2b gate) + the fitted v2 mapping

**Source revision:** `4625ffe8014fb3752a317df90aa92c0179449e25` (the p4 commit where the score lives; this verdict is written at the same revision).

**Spec version:** `cap_2a_rerun2@0.1` (campaign spec, `workflows/repository/cap_2a_rerun2.yaml`); the three cell specs are `cap_2a_cell_clean@0.1`, `cap_2a_cell_critical@0.1`, `cap_2a_cell_style@0.1`.

**Candidate-manifest SHA256:** `c7a1afcec2ad246f5b68a11d4c95b61dd3060a6d20e957af030c7ddf79c56f4e` (`experiments/results/cap_2a_rerun2/p2_candidate_manifest.json`).

## p4 JSON provenance (every number below cites one of these)

| File | SHA256 |
|---|---|
| `experiments/results/cap_2a_rerun2/cap_2a_rerun2_score_20260826T015846Z.json` (schema `cap_2a_score/v1`) | `ef42f8b0ae07704cc693c51243dc755807586b0b745365d606e76410b19dd1ec` |
| `experiments/results/cap_2a_rerun2/p4_validation.json` (schema `cap_2a_p4_validation/v1`) | `a2fd71fde21ef2563debd497fbd6224761c89365a05cbca64bf89ac87dd3375b` |

The p2/p3 input artifacts (cell manifests, phase ledgers, outcomes, the p3 execution
manifest) are the score JSON's `input_artifacts` + `cells[]`; their SHA256s live in that JSON.
Proposal SHA256s are in the cells table below.

## Cells table

| cell_id | spec | model/backend | baseline | analyzed | graph | sonar | lsp | forecast | actual | proposal (action/depth/scope) | valid | realized outcome (depth, \|set\|) | hit | blast err |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `cap2a_p2_clean` | `cap_2a_cell_clean@0.1` | deepseek-v4-pro / opencode | `00193d8b` | `79379b38` | available | available | available | $0.02575 | $0.012875 | continue / 0 / `[]` | yes | no_rework (0, 0) | **hit** | 4 |
| `cap2a_p3_critical` | `cap_2a_cell_critical@0.1` | deepseek-v4-pro / opencode | `6c871900` | `7d4be302` | available | available | available | $0.02575 | $0.016623 | rework / 3 / 4 syms | yes | targeted_rework (1, 1) | **miss** | 3 |
| `cap2a_p3_style` | `cap_2a_cell_style@0.1` | deepseek-v4-pro / opencode | `6c871900` | `9b5f39e7` | available | available | available | $0.02575 | $0.01131 | continue / 0 / `[]` | yes | no_rework (0, 0) | **hit** | 4 |

- Full revisions, proposal_ids, `code_change_risk` (`0.18` / `0.215` / `0.18`), and the per-cell `new_sonar_critical_count` (`0` / `1` / `0`) are in the p4 score JSON `cells[]` rows; short SHA prefixes shown for readability.
- Proposal SHA256s: clean `dfc85f15b306de84` → `1e27671f7ed775993c9bfba918451a6ca9aa4337382dbfc76b24f342749f5e71`; critical `49755e5691ee9909` → `ca794e9140c4c4c183793399c2761ce8044b910696bf0cf9a7b68b00abb69787`; style `cb75c4af8cd89a24` → `41e266081bc19b232665d3dcc9d08acffeee42bb691cf772e3206386dcbe3b1d`.
- Every proposal validated `applied=false`, schema `verify_code_change_proposal/v1`, contract `verify_code_change/v1` (p4 `proposal_validation_rate=1.0`).
- `blast err` = `abs(predicted_impacted_symbol_count − len(realized_symbol_set))`: clean `|4−0|=4`, critical `|4−1|=3`, style `|4−0|=4`.
- Cumulative actual `$0.040808` vs forecast envelope `$0.0515`; no cell stopped.
- No graph-down or analyzer-down cells: graph, sonar (`127.0.0.1:9000`), and lsp (mypy 2.3.1) were available on every cell — the rerun's lsp-unavailable gap is closed.

## Analysis

- **proposal hit-rate** = `2 / 3` = **0.6667** (p4 `aggregates.n_hits / aggregates.n_scored`).
- **Wilson 95% interval** = **[0.2077, 0.9385]** (p4 `aggregates.wilson_95_ci`).
- **Denominators (printed):** `n_scored=3`, `n_unknown_outcome=0`, `n_invalid_join=0`, `n_not_run=0` (p4 `aggregates`). `n_scored + n_unknown + n_invalid + n_not_run == n_ran = 3`.
- **graph-down rate** = `0/3`; **analyzer-down rate** = `0/3` (p4 `aggregates.graph_unavailable_rate=0.0`).
- **outcome-recorded rate** = `1.0`; **proposal-validation rate** = `1.0` (p4 `aggregates`).
- **risk_mint_rate** = `1.0` (`3/3` cells minted a non-None `code_change_risk`) — p4 `aggregates.risk_mint_rate`.
- **predicted-vs-observed blast radius** = mean `3.6667`, median `4`, `n_available=3` (p4 `aggregates.blast_radius`).
- **risk calibration** (p4 `calibration.risk_buckets`): `[0.15,0.30)` → 2×`no_rework` + 1×`targeted_rework`; `[0,0.15)` and `[0.30,∞)` are empty. Counterfactual design — **not** causal or predictive.

## The fitted mapping (design doc §F2 — this campaign's core deliverable)

Read off the p4 `calibration` block, the empirical v2 mapping is:

1. **The BLOCKER/CRITICAL change-introduced count is the discriminating signal, and its separating threshold in this sample is T = 1.**
   `new_sonar_critical_count = 0 → realized no_rework` (clean and style, 2/2); `= 1 → realized targeted_rework` (critical, 1/1). The count, not the risk number, separates rework from no-rework: risk `0.215` (rework) vs `0.18` (no-rework) are adjacent, while the count is a clean `{0, ≥1}` split (p4 `calibration.finding_outcome`).

2. **The v1 rework branch is confirmed; keep it.** `new_sonar_critical_count > 0 → rework/depth 3` was correct in the one cell that exercised it — the S3776 CRITICAL finding (a real maintainability defect in `classify`) realized `targeted_rework`. No change to this leg.

3. **MAJOR-only changes realize no_rework; v2 must map them to verify-or-continue, never rework.** The style cell minted 5× `python:S1244` (MAJOR) and the server-side `severities=BLOCKER,CRITICAL` filter returned `0` — so `new_sonar_critical_count=0` and the proposal was `continue`, which hit. This is the severity-conflation fix as data (p4 `calibration.severity_strictness`): the rerun's p3b minted `1` for the identical finding and over-predicted `rework`.

4. **The scope prediction is the remaining defect, and it is structural.** The one miss is a *scope* miss, not an action miss: the rework proposal's scope is the executor **neighborhood** `[add, subtract, test_add, test_subtract]` (the 1–2-hop dependents), which excludes the changed symbol `{classify}` itself. Under the fixed hit rule ("rework hits targeted/broad_rework only when scope contains the realized scope"), a correct rework action still misses. **Prescription for the next campaign:** the proposal scope must be seeded with the typed CodeDelta's added/changed symbols (the changed set), not only the reachable dependents — otherwise no symbol-level change can ever hit a rework outcome.

5. **The risk→depth ramp remains UNFITTED (exact n needed).** All three cells landed in `[0.15,0.30)`, and no cell realized `verification_only`, so the `_risk_depth` 0.15/0.3 ramp and `VERIFY_RISK_THRESHOLD=0.2` are still "deliberately not fitted to any data" (the v1 docstring's own admission). To fit them, the next campaign needs cells that (a) realize `verification_only` — a change that is verify-worthy but not rework-worthy — and (b) span the risk buckets (a `risk<0.15` cell and a `risk≥0.3` cell). With the current 3 rows all in one bucket, the count-threshold mapping (1–4) is fitted, the risk-threshold mapping (5) is not.

## Verdict

**The 2b calibration threshold (hit-rate ≥ 0.6) is met as a point estimate — 0.6667 (2/3) — but is NOT a statistical clearance.** Wilson 95% = **[0.2077, 0.9385]** straddles 0.6 with **n=3**, so the result is **descriptive-only**: it authorizes nothing and does not launch 2b. 2b is now **eligible for design review** (it has NOT run).

- **The severity-conflation blocker is fixed and measured.** The rerun's root cause (`new_sonar_critical_count` counting MAJOR bug-type findings) is gone: the style cell's 5 MAJOR findings mint `0`, and the critical cell's 1 CRITICAL finding mints `1` (p4 `calibration.severity_strictness`).
- **Over-prediction shrank and moved.** The rerun over-predicted on all 3 cells (verify/rework against no_rework). rerun2 has **0 action over-predictions** (continue→no_rework correct 2/2; rework→targeted_rework action correct 1/1). The remaining miss is a **scope** miss on the rework leg (item 4 above) — the verifier now proposes the right *kind* of action, but names the wrong *set* of symbols for rework.
- **Additional valid outcomes are still needed** for anything beyond description: with n=3 the interval is `[0.2077, 0.9385]`; reaching a lower bound above 0.6 requires a materially larger n with the hits holding.

## Comparison with the rerun (over-prediction shrank, moved — with the numbers)

| | rerun (`cap_2a_rerun`) | rerun2 (`cap_2a_rerun2`) |
|---|---|---|
| risk minted | 3/3 (`risk_mint_rate=1.0`) | 3/3 (`risk_mint_rate=1.0`) |
| hit-rate | **0.0** (0/3) | **0.6667** (2/3) |
| Wilson 95% | [0.0, 0.5615] | [0.2077, 0.9385] |
| action over-prediction | 3/3 (verify×2 + rework on no_rework) | **0/3** |
| S1244 MAJOR handling | drove a `rework` (severity conflation) | mints `new_sonar_critical_count=0` → `continue` |
| residual defect | over-prediction (action) | **scope miss** (rework scope excludes the changed symbol) |
| analyzers | lsp unavailable (pyright broken) | **all available** (mypy pinned) |

The over-prediction **shrank** (3/3 → 0/3 action over-predictions) and **moved** (from a wrong *action* to a wrong *scope*). The severity fix held; the scope prediction is the new, now-measured blocker for the rework leg's hit-rate.

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

**LOG:** hit-rate 2/3 (Wilson [0.2077, 0.9385]); blast-radius delta mean 3.6667 / median 4; `risk_mint_rate=1.0`; flagged cells: none (no graph-down, no analyzer-down, no invalid-join, no unknown). **PASS** — the verdict is issued, the fitted v2 mapping is stated, and the gate is honestly reported descriptively met (not a statistical clearance).
