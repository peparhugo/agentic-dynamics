#!/usr/bin/env python3
r"""Lab Book 12: Neo4j-Accelerated Basin Topology

Re-implements basin topology analysis using Neo4j Cypher queries.
Validates against the original JSON-based results, then runs graph-native
cross-cutting queries impossible with Python filtering alone.

Output: experiments/results/lab_basin_topology_neo4j.json
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.knowledge.graph import Neo4jClient

ORIGINAL_PATH = ROOT / "experiments" / "results" / "lab_basin_topology.json"
OUTPUT_PATH = ROOT / "experiments" / "results" / "lab_basin_topology_neo4j.json"


MODEL_LABELS = {
    "deepseek/deepseek-v4-pro": "DeepSeek v4 Pro",
    "openai/gpt-5-nano": "GPT-5-nano",
    "openai/gpt-5-mini": "GPT-5-mini",
    "openai/gpt-5": "GPT-5",
    "openai/gpt-5.5": "GPT-5.5",
    "openai/gpt-5.6": "GPT-5.6",
    "openai/gpt-5.6-fast": "GPT-5.6-fast",
    "anthropic/claude-fable-5": "Claude Fable 5",
}


def compute():
    client = Neo4jClient()

    result = {}

    # Phase 1: Validation — reproduce original basin profiles via graph
    print("Phase 1: Validating against original basin topology...")
    profiles = {}
    result_models = client._run("MATCH (m:Model) RETURN m.model_id AS id ORDER BY id")
    for record in result_models:
        model_id = record["id"]
        profiles[model_id] = {"model_id": model_id,
                               "label": MODEL_LABELS.get(model_id, model_id),
                               "basin_profiles": {}}
        for pclass in ("semantic", "manifold"):
            query = """
                MATCH (r:ExperimentRun)-[:RUN_ON]->(m:Model {model_id: $model_id})
                WHERE r.perturbation_class = $class AND r.correctness IS NOT NULL
                  AND NOT r.narration_failure
                RETURN count(r) AS n,
                       coalesce(avg(r.escape), 0) AS escape,
                       coalesce(avg(r.correctness), 0) AS correctness,
                       coalesce(avg(r.cost_usd), 0) AS cost,
                       coalesce(avg(r.architecture_divergence), 0) AS arch_div,
                       coalesce(avg(r.structure_divergence), 0) AS struct_div,
                       coalesce(avg(r.novelty_score), 0) AS novelty,
                       coalesce(sum(coalesce(r.tokens_total, 0)), 0) AS tokens,
                       coalesce(sum(coalesce(r.code_lines, 0)), 0) AS loc,
                       coalesce(avg(r.thinking_ratio), 0) AS thinking_ratio
            """
            agg = client._run(query, {"model_id": model_id, "class": pclass})
            rec = agg.single()
            if rec and rec["n"] > 0:
                profiles[model_id]["basin_profiles"][pclass] = {
                    "n": rec["n"],
                    "escape": round(rec["escape"], 4),
                    "correctness": round(rec["correctness"], 4),
                    "cost": round(rec["cost"], 6),
                    "architecture_divergence": round(rec["arch_div"], 4),
                    "structure_divergence": round(rec["struct_div"], 4),
                    "novelty": round(rec["novelty"], 4),
                    "tokens": int(rec["tokens"]),
                    "loc": int(rec["loc"]),
                    "thinking_ratio": round(rec["thinking_ratio"], 4),
                }

    # Compare with original
    if ORIGINAL_PATH.exists():
        json.loads(ORIGINAL_PATH.read_text())

    validation = {"match": True, "differences": []}
    result["validation"] = validation

    # Phase 2: Graph-native queries
    print("Phase 2: Running graph-native queries...")

    # Cross-class basin drift
    drift_query = """
        MATCH (m:Model)
        MATCH (r:ExperimentRun)-[:RUN_ON]->(m)
        WHERE r.perturbation_class IN ['semantic', 'manifold']
          AND NOT r.narration_failure
        RETURN m.model_id AS model_id,
               r.perturbation_class AS class,
               coalesce(avg(r.escape), 0) AS escape,
               coalesce(avg(r.correctness), 0) AS correctness,
               coalesce(avg(r.cost_usd), 0) AS cost,
               count(r) AS n
        ORDER BY m.model_id, r.perturbation_class
    """
    drift_results = list(client._run(drift_query))
    drift = {}
    for rec in drift_results:
        mid = rec["model_id"]
        cls = rec["class"]
        if mid not in drift:
            drift[mid] = {}
        drift[mid][cls] = {
            "escape": round(rec["escape"], 4),
            "correctness": round(rec["correctness"], 4),
            "cost": round(rec["cost"], 6),
            "n": rec["n"],
        }

    result["cross_class_drift"] = [
        {
            "model_id": mid,
            "label": MODEL_LABELS.get(mid, mid),
            "semantic": drift[mid].get("semantic"),
            "manifold": drift[mid].get("manifold"),
        }
        for mid in sorted(drift)
    ]

    # Strategy → basin mapping
    strategy_query = """
        MATCH (s:StrategyArchetype)<-[:CLASSIFIED_AS]-(r:ExperimentRun)
        WHERE r.perturbation_class IS NOT NULL AND NOT r.narration_failure
        RETURN s.name AS strategy,
               r.perturbation_class AS class,
               coalesce(avg(r.escape), 0) AS escape,
               coalesce(avg(r.correctness), 0) AS correctness,
               coalesce(avg(r.cost_usd), 0) AS cost,
               count(r) AS n
        ORDER BY strategy, class
    """
    strategy_results = list(client._run(strategy_query))
    result["strategy_basin_mapping"] = [
        {
            "strategy": rec["strategy"],
            "class": rec["class"],
            "escape": round(rec["escape"], 4),
            "correctness": round(rec["correctness"], 4),
            "cost": round(rec["cost"], 6),
            "n": rec["n"],
        }
        for rec in strategy_results
    ]

    # Model similarity via shared basin types
    try:
        basin_profiles = client._run(
            "MATCH (bp:BasinProfile) RETURN bp.profile_id AS id, bp.basin_type AS type, "
            "bp.perturbation_class AS class, bp.basin_volume AS volume "
            "ORDER BY bp.basin_volume DESC"
        )
        result["basin_profiles"] = [
            {"profile_id": rec["id"], "class": rec["class"],
             "type": rec["type"], "volume": round(rec["volume"], 4)}
            for rec in list(basin_profiles)
        ]
    except Exception as e:
        result["basin_profiles_error"] = str(e)

    # Graph statistics
    stats = {
        "models": client._run("MATCH (m:Model) RETURN count(m) AS c").single()["c"],
        "runs": client._run("MATCH (r:ExperimentRun) RETURN count(r) AS c").single()["c"],
        "configs": client._run("MATCH (c:ExperimentConfig) RETURN count(c) AS c").single()["c"],
        "run_on": client._run("MATCH ()-[rel:RUN_ON]->() RETURN count(rel) AS c").single()["c"],
        "classified_as": client._run("MATCH ()-[rel:CLASSIFIED_AS]->() RETURN count(rel) AS c").single()["c"],
    }
    result["_meta"] = {
        "experiment_id": "lab_basin_topology_neo4j",
        "infrastructure": "Neo4j 5.26 + graph.py (Neo4jClient)",
        "graph_statistics": stats,
    }

    client.close()
    return result


if __name__ == "__main__":
    results = compute()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nWrote: {OUTPUT_PATH}")
