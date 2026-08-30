# β coordination-tax instrument — corpus measurement

schema `coordination_overhead/v1` · generated 2026-08-30T18:25:54Z

formula: `coordination_overhead = (wrapper + merge + chain + review) / cell`

wrapper/cell are measured USD from phase-ledger total_measured_cost_breakdown; merge/chain/review are event counts (a different unit), reported separately, never blended into the cost ratio (design §6: measured, never blended).

## Per-campaign β curve

| campaign | cell (USD) | wrapper (USD) | β (wrapper/cell) | wrapper share | merge | chain | review |
|---|---|---|---|---|---|---|---|
| cap_2a_rerun | 0.00355972 | 0.00501877 | 1.410 | 58.5% | 3 | 1 | 6 |
| cap_2a_rerun2 | 0.00631081 | 0.00656464 | 1.040 | 51.0% | 1 | 0 | 2 |
| cap_2a_rerun3 | 0.00745457 | 0.009504 | 1.275 | 56.0% | 1 | 1 | 2 |
| cap_2a_shadow_calibration | 0.001164 | 0.201238 | 172.885 | 99.4% | 1 | 0 | 2 |
| cap_2b | 0.00359464 | 0.00518659 | 1.443 | 59.1% | 1 | 1 | 2 |
| cap_adaptive_2c | 0.01585328 | 0.0 | 0.000 | 0.0% | 1 | 1 | 2 |

## The 2b prior re-derivation

- prior: wrapper share **63%** ($0.17 of $0.27)
- re-derived from the one 2b phase ledger on disk: share 0.590645
- verdict: **directionally_confirmed_not_numerically_reproduced**
