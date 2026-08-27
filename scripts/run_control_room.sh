#!/usr/bin/env bash
# Control Room respawn supervisor (the 8001 service died silently three times —
# this loop restarts it on death with a short backoff; logs rotate by truncation).
# Usage: bash scripts/run_control_room.sh   (detach with setsid nohup)

set -u
export FINOPS_PORT="${FINOPS_PORT:-8001}"
export FINOPS_HOST="${FINOPS_HOST:-0.0.0.0}"
LOG="${CONTROL_ROOM_LOG:-/tmp/control_room.log}"

while true; do
    echo "[$(date -Is)] control_room starting (port ${FINOPS_PORT})" >>"$LOG"
    python3 "$(dirname "$0")/../apps/control_room/server.py" >>"$LOG" 2>&1
    rc=$?
    echo "[$(date -Is)] control_room exited rc=${rc}; restarting in 5s" >>"$LOG"
    sleep 5
done
