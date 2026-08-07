---
experiment_id: lab_grit_matrix
title: "Lab Book 2: The Grit Matrix — Correctness × Escape × Cost"
hypothesis: "Models with high Grit (high correctness, low escape) cluster in a distinct region of the correctness-escape space, and cost amplifies separation. DeepSeek achieves comparable correctness to Claude at dramatically lower escape rates and costs."
null_hypothesis: "Escape rate and correctness are uncorrelated, and model choice has no systematic effect on the relationship."
status: planned
created: 2026-08-07
data_sources:
  - experiments/results/_results_summary.json
analysis_script: scripts/lab_grit_matrix.py
---

# Lab Book 2: The Grit Matrix — Correctness × Escape × Cost

## Hypothesis

**H1:** Models with high Grit (high correctness, low escape) cluster in a distinct region of the correctness-escape space, and cost amplifies separation.

**H0:** Escape rate and correctness are uncorrelated, and model choice has no systematic effect.

## Methodology

**Design:** 2D scatter/bubble plot. X = escape score (0-1), Y = correctness (0-1), bubble size = cost per session, color = model. Each point = one experiment entry.

**Sample:** ~201 valid entries (non-narration) across all 8 models.

## Data Sources

- `experiments/results/_results_summary.json` — fields: `escape`, `correctness`, `cost`, `model`, `perturbation_class`

## Analysis Steps

1. Filter entries: `narration_failure == False`, `correctness >= 0`
2. Tag each entry: model label, perturbation_class (manifold/semantic/baseline)
3. Compute quadrant boundaries: median escape, median correctness
4. Assign quadrants:
   - **High Grit** (top-left): correctness > median, escape < median
   - **Explorative** (top-right): correctness > median, escape > median
   - **Conservative fail** (bottom-left): correctness < median, escape < median
   - **Wasteful** (bottom-right): correctness < median, escape > median
5. Count entries per model per quadrant
6. Generate bubble chart data for Chart.js

## Expected Output

**Table: Quadrant Distribution by Model**

| Model | High Grit | Explorative | Conservative Fail | Wasteful | Total |
|-------|-----------|-------------|-------------------|----------|-------|
| DeepSeek v4 Pro | 58 | 31 | 12 | 8 | 109 |
| Claude Fable 5 | 18 | 15 | 6 | 0 | 39 |
| GPT-5.6 | 10 | 1 | 3 | 1 | 15 |
| GPT-5-nano | 0 | 1 | 0 | 5 | 6 |
| ... | | | | | |

**Chart:** Bubble chart with:
- X-axis: Escape rate (labeled: "Divergence from baseline →")
- Y-axis: Correctness (labeled: "Correctness →")
- Bubble size: Cost ($0.001–$2.49 range)
- Colors: DeepSeek = green, Claude = amber, GPT-5.6 = blue, nano = red
- Hover tooltip: Model, task type, perturbation class, cost, correctness, escape

## Interpretation Guide

- DeepSeek entries should cluster in High Grit quadrant with tiny (cheap) bubbles
- Claude entries should span High Grit + Explorative with large (expensive) bubbles
- Nano entries should cluster in Wasteful quadrant (high escape, low correctness)
- If Claude entries never appear in Wasteful: Claude doesn't waste — it just costs more
- If manifold perturbation entries cluster in Explorative/Wasteful: linguistic surface shifts are the harder test

## Results

*To be filled after analysis execution.*

## Artifacts

- Analysis script: `scripts/lab_grit_matrix.py`
- Output data: `experiments/results/lab_grit_matrix.json`
- Chart: Bubble chart on evidence.html (reuse existing Chart.js bubble chart infrastructure)
