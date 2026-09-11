---
status: accepted
---

# Control Room — the one resting screen (campaign `control_room_research_repair`, phase `p2_fix_glance_ia`)

**Date:** 2026-09-11
**Question answered:** can ONE resting screen answer the operator glance needs `ON-G1..G7`
(`docs/research/control_room_questions.md` §4.1) with **no interaction**, and where exactly is
each answer on that screen?
**Inputs:** the measured portal audit `docs/research/control_room_audit.md` (r0 panels/feeds),
the operator-needs contract `control_room_questions.md` (r1), the reworked direction
`control_room_direction.md` (p1), the repaired catalogs, and the IA adversary pass r6c
(`docs/reviews/control_room_research_ia.md`, findings IA1–IA16).
**Verdict carried from r6c:** the r5 one-active-board IA was *physically incapable* of the
no-interaction contract (IA1). This document replaces it with a single resting screen whose regions
are all present at once.

**Claim discipline.** `[M]` measured (r0/the repository), `[X]` external exemplar, `[P]` local
design policy. "At rest" is a precise term here: **visible in the default viewport with zero
interaction** — no tab, lens, board, modal, hover, or filter applied. Scrolling inside the single
screen is allowed but is treated as failure of the "glance" only where the need is placed below the
fold (stated explicitly in §5).

---

## 1. The resting screen, defined

The resting screen is **one scrollable layout**, not a set of destinations. It is organized as a
persistent qualifier bar over a **three-column body**:

```text
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ R0  SCOPE / TRUTH BAR   (full width, one line, always visible)                        │
│     repo | worktree/campaign | conn | control-plane | epoch | degraded summary         │
├──────────────────────┬────────────────────────────────┬───────────────────────────────┤
│ R1  ATTENTION INBOX   │ R2  RUN ROSTER                  │ R3  CONSTRAINT RAIL            │
│     (ranked, durable) │     (default body; scrolls)     │  R3a MONEY (5 numbers + flag)  │
│  R1a decisions pinned │     run | phase n/t | lifecycle  │  R3b HEALTH (workers+projections)│
│  R1b failures/risks   │     changed-at | cost provenance │  R3c COMPOSITION (counts)      │
│  R1c advisory/process │     attention | decision flag    │                                │
├──────────────────────┴────────────────────────────────┴───────────────────────────────┤
│ R4  SELECTION DOCK  (hidden at rest; opens on a run/item selection without losing R2)  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

- **At rest** (no selection) R0–R3 are all visible. Nothing in §4 requires R4.
- **On selection** R4 opens as a docked inspector (right/bottom) while R1–R3 remain in place; the
  roster is never hidden by a modal (`[P]`; r6c IA1/IA2).
- **Navigation** = switching a route/board/lens, opening the System sheet, or any modal. The
  resting answers in §4 require none of it. Opening R4 is *drill-down*, not glance.

The region ids (`R0`…`R4`) are labels for this document and the acceptance checks; they map to the
current portal surfaces in §9.

---

## 2. Region contents (what each region must render at rest)

### R0 — Scope / truth bar (persistent qualifier)

One line, fixed height, never scrolls away. Five separately named states (never one health number):

| Slot | Content | Failure it prevents |
|---|---|---|
| scope | repository; active worktree/campaign scope | acting on the wrong scope |
| `conn` | browser/SSE connection state | false "live" while disconnected |
| `ctrl` | control-plane read state (`control-status/v1` reachable) | acting on a stale/absent control db |
| `epoch` | control epoch + its age | not knowing the current-state watermark |
| `degraded` | compact count of degraded dependencies (workers, projections, settlement) | green board over a stale subsystem |

`[M]` (r0 M2, M3, A1, A10; control packet `control_epoch`/`degraded`).

### R1 — Attention inbox (the operator's work queue)

A durable, ranked, deduplicated list; not a decorative strip (`[P]`; r6c IA4, IA5). Pinned
sub-regions:

- **R1a decisions** — pending decision objects (ON-G5): target run, decision kind, current epoch,
  and a database-derived safe-action affordance.
- **R1b failures/risks** — run failures/stalls, worker/projection impact, money-risk exceptions.
- **R1c advisory/process** — supervisor flags (persistent, `[M]` ON-A5) and docs/recording process
  gaps.
  Each item carries identity, priority, first/last-seen, scope, state
  (`new|active|snoozed|resolved|stale`), authority, and action (`[P]`; direction §3.3).

### R2 — Run roster (default operational body)

A keyed, write-on-change list of live runs/cells, ranked for triage (attention first, then
running/queued, then settled) `[M]` keyed-list contract; `[P]` ranking. Every row shows:
`run_id` · spec/cell · phase `n/total` · lifecycle state · changed-at/live marker · cost provenance
(on-row) · attention state · decision flag. Live/change state is always visible — never behind a
filter (`[X]`; r0 M7, r6c IA1). This is where ON-G2 lives.

### R3 — Constraint rail (decisions' context, not peer boards)

Three fixed-height summaries stacked; the rail may scroll internally but is always present.

- **R3a MONEY** — five labelled numbers: retained-window spend, burn rate, worst provider-window %,
  wallet/token headroom, reserved-(unspent)-leases; exception highlighting when a window/lease is
  near its cap. This is the ON-G4 answer. It is a *context rail*, not the removed "Money board".
- **R3b HEALTH** — named dependency rows: worker health (unhealthy count + link to affected runs)
  and knowledge projections (registry/ledger/chroma/neo4j lag + last-report age). This is the
  dependency half of ON-G1 and the source of ON-G6's degraded summary.
- **R3c COMPOSITION** — grouped counts by model × condition × provider × lifecycle (ON-G7 shape).
  Performance/cost/quality is **not** here (separate lens; §5 T3).

### R4 — Selection dock (drill-down only)

Opens on a run/attention-item selection; renders the p1 evidence ladder
(identity → lifecycle → narration → measured facts → independent verification → change/commit →
cost provenance → decision → registry record) and the safe-action preview. Not required at rest.

---

## 3. Hierarchy: what is first, second, third

The hierarchy is **visual weight and reading order within one screen**, not disclosure depth
(everything in §2 is present at rest). It follows r6c's required sequence (`[P]`; r6c "Required IA").

1. **First — the qualifier and the work queue.** `R0` scope/truth + `R1` attention/decisions. The
   operator sees *whether the data is trustworthy* and *what needs them* before anything else. `R1a`
   decisions and `R1b` failures sit at the top of the left column with the strongest accent budget.
2. **Second — the fleet body.** `R2` run roster is the largest region and the default addressable
   list. It carries ON-G2 and is never displaced by a selected object.
3. **Third — the constraint rail.** `R3a` money, `R3b` health, `R3c` composition answer the
   remaining glance questions as compact context. They are third by weight, but present.

On selection, `R4` takes the second visual band and `R3` compresses to a one-line constraint
summary inside the inspector; `R2` remains.

**Region budget (the anti-crowding rule).** `R1` and `R3` are fixed-height and exception-first:
they show exceptions + headline numbers, never full detail. `R2` is the only region that scrolls by
default. Any content that does not fit a summary region is by definition drill-down (R4) or lens
(§6), not glance.

---

## 4. Glance mapping: every `ON-G*` → the exact resting region

Every row is answerable in the default viewport with **zero interaction**. "No navigation" means no
board/lens/tab/modal change; `R0` and `R1..R3` are simultaneously visible.

| Need (r1 wording) | Resting region | What is shown there (the answer) | Never the answer | Evidence |
|---|---|---|---|---|
| `ON-G1` whole system up / room connected | **R0** (`conn`, `ctrl`, `epoch`) + **R3b** (workers, projections) | four separately named states: browser connection, control-plane read, worker health, projection lag/age — each with a state token and age; `R0.degraded` counts the non-green ones | one combined health badge or score | `[M]` r0 M2/M3/A1; `[P]` separation |
| `ON-G2` running / queued / failed / live | **R2** run roster | keyed rows with phase `n/total`, lifecycle, live/changed-at marker, cost provenance, attention, decision flag; counts for totals | a hidden or filter-only live view | `[M]` r0 M7, keyed list; `[X]` r6c IA1 |
| `ON-G3` failing / stalled / at risk | **R1b** | ranked durable items with identity, first/last-seen, scope, state, and a safe action | counts or a one-line strip | `[P]` r6c IA4; `[X]` Linear/Datadog triage |
| `ON-G4` money: spend, burn, quota, wallet, leases | **R3a** | the five labelled numbers + a money-risk exception marker when a window/lease nears its cap | a peer Money board the operator must open | `[M]` r0 M1; `[P]` five-number composition |
| `ON-G5` does anything need a decision from me | **R1a** (decision objects) + **R2** decision flag | target run, decision kind, epoch, evidence-authority, and a database-derived safe-action affordance | a count of pending approvals | `[M]` packet `awaiting_approvals`/`promotable_runs`; `[X]` r6c IA9 |
| `ON-G6` fresh / trustworthy | **R0.degraded** + per-value chips in **R2/R3a/R3b** | a global degraded summary plus source + observation-time chips on every consequential value; explicit stale markers | a single global age footer | `[M]` r0 M2/A10; `[P]` per-value truth |
| `ON-G7` shape of the fleet (by model / condition / provider) | **R3c** | grouped counts across model × condition × provider × lifecycle | pushing live triage below charts; performance graphs | `[P]` r6c IA14; `[X]` r1 need |

**Simultaneity assertion (the IA1 test).** A screenshot of the default viewport must contain all
seven rows' regions at once, with none hidden behind a peer-board switch. This is the mechanical
disproof of the r5 layout.

---

## 5. Tradeoffs where "at rest" meets crowding, and the chosen resolution

The contract is honest only if the forcing cases are named. These are the four known tensions and the
resolution each takes.

### T1 — Seven answers in one viewport is dense

**Tension:** `R0` + three rail summaries + the inbox + the roster compete for one screen; a naive
layout either crowds the roster or pushes the rail below the fold.

**Resolution `[P]`:** a fixed region budget with **exception-first, count-first** representations.
`R1`/`R3` are fixed-height chips (no embedded tables or charts); `R2` is the sole default scrolling
region. When vertical space is insufficient at a given viewport, the rail does **not** move to
another route: it collapses to a single-line constraint ticker in place, and the full rail renders
directly beneath the roster on the same screen (scroll, not navigate). AC-1/AC-2 verify this.

### T2 — `ON-G4` "spend, burn, quota, wallet, leases" vs a compact rail

**Tension:** the full ledger (per-window usage, wallet history, lease-by-lease reconciliation) is
far too much for a resting summary.

**Resolution `[P]`:** at rest, `ON-G4` is answered by the **five headline numbers plus the
exception**, which is the operator's actual question ("is money blocking me?"). The full ledger and
per-lease settlement are the Money **lens** (deliberate comparison, §6) and the run's cost rung in
`R4`. This is an explicit narrowing: the resting answer is *state + exception*, not the ledger. It
is recorded here rather than left implicit.

### T3 — `ON-G7` shape vs performance (r6c IA14)

**Tension:** "shape of the fleet" and "cost/quality comparison" have different denominators and
freshness, and a performance chart at rest would push live triage down.

**Resolution `[P]`:** `R3c` answers `ON-G7` with **composition/status counts** only (model,
condition, provider, lifecycle). Cost/quality/latency **performance** is a separate secondary lens
with a named time range and sample coverage; it is not part of `ON-G7` and never outranks `R1`/`R2`.
This also avoids a thin small-multiples default (`[P]`; p0 repair).

### T4 — Mobile cannot be the desktop wall

**Tension:** a phone cannot show seven regions side by side without turning the first screen into
navigation (r6c IA16).

**Resolution `[P]`:** mobile is **triage/inspection mode**. The resting single column answers
`ON-G1..G6` at rest (R0 bar; R1 inbox; R2 recently-changed + attention runs; money/health/composition
as compact chip rows). **`ON-G7` is an explicit secondary view on mobile** — a documented narrowing
of the glance contract for the narrow mode only; desktop answers all seven. This tradeoff is
accepted because the mobile operator's first task is triage, not fleet comparison (r6b D11). AC-9
verifies the mobile first screen and the deliberate omission.

### T5 — Very large fleets (hundreds of runs)

**Tension:** the roster cannot render every run at rest.

**Resolution `[P]`:** the `ON-G2` answer at rest is **counts + attention-ranked rows + changed-since
rows**. The full roster scrolls within R2. "What is running/queued/failed" is answered by the counts
and the visible exceptions for any fleet size; the operator never needs to open a board to know the
totals or to see what changed.

---

## 6. Drill-down paths (selection → evidence; `ON-D1..D7`)

Drill-down is one selection from the roster or inbox into `R4`; the roster and summaries remain
(`[P]`; r6c IA2, IA10). The navigation contract holds: each object has a type + stable key; selection
survives live reconciliation and compatible lens changes; scope/filters/sort/time-range/scroll/
transcript-query/follow-pause persist; incompatible scope changes confirm; disappeared/stale/denied
states keep identity; closing restores focus to the origin; exactly one event stream is open `[M]`.

| Need | Path |
|---|---|
| `ON-D1` one run, step by step live | select R2 row → R4 evidence ladder → attempt → transcript/tool events (one live stream, follow/pause) |
| `ON-D2` why flagged / safe action | select R1b item or R2 row → R4 decision/flag object → safe-action preview (target, epoch, scope, budget, reversibility, receipt) |
| `ON-D3` design draft/validation | Sessions object type (roster/search) → R4 design-session inspector |
| `ON-D4` canonical explanation | R4 → registry record link → canonical-lineage view (distinct from the runtime trace) |
| `ON-D5` route + cost/quality | R4 → routing recommendation inputs + evidence, beside the run context |
| `ON-D6` cost by step/model/cell | R4 cost/lease provenance rung; aggregate in the Money lens |
| `ON-D7` background Claude session | Sessions object type (roster/search) → R4 Claude-session inspector with owned actions |

Design sessions, background Claude sessions, supervisor flags, routing, registry, recording and queue
controls all keep explicit entry paths and global-search classes (`[P]`; r6c IA12).

---

## 7. Alert paths (attention lifecycle; `ON-A1..A6`)

Disclosure and attention are orthogonal (`[P]`; r6c IA5):

```text
Disclosure:  roster -> selected run -> evidence detail
Attention:   observation -> state transition -> attention item -> resolution
```

A transition creates or updates exactly one durable `R1` item; a **single polite live region**
announces transitions only, deduplicated. Ordinary changing metrics are readable but not announced
(`[M]`; r0 M9). In-room-only delivery is stated honestly: impossible to miss **while the room is
foregrounded**, with durable unseen history; no "interrupt" promise (`[P]`; r6c IA6).

| Need | Detection → `R1` item | Item opens |
|---|---|---|
| `ON-A1` run failed/timed out | lifecycle transition → **failure** item | R4 run evidence ladder |
| `ON-A2` worker/projection unhealthy | dependency state → **impact** item listing affected runs | R3b detail / affected runs |
| `ON-A3` spend/quota threshold | window/lease threshold → **money-risk** item with window/headroom/reset | R3a / run cost rung |
| `ON-A4` controller decision pending | packet `awaiting_approvals`/`promotable_runs` → **decision** item | R4 decision object + safe action |
| `ON-A5` supervisor flag raised/changed | flag event → **advisory** row (persistent Flags view retained) | R4 flag detail |
| `ON-A6` room data stale/disconnected | freshness floor crossed → **degraded** state in R0 + local stale marker | R3b dependency |

---

## 8. Truth placement (r6c IA7)

Global: scope, `conn`, `ctrl`, `epoch`, `degraded` (R0) and nothing else. Every consequential value
in R2/R3/R4 carries its own **source + observation-time/age** chip; truncation/partiality, revision/
epoch, and measured/estimated/unknown/unmeasured semantics attach where they apply. Green never
renders for a stale or unmeasured subsystem (`[M]`; r0 M2). This is what lets `ON-G6` be answered at
rest without one undifferentiated footer.

---

## 9. Migration map from the current portal (r0 panels → regions)

Every existing surface receives an explicit home; none is deleted silently (`[P]`; r6c IA12/IA15).

| Current surface (r0) | Resting region | Notes |
|---|---|---|
| command rail mirrors (`index.html` rail) | R0 (scope/truth) | split into named states; mirrors become labels, not a live region (M9) |
| Fleet grid + counts + Live now (`board-fleet`) | R2 (merged) | one keyed roster; live always visible (M7) |
| Flags board (`board-flags`) | R1c + persistent view | advisory items; flags remain a durable destination (ON-A5) |
| Status board / spend-burn (`board-status`) | R3a | headline numbers; full ledger → Money lens (M1) |
| System ▸ subscription usage + registry | R3a + Money/Registry lenses | quota/wallet/leases surfaced at rest (M1); registry becomes evidence destination (M4) |
| Routing board (`board-routing`) | R4 (run context) + composition lens | inputs/evidence beside the run (ON-D5) |
| Sessions / design / Claude | R2 object types + R4 inspectors | typed objects + search (ON-D3/D7) |
| docs health (Fleet inline) | R1c process gap | one owner; warranted proposal becomes a decision (M5, IA15) |
| projection health (unrendered `/api/projections`) | R3b | rendered; global degraded summary in R0 (M2) |
| control packet (absent) | R0 + R1a + R2 | the authoritative current-state projection (M3, IA3) |
| recording audit/sweep | R1c process health | missing record becomes an item (M12) |
| queue reinterleave (route, no UI) | R2 action + R4 preview | target/order preview + receipt (M11) |
| `architecture.svg` (orphaned) | out of resting screen | live+scoped inspector or System/help link (A7, r6b D7) |

---

## 10. Acceptance checks (reviewer-runnable against screenshots)

Each check names the capture, the inspection, and the pass condition. "Region" uses §1 ids. A
reviewer should be able to run these without reading code, from screenshots plus a DOM overlay dump.

| # | Capture | Inspect | Pass condition |
|---|---|---|---|
| AC-1 | Desktop 1440×900, default state, no interaction | presence of R0, R1 (a/b/c), R2, R3 (a/b/c) | all regions visible simultaneously; none behind a tab/lens/modal |
| AC-2 | Same capture | ON-G1..G7 mapping | each of the seven answers is readable in the capture per §4; no click required |
| AC-3 | Same capture | R0 + R3b slots | separately named states for browser connection, control-plane read, worker health, projection lag/age, control `epoch`, and a `degraded` count; zero combined health scores |
| AC-4 | Same capture | R2 rows | phase `n/total`, lifecycle token, changed-at/live marker, cost-provenance chip, decision flag present on each visible row |
| AC-5 | Same capture | R3a | five labelled money numbers present; at least one exception marker when a threshold fixture is loaded |
| AC-6 | Same capture | R3c | grouped counts include **provider** in addition to model/condition/lifecycle |
| AC-7 | Same capture | provenance | every consequential headline value has a source+age chip; a stale fixture renders non-green |
| AC-8 | After selecting a R1b failure | R4 + R2 | roster still visible; evidence ladder shows separate narration / measured / verification / decision classes; focus returns to origin on close |
| AC-9 | Simulated poll while a run is selected | selection + scroll + query | selection persists, follow/pause and query persist, only one event stream open, no focus loss |
| AC-10 | Transition fixture (a run fails) | R1 + live region | exactly one new/updated inbox item; one polite transition announcement; a no-op poll adds no announcement |
| AC-11 | Mobile 390×844, default | first column | R0 + R1 + recently-changed/attention rows at rest answer ON-G1..G6; **ON-G7 absent by design** (T4); no navigation needed |
| AC-12 | Narrow viewport (e.g. 1024 px) | R3 | rail collapses in place to a ticker or renders beneath the roster **on the same route**; no lens switch required (T1) |
| AC-13 | Large-fleet fixture (≥200 runs) | R2 | counts + attention-ranked + changed-since rows visible at rest; full list scrolls in place (T5) |
| AC-14 | Cross-check | R3a/R3b/R1a vs R4 for the same run/epoch | displayed numbers match the inspector's at the same control epoch (one current-state authority) |
| AC-15 | DOM overlay dump | all ON-G answers | every §4 region anchor exists in the DOM and is not `hidden`/`aria-hidden` at rest |

---

## 11. Open items

- **Implementation.** This document is the IA contract the facelift executes; the code change is a
  later phase.
- **Mobile ON-G7 narrowing** (T4) is an accepted, documented deviation; if a future review wants it
  at rest on mobile, it must show how it fits the first column without displacing attention.
- **Threshold fixtures** for AC-5 require the settlement/usage surfaces to expose a near-cap state in
  a test harness; currently the numbers exist but no fixture is committed.
- **Provider composition** (AC-6) depends on the control packet / ledger carrying provider per run;
  if a run lacks it, the count must show `unknown`, never be omitted.
