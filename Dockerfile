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
#     -e FINOPS_WORKTREE_ROOT=/app/experiments/results/artifacts \
#     agentic-dynamics
#
# Persistence: the CORE run rewrites two outputs — apps/website/data.js and
# experiments/data_manifest.json (+ experiments/results/lab_*.json). Mount BOTH
# directories (as above) to keep them; without the mounts they live only in the
# container's writable layer and vanish with `--rm`. apps/website/ is mounted for
# data.js specifically (the review item 7 persistence fix).
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
# experiments/data_manifest.json is the canonical registry the labs read.
COPY scripts/ scripts/
COPY conventions/ conventions/
COPY apps/ apps/
COPY experiments/definitions/ experiments/definitions/
COPY experiments/results/ experiments/results/
COPY experiments/data_manifest.json experiments/data_manifest.json

# Ensure output directories exist (website + artifact scratch roots)
RUN mkdir -p /app/experiments/results/artifacts /app/apps/website

# Set worktree root to persistent volume path
ENV FINOPS_WORKTREE_ROOT=/app/experiments/results/artifacts

# Volume mount points for external dependencies
# - /usr/local/bin/opencode: the opencode CLI binary (manifest version stamp)
# - /root/.local/share/opencode/opencode.db: session cost data (warned if absent)
# - /app/experiments/results: lab outputs + regenerated data_manifest.json persistence
# - /app/apps/website: the rebuilt data.js persistence

# Default entrypoint runs the CORE reproduction pipeline (deterministic — no external
# services, canonical registry only). Append --with-neo4j / --with-sonar to opt in.
ENTRYPOINT ["bash", "scripts/reproduce.sh", "core"]
