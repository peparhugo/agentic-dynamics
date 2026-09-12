---
status: accepted
---

# Control Room repair — design critique (campaign `control_room_research_repair`, p4)

**Reviewer:** `openai/gpt-5.6-luna`  
**Date:** 2026-09-11  
**Scope:** `docs/research/control_room_direction.md` (p1),
`docs/research/control_room_ia.md` (p2), and the repaired catalogs/skills. This is an adversarial
design review. It does not change the reviewed artifacts.

## Verdict

**REWORK REQUIRED — the direction is more disciplined, but the design is not yet recognizably a
multi-CLI-agent control surface.**

The p1 document successfully centers the product thesis on a live run, evidence ladder, and governed
action. It also explicitly rejects the old four-board layout, static topology, unconditional chart
defaults, palette-only navigation, and "flight deck" mood language. Those are real improvements.

The implementation shape described by p1/p2 nevertheless remains a familiar dashboard shell:

```text
scope/truth bar -> attention inbox -> run roster -> constraint rail -> selection dock
```

The current prose does not make the CLI-agent identity visible enough in the resting composition. A
reviewer could still mistake the proposed screen for an observability dashboard with runs substituted
for services. The distinctiveness is asserted in the thesis but not yet carried by the first-screen
objects, visual grammar, or a concrete terminal interaction model.

The p0/p3 support problem also matters here: the direction presents catalog counts as `[X]` grounding,
while the entailment re-check found remaining adjacent-label promotion. The design may use those
patterns as bounded inspiration, but it cannot use the current counts as proof of a distinctive
external composition until p3 E1/E4 are repaired.

## 1. Review method

1. Read p1's thesis, run-object anatomy, resting-screen composition, distinctive-moves table, generic
   grammar rejection, and acceptance criteria.
2. Read p2's R0–R4 regions, hierarchy, glance mapping, crowding tradeoffs, mobile behavior, and
   screenshot acceptance checks.
3. Compared the result against the prior design critique's D1–D12, especially D1 generic dashboard
   grammar, D5 dated retro-ops costume, D6 chart cargo cult, D8 terminal grammar, D9 generic transcript
   detail, and D12 control semantics.
4. Checked whether each claimed distinctive move is either grounded by an existing repaired catalog
   item or explicitly `[P]`. Where a catalog count is still semantically disputed by p3 E1/E4, this
   review treats it as provisional rather than as proof.

## 2. Findings

| ID | Severity | Finding | Evidence | Required disposition |
|---|---|---|---|---|
| D1 | **BLOCKER** | The resting composition is still dashboard costume, despite rejecting the dashboard grammar in prose. | p2 defines `R0 scope/truth bar → R1 attention inbox → R2 run roster → R3 constraint rail → R4 selection dock` (`control_room_ia.md:27-51`). p1's own rejected r5 shell has the same structural vocabulary: rail/strip/board/dock/footer (`control_room_direction.md:332-340`). | Replace at least one primary structural axis with an agent/run-native grammar. The first screen must visibly organize around agent session, current command/tool phase, worktree/terminal target, evidence authority, and governed action — not only around a roster plus dashboard side rail. Add a blind screenshot test against a generic Grafana/Datadog-like comparator. |
| D2 | **BLOCKER** | The screen is not yet recognizably for operating multiple CLI AI agents. | p1's resting row fields are `run_id`, spec/cell, phase, model×condition×policy, lifecycle, changed-at, cost, attention, decision (`control_room_direction.md:199-201`); p2 repeats the same run-centric fields (`control_room_ia.md:87-93`). Agent/session objects are deferred to R2 object types and R4 inspectors (`control_room_ia.md:228-239`). The first screen does not visibly show terminal/session identity, current command/tool, worktree target, provider/model together, or a CLI address token. | Add a mandatory agent/session identity band to each actionable run row or to the primary roster header: session/agent id, worktree or terminal target, current command/tool, provider/model, and attempt. Define a visible address grammar from p1 D8 (`run`, `phase`, `attempt`, `session`, `worktree`, `lease`, `flag`, `approval`, `record`) rather than merely listing object classes. A reviewer must identify the product as a multi-CLI-agent control surface from a screenshot without reading this document. |
| D3 | **HIGH** | The no-interaction contract creates a cluttered information wall, and the region budget is not measurable. | p2 requires all R0–R3 simultaneously, five money numbers, worker/projection health, four-dimensional composition counts, inbox metadata, and per-value source/age chips (`control_room_ia.md:58-112`, `:139-156`, `:268-274`). T1 says the rail can collapse or move below the roster (`:165-174`), which conflicts with the default-viewport contract and AC-1/AC-2 (`:300-321`). | Specify a minimum desktop viewport, pixel/line budgets for R0/R1/R2/R3, minimum readable text size, maximum visible inbox rows, and the exact compact schema for a narrow-desktop ticker. A ticker must still answer ON-G1/G4/G7, or the contract must explicitly split at a named breakpoint. Test comprehension and correct next-action selection, not just DOM presence. |
| D4 | **HIGH** | Exemplar grounding establishes familiar components, not a distinctive composition. | p1 cites master-detail, trace trees, timeline, eval loop, prompt registry, logs, tables, keyboard operation, tokens, and SVG micro-visuals (`control_room_direction.md:274-304`). p3 reports that several supports are still semantically inflated and that some patterns are thin or single-family (`docs/reviews/control_room_repair_entailment.md:53-80`, `:100-116`). | Separate three claims in the direction: (1) a cited exemplar demonstrates a pattern; (2) the repository requires a local behavior; (3) the composition of those patterns is a `[P]` product decision. Do not describe the composition as externally grounded. Attach record-level evidence only after p3 E1/E4 are repaired; otherwise downgrade the move to `[P]`. |
| D5 | **HIGH** | The visual identity is explicitly declared non-differentiating, leaving no visual grammar that makes the run/evidence/control boundary legible. | p1 says dark/light tokens, restrained motion, and accessible status are quality bars and "never the differentiator" (`control_room_direction.md:64-67`). Yet the remaining concrete language is a tokenized console: fixed rail, chips, tables, logs, timeline, status colors, SVG micro-visuals, and provenance chips (`control_room_ia.md:60-112`; p1 §7/§10/§11). | Define a domain-specific visual grammar, not a mood: agent/session identity, attempt boundaries, agent-reported vs independently verified evidence, proposed vs controller-authorized action, lease/cost constraint, and terminal target must have distinct compositional treatments. State which visual behaviors are `[P]`; keep tokens/accessibility as hygiene. |
| D6 | **MEDIUM-HIGH** | Provenance and attention metadata risk chip soup and weaken scan priority. | p1 requires source, age, scope, partiality, revision, semantics, and event links on consequential values (`control_room_direction.md:380-396`). p2 simultaneously packs inbox identity, priority, timing, scope, state, authority, action, five money numbers, health rows, and composition counts into the resting screen (`control_room_ia.md:74-106`). | Use tiered disclosure: at glance show state, age, and one short authority marker; show full provenance and event links in R4. Give governed decisions, operational failures, and advisory flags visibly different channels. Add a scan-time test: an operator must select the correct next action without parsing every metadata chip. |
| D7 | **MEDIUM-HIGH** | The action boundary is strong in detail but not identity-bearing on the resting screen. | p1 correctly specifies target, scope, epoch, blast radius, budget effect, reversibility, and receipt (`control_room_direction.md:162-181`, `:250-256`), but p2 hides the evidence ladder and safe-action preview in R4 (`control_room_ia.md:108-112`). At rest only a decision flag/summary is visible (`:79-85`, `:144-152`). | Make the run row visibly distinguish `observe`, `inspect`, `approve`, `promote`, `cancel`, or `retire` eligibility, while keeping the full preview in R4. The resting design should communicate that this is a governed action surface, not merely a monitoring list. Never turn the summary into an automatic action. |
| D8 | **MEDIUM** | Mobile and narrow-desktop behavior preserves route identity but not the same design contract. | p2 explicitly removes ON-G7 on mobile (`control_room_ia.md:197-207`, `:317-318`) and permits R3 to move below the roster on narrow desktop (`:165-174`). That may be a reasonable product policy, but it means "one resting screen answers ON-G1..G7" is not globally true. | Name the contract as desktop glance vs mobile triage/inspection. Define a breakpoint and a narrow-desktop minimum. Add screenshots for desktop, narrow desktop, mobile, selected run, and a generic-dashboard comparator. Each must state which needs are guaranteed and which are deliberately deferred. |
| D9 | **MEDIUM** | The design still risks dated retro-ops styling because the rejected ingredients remain available without a restraint test. | p1 rejects "flight deck" language, but still permits dark-first token systems, status hues, sparklines, gauges as policy, SVG micro-visuals, dense rows, fixed rails, and terminal-native styling (`control_room_direction.md:64-67`, `:358-376`, `:417-437`). The prior adversary identified this exact 2010s monitoring-console risk (`control_room_research_design.md:171-199`). | Define a restraint budget: no decorative glow/pulse, no uppercase telemetry texture as decoration, no repeated neon status marks, no card field by default, and no chart whose only purpose is atmosphere. Validate with a blind “generic dashboard vs Control Room” comparison and require the run/evidence/action distinction to carry recognition. |

## 3. What is now working

The rework is not a failure of concept. These parts are materially better than r5:

- The live run, rather than a peer-board taxonomy, is the stated unit of work (`direction.md:43-67`).
- The evidence ladder separates narration, runtime measurement, independent verification, cost, and
  controller decision (`direction.md:131-160`).
- Safe-action preview and the machine-proposes/controller-disposes boundary are explicit
  (`direction.md:162-181`, `:250-256`).
- The r5 generic elements are rejected by name (`direction.md:332-351`).
- The p2 IA gives every desktop glance need a named region and preserves the roster during selection
  (`control_room_ia.md:139-156`, `:220-239`).
- Accessibility, no-regression, reduced-motion, focus, keyed reconciliation, and one-stream
  invariants remain visible constraints (`direction.md:442-472`).

These strengths should be retained while the first-screen identity and density contract are repaired.

## 4. Required disposition order

1. **Resolve D1/D2 together.** Recompose the resting screen so an agent/session/worktree/current
   command identity is visually primary, not merely available in drill-down. Define the terminal
   address grammar and show its context in the default roster.
2. **Resolve D3/D8.** Establish desktop, narrow-desktop, and mobile contracts with exact region budgets,
   breakpoint behavior, ticker schema, and screenshot comprehension checks. Do not call DOM presence a
   pass for a glance contract.
3. **Resolve D4 after p3 E1/E4.** Treat repaired catalog counts as provisional until direct-label
   entailment is fixed. Keep composition decisions `[P]` even when component exemplars are `[X]`.
4. **Resolve D5/D9.** Specify an agent-run visual grammar and restraint budget. Tokens, color contrast,
   reduced motion, and SVG technique are hygiene; they cannot be the identity claim.
5. **Resolve D6/D7.** Tier metadata and surface action eligibility at rest without turning the screen
   into chips or an automatic actuator.
6. **Rerun this design adversary after the next direction revision.** The acceptance gate is a blind
   screenshot set: default desktop, narrow desktop, mobile, selected-run evidence/action, and a generic
   observability-dashboard comparator. Reviewers must answer without prose: “What is this?”, “Which
   agent/run needs me?”, and “What governed action can I safely take?”

## 5. Acceptance gate

Do not treat the direction as design-complete until D1–D4 are resolved, p3's support entailment E1/E4
is repaired or explicitly downgraded to `[P]`, and the blind screenshot set demonstrates:

1. recognizable multi-CLI-agent operation;
2. a visually distinct run/evidence/decision grammar;
3. readable simultaneous glance answers at the named desktop breakpoint;
4. explicit, honest narrow-desktop and mobile tradeoffs; and
5. no dated dashboard-cosplay cues carrying the identity.
