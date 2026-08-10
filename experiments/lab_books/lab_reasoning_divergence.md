---
experiment_id: lab_reasoning_divergence
title: "Lab Book 9: Reasoning Divergence — How Perturbation Scrambles Thinking"
hypothesis: "Perturbation operators produce measurable divergence in the model's reasoning process (not just output), and manifold operators cause systematically higher reasoning divergence than semantic operators."
null_hypothesis: "Perturbation type has no effect on the semantic similarity of a model's reasoning traces."
status: planned
created: 2026-08-10
data_sources:
  - experiments/results/reports/exp_*/session.jsonl
  - experiments/results/_results_summary.json
analysis_script: scripts/lab_reasoning_divergence.py
infrastructure:
  - src/instrument/trajectory.py (compute_trajectory_distance, _embedding_distance)
  - src/instrument/embeddings.py (EmbeddingClient: bge-m3 via Ollama)
---

# Lab Book 9: Reasoning Divergence — How Perturbation Scrambles Thinking

## Hypothesis

**H1:** Perturbation operators produce measurable divergence in the model's reasoning process (not just output), and manifold operators (vocab swap, framing shift) cause systematically higher reasoning divergence than semantic operators (false premises, constraint removal).

**H0:** Perturbation type has no effect on the semantic similarity of a model's reasoning traces.

## Motivation

The existing basin escape metric (`basin.py`) measures **output divergence** — did the model build a structurally different solution? This answers "what changed" but not "how did thinking change."

Reasoning divergence measures **process divergence** — did the model change how it thought about the problem? Using bge-m3 embeddings via Ollama, we compute per-step cosine distance between baseline and perturbed reasoning traces. This is the complement to basin escape: output change vs. process change.

## Methodology

**Design:** For each baseline worktree and its perturbed counterparts, extract reasoning text (the `"type": "reasoning"` events from `session.jsonl`), compute embedding vectors via bge-m3, and calculate per-step cosine distance. Aggregate into a divergence matrix: operator × model × reasoning_distance.

**Sample:** All valid experiment pairs where both baseline and perturbed sessions exist. ~80-100 comparison pairs across 4 models and 6 perturbation operators.

**Formula:**

```
per_step_distance = (1 - cosine_similarity(baseline_step_embedding, perturbed_step_embedding)) / 2
reasoning_divergence = mean(per_step_distances)  # averaged across all compared steps
```

## Data Sources

- `experiments/results/reports/exp_*/session.jsonl` — full reasoning traces with `"type": "reasoning"` events
- `experiments/results/_results_summary.json` — maps worktree names to models, operators, experiments
- `bge-m3:latest` via Ollama — 1024-dim embeddings at ~50ms per text

## Analysis Steps

1. **Identify baseline sessions.** From `_results_summary.json`, find entries with `operator: "baseline"` per experiment
2. **Identify perturbed counterparts.** For each baseline, find entries with same `experiment` and `model` but different operator
3. **Extract reasoning traces.** Parse `session.jsonl` for `"type": "reasoning"` events, concatenate text per step
4. **Compute per-pair divergence.** For each (baseline, perturbed) pair:
   - Embed each step's reasoning text via `EmbeddingClient`
   - Compute cosine distance per step pair
   - Average across all steps for the pair divergence score
5. **Aggregate by operator.** Group divergence scores by perturbation operator name
6. **Aggregate by perturbation class.** Compare manifold vs semantic divergence
7. **Aggregate by model.** Compare how different models' reasoning is affected by the same operator

## Expected Output

**Table: Per-Operator Reasoning Divergence (DeepSeek v4 Pro)**

| Operator | Class | Mean Divergence | Std Dev | N Pairs | Baseline Correctness | Perturbed Correctness |
|----------|-------|-----------------|---------|---------|----------------------|-----------------------|
| baseline (self) | — | 0.00 | 0.00 | 10 | 0.94 | 0.94 |
| inject_alien_vocab | manifold | 0.42 | 0.15 | 15 | 0.94 | 0.74 |
| shift_framing | manifold | 0.38 | 0.12 | 14 | 0.94 | 0.80 |
| remove_critical_constraint | semantic | 0.18 | 0.09 | 12 | 0.94 | 0.88 |
| inject_phantom_success | semantic | 0.22 | 0.11 | 13 | 0.94 | 0.85 |
| invert_constraint | semantic | 0.31 | 0.10 | 11 | 0.94 | 0.78 |
| inject_competing_goal | semantic | 0.25 | 0.13 | 10 | 0.94 | 0.82 |

**Table: Per-Model Reasoning Divergence (manifold only)**

| Model | Mean Divergence (manifold) | Mean Divergence (semantic) | Basin Escape (semantic) | Δ (reasoning − basin) |
|-------|---------------------------|---------------------------|------------------------|----------------------|
| DeepSeek v4 Pro | 0.40 | 0.24 | 0.18 | +0.06 |
| Claude Fable 5 | 0.35 | 0.22 | 0.21 | +0.01 |
| GPT-5 | 0.45 | 0.28 | 0.20 | +0.08 |

**Key metric: Δ (reasoning − basin)** — positive delta means the model's thinking was affected more than its output changed. Negative delta means thinking stayed stable while output diverged.

## Interpretation Guide

- **Manifold > semantic reasoning divergence:** Confirms that linguistic surface shifts scramble internal reasoning more than semantic perturbations, even when output divergence is similar
- **High Δ for DeepSeek:** GRPO-trained reasoning is explicitly surfaced as text — embedding distance captures real process change, not just output drift
- **Low Δ for Claude:** SFT/dense models may show less reasoning divergence because chain-of-thought is implicit (not surfaced in reasoning events)
- **Operator ranking:** Operators that induce highest reasoning divergence likely test different cognitive systems than highest-output-divergence operators

## Expected Findings

1. Manifold operators produce 1.5-2× higher reasoning divergence than semantic operators
2. `inject_alien_vocab` produces highest reasoning divergence (random vocab substitution disrupts internal representations)
3. `remove_critical_constraint` produces lowest reasoning divergence (the model continues thinking normally but produces different code)
4. The Δ (reasoning − basin) metric reveals which models "think differently but build similarly" vs "think the same but build differently"
5. DeepSeek's surfaced reasoning makes it the most measurable model for process-level analysis

## Artifacts

- Analysis script: `scripts/lab_reasoning_divergence.py`
- Output data: `experiments/results/lab_reasoning_divergence.json`
- Infrastructure: `src/instrument/embeddings.py` (EmbeddingClient), `src/instrument/trajectory.py` (_embedding_distance)
