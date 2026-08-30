---
name: instrument
description: Running perturbation experiments through opencode to measure how language models explore unfamiliar reasoning trajectories under stress. Includes full knowledge of the measurement pipeline, mutation pipeline, story orchestration, and the experiment configs under experiments/definitions/configs/.
---

# Instrument Skill — Full Pipeline Knowledge

You are working with the `agentic_dynamics` measurement apparatus. This skill injects the full
instrument-pipeline knowledge so you don't need to rediscover it.

## Core pipeline (experiment execution)

```
Prompt ──▶ agentic_dynamics.measurement.perturb.perturb_prompt() ──▶ perturbed prompt
                                                                    │
        scripts/run.py ──▶ agentic_dynamics.adapters.opencode.run_opencode_agentic() ──▶ AgenticResult
                                                                    │
              measurement.solution + measurement.basin + measurement.efficiency
              + measurement.recovery_cost + measurement.strategy ──▶ reporting.game_report
```

Key files you'll modify (plane-qualified): `scripts/run.py`,
`src/agentic_dynamics/adapters/opencode.py`, `src/agentic_dynamics/measurement/perturb.py`,
`src/agentic_dynamics/runtime/story/`, `src/agentic_dynamics/measurement/mutation.py`.

## Spec & compiler (written)

The repo is an **information-acquisition machine**: `instrument → derive (measurement rules →
information) → write policy (control rules consuming that information) → grid (policy as an arm)
→ campaign (tweak one variable, repeat)`. Design:
`docs/architecture/current/2026-08-14_experiment-spec-and-compiler-design.md`.

Two modules, both written:

```
src/agentic_dynamics/experiment/experiment_spec.py     # ExperimentSpec, Workflow, Factor, RuleSpec, MetricSpec,
                                                       # ComparisonSpec, WriteupSpec, StopSpec, AdaptSpec + validator
src/agentic_dynamics/experiment/compile_experiment.py  # compile_spec(spec) -> DAG; validate_rules(spec) -> errors
```

**The load-bearing rule (enforced by the validator):** `RuleSpec` declares `requires` /
`produces`; `plane` is `"measurement"` (produces) or `"control"` (consumes). The compiler refuses
a control rule whose `requires` are unmet:

```
ERROR: policy arm "dynamics" requires [confidence, first_pass, deadline_slack]
       — not produced by the ledger or any rule in this spec. Instrument these first.
```

**Consequence for implementation order — instrument `confidence` FIRST**, then author the
`model_cascade`/`dynamics` arms. The formerly-missing signals are now **measured** in the ledger:
`confidence` [H] (`src/agentic_dynamics/adapters/opencode.py:113`), `perturbation_strength` +
`test_executed_success` (`src/agentic_dynamics/knowledge/ledger_ingestion.py:180-181`), and the
`answer`/`explanation` token split (`src/agentic_dynamics/experiment/experiment_spec.py:83`).

**Reuse map (no new transport):** `experiment_matrix` generalizes `_gen_matrix_cells`
(`scripts/pipeline.py`); `experiment_run` = enqueue + worker + run_story; `evaluate_rules` = the
lab books driven by `spec.rules`; `compare_arms` = `control.routing.simulate_strategies`;
`adapt` = the new campaign loop (tweak one factor, emit the next grid).

## Perturbation operators (measurement/perturb.py)

```python
from agentic_dynamics.measurement.perturb import build_operators, perturb_prompt

operators = build_operators()  # dict[str, PerturbationOperator]
perturbed_prompt, perturbation = perturb_prompt(
    prompt="Build a URL shortener...",
    operator_name="remove_critical_constraint",
    strength=0.5,
    rng_seed=42,
)
# perturbation is Perturbation(operator, strength, perturbation_class, vocab_domain)

# 10 operators, three PERTURBATION_CLASSES (measurement/perturb.py is the single source of truth):
#   specification_corruption: inject_false_premise, insert_contradiction,
#                             remove_critical_constraint, inject_phantom_success
#   objective_mutation:       invert_constraint, inject_competing_goal
#   process_perturbation:     inject_alien_vocab, shift_framing, reverse_causality, force_abandonment
```

## Running experiments (scripts/run.py)

```bash
# Single experiment (primary entry point):
python scripts/run.py experiments/definitions/configs/task_manager.yaml --model deepseek

# Or via the CLI:
agentic-dynamics experiment run experiments/definitions/configs/task_manager.yaml --model deepseek
```

Configs live at `experiments/definitions/configs/*.yaml` — `baseline`, `url_shortener`,
`task_manager`, `twitter_timeline`, `web_crawler`, the `go_`/`rust_`/`typescript_` language
families, `comparative`, `constraint_detection`, `recovery_cost`, `iterative_build`, and the
sweep configs. Each defines `task`, `constraints[]`, `operators[]`, `strengths[]`, `model`,
`turns`, `thinking_effort`. `plans.yaml` is the pipeline plan file, not an experiment config.

## The AgenticResult (adapters/opencode.py)

```python
from agentic_dynamics.adapters.opencode import run_opencode_agentic

result = run_opencode_agentic(
    prompt=perturbed_prompt,
    model="deepseek/deepseek-v4-pro",
    thinking_effort="high",
    thinking_budget_tokens=32000,
    output_token_limit=64000,
    timeout=1200,
    silent_mode=False,
    enforce_pytest=True,
    workdir="/tmp/exp_abc123",
)
# result: AgenticResult — run_id, task, model, prompt_tokens, completion_tokens,
#   reasoning_tokens, total_tokens, cost_usd, tests_passed, tests_total, tool_calls[],
#   error_count, retry_loops, session_count, session_timestamps[], perturbation_condition,
#   exit_code, confidence ([H] per-attempt execution confidence)
```

## Multi-session stories (runtime/story + run_story.py)

```bash
python scripts/run_story.py task_manager_api --condition early_degrade \
    --codebase-quality good --tier tier1_minimal --model deepseek/deepseek-v4-pro
```

```python
from agentic_dynamics.runtime.story import (
    run_story, BUILTIN_STORIES, PerturbationCondition,
)
from agentic_dynamics.measurement.mutation import compile_mutation, apply_mutation

# PerturbationCondition: CLEAN | BAD_SEED | EARLY_DEGRADE | LATE_DEGRADE
# BUILTIN_STORIES: task_manager_api, static_site_gen, notification_service
# compile_mutation() compiles a coherent mutation; apply_mutation() writes it to target_path.
```

## Measurement stack (post-hoc, consumed by analyze_worktrees.py)

```python
from agentic_dynamics.measurement.solution import evaluate_solution
from agentic_dynamics.measurement.basin import measure_basin_escape
from agentic_dynamics.measurement.efficiency import compute_efficiency
from agentic_dynamics.measurement.strategy import classify_strategy
from agentic_dynamics.reporting.game_report import GameReport
```

- `evaluate_solution(code, constraints=[...], baseline_code=..., language=..., run_pytest=..., workdir=...)` → `SolutionMetrics`
- `measure_basin_escape(baseline_solution, perturbed_solution, baseline_metrics=..., perturbed_metrics=..., language=...)` → `BasinMetrics`
- `compute_efficiency(result, model=..., baseline_metrics=...)` → `EfficiencyMetrics` (uses `PROVIDER_PRICING`)
- `classify_strategy(basin, solution, efficiency)` → `StrategyReport` (CONSERVATIVE/EXPLORATORY/EFFICIENT/WASTEFUL)
- `GameReport(...).to_markdown()` → provenance-tagged Markdown ([M]/[C]/[H]/[P]/[X])

## Models & pricing

```python
from agentic_dynamics.measurement.efficiency import PROVIDER_PRICING
```

`PROVIDER_PRICING` is the single source of truth for cost — never hardcode prices. Models in use
(`agent_config/rules.md`): `deepseek/deepseek-v4-flash`, `deepseek/deepseek-v4-pro`,
`anthropic/claude-haiku-4-5`, `anthropic/claude-sonnet-5`, `openai/gpt-5.6-luna`,
`openai/gpt-5.6-sol`, `openai/gpt-5.6-terra`.

## Batch & parallel runners

```bash
python scripts/batch_run.py          # parallel batch on DeepSeek
python scripts/sweep_parallel.py     # 4 models × 2 modes × 2 ops
python scripts/sweep_silent_mode.py  # Explanation Tax decomposition

# Redis queue (story experiments) — see the `queue` skill:
agentic-dynamics queue enqueue
agentic-dynamics queue worker
agentic-dynamics queue monitor
```

## Common workflows

### Running a single experiment end-to-end
1. Pick a config from `experiments/definitions/configs/`.
2. `python scripts/run.py experiments/definitions/configs/<name>.yaml --model deepseek`.
3. Check output in `experiments/results/` and `/tmp/exp_*`.

### Creating a new experiment config (e.g. Go)
1. Pick a `name` matching the filename, language-prefixed (`go_`, `rust_`, `typescript_`, or bare for Python).
2. Copy the closest same-language config (`go_crawler.yaml`, `rust_git_store.yaml`, `typescript_eventbus.yaml`).
3. Fill `task`, `constraints` (8-10 bullets), `operators` (5-6 of the 10), `strengths`, `model` + `model_id`.
4. Language flags: Go/Rust → `standardized: {enabled: true, enforce_pytest: false}` (runs `go test`/`cargo test`); Python → `enforce_pytest: true`.
5. Run and verify: GameReport + artifacts under `experiments/results/`, worktree at `/tmp/exp_*`.
6. Downstream: `agentic-dynamics analyze worktrees` then `agentic-dynamics spec pipeline --plan deploy`.

### Adding a new language (AST / tree-sitter / LSP / SonarQube)
`core/language.py` is the single source of truth (everything downstream keys off
`LanguageProfile`). Six layers:
1. **Tree-sitter AST** (`core/language.py`) — add to `_PROFILES` + node-type mappings.
2. **LSP** (`measurement/lsp_diagnostics.py`) — add an `LSPToolConfig` + optional `_parse_<tool>()`.
3. **SonarQube** (`measurement/sonar.py`) — zero code change (analyzer auto-detects the language).
4. **Conventions** (`measurement/commit_analysis.py` + `conventions/<lang>.yaml`).
5. **Test framework** — `LanguageProfile.test_framework`; set `enforce_pytest: false` for non-pytest.
6. **Verify** — `tests/test_language.py`, `tests/test_lsp.py`, `tests/test_commit_analysis.py`.

### Fixing a measurement bug
1. Read `agent_config/mental-model.md` for the module reference.
2. Check `tests/test_<module>.py` for existing coverage.
3. Fix the module; run `pytest tests/test_<module>.py -v`.
4. Run `agentic-dynamics data inventory refresh` if the data pipeline is affected.

## Common gotchas

- Don't confuse `run_opencode_agentic()` (real LLM call) with `evaluate_solution()` (static analysis).
- `PROVIDER_PRICING` is the source of truth for cost calculations.
- Retired: `experiment.py`, `adapter.py`, `lab_book.py`, and the old `instrument` package — use
  `agentic_dynamics.adapters.opencode`.
- Worktrees at `/tmp/exp_*` persist between sessions; clean with `rm -rf /tmp/exp_*`.
- Silent mode suppresses the model's reasoning text — measured for the Explanation Tax.
- Story sessions can time out; recovery handles continuation automatically.
