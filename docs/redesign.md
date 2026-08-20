---
status: accepted
---
# Evidence Page Story-First Redesign

## Purpose

`firebase/public/evidence.html` should lead with the current story corpus: 221 stories, 1,097 sessions, 7 models, and $288.6909 total cost ([C], displayed as $288.69). This is the primary evidence for agentic-work dynamics. The earlier perturbation corpus remains available as provenance and methodological history, but it should no longer occupy most of the initial reading path.

The redesign is an information-architecture and narrative change, not a data revision. Implementation should move existing evidence blocks intact, replace only the framing copy identified below, and preserve every number, provenance tag, binding, chart, table target, denominator, tooltip, source, and limitation.

The narrative still moves through the same ideas: a passing result left important behavior unmeasured; an instrument made that behavior observable; the findings reveal distinct dimensions of agentic work; and those dimensions define a field of study. The page should tell that story directly. It must not name or visibly label the framework previously used to organize it.

## Design Decision

Use one closed-by-default `<details>` disclosure for the complete perturbation precursor.

This is preferable to shortening the precursor because shortening would force the deletion of measured claims, provenance tags, charts, tables, sources, or limitations. It is preferable to moving the precursor to a separate archive page because a second page would weaken the methodological lineage and create a second set of anchors and rendering contracts to maintain. A disclosure keeps the full archive in this document, makes the primary story corpus immediately visible, and gives interested readers access to every precursor artifact without imposing roughly 560 lines of archived analysis on the default reading path.

The disclosure is a visual compaction only. Its content remains in the DOM and remains searchable, linkable, bindable, and available to the generated table of contents. No precursor chart or table is replaced with a screenshot or summary-only substitute.

## 1. New Hero Copy

Use this copy verbatim, with the existing live bindings placed as shown:

> **THE CURRENT EVIDENCE**
>
> # What 1,097 Agentic Sessions Reveal
>
> Across <span data-stat="stories_total">221</span> linked stories (210 unique cells plus 11 reruns), <span data-stat="variants">7</span> models inherited and extended real codebases through <span data-stat="story_sessions">1,097</span> sessions. The corpus cost $288.6909 in total ([C], displayed as $288.69) and is the primary evidence for how verification, reviewed quality, solution dynamics, and cost change as agentic work compounds.
>
> A passing result shows whether one task finished. This instrument follows what that result conceals: how much verification a model chooses, what an independent reviewer and static analysis find, how far the solution moves, and what happens when each session inherits the code and context produced before it.

Immediately below the copy, use four evidence receipts:

| Label | Visible value | Binding and provenance |
|---|---:|---|
| Stories | `221` | `<strong data-stat="stories_total">221</strong>` |
| Sessions | `1,097` | `<strong data-stat="story_sessions">1,097</strong>` |
| Models | `7` | `<strong data-stat="variants">7</strong>` |
| Total cost | `$288.69` | `<strong>$<span data-stat="story_total_cost">288.69</span></strong>` with `[C] Computed: sum of story session costs` retained in visible or tooltip provenance |

This keeps the existing two hero occurrences of each story count and the existing hero occurrence of story cost, so the footer remains the third count occurrence and second cost occurrence. The receipts should not include precursor totals; introducing the archive in the first screen would recreate the current competition between primary and background evidence.

The recovered story-corpus inventory supplied for this redesign is `deepseek-v4-pro`, `deepseek-v4-flash`, `gpt-5.6-luna`, `gpt-5.6-sol`, `gpt-5.6-terra`, `claude-haiku-4-5`, and `claude-fable-5`. The current page and generated analysis payload instead contain legacy `claude-sonnet-5` story rows. Because the hard constraint also requires preserving every `data-anal-model` binding, this redesign must not silently relabel those rows. Keep the hero at the accurate aggregate `7 models` and preserve the existing binding key while the lineage is investigated.

This discrepancy is a shipping blocker, not an accepted inconsistency. Before implementation can pass acceptance, the measurement pipeline must establish whether `claude-sonnet-5` is a historical compatibility key for the supplied Fable corpus and document that mapping, or the corpus inventory must be corrected by its authoritative source. If the names represent different models, the requirement to preserve the Sonnet binding and verbatim Sonnet caveat conflicts with the supplied Fable ground truth and requires an explicit data-owner decision. The page must not publish a model-level relabel based on narrative inference.

## 2. Story-First Page Order

The DOM order should become the reading order. Move complete blocks rather than copying their visible text, so inline scripts, fallback values, attributes, and nearby caveats remain attached to the evidence they describe.

| Order | Section | Existing material | Design decision and reason |
|---:|---|---|---|
| 1 | **Hero: What 1,097 Agentic Sessions Reveal** | Replace the current two-corpus hero with the copy and four receipts above. Retain the provenance legend immediately after the hero. | The first screen must establish the current corpus as the primary evidence, not ask the reader to choose between two corpora. |
| 2 | **The Story Evidence** | Move `#current-story-instrument` and its current TL;DR directly below the hero. Remove the act label and chronological framing, but retain the matrix scope, 221 stories, 210 unique cells plus 11 reruns, 1,097 sessions, 7 models, five-session design, $288.6909 total, and all tags. | Readers need the instrument boundary before interpreting findings. The section should say plainly that observations come from inherited, linked codebases rather than independent benchmark prompts. |
| 3 | **Natural Verification Behavior** | Move `#story-models`, the protocol caveat, measurement distinctions, complete seven-model table, all three insights, and the cost-coverage note intact. | Verification is the strongest accessible entry point into the story evidence and is already first in the story section's internal order. |
| 4 | **Independent Review and Static Quality** | Move `#review-and-static-quality`, `#reviews`, `#what-the-reviewer-flags`, `#static-analysis`, their tables, notes, and every story-analysis binding intact. | This answers whether authored tests align with second-model review, AST structure, SonarQube results, and conventions without treating those signals as interchangeable. |
| 5 | **Solution Dynamics** | Move `#dynamics`, its complete bound table, strategy values, and insights intact. | The section carries the solution, basin-escape, and strategy measurements into the current multi-session corpus. |
| 6 | **The Five-Session Arc** | Move `#arc`, its table, `#snowballChart`, chart script, condition table, and findings intact. | The arc is the result the single-session precursor could not measure: inherited code and context change later-session cost and behavior. |
| 7 | **How We Got Here** | Add the compact precursor summary and closed archive disclosure specified in section 3. | Chronology becomes supporting explanation after the reader has seen the current evidence. |
| 8 | **The Field Now Visible** | Retain `#field-visible`, its observed/open distinction, CTA, and footer, but remove its old framework label and rewrite only the first sentence as needed to follow the archive. | The close can synthesize both distinct corpora without pooling their denominators or turning open control questions into findings. |

Within orders 3 through 6, preserve the current story section order exactly:

1. Natural verification behavior and the protocol caveat.
2. Second-model commit and story review.
3. Reviewer issue themes.
4. AST, SonarQube, and convention diagnostics.
5. Solution dynamics.
6. The five-session arc and seed-condition comparison.

Do not insert precursor charts, archive links, or a two-corpus ledger between those sections. The story evidence should read as one continuous main body.

### Story Instrument Introduction

Replace the current act-oriented introduction with this direct framing while preserving its existing numeric and provenance-bearing spans:

> **The Story Evidence**
>
> The current instrument follows linked work rather than isolated answers. Its matrix crosses 3 codebases, 2 tiers, 2 codebase qualities, and the existing conditions. The 221 executed stories comprise 210 unique cells plus 11 reruns; their five-session builds produced 1,097 captured sessions across 7 models for a CRUD API, static site generator, or notification service, with every task inheriting the prior codebase. The corpus cost $288.6909 in total ([C], displayed as $288.69). Multiple independent measurements examine verification, review quality, static quality, solution dynamics, recovery, and compounding cost without reducing them to one composite score.

The existing story TL;DR may remain a disclosure, but it should be open by default or promoted to a visible summary strip. Primary conclusions should not require an interaction to discover.

### Required Natural-Behavior Caveat

Keep this callout verbatim, prominently between the `#story-models` lead and the measurement key/table:

> **We never instructed the models how many tests to write.** Every model was asked to build the same system, but the number of tests and the edge cases covered were left entirely to the model. The difference between Luna at about 7 tests per story and Sonnet at about 122 is therefore natural, emergent behavior, not a failure to follow instructions. The verification gap measures the models' own unguided disposition toward verification, not instruction-following compliance.

The wording, bold opening, and placement are all part of the requirement. It must not move to a footnote, tooltip, methodology link, or closed disclosure. The adjacent four-way distinction between tests authored, tests executed, self-test pass rate, and independent evidence also stays in place because it defines what the finding does and does not measure.

## 3. How We Got Here

Use this visible summary before the disclosure:

> ## How We Got Here
>
> The current story instrument grew out of an earlier perturbation study. That precursor ran 227 single-session trials across 8 models and 10 stress operators, producing 224 game reports; the paired Grit view uses its own 201-session denominator. It discovered the perturbation operators and recovery signals that the story instrument now reuses across linked work. The two corpora remain distinct: the precursor explains the instrument's origin, while the 221-story corpus is the primary evidence on this page.

The precursor's eight-model scope is `deepseek-v4-pro`, `claude-fable-5`, `gpt-5`, `gpt-5-mini`, `gpt-5.5`, `gpt-5.6`, `gpt-5.6-fast`, and `gpt-5-nano`. Preserve the source's exact displayed model spelling wherever the archived tables or charts already provide it.

Follow the summary with one closed disclosure:

```html
<!-- The archive stays in the DOM; opening it triggers chart resize and redraw. -->
<details id="perturbation-archive" class="precursor-archive">
  <summary>Open the perturbation archive: 227 runs, 224 game reports, 8 models</summary>
  <div class="precursor-archive-content">
    <!-- Move the complete existing precursor introduction, limitations,
         findings, sources, validation, tables, canvases, and scripts here. -->
  </div>
</details>
```

Inside the disclosure, keep the precursor's existing internal order:

1. `#perturbation` introduction, TL;DR, provenance legend, and limitations, with the heading renamed from `Act I: Archived Precursor` to `Perturbation Precursor`.
2. Grit and recovery, including manifold/semantic comparison, filters, matrix, narration, and flail rate.
3. Economic and code outputs, including cost ranking, AST, SonarQube, constraints, and token costs.
4. Perturbation response and cross-model rollup.
5. Scope, model profiles, tool profiles, and the exploratory research notebook.
6. Quality, operator impact, modeled energy, drift trajectories, and strategy distribution.
7. `#data-sources` and independent validation.

The visible summary establishes the methodological inheritance in one screenful. The disclosure preserves the full record for auditability. Do not retain a separate precursor-to-story bridge after moving the archive below the story corpus; its job is performed by the new summary, and retaining it would reintroduce act chronology and duplicate the same explanation.

## 4. Golden-Circle Scaffolding to Remove

Remove these visible strings exactly. Replacement headings should use the direct section names in this plan.

| Current string | Replacement or disposition |
|---|---|
| `SIMON SINEK'S GOLDEN CIRCLE · WHY / HOW / WHAT` | Replace with `THE CURRENT EVIDENCE`. |
| `The Evidence: WHY / HOW / WHAT` | Replace with `What 1,097 Agentic Sessions Reveal`. |
| `WHY · THE CENTER` | Delete. |
| `WHY: The Gap a Passing Result Could Not Measure` | Fold its underlying gap into the hero; delete this standalone transition. |
| `ACT I · HOW THE MEASUREMENT BEGAN` | Delete. |
| `Act I: Archived Precursor` | Replace with `Perturbation Precursor`, retaining `id="perturbation"`. |
| Every occurrence of `ACT I · WHAT THE PRECURSOR DISCOVERED` | Delete. |
| `ACT I · WHAT · SCOPE AND EXPLORATION` | Delete. |
| `ACT I · WHAT · QUALITY AND MODELED EXTENSIONS` | Delete. |
| `WHY THE INSTRUMENT CHANGED` | Delete with the old bridge. |
| `ACT II · HOW THE MEASUREMENT SCALES NOW` | Delete. |
| `Act II: The Current Story Instrument` | Replace with `The Story Evidence`. |
| `ACT II · WHAT IS VISIBLE NOW` | Delete. |
| `ACT II · WHAT · INDEPENDENT MEASUREMENT` | Delete. |
| `ACT II · WHAT · SOLUTION BEHAVIOR` | Delete. |
| `ACT II · WHAT · LONGITUDINAL EVIDENCE · 5 LINKED SESSIONS` | Delete. |
| `WHAT · THE OUTSIDE OF THE CIRCLE` | Delete. |
| `WHAT: The Field Now Visible` | Replace with `The Field Now Visible`. |

Remove the corresponding page-local scaffolding when no longer used:

- `.circle-label` declarations and every `.circle-label` element.
- `.golden-hero`; replace it with a neutral evidence-hero class rather than retaining the old semantic name.
- `.narrative-step`, `.chapter-marker`, and `.bridge-step` where they exist only to visualize the previous framework.
- Comments that mention the named framework, its center/outside geometry, `WHY`, `HOW`, `WHAT`, or act numbering.
- Corpus-card status copy such as `CHRONOLOGICALLY FIRST`, `CHRONOLOGICALLY SECOND`, `ACT I`, and `ACT II`.

Remove or rewrite these source comments as part of the same cleanup:

- `<!-- Hero: name the Golden Circle and establish both corpus boundaries before findings. -->`
- `<!-- WHY stays concise so the chronological evidence remains the center of the page. -->`
- `<!-- Act I findings remain in their original evidence order under four readable chapters. -->`
- Every section-divider or ordering comment that labels content as `ACT I`, `ACT II`, `WHY`, `HOW`, `WHAT`, center, outside, circle, or ring.

Retain removed section fragments by rehoming their IDs on neutral destinations:

- Put `id="why-measure"` on the second hero paragraph that explains what a passing result conceals.
- Put `id="precursor-bridge"` on the visible `How We Got Here` summary paragraph that explains methodological inheritance.

These are compatibility anchors, not visible framework labels. They preserve inbound and generated fragments without keeping obsolete transition sections.

Ordinary grammatical uses such as `What the reviewer flags` are not framework labels and need not be awkwardly rewritten. The removal target is the visible organizing apparatus, geometric metaphor, act system, and comments/classes that encode it.

Keep the underlying argument in direct language:

- Unmeasured gap: a passing result conceals verification choice, recovery, reviewed quality, and inherited-work cost.
- Instrument: linked story sessions and independent measurement angles expose those dimensions.
- Findings: verification, review/static quality, solution dynamics, and cost do not collapse onto one price axis.
- Field: the measurements support further questions about routing, retry, escalation, stopping, and long-horizon value.

## 5. Number, Provenance, and Binding Contract

### Corpus Boundaries

| Corpus | Required scope | Role on the redesigned page |
|---|---|---|
| Story corpus | 221 stories, 1,097 sessions, 7 models, $288.6909 total cost, displayed as $288.69 `[C]` | Primary evidence in the hero and main body. |
| Perturbation precursor | 227 single-session runs, 224 game reports, 201 paired Grit sessions, 8 models, 10 operators | Compact background and archive. Its denominators remain separate. |

Never add 227 precursor runs to 1,097 story sessions, call them one total, or imply that 224 reports and 201 Grit sessions are interchangeable counts. The precursor came first chronologically, but chronology must not determine visual priority.

### Provenance

Preserve every existing provenance marker and its attached claim:

| Tag | Meaning | Preservation rule |
|---|---|---|
| `[M]` | Measured from executions, billing, or artifacts | Keep the same source and denominator. Reordering does not broaden a measurement. |
| `[C]` | Computed from measured values | Keep the calculation status, precision, and rounding. In particular, story total cost remains `[C]`, not `[M]`. |
| `[H]` | Heuristic estimate, score, threshold, or classification | Keep the relevant limitation adjacent to the claim. |
| `[X]` | External source or constant | Keep the citation and do not imply that the corpus measured it. |

Do not add `[P]`; it is not part of the current page legend. Preserve the legend text `[M] measured`, `[C] computed`, `[H] heuristic`, and `[X] external` near the top of the page and inside the archive where readers encounter precursor claims.

### `data-stat` Bindings

Preserve the spelling, fallback, wrapper formatting, and corpus meaning of every current static key:

| Key | Current static occurrences | Required use |
|---|---:|---|
| `stories_total` | 3 | Hero lead, hero receipt, and footer; fallback `221`. |
| `story_sessions` | 3 | Hero lead, hero receipt, and footer; fallback `1,097`. |
| `variants` | 3 | Hero lead, hero receipt, and footer; fallback `7`. |
| `story_total_cost` | 2 | Hero receipt and footer; fallback `288.69`, with the dollar sign outside the bound span. |
| `reports` | 2 | Existing precursor rollup/profile locations inside the archive; fallback `224`. |

The generated cost renderer may emit `data-stat="ci95"`; retain that generated attribute and fallback behavior. Do not introduce story totals into precursor elements or reuse a generic session binding for a precursor denominator.

The current footer suffix calls story cost `measured`, which conflicts with the authoritative `[C]` provenance. This redesign explicitly replaces that suffix with `computed [C]`; the value, binding, precision, and footer position remain unchanged. Correcting the provenance word is required preservation, not a new interpretation.

### `data-anal` Bindings

Keep these seven row keys unchanged wherever they currently occur:

- `deepseek-v4-flash`
- `gpt-5.6-luna`
- `deepseek-v4-pro`
- `claude-haiku-4-5`
- `gpt-5.6-terra`
- `claude-sonnet-5`
- `gpt-5.6-sol`

Keep all child fields unchanged:

- Static analysis: `commits`, `lines_added`, `functions_added`, `sonar_smells_delta`, `sonar_complexity_delta`, and `avg_convention`.
- Solution dynamics: `solution_correctness`, `solution_constraints`, `solution_quality`, `solution_novelty`, `basin_escape`, and `lsp_errors_per_cell`.

Shared `app.js` matches these attributes to `DYNAMICS_DATA.analysis.models`. A visible fallback can look plausible even when a binding is broken, so acceptance must inspect the post-load DOM rather than only the source HTML.

### Literal Preservation Method

Before implementation, capture a machine-readable baseline of all numeric text nodes and attributes from `evidence.html`, grouped by their nearest section ID. After implementation, compare the multiset within each moved evidence block. Exclude only the framing nodes explicitly replaced by this plan, then verify that every number removed from the old framing still appears in the new hero or precursor summary with the same corpus meaning.

Also exclude renderer placeholders from evidence-literal comparison: empty cells, `Loading...`, em dashes used as pending values, and zeroes whose containing `data-anal` cells are populated after load. These are DOM states, not measured fallbacks. Do not replace them with invented static measurements. With no live payload, render an explicit `Data unavailable` state; with a live payload, require every supported binding to populate.

Also snapshot and compare:

- Every `[M]`, `[C]`, `[H]`, and `[X]` occurrence with its containing claim.
- Every `data-stat`, `data-anal-model`, and `data-anal` attribute/value pair.
- Every `title` containing provenance, a denominator, or a numeric explanation.
- Every chart dataset literal and table fallback value in inline JavaScript.
- Every source URL, methodology link, footer link, and internal fragment.

This mechanical comparison is required because visual review will not detect a changed tooltip number, dropped fallback, or disconnected binding.

## 6. Chart and `app.js` Integrity Register

The shared `app.js` owns generic `data-stat` replacement, `data-anal-model` row population, and generated heading navigation. The five charts and most fixed table renderers are currently created by inline scripts in `evidence.html`. The redesign must preserve both contracts rather than assuming all chart behavior lives in `app.js`.

### Pre-Implementation Data-Source Blocker

The current generated payload exposes story-model records through `D.models` and `D.charts`, while several blocks presented as precursor evidence consume those generic properties. It separately exposes `D.perturbation_models`. Moving the blocks intact would therefore preserve a current defect: post-load cost, LOC, narration, model-card, and energy content can show seven story models inside an eight-model precursor archive.

Do not conceal this mismatch with fallback text or relabel story data as precursor data. Before shipping the redesign, establish an explicit precursor payload in the generated schema for every archived renderer and update the renderer consumers to use it. The values must come from the existing precursor result records through `scripts/build_data.py`; they must not be re-derived in prose or manually copied into `evidence.html`. Keep the existing `D.models`, `D.charts`, story `data-anal` contract, and generated `data.js` workflow intact for story consumers. This prerequisite may require a separately reviewed producer change even though the eventual page redesign remains centered on `evidence.html`.

Acceptance for the archive is post-load identity, not merely DOM presence: its model-level charts, tables, cards, and energy rows must contain the eight precursor models and no story-only row unless that model is genuinely present in the precursor records.

### Canvases

| Required ID | Corpus | Consumer | Disclosure behavior |
|---|---|---|---|
| `snowballChart` | Story | Story-arc `DOMContentLoaded` handler | Remains visible in the main body and renders normally. |
| `gritMatrixChart` | Precursor | Footer renderer and filter rebuild function | Hidden initially; resize and update when `#perturbation-archive` opens. |
| `narrationChart` | Precursor | Footer `DOMContentLoaded` renderer | Hidden initially; resize and update on open. |
| `costBarChart` | Precursor | Footer `DOMContentLoaded` renderer | Hidden initially; resize and update on open. |
| `locVsCostChart` | Precursor | Footer `DOMContentLoaded` renderer | Hidden initially; resize and update on open. |

### Table Bodies

Preserve every current `<tbody>` ID exactly once:

| Required ID | Population contract |
|---|---|
| `narration-tbody` | Cleared and rebuilt by the precursor footer renderer. |
| `cost-ranking-tbody` | Cleared and rebuilt from model records. |
| `ast-metric-body` | Receives generated precursor AST metric rows. |
| `sonar-quality-body` | Receives generated precursor Sonar rows. |
| `token-cost-tbody` | Cleared and rebuilt with token-cost rows. |
| `rollup-tbody` | Retains the static cross-model rollup rows. |
| `tool-profile-body` | Receives the eight tool-profile rows from its adjacent IIFE. |
| `rvs-body` | Receives reasoning-volatility rows. |
| `drift-body` | Receives semantic-drift rows. |
| `recovery-body` | Receives perturbation-recovery rows. |
| `coupling-body` | Receives think/do coupling rows. |
| `stability-body` | Receives cluster-stability rows. |
| `cascade-body` | Receives divergence-cascade rows. |
| `sonar-impact-body` | Receives perturbation quality-impact rows. |
| `operator-impact-body` | Receives computed operator-impact rows. |

### Other Renderer and Structural Targets

Preserve spelling, case, element type, and uniqueness for:

- `grit-model-filters`
- `ast-metric-head`
- `ast-insight`
- `model-cards-root`
- `energy-ranking-cards`
- `strategy-distribution`
- `no-data-row`
- `sonar-quality-tbl`
- `tool-profile-tbody`
- `sonar-impact-tbody`
- `operator-impact-tbl`
- `data-sources`

Do not move an adjacent immediate IIFE before its target exists. The safest structure is to move each precursor content block and its local script together, then leave the large `DOMContentLoaded` renderer after all story and archive targets.

`no-data-row` has conditional cardinality: it exists once before successful cost-table population or when the dataset is empty, and zero times after successful rows replace it. Other registered targets remain exactly once. The Sonar renderer must likewise clear its `Loading...` placeholder before appending successful rows; a populated table must never retain the loading row.

### Expand-Time Rendering

Charts initialized under a closed `<details>` can measure a zero-width parent. Add one `toggle` listener to `#perturbation-archive`; when `details.open` becomes true, wait for layout with `requestAnimationFrame`, obtain all four precursor Chart instances, call `resize()`, and then call `update('none')` or the installed Chart.js equivalent that redraws without animation.

Implementation should retain named references to the four instances in a small precursor chart registry. This is more maintainable than four unrelated listeners and does not depend on private Chart.js state. Fold the existing Grit-only disclosure listener into this registry so the Grit chart is not resized twice.

Flatten the current nested Grit `<details>` when it moves inside the outer archive. Its filters, explanatory copy, and `gritMatrixChart` remain intact, but a chart must not sit inside a second closed disclosure when the archive-open listener runs. Because filtering destroys and rebuilds the Grit chart, the Grit build function must replace its entry in `precursorCharts` every time it creates a new instance.

The required behavior is:

```js
// Closed disclosures have no reliable chart width; redraw after the browser lays them out.
perturbationArchive.addEventListener('toggle', function () {
  if (!perturbationArchive.open) return;
  requestAnimationFrame(function () {
    precursorCharts.forEach(function (chart) {
      if (!chart) return;
      chart.resize();
      chart.update('none');
    });
  });
});
```

The registry should contain `gritMatrixChart`, `narrationChart`, `costBarChart`, and `locVsCostChart` instances after their normal `DOMContentLoaded` construction. Opening, closing, and reopening the archive must not create duplicate charts, duplicate filter controls, or duplicate event handlers.

### Anchors and Generated Navigation

Keep all existing evidence IDs attached to their original content, especially `#story-models`, `#reviews`, `#static-analysis`, `#dynamics`, `#arc`, `#perturbation`, `#data-sources`, and every precursor chart-section heading. `index.html` links to `evidence.html#story-models`, so that fragment must land directly in the main story evidence after the reorder.

Also preserve `#why-measure` and `#precursor-bridge` on their neutral replacement destinations as specified above.

The generated table of contents reads every `h2` and `h3`, including headings inside a closed disclosure. When a generated navigation link targets content in `#perturbation-archive`, its click handling must open the ancestor disclosure before scrolling and focusing the heading. Otherwise the anchor technically resolves but remains invisible. Keep existing explicit IDs when changing heading copy so generated slug changes do not break inbound or bookmarked links.

Use the same archive-opening helper for three paths: generated TOC clicks, `location.hash` during `DOMContentLoaded`, and later `hashchange` events. For a non-empty fragment, resolve the target, collect every closed ancestor `details`, open those disclosures from outermost to innermost, wait for layout, and then scroll/focus. Opening the full ancestor chain is necessary for nested targets such as `#data-sources`. This also makes an external URL such as `evidence.html#cost-ranking` work without requiring a prior in-page click.

### Search and Social Metadata

Update the document description and Open Graph description to lead with the same story-corpus scope as the visible hero: 221 stories, 1,097 sessions, 7 models, and $288.69 computed total cost. Do not lead metadata with the older 227/249-session precursor wording. The precursor counts remain preserved in `How We Got Here`; metadata priority should match page priority.

## 7. Visual Hierarchy and Responsive Behavior

- Give the story hero and four receipts the strongest visual hierarchy on the page. The receipts should collapse to a two-column grid and then one column without changing their reading order.
- Use normal section headings for the story body. Do not replace the removed kickers with another repeated taxonomy or act system.
- Keep the natural-behavior callout fully visible and high contrast on desktop and mobile.
- Style `How We Got Here` as a quieter background band. Its summary remains readable without opening the archive, but it must not visually resemble a disabled or deprecated section.
- Make the archive summary a semantic, keyboard-operable `<summary>` with a visible focus state and native open/closed indication.
- Keep tables horizontally scrollable at narrow widths. Collapsing the archive must not create page-level horizontal overflow when it opens.
- Verify at 375, 768, 1024, and 1440 CSS pixels in dark and light themes.
- Preserve reduced-motion behavior. The archive redraw must not force chart animation when the user requests reduced motion.

## 8. Acceptance Checks

The later `evidence.html` implementation is complete only when all checks pass:

1. The first screen uses the hero copy and binding placement from section 1 verbatim and identifies 221 stories, 210 unique cells plus 11 reruns, 1,097 sessions, 7 models, and $288.69 as the current and primary evidence.
2. The hero retains $288.6909 as the precise total and `[C]` as its provenance; no story-cost label or footer calls it `[M]` or merely `measured`.
3. The story body appears before any full precursor table, chart, model profile, research notebook, or validation appendix.
4. The story sections remain in this order: natural verification, second-model review, reviewer issue themes, AST/Sonar quality, solution dynamics, and five-session arc.
5. The natural-behavior caveat is present verbatim, visible without interaction, and located before the story verification comparison.
6. The adjacent authored/executed/self-test/independent-evidence distinction remains visible.
7. `How We Got Here` states that the precursor discovered the operators and recovery signals reused by the story instrument.
8. The precursor summary keeps 227 runs, 224 reports, 201 Grit sessions, 8 models, and 10 operators as separate, correctly described quantities.
9. The full precursor is closed by default in one disclosure, while every archived claim, table, chart, source, caveat, and validation block remains in the DOM.
10. No visible text, comment, class name, heading, status label, or kicker names Simon Sinek, the Golden Circle, its rings, its center/outside, `WHY / HOW / WHAT`, or the old act structure, including `Act I: Archived Precursor`.
11. The page still communicates the unmeasured gap, instrument, findings, and field without naming that organizing framework.
12. Every pre-redesign number remains associated with the same corpus, denominator, precision, fallback, tooltip, and provenance tag, except duplicated framing occurrences explicitly remapped in this plan.
13. No text pools 227 precursor runs with 1,097 story sessions or treats 224 reports and 201 Grit sessions as the same denominator.
14. Static counts of `data-stat` keys match the binding register, and every supported key resolves to the expected post-load value.
15. All seven `data-anal-model` keys and all twelve `data-anal` fields remain unchanged and populate after `DOMContentLoaded`.
16. All five canvases exist exactly once. `snowballChart` renders on initial load; all four precursor charts have non-zero width and render after the archive first opens and reopens. The Grit chart is not inside a second closed disclosure, and its registry reference remains current after filter-driven rebuilds.
17. All fifteen `<tbody>` IDs and every stable renderer target in the integrity register exist exactly once and populate without a console exception. `no-data-row` follows its documented conditional cardinality.
18. Opening the archive does not create a second Chart instance, duplicate filter buttons, or duplicate table rows.
19. Every authored and generated fragment resolves. TOC clicks, initial `location.hash`, and later `hashchange` navigation into the precursor open the archive before scrolling; `evidence.html#story-models` remains visible without opening anything.
20. Every post-load precursor renderer uses an explicit precursor payload and shows the recovered eight-model precursor scope rather than generic story `D.models` or `D.charts` content.
21. Search and Open Graph descriptions lead with the story corpus rather than the precursor.
22. The browser console has no null-target, duplicate-ID, `toFixed`, chart sizing, or binding errors with live `data.js`.
23. With `data.js` unavailable, static story values remain legible and corpus-correct; dynamic cells report `Data unavailable` rather than invented values or a permanent `Loading...`. With live data, all placeholders are removed, including the Sonar loading row.
24. Desktop and mobile preserve the story-first hierarchy in dark and light themes, with no page-level horizontal overflow.
25. `firebase/public/data.js` remains generated, never hand-edited, and is rebuilt only from the data pipeline. Any precursor payload correction must be made in the producer and reviewed separately from narrative copy.
26. `pytest tests/` passes, followed by a browser smoke test for initial load, archive open/close/reopen, direct precursor fragment navigation, story fragment navigation, chart filtering, and theme switching.
27. Corpus inventory checks use the recovered canonical lists in this plan: seven story models at the aggregate boundary and eight precursor models in archive renderers. The Fable/Sonnet lineage blocker is resolved and documented before shipping; preserving the legacy `claude-sonnet-5` binding is not permission to publish contradictory model identity.

## Implementation Sequence

1. Snapshot numeric literals, provenance claims, IDs, bindings, hrefs, metadata, model identities, and chart datasets before editing.
2. Resolve and document the Fable/Sonnet lineage, then resolve the generic story-versus-precursor payload mismatch in the generated data producer and verify the recovered eight-model archive post-load.
3. Replace the hero and metadata with the exact story-first copy while preserving binding occurrence counts and rehoming `#why-measure`.
4. Move the complete story instrument and its four evidence sections directly below the hero.
5. Add `How We Got Here`, wrap all precursor blocks in `#perturbation-archive`, rehome `#precursor-bridge`, and remove the obsolete bridge.
6. Remove every framework label, act label, related comment, and unused visual scaffold listed above.
7. Flatten the nested Grit disclosure, consolidate precursor chart references, and add one expand-time resize/update listener.
8. Make generated precursor navigation open its ancestor disclosure before scrolling.
9. Run automated before/after integrity comparisons, `pytest tests/`, and browser checks at the required widths and themes.

The smallest safe page implementation is therefore a DOM reorder, exact framing-copy replacement, one semantic archive wrapper, and one chart lifecycle fix. It introduces no new measurement, no new chart, and no archive page. The existing generic story-versus-precursor payload collision is a separate precondition: it requires an explicit generated precursor payload rather than a hand-authored value or silent schema assumption.
