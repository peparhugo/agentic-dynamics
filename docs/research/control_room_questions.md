---
status: accepted
---

# Control Room — research questions, facet matrix & operator needs (campaign phase r1)

**Date:** 2026-09-11
**Campaign:** `workflows/repository/control_room_research.yaml`, phase `r1_questions`.
**Inputs:** the mandate (`docs/designs/proposed/control_room_research_campaign.md:7-12`; pre-registration
`docs/experiments/preregistrations/control_room_research_preregistration.md`) and the measured
baseline `docs/research/control_room_audit.md` (phase r0).
**Outputs this document defines:** the research questions; the **facet matrix** (category ×
aesthetic × stack × techniques × quality signals) bound to the five corpus families; and the
**operator-needs list** (glance / drill-down / alert). Each is the contract the acquisition (r2a–r2e),
taxonomy (r3), reduction (r4), direction (r5) and brief (r7) phases execute against.

---

## 0. The mandate and how to read this

The mandate is explicit and deliberately does not describe the target
(`control_room_research_campaign.md:7-12`):

> "Do not hand-describe 'sleek and sexy'. The system research the open web at breadth (**200
> high-quality sources**), derive its own UI/UX knowledge, categorize/split/reduce it, and answer:
> *what would a sleek, sexy control room look like for operating multiple CLI AI coding-agent
> sessions — what does the operator need to know, what is present but in the wrong place, what is
> missing?*"

So this phase does **not** answer the design question. It converts the measured r0 baseline into
*researchable* questions (each answerable by documents on the open web), organises the corpus by
facet so r3 can cluster rather than flat-list, and pins the operator needs so r5/r6 can be graded
rather than argued. The three r0 outputs this document consumes are:

- the **panel/feed inventory** (r0 §2) and **cadence** (r0 §3) — what exists;
- the **mis-placed** list (r0 §5, M1–M14) and **absent** list (r0 §6, A1–A12) — the problem space;
- the **operator-question map** (r0 §4) and **guardrails** (r0 §9) — the constraint space.

Three terms are used precisely below:

- **Facet** — a named, enumerable property of a source (e.g. `aesthetic=dark-dense`,
  `stack=react`, `technique=small-multiples`). Facets are what r3 clusters on.
- **Corpus family** — one of the five acquisition channels with its own budget and seeds. A family
  is a *sampling frame*, not a facet value; the same facet may be evidenced by several families.
- **Operator need** — a question a human running many CLI agent sessions must be able to answer, at
  one of three depths. Needs are the acceptance target; facets are the vocabulary the direction is
  expressed in.

---

## 1. Method: the traceability chain

Every research question must survive a single chain, and every later artifact must carry its links.
This is the "derivation, not description" requirement made operational.

```
operator need (ON-*)                       §4   what must be answerable
   └─ research question (RQ-*)              §2   what we must learn from the web
        └─ facet (category/aesthetic/stack/ §3   how a source is described so it can cluster
           technique/quality-signal)
             └─ corpus family (F1–F5)       §3.3 which acquisition phase collects it
                  └─ evidence record (r2)   JSONL, one per source, with provenance
                       └─ taxonomy (r3)     clusters with split/merge + support
                            └─ skills/catalogs (r4)   decision-oriented, cited
                                 └─ direction (r5)     one cited answer
                                      └─ adversary passes (r6a–c)  entailment/design/IA
                                           └─ brief (r7)   acceptance criteria
```

**Rules carried from the campaign hard-rules** (`control_room_research.yaml:25-31`): every source
enters through `scripts/research_fetch.py` (provenance mandatory); single-source claims carry a
caveat and raised uncertainty; adversaries write only review docs; no live-KB writes in this
workflow; deliverables commit under `experiments/research/control_room/` and `docs/research/`.

**Reasoning for the chain shape.** The audit (r0) already names *problems* (M1–M14, A1–A12). If we
jumped from problem to design we would be hand-describing. Inserting RQs and facets forces each
design move to cite the sources that support it, which is what makes the three adversary passes
(r6a entailment, r6b design, r6c IA) mechanical rather than taste-based.

---

## 2. Research questions

RQs are grouped by the surface they govern so that r3 can cluster within a group and r4 can emit
one catalog per group. Each RQ row names the r0 driver (so the question is grounded in measured
code, not fashion), the corpus families most likely to answer it, and the later artifact it feeds.
`F1` agent-ops rooms · `F2` operational dashboards/design systems · `F3` charts/data-viz · `F4`
terminal/CLI · `F5` craft/reference.

### 2.1 Foundations and delivery model (RQ-A)

| ID | Research question | r0 driver | Families | Output |
|---|---|---|---|---|
| RQ-A1 | Which delivery model best fits a dark, data-dense, **local-only** operator console that is currently a no-build Flask companion — keep build-less vanilla, adopt a component framework, or use web components/SSR? What do comparable local/dev tools actually ship? | r0 §1 (34 routes, six classic scripts, `index.html:795-800`); guardrail "no build step" r0 §9.8 | F2, F1 | framework catalog |
| RQ-A2 | How do leading real-time operations rooms structure **update transport and reconciliation** (WS/SSE/poll, optimistic overlays, keyed re-render, write-on-change) so live data never flickers, steals focus, or double-counts? | r0 §1 two-layer reconciliation; r0 §9.1–9.3 | F1, F2 | IA/layout + framework catalog |
| RQ-A3 | What is the **smallest viable design-system layer** (design tokens + primitives) that yields visual consistency for a single-page console without adopting a framework's whole runtime? | r0 §8 dated elements; r0 M6/M14 | F2, F5 | framework + color/motion catalog |
| RQ-A4 | How do comparable tools **fail-safe**: what happens to the UI when the datastore, a provider, or a projector is down, and how is that state shown without collapsing the whole page? | r0 §5 M2 (projection health unrendered), A1; r0 §2.5 | F1, F2, F5 | IA/layout + chart catalog |

### 2.2 Information architecture and layout (RQ-B)

| ID | Research question | r0 driver | Families | Output |
|---|---|---|---|---|
| RQ-B1 | What must be **above the fold** for an operator watching many concurrent CLI agent sessions — the first-screen hierarchy. | r0 §4 glance list; M5 (docs health pushes fleet below fold) | F1, F2, F4 | IA/layout catalog |
| RQ-B2 | Which **navigation model** fits 5–7 primary surfaces across desktop and phone: persistent left rail, bottom tab bar, command palette, or a hybrid? What do the best ops products choose and why? | r0 §2.2 (five boards + System overflow); r0 §9.7 | F2, F4 | IA/layout catalog |
| RQ-B3 | What is the right **transversal detail pattern** — docked column, modal sheet, side peek, or routed page — for a node selected from a live grid, and how is it dismissed/restored across breakpoints? | r0 §2.3 (`detail-sheet.js` modal/dock split) | F2, F5 | IA/layout catalog |
| RQ-B4 | How should **money surfaces** (spend, burn, provider quota, wallet, reserved leases, budgets) be grouped relative to **work surfaces** (runs, queues, workers, cells)? Should quota/leases live on the money board by construction? | r0 §5 M1 (quota/leases buried in System) | F1, F2 | IA/layout catalog |
| RQ-B5 | How do the best rooms handle **overflow/secondary surfaces** (registry, canonical state, config) without burying them — drawer vs destination vs command palette entry? | r0 §5 M4 (registry-as-drawer); A3 | F2 | IA/layout catalog |

### 2.3 Data visualization (RQ-C)

| ID | Research question | r0 driver | Families | Output |
|---|---|---|---|---|
| RQ-C1 | Which **chart forms** are appropriate for each operator question — cost/burn over time, status distribution, queue depth, latency, phase progress — at fleet scale? | r0 §3 windows; r0 §6 A5 (no trends) | F3, F2 | chart selection catalog |
| RQ-C2 | Which **charting library/approach** (D3, ECharts, Vega-Lite, uPlot, visx, Nivo, Tremor, shadcn charts, hand-rolled SVG) best fits a dark theme, small multiples, sparklines, and dense tables with an accessible, lightweight runtime? | r0 §1 no-build; M6 hand-rolled sparkline | F3, F2 | framework + chart catalog |
| RQ-C3 | Which **glance-oriented techniques** (sparkline, bullet, small multiples, heatmap/status grid, threshold bands) communicate state rather than analytics, and when is a number better than a mark? | r0 §4 glance; M6 (marks that cannot compare) | F3, F2 | chart selection catalog |
| RQ-C4 | How should charts represent **partial / retained / uncertain data** (a 500-event retained window, missing provider fields) so a viewer is never misled? | r0 §2.2 provenance ("RETAINED WINDOW"); `services/telemetry.py:198-210` `partial: True` | F3, F5 | chart selection catalog |
| RQ-C5 | What is the **performance budget** for many live marks (hundreds of cards/charts) — canvas vs SVG, virtualization, sampling, and render cadence? | r0 §3 (5 s polls, 60 samples/cell); r0 §9.3 | F3, F2 | chart catalog |

### 2.4 Aesthetic system — color, type, motion, depth (RQ-D)

| ID | Research question | r0 driver | Families | Output |
|---|---|---|---|---|
| RQ-D1 | What concrete visual system defines **"sleek/sexy"** for a dark, data-dense ops room: surface elevation model, contrast strategy, accent economy, radius/shadow rhythm? | r0 §5 M6/M14; r0 §8 (dated elements) | F2, F5, F3 | color/motion catalog |
| RQ-D2 | What is a defensible **motion budget** (durations, easing, which elements animate, reduced-motion behavior) for a room that must stay calm under continuous load? | r0 §9.7 reduced motion; `style.css:2155-…` | F5, F2 | color/motion catalog |
| RQ-D3 | Which **status-encoding systems** keep lifecycle, attention, and severity legible and colorblind-safe while colour is never the only signal? How many hues before it becomes noise? | r0 §9.5 two-axis language | F5, F1, F3 | color/motion catalog |
| RQ-D4 | What **typography and iconography** choices distinguish a premium operations product from an admin console (display scale, mono usage, icon family, uppercase restraint)? | r0 M6/M14 + prior audit's dated-element list (`control_room_refresh_audit.md:220-258`) | F5, F2 | color/motion catalog |
| RQ-D5 | How do the best systems theme **dark-first with a real light theme** from one token set, including forced-colors/high-contrast? | r0 §2.1 theme toggle; `style.css:2867` forced-colors | F5, F2 | color/motion catalog |

### 2.5 Density and large data surfaces (RQ-E)

| ID | Research question | r0 driver | Families | Output |
|---|---|---|---|---|
| RQ-E1 | How do the best products present **large, live, sortable tables** (registry, events, cells) with keyboard access, stable row identity, and no focus loss under update? | r0 §5 M10 (pseudo-button rows); §9.3 keyed lists | F2, F3 | IA/layout catalog |
| RQ-E2 | What **density ladders** (comfortable/compact/executive) are standard, how is density switched, and how is the choice persisted without losing selection? | r0 §2.2 density toggle (`shell.js:82-92`) | F2, F5 | IA/layout catalog |
| RQ-E3 | How should per-node telemetry (cost/tokens/phase) be surfaced **without a per-card microchart**, preserving comparability and scan speed? | r0 M6 (sparkline noise) | F3, F2 | chart selection catalog |
| RQ-E4 | How are **command palettes / keyboard-first** interactions used in ops tools, and where do they beat visual navigation? | r0 §2.2 five boards; prior audit keyboards | F4, F2 | framework + IA catalog |

### 2.6 Alerting and attention (RQ-F)

| ID | Research question | r0 driver | Families | Output |
|---|---|---|---|---|
| RQ-F1 | How do operations tools **rank and present attention** (severity, recency, ownership, confidence) so a human triages fast without alarm fatigue? | r0 §2.2 Flags board; §4 alert gaps | F1, F2 | IA/layout catalog |
| RQ-F2 | What is the right **push-vs-pull alerting model** for a local, single-operator tool — browser notifications, sound, badge only, or none? What do agent-ops rooms do? | r0 §4 ("no push signals but connection and flag count"); A9 | F1, F2 | IA/layout catalog |
| RQ-F3 | How should **"healthy but stale/degraded"** and **"unmeasured ≠ clean"** be presented so green never lies — freshness displays, staleness thresholds, source provenance? | r0 M2, M3; `services/docs_health.py:26-30`; `services/supervisor.py:147-161` | F5, F1 | IA/layout + color catalog |
| RQ-F4 | How are **single "is anything wrong?" summaries** built (health score, degraded banner, alert digest) without collapsing distinct failure modes into one number? | r0 §6 A1 (no health aggregate) | F1, F2, F5 | IA/layout catalog |

### 2.7 Terminal / CLI aesthetics (RQ-G)

| ID | Research question | r0 driver | Families | Output |
|---|---|---|---|---|
| RQ-G1 | Which **terminal/TUI conventions transfer to a GUI console** — monospace density, log streaming, inline status, keybindings, command palette — and which do not? | r0 §1 CLI-agent subject; §2.3 transcript | F4, F3 | IA/layout + color catalog |
| RQ-G2 | How do best-in-class terminal apps render **live, unbounded log streams** with follow/pause/search/filter and bounded memory? | r0 §2.3 transcript (rebuilds 500 rows/event; `app.js:1522-1675`) | F4, F5 | IA/layout catalog |
| RQ-G3 | What visual language makes a **multi-session agent fleet** feel native to developers (session cards, process states, attach/detach affordances)? | r0 §2.2 Sessions; §2.3 detail | F4, F1 | IA/layout + chart catalog |

### 2.8 Accessibility and craft reference (RQ-H)

| ID | Research question | r0 driver | Families | Output |
|---|---|---|---|---|
| RQ-H1 | What is the **accessibility bar** (WCAG 2.2 AA specifics) for a dark, data-dense, live-updating console — contrast in dark themes, focus visibility/order, table semantics, chart alternatives, motion? | r0 M9/M10; §9.7 | F5, F3 | IA/layout + chart catalog |
| RQ-H2 | How are **live regions** used so AT users learn of important changes without an announcement flood under a 1–5 s update cadence? | r0 §3 (1 s tick, 5 s polls); `app.js:130-136` | F5, F2 | IA/layout catalog |
| RQ-H3 | What are the **responsive/breakpoint** patterns that keep wide telemetry usable on a phone without merely stacking? | r0 §2.2–2.4; `style.css:1958-2134` | F5, F2 | IA/layout catalog |

### 2.9 Money, quota and cost surfaces (RQ-I)

| ID | Research question | r0 driver | Families | Output |
|---|---|---|---|---|
| RQ-I1 | How do AI/agent platforms visualize **spend, quota, budget, and rate limits** (windows, resets, burn, forecast) at a glance? | r0 §5 M1; §6 A5 | F1, F2, F3 | chart + IA catalog |
| RQ-I2 | How is **"reserved but unspent" / headroom** shown beside **consumed** usage so the two are readable together? | r0 M1 (`routes/telemetry.py:303-356` co-locates them) | F1, F2 | chart + IA catalog |
| RQ-I3 | How are **cost attribution and per-model/per-task comparison** presented (what did this cost, by what) without inventing signals the data does not have? | r0 §6 A6 | F1, F2, F3 | chart catalog |

### 2.10 SVG and diagram craft (RQ-J)

| ID | Research question | r0 driver | Families | Output |
|---|---|---|---|---|
| RQ-J1 | How to build **responsive, theme-aware, accessible SVG diagrams** for architecture/topology (queues → workers → cells → sessions → projections) that survive print and forced-colors? | r0 §6 A7; `architecture.svg` orphaned r0 §2.6 | F5, F3 | SVG technique catalog |
| RQ-J2 | What SVG/CSS techniques produce **premium micro-visuals** (sparklines, gauges, flow lines, status glyphs) with small payloads and no JS chart runtime? | r0 M6; `app.js:283-340` hand-rolled SVG | F5, F3 | SVG technique catalog |
| RQ-J3 | How are SVG diagrams made accessible (title/desc, text equivalents, focusable overflow) and reduced-motion safe? | r0 §2.6; `architecture_visual.md:64-76` | F5 | SVG technique catalog |

---

## 3. The facet matrix

### 3.1 Dimensions and value vocabularies

These are the enumerable values r2 records and r3 clusters on. Values are open where noted (`†`)
— an acquisition agent may add a value, but must record the addition in the family's stop-reason
note so r3 can see the vocabulary drift. Each source gets exactly one primary value per dimension
and zero or more technique values.

**Dimension 1 — category** (what the artifact *is*, and therefore where its authority lies)

| Value | Meaning |
|---|---|
| `agent-ops-room` | An LLM/agent observability product or its docs (traces, evals, prompts, costs) |
| `ops-dashboard` | A product's operational UI (deploys, incidents, queues, infra) |
| `design-system` | A published token/component system or its docs |
| `chart-library` | A charting/visualization library, gallery, or grammar |
| `terminal-app` | A terminal/TUI product or its craft writing |
| `design-craft` | A craft/reference article (IA, a11y, SVG, type, motion) |
| `case-study` | A product/engineering narrative that demonstrates a shipped decision |
| `reference-standard` | A standards body or platform guideline (MDN, W3C, vendor HIG) |
| `component-kit` | A copyable component collection (shadcn-style, templates) |

**Dimension 2 — aesthetic**

| Value | Meaning |
|---|---|
| `dark-dense` | Dark, information-dense, low-chrome |
| `light-minimal` | Light, generous whitespace, restrained |
| `hybrid-theme` | A real dark+light token system |
| `high-contrast-mono` | Near-monochrome, maximum legibility |
| `terminal-native` | TUI/console visual language |
| `brand-gradient` | Brand/marketing-forward surfaces |
| `editorial` | Type-led, publication-like |
| `material-apple` | Platform-HIG systems (Material 3 / Apple HIG) |
| `precision-instrument` | Industrial/measurement-instrument feel (r0's target category) |

**Dimension 3 — stack** (what it is built with; `none` = conceptual article with no implementation)

| Value | Meaning |
|---|---|
| `react` / `vue` / `svelte` / `solid` | Component frameworks |
| `vanilla-js` | No framework |
| `web-components` | Custom elements / shadow DOM |
| `d3` | D3 primitives |
| `chart-lib` | ECharts/Vega-Lite/uPlot/visx/Nivo/Tremor/shadcn charts |
| `canvas-webgl` | Canvas/WebGL rendering |
| `svg-css-only` | SVG + CSS, no JS chart runtime |
| `tui-rust` / `tui-go` / `tui-python` | Terminal stacks (Ratatui, Bubbletea, Textual, …) |
| `no-build-static` | Plain files served directly |
| `none` | Article/reference only |

**Dimension 4 — techniques** (the mineable specifics; many per source)

| Group | Values |
|---|---|
| IA / layout | `left-rail`, `tab-bar`, `command-palette`, `overflow-drawer`, `docked-detail`, `modal-sheet`, `progressive-disclosure`, `density-ladder`, `master-detail`, `board-per-domain` |
| Data / viz | `sparkline`, `small-multiples`, `bullet-chart`, `heatmap-status-grid`, `threshold-bands`, `gauge`, `timeline-gantt`, `virtualized-table`, `log-stream`, `provenance-annotation`, `uncertainty-encoding`, `sampling-decimation` |
| Interaction | `keyboard-first`, `focus-management`, `optimistic-update`, `live-follow`, `pause-resume`, `sort-filter`, `skeleton-loading`, `empty-error-states`, `confirmation-door`, `undo`, `reduced-motion` |
| Visual | `design-tokens`, `elevation-model`, `accent-economy`, `type-scale`, `icon-family`, `motion-easing`, `colorblind-safe-status`, `dark-first-theming`, `forced-colors` |
| Trust / ops | `freshness-indicator`, `staleness-threshold`, `source-provenance`, `degraded-banner`, `audit-trail`, `idempotency-surfacing`, `causal-lineage` |
| SVG / diagram | `theme-aware-svg`, `accessible-svg`, `print-safe-svg`, `micro-visual`, `path-tracer`, `flow-diagram` |

**Dimension 5 — quality signals** (recorded per source; used by r6a and by r3 support counts)

| Signal | Values / rule |
|---|---|
| `authority` | `vendor-primary` (the product's own docs) · `vendor-blog` · `standards-body` · `independent-analysis` · `practitioner` |
| `recency` | `current` (≤ 18 months at fetch) · `recent` (≤ 3 y) · `dated` (> 3 y, kept only if canonical) |
| `demonstrates` | `true` when the source **shows** a shipped technique (screenshots/code/demo), not merely describes it — the campaign's explicit quality gate (`control_room_research_campaign.md:27-30`) |
| `accessibility_evidence` | `audited` · `claimed` · `none` |
| `performance_evidence` | `measured` · `claimed` · `none` |
| `open_implementation` | `true` when code is inspectable (repo/CodePen/demo) |
| `single_source_risk` | `high` when no independent corroboration is known at record time; forces a caveat in r4/r5 |

**Reasoning for these five dimensions.** The mandate names exactly them
(`control_room_research_campaign.md:35-40`, `research.md` §facet): category makes a source
findable, aesthetic and stack make it comparable ("would this even apply to us?"), techniques are
the unit r4 turns into a decision skill, and quality signals are the only defence against open-web
noise. Putting `demonstrates` in the *quality* dimension (not the technique dimension) is deliberate:
a technique that is only described is weaker support, and r3 must be able to age it out.

### 3.2 Per-source facet record (the JSONL schema)

Every `experiments/research/control_room/corpus/<family>.jsonl` line is one record. This mirrors the
phase prompts' required fields (`control_room_research.yaml:66-71`) and the fetch tool's own
provenance record.

```json
{
  "family": "dataviz",                       // F3 — the sampling frame
  "uri": "https://…",                        // as requested
  "final_uri": "https://…",                  // after redirects
  "sha256": "…",                             // content hash (dedup key)
  "fetched_at": "2026-09-11T…Z",
  "title": "…",
  "category": "chart-library",               // dimension 1
  "aesthetic": "dark-dense",                 // dimension 2
  "stack": ["chart-lib", "react"],           // dimension 3 (list allowed)
  "techniques": ["small-multiples", "threshold-bands", "provenance-annotation"],
  "quality": {
    "authority": "vendor-primary",
    "recency": "current",
    "demonstrates": true,
    "accessibility_evidence": "claimed",
    "performance_evidence": "none",
    "open_implementation": true,
    "single_source_risk": "low"
  },
  "notes": "…"                               // one line: what this source actually evidences
}
```

**Reasoning.** The record is flat enough to append without a schema migration, carries the fetch
tool's provenance verbatim (so r6a can re-read the stored text), and separates `stack`/`techniques`
(as lists) from the single-valued facets so clustering is unambiguous. `notes` exists so a later
reader does not have to re-fetch to learn why the source was kept.

### 3.3 Family × facet matrix (what each acquisition phase is the authority for)

Read this as: "when r3 needs evidence for facet X, which family is expected to supply it, and what
does that family prove *uniquely*?" A family is not limited to its primary rows — it may supply
cross-cutting evidence — but the primary rows are its obligation.

| Family (budget) | Seeds | Primary facet authority | Techniques it uniquely proves | Quality-signal bar |
|---|---|---|---|---|
| **F1 agent-ops rooms** (≈40) | LangSmith, Langfuse, Braintrust, Helicone, AgentOps, W&B Weave, Arize Phoenix | `category=agent-ops-room`; `technique=provenance-annotation`, `causal-lineage`, `uncertainty-encoding`; cost/eval surfaces | How traces/evals/cost are shown for *agents specifically*; prompt/run drill-down; quota for LLM APIs | `demonstrates=true` preferred; vendor-primary counts; one independent review per major product |
| **F2 operational dashboards & design systems** (≈50) | Linear, Vercel, Grafana, Datadog, Sentry, PostHog, Railway, Fly.io, Modal, Supabase, Stripe | `category=ops-dashboard` / `design-system`; IA (`left-rail`, `command-palette`, `docked-detail`, `density-ladder`), interaction, theming | Real shipped multi-surface ops IA; dark/light token systems; large live tables; incident/attention patterns | Mix vendor-primary + case-study; reject pure marketing; ≥3 independent per technique |
| **F3 charts & data-viz** (≈40) | Observable/D3, ECharts examples, Vega-Lite, visx, Nivo, uPlot, Tremor, shadcn charts | `category=chart-library`; chart-form selection, `small-multiples`, `threshold-bands`, `sparkline`, `uncertainty-encoding`, `sampling-decimation` | Which mark for which question; dark-theme chart defaults; a11y chart alternatives; performance at scale | `open_implementation=true` strongly preferred; gallery/example sources must show runnable code |
| **F4 terminal / CLI** (≈30) | Warp, Wave, Ghostty, Charm (bubbletea/gum), Textual, nvitop, asciinema | `category=terminal-app`; `stack=tui-*`; `log-stream`, `live-follow`, `keyboard-first`, `high-contrast-mono` | Multi-session/process fleets; unbounded log streaming; keyboard-first density; terminal-native status | `demonstrates=true` (recordings/docs of the real app); authority `vendor-primary` or `practitioner` |
| **F5 craft / reference** (≈40) | MDN (SVG/CSS/a11y), web.dev, NN/g, Refactoring UI, Material/Apple HIG (density), Smashing, css-tricks SVG archive, SVG-Tutorial | `category=design-craft` / `reference-standard`; accessibility, type, motion, SVG technique, `forced-colors` | The normative bar (WCAG 2.2, HIG density), SVG craft, motion budgets, typography systems | `standards-body`/`reference-standard` authority; recency `current` unless canonical; `accessibility_evidence=audited` where available |

**Total budget: 40 + 50 + 40 + 30 + 40 = 200 sources ±20% per family**
(`control_room_research_preregistration.md:13-16`). F2 is the largest because it is the only family
that supplies IA *and* design-system evidence; F4 is the smallest because multi-session agent
fleet patterns are a narrow target.

**Cross-family coverage rule.** Every technique in §3.1 dimension 4 must be evidenced by **≥3
independent sources** before it may appear in r4 (`control_room_research_campaign.md:78-81`). A
technique evidenced by only one family triggers an explicit "searched Fx, found none" note in r3 so
the gap is visible rather than silently under-supported.

### 3.4 Budgets, stop reasons and the acquisition contract

Each r2 phase (r2a–r2e) stops when its family budget is met (±20%) **or sources run dry**, and must
record the stop reason (`control_room_research.yaml:71`). The stop reason is data for r3/r7: a
family stopped "budget met" is a healthy sample; one stopped "sources run dry" is a coverage hole.

Per-phase extraction obligation (so r3 receives comparable records):
1. fetch through `scripts/research_fetch.py` only, batch URLs, dedup by content hash;
2. write the §3.2 record per stored source, appending to the family's JSONL;
3. record the stop reason and the final family count;
4. commit.

### 3.5 Quality signals and evidence rules

- **Demonstrates over describes.** A source that only asserts ("dark mode is best") is `dated`/low
  support unless it is a standards body.
- **Single-source caveat.** Any claim in r4/r5 resting on one source gets a caveat and raised
  uncertainty (`control_room_research_preregistration.md:26-30`).
- **Conflicts are recorded, not averaged** (`control_room_research_campaign.md:78-81`): if two
  credible sources disagree (e.g. rail vs palette), r3/r4 must record both with support.
- **Recency.** `dated` sources are allowed only when canonical (e.g. a classic NN/g or MDN page).

---

## 4. Operator-needs list

Derived from r0 §4 and the audit's M/A findings, restated as testable needs at the three depths the
campaign names. Status column = measured r0 state. Each need is a target for r5/r6c.

### 4.1 At a glance (no interaction; the resting screen)

| ID | The operator must be able to see… | r0 status | r0 evidence / gap |
|---|---|---|---|
| ON-G1 | Is the whole system up and is this room connected? | partial | rail badge + Redis mirror (`app.js:215-248`); no single health summary (A1) |
| ON-G2 | What is running / queued / failed **right now**, and what is live? | satisfied | Fleet grid + counts + Live now (`app.js:602-676`, `:582-600`) |
| ON-G3 | Is anything failing, stalled, or at risk? | partial | Flags board + risk filter (`board-fleet.js:71`); failures are only a count/tile, not surfaced as an event |
| ON-G4 | What is money doing — spend, burn, provider quota, wallet, **reserved leases**? | partial | Spend/burn on Status (`app.js:223-288`); quota/wallet/leases buried in System (M1) |
| ON-G5 | Does anything need a decision **from me** (approvals, proposals, promotion)? | partial | Docs-health proposal (`app.js:803-857`); no approvals/promotable board (M3/A3) |
| ON-G6 | Is what I'm looking at **fresh and trustworthy** (projections, degraded, stale)? | absent | projection health measured but unrendered (M2); supervisor source shown, projections not |
| ON-G7 | What is the shape of the fleet (by model / condition / provider)? | absent | no fleet rollup in the room; only per-cell cards and the region-wide count footer |

### 4.2 On drill-down (one selection away)

| ID | The operator must be able to answer… | r0 status | r0 evidence / gap |
|---|---|---|---|
| ON-D1 | For one cell/session: what is it doing, step by step, live? | satisfied | transcript + SSE (`app.js:1522-1675`, `:1747-1794`) |
| ON-D2 | Why is this flagged, and what is the safe action (steer/interrupt)? | satisfied | supervisor detail panel + typed door (`index.html:223-263`) |
| ON-D3 | What is this design's draft/validation state, and can I save/run it? | satisfied | design detail panel (`app.js:1256-1297`) |
| ON-D4 | What canonical record explains this — why did the system act? | partial | registry lineage (`app.js:2479-2500`) but buried in System (M4) |
| ON-D5 | Which model/route should this task use, and at what cost/quality? | partial | Routing board exists but lazy/hidden and starts collapsed (`app.js:2216-2263`) |
| ON-D6 | What did this cost, by step / model / cell? | partial | per-step cost in transcript + per-cell latest cost; no attribution rollup (A6) |
| ON-D7 | Manage one background `claude` session (stop/respawn/rm/steer). | satisfied | Claude detail panel (`index.html:318-347`) |

### 4.3 On alert (must interrupt or be impossible to miss)

| ID | The operator must be told… | r0 status | r0 evidence / gap |
|---|---|---|---|
| ON-A1 | A run failed or timed out just now. | partial | status transitions announced (`app.js:2147`); no failure event/alert log |
| ON-A2 | A worker or a knowledge projection is unhealthy or stale. | absent | `projection_lag`/`unhealthy_workers` not in the room (M2/A4) |
| ON-A3 | A spend or quota threshold is crossed. | absent | no threshold/alert concept in the room (A5) |
| ON-A4 | A controller decision is pending (approval / promotion). | partial | docs proposal is visible & alertable; approvals/promotable are not (M3/A3) |
| ON-A5 | A supervisor flag was raised or changed. | satisfied | badge + announcement + board (`app.js:2086-2089`) |
| ON-A6 | This room's own data went stale/disconnected. | partial | connection badge + matrix age + per-board degraded copy; not systematic (A10) |

**Reasoning for splitting needs three ways.** r0 showed the room is strong at drill-down
(ON-D1/2/3/7 satisfied) and reasonable at *work* glance (ON-G2), but weak at *money/health/decision*
glance and almost empty at alert (ON-A2/A3 absent). If the direction optimizes only the glance
screen it will not fix the alert depth; if it optimizes only alert it may bury drill-down. Naming
all three makes r6c (IA adversary) able to attack the ranking directly, which is its charge
(`control_room_research.yaml:186-191`).

---

## 5. What "sleek and sexy" must mean here (anti-subjectivity criteria)

The mandate forbids hand-description, so the direction phase needs operational criteria for the
adjectives. Derived from the operator needs, a design counts as **sleek** for this product when:

1. **Operator-first ranking** — the first screen answers ON-G1…G6 in that order; nothing decorative
   precedes a decision-relevant signal (`candidate failure: r0 M5/M7`).
2. **Calm under load** — under a 1 s tick / 5 s poll with dozens of live nodes, no flicker, no
   focus loss, no announcement flood (r0 §9.1–9.3; ON-H2).
3. **Truthful state** — partial, stale, degraded, and unmeasured are visually distinct and green
   never lies (ON-G6/ON-A6; r0 M2/M3).
4. **Evidence at hand** — every consequential surface (registry, docs proposal, quota) is one step
   from the place the decision is made (ON-G5/ON-D4; r0 M1/M4).
5. **Restrained craft** — a coherent token-based visual system (elevation, accent economy, type
   scale, motion budget) rather than accumulating chrome (r0 M6/M14; §8 dated elements).
6. **Accessible by default** — keyboard, screen reader, colorblind, reduced-motion, forced-colors
   (ON-A6; r0 M9/M10).

These six become the rubric r6b (design critique) and r7 (brief acceptance) grade against.

---

## 6. Traceability matrix (needs → RQ → facets → family)

Compact map so r3/r4/r5 can walk backwards from a design claim to its sources.

| Need(s) | Research questions | Facet dimensions most used | Families | Later artifact |
|---|---|---|---|---|
| ON-G1, ON-A6 | RQ-A4, RQ-F3, RQ-F4 | trust/ops techniques, quality signals | F1, F2, F5 | IA catalog, direction §health |
| ON-G2, ON-G3, ON-A1 | RQ-B1, RQ-C1, RQ-C5, RQ-F1 | IA, data/viz, interaction | F2, F3, F4 | IA + chart catalogs |
| ON-G4, ON-D6, ON-A3 | RQ-B4, RQ-I1–I3, RQ-C1, RQ-C4 | data/viz, IA, provenance | F1, F2, F3 | chart + IA catalogs |
| ON-G5, ON-A4 | RQ-B5, RQ-F1, RQ-F4 | IA, trust/ops | F2, F1 | IA catalog |
| ON-G6, ON-A2 | RQ-A4, RQ-F3, RQ-I2 | trust/ops, color | F5, F1, F2 | IA + color catalogs |
| ON-G7 | RQ-C3, RQ-E3, RQ-I3 | data/viz, visual | F3, F2 | chart catalog |
| ON-D1, RQ-G2 | RQ-G1, RQ-G2, RQ-E1 | interaction, data/viz | F4, F5 | IA catalog |
| ON-D2, ON-D3, ON-D7 | RQ-B3, RQ-G3 | IA, interaction | F4, F2 | IA catalog |
| ON-D4 | RQ-B5, RQ-F3 | IA, trust/ops | F2, F5 | IA catalog |
| ON-D5 | RQ-C3, RQ-B1 | data/viz, IA | F1, F2, F3 | chart + IA catalogs |
| ON-A5 | RQ-F1, RQ-F4 | IA, color | F1, F2 | IA + color catalogs |
| all | RQ-A1–A3, RQ-D1–D5, RQ-H1–H3, RQ-J1–J3 | stack, aesthetic, SVG | F2, F5, F3 | framework + color + SVG catalogs |

---

## 7. Handoff to the acquisition phases (r2a–r2e)

- **r2a–r2e** execute §3.3: one family each, §3.4 budget and stop reason, §3.2 records to
  `experiments/research/control_room/corpus/<family>.jsonl`.
- **r3** clusters by the §3.1 vocabulary, splits heterogeneous clusters and merges thin ones, and
  reports support per node using the §3.5 rules.
- **r4** emits one catalog per §2 group (frameworks, IA/layout, chart selection, color/motion, SVG
  technique) plus decision skills, each item citing its records.
- **r5** answers the mandate with the §4 needs and §5 criteria, addressing every M/A disposition
  from r0.
- **r6a/b/c** attack entailment, design genericness, and IA ranking respectively.
- **r7** tightens the direction into the facelift brief using §5 and the r0 §9 guardrails.

---

## 8. Reproduce

- Questions/facets/needs are derived from `docs/research/control_room_audit.md` sections cited
  inline; no external source was fetched in this phase (acquisition begins at r2a).
- Family budgets and stop contract: `workflows/repository/control_room_research.yaml:58-113`;
  pre-registration `docs/experiments/preregistrations/control_room_research_preregistration.md:13-16`.
- Doc lifecycle: this file carries `status: accepted`
  (`tests/test_doc_lifecycle.py:66-120`).

*End of phase r1. The facet vocabulary and the operator-needs list are the contract for the
acquisition, reduction, and adversary phases.*
