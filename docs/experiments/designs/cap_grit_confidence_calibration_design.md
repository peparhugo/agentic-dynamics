---
status: accepted
---

# cap_grit_calibration — design: the retry-threshold × verify-gate calibration (does a retry on a failing attempt pay, and where does it stop?)

**PARKING NOTE (2026-08-30 — the operator's stand-back review).** This campaign is **PARKED**:
the full 84-cell strength-response curve is over-built for the operational retry decision — the
retry decision is a **lookup, not a response curve**. Superseded by the observational replacement
`retry_observational_analysis` (spec SHA256
`b07d86d7cac1a5cbab0db5b67e35085a02f5ee58d628b8ef0fccfdf105b12b9b`), which computes the
retry-worthiness lookup from the corpus's existing fail → retry → outcome chains (no new cells,
no grid, confounds disclosed). The preregistration grid (§3) and its 84 cells are **not run**.

**Status: PROPOSED — a preregistration-style design doc, not a preregistration.** Nothing below
commits a cell, a seed, or a number into execution. The operator reviews this document; the
next artifact (if accepted) is the preregistration, which fixes every number (§3) before any
cell runs, per the 2b/2c pattern.

**The design question (the HANDOFF §3.2 queue item, engaged with the 2c/2d abstention
verdicts):** the review's list (HANDOFF §3.2, citing the external review) asks for "full
strength-response curves, model×strength interaction, calibrated confidence vs independent
success, policy thresholds selected on training data + evaluated on held-out cells." The 2c
verdict says **confidence must NOT gate the verifier's decline decision** (no θ improves value;
the signal is inverse to where adaptive adds value — `cap_adaptive_2c.md` §3/§5). The 2d verdict
REFUTES the informational-abstention rule as built (capture 1/3; leg-3 fingerprint never
instantiated; second incorrect_rebuilt construction failure — `cap_adaptive_2d.md`), and the 2e
campaign (running) reconstructs the leg-3 capture only. The grit grid (E4) measured a
**strength-response pilot** with one live retry. **This design separates the two decisions the
queue item names — retry-threshold (grit) and verify-gate (abstention) — and proposes the
calibration campaign that engages BOTH without conflating them.**

**Scope guard:** this document touches nothing. No cells, no code changes, no payload writes,
no edits to `workflows/`, `src/`, or the running machine. The 2e campaign (`cap_adaptive_2e`,
in flight) owns the deepseek cell envelope until it completes; this design is the **successor**
campaign on that envelope (§4).

---

## 1. The measured state — what exists, what is missing

### 1.1 The grit grid (E4) — `cap_grit_strength_grid`, completed

Campaign: `experiments/definitions/cap_grit_strength_grid.yaml` (`cap_grit_strength_grid@0.1`),
executed by `scripts/run_cap_grit_grid.py` (x2) + `scripts/measure_cap_grit_grid.py` (x3),
run plan `docs/experiments/designs/cap_grit_grid_runplan.md` (accepted). Measured outputs:
`experiments/results/cap_grit_grid_ledger.json` + `experiments/results/cap_grit_grid_metrics.json`
(schema `cap_grit_grid_metrics/v1`) + `experiments/results/cap_grit_grid_writeup.md`. One story
(`task_manager_api`, 5 sessions/cell), one model (`anthropic/claude-sonnet-5` via `claude_cli`),
8 cells = `condition_strength {clean, bad_seed_low, bad_seed_mid, bad_seed_high} × policy_arm
{baseline, grit_retry}`, sequential.

| measured fact | value | artifact field |
|---|---|---|
| verified success rate per strength, G(s) = P(test_executed_success \| s) | {0.0: **0.5**, 0.2: 1.0, 0.5: 1.0, 0.8: 0.6667} — n=1–3 attempts per strength | `cap_grit_grid_metrics.json` → `grit.produces.grit` |
| retention R(s) = G(s)/G(0) | {0.0: 1.0, 0.2: 2.0, 0.5: 2.0, 0.8: 1.3333}; `grit_auc` = **1.4** (≥1 because G(0)=0.5 — the clean×baseline cell failed genuinely: `limiter.reset()` → `Connection closed by server`, root-caused in runplan §10 F5) | `grit.produces.retention` / `grit.produces.grit_auc` |
| recovery_premium = C(successful_perturbed)/C(successful_baseline) | **1.1277** — the only genuine cross-strength signal in the pilot | `grit.produces.recovery_premium` |
| retries fired / eligible | **1/1** — the ONLY retry in the grid: `bad_seed_high × grit_retry` (a1 $3.6330, `test_executed_success=false` → a2 $3.1866, `true`) | `cap_grit_grid_ledger.json` → `cells[7].attempts` (two rows, `retry_reason="first_attempt_test_failure"`, `parent_attempt_id` linkage) |
| realized retry cell cost | $6.8195 vs baseline $3.0694 at the same strength — cell cost **2.2×**; per-cell cpvo regret **+$3.7501** (baseline better) | `ledger.cells[].realized_cost`; `metrics.arm_comparison.stratified[0]` (`condition_strength=bad_seed_high`) |
| stratified arm regret (baseline vs grit_retry cpvo) | low −$0.1841 (grit_retry), mid +$0.2618 (baseline), high +$3.7501 (baseline), clean unmeasured (baseline verified 0) | `metrics.arm_comparison.stratified` |
| rework axis | **$0.00 on all 9 attempts** — constant zero (runplan §10 F6: no continuation/subagent spend; the `rework_cost_report` field is dead in this grid) | `metrics.rework_cost_report[]` + ledger attempt rows |
| coverage + fidelity | cost 9/9 (1.0), test-verification 9/9 (1.0); retry_triggered_rate 1.0, **0 violations** | `metrics.coverage`; `metrics.retry_policy_fidelity` |
| realized cost | **$31.2733 vs the $10.00 ceiling — 3.1× overrun** (sonnet-5 story attempts measured $3.07–4.13 each vs the $0.30–0.60 flash-scaled estimate; "the next grid must re-baseline per-story cost empirically before committing a budget" — runplan §10) | `ledger.run_status.realized_total_cost_usd` + `budget_overrun` |

**What the E4 grid measured:** the strength axis is mechanically real (verified `inject_bug`
artifacts s=0.2/0.8, `mut_3caacc977303246d` single-hunk / `mut_1957f3238ebc0f5c` 3-hunk; mid =
standard on-disk `bad` variant at `CONDITION_STRENGTH=0.5` — runplan §3 F1–F4 + §10 x5 attack 4),
retry policy fidelity is operational, and the retry mechanism converts failure→success at cost.
**What it could not measure:** any retry-threshold response — exactly one retry fired, so the
retry posterior P(success | failed attempt, s) has **n=1**; per-strength G(s) has n=1–3 (no
CIs); and the model axis is sonnet-5 only (no model×strength interaction).

### 1.2 The abstention verdicts (2c / 2d / 2e) — the confidence-null and the informational boundary

2c score: `experiments/results/cap_adaptive_2c/cap_adaptive_2c_score_20260827T180241Z.json`
(sha256 `076751e4…`), `abstention_analysis` (EXPLORATORY, pre-registration §2/§5):

| measured fact | value | field |
|---|---|---|
| observed confidences at proposal emission | {**0.6667**, **1.0**} — 0.6667 exactly on the defect-bearing correct/competing/unseen-family cells, 1.0 on the clean incorrect/irrelevant cells | `abstention_analysis.observed_confidences` |
| decile [0.6, 0.7) — the defect-bearing decile | value(apply) **$0.016392** (4 accepted) vs value(abstain) **undefined** (0 accepted); harm 0.039447 vs undefined | `abstention_analysis.per_decile["6"]` |
| decile [0.9, 1.0] — the clean decile | value(apply) $0.009089 vs value(abstain) $0.009060 — statistically identical | `abstention_analysis.per_decile["9"]` |
| threshold curve over θ ∈ {0, 0.6667, 1.0} | θ=0: cpvo_gated $0.015409, 14 accepted, harm11 0.054931 · θ=1: cpvo_gated **$0.019864**, accepted **14→10**, harm11 **0.054931→0.102860** | `abstention_analysis.threshold_curve[]` |
| verdict | `improving_threshold_exists=false`, `improving_thresholds=[]` — **no θ ∈ (0,1) improves value**; the low-confidence decile is exactly where adaptive fixes defects | `abstention_analysis.improving_threshold_exists` |

The 2c verdict's boundary (`cap_adaptive_2c.md` §5): decline **when the gate has NO information**
(absent-defective $0.046109/escape and unseen-family $0.092218/arm @11.47 escapes) — **not on
confidence**, which is inverse to where adaptive adds value. The 2d campaign tested the
informational-abstention rule and **REFUTED it as built** (`cap_adaptive_2d.md`): capture leg 1/3
< 2/3 (the unseen-family cells measured multi-term risk 0.18, ratio 0.5 — the Option A
fingerprint never instantiated), leg A held numerically but not as a treatment effect, the
incorrect_rebuilt class failed to construct a second time. The 2d confidence curve repeated the
2c null (observed confidences {0.6667, 1.0} again; `improving_threshold_exists=false`,
`cap_adaptive_2d_score_20260828T043139Z.json`). The **2e campaign (RUNNING)** reconstructs only
the leg-3 capture: 6 cells, unseen-family fingerprint pre-verified in p1, capture floor 2/3
(`docs/experiments/preregistrations/cap_adaptive_2e_preregistration.md`).

### 1.3 The confidence signal — what it is, and where it was and was not recorded

The measured `confidence` is the `AgenticResult.confidence` property
(`src/agentic_dynamics/adapters/opencode.py:113`): an **[H] per-attempt execution-confidence**,
outcome-grounded — 0.0 on session error; else `tests_passed/tests_total` when any tests ran;
else the tool-call success fraction; else `None`. It is deliberately **not** the model's
self-reported confidence. In 2c/2d it was recorded on every **proposal record at
proposal-emission time, BEFORE the outcome** (2c preregistration §7 verbatim; 2d preregistration
§7 restated; absent cells carry no proposal, never imputed). `perturbation_strength` +
`test_executed_success` are measured on every story attempt
(`src/agentic_dynamics/knowledge/ledger_ingestion.py:180-181`; the E4 ledger rows carry both,
coverage 9/9).

### 1.4 The measured-vs-missing ledger for the calibration question

| needed for the calibration | measured? | where |
|---|---|---|
| strength-response curve G(s), per model | **PILOT ONLY** — 4 strengths × n=1–3, sonnet-5 only, no CIs | E4 metrics `grit.produces.grit` |
| retry posterior P(success \| failed attempt, s, c) | **NO** — exactly 1 retry observed (n=1, s=0.8, converted at +$3.19 attempt cost) | E4 ledger `cells[7].attempts` |
| confidence per story attempt (the [H] field on attempt rows) | **MISSING in E4** — `build_attempt_row` (`scripts/run_cap_grit_grid.py:129-159`) writes no `confidence` field; the 2c §7 recording requirement was applied to verifier proposal records, never to the grit ledger. The retry-threshold cannot be fit without it | E4 ledger attempt rows |
| calibration curve P(test_executed_success \| confidence bin), per model | **NO** — the 2c/2d confidence distributions are verifier-proposal-level (24/28 cells, 2 point masses), not story-attempt-level | 2c/2d `abstention_analysis` |
| model×strength interaction | **NO** — E4 is sonnet-5 only; the abstention arc is deepseek-v4-pro only | — |
| held-out policy thresholds | **NO** — nothing has been held out; the 2c/2d abstention curve is evaluated over its own full grid | — |
| per-model per-attempt story cost (for budget) | **NO** — the E4 overrun is exactly this gap (flash-scaled estimate, sonnet reality) | E4 ledger `run_status.budget_overrun` |

---

## 2. The two-decisions separation — retry-threshold is not verify-gate, and the 2c null does not constrain grit

The queue item's lesson (HANDOFF §3.2): *"a threshold on confidence for RETRY policy vs the
verify gate are different decisions."* This section makes that precise, because the whole
design hinges on not importing the 2c null into the retry decision.

### 2.1 The two decision points in the machine's vocabulary

| | **Decision 1 — retry-threshold (grit)** | **Decision 2 — verify-gate (abstention)** |
|---|---|---|
| when it fires | **AFTER a failure signal**: `test_executed_success == false` on a completed attempt | **BEFORE application**: a proposal (or refusal) exists, the gate decides apply / apply-null / decline |
| the action | spend another attempt (attempt_number=2, parent_attempt_id set — the E4 fidelity mechanism) | apply exactly as proposed / apply-null / DECLINE → operator review |
| what it consumes | `perturbation_strength`, `test_executed_success`, [H] `confidence`, `actual_cost`, `rework_cost` — all ledger-measured (ledger_ingestion.py:180-181; opencode.py:113) | the informational seam facts: `analysis_revision_matches`, `code_change_risk`, `changed_symbols_with_tests_ratio`, `new_sonar_critical_count` — `code_change_facts/v2` predicates (2d design §2) |
| the question | at what (strength, confidence) does the **expected value of attempt 2** turn negative? | when does the gate **decline to act**? |
| the E_x harm it trades against | the escaped defect if the failure ships (wrong-continue) vs the attempt-2 cost if the retry fails | the escape harm the rule fails to capture vs the flag cost on clean cells |
| status | E4 pilot only — curve unmeasured (n=1 retry) | 2c null (confidence axis) + 2d REFUTE (informational rule as built) + 2e running (leg-3 capture reconstruction) |

### 2.2 Why the 2c confidence-null does NOT constrain grit

1. **Different action spaces.** The 2c abstention curve evaluated *declining proposals* on a
   clean-vs-defective proposal distribution (24 cells, confidences {0.6667, 1.0}). The retry
   decision acts on a **known-failed attempt** — its object is the conditional distribution
   P(success | failure, s), which the 2c analysis never conditioned on. The 2c null says "the
   low-confidence *proposals* are the defect-bearing ones, so declining them destroys value"; it
   says nothing about "the low-confidence *failed attempts* are worth (or not worth) a second
   try." The two conditionals need not move together.
2. **Different information sets.** The retry decision consumes facts the abstention rule does
   not use (`test_executed_success`, `perturbation_strength`) and vice versa (the seam facts).
   The 2c null is a statement about one action with one information set; it cannot be
   transported to a different action with a different information set without a measurement.
3. **A retry on a failing attempt is not a decline on a clean change.** The abstention decision
   declines to *apply* (a pass-level action on a proposal the gate cannot evaluate). The retry
   escalates *effort* on a change that already failed independent verification
   (`runtime.test_runner` — the sole source of truth for `test_executed_success`). One is
   refusal; the other is persistence. They are not even on the same side of the ledger: the
   abstention arm's harm is the escape it *fails to prevent*; the retry arm's harm is the
   attempt-2 cost it *spends*.
4. **The empirical E4 datum is open, not settled.** The grid's only retry converted a genuine
   failure at s=0.8 into success (attempt-2 $3.1866) — but the cell cost doubled ($6.82 vs
   $3.07) and the regret at that stratum was **+$3.7501** (baseline better). Whether that
   conversion is worth it *at s=0.8, at other strengths, and at other confidences* is exactly
   the unmeasured quantity; the 2c null does not answer it in either direction.

The 2d REFUTE cuts the other way and matters as much: the abstention rule's capture leg failed
(1/3), so the *decline* decision is **unverified as a mechanism** — which is precisely why this
design measures the retry decision *independently* rather than folding it into an abstention
rule, and why the two must stay separate rules in the compiler's vocabulary (2d design §2's
`informational_abstention` control rule consumes the seam facts only; the `grit_retry` policy
consumes `test_executed_success` + `confidence` + `perturbation_strength` — no shared
`requires`).

---

## 3. The calibration design — cap_grit_calibration

### 3.1 The question (the campaign's headline)

**Does a retry on a failing attempt pay, and at what (strength, confidence) does it stop
paying — and does that answer differ by model?** Operationalized: the full strength-response
curve G(s) per model, the calibration curve P(success | confidence) against the independent
outcome, and the retry-threshold policy θ* **selected on training strength cells and evaluated
on held-out strength cells** — the review's three asks (HANDOFF §3.2), with the verify-gate
question explicitly out of scope for θ* (it stays the 2d/2e informational rule's question).

### 3.2 The grid shape

**Factors:** `model × condition_strength × policy_arm × repetition`.

| factor | levels | rationale |
|---|---|---|
| `model` | `deepseek/deepseek-v4-pro` (primary — the 2c/2d/2e envelope, backend opencode) · `anthropic/claude-sonnet-5` (cross-envelope — the E4 model, backend claude_cli) | the review's model×strength interaction ask; the E4 curve is sonnet-5-only and the abstention arc is deepseek-only — neither alone answers the calibration |
| `condition_strength` | training set {0.0, 0.2, 0.4, 0.6} · held-out set {0.3, 0.5, 0.7} — 7 distinct strengths total | **full** response curve (E4 had 4); the held-out set is **interleaved strengths** (a design axis, never randomized): thresholds selected on the training strengths must generalize to unseen strengths — the review's held-out ask made operational. Mechanical distinctness per the E4 precedent: s=0.2/0.4/0.6/0.7 via verified `inject_bug` artifacts (compiled per cell, `compile_mutation(spec, "inject_bug", strength=s)`, load-checked like `mut_3caacc977303246d`/`mut_1957f3238ebc0f5c`), s=0.5 via the standard on-disk `bad` variant (`CONDITION_STRENGTH=0.5`), s=0.0 clean, s=0.3/0.7 via the same artifact seam |
| `policy_arm` | `baseline` (max_attempts=1) · `grit_retry` (unconditional retry-on-failure, max_attempts=2) on ALL training cells · `grit_retry@θ*` (live) on ALL held-out cells | baseline + unconditional retry bound the θ* evaluation from both sides (θ=1 ≈ baseline, θ=0 ≈ unconditional grit_retry — read off the same grid); θ* is a **live arm on held-out cells** (retry counterfactuals are not estimable shadow-style — the cap_confidence_cascade tautology lesson: a never-executed retry arm has `regret 0.0 by construction` per scripts/CONTEXT.md) |
| `repetition` | r = 3 | E4's n=1 per cell gave no CI at all; r=3 gives the curve a real shape with Wilson intervals per strength |

**Cell count:** training 2 models × 4 strengths × 2 arms × 3 reps = **48 cells**; held-out
2 models × 3 strengths × 2 arms × 3 reps = **36 cells**; total **84 story runs** (≤ 2 attempts
each on the retry arms). Each cell = one `task_manager_api` story (5 sessions) in a fresh
worktree with a unique `FINOPS_CELL_ID`, `enforce_pytest=True` — the E4 machinery unchanged.

### 3.3 The policy arms and the threshold set

- `baseline` — score the single attempt unconditionally (E4 finding-4 definition).
- `grit_retry` — second attempt iff first `test_executed_success == false` (E4 finding-4
  definition; fidelity rule carried over verbatim).
- `grit_retry@θ*` — second attempt iff first failed **and the attempt's [H] confidence ≥ θ***,
  where **θ\* ∈ {0.4, 0.6, 0.8} is pre-registered and selected on the training cells only**
  (argmin of `cpvo_harm` over the training grid; tie-break by verified success rate; θ=0 and
  θ=1 are read off the training grid's unconditional/never-retry arms as the bounds). The
  pre-registration fixes the candidate set; the fit is mechanical, never post-hoc.

### 3.4 The decision rule (pre-registered)

Primary outcome, per model: **cpvo_harm(arm) = (Σ cost + Σ harm) / Σ accepted** at the measured
**E_x = 11.4671** (sensitivity at 28), the 2c/2d model verbatim — accepted =
`test_executed_success == true` on the final commit (independent `runtime.test_runner`), cost =
measured ledgered `actual_cost`, harm = escaped defects × $0.046109 @11.47 ($0.112588 @28)
(escalation score JSON `loss_table` — the E_x machinery reused, never re-derived).

**SUPPORT ⟺ all of, per model, on the HELD-OUT cells:**

1. **Held-out threshold win:** `cpvo_harm(grit_retry@θ*) < cpvo_harm(baseline)` @11.47 on the
   held-out strengths.
2. **Non-flat response curve:** measured G(s) over the full 7-strength axis (training + held-out
   pooled for the curve, n ≥ 3 per strength) has range > 0.15 between any two strengths — the
   axis actually responds.
3. **Calibration estimable and predictive:** P(test_executed_success | confidence bin) over the
   pooled attempt ledger (bins over the recorded [H] confidence, n ≥ 5 per bin) is defined and
   monotone non-decreasing — the signal the retry decision conditions on predicts the
   independent outcome it trades against.
4. **Fidelity + coverage guards:** retry fidelity 0 violations (retry never fires on a passed
   attempt; baseline never retries), cost + test-verification coverage = 1.0 on both axes.

**The abstention re-check (analytic probe, EXPLORATORY — not a decision leg):** the campaign
re-reports the 2c/2d abstention curve over the new confidence distribution and asserts the
confidence-free constraint on the **decline** decision (2d prereg §1 pattern) — never fixes a
threshold on it, never lets θ* touch it.

### 3.5 The harm model and what the retry trades

- **If the failed attempt ships (no retry):** the escaped-defect harm at E_x —
  `harm = E_x × $0.004021` = **$0.046109 @11.47 / $0.112588 @28 per escaped defect**
  (escalation score JSON `base_downstream_defect_cost_usd` × `per_model[0].E_x`, `loss_table`).
- **If the retry fires:** the attempt-2 `actual_cost` (measured; E4's realized attempt-2 cost
  was $3.1866 on sonnet-5) + any continuation/subagent spend (`rework_cost` field — measured
  **$0.00 everywhere in E4**, runplan §10 F6: the rework axis is constant-zero until a cell
  actually spends; the calibration records it honestly rather than assuming it stays zero).
- **The retry pays when** `P(success | failure, s, c) × value(success) > cost(attempt 2)` —
  where value(success) is the avoided escape harm. The calibration measures every component:
  the posterior from the live retry arms, the cost from the ledger, the harm from the E_x
  loss table.

### 3.6 The budget (the E4 lesson, applied)

- **The E4 overrun is a hard precedent, not a footnote:** sonnet-5 story attempts cost
  **$3.07–4.13** (ledger `realized_cost`), the flash-scaled $0.30–0.60 estimate was ~10× wrong,
  and the runplan's release verdict explicitly re-baselines before the next grid
  (runplan §10: "the next grid must re-baseline per-story cost empirically before committing a
  budget"). This design therefore **fixes no absolute per-cell number in advance**: the
  preregistration fixes the grid's final N and per-envelope ceilings **from p1 probe cells**
  (one story attempt per model on the anchor strengths) — the probes are the budget's only
  input, never a scaled estimate from another model's envelope.
- **Primary envelope (deepseek-v4-pro):** 84 cells within the $30 stop (`stop.budget_usd`,
  the 2b–2e pattern). If the p1 probe is ≈$0.05–0.15/attempt (deepseek story scale), 84 ×
  (probe × ≤2 attempts) fits inside $30; if the probe is higher, the **pre-registered
  contraction** drops repetitions 3→2 (84 → 56 cells) — arms, strengths, and the threshold
  rule are never re-opened (the 2d prereg §2 contingency pattern).
- **Cross-envelope tranche (sonnet-5):** runs in parallel on the anthropic envelope with its
  **own ceiling**, computed at p0 as `12 cells × probe × 2 attempts` (12 = the 2 models × 3
  held-out strengths × 2 arms... at r=1 — a held-out-only re-check sized to the E4-measured
  sonnet cost, ~$37–50 worst case; a separate envelope budget, never shared with the deepseek
  stop). The 2d prereg §6 parallel-vehicles precedent (separate rate limits, separate
  envelopes, data chain single-writer) governs.

### 3.7 The seed discipline (2b/2c pattern)

Committed seed + full assignment table in the preregistration before any cell runs: seed =
`sha256("cap_grit_calibration|train{0.0,0.2,0.4,0.6}-heldout{0.3,0.5,0.7}|baseline-grit_retry-theta|20260828")`
(the honest-derived pattern of 2d prereg §4), block-randomized within (model × strength) blocks
for arm order; the **training/held-out split is a fixed design axis** (strength levels), never
randomized and never re-negotiated after the fit. Every attempt row carries the full
LEDGER_FIELDS vocabulary **plus the [H] `confidence` field** (the 2c §7 recording requirement
extended to the grit ledger — the field E4's `build_attempt_row` omitted; a row without it is
flagged, never imputed, excluded from the calibration bins with the count reported).

### 3.8 How the design engages the 2d abstention result

1. **θ\* is fitted on held-out strength cells, never on the 2c/2d confidence distribution.**
   The 2c curve lives on the proposal-level distribution {0.6667, 1.0} of the verifier's
   decline action; the retry threshold's training distribution is the attempt-level
   (strength × confidence × test_executed_success) of the story grid. Importing the 2c
   distribution into the retry fit would be exactly the conflation §2.2 refuses.
2. **The abstention rule stays confidence-free.** The 2d/2e decline rule consumes the seam
   facts only; this campaign's θ* consumes confidence + test_executed_success + strength.
   They are separate control rules with disjoint `requires`; the campaign evaluates them in
   separate arms and never reports a fused "gate" verdict.
3. **The 2e result lands first (sequencing, §4) and is orthogonal:** 2e's capture leg (does
   the leg-3 fingerprint fire?) has no retry content; a REFUTE in 2e would say the *decline*
   mechanism is unconstructible — which would *strengthen* the case for measuring the retry
   decision as the remaining actionable policy, not weaken it.

---

## 4. Relationship to the running campaigns

- **`cap_adaptive_2e` (RUNNING)** — the leg-3 capture reconstruction, 6 cells on the deepseek
  envelope, capture floor 2/3 (2e prereg). **This design is the next deepseek-envelope campaign
  after 2e completes** — the envelope is single-owner (2d prereg §6 single-writer discipline);
  the deepseek tranche of this grid starts only after the 2e verdict lands.
- **Parallel, not serial:** the sonnet-5 cross-envelope tranche (§3.6) can run concurrently on
  the anthropic envelope (separate rate limits — the 2d prereg §6 precedent) once the p1 probes
  set its ceiling.
- **No other machine is touched:** the data chain (spec index / manifest / data.js / deploys)
  stays single-writer; no campaign edits `workflow_runner.py` / `experiment_spec.py` while the
  cells are in flight; the abstention rule remains shadow-only (2d design §6 boundary).

---

## 5. The falsifiability contract — what refutes the calibration

A verdict REFUTES the calibration hypothesis if **any** of:

1. **Flat response curves** — G(s) over the 7-strength axis (n ≥ 3/strength) has range ≤ 0.15
   between any two strengths, or is non-monotone with no Δ > 0.15 anywhere: there is no
   strength-response to fit, and the E4 curve ({0.5, 1.0, 1.0, 0.6667}) fails to replicate at
   power. The strength axis does not carry the signal the retry decision would condition on.
2. **Confidence does not calibrate** — P(test_executed_success | confidence bin) is flat or
   inverse at bin n ≥ 5: the [H] signal cannot predict the independent outcome it would gate,
   so no confidence threshold is defensible (the 2c null replicated at the attempt level, this
   time as a measurement rather than an abstention-curve artifact).
3. **The fitted threshold fails held-out** — `cpvo_harm(grit_retry@θ*) ≥ cpvo_harm(baseline)`
   on the held-out strengths @11.47: the threshold selected on training cells does not
   generalize to unseen strengths, the review's held-out ask answered negatively.
4. **Retry pays negative returns at all θ** — the unconditional retry arm (θ=0) does not beat
   baseline on the training cells: no threshold can rescue a negative-expected-value action,
   and the E4 high-strength pattern (regret +$3.7501, 2.2× cell cost) generalizes.
5. **Machinery failures** — the 2c-family failure modes: retries never fire on engineered
   failure-bearing cells (the retry posterior unestimable — the incorrect-class construction
   lesson), retry fidelity violations, coverage < 1.0 on either axis, or a budget breach
   without the p1 re-baseline (the E4 overrun repeated as a design failure, not a measurement).

A verdict SUPPORTS the calibration if the curve responds, the calibration is predictive, θ*
wins on held-out cells, and the machinery is clean — at which point the policy arm
(`grit_retry@θ*`) becomes a candidate factor level for the next grid (the `adapt` loop: one
variable — the retry threshold — carried into a new campaign), with the verify-gate question
still owned by the 2d/2e abstention arc.

## Guard

Every number in this document cites its source artifact + field (paths and fields inline in
§1–§3): the E4 ledger/metrics JSONs for the grit grid, the 2c/2d score JSONs + verdicts for the
abstention, the escalation score JSON for E_x and the loss table, `opencode.py:113` for the
confidence definition, `ledger_ingestion.py:180-181` for the attempt fields, the 2e
preregistration for the running campaign, HANDOFF §3.2 for the review's list. No hash is
invented for artifacts this document did not read. The grid shape, arms, threshold set,
decision rule, harm model, and falsifiability contract are fixed here; every absolute number
(cells, repetitions, ceilings) is fixed by the preregistration from the p1 probes — the E4
budget lesson encoded.

**LOG:** the measured state restated from the three artifact families (E4: G(s) =
{0.0: 0.5, 0.2: 1.0, 0.5: 1.0, 0.8: 0.6667}, grit_auc 1.4, recovery_premium 1.1277, one retry
converting s=0.8 at 2.2× cell cost, regret +$3.7501, $31.27 vs $10 ceiling; 2c/2d: the
confidence-null — no θ improves the decline decision, decile [0.6,0.7) is where adaptive adds
its value; 2e running: leg-3 capture reconstruction); the two-decisions separation argued
(retry-threshold acts post-failure on the attempt-level conditional with the ledger facts;
verify-gate acts pre-application on the seam facts; the 2c null constrains neither the action
space nor the information set of the retry decision — a retry on a failing attempt is not a
decline on a clean change); the calibration designed (2 models × 7 strengths
{train 0.0/0.2/0.4/0.6, held-out 0.3/0.5/0.7} × 2 arms × 3 reps = 84 cells; threshold arms
θ* ∈ {0.4, 0.6, 0.8} selected on training strengths, evaluated live on held-out strengths;
cpvo_harm @E_x 11.47 decision rule with the four legs; the E_x harm model reused; the budget
re-baselined from p1 probes per envelope with the deepseek stop at $30 and a separate sonnet
ceiling — the E4 overrun never repeated by design; seed discipline + full table deferred to the
preregistration; the 2d engagement: θ* never fit on the 2c distribution, abstention stays
confidence-free, 2e sequencing); the falsifiability contract (flat curves, non-calibrating
confidence, held-out failure, negative returns at all θ, machinery failure — any one refutes).
**PROPOSED — awaiting the operator's review; nothing is committed or run.**
