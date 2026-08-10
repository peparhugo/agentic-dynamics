#!/bin/bash
set -euo pipefail

echo "============================================"
echo " AI FinOps Framework — Reproduction Pipeline"
echo "============================================"
echo ""
echo "Prerequisites:"
echo "  - opencode CLI (in PATH or ~/.opencode/bin/)"
echo "  - Python 3.10+"
echo "  - ~/.local/share/opencode/opencode.db (session data)"
echo "  - Optional: FINOPS_WORKTREE_ROOT (default /tmp)"
echo ""

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

mkdir -p experiments/results/artifacts

echo "--- Step 1/5: Inventory ---"
python3 scripts/inventory.py refresh

echo "--- Step 2/5: Analyze worktrees ---"
python3 scripts/analyze_worktrees.py --no-tests

echo "--- Step 3/5: Analyze trajectories ---"
python3 scripts/analyze_trajectories.py

echo "--- Step 4/5: Build website data ---"
python3 scripts/build_data.py

echo "--- Step 5/5: Generate data manifest ---"
python3 scripts/generate_manifest.py

echo ""
echo "============================================"
echo " Done — firebase/public/data.js is ready"
echo " Deploy: cd firebase && firebase deploy --only hosting"
echo " Manifest: experiments/data_manifest.json"
echo "============================================"
