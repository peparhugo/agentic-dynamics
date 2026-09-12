---
status: accepted
---

# Control Room repair2 -- canonical glance IA verdict

**Reviewer:** `openai/gpt-5.6-sol`
**Date:** 2026-09-11
**Scope:** `docs/research/control_room_ia.md`, its non-authoritative pointer in
`docs/research/control_room_direction.md`, and the authoritative `ON-G1..G7` wording in
`docs/research/control_room_questions.md` §4.1.

## Verdict: PASS at contract level

One canonical glance contract exists: `control_room_ia.md` §4. The direction deliberately points to
that section without repeating its breakpoint or need tables. Every need has exactly one canonical
answer anchor inside one region represented in the pixel-budget table. All resting regions and answer
anchors are non-scrolling and fully above the fold at 1440×900 and 390×844; the additionally claimed
1024×768 layout also fits.

The render gate has not been implemented, which is outside this review's documentation scope. Its
checks are implementable without another IA decision: selectors, cardinalities, parent ownership,
fixed boxes, field schemas, semantic enums, row/line budgets, deterministic fixtures, readiness,
themes, and HTML contrast calculation are explicit.

## Explicit Pass Conditions

| Pass condition | Result | Evidence |
|---|---|---|
| A single canonical glance contract exists. | PASS | IA §4 is the only authoritative list. Direction §16 is a pointer and contains no duplicate mapping table. |
| Every need maps to one region in the pixel-budget table. | PASS | `G1→R0`, `G2→R2`, `G3→R1`, `G4→R3a`, `G5→R1`, `G6→R0`, `G7→R3c`; every owner is a §3.2 row. |
| Both required viewport budgets fit. | PASS | 1440×900 uses 884px vertically; 390×844 uses 760px. Exact horizontal equations equal 1440 and 390. |
| Claimed narrow desktop also fits. | PASS | 1024×768 uses 760px vertically and exactly 1024px horizontally. |
| No need depends on page scroll, region scroll, or below-fold placement. | PASS | Every owner and answer anchor is bounded by G-1/G-3; R1 reserves risk/decision rows; R2 uses exact counts and a bounded sample rather than an internal scroller. |
| Acceptance checks are implementable by the render gate. | PASS | IA §10 specifies valid selectors, exact schemas and enums, fixed coordinates, all-match loops, fixture wire data/SSE, readiness, theme emulation, and effective HTML contrast. |

## Need-by-Need Walk

| Need | One canonical owner | Complete visible answer | Desktop position | Mobile position | Split / scroll / fold verdict |
|---|---|---|---|---|---|
| `ON-G1` whole system up / room connected | `R0` | browser, control, workers, projections; each has state and worst age | y=0–72 | y=0–72 | PASS: one owner, no join with R3b, no scroll, above fold |
| `ON-G2` running / queued / failed / live | `R2` | exact four counts plus bounded agent-session sample | y=84–884 | y=232–516 | PASS: full-fleet overflow is a lens; R2 never scrolls |
| `ON-G3` failing / stalled / at risk | `R1` | reserved highest-risk row or explicit all-clear | y=84–884 | y=80–224 | PASS: cannot be buried by decisions or overflow |
| `ON-G4` spend / burn / quota / wallet / leases | `R3a` | exact five unique fields plus conditional risk marker | y=84–304 | y=524–616 | PASS: complete 3+2 grid; no Money-board hop |
| `ON-G5` decision from me | `R1` | reserved decision row with state, target, kind, epoch, authority, eligibility; or explicit none | y=84–884 | y=80–224 | PASS: R2 tokens are mirrors without answer attributes |
| `ON-G6` fresh / trustworthy | `R0` | epoch, worst age, projection state, degraded/stale/partial/unknown counts | y=0–72 | y=0–72 | PASS: local provenance chips are explanations, not answer fragments |
| `ON-G7` fleet shape | `R3c` | model, condition, provider, lifecycle; each exactly top/other/unknown | y=500–640 | y=700–760 | PASS: bounded text marginals, no chart/lens/scroll dependency |

## Pixel-Budget Proof

### 1440×900

```text
R3 stack = 220 + 8 + 180 + 8 + 140 = 556
body     = max(R1 800, R2 800, R3 556) = 800
height   = R0 72 + gap 12 + body 800 = 884 <= 900
width    = outer 32 + gaps 24 + R1 300 + R2 744 + R3 340 = 1440
headroom = 16px vertical
```

### 1024×768

```text
R3 stack = 160 + 8 + 132 + 8 + 116 = 424
body     = max(R1 692, R2 692, R3 424) = 692
height   = R0 60 + gap 8 + body 692 = 760 <= 768
width    = outer 24 + gaps 16 + R1 224 + R2 472 + R3 288 = 1024
headroom = 8px vertical
```

### 390×844

```text
regions  = 72 + 144 + 284 + 92 + 68 + 60 = 720
gaps     = 5 * 8 = 40
height   = 720 + 40 = 760 <= 844
width    = outer 24 + one stacked column 366 = 390
headroom = 84px vertical
```

Content also fits the forcing mobile width: each region has 350px after padding; R0 uses
70+4+276px, R3a uses `3*110 + 2*10 = 350px`, and R3c uses `68+4+278 = 350px`. Desktop and narrow
have their own smaller R3 tracks rather than incorrectly reusing mobile widths.

## Render-Gate Implementability

| Gate concern | Implementable contract |
|---|---|
| Unique ownership | Exact global region/answer sets; one answer writer; nearest and only region ancestor must match the canonical map. |
| Visibility | Every region, answer, field, and value gets a non-zero in-viewport box; hidden/aria-hidden/display/visibility ancestors fail. |
| No scrolling or clipping | Page, all six regions, all seven answers, and required values compare scroll/client dimensions; required values cannot ellipsis. |
| Content schemas | Exact field-set equality catches omissions and duplicates; labels and values are checked separately. |
| Semantic validity | System, decision, trust, lifecycle, liveness, provenance, attention, eligibility, receipt, counts, and composition use declared enums/ranges. |
| Capacity | R1 exact rows are 5/4/3; R2 exact rows are 8/7/3; per-class line-clamp counts are asserted at each viewport. |
| Geometry | Fixed x/y/width/height dictionaries cover all six regions at all three viewports with ±1px tolerance. |
| Fixtures | Only `/api/glance` and `/api/events` are allowed; F-0 seed, F-1..F-7 deltas, metadata inheritance, and exact SSE frames are declared. |
| Readiness | Same-epoch GET/SSE replay completion, fonts, two animation frames, frozen clock, locale/timezone, and reduced motion precede capture. |
| Themes / contrast | Dark/light use `control-room-theme`; forced colors uses Playwright media emulation; an HTML TreeWalker composites effective backgrounds and applies WCAG ratios. |

## Findings and Dispositions

| ID | Severity | Initial failure | Final disposition |
|---|---|---|---|
| IA-R1 | BLOCKER | `ON-G1` and `ON-G6` were split between R0, R3b, and local chips. | Complete independent answers now live in R0; detail/chips are non-authoritative mirrors. |
| IA-R2 | BLOCKER | `ON-G2` depended on R2 internal scrolling. | Exact counts answer the need at any fleet size; bounded rows remain visible; full fleet is a lens. |
| IA-R3 | HIGH | Ranked R1 could hide all risks or all decisions. | R1 reserves one risk/all-clear and one decision/none row before globally ranked remainder capacity. |
| IA-R4 | HIGH | Outer boxes fit, but horizontal and line content did not have arithmetic. | Fixed border-box, row, line, padding, and per-viewport track equations now cover content. |
| IA-R5 | HIGH | Selector shorthand, one-match queries, and weak cardinality allowed false passes. | Explicit valid selectors, exact sets, `count()`/`nth()`, nearest-parent checks, and row-local loops are specified. |
| IA-R6 | HIGH | Fixture/readiness/theme/contrast helpers were placeholders. | Exact route/payload/SSE contracts, readiness barrier, real theme key, forced-colors emulation, and HTML contrast algorithm are specified. |

## Final Adversarial Rule

Any future edit fails this verdict if it introduces a second canonical table, a second answer writer,
an answer whose canonical region is absent from the budget table, a required internal/page scrollbar,
a region below the fold, a field schema that can pass with duplicate/missing values, or viewport/content
arithmetic exceeding its fixed budget. The implementation remains pending; the IA decision surface is
closed.
