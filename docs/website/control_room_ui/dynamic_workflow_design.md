---
status: accepted
---

# Control Room facelift — dynamic, question-driven workflow design (phase `a2_dynamic_workflow`)

**Date:** 2026-09-13
**Phase:** `a2_dynamic_workflow` of `workflows/repository/control_room_facelift_review.yaml`.
**Question it answers:** what workflow *shape* should run the `a1` decomposition (and future design
work) — a question-driven, self-evolving tree selected by information gain, layered for parallel
processing, with acceptance gates — **without inventing machinery the compiler does not have**?
**Companions:** `docs/website/control_room_ui/facelift_task_plan.md` (a1) is the first tree this
shape grows; `docs/reviews/control_room_facelift_adversarial.md` (a3) is the proof that the
adversarial loop attacks questions and acceptance, not only answers.

---

## Brief coverage — where each required element is answered

| The brief asks for | Section |
|---|---|
| **TASK UNIT** — question + acceptance + kill-criterion; "small" as the one-session bound; expansion into a sub-tree | §1 |
| **LAYERS** — intent → structure → behavior → verification → presentation; parallel fan-out; cross-layer `requires`/`produces` | §2 |
| **DRIVE** — next question by information gain; the compiler's adapt strategies; `StopSpec` as the brake | §3 |
| **SELF-EVOLUTION** — emit (answer, new questions, uncertainty delta); child-spec generation + admission; the minimal new machinery | §4 |
| **ADVERSARIAL LOOP** — attack the question and the acceptance; findings are corrections | §5 |
| **WORKED EXAMPLE** — a 10–15 question tree for *this* facelift | §6 |

---

## 0. The operating metaphor, made mechanical

The controller's framing: a static checklist is not how this work actually proceeds. A person
operating at high abstraction with parallel attention does not walk a fixed list — they **grow a
living question tree**: an uncertain answer becomes a sub-question, a sub-question that turns out to
be ill-posed is re-cut, and the next thing attended to is the thing whose answer would change the
most. This is novelty/complexity-seeking behaviour, and it is exactly the information-acquisition
loop the repository already names (`agent_config/rules.md`: instrument → derive → write policy →
grid → campaign → repeat).

The design keeps the metaphor as the *drive* and the compiler as the *substrate*. **No node in the
tree is free-form prose.** Every node is a question with a named acceptance and a kill criterion,
and every edge is a `requires`/`produces` edge the compiler already validates.

The one sentence to hold onto:

> **A tree of executable questions whose next move is chosen by how much its answer would change
> our uncertainty, and whose every node must survive an adversary that attacks the question before
> anyone pays to answer it.**

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

The three fields that make this a *protocol* and not a to-do list:

- **`acceptance`** is exactly one named gate — a test target, a render-gate fixture, or a measured
  diff. A gate that cannot be written down is not an acceptance.
- **`kill_criterion`** is what would prove the question *wrong* (not merely unanswered). It is the
  unit the adversary attacks and the unit that disposes a rejected idea.
- **`uncertainty`** is the drive's input (§3). It is a *posterior* the moment the acceptance has
  run, and a sentinel `1.0` while it has been instrumented but not yet answered.

### 1.1 "Small" is now a two-part bound

1. **One session** produces the artifact (a1's bound).
2. **One named gate** can turn green *and can turn red on a seeded violation.* A gate that cannot
   fail is not an acceptance (this is the a3 adversary's first attack: "acceptance that can pass
   vacuously").

Both parts are required. Part 1 alone admits a one-session task with no checkable answer; part 2
alone admits a check that spans a week. The conjunction is what "small" means here.

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

**The split is the *only* legal expansion.** A question may not expand into "do part of it" — the
children must each be independently gated, and the parent stays `open` until all children are green
or killed. This is what keeps the tree convergent (§7): expansion adds gates, never prose.

---

## 2. Layers, fan-out, and how cross-layer edges are typed

The a1 layer grammar (`intent → structure → behavior → verification → presentation`) is the tree's
**abstraction/typing axis** — the vocabulary used to *name* and *group* questions. It is **not a
topological order and not a scheduling lane.**

This distinction matters because the a1 plan's true frontier is `F01a/F01b` — **verification**
questions — even though no pixels exist yet. An intent question (`Q1`) needs the class-B scorecard
that a verification question (`Q12`) produces; if layers were a barrier, the first admissible
question would be the last one that can run. So:

- **The layer label is a name, not a gate.** A question is admissible exactly when its `requires`
  are satisfied (§3's hard readiness filter), regardless of layer.
- **Same-layer siblings fan out.** They have no `requires` edge between them, so they run in
  parallel (the existing queue: `enqueue.py` → `worker.py`, N concurrent workers). `Q3 (R0)`,
  `Q4 (row)`, `Q5 (inbox)` are independent structure questions and fan out together.
- **Cross-layer questions are edges, not barriers.** A `behavior` question that needs a structure
  selector waits only on that structure question, not on the whole layer. The compiler's
  `RuleSpec.requires`/`produces` gate (`src/agentic_dynamics/experiment/experiment_spec.py:899-963`)
  is the mechanism: `requires` a field a sibling has not `produces` yet → the arm is refused.

### 2.1 Which questions may run in parallel at each layer

| Layer | The question shape | Parallel set at this layer | Cross-layer `requires` it consumes |
|---|---|---|---|
| **intent** | *what operator question must this answer?* | all intent questions with satisfied deps | the acceptance gate a lower layer produces (e.g. the scorecard) |
| **structure** | *what regions/objects/selectors carry the answer?* | independent regions (R0, R1, R2, R3, R4) | intent's acceptance; produces DOM selectors |
| **behavior** | *what happens on state change / interaction?* | independent mechanics (announcer, filters, pause, steer) | structure selectors |
| **verification** | *what fixture and gate prove it?* | independent gate holes (`Q11a`/`Q11b`, classes, fixtures) | behavior's transition semantics |
| **presentation** | *does it read under load and in forced-colors?* | token/theme questions | structure + verification |

```text
intent      Q1 thesis-recognized        Q2 disposition-reconciled
               │                          │
structure     ├─ Q3 R0 truth ──┐         ├─ Q6 R4c ladder
               ├─ Q4 row identity ─┬──────┘
               └─ Q5 inbox expand ─┘
behavior      Q7 announcer   Q8 counts-filter   Q9 pause-confirmed   Q10 steer-receipt
               │              │                  │                    │
verification  Q11a gate-holes  Q11b value-semantics  Q12 test-classes  Q13 forcing-fixtures
presentation  Q14 tokens
```

The arrows are `requires` edges, not drawing order. In the diagram, `Q1` (intent) depends on
`Q11a/Q11b/Q12` (verification) via the scorecard, so the first admissible frontier is verification —
exactly as the a1 plan states ("F01–F03 are the true frontier, even though they deliver no pixels").

### 2.2 Cross-layer edges are `requires`/`produces`, never hand-waving

| From (layer) | Produces | Consumed by | Compiler representation |
|---|---|---|---|
| intent | the acceptance + kill criterion | structure | `RuleSpec(name=…, plane=control, requires=[…])` |
| structure | `[data-region]`/`[data-answer]` selectors | behavior | a measurement rule producing the selector field |
| behavior | transition/act semantics | verification | a control rule whose `requires` name the behavior signal |
| verification | a green/red gate | intent + presentation | the gate result as the accepted-outcome field |
| presentation | theme/contrast state | verification | the style gate's own class |

**Why not just let the queue run everything at once?** Because a behavior question with an
unanswered structure dependency scores low on the drive anyway (§3), so it is never selected; the
readiness filter makes that starvation explicit and deterministic instead of accidental.

---

## 3. The drive — selecting the next question by information gain

The next question is chosen by a **novelty score**, not by document order. The score reuses the
compiler's declared selection strategies verbatim (`AdaptSpec.selection`,
`src/agentic_dynamics/experiment/experiment_spec.py:627-640`; the closed set is
`ADAPT_SELECTIONS` at `experiment_spec.py:39`):

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

### 3.1 What `uncertainty` actually is (the convergence fix — a3 `W-10`)

**A design Question is not a `RuleSpec`, and no `(question, acceptance) → RuleResult` mapping
exists.** A design question runs no attempts, so there is no ledger field to read a posterior from;
the compiler's `RuleResult.state ∈ {measured, unmeasured, unimplemented}`
(`compile_experiment.py:322-342`) describes a *measurement rule's* result, not a design node's. The
previous draft asserted a `select_next_question` posterior over `RuleResult.state` as if that
mapping existed — it does not (a3 `W-10`). Two cases, stated honestly:

- **An acceptance that *is* an instrumented measurement rule** (it maps to a `RuleSpec` in the
  campaign spec and attempts exist): `uncertainty(q)` is that rule's own posterior —
  `RuleResult.uncertainty`, with `state=unmeasured` admissible at `1.0` (instrumented, awaiting
  data) and `state=unimplemented` **inadmissible** (it expands into instrumentation children).
- **An acceptance that is a gate** (a render-gate fixture, a named pytest target, a measured diff —
  the a1 plan's actual acceptance shape): uncertainty is **binary** — the gate is green (answered,
  `0.0`) or not (open, `1.0`). There is no scalar to order. For these, selection is
  **readiness + authored priority**, not information gain, and the design says so rather than
  fabricating a posterior. `AdaptSpec.selection` orders the *instrumented* subset; the authored
  priority in the a1 plan orders the rest.

This is what keeps the loop convergent instead of selecting `1.0` forever: an uninstrumented
acceptance never sits in the candidate set at `1.0`; it expands until each leaf can actually be
measured or gated. An answered question falls to `0.0` and leaves the candidate set.

`regret(q)` / `effect(q)` come from `compare_arms` over the answered sub-tree
(`compile_experiment.py:166-316`); a question whose answer flips the best arm has high regret.
**The falsification test is restated so it can actually fire** (the previous one could not, a3
`W-10`): with a synthetic candidate set whose `requires` are all green but whose *instrumented*
uncertainties differ, the rule must select the higher-uncertainty candidate; a question with an
`unimplemented` acceptance must be provably **absent** from the candidate set. A test whose candidate
set is empty by construction is not a falsifier.

### 3.2 The convergence brakes

The brief names **budget, attempts, time**. Two of these live in `StopSpec`
(`experiment_spec.py:602-623`); time is enforced by the runner wall, and this design says so
honestly rather than pretending `StopSpec` owns it:

| Brake | Field | Behaviour |
|---|---|---|
| spend | `StopSpec.budget_usd` | no child spec is admitted without a lease once the campaign budget is consumed |
| attempts | `StopSpec.max_attempts` | a question that exhausts attempts is `parked`, not retried forever |
| uncertainty | `StopSpec.uncertainty_threshold` | when `next`'s uncertainty is below the threshold, the tree converges and the `writeup` phase runs |
| **time** | per-phase `timeout` + `run_workflow.py --phase-watchdog-min` | a phase that burns its wall is recorded as `timed_out` (a `PhaseResult` truth, `runtime/workflow_runner.py:229-234`); a campaign that overruns its deadline parks the frontier rather than spending unbounded |
| **red acceptance** | an attempt counter for **non-cell** questions (a3 `W-12`) | a design question's "attempt" is one re-run of its acceptance. `max_attempts` counts those re-runs; a question whose acceptance stays red **unchanged** is `parked` after `max_attempts`, not re-selected forever, and a question is excluded once its acceptance has failed unchanged (the same red), so a permanently red gate terminates the frontier instead of looping. |

`StopSpec.uncertainty_threshold` is **declared and validated today but consumed nowhere**
(`experiment_spec.py:608`); §4.1 names consuming it as the one small addition, not a new mechanism.
For gate-shaped questions (§3.1) the threshold compares `0.0`/`1.0`, and the non-cell attempt counter
above is the real brake.

---

## 4. Self-evolution — how a phase emits and how a child spec is admitted

The cycle, expressed only in existing phase kinds (`compile_experiment.py:35`):

```text
cells → execute → measure → compare → writeup → adapt
                                   ▲                │
                                   └──── feedback ──┘   (compile_experiment.py:96: adapt → cells)
```

1. **Emit.** A phase's `PhaseResult` today carries no structured question fields; its narrative
   carriers are `final_response` and a single `confidence` scalar
   (`runtime/workflow_runner.py:282-283`). The minimal emission contract is therefore:
   - the phase definition (already a free-form `phase_def` dict) gains optional
     `question`, `acceptance`, `kill_criterion`, `conclusion` keys;
   - **`workflow_runner` recording them on `PhaseResult` is a prerequisite, not an optional
     key** (a3 `W-13`): `emit_phase_finding` reads `conclusion` via
     `getattr(phase_result, "conclusion", "")` (`knowledge/knowledge_ingestion.py:485`) but
     `PhaseResult` has no `conclusion` field, so question text is silently dropped until the
     recorder lands. Handing the fields to the control db's `step_attempts` would also need a
     schema change and remains a named follow-up, **not** claimed as existing (the `step_attempts`
     table at `control/control_db.py:957-976` has no such columns; the injected `PhaseEvidence`
     recorder at `runtime/phase_evidence.py:116-154` carries `gates`, not questions);
   - **emission stops at the phase result / ledger by default.** An open question is neither a
     measured finding nor verified (a3 `W-5`), so it must not enter the knowledge stream with
     `MEASURED` authority. **The question path sets authority `ADVISORY` explicitly and must never
     inherit the test bool** (a3 `W-13`): `emit_phase_finding` currently derives authority from
     `test_executed_success` (`MEASURED` iff a real bool, else `ADVISORY`,
     `knowledge/knowledge_ingestion.py:538-540`), so a *design phase with a passing test* would
     otherwise register an open question as `MEASURED`. A registered question therefore passes
     `ADVISORY` and a `causes` link to the observation that raised it; a measured finding keeps
     `MEASURED`; a phase result without the recorded fields emits nothing.
2. **Measure.** `evaluate_rules` maps attempts → `RuleResult`s; each open question's acceptance
   rule yields a posterior uncertainty. `compare_arms` yields regret/effect.
3. **Select.** `select_next_question(...)` (the `adapt` executor, §4.1) scores the open set.
4. **Generate + admit — bounded to authored phases.** The compiler is a **plan, not a runtime**
   (a3 `W-9`): `compile_spec` returns a static `DAG` object and nothing executes its phases; its
   only non-test caller (`scripts/fleet/spawn_wrapper.py:912`) uses it as the requires/produces gate.
   The existing "transport" `enqueue.py` builds a **fixed story matrix**
   (`STORIES × TIERS × CONDITIONS`, `scripts/enqueue.py:58-64`), not spec cells, and there is no
   spec→job bridge. This design therefore does **not** claim a self-evolving runtime campaign: the
   campaign is the authored `phases:` list (as this very workflow is), a Question compiles to a
   child `ExperimentSpec` (same `compile_spec` DAG, `compile_experiment.py:88-97`) and is
   **authored by default** (controller decision D5/W1) — the drive **ranks** the frontier; the
   controller writes or approves the child. A child that does run is admitted through the
   **existing** spend gate (`control.admission` — budget + concurrency leases, no lease no spend)
   and drained by the existing workers. There is no second scheduler. The full executor surface a
   future auto-generation enablement must build is enumerated with its size in §4.1; it is **not**
   built here.
   **Lease shape** (a3 `W-7`): children reserve against the **campaign** lease; the parent's already
   reserved amount is not double-counted, and an exhausted campaign lease denies the child. The
   parent is settled once (`settlement` status `matched`), so the campaign's cost is counted once.
5. **Converge.** When `select_next_question` returns `None` (below threshold, or budget/attempts/
   time exhausted), the campaign's `writeup` runs and the tree closes.

### 4.1 Exactly what is new (the honest gap list)

Per the project rule — *a net-new top-level mechanism requires a one-line justification naming the
gap it closes* — here is the complete list, each located inside an existing module:

| New thing | Gap it closes | Where it lives |
|---|---|---|
| `select_next_question(questions, *, selection, budget, attempts, threshold) -> Question \| None` — **ranks** the open set (children authored by default) | `AdaptSpec.selection` and `StopSpec.uncertainty_threshold` are validated but have **no consumer**; the `adapt` phase has no executor | `src/agentic_dynamics/experiment/compile_experiment.py` (the module that owns the `adapt` phase) |
| optional `question`/`acceptance`/`kill_criterion`/`conclusion` phase keys + recording on `PhaseResult` | no structured question/acceptance/kill/uncertainty on a phase result; only `final_response`/`confidence` | `runtime/workflow_runner.py` (recording) + `experiment_spec.py` (validation of the keys, alongside the existing `deploy_allowed`/`checkpoint`/`no_emit` phase markers at `experiment_spec.py:1108-1149`) |
| reuse of the `conclusion` slot in `emit_phase_finding` (ADVISORY only; a question is never a measured finding) | the slot is read but never set; authority would otherwise inherit `test_executed_success` | `knowledge/knowledge_ingestion.py:485,538-540` (existing consumer; the question producer passes `ADVISORY` + `causes` explicitly) |
| **spec→job executor** (compile→enqueue→worker bridge, campaign-lease allocation, parent/child lineage) | the "existing transport" does not carry spec cells (a3 `W-9`): `enqueue.py` builds a fixed story matrix, and `compile_spec`'s DAG is never executed | `scripts/enqueue.py` + `scripts/worker.py` + the run ledger — **NOT built by default; sized `L`, explicitly deferred** |
| persist question fields into `control_db.step_attempts` | **not added by default** — the phase result carries them; a control-db column/JSON field is a bounded follow-up with a migration, named so a future enablement cannot under-build it | `control/control_db.py` + `control/phase_evidence.py` (if ever enabled) |
| **auto-generation** of child specs (lifecycle index write, parent/child lineage, budget carry-over) | **not added by default** — authoring children is the controller's act; the surface is named in §4 so a future enablement cannot under-build it | `scripts/spec_status.py` + the run ledger + `control.admission` (if ever enabled) |

**Not added:** no new CLI entry point (an existing `agentic-dynamics experiment run` drives it), no
new persistence plane (the run ledger carries the phase result), no second queue, no new lease kind,
no new node/envelope type in the knowledge stream, and no runtime adversary scheduler (§5).

**Why a ranking function is the right size of addition.** The tree's *drive* is a pure selection over
the signals the compiler already measures (for instrumented questions) or a readiness +
authored-priority order (for gates, §3.1); it needs a home to be executable, and the `adapt` phase is
that home. The edges, brakes, and emission contract are authored data over machinery the compiler
already ships; the **executor surface (spec→job, campaign lease, lineage) is not shipped and is
explicitly deferred** (§4.1, a3 `W-9`).

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
acceptance that proves the correction. **The loop is an authored phase-per-campaign, and it does
spend model budget** (a3 `W-14`): `a3_adversarial` is an `agent` phase that runs automatically
whenever the campaign runs (`workflows/repository/control_room_facelift_review.yaml:127-151`), so
"authored" vs "runtime" is a naming difference, not a zero-cost property. What is genuinely absent
is a **per-node hook**: no code path constructs an adversary session from another phase's result,
and no phase auto-launches an adversary on a sibling. The declared cost is **one model call per
adversary phase**; the campaign's `StopSpec` budget must enumerate the adversary phases it runs, and
a future per-layer adversary must be added to that budget rather than silently multiplying it.

**Where the loop sits in the tree.** The adversary is not a leaf question and not a per-node hook —
it is a *review layer* that can be scheduled against any node's emitted
`(question, acceptance, kill_criterion, conclusion)` tuple. In the facelift workflow it runs as
`a3_adversarial` over both a1 and a2; a future campaign can instantiate the same shape per
structure layer without new machinery, because the emitted tuple already carries everything the
attack table consumes.

---

## 6. Worked example — growing this facelift's tree

**Illustrative, not exhaustive** (a3 `W-11`): sixteen questions demonstrate the protocol's shape and
its first move; they do **not** claim to cover all 26 a1 tasks, and the selection replay below is a
demonstration — not a proof that the emitted wave equals a1's authored plan (the earlier draft's
"plan and drive agree" equivalence claim failed its own test and is withdrawn). Every question
carries a unique id; the coverage requirement the *drive* must enforce is stated in §7. Kill criteria
are the five v2 conflicts plus the a6 gate misses, so the tree cannot regrow a rejected idea.

| Q | Layer | Question | Acceptance (named gate) | Kill criterion | a1 task | Uses (external) |
|---|---|---|---|---|---|---|
| Q1 | intent | Does the resting screen communicate the run-first thesis to a stranger? | direction §4.2 recognizability test (class B scorecard — **consumed** from Q12, not owned) | a generic-dashboard comparator passes all five direction §4.2 sentences | F02a/F02b (acceptance), first-wave gate | direction §4.2; note v2 C12 is the *human-experience contract* (v2:201, §3.4), not blind comprehension (a3 D-9) |
| Q2 | intent | Which v1 proposals survive reconciliation with the direction? | v2 §6 table, each row statused | a proposal not in the direction is scheduled as-is | this plan §0 | v2 §5 |
| Q3 | structure | Can R0 answer `ON-G1`/`ON-G6` with no KPI tile row? | render gate `ON-G1`/`ON-G6` + no-tile assertion | a `.stat-tile` appears in R0 | F07 | v2 T2/T3 |
| Q4 | structure | Does the row keep the E10 identity+lease+claim/proof contract on mobile? | mobile blind-comprehension fixture + G-13 row values incl. `spec/cell` | any identity field is ellipsised on mobile | F11 | v2 O2/O4 |
| Q5 | structure | Does one attention item expand in place with one compact empty state? | fixture F-1 + screenshot + one-empty-state assertion | repeated filler cards return | F09 | v2 C3 |
| Q6 | structure | Does R4c render typed rungs + a five-stage causal spine? | fixture (waiting/failed/money-risk) + gate | raw JSON transcript becomes the spine | F17 | v2 C8 |
| Q7 | behavior | Does one transition-only announcer replace the current one? | announcer unit tests (initial/decreases silent; identical re-announces) | two live regions are required | F06 | v2 T7 |
| Q8 | behavior | Do counts filter with a refresh-age caveat (no stale delta)? | gate G-14 + click-through + stale fixture | a bare delta renders from a stale poll | F08 | v2 T3/T4/A-6 |
| Q9 | behavior | Is approval-pause a confirmed controller act, never automatic? | no unconfirmed pause path + receipt | any threshold auto-steers | F10 | v2 C4/A-4 |
| Q10 | behavior | Does a steer/reply show target/scope/reversibility + receipt? | authority test + receipt fixture | an unguarded terminal write appears | F20 | v2 H2/A-12 |
| Q11a | verification | Can the gate no longer pass on a duplicate/overwritten selector, an overflowing answer, or a clipped label? | seeded-bad fixture set makes the gate exit 1 | a gate hole survives | F01a | a6 G-1/G-3/G-5/G-6 |
| Q11b | verification | Can the gate no longer pass on a value that disagrees with its fixture? | seeded-bad fixture (wrong `ON-G4`, wrong buckets, duplicate writer) exits 1 | a gate hole survives | F01b | a6 G-10/G-11/G-13/G-14/G-15 |
| Q12 | verification | Do all four canonical test classes exist and fail on a seeded violation? | **full gate** green + a schema-valid `b_comprehension.json` (**recorded human pass**) with a seeded miss, consumed by F02b | DOM presence is treated as a pass | F02a, F02b | direction §18 gate order; D6 |
| Q13 | verification | Do the forcing fixtures exist? | each fixture renders its distinguishing field | empty fixtures pass | F03 | v2 C7/C11 |
| Q14 | presentation | Do the tokens hold forced-colors + the restraint budget? | **computed-style contract** across 3 themes (F25a) + recorded blind A/B (F25b) | a second amber / chrome-on-rest / a "KPI rail" restyle survives | F25a, F25b | direction §4.5/§11 (v2 calls the dropped pulse a *decorative pulse*, there is no `no-pulse` id — a3 D-9) |
| Q15 | presentation | Do the two axes the packet **actually emits** render independently without client derivation? | client-spy test + captured-packet fixture (only `active`/`none`/`unknown`) | the renderer derives attention from lifecycle, or a `stale` value appears that no producer emits | F04 (+ parked F27) | `glance.py:568`; direction §2.2; a3 D-6 |
| Q16 | structure | Does a governed ack/steer write a receipt without altering an observe-only flag? | authority test + receipt fixture; **else parked** | an ack can clear or steer a flag | F05 (D1); F20 | direction §12.2.6; a3 T-13 |

**The tree's first move** (readiness filter, then authored priority for gate-shaped questions §3.1):
`Q1` requires the class-B scorecard that `Q12` produces, so `Q1` is **not in the candidate set**
until the verification layer lands. The frontier is therefore the verification questions
`{Q11a, Q11b, Q12, Q13}`; `Q11a`/`Q11b` (the gate's ability to fail) are the prerequisites for
`Q12`/`Q13`, so they are attended first (they are the a1 splits with independent seeded-bad
fixtures), then `Q12`/`Q13`. Once the gate and scorecard are green, `Q1` enters the candidate set;
then the structure frontier `{Q3,Q4,Q5,Q6}` fans out. This *reproduces the shape* of the a1 first
wave — verification first, then state/structure — but it is a protocol demonstration, not a proof:
the a1 wave is authored, and the drive ranks rather than emits it (a3 `W-11`).

**A concrete re-cut.** If `Q4`'s first answer shows mobile cannot carry identity+lease+claim/proof in
one row without overflow, `Q4` expands into `Q4a` (two-line identity band) and `Q4b` (row-lease
compaction); the parent is `open` until both leaves are green. The overflow measurement is the
`produces` that makes `Q4b`'s acceptance concrete.

**What would falsify the design.** Not a replay that "emits the a1 wave" (withdrawn, a3 `W-11`);
instead: (1) a candidate set whose `requires` are all green and whose *instrumented* uncertainties
differ must select the higher-uncertainty question, and an `unimplemented` acceptance must be
provably absent (§3.1); (2) the coverage gate in §7 must reject an a1 task with no question and two
questions claiming the same task as their sole carrier; (3) a question whose gate stays red
unchanged must park after `max_attempts` rather than re-selecting (§3.2).

---

## 7. Anti-thrash and failure modes

| Failure mode | Symptom | Guard |
|---|---|---|
| **Divergence** | a question spawns children without lowering uncertainty | `max_attempts` parks it; a child's acceptance must be strictly more concrete than the parent's |
| **Cycling** | two questions keep re-opening each other | the only feedback edge is `adapt → cells` (`compile_experiment.py:96`); any new cycle is a design error, not a feature |
| **Budget burn** | the drive keeps selecting high-effect but low-value questions | `budget_usd` + admission lease; high regret with no owner is a kill, not a spend |
| **Vacuous acceptance** | a gate that cannot fail | every acceptance names a seeded violation (a3's first attack) |
| **Unmapped task** | a question tree omits an a1 task, or two questions claim the same sole task | the drive's coverage gate refuses an a1 task with no `source` and two questions claiming the same task as their sole carrier (a3 `W-11`) |
| **Red-acceptance loop** | a gate stays red and is re-selected forever | the non-cell attempt counter parks the question after `max_attempts` unchanged re-runs (§3.2; a3 `W-12`) |
| **Authority drift** | a question quietly expands the mutation surface, or a design phase registers an open question as `MEASURED` | the adversary checks for new route classes / auto-actuation; direction §12.2 is the fence; the question path sets `ADVISORY` explicitly and never inherits `test_executed_success` (a3 `W-13`) |
| **Unmeasured `requires`** | a control question consumes a signal no rule produces | `validate_rules` refuses it (`experiment_spec.py:899-963`) — the compiler is the guard |
| **Wall-clock runaway** | a phase spins past its window and is counted as success | `PhaseResult.timed_out` is a runner truth (`workflow_runner.py:229-234`); the watchdog parks the frontier |

---

## 8. What already exists vs what is new (contract table)

| Capability | Status | Anchor |
|---|---|---|
| spec object + free-form `question` | **WRITTEN** | `experiment_spec.py:675` |
| `requires`/`produces` gate | **WRITTEN** | `experiment_spec.py:899-963` |
| 7-phase DAG + `adapt → cells` feedback | **WRITTEN** | `compile_experiment.py:35,88-97` |
| factorial fan-out (`experiment_matrix`) | **WRITTEN** | `compile_experiment.py:108-129` |
| regret/effect (`compare_arms`) | **WRITTEN** | `compile_experiment.py:166-316` |
| per-rule uncertainty + `state` (`RuleResult`) | **WRITTEN** | `compile_experiment.py:322-342` |
| `AdaptSpec` strategy/selection | **declared + validated, no consumer** | `experiment_spec.py:627-640`, `:39`, `:1090-1097` |
| `StopSpec.uncertainty_threshold` | **declared, no consumer** | `experiment_spec.py:602-623` |
| structured question/acceptance/kill on a phase result | **ABSENT** | `runtime/workflow_runner.py:216-400` |
| emission of new questions/conclusion | **slot exists, never set** (authority now explicit `ADVISORY`; recording is a prerequisite) | `knowledge/knowledge_ingestion.py:485,538-540` |
| child-spec generation from selection | **ABSENT** — children authored by default (§4) | — |
| spec→job executor (compile→enqueue→worker) | **ABSENT** — deferred, sized `L` (§4.1) | — |
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
- **The brake is `StopSpec` plus the runner wall.** Budget/attempts/threshold already exist; time is
  the existing phase timeout/watchdog, named rather than invented.
- **The transport is the queue — for authored children.** A child is admitted by the lease gate and
  drained by the existing workers **only because it is authored into a workflow's `phases:` list**;
  the spec→job executor does not exist (a3 `W-9`, §4.1). The design claims no more than that.
- **The adversary is an authored phase.** It is data in the workflow spec, not a scheduling loop —
  but it is an auto-running phase that spends (a3 `W-14`, §5).

If a future session wants a runtime self-generating campaign, the missing pieces are the `adapt`
executor **and** the spec→job executor, both named and sized in §4.1; everything else is authored
data.

---

## 10. Adversarial dispositions (a3 → a2)

| a3 | Status | Resolution in this design |
|---|---|---|
| W-1 new-mechanism surface | **accepted** | Children are **authored by default**; the auto-generation surface (lifecycle index, lineage, budget carry-over) is enumerated in §4.1 so a future enablement cannot under-build it. |
| W-2 non-convergence | **accepted (amended)** | Uncertainty is a posterior **only for instrumented acceptances**; a gate acceptance is binary, so selection falls to readiness + authored priority (§3.1, a3 `W-10`). |
| W-3 runtime adversary | **accepted** | No code path launches an adversary from a phase result; the loop is an authored phase-per-campaign that does spend (§5, a3 `W-14`). |
| W-4 incommensurable score | **accepted** | Weighted sum replaced with a **lexicographic** order over the declared strategies, with deterministic tie-breaks (§3). |
| W-5 knowledge-authority pollution | **accepted** | Emission stops at the phase result/ledger; the question path sets `ADVISORY` **explicitly** and never inherits the test bool (§4, a3 `W-13`). |
| W-6 readiness tie-break | **accepted** | Readiness is a **hard admissibility filter** before scoring; no depth heuristic (§3, §6). |
| W-7 budget ownership | **accepted** | Children reserve against the **campaign** lease; the parent reservation is not double-counted and settles once (§4 step 4). |
| W-8 "time" not in `StopSpec` | **accepted** | The brief's third brake is named honestly as the runner wall (phase `timeout` + watchdog), not smuggled into `StopSpec` (§3.2). |
| W-1 (auto-gen) | **accepted (deferred)** | Auto-generation is not enabled by default; decision W1 owns it. |
| W-9 compiler "substrate" is a plan | **accepted** | Bounded to authored phases; the spec→job executor is named and sized `L` in §4.1, not built (§4 step 4, §9). |
| W-10 circular convergence + vacuous falsifier | **accepted** | `uncertainty` defined only for instrumented acceptances; gates are readiness + authored priority; the falsifier is restated so it can fire (§3.1, §6). |
| W-11 worked-example equivalence | **accepted** | §6 is marked illustrative, the "plan and drive agree" claim is withdrawn, Q1/Q12 are de-duplicated, a coverage gate is added (§6, §7). |
| W-12 red-acceptance thrash | **accepted** | A non-cell attempt counter (a re-run of the acceptance) parks an unchanged red acceptance after `max_attempts` (§3.2). |
| W-13 authority guard does not bind | **accepted** | The recorder on `PhaseResult` is a prerequisite; authority is `ADVISORY` explicitly, never inherited from `test_executed_success` (§4). |
| W-14 adversary cost unstated | **accepted** | The loop is stated as an authored phase-per-campaign with a declared one-call cost; the campaign budget enumerates adversary calls (§5, decision W8). |
| D-9 unresolved anchors (as it touches a2) | **accepted** | Q1's blind-comprehension anchor is direction §4.2 (v2 C12 is the *human-experience contract*); Q14's "no-pulse" is direction §11's *decorative pulse*; the herdr pins are v2 H1–H3 (§6). |

**Rejected sub-demands (one line each).** No finding is rejected outright; one sub-demand is.

- **D-9's blanket "re-anchor every cited id to a v2 §2 pin" — rejected as stated:** the v2 pins already
  cover the mechanisms (H1/H2/H3, L4, T6); "Brain" is a **v1** source and is correctly anchored to
  `control_room_ui_reference_synthesis.md` §2.1, so forcing a v2 pin would be a false citation. The
  accepted part (fix Q1's C12 misuse, retire the `no-pulse` id) is folded in above.

---

## 11. Controller decisions needed (open choices only — a4)

The genuinely open choices this design cannot resolve from the compiler contracts and the accepted
direction.

| # | Decision | Why it blocks | Default if silent |
|---|---|---|---|
| W1 | Adopt `select_next_question` + the structured phase keys as the campaign engine, and are children **authored** or **auto-generated**? | auto-generation adds a spec-lifecycle write + lineage + budget carry-over (a3 W-1); authoring keeps it small | authored children; the drive ranks, the controller writes |
| W2 | Which `AdaptSpec` strategy is the default drive (`coordinate_descent` vs `manual`)? | `manual` keeps the controller at the frontier; `coordinate_descent` automates selection | `manual` |
| W3 | May a child spec spend within the **campaign** lease without a per-child approval? | the admission gate already permits lease-scoped P1 spend; this confirms the campaign's authority and fixes the no-double-count rule (a3 W-7) | controller approves each child; no double-count |
| W4 | Is the question-level adversary a static authored phase only (never a runtime scheduler)? | a runtime adversary adds model calls and a new mechanism to a design task (a3 W-3) | static authored phase only; its per-campaign calls are enumerated in the campaign `StopSpec` (`W-14`) |
| W5 | For gate-shaped questions (no measured posterior), is selection **readiness + authored priority** acceptable, or must every question map to an instrumented rule first? | the information-gain drive is only defined where a posterior exists (a3 `W-10`); instrumenting every gate question is a much larger program | readiness + authored priority for gates; information gain for instrumented questions |
| W6 | How many **unchanged red re-runs** of a non-cell acceptance park a question? | bounds the red-acceptance loop (a3 `W-12`); too low kills a fixable question, too high burns budget | `max_attempts` (default 2), then `parked` |
| W7 | Is the `PhaseResult` question/acceptance/kill/conclusion recorder in scope (a prerequisite, not optional)? | without it the `conclusion` slot is silently empty and a question can be registered `MEASURED` (a3 `W-13`) | in scope; recording lands with the drive |
| W8 | Does the campaign budget explicitly enumerate adversary phases (one call each)? | otherwise the adversary's cost is invisible and the campaign can overrun (a3 `W-14`) | yes; the `StopSpec` budget lists every adversary phase |
