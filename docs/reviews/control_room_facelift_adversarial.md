---
status: accepted
---

# Control Room facelift — adversarial review (phase `a3_adversarial`)

**Date:** 2026-09-13
**Phase:** `a3_adversarial` of `workflows/repository/control_room_facelift_review.yaml`.
**Reviewer:** the document adversary, standing in for the GPT Astra adversary. The fleet does **not**
whitelist `openai/gpt-6-astra` for containerized cells today — `control.model_policy` states the
host config maps it but containerized fleets need the same entry in their config mount
(`src/agentic_dynamics/control/model_policy.py:29`), and `workflows/repository/control_room_facelift_review.yaml:135`
already parks the enablement. This pass is therefore a repository-grounded review, not a second-model
vote; `a1` F26 makes the astra arm real for the next pass.
**Targets:** `docs/research/control_room_ui_reference_synthesis.md` (v1), the accepted direction
(`docs/research/control_room_direction.md`), `docs/website/control_room_ui/facelift_task_plan.md` (a1),
and `docs/website/control_room_ui/dynamic_workflow_design.md` (a2).
**Method:** attack the claim, the question, and the acceptance — not the prose. Each finding is a
required correction plus the acceptance that proves it. No praise; no restatement.

---

## 1. Design attacks (the facelift design and the direction it presupposes)

| # | Sev | The flawed claim | Required correction | Acceptance that proves the correction |
|---|---|---|---|---|
| **D-1** | high | a1 F04 equates "the state contract" with a single `glyph+word+colour+timestamp` vocabulary. The direction requires **two independent axes** — lifecycle vs supervisor attention — never collapsed (direction §12.1, §12.2.5; `control_room_ia.md` §4). | F04 must render and test both axes (a lifecycle token and an attention token) and prove they can disagree without one overwriting the other. | A fixture where a lifecycle `done` run carries attention `stale` renders both tokens distinctly; gate asserts two independent `data-*` fields, not one merged state. |
| **D-2** | high | a1's "no fabricated values" coverage is incomplete: F06 covers stale/unavailable, F14 covers two-sources-disagree, but **no task asserts the cost `unknown is never 0` literal** on the row or in `ON-G4` (direction §8; state-screens `S-7`; v2 C11). | Extend F13's acceptance (or add a dedicated assertion) that every consequential money value renders the literal `unknown` and never `0`/blank, verified against the F-04 fixture. | A fixture with `cost_source=unknown` renders `unknown`; a seeded `0` render fails the gate (state-screens `S-7`). |
| **D-3** | high | v1 §4.5.3's "ask the data" lens is scheduled in a1 as F24 with a static map — but F24 sits in the **intent** layer while depending on structure tasks F21/F22. A layered workflow cannot have an intent question wait on its own descendants. | Re-layer F24 as a structure/behavior refinement (it is a lens whose question is already intent-fixed), or rename the layer so the ordering is honest. | The dependency DAG renders F24 after F21/F22 with no back-edge across layers; a cycle check passes. |
| **D-4** | medium | a1 F10 (approval pause) and F24 (no model call) are accepted by behavioral facts ("no unconfirmed pause path", "test that no model call is made") that a screenshot render gate **cannot** pin. The direction's gate order separates browser/screenshot from event/state for exactly this reason (direction §18, p5 IA8). | Both tasks must name a state-class test with a **spy/guard that can fail**: a mutations-boundary test that fails if a pause is reachable without the typed door, and a client test that fails on construction of any outbound model client. | The named test goes red when the guard is removed; the render gate is not cited as their acceptance. |
| **D-5** | medium | The plan claims the first wave "delivers visible improvement" but F01/F02 only build gate capability and F11's acceptance cites the class-B scorecard F02 owns — so the wave cannot be graded as landed until F02 exists, yet F02 is not in the wave. | Either put F02 in the first wave or change F11's acceptance to a non-B gate (G-13 row values) until F02 lands. | The first wave's stopped-by list is satisfiable with only the tasks actually in the wave. |

---

## 2. Decomposition attacks (a1)

| # | Sev | The flawed claim/question | Required correction | Acceptance that proves the correction |
|---|---|---|---|---|
| **T-1** | high | a1 F11 (row legibility) and F07 (R0) both cite a "blind-comprehension fixture" as acceptance, but a6 found the class-B scorecard does not exist and is not scored in `gate_report.md` (`docs/reviews/control_room_facelift_ia.md` B-1…B-11 **FAIL**). A cited-but-unbuilt gate is a vacuous acceptance. | F02 must ship the scorecard **as a checked artifact with a seeded miss** before any task may cite it; until then F07/F11 cite G-13/G-14 plus a retained screenshot. | `b_comprehension.json` validates against its schema; deleting a required recognition makes the class-B check fail. |
| **T-2** | high | a1 `F01` is not small by its own rule: it lands nine independent gate holes and the plan itself concedes it "may split". A task that may split violates the one-session bound. | Ship **F01a** (uniqueness/overflow/legibility: G-1/G-3/G-5/G-6) and **F01b** (value/fixture semantics: G-10/G-11/G-13/G-14/G-15) as two gated tasks from the start, each with its own seeded-bad fixture. | Each of F01a/F01b has a distinct seeded-bad fixture that fails its own gate; neither alone makes the other's fixtures pass. |
| **T-3** | high | a1's ordering risks a **half-migrated room**: F13/F14/F15 (R3 regions) and F17/F18 (R4) have no dependency on F04's state grammar, so they can land on the old vocabulary while F04/F07/F11 land the new one. | F13/F14 and F17/F18 must `requires` F04; the DAG must refuse a region built on the retired vocabulary. | The compiler's `requires`/`produces` gate refuses the F13 spec until F04's state fields are in `produces`. |
| **T-4** | medium | a1 F25 restyles every region as one task, and is only gated by `--style`/`--a11y`. It can land mid-structure and force re-tokenising of regions still being built, multiplying the render gate. | Land F25 as the **first task of the second wave**, after the structure frontier freezes; split base tokens from accent/chrome if needed. | F25 is not in the first wave and all structure tasks are green before it starts. |
| **T-5** | medium | a1 F26 asks a repo task to "clear the `model_policy.py:29` warning", but the fix is a **host config-mount change** outside the worktree — a host/ops act, not a repo edit. The plan risks claiming completion by editing only the repo. | Frame F26 as **verify-only** in the repo, with the host mount change named as a controller/host action; the acceptance is a resolution check, not a config edit. | The acceptance reports the container can address the model; if it cannot, F26 is `parked` on the host action, not marked done. |
| **T-6** | medium | a1 omits the a6 findings that are already **code-level gate** fixes from the plan's own scope: G-5 (labels in 1×1px clips still pass) and G-6 (an attribute is used as a proxy for actual clipping). These are legibility failures, not only gate holes. | Fold the *rendered* fix (do not clip labels; compare visible text to fixture) into F11/F13 acceptance, not only into F01a/b. | A fixture with a hidden-but-clipped label fails the gate; the visible text equals the fixture value. |
| **T-7** | medium | a1's evidence-class column mixes producer status with intent: F24 is `[P]` but its real risk is `[X]` (OpenVizAI) versus a `[P]` composition choice; F26 is `[M]/[P]` for a fact that is an environment observation, not a measurement. | Classify by **who can falsify it**: environment facts `[M]`/`[C]`, external mechanisms `[X]`, placements `[P]`. | Each task's class matches the falsifier named in its acceptance. |

---

## 3. Dynamic-workflow attacks (a2)

| # | Sev | The flawed claim/question | Required correction | Acceptance that proves the correction |
|---|---|---|---|---|
| **W-1** | high | a2 claims "no new top-level mechanism" and reduces the addition to one `select_next_question` function — but generating and admitting a **child spec** also requires a spec-lifecycle write (`experiments/specs/index.json`, `scripts/spec_status.py`), budget carry-over into the child lease, and a resume/lineage key. That is feature-sized, not a field. | Enumerate the full child-spec admission surface (lifecycle index update, budget carry-over, parent/child lineage in the run ledger), or bound the addition to **authored children** (the controller writes them) and drop the auto-generation claim. | The chosen surface is exercised end-to-end by the worked example: a child appears in the spec index with correct lineage and its own lease, or the design states children are authored. |
| **W-2** | high | a2's drive is non-convergent as written: `uncertainty(q)` is `1.0` whenever the acceptance rule is *unimplemented*, and many tree leaves start unimplemented — so the threshold never trips and the tree selects forever. | Define convergence on **posterior** uncertainty: a question's uncertainty falls only when its acceptance is *instrumented and answered*; an unimplemented rule makes the question **inadmissible** (must expand), not maximally novel. | A tree with N unimplemented acceptances converges because each expands to instrumentation leaves that can reach `uncertainty ≤ threshold`. |
| **W-3** | high | a2's adversarial loop is described as a "gate the controller commissions", but in the workflow YAML `a3_adversarial` is an **agent phase** that would run automatically — which, if generalized, is a runtime self-attack mechanism the design said it would not add. | State unambiguously that the loop is a **static authored phase** (as the existing spec shows), never a runtime scheduler; no new orchestration is implied. | The design contains no code path that launches an adversary session; the only invocation is the authored phase. |
| **W-4** | medium | a2's `score = w_u·uncertainty + w_r·regret + w_e·effect` adds incommensurable units (a `[0,1]` scalar, a loss-unit regret, an outcome-unit effect) with undefined weights. The argmax is not well-defined. | Either normalize every term to `[0,1]` with named weights, or make selection **lexicographic** (readiness filter → uncertainty → regret → effect), which the three declared strategies map onto cleanly. | Two questions with the same uncertainty but different regret order deterministically; the ordering is stable across runs (seed/ties specified). |
| **W-5** | medium | a2 routes new questions/conclusions through `emit_phase_finding`, whose producer writes authority `MEASURED` when `test_executed_success` is a bool and `ADVISORY` otherwise (`knowledge/knowledge_ingestion.py:538-540`). An open question is neither measured nor a finding; emitting it pollutes the knowledge authority model. | Cap the emission to the phase result / `step_attempts`; if a question must enter the KB, give it an explicit ADVISORY `source_type` and a `causes` link to the observation that raised it — or do not emit it. | A question emitted to the KB carries authority `ADVISORY` and a resolvable `causes`; a measured finding keeps `MEASURED`. |
| **W-6** | medium | a2's worked example breaks its own tie by "dependency depth", a signal not in the score — an ad hoc rule that hides a scheduling bug. | Make **readiness (all `requires` satisfied) a hard admissibility filter before scoring**, so a question with unmet dependencies is never in the candidate set and the tie cannot arise. | The candidate set at each step contains only questions whose `requires` are green; the worked example's first move is unambiguous without depth. |
| **W-7** | medium | a2 asserts `budget_usd`/`max_attempts` are the brake but does not say **whose** budget a child spends: the campaign lease, a per-child lease, or both. Ambiguity here is a spend-safety hole. | State the lease shape: children reserve against the **campaign** lease (`control.admission`), the parent's reserved amount is not double-counted, and an exhausted campaign lease denies the child. | An exhausted campaign lease denies child admission; the parent's reservation is reconciled once (settlement `matched`). |

---

## 4. Verdict

**REWORK REQUIRED.** The design's direction is sound and a1/a2 are close, but the ledger is not
empty. Two design claims are incomplete (`D-1` two axes, `D-2` unknown-never-zero), the first wave
can cite a gate it does not yet build (`T-1`, `D-5`), the largest task violates its own size bound
(`T-2`), the region tasks can land on a half-migrated vocabulary (`T-3`), and the dynamic-workflow
design overstates its minimalism while under-specifying convergence and budget ownership
(`W-1`, `W-2`, `W-7`). These are corrections to questions and acceptance, as required — none is a
rewrite of the direction.

**Disposition of every finding is in `docs/website/control_room_ui/facelift_task_plan.md` and
`docs/website/control_room_ui/dynamic_workflow_design.md` after phase `a4_revise`:** an accepted
finding becomes a correction to a task/question/acceptance; a rejected finding gets a one-line
reason. The controller decisions that remain open are listed at the end of a1/a2.
