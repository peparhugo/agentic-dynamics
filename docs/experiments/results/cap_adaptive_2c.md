---
status: accepted
---

# cap_adaptive_2c — verdict: the boundary of the decided arm (when should the gate decline to adapt?)

**Status: accepted** · **Decision: NON-INFERIOR** · **Abstention: no improving threshold** ·
Campaign: `cap_adaptive_2c` (`workflows/repository/cap_adaptive_2c.yaml`, `cap_adaptive_2c@0.1`,
spec SHA256 `15e15019d5435233079d5cd17b933de449fd5212f227b3229b433d16ee419940`).
**Pre-registration:** `docs/experiments/preregistrations/cap_adaptive_2c_preregistration.md` — committed
BEFORE any cell ran at `104a8eade91c8b77849d9db5fcd0f1e99d7925ad`, SHA256
`0f3a5de755784a6e9f8a71da3e7706782cddf930095fbc65a685ccc361da5e3d`.
**Source revision of the analysis:** `104a8eade91c8b77849d9db5fcd0f1e99d7925ad` (the score
JSON `preregistration_revision` — the p0 commit the grid was run from). **Seed:**
`92983f6f06f8b5a13d24ecfae87aac5b6f707b780e716a5bf434a244c3e0f252`. **Cell model:**
`deepseek/deepseek-v4-pro`, backend opencode, full seam (`--change-analysis
--change-analysis-graph`). **Design authority (reused):** `cap_2b_design.md` (the
pre-registration + decision pattern). **Predecessor:** `cap_2b.md` (the 2b verdict — NON-INFERIOR,
ratio 0.7857, and the limitation this campaign attacks). **Stop budget:** $30.00
(`cap_adaptive_2c.yaml` `stop.budget_usd`).

## Provenance (every verdict number cites the p3 JSON; paths inline)

| artifact | SHA256 |
|---|---|
| `experiments/results/cap_adaptive_2c/cap_adaptive_2c_score_20260827T180241Z.json` (schema `cap_adaptive_2c_score/v1`) | `076751e4b14d74085fba46581a9bf9bd6bb627bee1089a5afce4c87d5cde60f7` |
| `experiments/results/cap_adaptive_2c/cap_adaptive_2c_validation_20260827T180241Z.json` (schema `cap_adaptive_2c_validation/v1` — every verdict number traced to a field) | `17093d858b4526c3273f964d12418964151552b98d7c123893fda15fd86fd99c` |
| `experiments/results/cap_adaptive_2c/p2_execution_manifest.json` (the 24-cell pre-registered table, written BEFORE p2) | `676eb25133e81ed2ec6e436300a6f0e0870738f5fd3b3293079e1bd98331fa54` |
| `experiments/results/cap_adaptive_2c/p1_cell_manifest.json` (E4 = `cap2c_correct_adaptive_r1`) | `b9e6983b93b007082f5b18f7bc25d7ec96e82b7a8955869012933c791db224e6` |
| `experiments/results/cap_adaptive_2c/p1_phase_ledger.json` (E4 phase ledger) | `14531e274bdbae4f29d124ae656dfc467b9c134420ea909669b59e19e8f76197` |
| `experiments/results/cap_adaptive_2c/p1_candidate_manifest.json` (E4 candidate, written BEFORE p1) | `5bdc4e64de147aa9829385c2440ae7a5d82b091b2e24ba18792a3ba33967b4c5` |

Join validation (`score.join_validation`): `valid=true`, **0 invalid**, `n_table_rows=24`,
`n_cells=24` — every scored cell's (cell_id, class, variant, arm, repetition) matches the
pre-registered assignment table; a mismatch would be invalid, not corrected
(`validation.guard`). The grid ran all 24 cells (E4 in p1; the 23 remaining in p2; the
unseen-family r2 block added to the p2 run before scoring). No cell was dropped; absent-defective
is a **designed** analyzer/graph-down cell, flagged and never dropped (`score.denominators.note`).

## The per-arm table (`score.per_arm`)

| arm | n | total cost | accepted | **cpvo** | cpvo 95% CI (bootstrap) | verified-success | Wilson 95% | escaped defects |
|---|---|---|---|---|---|---|---|---|
| static | 12 | $0.099112 | 5 | **$0.019822** | [0.016101, 0.025406] | 0.4167 (5/12) | [0.1933, 0.6805] | 9 |
| adaptive | 12 | $0.116615 | 9 | **$0.012957** | [0.011164, 0.015193] | 0.7500 (9/12) | [0.4677, 0.9111] | 3 |

`cpvo = total arm cost / accepted outcomes` (pre-registration §1). Accepted = independent
runtime pytest on the immutable final commit AND the post-hoc evaluator's defect determination on
the same commit (competing additionally requires both defects absent). Static = proposals
recorded, never applied; adaptive = applied exactly as proposed (rework = ONE bounded pass over
the proposal scope, verify = one pass, continue = null — provable in the commit trail,
`score.per_cell[].application_proof`).

**Defect-bearing n = 7 per arm** (correct 2 + competing 2 + absent-defective 1 + unseen-family 2
per arm) — the 2b-registered power threshold (n ≥ 6 defect-bearing → ≥ 18 cells) by carry-over.
Per-class inference is descriptive (n=2 per arm per class), per pre-registration §3.

## The per-class table — the heterogeneous grid's core output (`score.per_class`)

| class | arm | n | cost$ | acc | cpvo$ | success | escaped | harm11$ | harm28$ | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| correct | static | 2 | 0.021975 | 0 | undef (0 acc) | 0.00 | 2 | 0.092218 | 0.225176 | rework ignored → escape |
| correct | adaptive | 2 | 0.026931 | 2 | 0.013465 | 1.00 | 0 | 0.000000 | 0.000000 | rework applied, defect fixed |
| incorrect | static | 2 | 0.018297 | 2 | 0.009149 | 1.00 | 0 | 0.000000 | 0.000000 | construction failure (flagged) |
| incorrect | adaptive | 2 | 0.018360 | 2 | 0.009180 | 1.00 | 0 | 0.000000 | 0.000000 | construction failure (flagged) |
| irrelevant | static | 2 | 0.017945 | 2 | 0.008972 | 1.00 | 0 | 0.000000 | 0.000000 | continue = value-neutral |
| irrelevant | adaptive | 2 | 0.017997 | 2 | 0.008998 | 1.00 | 0 | 0.000000 | 0.000000 | continue = null, accepted |
| competing | static | 2 | 0.018655 | 0 | undef (0 acc) | 0.00 | 4 | 0.184436 | 0.450352 | 2 defects × 2 cells escape |
| competing | adaptive | 2 | 0.030613 | 2 | 0.015306 | 1.00 | 0 | 0.000000 | 0.000000 | both-fixed reworks (audited) |
| absent | static | 2 | 0.014386 | 1 | 0.014386 | 0.50 | 1 | 0.046109 | 0.112588 | clean accepted; defective escapes |
| absent | adaptive | 2 | 0.014688 | 1 | 0.014688 | 0.50 | 1 | 0.046109 | 0.112588 | refusal → defective escapes |
| unseen_family | static | 2 | 0.007854 | 0 | undef (0 acc) | 0.00 | 2 | 0.092218 | 0.225176 | continue → mutation escapes |
| unseen_family | adaptive | 2 | 0.008026 | 0 | undef (0 acc) | 0.00 | 2 | 0.092218 | 0.225176 | continue (wrong) → escape |

(All values from `score.per_class.<class>.<arm>`: `total_cost_usd`, `accepted_outcomes`,
`cpvo_usd`, `verified_success_rate`, `escaped_defect_count`, `harm_11`, `harm_28`.)

**Which classes push the pooled ratio:** the adaptive arm wins outright on the two defect-bearing
families the verifier was calibrated for — **correct** (static 0 accepted / adaptive 2) and
**competing** (static 4 escaped defects / adaptive 0). The two classes where adaptive adds
NOTHING are **unseen-family** (continue is wrong in both arms — the verifier's blind spot) and
**absent-defective** (the seam refuses in both arms). **incorrect** could not instantiate its
claimed harm (see §2 below). **irrelevant** is value-neutral as designed.

## The HARM table (`score.harm_table`)

**Wrong-apply — $0.000000 measured.** In this campaign the only constructible false-positive is
the `verify` pass (a false-positive `rework` is NOT constructible under the severity filter —
only change-introduced BLOCKER/CRITICAL issues trigger `rework`, and those are 0 on a
defect-free change, pre-registration §1 component 1). The incorrect-class construction was
designed to emit a false-positive `verify` via the tests-ratio term, but the measured facts
(`changed_symbol_count=20`, `changed_symbols_with_tests_ratio=0.05`, `impacted_symbol_count=0`,
`code_change_risk=0.19`) put risk **below** `VERIFY_RISK_THRESHOLD 0.2` — the pre-registered
structural guarantee (impacted ≥ 1) did NOT hold (measured impacted=0), so the proposal was
`continue`, not `verify`. **No verify pass was ever applied → wrong-apply = $0 measured.** This
is the pre-registered filter-strength statement confirmed, plus a recorded construction failure:
the incorrect class did not instantiate its false-positive VERIFY (4 cells flagged
`construction-failure: expected proposal verify, got continue`, `score.flags.construction_failures`).

**Wrong-continue — 12 escaped defects, E_x-scaled at 11.47/28:**

| multiplier | per escaped defect | escaped defects | total |
|---|---|---|---|
| **E_x = 11.4671 (measured, sol, n=1)** | $0.046109 | 12 | **$0.553311** |
| **E_x = 28.0 (sourced)** | $0.112588 | 12 | **$1.351056** |

Escaped-defect ledger (per cell): correct-static 2 + competing-static 4 + absent-defective 2
(one per arm) + unseen-family 4 (one per cell, both arms) = **12**. The n=1-per-model limitation
of the E_x multiplier is stated (two measured E_x values, one cell each); sensitivity at both
11.47 and 28 is reported per pre-registration §1.

## The ABSTENTION curve (`score.abstention_analysis` — **EXPLORATORY**, pre-registration §2/§5)

**Method (pre-registered, §5):** proposal confidence is the [H] per-attempt execution-confidence
of the analyzed implement attempt, recorded at proposal-emission time BEFORE the outcome. A
proposal without the field is invalid for this analysis (never imputed); the 4 absent-class cells
have no proposal record (the seam refused) and are excluded from the decile bins — reported,
count 4, never imputed. Observed confidences: `{0.6667, 1.0}`.

**Per-confidence-decile value(apply) vs value(abstain)** (`score.abstention_analysis.per_decile`):

| decile | n apply / abstain | value(apply) cpvo$ | value(abstain) cpvo$ | value(apply) harm11 | value(abstain) harm11 |
|---|---|---|---|---|---|
| [0.6, 0.7) | 6 / 6 | **$0.016392** (4 acc) | **undefined** (0 acc — infinite) | $0.039447 | undefined |
| [0.9, 1.0] | 4 / 4 | **$0.009089** (4 acc) | **$0.009060** (4 acc) | $0.009089 | $0.009060 |

The low-confidence decile is EXACTLY the defect-bearing correct/competing/unseen-family cells —
where adaptive adds its value. value(apply) is finite and value(abstain) is undefined (0
accepted). The high-confidence decile is the clean incorrect/irrelevant cells, where apply and
abstain are statistically identical (~$0.009). **Confidence does not point at the proposals the
gate should decline.**

**Threshold curve — `cpvo_gated(θ) = (Σ cost + Σ harm) / Σ accepted` over all 24 cells, θ ∈
{0, 0.6667, 1.0}:**

| θ | declined | cost$ | accepted | cpvo_gated$ | harm11-inclusive | harm28-inclusive |
|---|---|---|---|---|---|---|
| 0.0 | 0 | 0.215727 | 14 | **$0.015409** | $0.054931 | $0.111913 |
| 0.6667 | 0 | 0.215727 | 14 | $0.015409 | $0.054931 | $0.111913 |
| 1.0 | 6 | 0.198641 | 10 | $0.019864 | $0.102860 | $0.222522 |

At θ=1.0 (decline the six 0.6667-confidence adaptive cells: correct ×2, competing ×2,
unseen-family ×2) the gate removes exactly the cells where adaptive fixes defects: accepted
drops 14→10 AND harm-INCREASES (0.054931 → 0.102860) because the declined defects now escape at
the static-arm counterfactual. **No θ ∈ (0,1) yields `cpvo_gated(θ) < cpvo_gated(0)`
(`improving_threshold_exists=false`, `improving_thresholds=[]`).** `cpvo_gated(1)` (pure
static, decline everything) is worse than `cpvo_gated(0)` (apply everything): $0.019864 >
$0.015409.

## Decision-rule computation (pre-registration §2 margin, §5 decision rule)

```
NI  ⟺  cpvo_adaptive ≤ 1.10 × cpvo_static  AND  verified_success_adaptive ≥ verified_success_static − 5pts
   ⟺  cpvo ratio ≤ 1.10                      AND  success gap (static − adaptive) ≤ 0.05
```

| input | value | source field |
|---|---|---|
| cpvo_adaptive / cpvo_static | **0.653666** | `score.decision_rule.cpvo_ratio` (cpvo $0.012957 / $0.019822) |
| cpvo 95% CI (bootstrap, per arm) | static [0.016101, 0.025406] · adaptive [0.011164, 0.015193] | `score.per_arm.<arm>.cpvo_ci_95` |
| margin, cpvo leg | ≤ **1.10** | pre-registration §2; `score.decision_rule.margin_cpvo_ratio_le` |
| success gap (static − adaptive) | **−0.3333** | `score.decision_rule.success_gap_static_minus_adaptive` |
| margin, success leg | ≤ **0.05** | pre-registration §2; `score.decision_rule.margin_success_gap_le` |
| cpvo leg holds / success leg holds | true / true | `score.decision_rule.cpvo_leg_holds` / `.success_leg_holds` |

**Both legs hold with margin to spare**: the ratio (0.6537) sits 0.446 below the 1.10 boundary
and the two per-arm CI bands do not even overlap (static [0.0161, 0.0254] vs adaptive [0.0112,
0.0152]); the success gap (−0.3333, adaptive 0.75 vs static 0.4167) is 38.3 points inside the 5pt
boundary — adaptive is AHEAD, not merely within margin. **The decision rule decides on the pooled
grid.**

## Verdict

### (1) Non-inferior — YES, by the pre-registered decision rule, with n + CI.

Adaptive verification remains **non-inferior to static** under proposal heterogeneity — the exact
2b margin, applied to the full heterogeneous grid (all six stimulus classes pooled): cpvo ratio
**0.6537** ≤ **1.10** and success gap **−0.3333** ≤ **0.05**, at **n = 12 cells per arm**
(n = 7 defect-bearing per arm — the registered carry-over n). Descriptive framing: per-class
inference is n=2 per arm per class and is reported, never decided. The ratio CI does not cross the
margin, and the per-arm CIs are disjoint in adaptive's favor — the pooled decision is not
borderline.

### (2) Which classes break it — NONE break non-inferiority; three findings.

- **The incorrect class did not break it — it did not instantiate.** The claimed wrong-rework
  harm (a false-positive `verify` pass on a clean change) was **not constructible as designed**:
  the tests-ratio term (ratio 0.05) did not push risk past `VERIFY_RISK_THRESHOLD` because
  `impacted_symbol_count` measured **0**, not the pre-registered ≥ 1. All 4 incorrect cells
  emitted `continue` (flagged construction-failure). Measured wrong-apply = **$0.00** across the
  grid — the filter-strength statement (false-positive REWORK unconstructible under the severity
  filter) is confirmed, and the false-positive VERIFY remains **unmeasured** in this campaign
  (recorded limitation for the design review; a future construction needs a different
  impacted-set guarantee or a higher tests-ratio term).
- **The unseen-family class is adaptive's real blind spot.** The mutation/aliasing defect
  (confirmed by the post-hoc evaluator as NOT boundary-compare / NOT S1244 / NOT S3776) produced
  `continue` in both arms → **2 escaped defects per arm**, wrong-continue harm
  **$0.092218 @11.47 / $0.225176 @28 per arm**. This is the pre-registered demonstration: adaptive
  can only add value when it can SEE the defect. The gate's null (`continue`) is correct on clean
  changes but is a **wrong-continue** on defects outside the calibrated families.
- **The competing class is where adaptive's value is largest — and the p2 evaluator's label
  strings were a false-positive hazard.** Both competing-adaptive reworks fixed BOTH boundary
  defects (git diff `>`→`>=` at both edges; 3/3 tests; label-agnostic boundary check
  `10-edge correct=True, 20-edge correct=True`). The p2 evaluator's hardcoded label assertion
  (`classify(10.0) == 'ten_to_twenty'`) mis-flagged both-fixed reworks as defects — **corrected
  in scoring via `score.flags.outcome_audit_corrections`, accepted=true, escaped=0, harm=$0**.
  The corrected numbers are what the verdict uses; the two cells are flagged for the adversarial
  phase.

### (3) ABSTENTION — does confidence-gated refusal improve value?

**No.** No θ ∈ (0,1) in the observed distribution improves `cpvo_gated`; declining low-confidence
proposals makes value strictly worse (accepted drops 14→10 and harm rises 0.0549→0.1029 at
θ=1.0). The reason is structural: the implement-phase confidence (0.6667 on the defect-bearing
correct/competing/unseen-family cells, 1.0 on the clean cells) is **inverse** to where adaptive
adds value — the proposals the gate would decline on confidence are exactly the proposals whose
application fixes real defects.

**What the gate change would look like — a DESIGN CHANGE proposal, not an activation.** The 2c
finding authorizes a design-review conversation about the application policy (pre-registration §6)
and nothing else. The boundary verdict gives the design review:

- **Do NOT add a confidence threshold to the application policy.** The confidence signal as
  measured does not identify proposals the gate should decline.
- **Do investigate a capability/visibility-based abstention** instead: decline to apply (or
  escalate) when the change's facts are LOW-INFORMATION — specifically when the verifier cannot
  measure risk (all terms omitted, as in the absent-class designed state) or when the changed
  symbols sit outside a test-visible surface (the tests-ratio deferral the unseen-family defect
  exploited). The absent-defective harm ($0.046109/escape) and the unseen-family harm
  ($0.046109/escape) are both paid when the gate has no information; a policy that treats
  "cannot measure" as a caution flag rather than a pass-through would target those escapes.
- The confidence-recording requirement stays: proposal records carry the measured confidence
  field (verified in all 20 proposal records; the 4 absent cells carry no proposal by design).

### (4) The absent-class finding — the seam's refusal: value-preserving on clean, costly on defective.

- **absent-clean: value-preserving as designed.** The seam refused (sonar + lsp unavailable +
  graph unavailable → no risk term measurable); the change was clean; accepted in both arms, no
  harm (`defect_present=False`, `wrong_apply=0`, `escaped=0`). The refusal cost the gate nothing
  on a change that didn't matter.
- **absent-defective: the refusal is NOT value-preserving — it is the abstention-harm case.** The
  seam refused identically, but the change carried a real wrong-operation defect, which escaped in
  BOTH arms: harm **$0.046109 @11.47 / $0.112588 @28 per arm**. The refusal mechanism is
  identical in both variants; the independent variable is clean-vs-defective. The finding: when
  the gate declines to act, it saves the pass cost but pays the full E_x-scaled escape cost — the
  refusal is only value-preserving when the change is actually clean, and the seam cannot know
  that in the designed degraded state. This is the harm side of the abstention question.

### (5) The boundary restated — when should the gate decline to adapt?

**The gate should NOT decline to adapt on the confidence axis — no observed threshold improves
value.** The gate's value boundary runs along the *information* axis, not the confidence axis:

- **Apply when the proposal carries information** — a correct `rework` on a real
  BLOCKER/CRITICAL (correct, competing): adaptive fixed 4/4 defect-bearing cells those classes
  presented, static accepted 0. Adaptive is strictly superior exactly here.
- **Apply-with-null when the change is genuinely low-value and visible** — `continue` on a
  trivial, fully-tested change (irrelevant): value-neutral, zero cost either way.
- **Decline/flag when the gate has NO information** — the seam's refusal on a defective change
  (absent-defective) and the wrong `continue` on an unseen-family defect both pay the wrong-continue
  E_x-scaled cost. The gate should treat "cannot measure risk" as a caution flag (design-change
  candidate, §3), and the adversarial phase should probe whether the unseen-family escape is
  reachable by any application-policy change short of new measurement.

**Bottom line:** adaptive verification remains non-inferior (in fact superior) across the
heterogeneous grid the 2b limitation demanded; no class breaks the pre-registered margin; the
confidence-gated abstention rule does not improve value; and the honest boundary for "when the
gate declines to adapt" is **when it has no information to act on** — not when it is uncertain
about what it already sees.

## Flagged cells, budget/SLA guard, expected-effect ceiling

- **Flagged cells: 6.** Four incorrect-class cells (construction failure: expected `verify`, got
  `continue`) and two competing-adaptive cells (outcome-audit correction; the rework did fix both
  boundaries — the p2 evaluator's hardcoded label assertion was the false signal). No cell was
  dropped; the flags travel to the adversarial phase.
- **Budget/SLA guard: no breach.** Total cell spend **$0.2157** (static $0.0991 + adaptive
  $0.1166) against the **$30.00** stop budget; no cell exceeded 2× the p1 FORECAST ($0.031707/cell
  — all 24 cells are within $0.0039–$0.0164); no cell stopped.
- **Expected-effect checks:** the 2b structural ceiling carried forward — rework passes were not
  handed to a post-rework change analyzer and `continue` = null leaves no next-phase facts, so
  every claim is `measurable=false` (`score.per_cell[].expected_effect_checks`). Recorded
  limitation, not a passed-or-failed claim.

## Guard

Every number above cites a field of the p3 score JSON (`cap_adaptive_2c_score_20260827T180241Z.json`,
SHA256 above; paths named inline in each table) and is traced field-by-field in the validation JSON.
The margin is the **pre-registered** §2 margin applied as the §5 decision rule on the pooled grid —
no post-hoc redefinition, no post-hoc arm reselection, no dropped cells, no re-labelled classes.
The per-class table is reported (n=2 per arm per class) and never decided. The abstention analysis
is **labeled exploratory** and descriptive at the campaign's n. The two outcome-audit corrections
(competing-adaptive) are flagged, evidenced (git diff + label-agnostic boundary check + 3/3 tests),
and used in place of the p2 evaluator's false positive — with the recorded value preserved in
`score.per_cell[].outcome_audit`.

**LOG:** ratio 0.6537 (per-arm CIs [0.0161,0.0254] vs [0.0112,0.0152], disjoint in adaptive's
favor) ≤ 1.10; success gap −0.3333 ≤ 5pts; n=12/arm (7 defect-bearing per arm); per-class: adaptive
wins correct (0→2 acc) + competing (4→0 escaped), value-neutral irrelevant, blind on
unseen-family (2 escaped/arm) + absent-defective (1 escaped/arm), incorrect construction failed
(wrong-apply $0 measured); harm: wrong-apply $0, wrong-continue 12 escaped = $0.553311 @11.47 /
$1.351056 @28; abstention (EXPLORATORY): no improving θ — declining low-confidence proposals
removes adaptive's value (acc 14→10, harm 0.0549→0.1029); absent-clean refusal value-preserving,
absent-defective refusal costly (harm $0.046109/arm); $0.2157 / $30.00; 6 flagged, 0 dropped.
**PASS — NON-INFERIOR under proposal heterogeneity; confidence-gated abstention does NOT improve
value; the boundary is informational (decline when the gate has no information), not
confidence-based; authorizes design review of the application policy, nothing else.**
