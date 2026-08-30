#!/usr/bin/env bash
# fleet entrypoint — the binary-resolution probe (D-18) as the container-start assertion.
#
# Every cell/orchestrator/supervisor container starts by resolving the model CLI chains
# (opencode + claude) and FAILING LOUDLY on a broken one — a boot-time assertion, not a
# runtime surprise (the R1 canonical-env guarantee made structural). Services that never
# invoke a CLI (the kb consumers, the fleet manager itself) opt out with FLEET_SKIP_PROBE=1.
set -euo pipefail

# The D-2 auth seeding (smoke-test revision, 2026-08-30): the credential files mount ro at
# /auth/... — seed them into the ISOLATED per-cell CLI state (rw) so the CLIs find their
# credentials without the host's live state ever entering the cell. Idempotent: an existing
# state auth is never overwritten.
if [ -f /auth/opencode_auth.json ]; then
    mkdir -p /home/drseuss/.local/share/opencode
    if [ ! -f /home/drseuss/.local/share/opencode/auth.json ]; then
        cp /auth/opencode_auth.json /home/drseuss/.local/share/opencode/auth.json
        chmod 600 /home/drseuss/.local/share/opencode/auth.json
    fi
fi

if [ "${FLEET_SKIP_PROBE:-0}" != "1" ]; then
    python3 /app/scripts/fleet/probe_binaries.py
fi

exec "$@"
