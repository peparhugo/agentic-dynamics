---
experiment_id: lab_verification_value
title: "Lab Book: Verification Value — Does writing more tests predict reviewer outcomes?"
hypothesis: "More tests correlate with fewer reviewer-flagged 'worse' commits and more 'better' commits."
null_hypothesis: "Test count is uncorrelated with reviewer outcome."
status: completed
created: 2026-08-13
data_sources:
  - experiments/results/stories/*.json
  - experiments/results/reviews/review_*.json
analysis_script: scripts/lab_verification_value.py
reviewer_model: deepseek/deepseek-v4-flash
---

# Lab Book: Verification Value

## Hypothesis

**H1:** Test thoroughness predicts reviewer quality — high-test stories get fewer "worse" commits.

**H0:** Verification and reviewer-judged quality are independent (consistent with the page's "review quality is decoupled from test thoroughness" finding).

## Methodology

**Design:** Join per-story test counts to the second-model commit reviews (`better_or_worse` per commit). Bucket by (model, test count), compute worse-rate per bucket, then correlate test count with worse-rate across cells with ≥3 reviews.

## Data Sources

- `experiments/results/stories/*.json` — recovered test count.
- `experiments/results/reviews/review_*.json` — `commit_reviews[].better_or_worse`, `story_id`.

## Analysis Steps

1. Recover test count per story.
2. For each aggregate review file, tally better/worse/neutral per commit.
3. Compute worse-rate per (model, tests) bucket.
4. Pearson correlation of tests vs worse-rate over buckets with ≥3 reviews.

## Results

*Executed 2026-08-13. Reviewer: DeepSeek v4 Flash.*

**correlation(tests, worse_rate) = −0.226.**

## Interpretation

Weak negative correlation: more tests predict *slightly* fewer "worse" commits, but the effect is small. This is consistent with H0-leaning behavior — verification is weakly protective but does not substitute for architecture quality, which the reviewer scores independently. The decoupling finding on the evidence page holds: tests and reviewer-judged quality are largely independent signals.

## Artifacts

- Analysis script: `scripts/lab_verification_value.py`
- Output data: `experiments/results/lab_verification_value.json`
