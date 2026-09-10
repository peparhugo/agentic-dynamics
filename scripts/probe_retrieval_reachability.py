#!/usr/bin/env python3
"""Reproducible live probe: can retrieval reach knowledge across a mismatched commit?

Runs the REAL ``retrieve()`` against the LIVE stores and emits machine-checkable JSON. This is
the g5 F3 evidence artifact generator: the dense store (Chroma) lives on the host's
``ai-infra`` network, which the fleet's cell network cannot reach BY DESIGN, so the dense leg's
live evidence is host-side and reproduced by this script; the lexical leg is also probeable
in-cell against ``bolt://neo4j:7687`` (the ``neo4j`` service alias on ``fleet-net``).

Environment: ``CHROMA_HOST``/``CHROMA_PORT`` (default ``127.0.0.1``/``8100``), ``NEO4J_URI``
(default ``bolt://localhost:7687``), ``NEO4J_USER``/``NEO4J_PASSWORD`` (default
``neo4j``/``password123``).

    python3 scripts/probe_retrieval_reachability.py > docs/reviews/flash_exploration_retrieval_probe.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.knowledge.embeddings import ChromaStore
from agentic_dynamics.knowledge.graph import Neo4jClient
from agentic_dynamics.knowledge.retrieval import retrieve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--commit-sha", default="0" * 40)
    parser.add_argument(
        "--query", default="grit recovery under process perturbation test success"
    )
    parser.add_argument("--repository-id", default="agentic-dynamics")
    parser.add_argument("--acl-scope", default="public")
    args = parser.parse_args(argv)

    dense_available = True
    store = None
    try:
        store = ChromaStore(
            host=os.environ.get("CHROMA_HOST", "127.0.0.1"),
            port=int(os.environ.get("CHROMA_PORT", "8100")),
            collection_name="knowledge_chunks_v1",
        )
    except Exception as exc:  # noqa: BLE001 — a missing dense store is REPORTED, not a crash
        dense_available = False
        print(f"dense store unavailable: {exc!r}", file=sys.stderr)

    graph = Neo4jClient(
        uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", "password123"),
    )

    out: dict = {
        "commit_sha": args.commit_sha,
        "dense_available": dense_available,
        "query": args.query,
        "runs": [],
    }
    for projection in (False, True):
        attempt = retrieve(
            args.query,
            dense_store=store,
            graph_client=graph,
            repository_id=args.repository_id,
            acl_scope=args.acl_scope,
            commit_sha=args.commit_sha,
            pattern_projection=projection,
        )
        evidence = attempt.selected_evidence
        by_type: dict[str, int] = {}
        for candidate in evidence:
            by_type[candidate.source_type] = by_type.get(candidate.source_type, 0) + 1
        stale_source = [
            {
                "source_type": c.source_type,
                "authority": c.authority.name,
                "commit_sha": str(c.commit_sha),
                "locator": str(c.locator),
            }
            for c in evidence
            if c.authority.name == "SOURCE" and c.commit_sha and str(c.commit_sha) != args.commit_sha
        ]
        out["runs"].append(
            {
                "pattern_projection": projection,
                "fallback_mode": attempt.fallback_mode,
                "candidates": len(attempt.candidates),
                "selected": len(evidence),
                "selected_by_source_type": by_type,
                "stale_source_selected": stale_source,
                "selected_evidence": [
                    {
                        "source_type": c.source_type,
                        "authority": c.authority.name,
                        "commit_sha": str(c.commit_sha),
                        "locator": str(c.locator),
                    }
                    for c in evidence
                ],
            }
        )

    graph.close()
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
