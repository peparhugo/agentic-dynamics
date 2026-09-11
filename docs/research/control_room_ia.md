---
status: accepted
---

# Control Room — the one resting screen: the canonical glance contract (campaign `control_room_research_repair2`, phase `q2_glance_proof`)

**Date:** 2026-09-11
**Question answered:** can ONE resting screen answer the operator glance needs `ON-G1..G7`
(`docs/research/control_room_questions.md` §4.1) with **no interaction**, and where exactly is
each answer on that screen?
**Inputs:** the measured portal audit `docs/research/control_room_audit.md` (r0 panels/feeds),
the operator-needs contract `control_room_questions.md` (r1), the direction
`control_room_direction.md` (p1/q1), the **q0 quoted-evidence** taxonomy/catalogs/skills, and the
two IA adversary passes — p5 (`docs/reviews/control_room_repair_ia.md`, findings IA1–IA11) and r6c
(`docs/reviews/control_room_research_ia.md`, IA1–IA16).
**This revision's job (q2).** The p5 adversary found that r1, p1, and p2 promised *different*
glance contracts (IA1), that required answers could scroll or move below the fold (IA2), that
`ON-G4`/`ON-G7` were not guaranteed at rest (IA3/IA4), and that the acceptance suite tested DOM
presence rather than visibility (IA8). This document now holds **one canonical contract for both
breakpoints**, a **pixel budget whose sums fit both viewports**, and a **Playwright-implementable
acceptance-check section** (§10).

**Canonical contract (the single source of truth).** At the two claimed resting breakpoints —
**1440×900 desktop and 390×844 mobile** — the resting screen shows **all seven `ON-G1..G7`
answers above the fold with no page scroll, no region scroll, and no navigation**. Narrow desktop
down to 1024×768 uses the same region set and the same seven answers; only the column arrangement
changes. There is no mobile omission and no below-fold fallback. Any document that says otherwise is
superseded by §4.

**Claim discipline.** `[M]` measured (r0/the repository), `[X]` external exemplar, `[P]` local
design policy. "At rest" is exact: **visible in the initial viewport with zero interaction** — no
tab, lens, board, modal, hover, or filter, and no scrolling of the page or of any required region
(§10). Scrolling is permitted only inside the roster `R2` for rows beyond the bounded visible set.

---

## 1. The resting screen, defined

The resting screen is **one layout**, not a set of destinations. Desktop is a persistent qualifier
bar over a **three-column body**; mobile is the same regions stacked in one column. Nothing is
hidden behind navigation, and no required answer is below the fold.

```text
DESKTOP 1440x900                                          MOBILE 390x844
┌───────────────────────────────────────────────┐        ┌──────────────────────┐
│ R0  SCOPE / TRUTH BAR (full width, 56px)       │        │ R0 scope/truth 44px  │
├──────────────┬──────────────────┬─────────────┤        ├──────────────────────┤
│ R1 ATTENTION │ R2 RUN ROSTER    │ R3 RAIL     │        │ R1 attention 176px   │
│  (ranked)    │  (only scroller) │  R3a MONEY  │        ├──────────────────────┤
│  R1a money   │  run | phase    │  R3b HEALTH │        │ R2 roster 196px      │
│  R1b failure │  lifecycle      │  R3c COMPO  │        ├──────────────────────┤
│  R1c advisory│  decision token │             │        │ R3a MONEY 92px       │
├──────────────┴──────────────────┴─────────────┤        │ R3b HEALTH 68px      │
│ R4 SELECTION DOCK (hidden at rest)             │        │ R3c COMPOSITION 60px │
└───────────────────────────────────────────────┘        └──────────────────────┘
```

- **At rest** (no selection) `R0`, `R1` (a/b/c), `R2`, and `R3` (a/b/c) are all visible in the
  initial viewport at both breakpoints (§4, §3 budget).
- **On selection** `R4` opens as a docked inspector while `R1`–`R3` remain in place; the roster is
  never hidden by a modal (`[P]`; r6c IA1/IA2). The selected-state arrangement is fixed in §3.2.
- **Navigation** = switching a route/board/lens, opening the System sheet, or any modal. The
  resting answers in §4 require none of it. Opening `R4` is *drill-down*, not glance.

**Selector contract (`[P]`).** Every region and every answer carries a stable data attribute so the
render gate can find it without brittle CSS: regions are `[data-region="R0"|"R1"|"R1a"|"R1b"|"R1c"|
"R2"|"R3a"|"R3b"|"R3c"]`, each need is `[data-answer="ON-G1".."ON-G7"]`, and required values use
`[data-field="money.spend"|"money.burn"|"money.quota"|"money.wallet"|"money.leases"|
"health.workers"|"health.projections"|"composition.rollup"]`. The gate contract is §10; the
implementation is free to choose the DOM tree beneath those anchors.

---

## 2. Region contents (what each region must render at rest)

### R0 — Scope / truth bar (persistent qualifier)

`[data-region="R0"]`, carrying the `ON-G6` answer anchor (`[data-answer="ON-G6"]`). One line, fixed
height, never scrolls away. Five separately named states (never one health number):

| Slot | Content | Failure it prevents |
|---|---|---|
| scope | repository; active worktree/campaign scope | acting on the wrong scope |
| `conn` | browser/SSE connection state | false "live" while disconnected |
| `ctrl` | control-plane read state (`control-status/v1` reachable) | acting on a stale/absent control db |
| `epoch` | control epoch + its age | not knowing the current-state watermark |
| `degraded` | compact count of degraded dependencies (workers, projections, settlement) | green board over a stale subsystem |

`[M]` (r0 M2, M3, A1, A10; control packet `control_epoch`/`degraded`).

### R1 — Attention inbox (the operator's work queue)

A durable, ranked, deduplicated list; not a decorative strip (`[P]`; r6c IA4, IA5). It is one
**globally ordered** queue, not fixed categories: every item is ranked by *severity × actionability*,
with capacity reserved for the highest severity class so a saturated inbox cannot bury a new
critical failure (p5 IA6). The `R1a/b/c` labels are item *classes*, not fixed positions:

- **R1a decisions** (`[data-answer="ON-G5"]`) — pending decision objects: target run, decision kind,
  current epoch, evidence authority, and a compact **eligibility token**
  (`observe|inspect|approve|promote|cancel|retire|none`). This is the canonical at-rest `ON-G5`
  answer; the `R2` decision token is a navigational mirror, not a second writer (p5 IA5/IA9).
- **R1b failures/risks** (`[data-answer="ON-G3"]`) — run failures/stalls, worker/projection impact,
  money-risk exceptions.
- **R1c advisory/process** — supervisor flags (persistent, `[M]` ON-A5) and docs/recording process
  gaps.

Each item carries identity, severity, actionability, first/last-seen, scope, state
(`new|active|snoozed|resolved|stale`), authority, action, and source+age (`[P]`; direction §3.3).
Visible capacity: **≥ 3 ranked items at mobile, ≥ 5 at desktop**, with the top-severity slot always
rendered even if lower-ranked items are clipped (`[P]`; p5 IA6).

### R2 — Run roster (default operational body)

`[data-region="R2"]`, carrying the `ON-G2` answer anchor (`[data-answer="ON-G2"]`) and the row
selector `[data-run-id]`. A keyed, write-on-change list of live runs/cells, ranked for triage (attention first, then
running/queued, then settled) `[M]` keyed-list contract; `[P]` ranking. Every row shows:
agent/session identity (session id · worktree/host target · current command/tool · provider×model ·
attempt, per direction §4.1 Move 1) · spec/cell · phase `n/total` · lifecycle state · changed-at/live
marker · cost provenance (on-row) · attention state · **decision-eligibility token**. Live/change
state is always visible — never behind a filter (`[X]`; r0 M7, r6c IA1). This is where `ON-G2` lives
and where the row-level `ON-G5` mirror points back to `R1a`. `R2` is the **only** region allowed to
scroll, and only for rows beyond the bounded visible set (`[P]`; §3.1).

### R3 — Constraint rail (decisions' context, not peer boards)

Three **fixed-height, non-scrolling** summaries stacked. Together they are the `ON-G4` (`R3a`),
`ON-G1` dependency half (`R3b`), and `ON-G7` (`R3c`) answers; none may require scrolling or move
below the fold (p5 IA2/IA3/IA4).

- **R3a MONEY** (`[data-answer="ON-G4"]`) — exactly five labelled values, each with
  `[data-field]`: retained-window spend, burn rate, worst provider-window %, wallet/token headroom,
  and reserved-(unspent)-leases; a money-risk exception marker when a window/lease nears its cap.
  This is the full `ON-G4` answer, not a risk exception alone (p5 IA3). It is a *context rail*, not
  the removed "Money board".
- **R3b HEALTH** (`[data-answer="ON-G1"]`) — named dependency rows: worker health (unhealthy count +
  affected-run link) and knowledge projections (registry/ledger/chroma/neo4j lag + last-report age),
  sharing one observation epoch/age with `R0` (p5 IA5). This is the dependency half of `ON-G1` and
  the source of `ON-G6`'s degraded summary.
- **R3c COMPOSITION** (`[data-answer="ON-G7"]`) — a **bounded** rollup of model × condition ×
  provider × lifecycle: four marginals, each capped (e.g. top groups plus explicit `other` and
  `unknown`), never an unbounded cross-product and never a chart (p5 IA4). Performance/cost/quality
  is **not** here (separate lens; §5 T3).

### R4 — Selection dock (drill-down only)

Opens on a run/attention-item selection; renders the p1 evidence ladder
(identity → lifecycle → narration → measured facts → independent verification → change/commit →
cost provenance → decision → registry record) and the safe-action preview. Not required at rest.

---

## 3. Hierarchy, pixel budget, and selected state

### 3.1 Hierarchy and the anti-crowding rule

The hierarchy is **visual weight and reading order within one screen**, not disclosure depth
(everything in §2 is present at rest). It follows r6c's required sequence (`[P]`; r6c "Required IA").

1. **First — the qualifier and the work queue.** `R0` scope/truth + `R1` attention. The operator sees
   *whether the data is trustworthy* and *what needs them* before anything else. `R1` is globally
   severity-ranked (§2), not category-pinned.
2. **Second — the fleet body.** `R2` run roster is the largest region and the default addressable
   list. It carries `ON-G2` and is never displaced by a selected object.
3. **Third — the constraint rail.** `R3a` money, `R3b` health, `R3c` composition answer the remaining
   glance questions as compact context. They are third by weight, but present and **non-scrolling**.

**Anti-crowding rule.** `R1`, `R3a`, `R3b`, `R3c` are fixed-height and summary-first: they show
exceptions plus headline values, never full detail. `R2` is the **only** region that may scroll, and
only for rows beyond its bounded visible set. Any content that does not fit a summary region is by
definition drill-down (`R4`) or lens (§6), not glance. No required answer may live in an internal
scroll container (p5 IA2/IA7).

### 3.2 Pixel budget (sums fit both viewports)

Max heights in CSS pixels, excluding browser chrome. The mobile column is the sum of every region
because the regions stack; the desktop column places `R1`/`R2`/`R3` side by side, so its vertical
sum is `R0 + max(R1, R2, R3)`.

| Region | Desktop max-height | Mobile max-height | Budgeted content |
|---|---:|---:|---|
| `R0` scope / truth | 56 | 44 | 5 named state tokens (`scope`, `conn`, `ctrl`, `epoch`, `degraded`) |
| `R1` attention inbox | 800 (fills body) | 176 | ≥5 ranked items desktop / ≥3 mobile, top-severity slot reserved |
| `R2` run roster | 800 (fills body; internal scroll only) | 196 | counts row + ranked identity rows (≥5 desktop / ≥3 mobile visible) |
| `R3a` money | 220 | 92 | 5 labelled values + exception marker (2-line grid at mobile) |
| `R3b` health | 180 | 68 | worker state + 4 projection rows (one shared epoch/age) |
| `R3c` composition | 140 | 60 | 4 capped marginals (`other`/`unknown` explicit) |
| `R4` selection dock | 0 at rest | 0 at rest | hidden until selection; then bottom dock (§3.3) |
| Inter-region gaps | 12 (bar → body) | 24 (3 × 8 stack) | plus 2 × 8 internal `R3` gaps at each breakpoint |
| **Vertical sum** | **56 + 12 + 800 = 868 ≤ 900** | **44+176+196+(92+68+60+16)+24 = 676 ≤ 844** | headroom desktop 32 px, mobile 168 px |

The chosen budgets leave explicit headroom at both breakpoints; the sums are the *maximum* the regions
may occupy and are the numbers the render gate asserts (§10). If a future change raises any budget,
the sum must still satisfy `desktop ≤ 900` and `mobile ≤ 844` or the contract is broken.

### 3.3 Selected state (one arrangement per breakpoint)

Selection is drill-down, not a new resting screen. The fixed arrangement is:

- **Desktop:** `R4` opens as a **bottom dock** (≈ 320 px) while `R0`, `R1`, `R2`, `R3` stay in their
  resting positions; the body above the dock re-flow-layouts to the reduced height, and no required
  region scrolls. `R2` keeps its internal row scroll.
- **Mobile:** `R4` pushes over `R2` as a full-height inspector with an explicit Back; `R0` and `R1`
  remain at the top and the `R3` answers remain reachable in the same viewport, so the content of the
  resting answer is never destroyed.

Either way, every region promised to remain visible is tested in §10 (p5 IA10), and the at-rest
`ON-G4`/`ON-G7` answers do not disappear while an object is selected.

---

## 4. The canonical glance contract: one `ON-G1..G7` list

This is the single authoritative contract (p5 IA1). It supersedes every earlier mapping in r1/p1/p2:
at **both** 1440×900 and 390×844, each need is answered by the listed region, with the listed
visible content, inside the initial viewport. "Above fold" means the region's bounding box is fully
inside the viewport (`top ≥ 0` and `bottom ≤ viewport height`), the page does not scroll, and the
region's own `scrollHeight ≤ clientHeight` (no internal scroll). The mechanical check is §10.

| Need (authoritative r1 wording) | Canonical region | Visible content (the answer) | Above fold @1440×900 | Above fold @390×844 | Never the answer | Evidence |
|---|---|---|---|---|---|---|
| `ON-G1` is the whole system up / room connected? | **`R0` + `R3b`** | four independently named states: browser `conn`, control-plane `ctrl`, worker health, projection lag+age; `R0.degraded` counts the non-green ones; `R0` and `R3b` share one epoch/age | yes — `R0` top + `R3b` in rail, both boxes inside 900; no page scroll | yes — `R0` top + `R3b` stacked, both inside 844; no page scroll | one combined health badge or score | `[M]` r0 M2/M3/A1; `[P]` separation |
| `ON-G2` what is running / queued / failed right now, and what is live? | **`R2`** | keyed rows with session identity, phase `n/total`, lifecycle, live/changed-at, cost provenance, attention, decision mirror; a counts row for totals | yes — roster fills the body; `R2` is the only scroller (rows only) | yes — roster stacked between `R1` and `R3a`; bounded rows + counts | a hidden or filter-only live view | `[M]` r0 M7 keyed list; `[X]` r6c IA1 |
| `ON-G3` is anything failing, stalled, or at risk? | **`R1b`** | globally severity-ranked durable items with identity, first/last-seen, scope, state, and a safe action; top-severity slot reserved | yes — `R1` at top of the left column, inside 900 | yes — `R1` directly under `R0`, inside 844 | a count or a one-line strip | `[P]` r6c IA4; `[X]` Linear/Datadog triage |
| `ON-G4` what is money doing — spend, burn, provider quota, wallet, reserved leases? | **`R3a`** | **all five** labelled values (`money.spend`, `money.burn`, `money.quota`, `money.wallet`, `money.leases`) + a money-risk exception marker near a cap | yes — `R3a` fixed 220 px in the rail, inside 900; no rail scroll | yes — `R3a` fixed 92 px, five values in a 2-line grid, inside 844 | a Money board the operator must open; a risk exception alone | `[M]` r0 M1; `[P]` five-value composition |
| `ON-G5` does anything need a decision from me? | **`R1a`** (canonical) + `R2` mirror | decision objects: target run, decision kind, epoch, evidence authority, compact eligibility token; the `R2` flag is a mirror only | yes — `R1a` ranked into `R1`, inside 900 | yes — `R1a` ranked into `R1`, inside 844 | a count of pending approvals | `[M]` packet `awaiting_approvals`/`promotable_runs`; `[P]` eligibility tokens (p5 IA9) |
| `ON-G6` is what I am looking at fresh and trustworthy? | **`R0.degraded`** + per-value chips in `R2/R3a/R3b` | global degraded summary + source+observation-time chips on every consequential value; explicit stale/partial/unknown markers; one shared epoch for split summaries | yes — `R0` top, chips inline, inside 900 | yes — `R0` top, chips inline, inside 844 | a single global age footer | `[M]` r0 M2/A10; `[P]` per-value truth (p5 IA5/IA11) |
| `ON-G7` what is the shape of the fleet (by model / condition / provider)? | **`R3c`** | **bounded** marginals across model × condition × provider × lifecycle (four capped groups + explicit `other`/`unknown`), text counts only | yes — `R3c` fixed 140 px in the rail, inside 900; no rail scroll | yes — `R3c` fixed 60 px, inside 844 | an unbounded cross-product; a chart; a fleet view the operator must open | `[P]` r6c IA14; `[X]` r1 need (p5 IA4) |

**Simultaneity assertion (the IA1 test).** A screenshot of the default viewport at **both**
1440×900 and 390×844 must contain all seven answers' regions at once — none hidden behind a
peer-board switch, a lens, a modal, an internal scroll, or the fold. This is the mechanical disproof
of the r5 layout and the p5 IA1/IA2 defects.

---

## 5. Tradeoffs where "at rest" meets crowding, and the chosen resolution

The contract is honest only if the forcing cases are named. These are the known tensions and the
resolution each takes; every resolution preserves the §4 canonical contract.

### T1 — Seven answers in one viewport is dense

**Tension:** `R0` + three rail summaries + the inbox + the roster compete for one screen; a naive
layout either crowds the roster or pushes the rail below the fold.

**Resolution `[P]`:** the §3.2 pixel budget with **exception-first, count-first** representations.
`R1`/`R3` are fixed-height summaries (no embedded tables or charts); `R2` is the sole scrolling
region. There is **no ticker fallback and no below-fold placement**: the budgets were chosen so the
regions fit 1440×900 and 390×844 without scrolling. If a future change cannot fit, the offending
content is drill-down/lens, not a region that moves below the fold.

### T2 — `ON-G4` "spend, burn, quota, wallet, leases" vs a compact rail

**Tension:** the full ledger (per-window usage, wallet history, lease-by-lease reconciliation) is
far too much for a resting summary.

**Resolution `[P]`:** at rest, `ON-G4` is answered by **all five labelled values plus the exception
marker** — never a subset and never a risk exception alone (p5 IA3). The full ledger and per-lease
settlement are the Money **lens** (§6) and the run's cost rung in `R4`. This is a narrowing of
*detail*, not of the `ON-G4` answer: the five-value row is the resting answer.

### T3 — `ON-G7` shape vs performance (r6c IA14)

**Tension:** "shape of the fleet" and "cost/quality comparison" have different denominators and
freshness, and a performance chart at rest would push live triage down.

**Resolution `[P]`:** `R3c` answers `ON-G7` with **bounded composition/status counts** only (model,
condition, provider, lifecycle; four capped marginals with explicit `other`/`unknown`). Cost/quality/
latency **performance** is a separate secondary lens with a named time range and sample coverage; it
is not part of `ON-G7` and never outranks `R1`/`R2`. This also avoids a thin small-multiples default
(`[P]`; q0 crosswalk).

### T4 — Mobile is the same seven answers, stacked

**Tension:** a phone cannot show seven regions side by side, and the earlier draft resolved that by
deferring `ON-G7` — which broke the single canonical contract (p5 IA1/IA4).

**Resolution `[P]`:** mobile keeps the **same seven answers** in a single stacked column: `R0` bar;
`R1` ranked inbox; `R2` bounded roster; `R3a` money (five values, two-line grid); `R3b` health;
`R3c` bounded composition. The §3.2 mobile budget (676 ≤ 844) proves they fit above the fold. There
is **no mobile omission**; the only mobile difference is arrangement and bounded row counts (§10 G-8/G-9).

### T5 — Very large fleets (hundreds of runs)

**Tension:** the roster cannot render every run at rest.

**Resolution `[P]`:** the `ON-G2` answer at rest is **counts + attention-ranked rows + changed-since
rows**. The full roster scrolls within `R2`. "What is running/queued/failed" is answered by the counts
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

## 8. Truth placement and the per-region provenance inventory (r6c IA7; p5 IA11)

Global: scope, `conn`, `ctrl`, `epoch`, `degraded` (`R0`) and nothing else. Every consequential value
in `R2/R3/R4` carries its own **source + observation-time/age** chip; truncation/partiality, revision/
epoch, and measured/estimated/unknown/unmeasured semantics attach where they apply. Green never
renders for a stale or unmeasured subsystem (`[M]`; r0 M2). This is what lets `ON-G6` be answered at
rest without one undifferentiated footer.

The following inventory is the exact set of provenance-bearing fields the geometry checks (§10 G-4,
contrast) and the blind check B-6 cover; any value not listed is not "consequential" at rest and may
omit the chip (p5 IA11):

| Region | Provenance-bearing fields | Required chip attributes |
|---|---|---|
| `R0` | `scope`, `conn`, `ctrl`, `epoch`, `degraded` | source + age; `epoch` carries revision; `degraded` carries the non-green count |
| `R1` | every inbox item (decision, failure/risk, advisory) | authority class (`measured`/`computed`/`heuristic`/`policy`/`unknown`) + first/last-seen |
| `R2` | per-row cost provenance; row `changed-at` | `cost_source` (`metered`/`estimated`/`unknown`/`reconciled`) + age; every visible row |
| `R3a` | all five `money.*` values | source + age; `unknown` renders as explicit `unknown`, never `0` |
| `R3b` | worker state; each projection row | source + last-report age; shared observation epoch with `R0` |
| `R3c` | composition marginals | source + age; `other`/`unknown` rendered explicitly |
| `R4` | the full evidence ladder | per-rung evidence class + source + age (drill-down; not tested at rest) |

For any need whose answer is split across regions (`ON-G1`, `ON-G6`), the regions share **one**
observation epoch/age so a reviewer never has to join two freshnesses (p5 IA5).

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

## 10. Acceptance checks — implementable by the Playwright render gate

The acceptance suite this section defines is the contract `verify_control_room_rendering.py` (the
facelift render gate, patterned on the website's `verify_svg_rendering.py`) must implement. It is
split into four classes so a screenshot is never asked to prove something only the browser or the
network can observe (p5 IA8): **G geometry**, **B blind comprehension**, **A browser/accessibility**,
and **E event/network/state**.

### 10.1 The five geometry primitives

Every geometry assertion is built from five primitives, each of which must hold for every listed
selector at every listed viewport:

1. **Present** — `document.querySelector(sel)` is non-null, and the element and all ancestors are
   not `hidden`, `[hidden]`, `display:none`, `visibility:hidden`, or `aria-hidden="true"`.
2. **In viewport** — `const r = el.getBoundingClientRect()` satisfies `r.top >= -0.5`,
   `r.bottom <= innerHeight + 0.5`, `r.left >= -0.5`, `r.right <= innerWidth + 0.5`.
3. **Non-zero box** — `r.width > 0 && r.height > 0` (rejects collapsed or clipped-to-nothing nodes).
4. **No scroll** — `document.scrollingElement.scrollHeight <= innerHeight + 1` and
   `scrollWidth <= innerWidth + 1` (no page scroll, no horizontal overflow); for every required
   non-scrolling region, `el.scrollHeight <= el.clientHeight + 1` (no internal scroll).
5. **Contrast** — for each text node inside the region, the computed-color luminance ratio is
   ≥ 4.5:1 for normal text and ≥ 3:1 for large text (≥ 24px, or ≥ 18.66px bold), against the
   element's effective background. (An axe-core `color-contrast` pass is an acceptable substitute.)

### 10.2 Selector map

| Anchor | Selector | Meaning |
|---|---|---|
| Regions | `[data-region]` with value in `R0, R1, R1a, R1b, R1c, R2, R3a, R3b, R3c` | the §1 regions |
| Answers | `[data-answer]` with value in `ON-G1 .. ON-G7` | the canonical §4 answer anchors |
| Money | `[data-field]` with value in `money.spend, money.burn, money.quota, money.wallet, money.leases` | the five `ON-G4` values |
| Health / truth | `[data-field]` with value in `health.workers, health.projections, truth.conn, truth.ctrl, truth.epoch, truth.degraded` | `ON-G1`/`ON-G6` values |
| Composition | `[data-field="composition.rollup"]` with child `[data-marginal]` | the bounded `ON-G7` rollup |
| Row identity | `[data-region="R2"] [data-run-id]` | roster rows (bounded visible set) |

### 10.3 Geometry checks (G)

| # | Viewport | Selectors | Assertion | Threshold |
|---|---|---|---|---|
| G-1 | 1440×900, 390×844 | all `[data-region]`, all `[data-answer]` | primitives 1, 2, 3 | 0 violations |
| G-2 | both | all `[data-answer]` | primitive 4 (page) | `scrollHeight ≤ innerHeight+1`, `scrollWidth ≤ innerWidth+1` |
| G-3 | both | `R1`, `R3a`, `R3b`, `R3c` | primitive 4 (no internal scroll) | each `scrollHeight ≤ clientHeight+1` |
| G-4 | both | all text nodes in `[data-answer]` | primitive 5 (contrast) | ≥ 4.5:1 normal / ≥ 3:1 large |
| G-5 | both | computed `font-size` in `R0..R3c` | type floor | ≥ 12px mobile, ≥ 13px desktop; labels ≥ 11px |
| G-6 | both | all `[data-answer]` | non-empty answer token | `innerText.trim().length > 0` |
| G-7 | 1440×900 | `R0`, `R1`, `R2`, `R3a/b/c` | §3.2 desktop budget | `R0≤56`, `R1/R2≤800`, `R3a≤220`, `R3b≤180`, `R3c≤140`; vertical sum ≤ 900 |
| G-8 | 390×844 | `R0`, `R1`, `R2`, `R3a/b/c` | §3.2 mobile budget | `R0≤44`, `R1≤176`, `R2≤196`, `R3a≤92`, `R3b≤68`, `R3c≤60`; vertical sum ≤ 844 |
| G-9 | 390×844 | `[data-region]` | single-column arrangement | all regions share the same `left` and `width ≈ innerWidth`; no side-by-side |
| G-10 | 1440×900 | `[data-answer="ON-G4"] [data-field^="money."]` | exactly five money values, all non-empty | `count === 5` |
| G-11 | 1440×900 | `[data-answer="ON-G7"] [data-marginal]` | bounded composition | `2 ≤ count ≤ 6`, each marginal has an explicit `other`/`unknown` bucket |
| G-12 | 1024×768 (narrow desktop) | all `[data-answer]` | same seven answers present and in viewport | same as G-1/G-2 |

Mobile has **no** `ON-G7` omission: G-1 and G-11 run at 390×844 too (p5 IA4).

### 10.4 Blind-comprehension checks (B)

A human reviewer, shown only the screenshot and not this document, must state each answer within ten
seconds and point to the carrying element; a miss fails the design, not the copy (p4 recognizability
test; p5 IA8).

| # | Reviewer says | Carrying element |
|---|---|---|
| B-1 | "The room is connected / the system is up." | `R0` `truth.conn`/`truth.ctrl` + `R3b` |
| B-2 | "These are the live runs and what is queued/failed." | `R2` counts + rows |
| B-3 | "That failure needs me." | `R1b` item, top of the ranked inbox |
| B-4 | "Here is spend against the five money buckets." | `R3a` five values |
| B-5 | "That run is waiting on a decision." | `R1a` decision object / `R2` mirror |
| B-6 | "Here is whether the data is fresh." | `R0.degraded` + per-value chips |
| B-7 | "Here is the fleet's shape." | `R3c` bounded rollup |
| B-8 | The correct next action for the top item. | `R1` eligibility token / `R2` mirror |

### 10.5 Browser / accessibility automation (A) and event/state (E)

Screenshots cannot prove these; the gate runs them in the browser or over the network.

| # | Class | Check | Pass condition |
|---|---|---|---|
| A-1 | a11y | `R4` focus containment + return to origin on close | focus never escapes the dialog; returns to the opening control |
| A-2 | a11y | selected identity survives a poll | the same `data-run-id` remains selected |
| A-3 | a11y | preserved filters / query / scroll / follow-pause | each is unchanged after a live update |
| A-4 | a11y | accessibility-tree names for `R1` items and `R2` rows | non-empty accessible name, role present |
| A-5 | a11y | `hidden` deactivation | inactive surfaces are truly `hidden`, not CSS-only |
| A-6 | a11y | keyboard path: focus visible, Enter opens, Escape closes | end-to-end without a pointer |
| E-1 | state | selected SSE streams | exactly one open |
| E-2 | network | replay + de-dup | bounded replay with one `replay_complete`; no duplicate events |
| E-3 | a11y/state | announcement policy | exactly one polite announcement per transition; a no-op poll is silent |
| E-4 | state | control epoch consistency | `R3a`/`R3b`/`R1a` and `R4` agree at the same epoch |
| E-5 | state | saturated inbox | a new critical failure stays visible (top-severity slot reserved) |

### 10.6 Fixtures

`F-1` saturated inbox (critical failure injected), `F-2` ≥ 200-run fleet, `F-3` near-cap money,
`F-4` unknown provider, `F-5` stale projection, `F-6` disconnected browser. Each geometry check
runs against the default and the relevant fixture.

### 10.7 Reference gate (pseudo-code)

```python
# verify_control_room_rendering.py — geometry class, per viewport.
VIEWPORTS = {"desktop": (1440, 900), "narrow": (1024, 768), "mobile": (390, 844)}
REQUIRED = ['[data-region="R0"]', '[data-region="R1"]', '[data-region="R2"]',
            '[data-region="R3a"]', '[data-region="R3b"]', '[data-region="R3c"]'] + \
           [f'[data-answer="ON-G{i}"]' for i in range(1, 8)]

for name, (w, h) in VIEWPORTS.items():
    page.set_viewport_size({"width": w, "height": h})
    page.goto(PORTAL_URL)
    # G-2 no page scroll
    assert page.evaluate("document.scrollingElement.scrollHeight <= innerHeight + 1")
    assert page.evaluate("document.scrollingElement.scrollWidth <= innerWidth + 1")
    for sel in REQUIRED:
        el = page.query_selector(sel)
        assert el and el.is_visible(), f"{sel} missing/hidden at {name}"          # primitive 1
        box = el.bounding_box()
        assert box["width"] > 0 and box["height"] > 0, f"{sel} zero box"          # primitive 3
        assert box["y"] >= -0.5 and box["y"] + box["height"] <= h + 0.5, sel     # primitive 2
        assert box["x"] >= -0.5 and box["x"] + box["width"] <= w + 0.5, sel
        assert el.evaluate("e => e.scrollHeight <= e.clientHeight + 1"), sel     # primitive 4
        assert page.evaluate(  # primitive 5 (per text node), simplified
            "e => e.innerText.trim().length > 0", el)
    # G-10 / G-11 exactness on the required viewports
    assert len(page.query_selector_all('[data-answer="ON-G4"] [data-field^="money."]')) == 5
    marg = page.query_selector_all('[data-answer="ON-G7"] [data-marginal]')
    assert 2 <= len(marg) <= 6
```

---

## 11. Open items

- **Implementation.** This document is the IA contract the facelift executes; the code change (and
  the `[data-*]` selector contract in §10.2) is a later phase. The gate script does not exist yet;
  `verify_control_room_rendering.py` is named in the direction's acceptance criteria.
- **Canonical contract reconciled.** The earlier mobile `ON-G7` omission and the narrow-desktop
  ticker fallback are both withdrawn: §4 and T4/T1 now answer all seven needs at 1440×900 and
  390×844 with no below-fold placement, so r1, the direction, and this document agree.
- **Fixtures.** `F-1`..`F-6` (§10.6) need a test harness that can inject a near-cap window/lease, a
  stale projection, an unknown provider, and a saturated inbox; the numbers exist but the fixtures
  are not committed.
- **Contrast automation.** Primitive 5 may be satisfied by axe-core; if a bespoke checker is used it
  must resolve effective backgrounds for the status chips, which are layered on tinted rows.
- **Provider composition** (`G-11`) depends on the control packet / ledger carrying provider per
  run; if a run lacks it, the count must show `unknown`, never be omitted.
