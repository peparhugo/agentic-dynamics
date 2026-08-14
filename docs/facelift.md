# Operational Framework Face-Lift Plan

## Purpose and non-negotiables

The Operational Framework page should read as one golden-circle argument rather than a catalogue of adjacent features:

1. **WHY:** measured information should become testable policy.
2. **HOW:** instrument the work, derive information, expose the cost levers (`C₀`, `P`, `ε`, `r`, `β`, and `EPM`), and let an operator test those levers in the calculator.
3. **WHAT:** choose policy arms, distinguish reversible from compounding commitments, route autonomous work, and repeat the comparison as a campaign.

The redesign is presentation and information architecture, not a data revision. Implementation changes only `firebase/public/framework.html`; it does not change `base.css`, `app.js`, or generated `data.js`. Every existing number, formula, fallback, `data-stat` binding, element ID, and link remains byte-for-byte equivalent unless only its surrounding layout changes. The new architecture visual is an inline SVG with no runtime or third-party dependency.

The source baseline for this plan is `firebase/public/framework.html` as audited on 2026-08-14. The preservation register at the end of this document is the implementation checklist.

## 1. Current problems

### Narrative and hierarchy

- The page opens with a `What — from information to policy` pill even though the opening proposition is the WHY. It therefore announces the answer before establishing the belief.
- The ten rules appear immediately after the proposition. This puts WHAT before HOW and makes the page feel like a rule inventory rather than an operational argument.
- The levers, equations, chart, calculator, doors, model-profile CTA, and playbook each restart the narrative. Their individual headings are strong, but there is no visible through-line connecting an event in the ledger to a policy decision.
- The engineering machine is absent. Readers see formulas and recommendations without seeing how `ExperimentSpec`, factor cells, attempts, measurement rules, information, and policy arms form one repeatable loop.
- The page has no visible `<h1>`. It begins at `<h2>`, weakening document hierarchy and the generated table of contents.
- The autonomous workforce-management comparison is outside a semantic section. The final calculator CTA is also a free-floating block, so alternating section backgrounds depend on sibling position rather than meaning.

### Density and scanability

- Ten same-weight rule rows create a long visual wall. Observed, derived, and modeled material is explained in prose but not consistently encoded in the cards.
- Lever cards repeat nearly identical border and text styles. Their measured-versus-modeled distinction is carried mostly by paragraphs rather than card anatomy.
- Three equation blocks, a chart, six statistic cards, and a calculator are separated into successive dense blocks. The calculator feels bolted on instead of being the main operational workbench.
- The provider playbook combines a mapping table, pricing table, cache guidance, routing prose, three routing tiers, command examples, provider profiles, and escalation tables in one uninterrupted section.
- “Model Cards” is a full section containing only a CTA. It interrupts the WHAT sequence without providing a corresponding visual set-piece.

### Visual-system debt

- `framework.html` contains roughly one hundred inline style declarations. Accent colors, three-pixel left rules, centered subsection headings, formula panels, control pills, command snippets, and spacing are repeatedly hand-authored.
- Page-local surfaces use hard-coded translucent dark colors. They do not all inherit the light-theme treatment already provided by `base.css`.
- The page uses rounded cards everywhere but does not vary hierarchy through scale, negative space, border weight, or composition. As a result, a primary decision and a supporting note often have the same visual importance.
- The local fixed-column workforce table and escalation grid do not have complete narrow-screen behavior. Formula content can become cramped, and the architecture has no current mobile representation because it does not yet exist.

### Interaction and accessibility

- Chart controls are links with `href="#"` and inline handlers rather than semantic toggle controls; their active state is color-only. Because existing hrefs must remain working, improve them in place with keyboard handling, `role="button"`, and `aria-pressed` rather than replacing the anchors.
- Calculator mode controls lack `aria-pressed` and `aria-controls`. The “show computation” interaction uses pointer-only hover styling.
- The active navigation item is color-only and has no `aria-current="page"`.
- The generated table of contents includes every `h2` and `h3`. The current number of subsection headings makes the generated navigation noisy, and headings containing `<br>` can produce poor generated slugs.
- A live seven-entry `model_costs` array currently conflicts with `costs[7]` in the page-local calculator code. The default augmented update can throw before rendering output or building the chart. This is an existing functional defect, not permission to change any cost value or fallback.
- `toggleHow()` selects the first calculator button, so it can relabel the Augmented Workforce mode control instead of the disclosure control. This is also an existing behavior defect and must be repaired without changing the equations or defaults if calculator behavior is touched during implementation.

## 2. Target page structure

The DOM order should become the visual and rhetorical order. All existing section IDs remain in the document so old fragments and generated links continue to resolve.

| Order | Golden-circle role | Existing ID | Visual treatment | Design decision and reason |
|---:|---|---|---|---|
| 1 | WHY | `why` | Full-width dossier hero with the only `<h1>`, a concise thesis, two evidence receipts, and a direct jump to the architecture | The belief must be encountered before rules or controls. Reusing `.dossier-hero`, `.hero-grid`, `.thesis`, and `.proof-ledger` makes it feel native to the site. |
| 2 | WHY → HOW → WHAT | new `architecture` | The architecture figure described in section 4 | The machine is the bridge from belief to operating method and should be the visual centerpiece, not an appendix. |
| 3 | HOW | `levers` | A lever console split into measured/control and compounding/model cards | Readers should first learn which values are observed, which are operator-controlled, and which grow over time. |
| 4 | HOW | `cost-model` | Three formula plates beside the existing chart and projection controls | Equations become the compact reference rail for the calculator rather than a separate wall of math. |
| 5 | HOW | `calculator` | A large two-column workbench with inputs on the left and sticky result receipts on the right | The calculator is where HOW becomes tangible. Giving it the widest and strongest panel makes interaction the center of the page. |
| 6 | WHAT | `decisions` | Three equal-height door cards: Two-Way, One-Way, and Autonomous | These are the first outputs of measured information and provide the cleanest transition from calculation to action. |
| 7 | WHAT | `rules` | Ten policy cards grouped into “selection and verification,” “compounding economics,” and “autonomous operations” | Grouping preserves every rule while replacing the undifferentiated list with a usable control-rule catalogue. |
| 8 | WHAT | `playbook` | Scannable tactic and provider card grids, ending with escalation economics | The playbook demonstrates concrete policy arms after the reader understands doors and rules. |
| 9 | WHAT | `model-cards` | Compact evidence handoff embedded as the closing dossier panel, still with its own section ID | The existing CTA remains linkable without interrupting the main playbook. |
| 10 | WHAT → repeat | none | Closing campaign strip and existing `#calculator` CTA | Returning to the calculator closes the loop: choose an arm, measure it, and run the next grid. |

### WHY: opening proposition

- Replace the current pill with an explicit `.section-kicker` reading `WHY / BELIEF`.
- Use `Measured information becomes testable policy.` as the `<h1>`. Keep the exact proposition; only its semantic level and line treatment change.
- Keep the existing Snowball and verification claims and values in two `.proof-card` receipts. The split makes the two motivating facts comparable without introducing a third claim.
- Keep the audience and domain-validity note, but place it beneath the hero as a narrow `.highlight-box`. It remains supporting scope, not hero copy.
- Add two CTAs: `See the machine` points to `#architecture`; `Test your levers` points to `#calculator`. The second reuses the existing calculator fragment.
- Use substantial negative space and one restrained radial glow. The opening should feel like a dossier cover, not a feature landing page.

### Architecture bridge

- Place the architecture immediately after the hero, under the kicker `WHY → HOW → WHAT / SYSTEM MAP`.
- Pair the figure with a short plain-language caption: the ledger makes an unmeasured gap visible; measurement rules turn events into information; control rules can then be tested as policy arms.
- Do not attach measured numerical claims to the diagram. Its labels are architecture and process semantics, so the visual cannot silently create a new evidence claim.
- Provide a text-equivalent ordered list after the `<figure>`. This supports screen readers, print, and mobile readers who do not want to pan a dense systems diagram.

### HOW: levers

- Keep augmented and autonomous modes, but render each as a titled console lane rather than two runs of identical cards.
- Give each lever card four stable fields: symbol, operational question, evidence status, and door effect. This makes `C₀`, `P`, `ε`, `r`, `β`, `v`, `b`, `Eₘ`, `W`, and `EPM(t)` scannable.
- Use cyan for directly selectable or measured inputs, amber for compounding/model inputs, and sky/cyan for autonomous-routing inputs. Color supplements the field labels; it never replaces them.
- Move the workforce-management equivalence table into the autonomous lane as a collapsible or secondary comparison panel. It explains the operating model exactly where autonomous levers are introduced.
- Preserve the existing prose-tier language `Observed`, `Derived`, and `Modeled`. No literal provenance tags currently appear in `framework.html`; implementation must not imply that a modeled number became measured merely because its card looks stronger.

### HOW: cost model

- Use three formal formula plates: Augmented Workforce, Autonomous Workloads, and Business Value Index. Each plate gets a symbol rail, the unchanged equation text, and a one-line “controls” footer.
- Put the chart and its controls in a single bordered plot panel. The controls remain visually attached to the canvas so projection, EPM scenario, and view read as chart state.
- Retain all existing chart labels, years, rates, and hard-coded chart data. A visual refactor must not opportunistically synchronize them with `data.js`; that would change the numeric baseline.
- Render the six existing summary statistics as a low-profile receipt row beneath the plot. They are supporting context, not the focal interaction.

### HOW: calculator centerpiece

- Wrap the calculator in a large `.framework-workbench` surface with a subtle cyan top rule and the strongest page-local shadow.
- Keep Augmented Workforce and Autonomous Workloads as a segmented control above the panel. Add semantic state (`aria-pressed`, `aria-controls`) while preserving both IDs and handler entry points.
- Desktop layout uses a `minmax(0, 1fr) minmax(19rem, 0.72fr)` grid. Inputs remain on the left; `roi_output`, `roi_context`, and the computation disclosure occupy the right.
- Results use receipt cards with tabular numerals. Their current generated labels and values remain untouched because `updateROI()` owns their content.
- Place “Show how this is computed” directly under the result cards as a real disclosure with a stable ID. The formula output remains plain text in `howComputed`, preserving safe rendering and horizontal scrolling.
- At `max-width: 768px`, stack modes, inputs, results, and disclosure. Keep every range input at least 44 pixels high and prevent the formula output from widening the page.
- Treat the existing seven-model indexing failure and disclosure-button targeting defect as behavior-preservation fixes in `framework.html` only. Repairing those defects must not edit `model_costs`, `escalation_tiers`, formulas, range values, or fallback labels.

### WHAT: doors set-piece

- Introduce the section with `WHAT / POLICY DECISIONS` and the existing “Test reversible choices. Model durable commitments.” heading.
- Use three equal cards with a top status rail rather than three nearly identical left borders.
- Two-Way Door uses `var(--ac)` and a loop-arrow glyph; its footer remains `Experiment. Measure. Iterate.`
- One-Way Door uses `var(--am)` and a ratchet/commit glyph; its footer remains `Model cumulative cost. Project 36 months.`
- Autonomous Door uses `var(--cy)` and a branching route glyph; its footer remains `Design for <1% human escalation. Measure WOC daily.`
- Put `policy = a factor level / arm` in a shared caption beneath the cards. At routing, annotate the decision boundary: per-task model selection is a two-way door; provider-default architecture, reserved capacity, or distribution lock-in becomes a one-way door.
- Keep the 30-day implementation sequence as a four-step horizontal strip on desktop and an ordered stack on mobile.

### WHAT: ten rules

- Preserve `rule-1` through `rule-10` and every sentence, number, formula, and badge.
- Group Rules 1, 2, and 5 under **Selection and verification**; Rules 3, 4, and 10 under **Compounding economics**; Rules 6, 7, 8, and 9 under **Autonomous operations**. The grouping is navigational and does not renumber or reinterpret a rule.
- Use `.chapter`-style cards with the rule number in a fixed mono column and the lever/formula line in a subdued footer.
- Preserve `Extension` and `Modeled` badges. Add no visual treatment that suggests an extension is directly measured.
- Keep the methodology audience link and modeled-projection disclaimer adjacent to the catalogue.

### WHAT: provider playbook

- Begin with a five-card policy map for caching, routing, budget enforcement, batch scheduling, and escalation. Each card retains its rule mapping and links visually back to the corresponding rule numbers.
- Keep per-token pricing as a compact comparison table with horizontal overflow at narrow widths.
- Render Cache Strategy as a three-card progression with the cache write/read decision directly below it.
- Render Simulated Model Routing as a formal chain (`request → classifier → default → verification gate → escalation`) followed by the three existing tier cards. Mark the routing gate with the same two-way/one-way annotation used in the architecture visual.
- Render Budget Enforcement as three code-oriented cards. Preserve every command and numeric option exactly.
- Render provider references as a three-card grid with provider name, price line, cache behavior, and best-fit statement in consistent positions.
- End with Escalation Economics as the section’s decision receipt: two comparison tables and the existing takeaway in one bounded panel.
- Keep `model-cards` as the closing evidence handoff immediately after the playbook. Its CTA still targets `evidence.html`; the section should look intentional without pretending to contain cards it does not contain.

## 3. Design-token mapping

`base.css` remains unchanged. The implementation should define page-local semantic aliases and components inside `framework.html` so all new surfaces inherit dark/light theme values from the shared tokens.

### Shared tokens to semantic roles

| Existing token or class | Framework role | Reason |
|---|---|---|
| `--bg` | Page ground and negative-space bands | It is the darkest shared surface and preserves the dossier backdrop. |
| `--bg2` | Alternating golden-circle chapters | It separates WHY, HOW, and WHAT without brittle `nth-child` striping. |
| `--bg3` | Cards, SVG nodes, workbench panels | It is the established primary panel surface. |
| `--bg4` | Inset controls, formula rails, result wells | It creates depth without introducing a new color. |
| `--b` | Default one-pixel borders and SVG ring guides | Quiet structure keeps the formal diagram from becoming neon decoration. |
| `--ba` | Active boundaries and primary panel outlines | The stronger shared border is enough for hierarchy. |
| `--t` | Headlines, node titles, primary values | Highest-contrast text is reserved for conclusions and labels. |
| `--t2` | Body copy and node detail | This remains the normal reading color. |
| `--t3` | Metadata, evidence status, edge labels | Muted text separates annotation from claims. |
| `--am` | WHY core, compounding variables, one-way doors | Amber carries belief and durable commitment, matching existing use. |
| `--ac` | HOW, measurement, selectable controls, two-way doors | Cyan already identifies active and measured operational surfaces. |
| `--cy` | WHAT routing, autonomous doors, campaign output | The sky accent distinguishes policy application from measurement. |
| `--success` | Valid/accepted outcome state only | Green should retain its status meaning rather than becoming decoration. |
| `--danger` | Invalid dependency or failed gate only | Red remains exceptional and is not part of the normal architecture path. |
| `--panel-shadow` | Hero ledger, architecture figure, calculator workbench | Using one shared shadow avoids card-by-card visual noise. |
| `--ring` | Focus state and active SVG/node halo | It is already the shared interaction ring. |
| `.section-kicker` | Explicit `WHY`, `HOW`, and `WHAT` labels | The shared mono kicker creates the requested narrative signposts. |
| `.dossier-hero`, `.hero-grid`, `.thesis` | WHY composition | These existing primitives already provide the modern dossier opening. |
| `.proof-ledger`, `.proof-card` | Opening evidence receipts and calculator summaries | Their label/value anatomy is suited to traceable measurements. |
| `.receipt-grid`, `.receipt` | Lever, provider, and result cards | Reuse provides consistent, responsive card groupings. |
| `.comparison-panel` | Door notes, WFM mapping, escalation economics | It visually communicates alternatives without inventing another component family. |
| `.chapter-list`, `.chapter` | Ten-rule catalogue | The fixed numeric gutter improves scanning. |
| `.tbl` | Pricing and escalation tables | It already supplies a bounded, horizontally scrollable table. |
| `.cta-btn`, `.cta-bar` | Hero and closing actions | Existing actions retain cross-page consistency. |

### Page-local aliases

These aliases are mappings, not new palette values. Keeping them page-local obeys the `base.css` constraint while making the eventual CSS readable.

```css
/* Semantic aliases keep component rules independent of raw palette choices. */
.framework-page {
  --fw-why: var(--am);
  --fw-how: var(--ac);
  --fw-what: var(--cy);
  --fw-surface: var(--bg3);
  --fw-inset: var(--bg4);
  --fw-line: var(--b);
  --fw-line-strong: var(--ba);
}
```

Page-local component names should be purposeful rather than generic: `.golden-chapter`, `.architecture-figure`, `.lever-console`, `.formula-plate`, `.framework-workbench`, `.door-card`, `.policy-map`, and `.provider-card`. Replacing repeated inline declarations with these classes is the main maintainability improvement; existing shared classes should be preferred where their semantics already fit.

## 4. Architecture visual design

### Message

The figure’s title is **The information-acquisition machine**. Its visual thesis is:

> The ledger makes the unmeasured gap visible. Measurement turns events into information. Information is the prerequisite for policy. Policy becomes useful only when it is tested as an arm in a grid and revised through a campaign.

The diagram combines two related circuits without conflating them:

1. **Execution and learning loop:** `spec → DAG → cells → jobs → attempts → ledger → measure → information → compare → adapt → spec`.
2. **Load-bearing policy rail:** `instrument → derive → write policy → grid → campaign → adapt`.

The policy rail branches from `information`, passes through `policy`, `grid`, and `campaign`, then rejoins `adapt`. This makes the dependency explicit: policy cannot be drawn upstream of the information it requires.

### Golden-circle binding

| Ring | Visual territory | Architecture stages | Concept binding |
|---|---|---|---|
| WHY, center | Amber core | `ledger → measure → information`, summarized rather than duplicated as full nodes | The ledger exposes the unmeasured gap, and the belief is that visible events should become decision-grade information and then testable policy. |
| HOW, middle | Cyan instrument ring | `spec`, compile edge, `DAG`, `cells`, `jobs`, `attempts`, `ledger`, and `measure` | This is the `N linked sessions × M measurement angles` instrument. A bracket below the stages states `analysis burden = N × M before arm comparison`. |
| WHAT, outside | Sky policy/campaign ring | `policy`, `grid`, `campaign`, `compare`, and `adapt` | These are the repeatable decisions the machine enables. The outer ring turns a recommendation into a controlled arm and a campaign discipline. |

The rings are concentric dossier boundaries, not decorative circles. Their labels sit at the upper-left edge of each boundary, and each uses a different line style so the structure survives monochrome print: WHY solid, HOW double-line, WHAT dashed outer guide.

### Desktop composition

Use one responsive SVG with `viewBox="0 0 1440 900"` and `preserveAspectRatio="xMidYMid meet"`.

- Draw the WHAT boundary as a rounded rectangle at approximately `x=24, y=24, width=1392, height=852, rx=40` with a faint `var(--cy)` stroke.
- Draw the HOW boundary at approximately `x=168, y=118, width=1104, height=620, rx=34` with a faint `var(--ac)` double stroke.
- Draw the WHY core at approximately `x=500, y=330, width=440, height=210, rx=105` with a restrained amber radial fill and solid amber boundary.
- Place the forward execution nodes on the upper circuit from left to right: `ExperimentSpec`, `DAG`, `cells`, `jobs`, `attempts`, and `ledger`.
- Place `measure` at the lower-right turn, then `information`, `compare`, and `adapt` from right to left along the return circuit. The return arrow rises from `adapt` to `ExperimentSpec` and is labeled `tweak one variable`.
- Place `policy`, `grid`, and `campaign` on the outer lower rail. A branch from `information` crosses a diamond dependency gate before `policy`; `campaign` joins `adapt`.
- Keep the WHY core visually in the center of the circuit. Its primary line is `MEASURED INFORMATION`; its second line is `BECOMES TESTABLE POLICY`; its smallest line is `unmeasured gap → ledger visibility → decision`.
- Use compact edge labels above or below the path, never inside arrowheads. Labels are `compile`, `factor cross-product`, `enqueue`, `execute`, `emit events`, `measurement rules`, `arm loss`, and `adapt`.

### Node and edge semantics

| Node or edge | Label in the SVG | Meaning communicated by the visual |
|---|---|---|
| `spec` | `ExperimentSpec` / `question · workflow · factors · rules` | A reproducible question and design enter the machine. |
| compile edge | `compile` | Validation and dependency ordering turn intent into executable phases. |
| `DAG` | `DAG` / `validate → cells → execute → measure → compare → adapt` | The work is ordered, not an informal sequence of scripts. |
| `cells` | `CELLS` / `factor cross-product` | Every controlled trial gets one factor assignment; policy can be one factor level. |
| cells-to-jobs edge | `materialize` | A design cell becomes queueable work without changing its assignment. |
| `jobs` | `JOBS` / `budget · deadline · policy arm` | The scheduling and control envelope around an execution. |
| `attempts` | `ATTEMPTS` / `tokens · timing · tools · outcome` | One job can produce retry or escalation attempts, each retaining its own evidence. |
| attempts-to-ledger edge | `emit events` | Execution is recorded before interpretation. |
| `ledger` | `LEDGER` / `append-only events` | The visibility boundary: previously unmeasured behavior becomes inspectable evidence. |
| ledger-to-measure edge | `instrument` | Raw events are available to measurement rules; they are not yet policy. |
| `measure` | `MEASURE` / `measurement rules` | Declared transformations derive information from ledger fields. |
| measure-to-information edge | `derive` | Rules produce named information with explicit evidence class. |
| `information` | `INFORMATION` / `first-pass · grit · cost · uncertainty` | Decision inputs exist only after they are measured or derived. Labels are examples of information categories, not new page statistics. |
| dependency diamond | `requires ⊆ produced?` | The load-bearing gate: a control rule cannot consume unavailable information. |
| `policy` | `POLICY` / `route · retry · escalate · budget` | A control rule consumes information and decides an operational action. |
| routing annotation | `policy = factor level / arm` | Routing enters the experiment as a testable factor rather than an unquestioned default. |
| door split | `two-way: per-task route` / `one-way: default architecture` | Reversible model choice is distinguished from compounding provider and architecture commitment at the routing boundary. |
| `grid` | `GRID` / `policy as an arm` | Competing policies are evaluated under the same factor design. |
| `compare` | `COMPARE` / `cost · quality · latency · SLA · value` | Arm outcomes are compared on declared loss dimensions. |
| `campaign` | `CAMPAIGN` / `repeat the grid` | A sequence of grids creates a disciplined field, not a one-off benchmark. |
| `adapt` | `ADAPT` / `tweak one variable` | The next grid changes one coordinate based on information from the last comparison. |
| adapt-to-spec edge | `next specification` | Learning closes the loop by revising the design rather than silently changing production behavior. |

### N × M instrumentation annotation

A thin cyan brace spans `cells → jobs → attempts → ledger → measure` and is labeled:

`N linked sessions × M measurement angles = instrumented evidence surface`

A second, amber-tinted brace spans `measure → information → compare` and is labeled:

`analysis burden = N × M before cross-arm aggregation`

The two braces deliberately use symbolic `N × M`; they add no measured value. Their purpose is to show that more linked sessions and more measurement angles increase both evidence and analysis work.

### Load-bearing ordering rail

Place a straight five-stage rail beneath the circuit:

`INSTRUMENT → DERIVE → WRITE POLICY → GRID → CAMPAIGN`

Use short vertical leaders to connect the stages to `ledger/measure`, `information`, `policy`, `grid`, and `campaign`. Between `DERIVE` and `WRITE POLICY`, place the dependency diamond and the caption `information first`. This is the only gate rendered as a diamond; normal stages remain rounded rectangles so validation cannot be mistaken for work.

### SVG structure

The implementation should use this semantic group order. The comment labels are part of maintainability: they explain layer purpose without narrating obvious individual shapes.

```html
<figure class="architecture-figure" id="architecture">
  <svg class="architecture-map" viewBox="0 0 1440 900"
       role="img" aria-labelledby="architecture-title architecture-desc">
    <title id="architecture-title">The information-acquisition machine</title>
    <desc id="architecture-desc">An ExperimentSpec compiles into a DAG and factor cells...
      Events enter a ledger, measurement rules produce information, and policy arms are
      compared in grids and campaigns before one variable is adapted.</desc>

    <defs><!-- arrow markers, restrained glows, clip paths, and surface gradients --></defs>
    <g class="architecture-rings"><!-- WHAT, HOW, and WHY boundaries --></g>
    <g class="architecture-edges"><!-- execution loop paths and labels --></g>
    <g class="architecture-nodes"><!-- stage groups with title and detail text --></g>
    <g class="architecture-gates"><!-- requires/produces and routing door split --></g>
    <g class="architecture-burden"><!-- N × M braces and labels --></g>
    <g class="architecture-order"><!-- instrument-to-campaign dependency rail --></g>
    <g class="architecture-motion" aria-hidden="true"><!-- optional path tracers --></g>
  </svg>
  <figcaption>Events are not policy. Measurement creates the information that makes a
    policy arm writable, comparable, and adaptable.</figcaption>
</figure>
```

Each node is a `<g>` containing a `<rect>`, one title `<text>`, and one detail `<text>` or `<tspan>` group. Connections are `<path>` elements with marker-end references. Use classes rather than `fill` and `stroke` attributes wherever possible so light theme and print rules remain manageable.

### SVG colors and type

| Element | Fill | Stroke/text |
|---|---|---|
| Figure ground | `var(--bg2)` with a low-opacity grid pattern | `var(--b)` frame |
| WHY core | amber gradient from transparent to `color-mix`-equivalent static rgba | `var(--am)` boundary, `var(--t)` statement |
| HOW boundary and instrument nodes | `var(--bg3)` | `var(--ac)` keylines, `var(--t2)` details |
| WHAT boundary and policy nodes | `var(--bg3)` | `var(--cy)` keylines, `var(--t2)` details |
| Standard execution edges | none | `var(--t3)` at 1.5–2 px |
| Active dependency path | none | `var(--ac)` from ledger through information; `var(--cy)` from policy through campaign |
| Adapt edge | none | `var(--am)`, dashed until it reaches the next spec |
| Gate pass | `var(--bg4)` | `var(--success)` only for the small pass indicator |
| Labels | none | `var(--t3)` in JetBrains Mono |

All SVG labels use `'JetBrains Mono', monospace`. Stage titles are uppercase, 15–17 SVG pixels, weight 700, with modest letter spacing. Detail lines are 11–13 pixels and never rely on `foreignObject`, so the visual remains portable and printable.

The page requirement names amber/coral/cyan accents but the implemented design system exposes `--am`, `--ac`, and `--cy`; the figure uses those exact tokens rather than inventing a coral literal. This keeps the visual consistent with the actual shared palette.

### Motion, responsive behavior, and accessibility

- Animate only one or two small tracer dashes along the execution and feedback paths, with a duration of at least six seconds. Nodes do not float, pulse, or rearrange.
- Under `@media (prefers-reduced-motion: reduce)`, remove tracer animation and all SVG transitions. Arrowheads and edge labels retain the complete sequence without motion.
- At widths below 760 pixels, keep the figure inside an overflow container with `max-width: 100%`, `overflow-x: auto`, and a minimum SVG width near 900 pixels. This preserves readable formal labels without causing page-level horizontal overflow.
- Give the scroll container `tabindex="0"` and an accessible label such as `Scrollable architecture diagram`. The ordered text equivalent immediately after the figure prevents horizontal panning from being the only way to obtain the information.
- Ensure every text color meets contrast against its direct surface. Ring color is redundant with the visible `WHY`, `HOW`, and `WHAT` labels and distinct line styles.
- Print removes glow, animation, and grid texture; it uses black/gray boundaries plus solid/double/dashed ring styles. The SVG itself remains visible.

## 5. Number and binding preservation register

This register is intentionally exhaustive. During implementation, compare the old and new DOM/script values against it before visual review. Reordering a node is allowed; changing a literal, range, formula, binding key, fallback object, or generated-content target is not.

### Dynamic bindings and provenance

| Binding occurrence | Required fallback text | Constraint |
|---|---:|---|
| `data-stat-fmt="woc"` in Rule 5 | `0.90` | Preserve the attribute name, key, and fallback. |
| `data-stat-fmt="woc"` in the autonomous formula plate | `0.90` | Preserve the second independent occurrence. |
| `data-stat="woc_percent"` | `90%` | Preserve percent formatting in fallback text. |
| `data-stat="story_sessions"` | `1,097` | Preserve footer binding and localized fallback. |
| `data-stat="variants"` | `7` | Preserve footer binding. |
| `data-stat="stories_total"` | `221` | Preserve footer binding. |
| `data-stat="story_total_cost"` | `288.69` | Preserve the external `$` and bound numeric text. |

`framework.html` currently contains no literal bracket provenance tags. It uses the visible tiers `Observed`, `Derived`, `Modeled`, `Extension`, and the measured/modeling disclaimer. Preserve those words and all existing badges. Do not add `[M]`, `[C]`, `[H]`, `[X]`, or `[P]` to a claim unless the implementation separately verifies the corresponding `data.js` provenance; visual grouping alone is not evidence.

### Calculator arrays, scenarios, and formulas

Preserve the scenario arrays verbatim:

```js
const epmScenarios=[1.00,1.25,1.50],epmLabels=['Baseline (1.00&times;)','High (1.25&times;)','Extreme (1.50&times;)'];
```

Preserve the complete `model_costs` fallback verbatim:

```js
[{n:'DeepSeek v4 Pro',c:0.0158,p:0.84},{n:'GPT-5-nano',c:0.0057,p:0.89},{n:'GPT-5-mini',c:0.0258,p:0.94},{n:'GPT-5',c:0.159,p:0.7},{n:'GPT-5.5',c:0.282,p:1.0},{n:'GPT-5.6',c:0.4474,p:1.0},{n:'GPT-5.6-fast',c:0.6625,p:1.0},{n:'Claude Fable 5',c:1.0847,p:0.99}]
```

Preserve the complete `escalation_tiers` fallback and label array verbatim:

```js
[{m:'DS\u2192GPT-5-nano',e:0.4},{m:'DS\u2192GPT-5-mini',e:1.6},{m:'DS\u2192GPT-5',e:10.1},{m:'DS\u2192GPT-5.5',e:17.8},{m:'DS\u2192GPT-5.6',e:28.3},{m:'DS\u2192GPT-5.6-fast',e:41.9},{m:'DS\u2192Claude',e:68.7},{m:'\u2192Human ($5/job)',e:316.5}]
['DS\u2192GPT-5-nano (0.4\u00d7)','DS\u2192GPT-5-mini (1.6\u00d7)','DS\u2192GPT-5 (10.1\u00d7)','DS\u2192GPT-5.5 (17.8\u00d7)','DS\u2192GPT-5.6 (28.3\u00d7)','DS\u2192GPT-5.6-fast (41.9\u00d7)','DS\u2192Claude (68.7\u00d7)','\u2192Human ($5)']
```

Preserve these calculation constants and operations:

- Augmented: `N=S*D`, `B=0.001`, and `E*m.c*EPM*(N+B*V*N*(N-1)/2)`.
- Annual savings multiplier: `12`; engineer hours denominator: `D*8`; runway multiplier: `30`.
- Autonomous: `b=/100`, `rr=/100`, `ac0=/1000`, `er=/1000`.
- Autonomous EPM: `1.00+er*2`.
- Cost per job: `ac0*Ep*(1-b*0.5)*(1+rr*Em)`.
- Maximum jobs budget: `10000/Cjob`; monthly spend: `W*30*Cjob`; WOC: `1/(1+rr)`.
- WOC display thresholds: `0.85` and `0.70`.
- All `toFixed()` precisions, `Math.round()` calls, locale formatting, output labels, and the existing `howComputed` formula strings.

### Calculator control bounds and defaults

| Control | Minimum | Maximum | Default | Step or display |
|---|---:|---:|---:|---|
| Team size `r_eng` | `1` | `100` | `10` | `10 engineers` |
| Sessions/engineer/day `r_ses` | `1` | `100` | `20` | `20` |
| Velocity `r_vel` | `50` | `2000` | `500` | `500 lines/session` |
| Working days/month `r_day` | `15` | `25` | `20` | `20 days/month` |
| Energy scenario `r_epm` | `0` | `2` | `0` | `Baseline (1.00×)` |
| Engineer loaded cost `r_cost` | `5000` | `50000` | `20000` | `$20,000` |
| Augmented EPM annual rate `r_rate` | `5` | `30` | `16` | displays `1.6%` |
| Monthly AI budget `r_budget` | `500` | `500000` | `10000` | step `500`, displays `$10,000` |
| Workload `r_workload` | `100` | `100000` | `5000` | `5,000 jobs/day` |
| Batch fraction `r_batch` | `0` | `100` | `70` | `70%` |
| Retry rate `r_retry` | `0` | `100` | `11.5` | step `0.1`, displays `11.5%` |
| Escalation tier `r_escalation` | `1` | `4` | `2` | default HTML says `DeepSeek → GPT-5.6 (28.2×)` |
| Baseline cost/job `r_ac0` | `1` | `200` | `15` | displays `$0.015` |
| Autonomous EPM rate `r_arate` | `5` | `30` | `16` | displays `1.6%` |

### Visible narrative and formula values

Preserve every occurrence, including repeated values with different contexts:

- Opening and corpus: `$0.16`, `$0.34`, `~10`, `~120`, `227`, and `1,097`.
- Rules: `1` through `10`; `10 operators`; `11%`, `8%`, `8%`, `0.0%`; `$0.16 → $0.34`; `2.13×`; `N²`; `1.00`; `2024`; `1/(1+r)`; `0.115`; fallback `0.90`; `11.5%`; `0.85`; `0.70`; `50%`; `72-hour`; `<4 hours`; `1%`; `<1%`; `28.2×`; `GPT-5.6`; `2×`; and `10×`.
- Augmented levers: Rules `1–5`; `$0.005` to `$1.01`; `$3.75/Mtok`; `$0.14/Mtok`; `<50%`; `72%`; `8.4%`; `50%`; `GPT-5.5`; `0.3%`; `30%`; `N²`; `0.001`; `1.6%/yr`; and `2.5%/yr`.
- Autonomous levers: Rules `6–9`; `$0.001` to `$1.01`; `50%`; `1−b×0.5`; `11.5%`; `249 sessions`; `28.2×`; `GPT-5.6`; `68.7×`; and `<1%`.
- Workforce mapping: `L1 → L2 → L3`, `72-hour`, `1/(1+r)`, and `50%`.
- Formula constants: Rules `1–5`, `6–9`, and `10`; constants `1`, `0.5`, `0.115`, fallback `0.90`, and `28.2×`; preserve every `N−1`, `/2`, and exponent.
- Chart controls and notes: `3`, `10`, and `25` years; `1.6%/yr`; `3yr`; `10yr`; `2.5%`; `0.8%`; `2025`; `~667K`; `$10K`; `$0.015/job`; `90%`; and `1/(1+0.115)`.
- Doors and model handoff: `N²`; `36 months`; `<1%`; `30-day`; Weeks `1`, `2`, `3`, and `4`; `6–50%`; `7 models`; and `3 provider families`.
- Policy map: `10` rules and mappings `1+2`, `1+5`, `5+7`, `6+9`, and `8+10`.
- Per-token pricing: per `1M` tokens; DeepSeek `v4`, `$0.435`, `$0.0036`, `$0.87`; GPT-`5.6`, `$0.20`, `$0.02`, `$1.20`; Sonnet `5`, `$2.00`, `$0.20`, `$10.00`; and August `2026`.
- Cache strategy: Layers `1`, `2`, and `3`; `80–95%`; `50–90%`; `0.97`; `20–60%`; `$3.75/Mtok`; `$0.14/Mtok`; `50%`; and `80%`.
- Routing: `60–80%`; Tiers `1`, `2`, and `3`; `~60%`, `~25%`, and `~15%`; model tokens `V3`, `R1`, `GPT-4o`, and `GPT-5.6`.
- Budget commands: `1M`, `1h`, `gpt-5.6`, `128000`, `16384`, and `$5.00`.
- Provider cards: DeepSeek `$0.435`, `$0.0036`, `$0.87`, `78%`, `35K`, and `34`; Luna `$0.20`, `$1.20`, `$0.02`, `97.5%`, `6.3K`, `$0.09`, and `7`; Sonnet `5`, `$2.00`, `$10.00`, `$0.20`, `73%`, and `122`.
- Escalation economics: `221 stories`; `50×`; `17×`; `7`; `122`; `33×`; `$4.58`; `$0.14`; tiers `1`, `2`, and `3`; `~$0.09`, `~$0.14`, and `~$4.58`; and `7 → 122 tests/story`.
- Footer: `v0.9`; August `2026`; fallback `1,097`; `7`; `221`; and `$288.69`.

### Chart-only constants

The chart’s internal values are part of the preservation requirement even when they do not appear as prose. Preserve:

- Defaults `E=10`, `S=20`, `D=20`, `V=500`, `B=0.001`, `Ny=S*D*12`, and start year `2024`.
- Throughput labels `0.01`, `0.05`, `0.1`, `0.15`, `0.2`, `0.25`, and `0.3`.
- Throughput budget and base job cost `10000` and `0.015`.
- Retry series `5%` / `0.05`, `11.5%` / `0.115`, and `11.4%` / `0.114`.
- Escalation multiplier `28.2`.
- EPM paths `2.5%` / `0.025`, `1.6%` / `0.016`, and `0.8%` / `0.008`.
- Provider cost series `$0.015`, `$0.43`, and `$1.01`, plus all chart labels, colors, dash arrays, axis labels, tick formatting, and the initial `buildChart(3)` call.

### IDs and anchors

Preserve these authored section IDs: `why`, `rules`, `levers`, `cost-model`, `calculator`, `decisions`, `model-cards`, and `playbook`. Preserve rule IDs `rule-1` through `rule-10`.

Preserve chart IDs `costChart`, `yr3`, `yr10`, `yr25`, `epmBase`, `epmSens`, `vwCost`, and `vwThroughput`.

Preserve calculator IDs `btnAugmented`, `btnAutonomous`, `calcAugmented`, `calcAutonomous`, `v_eng`, `r_eng`, `v_ses`, `r_ses`, `v_vel`, `r_vel`, `v_day`, `r_day`, `v_epm`, `r_epm`, `v_cost`, `r_cost`, `v_rate`, `r_rate`, `v_budget`, `r_budget`, `v_workload`, `r_workload`, `v_batch`, `r_batch`, `v_retry`, `r_retry`, `v_escalation`, `r_escalation`, `v_ac0`, `r_ac0`, `v_arate`, `r_arate`, `roi_output`, `roi_context`, and `howComputed`.

Preserve all href destinations:

- Top navigation: `/`, `methodology.html`, `evidence.html`, `framework.html`, `story.html`, and `https://github.com/peparhugo/ai-finops-framework`.
- Audience note: `methodology.html`.
- Chart controls: preserve all seven existing `href="#"` destinations, IDs, and handlers. Accessibility enhancements must operate on those anchors in place; no fragment may be removed or repurposed.
- Model-profile CTA: `evidence.html`.
- Calculator CTA: `#calculator`.
- Footer: GitHub, `framework.html`, `story.html`, `methodology.html`, `evidence.html`, and `#playbook`.

Adding `id="architecture"` and a hero link to `#architecture` is allowed because it does not replace or reinterpret an existing fragment.

## 6. Implementation and verification sequence

1. Capture the current IDs, hrefs, bindings, calculator fallbacks, and numeric literals with an automated before snapshot. This makes the preservation requirement mechanically reviewable.
2. Reorder semantic sections into WHY, HOW, and WHAT while keeping every existing ID attached to its original content.
3. Replace repeated inline style declarations with page-local classes in the existing `<style>` block. Reuse shared dossier classes before adding a new component.
4. Add the accessible architecture `<figure>` and inline SVG. Verify its text equivalent before adding optional tracer motion.
5. Recompose the calculator without changing control IDs or generated output targets. If repairing the existing indexing and disclosure defects, keep the data arrays and formulas untouched and add focused browser-level assertions.
6. Recompose doors, rules, and playbook into their card grids. Check that no rule copy, command, pricing row, provider claim, or escalation value changed.
7. Add narrow-screen and reduced-motion rules locally. Verify at 375, 768, 1024, and 1440 CSS pixels in dark and light themes.
8. Compare before/after snapshots for numeric literals, `data-stat` attributes, IDs, hrefs, input bounds/defaults, and fallback object values. Any difference not explicitly allowed by this plan blocks the redesign.
9. Run `pytest tests/` and a manual smoke check with JavaScript enabled and with `data.js` unavailable so both live and fallback paths are exercised.

The face-lift is complete only when the page can be summarized from its visible sequence without reading every card: belief in the center, instrument and economics around it, and tested operating policy on the outside.
