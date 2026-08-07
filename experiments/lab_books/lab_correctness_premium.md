---
experiment_id: lab_correctness_premium
title: "Lab Book 3: Does Claude's Premium Buy Anything?"
hypothesis: "Across 13 overlapping task types, Claude never achieves higher correctness than DeepSeek at any statistically meaningful margin. The 69x cost premium purchases zero correctness improvement."
null_hypothesis: "Claude achieves higher correctness than DeepSeek on at least 3 of the 13 overlapping task types."
status: planned
created: 2026-08-07
data_sources:
  - experiments/results/_results_summary.json
analysis_script: scripts/lab_correctness_premium.py
---

# Lab Book 3: Does Claude's Premium Buy Anything?

## Hypothesis

**H1:** Across 13 overlapping task types, Claude never achieves higher correctness than DeepSeek at any statistically meaningful margin.

**H0:** Claude achieves higher correctness than DeepSeek on at least 3 of the 13 overlapping task types.

## Methodology

**Design:** Head-to-head comparison on 13 tasks where both models ran the same experiment config. Point-by-point correctness and cost comparison.

| Variable | Description |
|----------|-------------|
| Cost ratio | Claude cost / DeepSeek cost per task |
| Correctness delta | Claude correctness - DeepSeek correctness per task |
| Significance threshold | Claude leads only if correctness delta > 5pp (0.05) |

**Sample:** 13 overlapping task types. Minimum 1 entry per model per task. Small n per task (1-4 entries). Report as exploratory, not conclusive.

## Data Sources

- `experiments/results/_results_summary.json` — cross-reference experiment names between models

## Analysis Steps

1. Normalize experiment names (strip `_s0.5`, `_r1`, `_r2`, `_r3` suffixes)
2. Identify task types where BOTH models have ≥1 entry
3. Per task type: compute mean correctness and mean cost per model
4. Compute Claude-DeepSeek correctness delta per task
5. Count tasks where Claude correctness > DeepSeek correctness by >5pp
6. Aggregate: total cost, weighted correctness, cost per correct session

## Expected Output

**Table: Does Claude Ever Win?**

| Task Type | Claude Correct | DS Correct | Delta | Claude Wins? | Cost Ratio |
|-----------|---------------|------------|-------|--------------|------------|
| baseline | 100% | 100% | 0pp | Tie | 10.5× |
| url_shortener | 81% | 97% | -16pp | DeepSeek | 61.6× |
| inject_alien_vocab | 90% | 74% | +16pp | Claude | 82.6× |
| task_manager | 70% | 100% | -30pp | DeepSeek | 105.7× |
| ... | | | | | |

**Aggregate:**
```
Tasks where Claude beats DeepSeek: X/13
Tasks where DeepSeek beats Claude: Y/13
Tied: Z/13
Average correctness delta: DeepSeek ±Npp
Average cost ratio: N×
```

**Cost per correct session:**
```
Claude: $47.54 / (44 × 0.86) = $1.26 per correct session
DeepSeek: $2.04 / (119 × 0.91) = $0.019 per correct session
Ratio: 66× more expensive per correct outcome
```

## Interpretation Guide

- If Claude beats DeepSeek on ≤2 tasks: null hypothesis rejected. Claude's premium doesn't buy general correctness
- If Claude beats DeepSeek primarily on manifold perturbations (alien vocab, shift framing): Claude's advantage is specific to linguistic-surface stress tests, not general coding
- If DeepSeek beats Claude on semantic perturbations (constraint removal, false premises): DeepSeek is better at detecting and recovering from logical corruption

## Results

*To be filled after analysis execution.*

## Artifacts

- Analysis script: `scripts/lab_correctness_premium.py`
- Output data: `experiments/results/lab_correctness_premium.json`
