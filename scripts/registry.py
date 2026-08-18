#!/usr/bin/env python3
"""registry.py — read-only CLI surface over the canonical-state registry.

Canonical-state round 2, plan step 16 (``docs/canonical_state_r2_plan.md``) / design §10
(``docs/canonical_state_r2_design.md``). Three subcommands, all GET-equivalent — nothing
here ever calls ``send_input``/``interrupt`` or touches ``OpenCodeClient``, matching the
flag-only rail's existing invariant unchanged by this round::

    python scripts/registry.py show <id>
        # id tried in this order: logical_locator (story_id | session_id | cell_id |
        # attempt_id — the SAME underlying KnowledgeRecord field across every
        # source_type, see docs/canonical_state_r2_design.md §3's identity table) ->
        # entity_id (exact) -> knowledge_id (prefix). First non-empty match wins; more
        # than one candidate at any stage prints all of them rather than guessing. For
        # an actuation record, additionally follows `causes` and prints the justifying
        # observation inline (design §10 / §5a) — "why did the system decide to act"
        # stays a one-hop lookup even though nothing constructs an actuation record
        # today (see src/instrument/actuation_ingestion.py's module docstring).

    python scripts/registry.py query [--record-type TYPE] [--lifecycle STATE] [--since DATE]
        # Filtered listing over experiments/data_manifest.json's `registry` array — the
        # compacted output of generate_manifest.py's _compact_registry_index (plan step
        # 15). Zero external dependency: this command never touches Redis or Neo4j,
        # matching /api/flags' existing file-fallback philosophy (admin/server.py).

    python scripts/registry.py lineage <entity_id> [--live]
        # The registry array is ALREADY compacted to one (current) row per entity_id —
        # that's the whole point of step 15's compaction — so a supersedes CHAIN cannot
        # be reconstructed from the manifest alone. Only --live (a real Neo4j query
        # walking the -[:SUPERSEDES]-> edges scripts/kb_worker.py's kb-neo4j-v1 handler
        # actually writes, per plan step 8) resolves the full chain. Without --live,
        # this prints the one-hop view the manifest alone can offer (this entity's own
        # `supersedes`/`causes` pointers) and says so explicitly, rather than silently
        # under-reporting a chain it cannot see. Note: design §10 also names
        # CLEARED_BY/REPLACED_BY cross-entity edges — as of this round nothing in this
        # codebase writes either edge type (confirmed by search), so --live here walks
        # SUPERSEDES only; extending to the other two edge types is future work once a
        # producer actually creates them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

#: Where generate_manifest.py (plan step 15) writes the compacted registry array.
DATA_MANIFEST_PATH = PROJECT_ROOT / "experiments" / "data_manifest.json"

#: The 8 source_type values this round's registry recognizes (design §2's table) — "code"/
#: "report"/"policy"/"finding" (round-1 KB source types, pre-dating this registry) are
#: deliberately excluded from this CLI's --record-type choices; they are not part of the
#: observation/actuation family this surface was built to inspect.
RECORD_TYPES = (
    "story", "review", "ledger_job", "ledger_attempt",
    "observation", "flag", "meta_session", "actuation",
)

#: index-only, computed states (design §6) — see this module's docstring on `lineage` for
#: why "superseded"/"tombstoned" resolution is not yet wired end-to-end in this codebase;
#: `query --lifecycle` filters on whatever value each row actually carries today (always
#: "current", per kb_worker.py's kb-registry-v1 handler — see its own docstring).
LIFECYCLE_STATES = ("current", "superseded", "tombstoned")


# ── Loading the compacted registry ──────────────────────────────


def load_registry(manifest_path: Path = DATA_MANIFEST_PATH) -> list[dict[str, Any]]:
    """Return the manifest's ``registry`` array, or ``[]`` when it's absent/unreadable.

    Matches ``/api/flags``' file-fallback philosophy: a missing manifest (i.e.
    ``generate_manifest.py`` was never run) is not an error here — every subcommand
    degrades to "no rows" rather than raising, since this is a read-only inspection
    tool, not a pipeline step with a hard dependency on the manifest existing.
    """
    if not manifest_path.exists():
        return []
    try:
        manifest = json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    return manifest.get("registry") or []


# ── show ──────────────────────────────────────────────────────────


def _find_by_locator(rows: list[dict], target: str) -> list[dict]:
    return [r for r in rows if r.get("logical_locator") == target]


def _find_by_entity_id(rows: list[dict], target: str) -> list[dict]:
    return [r for r in rows if r.get("entity_id") == target]


def _find_by_knowledge_id_prefix(rows: list[dict], target: str) -> list[dict]:
    return [r for r in rows if str(r.get("knowledge_id", "")).startswith(target)]


def resolve_show(rows: list[dict], id_: str) -> tuple[str, list[dict]]:
    """Resolve one ``show <id>`` query against ``rows``.

    Returns ``(stage, candidates)`` where ``stage`` names which lookup matched
    (``"logical_locator"`` | ``"entity_id"`` | ``"knowledge_id_prefix"`` | ``"none"``),
    tried in that documented order — first non-empty match wins. Exposed as its own
    function (rather than inlined into :func:`cmd_show`) so :func:`cmd_show` can reuse it
    unchanged to resolve an actuation record's ``causes`` citation.
    """
    by_locator = _find_by_locator(rows, id_)
    if by_locator:
        return "logical_locator", by_locator
    by_entity = _find_by_entity_id(rows, id_)
    if by_entity:
        return "entity_id", by_entity
    by_prefix = _find_by_knowledge_id_prefix(rows, id_)
    if by_prefix:
        return "knowledge_id_prefix", by_prefix
    return "none", []


def _format_row(row: dict, *, indent: str = "") -> str:
    lines = [
        f"{indent}knowledge_id     {row.get('knowledge_id')}",
        f"{indent}entity_id        {row.get('entity_id')}",
        f"{indent}source_type      {row.get('source_type')}",
        f"{indent}logical_locator  {row.get('logical_locator')}",
        f"{indent}lifecycle_state  {row.get('lifecycle_state')}",
        f"{indent}observed_at      {row.get('observed_at')}",
        f"{indent}indexed_at       {row.get('indexed_at')}",
    ]
    if row.get("supersedes"):
        lines.append(f"{indent}supersedes       {row.get('supersedes')}")
    if row.get("causes"):
        lines.append(f"{indent}causes           {row.get('causes')}")
    return "\n".join(lines)


def cmd_show(args: argparse.Namespace, rows: list[dict]) -> int:
    stage, candidates = resolve_show(rows, args.id)
    if stage == "none":
        print(f"no registry entry matches {args.id!r}")
        return 1
    if len(candidates) > 1:
        print(f"ambiguous — {len(candidates)} candidates matched via {stage}:\n")
        for row in candidates:
            print(_format_row(row, indent="  "))
            print()
        return 0

    row = candidates[0]
    print(f"matched via {stage}:")
    print(_format_row(row))

    # design §10 / §5a: for an actuation record, follow `causes` and print the
    # justifying observation inline.
    if row.get("source_type") == "actuation" and row.get("causes"):
        causes_stage, causes_candidates = resolve_show(rows, row["causes"])
        print("\ncauses (the justifying observation):")
        if causes_stage == "none":
            print(f"  {row['causes']} — not found in the registry (unresolved citation)")
        else:
            for candidate in causes_candidates:
                print(_format_row(candidate, indent="  "))
    return 0


# ── query ─────────────────────────────────────────────────────────


def cmd_query(args: argparse.Namespace, rows: list[dict]) -> int:
    filtered = rows
    if args.record_type:
        filtered = [r for r in filtered if r.get("source_type") == args.record_type]
    if args.lifecycle:
        filtered = [r for r in filtered if r.get("lifecycle_state") == args.lifecycle]
    if args.since:
        # observed_at is a canonical ISO-8601 UTC timestamp throughout this package
        # (knowledge.py's KnowledgeRecord.observed_at), so a plain string comparison
        # sorts correctly against another ISO-8601 string without parsing either side.
        filtered = [r for r in filtered if str(r.get("observed_at") or "") >= args.since]

    for row in filtered:
        print(
            f"{str(row.get('knowledge_id', ''))[:12]:<12}  [{row.get('source_type', ''):<14}]  "
            f"{row.get('lifecycle_state', ''):<10}  {row.get('observed_at', ''):<26}  "
            f"{row.get('logical_locator', '')}"
        )
    print(f"\n{len(filtered)} record(s)")
    return 0


# ── lineage ──────────────────────────────────────────────────────


def resolve_lineage_live(client: Any, entity_id: str) -> list[dict[str, Any]]:
    """Walk the ``-[:SUPERSEDES]->*`` chain for ``entity_id`` via a Neo4j client.

    ``client`` is duck-typed (any object exposing ``._run(query, params)`` returning an
    iterable of row-like objects — matches ``instrument.graph.Neo4jClient``'s own
    convention), so this is testable with a store double and never requires a live
    connection, mirroring every other producer/consumer in this package.
    """
    result = client._run(
        "MATCH (k:Knowledge {entity_id: $eid}) "
        "OPTIONAL MATCH path = (k)-[:SUPERSEDES*0..]->(prev:Knowledge) "
        "UNWIND (CASE WHEN path IS NULL THEN [k] ELSE nodes(path) END) AS n "
        "RETURN DISTINCT n.knowledge_id AS knowledge_id, n.entity_id AS entity_id, "
        "n.source_type AS source_type, n.supersedes AS supersedes, n.causes AS causes",
        {"eid": entity_id},
    )
    return [dict(row) for row in result]


def cmd_lineage(args: argparse.Namespace, rows: list[dict]) -> int:
    matches = _find_by_entity_id(rows, args.entity_id)
    if not matches:
        print(f"no registry entry for entity_id {args.entity_id!r}")
        return 1
    current = matches[0]

    if not args.live:
        print(
            "one-hop view only (pass --live for the full SUPERSEDES chain via Neo4j — "
            "the compacted registry array keeps only the current row per entity_id):\n"
        )
        print(_format_row(current))
        return 0

    from instrument.graph import Neo4jClient

    client = Neo4jClient()
    try:
        chain = resolve_lineage_live(client, args.entity_id)
    finally:
        client.close()

    print(f"SUPERSEDES chain for entity_id {args.entity_id} ({len(chain)} version(s)):")
    for node in chain:
        print(
            f"  {str(node.get('knowledge_id', ''))[:12]:<12}  [{node.get('source_type')}]"
            f"  supersedes={node.get('supersedes')}  causes={node.get('causes')}"
        )
    return 0


# ── CLI ──────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect the canonical-state registry (read-only)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_show = sub.add_parser("show", help="look up one registry entry by story_id/session_id/cell_id/entity_id/knowledge_id-prefix")
    p_show.add_argument("id")

    p_query = sub.add_parser("query", help="filtered listing over the registry")
    p_query.add_argument("--record-type", choices=RECORD_TYPES, default=None)
    p_query.add_argument("--lifecycle", choices=LIFECYCLE_STATES, default=None)
    p_query.add_argument("--since", default=None, help="ISO-8601 date/time lower bound on observed_at")

    p_lineage = sub.add_parser("lineage", help="supersedes chain for one entity_id")
    p_lineage.add_argument("entity_id")
    p_lineage.add_argument("--live", action="store_true", help="query Neo4j for the full SUPERSEDES chain")

    args = parser.parse_args(argv)
    # Read DATA_MANIFEST_PATH from the module namespace at call time (not as
    # load_registry's default parameter, which would bind the value once at import
    # time) — this is what lets tests monkeypatch registry.DATA_MANIFEST_PATH and have
    # main() actually honor the override.
    rows = load_registry(DATA_MANIFEST_PATH)

    if args.command == "show":
        return cmd_show(args, rows)
    if args.command == "query":
        return cmd_query(args, rows)
    if args.command == "lineage":
        return cmd_lineage(args, rows)
    parser.error(f"unknown command {args.command!r}")  # pragma: no cover — argparse enforces choices
    return 2


if __name__ == "__main__":
    sys.exit(main())
