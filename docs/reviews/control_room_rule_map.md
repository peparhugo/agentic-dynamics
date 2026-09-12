---
status: accepted
---

# Control Room — 10-rule operator/decision/evidence/record map (campaign phase d1)

**Date:** 2026-09-11
**Workflow:** `workflows/repository/control_room_rules_design.yaml`, phase `d1_rule_decision_map`.
**Frozen mandate:** `docs/research/control_room_rules.md` (the 10 rules + engine chain) and
`docs/research/control_room_rules_sources.md` (pin table).
**Machine artifact:** `experiments/control_room_rules/rule_map.json` (schema
`control_room_rule_map/v1`) — the canonical record; this document renders and reasons over it.
**Hard rules applied:** (1) every design element traces to a rule or an operator job; (2)
measured / computed / modeled evidence is distinguished and the missing class is named; (3)
records the backend does not emit are **gaps, not assumptions**.

This map answers, for each of the 10 rules: the **operator decision** it enables, the **evidence
fields** (from the frozen docs) and their **evidence class**, the **existing backend source** in
this repo (or explicit `NONE`), the **missing record fields**, the **surface**
(rest/drill/alert), the **action**, the **cost of missing**, and an **acceptance walkthrough** the
future render gate can implement.

## How to read the evidence classes

| class | meaning (frozen mandate) |
|-------|--------------------------|
| **M** | measured — observed in the corpus/ledger |
| **C** | computed — derived from measured fields |
| **P** | modeled / policy — calibrated input, WFM theory, or assumption |
| **X** | external — provider pricing, IEA energy projections |

A field declared in `LEDGER_FIELDS` (`src/agentic_dynamics/experiment/experiment_spec.py:330`)
without a writer is **not** a backend source. Those are the load-bearing gaps: the declaration
makes them look instrumented; the absence of a writer makes them unmeasured. Every such field is
listed under `missing_record_fields`.

## The two workforces and the value rule

| group | rules | basis |
|-------|-------|-------|
| **augmented** (human + AI, per session) | 1, 2, 3, 4, 5 | frozen mandate: Rules 1–5 |
| **autonomous** (bounded autonomy, per job) | 6, 7, 8, 9 | frozen mandate: Rules 6–9 |
| **value** (outcomes per dollar) | 10 | frozen mandate: Rule 10 |

## Rule map (summary)

| # | rule | published status | evidence class | primary surface | existing backend source (room level) | operator decision |
|---|------|------------------|----------------|-----------------|--------------------------------------|-------------------|
| 1 | Grit | instrumented [M] | M/C | rest | **none in room** — ledger + `lab_grit` + `data.js` only | which models are safe for unsupervised work |
| 2 | Explanation Tax | instrumented [M] | M/C | drill | **none in room** — token split emitted; narration fields null | pay narration tax or force silent mode |
| 3 | Snowball | proposed [C] | C/P | drill | **none in room** — `lab_story_arc` + `data.js` | commit to a compounding architecture + budget the arc |
| 4 | EPM Horizon | proposed [C] | X/P | drill | **none in room** — `data.js` energy/design params | choose the energy scenario + hedge horizon |
| 5 | First-Pass | instrumented [M] | C | alert | **partial** — `attempt_number`/`accepted` on the ledger; `evaluator_independent` unwritten | retry / escalate / abandon a failed attempt |
| 6 | Batch Discount | proposed [C] | X/P | drill | **NONE** — metric hard-coded not-measurable | batch vs on-demand split |
| 7 | Budget Ceiling | proposed [C] | C/P | rest | **yes** — lease/admission caps + `/api/subscription-usage` + `/api/glance` money | raise/lower the cap; size throughput |
| 8 | Cascade Rule | proposed [C] | X/P | alert | **NONE** — `escalation_from/to` always `None`; no cascade | escalate a failed attempt; bound human escalation |
| 9 | SLA Buffer | proposed [C] | P | alert | **NONE for buffer** — queue counts + aggregate breach rate | set the buffer; never batch under 2× queue depth |
| 10 | Outcome Multiplier | proposed [C] | C/P | rest | **partial** — `verdicts.cap_2b` outcomes+cost; no BVI | keep the value-maximizing arm |

Counts: **3** instrumented `[M]` (rules 1, 2, 5); **7** proposed `[C]` (3, 4, 6, 7, 8, 9, 10);
**0** decided. Exactly **one** rule (7, Budget Ceiling) has a live room surface backed by measured
records. Four rules (1, 2, 5, 10) are measured but **not exposed in the room**. Four (3, 4, 8, 9)
are modeled/external only. Rule 6 is absent entirely.

## Operator's daily loop × rules

The loop is the u0 job set `control_room_ux_foundation.md` §2 (J1–J11); the room-side surface
vocabulary is `control_room_ia.md` §12.

| loop stage | job | rules that inform it | what the operator does there |
|------------|-----|----------------------|------------------------------|
| **glance** | J1 | 1, 2, 5, 7, 10 | read system + run + risk + money + value at rest, no interaction |
| **triage** | J2 | 1, 5, 8, 9 | decide whether a stalled/failed run is retry-worthy |
| **decide** | J3 | 5, 7, 8, 10 | approve / cancel / promote / raise-cap (P0) |
| **inspect** | J4 | 1, 2, 3, 5, 8, 9 | read the attempt-scoped causal ladder + step timings |
| **intervene** | J6 | 8, 9 | steer / interrupt / retry / escalate per worker |
| **budget** | J5 | 3, 4, 6, 7, 10 | spend, burn, quota, lease headroom, scenarios |
| **audit** | J7 | 1, 5, 7, 10 | who decided what, with what authority; recording coverage |

Every loop stage is covered, and every rule appears in at least one stage (`rule_map.json`
`loop_coverage`).

## Per-rule records (rendered from `rule_map.json`)

### Rule 1 — Grit (Ground-Truth Integrity) · instrumented [M] · augmented
- **Decision:** which models may be trusted with unsupervised work at a given perturbation
  strength (default-route to high-Grit; exclude low-Grit).
- **Evidence fields:** `test_executed_success` [M], `perturbation_strength` [M],
  `operator`/`perturbation_class` [M], `model` [M], `G(s)` summary [C].
- **Existing backend source:** ledger `AttemptRecord` fields (declared
  `experiment_spec.py:409-410`; writers `knowledge/ledger_ingestion.py:180-181,264-266`,
  `runtime/test_runner.py:151-153`, `scripts/verify_tests.py:71-73`); derived by
  `scripts/lab_grit.py:277`; published at `apps/website/data.js` `labs.grit`. **No room endpoint.**
- **Missing record fields:** room projection of `test_executed_success` by model/operator;
  `perturbation_strength` coverage; `G(s)` lens; per-attempt operator label in the run sample.
- **Surface:** rest (also alert, drill). **Action:** route on Grit (J9/R4a).
- **Cost of missing:** a low-Grit model stays in unsupervised production and its failure under
  degraded input is invisible.
- **Walkthrough:** R0 (J1) → confirm per-model Grit token → R4c ladder shows the run's measured
  `test_executed_success`. PASS: at-rest Grit signal + per-run measured verdict; FAIL: Grit only
  on the website.

### Rule 2 — Explanation Tax (ε) · instrumented [M] · augmented
- **Decision:** pay the narration tax only where auditability is worth it; force silent mode
  elsewhere.
- **Evidence fields:** `tokens_answer` [M], `tokens_explanation` [M], `thinking_ratio` [C], flail
  rate [C, derived from `code_lines==0`/`files_changed==0`], `narration_rate`/penalty [H, null].
- **Existing backend source:** split EMITTED (`experiment_spec.py:385-386`;
  `adapters/opencode.py:720-724`; `runtime/story/models.py:115-116`); `thinking_ratio`
  (`measurement/efficiency.py:257`); `data.js` narration fields exist but are**null**. No room
  endpoint; no named flail field.
- **Missing record fields:** named `flail`; per-model narration penalty aggregation; room surface
  for the split; a silent-mode policy arm.
- **Surface:** drill (also budget). **Action:** set narration/silent-inference policy per task.
- **Cost of missing:** 0.3%–30% narration penalty paid with no visible split to decide which work
  should pay it.
- **Walkthrough:** R4d (J4) → select attempt → `tokens.answer` + `tokens.explanation` both shown →
  L-WORKFORCE narration penalty. PASS: split rendered + penalty present; FAIL: single token total.

### Rule 3 — Snowball Rule (N²) · proposed [C] · augmented
- **Decision:** commit to a one-way-door architecture and budget the N-session cost arc before
  the quadratic growth locks in.
- **Evidence fields:** session-arc cost [M], `snowball_factor` S5/S1 [C], velocity `v` [C],
  `β` context inflation [P, calibrated].
- **Existing backend source:** `scripts/lab_story_arc.py` (`snowball_factor:139-142`, session
  costs `:149-150`) → `data.js` `labs.story_arc`; `design_parameters.beta`. **No room endpoint.**
- **Missing record fields:** per-session arc in the room; velocity by model; β provenance label;
  one-way-door decision marker.
- **Surface:** drill (also budget). **Action:** choose the architecture on the projected curve.
- **Cost of missing:** a one-way door is chosen without the arc; the overrun appears after the
  compounding is irreversible.
- **Walkthrough:** money/arc drill → session1..N costs + snowball_factor → β labeled calibrated
  [P]. PASS: arc + provenance before the architecture decision; FAIL: only a total cost.

### Rule 4 — EPM Horizon · proposed [C] · augmented
- **Decision:** which energy scenario and hedge horizon to budget against, and the flip year for
  local energy.
- **Evidence fields:** EPM baseline/aggressive [X], energy ranking [X], `ENERGY_PER_*` [P],
  `energy_total_j`/`quality_per_joule` [C].
- **Existing backend source:** `data.js` `energy_ranking`, `design_parameters.epm_baseline`/
  `epm_aggressive`, `external_sources`; `measurement/efficiency.py:30-31`;
  `build_data.py:193-194`. **No room endpoint; no ledger energy price.**
- **Missing record fields:** EPM(t) scenario field; region/provider split; flip-year alert;
  measured (not modeled) energy cost per session.
- **Surface:** drill (also budget, alert). **Action:** pick scenario + hedge; recalibrate EPM.
- **Cost of missing:** long-horizon compute inflation invisible until it flips the provider
  selection.
- **Walkthrough:** budget lens → active EPM scenario + rate next to spend → provenance labeled
  [P]/[X]. PASS: scenario visible/swappable with provenance; FAIL: energy absent.

### Rule 5 — First-Pass Rule · instrumented [M] · augmented
- **Decision:** retry / escalate / abandon a failed attempt by the accepted outcome, not the
  prompt price.
- **Evidence fields:** `attempt_number` [M], `accepted`/`first_pass` [M],
  `evaluator_independent` [M — **declared, no writer**], `test_executed_success` [M],
  `WOC = 1/(1+r)` [C].
- **Existing backend source:** workflow-run ledger (`experiment_spec.py:362,377-379`;
  `runtime/workflow_runner.py:2793-2796`); `runtime/test_runner.py`. `evaluator_independent` has
  **no writer**. `data.js` `derived.overall_pass_rate`, `verdicts.cap_2b`. **No room endpoint**
  (glance shows `attempt.number` only).
- **Missing record fields:** `evaluator_independent`; `first_pass`/`accepted` in the live run
  sample; per-task/per-model coverage; cost-per-accepted-outcome; attempt-chain projection.
- **Surface:** alert (also rest, drill). **Action:** retry/escalate on failed verification (J2/J3).
- **Cost of missing:** a cheaper model keeps a false price advantage because retries and failed
  verification are not priced into the accepted outcome.
- **Walkthrough:** verification-failure alert (ON-A1) on R1 → R4a/R4c show attempt_number,
  first_pass, independent test verdict → bounded retry action. PASS: alert carries attempt-chain
  evidence; FAIL: failure is a bare status.

### Rule 6 — Batch Discount · proposed [C] · autonomous
- **Decision:** what fraction of jobs to run in cheaper deferred batch mode vs on-demand.
- **Evidence fields:** batch fraction `b` [P], `batch_mode` marker [P, absent], provider batch
  pricing [X], queue model [P].
- **Existing backend source:** **NONE.** `batch_mode` is referenced only by a comment
  (`measurement/efficiency.py:104`) and a pinned metric that is hard-coded not-measurable
  (`scripts/aggregate_workflow_metrics.py:536-538`); `scripts/generate_manifest.py:396` records
  that batch/cascade/SLA were not executed.
- **Missing record fields:** `batch_mode` on jobs; batch vs on-demand cost accounting; batch queue
  depth/horizon; batch-fraction measurement; an executed batch arm.
- **Surface:** drill (also budget). **Action:** (future) split workstreams batch vs on-demand;
  today a modeled scenario toggle only.
- **Cost of missing:** the 50% discount is unusable and unbudgetable, and the room cannot even
  show that it is unmeasured.
- **Walkthrough:** budget lens → batch fraction is a measured value **or** an explicit
  modeled/not-measured token. PASS: labeled [P]/[X] + names the missing `batch_mode` record;
  FAIL: a fabricated batch number, or silent omission.

### Rule 7 — Budget Ceiling · proposed [C] · autonomous
- **Decision:** raise/lower the cap and read the autonomous throughput it buys
  (`T_max = Budget / (cost per job × (1 + retry))`).
- **Evidence fields:** `hard_cap_usd`/`reserved_cost_usd` [M], campaign cap [P],
  retry rate `r` [M], settlement status [M], `StopSpec.budget_usd` [P], `forecast_cost` [P —
  declared, no writer].
- **Existing backend source:** lease/admission (`control/lease_registry.py:431-448,882`;
  `control/admission.py:486,573-576`); run cap (`scripts/run_workflow.py:308`); settlement
  (`control/settlement.py:100-110`, `experiments/results/settlement/settlements.jsonl`). Room:
  `GET /api/subscription-usage` admission board (`routes/telemetry.py:298-303`) + `/api/glance`
  money (`routes/glance.py:342-388`). **The one measured, room-exposed rule.**
- **Missing record fields:** `StopSpec.budget_usd` enforcement at run time; per-job actual vs
  budget; `forecast_cost`/`forecast_latency`; `T_max` projection; cap-raise record at rest.
- **Surface:** rest (also alert, decide). **Action:** raise/lower the cap (P0 raise-cap).
- **Cost of missing:** the room shows spend but not the throughput the cap buys or the enforcement
  gap; a declared ceiling that is not enforced is mistaken for one.
- **Walkthrough:** R3a (J5) + money lens → spend, budget, headroom, reservations with provenance
  (unknown ≠ `$0.00`) → raise-cap door + record. PASS: spend vs hard cap + reserved headroom at
  rest with a raise-cap door; FAIL: only a spend number.

### Rule 8 — Cascade Rule · proposed [C] · autonomous
- **Decision:** whether/how to escalate a failed attempt through model tiers, bounded to <1%
  human escalation.
- **Evidence fields:** `escalation_from`/`escalation_to` [M — declared, always `None`],
  `E_x` multiplier [C], `escalation_rate` [P], tier price ratios [X].
- **Existing backend source:** fields declared (`experiment_spec.py:365-366`) but
  `runtime/workflow_runner.py:528-529` **always writes `None`** ("never escalates mid-phase").
  `control/routing.py:110` is an offline recommendation; `control/decisions.py:37` is
  proposal-only; `scripts/cap_cascade_retrospective.py` is retrospective-only (`data.js`
  `verdicts.escalation`). **No room endpoint; no recorded escalation cost.**
- **Missing record fields:** actual escalation events (from/to/reason); escalated-attempt cost;
  escalation rate per tier; an armed cascade arm; human-escalation counter.
- **Surface:** alert (also drill, intervene). **Action:** escalate a failed attempt; design the
  cascade bound.
- **Cost of missing:** failures never auto-escalate and escalation cost is never recorded, so the
  28.2× multiplier is a surprise and the cascade cannot be run as a policy arm.
- **Walkthrough:** failed attempt → R4a/R4c show escalation from→to + reason + measured cost, or an
  explicit "no cascade armed". PASS: tier/reason/cost shown or absence explicit; FAIL: silent
  status change.

### Rule 9 — SLA Buffer · proposed [C] · autonomous
- **Decision:** set the SLA buffer and never batch under 2× observed queue depth.
- **Evidence fields:** `queue_length` [M], `queue_wait_ms`/`service_time_ms` [M — declared, **no
  writer**], `due_at`/`deadline_slack` [P — no writer], SLA breach rate [C, aggregate only].
- **Existing backend source:** queue counts EMITTED (`control/pipeline_status.py:61-73`;
  `scripts/monitor.py`; `GET /api/matrix`); aggregate breach rate
  (`scripts/aggregate_workflow_metrics.py:706-748`). `queue_wait_ms`/`service_time_ms`/`due_at`/
  `deadline_slack` declared (`experiment_spec.py:338-374`) with **zero writers**;
  `worker.py:391,434` computes elapsed but only logs it. Parity `TIMING_FIELDS`
  (`apps/control_room/static/parity.js:458-471`) marks queue_wait/service_time `unknown`.
  **No SLA buffer arithmetic exists anywhere.**
- **Missing record fields:** `queue_wait_ms`, `service_time_ms`, `due_at`/`deadline_slack`
  enforcement, per-job buffer/horizon, live completion-time trace.
- **Surface:** alert (also drill, intervene). **Action:** add an on-demand fallback; hold batch
  when depth threatens the SLA.
- **Cost of missing:** the 2× rule cannot be applied because wait/service are invisible; batch work
  silently breaches its SLA and the room shows only a stuck queue.
- **Walkthrough:** queue lens (J8/J2) → depth + per-job queue_wait/service_time or explicit
  `unknown` → fallback action when 2×depth exceeds the horizon. PASS: timings measured/unknown +
  2× rule surfaces; FAIL: raw counts shown as if timings.

### Rule 10 — Outcome Multiplier · proposed [C] · value
- **Decision:** which policy arm to keep, judged by outcomes per dollar (BVI), not lowest cost.
- **Evidence fields:** accepted/verified outcomes [M], total AI cost [M], human cost `H` [P],
  workload `W` [P], BVI [C — not computed in-repo].
- **Existing backend source:** outcomes+cost measured (ledger `accepted` `experiment_spec.py:379`;
  `control/settlement.py`; `data.js` `verdicts.cap_2b` cpvo/verified-success-rate). `H` and `W` are
  modeled calculator inputs. **No BVI computation; no room outcomes-per-dollar or arm comparison.**
- **Missing record fields:** accepted-outcome count per run/arm; human-cost `H` input; BVI
  computation; arm-comparison (compare phase) surface; value-weighted verdict row.
- **Surface:** rest (also drill, decide). **Action:** compare arms on outcomes per dollar; keep the
  value-maximizing policy; record the verdict.
- **Cost of missing:** the room optimizes visible cost, not outcomes per dollar; the compare/adapt
  phase of the engine chain has no operator surface.
- **Walkthrough:** R0 + money lens (J1/J5) → accepted outcomes + total cost + BVI (or explicit
  modeled label) → arm-comparison drill + verdict receipt. PASS: outcomes-per-dollar or its
  explicit [P] gap at rest, with a compare-arm decision; FAIL: only cost.

## Gap rollup — the workflow-management records the backend does not emit

The d1 hard rule is explicit: a record the backend does not emit is a **gap**. Declared-but-unwritten
`LEDGER_FIELDS` (`src/agentic_dynamics/experiment/experiment_spec.py:330`) are the sharpest gaps,
because the declaration looks like instrumentation:

```
queue_wait_ms            experiment_spec.py:373   no writer  (worker.py:391,434 logs elapsed only)
service_time_ms          experiment_spec.py:374   no writer
leased_at                experiment_spec.py:369   no writer
first_token_at           experiment_spec.py:371   no writer
due_at                   experiment_spec.py:338   no writer
deadline_slack           experiment_spec.py:342   no writer
forecast_cost            experiment_spec.py:339   no writer
forecast_latency         experiment_spec.py:340   no writer
evaluator_independent    experiment_spec.py:380   no writer
cost_inference           experiment_spec.py:387   no writer
cost_orchestration       experiment_spec.py:388   no writer
reuse_value              experiment_spec.py:406   no writer
batch_mode               (no field at all)        no batch execution mode exists
escalation cost          (no field at all)        escalation_from/to always None
```

These are the records the room cannot show **today** and that a later phase (d2 information gaps,
d3 backend requirements) must schedule. Note the direction of the fix: the measured signals
(`confidence`, `perturbation_strength`, `test_executed_success`, the answer/explanation split)
already exist and are **not** in this gap list — what is missing is (a) the timing/management
records above and (b) the room projections that would expose the measured fields.

## Acceptance (d1)

- **10/10 rules** present in `experiments/control_room_rules/rule_map.json`, every required field
  populated; `NONE` is used explicitly (rules 6 and 8; room-level for 1–5 and 10).
- Both workforces covered: augmented 1–5, autonomous 6–9, value 10.
- The operator's daily loop covered: `glance, triage, decide, inspect, intervene, budget, audit`
  all appear across the rules' `loop_stages`.
- Every `existing_backend_source` names a real `file:line`/table/endpoint in this repo, or `NONE`.
- Companion render: this document (`docs/reviews/control_room_rule_map.md`).
