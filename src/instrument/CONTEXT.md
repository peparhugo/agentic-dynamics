# `src/instrument/` — Measurement Apparatus

40 Python modules (+ `__init__.py`) that form the core library. Measures search dynamics (not
outputs): basin escape rates, recovery cost, attractor strength, strategy classification.
Pip-installable as `ai-finops-dynamics`.

Two modules form the spec/compiler layer (see `code_reviews/2026-08-14_experiment-spec-and-compiler-design.md`). `experiment_spec.py` and `compile_experiment.py` are both **written**. Together they turn the library from a linear pipeline into a cycle: `spec → DAG → cells → jobs → attempts → information → policy → grid → campaign`.

## Architecture

```
        ┌──────────────────── the cycle (information acquisition) ────────────────────┐
        │                                                                              │
        ▼                                                                              │
  spec (ExperimentSpec) ──compile──▶ DAG ──▶ cells ──▶ jobs ──▶ attempts ──▶ ledger    │
        ▲                                       │                                │     │
        └──── adapt (tweak one factor) ── compare ◀── information ◀── measure ◀───┘     │
        └───────────────────────────────────────────────────────────────────────────────┘
```

Today's code is the linear core (which the compiler will generalize):

```
Prompt ──→ perturb.py ──→ backends.py ──→ [LLM] ──→ trajectory.py
                                                      │
                    ┌─────────────────────────────────┘
                    ▼
              solution.py ─── correctness
              basin.py ────── structural divergence
              efficiency.py ─ cost (tokens/$/joules)
              recovery.py ─── exploration vs recovery tokens
                    │
                    ▼
              strategy.py ─── archetype classification
                    │
                    ▼
              game_report.py ── Markdown artifact
```

## Module Reference

### Core Pipeline

| Module | Lines | Purpose | Key Exports |
|--------|-------|---------|-------------|
| `perturb.py` | 752 | 10 perturbation operators (4 spec + 4 process + 2 objective) | `Perturbation`, `PerturbationOperator`, `build_operators()`, `perturb_prompt()`, `PERTURBATION_CLASSES`, `perturbation_class_for()` |
| `adapter.py` | 149 | [deprecated] Wraps LLM calls to capture trajectory steps | `InstrumentedAdapter` |
| `opencode.py` | 614 | Spawns real opencode sessions (think/write/test loop) | `run_opencode_agentic()` |
| `experiment.py` | 309 | [deprecated] Orchestrates full experiment: perturb → invoke → evaluate | `ExperimentConfig`, `run_experiment()` |
| `language.py` | 295 | Multi-language codebase analysis via tree-sitter — unified parsing API across Python/TypeScript/Go/Rust; foundation module, no internal deps | `LanguageProfile`, `detect_language()`, `get_parser()`, `CodebaseAST`, `parse_codebase()`, `collect_imports()`, `collect_functions()` |

### Story / Multi-Session (v0.6–v0.9)

| Module | Lines | Purpose | Key Exports |
|--------|-------|---------|-------------|
| `story.py` | 1374 | Multi-session story orchestrator — N sequential coding sessions, each building on the prior session's git commit | `PerturbationCondition`, `condition_to_mutations()`, `StoryConfig`, `StoryResult`, `run_story()`, `save_story_result()`, `BUILTIN_STORIES` |
| `mutation.py` | 438 | Flash V4 mutation compiler — semantic perturbation of specs and code, pinned as a hashable artifact per cell | `MutationArtifact`, `compile_mutation()`, `apply_mutation()` |
| `commit_analysis.py` | 841 | Per-commit analysis: AST diff, SonarQube delta, convention scoring | `ConventionRules`, `CommitAnalysis`, `StoryAnalysis`, `compute_ast_diff()`, `score_conventions()`, `compute_sonar_delta()` |
| `review.py` | 809 | LLM code review pool — commit reviewer, story reviewer, cross-model comparator, held-out test generator | `CommitReview`, `StoryReview`, `review_commit()`, `review_story()`, `generate_tests()`, `compare_implementations()` |
| `entropy.py` | 363 | Architectural entropy — information-theoretic disorder across function length, module size, import graph, naming, file-responsibility mapping | `EntropyProfile`, `compute_entropy()`, `entropy_delta()`, `entropy_delta_detailed()` |
| `codebase_graph.py` | 356 | Import-graph structural metrics — modularity, coupling, centrality, connected components; Neo4j or in-memory networkx | `CodebaseGraph`, `GraphMetrics`, `build_graph()`, `compute_metrics()`, `GraphDelta` |
| `lsp_diagnostics.py` | 401 | Language-server diagnostics (pyright, tsc, golangci-lint, rust-analyzer), graceful fallback when tools are missing | `LSPReport`, `LSPToolConfig`, `run_diagnostics()`, `diagnostics_delta()`, `available_tools()` |

### Measurement Modules

| Module | Lines | Purpose | Key Exports |
|--------|-------|---------|-------------|
| `trajectory.py` | 270 | Captures step-level reasoning trace (thought/action/tool/tokens) | `TrajectoryStep`, `ReasoningTrajectory` |
| `solution.py` | 266 | 4-dimension evaluation (correctness, constraints, quality, novelty) | `SolutionMetrics` |
| `basin.py` | 322 | Structural divergence from baseline (not text similarity) | `BasinMetrics` |
| `efficiency.py` | 433 | Token breakdown, dollar cost, joule estimate per model architecture | `EfficiencyMetrics`, `compute_efficiency()` |
| `recovery.py` | 277 | Classifies tokens as EXPLORATION / RECOVERY / STABLE | `SegmentClassification`, `classify_trajectory_segments()` |
| `recovery_cost.py` | 171 | Economic cost of constraint recovery ($ per removed constraint) | `RecoveryCost`, `compute_recovery_cost()` |
| `strategy.py` | 197 | 4 archetypes: CONSERVATIVE, EXPLORATORY, EXPLOITATIVE, FLAILING | `StrategyType`, `StrategyReport`, `classify_strategy()` |

### Validation Modules

| Module | Lines | Purpose | Key Exports |
|--------|-------|---------|-------------|
| `constraint_detection.py` | 268 | Detects whether model notices removed constraints | `ConstraintDetection` |
| `semantic_validation.py` | 300 | 3 signals: pragmatic markers, AST edit distance, tool-call latency | `MarkerProfile`, `ASTProfile`, `EscapeProfile`, `analyze_markers()`, `analyze_ast()`, `analyze_escape()` |

### Analysis / Graph

| Module | Lines | Purpose | Key Exports |
|--------|-------|---------|-------------|
| `embeddings.py` | 288 | Text embedding + vector search via Ollama (bge-m3) + ChromaDB; `ChromaStore` gains `collection_name` isolation, env-driven `CHROMA_HOST`/`CHROMA_PORT`, canonical upsert/delete/inventory, and `step_doc_id()` (the dense↔graph join key) | `EmbeddingClient`, `ChromaStore`, `ChromaStoreError`, `step_doc_id()`, `extract_session_text()`, `extract_session_steps()` |
| `graph.py` | 524 | Neo4j knowledge graph — experiment ontology loaders + knowledge-base capabilities: `create_knowledge_schema()`, full-text/exact search, bounded `expand_candidates()`, `load_codebase_graph()`, and the `Step.doc_id`/`Step.text` join repair | `Neo4jClient`, `ALLOWED_EXPANSION_RELS` |
| `ollama_analyzer.py` | 173 | Qualitative experiment analysis via DeepSeek R1 on Ollama — narrative commentary over game report metrics + session data | `OllamaAnalyzer`, `load_summary_data()` |
| `opencode_analyzer.py` | 245 | Qualitative experiment analysis via real opencode sessions with DeepSeek — a meta-experiment, measured by the same instrument | `OpencodeAnalyzer` |
| `sonar.py` | 401 | SonarQube static analysis for LLM-generated code — bugs, vulnerabilities, code smells, cognitive complexity, duplications, maintainability, plus differential quality analysis | `SonarMetrics`, `compute_sonar_diff()`, `run_sonar_analysis()`, `sonar_quality_score()` |

### Control Room / Workflow

| Module | Lines | Purpose | Key Exports |
|--------|-------|---------|-------------|
| `supervisor.py` | 171 | Shared Redis contracts for human-reviewed supervisor flags — observation metadata only; deliberately no OpenCode client dependency, so observation can't become control | `canonical_json()`, `normalize_flag()`, `parse_mapping()`, `register_session_mapping()`, `register_event_mapping()` |
| `workflow_runner.py` | 706 | Executes an `agent_task` workflow's phases inside a git worktree, committing + ledgering (tokens, cost, `test_executed_success`) after each phase; the `execute` phase of the spec/compiler DAG; hosts the off-by-default RAG augmentation seam | `PhaseResult`, `WorkflowRunResult`, `AugmentationOutcome`, `run_workflow()` |
| `test_runner.py` | 140 | Independent pytest/jest/go-test/cargo-test runner, keyed off `language.py`; sole source of truth for `test_executed_success` — never taken from the model's self-reported pass/fail | `resolve_node()`, `run_suite()`, `suite_succeeded()` |

### Backend, Telemetry & Routing

| Module | Lines | Purpose | Key Exports |
|--------|-------|---------|-------------|
| `streaming.py` | 123 | Shared line-by-line subprocess runner (live telemetry, timeout-safe) | `stream_subprocess()`, `StreamResult` |
| `claude_adapter.py` | 346 | Drives the Claude CLI (`stream-json`) and translates to opencode events | `run_claude_agentic()`, `ClaudeStreamAdapter`, `adapt_usage()` |
| `backends.py` | 56 | Routes `anthropic/*` → Claude CLI, else opencode | `run_agentic()`, `get_backend_for_model()` |
| `live.py` | 101 | Redis Pub/Sub telemetry (status + per-cell event stream + replay log) | `LivePublisher`, `make_publisher()` |
| `routing.py` | 187 | Task-optimal routing: per-task model recommendation + strategy simulation | `compute_routing()`, `recommend_route()`, `simulate_strategies()` |
| `signal_store.py` | — | Per-step routing signal store (field/id mismatches, portal validation wiring) | — |
| `step_routing.py` | — | Per-step model routing across workflow phases | — |

### Output

| Module | Lines | Purpose |
|--------|-------|---------|
| `game_report.py` | 319 | Combines all metrics into a single Markdown report per experiment |
| `lab_book.py` | 82 | [deprecated] YAML-frontmatter persistence for experiment results |

### Runtime RAG / Knowledge Base (v1.0)

The runtime-RAG stack (design: `code_reviews/2026-08-15_rag-knowledge-base-proposal-review.md`) adds a
knowledge identity + authority contract, a deterministic retrieval pipeline, and a typed
prompt-constructor, wired into `run_workflow()` as an **off-by-default** augmentation seam
(`spec.workflow.params.rag_augment`). Data flow for one agent phase:

```
raw work item ── route_step ──▶ retrieve ──▶ construct ──▶ render ──▶ run_agent
   (base prompt)                 (deterministic,   (one flash-      (typed
                                  dense+lexical      model call +     plan →
                                  RRF fusion)        validator)      prompt)
```

| Module | Lines | Purpose | Key Exports |
|--------|-------|---------|-------------|
| `knowledge.py` | 288 | Canonical identity + authority contract — two sha256 ids (`entity_id`, `knowledge_id`), ordered `Authority` (POLICY > SOURCE > MEASURED > DERIVED > ADVISORY), frozen `KnowledgeRecord`/`KnowledgeEvent` (pointer-only) | `Authority`, `KnowledgeRecord`, `KnowledgeEvent`, `compute_entity_id()`, `compute_knowledge_id()`, `compute_content_hash()` |
| `retrieval.py` | 907 | Deterministic retrieval — regex query planner, parallel dense (Chroma) + lexical (Neo4j full-text) legs, RRF fusion × authority/freshness/exact-id/conflict, bounded decayed graph expansion, token-budgeted whole-chunk selection, `RetrievalAttempt`, offline `build_evidence_cards()` | `QueryPlan`, `Candidate`, `RetrievalAttempt`, `build_query_plan()`, `retrieve()`, `rrf_base()`, `compute_fused_score()`, `graph_boost()`, `select_evidence()`, `build_evidence_cards()`, `FallbackMode` |
| `prompt_constructor.py` | 456 | Typed prompt-constructor — `PromptConstructor` protocol, `prompt-plan/v1` schema, deterministic validator, one-repair + deterministic fallback renderer, no-fork cache keying, default `deepseek/deepseek-v4-flash` | `PromptConstructor`, `ModelPromptConstructor`, `ConstructionRequest`, `AugmentedPrompt`, `PromptPlan`, `validate_plan()`, `render_prompt()`, `construction_cache_key()`, `hash_work_item()` |

`workflow_runner.py` is the seam: between `route_step()` and `run_agent()` it calls
`retrieve → construct → render` (gated by `spec.workflow.params.rag_augment`, default OFF) and
persists augmentation provenance on `PhaseResult` (`raw_prompt_hash`, `pre_phase_commit`,
`retrieval_attempt_id`, `constructor_attempt_id`, `selected_evidence_ids`, `augmentation_versions`,
`augmentation_tokens`, `augmentation_cost_usd`, `augmentation_latency_ms`, `fallback_mode`). Any
retrieval/constructor failure falls back to the base prompt and records a named fallback mode.

### The spec/compiler layer

| Module | Status | Purpose | Key Exports |
|--------|--------|---------|-------------|
| `experiment_spec.py` | **written** | Spec dataclasses + YAML loader + requires/produces validator | `ExperimentSpec`, `Workflow`, `Factor`, `RuleSpec`, `MetricSpec`, `ComparisonSpec`, `WriteupSpec`, `StopSpec`, `AdaptSpec`, `LEDGER_FIELDS`, `load_spec`, `validate_rules`, `validate_spec` |
| `compile_experiment.py` | **written** | spec → DAG; generalizes `_gen_matrix_cells` + `simulate_strategies` | `compile_spec()`, `validate_rules()`, `RuleResult` |

### The rule/ledger interface (schema written; UNMEASURED fields below are the open instrumentation gap)

```
RuleSpec(name, plane, evidence_class, requires, produces)
  plane: "measurement" (produces information) | "control" (consumes it)
  evidence_class: [M] [C] [H] [P]
RuleResult(rule, metric, evidence_class, uncertainty, produces)
first_pass_quality(attempts) -> RuleResult   # measurement (produces)
grit(attempts) -> RuleResult                 # measurement — gated until strength+success exist
model_cascade(attempts, state) -> RuleResult # control (consumes confidence)

JobRecord:    factors{model,condition,policy,seed}, policy_arm, policy_id, budget,
              due_at, forecast_cost, forecast_latency, status
AttemptRecord: attempt_number, retry_reason, escalation_from/to, model,
              queued/leased/started/first_token/ended timestamps,
              tokens{in,out,reasoning,answer,explanation}, cache_hit, tool_calls,
              completed, first_pass, accepted, evaluator_independent,
              confidence: float | None            # ← UNMEASURED; model_cascade needs it
              perturbation_strength: float | None # ← UNMEASURED; grit needs it (the s axis)
              test_executed_success: bool | None  # ← UNMEASURED; grit needs it (verified success)
              cost{inference, orchestration}, rework_cost, reuse_value
```

The `confidence` field is the concrete gap for policy: it is what the `model_cascade`/`dynamics`
arms require and the ledger does not emit yet. `perturbation_strength` + `test_executed_success`
are the gap for `grit` — its operational definition (basin.py) is a retention curve over
strength conditioned on verified success, not a "completed/n" proxy. Instrument all of them
(plus the `answer`/`explanation` token split and attempt/timestamp fields) before authoring the
arms that consume them.

## Which Scripts Consume Which Modules

| Script | Modules Used |
|--------|-------------|
| `scripts/run.py` | backends (run_agentic), opencode, claude_adapter, perturb, all measurement modules |
| `scripts/worker.py` | live (LivePublisher) — publishes status + sets FINOPS_CELL_ID |
| `scripts/analyze_worktrees.py` | solution, basin, efficiency, strategy, game_report, opencode_analyzer |
| `scripts/analyze_trajectories.py` | trajectory |
| `scripts/validate_session.py` | solution (test pass/fail) |
| `scripts/lab_*.py` (all 19 active) | efficiency, solution, strategy, basin, sonar, embeddings, graph, ollama_analyzer |
| `scripts/build_data.py` | routing (compute_routing), plus JSON output reads |
| `admin/server.py` | live (channel/key constants), routing (compute_routing) |

Note: `experiment.py`, `adapter.py`, and `lab_book.py` are deprecated (Phase 1B added deprecation
warnings). Use `opencode.py` / `run_opencode_agentic()` for running experiments.

## Key Design Decisions

- **Search dynamics, not output quality.** The instrument doesn't judge code — it measures how the model searches for solutions and what that search costs.
- **Output-based divergence** (basin.py): Architecture/tech-stack/pattern differences, not text similarity.
- **Model-agnostic** (semantic_validation.py): No embeddings needed. Uses linguistic markers + AST analysis.
- **Provenance-tagged** (game_report.py): All metrics tagged [M]easured, [C]omputed, [H]euristic, [P]olicy, or e[X]ternal.
- **Energy estimation** (efficiency.py): DeepSeek uses 37B active MoE params; Claude/others use architecture estimates with GPU TDP constants.
- **Measure before policy** (written — `compile_experiment.py`'s validator): measurement rules produce information; control rules consume it. The validator refuses unwritable control arms.

## Adding a New Perturbation Operator

1. Add the operator function in `perturb.py` (with `strength` parameter)
2. Register it in the `__init__.py` exports
3. Create a config YAML in `experiments/configs/` that uses it
4. Run `python scripts/run.py experiments/configs/your_config.yaml --model deepseek/deepseek-v4-pro`

## Adding a New Metric

1. Create your module in `src/instrument/`
2. Add exports to `src/instrument/__init__.py`
3. Integrate into `game_report.py` (so it appears in generated reports)
4. Update `scripts/analyze_worktrees.py` (so post-hoc analysis includes it)

## Adding a New Language

`language.py` is the single source of truth — all downstream modules key off `LanguageProfile`.
Six touchpoints:

1. **Tree-sitter AST** (`language.py`) — add a `LanguageProfile` to `_PROFILES`
   (name, extensions, `tree_sitter_id`, `test_framework`, `test_file_pattern`), then add the
   grammar's node names to `function_node_types` / `class_node_types` / `import_node_types`.
2. **LSP** (`lsp_diagnostics.py`) — add an `LSPToolConfig` to `_TOOLS` (check_cmd + diag_cmd).
   Add a `_parse_<tool>()` + `_run_tool` branch if output isn't `file:line:col: message`, else
   it falls through to `_parse_generic`.
3. **SonarQube** (`sonar.py`) — no code change. Runs `sonar-scanner` with `sonar.sources=.`;
   SonarQube auto-detects the language. Requires the language analyzer plugin on the server.
4. **Conventions** (`commit_analysis.py` + `conventions/<lang>.yaml`) — create the YAML
   (naming_patterns / forbidden_patterns / scoring). Only `python.yaml` + `typescript.yaml`
   exist; Go/Rust fall back to empty rules. Add a regex branch in `compute_ast_diff` if syntax
   differs from the `+def`/`+function` fallback.
5. **Test framework** — `test_framework` flows to `review.py`; set `standardized.enforce_pytest: false`
   in the config YAML for non-pytest languages (see `go_crawler.yaml`).
6. **Verify** — `tests/test_language.py`, `tests/test_lsp.py`, `tests/test_commit_analysis.py`.

Tree-sitter: `tree_sitter_id` resolves via `tree_sitter_languages.get_parser(id)` (~70 bundled
grammars). For an unbundled grammar, swap in `tree_sitter_language_pack` or register manually.
