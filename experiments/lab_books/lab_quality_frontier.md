---
experiment_id: lab_quality_frontier
title: "Lab Book: Quality Frontier — Is code cleanliness decoupled from cost?"
hypothesis: "Code cleanliness (LSP errors, code-quality score, cyclomatic complexity) is decoupled from cost."
null_hypothesis: "Pricier models produce cleaner code."
status: completed
created: 2026-08-13
data_sources:
  - experiments/results/analysis/*.json
  - experiments/results/stories/*.json
analysis_script: scripts/lab_quality_frontier.py
cells: 221
---

# Lab Book: Quality Frontier

## Hypothesis

**H1:** Cleanliness is decoupled from cost — the same way review quality already is.

## Methodology

**Design:** Per-model mean of mechanical quality signals from the analysis `deep` block: LSP errors (`deep.lsp.errors`), code-quality score (`deep.solution.code_quality_score`), cyclomatic complexity, and novelty — plotted against captured-cost mean.

## Results

*Executed 2026-08-13.*

| Model | Cost/story | LSP errors | Code quality | Cyclomatic |
|-------|-----------|-----------|--------------|------------|
| DeepSeek v4 Flash | $0.068 | 13.5 | 0.035 | 481 |
| GPT-5.6 Luna | $0.091 | 5.1 | 0.086 | 263 |
| DeepSeek v4 Pro | $0.138 | 11.3 | 0.048 | 262 |
| GPT-5.6 Terra | $1.021 | 13.7 | 0.088 | 232 |
| Claude Haiku 4.5 | $1.590 | 9.0 | 0.167 | 283 |
| GPT-5.6 Sol | $3.749 | 9.2 | 0.056 | 298 |
| Claude Sonnet 5 | $4.583 | 9.4 | 0.125 | 289 |

## Interpretation

Cleanliness is decoupled from cost. The cheapest model (Flash) has the *most* LSP errors (13.5) and the *lowest* code-quality score (0.035); the cheapest-but-one (Luna) has the *cleanest* LSP (5.1). Claude Haiku ($1.59) has the best code-quality score (0.167), ~5× Flash's. Paying more buys neither fewer diagnostics nor higher cleanliness — the signals move independently of price.

## Artifacts

- Analysis script: `scripts/lab_quality_frontier.py`
- Output data: `experiments/results/lab_quality_frontier.json`
