---
experiment_id: lab_grit_matrix
title: "Lab Book 2: The Grit Matrix — Correctness × Escape × Cost"
hypothesis: "Models with high Grit (high correctness, low escape) cluster in a distinct region of the correctness-escape space, and cost amplifies separation. DeepSeek achieves comparable correctness to Claude at dramatically lower escape rates and costs."
null_hypothesis: "Escape rate and correctness are uncorrelated, and model choice has no systematic effect on the relationship."
status: completed
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

*Executed 2026-08-07. 201 valid entries across 8 models.*

**Quadrant boundaries:** escape median = 0.0, correctness median = 1.0. The data is bimodal — most entries achieve perfect correctness or zero escape, creating natural clustering at extremes.

| Model | High Grit | Explorative | Consv Fail | Wasteful |
|-------|-----------|-------------|------------|----------|
| DeepSeek v4 Pro | **51.4%** | 19.3% | 10.1% | 19.3% |
| Claude Fable 5 | 35.9% | 17.9% | 23.1% | 23.1% |
| GPT-5.6 | 46.7% | 33.3% | 13.3% | 6.7% |
| GPT-5-nano | 0.0% | 0.0% | 16.7% | **83.3%** |
| GPT-5 | 9.1% | 36.4% | 18.2% | 36.4% |

**Manifold vs Semantic:**
- Semantic perturbations (185 entries): 80 high grit, 46 explorative, 29 consv fail, 30 wasteful
- Manifold perturbations (16 entries): 13 wasteful, 3 explorative, 0 high grit, 0 consv fail

**Finding:** DeepSeek clusters in High Grit quadrant (51.4%) — more than any other model. GPT-5-nano clusters in Wasteful (83.3%). Manifold perturbations produce zero High Grit entries — linguistic surface shifts force all models into Explorative or Wasteful quadrants.

**Chart data:** 8 datasets ready for Chart.js bubble chart rendering. X-axis: escape (0-1), Y-axis: correctness (0-1), bubble radius: cost ($0.001-$2.49 ×15).

## Artifacts

- Analysis script: `scripts/lab_grit_matrix.py`
- Output data: `experiments/results/lab_grit_matrix.json`
- Chart: Bubble chart on evidence.html (reuse existing Chart.js bubble chart infrastructure)
