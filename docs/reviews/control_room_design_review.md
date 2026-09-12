---
status: accepted
---

# Control Room — controller design review (campaign phase d5)

**Date:** 2026-09-11
**Workflow:** `workflows/repository/control_room_rules_design.yaml`, phase `d5_controller_checkpoint`.
**Status:** **AWAITING OPERATOR APPROVAL** — this phase is a `checkpoint: true` stop. The run is
`awaiting_operator_approval`; no implementation wave may start until the controller commits
`approvals/control_room_rules_design/d5_controller_checkpoint_approval.md` with a real signature and
date (contract: `runtime/workflow_runner.py:67-83`).

This packet is the controller's decision document. It summarizes the whole `d0–d4` chain —
**frozen mandate → rule/decision map → information gaps → backend requirements → room design** —
and ends with the explicit **OPEN QUESTIONS** the controller must answer. The supporting machine
artifacts are listed in §7.

## 0. Executive summary

The published **10 rules** and the shared engine chain are the mandate of record. Against them the
campaign found:

- **3 of 10 rules are instrumented `[M]`** (1, 2, 5); the other **7 are proposals `[C]`** modeled
  or designed but never run as arms. **0 are decided** (`docs/research/control_room_rules.md`).
- The room today can fully show **exactly one rule** — **7 Budget Ceiling** (lease/admission +
  `/api/subscription-usage` + `/api/glance` money). Four rules (1, 2, 5, 10) are **measured but
  have no room surface**; four (3, 4, 8, 9) are modeled/external only; **Rule 6 Batch is `NONE`**.
- **42 gaps** block the full room; **24 are workflow-management records** (job state, attempts/
  retries, step timings, escalations, queue wait, batch flags, budget/SLA). **9 have no producer at
  all** — true build items. The sharpest are **declared-but-unwritten `LEDGER_FIELDS`** (e.g.
  `queue_wait_ms`, `service_time_ms`, `evaluator_independent`, `forecast_cost`): they *look*
  instrumented but have no writer.
- **11 read-only projections** close the room side; **26 of 42 gaps need a new writer/producer**
  first. The room design maps **10 rules × 11 operator jobs** to closed surfaces and fixes **6
  operator states**, two resting viewports, the `R4` drill-down, and 14 lenses.

**The ask:** sign the checkpoint to authorize the read-only projection layer, and decide the
build-vs-model priority for the writer-dependent gaps (§6).

## (a) Wireframe summary and the state table

**Resting screen.** One screen answers `ON-G1..G7` at rest, no interaction, no scroll. Desktop
1440×900: `R0` system+trust (72px) over `R1` attention (300) │ `R2` run ledger (744) │ `R3`
cost/health/composition (340); `72 + 12 + 800 = 884 ≤ 900`, `16+300+12+744+12+340+16 = 1440`.
Mobile 390×844 stacks the same seven answers: `72+144+284+92+68+60+40 = 760 ≤ 844`. `R4` is `0` at
rest; on selection it opens as a ≈320px bottom dock (`R4a` 48 / `R4b` 160 │ `R4c` 160 / `R4d` 96) or
a mobile full-height inspector. Full ASCII grids, element lists with dimensions, and the lens
palette: `docs/research/control_room_wireframe.md`. Every one of rules 1–10 is a labeled element
(gate hook).

**Per-state screen** (`docs/research/control_room_state_screens.md`). A state is a *situation read*,
mapped exhaustively to the control DB's `RunState`/`AttemptState` — the UI never invents one.

| operator state | lifecycle mapping | primary alert | R2 row | R4 primary | action (eligibility) |
|----------------|-------------------|---------------|--------|------------|----------------------|
| **running** | `running`/`verifying`/`promoting`/`projecting`; attempt `running`/`ok` | none (watch) | live marker, phase n/t | R4c ladder / R4b stream | `interrupt` (P1) |
| **blocked** | `awaiting_approval`; attempt `awaiting` — a designed stop, **not failed** | `ON-A4` | state `awaiting_approval`, eligibility token | R4a + R4b preview | `approve`/`cancel` (P0) |
| **stalled** | still `running`; expired heartbeat / phase `STALLED` | `ON-A1`/`ON-A2` | stale changed-at + stall marker | R4a (last_seen) / R4b | `cancel`/`interrupt` |
| **failed** | `failed`; attempt `failed` | `ON-A1` | `failed`, terminal reason | R4c ladder (test verdict vs narration) | `retry(new run)`/`cancel` |
| **escalated** | attempt tier change (`escalation_from`→`to`); **no mechanism today** | `ON-A1` if it fails | escalation mark | R4c attempt boundary | `escalate`/`interrupt` |
| **done** | `merged`/`projecting`/`published`; attempt `ok`/`skipped` | none (audit) | settled, receipt coverage | R4c + registry link | `promote`/`retire` (P0) |

Two distinctions the screen never erases: **`merged` ≠ `published`**, and **`awaiting_approval` ≠
`failed`**. Render-gate checks `S-1..S-8` are in the state-screens doc.

## (b) The 10-rule map — status, evidence class, backend source, top gaps

From `experiments/control_room_rules/rule_map.json` (d1) and `information_gaps.json` (d2). "Surface"
is the primary operator surface (rest/drill/alert).

| # | rule | status | evidence class | surface | existing backend source (room) | top gaps |
|---|------|--------|----------------|---------|-------------------------------|----------|
| 1 | Grit | instrumented [M] | M/C | rest | none in room (ledger + `lab_grit` + `data.js` only) | G-01..03 |
| 2 | Explanation Tax | instrumented [M] | M/C | drill | none in room (token split emitted; narration fields null) | G-04..06 |
| 3 | Snowball | proposed [C] | C/P | drill | none in room (`lab_story_arc` + `data.js`) | G-07..10 |
| 4 | EPM Horizon | proposed [C] | X/P | drill | none in room (`data.js` energy/design params) | G-11..13 |
| 5 | First-Pass | instrumented [M] | C | alert | partial (ledger `attempt_number`/`accepted`; `evaluator_independent` unwritten) | G-14..18 |
| 6 | Batch Discount | proposed [C] | X/P | drill | **NONE** (metric hard-coded not-measurable) | G-19..21 |
| 7 | Budget Ceiling | proposed [C] | C/P | rest | **yes** — lease/admission + `/api/subscription-usage` + `/api/glance` | G-22..26 |
| 8 | Cascade | proposed [C] | X/P | alert | **NONE** (`escalation_from/to` always `None`; no cascade) | G-27..29 |
| 9 | SLA Buffer | proposed [C] | P | alert | **NONE for buffer** (queue counts + aggregate breach rate only) | G-30..34 |
| 10 | Outcome Multiplier | proposed [C] | C/P | rest | partial (`verdicts.cap_2b` outcomes+cost; no BVI) | G-35..38, G-42 |

**Load-bearing limitation** (frozen mandate): *a rule's premise being measured does not make the
rule measured — a policy becomes decided only when it is run as an arm and compared.* Only the
`cap_2b` verdict is decided, and it authorizes design review only.

## (c) Backend requirements

`docs/designs/current/control_room_backend_requirements.md` (d3). 42 gaps → **11 read-only
projections**; **16 gaps close with a read model over already-emitted data**, **26 require a new
writer/producer**.

| projection | purpose | key gaps | API (read-only) |
|------------|---------|----------|-----------------|
| **P1 `workflow_records`** | **the single jobs/attempts/steps projection** (timings, retries, escalations, queue waits, batch, budget/SLA) | G-16,19,22-24,30-32,39-41 | `GET /api/workflow-records[/<job_id>]` |
| P2 `attempt_evidence` | per-attempt causal ladder | G-02..04,12,14,15,31,41,42 | `GET /api/runs/<run_id>/attempts` |
| P3 `model_quality` | Grit / first-pass / narration / coverage | G-01,05,06,18 | `GET /api/quality` |
| P4 `story_arc` | snowball / velocity / β | G-07..09 | `GET /api/stories/<name>/arc` |
| P5 `run_value` | accepted outcomes, cost-per-outcome, BVI | G-17,35,37 | `GET /api/value` |
| P6 `arm_comparison` | compare/adapt arms | G-38 | `GET /api/arms/compare` |
| P7 `spend_budget` | spend/headroom/leases/T_max/EPM/human cost | G-09,11,13,22,24-26,36 | `GET /api/spend` / extend `/api/subscription-usage` |
| P8 `sla_queue` | queue depth, wait/service, burn, SLA buffer | G-30,32-34 | `GET /api/queue/sla` |
| P9 `escalation_cascade` | escalation events/cost/rate | G-27..29 | `GET /api/escalations` |
| P10 `batch` | batch flags/accounting (explicit not-measurable) | G-20,21 | `GET /api/batch` |
| P11 `decision_ledger` | architecture + cap decisions | G-10,26 | `GET /api/decisions` |

**Marked "do not rebuild":** control packet `control-status/v1`, control-DB tables (`runs`,
`step_attempts`, `run_transitions`, `gate_results`, `approvals`, `promotions`, `run_heartbeats`),
the emitted ledger fields, run ledgers, lease/settlement, queue counts, canonical corpus, lab
metrics, supervisor rail. **No new mutation routes** — projections are strictly additive `GET`s.
Invoice of new writers: §7 of the requirements doc (27 rows), gated below.

## (d) Job walkthroughs

`experiments/control_room_rules/job_walkthroughs.md` (d4). Every operator job J1–J11 has a numbered
click-path, the expected information at each step, and a PASS/FAIL assertion the render gate can
implement.

| job | surface | rules served | PASS class |
|-----|---------|--------------|------------|
| J1 Glance | rest R0–R3c | 1,2,5,7,10 | `ON-G1..G7` geometry |
| J2 Triage | alert R1b → R4a/R4c/R4b | 1,5,8,9 | `ON-A1` event |
| J3 Decide | alert R1a → R4a/R4b/R4c | 5,7,8,10 | `ON-A4` event / safe-action |
| J4 Inspect | drill R4c/R4d + L-WORKFORCE | 1,2,3,5,8,9 | `G-18` timings |
| J5 Watch spend | rest R3a → L-MONEY | 3,4,6,7,10 | `ON-G4` |
| J6 Intervene | drill R4b | 8,9 | `E-6/E-7` |
| J7 Audit | drill L-REGISTRY/AUDIT/R1c | 1,5,7,10 | `ON-D4` |
| J8 Enqueue | drill QUEUE | 6,9 | admission fail-closed |
| J9 Route | drill R4a + L-COMPOSITION | 1,2,5 | `ON-D5` |
| J10 Claude sessions | drill L-SESSIONS/R4b | — | ownership + receipt |
| J11 Record close | drill AUDIT/R1c/L-REGISTRY | 1,5,7,10 | receipt + rerun no-op |

## (e) OPEN QUESTIONS for the controller

Each is a decision the campaign cannot make for you. Recommended answers are marked
**(recommended)** where the evidence points one way, but the call is P0.

**Authorization**

1. **Do you sign the checkpoint and authorize implementation?** The gate is exact: committing
   `approvals/control_room_rules_design/d5_controller_checkpoint_approval.md` with a real signature
   + date, as a **descendant** of this packet's commit. **(recommended: sign the read-only subset;
   hold the writer-dependent subset pending Q2/Q3.)**

2. **Is the worktree branch itself a proposal for `main`, or does it stay a research branch?**
   Merging to `main` is a separate P0 act (`workflow promote`).

**Scope and sequencing**

3. **Wave 1 scope — read model or producers?** Build the **16 read-only gaps** immediately (they
   cost no new instrumentation), or first land the **declared-but-unwritten writers** so the
   projections are honest on arrival? **(recommended: read-only first; they are independent and
   prove the projection layer; then writers in dependency order.)**

4. **Which writer-dependent items are funded?** The 9 `NONE`/no-producer gaps are the expensive
   ones: batch (G-19/20/21), cascade (G-27/28/29), SLA buffer (G-33/34), BVI (G-37), human cost
   (G-36), region energy (G-13), flail (G-05). Which are in scope, and which stay explicitly
   modeled/absent in the room?

5. **Budget enforcement (G-22):** do you want `StopSpec.budget_usd` enforced at run time and
   `FINOPS_ADMISSION_REQUIRED` armed? The lease machinery exists but is **dormant** (off by
   default). Enforcing changes spend behavior; not enforcing means the room shows a ceiling that
   is not real.

**Rule interpretation**

6. **Rule 8 Cascade:** is an **automatic** escalation cascade in scope, or is escalation
   human-in-the-loop (AIO within lease) only? The mandate designs for <1% human escalation, but no
   mechanism exists and `escalation_from/to` is structurally `None`.

7. **Rule 6 Batch:** do we build a batch execution/accounting path, or keep batch explicitly
   modeled `[P]/[X]` and say so in the room? `generate_manifest.py:396` currently records it
   unexecuted.

8. **Rule 10 BVI + human cost (G-36/37):** who owns `H` (loaded engineer cost) and `W` (workload)?
   Without an owner the value is a modeled input the room must label `[P]`, never a measured KPI.

**Placement / housekeeping**

9. **Doc placement:** this campaign wrote to `docs/designs/current/`, which the docs-taxonomy
   restructure retired as a path family (`docs_taxonomy_restructure.md` §(d)). It is not guarded
   today. Do you want the d3 requirements moved to `docs/architecture/current/` (mechanism design's
   kind home) in a follow-up sweep?

10. **`/api/routing` data source:** it reads the **retired** `experiments/results/_results_summary.json`
    (`telemetry.py:256`), the quarantined corpus. Confirm the replacement with the canonical
    registry/corpus path (the d3 P3 projection) before wiring routing into the room.

11. **Projection shape:** in-process deterministic read models (like `build_packet`) — recommended,
    no new store — or materialized projection tables refreshed by a worker? The former fits the
    read-only contract; the latter adds a writer.

12. **Deployment:** should the room be deployed to **both** Firebase hosts (canonical
    `ai-finops-rulebook` + mirror `agentic-dynamics`) per the repo rule, and is that part of this
    campaign's release or a separate P0 release decision?

**Data integrity (raised by the chain, not new to this campaign)**

13. **The d2 `no-mechanism` vs `modeled-only` rollup** for G-36 was internally inconsistent; this
    packet corrects the derived rollup to match the gap record (`modeled-only`), alongside the d2
    edit. Confirm the correction is acceptable.

## The checkpoint contract

A successful checkpoint phase does **not** authorize implementation. To resume past it, the
controller commits `approvals/control_room_rules_design/d5_controller_checkpoint_approval.md`
**after** this packet's commit, with a real signature and date. The runner refuses a placeholder or
a same-commit template (`workflow_runner.py:74-83`). The unsigned template below is provided for
the controller to copy — **do not commit it unsigned**.

```text
# Control Room rules design — d5 controller checkpoint approval

CAMPAIGN: control_room_rules_design
PHASE: d5_controller_checkpoint
REVIEW PACKET: docs/reviews/control_room_design_review.md

SIGNED-BY-OPERATOR: <name>
DATE: <YYYY-MM-DD>
APPROVED DESIGN REVISION: <git sha of the committed d5 review packet>
NOTES OR SPECIFIC WAIVERS: <none | the Q-numbers decided, and any scope limits>
```

## §7. Supporting artifact index

| phase | artifact | what it fixes |
|-------|----------|---------------|
| d0 | `docs/research/control_room_rules_sources.md` | pin table (uri/final_url/fetched_at/sha256/title/quality) |
| d0 | `docs/research/control_room_rules.md` | the 10 rules verbatim + engine chain |
| d1 | `experiments/control_room_rules/rule_map.json` | rule → decision/evidence/source/gaps/surface/action |
| d1 | `docs/reviews/control_room_rule_map.md` | rendered rule map |
| d2 | `experiments/control_room_rules/information_gaps.json` | 42 gaps (source/granularity/cadence) |
| d2 | `docs/reviews/control_room_information_gaps.md` | rendered gaps + workflow-management records |
| d3 | `docs/designs/current/control_room_backend_requirements.md` | 11 projections, APIs, acceptance tests |
| d4 | `experiments/control_room_rules/surface_map.json` | rules × jobs → surface/fields/action |
| d4 | `docs/research/control_room_state_screens.md` | 6-state truth table + transitions |
| d4 | `docs/research/control_room_wireframe.md` | annotated wireframes + element budgets + rule labels |
| d4 | `experiments/control_room_rules/job_walkthroughs.md` | J1–J11 click-paths + PASS/FAIL |
| d5 | this packet | controller decision + open questions + approval template |

## Acceptance of the chain

- 10 rules present with citations (d0); every d1 decision in the surface map; every rule labeled in
  the wireframe; every job has a walkthrough (d4).
- 42/42 gaps mapped to projections (d3); workflow-management records explicit (d2).
- **Implementation is BLOCKED** until the controller signs the checkpoint. The machine proposes;
  the controller disposes.
