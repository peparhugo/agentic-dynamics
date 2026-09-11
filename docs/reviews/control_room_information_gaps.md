---
status: accepted
---

# Control Room — information gaps (campaign phase d2)

**Date:** 2026-09-11
**Workflow:** `workflows/repository/control_room_rules_design.yaml`, phase `d2_information_gaps`.
**Input:** `experiments/control_room_rules/rule_map.json` (d1) — every `missing_record_fields`
item the room cannot show today.
**Machine artifact:** `experiments/control_room_rules/information_gaps.json` (schema
`control_room_information_gaps/v1`) — the canonical gap inventory; this document renders and
reasons over it.
**Hard rule 3:** *records the backend does not emit are gaps, not assumptions.*

Each gap names **the missing data**, **where it should come from** (a real plane in this repo, or
the literal `NONE`), the **granularity** (per attempt/step/job/model/task/session/run/arm/campaign),
and the **update cadence**. The workflow-management records are listed explicitly.

## Why items are missing — five classes

| class | meaning | examples |
|-------|---------|----------|
| `not-exposed` | the backend **already emits** the field; the room simply has no projection | `test_executed_success`, `first_pass`, answer/explanation tokens, Grit `G(s)` |
| `declared-but-unwritten` | the field is named in `LEDGER_FIELDS` (`experiment_spec.py:330`) but has **no writer** — it *looks* instrumented | `queue_wait_ms`, `service_time_ms`, `due_at`, `forecast_cost`, `evaluator_independent` |
| `no-mechanism` | no producer, schema, or execution path exists at all | `batch_mode`, escalation events, SLA buffer, BVI, human cost |
| `modeled-only` | the value is a calibrated/policy input, never measured | `beta`, `EPM(t)`, `StopSpec.budget_usd` as ceiling, `T_max` |
| `coverage` | the signal exists but its per-task/per-model coverage is not shown | first-pass coverage |

The distinction is load-bearing: **`not-exposed` gaps are cheap** (add a read projection) while
**`declared-but-unwritten` and `no-mechanism` gaps require new writers/mechanisms** — and the
declaration must not be mistaken for instrumentation.

## Counts

- **42 gaps** total; **24** are workflow-management gaps.
- By class: `not-exposed` 14 · `no-mechanism` 14 · `declared-but-unwritten` 9 · `modeled-only` 4 ·
  `coverage` 1.
- By source plane: ledger 6 · job/attempt table 4 · lease/settlement 3 · queue 3 · control packet
  3 · run ledger 3 · measurement rule 5 · website/lab 5 · **none 9**.

## Workflow-management records (explicit)

The task names seven record families; all are present, plus per-job state and the cost split.

| record | gaps | what exists today | where it should come from |
|--------|------|-------------------|---------------------------|
| **job state** | G-39 | queue counts + `control_db.runs.state`; no per-job state row in the room | queue (`worker.py` status writes; `monitor.py:29`) + control-packet |
| **attempt number / retries** | G-15, G-16 | `step_attempts.attempt_no` (per step); `sessions.parquet retries`; not on the room run/attempt row | job/attempt table + run ledger |
| **step timings** | G-30, G-31, G-40 | `step_attempts.started_at/ended_at`; `queue_wait_ms`/`service_time_ms`/`first_token_at`/`leased_at` declared, **no writer** | job/attempt table + queue |
| **escalations (from/to/reason)** | G-27, G-28 | declared `experiment_spec.py:365-366`; `workflow_runner.py:528-529` always `None`; **no mechanism** | ledger |
| **queue wait** | G-30 | `worker.py:391,434` computes elapsed but only **logs** it (never persisted) | queue |
| **batch flags** | G-19, G-20, G-21 | **NONE**; `aggregate_workflow_metrics.py:538` hard-codes batch not-measurable | none |
| **budget fields** | G-22, G-23, G-24, G-25, G-26, G-41 | lease hard cap + settlement emitted; `StopSpec.budget_usd`/`forecast_cost`/`job.budget` unenforced or unwritten | lease/settlement + control-packet |
| **SLA fields** | G-32, G-33, G-34 | `due_at`/`deadline_slack` declared, no writer; aggregate breach rate only | ledger + queue |

## Gaps by rule

### Rule 1 — Grit (augmented)
| ID | missing data | source of truth | granularity | cadence | class |
|----|--------------|-----------------|-------------|---------|-------|
| G-01 | `G(s)` per model × strength + CI | ledger fields → `canonical_corpus` → `lab_grit.py:277`; needs a room projection | model × strength | on-demand | not-exposed |
| G-02 | `perturbation_strength` + operator per attempt | `experiment_spec.py:409`; `ledger_ingestion.py:180-181`; `perturb.py:599-667` | attempt | attempt-end | not-exposed |
| G-03 | `test_executed_success` on the room attempt row | `test_runner.py:151-153` / `verify_tests.py:71-73` → `step_attempts` | attempt/step | attempt-end | not-exposed |

### Rule 2 — Explanation Tax (augmented)
| ID | missing data | source of truth | granularity | cadence | class |
|----|--------------|-----------------|-------------|---------|-------|
| G-04 | answer/explanation token split in the room | `opencode.py:720-724`; `experiment_spec.py:385-386`; run-ledger `PhaseResult.tokens` | attempt/step | attempt-end | not-exposed |
| G-05 | named flail field / flail rate | derive from `sessions.parquet code_lines/files_changed` (`sync_data.py:75,82`); no field | session/model | on-demand | no-mechanism |
| G-06 | per-model narration penalty (currently `null`) | `data.js models[].narration_rate`; `build_data.py:572-712` | model | run-close | not-exposed |

### Rule 3 — Snowball (augmented)
| ID | missing data | source of truth | granularity | cadence | class |
|----|--------------|-----------------|-------------|---------|-------|
| G-07 | per-session cost arc + snowball factor | `lab_story_arc.py:139-150`; `sessions.parquet` | session/story | on-demand | not-exposed |
| G-08 | velocity `v` (code_lines/session) | `sessions.parquet code_lines` (`sync_data.py:82`) | session/model | on-demand | not-exposed |
| G-09 | `beta` provenance (calibrated vs measured) | `data.js design_parameters.beta`; no ledger field | codebase/campaign | static | modeled-only |
| G-10 | one-way-door architecture decision marker | decision records (`control_db.py:936`; `decision_record.py`); no field | run/campaign | event | no-mechanism |

### Rule 4 — EPM Horizon (augmented)
| ID | missing data | source of truth | granularity | cadence | class |
|----|--------------|-----------------|-------------|---------|-------|
| G-11 | `EPM(t)` scenario + rate in the room | `data.js design_parameters.epm_baseline/aggressive` | campaign | static | modeled-only |
| G-12 | measured energy cost per session | `efficiency.py:30-31,269-278`; not in ledger/parquet | session/attempt | attempt-end | no-mechanism |
| G-13 | provider/region split + flip-year alert | NONE (needs region field + comparison rule) | provider/region | per-campaign | no-mechanism |

### Rule 5 — First-Pass (augmented)
| ID | missing data | source of truth | granularity | cadence | class |
|----|--------------|-----------------|-------------|---------|-------|
| G-14 | `evaluator_independent` (declared, no writer) | `experiment_spec.py:380`; must write at the verify seam | attempt | attempt-end | declared-but-unwritten |
| G-15 | `first_pass`/`accepted` on the room row | run ledger `workflow_runner.py:2793-2796`; `step_attempts` lacks it | attempt/run | attempt-end | not-exposed |
| G-16 | attempt chain (`attempt_number`, parent, `retry_reason`) | `experiment_spec.py:362-364`; `workflow_runner` writes blanks | attempt | attempt-end | not-exposed |
| G-17 | cost-per-accepted-outcome | accepted + settlement; only `cap_2b.cpvo_usd` exists | run/model/task | run-close | not-exposed |
| G-18 | per-task/per-model first-pass coverage | `canonical_corpus.resolve_findings`; no projection | task/model | on-demand | coverage |

### Rule 6 — Batch Discount (autonomous)
| ID | missing data | source of truth | granularity | cadence | class |
|----|--------------|-----------------|-------------|---------|-------|
| G-19 | `batch_mode` flag on jobs | NONE; add to `enqueue.py build_cells:125` + ledger | job | enqueue | no-mechanism |
| G-20 | batch vs on-demand cost accounting / an arm | NONE; `efficiency.py:104` comment; `generate_manifest.py:396` | job/model | run-close | no-mechanism |
| G-21 | batch fraction + queue depth/horizon | `aggregate_workflow_metrics.py:536-538` not-measurable | campaign/fleet | per-campaign | no-mechanism |

### Rule 7 — Budget Ceiling (autonomous)
| ID | missing data | source of truth | granularity | cadence | class |
|----|--------------|-----------------|-------------|---------|-------|
| G-22 | `StopSpec.budget_usd` enforcement + surface | `experiment_spec.py:606`; admission → `runs.cost_usd` | run/campaign | event | modeled-only |
| G-23 | `forecast_cost`/`forecast_latency` (no writer) | `experiment_spec.py:339-340`; enqueue + settlement | job | enqueue | declared-but-unwritten |
| G-24 | per-job actual vs budget | lease + `settlement.py:100-142` + `settlements.jsonl` | job/run | run-close | declared-but-unwritten |
| G-25 | `T_max` throughput projection | lease cap + retry rate; formula not computed | fleet/campaign | per-campaign | modeled-only |
| G-26 | cap-raise decision record at rest | `run_workflow.py:308` cap + decision record | campaign | event | no-mechanism |

### Rule 8 — Cascade (autonomous)
| ID | missing data | source of truth | granularity | cadence | class |
|----|--------------|-----------------|-------------|---------|-------|
| G-27 | escalation events (from/to/reason) + armed arm | `experiment_spec.py:365-366`; `workflow_runner.py:528-529` None; proposal-only | attempt | event | no-mechanism |
| G-28 | escalated-attempt cost | NONE; needs a per-tier cost field | attempt/tier | attempt-end | no-mechanism |
| G-29 | escalation rate per tier + human counter | `aggregate_workflow_metrics.py:64-73` (cascade not run) | tier/task | per-campaign | no-mechanism |

### Rule 9 — SLA Buffer (autonomous)
| ID | missing data | source of truth | granularity | cadence | class |
|----|--------------|-----------------|-------------|---------|-------|
| G-30 | `queue_wait_ms` (no writer) | `experiment_spec.py:373`; `worker.py:391,434` logs only | job/attempt | attempt-end | declared-but-unwritten |
| G-31 | `service_time_ms` (no writer) | `experiment_spec.py:374`; `step_attempts` start/end raw | attempt/step | attempt-end | declared-but-unwritten |
| G-32 | `due_at`/`deadline_slack` (no writer) | `experiment_spec.py:338,342`; `control/facts.py:210,584` | job | enqueue | declared-but-unwritten |
| G-33 | per-job SLA buffer/horizon | NONE; needs SLA definition + arithmetic | job/batch | poll:30s | no-mechanism |
| G-34 | live burn + completion-time trace | queue `story_status` + `duration_s`; parity marks unknown | fleet/queue | poll:15s | not-exposed |

### Rule 10 — Outcome Multiplier (value)
| ID | missing data | source of truth | granularity | cadence | class |
|----|--------------|-----------------|-------------|---------|-------|
| G-35 | accepted-outcome count per run/arm | `experiment_spec.py:379`; `verdicts.cap_2b`; `runs` lacks an outcome count | run/arm/model | run-close | not-exposed |
| G-36 | human-cost `H` input in the room | NONE; modeled `data.js calculator` input | campaign/org | static | modeled-only |
| G-37 | BVI / outcomes-per-dollar | NONE; formula `WOC/(C_job + H/W)`; no computation | arm/campaign | per-campaign | no-mechanism |
| G-38 | arm-comparison (compare phase) surface | `compile_experiment.compare_arms`; `decision_arm_comparison.py`; no endpoint | arm/task | per-campaign | not-exposed |
| G-42 | `reuse_value` (declared, no writer) | `experiment_spec.py:406`; `lab_cache_economics.py` is the closest signal | attempt/model | attempt-end | declared-but-unwritten |

### Cross-rule workflow management
| ID | missing data | source of truth | granularity | cadence | class |
|----|--------------|-----------------|-------------|---------|-------|
| G-39 | per-job state in the room | queue `story_status` + `control_db.runs.state`/`run_transitions` | job | event | not-exposed |
| G-40 | `first_token_at` + unified per-step timing | `experiment_spec.py:368-374`; `parity.js:458-471` marks unknown | step/attempt | attempt-end | declared-but-unwritten |
| G-41 | `cost_inference`/`cost_orchestration` (no writer) | `experiment_spec.py:387-388`; `efficiency.py` computes components | attempt | attempt-end | declared-but-unwritten |

## The nine `NONE` gaps (no producer exists)

These are the true build items — a room projection cannot close them:

```
G-05  flail field                  (derive or add to schema)
G-13  provider/region energy split + flip-year alert
G-19  batch_mode flag              (add to enqueue + ledger)
G-20  batch vs on-demand accounting / arm
G-21  batch fraction measurement
G-28  escalated-attempt cost
G-33  per-job SLA buffer/horizon
G-36  human-cost H input (room)
G-37  BVI / outcomes-per-dollar
```

## Acceptance (d2)

- Every d1 `missing_record_fields` item maps to at least one gap (`rule_map.json` →
  `information_gaps.json`).
- All seven required workflow-management record families are present in
  `workflow_management_records`, plus per-job state and the cost split.
- Every gap names a real `file:line`/table/endpoint or the literal `NONE`; no measured signal is
  listed as a gap unless its **room projection** is missing.
- Machine artifact: `experiments/control_room_rules/information_gaps.json` (`gap_count` 42).
