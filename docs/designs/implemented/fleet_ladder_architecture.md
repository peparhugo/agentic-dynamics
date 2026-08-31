---
status: implemented
implemented_by: workflows/repository/fleet_ladder_implementation.yaml
spec_sha256: 0d30d4bc6d6014c8f1d2283aaad88c79dd9b6d749ca9a48e6b028f35ff733589
---

# Fleet ladder - containerized execution, supervised fleet, master control

## Status and evidence

[C] This document moved from `docs/designs/proposed/` to the implemented-design tree because the
accepted logs record PASS for all four implementation slices and the compose file declares the
cell, orchestrator, and supervisor service groups (`docs/fleet/04_slice1_live_cutover_log.md:12-18`,
`05_slice2_orchestrator_log.md:12-17`, `06_slice3_neo4j_rrf_log.md:12-17`,
`07_slice4_guards_log.md:12-18`, `infrastructure/docker-compose.ladder.yml:90-137,139-339`).

[M] The implementation was exercised by the `fleet_ladder_implementation` workflow and the
containerized `green_main_closure` run completed successfully in `/tmp/wt_green_main`
(`experiments/results/workflows/fleet_ladder_implementation/20260830T191351Z.json:48-55`,
`experiments/results/workflows/green_main_closure/20260831T201627Z.json:2-14`).

## Implemented topology

[M] The ladder has three runtime roles: cell services process one queue job at a time; the
orchestrator runs campaign/workflow wrappers and can spawn sibling cells; supervisor services run
the fleet manager, Control Room, game board, and review trigger
(`infrastructure/docker-compose.ladder.yml:139-339`). [P] The controller remains outside the
ladder and is the sole permanence authority.

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

[M] The mount contract permits a closed set of targets: worktree, repository aliases with writable
`.git` overlays, results, isolated OpenCode state, and read-only credential/configuration mounts
(`infrastructure/docker-compose.ladder.yml:49-88`). It is deliberately not described as exactly
four host paths; the earlier literal claim was falsified by the compose inventory.

[M] The closed `SCOPE_VOCABULARY`, `SCOPE_CONFIGS`, and `PHASE_SCOPE_AUTHORIZATION` declare the
allowed phase scopes, result modes, network, and write flags
(`src/agentic_dynamics/experiment/experiment_spec.py:65-133`). [M] The slice-2 validation tests
prove invalid scopes, unauthorized phases, and bad mounts fail before a socket call
(`docs/fleet/05_slice2_orchestrator_log.md:80-91`).

[M] The accepted slice-4 guard log records checks for the mount targets, single socket tier,
supervisor restrictions, heartbeats/DLQ, single write-back, scope vocabulary, and network membership
(`docs/fleet/07_slice4_guards_log.md:20-37`).

## Knowledge and network evidence

[M] The live `kb-neo4j-v1` cell consumer reaches Neo4j by name, drained its pending stream group,
and contributed a lexical leg to RRF retrieval (`docs/fleet/06_slice3_neo4j_rrf_log.md:14-37`,
`70-93`).

[M] `fleet-net` excludes `finops-redis` and the live cutover observed the story sandbox as
structurally unreachable from cells (`infrastructure/docker-compose.ladder.yml:344-351`,
`docs/fleet/04_slice1_live_cutover_log.md:57-61`).

[C] The egress proxy is defined but is not the enforced sole Internet route: the cells do not set
`HTTP_PROXY` or `HTTPS_PROXY`, so direct bridge-NAT egress remains possible
(`docs/fleet/04_slice1_live_cutover_log.md:126-134`,
`docs/reviews/fleet_ladder_implementation_adversary.md:15-18`, `50-70`). [P] This limitation stays
open until a documented operator-approved remediation or deferral closes it.

## Historical proposal record

[M] The earlier proposed document described the intended slice sequence and the missing Neo4j
consumer. The accepted slice logs above are the current implementation evidence; the proposal is
preserved in this document's history rather than represented as a current implementation plan.
