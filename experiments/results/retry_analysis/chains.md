---
status: accepted
---

# Retry chains — p1 extraction (fail → retry → outcome)

**Spec:** `retry_observational_analysis@0.1` · phase `p1_extract_chains` · OBSERVATIONAL (no cells, no grid).

## 1. The complete chains (attempt-ledger plane, with retry linkage)

| # | cell | model | policy arm | first-attempt tes | strength | cost-so-far | [H] confidence @failure | retry | retry reason | retry tes | outcome | chain cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cap_grit_strength_grid_condition_strength_clean_policy_arm_baseline_model_anthropic_claude_sonnet_5 | anthropic/claude-sonnet-5 | baseline | False | 0.0 | $3.5575 | 0.8049 | False | None | — | no-retry-was-taken | $3.5575 |
| 2 | cap_grit_strength_grid_condition_strength_bad_seed_high_policy_arm_grit_retry_model_anthropic_claude_sonnet_5 | anthropic/claude-sonnet-5 | grit_retry | False | 0.8 | $3.6330 | 0.8462 | True | first_attempt_test_failure | True | rescued | $6.8195 |

### Confidence series (the [H] per-session execution-confidence)

- `cap_grit_strength_grid_condition_strength_clean_policy_arm_baseline_model_anthropic_claude_sonnet_5` first attempt sessions: [0.9, 0.7, 0.8947, 0.75, 0.8049] → failure-signal confidence = 0.8049
- `cap_grit_strength_grid_condition_strength_bad_seed_high_policy_arm_grit_retry_model_anthropic_claude_sonnet_5` first attempt sessions: [0.875, 0.65, 0.8667, 0.8125, 0.8462] → failure-signal confidence = 0.8462
  - retry end confidence: 0.9024

## 2. Coverage (exact)

| plane | field | value |
|---|---|---|
| coverage | attempt_ledger_records | 11 |
| coverage | attempt_ledger_failed_first_attempts | 2 |
| coverage | attempt_ledger_retries | 1 |
| coverage | attempt_ledger_complete_chains | 2 |
| coverage | attempt_ledger_coverage_complete_over_failed | 2/2 |
| coverage | attempt_ledger_coverage_complete_over_total | 2/11 |
| coverage | story_files_total | 255 |
| coverage | story_files_wired | 120 |
| coverage | story_files_wired_failed | 24 |
| coverage | story_files_with_retry_linkage | 0 |
| coverage | real_retry_events | 1 |

| source | note |
|---|---|
| attempt ledgers | cap_grit_grid_ledger.json: 9 attempts (8 first, 1 retry, 2 failed-first) |
| attempt ledgers (synthetic) | experiments/results/workflows/ledger_instrumentation_probe/20260830T190548Z.json: 2 attempts, 0 retries (probe — no real chain) |
| story results | 255 files, 120 wired, 24 wired-failed, 21 not-all-successful, 1259 sessions (73 failed) — zero retry linkage |

## 3. Extraction honesty notes

- The E4 ledger attempt rows carry NO `confidence` field; the [H] confidence is recovered by joining `result_path` to the wired story results.
- `failed-first` = attempt_number 1 with test_executed_success false; no imputed outcomes — a retry with a missing test_executed_success is classified `retry-taken-outcome-missing`, never guessed.
- The story runner has no retry mechanism, so the 24 wired-failed stories are first-attempt outcomes, not retry chains (a 'no retry was armed' set).
