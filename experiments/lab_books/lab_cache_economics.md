---
experiment_id: lab_cache_economics
title: "Lab Book: Cache Economics — Is cache policy the hidden cost driver?"
hypothesis: "Cache hit rate and context volume vary independently of model price and are the hidden drivers of multi-session cost."
null_hypothesis: "Cache policy tracks price."
status: completed
created: 2026-08-13
data_sources:
  - experiments/results/stories/*.json
analysis_script: scripts/lab_cache_economics.py
cells: 221
---

# Lab Book: Cache Economics

## Hypothesis

**H1:** Cache hit rate, read/write split, and context volume are independent knobs — none predicts cost or verification.

## Methodology

**Design:** Per-model aggregation of `cache_hit_rate`, `total_cache_reads/writes`, `total_context_tokens`, and `total_tokens` from story summaries. Cost averaged over captured-cost cells only.

## Results

*Executed 2026-08-13.*

| Model | Cost/story | Cache hit | Read/write | Context/cell |
|-------|-----------|-----------|-----------|--------------|
| DeepSeek v4 Flash | $0.068 | 96% | — | 7.0M |
| GPT-5.6 Luna | $0.091 | 98% | 11.9 | 1.3M |
| DeepSeek v4 Pro | $0.138 | 78% | — | 3.2M |
| GPT-5.6 Terra | $1.021 | 82% | — | 0.9M |
| Claude Haiku 4.5 | $1.590 | 61% | 37.3 | 4.7M |
| GPT-5.6 Sol | $3.749 | 84% | — | 1.6M |
| Claude Sonnet 5 | $4.583 | 73% | 32.2 | 5.1M |

## Interpretation

Cache hit rate does not track price: Flash (cheapest) hits 96% but carries 7M context tokens/cell; Luna (also cheap) hits 98% with just 1.3M. Claude models read heavily from cache (r/w 32–37) with mid hit rates. Token volume, cache policy, and cost are three independent axes — a model can be cheap *or* cache-trusting *or* token-hungry in any combination. The cheapest model re-reads its codebase 5× more than the cheapest model's sibling.

## Artifacts

- Analysis script: `scripts/lab_cache_economics.py`
- Output data: `experiments/results/lab_cache_economics.json`
