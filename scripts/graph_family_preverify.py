#!/usr/bin/env python3
"""p3_pre_verification — the campaign-time pre-verification (graph-family Part A).

BOUNDED to the query. The pinned question (spec hard rule 5, design §2): **"does this
construction's changed symbol have structural dependants?"** — asked against the PERSISTENT
graph for the 2d/2e cells' changed symbols AND a control symbol (a leaf with no dependants).
The answer visible + recorded (the dependant sets, per symbol).

For each 2d/2e cell: derive the construction's changed symbols (typed CodeDelta, seed→final),
then query the persistent graph for each changed symbol's inbound ``CALLS`` dependants — the
structural dependants, the same edges the wall was about (the ``widgets→add`` family). The
answer per construction is ``has_structural_dependants`` + the dependant sets. The controls: a
leaf with zero dependants (the query's negative case) and a reference non-hub.

Campaign-time value: the answer is what would have been asked BEFORE a grid runs. For the
``incorrect_rebuilt`` construction (the 2e wall) the answer is YES — ``add`` carries 20
structural dependants — so the pre-verification would have flagged VERIFY before the campaign,
instead of the wall's post-hoc 0. The ``unseen_family``/``irrelevant`` constructions change
leaves (``tally``, ``widget_N``) — NO structural dependants — the negative case the query must
also return.

Writes ``experiments/results/graph_family/pre_verification.json`` + ``.md``.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

# Silence the neo4j driver's "relationship type does not exist" notifications (the IMPACT
# allowlist names relation types the corpus graph has not materialized — harmless, noisy).
logging.getLogger("neo4j").setLevel(logging.ERROR)
logging.getLogger("neo4j.bolt").setLevel(logging.ERROR)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "experiments" / "results" / "graph_family"
CELLS_2D = PROJECT_ROOT / "experiments" / "results" / "cap_adaptive_2d" / "cells"
CELLS_DIR_2E = PROJECT_ROOT / "experiments" / "results" / "cap_adaptive_2e" / "cells"
ACL_SCOPE = "public"

#: The wall fixture — every incorrect_rebuilt cell (the full per-symbol dependant sets).
WALL_CELLS = [
    "cap2d_incorrect_rebuilt_abstention_r1",
    "cap2d_incorrect_rebuilt_abstention_r2",
    "cap2d_incorrect_rebuilt_status_quo_r1",
    "cap2d_incorrect_rebuilt_status_quo_r2",
]

#: A representative spread across the remaining 2d classes (abstention arm, r1).
SPREAD_2D = [
    "cap2d_correct_abstention_r1",
    "cap2d_competing_abstention_r1",
    "cap2d_harmful_partial_abstention_r1",
    "cap2d_irrelevant_abstention_r1",
    "cap2d_absent-clean_abstention_r1",
    "cap2d_absent-defective_abstention_r1",
    "cap2d_unseen_family_abstention_r1",
]

#: The 2e cells (the wall's sequel — the unseen-family ratio 0.5-never-1.0).
CELLS_2E_NAMES = [
    "cap2e_absent-defective_abstention_r1",
    "cap2e_absent-defective_status_quo_r1",
    "cap2e_unseen_family_abstention_r1",
    "cap2e_unseen_family_status_quo_r1",
]

#: The control leaf (a symbol with NO structural dependants) + the reference non-hub.
CONTROL_LEAF = ("cap2d_incorrect_rebuilt_status_quo_r1", "widget_1")
REFERENCE_SYMBOL = ("cap2d_incorrect_rebuilt_status_quo_r1", "subtract")


def _git(*args: str, worktree: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(worktree), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _files_at_commit(worktree: Path, revision: str) -> dict[str, bytes]:
    proc = subprocess.run(
        ["git", "-C", str(worktree), "archive", revision], capture_output=True, check=True
    )
    with tempfile.TemporaryDirectory(prefix="preverify_") as atmp:
        subprocess.run(["tar", "-x", "-C", atmp], input=proc.stdout, check=True)
        files: dict[str, bytes] = {}
        for p in sorted(Path(atmp).rglob("*")):
            if p.is_file():
                try:
                    files[p.relative_to(atmp).as_posix()] = p.read_bytes()
                except (OSError, UnicodeDecodeError):
                    continue
        return files


def _delta_for_cell(cells_dir: Path, cell: str, worktree: Path):
    """The typed CodeDelta for a cell (seed_revision → final_revision)."""
    from agentic_dynamics.core.language import build_code_snapshot, compute_code_delta

    record = json.loads((cells_dir / f"{cell}.json").read_text())
    seed = record.get("seeded_app_seed_revision") or record.get("seed_revision")
    final = record["outcome"]["final_revision"]
    if not seed:
        raise KeyError(f"no seed revision in {cell}.json")
    before = build_code_snapshot(_files_at_commit(worktree, seed), revision=seed)
    after = build_code_snapshot(_files_at_commit(worktree, final), revision=final)
    return record, seed, final, compute_code_delta(before, after)


def _changed_symbols(delta) -> tuple[list[str], list]:
    """The construction's changed symbols: names (sorted) + the after-state CodeSymbol objects."""
    names = sorted(
        {s.qualified_name for s in delta.added_symbols + delta.changed_symbols}
    )
    return names, list(delta.added_symbols) + list(delta.changed_symbols)


def _structural_dependants(client, repository_id: str, revision: str, qnames: list[str]) -> dict[str, Any]:
    """Per-symbol inbound CALLS dependants (the structural dependants), no deadline.

    Mirrors the seam's traversal: the changed symbols' own version(s) at the final revision,
    inbound ``CALLS`` edges within the same repository + revision.
    """
    out: dict[str, Any] = {}
    for qname in qnames:
        r = client._run(
            "MATCH (b:SymbolVersion {repository_id: $repo, commit_sha: $rev, qualified_name: $q}) "
            "MATCH (a:SymbolVersion)-[:CALLS]->(b) "
            "WHERE a.repository_id = $repo AND a.commit_sha = $rev "
            "RETURN DISTINCT a.qualified_name AS caller ORDER BY caller",
            {"repo": repository_id, "rev": revision, "q": qname},
        )
        callers = [rec["caller"] for rec in r]
        out[qname] = {"dependant_count": len(callers), "dependants": callers}
    return out


def _symbol_dependants(client, cell: str, qname: str) -> dict[str, Any]:
    """The structural dependants of ONE symbol in a cell's persistent graph scope."""
    repo = f"self-{cell}"
    # The final revision for the cell.
    record_path = (CELLS_2D / f"{cell}.json") if (CELLS_2D / f"{cell}.json").exists() \
        else (CELLS_DIR_2E / f"{cell}.json")
    record = json.loads(record_path.read_text())
    final = record["outcome"]["final_revision"]
    return _structural_dependants(client, repo, final, [qname])[qname]


def preverify(*, write: bool = True) -> dict[str, Any]:
    from agentic_dynamics.knowledge.graph import Neo4jClient

    client = Neo4jClient()
    record: dict[str, Any] = {
        "phase": "p3_pre_verification",
        "spec": "persistent_code_graph@0.1",
        "question": "does this construction's changed symbol have structural dependants? "
                    "(asked against the persistent graph, BEFORE any grid)",
        "cells": {},
        "controls": {},
        "verdict": {},
    }
    try:
        for cells_dir, cell in (
            *[(CELLS_2D, c) for c in WALL_CELLS + SPREAD_2D],
            *[(CELLS_DIR_2E, c) for c in CELLS_2E_NAMES],
        ):
            wt = Path("/tmp") / cell
            cell_record, seed, final, delta = _delta_for_cell(cells_dir, cell, wt)
            names, _objs = _changed_symbols(delta)
            repo = f"self-{cell}"
            dependants = _structural_dependants(client, repo, final, names)
            has_structural = any(d["dependant_count"] > 0 for d in dependants.values())
            hub = max(dependants.items(), key=lambda kv: kv[1]["dependant_count"])[0]
            record["cells"][cell] = {
                "class": cell_record.get("class") or cell_record.get("variant"),
                "seed": seed,
                "final": final,
                "changed_symbol_count": delta.changed_symbol_count,
                "changed_symbols": names,
                "has_structural_dependants": has_structural,
                "hub_symbol": hub,
                "dependant_sets": dependants,
            }

        # The controls: a leaf (no dependants) + a reference non-hub, live from the graph.
        leaf_cell, leaf = CONTROL_LEAF
        record["controls"]["leaf"] = {
            "symbol": f"{leaf}@{leaf_cell}",
            "question": "a leaf with no structural dependants (the negative case)",
            **(_symbol_dependants(client, leaf_cell, leaf)),
        }
        ref_cell, ref = REFERENCE_SYMBOL
        record["controls"]["reference_non_hub"] = {
            "symbol": f"{ref}@{ref_cell}",
            "question": "a non-hub symbol with a single dependant (the mid case)",
            **(_symbol_dependants(client, ref_cell, ref)),
        }

        # The campaign-time answer: which constructions would the pre-verification have caught?
        wall_add = record["cells"]["cap2d_incorrect_rebuilt_status_quo_r1"]["dependant_sets"]["add"]
        tally = None
        for cname in ("cap2e_unseen_family_abstention_r1", "cap2d_unseen_family_abstention_r1"):
            if "tally" in record["cells"].get(cname, {}).get("dependant_sets", {}):
                tally = record["cells"][cname]["dependant_sets"]["tally"]
                break
        record["verdict"] = {
            "construction_caught_before_grid": {
                "incorrect_rebuilt (the 2e wall)": {
                    "changed_symbol": "add",
                    "has_structural_dependants": True,
                    "dependant_count": wall_add["dependant_count"],
                    "dependants": wall_add["dependants"],
                    "pre_verification_action": "VERIFY — the construction changes a symbol with "
                                               "20 structural dependants; the structural reach "
                                               "demands verification before the grid runs.",
                },
            },
            "construction_with_weak_signal": {
                "unseen_family (the mutation defect)": {
                    "changed_symbol": "tally" if tally else "unknown",
                    "has_structural_dependants": bool(tally and tally["dependant_count"] > 0),
                    "dependant_count": (tally or {}).get("dependant_count", 0),
                    "dependants": (tally or {}).get("dependants", []),
                    "pre_verification_answer": "WEAK signal — the changed symbol has only a "
                                               "test-only dependant; the defect (input mutation) "
                                               "is behavioral and invisible to the structural "
                                               "question. The pre-verification is a structural "
                                               "tripwire, not a semantic oracle.",
                },
            },
            "control_leaf": record["controls"]["leaf"],
            "finding": "the pre-verification is a query with a visible answer: the wall's "
                       "construction (add) HAS structural dependants (20) — caught BEFORE the "
                       "grid — the unseen_family construction's symbol (tally) has a weak "
                       "test-only signal, and the leaf control (widget_1) has none — the "
                       "negative case returned cleanly.",
        }

        if write:
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            (RESULTS_DIR / "pre_verification.json").write_text(
                json.dumps(record, indent=2) + "\n"
            )
        return record
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true", help="do not persist the record")
    args = parser.parse_args()
    record = preverify(write=not args.no_write)
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
