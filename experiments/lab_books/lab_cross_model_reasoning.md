---
experiment_id: lab_cross_model_reasoning
title: "Lab Book 11: Cross-Model Reasoning Similarity — Do Models Think Alike?"
hypothesis: "Different models solving the same task exhibit measurable differences in reasoning approach, and models with similar architectures (DeepSeek GRPO/MoE) cluster closer together in reasoning space than models with different architectures (Claude SFT/Dense)."
null_hypothesis: "All models produce indistinguishable reasoning patterns when solving the same task."
status: planned
created: 2026-08-10
data_sources:
  - experiments/results/reports/exp_*/session.jsonl
  - experiments/results/_results_summary.json
  - experiments/results/typescript_ssg_*.json
analysis_script: scripts/lab_cross_model_reasoning.py
infrastructure:
  - src/instrument/embeddings.py (EmbeddingClient: bge-m3 via Ollama)
  - src/instrument/trajectory.py (compute_trajectory_distance)
---

# Lab Book 11: Cross-Model Reasoning Similarity — Do Models Think Alike?

## Hypothesis

**H1:** Different models solving the same task exhibit measurable differences in reasoning approach, and models with similar architectures (GRPO/MoE) cluster closer together in reasoning space than models with different architectures (SFT/Dense).

**H0:** All models produce indistinguishable reasoning patterns when solving the same task.

## Motivation

The Grit Matrix (lab_grit_matrix) shows that DeepSeek and Claude produce similar outputs but at radically different costs. The Basin Topology (lab_basin_topology) shows they have different attractor topology. But we've never measured whether they *think* differently.

Using the same embedding infrastructure that powers reasoning divergence measurement, we can compare reasoning traces across models on identical tasks. This reveals whether architectural differences (GRPO vs SFT, provider family differences) produce measurably different reasoning approaches — or whether all models converge on the same thinking patterns.

## Methodology

**Design:** For each task type where multiple models have sessions (typescript_ssg, url_shortener, task_manager, etc.), extract reasoning text from all model variants. Compute pairwise embedding distances between model pairs. Produce a cross-model similarity matrix and hierarchical clustering of models by reasoning similarity.

**Sample:** Tasks with ≥2 model variants. Primary: `typescript_ssg` (DeepSeek, Claude, GPT-5 all tested). Secondary: `url_shortener`, `task_manager`. ~15-30 comparison pairs.

**Metrics:**
- **Reasoning distance**: Mean per-step cosine distance between model A and model B reasoning traces
- **Tool sequence divergence**: Levenshtein distance between tool-call sequences (read/write/bash order)
- **Architecture alignment**: Are models with similar architecture (MoE, Dense) closer in reasoning space?

## Data Sources

- `experiments/results/reports/exp_*/session.jsonl` — reasoning traces per model
- `experiments/results/_results_summary.json` — maps sessions to models and tasks
- `experiments/results/typescript_ssg_*.json` — per-model SSG results
- `bge-m3:latest` via Ollama — 1024-dim embedding model

## Analysis Steps

1. **Identify multi-model tasks.** Group sessions by experiment type where ≥2 models appear
2. **Extract reasoning per model-task.** For each (task, model) pair, collect all reasoning text from all sessions of that type
3. **Compute model embedding centroids.** For each (task, model), compute the mean embedding of all reasoning text
4. **Compute pairwise distances.** For each task, compute cosine distance between every model pair
5. **Build similarity matrix.** Aggregate across tasks to produce a global model-to-model reasoning similarity matrix
6. **Hierarchical clustering.** Cluster models by reasoning similarity to test the "architecture alignment" hypothesis
7. **Tool sequence comparison.** For the same task, compute Levenshtein distance between tool-call sequences of different models

## Expected Output

**Table: Cross-Model Reasoning Distances (typescript_ssg)**

| Model A | Model B | Reasoning Distance | Tool Seq Divergence | Output Correctness Δ |
|---------|---------|--------------------|--------------------|--------------------|
| DeepSeek v4 Pro | Claude Fable 5 | 0.38 | 0.45 | -0.05 (DS wins) |
| DeepSeek v4 Pro | GPT-5 | 0.35 | 0.40 | -0.02 (DS wins) |
| DeepSeek v4 Pro | GPT-5-mini | 0.42 | 0.52 | +0.05 (DS wins) |
| Claude Fable 5 | GPT-5 | 0.28 | 0.30 | +0.03 (tie) |
| GPT-5 | GPT-5-mini | 0.15 | 0.18 | +0.07 (GPT-5 wins) |

**Chart: Model Reasoning Dendrogram**

```
                    DeepSeek v4 Pro (GRPO/MoE)
                   /
                  +—— GPT-5 (RLHF/Dense?)
                 /
        ————————+
                 \
                  +—— Claude Fable 5 (SFT/Dense)
                   \
                    GPT-5-nano (SFT/Tiny)
```

**Table: Architecture Similarity Hypothesis Test**

| Architecture Pair | Mean Reasoning Distance | Hypothesis |
|-------------------|------------------------|------------|
| MoE ↔ MoE (same family) | <0.20 | Expect: low distance |
| Dense ↔ Dense (same provider) | <0.25 | Expect: moderate distance |
| MoE ↔ Dense (cross-architecture) | >0.30 | Expect: higher distance |
| GRPO ↔ SFT (cross-training) | >0.35 | Expect: highest distance |

## Interpretation Guide

- **If GPT-5 ↔ GPT-5-mini distance < GPT-5 ↔ DeepSeek:** Same-provider models share reasoning patterns (training data overlap)
- **If Claude ↔ GPT-5 distance ≈ 2× DeepSeek ↔ GPT-5:** Claude's SFT training produces distinctive reasoning
- **If all models converge on same distance (~0.3):** The task, not the model, determines reasoning approach
- **If tool sequence divergence >> reasoning distance:** Models think similarly but act differently (different coding strategies)
- **If reasoning distance >> tool sequence divergence:** Models think differently but converge on the same actions

## Expected Findings

1. Claude and GPT-5 cluster closer together (both SFT/Dense) than either does to DeepSeek (GRPO/MoE)
2. GPT-5 ↔ GPT-5-mini have the lowest reasoning distance (same provider, similar training)
3. DeepSeek has the most distinctive reasoning signature (observed reasoning-text patterns; causal architecture not established)
4. Within a model family (DeepSeek only), reasoning is highly consistent across tasks
5. Tool sequence divergence is higher than reasoning divergence — models execute differently even when thinking similarly
6. Reasoning distance correlates weakly with cost (expensive models don't think "better")

## Related Lab Books

- `lab_grit_matrix.md` — output-level comparison of models (complement: this measures process-level)
- `lab_reasoning_divergence.md` — within-model reasoning change under perturbation (complement: this measures between-model differences)

## Artifacts

- Analysis script: `scripts/lab_cross_model_reasoning.py`
- Output data: `experiments/results/lab_cross_model_reasoning.json`
- Infrastructure: `src/instrument/embeddings.py` (EmbeddingClient)
