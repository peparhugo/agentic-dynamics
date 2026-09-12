---
status: accepted
---

# Control Room — reduced knowledge: catalogs & decision skills (campaign r4)

**Date:** 2026-09-11  
**Campaign:** `workflows/repository/control_room_research.yaml`, phase `r4_reduce`.  
**Inputs:** `experiments/research/control_room/taxonomy.json` + the five corpora.
**Outputs:** `experiments/research/control_room/catalogs.json`, `experiments/research/control_room/skills.json`, and this document.

Every item cites its example refs and support in the JSON; a leaf below the ≥3-source bar is **dropped**, not emitted; single-family clusters carry the single-source caveat. This is a reduction of the records, not new research.

## 1. Skills (decision-oriented)

### `skill-delivery` — What delivery model should the Control Room use?

Stay build-less: vanilla JS + CSS custom properties + CSS/SVG micro-visuals. Adopt a chart library only for the time-series/table marks that justify it (uPlot or ECharts for streaming breadth), and prefer D3 only for one or two bespoke marks.

**Avoid:** A React SPA/build pipeline for a single-page local console (no corpus evidence it is needed; conflicts with the no-build guardrail).; Mixing three chart grammars on one page.; Per-card JS chart runtimes for tiny repeated marks.

- **Evidence:** max cluster support 39; families cli, craft, dashboards, dataviz; confidence **high** (see `skills.json` for per-node support).
- **Catalogs:** `fw-no-build`, `fw-canvas-stream`, `fw-d3`, `fw-react-kits`.
- **Needs answered:** RQ-A1, RQ-A3, RQ-C2.
- **Caveat:** The product dashboards' own frontend stacks are invisible to text extraction (stack=unknown), so the framework choice rests on the dataviz/craft sources, not on what Linear/Grafana ship.

### `skill-shell-ia` — How should the room be navigated and laid out?

Board-per-domain (work / money / health / decisions) filled from a small widget catalog, with a command palette + keyboard shortcuts as an accelerator, a docked master–detail for selection, progressive disclosure for the long tail, and a persisted density ladder. Keep money on the money board and alerts on an attention board rather than in an overflow System area.

**Avoid:** One mega-screen with everything; burying quota/leases or approvals in an overflow drawer.; Command palette as the only navigation.; A detail view that resets when live data updates.

- **Evidence:** max cluster support 63; families agentops, cli, craft, dashboards, dataviz; confidence **high** (see `skills.json` for per-node support).
- **Catalogs:** `ia-board-per-domain`, `ia-widget-catalog`, `ia-command-palette`, `ia-master-detail`, `ia-progressive-disclosure`, `ia-density-ladder`, `ia-attention-surface`, `ia-money-grouping`.
- **Needs answered:** RQ-B1, RQ-B4, ON-G5.
- **Caveat:** Left-rail vs command-palette is a recorded conflict: the corpus shows palettes used alongside a visual board (Linear, Railway, Warp), not as a replacement.

### `skill-glance` — What must the resting screen answer, in what order?

Rank the glance screen operator-first: (1) system/connection health, (2) what is running/queued/failed, (3) anything failing or stale, (4) money (spend/burn/quota/leases), (5) decisions pending, (6) fleet shape. Put the single health/staleness summary and the attention surface above the fold.

**Avoid:** Docs-health or registry chrome pushing fleet state below the fold (r0 M5).; A green badge when a projection is stale (green must never lie).

- **Evidence:** max cluster support 30; families agentops, cli, craft, dashboards, dataviz; confidence **high** (see `skills.json` for per-node support).
- **Catalogs:** `ia-attention-surface`, `tr-freshness`, `tr-degraded`, `ch-status-grid`, `ia-money-grouping`.
- **Needs answered:** ON-G1, ON-G3, ON-G4, ON-G6, ON-A2.
- **Caveat:** r0 measured this gap from code; the corpus supplies the pattern (health + attention first), not a pixel layout.

### `skill-charts` — Which mark answers which operator question?

Map questions to marks: cost/burn/latency over time → line/area + inline sparkline; fleet/node status → heatmap status grid; bounded quantity (queue/phase) → gauge; large sets → virtualized sortable table; live output → log stream with follow/pause; multi-step run → timeline/waterfall; cross-group comparison → small multiples.

**Avoid:** Per-card microcharts that cannot compare (r0 M6).; Color as the only status signal.; Rebuilding a 500-row list per event.

- **Evidence:** max cluster support 39; families agentops, cli, craft, dashboards, dataviz; confidence **high** (see `skills.json` for per-node support).
- **Catalogs:** `ch-time-series`, `ch-status-grid`, `ch-gauge`, `ch-table`, `ch-log-stream`, `ch-timeline`, `ch-small-multiples`, `ch-perf`.
- **Needs answered:** ON-G2, ON-G7, ON-D1, RQ-C3.
- **Caveat:** Small multiples and threshold bands are thin/one-source in the corpus; use them only where the operator question demands comparison and keep the status grid as the default.

### `skill-visual-system` — What visual system makes this feel sleek and trustworthy?

One token layer (CSS custom properties + color-mix) drives a dark-first theme with a real light theme and a forced-colors path; few colorblind-safe status hues, always with a non-color signal; tabular numerals on a small type scale; one icon family; structural elevation; a restrained motion budget that honors prefers-reduced-motion.

**Avoid:** Inverting light to fake dark (elevation/contrast break).; Accent everywhere; more than a handful of hues.; Motion that competes with the 1s live cadence.

- **Evidence:** max cluster support 28; families cli, craft, dashboards, dataviz; confidence **high** (see `skills.json` for per-node support).
- **Catalogs:** `cm-tokens`, `cm-status-color`, `cm-dark-first`, `cm-accent`, `cm-type`, `cm-icon`, `cm-elevation`, `cm-motion`, `cm-reduced-motion`, `cm-forced-colors`.
- **Needs answered:** RQ-D1, RQ-D2, RQ-D3, RQ-D4, RQ-D5.
- **Caveat:** Aesthetic evidence is text-only: 105/229 sources record aesthetic=unspecified, and the Material/Apple HIG density pages were not text-extractable, so the visual system is argued from stated systems (F2/F5), not observed pixels.

### `skill-svg` — How should diagrams and micro-visuals be built?

Author diagrams as theme-aware SVG (viewBox + currentColor + custom properties), give informative SVGs a title/desc (aria-hidden when decorative), keep labels as SVG <text> for print, and build sparklines/gauges/status glyphs as small SVG+CSS pieces. Use a path tracer only for genuine flow/route lines.

**Avoid:** Hard-coded fills; text outlined to paths.; Pulling a JS chart runtime for a 40px sparkline.; Decorative SVG announced to screen readers.

- **Evidence:** max cluster support 29; families cli, craft, dashboards, dataviz; confidence **high** (see `skills.json` for per-node support).
- **Catalogs:** `svg-theme`, `svg-micro`, `svg-accessible`, `svg-path`, `svg-flow`, `svg-print`.
- **Needs answered:** RQ-J1, RQ-J2, RQ-J3, RQ-H1.
- **Caveat:** The flow-diagram cluster is 2 sources; the technique is supported but the exact diagram layout is not evidenced, so treat the topology design as unproven.

### `skill-trust` — How does the room stay truthful under load?

Attach provenance (measured/estimated/unknown + model/window) to consequential numbers; show freshness and a retained-window marker instead of implying live; keep a degraded banner that names the failing dependency; and encode uncertainty or 'unmeasured' explicitly so green never lies.

**Avoid:** A single health number collapsing distinct failure modes.; Fresh-looking charts over stale/partial data.; Estimated cost shown as metered.

- **Evidence:** max cluster support 40; families agentops, cli, craft, dashboards, dataviz; confidence **high** (see `skills.json` for per-node support).
- **Catalogs:** `tr-lineage`, `tr-provenance`, `tr-freshness`, `tr-degraded`, `tr-uncertainty`, `ia-attention-surface`.
- **Needs answered:** ON-G6, ON-A2, ON-A3, ON-A6, RQ-F3, RQ-F4.
- **Caveat:** Freshness and uncertainty clusters are small (3–4 sources); the provenance/lineage cluster is strong (F1).

### `skill-agent-ops` — Which agent-specific surfaces must exist?

Provide the eval loop (datasets→runs→scores→compare), a prompt registry linked to runs, and OTel-based observability so multiple agents/providers feed one room; the trace/span tree is the core navigation object.

**Avoid:** A vendor-only trace format.; Eval siloed from the live room.

- **Evidence:** max cluster support 40; families agentops, cli, dashboards, dataviz; confidence **high** (see `skills.json` for per-node support).
- **Catalogs:** `ao-eval`, `ao-prompt`, `ao-observability`, `tr-lineage`, `tr-provenance`.
- **Needs answered:** RQ-F1, RQ-F2.
- **Caveat:** Agent-ops evidence is F1-only by construction (the family is the agent-ops family); apply the single-source caveat.

### `skill-synthesis` — One-line synthesis for a sleek dark data-dense agent-ops room.

Framework: build-less vanilla JS + CSS tokens, with uPlot/ECharts only for streaming charts and D3 for bespoke marks. Layout: board-per-domain from a small widget catalog, command palette + keyboard shortcuts, docked master–detail, persisted density ladder, money and attention as their own boards. Charts: status grid at a glance, line/sparkline over time, gauge for bounded state, virtualized table for sets, waterfall for runs. Visual: one token layer, dark-first + light + forced-colors, colorblind-safe status always with shape/label, tabular numerals, restrained motion with reduced-motion. SVG: theme-aware, accessible, print-safe; micro-visuals as SVG+CSS. Avoid: a React build, per-card microcharts, color-only status, a single collapsing health number, and embiggening chrome over data.

**Avoid:** A React SPA build for a local single-page console.; Per-card microcharts and color-only status.; Green health over stale/unmeasured data.

- **Evidence:** max cluster support 55; families agentops, cli, craft, dashboards, dataviz; confidence **high** (see `skills.json` for per-node support).
- **Catalogs:** `fw-no-build`, `ia-board-per-domain`, `ia-command-palette`, `ia-master-detail`, `ch-status-grid`, `ch-time-series`, `ch-gauge`, `ch-table`, `ch-timeline`, `cm-tokens`, `cm-status-color`, `svg-theme`, `svg-micro`.
- **Caveat:** This is the reduction's one-line answer; r5 must cite it against the operator needs and r6 must attack it before the brief.

## 2. Catalogs

### Framework / delivery-model catalog (`frameworks`)

*RQ-A1–A3, RQ-C2 — how the console itself is built, and which chart runtime to adopt.*

| Item | Recommendation | Support | Families | Confidence | Caveats |
|---|---|---|---|---|---|
| `fw-no-build` | Build-less vanilla JS + CSS custom properties | 14 | dataviz:11, cli:3 | medium | — |
| `fw-d3` | D3 primitives for bespoke marks | 5 | dataviz:5 | low | single-family evidence (dataviz only) — single-source caveat applies |
| `fw-declarative` | Declarative grammars (Vega-Lite, Observable Plot) | 52 | dataviz:32, dashboards:19, cli:1 | high | — |
| `fw-canvas-stream` | Canvas time-series engine (uPlot / ECharts) | 39 | dashboards:20, dataviz:17, cli:2 | high | — |
| `fw-echarts` | ECharts for batteries-included charts + ARIA | 52 | dataviz:32, dashboards:19, cli:1 | high | — |
| `fw-react-kits` | React copy-paste kits (Tremor, shadcn/ui charts, Nivo) | 10 | dataviz:10 | low | single-family evidence (dataviz only) — single-source caveat applies |

- **`fw-no-build`** — Keep the console build-less: vanilla JS state/render + CSS custom properties for tokens, and hand-authored SVG/CSS micro-visuals. The corpus' no-framework chart (uPlot) and SVG/CSS craft sources demonstrate the approach at this scale.  
  *When:* A single-page local operator console with no npm pipeline and few contributors.  
  *Avoid when:* Many contributors needing a typed component model or a large third-party widget set.  
  *Refs:* dataviz:`https://github.com/leeoniya/uPlot`; dataviz:`https://d3js.org/`; craft:`https://every-layout.dev/`; dataviz:`https://d3js.org/`; dataviz:`https://d3js.org/what-is-d3`
- **`fw-d3`** — Reach for D3 when a mark is genuinely bespoke (custom flow/cost geometry). It binds data to DOM/SVG directly, so it composes with a no-build console but costs imperative code.  
  *When:* One or two custom visualizations that no library draws well.  
  *Avoid when:* Standard time-series or dashboards that a smaller library already covers.  
  *Refs:* dataviz:`https://d3js.org/`; dataviz:`https://github.com/observablehq/plot`; dataviz:`https://d3js.org/`; dataviz:`https://d3js.org/what-is-d3`; dataviz:`https://d3js.org/d3-scale-chromatic`
- **`fw-declarative`** — Use a declarative grammar when chart variety matters more than bespoke geometry; a spec beats imperative code for a catalog of standard marks.  
  *When:* Many standard chart forms and rapid iteration on encodings.  
  *Avoid when:* A tiny payload target or one-off marks.  
  *Refs:* dataviz:`https://vega.github.io/vega-lite/`; dataviz:`https://github.com/observablehq/plot`; dashboards:`https://grafana.com/`; dashboards:`https://grafana.com/docs/grafana/latest/`; dashboards:`https://grafana.com/docs/grafana/latest/dashboards/`
- **`fw-canvas-stream`** — For many live points (cost/burn/latency at fleet scale), prefer a canvas renderer built for streaming — uPlot is the small/fast end, ECharts the batteries-included end; both document the canvas-vs-SVG tradeoff.  
  *When:* Hundreds of concurrent live series or high-frequency updates.  
  *Avoid when:* A handful of static marks (SVG is simpler and accessible by default).  
  *Refs:* dataviz:`https://github.com/leeoniya/uPlot`; dataviz:`https://echarts.apache.org/handbook/en/best-practices/canvas-vs-svg/`; dashboards:`https://grafana.com/`; dashboards:`https://grafana.com/docs/grafana/latest/`; dashboards:`https://grafana.com/docs/grafana/latest/dashboards/`
- **`fw-echarts`** — ECharts couples a broad chart catalog with responsive containers and documented ARIA support — the strongest single-library a11y evidence in the corpus.  
  *When:* Breadth of chart types plus built-in accessibility and resize behavior.  
  *Avoid when:* A strict small-payload / no-dependency budget.  
  *Refs:* dataviz:`https://echarts.apache.org/en/index.html`; dataviz:`https://echarts.apache.org/handbook/en/best-practices/aria/`; dataviz:`https://echarts.apache.org/handbook/en/concepts/chart-size/`; dashboards:`https://grafana.com/`; dashboards:`https://grafana.com/docs/grafana/latest/`
- **`fw-react-kits`** — These are the fastest path to polished chart/UI primitives, but they assume React + a build step (Tailwind/Recharts). Recommended only if the no-build guardrail is lifted.  
  *When:* A React build is adopted and copy-paste velocity is the priority.  
  *Avoid when:* The room stays a no-build Flask companion (r0 §9.8).  
  *Refs:* dataviz:`https://www.tremor.so/`; dataviz:`https://ui.shadcn.com/charts`; dataviz:`https://nivo.rocks/bar/`; dataviz:`https://nivo.rocks/bar/`; dataviz:`https://nivo.rocks/line/`

### IA / layout catalog (`ia-layout`)

*RQ-B1–B5, RQ-E1–E2 — navigation, board structure, detail pattern, density, attention and money grouping.*

| Item | Recommendation | Support | Families | Confidence | Caveats |
|---|---|---|---|---|---|
| `ia-board-per-domain` | Board per domain | 55 | dashboards:53, agentops:1, cli:1 | high | — |
| `ia-widget-catalog` | Widget / panel catalog | 63 | dashboards:41, cli:15, dataviz:7 | high | — |
| `ia-command-palette` | Command palette + keyboard-first navigation | 14 | dashboards:11, cli:3 | medium | — |
| `ia-master-detail` | Master / detail (docked detail, side peek) | 15 | cli:11, craft:4 | medium | — |
| `ia-tab-bar` | Tabs / panes / split views | 15 | cli:14, craft:1 | medium | — |
| `ia-progressive-disclosure` | Progressive disclosure | 4 | craft:4 | low | single-family evidence (craft only) — single-source caveat applies; thin support (4 sources) |
| `ia-density-ladder` | Density ladder / responsive sizing | 14 | dashboards:7, dataviz:3, craft:3, cli:1 | high | — |
| `ia-attention-surface` | Attention / alert surface | 28 | dashboards:23, agentops:5 | medium | — |
| `ia-money-grouping` | Group money surfaces together | 17 | agentops:13, dashboards:4 | medium | — |
| `ia-audit-trail` | Audit trail / changelog affordance | 14 | dashboards:7, cli:6, agentops:1 | high | — |

- **`ia-board-per-domain`** — Give each operator domain its own board (fleet/work, money, health, decisions) rather than one mega-screen; this is the dominant ops IA in the corpus.  
  *When:* Several distinct operator questions (work vs money vs health).  
  *Avoid when:* Only one domain exists.  
  *Refs:* dashboards:`https://grafana.com/docs/grafana/latest/dashboards/`; dashboards:`https://docs.datadoghq.com/dashboards/`; dashboards:`https://docs.sentry.io/product/dashboards/`; dashboards:`https://docs.railway.com/`; agentops:`https://langfuse.com/docs/analytics/overview`
- **`ia-widget-catalog`** — Offer a small, named set of reusable panels (status tile, sparkline, table, log pane) instead of bespoke per-card markup; the widget-catalog pattern recurs across F2/F3/F4.  
  *When:* The same panel type repeats across boards.  
  *Avoid when:* Every panel is genuinely one-off.  
  *Refs:* dashboards:`https://grafana.com/docs/grafana/latest/panels-visualizations/`; dashboards:`https://docs.datadoghq.com/dashboards/widgets/`; cli:`https://textual.textualize.io/widgets/`; cli:`https://charm.sh/`; dashboards:`https://vercel.com/`
- **`ia-command-palette`** — Ship a command palette and global shortcuts as an accelerator over the visual IA — the ops/terminal sources pair palettes with keyboard access, not instead of boards.  
  *When:* Power operators repeat the same jumps and actions.  
  *Avoid when:* It is the only navigation (discoverability suffers).  
  *Refs:* dashboards:`https://linear.app/`; dashboards:`https://docs.railway.com/`; cli:`https://www.warp.dev/`; cli:`https://github.com/junegunn/fzf`; dashboards:`https://linear.app/`
- **`ia-master-detail`** — Select a node in a live grid and inspect it in a docked detail region that survives updates; the corpus' table/preview patterns pair a list with an adjacent detail.  
  *When:* Drill-down from a dense list without losing the list.  
  *Avoid when:* Selection is rare (a routed page is simpler).  
  *Refs:* craft:`https://inclusive-components.design/`; dashboards:`https://docs.railway.com/`; cli:`https://github.com/jesseduffield/lazygit`; cli:`https://www.waveterm.dev/`; cli:`https://github.com/charmbracelet/lipgloss`
- **`ia-tab-bar`** — Use tabs or split panes to keep several live surfaces co-resident; terminal multiplexers and the ARIA tabs pattern show the interaction contract (roving focus, labelled panels).  
  *When:* Operators juggle several surfaces at once.  
  *Avoid when:* A single surface is enough.  
  *Refs:* cli:`https://sw.kovidgoyal.net/kitty/`; cli:`https://ghostty.org/`; cli:`https://wezterm.org/`; craft:`https://www.w3.org/WAI/ARIA/apg/patterns/`; cli:`https://www.warp.dev/`
- **`ia-progressive-disclosure`** — Show the common case and defer the rest to a secondary surface (drawer/peek); NN/g's canonical two-level reveal and Every Layout's composable primitives both support this.  
  *When:* Surfaces have a frequent core and a long tail.  
  *Avoid when:* Hiding a decision-critical signal (r0 M5 risk).  
  *Refs:* craft:`https://www.nngroup.com/articles/progressive-disclosure/`; craft:`https://every-layout.dev/`; craft:`https://web.dev/learn/design/`; craft:`https://www.nngroup.com/articles/progressive-disclosure/`; craft:`https://www.nngroup.com/articles/skeleton-screens/`
- **`ia-density-ladder`** — Provide a persisted density mode (comfortable/compact) and intrinsic layout; the responsive-design and data-dense typography sources support both.  
  *When:* Dense telemetry must stay usable across laptop and phone.  
  *Avoid when:* Density switch resets selection/focus.  
  *Refs:* craft:`https://web.dev/learn/design/`; craft:`https://every-layout.dev/`; dashboards:`https://fly.io/docs/`; craft:`https://www.smashingmagazine.com/2023/10/choose-typefaces-fintech-products-guide-part1/`; dashboards:`https://linear.app/`
- **`ia-attention-surface`** — Give alerts and health a first-class board (severity, owner, ack), not just a count; Grafana/Datadog/Sentry all separate the attention surface from the dashboard.  
  *When:* Operators must not miss failures or staleness.  
  *Avoid when:* Alerting becomes a firehose (r0 ON-A2).  
  *Refs:* dashboards:`https://grafana.com/docs/grafana/latest/alerting/`; dashboards:`https://docs.datadoghq.com/monitors/`; dashboards:`https://docs.sentry.io/product/alerts/`; agentops:`https://www.langchain.com/langsmith`; agentops:`https://phoenix.arize.com/`
- **`ia-money-grouping`** — Keep spend, burn, quota/wallet and budget thresholds on the money board; the agent-ops cost/analytics sources and Stripe's payments IA both treat money as its own domain (r0 M1: quota buried in System).  
  *When:* Spend/quota decisions are part of the operator loop.  
  *Avoid when:* Money data is untrusted/unmeasured.  
  *Refs:* dashboards:`https://stripe.com/docs`; agentops:`https://langfuse.com/docs/analytics/overview`; agentops:`https://docs.helicone.ai/`; agentops:`https://langfuse.com/docs`; agentops:`https://langfuse.com/docs/observability/overview`
- **`ia-audit-trail`** — Expose a durable, filterable history (what changed, when, by whom) as an evidence surface, not a marketing changelog.  
  *When:* A canonical record or decision needs explaining.  
  *Avoid when:* It becomes a passive feed nothing reads.  
  *Refs:* dashboards:`https://linear.app/changelog`; dashboards:`https://vercel.com/changelog`; agentops:`https://docs.confident-ai.com/`; agentops:`https://docs.smith.langchain.com/administration`; dashboards:`https://linear.app/`

### Chart-selection catalog (`chart-selection`)

*RQ-C1–C5 — which mark for which operator question, and the performance budget.*

| Item | Recommendation | Support | Families | Confidence | Caveats |
|---|---|---|---|---|---|
| `ch-time-series` | Line / area / sparkline for cost, burn, latency over time | 39 | dashboards:20, dataviz:17, cli:2 | high | — |
| `ch-status-grid` | Status grid / heatmap for fleet state | 30 | dashboards:17, dataviz:10, cli:2, craft:1 | high | — |
| `ch-gauge` | Gauge / progress meter for bounded quantities | 25 | dataviz:10, dashboards:8, cli:6, craft:1 | high | — |
| `ch-table` | Virtualized / sortable table for large sets | 32 | dashboards:25, cli:3, craft:3, dataviz:1 | high | — |
| `ch-log-stream` | Live log / event stream with follow + filter | 36 | dashboards:25, cli:7, agentops:2, dataviz:2 | high | — |
| `ch-timeline` | Timeline / waterfall for runs and phases | 14 | agentops:14 | low | single-family evidence (agentops only) — single-source caveat applies |
| `ch-small-multiples` | Small multiples for comparison | 4 | dataviz:3, craft:1 | low | thin support (4 sources) |
| `ch-grammar` | Chart grammar / library selection | 52 | dataviz:32, dashboards:19, cli:1 | high | — |
| `ch-perf` | Performance budget: canvas, decimation, lazy render | 15 | cli:8, dataviz:5, craft:2 | high | — |

- **`ch-time-series`** — Use line/area marks for trends over time and sparklines inline in rows; this is the single most-evidenced mark family in the corpus.  
  *When:* A quantity changes over time (spend, tokens, latency, queue depth).  
  *Avoid when:* Comparing unordered categories.  
  *Refs:* dataviz:`https://github.com/leeoniya/uPlot`; dataviz:`https://echarts.apache.org/examples/en/index.html`; dashboards:`https://docs.datadoghq.com/dashboards/`; dashboards:`https://grafana.com/docs/grafana/latest/dashboards/`; dashboards:`https://grafana.com/`
- **`ch-status-grid`** — Encode many nodes' state as a status grid so color/position read pre-attentively; NN/g's dashboard guidance and Grafana's panel model both support grid-over-list at fleet scale.  
  *When:* One glance must answer 'is anything wrong across N nodes'.  
  *Avoid when:* Color is the only signal (add shape/label).  
  *Refs:* craft:`https://www.nngroup.com/articles/dashboards-preattentive/`; dashboards:`https://grafana.com/docs/grafana/latest/panels-visualizations/`; dashboards:`https://docs.datadoghq.com/dashboards/`; dashboards:`https://grafana.com/docs/grafana/latest/`; dashboards:`https://grafana.com/docs/grafana/latest/dashboards/`
- **`ch-gauge`** — Use a gauge/progress mark for a bounded quantity (queue depth vs cap, phase progress); process monitors (nvitop, btop) demonstrate the compact bounded-state mark.  
  *When:* A value has a known maximum or a completion ratio.  
  *Avoid when:* The value is unbounded (a number or sparkline is better).  
  *Refs:* cli:`https://github.com/XuehaiPan/nvitop`; cli:`https://github.com/aristocratos/btop`; dashboards:`https://docs.datadoghq.com/dashboards/`; dashboards:`https://grafana.com/docs/grafana/latest/`; dashboards:`https://grafana.com/docs/grafana/latest/dashboards/`
- **`ch-table`** — Use a large sortable table for registry/cells/events; virtualize rows (content-visibility or a virtual list) and keep header/selection stable under live updates.  
  *When:* Many rows with find/sort/compare/act tasks.  
  *Avoid when:* A handful of rows (a list or cards is clearer).  
  *Refs:* craft:`https://www.nngroup.com/articles/data-tables/`; dashboards:`https://grafana.com/docs/grafana/latest/panels-visualizations/`; dashboards:`https://fly.io/docs/reference/`; craft:`https://www.w3.org/WAI/tutorials/tables/`; dashboards:`https://vercel.com/`
- **`ch-log-stream`** — Render the transcript/log as a bounded live stream with follow, pause and filter; the ops docs treat logs as their own surface, distinct from dashboards.  
  *When:* Unbounded, append-only output must be watched live.  
  *Avoid when:* Rebuilding the whole list per event (r0 app.js:1522).  
  *Refs:* dashboards:`https://docs.railway.com/`; dashboards:`https://docs.datadoghq.com/`; dashboards:`https://supabase.com/docs/guides/observability`; dashboards:`https://modal.com/docs/guide`; agentops:`https://docs.helicone.ai/`
- **`ch-timeline`** — Use a timeline/waterfall to show a run's phases and spans over time; every major agent-ops source ships a trace waterfall for exactly this question.  
  *When:* A multi-step run's latency and order must be inspected.  
  *Avoid when:* Only totals matter (a number suffices).  
  *Refs:* agentops:`https://docs.arize.com/phoenix`; agentops:`https://www.langchain.com/langsmith`; agentops:`https://langfuse.com/docs`; agentops:`https://langfuse.com/docs/observability/overview`; agentops:`https://docs.smith.langchain.com/`
- **`ch-small-multiples`** — Tile the same mark across dimensions (model/condition) for comparison; supported but thinner in the corpus — prefer it over overlaying many series on one axis.  
  *When:* The same measure must be compared across groups.  
  *Avoid when:* It becomes a wall of unreadable mini-charts (r0 M6).  
  *Refs:* dataviz:`https://echarts.apache.org/handbook/en/best-practices/canvas-vs-svg/`; craft:`https://www.nngroup.com/articles/dashboards-preattentive/`; dataviz:`https://echarts.apache.org/handbook/en/best-practices/canvas-vs-svg/`; dataviz:`https://github.com/leeoniya/uPlot`; dataviz:`https://leeoniya.github.io/uPlot/`
- **`ch-grammar`** — Pick one grammar/library per surface and stay consistent; the corpus spans imperative (D3), declarative (Vega-Lite, Plot), canvas (uPlot/ECharts) and React kits — the choice is the framework catalog's, this item only bounds the mark set.  
  *When:* Deciding how charts are authored at all.  
  *Avoid when:* Mixing three grammars on one page.  
  *Refs:* dataviz:`https://vega.github.io/vega-lite/`; dataviz:`https://d3js.org/`; dashboards:`https://grafana.com/`; dashboards:`https://grafana.com/docs/grafana/latest/`; dashboards:`https://grafana.com/docs/grafana/latest/dashboards/`
- **`ch-perf`** — Bound live marks: canvas over SVG for high-frequency series, sampling/decimation, and content-visibility for off-screen panels; the corpus' only measured performance evidence (web.dev) supports lazy rendering.  
  *When:* Hundreds of marks or long lists update on a short cadence.  
  *Avoid when:* It hides data the operator must see (sampling must be honest).  
  *Refs:* craft:`https://web.dev/articles/content-visibility`; dataviz:`https://echarts.apache.org/handbook/en/best-practices/canvas-vs-svg/`; dataviz:`https://github.com/leeoniya/uPlot`; dataviz:`https://echarts.apache.org/en/index.html`; dataviz:`https://echarts.apache.org/handbook/en/get-started/`

### Color / motion / type catalog (`color-motion`)

*RQ-D1–D5, RQ-H1 — tokens, dark-first theming, status color, accent economy, type, motion budget, forced colors.*

| Item | Recommendation | Support | Families | Confidence | Caveats |
|---|---|---|---|---|---|
| `cm-tokens` | Smallest viable token layer (CSS custom properties) | 28 | craft:10, dashboards:8, dataviz:8, cli:2 | high | — |
| `cm-status-color` | Colorblind-safe, never-color-alone status | 16 | craft:6, dashboards:5, dataviz:4, cli:1 | high | — |
| `cm-dark-first` | Dark-first with a real light + forced-colors path | 28 | craft:10, dashboards:8, dataviz:8, cli:2 | high | — |
| `cm-accent` | Accent economy / minimal chrome | 10 | craft:5, dashboards:4, cli:1 | high | — |
| `cm-type` | Type scale for dense data (tabular numerals) | 9 | craft:5, dashboards:3, cli:1 | medium | — |
| `cm-icon` | One icon family, labelled where ambiguous | 4 | craft:4 | low | single-family evidence (craft only) — single-source caveat applies; thin support (4 sources) |
| `cm-elevation` | Elevation model (surfaces, not shadows-as-decoration) | 3 | craft:3 | low | single-family evidence (craft only) — single-source caveat applies; thin support (3 sources) |
| `cm-motion` | Motion easing / springs with a budget | 11 | craft:7, dashboards:4 | medium | — |
| `cm-reduced-motion` | Reduced-motion path | 14 | dashboards:7, craft:6, dataviz:1 | high | — |
| `cm-forced-colors` | Forced-colors / high-contrast support | 8 | cli:4, craft:4 | medium | — |

- **`cm-tokens`** — Define one token set (surface/elevation/accent/status/type) with CSS custom properties and derive variants with color-mix(); this is the smallest design-system layer that yields consistency without a framework runtime.  
  *When:* A single-page console needs visual consistency.  
  *Avoid when:* Tokens proliferate without a naming convention.  
  *Refs:* craft:`https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties`; craft:`https://www.refactoringui.com/`; craft:`https://developer.mozilla.org/en-US/docs/Web/CSS/color_value/color-mix`; craft:`https://www.smashingmagazine.com/2024/05/naming-best-practices/`; dashboards:`https://linear.app/customers`
- **`cm-status-color`** — Keep status hues few and colorblind-safe, and always pair color with shape/label; contrast + palette sources (web.dev, ColorBrewer, NN/g, WCAG 1.4.3) define the bar.  
  *When:* Lifecycle/severity/attention states are encoded.  
  *Avoid when:* Hue count grows until it is noise.  
  *Refs:* craft:`https://web.dev/articles/color-and-contrast-accessibility`; dataviz:`https://colorbrewer2.org/`; craft:`https://www.nngroup.com/articles/color-enhance-design/`; craft:`https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html`; dashboards:`https://linear.app/customers`
- **`cm-dark-first`** — Theme dark-first but keep a real light theme from the same tokens, and honor prefers-color-scheme/forced-colors; NN/g's dark-mode guidance and MDN's forced-colors feature define the fallback.  
  *When:* The room is dark by default.  
  *Avoid when:* Dark is just inverted light (elevation/contrast break).  
  *Refs:* craft:`https://www.nngroup.com/articles/dark-mode/`; craft:`https://developer.mozilla.org/en-US/docs/Web/CSS/@media/forced-colors`; craft:`https://web.dev/articles/color-and-contrast-accessibility`; dashboards:`https://linear.app/customers`; dashboards:`https://vercel.com/`
- **`cm-accent`** — Spend the accent color on one thing at a time and strip decorative chrome; Refactoring UI and NN/g both argue restrained accents carry more meaning.  
  *When:* Data is dense and chrome competes with it.  
  *Avoid when:* Every panel is highlighted (nothing stands out).  
  *Refs:* craft:`https://www.refactoringui.com/`; craft:`https://www.nngroup.com/articles/color-enhance-design/`; dashboards:`https://vercel.com/`; dashboards:`https://linear.app/`; dashboards:`https://vercel.com/`
- **`cm-type`** — Fix a small type scale and use tabular numerals for data-dense panels; the typography and fintech-typeface sources specifically address numerals under dense data.  
  *When:* Many small numbers must align and scan.  
  *Avoid when:* More than a few sizes / weights are in play.  
  *Refs:* craft:`https://practicaltypography.com/summary-of-key-rules.html`; craft:`https://www.smashingmagazine.com/2023/10/choose-typefaces-fintech-products-guide-part1/`; craft:`https://developer.mozilla.org/en-US/docs/Web/SVG/Tutorial/Texts`; dashboards:`https://vercel.com/docs`; dashboards:`https://vercel.com/geist/colors`
- **`cm-icon`** — Use one consistent SVG icon family (symbol/<use>) and label icons whose meaning is not universal; NN/g's icon-usability findings and the SVG symbol technique support this.  
  *When:* Dense toolbars/status glyphs are needed.  
  *Avoid when:* Icon-only controls for novel actions.  
  *Refs:* craft:`https://www.nngroup.com/articles/icon-usability/`; craft:`https://developer.mozilla.org/en-US/docs/Web/SVG/Element/use`; craft:`https://css-tricks.com/mega-list-svg-information/`; craft:`https://developer.mozilla.org/en-US/docs/Web/SVG/Element/use`; craft:`https://www.nngroup.com/articles/icon-usability/`
- **`cm-elevation`** — Separate surfaces with a small elevation ladder (background/surface/raised/overlay); dark-mode and Refactoring UI sources tie depth to structure, not ornament.  
  *When:* Layered panels/overlays must be distinguishable in dark.  
  *Avoid when:* Every card is elevated (depth loses meaning).  
  *Refs:* craft:`https://www.nngroup.com/articles/dark-mode/`; craft:`https://www.refactoringui.com/`; craft:`https://web.dev/learn/css/`; craft:`https://web.dev/learn/css/`; craft:`https://www.nngroup.com/articles/dark-mode/`
- **`cm-motion`** — Animate state changes only, with short durations and spring/ease curves; the spring-physics and microinteraction sources frame motion as feedback, not decoration.  
  *When:* A change needs confirming (arrive/leave/attention).  
  *Avoid when:* Motion competes with a 1s live tick.  
  *Refs:* craft:`https://www.joshwcomeau.com/animation/a-friendly-introduction-to-spring-physics/`; craft:`https://www.nngroup.com/articles/microinteractions/`; dashboards:`https://linear.app/`; dashboards:`https://linear.app/blog`; dashboards:`https://linear.app/customers`
- **`cm-reduced-motion`** — Honor prefers-reduced-motion: drop large/parallax motion and non-essential animation while preserving state feedback; MDN and web.dev define the safe degradation.  
  *When:* Any motion exists at all.  
  *Avoid when:* Reduced motion removes information that only motion carried.  
  *Refs:* craft:`https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion`; craft:`https://web.dev/articles/prefers-reduced-motion`; craft:`https://www.nngroup.com/articles/microinteractions/`; dashboards:`https://linear.app/`; dashboards:`https://linear.app/blog`
- **`cm-forced-colors`** — Use system color keywords and currentColor so the room survives Windows High Contrast; MDN's forced-colors guide is the normative reference.  
  *When:* High-contrast/forced-colors users are supported.  
  *Avoid when:* Hard-coded hex colors block the override.  
  *Refs:* craft:`https://developer.mozilla.org/en-US/docs/Web/CSS/@media/forced-colors`; craft:`https://web.dev/articles/color-and-contrast-accessibility`; cli:`https://ghostty.org/`; cli:`https://ghostty.org/docs`; cli:`https://github.com/charmbracelet/lipgloss`

### SVG-technique catalog (`svg-technique`)

*RQ-J1–J3 — theme-aware, accessible, print-safe diagrams and micro-visuals.*

| Item | Recommendation | Support | Families | Confidence | Caveats |
|---|---|---|---|---|---|
| `svg-theme` | Theme-aware SVG (viewBox + currentColor + custom properties) | 29 | craft:12, cli:9, dataviz:8 | high | — |
| `svg-micro` | Micro-visuals as SVG + CSS (no chart runtime) | 22 | craft:12, dataviz:7, cli:3 | high | — |
| `svg-accessible` | Accessible SVG (title/desc, role, text alternative) | 10 | craft:5, dashboards:3, dataviz:2 | high | — |
| `svg-path` | Path tracer for flow / route lines | 7 | craft:5, dataviz:2 | medium | — |
| `svg-flow` | Flow / architecture diagram | 4 | cli:2, craft:2 | low | thin support (4 sources) |
| `svg-print` | Print-safe SVG (text as text, no raster) | 3 | craft:3 | low | single-family evidence (craft only) — single-source caveat applies; thin support (3 sources) |

- **`svg-theme`** — Author diagrams with viewBox for scale and drive colors from currentColor/custom properties so one SVG renders in both themes and forced-colors.  
  *When:* Any architecture/flow/topology diagram.  
  *Avoid when:* Hard-coded fills (breaks theming/high contrast).  
  *Refs:* craft:`https://developer.mozilla.org/en-US/docs/Web/SVG/Attribute/viewBox`; craft:`https://developer.mozilla.org/en-US/docs/Web/SVG/Element/use`; craft:`https://www.smashingmagazine.com/2025/11/smashing-animations-part-6-svgs-css-custom-properties/`; craft:`https://css-tricks.com/svg-properties-and-css/`; dataviz:`https://d3js.org/`
- **`svg-micro`** — Build sparklines, gauges and status glyphs as small SVG+CSS pieces (path + stroke/dasharray/gradient) rather than pulling a JS chart runtime.  
  *When:* A mark is tiny and repeated many times.  
  *Avoid when:* The mark needs real interaction/data-heavy redraw.  
  *Refs:* craft:`https://css-tricks.com/svg-line-animation-works/`; craft:`https://svg-tutorial.com/svg/gradient`; craft:`https://www.nngroup.com/articles/dashboards-preattentive/`; dataviz:`https://d3js.org/`; dataviz:`https://d3js.org/what-is-d3`
- **`svg-accessible`** — Give meaningful SVGs a title/desc or role=img with a label, and mark decorative ones aria-hidden; the a11y sources define the text-alternative contract.  
  *When:* Any SVG conveys information.  
  *Avoid when:* A complex diagram has no textual equivalent.  
  *Refs:* craft:`https://css-tricks.com/accessible-svgs/`; craft:`https://developer.mozilla.org/en-US/docs/Web/SVG/Tutorial/Texts`; craft:`https://www.w3.org/WAI/ARIA/apg/patterns/`; dashboards:`https://vercel.com/docs`; dashboards:`https://vercel.com/geist/colors`
- **`svg-path`** — Use path + stroke-dasharray/dashoffset to draw flow or route lines; the path-grammar sources make the geometry maintainable rather than copy-pasted.  
  *When:* Showing a route/flow/edge between nodes.  
  *Avoid when:* A plain connector is clearer (don't over-animate).  
  *Refs:* craft:`https://developer.mozilla.org/en-US/docs/Web/SVG/Tutorial/Paths`; craft:`https://css-tricks.com/svg-line-animation-works/`; craft:`https://www.smashingmagazine.com/2025/06/decoding-svg-path-element-line-commands/`; dataviz:`https://d3js.org/d3-scale-chromatic`; dataviz:`https://d3js.org/d3-shape`
- **`svg-flow`** — For the queue→worker→cell→session topology, compose labeled shapes with explicit groups and a legend; supported but thin in the corpus (2 families).  
  *When:* Operators need the system's shape, not a table of its parts.  
  *Avoid when:* The diagram duplicates live state that belongs on a board.  
  *Refs:* craft:`https://developer.mozilla.org/en-US/docs/Web/SVG/Tutorial/Paths`; craft:`https://www.smashingmagazine.com/2025/06/decoding-svg-path-element-line-commands/`; cli:`https://github.com/charmbracelet/bubbletea`; cli:`https://github.com/htop-dev/htop`; craft:`https://developer.mozilla.org/en-US/docs/Web/SVG/Tutorial/Paths`
- **`svg-print`** — Keep labels as SVG <text> so diagrams survive print/zoom and scale cleanly.  
  *When:* Diagrams may be exported or printed.  
  *Avoid when:* Text is outlined into paths (loses accessibility/search).  
  *Refs:* craft:`https://developer.mozilla.org/en-US/docs/Web/SVG/Tutorial/Texts`; craft:`https://css-tricks.com/accessible-svgs/`; craft:`https://developer.mozilla.org/en-US/docs/Web/SVG/Tutorial/Texts`; craft:`https://css-tricks.com/accessible-svgs/`; craft:`https://svg-tutorial.com/svg/text`

### Trust / attention catalog (supplementary) (`trust-attention`)

*RQ-F1–F4, ON-G6/A2 — lineage, provenance, freshness, degraded state, uncertainty.*

| Item | Recommendation | Support | Families | Confidence | Caveats |
|---|---|---|---|---|---|
| `tr-lineage` | Causal lineage / span tree | 23 | agentops:16, dashboards:5, cli:2 | high | — |
| `tr-provenance` | Source provenance / attribution | 40 | dashboards:26, agentops:13, dataviz:1 | high | — |
| `tr-freshness` | Freshness / staleness indicator | 4 | cli:3, craft:1 | low | thin support (4 sources) |
| `tr-degraded` | Degraded / health banner | 11 | dashboards:11 | low | single-family evidence (dashboards only) — single-source caveat applies |
| `tr-uncertainty` | Uncertainty / eval encoding | 3 | agentops:2, dataviz:1 | low | thin support (3 sources) |

- **`tr-lineage`** — Represent a run as a session→trace→span tree with parent links so a failure's cause is walkable; every major agent-ops source ships this structure.  
  *When:* Explaining why a run/step did what it did.  
  *Avoid when:* The tree is flattened to a log.  
  *Refs:* agentops:`https://docs.arize.com/phoenix`; agentops:`https://langfuse.com/docs`; agentops:`https://langfuse.com/docs/observability/overview`; agentops:`https://docs.smith.langchain.com/`; agentops:`https://www.braintrust.dev/docs`
- **`tr-provenance`** — Attach provenance (which model/provider/window, measured vs estimated) to every consequential number, especially cost and scores.  
  *When:* A number drives a decision.  
  *Avoid when:* Provenance becomes noise on decorative stats.  
  *Refs:* agentops:`https://langfuse.com/docs/analytics/overview`; agentops:`https://docs.helicone.ai/`; agentops:`https://www.braintrust.dev/docs`; agentops:`https://langfuse.com/docs/scores/overview`; agentops:`https://langfuse.com/docs`
- **`tr-freshness`** — Show how fresh the data is (last updated / retained window) rather than implying live; the live-monitor sources tie every display to a refresh.  
  *When:* Data can lag, be retained, or be partial.  
  *Avoid when:* Green is shown when data is stale (green lies).  
  *Refs:* dashboards:`https://docs.railway.com/`; craft:`https://www.nngroup.com/articles/skeleton-screens/`; cli:`https://github.com/XuehaiPan/nvitop`; cli:`https://github.com/XuehaiPan/nvitop`; cli:`https://nvitop.readthedocs.io/`
- **`tr-degraded`** — Surface a top-level degraded/health state that names the failing dependency, without collapsing distinct failures into one number.  
  *When:* A dependency (db/projector/provider) is down.  
  *Avoid when:* The whole page collapses instead of the affected region.  
  *Refs:* dashboards:`https://docs.sentry.io/product/alerts/`; dashboards:`https://docs.railway.com/`; dashboards:`https://supabase.com/docs`; dashboards:`https://www.datadoghq.com/`; dashboards:`https://www.datadoghq.com/blog/`
- **`tr-uncertainty`** — Encode confidence/score/partiality explicitly (bands, intervals, 'unmeasured') so a viewer is never misled; the eval platforms carry the score/measure vocabulary.  
  *When:* A value is estimated, sampled, or unmeasured.  
  *Avoid when:* A point estimate is shown as certain.  
  *Refs:* agentops:`https://www.braintrust.dev/docs/guides/evals`; agentops:`https://langfuse.com/docs/scores/overview`; agentops:`https://docs.arize.com/phoenix/evaluation/llm-evals`; agentops:`https://www.patronus.ai/`; agentops:`https://www.galileo.ai/`

### Agent-ops surface catalog (supplementary) (`agent-ops`)

*F1-specific — eval loop, prompt registry, OTel observability.*

| Item | Recommendation | Support | Families | Confidence | Caveats |
|---|---|---|---|---|---|
| `ao-eval` | Eval / dataset / experiment loop | 24 | agentops:24 | low | single-family evidence (agentops only) — single-source caveat applies |
| `ao-prompt` | Prompt registry / versioning | 4 | agentops:3, cli:1 | low | thin support (4 sources) |
| `ao-observability` | Agent observability / OTel instrumentation | 22 | agentops:19, dashboards:3 | medium | — |

- **`ao-eval`** — Treat evals as a first-class surface (datasets → runs → scores → compare) alongside live traces; F1 is unanimous on the eval loop.  
  *When:* Quality must be tracked, not just observed.  
  *Avoid when:* Eval becomes a separate disconnected tool.  
  *Refs:* agentops:`https://docs.smith.langchain.com/evaluation`; agentops:`https://www.braintrust.dev/docs/guides/evals`; agentops:`https://docs.arize.com/phoenix/evaluation/llm-evals`; agentops:`https://blog.langchain.dev/`; agentops:`https://www.langchain.com/langsmith`
- **`ao-prompt`** — Version prompts and tie each run to the prompt version that produced it, so a regression is attributable.  
  *When:* Prompts change and outcomes must be compared.  
  *Avoid when:* Prompt versions aren't linked to runs.  
  *Refs:* agentops:`https://docs.smith.langchain.com/prompt_engineering`; agentops:`https://langfuse.com/docs/prompts/get-started`; agentops:`https://www.langchain.com/langsmith`; agentops:`https://docs.smith.langchain.com/prompt_engineering`; agentops:`https://langfuse.com/docs/prompts/get-started`
- **`ao-observability`** — Instrument with an open standard (OTel/OpenLLMetry) so the console can ingest without vendor lock-in; the open-source agent-ops sources converge on this.  
  *When:* Multiple agents/providers must feed one room.  
  *Avoid when:* Proprietary traces are the only option.  
  *Refs:* agentops:`https://langfuse.com/docs/observability/overview`; agentops:`https://openllmetry.com/`; agentops:`https://docs.arize.com/phoenix`; agentops:`https://blog.langchain.dev/`; agentops:`https://www.langchain.com/langsmith`

## 3. Dropped (unsupported) leaves

| Catalog | Item | Support | Reason |
|---|---|---|---|
| `(taxonomy)` | `thin-ia-modal-sheet` | 1 | thin cluster below the >=3-source bar; merged in r3 and not elevated here |
| `(taxonomy)` | `thin-ia-overflow-drawer` | 1 | thin cluster below the >=3-source bar; merged in r3 and not elevated here |
| `(taxonomy)` | `thin-viz-threshold-bands` | 1 | thin cluster below the >=3-source bar; merged in r3 and not elevated here |
| `(taxonomy)` | `thin-ops-self-host` | 2 | thin cluster below the >=3-source bar; merged in r3 and not elevated here |

## 4. Recorded conflicts (not averaged)

- **Command palette vs persistent rail:** Linear/Railway pair a palette with a visual board; the corpus does not support palette-only navigation.
- **Dark vs light:** NN/g argues dark needs desaturated surfaces and recommends offering both; the room's r0 baseline already toggles both — recorded, not resolved here.
- **SVG vs canvas:** ECharts documents the tradeoff (SVG for a few marks/accessibility, canvas for many/high-frequency); the chart catalog keeps both.
- **Framework:** the dataviz/craft sources are build-less; the React component kits require a build. Both are recorded; the skill prefers no-build under the r0 guardrail.

## 5. Coverage caveats

- Product frontend stacks are not visible to text extraction (`stack=unknown` for F2), so the framework catalog rests on the dataviz/craft sources.
- Aesthetic is text-stated only; 105/229 sources record `aesthetic=unspecified`.
- Material/Apple HIG density pages were not text-extractable (client-rendered), so density is evidenced indirectly.
- Agent-ops clusters are F1-only; the single-source caveat is carried on those items.

## 6. Reproduce

```bash
# inputs are content-hashed in catalogs.json / skills.json inputs[]
python3 -m json.tool experiments/research/control_room/catalogs.json >/dev/null
python3 -m json.tool experiments/research/control_room/skills.json >/dev/null
```

