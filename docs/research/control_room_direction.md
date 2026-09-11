---
status: accepted
---

# Control Room — design direction & facelift brief seed (campaign r5)

**Date:** 2026-09-11
**Campaign:** `workflows/repository/control_room_research.yaml`, phase `r5_synthesize`.
**Inputs:** the measured baseline `docs/research/control_room_audit.md` (r0), the operator-needs/facet
contract `docs/research/control_room_questions.md` (r1), `experiments/research/control_room/taxonomy.json`
(r3), and `catalogs.json` + `skills.json` (r4).
**Output:** ONE cited design direction. This is a synthesis of the records; r6 attacks it, r7 tightens it
into the facelift brief.

**Citation legend.**
`[r0 M#/A#/§]` = measured finding in the audit · `[ON-G#/D#/A#]` = operator need (r1 §4) ·
`[S1]–[S6]` = sleek criteria (r1 §5) · `[RQ-*]` = research question (r1 §2) ·
`[skill:…]` / `[cat:…/…]` = reduction artifacts · `[tax:…]` = taxonomy node ·
`[src:…]` = corpus source (appendix maps tag → family/uri/sha256).

---

## 1. What "sleek and sexy" means here

The mandate forbids hand-describing the adjective, so "sleek" is defined operationally by the six
criteria r1 derived from the measured problems `[S1]–[S6]`, and each is now backed by exemplars:

1. **Operator-first ranking.** The resting screen answers the operator's questions in cost order; no
   decoration precedes a decision signal `[S1]`. Exemplars: Grafana/Datadog boards rank state before
   chrome `[src:grafana]` `[src:datadog]`; NN/g's pre-attentive dashboard guidance puts status
   encoding first `[src:nng-dash]`.
2. **Calm under load.** Under the existing 1 s tick / 5 s poll with dozens of nodes, no flicker, no
   focus loss, no announcement flood `[r0 §9.1–9.3]` `[S2]`. Exemplars: keyed write-on-change lists
   are already the room's contract `[r0 §9.3]`; progressive disclosure keeps the standing screen
   quiet `[src:nng-progressive]`.
3. **Truthful state.** Partial, stale, degraded and unmeasured are distinct and green never lies
   `[S3]` `[ON-G6]`. Exemplars: projection watermarks already measured but unrendered `[r0 M2]`;
   freshness/skeleton affordances `[src:nng-skeleton]`; explicit source provenance on agent-ops
   numbers `[src:langfuse-cost]` `[src:helicone]`.
4. **Evidence at hand.** Every consequential surface is one step from the decision it supports `[S4]`.
   Exemplars: registry lineage `[r0 M4]`; agent-ops trace trees `[src:langfuse-obs]` `[src:arize]`.
5. **Restrained craft.** One token-based system — elevation, accent economy, type scale, motion
   budget — instead of accumulating chrome `[S5]`. Exemplars: Refactoring UI's constrained tactics
   `[src:refactoringui]`, token naming `[src:smashing-tokens]`, accent economy `[src:nng-color]`.
6. **Accessible by default.** Keyboard, screen reader, colorblind, reduced-motion, forced-colors
   `[S6]` `[ON-A6]`. Exemplars: WCAG 2.2 Quickref `[src:wcag-quickref]`, contrast minimum
   `[src:wcag-contrast]`, APG patterns `[src:w3c-apg]`, forced-colors
   `[src:mdn-forced-colors]`, reduced-motion `[src:mdn-reduced-motion]`.

**What sleek is *not* here:** animated flourish over live data `[src:nng-micro]`; a per-card chart
gallery `[r0 M6]`; a single big "health" number `[r0 A1]`; a modal-everything shell `[r0 M14]`; a
React component showroom `[cat:frameworks/fw-react-kits]`.

---

## 2. The one direction — "Instrument Panel"

> **A calm, truthful operator instrument: a build-less shell whose first screen is one attention strip
> over a domain board, whose money and health are first-class boards rather than overflow, whose detail
> is docked beside the live grid, and whose charts and diagrams answer one question each in a single
> dark-first token system.**

The direction is the composition of the r4 `skill-synthesis` `[skill:skill-synthesis]` with the r0
dispositions in §4. It answers the mandate's three questions directly:

- **What the operator needs to know:** the r1 needs `[ON-G1..G7]` `[ON-D1..D7]` `[ON-A1..A6]`,
  answered in §3.
- **What is present but in the wrong place:** every r0 M-finding gets a disposition in §4.
- **What is missing:** every r0 A-finding gets a disposition in §4 (built, folded in, or rejected
  with reason).

---

## 3. The operator-needs answer (glance / drill-down / alert)

### 3.1 Glance — the resting screen (no interaction)

| Need | Direction | Evidence |
|---|---|---|
| `[ON-G1]` is the system up / connected? | One **status/health summary** in the rail + a connection state; health is a board, not a badge alone. | `[r0 A1]` `[skill:skill-glance]` `[cat:trust-attention/tr-degraded]` |
| `[ON-G2]` running / queued / failed now? | **Work board**: keyed fleet grid with counts; live rows are a filter, not a second list. | `[r0 M7]` `[cat:ia-layout/ia-board-per-domain]` `[cat:chart-selection/ch-table]` |
| `[ON-G3]` anything failing / stalled / at risk? | **Attention strip** above the board: failed runs · projection lag · unhealthy workers · approvals. | `[r0 A2]` `[cat:ia-layout/ia-attention-surface]` |
| `[ON-G4]` money — spend, burn, quota, wallet, leases? | **Money board** owns spend/burn trend + provider windows + wallet + lease reservations + budget thresholds. | `[r0 M1]` `[cat:ia-layout/ia-money-grouping]` `[src:langfuse-cost]` `[src:stripe]` |
| `[ON-G5]` anything needs a decision from me? | **Decisions board**: `awaiting_approvals`, `promotable_runs` (+candidate sha), docs proposal, recording coverage. | `[r0 M3]` `[r0 A3]` `[r0 M12]` `[skill:skill-shell-ia]` |
| `[ON-G6]` is what I see fresh and trustworthy? | **Truth bar** footer: data age, retained-window marker, projection health, provenance on consequential numbers. | `[r0 M2]` `[r0 A10]` `[skill:skill-trust]` `[src:webdev-contentvis]` |
| `[ON-G7]` shape of the fleet by model/condition? | **Fleet rollup** on the Work board: status grid + small multiples by model/condition. | `[r0 A6]` `[cat:chart-selection/ch-status-grid]` `[cat:chart-selection/ch-small-multiples]` |

### 3.2 Drill-down — one selection away

| Need | Direction | Evidence |
|---|---|---|
| `[ON-D1]` what is a cell doing, step by step? | **Docked detail** transcript with follow/pause/filter (bounded stream, never a 500-row rebuild). | `[r0 §9.1]` `[cat:chart-selection/ch-log-stream]` `[src:railway]` |
| `[ON-D2]` why flagged / safe action? | Detail shows source provenance + typed **confirmation doors** (no native `confirm()`). | `[r0 M14]` `[r0 §9.6]` `[cat:trust-attention/tr-provenance]` |
| `[ON-D3]` design draft/validation? | Detail design panel unchanged; **status is never color-only**. | `[r0 §9.5]` `[cat:color-motion/cm-status-color]` |
| `[ON-D4]` which canonical record explains this? | **Registry is a destination** under Decisions, with lineage (span/session tree). | `[r0 M4]` `[cat:trust-attention/tr-lineage]` `[src:langfuse-obs]` `[src:arize]` |
| `[ON-D5]` route model at what cost/quality? | Routing folded into Work/detail; eval loop lives beside live traces. | `[r0 A6]` `[cat:agent-ops/ao-eval]` `[src:braintrust]` `[src:langsmith-eval]` |
| `[ON-D6]` what did this cost, by step? | Per-step cost **with provenance** (metered/estimated/unknown) in detail; money board owns the rollup. | `[r0 A5]` `[cat:chart-selection/ch-time-series]` `[src:helicone]` |
| `[ON-D7]` manage a background `claude` session? | Detail panel unchanged; actions stay typed. | `[r0 §9.6]` |

### 3.3 Alert — must interrupt or be impossible to miss

| Need | Direction | Evidence |
|---|---|---|
| `[ON-A1]` a run failed/timed out | Failure is an **event on the attention strip**, not only a count/tile. | `[r0 §4]` `[cat:ia-layout/ia-attention-surface]` |
| `[ON-A2]` worker/projection unhealthy or stale | Same strip; `projection_lag`/`unhealthy_workers` from the control packet. | `[r0 M2/A2/A4]` `[cat:trust-attention/tr-freshness]` |
| `[ON-A3]` spend/quota threshold crossed | Money board threshold bands + attention event. Threshold bands are thin in the corpus (1 source) — keep as a text+band cue, not a chart. | `[tax:thin-viz-threshold-bands]` `[cat:ia-layout/ia-money-grouping]` |
| `[ON-A4]` controller decision pending | Decisions board tile + attention event. | `[r0 M3/A3]` `[skill:skill-shell-ia]` |
| `[ON-A5]` supervisor flag raised/changed | In-room announcements via a **live region** (polite, deduped), not an announcement flood. | `[r0 §9.7]` `[src:mdn-live-regions]` `[skill:skill-shell-ia]` |
| `[ON-A6]` the room's own data went stale | Truth bar + degraded banner naming the dependency. | `[r0 A10]` `[cat:trust-attention/tr-degraded]` |

**Alert model.** The room stays **in-room, pull-first** (r0 measured no push channel beyond connection
state `[r0 §4]`). We add a persistent attention strip + an in-room alert log + `aria-live` status,
and **reject** external channels (A9) for this scope — see §5.

---

## 4. Dispositions — every r0 finding

### 4.1 "Present but in the wrong place" (M1–M14)

| # | Finding | Disposition | Reason / citation |
|---|---|---|---|
| M1 | quota/wallet/leases buried in System | **Move** to the Money board | Money is a first-class operator domain `[skill:skill-shell-ia]` `[cat:ia-layout/ia-money-grouping]` `[r0 M1]` |
| M2 | projection health measured, unrendered | **Render** on Health + truth bar | The measured-but-unrendered rail was built to stop false confidence `[r0 M2]` `[skill:skill-trust]` |
| M3 | `control status` packet absent | **Render** the packet on Health/Decisions | ONE dynamic-state contract exists; show it `[r0 M3]` `[r0 A3]` `[cat:trust-attention/tr-degraded]` |
| M4 | registry is an overflow drawer | **Promote** to destination under Decisions | Evidence must be one step from the decision `[r0 M4]` `[S4]` `[cat:trust-attention/tr-lineage]` |
| M5 | docs health inline below fold | **Collapse** to one-line health tile + drill | It is an alertable standing state, not a form `[r0 M5]` `[cat:ia-layout/ia-progressive-disclosure]` `[src:nng-progressive]` |
| M6 | per-card sparkline can't compare | **Remove**; status grid + row sparkline only where comparison is real | The mark has no shared scale/baseline `[r0 M6]` `[src:nng-dash]` `[cat:chart-selection/ch-status-grid]` |
| M7 | Live now duplicates grid | **Merge** as a filter/pin on the fleet grid | Same selectable nodes rendered twice `[r0 M7]` `[cat:ia-layout/ia-board-per-domain]` |
| M8 | hidden System still polls 60 s | **Poll only the active board**; pause hidden surfaces | Unconditional polls waste and surprise `[r0 M8]` `[r0 §3.1]` |
| M9 | rail mirrors `aria-hidden` | **Expose** as a labelled live region with text values | A from-any-board mirror must be hearable `[r0 M9]` `[src:mdn-live-regions]` |
| M10 | registry rows pseudo-buttons | **Fix semantics**: real focusable controls inside cells; keep table roles | `<tr role=button>` announces inconsistently `[r0 M10]` `[src:w3c-tables]` `[src:w3c-apg]` |
| M11 | reinterleave has no affordance | **Add** a queue control with a typed door | Route exists, unreachable `[r0 M11]` `[r0 §9.6]` |
| M12 | recording audit/sweep outside the room | **Surface** on Decisions or System | Recording is part of the act `[r0 M12]` |
| M13 | pipeline strip re-parented | **Own a strip per board** | Context should not jump between boards `[r0 M13]` |
| M14 | native `confirm()` seams | **Replace** with the typed-door primitive | Visual/behaviour seam `[r0 M14]` `[r0 §9.6]` |

### 4.2 "Missing" (A1–A12)

| # | Missing | Disposition | Reason / citation |
|---|---|---|---|
| A1 | single health/alert aggregate | **Build** the attention strip + health board (not one number) | Summarize without collapsing failure modes `[r0 A1]` `[skill:skill-trust]` |
| A2 | projection/latency health | **Build** (same as M2) | `[r0 A2]` |
| A3 | approvals/permanence queue | **Build** Decisions board | `[r0 A3]` `[cat:ia-layout/ia-attention-surface]` |
| A4 | worker/fleet execution health | **Build** on Health (unhealthy workers, throughput) | `[r0 A4]` `[cat:trust-attention/tr-degraded]` |
| A5 | historical trends | **Build** time-series marks on Money/Health | The corpus' strongest mark family `[r0 A5]` `[cat:chart-selection/ch-time-series]` `[src:uplot]` |
| A6 | fleet cost/quality rollup | **Build** fleet rollup + small multiples | `[r0 A6]` `[cat:chart-selection/ch-small-multiples]` `[cat:agent-ops/ao-eval]` |
| A7 | operator architecture diagram | **Build** a theme-aware topology SVG and adopt the orphaned asset | `[r0 A7/§8.3]` `[cat:svg-technique/svg-theme]` `[src:mdn-viewbox]` |
| A8 | cross-session/log search | **Build** bounded search over the retained window on the log-stream surface | `[r0 A8]` `[cat:chart-selection/ch-log-stream]` |
| A9 | notifications (browser/sound/email) | **Reject for this scope**; in-room attention only | The room is the operator's surface; external channels are a separate trust/infra decision `[r0 A9]` |
| A10 | timezone + data-age everywhere | **Build** the truth bar (age/retained-window per panel); keep UTC + local toggle | `[r0 A10]` `[skill:skill-trust]` |
| A11 | auth / multi-operator | **Reject** (unchanged): loopback/tailnet trust boundary | By design `[r0 A11]`; out of campaign scope |
| A12 | mobile treatment for wide tables | **Build** responsive: docked detail collapses to a sheet; tables virtualize and reflow | `[r0 A12]` `[cat:ia-layout/ia-density-ladder]` `[src:webdev-design]` |

---

## 5. Rejected alternatives (with reasons)

1. **React SPA / build-pipeline rebuild.** Rejected: the room's no-build guardrail is a measured
   contract `[r0 §9.8]`; the component kits assume React+Tailwind+Recharts `[cat:frameworks/fw-react-kits]`
   `[src:tremor]` `[src:shadcn]`. Revisit only if contributor count changes.
2. **Command-palette-only navigation.** Rejected: palettes are used *alongside* a visual board
   `[src:linear]` `[src:railway]` `[src:warp]`, never as the only IA `[skill:skill-shell-ia]`.
3. **One mega-dashboard.** Rejected: board-per-domain dominates ops IA and keeps money/health from
   drowning in work state `[cat:ia-layout/ia-board-per-domain]` `[src:grafana]` `[src:datadog]`.
4. **Keep per-card sparklines.** Rejected: no shared scale/baseline, so they cannot compare `[r0 M6]`;
   prefer a status grid + one row-level sparkline `[src:nng-dash]` `[cat:chart-selection/ch-status-grid]`.
5. **Canvas/SVG monotheism.** Rejected: ECharts documents the tradeoff — SVG for a few
   marks/accessibility, canvas for many/high-frequency `[src:echarts-canvas]`; keep both
   `[skill:skill-charts]`.
6. **Dark-only theme.** Rejected: dark needs desaturated surfaces and a real light path
   `[src:nng-dark]`; plus a forced-colors path `[src:mdn-forced-colors]` `[cat:color-motion/cm-dark-first]`.
7. **A single collapsing health score.** Rejected: it hides distinct failure modes `[r0 A1]`
   `[skill:skill-trust]`; show named failures on the strip.
8. **Keep registry/health/quota in System overflow.** Rejected: evidence-at-hand is criterion S4 and
   the r0 cost ranking puts these at HIGH `[r0 M1/M2/M4]`.
9. **D3 for every chart.** Rejected: imperative cost is justified only for bespoke marks
   `[cat:frameworks/fw-d3]`; standard marks use a small library `[cat:frameworks/fw-declarative]`.
10. **External alert channels (browser/sound/email).** Rejected for this scope (A9); adds a new trust
    boundary, and the measured gap is in-room attention, not delivery `[r0 A9/§4]`.

---

## 6. Concrete layout proposition

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  RAIL  ⌂ Work ▤ Money ✚ Health ⚖ Decisions      ⌘K commands   ● status  $$$  │
├──────────────────────────────────────────────────────────────────────────────┤
│  ATTENTION STRIP   ▲ 2 failed runs · ▣ 1 approval · ⧗ chroma lag 3 · ⚠ docs  │  ← live region
├───────────────────────────────────────────────┬──────────────────────────────┤
│  BOARD (active domain)                        │  DOCKED DETAIL               │
│                                               │  ─ selected node ─           │
│  Work:      keyed fleet grid + queue          │  status · provenance         │
│  Money:     spend/burn line · windows/wallet  │  transcript (follow/pause)   │
│             lease reservations · budgets      │  lineage tree · per-step cost│
│  Health:    degraded · workers · projections  │  typed safe-actions          │
│  Decisions: approvals · promotable · registry │                              │
│                                               │  (narrow: modal sheet)       │
├───────────────────────────────────────────────┴──────────────────────────────┤
│  TRUTH BAR   age 4s · retained window · provenance [M/E/U] · tz UTC|local    │
└──────────────────────────────────────────────────────────────────────────────┘
   System overflow (gear): config · recording · advanced — secondary only
```

- **Navigation:** a persistent rail of domains + `⌘K` palette as accelerator `[cat:ia-layout/ia-command-palette]`;
  tabs/panes for co-resident surfaces `[cat:ia-layout/ia-tab-bar]`.
- **Detail:** docked right column that survives live updates, collapsing to a modal sheet on narrow
  viewports `[cat:ia-layout/ia-master-detail]` `[r0 A12]`.
- **Density:** comfortable/compact ladder, persisted; selection/focus preserved across switches
  `[cat:ia-layout/ia-density-ladder]` `[src:webdev-design]` `[src:every-layout]`.
- **Disclosure:** long-tail surfaces behind progressive disclosure, never decision-critical ones
  `[cat:ia-layout/ia-progressive-disclosure]` `[src:nng-progressive]`.

---

## 7. Concrete chart proposition

| Operator question | Mark | Library | Citation |
|---|---|---|---|
| Money/quality over time (`ON-G4`,`ON-D6`) | line/area + inline sparkline | uPlot (small/streaming) or ECharts | `[cat:chart-selection/ch-time-series]` `[src:uplot]` `[src:echarts]` |
| Fleet/node state (`ON-G3`,`ON-G7`) | status grid / heatmap | hand SVG or ECharts | `[cat:chart-selection/ch-status-grid]` `[src:nng-dash]` |
| Bounded quantity: queue/phase (`ON-G2`) | gauge/progress | hand SVG | `[cat:chart-selection/ch-gauge]` `[src:nvitop]` `[src:btop]` |
| Large sets: registry/cells/events (`ON-D4`) | virtualized sortable table | hand/vanilla + `content-visibility` | `[cat:chart-selection/ch-table]` `[src:nng-tables]` `[src:webdev-contentvis]` |
| Live output (`ON-D1`) | bounded log stream, follow/pause/filter | hand | `[cat:chart-selection/ch-log-stream]` `[src:railway]` |
| Multi-step run (`ON-D1`,`ON-D6`) | timeline/waterfall | hand or ECharts | `[cat:chart-selection/ch-timeline]` `[src:langfuse-obs]` |
| Cross-group compare (`ON-G7`) | small multiples *(thin evidence)* | any | `[cat:chart-selection/ch-small-multiples]` |
| Many live marks (`RQ-C5`) | canvas + decimation, lazy panels | uPlot/ECharts | `[cat:chart-selection/ch-perf]` `[src:echarts-canvas]` |

Chart types with a **default**: status grid at a glance, line/sparkline over time, gauge for
bounded state, table for sets, waterfall for runs. **Dropped:** threshold-band and small-multiple
clusters are below/at the evidence bar `[tax:thin-viz-threshold-bands]` — use them only as
text+band cues where the question forces it.

---

## 8. Concrete SVG proposition

- **Topology diagram (adopted, `A7`).** Rewrite the orphaned `static/architecture.svg` `[r0 §8.3]` as a
  **theme-aware flow**: `queues → launch broker → workers → cells → sessions → knowledge projections`.
  Author with `viewBox` for scale `[src:mdn-viewbox]`, colors from `currentColor`/custom properties
  `[src:mdn-custom-props]` `[src:smashing-svg]`, grouped + labelled with real `<text>`
  `[src:svg-tutorial]`, a `<title>`/`<desc>` and `role="img"` (or `aria-hidden` if decorative)
  `[src:cstricks-accessible]`. Link it from the Health board (topology explains lag).
- **Micro-visuals.** Sparkline, gauge, status glyph and flow line as small **SVG+CSS** pieces
  (path + `stroke-dasharray`/gradient), not a JS chart runtime `[cat:svg-technique/svg-micro]`
  `[src:cstricks-line]` `[src:svg-tutorial]`.
- **Accessibility.** Every informative SVG carries a text alternative; charts get a textual
  equivalent `[src:wcag-quickref]` `[src:cstricks-accessible]`; forced-colors safe
  `[src:mdn-forced-colors]`.

---

## 9. Visual system (tokens, color, type, motion)

- **Tokens.** One CSS-custom-property layer (surface/elevation/accent/status/type); derive variants
  with `color-mix()` `[src:mdn-custom-props]` `[src:mdn-color-mix]`; name by convention
  `[src:smashing-tokens]`.
- **Color.** Few, colorblind-safe status hues; **never color alone** (shape/label always)
  `[r0 §9.5]` `[cat:color-motion/cm-status-color]` `[src:webdev-contrast]` `[src:nng-color]`;
  contrast ≥ 4.5:1 body / 3:1 large `[src:wcag-contrast]`.
- **Theming.** Dark-first + a real light theme from the same tokens + forced-colors
  `[cat:color-motion/cm-dark-first]` `[src:nng-dark]` `[src:mdn-forced-colors]`.
- **Type.** Small scale, tabular numerals for dense data `[cat:color-motion/cm-type]` `[src:butterick]`
  `[src:smashing-type]`; one icon family, labelled where ambiguous `[cat:color-motion/cm-icon]`
  `[src:nng-icon]` `[src:mdn-use]`.
- **Elevation.** Structural surface ladder, not decoration `[cat:color-motion/cm-elevation]`
  `[src:refactoringui]`.
- **Motion.** Short state-change motion only, spring/ease `[cat:color-motion/cm-motion]`
  `[src:josh-spring]` `[src:nng-micro]`; honor `prefers-reduced-motion`
  `[cat:color-motion/cm-reduced-motion]` `[src:mdn-reduced-motion]` `[src:webdev-reduced]`.
- **Accent economy.** One accent at a time `[cat:color-motion/cm-accent]` `[src:vercel-geist]`.
- **A11y live.** Attention changes announce via polite live regions, deduped
  `[src:mdn-live-regions]` `[src:webdev-a11y]`.

---

## 10. No-regression contract + drift reconciliation

The direction must preserve every measured guardrail `[r0 §9]`: two-layer reconciliation `[§9.1]`, one
selected event stream `[§9.2]`, keyed write-on-change lists `[§9.3]`, no HTML-string rendering
`[§9.4]`, two-axis status language `[§9.5]`, mutation trust boundary + typed doors `[§9.6]`,
accessible chrome (hidden-not-CSS, focus traps, reduced motion) `[§9.7]`, and **no build step**
`[§9.8]`.

It must also reconcile the measured drift `[r0 §8]`: the route count is **34 across 7 categories**
(not 28/31/32) `[r0 §8.1]`; the design authority actually lives at
`docs/website/control_room_ui/design.md` `[r0 §8.2]`; `architecture.svg` is orphaned and is **adopted**
by §8 `[r0 §8.3]`; the route-list docstring must gain the recording category `[r0 §8.4]`.

---

## 11. Carry-forward to r6/r7

- **r6a (entailment):** re-check every `[src:*]` and `[skill/cat]` citation above against the stored
  records; flag any claim resting on a single family (the agent-ops and a few craft/trust items).
- **r6b (design):** attack §6/§9 for genericness — is the Instrument Panel actually distinctive, or a
  Grafana-shaped template?
- **r6c (IA):** attack §3 for ranking — does the glance screen truly answer `ON-G1..G7` in cost order?
- **r7 (brief):** tighten §6/§7/§8/§9 into acceptance criteria (scope, layout, chart set, SVG set,
  motion budget, accessibility bar, no-regression), using the language of `[r0 §9]` and `[r0 §11]`.

---

## Appendix — sources cited

| Tag | Family | sha256 (16) | URI |
|---|---|---|---|
| `[src:linear]` | dashboards | `eb0e0bc396ddd962` | https://linear.app/ |
| `[src:vercel]` | dashboards | `c26a33d2b08d2b60` | https://vercel.com/ |
| `[src:vercel-geist]` | dashboards | `74aeb67b13ba6192` | https://vercel.com/geist/colors |
| `[src:grafana]` | dashboards | `789c3cf84b24905d` | https://grafana.com/docs/grafana/latest/dashboards/ |
| `[src:datadog]` | dashboards | `10b7d1ed79891712` | https://docs.datadoghq.com/dashboards/ |
| `[src:sentry]` | dashboards | `78abfbfa297e2a6d` | https://docs.sentry.io/product/dashboards/ |
| `[src:railway]` | dashboards | `fb3d9950d9d1705b` | https://docs.railway.com/ |
| `[src:fly]` | dashboards | `302af27b202b0d9a` | https://fly.io/docs/ |
| `[src:supabase]` | dashboards | `a62f83704d3f940d` | https://supabase.com/docs |
| `[src:stripe]` | dashboards | `255311919f90098f` | https://stripe.com/docs |
| `[src:posthog]` | dashboards | `923433f300af8023` | https://posthog.com/docs/product-analytics |
| `[src:langfuse-obs]` | agentops | `0a1784a27f750267` | https://langfuse.com/docs/observability/overview |
| `[src:langfuse-cost]` | agentops | `245019da24ca609e` | https://langfuse.com/docs/analytics/overview |
| `[src:langfuse-scores]` | agentops | `4667e20442936138` | https://langfuse.com/docs/scores/overview |
| `[src:langsmith]` | agentops | `216cc0ec88b4a616` | https://docs.smith.langchain.com/ |
| `[src:langsmith-eval]` | agentops | `60381850f2ec94ec` | https://docs.smith.langchain.com/evaluation |
| `[src:braintrust]` | agentops | `943a46764e1dce65` | https://www.braintrust.dev/docs/guides/evals |
| `[src:helicone]` | agentops | `20ead7ec1d1155ef` | https://docs.helicone.ai/ |
| `[src:arize]` | agentops | `03f451e9e86f8ade` | https://docs.arize.com/phoenix |
| `[src:weave]` | agentops | `d08fed9663231367` | https://weave-docs.wandb.ai/guides/tools/playground |
| `[src:uplot]` | dataviz | `c3a34c9200af26ab` | https://github.com/leeoniya/uPlot |
| `[src:echarts]` | dataviz | `caa87df6c6cfc387` | https://echarts.apache.org/en/index.html |
| `[src:echarts-aria]` | dataviz | `dfb00439e589043e` | https://echarts.apache.org/handbook/en/best-practices/aria/ |
| `[src:echarts-canvas]` | dataviz | `f7498c71e2215e1a` | https://echarts.apache.org/handbook/en/best-practices/canvas-vs-svg/ |
| `[src:vega-lite]` | dataviz | `2064f3499486a4bb` | https://vega.github.io/vega-lite/ |
| `[src:d3]` | dataviz | `a2d77a5b707ffb7d` | https://d3js.org/ |
| `[src:nivo]` | dataviz | `7fbbcfe5789d6603` | https://nivo.rocks/line/ |
| `[src:tremor]` | dataviz | `ad8fe3598ecb31d8` | https://www.tremor.so/ |
| `[src:shadcn]` | dataviz | `b34430159fcfd06c` | https://ui.shadcn.com/charts |
| `[src:warp]` | cli | `b5c3555b32cf6350` | https://www.warp.dev/ |
| `[src:ghostty]` | cli | `c2dd13ab48151194` | https://ghostty.org/ |
| `[src:textual]` | cli | `5fe641dcb2a0ba93` | https://textual.textualize.io/ |
| `[src:nvitop]` | cli | `f0d68d37b1d8bc32` | https://github.com/XuehaiPan/nvitop |
| `[src:btop]` | cli | `f6d5e898349bb60c` | https://github.com/aristocratos/btop |
| `[src:fzf]` | cli | `69fcc77a700dd447` | https://github.com/junegunn/fzf |
| `[src:lazygit]` | cli | `bcba07779b22b8e0` | https://github.com/jesseduffield/lazygit |
| `[src:k9s]` | cli | `1a478e7877c824fe` | https://github.com/derailed/k9s |
| `[src:kitty]` | cli | `a3d50cc44562b66c` | https://sw.kovidgoyal.net/kitty/ |
| `[src:mdn-viewbox]` | craft | `c953bc2f52e375d0` | https://developer.mozilla.org/en-US/docs/Web/SVG/Attribute/viewBox |
| `[src:mdn-use]` | craft | `4ce5f6172aae264a` | https://developer.mozilla.org/en-US/docs/Web/SVG/Element/use |
| `[src:mdn-reduced-motion]` | craft | `e3fe57980976a907` | https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion |
| `[src:mdn-forced-colors]` | craft | `ebbddff1da6be245` | https://developer.mozilla.org/en-US/docs/Web/CSS/@media/forced-colors |
| `[src:mdn-custom-props]` | craft | `a91bb30d7c48d173` | https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties |
| `[src:mdn-live-regions]` | craft | `11655ccb46931ebe` | https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions |
| `[src:mdn-color-mix]` | craft | `3ab0045d33f37663` | https://developer.mozilla.org/en-US/docs/Web/CSS/color_value/color-mix |
| `[src:webdev-a11y]` | craft | `abe7da4e372ad808` | https://web.dev/learn/accessibility/ |
| `[src:webdev-design]` | craft | `64d16f4d7158c427` | https://web.dev/learn/design/ |
| `[src:webdev-contrast]` | craft | `aded09c8b9cfa9b7` | https://web.dev/articles/color-and-contrast-accessibility |
| `[src:webdev-reduced]` | craft | `00c6f4b49de13c1b` | https://web.dev/articles/prefers-reduced-motion |
| `[src:webdev-contentvis]` | craft | `7aa4893ce08fa550` | https://web.dev/articles/content-visibility |
| `[src:nng-tables]` | craft | `7bb44646100f45ed` | https://www.nngroup.com/articles/data-tables/ |
| `[src:nng-progressive]` | craft | `704fe924fed0ccae` | https://www.nngroup.com/articles/progressive-disclosure/ |
| `[src:nng-response]` | craft | `ffa84c46b1dc9665` | https://www.nngroup.com/articles/response-times-3-important-limits/ |
| `[src:nng-skeleton]` | craft | `ae670dfbb428a6ce` | https://www.nngroup.com/articles/skeleton-screens/ |
| `[src:nng-color]` | craft | `def697856da898b9` | https://www.nngroup.com/articles/color-enhance-design/ |
| `[src:nng-dark]` | craft | `effad3bad3f8f8d5` | https://www.nngroup.com/articles/dark-mode/ |
| `[src:nng-micro]` | craft | `e70316fbafc50556` | https://www.nngroup.com/articles/microinteractions/ |
| `[src:nng-icon]` | craft | `1d9e07b7547bfde0` | https://www.nngroup.com/articles/icon-usability/ |
| `[src:nng-dash]` | craft | `b665ad15d558dbd6` | https://www.nngroup.com/articles/dashboards-preattentive/ |
| `[src:refactoringui]` | craft | `d89a448704f5301e` | https://www.refactoringui.com/ |
| `[src:smashing-svg]` | craft | `b8bc0e988e39ee25` | https://www.smashingmagazine.com/2025/11/smashing-animations-part-6-svgs-css-custom-properties/ |
| `[src:smashing-aria]` | craft | `44d54c5850d776a2` | https://www.smashingmagazine.com/2025/06/what-i-wish-someone-told-me-aria/ |
| `[src:smashing-type]` | craft | `88846b6feced9773` | https://www.smashingmagazine.com/2023/10/choose-typefaces-fintech-products-guide-part1/ |
| `[src:smashing-tokens]` | craft | `5786269a0bca7790` | https://www.smashingmagazine.com/2024/05/naming-best-practices/ |
| `[src:cstricks-svg]` | craft | `45906cdcaa5d19ce` | https://css-tricks.com/mega-list-svg-information/ |
| `[src:cstricks-accessible]` | craft | `03dcc0382b1f0621` | https://css-tricks.com/accessible-svgs/ |
| `[src:cstricks-line]` | craft | `5b1adeb30b08f494` | https://css-tricks.com/svg-line-animation-works/ |
| `[src:svg-tutorial]` | craft | `ea201b4404388cbe` | https://svg-tutorial.com/ |
| `[src:wcag-quickref]` | craft | `ed61b139cdf28bff` | https://www.w3.org/WAI/WCAG22/quickref/ |
| `[src:wcag-contrast]` | craft | `3352aaf477e97391` | https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html |
| `[src:w3c-tables]` | craft | `627865eeda93dba0` | https://www.w3.org/WAI/tutorials/tables/ |
| `[src:w3c-apg]` | craft | `67aa84429d27fba3` | https://www.w3.org/WAI/ARIA/apg/patterns/ |
| `[src:inclusive-components]` | craft | `ac8dbab4744ac5bf` | https://inclusive-components.design/ |
| `[src:every-layout]` | craft | `4b5a5ab9eabd35d8` | https://every-layout.dev/ |
| `[src:josh-spring]` | craft | `71b1e7fa215f3d5a` | https://www.joshwcomeau.com/animation/a-friendly-introduction-to-spring-physics/ |
| `[src:butterick]` | craft | `ef40706eeb33417f` | https://practicaltypography.com/summary-of-key-rules.html |

*Full 64-char hashes and extracted text live in `experiments/research/control_room/sources/` and
`sources.jsonl`; facet records carry the same hash in `corpus/*.jsonl`.*
