#!/usr/bin/env bash
# Review cut-over — the SEQUENCED migration (proposal §7 slice 1, D-10).
#
# The review path is a CUT-OVER, never additive: the host `trigger_reviews` runs
# `review_all` synchronously, so starting the containerized `review-unit`/`trigger-reviews`
# while the host copy still runs would double-review (the F-A6 failure). The order is:
#
#     1. STOP   — terminate the host `trigger_reviews` (the poller), so no new review
#                 cycles start.
#     2. DRAIN  — wait for the in-flight `review_all` (the synchronous runner it spawned)
#                 to exit, so no review is mid-flight when the container path starts.
#     3. START  — bring up the containerized `review-unit` + the supervisor-tier
#                 `trigger-reviews` (the compose services).
#
# Rollback (the inverse, also sequenced): `docker-compose stop` the two containerized
# services, then re-launch the host `trigger_reviews` — never both live at once.
#
# This script runs on the HOST (it needs host process visibility + the compose CLI); the
# supervisor container has neither (no socket, D-3/D-14). It is idempotent and safe to
# re-run: `stop`/`drain` are no-ops when the host process is already gone.
#
# Usage:
#   scripts/fleet/review_cutover.sh cutover              # stop -> drain -> start (the full sequence)
#   scripts/fleet/review_cutover.sh stop                 # only stop the host trigger_reviews
#   scripts/fleet/review_cutover.sh drain [--timeout N]  # only wait for in-flight review_all
#   scripts/fleet/review_cutover.sh start                # only start the containerized path
#   scripts/fleet/review_cutover.sh rollback             # the inverse sequence (container -> host)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/infrastructure/docker-compose.ladder.yml"
COMPOSE="${DOCKER_COMPOSE:-docker-compose}"

TRIGGER_PATTERN="scripts/trigger_reviews.py"
REVIEW_PATTERN="scripts/review_all.py"

log() { echo "[review-cutover] $*"; }

# host_pids <pattern> — PIDs whose command line matches <pattern> (host processes only).
host_pids() {
    pgrep -f "$1" 2>/dev/null || true
}

stop_host() {
    local pids
    pids="$(host_pids "$TRIGGER_PATTERN")"
    if [ -z "$pids" ]; then
        log "STOP: no host trigger_reviews running (already stopped)"
        return 0
    fi
    log "STOP: terminating host trigger_reviews pid(s): $pids"
    # SIGTERM first (graceful); the poller has no state to flush, so no SIGKILL needed.
    echo "$pids" | xargs -r kill -TERM 2>/dev/null || true
    sleep 2
    local remaining
    remaining="$(host_pids "$TRIGGER_PATTERN")"
    if [ -n "$remaining" ]; then
        log "STOP: trigger_reviews still alive ($remaining) — SIGKILL"
        echo "$remaining" | xargs -r kill -KILL 2>/dev/null || true
    fi
    log "STOP: host trigger_reviews stopped"
}

drain_reviews() {
    local timeout="${1:-600}"
    local waited=0
    while [ "$waited" -lt "$timeout" ]; do
        local pids
        pids="$(host_pids "$REVIEW_PATTERN")"
        if [ -z "$pids" ]; then
            log "DRAIN: no in-flight review_all (drained)"
            return 0
        fi
        log "DRAIN: waiting for in-flight review_all pid(s): $pids (${waited}s/${timeout}s)"
        sleep 5
        waited=$((waited + 5))
    done
    log "DRAIN: TIMEOUT after ${timeout}s — review_all still running: $(host_pids "$REVIEW_PATTERN")" >&2
    return 1
}

start_container() {
    log "START: bringing up the containerized review path (review-unit + trigger-reviews)"
    "$COMPOSE" -f "$COMPOSE_FILE" up -d trigger-reviews review-unit
    log "START: containerized review path is up"
}

stop_container() {
    log "ROLLBACK: stopping the containerized review path"
    "$COMPOSE" -f "$COMPOSE_FILE" stop trigger-reviews review-unit || true
}

cmd="${1:-cutover}"
case "$cmd" in
    stop)
        stop_host
        ;;
    drain)
        shift || true
        timeout=600
        [ $# -gt 0 ] && timeout="${2:-600}"
        drain_reviews "$timeout"
        ;;
    start)
        start_container
        ;;
    cutover)
        stop_host
        drain_reviews
        start_container
        ;;
    rollback)
        stop_container
        # Re-launch the host path (the operator's own responsibility to detach; documented).
        log "ROLLBACK: re-launch host trigger_reviews with:"
        log "    setsid nohup python3 \"$REPO_ROOT/scripts/trigger_reviews.py\" &"
        ;;
    *)
        echo "usage: $0 {cutover|stop|drain|start|rollback}" >&2
        exit 2
        ;;
esac

log "review cut-over step '$cmd' complete"
