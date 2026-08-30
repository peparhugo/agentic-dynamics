---
status: accepted
---

# retry-worthiness — adversarial verification

**Role:** adversarial verifier (p4). **Source revision:** `workflows/repository/retry_observational_analysis.yaml`
SHA256 `b07d86d7cac1a5cbab0db5b67e35085a02f5ee58d628b8ef0fccfdf105b12b9b`. **Findings:**
`docs/reviews/retry_worthiness_findings.md`. **Consumed artifacts:** p1
`experiments/results/retry_analysis/chains.json` (`retry_chains/v1`), p2
`experiments/results/retry_analysis/lookup.json` (`retry_lookup/v1`). **Adversary inputs (raw, not
the derived outputs):** `experiments/results/cap_grit_grid_ledger.json`,
`experiments/results/stories/task_manager_api_claude_sonnet_5_bad_seed_{7b38e1d32d59,2b6d8dd557e9}.json`,
`experiments/results/stories/task_manager_api_claude_sonnet_5_clean_c0e0d6871f69.json`,
`experiments/results/cap_escalation_measurement/cap_escalation_measurement_score_20260826T125726Z.json`,
`experiments/results/cap_grit_grid_metrics.json`, `docs/reviews/workflow_metrics_findings.md`,
`src/agentic_dynamics/adapters/opencode.py`.

## Findings table

| # | Attack (order) | Result | Disposition |
|---|---|---|---|
| F1 | (1) observational framing — scan for a controlled/causal claim | **PASS** | no finding; the only causal-looking strings are an attributed 2c quote and interpretive prose; no "caused/randomized/assigned/controlled" claim |
| F2 | (2) arithmetic — re-derive WOC + one rescue-rate bin from raw chains | **PASS** | no finding; r=1/8=0.125, WOC=0.8889, rescue 1/1 (Wilson [0.2065,1.0]) recompute from the ledger |
| F3 | (3) coverage — the complete-chains table exact | **PASS** | no finding; 8 cells/9 attempts/1 retry/2 failed-first; 2 chains; story 255/120/24/0 recomputed |
| F4 | (4) confounds disclosed | **PASS** | no finding; n=1, scale mismatch, confidence semantics, uncontrolled, coverage all present in §6 |
| F5 | (5) economics at E_x — boundary re-derived | **PASS** | no finding; $3.1866 ÷ $0.0461 = 69.1×; break-even E_x=792.5 recomputes |
| F6 | (6) citations resolve | **PASS*** | one minor: `opencode.py:113` is actually `:119` (confidence property); every *other* citation resolves to the exact field/line |

\* F6 is a precision note, not a falsification: the cited `confidence` field exists and its
definition matches verbatim; only the line number is six lines off (the `:113` figure is inherited
from the grit design's §1.3, and was already flagged in the p0 verification record
`docs/verification/cap_grit_calibration_verification.md`).

**No attack falsified a substantive claim.** The findings' three load-bearing conclusions —
(1) exactly one real retry event exists, (2) the retry economics are deeply negative at the
measured story scale (69× the rescue value), (3) the lookup is unidentified at n=1 and the
decision is cost- not confidence-dominated — are each *strengthened* by re-derivation.

---

## Attack-by-attack

### (1) Observational framing — scan for a controlled/causal claim — **PASS**

Grepped the findings doc for causal/controlled language (`caused|causes|led to|leads to|
improve|reduce|randomiz|assign|treat|we ran|controlled`). The only matches:

- §5.1, "no confidence threshold improves value" — a **quoted** fragment of the 2c abstention
  null, attributed inline, not a claim this doc makes about its own data.
- §5 bottom, "over-built not because … but because …" — interpretive prose about *why the grit
  campaign was parked*, not a controlled-effect claim about the retry.

The doc states "OBSERVATIONAL", "n=1", "not identifiable", "counterfactual", and "a correlation,
never a causal claim" at every juncture; §6 carries the confounds. The framing holds: **no
"caused" statement exists.** The single use of the word *causal* ("strength is a *causal* feature
of the stimulus", §5.3) describes the perturbation as the *manipulated factor in the stimulus
design*, not a causal claim about the retry's effect — read in context it is not a controlled
claim.

### (2) Arithmetic — re-derive WOC + one rescue-rate bin — **PASS**

Re-derived from `cap_grit_grid_ledger.json` directly (8 cells, 9 attempts): the single retry row
(`bad_seed_high × grit_retry`, attempt_number=2, `retry_reason=first_attempt_test_failure`,
`parent_attempt_id` = that cell's a1, `test_executed_success=True`, `actual_cost=3.1865708`).

- `r = 1 retry / 8 cells = 0.125`; `WOC = 1/(1+0.125) = 0.888888…` — matches the findings' 0.8889.
- Rescue-rate bin: 1 rescued / 1 retried = 1.0; Wilson 95% for 1/1 = **[0.2065, 1.0]** — matches.

### (3) Coverage — the complete-chains table exact — **PASS**

Re-counted independently: 8 cells → 9 attempts (the one grit_retry cell contributes two); 2
failed-first (`clean × baseline` a1 tes=false, `bad_seed_high × grit_retry` a1 tes=false); 1
retry; **2 complete chains** (1 rescued, 1 no-retry-was-taken), 2/2 of failed-first, 2/11 of all
attempt records (9 E4 + 2 synthetic probe). Story corpus: 255 files, 120 with
`test_executed_success`, 24 wired-failed, **0 with retry linkage**. Every count in the findings
§1 and the chains table matches.

### (4) Confounds disclosed — **PASS**

Findings §6 discloses all five material confounds: n=1 (Wilson [0.21,1.0]); observational/
uncontrolled (the retry armed only in the grit_retry arm); scale mismatch (sonnet story retry cost
vs flash-scale base); confidence semantics (execution-confidence, not correctness); coverage (2/2
failed-first but 2/11 total, plus 24 wired-failed with no retry linkage). Nothing material is
undisclosed.

### (5) Economics at E_x — boundary re-derived — **PASS**

From `cap_escalation_measurement_score_…json`: `base_downstream_defect_cost_usd = 0.004021`,
`per_model[].E_x = {11.4671, 12.5134}`, `loss_table` column E_x=11.4671 → `0.046109`.

- rescue value @11.4671 = 11.4671 × 0.004021 = **0.046109** — matches.
- retry cost = the a2 `actual_cost` = **3.1865708** — matches.
- retry cost ÷ rescue value = 3.1865708 / 0.046109 = **69.1×** — matches.
- break-even E_x at P(rescue)=1 = 3.1865708 / 0.004021 = **792.5×** — matches.

The boundary is correct and the "deeply negative" characterization is not an overstatement: at
the measured E_x the net EV is −$3.14 and the retry cannot break even below E_x ≈ 792×.

### (6) Citations resolve — **PASS** (one precision note)

Resolved: the escalation score JSON (`base_downstream_defect_cost_usd`, `per_model[].E_x`,
`loss_table`); `cap_grit_grid_metrics.json` (`grit.produces.grit` =
`{0.0:0.5, 0.2:1.0, 0.5:1.0, 0.8:0.6667}`, `arm_comparison.stratified`);
`workflow_metrics_findings.md:102` (`WOC = 1/(1+r)`, `C_job = C₀·EPM·(1−b·0.5)·(1+r·E_x)`).

**Minor (F6):** the findings cite `opencode.py:113` for the confidence field; the property is at
`opencode.py:119` (`def confidence(self)`). The field resolves and the definition matches
verbatim; the `:113` figure is inherited from the grit design's §1.3 and was already noted in the
p0 verification. Recorded as a precision note — the citation's *substance* resolves.

---

## Verdict

**PASS.** Six attacks attempted; none falsified a finding. One precision note (opencode.py line
number :113 → :119), which does not affect any claim. The findings are adversarial-clean: the
arithmetic re-derives, the coverage is exact, the confounds are disclosed, the framing is
observational throughout, and the boundary is pinned. Committing the findings as known-safe with
the single precision note carried forward.
