---
status: accepted
---

# Control Room facelift — independent adversarial review v2 (DeepSeek flash)

**Date:** 2026-09-13
**Reviewer:** DeepSeek V4 flash — a second adversary, independent of the Astra pass
(`docs/reviews/control_room_facelift_adversarial.md`, phase `a3`).
**Targets:** `docs/website/control_room_ui/facelift_task_plan.md` (**a1**),
`docs/website/control_room_ui/dynamic_workflow_design.md` (**a2**),
`docs/research/control_room_ui_reference_synthesis_v2.md` (**v2**),
`docs/research/control_room_direction.md` (**direction**), and the live source they cite.

**Method.** Same discipline as pass 1: attack the claim, the question, and the acceptance; cite the
artifact line and the source line; no praise, no restatement. The disposition audit checks only whether
a claimed a4 correction **exists in the artifact or the code** — not whether the intent was good.
Findings continue pass 1's series (`N-` nominal reopenings, `T-` task plan, `W-` workflow) so a fold can
address both passes without renumbering. This pass writes the review only; a1/a2 are not modified.

---

## 1. Disposition audit — does the claimed correction exist?

Every a3 finding was dispositioned in a1 §7 / a2 §10. This table checks the claim against the
artifact text and the cited source. Rows not listed are corroborated (existence confirmed; see the
anchor ledger in §5).

| # | a3 item / claim | What the artifact and source actually show | Verdict |
|---|---|---|---|
| **N-1** | **T-11/F04→F06.** a1 §7 claims `F04 → F06, F08, F15, F16, F20` was added (`:402`). | **F06's `Deps` cell is `F01a, F03` — no F04** (`facelift_task_plan.md:209`). F08 does carry F04 (`:224`), but a1 §5's F04 consumer line omits F06 **and** F08 (`:332`). The claimed edge does not exist in the dependency table. | **NOMINAL** |
| **N-2** | **D-6/D-1 attention axis.** a1 claims F04 renders "the packet's emitted `attention.state ∈ {active,none}`" (`:206`). | The producer emits only `"active"`/`"none"` (`apps/control_room/routes/glance.py:568`). F04's acceptance nonetheless says "the fixture uses only the emitted enum **{active,none,unknown}**" and the question asks "can attention be `unknown` while lifecycle resolves" (`:206`). `unknown` is not emitted, and attention is a pure function of `awaiting_approval`, so it cannot be `unknown` while lifecycle resolves. a2 Q15 repeats "(only `active`/`none`/`unknown`)" (`:408`). | **NOMINAL / false enum** |
| **N-3** | **T-10 class-B.** a1 claims F02 splits into F02a (schema + **recorded human pass**) and F02b (gate consumer + seeded miss) (`:187-188`, `:401`). | F02a's acceptance fails only on "deleting the recorded pass or flipping one required recognition" (`:187`). Nothing binds `b_comprehension.json` to a human — no signature/attestation field, unlike the repo's own operator-approval contract (`approvals/<spec>/<phase>_approval.md`). An agent session can author the file and the gate accepts it. The circularity pass 1 named is **not** closed; it is relabelled. | **NOMINAL** |
| **N-4** | **T-12 blocker.** a1 §0.2 names the repo `MODEL_WHITELIST` entry and cites "`control/model_policy.py:27-30`" (`:88`). | `model_policy.py:27-30` is the host-config note plus `SUBSCRIPTION_DEFAULT` (`:27-30`). `MODEL_WHITELIST` lives at `scripts/fleet/spawn_wrapper.py:379-389`. F26a's own row cites it correctly (`:283`), so the §0.2 citation is simply wrong. It resolves to a file that has those lines, so the `docs scan` anchor axis cannot catch it. | **NOMINAL citation** |
| **N-5** | **W-11 de-dup.** a2 §10 claims "Q1/Q12 are de-duplicated" (`:510`). | Q1's `a1 task` cell is "F02a/F02b (acceptance), first-wave gate" (`:393`); Q12's is "F02a, F02b" (`:405`). Both still name the same ids. The §7 coverage gate keys on "two questions claiming the same task as their sole carrier" (`:443`) but the §6 table has **no ownership field** to distinguish "consumed" from "owned", so a mechanical coverage check still flags the pair. | **NOMINAL** |
| **N-6** | **W-13 authority guard.** a2 §4.1 says "the question producer passes `ADVISORY` + `causes` explicitly" (`:331`). | `derive_phase_record` computes authority from `test_executed_success` and takes **no** authority or `causes` parameter (`knowledge/knowledge_ingestion.py:505-540`); `emit_phase_finding` likewise (`:575-582`); the `build_record_from_parts` call at `:555` passes `authority=authority` and no `causes`. Making the claim true needs a signature/record-factory change the §4.1 gap list does not enumerate. | **NOMINAL / unbuilt** |

### Disagreements with pass-1 items it marked resolved

- **T-10 not resolved (N-3).** A recorded *pass* that only a machine compares cannot prove a human
  recognised the seven answers; the fix moved the value into a file, not the provenance into the gate.
- **T-8 not fully closed (T-16).** The full gate now observes the geometry/clip claim, but the paired
  sub-acceptance ("the same seeded set passes `--check-fixtures`") cannot observe it and can pass
  vacuously.
- **W-11 not resolved (N-5).** The de-dup is asserted in prose; the table still collides.

---

## 2. New holes — the task plan (a1)

| # | Sev | The hole | Required correction | Acceptance that proves it |
|---|---|---|---|---|
| **T-15** | high | **F03 is one task whose acceptance includes a fixture it declares blocked.** F03's acceptance carries the two-sources-disagree fixture "**BLOCKED until precedence is specified**" (D8) (`:189`), yet F03 is the single producer F06/F08/F10/F14 depend on (`:224`, `:226`, `:249`, `:250`). A task that cannot go green blocks four second-wave tasks — and the block is not a dependency edge, so the DAG looks healthy. | Split `F03` into `F03a` (the forcing fixtures) and `F03b` (two-sources, gated on D8), or remove the two-sources fixture from F03's acceptance and state it is not produced. | F03a's named gate goes green with the two-sources fixture absent; F03b carries its own D8 dep and is the only task red while D8 is open. |
| **T-16** | high | **F01a's `--check-fixtures` limb is vacuous.** `check_fixtures()` iterates the hardcoded tuple `("F-0"…"F-7")` and asserts only schema facts — `run_counts` keys, ≥8 rows, `ROW_FIELDS` presence (`scripts/verify_control_room_rendering.py:288-304`). The seeded-bad set (duplicate selector / overflow / 1×1px clip) is geometry, which `--check-fixtures` never inspects. "The same seeded set passes `--check-fixtures` (proving the browser path is the discriminator)" (`:185`) passes because the set is out of scope, not because the browser path is required. | Assert that `--check-fixtures` processes the **same seeded fixture ids** (extend the tuple as part of F01a) and that the discriminator is the geometry/clip JS. | With the new clip detector disabled, `--check-fixtures` still exits 0 while the full gate exits 1 on the seeded set; with it enabled, both behave as specified. |
| **T-17** | high | **The gate-of-record table is declared closed but the first wave cites primitives not in it.** §1.3 says "These are the only acceptance primitives a task may cite. A task that cannot name one is not gated" (`:133`), and the table has 14 rows (`:135-150`). The first wave cites: F04's "**client-spy test**" (`:206`), and F02a/F02b's "**class-B check**" (`:187-188`) — §1.3 has `--a11y` and "recorded blind A/B" but **no** client-spy harness and **no** class-B reader. Outside the wave, F09/F10/F16/F17/F19/F22/F23/F24/F26a cite unnamed fixtures/unit tests likewise. | Add the client-spy harness and the class-B reader to §1.3, or split each task so its acceptance names a listed gate. | A check that every §3 acceptance string matches exactly one §1.3 row fails today for F04, F02a, F02b and passes after the gate table and tasks are reconciled. |
| **T-18** | high | **The §5 DAG disagrees with the `Deps` column.** §5 writes `F04 ──▶ F05, F07, F11, F12, F13, F14, F15, F16, F17, F18, F20, F25a` (`:332`) — it omits F06 (N-1) and F08, while F08's row does carry F04 (`:224`). A reader building the DAG from §5 gets a different graph than one building from the table. | Make §5 the render of the deps table, not a hand-kept list; add F06 and F08 to the F04 line. | The union of every task's `Deps` cell equals the §5 edge set (it differs today on F06 and F08). |
| **T-19** | high | **F11 is over the one-session bound and its blind half is a proxy.** F11's acceptance bundles (a) G-13 row values incl. `spec/cell`, (b) visible-text-equals-fixture + the F01a clip detector, (c) "the mobile blind-comprehension half is satisfied once F02a/F02b are green", and (d) an A5-D2/D3 re-adjudication instruction (`:242`). (c) does not run the mobile check; it substitutes "F02a is green". (d) is prose, not an acceptance. | Split F11 into `F11a` (row contract values + clip) and `F11b` (mobile identity blind half, explicitly consuming the recorded scorecard), or delete the parenthetical and the re-adjudication instruction. | F11a goes green in one session with no human input; F11b's gate names the recorded scorecard as its input and fails when the scorecard is absent. |
| **T-20** | medium | **F25b's acceptance is not machine-checkable.** Its named gate is the recorded blind A/B, whose primitive is artifact existence (`:144`, `:277`), but the acceptance also demands "a seeded 'KPI rail' restyle **fails its thesis check**" (`:277`) — a human judgment. | State the machine-observable part (artifact present/valid; the restyle is recorded) and keep the human verdict as recorded evidence, not a tool assertion. | The gate fails on a machine-observable condition (missing/invalid artifact); the seeded restyle's verdict is a recorded field, not a computed one. |
| **T-21** | medium | **The first wave's second axis is not the direction's §12.2.5 axis.** F04 ships `attention.state` derived from `awaiting_approval` (`glance.py:568`); the direction's two-axis contract is "lifecycle vs **supervisor attention**" (`control_room_direction.md:677`). The real axis is deferred to F27/D7 (`:207`, `:433`), yet §0 lists the two axes among what is "Presupposed (not re-litigated)" (`:46`). | Say in §4.1 that F04 partially delivers §12.2.5 and F27 completes it, or drop §12.2.5 from the presupposed list. | The §4.1 rationale contains the partial-delivery sentence; no first-wave task claims the supervisor-attention axis. |

---

## 3. New holes — the dynamic-workflow design (a2)

| # | Sev | The hole | Required correction | Acceptance that proves it |
|---|---|---|---|---|
| **W-15** | high | **The honest-gap list omits the change its own W-13 fix requires.** §4.1 row 3 says the question producer passes `ADVISORY` + `causes` explicitly (`:331`), but the named consumer has no such parameters (N-6; `knowledge_ingestion.py:505-540,575-582`). The gap list is supposed to be complete ("the complete list, each located inside an existing module", `:325`) — it is not. | Add the emit-authority/`causes` signature change (and the `build_record_from_parts` call at `:555`) to §4.1, or define a separate question producer. | A test emits a question phase with `test_executed_success=True` and asserts `ADVISORY` + a resolvable `causes`, using only the listed new surface. |
| **W-16** | high | **The coverage gate is decorative and self-contradicting.** §7 says the guard "refuses an a1 task with no `source` and two questions claiming the same task as their sole carrier" (`:443`), but §6 is "Illustrative, not exhaustive … do not claim to cover all 26 a1 tasks" (`:384-389`). Either the gate demands full coverage (and §6 fails its own gate: no question for F12–F26; Q1/Q12 collide per N-5) or it does not (and it cannot catch an omitted task). The gate is also absent from §4.1's "complete" gap list. | State the gate's exact predicate as an authored artifact (full task coverage, or "no two questions share a sole carrier"), implement it, and reconcile §6. | Running the gate over §6 fails on the known omissions/collision today; after the fix it fails only on a genuinely uncovered task, or §6 is excluded by an explicit stated rule. |
| **W-17** | high | **"Reuses `AdaptSpec.selection` verbatim" is false.** `AdaptSpec.selection` is a single enum value (`experiment_spec.py:631`; `ADAPT_SELECTIONS` `:39`, validated `:1094-1097`). §3 invents a three-level **lexicographic order** (`highest_uncertainty → highest_regret → largest_effect`, `:205-208`) that the compiler neither declares nor validates. | Either declare the lexicographic order as new in §4.1 (with its one-line gap), or drop the "verbatim" claim. | The design names the ordering as a new mechanism in §4.1, and a reader can point to the code that would consume it. |
| **W-18** | high | **The instrumented-uncertainty path has no Question→`RuleSpec` mapping.** §3.1 says an acceptance that "maps to a `RuleSpec` in the campaign spec and attempts exist" yields a posterior (`:223-226`), but the `Question` dataclass has no rule/spec/attempt field (§1, `:58-75`), and the a1 plan's acceptances are gates, not rules. The posterior is undefined for every question in the worked example. | Add the mapping field (e.g. `rule_ref`/`acceptance_rule`) or state the instrumented path is out of scope and selection is readiness + authored priority for all current questions. | The §3.1 falsifier runs on a synthetic instrumented question whose `RuleResult` is built from a named field, not asserted into existence. |
| **W-19** | high | **The red-acceptance brake is ungrounded.** §3.2 parks a question after `max_attempts` "unchanged" reds (`:258`), but no store or field holds the counter, and "unchanged (the same red)" has no equality predicate for a gate (a re-run returns a fresh result). A crash/restart resets an in-memory counter and the loop resumes. | Name the counter's durable location and the equality predicate (e.g. the gate's error-set/fixture-diff hash), or fall back to a hard attempt cap. | A question whose gate stays red parks after `max_attempts`, is not re-selected, and the count survives a process restart. |
| **W-20** | high | **Two worked-example questions re-merge tasks a1 split for the one-session bound.** Q12 maps `F02a, F02b` (`:405`) and Q14 maps `F25a, F25b` (`:407`) — the exact splits §1.2 cites as the canonical expansion (`:109-112`). §1.1 says one session produces the artifact (`:86-94`). The worked example violates the protocol it demonstrates. | Give each split half its own Question, or amend §1.1 to say a Question may span siblings (contradicting the a1 split rationale). | Every §6 row's `a1 task` cell is a single id, and each question's acceptance is one session's gate. |
| **W-21** | medium | **"Drained by the existing workers" is wrong for authored phases.** §4 step 4 (`:313`) and §9 (`:483-485`) say an authored child is "drained by the existing workers"; the Redis queue/`worker.py` drains the fixed `story_jobs` matrix (`scripts/enqueue.py:58-64`), and no spec→job bridge exists (which the design itself admits at `:332`). Authored workflow phases run through the `run_workflow` runner, not the queue workers. | Correct the wording: authored phases run under the workflow runner and the campaign lease; the queue is not their transport. | A replayed child runs end-to-end through the named path with no new scheduler, and the design's transport sentence matches that path. |

**On the honest-gap list itself.** §4.1 correctly names the two large absences (spec→job executor, auto-generation) and the `control_db` column follow-up. It misses W-15 (emit signature), W-16 (coverage gate), W-17 (ordering), W-18 (question→rule mapping), and W-19 (attempt-counter store). "Complete list" is thus not yet true; the gaps that remain are exactly the ones the drive depends on.

**Cross-artifact contradiction.** a1 §7 **rejects** "F04's fixture must be a captured packet" ("the render gate's fixtures are deterministic by construction", `:409-412`), while a2 Q15 **requires** a "captured-packet fixture" (`:408`). One of the two is the a4 position; the pair currently ships both.

---

## 4. Attack the first wave {F01a, F01b, F02a, F02b, F04, F07, F11}

| Task | Executable exactly as specified? | Named gate present in §1.3? | Acceptance that a green run could satisfy without the claimed behavior |
|---|---|---|---|
| **F01a** | Yes (one session; one file). | Yes — full render gate + clip detector. | **Yes** — the paired `--check-fixtures` limb cannot see geometry (T-16). |
| **F01b** | Yes, after F01a. | Yes — browser `_check_semantics`. | No, if the seeded wrong-value fixture is processed by the same path. But §5 writes `F01a ──▶ F02a` (`:328`) while F02a's deps are `F01a, F01b` (`:187`) — a missing edge in the diagram. |
| **F02a** | **No.** Its artifact is "a recorded **human** pass per direction §4.2" (`:187`). No agent session can produce a human-recorded artifact; the task is M-sized only if a human supplies the pass, which is an external dependency the plan does not schedule. | **No** — cites a "class-B check" absent from §1.3 (T-17). | **Yes** — an agent-authored `b_comprehension.json` passes the recorded-pass check (N-3). |
| **F02b** | Yes, once the file exists. | **No** — same class-B reader gap (T-17). | **Yes** — schema-valid + seeded-miss proves the validator rejects its own row, not that a human recognised the seven answers (N-3). |
| **F04** | Yes (one session; `app.js`/`style.css`). | **No** — cites a "client-spy test" absent from §1.3 (T-17). | **Partly** — the acceptance's "emitted enum {active,none,unknown}" is false (N-2); a fixture-author could satisfy the unknown-enum test with a value the producer never emits. Second axis is lifecycle-derived (T-21). |
| **F07** | Yes, after F01a/F04. | Yes — render gate `ON-G1`/`ON-G6` (the no-tile assertion is a new limb of that gate, not a separate primitive). | No — the no-tile assertion is a real, falsifiable check. |
| **F11** | **No** — it depends on F02a/F02b (human-gated) and bundles four claims (T-19). | Partly — G-13 + the clip detector are in §1.3; the mobile blind half is a proxy. | **Yes** — "satisfied once F02a/F02b are green" is satisfied by a green F02a that no human touched (N-3). |

**First-wave stop conditions.** The wave's stated "smallest set" (`:292`) is correct only as a set of
*file producers*; as a *validated* set it is blocked by F02a's human dependency and by T-17's gate
gap. The stopped-by list (`:311-320`) also includes "Feature-parity class-P" and "Doc lifecycle +
fast-path gate", which no first-wave task produces — fine as pre-existing gates, but the §4.1
rationale ("the wave must contain every gate its stopped-by list cites", `:292-295`) does not hold for
those two.

---

## 5. Anchor ledger (newly verified this pass)

Positive checks (claim resolves): `glance.py:568` emits `active`/`none`; `spawn_wrapper.py:379-389`
excludes `openai/gpt-6-astra`, `:912` is the `compile_spec` caller, `:917-922` is step 2;
`model_policy.py:30` is `SUBSCRIPTION_DEFAULT`; `knowledge_ingestion.py:485` reads `conclusion`,
`:538-540` derives authority from the test bool, `:555` calls the factory without `causes`;
`experiment_spec.py:39,602-623,627-640,675,899-963,1090-1097,1108-1149` all resolve;
`compile_experiment.py:35,88-97,322-342` resolve; `enqueue.py:58-64` is the fixed matrix;
`control_db.py:957-976` has no question columns; `phase_evidence.py:116-154` carries `gates` only;
`verify_control_room_rendering.py:36,291,2218,2314-2316,2351-2356` resolve; `app.js:463,999` and
`parity.js:1802,2223` resolve; `control_room.ts:7` is GET-only; `control_room_facelift_design.md:46-47`
= A5-D2/A5-D3; `..._repair_design.md:28,58`; `control_room_wireframe.md:113`; the six operator states
and `merged ≠ published`/`escalated has no mechanism today` are at `control_room_state_screens.md:24-35`;
the `a3_adversarial` agent phase is at `workflows/repository/control_room_facelift_review.yaml:127-151`;
`tests/test_control_room_{static_views,glance_integrity,feature_parity,parity}.py`,
`tests/test_fast_path_gate.py`, `tests/test_doc_lifecycle.py`, and
`experiments/research/control_room/parity_inventory.json` exist.

---

## 6. Verdict

**REWORK REQUIRED.** The direction and v2 stand; a4 closed most of a3's mechanical findings, and the
largest a2 gaps (spec→job executor, auto-generation) are now stated honestly. But the correction wave
left six dispositions nominal, the first wave is not executable-and-validating as specified, and the
design's drive still rests on machinery its own gap list does not budget.

**Severity-ranked required corrections** (each with the acceptance that proves it):

1. **BLOCKER — the first wave's validation loop is not closed (N-3, T-17).** Make F02a a
   controller/human act (not a session task) bound by an attestation the gate checks, add the class-B
   reader and the client-spy harness to §1.3, and stop citing checks a green agent run can satisfy.
   *Proves:* deleting/flipping the recorded pass fails, and an agent-authored "human" file lacking the
   attestation also fails; every first-wave acceptance names a §1.3 row.
2. **BLOCKER — the F04 correction is nominal and misstated (N-1, N-2, T-18).** Add `F04 → F06`, make §5
   the render of the deps table, and fix the attention enum to the producer's actual `{active,none}`
   (or name the `unknown` producer F27 must add). *Proves:* the dep-table union equals §5 and F06
   cannot be green before F04; F04's fixture enum equals `glance.py:568`.
3. **BLOCKER — the a2 honest-gap list is incomplete (W-15, W-16, W-17, W-18, W-19).** Budget the emit
   authority/`causes` change, the coverage-gate predicate + implementation, the lexicographic ordering,
   the Question→`RuleSpec` mapping, and the durable attempt counter. *Proves:* the W-13 emission test
   runs on listed surface; the coverage gate fails §6 today (or §6 is excluded explicitly); the
   `uncertainty` falsifier runs on a mapped rule; a red gate parks and stays parked across a restart.
4. **HIGH — F03 blocks four downstream tasks on a controller decision (T-15).** Split `F03a/F03b`.
   *Proves:* F03a is green with the two-sources fixture absent; only F03b is red while D8 is open.
5. **HIGH — F01a's discriminator proof is vacuous (T-16).** Extend `check_fixtures` to the seeded ids
   and assert the discriminator is the geometry/clip JS. *Proves:* clip detector off → `--check-fixtures`
   0, full gate 1; on → both behave as specified.
6. **HIGH — the worked example violates its own protocol (W-20) and the two artifacts contradict each
   other on the captured packet (N-2 cross-artifact).** Split Q12/Q14; pick one fixture policy.
   *Proves:* every §6 row names a single task id; one fixture policy appears in both a1 and a2.
7. **MEDIUM — T-19/T-20/W-21/N-4/N-5.** Split F11; make F25b's machine check explicit; correct the
   "drained by the existing workers" sentence; fix the §0.2 whitelist citation; add an ownership field
   or drop the de-dup claim. *Proves:* each stated acceptance is one session, machine-observable, and
   anchored to a resolving source.

**The three highest-value corrections:** (1) close the first-wave validation loop (N-3 + T-17);
(2) repair the nominal F04/F06 edge and the misstated attention enum (N-1 + N-2 + T-18); (3) complete
the a2 gap list and make its gates real (W-15 + W-16 + W-19). Each is mechanical, each is provable with
a named check, and none requires rewriting the direction.

**Disposition.** Feed this pass into a5 alongside pass 1. This review itself carries no controller
decision; D1–D8 (a1 §8) and W1–W8 (a2 §11) remain the open choices, and D6's "human-scored" default
is only meaningful once N-3's attestation is specified.
