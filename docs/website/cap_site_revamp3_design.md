---
status: accepted
---
# CAP Site Revamp 4: Augmentation Delta Preview

**Phase:** `p2_design_with_human_checkpoint` (campaign `cap_site_revamp4`)
**Executor:** deepseek/deepseek-v4-flash
**Supersedes design basis:** the approved revamp3 delta (`docs/website/cap_site_revamp3_design.md`,
signed `peparhugo` 2026-08-27, revision `ee12c9c5b`). This document re-verifies that delta
against the campaign's verified census and re-issues it for operator signature. The revamp4
campaign keeps revamp3's gates identical and swaps the executor; the incumbent site is
byte-identical (all 11 served-file sha256 fingerprints match the revamp3 census).
**Decision state:** design complete; implementation is blocked pending the signed operator
approval at `approvals/cap_site_revamp3_design_approval.md`.
**Design rule:** preserve the instrument, then establish the field around it. This document
authorizes no implementation, deployment, removal, or data regeneration.

## Decision Basis

The preservation baseline is the verified, current source census in
`experiments/results/cap_site_revamp3/incumbent_census.json` [M] — re-run on the current main
checkout by this campaign's p1 and committed (`40691ff0b`). It reconciles the earlier feature
matrix without a structural source delta and records these minimum site-wide contracts:

| Contract | Verified baseline | Preservation meaning |
|---|---:|---|
| Served routes | 8 HTML pages | Every current route remains served. |
| Framework sliders | 14 | Each remains visible and invokes `updateROI()` through `oninput`. |
| Canvas/chart construction sites | 6 / 6 | All chart hosts and `new Chart(...)` sites remain; the data-gated Grit host is not a removable feature. |
| Semantic tables | 38 | Framework, Evidence, Methodology, and Applications tables remain available. |
| Handler attachment sites | 50 | Calculator, chart, disclosure, theme, ToC, and evidence interactions remain structurally wired. |
| Theme toggle | 1 shared control | The persisted light/dark control remains on every page. |
| Shared data door | 33 supported `data-stat` keys; 84 `data-anal` cells | `data.js` remains the only generated data source; no duplicate hand-typed live values. |

The field-layer direction is a [P] editorial decision grounded in the historical research
artifact `feature/site-revamp:docs/designs/current/cap_site_revamp_research.md`, the measured
revamp regression analysis [M/C], and the local-example inventory at
`feature/site-revamp:apps/website/references/`. Those historical artifacts are cited as
implementation references only; they are not copied into the current site during this phase.

**Prior-campaign lesson (incorporated):** revamp3's p5 independent review
(`docs/reviews/cap_site_revamp3_review.md` on `feature/site-revamp3`) verified the instrument
survived feature-by-feature but FAILED the field layer: `base.css` untouched (no editorial
typography/color system), `accelerator.html`/`databricks.html`/`glossary.html` byte-identical
(no open-questions reframe, no `[X]` scope labels, no glossary receipts), and several approved
figures absent (one-engine/two-modes, bounded-autonomy envelope, ten rule cards, instrument
cycle on Framework). The ADD contract below is therefore enumerated as concrete, checkable
surfaces — a "present / absent" per row — so the same gate structure cannot pass a partial
field layer again. The preservation contract is unchanged.

## Keep: The Preservation Contract

Every incumbent feature stays. Styling, adjacent framing, and accessible explanatory material
may be added, but a widget is never replaced by a static approximation. The anti-SaaS rule
constrains claims and calls to action, not transparent data-wired tools.

| Page / surface | Keep exactly | Augmentation boundary |
|---|---|---|
| All eight routes: Home, Framework, Evidence, Story, Methodology, Applications, Related Work, Glossary | Existing URLs, navigation reachability, visible authored content depth, `app.js` hydration, and generated data dependency | Add field navigation and editorial framing without orphaning, collapsing, or redirecting an incumbent page. |
| All pages except Glossary | Floating table of contents, keyboard handling, fragment navigation, and smooth-scroll behavior | Improve its visual treatment only after preserving source handler behavior. |
| All pages | Persisted theme toggle (`body.light`, `ai-finops-theme`) | Typography and color tokens must work in both themes; no theme control may be replaced with a default palette. |
| Home (`index.html`) | Current corpus receipt, field-map image, eight `data-stat` slots, and current navigation role | Add a concise field statement and an instrument-cycle figure beside the existing receipt, not in place of it. |
| Framework (`framework.html`) | 14 calculator sliders, two modes, live results, cost/throughput chart, horizon and scenario controls, how-computed disclosure, workforce details, three semantic tables, existing inline diagrams | Reframe the calculator as a transparent `[C]` explorable with assumptions and provenance adjacent to it. Add field diagrams and rule-status material around the working controls; do not turn the page into a pricing or product surface. |
| Evidence (`evidence.html`) | Five chart hosts/construction sites, Grit model and class filters, data-gated Grit empty state, archive redraw and fragment reveal, six disclosures, 30 tables, 18 `data-stat` slots, and 84 `data-anal` cells | Add evidence receipts, scoped verdict figures, and named null states before or alongside current evidence. A missing canonical series remains visibly unmeasured, never a zero or historical fallback. |
| Story (`story.html`) | Four-part origin, including the attributed $20/Rome account, and nine data slots | Add a dated bridge from the origin to the research question while preserving the origin's [H] status. |
| Methodology (`methodology.html`) | Fourteen method sections, native TL;DR disclosure, two tables, and five data slots | Add a clearer instrument/ledger explanation and an optional bounded scenario figure without treating it as a forecast. |
| Applications (`accelerator.html`) | Route, 11 sections, three tables, six `data-stat` and two `data-stat-fmt` slots | Reframe in place as bounded applications/open questions. Existing material stays reachable and any stale claim is labeled, sourced, or archived in situ rather than silently dropped. |
| Related Work (`databricks.html`) | Route, comparison material, six `data-stat` and one `data-stat-fmt` slots | Add provenance and scope labels; retain external context as `[X]`, even if Evidence gains a related-work cross-link. |
| Glossary (`glossary.html`) | Fifteen definition cards and eight data slots | Add source anchors and evidence-class explanations without reducing the definitions to a smaller glossary. |

## Remove: None Proposed

| Proposed removal | Page | Reason | Operator waiver |
|---|---|---|---|
| None | N/A | The incumbent is the preservation baseline. Reframing, labeling, and archival context solve the editorial problems without deleting an interaction, route, table, or data contract. | Not applicable. Any future removal requires a specific signed waiver in the approval artifact before implementation. |

Two planned editorial corrections are **not removals**: a stale claim is re-bound to a
`data.js` field or displayed as dated historical context; an unavailable measurement is rendered
as a named null. Neither change permits a feature-count reduction.

## Add: Field Establishment as Augmentation

The additions below are implementation work for a later, approved phase. Claims retain their
evidence class at the point of reading. A measured or computed value must enter through
`data.js`; if the required field is absent, the addition is a named null until the generator can
produce it. Each row carries a checkable surface so the comparison gate and independent review
can verify presence mechanically.

| Addition | Page / placement | Checkable surface (present/absent) | Evidence and editorial constraint | Example-library reference |
|---|---|---|---|---|
| Field statement and named question | Home lead; new `question.html` linked from, not substituted for, existing navigation | Route `question.html` served and linked; Home leads with the field statement | `[P]` framing: the question concerns accepted outcomes as tasks, environments, workflows, and time change. The new page adds a route; it does not displace Story or Methodology. | `type-editorial-measure.html`, `type-responsive-grid.html`, `svg-pattern-surface.html` |
| Origin-to-instrument bridge | Story after the existing origin | A dated bridge block exists between the origin and the research question | Keep the $20/Rome account visibly `[H]`; distinguish it from current corpus evidence. | `scroll-sticky-side.html`, `type-editorial-measure.html` |
| Repeated provenance receipt | Home, Evidence, Methodology, Framework, and Glossary (all five named pages) | Receipt block present on each named page with class, source/artifact, corpus/denominator, date, limitation | Use the existing `[M]`, `[C]`, `[H]`, `[X]`, `[P]` vocabulary. | `card-details.html`, `card-tooltip-badge.html` |
| Honest-null treatment | Evidence, Methodology, and Applications/Open Questions | Named-null states (`not measured`, `untriggered`, `underpowered`, `no canonical output`) present on each named page | Render absent measurement as a named state, never `0`, an unexplained dash, or a historical fallback. | `svg-pattern-surface.html`, `card-tooltip-badge.html` |
| `cap_2b` decision card | Evidence verdict section | Card present with both arms, n, CPVO ratio, CI, decision rule, and authorization boundary | [C] decision over [M] outcomes: NON-INFERIOR (CPVO ratio 0.785746, 95% CI [0.6842, 0.9105], n=9/9, margin ≤ 1.10) in the randomized DeepSeek v4 Pro pilot (static $0.080062 6/9, adaptive $0.094364 9/9). Shows that it authorizes design review only, not control activation. | `card-details.html`, `card-tooltip-badge.html` |
| Escalation figure | Evidence, adjacent to existing charts and tables | Figure present showing baseline, both measured `E_x`, n, and scope | Show baseline `$0.008949`, Sol `E_x = 11.4671` (`0.102619 / 0.008949`), and Sonnet `E_x = 12.5134` (`0.111982 / 0.008949`) with `[M]` costs, `[C]` ratios, `n=1` per escalation model, and no causal generalization. | `svg-marker-flow.html`, `svg-pattern-surface.html` |
| Calibration arc | Evidence verdict section | Arc/panels present covering 0/3 → 2/3 → 2b with each n and interval | Distinguish 0/3 initial, 2/3 rerun with Wilson [0.2077, 0.9385] (n=3), and the later 2b decision. The final label must state its authorization boundary. | `scroll-sticky-overlay.html`, `d3-line-arc.html` |
| Instrument cycle | Home and Framework (both named pages) | `instrument-cycle` figure present on Home AND Framework | `[P]` method explanation: Instrument -> Derive -> Write policy -> Grid -> Campaign. It visibly encodes that unmeasured requirements block policy. | `svg-marker-flow.html`, `svg-animated-status.html` |
| N x M problem figure | New Question page and Story cross-link | Figure present on Question; Story links to Question | `[P]` explanatory map only; no numeric claim is implied by the diagram. | `svg-pattern-surface.html`, `type-responsive-grid.html` |
| Eight planes | Framework around the existing calculator, chart, levers, and diagrams | Field-map section present with the eight planes and INSTRUMENTED/PROPOSED/DECIDED states | `[P]` architecture figures cite `ARCHITECTURE.md`; they add explanation rather than hiding the operating instrument. | `svg-marker-flow.html`, `svg-filter-focus.html`, `svg-pattern-surface.html` |
| One engine / two operating modes | Framework | Figure present (distinct from eight-planes) | `[P]` from written compiler/runtime: fixed assignment -> one cell; factor cross-product -> G cells; converge at cell -> compile -> jobs -> attempts -> ledger. | `svg-marker-flow.html` |
| Bounded-autonomy envelope | Framework | Figure present distinguishing proposed capability from a run | `[P]` policy/architecture; visually distinguish proposed typed checkpoint capability from not-run state. | `svg-pattern-surface.html`, `svg-filter-focus.html` |
| Cost-curve explorable | Methodology or Framework, separated from the live calculator | Bounded scenario control present, labeled and separate from observed data | If a current canonical series exists, label it `[M]/[C]`; any N-squared scenario is `[C]`, exposes its formula/input, and never merges with observed data or forecasts a business result. | `d3-line-arc.html`, `d3-interactive-curve.html` |
| Ten rule cards | Framework, alongside existing provider/playbook material | Ten expandable cards grouped by instrumented/proposed/decided state | Each card exposes inputs, evidence class, source, limitation, and next test. Never call a rule "measured" if only its premise/input is measured. | `card-details.html`, `card-tooltip-badge.html` |
| Typography and color system | `base.css` (shared), applied to every preserved page and both themes | `base.css` carries the system; both themes honor it; no page-local-only styling of the system | Editorial serif body, sans UI/display, mono receipts; warm paper/ink palette with teal for measured, amber for computed, and a non-color textual class. No ambient motion; respect reduced motion. | `type-editorial-measure.html`, `type-responsive-grid.html`, `svg-pattern-surface.html`, `svg-animated-status.html` |
| Applications bounded reframe | `accelerator.html` (in place) | Page gains a bounded/open-questions treatment with honest-null states; all incumbent material stays reachable | Anti-SaaS guard: claims constrained, enterprise projections labeled as bounded hypotheses or dated context, never deleted. | `card-details.html`, `type-editorial-measure.html` |
| Related Work scope labels | `databricks.html` (in place) | External claims marked `[X]` with source/date; instrument comparisons scoped | Retain external context as `[X]`, never as causal support for a corpus finding. | `card-tooltip-badge.html`, `type-editorial-measure.html` |
| Glossary source anchors | `glossary.html` (in place) | Each `.gcard` gains a source anchor and evidence-class line | Definitions remain; add the source/evidence line without reducing the set. | `card-tooltip-badge.html` |

## Diagram Inventory: Later Implementation Checklist

This table turns the reused diagram inventory into an auditable implementation plan. Each row
must be present in a served page, have a caption/alt text/provenance treatment, retain a prose
equivalent, and cite its local reference in a source comment. It augments the incumbent SVGs,
Chart.js canvases, and calculator; it does not replace them.

| ID | Target page | Data / evidence boundary | Reference | Required later verification |
|---|---|---|---|---|
| `instrument-cycle` | Home AND Framework | `[P]` method structure | `svg-marker-flow.html`, `svg-animated-status.html` | Served SVG exists on both pages; static meaning survives reduced motion. |
| `nxm-problem` | Question; Story cross-link | `[P]` explanatory structure | `svg-pattern-surface.html`, `type-responsive-grid.html` | New route does not reduce Story content or navigation. |
| `eight-planes` | Framework | `[P]`, `ARCHITECTURE.md` dependency direction | `svg-marker-flow.html`, `svg-filter-focus.html` | Existing calculator/chart/sliders and their handlers remain. |
| `one-engine-two-modes` | Framework | `[P]`, compiler/runtime explanation | `svg-marker-flow.html` | Existing two calculator modes remain independently operable. |
| `bounded-autonomy-envelope` | Framework | `[P]`; distinguish proposed capability from a run | `svg-pattern-surface.html`, `svg-filter-focus.html` | No policy claim is presented as measured. |
| `cost-curves` | Methodology or Framework | Observed series `[M]/[C]`; scenario `[C]` and visually separate | `d3-line-arc.html`, `d3-interactive-curve.html` | Scenario controls are additive; baseline chart host remains. |
| `escalation-chain` | Evidence | `[M]` costs / `[C]` `E_x`, n and scope shown | `svg-marker-flow.html`, `svg-pattern-surface.html` | Values arrive through `data.js` or render a named unavailable state. |
| `calibration-arc` | Evidence | `[C]` over `[M]` outcomes; 2b decision boundary visible | `scroll-sticky-overlay.html`, `d3-line-arc.html` | Mobile/static prose equivalent; existing Evidence canvases and filters survive. |
| `ten-rules-cards` | Framework | Mixed rule status, never over-claiming measurement | `card-details.html`, `card-tooltip-badge.html` | Keyboard-readable details; existing tables and disclosures survive. |

## Mandatory Gates After Approval

1. Before the first implementation increment, the signed approval below must be committed
   with `SIGNED-BY-OPERATOR` containing a non-placeholder identity and date. An unsigned
   template is a stop signal, not approval.
2. Each small page-family increment re-runs the incumbent census. A count below the baseline
   is a failed increment until restored or covered by a specific signed waiver.
3. The comparison phase computes a feature-by-feature `kept/lost/changed/added` delta against
   the incumbent census. "Specification satisfied" is insufficient; any unwaived loss fails.
   The ADD rows above are also checked: an approved addition with surface "absent" is a failed
   finding (the revamp3 review lesson).
4. A different model/session performs the independent review from the census and comparison
   report, issuing a survival verdict for every incumbent feature and for every approved ADD row.
5. Only the final phase may deploy. It refreshes the data chain, deploys both Firebase projects,
   and compares the deployed pages against the same census.

## Phase Result

**PASS for design completeness; implementation status: AWAITING OPERATOR APPROVAL.** The
requested delta is augmentation-only, every incumbent instrument feature has a preservation
home, no removal is proposed, and every new figure/visual treatment maps to a reused example
reference. The revamp3 review's field-layer FAIL is answered by making every ADD row a concrete,
mechanical checkable surface. The campaign must not enter `p3_implement_augmentation` until the
approval artifact is signed and committed.
