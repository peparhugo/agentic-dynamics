# `src/instrument/` — Measurement Apparatus

16 Python modules that form the core library. Measures search dynamics (not outputs): basin escape
rates, recovery cost, attractor strength, strategy classification. Pip-installable as `reasoning-instrument`.

## Architecture

```
Prompt ──→ perturb.py ──→ adapter.py ──→ [LLM] ──→ trajectory.py
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
| `perturb.py` | 697 | 10 perturbation operators (4 manifold + 6 semantic) | `Perturbation`, `PerturbationOperator`, `build_operators()`, `perturb_prompt()` |
| `adapter.py` | 142 | Wraps LLM calls to capture trajectory steps | `InstrumentedAdapter` |
| `opencode.py` | 421 | Spawns real opencode sessions (think/write/test loop) | `run_opencode_agentic()` |
| `experiment.py` | 302 | Orchestrates full experiment: perturb → invoke → evaluate | `ExperimentConfig`, `run_experiment()` |

### Measurement Modules

| Module | Lines | Purpose | Key Exports |
|--------|-------|---------|-------------|
| `trajectory.py` | 313 | Captures step-level reasoning trace (thought/action/tool/tokens) | `TrajectoryStep`, `ReasoningTrajectory` |
| `solution.py` | 211 | 4-dimension evaluation (correctness, constraints, quality, novelty) | `SolutionMetrics` |
| `basin.py` | 254 | Structural divergence from baseline (not text similarity) | `BasinMetrics` |
| `efficiency.py` | 264 | Token breakdown, dollar cost, joule estimate per model architecture | `EfficiencyMetrics`, `compute_efficiency()` |
| `recovery.py` | 257 | Classifies tokens as EXPLORATION / RECOVERY / STABLE | `SegmentClassification`, `classify_trajectory_segments()` |
| `recovery_cost.py` | 171 | Economic cost of constraint recovery ($ per removed constraint) | `RecoveryCost`, `compute_recovery_cost()` |
| `strategy.py` | 192 | 4 archetypes: CONSERVATIVE, EXPLORATORY, EXPLOITATIVE, FLAILING | `StrategyType`, `StrategyReport`, `classify_strategy()` |

### Validation Modules

| Module | Lines | Purpose | Key Exports |
|--------|-------|---------|-------------|
| `constraint_detection.py` | 268 | Detects whether model notices removed constraints | `ConstraintDetection` |
| `semantic_validation.py` | 300 | 3 signals: pragmatic markers, AST edit distance, tool-call latency | `MarkerProfile`, `ASTProfile`, `EscapeProfile`, `analyze_markers()`, `analyze_ast()`, `analyze_escape()` |

### Output

| Module | Lines | Purpose |
|--------|-------|---------|
| `game_report.py` | 263 | Combines all metrics into a single Markdown report per experiment |
| `lab_book.py` | 75 | YAML-frontmatter persistence for experiment results |

## Which Scripts Consume Which Modules

| Script | Modules Used |
|--------|-------------|
| `scripts/run.py` | experiment, adapter, perturb, all measurement modules |
| `scripts/analyze_worktrees.py` | solution, basin, efficiency, strategy, game_report |
| `scripts/analyze_trajectories.py` | trajectory |
| `scripts/validate_session.py` | solution (test pass/fail) |
| `scripts/lab_*.py` (all 8) | efficiency, solution, strategy, basin |
| `scripts/build_data.py` | (reads JSON output, not Python modules directly) |

## Key Design Decisions

- **Search dynamics, not output quality.** The instrument doesn't judge code — it measures how the model searches for solutions and what that search costs.
- **Output-based divergence** (basin.py): Architecture/tech-stack/pattern differences, not text similarity.
- **Model-agnostic** (semantic_validation.py): No embeddings needed. Uses linguistic markers + AST analysis.
- **Provenance-tagged** (game_report.py): All metrics tagged [M]easured, [C]omputed, [H]euristic, or e[X]ternal.
- **Energy estimation** (efficiency.py): DeepSeek uses 37B active MoE params; Claude/others use architecture estimates with GPU TDP constants.

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
