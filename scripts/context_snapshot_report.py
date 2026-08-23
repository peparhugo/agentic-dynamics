#!/usr/bin/env python3
"""context_snapshot_report.py — CAP I4's gate: measure snapshot admissibility over a campaign.

Design §9 I4's gate: "snapshot admissibility rate and unknown/stale/conflict rates measured
over a real campaign." Read-only, no external dependency: this reads the SAME compacted
registry ``scripts/registry.py`` already exposes (``experiments/data_manifest.json``'s
``registry`` array, ``--record-type context_snapshot`` is already a valid choice there — the
``source_type`` is derived automatically from ``knowledge.SOURCE_TYPES``) and, for each row, the
durable per-record artifact (``KB_ARTIFACT_DIR/<knowledge_id>.json``) written by
``context_compiler.record_snapshot`` — the payload ``context_compiler.snapshot_payload`` shaped.

    python scripts/context_snapshot_report.py                    # human-readable summary
    python scripts/context_snapshot_report.py --json              # machine-readable

Nothing here writes anything; it is a report over what ``make_snapshotting_router`` (or a test
harness) has already recorded. Zero rows is not an error — it means the seam has not been
enabled for any run yet (I4 ships the mechanism; enabling it for a real campaign is a separate,
explicit operator decision — see ``scripts/run_workflow.py --cap-snapshot``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

from agentic_dynamics.control.context_compiler import SNAPSHOT_SOURCE_TYPE  # noqa: E402
from agentic_dynamics.core.paths import KB_ARTIFACT_DIR, PROJECT_ROOT  # noqa: E402

#: Where ``scripts/generate_manifest.py`` writes the compacted registry array — the same file
#: ``scripts/registry.py`` reads. Duplicated here (rather than a fragile ``scripts.registry``
#: cross-script import — ``scripts/`` carries no ``__init__.py``, so its import-as-a-package
#: contract is not guaranteed outside pytest's own path setup) as one constant + one small
#: reader, exactly the shape ``registry.load_registry`` already has.
DATA_MANIFEST_PATH = PROJECT_ROOT / "experiments" / "data_manifest.json"


def load_registry(manifest_path: Path = DATA_MANIFEST_PATH) -> list[dict[str, Any]]:
    """Return the manifest's ``registry`` array, or ``[]`` when it's absent/unreadable."""
    if not manifest_path.exists():
        return []
    try:
        manifest = json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    return manifest.get("registry") or []


def _read_payload(knowledge_id: str, *, artifact_dir: Path = KB_ARTIFACT_DIR) -> dict[str, Any] | None:
    path = artifact_dir / f"{knowledge_id}.json"
    if not path.is_file():
        return None
    try:
        artifact = json.loads(path.read_text())
        return json.loads(artifact.get("text") or "{}")
    except (OSError, json.JSONDecodeError):
        return None


def compute_report(
    *,
    manifest_path: Path = DATA_MANIFEST_PATH,
    artifact_dir: Path = KB_ARTIFACT_DIR,
) -> dict[str, Any]:
    """Aggregate admissibility/unknown/stale/conflict rates over every recorded snapshot."""
    rows = [
        r for r in load_registry(manifest_path) if r.get("source_type") == SNAPSHOT_SOURCE_TYPE
    ]
    payloads = [p for p in (_read_payload(r["knowledge_id"], artifact_dir=artifact_dir) for r in rows) if p]

    n = len(payloads)
    n_admissible = sum(1 for p in payloads if p.get("admissible"))
    n_with_unknowns = sum(1 for p in payloads if p.get("n_unknowns"))
    n_with_conflicts = sum(1 for p in payloads if p.get("n_conflicts"))
    n_with_stale = sum(1 for p in payloads if p.get("n_stale"))

    unknown_predicates: dict[str, int] = {}
    for p in payloads:
        for pred in p.get("unknown_predicates") or []:
            unknown_predicates[pred] = unknown_predicates.get(pred, 0) + 1

    return {
        "n_snapshots": n,
        "admissibility_rate": round(n_admissible / n, 4) if n else None,
        "unknown_rate": round(n_with_unknowns / n, 4) if n else None,
        "conflict_rate": round(n_with_conflicts / n, 4) if n else None,
        "stale_rate": round(n_with_stale / n, 4) if n else None,
        "unknown_predicates": dict(sorted(unknown_predicates.items(), key=lambda kv: -kv[1])),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    report = compute_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    if report["n_snapshots"] == 0:
        print("No context_snapshot records found — the seam has not recorded anything yet.")
        print("Enable it with `scripts/run_workflow.py --cap-snapshot`, then re-run.")
        return 0

    print(f"snapshots recorded:  {report['n_snapshots']}")
    print(f"admissibility rate:  {report['admissibility_rate']:.1%}")
    print(f"unknown rate:        {report['unknown_rate']:.1%}")
    print(f"conflict rate:       {report['conflict_rate']:.1%}")
    print(f"stale rate:          {report['stale_rate']:.1%}")
    if report["unknown_predicates"]:
        print("most-often-unknown predicates:")
        for pred, count in report["unknown_predicates"].items():
            print(f"  {pred}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
