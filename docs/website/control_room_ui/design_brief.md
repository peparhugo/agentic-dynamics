---
status: superseded
superseded_by: docs/website/control_room_ui/design_determination.md
---
# Control Room UI — design brief by process: evidence, criteria, candidates, and determination

> **Superseded as a determination by `design_determination.md` (the single accepted decision).**
> Parts I–III and V remain the evidence pack and are citable; Part IV's 4.48 selection and
> Part VI's open questions are superseded — the final determination folds in the adversarial
> findings and carries the corrected score vector.

> **Phase:** determination (`wt_ui_determination`). **Question:** what should the Control Room's
> next design be, decided by process — evidence, then weighted criteria, then three candidate
> directions, then adversarial review, then a final determination.
>
> **Inputs (read-only):** the old dashboard at commit `1457b9299`; the accepted direction
> (`docs/research/control_room_direction.md`, status: accepted); the v2 reference synthesis
> (`docs/research/control_room_ui_reference_synthesis_v2.md` @ `87559ef66`, on branch
> `wt_facelift_review`); the parity inventory
> (`experiments/research/control_room/parity_inventory.json`, `control-room-parity-inventory/v1`);
> the Control Room tree at `HEAD` (`0a29f28b4` = `main`) and the unmerged new-resting-screen branch
> (`wt_room_new` @ `c06b158a7`).
>
> **Claim discipline.** `[M]` measured in this repository (a `file:line` anchor); `[C]` computed
> (arithmetic over `[M]`); `[X]` external observation at the pinned commit/URL (v2 synthesis
> mechanism IDs + anchors); `[P]` policy — a local/controller decision, never external consensus.
> The old dashboard's anchors are against `1457b9299`; current-tree anchors are against `HEAD`.

---

## 0. Executive summary

- The **old dashboard** (`1457b9299`) is a seven-board, no-page-scroll, three-column cockpit with
  **235 unique ids**, **44 registered routes**, a burn trace, per-cell sparklines, and every
  per-worker control. It was rejected once as "a layer on top of the clunk" *as a layout to copy*
  (`workflows/repository/control_room_ui_rebuild.yaml:24-29`), but it is the repository's canonical
  **working set** and the parity reference (`docs/research/control_room_direction.md:301-303`).
- The **current room** (`HEAD`) kept the old capabilities by re-housing them into a workbench of 13
  lenses (`apps/control_room/static/parity.js`), added four SVG trend charts
  (`apps/control_room/static/charts.js`), and enforces a no-scroll glance contract
  (`apps/control_room/static/index.html:1-68`). Its measured weakness is that two of the brief's
  four elements are not delivered: **scroll** (the resting room forbids page scroll) and **measured
  step durations** (the workforce lens renders `queue_wait`/`service_time`/`first_token` as
  `unknown` despite the writers now existing — `apps/control_room/static/parity.js:491-570`).
- The **brief** (work item verbatim) asks for **scroll, charts/SVG, workforce, step durations, old
  dashboard as base**. The evidence shows *scroll* and *charts/SVG* are achievable with existing
  routes; *workforce* and *step durations* require exposing already-measured ledger fields (`G-40`
  timings, `G-41` cost split) through a read-only route; and *old dashboard as base* is satisfied
  as working-set fidelity via the parity inventory (not DOM reuse).
- **Determination:** select **Candidate C — the scroll-synthesized instrument**: a single scrolling
  page whose first viewport preserves the no-scroll glance contract (`ON-G1..G7`) and whose body
  stacks the old dashboard's full working set as dense scrollable bands, with real SVG step/phase
  duration, cost, and throughput charts, and a workforce band built from the now-measured ledger
  timings. Weighted score **4.48/5** vs 3.79 (current room) and 3.27 (restore old boards).

---

# Part I — Evidence pack

## 1. Evidence (a): the old dashboard's boards/pages/charts inventory (`1457b9299`) `[M]`

All anchors in this section are against commit `1457b9299` (the "old room" / parity reference).
Path prefix `static/` = `apps/control_room/static/`; `routes/` = `apps/control_room/routes/`.

### 1.1 Asset inventory

| File | Lines | Role |
|---|---|---|
| `static/index.html` | 847 | Static shell: command rail, destinations nav, detail surface, 8 boards, System sheet |
| `static/app.js` | 4109 | Data layer: all fetch/EventSource/poll/render/mutation logic |
| `static/shell.js` | 438 | Chrome only: board visibility, theme, density, region adoption, System sheet; issues no fetch, opens no EventSource (`shell.js:8-10`) |
| `static/board-fleet.js` | 228 | Pure functions: lifecycle/attention vocabularies, filtering/sorting/counts (`board-fleet.js:45-68`) |
| `static/detail-sheet.js` | 334 | Transversal Detail surface, focus trap, drag-to-dismiss (`detail-sheet.js:10`) |
| `static/control-room-core.js` | 285 | Pure parse/normalize helper (transcript, telemetry reconcile, burn rate, EventSource replace) |
| `static/keyed-list.js` | 138 | Keyed reconciliation + write-on-change DOM helper |
| `static/style.css` | 2965 | Styling (dark-only at this commit) |
| `static/architecture.svg` | — | Present but **referenced by no static file** at this commit (docs/workflow specs only) |

Script order (`index.html:840-845`): `control-room-core → keyed-list → board-fleet → shell →
detail-sheet → app`.

### 1.2 Every board / page / destination

Destinations constant: `["fleet","status","flags","sessions","routing","operations","surfaces"]`
(`shell.js:26`). System is an overflow sheet, not a destination (`shell.js:25`). Exactly one board
is visible at a time; inactive boards carry `hidden` (`index.html:364-366`).

| # | Board | id / `data-board` | `index.html` | Purpose | Routes consumed |
|---|---|---|---|---|---|
| 1 | **Fleet** (home) | `#board-fleet` / `fleet` | 367-468 | Cell grid, pipeline strip, Docs health, LIVE NOW, filters, counts | `GET /api/matrix` (5 s), `GET /api/status` (SSE), `GET /api/events/<cell>` (SSE selected), `GET /api/docs-health` (60 s), `POST /api/docs-health/approve` |
| 2 | **Status** | `#board-status` / `status` | 471-516 | Money & throughput: spend, burn, tokens, running, Redis, expanded pipeline strip | same `/api/matrix` snapshot (no separate fetch) |
| 3 | **Flags** | `#board-flags` / `flags` | 519-541 | Supervisor alert queue, source provenance, delay notice | `GET /api/flags?limit=50` (5 s), `POST /api/flags/<id>/steer`, `POST /api/flags/<id>/interrupt` |
| 4 | **Sessions** | `#board-sessions` / `sessions` | 544-652 | Design sessions + Claude background sessions | `GET/POST /api/design-sessions` (10 s), `…/<id>/spec|input|interrupt|save|run`; `GET/POST /api/claude-agents`, `…/<id>/logs|stop|respawn|rm|steer`, `…/daemon`, `…/daemon/stop` |
| 5 | **Routing** | `#board-routing` / `routing` | 655-676 | Lazy read-only routing recommendations + strategy simulation | `GET /api/routing` |
| 6 | **Operations** | `#board-operations` / `operations` | 678-698 | The "one packet" operational snapshot + run-detail drawer | `GET /api/operations`, `GET /api/runs/<run_id>` |
| 7 | **Surfaces** | `#board-surfaces` / `surfaces` | 700-713 | Read-model panels, each independent | `/api/quality`, `/api/value`, `/api/arms/compare`, `/api/queue/sla`, `/api/escalations`, `/api/batch`, `/api/energy` (`app.js:3284-3292`), `/api/stories/<name>/arc` |
| — | **System** (overflow) | `#system-sheet` + `#system-nav` | 130-133, 725-835 | Registry + Queue actions + Subscription usage | `GET /api/registry`, `GET /api/registry/<entity_id>`, `POST /api/experiments`, `GET /api/subscription-usage` |

**Transversal Detail surface** (`#detail-surface`, `index.html:146-358`) — docked right column
(≥760 px) / modal bottom sheet (<760 px), never arrived at cold. Four mutually exclusive control
panels toggled by selection type (`app.js:1437-1525`): Cell (`#cell-control-panel`, 206-229),
Supervisor (231-271), Design (273-324), Claude agent (326-355). Single transcript feed
`#transcript-feed` (188) with `#follow-button`/`#pause-button`/`#clear-button` (184-186) and
`#jump-live` (191). Header glance: `#transcript-title`, `#selected-status`, `#selected-phase`,
`#selected-stream-state`, `#selected-cost`, `#selected-tokens` (158-171).

**Board sub-regions:** Fleet `#fleet-total`/`#matrix-age` (371-373), single `#pipeline-stages`
(381) **re-parented** between Fleet and Status by `adoptRegions` (`shell.js:102-109`), Docs health
`#docs-health` (394-420), Live Now `#live-now` (431-441); Flags `#supervisor-rail` (528-535);
Operations `#run-detail-drawer` (685-696); System registry/queue/usage (745-835).

### 1.3 Every chart / SVG / visual mark

| Mark | Definition / render | Notes |
|---|---|---|
| **Burn trace** (full-width cost polyline) | SVG host `index.html:494` (`#burn-trace`, `viewBox="0 0 240 48"`, `role="img"`); `renderBurn` `app.js:260-294`; `polyline.cost-line` `app.js:289-292` | 60-sample bound (`app.js:26`) |
| **Per-cell sparkline** | `createSparkline` `app.js:306-355`; SVG `viewBox="0 0 180 36"` `app.js:315-317`; token bars `app.js:323-331`; cost polyline `app.js:338-344` | one `rect` per sample, last 12; replace-on-change `app.js:485-490` |
| **Status glyphs + word** (never colour-only) | `applyStatusWord` `app.js:212-218`; lifecycle vocab `board-fleet.js:45-54` (○ ◔ ✓ × ◷ ↻ ◻ ?); attention vocab `board-fleet.js:64-68` (▲ ■ ◆) | cards/flags/detail/claude |
| **Destination glyph SVGs** | 8 inline `svg.icon-svg` `index.html:100-131` | decorative `aria-hidden` |
| **Pipeline-stage cards** (visual progress strip) | `#pipeline-stages` `index.html:381-385`; `renderPipelineStages` `app.js:718-728`; `stageCard` `app.js:696-715`; `pipelineStageClass` `app.js:684-693` | no `<progress>`/bar element exists |
| **Phase badge** (i-of-N + name + age) | `phaseLabel` `app.js:494-500`; `phaseBadgeLabel` `app.js:509-514` | |
| **Mirror values** (rail telemetry) | `index.html:74-77`; sync `shell.js:342-375` | |
| Skeleton cards | `index.html:463-465`; removed on first render `app.js:624` | loading state only |

No chart library, no `<canvas>`, no `<progress>`; the only SVG-drawing functions are `renderBurn`
and `createSparkline` (`app.js:260,306`). `architecture.svg` is unused by the dashboard.

### 1.4 Every interaction (handler + anchor)

| Group | Interactions | Anchors |
|---|---|---|
| Navigation/chrome (`shell.js`) | destination click `showBoard` 295-297/140-161; System open/close 299-307/241-268; scrim 319-322; Escape/focus-trap 326-332/214-231; theme `setTheme` 309-311/67-76; density `setDensity` 313-316/82-92; drawer label sync `syncToggleLabel` 179-193; rail mirrors `bindMirrors` 357-375; on-demand form reveal `revealForm` 385-392; region adoption `adoptRegions` 102-109; lazy board auto-load 119-137 | |
| Detail (`detail-sheet.js`) | open `open` 267-270/124-143; close 272/146-158; drag-to-dismiss 244-256/204-241; prose expand `toggleProse` 259-262; Escape/tab trap 290-293/106-121; mobile anchor 299-309; breakpoint re-eval 313-326 | |
| Fleet (`app.js`) | card drill-down `selectCell` 3731-3735/1802-1837; filter chips (All/Live/Running/Risk) 3743-3753; search `#cell-search` 3754-3757; docs-health approve 922-964/903-919; watch/detach 3758-3761/1753-1799; copy session 3762-3771; pause/resume 3772-3787; follow 3788-3794; scroll→follow-off 3795-3802; jump-live 3803-3809; clear view 3810-3816; stream replay boundary `replay_complete` `app.js:1771`; queue enqueue/clear 3861-3864/3891-3895 | |
| Flags/supervisor | flag select `selectSupervisorFlag` 3726-3730; steer `submitSupervisorSteer` 3642/2607-2641; interrupt typed door `openSupervisorInterruptDoor` 3653/2644-2653, `confirmSupervisorInterrupt` 3669/2664-2694 (phrase `INTERRUPT <session_id>`, `index.html:257-269`) | |
| Sessions — design | start `openDesignStart`/`startDesignSession` 3671-3677/2782-2822; input `submitDesignInput` 3678-3682/2825-2851; interrupt 3683-3704; save `saveSpec` 3706/2854-2892; run `runWorkflow` 3707/2895-2942; draft poll `loadDraftState` 1683-1744 | |
| Sessions — Claude | roster select `selectClaudeAgent` 3719-3723; start 3909-3941; stop/respawn/rm/steer 3943-4033; external log fetch 4038-4055; daemon stop two confirms 4059-4083 | |
| Routing/Ops/Surfaces/System | routing drawer + refresh 3817-3835/2222-2265; registry drawer/filter/lineage 3837-3860/2413-2506; usage refresh 3836/2271-2405; queue clear typed door 3872-3895 (`CLEAR QUEUE`); operations refresh + run detail 3609-3626/3033-3213; surfaces refresh + story arc 3627-3637/3294-3605 | |
| Pollers (`app.js`) | matrix 5 s `4101`; flags 5 s `4102`; design 10 s `4103`; claude roster 10 s `4104`; daemon 15 s `4105`; usage 60 s `4106`; docs 60 s `4107`; clock 1 s `4108`; status SSE `connectStatusStream` 2136-2165 | |

**"One-way door" typed-confirmation actions** (the irreversible pattern): Supervisor Interrupt
(`INTERRUPT <session_id>`, `flags.py:58-84`) and Clear queue (`CLEAR QUEUE`,
`telemetry.py:395-425`). Other irreversible actions use plain `confirm()`: daemon stop, Claude
stop/rm, design interrupt, spec overwrite.

### 1.5 Route surface consumed (`1457b9299`)

**44 route registrations** at this commit (measured). `app.js` fetches/EventSources at lines
`879, 907, 1689, 1759/1762, 2040, 2084, 2138, 2226, 2286, 2425, 2492, 2517, 2543, 2565, 2586,
2714, 2748, 2773, 3042, 3194, 3301, 3594, 4044`. Registered but **not** consumed by the static
UI at this commit: `POST /api/queue/reinterleave`, `GET /api/recording-audit`,
`POST /api/recording-sweep/run`, `GET /api/projections` (projection lag reached the UI only
through `/api/operations`).

### 1.6 Data fields rendered

Spend (`telemetry.reported_cost`, `history_capped`), burn (rolling 60 s from samples), input/output
tokens, running count, Redis state, per-stage counts (`total/done/running/queued/failed/retry/
timeout`), phase i-of-N + age, per-card latest cost + sparkline samples, docs-health condition/
axes/proposal, supervisor flags (`session_id,title,model,status,why,at,flag_id,review.*`),
design draft/validation/matrix/capabilities, claude agent+daemon, registry rows + lineage,
subscription usage (windows, deepseek totals/days, wallet, cache), operations packet
(`active_runs,promotable_runs,attention,degraded,projection_lag,safe_actions`), run detail
(`run,attempts,gates,approvals,commands`), seven surface panels, routing tables, transcript rows.
Full per-field anchors are in the working notes; the load-bearing ones for this brief are:
`#fleet-counts`/`statusCounts` (`board-fleet.js:146-161`), `renderPipelineStages`
(`app.js:718-728`), `renderRunDetail` attempts (`app.js:3231-3280`), SLA `recent_completions`
(`app.js:3434-3465`).

### 1.7 Measured absences at `1457b9299` `[C]`

- **No workforce step-timing surface at all.** `queue_wait_ms`, `service_time_ms`, `first_token_at`,
  `started_at`/`ended_at` have no view (`docs/research/control_room_ux_foundation.md:346-354`).
- **No scrolls are bounded per-board only**; the page is composed of one visible board, so the
  old room *does* scroll within a board and its detail drawer.
- **No chart runtime / no canvas / no `<progress>`.** Progress is a stage strip + phase badge.
- `architecture.svg` is dead weight (unreferenced).
- **Per-card sparklines** exist (old room) and are exactly what the accepted direction later
  removes for want of a shared scale (`docs/research/control_room_direction.md:471,559`).

### 1.8 The parity inventory (`1457b9299` → facelift) `[M]/[C]`

`experiments/research/control_room/parity_inventory.json` (`control-room-parity-inventory/v1`,
built by `experiments/research/control_room/build_parity_inventory.py`):

| Field | Value |
|---|---|
| `summary.old_unique_ids` | **235** |
| `summary.facelift_unique_ids` | **24** |
| `summary.ids_dropped_by_facelift` | **234** (single shared id: `theme-toggle`) |
| `summary.old_routes` / `facelift_routes` / `routes_dropped_by_facelift` | 34 / 36 / **0** |
| `summary.old_consumed_feeds` / `facelift_consumed_feeds` | 28 / **2** |
| `items` | **235** (dispositions: 214 `re-house`, 20 `replace-with-reason`, 1 `preserve`) |
| `endpoints` | 34 (30 `re-house`, 3 `replace-with-reason`, 1 `preserve`) |
| `capabilities` | 10 |
| Surfaces with **no** old item (net-new) | `L-COMPOSITION, L-FLEET, L-HEALTH, L-WORKFORCE, R3c, R4c, R4d, SYSTEM` |

**Reading:** the facelift left the server capability intact (0 routes dropped) but removed the
operator's access (2 of 28 feeds consumed). The old room is therefore the **working-set baseline**,
not a layout to copy.

---

## 2. Evidence (b): the v2 synthesis — mechanisms and dispositions `[X]`

Source: `docs/research/control_room_ui_reference_synthesis_v2.md` @ `87559ef66` (branch
`wt_facelift_review`; **not on `main`**). It *extends* v1
(`docs/research/control_room_ui_reference_synthesis.md`) and presupposes the accepted direction
(`docs/research/control_room_direction.md`). Section anchors below are v2 §.

### 2.1 Method and pins (v2 §0, §2, §11)

Sweep → pin → extract → dispose → reconcile. Twelve repos cloned, nine read deeply. Pins (v2 §2,
§11): `[src:temporal-ui]` @ `542fa634…`; `[src:hatchet]` @ `315d43a7…`; `[src:dagu]` @
`2635b927…`; `[src:langfuse]` @ `6d298ec5…`; `[src:openhands]` @ `28464621…`; `[src:uptime-kuma]`
@ `3afdc9ca…`; `[src:dashclaw]` @ `275c6f33…`; `[src:herdr-portal]` @ `cae8ea07…`;
`[src:lazyagent]` @ `2be879c1…`; `[src:herdr-f1]` @ `9af4d2af…`; `[src:netdata-docs]` @
`0a4ce7db…`.

### 2.2 Mechanism inventory with dispositions (v2 §3, §4)

**ADOPT** (v2 §4.1) — compatible as-is:

| ID | Mechanism | Anchor |
|---|---|---|
| T1 | Run history as event-sourced typed event cards (deep-linkable) | `temporal-ui` `event-card.svelte:126-177,258-316` |
| T2 | Status const tuple + explicit `unknown` fallback | `temporal-ui` `workflow-status.ts:5-25` |
| T4 | Query-grammar filter chip | `temporal-ui` `status-filter-chip.svelte:65-108,141-165` |
| T5 | Pending/retry/completed-with-retries are distinct marks | `temporal-ui` `event-history-legend.svelte:24-50,99,124` |
| HT1 | Run detail as orthogonal regions/tabs | `hatchet` `step-run-detail.tsx:35-42` |
| HT2 | Mini-map DAG with computed column layout | `hatchet` `mini-map.tsx:63-116` |
| D1 | Lowercase compact status vocabulary | `dagu` `statusLabels.ts:8-18` |
| D4 | Per-node table with permission-gated row actions | `dagu` `NodeStatusTable.tsx:29-56` |
| C1 | Decision record as a multi-tab object (Timeline/Graph/Evidence/Policies/…) | `dashclaw` `decisions/[actionId]/page.tsx:31-42,296-297,471-533` |
| C2 | Containment lifecycle independent of action status | `dashclaw` same page `:26-35` |
| C3 | Single approvals inbox as the primary human surface | `dashclaw` `approvals/page.tsx:96-150,256-260` |
| C5 | Approval-pause as a loud state | `dashclaw` `ApprovalPauseBanner.tsx:15-26` |
| C6 | Live-grants strip with inline revoke | `dashclaw` `ActiveGrantsStrip.tsx:8-23,81-108` |
| C7 | Queue-unavailable honesty ("last successful result from HH:MM:SS") | `dashclaw` `approvals/page.tsx:103,140,456-457` |
| C8 | Five-stage causal spine for one decision | `dashclaw` `CausalTimeline.tsx:27,40-49,78-86` |
| C9 | Evidence tab: side effects/artifacts/systems/raw payload | `dashclaw` `EvidenceTab.tsx:20,36,51,70-83` |
| C11 | Enforcement-liveness honesty | `dashclaw` `THESIS.md:47-48,83` |
| T7 | Debounced, increases-only live-region announcer | `temporal-ui` `count-announcer.ts:7-52` |
| C13 | Reduced-motion collapse system-wide | `dashclaw` `HeroDecisionRecord.tsx:1-13,20-24` |
| K2 | Accessible canvas mark (`role="img"`+`aria-label`+focus) | `uptime-kuma` `HeartbeatBar.vue:4-16,76-77` |

**ADAPT** (v2 §4.2) — compatible in spirit, constrained by the direction:

| ID | Adaptation |
|---|---|
| T3 | Counts-as-filters **drop the bare delta** or pair it with refresh age |
| O1/O2/O3 | Status badge: degrade-on-unknown + icon+label + `motion-reduce`; drop pill chrome |
| O4 | Phase text + age, mapped to the DB `RunState`/`StepAttemptRecord` vocabulary; `unknown`, never a raw code |
| O5 | Coarse health **only** as a derived display with its mapping exposed (no vanity score) |
| O6 | Log-scale duration bar with `UNKNOWN` height — fires only inside `L-WORKFORCE`, never on the resting roster |
| D3 | "Summary condition + failed-detail conditions" as the degraded/`safe_actions` summary |
| C10 | Receipt verify is a **read-only** affordance; no new mutating route class by default |
| L1 | Playback playhead only for the selected attempt's bounded replay |
| L3 | Comfort-band math as guidance; **fixed arrangements** (no persisted resize) |
| L4 | Size gate, with the portal's own budget and a marked `partial`/truncation |
| L5 | Small closed type set for the room's evidence classes |
| H1 | Zero-footprint attention column appears first; **drop the blink** |
| H3 | Fingerprint skip + keep-last-data on disconnect |
| H2 | Click-to-land; reply/steer becomes the governed `R4b` action band |
| Y2 | Provider window/pace as `ON-G4`, sourced from the existing usage/settlement ledger |
| Y3 | Inline SVG sparkline only inside a lens, only on one shared scale |
| K3 | Uptime clamp + retained-window pairing |
| C4 | Flood/pause is a **confirmed controller act**, never an automatic steer |
| HT3 | Live trace timeline for `R4d` + the pipeline lens |
| HT4 | Separate span-evidence region |

**DO-NOT-COPY** (v2 §4.3): throwing on unknown status (HTx); a per-user density switch (Y1) —
one arrangement per breakpoint; synced-hover anomaly charts (N1) — a chart wall; blinking counters;
gamification (F1, `herdr-f1` README explicitly fictional); a new POST verify route as a default
(C10); persisted resizable layout (L3); a multi-theme switcher as a product feature.

### 2.3 The five conflicts the new evidence surfaced (v2 §5)

1. **v1 "R0 wallboard of six KPI tiles"** conflicts with direction §4.3 (top-row KPI tiles removed)
   and §4.5. Correction: R0 is a **scope/truth strip** with per-value provenance; counts are
   addressable filters. Supported by `temporal-ui` T3/T4 and `dashclaw` C7.
2. **v1 "state as colour and rhythm"** conflicts with direction §11 (no decorative pulse) and §4.3.
   Correction: state = glyph + word + colour + settled timestamp; motion only for live transitions.
3. **v1 "Ask the data" LLM chart lens** conflicts with the zero-model-call portal. Correction:
   static recommended-lens mapping or omit.
4. **v1 "one computed health score"** is an unsupported `[P]` claim. Correction: derived display of
   measured statuses with its mapping exposed.
5. **v1 "call-center KPI treatment for R3"** conflicts with direction §4.1 Move 6. Correction:
   bounded **constraint ledger** with provenance and a money-risk exception marker.

### 2.4 Reconcile summary (v2 §6)

Net of v2: it **adds no new resting-screen region**; it **subtracts** the R0 KPI wallboard and the
rhythm animation, **relocates** the activity bar to a lens, and **gates** the LLM lens. It adds
mechanism-level detail to existing regions (announcer, typed evidence tab, causal spine,
flood/pause/grants, phase+age, payload size gate). It also records anti-references
(`herdr-f1` gamification; Netdata's chart wall) as the explicit things the direction forbids.

### 2.5 Adversarial findings carried forward (v2 §7, A-1..A-12)

High-severity: A-1 rhythm is not identity; A-2 no KPI wallboard; A-3 no runtime LLM chart lens;
A-4 no automatic approval pause (rails are observe-only). Medium: A-5 no density switch at rest;
A-6 no bare stale delta; A-7 accessible canvas; A-8 no persisted resize; A-9 no "consensus" claim;
A-10 health score must be `[C]` and linked. Low: A-11 a log is not a causal explanation; A-12
steering is a P1 act within a lease.

---

## 3. Evidence (c): the new-UI work's data surfaces and writers now available `[M]`

Branch state: `HEAD` = `0a29f28b4` = `main`. `wt_room_new` = `c06b158a7` (**8 commits ahead of
`main`, unmerged**). G-40/G-41 writers landed on `main` via `dc51c77ef` (PR #60 / `2cd0606e0`);
the older docs still calling them "declared-but-unwritten" are **stale**
(`docs/reviews/control_room_information_gaps.md:142`, `docs/designs/current/
control_room_backend_requirements.md:344`).

### 3.1 Timings (G-40 first-token/lease; G-30/G-31 queue/service)

| Signal | Writer (`file:line`) | Reader / route | Availability |
|---|---|---|---|
| `first_token_at` | `adapters/opencode.py:558-559` (field `:170`) → `runtime/executor.py:259-261,361` → `workflow_runner.py:247-256,349-352` (phase), `:631-636,643-667` (attempt), `:4031-4033` | run-ledger JSON (`scripts/run_workflow.py:966-967`) | `main` (measured) |
| `leased_at` | `workflow_runner.py:3824-3827,3890,3977-3979`; `scripts/worker.py:449-461` | run ledger + `queue_timings.jsonl` | `main` |
| `queue_wait_ms` / `service_time_ms` | `runtime/queue_timings.py:63-118` (`timing_row`/`append_timing`); `scripts/worker.py:347-365`; enqueue `queue_timings.py:47-60` | `control/projections/sla_queue.py:103-200` (`recent_completions`) → `GET /api/queue/sla` (`routes/analytics.py:40,73-77`) | `main` |
| R4d UI timings grid | `parity.js:514-547` (`renderTimings`), `:552-570` (`loadTimingSample`, reads `/api/matrix`); `TIMING_FIELDS` `:491-506` | — | `main`; **renders `unknown`** for queue/service/first-token |
| Workforce lens | `parity.js:1558-1610` (`loadWorkforce`, header `:1572`, reads `/api/matrix`) | — | `main`; explicitly labels queue/service/first-token unobservable |

**Gap:** the control DB `step_attempts` table (`control/control_db.py:957-976`) carries only
`started_at`/`ended_at`/scalar `tokens`/`cost_usd`/`exit_code`/`error`, so `GET /api/runs/<run_id>`
cannot expose G-40/G-41. Those fields live **only** in the workflow run ledger and
`queue_timings.jsonl`.

### 3.2 Cost split (G-41) and the answer/explanation split

| Signal | Writer (`file:line`) | Reader / route | Availability |
|---|---|---|---|
| `cost_inference` / `cost_orchestration` (G-41) | `measurement/efficiency.py:249-272` (`split_cost`); `workflow_runner.py:4034-4047`, fields `:247-251,:349-350,:631-633,:659-660`; attach `:3255-3256,3274-3275` | **none dedicated** (run ledger only; `glance.py:567` hardcodes `cost.provenance: unknown`) | `main` (written, **unexposed**) |
| `tokens.answer` / `tokens.explanation` | `adapters/opencode.py:223-226,1193-1195`; `runtime/executor.py:251-252,351-352`; `workflow_runner.py:1654-1655,3973-3974,4016-4017`; story path `runtime/story/models.py:115-116,156-157,176-177`; `measurement/signal_registry.py:110-119` | `control/projections/model_quality.py:144-173` (`_narration_block`) → `GET /api/quality` (`routes/analytics.py:36,46-49`, service `services/context.py:186-220`) | `main` (measured where the canonical cells carry the split; else `None` with a named reason) |

**Explanation Tax** = `explanation_tokens/(answer+explanation)` (`model_quality.py:144-173`), a
separate signal from G-41's dollar split.

### 3.3 States

| Vocabulary | Anchor |
|---|---|
| `RunState` — 12 values (`queued running awaiting_approval verifying promotable promoting merged projecting published failed cancelled quarantined`) | `control/control_db.py:140-182`; terminal `:187-189`; `ALLOWED_TRANSITIONS` `:193-249` |
| `AttemptState` — 7 values (`queued running ok failed awaiting skipped cancelled`) | `control_db.py:252-276,281-289` |
| `RunRecord` / `StepAttemptRecord` | `control_db.py:460-496,518-545` |
| `control-status/v1` packet (`active_runs`+`phases_completed/phases_total`, `awaiting_approvals`, `promotable_runs`, `failed_runs`, `unhealthy_workers`, `projection_lag`, `safe_actions`, `degraded`) | `control/control_status.py:92,199-334,357-398,482-559,722-828`; CLI `scripts/control_status.py`; dispatch `cli.py:137` |
| UI lifecycle tokens | `wt_room_new` only: `app.js:50` (`LIFECYCLE_TOKENS`), `:525` (`lifecycleToken`), `:628` (`renderPhaseBar`) |

### 3.4 Data surfaces — Control Room HTTP routes at `HEAD`

**47 routes** at `HEAD` (measured), up from **44** at `1457b9299`. New on `main` since the old room:
`GET /api/glance` + `GET /api/events` (the glance SSE, `routes/glance.py:800,803`), and
`GET /api/decisions` (`routes/decisions.py:25`). Existing routes the old room used remain
registered and served. Full list (47) is enumerated in the working notes; the load-bearing ones:

| Surface | Route | Handler |
|---|---|---|
| One resting-screen projection | `GET /api/glance` | `routes/glance.py:800` / `build_glance:678-724` |
| Bounded glance SSE | `GET /api/events` | `routes/glance.py:803` / `_event_stream:758` |
| Per-cell SSE | `GET /api/events/<cell_id>` | `routes/telemetry.py:465` |
| Fleet matrix + telemetry | `GET /api/matrix` | `routes/telemetry.py:462` |
| Operations packet + run detail | `GET /api/operations`, `GET /api/runs/<run_id>` | `routes/operations.py:28-29` |
| Queue timings | `GET /api/queue/sla` | `routes/analytics.py:40` |
| Model quality (narration) | `GET /api/quality` | `routes/analytics.py:36` |
| Flags / registry / routing / usage / projections | `GET /api/flags`, `/api/registry`, `/api/routing`, `/api/subscription-usage`, `/api/projections` | `routes/flags.py:90`, `registry.py:93`, `telemetry.py:466-467,464` |
| Mutations (existing, gated) | `POST /api/flags/<id>/steer|interrupt`, `/api/experiments`, `/api/queue/reinterleave`, `/api/claude-agents/…`, `/api/design-sessions/…`, `/api/docs-health/approve` | see §1.5 |

### 3.5 The current room's surfaces (what the new-UI work actually built)

| Surface | Anchor (`HEAD`) | Notes |
|---|---|---|
| One resting screen: R0 truth strip, R1 attention, R2 roster, R3a/b/c ledger | `apps/control_room/static/index.html:100-196`; hydration `app.js` from `/api/glance` | no page scroll, no region scroll (`index.html:1-9`) |
| Selection dock with `R4a` identity / `R4b` worker stream+actions / `R4c` evidence ladder / `R4d` step timings | `index.html:206-243`; `parity.js` | R4b uses `GET /api/events/<cell_id>`; R4d grid currently `unknown` for timing fields |
| Trends lens — 4 catalog charts: `spend`, `throughput`, `failure`, `dependency` | `charts.js:39-76,195-203,411-418` | SVG+CSS, `viewBox`, `currentColor`; browser-session retained window (`HISTORY_MAX=60`, `charts.js:35`) |
| Workbench — 13 lenses: fleet, attention, money, registry, sessions, queue, routing, docs, audit, health, **workforce**, operations, surfaces | `index.html:270-297`; registry `parity.js:2221-2236` | each lazy-loads the old endpoint; `data-lens="workforce"` present (`parity.js:1558-1610`) |
| `wt_room_new` adds (unmerged) | truth strip `app.js:331`, attention inbox `:884/:1060`, run tiles `:669/:850`, money+health `:1237/:1300/:1346`, session dock tabs Transcript/Tools/Diff `index.html:253-268`, `parity.js:524/:556/:590` | adds **no** new chart/sparkline/burn surface |

### 3.6 Measured vs proposed vs unexposed — the determination's crux

| Signal | Measured? | Writer | UI/route exposure |
|---|---|---|---|
| `first_token_at` (G-40) | **Yes** (`main`) | `opencode.py:558`, `workflow_runner.py:4031` | run ledger only; R4d/workforce show `unknown` |
| `leased_at` (G-40) | **Yes** | `workflow_runner.py:3824-3890`, `worker.py:461` | run ledger + `/api/queue/sla` (settled jobs); R4d `unknown` |
| `queue_wait_ms` / `service_time_ms` | **Yes** | `queue_timings.py:63-118`, `worker.py:347-365` | `/api/queue/sla` only; R4d/workforce `unknown` |
| `cost_inference` / `cost_orchestration` (G-41) | **Yes** | `efficiency.py:249-272`, `workflow_runner.py:4034-4047` | **no route/UI** |
| `tokens.answer` / `tokens.explanation` | **Yes** | `opencode.py:1193-1195` + story path | `/api/quality` narration block |
| `RunState`/`AttemptState`/`safe_actions`/phase progress | **Yes** | `control_db.py`, `control_status.py` | `/api/glance`, `/api/operations`, `/api/runs/<run_id>`, CLI |
| `L-WORKFORCE` p50/p95 + narration penalty lens; R4d answer/explanation tokens | **Proposed only** | — | research docs only; UI renders `unknown` |

**Conclusion the criteria must grade against:** the four brief elements split cleanly —
*scroll* and *charts/SVG* exist but are constrained (no page scroll; charts browser-session only);
*workforce* exists as a lens but its distinguishing data (step durations) is **written and
unexposed**; *old dashboard as base* is available as an inventory (235 ids) and is already the
parity reference.

---

## 4. Evidence (d): the controller's brief `[P]`

### 4.1 The brief, verbatim

The work item states the outcome elements verbatim:

> **(scroll, charts/SVG, workforce, step durations, old dashboard as base)**

and the objective:

> "Determine the Control Room design by process: evidence + criteria, three candidate directions,
> weighted evaluation and selection, adversarial review, final determination (scroll, charts/SVG,
> workforce, step durations, old dashboard as base)."

**Fidelity note.** A repo-wide search found **no document** containing this phrase list verbatim as
a "controller brief". The only `charts/SVG` match is the earlier work order
`workflows/repository/control_room_ux_repair.yaml:100` ("Keep charts/SVG/ styling from the
facelift where they satisfy the principles"); the only `old dashboard` match **rejects** it as the
base (`workflows/repository/control_room_ui_rebuild.yaml:24-29`). The brief is therefore treated as
the **controller's current policy**, and this brief records where it agrees with and departs from
the earlier accepted direction.

### 4.2 The repository's authoritative brief (for reconciliation)

`docs/research/control_room_direction.md` (status: accepted) is the repository's brief:

- §16 "The resting screen — the canonical glance contract (brief)" (`:776`), delegating the
  canonical `ON-G1..G7` contract to `docs/research/control_room_ia.md` §4 (`:776-787`) and fixing
  §18.2's **"no page scroll and no region scroll"**.
- §18 "Facelift brief — acceptance criteria, render gate, and glance check" (`:860-898`): render
  gate at 1440×900 / 1024×768 / 390×844, one-resting-screen glance check, contrast, a11y,
  no-regressions, adversary closure, recognizability, and a semantic+feature-parity gate.
- §7 "Chart set (no unconditional defaults)" (`:570-588`): charts are counts/tables first; a chart
  must state its question, decision, baseline/scope, sampling rule, textual equivalent, fallback,
  and a performance budget. Priority chart forms: ranked ledger (1), causal timeline/waterfall (2),
  cost/quality time-series on **one shared scale** (3), bounded quantity text+progress (4), live
  output feed (5).
- §10 "SVG set" (`:630-641`): topology only if live+scoped+actionable; micro-visuals as SVG+CSS
  micro-marks, never a chart runtime for a 40 px mark; `viewBox`, `currentColor`, real `<text>`,
  `role`/`<title>`, forced-colors safe.
- §3.6 "The restored worker regions" (`:284-303`): `R4b` per-worker event+action; `R4d` per-attempt
  step timings (queue wait, service time, first-token, duration, retries, tokens by
  answer/explanation, cost provenance, exit code, verification; each `measured` or explicit
  `unknown`); the fleet aggregate is the `L-WORKFORCE` lens; parity is a hard rule.
- §8 "Truth and provenance contract" (`:592-610`): every consequential value carries source,
  observation time/age, scope/retained window/truncation, measured/estimated/unknown semantics, and
  a link; "green never lies".

### 4.3 The tension the determination must resolve

The brief says **scroll**; the accepted direction §18.2 says **no page scroll and no region
scroll**. These are in direct conflict. The determination (Part VI) resolves it explicitly and
returns the change to the controller for ratification.

---

# Part II — Evaluation criteria

Eight weighted criteria (weights sum to 100). Each cites its **controller policy `[P]`**, a
**reference mechanism `[X]` with anchor**, and the **truth contract `[M]`** it must not violate.

| # | Criterion | Wt | Definition (pass condition) | Controller `[P]` | Reference `[X]` (anchor) | Truth contract `[M]` |
|---|---|---|---|---|---|---|
| **C1** | **Immediate legibility** | 14 | A cold operator can read the fleet's health and the next decision from the first screen without interaction or scrolling to find them. | Work item; direction §16/§18.2 ("no page scroll", all `ON-G1..G7`) | Temporal T3 counts-as-filters (`status-counts.svelte:62-84`); OpenHands O2 icon+label+color (`run-status-badge.tsx:66-127`) | `ON-G1..G7` contract (`control_room_ia.md` §4); `glance.py` |
| **C2** | **Information density without wall-of-noise** | 13 | High information per pixel with a stated restraint budget; no KPI-tile filler, no unconditional chart, no decorative pulse. | Direction §4.5 restraint budget; §6 rejected generic grammar | Langfuse L3 comfort-band split (`TraceLayoutDesktop.tsx:42-87`); DO-NOT-COPY Y1 density switch (v2 §4.3) | Direction §16 pixel budget; `parity` dispositions |
| **C3** | **Chart coverage: step/phase duration, cost, throughput** | 13 | Real SVG charts exist for cost, throughput, and **step/phase duration**, each meeting direction §7's eight statements and §10's SVG rules. | Work item ("charts/SVG", "step durations"); direction §7/§10 | Hatchet HT3 live trace timeline (`trace-timeline.tsx:52-85`); OpenHands O6 log-scale duration bar (`automation-run-activity-metrics.ts:9-96`); lazyagent Y3 SVG sparkline (`Sparkline.svelte:1-40`) | `charts.js`; G-40 timings; §8 truth contract |
| **C4** | **Workforce visibility** | 13 | A workforce surface (region or lens) shows measured per-model/per-attempt workload: queue wait, service time, first-token, retry, tokens by model, and step durations — with `unknown` where unmeasured. | Work item ("workforce", "step durations"); direction §3.6 `R4d`+`L-WORKFORCE` | lazyagent Y2 provider window/pace (`LimitsPage.svelte`); Dagu D4 per-node table with gated actions (`NodeStatusTable.tsx:29-56`) | `L-WORKFORCE` = 0 old items (`parity_inventory`); G-40/G-30/G-31 writers §3.1 |
| **C5** | **Scroll / navigation** | 12 | One deliberate arrangement per breakpoint; content beyond the fold is reachable by scroll; drill-down is a push, not a board-hop; selection/scroll position survives a refresh. | Work item ("scroll"); direction §3.2/§12 (one arrangement per breakpoint) | Herdr-portal H2 click-to-land (`README.md`); Temporal T1 deep-linkable event id (`event-card.svelte:126-177`); v2 H3 fingerprint+reconnect | Direction §18.2 no-page-scroll (to be ratified); one arrangement |
| **C6** | **Truthfulness (provenance / no fabricated value)** | 15 | Every consequential value carries source + age + scope; a missing value is `unknown`, never `0`; stale/degraded never reads as all-clear; per-value provenance, not one global footer. | Direction §8 truth contract; work item's "old dashboard as base" must not resurrect per-card sparkline fabrication | DashClaw C7 queue-unavailable honesty (`approvals/page.tsx:103,140,456-457`); C11 liveness honesty (`THESIS.md:47-48,83`); OpenHands O1 degrade-on-unknown (`run-status-badge.tsx:140-143`) | `control_status` `safe_actions`; `glance.py`; "green never lies" |
| **C7** | **Feasibility with existing routes** | 10 | The design needs no new endpoint class and no new mutating route; any addition is read-only and reuses a registered route or the already-written ledger. | Work item; direction §18 scope ("No new mutating route class") | DashClaw C10 stateless verify (gated, v2 §4.2) | **47 routes at `HEAD`**, **44 at `1457b9299`**; parity `routes_dropped: 0` |
| **C8** | **Working-set fidelity to the old dashboard** | 10 | Every one of the old room's capabilities (235 ids, 10 capability classes) is placed, present, wired, and non-empty — or an explicit documented empty-state. No silent drop. | Work item ("old dashboard as base"); direction §3.6 parity hard-rule; §14 #24 | DashClaw C1/C2 multi-tab decision object + separate containment lifecycle (`decisions/[actionId]/page.tsx:31-42,26-35`) | `parity_inventory.json` (235 items, 214 re-house, 20 replace-with-reason, 1 preserve); u3 IA §15 class-P gate |

**Alternatives considered and folded in:** a ninth criterion, "aesthetic identity", was rejected as
untestable and taste-based (direction §4.2's blind recognizability test already operationalises the
legible part); a "model-quality/`Grit`" criterion was folded into C3/C4 because those signals are
measured but belong to the chart/workforce surfaces.

---

# Part III — Three candidate directions

All three are *design directions*, not layouts; each names its base, its answer to the five brief
elements, the routes it consumes, and its measured evidence.

## Candidate A — "Old dashboard, restored" (multi-board nav + System overflow, as `1457b9299`)

**Base:** the old dashboard's DOM/layout itself.
**Shape:** 7 destinations + System overflow + transversal Detail; one board visible at a time;
three-column desktop; `adoptRegions` re-parents the shared pipeline strip; per-cell sparklines and
burn trace as at `1457b9299`.

| Brief element | Answer |
|---|---|
| scroll | board-internal scroll + a scrolling detail drawer; no page-level scroll concept |
| charts/SVG | burn trace + per-cell sparklines + surface tables (`app.js:260,306`; `#burn-trace`) |
| workforce | **absent** — no step-timing surface (`ux_foundation.md:346-354`) |
| step durations | **absent** (`queue_wait_ms`/`service_time_ms`/`first_token_at` unexposed) |
| old dashboard as base | **is** the base |

**Evidence for:** full working-set fidelity (235/235); every old interaction preserved; 0 new
routes needed. **Evidence against:** rejected once as "a layer on top of the clunk" with a broken
mobile stack (`control_room_ui_rebuild.yaml:24-29`); no workforce/step-duration; per-card
sparklines are explicitly removed by the direction (`direction.md:471,559`); 234/235 ids differ
from the current room, so "restore" is a large re-litigation.

## Candidate B — "One resting screen + deliberate lenses" (the current room, `HEAD`)

**Base:** the facelift / current `main` (`apps/control_room/static/index.html` + `parity.js` +
`charts.js` + `visuals.js`).
**Shape:** one no-scroll resting screen (R0 truth strip, R1 attention, R2 roster, R3a/b/c ledger),
a hidden selection dock (R4a–d), a trends lens, and a workbench of 13 lenses that re-house the old
capabilities; optional `wt_room_new` refinements (truth strip, attention inbox, run tiles, session
dock tabs).

| Brief element | Answer |
|---|---|
| scroll | **none at rest** (direction §18.2 enforced); drill-down only |
| charts/SVG | `charts.js`: spend/throughput/failure/dependency, browser-session window |
| workforce | a workbench lens exists (`parity.js:1558-1610`) but labels queue/service/first-token `unobservable` |
| step durations | R4d grid exists (`parity.js:514-547`) but renders timing fields `unknown` |
| old dashboard as base | re-housed as lenses (214 `re-house`); not structurally the base |

**Evidence for:** meets `ON-G1..G7`; enforces the truth contract; parity inventory satisfied
(0 routes dropped); already merged and gated. **Evidence against:** the brief's *scroll* is
unmet; the brief's *step durations* are unmet despite the writers existing; common jobs sit behind
several drill-down clicks; the trends charts cannot see server history (browser-session ring only).

## Candidate C — "Scroll-synthesized instrument" (hybrid; old working set as scrollable bands)

**Base:** the old dashboard's **working set** (the 235-id parity inventory), recomposed.
**Shape:** one document that **scrolls**. The **first viewport** is the no-scroll glance contract
(`R0` truth strip, `R1` attention, `R2` roster, `R3a/b/c` ledger — i.e. Candidate B's rest state).
Below the fold, the old room's capability set is stacked as dense, labelled, scrollable **bands**
(Fleet ledger, Money/health, Workforce, Board surfaces, Sessions, Routing/System), each band
lazy-loading the same route the old room used. SVG charts are real marks, not a runtime. The
workforce band is built from the now-measured ledger timings.

```text
┌ first viewport (no-scroll glance: ON-G1..G7) ───────────────────────┐
│ R0 truth strip · R1 attention · R2 roster · R3a/b/c ledger          │
├─────────────────────────────────────────────────────────────────────┤
│ ▼ scroll                                                            │
│ [FLEET BAND]      full roster, filters, search, stage strip         │
│ [MONEY BAND]      spend/burn trace (one scale), tokens, leases      │
│ [WORKFORCE BAND]  ▲ SVG: step/phase duration · queue wait · service │
│                   time · first-token p50/p95 by model · retry rate  │
│ [CHARTS BAND]     SVG cost · throughput · failure · dependency      │
│ [BOARDS BAND]     flags · routing · registry · docs · audit · usage │
│ [SESSIONS BAND]   design + claude controls (governed action band)   │
│ [DETAIL DOCK]     R4a–d selected run (stream · ladder · timings)    │
└─────────────────────────────────────────────────────────────────────┘
```

| Brief element | Answer |
|---|---|
| scroll | the page scrolls; the first viewport still answers `ON-G1..G7` with no scroll |
| charts/SVG | keep `charts.js` (extend to server-windowed cost/throughput) + add a step/phase-duration SVG; no runtime |
| workforce | a first-class workforce band with measured p50/p95 + step durations; unknown stays unknown |
| step durations | R4d per-attempt grid wired to G-40/G-30/G-31 via a read-only route over the existing run ledger / `queue_timings.jsonl` |
| old dashboard as base | the parity inventory is the base; every capability placed, wired, non-empty |

**Evidence for:** answers all five brief elements; keeps the glance contract while restoring
density; makes the already-measured timings visible; uses only existing routes plus one read-only
exposure; preserves the old room's working set (C8=5). **Evidence against:** the scroll change
requires a controller ratification of direction §18.2; more surface area to gate; must actively
prevent a "wall of noise" and per-value provenance must remain attached in a long page.

---

# Part IV — Weighted evaluation and selection

Scoring: 1 (fails) … 5 (excellent). Weighted total = Σ (score × weight) / 5, on a 0–5 scale.

| Criterion | Wt | A: restore old | B: current room | C: scroll-synthesized |
|---|---|---|---|---|
| C1 Immediate legibility | 14 | 3 | **5** | 4 |
| C2 Density w/o wall-of-noise | 13 | 3 | 4 | 4 |
| C3 Chart coverage (duration/cost/throughput) | 13 | 4 | 3 | **5** |
| C4 Workforce visibility | 13 | 1 | 3 | **5** |
| C5 Scroll / navigation | 12 | 3 | 2 | **5** |
| C6 Truthfulness | 15 | 3 | **5** | 4 |
| C7 Feasibility with existing routes | 10 | **5** | **5** | 4 |
| C8 Working-set fidelity | 10 | **5** | 3 | **5** |
| **Weighted total (0–5)** | **100** | **3.27** | **3.79** | **4.48** |

Computation (C): `4×.14 + 4×.13 + 5×.13 + 5×.13 + 5×.12 + 4×.15 + 4×.10 + 5×.10`
`= .56+.52+.65+.65+.60+.60+.40+.50 = 4.48`.

**Sensitivity.** C remains first under adverse re-scoring: if C's truthfulness drops to 3 and its
feasibility to 3, C = 4.23; B's best case (C3=5, C4=5, C5=3) = 4.43; A's ceiling ≈ 3.5. The
ordering `C > B > A` is stable because C wins the four brief-weighted criteria (C3–C5, C8) that B
and A each fail on at least two.

**Why not B despite its truth score.** The brief explicitly names *scroll* and *step durations*;
B's own code documents that it delivers neither (no page scroll; timing fields `unknown`), so B
cannot satisfy the work item without becoming C.

**Why not A despite its fidelity.** A is the only candidate that fails both *workforce* and
*step durations* outright and re-introduces per-card sparklines the direction removed; its layout
was already rejected for mobile.

---

# Part V — Adversarial review

Format: severity · the flawed claim · required correction · the acceptance that proves the
correction.

| # | Sev | Flawed claim | Required correction | Acceptance |
|---|---|---|---|---|
| **AD-1** | high | "Scroll" can simply be added; direction §18.2's no-scroll rule is a detail. | The no-scroll rule is a *contract* (`direction.md:876-880`). Resolve as: the **first viewport** must still answer all `ON-G1..G7` with no page/region scroll; scroll is admitted **only below the fold**. A controller ratification is an explicit open decision (Part VI). | Render gate geometry check at all three breakpoints proves `ON-G1..G7` inside the initial viewport, **and** a "scroll-reachable" fixture proves the bands render non-empty below it. |
| **AD-2** | high | The workforce/step-duration data can be rendered "live" now. | G-40/G-41 are written to the run ledger / `queue_timings.jsonl` only; the control DB `step_attempts` table lacks them (`control_db.py:957-976`) and R4d renders `unknown`. Any design that claims measured step durations must add a **read-only** exposure, not read `unknown` and call it a duration. | A fixture run with a real ledger shows `queue_wait`/`service_time`/`first_token`/`cost_inference` as `measured` (or `unknown` with a *reason*), and the route is `GET`-only. |
| **AD-3** | high | "Old dashboard as base" means copy its DOM (Candidate A). | The repo's only literal `old dashboard` reference **rejects** DOM-copy (`control_room_ui_rebuild.yaml:24-29`); the requirement is **working-set fidelity** (parity), not structural reuse. Base = the 235-id inventory, recomposed. | The class-P parity gate passes for all 235 items with a surface and a disposition; no `re-skin` statement survives in the design. |
| **AD-4** | high | A long scrolling page is fine as long as it is dense. | Direction §4.5 restraint budget and §8 per-value provenance apply to **every** band; a scroll page is the easiest place to reintroduce a generic dashboard wall. | Every chart is justified by direction §7's eight fields; no KPI tile row; per-value provenance tested in a "stale fixture" (age shown, never all-clear). |
| **AD-5** | medium | Server-windowed trend charts are a new backend feature. | If the trends lens needs server history, it must read an existing route (e.g. `/api/queue/sla` `recent_completions`, the run ledger via `/api/runs/<id>`) or stay browser-session with an explicit scope label (`charts.js:35,254`). No new datastore. | The chart card states its scope and source; a missing projection is an explicit error state, not a blank. |
| **AD-6** | medium | Re-adding per-card sparklines improves the old-room fidelity score. | The direction **removed** per-card sparklines for want of shared scale (`direction.md:471,559`); fidelity means preserving the capability (a cost/throughput view), not the mark. One-scale series belong in a band/lens. | Forced-colors + reduced-motion screenshot; one scale per chart; no ambient per-card mark on the resting roster. |
| **AD-7** | medium | The workforce band makes the resting screen heavier. | The workforce band lives **below the fold** as a scroll band or a lens; the first viewport's pixel budget is untouched (v2 §4.2 O6 relocation). | Resting glance check still passes at 1440×900 / 390×844; the workforce band is not in the initial viewport. |
| **AD-8** | medium | Observe-only rails can auto-pause on a threshold (DashClaw C4). | The repository's rails never steer (rules AUTHORITY; v2 A-4). Any pause/bulk action is a **confirmed controller act** with a recorded decision. | No code path pauses without a confirmation + decision record; grep + authority test. |
| **AD-9** | low | A scrolling page needs a per-user density switch. | One arrangement per breakpoint (direction §12.2); density switches multiply the render gate (v2 §4.3 Y1). | The render gate tests one arrangement per breakpoint, not a density matrix. |
| **AD-10** | low | The v2 synthesis is authoritative because it is newest. | v2 is `status: proposed` and **not on `main`**; the accepted authority is `control_room_direction.md`. v2 is evidence, not policy. | Every adopted mechanism cites v2 by ID + anchor **and** reconciles to the direction; no v2-only mechanism is adopted without a direction basis. |

---

# Part VI — Final determination

## 6.1 The design

**Selected: Candidate C — the scroll-synthesized instrument.**

A single scrolling Control Room document that keeps the accepted direction's truth and provenance
contract, and resolves the five brief elements as:

1. **Scroll.** The page scrolls. The **first viewport** remains the canonical no-scroll
   `ON-G1..G7` glance surface (`R0` truth strip, `R1` attention, `R2` roster, `R3a/b/c` ledger).
   Everything the old room carried that does not fit the glance is stacked below as labelled,
   dense, **scrollable bands** — one deliberate arrangement per breakpoint. This is the change
   that requires controller ratification (6.4).
2. **Charts/SVG.** Keep the existing SVG+CSS chart module (`charts.js`; no runtime, no canvas,
   `viewBox` + `currentColor`) and extend it to the chart set the brief names: **step/phase
   duration**, **cost** (one shared scale), and **throughput**, each meeting direction §7's eight
   statements. Missing values are gaps; <2 samples is an explicit empty state.
3. **Workforce.** A first-class **workforce band** (and the existing `L-WORKFORCE` lens) that
   aggregates the already-measured ledger timings per model/attempt: p50/p95 queue wait, p50/p95
   service time, first-token latency, retry rate, tokens by model, and step durations — `measured`
   where measured, `unknown` with a reason where not.
4. **Step durations.** Wire the per-attempt `R4d` grid and the workforce band to G-40/G-30/G-31 by
   adding **one read-only exposure** over the existing run ledger / `queue_timings.jsonl` (the
   `queue_wait_ms`/`service_time_ms`/`first_token_at`/`cost_inference`/`cost_orchestration` fields).
   No new mutating route class; no new datastore; the control DB schema is untouched (or extended
   additively if the controller prefers DB-sourced reads — see 6.4).
5. **Old dashboard as base.** The **working set is the base**: all 235 old ids / 10 capability
   classes / 34 canonical endpoints are placed, present, wired, and non-empty (or an explicit
   empty-state) under the class-P parity gate. The old DOM/layout is **not** copied (AD-3).

## 6.2 What is preserved from each candidate

- From **A**: the complete working set and every interaction (235 ids, per-worker actions, typed
  doors, all boards) — as scroll bands, not as a three-column cockpit.
- From **B**: the `ON-G1..G7` no-scroll first viewport, the truth/provenance contract, the
  selection dock `R4a–d`, the workbench lenses, the SVG chart module, and the render gate.
- New in **C**: the scroll below the fold, the step/phase-duration chart, the measured workforce
  band, the read-only timing exposure, and a first-viewport geometry guard that keeps the glance
  contract intact.

## 6.3 Acceptance (what proves the determination)

| Gate | Check |
|---|---|
| Glance preserved | Render gate at 1440×900 / 1024×768 / 390×844: all `ON-G1..G7` anchors present, non-zero, fully inside the initial viewport, **no page scroll needed to reach them**. |
| Scroll works | A below-the-fold fixture shows every band non-empty with live data; the page's total height is bounded and each band carries a scope/provenance label. |
| Charts real | Every chart states question, decision, baseline/scope, sampling rule, textual equivalent, fallback, and budget (direction §7); SVG only; missing value = gap, not zero. |
| Workforce measured | A fixture run with a real ledger shows measured queue wait / service time / first-token / cost split / step durations; unmeasured = `unknown` with a reason. |
| Parity | Class-P gate: all 235 `parity_inventory` items present/wired/non-empty, with their disposition; no silent drop. |
| Authority | No new mutating route; observe-only rails never auto-steer; every irreversible act behind its existing typed door + receipt. |
| No-regression | The eight §12.2 guardrails, forced-colors, reduced-motion, contrast (WCAG 2.2 AA), single EventSource-per-object. |

## 6.4 Open controller decisions (the genuinely open choices)

1. **Ratify scroll (required).** The determination admits page scroll below the first viewport,
   which relaxes direction §18.2's "no page scroll". This is a **P0 controller policy change** and
   must be signed before implementation; the alternative (keep no-scroll) forces Candidate B and
   forgoes the brief's *scroll* element.
2. **Ratify the read-only timing exposure.** G-40/G-41 are measured but reach no route. Choose
   (a) a new read-only `GET` over the run ledger / `queue_timings.jsonl`, or (b) an additive
   control-DB read model. Either is read-only; (b) touches the schema and is the heavier path.
3. **Ratify "old dashboard as base" as working-set fidelity, not DOM reuse** (AD-3), consistent
   with the parity hard-rule and the earlier rebuild rejection.
4. **Confirm the v2 status.** If any v2-only mechanism is adopted, decide whether to land v2
   (`87559ef66`) on `main` or keep it as a pinned, branch-local evidence reference.

## 6.5 Handoff

This brief is the determination input for the next phase: a small, gated task decomposition
(one question + one acceptance per task) that implements Candidate C band by band, in this order:
(a) first-viewport/layout guard + scroll shell; (b) chart set (step/phase duration, cost,
throughput); (c) read-only timing exposure; (d) workforce band wired to it; (e) parity class-P
gate over all 235 items. No task may expand the authority model, add a runtime dependency, or
introduce a new mutating route class.

---

## Appendix — source pins

- Old dashboard: `1457b9299` (847-line `apps/control_room/static/index.html`, 4109-line `app.js`,
  235 unique ids, 44 route registrations).
- Current room: `HEAD` = `0a29f28b4` = `main` (321-line `index.html`, 47 routes, `charts.js`,
  `visuals.js`, `parity.js`).
- New resting screen: `wt_room_new` @ `c06b158a7` (8 commits ahead of `main`, unmerged).
- v2 synthesis: `docs/research/control_room_ui_reference_synthesis_v2.md` @ `87559ef66`
  (branch `wt_facelift_review`).
- Accepted direction: `docs/research/control_room_direction.md` (status: accepted);
  `docs/research/control_room_ia.md` (§4 `ON-G1..G7`, §14/§15 parity palette);
  `docs/research/control_room_ux_foundation.md` (operator/jobs/pain/principles);
  `docs/research/control_room_interaction_model.md`, `control_room_wireframe.md`,
  `control_room_state_screens.md`.
- Parity: `experiments/research/control_room/parity_inventory.json`.
- Writers: `dc51c77ef` / `a289e87db` ("G-14 evaluator_independent, G-40 attempt timings, G-41 cost
  split"); `c8ca59832`; `d1f8a8279`.
- Briefs/work orders: `workflows/repository/control_room_ux_repair.yaml`,
  `workflows/repository/control_room_ui_rebuild.yaml`,
  `workflows/repository/control_room_facelift_review.yaml`.
