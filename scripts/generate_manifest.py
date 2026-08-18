#!/usr/bin/env python3
"""Generate data_manifest.json — schema version, hashes, pipeline audit trail."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"

#: Where scripts/kb_worker.py's "kb-registry-v1" consumer group appends one compacted
#: JSON line per indexed knowledge record (canonical-state round 2, plan step 8). This
#: literal path is duplicated (not imported) from kb_worker.py's own
#: REGISTRY_INDEX_PATH constant deliberately: kb_worker.py imports `redis` and the full
#: `instrument` package at module level (a consumer-worker dependency footprint), while
#: this script is intentionally dependency-light (hashlib/json/subprocess/pathlib only,
#: confirmed by its existing imports above) so it stays a fast, always-available
#: pipeline step. Keep this path in sync with kb_worker.REGISTRY_INDEX_PATH by hand if
#: either ever moves.
REGISTRY_INDEX_PATH = RESULTS_DIR / "registry_index.jsonl"

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

def _compact_registry_index(path):
    """Compact the append-only registry_index.jsonl into one row per entity_id.

    Canonical-state round 2, plan step 15: the same "append-only log + compacted
    snapshot" relationship flags.jsonl already has to its own bounded Redis mirror.
    Reads every line, keeps only the row with the newest ``indexed_at`` per
    ``entity_id`` (a later index pass always describes the more current state of that
    logical entity — this is what makes each output row genuinely "current", not a
    stale intermediate version), and returns the result as a list sorted by entity_id
    for deterministic, diff-friendly manifest output.

    Missing/corrupt lines are skipped rather than aborting the whole manifest build — a
    single truncated JSONL line (e.g. from a process killed mid-write) must not prevent
    every OTHER already-durable line from surfacing.
    """
    if not path.exists():
        return []
    latest = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            entity_id = row.get("entity_id")
            if not entity_id:
                continue
            existing = latest.get(entity_id)
            # ">=" (not ">"): among ties, the later line in append order wins — a
            # deterministic tiebreak since the file is strictly append-only.
            if existing is None or str(row.get("indexed_at") or "") >= str(existing.get("indexed_at") or ""):
                latest[entity_id] = row
    return [latest[key] for key in sorted(latest)]

def main():
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
        "inventory.json": PROJECT_ROOT / "experiments" / "inventory.json",
        "_results_summary.json": RESULTS_DIR / "_results_summary.json",
        "_trajectory_aggregate.json": RESULTS_DIR / "_trajectory_aggregate.json",
        "data.js": PROJECT_ROOT / "firebase" / "public" / "data.js",
    }
    for name, path in files_to_hash.items():
        if path.exists():
            manifest["files"][name] = {
                "sha256": sha256(path),
                "size_bytes": path.stat().st_size,
            }
        else:
            manifest["files"][name] = None

    # canonical-state round 2, plan step 15: the compacted registry array — additive
    # only. `manifest["files"]` above is otherwise byte-for-byte unchanged (design §11's
    # backward-compatibility requirement), and this key is new, so no existing consumer
    # of data_manifest.json is affected by its presence.
    manifest["registry"] = _compact_registry_index(REGISTRY_INDEX_PATH)

    output_path = PROJECT_ROOT / "experiments" / "data_manifest.json"
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Written {output_path}")
    print(f"  opencode: {manifest['opencode_version']}")
    print(f"  commit:   {manifest['git_commit']}")
    for name, info in manifest["files"].items():
        if info:
            print(f"  {name}: {info['size_bytes']:,} bytes, sha256={info['sha256'][:12]}...")
        else:
            print(f"  {name}: MISSING")
    print(f"  registry: {len(manifest['registry'])} entities (compacted from {REGISTRY_INDEX_PATH.name})")

if __name__ == "__main__":
    main()
