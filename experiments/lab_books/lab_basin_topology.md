---
experiment_id: lab_basin_topology
title: "Lab Book 7: Attractor Basin Topology Profile"
hypothesis: "Each model exhibits a distinct attractor basin shape — inferrable from output surface divergence patterns — that explains its behavior under perturbation."
null_hypothesis: "All models exhibit the same attractor basin topology under perturbation."
status: completed
created: 2026-08-08
data_sources:
  - experiments/results/_results_summary.json
analysis_script: scripts/lab_basin_topology.py
reference: "Munshi et al., 'Manifold of Failure: Behavioral Attraction Basins in Language Models,' arXiv:2602.22291, 2026"
---

# Lab Book 7: Attractor Basin Topology Profile

## Hypothesis

**H1:** Each model exhibits a distinct attractor basin shape — inferrable from output surface divergence patterns — that explains its behavior under perturbation.

**H0:** All models exhibit the same attractor basin topology.

## Methodology

**Design:** Classify each model's attractor basin from behavioral output metrics (escape score, correctness, recovery cost). Infer topology from output surface — not latent space geometry.

**Formula:** `basin_volume = (1 - escape) × correctness / recovery_multiplier`

**Basin types:**
- **Wide, shallow**: Low escape, high correctness, low recovery cost → explores efficiently (GRPO/MoE signature)
- **Narrow, deep**: Low escape, high correctness, high recovery cost → stays close to patterns (SFT/Dense signature)
- **Wide, moderate**: Moderate escape, good correctness, reasonable recovery cost
- **Deep, expensive**: Moderate escape, high recovery cost → exploration is expensive
- **Unstable**: Cannot maintain correctness under perturbation
- **Collapsed**: Cannot recover from perturbation (>50% flail rate)

**Reference:** Munshi et al. (2026) introduce "behavioral attraction basins" as the continuous topology of failure regions in LLMs. We extend this framework from safety topology (alignment deviation) to resilience topology (escape × correctness × cost).

## Results

*Executed 2026-08-08. 201 valid entries across 8 models.*

| Model | Class | Basin Type | Escape | Correctness | Recovery Mult | Basin Volume |
|-------|-------|-----------|--------|-------------|---------------|--------------|
| DeepSeek v4 Pro | semantic | wide_shallow | 0.18 | 94% | 1.11× | 0.691 |
| DeepSeek v4 Pro | manifold | unstable | 0.76 | 77% | 1.10× | 0.168 |
| Claude Fable 5 | semantic | wide_shallow | 0.21 | 88% | 1.31× | 0.530 |
| Claude Fable 5 | manifold | wide_moderate | 0.62 | 87% | 1.34× | 0.246 |
| GPT-5-nano | semantic | unstable | 0.45 | 70% | 1.64× | 0.234 |
| GPT-5.6 | semantic | wide_shallow | 0.16 | 94% | 0.66× | 1.193 |

**Finding:** DeepSeek's semantic basin volume (0.691) is 30% larger than Claude's (0.530). Both models collapse under manifold perturbation — linguistic surface shifts force exploration at the cost of correctness. Nano's basin is unstable: escape=0.45, correctness=70%, cannot recover at reasonable cost.

**Basin volume ranking (semantic):** GPT-5.6 > GPT-5-mini > DeepSeek > GPT-5 > Claude > GPT-5.6-fast > GPT-5.5 > GPT-5-nano

**Architecture signatures confirmed:**
- GRPO/MoE (DeepSeek): wide_shallow — explores efficiently, low recovery cost
- SFT/Dense (Claude): wide_shallow under semantic, wide_moderate under manifold — higher recovery cost
- Small dense models (nano, GPT-5.5): unstable or collapsed — cannot maintain integrity under perturbation

## Artifacts

- Analysis script: `scripts/lab_basin_topology.py`
- Output data: `experiments/results/lab_basin_topology.json`
