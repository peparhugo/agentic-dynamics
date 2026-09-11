---
status: accepted
---

# Control Room repair — information architecture re-check (campaign `control_room_research_repair`, p5)

**Reviewer:** `openai/gpt-5.6-sol`  
**Date:** 2026-09-11  
**Scope:** `docs/research/control_room_ia.md` (p2), checked against the authoritative r1
`ON-G1..G7` needs, the p1 direction, and the p3/p4 repair adversaries. This is a read-only adversarial
review; it records findings and required dispositions without editing the reviewed artifacts.

## Verdict

**FAIL — the IA is a useful 1440×900 proposal, not yet a proof that ONE resting screen answers
`ON-G1..G7` without navigation.**

p2 materially improves r5: it places each need in a named R0–R3 region, keeps a run roster visible,
defines a durable attention model, separates disclosure from alert lifecycle, and records its mobile
tradeoff. The defect is now sharper and therefore easier to repair: the documents promise different
glance contracts, required answers may scroll or move below the fold, and the acceptance suite mostly
tests region/DOM presence rather than whether a human can see and correctly interpret each answer.

Per-need result: **PASS 1, PARTIAL 4, FAIL 2**. `ON-G2` is the only clean pass. `ON-G1`, `ON-G3`,
`ON-G5`, and `ON-G6` are partial; `ON-G4` and `ON-G7` fail across the claimed breakpoints.

## 1. Review method

1. Took r1 §4.1 as authoritative: all seven `ON-G*` needs are explicitly "At a glance (no
   interaction; the resting screen)" (`control_room_questions.md:347-362`).
2. Walked each need through p2's mapping table (`control_room_ia.md:139-156`), then traced every
   referenced region through the region definition, hierarchy, crowding fallback, selected state,
   mobile policy, and acceptance checks.
3. Treated "at rest" according to p2's own definition: visible in the default viewport, with below-fold
   placement a glance failure (`control_room_ia.md:19-23`).
4. Checked the p1 direction for contract consistency, especially money, fleet shape, and the glance
   acceptance statement (`control_room_direction.md:308-326`, `:400-413`).
5. Distinguished four test classes: screenshot geometry, blind comprehension, browser/accessibility
   behavior, and event/network state. A screenshot cannot prove focus return or stream multiplicity.

## 2. Findings

| ID | Severity | Finding | Evidence | Required disposition |
|---|---|---|---|---|
| IA1 | **BLOCKER** | The governing documents define incompatible glance contracts. | r1 puts `ON-G1..G7` at rest (`control_room_questions.md:352-362`). p1 reduces `ON-G4` to a money-risk exception and moves its full answer to run context/Money lens (`control_room_direction.md:317-318`), moves `ON-G7` to a secondary composition lens (`:322`), and says the resting screen answers only `ON-G1..G6` (`:409`). p2 claims all seven at desktop (`control_room_ia.md:139-156`) but explicitly removes `ON-G7` on mobile (`:197-207`, `:317`). | Establish one authoritative contract per breakpoint. Either restore the complete `ON-G4`/`ON-G7` answers at every claimed resting breakpoint or formally narrow r1 and align the direction, IA headline, mapping, and acceptance tests. |
| IA2 | **BLOCKER** | Internal scrolling and the narrow-desktop fallback defeat p2's own definition of “at rest.” | R3 may scroll internally (`control_room_ia.md:95-107`) although §3 says R2 is the only default scrolling region (`:132-135`). At insufficient height/width, R3 may collapse to an unspecified ticker and render fully beneath the roster (`:165-174`). R3 contains required `ON-G1`, `ON-G4`, and `ON-G7` answers. p2 defines below-fold placement as failure (`:19-23`). | Define width **and height** breakpoints and the complete visible schema at each. Required glance values must not depend on page/R3 scrolling. If a ticker remains, enumerate the worker/projection state, all five money values, and bounded fleet-composition tokens it preserves. |
| IA3 | **CRITICAL** | `ON-G4` is not guaranteed at rest. | The authoritative need asks for spend, burn, provider quota, wallet, and reserved leases (`control_room_questions.md:359`). p2 assigns all five to R3a (`control_room_ia.md:99-101`, `:149`), but R3 can scroll or move below the fold. The mobile acceptance check names R0/R1/recent runs, not the five money values (`:317`). p1 separately says only money risk is at rest (`control_room_direction.md:317-318`). | Decide whether `ON-G4` means the five labelled values or state+exception. If the original need stands, reserve a visible, bounded five-value row at every qualifying breakpoint and test each label/value. If narrowed, amend r1 and all downstream claims explicitly. |
| IA4 | **CRITICAL** | `ON-G7` is not satisfied as a universal no-interaction need. | R3c promises model × condition × provider × lifecycle counts (`control_room_ia.md:105-106`, `:152`) but gives no cardinality/truncation rule and may scroll. Mobile deliberately omits it (`:197-207`, `:317`). p1 calls fleet shape a secondary lens (`control_room_direction.md:322`). | Define a bounded visible rollup (for example four marginals, each capped with `other` and `unknown`) and keep it in the initial viewport, or formally move `ON-G7` out of the universal glance contract. |
| IA5 | **HIGH** | Required answers remain split, forcing cognitive joins and potentially mixing freshness. | `ON-G1` is split between R0 connection/control/epoch and R3b workers/projections; `ON-G5` is duplicated across R1a and an R2 flag; `ON-G6` is a global degraded count plus chips distributed across R2/R3a/R3b (`control_room_ia.md:146-152`). Co-location avoids navigation but does not ensure one coherent answer or one epoch. | Give each need one canonical answer region and make other occurrences navigational mirrors. For split health/truth, expose a shared observation epoch/age and state whether the global answer is complete or only a summary. Remove duplicative writers. |
| IA6 | **HIGH** | Fixed inbox categories can bury the most serious alert. | R1 is fixed-height and pins decisions before failures/risks (`control_room_ia.md:74-85`, `:121-127`). No global severity/actionability ordering or reserved critical capacity is defined. A backlog of low-urgency decisions can consume the visible rows while a new failed run lands below the fold. | Rank all R1 items by global severity + actionability, or reserve visible slots per critical class. Add a saturated-inbox fixture proving a newly critical failure remains visible without scrolling. |
| IA7 | **HIGH** | The information density is unbounded, so “all visible” is not an implementable contract. | The screen combines an inbox with identity/timing/state/authority/action, detailed roster rows, five money values, worker/projection health, four-dimensional composition, and source/age chips (`control_room_ia.md:58-112`, `:268-274`). No column ratios, row caps, text-size floor, line budget, or high-cardinality behavior is specified. | Specify minimum viewport dimensions, region pixel/line budgets, minimum readable text size, maximum visible inbox/roster rows, truncation rules, and bounded composition cardinality. Validate scan time and correct action selection, not merely fit. |
| IA8 | **HIGH** | The acceptance suite cannot prove the no-navigation claim. | AC-1 checks region presence; AC-12 accepts same-route below-fold placement; AC-15 checks only `hidden`/`aria-hidden`, which misses clipping/off-screen content/internal scroll (`control_room_ia.md:300-321`). AC-8/9/10/14 require focus, stream, announcement, and state behavior that screenshots cannot establish. | Split acceptance into screenshot geometry, blind comprehension, browser/accessibility-tree automation, and event/network tests. Geometry must assert viewport intersection, zero page/R3 scroll, no horizontal overflow, minimum type size, and the exact answer tokens per breakpoint. |
| IA9 | **MEDIUM-HIGH** | Governed-action meaning is only partly visible at rest. | R1a says a safe-action affordance exists, while R2 shows only a generic decision flag (`control_room_ia.md:79-85`, `:87-93`, `:150`). Full target/scope/budget/reversibility/receipt semantics remain in R4 (`:108-112`). The existence question is visible, but action eligibility is not consistently scannable. | Make R1a the canonical at-rest answer and expose compact action kind/eligibility (`inspect`, `approve`, `promote`, `cancel`, `retire`, or none). Keep full preview/confirmation in R4; do not create an automatic actuator. |
| IA10 | **MEDIUM** | Selected-state layout is internally inconsistent. | p2 says R4 opens while R1–R3 remain in place (`control_room_ia.md:47-51`), then says R3 compresses into the inspector (`:129-130`). AC-8 verifies only R4 + R2 (`:314`), so R1/R3 disappearance could pass. | Specify one selected-state arrangement per breakpoint and test every region promised to remain visible, including the at-rest answer that replaces a compressed R3. |
| IA11 | **MEDIUM** | Freshness coverage is undefined and the test is weaker than the prose. | p2 promises provenance for every “consequential value” (`control_room_ia.md:151`, `:268-274`), but AC-7 checks only “headline” values (`:313`). Neither set is enumerated. | Publish a per-region inventory of provenance-bearing fields and align AC-7 with it. Include stale, partial, unknown, and unmeasured fixtures. |

## 3. Need-by-need walk

| Need | Region(s) | Verdict | Walk / required disposition |
|---|---|---|---|
| `ON-G1` whole system up / room connected | R0 + R3b | **PARTIAL** | Browser/control state is visible in R0, but worker/projection health is split into the third-priority rail, which may scroll or move below the roster. Keep every independent health dimension co-visible with one shared epoch/age at each desktop breakpoint. |
| `ON-G2` running / queued / failed / live | R2 | **PASS** | Counts plus lifecycle/live/change state are assigned to the persistent roster, including a large-fleet policy (`control_room_ia.md:87-93`, `:209-216`). Retain this. Design adversary D2 still requires agent/session/worktree/current-command identity, but the `ON-G2` placement itself is sound. |
| `ON-G3` failing / stalled / at risk | R1b | **PARTIAL** | Durable items are better than r5's strip, but R1's fixed category order can bury a critical failure behind decisions. Use global severity/actionability ordering or reserved critical capacity. |
| `ON-G4` spend / burn / quota / wallet / leases | R3a | **FAIL** | Five values exist in the specification, but R3 may scroll or move below the fold, mobile does not test them, and p1 narrows the answer to a risk exception. Resolve IA1/IA3. |
| `ON-G5` decision from me | R1a + R2 | **PARTIAL** | R1a provides target/kind/epoch/safe-action affordance, so existence is visible; the R2 flag is a duplicate and action eligibility is not standardized. Make R1a canonical and define compact eligibility. |
| `ON-G6` fresh / trustworthy | R0 + R2/R3 chips | **PARTIAL** | The global degraded summary plus local age/source is directionally correct, but “consequential/headline” coverage is undefined and split facts can have different ages. Enumerate fields and show a coherent summary epoch. |
| `ON-G7` fleet shape by model / condition / provider | R3c | **FAIL** | The four-dimensional grouping is unbounded, can scroll, is a secondary lens in p1, and is explicitly absent on mobile. Restore a bounded visible rollup or narrow the authoritative need. |

## 4. Hierarchy audit

p2's stated hierarchy is:

1. R0 qualifier + R1 work queue;
2. R2 fleet body;
3. R3 constraints (money, health, composition).

This ordering correctly treats truth as a prerequisite and attention as work. It also creates three
placement costs:

- half of `ON-G1` (dependency health) is third even though system health is the prerequisite;
- `ON-G4` and `ON-G7` share the least prominent and most scroll-prone region;
- decisions are pinned above failures without a severity override.

**Disposition:** keep the high-level order, but put a complete compact health qualification in R0,
globally rank R1, and define a non-scrolling R3 minimum schema. “Third” may mean lower visual weight;
it may not mean below fold or hidden in internal overflow.

## 5. Drill-down and alert path audit

### Drill-down

The R2/R1 → R4 paths cover `ON-D1..D7` and preserve one selected stream in prose. The remaining
defects are arrangement/testability: R1/R3 persistence is contradictory (IA10), and screenshot checks
cannot prove focus return, query preservation, or stream multiplicity (IA8). Browser automation must
own those checks.

### Alerts

The transition → durable R1 item → owning detail path is structurally better than r5. The primary
risk is burial under fixed categories (IA6). The transition-only announcement rule also requires an
event/accessibility test; a screenshot cannot prove deduplication or no-op silence.

## 6. Acceptance-test rewrite required

The next IA revision must divide tests by what they can observe:

| Test class | Must prove |
|---|---|
| screenshot geometry | every promised answer token intersects the initial viewport; no page/R3 scroll; no clipping/horizontal overflow; readable type; priority hierarchy |
| blind comprehension | reviewer identifies system health, actionable run, complete money state, pending decision, trust state, fleet shape, and correct next action within a time bound |
| browser/accessibility automation | focus containment/return, selected identity, preserved filters/query/scroll, accessibility-tree names, `hidden` state, keyboard/escape behavior |
| event/network/state | exactly one selected SSE stream, bounded replay/de-dup, transition-only announcement, no-op poll silence, one control epoch across mirrors |

Required captures: 1440×900 default, named minimum desktop, narrow desktop, mobile triage, saturated
inbox, ≥200-run fleet, selected run, stale projection, near-cap money, unknown provider, and the
generic-dashboard comparator required by p4.

## 7. Required disposition order

1. **Resolve IA1 before refining layout.** Name the authoritative desktop/mobile contract and align
   r1, p1, p2, and every acceptance statement.
2. **Resolve IA2/IA3/IA4.** No required desktop glance answer may rely on page or R3 scrolling.
   Define the exact compact schema and bounded composition representation.
3. **Resolve IA5/IA6.** Give each need one canonical answer and guarantee visible capacity for a
   critical failure.
4. **Resolve IA7/IA8/IA11.** Add dimensions, field inventories, fixtures, and the four test classes;
   DOM presence is not a glance pass.
5. **Resolve IA9/IA10.** Standardize at-rest action eligibility and selected-state region persistence.
6. **Rerun this adversary on rendered evidence.** A clean verdict requires screenshots plus browser
   tests, not another prose-only simultaneity assertion.

## 8. Acceptance gate

Do not call the one-resting-screen contract satisfied until:

1. every `ON-G1..G7` answer required at the named desktop breakpoint is visible without page/region
   scroll or navigation;
2. the same documents agree on what mobile and narrow desktop deliberately omit;
3. a saturated inbox cannot bury a critical failure;
4. split summaries share one explicit freshness/epoch contract;
5. blind reviewers can identify every answer and the correct next action; and
6. browser/state tests prove the non-visual interaction and alert invariants.

**Bottom line:** p2 names the right information, but placement names are not yet proof of a glance
contract. The repair must make visibility, bounded density, ordering, freshness, and comprehension
mechanically testable at each claimed breakpoint.
