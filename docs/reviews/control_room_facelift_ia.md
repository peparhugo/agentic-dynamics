---
status: accepted
---

# Control Room facelift - canonical glance IA adversary (a6)

**Reviewer:** `openai/gpt-5.6-luna`

**Date:** 2026-09-11

**Scope:** the retained resting screenshots in `apps/control_room/verification/`, the canonical
glance contract in `docs/research/control_room_ia.md`, and the executable checks in
`scripts/verify_control_room_rendering.py`. This pass judges information architecture and gate
coverage; the separate a5 review judges visual distinctiveness.

## Verdict

**FAIL - THE CANONICAL GLANCE CONTRACT IS NOT PROVEN.**

All seven named answer regions are physically present above the fold in the inspected desktop and
mobile screenshots, and the page does not visibly scroll. That is necessary but insufficient. The
canonical contract also requires each answer to be complete and legible, reserved alerts to survive
real saturation, decision state to be unmistakable, and the full G/B/A/E acceptance suite to fail on
semantic or state inconsistency (`docs/research/control_room_ia.md:436-545`).

The current gate reports **PASS** while several required checks are absent or partial:

- F-1 does not prove alert ranking because `attention.items` is never rendered.
- F-7 says no decision is pending in R1 while the first R2 row still says `approve` and `controller`.
- `ON-G7` renders compact `t/o/u` bucket notation rather than explicit `top/other/unknown` meaning.
- Fixture values are generally not compared with rendered values.
- The canonical blind-comprehension B checks, accessibility A checks, and event/state E checks are not
  implemented by the gate.

A gate that can stay green through those misses cannot prove the canonical glance contract. The
mechanical PASS remains useful evidence for layout stability, contrast, first paint, and console
cleanliness; it is not the IA verdict.

## Review Method

1. Read the one authoritative `ON-G1..G7` region/content map and the exact G/B/A/E acceptance checks.
2. Inspected F-0 and F-1 at 1440x900 and 390x844, then used F-2 through F-7 to check aggregate,
   near-cap, unknown, stale, disconnected, and empty-state forcing conditions.
3. Walked `GEOMETRY_JS` and `_check_geometry()` field by field, including how selector cardinality,
   viewport bounds, scroll, field schemas, fixture values, row capacities, and marginal buckets are
   actually evaluated.
4. Treated any visual miss or executable-gate miss as a failure. DOM presence is not substituted for
   legibility, correct semantics, alert ranking, or decision consistency.

## Canonical Answer Walk

| Answer | Canonical carrier and complete answer | Screenshot judgment | Gate judgment | Verdict |
|---|---|---|---|---|
| `ON-G1` system | R0: browser/SSE, control plane, workers, and projections, each with state and worst age (`control_room_ia.md:81-93`). | **Visible.** F-0 names all four dimensions at desktop and mobile; F-6 visibly isolates `browser down - 7s` while the others stay up. The compact mobile wrap remains above the fold. | **Incomplete.** Field names and non-empty values are checked, but legal state enums, numeric ages, and F-5/F-6 fixture values are not. Answer uniqueness can be hidden by object-key overwrite in `GEOMETRY_JS` (`verify_control_room_rendering.py:409-420`). | **FAIL (gate miss).** |
| `ON-G2` fleet state | R2: exact running/queued/failed/live totals plus a bounded, non-scrolling agent-session sample (`control_room_ia.md:120-135`). | **Visible.** F-2 shows `80 / 60 / 40 / 20` and keeps the bounded sample. F-0 shows 8 desktop rows and 3 mobile rows without visible scroll. However, the required per-row spec/cell field is absent from the screenshot. | **Incomplete.** G-13 compares field sets but not row values or duplicates; G-14 checks row/line counts but never compares F-2's aggregate totals. `spec/cell` is absent from the gate's row schema. | **FAIL (incomplete answer and gate miss).** |
| `ON-G3` risk | R1 reserved highest-severity failure/stall/risk or explicit all-clear; saturation must not bury the critical item (`control_room_ia.md:97-118`). | **Nominally visible.** F-0/F-1 show the same `RISK target run-failed state active / action inspect`; F-7 shows `target none state all-clear / action none`. The F-1 image does not visually demonstrate that more than 20 competitors were ranked. | **Failing.** G-14 proves only that a fixed risk row exists. The renderer ignores `attention.items`, and E-5 is absent, so F-1 does not test selection of the highest-severity item or displacement under saturation. | **FAIL (alert burial unproven).** |
| `ON-G4` money | R3a: exactly spend, burn, quota, wallet/headroom, and reserved leases, plus a near-cap exception where applicable (`control_room_ia.md:137-147`). | **Visible.** F-3 shows all five values and `near cap`; F-4 keeps all five as literal `unknown`, never zero. The values fit at desktop and mobile. Source and age do not travel with the consequential values as the region contract requires. | **Incomplete.** Exact field names and marker cardinality are checked, but F-3's 96%, F-4's literal unknowns, and source/age semantics are not compared or validated. | **FAIL (provenance and semantic gate miss).** |
| `ON-G5` decision | R1 reserved pending decision or explicit none-pending state, with target, kind, epoch, authority, and legal eligibility (`control_room_ia.md:103-107`). | **Pending case visible.** F-0/F-1 make `DECISION`, `pending`, `approve`, epoch 42, controller, and eligible approve visible. **Empty case contradictory.** F-7's R1 says state/target/kind/authority/eligibility are `none`, while the first R2 row still says `approve`, `controller`, and `recorded`. It also says `state none`, not the required plain-language `none pending`. | **Failing.** The gate checks non-empty fields, not pending/none semantics, legal eligibility, same-epoch linkage, or R1/R2 consistency. The F-7 DOM retains the accessible name `Pending controller decision` (`apps/control_room/static/app.js:354-360`), and A-4 is absent. | **FAIL (decision state is not unmistakable).** |
| `ON-G6` trust | R0: epoch, worst age, projection state, and degraded/stale/partial/unknown counts (`control_room_ia.md:81-93`). | **Visible.** F-0 reads current/zero; F-4 exposes unknown count 2; F-5 visibly pairs age 901s, stale projection, degraded 1, and stale 1. | **Incomplete.** The gate checks field-set presence and non-empty text, but not projection-state enums, integer counts, fixture deltas, or consistency with `ON-G1`. | **FAIL (gate miss).** |
| `ON-G7` fleet shape | R3c: model, condition, provider, and lifecycle; each has explicit top, other, and unknown buckets (`control_room_ia.md:152-155`). | **Present but not sufficiently legible.** The four marginals are above the fold at both viewports, but strings such as `t sol 5 o 2 u 0` require prior knowledge that `t/o/u` mean top/other/unknown. F-4 changes provider unknown to 2, but the meaning remains encoded rather than explicit. | **Incomplete.** G-11 checks bucket names in data attributes and only validates the top bucket's category/value. Empty `other` or `unknown` values can pass, and F-4's expected unknown count is never compared. | **FAIL (legibility and gate miss).** |

**Per-anchor result:** zero of seven answers receives an unconditional PASS because every anchor has
at least one content, semantic, provenance, or executable-gate miss. Physical presence alone does not
satisfy the contract's definition of visible at rest.

## Geometry Gate Walk (G-1 Through G-15)

| Check | Implemented behavior | Adversary verdict |
|---|---|---|
| G-1 | The probe stores regions and answers in JavaScript objects keyed by data value, then compares key sets. Region boxes are checked for non-zero size. | **FAIL/PARTIAL.** Duplicate selectors overwrite earlier entries before cardinality is tested. Answer boxes are not independently checked for non-zero size, viewport bounds, or ancestor visibility. |
| G-2 | Compares document scroll height/width with the viewport. | **PASS for page scroll.** The screenshots and measurement support no page scroll. The canonical row says page plus all answers, but answer overflow is delegated incompletely to G-3. |
| G-3 | Checks internal scroll width/height for the six regions. | **FAIL/PARTIAL.** The seven answer anchors are not checked even though the canonical check explicitly includes them. |
| G-4 | Runs a computed-color contrast walker for every theme and viewport. | **PASS mechanically.** This proves contrast ratios, not wording, grouping, or comprehension. |
| G-5 | Checks computed font size for discovered labels and values. | **FAIL/PARTIAL.** Mobile R2 labels are visually hidden in 1x1px clipping while retaining an acceptable computed font size, so the test can pass labels a stranger cannot see. |
| G-6 | Checks non-empty strings only for values added to `valueTexts`; checks the presence of `data-no-ellipsis`. | **FAIL/PARTIAL.** A missing direct value can be absent from the map rather than fail, and an attribute is used as a proxy for actual clipping. Fixture truth is not compared with visible text. |
| G-7 | Compares desktop region rectangles with fixed expected boxes. | **PASS/PARTIAL.** The boxes match. Explicit overlap and independent layout-equation assertions are not performed. |
| G-8 | Uses the mobile fixed-box table through the same G-7-labelled loop. | **PASS/PARTIAL.** Mobile region boxes fit, but the report does not emit G-8-specific evidence or independently verify the full vertical equation. |
| G-9 | Mobile left/width values are implied by the fixed boxes. | **PASS/PARTIAL.** The one-column shape fits, but no G-9-labelled assertion independently checks the contract. |
| G-10 | Exact money field set is checked under generic `schema`; G-10 itself checks only risk-marker count. | **FAIL/PARTIAL.** Values, duplicates across overwritten maps, unknown semantics, and provenance are not fully enforced. |
| G-11 | Checks marginal names, bucket data attributes, and completeness of only the top bucket. | **FAIL.** Other/unknown values and fixture-specific counts are unchecked; visible `t/o/u` wording does not prove comprehension. |
| G-12 | Narrow boxes use the common fixed-box loop. | **PASS/PARTIAL.** Geometry fits, but answer-level uniqueness/viewport/scroll gaps from G-1/G-3 remain. |
| G-13 | Compares each row's field-name set with `ROW_FIELDS`. | **FAIL/PARTIAL.** Set equality masks duplicate fields; values are collected but never validated; required spec/cell is not in the schema. |
| G-14 | Checks row/item/line counts and line clamps. | **FAIL/PARTIAL.** Exact R2 aggregate values, reserved-row classes, global attention ranking, and forcing semantics are not tested. |
| G-15 | Checks each answer's canonical parent region. | **FAIL/PARTIAL.** Parent mapping is correct for the surviving object entry, but duplicate answer writers can be overwritten before this check. |

The report's statement `geometry (IA section 10.3 G-1..G-15)` therefore overstates coverage. Several
checks are only implied by a shared fixed-box comparison, and the load-bearing per-anchor assertions
are partial or absent.

## Blind, Accessibility, and State Classes

The canonical contract explicitly separates checks that geometry cannot prove:

| Class | Required coverage | Current status | Verdict |
|---|---|---|---|
| B-1 through B-7 | A stranger states each `ON-G1..G7` answer within ten seconds and points to its pixels. | No executable or recorded human score exists. Screenshots are retained but not scored in `gate_report.md`/JSON. | **FAIL - missing.** |
| B-8 through B-11 | Correct next action, agent-session identity, claim/proof distinction, and eligibility/receipt recognition. | No comparator or scored comprehension record exists. The a5 design adversary separately finds mobile identity and claim/proof recognition failures. | **FAIL - missing.** |
| A-1 through A-6 | Focus containment/return, selection persistence, preserved controls, accessible names/roles, true hidden state, keyboard open/close. | The style class samples focus appearance, but it does not implement the canonical end-to-end A suite. F-7's incorrect accessible decision name demonstrates the consequence. | **FAIL - missing.** |
| E-1 through E-5 | One selected stream, replay/de-dup, transition announcements, epoch consistency, saturated-inbox behavior. | The live class checks structure against live data. It does not execute the canonical event/state cases, including E-5. | **FAIL - missing.** |

## Alert Burial Adversary

**FAIL.** F-1 visually retains one decision and one risk row, but this is a reserved-slot demo, not a
saturation test. The fixture adds more than 20 low-priority objects to `attention.items`; the renderer
does not consume that collection (`apps/control_room/static/app.js:344-426`). It always constructs
decision, risk, next, then filler rows. Consequently:

- no competing items are ranked by severity x actionability;
- no critical transition displaces a lower-priority item;
- G-14 can pass by counting fixed rows; and
- E-5, the required proof that a new critical failure stays visible, is absent.

The screenshot shows an alert, but the system has not proved that the correct alert cannot be buried.

## Decision-State Adversary

**FAIL.** The pending state is visually strong in F-0/F-1: DECISION, pending, approve, controller, and
eligibility are grouped. The all-clear fixture invalidates the global claim:

- F-7 R1 says there is no decision.
- The first F-7 run row still presents `approve`, a controller-authority mark, and `recorded`.
- The decision item's accessibility name remains `Pending controller decision` for the none state.
- The gate validates non-empty text rather than state semantics or R1/R2 linkage.

An operator receives two incompatible answers on the same resting screen. Decision state is therefore
not unmistakable, and the gate would not catch the contradiction.

## What Is Proven

- R0, R1, R2, R3a, R3b, and R3c all fit above the fold at 1440x900, 1024x768, and 390x844.
- The page itself does not scroll in the exercised fixtures.
- The seven answer anchors are currently nested in their canonical regions.
- R2 and R1 honor the nominal visible row capacities.
- Dark, light, and forced-colors contrast checks, first paint, and console cleanliness pass.
- F-2, F-3, F-4, F-5, F-6, and F-7 screenshots expose their headline forcing values visually.

These are valuable layout regressions. They must be retained while the semantic gate is repaired.

## Required Dispositions

1. **Make per-anchor checks literal.** Use locator cardinality rather than object-key maps; apply all
   five geometry primitives to every region and answer; check actual clipping; validate exact field
   cardinality, legal enums, numeric domains, and required values.
2. **Compare fixture truth to rendered truth.** Assert F-2 totals, F-3 near-cap values/marker, F-4
   unknown values and provider bucket, F-5 stale/degraded coupling, F-6 independent browser failure,
   and F-7 all-clear/none semantics.
3. **Repair R1 saturation.** Render/rank the actual attention collection, reserve decision and critical
   risk capacity within that ranking, then execute E-5 with a post-ready critical transition.
4. **Repair decision consistency.** Derive the R2 decision mirror from the same authoritative decision
   object, remove approval/controller affordances when R1 is none, render explicit `none pending`, and
   make the accessible name state-sensitive.
5. **Complete the answer schemas.** Add the required R2 spec/cell field and consequential-value
   provenance; render `top`, `other`, and `unknown` legibly in R3c rather than relying on `t/o/u`.
6. **Implement B/A/E as first-class report classes.** Record human blind scores and comparator result;
   automate the canonical keyboard/accessibility and event/state cases. Do not label the report as
   covering the canonical contract until every class runs.
7. **Re-run every fixture at every required viewport.** PASS only when each `ON-G1..G7` row above has
   no visual or executable-gate miss, alerts survive true saturation, and pending/none decisions are
   internally and accessibly consistent.

**Disposition:** retain the mechanical gate but treat its current PASS as layout-only. The Control Room
facelift IA remains **REWORK REQUIRED**.
