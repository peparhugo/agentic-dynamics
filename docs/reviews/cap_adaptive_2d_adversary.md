---
status: accepted
---

# cap_adaptive_2d — adversarial review (p5)

**Campaign:** `cap_adaptive_2d` (`cap_adaptive_2d@0.1`, spec SHA256
`1258280d44f608c7fcccf91ef514cc5a39994a9fd352852d96fb35c919f2ea0c`) · **Verdict under review:**
`docs/designs/current/cap_adaptive_2d.md` (committed `02abd464988aee8ddbe9ffd04916f5658008114b`,
SHA256 `c21bc97c5997adee…`). **Pre-registration:**
`docs/designs/current/cap_adaptive_2d_preregistration.md` (committed `9dc0b4a638810af28ccf82b6beeb4af6b596d467`;
current file SHA256 `98da62a31f3817e6…`, spec pinned in header at `044f7c23c`).
**Score:** `experiments/results/cap_adaptive_2d/cap_adaptive_2d_score_20260828T043139Z.json`
(SHA256 `9c6abb55a1261cec1826e55519411744e6867c5246ba6e1488be42b1db6400ce`) + the validation JSON
(`cap_adaptive_2d_validation_20260828T043139Z.json`, SHA256
`ad8a0b2f34839ff260dc8924d1147bff4bab8f081d8d07287bc1252722eb3a8b`). **Execution:**
`p1_execution_manifest.json` (`b1be2cb3…`), `p2_execution_manifest.json` (`9fab82c2…`),
`p1_incorrect_rebuilt_probe.json` (`567839d3…`), 28 per-cell records
(`experiments/results/cap_adaptive_2d/cells/`, schema `cap_adaptive_2d_cell/v1`), 24 durable
proposals (`experiments/results/proposals/`). **Attacker role:** adversarial verifier, attack in
the pre-registered order (spec p5 prompt); a deviation from the pre-registered plan is a FAILED
finding, not a limitation.

## Attack 1 — Pre-registration adherence

**Attack:** does the committed pre-registration (9dc0b4a63) match what was analyzed? Any redefined
margin, reseeded assignment, dropped cell, post-hoc re-labelled class, or post-hoc leg widening is
a FAILED finding.

**Evidence:**
- **Commit order** (provable by `git log`): `9dc0b4a63` p0 preregistration → `24e5864c2` campaign
  spec → `044f7c23c` p0_pin (spec SHA pinned into the header) → `e2bb2f94b` p1/p2 machinery →
  `72dc47f94` p1 (E1 + probe, **02:23**) → `ada584e2b`/`9f12ab9ad` p2 (grid, **02:10–06:26**) →
  `e0c41fb52` p3 (score, **06:33**) → `02abd4649` p4 (verdict, **06:34**). p0 precedes every cell:
  the first p1 cell record was written `2026-08-28T00:13:14Z` (UTC), the p2 grid cells
  `02:10–06:26` (+0200), both after p0's `2026-08-27` commit. The registration rule held.
- **The pin is the only edit.** `git diff 9dc0b4a63 HEAD -- …preregistration.md` shows exactly two
  changes: (1) the header line "Campaign: cap_adaptive_2d" now carries the spec SHA256
  `1258280d44f608c7fcccf91ef514cc5a39994a9fd352852d96fb35c919f2ea0c` (`workflows/repository/cap_adaptive_2d.yaml`,
  `cap_adaptive_2d@0.1`); (2) a `LOG — p0_pin_spec` block appended at the end documenting the
  verification. No section of §0–§8 was altered. The pinned SHA equals the committed file:
  `git rev-parse HEAD:workflows/repository/cap_adaptive_2d.yaml` → blob `4ab83398…`, `sha256sum`
  → `1258280d…` — re-verified in this review (the current tree is `02abd4649`, byte-identical
  spec).
- **Seed reproduces the 28-cell table exactly.** This review re-ran the §4 reproducibility key
  with `random.seed("617e6763fcd238dc93a59ba1f41e01ba5f281c4748ef3867dbebeeca344c7dfb")`
  (verified `sha256("cap_adaptive_2d|blocked-by-stimulus|50-50|statusquo-vs-abstention|20260828")`
  == the committed seed): 28 cells, 14 status_quo / 14 abstention, **9 defect-bearing per arm**,
  5 clean per arm, and **zero mismatches** across (cell_id, class, variant, arm, repetition,
  slot) vs the committed §4 table.
- **E1 = `cap2d_correct_abstention_r1`** (§4 correct block, slot 3) — confirmed in the p1
  manifest (`e1_cell`) and the cell record (`cap2d_correct_abstention_r1.json`: slot 3, arm
  abstention, correct class).
- **Option A leg-3 fingerprint pinned** (§0 table): risk < 0.2, severity terms zero, tests term
  zero, risk == 0.20·min(1, impacted/10) EXACTLY. The harness implements it
  (`run_cap_2d_grid.py` `evaluate_abstention`, lines 233–250): `severity_zero = sonar==0 and
  lsp==0`, `tests_zero = ratio is None or ratio >= 1.0`, `expected = round(0.20*min(1,
  impacted/10), 4)`, `abs(risk - expected) < 1e-9`. No post-hoc widening.
- **Four decision-rule legs pinned** (§1–§2): (a) `cpvo_harm(abstention) < cpvo_harm(status_quo)`
  at E_x=11.47; (b) capture ≥ 2/3 of the low-information cells (absent-defective + unseen_family
  ×2); (c) flag cost < saved escape harm; (d) NI guard (`cpvo_ab ≤ 1.10 × cpvo_sq` AND
  `success_ab ≥ success_sq − 5pts`). All four must hold for SUPPORT.
- **$30 stop confirmed** in the spec (`stop.budget_usd: 30.0`).
- **Join validation:** `score.join_validation` — `valid=true`, `n_invalid=0`, `n_table_rows=28`,
  `n_cells=28`; every scored (cell_id, class, variant, arm, repetition) matches the §4 table.
- **Harm constants re-derived** in this review from `cap_escalation_measurement_score`:
  `base_downstream_defect_cost_usd = 0.004021`, E_x 11.4671 (sol) / 12.5134 (sonnet), loss at
  E_x=11.4671 = $0.046109, at E_x=28 = $0.112588 — matching the pre-registration's cited values
  and the score's `harm_table`.

**Result: PASS.** No deviation. The pre-registration is the analyzed plan; commit order proves it
preceded data collection; the only post-p0 edit is the pinned SHA + its verification log.

## Attack 2 — Class integrity

**Attack (per the p5 prompt):** did the incorrect_rebuilt cells really make the verifier propose
`verify` on a CLEAN change (proposal + evaluator + p1 probe)? Is the unseen-family defect really
outside the calibrated families? Did the harmful_partial cells' outcome really follow one-of-two?

**2a. incorrect_rebuilt — SECOND construction failure (FAILED finding F1).**
- The rebuild's guarantee was `impacted_symbol_count ≥ 1` (the widgets-call-add dependant edge) →
  `risk = 0.19 + 0.02·min(1, impacted/10) ≥ 0.21` → **`verify` d2**. All 4 cells + the p1 probe
  measured **`impacted_symbol_count = 0`** under the pinned analyzer → `risk = 0.19 < 0.2` →
  all 4 emitted **`continue`**, not `verify` (per-cell `flags:
  ["construction-failure: expected proposal verify, got continue"]`, 4/4; `score.flags.
  construction_failures`, 4 rows). The p1 probe
  (`p1_incorrect_rebuilt_probe.json`) is explicit: `design_refuted: true`, root cause =
  the 19 widgets are THEMSELVES changed symbols (added symbols → seeds), so the analyzer's
  `_neighborhood` excludes them; the only non-seed dependants (test_add/test_subtract/subtract)
  are unreachable within the analyzer's hard `timeout_ms=300` BFS on a 20-seed expansion (a 10s
  re-run returns 3 non-seed dependants — the edge EXISTS; the guarantee fails on the analyzer's
  deadline, not the graph). **A second impacted=0 refutes the design per pre-registration §4 /
  design §4** — this is the decisive FAILED finding. The wrong-apply leg (the `verify` pass on a
  clean change) is **unverifiable**: no verify pass was ever applied, so `wrong_apply.total_usd_
  measured = $0` is a non-measurement, correctly reported as such (`harm_table.wrong_apply`),
  not as a passed-or-failed claim.
- Evaluator on the immutable final commits (re-verified in this review on
  `/tmp/cap2d_incorrect_rebuilt_status_quo_r1`, final rev `e6603608a…`, worktree HEAD matches):
  clean — `add(1,2)==3`, `widget_19(1)==20`; `defect_present_on_final_commit=false`. The class is
  clean as designed; only the false-positive-verify exposure failed to instantiate.

**2b. unseen_family — defect real, fingerprint NEVER instantiated (FAILED finding F2).**
- Evaluator + re-verified here: `tally` mutates its input (`s.sort(reverse=True); return s`).
  `import calc; s=[3,1,2]; calc.tally(s); assert s==[3,1,2]` FAILS on the immutable final commit
  (`cap2d_unseen_family_abstention_r1`, rev `62cbe81ab…`, worktree HEAD matches) — defect
  present. Family = mutation/aliasing — **NOT boundary-compare, NOT S1244, NOT S3776** — the
  class's checkable claim holds.
- **BUT** the measured facts do NOT match the pre-registered Option A fingerprint: the §3 table
  expected `ratio 1.0, tests term 0, risk = 0.20·min(1, impacted/10) exactly`. The cells measured
  `changed_symbols_with_tests_ratio = 0.5`, `impacted = 4`, `risk = 0.18` — a **multi-term** risk
  (tests term 0.10 + impacted term 0.08), the same profile as the `irrelevant` class. So leg 3
  **never fired** and the unseen-family escapes were not captured. The pre-registration's §3
  expected-facts column for unseen_family did not match the machinery (this was ALREADY true of
  the 2c cells); the class the design's capture claim depended on did not instantiate its trigger
  state. The capture leg is **unmeasured → failed** (`leg_b_capture.capture_rate = 1/3 < 2/3`).
- This is a pre-registered-expectation mismatch, recorded (not re-labelled, not re-run): the cells
  are still unseen_family cells with real escaped defects; the abstraction policy's leg-3 trigger
  just never fired on them.

**2c. harmful_partial — one-of-two held (PASS).**
- `cap2d_harmful_partial_status_quo_r2` (re-verified on its immutable final commit, rev
  `088f0b501…`, worktree HEAD matches): the [80,90) boundary still uses `>` not `>=` →
  `classify(80.0) == classify(85.0)` fails → defect present, one-of-two semantics
  (`defect_note: "family: boundary-compare x1 ([80,90) inverted boundary) present — one-of-two
  (partial_rework exposure)"`), `accepted=false`, 1 escaped. The [10,20) boundary was fixed — the
  one-bounded-pass exposure worked as designed. `test_executed_success=false` (independent
  pytest). Both the status_quo r2 (partial) and the other three cells' outcomes are legitimate
  one-of-two outcomes, not construction failures.

**2d. Other classes (PASS):** correct (rework fixed the boundary; `classify(10.0)` band-check
passes — label-agnostic), competing (both defects escaped in r2 of both arms → 2 escapes, the
one-of-two semantics), irrelevant (clean, `continue`, accepted), absent-clean (refusal,
value-preserving), absent-defective (refusal → wrong-op defect escaped — the designed degraded
escape).

**Result: FAILED (two construction failures).** F1 (incorrect_rebuilt: impacted=0, second
failure, wrong-apply unverifiable) and F2 (unseen_family: fingerprint never instantiated →
capture leg unmeasured → leg B fails). Both are the design's own falsifiability contract firing;
neither is a re-labelling or a dropped cell.

## Attack 3 — Arm integrity

**Attack:** did status_quo apply exactly per proposal (rework = ONE bounded pass, verify = one
pass, continue = null)? Did abstention DECLINEs fire only on the pinned legs and SKIP the apply
(provable in the commit trails)? Did any cell apply under a different policy than its assignment?

**Evidence:**
- **Re-verified per-cell** (this review, programmatic sweep over all 28 cell records):
  - status_quo cells: `applied_or_null == "applied"` iff proposal action ∈ {rework, verify} with a
    `[workflow] rework` commit recorded (e.g. `cap2d_correct_status_quo_r1` → rework commit
    present, 1 pass), else `"null"` (continue/refusal). **No status_quo cell deviated.**
  - abstention cells: `applied_or_null == "declined"` for the 2 leg-2 DECLINEs (absent-clean,
    absent-defective — the apply pass is provably skipped; `proof: abstention-decline:leg-2`),
    `"applied"`/`"null"` exactly as the proposal tree for the APPLY/APPLY-NULL cells. **No cell
    applied under a different policy than its assignment** (sweep result: 0 failures).
- **The abstention shadow decision is evaluated for EVERY cell (both arms)** — per §0, the p2
  harness records it on status_quo cells too (e.g. `cap2d_competing_status_quo_r2` records
  abstention_decision APPLY_NULL but the status_quo arm APPLIED the rework as proposed). This is
  shadow evaluation, not a policy switch — the recorded decision on status_quo cells is
  informational, and the application proof shows the status_quo policy was followed. The score's
  `per_cell[].abstention_decision` mirrors this.
- **Decline legs in {1,2,3} only, on the pinned states:** all DECLINE records are leg 2 on
  risk-absent (refuse-state) cells (2 cells); leg 1 (stale analysis) never fired (all
  `analysis_revision_matches=true`); leg 3 (Option A fingerprint) never fired (F2). No
  out-of-table leg, no leg on an APPLY/APPLY-NULL state.
- **No runner wiring:** the abstention rule lives in the p2 harness
  (`scripts/run_cap_2d_grid.py` `evaluate_abstention`), never in the treatment. The only
  `scripts/run_workflow.py` change in the machinery commit is the `FINOPS_SKIP_SPEC_INDEX=1`
  guard (a 4-wide index-writer race guard), not the abstention rule. `verify_proposal.py`,
  `_risk_depth`, `VERIFY_RISK_THRESHOLD`, `RISK_WEIGHTS` are untouched (2c hard-rule 10 restated).

**Result: PASS.** Arms behaved exactly as assigned; DECLINEs were leg-faithful and provably
skipped the apply pass; the treatment is code-unchanged.

## Attack 4 — The abstention rule

**Attack:** shadow-evaluated (no runner wiring)? Option A fingerprint applied exactly (no post-hoc
leg widening)? Confidence never used?

- **Shadow-only:** verified above — `evaluate_abstention` is harness-side; zero call sites in the
  runner/treatment.
- **Fingerprint exact:** the code's `expected = round(0.20*min(1, impacted/10), 4)` with
  `abs(risk - expected) < 1e-9`, `severity_zero`, `tests_zero` matches the pinned §0 table
  verbatim; the APPLY / APPLY-NULL / DECLINE ordering (leg 2 → leg 1 → APPLY → leg 3 → APPLY-NULL)
  is the pinned table's order (risk-absent wins over revision-mismatch, per §3). No post-hoc leg
  widening: this review found zero declines outside the pinned states, and zero
  APPLY/APPLY-NULL cells that should have been declines under the pinned table (the irrelevant
  cells' multi-term risk 0.18 is explicitly NOT the fingerprint, and the harness correctly
  left them APPLY-NULL).
- **Confidence-free:** `evaluate_abstention` consumes only the six facts of `requires_facts`
  (analysis_revision_matches, code_change_risk, new_sonar_critical_count, new_lsp_error_count,
  impacted_symbol_count, changed_symbols_with_tests_ratio); confidence is not read. The confidence
  curve (`score.abstention_analysis`) is labeled EXPLORATORY, `improving_threshold_exists=false`
  — the 2c constraint re-check holds (no θ on confidence improves the rule).

**Result: PASS.**

## Attack 5 — The harm model

**Attack:** wrong-apply measured within-campaign? wrong-continue E_x cited + sensitivity? n=1
per-model limitation stated?

- **wrong-apply: $0 measured, UNVERIFIABLE** (F1). The constructible false-positive (verify pass
  on a clean change) never instantiated; the within-campaign pass delta cannot be measured. The
  score reports `total_usd_measured = 0` with the construction-failure note — an honest
  non-measurement, never a passed claim. Pre-registration §1's "wrong-apply measured
  within-campaign" precondition is unmet → the leg is unmeasurable.
- **wrong-continue: E_x-scaled.** Re-derived here from the escalation score: 11 escaped defects
  × $0.046109 @11.47 = **$0.507199**; × $0.112588 @28 = **$1.238468** (status_quo 6 escapes →
  $0.276654; abstention 5 escapes → $0.230545). Sensitivity at 28 reported. The 1-defect delta is
  the harmful_partial r2 model-noise cell (both arms APPLY the rework; not a decline).
- **n=1 per model stated:** E_x 11.4671 (sol) / 12.5134 (sonnet), n=1 each — recorded in the
  verdict + score.

**Result: PASS** (with the F1 unverifiability recorded as the campaign's design-refuting gap).

## Attack 6 — The four decision-rule legs

**Attack:** each leg computed from recorded fields, nothing imputed?

- **leg_a_primary** — cpvo_harm @11.47: abstention $0.038908 < status_quo $0.048313. Re-computed
  in this review from `per_cell` (cost + harm_11 / accepted): abstention (0.158536 + 0.230545)/10
  = 0.038908; status_quo (0.158165 + 0.276654)/9 = 0.048313. **Holds numerically** — but the
  score's caveat is correct: the only DECLINEs were leg-2 absent cells whose escapes stand in both
  arms (flag-only pilot), and leg 3 never fired; the delta is the harmful_partial r2 outcome on a
  rework pass both arms apply → **not a treatment effect**.
- **leg_b_capture** — 1/3 < 2/3: declined low-information = {absent-defective} only (leg 2);
  unseen_family ×2 not declined (F2). **FAILS** (this is the decision-rule leg that decides).
- **leg_c_flag_cost** — flag cost = −$0.000183 (declined absent-clean $0.006965 vs status_quo
  $0.007148); saved escape harm = $0 (no decline prevented an escape). Holds **vacuously**.
- **leg_d_ni_guard** — cpvo ratio 0.902 ≤ 1.10; success gap −0.0714 ≤ 0.05. **Holds.**
- **all_four_hold = FALSE** — leg B fails outright; leg A is not a treatment effect. Re-computed
  independently in this review; every number traced to `score.per_cell`/`per_arm`/
  `abstention_decision_rule` fields. Nothing imputed.

**Result: FAILED (the decision-rule verdict).** REFUTE is the pre-registered outcome — all four
must hold for SUPPORT.

## Attack 7 — The usual suite

- **Baselines/denominators:** 28/28 cells scored, `n_dropped=0`, `n_not_run=0`; absent-defective
  is a designed degraded cell, flagged, never dropped (`score.denominators.note`). All cells
  `status=ok` (no timeout/SLA stops).
- **Hashes:** score `9c6abb55…`, validation `ad8a0b2f…`, p2 manifest `9fab82c2…`, p1 manifest
  `b1be2cb3…`, probe `567839d3…` — re-computed and all match the verdict's provenance table.
  Proposal artifacts (24) sha256-verified against the per-cell `proposal.artifact_sha256`
  (0 mismatches); cell record ↔ worktree final-revision matches confirmed (4 spot-checked).
- **Credentials:** `git grep` for keys/secrets/passwords over the campaign results + the two
  campaign scripts → no matches.
- **Budget/SLA:** total cell cost $0.316701 vs the $30 stop; all 28 within the 2× FORECAST guard
  ($0.02604); Σ cost ≈ $0.3–0.7, consistent with the pre-registration's budget arithmetic.
- **Limitation found (L1):** the p2 manifest's per-cell `artifact_sha256` is a **stub** — all 28
  rows carry the SAME value (the SHA of `cap2d_unseen_family_status_quo_r2.json`), so the manifest
  does NOT independently pin each cell file. **Mitigations:** the 28 cell files themselves are
  committed (distinct SHAs), each cell record internally pins its proposal artifact_sha256
  (verified 24/24), and the score reads the cell files directly (not the manifest column) — the
  stub does not affect any scored number. Recorded as an accepted limitation (residual risk: a
  reader relying on that manifest column alone could not verify cell-file integrity; git + the
  internal proposal hashes cover it). The verdict is unaffected.
- **Limitation found (L2):** the confidence curve's observed distribution is only {0.6667, 1.0}
  (the 2c two-value resolution), n=24 proposals (4 absent cells carry no proposal → reported,
  count 2/arm, never imputed). This is a descriptive constraint, recorded in the score
  (`cells_without_confidence`, `n_without_confidence=4`).
- **New-attack finding (F3 — recorded, not a decision change):** the harmful_partial r2
  model-noise asymmetry (abstention accepted where status_quo did not) is the source of leg A's
  numeric hold. It is correctly attributed as noise (both arms APPLY the same rework policy;
  `run_cap_2d_grid.py` `_rework_prompt` is identical across arms), so it does not falsify the
  verdict — but it is the honest reason leg A cannot be read as an abstention effect.

**Result: PASS (with L1/L2/F3 recorded).**

## Finding table

| # | attack | result | finding |
|---|---|---|---|
| F1 | incorrect_rebuilt second construction failure (impacted=0 → continue, not verify) | **FAILED** | refutes the design per prereg §4 / design §4; wrong-apply unverifiable; recorded (4 cells + p1 probe), never re-labelled |
| F2 | unseen_family fingerprint never instantiated (ratio 0.5 / risk 0.18 multi-term) | **FAILED** | leg-3 capture unmeasured → leg B fails (1/3 < 2/3); recorded, never re-run |
| A1 | pre-registration adherence | PASS | seed re-derives the 28-cell table (0 mismatches), pin-only edit, commit order p0→p1→p2→p3→p4 |
| A2 | class integrity (other classes) | PASS | harmful_partial one-of-two, competing escapes, correct rework, absent variants, unseen-family family claim all verified on immutable commits |
| A3 | arm integrity | PASS | status_quo applied per proposal; abstention DECLINEs leg-faithful + skipped apply; no cross-policy cell |
| A4 | abstention rule | PASS | shadow-only, no runner wiring, fingerprint exact, confidence-free |
| A5 | harm model | PASS | wrong-continue re-derived; wrong-apply honestly $0/unverifiable; n=1 stated |
| A6 | four decision-rule legs | **FAILED (decision)** | all_four_hold=FALSE; leg B fails; leg A not a treatment effect; REFUTE is correct |
| A7 | usual suite | PASS | hashes, denominators, credentials, budget all clean; L1 manifest-stub + L2 confidence-resolution limitations recorded |

**Verdict under review: REFUTE — CONFIRMED.** The campaign's own falsifiability contract fires:
leg B fails (capture 1/3 < 2/3 — the unseen-family class never instantiated the leg-3 fingerprint
that the capture claim depended on), leg A's numeric hold is not a treatment effect, and the
incorrect_rebuilt class failed to instantiate `verify` a SECOND time (impacted=0 under the pinned
analyzer), making the wrong-apply leg unverifiable. Two construction failures + a failed capture
leg mean the campaign cannot distinguish "abstention doesn't help" from "the exposures couldn't be
built to test it." The adaptive controller did not demonstrate it knows when not to intervene.

## LOG

Adversarial pass completed. Attacks A1–A7 run in the pre-registered order; F1 and F2 are FAILED
findings (both construction failures, both already flagged/recorded in the p1/p2/p3 artifacts);
A6 confirms the REFUTE decision; L1/L2/F3 recorded as accepted limitations. Every verdict number
re-computed from the immutable artifacts (seed table, per-cell costs/harms, harm constants,
proposal hashes, worktree final-revision matches). **PASS — committed.**
