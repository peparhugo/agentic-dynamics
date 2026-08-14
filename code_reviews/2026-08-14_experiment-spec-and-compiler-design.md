# ExperimentSpec + Compiler — Design Specification

Status: proposed (v2, corrected) · Owner: AI FinOps Dynamics instrument
Date: 2026-08-14 · Supersedes: the v1 framing in this file (policy-vs-experiment split,
OVAT-as-design, "bandit end-state") — all removed; see §3 for the correction.

---

## 1. What this repo actually is

An **information-acquisition machine for AI economics**.

The experiments are captured in the repo *because they are the information* — and
you cannot make policies without information. The chain is:

```
cells (controlled trials) → raw events → information (measurement rules)
     → policies (control rules) → policy arms → grid → campaign → repeat
```

Everything else — the rules, the ledger, the write-ups, the site — is a stage in that
chain. The primary product is **information**; policies are what the information
*makes possible*.

## 2. The core objects

| Object | Definition |
|---|---|
| **Cell** | One controlled trial: a workflow + a factor assignment (story, tier, model, condition, policy) + instrumentation. The atomic information-producing unit. |
| **Experiment** | A grid of cells — the cross-product of the factors. A systematic information-acquisition pass. |
| **Campaign** | A sequence of grids; between grids, **tweak one variable** and re-run. Sustained acquisition. |
| **Policy** | A decision rule `decide(job, state) → {route, depth, retry, escalate, budget, deadline}`. **A policy is a factor level in the grid** — the winning arm *is* the controller. |
| **Information** | The metrics the measurement rules emit (first-pass, grit, confidence, regret…). The product. |

## 3. The load-bearing rule: policies consume information

> **To make policies, we need information.**

A policy is a decision rule over signals. You cannot write "escalate when
`confidence < θ`" until `confidence` is measured. So the ordering is a hard
constraint, not a preference:

```
instrument (ledger: events, attempts, tokens, timestamps)
   → derive  (measurement rules → information)
   → write policy (control rules consuming that information)
   → grid    (policy as an arm, compared against other arms)
   → campaign (tweak one variable, repeat)
```

This is enforced **by the compiler**, not by convention. `RuleSpec` declares the
information it *consumes* (`requires`) and *emits* (`produces`). The compiler
refuses to admit a control rule whose `requires` are not satisfied by the ledger
schema or by the `produces` of measurement rules in the same spec:

```
ERROR: policy arm "dynamics" requires [confidence, first_pass, deadline_slack]
       — not produced by the ledger or any rule in this spec. Instrument these first.
```

That validation is the executable form of "to make policies, we need information."
It also resolves the control/measurement split into its real meaning: **measurement
rules produce information; control rules consume it.** A control rule literally
cannot run until its inputs exist.

## 4. Schema

```python
# src/instrument/experiment_spec.py

@dataclass
class Workflow:
    kind: str            # "story" | "task" | "experiment" | "agent_task"
    params: dict

@dataclass
class Factor:
    name: str            # "model" | "condition" | "policy" | "seed" | "strength"
    levels: list
    active: bool = True
    current: Any = None

@dataclass
class RuleSpec:
    name: str
    plane: str           # "measurement" (produces information) | "control" (consumes it)
    evidence_class: str  # [M] [C] [H] [P]
    requires: list[str]  # information fields this rule CONSUMES (ledger or other rules)
    produces: list[str]  # information fields this rule EMITS (measurement rules)

@dataclass
class MetricSpec:
    name: str; agg: str; over: str    # mean | distribution | ratio  ×  outcome | attempt | job | cell

@dataclass
class ComparisonSpec:
    kind: str            # routing_regret | policy_diff | effect_size
    arm_factor: str      # the factor being compared (e.g. "policy")
    loss: dict           # {cost, quality, latency, sla, value}

@dataclass
class WriteupSpec:
    format: str; sections: list       # the human-readable INFORMATION

@dataclass
class StopSpec:
    budget_usd: float | None
    max_attempts: int | None
    uncertainty_threshold: float | None

@dataclass
class AdaptSpec:
    strategy: str        # coordinate_descent | manual   (one-variable tweak per iteration)
    selection: str       # highest_uncertainty | highest_regret | largest_effect

@dataclass
class ExperimentSpec:
    name: str
    question: str
    version: str
    workflow: Workflow
    factors: list[Factor]      # policy is a first-class factor here
    design: str                # "factorial" (cross-product) — the cells ARE the grid
    rules: list[RuleSpec]      # dependency-validated via requires/produces
    metrics: list[MetricSpec]
    comparison: ComparisonSpec | None
    writeup: WriteupSpec
    stop: StopSpec
    adapt: AdaptSpec           # campaign loop: tweak one variable → emit next grid
    git_sha: str = ""; pricing_version: str = ""; seed: int | None = None
```

## 5. Worked example — the flagship experiment

```yaml
# experiments/specs/routing_regret.yaml
name: routing_regret_under_degradation
question: >-
  Does a dynamics controller that escalates on measured confidence beat
  static cheapest/premium policies in accepted-cost-per-outcome?
version: "0.2"
workflow:
  kind: story
  params: {stories: [task_manager_api, static_site_gen, notification_service]}
factors:
  - {name: model,    levels: [flash, luna, pro, haiku, terra, sonnet, sol]}
  - {name: condition, levels: [clean, bad_seed, early_degrade, late_degrade]}
  - {name: policy,   levels: [cheapest, premium_static, quality_cascade, dynamics]}
design: factorial            # cells = cross-product of the three factors

rules:
  # measurement — produces the information the policies consume
  - {name: first_pass_quality, plane: measurement, evidence_class: "[M]",
     requires: [attempt_number, accepted, evaluator_independent],
     produces: [first_pass_rate, accepted_outcome]}
  - {name: grit,               plane: measurement, evidence_class: "[M]",
     requires: [perturbation_strength, test_executed_success, condition],
     produces: [grit, retention, grit_auc, recovery_premium]}
  - {name: outcome_multiplier, plane: measurement, evidence_class: "[P]",
     requires: [value, rework_cost, reuse_value],
     produces: [net_value]}
  # control — consumes that information
  - {name: model_cascade,      plane: control, evidence_class: "[H]",
     requires: [confidence],            # ← NOT produced above yet
     produces: [escalation_decision]}
  - {name: budget_ceiling,     plane: control, evidence_class: "[P]",
     requires: [budget, forecast_cost, actual_cost],
     produces: [admit_or_halt]}

metrics:
  - {name: cost_per_accepted_outcome, agg: mean, over: outcome}
  - {name: first_pass_rate,           agg: ratio, over: job}
  - {name: escalation_rate,           agg: ratio, over: job}
comparison:
  kind: routing_regret
  arm_factor: policy
  loss: {cost: 1.0, quality: 5.0, sla: 2.0, value: -3.0}
writeup: {format: lab_book, sections: [hypothesis, method, results, interpretation]}
stop: {budget_usd: 40.0, uncertainty_threshold: 0.05}
adapt: {strategy: coordinate_descent, selection: highest_regret}
```

**The compiler refuses this spec as written** — `model_cascade` requires `confidence`,
and `grit` requires `perturbation_strength` + `test_executed_success`; none are produced
by the ledger yet. The correct move is to *instrument those fields first*, then re-run.
That refusal is the architecture doing its job: it tells you what to measure next.
(Note the asymmetry — `first_pass_quality` and `outcome_multiplier` consume ledger fields
that already exist, so they are admissible; `grit` and `model_cascade` are gated because
their inputs are not yet instrumented.)

## 6. The compiler — spec → DAG

```
spec
 ├─ validate    (no phase)        — resolve requires/produces; refuse unmet control inputs
 ├─ cells       (experiment_matrix) — factors' cross-product → jobs
 ├─ execute     (experiment_run)    — enqueue → workers → attempts
 ├─ measure     (evaluate_rules)    — measurement rules over the ledger → information
 ├─ compare     (compare_arms)      — regret/effect over the arm factor
 ├─ writeup     (writeup)           — the human-readable information
 └─ adapt       (adapt)             — tweak one variable → emit the next spec
```

Reuse (no new machinery):

| New kind | Generalizes / replaces |
|---|---|
| `experiment_matrix` | `_gen_matrix_cells` (pipeline.py:394) + `enqueue.py` matrix — deletes both |
| `experiment_run` | existing `enqueue.py` + `worker.py` + `run_story.py` — unchanged transport |
| `evaluate_rules` | the 14 lab books, driven by `spec.rules` |
| `compare_arms` | `routing.simulate_strategies` — arms become data |
| `writeup` | lab-book template from `spec.question` + metrics |
| `adapt` | new — the campaign loop (one variable at a time) |

## 7. The data model — the ledger that produces the information

A `job` has N `attempts`. Every field below is **information** a later rule may
consume.

```python
@dataclass
class JobRecord:
    job_id; spec_id; workflow
    factors: dict              # {model, condition, policy, seed, …}
    policy_arm; policy_id
    budget; due_at; forecast_cost; forecast_latency
    status: str                # queued | leased | running | accepted | failed | dead_letter

@dataclass
class AttemptRecord:
    attempt_id; job_id; parent_attempt_id
    attempt_number; retry_reason
    escalation_from; escalation_to
    model; provider_model_version
    queued_at; leased_at; started_at; first_token_at; ended_at
    tokens: dict               # {in, out, reasoning, answer, explanation}
    cache_hit; tool_calls; queue_wait_ms; service_time_ms
    completed; first_pass; accepted; evaluator_independent
    confidence: float | None            # ← UNMEASURED; model_cascade needs it
    perturbation_strength: float | None # ← UNMEASURED; grit needs it (the s axis)
    test_executed_success: bool | None  # ← UNMEASURED; grit needs it (verified success)
    cost: dict                 # {inference, orchestration}
    rework_cost; reuse_value
```

The `confidence` field is the concrete example of the gap: it's what the "dynamics"
arm wants and the ledger doesn't produce yet. `perturbation_strength` +
`test_executed_success` are what the `grit` rule needs (Grit(s) is a retention curve
over strength conditioned on verified success, per `basin.py`). `answer`/`explanation`
token split unlocks Explanation Tax. Everything else is bookkeeping that the rules need.

## 8. Rule evaluator interface

```python
@dataclass
class RuleResult:
    rule: str; metric: float; evidence_class: str; uncertainty: float
    produces: dict            # the information this rule emits

def first_pass_quality(attempts) -> RuleResult: ...   # measurement (produces)
def model_cascade(attempts, state) -> RuleResult: ... # control (consumes confidence)
```

- `measure` = measurement rules over the ledger → information.
- `control` = control rules at enqueue/lease time, writing `policy_arm`, `budget`,
  `due_at`, escalation tiers into the job payload.

## 9. The campaign loop (the "dynamics")

`adapt` reads `compare`'s regret per arm and **tweaks one factor** — drop the worst
arm, sweep a new factor, or tighten a level — emitting the next spec. This is the
sustained information-acquisition loop. It is *not* a separate controller; the
winning arm from the grid already is the controller.

## 10. Recursion

`Workflow.kind == "experiment"` makes a campaign an experiment of experiments of
cells. Same interpreter at every level. `agent_task` makes the agent itself a
measurable workflow.

## 11. Reproducibility

Every run pins `git_sha`, `pricing_version`, `dataset_hash`, `seed`,
`provider_model_version`, `instrument_version`. The write-up emits them;
`generate_manifest.py` verifies them.

## 12. Implementation order (corrected — measure first)

1. `experiment_spec.py` — dataclasses + loader + **the requires/produces validator**.
2. `compile_experiment.py` — spec → DAG; `experiment_matrix` generalizes
   `_gen_matrix_cells`; `compare_arms` generalizes `routing.simulate_strategies`;
   `evaluate_rules` + `RuleResult` interface, with `grit` gated until its inputs exist.
3. Instrument the missing information — **`confidence`** (for `model_cascade`/`dynamics`),
   **`perturbation_strength` + `test_executed_success`** (for `grit`), plus
   attempt/timestamp fields and the `answer`/`explanation` token split. Until these are
   in the ledger, the validator refuses the rules that consume them.
4. `adapt` — tweak one factor, emit the next grid.
5. Run `routing_regret.yaml` end-to-end; the validator gates when the "dynamics" arm
   is actually admissible.

The whole thing is: **capture information → make policies → put policies in the grid
→ capture more information.** The spec/compiler just keeps that chain honest.
