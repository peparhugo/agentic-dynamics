---
experiment_id: lab_semantic_clusters
title: "Lab Book 10: Semantic Session Clusters — Reasoning Pattern Typology"
hypothesis: "Experiment sessions cluster by reasoning pattern in embedding space, and clusters correspond to strategy archetypes (conservative/exploratory/wasteful) more strongly than to perturbation operator or model."
null_hypothesis: "Session reasoning patterns are uniformly distributed in embedding space with no meaningful clusters."
status: planned
created: 2026-08-10
data_sources:
  - experiments/results/reports/exp_*/session.jsonl
  - experiments/results/_results_summary.json
  - ChromaDB collection: session_embeddings
analysis_script: scripts/lab_semantic_clusters.py
infrastructure:
  - src/instrument/embeddings.py (ChromaStore, EmbeddingClient)
  - bge-m3 via Ollama (1024-dim embeddings)
---

# Lab Book 10: Semantic Session Clusters — Reasoning Pattern Typology

## Hypothesis

**H1:** Experiment sessions cluster by reasoning pattern in embedding space, and clusters correspond to strategy archetypes (conservative/exploratory/wasteful) more strongly than to perturbation operator or model.

**H0:** Session reasoning patterns are uniformly distributed in embedding space with no meaningful clusters.

## Motivation

Existing analysis groups sessions by metadata: model, operator, experiment type. But metadata doesn't capture **behavioral similarity** — do two sessions with different perturbations produce similar reasoning patterns? Do DeepSeek and Claude think alike on the same task?

Using the ChromaDB vector store populated with bge-m3 embeddings of every session's reasoning text, we can discover latent structure: sessions that cluster together in embedding space share reasoning patterns regardless of their labeled category.

## Methodology

**Design:** Query the ChromaDB `session_embeddings` collection for nearest-neighbor distances across all sessions. Compute an all-pairs similarity matrix for a stratified sample (50-100 sessions), then apply agglomerative clustering to discover emergent groups.

**Infrastructure:**
- `ChromaStore.search()` — cosine-similarity nearest-neighbor queries
- `EmbeddingClient.embed()` — 1024-dim bge-m3 embeddings
- `scipy.cluster.hierarchy` — agglomerative clustering with Ward linkage

**Sample:** All sessions currently indexed in ChromaDB (40+ documents across 2 embedding sources: reasoning and tool_outputs). For cross-session similarity: the 50 session_summary embeddings (reasoning text aggregated per session).

## Data Sources

- `ChromaDB: session_embeddings` — vector store with `session_id`, `model`, `experiment`, `operator`, `strategy`, `correctness`, `cost_usd` metadata
- `experiments/results/_results_summary.json` — supplementary metadata for sessions not yet indexed
- `bge-m3:latest` via Ollama — embedding model

## Analysis Steps

1. **Retrieve all session embeddings.** Query ChromaDB for all reasoning documents with their metadata
2. **Build similarity matrix.** For a stratified sample (balancing models and operators), compute pairwise cosine similarity between reasoning embeddings
3. **Cluster.** Apply agglomerative clustering with Ward linkage on the distance matrix (1 − similarity)
4. **Label clusters.** For each cluster, compute:
   - Dominant strategy (% conservative, exploratory, wasteful)
   - Dominant model (% DeepSeek, Claude, GPT)
   - Dominant perturbation class (% semantic, manifold)
   - Mean correctness and cost
5. **Detect outliers.** Sessions with >2σ distance from their nearest neighbor are flagged as reasoning outliers
6. **Cross-task similarity.** For sessions sharing experiment type but different models, compute model-to-model reasoning distance

## Expected Output

**Table: Cluster Composition**

| Cluster | Size | Dominant Strategy | Dominant Model | Mean Cost | Mean Correctness | Label |
|---------|------|-------------------|----------------|-----------|------------------|-------|
| A | 18 | conservative (83%) | DeepSeek (72%) | $0.015 | 0.94 | "Efficient Planners" |
| B | 12 | exploratory (58%) | Claude (50%) | $0.85 | 0.87 | "Expensive Explorers" |
| C | 8 | wasteful (75%) | GPT-5-nano (63%) | $0.03 | 0.45 | "Failing Small Models" |
| D | 6 | conservative (67%) | DeepSeek (83%) | $0.008 | 0.98 | "Minimalist Winners" |
| Outliers | 6 | mixed | mixed | — | — | "Anomalous Reasoning" |

**Table: Cross-Model Reasoning Distance (same task)**

| Experiment | DeepSeek ↔ Claude | DeepSeek ↔ GPT-5 | Claude ↔ GPT-5 |
|-----------|-------------------|-------------------|----------------|
| typescript_ssg | 0.35 | 0.42 | 0.38 |
| url_shortener | 0.28 | 0.31 | 0.40 |
| task_manager | 0.33 | 0.37 | 0.35 |

**Chart:** 2D UMAP projection of session embeddings, colored by cluster label, sized by cost.

## Interpretation Guide

- **If clusters correspond to strategy > operator:** Reasoning patterns predict outcomes more than perturbation type
- **If clusters correspond to model > strategy:** Models have fixed reasoning "fingerprints" regardless of task
- **If manifold sessions cluster apart:** Linguistic perturbation creates a distinct reasoning mode
- **If DeepSeek-Claude distance < DeepSeek-GPT distance:** Architecture matters more than provider
- **Outlier sessions:** Worth manual inspection — may reveal bugs, edge cases, or genuinely novel behavior

## Expected Findings

1. 3-5 coherent clusters emerge from the reasoning similarity matrix
2. Conservative strategy sessions form the largest cluster (they dominate at 62% of all sessions)
3. DeepSeek sessions cluster tightly together (consistent reasoning across tasks)
4. Claude sessions are more spread out (higher variance in reasoning patterns)
5. Manifold-perturbed sessions form a distinct cluster from semantic-perturbed sessions
6. 5-10% of sessions are reasoning outliers — worth individual investigation

## Artifacts

- Analysis script: `scripts/lab_semantic_clusters.py`
- Output data: `experiments/results/lab_semantic_clusters.json`
- Infrastructure: `src/instrument/embeddings.py` (ChromaStore)
