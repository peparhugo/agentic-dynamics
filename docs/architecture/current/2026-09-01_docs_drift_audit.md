---
status: accepted
---

# Documentation Drift Audit — 2026-09-01

## Scope and method

[P] This is the p1 inventory only. It records documentation-to-tree drift and does not change an architectural document, a configuration source, or a derived surface.

[M] The audit was taken from checkout `196e5682292800f630917baadec2a7191aea596e` on 2026-09-01. File anchors are repository-relative and refer to that checkout.

[P] `current` means the cited documentation agrees with the cited implementation or guard. `stale` means a documented claim contradicts the cited implementation or newer committed state. `missing` means the documented authority has no coverage for an implemented concern or a required inventory domain.

[P] `[M]` denotes a directly observed file, test, or command result. `[C]` denotes a deterministic comparison of those observations. No finding below relies on an unanchored heuristic.

## Starting-hypothesis verdicts

| Hypothesis | Verdict | Evidence |
|---|---|---|
| (a) `ARCHITECTURE.md` has no Docker/fleet/container/isolation coverage and no context-compiler section. | **PARTIAL FAIL [C].** It has a substantive Context Abstraction Plane map, but no Docker/fleet/container or container-isolation section. | Context map: `ARCHITECTURE.md:155-182`; no Docker/fleet/container section in the architectural authority; implemented fleet: `infrastructure/docker-compose.ladder.yml:1-15`. |
| (b) The fleet-ladder design remains proposed although slices 1–2 are implemented. | **CONFIRMED AT AUDIT, RESOLVED [C]** by the post-audit move: the design now sits in the implemented tree with `status: implemented` and records the slice evidence. | Design: `docs/designs/implemented/fleet_ladder_architecture.md:9-23` (status + evidence; supersedes the audit-time proposed location); logs: `docs/fleet/04_slice1_live_cutover_log.md:5-18`, `05_slice2_orchestrator_log.md:5-17`, `06_slice3_neo4j_rrf_log.md:5-16`, `07_slice4_guards_log.md:5-18`; compose: `infrastructure/docker-compose.ladder.yml:90-137,139-339`. |
| (c) `.opencode/`, `.claude/`, and `CONTEXT.md` manifests may lag code. | **PARTIAL FAIL [C].** The generated trees match their renderers and have no generated-file orphans; their source snapshot and two root instruction references are stale, and `scripts/CONTEXT.md` has inventory/count drift. | Renderer map: `scripts/_gen_instructions.py:47-57,171-198,235-261`; guard: `tests/test_agent_config_render.py:147-193`; observed guard result: 12 passed; stale sources: `agent_config/system_snapshot.md:7`, `CLAUDE.md:16-17`, `AGENTS.md:9-10`, `scripts/CONTEXT.md:3-16`. |
| (d) Some `cap_*` designs in `docs/architecture/current/` have implementation status that no longer matches code. | **CONFIRMED [C].** Five accepted CAP design/migration documents still describe completed mechanisms as future, absent, or manual. | Inventory rows C2–C7 below. |
| (e) `scripts/CONTEXT.md` classifications and line counts may differ from the scripts on disk. | **PARTIAL FAIL [C].** The Python classification is complete and CLI-reachable, but its headline/count tables and non-Python coverage are stale or incomplete. | Guard: `tests/test_script_classification.py:45-72`; observed guard result: 12 passed; manifest/table: `scripts/CONTEXT.md:3-16,41-45,53-71,77-133`. |

## PASS/FAIL register

| Axis | Result | Current | Stale | Missing |
|---|---:|---:|---:|---:|
| Layers | **FAIL [C]** | 1 | 5 | 1 |
| Context | **FAIL [C]** | 1 | 6 | 0 |
| Docker | **FAIL [C]** | 0 | 4 | 1 |
| Isolation | **FAIL [C]** | 1 | 2 | 1 |
| Surfaces | **FAIL [C]** | 2 | 6 | 1 |
| **Total** | **FAIL [C]** | **5** | **23** | **4** |

[P] Counts are counts of the findings in the five detailed tables below. A finding may cover multiple affected files only where they make one indivisible claim, such as the generated snapshot source and its two rendered copies.

## Layers

| Doc | Claim | Code truth | Status |
|---|---|---|---|
| `ARCHITECTURE.md:20-49` | [M] Eight bounded planes are the package map; the physical tree has “59 live modules.” | [C] The eight named package initializers exist and agree on the plane names: `src/agentic_dynamics/{core,experiment,measurement,runtime,adapters,knowledge,control,reporting}/__init__.py:1`. The tree contains 107 tracked Python files under those planes, not 59. | **STALE** |
| `ARCHITECTURE.md:61-66,107-115` | [M] The tier table includes adapters and reporting, but the textual dependency spine omits both. | [C] `adapters` and `reporting` are tier-1 planes in the table and have package maps at `src/agentic_dynamics/adapters/__init__.py:1-12` and `src/agentic_dynamics/reporting/__init__.py:1-35`. | **STALE** |
| `src/agentic_dynamics/core/__init__.py:10-16` | [M] `contracts.py` is reserved and empty until a future CAP implementation. | [M] `FactRequirement` and the fact-contract validator are implemented in `src/agentic_dynamics/core/contracts.py:46-109`. | **STALE** |
| `src/agentic_dynamics/experiment/__init__.py:7-13` | [M] `JobRecord` and `AttemptRecord` are deferred primitives. | [M] The runtime owns and implements workflow attempt records in `src/agentic_dynamics/runtime/workflow_runner.py:411-464`; the package summary must state the actual ownership rather than a blanket deferral. | **STALE** |
| `src/agentic_dynamics/measurement/__init__.py:1-28` | [M] The measurement ownership and export map enumerates its public modules. | [M] `measurement/signal_registry.py` is implemented and defines the single measured-signal contract at `src/agentic_dynamics/measurement/signal_registry.py:1-23,54-118`, but is absent from the package summary and exports. | **MISSING** |
| `src/agentic_dynamics/reporting/__init__.py:3-10` | [M] The publication boundary contains “three cooperating modules,” followed by four module entries. | [C] The count conflicts with the four listed modules in the same docstring. | **STALE** |
| `ARCHITECTURE.md:37` | [M] The knowledge plane has “nine ingestion producers.” | [C] Its package map names eight producer modules at `src/agentic_dynamics/knowledge/__init__.py:13-30`; the architecture count is not reconciled to the actual public map. | **STALE** |

## Context

| Doc | Claim | Code truth | Status |
|---|---|---|---|
| `ARCHITECTURE.md:155-182` | [M] CAP I0-I7 plus the named addenda are implemented, with a current consumption map. | [M] The implementation anchors cited by the table exist, including the reducer registry at `src/agentic_dynamics/control/reducers/__init__.py:1-67`. This disproves hypothesis (a)'s “no context-compiler section” portion. | **CURRENT** |
| `src/agentic_dynamics/control/__init__.py:5-29` | [M] The package points to `docs/designs/current/context_abstraction_design.md` and describes the plane only through I0-I7, zero call sites, and all seams off by default. | [M] The design is at `docs/architecture/current/context_abstraction_design.md:1-13`; I8-I10 are registered at `src/agentic_dynamics/control/reducers/__init__.py:1-21,41-67`; the current architecture records an applied cap_2b path at `ARCHITECTURE.md:172-179`. | **STALE** |
| `docs/architecture/current/context_abstraction_design.md:6-13` | [M] The document is design-only and says nothing in it is implemented. | [M] `control/context_compiler.py` is an implemented CAP module according to `ARCHITECTURE.md:167`, and the context package includes current CAP implementations at `src/agentic_dynamics/control/__init__.py:35-51`. | **STALE** |
| `docs/architecture/current/cap_fact_auto_emit_design.md:26-37` | [M] No workflow-completion path emits facts; only a manual batch producer exists. | [M] The test-runner wiring document records the default-on `_emit_workflow_facts` path at `docs/architecture/current/cap_test_runner_wiring.md:63-70`; `ARCHITECTURE.md:166` also records the workflow-completion auto-emit hook. | **STALE** |
| `docs/architecture/current/cap_gate_migration.md:45-59` | [M] No reducer consumes the story/experiment ledger and the fact plane has five reducers. | [M] `story_facts/v1` is registered at `src/agentic_dynamics/control/reducers/__init__.py:38,48,62`; `cap_story_bridge.md:134-152` documents the resulting story predicates. | **STALE** |
| `docs/architecture/current/cap_evidence_integrity_design.md:7-10,114-143` | [M] Evidence integrity is the next implementation stream and lists the analyzer, CodeDelta, and code-change facts as future phases. | [M] `control/evidence_analyzer.py` implements the phase-boundary flow, including `CodeSnapshot/CodeDelta` and `code_change_facts/v2`, at `src/agentic_dynamics/control/evidence_analyzer.py:1-26`; the reducer is registered at `control/reducers/__init__.py:30-33,52,66`. | **STALE** |
| `docs/architecture/current/cap_runner_hardening2_design.md:139-149` | [M] Orphan sweep, relabel gate, checkpoints, and adversarial verification are campaign work to implement. | [M] The runtime implements relabel and checkpoint gates at `src/agentic_dynamics/runtime/workflow_runner.py:45-80` and identifies the implemented orphan sweep at `:82-87`. | **STALE** |
| `docs/architecture/current/cap_story_bridge.md:143-145` | [M] Story confidence facts are ADVISORY/[H] and can bind as `requires_facts`. | [P] `FactRequirement` defaults to `min_authority="DERIVED"` at `src/agentic_dynamics/core/contracts.py:59-65`; the document needs an explicit valid authority/consumer contract before presenting that binding as usable. | **STALE** |

## Docker

| Doc | Claim | Code truth | Status |
|---|---|---|---|
| `ARCHITECTURE.md:1-277` | [C] The single architectural authority covers planes, boundaries, CAP, and the canonical loop, but has no Docker/fleet/container topology, service ownership, image, or lifecycle section. | [M] The implemented fleet has cell, orchestrator, and supervisor service groups in `infrastructure/docker-compose.ladder.yml:90-137,139-339`, plus a three-stage image definition in `Containerfile.fleet:120-143`. | **MISSING** |
| `docs/designs/implemented/fleet_ladder_architecture.md:9-23` | [M] The design's status-and-evidence section records `status: implemented` and cites the accepted slice logs; the audit-time “proposed / slice 1 is the first implementation” claim is gone. | [M] Accepted logs record PASS for slices 1–4 at `docs/fleet/04_slice1_live_cutover_log.md:5-18`, `05_slice2_orchestrator_log.md:5-17`, `06_slice3_neo4j_rrf_log.md:5-16`, and `07_slice4_guards_log.md:5-18`. | **RESOLVED** — the post-audit move closed the proposed-vs-implemented drift |
| `docs/designs/implemented/fleet_ladder_architecture.md:74-78` | [M] The implemented design records the live `kb-neo4j-v1` cell consumer and its RRF lexical-leg contribution — no “missing/dead consumer to be built” claim. | [M] `kb-neo4j` is declared at `infrastructure/docker-compose.ladder.yml:185-193`; the slice-3 log records its live consumer and RRF validation at `docs/fleet/06_slice3_neo4j_rrf_log.md:18-37,70-79`. | **RESOLVED** — the post-audit move re-stated the consumer as live |
| `docs/fleet/00_proposal.md:112` | [M] The in-network queue configuration uses port 6380. | [M] Compose uses the queue container's internal port 6379 at `infrastructure/docker-compose.ladder.yml:22-32`; the slice-1 correction is recorded at `docs/fleet/04_slice1_live_cutover_log.md:79-85`. | **STALE** |
| `docs/designs/implemented/fleet_ladder_architecture.md:37-40` | [M] The implemented design records that the active supervisor base uses `fleet/base` and the defined `fleet/supervisor` target is not yet wired. | [M] The image stage exists at `Containerfile.fleet:134-143`, but `x-supervisor-base` uses `fleet/base` in `infrastructure/docker-compose.ladder.yml:99-106`; the smoke handoff labels this F2 open at `docs/fleet/smoke_test_handoff.md:13-17`. | **STALE** — the supervisor-target gap survives the move and is recorded as such |

## Isolation

| Doc | Claim | Code truth | Status |
|---|---|---|---|
| `docs/designs/implemented/fleet_ladder_architecture.md:54-58` | [M] The implemented design's mount/scope contract records the actual cell mount set — worktree, repository aliases with writable `.git` overlays, results, shared OpenCode-state, and credential/config paths — with no “exactly four host-path categories” claim. | [M] The cell mount set includes `/tmp`, two repo aliases, writable `.git`, results, isolated OpenCode state, credentials, and provider config at `infrastructure/docker-compose.ladder.yml:49-73`. | **RESOLVED** — the post-audit move re-stated the mount contract accurately |
| `docs/fleet/00_proposal.md:170-180` | [M] The egress proxy is the only internet route and all tiers set `HTTP_PROXY`/`HTTPS_PROXY`. | [M] `x-ladder-env` has no proxy variables at `infrastructure/docker-compose.ladder.yml:22-47`; the accepted slice-1 log records that cells do not set them at `docs/fleet/04_slice1_live_cutover_log.md:126-134`. | **STALE** |
| `ARCHITECTURE.md:1-277` | [C] The architectural authority has no section defining container mount, egress, socket, or network-isolation invariants. | [M] Those implemented invariants are expressed only in compose comments and mounts at `infrastructure/docker-compose.ladder.yml:1-15,49-137,344-353`, so the architectural authority lacks the required cross-plane isolation contract. | **MISSING** |
| `infrastructure/docker-compose.ladder.yml:3-12,344-351` | [M] The ladder attaches to external `fleet-net` while excluding `finops-redis` from it. | [M] The service network and explicit exclusion are declared in the cited compose file; slice-1 records observed sandbox isolation at `docs/fleet/04_slice1_live_cutover_log.md:57-61`. | **CURRENT** |

## Surfaces

| Doc | Claim | Code truth | Status |
|---|---|---|---|
| `scripts/_gen_instructions.py:47-57,171-198,235-261` | [M] Four instructions, seven skills, three agents, and five commands are rendered to each target. | [M] `tests/test_agent_config_render.py:150-193` compares every mapped output and rejects orphans; the audit run passed all 12 generated-surface and script-classification tests. | **CURRENT** |
| `agent_config/system_snapshot.md:7`; `.opencode/instructions/system_snapshot.md:7`; `.claude/rules/system_snapshot.md:7` | [M] The source snapshot and both rendered copies identify HEAD as `a9fa243db`. | [M] The audited checkout HEAD is `196e5682292800f630917baadec2a7191aea596e`; the source and render agree with each other but are both outdated. | **STALE** |
| `CLAUDE.md:16-17` | [M] Three Claude rules are rendered from `agent_config/`. | [M] The renderer maps four instruction documents, including `system_snapshot.md`, at `scripts/_gen_instructions.py:47-48,243-245`. | **STALE** |
| `AGENTS.md:9-10` | [M] Research and website claims should ground in `_results_summary.json`. | [P] The canonical source policy in `agent_config/rules.md:6-7` instead names the registry/canonical corpus; the root instruction surface needs the same current data authority. | **STALE** |
| `scripts/CONTEXT.md:3-6` | [M] The scripts directory has 75 command scripts plus two helpers. | [C] The classification guard covers 116 Python scripts plus two helpers (`tests/test_script_classification.py:18-62`), while the tracked `scripts/` tree contains 118 Python files. | **STALE** |
| `scripts/CONTEXT.md:9-12` | [M] The classification is presented as one bucket assignment per command. | [C] The four duplicated `maintained:` rows contain 246 raw entries for 70 unique maintained scripts; set-union parsing still passes the guard, so the manifest is semantically covered but not a deterministic readable inventory. | **STALE** |
| `scripts/CONTEXT.md:41-45,53-71,77-133` | [M] The reference publishes per-script line counts. | [C] 65 of its 67 numeric line-count cells disagree with `wc -l`; representative deterministic comparisons are `run.py` 502→594 (`:41,53`), `analyze_worktrees.py` 1398→1425 (`:42,77`), `build_data.py` 1188→2447 (`:44,106`), `run_workflow.py` 434→558 (`:63`), `kb_worker.py` 204→572 (`:121`), and `kb_produce_facts.py` 244→1252 (`:124`). | **STALE** |
| `scripts/CONTEXT.md:3-23` | [M] The classification manifest describes script coverage but lists only Python filename buckets. | [M] Eight tracked executable/support scripts are outside that Python manifest axis: `scripts/{reproduce,run_control_room,sweep_parallel}.sh`, `scripts/sdk_bridge.mjs`, and `scripts/fleet/{attach_data_plane,build,entrypoint,review_cutover}.sh`. | **MISSING** |
| `README.md:96` | [M] The public inventory reports 161 specs: 11 experiments and 150 workflows. | [M] `test_readme_spec_counts_match_index` derives 164 specs from `experiments/specs/index.json` (11 experiments and 153 workflows) and failed with that exact mismatch: `tests/test_doc_lifecycle.py:230-252`. | **STALE** |

## Deterministic follow-up order

1. [P] Update the authoritative prose and package docstrings before any derived instruction artifact.
2. [P] Reconcile the fleet proposal or supersession/status chain with the accepted slice logs, retaining historical evidence rather than rewriting it as current state. — **[P] Executed by the 2026-09-01 remediation:** the design moved to `docs/designs/implemented/fleet_ladder_architecture.md` (`status: implemented`) and every audit anchor above re-points to it; `docs/fleet/00_proposal.md` + `docs/fleet/01_infra_inventory.md` carry supersession notes for their operational claims.
3. [P] Regenerate only through `agent_config/` and `scripts/_gen_instructions.py`; then re-run `python3 -m pytest tests/test_agent_config_render.py tests/test_script_classification.py -q`.
4. [P] Run the independent adversarial review after the authoritative and derived surfaces agree, so it reviews the new contract rather than a mixed state.
