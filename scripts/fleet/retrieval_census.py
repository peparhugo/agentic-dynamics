#!/usr/bin/env python3
"""Retrieval census (p4_activation_gate) — leg contribution + fallback_mode measurement.

Slice 3 claimed the two-leg RRF fusion as a live product gate from a SINGLE query
(``docs/fleet/06_slice3_neo4j_rrf_log.md``: dense-only 1, lexical-only 8, fused 0). The
retrieval-activation agenda (``docs/architecture/current/2026-09-01_retrieval_agenda.md``)
and decision record explicitly refuse to treat that one-query snapshot as sufficient product
proof and require a census over a real query set before the gate can be called "measured"
(``docs/architecture/current/2026-09-01_retrieval_decisions.md`` §7 item 3).

This script runs ``retrieve()`` (the SAME path ``augment_prompt`` uses, via
``default_retrieve_fn``) against a deterministic sample of real work-item text — actual
``question:`` fields from committed workflow specs (``workflows/**/*.yaml``), not synthetic
strings — plus a few exact-identifier-heavy queries that mimic a real phase citing a file path
or symbol. It reports, over the whole set:

  - the ``fallback_mode`` distribution (full / lexical_graph_only / dense_local_exact / no_rag)
  - leg-contribution totals: candidates seen only by the dense leg, only by the lexical leg, or
    surfaced by both (a fused, same-id hit on both legs)
  - the active ``WEIGHTS_VERSION``

No source is mutated; this is a read-only measurement over the live Chroma + Neo4j stores.

Usage:
    python3 scripts/fleet/retrieval_census.py [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

# A deterministic sample (random.seed(7), n=12) of real workflow-spec `question:` fields,
# named explicitly so the query TEXT is always re-read from the current tree (never a frozen
# copy that could drift from the spec it names).
SAMPLE_SPEC_NAMES = [
    "context_abstraction_implement",
    "cap_addendum_implement",
    "fleet_job_submission",
    "routing_kb_experiment_design",
    "cap_2e_cell_unseen_family",
    "queue_steer",
    "routing_follow_up",
    "canonical_state_design",
    "delta_entropy_response_campaign",
    "website_rewrite",
    "cap_escalation_fix",
    "rag_knowledge_sources",
]

# Exact-identifier-heavy queries — the shape a real phase issues when it cites a file/symbol
# rather than describing a feature in prose (query_plan.exact_terms is non-empty for these).
IDENTIFIER_QUERIES = [
    "src/agentic_dynamics/knowledge/retrieval.py retrieve() RRF fusion fallback_mode",
    "tests/test_fleet_guards.py test_neo4j_index_populated_and_group_caught_up_live",
    "kb-neo4j-v1 consumer group pending XPENDING knowledge_text_ft",
]


def _load_spec_questions(names: list[str]) -> dict[str, str]:
    """Re-read each named spec's ``question:`` field from the current tree."""
    found: dict[str, str] = {}
    remaining = set(names)
    for path in sorted((ROOT / "workflows").rglob("*.yaml")) + sorted(
        (ROOT / "experiments" / "definitions").glob("*.yaml")
    ):
        if not remaining:
            break
        try:
            doc = yaml.safe_load(path.read_text())
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        name = doc.get("name")
        if name in remaining and doc.get("question"):
            found[name] = str(doc["question"]).strip()
            remaining.discard(name)
    missing = set(names) - found.keys()
    if missing:
        raise RuntimeError(f"census query specs not found in the current tree: {sorted(missing)}")
    return found


def build_queries() -> list[tuple[str, str]]:
    """Return ``[(label, raw_work_item)]`` — the real query set."""
    specs = _load_spec_questions(SAMPLE_SPEC_NAMES)
    queries = [(f"spec:{name}", specs[name]) for name in SAMPLE_SPEC_NAMES]
    queries += [(f"identifier:{i}", q) for i, q in enumerate(IDENTIFIER_QUERIES)]
    return queries


def run_census(queries: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    """Run ``retrieve()`` over ``queries`` and aggregate leg contribution + fallback modes."""
    from agentic_dynamics.knowledge.augment import default_retrieve_fn
    from agentic_dynamics.knowledge.retrieval import WEIGHTS_VERSION

    queries = queries if queries is not None else build_queries()
    retrieve_fn = default_retrieve_fn()

    fallback_counts: Counter[str] = Counter()
    leg_totals: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []

    for label, raw in queries:
        attempt = retrieve_fn(raw)
        dense_only = lexical_only = fused = 0
        for cand in attempt.candidates:
            has_dense = cand.dense_rank is not None
            has_lexical = cand.lexical_rank is not None
            if has_dense and has_lexical:
                fused += 1
            elif has_dense:
                dense_only += 1
            elif has_lexical:
                lexical_only += 1
        fallback_counts[attempt.fallback_mode] += 1
        leg_totals["dense_only"] += dense_only
        leg_totals["lexical_only"] += lexical_only
        leg_totals["fused"] += fused
        rows.append(
            {
                "label": label,
                "fallback_mode": attempt.fallback_mode,
                "candidates": len(attempt.candidates),
                "dense_only": dense_only,
                "lexical_only": lexical_only,
                "fused": fused,
                "selected_evidence": len(attempt.selected_evidence),
                "latency_ms": attempt.latency_ms,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weights_version": WEIGHTS_VERSION,
        "n_queries": len(queries),
        "fallback_mode_distribution": dict(fallback_counts),
        "leg_contribution_totals": dict(leg_totals),
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="print the raw census dict as JSON")
    args = ap.parse_args()

    result = run_census()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"weights_version: {result['weights_version']}")
        print(f"n_queries: {result['n_queries']}")
        print(f"fallback_mode_distribution: {result['fallback_mode_distribution']}")
        print(f"leg_contribution_totals: {result['leg_contribution_totals']}")
        for row in result["rows"]:
            print(
                f"  {row['label']:40s} fallback={row['fallback_mode']:20s} "
                f"candidates={row['candidates']:3d} dense_only={row['dense_only']:2d} "
                f"lexical_only={row['lexical_only']:2d} fused={row['fused']:2d}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
