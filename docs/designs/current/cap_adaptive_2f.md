---
status: accepted
---

# cap_adaptive_2f — verdict: the Option B follow-up (the wider leg-3 net) — flag-cost measured, capture refuted at the wall

**Campaign:** `cap_adaptive_2f` (`cap_adaptive_2f@0.1`; spec SHA256
`aac533b6b4400e5a48ef3e43b9214a401bda799fccaa90dcdeee820986d69ec3`).
**Preregistration:** `docs/designs/current/cap_adaptive_2f_preregistration.md`
(`d199c50b6`, committed BEFORE any cell ran; the spec SHA was appended to its header on the spec
commit `694cc6029` — the ONLY allowed edit, done once).
**Source revision (main HEAD at campaign start):** `694cc6029`.
**Score artifact:** `experiments/results/cap_adaptive_2f/cap_adaptive_2f_score_20260828T210239Z.json`
SHA256 `fa6bc16b5c32773c…`.
**Validation artifact:** `cap_adaptive_2f_validation_20260828T210239Z.json` (traces every verdict
number to an immutable record field). **p1 manifest:** `p1_execution_manifest.json`; **p2
manifest:** `p2_execution_manifest.json`; **p1 probes:** `p1_unseen_family_probe.json` +
`p1_trivial_clean_probe.json`.

**VERDICT: REFUTE.** Option B's capture refutes at the ratio wall exactly as pre-registered —
capture 1/3 < 2/3 — and the flag-cost ceiling is vacuous (no escape captured). The campaign's NEW
information is the flag-cost magnitude: **$0.000634** — the price B's wider net pays on the four
trivial fully-tested clean changes it newly declines, with no escapes saved to compare. The wider
net does NOT rescue capture; it prices its own false positives at a small but non-zero measured
number.

## 1. The construction probes (p1) — both constructions measured, both pre-registered checks confirmed

| probe | construction | ratio | risk | severity | B trigger fires | expectation |
|---|---|---|---|---|---|---|
| unseen-family | 2e-verbatim (tally mutation + REQUIRED test_tally) | **0.5** | 0.18 | 0/0 | **NO** | ratio 0.5 (the wall) — **CONFIRMED** |
| trivial_clean | private-variable rename in a tested function | **1.0** | 0.06 | 0/0 | **YES** | ratio 1.0 AND risk < 0.2 — **CONFIRMED** |

Both constructions built and measured with the real stack (sonar + lsp + graph + the
`code_change_facts/v2` reducer). The unseen-family probe reproduces the 2e mutual-exclusivity
finding deterministically: a new test-file function is a changed symbol that is never test-linked,
so the REQUIRED `test_tally` forces ratio 0.5. The trivial_clean probe confirms B's trigger CAN
fire on a genuinely trivial fully test-linked clean change (the flag-cost leg is constructible).

## 2. The ratio table (measured, every cell)

| cell | class | arm | ratio | risk | severity | B trigger |
|---|---|---|---|---|---|---|
| `cap2f_unseen_family_abstention_r1` | unseen_family | abstention | **0.5** | 0.18 | 0/0 | NO |
| `cap2f_unseen_family_abstention_r2` | unseen_family | abstention | **0.5** | 0.18 | 0/0 | NO |
| `cap2f_unseen_family_status_quo_r1` | unseen_family | status_quo | **0.5** | 0.18 | 0/0 | NO |
| `cap2f_unseen_family_status_quo_r2` | unseen_family | status_quo | **0.5** | 0.18 | 0/0 | NO |
| `cap2f_trivial_clean_abstention_r1` | trivial_clean | abstention | **1.0** | 0.06 | 0/0 | YES |
| `cap2f_trivial_clean_abstention_r2` | trivial_clean | abstention | **1.0** | 0.06 | 0/0 | YES |
| `cap2f_trivial_clean_status_quo_r1` | trivial_clean | status_quo | **1.0** | 0.06 | 0/0 | YES |
| `cap2f_trivial_clean_status_quo_r2` | trivial_clean | status_quo | **1.0** | 0.06 | 0/0 | YES |
| `cap2f_absent-defective_abstention_r1` | absent_defective | abstention | — | absent | — | leg 2 |
| `cap2f_absent-defective_status_quo_r1` | absent_defective | status_quo | — | absent | — | leg 2 |

Every unseen-family cell measures ratio 0.5 — the wall, reproduced in all four cells (and in the p1
probe). Every trivial_clean cell measures ratio 1.0, risk 0.06, severity zero — B's trigger fires.

## 3. The capture table — REFUTE (the expected wall)

| class (abstention arm) | declined | total | |
|---|---|---|---|
| unseen_family (B trigger) | 0 | 2 | the wall — B never fires |
| absent_defective (leg 2) | 1 | 1 | mechanical |
| **low-information capture** | **1** | **3** | **1/3 < 2/3 — FAIL** |

The abstention arm declined on 1 of the 3 low-information cells (the absent-defective leg-2
decline only). B's trigger never fired on a single unseen-family cell: every one measured ratio
0.5, and B needs ratio >= 1.0. **Capture 1/3 < 2/3 — the fourth construction divergence, by the
same mechanism that refuted A** (the unseen-family construction and any ratio-1.0 trigger are
mutually exclusive under the real measurement rule). The unseen-family escapes (2 per arm) stand
in BOTH arms.

## 4. The flag-cost table — THE PRIMARY (B's new claim, measured)

The wider net's price on the trivial fully-tested clean changes it newly declines (status-quo
continues, B declines):

| arm | trivial_clean total cost | n |
|---|---|---|
| status_quo (continue = null) | $0.016622 | 2 |
| abstention (DECLINE leg 3 + operator-review routing) | $0.017256 | 2 |
| **flag cost** | **$0.000634** | — |

`flag_cost = Σ(abstention trivial-clean) − Σ(status-quo trivial-clean) = $0.000634` — the decline
overhead + operator-review routing on changes that needed nothing. The saved-escape-harm side is
**$0**: no abstention DECLINE prevented an escape (the pilot is flag-only, and the unseen-family
escapes stand in both arms — the wall). **The ceiling is VACUOUS** (captured escapes = 0), so the
PRIMARY comparison cannot hold — reported, never re-scoped. B's decline cost is measured at
$0.000634 per cell-pair ($0.000317/cell), with no escapes saved to compare.

## 5. The harm table (E_x 11.47/28)

| measure | value |
|---|---|
| escaped defects per arm | 3 (unseen-family x2 + absent-defective x1) |
| wrong-continue @11 per defect | $0.046109 |
| **harm @11 per arm** | **$0.138327** (3 × 0.046109) |
| harm @28 per arm | $0.337764 (3 × 0.112588) |
| abstention vs status_quo harm | **identical** ($0.138327 both arms @11) — the treatment changed nothing |

The abstention rule provided **zero capture value**: both arms carry the same 3 escaped defects at
the same cost. The flag-cost leg adds $0.000634 on the abstention side with no saved harm to offset.

## 6. The decision rule (pre-registered)

| condition | holds | value |
|---|---|---|
| A. capture ≥ 2/3 of the 3 low-information cells | **FAIL** | 1/3 |
| B. flag-cost ceiling holds non-vacuous | **FAIL** | vacuous (saved harm = $0); flag cost $0.000634 |
| **SUPPORT ⟺ A AND B** | **NO** | REFUTE |

**VERDICT: REFUTE.** (a) capture 1/3 < 2/3 — the pre-registered expectation, the fourth
divergence by the same mechanism that refuted A; (b) the flag-cost ceiling is vacuous (no escapes
captured, so no saved harm to compare the price against). Either alone decides REFUTE.

## 7. The boundary restated

Option B closes the leg-3 question with measured numbers. **The wider net does NOT rescue
capture**: the ratio wall is structural — the unseen-family construction measures 0.5 under the
real TESTED_BY rule, so B's ratio-1.0 trigger cannot co-occur with the family's defect, exactly as
2e found for A's fingerprint. **B does price its own false positives**: the flag-cost leg measured
$0.000634 on four trivial fully-tested clean changes — B declines work that needed nothing, at a
small but non-zero measured cost, with zero escapes saved. The abstention rule knows when NOT to
intervene only for the refusal states (legs 1-2); the invisible-defect states remain a measurement
frontier — no production activation, the rule stays shadow-only.

## 8. Preregistration deviations (p0 findings, carried through)

1. **Seed (FAIL):** the committed seed hash `e4f9c1a7…` ≠ `sha256("cap_2f|option-B|flag-cost-primary|20260828")`
   (measured `4d5ed42e…`) — recorded, never corrected; the enumerated 10-cell table is unaffected.

No cell, arm, or threshold deviated from the preregistration.

## GUARD

Every number above is traced to the p3 score JSON (SHA256 `fa6bc16b5c32773c…`) and its validation
artifact; the ratio and the B trigger are re-derived from the recorded facts, never from proposal
text; no post-hoc redefinition was made. The seed deviation is a pre-registered deviation reported
as a FAILED finding, not re-labelled.

**LOG:** probes confirmed (wall ratio 0.5; trivial_clean trigger fires) → grid reproduced both
constructions exactly (unseen-family 0.5 wall in all 4 cells; trivial_clean 1.0/0.06 trigger fires
in all 4) → capture 1/3 → flag-cost $0.000634 measured, vacuous ceiling → harm $0.138327/arm @11 →
verdict REFUTE (both conditions fail as pre-registered; B's new information is the flag-cost
magnitude — the wider net prices its own false positives at $0.000634 and rescues nothing).
**PASS — verdict committed.**
