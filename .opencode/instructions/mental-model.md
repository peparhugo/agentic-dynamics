# File map, signatures, and dependencies. No theory. No methodology.

This repo is an **information-acquisition machine for AI economics**: controlled
trials (cells) → raw events → information (measurement rules) → policies (control
rules) → policy arms → grid → campaign → repeat. Everything below is one stage in
that chain. Design of the spec/compiler: `code_reviews/2026-08-14_experiment-spec-and-compiler-design.md`.

## Architecture

```
        ┌──────────────────────── the cycle (information acquisition) ─────────────────────────┐
        │                                                                                        │
        ▼                                                                                        │
  spec (ExperimentSpec) ──compile──▶ DAG ──▶ cells (factor cross-product) ──▶ jobs ──▶ attempts
        ▲                                  │                                            │
        │                                  │                                            ▼
        └──adapt (tweak one factor)── compare ◀── information ◀── measure ◀── ledger (events)
```

Today (code that exists), the execution chain is still the linear core, which the
compiler will generalize (see reuse map below):

```
perturb.py → backends.py → opencode.py / claude_adapter.py → [LLM] → trajectory.py
                        ↓
solution.py + basin.py + efficiency.py + recovery.py → strategy.py → game_report.py

story.py ── mutation.py, commit_analysis.py, review.py, entropy.py, codebase_graph.py, lsp_diagnostics.py
routing.py ── recommend model per task type from experiment results
live.py ──── Redis pub/sub telemetry (feeds admin portal)
```

## The spec/compiler layer — PARTIALLY BUILT

Two new modules, per the design doc. `experiment_spec.py` is **written** (dataclasses,
YAML loader, requires/produces validator, tests). `compile_experiment.py` is still
**proposed**.

```
experiment_spec.py     — WRITTEN — dataclasses + YAML loader + requires/produces validator
compile_experiment.py  — proposed — spec → DAG; generalizes _gen_matrix_cells + routing.simulate_strategies
```

Core objects (see §2 of the design doc):

| Object | Meaning |
|---|---|
| **Cell** | One controlled trial: workflow + factor assignment (story, tier, model, condition, policy) + instrumentation |
| **Experiment** | A grid of cells — cross-product of factors (design: factorial) |
| **Campaign** | A sequence of grids; between grids, tweak one variable, re-run |
| **Policy** | `decide(job, state) → {route, depth, retry, escalate, budget, deadline}` — **a factor level in the grid** |
| **Information** | The fields measurement rules emit (first-pass, grit, confidence, regret…) |

### The load-bearing rule (hard ordering, enforced by the validator)

> **To make policies, we need information.**

```
instrument (ledger) → derive (measurement rules → information)
  → write policy (control rules consuming that information)
  → grid (policy as an arm) → campaign (tweak one variable, repeat)
```

`RuleSpec` declares `requires` (information it CONSUMES) and `produces` (information
it EMITS). The validator refuses a control rule whose `requires` are unsatisfied:

```
ERROR: policy arm "dynamics" requires [confidence, first_pass, deadline_slack]
       — not produced by the ledger or any rule in this spec. Instrument these first.
```

**Consequence for implementation order: instrument `confidence` (for
`model_cascade`/`dynamics`), `perturbation_strength` + `test_executed_success` (for
`grit`), and attempt/timestamp fields + `answer`/`explanation` token split BEFORE
authoring the arms that consume them.** Those fields are currently UNMEASURED — see the
ledger below. The `answer`/`explanation` split unlocks the Explanation Tax decomposition.

### Reuse map (no new transport machinery)

| New kind | Generalizes / replaces |
|---|---|
| `experiment_matrix` | `_gen_matrix_cells` (`pipeline.py:394`) + `enqueue.py` matrix |
| `experiment_run` | existing `enqueue.py` + `worker.py` + `run_story.py` (unchanged transport) |
| `evaluate_rules` | the lab books, driven by `spec.rules` |
| `compare_arms` | `routing.simulate_strategies` (`routing.py:98`) |
| `writeup` | lab-book template from `spec.question` + metrics |
| `adapt` | new — the campaign loop (one variable at a time) |

## Key Signatures

```
# --- existing execution core (real code) ---
run_opencode_agentic(prompt, *, model, thinking_effort, thinking_budget_tokens,
                     output_token_limit, timeout, silent_mode, enforce_pytest, workdir) -> AgenticResult

perturb_prompt(prompt, operator_name, strength, *, rng_seed) -> (str, Perturbation)

evaluate_solution(code, *, constraints, baseline_code, language,
                  run_pytest, workdir, test_timeout) -> SolutionMetrics

measure_basin_escape(baseline_solution, perturbed_solution, *,
                     baseline_metrics, perturbed_metrics, language) -> BasinMetrics

compute_efficiency(result, *, model, baseline_metrics) -> EfficiencyMetrics
  PROVIDER_PRICING: dict of per-model cost rates

classify_strategy(reasoning, solution, efficiency) -> StrategyReport

run_story(story, *, codebase_path, model, condition, mutation, worktree_root,
          timeout, thinking_budget_tokens, output_token_limit, backend) -> StoryResult
  PerturbationCondition: CLEAN, BAD_SEED, EARLY_DEGRADE, LATE_DEGRADE
  BUILTIN_STORIES: task_manager_api, static_site_gen, notification_service

compile_mutation(spec, operator, strength, *, codebase_path, model, cache_dir) -> MutationArtifact
apply_mutation(artifact, target_path) -> bool

analyze_commit(worktree, commit_hash, language, baseline_ast) -> CommitAnalysis
review_commit(worktree, commit_hash, *, model, timeout, story_id) -> CommitReview
compute_entropy(codebase_path, *, language) -> EntropyProfile
build_graph(codebase_path, *, language) -> CodebaseGraph
run_diagnostics(codebase_path, *, language) -> LSPReport
detect_language(path) -> LanguageProfile
parse_codebase(path, profile) -> CodebaseAST

stream_subprocess(cmd, *, workdir, timeout, on_line) -> StreamResult

run_claude_agentic(prompt, *, model, thinking_effort, thinking_budget_tokens,
                   output_token_limit, timeout, workdir) -> AgenticResult

run_agentic(prompt, *, model, backend, **kwargs) -> AgenticResult
get_backend_for_model(model) -> "opencode" | "claude_cli"

LivePublisher(cell_id).publish_status(status) / .publish_event(event)
make_publisher() -> LivePublisher | None

compute_routing(entries) -> dict   # per-task recs + strategy simulation
recommend_route(task_type, entries, *, correctness_threshold, lead_margin) -> dict
```

### Proposed signatures (spec/compiler — not in the repo yet)

```
# experiment_spec.py
ExperimentSpec(name, question, version, workflow, factors, design, rules,
               metrics, comparison, writeup, stop, adapt, git_sha, pricing_version, seed)
Workflow(kind, params)            # kind: story | task | experiment | agent_task
Factor(name, levels, active, current)
RuleSpec(name, plane, evidence_class, requires, produces)
  plane: "measurement" (produces information) | "control" (consumes it)
  evidence_class: [M] [C] [H] [P]
MetricSpec(name, agg, over)       # agg: mean | distribution | ratio
ComparisonSpec(kind, arm_factor, loss)   # loss: {cost, quality, latency, sla, value}
WriteupSpec(format, sections)
StopSpec(budget_usd, max_attempts, uncertainty_threshold)
AdaptSpec(strategy, selection)    # strategy: coordinate_descent | manual
                                  # selection: highest_uncertainty | highest_regret | largest_effect

# compile_experiment.py
compile_spec(spec: ExperimentSpec) -> DAG   # phases: validate → cells → execute
                                            #         → measure → compare → writeup → adapt
validate_rules(spec) -> list[str]           # errors for unmet requires (the gate)

# rule evaluator
RuleResult(rule, metric, evidence_class, uncertainty, produces)
first_pass_quality(attempts) -> RuleResult   # measurement (produces)
model_cascade(attempts, state) -> RuleResult # control (consumes confidence)
```

### Ledger (the data model rules consume) — PROPOSED

```
JobRecord:    job_id, spec_id, workflow, factors{model,condition,policy,seed},
              policy_arm, policy_id, budget, due_at, forecast_cost, forecast_latency,
              status[queued|leased|running|accepted|failed|dead_letter]

AttemptRecord: attempt_id, job_id, parent_attempt_id, attempt_number, retry_reason,
              escalation_from/to, model, provider_model_version,
              queued_at, leased_at, started_at, first_token_at, ended_at,
              tokens{in,out,reasoning,answer,explanation}, cache_hit, tool_calls,
              queue_wait_ms, service_time_ms, completed, first_pass, accepted,
              evaluator_independent,
              confidence: float | None   # ← UNMEASURED TODAY; model_cascade needs it
              cost{inference, orchestration}, rework_cost, reuse_value
```

## Script map

```
scripts/run.py            — experiment: perturb → invoke → evaluate
scripts/run_story.py      — multi-session story CLI
scripts/analyze_worktrees.py — worktrees → GameReport .md + _results_summary.json
scripts/analyze_trajectories.py — session.jsonl → trajectory JSON
scripts/inventory.py      — refresh, list, stats, worktrees, report
scripts/sync_data.py      — story results → sessions.parquet + stories.parquet
scripts/build_data.py     — inventory+results+parquet → firebase/public/data.js
scripts/validate_session.py — pytest on generated code
scripts/enqueue.py + worker.py — Redis experiment queue
scripts/backfill_artifacts.py + backfill_sonar.py — data migration
scripts/backfill_story_transcripts.py — recover session_{n}.jsonl from opencode.db
scripts/monitor.py        — Redis queue dashboard (--json for machine output)
scripts/review_all.py     — review every story (ThreadPoolExecutor, no Redis)
scripts/review_stories.py + review_worker.py — batch/Redis review runners
scripts/generate_manifest.py — SHA256 manifest
scripts/pipeline.py       — YAML-driven phase orchestration (plans.yaml; 11 kinds)
scripts/plan.py           — [deprecated] hardcoded phase orchestration, superseded by pipeline.py
scripts/compile_experiment.py — [proposed] spec → DAG (see design doc)
19 active scripts/lab_*.py — measurement rules; 8 *_DEPRECATED_bge_m3 to ignore

admin/server.py           — Flask portal: SSE telemetry + routing (port 8000, FINOPS_PORT)
.opencode/tools/dashboard.ts — pull tool: Redis status matrix via monitor.py --json
```

## Test files

```
tests/test_pipeline.py (673L), test_story.py (330L), test_opencode_events.py (212L),
test_mutation.py (205L), test_embeddings.py (200L), test_commit_analysis.py (200L),
test_lsp.py (188L), test_claude_adapter.py (181L), test_trajectory_embedding.py (178L),
test_review_agent.py (151L), test_pricing.py (149L), test_correctness_lineage.py (148L),
test_language.py (143L), test_opencode_analyzer.py (136L), test_graph.py (131L),
test_entropy.py (126L), test_codebase_graph.py (125L), test_ollama_analyzer.py (121L),
test_live.py (91L), test_perturb.py (88L), test_data_integrity.py (72L),
test_routing.py (66L), test_strategy.py (64L), test_recovery.py (58L),
test_adapter.py (53L), test_streaming.py (49L), test_backends.py (30L)
```

## Navigation

```
Task: instrument logic → Read src/instrument/CONTEXT.md
Task: experiments     → Load skill: instrument
Task: analysis        → Load skill: analyze
Task: lab books       → Load skill: lab-books
Task: pipeline        → Read scripts/CONTEXT.md
Task: website         → Read firebase/CONTEXT.md
Task: configs         → Read experiments/CONTEXT.md
Task: spec/compiler   → Read code_reviews/2026-08-14_experiment-spec-and-compiler-design.md
```
