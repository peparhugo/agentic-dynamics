#!/usr/bin/env python3
"""The self-maintenance command (design: system_knowledge_abstraction §4).

Regenerates EVERY derived surface from its sources, in dependency order — the machine
reshapes itself after a boundary lands, a campaign phase commits, or the contract layer
(frontmatter / markers / status fields) changes:

    1. system_snapshot.py      → agent_config/system_snapshot.md   (L0 — the game board)
    2. _gen_instructions.py    → .opencode/** + .claude/**         (L0 + L1 rendering)
    3. spec_status.py          → experiments/specs/{index.json,STATUS.md}  (spec lifecycle)
    4. sync_data.py            → experiments/data/*.parquet
    5. build_data.py           → apps/website/data.js
    6. generate_manifest.py    → data_manifest.json

The guard tests are the backstop (never the repair path): if a guard reports drift, run this
command — the drift is a stale render, and this command re-renders it. ``--verify`` appends
the guard suite as step 7. Every step is best-effort with a loud failure line; one failing
subsystem does not block the rest. Steps 4-6 are skipped when no results changed (the data
chain is the slow part) unless ``--full`` is passed.

Usage:
    python3 scripts/sync_surfaces.py            # regen surfaces (fast path)
    python3 scripts/sync_surfaces.py --full     # + the data chain unconditionally
    python3 scripts/sync_surfaces.py --verify   # + the deterministic guard suite
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

#: (label, argv, critical) — critical steps stop the run on failure; the renders are
#: critical (a stale render is the failure mode), the data chain is not (it is slow and
#: skipped on the fast path anyway).
STEPS: list[tuple[str, list[str], bool]] = [
    ("L0 game board", ["python3", "scripts/system_snapshot.py"], True),
    ("agent surfaces", ["python3", "scripts/_gen_instructions.py"], True),
    ("spec lifecycle", ["python3", "scripts/spec_status.py"], True),
    ("story sync", ["python3", "scripts/sync_data.py"], False),
    ("site data", ["python3", "scripts/build_data.py"], False),
    ("manifest", ["python3", "scripts/generate_manifest.py"], False),
]

DATA_CHAIN_FAST_STEPS = {3, 4, 5}  # indices of STEPS skipped unless --full


def _run(label: str, argv: list[str], timeout: int = 900) -> bool:
    print(f"── {label}: {' '.join(argv)}")
    try:
        r = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        print(f"   FAILED to launch: {e!r}")
        return False
    if r.returncode != 0:
        tail = (r.stdout or "")[-400:] + (r.stderr or "")[-400:]
        print(f"   FAILED (exit {r.returncode}): {tail.strip()[-400:]}")
        return False
    print("   ok")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="run the data chain unconditionally")
    parser.add_argument(
        "--verify", action="store_true", help="append the deterministic guard suite (step 7)"
    )
    args = parser.parse_args()

    ok = True
    for i, (label, argv, critical) in enumerate(STEPS):
        if i in DATA_CHAIN_FAST_STEPS and not args.full and not args.verify:
            print(f"── {label}: skipped (fast path — pass --full to force)")
            continue
        ok = _run(label, argv) and ok
        if not ok and critical:
            print("CRITICAL STEP FAILED — a stale render is the failure mode; see above")
            return 1
    if args.verify:
        ok = _run(
            "guard suite",
            ["python3", "-m", "pytest", "tests/", "-m", "not external", "--timeout", "600", "-q"],
            1800,
        ) and ok
    print("── sync complete" if ok else "── sync finished with failures")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
