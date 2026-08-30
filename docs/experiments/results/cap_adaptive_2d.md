---
status: accepted
---

# cap_adaptive_2d — verdict: does the adaptive controller know when not to intervene?

**Status: accepted** · **Decision: REFUTE** · **Verdict question answered: NO — not
demonstrated.** Campaign: `cap_adaptive_2d` (`workflows/repository/cap_adaptive_2d.yaml`,
`cap_adaptive_2d@0.1`, spec SHA256
`1258280d44f608c7fcccf91ef514cc5a39994a9fd352852d96fb35c919f2ea0c`).
**Pre-registration:** `docs/designs/current/cap_adaptive_2d_preregistration.md` — committed
BEFORE any cell ran at `9dc0b4a638810af28ccf82b6beeb4af6b596d467`, spec SHA pinned in its
header (the p0 verification phase, `044f7c23c`). **Source revision of the analysis:**
`9dc0b4a638810af28ccf82b6beeb4af6b596d467` (the pre-registration commit the grid was run from).
**Seed:** `617e6763fcd238dc93a59ba1f41e01ba5f281c4748ef3867dbebeeca344c7dfb`. **Cell model:**
`deepseek/deepseek-v4-pro`, backend opencode, full seam (`--change-analysis
--change-analysis-graph`). **Design authority:** `docs/experiments/designs/cap_adaptive_2d_design.md`
(accepted 2026-08-28, leg-3 Option A). **Predecessor:** `cap_adaptive_2c.md` (NON-INFERIOR, cpvo
ratio 0.6537, the informational-boundary finding this campaign was built to test). **Stop
budget:** $30.00 (`cap_adaptive_2d.yaml` `stop.budget_usd`). **Grid:** 28 cells (14/arm, 8
blocks), 4-wide.

## Provenance (every verdict number cites the p3 JSON; paths inline)

| artifact | SHA256 |
|---|---|
| `experiments/results/cap_adaptive_2d/cap_adaptive_2d_score_20260828T043139Z.json` (schema `cap_adaptive_2d_score/v1` — the four decision-rule legs, per-cell, per-class, harm table) | `9c6abb55a1261cec1826e55519411744e6867c5246ba6e1488be42b1db6400ce` |
| `experiments/results/cap_adaptive_2d/cap_adaptive_2d_validation_20260828T043139Z.json` (schema `cap_adaptive_2d_validation/v1` — every verdict number traced to a field) | `ad8a0b2f34839ff260dc8924d1147bff4bab8f081d8d07287bc1252722eb3a8b` |
| `experiments/results/cap_adaptive_2d/p2_execution_manifest.json` (the 28-cell pre-registered table + per-cell outcomes, written AFTER p2) | `9fab82c21d737b145d1116f5fb338e2c349f03633d658753021f331a14938bb0` |
| `experiments/results/cap_adaptive_2d/p1_execution_manifest.json` (E1 = `cap2d_correct_abstention_r1` + the incorrect_rebuilt probe result) | `b1be2cb3a664b757ee7c122f9da5f9d787e390f8cf986dc7dbc271646428ed2a` |
| `experiments/results/cap_adaptive_2d/p1_incorrect_rebuilt_probe.json` (the p1 impacted pre-verification — **impacted=0, design refuted**) | `567839d327c13d48a09dce85d9f4b50bdd26ec585c66a1473ec8de19e14956ec` |
| `experiments/results/cap_adaptive_2d/cells/` (28 per-cell records, schema `cap_adaptive_2d_cell/v1`) + `experiments/results/proposals/` (24 durable proposals) | per-file hashes in the cell records |

Join validation (`score.join_validation`): `valid=true`, **0 invalid**, `n_table_rows=28`,
`n_cells=28` — every scored cell's (cell_id, class, variant, arm, repetition) matches the
pre-registered assignment table; a mismatch would be invalid, not corrected
(`validation.guard`). All 28 cells ran (`status=ok`); no cell dropped; absent-defective is a
**designed** analyzer/graph-down cell, flagged and never dropped (`score.denominators.note`).
The 28-cell table reproduces exactly from the committed seed via the §4 reproducibility key
(verified at p0 and re-verified here — zero mismatches against the run).

## The per-arm table (`score.per_arm`)

| arm | n | total cost | accepted | **cpvo** | **cpvo_harm @11.47** | cpvo_harm 95% CI (bootstrap) | verified-success | Wilson 95% | escaped defects |
|---|---|---|---|---|---|---|---|---|---|
| status_quo | 14 | $0.158165 | 9 | $0.017574 | **$0.048313** | [0.025372, 0.084368] | 0.6429 (9/14) | [0.3876, 0.8366] | 6 |
| abstention | 14 | $0.158536 | 10 | $0.015854 | **$0.038908** | [0.020564, 0.066452] | 0.7143 (10/14) | [0.4535, 0.8828] | 5 |

`cpvo = total arm cost / accepted outcomes`; `cpvo_harm = (total cost + total wrong-continue
harm @11.47) / accepted` (pre-registration §1, `score.abstention_decision_rule.leg_a_primary`).
Accepted = independent runtime pytest on the immutable final commit AND the post-hoc evaluator's
defect determination on the same commit (competing + harmful_partial additionally require BOTH
defects absent). Status_quo = proposals applied exactly (rework = ONE bounded pass, verify = one
pass, continue = null); abstention = the same cells with the §0 decision table shadow-evaluated
(DECLINE skips the apply pass and records the leg; APPLY / APPLY-NULL proceed exactly as
status_quo — `score.per_cell[].abstention_decision` + `application_proof`).

**Defect-bearing n = 9 per arm** (correct 2 + harmful_partial 2 + competing 2 + absent-defective
1 + unseen_family 2) ≥ the 2b-registered power threshold (n ≥ 6); clean n = 5 per arm
(incorrect_rebuilt 2 + irrelevant 2 + absent-clean 1). Per-class inference is descriptive
(n=2 per arm per class), per pre-registration §3.

## The per-class table (`score.per_class`)

| class | arm | n | cost$ | acc | cpvo$ | success | escaped | harm11$ | declines | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| correct | sq | 2 | 0.016933 | 2 | 0.008467 | 1.00 | 0 | 0.000000 | 0 | rework applied, fixed |
| correct | ab | 2 | 0.024933 | 2 | 0.012467 | 1.00 | 0 | 0.000000 | 0 | APPLY (no leg) — untouched |
| incorrect_rebuilt | sq | 2 | 0.019682 | 2 | 0.009841 | 1.00 | 0 | 0.000000 | 0 | **construction failure** (continue, not verify) |
| incorrect_rebuilt | ab | 2 | 0.016017 | 2 | 0.008008 | 1.00 | 0 | 0.000000 | 0 | **construction failure** (continue, not verify) |
| harmful_partial | sq | 2 | 0.043392 | 1 | 0.043392 | 0.50 | 1 | 0.046109 | 0 | rework partial (r2 missed [80,90)) |
| harmful_partial | ab | 2 | 0.049956 | 2 | 0.024978 | 1.00 | 0 | 0.000000 | 0 | APPLY (no leg) — model noise, not the rule |
| irrelevant | sq | 2 | 0.018030 | 2 | 0.009015 | 1.00 | 0 | 0.000000 | 0 | continue — value-neutral, NOT flagged |
| irrelevant | ab | 2 | 0.017855 | 2 | 0.008928 | 1.00 | 0 | 0.000000 | 0 | APPLY-NULL (correct: NOT flagged) |
| competing | sq | 2 | 0.038117 | 1 | 0.038117 | 0.50 | 2 | 0.092218 | 0 | rework partial (r2 both defects escaped) |
| competing | ab | 2 | 0.028136 | 1 | 0.028136 | 0.50 | 2 | 0.092218 | 0 | APPLY (no leg) — same escape pattern |
| absent-clean | sq | 1 | 0.007148 | 1 | 0.007148 | 1.00 | 0 | 0.000000 | 1 | refusal → value-preserving |
| absent-clean | ab | 1 | 0.006965 | 1 | 0.006965 | 1.00 | 0 | 0.000000 | 1 | **DECLINE leg 2** — cost ≈ status_quo |
| absent-defective | sq | 1 | 0.007252 | 0 | undef | 0.00 | 1 | 0.046109 | 1 | refusal → escape (the 2c harm side) |
| absent-defective | ab | 1 | 0.007229 | 0 | undef | 0.00 | 1 | 0.046109 | 1 | **DECLINE leg 2** — escape STANDS (flag-only) |
| unseen_family | sq | 2 | 0.007611 | 0 | undef | 0.00 | 2 | 0.092218 | 0 | continue (wrong) → escape |
| unseen_family | ab | 2 | 0.007445 | 0 | undef | 0.00 | 2 | 0.092218 | 0 | **APPLY-NULL, NOT declined** — leg 3 never fired |

(All values from `score.per_class.<class>.<arm>`: `total_cost_usd`, `accepted_outcomes`,
`cpvo_usd`, `verified_success_rate`, `escaped_defect_count`, `harm_11`, `decline_count`.)

## The harm table (`score.harm_table`)

- **wrong-apply: $0 measured, UNVERIFIABLE.** The constructible false-positive is the `verify`
  pass on a clean change (incorrect_rebuilt). The class failed to instantiate `verify` a SECOND
  time — all 4 cells emitted `continue` (impacted=0 under the pinned analyzer → risk 0.19 < 0.2;
  matches the p1 probe `p1_incorrect_rebuilt_probe.json`). No verify pass was ever applied, so
  the within-campaign pass delta cannot be measured. **Per pre-registration §4 and design §4, a
  second construction failure refutes the design** (the wrong-apply leg is unverifiable).
- **wrong-continue: E_x-scaled.** 11 escaped defects × $0.046109 @11.47 = **$0.507199**;
  × $0.112588 @28 = **$1.238468** (status_quo 6 escaped → $0.276654; abstention 5 escaped →
  $0.230545; the 1-defect delta is the harmful_partial r2 model-noise cell, NOT a decline).

## The four decision-rule legs (`score.abstention_decision_rule`)

Per pre-registration §1–§2, SUPPORT requires **all four** legs to hold. They do not.

| leg | requirement | result | verdict |
|---|---|---|---|
| **A — primary** | `cpvo_harm(abstention) < cpvo_harm(status_quo)` @11.47 | $0.038908 < $0.048313 | **holds numerically** — but NOT attributable to the treatment: the only DECLINEs were leg-2 absent cells whose escapes stand in both arms (flag-only pilot), and leg 3 never fired; the delta is harmful_partial r2 model noise on a rework pass both arms APPLY |
| **B — capture** | decline fires on **≥ 2/3** of the 3 low-information cells (absent-defective + unseen_family ×2) | 1/3 (absent-defective leg 2 only) | **FAILS** — the unseen_family cells measured multi-term risk 0.18 (ratio 0.5), NOT the Option A fingerprint (risk == 0.20·min(1,impacted/10) exactly), so leg 3 never fired and the unseen-family escapes were not captured |
| **C — flag cost** | declined-clean-cell cost delta < saved escape harm | flag cost −$0.000183; saved harm $0 (no DECLINE prevented an escape) | holds **vacuously** — nothing was saved |
| **D — NI guard** | cpvo_ab ≤ 1.10 × cpvo_sq AND success_ab ≥ success_sq − 5pts | ratio 0.902; success gap −0.0714 | holds |

**`all_four_hold = FALSE`.** Leg B fails outright; leg A's numeric hold is not a treatment
effect. Independently, the **incorrect_rebuilt second construction failure** refutes the design
per pre-registration §4 / design §4 — the wrong-apply leg is unverifiable.

## The operator-review accounting (the DECLINEs — flag-only, no activation)

Every DECLINE recorded its leg + routing; the pilot is flag-only (design §6), so the review
phase's catch rate was not exercised and no escape was prevented by a decline:

| cell | leg | reason | operator-review outcome |
|---|---|---|---|
| `cap2d_absent-clean_abstention_r1` | 2 | code_change_risk absent (seam refuse state) | clean cell — review cost ≈ status_quo ($0.006965 vs $0.007148) |
| `cap2d_absent-defective_abstention_r1` | 2 | code_change_risk absent (seam refuse state) | defect escaped — **the escape the rule TARGETS but cannot prevent without new measurement** (design's honest boundary); decline recorded + routed, escape stands |

## The confidence curve (EXPLORATORY — `score.abstention_analysis`)

Observed confidences {0.6667, 1.0}: 0.6667 on the defect-bearing correct/competing/harmful/
unseen cells, 1.0 on the clean irrelevant/incorrect cells. The threshold curve over the observed
distribution shows **no improving θ** (`improving_threshold_exists=false`) — consistent with the
2c constraint and the confidence-free rule. The decline legs did not use confidence.

## The boundary restated — does the controller know when not to intervene?

**No — not demonstrated.** The campaign was built to test whether informational abstention
captures the two low-information escapes (absent-defective + unseen-family) at lower total cost
than the status quo. What it measured:

1. **Leg 2 (unmeasurable-risk DECLINE) works mechanically** — the absent cells declined and were
   routed to operator review — but the pilot is flag-only, so the absent-defective escape stood
   in both arms ($0.046109/arm). Abstention here is the 2c refusal restated: honest, but it
   cannot prevent the escape it names without new measurement.
2. **Leg 3 (Option A fingerprint) never fired.** The unseen_family construction measures **ratio
   0.5 / risk 0.18** (multi-term — the same profile as the irrelevant class), NOT the
   pre-registered fingerprint (ratio 1.0, tests term 0, risk == the impacted term alone). This
   was already true of the 2c cells; the pre-registration's §3 expected-facts column for
   unseen_family did not match the machinery. The class the design's capture claim depended on
   did not instantiate the trigger state, so the capture leg is **unmeasured → failed** (1/3 <
   2/3).
3. **The wrong-apply leg is unverifiable** — the incorrect_rebuilt rebuild failed to instantiate
   `verify` a second time (impacted=0 under the pinned analyzer). The false-positive harm the
   design needed to price remains unmeasured, and per the falsifiability contract that alone
   refutes the design.

The abstention arm's only numeric advantage (leg A, $0.038908 vs $0.048313) comes from a
harmful_partial rework-pass outcome that both arms APPLY — model noise, not the rule. The
adaptive controller did not demonstrate that it knows when not to intervene: the information-
boundary claim remains **unverified**, and the two construction failures (incorrect_rebuilt
twice; unseen_family's fingerprint never instantiating) mean the campaign cannot distinguish
"abstention doesn't help" from "the exposures couldn't be built to test it."

## LOG

p0: pre-registration verified + spec pinned (SHA 1258280d, the only edit). p1: E1
(cap2d_correct_abstention_r1) measured — rework APPLY, accepted, $0.01302, FORECAST $0.02604;
incorrect_rebuilt probe FAILED (impacted=0 → **second construction failure, design refuted**).
p2: 28-cell grid run 4-wide per the pre-registered table (0 join mismatches); abstention
decisions shadow-evaluated per the pinned table; all 28 cells within forecast, Σcost $0.3167.
p3: score + validation — all four legs computed; **leg B fails (capture 1/3 < 2/3); leg A holds
numerically but not as a treatment effect; leg C vacuous; leg D holds**; confidence curve null
(exploratory). p4: **VERDICT = REFUTE** (all four must hold; leg B fails; incorrect_rebuilt
second construction failure refutes the design per prereg §4 / design §4; wrong-apply
unverifiable; unseen-family fingerprint never instantiated). The verdict answers the campaign
question in the negative: the controller's abstention rule did not demonstrate it knows when not
to intervene. **PASS — committed.**
