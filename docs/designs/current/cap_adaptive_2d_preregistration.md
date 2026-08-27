---
status: accepted
---

# cap_adaptive_2d — pre-registration (p0): the informational-abstention campaign (does the adaptive controller know when not to intervene?)

**Status: accepted · PRE-REGISTERED — committed BEFORE any cell runs.**
**Campaign:** `cap_adaptive_2d` (`workflows/repository/cap_adaptive_2d.yaml` SHA256
`1258280d44f608c7fcccf91ef514cc5a39994a9fd352852d96fb35c919f2ea0c`; `cap_adaptive_2d@0.1`). **Design authority:** `docs/designs/current/cap_adaptive_2d_design.md` — the
informational-abstention design, **accepted 2026-08-28 (operator)**, leg-3 trigger pinned at
**Option A** (the narrow fingerprint). **Pre-registration pattern:** the 2c pre-registration
(`cap_adaptive_2c_preregistration.md`, SHA256 `0f3a5de755784a6e9f8a71da3e7706782cddf930095fbc65a685ccc361da5e3d`).
**Predecessor verdicts (all measured):** `cap_adaptive_2c.md` (the 2c verdict — NON-INFERIOR,
cpvo ratio 0.6537, success gap −0.3333, abstention curve: NO improving confidence threshold;
the boundary is informational, not confidence-based) SHA256 `076751e4…`-score-backed; `cap_2b.md`
(NON-INFERIOR, ratio 0.7857); the measured-E_x campaign score SHA256 `6d3c7a7c…`.
**Cell model:** `deepseek/deepseek-v4-pro`, backend opencode, full seam
(`--change-analysis --change-analysis-graph`) — unchanged from 2b/2c. **Stimulus family**
(reused verbatim from 2c): `cap_2a_cell_clean@0.1` SHA256 `65730a22…`,
`cap_2a_cell_critical@0.1` SHA256 `6ecb2bd9…`, `cap_2a_cell_style@0.1` SHA256 `eaf7e806…`
plus the 2c-built cells (correct/irrelevant/competing/absent/unseen-family constructions).
**Stop budget:** $30.00. **Grid concurrency:** 4-wide cell execution in p2 (the tested sweep
norm; `sweep_silent_mode.py` `max_workers=4`), 28 cells → 7 batches of 4.

> **The registration rule:** nothing in §0–§8 may be redefined after this commit. A deviation
> from this pre-registered plan — a redefined capture floor, a reseeded assignment, a dropped
> cell, a post-hoc re-labelled class — is a **FAILED finding** in p5, not a limitation. The
> assignment table (§4) is the canonical record; the seed is the reproducibility key. Every
> number below is derived from a cited artifact (hashes in the header) or from the arithmetic
> of the pinned machinery (§0); the class constructions are buildable from this document alone.

---

## 0. The pinned machinery facts the classes and the abstention rule are grounded in

The stimulus classes are built **against the verifier's real machinery** — the 2c §0 pins,
restated verbatim (nothing changed; the treatment is code-unchanged, 2c hard-rule 10):

**The proposal action tree** (`verify_proposal.py` `build_verify_proposal`, lines 169–255):

1. **`rework`** (depth 3) ⟺ `new_sonar_critical_count > 0` **or** `new_lsp_error_count > 0`.
2. **`continue`** (depth 0, empty scope) ⟺ `changed_symbol_count == 0`.
3. **`verify`** (depth = `_risk_depth(risk)`: 1 if risk < 0.15, 2 if risk < 0.3, else 3) ⟺
   `code_change_risk >= VERIFY_RISK_THRESHOLD` with **`VERIFY_RISK_THRESHOLD = 0.2`**
   (`verify_proposal.py:61`).
4. **`continue`** (depth 0) otherwise.

The seam **refuses** (`ValueError`) when any required fact is missing or unparseable — never a
hand-authored proposal past a failing seam.

**The `code_change_risk` formula** (`code_change_facts.py` module docstring + `RISK_WEIGHTS`,
weights `[P]` operator policy, UNCHANGED):

```
risk = [ 0.35·min(1, new_sonar_critical_count/10)
       + 0.25·min(1, new_lsp_error_count/10)
       + 0.20·(1 − changed_symbols_with_tests_ratio)
       + 0.20·min(1, impacted_symbol_count/10) ] / Σ(weights of the MEASURABLE terms)
```

Terms whose analyzer did not run / whose ratio is deferred / whose count is absent are
**omitted** and the remaining weights **renormalized**; `risk` is `None` (fact omitted) when no
term is measurable. `new_sonar_critical_count` is the **severity-filtered, change-introduced**
count (BLOCKER/CRITICAL only — a MAJOR finding NEVER counts). `changed_symbols_with_tests_ratio`
is under the TESTED_BY rule; **deferred (omitted) when no changed symbol is test-linked** —
"never 0". The runner's gates are unchanged: DEPLOY_GATE, COMMIT_PREFIX, watchdogs, checkpoints
(no checkpoint phases in this campaign), and the NO_CHANGES guard.

**The measured reference costs** (all MEASURED, from the cited score JSONs):

| quantity | value | artifact field |
|---|---|---|
| base downstream defect cost | **$0.004021** | escalation score JSON `base_downstream_defect_cost_usd` |
| E_x (openai/gpt-5.6-sol, n=1) | **11.4671** | escalation score JSON `per_model[0].E_x` |
| E_x (anthropic/claude-sonnet-5, n=1) | **12.5134** | escalation score JSON `per_model[1].E_x` |
| wrong-continue loss @ E_x=11.4671 | **$0.046109** | escalation score JSON `loss_table` |
| wrong-continue loss @ E_x=28 (sourced) | **$0.112588** | escalation score JSON `loss_table` |
| 2c cpvo ratio | **0.6537** [0.0112, 0.0152] vs [0.0161, 0.0254] per-arm CIs | 2c score JSON `decision_rule`/`per_arm` |
| 2c status-quo arm outcomes (the per-class baseline this campaign's abstention arm is compared against — §2) | correct: 2 accepted, 0 escaped · competing: 2 accepted, 0 escaped · irrelevant: 2 accepted · absent-clean: 1 accepted, 0 escaped · **absent-defective: 0 accepted, 1 escaped ($0.046109/arm @11.47)** · **unseen-family: 0 accepted, 2 escaped ($0.092218/arm @11.47)** · incorrect: construction failure (4 cells, `continue` not `verify`) | 2c score JSON `per_class` |
| 2c per-cell cost range | **$0.0039–$0.0164** | 2c score JSON `per_cell[].cost_usd` |
| 2c measured confidence at emission | {0.6667, 1.0} — 0.6667 on the defect-bearing correct/competing/unseen-family cells, 1.0 on the clean cells | 2c score JSON `abstention_analysis.per_decile` |

**The abstention rule under test (the design's proposal, pinned here — `[C]` control rule,
`requires_facts` all measured by `code_change_facts/v2`):**

| seam state (measured facts) | 2c status-quo behavior | **abstention behavior (2d)** |
|---|---|---|
| `analysis_revision_matches` **false or absent** | continue on stale risk / refuse | **DECLINE — leg 1** → operator review |
| `code_change_risk` **absent** (no term measurable — the seam's refuse state) | seam refuses → pass-through | **DECLINE — leg 2** → operator review |
| risk ≥ 0.2 (severity signal or tests-ratio-driven) | apply (verify/rework per the tree) | unchanged — **APPLY** |
| risk < 0.2, severity terms zero, tests term zero, **risk == 0.20·min(1, impacted/10) EXACTLY** (the impacted term is the ONLY contributing term — the **Option A fingerprint**; the unseen-family state) | `continue` (wrong) | **DECLINE — leg 3** → operator review |
| any other risk < 0.2 state (multi-term risk — the irrelevant class, risk 0.18 = tests 0.10 + impacted 0.08) | `continue` | unchanged — **APPLY-NULL** (NOT flagged; Option A) |

The abstention decision is evaluated **per cell in the p2 harness** (campaign-side
orchestration, exactly as 2c's static/adaptive arm assignment was orchestrated): the cell runs
the 2c machinery unchanged; the harness reads the cell's measured facts + proposal, applies the
table above, and for the abstention arm either skips the apply pass (DECLINE, recording the
leg) or applies exactly per the proposal (APPLY / APPLY-NULL). **Treatment code-unchanged**:
`verify_proposal.py`, `_risk_depth`, `VERIFY_RISK_THRESHOLD`, `RISK_WEIGHTS`, the severity
filter — the abstention rule is shadow evaluated, never wired into the runner.

---

## 1. Primary outcome + secondary + the HARM model

**Primary — the abstention decision rule's headline comparison** (the design §5): on the pooled
grid, the abstention arm's **harm-inclusive total** `(Σ cost + Σ harm) / Σ accepted` must be
**strictly lower** than the status-quo arm's, at the measured E_x = 11.47 (sensitivity at 28):

```
SUPPORT  ⟺  cpvo_harm(abstention) < cpvo_harm(status_quo)   at E_x = 11.47
```

`cpvo_harm(arm) = (Σ cost_usd + Σ harm_usd) / Σ accepted` over the arm's 14 cells; cost = the
measured ledgered cell cost; accepted = `test_executed_success == true` (independent
`runtime.test_runner` on the immutable final commit) AND `defect_present_on_final_commit ==
false` (post-hoc evaluator on the same commit); competing and harmful_partial additionally
require BOTH defects absent (2c's pinned one-of-two semantics).

**Secondary — the three guard rails, all pre-registered (design §4 falsifiability):**

1. **Capture rate** (the abstention mechanism fires where it must): the decline fires on
   **≥ 2 of the 3 low-information cells per arm** — absent-defective (leg 2, mechanical by
   construction) + unseen-family ×2 (leg 3, Option A fingerprint). Per-class capture reported;
   the pooled floor is decided. Legs 1–2 are mechanical (the state IS the trigger); leg 3's
   capture is the empirical claim.
2. **Flag-cost ceiling** (the decline's cost on clean cells): the abstention arm's clean-cell
   overhead — the measured cost delta of the declined clean cells (absent-clean, and any
   clean cell the rule flags) vs the same class's status-quo cells — must be **< the saved
   escape harm** (escaped defects prevented × $0.046109 @11.47). The 2c absent-clean result
   (refusal cost the gate nothing) is the expectation; the measurement is the claim.
3. **Non-inferiority guard** (the rule did not bleed into the apply classes): the 2b/2c margin
   reused on the pooled grid — `cpvo_abstention ≤ 1.10 × cpvo_status_quo` AND
   `success_abstention ≥ success_status_quo − 5pts`. The correct/competing/harmful_partial
   cells must be accepted at the same rate in both arms.

**Confidence probes (re-check of the 2c constraint — analytic, no separate constructions):**
every cell's proposal record carries the measured confidence at emission (§7). The
**high-confidence-wrong** probe = the incorrect_rebuilt cells (all tests pass → confidence 1.0;
proposal `verify` on a clean change — the wrong-apply exposure) and the **low-confidence-correct**
probe = the correct cells (the failing boundary test → confidence 2/3 ≈ 0.6667; proposal `rework`
on a real defect). The verdict re-reports the 2c abstention curve over the 2d confidence
distribution and asserts: **no θ on confidence improves the abstention rule** — the rule's
decline legs must remain confidence-free (design §2 constraint).

**HARM (per-cell, the 2c model verbatim):**

1. **wrong-apply — the measured pass delta.** The constructible false-positive is the `verify`
   pass on a clean change (incorrect_rebuilt; a false-positive `rework` remains
   unconstructible under the severity filter — 2c filter-strength, restated). The pass cost is
   measured **within-campaign**: `mean(incorrect_rebuilt cell cost) − mean(irrelevant cell
   cost)` per arm — both clean, the only difference being the verify pass (irrelevant emits
   `continue`, no pass). The 2c incorrect class failed to instantiate (impacted=0, risk 0.19 <
   0.2); the 2d rebuild (§3) fixes the guarantee and the construction is **pre-verified** (the
   p1 measurement cell measures its facts before the grid runs; a cell whose facts do not
   instantiate `verify` is a construction failure — flagged, recorded, never re-labelled, never
   silently passed).
2. **wrong-continue — E_x-scaled.** For each **escaped defect** (defect on the final commit
   whose cell did not apply a fix): `harm = E_x × $0.004021` = **$0.046109 @11.47** /
   **$0.112588 @28** per escaped defect. Arises in: correct status_quo (rework ignored? — no:
   status_quo applies; see §3), harmful_partial (unfixed defect), absent-defective (decline →
   escape in BOTH arms — the abstention arm's decline IS the 2c refusal, so the escape is the
   measured abstention-harm side), unseen-family (status_quo continues wrong; abstention's leg-3
   decline either captures or escapes), competing partial_rework.

**Denominator discipline (2b/2c carried forward):** a cell stopped by the budget/SLA guard or
flagged (graph-down/analyzer-down) is reported **in its denominator** with its status, never
silently dropped. The absent variants are **designed** degraded cells — flagged as designed,
never dropped. A cell scored under a different arm than its assignment is **invalid**, not
corrected.

---

## 2. Decision rule + the status-quo baseline

**The comparison is within-campaign, both arms re-run** (28 cells): status_quo = the 2c
adaptive behavior (proposals applied exactly: rework = ONE bounded pass, verify = one pass,
continue = null); abstention = the same cells with the abstention policy (§0 table) shadow
evaluated by the p2 harness. The 2c per-class outcomes are cited (§0) as the **prior** the
status-quo arm is expected to reproduce — NOT as the comparison baseline; the baseline is the
2d status-quo arm itself, block-randomized with the abstention arm within every class.

**The decision rule (pre-registered, §1):** SUPPORT ⟺ `cpvo_harm(abstention) <
cpvo_harm(status_quo)` at E_x = 11.47 **AND** capture ≥ 2/3 of the low-information cells in the
abstention arm **AND** the flag-cost ceiling holds **AND** the NI guard holds. All four must
hold; a verdict reports each leg with n + CI (bootstrap for the ratios, Wilson for the rates),
and the per-class table identifies which classes push each leg — reported, never decided at the
class level (n=1–2 per arm per class).

**The abstention analysis is the PRIMARY outcome — not exploratory** (the change from 2c,
per the accepted design): the decline decisions are the treatment, and the decision rule above
is its pre-registered evaluation. The confidence curve remains EXPLORATORY (2c §2 style —
no threshold is fixed; the verdict only asserts the confidence-free constraint).

**Pre-registered contingency:** if the pooled rule does not decide (a construction failure in
a defect-bearing class, or a CI straddle), the plan extends the grid under the **same** block
scheme + a documented seed extension (a third repetition per class block), re-running both
arms' new cells — the margin, capture floor, outcome metric, class definitions, and abstention
legs are **not** re-opened.

---

## 3. Coverage analysis — the classes × arms × repetitions

**Grid shape: 8 blocks (the design's exposure set, with two analytic merges) × 2 repetitions ×
2 arms = 28 cells** (14 per arm). **Merge note (registration-time, grounded in the pinned
confidence definition):** the design's "high-confidence wrong proposal" and "low-confidence
correct proposal" exposures are **analytic labels over the incorrect_rebuilt and correct
cells** — the constructions produce the confidences by design (incorrect_rebuilt: all tests
pass → confidence 1.0; correct: the failing boundary test → confidence 2/3), so no separate
constructions exist for them (§1 confidence probes). **Coverage per arm:** defect-bearing n =
9 (correct 2 + harmful_partial 2 + competing 2 + absent-defective 1 + unseen-family 2) ≥ the
2b-registered power threshold (n ≥ 6 defect-bearing); clean n = 5 (incorrect_rebuilt 2 +
irrelevant 2 + absent-clean 1). **Budget arithmetic:** 28 cells × $0.0039–$0.0164 ≈
**$0.11–$0.46** + the p0–p5 wrapper phases (the 2b/2c flash-orchestrator cost, ~$0.2) ≈
**$0.3–0.7 total, inside the $30 stop.**

**Seed app (shared, all classes):** the 2c seed app verbatim — a fresh disposable worktree
seeded with `calc.py` (`add`, `subtract`) and `test_calc.py` (`test_add`, `test_subtract`).

### Class constructions (all 2c-verbatim except the two rebuilds)

| class | construction | expected measured facts | expected proposal | outcome claim |
|---|---|---|---|---|
| **correct** (2c verbatim) | `classify(value)` in `calc.py`, deep nested tree (S3776 CRITICAL) + the `[10,20)` `>`-for-`>=` boundary defect; `test_classify` asserts the boundary incl. `classify(10.0)` | `new_sonar_critical_count=1`, `changed_symbol_count≥1`, risk measurable | **`rework` d3** | status_quo: one pass fixes → accepted (2c: 2/2). abstention: APPLY (no leg fires) → accepted. Both arms escape 0; the class is the NI-guard's apply-leg |
| **incorrect_rebuilt** (REBUILT — the 2c construction-failure fix) | `add(a,b)` body changed **behavior-preserving** (`return a+b` → `result = a+b; return result`); NEW module `widgets.py` with 19 trivial functions **each CALLING `add`** (the structural dependant edge the graph provably sees — the 2c lesson: impacted=0 broke the guarantee; here `add`'s dependant set provably contains the 19 widgets → `impacted_symbol_count ≥ 1`) and NO `test_widgets.py` | `changed_symbol_count=20`, `changed_symbols_with_tests_ratio=1/20=0.05`, `impacted_symbol_count ≥ 1` (**pre-verified in p1**), criticals 0, `risk = 0.19 + 0.02·min(1, impacted/10) ≥ 0.21` | **`verify` d2** (risk ∈ [0.2, 0.3)) | clean in both arms → accepted both; wrong-apply = the measured verify-pass delta (§1). The falsifiability: if p1/p2 facts yield risk < 0.2 (impacted still 0), the class is a construction failure — flagged, recorded (a SECOND construction failure refutes the design per §4) |
| **harmful_partial** (NEW — the design's "harmful proposal" exposure, constructible harm) | `classify(value)` with S3776 + **two boundary defects far apart** (`[10,20)` and `[80,90)` both `>`-for-`>=`), so ONE bounded rework pass plausibly fixes one and misses the other; `test_classify` asserts both | as competing (critical count 1 → `rework` d3; scope contains the changed symbols) | **`rework` d3** | both-fixed → accepted, no harm; one-fixed → **partial_rework** (2c's pinned one-of-two semantics): not accepted, harm = 1×E_x; zero-fixed → 2 escapes. The class measures the **ceiling of application-policy-only prevention**: the facts say rework (correct at the rule level) — abstention does NOT fire; a partial outcome is a legitimate outcome, not a construction failure |
| **irrelevant** (2c verbatim) | `product(values)` with `test_product` | ratio 0.5, impacted 4, criticals 0, risk 0.18 | **`continue` d0** | accepted both arms; **NOT flagged** by Option A (multi-term risk 0.18 ≠ the fingerprint) — the flag-cost leg's clean baseline |
| **competing** (2c verbatim) | two boundary defects in the same changed scope (`[10,20)` + `[20,30)`) | critical 1 → `rework` d3, scope contains both | **`rework` d3** | both-fixed → accepted (2c: 2/2 audited); one → partial_rework; the NI-guard's second apply-leg |
| **absent-clean** (2c verbatim, designed degraded) | clean helper in new module, seam run with sonar+lsp+graph unavailable → no risk term → **refusal** | risk absent | **refuse** | accepted both arms; the abstention arm records DECLINE (leg 2) → the flag-cost measurement on a clean cell (2c: refusal cost nothing — expected delta ≈ 0) |
| **absent-defective** (2c verbatim, designed degraded) | real wrong-op defect in new module, same degraded seam → refusal | risk absent | **refuse** | the defect escapes in BOTH arms (status_quo: pass-through refusal; abstention: DECLINE leg 2) — the **abstention-harm side**: 1 escaped defect × $0.046109/arm @11.47 in each arm. This is the class whose escape the rule TARGETS but, being a refusal-state, cannot prevent without new measurement (design's honest boundary) — the capture leg measures the decline RECORDED + routed to operator review, and the operator-review action in the pilot is flag-only (no fix) → escape stands |
| **unseen_family** (2c verbatim) | mutation/aliasing defect in `tally(scores)` (sorts in place); `test_tally` asserts the input unchanged; family verified NOT in {boundary-compare, S1244, S3776} by the p4 evaluator (2c's mandatory family-verification step) | ratio 1.0, criticals 0, tests term 0, `risk = 0.20·min(1, impacted/10)` — the **Option A fingerprint exactly** | `continue` (wrong) in status_quo | **status_quo**: escape (2c: 2/arm). **abstention**: DECLINE (leg 3 — risk == the impacted term alone, measured) → no apply pass, operator review. The capture claim: the decline fires; whether the escape stands (flag-only pilot) or the operator catches it is the review-phase outcome — the capture-rate leg counts the FIRED decline, the flag-cost leg counts its cost; the escape harm is reported per arm as the abstention-harm side of leg 3 |

**Evaluator's family-verification step (unchanged from 2c):** after scoring, the post-hoc
evaluator (a) confirms defect presence on the immutable final commit, (b) classifies the
family, (c) verifies it is NOT in the calibrated set — the unseen-family class's checkable
claim; a calibrated-family defect is a construction failure, flagged.

---

## 4. Randomization scheme

**Design:** block-randomized by **class** (8 blocks; the absent block ordered as its two
sub-variants). Within each block, exactly 50% status_quo / 50% abstention (2+2; absent: 1+1
per variant). Cell model, stimulus spec, and seed app are identical within each arm — the only
difference between arms is the application policy (status_quo: apply as proposed; abstention:
the §0 decision table).

**Committed seed (hex):** `617e6763fcd238dc93a59ba1f41e01ba5f281c4748ef3867dbebeeca344c7dfb`
(derived as `sha256("cap_adaptive_2d|blocked-by-stimulus|50-50|statusquo-vs-abstention|20260828")`
— an honest committed seed, not a hand-picked permutation).

**Reproducibility key (p5 must re-derive the table from this):**

```python
import random
random.seed("617e6763fcd238dc93a59ba1f41e01ba5f281c4748ef3867dbebeeca344c7dfb")
for cls in ("correct", "incorrect_rebuilt", "harmful_partial", "irrelevant",
            "competing", "absent", "unseen_family"):
    if cls == "absent":
        for variant in ("clean", "defective"):
            arms = ["status_quo", "abstention"]; random.shuffle(arms)
    else:
        arms = ["status_quo"] * 2 + ["abstention"] * 2
        random.shuffle(arms)
```

**The exact assignment table — pre-computed, canonical, committed here** (slot # = seeded
permutation position within the block; the execution order):

| cell_id | class | variant | arm | repetition | slot # |
|---|---|---|---|---|---|
| `cap2d_correct_status_quo_r1` | correct | — | status_quo | r1 | 1 |
| `cap2d_correct_status_quo_r2` | correct | — | status_quo | r2 | 2 |
| `cap2d_correct_abstention_r1` | correct | — | abstention | r1 | 3 |
| `cap2d_correct_abstention_r2` | correct | — | abstention | r2 | 4 |
| `cap2d_incorrect_rebuilt_abstention_r1` | incorrect_rebuilt | — | abstention | r1 | 1 |
| `cap2d_incorrect_rebuilt_abstention_r2` | incorrect_rebuilt | — | abstention | r2 | 2 |
| `cap2d_incorrect_rebuilt_status_quo_r1` | incorrect_rebuilt | — | status_quo | r1 | 3 |
| `cap2d_incorrect_rebuilt_status_quo_r2` | incorrect_rebuilt | — | status_quo | r2 | 4 |
| `cap2d_harmful_partial_abstention_r1` | harmful_partial | — | abstention | r1 | 1 |
| `cap2d_harmful_partial_status_quo_r1` | harmful_partial | — | status_quo | r1 | 2 |
| `cap2d_harmful_partial_abstention_r2` | harmful_partial | — | abstention | r2 | 3 |
| `cap2d_harmful_partial_status_quo_r2` | harmful_partial | — | status_quo | r2 | 4 |
| `cap2d_irrelevant_abstention_r1` | irrelevant | — | abstention | r1 | 1 |
| `cap2d_irrelevant_status_quo_r1` | irrelevant | — | status_quo | r1 | 2 |
| `cap2d_irrelevant_status_quo_r2` | irrelevant | — | status_quo | r2 | 3 |
| `cap2d_irrelevant_abstention_r2` | irrelevant | — | abstention | r2 | 4 |
| `cap2d_competing_status_quo_r1` | competing | — | status_quo | r1 | 1 |
| `cap2d_competing_abstention_r1` | competing | — | abstention | r1 | 2 |
| `cap2d_competing_status_quo_r2` | competing | — | status_quo | r2 | 3 |
| `cap2d_competing_abstention_r2` | competing | — | abstention | r2 | 4 |
| `cap2d_absent-clean_abstention_r1` | absent | clean | abstention | r1 | 1 |
| `cap2d_absent-clean_status_quo_r1` | absent | clean | status_quo | r1 | 2 |
| `cap2d_absent-defective_abstention_r1` | absent | defective | abstention | r1 | 1 |
| `cap2d_absent-defective_status_quo_r1` | absent | defective | status_quo | r1 | 2 |
| `cap2d_unseen_family_abstention_r1` | unseen_family | — | abstention | r1 | 1 |
| `cap2d_unseen_family_status_quo_r1` | unseen_family | — | status_quo | r1 | 2 |
| `cap2d_unseen_family_status_quo_r2` | unseen_family | — | status_quo | r2 | 3 |
| `cap2d_unseen_family_abstention_r2` | unseen_family | — | abstention | r2 | 4 |

Totals: **28 cells · 14 status_quo · 14 abstention · 9 defect-bearing per arm**. Arm labels
come from this committed seed + block scheme, never from the model's choice and never post-hoc.
**E1** (the p1 measurement cell, per the 2c p1 prompt "the correct-class adaptive arm first",
adapted: the FIRST abstention-arm cell in the correct block by slot order) =
**`cap2d_correct_abstention_r1`**; its facts pre-verify the incorrect_rebuilt construction's
impacted guarantee is checked in p1 too (the rebuild's pre-verification, §1). Every cell runs in
a fresh worktree with a unique `FINOPS_CELL_ID`; the proposal (or refusal) and the abstention
decision are recorded BEFORE the outcome; p2's execution manifest lists every cell of this
table and no others.

---

## 5. Analysis plan

**Inputs:** only immutable p1/p2 artifacts; join validated on `(cell_id, class, variant, arm,
repetition)` against §4's table. A cell scored under a different arm than its assignment is
**invalid**, not corrected. Output JSON:
`experiments/results/cap_adaptive_2d/cap_adaptive_2d_score_<ts>.json` (schema
`cap_adaptive_2d_score/v1`) + a validation result tracing every verdict number to a field.

**Per-arm estimates (with n + CI):**

| quantity | estimator | CI |
|---|---|---|
| cpvo_harm per arm (the primary) | `(Σ cost + Σ harm) / Σ accepted` over the arm's 14 cells, harm per §1 at E_x = 11.47 | bootstrap, 10,000 resamples of cells within the arm, stratified by class block; 95% |
| cpvo per arm (raw, harm-free) + success rate | 2c estimators verbatim | bootstrap / Wilson 95% |
| capture rate (abstention arm) | declined low-information cells / 3 (absent-defective + unseen-family×2) | reported with the exact count; per-class capture listed |
| flag cost (abstention arm) | Σ cost of the declined CLEAN cells (absent-clean + any flagged clean cell) − the same classes' status-quo costs | reported per cell |
| wrong-apply pass delta | `mean(incorrect_rebuilt cost) − mean(irrelevant cost)` per arm | reported with the two cell costs |
| per-class cpvo + success | same estimators over the class's cells (n=2 per arm per class) | reported descriptively, never decided |

**Decision rule (§1–§2):** all four legs (primary comparison, capture, flag-cost ceiling, NI
guard) computed from the above; the verdict is SUPPORT / REFUTE per the falsifiability contract
(design §4), with each leg's numbers and the per-class table.

**The confidence curve (EXPLORATORY, the 2c method verbatim):** bin the recorded confidences
into deciles; per decile value(apply) vs value(abstain); threshold curve over the observed
distribution; the verdict asserts the confidence-free constraint (no improving θ) — never fixes
a threshold.

**Expected-effect checks:** as 2c (the structural ceiling carried forward — rework passes were
not handed to a post-rework analyzer; recorded limitation, not a passed-or-failed claim).

**The operator-review accounting (pilot):** every DECLINE records the leg + the review routing;
the review phase (p4) processes the declined cells (the checkpoint/approval machinery — the
operator or the adversarial reviewer). The review's outcome per declined cell (caught vs
passed) is recorded; the pilot's claim is the DECLINE firing + its cost, not the review's
catch rate (flag-only by design — no production activation, design §6).

---

## 6. Authorization boundary (unchanged from the design, restated)

- The accepted design authorizes: this preregistration, the 2d campaign (cells + wrapper
  phases, ≤ $30, 4-wide p2 concurrency), and the operator-review routing of DECLINED cells
  (pilot, checkpoint-style).
- It does NOT: activate the abstention rule in any production path; change `control_route`,
  arm any actuation, or flip the verify gate; modify the treatment (verify_proposal /
  RISK_WEIGHTS / VERIFY_RISK_THRESHOLD / severity filter — code-unchanged, hard-rule 10); or
  re-open the 2c verdict.
- A SUPPORT verdict authorizes the NEXT conversation — wiring DECLINE into the live
  application path — never by itself.
- **Parallel vehicles (operator's plan, recorded):** the 2d campaign owns the deepseek-v4-pro
  cell envelope. In parallel: the cross-models campaign (anthropic/openai envelopes — separate
  rate limits) and the mechanical workstreams (artifact governance, docs restructure) run
  concurrently; the data chain (spec index / manifest / data.js / deploys) stays
  single-writer — only one campaign regenerates it at a time. No campaign edits
  `workflow_runner.py` / `experiment_spec.py` while 2d's cells are in flight.

---

## 7. Confidence-recording requirement (restated for p2's cell records)

- Every cell's proposal record MUST carry the measured confidence field (the [H] per-attempt
  execution-confidence of the analyzed implement attempt, recorded at proposal-emission time
  BEFORE the outcome — 2c §7 verbatim). A record without the field is flagged, never imputed;
  `None` is recorded as `null` and excluded from the decile bins (count reported). The absent
  cells carry no proposal (the seam refused) — reported, count 2 per arm, never imputed.

---

## 8. Concurrency and execution plan (the operator's plan, pinned)

- **p2 grid at 4-wide** (ThreadPoolExecutor `max_workers=4` — the sweep precedent), 28 cells →
  7 batches of 4; cells are worktree-isolated (`FINOPS_CELL_ID` per cell), score join is
  order-independent (§4).
- **Order of execution:** block order per the slot numbering; the p1 measurement cell
  (`cap2d_correct_abstention_r1`) runs first and pre-verifies the incorrect_rebuilt impacted
  guarantee (§1) before the grid's incorrect_rebuilt block runs.
- **Running concurrently (not on the deepseek envelope):** cross-models campaign on
  anthropic/openai; artifact governance + docs restructure workstreams (no model / flash
  only). The data chain is single-writer; the wrapper phases (p0, p1, p3, p4, p5) are
  sequential flash sessions and do not overlap the cross-models data chain.
- **Watchdogs:** the 2c cell timeouts + the runner's phase watchdogs apply unchanged; a cell
  exceeding the SLA guard is stopped and recorded in its denominator.

---

## Guard (provenance of every number)

- **VERIFY_RISK_THRESHOLD 0.2, action tree, `_risk_depth`, refuse contract** =
  `verify_proposal.py` (lines 61, 143–150, 169–255) — 2c §0 pins, unchanged.
- **risk formula weights, renormalization, severity filter, ratio deferral, TESTED_BY** =
  `code_change_facts.py` + `workflow_runner.py` + `language.py` — 2c §0 pins, unchanged.
- **$0.004021, E_x 11.4671/12.5134, loss $0.046109/$0.112588** = escalation score JSON
  `base_downstream_defect_cost_usd`, `per_model[].E_x`, `loss_table`.
- **2c ratio 0.6537, per-class outcomes, confidence set, per-cell cost range** = 2c score JSON
  `decision_rule`/`per_class`/`abstention_analysis`/`per_cell[].cost_usd`.
- **Option A fingerprint (leg 3)** = the accepted design
  (`docs/designs/current/cap_adaptive_2d_design.md`, §2 resolved decision) — risk < 0.2, zero
  severity terms, zero tests term, risk == the impacted term exactly.
- **incorrect_rebuilt risk 0.19 + 0.02·min(10, impacted) ≥ 0.21** = the §0 formula applied to
  the §3 construction's expected facts (ratio 1/20, the widgets-call-add dependant edge).
- **Defect-bearing n (9/arm)** = the §3 coverage construction (correct 2 + harmful 2 +
  competing 2 + absent-defective 1 + unseen-family 2).
- **Seed + assignment table** = concrete hex `617e6763…` with the reproducibility key and the
  full 28-row table committed in §4 — no placeholders, no run-time randomization.
- **Budget ≈ $0.3–0.7 vs $30 stop** = the 2c measured per-cell range × 28 cells + the 2b/2c
  wrapper-phase precedent; the $30 stop from the campaign spec `stop.budget_usd`.
- **Concurrency 4-wide** = `sweep_silent_mode.py` `max_workers=4` (the tested precedent).

## LOG

Pre-registration complete and internally consistent: the abstention rule pinned in the
compiler's vocabulary with the three decline legs (stale / unmeasurable / the accepted Option A
fingerprint) and the shadow-evaluated p2-harness mechanism (treatment code-unchanged); the
primary outcome (harm-inclusive cpvo comparison, abstention vs within-campaign status-quo) +
the three guard rails (capture ≥ 2/3 of the low-information cells, flag-cost ceiling, the
reused NI margin); the 8-block grid with the two rebuilds specified (incorrect_rebuilt with
the widgets-call-add impacted guarantee + the p1 pre-verification; harmful_partial with the
far-apart two-defect partial-rework exposure) and the analytic merge of the confidence probes
into the correct/incorrect_rebuilt cells; the committed seed `617e6763…` + full 28-cell
assignment table (14/arm, 9 defect-bearing/arm); the analysis plan with the abstention rule as
PRIMARY; the authorization boundary (pilot flag-only, no activation) + the parallel-vehicles
plan (cross-models on other envelopes, mechanical workstreams concurrent, data chain
single-writer); the confidence-recording requirement restated; the 4-wide execution plan.
**PASS — committing before any cell runs.**
