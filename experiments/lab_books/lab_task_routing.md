---
experiment_id: lab_task_routing
title: "Lab Book 6: Task-Optimal Routing — Decision Table"
hypothesis: "A routing strategy (DeepSeek by default, escalate to Claude/GPT-5.6 only when correctness drops below 85%) produces lower total cost at equal or higher correctness than any single-model strategy."
null_hypothesis: "A single-model strategy produces better cost-correctness outcomes than a routing strategy."
status: planned
created: 2026-08-07
data_sources:
  - experiments/results/_results_summary.json
analysis_script: scripts/lab_task_routing.py
---

# Lab Book 6: Task-Optimal Routing — Decision Table

## Hypothesis

**H1:** A Grit-routed strategy produces lower total cost at equal or higher correctness than any single-model strategy.

**H0:** A single-model strategy produces better cost-correctness outcomes.

## Methodology

**Design:** Simulated routing comparison. Compute total cost and weighted correctness for three strategies:

1. **Claude-only:** All tasks routed to Claude (baseline premium strategy)
2. **DeepSeek-only:** All tasks routed to DeepSeek (baseline cost strategy)
3. **Grit-routed:** DeepSeek default. Escalate to Claude/GPT-5.6 only when DeepSeek correctness < 85% AND the escalation model has higher correctness on that specific task type.

**Sample:** 13 overlapping tasks where both DeepSeek and Claude have data. Extended to all 30 task types for per-model recommendations.

## Data Sources

- `experiments/results/_results_summary.json` — per-task per-model correctness and cost
- `_trajectory_aggregate.json` — `by_task_model` for all model×task combinations

## Analysis Steps

1. For each of 30 task types, collect all models with ≥1 entry
2. Per task type, rank models by:
   - Primary: correctness/cost ratio (efficiency score = correctness / cost)
   - Tiebreaker: absolute correctness
3. Build per-task best-model recommendation
4. Simulate three strategies:
   - Claude-only: sum costs, average correctness across Claude entries
   - DeepSeek-only: sum costs, average correctness across DeepSeek entries
   - Grit-routed: route each task to recommended model; compute total cost and weighted correctness
5. Count: tasks where recommended model is DeepSeek vs Claude vs GPT-5.6 vs other

## Expected Output

**Table: Per-Task Model Recommendation**

| Task Type | Best Correctness | Best Cost | Recommended Model | Reasoning |
|-----------|-----------------|-----------|-------------------|-----------|
| baseline | Both 100% | DS $0.016 | DeepSeek | Tied on correctness, 10.5× cheaper |
| url_shortener | DS 97% | DS $0.008 | DeepSeek | Wins on both metrics |
| inject_alien_vocab | Claude 90% | DS $0.017 | Claude (escalate) | 16pp correctness gap, evaluate if worth 82.6× cost |
| task_manager | DS 100% | DS $0.019 | DeepSeek | Wins on both metrics |
| ... | | | | |

**Strategy Comparison:**

| Strategy | Total Cost | Weighted Correctness | Cost per Correct Session |
|----------|------------|---------------------|--------------------------|
| Claude-only | $28.62 | 86% | $1.23 |
| DeepSeek-only | $0.93 | 91% | $0.018 |
| Grit-routed | $1.08 | 93% | $0.020 |

**Routing Distribution:**
```
DeepSeek: N tasks (N% of total)
Claude escalation: M tasks (M% of total)
GPT-5.6 escalation: P tasks (P% of total)
```

## Interpretation Guide

- If DeepSeek-only beats Claude-only on BOTH cost AND correctness: the null hypothesis is rejected — Claude is never the right default
- If Grit-routed adds marginal correctness at minimal marginal cost: the routing strategy is optimal
- If only 1-2 tasks justify Claude escalation: the framework's "use Claude for mission-critical" recommendation applies to a very narrow set of perturbation types
- The decision table becomes a routing ruleset: "for tasks of type X, use model Y; if correctness drops below Z, escalate to model W"

## Results

*To be filled after analysis execution.*

## Artifacts

- Analysis script: `scripts/lab_task_routing.py`
- Output data: `experiments/results/lab_task_routing.json`
