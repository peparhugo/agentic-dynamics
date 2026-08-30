#!/usr/bin/env bash
# Build the fleet images (docker-native).
#
# Stages the sonar client into the build context (it lives on the host at
# /tmp/sonar-scanner-6.2.1.4610 — ephemeral, so it is BAKED, not mounted; D-18/§4) and then
# builds the three ladder targets. The staging dir `.build/` is gitignored (a build artifact,
# not provenance).
#
# Usage:
#   scripts/fleet/build.sh                 # build base + orchestrator + supervisor
#   scripts/fleet/build.sh base            # build only fleet/base (slice 1's build test)
#   scripts/fleet/build.sh base --no-cache # force a clean rebuild
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD_DIR="$REPO_ROOT/.build"
SONAR_STAGED="$BUILD_DIR/sonar-scanner"

# The host's sonar client (pinned version 6.2.1.4610 — the inventory's own number; the
# on-disk dir carries the `-linux-x64` suffix, matching ~/.local/bin/sonar-scanner's target).
SONAR_HOST_DIR="/tmp/sonar-scanner-6.2.1.4610-linux-x64"
SONAR_PINNED_URL="https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-6.2.1.4610-linux-x64.zip"

log() { echo "[build] $*"; }

stage_sonar() {
    # Idempotent: re-use the staged copy if it is already populated.
    if [ -d "$SONAR_STAGED/bin" ]; then
        log "sonar client already staged at $SONAR_STAGED"
        return 0
    fi
    mkdir -p "$BUILD_DIR"
    if [ -d "$SONAR_HOST_DIR" ]; then
        log "staging sonar client from $SONAR_HOST_DIR"
        cp -a "$SONAR_HOST_DIR" "$SONAR_STAGED"
        return 0
    fi
    # Fallback: pinned download (same released version), then a shim-less unpack.
    log "host sonar client absent — downloading pinned 6.2.1.4610"
    curl -fsSL "$SONAR_PINNED_URL" -o "$BUILD_DIR/sonar-scanner.zip"
    unzip -q -o "$BUILD_DIR/sonar-scanner.zip" -d "$BUILD_DIR"
    mv "$BUILD_DIR/sonar-scanner-cli-6.2.1.4610-linux-x64" "$SONAR_STAGED"
    rm -f "$BUILD_DIR/sonar-scanner.zip"
}

build_target() {
    local target="$1"; shift
    log "building fleet/$target (docker build --target $target)"
    docker build -f "$REPO_ROOT/Containerfile.fleet" --target "$target" \
        -t "fleet/$target" "$@" "$REPO_ROOT"
}

stage_sonar

case "${1:-all}" in
    base)         build_target base ;;
    orchestrator) build_target orchestrator ;;
    supervisor)   build_target supervisor ;;
    all)
        build_target base
        build_target orchestrator
        build_target supervisor
        ;;
    *)
        echo "usage: $0 {base|orchestrator|supervisor|all} [extra docker build args...]" >&2
        exit 2
        ;;
esac

log "done"
