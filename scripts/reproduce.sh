#!/bin/bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Agentic Dynamics — Reproduction Pipeline
# ---------------------------------------------------------------------------
# Rebuilds the analysis and presentation layer from existing experiment
# artifacts. Does NOT rerun experiments (no inference, no queue, no Redis).
#
#   scripts/reproduce.sh            # run the full post-hoc pipeline
#   scripts/reproduce.sh --dry-run  # print the steps WITHOUT executing them
#
# Steps (in dependency order):
#   1. inventory.py refresh       — rebuild experiments/inventory.json
#   2. sync_data.py               — story results -> sessions.parquet/stories.parquet
#   3. analyze_worktrees.py       — per-experiment Game Report markdown
#   4. analyze_trajectories.py    — per-transcript trajectory summaries
#   5. lab books (the CORE set)   — per-question analyses -> experiments/results/lab_*.json
#                                   The set is NOT hard-coded here: it is read from
#                                   scripts/lab_manifest.json (reproduce_default: true).
#                                   Quarantined labs — those that read the retired
#                                   _results_summary.json, directly or transitively — are
#                                   excluded by construction (semantic-integrity review P0).
#   6. build_data.py              — apps/website/data.js (the website corpus)
#   7. generate_manifest.py       — experiments/data_manifest.json (hashes the outputs above)
#
# Prerequisites:
#   - opencode CLI (in PATH or ~/.opencode/bin/) — used only for the manifest version stamp
#   - Python 3.10+
#   - ~/.local/share/opencode/opencode.db (session data)
#   - Optional: FINOPS_WORKTREE_ROOT (default /tmp)
# ---------------------------------------------------------------------------

DRY_RUN=0
case "${1:-}" in
  "")
    ;;
  "--dry-run")
    DRY_RUN=1
    ;;
  "-h"|"--help")
    echo "Usage: $0 [--dry-run]"
    echo ""
    echo "Rebuild the analysis + presentation layer from existing experiment artifacts."
    echo "  --dry-run  print every step that would run, without executing anything"
    exit 0
    ;;
  *)
    echo "Unknown argument: $1 (use --dry-run or --help)" >&2
    exit 2
    ;;
esac

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# ---------------------------------------------------------------------------
# The core lab set — derived, never hand-listed.
#
# It used to be a hard-coded array of all 19 labs, which is exactly how the
# noncanonical ones stayed in the default reproduction: two lists (this one and
# build_data's) drifting away from each other with nothing checking either.
# Both now read scripts/lab_manifest.json through the single parser in
# agentic_dynamics.reporting.lab_manifest, so "what reproduce runs" and "what the
# website publishes" cannot disagree with the classification.
#
# PYTHONPATH is pinned to THIS checkout's src/ so an editable install of another
# checkout can never answer the question for us.
# ---------------------------------------------------------------------------
LAB_QUERY='from agentic_dynamics.reporting.lab_manifest import reproduce_lab_scripts
print("\n".join(reproduce_lab_scripts()))'

if ! LAB_LIST="$(PYTHONPATH="$PROJECT_ROOT/src" python3 -c "$LAB_QUERY")"; then
  echo "ERROR: could not read the core lab set from scripts/lab_manifest.json" >&2
  exit 1
fi

# shellcheck disable=SC2206  # word splitting on newlines is the intent here
LAB_BOOKS=($LAB_LIST)

if [[ "${#LAB_BOOKS[@]}" -eq 0 ]]; then
  echo "ERROR: scripts/lab_manifest.json yielded an empty core lab set" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# run_step <description> <command...>
#
# Executes the command, or — under --dry-run — prints the exact argv it would
# invoke and skips the side effect. This is what lets CI smoke the entrypoint
# without a real opencode DB, worktrees, or network.
# ---------------------------------------------------------------------------
run_step() {
  local description="$1"
  shift
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] %s\n' "$*"
    return 0
  fi
  echo "--- $description ---"
  "$@"
}

echo "============================================"
echo " Agentic Dynamics — Reproduction Pipeline"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo " (dry run — no steps will execute)"
fi
echo "============================================"
echo ""

# Outputs are written under experiments/results/ and apps/website/ — make sure the
# scratch roots exist even on a fresh checkout.
run_step "Create artifact scratch dirs" \
  mkdir -p experiments/results/artifacts

run_step "Step 1/7: Refresh inventory" \
  python3 scripts/inventory.py refresh

run_step "Step 2/7: Normalize story results to parquet" \
  python3 scripts/sync_data.py

run_step "Step 3/7: Analyze worktrees (game reports)" \
  python3 scripts/analyze_worktrees.py

run_step "Step 4/7: Analyze trajectories" \
  python3 scripts/analyze_trajectories.py

echo "--- Step 5/7: Run lab book analyses (${#LAB_BOOKS[@]} core, from scripts/lab_manifest.json) ---"
for lab in "${LAB_BOOKS[@]}"; do
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] python3 scripts/%s\n' "$lab"
    continue
  fi
  echo "  Running ${lab}..."
  python3 "scripts/${lab}" 2>&1 | tail -1
done

run_step "Step 6/7: Build website data (apps/website/data.js)" \
  python3 scripts/build_data.py

run_step "Step 7/7: Generate data manifest" \
  python3 scripts/generate_manifest.py

echo ""
echo "============================================"
echo " Done — apps/website/data.js is ready"
echo " Deploy (BOTH hosts): cd apps/website && firebase deploy --only hosting && firebase deploy --only hosting --project agentic-dynamics"
echo " Manifest: experiments/data_manifest.json"
echo "============================================"
