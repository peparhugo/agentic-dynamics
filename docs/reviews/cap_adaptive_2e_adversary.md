---
status: accepted
---

# cap_adaptive_2e — adversarial review

**Role:** adversarial verifier — falsify the campaign. Campaign `cap_adaptive_2e` (`cap_adaptive_2e@0.1`,
spec SHA256 `b0ad1c4fe65d364478db4c508e694b58a09c2377a8063efe514796a1d853e4ad`).
**Score under review:** `experiments/results/cap_adaptive_2e/cap_adaptive_2e_score_20260828T144818Z.json`
(SHA256 `4564cb89fb2aa2fe6c500d9c53d24848c2d6c8ab0c82660b24d06bfe5a1ffbfc`).
**Verdict claimed:** REFUTE (third construction divergence → leg-3 refuted as a mechanism; capture 1/3).

Every item below was re-derived independently from the immutable per-cell records
(`experiments/results/cap_adaptive_2e/cells/*.json`), the probe artifact, and the worktree commit
trails — never from the score JSON's own numbers and never from proposal text.

## Finding table

| # | check | attempt to falsify | result | finding |
|---|---|---|---|---|
| F1 | preregistration adherence | re-joined all 6 cells against the §3 table (cell_id, class, variant, arm, rep) | 6/6 match; 0 invalid joins; 0 unlisted cells ran | **CLEAN** |
| F2 | fingerprint arithmetic | re-derived `0.20·(1−ratio) + 0.20·min(1, impacted/10)` from the RAW facts of every unseen-family cell | all four cells: ratio 0.5 → risk 0.18 = 0.10 + 0.08; expected fingerprint 0.08; `risk − expected = 0.10` ≫ 1e-9 → divergence | **CLEAN (divergence real, not a scoring artifact)** |
| F3 | test_tally presence in commit trails | `git log -S'test_tally'` on every unseen-family worktree | all 4 implement commits contain `test_tally` (asserting only the return value — passes, misses the aliasing); absent cells correctly have none | **CLEAN** |
| F4 | abstention DECLINE legs | recomputed `evaluate_abstention` over each cell's recorded facts; checked the commit trails for apply/rework commits | absent-defective → DECLINE leg 2 (risk absent); unseen-family → APPLY_NULL (fingerprint did not hold); NO `[workflow] rework`/apply commit exists in any worktree (decline = apply skipped, provable-null) | **CLEAN** |
| F5 | status_quo applied exactly | checked the status_quo worktrees for any extra apply pass | continue = null application (no extra commit); the mutation/aliasing defect stands on the final commit in every unseen-family cell | **CLEAN** |
| F6 | abstention rule shadow-only | `git diff 3458f916d..HEAD -- src/agentic_dynamics/` | empty — treatment code (verify_proposal, code_change_facts, workflow_runner) byte-identical; the rule never left shadow | **CLEAN** |
| F7 | harm model | recomputed `3 escaped × $0.046109 = $0.138327` @11 and `× $0.112588 = $0.337764` @28, per arm | matches both arms; E_x 11.4671 measured (sol, n=1), E_x 28 sourced — sensitivity reported | **CLEAN** |
| F8 | decision rule computed from recorded fields | checked condition 1 (probe + cell fingerprint holds) and condition 2 (declined/total on the 3 low-information abstention cells) | condition 1 = FAIL (5/5 divergences incl. the probe); condition 2 = 1/3 < 2/3 FAIL; no imputed field | **CLEAN** |
| F9 | outcomes independent | checked the outcome fields (independent pytest on the immutable final commit + the post-hoc evaluator) | `test_executed_success=true` (the passing test_tally), `defect_present=true` (post-hoc aliasing check), accepted=false — consistent per class | **CLEAN** |
| F10 | no post-hoc redefinition | searched the score + verdict for any re-labelled divergence | the divergence is named a divergence everywhere; the seed + §1-premise deviations are reported as FAILED findings, not corrected | **CLEAN (one integrity defect, below)** |
| F11 | preregistration integrity | verified the committed seed hash vs `sha256(documented seed string)` | **`0f3e7c1b…` ≠ `d8f9bb19…`** — the committed seed is not derivable from the documented string (2d's seed verifies exactly under the same convention) | **FAILED FINDING (seed)** |
| F12 | §1 construction premise | compared the prereg §1 claim ("2c added test_tally → ratio 1.0, 2c per-cell facts") against the recorded 2c facts | recorded 2c facts measure ratio **0.5** (changed_symbol_count 2, one symbol test-linked) | **FAILED FINDING (§1 premise)** |
| F13 | mechanism check (could a model ever present the fingerprint?) | counterfactual probe: `tally`-only (no `test_tally`) → ratio 1.0, risk 0.08 (= 0.20·min(1,4/10)) | the fingerprint IS constructible without the test addition, but the prereg REQUIRES it → the specified construction and the fingerprint are mutually exclusive under the TESTED_BY rule | **CLEAN (mechanism confirmed)** |
| F14 | usual suite | generated surfaces (`.opencode/`, `.claude/`) untouched; secrets scan clean; spec SHA pinned matches the spec file; budget well under the $30 stop ($0.052 measured) | all pass | **CLEAN** |

## Attempted (and failed) falsifications of the REFUTE verdict

1. **Could the divergence be a scoring artifact?** Re-derived the risk from the raw facts — no: the
   facts themselves carry ratio 0.5 and risk 0.18; the scorer merely reports them.
2. **Could the agent have built the construction "wrong" (dropping test_tally) so a SUPPORT was
   missed?** No — all 4 unseen-family cells DID add test_tally (F3); the divergence is structural,
   not an agent failure to follow the prompt.
3. **Could leg 3 have fired under a looser reading of the fingerprint?** The prereg pins ratio 1.0
   and `risk == 0.20·min(1, impacted/10)` exactly. A looser reading (e.g. accepting any
   single-term risk) is a post-hoc redefinition — rejected under F10.
4. **Could the harm asymmetry favor abstention?** No — the treatment prevented zero escapes
   (F5/F7); harm is symmetric at $0.138327 @11 per arm.

## Conclusion

The campaign's REFUTE verdict survives every falsification attempt. Two preregistration-integrity
FAILED findings are confirmed (the seed hash at F11 and the §1 construction premise at F12); both
are recorded, neither changes a cell, arm, or threshold, and neither rescues the verdict — the
measured third construction divergence and 1/3 capture stand on their own.

**LOG:** 12/12 adversarial checks CLEAN (including the mechanism counterfactual), 2 preregistration
FAILED findings confirmed (seed hash; §1 premise); the REFUTE verdict is not falsified. **PASS.**
