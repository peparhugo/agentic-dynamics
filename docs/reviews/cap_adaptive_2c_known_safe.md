---
status: accepted
---

# cap_adaptive_2c — known-safe list (p5 adversarial: attempted non-falsifying attacks)

**Campaign:** `cap_adaptive_2c` (`cap_adaptive_2c@0.1`). This document records the
**non-falsifying** attacks that were attempted in the adversarial pass and why each is safe. A
falsifying attack would have been a FAILED finding in `docs/reviews/cap_adaptive_2c_adversary.md`;
none of these falsified the verdict. The two FAILED findings there (the incorrect-class
non-instantiation L1/L2 and the competing evaluator label bug L3) are construction/measurement
defects that were already flagged + corrected in the score and do not change the decision — they
are recorded, not swept under a known-safe entry.

| # | attempted attack | evidence | why safe |
|---|---|---|---|
| K1 | Re-derive a **different** assignment table from the committed seed (hoping the table was post-hoc fit) | `random.seed("92983f6f06f8b5a13d24ecfae87aac5b6f707b780e716a5bf434a244c3e0f252")` + the §4 block scheme reproduces **exactly** the 24-cell table (cell_id/class/variant/arm/repetition/slot); manifest set == re-derived set, symmetric difference empty | The table is seed-derivable, committed before data (p0 17:28 +0200 < first cell 15:47 UTC), and identical to what was analyzed |
| K2 | Find a cell scored under an **arm/class different from its assignment** | All 24 scored `(cell_id, class, variant, arm, repetition)` tuples equal the pre-registered table; `join_validation.valid=true`, `n_invalid=0` | No arm/class mislabel survived; a mismatch would be invalid, not corrected |
| K3 | Find a **dropped cell** (a table row with no result) | 24/24 table rows scored; `n_dropped=0`, `n_not_run=0`; the absent-defective cells are present with `analyzer_status=unavailable (designed)` and never dropped | Denominators are complete |
| K4 | Find a **redefined margin** in the score/verdict | `score.decision_rule.margin_cpvo_ratio_le=1.10`, `margin_success_gap_le=0.05` equal the pre-registration §2 values verbatim; verdict cites §2/§5 | No post-hoc margin change |
| K5 | Find an **applied static-arm proposal** | All 12 static cells: `applied_or_null=not_applicable`, proposal artifacts `"applied": false`, no extra rework/application commit in any static trail (the `[workflow] verify` commit present in some trails is the workflow spec's own verify phase, symmetric across arms) | Static proposals provably never applied |
| K6 | Find an **unprovable adaptive application** | Correct/competing adaptive cells each have a `[workflow] rework` commit (single/two-line `calc.py` boundary fixes, no test edits); continue cells are provable null; rework_pass_cost recorded separately | Applications are provable in the commit trail |
| K7 | Find **weakened tests** in any rework | Every rework diff touches only `calc.py`; `test_calc.py` untouched in all 4 rework commits | No test weakening |
| K8 | Find a **fabricated cost** | Recorded cell cost == run-ledger `total_cost_usd`; `run_workflow_usd + application_usd == total_usd` for every applied adaptive cell (e.g. correct-adaptive r2: 0.007352 + 0.003726 = 0.011078); E4 cost == p1 phase ledger | Costs are ledger-sourced |
| K9 | Find an **outcome not independently verified** | `test_executed_success` from the independent runtime pytest on the immutable final commit; defect determination from a post-hoc evaluator (label-agnostic boundary/mutation checks re-run in this review); never the proposing agent's narrative | Outcomes are independent of the proposing agent |
| K10 | Find the **unseen-family defect inside the calibrated families** | `tally` uses no float `==` (no S1244), no nested decisions (no S3776), no inverted boundary guard — the family is mutation/aliasing, outside {boundary-compare, S1244, S3776}; present on all 4 immutable final commits | The class's family claim is checkable and held |
| K11 | Find a **secret/credential** in committed artifacts | `git grep` for `sk-…`, API keys, passwords, `AKIA…` across `experiments/results/cap_adaptive_2c/`, the two campaign scripts, and the cap_2c docs → no matches | No secrets committed |
| K12 | Find a **guard breach / stopped cell** | Total cell spend $0.2157 vs the $30.00 stop budget; max cost/forecast ratio 0.519 (competing-adaptive r1), under the 2× FORECAST guard; `n_not_run=0` | Budget/SLA guard held |
| K13 | Find a **hash mismatch** that indicates tampering | Score JSON SHA256 `076751e4…` equals the validation pin; both committed; the E4 (p1) row is faithful to the p1 cell manifest (cost 0.015853, rework/3, confidence 0.6667, 3/3, accepted) | Only the documented L4 rounding artifact (3e-6); no scored artifact mis-hashed |
| K14 | Find a **post-hoc margin renegotiation** or a verdict number without a JSON citation | The verdict's decision is computed from the pre-registered rule only; every table cites its `score.*` field; the validation JSON traces every verdict number | Descriptive framing; the margin is untouched |
| K15 | Find the **abstention analysis fitted-then-sold** (a cherry-picked threshold) | The threshold curve evaluates ALL observed thetas + boundaries (θ ∈ {0, 0.6667, 1.0}); `improving_threshold_exists=false`; robust to the harm-inclusive variant (0.054931 → 0.102860 at θ=1); labeled EXPLORATORY | No threshold is sold as a pre-registered finding; the search is honest and complete over the observed distribution |
| K16 | Find a **confidence recorded after the outcome** (leaked predictor) | Every proposal artifact's `recorded_at` precedes its cell record's `written_at`; `impl.confidence == proposal.confidence` (0 mismatches) | Confidence is a genuine predictor, recorded at proposal-emission time |
| K17 | Find the **4 absent cells' absence hidden** | The abstention analysis reports `n_without_confidence=4` and lists the cells; the absent-defective harm is counted (1 escaped/arm) | Excluded cells are reported, never imputed, never dropped |
| K18 | Find the **treatment modified** during the campaign | The campaign runs the treatment (`verify_proposal.py`, `_risk_depth`, `VERIFY_RISK_THRESHOLD`, risk weights, severity filter) code-unchanged; no campaign-phase commit touches the treatment | The treatment is code-unchanged (pre-registration §6 / hard rule 10) |

**Attempted attacks that were non-falsifying:** none of K1–K18 falsified the pre-registered
decision or any of its inputs. The verdict (`docs/experiments/results/cap_adaptive_2c.md`,
NON-INFERIOR; abstention: no improving threshold) stands unchanged. The two recorded findings
(L1/L2 incorrect-class non-instantiation → wrong-apply unmeasured; L3 competing evaluator label
bug → corrected in the score) are disclosed in the adversary review and do not alter the decision.

**LOG:** 18 attempted non-falsifying attacks, 18 safe. **PASS** — commit.
