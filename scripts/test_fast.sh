#!/usr/bin/env bash
# The fast-path test command (test_suite_speed p3): the `fast`-marked subset — the sub-minute
# guards + the audited pure-unit families — with NO real subprocesses, NO Redis/stores/ports,
# NO real worktrees. Budget: sub-3-minutes (measured 2026-09-01: 509 tests in ~25s).
#
# This is the smoke the guards/CI run on every change. The full suite stays runnable on
# demand (`python3 -m pytest tests/ -q`) and stays green.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pytest tests/ -m fast -q -p no:cacheprovider "$@"
