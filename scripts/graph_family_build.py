#!/usr/bin/env python3
"""p1_build_graph — load the persistent code graph into the live neo4j (graph-family Part A).

BOUNDED to the build. Uses the existing wiring (`code_ingestion.ingest_codebase_graph` →
`graph.load_codebase_graph` for the module-level :CodeModule graph; `graph.populate_versioned_graph`
for the symbol-level :SymbolVersion/:ModuleVersion graph with CALLS edges) to load:

  1. **the framework's own ``src/``** (``src/agentic_dynamics``) — module-level CodeModule graph
     under the ``framework-src`` run.
  2. **the 2d/2e fixture cells' codebases** (the ``incorrect_rebuilt`` worktrees — the wall's
     fixture — plus the other 2d/2e cells found via ``p1_incorrect_rebuilt_probe.json``'s
     paths) — module-level CodeModules AND symbol-level versions (so the ``widgets→add``
     dependant CALLS edges — the wall's edges — land in the persistent graph).
  3. **one story's 5-session arc** (``/tmp/story_c55b0cf5d2e9``, notification_service clean) —
     per-commit CodeSnapshots loaded as Revisions + SUPERSEDES chains, with the structural
     delta per commit (added/removed symbols, coupling drift, new hub nodes) recorded.

Records the node/edge counts, the sample structural edges (INCLUDING the widgets→add
dependants), and the snapshot deltas under ``experiments/results/graph_family/``.

The graph is additive — nothing is deleted. The neo4j service is
``bolt://localhost:7687`` (FINOPS_NEO4J_URI override).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "experiments" / "results" / "graph_family"

FRAMEWORK_SRC = PROJECT_ROOT / "src" / "agentic_dynamics"
STORY_WORKTREE = Path("/tmp/story_c55b0cf5d2e9")
STORY_REPOSITORY_ID = "self-story_c55b0cf5d2e9"
ACL_SCOPE = "public"

#: The 2d/2e fixture cells (the wall's cells) — the codebases the probe's paths point at.
FIXTURE_CELLS = [
    "cap2d_incorrect_rebuilt_abstention_r1",
    "cap2d_incorrect_rebuilt_abstention_r2",
    "cap2d_incorrect_rebuilt_status_quo_r1",
    "cap2d_incorrect_rebuilt_status_quo_r2",
    "cap2d_probe_incorrect_rebuilt",
    "cap2e_absent-defective_abstention_r1",
    "cap2e_absent-defective_status_quo_r1",
    "cap2e_unseen_family_abstention_r1",
    "cap2e_unseen_family_abstention_r2",
    "cap2e_unseen_family_status_quo_r1",
    "cap2e_unseen_family_status_quo_r2",
    "cap2e_probe_unseen_family",
]

GIT_SHOW_TIMEOUT = 60


# ── git helpers ─────────────────────────────────────────────────


def _git(*args: str, worktree: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(worktree), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=GIT_SHOW_TIMEOUT,
    ).stdout.strip()


def _files_at_commit(worktree: Path, revision: str) -> dict[str, bytes]:
    """Materialize a commit's tree as ``{repo-relative path: bytes}`` (read-only, via git archive)."""
    files: dict[str, bytes] = {}
    proc = subprocess.run(
        ["git", "-C", str(worktree), "archive", revision],
        capture_output=True,
        check=True,
        timeout=GIT_SHOW_TIMEOUT,
    )
    with tempfile.TemporaryDirectory(prefix="graph_family_archive_") as atmp:
            subprocess.run(
                ["tar", "-x", "-C", atmp],
                input=proc.stdout,
                check=True,
                timeout=GIT_SHOW_TIMEOUT,
            )
            for p in sorted(Path(atmp).rglob("*")):
                if p.is_file():
                    try:
                        files[p.relative_to(atmp).as_posix()] = p.read_bytes()
                    except (OSError, UnicodeDecodeError):
                        continue
    return files


def _head_sha(worktree: Path) -> str:
    return _git("rev-parse", "HEAD", worktree=worktree)


# ── graph loading ───────────────────────────────────────────────


def _load_module_graph(client, repo_root: Path, *, worktree_name: str) -> dict[str, int]:
    """The module-level :CodeModule graph via the mandated wiring (ingest_codebase_graph)."""
    from agentic_dynamics.knowledge.code_ingestion import ingest_codebase_graph

    return ingest_codebase_graph(client, repo_root, worktree_name=worktree_name)


def _load_symbol_graph(
    client, files: dict[str, bytes], *, revision: str, repository_id: str
) -> dict[str, int]:
    """The symbol-level :SymbolVersion graph (CALLS/IMPORTS/SUPERSEDES) for one revision."""
    from agentic_dynamics.core.language import build_code_snapshot

    snapshot = build_code_snapshot(files, revision=revision)
    counts = client.populate_versioned_graph(
        snapshot,
        revision=revision,
        repository_id=repository_id,
        acl_scope=ACL_SCOPE,
    )
    return counts, snapshot


# ── snapshot shape / delta (the structural shape of a revision) ──


def _call_edges(snapshot) -> list[tuple[str, str]]:
    """Name-resolved CALLS edges within one snapshot (same rule as populate_versioned_graph)."""
    qnames = {s.qualified_name for path in snapshot.files for s in snapshot.files[path]}
    edges: set[tuple[str, str]] = set()
    for path in sorted(snapshot.files):
        for sym in snapshot.files[path]:
            for callee in sym.calls:
                if callee in qnames and callee != sym.qualified_name:
                    edges.add((sym.qualified_name, callee))
    return sorted(edges)


def _shape(snapshot, files: dict[str, bytes]) -> dict[str, Any]:
    """The structural shape of one revision: counts, call edges, hub nodes, coupling drift."""
    symbols = snapshot.all_symbols
    edges = _call_edges(snapshot)
    in_degree: dict[str, int] = {}
    for _, callee in edges:
        in_degree[callee] = in_degree.get(callee, 0) + 1
    hubs = sorted(in_degree.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    n = len(symbols)
    return {
        "revision": snapshot.revision,
        "language": snapshot.language,
        "module_count": len(snapshot.files),
        "file_count": len(files),
        "symbol_count": n,
        "call_edge_count": len(edges),
        "coupling": round(len(edges) / (n * (n - 1)), 6) if n > 1 else 0.0,
        "hub_nodes": [{"symbol": s, "in_degree": d} for s, d in hubs],
    }


def _story_delta(before, after) -> dict[str, Any]:
    """The structural delta between two consecutive story revisions (typed CodeDelta)."""
    from agentic_dynamics.core.language import compute_code_delta

    d = compute_code_delta(before, after)
    return {
        "added_symbols": [s.qualified_name for s in d.added_symbols],
        "removed_symbols": [s.qualified_name for s in d.removed_symbols],
        "changed_symbols": [s.qualified_name for s in d.changed_symbols],
        "added_files": d.added_files,
        "removed_files": d.removed_files,
        "added_call_edges": [list(e) for e in d.added_call_edges],
        "removed_call_edges": [list(e) for e in d.removed_call_edges],
        "changed_symbol_count": d.changed_symbol_count,
    }


# ── the p1 build ────────────────────────────────────────────────


def build(*, write: bool = True, story: bool = True) -> dict[str, Any]:
    from agentic_dynamics.knowledge.graph import Neo4jClient

    client = Neo4jClient()
    record: dict[str, Any] = {
        "phase": "p1_build_graph",
        "spec": "persistent_code_graph@0.1",
        "source_revision": _head_sha(PROJECT_ROOT),
        "graph_service": "bolt://localhost:7687 (FINOPS_NEO4J_URI)",
        "framework_src": {},
        "fixture_cells": {},
        "story_arc": {},
        "wall_edges": {},
        "graph_counts": {},
    }
    try:
        client.create_knowledge_schema()
        client.create_schema()

        # 1. the framework's own src/ (module-level CodeModule graph)
        fw = _load_module_graph(client, FRAMEWORK_SRC, worktree_name="framework-src")
        record["framework_src"] = {
            "worktree_name": "framework-src",
            "codebase": str(FRAMEWORK_SRC.relative_to(PROJECT_ROOT)),
            **fw,
        }

        # 2. the 2d/2e fixture cells' codebases (module-level + symbol-level versions)
        for cell in FIXTURE_CELLS:
            wt = Path("/tmp") / cell
            if not wt.exists():
                record["fixture_cells"][cell] = {"status": "missing"}
                continue
            revision = _head_sha(wt)
            files = _files_at_commit(wt, revision)
            mod = _load_module_graph(client, wt, worktree_name=f"fixture-{cell}")
            sym, snapshot = _load_symbol_graph(
                client, files, revision=revision, repository_id=f"self-{cell}"
            )
            record["fixture_cells"][cell] = {
                "worktree": str(wt),
                "revision": revision,
                "module_graph": mod,
                "symbol_graph": sym,
                "shape": _shape(snapshot, files),
            }

        # 3. one story's 5-session arc (cross-commit evolution)
        if story:
            record["story_arc"] = _build_story_arc(client)

        # 4. the wall's edges — the widgets->add dependants, live from the graph
        record["wall_edges"] = _wall_edges(client)

        # 5. the post-build graph counts
        record["graph_counts"] = _graph_counts(client)

        # 6. persist the record
        if write:
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            (RESULTS_DIR / "p1_build_graph.json").write_text(
                json.dumps(record, indent=2) + "\n"
            )
        return record
    finally:
        client.close()


def _build_story_arc(client) -> dict[str, Any]:
    """Load the story's 6 commits as Revisions + SUPERSEDES chains; record the delta shape."""
    from agentic_dynamics.core.language import build_code_snapshot

    wt = STORY_WORKTREE
    commits: list[str] = []
    log = _git("log", "--format=%H %s", worktree=wt)
    for line in log.splitlines():
        sha, _, msg = line.partition(" ")
        commits.append(sha)

    snapshots: dict[str, Any] = {}
    shapes: list[dict[str, Any]] = []
    deltas: list[dict[str, Any]] = []
    prev_snapshot = None
    for sha in reversed(commits):
        files = _files_at_commit(wt, sha)
        snapshot = build_code_snapshot(files, revision=sha)
        snapshots[sha] = snapshot
        shape = _shape(snapshot, files)
        shape["commit_message"] = _git("log", "-1", "--format=%s", sha, worktree=wt)
        shapes.append(shape)
        if prev_snapshot is not None:
            d = _story_delta(prev_snapshot, snapshot)
            d["from_revision"] = prev_snapshot.revision
            d["to_revision"] = snapshot.revision
            d["commit_message"] = shape["commit_message"]
            deltas.append(d)
        prev_snapshot = snapshot

        counts = client.populate_versioned_graph(
            snapshot,
            revision=sha,
            repository_id=STORY_REPOSITORY_ID,
            acl_scope=ACL_SCOPE,
        )
        shape["populate_counts"] = counts

    # Post-load graph state for the story's own revisions.
    return {
        "worktree": str(wt),
        "story_id": "c55b0cf5d2e9",
        "repository_id": STORY_REPOSITORY_ID,
        "commit_count": len(commits),
        "commits": [
            {"sha": sha, "short": _git("rev-parse", "--short", sha, worktree=wt),
             "message": _git("log", "-1", "--format=%s", sha, worktree=wt)}
            for sha in reversed(commits)
        ],
        "snapshot_shapes": shapes,
        "deltas": deltas,
        "story_graph": {
            "revisions": len(commits),
            "symbol_versions": sum(s["populate_counts"]["symbol_versions"] for s in shapes),
            "supersedes": sum(s["populate_counts"]["supersedes"] for s in shapes),
            "calls": sum(s["populate_counts"]["calls"] for s in shapes),
        },
    }


def _wall_edges(client) -> dict[str, Any]:
    """The wall's edges, live from the persistent graph: the widgets→add dependants."""
    wall = {"cells_with_edges": {}, "sample": []}
    for cell in FIXTURE_CELLS:
        repo = f"self-{cell}"
        r = client._run(
            "MATCH (a:SymbolVersion)-[:CALLS]->(b:SymbolVersion) "
            "WHERE b.qualified_name = $q AND a.repository_id = $repo "
            "RETURN DISTINCT a.qualified_name AS caller, b.qualified_name AS callee "
            "ORDER BY caller",
            {"q": "add", "repo": repo},
        )
        callers = [rec["caller"] for rec in r]
        if callers:
            wall["cells_with_edges"][cell] = {
                "dependant_count": len(callers),
                "dependants": callers,
            }
    r = client._run(
        "MATCH (a:SymbolVersion)-[:CALLS]->(b:SymbolVersion) "
        "WHERE b.qualified_name = $q AND a.repository_id = $repo "
        "RETURN DISTINCT a.qualified_name AS caller ORDER BY caller",
        {"q": "add", "repo": "self-cap2d_incorrect_rebuilt_status_quo_r1"},
    )
    wall["sample"] = [
        {"caller": rec["caller"], "callee": "add"}
        for rec in r
    ]
    return wall


def _graph_counts(client) -> dict[str, Any]:
    counts: dict[str, Any] = {}
    for label in ("CodeModule", "ModuleVersion", "SymbolVersion", "Revision", "Knowledge"):
        counts[f"{label}_nodes"] = client._run(
            f"MATCH (n:{label}) RETURN count(n) AS c"
        ).single()["c"]
    for rel in ("IMPORTS", "IMPORTED_BY", "TOUCHED", "CALLS", "CONTAINS", "DEFINES",
                "SUPERSEDES", "TESTED_BY"):
        counts[f"{rel}_rels"] = client._run(
            f"MATCH ()-[r:{rel}]->() RETURN count(r) AS c"
        ).single()["c"]
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true", help="do not persist the record")
    parser.add_argument("--no-story", action="store_true", help="skip the story arc")
    args = parser.parse_args()
    record = build(write=not args.no_write, story=not args.no_story)
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
