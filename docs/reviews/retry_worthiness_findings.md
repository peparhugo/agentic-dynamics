---
status: accepted
---

# Retry-worthiness findings — the observational retry lookup (the grit replacement)

**Role:** p3 (findings). **Spec:** `retry_observational_analysis@0.1` (spec SHA256
`b07d86d7cac1a5cbab0db5b67e35085a02f5ee58d628b8ef0fccfdf105b12b9b` — pinned into the grit
design's parking note at p0). **Phases consumed:** p1 (`chains.json`, `retry_chains/v1`),
p2 (`lookup.json`, `retry_lookup/v1`). **Numbers:** every figure below traces to a field in
those two artifacts or the cited framework/escalation artifacts; nothing is re-derived here
beyond the arithmetic p2 already pinned.

**The headline in one line:** the corpus holds **exactly one real retry event**, and it is
**economically irrational at the measured scales** — a $3.19 same-model re-attempt spent to
avoid $0.046 of escaped-defect harm (a 69× loser), so the retry-worthiness lookup is
**unidentified** and the machine's best read at first-failure is *cost*, not *confidence*.

---

## 1. Methodology — the observational framing, pinned definitions, coverage

**Framing.** This is an observational analysis, not a controlled grid. No cells were run, no
treatments assigned. The corpus's *existing* fail → retry → outcome chains were extracted from
two planes and joined:

1. **The attempt ledgers** — records carrying the retry-linkage fields (`attempt_number`,
   `parent_attempt_id`, `retry_reason`). Exactly two files carry them in the committed corpus:
   `experiments/results/cap_grit_grid_ledger.json` (the E4 grit grid, 9 attempts) and the
   synthetic `ledger_instrumentation_probe` (2 attempts). The E4 rows carry **no** `confidence`
   field (the design-doc §1.4 gap).
2. **The story results** — `experiments/results/stories/*.json`. The post-instrumentation runs
   (120 of 255) carry `perturbation_strength`, `test_executed_success`, and per-session
   `confidence`. The E4 grid's story runs are among these, so the known-at-failure features for
   the one retry are recovered by joining `result_path`.

**Pinned definitions** (spec hard rule 3, verified complete at p0):

- **rescue signal** — retry succeeded (the retry's `test_executed_success`) / retry failed /
  no-retry-was-taken.
- **known-at-failure features** — the `[H]` confidence (opencode.py:113), the perturbation
  strength, the cost-so-far, the attempt number.
- **WOC** = `1/(1+r)` (the framework equation, unchanged); **E_x anchors** = 11.47 / 28 (spec
  hard rule 7; 12.51 reported alongside as the sonnet-measured value).

**Coverage (exact).** 11 attempt-ledger records (E4 9 + probe 2); **2 failed-first attempts**
(both E4); **1 retry**; **2/2** complete chains (no imputation). The story corpus is 255 files —
120 wired, 24 wired-failed, **0 with retry linkage** (the story runner has no retry mechanism).
The bottom line: **1 real retry event in the entire corpus.**

---

## 2. The retry-worthiness lookup

### 2.1 Rescue-rate-by-signal

| axis | populated bin | retried | rescued | rescue rate | Wilson 95% |
|---|---|---|---|---|---|
| confidence decile | [0.8, 0.9) | 1 | 1 | 1.0 | [0.21, 1.0] |
| strength | 0.8 | 1 | 1 | 1.0 | [0.21, 1.0] |
| cost-so-far | [$3.6] | 1 | 1 | 1.0 | [0.21, 1.0] |

Every *other* decile / strength / cost bin is **n = 0** — reported as unmeasurable, never
imputed. The "rescue-rate-by-signal table" is therefore **one populated cell per axis**. The
rescue rate is 1/1, and its Wilson interval spans [0.21, 1.0]: the observed data is consistent
with a true rescue rate anywhere from 21% to 100%. **The lookup pins nothing.**

### 2.2 The boundary at E_x

The retry-worthiness condition is `P(rescue) × value(rescue) > cost(retry)`, where
`value(rescue) = E_x × $0.004021` (the avoided escaped-defect harm; base defect cost from the
escalation score JSON) and `cost(retry)` is the measured attempt-2 cost.

| E_x | rescue value | measured retry cost | net EV @ P=1 | retry cost ÷ rescue value |
|---|---|---|---|---|
| 11.4671 (measured sol) | $0.0461 | $3.1866 | **−$3.1405** | **69.1×** |
| 12.5134 (measured sonnet) | $0.0503 | $3.1866 | −$3.1363 | 63.3× |
| 28.0 (sourced) | $0.1126 | $3.1866 | −$3.0740 | 28.3× |

**Break-even E_x at P(rescue)=1: 792.5×.** For the retry to pay, the escaped-defect harm would
have to be ~792× the base cell cost — versus the measured 11.5–12.5× and the sourced 28×. The
retry cost **dwarfs** the rescue value at every realistic E_x. This is the retry-worthiness
boundary, and it is far on the *do-not-retry* side.

**Why the boundary sits there (the load-bearing observation):** the retry is a **full same-model
re-attempt** (sonnet-5 story, $3.19), not an escalation. The harm model's base ($0.004021) is a
flash-scale cell, so `E_x × base` = $0.046 is ~69× smaller than the story-attempt cost. The two
scales do not meet: a retry that costs one whole story attempt cannot be repaid by a harm term
priced on a flash cell.

### 2.3 No-retry-was-worse

**Not identifiable.** 1 failed-without-retry attempt (E4 `clean × baseline`, $3.5575, escaped
defect) + 24 wired-failed stories vs 1 retried-and-rescued chain ($6.8195). The comparison is a
counterfactual over n=1, and the two observed failures are **different failure modes** — the
retried cell failed on an *injected* bug (bad_seed_high, s=0.8) while the no-retry cell failed
*genuinely* (the E4 F5 `limiter.reset()` harness failure). Nothing here licenses a "no-retry was
worse" claim.

---

## 3. The measured WOC and r

| plane | r | WOC = 1/(1+r) |
|---|---|---|
| framework "11.5% scenario" | 0.115 | 0.8969 |
| E4 grit grid (8 cells, retry armed) | 1/8 = **0.125** | **0.8889** |
| attempt plane (E4 + probe) | 1/11 = 0.0909 | 0.9167 |
| story corpus (no retry mechanism) | **0.0** | **1.0** |

The E4 `r = 0.125` sits within a hair of the framework's 11.5% — **by coincidence, not by
measurement**. It is one retry over eight cells in a grid where `grit_retry` was *deliberately
armed on half the cells*, and it fired exactly once (the one grit_retry cell that failed). The
actual story corpus (the Rules 1–5 perturbation data, 255 runs) has **r = 0** because its runner
has no retry mechanism at all. So the "measured" retry rate is a story-grid artefact, not an
autonomous-workload figure.

---

## 4. The framework correction

Three corrections, each scoped to what the corpus can and cannot support:

1. **The "11.5% scenario" is not measured — and its coincidental match is a different thing.**
   The framework's `r = 0.115` (WOC = 0.90) is a scenario parameter, not a ledger value. The only
   attempt ledger with a non-zero `r` is the E4 *story* grid (r = 0.125), not the autonomous
   workload the framework's `r` lever targets. The story corpus's true retry rate is **0**. The
   WOC correction is therefore **no material change** (0.8889 vs 0.8969) *and* a warning that the
   number is not being fed by the plane the framework assumes.

2. **The retry cost is a full re-attempt, not an escalation — the `E_x` multiplier does not
   apply to the retry decision.** The framework's job-cost term `C_job = C₀·EPM·(1−b·0.5)·(1+r·E_x)`
   prices a retry as an *escalation* (E_x × C₀). The measured retry is a **same-model
   re-attempt** costing 1.0 × C_attempt ($3.19), which at the sonnet story scale is ~69× the
   escalation-priced harm ($0.046). A retry is `+1` attempt, not `+E_x` — the correct inflation
   is `(1 + r)` (already captured by `WOC = 1/(1+r)`), and the `r·E_x` escalation term is a
   *different* decision (escalating to a pricier model), which the retry does not do.

3. **The retry-worthiness boundary is cost-dominated, not signal-dominated.** Break-even
   E_x = 792× means the decision is decided by `cost(attempt 2)` vs `E_x × base` — i.e. by the
   *attempt-cost scale*, not by any per-attempt feature. This is the deepest correction: the
   grit design's premise (fit a retry threshold over `(strength, confidence)`) addresses a term
   that is 69× smaller than the term that actually decides the retry.

---

## 5. The retry-policy recommendation — what the machine should read at first-failure

The lookup the machine should read at first-failure is **three numbers, and none of them is
confidence**:

1. **Gate on cost, not confidence.** The `[H]` confidence *does* separate failures from passes
   on average — final-session confidence mean **0.6454** (median 0.755) on the 24 wired-failed
   stories vs **0.9094** (median 1.0) on the 96 wired-passed ones — but the *single* retried
   failure carried confidence **0.8462**. That is the field's meaning made visible: confidence is
   **execution-confidence** (tool-run smoothness), and a cleanly-executed session still ships an
   injected bug. A confidence threshold cannot gate the retry; it would admit the exact
   high-confidence failure it is meant to catch. (This is the attempt-level echo of the 2c
   abstention null — "no confidence threshold improves value" — extended to the retry decision.)

2. **Read the retry-worthiness boundary, which is cost.** Retry only when
   `cost(attempt 2) ≤ E_x × $0.004021`. At the measured sonnet story scale ($3.19 vs $0.046) that
   inequality is **69× false** — so the machine should **not retry story-scale attempts**. The
   inequality only clears on *cheap* cells (flash-scale, where a re-attempt is a few cents and
   `E_x × base` is comparable). The retry decision is worth reconsidering only at the flash scale,
   never at the sonnet story scale.

3. **If a feature must gate, prefer `perturbation_strength` over `confidence`.** The one
   retried failure sat at the grid's **top strength (s=0.8)**, and the E4 G(s) curve dips only
   there (G = {0.0: 0.5, 0.2: 1.0, 0.5: 1.0, 0.8: 0.6667}). Strength is a *causal* feature of the
   stimulus; confidence is a *symptom* of execution. But this is n=1 — a preference, not a pinned
   threshold.

**Bottom line for the machine:** the retry-worthiness lookup is **unidentified at n=1**, and the
strongest honest read is that the retry is **economically dominated at the measured story scale
and should be gated off by cost, not armed by confidence**. The grit campaign's 84-cell curve was
over-built not because the question is unimportant but because the *binding* term — the re-attempt
cost vs the harm — is already measured and already negative.

---

## 6. Honest limits (confounds + coverage)

- **n = 1 retry.** The rescue rate 1/1 has Wilson 95% [0.21, 1.0]; the lookup cannot be pinned.
- **Observational, uncontrolled.** The retry was armed only in the E4 `grit_retry` arm; the single
  retried failure and the single no-retry failure are *different failure modes* (injected bug vs
  genuine harness failure) — a confound no adjustment removes at n=1.
- **Scale mismatch.** retry cost (sonnet-5 story, $3.19) vs rescue value (flash-scale base × E_x,
  $0.046) — the economics are dominated by the attempt-cost scale, and the break-even E_x = 792×
  is a statement about that mismatch as much as about retries.
- **Confidence semantics.** the `[H]` field is execution-confidence, not correctness; its
  failure/pass separation (0.645 vs 0.909) is a correlation, never a causal claim, and it misses
  the one retried failure.
- **Coverage.** 2/2 of the *failed-first attempts* have complete chains, but that is 2/11 of all
  attempt-ledger records; the story corpus contributes 24 wired failures with **zero retry
  linkage**. The autonomous-workload attempt ledger the framework's `r`/`WOC` need is still absent
  from the committed corpus.
- **The 2c lesson carries forward:** a retry decision that gates on a *symptom* (confidence)
  repeats the abstention-null mistake; the only decision-relevant quantity measured here is
  *cost*.

---

## Guard

Every number cites its artifact: chains/coverage → `experiments/results/retry_analysis/chains.json`
(`retry_chains/v1`); the lookup, WOC, economics, confidence distribution →
`experiments/results/retry_analysis/lookup.json` (`retry_lookup/v1`); E_x and base defect cost →
`cap_escalation_measurement_score_20260826T125726Z.json` (`per_model[].E_x`,
`base_downstream_defect_cost_usd` 0.004021); the framework equations →
`docs/reviews/workflow_metrics_findings.md` §3.3 (`WOC = 1/(1+r)`,
`C_job = C₀·EPM·(1−b·0.5)·(1+r·E_x)`); E4 G(s) and the arm comparison →
`cap_grit_grid_metrics.json` (`grit.produces.grit`, `arm_comparison.stratified`). No number is
invented; the "11.5% scenario" is quoted as the framework's `r=0.115`, and the sourced E_x=28 is
labelled as such throughout.

**LOG:** findings — (1) 1 real retry event, rescue rate 1/1 Wilson [0.21,1.0], lookup
unidentified; (2) retry economics deeply negative (retry cost $3.19 = 69× the $0.046 rescue
value @11.47, break-even E_x 792×); (3) WOC/r: measured r 0.125 (E4) coincidentally near the
11.5% scenario, story-corpus r 0, WOC 0.8889 ≈ 0.8969 — no material WOC correction; (4) framework
correction: the retry is a full same-model re-attempt, not an `E_x` escalation; (5) policy: gate
on **cost**, not confidence — confidence is execution-confidence (misses the 0.8462 failure),
prefer strength if a feature must gate. **PASS — committing.**
