# AI FinOps Framework — Reproduction Environment
# 
# Build:  docker build -t ai-finops-framework .
# Run:    docker run --rm \
#           -v ~/.opencode/bin/opencode:/usr/local/bin/opencode \
#           -v ~/.local/share/opencode/opencode.db:/root/.local/share/opencode/opencode.db \
#           -v $(pwd)/experiments/results:/app/experiments/results \
#           -e FINOPS_WORKTREE_ROOT=/app/experiments/results/artifacts \
#           ai-finops-framework

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for opencode (ELF binary may need these)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python package
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .

# Copy scripts and experiments config
COPY scripts/ scripts/
COPY experiments/configs/ experiments/configs/
COPY experiments/results/ experiments/results/

# Ensure artifacts directory exists
RUN mkdir -p /app/experiments/results/artifacts

# Set worktree root to persistent volume path
ENV FINOPS_WORKTREE_ROOT=/app/experiments/results/artifacts

# Volume mount points for external dependencies
# - /usr/local/bin/opencode: the opencode CLI binary
# - /root/.local/share/opencode/opencode.db: session cost data
# - /app/experiments/results: for output persistence

# Default entrypoint runs the reproduction pipeline
# Override with: docker run ... ai-finops-framework bash
ENTRYPOINT ["bash", "scripts/reproduce.sh"]
