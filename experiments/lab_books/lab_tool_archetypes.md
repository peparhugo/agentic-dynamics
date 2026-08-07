---
experiment_id: lab_tool_archetypes
title: "Lab Book 5: Tool-Choice Archetypes — Write vs Patch vs Bash"
hypothesis: "Models that directly write files produce more modular, higher-quality code than models that patch via bash. The tool choice reflects architectural confidence."
null_hypothesis: "Tool choice pattern has no correlation with code quality or correctness."
status: completed
created: 2026-08-07
data_sources:
  - experiments/results/_trajectory_aggregate.json
  - experiments/results/_results_summary.json
analysis_script: scripts/lab_tool_archetypes.py
---

# Lab Book 5: Tool-Choice Archetypes — Write vs Patch vs Bash

## Hypothesis

**H1:** Models that directly write files produce more modular, higher-quality code than models that patch via bash. Tool choice reflects architectural confidence.

**H0:** Tool choice pattern has no correlation with code quality or correctness.

## Methodology

**Design:** Cross-sectional comparison. Group entries by dominant tool pattern. Compare code quality and correctness across groups.

| Variable | Type | Description |
|----------|------|-------------|
| Tool archetype | Independent | write-dominant (>40% write), bash-dominant (>40% bash), balanced |
| Correctness | Dependent | Score from solution evaluation (0-1) |
| Code quality | Dependent | composite_score, code_quality_score |
| LOC | Dependent | Lines of code per session |
| Modularity | Dependent | functions_per_file from AST |

**Sample:** All valid entries across 8 models where trajectory data exists (255 transcripts mapped to 201 valid entries).

## Data Sources

- `experiments/results/_trajectory_aggregate.json` — `by_task_model` section: write_pct, read_pct, bash_pct per model×task
- `experiments/results/_results_summary.json` — correctness, composite_score, code_quality_score, code_lines, AST metrics

## Analysis Steps

1. For each model×task combination in trajectory data, compute dominant tool: write-dominant (write_pct > 40%), bash-dominant (bash_pct > 40%), balanced (neither > 40%)
2. Map trajectory model×task combinations back to `_results_summary.json` entries by matching model + experiment name
3. Group entries by tool archetype
4. Per archetype: aggregate correctness, composite_score, code_quality_score, LOC, modularity metrics
5. Compare archetypes on cost and cost-adjusted quality

## Expected Output

**Table: Tool Archetype Comparison**

| Tool Archetype | Models | N | Correctness | Code Quality | LOC | Cost/Session | Cost per Correct LOC |
|----------------|--------|---|-------------|--------------|-----|--------------|----------------------|
| Write-dominant | DeepSeek, Claude | ~160 | | | | | |
| Bash-dominant | GPT-5.6, GPT-5-mini, GPT-5.6-fast | ~38 | | | | | |
| Balanced | GPT-5, GPT-5.5, GPT-5-nano | ~26 | | | | | |

**Model × Tool Matrix:**

| Model | Write% | Read% | Bash% | Archetype | Notes |
|-------|--------|-------|-------|-----------|-------|
| DeepSeek | 59.9% | 6.5% | 18.5% | Write-dominant | Uses write + todowrite + edit |
| Claude | 62.1% | 0.0% | 18.1% | Write-dominant | Never reads files |
| GPT-5.6 | 0.0% | 0.3% | 39.0% | Bash-dominant | Uses apply_patch via bash |
| GPT-5-mini | 0.0% | 0.4% | 46.2% | Bash-dominant | Highest bash percentage |
| GPT-5-nano | 0.0% | 9.9% | 12.8% | Read-heavy | Highest read percentage |

## Interpretation Guide

- If write-dominant models produce higher LOC at comparable correctness: writing files directly produces more code per session
- If bash-dominant models show higher correctness but lower LOC: patching existing files may be more conservative/correct but less productive
- If read-heavy models (nano, 9.9% read) also have highest flail rates: reading without writing is a flail signal
- If Claude never reads files (0.0%) but maintains correctness: Claude relies on its training distribution, not file context — this explains the 22.5K cache writes (it stores context for later retrieval instead of reading current state)
- The key insight: tool choice is an architectural fingerprint of the model's interaction with its environment. Write-dominant = confident generation. Bash-dominant = conservative modification. Read-heavy = uncertain exploration.

## Additional Analysis: Tool Sequence as Flail Predictor

Beyond the aggregate percentages, the `tool_call_sequence` array in `_trajectory_summary.json` allows per-session sequence analysis:
- Do flail entries show repeated reads without writes?
- Do they alternate between tools without committing?
- Is there a specific tool-call pattern that precedes narration failure?

## Results

*Executed 2026-08-07. 201 valid entries, 8 models.*

**By Archetype:**
- Write-dominant (148 entries): 91% correctness, $0.30/session, 670 LOC — DeepSeek + Claude
- Bash-dominant (18 entries): 88% correctness, $0.24/session, 291 LOC — GPT-5-mini + GPT-5.6-fast
- Balanced (35 entries): 89% correctness, $0.27/session, 340 LOC — GPT-5, GPT-5.5, GPT-5.6, GPT-5-nano

**Key finding:** Write-dominant models produce 2.3× more LOC per session (670 vs 291/340) at comparable correctness. DeepSeek achieves this at $0.015/session (write-dominant, 670 LOC). Claude also produces 568 LOC (write-dominant) but at $1.08/session.

**Model Profiles:**
- DeepSeek: 59.9% write, 6.5% read, 18.5% bash — iterative writer (15 steps/session)
- Claude: 62.1% write, 0% read, 18.1% bash — confident writer (never reads files)
- GPT-5-nano: 0% write, 9.9% read, 12.8% bash — hesitant reader (highest read%, lowest write%)
- GPT-5.6-fast: 0% write, 0.9% read, 46.3% bash — heavy bash user

**Hypothesis assessment:** H1 partially supported. Write-dominant models produce more LOC at comparable correctness, but quality scores are slightly lower (0.25 vs 0.37 bash-dominant). The tradeoff is volume vs quality, not correctness.

## Artifacts

- Analysis script: `scripts/lab_tool_archetypes.py`
- Output data: `experiments/results/lab_tool_archetypes.json`
