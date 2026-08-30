#!/usr/bin/env bash
# Attach the data plane to `fleet-net` — the D-17 wiring (proposal §2/§3).
#
# `fleet-net` is the CELL network: it carries ONLY the queue redis (finops-queue, 6380),
# chroma (chromadb, 8000), neo4j (7687), the four sonar instances (9000-9003) — and the
# egress proxy. `finops-redis` (6379) and `redis-test` (6399) are deliberately NEVER
# attached: the cells hold no network path to the story-agent sandbox or the scratch redis
# (the two-channel rule made topological, D-17).
#
# The data plane lives in the OTHER infrastructure/ compose files (docker-compose.yml,
# docker-compose.sonar.yml, docker-compose.experiment.yml) with their own networks, so this
# script connects the running containers to fleet-net BY NAME — a docker-native `docker
# network connect`, idempotent (connecting an already-attached container is a no-op warning).
#
# Usage: scripts/fleet/attach_data_plane.sh   (run on the host; requires docker + fleet-net)
set -euo pipefail

# The allowed data-plane services (D-17). NOT here: finops-redis, redis-test, opencode-server.
ALLOWED=(finops-queue chromadb neo4j sonarqube sonarqube-9001 sonarqube-9002 sonarqube-9003)
NET="${FLEET_NET:-fleet-net}"

log() { echo "[attach-data-plane] $*"; }

# Ensure fleet-net exists (docker-compose creates it on first `up`; create it here so the
# attach can precede any `up`).
if ! docker network inspect "$NET" >/dev/null 2>&1; then
    log "creating network $NET"
    docker network create "$NET"
fi

for c in "${ALLOWED[@]}"; do
    if ! docker inspect "$c" >/dev/null 2>&1; then
        log "SKIP $c (not running)"
        continue
    fi
    if docker network inspect "$NET" --format '{{range .Containers}}{{.Name}} {{end}}' \
        | grep -qw "$c"; then
        log "OK    $c (already on $NET)"
        continue
    fi
    docker network connect "$NET" "$c"
    log "ATTACHED $c -> $NET"
done

log "done. finops-redis (6379) and redis-test (6399) intentionally NOT attached."
