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

```
supervisor.py ── Redis flag/session↔cell mapping contracts (no OpenCode client dep — observe only, see docs/supervisor_design.md)
workflow_runner.py ── executes an agent_task workflow's phases inside a git worktree, committing + ledgering each
test_runner.py ── independent pytest/jest/go-test/cargo-test runner; sole source of truth for test_executed_success
```

## The spec/compiler layer — WRITTEN

Two modules, per the design doc: `experiment_spec.py` (dataclasses, YAML loader,
requires/produces validator, tests) and `compile_experiment.py` (spec → DAG). Both are
**written**.

```
experiment_spec.py     — WRITTEN — dataclasses + YAML loader + requires/produces validator
compile_experiment.py  — WRITTEN — spec → DAG; generalizes _gen_matrix_cells + routing.simulate_strategies
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
authoring the arms that consume them.** Those fields are now MEASURED (instrumentation
step 3 done) — see the ledger below. The `answer`/`explanation` split unlocks the
Explanation Tax decomposition.

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

### Spec/compiler signatures (written — src/instrument/{experiment_spec,compile_experiment}.py)

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

### Runtime RAG / Knowledge Base (v1.0 — merged; default OFF)

```
# knowledge.py — canonical identity + authority contract (two sha256 ids, ordered Authority)
Authority, KnowledgeRecord, KnowledgeEvent
compute_entity_id(), compute_knowledge_id(), compute_content_hash()

# retrieval.py — deterministic retrieval (dense Chroma + lexical Neo4j full-text → RRF fusion)
QueryPlan, Candidate, RetrievalAttempt, FallbackMode
build_query_plan(), retrieve(), select_evidence(), build_evidence_cards()
  # Candidate.repository_id + scope_excluded(): HARD per-cell scope pre-filter (default self-<worktree>)

# prompt_constructor.py — typed prompt-constructor (one flash-model call + validator)
PromptConstructor, ModelPromptConstructor, PromptPlan, AugmentedPrompt, render_prompt()

# knowledge_stream.py — durable Redis Streams ingestion (DB 2 on 6380)
connect(), publish_event(), process_entry(), reconcile_missing()
  CONSUMER_GROUPS: kb-chroma-v1 | kb-neo4j-v1 | kb-ledger-v1
  # WRITE GUARD: publish_event raises RuntimeError unless FINOPS_KB_WRITE=1 or authorized=True

# knowledge_ingestion.py — producer-side measured-finding derivation (richer extractor)
EXTRACTOR_VERSION = "measured-finding/v1"
derive_records(entries, *, repository_id=REPOSITORY_ID) -> list[KnowledgeRecord]
build_record(entry, *, repository_id=REPOSITORY_ID, now=None) -> KnowledgeRecord
record_to_artifact(record) -> bytes          # durable per-record JSON (stable content; ids+timestamps blanked)
record_to_event(record, *, now=None) -> KnowledgeEvent
  # POINTER contract: source_uri = file://experiments/results/kb/<knowledge_id>.json,
  #   content_hash = sha256(record_to_artifact(record)); event_id = knowledge_id (tracing, not the key)
extract_record(event, artifact_bytes) -> KnowledgeRecord
  # measured-result extractor — supersedes default_extract; wired in kb_worker.py
PHASE_EXTRACTOR_VERSION = "phase-finding/v1"
derive_phase_record(phase_result, *, goal, repository_id, revision, now=None) -> KnowledgeRecord
emit_phase_finding(phase_result, *, goal, repository_id, revision, now=None) -> KnowledgeRecord
  # self-build (progressive) producer: scoped to repository_id (never global); authority MEASURED
  #   when test_executed_success is a bool, else ADVISORY; idempotent key f(goal, phase, commit, scope, extractor)

# code_ingestion.py — producer-side code-structure derivation (source_type=code)
EXTRACTOR_VERSION = "code/v1"
derive_code_records(profile, *, repository_id, revision, repo_root, now=None) -> list[KnowledgeRecord]
build_code_record(symbol, file_path, language, *, repository_id, revision, now=None) -> KnowledgeRecord
ingest_codebase_graph(client, repo_root, *, worktree_name, profile=None) -> dict
  # one record per function/class; authority=SOURCE, evidence_class="[C]"; wires graph.load_codebase_graph

# quality_ingestion.py — producer-side code-quality derivation (source_type=report)
EXTRACTOR_VERSION = "quality/v1"
derive_quality_records(codebase_path, *, profile, repository_id, revision, now=None, notes=None) -> list[KnowledgeRecord]
build_quality_record(*, signal, logical_locator, language, text, authority, evidence_class, ...) -> KnowledgeRecord
  # SonarQube/LSP -> MEASURED "[M]"; entropy -> DERIVED "[C]"; absent tool -> skipped (noted, never fabricated)

# policy_ingestion.py — producer-side policy ingestion (source_type=policy)
EXTRACTOR_VERSION = "policy/v1"
derive_policy_records(policy_paths, *, repository_id, revision, repo_root=None, now=None) -> list[KnowledgeRecord]
build_policy_record(locator, text, *, repository_id, revision, now=None) -> KnowledgeRecord
discover_policy_paths(repo_root) -> list[Path]
  # authority=POLICY (top tier), evidence_class="[P]"; discoverability/citation only — never RRF candidates

# workflow_runner.py — the rag_augment seam (default OFF)
cell_scope(workdir) -> str   # f"self-{workdir.name}"; FINOPS_CELL_ID overrides — the cell's KB scope
run_workflow(spec, *, goal, model, workdir, ..., rag_augment=None, retrieve_fn=None,
             construct_fn=None, rag_params=None) -> WorkflowRunResult
  # rag_params.emit_self (opt-in, default OFF): after a phase commits, emit its finding into
  #   the cell's OWN scope via emit_phase_finding (best-effort — never blocks the phase)

# one agent phase (only when rag_augment enabled):
route_step ──▶ retrieve ──▶ construct ──▶ render ──▶ run_agent

# producer data flow (batch ingestion): any of four sources ──▶ derive_*_records ──▶
#   record_to_artifact (write kb/<id>.json) ──▶ record_to_event ──▶ publish_event ──▶
#   stream ──▶ process_entry (read → verify sha256(artifact) → extract_record → upsert)
# four record types, over the authority ordering (POLICY > SOURCE > MEASURED > DERIVED > ADVISORY):
#   finding → MEASURED [M] | code → SOURCE [C] | report → MEASURED [M] (Sonar/LSP) or DERIVED [C] (entropy) | policy → POLICY [P]

# two-channel rule (do not conflate the two Redis planes):
#   knowledge = per-cell repository_id scope (default self-<worktree>); an explicit non-empty
#               repository_id is the SHARED-scope override (parallel workstreams). Empty never
#               means "global". retrieve→construct→render references publish_event ZERO times —
#               the ONLY KB writer is the opt-in emit_self path.
#   control/telemetry = live.LivePublisher (pub/sub, DB 1) — UNscoped, observe-only, never writes KB.
```

### Ledger (the data model rules consume) — schema WRITTEN; the four formerly-missing fields are now MEASURED

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
              confidence: float | None            # MEASURED [H] — AgenticResult.confidence
              perturbation_strength: float | None # MEASURED — StoryResult / run.py
              test_executed_success: bool | None  # MEASURED — test_runner.run_suite
              cost{inference, orchestration}, rework_cost, reuse_value
```

## Script map

78 scripts across 5 categories (experiment runners, post-hoc analysis, data pipeline,
19 active lab_*.py + 8 deprecated *_bge_m3, Redis queue/review workers). Full table:
`scripts/CONTEXT.md` (the authoritative, per-script reference — keep this pointer,
don't re-duplicate the table here).

Primary entry points: run.py, run_story.py, run_workflow.py, pipeline.py,
inventory.py, build_data.py, sync_data.py, analyze_worktrees.py,
analyze_trajectories.py, validate_session.py, enqueue.py + worker.py,
review_all.py (+ review_stories.py/review_worker.py/trigger_reviews.py/
enqueue_reviews.py/finalize_reviews.py), monitor.py, generate_manifest.py.

admin/server.py — Control Room portal: SSE telemetry, routing, supervisor flags,
design sessions, Claude background sessions (port 8000, FINOPS_PORT). Full route
list: scripts/CONTEXT.md.
.opencode/tools/dashboard.ts — pull tool: Redis status matrix via monitor.py --json

## Test files

39 files total (`ls tests/test_*.py | wc -l` — verify current count), by module family:

```
Core pipeline (27): test_pipeline.py, test_story.py, test_opencode_events.py,
test_mutation.py, test_embeddings.py, test_commit_analysis.py, test_lsp.py,
test_claude_adapter.py, test_trajectory_embedding.py, test_review_agent.py,
test_pricing.py, test_correctness_lineage.py, test_language.py,
test_opencode_analyzer.py, test_graph.py, test_entropy.py, test_codebase_graph.py,
test_ollama_analyzer.py, test_live.py, test_perturb.py, test_data_integrity.py,
test_routing.py, test_strategy.py, test_recovery.py, test_adapter.py,
test_streaming.py, test_backends.py

Admin/supervisor (6): test_admin_claude_agents.py, test_admin_claude_agents_frontend.py,
test_admin_design_sessions.py, test_admin_frontend.py, test_admin_server.py,
test_admin_supervisor.py

Claude-agents (2): test_claude_agents_client.py, test_claude_agents_supervisor.py

Spec/compiler + workflow (4): test_compile_experiment.py, test_experiment_spec.py,
test_workflow_runner.py, test_supervise.py
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
