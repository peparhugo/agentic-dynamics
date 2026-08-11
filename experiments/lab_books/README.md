# Lab Books

Structured experiment plans for analyzing the AI FinOps Dynamics dataset. Each lab book follows the same format as `src/instrument/lab_book.py`: hypothesis → methodology → data sources → analysis steps → expected output → interpretation guide → results (initially empty).

## Status

All 13 lab books have been executed. Analysis scripts in `scripts/` produce results to `experiments/results/lab_*.json`. 
The lab books below represent the initial 8 planned analyses; 5 additional analyses (reasoning divergence, semantic clusters, 
cross-model reasoning, basin topology neo4j, and opencode meta-analysis) were added during execution and are documented 
in their respective lab book files.

## Lab Books

| # | File | Question | Hypothesis |
|---|------|----------|------------|
| 1 | `lab_claude_audit.md` | Where did Claude's $47.54 go? | The cost premium purchases narration, not capability |
| 2 | `lab_grit_matrix.md` | What does the correctness × escape × cost space look like? | DeepSeek clusters in high-Grit quadrant at tiny cost |
| 3 | `lab_correctness_premium.md` | Does Claude's premium buy anything? | Claude never beats DeepSeek on correctness across overlapping tasks |
| 4 | `lab_flail_triggers.md` | What makes a model flail? | Manifold perturbations trigger flailing; SFT models flail more than GRPO |
| 5 | `lab_tool_archetypes.md` | Does tool choice predict code quality? | Write-dominant models produce more modular code; bash-dominant models are more conservative |
| 6 | `lab_task_routing.md` | What's the optimal model-per-task routing? | Grit-routed strategy beats any single-model strategy |
| 7 | `lab_basin_topology.md` | What is each model's attractor basin topology? | Basin classification reveals model default strategies |
| 8 | `lab_survival_horizon.md` | How many sessions before bankruptcy? | Cost compounds faster than most budgets can absorb |
| 9 | `lab_reasoning_divergence.md` | How do reasoning trajectories diverge under perturbation? | Manifold perturbations produce higher per-step divergence |
| 10 | `lab_semantic_clusters.md` | What semantic clusters emerge in reasoning patterns? | Models fall into distinct reasoning typologies |
| 11 | `lab_cross_model_reasoning.md` | How does reasoning differ across models? | Architecture determines reasoning topology more than scaling |
| 12 | `lab_basin_topology_neo4j.md` | What is basin topology via graph analysis? | Neo4j validates attractor basin framework |
| 13 | `lab_opencode_meta_analysis.md` | What patterns exist in opencode experiments? | Models analyzing themselves reveal self-consistency limits |

## Execution

Each lab book corresponds to a script in `scripts/` (e.g., `lab_claude_audit.py`). Scripts:

1. Read from `experiments/results/_results_summary.json` and/or `_trajectory_aggregate.json`
2. Perform the analysis steps described in the lab book
3. Write results to `experiments/results/lab_<name>.json`
4. Results feed into the data pipeline via `scripts/build_data.py` (for `lab_grit_matrix.json`) or are standalone analysis artifacts.

The lab books are designed to be self-contained — any researcher can pick one up, understand the methodology, and implement the analysis script without additional context.
