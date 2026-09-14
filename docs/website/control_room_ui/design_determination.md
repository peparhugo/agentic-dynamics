---
status: accepted
supersedes:
  - docs/website/control_room_ui/design_brief.md
  - docs/website/control_room_ui/design_evaluation.md
---

# Control Room UI — final design determination

> **Phase:** `d5_final_determination` (`wt_ui_determination`). **Question:** what is the Control
> Room's next design, decided by process — evidence, weighted criteria, three directions,
> adversarial review, and this final determination.
>
> **Inputs (read-only).** Evidence + criteria: `docs/website/control_room_ui/design_brief.md`
> (d1). Directions: `docs/website/control_room_ui/design_candidates.md` (d2). Evaluation +
> refinement: `docs/website/control_room_ui/design_evaluation.md` (d3). Adversarial review:
> `docs/reviews/control_room_design_determination_adversarial.md` (d4, findings `A-1..A-13`).
> Accepted direction `docs/research/control_room_direction.md` (§3.6, §4.5, §7, §8, §10, §12,
> §16, §18); canonical glance + palette `docs/research/control_room_ia.md` (§4 `ON-G1..G7`, §14
> closed palette, §15 class-P gate). Parity inventory
> `experiments/research/control_room/parity_inventory.json`. Current tree `HEAD` =
> `631be7d88`; `main` = `0a29f28b4`.
>
> **Claim discipline.** `[M]` measured in this repository (a `file:line`), `[C]` computed
> (arithmetic over `[M]`), `[H]` heuristic, `[X]` external observation at the pinned commit,
> `[P]` policy (controller/local decision). Every load-bearing number below was recomputed in
> this worktree; where it corrects a prior phase the `A-n` finding that drove the correction is
> named.
>
> **Status.** This document is the **single accepted determination**. It supersedes the d1
> brief's Part IV selection (Candidate C, 4.48 `[C]`) and the d3 evaluation's §0 selection
> (Candidate 1, 4.72 `[C]`), which are `status: superseded` as determinations and remain citable
> as evidence and scoring record. This document is decisions, not questions.

---

## 0. Final determination (executive)

**Winner — "The Scroll-Synthesized Instrument"** (d1 Candidate C ≡ d2 Candidate 1), corrected
weighted **4.52 / 5.00** `[C]`.
**Runner-up — "The Routed Room"** (d2 Candidate 2), **4.29 / 5.00** `[C]`.
**Third — "The Workforce Console"** (d2 Candidate 3), **3.76 / 5.00** `[C]`.

The room is **one document read top to bottom**. Its first viewport is the canonical no-scroll
glance (the seven `ON-G1..G7` answers in `R0`/`R1`/`R2`/`R3a/b/c`, `control_room_ia.md` §4
`[M]`), with the `R0` system/trust strip sticky. Below the fold the old dashboard's entire
working set is stacked as dense, labelled, measured **bands** — Fleet, Money, **Workforce**,
Trends, Boards, Sessions, System — plus the `R4a–d` inspector dock. Charts are real SVG+CSS
marks (`apps/control_room/static/charts.js`, `HISTORY_MAX=60` `[M]`), never a chart runtime.

**Why this direction survives the adversarial round.** The d4 review attacked the *scoring*,
not the design; every finding is a correction that this document makes, and the corrections do
not change the ordering under the stated decision rule (§2.4). The changes that moved the
scores were:

| Correction (finding) | Score change `[C]` |
|---|---|
| Step durations are already served by `GET /api/runs/<run_id>`; queue wait/service time by `GET /api/queue/sla` (`A-2`, `A-3`). Only `first_token_at` and the `cost_inference`/`cost_orchestration` split lack a carrier. | re-grounds C4/C7; no net deduction |
| The page-scroll ban is IA §4/§10 plus a shipped gate, not a direction-§18 phrasing nuance; ratifying it prices a gate amendment (`A-4`). | C7 5 → 4 |
| The aggregate timing route's enumeration/index, the `run_id`→ledger mapping, and the absent `queue_timings.jsonl` empty-state are unspecified (`A-10`). | C7 (same deduction) |
| `C8` measures conformance to the closed palette (IA §14), not old-dashboard fidelity; the 57 mutating-control ids have no demonstrated band home (`A-8`, `A-11`). | C8 5 → 4 |
| Candidate 3 omits the failure chart from its own chart table (`A-7`). | C3's chart coverage 5 → 4 |

Corrected matrix `[C]`:

| # | Criterion | Wt | **The Scroll-Synthesized Instrument** | The Routed Room | The Workforce Console |
|---|---|---|---|---|---|
| C1 | Immediate legibility | 14 | **5** | 4 | 3 |
| C2 | Density without wall-of-noise | 13 | 4 | **5** | 3 |
| C3 | Chart coverage | 13 | **5** | **5** | 4 |
| C4 | Workforce visibility | 13 | **5** | 4 | **5** |
| C5 | Scroll / navigation | 12 | **5** | 3 | 4 |
| C6 | Truthfulness | 15 | 4 | **5** | 4 |
| C7 | Feasibility with existing routes | 10 | **4** | 4 | 3 |
| C8 | Working-set fidelity (palette conformance) | 10 | **4** | 4 | 4 |
| | **Weighted total (0–5)** | **100** | **4.52** | **4.29** | **3.76** |

`4.52 = 5×.14 + 4×.13 + 5×.13 + 5×.13 + 5×.12 + 4×.15 + 4×.10 + 4×.10` `[C]`.

---

## 1. Adversarial findings — disposition (`A-1`..`A-13`)

Every d4 finding is folded in. "Lands where" names the section or the migration gate (§7).

| # | Sev | Finding (short) | Disposition | Lands where |
|---|---|---|---|---|
| A-1 | high | Parity inventory is byte-anchored to `349f06753` (sha `e26d36a3…`, 802-line `index.html`, 235 ids), not the declared old dashboard `1457b9299` (sha `c5742a98…`, 847 lines, **247 ids**) | Re-pin the parity unit and the prose to the byte-verified anchor; re-derive at `1457b9299` if that, not `349f06753`, is the intended old room; record the added Operations/Surfaces boards (12 ids) the inventory omits | §3.6; gate **P0** |
| A-2 | high | `queue_wait_ms`/`service_time_ms` are already served by `GET /api/queue/sla`; the winner's workforce tier does not need a new route for them | Partition signals by carrier; the new route is reserved for `first_token_at` + the cost split only | §4, §5; gate **P2** |
| A-3 | high | Per-attempt step durations already reach `GET /api/runs/<run_id>` (control DB `step_attempts.started_at/ended_at`) | Same; drop `started_at`/`ended_at`/duration from the new-route field list | §5; gate **P2** |
| A-4 | high | The scroll conflict is broader than "a §18.2 clarification": IA §4/§10 fix "no page scroll, no region scroll" and the shipped gate fails `chart-page-scroll` | Present D1 as an **amendment** to IA §4/§10 and to the gate, name the invalidated assertions, and price the gate rewrite in C7 | §2.3, §7 gate **P1** |
| A-5 | high | d1 pre-committed the winner; two `status: accepted` determinations disagree (4.48 vs 4.72) | Collapse to one accepted determination; this document is it; both predecessors marked `superseded`; each score delta is grounded | frontmatter; §2 |
| A-6 | high | The sensitivity analysis perturbs scores, never weights; three of the five brief elements score zero separation | Run a weight sweep with a stated rule; state that the brief's elements do not decide the winner; the win is carried by C5 | §2.4 |
| A-7 | medium | C3's "all three tie at 5" is false — Candidate 3 omits the failure chart | Re-score Candidate 3 chart coverage to 4; the chart set is delivered by C1/C2 | §0, §4 |
| A-8 | medium | C8 "old-dashboard fidelity" actually measures conformance to the facelift palette | Relabel C8 as **palette conformance** (IA §14); fix `surface_counts` (269) vs `items` (235) | §3.6; gate **P0** |
| A-9 | medium | The winner's headline chart mechanisms (`O6`, `HT3`) are v2-only and unpaired to a direction anchor | Pair each adopted v2 id to a direction § anchor; drop v2-only mechanisms | §4.1 |
| A-10 | medium | C7=5 hides the aggregate route's ledger enumeration and the absent `queue_timings.jsonl` | Specify enumeration/index, `run_id`→file mapping, refresh, and empty-state; re-score C7 | gate **P2** |
| A-11 | medium | The old room's 57 mutating control ids are dropped by the winner with no placement or typed door | Per-id placement table (5 families → band/dock + typed door) before C8 can pass | §3.5; gate **P5** |
| A-12 | low | The "old dashboard" rejection is quoted loosely and belongs to a superseded work order | Quote both exact lines, mark the reading as the open controller decision it is, and stop resting C8 on it | §3.6 |
| A-13 | low | Route counts (47/44 vs 34/36) are unreconciled and unreproducible | Name the counting command and scope; reconcile the two totals; exclude the static `GET /` | Appendix |

**What would falsify the winner — now run.** (a) The parity inventory is re-derived at a named
anchor (gate P0). (b) The workforce band is rendered from endpoints that exist at `HEAD`
(`/api/queue/sla`, `/api/runs/<id>`) — it is, so the "unreachable" gap narrative collapses to
two fields (gate P2). (c) The weight sweep is run (§2.4): the ordering flips only when the
scroll criterion weight is **zeroed** or C2/C6 weights are **tripled**.

---

## 2. Chosen direction — rationale table

Each criterion: the pass condition, **how the chosen direction satisfies it**, and the
**grounding**. Scores are the corrected vector (§0); runner-up differences are noted.

| Criterion (wt) | How satisfied | Grounding |
|---|---|---|
| **C1 Immediate legibility** (14) — a cold operator reads fleet health and the next decision from the first screen without interaction or scrolling | The first viewport **is** the glance: `R0` truth strip + `R1` attention + `R2` roster + `R3a/b/c` in the IA's own order, with `R0` `position: sticky`. Scroll reaches capability, never the seven answers | IA §4 `ON-G1→R0, ON-G2→R2, ON-G3→R1, ON-G4→R3a, ON-G5→R1, ON-G6→R0, ON-G7→R3c` (`control_room_ia.md:325-342` `[M]`); direction §16/§18.2; C1 beats C2 because C2's seven answers split between the global strip and one destination |
| **C2 Density without wall-of-noise** (13) — high information per pixel with a stated restraint budget; no KPI filler, no unconditional chart, no decorative pulse | Band grammar (one header per band carrying name + scope + source + age), rows separated by hairlines, density from alignment; enforced by a **deterministic DOM audit** (no `.kpi` selector, every chart carries its eight §7 fields, whole-page thesis-failure A/B). Scored 4, not 5, until that gate ships | Direction §4.4/§4.5 (`control_room_direction.md:505-511` `[M]`); d3 refinement D3; C2 is the only criterion the runner-up wins outright |
| **C3 Chart coverage** (13) — real SVG charts for step/phase duration, cost, throughput | Delivers all three plus queue timing, first-token, failure, dependency, provider-window, and the cost split; every chart a real SVG mark. C3 (Workforce Console) omits the failure chart and is scored 4 | `charts.js` catalog (`spend`/`throughput`/`failure`/`dependency`, `charts.js:39-76` `[M]`); direction §7/§10; d2 §4.3 vs §2.3/§3.3 |
| **C4 Workforce visibility** (13) — a surface shows measured per-model/per-attempt workload with `unknown` where unmeasured | A first-class **Workforce band** reading three tiers as one workforce (agents / workers / operators). Queue wait + service time come from an **existing** route; step durations from an **existing** route; only first-token and the cost split need the one additive route | `GET /api/queue/sla` → `_completions_block` (`control/projections/sla_queue.py:166-200`; `routes/analytics.py:40` `[M]`); `GET /api/runs/<run_id>` → `run_detail` (`services/operations.py:78-97` `[M]`); direction §3.6 `R4d`+`L-WORKFORCE` |
| **C5 Scroll / navigation** (12) — one arrangement per breakpoint; beyond-fold content reachable; drill-down is a push, not a hop; position survives refresh | Page scroll below the sticky masthead; the `R4a–d` inspector is a fixed dock that opens without moving the page; no density switch; one arrangement per breakpoint. This is the **load-bearing** score (§2.4) and the P0 ratification | Direction §3.2/§12; d3 D1; C1 wins this outright (C2's destination switch is the board-hop the criterion penalises) |
| **C6 Truthfulness** (15) — every consequential value carries source + age + scope; missing is `unknown`, never `0`; per-value, not one global footer | Per-band provenance header; sticky masthead keeps `ON-G1`/`ON-G6` on screen; per-value source/age/measured-estimated-unknown chips sharing `charts.js`'s null-not-zero parser; a failed band shows its last-success age. Scored 4, not 5, until the stale/failed fixtures are part of the gate | Direction §8 (`control_room_direction.md:592-610` `[M]`); `charts.js:90-99` `[M]`; runner-up wins C6 because routed pages localise provenance more naturally |
| **C7 Feasibility with existing routes** (10) — no new endpoint class, no new mutating route; additions are read-only | Most workforce data is served **today** (`/api/queue/sla`, `/api/runs/<id>`); the only additive route is a `GET` for first-token + the cost split over already-durable artifacts. Scored 4 because the aggregate enumeration/index, the `run_id`→ledger mapping, the missing `queue_timings.jsonl` empty-state, and the P1 gate amendment are all unbuilt | `control/control_db.py:957-976` `[M]`; `runtime/queue_timings.py:34` `[M]`; direction §18 scope ("no new mutating route class") |
| **C8 Working-set fidelity — palette conformance** (10) — every old capability is placed, present, wired, non-empty, or an explicit empty-state; no silent drop | All 235 inventory items map to a fixed band or dock home by their IA §14 surface, in the old destination order. Scored 4 until the parity unit is re-anchored (`A-1`), the count mismatch is fixed (`A-8`), and the 57 mutating controls have a demonstrated home (`A-11`) | `parity_inventory.json` (235 items; sum of `surface_counts` = 269 `[C]`); IA §14/§15; direction §3.6 parity hard-rule |

### 2.1 What is preserved from each candidate

- **From Candidate A (restore old):** the complete working set and every interaction — 235 ids,
  per-worker actions, typed doors, all boards — as bands, not as a three-column cockpit.
- **From Candidate B (current room):** the `ON-G1..G7` no-scroll first viewport, the
  truth/provenance contract, the `R4a–d` dock, the SVG chart module, and the render gate.
- **New in this direction:** the below-fold scroll, the step/phase-duration chart, the measured
  Workforce band, the one additive read-only route (two fields), and the first-viewport geometry
  guard.

### 2.2 The correction the design makes to the accepted direction

The direction's §18.2 and IA §4/§10 fix **no page scroll and no region scroll** and the shipped
gate enforces it (`scripts/verify_control_room_rendering.py:984`, `chart-page-scroll` `[M]`).
The determination **amends** that contract to a **first-viewport** property: all seven
answers inside the initial viewport with no page or region scroll; page scroll permitted
**below** it; `R0` sticky. This is not a clarification of §18 — it is an explicit amendment to
IA §4/§10 and requires a diff to that document and to the gate (gate **P1**). The ruling is
made here; the signature is the controller's (§8).

### 2.3 The C7 deduction, in full

The d3 evaluation scored C1's feasibility 5 on "the only server change is the single shared
read-only route". That hides four real costs `[M]`:

1. an aggregate mode must enumerate the per-run workflow ledgers under
   `experiments/results/workflows/<spec>/<ts>_<run_id>.json` (`scripts/run_workflow.py:1290-1301`)
   and map a control `run_id` to a ledger filename (a glob);
2. `experiments/results/queue_timings.jsonl` is **absent in this checkout** and is created only
   at runtime (`runtime/queue_timings.py:34`) — the route must render an honest empty population;
3. the route is only needed for `first_token_at` and `cost_inference`/`cost_orchestration`;
4. the P1 gate amendment is a real edit to an accepted document.

Hence C7 = 4. The direction remains the cheapest of the three: C2 adds a fragment router; C3
adds a tri-pane state model plus three simultaneous scroll regions.

### 2.4 Weight sensitivity and the decision rule `[C]`

The 4.52 is robust under the stated rule. Weights are held fixed at d1's; we perturb them
**after** scoring and report every ordering flip. The rule: **the winner must hold under (i)
any single-criterion weight in ±50 % of base, and (ii) the "brief-elements" emphasis
(`C3`,`C4`,`C5` doubled).** A scenario that zeroes the criterion carrying the design's defining
mechanism is treated as a failed premise, not a counter-example.

| Scenario | C1 | C2 | C3 | Leader |
|---|---|---|---|---|
| Base (corrected scores) | **4.52** | 4.29 | 3.76 | C1 |
| Brief elements `C3`/`C4`/`C5` × 2 | **4.65** | 4.22 | 3.92 | C1 |
| `C5` weight → 0 | 4.45 | **4.47** | 3.73 | C2 (flip) |
| `C5` → 0, `C4` × 2 | **4.52** | 4.41 | 3.89 | C1 |
| Joint extreme: C1 worst (C2,C6→3) vs C2 best (C5→4,C7→5,C8→5) | 4.24 | **4.61** | 3.76 | C2 |
| Single-axis flips within ×3 | — | `C2`×3, `C6`×3 | — | C1 otherwise |

**Reading.** The only single-axis zeroing flip is `C5` (scroll/navigation) — the criterion the
direction's defining mechanism occupies. That is the honest statement the d4 review demanded:
the winner is carried by its **arrangement** (C1/C5), not by chart or workforce coverage, which
is a tie. The joint extreme reverses the order, but it assumes three free upgrades bought by
the one paid mechanism (a router); a router-free C2 would have no deep-link to score. Under the
decision rule the winner holds; if the scroll amendment (P1) is **not** ratifiable, the
determination's premise fails and the field collapses to the Routed Room.

---

## 3. Final page/board inventory

### 3.1 Old-dashboard survivors (7 boards + System + Detail → bands/dock)

The old room's seven destinations `["fleet","status","flags","sessions","routing",
"operations","surfaces"]` + System overflow (`apps/control_room/static/shell.js:26` @
`1457b9299` `[M]`) and the transversal Detail surface survive as capability, re-homed by the
closed palette (IA §14). The band order is the old destination order.

| Old board / surface | Target band | Palette surface(s) | Disposition |
|---|---|---|---|
| Fleet (`#board-fleet`) | **Fleet** band | `R2`, `L-FLEET` | re-house |
| Status (`#board-status`) | **Money** band | `R3a`, `L-MONEY` | re-house |
| Flags (`#board-flags`) | **Boards** band | `R1`, `L-ATTENTION` | re-house |
| Sessions (`#board-sessions`) | **Sessions** band | `L-SESSIONS`, `R4b` | re-house |
| Routing (`#board-routing`) | **Boards** band | `R4a`, `L-COMPOSITION` | replace-with-reason (routing drawer → composed surface) |
| Operations (`#board-operations`) | **Boards** band + inspector dock | `R4c`, `AUDIT` | re-house **— absent from the parity inventory; gate P0** |
| Surfaces (`#board-surfaces`) | **Boards** band | `L-REGISTRY`, `DOCS`, `QUEUE`, `AUDIT`, `L-COMPOSITION` | re-house |
| System sheet (`#system-sheet`) | **System** band | `SEARCH`, `L-REGISTRY`, `QUEUE`, `SYSTEM` | replace-with-reason |
| Detail surface (`#detail-surface`) | **Inspector dock** `R4a–d` | `R4a`/`R4b`/`R4c`/`R4d` | re-house |

Inventory totals `[M]`: 214 `re-house`, 20 `replace-with-reason` (the routing + registry +
system-sheet families), 1 `preserve` (`theme-toggle`).

### 3.2 Additions (net-new, no old item)

| Addition | Palette surface | Why | Grounding |
|---|---|---|---|
| **Workforce** band (three tiers) | `L-WORKFORCE`, `R4d` | the brief's *workforce* + *step durations* | direction §3.6; parity `L-WORKFORCE` = 0 old items `[M]` |
| **Trends** band | `L-COMPOSITION` | hosts the four catalog charts + new builders | `charts.js:39-76` `[M]` |
| Sticky `R0` masthead | `R0` | make trust/epoch un-scrollable (D4) | direction §8 |
| Band anchor nav + skip links | `A11Y` | deep-link a band; keyboard reach | direction §12.1; `T1` `[X]` |
| Read-only timing route (first-token + cost split) | — (data plane) | the two fields with no carrier | gate **P2** |
| `L-HEALTH`, `R3c`, `R4c`, `SYSTEM`, `L-FLEET` placements | palette | palette surfaces the facelift left without an old item | `summary.surfaces_without_old_item` `[M]` |

### 3.3 Cuts (old affordances deliberately not carried)

| Cut | Reason | Grounding |
|---|---|---|
| Per-card sparklines (`createSparkline`) | removed for want of one shared scale; the capability survives as a band chart | direction §4.3/§7 (`control_room_direction.md:471,559` `[M]`) |
| Density switch (`setDensity`) | one arrangement per breakpoint; a density matrix multiplies the render gate | direction §12; v2 `Y1` DO-NOT-COPY `[X]` |
| `adoptRegions` shared-region re-parenting | a shared region moved between boards is a navigation artifact; the strip lives once | `shell.js:102-109` `[M]`; one writer per surface |
| Board-visibility model (one board at a time) | replaced by the band order; the single-screen lens workbench is the rejected baseline | d3 `§0.3` `[M]` |
| Chart runtime / canvas / `<progress>` | SVG+CSS micro-marks only | direction §10 |
| `architecture.svg` | referenced by no static file at the old commit | `design_brief.md` §1.1 `[M]` |
| Blinking counters / gamification / animated rhythm | decorative motion; observe-only rails never steer | v2 §4.3 `[X]`; rules AUTHORITY |

### 3.4 Palette placement — all IA §14 surfaces

`R0` masthead · `R1` attention rows in `R2`/Boards · `R2` Fleet band · `R3a` Money band ·
`R3b` health detail (Money) · `R3c` composition (System) · `R4a–d` inspector dock ·
`L-MONEY` Money · `L-COMPOSITION` Trends · `L-FLEET` Fleet · `L-ATTENTION` Boards ·
`L-HEALTH` System · `L-WORKFORCE` Workforce · `L-REGISTRY` Boards/System · `L-SESSIONS`
Sessions · `QUEUE`/`DOCS`/`AUDIT`/`SEARCH`/`SYSTEM` Boards/System · `A11Y` masthead live
region. A candidate that leaves a palette surface unplaced fails class-P.

### 3.5 Mutating-control placement (`A-11`) — 57 ids, five families

The old room's five mutating-control families each lost every member in the facelift. Each id
gets a band/dock home and a governed action; irreversible acts keep a typed door and a receipt
(direction §3.6/§12.2). `facelift_members_dropped` counts from `parity_inventory.json`
`capabilities` `[M]`.

| Family (members) | Home | Action band / door |
|---|---|---|
| `supervisor-controls` (11) | `R1` + `R4b` | steer (governed); interrupt behind typed door `INTERRUPT <session_id>` (`routes/flags.py:68` `[M]`); receipt |
| `claude-agent-controls` (16) | `L-SESSIONS` + `R4b` | start / stop / respawn / rm / steer / daemon-stop, each a governed call through the mutation trust gate; confirm + receipt |
| `cell-panel` (11) | `R4b` (+ `R4a` facts) | watch/detach, copy session, pause/resume, follow, docs-health approve; eligibility at rest, full door one selection away |
| `queue-controls` (7) | `QUEUE` (System band) | enqueue / clear / reinterleave, each idempotent (`POST /api/experiments` — loopback + same-origin + JSON + size-cap + `Idempotency-Key`, `routes/telemetry.py:395-425` `[M]`); receipt |
| `design-controls` (12) | `L-SESSIONS` + `R4b` | create / input / save / run; interrupt (confirm); draft validation + receipt |

No new mutating route is added; every door already exists at `HEAD`. A per-id placement table
is the fidelity evidence and is exercised by the class-P gate (gate **P5**).

### 3.6 Parity unit, anchor, and the old-dashboard reading (`A-1`, `A-8`, `A-12`, `A-13`)

- **Anchor.** The inventory's `inputs.old_index.sha256` is
  `e26d36a3886c362b77f21826181a81437bb62181081b2cde2aa514cf0eb67064`, byte-identical to
  `git show 349f06753:apps/control_room/static/index.html` (802 lines, **235 unique ids**);
  the prose pins the old dashboard to `1457b9299`, whose `index.html` is
  `c5742a98…` (847 lines, **247 unique ids**) `[M]`. The "847-line / 235-id" framing is a
  chimera. This determination re-pins the parity unit to the **byte-verified** anchor and
  requires re-derivation at `1457b9299` (which adds the `operations` and `surfaces` boards, 12
  ids) if that commit is the intended old room (gate **P0**).
- **Count mismatch.** `sum(summary.surface_counts) = 269` while `len(items) = 235` `[C]`; the
  builder's summary is inconsistent with its own item list. Fix `sum(surface_counts) ==
  len(items)` before class-P (gate **P0**).
- **C8 unit.** The gate's unit is the **closed palette** (IA §14), not the old board list;
  eight palette surfaces have no old item `[M]`. C8 is therefore *palette conformance*, and the
  determination stops calling it "old-dashboard fidelity".
- **The exact quotes.** The pre-facelift work order
  `workflows/repository/control_room_ui_rebuild.yaml` says, in its `question`, "a layer on top
  of the clunk" (`:5`) and, in `why_rebuild`, "a layer of shit on top of the dashboard" (`:26`)
  `[M]`; it is superseded and its `authority` points at the old `docs/control_room_ui/design.md`.
  "Old dashboard as base" therefore rests on the **open controller decision** (now made here:
  working-set fidelity, not DOM reuse), not on that work order.

---

## 4. Chart specification

Every chart states direction §7's eight fields (question, decision, baseline/scope, sampling
rule, textual equivalent, fallback, budget) and obeys §10's SVG rules (`viewBox`,
`currentColor`, real `<text>`, `<title>`/role for informative marks). A missing value is a
**gap**, never `0`; fewer than two samples is an explicit empty state; no chart on the first
viewport. Four charts already exist in `charts.js` (`spend`, `throughput`, `failure`,
`dependency` `[M]`); five of the nine entries below (step duration, queue span, first-token,
provider-window, cost split) are new builders.

| # | Chart | Purpose (question → decision) | Data source | Placement | SVG approach |
|---|---|---|---|---|---|
| 1 | **Step / phase duration** | Where does the workforce spend time? → rebalance or unblock a model/step | `GET /api/runs/<run_id>` attempts (`started_at`/`ended_at`, `control_db.py:957-976`; `operations.py:78-97`) `[M]` | Workforce band | Horizontal per-model p50/p95 bars, **log scale**, explicit `UNKNOWN` height; `viewBox`+`currentColor`; zero-percent = an explicit empty bar |
| 2 | **Queue timing** (wait vs service) | Queue-bound or model-bound? → add workers or inspect the model | `GET /api/queue/sla` `recent_completions` (`sla_queue.py:166-200`; `analytics.py:40`) `[M]` | Workforce band | Stacked span bars per attempt on one shared time axis; textual table alongside |
| 3 | **First-token latency** | How fast does the model start answering? → route or downgrade | **new** `GET /api/timings?run=` over the run ledger (`first_token_at`, `opencode.py:558` `[M]`) | Workforce band | p50/p95 bars on the **same scale** as #1 |
| 4 | **Cost / burn** | Trending to the cap? → throttle, raise a cap, or run | `GET /api/matrix` `reported_cost`/`history_capped`; `/api/subscription-usage` | Money band | One shared-scale line (`charts.js` `spend`); cap as a bounded quantity + progress, not a free-floating mark |
| 5 | **Throughput** | Moving or backing up? → add workers / re-interleave / investigate | browser-session ring, or `/api/queue/sla` `recent_completions` when served | Trends band | Step lines (`charts.js` `throughput`); scope label states session vs served |
| 6 | **Failure** | Accumulating or clearing? → inspect/cancel/quarantine | `/api/matrix` / `/api/glance` failed counts | Trends band | Step line, zero baseline (`charts.js` `failure`); fallback = the `ON-G3` risk answer |
| 7 | **Dependency health** | Are the dependencies healthy? → pause promotion/re-run a projector | `/api/projections`, `/api/flags` | Trends band | Bounded bars + status grid (`charts.js` `dependency`); gauge only because a maximum (lag 0) exists |
| 8 | **Provider-window pace** | How full is the 5h/7d window? → pace the fleet | usage/settlement ledger (`/api/subscription-usage`) | Money band | Bounded quantity + progress (direction §7 priority 4; `Y2` `[X]`) |
| 9 | **Cost split** (inference vs orchestration) | Where do the dollars go? → attribute spend | **new** `GET /api/timings?run=` over the run ledger (`cost_inference`/`cost_orchestration`, `efficiency.py:249-272` `[M]`) | Money band | Two-segment proportional bar on one scale; `unknown` segment when absent |

### 4.1 v2 mechanism pairing (`A-9`)

v2 is `status: proposed`, 479 lines, on `wt_facelift_review` @ `87559ef66`, **not on `main`**
`[M]`. Every v2 id the design adopts is paired to an accepted-direction anchor; a v2-only
mechanism is dropped.

| v2 id | Mechanism | Direction basis | Disposition |
|---|---|---|---|
| `O6` | log-scale duration bar with `UNKNOWN` height | §7 priority 2/3 (bounded causal timeline; one shared scale) + §3.6 `R4d` step timings | **ADOPT** (chart #1) |
| `HT3` | shared-axis span bars | §7 priority 2 (bounded causal timeline / waterfall) | **ADOPT** (chart #2) |
| `T1` | deep-linkable event id | §9 drill-down ("no board hopping") | **ADAPT** as band anchors |
| `H3` | fingerprint + keep-last-data on disconnect | §8 truth contract (last-success age) | **ADAPT** |
| `C7` | queue-unavailable honesty | §8 ("green never lies") | **ADAPT** |
| `Y2` | provider window/pace | §7 priority 4 (bounded quantity) | **ADAPT** (chart #8) |
| `Y1` | per-user density switch | — (conflicts §12) | **DROPPED** |
| `N1` | synced-hover anomaly chart wall | — (conflicts §4.5) | **DROPPED** |
| `C10` | new POST verify route by default | §18 ("no new mutating route class") | **DROPPED** |

---

## 5. Workforce view specification

The brief's parenthetical is read as **three tiers of one workforce**, all in the **Workforce
band** (below the fold) and mirrored per-attempt in the `R4d` dock. Each field renders
`measured` or `unknown` **with a reason** — never a fabricated `0`.

| Tier | Who | Fields shown | Source | Carrier |
|---|---|---|---|---|
| **Agents** | agent sessions / cells (opencode), design sessions | session id, model, workdir, current phase/tool, attempt no, live state; **per-attempt step duration**; first-token latency; tokens by answer/explanation; cost provenance | `/api/matrix`; `GET /api/runs/<run_id>` attempts; `/api/quality` narration | duration **exists**; first-token = new route; narration = `/api/quality` |
| **Workers** | Redis queue workers + control-plane lease holders | worker health (`unhealthy_workers`), occupancy, concurrency leases, queue depth, **queue-wait/service-time distributions (p50/p95 by model)** | control packet; `GET /api/queue/sla` `recent_completions`; `leased_at` | **exists** |
| **Operators** | humans in the loop (controller, AIO) | pending decisions (`awaiting_approvals`), promotable runs, live grants, docs-health signer, decision records | control packet; `/api/flags`; `/api/decisions`; `/api/docs-health` | **exists** |

**Surface split.** The fleet aggregate is the **Workforce band**; the per-attempt timing grid
is the **`R4d`** dock region. No per-card sparkline on the resting roster; the duration mark
fires only inside the Workforce band (`O6` relocation, §4.1). The band is **below the first
viewport**, so the §16 pixel budget is untouched.

**Honesty rules.** A field the route cannot supply renders the literal `unknown` plus a reason
(the null-not-zero parser, `charts.js:90-99` `[M]`); an unmeasured distribution shows sample
counts (`n_with_queue_wait`); a failed fetch shows the last-success age, never a blank.

---

## 6. Visual language specification

- **Type.** System UI sans for labels/prose; **monospace** for identity (session token,
  worktree, command) and every numeric/unit (direction §4.1 identity band). Type floor IA G-5:
  ≥13 px desktop, ≥12 px mobile, labels ≥11 px.
- **Colour.** A semantic token set only — `surface`, `line`, `text-primary`, `text-muted`, plus
  a small status set. **State = glyph + word + colour** (never colour-only); the single
  brand-orange cue is reserved for `awaiting_promotion`. Light/dark/forced-colors via system
  colors + `currentColor`. Theme remains a `preserve` item; a multi-theme product is not.
- **Density.** Dense, banded, aligned. Each band begins with one header line carrying
  **name + scope + source + observation age**; hairline row rules; density from alignment, not
  card chrome. The §4.5 thesis-failure rule applies **per band and to the whole page**.
- **Provenance.** Per-band header + sticky `R0` masthead + per-value chip (source/age/
  measured-estimated-unknown) + last-success-on-failure. A missing value is `unknown`, never
  `0`; stale never reads as all-clear.
- **Motion.** State transitions only, ≈100–240 ms, decelerating; `prefers-reduced-motion`
  collapses; no decorative pulse or glow.
- **Charts.** SVG+CSS micro-marks only; `viewBox`; `currentColor`; real `<text>`; `<title>`/
  role for informative marks; `aria-hidden` for decorative; forced-colours safe (direction §10).
- **A11y.** WCAG 2.2 AA; semantic table controls; one transition-only polite live region; band
  skip links; focus lands on the band heading; keyboard operation.

---

## 7. Migration order from the old dashboard (phases + gates)

Implementation order is by dependency. **No phase may expand the authority model, add a runtime
dependency, add a mutating route, or reuse the single-screen lens shell.** Each gate is the
acceptance that proves the phase.

| Phase | Work | Gate (acceptance) |
|---|---|---|
| **P0 — Parity ground truth** | Re-derive/re-pin the parity inventory to a named anchor; add the `operations`/`surfaces` boards; fix `sum(summary.surface_counts) == len(items)` | `parity_inventory.inputs.old_index.sha256 == sha256(git show <named-anchor>:apps/control_room/static/index.html)`; the prose id count equals that commit's count; `sum(surface_counts) == len(items)` |
| **P1 — First-viewport shell + scroll gate** | Amend IA §4/§10 (first-viewport no-scroll, below-fold scroll) and `verify_control_room_rendering.py`'s page-scroll assertion; add a below-fold band fixture; sticky `R0` | At 1440×900 / 1024×768 / 390×844: all seven `ON-G1..G7` present, non-zero, fully inside the initial viewport with zero page/region scroll; a below-fold fixture renders every band non-empty; the diff to IA §4/§10 and the gate exists |
| **P2 — Read-only timing route** | `GET /api/timings` (per-run + aggregate) over the run ledger for **first-token + cost split only**; reuse `/api/queue/sla` and `/api/runs/<id>` for queue/service and step durations; specify ledger enumeration, `run_id`→file mapping, refresh, and the missing-`queue_timings.jsonl` empty-state | Route is `GET`-only and writes nothing; a real-ledger fixture shows `first_token`/cost split as `measured` (or `unknown` + reason); an absent `queue_timings.jsonl` renders an honest empty population, not an error or a zero; control DB schema untouched |
| **P3 — Chart set** | Ship charts #1–#9 with §7's eight fields; pair every v2 id to a direction anchor (§4.1) | Every chart states all eight §7 fields; SVG-only rules hold; failure chart present; no unconditional/ambient chart; <2 samples = explicit empty state |
| **P4 — Workforce band** | Wire the three tiers to the P2 carriers; build the `R4d` grid from `/api/runs/<id>` + the per-run timing route | Per-model p50/p95 queue wait/service time/first token render from measured data; unmeasured = `unknown` + reason; band is below the first viewport |
| **P5 — Parity class-P + control placement** | Run the class-P gate over all inventory items; demonstrate the 57-control placement table with typed doors + receipts | Every item present/wired/non-empty (or documented empty-state); every mutating control has a band/dock home and a door; `routes_dropped: 0`; no silent drop |
| **P6 — Visual language + wall guard** | Apply the visual-language spec; ship the deterministic DOM audit (per-band provenance header, no `.kpi`, eight §7 fields per chart, whole-page thesis-failure A/B) | Stale fixture shows ages + explicit `unknown`, never green-over-stale; failed band shows last-success age; the wall audit passes |

**Not in scope for any phase:** DOM-copying the old room; a router/state-machine; a chart
runtime; a density switch; automatic actuation; per-card sparklines on the roster.

---

## 8. Authority-level items only

**Design-level authority items: none (empty).** This document decides every design question the
process surfaced; there are no open questions returned to the controller.

The following are **permanence acts**, not design questions, and are the only items that require
the controller's signature:

1. **Ratify the P1 amendment** to `control_room_ia.md` §4/§10 and the render gate (scroll is a
   first-viewport property; below-fold scroll + sticky `R0`).
2. **Ratify the P2 read-only route** (one additive `GET`; no schema change, no mutating route).
3. **Merge** the resulting `feature/*` work through the permanence gate.

---

## Appendix — pins, route-count reconciliation, and citation key

**Pins.**

- Old dashboard (declared in prior prose): `1457b9299` — `apps/control_room/static/index.html`
  (847 lines, 247 unique ids) `[M]`.
- Parity inventory byte-anchor: `349f06753` — `apps/control_room/static/index.html` (802 lines,
  235 unique ids), `inputs.old_index.sha256 = e26d36a3…` `[M]`.
- Current tree: `HEAD` = `631be7d88`; `main` = `0a29f28b4`.
- v2 synthesis: `docs/research/control_room_ui_reference_synthesis_v2.md` @ `87559ef66`
  (branch `wt_facelift_review`, not on `main`).

**Route-count reconciliation (`A-13`).**

| Scope | Count | Command `[M]` |
|---|---|---|
| Route **registrations** at `1457b9299` | **44** | `for f in $(git ls-tree -r --name-only 1457b9299 -- apps/control_room/routes \| grep '\.py$'); do git show 1457b9299:"$f" \| grep -cE 'app\.(get\|post\|put\|delete\|patch)\('; done` |
| Route **registrations** at `HEAD` | **47** (incl. the static `GET /`, `routes/index.py:23`) | same shape against `HEAD`; `sum = 8+9+1+7+2+3+2+1+2+2+2+8` |
| **Canonical endpoints**, old / facelift | **34 / 36** | `parity_inventory.json` `summary.old_routes`/`facelift_routes`; `routes_dropped_by_facelift: 0` |
| Mutating (`POST`) registrations at `HEAD` | **17** | `grep -rnE 'app\.(post\|put\|delete\|patch)\(' apps/control_room/routes/*.py` |

The two figures count different scopes: registrations include the static `/` and method
variants; canonical endpoints are the inventory's de-duplicated route set. C7's "no new endpoint
class" is applied to API endpoints and excludes the static `/`.

**Load-bearing anchors.**

- Glance contract: `docs/research/control_room_ia.md:33-34`, `:325-342`, `:549` `[M]`.
- Gate (page scroll): `scripts/verify_control_room_rendering.py:984` (`chart-page-scroll`) `[M]`.
- Charts: `apps/control_room/static/charts.js:35` (`HISTORY_MAX=60`), `:39-76` (four charts),
  `:90-99` (null-not-zero) `[M]`.
- Timing carriers: `control/projections/sla_queue.py:166-200`; `apps/control_room/routes/analytics.py:40`;
  `control/control_db.py:957-976`; `apps/control_room/services/operations.py:78-97`;
  `runtime/queue_timings.py:34` `[M]`.
- Typed doors: `apps/control_room/routes/flags.py:68` (`INTERRUPT <session_id>`);
  `apps/control_room/routes/telemetry.py:395-425` (`POST /api/experiments`, idempotent) `[M]`.
- Parity: `experiments/research/control_room/parity_inventory.json` (235 items; 214/20/1;
  10 capabilities; `sum(surface_counts)=269` `[C]`).
- Rejection quotes: `workflows/repository/control_room_ui_rebuild.yaml:5` and `:26` `[M]`.
