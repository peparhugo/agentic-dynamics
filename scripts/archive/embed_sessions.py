#!/usr/bin/env python3
"""Index all experiment session.jsonl reasoning steps into ChromaDB.

Extracts individual reasoning steps from each session, embeds them via
bge-m3, and stores in ChromaDB with full metadata. Enables step-level
comparison across sessions — the foundation for reasoning divergence
and cross-model analysis.

Usage:
  python scripts/embed_sessions.py                 # index all steps
  python scripts/embed_sessions.py --limit 20       # index first 20 sessions
  python scripts/embed_sessions.py --search "WebSocket"  # search
  python scripts/embed_sessions.py --delete          # clear collection
  python scripts/embed_sessions.py --stats           # show counts
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401


from agentic_dynamics.knowledge.embeddings import ChromaStore, extract_session_steps
from agentic_dynamics.measurement.perturb import perturbation_class_for

SUMMARY_PATH = PROJECT_ROOT / "experiments" / "results" / "_results_summary.json"

KNOWN_OPERATORS = {
    "inject_alien_vocab", "shift_framing", "swap_modality", "parse_structural_shift",
    "remove_critical_constraint", "invert_constraint", "inject_phantom_success",
    "inject_competing_goal", "inject_false_premises", "inject_recursion",
}


def _extract_operator_detail(experiment_name: str) -> dict:
    """Extract granular operator name from experiment field.
    E.g. 'inject_alien_vocab_s0.5' → {operator: 'inject_alien_vocab', class: 'process_perturbation'}
    """
    if not experiment_name:
        return {}
    base = experiment_name
    for suffix in ("_s0.5", "_r1", "_r2", "_r3"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    if base in KNOWN_OPERATORS:
        return {
            "operator": base,
            "perturbation_class": perturbation_class_for(base),
        }
    if experiment_name.startswith("exp_"):
        return {}
    return {"operator": "baseline", "perturbation_class": ""}


def _get_session_metadata(session_dir: Path) -> dict:
    if not SUMMARY_PATH.exists():
        return {}
    data = json.loads(SUMMARY_PATH.read_text())
    for entry in data.get("entries", []):
        if entry.get("worktree_name") == session_dir.name:
            exp = entry.get("experiment", "")
            op_detail = _extract_operator_detail(exp)
            return {
                "model": entry.get("model", ""),
                "experiment": exp,
                "operator": op_detail.get("operator", entry.get("operator", "")),
                "perturbation_class": op_detail.get("perturbation_class", entry.get("perturbation_class", "")),
                "strategy": entry.get("strategy", ""),
                "correctness": entry.get("correctness", 0),
                "cost_usd": entry.get("cost", 0),
                "tokens_total": entry.get("tokens", 0),
                "code_lines": entry.get("code_lines", 0),
                "silent_mode": entry.get("silent_mode", ""),
            }
    return {}


def find_sessions(reports_dir: Path) -> list[Path]:
    return sorted(reports_dir.glob("*/session.jsonl"))


def main():
    parser = argparse.ArgumentParser(description="Index reasoning steps in ChromaDB")
    parser.add_argument("--limit", type=int, default=0, help="Limit sessions to index")
    parser.add_argument("--search", type=str, help="Search query after indexing")
    parser.add_argument("--top-k", type=int, default=10, help="Results for search")
    parser.add_argument("--delete", action="store_true", help="Delete collection first")
    parser.add_argument("--model", type=str, help="Filter search by model")
    parser.add_argument("--stats", action="store_true", help="Show collection stats")
    args = parser.parse_args()

    reports_dir = PROJECT_ROOT / "experiments" / "results" / "reports"
    store = ChromaStore()

    if args.delete:
        store.delete_all()
        print("Collection deleted.")
        return

    if args.stats:
        results = store.collection.get(include=["metadatas"])
        print(f"Total documents: {store.count()}")
        if results.get("metadatas"):
            sources = {}
            for m in results["metadatas"]:
                src = m.get("embedding_source", "?")
                sources[src] = sources.get(src, 0) + 1
            for src, count in sorted(sources.items()):
                print(f"  {src}: {count}")
        return

    if args.search:
        results = store.search(args.search, top_k=args.top_k)
        print(f'\nSearch results for: "{args.search}"')
        print(f"Found {len(results)} results:\n")
        for i, hit in enumerate(results):
            meta = hit["metadata"]
            print(f"{i+1}. [{meta.get('strategy','?')}] {meta.get('model','?')} "
                  f"step={meta.get('step_index','?')}")
            print(f"   Session: {meta.get('session_id','?')}")
            print(f"   Tool: {meta.get('tool_after','?')}")
            print(f"   Experiment: {meta.get('experiment','?')}")
            print(f"   Distance: {hit['distance']:.4f}")
            print(f"   Preview: {hit['document'][:150]}...")
            print()
        return

    sessions = find_sessions(reports_dir)
    if args.limit:
        sessions = sessions[:args.limit]

    print(f"Indexing {len(sessions)} sessions at step level...")
    total_steps = 0
    sessions_with_steps = 0

    for i, session_path in enumerate(sessions):
        session_id = session_path.parent.name
        steps = extract_session_steps(session_path)
        if not steps:
            continue

        meta = {"session_id": session_id}
        meta.update(_get_session_metadata(session_path.parent))

        indexed = store.index_session_steps(session_id, steps, meta)
        total_steps += indexed
        sessions_with_steps += 1

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(sessions)} sessions, {total_steps} steps indexed...",
                  flush=True)

    print(f"\nDone. Indexed {total_steps} steps across {sessions_with_steps} sessions.")
    print(f"Collection size: {store.count()} documents.")


if __name__ == "__main__":
    main()
