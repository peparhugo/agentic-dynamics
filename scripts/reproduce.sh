#!/bin/bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Agentic Dynamics — Reproduction Pipeline
# ---------------------------------------------------------------------------
# Rebuilds the analysis and presentation layer from existing experiment
# artifacts. Does NOT rerun experiments (no inference, no queue, no Redis).
#
# Modes (the review item 7 split — semantic-integrity release):
#
#   scripts/reproduce.sh                # == "core": deterministic, no external
#   scripts/reproduce.sh core           #    services, canonical registry only
#
#   scripts/reproduce.sh --with-neo4j   # core + the Neo4j basin-topology lab
#   scripts/reproduce.sh --with-sonar   # core + SonarQube analysis + the sonar lab
#   scripts/reproduce.sh --dry-run      # print every step, execute nothing
#
# The CORE lab set is derived from scripts/lab_manifest.json (reproduce_default: true)
# — the canonical, contract-bearing labs. The quarantined labs that need an external
# service are NOT in the core set; they are reachable only through the opt-in flags:
#
#   --with-neo4j  appends lab_basin_topology_neo4j.py (needs a Neo4j server on :7687
#                 and the `neo4j` optional dependency: pip install -e ".[neo4j]").
#   --with-sonar  re-enables SonarQube in analyze_worktrees.py (needs a SonarQube
#                 server on :9000) and appends lab_sonar_quality.py.
#
# Core determinism: analyze_worktrees.py runs with `--no-tests --no-sonar` so the
# core makes no network call (the per-worktree pytest venv) and touches no external
# service. Per-worktree pytest and SonarQube are measurement enrichments, not part
# of the canonical-corpus derivation the labs consume, so they are opt-in.
#
# Steps (in dependency order):
#   1. inventory.py refresh       — rebuild experiments/inventory.json
#   2. sync_data.py               — story results -> sessions.parquet/stories.parquet
#   3. analyze_worktrees.py       — per-experiment Game Report markdown
#   4. analyze_trajectories.py    — per-transcript trajectory summaries
#   5. lab books                  — per-question analyses -> experiments/results/lab_*.json
#   6. build_data.py              — apps/website/data.js (the website corpus)
#   7. generate_manifest.py       — experiments/data_manifest.json (hashes the outputs)
#
# Prerequisites:
#   - opencode CLI (in PATH or ~/.opencode/bin/) — only for the manifest version stamp
#   - Python 3.10+ (deps: pip install -e ".")
#   - ~/.local/share/opencode/opencode.db (session data; warned-and-continued if absent)
#   - Optional: FINOPS_WORKTREE_ROOT (default /tmp)
# ---------------------------------------------------------------------------

DRY_RUN=0
WITH_NEO4J=0
WITH_SONAR=0

# ---------------------------------------------------------------------------
# Argument parsing. `core` is an explicit no-op (it is the default); the two
# `--with-*` flags opt quarantined external-service labs back in. Flags may appear
# in any order, so the Docker ENTRYPOINT `reproduce.sh core` plus an operator's
# `--with-sonar` (appended) both parse.
# ---------------------------------------------------------------------------
for arg in "$@"; do
  case "$arg" in
    core)
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    --with-neo4j)
      WITH_NEO4J=1
      ;;
    --with-sonar)
      WITH_SONAR=1
      ;;
    -h|--help)
      echo "Usage: $0 [core] [--with-neo4j] [--with-sonar] [--dry-run]"
      echo ""
      echo "Rebuild the analysis + presentation layer from existing experiment artifacts."
      echo "  core           deterministic core (default): canonical labs only, no external services"
      echo "  --with-neo4j   also run lab_basin_topology_neo4j.py (Neo4j on :7687)"
      echo "  --with-sonar   also run SonarQube analysis + lab_sonar_quality.py (SonarQube on :9000)"
      echo "  --dry-run      print every step that would run, without executing anything"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg (use --help)" >&2
      exit 2
      ;;
  esac
done

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
# Opt-in external-service labs (quarantined — their output goes to legacy_labs/
# and is NOT published by build_data.py). Appended only under their flag, never in
# the core set. This is the review item 7 move: the Neo4j basin lab is opt-in.
# ---------------------------------------------------------------------------
if [[ "$WITH_NEO4J" -eq 1 ]]; then
  LAB_BOOKS+=("lab_basin_topology_neo4j.py")
fi
if [[ "$WITH_SONAR" -eq 1 ]]; then
  LAB_BOOKS+=("lab_sonar_quality.py")
fi

# ---------------------------------------------------------------------------
# analyze_worktrees.py flags. Core: --no-tests --no-sonar (deterministic — no
# per-worktree pytest venv, no SonarQube). --with-sonar re-enables SonarQube.
# ---------------------------------------------------------------------------
ANALYZE_ARGS=(--no-tests --no-sonar)
if [[ "$WITH_SONAR" -eq 1 ]]; then
  ANALYZE_ARGS=(--no-tests)
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

MODE_LABEL="core"
if [[ "$WITH_NEO4J" -eq 1 ]]; then MODE_LABEL="${MODE_LABEL} + neo4j"; fi
if [[ "$WITH_SONAR" -eq 1 ]]; then MODE_LABEL="${MODE_LABEL} + sonar"; fi

echo "============================================"
echo " Agentic Dynamics — Reproduction Pipeline"
echo " Mode: ${MODE_LABEL}"
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
  python3 scripts/analyze_worktrees.py "${ANALYZE_ARGS[@]}"

run_step "Step 4/7: Analyze trajectories" \
  python3 scripts/analyze_trajectories.py

echo "--- Step 5/7: Run lab book analyses (${#LAB_BOOKS[@]} labs: ${MODE_LABEL}) ---"
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
