---
experiment_id: lab_survival_horizon
title: "Lab Book 8: Infinite Game Survival Horizon"
hypothesis: "A model's survival horizon — sessions-to-bankruptcy given a budget and perturbation rate — reveals which architectures sustain long-lived autonomous agents."
null_hypothesis: "All models have equivalent survival horizons under the same budget and perturbation conditions."
status: completed
created: 2026-08-08
data_sources:
  - experiments/results/_results_summary.json
analysis_script: scripts/lab_survival_horizon.py
---

# Lab Book 8: Infinite Game Survival Horizon

## Hypothesis

**H1:** A model's survival horizon reveals which architectures sustain long-lived autonomous agents under finite budgets and variable perturbation rates.

**H0:** All models have equivalent survival horizons.

## Methodology

**Design:** Compute sessions-to-bankruptcy for each model under 6 budget/perturbation scenarios. Effective cost accounts for perturbation frequency, recovery multipliers, and flail rates.

**Formula:**
```
effective_cost = baseline_cost × (1-rate) × (1-flail) + perturbed_cost × rate × (1-flail) × recovery_mult + flail_cost_terms
survival_horizon = budget / effective_cost
```

**Scenarios:**
- Low perturbation (5%) | $1,000
- Moderate perturbation (20%) | $10,000
- High perturbation (50%) | $10,000
- Adversarial (80%) | $1,000
- Enterprise annual | 20% | $100,000
- Enterprise annual | 20% | $1,000,000

## Results

*Executed 2026-08-08.*

| Scenario | DeepSeek | Claude | GPT-5 | GPT-5-nano |
|----------|----------|--------|-------|------------|
| Low (5%) $1K | 65,489 | 1,007 | 5,196 | 250,797 |
| Moderate (20%) $10K | 633,771 | 9,154 | 55,590 | ∞ |
| High (50%) $10K | 595,366 | 7,743 | 64,593 | ∞ |
| Adversarial (80%) $1K | 56,134 | 670 | 7,707 | 120,531 |
| Enterprise $100K | ∞ | 91,549 | 555,908 | ∞ |
| Enterprise $1M | ∞ | 915,492 | ∞ | ∞ |

**Note on nano:** nano scores high on survival because its per-session cost is extremely low ($0.006). This does NOT mean nano is the best model — it means cost minimization is not equivalent to outcome maximization. nano has 70% correctness and 14% flail. A survival metric that accounts for correctness would penalize nano.

**Finding:** DeepSeek achieves the best balance of survival (600K+ sessions under most scenarios) and correctness (92%). Claude's survival is limited by its per-session cost ($1.08) — at adversarial rates, it survives only 670 sessions on a $1K budget. For enterprise deployments at $100K+, Claude becomes viable (91K sessions) but DeepSeek is effectively infinite.

**Null hypothesis:** Rejected. Survival horizons differ by 1-3 orders of magnitude across models.

## Artifacts

- Analysis script: `scripts/lab_survival_horizon.py`
- Output data: `experiments/results/lab_survival_horizon.json`
