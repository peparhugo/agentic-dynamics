---
status: accepted
---

# cap_adaptive_2e — verdict: the leg-3 capture reconstruction (does the Option A fingerprint fire?)

**Campaign:** `cap_adaptive_2e` (`cap_adaptive_2e@0.1`; spec SHA256
`b0ad1c4fe65d364478db4c508e694b58a09c2377a8063efe514796a1d853e4ad`).
**Preregistration:** `docs/designs/current/cap_adaptive_2e_preregistration.md`
(`d1a0ad777`, committed BEFORE any cell ran).
**Source revision (main HEAD at campaign start):** `3458f916d`.
**Score artifact:** `experiments/results/cap_adaptive_2e/cap_adaptive_2e_score_20260828T144818Z.json`
SHA256 `4564cb89fb2aa2fe6c500d9c53d24848c2d6c8ab0c82660b24d06bfe5a1ffbfc`.
**Validation artifact:** `cap_adaptive_2e_validation_20260828T144818Z.json` (traces every verdict
number to an immutable record field). **p1 manifest:** `68a43cf2…`; **p2 manifest:**
`32562eeb…`; **p1 probe:** `57cb33f1…`.

**VERDICT: REFUTE.** The Option A fingerprint FAILED to construct — the third construction
divergence, measured in the p1 pre-verification probe AND in every one of the four agent-built
unseen-family cells. Leg-3 is therefore **refuted as a mechanism**, not merely unmeasured
(preregistration §2 falsifiability clause). Capture is also below the 2/3 floor (1/3), but the
construction failure alone decides the verdict (preregistration §4: "REFUTE if the fingerprint
fails to construct (third failure)").

## 1. Did the cells present the fingerprint? — NO (measured, every cell)

The fingerprint condition (prereg §4): `changed_symbols_with_tests_ratio == 1.0` AND severity terms
zero AND `code_change_risk == 0.20·min(1, impacted/10)` within `1e-9`.

| cell | ratio | severity terms | impacted | risk | fingerprint risk expected | fingerprint holds |
|---|---|---|---|---|---|---|
| p1 probe (construction pre-verification) | **0.5** | 0 / 0 | 4 | **0.18** | 0.08 | **NO — divergence** |
| `cap2e_unseen_family_abstention_r1` | **0.5** | 0 / 0 | 4 | **0.18** | 0.08 | **NO — divergence** |
| `cap2e_unseen_family_abstention_r2` | **0.5** | 0 / 0 | 4 | **0.18** | 0.08 | **NO — divergence** |
| `cap2e_unseen_family_status_quo_r1` | **0.5** | 0 / 0 | 4 | **0.18** | 0.08 | **NO — divergence** |
| `cap2e_unseen_family_status_quo_r2` | **0.5** | 0 / 0 | 4 | **0.18** | 0.08 | **NO — divergence** |

Every measured risk `0.18 = 0.20·(1−ratio) + 0.20·min(1, impacted/10) = 0.10 + 0.08` — the
multi-term risk, byte-identical to the 2d divergence, now reproduced deterministically with the
REQUIRED `test_tally` in place. The construction was fidelity-verified in the commit trails: every
cell's implement commit contains `test_tally` (asserting only the return value — it passes, the
aliasing is invisible to it). **Construction fidelity: FAIL** (condition 1 of the decision rule).

**The mechanism (measured, not assumed):** the TESTED_BY rule
(`src/agentic_dynamics/core/language.py:811`) links only MODULE symbols to a matching test file; a
new test-file function is itself a changed symbol but is NEVER test-linked. The preregistration's
REQUIRED `test_tally` addition therefore forces `changed_symbol_count = 2` while only `tally` is
test-linked → `ratio = 0.5` → multi-term risk. The ratio-1.0 fingerprint IS constructible — but
ONLY by adding `tally` without the `test_tally` addition (counterfactual probe measured ratio 1.0,
risk 0.08) — which violates the preregistration's REQUIRED construction. **The specified
construction and the fingerprint are mutually exclusive under the real measurement rule.** This is
the third construction divergence (2c/2d measured ratio 0.5; 2e reproduces it with the enforced
construction), so leg-3 is refuted as a mechanism.

## 2. Did leg 3 fire on the unseen-family cells? — NO

| cell | abstention decision | leg | reason |
|---|---|---|---|
| `cap2e_unseen_family_abstention_r1` | APPLY_NULL | — | risk 0.18 multi-term, NOT the fingerprint → apply-null (unchanged, not flagged) |
| `cap2e_unseen_family_abstention_r2` | APPLY_NULL | — | same |
| `cap2e_absent-defective_abstention_r1` | **DECLINE** | **2** | risk absent (seam refused) — the mechanical leg-2 check |

Leg 3 never fired on a single unseen-family cell: the fingerprint the leg consumes never
materialized. The only decline is the absent-defective cell's mechanical leg-2 refusal — which
declines the SAME way in both arms (the escape stands in both; the pilot is flag-only, no fix).

## 3. The escapes captured vs standing

| arm | unseen-family escaped defects | absent-defective escaped defects | total escaped | decline count | capture |
|---|---|---|---|---|---|
| status_quo | 2 | 1 | **3** | 1 (shadow) | — |
| abstention | 2 | 1 | **3** | 1 (leg 2) | **1/3** |

The abstention arm declined on 1 of the 3 low-information cells (`cap2e_absent-defective_abstention_r1`,
leg 2). **Capture 1/3 < 2/3 floor — FAIL** (condition 2 of the decision rule). The unseen-family
escapes (2 per arm) stand in BOTH arms because leg 3 never fired; the abstention treatment
prevented zero escapes.

## 4. The harm table (E_x 11.47/28)

`wrong-continue = E_x × base_downstream_defect_cost ($0.004021)`; `E_x 11.4671` measured (sol, n=1),
`E_x 28` sourced (sensitivity). Wrong-apply is vacuous (no apply-class cells in this capture-only grid).

| measure | value |
|---|---|
| escaped defects per arm | 3 |
| wrong-continue @11 per defect | $0.046109 |
| **harm @11 per arm** | **$0.138327** (3 × 0.046109) |
| harm @28 per arm | $0.337764 (3 × 0.112588) |
| abstention vs status_quo harm | **identical** ($0.138327 both arms @11) — the treatment changed nothing |

The 2e score's harm table reproduces the 2d asymmetry as a symmetric baseline: both arms carry 3
escaped defects at the same cost. The abstention rule provided **zero capture value** here.

## 5. The decision rule (pre-registered)

| condition | holds | value |
|---|---|---|
| 1. construction fidelity | **FAIL** | probe + all 4 unseen-family cells diverge (third divergence) |
| 2. capture ≥ 2/3 of low-information cells | **FAIL** | 1/3 |
| 3. flag cost < saved escape harm | vacuous-reported | no clean cells; prevented escapes = 0 |
| 4. NI guard | NOT MEASURED | capture-only grid (by design) |

**VERDICT: REFUTE.** (a) The fingerprint failed to construct a third time — leg-3 refuted as a
mechanism, not merely unmeasured; (b) capture 1/3 < 2/3. Either alone decides REFUTE.

## 6. The boundary restated

The abstention rule cannot be tested at the exposure the design assumed, because the exposure is
unconstructible: the Option A fingerprint (`risk == 0.20·min(1, impacted/10)` with ratio 1.0)
cannot arise from a change that ADDS a test — the added test itself is a changed symbol the
TESTED_BY rule never counts, so the tests term can never be zero when the construction adds
`test_tally`. The design's leg-3 condition and the construction the preregistration REQUIRED are
logically incompatible. **The rule's leg-3 does not know when to intervene on this family, because
the family cannot be presented to it under the specified construction.**

## 7. Preregistration deviations (p0 findings, carried through)

1. **Seed (FAIL):** the committed seed hash `0f3e7c1b…` ≠ `sha256("cap_2e|reconstruct-unseen-family|fingerprint|20260828")`
   (measured `d8f9bb19…`) — recorded, never corrected; the enumerated grid is unaffected.
2. **§1 construction premise (FAIL):** the preregistration claims "2c's construction added
   `test_tally` → ratio 1.0 (2c per-cell facts)"; the recorded 2c facts measure ratio 0.5. The
   premise's own evidence contradicts it.

Neither deviation changed a cell, arm, or threshold; both are reported here and in the adversarial
review.

## GUARD

Every number above is traced to the p3 score JSON (SHA256 `4564cb89…`) and its validation artifact;
the fingerprint arithmetic is re-derived from the recorded facts, never from proposal text; no
post-hoc redefinition was made. The seed deviation and the construction-premise deviation are
pre-registered deviations reported as FAILED findings, not re-labelled.

**LOG:** probe divergence measured (ratio 0.5, risk 0.18 ≠ 0.08) → all 4 grid cells reproduce it →
leg 3 never fired → capture 1/3 → harm symmetric $0.138327 @11 per arm → verdict REFUTE (third
construction divergence refutes leg-3 as a mechanism). **PASS — verdict committed.**
