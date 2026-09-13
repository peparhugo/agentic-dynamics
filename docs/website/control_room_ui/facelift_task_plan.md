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
silent drop. `F01a/F01b/F02/F03` (verification substrate) is the enabler every row depends on and
carries no region of its own.

| Prompt deliverable | Task(s) | Corrected form (v2 §5) |
|---|---|---|
| R0 wallboard | F07 | **Not** a KPI wallboard: R0 is the scope/truth strip (`ON-G1`/`ON-G6`) with per-value provenance and counts as filters (v2 §5.1). |
| R1 inbox | F08, F09, F10 | Counts-as-filters with the refresh-age caveat; one expand-in-place item; flood/pause/grants with pause a *confirmed controller act*. |
| R2 tiles (incl. E10 row legibility) | F11, F12 | Tiles become run-ledger rows; the E10 `.run-row` contract (identity, target, model×attempt, phase n/t, state, live, claim/proof, commit, cost-provenance, eligibility, receipt; `control_room_wireframe.md:113`) is preserved at both breakpoints. |
| R3 KPI/health/composition | F13, F14, F15 | Five `ON-G4` values as a bounded constraint ledger (not money cards); degraded summary derived from measured statuses (not a vanity score); composition stated in words. |
| R4 session surface | F16, F17, F18, F19, F20 | R4b one-stream feed + governed action band; R4c typed ladder + causal spine; R4d step timings; size-gated payloads; governed steer/reply. |
| State language (glyph/colour/rhythm/seen/ack) | F04, F05, F06 | Rhythm dropped (not identity, v2 §5.2); state = glyph+word+colour+settled timestamp on **two independent axes**; seen/ack watermark; transition-only announcer. |
| Visual tokens | F25 | Surface ramp, one operator amber + one machine cyan, mono data type, chrome only on active/selected, motion only on transitions — under the restraint budget. |
| Add: live-log lens | F21 | Off the resting screen; per-cell event kinds with colour + filter. |
| Add: pipeline lens | F22 | Per-run phase grid from `step_attempts` (`phases_completed/phases_total`). |
| Add: ask-the-data | F24 | Static `question → lens` map from `spec.rules`; the runtime-LLM variant is **DO-NOT-COPY** (v2 §5.3). |
| Add: counters-as-filters | F08, F07 | Query-grammar chips; counts link to their lens; never a bare delta from a stale poll. |
| Add: toast rail | F23 | Bounded, per-kind durations, active-view silent, deep-link only, never a second announcer. |
| Astra fleet enablement | F26 | Repo-side **verify-only**; the config-mount change is a controller/host act (`control/model_policy.py:27-29`). |

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
| Browser-free render gate | `python3 scripts/verify_control_room_rendering.py --check-fixtures` | `scripts/verify_control_room_rendering.py:28-36` |
| Full render gate (Playwright) | `python3 scripts/verify_control_room_rendering.py` (or `agentic-dynamics validate render`) | same; exit 0 PASS / 1 FAIL / 2 no browser |
| Style gate | `python3 scripts/verify_control_room_rendering.py --style` | contrast/forced-colors/reduced-motion class; flag at `scripts/verify_control_room_rendering.py:2294` |
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
| V | verification substrate | F01a, F01b, F02, F03 | no (enabler) — closes the a6 gate misses first |
| S | state language | F04–F06 | yes (identity + honesty) |
| R0 | scope / truth strip | F07 | yes |
| R1 | attention inbox | F08–F10 | yes |
| R2 | run ledger / rows | F11–F12 | yes |
| R3 | money / health / composition | F13–F15 | yes |
| R4 | session surface | F16–F20 | partially (drill-down) |
| L | lenses and adds | F21–F24 | partially |
| T | visual tokens | F25 | yes (restyle) |
| A | fleet enablement | F26 | no (unblocks the astra adversary) |

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
| **F01a** | Can the gate no longer pass on a duplicate/overwritten selector, an answer that overflows its region, or a label hidden in a 1×1px clip? | `scripts/verify_control_room_rendering.py` G-1/G-3/G-5/G-6 uniqueness/overflow/legibility hardening | Browser-free gate passes on F-0; a **seeded-bad fixture set** (duplicate selector, overflowing answer, clipped label) makes the gate exit 1 | — | verification | [M] | M |
| **F01b** | Can the gate no longer pass on a value that disagrees with its fixture (money unknowns, marginals, row fields, answer/parent uniqueness)? | gate G-10/G-11/G-13/G-14/G-15 value/fixture semantics | a **seeded-bad fixture set** (wrong `ON-G4` value, wrong `top/other/unknown` count, duplicated answer writer) makes the gate exit 1, independently of F01a | — | verification | [M] | M |
| **F02** | Do the four canonical test classes (geometry, blind comprehension, browser/a11y, event/state) each exist and fail on a seeded violation? | gate classes B (scorecard schema + recorded pass) and A/E cases; `apps/control_room/verification/b_comprehension.json` | `validate render --a11y` green; `b_comprehension.json` validates against its schema **and a seeded recognition miss makes the class-B check fail** (a cited-but-unbuilt scorecard is not an acceptance; the file is absent in the working tree today, so this task is unambiguously net-new) | F01a, F01b | verification | [M]/[P] | M |
| **F03** | Do the forcing fixtures the new mechanics need exist (saturated inbox, approval flood, stale/queue-unavailable, oversized payload, two-sources-disagree, cost-unknown-never-zero)? | `verification/fixtures/F-8…F-12` + gate assertions | each fixture renders and the gate asserts its distinguishing field; empty fixtures fail | F01a, F01b | verification | [M] | M |

**Size bound (a3 T-2).** F01 is split into **F01a** and **F01b** from the start, each with its own
seeded-bad fixture that fails independently. A single session landing both is an economy, never a
prerequisite, so the one-session bound is never violated.

### Workstream S — state language (identity and honesty)

The direction's state contract is two-axis and never colour-only (direction §12.1; v2 §4.2 O2/T2).
V2 killed the v1 rhythm-as-identity idea (§5.2). The state is **glyph + word + colour + a settled
timestamp**; motion is only a state transition (100–240 ms, collapsed under reduced motion).

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F04** | Do **both** state axes (lifecycle and supervisor attention) render independently as glyph+word+colour+settled-timestamp, does an unmapped enum degrade to `unknown`, and can the axes disagree without one overwriting the other? | state token map + `app.js` renderer + `style.css` tokens | `pytest tests/test_control_room_static_views.py` + a unit test that an unknown enum renders `unknown`; a fixture where lifecycle `done` carries attention `stale` renders **two independent `data-*` fields** (direction §12.1/§12.2.5, a3 D-1) | F01a | presentation | [M] | S |
| **F05** | Can "done" be distinguished from "idle" with a seen/ack watermark whose acknowledgement is recorded, without inventing a second operational truth? | supervisor-flag ack bit + `app.js` seen watermark + ack write → decision record | `tests/test_control_room_glance_integrity.py` (no client guess) + ack authority test (P1 within lease, behind the confirm bar, receipt written) | F04; **controller decision D1** | behavior | [M]/[P] | M |
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
| **F08** | Are counts addressable filters (composing a visible query grammar) whose any displayed delta carries the refresh age, so a stale poll cannot render as a trend? | R1 counts + filter chips + query serialiser | gate G-14 counts/totals + a click-through filter test; a stale fixture asserts the age, not an unqualified delta (A-6) | F01a, F03 | behavior | [M]/[X] T3,T4 | M |
| **F09** | Does one attention item expand in place into its report, with a single compact empty state (no repeated filler cards)? | R1 item renderer | fixture F-1 (one waiting / one failed / one money-risk) + screenshot + gate asserts one empty state, not N cards (A5-D7) | F07, F08 | structure | [M]/[X] C3 | M |
| **F10** | Are approval-flood, pause, and standing-grant controls present, with pause as a *confirmed controller act* — never a threshold-triggered automatic steer? | R1 flood/pause/grants region + `services/` confirm path | a **mutations-boundary state test** (patterned on `tests/test_control_room_parity.py`) that fails if pause is reachable without the typed door; receipt fixture; flood fixture renders a labeled confirm (A-4). The render gate is **not** this task's acceptance (a3 D-4) | F01a, F03, F09 | behavior | [X] C4,C5,C6 | M |

### Workstream R2 — the run ledger and its rows

The repaired facelift already passed the r3/r4 adversaries (`docs/reviews/control_room_facelift_repair_design.md`,
`..._repair_ia.md`); the E10 row legibility contract (session band, row-lease, claim/proof,
source/receipt) is now the baseline. This workstream must **preserve** it while adding the ledger
mechanics, and must close the residual mobile truncation finding (A5-D2/A5-D3).

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F11** | Does every actionable row keep the E10 legibility contract at both breakpoints — identity band, attached lease/cost band (reserved vs settled, source, headroom), paired ADVISORY/MEASURED marks, eligibility + receipt — with no ellipsised identity on mobile? | `.run-row` markup + `app.js` renderer + tokens | gate G-13 compares **row values** incl. `spec/cell` (a6 G-13 gap) + **visible text equals the fixture value and no label is clipped** (a3 T-6, a6 G-5/G-6); the mobile blind-comprehension half is satisfied once F02's scorecard is green. A5-D2 row cost band present | F07, F04, F02 | structure | [M] | M |
| **F12** | Does each in-flight/failed run show its phase text and phase age, with a total map to `RunState`/attempt and an explicit `unknown` for unmapped phases? | attempt-phase renderer + mapping table | `pytest tests/test_control_room_static_views.py` + a unit test of the exhaustive map (unknown → `unknown`, never the raw code as a label) | F04 | behavior | [M]/[X] O4 | S |

### Workstream R3 — money, health, composition

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F13** | Do all five `ON-G4` values render at rest in a bounded constraint ledger with per-value provenance and a money-risk exception — never as free-floating money cards? | `data-region="R3a"` + cost block | gate `ON-G4` (all five values) + provenance chips on each + F-03 money-risk exception; a6 G-10 provenance gap closed; a `cost_source=unknown` fixture renders the literal `unknown` and **never `0`/blank** (state-screens `S-7`, a3 D-2); a hidden-but-clipped label fails (a3 T-6) | F01b, F04, F11 | presentation | [M] | M |
| **F14** | Does `ON-G6`/R3b render a degraded summary **derived from measured statuses** with its mapping exposed, instead of a composite vanity score? | R3b degraded summary + mapping | gate `ON-G6` + F-03 two-sources-disagree fixture; the mapping is rendered/`title`-exposed; no single score field exists without inputs (v2 §5.4/A-10) | F01b, F04, F03 | presentation | [M]/[C] | M |
| **F15** | Does R3c state `top`/`other`/`unknown` in words (never `t/o/u`), with bounded buckets and the fixture's counts asserted? | R3c marginals | gate G-11 extended to assert bucket values + fixture counts (a6 legibility gap) | F01b | presentation | [M] | S |

### Workstream R4 — the session surface

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F16** | Does R4b give exactly one selected worker a bounded live event feed (replay → `replay_complete` → live, follow/pause) plus a governed action band? | R4b region + one-stream guard | one-stream test (direction §12.2.2) + authority test for the action band + receipt fixture; gate R4b class | F01a | structure | [M] | M |
| **F17** | Does R4c render the evidence ladder with the repository's typed rungs and a five-stage causal spine for the selected decision? | R4c region + causal-spine renderer | fixture with one waiting / one failed / one money-risk; gate asserts typed rungs and the spine stages (v2 C8) | F16, F04 | structure | [X] C8 | M |
| **F18** | Does R4d show per-attempt timings each as `measured` or an explicit `unknown` (never a fabricated `0`), with the fleet aggregate in the `L-WORKFORCE` lens? | R4d region + `L-WORKFORCE` lens | gate asserts `data-state=measured\|unknown`; a missing-writer fixture renders `unknown`; resting gate unchanged (v2 O6) | F16, F04 | behavior | [M]/[X] O6,HT3 | M |
| **F19** | Does a heavy payload/JSON surface gate on a serialization probe and mark truncation/partiality instead of parsing/rendering unbounded input? | size-gate helper + disclosure | unit test at/below/above threshold + a `partial` marker renders (v2 L4); F-11 oversized fixture | F17 | behavior | [X] L4 | S |
| **F20** | Does R4 offer a governed steer/reply that shows target, scope, reversibility, and writes a receipt — and refuses to steer without them? | R4b action band + `services/mutations.py` path | authority test (no unguarded terminal write; P1 within lease) + receipt fixture (A-12) | F16 | behavior | [M]/[X] H2 | M |

### Workstream L — lenses and adds

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F21** | Does the live-log lens show per-cell event kinds with colour and filter, off the resting screen? | new lens in `parity.js` `PANELS` + panel DOM | lens fixture desktop/mobile; resting gate unchanged; lens hidden at rest | F01a, F13 | structure | [X] Brain | M |
| **F22** | Does the pipeline lens render the per-run phase grid from `step_attempts` using the packet's `phases_completed/phases_total`? | pipeline lens + renderer | lens fixture; gate asserts the phase grid counts | F01b, F12 | structure | [M] | S |
| **F23** | Does a bounded toast rail exist (max N queued, per-kind durations, active view silent, click deep-links only) without duplicating the polite live region? | toast module + tokens | unit test of the queue/duration policy; a11y test that the live region is transition-only and the toast is not a second announcer | F06 | behavior | [X] Herdr | M |
| **F24** | Can a user question map to a recommended lens **statically** from `spec.rules`, with a test that **fails on construction of any outbound model client** (replacing the v1 runtime LLM lens)? | static `question → lens` map | a client-spy test that goes red if the lens path builds a model call; every recommended lens exists in `PANELS`; no chart renders without question/baseline/fallback (direction §7, A-3, a3 D-4) | F21, F22 | structure | [P]/[X] | S |

### Workstream T — visual tokens

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F25** | Do the accepted visual tokens (surface ramp, one operator amber + one machine cyan, mono data type, chrome only on active/selected, motion only on transitions) hold contrast in all three themes and forced-colors without violating the restraint budget? | `style.css` token block | `validate render --style` + `--a11y` green in dark/light/forced-colors; a no-decorative-pulse assertion; contrast gate. **Scheduled as the first task of the second wave**, after the structure frontier freezes (a3 T-4) | F04, F07 | presentation | [M]/[P] | M |

### Workstream A — astra fleet enablement

| ID | Question | Artifact | Acceptance (named gate) | Deps | Layer | Class | Size |
|---|---|---|---|---|---|---|---|
| **F26** | Can the ladder's containerized cells address `openai/gpt-6-astra` (the host config maps it, but `control.model_policy` warns containerized fleets need the entry in their config mount)? | a verification note + the repo-side resolution check; the **host config-mount change is a controller/host action**, not a repo edit (a3 T-5) | a spawn/admission dry-run with `--model openai/gpt-6-astra` reports whether the model resolves; if it does not, F26 is `parked` on the host action, never marked done by a repo edit | — | behavior | [M] | S |

---

## 4. Minimal first wave and the stopped-by gates

### 4.1 The smallest set that delivers visible improvement

**First wave = `{F01a, F01b, F02, F04, F07, F11}`** (revised by a3 `D-5`/`T-1`: the wave must
contain every gate its stopped-by list cites).

| Why each is in | F01a/F01b the gate must see the change | F02 the legibility scorecard must exist before it is cited | F04 the two-axis identity grammar is the product | F07 R0 truth strip (corrected) | F11 the row is the run object |
|---|---|---|---|---|---|

Rationale: F01a/F01b are the prerequisite (a change the gate cannot fail on is not gated). F02 makes
the blind-comprehension acceptance real before F11 cites it. F04/F07/F11 are the three
screenshot-level carriers of the direction's thesis (state, truth, row identity, direction
§4.4/§16). F06 (staleness/announcer) and F08 (counts as filters) are **second wave** — they are
small and high-value but the wave is kept minimal and self-contained. Nothing in the first wave adds
a new route, a new persistence plane, or a model call.

Everything else (`F03, F05, F06, F08–F10, F12–F26`) builds on the first wave; the drill-down work
(F16–F20) is deliberately **not** first-wave because the resting screen must pass the recognizability
test before the inspector is deepened.

### 4.2 Stopped-by gates (a wave does not start until these are green)

| Gate | Condition |
|---|---|
| Render gate, 3 breakpoints × 3 themes | 1440×900 / 1024×768 / 390×844 in dark, light, forced-colors; zero failures |
| One-resting-screen glance check | all `ON-G1..G7` answers present, complete, non-zero, inside the initial viewport with no page/region scroll |
| Blind-comprehension scorecard | the §4.2 five sentences + the seven `ON-G1..G7` answers, recorded (class B) |
| Feature-parity class-P | every `parity_inventory.json` record placed/present/wired/non-empty or a documented empty state |
| Doc lifecycle + fast-path gate | `pytest tests/test_doc_lifecycle.py tests/test_fast_path_gate.py` green |

---

## 5. Sequencing (dependency edges as the compiler sees them)

```text
F01a ──▶ F02        F01b ──▶ F02        # the two gate frontiers both feed the test-class suite
F02  ──▶ F11                            # blind-comprehension acceptance exists before it is cited (a3 D-5/T-1)
F01a ──▶ F03, F04, F06, F08, F10, F16, F21
F01b ──▶ F03, F13, F14, F15, F22
F04  ──▶ F05, F07, F11, F12, F13, F14, F17, F18, F25   # one state vocabulary, no half-migration (a3 T-3)
F07  ──▶ F09, F11, F25
F08  ──▶ F09 ──▶ F10
F11  ──▶ F13
F12  ──▶ F22
F13  ──▶ F21 ──▶ F24        F22 ──▶ F24
F16  ──▶ F17 ──▶ F19 ;  F16 ──▶ F18 ;  F16 ──▶ F20
F26 (independent, verify-only)
```

Reading the edges: the two gate frontiers `F01a`/`F01b` both feed `F02`; `F11` requires `F02` (so
the blind-comprehension acceptance exists before it is cited, a3 `D-5`/`T-1`). `F04` produces the
state vocabulary consumed by `F05,F07,F11,F12,F13,F14,F17,F18,F25`. `F13`/`F14`/`F17`/`F18` carry
the `F04` edge so a region cannot land on the retired vocabulary (a3 `T-3`). `F25` is deliberately
last in the second wave (a3 `T-4`).

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
| Five `ON-G4` values as a constraint ledger; derived degraded summary (not a score) | Presupposed + corrected v2 §5.4/§5.5 |
| Live-log and pipeline lenses; static recommended-lens map | New lenses; the LLM variant is **DO-NOT-COPY** (v2 §5.3) |
| Astra container mount | New local enablement; makes the parked astra adversary real |

---

## 7. Controller decisions needed (finalized — a4)

| # | Decision | Why it blocks | Default if silent |
|---|---|---|---|
| D1 | Does the supervisor gain an **ack/seen bit** (so `done` ≠ `idle` can be real)? | F05 is unwritable without a measured ack signal (the load-bearing rule) | F05 stays parked; `done`/`idle` remain colour+word only |
| D2 | Is a read-only **receipt-verify** affordance allowed (no new mutating route class)? | v2 §4.2 C10 is ADAPT-gated on this | not scheduled |
| D3 | Is F26 (astra mount) in scope for this facelift, or a separate fleet-enablement task? | it is orthogonal to the UI thesis; the actual change is a host config-mount act | scheduled as an independent, verify-only task; host change is the controller's |
| D4 | Is the v1 proposed restyle (surface ramp/amber+cyan) wanted now, or after the mechanics? | F25 touches every region | after the first wave; F25 is the first task of the second wave |
| D5 | Does the campaign auto-generate child specs (a2 W1), or are children authored? | spend-safety and the spec-lifecycle write path | authored children; the drive is a ranking aid |

---

## 8. Adversarial dispositions (a3 → a1)

Every a3 finding is dispositioned. **Accepted** = the plan changed; **rejected** = a one-line reason.

| a3 | Status | Resolution in this plan |
|---|---|---|
| D-1 two axes | **accepted** | F04 now renders and tests lifecycle + attention as two independent fields (fixture: lifecycle `done` with attention `stale`). |
| D-2 unknown-never-zero | **accepted** | F13 acceptance asserts the literal `unknown`, never `0`/blank; F03 adds the cost-unknown fixture. |
| D-3 F24 layer | **accepted** | F24 moved from `intent` to `structure`; the DAG carries no back-edge. |
| D-4 behavioral acceptance | **accepted** | F10 names a mutations-boundary state test; F24 names a client-spy test; neither cites the render gate. |
| D-5 first wave / B scorecard | **accepted** | First wave now `{F01a,F01b,F02,F04,F07,F11}`; F11 requires F02. |
| T-1 cited-but-unbuilt gate | **accepted** | F02 ships `b_comprehension.json` with a seeded miss; F11 cites G-13 until F02 is green. |
| T-2 F01 not small | **accepted** | Split into F01a/F01b with independent seeded-bad fixtures. |
| T-3 half-migrated room | **accepted** | F13/F14/F17/F18 require F04; the `requires`/`produces` gate refuses the retired vocabulary. |
| T-4 F25 timing | **accepted** | F25 is the first task of the second wave, after the structure frontier freezes. |
| T-5 F26 host action | **accepted** | F26 is verify-only; the config-mount change is a controller/host action; otherwise `parked`. |
| T-6 rendered clipping | **accepted** | F11/F13 assert visible text equals the fixture and no label is clipped. |
| T-7 evidence classes | **accepted** | F24 `[P]/[X]`, F26 `[M]`; classes now follow the falsifier named in the acceptance. |
| W-6 readiness filter | **accepted** | Reflected in the a2 revision (readiness is a hard admissibility filter). |
