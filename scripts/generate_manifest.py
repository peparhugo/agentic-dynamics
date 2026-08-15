#!/usr/bin/env python3
"""Generate data_manifest.json — schema version, hashes, pipeline audit trail."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"

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

if __name__ == "__main__":
    main()
