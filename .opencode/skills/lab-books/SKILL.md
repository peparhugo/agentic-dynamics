---
name: lab-books
description: Running structured lab book analyses against accumulated experiment data. Each lab book answers a specific research question using _results_summary.json, inventory.json, and trajectory data. Contains full knowledge of all 14 lab books and their data dependencies.
---

# Lab Books Skill — Full Lab Analysis Knowledge

You are running structured scientific analyses against the AI FinOps Dynamics experiment corpus. This skill injects knowledge of all lab books, their data dependencies, and common analysis patterns.

## Prerequisites (ALWAYS run these first)

```bash
python scripts/inventory.py refresh          # Rebuild inventory
python scripts/analyze_worktrees.py          # Regenerate _results_summary.json
python scripts/analyze_trajectories.py       # Regenerate trajectory aggregates
```

Lab books read from these files in `experiments/results/`:
- `_results_summary.json` — per-experiment solution + efficiency + strategy metrics
- `_trajectory_summary.json` — per-transcript step-level data
- `_trajectory_aggregate.json` — per-model trajectory aggregates
- `inventory.json` — experiment registry

## Active Lab Books (9 non-deprecated)

### Cost & Pricing Analysis

**1. lab_claude_audit.py** (216L) — "Where did Claude's $47.54 go?"
- Per-task cost, correctness, LOC, narration penalty breakdown
- Compares Claude vs DeepSeek on overlapping tasks
- Output: `experiments/results/lab_claude_audit.json`

**2. lab_correctness_premium.py** (202L) — "Does Claude's premium buy anything?"
- Head-to-head correctness on 13 overlapping task types
- Controls for perturbation class and strength
- Output: `experiments/results/lab_correctness_premium.json`

### Behavioral Analysis

**3. lab_grit_matrix.py** (204L) — "Correctness × escape × cost visualization"
- 2D bubble chart data: x=escape, y=correctness, size=cost
- Per-model, per-perturbation class breakdown
- Output: `experiments/results/lab_grit_matrix.json`

**4. lab_flail_triggers.py** (183L) — "What makes a model flail?"
- Failure patterns by model, perturbation class, task type
- Identifies conditions where models fall into recovery loops
- Output: `experiments/results/lab_flail_triggers.json`

**5. lab_tool_archetypes.py** (146L) — "Does tool choice predict code quality?"
- Write-dominant vs bash-dominant vs balanced tool usage patterns
- Correlates tool-call distributions with solution quality
- Output: `experiments/results/lab_tool_archetypes.json`

### Strategy & Topology

**6. lab_task_routing.py** (235L) — "Optimal model-per-task routing"
- Simulates 3 routing strategies across 30 task types
- Cost-optimal, quality-optimal, and blended routing
- Output: `experiments/results/lab_task_routing.json`

**7. lab_basin_topology.py** (209L) — "Attractor basin topology per model"
- Classifies each model's basin shape: shallow/broad, deep/narrow, multi-modal, flat
- Uses basin escape scores + trajectory distances
- Output: `experiments/results/lab_basin_topology.json`

**8. lab_survival_horizon.py** (195L) — "Sessions-to-bankruptcy"
- "Infinite game" framing: how many sessions before fixed budget exhausted?
- Per model, per budget level
- Output: `experiments/results/lab_survival_horizon.json`

### Advanced Analysis

**9. lab_sonar_quality.py** (248L) — "Code quality signals from SonarQube"
- Bugs, vulnerabilities, code smells, complexity across all experiments
- Quality gate pass rates per model
- Output: `experiments/results/lab_sonar_quality.json`

**10. lab_think_do_coupling.py** (318L) — "How coupled are thinking and doing?"
- Think/do phase dynamics analysis from trajectory data
- Measures lag between reasoning and action
- Output: `experiments/results/lab_think_do_coupling.json`

**11. lab_story_review.py** (220L) — "What review patterns emerge across stories?"
- Per-story review aggregation from commit_analysis + review
- Identifies common strengths and weaknesses across multi-session stories
- Output: `experiments/results/lab_story_review.json`

## Graph-Based Analysis (requires neo4j running)

**12. lab_basin_topology_neo4j.py** (193L) — "Basin topology via Neo4j"
- Graph-based attractor basin classification
- Requires Docker: `docker-compose -f infrastructure/docker-compose.yml up -d neo4j`
- Output: `experiments/results/lab_basin_topology_neo4j.json`

## Meta-Analysis

**13. lab_opencode_meta_analysis.py** (178L) — "Patterns in opencode experiments"
- Meta-analysis of experiment structure and outcomes
- Analyzes experiment design itself as data
- Output: `experiments/results/lab_opencode_meta_analysis.json`

## DEPRECATED Lab Books (DO NOT RUN — use non-deprecated alternatives)

```
lab_drift_trajectories_DEPRECATED_bge_m3.py          (240L)
lab_reasoning_volatility_DEPRECATED_bge_m3.py         (203L)
lab_cross_model_reasoning_DEPRECATED_bge_m3.py        (177L)
lab_divergence_cascades_DEPRECATED_bge_m3.py           (211L)
lab_cluster_stability_DEPRECATED_bge_m3.py             (218L)
lab_recovery_curves_DEPRECATED_bge_m3.py               (367L)
```

These used bge-m3 embeddings via Ollama. Superseded by new semantic_validation.py approach (no embeddings needed).

## Running a Lab

```bash
# Standard pattern:
python scripts/lab_grit_matrix.py         # Run the analysis
cat experiments/results/lab_grit_matrix.json | python -m json.tool | head -50  # Inspect

# All labs follow the same pattern:
python scripts/lab_<name>.py
# Output: experiments/results/lab_<name>.json
# Methodology: experiments/lab_books/lab_<name>.md
```

## Lab Book Methodology Documents

Living at `experiments/lab_books/lab_<name>.md`. Each defines:
- Hypothesis being tested
- Data sources (which JSON files)
- Analysis steps
- Interpretation guidance

These are the "experiment plan" documents — lab scripts are the implementation.

## Data Dependencies Map

```
lab_claude_audit.py        → _results_summary.json, inventory.json
lab_grit_matrix.py         → _results_summary.json, inventory.json
lab_correctness_premium.py → _results_summary.json
lab_flail_triggers.py      → _results_summary.json, _trajectory_aggregate.json
lab_tool_archetypes.py     → _trajectory_aggregate.json
lab_task_routing.py        → _results_summary.json
lab_basin_topology.py      → _results_summary.json, _trajectory_aggregate.json
lab_survival_horizon.py    → _results_summary.json
lab_sonar_quality.py       → _results_summary.json
lab_think_do_coupling.py   → _trajectory_summary.json
lab_story_review.py        → _results_summary.json, stories/*.json
```

## Common Patterns When Adding a New Lab

1. Create methodology doc: `experiments/lab_books/lab_<name>.md`
2. Create script: `scripts/lab_<name>.py` that reads from standard JSON sources
3. Output to: `experiments/results/lab_<name>.json`
4. Run with: `python scripts/lab_<name>.py`

## Common Gotchas

- Always refresh inventory + regenerate summary before running labs.
- The DEPRECATED lab scripts use bge-m3 embeddings which are slow — avoid them.
- Some labs require neo4j Docker container running. Skip if unavailable.
- Lab output JSON files are intermediate — they're consumed by website but not committed directly.
- If a lab crashes with KeyError, likely _results_summary.json is stale. Regenerate it.
- `lab_story_review.py` depends on story worktrees having been run first.
