---
status: accepted
---

# Control Room — operator-surface audit (campaign phase r0)

**Audit date:** 2026-09-11
**Campaign:** `workflows/repository/control_room_research.yaml`, phase `r0_audit`
(`docs/designs/proposed/control_room_research_campaign.md`; pre-registration
`docs/experiments/preregistrations/control_room_research_preregistration.md`).
**Scope:** `apps/control_room/` only — `server.py`, `routes/`, `clients/`, `services/`,
`static/index.html`, `static/*.js`, `static/style.css`, `static/architecture.svg`.
**Method:** every claim below is read from the code at the cited `path:line` range. No portal was
started, no network request was made, no live portal was touched. Where the code's own prose and
the code's behaviour disagree, the behaviour is reported and the drift is named (see §8).

This document is the campaign's **measured baseline**. It answers, from code, the four r0
questions: *what panels and data feeds does the operator see; at what cadence; which questions do
they answer; what is present but in the wrong place, and what is absent?* The open-web acquisition
(r2a–r2e), taxonomy (r3), reduction (r4), design direction (r5) and facelift brief (r7) are later
campaign phases and deliberately do **not** appear here. A **prior, now partly stale** audit exists
at `docs/website/control_room_ui/control_room_refresh_audit.md` (dated 2026-08-23, written against
28 routes); §10 records what this audit supersedes and corrects.

---

## 1. What the Control Room is (composition, planes, transport)

The Control Room is a **local-operator Flask portal** over the framework's Redis control/telemetry
plane. It is a composition root plus six route modules, seven service modules, two clients, and a
**no-build** vanilla-JS shell.

| Layer | Files | Role | Evidence |
|---|---|---|---|
| Composition root | `apps/control_room/server.py` | Config, factories, parsed-manifest cache, Flask `app`, `build_services()` injection, boot | `server.py:86-134`, `server.py:203-211`, `server.py:214-218` |
| Routes | `routes/{telemetry,flags,registry,recording,design_sessions,claude_agents,docs_health,index}.py` | One `register(app, services)` each | `routes/__init__.py:22-46` |
| Services | `services/{telemetry,supervisor,mutations,registry,design_sessions,docs_health,subscription_usage,context}.py` | Decoding/aggregation, trust boundary, idempotency, file reads | `services/context.py:67-187` |
| Clients | `clients/opencode_client.py`, `clients/claude_agents_client.py` | The only outbound calls: OpenCode HTTP v2, and the `claude` CLI subprocess | `clients/opencode_client.py:1-6`, `clients/claude_agents_client.py:1-13` |
| Static shell | `static/index.html` + six classic scripts | No build step, ordered globals | `index.html:24-26`, `index.html:795-800` |

**Measured route count: 34 endpoints** (33 under `/api/*` plus the static `GET /`), across **seven**
API categories. This is the number the code actually registers (`app.get`/`app.post` calls), not
the number the docstring claims — see §8.1.

| Category | Count | Registered at |
|---|---|---|
| Telemetry + experiment control | 8 | `routes/telemetry.py:425-432` |
| Supervisor flags | 3 | `routes/flags.py:90-92` |
| Registry | 2 | `routes/registry.py:93-94` |
| Recording sweep | 2 | `routes/recording.py:62-63` |
| Design sessions | 7 | `routes/design_sessions.py:159-165` |
| Claude background sessions | 9 | `routes/claude_agents.py:283-291` |
| Docs health | 2 | `routes/docs_health.py:172-173` |
| Static shell | 1 | `routes/index.py:26` |

**Transport is two-layer by construction.** Slow-changing populations are **polled** HTTP JSON
(`app.js` timers); fast-changing cell status and the selected transcript are **pushed** over SSE
(`routes/telemetry.py:187-252`) and then *reconciled* with the poll snapshot rather than replacing
it (`app.js:2028-2071`; de-dup logic `app.js:1587-1675`). The whole design leans on the fact that
the matrix snapshot owns retained telemetry and the SSE stream only overlays not-yet-polled live
samples (`app.js:4-8`).

**Trust boundary for mutations.** Every non-GET route funnels through a loopback/tailnet +
same-origin + JSON + size-cap + `Idempotency-Key` gate (`services/mutations.py:40-68`) and a Redis
`SET NX` reserve/replay (`services/mutations.py:70-120`). The Claude routes duplicate the gate for
feature-isolation reasons (`services/mutations.py:132-157`, `:167-220`). This is a hard invariant
for any facelift and is restated in §11.

---

## 2. Panel and feed inventory (everything the operator can see)

The operator surface is: **one command rail**, **five destination boards**, **one transversal
detail surface**, and **one System overflow sheet**. There is exactly one visible board at a time
(`shell.js:127-148`); Detail only ever opens as the *result* of selecting a node (`detail-sheet.js:124-143`).

### 2.1 Command rail (always visible)

| Element | DOM | Data + cadence | Operator question answered | Evidence |
|---|---|---|---|---|
| Identity ("dynamic-code / CONTROL ROOM") | `#app-shell` header | static | "What am I looking at?" | `index.html:62-66` |
| Overall connection badge | `#overall-state` | Derived from matrix + status SSE states, every 1 s via `tick()` | "Is the room connected?" | `app.js:215-220`, `app.js:246-248`, `app.js:2939-2950` |
| UTC clock | `#utc-clock` | client clock, 1 s | "What time is it (UTC)?" | `app.js:2939-2943` |
| Mirrors: Spend / Burn / Running / Redis | `.rail-mirrors[data-mirror]` | Mirrored from the Status-board canonical nodes via `MutationObserver` | "Give me the headline numbers from any board" | `index.html:73-78`, `shell.js:329-362` |
| Theme toggle, System gear | `#theme-toggle`, `#system-toggle` | chrome | preference / overflow | `index.html:80-90`, `shell.js:296-303` |

**Important measured detail:** the mirror cluster is marked `aria-hidden="true"`
(`index.html:73`), so a screen-reader operator cannot hear Spend/Burn/Running/Redis at all; the
mirrors are visual-only. (Detail: `syncMirror` writes `textContent` but does not remove the
`aria-hidden` ancestor — `shell.js:329-341`.)

### 2.2 Destination boards

#### Fleet (home) — `#board-fleet` (`index.html:359-460`)

| Panel | Data source | Cadence | Operator question | Evidence |
|---|---|---|---|---|
| Cell count header + matrix age | `/api/matrix` `total` | 5 s (+1 s age tick) | "How many cells, how fresh?" | `app.js:602-676`, `app.js:2944-2946` |
| Pipeline-stage strip (EXECUTE/ANALYZE/REVIEW) | `/api/matrix` `stages` | 5 s | "Where is work sitting across the three post-hoc stages?" | `app.js:678-740`; region re-parented by `shell.js:102-109` |
| **Docs health** | `GET /api/docs-health` | **60 s** | "Are the docs current, and is there a remediation to sign?" | `app.js:828-976`, poll `app.js:3418` |
| **Live now** | `/api/matrix` `phases` (`live` flag) | 5 s | "Which runs published a phase in the last 10 min?" | `app.js:537-600`; server window `services/telemetry.py:24` |
| Fleet filters (All/Live/Running/Risk) + search + density | matrix `cells` | 5 s | "Slice a large fleet; find a cell" | `index.html:436-452`, `board-fleet.js:106-127` |
| Fleet grid of cell cards | `/api/matrix` `cells` + `telemetry` + `phases`; status SSE overlay | 5 s poll + SSE | "What is each cell doing, at what phase, at what cost?" | `app.js:405-508`, `app.js:602-676` |
| Fleet counts footer | matrix `cells` | 5 s | "Give me the fleet histogram" | `board-fleet.js:146-161` |

Each cell card renders status word+glyph, full cell id, live phase badge with age, latest step
cost, and a 12-sample token/cost sparkline (`app.js:405-485`). Ordering is urgency-first, then
lexicographic (`control-room-core.js:256-261`); the card fingerprint makes a no-op poll write
nothing (`board-fleet.js:172-193`, `keyed-list.js:88-132`).

#### Status — `#board-status` (`index.html:463-508`)

| Panel | Data source | Cadence | Operator question | Evidence |
|---|---|---|---|---|
| Reported spend (hero) | `/api/matrix` `telemetry.reported_cost` + live overlays | 5 s + SSE | "How much has been reported this retained window?" | `app.js:223-235` |
| Reported burn (rolling 60 s) + full-width trace | live `step_finish` samples; window 60 s | SSE + 1 s tick | "What am I spending right now?" | `app.js:254-288`, `BURN_WINDOW_MS` `app.js:24` |
| Token totals (in/out) | matrix `telemetry` | 5 s | "How many tokens?" | `app.js:237-242` |
| Throughput: running + Redis | matrix state + derived | 5 s / 1 s | "How many running; is Redis up?" | `app.js:243-249` |
| Pipeline strip (expanded) | same single node as Fleet | 5 s | same | `shell.js:102-109` |

Provenance is stated in-panel: `RETAINED WINDOW`, and `TRUNCATED` when the 500-event log is capped
(`index.html:476`, `app.js:235`). `reported_cost` is **partial by construction** — the server
marks `partial: True` (`services/telemetry.py:198-210`).

#### Flags — `#board-flags` (`index.html:511-533`)

| Panel | Data source | Cadence | Operator question | Evidence |
|---|---|---|---|---|
| Source + attention count | `GET /api/flags?limit=50` envelope | 5 s | "Is this live or a retained snapshot, and how many flags?" | `index.html:517-522`, `app.js:1065-1104` |
| Supervisor flag list | flags envelope | 5 s | "What does the heuristic want a human to look at?" | `app.js:984-1104` |
| Degraded delay notice | envelope `degraded`/`source` | 5 s | "Am I seeing stale supervisor data?" | `index.html:526`, `services/supervisor.py:147-161` |

The service reads Redis first and falls back to a bounded tail of the append-only file, marking the
envelope `source: redis|file` and `degraded` (`services/supervisor.py:95-161`). The flag-only
boundary is printed on the board ("Supervisor flags. You decide.", `index.html:531`).

#### Sessions — `#board-sessions` (`index.html:536-644`)

| Panel | Data source | Cadence | Operator question | Evidence |
|---|---|---|---|---|
| Design launchers | chrome | — | "Start a workflow/experiment design" | `index.html:544-550`, `app.js:2776-2783` |
| Recent design sessions | `GET /api/design-sessions` | 10 s | "What design conversations exist and what draft state?" | `app.js:1171-1227`, poll `app.js:3414` |
| Design start form | `workdirs` from the same envelope | on demand | "Begin a new design session" | `index.html:560-579`, `app.js:1411-1422` |
| Claude background sessions grid | `GET /api/claude-agents` (supervisor-maintained roster) | 10 s | "Which headless `claude --bg` sessions exist, owned vs external?" | `app.js:1323-1409`, poll `app.js:3415` |
| Claude daemon panel | `GET /api/claude-agents/daemon` | 15 s | "Is the local claude daemon up; what PID?" | `app.js:1424-1428`, poll `app.js:3416` |
| Claude start form | `workdirs` from the roster envelope | on demand | "Launch a new background session" | `index.html:609-638` |

#### Routing — `#board-routing` (`index.html:647-668`)

| Panel | Data source | Cadence | Operator question | Evidence |
|---|---|---|---|---|
| Routing drawer (lazy) | `GET /api/routing` → `compute_routing(entries)` | **on demand** (first activation auto-toggles; manual Refresh) | "Which model/strategy should I route a task to, at what simulated cost/correctness?" | `app.js:2216-2263`, `shell.js:119-124`, `index.html:657-660` |

### 2.3 Detail surface (transversal) — `#detail-surface` (`index.html:138-350`)

Docked right column ≥760 px, modal bottom sheet below (`style.css:1985-2100`, `detail-sheet.js:24-52`).
Selection is document-delegated from `.cell-select`, `.supervisor-flag`, `.recent-design`
(`detail-sheet.js:28`, `:265-270`). One selected event `EventSource` at a time (`app.js:1747-1794`).

| Sub-panel | What it shows | Operator question | Evidence |
|---|---|---|---|
| Header | mode, title, status word, phase, stream state, cost/tokens glance | "What is it; is it healthy; where is it; what has it cost?" | `index.html:150-171`, `app.js:1229-1253`, `app.js:1431-1520` |
| Transcript | replayed history + live events, Follow/Pause/Clear/Jump-to-live, 500-row bound | "What is the agent actually doing?" | `index.html:174-185`, `app.js:1522-1675`, `app.js:1747-1794` |
| Cell controls | read-only cell/status/stream/session facts; Watch | "Attach/detach; copy session id" | `index.html:198-221` |
| Supervisor controls | flag facts, reason, review stream, last activity; Steer; Interrupt behind typed door | "Act on one flagged session safely" | `index.html:223-263`, `app.js:1117-1146` |
| Design controls | kind/portal/model/workdir/draft; validation; matrix preview; save spec; run workflow; composer; interrupt | "Advance a design session to a saved/run spec" | `index.html:265-316`, `app.js:1256-1297` |
| Claude-agent controls | ownership-aware stop/respawn/rm/steer, or external log tail | "Manage or inspect a background `claude` session" | `index.html:318-347`, `app.js:1298-1315` |

### 2.4 System overflow — `#system-sheet` (`index.html:680-790`)

| Panel | Data source | Cadence | Operator question | Evidence |
|---|---|---|---|---|
| Registry table + filters + lineage | `GET /api/registry(?record_type&lifecycle&since)`, `GET /api/registry/<entity_id>` | **on open / manual Apply / row click** | "What canonical records exist; what superseded what; why did the system act?" | `app.js:2407-2500` |
| Queue actions (Enqueue, Clear behind typed door) | `POST /api/experiments` | on press | "Fill or clear the story queue" | `app.js:2502-2524`, `index.html:747-772` |
| Subscription usage | `GET /api/subscription-usage[?refresh=1]` | **60 s** + manual Refresh | "Provider quota windows; DeepSeek wallet/meter; what leases are reserved?" | `app.js:2265-2399`, poll `app.js:3417`, `index.html:774-788` |

The usage route deliberately co-locates **consumed** (provider endpoints, 15-min cache) and
**reserved-but-unspent** (lease admission board) on one route (`routes/telemetry.py:303-356`;
scopes `:277-286`; cache contract `services/subscription_usage.py:29-32`).

### 2.5 Feeds the server exposes but no operator surface consumes

These are registered and, where noted, computed on a live poll — but nothing in `static/` fetches
or renders them. Verified by grepping every route token against `static/`.

| Endpoint / payload | Status | Evidence |
|---|---|---|
| `GET /api/projections` | **No frontend caller.** Full projection-watermark report (registry/chroma/neo4j/ledger health, lag, stale-after). | route `routes/telemetry.py:145-184`; zero hits in `static/` |
| `response["projections"]` inside `/api/matrix` | **Computed on every 5 s poll, never read.** The p3 comment says it exists so a green board cannot hide a 400-event-behind registry. | `routes/telemetry.py:135-141`; zero hits in `static/` |
| `GET /api/recording-audit` | No frontend caller (decision-record coverage rail). | `routes/recording.py:43-44`; zero hits in `static/` |
| `POST /api/recording-sweep/run` | No frontend caller. | `routes/recording.py:47-58`; zero hits in `static/` |
| `POST /api/queue/reinterleave` | No frontend caller. Queue-level control, queue reorder. | `routes/telemetry.py:391-418`; zero hits in `static/` |
| The `control status` packet (`control-status/v1`) | **The portal never imports or renders it.** No route wraps `control_status.build_packet`. | no `control_status` reference under `apps/control_room/`; packet lives in `src/agentic_dynamics/control/control_status.py` |

### 2.6 `static/architecture.svg` — present in the repo, orphaned from the portal

`architecture.svg` (469 lines) is a self-contained, accessible diagram of **the
information-acquisition machine** (`ExperimentSpec → DAG → cells → jobs → attempts → ledger →
measure → information → policy → grid → campaign`). Its `<title>`/`<desc>` are explicit. It is a
**documentation source asset**, described in `docs/architecture/current/architecture_visual.md:6-20`,
and that doc still cites the pre-move path `admin/static/architecture.svg`. It is referenced by
**no HTML, JS, or JSON** in the repo (verified by grep), and `index.html` loads no image. So the
architecture picture the operator would need to orient in the system is not in the room at all.
Note also its subject is **the research/engineering loop**, not the operator's control topology
(queues → workers → cells → sessions), so even if embedded it would not answer "what am I
operating?".

---

## 3. Refresh cadence (measured, complete)

### 3.1 Poll timers (`app.js:3412-3419`; constants `app.js:11-29`)

| Feed | Interval | Fires regardless of visible board? | In-flight guard? | Evidence |
|---|---|---|---|---|
| `/api/matrix` | **5 s** | yes | yes | `app.js:16`, `app.js:2028-2031` |
| `/api/flags?limit=50` | **5 s** | yes | yes | `app.js:17`, `app.js:2074-2076` |
| `/api/design-sessions` | **10 s** | yes | no | `app.js:22`, `app.js:2706` |
| `/api/design-sessions/<id>/spec` (selected draft only) | **3 s** | only while a design is selected | `draftRequestInFlight` | `app.js:23`, `app.js:1878` |
| `/api/claude-agents` | **10 s** | yes | no | `app.js:27`, `app.js:2740` |
| `claude-agents/daemon` | **15 s** | yes | no | `app.js:28`, `app.js:2765` |
| `/api/subscription-usage` | **60 s** | yes (fetches even while System is closed) | yes | `app.js:3417`, `app.js:2268` |
| `/api/docs-health` | **60 s** | yes | (no guard) | `app.js:21`, `app.js:3418` |
| `tick()` (clock, rail, flag re-render) | **1 s** | yes | — | `app.js:3419`, `app.js:2939-2950` |

### 3.2 Push streams

| Stream | Lifetime | Heartbeat | Evidence |
|---|---|---|---|
| `/api/status` (cell status transitions) | one page-lifetime `EventSource` | server `: ping` every `HEARTBEAT_SECONDS` = **15 s** | `app.js:2130-2159`, `routes/telemetry.py:187-210`, `server.py:99` |
| `/api/events/<cell_id>` (selected node) | one at a time; replaced on selection change | same 15 s | `app.js:1747-1794`, `routes/telemetry.py:213-252` |

### 3.3 Server-side windows / freshness floors (not cadence, but they bound what a poll can mean)

| Window | Value | Where |
|---|---|---|
| LIVE NOW horizon | 600 s (10 min) | `services/telemetry.py:24` |
| Rolling burn window | 60 s | `app.js:24` |
| Retained samples shipped per cell | 60 (aggregates over full 500) | `server.py:105-110` |
| Event log cap | `EVENT_LOG_MAX` (500) | imported `server.py:70`; cap surfaced `app.js:225` |
| Supervisor active window | 900 s (`SUPERVISOR_ACTIVE_WINDOW`) | `paths.py:24` |
| Subscription usage cache TTL / refresh floor / file stale max | 900 s / 60 s / 86400 s | `services/subscription_usage.py:30-32` |
| Registry cache invalidation | `(path, mtime_ns, size)` | `services/registry.py:26-34` |
| Docs-drift rail cadence | hourly timer (per the code's own note) | `app.js:18-20` |

**Measured cadence consequence:** five of the nine pollers fire on their schedule even when the
board they serve is `hidden`, and four have no in-flight guard. There is no `visibilitychange`
pause/backoff, no `AbortSignal`, and no request timeout anywhere in the fetch layer.

---

## 4. Operator-question map (glance / drill-down / alert)

Derived by mapping each panel to the question its labels and reading order imply (`index.html`
field order; `app.js` render order). The design's own stated model is glance → drill-down → alert
(`docs/website/control_room_ui/design.md` §1.1; cited in `index.html:5-10`).

**Glance (should be answerable in one screen, no interaction):**
- *Is the system up, and am I connected?* → command rail overall badge + Redis mirror (`app.js:215-248`).
- *What is running / queued / failed?* → Fleet count header, counts footer, urgency-ordered grid (`board-fleet.js:146-161`, `app.js:602-676`).
- *What is live right now?* → Live now section (`app.js:582-600`).
- *Am I spending? How much?* → rail Spend/Burn mirrors + Status board (`app.js:223-288`).
- *Is anything asking for a human?* → Flags badge + Flags board (`index.html:110-113`, `app.js:1049-1104`).
- *Is the docs/knowledge state current?* → Docs health (Fleet) — **but not the projection watermarks that say whether results reached the KB**.

**Drill-down (one selection away):**
- *What is this one cell doing, step by step?* → Detail transcript (`app.js:1522-1675`).
- *Why was this flag raised; can I steer/interrupt?* → Detail supervisor panel (`app.js:1117-1146`).
- *What is this design's draft/validation state?* → Detail design panel (`app.js:1256-1297`).
- *Which canonical record explains this action?* → Registry lineage (`app.js:2479-2500`).
- *Which model should route this task?* → Routing board (`app.js:2216-2263`).
- *What are my provider quotas/wallet/leases?* → System ▸ Subscription usage (`app.js:2265-2399`).

**Alert (should interrupt or be impossible to miss):**
- Supervisor flags (heuristic attention) — surfaced as a badge and a board (`index.html:110-113`).
- Connection loss — rail badge + announcements (`app.js:2036-2041`, `:2118-2123`).
- Docs `warranted` proposal — red word + approve affordance (`services/docs_health.py:70-83`).

**Measured alerting gaps:** the room's only *push* signals are connection state and the flag count
mirror; everything else is pull. There is no desktop/browser notification, no sound, no persistent
alert log, no unread/seen state, and no single "what changed since I last looked" surface. The
authoritative alert-like state that *does* exist elsewhere in the repo — the `control status`
packet's `awaiting_approvals`, `promotable_runs`, `failed_runs`, `unhealthy_workers`, `degraded` —
is not in the room at all (§2.5).

---

## 5. Present but mis-placed — ranked by likely operator cost

Ranking key: **cost = how badly a wrong or late decision becomes when the operator has to work
around the placement** (money, dropped work, false confidence), multiplied by how often the
operator needs it. Ties broken by how easy the fix is.

### M1 — Provider quota/wallet + lease reservations are buried two levels deep in System overflow.
**Cost: HIGH (money).** The single most spend-relevant surface — Anthropic/OpenAI usage windows,
DeepSeek wallet balance, and the *reserved-but-unspent* lease board that the caps are sized
against — lives in `System ▸ Subscription usage`, behind the gear on mobile / the rail's bottom
entry on desktop (`index.html:774-788`), while the Status board (`#board-status`, the money board)
shows only a retained-window spend and a 60 s burn. The route's own docstring says the two halves
"only mean something together" (`routes/telemetry.py:305-317`), yet the one place an operator
watches money has neither. An operator can watch "spend" all day and never see that a provider
window is exhausted or that a campaign lease has reserved the headroom.

### M2 — Knowledge projection health is measured on every 5 s poll and rendered nowhere; `/api/projections` is orphaned.
**Cost: HIGH (false confidence).** `/api/matrix` computes `response["projections"]` on every poll
(`routes/telemetry.py:135-141`) and `/api/projections` exists precisely because "an operator
reading a green board had no way to know the registry was 400 events behind" (design note at
`routes/telemetry.py:136-140`). No frontend code reads either. The room can show a fully green
fleet while the ledger/registry/chroma/neo4j projections are stale or failing — exactly the
false-authority failure the control-plane work was built to remove.

### M3 — The canonical `control status` packet is absent; the room re-derives a subset ad hoc.
**Cost: HIGH (correctness of action).** The repo's ONE dynamic-state contract
(`control-status/v1`: `active_runs`, `awaiting_approvals`, `promotable_runs`, `failed_runs`,
`unhealthy_workers`, `projection_lag`, `safe_actions`, `degraded`) is not imported by
`apps/control_room/` at all. The portal instead shows `/api/matrix` states and `/api/flags`, which
overlap but do not cover approvals, promotable/failed runs, worker health, or the derived
`safe_actions`. The operator's permanence decisions (merge/promote) have no board in the room.

### M4 — Registry (canonical state) is an overflow drawer, not a destination.
**Cost: MEDIUM-HIGH (evidence-gathering).** Registry is the authority for "what happened / what
superseded what / why did the system act" (lineage), yet it sits in the System sheet behind a
toggle (`index.html:693-745`) and shares the generic drawer styling. On a wide desktop it forces a
5-column table into a 720 px modal (`style.css:2089-2099`). When the operator needs to *justify*
an action, the evidence surface is the hardest one to reach.

### M5 — Docs health is placed on Fleet, below the pipeline strip and above Live now, in a long single column.
**Cost: MEDIUM (atrophy/alarm fatigue).** Docs health is a standing one-line state — the same kind
of thing as the pipeline strip, which is why it sits there (`index.html:379-413`) — but it renders
four axes + up to 25 inventory rows + a proposal form inline, so on a phone it pushes Live now and
the entire fleet grid below the fold. The one *alertable* item in the room is the hardest to
glance at.

### M6 — Fleet card sparklines spend scarce card space on a mark that cannot support comparison.
**Cost: MEDIUM (scan speed).** Every card draws a 12-sample token bar + cost polyline at 180×36
with a 22 px box (`app.js:300-348`; `index.html` has no card template). The retained history is
capped at 60 samples shipped, the trace is local to each card, and there is no shared scale or
baseline, so the mark cannot compare cards; it only adds paint cost and noise on a large grid.
The prior audit reaches the same conclusion (`control_room_refresh_audit.md:240-244`).

### M7 — `LIVE NOW` duplicates the fleet grid as a second list of the same selectable nodes.
**Cost: MEDIUM (duplicate target / stale ordering).** Live now rows and fleet cards drill into the
same Detail surface (`app.js:537-600`), so the same run can appear twice and be selected from
either, and both re-render on the same 5 s poll. The distinction (phase published within 10 min
vs. all) is real, but the operator pays a duplicate-surface cost to get it.

### M8 — Subscription usage polls every 60 s even while the System sheet is closed.
**Cost: MEDIUM (resource + surprise).** The timer is unconditional (`app.js:3417`); the route then
hits a 15-min cached provider endpoint (`routes/telemetry.py:319-334`). So the browser is warm on
data the operator is not looking at, and because System is also where the registry/queue live, the
closed sheet is doing background work. (Related: five unconditional polls total — §3.1.)

### M9 — The command-rail mirrors cannot be heard.
**Cost: MEDIUM (accessibility).** `.rail-mirrors` is `aria-hidden="true"` (`index.html:73`). The
mirrored Spend/Burn/Running/Redis values are announced only if the operator navigates to the
canonical Status nodes, defeating the purpose of a from-any-board mirror for AT users.

### M10 — Registry rows are `<tr role="button" tabindex=0>`.
**Cost: MEDIUM (keyboard/AT semantics).** `app.js:2451-2453` makes the whole row a pseudo-button,
which is inconsistently announced and gives no native target inside the table. Carried over from
the prior audit (`control_room_refresh_audit.md:294-297`).

### M11 — `queue/reinterleave` has a server route and no affordance.
**Cost: LOW-MEDIUM (operator workaround).** The route is complete and shares the CLI's logic
(`routes/telemetry.py:391-418`), but no JS calls it. Provider-fair queue ordering is a control the
operator can only get from the CLI.

### M12 — Recording coverage (audit + sweep) is entirely outside the room.
**Cost: LOW-MEDIUM (process).** `GET /api/recording-audit` and `POST /api/recording-sweep/run`
exist for the decision-record coverage rail (`routes/recording.py`), including a one-click
backfill, but nothing in the UI reaches them. The room cannot show whether decisions are being
recorded.

### M13 — The pipeline-stage strip moves between Fleet and Status.
**Cost: LOW (orientation).** One DOM node is re-parented per board (`shell.js:102-109`), so the
strip is *never visible on both* boards; switching boards makes context jump. The design asked for
compact-on-Fleet and expanded-on-Status, but the shared-node implementation means an operator
cannot compare fleet and status with the strip in view in both.

### M14 — Native `window.confirm()` interrupts the composed visual language.
**Cost: LOW (polish).** Some irreversible actions use typed two-step doors (`queue clear`,
supervisor interrupt — `index.html:249-261`, `:758-770`) while others fall back to browser
dialogs; the prior audit catalogues the call sites (`control_room_refresh_audit.md:253-258`). Not
a correctness bug, but a visible seam in a "sleek" room.

---

## 6. Absent (no surface exists at all)

Measured by "is there any DOM/route/consumer for this?".

**A1 — A single health/alert aggregate.** No "is anything wrong?" summary and no alert log. The
operator must scan the rail, five boards, and two overflow sections. (Contrast: the control packet
offers `degraded` + `safe_actions` — §2.5.)

**A2 — Projection/latency health in the room.** See M2: the data is measured; the surface is absent.

**A3 — Approvals / permanence queue.** `awaiting_approvals` and `promotable_runs` from the control
packet have no board; there is no place to see what is waiting on a controller decision.

**A4 — Worker / fleet execution health.** `unhealthy_workers` and per-worker throughput are absent;
the room shows cells, not the workers leasing them.

**A5 — Historical trends.** Burn is a 60 s trace; spend is a retained window; there is no
hour/day spend trend, no queue-depth-over-time, no throughput-over-time, and only the usage page's
tabular per-day DeepSeek numbers (`app.js:2330-2340`) — which are not the *framework's* spend.
No chart library is present; every mark is hand-rolled SVG (`app.js:283-287`, `:309-340`).

**A6 — A fleet-level cost/quality comparison.** No per-model or per-condition rollup in the room;
those live in the website's `data.js`/Game Reports, not the operator console.

**A7 — An operator-facing system/architecture diagram.** `architecture.svg` is orphaned (§2.6),
and a control-topology diagram (queues → workers → cells → sessions → projections) does not exist
anywhere.

**A8 — Cross-session search / log search.** Transcript search is a single-cell feed with
Follow/Pause/Clear (`app.js:1522-1675`); there is no search across retained events or sessions.

**A9 — Notifications.** No browser notification, sound, email, or webhook; alerting is pull-only
(§4).

**A10 — Time-zone context and explicit data-age everywhere.** Only a UTC clock; freshness is shown
for the matrix age and supervisor delay, but not systematically on every panel.

**A11 — Auth / multi-operator.** By design the trust boundary is loopback/tailnet
(`services/mutations.py:26-37`), so there is no login, roles, or per-operator audit in the room;
the docs-approval signature is free text (`index.html:407`).

**A12 — Mobile treatment for the wide data surfaces.** Registry and usage tables live in the
System sheet; at ≤420 px the shell stacks (`style.css:2110-2133`) but the sheet is the only
container for two dense tables.

---

## 7. Operator-cost summary (one table)

| Rank | Finding | Class | Cost | Primary evidence |
|---|---|---|---|---|
| M1 | Quota/wallet/lease board buried in System | placement | HIGH | `index.html:774-788`, `routes/telemetry.py:303-356` |
| M2 | Projection health never rendered; route orphaned | absent render | HIGH | `routes/telemetry.py:135-184`, no `static/` hit |
| M3 | `control status` packet absent | absent surface | HIGH | no `control_status` in `apps/control_room/` |
| M4 | Registry overflow not destination | placement | MED-HIGH | `index.html:693-745` |
| M5 | Docs health inline below fold | placement | MED | `index.html:386-413` |
| M6 | Per-card sparkline can't compare | placement | MED | `app.js:300-348` |
| M7 | Live now duplicates grid | duplication | MED | `app.js:537-676` |
| M8 | Hidden System still polls 60 s | cadence | MED | `app.js:3417` |
| M9 | Rail mirrors `aria-hidden` | accessibility | MED | `index.html:73` |
| M10 | Registry rows pseudo-buttons | accessibility | MED | `app.js:2451-2453` |
| M11 | Queue reinterleave no UI | absent affordance | LOW-MED | `routes/telemetry.py:391-418` |
| M12 | Recording audit/sweep no UI | absent affordance | LOW-MED | `routes/recording.py` |
| M13 | Pipeline strip re-parented | placement | LOW | `shell.js:102-109` |
| M14 | Native confirm() seams | polish | LOW | `control_room_refresh_audit.md:253-258` |

---

## 8. Documentation and inventory drift (measured; matters for the facelift)

### 8.1 The route-count docstring is stale.
`server.py:14` says "32 routes across 6 API categories", and `routes/__init__.py:3` says "the 31
routes". The code registers **34** (`app.get`/`app.post`, counted above) across **7** categories;
the 2 recording routes and the docstring's own legacy-telemetry undercount account for the
difference. Any facelift acceptance criterion that pins "28/31/32 routes unchanged" is wrong before
it starts; the correct guard is 34, or better, the enumerated endpoint set in §2.

### 8.2 The design authority cited by the source is at a different path.
`index.html:5`, `style.css` and `shell.js` all cite `docs/control_room_ui/design.md`; the file
actually lives at `docs/website/control_room_ui/design.md` (the docs-taxonomy restructure moved it;
the campaign docs were excepted from the cross-reference repoint — commit `190712d5a`). So the
"design §N" citations throughout the UI code point at a path that does not resolve. This is a
direct docs-drift finding, and the docs-drift rail the room itself monitors does not appear to
catch it (the doc exists, just at another path).

### 8.3 `architecture.svg` is orphaned and path-stale.
`docs/architecture/current/architecture_visual.md:8` still names `admin/static/architecture.svg`;
the asset is at `apps/control_room/static/architecture.svg` and is referenced by nothing. See §2.6.

### 8.4 The route-list docstring omits the recording category entirely.
`server.py:14-33` documents six API categories; `routes/recording.py` is a seventh and is wired by
`routes/__init__.py:42`.

---

## 9. Guardrails a facelift must not break (measured contracts)

These are the invariants the code enforces; §11 restates them as acceptance criteria for the later
facelift phase.

1. **Two-layer reconciliation.** The matrix snapshot owns retained telemetry; SSE overlays live
   samples; replay is bounded by a `replay_complete` boundary and de-dup windows
   (`app.js:1587-1675`, `:1747-1794`, `routes/telemetry.py:230-235`).
2. **One selected event stream.** `replaceEventSource` closes the prior source before opening the
   new one (`control-room-core.js:264-267`; used `app.js:1747-1794`).
3. **Keyed, write-on-change lists.** Fleet/flags/design/Claude rows reconcile by stable key and
   skip same-value writes (`keyed-list.js:88-132`; `board-fleet.js:172-193`); `replaceChildren()`
   is used only for unkeyed units (pipeline, routing, registry, transcript).
4. **No HTML-string rendering.** All content is built with `element()`/`textContent`
   (`app.js:122-127`); cell ids are untrusted and rendered as text (`app.js:419-422`).
5. **Two-axis status language.** Lifecycle (`status-*`) and supervisor attention (`flag-status-*`)
   are separate maps with separate prefixes; color is never the only signal (`board-fleet.js:5-27`,
   `:44-68`).
6. **Mutation trust boundary + idempotency** on every non-GET (`services/mutations.py:40-120`),
   with the explicit typed-confirmation doors preserved (`index.html:249-261`, `:758-770`).
7. **Accessible chrome.** `hidden` (not CSS-only) deactivates boards (`index.html:50-54`); modal
   focus trap exists for System (`shell.js:201-218`) and Detail (`detail-sheet.js:98-121`);
   reduced-motion is honored (`shell.js:190-193`, `detail-sheet.js:185-188`, `style.css:2155-…`).
8. **No build step.** Six classic scripts in dependency order (`index.html:24-26`, `:795-800`).

---

## 10. Prior art and what this audit supersedes

`docs/website/control_room_ui/control_room_refresh_audit.md` (2026-08-23) is a thorough
source audit written for a *visual refresh*. It remains useful for its visual-system critique
(dated elements, confirmation dialogs, rendering smells). This audit **supersedes** it on facts:

- route count: prior says **28**; actual is **34** (`routes/telemetry.py:425-432` adds
  `/api/projections`, and `routes/recording.py` was not in scope then).
- System sheet modality: prior says System "is not" a modal; **current code has
  `role="dialog" aria-modal="true"` (`index.html:680`) and a focus trap (`shell.js:201-218`)**.
- it predates the docs-health panel, the Live-now section, the projections route/payload, the
  subscription-usage/admission co-location, and the recording routes.
- its "28 routes" acceptance criterion (§8.1 here) is now wrong.

This audit adds what the campaign needs and the prior one does not: a complete **panel × feed ×
cadence** map, an explicit **operator-question** map, and a cost-ranked **misplaced/absent**
inventory, all measured from the current tree.

---

## 11. Carry-forward for the campaign (r1 → r7)

The later phases should treat this document as the measured input:

- **r1 (questions):** the §4 glance/drill-down/alert map and the §5 cost ranking are the raw
  operator-needs list; the §6 absences are candidate research questions.
- **r3/r4 (taxonomy/reduction):** §5's "mis-placed" patterns (money state behind an overflow;
  measured-but-unrendered health; authority surface as drawer) are concrete problem categories to
  look for prior art against, not abstract taste.
- **r5/r7 (direction/brief):** §9 is the no-regression contract; §8 is the stale-artifact list the
  direction must reconcile (route count, design-doc path, orphaned SVG).

**Acceptance criteria seed (for r7 to tighten, not this phase):** every §2 panel still renders from
the same route with the same payload shape; every §9 guardrail holds; every §5 finding has an
explicit disposition (moved, merged, rendered, or rejected with reason); M2/M3's absent
authorities are placed by decision, not by accident.

---

## 12. Reproduce

- Route inventory: `grep -rn "app\.\(get\|post\)(" apps/control_room/routes/` → 34.
- Frontend feed map: `grep -nE "fetch\(|EventSource|setInterval" apps/control_room/static/*.js`.
- Panel map: `apps/control_room/static/index.html` (`id="board-*"`, `id="*-panel"`, `id="system-sheet"`).
- Orphan check: for each route token (`projections`, `recording-audit`, `recording-sweep`,
  `queue/reinterleave`), `grep -rl <token> apps/control_room/static/` → no hits.
- Doc lifecycle: every file under `docs/` needs a valid `status` front-matter field
  (`tests/test_doc_lifecycle.py:66-120`); this file carries `status: accepted`.

*End of audit. Measured from `apps/control_room/` at the tree state of this commit; the portal was
not started and no live state was read.*
