---
status: accepted
---
# Control Room UI Redesign — Design Spec

> Phase: **design** (`control_room_ui_redesign` spec, phase 2 of 3).
> Consumes `docs/control_room_ui/research.md` (this repo's research reference — cited below as
> `[R §x.y]`). This is a **design spec**, not an implementation: it maps to the *real* 28
> routes and the *real* `admin/static` DOM, and a stronger UI model or human implements it.
> The **verify** phase (`docs/control_room_ui/verify.md`) traces every decision back here.

## How to read this doc

Every decision carries an inline citation to a research pattern or embodiment (`[R §2.1]` =
"pattern 2.1, Fleet overview matrix", `[R §1.3.1]` = "reference entry 1.3.1, Linear"). Any
choice that cannot carry such a citation is explicitly labeled `UNCITED` so the verify phase
can flag it. The design never invents an endpoint: every board consumes the routes enumerated
in `[R §0.1]`.

---

## 1. Information architecture

### 1.1 Principles (each cited)

1. **Glanceable fleet is home.** The cell matrix is the operator's default surface, ordered
   urgency-first, status-colored, one-tap from any node. `[R §2.1]` (Datadog host map).
2. **Progressive disclosure, three depths.** Fleet (overview) → node (facts) → stream
   (transcript). Each depth is a push, not a side-by-side pile. `[R §2.3]` (Kubernetes/Lens,
   LangSmith).
3. **Single-context handoff.** Exactly one selected detail and one live `EventSource` may
   exist at a time. `[R §2.4]`; the invariant in `docs/supervisor_design.md §2`.
4. **Read is default; actuation is gated and visible.** `[R §2.8]` (GitHub type-to-confirm,
   PagerDuty ack).
5. **Mobile is first-class: a bottom tab bar + a bottom sheet, never an anchor-jump stack.**
   `[R §2.6]` (Material 3 AppBar/NavigationBar), `[R §2.7]` (Material 3 bottom sheet, iOS
   sheets).
6. **Calm under load.** Stable row identity, in-place updates, delta-only announcements,
   motion only on state *transitions*. `[R §2.9]` (PagerDuty dedup).

### 1.2 The five destinations + one overflow

The spec's suggested hierarchy (`Fleet / Status / Flags / Routing / Sessions`) maps cleanly to
the 28 routes. **Five top-level destinations** plus a **System overflow** for the two
occasional surfaces (Registry, Queue actions) that are not glance-worthy enough to earn a tab.

| Destination | Holds | Current boards moved here | Routes consumed |
|---|---|---|---|
| **Fleet** (home) | cell matrix, pipeline stage strip, filters/search, fleet counts | `#pipeline-stages`, `.fleet-controls`, `#fleet-grid`, `#fleet-counts` | `GET /api/matrix` (5s poll), `GET /api/status` (global SSE) |
| **Status** | live spend/burn/tokens, full burn trace, stage totals, connection + provenance | `#command-rail` metrics (expanded), `.pipeline-stage` (expanded) | `GET /api/matrix` (telemetry + stages), `GET /api/status` (SSE) |
| **Flags** | supervisor needs-attention list (full-height) | `#supervisor-rail` (promoted from right-column details to a full board) | `GET /api/flags` (5s poll), `POST /api/flags/<id>/steer`, `POST /api/flags/<id>/interrupt` |
| **Sessions** | design sessions (launchers + recent list) **and** Claude background sessions (daemon + roster + start) | `#claude-agents-pane`, `#design-launchers`, `#recent-design-list`, `#design-start-form` | `GET/POST /api/design-sessions`, `…/<id>/spec|input|interrupt|save|run`, `GET/POST /api/claude-agents`, `…/<id>/logs|stop|respawn|rm|steer`, `…/daemon`, `…/daemon/stop` |
| **Routing** | model-operations routing board (per-task recs + strategy simulation) | `#routing-drawer` (promoted from bottom drawer to a full board) | `GET /api/routing` |
| **System** (overflow) | canonical-state Registry (filterable table + lineage) **and** Queue actions (enqueue/clear/reinterleave) | `#registry-drawer`, `.utility-menu` (queue actions) | `GET /api/registry`, `GET /api/registry/<entity_id>`, `POST /api/experiments`, `POST /api/queue/reinterleave` |
| **Detail** (transversal — *not a tab*) | selected-node transcript + selected-session control panel | `#transcript-pane`, `#cell-control-panel`, `#supervisor-control-panel`, `#design-control-panel`, `#claude-agent-control-panel` | `GET /api/events/<cell_id>` (SSE), plus the actuation routes above on demand |

**Why Flags is a full board and not a right-rail.** The current rail is buried in the third
column and, on mobile, collapses to a small `details` block. Flags are the operator's *alert
queue* — PagerDuty's incident list is the home surface, not a side widget `[R §2.5]`. Promoting
it to a tab gives it full height and makes the count badge a genuine "go here" signal.

**Why Routing and Sessions are separate, not stacked in one column.** Routing is a
read-analysis board (per-task recommendations + strategy simulation, `[R §1.1.4]` GitHub
Actions / `[R §0.1]` `/api/routing`); Sessions is a *management* board full of actuation
(start/stop/steer). Separating them keeps read and act surfaces from mixing `[R §2.8]`.

### 1.3 Board → new-home migration map (exhaustive)

| Current DOM surface (`index.html`) | New home |
|---|---|
| `header.command-rail` | **Global sticky shell** (slim; metrics split — summary stays in shell, full detail in Status board) |
| `section#pipeline-stages` | **Fleet** board (compact strip) + **Status** board (expanded) |
| `.fleet-controls` (filter chips + search) | **Fleet** board |
| `#fleet-grid` (cell cards) | **Fleet** board |
| `#fleet-counts` | **Fleet** board footer |
| `#claude-agents` pane (daemon + start + roster) | **Sessions** board |
| `#transcript-panel` | **Detail** surface (transversal) |
| `aside#session-controls` | split: `#supervisor-rail` → **Flags** board; `#design-launchers` + `#recent-designs` + `#design-start-form` → **Sessions** board; the four `*-control-panel`s + `#cell-control-panel` → **Detail** surface |
| `footer.bottom-rail` (routing/registry toggles, queue menu, provenance) | split: routing toggle → **Routing** board; registry + queue menu → **System** overflow; provenance → **Status** board |
| `#routing-drawer` | **Routing** board |
| `#registry-drawer` | **System** overflow (Registry sheet) |

### 1.4 Navigation: desktop left rail vs. mobile sticky tab bar

**Desktop (≥760px):** a narrow **left nav rail** (48–56px collapsed, expandable) listing the
five destinations with icons + labels, plus a `System` entry at the bottom. This matches
Datadog/Linear/Stripe's left-rail convention `[R §1.3.5]`, `[R §1.3.1]`. The rail is
**sticky**; only the board area scrolls.

**Mobile (<760px):** a **sticky bottom tab bar** with the same five destinations, *not* a
hamburger drawer. Rationale, cited: Material 3 specifies 3–5 destinations for `NavigationBar`
and reserves the drawer for *more* than five `[R §1.4.1]`; Linear and PagerDuty mobile both use
bottom tabs / bottom actions because they are reachable one-handed `[R §1.3.1]`, `[R §1.2.1]`.
A hamburger drawer hides the primary surfaces behind a tap and is reachable only at the top
corner — the opposite of one-handed. The `System` overflow (Registry + Queue) is reached from a
persistent gear/ellipsis icon in the top shell → a **bottom sheet** `[R §2.7]`.

```text
DESKTOP                              MOBILE (<760px)
┌────────────────────────────┐       ┌────────────────────────────┐
│ slim sticky command rail   │       │ slim sticky command rail   │
├───────┬────────────────────┤       ├────────────────────────────┤
│ FLEET │  active board      │       │  active board              │
│ STATUS│  (scrolls)         │       │  (scrolls)                 │
│ FLAGS │                    │       ├────────────────────────────┤
│ SESS  │                    │       │ ●Fleet ○Status ▲Flags 2    │
│ ROUTE │                    │       │  ○Sessions ○Routing         │
│ ───── │                    │       └────────────────────────────┘
│ system│                    │          ← sticky bottom tab bar
└───────┴────────────────────┘
```

### 1.5 The transversal Detail surface

Selecting any node — a fleet cell, a flag (mapped), a design session, or a Claude agent —
opens the **Detail surface**: the transcript + the matching control panel. On desktop it is a
right-side column (today's layout, kept); on mobile it is a **modal bottom sheet** over the
board (dims the board behind), preserving the board's scroll position `[R §2.7]`. Detail is
reachable but *not* a tab: it is always the *result* of a drill-down, never a destination you
arrive at cold `[R §2.3]`.

---

## 2. Fleet overview

### 2.1 Before / after

```text
BEFORE (today, ≤759px stacks everything)     AFTER (Fleet board, desktop)
┌ command rail (86px, 4 cols) ──────────┐    ┌ slim command rail (48px, sticky) ──────────┐
│ identity│spend│burn│in/out/run/redis │    │ CONTROL ROOM·LIVE│$12.34│0.42/s│run 7│redis ●│
├──────┬──────────┬─────────────────────┤    ├─nav──┬──────────────────────────────────────┤
│fleet │transcript│supervisor rail+ctrl │    │ FLEET│ [EXEC 14/22] [ANALYZE 3/8] [REV 2/8] │
│stages│(stream)  │(the right column)   │    │      │ [All|Running|Risk] [⌕ cell id] [▤] │
│filters│         │                     │    │      │ ┌───┐┌───┐┌───┐┌───┐┌───┐┌───┐     │
│grid   │         │                     │    │      │ │◔r││✓d││×f││◔r││◷t││○q│ …   │     │
└───────┴─────────┴─────────────────────┘    │      │ ▎7 running·8 done·2 failed·…        │
                                             └──────┴──────────────────────────────────────┘
```

**Changes, cited:** the pipeline strip and the matrix live together so health-by-stage and
health-by-cell are one glance `[R §2.1]` (Grafana panel wall); the filter row adds a **density
toggle** `[R §1.3.1]` (Linear); every card is a single `<button>` so tapping it *is* the
drill-down `[R §2.3]`.

### 2.2 Status color language (concrete)

Lifecycle and attention are **two axes** and must never share a hue family `[R §2.2]`.

| Axis | Token | Color (dark / light) | Glyph | Meaning |
|---|---|---|---|---|
| lifecycle | `status-queued` | `#94a3b8` / `#64748b` | `○` | waiting |
| lifecycle | `status-running` | `#38bdf8` / `#0284c7` | `◔` (pulse) | active |
| lifecycle | `status-done` | `#34d399` / `#059669` | `✓` | succeeded |
| lifecycle | `status-failed` | `#f87171` / `#dc2626` | `×` | hard failure |
| lifecycle | `status-timeout` | `#fbbf24` / `#d97706` | `◷` | ran out of time |
| lifecycle | `status-retry` | `#2dd4bf` / `#0d9488` | `↻` | re-enqueued |
| lifecycle | `status-unknown` | `#64748b` / `#94a3b8` | `?` | unrecognized |
| attention | `attention-off-track` | `#fb7185` / `#e11d48` | `▲` | heuristic: needs a human |
| attention | `attention-stalled` | `#fbbf24` / `#d97706` | `■` | heuristic: idle |

**Rules (each cited):**
- Color is **never** the only signal: every status renders glyph + uppercase word + color
  `[R §2.2]` (GitHub status icons, PagerDuty severity = number *and* color).
- Attention colors appear **only** in the Flags board and the supervisor pane — never on a
  fleet card. `off_track` uses a warm **rose** (`#fb7185`), deliberately distinct from
  `failed`'s red (`#f87171`) so a heuristic verdict can't be misread as an execution failure
  `[R §2.2]`, and the distinction is reinforced by location + word, not hue alone.
- `stalled` shares amber with `timeout` — intentional (both mean "look at this, not
  catastrophic") `[R §2.2]`.
- The interactive/brand accent (`#6366f1` indigo) is reserved for *interactivity* (focus,
  active tab, primary CTA, links) and is therefore never confused with any status hue
  `[R §1.3.1]` (Linear: monochrome + one accent).

### 2.3 Density control

A `comfortable` / `compact` toggle sits at the right end of the filter row `[R §1.3.1]`
(Linear's density options). It is a *layout* concern only — the same card DOM restyles:

| | comfortable (default) | compact |
|---|---|---|
| card min-height | 132px | 84px |
| padding | 10px | 8px |
| content | id + status + phase badge + cost + sparkline | id + status + cost (phase + sparkline hidden) |
| grid min column | `minmax(190px,1fr)` | `minmax(150px,1fr)` |

Persist the choice in `localStorage`. `UNCITED` (the two concrete min-width values are an
engineering judgment, not a researched constant).

### 2.4 One-tap drill-down

The entire card is already a single `button.cell-select`; the redesign keeps that and makes
the *target* explicit: tap → store `selectedType:"cell"` + `selectedId` → close any prior
`EventSource` → open `GET /api/events/<cell_id>` `[R §2.4]`, `[R §2.3]`. On mobile this opens
the **Detail bottom sheet** (§1.5). No confirmation, no interstitial — drill-down is read-only
and safe to be one-tap `[R §2.8]`.

### 2.5 Fleet counts footer

The existing `#fleet-counts` (mono summary line: `7 running · 8 done · …`) stays as the board
footer, re-rendered in place on each poll **without reordering** `[R §2.9]`.

---

## 3. Detail (per-cell / per-session)

### 3.1 Before / after (mobile: the bottom sheet is the headline change)

```text
BEFORE (mobile): a long anchor-jump chain            AFTER (mobile): one bottom sheet
┌ attention ────────────────────────┐               ┌ Fleet board (dimmed) ──────────────┐
│ fleet grid (scrolls)              │               │ ┌ ◔ wf_retry_gpt_5_6_sol          │
│ [Jump to transcript]              │               │ ├── drag handle ────────────────── │
│ transcript (min 55vh, scrolls)    │               │ ║ ◔ RUNNING · phase 3/5 · review   │
│ [Back to fleet]                   │               │ ║ $1.234 · 45K in · 2K out         │
│ supervisor controls (scrolls)     │               │ ║ [⌕ Jump to transcript]           │
└───────────────────────────────────┘               │ ├────────────────────────────────── │
                                                     │ ║ (live transcript, follow/pause)  │
                                                     │ ├────────────────────────────────── │
                                                     │ ║ READ ONLY  ·  [Steer][Interrupt] │
                                                     │ └──────────────────────────────────┘
```

### 3.2 Field order — glanceable first

The facts panel (`dl.control-facts`) is reordered so the operator reads the *identity and
state* before any detail `[R §2.12]` (GitHub PR sidebar / Linear right rail):

1. **Title / cell id** (or session title → native `session_id`), `textContent`-rendered.
2. **Status word + glyph** (lifecycle) — largest emphasis.
3. **Phase badge** (`3/5 · review`) when present.
4. **Cost + tokens** (latest reported).
5. Metadata (model, workdir, age, review-stream state).
6. Long prose (`why`, reason) *last*, clamped, expandable.

Rule: the first three lines must answer "what is it, is it healthy, where is it in the
pipeline" without scrolling — everything below is secondary `[R §2.3]` (progressive
disclosure). `UNCITED` (the "three lines" figure is a design target, not a researched value).

### 3.3 Terminal surface

Unchanged contract, restyled for touch `[R §2.10]` (Vercel/GitHub Actions live logs):

- One monospace stream; `follow`/`pause`/`clear` controls; `jump-live` appears only when
  scrolled off the tail; the `replay_complete` boundary separates replay from live.
- Mobile: the transcript occupies the sheet body; the sheet drag-handle and a **back**
  affordance return to the board; the `follow` toggle is the single most-thumbed control and
  sits bottom-right (thumb zone) `[R §1.4.2]` (iOS bottom reach).
- Never more than one selected-detail `EventSource` (§1.1 principle 3) `[R §2.4]`.

### 3.4 Control panels + gated actuation

The four existing control panels (`cell`, `supervisor`, `design`, `claude-agent`) become the
sheet's bottom section, selected by `selectedType`. The read/act boundary is made **explicit
and permanent** `[R §2.8]`:

- A mode line labels the attachment: `READ ONLY` (muted chip) vs `INTERACTIVE` (indigo chip),
  mirroring today's `readonly-badge`/`interactive-badge`.
- **Reversible** actions (Steer, Send, Respawn, Enqueue, Reinterleave) are `primary`
  (indigo) and need one explicit press.
- **Irreversible** actions (Interrupt, Stop daemon, Clear queue, `rm`) are `danger` (rose) and
  sit behind a **two-step door** with typed confirmation — the existing `INTERRUPT
  <session_id>` door is the model, and the same pattern extends to daemon-stop and clear-queue
  (both already confirm or gate) `[R §2.8]` (GitHub type-to-confirm).
- The supervisor pane repeats **"Supervisor flags. You decide."** above its actions, per
  `docs/supervisor_design.md §1` `[R §2.8]`.

---

## 4. Alert rail (Flags board)

### 4.1 Before / after

```text
BEFORE (buried details block, ≤260px)          AFTER (full board, both widths)
┌ control column ─────────────┐               ┌ FLAGS ────────────────────────────────┐
│ ▶ Supervisor  NEEDS ATTN 2 │               │ NEEDS ATTENTION · 2          (source)  │
│   (a small scrollable list) │               │ ┌▲ OFF TRACK · Fix retry accounting ┐│
└─────────────────────────────┘               │ │ gpt-5.6-sol · 12s · act 8s ago     ││
                                               │ │ "editing pricing before repro…"    ││
                                               │ └────────────────────────────────────┘│
                                               │ ┌■ STALLED · Add cache layer ────────┐│
                                               │ │ claude-sonnet · 3m · act 1m ago     ││
                                               │ │ "no activity in the active window" ││
                                               │ └────────────────────────────────────┘│
                                               │ Supervisor flags. You decide.          │
                                               └───────────────────────────────────────┘
```

### 4.2 Surfacing without shouting

- The board header carries the count badge (amber) and the **source/degraded** line
  (`redis` / `file` / `none`, `Supervisor data delayed` when degraded) — the three states
  (empty / flags / degraded) are already specified in `docs/supervisor_design.md §1` and are
  rendered here verbatim `[R §2.5]` (Better Uptime healthy/incident states).
- Each row: status word (`OFF TRACK` / `STALLED` / `ATTENTION`) + title + one-sentence `why`
  (2-line clamp) + model + flag age + last-activity. `textContent` only.
- Rows update **in place by `flag_id`** so a 5s poll never reorders or steals focus;
  announcements fire only on *new session or changed assessment* `[R §2.9]`.
- A nonzero count makes the badge visible but **never** auto-opens the board or steals the
  current board — attention is suggested, not forced `[R §2.5]` (PagerDuty does not yank you
  to the incident list).

### 4.3 Read vs. actuation (the flag-only rail, visually)

Selecting a mapped flag opens the Detail sheet in **supervisor mode**: the transcript is
labeled "review of observed activity" (read), while the only actuation is the deliberate
Steer composer and the gated Interrupt door `[R §2.8]`, `docs/supervisor_design.md §2–3`. The
board itself is **pure read**: no button on the list ever sends a request. The border between
observe and act is drawn by (a) the `READ ONLY`/`INTERACTIVE` mode line, (b) the persistent
"Supervisor flags. You decide." footer (on the board *and* above actions), and (c) the
danger-styled, type-to-confirm door `[R §2.8]`.

---

## 5. Status board (live telemetry, expanded)

### 5.1 Before / after

```text
BEFORE: metrics crammed in the 86px rail        AFTER: a full "spend dashboard" board
┌ command rail ───────────────────────────┐    ┌ STATUS ─────────────────────────────────┐
│ spend $12.34 │ burn 0.42/s ▁▂▁ │ in/out │    │ REPORTED SPEND   $12.34   retained wind.│
└──────────────────────────────────────────┘    │ REPORTED BURN    0.42/s   rolling 60s  │
                                                 │  ▁▂▃▂▁▃▄▂▁▁▂▃▂▂▂▃▂▁   (full trace)   │
                                                 │ INPUT 1.2M · OUTPUT 340K               │
                                                 │ EXEC 14/22 · ANALYZE 3/8 · REVIEW 2/8   │
                                                 │ Redis LIVE · telemetry: retained window │
                                                 └──────────────────────────────────────────┘
```

### 5.2 What lives here

The Status board is where the operator watches **money and throughput**, not individual cells
`[R §1.2.3]` (Datadog) and `[R §1.3.2]` (Vercel's deployment/usage dashboards):

- Reported spend (large), reported burn with the **full-width burn trace** (the command rail
  keeps only a 60px sparkline; this board renders the full trace) `[R §1.2.3]`.
- Input/output token totals (from `telemetry` block) + `history_capped` / provenance.
- The three pipeline stages expanded with per-stage counts `[R §2.1]`.
- Redis/connection state + the telemetry provenance label (`retained window`).

Routes: `GET /api/matrix` (telemetry + stages) and the global `GET /api/status` SSE — no new
endpoint `[R §0.1]`.

---

## 6. Sessions board (design + Claude background sessions)

### 6.1 Before / after

```text
BEFORE: claude pane under the fleet;            AFTER: one "session fleet" board
design launchers buried in the control column
┌ fleet grid ──────────────┐                   ┌ SESSIONS ───────────────────────────────┐
│ …                        │                   │ DESIGN SESSIONS   [+ Workflow][+ Exper] │
│ ── claude agents ──      │                   │  ┌ Fix retry accounting … ────────────┐ │
│  daemon · start · roster │                   │  └────────────────────────────────────┘ │
└──────────────────────────┘                   │ CLAUDE BACKGROUND SESSIONS  [+ Start]   │
   (control column: launchers + recent list)   │  DAEMON  ● running · PID 1234           │
                                                │  ┌ session · task ───────┐ ┌ … ┐       │
                                                │  └ owned · stop/respawn ┘ └   ┘       │
                                                └────────────────────────────────────────┘
```

### 6.2 What lives here

This board is the **management** surface for the two session fleets `[R §1.1.3]` (Kubernetes
workloads), `[R §1.3.3]` (Railway service tiles):

- **Design sessions**: the two launchers (`Workflow design`, `Experiment design`), the
  `#design-start-form`, and the `#recent-design-list`.
- **Claude background sessions**: the daemon panel (status + `Stop daemon`, gated), the
  `#claude-agent-start-form`, and the roster grid, each card carrying an `owned`/`external`
  ownership chip (read/act distinction for lifecycle controls `[R §2.8]`).
- Selecting a session opens the Detail sheet (§3) in `design` or `claude-agent` mode.

Routes: the full 7 design-session + 9 claude-agent routes `[R §0.1]`. Ownership controls
(`stop`/`respawn`/`rm`) remain hidden for `external` sessions and are server-enforced anyway
(`_require_owned_claude_agent`) — the UI only *mirrors* the backend gate, it does not add one.

---

## 7. Routing board + System overflow

### 7.1 Routing (read-only analysis board)

The `#routing-drawer` content (`compute_routing` output: per-task recommendations + strategy
simulation) is promoted to a full board `[R §1.1.4]`. Read-only; a `Refresh` action reloads
`GET /api/routing`. The dense strategy table uses the same card→list→table compaction as the
fleet `[R §1.4.3]`.

### 7.2 System overflow (Registry + Queue actions)

Reached from a gear icon in the command shell → bottom sheet (mobile) / popover (desktop)
`[R §2.7]`:

```text
┌ SYSTEM ────────────────────────────────┐
│ REGISTRY  [record type ▾][lifecycle ▾] │
│  ┌ story · current · 12:00Z ──────────┐│
│  └ … ─────────────────────────────────┘│
│  [lineage: one entity → its causes]    │
│ QUEUE                                   │
│  [Enqueue experiment]  [Reinterleave]   │
│  [Clear queued work]   ← danger, gated  │
└─────────────────────────────────────────┘
```

Registry stays a **filterable table + one-hop lineage** (read-only by construction `[R §0.1]`);
Queue actions are the *only* actuation here and carry the same gating as §3.4 — `Clear queued
work` is `danger` and gated, `Enqueue`/`Reinterleave` are `primary` `[R §2.8]`.

---

## 8. Visual system

### 8.1 Stance: dark-first, light available

Mission-control surfaces are dark-first (Grafana, Netdata, Railway) `[R §1.2.2]`, `[R §1.2.5]`,
`[R §1.3.3]`, and the current app is already dark-only (`color-scheme: dark`). Keep **dark as
default** but add a full **light** theme, because Geist and Stripe prove dense tools read
better in light for bright rooms `[R §1.3.2]`, `[R §1.3.5]`. Stance: default follows
`prefers-color-scheme`; a toggle in the shell persists to `localStorage`. Both themes are
defined as the same set of CSS custom properties, so the design is one token set, two values
`[R §1.4.3]`.

### 8.2 Concrete palette

```css
:root { /* dark (default) */
  /* surfaces */
  --bg-0:#0a0d12; --bg-1:#10151d; --bg-2:#171e28; --bg-3:#1e2733;
  --border:#1f2a37; --border-strong:#334154;
  /* text */
  --text:#e6edf3; --text-muted:#8b98a9; --text-faint:#5b6b7e;
  /* brand — interactivity ONLY (focus, active tab, primary CTA, links) */
  --accent:#6366f1; --accent-hover:#818cf8; --accent-strong:#4f46e5; --accent-ink:#eef2ff;
  /* lifecycle status (glyph+word+color, never alone) */
  --status-queued:#94a3b8; --status-running:#38bdf8; --status-done:#34d399;
  --status-failed:#f87171; --status-timeout:#fbbf24; --status-retry:#2dd4bf; --status-unknown:#64748b;
  /* attention (supervisor only) */
  --attention-off-track:#fb7185; --attention-stalled:#fbbf24; --attention-unknown:#e2e8f0;
}

[data-theme="light"] {
  --bg-0:#f1f5f9; --bg-1:#ffffff; --bg-2:#f8fafc; --bg-3:#eef2f7;
  --border:#e2e8f0; --border-strong:#cbd5e1;
  --text:#0f172a; --text-muted:#475569; --text-faint:#94a3b8;
  --accent:#4f46e5; --accent-hover:#6366f1; --accent-strong:#4338ca; --accent-ink:#ffffff;
  --status-queued:#64748b; --status-running:#0284c7; --status-done:#059669;
  --status-failed:#dc2626; --status-timeout:#d97706; --status-retry:#0d9488; --status-unknown:#94a3b8;
  --attention-off-track:#e11d48; --attention-stalled:#d97706; --attention-unknown:#334155;
}
```

**Brand-accent rationale (cited, not taste):** a single, desaturated **indigo** accent used
*only* for interactivity is the Linear/Geist "monochrome + one accent" convention `[R §1.3.1]`,
`[R §1.3.2]`; it frees every other hue for semantics, eliminating the current conflation where
`--running` doubles as the focus ring and primary-CTA color. `off_track` rose vs. `failed` red
is the two-axis separation from `[R §2.2]`.

### 8.3 Spacing

4px base scale, per Geist `[R §1.3.2]`: `--sp-1:4px · --sp-2:8px · --sp-3:12px · --sp-4:16px
· --sp-5:24px · --sp-6:32px`. Board padding `--sp-3`; card padding `--sp-2`/`--sp-3`;
section gaps `--sp-2`; rail/pane borders 1px `--border`.

### 8.4 Typography

- **UI sans**: `Inter, system-ui, -apple-system, "Segoe UI", sans-serif` `[R §1.3.2]`
  (Geist/Linear both use a geometric sans; Inter is the pragmatic system-safe equivalent).
- **Data mono**: `ui-monospace, "SF Mono", "JetBrains Mono", monospace` — IDs, tokens, costs,
  timestamps, logs `[R §1.1.1]` (LangSmith monospace IDs).
- **Scale**: `11` eyebrow/meta · `12` body-small · `13` board-title (h2) · `14` base · `16`
  metric · `24` hero metric. `UNCITED` (exact point sizes are judgment; the *ratios* follow
  a compact dev-tool scale `[R §1.3.1]`).
- **Tabular numerals** (`font-variant-numeric: tabular-nums`) on every counter/cost/token so
  polling updates don't jitter widths `[R §2.9]`.

### 8.5 Motion

Reserved for **transitions, not churn** `[R §2.9]`: the `running` pulse (2s, subtle border
shift) stays; cards update *in place*; the sheet slides up 200ms; nothing reflows on a no-op
poll. Honor `prefers-reduced-motion` (the existing block already does — keep it).

---

## 9. Implementation notes (mapping to real code, no invented endpoints)

The redesign is a **re-skin + re-layout** of the existing DOM/JS, not a new app:

- The five destinations are the existing sections regrouped under a nav shell (§1.3); the
  Detail surface is the existing transcript + control panels moved into a sheet on mobile.
- **No new route** is required. Every board consumes the routes in §1.2 (`[R §0.1]`).
- JS changes are limited to: a nav/tab switcher, the Detail sheet open/close (wrapping the
  existing selection handoff `replaceEventSource`), a density toggle (adds a class to
  `#fleet-grid`), and the System sheet (mounting the existing registry + queue UI). The
  render functions (`renderFleet`, `renderRail`, `renderBurn`, `stageCard`, flag/render code)
  and `control-room-core.js` helpers (`normalizeStatus`, `sortCellIds`, `replaceEventSource`,
  `reconcileTelemetry`, `burnRate`) are unchanged in contract.
- The flag-only invariant (`docs/supervisor_design.md`) is *preserved*: the Flags board is
  read-only; Steer/Interrupt remain the only actuation, behind the existing gated doors; the
  "Supervisor flags. You decide." copy stays visible on the board and above actions.

---

## 10. Handoff to the verify phase

The verify phase must confirm (and this design asserts): (a) every decision above carries a
`[R §x.y]` citation, and any `UNCITED` choice is enumerated — there are exactly **three**
(§2.3 density widths, §3.2 "three lines" target, §8.4 point sizes); (b) mobile is specified
explicitly (bottom tab bar + bottom sheet + one-handed reach, §1.4, §2.7, §3.3); (c) the
flag-only rail is visibly preserved (§4.3, §3.4); (d) the design maps to the actual 28 routes
and data shapes (§1.2, §9) with no invented endpoints.
