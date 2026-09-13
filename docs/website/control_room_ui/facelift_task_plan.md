---
status: accepted
---

# Control Room facelift — small-task plan (phase `a1_decompose`)

**Date:** 2026-09-13
**Phase:** `a1_decompose` of `workflows/repository/control_room_facelift_review.yaml`.
**Inputs (read-only):** `docs/research/control_room_direction.md` (status: accepted),
`docs/research/control_room_ui_reference_synthesis.md` (proposed facelift, "v1"),
`docs/research/control_room_ui_reference_synthesis_v2.md` (the a0 reference sweep, "v2"),
`docs/research/control_room_state_screens.md`, `docs/research/control_room_wireframe.md`,
`docs/research/agent_runtime_landscape.md`, and the live room inventory in v1 §1 / v2 §2.
**No implementation in this run.** The artifact is the reviewed plan; the phased render gate and
the feature-parity checks remain the executors of record.

---

## 0. What this plan is, and what it deliberately is not

This plan decomposes the **facelift that survives reconciliation with the accepted direction** —
not every sentence of v1. V2 already ran the reconciliation and found five v1 proposals that
*conflict* with the accepted direction (v2 §5–§6): the R0 KPI wallboard, the state-rhythm animation,
the LLM "ask the data" lens, the single computed health score, and the call-center KPI treatment of
R3. Those five are **not scheduled in their v1 form**. Their corrected forms are scheduled instead
(v2 §5.1–§5.5), and the corrections are called out inline so a reviewer cannot mistake a corrected
task for a re-litigation.

Three sentences frame every task below.

1. **The unit of work is the run**, and the resting screen is a run-triage console, not a dashboard
   (direction §1). Every task either strengthens the run object, the evidence authority boundary, or
   a governed decision.
2. **The machine proposes; the controller disposes** (direction §2.5, `agent_config/rules.md`).
   Observe-only rails (supervisor, lease watchdog) never steer; a task may never introduce an
   automatic actuation.
3. **To make policies, we need information** (the load-bearing rule). A task that consumes a signal
   must name the measured producer of that signal; a task with an unmeasured `requires` is
   unwritable and must be split or gated behind the instrumentation that produces it.

### 0.1 Relationship to v1 / v2 / direction

- **Presupposed (not re-litigated):** the run object and its four facets (direction §2), the
  removed-generic-elements list (direction §4.3), the restraint budget (direction §4.5), the
  truth/provenance contract (direction §8), the motion budget (direction §11), the accessibility
  bar (direction §12.1), and the eight no-regression guardrails (direction §12.2).
- **Adopted from v2 (mechanism-level, corrected):** the transition-only announcer (T7), counts as
  filters with a refresh-age caveat (T3/T4/A-6), the phase+age pair (O4), the split-pane comfort
  band as guidance only (L3/A-8), the size gate (L4), the causal spine (C8), the evidence tab (C9),
  the flood/pause/grants attention controls (C4/C5/C6/A-4), and stale/queue-unavailable honesty (C7).
- **Explicitly not scheduled (v2 conflicts):** an R0 KPI wallboard; state rhythm/pulse as identity;
  a runtime LLM chart lens; a composite vanity health score; R3 rendered as money KPI cards.
- **Deferred behind a controller decision:** the seen/ack watermark (depends on whether supervisor
  flags gain an ack bit, `agent_runtime_landscape.md` §5.1 item 1) and the receipt-verify affordance
  (needs a route-class decision, direction §12.2).

### 0.2 Coverage of the required synthesis

The phase prompt names thirteen deliverables (five regions + state language + visual tokens + the
five adds + astra). Each maps to at least one task below; the *corrected
form* column records the v2 §5 reconciliation, so a reviewer cannot mistake a correction for a
silent drop. `F01a/F01b/F02a/F02b/F03` (verification substrate) is the enabler every row depends on and
carries no region of its own.

**Revision note (a4).** This plan was folded against `docs/reviews/control_room_facelift_adversarial.md`
(phase `a3`). The adversarial pass split three over-broad tasks (`F02 → F02a/F02b`, `F25 → F25a/F25b`,
`F26 → F26a/F26b`), serialized `F01a → F01b`, completed the half-migration edges (`F04 →` five more
consumers), removed two client-derived values (`F04`/`F14` now render packet fields only), and made
the gate shapes name a gate that can actually observe the claim. Every disposition is in §8; the two
rejected sub-demands are at the end of §8. The plan stays **small and gated**: the task count rose
only where a task was too broad for one session, and each new leaf carries its own seeded-bad
fixture or named gate.

| Prompt deliverable | Task(s) | Corrected form (v2 §5) |
|---|---|---|
| R0 wallboard | F07 | **Not** a KPI wallboard: R0 is the scope/truth strip (`ON-G1`/`ON-G6`) with per-value provenance and counts as filters (v2 §5.1). |
| R1 inbox | F08, F09, F10 | Counts-as-filters with the refresh-age caveat; one expand-in-place item; flood/pause/grants with pause a *confirmed controller act*. |
| R2 tiles (incl. E10 row legibility) | F11, F12 | Tiles become run-ledger rows; the E10 `.run-row` contract (identity, target, model×attempt, phase n/t, state, live, claim/proof, commit, cost-provenance, eligibility, receipt; `control_room_wireframe.md:113`) is preserved at both breakpoints. |
| R3 KPI/health/composition | F13, F14, F15 | Five `ON-G4` values as a bounded constraint ledger (not money cards); degraded summary read from the **packet's health fields** (not a client-derived vanity score); composition stated in words; partiality and `merged`≠`published` preserved. |
| R4 session surface | F16, F17, F18, F19, F20 | R4b one-stream feed + governed action band; R4c typed ladder + causal spine; R4d step timings; size-gated payloads; governed steer/reply. |
| State language (glyph/colour/rhythm/seen/ack) | F04, F05, F06 | Rhythm dropped (not identity, v2 §5.2); state = glyph+word+colour+settled timestamp on the **two axes the packet emits** (`lifecycle.state`, `attention.state`); seen/ack watermark gated on D1; transition-only announcer. A genuinely independent supervisor-attention axis is **parked as F27** behind D7. |
| Visual tokens | F25a, F25b | Computed-style token contract (surface ramp, one operator amber + one machine cyan, mono data type, chrome only on active/selected, motion only on transitions) + a recorded blind A/B for the restraint budget. |
| Add: live-log lens | F21 | Off the resting screen; per-cell event kinds with colour + filter. |
| Add: pipeline lens | F22 | Per-run phase grid from `step_attempts` (`phases_completed/phases_total`). |
| Add: ask-the-data | F24 | An **authored** `question → lens` map (no route exposes `spec.rules`); the runtime-LLM variant is **DO-NOT-COPY** (v2 §5.3, a3 D-9). |
| Add: counters-as-filters | F08, F07 | Query-grammar chips; counts link to their lens; never a bare delta from a stale poll. |
| Add: toast rail | F23 | Bounded, per-kind durations, active-view silent, deep-link only, never a second announcer. |
| Astra fleet enablement | F26a, F26b | F26a = the repo `MODEL_WHITELIST` entry; F26b = the container config-mount change (controller/host act, parked). Both gates named (`control/model_policy.py:27-30`). |

---

## 1. The task unit contract

The phase prompt's rule, made mechanical:

> **A task is small iff ONE agent session can produce its artifact and ONE named acceptance check
> turns green.**

If one session cannot both write the artifact and make the named gate pass, the task is split by
asking *"what must be true for this to hold?"* until every leaf satisfies the bound. The split is a
`requires`/`produces` edge, never an informal "do part of it".

### 1.1 Fields every task carries

| Field | Meaning |
|---|---|
| **id** | `Fnn`, stable; never reused. |
| **Question** | the single question the task answers — a question, not a topic. |
| **Artifact** | the exact file(s)/region(s)/module(s) the session produces. |
| **Acceptance (named gate)** | the ONE check that proves the answer: a render-gate class, a named pytest target, a fixture assertion, or a measured diff. "Works" is not an acceptance. |
| **Deps** | task ids that must be green first; `—` = frontier. |
| **Layer** | `intent` → `structure` → `behavior` → `verification` → `presentation` (below). |
| **Class** | evidence class of the claim: `[M]` measured in-repo, `[C]` computed, `[H]` heuristic, `[P]` policy/placement, `[X]` external (with a v2 §2 pin). |
| **Size** | `S` ≤ ½ session; `M` = 1 session. No `L` survives (it is split). |

### 1.2 The layer grammar

The five layers are an ordering of *questions*, not of files. A question at a layer may fan out in
parallel with its siblings; a question that needs another layer's answer carries a cross-layer
`requires` edge (this is exactly the compiler's `RuleSpec.requires`/`produces` gate,
`src/agentic_dynamics/experiment/experiment_spec.py:899-963`).

| Layer | The question shape | Fans out | Cross-layer edges |
|---|---|---|---|
| **intent** | *what operator question must this answer?* | yes | produces the acceptance every lower layer consumes |
| **structure** | *what regions/objects/selectors carry the answer?* | yes | requires intent; produces DOM selectors |
| **behavior** | *what happens on state change / interaction?* | yes | requires structure selectors |
| **verification** | *what fixture and gate prove it?* | yes | requires behavior; produces the green gate |
| **presentation** | *does it read correctly under load and in forced-colors?* | yes | requires structure + verification |

### 1.3 The named gates of record

These are the only acceptance primitives a task may cite. A task that cannot name one is not gated.

| Gate | Command / target | Source |
|---|---|---|
| Browser-free render gate | `python3 scripts/verify_control_room_rendering.py --check-fixtures` | `scripts/verify_control_room_rendering.py:288-291`; **returns before any browser call** (`:2314-2316`), so it cannot observe geometry/clip/value claims (a3 T-8) |
| Full render gate (Playwright) | `python3 scripts/verify_control_room_rendering.py` (or `agentic-dynamics validate render`) | same; exit 0 PASS / 1 FAIL / **2 = no browser** — the first wave halts (blocked, not passed) on 2 |
| Geometry/semantics path | the browser `_check_semantics` / geometry JS | duplicate/overwrite, overflow and value checks live here, not in `--check-fixtures` |
| Clip/occlusion detector | **new, part of F01a** | no clip / 1×1px / occlusion detector exists today (only G-5 font floors, G-6 empty-value, G-14 line clamps) — F01a adds it (a3 T-8) |
| Style gate | `python3 scripts/verify_control_room_rendering.py --style` | tabular numerals, landmarks, live region, recognizability carriers, focus rings, motion budget, reduced-motion collapse (`:1285-1310`); **does not test contrast or forced-colors** |
| Contrast / forced-colors | inside the default browser gate theme loop | `:1459-1521`; never `--style` alone (a3 D-8) |
| Computed-style token contract | **new, part of F25a** | enumerates exact custom properties/hex and asserts `getComputedStyle` on a fixture across dark/light/forced-colors (a3 D-8) |
| Recorded blind A/B | **new, part of F25b** | the direction §4.5 restraint-budget check is a blind A/B, not a machine assertion (a3 D-8) |
| Static-view contract | `pytest tests/test_control_room_static_views.py` | test asserts read routes + lenses + verbatim packet states |
| Glance integrity | `pytest tests/test_control_room_glance_integrity.py` | missing DB → `unknown` not zero/all-clear; no client guessing |
| Feature parity | `python3 scripts/verify_control_room_rendering.py --parity` + `pytest tests/test_control_room_feature_parity.py` + `tests/test_control_room_parity.py` | `experiments/research/control_room/parity_inventory.json` |
| Accessibility class | `python3 scripts/verify_control_room_rendering.py --a11y` | a11y suite in the gate |
| Doc lifecycle | `pytest tests/test_doc_lifecycle.py` | frontmatter/status contract |
| Fast-path gate | `pytest tests/test_fast_path_gate.py` | `pytest tests/ -m fast` within 180 s |

A task's acceptance is stated as **one** of these plus the specific fixture/selector it asserts.

---

## 2. Workstream map

| WS | Theme | Tasks | Delivers (visible improvement?) |
|---|---|---|---|
| V | verification substrate | F01a, F01b, F02a, F02b, F03 | no (enabler) — closes the a6 gate misses first |
| S | state language | F04–F06 (+ parked F27) | yes (identity + honesty) |
| R0 | scope / truth strip | F07 | yes |
| R1 | attention inbox | F08–F10 | yes |
| R2 | run ledger / rows | F11–F12 | yes |
| R3 | money / health / composition | F13–F15 | yes |
| R4 | session surface | F16–F20 | partially (drill-down) |
| L | lenses and adds | F21–F24 | partially |
| T | visual tokens | F25a, F25b | yes (restyle) |
| A | fleet enablement | F26a, F26b | no (unblocks the astra adversary) |

---

## 3. Tasks

### Workstream V — verification substrate (build the gate before the pixels)

The a6 IA adversary proved the current gate can PASS while answers are incomplete, illegible, or
contradictory (see `docs/reviews/control_room_facelift_ia.md` G-1/G-3/G-5/G-6/G-10/G-11/G-13/G-14/G-15
FAIL/PARTIAL, and the missing B/A/E classes). A visual task landing before F01 would be graded by a
gate that cannot see it. **F01–F03 are therefore the true frontier**, even though they deliver no
pixels.

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F01a** | Can the **full render gate** no longer pass on a duplicate/overwritten selector, an answer that overflows its region, or a label hidden in a 1×1px clip? | `scripts/verify_control_room_rendering.py` G-1/G-3/G-5/G-6 uniqueness/overflow/legibility hardening **plus a new clip/occlusion detector** | **full Playwright gate** (not `--check-fixtures`) passes on F-0; a **seeded-bad fixture set** (duplicate selector, overflowing answer, 1×1px-clipped label) makes it exit 1; the same seeded set **passes** `--check-fixtures` (proving the browser path is the discriminator, a3 T-8) | — | verification | [M] | M |
| **F01b** | Can the full gate no longer pass on a value that disagrees with its fixture (money unknowns, marginals, row fields, answer/parent uniqueness)? | gate G-10/G-11/G-13/G-14/G-15 value/fixture semantics in the browser `_check_semantics` path | a **seeded-bad fixture set** (wrong `ON-G4` value, wrong `top/other/unknown` count, duplicated answer writer) makes the **full** gate exit 1 | **F01a** — both patch one file, so they are serialized; two first-wave sessions writing one file is a merge hazard, not a split (a3 T-9) | verification | [M] | M |
| **F02a** | Is the blind-comprehension scorecard a schema-valid, **human-recorded** artifact — never machine-generated? | scorecard schema + `apps/control_room/verification/b_comprehension.json` (a recorded human pass per direction §4.2) | `b_comprehension.json` validates against its schema **and** records the five §4.2 sentences + seven `ON-G1..G7` answers from a human; deleting the recorded pass or flipping one required recognition fails the class-B check; the artifact **cannot be regenerated from the DOM** (a3 T-10) | F01a, F01b | verification | [M]/[P] | M |
| **F02b** | Does the full gate **consume** the recorded scorecard and fail on a seeded recognition miss? | gate class-B reader | full gate (not `--a11y` alone) green; a seeded recognition miss makes the class-B check fail | **F02a** | verification | [M] | S |
| **F03** | Do the forcing fixtures the new mechanics need exist (saturated inbox, approval flood, stale/queue-unavailable, oversized payload, two-sources-disagree, cost-unknown-never-zero), **including the two failure states the truth table already names**? | `verification/fixtures/F-8…F-12` + gate assertions | each fixture renders and the gate asserts its distinguishing field; empty fixtures fail; **adds `partial: True`/`history_capped` (direction §8) and `merged ≠ published` (state-screens S-6)**; the two-sources-disagree fixture is **BLOCKED until precedence is specified** (a3 D-7; decision D8) | F01a, F01b; **D8 for the two-sources fixture** | verification | [M] | M |

**Size bound (a3 T-2/T-8/T-10).** F01 is split into **F01a** and **F01b**; both patch one file, so
they are **serialized** (`F01a → F01b`, a3 T-9) rather than presented as independent. F02 is split
into **F02a** (schema + a recorded human pass) and **F02b** (the gate consumer + seeded miss),
because schema + recorder + reader + recorded pass is two sessions (a3 T-10). A single session
landing both halves of either is an economy, never a prerequisite, so the one-session bound is never
violated.

### Workstream S — state language (identity and honesty)

The direction's state contract is two-axis and never colour-only (direction §12.1; v2 §4.2 O2/T2).
V2 killed the v1 rhythm-as-identity idea (§5.2). The state is **glyph + word + colour + a settled
timestamp**; motion is only a state transition (100–240 ms, collapsed under reduced motion).

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F04** | Do the **two axes the packet actually emits** (`lifecycle.state`, `attention.state ∈ {active,none}`, `glance.py:568`) render independently as glyph+word+colour+settled-timestamp, does an unmapped enum degrade to `unknown`, and can attention be `unknown` while lifecycle resolves? | state token map + `app.js` renderer + `style.css` tokens | `pytest tests/test_control_room_static_views.py` + a unit test that an unknown enum renders `unknown`; **a client-spy test fails if the renderer derives attention instead of reading the packet's `attention.state`**; the fixture uses only the emitted enum `{active,none,unknown}`, never a hand-authored `stale` (direction §2.2/§12.1/§12.2.5, a3 D-6) | F01a | presentation | [M] | S |
| **F27** *(parked)* | Do we want a genuinely independent **supervisor-attention axis** the packet does not emit today, with a server-derived degraded summary? | `apps/control_room/routes/glance.py` projection change (per-run attention field + derived health) | a captured-packet fixture carries the new field and a client-spy test proves the renderer reads it (no client derivation); **parked on D7 — no producer exists today** (a3 D-6) | — ; **D7** | structure | [M] | M |
| **F05** | Can "done" be distinguished from "idle" with a seen/ack watermark whose acknowledgement is recorded, **without altering the observe-only flag**? | if D1=yes: a **typed-door P1 act** writing a receipt, with an explicit "does not alter flag state/steering" contract, and a stated route-class inventory change; if D1=no: **parked** (a3 T-13) | authority test proves the ack writes a receipt and **cannot change or clear a flag**; `tests/test_control_room_glance_integrity.py` (no client guess); the route-class inventory diff is exactly the one typed door | F04; **controller decision D1** | behavior | [M]/[P] | M |
| **F06** | Does a failed packet fetch keep the last-known data, label it with its last-successful age, and never read as all-clear — with one transition-only, increases-only polite live region? | freshness banner + `announcer` module replacing the sr-only announcer | failure fixture shows last-successful age, never “all clear” (gate + F03 stale fixture); announcer unit tests: initial/decreases not announced, identical re-announces, batch coalesced | F01a, F03 | behavior | [M]/[X] T7,C7 | M |

### Workstream R0 — the persistent scope / truth strip

Corrected from v1: **not** a six-number wallboard (v2 §5.1). R0 answers `ON-G1` and `ON-G6` with
per-value provenance; counts are addressable filters; no tiles, no per-card sparklines.

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F07** | Can R0 answer `ON-G1`/`ON-G6` at rest with per-value source+age and no KPI tile row, with its counts linking to their lens? | `index.html` `data-region="R0"` + `app.js` renderer + tokens | Render gate `ON-G1`/`ON-G6` + a **no-tile assertion** (no `.kpi`/`.stat-tile` in R0) + the no-scroll glance check | F01a, F04 | structure | [M]/[P] | M |

### Workstream R1 — the attention inbox

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F08** | Are counts addressable filters (composing a visible query grammar) whose any displayed delta carries the refresh age, so a stale poll cannot render as a trend? | R1 counts + filter chips + query serialiser | gate G-14 counts/totals + a click-through filter test; a stale fixture asserts the age, not an unqualified delta (A-6); the chips use F04's state enumeration, not a second list (a3 T-11) | F01a, F03, **F04** | behavior | [M]/[X] T3,T4 | M |
| **F09** | Does one attention item expand in place into its report, with a single compact empty state (no repeated filler cards)? | R1 item renderer | fixture F-1 (one waiting / one failed / one money-risk) + screenshot + gate asserts one empty state, not N cards (A5-D7) | F07, F08 | structure | [M]/[X] C3 | M |
| **F10** | Are approval-flood, pause, and standing-grant controls present, with pause as a *confirmed controller act* — never a threshold-triggered automatic steer? | R1 flood/pause/grants region + `services/` confirm path | a **mutations-boundary state test** (patterned on `tests/test_control_room_parity.py`) that fails if pause is reachable without the typed door; receipt fixture; flood fixture renders a labeled confirm (A-4). The render gate is **not** this task's acceptance (a3 D-4) | F01a, F03, F09 | behavior | [X] C4,C5,C6 | M |

### Workstream R2 — the run ledger and its rows

The repaired facelift already passed the r3/r4 adversaries (`docs/reviews/control_room_facelift_repair_design.md`,
`..._repair_ia.md`); the E10 row legibility contract (session band, row-lease, claim/proof,
source/receipt) is now the baseline. This workstream must **preserve** it while adding the ledger
mechanics. **A5-D2/A5-D3 must be re-adjudicated by id against the current committed source before
being scheduled** (a3 T-14): A5-D2 is the row **hard-budget carrier** (desktop/live) and A5-D3 is
mobile truncation (`docs/reviews/control_room_facelift_design.md:46-47`), and the repair verdict
already reports the row reserved/cap pair present with "No design finding remains open for this
pass" (`..._repair_design.md:28,58`). F11 keeps only what a fixture from the current source shows
missing, and if nothing is missing the repair verdict is corrected instead (a3 T-14).

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F11** | Does every actionable row keep the E10 legibility contract at both breakpoints — identity band, attached lease/cost band (reserved vs settled, source, headroom), paired ADVISORY/MEASURED marks, eligibility + receipt — with no ellipsised identity on mobile? | `.run-row` markup + `app.js` renderer + tokens | gate G-13 compares **row values** incl. `spec/cell` (a6 G-13 gap) + **visible text equals the fixture value and no label is clipped** (full gate's new clip detector, a3 T-6/T-8); the mobile blind-comprehension half is satisfied once **F02a/F02b** are green. **A5-D2/A5-D3 re-adjudicated by id against the current source, citing the failing selector; keep only what the source shows missing** (a3 T-14) | F07, F04, F02a, F02b | structure | [M] | M |
| **F12** | Does each in-flight/failed run show its phase text and phase age, with a **total map over the six operator states** to `RunState`/attempt and an explicit `unknown` for unmapped phases? | attempt-phase renderer + mapping table | `pytest tests/test_control_room_static_views.py` + a unit test of the exhaustive map: **all six operator states (`running/blocked/stalled/failed/escalated/done`) + an unmapped enum → `unknown`**; `escalated` → "no cascade armed" when no mechanism event exists (state-screens S-5, a3 D-7); never the raw code as a label | F04 | behavior | [M]/[X] O4 | S |

### Workstream R3 — money, health, composition

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F13** | Do all five `ON-G4` values render at rest in a bounded constraint ledger with per-value provenance and a money-risk exception — never as free-floating money cards — **and never erase partiality or the `merged`/`published` distinction**? | `data-region="R3a"` + cost block | gate `ON-G4` (all five values) + provenance chips on each + F-03 money-risk exception; a6 G-10 provenance gap closed; a `cost_source=unknown` fixture renders the literal `unknown` and **never `0`/blank** (state-screens `S-7`, a3 D-2); **`partial: True`/`history_capped` are marked and `merged ≠ published` renders distinctly** (direction §8, state-screens S-6, a3 D-7); a hidden-but-clipped label fails (full gate, a3 T-6) | F01b, F04, F11 | presentation | [M] | M |
| **F14** | Does `ON-G6`/R3b render the packet's **degraded/health fields** (`health_detail`, `composition`) without deriving a composite score client-side? | R3b degraded summary (reads packet fields) | gate `ON-G6` + a **client-spy test that fails if the renderer derives health** rather than reading the packet; no single score field exists without server inputs (v2 §5.4/A-10, a3 D-6/D-7); the two-sources-disagree fixture is **BLOCKED until precedence is specified** (D8) | F01b, F04, F03 | presentation | [M]/[C] | M |
| **F15** | Does R3c state `top`/`other`/`unknown` in words (never `t/o/u`), with bounded buckets and the fixture's counts asserted? | R3c marginals | gate G-11 extended to assert bucket values + fixture counts (a6 legibility gap); the marginals use F04's state enumeration (a3 T-11) | F01b, **F04** | presentation | [M] | S |

### Workstream R4 — the session surface

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F16** | Does R4b give exactly one selected worker a bounded live event feed (replay → `replay_complete` → live, follow/pause) plus a governed action band? | R4b region + one-stream guard | one-stream test (direction §12.2.2) + authority test for the action band + receipt fixture; gate R4b class; the feed uses F04's state vocabulary (a3 T-11) | F01a, **F04** | structure | [M] | M |
| **F17** | Does R4c render the evidence ladder with the repository's typed rungs and a five-stage causal spine for the selected decision? | R4c region + causal-spine renderer | fixture with one waiting / one failed / one money-risk; gate asserts typed rungs and the spine stages (v2 C8) | F16, F04 | structure | [X] C8 | M |
| **F18** | Does R4d show per-attempt timings each as `measured` or an explicit `unknown` (never a fabricated `0`), with the fleet aggregate in the `L-WORKFORCE` lens? | R4d region + `L-WORKFORCE` lens | gate asserts `data-state=measured\|unknown`; a missing-writer fixture renders `unknown`; resting gate unchanged (v2 O6) | F16, F04 | behavior | [M]/[X] O6,HT3 | M |
| **F19** | Does a heavy payload/JSON surface gate on a serialization probe and mark truncation/partiality instead of parsing/rendering unbounded input? | size-gate helper + disclosure | unit test at/below/above threshold + a `partial` marker renders (v2 L4); F-11 oversized fixture | F17 | behavior | [X] L4 | S |
| **F20** | Does R4 offer a governed steer/reply that shows target, scope, reversibility, and writes a receipt — and refuses to steer without them? | R4b action band + `services/mutations.py` path | authority test (no unguarded terminal write; P1 within lease) + receipt fixture (A-12); the action band uses F04's state vocabulary (a3 T-11) | F16, **F04** | behavior | [M]/[X] H2 | M |

### Workstream L — lenses and adds

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F21** | Does the live-log lens show per-cell event kinds with colour and filter, off the resting screen? | new lens in `parity.js` `PANELS` + panel DOM | lens fixture desktop/mobile; resting gate unchanged; lens hidden at rest | F01a, F13 | structure | [X] v1 §2.1 (Brain; the Brain is a **v1** source, not a v2 §2 pin — a3 D-9) | M |
| **F22** | Does the pipeline lens render the per-run phase grid from `step_attempts` using the packet's `phases_completed/phases_total`? | pipeline lens + renderer | lens fixture; gate asserts the phase grid counts | F01b, F12 | structure | [M] | S |
| **F23** | Does a bounded toast rail exist (max N queued, per-kind durations, active view silent, click deep-links only) without duplicating the polite live region? | toast module + tokens | unit test of the queue/duration policy; a11y test that the live region is transition-only and the toast is not a second announcer | F06 | behavior | [X] v1 §4.5.5 (the toast contract is Herdr policy; v2 pins herdr-portal H1–H3, not a raw `Herdr` id — a3 D-9) | M |
| **F24** | Can a user question map to a recommended lens **statically**, with a test that **fails on construction of any outbound model client** (replacing the v1 runtime LLM lens)? | an **authored** `question → lens` map at `apps/control_room/static/experiment_lens_map.json` + a `PANELS` index loader (no route exposes `ExperimentSpec` rule objects today — a3 D-9) | a client-spy test that goes red if the lens path builds a model call; every recommended lens exists in `PANELS`; **every chart states question/decision/baseline/completeness/textual-equivalent/fallback** (direction §7, A-3, a3 D-4/D-9) | F21, F22 | structure | [P]/[X] | S |

### Workstream T — visual tokens

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F25a** | Do the accepted visual tokens hold as a **computed-style contract** across all three themes and forced-colors? | `style.css` token block | computed-style assertions enumerate the exact custom properties/hex set and assert `getComputedStyle` on a fixture in dark/light/forced-colors; a seeded palette mutation (a second amber, a chrome token on a resting region) fails; **contrast/forced-colors come from the full browser gate (theme loop `:1459-1521`), never `--style` alone** (a3 D-8). **First task of the second wave** (a3 T-4) | F04, F07 | presentation | [M]/[P] | M |
| **F25b** | Is the restraint budget / thesis-failure rule validated by a recorded **blind A/B**? | recorded blind A/B disposition artifact (direction §4.5) | the artifact exists; a seeded "KPI rail" restyle fails its thesis check (a3 D-8) | F25a | presentation | [P] | S |

### Workstream A — astra fleet enablement

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F26a** | Is `openai/gpt-6-astra` a permitted fleet model in the **repo** whitelist? | `scripts/fleet/spawn_wrapper.py` `MODEL_WHITELIST` + the closed-vocabulary test that guards it | after the entry, a spawn/admission dry-run with `--model openai/gpt-6-astra` proceeds **past validation step 2**; the closed-vocabulary test gains a **named reason**, never a weakened assertion (a3 T-12) | — | behavior | [M] | S |
| **F26b** | Does the container config mount map the model (the **second** gate)? | the host config-mount change (a controller/host act — the controller's, not a repo edit) + verification note | a spawn/admission dry-run reports the remaining (host) blocker; parked until the controller performs the mount | **F26a**; controller decision D3 | behavior | [M] | S |

---

## 4. Minimal first wave and the stopped-by gates

### 4.1 The smallest set that delivers visible improvement

**First wave = `{F01a, F01b, F02a, F02b, F04, F07, F11}`** (revised by a3 `D-5`, `T-1`, `T-8`,
`T-9`, `T-10`: the wave must contain every gate its stopped-by list cites, and F01/F02 are split so
each leaf is one session). The wave is **serialized where two tasks patch one file**: `F01a → F01b`
and `F02a → F02b`.

| Why each is in | F01a/F01b the full gate must see the change (and the seeded-bad fixture must fail) | F02a/F02b the recorded legibility scorecard must exist before it is cited | F04 the two-axis identity grammar the packet actually emits | F07 R0 truth strip (corrected) | F11 the row is the run object |
|---|---|---|---|---|---|

Rationale: F01a/F01b are the prerequisite (a change the gate cannot fail on is not gated); F02a/F02b
make the blind-comprehension acceptance real before F11 cites it. F04/F07/F11 are the three
screenshot-level carriers of the direction's thesis (state, truth, row identity, direction
§4.4/§16). F06 (staleness/announcer) and F08 (counts as filters) are **second wave** — they are
small and high-value but the wave is kept minimal and self-contained. Nothing in the first wave adds
a new route, a new persistence plane, or a model call.

Everything else (`F03, F05, F06, F08–F10, F12–F26b`, plus parked `F27`) builds on the first wave;
the drill-down work (F16–F20) is deliberately **not** first-wave because the resting screen must
pass the recognizability test before the inspector is deepened.

### 4.2 Stopped-by gates (a wave does not start until these are green)

| Gate | Condition |
|---|---|
| **A browser is available** | the full Playwright gate exits **2** when no browser is present (`verify_control_room_rendering.py:36`); the wave reports **blocked, not passed** (a3 T-8) |
| Render gate, 3 breakpoints × 3 themes | 1440×900 / 1024×768 / 390×844 in dark, light, forced-colors; zero failures |
| One-resting-screen glance check | all `ON-G1..G7` answers present, complete, non-zero, inside the initial viewport with no page/region scroll |
| Blind-comprehension scorecard | the direction §4.2 five sentences + the seven `ON-G1..G7` answers, **recorded by a human** (class B, F02a) |
| Feature-parity class-P | every `parity_inventory.json` record placed/present/wired/non-empty or a documented empty state |
| Doc lifecycle + fast-path gate | `pytest tests/test_doc_lifecycle.py tests/test_fast_path_gate.py` green |

---

## 5. Sequencing (dependency edges as the compiler sees them)

```text
F01a ──▶ F01b ──▶ F02b        # serialized: both patch one file (a3 T-9)
F01a ──▶ F02a ──▶ F02b        # schema + recorded pass feed the gate consumer (a3 T-10)
F02a/F02b ──▶ F11             # blind-comprehension acceptance exists before it is cited (a3 D-5/T-1/T-10)
F01a ──▶ F03, F04, F06, F08, F10, F16, F21
F01b ──▶ F03, F13, F14, F15, F22
F04  ──▶ F05, F07, F11, F12, F13, F14, F15, F16, F17, F18, F20, F25a   # one state vocabulary, no half-migration (a3 T-3/T-11)
F07  ──▶ F09, F11, F25a
F08  ──▶ F09 ──▶ F10
F11  ──▶ F13
F12  ──▶ F22
F13  ──▶ F21 ──▶ F24        F22 ──▶ F24
F16  ──▶ F17 ──▶ F19 ;  F16 ──▶ F18 ;  F16 ──▶ F20
F25a ──▶ F25b
F26a ──▶ F26b (host mount; verify-only)
F03(two-sources) blocked on D8
```

Reading the edges: `F01a → F01b` (one file) and `F02a → F02b` serialize the split halves. `F11`
requires `F02a`/`F02b` (the blind-comprehension acceptance exists before it is cited, a3
`D-5`/`T-1`). `F04` produces the state vocabulary consumed by `F05,F07,F11,F12,F13,F14,F15,F16,F17,
F18,F20,F25a` — including the five consumers the earlier half-migration missed (a3 `T-11`).
`F25a` is deliberately first in the second wave, followed by `F25b` (a3 `T-4`). The two-sources
fixture is blocked until the precedence it asserts is specified (a3 `D-7`, decision D8).

Every edge is expressible as `requires`/`produces` in the compiler (`RuleSpec`, the direction of the
load-bearing rule). `F01a`/`F01b` produce the gate capability every later task consumes; `F04`
produces the state vocabulary; `F07` produces the R0 selectors `F09`/`F11` require; `F16` produces
the one-stream guard `F17`/`F18`/`F20` require.

---

## 6. Reconciliation against the accepted direction (`control_room_direction.md`)

| This plan | Status vs direction |
|---|---|
| Run-first object, evidence classes, ranking by attention | **Presupposed** (direction §1–§2) |
| No R0 KPI tiles/sparklines; R0 is the scope/truth strip | **Presupposed** (direction §4.3, §16; v2 §5.1 correction) |
| State = glyph+word+colour+settled timestamp; motion only on transitions | **Presupposed** (direction §11–§12; v2 §5.2 correction) |
| R1/R3 as annotation gutters, not peer boards; lenses deliberate | **Presupposed** (direction §3.1) |
| Counts as filters, expand-in-place inbox, flood/pause/grants | Extends direction §3.3 with v2 mechanisms (C3–C6) |
| seen/ack watermark | New; **deferred** behind a controller decision because supervisor flags have no ack bit (`agent_runtime_landscape.md` §5.1.1) |
| Toast rail | New; bounded, deep-link-only, never mutates (v1 §4.5.5) |
| Five `ON-G4` values as a constraint ledger; packet-derived degraded summary (not a client-derived score) | Presupposed + corrected v2 §5.4/§5.5; a client-derived value would be a second operational truth (a3 D-6) |
| Live-log and pipeline lenses; an **authored** recommended-lens map (no route exposes `spec.rules`) | New lenses; the runtime-LLM variant is **DO-NOT-COPY** (v2 §5.3, a3 D-9) |
| Astra enablement: repo `MODEL_WHITELIST` entry (F26a) + container config mount (F26b) | New local enablement; makes the parked astra adversary real (a3 T-12) |

---

## 7. Adversarial dispositions (a3 → a4)

Every a3 finding is dispositioned. **Accepted** = the plan changed; **rejected** = a one-line reason
(the two rejected sub-demands are at the end).

| a3 | Status | Resolution in this plan |
|---|---|---|
| D-1 two axes | **accepted (amended by D-6)** | F04 renders lifecycle + attention, but the attention axis is the packet's emitted `attention.state ∈ {active,none}`, not a hand-authored `stale`. |
| D-2 unknown-never-zero | **accepted** | F13 asserts the literal `unknown`; F03 adds the cost-unknown fixture. |
| D-3 F24 layer | **accepted** | F24 is `structure`; no back-edge. |
| D-4 behavioral acceptance | **accepted** | F10 names a mutations-boundary state test; F24 names a client-spy test; neither cites the render gate. |
| D-5 first wave / B scorecard | **accepted (updated)** | First wave `{F01a,F01b,F02a,F02b,F04,F07,F11}`; F11 requires F02a/F02b. |
| T-1 cited-but-unbuilt gate | **accepted (updated)** | F02a ships the recorded `b_comprehension.json`; F02b is the gate consumer; F11 cites F02a/F02b. |
| T-2 F01 not small | **accepted (updated by T-9)** | Split into F01a/F01b, **serialized** because both patch one file. |
| T-3 half-migrated room | **accepted (completed by T-11)** | F13/F14/F17/F18 require F04; T-11 adds F04→F06/F08/F15/F16/F20. |
| T-4 F25 timing | **accepted (updated)** | F25a is the first task of the second wave; F25b follows. |
| T-5 F26 host action | **accepted (completed by T-12)** | F26a (repo whitelist) + F26b (host mount); the host change is the controller's. |
| T-6 rendered clipping | **accepted (requires T-8's detector)** | F11/F13 assert visible text equals the fixture; the clip detector is F01a's. |
| T-7 evidence classes | **accepted** | F24 `[P]/[X]`, F26a/F26b `[M]`; classes follow the acceptance's falsifier. |
| W-6 readiness filter | **accepted** | Reflected in a2 (readiness is a hard admissibility filter). |
| **D-6 client-derived consequential values** | **accepted (core); one sub-demand rejected** | F04 renders only the packet's `attention.state`; F14 reads the packet's health fields; a client-spy test fails on client derivation. The genuinely-independent axis becomes parked **F27** behind D7. |
| **D-7 unspecified failure states** | **accepted (precedence deferred to D8)** | F03 adds `partial`/`history_capped` + `merged ≠ published`; F12's map is exhaustive over the six operator states with `escalated` → "no cascade armed"; the two-sources fixture is **blocked** until precedence is specified (the truth table is a read-only input). |
| **D-8 unpinnable token acceptance** | **accepted** | F25 splits into F25a (computed-style contract across 3 themes; contrast/forced-colors from the full browser gate, never `--style`) and F25b (recorded blind A/B). |
| **D-9 unresolving anchors** | **accepted** | F21 re-anchors Brain to v1 §2.1; F23 re-anchors the toast contract to v1 §4.5.5; F24 uses an **authored** lens map (no route exposes `spec.rules`) and cites direction §7; the `no-pulse` id is retired for direction §11's *decorative pulse*. |
| **T-8 wrong gate for F01a** | **accepted** | F01a names the **full** gate and adds the missing clip detector; F01b asserts the browser `_check_semantics` path; the stopped-by list includes "a browser is available (exit 2 blocks the wave)". |
| **T-9 false independence** | **accepted** | `F01a → F01b` serialized (both patch one file). |
| **T-10 circular class-B** | **accepted** | F02 splits into F02a (schema + **recorded human pass**) and F02b (gate consumer + seeded miss); the pass is human, never machine-generated (decision D6). |
| **T-11 incomplete half-migration** | **accepted** | `F04 → F06, F08, F15, F16, F20` added. |
| **T-12 F26 misidentified blocker** | **accepted** | F26a names the repo `MODEL_WHITELIST` (and its closed-vocabulary test); F26b is the host mount. |
| **T-13 F05 authority expansion** | **accepted** | F05, if D1=yes, is a typed-door P1 act with a receipt and a "does not alter flag state/steering" contract, with the route-class diff stated; else parked. |
| **T-14 F11 re-litigates A5** | **accepted** | F11 re-adjudicates A5-D2/A5-D3 by id against the current source, citing the failing selector; keep only what the source shows missing, else correct the repair verdict. |

**Rejected sub-demands (one line each).**

- **D-6's literal "F04's fixture must be a captured packet" — rejected:** the render gate's fixtures
  are deterministic by construction; the correction is that the fixture uses only the enum values the
  projection emits (`active`/`none`/`unknown`), which its schema enforces, not that it be
  runtime-captured. (The core — no client derivation — is accepted above.)
- **D-7's demand to "specify precedence in the accepted truth table before the fixture" as an a4
  deliverable — rejected as stated:** `control_room_state_screens.md` is an accepted read-only input
  to this run, so the plan cannot rewrite it; the correction is carried as decision **D8** and the
  fixture is blocked until the controller specifies it.

---

## 8. Controller decisions needed (open choices only — a4)

The genuinely open choices this plan cannot resolve from the accepted direction. Everything else is
scheduled with a default.

| # | Decision | Why it blocks | Default if silent |
|---|---|---|---|
| D1 | Does the supervisor gain an **ack/seen bit** (so `done` ≠ `idle` can be real)? | F05 is unwritable without a measured ack signal (the load-bearing rule); a client write to an observe-only rail needs a typed door (a3 T-13) | F05 stays parked; `done`/`idle` remain colour+word only |
| D2 | Is a read-only **receipt-verify** affordance allowed (no new mutating route class)? | v2 §4.2 C10 is ADAPT-gated on this | not scheduled |
| D3 | Is the astra enablement in scope — the repo `MODEL_WHITELIST` entry (F26a) **and** the host config mount (F26b)? | orthogonal to the UI thesis; F26a is a repo constant change, F26b is a host act (a3 T-12) | F26a scheduled; F26b parked until the controller performs the mount |
| D4 | Is the v1 proposed restyle (surface ramp/amber+cyan) wanted now, or after the mechanics? | F25a/F25b touch every region | after the first wave; F25a first, then F25b |
| D5 | Does the campaign auto-generate child specs (a2 W1), or are children authored? | spend-safety and the spec-lifecycle write path | authored children; the drive is a ranking aid |
| D6 | Is the class-B scorecard **human-scored** or machine-generated? | a machine-generated scorecard makes the class-B acceptance circular (a3 T-10) | human-scored; a machine-generated scorecard is rejected |
| D7 | Does the glance projection gain a per-run supervisor-attention axis **and** a server-derived degraded summary? | F04's genuinely-independent second axis and parked F27 are unwritable until a producer exists (the load-bearing rule; a3 D-6) | not this facelift; F27 stays parked |
| D8 | What precedence applies when two sources disagree, and is `partial`/`history_capped` authoritative? | F03/F14's two-sources fixture has no specified winner, so it can pass vacuously (a3 D-7); the truth table is an accepted read-only input, so specifying it is a controller act | the two-sources fixture stays blocked until precedence is specified |
