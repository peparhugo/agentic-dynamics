# Control Room Refresh: Visual System Design

**Phase:** design only
**Date:** 2026-08-23
**Companion:** `docs/designs/control_room_refresh_audit.md` (the c1 audit)
**Scope:** `apps/control_room/static/` visual and interaction treatment only in a later phase.
This document changes no implementation, route, polling cadence, event stream, or API payload.

## Design Thesis

**Obsidian Signal** turns Control Room from a developer-console collection of cards into a quiet,
high-confidence operations instrument: near-black space, a single electric iris accent, generous
data hierarchy, and only meaningful motion. It should feel like a premium flight deck, not a
marketing dashboard: the most urgent work is visually immediate, the rest recedes without being
hidden, and every live indicator is honest about what the browser actually knows.

The c1 audit establishes the constraints that make this an interface refresh rather than a
functional rewrite:

1. Preserve all 28 routes, both SSE streams, default `message` frames, `replay_complete`,
   heartbeat comments, and the one-selected-detail-stream rule
   (`control_room_refresh_audit.md` §Contract Guardrails, §SSE Inventory).
2. Retain safe DOM construction, keyed reconciliation for the four polled lists, delegated
   selection, existing idempotent mutations, and the current `data-mirror` single-writer
   mechanism (`control_room_refresh_audit.md` §JavaScript Architecture).
3. Improve visual hierarchy rather than inventing observability. The matrix payload lacks a
   structured condition or per-cell model field; the refresh must not parse compound cell IDs to
   simulate them (`control_room_refresh_audit.md` §Data That Is Present but Hard to Read).
4. Preserve the separate lifecycle and supervisor-attention axes, including text and non-color
   cues (`control_room_refresh_audit.md` §Visual System and Dated Elements).

## Design Principles

1. **Signal has a place.** The global shell answers "is the room connected and where is the
   work?" Fleet answers "which cell needs my eyes?" Detail answers "what happened?" No surface
   repeats a larger surface merely because data is available.
2. **Black creates hierarchy.** Use true near-black page space and dark graphite panels; reserve
   luminous surfaces for selection, danger, and active work. This corrects the audit's finding
   that every surface currently has equal bordered-card weight.
3. **One signature color, several semantic channels.** Iris is solely for focus, selection, and
   primary reversible action. Lifecycle and attention retain distinct semantic tokens and always
   pair color with an icon and plain-language status.
4. **Live, not theatrical.** Liveness is a small status dot, a settling timestamp, and a
   restrained pulse on real known activity. The app cannot observe SSE `ping` comments, so it
   must never claim to visualize a heartbeat it does not receive.
5. **Density is a controlled tool.** At high fleet count, operators compare a field of cells;
   at low count, they inspect individual cards. Same data, same DOM identity, different visual
   density.
6. **Actuation looks different from observation.** Read-only information is spacious and quiet.
   Reversible controls are deliberate iris actions. Destructive controls retain rose treatment
   and typed confirmation; a premium coat must not reduce the existing safety friction.

## Design Tokens

All values below are named tokens. The implementation should expose them as CSS custom
properties, group them in the existing token block, and use token references rather than literal
values in component rules. No external font or CDN is permitted.

### Color

The dark theme is primary. The palette uses a blue-violet signature rather than generic cyan,
and keeps semantic colors separated by lightness, shape, label, and placement so status remains
distinguishable for deuteranopia.

| Token | Value | Role and decision |
| --- | --- | --- |
| `--cr-canvas` | `#05070B` | True-near-black application canvas. It creates negative space around operational panels rather than another tinted slab. |
| `--cr-canvas-raised` | `#090D14` | Hovered canvas and shallow shelf behind a grouped object. |
| `--cr-surface-1` | `#0D121B` | Default board and rail surface. |
| `--cr-surface-2` | `#131B27` | Raised card, sheet, filter, and form surface. |
| `--cr-surface-3` | `#1A2533` | Hover/active neutral surface, never a status color. |
| `--cr-surface-inset` | `#070B11` | Transcript and code/log well. |
| `--cr-line-subtle` | `#1C2837` | Hairline group separation. |
| `--cr-line-strong` | `#2A3A4E` | Focus-adjacent or selected-structure border. |
| `--cr-text-primary` | `#F3F7FC` | Primary labels, metrics, and selected identity. |
| `--cr-text-secondary` | `#A9B7C8` | Supporting labels and metadata. |
| `--cr-text-tertiary` | `#718198` | Provenance, disabled metadata, and quiet labels. |
| `--cr-text-disabled` | `#4D5D72` | Disabled copy only; never the sole error/connection indication. |
| `--cr-accent` | `#8B7CFF` | Signature iris. Focus, selection, links, active navigation, and primary reversible controls only. |
| `--cr-accent-hover` | `#A89DFF` | Hover/pressed-lift variant of the signature accent. |
| `--cr-accent-ink` | `#090711` | Text/icon on solid iris controls. |
| `--cr-accent-wash` | `rgba(139, 124, 255, 0.14)` | Selected row/card field and subtle active background. |
| `--cr-focus-ring` | `#C2B9FF` | Two-pixel visible keyboard focus ring, brighter than the accent for a clear non-color-only state change. |
| `--cr-status-running` | `#55B8FF` | Lifecycle running. Blue, plus orbit/spinner glyph and `RUNNING` word. |
| `--cr-status-queued` | `#AAB7C6` | Lifecycle queued. Neutral silver, plus hollow-circle glyph and `QUEUED` word. |
| `--cr-status-done` | `#6EE7B7` | Lifecycle done. Teal-green, plus check glyph and `DONE` word. |
| `--cr-status-failed` | `#FF7A91` | Lifecycle failure. Rose, plus cross glyph and `FAILED` word. |
| `--cr-status-timeout` | `#FFC15C` | Lifecycle timeout. Gold, plus clock glyph and `TIMEOUT` word. |
| `--cr-status-retry` | `#78D6D0` | Lifecycle retry. Cyan-teal, plus return-arrow glyph and `RETRY` word. |
| `--cr-status-unknown` | `#8596AA` | Unknown lifecycle. Slate, plus question glyph and `UNKNOWN` word. |
| `--cr-attention-off-track` | `#FF8AA1` | Heuristic attention only. Rose-pink, triangle icon, `OFF TRACK` word, and Flags-only placement distinguish it from failure. |
| `--cr-attention-stalled` | `#FFD27D` | Heuristic attention only. Warm gold, square icon, `STALLED` word, and Flags-only placement distinguish it from timeout. |
| `--cr-attention-neutral` | `#D1D9E6` | Unclassified `ATTENTION`, diamond icon, and Flags-only placement. |
| `--cr-data-model-a` | `#9A8CFF` | Reserved future categorical model color A. Do not render until a structured per-cell `model` field exists. |
| `--cr-data-model-b` | `#5CC8FF` | Reserved future categorical model color B. Do not render until a structured per-cell `model` field exists. |
| `--cr-data-model-c` | `#7DE0B8` | Reserved future categorical model color C. Do not render until a structured per-cell `model` field exists. |
| `--cr-data-model-d` | `#FFC875` | Reserved future categorical model color D. Do not render until a structured per-cell `model` field exists. |
| `--cr-overlay` | `rgba(2, 5, 10, 0.72)` | Modal scrim that maintains board context without competing with the active sheet. |

**Semantic-color rule:** no status is ever communicated by color alone. Existing text status and
glyph rendering stay mandatory. Status family, label, icon shape, and location are redundant
channels, which avoids red/green-only decisions for deuteranopic users.

### Typography

| Token | Value | Role and decision |
| --- | --- | --- |
| `--cr-font-sans` | `Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif` | Uses the current local/system-first approach; no network dependency. The system fallback keeps platform rendering fast and credible. |
| `--cr-font-mono` | `ui-monospace, "SFMono-Regular", "Cascadia Code", "Roboto Mono", Consolas, monospace` | IDs, telemetry, transcript, code, and table numerals only. |
| `--cr-text-2xs` | `0.6875rem / 1rem` | Provenance and compact timestamp. |
| `--cr-text-xs` | `0.75rem / 1rem` | Badges, table metadata, nav labels. |
| `--cr-text-sm` | `0.875rem / 1.25rem` | Form controls and supporting data. |
| `--cr-text-base` | `1rem / 1.5rem` | Default readable body and cell/session names. |
| `--cr-text-lg` | `1.125rem / 1.5rem` | Panel and detail titles. |
| `--cr-text-xl` | `1.5rem / 1.875rem` | Board title and selected cell identity. |
| `--cr-text-2xl` | `2rem / 2.25rem` | Status-board headline metric. |
| `--cr-text-3xl` | `2.75rem / 3rem` | 1440p reported-spend hero only. |
| `--cr-weight-regular` | `400` | Long-form reading and transcript. |
| `--cr-weight-medium` | `500` | Labels, table headings, and field names. |
| `--cr-weight-semibold` | `600` | Board titles, key metric, selected identity. |
| `--cr-tracking-label` | `0.08em` | Small metadata labels only; replaces the audit's excessive all-caps hierarchy. |
| `--cr-tracking-title` | `-0.02em` | Board/metric titles for a more deliberate, premium hierarchy. |

### Spacing, Shape, Elevation, and Layout

| Token | Value | Role and decision |
| --- | --- | --- |
| `--cr-space-1` | `0.25rem` | Icon-to-label and tight inline gap. |
| `--cr-space-2` | `0.5rem` | Compact metadata and segmented control gap. |
| `--cr-space-3` | `0.75rem` | Card internal grouping. |
| `--cr-space-4` | `1rem` | Default card padding and board control spacing. |
| `--cr-space-5` | `1.25rem` | Standard panel padding. |
| `--cr-space-6` | `1.5rem` | Board gap and desktop panel padding. |
| `--cr-space-8` | `2rem` | Major board section separation. |
| `--cr-space-10` | `2.5rem` | Wide-screen board breathing room. |
| `--cr-radius-sm` | `0.5rem` | Inputs, small controls, and status badges. |
| `--cr-radius-md` | `0.75rem` | Cards, stage tiles, and controls. |
| `--cr-radius-lg` | `1rem` | Major panels and modal/sheet corners. |
| `--cr-radius-xl` | `1.5rem` | Mobile sheet top corners only. |
| `--cr-shadow-1` | `0 1px 0 rgba(255,255,255,0.03) inset` | Subtle panel lift without a border wall. |
| `--cr-shadow-2` | `0 12px 32px rgba(0,0,0,0.22), 0 1px 0 rgba(255,255,255,0.03) inset` | Selected/raised card or popover. |
| `--cr-shadow-3` | `0 24px 64px rgba(0,0,0,0.46), 0 1px 0 rgba(255,255,255,0.05) inset` | Modal sheet and System dialog. |
| `--cr-touch-target` | `2.75rem` | 44px minimum interactive target, preserving the audit's mobile accessibility baseline. |
| `--cr-shell-rail-height` | `4rem` | Global top bar height. Taller than current 48px to let connection and primary signal breathe. |
| `--cr-nav-width` | `5.25rem` | Desktop icon-first left rail; labels appear in tooltip/accessible text, not as another dense column. |
| `--cr-detail-width` | `28rem` | Default desktop detail width for readable transcript/control layout. |
| `--cr-detail-width-wide` | `32rem` | Wide-desktop detail width. |
| `--cr-board-max` | `100rem` | Maximum usable board width, preventing 1440p content from becoming a stretched field. |

### Motion

| Token | Value | Role and decision |
| --- | --- | --- |
| `--cr-motion-instant` | `100ms` | Focus/pressed state only. |
| `--cr-motion-fast` | `150ms` | Hover, selected treatment, tooltip, and compact filter transition. |
| `--cr-motion-base` | `200ms` | Sheet, drawer, card state transition. |
| `--cr-motion-slow` | `240ms` | Board-level entrance only when explicitly navigated, never on polling. |
| `--cr-ease-standard` | `cubic-bezier(0.2, 0, 0, 1)` | Decelerating surface motion. |
| `--cr-ease-emphasis` | `cubic-bezier(0.16, 1, 0.3, 1)` | Sheet/dialog entrance with no bounce. |
| `--cr-pulse-duration` | `1800ms` | Running/status-dot breathing; use opacity only, not layout or color cycling. |

Under `prefers-reduced-motion: reduce`, every duration becomes `1ms`, all repeating animation is
disabled, and live state remains visible through copy, icon, and timestamp. This retains the
current audit baseline while making the intended behavior explicit.

## Layout and Information Hierarchy

### Desktop Operations Wall: 1440px and Above

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ Control Room     [LIVE dot • connected]    14 running / 38 cells    $12.84 spend   System   │
├──────────┬──────────────────────────────────────────────────────────────────────────────────┤
│ Fleet    │ Board eyebrow / title                    [range or refresh context]               │
│ Status   │ ┌ Pipeline health ──────────────────────────────────────────────────────────────┐ │
│ Flags  3 │ │ Execute 14/22      Analyze 3/8       Review 2/8                              │ │
│ Sessions │ └─────────────────────────────────────────────────────────────────────────────┘ │
│ Routing  │ Filters / search / density                               visible fleet count      │
│          │ ┌──────────────────── live matrix field ───────────────────────────────────────┐ │
│ System   │ │ compact status cells, grouped by lifecycle with spatial density               │ │
│          │ │ selected/risk cells have elevated, labelled treatment; no decorative noise   │ │
│          │ └─────────────────────────────────────────────────────────────────────────────┘ │
└──────────┴──────────────────────────────────────────────────────────────────────────────────┘
```

- The header is an **instrument strip**, not a duplicate dashboard: brand/context, one honest
  connection state, running count, reported spend, and System entry. Data comes from
  `GET /api/matrix` telemetry plus the page-lifetime `/api/status` SSE
  (`control_room_refresh_audit.md` §Route Inventory, `/api/matrix` and `/api/status`).
- The 84px nav rail preserves five boards and the System overflow. Active destination uses iris
  surface wash and a 3px leading indicator; flag count is a small number plus triangle, never
  only a colored dot. It preserves the current board model and no route changes.
- Board content uses `--cr-board-max` and `--cr-space-8` rather than filling every pixel. This
  creates a composed, expensive-feeling field at 1440p while retaining dense operational data.
- Detail remains an optional right dock at `28rem`; it overlays no content and opens only on
  selection, preserving the one-context handoff from the audit.

### Laptop: 1024px to 1439px

- Retain the top instrument strip and icon-first rail.
- Fleet uses 180px comfortable cells or 136px compact cells; no third metric rail is introduced.
- Detail docks at `24rem` on widths at or above 1180px. From 760px to 1179px it becomes a
  modal side sheet over the board, so Fleet retains meaningful width; this is a layout change
  only and must preserve selection, focus, and EventSource ownership.
- Status cards form a 2x2 arrangement, and stage health stays a three-part horizontal band.
- Tables retain horizontal scroll rather than collapsing evidence into unreadable labels.

### Mobile and Narrow Laptop Guard

- Keep the existing bottom navigation under 760px, safe-area padding, 44px targets, and one
  modal detail sheet. These are established in the audit as working foundations.
- The header reduces to room identity, connection state, active running count, and System.
  Spend remains on Status rather than becoming a truncating micro-metric.
- Fleet defaults to compact list cards. Matrix density is expressed through left status rails,
  phase/current-state, and scan-friendly count blocks rather than a literal tiny heatmap.

## Component Inventory

Every component names the data it may render. "No new data" is a deliberate constraint, not an
omission.

| Component | Redesign | Existing source and fields | Interaction / contract guard |
| --- | --- | --- | --- |
| Instrument header | Near-black strip with room name, one live-state capsule, running count, reported spend, quiet UTC clock, theme and System controls. Keep metrics sparse. | `GET /api/matrix`: `telemetry.available`, `reported_cost`, `history_capped`, `cells`; `/api/status` default message `{cell_id,status}`. Audit: §Route Inventory and §SSE Inventory. | Show `LIVE`, `RECONNECTING`, `OFFLINE`, or `CONNECTING` from existing browser state only. Do not attach a second stream or interpret SSE comments. |
| Navigation chrome | Icon-first rail, iris active wash, slim status count for Flags, System parked at bottom. Replace font glyphs with inline SVG whose accessible label matches the existing text label. | `GET /api/flags?limit=50`: `flags.length`; current board in shell state. Audit: §JavaScript Architecture. | Navigation remains one DOM nav and five destinations plus System. A flag count suggests, never auto-navigates. |
| Pipeline band | Three low-surface tiles with progress number, running dot, and a one-line status distribution. | `GET /api/matrix`: `stages.execute|analyze|review.{total,done,running,queued,failed,retry,timeout}`. | Keep the one existing `#pipeline-stages` node and reparenting approach; no duplicated ID or data writer. |
| Fleet matrix | A first-class responsive field. Comfortable mode uses “signal tiles”; compact mode uses a dense mosaic of short cards. Each tile shows status icon/word, human-readable clipped ID, phase, and latest cost only when present. Group/rhythm come from lifecycle state, not arbitrary borders. | `GET /api/matrix`: `cells`, `phases[cell_id].{name,index,total}`, `telemetry.cells[cell_id].samples`; selected-stream live overlays use `step_finish` cost/tokens. Audit: §Route Inventory, §SSE Inventory. | Retain one `button.cell-select` per cell, keyed reconciliation, delegated selection, filtering, and existing density preference. No per-cell model/condition parsing. |
| Fleet density legend | Top-right quiet key shows lifecycle icon+word and count. It makes the “heatmap-ish” field legible without a separate chart. | `GET /api/matrix`: `cells`; counts are already calculated from cell statuses. | It is presentational only. No new aggregate or status category. |
| Status board | Hero spend in 2xl/3xl, burn trace in an inset “signal well,” tokens and connection as supporting stacked metrics, pipeline band below. | `GET /api/matrix`: `telemetry.{reported_cost,input_tokens,output_tokens,history_capped,provenance}`, `stages`; `/api/status` browser connection state. | Preserve the existing retained-window provenance and `history_capped` qualifier. Never portray reported spend as a complete billing total. |
| Supervisor Flags | Editorial alert ledger rather than equal cards: severity icon/word, title, reason, model, recency/activity, review availability, source/degraded strip. Rose and gold are confined to this axis. | `GET /api/flags?limit=50`: `{source,degraded,warnings,flags[]}` and `flag.{session_id,flag_id,status,title,why,model,at,last_activity_at,review}`. | List remains keyed by `session_id`, selected rows open Detail only, and board has zero mutations. Keep `Supervisor flags. You decide.` visible. |
| Routing | Read-only analysis surface with a short “coverage” summary from `_meta`, followed by two calm, full-width data tables. Model names are text-first; no unsupported per-model fleet encoding is borrowed here. | `GET /api/routing`: `_meta`, `per_task[].{task,routing,escalate_model,default_model,best_correctness_model,best_efficiency_model}`, `strategies[name].{n,total_cost,avg_correctness}`, `routing_distribution`. | Preserve lazy fetch and refresh control. Empty state must say data is absent, not that routing is healthy/unhealthy. |
| Design sessions | Two composable zones: “Design work” launcher + recent design session timeline. Session rows use state, kind, revision, model/workdir and updated time; selected row receives iris contour. | `GET /api/design-sessions`: `sessions[].{portal_id,stream_id,kind,title,model,workdir_label,lifecycle_state,draft_state,revision,created_at,updated_at}`; selected draft `GET /api/design-sessions/<id>/spec`. | Start/save/run/send/steer stay in Detail/control forms with existing POST payloads and idempotency. The board stays an index, not an action wall. |
| Claude sessions | Separate “Background agents” zone: daemon health line, owned/external ownership treatment, task, model, workdir, and activity/relay state. External state is intentionally quiet and not styled as a failure. | `GET /api/claude-agents`: `agents[].{id,status,owned,relay_active,task,title,model,cwd}`; `GET /api/claude-agents/daemon`: `{running,pid}`. | Start/stop/respawn/rm/steer remain Detail actions and obey the current server ownership gate. External log tail stays the existing on-demand text endpoint. |
| Detail surface | Darker “focus well” with identity/status/phase/cost in the title zone, a terminal transcript with a non-scrolling control rail, then the selected read/act panel. | `/api/events/<cell_id>` default message plus `replay_complete:{cell_id}`; normalized reasoning/text/tool/step events. External Claude uses `GET /api/claude-agents/<id>/logs`. | Keep exactly one transcript feed and one selected stream. Follow/pause/clear/jump-live semantics do not change. |
| System sheet | On desktop, composed dialog; on mobile, modal bottom sheet. Registry becomes a filter bar, result table, and contained lineage viewer. Queue actions form a clearly separated control block. | `GET /api/registry` fields `{knowledge_id,source_type,lifecycle_state,observed_at,logical_locator,entity_id}`; `GET /api/registry/<id>` `{record,causes_record}`; existing queue POST routes. | Repair modal semantics in implementation: labelled modal, focus trap, Escape, return focus. Queue actions retain existing confirmation/idempotency. |
| Actions and confirmation | Iris solid for reversible primary controls; rose outline plus existing typed door for irreversible actions. Use a shared in-product confirmation treatment rather than native browser dialogs only when every existing confirmation and server check stays intact. | Existing mutation endpoints and form state, detailed in audit §Route Inventory. | No visual change may make a POST automatic, hide its blast radius, or bypass typed confirmation. |

## Matrix Data Visualization

### What Can Ship With Current Data

The matrix can be heatmap-like in **spatial density and lifecycle treatment**, but it cannot be a
true condition-by-model heatmap without data the API does not provide.

1. **Status field:** arrange currently urgency-sorted, keyed cell tiles in a regular grid. Each
   tile uses a 3px left status rail, icon, word, and a low-contrast surface. Running cells use a
   single calm orbit dot; failure/timeout tiles gain stronger edge contrast, not a flashing fill.
   Source: `GET /api/matrix.cells` (`cell_id -> status`) and audit §Route Inventory.
2. **Pipeline context:** the three pipeline tiles sit directly above Fleet. This makes an
   operator read stage blockage before individual cell density. Source: `GET /api/matrix.stages`.
3. **Phase badge:** show `index/total` plus `name` only when `phases[cell_id]` exists. Source:
   `GET /api/matrix.phases`; do not generate a phase from cell ID.
4. **Cost activity:** show an understated latest reported cost marker only when the retained
   samples or selected-stream overlay includes cost. Source: `telemetry.cells[cell_id].samples`
   and normalized `step_finish.part.cost`; retain “reported” language.
5. **Density modes:** comfortable is 180px-min tiles with phase/cost; compact is 136px-min tiles
   with status, shortened cell ID, and phase/cost as available. This is a CSS presentation of
   existing keyed nodes, not a new renderer or data model.

### Reserved, Not Shippable in This Refresh

| Requested encoding | Why it cannot be shown honestly today | Reserved visual treatment when API adds the field |
| --- | --- | --- |
| Condition badge | `/api/matrix.cells` has only cell ID and status. The audit explicitly prohibits parsing compound IDs for condition. | A text badge with neutral outline, e.g. `clean`, `bad seed`, `early degrade`, never a color-only condition marker. Requires `cells[cell_id].condition`. |
| Per-model color encoding | The matrix has no structured per-cell model; only Flags, Design, and Claude rows expose model strings. | A small four-color left-edge segment, paired with text/tooltip and deterministic legend. Requires `cells[cell_id].model`; use the reserved `--cr-data-model-*` tokens. |
| Actual SSE heartbeat meter | Server `ping` frames are SSE comments; browser `EventSource` does not surface them. | A last-observed-event latency indicator only if the service emits a timestamp/counter or browser state explicitly measures last status event. |
| Confidence/quality heatmap | Matrix response supplies no per-cell confidence, correctness, or quality metric. | A separate diverging/ordinal visualization only after an explicitly measured field is added; never derive quality from lifecycle alone. |

## State Design

State should be unmistakable even in a screenshot. It must use existing fields and local browser
state; none of the states below permit invented telemetry.

| Surface | Loading | Empty / no-data-yet | Live / healthy | Degraded / stale | Hard error |
| --- | --- | --- | --- | --- | --- |
| Header / connection | Quiet iris dot with `CONNECTING`; metric values use em dash, not zero. | Not applicable. | Small blue running dot plus `LIVE` from both current matrix/status browser state. | Gold ring plus `RECONNECTING` when EventSource reports reconnecting; retain last known metrics with `last updated` age. | Rose outlined `OFFLINE`; no pulsing; report unavailable, do not turn data into zero. |
| Fleet / matrix | Three-to-six low-contrast skeleton tiles preserving final density. | Centered sparse state: `No cells queued or retained` and one sentence explaining that the matrix appears after work is queued. | Status mosaic, pipeline band, count legend, and update age. | Keep retained keyed cells, add a gold “snapshot delayed” strip with age; no layout shift. | Retain last usable cells behind a rose “Fleet snapshot unavailable” strip. If no prior data exists, show error state rather than an empty healthy grid. |
| Pipeline band | Three skeleton stage bars labelled Execute, Analyze, Review. | `Waiting for first matrix snapshot`; never show all zeros as success. | Counts and lifecycle key. | Gold provenance `last snapshot <age>`; counts stay visibly stale. | Rose outlined strip explaining stage health is unavailable. |
| Status | Metric blocks use shimmering-free placeholder rules and “waiting for telemetry” copy. | `No reported cost samples yet`; burn trace renders a baseline, not a fake chart. | Spend/burn/tokens/connection and retained-window provenance. | Gold `retained window may be delayed` provenance; exact existing cap marker remains. | Rose message scoped to telemetry, while Fleet may still be visible from last state. |
| Flags | Three compact row silhouettes, source label `checking supervisor`. | Calm check icon and `No sessions need attention`; retain the supervisor boundary copy. | Severity-led rows with source, flag count, and exact activity ages. | Gold source strip (`file` / delayed / warning) and retained rows, matching API `degraded`/`warnings`. | Rose `Supervisor state unavailable`; retained flags remain visible when browser state has them. |
| Routing | Table-header skeleton and three row bands after explicit open/refresh. | `No routing data yet` plus the API-provided reason/note if present. | Coverage summary and two tables. | Not applicable unless the API provides stale metadata; do not invent it. | `Routing unavailable` with retry control; clarify live Fleet remains unaffected. |
| Design sessions | Timeline/row skeleton plus disabled launcher workdir choice only while options load. | `No portal-owned design sessions yet`; keep launchers visible. | Timeline rows show state, kind, revision, model/workdir, selected contour. | Preserve previous rows and show small gold `session list delayed`; do not replace context with a paragraph. | Rose inline failure above retained list; launch form reports its own mutation error locally. |
| Claude agents / daemon | Roster skeleton plus daemon `CHECKING`. | `No Claude background sessions observed`; daemon separately reports `NOT RUNNING`. | Roster rows, ownership label, daemon status/PID. | `Supervisor unavailable` is gold/neutral operational absence, not failure; clearly distinguish it from daemon stopped. | Transport/client error uses rose line and preserves prior roster. |
| Registry | Table skeleton inside System dialog; filters remain visible. | `No registry entries match this filter` with filter reset affordance. | Dense table and contained lineage panel. | No stale claim without API metadata. | Rose inline `Registry unavailable`; System and Queue controls remain usable. |
| Detail transcript | Inset terminal shows `Connecting to retained history`. | `No retained events observed` or `No retained design events observed`, matching selected type. | Small stream state, replay/live divider, ordered transcript rows. | Gold `Reconnecting - showing received events`; preserve follow/pause controls. | Rose persistent stream banner within the transcript pane, with current selected identity and no implied retry time. |
| Mutations / one-way door | Button has a deterministic label such as `Saving...`/`Interrupting...`; disable duplicate activation. | Not applicable. | Success uses text confirmation and a check icon, then returns control to normal. | Not applicable. | Local inline error retains user-entered input and original idempotency/retry semantics. Typed doors remain distinct from standard inline errors. |

## Micro-Interactions and Liveness

| Interaction | Behavior | Honest trigger and guard |
| --- | --- | --- |
| Connection dot | A 6px dot gets one 1.8s opacity-breath only in `LIVE`; `CONNECTING`, `RECONNECTING`, and `OFFLINE` are static, labelled states. | Existing `matrixState` and `statusState` render logic. Do not listen for or imply visibility of `: ping` comments. |
| Running cell | Running tile has a subtle orbital dot at its status glyph and a 150ms iris selection lift on click. | `cells[cell_id] === "running"`; selection is current `selectedId`. No layout-changing pulse and no animation on poll. |
| Selected cell | Tile elevates with `--cr-shadow-2`, iris inset ring, and a 2px left-edge accent. Detail opens with a 200ms surface transition. | Existing selected-type/ID state and current detail logic. Preserve single stream replacement before selection attachment. |
| Stage/count update | Number changes fade between values over 150ms; no count odometer. | Matrix poll updates only. A no-op poll must produce zero writes under existing keyed-list discipline. |
| Flag arrival/change | New or revised flag gets a single 200ms highlight wash, then settles. Its row never moves solely because assessment content changed. | Existing `flag_id` revision signature and `session_id` stable key. No auto-navigation or sound. |
| Session activity | A small live dot appears only for an active lifecycle or `relay_active !== false`; a paused relay uses labelled muted state. | Design lifecycle and Claude `{status,relay_active}` fields. Do not infer activity age without a supplied timestamp. |
| Filters/density | Chip and density control use 150ms color/surface transition; grid reflows without entry animation. | Existing filter/search/density state. No per-card animation on every poll. |
| System/detail sheets | Surface opacity/translate on explicit open/close only; no motion on content update. | Existing shell/detail controls. Reduced motion disables translation. Implementation must add the audit-required System focus containment. |
| Typed confirmation | Opening a danger door uses a 200ms border/surface reveal, focuses its field, and leaves destructive button disabled until exact phrase. | Existing queue and supervisor typed confirmation. Other confirmations may adopt it only with equivalent server/body/idempotency behavior. |

## Implementation Notes for the Next Phase

1. Add the token block first, then replace component literals incrementally. This minimizes
   visual drift and lets screenshot QA identify which component changed.
2. Keep classic-script load order and `window.ControlRoom*` boundaries. The requested refresh is
   not a module-system migration (`control_room_refresh_audit.md` §Known Architecture Smells).
3. Do not add a new fetch, poll, `EventSource`, route, or data store for visual convenience.
4. Preserve `textContent` DOM construction and keyed Fleet/Flags/Design/Claude reconciliation.
   A premium UI that loses focus every five seconds is a regression.
5. Use inline SVG only for decorative/navigation icons; retain existing accessible names, button
   labels, glyph+word status semantics, and live regions.
6. Treat the System sheet accessibility repair as a required polish item: dialog semantics,
   focus trap, Escape, scrim dismissal, and return focus. It is not an optional aesthetic change.
7. Validate on an alternate port only, never by interrupting the live port-8000 portal. Manual QA
   must cover 1440px wall, 1024px laptop, 760px transition, 420px phone, keyboard-only flow,
   reduced motion, light/dark, every state in the table above, both SSE reconnect paths, and all
   existing mutation confirmation flows.

## Design Log

| Item | Result | Evidence |
| --- | --- | --- |
| Token table | **PASS** | Color, typography, spacing, radius, shadow, layout, and motion tokens all have explicit names and values in §Design Tokens. |
| Component inventory | **PASS** | Every redesigned component names its existing API/SSE source and fields in §Component Inventory. |
| Matrix truthfulness | **PASS** | §Matrix Data Visualization distinguishes current status/phase/cost density from unsupported condition/model/heartbeat encodings. |
| State design | **PASS** | §State Design specifies loading, empty, live, degraded, and hard-error behavior for every portal surface. |
| Design-only scope | **PASS** | This phase adds this document only; no static, server, route, or SSE edit is proposed or made. |
| No-regression guard | **PASS** | §Design Thesis and §Implementation Notes retain 28 routes, two streams, safe rendering, keyed lists, idempotent actions, and alternate-port validation. |

**Design result: PASS.** The next phase has a complete premium visual system and an explicit
boundary between visual treatment and unmeasured data. It can make Control Room feel materially
more composed without changing what the portal knows, serves, or controls.
