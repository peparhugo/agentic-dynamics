"""Given a scope, read the knowledge base — the reader verb (the missing read path).

The 2026-09-21 retrieval audit (``docs/reviews/retrieval_audit.md``) measured the gap this
verb closes: ``registry query`` filters metadata only (no text search), and the ranked
retrieval pipeline (dense + lexical) was reachable only in-process — so a step holding a
scope had no documented way to READ the KB. This verb is the thin reader over the existing
engine:

* default: the ranked pipeline (``retrieval.retrieve`` over the Neo4j vector + full-text
  legs) with the scope's exact filters, printing what a step would retrieve;
* ``--contains PHRASE``: a deterministic, service-free substring scan over the durable
  artifacts (``experiments/results/kb/<id>.json`` selected via ``registry_index.jsonl``);
  the ranked path falls back to it automatically when the services are unreachable.

Scope semantics (the cell rule): ``--scope`` defaults to ``self-<cwd name>`` (FINOPS_CELL_ID
overrides the name); a non-empty explicit ``--scope`` is the SHARED-scope override; ``--acl``
defaults to the scope value. The scope pre-filter is an exact match, so zero hits usually mean
"wrong scope", not "empty KB".

Invocation:
    python3 scripts/kb_read.py --query "cache hit rate" [--scope agentic-dynamics]
        [--acl agentic-dynamics] [--type finding] [--limit 8] [--json] [--contains]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

KB_DIR = REPO / "experiments" / "results" / "kb"
REGISTRY = REPO / "experiments" / "results" / "registry_index.jsonl"


def _default_scope() -> str:
    cell = os.environ.get("FINOPS_CELL_ID") or Path.cwd().name
    return f"self-{cell}"


def _ranked(args: argparse.Namespace) -> list[dict] | None:
    """Ranked retrieval via the existing pipeline; None when the services are unreachable."""
    try:
        from agentic_dynamics.knowledge.graph import Neo4jClient
        from agentic_dynamics.knowledge.neo4j_vectors import Neo4jVectorStore
        from agentic_dynamics.knowledge.retrieval import retrieve

        client = Neo4jClient()
        dense = Neo4jVectorStore(client=client)
        res = retrieve(
            args.query,
            dense_store=dense,
            graph_client=client,
            repository_id=args.scope,
            acl_scope=args.acl,
            top_k=max(args.limit, 1),
        )
    except Exception as exc:  # services down, optional deps missing, ...
        print(
            f"[kb-read] ranked retrieval unavailable ({type(exc).__name__}: {exc}) — "
            "falling back to the deterministic scan",
            file=sys.stderr,
        )
        return None
    out: list[dict] = []
    for cand in res.candidates or []:
        d = cand if isinstance(cand, dict) else getattr(cand, "__dict__", {})
        if args.type and d.get("source_type") != args.type:
            continue
        out.append(
            {
                "id": d.get("id"),
                "source_type": d.get("source_type"),
                "authority": d.get("authority"),
                "evidence_class": d.get("evidence_class"),
                "locator": d.get("locator"),
                "text": str(d.get("text") or "")[:400],
                "mode": "ranked",
            }
        )
    return out[: args.limit]


def _contains(args: argparse.Namespace) -> list[dict]:
    """Deterministic substring scan over the durable artifacts (no services required)."""
    needle = args.query.casefold()
    out: list[dict] = []
    # Newest-first: the registry is append-only chronological, and a reader usually wants
    # recent knowledge — this also keeps a common read cheap on a large corpus.
    lines = REGISTRY.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except Exception:
            continue
        if args.type and row.get("source_type") != args.type:
            continue
        if args.lifecycle and row.get("lifecycle_state") != args.lifecycle:
            continue
        kid = str(row.get("knowledge_id") or "")
        if not kid:
            continue
        path = KB_DIR / f"{kid}.json"
        if not path.is_file():
            continue
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        text = str(rec.get("text") or "")
        i = text.casefold().find(needle)
        if i < 0:
            continue
        lo = max(0, i - 80)
        out.append(
            {
                "id": kid,
                "source_type": rec.get("source_type"),
                "authority": rec.get("authority"),
                "evidence_class": rec.get("evidence_class"),
                "locator": rec.get("logical_locator"),
                "text": text[lo : i + len(needle) + 200].replace("\n", " "),
                "mode": "contains",
            }
        )
        if len(out) >= args.limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Read the knowledge base for a scope.")
    ap.add_argument("--query", required=True, help="the query / phrase to read for")
    ap.add_argument(
        "--scope",
        default="",
        help="repository_id (default: self-<cwd>; a non-empty value = shared-scope override)",
    )
    ap.add_argument("--acl", default="", help="acl_scope (default: the scope value)")
    ap.add_argument("--type", default="", help="filter by source_type (finding, decision, ...)")
    ap.add_argument(
        "--lifecycle",
        default="current",
        help="lifecycle filter for --contains (default: current; '' disables)",
    )
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument(
        "--contains", action="store_true", help="deterministic artifact scan (no services)"
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    args.scope = args.scope or _default_scope()
    args.acl = args.acl or args.scope

    hits = None if args.contains else _ranked(args)
    if hits is None:
        hits = _contains(args)
        mode = "contains"
    else:
        mode = "ranked"

    if args.json:
        print(
            json.dumps(
                {
                    "scope": args.scope,
                    "acl": args.acl,
                    "query": args.query,
                    "mode": mode,
                    "hits": hits,
                },
                indent=2,
            )
        )
    else:
        print(
            f"[kb-read] scope={args.scope} acl={args.acl} query={args.query!r} "
            f"mode={mode} hits={len(hits)}"
        )
        for h in hits:
            print(f"  {str(h['id'])[:16]} | {h['source_type']} | {h['authority']} | {h['locator']}")
            print(f"      {h['text'][:220]}")
        if not hits:
            print(
                "  (zero hits — check the scope: the scope pre-filter is an exact match, so a "
                "mismatched scope returns nothing. See docs/reviews/retrieval_audit.md)"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
