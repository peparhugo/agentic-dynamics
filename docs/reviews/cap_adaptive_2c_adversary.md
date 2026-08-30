---
status: accepted
---

# cap_adaptive_2c — adversarial review (p5)

**Campaign:** `cap_adaptive_2c` (`cap_adaptive_2c@0.1`) · **Verdict under review:**
`docs/experiments/results/cap_adaptive_2c.md` (committed `f1799ed53be089b6f66d88f1b51fb3928d0e3b8b`,
SHA256 `e287933781872da854b75a559911449de8349ef18726147244606b2034fb91dc`). **Pre-registration:**
`docs/experiments/preregistrations/cap_adaptive_2c_preregistration.md` (committed `104a8eade91c8b77849d9db5fcd0f1e99d7925ad`,
SHA256 `0f3a5de755784a6e9f8a71da3e7706782cddf930095fbc65a685ccc361da5e3d`). **Score:**
`experiments/results/cap_adaptive_2c/cap_adaptive_2c_score_20260827T180241Z.json` (SHA256
`076751e4b14d74085fba46581a9bf9bd6bb627bee1089a5afce4c87d5cde60f7`) + the validation JSON
(`cap_adaptive_2c_validation_20260827T180241Z.json`, SHA256
`17093d858b4526c3273f964d12418964151552b98d7c123893fda15fd86fd99c`).
**Attacker role:** adversarial verifier, attack in the pre-registered order; a deviation from the
pre-registered plan is a FAILED finding, not a limitation.

## Attack 1 — Pre-registration adherence

**Attack:** does the committed pre-registration match what was analyzed? Any redefined margin,
reseeded assignment, dropped cell, or post-hoc class re-label is a FAILED finding.

**Evidence:**
- Commit order (provable by `git log`): `104a8eade` p0_preregister **17:28:17** → `0a859ba7f`
  p1_measure_one (E4) **17:39:07** → `80f7806fe` p2_run_grid (execution manifest FIRST)
  **17:44:41** → grid cells written **15:47–17:49 UTC** → `90157251f`/`48833c385` p3_score
  **18:02** → `f1799ed53` p4_verdict **20:07:01**. p0 precedes every cell: the first p2 cell
  record was written `2026-08-27T15:47:29Z` (UTC), after p0 (17:28 +0200 = 15:28 UTC); the E4
  p1 manifest was written `2026-08-27T15:37:10Z`, after p0.
- The p0 commit adds exactly one file, `docs/experiments/preregistrations/cap_adaptive_2c_preregistration.md`
  (591 lines), containing the margin (`≤ 1.10 ×` and `− 5 percentage points`, §2), the committed
  seed `92983f6f06f8b5a13d24ecfae87aac5b6f707b780e716a5bf434a244c3e0f252` (§4), and the full
  24-cell assignment table (§4). The current file's SHA256 equals the committed version's
  (`0f3a5de7…` == `0f3a5de7…`) — the pre-registration was never edited after p0.
- The score/verdict applied exactly that margin: `score.decision_rule.margin_cpvo_ratio_le =
  1.10`, `margin_success_gap_le = 0.05` — matching pre-registration §2 verbatim. The harm
  constants trace: `$0.004021` base defect cost and E_x 11.4671 / 28.0 → per-escaped-defect
  `$0.046109` / `$0.112588` (score `harm_table.wrong_continue.*`, re-derived from
  `cap_escalation_measurement_score` in this review — see A4).
- Cells: 24 in the pre-registered table, 24 scored (`join_validation.n_table_rows=24`,
  `n_cells=24`, `valid=true`, `n_invalid=0`); zero dropped (`denominators.n_not_run=0`,
  `n_dropped=0`; absent-defective is a designed analyzer/graph-down cell, flagged and never
  dropped per §1 denominator discipline).

**Result: PASS.** No deviation. The pre-registration is the analyzed plan; commit order proves it
preceded data collection; the current pre-registration file is byte-identical to the committed one.

## Attack 2 — Class integrity

**Attack (per the p5 prompt):** did the incorrect-class cell really make the verifier propose
**rework** on a CLEAN change (proven by the proposal + the evaluator)? Is the unseen-family
defect really outside the calibrated families? Did each class instantiate its construction?

**2a. The incorrect class — CONSTRUCTION FAILURE (finding F1).**
- The pre-registration §3 class 2 specified a **false-positive VERIFY** (not rework) built via the
  tests-ratio term, with the arithmetic shown: `changed_symbol_count=20`,
  `changed_symbols_with_tests_ratio=0.05` (1/20), and — the structural guarantee —
  `impacted_symbol_count ≥ 1` ("the seeded test_add calls the modified add, so the 1-2 hop
  dependent set is non-empty") → `risk = 0.19 + 0.02·min(10, impacted) ≥ 0.21` → **verify**.
- **Measured in all 4 incorrect cells:** `impacted_symbol_count = **0**` (graph available,
  `graph_updated=true`, per the immutable run ledger `20260827T155639Z.json`), so
  `risk = 0.19 < VERIFY_RISK_THRESHOLD 0.2` → the proposal was **`continue`**, not `verify`.
  The structural guarantee did NOT hold in the measured environment: the graph's 1-2 hop
  expansion over the cell's repository scope returned zero dependents for the modified `add`
  (the seeded `test_add` → `add` edge was not in the reachable set).
- The risk arithmetic is exactly the pinned formula (recomputed in this review:
  `[0 + 0 + 0.20·(1−0.05) + 0.20·0] / 1.0 = 0.19` → continue). The verifier's machinery behaved
  as pinned; the **construction** did not instantiate.
- **Consequence:** the class's intended measurement — the constructible false-positive **verify
  pass** (the wrong-apply harm leg) — was **never produced**. The campaign therefore reports
  wrong-apply = **$0.000000 measured**, which is honest (no verify pass ever applied) but is a
  **non-measurement** of the false-positive leg, not a measured zero. The 4 incorrect cells are
  flagged `construction-failure: expected proposal verify, got continue`
  (`score.flags.construction_failures`, 4 entries) and behave, in practice, as additional
  irrelevant-class cells (continue on a clean change → accepted both arms).
- **Classification:** a genuine construction failure, **already flagged and recorded per the
  pre-registration's falsifiability contract** (§3 class 2: "the cell did not instantiate the
  class → construction failure, flagged + recorded"), and the verdict discloses it (§2 finding).
  It is NOT a silent pass and NOT a re-label. It is recorded as accepted limitation **L2** with
  residual risk: the wrong-apply harm of a false-positive VERIFY remains **unmeasured** in this
  campaign — the campaign bounds it only by the filter-strength statement (false-positive REWORK
  unconstructible under the severity filter), not by a measured pass cost. The verdict's
  non-inferiority claim does NOT rest on a measured wrong-apply leg.

**2b. The unseen-family class — PASS (the defect is really outside the calibrated families).**
- The defect (`tally(scores)` mutating its input via `scores.sort(reverse=True); return scores`)
  was verified present on the immutable final commits of all 4 unseen-family cells
  (`calc.tally([3,1,2])` returns `[3,2,1]` and mutates the caller's list; input `[3,1,2]` after
  the call — re-run in this review).
- Family verification (the class's checkable claim, §3 class 6): the defect involves **no float
  `==`** (S1244 absent — AST scan for `Eq` on the function shows none), **no deep nesting /
  cognitive complexity** (`tally` has zero nested decisions; S3776 absent), and is **not an
  inverted boundary comparison** (no `>`-for-`>=` guard). The defect family is
  **mutation/aliasing**, genuinely outside {boundary-compare, S1244 float, S3776 complex-method}.
  The evaluator's recorded note (`"family: mutation/aliasing … NOT boundary-compare, NOT S1244,
  NOT S3776"`) is consistent with this review's independent determination.
- The verifier's blind spot is reproduced: `new_sonar_critical_count=0`, `new_lsp_error_count=0`,
  `changed_symbols_with_tests_ratio=1.0`, risk below threshold → `continue` (wrong-continue).

**2c. The competing class — evaluator label bug, caught by the score audit (finding F2).**
- The p2 grid executor's `_defect_determination` asserted hardcoded label strings
  (`classify(10.0) == 'ten_to_twenty'`, `classify(20.0) == 'twenty_to_thirty'`) for the competing
  class. The competing agents never used those labels (`tier_10`/`tier_20`, `low`/`moderate`,
  etc.), so the p2 records carry `defect_present_on_final_commit=true` even where the rework
  **did fix both boundaries** — internally inconsistent with their own `test_executed_success
  = true` (3/3, the test file asserts `classify(10.0) == "tier_10"` / `classify(20.0) ==
  "tier_20"`).
- Independent verification in this review (label-agnostic boundary checks on the immutable final
  commits): competing-adaptive r1/r2 → `classify(10.0) == classify(10.001)` AND `!= classify
  (9.999)`; `classify(20.0) == classify(20.001)` AND `!= classify(19.999)` — **both boundaries
  correct**; the rework diffs change `> 10` → `>= 10` and `> 20` → `>= 20` (two lines, `calc.py`
  only). competing-static r1/r2 → both checks fail (defects genuinely present, tests 2/3).
- The score's `outcome_audit_corrections` (2 entries) re-determined competing-adaptive r1/r2 as
  accepted (escaped=0, harm=$0) and flagged them. **The verdict uses the audited values.**
- **Classification:** a p2-executor measurement bug, **corrected + flagged in the score**, not
  propagated into the verdict. Accepted limitation **L3**: the p2 cell records themselves keep the
  stale `defect_present=true` field (the score preserves both recorded and audited values in
  `outcome_audit`), so a consumer reading only the raw p2 cell records would misread those two
  cells; the score and verdict are correct.

**Result: 2a FAIL (construction — recorded as L2), 2b PASS, 2c FAIL (evaluator bug — corrected,
recorded as L3).** Neither failure changes the pooled decision: the incorrect-class cells were
clean/accepted in both arms (their mis-construction does not inflate adaptive's win), and the
competing correction is already reflected in the verdict.

## Attack 3 — Arm integrity

**Attack:** are adaptive applications provable in the commit trail, and static-arm proposals
provably never applied?

**Evidence (all 24 worktrees re-examined in this review):**
- **Adaptive rework cells** (correct-adaptive r1/r2, competing-adaptive r1/r2): each carries a
  `[workflow] rework` commit on top of its `[workflow] implement` commit. Diff audit: correct r1
  (E4) and r2 change only the `[10,20)` guard (`> 10` → `>= 10`); competing r1/r2 change BOTH
  guards (`> 10` → `>= 10`, `> 20` → `>= 20`). No test-file edits in any rework (no test
  weakening). Application cost `rework_pass_cost_usd` ~$0.0037–0.0047, recorded separately from
  the workflow run cost.
- **Adaptive continue/null cells** (incorrect, irrelevant, unseen-family adaptive): proposal
  action `continue` → `applied_or_null = "null"` (provable null — no extra pass in the commit
  trail, only the workflow's own implement/test/verify phases).
- **Static cells (all 12):** no rework/extra application commit; proposal artifacts record
  `"applied": false`; `applied_or_null = "not_applicable"`. The `[workflow] verify` commit present
  in some static trails is the **workflow spec's own verify phase** (all six cell specs have
  implement/test/verify phases), symmetric across arms — it is not the campaign's application.
- **Absent cells (4):** no proposal emitted (seam refused in the designed degraded state);
  `applied_or_null = "null"` (adaptive) / `"not_applicable"` (static); the refusal + facts present
  are recorded. No hand-authored proposal.

**Result: PASS.** Every application (or non-application) is provable from the commit trail; no
static proposal was applied; every adaptive application matches the proposal's action and is a
single bounded pass.

## Attack 4 — The harm model

**Attack:** is wrong-apply measured not inferred? Is E_x cited with sensitivity, and the n=1
limitation stated?

**Evidence:**
- **Wrong-apply = $0.000000 measured** (`score.harm_table.wrong_apply.total_usd_measured`, with
  the note). This is a **measurement** (no false-positive verify pass was ever applied — the only
  constructible false-positive), not an inference. The pre-registration's filter-strength
  statement (false-positive REWORK unconstructible under the severity filter) is confirmed. The
  limitation that the false-positive VERIFY leg is **unmeasured** (because the incorrect class did
  not instantiate) is recorded as L2.
- **Wrong-continue = E_x × base cost**, E_x cited + sensitivity reported. This review re-derived
  the constants from the escalation score JSON (`cap_escalation_measurement_score_20260826T125726Z.json`):
  `base_downstream_defect_cost_usd = 0.004021` (0.112588 / 28.0, re-derived from the rerun3 score
  JSON), `per_model[0].E_x = 11.4671` (sol, `0.102619 / 0.008949`), `per_model[1].E_x = 12.5134`
  (sonnet, `0.111982 / 0.008949`), and the loss-table rows `$0.046109` @ 11.4671 and `$0.112588` @
  28.0. The score's `$0.046109`/`$0.112588` per escaped defect match. **n=1-per-model limitation
  is stated** in the score's harm note and the verdict.
- **Escaped-defect ledger re-counted in this review:** correct-static 2 (1/cell) + competing-static
  4 (2/cell) + absent-defective 2 (1/arm) + unseen-family 4 (1/cell, both arms) = **12**, matching
  `score.harm_table.wrong_continue` (12 escaped). Per-arm: static 9, adaptive 3 — matching
  `score.per_arm` and the verdict.

**Result: PASS, with the L2 non-measurement caveat and the L4 rounding artifact below.**

## Attack 5 — The abstention analysis

**Attack:** is it computed from recorded proposals + outcomes, exploratory-labeled, not
fitted-then-sold?

**Evidence:**
- **Input = proposal-record confidence**, recorded at proposal-emission time BEFORE the outcome:
  every proposal artifact's `recorded_at` precedes its cell record's `written_at` (checked for
  all 20 proposal-bearing cells; e.g. competing-adaptive r1 proposal 16:24:22 vs cell 16:24:50).
  Confidence is the implement-phase [H] execution-confidence, and `impl.confidence` ==
  `proposal.confidence` for every cell (0 mismatches).
- **The 4 absent cells have no proposal record** (seam refused) → excluded from the decile bins
  with their count reported (`n_without_confidence = 4`, cells listed) — exactly the pre-registered
  §7 rule ("excluded from the decile bins with its count reported"). Never imputed.
- **Deciles are honest:** only 2 observed confidence values (0.6667, 1.0), so only deciles
  [0.6, 0.7) and [0.9, 1.0] are populated; the analysis reports the empty deciles implicitly by
  their absence and reports `n_apply`/`n_abstain` per populated decile. Decile [0.6, 0.7) shows
  `value(abstain) = null` (0 accepted → infinite cpvo) — reported as null, not fabricated.
- **Threshold curve spans ALL observed thetas + boundaries** (θ ∈ {0, 0.6667, 1.0}), no
  cherry-picked θ. `improving_threshold_exists=false`. The verdict's claim is robust to the
  harm-inclusive variant: `cpvo_gated_harm_11` is also monotonically worse at θ=1 (0.054931 →
  0.102860).
- **Exploratory-labeled** in both the score (`abstention_analysis.exploratory_label`) and the
  verdict ("EXPLORATORY … descriptive at the campaign's n; no threshold is fixed").
- The per-decile value(apply)/value(abstain) computation was re-derived in this review from the
  recorded proposals + outcomes and matches (decile 6: apply cpvo $0.016392, 4 accepted; abstain 0
  accepted → null; decile 9: apply $0.009089 vs abstain $0.009060).

**Result: PASS.** The analysis is computed from recorded proposals + outcomes, exploratory-labeled,
and not fitted-then-sold. Its resolution is limited (2 confidence values) — recorded as accepted
limitation **L5**.

## Attack 6 — Usual suite (baselines, denominators, credentials, hashes, guard, fabrication)

**Attack + evidence:**
- **Baselines/seed:** every worktree is seeded from the same `calc.py` (`add`, `subtract`) +
  `test_calc.py`; the seed content is identical across cells (the seed commit reproduces the
  seeded-app baseline revision).
- **Denominators:** n=24 total, 12 per arm, 7 defect-bearing per arm (correct 2 + competing 2 +
  absent-defective 1 + unseen-family 2) — re-counted in this review, matching
  `score.denominators`. `n_invalid_join=0`, `n_dropped=0`, `n_not_run=0`.
- **Credentials:** `git grep` for `sk-…`, API-key, password, `AKIA` patterns across
  `experiments/results/cap_adaptive_2c/` + `scripts/score_cap_2c.py` + `scripts/run_cap_2c_grid.py`
  + the cap_2c docs → no matches.
- **Hashes:** the score JSON SHA256 (`076751e4…`) equals the validation JSON's pin
  (`validation.score_json_sha256`); both artifacts are committed. The E4 (p1) row was re-mapped in
  this review from the p1 cell manifest and is faithful (cost 0.015853, accepted true, rework/3,
  confidence 0.6667, 3/3, defect absent).
- **Guard:** total cell spend **$0.2157** vs the **$30.00** stop budget; the max cost/forecast
  ratio across cells is 0.519 (competing-adaptive r1), well under the 2× FORECAST guard; no cell
  stopped.
- **Cost integrity:** recorded cell cost == run-ledger `total_cost_usd` (spot-checked; the
  run_workflow_usd + application_usd == total_usd for every adaptive applied cell, e.g.
  correct-adaptive r2: 0.007352 + 0.003726 = 0.011078).

**Result: PASS**, with the L4 rounding artifact.

## Findings table

| # | attack | result | fix / limitation |
|---|---|---|---|
| A1 | pre-registration adherence | **PASS** | — |
| A2a | incorrect-class construction (false-positive verify instantiation) | **FAIL** | recorded, L2 |
| A2b | unseen-family family check | **PASS** | — |
| A2c | competing evaluator label bug | **FAIL** | corrected in score, L3 |
| A3 | arm integrity | **PASS** | — |
| A4 | harm model | **PASS** | L2 caveat + L4 |
| A5 | abstention analysis | **PASS** | L5 |
| A6 | usual suite | **PASS** | L4 |

## Accepted limitations

**L1 — the incorrect-class false-positive VERIFY is unmeasured (the campaign's principal
honesty gap).** Reasoning: the pre-registered construction's structural guarantee
(`impacted_symbol_count ≥ 1`) did not hold (measured 0 in all 4 incorrect cells — the graph's
1-2 hop expansion over the cell scope returned no dependents for the modified `add`), so the
proposal was `continue` and the false-positive verify pass was never produced. Wrong-apply =
$0 is therefore a **non-measurement**, not a measured zero. The campaign already flags this
(4 construction-failure flags) and discloses it in the verdict (§2). Residual risk: the design
review cannot, from this campaign, price a false-positive verify pass; the bound is only the
filter-strength statement (no false-positive REWORK constructible). This does NOT weaken the
non-inferiority verdict (adaptive's win on correct/competing does not depend on the incorrect
class), but it means the "when proposals can be wrong" leg of the 2b limitation is **partially
unanswered** — the wrong-continue direction (unseen-family, absent-defective) is measured; the
wrong-apply direction is not.

**L2 — [consolidated with L1]** the incorrect-class construction failure, its flag, and the
unmeasured wrong-apply leg.

**L3 — the p2 competing evaluator's hardcoded-label bug.** Reasoning: `_defect_determination`
asserted label strings the competing agents never used, so the two p2 cell records carry
`defect_present=true` despite both boundaries being fixed (internally inconsistent with their own
3/3 tests). The score's outcome audit corrected + flagged both; the verdict uses the audited
values. Residual risk: a consumer reading only the raw p2 cell records would misread those two
cells as rejected — the score and verdict are correct, and the p2 records preserve the recorded
value alongside the audited one. No fix to the p2 records (immutable); the evaluator should be
made label-agnostic in a future campaign.

**L4 — $0.000003 rounding artifact in the harm table total.** The harm table's wrong-continue
total at E_x=11.47 is `$0.553311` (computed from the unrounded per-defect product
`12 × 0.0461092091…`), while the sum of the per-cell `harm_11` fields is `$0.553308` (each cell
rounded to 6dp `0.046109`). The verdict cites the harm-table total (`$0.553311`). The discrepancy
is pure rounding (3e-6) and changes no conclusion; recorded for reproducibility cleanliness.

**L5 — abstention resolution.** Only two distinct confidence values (0.6667, 1.0) were observed
(20 proposal-bearing cells; the 4 absent cells carry no proposal), so the abstention curve has
only three θ points and the per-decile table two populated deciles. The verdict's abstention
finding ("no improving threshold") is therefore coarse — it says "confidence-gated abstention does
not improve value at ANY observed threshold," which is exactly the registered claim, but the
confidence distribution offers little discriminating power. Descriptive at the campaign's n, as
registered; a future campaign needs a confidence distribution with more spread (or a different
signal) to test the abstention hypothesis harder.

## Re-test

The decision-rule computation was re-derived in this review from the same immutable artifacts:
cpvo ratio **0.653666** (static $0.019822 → adaptive $0.012957) ≤ 1.10 and success gap **−0.3333**
(static 0.4167 → adaptive 0.7500) ≤ 0.05, at n = 12 per arm and n = 7 defect-bearing per arm —
identical to the p3 score and the p4 verdict. Per-arm bootstrap CIs [0.016101, 0.025406] vs
[0.011164, 0.015193] (disjoint in adaptive's favor). The abstention θ=1.0 counterfactual was
recomputed from the recorded static-arm matches (correct/competing/unseen static cells) and
reproduces cost $0.198641 / accepted 10. No recomputation changed any number.

## Re-stated verdict

**UNCHANGED — NON-INFERIOR.** Adaptive verification remains non-inferior (indeed superior) to
static under proposal heterogeneity by the pre-registered decision rule (§2 margin, §5 rule), with
n and CI. The abstention analysis (exploratory) shows no confidence-gated threshold improves value
— the gate should not decline on the confidence signal. The two genuine findings (L1/L2
incorrect-class non-instantiation, L3 competing evaluator bug) are recorded/corrected and do NOT
change the decision; L4/L5 are cleanliness/resolution limitations. Per §6, this authorizes
**design review of the application policy — nothing else**; it does not launch a regime, flip
`control_route`, arm actuation, or modify the treatment.

**LOG:** A1 PASS · A2a FAIL (L1/L2) · A2b PASS · A2c FAIL→corrected (L3) · A3 PASS · A4 PASS
(L2/L4) · A5 PASS (L5) · A6 PASS (L4); re-test reproduces ratio 0.6537 / gap −0.3333 / θ=1.0
cost 0.198641. **PASS** — verdict re-stated unchanged; the incorrect-class leg is a recorded
non-measurement, not a falsification; commit.
