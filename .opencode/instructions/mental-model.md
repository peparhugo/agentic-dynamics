# File map, signatures, and dependencies. No theory. No methodology.

This repo is an **information-acquisition machine for AI economics**: controlled
trials (cells) → raw events → information (measurement rules) → policies (control
rules) → policy arms → grid → campaign → repeat. Everything below is one stage in
that chain. Design of the spec/compiler: `docs/designs/current/2026-08-14_experiment-spec-and-compiler-design.md`.

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
compiler will generalize (see reuse map below). Module names are plane-qualified below
(`measurement.perturb` = `src/agentic_dynamics/measurement/perturb.py`, etc.):

```
measurement.perturb.perturb_prompt → adapters.backends / adapters.opencode / adapters.claude_adapter
  → [LLM] → AgenticResult (trajectory captured in session.jsonl, parsed by scripts/analyze_trajectories.py)
      → measurement.solution + measurement.basin + measurement.efficiency
        + measurement.recovery_cost + measurement.strategy → reporting.game_report

runtime.story ── measurement.mutation, measurement.commit_analysis, reporting.review,
                 measurement.entropy, measurement.codebase_graph, measurement.lsp_diagnostics
control.routing ── recommend model per task type from experiment results
control.live ──── Redis pub/sub telemetry (feeds the Control Room portal)
```

```
control.supervisor ── Redis flag/session↔cell mapping contracts (no OpenCode client dep — observe only, see docs/designs/current/supervisor_design.md)
runtime.workflow_runner ── executes an agent_task workflow's phases inside a git worktree, committing + ledgering each
runtime.test_runner ── independent pytest/jest/go-test/cargo-test runner; sole source of truth for test_executed_success
```

## The game board and the permanence gate (L0 — see `docs/designs/proposed/system_knowledge_abstraction.md`)

The system shapes the agent and the agent reshapes the system: every boundary changes the
derived surfaces (agent files, mental model, tools, skills, mds), and the machine re-renders
them itself. **`agentic-dynamics surfaces sync`** regenerates every derived surface from its
sources (game board → agent surfaces → spec lifecycle → data chain; `--full` forces the data
chain, `--verify` appends the guard suite). **`agentic-dynamics surfaces snapshot`** writes
`agent_config/system_snapshot.md` — the **game board (L0)**: main HEAD + the last 12 commits of
chronological history, spec lifecycle counts, registry + corpus counts, live machine state
(Redis/queue/pipeline), campaigns in flight, and the worktrees awaiting the permanence
decision. The snapshot is rendered into both agent surfaces (`.opencode/instructions/` +
`.claude/rules/`) and read by every actor: workers for orientation, the supervisor as its
assessment baseline (on-task/safety/budget/loops — `scripts/supervise.py`'s `MONITOR_ROLE`),
the controller instead of chat triage.

**The permanence gate.** Worktree branches (`feature/*`, `wt_*`) are EPHEMERAL proposals; the
chronological history of the system is `main` plus the merges the controller signs. The
machine proposes (campaign phases, workflow commits, merge-ready branches); the controller
decides what becomes permanent. The snapshot's "awaiting permanence" section is the board for
that decision. The contract layer (frontmatter/status/markers) is the state; the formatter is
the render — derivation runs contract → render, never backwards (guards verify both
directions).

## Package planes (Stage 1 — the modular monorepo)

The former flat `instrument` package is re-homed as `src/agentic_dynamics/` with eight
bounded planes (`ARCHITECTURE.md` §1; the dependency direction is enforced by
`tests/test_dependency_direction.py`):

| Plane | Ownership |
|---|---|
| `core` | foundation — language, paths, session vocabulary, streaming, constants |
| `experiment` | the platform — `ExperimentSpec`, the `requires`/`produces` gate, spec→DAG, spec-lifecycle index |
| `measurement` | the measurement apparatus — perturb/mutation/solution/basin/efficiency/… + static analysis |
| `runtime` | execution runtime — workflow_runner, test_runner, story, posthoc |
| `adapters` | model backends — opencode, claude_adapter, backends |
| `knowledge` | knowledge + augmentation — identity/authority, retrieval, prompt-construction, ingestion producers |
| `control` | the implemented control plane — fact plane (`facts` + `fact_ingestion` + `reducers/`), context compiler, shadow-mode controller/validator, routing, supervisor, telemetry, queue steering, observation/actuation |
| `reporting` | research output — game_report, review, analyzers |

Tier map: `core` (0) ← `experiment/measurement/runtime/adapters/knowledge/reporting` (1) ←
`control` (2) ← `apps` (3). The only tier-1→tier-2 edges are the pinned adapter telemetry seam
(`adapters.opencode`/`claude_adapter → control.live`); `runtime.workflow_runner` is
dependency-inverted (Debt-2) — it consumes the runtime-owned `Router`/`TelemetryPublisher`
protocols (`runtime/routing.py`/`runtime/telemetry.py`) with the control implementations
(`control.step_routing.route_step`, `control.live.LivePublisher`) injected at the composition
root (`scripts/run_workflow.py`), so runtime never imports control.

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

### Spec/compiler signatures (written — agentic_dynamics/experiment/{experiment_spec,compile_experiment}.py)

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
  # lineage + version fields on KnowledgeRecord (and KnowledgeEvent):
  #   supersedes: str|None — predecessor knowledge_id for the SAME entity_id (version chain link)
  #   causes:     str|None — observation-family knowledge_id that justified an actuation (cross-entity)
  #   operation:  upsert | supersede | delete  (delete = tombstone; requires a non-empty `reason`)
  # observation-vs-actuation split (no third envelope; source_type + operation are the only discriminators):
  #   OBSERVATION_TYPES / ACTUATION_TYPES, message_family(source_type) -> "observation"|"actuation"
  #   ACTUATION_TYPES = {"actuation"} is a closed-by-default allowlist; unknown types -> "observation"

# retrieval.py — deterministic retrieval (dense Chroma + lexical Neo4j full-text → RRF fusion)
QueryPlan, Candidate, RetrievalAttempt, FallbackMode
build_query_plan(), retrieve(), select_evidence(), build_evidence_cards()
  # Candidate.repository_id + scope_excluded(): HARD per-cell scope pre-filter (default self-<worktree>)

# prompt_constructor.py — typed prompt-constructor (one flash-model call + validator)
PromptConstructor, ModelPromptConstructor, PromptPlan, AugmentedPrompt, render_prompt()

# knowledge_stream.py — durable Redis Streams ingestion (DB 2 on 6380)
connect(), publish_event(), process_entry(), reconcile_missing()
  CONSUMER_GROUPS: kb-chroma-v1 | kb-neo4j-v1 | kb-ledger-v1 | kb-registry-v1
  # WRITE GUARD: publish_event raises RuntimeError unless FINOPS_KB_WRITE=1 or authorized=True
  # three orthogonal gates keyed off message_family(source_type): write guard (all) ->
  #   actuation-armed (actuation: FINOPS_ACTUATION_ARMED=1 or armed=True) ->
  #   lineage (actuation: event.causes must resolve to an observation via SOURCE_TYPE_INDEX_KEY)

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

# story_ingestion.py — canonical-state producer (source_type=story)
EXTRACTOR_VERSION = "story/v1"
derive_story_records(story_result, *, repository_id, revision, now=None) -> list[KnowledgeRecord]
build_story_record(story_result, *, repository_id, revision, now=None) -> KnowledgeRecord
derive_story_records_from_run_output(run_output, *, repository_id, now=None) -> list[KnowledgeRecord]
  # authority=MEASURED "[M]"; write-time registration call site in story.save_story_result / scripts/run.py

# review_ingestion.py — canonical-state producer (source_type=review)
EXTRACTOR_VERSION = "review/v1"
derive_review_records(review, *, repository_id, revision, now=None) -> list[KnowledgeRecord]
build_review_record(review, *, repository_id, revision, now=None) -> KnowledgeRecord
  # authority=ADVISORY "[H]"; write-time call site in scripts/finalize_reviews.py

# ledger_ingestion.py — canonical-state producer (ledger_job / ledger_attempt / meta_session)
EXTRACTOR_VERSION = "ledger/v1"
derive_ledger_records(summary_entry, *, repository_id, revision, now=None) -> list[KnowledgeRecord]
build_job_record(...) / build_attempt_record(...) / classify_session(title) -> source_type
  # ledger_job/ledger_attempt -> MEASURED "[M]"; meta_session -> ADVISORY (closes gaps a+b)

# observation_ingestion.py — canonical-state producer (source_type=observation / flag)
EXTRACTOR_VERSION = "observation/v1"
derive_observation_record(...) / build_observation_record(...) -> KnowledgeRecord
derive_flag_record(...) / build_flag_record(...) -> KnowledgeRecord
  # authority=ADVISORY "[H]"; every supervisor verdict registrable (closes OQ6a)

# actuation_ingestion.py — canonical-state producer, Delta 3 (source_type=actuation)
EXTRACTOR_VERSION = "actuation/v1"
derive_actuation_record(..., *, causes, repository_id, now=None) -> KnowledgeRecord
  # authority=POLICY "[P]"; causes-linked to an observation; ZERO call sites (nothing fires it yet)

# augment.py — the retrieve->construct->render seam (R7; split out of workflow_runner, default OFF)
augment_prompt(*, base_prompt, goal, phase_def, model, commit_sha, inherited_tools,
               pinned_policy, rag_params, retrieve_fn, construct_fn) -> AugmentationOutcome
default_retrieve_fn() -> Callable    # dense ChromaStore + graph Neo4jClient -> functools.partial(retrieve)
default_construct_fn(rag_params, run_agent) -> Callable  # ModelPromptConstructor on DEFAULT_CONSTRUCTOR_MODEL
  # pure w.r.t. the worktree; any failure -> base_prompt + named fallback_mode; NEVER blocks the phase

# workflow_runner.py — phase execution + the opt-in self-build emit (default OFF)
cell_scope(workdir) -> str   # f"self-{workdir.name}"; FINOPS_CELL_ID overrides — the cell's KB scope
run_workflow(spec, *, goal, model, workdir, ..., rag_augment=None, retrieve_fn=None,
             construct_fn=None, rag_params=None) -> WorkflowRunResult
  # rag_params.emit_self (opt-in, default OFF): after a phase commits, emit its finding into
  #   the cell's OWN scope via emit_phase_finding (best-effort — never blocks the phase)

# one agent phase (only when rag_augment enabled):
route_step ──▶ retrieve ──▶ construct ──▶ render ──▶ run_agent

# producer data flow (batch ingestion): any source ──▶ derive_*_records ──▶
#   record_to_artifact (write kb/<id>.json) ──▶ record_to_event ──▶ publish_event ──▶
#   stream ──▶ process_entry (read → verify sha256(artifact) → extract_record → upsert)
# nine source_type values, over the authority ordering (POLICY > SOURCE > MEASURED > DERIVED > ADVISORY):
#   finding → MEASURED [M] | code → SOURCE [C] | report → MEASURED [M] (Sonar/LSP) or DERIVED [C] (entropy)
#   | policy → POLICY [P] | story → MEASURED [M] | review → ADVISORY [H]
#   | ledger_job/ledger_attempt → MEASURED [M] + meta_session → ADVISORY
#   | observation/flag → ADVISORY [H] | actuation → POLICY [P]
# ONE typed stream: source_type + operation are the only discriminators, one pointer envelope,
#   one idempotent knowledge_id key. Write-time registration is now live in four call sites
#   (story.py, run.py, finalize_reviews.py, supervise.py) + the kb_produce* scripts + the opt-in
#   emit_self path — NOT only emit_self anymore (see docs/review/restructure.md §1).

# registry / tombstone / compaction (canonical-state):
#   kb-registry-v1 consumer -> append-only experiments/results/registry_index.jsonl (one line/record)
#   generate_manifest.py compacts it into the manifest `registry` array (latest-per-entity,
#     lifecycle_state current|superseded|tombstoned derived from the supersede/delete chain)
#   scripts/registry.py (show/query/lineage) + Control Room /api/registry* read it back

# two-channel rule (do not conflate the two Redis planes):
#   knowledge = per-cell repository_id scope (default self-<worktree>); an explicit non-empty
#               repository_id is the SHARED-scope override (parallel workstreams). Empty never
#               means "global". retrieve→construct→render references publish_event ZERO times —
#               the write is the opt-in emit_self path (and the batch producers above).
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

Every command script is classified in exactly one bucket of `scripts/CONTEXT.md`'s manifest
(maintained / historical lab books / one-time — machine-parsed by
`tests/test_script_classification.py`, keep the markers intact). The authoritative counts and the
per-script table live in that file, not here.

One entry point: `agentic-dynamics` (Stage 3) — every maintained command maps to a subcommand; the
one-time migrations live under `scripts/archive/`.

Primary maintained commands: run.py, run_story.py, run_workflow.py, pipeline.py,
inventory.py, build_data.py, sync_data.py, analyze_worktrees.py, analyze_trajectories.py,
validate_session.py, enqueue.py + worker.py, review_all.py (+ review_stories.py/
trigger_reviews.py/enqueue_reviews.py/finalize_reviews.py), monitor.py, generate_manifest.py.

apps/control_room/server.py — Control Room portal: SSE telemetry, routing, supervisor flags,
design sessions, Claude background sessions (port 8000, FINOPS_PORT). Full route
list: scripts/CONTEXT.md.
.opencode/tools/dashboard.ts — pull tool: Redis status matrix via monitor.py --json

## Test files

Tests live under `tests/test_*.py`, one per module family (the authoritative list is the `tests/`
directory itself). Notable guard families: the consolidation guards (`test_dependency_direction.py`,
`test_data_flow.py`, `test_doc_lifecycle.py`, `test_script_classification.py`,
`test_experiment_workflow_classification.py`, `test_kb_produce_registry.py`), the
spec/compiler + workflow tests (`test_compile_experiment.py`, `test_experiment_spec.py`,
`test_workflow_runner.py`, `test_supervise.py`), and the admin/supervisor + claude-agents suites.

## CLI surface (Stage 3 — one entry point)

`agentic-dynamics` (a thin dispatcher over the maintained `scripts/`, `agentic_dynamics/cli.py`) —
each subcommand forwards argv to its backing script; the CLI composes, never re-implements.

```
agentic-dynamics
├─ experiment run|sweep-parallel|sweep-silent|batch|remaining|multi-phase
├─ story       run|batch
├─ workflow    run|discard-tree
├─ queue       enqueue|worker|monitor|reinterleave|analysis-enqueue|analysis-worker
├─ analyze     worktrees|trajectories|stories|lab <name>
├─ data        build|sync|manifest|inventory
├─ knowledge   ingest|sources|worker
├─ registry    query|show|lineage
├─ review      all|stories|trigger|enqueue|finalize
├─ spec        status|pipeline
├─ validate    session|tests
└─ supervise   [claude-agents|orphans]
```

## Navigation

```
Task: instrument logic → Read the agentic_dynamics/ plane __init__ docstrings (the module map)
Task: experiments     → Load skill: instrument
Task: analysis        → Load skill: analyze
Task: lab books       → Load skill: lab-books
Task: pipeline        → Read scripts/CONTEXT.md
Task: website         → Read apps/website/CONTEXT.md
Task: configs         → Read experiments/CONTEXT.md
Task: spec/compiler   → Read docs/designs/current/2026-08-14_experiment-spec-and-compiler-design.md
```
