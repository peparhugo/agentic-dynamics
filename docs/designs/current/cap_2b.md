# cap_2b — verdict: the randomized static-vs-adaptive pilot (non-inferiority)

**Status: accepted** · **Decision: NON-INFERIOR** · Campaign: `cap_2b`
(`workflows/repository/cap_2b.yaml`, `cap_2b@0.1`) · **Pre-registration:**
`docs/designs/current/cap_2b_preregistration.md` — **committed BEFORE any cell** at
`19e47b60b57f6ff3c3d8b15cafa9daa2ac4b6cbe`, SHA256
`8259fe8d4776d7cb2c310348ea1315876eea74277d126e91fd74b98ef352c193`.
**Source revision of the analysis:** `19e47b60b57f6ff3c3d8b15cafa9daa2ac4b6cbe` (the score JSON
`source_revision` — the p0 commit the grid was run from).
**Design:** `docs/designs/current/cap_2b_design.md` (accepted). **Stimulus set:**
`cap_2a_cell_clean/critical/style@0.1`, model `deepseek/deepseek-v4-pro` (unchanged). **Cell
model budget/SLA guard:** campaign stop budget $30.00 (`cap_2b.yaml` `stop.budget_usd`).

## Provenance (every verdict number cites the p3 JSON; paths inline)

| artifact | SHA256 |
|---|---|
| `experiments/results/cap_2b/cap_2b_score_20260826T160018Z.json` (schema `cap_2b_score/v1`) | `5f24f5072f1bb0ab17769b8db3734680b83981c2506df3b57fffa529c42ed3d9` |
| `experiments/results/cap_2b/p3_validation.json` (schema `cap_2b_p3_validation/v1`) | `730ecfd4443e87033b4a0c4b6ebdb4040053aec6888dd161358815c24fc520ac` |
| `experiments/results/cap_2b/p2_execution_manifest.json` (the 18-cell candidate manifest, written BEFORE p2) | `7bb802e97efc3cb1b2e628147c92f3cb6b2c4abc7320fcf577e4a289ee33037c` |
| `experiments/results/cap_2b/p1_candidate_manifest.json` (the E4 candidate manifest, written BEFORE p1) | `c05c05b8a0f09f523c3abbab65466a5743181ea19b9d1c394719a6b3e5daf219` |
| `experiments/results/cap_2b/p2_manifest.json` (immutable p2 manifest + artifact SHA256 index) | `c4d849051d8c5beeaede881efae675f4f77d9c89482ca55b34a33644ffef51d7` |

Join validation (`score.join_validation`): `valid=true`, **0 errors**, `n_scored=18` — every
scored cell's arm/stimulus/repetition matches the pre-registered table; a mismatch would be
invalid, not corrected (`p3_validation.guard`). Assignment integrity independently confirmed in
`p2_manifest.assignment_integrity` (17/17 p2 cells checked, 0 deviations).

## The per-arm table (`score.per_arm`)

| arm | n | total cost | accepted | **cpvo** | cpvo 95% CI (bootstrap) | verified-success | Wilson 95% |
|---|---|---|---|---|---|---|---|
| static | 9 | $0.080062 | 6 | **$0.013344** | [0.011744, 0.014770] | 0.6667 (6/9) | [0.3542, 0.8794] |
| adaptive | 9 | $0.094364 | 9 | **$0.010485** | [0.009522, 0.011569] | 1.0000 (9/9) | [0.7008, 1.0000] |

`cpvo = total arm cost / accepted outcomes` (pre-registration §1). Accepted = independent
test_runner verified AND post-hoc evaluator defect-free on the immutable final commit
(`score.outcome_definition`, pre-registration §1). Static arm = proposals recorded, never
applied; adaptive arm = applied exactly as proposed (3 `rework` applied as ONE bounded pass
each — provable `[workflow] rework` commits, `score.per_cell[].application_proof`; the
remaining adaptive cells were `continue` → provable null).

## Defect-bearing n — the pilot's n (`score.defect_bearing`)

The stimulus family's defect base rate is 1/3 by construction (pre-registration §3), so the
6 critical cells are the pilot's **n = 6** (3 static / 3 adaptive), matching the registered
power requirement **n ≥ 6 defect-bearing → ≥ 18 cells**.

| arm | n defect-bearing | cost | accepted | cpvo | success |
|---|---|---|---|---|---|
| static | 3 | $0.026837 | 0 | undefined (0 accepted) | 0.0 |
| adaptive | 3 | $0.040609 | 3 | **$0.013536** | 1.0 |

The measured conversion effect reproduced at the pilot's n: every static critical cell's
correct `rework` proposal was recorded and ignored → defect present (2/3 tests); every adaptive
critical cell applied the same rework as one pass → defect fixed (3/3 tests).

## Decision-rule computation (pre-registration §2 margin, §5 decision rule)

```
NI  ⟺  cpvo_adaptive ≤ 1.10 × cpvo_static  AND  verified_success_adaptive ≥ verified_success_static − 5pts
   ⟺  cpvo ratio ≤ 1.10                      AND  success gap (static − adaptive) ≤ 0.05
```

| input | value | source field |
|---|---|---|
| cpvo_adaptive / cpvo_static | **0.7857** (95% CI [0.6842, 0.9105]) | `score.decision_rule.cpvo_ratio`, `.cpvo_ratio_ci_95` |
| margin, cpvo leg | ≤ **1.10** | pre-registration §2; `score.decision_rule.margin_cpvo_ratio_le` |
| success gap (static − adaptive) | **−0.3333** | `score.decision_rule.success_gap_static_minus_adaptive` |
| margin, success leg | ≤ **0.05** | pre-registration §2; `score.decision_rule.margin_success_gap_le` |
| cpvo leg holds / success leg holds | true / true | `score.decision_rule.cpvo_leg_holds` / `.success_leg_holds` |

**Both legs hold with margin to spare**: the ratio sits 0.31 below the 1.10 boundary (and the
ratio CI's upper bound, 0.9105, is still below it), and the success gap is 38.3 percentage
points inside the 5pt boundary (adaptive is *ahead*, not merely within margin). **The decision
rule decides.**

## Verdict

### (1) Non-inferior — YES, by the pre-registered decision rule, with n + CI.

Adaptive verification is **non-inferior to static** on cost-per-accepted-outcome AND verified
success: cpvo ratio **0.7857** (95% CI [0.6842, 0.9105]) ≤ **1.10**, and the success gap
**−0.3333** ≤ **0.05** — at **n = 9 cells per arm** (n = 6 defect-bearing, the pilot's
registered n), descriptive framing, decision made by the pre-registered rule only. No
additional cells are required: n is not below the power analysis, and the ratio CI does not
cross the margin.

### (2) Authorization statement — design review only.

**This non-inferiority verdict authorizes DESIGN REVIEW of continuing adaptive selection — and
nothing else.** It does NOT launch the continuing regime, does NOT flip `control_route`, does
NOT arm actuation, and does NOT change the treatment (`verify_proposal.py` / `_risk_depth` /
`VERIFY_RISK_THRESHOLD` / risk weights stay code-unchanged). 2b ends here; what the design
review receives is this verdict, the per-arm table, the defect-bearing n, and the sensitivity
below (pre-registration §6).

### (3) Sensitivity — the asymmetric-loss table at E_x 11.47 vs 28 (`score.asymmetric_loss.rows`).

Base downstream defect cost $0.004021 (measured; escalation score JSON); loss = E_x × $0.004021.
Static arm: 3 escaped defects (correct rework proposals ignored). Adaptive arm: 3 applied
reworks.

| E_x | static arm loss | adaptive arm value | swing | source |
|---|---|---|---|---|
| **11.4671** | +$0.138327 | −$0.138327 | **$0.276654** | **MEASURED** (openai/gpt-5.6-sol escalation fix) |
| **28.0** | +$0.337764 | −$0.337764 | **$0.675528** | sourced (DeepSeek → GPT-5.6 pricing ratio) |

At both multipliers the adaptive arm is ahead on the loss axis; the magnitude spans
~$0.28–$0.68 pending which multiplier is used (measured 11.47 vs sourced 28).

### (4) Expected-effect checks rate (`score.expected_effects.aggregates`).

**check_rate 1.0 (24/24 claims submitted); held_rate 0.0 (0/24).** The 24 claims (6 `rework`
proposals × 2 + 12 `continue` proposals × 1) were all submitted to the validator, but **none is
measurable from the immutable p1/p2 artifacts**: the adaptive rework passes were applied without
a post-rework change_analysis, and `continue` = provable null leaves no next-phase facts —
`observed=null` for every claim (recorded limitation, not a passed or failed claim). This is the
same structural limit rerun3 identified for null-gate cells.

### (5) Flagged cells and the budget/SLA guard.

**Flagged cells: none** (`score.flags = []`; graph `bolt://localhost:7687`, sonar
`localhost:9000`, lsp mypy available on every cell). **Budget/SLA guard: no breach.** Total
spend **$0.1744** (p1 $0.008781 + p2 $0.1656) against the $30.00 stop budget
(`p2_manifest.budget_sla_guard`); no cell exceeded 2× the per-cell FORECAST ($0.017562); no
cell was stopped.

## Guard

Every number above cites a field of the p3 score JSON (paths named inline); the margin is the
**pre-registered** §2 margin, applied as the §5 decision rule — no post-hoc redefinition, no
post-hoc arm reselection, no dropped cells. Descriptive framing throughout: the verdict is
exactly the pre-registered decision-rule computation plus the sensitivity the plan registered.

**LOG:** ratio 0.7857 [0.6842, 0.9105] ≤ 1.10; success gap −0.3333 ≤ 5pts; defect-bearing n 6/6
counted (3 static rejected, 3 adaptive accepted via applied rework); asymmetric-loss swing
$0.276654 @ E_x=11.47 / $0.675528 @ 28; expected-effect check_rate 1.0 / held_rate 0.0
(unmeasurable — recorded); 0 flagged, 0 stopped, $0.1744 / $30.00. **PASS — NON-INFERIOR;
authorizes design review of continuing adaptive selection, nothing else.**
