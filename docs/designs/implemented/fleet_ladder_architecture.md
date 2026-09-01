---
status: implemented
implemented_by: workflows/repository/fleet_ladder_implementation.yaml
spec_sha256: 55b910db25c795a3d63cdf6c27cba225ee202598c9b8861e8f4bd50f1ef78233
---

# Fleet ladder - containerized execution, supervised fleet, master control

## Status and evidence

[C] This document moved from `docs/designs/proposed/` to the implemented-design tree because the
accepted logs record PASS for all four implementation slices and the compose file declares the
cell, orchestrator, and supervisor service groups (`docs/fleet/04_slice1_live_cutover_log.md:12-18`,
`docs/fleet/05_slice2_orchestrator_log.md:12-17`,
`docs/fleet/06_slice3_neo4j_rrf_log.md:12-17`,
`docs/fleet/07_slice4_guards_log.md:12-18`,
`infrastructure/docker-compose.ladder.yml:90-137,139-339`).

[M] The implementation was exercised by the `fleet_ladder_implementation` workflow and the
`green_main_closure` ledger records a successful run in `/tmp/wt_green_main`
(`experiments/results/workflows/fleet_ladder_implementation/20260830T191351Z.json:48-55`,
`experiments/results/workflows/green_main_closure/20260831T201627Z.json:2-14`). [C] The latter
ledger does not identify the execution runtime, so it is not container-execution evidence.

## Implemented topology

[M] The ladder has three runtime roles. Cell services are long-running units: the
story/analysis/review workers are BRPOP queue consumers that process one queue job at a time, the
`kb-*` stream consumers (`kb-chroma`, `kb-ledger`, `kb-registry`, `kb-neo4j`) run continuously
against the KB stream, and the batch producers run to completion once; the
orchestrator runs campaign/workflow wrappers and can spawn sibling cells; supervisor services run
the fleet manager, Control Room, game board, and review trigger
(`infrastructure/docker-compose.ladder.yml:139-339,144-257`). [P] The controller remains outside the
ladder and is the sole permanence authority
(`docs/designs/proposed/system_knowledge_abstraction.md:77-81`).

[M] `Containerfile.fleet` defines `fleet/base`, `fleet/orchestrator`, and `fleet/supervisor`
targets (`Containerfile.fleet:3-23`, `112-143`). The active compose supervisor base presently uses
`fleet/base`; the defined supervisor target is not yet wired (`infrastructure/docker-compose.ladder.yml:99-106`,
`docs/reviews/fleet_ladder_implementation_adversary.md:17-18`).

[M] Cell services use restart policies, worker heartbeats, and per-queue DLQ accounting; slice 1
observed queue draining without duplicate processing and surfaced heartbeats and DLQ counts on
`fleet:board` (`docs/fleet/04_slice1_live_cutover_log.md:14-18`, `45-77`).

[M] The orchestrator is the only socket-holder: its read-only Docker socket is declared in
`x-orchestrator-mounts`, while supervisor services hold no socket
(`infrastructure/docker-compose.ladder.yml:108-137`, `286-293`). `spawn_wrapper.validate_spawn()`
performs scope, authorization, mount, network, and write-flag checks before `spawn_sibling()` can
build or run the Docker command (`scripts/fleet/spawn_wrapper.py:155-240`, `317-348`).

## Mount and scope contract

[M] Compose declares mounts for the worktree, repository aliases with writable `.git` overlays,
results, a shared OpenCode-state directory, and read-only credential/configuration paths
(`infrastructure/docker-compose.ladder.yml:49-88`). [C] The state mount excludes the host's live
OpenCode state but is shared by scaled cell services, so it is not per-cell state isolation
(`infrastructure/docker-compose.ladder.yml:57-64,90-97,143-155`). [C] The mount guard's allowlist
now covers compose's repository-alias and `.git` overlay targets, mirroring the wrapper's runtime
`CONTRACT_TARGETS` (`scripts/fleet/spawn_wrapper.py:79-97`); `test_mount_contract_holds_no_unexpected_target`
passes and `test_mount_guard_rejects_a_foreign_target` proves the guard still fails on an invented
foreign target — the guard is not weakened (`tests/test_fleet_guards.py:86-102,136-153`).

[M] The closed `SCOPE_VOCABULARY`, `SCOPE_CONFIGS`, and `PHASE_SCOPE_AUTHORIZATION` declare the
allowed phase scopes, result modes, network, and write flags
(`src/agentic_dynamics/experiment/experiment_spec.py:49-133`). [M] The slice-2 validation tests
prove invalid scopes, unauthorized phases, and bad mounts fail before a socket call
(`docs/fleet/05_slice2_orchestrator_log.md:80-91`).

[M] The accepted slice-4 guard log records the then-run checks for mount targets, the single socket
tier, supervisor restrictions, heartbeats/DLQ, single write-back, scope vocabulary, and network
membership (`docs/fleet/07_slice4_guards_log.md:20-37`). [P] It is historical evidence and is kept
distinct from the current mount-guard state above (which now passes).

## Knowledge and network evidence

[M] The live `kb-neo4j-v1` cell consumer reaches Neo4j by name, drained its pending stream group,
and contributed a lexical leg to RRF retrieval (`docs/fleet/06_slice3_neo4j_rrf_log.md:14-37`,
`70-93`).

[M] `fleet-net` excludes `finops-redis` and the live cutover observed the story sandbox as
structurally unreachable from cells (`infrastructure/docker-compose.ladder.yml:344-351`,
`docs/fleet/04_slice1_live_cutover_log.md:57-61`).

[C] The egress proxy is the declared policy point, but it is not the enforced route: the cells do
not set `HTTP_PROXY` or `HTTPS_PROXY`, so direct bridge-NAT egress is the current operating state
(`docs/fleet/04_slice1_live_cutover_log.md:126-134`,
`docs/reviews/fleet_ladder_implementation_adversary.md:15-18,50-70`). [P] The proxy becomes the
enforced route only when a scope configures it — recorded as current reality, not as a pending fix.
