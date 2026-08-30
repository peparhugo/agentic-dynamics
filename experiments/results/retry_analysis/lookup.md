---
status: accepted
---

# Retry-worthiness lookup — p2 computation

**Spec:** `retry_observational_analysis@0.1` · phase `p2_compute_lookup` · OBSERVATIONAL (n=1 retry).

## 1. Rescue-rate-by-signal

Overall: 1/1 rescued (rate 1.0, Wilson 95% [0.2065, 1.0]).

**by_confidence_decile:**
| bin | retried | rescued | rescue rate | Wilson 95% |
|---|---|---|---|---|
| [0.8, 0.9) | 1 | 1 | 1.0 | [0.2065, 1.0] |

**by_strength:**
| bin | retried | rescued | rescue rate | Wilson 95% |
|---|---|---|---|---|
| 0.8 | 1 | 1 | 1.0 | [0.2065, 1.0] |

**by_cost_so_far:**
| bin | retried | rescued | rescue rate | Wilson 95% |
|---|---|---|---|---|
| [$3.6] | 1 | 1 | 1.0 | [0.2065, 1.0] |

## 2. Measured r and WOC = 1/(1+r)

| quantity | value |
|---|---|
| framework r (11.5% scenario) | 0.115 |
| framework WOC | 0.8969 |
| measured r (E4 grid, 8 cells, retry armed) | 0.125 |
| measured WOC (E4 grid) | 0.8889 |
| measured r (attempt plane, E4+probe) | 0.0909 |
| measured WOC (attempt plane) | 0.9167 |
| measured r (story corpus, no retry mechanism) | 0.0 |
| measured WOC (story corpus) | 1.0 |

## 3. Retry economics at E_x

measured retry cost (E4 attempt-2) = $3.186571 · observed P(rescue) = 1.0 (Wilson 95% [0.2065, 1.0]) · base defect cost = $0.004021

| E_x | rescue value | retry cost | net EV @P=1 | retry cost ÷ rescue value |
|---|---|---|---|---|
| 11.4671 (measured sol (cap_escalation_measurement)) | $0.046109 | $3.186571 | $-3.140462 | 69.11× |
| 12.5134 (measured sonnet (cap_escalation_measurement)) | $0.050316 | $3.186571 | $-3.136254 | 63.33× |
| 28.0 (sourced pricing ratio (site economics)) | $0.112588 | $3.186571 | $-3.073983 | 28.3× |

**Break-even E_x at P(rescue)=1:** 792.48× (the retry cost is this many times the base defect cost).

## 4. No-retry-was-worse

failed-without-retry (attempt ledger) = 1 · failed-without-retry (story corpus) = 24 · retried-and-rescued = 1

escaped harm per defect: $0.046109 @11.4671, $0.050316 @12.5134, $0.112588 @28.0)
no-retry example: cap_grit_strength_grid_condition_strength_clean_policy_arm_baseline_model_anthropic_claude_sonnet_5 ($3.5575)
retried chain: $6.8195
**Verdict:** not-identifiable — 1 retry, counterfactual, confounded by failure mode (genuine vs injected)

## 5. Confidence-at-failure distribution (the signal)

| population | n (non-null) | min | max | mean | median |
|---|---|---|---|---|---|
| wired_failed | 17/24 | 0.0 | 0.8696 | 0.6454 | 0.7551 |
| wired_passed | 96/96 | 0.6515 | 1.0 | 0.9094 | 1.0 |

## 6. Confounds + coverage (disclosed alongside)

- **n=1 retry.** The rescue rate (1/1) has Wilson 95% [0.21, 1.0] — it pins nothing.
- **Scale mismatch.** retry cost ($3.19, a sonnet-5 story attempt) vs rescue value ($0.05, E_x × a flash-scale base defect cost) — the retry is ~69× the harm it avoids; the economics are dominated by the story-attempt cost scale, not the retry decision.
- **Observational, uncontrolled.** The retry was armed only in the E4 grit_retry arm; its one failure (bad_seed_high) was an injected bug, while the no-retry failure (clean × baseline) was a genuine harness failure — different failure modes confound the comparison.
- **Confidence is execution-confidence, not correctness.** high confidence (0.85) did not prevent the injected-bug failure; the [H] field measures tool-execution smoothness.
