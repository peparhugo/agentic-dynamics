#!/usr/bin/env python3
"""Generate data_manifest.json — schema version, hashes, pipeline audit trail.

**The registry drain guard (aio_controller_postmortem A4).** ``_compact_registry_index`` is
the active path that consumes the append-only ``registry_index.jsonl``. That store only ever
grows — every change to a record (a supersede, a tombstone) APPENDS a line, it never removes
one — so the number of distinct ``knowledge_id`` versions is monotonic. The historical
"Sep-4 drain" (F-03) resolved a merge of this file to a stale side and dropped 48,321 → 5,011
rows; nothing refused it. This script now compares the compacted version count against the
previously written manifest and refuses to overwrite it with a smaller one unless the operator
passes ``--allow-shrink`` — a shrink is a violation until proven otherwise.

**The raw-source-row-count drain guard (aio_controller_postmortem B1).** The version count
alone is blind to the F-04 dedup signature: a tombstone/supersede **marker** line deliberately
shares its target's ``knowledge_id`` (it annotates the record it points at), so deleting the
marker does NOT reduce the number of distinct ``knowledge_id`` versions — yet real lifecycle
evidence is gone. The manifest therefore also records the number of structurally valid source
rows and refuses a compaction whose source-row count fell below the previous manifest's. This
is strictly more sensitive than the version count and catches the F-04 **count-decrease** form
(it cannot tell a lost marker from a lost ordinary row). It is a raw-COUNT guard, not identity
or content conservation: a marker replaced by an unrelated valid row leaves the count unchanged
and is NOT refused. Together the two guards bound the file by (a) distinct version identities
and (b) raw valid source-row count — neither compares row content.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"

#: Where scripts/kb_worker.py's "kb-registry-v1" consumer group appends one compacted
#: JSON line per indexed knowledge record (canonical-state round 2, plan step 8). This is
#: a *value-only leaf import* from ``agentic_dynamics.core.paths`` (canonical-state R6),
#: the single owner of the path: the pure-pathlib ``paths`` module is imported directly
#: (deliberately NOT the barrel ``instrument/__init__.py``) so this script never triggers
#: the heavy re-export surface (redis/neo4j/chroma) and stays a fast, always-available
#: pipeline step (hashlib/json/subprocess/pathlib only, plus this one pathlib-only leaf import).
try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401
from agentic_dynamics.core.paths import REGISTRY_INDEX_PATH  # noqa: E402  # isort: skip

def sha256(path):
    """SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def get_opencode_version():
    try:
        result = subprocess.run(["opencode", "--version"], capture_output=True, text=True, timeout=10)
        return result.stdout.strip() or result.stderr.strip()
    except Exception:
        return "unknown"

def get_git_commit():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5,
            cwd=str(PROJECT_ROOT)
        )
        return result.stdout.strip()[:8]
    except Exception:
        return "unknown"

def _iter_registry_rows(path):
    """Yield each structurally valid row from the append-only registry_index.jsonl.

    Missing/corrupt lines are skipped rather than aborting the whole manifest build — a
    single truncated JSONL line (e.g. from a process killed mid-write) must not prevent
    every OTHER already-durable line from surfacing. A row with no ``knowledge_id`` or
    no ``entity_id`` cannot be attributed to a version or a logical entity, so it is
    skipped too (this also covers scripts/kb_worker.py's kb-registry-v1 "predecessor
    superseded" marker lines, which — unlike a full record registration line — always
    carry both of those two fields even though several other fields are absent).
    """
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not row.get("knowledge_id") or not row.get("entity_id"):
                continue
            yield row


def _derive_lifecycle(row, successor_by_predecessor_kid):
    """Return ``(lifecycle_state, valid_to)`` DERIVED for one knowledge_id's row.

    Canonical-state finalize, G2 — closes the gap docs/canonical_state_r2_design.md §3/§6
    describes: ``lifecycle_state``/``valid_to`` are "index-only, computed, never stored in
    the artifact" — but the pre-G2 compaction above never actually computed them, it just
    copied whatever a single append-only line happened to say. This function is the
    computation design §6 always intended, applied at the ONE place (compaction) that has
    visibility across a whole entity's version history at once:

    - If some OTHER row's ``supersedes`` pointer names this row's ``knowledge_id``, this
      row is superseded — full stop, regardless of what its OWN ``lifecycle_state`` text
      says (so this is correct even for a registry_index.jsonl line written before
      kb_worker.py's kb-registry-v1 handler learned to compute lifecycle_state itself, or
      for a raw line some future producer writes without going through that handler at
      all). The effective ``valid_to`` is the successor's own ``valid_from`` — the flat
      index never persists a dedicated ``valid_from`` column (only ``observed_at``/
      ``indexed_at``), and base design §"Open Question 2" defines ``valid_from`` as
      defaulting to ``observed_at`` for exactly this reason, so ``observed_at`` (falling
      back to ``indexed_at``) is the correct proxy, not a workaround.
    - Otherwise, a row whose OWN ``lifecycle_state`` says "tombstoned" (kb_worker.py's
      handler writes this for a ``delete`` operation, self-tombstone — the record IS the
      retracted version) stays tombstoned; its ``valid_to`` is its own already-recorded
      value if the producer set one, else its ``indexed_at`` (the closest proxy this flat
      index has to "event time" per design §6's "delete ... valid_to = event time").
    - Otherwise it is current, with ``valid_to = None`` (still open).
    """
    successor = successor_by_predecessor_kid.get(row["knowledge_id"])
    if successor is not None:
        valid_to = successor.get("observed_at") or successor.get("indexed_at")
        return "superseded", valid_to
    if row.get("lifecycle_state") == "tombstoned":
        return "tombstoned", row.get("valid_to") or row.get("indexed_at")
    return "current", row.get("valid_to")


def _compact_registry_index(path):
    """Compact the append-only registry_index.jsonl into one row per entity_id, with
    ``lifecycle_state``/``valid_to`` DERIVED rather than copied verbatim from whichever
    line happens to be temporally last (canonical-state finalize, G2).

    Two passes:

    1. Collapse to (at most) one row per ``knowledge_id``. This is the idempotence step
       every consumer in this package already applies at its own destination — but it
       matters MORE here than it used to, because kb_worker.py's kb-registry-v1 handler
       can now append a "predecessor superseded" marker line for an OLDER version at
       supersede time (same ``entity_id`` as, and the SAME ``indexed_at`` as, the NEW
       version's own line). Deduping at the ``entity_id`` grain the way the pre-G2
       implementation did would let that marker line nondeterministically outrace the
       real "current" row on the ``>=`` latest-wins tiebreak; deduping at the finer
       ``knowledge_id`` grain first means the two lines never even compete for the same
       dict slot — each version keeps its own identity into pass 2.
    2. Roll each entity_id's known versions up into ONE compacted row. The row reported
       is either the entity's TOMBSTONED version (if a tombstone is the most recent event
       recorded against it — a tombstone is terminal, design §6: "used when a record is
       retracted with no replacement under the same entity", so an older "current" row
       must never resurface once one exists) or its live (derived-"current") version.
       Every OTHER known version for that entity — superseded predecessors, most
       commonly — is still exposed, DERIVED the same way, in the row's nested
       ``versions`` list, so "a supersede renders the predecessor superseded with
       effective valid_to = successor valid_from" (the source fact this function exists
       to compute) remains inspectable even though it can never itself be the entity's
       one reported head row.

    Missing/corrupt lines are skipped (see :func:`_iter_registry_rows`) rather than
    aborting the whole manifest build. Returns a list sorted by ``entity_id`` for
    deterministic, diff-friendly manifest output — unchanged from the pre-G2 contract.
    """
    if not path.exists():
        return []

    by_knowledge_id = {}
    for row in _iter_registry_rows(path):
        kid = row["knowledge_id"]
        existing = by_knowledge_id.get(kid)
        # ">=" (not ">"): among ties, the later line in append order wins — a
        # deterministic tiebreak since the file is strictly append-only.
        if existing is None:
            by_knowledge_id[kid] = row
        elif str(row.get("indexed_at") or "") >= str(existing.get("indexed_at") or ""):
            # MERGE, don't replace. kb_worker.py's kb-registry-v1 handler appends a thin
            # "predecessor superseded" marker line that shares the predecessor's knowledge_id
            # but carries only a handful of fields (lifecycle_state/valid_to/indexed_at). If a
            # bare replace won, that marker would clobber the predecessor's full registration
            # line and silently drop its observed_at/source_type/logical_locator/source_uri/
            # supersedes/causes. The newer line's non-null fields still win (so the marker's
            # derived lifecycle_state/valid_to take effect), but the older line's fields that
            # the newer line lacks are preserved.
            by_knowledge_id[kid] = {**existing, **{k: v for k, v in row.items() if v is not None}}

    # A knowledge_id that some OTHER row's `supersedes` pointer names is, by definition,
    # no longer current. Keyed by the PREDECESSOR's knowledge_id -> the row that
    # supersedes it, so _derive_lifecycle can look up "am I someone's predecessor, and if
    # so, what is my successor's own valid_from" in one dict lookup.
    successor_by_predecessor_kid = {
        row["supersedes"]: row for row in by_knowledge_id.values() if row.get("supersedes")
    }

    derived_by_kid = {}
    for kid, row in by_knowledge_id.items():
        lifecycle_state, valid_to = _derive_lifecycle(row, successor_by_predecessor_kid)
        derived_by_kid[kid] = {**row, "lifecycle_state": lifecycle_state, "valid_to": valid_to}

    by_entity = defaultdict(list)
    for row in derived_by_kid.values():
        by_entity[row["entity_id"]].append(row)

    compacted = []
    for entity_id, rows in by_entity.items():
        rows.sort(key=lambda r: str(r.get("indexed_at") or ""))
        tombstoned = [r for r in rows if r["lifecycle_state"] == "tombstoned"]
        live = [r for r in rows if r["lifecycle_state"] == "current"]

        if tombstoned and (not live or tombstoned[-1]["indexed_at"] >= live[-1]["indexed_at"]):
            head = tombstoned[-1]
        elif live:
            head = live[-1]
        else:
            # Degenerate: every known version for this entity derived as "superseded"
            # and none is tombstoned — only reachable from a malformed/partial supersede
            # chain (e.g. a `supersedes` pointer with no live head at the end of it).
            # Fall back to the temporally latest row rather than fabricating a "current"
            # state this entity's own history does not actually support.
            head = rows[-1]

        # Terminal-tombstone semantics (m4): a terminal tombstone closes every earlier
        # OPEN version of its entity. An open ("current") version becomes "superseded"
        # with valid_to = the tombstone's own valid_from (the flat index's valid_from
        # proxy - observed_at, falling back to indexed_at, exactly as _derive_lifecycle
        # uses for a successor's valid_from). Without this, "current, then tombstoned"
        # leaves a stale "current" predecessor lingering in the version history alongside
        # the tombstone (the entity 37679fe003ca retraction bug).
        if head["lifecycle_state"] == "tombstoned":
            tombstone_valid_from = head.get("observed_at") or head.get("indexed_at")
            for r in rows:
                if r["knowledge_id"] != head["knowledge_id"] and r["lifecycle_state"] == "current":
                    r["lifecycle_state"] = "superseded"
                    r["valid_to"] = tombstone_valid_from

        compacted.append({
            "entity_id": entity_id,
            "knowledge_id": head["knowledge_id"],
            "source_type": head.get("source_type"),
            "logical_locator": head.get("logical_locator"),
            "source_uri": head.get("source_uri"),
            "observed_at": head.get("observed_at"),
            "indexed_at": head.get("indexed_at"),
            "supersedes": head.get("supersedes"),
            "causes": head.get("causes"),
            "reason": head.get("reason"),
            "lifecycle_state": head["lifecycle_state"],
            "valid_to": head["valid_to"],
            # Every known version of this entity, oldest -> newest, each with its own
            # DERIVED lifecycle_state/valid_to — see this function's docstring on why a
            # superseded predecessor can never be the row above, but must still surface
            # somewhere in "the manifest's registry array".
            "versions": [
                {
                    "knowledge_id": r["knowledge_id"],
                    "lifecycle_state": r["lifecycle_state"],
                    "valid_to": r["valid_to"],
                    "observed_at": r.get("observed_at"),
                    "indexed_at": r.get("indexed_at"),
                    "reason": r.get("reason"),
                }
                for r in rows
            ],
        })

    return sorted(compacted, key=lambda r: r["entity_id"])

def _registry_version_count(registry: list[dict]) -> int:
    """Total version rows in a compacted registry.

    One entry per ``knowledge_id`` ever appended (a compacted row nests its entity's
    ``versions`` list), so this is the count the append-only index can only increase.
    """
    return sum(len(row.get("versions") or [row]) for row in registry)


def _count_registry_source_rows(path: Path) -> int:
    """Count every structurally valid row in the append-only ``registry_index.jsonl``.

    Unlike :func:`_registry_version_count` (which counts distinct ``knowledge_id`` versions),
    this counts raw source lines. A tombstone/supersede MARKER line deliberately shares its
    target's ``knowledge_id`` (it annotates the record it points at), so it does not add a
    version — but it is still a durable line in the append-only store, and losing it is the
    F-04 signature. Counting raw rows makes a COUNT DECREASE visible even when the version
    count cannot see it. It is a count, not content conservation: an equal-count replacement
    (a lost marker swapped for an unrelated valid row) is not detected. Malformed/blank lines
    are skipped exactly as :func:`_iter_registry_rows` skips them (they are not valid data, so
    their absence is not a data loss).
    """
    if not path.exists():
        return 0
    return sum(1 for _ in _iter_registry_rows(path))


def _read_previous_registry_versions(manifest_path: Path) -> int | None:
    """The version count recorded by the manifest already on disk, or ``None`` when absent."""
    if not manifest_path.exists():
        return None
    try:
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    registry = previous.get("registry")
    if not isinstance(registry, list) or not registry:
        return None
    return _registry_version_count(registry)


def detect_registry_drain(
    new_registry: list[dict], previous_versions: int | None
) -> tuple[int, int] | None:
    """``(new_count, previous_count)`` when an append-only registry lost versions, else None.

    Pure and side-effect free so the direction check is directly testable; ``main`` wires it
    to the write. A ``None`` baseline (first run, or a manifest without a registry) cannot
    prove a drain and is therefore not refused — the guard fails closed only on evidence.
    """
    if previous_versions is None:
        return None
    new_versions = _registry_version_count(new_registry)
    if new_versions < previous_versions:
        return (new_versions, previous_versions)
    return None


def _read_previous_registry_source_rows(manifest_path: Path) -> int | None:
    """The source-row count recorded by the manifest already on disk, or ``None`` when absent.

    ``None`` (a manifest written before the B1 guard, or a missing/corrupt file) is not a
    baseline and therefore cannot prove a marker loss — the guard fails closed only on
    evidence, mirroring :func:`_read_previous_registry_versions`.
    """
    if not manifest_path.exists():
        return None
    try:
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    rows = previous.get("registry_source_rows")
    if not isinstance(rows, int) or isinstance(rows, bool) or rows < 0:
        return None
    return rows


def detect_registry_source_drain(
    new_source_rows: int | None, previous_source_rows: int | None
) -> tuple[int, int] | None:
    """``(new_rows, previous_rows)`` when the append-only source lost raw lines, else None.

    The version-count guard (:func:`detect_registry_drain`) cannot see a lost
    tombstone/supersede MARKER line, because the marker shares its target's ``knowledge_id``
    and so does not change the distinct-version count. A raw-source-row COUNT DECREASE can —
    but only a decrease: the guard cannot distinguish a lost marker from a lost ordinary row,
    and an equal-count replacement (one valid row substituted for another) is invisible. Pure
    and side-effect free so the direction check is directly testable; ``main`` wires it to the
    write. A ``None`` baseline (first run, or a manifest without a source-row count) is not
    refused — the guard fails closed only on evidence.
    """
    if previous_source_rows is None or new_source_rows is None:
        return None
    if new_source_rows < previous_source_rows:
        return (new_source_rows, previous_source_rows)
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-dynamics data manifest",
        description="Generate data_manifest.json (schema, hashes, compacted registry).",
    )
    parser.add_argument(
        "--allow-shrink",
        action="store_true",
        help="permit a compaction that drops registry versions or raw valid source rows below "
        "the previous manifest (a destructive-store repair — the drain guards refuse by default)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv if argv is not None else [])
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "opencode_version": get_opencode_version(),
        "git_commit": get_git_commit(),
        "files": {},
        "pipeline_steps": ["inventory", "analyze_worktrees", "analyze_trajectories", "build_data"],
        "known_limitations": [
            "116 of 227 sessions use heuristic correctness (keyword-based, no pytest executed)",
            "Per-cell n < 5 for 17 operator×model combinations — shaded on evidence page",
            "Rules 6-9 are modeled, not experimentally validated — batch/cascade/SLA experiments not executed",
            "Per-model session counts are imbalanced: DeepSeek 119, Claude 44, GPT variants 6-18 each"
        ]
    }

    files_to_hash = {
        # The file classification (public-truth review "smaller"): inputs to build_data,
        # its published output, and retired artifacts that are no longer first-class
        # entries. ``_results_summary.json`` is HISTORICAL — hashed for audit only, never
        # treated as a current input (docs/data_integrity_findings.md rule 4).
        "canonical_inputs": {
            "inventory.json": PROJECT_ROOT / "experiments" / "inventory.json",
            "_trajectory_aggregate.json": RESULTS_DIR / "_trajectory_aggregate.json",
        },
        "canonical_outputs": {
            "data.js": PROJECT_ROOT / "apps" / "website" / "data.js",
        },
        "historical_artifacts": {
            "_results_summary.json": RESULTS_DIR / "_results_summary.json",
        },
    }
    manifest["files"] = {}
    for class_name, files in files_to_hash.items():
        bucket = {}
        for name, path in files.items():
            if path.exists():
                bucket[name] = {
                    "sha256": sha256(path),
                    "size_bytes": path.stat().st_size,
                }
            else:
                bucket[name] = None
        manifest["files"][class_name] = bucket

    # canonical-state round 2, plan step 15: the compacted registry array — additive
    # only. `manifest["files"]` above is otherwise byte-for-byte unchanged (design §11's
    # backward-compatibility requirement), and this key is new, so no existing consumer
    # of data_manifest.json is affected by its presence.
    compacted_registry = _compact_registry_index(REGISTRY_INDEX_PATH)
    source_rows = _count_registry_source_rows(REGISTRY_INDEX_PATH)
    output_path = PROJECT_ROOT / "experiments" / "data_manifest.json"

    # A4: the append-only registry only grows; refuse to overwrite the manifest with a
    # compaction that lost versions (the F-03 drain signature) unless the operator allowed it.
    drain = detect_registry_drain(compacted_registry, _read_previous_registry_versions(output_path))
    # B1: the raw append-only source also only grows. A version-count drain misses the F-04
    # marker-loss COUNT DECREASE (the marker shares its target's knowledge_id), so also refuse
    # a raw source-row count decrease. This is a count guard, not content conservation.
    source_drain = detect_registry_source_drain(
        source_rows, _read_previous_registry_source_rows(output_path)
    )
    if (drain is not None or source_drain is not None) and not args.allow_shrink:
        if drain is not None:
            new_versions, previous_versions = drain
            print(
                "REFUSED: registry_index.jsonl compacted to "
                f"{new_versions} versions, below the previous manifest's {previous_versions}. "
                "The append-only registry only grows; a shrink is the drain/over-deletion "
                "signature (aio_controller_postmortem F-03). Repair the index, or re-run "
                "with --allow-shrink if the loss is understood and intended.",
                file=sys.stderr,
            )
        if source_drain is not None:
            new_rows, previous_rows = source_drain
            print(
                "REFUSED: registry_index.jsonl now holds "
                f"{new_rows} valid source rows, below the previous manifest's {previous_rows}. "
                "The append-only registry only grows; a valid source-row count decrease is the "
                "F-04 over-deletion signature (the version count cannot see a lost "
                "tombstone/supersede marker, which shares its target's knowledge_id). This "
                "guard compares COUNTS, not row identities — an equal-count replacement is not "
                "refused. Repair the index, or re-run with --allow-shrink if the loss is "
                "understood and intended.",
                file=sys.stderr,
            )
        return 2

    manifest["registry"] = compacted_registry
    manifest["registry_source_rows"] = source_rows
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Written {output_path}")
    print(f"  opencode: {manifest['opencode_version']}")
    print(f"  commit:   {manifest['git_commit']}")
    for class_name, bucket in manifest["files"].items():
        print(f"  {class_name}:")
        for name, info in bucket.items():
            if info:
                print(
                    f"    {name}: {info['size_bytes']:,} bytes, "
                    f"sha256={info['sha256'][:12]}..."
                )
            else:
                print(f"    {name}: MISSING")
    print(f"  registry: {len(manifest['registry'])} entities (compacted from {REGISTRY_INDEX_PATH.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
