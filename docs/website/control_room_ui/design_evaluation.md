---
status: accepted
---

# Control Room UI — weighted evaluation, adversarial review, and final determination

> **Phase:** determination (`wt_ui_determination`). **Question:** which of the three candidate
> design directions should become the Control Room's next design — decided by process, scored
> against the eight weighted criteria fixed in the evidence phase, attacked, and then refined on
> its own weakest dimensions.
>
> **Inputs (read-only):** the evidence-and-criteria pack `docs/website/control_room_ui/design_brief.md`
> (phase `d1_evidence_and_criteria`); the three candidate directions
> `docs/website/control_room_ui/design_candidates.md` (phase `d2_directions`); the accepted direction
> `docs/research/control_room_direction.md` (status: accepted); the canonical glance contract
> `docs/research/control_room_ia.md` §4 (`ON-G1..G7`) and closed palette §14; the v2 reference
> synthesis `docs/research/control_room_ui_reference_synthesis_v2.md` @ `87559ef66` (branch
> `wt_facelift_review`, **not on `main`**); the old dashboard at commit `1457b9299`; the parity
> inventory `experiments/research/control_room/parity_inventory.json`
> (`control-room-parity-inventory/v1`); the current tree at `HEAD` = `main`.
>
> **Claim discipline.** `[M]` measured in this repository (a `file:line` anchor); `[C]` computed
> (arithmetic over `[M]`); `[X]` external observation at the pinned commit (v2 mechanism IDs +
> anchors); `[P]` policy — a controller/local decision, never external consensus.
>
> **Output contract.** This document is **determinations, not questions**. Every open decision named
> by the candidates phase (`design_candidates.md` §6) is decided here. The only things left to the
> controller are the **permanence acts** (merging a branch, amending the accepted direction) — those
> are gates, not design questions.

---

## 0. Determination (executive)

**Winner: Candidate 1 — "The Scroll-Synthesized Instrument" — weighted 4.72 / 5.**
**Runner-up: Candidate 2 — "The Routed Room" — weighted 4.29 / 5.**
**Third: Candidate 3 — "The Workforce Console" — weighted 3.89 / 5.**

The room becomes **one document you read top to bottom**. Its **first viewport is the canonical
no-scroll glance** (`R0` truth strip, `R1` attention, `R2` roster, `R3a/b/c` ledger — i.e. the seven
`ON-G1..G7` answers, `control_room_ia.md` §4 `[M]`), with the `R0` system/trust strip **sticky** so
scope and freshness never scroll away. Below the fold, the old dashboard's entire working set is
stacked as dense, labelled, measured **bands** — Fleet, Money, **Workforce**, Trends, Boards,
Sessions, System — plus the `R4a–d` inspector dock. Charts are real SVG+CSS marks
(`apps/control_room/static/charts.js`, `HISTORY_MAX=60`, `[M]`), never a chart runtime. The
Workforce band is built from the now-measured ledger timings (G-40/G-30/G-31/G-41) reached through
**one additive read-only route**.

Why C1 over C2: both answer all five brief elements, but C1 is the **lightest** to build and gate
(no router/state machine), keeps the glance contract intact **by construction**, and makes the parity
class-P gate cheapest (every old id has a fixed band home). C2's deep-linkable destinations are
genuinely good, but its destination switch is exactly the **board-hop** criterion C5 penalises, and
its hash router is new navigation code the no-build constraint must carry. Why not C3: the Workforce
Console is the strongest *workforce* answer, but it is the **hardest to keep `ON-G1..G7`-complete**
at rest and the most complex to gate — and the brief does not ask for the workforce to be the spine,
only for it to be visible and measured.

The refinement round (§6) then decided, **highest-uncertainty first**, the six things that held C1
back: **D1** the scroll contract (first-viewport no-scroll gate + below-fold scroll, ratifying a
narrowing of direction §18); **D2** the read-only timing exposure (option (a): one GET over the run
ledger / `queue_timings.jsonl`, not a schema change); **D3** the wall-of-noise guard (a hard band
grammar + deterministic DOM audit); **D4** provenance in a long page (per-band headers + sticky
masthead + per-value chips); **D5** "old dashboard as base" = working-set fidelity; **D6** v2 stays a
pinned branch-local evidence reference.

---

## 1. Method

### 1.1 The criteria are d1's, unchanged

The eight criteria and their weights are exactly those fixed by `design_brief.md` Part II `[P]/[M]`.
They are re-stated in §3 so this document is self-contained, but they are **not** re-derived here —
re-weighting after seeing the scores would be a process violation, so the weights are held fixed.

| # | Criterion | Weight |
|---|---|---|
| C1 | Immediate legibility | 14 |
| C2 | Information density without wall-of-noise | 13 |
| C3 | Chart coverage: step/phase duration, cost, throughput | 13 |
| C4 | Workforce visibility | 13 |
| C5 | Scroll / navigation | 12 |
| C6 | Truthfulness (provenance / no fabricated value) | 15 |
| C7 | Feasibility with existing routes | 10 |
| C8 | Working-set fidelity to the old dashboard | 10 |
| | **Total** | **100** |

### 1.2 Scoring rule

Scores are **1 (fails) … 5 (excellent)**. The weighted total is `Σ (score × weight) / 5`, on a
**0–5** scale (so a perfect 5s across all criteria = 5.00). [C]

### 1.3 Hard invariants are gates, not scores

`design_candidates.md` §0.4 lists ten shared invariants (truth/provenance contract, glance contract,
no new mutating route, no build step, one arrangement per breakpoint, motion budget, a11y bar, parity
hard-rule, SVG authoring, chart standard) `[P]`. These are the **floor**: a candidate that violates
one is a **hard failure**, not a deduction. In this evaluation **no candidate violates an invariant**
— all three were composed inside them — so the matrix scores *how well each arrangement sustains the
invariants under load*, which is where the candidates actually differ (e.g. C6 scores the difficulty
of keeping per-value provenance attached in a long page vs. across routed pages).

### 1.4 Evidence basis

Every score cites the candidate's own section (`design_candidates.md` §2/§3/§4) and a load-bearing
anchor. The criteria themselves cite their controller policy, reference mechanism, and truth contract
in `design_brief.md` Part II `[P]/[X]/[M]`. The shared evidence base is
`design_candidates.md` §1: the old dashboard (`1457b9299`, 235 ids, 44 route registrations,
34 canonical endpoints, per `parity_inventory.json` `[M]`), the current room (`HEAD`, 47 route
registrations — measured `[M]`), the closed palette (`control_room_ia.md` §14 `[M]/[P]`), the
measured writers (`design_candidates.md` §1.4 `[M]`), and the v2 mechanisms (`[X]`).

### 1.5 What the candidates are

For reference, from `design_candidates.md` §0.6 `[M]`:

| | Candidate 1 | Candidate 2 | Candidate 3 |
|---|---|---|---|
| **Name** | The Scroll-Synthesized Instrument | The Routed Room | The Workforce Console |
| **Navigation model** | Linear vertical scroll over one document | Multi-page hash router over destinations | Persistent tri-pane (navigator · workspace · dock) |
| **Unit of reach** | A band (fixed position) | A page (a destination) | A selection (an object) |
| **Scroll** | Page scroll below the masthead | Page scroll per destination | Region scroll per pane |
| **Old-dashboard base** | Working set as bands | The 7 boards + System as literal pages | Working set as navigator groups + workspace subjects |
| **Strongest element** | scroll + parity completeness | deep-linkable destinations + old nav fidelity | workforce + measured step durations |
| **Weakest element** | wall-of-noise risk | board-hopping risk | glance-room risk |

None of the three is the single-screen shell (`HEAD`); the shell is only the baseline they depart
from (`design_candidates.md` §0.3 `[M]`).

---

## 2. The weighted decision matrix

Scoring: 1 (fails) … 5 (excellent). Weighted total = `Σ (score × weight) / 5`, 0–5 scale. [C]

| # | Criterion | Wt | **C1 Scroll-Synthesized** | C2 Routed Room | C3 Workforce Console | Criterion winner |
|---|---|---|---|---|---|---|
| C1 | Immediate legibility | 14 | **5** | 4 | 3 | **C1** |
| C2 | Density w/o wall-of-noise | 13 | 4 | **5** | 3 | C2 |
| C3 | Chart coverage (duration/cost/throughput) | 13 | **5** | **5** | **5** | tie |
| C4 | Workforce visibility | 13 | **5** | 4 | **5** | tie C1/C3 |
| C5 | Scroll / navigation | 12 | **5** | 3 | 4 | **C1** |
| C6 | Truthfulness | 15 | 4 | **5** | 4 | C2 |
| C7 | Feasibility with existing routes | 10 | **5** | 4 | 3 | **C1** |
| C8 | Working-set fidelity | 10 | **5** | 4 | 4 | **C1** |
| | **Weighted total (0–5)** | **100** | **4.72** | **4.29** | **3.89** | **C1** |

**Computation.** [C]

- C1 = `5×.14 + 4×.13 + 5×.13 + 5×.13 + 5×.12 + 4×.15 + 5×.10 + 5×.10`
  = `.70 + .52 + .65 + .65 + .60 + .60 + .50 + .50` = **4.72**.
- C2 = `4×.14 + 5×.13 + 5×.13 + 4×.13 + 3×.12 + 5×.15 + 4×.10 + 4×.10`
  = `.56 + .65 + .65 + .52 + .36 + .75 + .40 + .40` = **4.29**.
- C3 = `3×.14 + 3×.13 + 5×.13 + 5×.13 + 4×.12 + 4×.15 + 3×.10 + 4×.10`
  = `.42 + .39 + .65 + .65 + .48 + .60 + .30 + .40` = **3.89**.

**Reading.** C1 wins or ties **five of the eight** criteria, including four of the five
brief-weighted criteria (C3, C4, C5, C8) and the second-heaviest truth criterion is only one point
behind. C2 wins the other two (C2, C6) but loses the scroll criterion outright on its own defining
mechanism (the destination switch is a board-hop). C3 wins only the two chart/workforce criteria and
is last on legibility, density, and feasibility.

---

## 3. Per-criterion reasoning

Each subsection restates the pass condition (from `design_brief.md` Part II `[P]`), then scores each
candidate with the evidence that moves the score.

### C1 — Immediate legibility (weight 14)

**Pass condition `[P]`.** A cold operator can read the fleet's health and the next decision from the
first screen **without interaction or scrolling** to find them. Authority: direction §16/§18.2
("no page scroll", all `ON-G1..G7`); reference: Temporal T3 counts-as-filters, OpenHands O2
icon+label+colour `[X]`; contract: `ON-G1..G7` (`control_room_ia.md` §4) `[M]`.

| Candidate | Score | Reasoning |
|---|---|---|
| C1 | **5** | The first viewport *is* the glance: `R0`+`R1`+`R2`+`R3a/b/c` in the IA's own order, with the `R0` system/trust strip sticky (`design_candidates.md` §2.1 `[M]`). Scroll reaches capability, never the seven answers. This is the literal reading of the pass condition. |
| C2 | 4 | The global truth strip is persistent and the resting page `#/fleet` must separately pass the glance (`design_candidates.md` §3.1 `[M]`). But the seven answers are split between the global strip and the `#/fleet` body, so a cold operator on any *other* destination sees only `ON-G1`/`ON-G6` and must navigate to `#/fleet` to recover the rest. Legible at rest, not at every address. |
| C3 | 3 | The pinned gutters are designed to keep `ON-G1..G7` visible, but three simultaneous panes at 1440×900 and the collapse to a stacked subject→evidence order at mobile make the first-viewport completeness the **crux to test** (the candidate says so itself, `design_candidates.md` §4.1 `[M]`). Region scroll in the first viewport is the riskiest relaxation of the pass condition. |

**Criterion winner: C1.**

### C2 — Information density without wall-of-noise (weight 13)

**Pass condition `[P]`.** High information per pixel with a stated restraint budget; no KPI-tile
filler, no unconditional chart, no decorative pulse. Authority: direction §4.5 restraint budget and
the thesis-failure rule ("truth bar + alert cards + service table + KPI rail" = failure,
`control_room_direction.md:505-511` `[M]`); reference: Langfuse L3 comfort-band split `[X]`,
DO-NOT-COPY Y1 density switch (v2 §4.3) `[P]`.

| Candidate | Score | Reasoning |
|---|---|---|
| C1 | 4 | A single long page is the **easiest place to reintroduce a dashboard wall** — the candidate names this as its own central risk (`design_candidates.md` §2.7 `[M]`). It can be held by the band grammar (one header + provenance per band; density from alignment), but the guard does not exist yet, so the arrangement is discounted one point. This is a refinement target (§6 D3). |
| C2 | **5** | Charts live on the page whose question they answer, page headers are "never a KPI-tile row" (`design_candidates.md` §3.5 `[M]`), and the risk is spread across pages rather than concentrated in one scroll. The routed layout most naturally satisfies §7's "no unconditional default". |
| C3 | 3 | The console is deliberately the highest density of the three (`design_candidates.md` §4.5 `[M]`), which is exactly the posture §4.5's thesis-failure rule warns against, and it carries the most chart-bearing surfaces (workspace + dock) — the `N1` chart-wall ban is most at risk here. |

**Criterion winner: C2.**

### C3 — Chart coverage: step/phase duration, cost, throughput (weight 13)

**Pass condition `[P]`.** Real SVG charts exist for **cost, throughput, and step/phase duration**,
each meeting direction §7's eight statements (question, decision, baseline/scope, sampling rule,
textual equivalent, fallback, budget) and §10's SVG rules (`viewBox`, `currentColor`, real `<text>`,
role/title). Authority: the work item ("charts/SVG", "step durations") and direction §7/§10 `[P]`;
reference: Hatchet HT3 trace timeline, OpenHands O6 log-scale duration bar, lazyagent Y3 sparkline
`[X]`; contract: `charts.js`, G-40 timings, §8 `[M]`.

| Candidate | Score | Reasoning |
|---|---|---|
| C1 | **5** | Delivers all three named charts — step/phase duration (Workforce band, log-scale per-model bars with an explicit `UNKNOWN` height, O6), queue timing (shared-axis span bars, HT3), first-token latency, cost/burn on one shared scale, throughput (browser-session or `/api/queue/sla` `recent_completions`), failure, dependency, and provider window (`design_candidates.md` §2.3 `[M]`). Every card keeps its eight §7 fields; missing value is a gap. |
| C2 | **5** | The same chart set, plus a **phase waterfall** and a **composition mini-map** on `#/run/<id>` (`design_candidates.md` §3.3 `[X]/[M]`). The extra charts are grounded in direction §7 priority 2 (bounded causal timeline) and HT2, so they are not decoration. |
| C3 | **5** | The same set plus retry-rate / tokens-by-model in the workforce workspace, with charts attached to the workspace subject and the dock and none ambient (`design_candidates.md` §4.3 `[M]`). |

**Criterion winner: all three tie at 5.** Chart coverage is not the differentiator — all three
reuse `charts.js` and add the same two new builders; the difference is *where* they live, and C1/C3
pay for their location in C2 (density) and C1 (legibility). A tie is left as a tie rather than
manufacturing a distinction the evidence does not support.

### C4 — Workforce visibility (weight 13)

**Pass condition `[P]`.** A workforce surface (region or lens) shows measured per-model/per-attempt
workload: queue wait, service time, first-token, retry, tokens by model, and step durations — with
`unknown` where unmeasured. Authority: the work item ("workforce", "step durations") and direction
§3.6 `R4d` + `L-WORKFORCE` `[P]`; reference: lazyagent Y2 provider window/pace, Dagu D4 per-node
table `[X]`; contract: `L-WORKFORCE` = 0 old items (net-new, `parity_inventory.json` `[M]`), the
G-40/G-30/G-31 writers (`design_candidates.md` §1.4 `[M]`).

| Candidate | Score | Reasoning |
|---|---|---|
| C1 | **5** | A first-class **Workforce band** with the three tiers read as one workforce — agents (per-attempt step timings, mirrors `R4d`), workers (queue/lease health + queue-wait/service-time distributions), operators (pending decisions, promotable runs, grants, docs-health signer) — all sourced from measured fields (`design_candidates.md` §2.4 `[M]`). Visible without drilling. |
| C2 | 4 | The same three tiers on a dedicated `#/workforce` page (`design_candidates.md` §3.4 `[M]`). Strong, but the workforce is **reached by navigating** to its destination rather than visible from the resting view; the brief says "visible", not "reachable". |
| C3 | **5** | The workforce **is** the console: the three tiers are simultaneously the navigator groups, the workspace subjects, and a shared aggregate, and the workforce is the default workspace (`design_candidates.md` §4.4 `[M]`). The strongest possible workforce answer. |

**Criterion winner: tie C1/C3.**

### C5 — Scroll / navigation (weight 12)

**Pass condition `[P]`.** One deliberate arrangement per breakpoint; content beyond the fold is
reachable by scroll; **drill-down is a push, not a board-hop**; selection/scroll position survives a
refresh. Authority: the work item ("scroll") and direction §3.2/§12 (one arrangement per breakpoint)
`[P]`; reference: herdr-portal H2 click-to-land, Temporal T1 deep-linkable event id, v2 H3
fingerprint+reconnect `[X]`; contract: direction §18.2 no-page-scroll (ratified/narrowed in §6 D1).

| Candidate | Score | Reasoning |
|---|---|---|
| C1 | **5** | Page scroll below the masthead is the brief's literal ask; the `R4a–d` inspector is a **fixed dock that opens without moving the page**, and `H3` (fingerprint + keep-last-data + preserved scroll) protects position on reconnect (`design_candidates.md` §2.1 `[M]`). Selection is a dock, not a hop. No density switch (Y1), one arrangement per breakpoint. |
| C2 | 3 | Page scroll per destination is fine, and `#/run/<id>` is a true deep-link push (`T1`). But **switching between destinations is the board-hop the pass condition names** — the exact navigation the accepted direction warns against (`control_room_direction.md` §3.2/§9) — and a hash router is new navigation state to gate. Its best feature (deep-linkable runs) does not offset the hop. |
| C3 | 4 | Region scroll per pane plus a persistent navigator is a legitimate scroll model, and object+workspace live in the fragment (`T1`). But region scroll **inside the first viewport** is the riskiest relaxation of the glance contract, and the mobile collapse changes the arrangement materially. Meets the brief; pays in C1 risk. |

**Criterion winner: C1.**

### C6 — Truthfulness (provenance / no fabricated value) (weight 15)

**Pass condition `[P]`.** Every consequential value carries source + age + scope; a missing value is
`unknown`, never `0`; stale/degraded never reads as all-clear; **per-value provenance, not one
global footer**. Authority: direction §8 truth contract ("green never lies",
`control_room_direction.md:592-610` `[M]`); reference: DashClaw C7 queue-unavailable honesty, C11
liveness honesty, OpenHands O1 degrade-on-unknown `[X]`; contract: `control_status.safe_actions`,
`glance.py`, `charts.js`'s null-not-zero parser (`charts.js:90-99` `[M]`).

| Candidate | Score | Reasoning |
|---|---|---|
| C1 | 4 | The truth contract is honored (null-not-zero parsing is shared code, the candidate mandates per-band scope/source/age headers, `design_candidates.md` §2.5 `[M]`). It is discounted one point because a long document is where provenance most easily degrades into one footer and where a stale band can read as an all-clear. This is a refinement target (§6 D4). |
| C2 | **5** | Each page carries its own provenance header and the global footer keeps only scope/connection/epoch/degraded; provenance travels with the page that owns the value (`design_candidates.md` §3.5 `[M]`). The routed structure most naturally satisfies "per-value, not one global footer". |
| C3 | 4 | Pane headers carry scope + source + age, but three simultaneous surfaces must each carry provenance, and a persistent navigator makes the "which value is stale" question harder to keep answered at a glance. Same discount as C1 for a different reason. |

**Criterion winner: C2.**

### C7 — Feasibility with existing routes (weight 10)

**Pass condition `[P]`.** The design needs **no new endpoint class** and **no new mutating route**;
any addition is read-only and reuses a registered route or the already-written ledger. Authority:
the work item and direction §18 scope ("No new mutating route class") `[P]`; reference: DashClaw C10
stateless verify (gated) `[X]`; contract: **47 route registrations at `HEAD`**, **44 at
`1457b9299`**, `routes_dropped: 0` (`parity_inventory.json` `[M]`, re-measured here `[M]`).

| Candidate | Score | Reasoning |
|---|---|---|
| C1 | **5** | No navigation state machine and no router: the only server change is the single shared read-only timing route (§6 D2). The band grammar is CSS/DOM only. The cheapest of the three to build and gate. |
| C2 | 4 | The same single read-only route, plus a **fragment router** — new navigation code the no-build constraint must carry and the render gate must test. No new mutating route, but more new surface than C1. |
| C3 | 3 | The same route, plus a tri-pane state model, a persistent navigator, object+workspace fragment state, and three simultaneous scroll regions. The most new code and the most gating surface; the regional scroll adds a11y and focus-management obligations. |

**Criterion winner: C1.**

### C8 — Working-set fidelity to the old dashboard (weight 10)

**Pass condition `[P]`.** Every one of the old room's capabilities (235 ids, 10 capability classes)
is placed, present, wired, and non-empty — or an explicit documented empty-state. No silent drop.
Authority: the work item ("old dashboard as base") and direction §3.6 parity hard-rule `[P]`;
reference: DashClaw C1/C2 multi-tab decision object + separate containment lifecycle `[X]`; contract:
`parity_inventory.json` (235 items: 214 `re-house`, 20 `replace-with-reason`, 1 `preserve`; 10
capabilities) `[M]`.

| Candidate | Score | Reasoning |
|---|---|---|
| C1 | **5** | Every old id maps to a **fixed band home** by its inventory `surface`; the band order *is* the old destination order (`design_candidates.md` §2.2 `[M]`). Because each capability has exactly one position, the class-P gate is a deterministic per-band check. The cheapest path to a clean parity pass. |
| C2 | 4 | Literal old board boundaries survive as navigation, which is the most *recognizable* fidelity. But the gate's unit is the closed **surface palette** (`control_room_ia.md` §14 `[M]`), not the old board list, and C2 merges Operations + Surfaces into one `#/operations` page and adds two destinations (`#/workforce`, `#/run/<id>`) — so one old boundary is lost and the mapping is not one-to-one. |
| C3 | 4 | Navigator groups + workspace subjects place every palette surface (`design_candidates.md` §4.2 `[M]`), but the same policy replaces page boundaries with object selection, so fidelity is by surface, not by board — equal to C2 in gate terms. |

**Criterion winner: C1.**

---

## 4. Sensitivity and stability

The ordering `C1 > C2 > C3` is stable under single-axis perturbations but is **worth stating
honestly**, because C1's win is carried by its *arrangement* (C1/C5/C7/C8), not by its raw feature
coverage (C3 is a tie). [C]

**Single-axis.** Downgrading C1 by one point on any single criterion leaves a worst case of
`4.72 − 0.15 = 4.57` (its heaviest, C6). Upgrading C2 by one point on its best criterion leaves a
best case of `4.29 + 0.12 = 4.41` (C5). **C1 remains first with ≥0.16 margin in every single-axis
case.** [C]

**Joint extremes.** C1's true worst case is both its weak scores dropping to 3 (C2 and C6):
`4.72 − 0.13 − 0.15 = 4.44`. C2's best case is three simultaneous upgrades (C5→4, C7→5, C8→5):
`4.29 + 0.12 + 0.10 + 0.10 = 4.61`. Taken as independent moves that would reverse the ordering — but
they are **not independent**: they are the *same* mechanism seen three ways. C2 buys its deep-link
(C5) and literal-board fidelity (C8) by adding a router/state layer (C7) — the cost **is** the
feature. A C2 that eliminated the router cost would have no deep-links to score. The joint extreme
assumes three free upgrades from one paid mechanism, which is incoherent. The ordering stands.

**C2 > C3 is robust.** C3 would need `+0.72` to reach C2's 4.29 — more than its three most plausible
upgrades (C1→4 = +.14, C2→4 = +.13, C7→4 = +.10 = +0.37). [C]

**The genuinely load-bearing score is C5 (scroll/navigation).** If the scroll contract were not
ratified at all, C1 and C2 would both lose their defining mechanism and the field would collapse to
C3 or the rejected single-screen shell. That is why the scroll decision is **D1**, the first and
highest-uncertainty refinement (§6).

---

## 5. Adversarial review

Format: severity · the claim under attack · required correction · the acceptance that proves the
correction. This round attacks the **selection itself** (why C1, and what would falsify it), not the
input candidates, which were attacked in `design_brief.md` Part V.

| # | Sev | Claim under attack | Required correction | Acceptance |
|---|---|---|---|---|
| **EV-1** | high | "C1's page scroll is simply non-compliant with direction §18.2." | §18 acceptance criterion 2 is a **resting-screen / first-viewport** contract (all seven answers inside the initial viewport with no page or region scroll, `control_room_direction.md:876-880` `[M]`), not a whole-document ban. The determination narrows it to the first viewport and ratifies scroll below (D1). | The render gate proves all seven `ON-G1..G7` present, non-zero, fully inside the initial viewport at 1440×900/1024×768/390×844 with **zero page scroll to reach them**, **and** a below-fold fixture proves the bands render non-empty. |
| **EV-2** | high | "C1's long page will collapse into a KPI/chart wall." | The band grammar (D3) plus the §4.5 thesis-failure rule applied **per band and to the whole page** (`control_room_direction.md:505-511` `[M]`). A long page is the easiest place to fail this, which is exactly why the guard must be a hard gate, not a guideline. | A deterministic DOM audit fails any band lacking a provenance header, any `.kpi`/ambient-chart selector, or any chart missing one of its eight §7 fields; the blind A/B is run on the whole page. |
| **EV-3** | high | "C1's workforce band renders measured durations today." | False as stated: the control DB `step_attempts` table carries only `started_at`/`ended_at`/scalar `tokens`/`cost_usd`/`exit_code`/`error` (`control_db.py:959-976` `[M]`), so G-40/G-41/G-30/G-31 are written to the run ledger / `queue_timings.jsonl` but reach **no route** (`design_candidates.md` §1.4 `[M]`). C1 must add one read-only exposure and render `unknown` with a reason where a field is absent (D2). | A fixture run with a real ledger shows `queue_wait`/`service_time`/`first_token`/`cost_inference` as `measured` (or `unknown` with an explicit reason); the route is `GET`-only and writes nothing. |
| **EV-4** | high | "A long page can carry one global provenance footer." | The pass condition forbids it: **per-value provenance, not one global footer** (C6 `[P]`). The sticky masthead keeps `ON-G1`/`ON-G6` (system + epoch/trust) on screen through the whole scroll; every band carries its own scope/source/age header; a failed band shows its last-success age (D4). | A stale fixture shows ages and explicit `unknown` and never green-over-stale; a failed-band fixture shows last-success age, not a blank or a zero. |
| **EV-5** | medium | "Old dashboard as base means copying its DOM (a point for C2's literal pages)." | The repository's only literal `old dashboard` statement **rejects** DOM-copy ("a layer on top of the clunk", `control_room_ui_rebuild.yaml:24-29` `[M]`); the requirement is **working-set fidelity** measured against the 235-id parity inventory (D5). C2's literal pages are recognizable, not more compliant. | The class-P gate passes all 235 items present/wired/non-empty (or documented empty-state); no `re-skin` claim survives; `routes_dropped: 0`. |
| **EV-6** | medium | "C1's in-page anchor nav is free." | It is a **second navigation contract** (band anchors + sticky masthead) that must be gated: skip links for keyboard users, stable deep-link targets, focus not lost on jump, and the arrangement unchanged across breakpoints (direction §12.1 `[P]`). | A keyboard/a11y fixture exercises every band skip link and anchor deep-link; focus lands on the band heading; forced-colors and reduced-motion hold. |
| **EV-7** | medium | "The Trends charts can claim server history." | Unless served from `/api/queue/sla` `recent_completions` (`sla_queue.py:103-200` `[M]`), the charts are **browser-session** with an explicit scope label (`charts.js:35` `HISTORY_MAX=60` `[M]`); a missing projection is an explicit error state, never a blank implying zero. | Each chart card states its scope and source; the below-fold fixture includes a chart with no samples → explicit empty/error state, not a flat line at zero. |
| **EV-8** | medium | "C3 (or C2) is 'more like the old dashboard', so it should win C8." | The gate's unit is the closed **surface palette** (`control_room_ia.md` §14 `[M]`), not old board boundaries; all three place every palette surface. C1's one-position-per-capability mapping is simply the easiest to prove. | The class-P gate is run surface-by-surface for all three in the abstract; C1's per-band mapping requires no reconciliation of merged boards. |
| **EV-9** | low | "v2 is authoritative because it is newest." | v2 is `status: proposed` and **not on `main`** (`design_candidates.md` §1 `[M]`); the accepted authority is `control_room_direction.md`. Every adopted v2 mechanism must cite a **direction basis**; a v2-only mechanism is dropped (D6). | Each adopted v2 mechanism ID in the final design is paired with a direction anchor; no v2-only adoption survives. |
| **EV-10** | low | "The selection needs another round of refinement." | Exactly **one** refinement round is run (the work item's instruction); it decides every open question the candidates phase surfaced. What remains is the permanence gate (merging, amending the direction), which is a controller act, not an open design question. | This document contains zero open questions; the only remaining items are P0 permanence acts listed in §8. |

---

## 6. Refinement round — the winner's weakest dimensions

**Trigger.** C1's two lowest scores are **C2 (density / wall-of-noise, 4)** and **C6 (truthfulness,
4)**; its highest-uncertainty dependency is the **scroll ratification** (C5, which is also the
load-bearing score in §4). This section runs **one** refinement round over those dimensions and the
four open decisions the candidates phase carried (`design_candidates.md` §6), **highest-uncertainty
first**. Each item is a **determination**, not a question.

Uncertainty order and the decision made: **D1** scroll (highest — a P0 policy narrowing),
**D2** timing exposure (high — blocks C3/C4 and must be chosen before the charts can be built),
**D3** wall-of-noise guard (medium-high — the C2 weakness), **D4** provenance in a long page
(medium — the C6 weakness), **D5** "old dashboard as base" (medium-low — already constrained by the
parity hard-rule), **D6** v2 status (low — evidence provenance).

### D1 — Scroll contract (decided: first-viewport no-scroll gate + below-fold scroll)

**Decision.** Adopt the **glance-gate / below-fold-scroll** contract for C1:

1. **Hard gate (unchanged from direction §18.2).** At **1440×900, 1024×768, and 390×844**, all seven
   `ON-G1..G7` answer anchors are present, non-zero, and **fully inside the initial viewport with no
   page scroll and no region scroll required to reach them**. The `control_room_ia.md` §4 map
   (`ON-G1→R0, ON-G2→R2, ON-G3→R1, ON-G4→R3a, ON-G5→R1, ON-G6→R0, ON-G7→R3c`) is the implementation
   contract `[M]`.
2. **Below the first viewport.** Page scroll is permitted. Region scroll is permitted only inside
   below-fold bands and inside the detail dock. The `R0` system/trust strip is `position: sticky` and
   remains on screen through the scroll.
3. **One arrangement per breakpoint.** No density switch, no persisted resize (v2 `Y1`/`L3`
   DO-NOT-COPY).

**Why this and not strict no-scroll.** The brief names **scroll** as an outcome element. The purpose
of direction §18.2 is that the seven answers require **no interaction or scrolling to reach them** —
a *first-viewport* property, which this contract preserves exactly. Strict no-scroll makes the
brief's scroll element unsatisfiable and forces the single-screen shell, which the candidates phase
explicitly forbids reusing (`design_candidates.md` §0.3 `[M]`). The determination therefore reads
§18 acceptance criterion 2 as a first-viewport condition and **narrows it explicitly**; it does not
repeal it.

**What it changes.** Direction §18 acceptance criterion 2's wording becomes "…inside the initial
viewport with no page scroll and no region scroll" **scoped to the first viewport**; the render gate
adds a **below-fold band fixture** alongside the existing above-fold glance fixture.

**This is a P0 ratification.** The wording amendment to the accepted direction, and its merge, are
controller permanence acts (§8). The determination is that the amendment is the intended reading;
implementation proceeds behind the gate.

**Acceptance.** Both fixtures pass at all three breakpoints (glance fully inside the initial viewport,
zero scroll needed; bands non-empty below it).

### D2 — Read-only timing exposure (decided: option (a), one GET over the existing artifacts)

**Decision.** Option **(a)**: **one additive, read-only `GET`** over the already-written durable
artifacts. Concretely, `GET /api/timings`, with two modes:

- per-run: `GET /api/timings?run=<run_id>` — the per-attempt rows that feed the `R4d` grid;
- aggregate: `GET /api/timings?aggregate=1&window=<n>` — the per-model distributions that feed the
  Workforce band.

Source: the workflow run ledger JSON and `queue_timings.jsonl` — the same append-only artifacts
`/api/queue/sla` already reads (`runtime/queue_timings.py:63-118` `[M]`;
`control/projections/sla_queue.py:103-200` `[M]`). Fields exposed per attempt:
`queue_wait_ms`, `service_time_ms`, `first_token_at`, `started_at`/`ended_at`/duration,
`retries`, `tokens{answer,explanation,reasoning}`, `cost{inference,orchestration}`, `cost_source`,
`exit_code`, `test_executed_success`. A field that is absent renders `null` **plus a `reason`** —
never `0` (the §8 truth contract).

**Why (a) and not (b) an additive control-DB read model.** The control DB is a single-writer store
whose `step_attempts` table has no columns for these fields (`control_db.py:959-976` `[M]`);
option (b) requires a schema migration plus writer changes to populate it — heavier, riskier, and
collision-prone with the orchestrator's single-writer rule. Option (a) reads artifacts that are
already durable and append-only, is read-only **by construction**, is trivially reversible, and
honors direction §18's "no new mutating route class" `[P]`. A new **read** registration is not a new
**class**.

**Why a dedicated route rather than extending `/api/runs/<id>` or `/api/queue/sla`.** `/api/runs`
is control-DB-sourced and cannot carry these fields without (b); `/api/queue/sla` carries only
*settled* rows and only the queue/SLA slice. A dedicated read projection cleanly separates
**ledger-sourced timings** from **DB-sourced run state**, and can serve both the aggregate band and
the per-attempt dock from one contract.

**Acceptance.** The route is `GET`-only and writes nothing; a fixture run with a real ledger shows
`measured` values for all fields; absent fields render `unknown` with a reason; the control DB schema
is untouched.

### D3 — Wall-of-noise guard (decided: hard band grammar + deterministic DOM audit)

*Refines C2 (density, 4 → gate-enforced).*

**Decision.** Adopt the **band grammar** as a hard render contract, and enforce it with a
deterministic DOM audit:

1. **Band header.** Every band begins with one header line carrying its **name + scope + source +
   observation age** (direction §8 `[M]`).
2. **Row grammar.** Rows are separated by hairline rules; density comes from **alignment**, not card
   chrome (direction §4.4 `[P]`). No default card field, no repeated bright status marks.
3. **No KPI-tile row.** Anywhere. Counts appear as age-qualified filters/links, never as a bare
   stale delta (`T3` ADAPT; v2 A-6 `[X]`).
4. **No unconditional chart.** Every chart card states all eight §7 fields (question, decision,
   baseline, scope, sampling rule, textual equivalent, fallback, budget). A chart without them is not
   rendered.
5. **No decorative pulse or glow**; motion only for state transitions (≈100–240 ms,
   `prefers-reduced-motion` collapses; direction §11 `[P]`).
6. **Per-band thesis-failure audit + whole-page audit.** A band fails if it reads as "truth bar +
   alert cards + service table + KPI rail" (`control_room_direction.md:505-511` `[M]`); the blind
   A/B is performed on the **whole page**, not just the resting screen.

**Why.** C1's density score is 4 precisely because a long page is where the wall risk concentrates
(`design_candidates.md` §2.7 `[M]`). A prose guideline is not enough; a DOM audit converts the §4.5
rule into a pass/fail gate, which is what moves the arrangement from "can be held" to "is held".

**Acceptance.** The DOM audit fails any band lacking a provenance header, any `.kpi`/ambient-chart
selector, and any chart missing an §7 field; the whole-page blind A/B passes; the first viewport's
pixel budget is untouched (the workforce band is below the fold, v2 `O6` relocation `[X]`).

### D4 — Provenance in a long page (decided: per-band header + sticky masthead + per-value chips + last-success-on-failure)

*Refines C6 (truthfulness, 4 → gate-enforced).*

**Decision.** Adopt a four-part provenance discipline for the scroll document:

1. **Per-band provenance header** — every band states its scope, source, observation time/age,
   retained window/truncation, and measured/estimated/unknown semantics (direction §8 `[M]`).
2. **Sticky masthead** — the `R0` system/trust strip (`ON-G1`/`ON-G6`) stays on screen for the whole
   scroll, so trust and epoch never scroll out of view.
3. **Per-value chips** — every consequential value carries source + age + `measured`/`estimated`/
   `unknown`; a missing value renders the literal `unknown`, **never `0`** (the null-not-zero parser
   is shared with `charts.js:90-99` `[M]`).
4. **Last-success-on-failure** — a band whose fetch fails renders an explicit error state carrying
   its **last-success age** (DashClaw C7 honesty `[X]`), never a blank or a zero.

**Why.** C1's truthfulness score is 4 because per-value provenance is hardest to sustain down a long
document. Making the masthead sticky and the provenance per-band/per-value is the direct structural
answer, and it converts "green never lies" from a footer claim into a per-band, per-value property.

**Acceptance.** A stale fixture shows ages and explicit `unknown` and never green-over-stale; a
failed-band fixture shows last-success age; a value whose source has no samples renders `unknown`
with a reason, not 0.

### D5 — "Old dashboard as base" (decided: working-set fidelity over the 235-id parity inventory)

**Decision.** "Old dashboard as base" means **working-set fidelity** measured against
`parity_inventory.json` **by the closed surface palette** (`control_room_ia.md` §14) — all **235 old
ids / 10 capability classes / 34 canonical endpoints** placed, present, wired, and non-empty (or an
explicit documented empty-state) under the class-P gate. The old DOM/layout is **not** copied, and
the old **board boundaries are not the gate's unit**.

**Why.** The repository's only literal statement about the old dashboard **rejects** DOM reuse
(`control_room_ui_rebuild.yaml:24-29` `[M]`); the parity hard-rule (`direction §3.6`,
`control_room_direction.md:301-303` `[M]`) already fixes the working set as the requirement. Reading
it as DOM reuse would contradict both.

**Acceptance.** The class-P gate passes for all 235 items with a surface and a disposition; no
`re-skin` statement survives in the design.

### D6 — v2 status (decided: pinned branch-local evidence, never v2-only adoption)

**Decision.** The v2 synthesis remains a **pinned, branch-local evidence reference**
(`87559ef66` on `wt_facelift_review`); this workstream does **not** land it on `main`. Every v2
mechanism the design adopts must cite a **direction basis**; a mechanism that exists **only** in v2
is **dropped, not adopted**. If the controller later lands v2, this determination is unchanged.

**Why.** v2 is `status: proposed` and not on `main` (`design_candidates.md` §1 `[M]`); the accepted
authority is `control_room_direction.md`. Landing v2 is a separate permanence decision outside this
brief's scope, and adopting a v2-only mechanism would let an off-main proposal become policy by the
back door.

**Acceptance.** Each adopted v2 mechanism ID in the final design is paired with a direction anchor;
no v2-only adoption survives review.

---

## 7. Final acceptance gates (what proves the determination)

| Gate | Check |
|---|---|
| **Glance** | At 1440×900 / 1024×768 / 390×844: all `ON-G1..G7` anchors present, non-zero, fully inside the initial viewport, **no page or region scroll needed to reach them** (D1). |
| **Scroll** | A below-fold fixture shows every band non-empty with live data; the page height is bounded; each band carries a scope/provenance header; the sticky masthead stays visible (D1, D3). |
| **Wall** | Deterministic DOM audit: every band has a provenance header; no KPI-tile row; every chart carries its eight §7 fields; whole-page blind A/B confirms the run/evidence/action distinction (D3). |
| **Provenance** | Stale fixture shows ages + explicit `unknown`, never green-over-stale; failed-band fixture shows last-success age; missing = `unknown`, never `0` (D4). |
| **Timing** | A real-ledger fixture shows measured `queue_wait` / `service_time` / `first_token` / cost split / step durations; unmeasured = `unknown` + reason; route is `GET`-only (D2). |
| **Charts** | Every chart states question, decision, baseline/scope, sampling rule, textual equivalent, fallback, budget (direction §7 `[P]`); SVG only (`viewBox`, `currentColor`, `<title>`/role); missing value = gap (EV-7). |
| **Parity** | Class-P gate: all 235 `parity_inventory` items present/wired/non-empty with their disposition; `routes_dropped: 0`; no silent drop (D5). |
| **Authority** | No new mutating route class; observe-only rails never auto-steer; every irreversible act behind its existing typed door + receipt (direction §12.2 `[P]`). |
| **No-regression** | The eight §12.2 guardrails hold; WCAG 2.2 AA contrast; forced-colors safe; reduced-motion collapses motion; single EventSource per object; one arrangement per breakpoint (D1). |

---

## 8. Handoff and the controller's remaining acts

**Implementation order (determined by dependency, not preference).**

1. **First-viewport/layout guard + scroll shell** (D1, D3, D4) — the gate exists before any band is
   added, so no band can quietly move the glance.
2. **Read-only timing route** (D2) — the shared dependency of the workforce band and `R4d`.
3. **Workforce band wired to the route** (C4) — built only on the exposed measured fields.
4. **Chart set** (C3) — step/phase duration, queue timing, first-token on one shared scale; cost and
   throughput reusing `charts.js`.
5. **Parity class-P gate** (D5) — run band by band over all 235 items.

No step may expand the authority model, add a runtime dependency, introduce a new mutating route
class, or reuse the single-screen shell.

**The controller's remaining acts (P0 permanence — gates, not design questions).**

1. **Ratify the D1 narrowing of direction §18 acceptance criterion 2** and merge the amendment
   through the permanence gate. The determination is made; the signature is the controller's.
2. **Ratify D2's new read-only route** as an implementation task (read-only; no schema change).
3. **Merge** the resulting `feature/*` work through the permanence gate. The machine proposes; the
   controller disposes.

**What this document is not.** It is not the implementation task list (that is the next phase's job)
and it is not the direction amendment itself. It is the determination: the winner, the runner-up, the
scores and their reasons, the attacks, and the six decisions that close every question the process
surfaced.

---

## Appendix — source pins and citation key

- **Old dashboard:** `1457b9299` — `apps/control_room/static/index.html` (847 lines), `app.js`
  (4109), `shell.js` (438); 235 unique ids, 44 route registrations, 34 canonical endpoints
  (`parity_inventory.json` `[M]`; verified).
- **Current room:** `HEAD` = `main` — `index.html`, `charts.js` (`HISTORY_MAX=60`; four charts
  `spend`/`throughput`/`failure`/`dependency`, `[M]` verified), `parity.js`, `visuals.js`;
  **47 route registrations** (re-measured here `[M]`).
- **Unmerged new resting screen:** `wt_room_new` @ `c06b158a7` (8 commits ahead of `main`).
- **v2 synthesis:** `docs/research/control_room_ui_reference_synthesis_v2.md` @ `87559ef66` (branch
  `wt_facelift_review`; not on `main`); mechanism IDs cited inline in `design_candidates.md` §1.5.
- **Accepted direction:** `docs/research/control_room_direction.md` (status: accepted); §3.6, §4.5,
  §7, §10, §12, §18.
- **Glance contract + palette:** `docs/research/control_room_ia.md` §4 (`ON-G1..G7`), §14 (closed
  palette), §15 (class-P gate).
- **Parity:** `experiments/research/control_room/parity_inventory.json`
  (`control-room-parity-inventory/v1`; 235 items; 214 `re-house` / 20 `replace-with-reason` /
  1 `preserve`; 10 capabilities; verified).
- **Measured writers:** `adapters/opencode.py:558-559`; `runtime/executor.py:259-261`;
  `runtime/workflow_runner.py:4031-4047`; `runtime/queue_timings.py:63-118`;
  `measurement/efficiency.py:249-272`; `control/control_db.py:959-976` (the `step_attempts` schema
  lacking queue/service/first-token/cost-split columns; verified).
- **This workstream's inputs:** `docs/website/control_room_ui/design_brief.md` (criteria);
  `docs/website/control_room_ui/design_candidates.md` (candidates).
