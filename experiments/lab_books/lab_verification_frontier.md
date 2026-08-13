---
experiment_id: lab_verification_frontier
title: "Lab Book: Verification Frontier — Does test thoroughness track cost?"
hypothesis: "Test thoroughness is a monotonic function of cost — pricier models write more tests."
null_hypothesis: "Test count is independent of cost; verification is a vendor behavior, not a price point."
status: completed
created: 2026-08-13
data_sources:
  - experiments/results/stories/*.json
analysis_script: scripts/lab_verification_frontier.py
models: 7
cells: 221
---

# Lab Book: Verification Frontier

## Hypothesis

**H1:** More expensive models write more tests per story — the "verification scales with cost" story.

**H0:** Test thoroughness is independent of price. Cheap and expensive siblings within a vendor write comparable test counts.

## Methodology

**Design:** Cross-model comparison of the story corpus. Per model: mean cost/story and mean tests/story. Tests are recovered from `summary.test_count` with an in-session `agentic.tests_total` floor (worktrees are cleaned, so summary counts can be zero). Cost is averaged over cells with a captured cost record only — the Claude subscription CLI is not per-token metered, so 12/31 Haiku and 8/31 Sonnet cells have no cost and are excluded from cost means (not treated as $0).

**Pareto frontier:** a model is on the frontier if no other model is both cheaper *and* writes more tests.

## Data Sources

- `experiments/results/stories/*.json` — `summary.total_cost`, `summary.test_count`, `sessions[].agentic.tests_total`.

## Analysis Steps

1. Load 221 story results.
2. Recover `tests` per story (summary → agentic floor).
3. Group by model; mean tests (all cells) and mean cost (captured cells only).
4. Compute Pareto frontier.

## Results

*Executed 2026-08-13. 221 cells, 7 models.*

| Model | Cells | Cost/story | Tests/story | Frontier |
|-------|-------|-----------|-------------|----------|
| DeepSeek v4 Flash | 30 | $0.068 | 33.5 | ✓ |
| GPT-5.6 Luna | 34 | $0.091 | 7.3 | |
| DeepSeek v4 Pro | 35 | $0.138 | 34.4 | ✓ |
| GPT-5.6 Terra | 30 | $1.021 | 8.8 | |
| Claude Haiku 4.5 | 31 | $1.590 | 117.4 | ✓ |
| GPT-5.6 Sol | 30 | $3.749 | 12.9 | |
| Claude Sonnet 5 | 31 | $4.583 | 122.1 | ✓ |

**Finding:** H1 is rejected. OpenAI spans a 41× price range ($0.09 → $3.75) with tests flat at 7–13; Claude spans 2.9× ($1.59 → $4.58) with tests flat at ~120. The verification gap is between vendors, not price tiers.

## Interpretation

Verification is a *vendor behavior*, not a *price point*. You do not buy more tests by paying for a pricier sibling model; you buy them by switching vendors. Caveat: Claude's cost mean is over a subset (19/31, 23/31 cells) due to unmetered subscription runs; its verification count is over the full 31 cells.

## Artifacts

- Analysis script: `scripts/lab_verification_frontier.py`
- Output data: `experiments/results/lab_verification_frontier.json`
