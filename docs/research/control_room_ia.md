---
status: accepted
---

# Control Room — the one resting screen: the canonical glance contract (campaign `control_room_research_repair2`, phases `q2_glance_proof` + `q5_adversary_ia`)

**Date:** 2026-09-11
**Question answered:** can ONE resting screen answer the operator glance needs `ON-G1..G7`
(`docs/research/control_room_questions.md` §4.1) with **no interaction**, and where exactly is
each answer on that screen?
**Inputs:** the measured portal audit `docs/research/control_room_audit.md` (r0 panels/feeds),
the operator-needs contract `control_room_questions.md` (r1), the direction
`control_room_direction.md` (p1/q1), the **q0 quoted-evidence** taxonomy/catalogs/skills, and the
two IA adversary passes — p5 (`docs/reviews/control_room_repair_ia.md`, findings IA1–IA11) and r6c
(`docs/reviews/control_room_research_ia.md`, IA1–IA16).
**u3 reconciliation (this revision).** This file is reconciled with the UX-repair wave:
`docs/research/control_room_ux_foundation.md` (u0: operator, jobs `J1–J11`, principles `DP1–DP10`),
`docs/research/control_room_interaction_model.md` (u1: lifecycle, decision points, per-worker
actions, alerts, drill-down), and `experiments/research/control_room/parity_inventory.json`
(u2: every old panel/control/feed with its disposition). The glance contract (§4) and the pixel
budgets (§3.2) are **unchanged**; the reconciliation (a) names the two regions the facelift dropped
— the **per-worker event/action region** `R4b` and the **step-timing region** `R4d` — plus the
**Workforce step-timing lens** that carries the fleet aggregate, and (b) places every parity item on
a closed surface palette (`§12`–`§15`).
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
(§10). **No resting region scrolls.** Full inbox and fleet lists are drill-down lenses; their bounded
at-rest summaries never acquire an internal scrollbar.

---

## 1. The resting screen, defined

The resting screen is **one run ledger**, not a set of dashboard destinations. Desktop is a persistent
qualifier bar over a three-column body: `R2` is the visually dominant agent-session ledger, while `R1`
and `R3` are annotation gutters attached to that ledger, not peer card boards. Mobile stacks the same
ledger and gutters in one column. Nothing is hidden behind navigation, and no required answer is below
the fold.

```text
DESKTOP 1440x900                                          MOBILE 390x844
┌───────────────────────────────────────────────┐        ┌──────────────────────┐
│ R0  SYSTEM + TRUST (full width, 72px)            │        │ R0 system/trust 72px │
├──────────────┬──────────────────┬─────────────┤        ├──────────────────────┤
│ R1 ATTENTION │ R2 RUN LEDGER    │ R3 CONTEXT  │        │ R1 attention 144px   │
│  (reserved)  │  (no scroller)   │  R3a COST   │        ├──────────────────────┤
│  R1a decision│  session | phase │  R3b HEALTH │        │ R2 run ledger 284px  │
│  R1b failure │  evidence marks │  R3c COMPO  │        ├──────────────────────┤
│  R1c next    │  eligibility    │             │        │ R3a COST 92px        │
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

**Selector contract (`[P]`).** Every layout region and answer carries a stable data attribute so the
render gate can find it without brittle CSS. Valid region selectors are the explicit list
`[data-region="R0"]`, `[data-region="R1"]`, `[data-region="R2"]`, `[data-region="R3a"]`,
`[data-region="R3b"]`, `[data-region="R3c"]`; `R1a/b/c` are item classes expressed with
`[data-attention-class]`, not nested layout regions. Exactly one element exists for each explicit
answer selector `[data-answer="ON-G1"]` through `[data-answer="ON-G7"]`. Required field selectors
are enumerated in §10.2. The implementation may choose the DOM tree beneath those anchors, but may not
add a second `[data-answer]` writer for a mirror.

**Drill-down region selectors (`[P]`).** `R4` (the selection dock) is not a `data-region` layout
region and exists only after selection; its four sub-regions use a separate attribute so the resting
contract in §1/§10 is untouched: `[data-dock-region="address"]` (`R4a`),
`[data-dock-region="worker"]` (`R4b`), `[data-dock-region="evidence"]` (`R4c`), and
`[data-dock-region="timing"]` (`R4d`). The workforce aggregate lives in a deliberate lens,
`[data-lens="workforce"]`. These selectors are added to the acceptance contract in §15; they never
appear at rest and never carry `data-region` or `data-answer`.

---

## 2. Region contents (what each region must render at rest)

### R0 — System and trust bar (two complete answers)

`[data-region="R0"]` contains the complete, separate `ON-G1` and `ON-G6` answer anchors. It is two
fixed lines, never scrolls, and never asks the operator to join another region:

| Answer | Required visible fields | Failure it prevents |
|---|---|---|
| `ON-G1` system | browser/SSE, control-plane read, workers, projections; each names state and worst age | requiring a health join with `R3b` |
| `ON-G6` trust | epoch, worst observation age, projection state, degraded count, stale count, partial count, unknown count | green state over stale or incomplete evidence |

Repository/worktree/campaign scope prefixes both lines but is not a separate answer. `R3b` may mirror
worker/projection detail, and local values retain provenance chips, but neither is part of the glance
answer and neither carries `data-answer="ON-G1"` or `data-answer="ON-G6"`.

`[M]` (r0 M2, M3, A1, A10; control packet `control_epoch`/`degraded`).

### R1 — Attention inbox (the operator's work queue)

A durable, ranked, deduplicated list; not a decorative strip (`[P]`; r6c IA4, IA5). It has three
non-scrolling reserved rows. Items are ranked by *severity × actionability* inside those guarantees,
so a saturated inbox cannot bury either a new critical failure or a pending controller decision:

- **R1a decisions** (`[data-attention-class="decision"]`, containing `[data-answer="ON-G5"]`) — one
  highest-priority pending decision, or an explicit `none pending`: target run, decision kind,
  current epoch, evidence authority, and a compact **eligibility token**
  (`observe|inspect|approve|promote|cancel|retire|none`). This is the canonical at-rest `ON-G5`
  answer; any `R2` decision token is a navigational mirror, never a second answer writer (p5 IA5/IA9).
- **R1b failures/risks** (`[data-attention-class="risk"]`, containing `[data-answer="ON-G3"]`) — one
  highest-severity run failure/stall/risk, or an explicit `all clear`; worker/projection impact and
  money-risk exceptions compete by severity inside this reserved row.
- **R1c next item** (`[data-attention-class="next"]`) — the highest remaining decision, risk,
  supervisor flag, or process gap after R1a/R1b reservations.

Each item carries identity, severity, actionability, first/last-seen, scope, state
(`new|active|snoozed|resolved|stale`), authority, action, and source+age (`[P]`; direction §3.3).
Visible capacity is exactly three rows at 390×844, four at 1024×768, and five at 1440×900. Every case
contains R1a and R1b; remaining rows are globally ranked. Overflow opens the Attention lens; `R1`
itself never scrolls or clips its two canonical answers (`[P]`; p5 IA6).

### R2 — Run ledger (default operational body)

`[data-region="R2"]`, carrying one `ON-G2` answer anchor (`[data-answer="ON-G2"]`) and bounded row
selectors `[data-run-id]`. Its fixed counts line contains exactly running, queued, failed, and live;
those four values are the complete glance answer for any fleet size. Below it, a keyed,
write-on-change sample of live agent sessions/runs is ranked for triage
(attention first, then running/queued, then settled) `[M]` keyed-list contract; `[P]` ranking. Every row shows:
agent/session identity (session id · worktree/host target · current command/tool · provider×model ·
attempt, per direction §4.1 Move 1) · spec/cell · phase `n/total` · lifecycle state · changed-at/live
marker · paired **ADVISORY claim / MEASURED proof** marks · source/commit marker · cost provenance
(on-row) · attention state · **decision-eligibility token** · receipt coverage (`recorded`/`missing`).
Live/change state is always visible — never behind a filter (`[X]`; r0 M7, r6c IA1). This is where
`ON-G2` lives and where a row-level decision mirror may point back to `R1a`. `R2` shows at least three
rows at mobile, seven at 1024×768, and eight at 1440×900. The full fleet opens in a separate lens;
`R2` never scrolls. A row is a ledger line, not a dashboard card; no card border or lifecycle-only row
may pass the glance gate.

### R3 — Constraint ledger (decisions' context, not peer boards)

Three **fixed-height, non-scrolling** annotations stacked. `R3a` is the complete `ON-G4` answer and
`R3c` is the complete `ON-G7` answer. `R3b` is worker/projection detail only; system status is already
complete in `R0`. None may require scrolling or move below the fold (p5 IA2/IA3/IA4/IA5).

- **R3a COST** (`[data-answer="ON-G4"]`) — exactly five labelled values, each with
  `[data-field]`: retained-window spend, burn rate, worst provider-window %, wallet/token headroom,
  and reserved-(unspent)-leases; a money-risk exception marker when a window/lease nears its cap.
  This is the full `ON-G4` answer, not a risk exception alone (p5 IA3). It is a *constraint annotation*,
  not the removed "Money board" or a field of KPI cards.
- **R3b HEALTH DETAIL** — two bounded rows: worker health (unhealthy count + affected-run link) and
  aggregate projection health (worst lag + oldest report age). Registry/ledger/chroma/neo4j detail
  opens in `R4`. This region mirrors the same epoch as `R0` but is never required to answer `ON-G1`
  or `ON-G6` (p5 IA5).
- **R3c COMPOSITION** (`[data-answer="ON-G7"]`) — a **bounded** rollup of model × condition ×
  provider × lifecycle: exactly four one-line marginals, each with at most three buckets (top,
  explicit `other`, explicit `unknown`), never an unbounded cross-product and never a chart (p5 IA4). Performance/cost/quality
  is **not** here (separate lens; §5 T3).

### R4 — Selection dock (drill-down only)

Opens on a run/attention-item selection; not required at rest, never a `data-region` layout region.
It is composed of four named sub-regions plus one deliberate lens, reconciled with
`control_room_interaction_model.md` (§3.1–§3.3) so the two surfaces the facelift dropped are explicit:

- **`R4a` ADDRESS & IDENTITY** (`[data-dock-region="address"]`) — the typed address band
  (`[data-dock-address]`), run identity (session · worktree/host · current command/tool ·
  provider×model · attempt), lifecycle state, scope, and control epoch/revision. It carries the
  routing inputs and the Claude/design session identity from the old detail header, cell panel and
  routing board (`ON-D5`, u1 §3.1.A/B).
- **`R4b` PER-WORKER EVENT + ACTION** (`[data-dock-region="worker"]`) — the restored surface. It
  carries (i) the **one** selected worker's event stream — replayed history bounded by a
  `replay_complete` boundary then live frames, `[data-attempt-feed]` with `[data-feed-entry]`,
  `[data-event-kind]` (`step_start|step_finish|reasoning|operator|text|tool_use`), a producer-supplied
  `[data-event-time]`, and `[data-feed-follow]`/`[data-feed-pause]` controls; and (ii) the **action
  band** — every action applicable to the selected target, rendered as `[data-action="<verb>"]` with
  `[data-action-target]`, `[data-action-authority]` (`controller`/`aios`), `[data-action-reversible]`,
  `[data-action-confirmation]` (the typed-door phrase or `none`), and a `[data-action-receipt]`
  result. Verbs and endpoints are exactly u1 §3.1: `attach`/`detach`/`copy-session`,
  `steer`/`interrupt` (`POST /api/flags/<session_id>/…`), the owned Claude
  `stop`/`respawn`/`rm`/`steer` and `logs` (`POST /api/claude-agents/…`), the design
  `input`/`interrupt`/`save`/`run` (`POST /api/design-sessions/…`), and the docs
  `approve` (`POST /api/docs-health/approve`). A flag never becomes an automatic action (I7).
- **`R4c` EVIDENCE LADDER** (`[data-dock-region="evidence"]`) — the p1 typed chain (identity →
  lifecycle → narration → measured facts → independent verification → change/commit → cost provenance
  → decision → registry record) with `[data-evidence-ladder]` and one `[data-attempt-boundary]` per
  attempt. Satisfies `ON-D1`, `ON-D2`, `ON-D4`.
- **`R4d` STEP TIMINGS** (`[data-dock-region="timing"]`) — the **per-attempt timing region**: for the
  selected run's attempt chain, `[data-timing="queue_wait|service_time|first_token|duration|retries|tokens.answer|tokens.explanation|cost|exit_code|verification"]`,
  each with `[data-state="measured|unknown"]` and a `[data-value]`. Values come from
  `StepAttemptRecord` (`started_at`/`ended_at`, `attempt_no`, `tokens`, `cost_usd`, `exit_code`,
  `error`) and the ledger `AttemptRecord` (`queue_wait_ms`, `service_time_ms`, `first_token_at`,
  `tokens_*`). An unobserved timing is `unknown`, never `0`. Satisfies u1 §3.3 and `ON-D6`.

**Workforce step-timing lens (`[data-lens="workforce"]`, `L-WORKFORCE`).** The per-attempt region
`R4d` is a single-run view; the **fleet aggregate** — p50/p95 queue wait, p50/p95 service time,
first-token latency, retry rate, and tokens per attempt by model — is a deliberate lens (like Money
and Fleet), not a resting region. This keeps the §3.2 resting budget intact while giving the
"where is the workforce spending time and money?" job (`J4`) a home (u0 §3 P3; r0 A4). A lens is a
deliberate drill-down; the resting contract never depends on it.

---

## 3. Hierarchy, pixel budget, and selected state

### 3.1 Hierarchy and the anti-crowding rule

The hierarchy is **visual weight and reading order within one screen**, not disclosure depth
(everything in §2 is present at rest). It follows r6c's required sequence (`[P]`; r6c "Required IA").

1. **First — the run identity and work queue.** `R2` begins with the session/terminal identity band;
   `R0` truth and `R1` attention qualify it. The operator sees *which agent is acting*, *where*, and
   *what needs them* before reading generic lifecycle counts. `R1` is globally severity-ranked (§2),
   not category-pinned.
2. **Second — the evidence-bearing fleet body.** `R2` run ledger is the largest region and the default
   addressable list. It carries `ON-G2`, the ADVISORY/MEASURED pair, eligibility, and receipt coverage;
   it is never displaced by a selected object.
3. **Third — the constraint ledger.** `R3a` cost, `R3b` health, `R3c` composition answer the remaining
   glance questions as compact annotations attached to the run ledger. They are third by weight, but
   present and **non-scrolling**, never peer KPI cards.

**Anti-crowding rule.** Every resting region is fixed-height and summary-first. `R1` reserves its risk
and decision rows; `R2` shows a counts line plus a bounded session sample; `R3a/b/c` use the exact line
budgets below. Any overflow is a drill-down (`R4`) or lens (§6), never an internal scrollbar. No
required answer, mirror, or sample row may be clipped or below the fold (p5 IA2/IA7).

### 3.2 Pixel budget (sums fit both viewports)

All dimensions are CSS border-box pixels, including region padding and borders and excluding browser
chrome. Text may truncate with an accessible full name, but required state/value tokens never wrap past
their line clamp. The mobile column sums every region; desktop places `R1`/`R2`/the `R3` stack side by
side, so vertical use is `R0 + gap + max(R1, R2, R3 stack)`.

| Region | 1440×900 max-height | 1024×768 max-height | 390×844 max-height | Internal line/row budget | Canonical need(s) |
|---|---:|---:|---:|---|---|
| `R0` system / trust | 72 | 60 | 72 | mobile: 8px vertical padding + 4 × 14px micro-lines + 8px spare =72; desktop/narrow use two 24/22px answer rows | `ON-G1`, `ON-G6` |
| `R1` attention | 800 | 692 | 144 | max-density rows exactly 5/4/3; row heights 56/52/38; mobile formula 8 padding + 18 heading + 4 gap + 3×38 =144 | `ON-G3`, `ON-G5` |
| `R2` run ledger | 800 | 692 | 284 | exact rows 8/7/3 at 88/84/80; counts 40/36/32; mobile formula 8 padding +32 counts +4 gap +3×80 =284 | `ON-G2` |
| `R3a` cost | 220 | 160 | 92 | mobile: 8 padding + one 20px heading/exception line + 2×32px value rows =92; five unique cells in 3+2 grid | `ON-G4` |
| `R3b` health detail | 180 | 132 | 68 | mobile: 8 padding +18 heading +2×21px detail rows =68; no answer anchor | none (mirror only) |
| `R3c` composition | 140 | 116 | 60 | mobile: no separate heading; accessible region name + 8 padding +4×13px marginals =60 | `ON-G7` |
| `R4` selection dock | 0 at rest | 0 at rest | 0 at rest | hidden until selection | none |
| Outer / internal gaps | 12 + 16 | 8 + 16 | 5 × 8 = 40 | no unbudgeted margins; safe-area padding is inside `R0`/region heights | none |
| **Vertical sum** | **72 + 12 + 800 = 884 ≤ 900** | **60 + 8 + 692 = 760 ≤ 768** | **72+144+284+92+68+60+40 = 760 ≤ 844** | headroom: 16 / 8 / 84px | all seven |

Horizontal fit is equally binding:

| Viewport | Outer padding | Gaps | `R1` | `R2` | `R3` stack | Exact sum |
|---|---:|---:|---:|---:|---:|---:|
| 1440 | 2 × 16 | 2 × 12 | 300 | 744 | 340 | **32+24+300+744+340 = 1440** |
| 1024 | 2 × 12 | 2 × 8 | 224 | 472 | 288 | **24+16+224+472+288 = 1024** |
| 390 | 2 × 12 | 0 | 366 | 366 | 366 | **24+366 = 390** (stacked, not summed across columns) |

Every region uses `box-sizing:border-box`; horizontal padding is ≤12px per side desktop and ≤8px per
side mobile. Labels are one line with ellipsis; required values and state words are never ellipsized.
The render gate asserts all maxima, line clamps, row counts, and exact sums (§10). Raising any budget
without preserving these inequalities breaks the contract.

**Content grids.** `R3a/b/c` use exactly 8px horizontal padding at every viewport, giving inner widths
324px desktop, 272px narrow, and 350px mobile. `R3a` uses three columns of 102px with 9px gaps at
desktop, three 86px columns with 7px gaps at narrow, and three 110px columns with 10px gaps at mobile;
the second row uses the first two tracks. `R3c` uses label/gap/buckets tracks of 64/4/256px desktop,
56/4/212px narrow, and 68/4/278px mobile. Each buckets track has exactly three equal slots (`top`,
`other`, `unknown`). Thus no mobile track is incorrectly reused at a narrower desktop column.

**Mobile forcing grid.** After 8px region padding, each region has 350px inner
width. `R0` uses a 70px scope column + 4px gap + 276px answer grid: `ON-G1` occupies two 14px rows of
two 136px cells with a 4px gap; `ON-G6` occupies one row of three 89px cells and one row of four 66px
cells, with 4px gaps. `R1` rows use two 15px text lines inside each 38px row. `R2` rows use three 18px
lines inside each 80px row: identity/target/model/attempt, command/phase/lifecycle/live, then
claim/proof/source/cost/eligibility/receipt. Long identifiers may middle-elide but preserve an
accessible full value and visible prefix+suffix; state, count, money, trust, and bucket values may not
ellipsis. `R3a`'s exception shares the 20px heading line. `R3c` has four 13px lines. G-3/G-13/G-14
reject any overflow, overlap, missing clamp, or value clipping at every viewport.

### 3.3 Selected state (one arrangement per breakpoint)

Selection is drill-down, not a new resting screen. The fixed arrangement is:

- **Desktop:** `R4` opens as a **bottom dock** (≈ 320 px) while `R0`, `R1`, `R2`, `R3` stay in their
  resting columns; the body above the dock re-flows to reduced-height summaries. The resting-screen
  no-scroll proof does not apply after selection, but each canonical answer remains represented by
  its fixed summary rather than an internal scrollbar.
- **Mobile:** `R4` pushes over `R2` as a full-height inspector with an explicit Back; `R0` and `R1`
  remain at the top and the `R3` answers remain reachable in the same viewport, so the content of the
  resting answer is never destroyed.

Either way, every region promised to remain visible is tested in §10 (p5 IA10), and the at-rest
`ON-G4`/`ON-G7` answers do not disappear while an object is selected.

### 3.4 R4 drill-down budgets (never charged to the resting sum)

The §3.2 budget is the **at-rest** contract and is unchanged: `R4` is `0 at rest`. Once selected,
`R4` is a bottom dock on desktop (≈320px, §3.3) and a full-height inspector on mobile, and its four
sub-regions are budgeted **inside** that dock. These budgets are internal to `R4` and must never be
added to the §3.2 vertical sum.

| Dock sub-region | Desktop (dock ≈320px) | Mobile (full height) | Internal budget | Need(s) |
|---|---:|---:|---|---|
| `R4a` address/identity | 48 | 64 | one identity band + one address line; no scroll | `ON-D5` |
| `R4b` worker event + action | 160 | 360 | event feed: bounded rows with follow/pause; action band: one group of `[data-action]` chips, wraps, no scroll | `ON-D1`, `ON-D2` |
| `R4c` evidence ladder | 160 | 280 | one `[data-attempt-boundary]` per attempt, bounded; overflow is the Attempt lens | `ON-D1`, `ON-D4` |
| `R4d` step timings | 96 | 140 | one `[data-timing]` row per timing field; a missing value is an explicit `unknown` row, not a gap | `ON-D6` |

Within a sub-region, excess rows are a deliberate **lens** (Attempt, Money, Workforce), never an
internal scrollbar: `R4b` bounds the event feed the same way the old transcript bounded 500 rows, and
`R4d` summarizes the latest `N` attempts with the full chain in the Attempt lens. The `[data-lens]`
container is `hidden` at rest and is not a `data-region`.

---

## 4. The canonical glance contract: one `ON-G1..G7` list

This is the single authoritative contract (p5 IA1). It supersedes every earlier mapping in r1/p1/p2:
at **both** 1440×900 and 390×844, each need is answered by the listed region, with the listed
visible content, inside the initial viewport. "Above fold" means the region's bounding box is fully
inside the viewport (`top ≥ 0` and `bottom ≤ viewport height`), the page does not scroll, and the
region's own `scrollHeight ≤ clientHeight` (no internal scroll). The mechanical check is §10.

| Need (authoritative r1 wording) | Canonical region | Visible content (the answer) | Above fold @1440×900 | Above fold @390×844 | Never the answer | Evidence |
|---|---|---|---|---|---|---|
| `ON-G1` is the whole system up / room connected? | **`R0`** | browser, control plane, workers, and projections each show state + worst age | yes — `R0` is 0–72px; no scroll | yes — `R0` is 0–72px; no scroll | `R3b` detail, one combined health score | `[M]` r0 M2/M3/A1; `[P]` separation |
| `ON-G2` what is running / queued / failed right now, and what is live? | **`R2`** | exact running/queued/failed/live counts + bounded agent-session sample with lifecycle/live state | yes — `R2` is 84–884px; no scroll | yes — `R2` is 232–516px; no scroll | full-fleet lens, hidden/filter-only live view | `[M]` r0 M7 keyed list; `[X]` r6c IA1 |
| `ON-G3` is anything failing, stalled, or at risk? | **`R1`** | reserved risk row: highest-severity identity/state/action or explicit `all clear` | yes — `R1` is 84–884px; reserved row visible | yes — `R1` is 80–224px; reserved row visible | overflow queue, a count alone | `[P]` r6c IA4; `[X]` Linear/Datadog triage |
| `ON-G4` what is money doing — spend, burn, provider quota, wallet, reserved leases? | **`R3a`** | exactly five unique labelled values (`money.spend`, `money.burn`, `money.quota`, `money.wallet`, `money.leases`) + exception marker | yes — `R3a` is 84–304px; no scroll | yes — `R3a` is 524–616px; 3+2 grid, no scroll | Money lens, a risk exception alone | `[M]` r0 M1; `[P]` five-value composition |
| `ON-G5` does anything need a decision from me? | **`R1`** | reserved decision row: target, kind, epoch, authority, eligibility; or explicit `none pending` | yes — `R1` is 84–884px; reserved row visible | yes — `R1` is 80–224px; reserved row visible | `R2` mirror, pending count alone | `[M]` packet `awaiting_approvals`/`promotable_runs`; `[P]` eligibility tokens |
| `ON-G6` is what I am looking at fresh and trustworthy? | **`R0`** | epoch, worst age, projection state, degraded count, and explicit stale/partial/unknown counts | yes — `R0` is 0–72px; no scroll | yes — `R0` is 0–72px; no scroll | distributed provenance chips, global age footer | `[M]` r0 M2/A10; `[P]` complete compact verdict |
| `ON-G7` what is the shape of the fleet (by model / condition / provider)? | **`R3c`** | exactly four marginals: model, condition, provider, lifecycle; each ≤3 buckets including `other` and `unknown` | yes — `R3c` is 500–640px; no scroll | yes — `R3c` is 700–760px; no scroll | unbounded cross-product, chart, secondary lens | `[P]` r6c IA14; `[X]` r1 need |

**Simultaneity assertion (the IA1 test).** A screenshot of the default viewport at **both**
1440×900 and 390×844 must contain exactly one anchor for each answer, inside its one canonical region,
at once — none hidden behind a peer-board switch, lens, modal, mirror, internal scroll, or the fold.
The mapping is total and single-valued: `G1→R0`, `G2→R2`, `G3→R1`, `G4→R3a`, `G5→R1`, `G6→R0`,
`G7→R3c`. This is the mechanical disproof of the r5 layout and p5 IA1/IA2/IA5 defects.

---

## 5. Tradeoffs where "at rest" meets crowding, and the chosen resolution

The contract is honest only if the forcing cases are named. These are the known tensions and the
resolution each takes; every resolution preserves the §4 canonical contract.

### T1 — Seven answers in one viewport is dense

**Tension:** `R0` + three rail summaries + the inbox + the roster compete for one screen; a naive
layout either crowds the roster or pushes the rail below the fold.

**Resolution `[P]`:** the §3.2 pixel budget with **exception-first, count-first** representations.
Every region is fixed-height and non-scrolling (no embedded tables or charts); full lists open in
deliberate lenses. There is **no ticker fallback and no below-fold placement**: the vertical,
horizontal, line, and row budgets were chosen so the regions fit 1440×900 and 390×844 without
scrolling. If a future change cannot fit, the offending content is drill-down/lens, not a region that
moves below the fold or acquires overflow.

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
`R1` reserved inbox; `R2` bounded ledger; `R3a` cost (five values, two-line grid); `R3b` health detail;
`R3c` bounded composition. The §3.2 mobile budget (760 ≤ 844) proves they fit above the fold. There
is **no mobile omission**; the only mobile difference is arrangement and bounded row counts (§10 G-8/G-9).

### T5 — Very large fleets (hundreds of runs)

**Tension:** the roster cannot render every run at rest.

**Resolution `[P]`:** the `ON-G2` answer at rest is the exact **running + queued + failed + live
counts**, followed by attention-ranked and changed-since sample rows. The full roster opens in a Fleet
lens; it does not scroll inside `R2`. The operator never needs a lens to know the totals or whether
anything is live, while the resting contract remains independent of fleet cardinality.

---

## 6. Drill-down paths (selection → evidence; `ON-D1..D7`)

Drill-down is one selection from the roster or inbox into `R4`; the roster and summaries remain
(`[P]`; r6c IA2, IA10). The navigation contract holds: each object has a type + stable key; selection
survives live reconciliation and compatible lens changes; scope/filters/sort/time-range/scroll/
transcript-query/follow-pause persist; incompatible scope changes confirm; disappeared/stale/denied
states keep identity; closing restores focus to the origin; exactly one event stream is open `[M]`.

| Need | Path |
|---|---|
| `ON-D1` one run, step by step live | select R2 row → R4a address → R4c evidence ladder → attempt → **R4b event stream** (one live stream, follow/pause) |
| `ON-D2` why flagged / safe action | select R1b item or R2 row → R4c decision/flag object → **R4b action band** with safe-action preview (target, epoch, scope, budget, reversibility, receipt) |
| `ON-D3` design draft/validation | Sessions object type (roster/search) → R4 design-session inspector (R4a + R4b actions) |
| `ON-D4` canonical explanation | R4c → registry record link → canonical-lineage view (`L-REGISTRY`, distinct from the runtime trace) |
| `ON-D5` route + cost/quality | R4a routing inputs + evidence (`L-COMPOSITION` for the fleet view), beside the run context |
| `ON-D6` cost by step/model/cell | R4c cost/lease provenance rung + **R4d step timings**; aggregate in the Money lens and the **Workforce step-timing lens** (`L-WORKFORCE`) |
| `ON-D7` background Claude session | Sessions object type (roster/search) → R4 Claude-session inspector (R4a + R4b owned actions) |

**Restored worker surfaces (u3).** `ON-D1`/`ON-D2`/`ON-D7` terminate in `R4b` (the per-worker event
stream plus the governed action band), and `ON-D6` gains `R4d` (per-attempt timing); the fleet
aggregate is `L-WORKFORCE`. These are the surfaces the facelift dropped; they are placed by
`parity_inventory.json` (`experiments/research/control_room/`) and asserted by §15. Exactly one
`R4b` event stream is open at a time (`E-1`/`I2`).

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

`R0` owns both complete global answers: system state (`ON-G1`) and trust verdict (`ON-G6`). Every
consequential value in `R1/R2/R3/R4` still carries local **source + observation-time/age** provenance;
truncation/partiality, revision/epoch, and measured/estimated/unknown/unmeasured semantics attach where
they apply. Those chips explain a value but are not pieces of the glance answer. Green never renders
for a stale or unmeasured subsystem (`[M]`; r0 M2).

The following inventory is the exact set of provenance-bearing fields the geometry checks (§10 G-4,
contrast) and the blind check B-6 cover; any value not listed is not "consequential" at rest and may
omit the chip (p5 IA11):

| Region | Provenance-bearing fields | Required chip attributes |
|---|---|---|
| `R0` | browser, control, workers, projections; epoch, worst age, stale/partial/unknown counts | source + age; `epoch` carries revision; all system/trust fields are complete here |
| `R1` | every inbox item (decision, failure/risk, advisory) | authority class (`measured`/`computed`/`heuristic`/`policy`/`unknown`) + first/last-seen |
| `R2` | per-row cost provenance; row `changed-at` | `cost_source` (`metered`/`estimated`/`unknown`/`reconciled`) + age; every visible row |
| `R3a` | all five `money.*` values | source + age; `unknown` renders as explicit `unknown`, never `0` |
| `R3b` | worker aggregate; projection aggregate | source + last-report age; mirror of `R0`, never required for its answers |
| `R3c` | composition marginals | source + age; `other`/`unknown` rendered explicitly |
| `R4a` | identity, lifecycle, scope, epoch, routing inputs | source + age; `epoch` carries revision |
| `R4b` | each `[data-feed-entry]` and each `[data-action]` chip | event: `data-event-kind` + producer `data-event-time`/age; action: authority + target + reversibility + receipt |
| `R4c` | the full evidence ladder | per-rung evidence class + source + age (drill-down; not tested at rest) |
| `R4d` | each `[data-timing]` value | `data-state="measured"\|"unknown"` + source + age; an unknown timing is explicit, never `0` |

No need is split across regions. Mirrors share the canonical answer's epoch and omit `[data-answer]`,
so a reviewer never has to join two writers or two freshnesses (p5 IA5).

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
| cell/session control panel (`cell-control-panel`) | R4a (facts) + R4b (attach/detach/copy) | the per-worker surface the facelift dropped |
| transcript event stream (`transcript-panel`, `/api/events/<cell_id>`) | R4b | restored with follow/pause; one stream at a time |
| background `claude` sessions + daemon (`claude-agents`) | L-SESSIONS + R4b owned actions | start/stop/respawn/rm/steer/logs re-housed |
| design sessions (`design-control-panel`) | L-SESSIONS + R4b | composer/save/run/interrupt re-housed |
| workforce step timings (absent in the old room) | R4d (per attempt) + L-WORKFORCE (fleet) | net-new surface assembled from the ledger, not a re-skin |
| recording audit/sweep | AUDIT + R1c process health | decision-record coverage |

**u3 placement.** Every old panel/control/feed is enumerated with its disposition and its target
**surface** in `experiments/research/control_room/parity_inventory.json` (v1); §14 defines the closed
surface palette and §15 makes placement an acceptance check. The rows above are the r0-level view of
the same placement.

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

1. **Present and unique** — Playwright `locator(sel)` has the declared cardinality (one for each
   answer and layout region), and the element and all ancestors are not `hidden`, `[hidden]`,
   `display:none`, `visibility:hidden`, or `aria-hidden="true"`. Checks over repeated rows/fields use
   `locator.count()` plus `locator.nth(i)`, never `querySelector`.
2. **In viewport** — `const r = el.getBoundingClientRect()` satisfies `r.top >= -0.5`,
   `r.bottom <= innerHeight + 0.5`, `r.left >= -0.5`, `r.right <= innerWidth + 0.5`.
3. **Non-zero box** — `r.width > 0 && r.height > 0` (rejects collapsed or clipped-to-nothing nodes).
4. **No scroll** — `document.scrollingElement.scrollHeight <= innerHeight + 1` and
   `scrollWidth <= innerWidth + 1` (no page scroll, no horizontal overflow); for **every resting
   region and answer anchor**, `el.scrollHeight <= el.clientHeight + 1` and
   `el.scrollWidth <= el.clientWidth + 1` (no internal scroll or clipping).
5. **Contrast** — for each text node inside the region, the computed-color luminance ratio is
   ≥ 4.5:1 for normal text and ≥ 3:1 for large text (≥ 24px, or ≥ 18.66px bold), against the
   element's effective composited background. The gate reuses the checked-in
   `verify_svg_rendering.py` parse/composite/luminance probe for HTML text and requires zero
   violations; non-empty text is not a contrast substitute.

### 10.2 Selector map

| Anchor | Explicit selector(s) | Required cardinality / meaning |
|---|---|---|
| Layout containers | `[data-glance-shell]`, `[data-glance-body]`, `[data-r3-stack]` | exactly one each; used for x/y/gap/overlap equations |
| Layout regions | `[data-region="R0"]`, `[data-region="R1"]`, `[data-region="R2"]`, `[data-region="R3a"]`, `[data-region="R3b"]`, `[data-region="R3c"]` | exactly one each; only these values use `data-region` |
| Answers | `[data-answer="ON-G1"]` through `[data-answer="ON-G7"]` (seven selectors written separately) | exactly one each; each must be a descendant of the §4 canonical region |
| Labels / values | every required `[data-field]` contains exactly one `[data-label]` and `[data-value]` | visible label and non-empty visible value checked separately |
| `ON-G1` system | `[data-field="system.browser"]`, `[data-field="system.control"]`, `[data-field="system.workers"]`, `[data-field="system.projections"]` inside its answer | exact set equality; each contains `[data-state]` in `up,degraded,down,unknown` and numeric `[data-age-seconds]` |
| `ON-G2` fleet state | `[data-field="runs.running"]`, `[data-field="runs.queued"]`, `[data-field="runs.failed"]`, `[data-field="runs.live"]` inside its answer | exact set equality; four unique fields |
| `ON-G3` risk | `[data-attention-class="risk"] [data-answer="ON-G3"]` with `[data-field="risk.identity"]`, `[data-field="risk.state"]`, `[data-field="risk.action"]` | exactly one reserved row; state is `active` or `all-clear`; all-clear uses identity/action=`none` |
| `ON-G4` cost | `[data-field="money.spend"]`, `[data-field="money.burn"]`, `[data-field="money.quota"]`, `[data-field="money.wallet"]`, `[data-field="money.leases"]`; `[data-money-risk]` | exact field set; risk marker count 1 only in F-3, otherwise 0 |
| `ON-G5` decision | `[data-attention-class="decision"] [data-answer="ON-G5"]` with `[data-field="decision.state"]`, `[data-field="decision.target"]`, `[data-field="decision.kind"]`, `[data-field="decision.epoch"]`, `[data-field="decision.authority"]`, `[data-field="decision.eligibility"]` | state=`pending` or `none`; eligibility in `observe,inspect,approve,promote,cancel,retire,none`; none uses target/kind/authority/eligibility=`none` |
| `ON-G6` trust | `[data-field="trust.epoch"]`, `[data-field="trust.worst_age"]`, `[data-field="trust.projection_state"]`, `[data-field="trust.degraded_count"]`, `[data-field="trust.stale_count"]`, `[data-field="trust.partial_count"]`, `[data-field="trust.unknown_count"]` | projection state in `current,lagging,stale,failing,unknown`; four counts are non-negative integers; F-0 all zero/current, F-4 unknown>0, F-5 stale/degraded>0 |
| `ON-G7` composition | four `[data-marginal]` values: `model`, `condition`, `provider`, `lifecycle` | exactly four unique marginals; each has exactly three unique buckets: `top` (with `[data-category]`), `other`, `unknown` |
| Row identity | `[data-region="R2"] [data-run-id]` | 8 desktop / 7 narrow / 3 mobile visible rows in the max-density fixture |
| Agent identity | for each R2 row: `session.identity`, `terminal.target`, `command.current`, `model.provider`, `attempt.number` | five non-empty fields scoped to that row |
| Run state | for each R2 row: `[data-field="spec.cell"]`, `[data-field="phase.progress"]`, `[data-field="lifecycle.state"]`, `[data-field="run.live"]`, `[data-field="source.commit"]`, `[data-field="cost.provenance"]`, `[data-field="attention.state"]` | seven non-empty fields scoped to that row |
| Evidence / action | for each R2 row: `[data-field="evidence.advisory"]`, `[data-field="evidence.measured"]`, `[data-field="evidence.source"]`, `[data-field="decision.eligibility"]`, `[data-field="decision.receipt"]` | five non-empty fields scoped to that row; mirrors never carry `data-answer` |
| Line clamps | `[data-max-lines]` on every R0 micro-row, R1 item line, R2 row line, R3a cell, R3b line, and R3c marginal | integer contract checked against rendered `height / line-height`; required values also carry `[data-no-ellipsis]` |

### 10.3 Geometry checks (G)

| # | Viewport | Selectors | Assertion | Threshold |
|---|---|---|---|---|
| G-1 | all three | six explicit region selectors + seven explicit answer selectors | unique + primitives 1, 2, 3 | exact global value sets; exactly one each; 0 violations |
| G-2 | all three | page + all answers | primitive 4 (page) | `scrollHeight ≤ innerHeight+1`, `scrollWidth ≤ innerWidth+1` |
| G-3 | all three | all six regions + all seven answer anchors | primitive 4 (no internal scroll/clipping) | scroll width/height ≤ client width/height + 1 |
| G-4 | all themes/viewports | all text nodes in the six resting regions | primitive 5 (contrast) | ≥ 4.5:1 normal / ≥ 3:1 large; dark/light/forced-colors |
| G-5 | all three | computed `font-size` in `R0..R3c` | type floor | ≥ 12px mobile, ≥ 13px desktop; labels ≥ 11px |
| G-6 | all three | `[data-value]` inside every required field | non-empty visible value | `innerText.trim().length > 0`; label text alone cannot pass |
| G-7 | 1440×900 | shell/body/R3 stack + six regions | §3.2 desktop equations | fixed boxes and gaps equal expected coordinates ±1px; no overlap; 72+12+800≤900; 32+24+300+744+340=1440 |
| G-8 | 390×844 | six regions | §3.2 mobile budget | heights ≤72/144/284/92/68/60; exact vertical sum ≤844; content width=366 |
| G-9 | 390×844 | six explicit region selectors | single-column arrangement | each left=12±1 and width=366±1; no nested item class included |
| G-10 | all three | `ON-G4` descendant fields + `[data-money-risk]` | exact money schema | set equals five named fields; no duplicate; marker count matches fixture; every value visible |
| G-11 | all three | `ON-G7` marginals/buckets | exact bounded composition | exactly four unique legal marginals; each has exactly three unique buckets: `top`,`other`,`unknown` |
| G-12 | 1024×768 | six regions + seven answers | §3.2 narrow budget | unique/in viewport/no scroll; vertical sum ≤768; exact width sum=1024 |
| G-13 | all three | every visible `[data-run-id]` row | row-scoped identity/evidence/action field sets | each exact set present and non-empty; no unscoped comma selectors |
| G-14 | all three | `R1` reserved rows + R2 counts/sample | capacity and line clamps | decision+risk rows always visible; R2 counts exact; row counts 8/7/3; no text exceeds declared lines |
| G-15 | all three | seven answers | canonical parent mapping | exact map `G1:R0,G2:R2,G3:R1,G4:R3a,G5:R1,G6:R0,G7:R3c`; mirrors have no answer attr |

Mobile has **no** `ON-G7` omission: G-1 and G-11 run at 390×844 too (p5 IA4).

### 10.4 Blind-comprehension checks (B)

A human reviewer, shown only the screenshot and not this document, must state each answer within ten
seconds and point to the carrying element; a miss fails the design, not the copy (p4 recognizability
test; p5 IA8).

| # | Reviewer says | Carrying element |
|---|---|---|
| B-1 | "The room is connected / the system is up." | complete `R0` system answer: browser/control/workers/projections |
| B-2 | "These are the live runs and what is queued/failed." | `R2` exact counts + bounded rows |
| B-3 | "That failure needs me" or "risks are clear." | `R1` reserved risk answer |
| B-4 | "Here is spend against the five money buckets." | `R3a` five values |
| B-5 | "That run is waiting on a decision" or "none need me." | `R1` reserved decision answer |
| B-6 | "Here is whether the data is fresh." | complete `R0` trust answer: epoch/worst age/stale/partial/unknown |
| B-7 | "Here is the fleet's shape." | `R3c` bounded rollup |
| B-8 | The correct next action for the top item. | `R1` eligibility token / `R2` mirror |
| B-9 | "This is an agent session writing to a terminal, not a service dashboard." | first R2 identity band: session, terminal target, current command, provider×model, attempt |
| B-10 | "The agent's claim and the measured proof are different." | paired R2 ADVISORY/MEASURED marks, visible without opening R4 |
| B-11 | "An action is eligible and its recording status is visible." | adjacent R2 eligibility and receipt tokens |

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

The gate intercepts every `/api/*` request and the SSE endpoint before navigation, serves committed
fixture JSON/event frames, then waits for exactly one `[data-render-state="ready"]`. No live Redis,
clock, network, or production data participates; fixture time is frozen and every payload carries one
control epoch.

`ready` has one exact meaning: all initial mocked GET responses have resolved; the initial SSE
`replay_complete` boundary for the same epoch has rendered; `document.fonts.ready` has resolved; two
`requestAnimationFrame` turns have completed; and the root's `data-control-epoch` equals the fixture
epoch. The browser context fixes UTC, `en-US`, reduced motion, `Date.now()`, and animation durations.
Geometry contexts close the SSE stream at `replay_complete`; event tests use a separate context and may
emit only the transition named by that test.

| Fixture | Required forcing state |
|---|---|
| `F-0` max-density default | 8/7/3 visible rows by viewport; one running, queued, failed and live count; one decision; one risk |
| `F-1` saturated inbox | >20 low-priority items plus a new critical failure and pending decision; both reserved answers remain visible |
| `F-2` 200-run fleet | exact aggregate counts plus bounded R2 sample; no R2 scrollbar |
| `F-3` near-cap cost | all five cost fields plus exception marker |
| `F-4` unknown provider | provider marginal includes `unknown`; cost source shows unknown, never zero |
| `F-5` stale projection | R0 trust stale count/worst age and system projection state both fail visibly |
| `F-6` disconnected browser | R0 browser state fails while other system dimensions remain independently named |
| `F-7` empty queues | reserved risk says `all clear`; reserved decision says `none pending` |

The fixture route inventory is exactly `GET /api/glance` and `GET /api/events` (SSE); any other
`/api/*` request fails the case. `F-0` uses this exact seed object; the fixture loader expands
`run_defaults` into each listed run before returning JSON, so every row has the complete schema:

```json
{
  "control_epoch": 42,
  "source": "fixture:/api/glance",
  "observed_at": "2026-09-11T11:59:56Z",
  "system": {
    "browser": {"state": "up", "age_seconds": 1},
    "control": {"state": "up", "age_seconds": 2},
    "workers": {"state": "up", "age_seconds": 4},
    "projections": {"state": "up", "age_seconds": 4}
  },
  "trust": {"epoch": 42, "worst_age": 4, "projection_state": "current",
    "degraded_count": 0, "stale_count": 0, "partial_count": 0, "unknown_count": 0},
  "attention": {
    "decision": {"state": "pending", "target": "run-approve", "kind": "approve",
      "epoch": 42, "authority": "controller", "eligibility": "approve"},
    "risk": {"identity": "run-failed", "state": "active", "action": "inspect"},
    "next": {"identity": "projection-registry", "state": "active", "action": "inspect"},
    "items": []
  },
  "run_counts": {"running": 5, "queued": 1, "failed": 1, "live": 3},
  "run_defaults": {"terminal.target": "wt/control-room", "command.current": "pytest",
    "model.provider": "openai/gpt-5.6-sol", "attempt.number": "1", "phase.progress": "2/4",
    "lifecycle.state": "running", "run.live": "live", "source.commit": "abc1234",
    "cost.provenance": "metered", "attention.state": "none", "evidence.advisory": "claimed pass",
    "evidence.measured": "tests pending", "evidence.source": "commit abc1234",
    "decision.eligibility": "inspect", "decision.receipt": "recorded"},
  "run_sample": [
    {"id": "run-approve", "session.identity": "agent-01", "decision.eligibility": "approve"},
    {"id": "run-failed", "session.identity": "agent-02", "lifecycle.state": "failed"},
    {"id": "run-live", "session.identity": "agent-03"},
    {"id": "run-04", "session.identity": "agent-04"},
    {"id": "run-05", "session.identity": "agent-05"},
    {"id": "run-06", "session.identity": "agent-06"},
    {"id": "run-07", "session.identity": "agent-07"},
    {"id": "run-08", "session.identity": "agent-08"}
  ],
  "cost": {"spend": "$12.40", "burn": "$0.82/h", "quota": "61%",
    "wallet": "$7.60", "leases": "$2.10", "money_risk": false},
  "health_detail": {"workers": "0 unhealthy", "projections": "current · lag 0 · age 4s"},
  "composition": {
    "model": {"top": "sol 5", "other": "2", "unknown": "0"},
    "condition": {"top": "clean 4", "other": "3", "unknown": "0"},
    "provider": {"top": "openai 5", "other": "2", "unknown": "0"},
    "lifecycle": {"top": "running 5", "other": "2", "unknown": "0"}
  }
}
```

Before serving, the fixture loader recursively copies the top-level `source`, `observed_at`, and
`control_epoch` into every nested object that lacks an override; the returned wire JSON therefore has
those three keys on each system field, attention item, run, cost field, health field, and composition
marginal. This expansion is deterministic and is itself snapshot-tested.

Fixture deltas are exact: `F-1` appends advisory items `adv-01` through `adv-20` to
`attention.items`, each expanded from `{state:active,action:inspect,authority:heuristic,severity:low}`,
but leaves the decision/risk objects above;
`F-2` sets counts to `80/60/40/20` and keeps the same eight-row sample; `F-3` sets quota=`96%` and
`money_risk=true`; `F-4` sets provider unknown=`2`, `trust.unknown_count=2`, and every affected cost
value to literal `unknown`; `F-5` sets system.projections=`degraded/901s`, projection_state=`stale`,
worst_age=`901`, degraded_count=`1`, stale_count=`1`; `F-6` sets system.browser=`down/7s`; `F-7`
sets decision to `{state:none,target:none,kind:none,epoch:42,authority:none,eligibility:none}` and risk
to `{identity:none,state:all-clear,action:none}`. The exact wire frames follow (blank-line terminators
included); geometry receives snapshot + replay completion, while the event test appends transition:

```text
event: snapshot
data: {"control_epoch":42,"fixture":"F-0"}

event: replay_complete
data: {"control_epoch":42}

event: transition
data: {"control_epoch":43,"kind":"run.failed","target":"run-live"}

```

Geometry receives only the first two frames. Event tests append the third frame in their separate
context and expect exactly one keyed DOM update and one polite announcement.

Every geometry check runs against `F-0`; G-10/G-11/G-14/G-15 additionally run against all forcing
fixtures that change their fields. The gate fails on an unmocked request. Fixtures expose the exact
view projection consumed by the static UI: `system`, `trust`, `attention`, `run_counts`, `run_sample`,
`cost`, `health_detail`, and `composition` objects, all with `control_epoch`, source, and observed-at.
The production implementation needs an additive read-only projection with the same schema; the render
gate itself is deterministic and does not depend on that endpoint existing while the fixture runs.

### 10.7 Reference gate (pseudo-code)

```python
# verify_control_room_rendering.py — executable shape of the geometry class.
VIEWPORTS = {"desktop": (1440, 900), "narrow": (1024, 768), "mobile": (390, 844)}
THEMES = ("dark", "light", "forced-colors")
REGIONS = ["R0", "R1", "R2", "R3a", "R3b", "R3c"]
ANSWER_REGION = {
    "ON-G1": "R0", "ON-G2": "R2", "ON-G3": "R1", "ON-G4": "R3a",
    "ON-G5": "R1", "ON-G6": "R0", "ON-G7": "R3c",
}
FIELDS = {
    "ON-G1": {"system.browser", "system.control", "system.workers", "system.projections"},
    "ON-G2": {"runs.running", "runs.queued", "runs.failed", "runs.live"},
    "ON-G3": {"risk.identity", "risk.state", "risk.action"},
    "ON-G4": {"money.spend", "money.burn", "money.quota", "money.wallet", "money.leases"},
    "ON-G5": {"decision.state", "decision.target", "decision.kind", "decision.epoch",
              "decision.authority", "decision.eligibility"},
    "ON-G6": {"trust.epoch", "trust.worst_age", "trust.projection_state",
              "trust.degraded_count", "trust.stale_count", "trust.partial_count",
              "trust.unknown_count"},
}
ROW_FIELDS = {
    "session.identity", "terminal.target", "command.current", "model.provider", "attempt.number",
    "phase.progress", "lifecycle.state", "run.live", "source.commit", "cost.provenance",
    "attention.state", "evidence.advisory", "evidence.measured", "evidence.source",
    "decision.eligibility", "decision.receipt",
}
EXPECTED_BOXES = {
    "desktop": {"R0": (16, 0, 1408, 72), "R1": (16, 84, 300, 800),
                "R2": (328, 84, 744, 800), "R3a": (1084, 84, 340, 220),
                "R3b": (1084, 312, 340, 180), "R3c": (1084, 500, 340, 140)},
    "narrow": {"R0": (12, 0, 1000, 60), "R1": (12, 68, 224, 692),
               "R2": (244, 68, 472, 692), "R3a": (724, 68, 288, 160),
               "R3b": (724, 236, 288, 132), "R3c": (724, 376, 288, 116)},
    "mobile": {"R0": (12, 0, 366, 72), "R1": (12, 80, 366, 144),
               "R2": (12, 232, 366, 284), "R3a": (12, 524, 366, 92),
               "R3b": (12, 624, 366, 68), "R3c": (12, 700, 366, 60)},
}

for fixture, theme, viewport in product(FIXTURES, THEMES, VIEWPORTS.items()):
    name, (w, h) = viewport
    page = new_isolated_page(timezone="UTC", locale="en-US", reduced_motion="reduce")
    freeze_clock_and_animations(page, "2026-09-11T12:00:00Z")
    install_api_and_sse_routes(page, fixture)  # installed before page.goto
    if theme == "forced-colors":
        page.emulate_media(color_scheme="dark", forced_colors="active", reduced_motion="reduce")
        page.add_init_script("localStorage.removeItem('control-room-theme')")
    else:
        page.emulate_media(color_scheme=theme, forced_colors="none", reduced_motion="reduce")
        page.add_init_script(
            f"localStorage.setItem('control-room-theme', {json.dumps(theme)})"
        )
    page.set_viewport_size({"width": w, "height": h})
    page.goto(PORTAL_URL)
    page.locator('[data-render-state="ready"]').wait_for()

    # Reject unknown values as well as omissions; all repeated checks use nth().
    assert set(page.locator("[data-region]").evaluate_all(
        "els => els.map(e => e.dataset.region)")) == set(REGIONS)
    assert set(page.locator("[data-answer]").evaluate_all(
        "els => els.map(e => e.dataset.answer)")) == set(ANSWER_REGION)
    for region in REGIONS:
        assert page.locator(f'[data-region="{region}"]').count() == 1
    for answer, region in ANSWER_REGION.items():
        anchor = page.locator(f'[data-answer="{answer}"]')
        assert anchor.count() == 1
        assert anchor.evaluate("(el, r) => el.closest('[data-region]').dataset.region === r", region)
        assert anchor.locator("xpath=ancestor::*[@data-region]").count() == 1

    # Assert fixed x/y/width/height, gaps, and non-overlap rather than only maxima.
    for region, expected in EXPECTED_BOXES[name].items():
        box = page.locator(f'[data-region="{region}"]').bounding_box()
        actual = (box["x"], box["y"], box["width"], box["height"])
        assert all(abs(got - want) <= 1 for got, want in zip(actual, expected))

    # No page, region, answer, or field scroll/clipping.
    assert page.evaluate("document.scrollingElement.scrollHeight <= innerHeight + 1")
    assert page.evaluate("document.scrollingElement.scrollWidth <= innerWidth + 1")
    checked = page.locator('[data-region], [data-answer], [data-answer] [data-field]')
    for i in range(checked.count()):
        el = checked.nth(i)
        assert el.evaluate("""e => {
          for (let n=e; n; n=n.parentElement) {
            const s=getComputedStyle(n);
            if (n.hidden || n.getAttribute('aria-hidden') === 'true' ||
                s.display === 'none' || s.visibility === 'hidden') return false;
          }
          return true;
        }""")
        box = el.bounding_box()
        assert box and box["width"] > 0 and box["height"] > 0
        assert -0.5 <= box["x"] and box["x"] + box["width"] <= w + 0.5
        assert -0.5 <= box["y"] and box["y"] + box["height"] <= h + 0.5
        assert el.evaluate("e => e.scrollHeight <= e.clientHeight + 1")
        assert el.evaluate("e => e.scrollWidth <= e.clientWidth + 1")

    # Exact schemas reject duplicates as well as omissions.
    for answer, expected in FIELDS.items():
        fields = page.locator(f'[data-answer="{answer}"] [data-field]')
        actual = [fields.nth(i).get_attribute("data-field") for i in range(fields.count())]
        assert len(actual) == len(set(actual)) and set(actual) == expected
        for i in range(fields.count()):
            field = fields.nth(i)
            assert field.locator(":scope > [data-label]").count() == 1
            assert field.locator(":scope > [data-value]").count() == 1
            assert field.locator(":scope > [data-value]").inner_text().strip()

    # Semantic values are part of the schema, not free display prose.
    system = page.locator('[data-answer="ON-G1"] [data-field]')
    for i in range(system.count()):
        assert system.nth(i).locator("[data-state]").get_attribute("data-state") in \
               {"up", "degraded", "down", "unknown"}
        assert int(system.nth(i).locator("[data-age-seconds]").get_attribute("data-age-seconds")) >= 0
    decision = values_for(page, "ON-G5")
    assert decision["decision.state"] in {"pending", "none"}
    assert decision["decision.eligibility"] in \
           {"observe", "inspect", "approve", "promote", "cancel", "retire", "none"}
    risk = values_for(page, "ON-G3")
    assert risk["risk.state"] in {"active", "all-clear"}
    if fixture.id == "F-7":
        assert risk == {"risk.identity": "none", "risk.state": "all-clear", "risk.action": "none"}
        assert decision == {"decision.state": "none", "decision.target": "none",
                            "decision.kind": "none", "decision.epoch": "42",
                            "decision.authority": "none", "decision.eligibility": "none"}
    trust = values_for(page, "ON-G6")
    assert trust["trust.projection_state"] in \
           {"current", "lagging", "stale", "failing", "unknown"}
    assert all(int(trust[key]) >= 0 for key in {
        "trust.degraded_count", "trust.stale_count", "trust.partial_count", "trust.unknown_count"
    })
    assert int(trust["trust.epoch"]) >= 0 and int(trust["trust.worst_age"]) >= 0
    run_counts = values_for(page, "ON-G2")
    assert all(int(value) >= 0 for value in run_counts.values())

    expected_rows = {"desktop": 8, "narrow": 7, "mobile": 3}[name]
    rows = page.locator('[data-region="R2"] [data-run-id]')
    assert rows.count() == expected_rows
    for i in range(rows.count()):
        row_fields = rows.nth(i).locator("[data-field]")
        actual = row_fields.evaluate_all("els => els.map(e => e.dataset.field)")
        assert len(actual) == len(set(actual)) and set(actual) == ROW_FIELDS
        assert all(row_fields.nth(j).locator(":scope > [data-value]").inner_text().strip()
                   for j in range(row_fields.count()))
        values = values_for(rows.nth(i))
        assert int(values["attempt.number"]) >= 1
        assert re.fullmatch(r"\d+/\d+", values["phase.progress"])
        assert values["lifecycle.state"] in {
            "queued", "running", "awaiting_approval", "verifying", "promotable", "promoting",
            "merged", "projecting", "published", "failed", "quarantined", "cancelled"
        }
        assert values["run.live"] in {"live", "not-live"}
        assert re.fullmatch(r"[0-9a-f]{7,40}|uncommitted", values["source.commit"])
        assert values["cost.provenance"] in {"metered", "estimated", "unknown", "reconciled"}
        assert values["attention.state"] in {"new", "active", "snoozed", "resolved", "stale", "none"}
        assert values["decision.eligibility"] in {
            "observe", "inspect", "approve", "promote", "cancel", "retire", "none"
        }
        assert values["decision.receipt"] in {"recorded", "missing"}
        for field, evidence_class in {
            "evidence.advisory": "advisory", "evidence.measured": "measured",
            "evidence.source": "source",
        }.items():
            assert rows.nth(i).locator(
                f'[data-field="{field}"]'
            ).get_attribute("data-evidence-class") == evidence_class
    marginals = page.locator('[data-answer="ON-G7"] [data-marginal]')
    assert marginals.count() == 4
    assert {marginals.nth(i).get_attribute("data-marginal") for i in range(4)} == \
           {"model", "condition", "provider", "lifecycle"}
    for i in range(4):
        buckets = marginals.nth(i).locator("[data-bucket]")
        actual = [buckets.nth(j).get_attribute("data-bucket") for j in range(buckets.count())]
        assert len(actual) == len(set(actual)) == 3
        assert set(actual) == {"top", "other", "unknown"}
        top = marginals.nth(i).locator('[data-bucket="top"]')
        assert top.get_attribute("data-category") and top.locator("[data-value]").inner_text().strip()

    money_risk = page.locator('[data-answer="ON-G4"] [data-money-risk]')
    assert money_risk.count() == (1 if fixture.id == "F-3" else 0)

    # Count rendered lines using computed line-height; identifiers may carry the
    # explicit middle-ellipsis contract, but required values may not clip.
    row_count = {"desktop": 8, "narrow": 7, "mobile": 3}[name]
    attention_count = {"desktop": 5, "narrow": 4, "mobile": 3}[name]
    clamp_groups = {
        '[data-region="R0"] [data-micro-row]': 4,
        '[data-region="R1"] [data-item-line]': attention_count * 2,
        '[data-region="R2"] [data-row-line]': row_count * 3,
        '[data-region="R3a"] [data-field]': 5,
        '[data-region="R3b"] [data-detail-line]': 2,
        '[data-region="R3c"] [data-marginal]': 4,
    }
    for selector, expected_count in clamp_groups.items():
        group = page.locator(selector)
        assert group.count() == expected_count
        assert group.evaluate_all("els => els.every(e => e.hasAttribute('data-max-lines'))")
    clamped = page.locator("[data-max-lines]")
    for i in range(clamped.count()):
        el = clamped.nth(i)
        assert rendered_line_count(el) <= int(el.get_attribute("data-max-lines"))
    required_values = page.locator('[data-region] [data-value]:not([data-identifier])')
    assert required_values.evaluate_all("els => els.every(e => e.hasAttribute('data-no-ellipsis'))")
    assert_no_clipped_required_values(required_values)

    # Walk all text under every resting region, including detailed R2 rows.
    assert_no_effective_contrast_violations(
        page.locator("[data-region]"), minimum=4.5, large_minimum=3.0
    )
```

### 10.8 HTML contrast probe

`assert_no_effective_contrast_violations` is not the SVG probe applied unchanged. It reuses only its
tested color parsing, alpha compositing, relative-luminance, and ratio functions, then walks HTML text
nodes under every resting region with a `TreeWalker`. For each non-whitespace text node it creates a `Range`
and rejects a zero/off-viewport box; reads the parent's computed `color`; composites computed
`backgroundColor` from the parent through ancestors until alpha=1; composites a translucent
foreground over that result; and applies 4.5:1 or 3:1 from computed font size/weight. A non-`none`
background image behind required text is a gate failure rather than an unmeasured guess. Forced-colors
uses the browser's post-emulation computed colors. The helper returns every failing selector, text,
foreground, effective background, and ratio, so zero failures is deterministic and actionable.

---

## 11. Open items

- **Implementation.** This document is the IA contract the facelift executes; the code change (and
   the `[data-*]` selector contract in §10.2) is a later phase. The gate script does not exist yet;
   `verify_control_room_rendering.py` is named in the direction's acceptance criteria. Section 10 is
   implementable without an IA decision: it fixes selectors, cardinalities, parent mapping, fixtures,
   ready state, viewport dimensions, exact schemas, clipping rules, and contrast mechanism.
- **Canonical contract reconciled.** The earlier mobile `ON-G7` omission and the narrow-desktop
  ticker fallback are both withdrawn: §4 and T4/T1 now answer all seven needs at 1440×900 and
  390×844 with no below-fold placement, so r1, the direction, and this document agree.
- **Fixtures.** `F-0`..`F-7` (§10.6) define the deterministic payload contract; the implementation must
   commit their JSON/SSE frames with the render gate and fail on any unmocked request.
- **Contrast automation.** Primitive 5 reuses the existing rendering gate's color parser, alpha
  compositing, and luminance functions for HTML text, including effective ancestor backgrounds and
  tinted status rows; dark, light, and forced-colors all run.
- **Provider composition** (`G-11`) depends on the control packet / ledger carrying provider per
  run; if a run lacks it, the count must show `unknown`, never be omitted.

---

## 12. Reconcile u0 — every JOB maps to a surface (`J1–J11`)

The operator's jobs are `control_room_ux_foundation.md` §2. Each job resolves to a resting region,
a drill-down region, a lens, or a control surface; **no job requires a surface not named here**, and
every surface here is defined in §2/§6.

| Job | Surface(s) | Element / selector | Alert item | Contract ref |
|---|---|---|---|---|
| `J1` glance (system, runs, risk, money, decision, trust, shape) | `R0`, `R1`, `R2`, `R3a`, `R3b`, `R3c` | the §4 canonical contract | `ON-A1..A6` | u0 DP1; §4 |
| `J2` triage a stalled/failed run | `R1` risk row → `R4a`, `R4c`, `R4b` | `[data-attention-class="risk"] [data-answer="ON-G3"]` → `[data-dock-region]` | `ON-A1` | u0 J2; u1 §2.2 |
| `J3` decide approve/cancel (and promote/retire) | `R1a` → `R4a` + `R4b` action band | `[data-field="decision.eligibility"]`, `[data-action="approve\|promote\|cancel\|retire"]` | `ON-A4` | u0 J3/DP4; u1 §2.2 |
| `J4` inspect evidence **and step timings** | `R4c` ladder + `R4d` timing + `L-WORKFORCE` | `[data-dock-region="evidence"]`, `[data-dock-region="timing"]`, `[data-lens="workforce"]` | — | u0 J4/DP3/DP7; u1 §3.3 |
| `J5` watch spend | `R3a` + `L-MONEY` (+ `R4c` cost rung) | `[data-field="money.*"]`, `[data-money-risk]` | `ON-A3` | u0 J5/DP5 |
| `J6` intervene per worker/session | `R4b` action band | `[data-action]` (`attach`/`detach`/`steer`/`interrupt`/`stop`/`respawn`/`rm`) | `ON-A5` | u0 J6; u1 §3.1 |
| `J7` audit what happened | `L-REGISTRY` + `AUDIT` + `R1c` | `[data-lens="registry"]` (canonical lineage), recording audit | `ON-A4`/process | u0 J7/DP6; u1 §5.1 ON-D4 |
| `J8` start / enqueue work | `QUEUE` | `[data-action="enqueue\|clear\|reinterleave"]` | — | u0 J8; u1 §3.1.D |
| `J9` route / choose the model | `R4a` routing inputs + `L-COMPOSITION` | routing fields beside the run (no peer board) | — | u0 J9; u1 §5.1 ON-D5 |
| `J10` manage background `claude` sessions | `L-SESSIONS` + `R4b` owned actions | `[data-action="start\|stop\|respawn\|rm\|steer\|logs"]` | — | u0 J10; u1 §3.1.B |
| `J11` record / close the session | `R1c` process health + `AUDIT` + `L-REGISTRY` | recording-coverage token; decision record | process | u0 §1.3 N6 |

**Completeness rule.** The union of the “Surface(s)” column equals the §14 palette minus
`SEARCH`/`SYSTEM`/`A11Y` (the cross-cutting accelerator, help link, and announcement channel). Every
job has an at-rest or one-selection answer; no job requires a board switch.

---

## 13. Reconcile u0 — every PRINCIPLE maps to elements (`DP1–DP10`)

The principles are `control_room_ux_foundation.md` §4. Each is enacted by named elements; the render
gate (§10 geometry, §15 parity) is how “enacted” is checked rather than asserted.

| Principle | Elements that enact it | Enforced by |
|---|---|---|
| `DP1` operator-first ranking | `[data-region="R0"/"R1"/"R2"/"R3a"/"R3b"/"R3c"]` + exactly-one `[data-answer="ON-G1..G7"]` | §4; G-1..G-15 |
| `DP2` agent-native addressable run | `R2 [data-run-id]` identity band; `R4a` `[data-dock-address]` | §10.2 row fields; G-13 |
| `DP3` typed evidence classes | `R2` `[data-evidence-class="advisory\|measured\|source"]`; `R4c` `[data-evidence-ladder]` | G-13; B-10 |
| `DP4` governed decisions + receipt | `R1a` decision; `[data-field="decision.eligibility"]`; `R4b` `[data-action-*]` + `[data-action-receipt]` | §15 P-2/E-6 |
| `DP5` money as bounded constraint | `R3a` five `money.*` + `[data-money-risk]`; `L-MONEY`; `R4c` cost rung | G-10 |
| `DP6` green never lies | `R0` `trust.*`; `R3b`; `[data-state]`/`[data-age-seconds]`; per-rung provenance | G-4; B-6; §8 |
| `DP7` marks with a budget | `R2` status rail; `R3c` `[data-marginal]`; `R4b` bounded feed; `L-WORKFORCE` (no per-card sparkline) | G-11; §4.5 restraint (direction) |
| `DP8` one token layer, accessible | CSS custom properties; `#theme-toggle`; color+glyph status; contrast | G-4/G-5; A-class |
| `DP9` build-less + accessible SVG | classic scripts; `[data-lens]`; theme-aware/`currentColor` SVG; `SYSTEM` link for `architecture.svg` | §12.2 no-build guardrail (direction) |
| `DP10` master–detail that persists | `R4` dock; `L-*` lenses; `SEARCH` accelerator; density ladder | A-2/A-3; E-1 |

---

## 14. Reconcile u2 — parity placement (the closed surface palette)

`experiments/research/control_room/parity_inventory.json` (`control-room-parity-inventory/v1`)
enumerates **every** old panel id (235), route (34), and client feed from `main`, and now carries a
`surface` on every item, endpoint, and capability. The builder refuses any value outside this closed
palette, and §15 makes the palette an acceptance check. The palette is:

| Surface | Meaning |
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
| `QUEUE` | enqueue/clear/reinterleave surface |
| `DOCS` | docs-health decision surface |
| `AUDIT` | recording/decision audit surface |
| `SEARCH` | global typed search / command accelerator |
| `SYSTEM` | system/help link (topology, architecture) |
| `A11Y` | single polite live region (announcement policy) |

**Panel → surface** (the default for each old panel; per-id overrides live in the inventory and are
exhaustive):

| Panel | Surface | Panel | Surface |
|---|---|---|---|
| `rail` | `R0` | `routing` | `R4a` |
| `detail` | `R4a` | `system` | `SEARCH` |
| `transcript` | `R4b` | `registry` | `L-REGISTRY` |
| `cell` | `R4b` | `queue` | `QUEUE` |
| `supervisor` | `R1` | `usage` | `R3a` |
| `design` / `claude` / `sessions` | `L-SESSIONS` | `announcer` | `A11Y` |
| `fleet` / `live-now` | `R2` | `flags` | `R1` |
| `docs-health` | `DOCS` | `status` | `R3a` |

**Capability → surface** (the ten named capabilities the repair requires):

| Capability | Surface |
|---|---|
| per-worker event stream | `R4b` |
| per-worker actions | `R4b` |
| workforce step timings | `R4d` + `L-WORKFORCE` (capability row records `R4d`) |
| boards (fleet/status/flags/sessions/routing) | `R0`/`R1`/`R2`/`R3*`/`L-*` |
| burn trace | `L-MONEY` |
| claude-agent controls | `L-SESSIONS` + `R4b` |
| queue controls | `QUEUE` |
| supervisor controls | `R1` + `R4b` |
| design controls | `L-SESSIONS` + `R4b` |
| cell panel | `R4b` (+ `R4a` facts) |

**Endpoint placement.** All 34 old routes survive server-side (`facelift_route: present`); the
facelift client wires only `GET /api/glance` and `GET /api/events`, so every other route records
`facelift_consumer: absent` and a target surface in the inventory. `GET /api/routing`,
`GET /api/registry`, `GET /api/registry/<entity_id>` are the three `replace-with-reason` dispositions
(§9); the other 30 are `re-house`.

---

## 15. Reconciled acceptance — restored regions and feature parity

The §10 classes (G/B/A/E) remain; the u3 reconciliation adds a fifth class **P (parity)** and extends
the R4 checks. All checks reuse the §10.1 primitives (present/unique, in-viewport, non-zero, no
scroll, contrast) and the §10.6 fixture discipline.

### 15.1 R4 drill-down checks (class G/D)

| # | Selectors | Assertion |
|---|---|---|
| `G-16` | dock open on a run | `[data-dock-region="address"]`, `"worker"`, `"evidence"`, `"timing"` each present exactly once; all inside the dock; the rest of the screen unchanged (§3.3) |
| `G-17` | `[data-attempt-feed]` | a `replay_complete` boundary then live entries; `[data-feed-entry]` count bounded; `[data-feed-follow]`/`[data-feed-pause]` present; exactly one feed open |
| `G-18` | `[data-dock-region="timing"] [data-timing]` | exact timing field set; each `[data-state]` in `measured,unknown`; an `unknown` row carries no fabricated `0`; a `measured` row carries source+age |
| `G-19` | `[data-action]` in `R4b` | each action chip carries target, authority, reversibility, confirmation (`none` or the phrase), and receipt; a disabled/ineligible action is not rendered as a live control |

### 15.2 Event/state checks (class E)

| # | Check | Pass condition |
|---|---|---|
| `E-6` | an action fires its endpoint | the request matches the u1 §3.1 endpoint; the response renders `[data-action-receipt]`; a no-op is idempotent |
| `E-7` | exactly one selected worker stream | selecting another worker closes the prior `[data-attempt-feed]` before opening the next |

### 15.3 Feature-parity checks (class P)

`u5_gate_semantic_parity` extends `verify_control_room_rendering.py` to consume
`parity_inventory.json` and assert, for **every** record (items, endpoints, capabilities):

1. **Placed** — the record carries a `surface` in the §14 palette (guaranteed at build time, re-checked).
2. **Present** — the surface/region exists in the running room (resting surfaces at rest; `R4*` and
   `L-*` after their documented selection/open path).
3. **Wired** — any record with an `old_endpoint` resolves to a live endpoint call (for actions) or a
   rendered query result (for reads); no inventory endpoint may remain consumer-absent after the repair.
4. **Non-empty** — a mapped surface renders data from the gate fixtures, or an **explicit
   documented empty-state** (`all clear`, `none pending`, `unknown`) where the inventory says so; a
   blank region is a failure.
5. **No silent drop** — every `facelift: dropped` id has a target surface and a passing
   present/wired/non-empty assertion; the gate reports any id with no element and no documented
   empty-state.

### 15.4 Blind comprehension additions (class B)

| # | Reviewer says | Carrying element |
|---|---|---|
| `B-12` | “I can watch this one agent and act on it from here.” | `R4b` event feed + action band with eligibility and receipt |
| `B-13` | “I can see where this run's time and money went, step by step.” | `R4d` timing rows (queue wait / service time / first token / tokens) |

### 15.5 Fixtures

`F-0`..`F-7` are unchanged. Add two forcing fixtures for the restored regions: `F-8` (a selected run
with a populated `R4b` feed and two eligible actions, one reversible and one typed-door) and `F-9`
(a selected run whose timing fields are partly `unknown`, proving the no-fabricated-zero rule). Both
extend the §10.6 `GET /api/glance` + SSE contract; no new route is required.

**Reconciliation exit.** With `§4` and `§3.2` unchanged, the glance contract stands; `R4b`/`R4d` and
`L-WORKFORCE` are explicit; every `u2` item is placed on the §14 palette; and class P makes “no
silent drops” a gate result rather than a claim. This is the contract `u4_implement` realizes and
`u5_gate_semantic_parity` proves.
