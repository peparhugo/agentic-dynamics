---
status: accepted
---
# CAP Site Revamp 3: Augmentation Delta Preview

**Phase:** `p2_design_with_human_checkpoint`
**Decision state:** design complete; implementation is blocked pending the signed operator
approval at `approvals/cap_site_revamp3_design_approval.md`.
**Design rule:** preserve the instrument, then establish the field around it. This document
authorizes no implementation, deployment, removal, or data regeneration.

## Decision Basis

The preservation baseline is the verified, current source census in
`experiments/results/cap_site_revamp3/incumbent_census.json` [M]. It reconciles the earlier
feature matrix without a structural source delta and records these minimum site-wide contracts:

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
produce it.

| Addition | Page / placement | Evidence and editorial constraint | Example-library reference |
|---|---|---|---|
| Field statement and named question | Home lead; new `question.html` linked from, not substituted for, existing navigation | `[P]` framing: the question concerns accepted outcomes as tasks, environments, workflows, and time change. The new page adds a route; it does not displace Story or Methodology. | `type-editorial-measure.html`, `type-responsive-grid.html`, `svg-pattern-surface.html` |
| Origin-to-instrument bridge | Story after the existing origin | Keep the $20/Rome account visibly `[H]`; distinguish it from current corpus evidence. | `scroll-sticky-side.html`, `type-editorial-measure.html` |
| Repeated provenance receipt | Home, Evidence, Methodology, Framework, and Glossary | Show class, source/artifact, corpus or denominator, date, and limitation in first view. Use the existing `[M]`, `[C]`, `[H]`, `[X]`, `[P]` vocabulary. | `card-details.html`, `card-tooltip-badge.html` |
| Honest-null treatment | Evidence, Methodology, and Applications/Open Questions | Render `not measured`, `untriggered`, `underpowered`, and `no canonical output` as explanatory states. Never use `0`, an em dash, or a historical fallback to fill a missing current observation. | `svg-pattern-surface.html`, `card-tooltip-badge.html` |
| `cap_2b` decision card | Evidence verdict section | `[C]` decision over `[M]` outcomes: NON-INFERIOR in the randomized DeepSeek v4 Pro pilot; show both arms, n, decision rule, and the boundary that it authorizes design review only, not control activation. | `card-details.html`, `card-tooltip-badge.html` |
| Escalation figure | Evidence, adjacent to existing charts and tables | Show baseline `$0.008949`, Sol `E_x = 11.4671`, and Sonnet `E_x = 12.5134` with `[M]` costs, `[C]` ratios, `n=1` per escalation model, and no causal generalization. | `svg-marker-flow.html`, `svg-pattern-surface.html` |
| Calibration arc | Evidence verdict section | Distinguish 0/3 initial, 2/3 rerun with its interval, and the later 2b decision. The final label must state its authorization boundary. | `scroll-sticky-overlay.html`, `d3-line-arc.html` |
| Instrument cycle | Home and Framework, adjacent to rather than replacing existing framework diagrams | `[P]` method explanation: Instrument -> Derive -> Write policy -> Grid -> Campaign. It visibly encodes that unmeasured requirements block policy. | `svg-marker-flow.html`, `svg-animated-status.html` |
| N x M problem figure | New Question page and Story cross-link | `[P]` explanatory map only; no numeric claim is implied by the diagram. | `svg-pattern-surface.html`, `type-responsive-grid.html` |
| Eight planes, one engine/two modes, bounded autonomy | Framework around the existing calculator, chart, levers, and diagrams | `[P]` architecture figures cite `ARCHITECTURE.md`; they add explanation rather than hiding the operating instrument. | `svg-marker-flow.html`, `svg-filter-focus.html`, `svg-pattern-surface.html` |
| Cost-curve explorable | Methodology or Framework, separated from the live calculator | If a current canonical series exists, label it `[M]/[C]`; any N-squared scenario is `[C]`, exposes its formula/input, and never merges with observed data or forecasts a business result. | `d3-line-arc.html`, `d3-interactive-curve.html` |
| Ten rule cards | Framework, alongside existing provider/playbook material | Group rules by instrumented, proposed, and decided state. Each card exposes inputs, evidence class, source, limitation, and next test. | `card-details.html`, `card-tooltip-badge.html` |
| Typography and color system | `base.css`, applied to every preserved page and both themes | Editorial serif body, sans UI/display, mono receipts; warm paper/ink palette with teal for measured, amber for computed, and a non-color textual class. No ambient motion; respect reduced motion. | `type-editorial-measure.html`, `type-responsive-grid.html`, `svg-pattern-surface.html`, `svg-animated-status.html` |

## Diagram Inventory: Later Implementation Checklist

This table turns the reused diagram inventory into an auditable implementation plan. Each row
must be present in a served page, have a caption/alt text/provenance treatment, retain a prose
equivalent, and cite its local reference in a source comment. It augments the incumbent SVGs,
Chart.js canvases, and calculator; it does not replace them.

| ID | Target page | Data / evidence boundary | Reference | Required later verification |
|---|---|---|---|---|
| `instrument-cycle` | Home and Framework | `[P]` method structure | `svg-marker-flow.html`, `svg-animated-status.html` | Served SVG exists on both pages; static meaning survives reduced motion. |
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
   the incumbent census. “Specification satisfied” is insufficient; any unwaived loss fails.
4. A different model/session performs the independent review from the census and comparison
   report, issuing a survival verdict for every incumbent feature.
5. Only the final phase may deploy. It refreshes the data chain, deploys both Firebase projects,
   and compares the deployed pages against the same census.

## Phase Result

**PASS for design completeness; implementation status: AWAITING OPERATOR APPROVAL.** The
requested delta is augmentation-only, every incumbent instrument feature has a preservation
home, no removal is proposed, and every new figure/visual treatment maps to a reused example
reference. The campaign must not enter `p3_implement_augmentation` until the approval artifact
is signed and committed.
