---
status: accepted
---

# Control Room — backend requirements spec (campaign phase d3)

**Date:** 2026-09-11
**Workflow:** `workflows/repository/control_room_rules_design.yaml`, phase `d3_backend_requirements`.
**Input:** `experiments/control_room_rules/information_gaps.json` (d2, `control_room_information_gaps/v1`).
**Rule-map:** `experiments/control_room_rules/rule_map.json` (d1).
**Companion render:** `docs/reviews/control_room_information_gaps.md` (d2).
**Implementation gate:** **BLOCKED** until the controller signs
`approvals/control_room_rules_design/d5_controller_checkpoint_approval.md`. This document is a
requirements spec, not an implementation.

## 1. Purpose and method

d2 established **42 gaps**: evidence/decision items the room cannot show today. d3 turns each gap
into a concrete backend requirement with four things:

1. **the source of truth in this repo** (where the value comes from);
2. the **projection/query to add** (name, inputs, fields, cadence);
3. the **API shape** — **read-only** (new GET routes only; no new POST/mutation routes);
4. the **acceptance test** (deterministic, fixture-driven).

Two design rules govern everything below.

- **Derive, never duplicate.** A projection is a **read model** over existing durable planes. If a
  value is already emitted, the projection *reads* it; we do not re-derive or re-store it. §2 is
  the explicit "do not rebuild" list.
- **Unknown is not zero.** Every projected field carries a provenance/`unknown` state. A field
  whose writer does not exist must render as `"unknown"` with a reason — never `0`, never absent.
  This is the room-level expression of `core.cost_provenance`'s *"an unknown cost is never free"*.

The 42 gaps reduce to **11 read projections**. Many gaps share a projection; every gap maps to at
least one (§6). Some projections can be built over existing data immediately; others depend on a
**new writer/producer** that must land first (§7). The separation matters: `not-exposed` gaps need
only a read model; `declared-but-unwritten` and `no-mechanism` gaps need producers, which are part
of the blocked implementation.

## 2. Already emitted — DO NOT rebuild

The projection layer must consume these surfaces, never re-implement them.

| surface | location | what it already carries |
|---------|----------|-------------------------|
| **control packet** `control-status/v1` | `src/agentic_dynamics/control/control_status.py:build_packet` | `active_runs` (run_id, spec_name, state, candidate_sha, model, started_at, phases_completed/phases_total), `awaiting_approvals`, `promotable_runs`, `failed_runs`, `unhealthy_workers`, `projection_lag`, `safe_actions`, `control_epoch`, `degraded` |
| **control DB** | `src/agentic_dynamics/control/control_db.py` | `runs` (:849: state, model, started_at, ended_at, cost_usd, candidate_sha), `step_attempts` (:899: attempt_no, model, state, started_at, ended_at, tokens, cost_usd, exit_code, error), `run_transitions` (:885), `gate_results` (:920), `approvals` (:936), `promotions` (:951), `run_heartbeats` (:875) |
| **ledger fields** | `experiment_spec.py:330` `LEDGER_FIELDS` | emitted: `attempt_number`, `accepted`, `first_pass`, `test_executed_success`, `perturbation_strength`, `confidence`, `tokens_answer`, `tokens_explanation`, `cost_source`, `reported_cost_usd`, `settled_cost_usd`, `settlement_status` |
| **run ledgers** | `experiments/results/workflows/<spec>/*.json`; `WorkflowRunResult.attempts` (`workflow_runner.py:474-482`, `AttemptRecord:496-556`) | per-phase attempt rows + `total_cost_usd` |
| **lease / admission** | `control/lease_registry.py:431-448,882`; `control/admission.py:486,573-576` | `hard_cap_usd`, `reserved_cost_usd`, `expires_at`, `cost_source`, provider class |
| **settlement** | `control/settlement.py:100-142`; `experiments/results/settlement/settlements.jsonl` | `matched/overspent/underspent/unsettled`, observed vs reserved |
| **queue counts** | `scripts/monitor.py:28-30,58-96`; `control/pipeline_status.py:61-73` | per-stage counts/status, `story_status`, `story_results` |
| **canonical corpus** | `reporting/canonical_corpus.py:889` `load_canonical_tables` (the one input door) | the registry-resolved story/analysis/review/finding rows |
| **lab-derived metrics** | `scripts/lab_grit.py:277`, `scripts/lab_story_arc.py:139-150` | `grit_overall`, `snowball_factor`, session costs |
| **supervisor rail** | `control/supervisor.py:15-19`; `scripts/supervise.py:49,239`; `control/quarantine.py` | flags (`at/session_id/title/model/status/why`), quarantine records |

**Do not rebuild** means: `workflow_records` (§4) reads the control DB + queue + settlement; it
does not create a second job table. `attempt_evidence` (§5 P2) reads the run ledger + ledger
fields; it does not recompute `test_executed_success`. `model_quality` (§5 P3) calls
`canonical_corpus.load_canonical_tables` and reuses `lab_grit`'s metric definition.

## 3. The projection layer — where the code goes

Following the existing read-model pattern (`control/control_status.py`, `control/projection_watermarks.py`,
`control/pipeline_status.py`):

- **pure derivations** live in a new package `src/agentic_dynamics/control/projections/`
  (tier 2; it may read tier-0/1 planes including `reporting`), one module per projection, each
  exposing `build_<name>(deps, *, now, ...) -> dict` with **injected** clock/DB/Redis (deterministic
  for a fixed fixture — same contract as `build_packet`).
- **thin route shells** live in new modules under `apps/control_room/routes/`, each exposing
  `register(app, services)` exactly like `routes/glance.py`.
- **read-only by construction**: routes are `GET` only. No projection writes to Redis, the control
  DB, or the KB. The one exception is the existing projector-owned watermark row
  (`projection_watermarks`), which is not touched here.
- **provenance is part of the payload**: every block carries an `evidence`/`unknown` marker and a
  `generated_at` + `control_epoch` so a snapshot is never mistaken for live state.

## 4. The single `workflow_records` projection (P1)

> **The one projection the room consumes for workflow management.** It bundles jobs, attempts, and
> steps with **timings, retries, escalations, queue waits, batch flags, and budget/SLA fields**
> (the d2 workflow-management requirement).

**Module:** `src/agentic_dynamics/control/projections/workflow_records.py`
**Route:** `apps/control_room/routes/workflow_records.py`

### Inputs (read-only)

- Redis queue: `story_jobs` / `story_status` / `story_results` and the job JSON from
  `scripts/enqueue.py:125` (+ admission fields `:221-225`).
- Control DB: `runs`, `step_attempts`, `run_transitions`, `gate_results`, `approvals`, `promotions`
  (`control_db.py:842-961`).
- Run ledgers: `experiments/results/workflows/<spec>/*.json` (`workflow_runner.AttemptRecord`).
- Lease/settlement: `control/lease_registry.py`, `control/settlement.py`, `settlements.jsonl`.
- Control packet (`build_packet`) for `safe_actions` and the run state (composed, not re-derived).

### Fields (per job)

| field | granularity | source | class | writer exists? |
|-------|-------------|--------|-------|----------------|
| `job_id`, `cell_id`, `run_id`, `spec_name`, `candidate_sha` | job | queue JSON + `runs` | M | yes |
| `model`, `provider`, `condition`, `tier` | job | queue JSON | M | yes |
| `state` (`queued\|leased\|running\|accepted\|failed\|dead_letter`) | job | `story_status` + `runs.state` | M | yes |
| `attempt_count`, `attempt_no`, `retry_count`, `retry_reason` | job/attempt | run ledger + `step_attempts.attempt_no` | M | partial (retry_reason: new writer G-16) |
| `queued_at`, `leased_at`, `started_at`, `first_token_at`, `ended_at` | job/step | queue + `step_attempts` | M | partial (leased/first_token: G-40) |
| `queue_wait_ms`, `service_time_ms`, `total_duration_ms` | job/attempt | worker + `step_attempts.started/ended` | M | **new writer (G-30, G-31)** |
| `escalation_from`, `escalation_to`, `escalation_reason` | attempt | run ledger | M | **new writer (G-27)** |
| `batch_mode` | job | enqueue | M | **new writer (G-19)** |
| `budget` (declared), `hard_cap_usd`, `actual_cost`, `cost_source`, `settlement_status` | job | `StopSpec` + lease + settlement | M/P | partial (budget/forecast: G-22, G-23, G-24) |
| `due_at`, `deadline_slack`, `sla_horizon`, `sla_breach` | job | enqueue + queue | P/C | **new writer (G-32, G-33)** |
| `phases_completed`, `phases_total` | run | control packet | M | yes |
| `last_transition` (`from_state`,`to_state`,`at`,`reason`,`actor`) | run | `run_transitions` | M | yes |
| `evidence` (`measured`/`unknown` per field) | — | derived | — | yes |

Nested `attempts[]` each carry: `attempt_id`, `attempt_no`, `parent_attempt_id`, `step_id`,
`model`, `state`, `started_at`, `ended_at`, `duration_ms`, `tokens`, `cost_usd`, `cost_source`,
`exit_code`, `error`, `test_executed_success`, `confidence`, `perturbation_strength`, `first_pass`,
`accepted`, `evaluator_independent`, `answer_tokens`, `explanation_tokens`, `cost_inference`,
`cost_orchestration`, `reuse_value`.

### API shape (read-only)

```
GET /api/workflow-records?spec=<name>&state=<state>&model=<id>&limit=<n>&cursor=<token>
  -> { "schema": "workflow-records/v1", "generated_at": "...", "control_epoch": <int>,
       "source": "control_room:/api/workflow-records", "total": <int>, "truncated": <bool>,
       "jobs": [ { <job fields>, "attempts": [ ... ] } ] }

GET /api/workflow-records/<job_id>
  -> { "schema": "workflow-records/v1", "job": { ... }, "attempts": [ ... ],
       "transitions": [ ... ], "evidence": { ... } }
  -> 404 { "error": "not_found" } when the job is unknown (never an empty 200)
```

### Cadence

- `event`: a run transition or attempt end updates the row; the room follows `GET /api/events`
  (SSE) for transitions.
- `poll:15s`: fallback recompute for queue fields that have no event.
- `generated_at` + `control_epoch` are always present; a stale read is visible, not hidden.

### Acceptance test

`tests/test_control_room_workflow_records.py` (new, `fast`-marked):
given a fixture control DB + queue snapshot + run ledger, `GET /api/workflow-records` returns the
expected jobs in a total order; a job missing a timing/scalar writer renders that field as
`{"state":"unknown","reason":"no_writer"}` and **never** `0`; `state` matches the control-packet
run state; every field carries an `evidence` class; the route table contains no `POST` for this
path.

## 5. Projection catalog (P2–P11)

Each entry: purpose · gaps served · source of truth · API · cadence · writer dependency ·
acceptance. All routes are read-only `GET`.

### P2 — `attempt_evidence` (the per-attempt causal ladder)
- **Gaps:** G-02, G-03, G-04, G-12, G-14, G-15, G-16, G-31, G-41, G-42.
- **Source of truth:** run ledgers (`workflow_runner.AttemptRecord`), ledger fields
  (`experiment_spec.py:385-410`), writers `test_runner.py:151-153`, `verify_tests.py:71-73`,
  `opencode.py:720-724`; `step_attempts` for timing.
- **API:** `GET /api/runs/<run_id>/attempts` → `{schema:"attempt-evidence/v1", run_id, attempts:[{...ledger fields..., evidence:{...}}]}`.
- **Cadence:** `attempt-end`; refreshed on `GET /api/events` transition.
- **Writer dependency:** `evaluator_independent` (G-14), energy (G-12), `first_token_at` (G-40),
  `cost_inference/orchestration` (G-41), `reuse_value` (G-42); the rest are already emitted.
- **Acceptance:** `tests/test_control_room_attempt_evidence.py` — given a fixture attempt, all
  measured fields resolve; unwritten fields render `unknown`; no narration field is substituted for
  the independent test verdict.

### P3 — `model_quality` (Grit + first-pass + narration + coverage)
- **Gaps:** G-01, G-05, G-06, G-18.
- **Source of truth:** `canonical_corpus.load_canonical_tables` (`reporting/canonical_corpus.py:889`);
  metric definitions reused from `scripts/lab_grit.py:75,277`; token split from the ledger.
- **API:** `GET /api/quality?model=<id>&task=<type>` → `{schema:"model-quality/v1", models:[{model, grit:{by_strength[],ci}, first_pass:{rate,coverage}, flail, narration:{rate,penalty}, evidence}]}`.
- **Cadence:** `on-demand` (recomputed from current canonical rows).
- **Writer dependency:** flail field (G-05) is derived or added to the schema; everything else is
  computable now.
- **Acceptance:** `tests/test_control_room_model_quality.py` — Grit matches `lab_grit`'s definition
  for a fixed fixture; coverage is reported before any ratio; a null narration field stays `unknown`.

### P4 — `story_arc` (Snowball)
- **Gaps:** G-07, G-08, G-09.
- **Source of truth:** `sessions.parquet`/`stories.parquet` (`scripts/sync_data.py:49-112`);
  `scripts/lab_story_arc.py:139-150`; `design_parameters.beta`.
- **API:** `GET /api/stories/<name>/arc` → `{schema:"story-arc/v1", story, sessions:[{session_number,cost_usd,code_lines}], snowball_factor, velocity, beta:{value,class:"P",source}}`.
- **Cadence:** `on-demand`.
- **Writer dependency:** none (β's provenance label is the only addition).
- **Acceptance:** `tests/test_control_room_story_arc.py` — the arc is ordered by session number; the
  snowball factor equals S5/S1; β is labeled `[P]`.

### P5 — `run_value` (Outcome Multiplier / BVI)
- **Gaps:** G-17, G-35, G-37.
- **Source of truth:** `accepted` (`experiment_spec.py:379`) + cost (`control/settlement.py`,
  `runs.cost_usd`); `data.js verdicts.cap_2b` for the only current instance.
- **API:** `GET /api/value?run=<id>&arm=<name>` → `{schema:"run-value/v1", rows:[{run,arm,accepted_outcomes,total_cost,cost_per_accepted,bvi:{value,class,inputs}}]}`.
- **Cadence:** `run-close` / `per-campaign`.
- **Writer dependency:** human cost `H` (G-36) and BVI computation (G-37) are new; accepted/cost
  exist.
- **Acceptance:** `tests/test_control_room_run_value.py` — cost-per-accepted-outcome equals
  accepted/cost for a fixture; BVI is present only when `H` and `W` are set, else `unknown`.

### P6 — `arm_comparison` (compare/adapt stage)
- **Gaps:** G-38.
- **Source of truth:** `experiment/compile_experiment.py compare_arms`;
  `scripts/decision_arm_comparison.py` (already computes it; no endpoint).
- **API:** `GET /api/arms/compare?spec=<name>` → `{schema:"arm-comparison/v1", arm_factor, arms:[{arm,loss,decisions}]}`.
- **Cadence:** `per-campaign`.
- **Writer dependency:** none — expose the existing derivation.
- **Acceptance:** `tests/test_control_room_arm_comparison.py` — the same `compare_arms` output the
  script produces is served; a single-arm spec returns a named empty state, not an error.

### P7 — `spend_budget` (Budget Ceiling + EPM + energy + human cost)
- **Gaps:** G-09, G-11, G-13, G-22, G-24, G-25, G-26, G-36.
- **Source of truth:** lease/admission (`lease_registry.py:431-448,882`), settlement
  (`settlement.py:100-142`), `StopSpec.budget_usd` (`experiment_spec.py:606`), `data.js`
  `design_parameters.epm_baseline/aggressive`, `calculator` human-cost input.
- **API:** extend `GET /api/subscription-usage` with a `budget` block (or add
  `GET /api/spend`) → `{schema:"spend-budget/v1", spend, hard_cap, headroom, reserved, settlement_stats, t_max:{value,class}, epm:{rate,class:"P"}, human_cost:{h,class:"P"}, evidence}`.
- **Cadence:** `poll:15s` for spend/headroom; `per-campaign` for `t_max`/EPM.
- **Writer dependency:** budget enforcement (G-22), forecast/reconcile (G-23/G-24), cap-raise record
  (G-26), human cost (G-36); spend/headroom/leases/settlement already emitted.
- **Acceptance:** `tests/test_control_room_spend_budget.py` — an unknown cost renders
  `{"state":"unknown"}` and never `$0.00`; headroom = cap − outstanding; `t_max` shows its inputs.

### P8 — `sla_queue` (SLA Buffer + live burn)
- **Gaps:** G-30, G-32, G-33, G-34.
- **Source of truth:** queue counts (`pipeline_status.py:61-73`, `monitor.py`),
  `worker.py:391,434` elapsed (currently logged only), `step_attempts` start/end, aggregate breach
  rate (`aggregate_workflow_metrics.py:706-748`).
- **API:** `GET /api/queue/sla?window=<n>` → `{schema:"sla-queue/v1", depth, burn, completion_trace:[...], sla:{horizon,breach_rate,class}, per_job:[{job_id,queue_wait_ms,service_time_ms,due_at,deadline_slack}]}`.
- **Cadence:** `poll:15s`.
- **Writer dependency:** `queue_wait_ms` (G-30), `due_at`/`deadline_slack` (G-32), SLA buffer
  (G-33), completion trace (G-34); the queue-count half is already emitted.
- **Acceptance:** `tests/test_control_room_sla_queue.py` — queue_wait/service render `unknown` until
  the writer lands; the 2× queue-depth rule is computed from measured values only; no fabricated
  timing.

### P9 — `escalation_cascade` (Cascade Rule)
- **Gaps:** G-27, G-28, G-29.
- **Source of truth:** `experiment_spec.py:365-366` (declared), `workflow_runner.py:528-529`
  (currently `None`), `data.js verdicts.escalation` E_x, `aggregate_workflow_metrics.py:64-73`.
- **API:** `GET /api/escalations?spec=<name>` → `{schema:"escalation-cascade/v1", events:[{from,to,reason,cost}], rate_by_tier, human_rate, armed:false, note}`.
- **Cadence:** `event` / `per-campaign`.
- **Writer dependency:** the escalation mechanism itself (G-27), escalated cost (G-28), rate metric
  (G-29). Until then the projection returns `armed:false` + the E_x reference.
- **Acceptance:** `tests/test_control_room_escalation.py` — with no cascade armed the projection
  says so explicitly and never invents events; E_x is labeled `[C]/[X]`.

### P10 — `batch` (Batch Discount)
- **Gaps:** G-20, G-21.
- **Source of truth:** **NONE**; `aggregate_workflow_metrics.py:536-538` hard-codes
  not-measurable; `generate_manifest.py:396` records batch unexecuted.
- **API:** `GET /api/batch` → `{schema:"batch/v1", measurable:false, reason:"no batch_mode marker", modeled:{discount:0.5,horizon_h:72,class:"X/P"}}`.
- **Cadence:** `per-campaign`.
- **Writer dependency:** batch mode/accounting/fraction (G-19, G-20, G-21).
- **Acceptance:** `tests/test_control_room_batch.py` — the endpoint returns `measurable:false` with
  the missing-record reason, never a fabricated fraction.

### P11 — `decision_ledger` (architecture + cap decisions)
- **Gaps:** G-10, G-26.
- **Source of truth:** decision records (`scripts/decision_record.py`;
  `approvals`/`promotions` in `control_db.py:936,951`), cap change at `run_workflow.py:308`.
- **API:** `GET /api/decisions?category=<one_way_door|cap_raise>` → `{schema:"decision-ledger/v1", decisions:[{category,decided_at,actor,artifact,run_id,candidate_sha}]}`.
- **Cadence:** `event`.
- **Writer dependency:** a decision record must be written on a cap change (G-26) and for a
  one-way-door architecture choice (G-10).
- **Acceptance:** `tests/test_control_room_decisions.py` — a cap change has an attributed decision
  record; an absent record is shown as missing, not assumed.

## 6. Gap → projection → writer → acceptance

All 42 d2 gaps. `W` = a new writer/producer is required (blocked); `read` = the projection is a
read model over already-emitted data.

| gap | decision it unblocks | projection | writer | acceptance test |
|-----|----------------------|------------|--------|-----------------|
| G-01 | model trust under perturbation | P3 model_quality | read | test_control_room_model_quality |
| G-02 | attribute run to perturbation | P2 attempt_evidence | read | test_control_room_attempt_evidence |
| G-03 | trust independent verdict | P2 attempt_evidence | read | test_control_room_attempt_evidence |
| G-04 | narration tax decision | P2 attempt_evidence | read | test_control_room_attempt_evidence |
| G-05 | identify flail sessions | P3 model_quality | W | test_control_room_model_quality |
| G-06 | compare narration overhead | P3 model_quality | read | test_control_room_model_quality |
| G-07 | budget the N² arc | P4 story_arc | read | test_control_room_story_arc |
| G-08 | project compounding | P4 story_arc | read | test_control_room_story_arc |
| G-09 | separate calibrated β | P4/P7 | read | test_control_room_story_arc |
| G-10 | record a one-way door | P11 decision_ledger | W | test_control_room_decisions |
| G-11 | choose energy scenario | P7 spend_budget | read | test_control_room_spend_budget |
| G-12 | measured vs modeled energy | P2 attempt_evidence | W | test_control_room_attempt_evidence |
| G-13 | energy flip year | P7 spend_budget | W | test_control_room_spend_budget |
| G-14 | independent evaluator | P2 attempt_evidence | W | test_control_room_attempt_evidence |
| G-15 | first-pass/accepted in room | P1/P2 | read (ledger) | test_control_room_workflow_records |
| G-16 | attempt chain + retry reason | P1 workflow_records | W (retry_reason) | test_control_room_workflow_records |
| G-17 | cost per accepted outcome | P5 run_value | read | test_control_room_run_value |
| G-18 | first-pass coverage | P3 model_quality | read | test_control_room_model_quality |
| G-19 | batch vs on-demand split | P1 workflow_records | W | test_control_room_workflow_records |
| G-20 | verify batch discount | P10 batch | W | test_control_room_batch |
| G-21 | size batch from depth | P10 batch | W | test_control_room_batch |
| G-22 | budget enforcement visible | P7/P1 | W | test_control_room_spend_budget |
| G-23 | plan spend per job | P1 workflow_records | W | test_control_room_workflow_records |
| G-24 | per-job actual vs budget | P1/P7 | W | test_control_room_workflow_records |
| G-25 | read throughput the cap buys | P7 spend_budget | read | test_control_room_spend_budget |
| G-26 | audit a cap raise | P11 decision_ledger | W | test_control_room_decisions |
| G-27 | escalate a failed attempt | P9 escalation_cascade | W | test_control_room_escalation |
| G-28 | escalation cost | P9 escalation_cascade | W | test_control_room_escalation |
| G-29 | <1% human escalation | P9 escalation_cascade | W | test_control_room_escalation |
| G-30 | queue wait | P1/P8 | W | test_control_room_workflow_records |
| G-31 | service time | P1/P2 | W | test_control_room_workflow_records |
| G-32 | due date / slack | P1/P8 | W | test_control_room_workflow_records |
| G-33 | 2× queue-depth rule | P8 sla_queue | W | test_control_room_sla_queue |
| G-34 | live burn + completion trace | P8 sla_queue | W | test_control_room_sla_queue |
| G-35 | accepted outcomes per run | P5 run_value | read | test_control_room_run_value |
| G-36 | include human cost | P7 spend_budget | W | test_control_room_spend_budget |
| G-37 | outcomes per dollar (BVI) | P5 run_value | W | test_control_room_run_value |
| G-38 | compare arms | P6 arm_comparison | read | test_control_room_arm_comparison |
| G-39 | per-job state | P1 workflow_records | read | test_control_room_workflow_records |
| G-40 | first token / leased timings | P1 workflow_records | W | test_control_room_workflow_records |
| G-41 | inference vs orchestration cost | P1/P2 | W | test_control_room_workflow_records |
| G-42 | value of reuse | P2 attempt_evidence | W | test_control_room_attempt_evidence |

**Coverage:** 42/42 gaps mapped; 15 projections-read gaps and 27 writer-dependent gaps.
Every projection has exactly one acceptance test; the `workflow_records` test covers 9 gaps.

## 7. New writers / producers required (BLOCKED pending the checkpoint)

These cannot be closed by a read projection — they need the producer to exist first. Each is
listed with its target seam and the existing machinery it must reuse.

| gap | field(s) | writer seam (reuse) | note |
|-----|----------|---------------------|------|
| G-05 | `flail` | measurement rule over `sessions.parquet` (`sync_data.py`) | derive, don't invent |
| G-10/G-26 | decision record (architecture/cap) | `scripts/decision_record.py` + `approvals`/`promotions` | P0 act; write at the moment of decision |
| G-12 | energy per session/attempt | `measurement/efficiency.py:269-278` → ledger writer | emit the computed value |
| G-13 | region field | session schema | new dimension |
| G-14 | `evaluator_independent` | `scripts/verify_tests.py` / `runtime/test_runner.py` | declared field, add writer |
| G-16 | `retry_reason`/`parent_attempt_id` | `runtime/workflow_runner.py:2793-2794` | currently blanks |
| G-19/G-20/G-21 | `batch_mode` + accounting + fraction | `scripts/enqueue.py` + a batch executor | no mechanism today |
| G-22/G-23/G-24 | budget enforcement + forecast + reconcile | `control/admission.py` + `control/settlement.py` | declared fields, add writers |
| G-27/G-28/G-29 | escalation events + cost + rate | `control/decisions.py` (act path) | proposal-only today |
| G-30/G-31/G-32/G-33 | `queue_wait_ms`, `service_time_ms`, `due_at`, `deadline_slack`, SLA buffer | `scripts/worker.py:391,434` (persist elapsed) + enqueue + a queue SLA rule | elapsed computed then discarded |
| G-34 | completion trace | queue/`story_status` time-series | new read model over an event log |
| G-36 | human cost `H` | org/campaign config | modeled input |
| G-37 | BVI | computation from P3+P5+P7 | modeled formula |
| G-40 | `first_token_at`, `leased_at` | `runtime/workflow_runner.py` / `scripts/worker.py` | declared, no writer |
| G-41 | `cost_inference`/`cost_orchestration` | `measurement/efficiency.py` → ledger | declared, no writer |
| G-42 | `reuse_value` | `scripts/lab_cache_economics.py` signal → ledger | declared, no writer |

The **declared-but-unwritten** set is the sharpest: after this spec, no project should claim these
fields are instrumented until a writer lands. The projection layer will render them `unknown` with
`reason:"no_writer"` in the meantime — honest gaps, never fabricated zeros.

## 8. API surface (read-only)

| method | path | projection | notes |
|--------|------|------------|-------|
| GET | `/api/workflow-records` | P1 | list + filter |
| GET | `/api/workflow-records/<job_id>` | P1 | detail + attempts + transitions; 404 on unknown |
| GET | `/api/runs/<run_id>/attempts` | P2 | causal ladder |
| GET | `/api/quality` | P3 | Grit/first-pass/narration/coverage |
| GET | `/api/stories/<name>/arc` | P4 | snowball/velocity/β |
| GET | `/api/value` | P5 | outcomes per dollar |
| GET | `/api/arms/compare` | P6 | arm comparison |
| GET | `/api/spend` (or extend `/api/subscription-usage`) | P7 | budget/EPM/human cost |
| GET | `/api/queue/sla` | P8 | queue/wait/burn/SLA |
| GET | `/api/escalations` | P9 | cascade |
| GET | `/api/batch` | P10 | explicit not-measurable |
| GET | `/api/decisions` | P11 | decision ledger |
| GET (SSE) | `/api/events` (extend) | P1/P2/P9 | transition/attempt/escalation frames |

**No new mutation routes.** The existing P0/P1 POST routes
(`/api/flags/<id>/steer|interrupt`, `/api/claude-agents/<id>/*`, `/api/experiments`,
`/api/queue/reinterleave`, `/api/design-sessions/*`, `/api/docs-health/approve`) stay exactly as
they are; the projections are strictly additive reads.

## 9. Acceptance test plan

- **One test module per projection**, named `tests/test_control_room_<projection>.py`, `fast`-marked
  where no external service is needed (the fail-closed pattern in `tests/test_fast_path_gate.py`).
- **Deterministic fixtures**: a fixture control DB (`ControlDB` on a temp path), a queue snapshot
  dict, a run-ledger JSON, and a canonical-corpus subset. The builder takes injected `db`, `redis`,
  and `now` exactly like `build_packet` (`control_status.py:781`) so output is byte-stable for a
  fixed fixture.
- **The three invariants every test asserts**:
  1. **unknown ≠ zero** — a field with no writer renders `{"state":"unknown","reason":"no_writer"}`;
  2. **coverage before ratio** — any ratio (Grit, first-pass, batch fraction) reports its
     numerator/denominator coverage first, and a zero denominator yields `unknown`, not `0.0`;
  3. **read-only** — the registered route methods are all `GET` for these paths, and a projection
     run leaves the control DB's `control_epoch` unchanged.
- **Provenance**: every block carries an evidence class (`[M]/[C]/[P]/[X]`); a test fails if a
  `[P]`/`[X]` value is rendered without its class.

## 10. Implementation gate

Per the workflow hard rule 5 and the repo's P0 authority: **no implementation wave may start until
the controller signs
`approvals/control_room_rules_design/d5_controller_checkpoint_approval.md`.** This spec, the
wireframe (`docs/research/control_room_wireframe.md`, d4), and the review packet
(`docs/reviews/control_room_design_review.md`, d5) are the artifacts the controller signs.

**What can be built immediately after approval (read-only, no new producers):** P1's state/attempt
halves, P2's emitted fields, P3, P4, P5's emitted halves, P6, and the queue-count half of P8.
**What needs a producer first:** every `W` row in §6/§7 — the workflow-management records the
mandate requires and the d0–d2 chain proved are missing.
