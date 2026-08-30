#!/usr/bin/env bash
# fleet entrypoint — the binary-resolution probe (D-18) as the container-start assertion.
#
# Every cell/orchestrator/supervisor container starts by resolving the model CLI chains
# (opencode + claude) and FAILING LOUDLY on a broken one — a boot-time assertion, not a
# runtime surprise (the R1 canonical-env guarantee made structural). Services that never
# invoke a CLI (the kb consumers, the fleet manager itself) opt out with FLEET_SKIP_PROBE=1.
set -euo pipefail

if [ "${FLEET_SKIP_PROBE:-0}" != "1" ]; then
    python3 /app/scripts/fleet/probe_binaries.py
fi

exec "$@"
