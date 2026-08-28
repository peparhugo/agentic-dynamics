---
status: accepted
---

# cap_adaptive_2d — known-safe list (p5 adversarial: attempted non-falsifying attacks)

**Campaign:** `cap_adaptive_2d` (`cap_adaptive_2d@0.1`, spec SHA256 `1258280d44f6…`). This
document records the **non-falsifying** attacks attempted in the adversarial pass and why each is
safe. A falsifying attack would have been a FAILED finding in
`docs/reviews/cap_adaptive_2d_adversary.md`; the two FAILED findings there (F1 incorrect_rebuilt
second construction failure, F2 unseen-family fingerprint never instantiated) and the three
accepted limitations (L1 p2-manifest per-cell hash stub, L2 two-value confidence resolution, F3
harmful_partial r2 model-noise source of leg A) are construction/measurement defects already
flagged + recorded in the p1/p2/p3 artifacts — they do not change the decision (REFUTE) and are
not swept under a known-safe entry.

| # | attempted attack | evidence | why safe |
|---|---|---|---|
| K1 | Re-derive a **different** assignment table from the committed seed (hoping the table was post-hoc fit) | `random.seed("617e6763fcd238dc93a59ba1f41e01ba5f281c4748ef3867dbebeeca344c7dfb")` + the §4 block scheme (per-arm repetition counting) reproduces **exactly** the 28-cell table (cell_id/class/variant/arm/repetition/slot); seed == `sha256("cap_adaptive_2d\|blocked-by-stimulus\|50-50\|statusquo-vs-abstention\|20260828")`; manifest set == re-derived set, 0 mismatches | The table is seed-derivable, committed before data (p0 9dc0b4a63 < first cell 00:13 UTC), and identical to what was analyzed |
| K2 | Find a cell scored under an **arm/class different from its assignment** | All 28 scored `(cell_id, class, variant, arm, repetition)` tuples equal the pre-registered table; `score.join_validation.valid=true`, `n_invalid=0`, `n_table_rows=28`, `n_cells=28` | No arm/class mislabel survived; a mismatch would be invalid, not corrected |
| K3 | Find a **dropped cell** (a table row with no result) | 28/28 table rows scored, `status=ok` on all 28; `score.denominators.n_dropped=0`, `n_not_run=0`; absent-defective present with `analyzer_status=unavailable (designed)`, never dropped | Denominators are complete; designed degraded cells are flagged, never dropped |
| K4 | Find a **redefined margin / reseeded assignment** in the score/verdict | `score.abstention_decision_rule` uses the pre-registered floor verbatim (`floor=0.6666667`, leg B), `leg_d_ni_guard.margin_cpvo_ratio_le=1.10`, `margin_success_gap_le=0.05`; verdict cites prereg §1–§2 | No post-hoc margin change |
| K5 | Find a **post-hoc leg widening** of the abstention rule | `run_cap_2d_grid.py` `evaluate_abstention` (lines 196–250) implements exactly the pinned §0 table (leg 2 risk-absent → leg 1 revision-mismatch → APPLY risk≥0.2 → leg 3 Option A fingerprint with `abs(risk−0.20·min(1,impacted/10))<1e-9` + severity_zero + tests_zero → APPLY-NULL); 0 declines outside the pinned states | The rule is byte-verbatim to the pin; no confidence used (only the 6 `requires_facts`) |
| K6 | Find an **abstention DECLINE that applied anyway** (policy not followed) | All 2 abstention DECLINEs (absent-clean, absent-defective, both leg 2) have `applied_or_null="declined"` and `proof:"abstention-decline:leg-2 (no apply pass)"`; no rework/verify commit on those trails | Declines provably skipped the apply pass |
| K7 | Find a **status_quo cell that did not apply exactly per proposal** | Programmatic sweep over all 28 cell records: status_quo cells have `applied_or_null="applied"` iff proposal ∈ {rework, verify} (each with a `[workflow] rework` commit, 1 pass), else `"null"`; 0 failures | Applications are provable in the commit trail; symmetric across arms |
| K8 | Find a **cell scored under a different arm than its assignment** (the invalid-not-corrected rule) | `join_validation.invalid_cells=[]`; all `per_cell[].arm` equal the §4 table arm | No invalid cell was corrected into a score |
| K9 | Find **weakened tests** in any rework | All rework diffs touch only `calc.py` (boundary `>`→`>=`); `test_calc.py` untouched (spot-checked across arms); the evaluator is label-agnostic (band checks, never hardcoded 2c band names) | No test weakening; evaluator not foolable by band-name renaming |
| K10 | Find a **fabricated cost** | Cell `cost.total_usd = run_workflow_usd + application_usd` (e.g. E1: 0.009223 + 0.003797 = 0.01302); per-cell costs sum to `per_arm` totals (status_quo $0.158165, abstention $0.158536, re-computed here); costs are ledger-sourced (`run_ledger_sha256` per cell) | Costs are internally consistent and ledger-backed |
| K11 | Find an **outcome not independently verified** | `test_executed_success` from independent runtime pytest on the immutable final commit; `defect_present_on_final_commit` from the post-hoc evaluator; final revisions verified to match the worktree HEADs (4 spot-checks); never the proposing agent's narrative | Outcomes are independent of the proposing agent |
| K12 | Find the **unseen-family defect inside the calibrated families** | `tally` uses `s.sort(reverse=True); return s` — mutation/aliasing; no float `==` (no S1244), no nested decisions (no S3776), no inverted boundary guard (not boundary-compare); present on all 4 immutable final commits | The class's family claim is checkable and held (F2 is about the fingerprint not firing, not the family) |
| K13 | Find the **harmful_partial outcome NOT one-of-two** | status_quo r2: [80,90) defect present, [10,20) fixed → `defect_note` "boundary-compare x1 … one-of-two (partial_rework exposure)", `accepted=false`; abstention r1/r2 both fixed → accepted; re-verified on immutable commits | One-of-two semantics held as designed |
| K14 | Find a **secret/credential** in committed artifacts | `git grep` for `sk-…`, API keys, passwords, `AKIA…` across `experiments/results/cap_adaptive_2d/`, the two campaign scripts, and the cap_2d docs → no matches | No secrets committed |
| K15 | Find a **guard breach / stopped cell** | Total cell spend $0.316701 vs the $30.00 stop budget; all 28 cells `within_forecast=true` (2× FORECAST $0.02604 guard); `n_not_run=0`; no timeout/SLA stops | Budget/SLA guard held |
| K16 | Find a **hash mismatch** indicating tampering | Score `9c6abb55…`, validation `ad8a0b2f…`, p2 manifest `9fab82c2…`, p1 manifest `b1be2cb3…`, probe `567839d3…` re-computed and equal the verdict provenance table; 24/24 proposal artifact hashes match the per-cell records | No scored artifact mis-hashed (L1: the manifest's per-cell stub column, recorded — git + internal hashes cover cell integrity) |
| K17 | Find a **verdict number without a JSON citation** | The verdict's decision is computed from the pre-registered rule only; every table cites its `score.*` field; `validation.traces` maps every verdict number to a field (capture, confidence, cpvo_harm, flag cost, NI, harm) | Descriptive framing; the margin and legs are untouched |
| K18 | Find the **confidence curve used by the abstention rule** (a rule/confidence coupling) | `evaluate_abstention` never reads confidence; `score.abstention_analysis` is labeled EXPLORATORY with `improving_threshold_exists=false` and no fixed threshold | The rule stays confidence-free (2c constraint re-check) |
| K19 | Find a **runner-wired abstention rule** (treatment code changed) | `git show e2bb2f94b -- scripts/run_workflow.py` = only the `FINOPS_SKIP_SPEC_INDEX=1` index-race guard; `verify_proposal.py` / `_risk_depth` / `VERIFY_RISK_THRESHOLD` / `RISK_WEIGHTS` untouched (hard-rule 10) | Shadow-evaluated only; the treatment is code-unchanged |
| K20 | Find a **re-run / re-labelled / dropped class** after a construction failure | All 4 incorrect_rebuilt + 4 unseen_family cells kept their assigned class/arm labels, flagged (`construction-failure`), and scored in their denominator; no cell re-ran under a different stimulus | F1/F2 are recorded as the design's falsifiability contract firing, never as silent corrections |
| K21 | Find the **harm multiplier mis-priced** | Re-derived from `cap_escalation_measurement_score_20260826T125726Z.json`: base $0.004021, E_x 11.4671/12.5134, loss $0.046109/$0.112588 — matching the pre-registration's cited values and the score's `harm_table` (11 escaped × $0.046109 = $0.507199 @11.47) | The harm model is sourced, cited, and n=1-per-model limitation stated |
| K22 | Find an **overstated capture claim** (a decline counted where it did not fire) | `decline_records` lists exactly 2 declines (both leg 2); the score counts capture as declined-low-information/3 = 1/3 and reports it as failing — no inflated capture | Capture is reported as measured (failed), never as a passed claim |

**Summary:** 22 non-falsifying attacks, all safe. The REFUTE verdict stands: the abstention rule
did not demonstrate it knows when not to intervene — leg B (capture) failed because the
unseen-family class never instantiated the leg-3 fingerprint, the wrong-apply leg is unverifiable
after the incorrect_rebuilt class failed to instantiate `verify` a second time, and leg A's numeric
hold is not a treatment effect. The two construction failures mean the informational-abstention
boundary remains unverified, and the campaign honestly cannot distinguish "abstention doesn't help"
from "the exposures couldn't be built to test it."
