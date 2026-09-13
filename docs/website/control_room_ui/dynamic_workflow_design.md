---
status: accepted
---

# Control Room facelift — dynamic, question-driven workflow design (phase `a2_dynamic_workflow`)

**Date:** 2026-09-13
**Phase:** `a2_dynamic_workflow` of `workflows/repository/control_room_facelift_review.yaml`.
**Question it answers:** what workflow *shape* should run the `a1` decomposition (and future design
work) — a question-driven, self-evolving tree selected by information gain, layered for parallel
processing, with acceptance gates — **without inventing machinery the compiler does not have**?
**Companion:** `docs/website/control_room_ui/facelift_task_plan.md` (a1) is the first tree this
shape grows; `docs/reviews/control_room_facelift_adversarial.md` (a3) is the proof that the
adversarial loop attacks questions and acceptance, not only answers.

---

## 0. The operating metaphor, made mechanical

The controller's framing: a static checklist is not how this work actually proceeds. A person
operating at high abstraction with parallel attention does not walk a fixed list — they **grow a
living question tree**: an uncertain answer becomes a sub-question, a sub-question that turns out to
be ill-posed is re-cut, and the next thing attended to is the thing whose answer would change the
most. This is novelty/complexity-seeking behaviour, and it is exactly the information-acquisition
loop the repository already names (`agent_config/rules.md`: instrument → derive → write policy →
grid → campaign → repeat).

The design below keeps the metaphor as the *drive* and the compiler as the *substrate*. **No node in
the tree is free-form prose.** Every node is a question with a named acceptance and a kill
criterion, and every edge is a `requires`/`produces` edge the compiler already validates.

---

## 1. The task unit — the Question node

A **Question** is the atomic unit. It refines the a1 "small task" bound with the two fields a task
plan does not carry: a **kill criterion** and an **uncertainty** scalar.

```yaml
Question:
  id:             Q7                       # stable; never reused
  question:       "Does one transition-only, increases-only live region replace the         # interrogative, one sentence
                   current announcer without double-announcing a batch?"
  acceptance:     "unit test: initial value and decreases are not announced; an identical    # ONE named gate
                   consecutive message re-announces; a burst coalesces"
  kill_criterion: "the room needs two live regions (e.g. one per axis) — then the single-    # what would dispose it
                   region hypothesis is false and the question is re-cut"
  layer:          behavior
  requires:       [Q4]                     # question ids + ledger/information fields
  produces:       [announcement_policy]    # information this answer emits
  uncertainty:    0.7                      # [0,1]; 1.0 = unanswered/uninstrumented
  evidence_class: [M]                      # [M]/[C]/[H]/[P]/[X]
  status:         open                     # open | answered | killed | parked
  children:       []                       # sub-questions opened when the acceptance cannot be made concrete
  source:         "a1:F06"                 # who emitted it (for self-evolved nodes)
```

### 1.1 "Small" is now a two-part bound

1. **One session** produces the artifact (a1's bound).
2. **One named gate** can turn green *and can turn red on a seeded violation.* A gate that cannot
   fail is not an acceptance (this is the a3 adversary's first attack: "acceptance that can pass
   vacuously").

### 1.2 How a question expands into a sub-tree

A question expands when **its acceptance cannot be made concrete in one session** — i.e. when the
session would have to answer a prior question to even state the check. The split rule is the same
one a1 uses:

> Ask **"what must be true for this to hold?"** until each leaf's acceptance is a fixture that can
> fail.

The split is recorded as `children`, and the parent's `produces` becomes the conjunction of the
children's `produces`. This is the compiler's `requires`/`produces` direction; no new edge type is
introduced.

**Worked micro-example.** `Q11: "Can the gate no longer pass on a seeded-bad fixture?"` cannot be
one acceptance because the gate has nine independent holes (a6 G-1/G-3/G-5/G-6/G-10/G-11/G-13/G-14/
G-15). It expands into `Q11a` (uniqueness/overflow/legibility) and `Q11b` (value/fixture semantics),
each with its own seeded-bad fixture. The plan ships this split (a1 §3, F01a/F01b).

---

## 2. Layers and parallel fan-out

The a1 layer grammar (`intent → structure → behavior → verification → presentation`) is the
tree's depth axis. Two rules govern concurrency:

- **Same-layer siblings fan out.** They have no `requires` edge between them, so they run in
  parallel (the existing queue: `enqueue.py` → `worker.py`, N concurrent workers). `Q3 (R0)`,
  `Q4 (row)`, `Q5 (inbox)` are independent structure questions and fan out together.
- **Cross-layer questions are edges, not barriers.** A `behavior` question that needs a structure
  selector waits only on that structure question, not on the whole layer. The compiler's
  `RuleSpec.requires`/`produces` gate (`src/agentic_dynamics/experiment/experiment_spec.py:899-963`)
  is the mechanism: `requires` a field a sibling has not `produces` yet → the arm is refused.

```text
intent      Q1 thesis-recognized        Q2 disposition-reconciled
              │                          │
structure     ├─ Q3 R0 truth ──┐         ├─ Q6 R4c ladder
              ├─ Q4 row identity ─┬──────┘
              └─ Q5 inbox expand ─┘
behavior      Q7 announcer   Q8 counts-filter   Q9 pause-confirmed   Q10 steer-receipt
              │              │                  │                    │
verification  Q11 gate-holes  Q12 test-classes  Q13 forcing-fixtures
presentation  Q14 tokens
```

The DAG is **layer-major**: a layer only opens when the previous layer's frontier is answered or
parked. This is not a constraint the compiler imposes — it is a scheduling choice the drive
(§3) makes because a behavior question with an unanswered structure dependency scores low.

### 2.1 Cross-layer edges are `requires`/`produces`, never hand-waving

| From (layer) | Produces | Consumed by | Compiler representation |
|---|---|---|---|
| intent | the acceptance + kill criterion | structure | `RuleSpec(name=…, plane=control, requires=[…])` |
| structure | `[data-region]`/`[data-answer]` selectors | behavior | a measurement rule producing the selector field |
| behavior | transition/act semantics | verification | a control rule whose `requires` name the behavior signal |
| verification | a green/red gate | presentation | the gate result as the accepted-outcome field |
| presentation | theme/contrast state | verification | the style gate's own class |

---

## 3. The drive — selecting the next question by information gain

The next question is chosen by a **novelty score**, not by document order. The score reuses the
compiler's declared selection strategies verbatim (`AdaptSpec.selection`,
`experiment_spec.py:39`):

**Readiness is a hard filter, not a score term.** Before any scoring, the candidate set is

```text
candidates = { q : status(q)==open, requires(q) all satisfied, acceptance(q) is concrete }
```

A question with unmet `requires` is **not in the set** — it cannot be selected, so the a3 `W-6`
ad-hoc "dependency depth" tie-break disappears. A question whose acceptance cannot be stated yet is
expanded into children (§1.2) and is not in the candidate set either.

Selection is then **lexicographic** over the declared strategies (a3 `W-4`: the raw terms have
incommensurable units, so no weighted sum is well-defined):

```text
select by AdaptSpec.selection, in order:
  1. highest_uncertainty : max posterior_uncertainty(q)      # primary
  2. highest_regret      : max regret(q)  from compare_arms   # tie-break
  3. largest_effect      : max effect(q)  from compare_arms   # final tie-break
next = the unique argmax; remaining ties broken by (layer order, question id) for determinism.
```

`AdaptSpec.strategy` remains the mode switch: `coordinate_descent` runs the loop unattended;
`manual` freezes the candidate set to the controller-pinned frontier.

- **Posterior uncertainty** (a3 `W-2`). `uncertainty(q)` is defined as a *posterior*, not the raw
  `RuleResult.uncertainty` sentinel: it is `1.0` only while the acceptance is **instrumented but
  unanswered**, and it falls to `RuleResult.uncertainty` once the acceptance has run. An
  **unimplemented** acceptance rule never sits in the candidate set — the question first expands
  into instrumentation children, which are the thing that can reach `uncertainty ≤ threshold`. This
  is what makes the loop convergent instead of selecting `1.0` forever.
- `regret(q)` / `effect(q)` come from `compare_arms` over the answered sub-tree
  (`compile_experiment.py:166-316`); a question whose answer flips the best arm has high regret.

**The convergence brake is `StopSpec`** (`experiment_spec.py:602-623`):

| Brake | Field | Behaviour |
|---|---|---|
| spend | `budget_usd` | no child spec is admitted without a lease once the campaign budget is consumed |
| attempts | `max_attempts` | a question that exhausts attempts is `parked`, not retried forever |
| uncertainty | `uncertainty_threshold` | when `next`'s uncertainty is below the threshold, the tree converges and the `writeup` phase runs |

`uncertainty_threshold` is **declared and validated today but consumed nowhere**
(`experiment_spec.py:608`); §6 names consuming it as the one small addition, not a new mechanism.

---

## 4. Self-evolution — how a phase emits and how a child spec is admitted

The cycle, expressed only in existing phase kinds (`compile_experiment.py:35`):

```text
cells → execute → measure → compare → writeup → adapt
                                   ▲                │
                                   └──── feedback ──┘   (compile_experiment.py:96: adapt → cells)
```

1. **Emit.** A phase's `PhaseResult` currently carries no structured question fields; its only
   narrative carrier is `final_response` and a single `confidence` scalar
   (`runtime/workflow_runner.py:216-392`). The minimal emission contract is therefore:
   - the phase definition (already a free-form `phase_def` dict) gains optional
     `question`, `acceptance`, `kill_criterion`, `conclusion` keys;
   - `workflow_runner` records them on `PhaseResult` and in the `step_attempts` row it already writes
     (`runtime/workflow_runner.py:1265-1308`);
   - **emission stops at the phase result / ledger by default.** An open question is neither a
     measured finding nor verified (a3 `W-5`), so it must not enter the knowledge stream with
     `MEASURED` authority. If a question is deliberately registered, it does so through the existing
     producer with an explicit `ADVISORY` source_type and a `causes` link to the observation that
     raised it; the existing `conclusion` slot
     (`knowledge/knowledge_ingestion.py:485`) is reused, not extended.
2. **Measure.** `evaluate_rules` maps attempts → `RuleResult`s; each open question's acceptance
   rule yields an uncertainty. `compare_arms` yields regret/effect.
3. **Select.** `select_next_question(...)` (the `adapt` executor, §6) scores the open set.
4. **Generate + admit.** A selected question compiles to a child `ExperimentSpec` (same
   `compile_spec` DAG, `compile_experiment.py:88-97`) and is **authored by default** (controller
   decision D5/W1): the drive ranks, the controller writes or approves the child. If a future
   session enables auto-generation, the full surface it must cover is named now so it is not
   smuggled in: a spec-lifecycle write (`experiments/specs/index.json` via
   `scripts/spec_status.py`), parent/child lineage on the run ledger (`run_id`/`parent_run_id`/
   `family_id`, `WorkflowRunResult`), and budget carry-over. A child that does run is admitted
   through the **existing** spend gate (`control.admission` — budget + concurrency leases, no lease
   no spend) and enqueued through the **existing** transport (`enqueue.py`/`worker.py`). There is no
   second scheduler.
   **Lease shape** (a3 `W-7`): children reserve against the **campaign** lease; the parent's already
   reserved amount is not double-counted, and an exhausted campaign lease denies the child. The
   parent is settled once (`settlement` status `matched`), so the campaign's cost is counted once.
5. **Converge.** When `select_next_question` returns `None` (below threshold, or budget/attempts
   exhausted), the campaign's `writeup` runs and the tree closes.

### 4.1 Exactly what is new (the honest gap list)

Per the project rule — *a net-new top-level mechanism requires a one-line justification naming the
gap it closes* — here is the complete list, each located inside an existing module:

| New thing | Gap it closes | Where it lives |
|---|---|---|
| `select_next_question(questions, *, selection, budget, attempts, threshold) -> Question \| None` — **ranks** the open set (children authored by default) | `AdaptSpec.selection` and `StopSpec.uncertainty_threshold` are validated but have **no consumer**; the `adapt` phase has no executor | `src/agentic_dynamics/experiment/compile_experiment.py` (the module that owns the `adapt` phase) |
| optional `question`/`acceptance`/`kill_criterion`/`conclusion` phase keys + recording on `PhaseResult` | no structured question/acceptance/kill/uncertainty on a phase result; only `final_response` | `runtime/workflow_runner.py` (recording) + `experiment_spec.py` (validation of the keys) |
| reuse of the `conclusion` slot in `emit_phase_finding` (ADVISORY only; a question is never a measured finding) | the slot is read but never set | `knowledge/knowledge_ingestion.py:485` (existing consumer, no change to the producer) |
| **auto-generation** of child specs (lifecycle index write, parent/child lineage, budget carry-over) | **not added by default** — authoring children is the controller's act; the surface is named in §4 so a future enablement cannot under-build it | `scripts/spec_status.py` + the run ledger + `control.admission` (if ever enabled) |

**Not added:** no new CLI entry point (an existing `agentic-dynamics experiment run` drives it), no
new persistence plane (the ledger/`step_attempts` carry it), no second queue, no new lease kind, and
no new node/envelope type in the knowledge stream.

---

## 5. The adversarial loop — attack the question, not just the answer

A question can be wrong in four ways, and the adversary's job is to find them **before** the answer
is paid for:

| Attack | Test the adversary applies | Correction it must produce |
|---|---|---|
| **Ill-posed** | can two competent reviewers disagree on what "answered" means? | rewrite the interrogative until the acceptance is unambiguous |
| **Unfalsifiable** | can the acceptance pass with the feature absent? | add a seeded violation the gate must fail |
| **Wrong question** | does answering it change a decision? | re-parent it or kill it (novelty without effect is a budget sink) |
| **Authority leak / fabricated signal** | does it require a value no producer measures? | split into an instrumentation question first (the load-bearing rule) |

**Findings are corrections to questions or acceptance, never praise and never a restatement.**
The a3 artifact (`docs/reviews/control_room_facelift_adversarial.md`) is the manual instance of this
loop: its rows carry severity, the flawed claim/question, the required correction, and the
acceptance that proves the correction. **The loop is a static, authored phase — exactly the `a3`
phase the existing spec declares — never a runtime scheduler** (a3 `W-3`): no code path constructs an
adversary session, and no phase auto-launches an adversary on another phase's output. This keeps the
portal and the campaign at zero *unnecessary* model spend while still attacking questions before
their answers are paid for.

---

## 6. Worked example — growing this facelift's tree

Fourteen questions, layered exactly as §2, each carried into a1's task ids. Kill criteria are the
five v2 conflicts plus the a6 gate misses, so the tree cannot regrow a rejected idea.

| Q | Layer | Question | Acceptance (named gate) | Kill criterion | a1 task | Uses (external) |
|---|---|---|---|---|---|---|
| Q1 | intent | Does the resting screen communicate the run-first thesis to a stranger? | blind-comprehension scorecard (class B) | a generic-dashboard comparator passes all five §4.2 sentences | F02 (+ first-wave gate) | v2 C12 zero-terminal/rendered proof |
| Q2 | intent | Which v1 proposals survive reconciliation with the direction? | v2 §6 table, each row statused | a proposal not in the direction is scheduled as-is | this plan §0 | v2 §5 |
| Q3 | structure | Can R0 answer `ON-G1`/`ON-G6` with no KPI tile row? | render gate `ON-G1`/`ON-G6` + no-tile assertion | a `.stat-tile` appears in R0 | F07 | v2 T2/T3 |
| Q4 | structure | Does the row keep the E10 identity+lease+claim/proof contract on mobile? | mobile blind-comprehension fixture + G-13 row values incl. `spec/cell` | any identity field is ellipsised on mobile | F11 | v2 O2/O4 |
| Q5 | structure | Does one attention item expand in place with one compact empty state? | fixture F-1 + screenshot + one-empty-state assertion | repeated filler cards return | F09 | v2 C3 |
| Q6 | structure | Does R4c render typed rungs + a five-stage causal spine? | fixture (waiting/failed/money-risk) + gate | raw JSON transcript becomes the spine | F17 | v2 C8 |
| Q7 | behavior | Does one transition-only announcer replace the current one? | announcer unit tests (initial/decreases silent; identical re-announces) | two live regions are required | F06 | v2 T7 |
| Q8 | behavior | Do counts filter with a refresh-age caveat (no stale delta)? | gate G-14 + click-through + stale fixture | a bare delta renders from a stale poll | F08 | v2 T3/T4/A-6 |
| Q9 | behavior | Is approval-pause a confirmed controller act, never automatic? | no unconfirmed pause path + receipt | any threshold auto-steers | F10 | v2 C4/A-4 |
| Q10 | behavior | Does a steer/reply show target/scope/reversibility + receipt? | authority test + receipt fixture | an unguarded terminal write appears | F20 | v2 H2/A-12 |
| Q11 | verification | Can the gate no longer pass on a seeded-bad fixture? | seeded-bad fixtures make the gate exit 1 | a gate hole survives | F01/F01a/F01b | a6 G-1…G-15 |
| Q12 | verification | Do all four canonical test classes exist? | `--a11y` green + a schema-valid `b_comprehension.json` | DOM presence is treated as a pass | F02 | direction §18.5 |
| Q13 | verification | Do the forcing fixtures exist? | each fixture renders its distinguishing field | empty fixtures pass | F03 | v2 C7/C11 |
| Q14 | presentation | Do the tokens hold forced-colors + the restraint budget? | `--style`/`--a11y` in 3 themes + no-pulse assertion | decorative pulse/glow returns | F25 | v2 §4.3 |

**The tree's first move** (readiness filter, then `highest_uncertainty`): `Q1` requires the class-B
scorecard that `Q12` produces, so `Q1` is **not in the candidate set** until the verification layer
lands. The frontier is therefore the verification questions `{Q11, Q12, Q13}`, all at posterior
uncertainty `1.0`; `Q11` (the gate's ability to fail) is the prerequisite for `Q12`/`Q13`, so it is
attended first, then `Q12`/`Q13`. Once the gate and scorecard are green, `Q1` enters the candidate
set and is selected; then the structure frontier `{Q3,Q4,Q5,Q6}` fans out. That is the a1 first wave
`{F01a,F01b,F02,F04,F07,F11}` passing through the tree's own selection rule — the plan and the drive
agree, and no ad-hoc tie-break is needed.

**A concrete re-cut.** If `Q4`'s first answer shows mobile cannot carry identity+lease+claim/proof in
one row without overflow, `Q4` expands into `Q4a` (two-line identity band) and `Q4b` (row-lease
compaction); the parent is `open` until both leaves are green. The overflow measurement is the
`produces` that makes `Q4b`'s acceptance concrete.

---

## 7. Anti-thrash and failure modes

| Failure mode | Symptom | Guard |
|---|---|---|
| **Divergence** | a question spawns children without lowering uncertainty | `max_attempts` parks it; a child's acceptance must be strictly more concrete than the parent's |
| **Cycling** | two questions keep re-opening each other | the only feedback edge is `adapt → cells` (`compile_experiment.py:96`); any new cycle is a design error, not a feature |
| **Budget burn** | the drive keeps selecting high-effect but low-value questions | `budget_usd` + admission lease; high regret with no owner is a kill, not a spend |
| **Vacuous acceptance** | a gate that cannot fail | every acceptance names a seeded violation (a3's first attack) |
| **Authority drift** | a question quietly expands the mutation surface | the adversary checks for new route classes / auto-actuation; direction §12.2 is the fence |
| **Unmeasured `requires`** | a control question consumes a signal no rule produces | `validate_rules` refuses it (`experiment_spec.py:948-952`) — the compiler is the guard |

---

## 8. What already exists vs the three additions (contract table)

| Capability | Status | Anchor |
|---|---|---|
| spec object + free-form `question` | **WRITTEN** | `experiment_spec.py:675` |
| `requires`/`produces` gate | **WRITTEN** | `experiment_spec.py:899-963` |
| 7-phase DAG + `adapt → cells` feedback | **WRITTEN** | `compile_experiment.py:35,88-97` |
| factorial fan-out (`experiment_matrix`) | **WRITTEN** | `compile_experiment.py:108-129` |
| regret/effect (`compare_arms`) | **WRITTEN** | `compile_experiment.py:166-316` |
| per-rule uncertainty (`RuleResult`) | **WRITTEN** | `compile_experiment.py:322-342` |
| `AdaptSpec` strategy/selection | **declared + validated, no consumer** | `experiment_spec.py:38-39,1090-1097` |
| `StopSpec.uncertainty_threshold` | **declared, no consumer** | `experiment_spec.py:608` |
| structured question/acceptance/kill on a phase result | **ABSENT** | `runtime/workflow_runner.py:216-392` |
| emission of new questions/conclusion | **slot exists, never set** | `knowledge/knowledge_ingestion.py:485` |
| child-spec generation from selection | **ABSENT** | — |
| question-level adversary | **manual instance only** (a3 / this workflow) | — |

---

## 9. Relationship to the compiler contracts (why this is not a parallel mechanism)

- **The tree is a campaign.** A campaign is "a sequence of grids; between grids, tweak one variable,
  re-run" (mental model). Each Question is a grid; the drive tweaks one variable at a time
  (`coordinate_descent`). No new orchestration layer.
- **The node is an `ExperimentSpec`.** `question`, `rules`, `stop`, `adapt` already carry everything
  a Question needs; this design adds only the *structured* question/acceptance/kill fields on the
  phase, not a new object family.
- **The edge is the gate.** `requires`/`produces` already refuses an unwritable policy arm; the tree
  inherits that refusal as its correctness property.
- **The brake is `StopSpec`.** Budget/attempts/threshold already exist.
- **The transport is the queue.** Children are admitted by the lease gate and drained by the
  existing workers.

If a future session wants a runtime self-generating campaign, the only missing piece is the
`adapt` executor named in §4.1; everything else is authored data.

---

## 10. Controller decisions needed (finalized — a4)

| # | Decision | Why it blocks | Default if silent |
|---|---|---|---|
| W1 | Adopt `select_next_question` + the structured phase keys as the campaign engine, and are children **authored** or **auto-generated**? | auto-generation adds a spec-lifecycle write + lineage + budget carry-over (a3 W-1); authoring keeps it small | authored children; the drive ranks, the controller writes |
| W2 | Which `AdaptSpec` strategy is the default drive (`coordinate_descent` vs `manual`)? | `manual` keeps the controller at the frontier; `coordinate_descent` automates selection | `manual` |
| W3 | May a child spec spend within the **campaign** lease without a per-child approval? | the admission gate already permits lease-scoped P1 spend; this confirms the campaign's authority and fixes the no-double-count rule (a3 W-7) | controller approves each child; no double-count |
| W4 | Is the question-level adversary a static authored phase only (never a runtime scheduler)? | a runtime adversary adds model calls and a new mechanism to a zero-call design task (a3 W-3) | static authored phase only |

---

## 11. Adversarial dispositions (a3 → a2)

| a3 | Status | Resolution in this design |
|---|---|---|
| W-1 new-mechanism surface | **accepted** | Children are **authored by default**; the auto-generation surface (lifecycle index, lineage, budget carry-over) is enumerated in §4.1 so a future enablement cannot under-build it. |
| W-2 non-convergence | **accepted** | Uncertainty is re-defined as a **posterior**; an unimplemented acceptance expands into instrumentation children instead of scoring `1.0` forever (§3). |
| W-3 runtime adversary | **accepted** | The adversarial loop is a **static authored phase**; no code path launches an adversary session (§5). |
| W-4 incommensurable score | **accepted** | Weighted sum replaced with a **lexicographic** order over the declared strategies, with deterministic tie-breaks (§3). |
| W-5 knowledge-authority pollution | **accepted** | Emission stops at the phase result/ledger; KB entry only as explicit `ADVISORY` with a `causes` link (§4 step 1). |
| W-6 readiness tie-break | **accepted** | Readiness is a **hard admissibility filter** before scoring; no depth heuristic (§3, §6). |
| W-7 budget ownership | **accepted** | Children reserve against the **campaign** lease; the parent reservation is not double-counted and settles once (§4 step 4). |
| W-1 (auto-gen) | **accepted (deferred)** | Auto-generation is not enabled by default; decision W1 owns it. |
