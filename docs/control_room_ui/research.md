---
status: accepted
---
# Control Room UI Redesign — Research Reference

> Phase: **research** (`control_room_ui_redesign` spec, phase 1 of 3).
> This document collects a grounded reference set and extracts reusable patterns. The
> **design** phase (`docs/control_room_ui/design.md`) consumes it; the **verify** phase
> traces every design decision back here. Nothing in this file edits `admin/` or deploys.

## Why this doc exists

The Control Room is the **fleet-management surface for AI agents**: the "fleet" is the set
of running workflows/cells, the "node" is one cell, the "alerts" are supervisor flags, and
the "controls" are routing/steer/interrupt. The spec's `problem` is blunt — the current
surface (`admin/server.py` + `admin/static/`) is *clunky and hard to navigate, especially on
mobile* — and its `hard_rules` forbid taste-based design: every recommendation must cite a
research source, mobile must be first-class (one-handed, specified explicitly), and the
**flag-only / observe-only rail** must stay visibly intact.

This document does three things:

1. **§0 — Constraints**: the 28 real routes, data shapes, and the current visual/mobile
   system. The redesign must map to these, not invent endpoints.
2. **§1 — Reference**: concrete, named products/consoles organized by the spec's four
   research-target families, each captured as *what it solves / layout & navigation / visual
   system / mobile treatment*.
3. **§2 — Patterns**: 12 reusable patterns, each with the example that embodies it and a
   direct mapping to the Control Room.

---

## 0. Constraints (the ground truth the redesign must map to)

### 0.1 The 28 routes (real endpoints — the design may not invent more)

From `admin/server.py`'s docstring. Five API categories + the static shell:

| Category | Routes | Read (GET) | Write (POST — actuation) |
|---|---|---|---|
| **Legacy telemetry** (6) | `/api/matrix`, `/api/status` (SSE), `/api/events/<cell_id>` (SSE), `/api/routing`, `/api/experiments`, `/api/queue/reinterleave` | matrix, status, events, routing | experiments (enqueue/clear), queue/reinterleave |
| **Supervisor flags** (3) | `/api/flags`, `/api/flags/<id>/steer`, `/api/flags/<id>/interrupt` | flags | steer, interrupt |
| **Registry** (2) | `/api/registry`, `/api/registry/<entity_id>` | registry, lineage | — (read-only by construction) |
| **Design sessions** (7) | `/api/design-sessions` (GET/POST), `/…/<portal_id>/spec`, `/input`, `/interrupt`, `/save`, `/run` | list, spec | create, input, interrupt, save, run |
| **Claude background sessions** (9) | `/api/claude-agents` (GET/POST), `/…/<id>/logs`, `/stop`, `/respawn`, `/rm`, `/steer`, `/daemon` (GET), `/daemon/stop` (POST) | roster, logs, daemon | start, stop, respawn, rm, steer, daemon/stop |
| **Static shell** (1) | `GET /` | index.html | — |

**Reads (GET) number 13; actuation (POST) numbers 15.** Every one of the 15 POST routes sits
behind a loopback + same-origin + JSON + size-cap + `Idempotency-Key` trust boundary. Reads
dominate the *visual surface and frequency* (a single GET `/api/matrix` renders the whole
fleet), while actuation is rare, deliberate, and gated. The design must make *read surfaces*
the default visual treatment and make *actuation surfaces* deliberately gated and visually
distinct — this is exactly the flag-only rail's contract. (Corrected during verify: the
earlier draft miscounted this as "~13 POST".)

### 0.2 Data shapes the UI already renders

- **Matrix cell** (`GET /api/matrix`): `total`, `queued`, `running`, `done`, `failed`,
  `timeout`, `cells{...}` (id → status), `phases{id → {name,index,total}}`, `stages{execute,
  analyze, review}`, `telemetry{reported_cost, input_tokens, output_tokens, cells{id →
  {reported_cost, input_tokens, output_tokens, latest_cost, samples[], history_size}}}`.
- **Flag** (`GET /api/flags`): `flag_id`, `at`, `session_id`, `title`, `model`, `status`
  (`off_track` | `stalled` | other→`ATTENTION`), `why`, `last_activity_at`, `review{state:
  mapped|snapshot|stale|unavailable, cell_id, source}`.
- **Design session**: `portal_id`, `stream_id`, kind, intent, model, workdir, draft state.
- **Claude agent**: `id`, ownership (`owned`/`external`), task, model, workdir, daemon status.
- **Registry row**: `source_type`, `lifecycle_state`, `entity_id`, `observed_at`, `causes`.

### 0.3 Current visual system (what exists today)

Dark-only. Palette: ink `#07090c/#0d1117/#151b23`, line `#2a3441/#46566a`, text
`#e8edf2`, muted `#9ba8b8`. Status vocabulary: `cost/amber #ffbf47`, `queued/gray #8793a1`,
`running/blue #43b9ff`, `done/green #57d38c`, `failed/red #ff6470`, `timeout/purple #c995ff`,
`unknown #aab3be`. Type: system `sans` for UI, `mono` for IDs/tokens/data. 14px base. Status is
already *not* color-only — each card pairs a color with a glyph (`○ ◔ ✓ × ◷ ↻ ?`), which is
correct and must be preserved (see §2.2).

### 0.4 Current mobile treatment (what is broken)

At ≤759px the three-column grid becomes a **single long stack**: command rail → needs-attention
→ fleet → transcript (min 55vh) → controls. Navigation is anchor-jumping (`Back to fleet`,
`Jump to transcript`, `Jump to observed activity`); there is **no sticky nav, no bottom sheet,
no tab bar**, and nothing is reachable one-handed. Cards collapse to one column only at ≤420px.
The result is a very long scroll with no persistent orientation. This is the primary thing the
redesign must fix, and it is the main gap the research below targets.

---

## 1. Reference by research-target family

Each entry follows the spec's required capture: **what it solves / layout & navigation /
visual system / mobile treatment**.

### 1.1 Fleet & agent-management consoles

#### 1.1.1 LangSmith (LangChain) — *LLM trace/run fleet observability* — the closest analog

- **Source:** LangSmith (`smith.langchain.com` / `docs.smith.langchain.com`).
- **What it solves:** Monitoring a *fleet of LLM agent runs* — exactly the Control Room's
  problem. Each "run" is an agent execution; each run has a status, latency, token count,
  cost, and a tree of child spans.
- **Layout & navigation:** A **filterable run list/table** is the home surface: columns for
  name, session, latency, tokens, cost, status; a left filter bar (project, time range,
  status, tags, metadata); clicking a run **drills into a trace tree**; a right-hand/side
  **detail panel** shows run metadata, inputs/outputs, and feedback. Navigation is list →
  detail, never everything-at-once.
- **Visual system:** Light, minimal; blue accent; **status as compact chips** (success/failed)
  with color *and* icon; monospace for IDs/timestamps; tabular-numeric alignment for
  latency/tokens/cost. Dense but scannable.
- **Mobile treatment:** Narrow-width responsive; the run table collapses toward cards;
  detail is a full-page push rather than a side-by-side pane.

#### 1.1.2 Langfuse / Helicone — *open-source LLM observability*

- **Source:** Langfuse (`langfuse.com`), Helicone (`helicone.ai`).
- **What it solves:** Trace/span/cost dashboards for LLM apps; Langfuse adds "sessions" that
  group traces, which maps directly to the Control Room's session→cell grouping.
- **Layout & navigation:** Trace table with session grouping, a cost/usage dashboard, filter
  chips; detail = trace tree + side metadata. Helicone emphasizes a cost-first summary bar.
- **Visual system:** Langfuse offers a dark mode; Helicone is light with strong data density.
- **Mobile treatment:** Responsive tables; primary navigation collapses to a hamburger/drawer.

#### 1.1.3 Kubernetes Dashboard + Lens — *container fleet management*

- **Source:** Kubernetes Dashboard (`github.com/kubernetes/dashboard`); Lens (`k8slens.dev`).
- **What it solves:** A fleet of containers/pods/nodes with live status; drill-down from
  cluster → namespace → workload → pod → logs/terminal.
- **Layout & navigation:** Left **resource nav** (Pods, Deployments, Nodes…); workload overview
  as **cards or tables** with status badges; per-resource **detail tabs** (Overview / Events /
  Logs / YAML). Lens adds a multi-cluster picker — "fleet of clusters" = "fleet of agents".
- **Visual system:** Status badges green/red/amber; dense tables; dark-capable; terminal
  surfaces for logs.
- **Mobile treatment:** The K8s dashboard is desktop-first (a cautionary counter-example);
  Lens ships a desktop app only. *Relevance: the drill-down hierarchy is the pattern to copy,
  not their mobile (they have none — that's what this redesign must beat).*

#### 1.1.4 GitHub Actions / Buildkite — *CI pipeline fleet + live logs*

- **Source:** GitHub Actions (`github.com/features/actions`); Buildkite (`buildkite.com`).
- **What it solves:** Many concurrent jobs across a fleet of runs; each job has a status, and
  each run streams live logs. Directly analogous to cells with live event streams.
- **Layout & navigation:** **Run list** with status icons (✓/✗/◔); a **job matrix**; clicking
  a job opens a **live log view** with step grouping (collapsible groups), log search, and
  "re-run" actions.
- **Visual system:** Status green/red/amber everywhere; monospace logs; tight spacing.
- **Mobile treatment:** GitHub's mobile web/app is strong: list → detail with a back affordance;
  Buildkite is desktop-first.

### 1.2 Mission-control / live-ops / incident dashboards

#### 1.2.1 PagerDuty — *incident queue + alert triage (the on-call gold standard)*

- **Source:** PagerDuty (`pagerduty.com`); sibling: Atlassian Opsgenie.
- **What it solves:** A prioritized **alert rail**: incidents surface, an operator acks/escalates,
  and the queue reorders by severity. The flag-only rail is a PagerDuty incident queue.
- **Layout & navigation:** **Incident list** sorted by severity (P1–P5, red→yellow); each row =
  title + service + assignee + age; ack is a **large one-tap action**; detail opens the
  incident timeline. Dedup/grouping **suppresses redundant noise** (see §2.9).
- **Visual system:** Severity **color + numeric level** (never color alone); red reserved for
  the highest severity; strong contrast; count badges.
- **Mobile treatment:** PagerDuty's mobile app is the canonical **one-handed alert triage**
  surface: a scrolling incident list, big tap targets (≥44pt), swipe/button to ack, a
  bottom-docked primary action. *This is the single best mobile reference for the flag rail.*

#### 1.2.2 Grafana — *dashboard wall + alerting*

- **Source:** Grafana (`grafana.com`).
- **What it solves:** Dense, glanceable metric dashboards; alert rules with a dedicated
  alerting pane; "a wall of charts you scan."
- **Layout & navigation:** **Panel grid** (drag/drop, adjustable density), sticky top toolbar
  with a time-range picker, left nav; alerting surfaces as a list of firing alerts.
- **Visual system:** Dark-mode-first near-black background; thin panel borders; colorful series
  lines; restrained chrome so data leads.
- **Mobile treatment:** Dashboards degrade poorly (desktop-first); Grafana's alerting is
  consumed via PagerDuty-style integrations. *Pattern to copy: the sticky toolbar + quiet
  chrome; pattern to avoid: non-responsive panels.*

#### 1.2.3 Datadog — *service/host map + monitors + Live Tail*

- **Source:** Datadog (`datadoghq.com`).
- **What it solves:** Fleet visibility at scale: the **host map** (a grid of squares, each
  colored by status) is a compact "fleet overview matrix"; **Live Tail** streams logs.
- **Layout & navigation:** Left nav rail; **host map** = tiled colored squares → click drills
  into a host detail; monitors list with status; Live Tail is a live monospace stream with a
  follow toggle.
- **Visual system:** Purple brand; status color language (green/amber/red); dense tables;
  monospace telemetry.
- **Mobile treatment:** Datadog's mobile app emphasizes alert push + incident triage, not
  dashboards — the same "read on desktop, triage on mobile" split this redesign needs.

#### 1.2.4 Better Uptime / Statuspage — *public incident + status surfaces*

- **Source:** Better Uptime (`betterstack.com`), Atlassian Statuspage (`statuspage.io`).
- **What it solves:** A **calm, glanceable status** view: green = all good; an incident banner
  when not. The "quiet empty state" for health.
- **Visual system:** Green/amber/red health; minimal; large status dot.
- **Mobile treatment:** Mobile-first by default. *Pattern to copy: the legible, non-shouting
  "healthy" empty state (§0.4's degraded-state requirement mirrors this).*

#### 1.2.5 Netdata — *real-time, ultra-dense telemetry*

- **Source:** Netdata (`netdata.cloud`).
- **What it solves:** Real-time system telemetry with thousands of metrics, sub-second updates,
  compact charts — the extreme case of "dense but glanceable."
- **Visual system:** Dark; tiny, tiled charts; subtle color coding. Demonstrates that density
  and calm can coexist when motion is minimal (values change, layout doesn't jump).

### 1.3 Modern dev-tool surfaces (calm, dense, keyboard-friendly)

#### 1.3.1 Linear — *the canonical calm, keyboard-first issue tracker*

- **Source:** Linear (`linear.app`) + their published "Linear Method" (`linear.app/method`).
- **What it solves:** A high-volume issue/team fleet kept *calm and fast*: quick capture, a
  powerful filter bar, minimal chrome, keyboard-first operation.
- **Layout & navigation:** **Left nav** (teams/projects) → **list/board** with a **filter/query
  bar** and **density control** → right-hand **detail pane**. Command palette (`⌘K`). Keyboard
  shortcuts for everything. **Status color system** is restrained: one accent + semantic
  statuses (Done=green, In Progress=blue, Canceled=gray).
- **Visual system:** Monochrome + a single accent; generous whitespace; tight typography;
  "calm" as an explicit design goal (fast, quiet, no shouting).
- **Mobile treatment:** Linear's mobile app reproduces the list → detail flow with a bottom
  tab bar and full-page detail push; density drops but scannability is preserved.

#### 1.3.2 Vercel (Geist) — *deployment fleet + build logs*

- **Source:** Vercel (`vercel.com`) + the Geist design system (`vercel.com/geist`).
- **What it solves:** A fleet of deployments/projects, each with build status and streaming
  build/function logs. The "deployment" ≈ the Control Room "cell."
- **Layout & navigation:** **Project → deployment list** (status chips: Ready/Building/Error +
  spinner), **live build log** with line streaming, a clean detail panel. Geist codifies the
  visual system: geometric sans (Geist), near-black/white, tight 4px-based spacing, minimal
  borders, status dots.
- **Visual system:** Monochrome + restrained accent; status conveyed by dot+label, not color
  wash; monospace for logs.
- **Mobile treatment:** Geist is responsive-first; deployment lists compact to cards; logs
  remain full-width monospace.

#### 1.3.3 Railway — *service fleet as tiles*

- **Source:** Railway (`railway.app`).
- **What it solves:** A fleet of services represented as **tiles/cards** with deploy status;
  one-click deploy; clean dark UI.
- **Layout & navigation:** Project canvas of service cards → click a card for detail +
  deploy logs. Card-as-node is the exact "fleet overview matrix" idiom.
- **Visual system:** Dark, rounded cards, status accents, minimal.
- **Mobile treatment:** Card grid stacks cleanly; detail is a push.

#### 1.3.4 Resend — *dense, scannable event log*

- **Source:** Resend (`resend.com`).
- **What it solves:** Email delivery logs — a dense table/list of events (to, subject, status
  delivered/dropped, timestamp) that stays scannable at volume.
- **Layout & navigation:** A single dense **list/table** with status chips and filters; detail
  drawer on click. Minimal nav; the log *is* the surface.
- **Visual system:** Calm, light/dark capable; status chips (delivered green, dropped red);
  monospace for IDs.
- **Mobile treatment:** The event table compacts to cards; filters stay sticky.

#### 1.3.5 Stripe Dashboard — *data-dense financial console*

- **Source:** Stripe (`stripe.com`).
- **What it solves:** Very high data density (payments, payouts, fees) kept legible.
- **Layout & navigation:** Left sidebar → dense tables with sortable columns → side detail
  panels; status badges; inline actions on rows.
- **Visual system:** Light; blue accent; tabular numerics; clear table headers; calm.
- **Mobile treatment:** Tables become cards; sidebar becomes a drawer. A benchmark for
  *respecting dense data on mobile without abridging it*.

### 1.4 Mobile-first responsive patterns for dense data

#### 1.4.1 Material 3 — bottom sheets, navigation bar, cards, touch targets

- **Source:** Material Design 3 (`m3.material.io`).
- **What it solves:** A spec for mobile-dense UIs: **modal bottom sheet** for drill-down,
  **navigation bar** (bottom tabs) for app-level nav, **cards** for lists, and **48dp minimum
  touch targets**.
- **Key mechanics to reuse:** Bottom sheet as the one-handed detail/inspector surface; bottom
  nav for 3–5 top-level destinations; card→list→table responsive compaction; `state layers`
  for pressed/focus.

#### 1.4.2 Apple HIG — sheets, navigation, safe areas, touch

- **Source:** Apple Human Interface Guidelines (`developer.apple.com/design/human-interface-guidelines`).
- **What it solves:** iOS navigation (push/detail, **sheets**, **swipe-back**), **44pt minimum
  touch targets**, **safe-area insets** (notch/home-indicator), and the pattern of moving
  secondary actions into a **toolbar** or **context menu** rather than crowding the screen.
- **Key mechanics to reuse:** `env(safe-area-inset-*)` for bottom-docked controls; one-handed
  reach (primary actions in the bottom ~40% of the screen); swipe-to-dismiss detail sheets.

#### 1.4.3 Responsive card → list → table compaction

- **Source:** The ubiquitous "responsive table" pattern, best exemplified by **GitHub, Linear,
  Stripe, Vercel** (and codified in MDN's responsive-table guidance + Adrian Roselli's
  `display: contents` technique).
- **What it solves:** Dense tabular data at 3 breakpoints: **card** (≤~420px, one per row),
  **list** (compact rows with a primary line + metadata line), **table** (full columns ≥~760px).
- **Key mechanics to reuse:** `display: contents` or data-attribute-driven layout so the *same
  DOM* restyles across breakpoints; a single source of truth for row content; hidden column
  headers only on the card variant (or reattached as inline labels).

#### 1.4.4 Sticky nav + persistent orientation

- **Source:** Datadog, Grafana, Linear (desktop), Material 3 `AppBar`, iOS `NavigationBar`.
- **What it solves:** The operator should never lose their place: a **sticky top command rail**
  (always-visible headline metrics) + a **sticky bottom tab bar** (mobile) provide orientation
  while a middle scroll region carries the detail.
- **Key mechanics to reuse:** `position: sticky` on top/bottom rails inside a `100dvh` flex
  shell; the scrolling region is the only thing that moves.

#### 1.4.5 Reference mobile apps to benchmark against

- **PagerDuty mobile** — one-handed incident ack (large targets, bottom primary action).
- **Linear mobile** — list → detail push, bottom tab bar, keyboard stays secondary.
- **GitHub mobile** — status icons in lists, back affordance, dense-but-tappable rows.
- **Datadog mobile** — alert-first triage, dashboards deferred to desktop.

---

## 2. Twelve reusable patterns

Each pattern: **the idea**, **the embodiment (source)**, **the mechanics**, **the Control Room
mapping**.

### 2.1 Fleet overview matrix (status-colored node grid)

- **Idea:** The fleet's home surface is a compact grid of unit cards, each colored/iconed by
  status, sorted urgency-first, so an operator scans health in one glance.
- **Embodiment:** Datadog **host map** (tiled status squares) + Railway's service-card canvas +
  Grafana's panel wall. The Control Room's existing `fleet-grid` already *is* this; the task is
  density + compaction, not reinvention.
- **Mechanics:** `auto-fill minmax()` card grid; one card per cell; status as a left-edge bar +
  glyph + word (color never sole signal); urgency-first sort (already in
  `core.sortCellIds`); a density toggle (comfortable/compact).
- **Control Room mapping:** `GET /api/matrix` `cells` → cards; `phases` → phase badge;
  `telemetry.cells[id].latest_cost` → cost line; sparkline → token history. Keep the pulse
  reserved for `running`.

### 2.2 Status color language (semantic, never color-only)

- **Idea:** A small, stable status vocabulary with **shape + glyph + word + color** redundancy,
  and a hard reserve on the most alarming color.
- **Embodiment:** PagerDuty severity (P1–P5 = numeric + color), GitHub status icons
  (✓/✗/◔), Linear's restrained status palette.
- **Mechanics:** The current palette is already good and already redundant (glyphs `○ ◔ ✓ ×
  ◷ ↻ ?`). Extend it to a **two-axis language**: *lifecycle* (queued/running/done/failed/
  timeout/retry) vs *attention* (off-track=red, stalled/attention=amber) — and keep these two
  axes **visually separate** (see §2.5), because supervisor flags are heuristic, not lifecycle.
- **Control Room mapping:** Reuse `status-*` classes for lifecycle; introduce a distinct
  `attention-*` family for flags so `failed` (red) and `off_track` (red) never read as the
  same kind of red.

### 2.3 Drill-down: overview → node detail → stream (progressive disclosure)

- **Idea:** Never show everything at once. Three depths: fleet (matrix) → node (cell/session
  facts) → stream (transcript/logs), with each step a push, not a side-by-side pile.
- **Embodiment:** Kubernetes/Lens (cluster → workload → pod → logs), Datadog (host map → host
  → traces), LangSmith (run list → trace tree → span), Linear (list → detail pane).
- **Mechanics:** A single selection model (the existing `selectedId`/`selectedType`); one
  detail surface; one live stream. The current app *already* does this on desktop; the redesign
  must preserve the "one terminal, one detail EventSource" invariant (§2.4's single-context
  rule) while making each depth a one-thumb push on mobile.
- **Control Room mapping:** `GET /api/matrix` (depth 1) → selection → `GET /api/events/
  <cell_id>` (depth 3) + a facts panel (depth 2). The flag→session review flow in
  `docs/supervisor_design.md §2` is already a drill-down and must stay single-context.

### 2.4 Single-context handoff (one live detail, one stream)

- **Idea:** Only one selected detail and one live EventSource may exist at a time; selecting a
  new node closes the prior source before opening the next.
- **Embodiment:** Vercel/Linear/GitHub detail push (one detail at a time); Datadog trace view.
- **Mechanics:** `core.replaceEventSource` already enforces close-then-open. The design must
  keep it: a detail *push* (not tabs that spawn parallel streams) and a persistent back
  affordance.
- **Control Room mapping:** Preserve the invariant from `docs/supervisor_design.md` ("the page
  never owns more than one global and one selected-detail EventSource").

### 2.5 Alert rail / needs-attention surface (bounded, prioritized, quiet-empty)

- **Idea:** A bounded, scrollable rail that surfaces only what needs a human; a nonzero count
  is visible but never forces the section open; the empty state is legible but honest.
- **Embodiment:** PagerDuty incident queue (the canonical alert rail); Grafana alerting;
  Better Uptime's healthy/incident states.
- **Mechanics:** Count badge (amber accent); rows with status word + title + one-sentence `why`
  (2-line clamp) + model/age metadata; **stable row identity** (`flag_id`) so polling updates
  in place without reordering or stealing focus; degraded-source state (`Supervisor data
  delayed`) when the source is down — never a false all-clear. All three states
  (no-flags / flags / degraded) are already specified in `docs/supervisor_design.md §1`; the
  redesign renders them, not reinvents them.
- **Control Room mapping:** `GET /api/flags` → the rail; poll on the same 5s cadence as the
  fleet snapshot.

### 2.6 Sticky controls / persistent command rail

- **Idea:** Headline telemetry and the primary navigation are **always visible**; only the
  middle scrolls.
- **Embodiment:** Datadog/Grafana sticky top toolbars, Linear's persistent bar, Material 3
  `AppBar` + `NavigationBar`.
- **Mechanics:** `100dvh` flex/grid shell: top rail (`position: sticky`) = identity + spend +
  burn + counts (the current `command-rail`); bottom tab bar on mobile = destinations; the
  middle region = the active board. On mobile this replaces the current anchor-jump soup
  (§0.4) with persistent orientation.
- **Control Room mapping:** The existing `command-rail` becomes the sticky top; the four boards
  (Fleet / Status / Flags / Sessions — see design phase) become bottom-tab destinations.

### 2.7 Mobile bottom-sheet drill-down (one-handed detail + controls)

- **Idea:** On mobile, the node detail + session controls live in a **modal bottom sheet**
  that slides over the fleet, keeping the fleet's scroll position and the primary action
  within thumb reach.
- **Embodiment:** Material 3 modal bottom sheet; iOS sheets; Linear/PagerDuty mobile detail.
- **Mechanics:** Sheet anchored to the bottom (safe-area aware via `env(safe-area-inset-*)`),
  with a drag handle, swipe-to-dismiss, and the primary action (Watch / Steer) docked at the
  bottom of the sheet. The *one-way* Interrupt stays a distinct, danger-styled inline door
  inside the sheet (it must not live in the dismiss path — see §2.8).
- **Control Room mapping:** Selecting a cell/flag/design/agent on mobile opens the sheet with
  the facts panel + the appropriate control panel (`#cell-control-panel`,
  `#supervisor-control-panel`, `#design-control-panel`, `#claude-agent-control-panel`) — the
  same panels desktop shows in the right column, restyled, not duplicated.

### 2.8 Sparse-but-clear controls + gated actuation (read vs. act)

- **Idea:** Read surfaces are the default; the few actuation surfaces are visually distinct,
  explicit, and — for one-way actions — gated by a typed confirmation.
- **Embodiment:** GitHub's destructive type-to-confirm (type the repo name), Linear's explicit
  confirm, Vercel's deploy confirm; PagerDuty's large explicit Ack; the Control Room's own
  existing Interrupt door.
- **Mechanics:** A visible **read/write boundary**: read-only attachments carry a quiet
  "READ ONLY" badge; reversible actions (Steer/Send) are `primary`-styled; irreversible
  actions (Interrupt, Stop daemon, Clear queue, `rm`) are `danger`-styled and behind a
  **two-step door** with typed confirmation (already implemented for Interrupt and daemon-stop
  — preserve it). Color alone must never distinguish "will do something" from "just viewing";
  pairing the danger color with a confirmation step does.
- **Control Room mapping:** The flag-only rail's "Supervisor flags. You decide." footer stays
  visible both when noticing and when acting (per `docs/supervisor_design.md`), and the gated
  Interrupt phrase (`INTERRUPT <session_id>`) remains the model for any new irreversible action.

### 2.9 Calm under load (quiet by default, loud only on delta)

- **Idea:** A busy fleet must not shout: motion and color are reserved for *state changes*,
  not for steady-state churn; nothing jumps.
- **Embodiment:** PagerDuty's alert dedup/grouping (suppress redundant noise); Stripe/Grafana's
  restrained animation; the current app's own `prefers-reduced-motion` handling.
- **Mechanics:** (1) limit motion to the existing `running` pulse and status *transitions*;
   (2) update rows in place by stable id so a 5s poll doesn't reorder the list; (3) announce
   only *new/changed* items via the polite/assertive live regions (already in `announce()`);
   (4) no layout shift when flags arrive (bounded rail); (5) honor `prefers-reduced-motion`.
- **Control Room mapping:** The rail's bounded max-height and stable-`flag_id` row updates are
  already specified (§2.5); the redesign extends the same discipline to the fleet grid (don't
  reflow cards on every poll).

### 2.10 Live stream / terminal surface (monospace, follow mode, jump-to-live)

- **Idea:** The transcript is a **live log**, not a page: monospace, a follow toggle, a
  pause, and a "jump to live" affordance when scrolled up.
- **Embodiment:** Vercel/GitHub Actions build logs, Datadog Live Tail, Resend logs, Netdata.
- **Mechanics:** `follow`/`pause`/`clear` controls (already present); `jump-live` appears only
  when the operator scrolled away; `replay_complete` boundary marks where replay ended and live
  begins. On mobile the terminal is a full-height push with a back affordance.
- **Control Room mapping:** `GET /api/events/<cell_id>` already emits `replay_complete`; the
  design keeps the one-terminal surface and its controls, restyled for touch.

### 2.11 Segmented filters + search (facets over the fleet)

- **Idea:** The fleet is filtered by a few **mutually-understood facets** (status chips) plus a
  free-text **search**, always visible above the grid.
- **Embodiment:** Linear's filter/query bar, Vercel's project filters, Kubernetes label
  selectors, GitHub's filters.
- **Mechanics:** Segmented control (All / Running / Risk — already present) + a monospace
  search box; results update in place; a count of matches is shown; filters compose with
  density. On mobile, chips scroll horizontally rather than wrapping into a tall stack.
- **Control Room mapping:** Preserve `data-filter` chips + `#cell-search`; add a horizontal
  scroll + a "risk" facet that pulls `failed`/`timeout`/`retry` (currently `risk` exists as a
  chip — the design defines exactly which statuses it includes).

### 2.12 Key-value facts panel (sidecar inspector)

- **Idea:** Node identity and metadata are presented as a **facts list** (label → value) in a
  sidecar, so the terminal stays the only "long-form" surface.
- **Embodiment:** GitHub PR sidebar, Linear's right rail, Vercel's deployment side panel,
  Stripe's detail panels.
- **Mechanics:** `dl` with `dt`/`dd` pairs (already the `control-facts` pattern); monospace
  values; `textContent`-only rendering (IDs/titles/reasons never trusted as HTML — already a
  hard rule in `docs/supervisor_design.md §7`); copyable IDs with a secondary "Copy" action.
- **Control Room mapping:** The existing `#cell-control-panel`, `#supervisor-control-panel`,
  `#design-control-panel`, `#claude-agent-control-panel` `dl`s are the sidecar; the redesign
  reorders them glanceable-first (status + title first, long `why`/reasons lower) and docks
  them in the mobile bottom sheet (§2.7).

---

## 3. Cross-cutting themes the design phase must honor

### 3.1 The flag-only rail is a *contract*, not a styling detail

Every pattern above is subordinate to the invariant in `docs/supervisor_design.md`: **the
supervisor flags; the human reviews, decides, and acts.** Concretely, the design must:

- Distinguish **read** from **actuation** visually (§2.8) and never bury the boundary.
- Keep **"Supervisor flags. You decide."** visible both on the rail footer and above action
  controls.
- Keep lifecycle states (`running/failed/done`) visually separate from heuristic assessments
  (`off_track/stalled`) — two color axes, never merged (§2.2).
- Preserve the **single-context handoff** (§2.4) and the **type-to-confirm Interrupt door**
  (§2.8), and never let Detach/Clear/refresh/unload trigger an interrupt.

### 3.2 Mobile is first-class, not a breakpoint afterthought

The spec's `hard_rules` require the one-handed layout to be specified *explicitly*. The
research above converges on a concrete shape: **sticky top command rail + a bottom tab bar
(Fleet / Status / Flags / Sessions) + a bottom-sheet drill-down for any node** (§2.6, §2.7),
with the fleet grid compacting card → list → table (§2.1, §2.11, §1.4.3). The current anchor-
jump stack (§0.4) is the anti-pattern to remove.

### 3.3 Calm under load is a *measure*, not a vibe

The redesign succeeds only if a 5s poll of a 200-cell fleet does not cause visible churn:
stable row identity, in-place updates, delta-only announcements, and motion reserved for
transitions (§2.9). This is testable (the verify phase should assert "no reorder on no-op
poll"), not aspirational.

---

## 4. Source list (products & design systems cited)

**LLM / agent observability (family 1.1):** LangSmith (`smith.langchain.com`),
Langfuse (`langfuse.com`), Helicone (`helicone.ai`).

**Container & CI fleets (family 1.1):** Kubernetes Dashboard
(`github.com/kubernetes/dashboard`), Lens (`k8slens.dev`), GitHub Actions
(`github.com/features/actions`), Buildkite (`buildkite.com`).

**Mission-control / incident (family 1.2):** PagerDuty (`pagerduty.com`), Atlassian Opsgenie
(`atlassian.com/software/opsgenie`), Grafana (`grafana.com`), Datadog (`datadoghq.com`),
Better Uptime (`betterstack.com`), Atlassian Statuspage (`statuspage.io`), Netdata
(`netdata.cloud`).

**Dev-tool surfaces (family 1.3):** Linear (`linear.app`, `linear.app/method`), Vercel + Geist
(`vercel.com`, `vercel.com/geist`), Railway (`railway.app`), Resend (`resend.com`), Stripe
Dashboard (`stripe.com`).

**Mobile / responsive systems (family 1.4):** Material Design 3 (`m3.material.io`), Apple Human
Interface Guidelines (`developer.apple.com/design/human-interface-guidelines`), MDN responsive
tables, Adrian Roselli's `display: contents` technique.

**Concrete pattern exemplars:** PagerDuty mobile (one-handed triage), Linear mobile
(list→detail), GitHub mobile (status-in-list), Datadog mobile (alert-first), Vercel build logs,
GitHub Actions logs (live stream).

> Provenance note: all cited products are real, recognizable consoles/design systems observed
> in the wild. Design decisions in the next phase will cite the §2 pattern (and its §1
> embodiment) inline; anything *not* traceable to a §1 source must be called out in
> `docs/control_room_ui/design.md` as an uncited aesthetic choice for the verify phase to flag.
