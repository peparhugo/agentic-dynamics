---
status: accepted
---

# Grit/Confidence Calibration Design — Verification Record

**Provenance [M]:** spot-checked directly against the cited artifacts in the working tree at
`799267d4a` (branch `feature/grit-calibration-design`, == `main`). The design doc is
**already committed in the parent tree** (`main` == `origin/main` == HEAD == `799267d4a`), so
the "commit the design doc" deliverable is satisfied by the existing commit
`799267d4a` ("grit/confidence calibration design (proposed)").

Doc: `docs/designs/proposed/cap_grit_confidence_calibration_design.md` (373 lines).
Frontmatter: `status: proposed` (line 2) — the contract layer, untouched (verify, never re-author).

## Five required parts — all PRESENT

| Part | Doc location | Verdict |
|---|---|---|
| (a) measured state: E4 G(s) curve, 2c decile null, [H] confidence definition | §1.1 (`cap_grit_grid_metrics.json` G(s)), §1.2 (`cap_adaptive_2c_score_*.json` deciles), §1.3 (confidence defn, `opencode.py`) | **PRESENT** |
| (b) two-decisions separation: retry-threshold vs verify-gate + why the 2c null does NOT constrain grit | §2.1 (the two-decision table), §2.2 (four numbered reasons) | **PRESENT** |
| (c) calibration design: models × strengths with held-out thresholds, cpvo_harm @ E_x 11.47 decision rule | §3.2 (2 models × 7 strengths, train/held-out split), §3.3 (θ* ∈ {0.4, 0.6, 0.8}), §3.4 (cpvo_harm @ E_x=11.4671, four support legs) | **PRESENT** |
| (d) relationship to the running campaigns: 2e owns the deepseek envelope | §4 — 2e (RUNNING) is single-owner; this design is the successor deepseek-envelope campaign; sonnet tranche parallel | **PRESENT** |
| (e) falsifiability contract | §5 — five independent REFUTE legs | **PRESENT** |

## Spot-checked citations (12, all RESOLVE)

1. **G(s) curve** — doc §1.1 `{0.0: 0.5, 0.2: 1.0, 0.5: 1.0, 0.8: 0.6667}` ==
   `cap_grit_grid_metrics.json` → `grit.produces.grit` (verified identical values).
2. **retention / grit_auc / recovery_premium** — doc `{0.0:1.0, 0.2:2.0, 0.5:2.0, 0.8:1.3333}`, `1.4`,
   `1.1277` == `grit.produces.retention` / `grit_auc` / `recovery_premium` (identical).
3. **E4 retry 1/1** — doc "bad_seed_high × grit_retry, a1 $3.6330 fail → a2 $3.1866 success,
   `retry_reason="first_attempt_test_failure"`, `parent_attempt_id`" ==
   `cap_grit_grid_ledger.json` `cells[7].attempts` (a1 `actual_cost` 3.6329759,
   `test_executed_success=false`; a2 `actual_cost` 3.1865708, `test_executed_success=true`,
   retry_reason + parent_attempt_id linkage present).
4. **Retry cell cost 2.2×, regret +$3.7501** — doc "$6.8195 vs $3.0694, per-cell regret +$3.7501"
   == ledger `cells[7].realized_cost` 6.8195467 vs high-baseline 3.0694191 (ratio 2.22) and
   `metrics.arm_comparison.stratified` bad_seed_high `routing_arm_regret` 3.7501, `better_arm` baseline.
5. **Stratified regret set** — doc low −$0.1841 (grit_retry), mid +$0.2618 (baseline), high +$3.7501
   (baseline) == `arm_comparison.stratified` rows (regrets −0.1841 / 0.2618 / 3.7501, better_arm matches).
6. **rework $0.00 on all 9 attempts** == `metrics.rework_cost_report[]` (per-cell 0.0).
7. **coverage + fidelity** — doc "cost 9/9 (1.0), test-verification 9/9 (1.0), retry_triggered_rate
   1.0, 0 violations" == `metrics.coverage` (9/9 both axes) + `metrics.retry_policy_fidelity`
   (`retry_triggered_rate` 1.0, `retry_policy_violations` []).
8. **realized cost $31.2733 vs $10 ceiling (3.1×)** == ledger `run_status.realized_total_cost_usd`
   31.2733, `budget_ceiling_usd` 10.0.
9. **2c observed confidences {0.6667, 1.0}** == `cap_adaptive_2c_score_*.json`
   `abstention_analysis.observed_confidences`.
10. **2c decile [0.6, 0.7)** — doc "value(apply) $0.016392 (4 accepted) vs value(abstain) undefined
    (0 accepted), harm 0.039447" == `per_decile["6"]` (value_apply_cpvo_usd 0.016392, n_apply 4
    accepted, value_abstain null, value_apply_cpvo_harm_11 0.039447).
11. **2c threshold curve** — doc "θ=0: cpvo_gated $0.015409, 14 accepted, harm11 0.054931; θ=1:
    $0.019864, 14→10, harm11 0.102860" == `threshold_curve[]` (θ=0.0 and θ=1.0 rows identical);
    `improving_threshold_exists=false`, `improving_thresholds=[]` == the doc's verdict.
12. **E_x harm model** — doc §3.4/§3.5 "E_x = 11.4671, harm = E_x × $0.004021 = $0.046109 @11.47 /
    $0.112588 @28" == `cap_escalation_measurement_score_20260826T125726Z.json`
    (`per_model[0].E_x` 11.4671, `base_downstream_defect_cost_usd` 0.004021, `loss_table` columns
    E_x 11.4671 → 0.046109 and E_x 28.0 → 0.112588). Arithmetic re-checked: 11.4671 × 0.004021
    = 0.046109, 28 × 0.004021 = 0.112588.
13. **2d confidence repeat** — doc "observed {0.6667, 1.0} again, improving_threshold_exists=false"
    == `cap_adaptive_2d_score_20260828T043139Z.json` `abstention_analysis` (identical).

## Verified definitions

- **[H] confidence** — `AgenticResult.confidence` at `src/agentic_dynamics/adapters/opencode.py:119`
  (doc cites `:113` — the property is one block below `correctness` at 119; same
  `AgenticResult` class, same docstring the doc quotes: 0.0 on session error, else
  `tests_passed/tests_total`, else tool-call success fraction, else `None`). Definition matches
  the doc's §1.3 text exactly.
- **`test_executed_success` / `perturbation_strength`** — `ledger_ingestion.py:180-181` confirmed.
- **E4 confidence gap** — `scripts/run_cap_grit_grid.py:129-159` `build_attempt_row` confirmed to
  write no `confidence` field; E4 ledger attempt rows carry `confidence: null` (the doc's §1.4
  gap claim is accurate).

## Verdict

**PASS.** All five required parts present; 13 spot-checked citations resolve to their cited
artifact fields; frontmatter `status: proposed` intact; doc already committed in the parent tree
(`799267d4a`). No FAILED finding. The design doc was **not** re-authored — verify-only.
