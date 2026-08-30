---
status: accepted
---

# cap_2b — design: the randomized live pilot (static vs adaptive verification)

**Status: accepted** · Predecessor: `cap_2a_rerun3` (the feasibility probe) +
`cap_evidence_integrity_design.md` §6 (Campaign 2) + the measured E_x campaign
(`cap_escalation_measurement` — E_x(sol)=11.47, E_x(sonnet)=12.51).

## 1. What this campaign is

2b as designed: **randomized static-vs-adaptive on live cells**, establishing outcome
non-inferiority under adaptive control — the counterfactual 2a/rerun3 could not provide
(they ran one arm with applied=false or paired both arms without randomization). The five
prerequisites (restated in every verdict since rerun2) are met HERE, in order:

1. **Randomized static-vs-adaptive assignment** — block-randomized by stimulus, seeded, 50/50.
2. **Pre-registered non-inferiority margin + outcome metric** — committed BEFORE any cell runs
   (p0; the margin is unregistered nowhere else — this campaign is where it gets registered).
3. **Independent test execution** — runtime.test_runner verdicts + the post-hoc evaluator on
   immutable commits; never model self-report.
4. **Budget/SLA guard** — the adaptive arm's rework capped at ONE pass per cell; per-cell
   timeout; campaign stop budget.
5. **Outcome non-inferiority under adaptive control** — the decision rule applied in the
   verdict.

## 2. The pre-registration (p0 — committed before data collection, the research-first rule)

p0 commits `docs/experiments/preregistrations/cap_2b_preregistration.md` containing, with no placeholders:

- **Primary outcome metric**: cost-per-accepted-outcome (cpvo = total cost / accepted
  outcomes, the site KPI; accepted = test_runner verified + post-hoc evaluator defect
  determination). Secondary: verified-success rate.
- **Non-inferiority margin**: adaptive cpvo <= 1.10 x static cpvo AND adaptive
  verified-success rate >= static rate - 5 percentage points. (Pre-registered here; chosen
  from the measured effect prior: one applied rework converts a rejected outcome at a
  $0.005719 premium vs ~$0.0461 avoided escalation at the measured E_x=11.47 — an ~8x
  value/premium ratio, comfortably inside a 10% margin.)
- **Power analysis**: n of defect-bearing cells for 80% power at alpha=0.05 one-sided, using
  the measured effect (the base rate of defect-bearing changes in the stimulus family is
  known: 1/3 by construction; the analysis states the total cell count accordingly, with the
  minimum defect-bearing cells required, e.g. >= 6).
- **Randomization scheme**: block-randomized by stimulus (clean/critical/style), seed committed
  in the pre-registration, 50/50 static/adaptive within each block, repetitions per block from
  the power analysis.
- **Analysis plan**: per-arm cpvo + verified-success; the decision rule (non-inferior if the
  cpvo ratio <= 1.10 AND the success-rate gap <= 5pts, both with the n and CI stated);
  sensitivity: E_x at 11.47 and 28 in the asymmetric-loss table.
- **Authorization boundary**: non-inferiority here authorizes DESIGN REVIEW of continuing
  adaptive selection — nothing else.

## 3. Arms and cells

- Arms: `static` (proposals recorded, NEVER applied) vs `adaptive` (proposals APPLIED: rework
  = one bounded pass over the proposal scope, verify = one pass, continue = null). The
  treatment (`build_verify_proposal` etc.) is code-unchanged — the merged measurement fixes
  (scope, expected-effects, severity) are consumed as-is.
- Cells: the cap_2a_cell family (clean/critical/style — the established stimulus set, with
  the known 1/3 defect base rate) x repetitions from the power analysis x 2 arms, randomized.
- Independent outcomes: test_runner + the rerun3 value evaluator components (verification
  surface, severity-filtered static quality, rework passes, defect presence).

## 4. Phases

p0_preregister (committed BEFORE any cell; gates everything) -> p1_measure_one (E4, one
static cell) -> p2_run_randomized_cells (the block-randomized grid, fresh worktrees, unique
FINOPS_CELL_IDs, proposals recorded before outcomes) -> p3_score (cpvo per arm, verified-
success, the decision rule, asymmetric loss at E_x 11.47/28) -> p4_verdict (non-inferiority
decision + authorization statement) -> p5_adversarial (arm-contamination, randomization
integrity, application provability, pre-registration adherence — a deviation from the
pre-registered plan is a FAILED finding, not a limitation).

## 5. Acceptance criteria

1. The pre-registration is committed before any cell runs (provable by commit order).
2. Randomization integrity: the assignment table is derivable from the committed seed + block
   scheme; arm labels match the assignment (p5 attacks this first).
3. Every adaptive-arm application is provable (rework/verify/null in the commit trail).
4. The decision rule is applied with n + CI; no authorization beyond design review.
5. The asymmetric-loss table at the measured E_x (11.47) and the sourced 28.
