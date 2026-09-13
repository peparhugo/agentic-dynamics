---
status: proposed
---

# Control Room UI — three candidate design directions

> **Phase:** candidates (`wt_ui_determination`). This document *generates the menu*; it deliberately
> does **not** pick a winner. The weighted-evaluation, adversarial-review, and final-determination
> phases consume it.
>
> **Question:** what should the Control Room's next design be, decided by process? This artifact
> supplies the three genuinely distinct directions that the process must score, attack, and resolve.
>
> **Inputs (read-only):** the design brief `docs/website/control_room_ui/design_brief.md` (this
> workstream's evidence + criteria pack, produced by phase `d1_evidence_and_criteria`); the accepted
> direction `docs/research/control_room_direction.md` (status: accepted); the canonical glance
> contract `docs/research/control_room_ia.md` §4 (`ON-G1..G7`) and its closed surface palette §14;
> the v2 reference synthesis `docs/research/control_room_ui_reference_synthesis_v2.md` @ `87559ef66`
> (branch `wt_facelift_review`, **not on `main`**); the old dashboard at commit `1457b9299`; the
> parity inventory `experiments/research/control_room/parity_inventory.json`
> (`control-room-parity-inventory/v1`); the current tree at `HEAD` = `0a29f28b4` = `main`; and the
> unmerged new-resting-screen branch `wt_room_new` @ `c06b158a7`.
>
> **Claim discipline.** `[M]` measured in this repository (a `file:line` anchor); `[C]` computed
> (arithmetic over `[M]`); `[X]` external observation at the pinned commit/URL (v2 mechanism IDs +
> anchors; the old dashboard's own code); `[P]` policy — a local/controller decision, never external
> consensus. The old dashboard's anchors are against `1457b9299`; current-tree anchors are against
> `HEAD`.

---

## 0. Scope, constraints, and how to read this document

### 0.1 What the brief asks the room to become

The work item names five outcome elements verbatim:

> **(scroll, charts/SVG, workforce, step durations, old dashboard as base)**

### 0.2 The six mandated specification dimensions

Every candidate below is specified across exactly these dimensions, for every candidate, so the
evaluation phase can score like against like:

1. **Navigation model** — pages/sections, how scrolling works, how selection and drill-down work.
2. **Page/board inventory** — which old boards survive, on which surface, and what is net-new.
3. **Chart set** — the SVG charts (step/phase duration, cost, throughput, queue timing), each with
   where it lives.
4. **Workforce view** — the agents/workers/operators surface and what it shows.
5. **Visual language** — type, colour, density.
6. **Data mapping** — which packet fields / writers feed each element.

### 0.3 The hard constraint: do not reuse the single-screen shell

The current room at `HEAD` is the **single-screen shell**: one resting screen with the `R0..R3`
regions, a hidden selection dock, and a workbench of 13 lenses that swaps one lens into the same
screen (the "single-screen shell"; `apps/control_room/static/index.html:1-68,100-196,206-243,270-297`;
`apps/control_room/static/parity.js:2221-2236`). **None of the three candidates is that shell.** Each
candidate is a different answer to *where things live and how you reach them*; the single-screen
shell is named only as the baseline they depart from (see §1.6).

### 0.4 Shared invariants every candidate must honor

These are not differentiators; they are the floor. Every candidate is composed inside them, and the
evaluation phase should treat a violation as a hard failure, not a scoring deduction.

| Invariant | Authority |
|---|---|
| **Truth/provenance contract** — every consequential value carries source, observation time/age, scope/retained window/truncation, measured/estimated/unknown semantics, and a link; a missing value is `unknown`, never `0`; "green never lies". | Direction §8 (`control_room_direction.md:592-610`); `control_status` packet; `charts.js`'s null-not-zero parser (`charts.js:90-99`) |
| **Glance contract** — the seven `ON-G1..G7` answers, with the single-valued map `ON-G1→R0, ON-G2→R2, ON-G3→R1, ON-G4→R3a, ON-G5→R1, ON-G6→R0, ON-G7→R3c`. | `control_room_ia.md` §4 (`:326-342`); direction §16 (`:776-809`) |
| **No new mutating route class; observe-only rails never steer**; every irreversible act behind its existing typed door + receipt. | Direction §12.2 (`:682-685`); repo rules `AUTHORITY`; v2 A-4/A-12 |
| **No build step / no framework migration** — classic scripts in dependency order. | Direction §12.2 item 8 (`:680`) |
| **One arrangement per breakpoint** — no per-user density switch. | Direction §3.2/§12; v2 §4.3 `Y1` DO-NOT-COPY |
| **Motion budget** — state changes only (≈100–240 ms), no decorative pulse, `prefers-reduced-motion` collapses it. | Direction §11 (`:644-649`); v2 `C13`/`Y1`-adjacent |
| **A11y bar** — WCAG 2.2 AA, status never colour-only, one transition-only polite live region, semantic table controls, forced-colors safe. | Direction §12.1 (`:657-668`); IA G-5 type floor (`:587`) |
| **Parity hard-rule** — every old capability placed, wired, non-empty (or explicit empty state); class-P gate. | Direction §3.6 (`:301-303`); IA §14/§15; `parity_inventory.json` (235 ids, 214 `re-house`, 20 `replace-with-reason`, 1 `preserve`) |
| **SVG authoring** — `viewBox`, `currentColor`, real `<text>`, `<title>`/`<desc>` + role for informative marks. | Direction §10 (`:630-641`) |
| **Chart standard** — every chart states question, decision, baseline/scope, sampling rule, textual equivalent, fallback, and budget; no unconditional default. | Direction §7 (`:570-588`) |

### 0.5 The tension all three must resolve

The brief says **scroll**; the accepted direction §18.2 fixes **"no page scroll and no region
scroll"** for the glancing screen (`:876-880`). The three candidates resolve this differently — that
difference is a primary axis of the evaluation:

- **Candidate 1** keeps the first viewport no-scroll and admits scroll **below** it (linear).
- **Candidate 2** keeps the resting page no-scroll and admits scroll **per destination page** (routed).
- **Candidate 3** keeps the seven answers pinned and admits scroll **per pane** (console).

Each requires the controller to ratify the specific relaxation it makes (§6).

### 0.6 The three directions at a glance

| | Candidate 1 | Candidate 2 | Candidate 3 |
|---|---|---|---|
| **Name** | The Scroll-Synthesized Instrument | The Routed Room | The Workforce Console |
| **Navigation model** | Linear vertical scroll over one document | Multi-page hash router over destinations | Persistent tri-pane (navigator · workspace · dock) |
| **Unit of reach** | A band (fixed position) | A page (a destination) | A selection (an object) |
| **Scroll** | Page scroll below the masthead | Page scroll per destination | Region scroll per pane |
| **Old-dashboard base** | working set as bands | the 7 boards + System as literal pages | working set as navigator groups + workspace subjects |
| **Strongest element** | scroll + parity completeness | deep-linkable destinations + old nav fidelity | workforce + measured step durations |
| **Weakest element** | wall-of-noise risk | board-hopping risk | glance-room risk |

---

## 1. Shared evidence base (all three draw on this)

### 1.1 The old dashboard (`1457b9299`) `[M]/[X]`

- **Seven boards + System overflow**, one board visible at a time, three-column desktop:
  `fleet`, `status`, `flags`, `sessions`, `routing`, `operations`, `surfaces`
  (`apps/control_room/static/shell.js:26`; `static/index.html:367-835`). The transversal **Detail
  surface** (`#detail-surface`, `index.html:146-358`) never arrives cold — it is opened by selecting
  a cell/flag/design/agent.
- **Every board's routes**: Fleet `GET /api/matrix` (5 s) + `/api/status` SSE + `/api/events/<cell>`
  SSE + `/api/docs-health`; Flags `/api/flags?limit=50`; Sessions `/api/design-sessions`,
  `/api/claude-agents`; Routing `/api/routing`; Operations `/api/operations`, `/api/runs/<id>`;
  Surfaces `/api/quality`, `/api/value`, `/api/arms/compare`, `/api/queue/sla`, `/api/escalations`,
  `/api/batch`, `/api/energy`, `/api/stories/<name>/arc`; System `/api/registry`,
  `/api/subscription-usage` (`design_brief.md` §1.2, §1.5).
- **Charts/SVG**: a full-width **burn trace** (`renderBurn`, `app.js:260-294`; `#burn-trace`,
  `index.html:494`) and **per-cell sparklines** (`createSparkline`, `app.js:306-355`). No chart
  library, no canvas, no `<progress>`: progress is a **pipeline stage strip**
  (`renderPipelineStages`, `app.js:718-728`) + a **phase badge** (`phaseBadgeLabel`, `app.js:509-514`).
- **Status language**: a lifecycle vocabulary `○ ◔ ✓ × ◷ ↻ ◻ ?` (`board-fleet.js:45-54`) and an
  attention vocabulary `▲ ■ ◆` (`board-fleet.js:64-68`), always paired with a **word**
  (`applyStatusWord`, `app.js:212-218`) — the origin of the repo's non-colour-only rule.
- **Measured absences**: **no workforce step-timing surface at all**; `queue_wait_ms`,
  `service_time_ms`, `first_token_at` have no view (`control_room_ux_foundation.md:346-354`).
- **Scale**: 235 unique ids, 44 route registrations, 34 canonical endpoints
  (`parity_inventory.json` summary; `design_brief.md` §1.8). The parity inventory's dispositions:
  214 `re-house`, 20 `replace-with-reason`, 1 `preserve`.

**The one literal "old dashboard" policy statement** rejects copying it: *"a layer on top of the
clunk"* (`workflows/repository/control_room_ui_rebuild.yaml:24-29`). So "old dashboard as base" means
**working-set fidelity**, not DOM reuse (§0.4 parity hard-rule).

### 1.2 The current room (`HEAD`) `[M]`

- **The single-screen shell** (§0.3): `R0` truth strip, `R1` attention, `R2` roster, `R3a/b/c` ledger
  (`index.html:100-196`); hidden selection dock `R4a–d` (`index.html:206-243`); a workbench of 13
  lenses (`index.html:270-297`; `parity.js:2221-2236`).
- **`charts.js` catalog** — four SVG+CSS charts, no runtime: `spend`, `throughput`, `failure`,
  `dependency` (`charts.js:39-76`), each already carrying its §7 question/decision/baseline/scope/
  fallback fields (`charts.js:41-76`); a **browser-session retained window** `HISTORY_MAX = 60`
  (`charts.js:35`); `viewBox` + `currentColor` via `svgEl`/`toPoints` (`charts.js:133-153`).
- **The workforce lens** exists but says the timing fields are unobservable
  (`parity.js:1558-1610`); the R4d timings grid renders `queue`/`service`/`first-token` as `unknown`
  (`parity.js:491-570`). This is the brief's central gap.
- **47 routes at `HEAD`** (up from 44): new since the old room are `GET /api/glance` +
  `GET /api/events` (the glance SSE, `routes/glance.py:800,803`) and `GET /api/decisions`
  (`routes/decisions.py:25`). The routes the old room used remain registered and served.
- **`wt_room_new`** (unmerged, 8 ahead) adds a truth strip, attention inbox, run tiles, money+health,
  and session dock tabs, but **no new chart/sparkline/burn surface** (`design_brief.md` §3.5).

### 1.3 The closed surface palette and the glance contract `[M]/[P]`

`control_room_ia.md` §14 (`:1053-1075`) is the closed palette every old id is placed onto, and every
candidate must place all of it:

| Palette | Meaning |
|---|---|
| `R0` | system/trust bar (`ON-G1`, `ON-G6`) |
| `R1` | attention inbox: `R1a` decision, `R1b` risk, `R1c` next (`ON-G3`, `ON-G5`) |
| `R2` | run ledger (`ON-G2`) |
| `R3a`/`R3b`/`R3c` | cost / health detail / bounded composition (`ON-G4`, `ON-G7`) |
| `R4a` | dock address/identity band (`ON-D5`) |
| `R4b` | dock per-worker event stream + action band (`ON-D1`, `ON-D2`, `ON-D7`) |
| `R4c` | dock evidence ladder (`ON-D1`, `ON-D4`) |
| `R4d` | dock step-timing region (`ON-D6`) |
| `L-MONEY`/`L-COMPOSITION` | money history/leases lens; performance lens |
| `L-FLEET` | full roster lens (filters, search, density) |
| `L-ATTENTION` | full inbox (all advisories) |
| `L-HEALTH` | per-projector health lens |
| `L-WORKFORCE` | workforce step-timing lens (aggregate by model) |
| `L-REGISTRY` | canonical-lineage destination (`ON-D4`) |
| `L-SESSIONS` | sessions object type (design + Claude + search) |
| `QUEUE`/`DOCS`/`AUDIT`/`SEARCH`/`SYSTEM` | enqueue·clear·reinterleave / docs-health / recording·decision audit / typed search / topology link |
| `A11Y` | single polite live region (announcement policy) |

A candidate that leaves a palette surface unplaced fails the parity class-P gate (§0.4).

### 1.4 The measured writers (the new data now available) `[M]`

| Signal | Writer | Route today |
|---|---|---|
| `first_token_at` (G-40) | `adapters/opencode.py:558-559`; `runtime/executor.py:259-261`; `runtime/workflow_runner.py:4031-4033` | run ledger only |
| `leased_at` (G-40) | `workflow_runner.py:3824-3890`; `scripts/worker.py:449-461` | run ledger + `/api/queue/sla` (settled) |
| `queue_wait_ms` / `service_time_ms` (G-30/G-31) | `runtime/queue_timings.py:63-118`; `worker.py:347-365` | `/api/queue/sla` (`recent_completions`, `control/projections/sla_queue.py:103-200`) |
| `cost_inference` / `cost_orchestration` (G-41) | `measurement/efficiency.py:249-272`; `workflow_runner.py:4034-4047` | **none** |
| `tokens.answer` / `tokens.explanation` | `adapters/opencode.py:1193-1195`; `runtime/story/models.py:115-116` | `/api/quality` narration (`control/projections/model_quality.py:144-173`) |
| `test_executed_success` | `runtime/test_runner.py` (sole source of truth; `ARCHITECTURE.md`) | run ledger |
| `RunState` (12) / `AttemptState` (7) | `control/control_db.py:140-249,252-289` | `/api/glance`, `/api/operations`, `/api/runs/<id>` |
| `control-status/v1` packet | `control/control_status.py:92,199-334` | `agentic-dynamics control status` |

**The crux:** G-40/G-41/G-30/G-31 are written to the run ledger and `queue_timings.jsonl`, but the
control DB `step_attempts` table (`control_db.py:957-976`) lacks them, so `GET /api/runs/<run_id>`
cannot expose them. Any candidate that renders measured step durations must add **one read-only
exposure** over the existing ledger/timings file (or an additive read model). None may read `unknown`
and call it a duration (`design_brief.md` AD-2).

### 1.5 The v2 mechanisms relevant to navigation, charts, workforce, and visual language `[X]`

Only the mechanisms a candidate actually cites. All are ADOPT or ADAPT per v2 §4 (never
DO-NOT-COPY), and each is reconciled to the accepted direction in §4.1/§4.2 of v2:

| ID | Mechanism | Anchor |
|---|---|---|
| `T1` | Run history as deep-linkable typed event cards | `temporal-ui` `event-card.svelte:126-177,258-316` |
| `T3` | Counts-as-filters (ADAPT: delta age-qualified or dropped) | `temporal-ui` `status-counts.svelte:62-84` |
| `T4` | Query-grammar filter chip | `temporal-ui` `status-filter-chip.svelte:65-108,141-165` |
| `T5` | Pending/retry/completed-with-retries as distinct marks | `temporal-ui` `event-history-legend.svelte:24-50,99,124` |
| `HT1` | Run detail as orthogonal regions | `hatchet` `step-run-detail.tsx:35-42` |
| `HT2` | Mini-map DAG, computed column layout | `hatchet` `mini-map.tsx:63-116` |
| `HT3` | Live trace timeline on a shared time axis | `hatchet` `trace-timeline.tsx:52-85,157` |
| `D1` | Lowercase compact status labels | `dagu` `statusLabels.ts:8-18` |
| `D4` | Per-node table with permission-gated row actions | `dagu` `NodeStatusTable.tsx:29-56` |
| `C3`/`C5`/`C6` | Approvals inbox / loud pause / grants strip | `dashclaw` `approvals/page.tsx:96-150,256-260`; `ApprovalPauseBanner.tsx:15-26`; `ActiveGrantsStrip.tsx:8-23,81-108` |
| `C7` | Queue-unavailable honesty ("last successful result from …") | `dashclaw` `approvals/page.tsx:103,140,456-457` |
| `C8`/`C9` | Causal spine / typed evidence tab | `dashclaw` `CausalTimeline.tsx:27,40-49,78-86`; `EvidenceTab.tsx:20,36,51,70-83` |
| `L3` | Split panes by comfort target (ADAPT: fixed constants, no resize) | `langfuse` `TraceLayoutDesktop.tsx:42-87,115-116` |
| `L4` | Size-gated JSON rendering | `langfuse` `jsonViewSizeGate.ts:1-40` |
| `L5` | Type iconography on a closed type set | `langfuse` `ItemBadge.tsx:43-82,101-121` |
| `O1`/`O2`/`O4`/`O5`/`O6` | Degrade-on-unknown / icon+label+colour / phase+age / derived health / log-scale duration bar with `UNKNOWN` height | `openhands` `run-status-badge.tsx:66-143`; `run-phase.tsx:17-43,65-114,196`; `automation-run-health.ts:11-52`; `automation-run-activity-metrics.ts:9-17,44-63,74-96` |
| `H1`/`H2`/`H3` | Attention column appears first / click-to-land / fingerprint + reconnect | `herdr-portal` `board/web/app.js:160-170,283-290` |
| `Y2` | Provider window/pace limits | `lazyagent` `LimitsPage.svelte` |
| `Y3` | Tiny SVG sparkline (ADAPT: one shared scale, inside a lens only) | `lazyagent` `Sparkline.svelte:1-40` |
| `K2`/`K3` | Accessible canvas mark / uptime clamp | `uptime-kuma` `HeartbeatBar.vue:4-16,76-77`; `Uptime.vue:35-39` |
| `T7`/`C13` | Debounced increases-only announcer / reduced-motion collapse | `temporal-ui` `count-announcer.ts:7-52`; `dashclaw` `HeroDecisionRecord.tsx:1-13,20-24` |

**Forbidden by v2 §4.3 (DO-NOT-COPY):** throwing on unknown status (`HTx`), a per-user density switch
(`Y1`), synced-hover anomaly charts / a chart wall (`N1`), blinking counters, gamification (`F1`),
a new POST verify route by default (`C10`), persisted resizable layout (`L3`), a multi-theme
switcher. Candidates must not lean on these.

### 1.6 The single-screen shell, named so it is not reused `[M]`

The shell that all three depart from: **one resting screen, no page scroll, one selected dock, and a
lens switcher that swaps one lens into the same screen.** Its measured properties: `index.html:1-68`
enforces no page/region scroll; `index.html:270-297` holds the 13-lens workbench; only one lens is
visible at a time; there is no persistent navigator and no simultaneous multi-board view. The three
candidates are distinguished from it explicitly in §5.1.

---

## 2. Candidate 1 — "The Scroll-Synthesized Instrument"

### 2.0 Thesis

> **The room is one document you read top-to-bottom.** The glance contract is the masthead; the old
> room's entire working set is the article below it, stacked as dense, labelled bands. Navigation is
> scroll plus anchors. There are no pages, no tabs, and no lens switcher — every capability has a
> fixed position in one vertical order.

This is the direction the d1 brief's Candidate C pointed at (`design_brief.md` Part III); here it is
specified to the six dimensions.

### 2.1 Navigation model

- **One URL (`/`), one document, vertical scroll only.** No two-axis scroll, no page reloads.
- **Pinned masthead.** The `R0` truth strip (`ON-G1`/`ON-G6`) is `position: sticky` at the top and
  stays visible through the whole scroll — the "scope + trust is always on screen" rule of direction
  §8/§16.
- **In-page anchor nav.** A compact, second-level nav row under the masthead lists the bands
  (`Fleet · Money · Workforce · Trends · Boards · Sessions · System`); each band heading carries an
  `id`, so the band is deep-linkable and the nav is a jump link — the linear analogue of `T1`'s
  deep-linkable event ids (`temporal-ui` `event-card.svelte:126-177`).
- **The first viewport is the no-scroll glance.** `R0` + `R1` + `R2` + `R3a/b/c` exactly as the IA
  fixes them (`control_room_ia.md` §4, `:326-342`); scroll reaches capability, never the glance.
- **Selection is a dock, not a hop.** The `R4a–d` inspector is a fixed right column at ≥1200 px and a
  sticky bottom sheet below 760 px; selecting a row opens it **without moving the page**, and clearing
  it returns scroll exactly (the `H3` fingerprint + keep-last-data + preserved-scroll mechanism,
  `herdr-portal` `board/web/app.js:283-290`, ADAPT).
- **No density switch** (v2 `Y1` DO-NOT-COPY); one arrangement per breakpoint (direction §3.2/§12).
- **A skip link** from the masthead to each band for keyboard users (direction §12.1).

**Scroll economics.** At 1440×900 the masthead + glance is one viewport; the bands follow in a fixed
order. At 390×844 the glance stacks and the bands remain a single column. The design admits page
scroll **below** the glance only — the minimal relaxation of direction §18.2 (open decision §6.1).

### 2.2 Page/board inventory

Old boards survive as **bands**; each is the old board's capability, not its DOM.

| Band (surface) | Old board(s) → target palette | Contents | Net-new |
|---|---|---|---|
| **Masthead** — first viewport | — (glance) → `R0`,`R1`,`R2`,`R3a/b/c` | system/trust, attention, run ledger, cost, composition | — |
| **Fleet** | Fleet + Status pipeline strip → `R2`,`L-FLEET` | full roster, filter chips (`T4`), typed search, live-now, stage strip | — |
| **Money** | Status → `R3a`,`L-MONEY` | burn trace (one scale), five `ON-G4` values, leases, provider window (`Y2`) | — |
| **Workforce** | (net-new) → `L-WORKFORCE`,`R4d` | step/phase duration, queue timing, agents/workers/operators | **yes** |
| **Trends** | (net-new; absorbs the current charts lens) | cost/throughput/failure/dependency SVG | — |
| **Boards** | Flags, Routing, Surfaces, Docs, Audit → `R1`,`L-ATTENTION`,`L-REGISTRY`,`L-COMPOSITION`,`QUEUE`,`DOCS`,`AUDIT` | alert queue, routing table, quality/value/SLA/escalations/batch/energy, docs-health, recording audit, story arc | — |
| **Sessions** | Sessions → `L-SESSIONS`,`R4b` | design composer (spec/input/interrupt/save/run), Claude roster + daemon, owned actions | — |
| **System** | System sheet → `L-REGISTRY`,`QUEUE`,`SEARCH`,`SYSTEM` | registry + lineage, queue actions, typed search, topology link | — |
| **Inspector dock** | Detail surface → `R4a–d` | identity band, per-worker stream + governed actions, evidence ladder, step timings | — |

**Parity reading.** Every palette surface of `control_room_ia.md` §14 is placed on a band or the
dock; the 235 old ids map to bands by their inventory `surface`, so the class-P gate is a fixed,
per-band check. The old order (`shell.js:26` destinations) becomes the band order, which is why
"old dashboard as base" is satisfied as **working-set fidelity** (§1.1) rather than DOM reuse.

### 2.3 Chart set

All charts are SVG+CSS via the existing `charts.js` technique (no runtime; `viewBox` +
`currentColor`; `charts.js:130-153`), extended with two new chart builders. Every card states the
eight §7 fields (the current catalog already demonstrates the pattern, `charts.js:41-76`).

| Chart | Question it answers | Where it lives | Form / mechanism |
|---|---|---|---|
| **Step/phase duration** | Where is the workforce spending time? | Workforce band | Horizontal per-model p50/p95 bars on a **log scale** with an explicit `UNKNOWN` height (`O6`, `automation-run-activity-metrics.ts:9-17,44-63,74-96`) |
| **Queue timing** | Are jobs waiting on the queue or on the model? | Workforce band | Stacked span bars per attempt on a shared time axis (`HT3`, `trace-timeline.tsx:52-85`), fed by `queue_wait_ms`/`service_time_ms`; textual table alongside |
| **First-token latency** | How fast does the model start answering? | Workforce band | p50/p95 bars, same axis and scale as step duration (one shared scale, direction §7 priority 3) |
| **Cost / burn** | Is spend trending toward the cap? | Money band + Trends band | `spend`/`burn` line on **one shared scale** (`charts.js` `spend`, `:261-270`); cap as a bounded quantity+progress, not a free-floating chart |
| **Throughput** | Is the fleet moving work or backing up? | Trends band | running/queued/live lines (`charts.js` `throughput`, `:271-280`); scope = browser session unless served from `/api/queue/sla` `recent_completions` (AD-5) |
| **Failure** | Are failures accumulating or clearing? | Trends band | `charts.js` `failure` (`:281-`); baseline zero; fallback = the `ON-G3` risk answer |
| **Dependency health** | Are the room's dependencies healthy? | Trends band | `charts.js` `dependency`; gauge only because a maximum (lag 0) exists (direction §7 priority 4) |
| **Provider-window pace** | How full is the 5h/7d window? | Money band | bounded quantity + progress (`Y2`, `LimitsPage.svelte`), sourced from usage/settlement ledger |

**Restraint rules.** No chart on the masthead (direction §4.5 budget); a missing value is a **gap**,
not zero (`charts.js:90-99`); <2 samples is an explicit empty state; the Trends charts label their
retained window and never imply server history when it is browser-session only (AD-5).

### 2.4 Workforce view (agents / workers / operators)

The brief's parenthetical is read as three tiers of one workforce, all in the **Workforce band**,
each sourced from measured fields (§1.4):

| Tier | Who | Shows | Source |
|---|---|---|---|
| **Agents** | agent sessions / cells (opencode), design sessions | session id, model, workdir, current phase/tool, attempt, live state; **per-attempt step timings** (mirrors `R4d`) | `/api/matrix` cells; run ledger `AttemptRecord`; `first_token_at`/`leased_at` (G-40) |
| **Workers** | the Redis queue workers + control-plane lease holders | worker health (`unhealthy_workers`), occupancy, concurrency leases, queue depth, **queue-wait/service-time distributions** | control packet; `/api/queue/sla` `recent_completions`; `queue_timings.jsonl` (G-30/G-31) |
| **Operators** | the humans in the loop (controller, AIO) | pending decisions (`awaiting_approvals`), promotable runs, live grants, docs-health signer, decision records | control packet; `/api/flags`; `/api/decisions`; `/api/docs-health`; `C3/C5/C6/C8` |

The fleet aggregate is the band; the per-run timing grid is the dock (`R4d`). **No per-card
sparkline** anywhere on the resting roster (direction §4.3; v2 `O6` relaxation: the duration mark
fires only inside the workforce band).

### 2.5 Visual language

- **Type.** System UI sans for labels/prose; **monospace** for identity (session token, worktree,
  command) and every numeric/unit, per the direction's identity band (`control_room_direction.md:487-488`).
  Type floor IA G-5 (`control_room_ia.md:587`): ≥13 px desktop, ≥12 px mobile, labels ≥11 px.
- **Colour.** A semantic token set only — `surface`, `line`, `text-primary`, `text-muted`, plus a
  small status set. **State = glyph + word + colour** (`O2`/`D1`/`T5`); the single brand-orange cue is
  reserved for `awaiting_promotion` (`C2`, `decisions/[actionId]/page.tsx:26-35`); no decorative glow
  or pulse (direction §4.5). Light/dark/forced-colors via system colors + `currentColor`
  (direction §10/§12.1).
- **Density.** Dense, banded, and aligned: each band has a one-line header carrying its **scope,
  source, and age** (direction §8 per-value provenance), separated by hairline rules; density comes
  from alignment, not card chrome (direction §4.4). The §4.5 **thesis-failure rule** is applied
  *per band* — a band must not read as "truth bar + alert cards + service table + KPI rail".
- **Motion.** Transitions only, ≈100–240 ms, decelerating; `prefers-reduced-motion` collapses
  (`C13`; direction §11).

### 2.6 Data mapping

| Element | Packet field / route | Writer (`file:line`) |
|---|---|---|
| Masthead system/trust (`ON-G1`/`ON-G6`) | `control-status/v1` `degraded`, `projection_lag`, `control_epoch`; `/api/glance` | `control_status.py:92,199-334` |
| Attention (`ON-G3`/`ON-G5`) | `awaiting_approvals`, `promotable_runs`, `failed_runs`, `safe_actions` | `control_status.py`; `/api/flags` |
| Run ledger (`ON-G2`) | `/api/matrix` cells + `active_runs` with `phases_completed/phases_total` | `routes/telemetry.py:462`; `control_status.py` |
| Cost (`ON-G4`) | `/api/matrix` `reported_cost`, `history_capped`; `/api/subscription-usage`; `/api/queue/sla` | `routes/telemetry.py`; usage/settlement ledger (`usage/subscription_usage_latest.json`) |
| Composition (`ON-G7`) | bounded model × condition × provider × lifecycle marginals | `/api/glance` |
| Step/phase duration chart | ledger `started_at`/`ended_at`; `first_token_at`; run-ledger JSON | `workflow_runner.py:247-256,4031-4033` |
| Queue-timing chart | `queue_wait_ms`/`service_time_ms` | `runtime/queue_timings.py:63-118`; `worker.py:347-365` |
| Cost inference/orchestration split | `cost_inference`/`cost_orchestration` | `measurement/efficiency.py:249-272`; `workflow_runner.py:4034-4047` |
| Answer/explanation tokens | `/api/quality` narration | `adapters/opencode.py:1193-1195`; `model_quality.py:144-173` |
| Workforce agents | `/api/matrix` cells; ledger `AttemptRecord` | `run_story.py`/`run.py` writers |
| Workforce workers | `unhealthy_workers`; `/api/queue/sla` `recent_completions` | control packet; `sla_queue.py:103-200` |
| Operators | `awaiting_approvals`, `promotable_runs`; `/api/decisions`; `/api/docs-health` | control packet; `routes/decisions.py:25` |
| Inspector `R4a–d` | `/api/events/<cell>` SSE, `/api/runs/<id>`, `/api/operations` | `routes/telemetry.py:465`; `routes/operations.py:28-29` |

**The one required read-only addition** (§1.4, AD-2): a `GET` over the run ledger / `queue_timings.jsonl`
exposing `queue_wait_ms`, `service_time_ms`, `first_token_at`, `cost_inference`, `cost_orchestration`
to the workforce band and `R4d`. It is read-only and mutates no schema (open decision §6.2).

### 2.7 Evidence for / against

**For.** Answers all five brief elements. The first viewport preserves the `ON-G1..G7` glance intact.
A single linear order is the **cheapest** way to make the parity class-P gate pass — every old id has a
fixed band home. Band anchors give deep-linkable addresses (`T1`). `H3` keeps scroll and last data on
disconnect. It is the lightest server change (one read-only timing route) and adds no navigation
state machine.

**Against.** A long page is the easiest place to reintroduce a generic dashboard wall — the exact
failure the direction's §4.5 thesis-failure rule names (AD-4). It requires ratifying direction §18.2's
scroll relaxation (§6.1). Per-value provenance must stay attached down a long document. The anchor nav
is a second navigation contract the render gate must test.

---

## 3. Candidate 2 — "The Routed Room"

### 3.0 Thesis

> **Every old destination is still a destination.** The room is a small multi-page application: a
> persistent global truth strip, a destination rail, one scrollable page per board, and a run
> inspector that is itself an addressable route — so any run deep-links and back always returns you
> exactly where you were.

The old dashboard's defining navigation (`shell.js:26`: seven destinations + System) is the base; this
candidate modernizes it with page scroll, a persistent truth strip, and route-addressable runs.

### 3.1 Navigation model

- **Hash-routed pages** (no build step; fragment routing is classic-script compatible): `#/fleet`,
  `#/money`, `#/flags`, `#/sessions`, `#/routing`, `#/operations`, `#/surfaces`, `#/workforce`,
  `#/system`, and `#/run/<id>` for the inspector. Each page is its own document and **its page body
  scrolls**.
- **Persistent global chrome:** the `R0` truth strip (`ON-G1`/`ON-G6`) sits above every page; a left
  **destination rail** reproduces the old `["fleet","status","flags","sessions","routing",
  "operations","surfaces"]` + System (`shell.js:26`); a breadcrumb + page-scoped filter bar carries
  the `T4` query-grammar chip.
- **The inspector is a push route.** `#/run/<id>` is a deep-linkable address (`T1`,
  `event-card.svelte:126-177`); on desktop it docks right, on mobile it is a full page. Back returns
  to the originating page with scroll restored (`H3`).
- **`adoptRegions` is retired.** The old room re-parented one pipeline strip between Fleet and Status
  (`shell.js:102-109`); here the strip lives once on `#/fleet` and the truth strip is global, so no
  shared region moves.
- **The resting page is `#/fleet`.** Its initial viewport must still pass the glance check; page
  scroll applies only to the board pages below the fold.
- One arrangement per breakpoint; no density switch (`Y1`).

### 3.2 Page/board inventory

Old boards survive as **literal pages**.

| Route | Old board | Target palette | Contents | Net-new |
|---|---|---|---|---|
| `#/fleet` | Fleet | `R2`,`L-FLEET` | roster, `T4` filters, search, stage strip, live-now | — |
| `#/money` | Status | `R3a`,`L-MONEY` | burn, five `ON-G4`, leases, provider window, cost/throughput charts | — |
| `#/workforce` | (net-new) | `L-WORKFORCE`,`R4d` | step/phase duration, queue timing, agents/workers/operators | **yes** |
| `#/flags` | Flags | `R1`,`L-ATTENTION` | alert queue, steer/interrupt doors | — |
| `#/sessions` | Sessions | `L-SESSIONS`,`R4b` | design + Claude controls, daemon | — |
| `#/routing` | Routing | `R4a`,`L-COMPOSITION` | routing recommendations, strategy simulation | — |
| `#/operations` | Operations + Surfaces | `R4c`,`AUDIT`,`L-REGISTRY`,`DOCS`,`QUEUE` | run detail, quality/value/SLA/escalations/batch/energy, docs-health, recording audit, story arc | — |
| `#/system` | System sheet | `L-REGISTRY`,`QUEUE`,`SEARCH`,`SYSTEM` | registry + lineage, queue actions, typed search, topology link | — |
| `#/run/<id>` | Detail surface | `R4a–d` | identity, stream + governed actions, ladder, timings | — |

**Parity reading.** The old 7 + System survive **as navigation**, which is the strongest possible
reading of "old dashboard as base" that still passes the parity hard-rule (the *working set* survives,
re-composed). The extra two routes (`#/workforce`, `#/run/<id>`) are the additions the brief demands;
neither is a mutating route.

### 3.3 Chart set

Charts live on the page whose question they answer (direction §7 "no unconditional default": a chart
must change a page's decision).

| Chart | Question | Page | Form / mechanism |
|---|---|---|---|
| **Step/phase duration** | Where does the workforce spend time? | `#/workforce` | log-scale per-model bars with `UNKNOWN` height (`O6`) |
| **Queue timing** | Queue-bound or model-bound? | `#/workforce` | shared-axis span bars (`HT3`) from `queue_wait_ms`/`service_time_ms` |
| **First-token latency** | How fast is first token? | `#/workforce` | p50/p95 bars, same shared scale |
| **Cost / burn** | Trending to the cap? | `#/money` | one shared-scale line (`charts.js` `spend`) + cap progress |
| **Provider window** | How full is the window? | `#/money` | bounded quantity + progress (`Y2`) |
| **Throughput** | Moving or backing up? | `#/money` | running/queued/live lines (`charts.js` `throughput`) |
| **Phase waterfall** | What happened in this run? | `#/run/<id>` | bounded causal timeline, one question per step (direction §7 priority 2; `HT3`) |
| **Failure** | Accumulating or clearing? | `#/operations` | `charts.js` `failure`, zero baseline |
| **Dependency health** | Dependencies healthy? | `#/fleet` | `charts.js` `dependency` gauge (maximum exists) |
| **Composition mini-map** | What is this run's phase shape? | `#/run/<id>` | computed-column mini-map (`HT2`, `mini-map.tsx:63-116`) |

No ambient charts on the rail or the truth strip; each card keeps its §7 fields and its fallback.

### 3.4 Workforce view (agents / workers / operators)

The workforce gets a **full page** — `L-WORKFORCE` promoted from a lens to a destination, with the
same three tiers as Candidate 1 but laid out as page sections:

- **Agents** — a per-session/attempt table (`D4` per-node table with permission-gated row actions,
  `NodeStatusTable.tsx:29-56`): model, workdir, phase, attempt, step duration, tokens by
  answer/explanation, cost provenance.
- **Workers** — the queue/control-plane pool: health (`unhealthy_workers`), occupancy, leases, and
  the queue-wait/service-time distributions.
- **Operators** — a compact decision queue (`C3`): pending approvals, promotable runs, live grants
  with inline revoke (`C6`), docs-health signer, decision records (`C8`).

The per-run `R4d` grid is on `#/run/<id>`, so the fleet aggregate and the per-attempt detail are
separated exactly as direction §3.6 requires.

### 3.5 Visual language

- **Same domain grammar** as Candidate 1 (monospace identity band, hairline attempt boundary,
  ADVISORY "said" vs MEASURED test-runner glyph, hollow/solid action affordances, lease headroom bar;
  `control_room_direction.md:484-498`).
- **Page headers are quiet:** a lowercase page title (`D1`, `statusLabels.ts:8-18`), its scope, its
  refresh age, and its provenance — **never a KPI-tile row** (direction §4.3/§4.5; v2 conflict 1).
- **Colour, type floor, motion, forced-colors:** identical token set and floors to Candidate 1
  (direction §10–§12; IA G-5).
- **Density:** page-level breathing room around dense tables; the rail is the constant, so each page
  can be focused. Counts-as-filters are age-qualified, never a bare stale delta (`T3` ADAPT; v2 A-6).
- **Each page carries its own provenance header**; the global footer keeps only scope, connection,
  control epoch, and the compact degraded summary (direction §8).

### 3.6 Data mapping

Same route/field sources as §2.6; the mapping is a per-page assignment rather than a per-band one:

| Page | Primary routes/fields | Writer |
|---|---|---|
| `#/fleet` | `/api/matrix`, `/api/status` SSE, `/api/docs-health`, `active_runs` | `routes/telemetry.py`; `control_status.py` |
| `#/money` | `/api/matrix` cost + tokens, `/api/subscription-usage`, `/api/queue/sla`, `cost_inference`/`cost_orchestration` | usage/settlement ledger; `efficiency.py:249-272` |
| `#/workforce` | ledger `AttemptRecord`, `queue_timings.jsonl`, `/api/quality`, `/api/queue/sla` | `queue_timings.py:63-118`; `model_quality.py:144-173` |
| `#/flags` | `/api/flags` | `routes/flags.py:90` |
| `#/sessions` | `/api/design-sessions`, `/api/claude-agents` | `routes` sessions handlers |
| `#/routing` | `/api/routing` | `routes/telemetry.py:466-467` |
| `#/operations` | `/api/operations`, `/api/runs/<id>`, `/api/projections`, `/api/quality` | `routes/operations.py:28-29`; `routes/analytics.py` |
| `#/system` | `/api/registry`, `/api/registry/<id>` | `routes/registry.py:93` |
| `#/run/<id>` | `/api/runs/<id>`, `/api/events/<cell>` SSE | `routes/operations.py`; `routes/telemetry.py:465` |

The same **one read-only timing exposure** (§1.4) is required by `#/workforce` and `#/run/<id>`.

### 3.7 Evidence for / against

**For.** The strongest reading of "old dashboard as base": the seven destinations + System survive
*as navigation* (`shell.js:26`), which the parity inventory can check route-by-route. The inspector as
a route gives every run a stable, shareable address (`T1`). Page-scoped charts satisfy §7's "no
unconditional default" by tying each chart to a page's decision. Scroll is per destination, so the
resting page can still pass the glance check.

**Against.** It needs a small router/state layer that the no-build constraint must carry (fragment
routing is achievable with classic scripts, but it is new navigation code to gate). Page switching is
"board hopping" the direction warns against (`control_room_direction.md` §3.2/§9) unless the
inspector deep-link is the only hop. It carries the most navigation chrome, and every page must
individually satisfy provenance and the restraint budget.

---

## 4. Candidate 3 — "The Workforce Console"

### 4.0 Thesis

> **The room's primary object is the workforce** — the agents doing the work, the workers running
> them, and the humans steering. So the room is a persistent tri-pane console: a fleet/worker
> **navigator** on the left, a scrolling measured-timing **workspace** in the centre, and an
> evidence/action **dock** on the right. The glance contract is a pinned header, not a page.

This makes the brief's most-under-served elements (workforce + measured step durations) the centre of
the product rather than a band or a page.

### 4.1 Navigation model

- **A persistent three-pane shell**, all panes visible at once, each independently scrollable:
  1. **Left navigator** — the fleet/worker list grouped by Agents / Workers / Operators, with
     counts-as-filters (`T3`, age-qualified) and typed search (`T4`). Selecting an object drives the
     centre and the dock.
  2. **Centre workspace** — the selected subject's reading: the fleet run ledger by default; a
     worker's expanded measured timings (`R4d` promoted); or a board (money/registry/routing/surfaces)
     as a workspace subject. A workspace switcher changes the **subject**, not the page.
  3. **Right dock** — `R4a` identity, `R4b` stream + governed actions, `R4c` evidence ladder for the
     selected object (`HT1` orthogonal regions, `step-run-detail.tsx:35-42`).
- **Pinned glance.** The `R0` truth strip spans all three panes; `R1` attention, `R3a` cost,
  `R3b` health, and `R3c` composition sit as pinned gutters so the first viewport still answers
  `ON-G1..G7`. This is the crux to test: a console must not lose the glance (IA §4; §5.4).
- **Region scroll is the disclosure axis** (below the pinned glance). Splits follow `L3`
  comfort-band math but are **fixed layout constants** — no persisted resize (`L3` ADAPT; v2 §4.3).
- **Deep-link.** Selected object + workspace live in the URL fragment (`T1`); `H3` preserves state on
  reconnect.
- **Mobile** collapses the panes to a stacked subject → evidence order — triage, not a wall
  (direction §3.5, `:276-282`).
- One arrangement per breakpoint; no density switch (`Y1`).

### 4.2 Page/board inventory

Old boards survive as **navigator groups + workspace subjects**.

| Zone | Old board(s) → target palette | Contents | Net-new |
|---|---|---|---|
| **Navigator** | Fleet + Flags + Sessions rosters → `R2`,`R1`,`L-FLEET`,`L-ATTENTION`,`L-SESSIONS` | agent/worker/operator grouping, counts-as-filters, typed search | grouping |
| **Workspace: fleet** (default) | Fleet + Status → `R2`,`R3a`,`L-MONEY` | run ledger + workforce aggregate | — |
| **Workspace: workforce** | (net-new) → `L-WORKFORCE` | agent timing table, worker pool, operator queue | **yes** |
| **Workspace: money** | Status → `R3a`,`L-MONEY` | burn, leases, provider window, cost/throughput charts | — |
| **Workspace: routing/surfaces** | Routing + Surfaces + System → `L-REGISTRY`,`L-COMPOSITION`,`QUEUE`,`DOCS`,`AUDIT` | read-model boards, registry/lineage, docs-health, audit | — |
| **Dock** | Detail surface → `R4a–d` | identity, stream + governed actions, ladder, timings | — |
| **Pinned gutters** | — | `R1` attention, `R3a` cost, `R3b` health, `R3c` composition | — |

**Parity reading.** Every palette surface is placed as a navigator group, a workspace subject, a
dock region, or a pinned gutter. The old boards' capability is preserved; their page boundary is
replaced by a subject selection. "Old dashboard as base" is satisfied as working-set fidelity.

### 4.3 Chart set

Charts attach to the workspace subject and the dock — never ambient (the navigator carries none, per
the restraint budget and the `N1` DO-NOT-COPY chart-wall ban).

| Chart | Question | Where | Form / mechanism |
|---|---|---|---|
| **Step/phase duration** | Where does the workforce spend time? | Workforce workspace | log-scale per-model bars with explicit `UNKNOWN` (`O6`) |
| **Queue timing** | Queue-bound or model-bound? | Workforce workspace | shared-axis span bars (`HT3`) from `queue_wait_ms`/`service_time_ms` |
| **First-token latency** | How fast is the first token? | Workforce workspace | p50/p95 bars, shared scale |
| **Retry rate / tokens by model** | Is the fleet churning or producing? | Workforce workspace | counts + table first, then one-scale bars (direction §7 priority 1) |
| **Cost / burn** | Trending to the cap? | Money workspace | one shared-scale line (`charts.js` `spend`) |
| **Provider window** | How full? | Money workspace | bounded quantity + progress (`Y2`) |
| **Throughput** | Moving or backing up? | Money workspace | running/queued/live lines (`charts.js` `throughput`) |
| **Phase waterfall + mini-map** | What happened in this run? | Dock `R4d` + workspace | bounded causal timeline (`HT3`) + computed-column mini-map (`HT2`) |
| **Dependency health** | Dependencies healthy? | Fleet workspace | `charts.js` `dependency` gauge (maximum exists) |

No chart on the navigator; every card keeps the §7 fields; a missing value is a gap.

### 4.4 Workforce view (agents / workers / operators)

The console **is** the workforce view. The three tiers are simultaneously the navigator groups, the
workspace subjects, and a shared aggregate:

- **Agents** — navigator group + expanded timing table: session, model, workdir, phase, attempt,
  step duration, first-token, retry, tokens by answer/explanation, cost provenance (`D4` gated rows).
- **Workers** — navigator group + worker panel: health (`unhealthy_workers`), occupancy, leases,
  queue depth, queue-wait/service-time distributions.
- **Operators** — navigator group + decision queue (`C3`): pending approvals, promotable runs, grants
  with inline revoke (`C6`), docs-health signer, decision records (`C8`).

Because the workforce is the default workspace, the brief's *workforce* and *step durations* elements
are delivered as the room's spine rather than reached by drilling.

### 4.5 Visual language

- **Same domain grammar** as Candidates 1–2; console chrome is deliberately quiet: 1 px pane rules,
  no card borders, density from alignment (direction §4.1/§4.4).
- **Navigator rows are the identity band**: session token + worktree + current command in monospace
  (`control_room_direction.md:487-488`), with a `D1`/`O2` glyph+word status.
- **Attempt boundary** is a hairline rule with attempt number, model, timestamps — attempts stack,
  not cards (`:489-490`).
- **Colour, type floor, motion, forced-colors:** identical token set and floors to Candidate 1
  (direction §10–§12; IA G-5).
- **Density** is the highest of the three (it is a console), but the §4.5 restraint budget and the
  thesis-failure rule still apply; no decorative pulse or glow.
- **Pane headers** carry scope + source + age (direction §8).

### 4.6 Data mapping

| Element | Packet field / route | Writer |
|---|---|---|
| Navigator agents | `/api/matrix` cells; `/api/glance` roster | `routes/telemetry.py:462`; `control_status.py` |
| Navigator workers | `unhealthy_workers`; `/api/queue/sla` | control packet; `sla_queue.py:103-200` |
| Navigator operators | `awaiting_approvals`, `promotable_runs`; `/api/flags`; `/api/decisions` | control packet; `routes/decisions.py:25` |
| Workspace fleet ledger | `/api/matrix`, `active_runs` w/ `phases_completed/phases_total` | `control_status.py` |
| Workspace workforce timings | ledger `AttemptRecord`; `first_token_at`; `queue_wait_ms`/`service_time_ms`; `/api/quality` | `queue_timings.py:63-118`; `opencode.py:558-559`; `model_quality.py:144-173` |
| Workspace money | `/api/matrix` cost/tokens; `/api/subscription-usage`; `cost_inference`/`cost_orchestration` | usage/settlement ledger; `efficiency.py:249-272` |
| Dock `R4a–d` | `/api/runs/<id>`; `/api/events/<cell>` SSE; `/api/operations` | `routes/operations.py:28-29`; `routes/telemetry.py:465` |
| Pinned gutters | `R1` attention; `R3b` health; `R3c` composition | `/api/glance`; control packet |

The same **one read-only timing exposure** (§1.4) feeds the workforce workspace and the dock.

### 4.7 Evidence for / against

**For.** Makes workforce + measured step durations the product's centre, directly answering the
brief's least-served elements. `L3` split panes, `D4` per-node tables, and `HT3` timelines are strong
external patterns (`langfuse`/`dagu`/`hatchet`). Region scroll is admitted only below the pinned
glance, which the IA contract permits for non-answer regions (`control_room_ia.md` §4). Deep-link
addresses (`T1`).

**Against.** It is the closest in spirit to the current room's dock + lens shell, so the "do not
reuse the single-screen shell" boundary must be enforced by the **persistent navigator plus three
simultaneous panes** (the current shell shows one lens at a time with no navigator). Region scroll on
the first viewport is the riskiest relaxation of direction §18.2; at 1024 px and mobile the three
panes must still fit the seven answers. It is the most complex of the three to gate.

---

## 5. Cross-candidate comparison (the evaluation input)

This section exists so the weighted-evaluation phase can score like against like. It deliberately
does not compute the weighted total — that is the next phase's act.

### 5.1 How each departs from the single-screen shell

| Property of the single-screen shell (`HEAD`) | Candidate 1 | Candidate 2 | Candidate 3 |
|---|---|---|---|
| One screen, no page/region scroll | page scroll below the glance | page scroll per destination | region scroll per pane |
| No persistent navigator | anchor nav (in-page) | destination rail (persistent) | navigator pane (persistent) |
| One lens visible at a time | all bands in one order | one page at a time | three panes simultaneously |
| No addressable run | band anchors only | `#/run/<id>` deep-link | object + workspace fragment |

### 5.2 The five brief elements per candidate

| Brief element | Candidate 1 | Candidate 2 | Candidate 3 |
|---|---|---|---|
| **scroll** | page scroll below the masthead | page scroll per destination | region scroll per pane |
| **charts/SVG** | Trends band + workforce band + money band | per-page charts (money/workforce/operations) | workspace + dock charts |
| **workforce** | first-class workforce band (3 tiers) | first-class workforce page (3 tiers) | the console's spine (3 tiers) |
| **step durations** | workforce band + `R4d` via one read-only route | workforce page + `#/run/<id>` via the route | workforce workspace + dock via the route |
| **old dashboard as base** | working set as bands | the 7 boards + System as literal pages | working set as navigator groups + subjects |

### 5.3 Old-surface placement (parity coverage)

| Palette surface | C1 | C2 | C3 |
|---|---|---|---|
| `R0`/`R1`/`R2`/`R3a/b/c` | masthead | global strip + fleet page | pinned gutters |
| `R4a–d` | inspector dock | `#/run/<id>` | right dock |
| `L-FLEET`/`L-ATTENTION`/`L-MONEY`/`L-COMPOSITION` | bands | pages | workspace subjects |
| `L-WORKFORCE` | workforce band | workforce page | workforce workspace |
| `L-REGISTRY`/`L-SESSIONS`/`QUEUE`/`DOCS`/`AUDIT`/`SEARCH`/`SYSTEM` | Boards/Sessions/System bands | Operations/System pages | workspace + navigator |
| `A11Y` | masthead live region | global strip live region | shell live region |

### 5.4 Shared risks (for the adversarial phase)

1. **The read-only timing exposure (AD-2).** All three need it; none may read `unknown` as a
   duration. This is a shared controller decision (§6.2).
2. **Scroll ratification (AD-1).** All three relax direction §18.2 in some form (§6.1).
3. **Wall-of-noise / chart-wall drift (§4.5, `N1`).** C1's long page and C3's panes are the two
   riskiest surfaces; C2 spreads the risk across pages.
4. **Glance preservation under selection.** C3's three-pane state is the hardest to keep
   `ON-G1..G7`-complete; C1's is the easiest.
5. **v2 provenance (AD-10).** v2 is `proposed`, not on `main`; every adopted mechanism must reconcile
   to the accepted direction, never to v2 alone.

### 5.5 What the evaluation phase must decide

- The weighted score (the eight criteria in `design_brief.md` Part II) per candidate.
- Which scroll relaxation to ratify (and at which breakpoints).
- Whether a persistent navigator (C3) or a routed destination (C2) better satisfies "old dashboard
  as base" without board-hopping.
- Whether the workforce should be a band (C1), a page (C2), or the spine (C3).

---

## 6. Open decisions surfaced by the candidates (controller-only, P0)

These are **not** candidate choices; they are policy choices the design cannot make for itself. They
are carried into the determination.

1. **Ratify scroll.** C1 admits page scroll below the masthead; C2 per destination page; C3 per pane.
   All relax direction §18.2's "no page scroll and no region scroll" (`:876-880`) while keeping the
   first viewport's `ON-G1..G7` intact. The alternative — keep no-scroll exactly — forces the
   single-screen shell and forgoes the brief's *scroll* element.
2. **Ratify the read-only timing exposure.** G-40/G-41/G-30/G-31 are measured but reach no route
   (`design_brief.md` §3.6). Choose (a) a new read-only `GET` over the run ledger /
   `queue_timings.jsonl`, or (b) an additive control-DB read model. Both are read-only; (b) touches
   the schema and is the heavier path.
3. **Ratify "old dashboard as base" as working-set fidelity, not DOM reuse** — consistent with the
   parity hard-rule and the earlier rebuild rejection (`control_room_ui_rebuild.yaml:24-29`).
4. **Confirm v2's status.** If any v2-only mechanism is adopted, decide whether to land v2
   (`87559ef66`) on `main` or keep it a pinned, branch-local evidence reference.

---

## Appendix — source pins and citation key

- **Old dashboard:** `1457b9299` — `apps/control_room/static/index.html` (847 lines),
  `app.js` (4109 lines), `shell.js` (438), `board-fleet.js` (228), `detail-sheet.js` (334);
  235 unique ids, 44 route registrations, 34 canonical endpoints.
- **Current room:** `HEAD` = `0a29f28b4` = `main` — `index.html` (321 lines), 47 routes,
  `charts.js`, `visuals.js`, `parity.js`.
- **New resting screen:** `wt_room_new` @ `c06b158a7` (8 commits ahead of `main`, unmerged).
- **v2 synthesis:** `docs/research/control_room_ui_reference_synthesis_v2.md` @ `87559ef66`
  (branch `wt_facelift_review`); mechanism IDs cited inline.
- **Accepted direction:** `docs/research/control_room_direction.md` (status: accepted).
- **Glance contract + palette:** `docs/research/control_room_ia.md` §4 (`ON-G1..G7`), §3.2 (pixel
  budget/type floor G-5), §14 (closed palette), §15 (class-P gate).
- **Parity:** `experiments/research/control_room/parity_inventory.json`
  (`control-room-parity-inventory/v1`).
- **Writers:** `dc51c77ef` / `a289e87db` ("G-14 evaluator_independent, G-40 attempt timings, G-41
  cost split"); `c8ca59832`; `d1f8a8279`.
- **Briefs/work orders:** `workflows/repository/control_room_ux_repair.yaml`,
  `workflows/repository/control_room_ui_rebuild.yaml`,
  `workflows/repository/control_room_facelift_review.yaml`.
- **This workstream's evidence pack:** `docs/website/control_room_ui/design_brief.md`.
