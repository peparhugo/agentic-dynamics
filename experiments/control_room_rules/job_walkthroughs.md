---
status: accepted
---

# Control Room — operator job walkthroughs (campaign phase d4)

**Date:** 2026-09-11
**Workflow:** `workflows/repository/control_room_rules_design.yaml`, phase `d4_room_design`.
**Inputs:** `experiments/control_room_rules/surface_map.json` (d4),
`docs/research/control_room_state_screens.md` (d4),
`docs/research/control_room_wireframe.md` (d4).
**Job authority:** `docs/research/control_room_ux_foundation.md` §2 (J1–J11);
**paths:** `docs/research/control_room_interaction_model.md` §5.

Each job is a numbered click-path. Every step names the expected information; each job ends with a
**PASS/FAIL assertion** the future render gate (`verify_control_room_rendering.py`) can implement
against the `[data-*]` selectors already defined in `control_room_ia.md` §10.2. `[Rn]` = the rule
served.

---

## J1 — Glance
*Continuous; no interaction. Rules [R1,R2,R5,R7,R10]. Surface: rest `R0 R1 R2 R3a R3b R3c`.*

1. **Return to the room, don't click.** Read `R0`: `ON-G1` (browser/control/workers/projections,
   each state + worst age) and `ON-G6` (epoch, worst age, `stale/partial/unknown` counts).
   → *Expected:* four named states; a non-zero `stale` never renders green.
2. **Read the attention inbox** `R1`: `R1a` decision (`ON-G5`) or `none pending`; `R1b` risk
   (`ON-G3`) or `all clear`; `R1c` next.
   → *Expected:* three reserved rows; a pending decision and a risk are both visible at once.
3. **Read the run ledger** `R2`: exact counts (running/queued/failed/live) then 8 ranked rows with
   identity, phase `n/t`, lifecycle, live marker, claim/proof, cost provenance, eligibility.
   → *Expected:* live state never hidden behind a filter.
4. **Read the constraint stack** `R3a` cost (all five `money.*` values + exception), `R3b` health,
   `R3c` four composition marginals.
   → *Expected:* unknown money is `unknown`, never `$0.00`.

**PASS:** at 1440×900 and 390×844 a screenshot contains exactly one `[data-answer]` anchor for each
of `ON-G1..G7`, in its canonical region (`G1→R0,G2→R2,G3→R1,G4→R3a,G5→R1,G6→R0,G7→R3c`), page does
not scroll, no region overflows. **FAIL:** any answer is missing, duplicated, below the fold, or
answered by a lens/mirror.

---

## J2 — Triage
*On a failure/risk signal; per incident. Rules [R1,R5,R8,R9]. Surface: alert `R1b` → drill `R4a R4c R4b`.*

1. **See the alert.** `R1b [data-attention-class="risk"]` shows the highest-severity failure/stall:
   identity, state, last-seen age, action.
2. **Open the run.** Click the item → `R4a [data-dock-region="address"]` shows run/session identity,
   worktree, current command, provider×model, attempt, lifecycle, epoch.
3. **Read the attempt chain.** `R4c [data-dock-region="evidence"]` shows one
   `[data-attempt-boundary]` per attempt: narration, MEASURED facts, independent test verdict,
   commit, cost, decision, registry link. `[R1,R5,R8]`
4. **Compare narration vs measured.** Confirm the independent test verdict is the failure reason,
   not the model's self-report.
5. **Pick the safe action.** `R4b` action band shows `retry`/`escalate`/`cancel` with target,
   authority, reversibility, confirmation, and the blast radius.

**PASS:** a failure raises `ON-A1`, whose item opens `R4c` with the attempt chain and an action set
⊆ `packet.safe_actions`; a stalled run shows last-seen age and the action set `{cancel, interrupt}`.
**FAIL:** triage terminates in an inspect-only view with no action, or the offered action is not in
`safe_actions`.

---

## J3 — Decide
*When the machine proposes; blocked-waiting; per gated run. Rules [R5,R7,R8,R10]. Surface: alert `R1a` → drill `R4a R4b R4c`.*

1. **See the proposal.** `R1a [data-attention-class="decision"]` (`ON-G5`): target, decision kind,
   control epoch, evidence authority, eligibility token.
2. **Open the decision object.** Click → `R4a`: `candidate_sha`, gate id, current run state, scope.
3. **Preview the act.** `R4b` action band shows the typed-confirm preview: target, scope/blast
   radius, budget effect, reversibility, and the **receipt** that will close it.
4. **Verify the gate.** `R4c` shows the measured evidence at the gate (same `candidate_sha`).
5. **Act or decline.** `approve` / `promote` / `cancel` / `retire` / `raise-cap`; irreversible acts
   require the typed phrase.

**PASS:** the eligibility token matches `ALLOWED_TRANSITIONS[state] ∩ packet.safe_actions`; the
preview names `candidate_sha`, epoch, budget effect, reversibility, and receipt; a decision record
is written at the moment of the act. **FAIL:** a bare button with no preview/receipt, or an offered
action the database would refuse.

---

## J4 — Inspect
*On demand, per selected run/attempt; per decision. Rules [R1,R2,R3,R5,R8,R9]. Surface: drill `R4c R4d L-WORKFORCE`.*

1. **Select a run** in `R2` → `R4a` address band appears.
2. **Read the evidence ladder** `R4c`: identity → lifecycle → narration → measured facts →
   independent verification → change/commit → cost provenance → decision → registry record.
   Each rung carries an evidence class + source + age.
3. **Read the step timings** `R4d`: one `[data-timing]` row per
   `queue_wait|service_time|first_token|duration|retries|tokens.answer|tokens.explanation|cost|exit_code|verification`,
   each `[data-state="measured|unknown"]` with `[data-value]`. `[R2,R9]`
4. **Aggregate across the fleet.** Open `L-WORKFORCE` for p50/p95 queue wait/service time, retry
   rate, tokens by model, Grit, narration penalty. `[R1,R2,R5,R8,R9]`

**PASS:** `R4c` has one `[data-attempt-boundary]` per attempt; `R4d` renders the exact timing field
set; an unobserved timing carries `data-state="unknown"` and **no** fabricated `0`; a measured row
carries source+age. **FAIL:** a missing timing renders `0`, or narration is shown as truth.

---

## J5 — Watch Spend
*Continuous; decisions at thresholds. Rules [R3,R4,R6,R7,R10]. Surface: rest `R3a` → drill `L-MONEY`.*

1. **Glance money at rest.** `R3a` shows exactly five values: `money.spend`, `money.burn`,
   `money.quota`, `money.wallet`, `money.leases`, plus a money-risk marker. `[R7]`
2. **Open the ledger.** Click `R3a` → `L-MONEY`: spend history, per-window usage, lease-by-lease
   reconciliation, settlement status, cost provenance.
3. **Read the arc and horizons.** `L-MONEY` shows the story session arc + `snowball_factor` `[R3]`,
   the EPM scenario `[R4]`, `T_max`/retry rate `[R7]`, and the batch scenario `[R6]`.
4. **Read value.** `L-COMPOSITION`/`L-MONEY` show accepted outcomes per arm and BVI `[R10]`.

**PASS:** `R3a` contains all five `[data-field^="money."]` nodes and an exception marker; an unknown
cost renders explicit `unknown`, never `$0.00`; `L-MONEY` shows the arc, EPM scenario, and T_max
with `[P]/[X]` provenance. **FAIL:** fewer than five values, a fabricated `$0.00`, or a ratio
without coverage.

---

## J6 — Intervene
*On a runaway/zombie/misbehaving session; per incident. Rules [R8,R9]. Surface: drill `R4b`.*

1. **Select the worker/session** (from `R1b` or `R2`) → `R4a` identity, then `R4b`.
2. **Watch the stream.** `R4b [data-attempt-feed]` replays history to `replay_complete`, then live
   frames (`step_start|step_finish|reasoning|operator|text|tool_use`) with follow/pause.
3. **Choose the action.** Each `[data-action]` chip carries `[data-action-target]`,
   `[data-action-authority]`, `[data-action-reversible]`, `[data-action-confirmation]`,
   `[data-action-receipt]`. Verbs: `attach/detach/copy-session/steer/interrupt` and owned
   `stop/respawn/rm/steer/logs`.
4. **Confirm if irreversible.** `interrupt` requires the exact phrase; `detach` is the
   non-destructive alternative.
5. **Read the receipt.** The response renders `[data-action-receipt]`.

**PASS:** exactly one event stream is open; every chip carries target/authority/reversibility/
confirmation/receipt; a disabled/ineligible action is not rendered as a live control; an action's
request matches its endpoint and returns a receipt. **FAIL:** more than one stream open, an action
with no confirmation/receipt, or a flag rendered as an automatic action.

---

## J7 — Audit
*At session/campaign close, at review, after a consequential act. Rules [R1,R5,R7,R10]. Surface: drill `L-REGISTRY AUDIT R1c`.*

1. **Open the audit lens** `AUDIT` from `J7`/`J11`: recording coverage (`recorded|missing`),
   decision records, and the decision ledger `[R3,R7,R10]`.
2. **Follow a decision to its receipt.** Click a decision → attributed actor, `decided_at`,
   artifact path, run/candidate binding.
3. **Follow lineage** `L-REGISTRY`: `supersedes`/`causes` links, `lifecycle_state`
   (`current|superseded|tombstoned`). `[R10]`
4. **Confirm no consequential act is unrecorded.** `R1c` surfaces residual process gaps.

**PASS:** every decision opens a receipt; `L-REGISTRY` shows canonical lineage distinct from the
runtime trace; an unrecorded consequential act appears as an `R1c` process gap, not silence.
**FAIL:** a decision with no receipt, or registry lineage merged with the runtime transcript.

---

## J8 — Enqueue
*Per campaign/fill. Rules [R6,R9]. Surface: drill `QUEUE`.*

1. **Preview.** Open `QUEUE`: what will be enqueued (cells/factors), budget/lease, queue depth,
   batch flags.
2. **Check admission.** The preview shows each job's lease; unbudgeted work is refused
   (fail-closed).
3. **Confirm.** `enqueue` / `clear` / `reinterleave` behind a confirm door; the response is a
   receipt `[data-action-receipt]`.
4. **Read depth.** Queue depth feeds the SLA/2× rule `[R9]`.

**PASS:** an unbudgeted cell cannot be enqueued; the preview names target/order/budget; enqueue
returns a receipt and the run ledger `R2` count increments. **FAIL:** a job enters the queue with
no lease, or a mutation fires with no preview/receipt.

---

## J9 — Route
*On demand, before a run/campaign; per task type. Rules [R1,R2,R5]. Surface: drill `R4a L-COMPOSITION`.*

1. **Select the task context** → `R4a` routing inputs beside the run (no peer routing board).
2. **Read the recommendation + evidence.** Per-model Grit `[R1]`, first-pass/WOC `[R5]`, narration
   penalty `[R2]`, each with its evidence class and coverage.
3. **Read the simulation.** `L-COMPOSITION` shows cost/quality per route with coverage.
4. **Choose the arm.** Route the task to the model/policy.

**PASS:** routing inputs and evidence appear beside the run context; a recommendation carries its
evidence class and coverage (a zero-coverage signal yields `unknown`, not a confident route).
**FAIL:** a routing recommendation with no evidence/coverage, or a required peer routing board.

---

## J10 — Claude Sessions
*Per background session. Rules —. Surface: drill `L-SESSIONS R4b`.*

1. **Open the roster** `L-SESSIONS`: sessions with ownership (`OWNED|EXTERNAL`), model, workdir,
   task, daemon status/PID.
2. **Open a session** → `R4b` owned actions: `start/stop/respawn/rm/steer/logs`.
3. **Act within ownership.** Owned-only controls; external sessions show relay only.
4. **Read logs / receipt.** `logs` returns bounded text; `stop` preserves the conversation for
   `respawn`.

**PASS:** owned actions appear only on `OWNED` sessions; daemon status is labeled; `stop` is
described as resumable via `respawn`. **FAIL:** an owned control on an EXTERNAL session, or an
action without a receipt.

---

## J11 — Record Close
*Every session close. Rules [R1,R5,R7,R10]. Surface: drill `AUDIT R1c L-REGISTRY`.*

1. **Open `AUDIT`** to confirm what ran: waves, merges, parks, open threads.
2. **Write the close record** (`session close`) — what ran, what merged, what parked, self-notes.
   `[R1,R5,R7,R10]`
3. **Confirm the receipt.** The append is rerun-safe and best-effort; the durable artifact lands
   and the report names its identity.
4. **Check residual gaps.** `R1c` shows any unrecorded consequential act.

**PASS:** a session close writes its record and shows a receipt; a rerun is a no-op; an unrecorded
consequential act surfaces as an `R1c` process gap. **FAIL:** a close that writes nothing and
reports success, or a decision without a receipt.

---

## Coverage

| job | rules served | primary surface | PASS assertion class |
|-----|--------------|-----------------|----------------------|
| J1 Glance | 1,2,5,7,10 | rest `R0 R1 R2 R3a R3b R3c` | geometry `ON-G1..G7` |
| J2 Triage | 1,5,8,9 | alert `R1b` → `R4a R4c R4b` | event `ON-A1` |
| J3 Decide | 5,7,8,10 | alert `R1a` → `R4a R4b R4c` | event `ON-A4` |
| J4 Inspect | 1,2,3,5,8,9 | drill `R4c R4d L-WORKFORCE` | geometry `G-18` |
| J5 Watch spend | 3,4,6,7,10 | rest `R3a` → `L-MONEY` | geometry `ON-G4` |
| J6 Intervene | 8,9 | drill `R4b` | event `E-6/E-7` |
| J7 Audit | 1,5,7,10 | drill `L-REGISTRY AUDIT R1c` | parity `ON-D4` |
| J8 Enqueue | 6,9 | drill `QUEUE` | event + admission fail-closed |
| J9 Route | 1,2,5 | drill `R4a L-COMPOSITION` | geometry `ON-D5` |
| J10 Claude sessions | — | drill `L-SESSIONS R4b` | ownership + receipt |
| J11 Record close | 1,5,7,10 | drill `AUDIT R1c L-REGISTRY` | receipt + rerun no-op |

Every job J1–J11 has a walkthrough; every rule 1–10 appears in at least one job's PASS path.
