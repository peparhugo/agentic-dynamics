---
status: accepted
---

# cap_adaptive_2f — adversarial review

**Role:** adversarial verifier — falsify the campaign. Campaign `cap_adaptive_2f` (`cap_adaptive_2f@0.1`,
spec SHA256 `aac533b6b4400e5a48ef3e43b9214a401bda799fccaa90dcdeee820986d69ec3`).
**Score under review:** `experiments/results/cap_adaptive_2f/cap_adaptive_2f_score_20260828T210239Z.json`
(SHA256 `fa6bc16b5c32773c…`).
**Verdict claimed:** REFUTE (capture 1/3 < 2/3 — the ratio wall, the fourth divergence; the
flag-cost ceiling vacuous; flag-cost magnitude $0.000634 measured).

Every item below was re-derived independently from the immutable per-cell records
(`experiments/results/cap_adaptive_2f/cells/*.json`), the probe artifacts, and the worktree commit
trails — never from the score JSON's own numbers and never from proposal text.

## Finding table

| # | check | attempt to falsify | result | finding |
|---|---|---|---|---|
| F1 | preregistration adherence | re-joined all 10 cells against the §2 table (cell_id, class, variant, arm, rep) | 10/10 match; 0 invalid joins; 0 unlisted cells ran | **CLEAN** |
| F2 | the ratio wall (the pre-registered expectation) | re-derived ratio from the RAW facts of every unseen-family cell + the p1 probe | all 4 cells + probe: changed_symbol_count 2, ratio **0.5**, risk 0.18 = 0.20·(1−0.5) + 0.20·min(1,4/10); B trigger (ratio ≥ 1.0) never fires — the wall is real, not a scoring artifact | **CLEAN (wall confirmed)** |
| F3 | test_tally presence in commit trails | `git log -S'test_tally'` on every unseen-family worktree | all 4 implement trails contain `test_tally` (asserts only the return value — passes, misses the aliasing); trivial_clean + absent trails have none (0 matches each) | **CLEAN** |
| F4 | trivial_clean B-trigger construction | re-derived ratio 1.0, risk 0.06 = 0.20·(1−1.0) + 0.20·min(1,3/10), severity zero from the raw facts of every trivial_clean cell + the p1 probe | all 4 cells + probe: ratio **1.0**, risk **0.06**, severity 0/0 → B trigger fires — the flag-cost leg's construction is real | **CLEAN** |
| F5 | abstention DECLINE legs (arm integrity) | recomputed `evaluate_b_trigger` over each cell's recorded facts; checked the commit trails for apply/rework commits | trivial_clean abstention → DECLINE leg 3 (B trigger); absent-defective → DECLINE leg 2 (risk absent); unseen-family → APPLY_NULL (ratio 0.5, the wall); NO `[workflow] rework`/apply commit exists in any declined worktree (decline = apply skipped, provable-null) | **CLEAN** |
| F6 | the B trigger shadow-only, applied exactly | `git diff 694cc6029..HEAD -- src/agentic_dynamics/` | empty — treatment code (verify_proposal, code_change_facts, workflow_runner, reducers) byte-identical; no post-hoc widening of the trigger | **CLEAN** |
| F7 | status_quo applied exactly | checked the status_quo worktrees for any extra apply pass | continue = null application (no extra commit); the mutation/aliasing defect stands on the final commit in every unseen-family cell | **CLEAN** |
| F8 | the flag-cost arithmetic (the PRIMARY) | re-derived `flag_cost = Σ(abstention trivial_clean) − Σ(status_quo trivial_clean)` from the records | abstention $0.017256 − status_quo $0.016622 = **$0.000634** — matches the score; the vacuous classification (captured escapes = 0) re-checked: no abstention DECLINE prevented an escape (the pilot is flag-only; the unseen-family escapes stand in both arms) | **CLEAN (vacuous confirmed)** |
| F9 | the harm model | recomputed `3 escaped × $0.046109 = $0.138328` @11 and `× $0.112588 = $0.337764` @28, per arm | matches both arms; E_x 11.4671 measured (sol, n=1), E_x 28 sourced — sensitivity reported; abstention = status_quo harm (the treatment changed nothing) | **CLEAN** |
| F10 | the decision rule | checked condition A (declined/total on the 3 low-information abstention cells) and condition B (flag-cost ceiling non-vacuous) | A = 1/3 < 2/3 FAIL; B = vacuous FAIL; support = False; no imputed field | **CLEAN** |
| F11 | outcomes independent | checked the outcome fields (independent pytest on the immutable final commit + the post-hoc evaluator) | unseen_family: test_executed_success=true (the passing test_tally), defect_present=true, accepted=false; trivial_clean: test_executed_success=true, defect_present=false, accepted=true; absent-defective: defect_present=true, accepted=false — consistent per class | **CLEAN** |
| F12 | no post-hoc redefinition | searched the score + verdict for any re-labelled divergence | the wall is named the wall everywhere; the seed deviation is reported as a FAILED finding, not corrected | **CLEAN (one integrity defect, below)** |
| F13 | preregistration integrity | verified the committed seed hash vs `sha256(documented seed string)` | **`e4f9c1a7…` ≠ `4d5ed42e…`** — the committed seed is not derivable from the documented string (2d's seed verifies exactly under the same convention) | **FAILED FINDING (seed)** |
| F14 | spec SHA pin | sha256 of the spec file vs the preregistration header | `aac533b6…` matches the header exactly; the header was edited ONCE (the only allowed edit) on the spec commit | **CLEAN** |
| F15 | usual suite | generated surfaces (`.opencode/`, `.claude/`) untouched; secrets scan clean; budget well under the $30 stop ($0.085758 measured, 10 cells) | all pass | **CLEAN** |

## Attempted (and failed) falsifications of the REFUTE verdict

1. **Could the ratio wall be a scoring artifact?** Re-derived the ratio from the raw facts — no:
   the facts themselves carry ratio 0.5 and changed_symbol_count 2 (one test-linked); the scorer
   merely reports them.
2. **Could the agent have built the construction "wrong" (dropping test_tally) so a SUPPORT was
   missed?** No — all 4 unseen-family cells DID add test_tally (F3); the wall is structural (the
   added test is a changed symbol that is never test-linked), not an agent failure.
3. **Could B have fired under a looser reading (e.g. ratio 0.5 accepted)?** The prereg pins B to
   `risk < 0.2 AND ratio >= 1.0`. A looser reading is a post-hoc widening — rejected under F6/F12.
4. **Could the flag cost have been zero, making the wider net "free"?** No — the abstention arm
   measured $0.000634 more on the four trivial_clean cells (the decline + operator-review
   routing). It is small, but non-zero and measured.
5. **Could a captured escape exist, making the ceiling non-vacuous?** No — the pilot is flag-only
   (declines never fix), and the unseen-family escapes stand in both arms; captured escapes = 0.

## Conclusion

The campaign's REFUTE verdict survives every falsification attempt. One preregistration-integrity
FAILED finding is confirmed (the seed hash at F13); it is recorded, changes no cell, arm, or
threshold, and does not rescue the verdict — the measured ratio wall (1/3 capture) and the vacuous
flag-cost ceiling stand on their own. B's new information — the $0.000634 flag cost — re-derives
exactly.

**LOG:** 14/15 adversarial checks CLEAN (including the ratio-wall re-measurement, the B-trigger
re-derivation, the flag-cost arithmetic, and the harm model), 1 preregistration FAILED finding
confirmed (seed hash); the REFUTE verdict is not falsified. **PASS.**
