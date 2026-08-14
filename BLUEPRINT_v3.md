# Blueprint v3 — Information-Acquisition Machine (ExperimentSpec + Compiler)

**Status:** Design approved (`code_reviews/2026-08-14_experiment-spec-and-compiler-design.md`).
Agent-facing docs synced. **Steps 1–2 done** (`experiment_spec.py` + validator,
`compile_experiment.py` → DAG, plus the real `grit` rule). **Step 3 in progress**:
`scripts/verify_tests.py` (independent test execution) is built and running; the ledger
instrumentation (`confidence`, `perturbation_strength`, `test_executed_success`) is next.
Supersedes `BLUEPRINT_v2.md` (which ends at v0.9 / pre-spec next-steps).

---

## Part 1: The reframe

This repo is not a measurement library. It is an **information-acquisition machine for AI
economics**. The chain:

```
instrument (ledger: events, attempts, tokens, timestamps)
   → derive  (measurement rules → information)
   → write policy (control rules consuming that information)
   → grid    (policy as an arm, compared against other arms)
   → campaign (tweak one variable, repeat)
```

The primary product is **information**; policies are what the information makes possible. The
spec/compiler just keeps that chain honest — the compiler refuses to admit a control rule whose
`requires` are not produced by the ledger or a measurement rule in the same spec.

## Part 2: As-built foundation (what exists today)

Verified current state (Aug 2026):

| Layer | State |
|---|---|
| Modules | 35 modules in `src/instrument/` (+ `__init__.py`): 33 measurement modules + `experiment_spec.py` + `compile_experiment.py` |
| Scripts | 75 `scripts/*.py` (experiment runners, analysis, data pipeline, `verify_tests.py`) |
| Configs | 34 experiment YAML configs (+ `plans.yaml`) |
| Lab books | 19 active `lab_*.py` + 8 `*_DEPRECATED_bge_m3` |
| Corpus | 224+ game reports, `_results_summary.json`, trajectory summaries, `inventory.json`, 221 story cells (1045 sessions) |
| Stories | 3 built-in stories × 2 tiers × 2 qualities × 4 conditions; 221 cells, 1045 sessions |
| Transport | `enqueue.py` + `worker.py` + `run_story.py` (Redis on port 6380); `pipeline.py` (11 phase kinds) |
| Website | `firebase/public/*` — `build_data.py` → `data.js`, provenance-tagged |
| Tests | 30 test modules (`test_experiment_spec.py`, `test_compile_experiment.py` added) |

Deprecated (ignore for new work): `experiment.py`, `adapter.py`, `lab_book.py`,
`scripts/plan.py`.

The spec/compiler layer is now real code, not a proposal:

```
spec (ExperimentSpec) ──compile──▶ DAG ──▶ cells ──▶ jobs ──▶ attempts ──▶ ledger
      ▲                                                                      │
      └──── adapt (tweak one factor) ◀── compare ◀── information ◀── measure ◀┘
```

- `experiment_spec.py` — dataclasses + YAML loader + the **requires/produces validator** (the gate).
- `compile_experiment.py` — `compile_spec` (validate → cells → execute → measure → compare →
  writeup → adapt, with an `adapt → cells` campaign-loop edge), `experiment_matrix`
  (generalizes `_gen_matrix_cells`), `compare_arms` (generalizes `simulate_strategies`),
  `evaluate_rules` + `RuleResult`.
- The validator **refuses** the flagship spec with one error per unmet field:
  `grit` needs `perturbation_strength` + `test_executed_success`; `model_cascade` needs
  `confidence`. Symmetric in both directions — *control rules* are refused until their
  information is measured; *measurement rules* are refused until their inputs are instrumented.

## Part 3: The core objects (from the design doc)

| Object | Meaning |
|---|---|
| **Cell** | One controlled trial: workflow + factor assignment + instrumentation. The atomic information-producing unit. |
| **Experiment** | A grid of cells — cross-product of factors (`design: factorial`). |
| **Campaign** | A sequence of grids; between grids, tweak one variable and re-run. |
| **Policy** | `decide(job, state) → {route, depth, retry, escalate, budget, deadline}`. **A factor level in the grid** — the winning arm *is* the controller. |
| **Information** | Fields measurement rules emit (first-pass, grit, confidence, regret…). |

`Workflow.kind ∈ {story, task, experiment, agent_task}` makes the same interpreter run at every
scale — a campaign is an experiment of experiments of cells, and the agent itself is a measurable
workflow.

## Part 4: The load-bearing rule — implementation order

> **To make policies, we need information.**

`RuleSpec` declares `requires` (information it consumes) and `produces` (information it emits).
`plane` is `"measurement"` (produces) or `"control"` (consumes). The validator refuses unmet
`requires`:

```
ERROR: policy arm "dynamics" requires [confidence, first_pass, deadline_slack]
       — not produced by the ledger or any rule in this spec. Instrument these first.
```

**Build order (each step is a discrete unit of work):**

| # | Task | Generalizes | Gate |
|---|---|---|---|
| 1 | ~~`src/instrument/experiment_spec.py` — dataclasses + YAML loader + **requires/produces validator**~~ **DONE** | — | validator rejects unmet control inputs |
| 2 | ~~`src/instrument/compile_experiment.py` — spec → DAG (+ `grit` rule)~~ **DONE** | `experiment_matrix` → `_gen_matrix_cells` (`pipeline.py:394`); `compare_arms` → `routing.simulate_strategies` (`routing.py:98`) | DAG phases: validate → cells → execute → measure → compare → writeup → adapt |
| 3 | **Instrument the missing information** — `confidence` (for `model_cascade`/`dynamics`), `perturbation_strength` + `test_executed_success` (for `grit`), plus attempt/timestamp fields and the `answer`/`explanation` token split | ledger (`AttemptRecord`) | `model_cascade`/`dynamics` and `grit` become writable/measurable |
| 4 | `adapt` — campaign loop: tweak one factor, emit next grid | new (one-variable coordinate descent) | `AdaptSpec.selection` |
| 5 | `experiments/specs/routing_regret.yaml` end-to-end | lab-book template + `routing.simulate_strategies` | validator gates the `dynamics` arm until step 3 is done |

Step 3 is the fulcrum, and its shape is now **verified against real data** (see below) — not
hypothesized. Everything else reuses existing transport — no new queue/worker machinery.

### Step 3 concretized — the verified instrumentation gaps

Running the real `grit` rule against the current corpus surfaced three concrete blockers, each
confirmed by inspecting the data (not speculation):

1. **`test_executed_success` is not uniformly captured by the backends.** `claude_adapter.py`
   records `tests_passed=0/tests_total=0` for haiku (and only 10/155 sessions for sonnet), while
   the opencode backend captures it fully. The model's self-report is unreliable — but running the
   suite ourselves recovers it (haiku's worktree passes 106/106 under `pytest`). Fix: the harness
   runs the tests, not the model's claim.
   → **Built**: `scripts/verify_tests.py` runs `pytest`/`jest` against each cell's final commit and
   writes `experiments/results/verified_tests.json` (running against 221 cells in the background).
2. **`perturbation_strength` is not a first-class field.** It lives in filenames (`_s0.5`) at a
   single strength, or not at all (`exp_*` entries). The story corpus has categorical `condition`,
   not a strength axis. Fix: record `perturbation_strength` (and `condition`) on every attempt.
3. **`evaluator_independent=False` everywhere.** Even where tests pass, they are agent-authored
   (the model passes tests it wrote). Independent *execution* is not independent *test generation*;
   the latter needs held-out tests (separate model, pre-experiment — the blueprint's P3 item).

These three are the acceptance criteria for step 3: when `verify_tests.py`'s output is a
first-class ledger field, `perturbation_strength`/`test_executed_success` are on every attempt,
and `confidence` is instrumented, the validator will admit the flagship's `grit` + `dynamics` arms.

## Part 5: Flagship experiment

```yaml
name: routing_regret_under_degradation
workflow: {kind: story, params: {stories: [task_manager_api, static_site_gen, notification_service]}}
factors:
  - {name: model,     levels: [flash, luna, pro, haiku, terra, sonnet, sol]}
  - {name: condition, levels: [clean, bad_seed, early_degrade, late_degrade]}
  - {name: policy,    levels: [cheapest, premium_static, quality_cascade, dynamics]}
rules:
  - {name: grit, plane: measurement, evidence_class: "[M]",
     requires: [perturbation_strength, test_executed_success, condition],
     produces: [grit, retention, grit_auc, recovery_premium]}   # refused until strength+success measured
  - {name: model_cascade, plane: control, evidence_class: "[H]",
     requires: [confidence], produces: [escalation_decision]}   # refused until confidence measured
comparison: {kind: routing_regret, arm_factor: policy,
             loss: {cost: 1.0, quality: 5.0, sla: 2.0, value: -3.0}}
stop: {budget_usd: 40.0, uncertainty_threshold: 0.05}
adapt: {strategy: coordinate_descent, selection: highest_regret}
```

The `loss` dict is the policy objective space (cost, quality, latency, sla, value). The
`adapt.selection` is the one-way/two-way-door knob: `highest_uncertainty` (reversible — probe a
factor) vs `highest_regret` (drop a losing arm — irreversible).

`grit` produces a **retention curve** (`Grit(s) = P(test_executed_success | strength=s)`,
`R(s) = G(s)/G(0)`, AUC, recovery premium), not a scalar — the corrected §5 rule in the design doc.

## Part 6: Scaling beyond AI FinOps

The instrument generalizes from "how does a coding task's cost/outcome change as specification
quality degrades" to **grid-state dynamics of arbitrary agent workflows**:

- **Measurement rules** → any information a policy needs (token usage, cost, solution quality,
  maintainability, cost-of-maintainability, long-horizon scalability).
- **Control rules** → routing policies for one-way and two-way doors, escalation tiers, budget
  ceilings, deadlines — each a `Factor` level compared in the grid.
- **`Workflow.kind == "experiment"`** → campaigns of campaigns; the same compiler, validator,
  and writeup at every recursion depth.
- **`agent_task`** → the agent itself is a measurable workflow, so the control plane that runs
  experiments is itself a subject of experiment.

The machine is: **capture information → make policies → put policies in the grid → capture more
information.** The spec/compiler keeps that loop honest at every scale.

---

*Updated August 2026. Reflects the approved design, the verified as-built state, and the
measure-first build order.*
