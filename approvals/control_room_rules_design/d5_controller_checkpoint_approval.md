# Controller approval — control_room_rules_design, d5_controller_checkpoint

**Signed:** controller (peparhugo) · **Date:** 2026-09-11 · **Spec:** workflows/repository/control_room_rules_design.yaml (bd90037cc)

## Decision

**APPROVED — design and read-only projection layer only**, with a staged build order. This
approval authorizes the design artifacts (rule map, gaps, backend requirements, surfaces, states,
wireframe, walkthroughs) and the 11 read-only projections. It does NOT authorize the full
26-writer program at once.

## Staging conditions

1. **Phase 0 — truth in the ledger first.** Every `LEDGER_FIELDS` entry with no writer gets either
   a writer or an explicit "no writer — not measured" marking in the room. No field is rendered
   that the ledger does not emit.
2. **Phase 1 — operational core.** Workflow-management records (job state, attempt/retry, step
   timings, escalations, queue wait, batch flags, budget/SLA) + **blocked-first triage** + the
   per-worker event stream / actions surface. This phase must pass the parity/render gate before
   anything else starts.
3. **Phase 2 — instrumented-rule surfaces.** Rules 1 Grit, 2 Explanation Tax, 5 First-Pass, 10 BVI
   (measured `[M]`/`[C]`, currently no room surface).
4. **Phase 3 — modeled/external rules + lenses.** Rules 3 Snowball, 4 EPM, 6 Batch, 8 Cascade,
   9 SLA shown as clearly-labeled scenario/model areas (`[C]/[P]`), never as live readings. The
   14 lenses are trimmed to those the operator jobs require; the rest are deferred.

Each phase carries its own gates (render + parity + job walkthroughs) and its own adversarial
review. No phase may start before the previous phase's gate passes.

SIGNED-BY-OPERATOR: peparhugo (controller) 2026-09-11
