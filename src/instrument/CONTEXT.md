# `src/instrument/` — Measurement Apparatus

33 Python modules (+ `__init__.py`) that form the core library. Measures search dynamics (not
outputs): basin escape rates, recovery cost, attractor strength, strategy classification.
Pip-installable as `ai-finops-dynamics`.

Two modules form the spec/compiler layer (see `code_reviews/2026-08-14_experiment-spec-and-compiler-design.md`). `experiment_spec.py` is **written**; `compile_experiment.py` is **proposed**. Together they turn the library from a linear pipeline into a cycle: `spec → DAG → cells → jobs → attempts → information → policy → grid → campaign`.

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

### Backend, Telemetry & Routing

| Module | Lines | Purpose | Key Exports |
|--------|-------|---------|-------------|
| `streaming.py` | 123 | Shared line-by-line subprocess runner (live telemetry, timeout-safe) | `stream_subprocess()`, `StreamResult` |
| `claude_adapter.py` | 346 | Drives the Claude CLI (`stream-json`) and translates to opencode events | `run_claude_agentic()`, `ClaudeStreamAdapter`, `adapt_usage()` |
| `backends.py` | 56 | Routes `anthropic/*` → Claude CLI, else opencode | `run_agentic()`, `get_backend_for_model()` |
| `live.py` | 101 | Redis Pub/Sub telemetry (status + per-cell event stream + replay log) | `LivePublisher`, `make_publisher()` |
| `routing.py` | 187 | Task-optimal routing: per-task model recommendation + strategy simulation | `compute_routing()`, `recommend_route()`, `simulate_strategies()` |

### Output

| Module | Lines | Purpose |
|--------|-------|---------|
| `game_report.py` | 319 | Combines all metrics into a single Markdown report per experiment |
| `lab_book.py` | 82 | [deprecated] YAML-frontmatter persistence for experiment results |

### The spec/compiler layer

| Module | Status | Purpose | Key Exports |
|--------|--------|---------|-------------|
| `experiment_spec.py` | **written** | Spec dataclasses + YAML loader + requires/produces validator | `ExperimentSpec`, `Workflow`, `Factor`, `RuleSpec`, `MetricSpec`, `ComparisonSpec`, `WriteupSpec`, `StopSpec`, `AdaptSpec`, `LEDGER_FIELDS`, `load_spec`, `validate_rules`, `validate_spec` |
| `compile_experiment.py` | proposed | spec → DAG; generalizes `_gen_matrix_cells` + `simulate_strategies` | `compile_spec()`, `validate_rules()`, `RuleResult` |

### The rule/ledger interface (proposed)

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
- **Measure before policy** (proposed): measurement rules produce information; control rules consume it. The validator refuses unwritable control arms.

## Adding a New Perturbation Operator

1. Add the operator function in `perturb.py` (with `strength` parameter)
2. Register it in the `__init__.py` exports
3. Create a config YAML in `experiments/configs/` that uses it
4. Run `python scripts/run.py --config experiments/configs/your_config.yaml`

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
