#!/usr/bin/env python3
"""Build the Neo4j experiment knowledge graph.

Populates Neo4j with the full experiment ecosystem from existing JSON files.
Creates nodes for models, configs, runs, perturbation operators, strategies,
and basin topologies with all relationships.

Usage:
  python scripts/build_graph.py                 # full build
  python scripts/build_graph.py --clear          # wipe and rebuild
  python scripts/build_graph.py --query "MATCH ..."  # run a custom query
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.knowledge.graph import Neo4jClient


def main():
    parser = argparse.ArgumentParser(description="Build Neo4j experiment graph")
    parser.add_argument("--clear", action="store_true", help="Clear existing data first")
    parser.add_argument("--query", type=str, help="Run a Cypher query and print results")
    parser.add_argument("--stats", action="store_true", help="Show graph statistics")
    parser.add_argument("--steps", action="store_true", help="Build step-level graph from ChromaDB")
    parser.add_argument("--step-limit", type=int, default=0, help="Max steps for step graph")
    args = parser.parse_args()

    client = Neo4jClient()

    if args.query:
        result = client._run(args.query)
        records = list(result)
        if records:
            keys = records[0].keys()
            for rec in records:
                print({k: rec[k] for k in keys})
        else:
            print("No results.")
        client.close()
        return

    if args.clear:
        print("Clearing graph...")
        client.clear_all()
        print("Done.")

    if args.steps:
        print("Building step graph from ChromaDB...")
        result = client.build_step_graph(max_steps=args.step_limit)
        print(f"Sessions: {result.get('sessions', 0)}")
        print(f"Steps: {result.get('steps', 0)}")
        print(f"Relationships: {result.get('relationships', 0)}")
        client.close()
        return

    if args.stats:
        stats_queries = [
            ("Models", "MATCH (m:Model) RETURN count(m) AS c"),
            ("ExperimentConfigs", "MATCH (c:ExperimentConfig) RETURN count(c) AS c"),
            ("ExperimentRuns", "MATCH (r:ExperimentRun) RETURN count(r) AS c"),
            ("PerturbationOperators", "MATCH (o:PerturbationOperator) RETURN count(o) AS c"),
            ("StrategyArchetypes", "MATCH (s:StrategyArchetype) RETURN count(s) AS c"),
            ("BasinTopologies", "MATCH (bt:BasinTopology) RETURN count(bt) AS c"),
            ("BasinProfiles", "MATCH (bp:BasinProfile) RETURN count(bp) AS c"),
            ("RUN_ON relationships", "MATCH ()-[rel:RUN_ON]->() RETURN count(rel) AS c"),
            ("INSTANCE_OF relationships", "MATCH ()-[rel:INSTANCE_OF]->() RETURN count(rel) AS c"),
            ("USED_OPERATOR relationships", "MATCH ()-[rel:USED_OPERATOR]->() RETURN count(rel) AS c"),
            ("CLASSIFIED_AS relationships", "MATCH ()-[rel:CLASSIFIED_AS]->() RETURN count(rel) AS c"),
            ("HAS_BASIN relationships", "MATCH ()-[rel:HAS_BASIN]->() RETURN count(rel) AS c"),
            ("PROFILE_IN relationships", "MATCH ()-[rel:PROFILE_IN]->() RETURN count(rel) AS c"),
        ]
        print("\nGraph Statistics:")
        for label, query in stats_queries:
            try:
                result = client._run(query)
                count = result.single()["c"]
                print(f"  {label}: {count}")
            except Exception:
                print(f"  {label}: N/A")
        client.close()
        return

    print("Building knowledge graph...")
    counts = client.build()

    print("\nGraph built successfully:")
    for key, value in counts.items():
        print(f"  {key}: {value}")

    client.close()


if __name__ == "__main__":
    main()
