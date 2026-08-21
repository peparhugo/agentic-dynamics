# Agentic Dynamics — Reproduction Environment
#
# Build:  docker build -t agentic-dynamics .
#
# Run (CORE pipeline — deterministic, canonical registry only, no external services):
#   docker run --rm \
#     -v ~/.opencode/bin/opencode:/usr/local/bin/opencode \
#     -v ~/.local/share/opencode/opencode.db:/root/.local/share/opencode/opencode.db \
#     -v $(pwd)/experiments/results:/app/experiments/results \
#     -v $(pwd)/apps/website:/app/apps/website \
#     -v $(pwd)/experiments/data_manifest.json:/app/experiments/data_manifest.json \
#     -e FINOPS_WORKTREE_ROOT=/app/experiments/results/artifacts \
#     agentic-dynamics
#
# Persistence: the CORE run rewrites several outputs — apps/website/data.js,
# experiments/data_manifest.json, experiments/inventory.json, experiments/data/*.parquet,
# and experiments/results/lab_*.json. Mount the two directories (results/, apps/website/)
# AND the manifest file (experiments/data_manifest.json, a single file OUTSIDE the results/
# mount) to keep them; without the mounts they live only in the container's writable layer
# and vanish with `--rm`. inventory.json and data/*.parquet are deterministic recomputes
# (steps 1-2) and are deliberately not persisted — the manifest is the load-bearing output
# because the lab-contract identity hashes the registry it embeds.
#
# Opt-in external-service labs (append the flag to the entrypoint; the entrypoint
# is `reproduce.sh core`, so appended args follow it):
#   docker run ... agentic-dynamics --with-neo4j   # + Neo4j basin lab (Neo4j on :7687)
#   docker run ... agentic-dynamics --with-sonar   # + SonarQube analysis (SonarQube on :9000)
# Override the entrypoint with: docker run ... agentic-dynamics bash

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for opencode (ELF binary may need these)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python package (base deps cover the CORE pipeline: duckdb/pyarrow
# for sync_data, tree-sitter for analyze_worktrees, numpy/scikit-learn for the labs).
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .

# Copy scripts, scoring conventions, the app tier, and the canonical corpus.
# conventions/ is required by commit analysis (measurement.commit_analysis loads
# conventions/<lang>.yaml and silently falls back when absent); apps/ hosts the
# website build (apps/website/data.js) and the Control Room portal; the committed
# experiments/data_manifest.json is the canonical registry the labs read; the waivers
# directory carries the reason-bearing exemptions for the 10 payload-less story rows that
# build_data's fail-closed gate must find (canonical-publication closure, c2).
COPY scripts/ scripts/
COPY conventions/ conventions/
COPY apps/ apps/
COPY experiments/definitions/ experiments/definitions/
COPY experiments/results/ experiments/results/
COPY experiments/waivers/ experiments/waivers/
COPY experiments/specs/ experiments/specs/
COPY experiments/data_manifest.json experiments/data_manifest.json

# Ensure output directories exist (website + artifact scratch roots)
RUN mkdir -p /app/experiments/results/artifacts /app/apps/website

# Set worktree root to persistent volume path
ENV FINOPS_WORKTREE_ROOT=/app/experiments/results/artifacts

# Volume mount points for external dependencies
# - /usr/local/bin/opencode: the opencode CLI binary (manifest version stamp)
# - /root/.local/share/opencode/opencode.db: session cost data (warned if absent)
# - /app/experiments/results: lab outputs persistence (lab_*.json + game reports)
# - /app/apps/website: the rebuilt data.js persistence
# - /app/experiments/data_manifest.json: the regenerated manifest (single file — a separate
#   mount because it lives OUTSIDE /app/experiments/results)

# Default entrypoint runs the CORE reproduction pipeline (deterministic — no external
# services, canonical registry only). Append --with-neo4j / --with-sonar to opt in.
ENTRYPOINT ["bash", "scripts/reproduce.sh", "core"]
