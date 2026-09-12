---
status: accepted
---

# Control Room — per-state screens (campaign phase d4)

**Date:** 2026-09-11
**Workflow:** `workflows/repository/control_room_rules_design.yaml`, phase `d4_room_design`.
**Inputs:** `experiments/control_room_rules/surface_map.json` (d4), `rule_map.json` (d1),
`information_gaps.json` (d2), `docs/designs/current/control_room_backend_requirements.md` (d3).
**Authoritative lifecycle:** `docs/research/control_room_interaction_model.md` §1 (the control
database's enforced `RunState` graph, `control_db.py:140-243`).
**Authoritative resting contract:** `docs/research/control_room_ia.md` §2 (regions), §4
(`ON-G1..G7`), §7 (`ON-A1..A6`).

This document fixes what is on screen for each operator-facing **state**: `running`, `blocked`,
`stalled`, `failed`, `escalated`, `done`. A state is a *situation the operator reads*, not a new
lifecycle — the UI renders the database's state and never invents one
(`interaction_model.md:64-67`). Each state therefore **maps exhaustively** to `RunState` /
`AttemptState` plus at most one observation (heartbeat, lease, escalation, gate).

## 0. State → lifecycle mapping

| operator state | maps to `RunState` / `AttemptState` | extra observation that names it | alert |
|----------------|--------------------------------------|----------------------------------|-------|
| **running** | `running`, `verifying`, `promoting`, `projecting`; attempt `running`/`ok` | fresh `run_heartbeats` row (`control_db.py:875`) | none (watch) |
| **blocked** | `awaiting_approval`; attempt `awaiting` | a pending gate / controller decision | `ON-A4` (or `ON-A2` if dependency-blocked) |
| **stalled** | still `running` in the DB | expired heartbeat (`run_heartbeats.last_seen_at`) or phase status `STALLED` | `ON-A1`/`ON-A2` |
| **failed** | `failed` (any non-terminal → failed); attempt `failed` | terminal negative outcome | `ON-A1` |
| **escalated** | attempt tier change (`escalation_from`→`escalation_to`) | an escalation event; **no mechanism today** (d2 G-27) | `ON-A1` if the escalated attempt fails |
| **done** | `merged`, `projecting`, `published`; attempt `ok`/`skipped` | terminal success (published = projections complete) | none (audit) |

Two distinctions the screen must never erase (`control_db.py:162-165`): **`merged` is not
`published`** (a run can be on `main` with stale projections), and **`awaiting_approval` is not
`failed`** (a designed stop).

## 1. The truth table

Rows are the resting regions + dock + alert; columns are the six states. `·` = not the owner of
this state; `◐` = present but secondary; `●` = the state's primary screen element. Every cell
names the actual content. `[Rn]` tags are the rules served (d1).

| region / element | running | blocked | stalled | failed | escalated | done |
|---|---|---|---|---|---|---|
| **R0 `ON-G1` system** | ● browser/control/workers/projections `up`, worst age fresh; live SSE | ◐ all `up`; the *run* is paused, not the room | ● worker/projection `degraded` when the stall is dependency-caused; age climbs | ◐ room healthy; the failure is the run's | ◐ room healthy | ◐ room healthy; projections may lag (`merged`≠`published`) |
| **R0 `ON-G6` trust** | ● epoch advanced; `stale/partial/unknown = 0` | ◐ epoch pinned at the decision | ● `stale` count > 0 or `unknown` for the stalled subsystem | ◐ trust complete | ◐ trust complete | ● projections shown `current` only when watermarks confirm; else explicit lag |
| **R1a decision (`ON-G5`)** | · `none pending` | ● pending decision: target, kind, epoch, authority, eligibility, `candidate_sha`, gate; typed-confirm preview | ◐ decision only if the stall has a safe cancel/interrupt | · `none pending` | · `none pending` | ◐ promote decision when `promotable`; else `none pending` |
| **R1b risk (`ON-G3`)** | ◐ live-stall watch, `all clear` normally | ◐ `all clear` (a decision is not a risk) | ● highest-severity **stalled** item: identity, last-seen age, affected phase, action `interrupt`/`cancel` `[5,9]` | ● **failure** item: failed run, terminal reason, action `triage` `[5,8]` | ● **advisory**: attempt escalated `from→to`, reason; action `inspect` `[8]` | ● `all clear`, or a residual unrecorded act `[10]` |
| **R1c next** | ◐ next risk/advisory after R1b | ◐ process/recording gap | ◐ next item | ◐ next item | ◐ next item | ● residual process gaps only |
| **R2 `ON-G2` run ledger** | ● row live marker; `phase n/total`; attempt; running/queued/failed/live counts `[5,7,9]` | ● row lifecycle `awaiting_approval`; decision-eligibility token; counts unchanged | ● row `running` but **changed-at stale** + stalled marker (never hidden) `[9]` | ● row `failed`; terminal reason; counts update `[1,5]` | ● row shows `escalation_from→to` on the attempt `[8]` | ● row settled `published`; receipt coverage `recorded`; live count drops `[10]` |
| **R3a `ON-G4` cost** | ● spend/burn climbing; leases held; provenance chips `[7]` | ◐ spend flat; lease reserved-unspent visible | ◐ spend may keep climbing if the stall still burns; money-risk if so `[7,9]` | ◐ spend stopped; settlement pending | ● escalated-attempt cost appears; E_x ratio `[8]` | ● settled cost, `cost_source` reconciled; leases released `[7,10]` |
| **R3b health detail** | ◐ worker health `up` | ◐ dependency row names the blocking gate | ● worker/dependency detail: which heartbeat, how old `[9]` | ◐ mirror | ◐ mirror | ◐ projection watermark detail |
| **R3c `ON-G7` composition** | ● lifecycle marginal shows `running` bucket `[5]` | ◐ `awaiting_approval` bucket | ◐ `running` bucket unchanged (the stall is invisible here) | ● `failed` bucket increments `[1]` | ◐ model marginal shifts as tiers change `[8]` | ● `published` bucket increments `[10]` |
| **R4a address** (drill) | ● identity, target, current command/tool, epoch `[5,7]` | ● + gate id, `candidate_sha`, decision authority `[7]` | ● + `last_seen_at`, heartbeat age, stall evidence `[9]` | ● + terminal reason, terminal epoch `[5]` | ● + escalation tiers and reason `[8]` | ● + squash/promotion sha, published receipt `[10]` |
| **R4b worker event + action** (drill) | ● one live stream (replay→live), follow/pause; actions `attach/detach/copy/interrupt` `[5,6,9]` | ● actions `approve/cancel` with preview, `interrupt` alternative `[7]` | ● stream silent; actions `interrupt`/`cancel` (typed) `[9]` | ● actions `retry(new run)`/`cancel`/`copy-session` `[5]` | ● actions `escalate`/`interrupt` `[8]` | ● actions `promote`/`retire`/audit-only `[10]` |
| **R4c evidence ladder** (drill) | ● rungs fill live: narration→measured→independent test `[1,5]` | ● ladder frozen at the gate; measured evidence at the gate shown `[7]` | ● ladder frozen; last rung age highlighted; no fabricated value `[9]` | ● failed rung + reason; independent test vs narration `[1,5]` | ● attempt boundary shows escalation from/to + escalated cost `[8]` | ● full ladder; registry record link `[10]` |
| **R4d step timings** (drill) | ● queue_wait/service_time/first_token/duration/tokens/cost/exit_code; measured|unknown `[2,9]` | ◐ timings frozen at the decision | ● `unknown` where the writer is missing; age shown `[9]` | ◐ timings complete to the failure | ● escalated attempt carries its own timings `[8]` | ● complete timings; verification row `measured` `[2]` |

Evidence-class chips attach to every consequential value (`ia.md` §8): measured `[M]`,
computed `[C]`, heuristic `[H]`, modeled/policy `[P]`, external `[X]`, unknown. **Unknown is never
`0`** (`DP5`, d3 §9).

## 2. What triggers each screen (the state machine)

| from → to | trigger (producer) | screen change | alert |
|-----------|--------------------|---------------|-------|
| (none) → running | `ControlDB.transition_run(queued→running)`; heartbeat touches | R2 row live; R3a burn starts | none |
| running → blocked | a checkpoint phase records `awaiting` (`workflow_runner`), or a dependency fails a gate | R1a decision item; R2 eligibility `approve` | `ON-A4` |
| blocked → running | an `ApprovalRecord`/`approval.md` satisfies the checkpoint | R1a → `none pending`; R2 live | none |
| running → stalled | heartbeat `last_seen_at` older than the stale floor (`run_heartbeats`), or phase `STALLED` | R0/R3b degraded; R2 stalled marker; R1b item | `ON-A1`/`ON-A2` |
| stalled → running | a fresh heartbeat (the run caught up) | stall marker clears | resolved |
| stalled → failed | the runner gives up / a watchdog records terminal `STALLED` (observe-only rail — flags, never kills) | R2 `failed`; R4 terminal reason | `ON-A1` |
| running → failed | a phase/gate records `failed`; `transition_run(→failed)` | R2 `failed`; R1b failure item | `ON-A1` |
| running → escalated | an escalation event (`escalation_from`→`escalation_to`) — **requires the mechanism, d2 G-27** | R2/R4c escalation mark; R4b `escalate` | advisory (`ON-A1` if the escalated attempt fails) |
| escalated → running/done | the escalated attempt finishes `ok`/`failed` | escalation mark retained; outcome shown | — |
| running → done | `verifying`→`promotable`→`promoting`→`merged`→`projecting`→`published` | R2 settled; R3a settled; promote decision if `promotable` | none (audit) |

**Observe-only rails never steer** (`agent_config/rules.md`): the supervisor and lease watchdog
raise flags/quarantine marks for `stalled`; they never kill or re-route. The screen's only
`stalled` actions come from the operator/AIO within the database graph (`cancel`, `interrupt`).

## 3. Acceptance checks (for the future render gate)

The checks extend `control_room_ia.md` §10 (geometry G, event E) and §15. Each names the state,
the selectors, and the pass condition. **P** = parity/feature class.

| # | state | selectors | assertion |
|---|-------|-----------|-----------|
| `S-1` | running | `[data-region="R2"] [data-run-id]` live marker; `R3a [data-field="money.burn"]` | a fresh run shows a live marker and a non-zero burn; `R0` worst age is fresh |
| `S-2` | blocked | `[data-attention-class="decision"] [data-answer="ON-G5"]` | a pending decision shows target/kind/epoch/authority/eligibility; the offered action ⊆ `packet.safe_actions`; R1b does **not** say `failed` |
| `S-3` | stalled | `R2` row stalled marker + `R1b` item | a run whose heartbeat expired shows a stall marker with last-seen age; no fabricated timing renders `0`; the action set is `{cancel, interrupt}` |
| `S-4` | failed | `R1b` failure item → `R4c [data-dock-region="evidence"]` | the failure item opens the attempt chain; the independent test verdict is shown beside the narration; `R2` counts update |
| `S-5` | escalated | `R4c [data-attempt-boundary]` escalation mark | `escalation_from`/`escalation_to`/reason render, or the dock says `no cascade armed`; E_x is labeled `[C]/[X]`; never an invented event |
| `S-6` | done | `R2` row `published`; `R3a` settlement; `R4c` registry link | a published run shows a settled cost with `cost_source` and `recorded` receipt coverage; `merged` (projecting) is distinguishable from `published` |
| `S-7` | any | `[data-state]` provenance chips on consequential values | every consequential value carries a source+age chip; `unknown` renders the literal `unknown`, never `0`/`null`/blank |
| `S-8` | any | `R0 [data-answer="ON-G6"]` | `stale`/`partial`/`unknown` counts are explicit and never green-over-stale (`green must never lie`) |

## 4. Rule coverage of the states

| state | rules most exercised |
|-------|----------------------|
| running | 1 (Grit), 2 (tax), 5 (first-pass), 7 (budget), 9 (SLA) |
| blocked | 5 (first-pass gate), 7 (budget/cap decision), 10 (value arm) |
| stalled | 9 (SLA/heartbeat), 5 (retry-worthiness), 8 (escalate instead of wait) |
| failed | 1 (Grit under perturbation), 5 (first-pass), 8 (cascade) |
| escalated | 8 (cascade), 7 (escalated cost), 10 (value of escalation) |
| done | 3 (snowball), 7 (settlement), 10 (BVI/verdict) |

Every rule 1–10 is exercised by at least one state, and every state's primary screen element is
named in `surface_map.json` (`rules[].surface`).
