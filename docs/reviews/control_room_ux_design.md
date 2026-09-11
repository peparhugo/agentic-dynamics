---
status: accepted
---

# Control Room UX design adversary (u6)

**Reviewer:** `openai/gpt-5.6-luna`  
**Date:** 2026-09-11  
**Scope:** the retained screenshots in `apps/control_room/verification/`,
`apps/control_room/verification/gate_report.md`, the u0 foundation, the u1 interaction model,
and the u2 parity inventory. This is a screenshot and acceptance-contract review, not a code
quality review.

## Verdict

**FAIL - REWORK REQUIRED.**

The repaired room is recognizably a control surface for many CLI agents. The desktop resting
screen makes concurrent sessions, worktrees, commands, models, lifecycle, evidence classes, cost,
and attention visible. The selected-run dock visibly restores a bounded worker feed, worker
actions, an evidence ladder, and timing rows. The workbench also visibly names the re-housed fleet,
queue, session, routing, docs, audit, health, registry, and workforce surfaces.

The `PASS` gate is therefore meaningful for geometry, rendering, fixture wiring, and presence of
the restored regions. It is not sufficient for this adversarial verdict. Two required operator jobs
remain visibly incomplete: a controller cannot complete the displayed approval decision from the
selected run, and the step-timing surface mostly exposes legal `unknown` placeholders rather than
the required ledger/control timing facts. The room is substantially repaired, but the brief says
to pass only when the principles hold and parity is visible; those two gaps block that conclusion.

## Review Method

I inspected the representative desktop and mobile resting captures, the selected-run dock,
workforce lens, and live/degraded captures before consulting implementation details. The primary
captures were:

- `F-0_desktop_dark_1440x900.png`
- `F-0_mobile_dark_390x844.png`
- `parity_dock_desktop.png`
- `parity_dock_mobile.png`
- `parity_workbench_desktop.png`
- `live_desktop_dark_1440x900.png`
- `live_mobile_dark_390x844.png`

I then compared those pixels with the u0 jobs and principles, the u1 action/timing contract, and
the u5 gate implementation. The gate report is treated as mechanical evidence, not as a substitute
for judging whether an operator can actually finish each job.

## Findings

| ID | Severity | Finding | Evidence | Disposition |
|---|---|---|---|---|
| U6-D1 | **BLOCKER** | A displayed controller decision is not executable from the run inspector. | The resting run and attention item show `eligible approve`, `controller`, and `receipt recorded`. The selected dock exposes copy, reattach, steer, and interrupt, but no approve, promote, cancel, or safe-action door. `parity.js` renders the eligibility token and flag-backed actions, not the control-packet `safe_actions`. | Add database-derived decision actions to the selected run. Render target, epoch, gate/candidate, authority, reversibility, budget effect, confirmation door, and inline receipt. Keep the action disabled or absent when the authoritative transition is illegal. Add a browser assertion that an eligible approval action posts to its verified endpoint and renders the receipt. |
| U6-D2 | **BLOCKER** | Step-timing parity is present as a scaffold but not as the required timing information. | `parity_dock_desktop.png` shows queue wait, service time, first token, duration, token splits, and exit code as `unknown`; only retry, cost, and verification are populated. `parity_workbench_desktop.png` shows retained step count, total cost, token totals, and a median timestamp gap, not p50/p95 queue/service/first-token metrics by model. The implementation explicitly states that ledger timing fields are not exposed by the portal. | Join the selected attempt to `StepAttemptRecord` and ledger `AttemptRecord` data, preserving unknown when a source is absent. Render measured queue wait, service time, first-token latency, duration, token answer/explanation split, exit code, verification, and provenance. Make the workforce lens report the required aggregate window and p50/p95 fields by model. Add fixtures with both measured and absent timing values. |
| U6-D3 | **HIGH** | The worker stream is visible, but replay/live provenance is not legible enough for an audit decision. | The dock contains seed rows and event rows, and has a Pause control. The captured event fixtures omit producer timestamps and the rendered rows show `seed`/`now` rather than a visible replay-to-live boundary or event source state. The u1 contract requires ordered events, honest producer/received timestamps, and a replay boundary that separates retained history from the live window. | Keep seed facts visually distinct from retained event replay and live frames. Show `replay`, `live`, or `received now` state on each applicable row, retain producer timestamps when present, and expose the replay-complete boundary. Extend the fixture with timestamped replay and live events and assert pause buffering plus drain-on-resume. |
| U6-D4 | **HIGH** | Mobile triage preserves the surface but compresses the agent grammar below the desktop level. | `F-0_mobile_dark_390x844.png` and `live_mobile_dark_390x844.png` truncate session, worktree, command, and model values. The row remains identifiable to a familiar operator, but a stranger must infer field meaning from order and clipped text. This weakens the u0 typed-address and operator-first principles at the required 390px viewport. | Give mobile rows a deliberate two-line identity band with a stable short session token, target basename, command/tool, provider/model, attempt, and lifecycle. Preserve explicit labels or semantic markers; do not rely on color or column position. Add a mobile comprehension assertion rather than only geometry checks. |
| U6-D5 | **MEDIUM-HIGH** | The feature-parity gate proves fixture non-emptiness and one mutation, not full capability behavior. | `gate_report.md` reports `PASS` and zero violations. The gate checks that each workbench lens requests its expected endpoint and renders fixture content, then probes one attention-lens steer POST. It does not exercise controller safe actions, every session/queue/docs/audit mutation, timing-source fidelity, receipts, or replay/pause behavior. | Retain the current mechanical gate, but add semantic parity cases for every irreversible action door, action receipt, ownership restriction, control-packet eligibility, timing provenance, replay/live labeling, and paused-feed buffering. Report fixture-limited claims explicitly. |

## Principle Dispositions

| u0 principle | Verdict | Pixel judgment |
|---|---|---|
| Operator-first ranking | **PASS** | The resting screen gives reserved space to attention, the agent roster, cost, and health. A return-to-screen operator can see active work and risk without opening a lens. |
| Addressable run objects | **PASS DESKTOP / PARTIAL MOBILE** | Desktop rows carry session, target, command, model, attempt, phase, and lifecycle. Mobile truncation weakens the same grammar. |
| Typed evidence | **PASS** | The resting rows and dock distinguish `said`, `measured`, `source`, cost, decision, and receipt. The visual separation is stronger than the pre-repair room. |
| Governed decisions with receipts | **FAIL** | Eligibility and receipt state are visible, but the displayed approval decision has no executable safe-action door in the dock. |
| Explicit unknowns | **PASS** | Unknown timing and cost values are shown as `unknown`, not fabricated zeroes. This is honest, even though the missing timing join remains a parity defect. |
| Bounded per-worker stream | **PASS WITH CAVEAT** | The dock visibly contains a bounded feed, Pause control, worker target, and steer/interrupt actions. Replay/live and timestamp provenance need stronger visual treatment. |
| Persistent master-detail selection | **PASS** | The selected-run dock overlays the room while the roster remains visible, and the mobile dock remains usable as a focused inspection surface. |
| Calm under load | **PARTIAL** | The desktop composition is legible and dense without decorative chart cargo. Mobile truncation and the large number of compact status fields increase interpretation cost during an incident. |

## Parity Disposition

The old-room capability set is no longer silently absent. The workbench visibly exposes named
destinations for the old fleet, queue, session, routing, docs, audit, health, registry, and
workforce concerns, and the gate confirms that those lenses are wired to their endpoints with
fixture content. The selected dock also visibly restores the two capabilities most clearly lost in
the facelift: per-worker event/actions and step-timing rows.

Parity is nevertheless **CONDITIONAL**, not complete:

- **Preserved/re-housed:** the resting roster, attention queue, cost/health/composition summary,
  worker event feed, worker actions, queue controls, Claude/design sessions, routing, docs health,
  recording audit, registry, projection health, and workforce lens are visibly represented.
- **Not yet equivalent:** controller decision actions are reduced to eligibility text, and the
  timing surface is reduced to retained event samples plus explicit unknowns instead of the full
  ledger/control join required by u1 §3.3.
- **Not yet proven by the gate:** all mutation receipts, safe-action legality, replay/live
  semantics, pause buffering, and measured timing provenance.

The explicit replacement decisions for routing and registry remain acceptable: the workbench and
selected-run evidence destination make those capabilities addressable without restoring a generic
peer-board layout. No replacement reason excuses the missing approval action or timing data.

## What To Retain

- The agent-run roster is the dominant resting object and reads as concurrent CLI work rather than a
  generic service list.
- Desktop identity bands visibly combine session, worktree, command, model, attempt, and lifecycle.
- Advisory narration is separated from measured verification and source evidence.
- The selected dock keeps the roster visible while exposing worker events, actions, evidence, and
  timing regions.
- Unknown values are explicit and honest rather than silently defaulted to zero.
- The workbench is a coherent re-housing strategy for old-room capability parity.
- The render gate's geometry, contrast, first-paint, console, and endpoint-wiring checks should stay
  as regression rails.

## Required Disposition Order

1. Resolve **U6-D1** by wiring control-packet safe actions and receipts into the selected-run
   decision object. Do not declare approval/promotion parity from an eligibility label alone.
2. Resolve **U6-D2** by exposing the authoritative ledger/control timing join and the required
   workforce aggregates. Preserve explicit unknowns for genuinely absent fields.
3. Resolve **U6-D3** with visible replay/live and timestamp provenance, then test pause buffering and
   resume behavior using timestamped fixtures.
4. Resolve **U6-D4** with an explicit mobile identity grammar and a blind comprehension check at
   390px.
5. Expand **U6-D5** so the report distinguishes structural fixture parity from behavioral feature
   parity. Re-run the screenshot adversary after those checks pass.

**Disposition:** retain the current gate as a useful mechanical `PASS`, but record the overall UX
acceptance as **FAIL / REWORK REQUIRED** until the controller decision door and authoritative timing
surface are visible and operable.
