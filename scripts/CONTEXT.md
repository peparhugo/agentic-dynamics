# `scripts/` — Scripts Reference

25 scripts across 4 categories: experiment runners, post-hoc analysis, data pipeline, and 14 lab books.

## Primary Entry Points

| Script | What it does | When to use |
|--------|-------------|-------------|
| `run.py` (488 lines) | Full experiment pipeline — perturb → invoke → evaluate → report | Running a single experiment config |
| `analyze_worktrees.py` (1263 lines) | Post-hoc Game Report generator from `/tmp/exp_*` worktrees | After experiments complete; fills gap for sessions that only collected raw cost data |
| `inventory.py` (402 lines) | Experiment/worktree inventory CLI | `inventory.py refresh` to rebuild, `list`/`stats`/`report` to inspect |
| `build_data.py` (562 lines) | Generates `firebase/public/data.js` from inventory + results | Push updated data to website |

## Experiment Runners

| Script | Lines | Purpose |
|--------|-------|---------|
| `run.py` | 488 | Primary runner. `python scripts/run.py --config <yaml>`. Produces JSON + Markdown game reports. |
| `batch_run.py` | 110 | Parallel batch runs on DeepSeek via `ThreadPoolExecutor`. |
| `multi_phase.py` | 128 | Iterative development: understand → build → refactor → add_feature. Measures compounding effects. |
| `remaining_batch.py` | 81 | Runs remaining uncompleted experiment cells one at a time. |
| `finish_sweep.py` | 73 | Completes remaining silent-mode sweep cells. |
| `sweep_parallel.py` | 99 | 4 models × 2 silent modes × 2 operators = 16 parallel subprocess runs. |
| `sweep_silent_mode.py` | 287 | Measures "natural" vs "forced-silent" cost gap (Explanation Tax decomposition). |
| `sweep_parallel.sh` | 141 | Bash equivalent of parallel silent-mode sweep. |

## Post-Hoc Analysis

| Script | Lines | Purpose |
|--------|-------|---------|
| `analyze_worktrees.py` | 1263 | **Primary analysis script.** Reads worktrees, evaluates code, runs full analysis stack (solution, basin, strategy), produces GameReport markdown files. `--no-tests` flag skips pytest. |
| `analyze_trajectories.py` | 350 | Parses `session.jsonl` transcripts. Produces `_trajectory_summary.json` and `_trajectory_aggregate.json`. |
| `validate_session.py` | 98 | Runs `pytest` on generated code in worktrees. Replaces heuristic correctness with actual test pass/fail. |

## Data Pipeline & Maintenance

| Script | Lines | Purpose |
|--------|-------|---------|
| `inventory.py` | 402 | Reads opencode.db, worktrees, results JSONs, config YAMLs. Commands: `refresh`, `list`, `stats`, `worktrees`, `report`. |
| `build_data.py` | 562 | Produces `window.FRAMEWORK_DATA` with provenance-tagged [M]/[C]/[H]/[X] measurements for the website. |
| `backfill_artifacts.py` | 263 | Copies generated code from `/tmp/exp_*` to `experiments/results/reports/`. Extracts session transcripts from SQLite. |
| `regen_typescript_ssg.py` | 172 | Reconstructs TypeScript SSG worktrees from opencode DB part records. |
| `batch_analyze_ts_ssg.py` | 159 | Runs `analyze_worktrees` on just the typescript_ssg worktrees. |
| `recovery_cost_table.py` | 99 | Extracts baseline vs perturbed cost by operator×strength from DB. |

## Lab Books (8 scripts)

| Script | Question Answered | Key Output |
|--------|-------------------|------------|
| `lab_claude_audit.py` | Where did Claude's $47.54 go? | Per-task cost/correctness/LOC/narration penalty |
| `lab_grit_matrix.py` | What does correctness × escape × cost look like? | 2D bubble chart data (bubble size = cost) |
| `lab_correctness_premium.py` | Does Claude's premium buy anything? | Head-to-head correctness on 13 overlapping task types |
| `lab_flail_triggers.py` | What makes a model flail? | Failure patterns by model, perturbation class, task type |
| `lab_tool_archetypes.py` | Does tool choice predict code quality? | Write-dominant vs bash-dominant vs balanced patterns |
| `lab_task_routing.py` | What's the optimal model-per-task routing? | 3 routing strategies simulated across 30 task types |
| `lab_basin_topology.py` | What is each model's attractor basin topology? | Shallow/broad, deep/narrow, multi-modal, flat classifications |
| `lab_survival_horizon.py` | How many sessions before bankruptcy? | Sessions-to-exhaustion per model, per budget |
