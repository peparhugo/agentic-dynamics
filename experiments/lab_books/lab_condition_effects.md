---
experiment_id: lab_condition_effects
title: "Lab Book: Condition Effects — Does perturbing the seed change the whole arc?"
hypothesis: "Perturbing the seed (bad_seed) or the session-1 spec (early_degrade) degrades the whole story arc versus clean."
null_hypothesis: "Perturbation condition has no effect on story success or cost."
status: completed
created: 2026-08-13
data_sources:
  - experiments/results/stories/*.json
analysis_script: scripts/lab_condition_effects.py
cells: 221
---

# Lab Book: Condition Effects

## Hypothesis

**H1:** Condition (clean / bad_seed / early_degrade) shifts success rate and cascade-recovery rate.

**H0:** Conditions are equivalent.

## Methodology

**Design:** Between-condition comparison of the story corpus. Per condition: success rate (`summary.all_successful`), cascade-recovery rate (`summary.cascade_recovery`), and mean cost.

## Data Sources

- `experiments/results/stories/*.json` — `perturbation_condition`, `summary.all_successful`, `summary.cascade_recovery`, `summary.total_cost`.

## Results

*Executed 2026-08-13.*

| Condition | Cells | Success | Cascade | Avg cost |
|-----------|-------|---------|---------|----------|
| clean | 96 | 91% | 0% | $1.25 |
| bad_seed | 40 | 88% | 2% | $1.48 |
| early_degrade | 85 | 85% | 4% | $1.29 |

## Interpretation

Condition effects are modest and monotonic: early_degrade (corrupted session-1 spec) has the lowest success (85%) and the highest cascade rate (4%) — the degraded spec *does* leak, but ~85% of cells still recover to passing. This is the multi-step analogue of the perturbation pipeline's flail analysis: degradation raises cost and cascades slightly, but does not dominate the outcome.

## Artifacts

- Analysis script: `scripts/lab_condition_effects.py`
- Output data: `experiments/results/lab_condition_effects.json`
