---
name: instrument
description: Running perturbation experiments through opencode to measure how language models explore unfamiliar reasoning trajectories under stress. Includes full knowledge of the measurement pipeline, mutation pipeline, story orchestration, and all 34 experiment configs.
---

# Instrument Skill — Full Pipeline Knowledge

You are working with the AI FinOps Dynamics measurement apparatus. This skill injects the full instrument pipeline knowledge so you don't need to rediscover it.

## Core Pipeline (experiment execution)

```
Prompts ──→ perturb.py ──→ perturb_prompt() ──→ perturbed prompt
                                              ↓
                    scripts/run.py ──→ run_opencode_agentic() ──→ AgenticResult
                                                                  ↓
                                              solution.py, basin.py, efficiency.py,
                                              recovery.py, strategy.py ──→ game_report.py
```

Key files you'll modify: `scripts/run.py` (502L), `src/instrument/opencode.py` (614L), `src/instrument/perturb.py` (752L), `src/instrument/story.py` (1374L), `src/instrument/mutation.py` (438L).

## Spec & Compiler (proposed — next build target)

The repo is an **information-acquisition machine**: `instrument → derive (measurement rules →
information) → write policy (control rules consuming that information) → grid (policy as an arm)
→ campaign (tweak one variable, repeat)`. Design: `code_reviews/2026-08-14_experiment-spec-and-compiler-design.md`.

Two modules are proposed, **not yet in the repo**:

```
src/instrument/experiment_spec.py    # ExperimentSpec, Workflow, Factor, RuleSpec, MetricSpec,
                                     # ComparisonSpec, WriteupSpec, StopSpec, AdaptSpec + validator
src/instrument/compile_experiment.py # compile_spec(spec) -> DAG; validate_rules(spec) -> errors
```

**The load-bearing rule (enforced by the validator):** `RuleSpec` declares `requires` (information
it consumes) and `produces` (information it emits). `plane` is `"measurement"` (produces) or
`"control"` (consumes). The compiler refuses a control rule whose `requires` are unmet:

```
ERROR: policy arm "dynamics" requires [confidence, first_pass, deadline_slack]
       — not produced by the ledger or any rule in this spec. Instrument these first.
```

**Consequence for implementation order — instrument `confidence` FIRST** (plus attempt/timestamp
fields and the `answer`/`explanation` token split), then author the `model_cascade`/`dynamics`
control arms. `confidence` is currently UNMEASURED in the ledger.

**Reuse map (no new transport):** `experiment_matrix` generalizes `_gen_matrix_cells`
(`pipeline.py:394`); `experiment_run` = existing enqueue+worker+run_story; `evaluate_rules` =
the lab books driven by `spec.rules`; `compare_arms` = `routing.simulate_strategies`
(`routing.py:98`); `adapt` = new campaign loop (tweak one factor, emit next grid).

**Flagship spec:** `experiments/specs/routing_regret.yaml` (proposed) — factors
`{model, condition, policy}` where `policy ∈ {cheapest, premium_static, quality_cascade,
dynamics}`. The validator gates the `dynamics` arm until `confidence` is instrumented.

## Perturbation Operators (perturb.py)

```python
from ai_finops_dynamics import build_operators, perturb_prompt

operators = build_operators()  # dict[str, PerturbationOperator]
# Apply operator at given strength:
perturbed_prompt, perturbation = perturb_prompt(
    prompt="Build a URL shortener...",
    operator_name="remove_critical_constraint",
    strength=0.5,
    rng_seed=42
)
# perturbation is Perturbation(operator, strength, vocab_domain)

# 10 operators, two classes:
# MANIFOLD: inject_alien_vocab, shift_framing, reverse_causality, force_abandonment
# SEMANTIC: inject_false_premise, invert_constraint, insert_contradiction,
#           remove_critical_constraint, inject_phantom_success, inject_competing_goal
```

## Running Experiments (scripts/run.py)

```bash
# Single experiment (primary entry point):
python scripts/run.py --config experiments/configs/task_manager.yaml --model deepseek

# Cross-model comparison:
python scripts/run.py --config experiments/configs/comparative.yaml --model deepseek

# The 34 configs are at experiments/configs/*.yaml. Each defines:
# task, constraints[], operators[], strengths[], model, turns, thinking_effort
```

Config names (omit .yaml): baseline, url_shortener, task_manager, twitter_timeline, web_crawler, search_kv_store, mint_financial, social_graph, collaborative_editor, data_table, form_wizard, notification_system, autocomplete_search, typescript_ssg*, typescript_eventbus, typescript_multitenant_api, flask_maintenance, fastapi_maintenance, architecture_redesign, rust_git_store, rust_redis, rust_proxy, go_crawler, go_jobqueue, go_grpc_chat, comparative, constraint_detection, recovery_cost, iterative_build, factorial_compound, silent_mode_sweep. (`plans.yaml` is the pipeline plan file, not an experiment config.)

Typescript variants: typescript_ssg, typescript_ssg_claude, typescript_ssg_gpt5, typescript_ssg_gpt5mini.

## The AgenticResult (opencode.py)

```python
from ai_finops_dynamics import run_opencode_agentic

result = run_opencode_agentic(
    prompt=perturbed_prompt,
    model="deepseek",
    thinking_effort="high",
    thinking_budget_tokens=32000,
    output_token_limit=64000,
    timeout=1200,
    silent_mode=False,
    enforce_pytest=True,
    workdir="/tmp/exp_abc123"
)
# result: AgenticResult with:
#   run_id, task, model, prompt_tokens, completion_tokens,
#   reasoning_tokens, total_tokens, cost_usd,
#   tests_passed, tests_total, tool_calls[], error_count,
#   retry_loops, session_count, session_timestamps[],
#   perturbation_condition, exit_code
```

## Multi-Session Stories (story.py + mutation.py + run_story.py)

```bash
# Run a 5-session story with perturbation:
python scripts/run_story.py --story task_manager --condition early_degrade \
    --codebase-quality good --tier tier1_minimal --model deepseek
```

```python
from ai_finops_dynamics import (
    run_story, BUILTIN_STORIES, PerturbationCondition,
    condition_to_mutations, save_story_result, load_story_result
)

# PerturbationCondition enum:
# CLEAN: no mutation, the control group
# BAD_SEED: codebase starts corrupted (Flash V4 generates bad variant)
# EARLY_DEGRADE: spec corrupted in session 2, cascade recovery measured
# LATE_DEGRADE: spec corrupted in session 4

# Mutation compilation (mutation.py):
from ai_finops_dynamics import compile_mutation, apply_mutation, ALL_OPERATORS
# compile_mutation() calls Flash V4 to generate coherent mutations
# 20 total operators: 10 spec + 10 codebase
# apply_mutation() writes mutated code to target_path

# BUILTIN_STORIES dict keys:
# "task_manager_story" — 5 sessions building a task API
# "static_site_gen_story" — 5 sessions building a TypeScript SSG
# "notification_service_story" — 5 sessions building notification delivery
```

## Measurement Stack (post-hoc, consumed by analyze_worktrees.py)

```python
from ai_finops_dynamics import evaluate_solution, measure_basin_escape

# Solution evaluation:
metrics = evaluate_solution(code, constraints=["..."], baseline_code="...",
                            language="python", run_pytest=True, workdir=Path("/tmp/exp_x"))
# Returns SolutionMetrics: tests_passed, correctness_score, constraint_score,
#                          code_quality_score, novelty_score, composite_score

# Basin escape (not text similarity — structural divergence):
basin = measure_basin_escape(baseline_solution, perturbed_solution,
                              baseline_metrics=bm, perturbed_metrics=pm, language="python")
# Returns BasinMetrics: architecture_divergence, structure_divergence,
#                       escape_score, quality_per_dollar, quality_per_joule

# Efficiency (tokens, dollars, joules):
from ai_finops_dynamics import compute_efficiency
eff = compute_efficiency(result, model="deepseek", baseline_metrics=None)
# Returns EfficiencyMetrics with PROVIDER_PRICING internals

# Strategy classification:
from ai_finops_dynamics import classify_strategy
report = classify_strategy(basin, solution, efficiency)
# Returns StrategyReport with one of: CONSERVATIVE/EXPLORATORY/EFFICIENT/WASTEFUL

# Game report:
from ai_finops_dynamics import GameReport
gr = GameReport(experiment_id="exp_xyz", model="deepseek", ...)
markdown = gr.to_markdown()  # with [M]/[C]/[H]/[X] tags
```

## Models & Pricing

```python
from ai_finops_dynamics.efficiency import PROVIDER_PRICING
# Keys: "deepseek", "anthropic", "anthropic-sonnet5", "openai", "openai-luna"
# Each has: prompt_per_1k, completion_per_1k, reasoning_per_1k (if applicable)

# DeepSeek: 37B active MoE params, env var DEEPSEEK_API_KEY
# Claude: ~500B estimated, env var ANTHROPIC_API_KEY
```

## Batch & Parallel Runners

```bash
# Parallel batch on DeepSeek:
python scripts/batch_run.py

# Redis queue parallel (v0.9, for story experiments):
docker-compose -f infrastructure/docker-compose.experiment.yml up -d
python scripts/enqueue.py
python scripts/worker.py
python scripts/monitor.py  # dashboard

# Phase orchestration (pipeline.py — replaces manual enqueue+worker for the full matrix):
python scripts/pipeline.py --plan full_matrix   # DS → Luna → analyze → review → regenerate → deploy
python scripts/pipeline.py --plan full_matrix --graph   # print DAG
python scripts/pipeline.py --plan full_matrix --from reviews  # resume mid-pipeline

# Sweep runners:
python scripts/sweep_parallel.py     # 4 models × 2 modes × 2 ops = 16 parallel
python scripts/sweep_silent_mode.py  # Explanation Tax decomposition
python scripts/finish_sweep.py       # Incomplete sweep cells
```

## Common Workflows

### Running a single experiment end-to-end:
1. Pick config from experiments/configs/
2. `python scripts/run.py --config experiments/configs/<name>.yaml --model deepseek`
3. Check output in experiments/results/ and /tmp/exp_*

### Running a story experiment (v0.9):
1. `python scripts/run_story.py --story task_manager --condition clean --model deepseek`
2. Results in experiments/results/stories/

### Adding a new perturbation operator:
1. Add operator function in perturb.py
2. Register in build_operators()
3. Create config YAML using it
4. Run with scripts/run.py

### Creating a new experiment config (e.g. Go):
1. Pick a `name` matching the filename, language-prefixed: `go_`, `rust_`, `typescript_`, or bare for Python/Flask.
2. Copy the structure of the closest existing same-language config:
   Go → `go_crawler.yaml`, `go_jobqueue.yaml`, `go_grpc_chat.yaml`
   Rust → `rust_git_store.yaml`, `rust_redis.yaml`, `rust_proxy.yaml`
   TypeScript → `typescript_eventbus.yaml`, `typescript_multitenant_api.yaml`
3. Fill in: `task` (multi-line, detailed spec with a fresh problem), `constraints` (8-10 bullets), `operators` (5-6 of the 10), `strengths`, `model` + `model_id`.
4. Language flags — critical for correctness measurement:
   - Go/Rust: `standardized: {enabled: true, enforce_pytest: false}` — runs `go test`/`cargo test`, NOT pytest.
   - Python: `standardized.enforce_pytest: true` (default pytest).
5. Run: `python scripts/run.py --config experiments/configs/<name>.yaml --model deepseek` (or the `run_experiment` tool).
6. Verify: GameReport + artifacts under `experiments/results/`, worktree at `/tmp/exp_*`.
7. Downstream: `python scripts/analyze_worktrees.py` then `python scripts/pipeline.py --plan deploy` to publish to the website.

Go config skeleton:
```yaml
# Go: <task title>
name: go_<name>
task: >
  <detailed Go task spec with concurrency/goroutines/channels,
   stdlib constraints, and explicit test requirements>
constraints:
  - <constraint 1>
  - <constraint 2>
  # ...
operators:
  - inject_alien_vocab
  - shift_framing
  - remove_critical_constraint
  - inject_false_premise
  - invert_constraint
  - inject_competing_goal
strengths: [0.5]
model: deepseek
model_id: deepseek/deepseek-v4-pro
standardized:
  enabled: true
  enforce_pytest: false
```

### Adding a new language (AST / tree-sitter / LSP / SonarQube):
`language.py` is the single source of truth — everything downstream keys off `LanguageProfile`.
Adding a language touches six layers:

1. **Tree-sitter AST (`language.py`)** — add to the `_PROFILES` registry:
   ```python
   _PROFILES["java"] = LanguageProfile(
       name="java", extensions=[".java"], tree_sitter_id="java",
       test_framework="mvn test", test_file_pattern="*Test.java",
   )
   ```
   Then add the grammar-specific node-type mappings in the three properties
   `function_node_types`, `class_node_types`, `import_node_types` (keys are tree-sitter
   node names, e.g. java `method_declaration` / `class_declaration` / `import_declaration`).
2. **LSP (`lsp_diagnostics.py`)** — add an `LSPToolConfig` to `_TOOLS` with `check_cmd`
   and `diag_cmd`. If the tool's output isn't `file:line:col: message`, add a `_parse_<tool>()`
   and a dispatch branch in `_run_tool`, else it falls through to `_parse_generic`.
3. **SonarQube (`sonar.py`)** — zero code change. It runs `sonar-scanner` with `sonar.sources=.`
   and SonarQube's own analyzer auto-detects the language. Only prerequisite: the language's
   analyzer plugin installed on the SonarQube server (e.g. `sonar.java`).
4. **Conventions (`commit_analysis.py` + `conventions/<lang>.yaml`)** — create the YAML file
   (naming_patterns / forbidden_patterns / scoring). Only `python.yaml` and `typescript.yaml`
   exist today — **Go and Rust currently fall back to empty rules**. In `compute_ast_diff`,
   add a language-specific regex branch if the syntax differs from the `+def`/`+function` fallback.
5. **Test framework** — `LanguageProfile.test_framework` flows to `review.py`'s prompt; set
   `standardized.enforce_pytest: false` in the config YAML for non-pytest languages
   (see `go_crawler.yaml`).
6. **Verify** — `tests/test_language.py`, `tests/test_lsp.py`, `tests/test_commit_analysis.py`.

Tree-sitter nuance: `tree_sitter_id` resolves via `tree_sitter_languages.get_parser(id)`, which
bundles ~70 grammars (python, go, rust, typescript, java, c, cpp, csharp, ruby, …). Mainstream
languages "just work"; for an unbundled grammar you'd swap in `tree_sitter_language_pack` or
register a grammar manually — the exception, not the rule.

### Fixing a measurement bug:
1. Read src/instrument/CONTEXT.md for the module reference
2. Check tests/test_<module>.py for existing coverage
3. Fix the module
4. Run `pytest tests/test_<module>.py -v`
5. Run `python scripts/inventory.py refresh` if data pipeline affected

## Common Gotchas

- Don't confuse run_opencode_agentic() (real LLM call) with evaluate_solution() (static analysis).
- PROVIDER_PRICING is the source of truth for cost calculations — never hardcode prices.
- The old adapter.py and experiment.py are deprecated with warnings. Ignore them.
- Worktrees at /tmp/exp_* persist between sessions. Clean up with `rm -rf /tmp/exp_*`.
- Silent mode suppresses the model's reasoning text — measured for Explanation Tax.
- Story sessions can timeout (1200s default). Recovery handles continuation automatically.
- Flash V4 mutation compilation requires FLASH_API_KEY for compile_mutation().
