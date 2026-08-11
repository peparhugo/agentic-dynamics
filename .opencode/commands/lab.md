---
description: Run a specific lab book analysis
agent: build
subtask: true
---

Run a specific lab book analysis from the 14 available labs.

First, load the "lab-books" skill. Then:

1. If a lab name is specified ($ARGUMENTS), run it:
   `python scripts/lab_$ARGUMENTS.py`

2. Available non-deprecated labs:
   claude_audit, grit_matrix, correctness_premium, flail_triggers,
   tool_archetypes, task_routing, basin_topology, survival_horizon,
   sonar_quality, think_do_coupling, story_review, basin_topology_neo4j,
   opencode_meta_analysis

3. If no lab specified, list available labs and ask which to run.

4. Ensure prerequisites exist: `_results_summary.json`, `inventory.json`.
   If not, suggest running `/analyze` or `/pipeline` first.

Report: lab output path, key findings summary.
