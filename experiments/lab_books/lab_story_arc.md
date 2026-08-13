---
experiment_id: lab_story_arc
title: "Lab Book: Story Arc — Does cost compound across the 5-session story?"
hypothesis: "Session cost grows across the story arc (greenfield → cross-cutting) because the codebase — and the context each session must read — compounds."
null_hypothesis: "Per-session cost is flat; a later session costs the same as an early one."
status: completed
created: 2026-08-13
data_sources:
  - experiments/results/stories/*.json
analysis_script: scripts/lab_story_arc.py
sessions: 1097
cells: 221
---

# Lab Book: Story Arc

## Hypothesis

**H1 (Snowball):** Session cost grows across the 5-session arc; tokens per session and tests per session also rise.

**H0:** Cost is flat across sessions.

## Methodology

**Design:** Within-story longitudinal. Aggregate per-session `cost_usd`, `total_tokens`, and `agentic.tests_total` by session number (1–5) across all 221 stories, then by perturbation condition.

## Data Sources

- `experiments/results/stories/*.json` — `sessions[].cost_usd`, `sessions[].agentic.total_tokens`, `sessions[].agentic.tests_total`, `perturbation_condition`.

## Analysis Steps

1. For each story, iterate sessions 1–5.
2. Bucket cost/tokens/tests by session number and condition.
3. Compute the Snowball factor = mean(session 5 cost) / mean(session 1 cost).

## Results

*Executed 2026-08-13. 1,097 sessions.*

| Session | Task | n | Avg cost | Avg tokens | Avg tests |
|---------|------|---|----------|-----------|-----------|
| 1 | greenfield | 221 | $0.159 | 18.7K | 4.4 |
| 2 | feature | 221 | $0.210 | 23.5K | 8.4 |
| 3 | integration | 221 | $0.319 | 29.4K | 10.6 |
| 4 | refactor | 217 | $0.290 | 30.0K | 10.9 |
| 5 | cross-cutting | 217 | $0.339 | 34.9K | 14.8 |

**Snowball factor: 2.13×.** Tokens grow 18.7K → 34.9K; tests accumulate 4.4 → 14.8.

## Interpretation

The Snowball Rule is measured, not assumed: the marginal cost of a change is a function of everything committed before it. Per-session cost understates maintenance cost by ~2×; a FinOps model that prices session 5 like session 1 systematically under-budgets.

## Artifacts

- Analysis script: `scripts/lab_story_arc.py`
- Output data: `experiments/results/lab_story_arc.json`
