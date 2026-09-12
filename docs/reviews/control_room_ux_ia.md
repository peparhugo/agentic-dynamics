---
status: accepted
---

# Control Room UX information-architecture adversary (u7)

**Reviewer:** `openai/gpt-5.6-sol`
**Date:** 2026-09-11
**Campaign:** `control_room_ux_repair`, phase `u7_adversary_ux_ia`
**Scope:** the u0 jobs-to-be-done, the u1 interaction model, the retained screenshots and gate
report in `apps/control_room/verification/`, and the implemented in-room drill-down paths. This
review asks whether the operator can finish each job, not whether a corresponding DOM region exists.

## Verdict

**FAIL - THE OPERATOR CANNOT COMPLETE THE REQUIRED JOB SET.**

The room now has a strong resting overview and substantially more operational surface than the
facelift it repairs. The screenshots show concurrent CLI-agent runs, typed evidence, per-run budget
bands, a selected worker feed, worker actions, an evidence ladder, timing labels, and a workbench
whose navigation names the re-housed capabilities. Those are real improvements.

They do not satisfy the u7 acceptance rule. A failed/stalled run cannot be followed from its
attention item through authoritative attempt evidence to a legal retry/escalate/cancel decision.
The selected worker surface has two competing feed/pause controls, and the actual per-cell Pause
control does not pause or buffer incoming events. The timing region displays the required field
names, but most decision-critical values are `unknown`. Approval and promotion remain eligibility
labels rather than executable safe-action objects. Several other u0 jobs have named workbench tabs,
but no retained screenshot or behavioral gate proves their end-to-end workflows.

Under the required fail-closed interpretation, the result is **0 PASS, 2 PARTIAL, 9 FAIL** across
u0's eleven jobs. One incomplete job is sufficient to fail; nine are incomplete.

## Acceptance Method

“Without navigating away” permits the documented in-room `R4` dock, Trends lens, and Workbench
overlay. It does not permit opening an external terminal or reconstructing a command from prose.

The classifications are deliberately strict:

- **PASS:** the screenshots and gate demonstrate an understandable path from trigger to evidence,
  legal action, confirmation where required, and visible receipt.
- **PARTIAL:** the room answers a meaningful part of the job, but a required source, state, or
  continuation is unavailable.
- **FAIL:** the operator cannot safely finish the job in-room, even if its label or a related control
  exists.

Primary screenshot evidence:

- `F-0_desktop_dark_1440x900.png` and `F-0_mobile_dark_390x844.png`: normal resting state.
- `F-3_desktop_dark_1440x900.png`: near-cap money state.
- `F-4_desktop_dark_1440x900.png`: explicit unknown-money state.
- `F-5_desktop_dark_1440x900.png`: stale/degraded projection state.
- `parity_dock_desktop.png` and `parity_dock_mobile.png`: selected run, worker, evidence, actions,
  and timing.
- `parity_workbench_desktop.png` and `parity_workbench_mobile.png`: re-housed workbench and
  workforce timing surface.
- `charts_desktop_dark_1440x900.png`: retained spend/throughput/failure/dependency trends.
- `live_desktop_dark_1440x900.png` and `live_mobile_dark_390x844.png`: live control-plane data.

The `gate_report.md` `PASS` is accepted as evidence of geometry, contrast, first paint, fixture
wiring, and non-empty regions. It is not treated as evidence that all jobs work: the parity class
checks endpoint requests and generic non-emptiness, exercises one representative Steer POST, and
accepts timing rows whose state is either `measured` or `unknown`
(`scripts/verify_control_room_rendering.py:1717-1887`).

## Blocking Findings

| ID | Severity | IA finding | Evidence | Required disposition |
|---|---|---|---|---|
| U7-IA1 | **BLOCKER** | The attention queue is not a drill-down path. | The resting screenshot names `run-failed` with action `inspect`, but only `#run-list` has click/keyboard handlers that call `openDock`; `#attention-list` has none (`app.js:1129-1165`). The selected screenshot opens `agent-01`, an approval candidate, not the failed target. | Make each run-linked attention item an addressable control that opens the exact run/attempt in `R4`, preserves focus return, and carries the item identity through live reconciliation. Add a stalled/failed screenshot beginning from the attention item. |
| U7-IA2 | **BLOCKER** | Stalled/failed triage terminates at inspection, not a safe decision. | `R4` shows identity, advisory/measured/source evidence, lease cost, and flag-backed Steer/Interrupt. It does not show retry, escalate, or cancel; the run projection also hard-codes attempt `1` and synthesizes several facts (`glance.py:307-339`). No screenshot demonstrates a stall classification or remaining-budget decision. | Add an authoritative stalled state and attempt chain, failure class, last tool, independent test result, remaining budget, and database-derived retry/escalate/cancel decision object with blast-radius preview and receipt. |
| U7-IA3 | **BLOCKER** | Controller decisions cannot be completed. | Resting and selected screenshots say `eligible approve` and `controller`, but the selected action band offers only Copy, Reattach, and flag-backed Steer/Interrupt. The u1 decision object requires target, epoch, gate, `candidate_sha`, rationale, safe action, reversibility, and receipt (`control_room_interaction_model.md:145-186`). | Consume the control packet's exact `safe_actions`; render approve/promote/cancel only when legal; preview the bound gate and candidate SHA; revalidate server-side; require the appropriate door; show the durable approval/promotion/decision record. |
| U7-IA4 | **BLOCKER** | Required step timings are labels without enough information to support a decision. | `parity_dock_desktop.png` renders queue wait, service time, first token, duration, token splits, and exit code as `unknown`. The Workforce lens shows steps, total cost, aggregate input/output tokens, median event gap, and last step rather than u1's p50/p95 queue wait, service time, and first-token latency by model. `parity.js:473-541,1123-1183` explicitly substitutes retained matrix telemetry for the missing ledger/control join. | Project `StepAttemptRecord` plus ledger `AttemptRecord` into the portal. Render per-attempt start/end, queue/service/first-token timing, token split, cost/provenance, exit/error, and verification; aggregate p50/p95 and retry rate by model over a named window. Keep genuine absence as `unknown`. |
| U7-IA5 | **HIGH** | The per-worker stream is not operationally usable as specified. | The dock shows both a `WORKER` feed with Pause and an `ATTEMPT FEED` with another Pause. The app-owned attempt feed buffers global transitions (`app.js:993-1046`), but the per-cell control only flips attributes/text while `appendWorkerEvent` continues appending and scrolling (`parity.js:294-302,1287-1296`). Detach, Clear, and Jump to live are absent. | Present one selected per-cell stream with a single follow/pause state. While paused, buffer to a visible bounded count and do not append/scroll; on resume, drain predictably. Add Detach, Clear, and Jump to live; label replay versus live and producer versus receipt time. |
| U7-IA6 | **HIGH** | Worker and queue actions use canned requests rather than operator-completable forms. | Worker Steer posts the fixed text `operator steer from the Control Room`; design input and Claude Steer use fixed `continue` (`parity.js:717-750,837-900,973-975`). Queue Enqueue passes a warning string but is marked reversible, so `actionChip` never opens that confirmation (`parity.js:165-193,997-1021`). | Require operator-entered prompts and explicit target context. Preview admission/budget before enqueue/run. Apply typed doors to irreversible acts and an explicit spend confirmation to enqueue. Treat payload-level `{ok:false}` as failure, not an HTTP-success receipt. |
| U7-IA7 | **HIGH** | The workbench restores destinations, but not the promised object-linked drill-downs. | The retained workbench screenshots show the tab labels and only the Workforce panel. They do not demonstrate Registry, Sessions, Queue, Routing, Docs, Audit, or Health content. `R4` contains no direct registry-lineage, routing, recording, or session inspector link, despite u1 §5.1 requiring those paths beside the selected context. | Capture and behaviorally gate every job-bearing panel. Add selected-object links that preserve run/cell/model context when opening registry, routing, money, audit, or session detail; do not make the operator search a global table again. |
| U7-IA8 | **HIGH** | Trust can contradict itself on the same resting screen. | In `F-5_desktop_dark_1440x900.png`, `R0` says projections are `degraded · 901s` and trust says `proj stale`, while `R3b` says `projections current · lag 0 · age 4s`. The operator cannot answer J1's health question from conflicting authorities. | Derive `R0` and `R3b` from one projection snapshot/epoch, and add a semantic assertion that state, lag, and age agree across mirrors. A stale fixture must never retain a current health line. |
| U7-IA9 | **MEDIUM-HIGH** | The retained screenshots do not prove a continuous spend trend. | `charts_desktop_dark_1440x900.png` draws changing spend/burn values, but all six rows show the same `observed_at` timestamp. The visual therefore cannot support a time-based burn judgement, even though the current snapshot and near-cap state are useful. | Preserve producer timestamps, order samples monotonically, label the retained window and gaps, and reject a “trend” whose timestamps do not advance. Connect the chart to provider usage/admission history rather than presentation-only samples. |
| U7-IA10 | **MEDIUM** | Mobile keeps the surfaces but damages object recognition and comparison. | The 390px resting captures truncate session, worktree, command, and model simultaneously. The selected dock is readable, but the operator must first infer which clipped row to choose. | Use a deliberate two-line mobile identity band with stable short IDs and explicit labels; prioritize failed/decision runs; preserve the action target before secondary evidence. Add a mobile failed-run triage capture, not only a normal roster and approval dock. |

## Job Completion Matrix

| Job | Verdict | Can the operator complete it in-room? | Disposition |
|---|---|---|---|
| **J1 - Glance** | **PARTIAL** | Normal and near-cap captures answer system, run counts, attention, money, health, and composition at rest. The stale fixture gives contradictory projection answers, and its `inspect` attention item does not open the affected object. | Reconcile trust/health mirrors and make attention items actionable before treating glance as authoritative under degradation. |
| **J2 - Triage a stalled or failed run** | **FAIL** | The operator can see a failure and can manually select a sampled run, but there is no demonstrated failed-item path, authoritative stall state, complete attempt/timing evidence, or retry/escalate/cancel decision. | Implement and gate the complete `R1 failure → R4 attempt → safe decision → receipt` path. |
| **J3 - Approve/cancel/promote/retire** | **FAIL** | Eligibility is visible; the decision door, preview, and resulting durable receipt are not. | Wire packet-derived actions through the verified commands/endpoints and show bound decision records. |
| **J4 - Inspect evidence and step timings** | **FAIL** | The evidence hierarchy is useful, but the required timing and token-split facts are predominantly unknown, so the operator cannot explain where time and cost went. | Expose authoritative attempt and ledger timing data; gate measured and unknown cases separately. |
| **J5 - Watch spend** | **PARTIAL** | The resting screen shows spend, burn, quota, wallet, leases, per-run cap bands, and honest unknowns. The retained “trend” has identical timestamps and does not prove continuous or authoritative burn history. | Keep the snapshot, but fix timestamped history and preserve source age/provenance through the Money drill-down. |
| **J6 - Intervene per worker/session** | **FAIL** | Interrupt has a typed door and receipts are structurally present, but worker selection, pause/follow, detach/clear/jump, editable steer input, and legal action gating are incomplete. | Replace the two-feed ambiguity with one usable stream and complete the worker action forms and receipts. |
| **J7 - Audit what happened** | **FAIL** | Registry and Audit tabs exist, but the screenshots do not show their contents and the selected run has no direct canonical-lineage or durable receipt link. | Add run-bound decision/actuation record IDs, full lineage, coverage/truncation state, and an audited end-to-end receipt fixture. |
| **J8 - Start/enqueue work** | **FAIL** | Queue and Sessions tabs exist, but no screenshot proves a budget-aware launch. Enqueue lacks an effective spend confirmation and no admission preview is visible. | Show matrix/goal/model/workdir, queue delta, lease/cap effect, confirmation, payload-aware result, and durable receipt before claiming completion. |
| **J9 - Route/choose a model** | **FAIL** | A Routing tab exists, but no captured path places recommendation inputs and evidence beside the selected run as u1 requires. The operator must leave run context and inspect a generic payload. | Link selected task/run context into a typed recommendation view with cost, quality, uncertainty, and source provenance. |
| **J10 - Manage background Claude sessions** | **FAIL** | The implementation has a Sessions lens and owned-session controls, but the screenshots do not demonstrate ownership, logs, or action results; Steer is a canned `continue`, owned logs/detach are not available as the contract specifies. | Capture and gate owned/external states, editable steer, logs, stop/respawn/rm, detach semantics, daemon state, confirmation, and receipts. |
| **J11 - Record/close the operator session** | **FAIL** | Neither the resting screen nor a documented drill-down exposes session close, decision-record completeness, beliefs, scoreboard, or reflection. Recording Audit is not a substitute for closing the current AIO session. | Add an explicit session-close object that previews included decisions/open threads/self-notes and invokes the existing verified close path with a durable record. |

## Stalled-Run Walkthrough

The required incident path currently breaks at every transition after detection:

1. **Detect:** PASS. `R1` visibly names a failed target and assigns `inspect`.
2. **Open the exact target:** FAIL. The attention item is not interactive; the operator must scan the
   bounded roster and hope the target is present.
3. **Confirm stall versus failure versus designed wait:** FAIL. No retained screenshot shows a
   stalled state, heartbeat age, retry chain, or checkpoint distinction in the selected object.
4. **Inspect causal evidence:** PARTIAL. Narration, measured status, commit, lease, and event rows are
   visible, but several values are projected placeholders and the independent timing/test evidence is
   incomplete.
5. **Choose a safe next action:** FAIL. Retry, escalate, and cancel are absent; Steer/Interrupt are
   available only when a supervisor flag happens to map to the selected session.
6. **Preview blast radius and budget:** FAIL. The decision-object preview required by u1 §2.3 is not
   shown.
7. **Act and verify the receipt:** FAIL. No stalled-run action is available, so no receipt can close
   the incident.

**Stalled-run verdict: FAIL.** The room detects a problem but does not yet function as a triage-to-
decision control surface.

## Per-Worker Usability Verdict

| Requirement | Verdict | Reason |
|---|---|---|
| One selected per-cell stream | **FAIL** | The dock presents a per-cell Worker feed and a separate Attempt Feed, each with Pause. |
| Retained replay then live boundary | **PARTIAL** | The endpoint emits the boundary, but the screenshot does not identify replay rows versus live rows. |
| Honest event timestamps | **PARTIAL** | Missing producer timestamps render `now`, but the row does not distinguish receipt time from producer time. |
| Follow/pause behavior | **FAIL** | The per-cell Pause changes attributes only; incoming rows still append and auto-scroll. |
| Bounded stream | **PASS** | The per-cell list is capped at 40 rows and the app-owned feed at 8. |
| Clear / jump live / detach | **FAIL** | These required controls are absent. Reattach is not an equivalent Detach control. |
| Worker actions | **PARTIAL** | Copy, Reattach, Steer, and typed Interrupt are visible, but Steer has no editable prompt and actions depend on a flag mapping rather than run state. |
| Action receipts | **PARTIAL** | Receipt UI exists, but the retained gate exercises only a fixture-backed Steer and does not prove durable recording. |

**Per-worker verdict: FAIL.** It is inspectable, but not yet safely operable.

## Step-Timing Visibility Verdict

The timing region is visually present and honestly labels missing values `unknown`; that satisfies
the no-fabricated-zero principle. It does not satisfy J4 or u1 §3.3's requirement for information on
screen. Queue wait, service time, first-token latency, duration, answer/explanation token split, exit
code, and independent verification must be populated when their authoritative records exist. The
Workforce lens must then aggregate those same facts by model over a named window, rather than treat
inter-event gap as a substitute.

**Step-timing verdict: FAIL FOR JOB COMPLETION; PASS FOR HONEST EMPTY-STATE SEMANTICS.**

## Required Disposition Order

1. Close **U7-IA1/U7-IA2** together with a tested failed/stalled attention-to-decision path.
2. Close **U7-IA3/U7-IA4** by exposing packet safe actions and authoritative attempt timing/evidence.
3. Close **U7-IA5/U7-IA6** with one real per-cell stream, working pause/follow, editable action forms,
   confirmations, and payload-aware receipts.
4. Close **U7-IA7** by making every workbench job object-linked and retaining a screenshot plus
   behavior test for each job-bearing panel.
5. Close **U7-IA8/U7-IA9** so trust mirrors and temporal charts cannot contradict or fabricate a
   usable trend.
6. Close **U7-IA10**, then repeat the stalled-run walkthrough at 1440x900 and 390x844.

**Final disposition:** keep the current semantic/feature gate as a structural regression rail, but
do not treat its `PASS` as UX-IA acceptance. The room remains **REWORK REQUIRED** until every u0 job
has an in-room path from trigger through authoritative evidence to a legal action and visible durable
receipt.
