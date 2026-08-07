# Lab Books

Structured experiment plans for analyzing the AI FinOps Framework dataset. Each lab book follows the same format as `src/instrument/lab_book.py`: hypothesis → methodology → data sources → analysis steps → expected output → interpretation guide → results (initially empty).

## Status

All six lab books are in `planned` status. Analysis scripts referenced in each lab book do not yet exist — they are described as the implementation target.

## Lab Books

| # | File | Question | Hypothesis |
|---|------|----------|------------|
| 1 | `lab_claude_audit.md` | Where did Claude's $47.54 go? | The cost premium purchases narration, not capability |
| 2 | `lab_grit_matrix.md` | What does the correctness × escape × cost space look like? | DeepSeek clusters in high-Grit quadrant at tiny cost |
| 3 | `lab_correctness_premium.md` | Does Claude's premium buy anything? | Claude never beats DeepSeek on correctness across overlapping tasks |
| 4 | `lab_flail_triggers.md` | What makes a model flail? | Manifold perturbations trigger flailing; SFT models flail more than GRPO |
| 5 | `lab_tool_archetypes.md` | Does tool choice predict code quality? | Write-dominant models produce more modular code; bash-dominant models are more conservative |
| 6 | `lab_task_routing.md` | What's the optimal model-per-task routing? | Grit-routed strategy beats any single-model strategy |

## Execution

Each lab book references a planned analysis script in `scripts/` (e.g., `scripts/lab_claude_audit.py`). When executed, the script should:

1. Read data from `experiments/results/_results_summary.json` and/or `experiments/results/_trajectory_aggregate.json`
2. Perform the analysis steps described in the lab book
3. Output results to `experiments/results/lab_<name>.json`
4. Update the lab book's Results section with findings

The lab books are designed to be self-contained — any researcher can pick one up, understand the methodology, and implement the analysis script without additional context.
