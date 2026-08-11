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

Key files you'll modify: `scripts/run.py` (495L), `src/instrument/opencode.py` (526L), `src/instrument/perturb.py` (728L), `src/instrument/story.py` (1095L), `src/instrument/mutation.py` (414L).

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

Config names (omit .yaml): baseline, url_shortener, task_manager, twitter_timeline, web_crawler, search_kv_store, mint_financial, social_graph, collaborative_editor, data_table, form_wizard, notification_system, autocomplete_search, typescript_ssg*, flask_maintenance, fastapi_maintenance, architecture_redesign, rust_git_store, rust_redis, rust_proxy, go_crawler, go_jobqueue, go_grpc_chat, comparative, constraint_detection, recovery_cost, iterative_build, factorial_compound, silent_mode_sweep.

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
