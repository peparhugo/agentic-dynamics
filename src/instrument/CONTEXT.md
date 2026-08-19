# `src/instrument/` — Measurement Apparatus

58 Python modules (+ `__init__.py`) that form the core library. Measures search dynamics (not
outputs): basin escape rates, recovery cost, attractor strength, strategy classification.
Pip-installable as `agentic-dynamics`.

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
| `workflow_runner.py` | 587 | Executes an `agent_task` workflow's phases inside a git worktree, committing + ledgering (tokens, cost, `test_executed_success`) after each phase; the `execute` phase of the spec/compiler DAG; phase execution + the opt-in self-build emit (`rag_params.emit_self`), calling out to `augment.py` for the rag-gated augmentation | `PhaseResult`, `WorkflowRunResult`, `cell_scope()`, `run_workflow()` |
| `augment.py` | 265 | The `retrieve -> construct -> render` augmentation seam (R7 — split out of `workflow_runner.py`): `augment_prompt()` plus the default dense+graph store wiring (`default_retrieve_fn()`) and the default constructor wiring (`default_construct_fn()`). Pure w.r.t. the worktree; references `publish_event` zero times | `AugmentationOutcome`, `augment_prompt()`, `default_retrieve_fn()`, `default_construct_fn()`, `DEFAULT_INHERITED_TOOLS` |
| `test_runner.py` | 140 | Independent pytest/jest/go-test/cargo-test runner, keyed off `language.py`; sole source of truth for `test_executed_success` — never taken from the model's self-reported pass/fail | `resolve_node()`, `run_suite()`, `suite_succeeded()` |

### Backend, Telemetry & Routing

| Module | Lines | Purpose | Key Exports |
|--------|-------|---------|-------------|
| `streaming.py` | 123 | Shared line-by-line subprocess runner (live telemetry, timeout-safe) | `stream_subprocess()`, `StreamResult` |
| `claude_adapter.py` | 346 | Drives the Claude CLI (`stream-json`) and translates to opencode events | `run_claude_agentic()`, `ClaudeStreamAdapter`, `adapt_usage()` |
| `backends.py` | 56 | Routes `anthropic/*` → Claude CLI, else opencode | `run_agentic()`, `get_backend_for_model()` |
| `live.py` | 101 | Redis Pub/Sub telemetry (status + per-cell event stream + replay log) — unscoped, observe-only; never writes the KB | `LivePublisher`, `make_publisher()` |
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

The `retrieve()` sub-pipeline, in order: parallel dense (Chroma) + lexical (Neo4j
full-text) legs → RRF fusion × authority/freshness/exact-id/conflict (with the commit
scope applied as a HARD pre-filter on every leg) → `deduplicate` (content-hash) →
`collapse_redundant` (cosine > 0.92 via optional `EmbeddingClient`; the attempt records
which path ran in `dedup_path`) → allowlisted graph expansion (real seed score × weight ×
`0.7**depth`) → `compute_token_budget` + `select_evidence` (whole-chunk, source-capped) →
`RetrievalAttempt`.

| Module | Lines | Purpose | Key Exports |
|--------|-------|---------|-------------|
| `knowledge.py` | 361 | Canonical identity + authority contract — two sha256 ids (`entity_id`, `knowledge_id`), ordered `Authority` (POLICY > SOURCE > MEASURED > DERIVED > ADVISORY), frozen `KnowledgeRecord`/`KnowledgeEvent` (pointer-only), the `source_type`/`operation` discriminator vocabulary (`OBSERVATION_TYPES`/`ACTUATION_TYPES` + `message_family()` — observation-vs-actuation, closed-by-default), and the lineage/version fields `causes` (observation→actuation) and `supersedes` (same-entity version chain). `KnowledgeRecord` carries the structured measured-or-`None` ledger signals `confidence` [H], `perturbation_strength` [M], and `test_executed_success` [M] (never a fabricated `0.0`) | `Authority`, `KnowledgeRecord`, `KnowledgeEvent`, `OBSERVATION_TYPES`, `ACTUATION_TYPES`, `message_family()`, `compute_entity_id()`, `compute_knowledge_id()`, `compute_content_hash()` |
| `retrieval.py` | 1121 | Deterministic retrieval — regex query planner, parallel dense (Chroma) + lexical (Neo4j full-text) legs, RRF fusion × authority/freshness/exact-id/conflict (hard commit pre-filter), per-cell `repository_id` scope pre-filter (`scope_excluded()`), content-hash `deduplicate`, cosine `collapse_redundant` (embeddings-optional), allowlisted decayed graph expansion, token-budgeted whole-chunk selection, `RetrievalAttempt` (`dedup_path` records the collapse leg), offline `build_evidence_cards()` | `QueryPlan`, `Candidate`, `RetrievalAttempt`, `build_query_plan()`, `retrieve()`, `rrf_base()`, `compute_fused_score()`, `graph_boost()`, `scope_excluded()`, `deduplicate()`, `collapse_redundant()`, `select_evidence()`, `build_evidence_cards()`, `FallbackMode` |
| `prompt_constructor.py` | 456 | Typed prompt-constructor — `PromptConstructor` protocol, `prompt-plan/v1` schema, deterministic validator, one-repair + deterministic fallback renderer, no-fork cache keying, default `deepseek/deepseek-v4-flash` | `PromptConstructor`, `ModelPromptConstructor`, `ConstructionRequest`, `AugmentedPrompt`, `PromptPlan`, `validate_plan()`, `render_prompt()`, `construction_cache_key()`, `hash_work_item()` |
| `knowledge_stream.py` | 449 | The durable transport — pointer-only `KnowledgeEvent` over Redis Streams (DB 2 on 6380); `publish_event()` carries three orthogonal gates (write guard → actuation-armed → lineage `causes`-must-resolve-to-observation), `process_entry()` (read → verify → extract → upsert → XACK), `SOURCE_TYPE_INDEX_KEY` (knowledge_id → source_type, powers the lineage gate); `CONSUMER_GROUPS` = `kb-chroma-v1`/`kb-neo4j-v1`/`kb-ledger-v1`/`kb-registry-v1` | `STREAM_KEY`, `DEAD_LETTER_KEY`, `SOURCE_TYPE_INDEX_KEY`, `CONSUMER_GROUPS`, `connect()`, `publish_event()`, `process_entry()`, `read_artifact()`, `verify_content_hash()`, `reconcile_missing()` |
| `knowledge_ingestion.py` | 599 | Producer-side measured-finding derivation — turns a `_results_summary.json` entry into a MEASURED-authority `KnowledgeRecord` whose text is the evidence-card one-liner, keyed by the canonical dual-id; the richer extractor that supersedes `knowledge_stream.default_extract`. Also the self-build (progressive) phase-finding producer: `derive_phase_record()` / `emit_phase_finding()` emit a completed phase's one-line finding into its OWN cell scope (`MEASURED` when `test_executed_success` is a bool, else `ADVISORY`) | `EXTRACTOR_VERSION` (`"measured-finding/v1"`), `PHASE_EXTRACTOR_VERSION` (`"phase-finding/v1"`), `derive_records()`, `build_record()`, `record_to_artifact()`, `record_to_event()`, `extract_record()`, `derive_phase_record()`, `emit_phase_finding()` |
| `code_ingestion.py` | 403 | Producer-side code-structure derivation — one `source_type=code` `KnowledgeRecord` per function/class (signature + docstring head, no body), `SOURCE`/`[C]`, keyed by the canonical dual-id; `ingest_codebase_graph()` wires the orphaned `graph.load_codebase_graph` so `CodeModule` + IMPORTS/IMPORTED_BY/TOUCHED populate | `EXTRACTOR_VERSION` (`"code/v1"`), `derive_code_records()`, `build_code_record()`, `ingest_codebase_graph()` |
| `quality_ingestion.py` | 308 | Producer-side code-quality derivation — one `source_type=report` `KnowledgeRecord` per available signal (SonarQube/LSP → `MEASURED`/`[M]`, entropy → `DERIVED`/`[C]`), graceful skip-and-note when a tool is absent (never fabricated) | `EXTRACTOR_VERSION` (`"quality/v1"`), `derive_quality_records()`, `build_quality_record()` |
| `spec_status.py` | 566 | Derived spec lifecycle index — joins `experiments/specs/*.yaml` with the run ledgers in `experiments/results/workflows/<spec>/*.json` and emits `experiments/specs/index.json` (machine) + `STATUS.md` (agent-facing table). Generated, never hand-edited; missing runs render as an em-dash, never a failure | `SpecStatusEntry`, `collect_entries()`, `derive_status()`, `build_index()`, `render_status_md()`, `refresh_spec_status()`, `index_entry()` |
| `spec_ingestion.py` | 571 | Producer-side spec-lifecycle ingestion — one `source_type=spec` record per index entry, `POLICY`/`[P]`, `entity_id = spec:<name>`. Emits `operation=supersede` linking the predecessor `knowledge_id` when the registry already holds that entity; a lifecycle fingerprint in the event `reason` makes an unchanged re-run a no-op. Distinct from `policy_ingestion`, which carries the same YAML's *text* for citation | `EXTRACTOR_VERSION` (`"spec-lifecycle/v1"`), `derive_spec_records()`, `build_spec_record()`, `registry_head()`, `spec_event()`, `emit_spec_record()` |
| `policy_ingestion.py` | 288 | Producer-side policy ingestion — one `source_type=policy` `KnowledgeRecord` per pinned policy artifact (`AGENTS.md`, `conventions/*.yaml`, `experiments/specs/*.yaml`, mental-model files), `POLICY`/`[P]`; discoverability/citation only, never RRF candidates | `EXTRACTOR_VERSION` (`"policy/v1"`), `derive_policy_records()`, `build_policy_record()`, `discover_policy_paths()` |
| `story_ingestion.py` | 285 | Canonical-state producer: `source_type=story` — one `KnowledgeRecord` per saved story result (idempotent `story_id` key), `MEASURED`/`[M]`; `derive_story_records_from_run_output()` adapts a `scripts/run.py` result into the same shape | `EXTRACTOR_VERSION` (`"story/v1"`), `derive_story_records()`, `build_story_record()`, `derive_story_records_from_run_output()` |
| `review_ingestion.py` | 160 | Canonical-state producer: `source_type=review` — one `KnowledgeRecord` per merged review, `ADVISORY`/`[H]` | `EXTRACTOR_VERSION` (`"review/v1"`), `derive_review_records()`, `build_review_record()` |
| `ledger_ingestion.py` | 374 | Canonical-state producer: `source_type=ledger_job`/`ledger_attempt`/`meta_session` — job/attempt/session records (`ledger_job`/`ledger_attempt` `MEASURED`/`[M]`, `meta_session` `ADVISORY`); `classify_session()` closes gap (a) no-session fallback and gap (b) `meta_*` pollution | `EXTRACTOR_VERSION` (`"ledger/v1"`), `derive_ledger_records()`, `build_job_record()`, `build_attempt_record()`, `classify_session()` |
| `observation_ingestion.py` | 236 | Canonical-state producer: `source_type=observation`/`flag` — every supervisor verdict is registrable (not only flagged ones, closing round-1 OQ6a), both `ADVISORY`/`[H]` | `EXTRACTOR_VERSION` (`"observation/v1"`), `derive_observation_record()`, `build_observation_record()`, `derive_flag_record()`, `build_flag_record()` |
| `actuation_ingestion.py` | 176 | Canonical-state producer (Delta 3): `source_type=actuation` — a candidate *instruction* to act, `POLICY`/`[P]`, `causes`-linked to a justifying observation; built + unit-tested with ZERO call sites (nothing fires it yet) | `EXTRACTOR_VERSION` (`"actuation/v1"`), `derive_actuation_record()`, `ACTUATION_KINDS` |

The producer-side `source_type` vocabulary (one typed stream — `source_type` + `operation`
are the only discriminators; one pointer envelope, one idempotent `knowledge_id` key), over
the authority ordering (`POLICY > SOURCE > MEASURED > DERIVED > ADVISORY`): **finding → MEASURED
`[M]`** (`knowledge_ingestion`), **code → SOURCE `[C]`** (`code_ingestion`), **report → MEASURED
`[M]`** (Sonar/LSP) or **DERIVED `[C]`** (entropy) (`quality_ingestion`), **policy → POLICY `[P]`**
(`policy_ingestion`), then the five canonical-state producers — **story → MEASURED `[M]`**
(`story_ingestion`), **review → ADVISORY `[H]`** (`review_ingestion`), **ledger_job/ledger_attempt
→ MEASURED `[M]`** + **meta_session → ADVISORY** (`ledger_ingestion`), **observation/flag → ADVISORY
`[H]`** (`observation_ingestion`), **actuation → POLICY `[P]`** (`actuation_ingestion`). All flow
through the same pointer contract (`record_to_artifact` → `record_to_event` → stream → `extract_record`).

`source_type` also carries a second, orthogonal split: `message_family()` (`knowledge.py`)
classifies each type as **observation** (a fact *about* the system — every type not in
`ACTUATION_TYPES`) or **actuation** (a candidate instruction to *act* — `ACTUATION_TYPES =
{"actuation"}`, an allowlist that is closed-by-default). `publish_event()` keys three gates off
this split: the write guard (`FINOPS_KB_WRITE=1` or `authorized=True`) applies to everything; the
actuation-armed gate (`FINOPS_ACTUATION_ARMED=1` or `armed=True`) and the lineage gate (`causes`
must resolve to an observation-family `knowledge_id` via `SOURCE_TYPE_INDEX_KEY`) apply only to
actuation.

Registry / tombstone / compaction (canonical-state rounds): the `kb-registry-v1` consumer group
appends one compacted line per record to the flat, append-only `experiments/results/registry_index.jsonl`;
`operation` discriminates `upsert` / `supersede` / `delete` (a `delete` is a **tombstone**,
requiring a non-empty `reason`); `KnowledgeRecord.supersedes` links same-entity versions and
`causes` links an actuation to its justifying observation. `scripts/generate_manifest.py` compacts
`registry_index.jsonl` into the manifest's `registry` array (latest-per-entity, deriving
`lifecycle_state` `current|superseded|tombstoned` from the supersede/delete chain), surfaced
read-only via `scripts/registry.py` (`show`/`query`/`lineage`) and the Control Room `/api/registry*` routes.

`augment.augment_prompt()` is the seam (R7 — split out of `workflow_runner.py`): between
`route_step()` and `run_agent()` it calls `retrieve → construct → render` (gated by
`spec.workflow.params.rag_augment`, default OFF) and `run_workflow()` persists the returned
`AugmentationOutcome` onto `PhaseResult` provenance (`raw_prompt_hash`, `pre_phase_commit`,
`retrieval_attempt_id`, `constructor_attempt_id`, `selected_evidence_ids`, `augmentation_versions`,
`augmentation_tokens`, `augmentation_cost_usd`, `augmentation_latency_ms`, `fallback_mode`). Any
retrieval/constructor failure falls back to the base prompt and records a named fallback mode.

Scope isolation (the load-bearing invariant): the retrieval filter is **per-cell**. `retrieve()`
carries `Candidate.repository_id` and hard-pre-filters via `scope_excluded()`, dropping any
candidate with a *different, non-empty* `repository_id` before fusion/graph-expansion. The cell
scope is `cell_scope(workdir)` (`self-<worktree>`, `FINOPS_CELL_ID` overrides); an explicitly
non-empty `rag_params.repository_id` is the shared-scope override for coordinated parallel
workstreams. The empty scope never means "global".

Two-channel rule (do not conflate the two Redis planes): the **knowledge** plane is per-cell
scoped (`repository_id`, default `self-<cell>`); the **control/telemetry** plane
(`live.LivePublisher`, pub/sub, DB 1) is unscoped and observe-only — it never writes the KB. The
self-build (progressive) producer is opt-in (`rag_params.emit_self`, default OFF): after a phase
commits, `emit_phase_finding()` emits that phase's one-line finding into the cell's OWN scope
(authority `MEASURED` when `test_executed_success` is a bool, else `ADVISORY`; idempotent key
`f(goal, phase, commit, scope, extractor)`). `knowledge_stream.publish_event` carries a WRITE
GUARD — it raises `RuntimeError` unless `FINOPS_KB_WRITE=1` or `authorized=True`; `kb_produce.py`
/ `kb_produce_sources.py` set the flag for the run, and the emit_self path sets it only for the
duration of the emit. `retrieve → construct → render` references `publish_event` ZERO times.

Two wiring gaps fixed (both live in `retrieval.py`, covered end-to-end in
`tests/test_retrieval.py` with store doubles — no live Chroma/Neo4j required):
1. `collapse_redundant` (cosine > 0.92) was defined/exported but never called — `retrieve()`
   now runs it after `deduplicate`, feeding it pairwise similarities from an optional
   `EmbeddingClient` (an empty dict → no-op when embeddings are unavailable), and records
   the path on the attempt (`dedup_path`: `"embedding"` | `"none"`).
2. `retrieve()` was never exercised against the other modules — the integration tests now
   drive the full fused → deduped → collapsed → expanded → budgeted → selected pipeline
   and assert `fallback_mode` tracks the surviving legs (fully-down → `no_rag`, empty evidence).

### The spec/compiler layer

| Module | Status | Purpose | Key Exports |
|--------|--------|---------|-------------|
| `experiment_spec.py` | **written** | Spec dataclasses + YAML loader + requires/produces validator | `ExperimentSpec`, `Workflow`, `Factor`, `RuleSpec`, `MetricSpec`, `ComparisonSpec`, `WriteupSpec`, `StopSpec`, `AdaptSpec`, `LEDGER_FIELDS`, `load_spec`, `validate_rules`, `validate_spec` |
| `compile_experiment.py` | **written** | spec → DAG; generalizes `_gen_matrix_cells` + `simulate_strategies` | `compile_spec()`, `validate_rules()`, `RuleResult` |

### The rule/ledger interface (schema written; the four formerly-missing fields are now MEASURED)

```
RuleSpec(name, plane, evidence_class, requires, produces)
  plane: "measurement" (produces information) | "control" (consumes it)
  evidence_class: [M] [C] [H] [P]
RuleResult(rule, metric, evidence_class, uncertainty, produces)
first_pass_quality(attempts) -> RuleResult   # measurement (produces)
grit(attempts) -> RuleResult                 # measurement — admitted (strength+success measured)
model_cascade(attempts, state) -> RuleResult # control (consumes confidence) — admitted

JobRecord:    factors{model,condition,policy,seed}, policy_arm, policy_id, budget,
              due_at, forecast_cost, forecast_latency, status
AttemptRecord: attempt_number, retry_reason, escalation_from/to, model,
              queued/leased/started/first_token/ended timestamps,
              tokens{in,out,reasoning,answer,explanation}, cache_hit, tool_calls,
              completed, first_pass, accepted, evaluator_independent,
              confidence: float | None            # MEASURED [H] — AgenticResult.confidence
              perturbation_strength: float | None # MEASURED — StoryResult/run.py (s=0.0 baseline)
              test_executed_success: bool | None  # MEASURED — test_runner.run_suite, never self-report
              cost{inference, orchestration}, rework_cost, reuse_value
```

Instrumentation step 3 is complete: `confidence` ([H] execution-confidence, derived in
`opencode.AgenticResult.confidence` from correctness / tool-call success), `perturbation_strength`
(first-class on `StoryResult` and `scripts/run.py` result dicts), `test_executed_success`
(independent `test_runner.run_suite` wired into `run_story` and `run.py`), and the
`answer`/`explanation` token split (step-granularity heuristic in `opencode._parse_session_output`).
All four are in `LEDGER_FIELDS`, so `validate_rules` now admits the `grit` rule and the
`model_cascade`/`dynamics` control arms. The `answer`/`explanation` split unlocks the Explanation
Tax decomposition (silent vs verbose mode).

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
