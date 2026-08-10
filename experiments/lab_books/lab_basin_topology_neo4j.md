---
experiment_id: lab_basin_topology_neo4j
title: "Lab Book 12: Neo4j-Accelerated Basin Topology"
hypothesis: "Neo4j graph traversal enables basin topology queries that are combinatorially infeasible with JSON-based Python filtering — revealing emergent relationships between model architecture, perturbation class, and basin type."
null_hypothesis: "The Neo4j graph representation produces the same basin topology classifications as the original JSON-based analysis."
status: planned
created: 2026-08-10
data_sources:
  - Neo4j graph database (bolt://localhost:7687)
  - experiments/results/_results_summary.json
  - experiments/results/lab_basin_topology.json
analysis_script: scripts/lab_basin_topology_neo4j.py
infrastructure:
  - src/instrument/graph.py (Neo4jClient)
  - Neo4j 5.26 with APOC + GDS plugins
---

# Lab Book 12: Neo4j-Accelerated Basin Topology

## Hypothesis

**H1:** Neo4j graph traversal enables basin topology queries that are combinatorially infeasible with JSON-based Python filtering — revealing emergent relationships between model architecture, perturbation class, and basin type.

**H0:** The Neo4j graph representation produces the same basin topology classifications as the original JSON-based analysis (lab_basin_topology).

## Motivation

The original `lab_basin_topology.py` reads `_results_summary.json` and computes basin profiles by filtering entries in Python. This works for simple aggregations but fails for cross-cutting queries — e.g., "find all models where semantic perturbation produces wide_shallow basins AND manifold perturbation produces unstable ones." These require multiple passes through the data.

Neo4j handles these as single Cypher traversals. The graph already contains:
- 227 `ExperimentRun` nodes with all metrics
- 9 `Model` nodes with aggregate stats
- 8 `BasinTopology` + 10 `BasinProfile` nodes
- `RUN_ON`, `CLASSIFIED_AS`, `HAS_BASIN`, `PROFILE_IN` relationships

This lab book re-implements the basin topology analysis using Cypher queries, then extends it with graph-native operations impossible in the original.

## Methodology

**Design:** Two-phase analysis:
1. **Validation**: Reproduce the original basin topology results using Cypher queries. Verify identical output.
2. **Extension**: Run graph-native queries for cross-cutting patterns, path analysis, and community detection.

**Graph model:**
```
(:Model)-[:HAS_BASIN]->(:BasinTopology)-[:PROFILE_IN]->(:BasinProfile {perturbation_class, basin_type, basin_volume})
(:ExperimentRun)-[:RUN_ON]->(:Model)
(:ExperimentRun)-[:CLASSIFIED_AS]->(:StrategyArchetype)
```

**Sample:** All 227 runs, 9 models, 8 basin topologies, 10 basin profiles. Full graph already populated.

## Data Sources

- Neo4j graph database at `bolt://localhost:7687` — fully populated from `scripts/build_graph.py`
- `src/instrument/graph.py` — Neo4jClient for Python-based queries
- `experiments/results/lab_basin_topology.json` — original results for validation

## Analysis Steps

### Phase 1: Validation

1. **Reproduce basin profile computation.** For each model, for each perturbation class:
   ```cypher
   MATCH (r:ExperimentRun)-[:RUN_ON]->(m:Model {model_id: $model_id})
   WHERE r.perturbation_class = $perturbation_class
   RETURN avg(r.escape), avg(r.correctness), avg(r.cost_usd), count(r)
   ```
2. **Compute basin volume** using the same formula: `(1 - escape) × correctness / recovery_multiplier`
3. **Classify basin type** using the same thresholds (wide_shallow, narrow_deep, etc.)
4. **Diff against original results** — verify identical within floating-point tolerance

### Phase 2: Graph-Native Extensions

4. **Cross-class basin discovery.** Find models where semantic and manifold basins differ drastically:
   ```cypher
   MATCH (bt:BasinTopology)-[:PROFILE_IN]->(bp_sem:BasinProfile {perturbation_class: 'semantic'})
   MATCH (bt)-[:PROFILE_IN]->(bp_man:BasinProfile {perturbation_class: 'manifold'})
   WHERE bp_sem.basin_type <> bp_man.basin_type
   RETURN bt.model_id, bp_sem.basin_type, bp_man.basin_type,
          abs(bp_sem.basin_volume - bp_man.basin_volume) AS volume_delta
   ORDER BY volume_delta DESC
   ```

5. **Strategy → basin type pathway.** Traverse from strategy archetypes through runs to basin profiles:
   ```cypher
   MATCH (s:StrategyArchetype)<-[:CLASSIFIED_AS]-(r:ExperimentRun)-[:RUN_ON]->(m:Model)-[:HAS_BASIN]->(bt)-[:PROFILE_IN]->(bp)
   RETURN s.name, bp.perturbation_class, bp.basin_type, count(r) AS run_count
   ORDER BY s.name, run_count DESC
   ```

6. **Model similarity via shared basin types.** Compute model-to-model similarity based on shared basin classification:
   ```cypher
   MATCH (m1:Model)-[:HAS_BASIN]->(bt1)-[:PROFILE_IN]->(bp1)
   MATCH (m2:Model)-[:HAS_BASIN]->(bt2)-[:PROFILE_IN]->(bp2)
   WHERE m1.model_id < m2.model_id
     AND bp1.perturbation_class = bp2.perturbation_class
     AND bp1.basin_type = bp2.basin_type
   RETURN m1.model_id, m2.model_id, count(*) AS shared_types
   ORDER BY shared_types DESC
   ```

7. **GDS community detection.** Optional: use the Graph Data Science plugin to detect communities of models with similar basin behavior.

## Expected Output

**Validated: identical to original lab_basin_topology.json**

**New: Cross-Class Basin Drift**

| Model | Semantic Basin | Manifold Basin | Volume Delta | Drift Severity |
|-------|---------------|----------------|-------------|----------------|
| DeepSeek v4 Pro | wide_shallow (0.691) | unstable (0.168) | 0.523 | Severe |
| Claude Fable 5 | wide_shallow (0.530) | wide_moderate (0.246) | 0.284 | Moderate |
| GPT-5-nano | unstable (0.234) | collapsed (0.091) | 0.143 | Severe |
| GPT-5.6 | wide_shallow (1.193) | — | — | No manifold data |

**New: Strategy → Basin Pathway**

| Strategy | Perturbation Class | Basin Type | Run Count |
|----------|-------------------|------------|-----------|
| conservative | semantic | wide_shallow | 89 |
| conservative | manifold | unstable | 12 |
| exploratory | semantic | wide_moderate | 31 |
| exploratory | manifold | deep_expensive | 8 |
| wasteful | semantic | unstable | 3 |

## Interpretation Guide

- **Cross-class basin drift quantifies model fragility:** Large volume delta between semantic and manifold = model is highly sensitive to perturbation type
- **Strategy → basin mapping:** Conservative strategies tend to produce wide_shallow basins; exploratory → wide_moderate; wasteful → unstable/collapsed
- **Shared basin types between models:** Models with identical basin types likely share architectural properties (MoE/Dense, GRPO/SFT)
- **If GDS detects communities that match architecture families:** Basin topology is a reliable architectural fingerprint

## Expected Findings

1. Neo4j validation produces results identical to original JSON analysis (within tolerance)
2. DeepSeek shows the largest cross-class basin drift (0.523 volume delta) — robust under semantic, fragile under manifold
3. Conservative strategies map overwhelmingly to wide_shallow basins (89/141 conservative runs)
4. Models with shared architecture (GPT-5 ↔ GPT-5.6) share basin types more often than cross-architecture pairs
5. GDS community detection recovers architecture families without being told about them

## Artifacts

- Analysis script: `scripts/lab_basin_topology_neo4j.py`
- Output data: `experiments/results/lab_basin_topology_neo4j.json`
- Infrastructure: `src/instrument/graph.py` (Neo4jClient), Neo4j 5.26
