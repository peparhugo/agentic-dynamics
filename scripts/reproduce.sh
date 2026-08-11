#!/bin/bash
set -euo pipefail

echo "============================================"
echo " AI FinOps Framework — Analysis Pipeline"
echo "============================================"
echo ""
echo "Rebuilds the analysis and presentation layer from existing"
echo "experiment artifacts. Does NOT rerun experiments."
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

echo "--- Step 1/6: Inventory ---"
python3 scripts/inventory.py refresh

echo "--- Step 2/6: Analyze worktrees (with tests) ---"
python3 scripts/analyze_worktrees.py

echo "--- Step 3/6: Analyze trajectories ---"
python3 scripts/analyze_trajectories.py

echo "--- Step 4/6: Run lab analyses ---"
for lab in lab_claude_audit lab_grit_matrix lab_correctness_premium \
           lab_flail_triggers lab_tool_archetypes lab_task_routing \
           lab_basin_topology lab_survival_horizon lab_reasoning_divergence \
           lab_semantic_clusters lab_cross_model_reasoning \
           lab_basin_topology_neo4j lab_opencode_meta_analysis lab_sonar_quality; do
    echo "  Running ${lab}.py..."
    python3 "scripts/${lab}.py" 2>&1 | tail -1
done

echo "--- Step 5/6: Build website data ---"
python3 scripts/build_data.py

echo "--- Step 6/6: Generate data manifest ---"
python3 scripts/generate_manifest.py

echo ""
echo "============================================"
echo " Done — firebase/public/data.js is ready"
echo " Deploy: cd firebase && firebase deploy --only hosting"
echo " Manifest: experiments/data_manifest.json"
echo "============================================"
