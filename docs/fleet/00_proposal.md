---
status: proposed
---

# Fleet-ladder proposal — the mapping, assembled (container topology + KB access per tier)

**Status: PROPOSED · Date: 2026-08-29T16:05Z · Source: p4_proposal of the `fleet_ladder_plan`
spec (spec_sha256 `0d30d4bc…`).** ASSEMBLES the prior phases — `docs/fleet/01_infra_inventory.md`
(the infra facts), `02_kb_access_map.md` (the 31-touch KB map), `03_review.md` (the 6 unmapped
touches F-1…F-6, the 2 constraint findings, 12 risks, 10 questions) — against the design
(`docs/designs/proposed/fleet_ladder_architecture.md`). Nothing here re-researches; every
decision resolves a prior-phase finding. **Nothing implements — the operator signs off.**

The proposal is complete only if every one of the **37** KB touches (31 mapped + F-1…F-6) is
placed on a tier with a read/write classification and its guards intact.

## 0. Decisions that resolve the review's findings

| # | finding (p3) | decision |
|---|---|---|
| D-1 | mount-contract gap: `~/.opencode/bin` (opencode binary) + `~/.local/share/claude` (the claude symlink's target) outside §3's list | **D-1:** the auth row becomes a bounded five-dir set (D-2), keeping the four *categories* (worktree/results/repo/auth) unchanged — no new mount category, the "no other host path, ever" rule holds |
| D-2 | — | **D-2 (the auth set):** `~/.claude` ro · `~/.local/share/opencode` ro · `~/.local/bin` ro · `~/.local/share/claude` ro · `~/.opencode/bin` ro. CLIs get working binaries + credentials; `credentials.json` (0700) stays ro |
| D-3 | socket §2-vs-§4 inconsistency | **D-3 (the socket):** the docker socket mounts in the **orchestrator tier ONLY** (hard-rule 6). The supervisor does NOT mount it; routine restarts are docker's own `restart: on-failure` policies declared in the supervisor-owned compose configs; fleet-level spawn/drain is executed by the orchestrator (the socket-holder) on the supervisor's command. The supervisor's §2 "restart authority" = the compose policies it owns + the orchestrator as its hands |
| D-4 | F-1 spec refresh (`spec_ingestion.py:560`), F-2 context_snapshot (`context_compiler.py:918`) | **D-4:** both are orchestrator-tier producers (they fire inside `run_workflow`), using the same temp-write-guard discipline as P11 |
| D-5 | F-3 analyze_trajectories, F-4 lab_basin_topology | **D-5:** cell-tier (analysis) read-only store consumers |
| D-6 | F-5 cap_2e grid graph probe | **D-6:** orchestrator-tier (the grid harness) graph read |
| D-7 | F-6 context_snapshot_report / shadow_decision_report | **D-7:** supervisor-tier read tools (the board's report surface) |
| D-8 | Q9 redis-test (6399) + the declared-but-dead opencode-server | **D-8:** retire both from the census (redis-test is scratch; opencode-server never ran) |
| D-9 | Q1 the opencode server (4096) + 62 GB db | **D-9:** stays host-native (its db cannot ride the worktree/results mounts); becomes a **supervisor-MANAGED unit** (heartbeats + restart watched) — not a container |
| D-10 | Q6 the review worker | **D-10:** the retired Redis review worker is NOT revived; slice 1 containerizes `review_all` as a cell-tier review unit (its ThreadPoolExecutor), triggered by the supervisor-managed `trigger_reviews` |
| D-11 | Q10 `kb_worker.py:212` `authorized=True` write-back | **D-11:** stays the single code-side exception, made auditable by the slice-4 guard test (asserts exactly one un-env-gated write path exists) |
| D-12 | Q7 the 26,877-entry replay + 2,640 DLQ | **D-12:** the chroma/ledger/neo4j groups reset to the stream head (no full replay); the DLQ gets a bounded triage pass in slice 3 (re-drive or tombstone) |

## 1. The container topology per tier + the KB access matrix (the centerpiece)

Every unit from p1's inventory placed; every one of the **37** KB touches assigned read/write.

### 1a. The ladder placement (units → tier)

| p1 unit | tier | notes |
|---|---|---|
| story worker (`worker.py`), analysis worker (`analysis_worker.py`), review unit (`review_all` containerized), kb consumers ×4 (`kb_worker --group …`), batch producers (`kb_produce`, `kb_produce_sources`, `kb_produce_facts`, `kb_produce_campaign_evidence`), `run.py` single-runner, `supervise` (flag monitor), orphan sweep, `analyze_trajectories` (F-3), `lab_basin_topology` (F-4) | **cell** | mount contract, no socket, one job at a time |
| campaign wrapper / grid harness (`run_cap_*_grid` p2 phase), `run_workflow` runner, the cap_2e graph probe (F-5) | **orchestrator** | mount contract + **the socket (ro)** |
| fleet manager (pools, watcher, heartbeats, DLQ, live logs, drain), Control Room portal, game-board snapshot, `trigger_reviews`, read tools: registry CLI, `context_snapshot_report`/`shadow_decision_report` (F-6) | **supervisor** | no socket, fleet configs ro, logs rw |
| the operator chat (master control) | **operator** | the game board + the permanence gate + the CLI; never a daemon |
| the opencode web server (4096) + its 62 GB db | **supervisor-MANAGED host unit** (D-9) | not a container |
| `redis-test` (6399), the declared `opencode-server` container | **retired** (D-8) | |

### 1b. The access matrix — tier | units | KB reads | KB writes | guards | mounts

| tier | KB reads | KB writes | guards | mounts |
|---|---|---|---|---|
| **cell** | R1 dense (chroma) · R2 lexical (neo4j) · R3 RRF (in-process) · R5 evidence_analyzer graph · R6 registry head · F-3 session_embeddings read · F-4 basin graph read | **P1-P10** stream (story/run/review/supervise/orphan + the four batch producers) · **C1-C4** store writes (chroma upsert / ledger checkpoint / registry append / neo4j MERGE) | G1 (`FINOPS_KB_WRITE=1` on writer units **only**) · G2/G3 (code-side) · G4 (the registry consumer is the sole appender) · G5 (per-cell `self-<worktree>` scope) · G6 (consumers read-only) | worktree rw · results rw · repo ro · **auth ro (D-2 five dirs)** · toolchain baked |
| **orchestrator** | R1-R4 (the augment seam in agent phases) · R5 (grid probes) · R6 | **P11** emit_self (scoped) · **F-1** spec refresh · **F-2** context_snapshot (both opt-in, temp write-guard) | G1 (temp for F-1/F-2/P11 only) · G2/G3 · G5 (workflow scope) | the cell set **+ `/var/run/docker.sock` ro — the ONE escalation** |
| **supervisor** | R7 registry CLI · R8 Control Room registry route · R9 game-board counts · F-6 report reads | **none** — the supervisor is KB-read-only (the master-control boundary) | G1-G6 untouched — never sets `FINOPS_KB_WRITE` | fleet configs ro · logs rw · results rw · repo ro · auth ro (for the report/registry tooling) |
| **operator** | R7 (registry show/query/lineage), R9 | none — never self-activates | — | the game board only |

**Completeness:** 37/37 touches placed — 13 writes (P1-P11, F-1, F-2) + 4 consumer store-write
paths (C1-C4) + 16 reads (R1-R9, F-3…F-6) + 6 guards (G1-G6). No unmapped touch remains.

## 2. The compose layout

One ladder compose file set under `infrastructure/` (the existing `docker-compose*.yml` stay
the data plane — unchanged per the design's §4 "data plane | docker (unchanged)"):

**`infrastructure/docker-compose.ladder.yml`** — three service groups, one `fleet-net`
(bridge) attached to the existing `ai-infra` network so the data plane (neo4j/chroma/redis/
sonar) is reachable **by container name**:

- **fleet/cell** (`--scale story-worker=4 --scale analysis-worker=4 --scale review-unit=2`):
  `story-worker`, `analysis-worker`, `review-unit`, `kb-chroma`, `kb-ledger`, `kb-registry`,
  `kb-neo4j` (each `kb-*` = `kb_worker.py --group <name>`), `kb-produce`,
  `kb-produce-sources`, `kb-produce-facts`, `kb-produce-campaign-evidence` (run-to-completion
  `profiles: ["batch"]`), `run-single`, `supervise`, `orphan-sweep`.
  - **restart:** `on-failure` (docker's backoff) for the loops; `restart: "no"` for the batch producers.
  - **env:** `FINOPS_REDIS_PORT=6380`, `FINOPS_KB_DB=2`, `FINOPS_WORKTREE_ROOT=<worktree-mount>`;
    `FINOPS_KB_WRITE=1` **only** on P1-P10 units (never on the kb consumers — G6);
    `CLAUDE_BIN=/root/.local/bin/claude`, `PATH=/root/.local/bin:$PATH`.
  - **mounts (D-2):** `<wt>:/wt:rw`, `experiments/results:/app/experiments/results:rw`,
    `<repo>:/repo:ro`, `~/.claude:/root/.claude:ro`, `~/.local/share/opencode:/root/.local/share/opencode:ro`,
    `~/.local/bin:/root/.local/bin:ro`, `~/.local/share/claude:/root/.local/share/claude:ro`,
    `~/.opencode/bin:/root/.opencode/bin:ro`.
- **fleet/orchestrator:** `campaign-wrapper`, `workflow-runner`. Same env + mounts, **plus**
  `/var/run/docker.sock:/var/run/docker.sock:ro` (D-3 — the only escalation). `restart: on-failure`.
- **fleet/supervisor:** `fleet-manager`, `control-room`, `game-board`, `trigger-reviews`,
  `registry-cli`, `report-tools`. Mounts: fleet configs ro, logs rw, results rw, repo ro, auth
  ro. **No socket, no `FINOPS_KB_WRITE`.** `restart: always` (the only `always`).

**The host's footprint (per the design §2):** the docker daemon + one bootstrap unit —
`systemd` unit that runs `docker compose -f infrastructure/docker-compose.ladder.yml up -d
fleet-manager`, `Restart=always` (~3 lines).

## 3. The image hierarchy

Built from the repo (a versioned `Dockerfile.fleet` — the image is a controlled experiment
variable, rebuildable at any commit, per the design §6):

- **`fleet/base`** — python deps (`pyproject.toml` + the `[neo4j]` extra), node, git, the
  **sonar client baked** (it lives in `/tmp/sonar-scanner-6.2.1.4610` — ephemeral, must not
  be a mount), the auth-aware CLI entrypoints; the mount contract as declared **in the
  compose**, not the image (design §6).
- **`fleet/orchestrator`** — `fleet/base` + the docker CLI + **the sibling-spawn wrapper**
  (validates every spawn request against the mount contract before the socket call — the
  "policy wrapper for sibling spawn, the only escalation", design §6).
- **`fleet/supervisor`** — `fleet/orchestrator` + the fleet manager (pools, restart-with-backoff,
  live logs, heartbeats, drain) + the compose configs (ro) + the logs volume (design §6).

## 4. The neo4j bridge — the kb-neo4j-v1 consumer specification (the resurrected leg)

Per the design §5: the retrieval RRF fusion is coded (`retrieval.py:47-52,276-283,891-899`),
the graph client's fulltext is coded (`graph.py:97-100,1271-1285`), the handler is written
(`kb_worker.py:367-463`) — the missing piece is the **supervised running unit**.

- **Tier:** cell (mount contract; data-plane network reaches neo4j at `neo4j:7687` by name).
- **Image:** `fleet/base` (the `kb_worker.py` entrypoint; the neo4j driver from the `[neo4j]` extra).
- **Access:** reads the stream (db2, `kb-neo4j-v1` group — D-12 start point); writes neo4j:
  `create_knowledge_schema()` + `MERGE (k:Knowledge)` keyed on `knowledge_id` (idempotent —
  the direct-producer nodes are already there, MERGE dedupes, resolving risk R6) + the
  SUPERSEDES/CLEARED_BY/REPLACED_BY edges + the `knowledge_text_ft` **fulltext-index write**
  maintenance.
- **Guards:** **no `FINOPS_KB_WRITE`** (G6 — this consumer never writes back to the stream;
  only the flag auto-clear in the registry consumer does, and only under `authorized=True`,
  D-11); G5 respected (records carry their `repository_id`; the consumer does not re-scope);
  G2/G3 untouched.
- **Supervision:** a dedicated `kb-neo4j` container under the fleet manager, `restart:
  on-failure`, heartbeats → the board. **Success measure (design §9):** the group's `pending =
  0` and the RRF lexical leg returns non-empty on real queries.
- **Slice-3 preconditions:** the D-12 catch-up (head start point, DLQ triage) and the
  direct-producer reconciliation (MERGE idempotency verified on the 33,517 existing nodes).

## 5. The migration slices (each bounded, each with a rollback)

| slice | scope | deliverables | rollback |
|---|---|---|---|
| **1 — base image + supervisor + the worker pools** (design §7.1) | build `fleet/base` + `fleet/supervisor`; story/analysis/review workers as cell containers (the ad-hoc workers replaced); the queue watcher live (fixes the "no watcher" R3); heartbeats + the job **DLQ** live (fixes R4 — the 70-dead-jobs class); the portal + daemons as supervisor-managed units (D-9, fixes the SPOF F-3-in-p1) | the images, `docker-compose.ladder.yml` §cell/§supervisor, the fleet manager, the heartbeats/DLQ, the board surfaces | **additive** — the old `setsid nohup` workers still run; stop the supervisor, re-launch the ad-hoc workers |
| **2 — the orchestrator migration** (design §7.2) | the campaign wrapper + grid harness run as orchestrator containers (the socket mount); sibling cell spawning container-to-container; the 4-wide shape unchanged (`run_cap_*_grid` p2) | `fleet/orchestrator` image, the sibling-spawn wrapper (the socket policy check), the grid wave plumbing | the wrappers still run host-native — the orchestrator is a thin layer |
| **3 — the neo4j consumer + the RRF leg live** (design §7.3) | the `kb-neo4j` cell container live + supervised; the D-12 group catch-up + DLQ triage; the direct-producer reconciliation; `rag_augment` enabled for the orchestrator workflows as a **measured product gate** (D-Q8) — the two-leg RRF verified | the `kb-neo4j` service, the catch-up/DLQ disposition, the RRF verification report | stop the consumer; `rag_augment` back OFF; the graph stays (MERGE is additive) |
| **4 — the audit guards** (design §7.4) | the compose-contract guard test (the mount contract holds — no unexpected mount), the fleet-health guard (heartbeats + DLQ counts on the board), the neo4j index guard (the fulltext index populated ↔ the group's `pending = 0`), the single-write-back audit (D-11) | the three guard tests + the D-11 audit | read-only tests — nothing to roll back |

## 6. The guard-placement table (unchanged in strength)

| guard | code home | placement per tier |
|---|---|---|
| **G1 WRITE GUARD** (`FINOPS_KB_WRITE=1`/`authorized=True`, `knowledge_stream.py:184`) | code-side | `FINOPS_KB_WRITE=1` set **only** on the cell writers (P1-P10) and temporarily on the orchestrator's F-1/F-2/P11; never on consumers, the supervisor, or the read tools |
| **G2 ACTUATION-ARMED** (`FINOPS_ACTUATION_ARMED`, `:188`) | code-side | never set in the ladder — zero actuation producers; a future actuation unit sets it per-process |
| **G3 LINEAGE** (`causes`→observation, `:194` + `SOURCE_TYPE_INDEX_KEY`) | code-side | untouched by placement; the index population continues on every non-actuation event |
| **G4 REGISTRY APPEND** (append-only `registry_index.jsonl`, `generate_manifest.py` compaction) | consumer-side | the kb-registry consumer stays the **only appender**; producers write only via the stream — no direct index writes in any tier |
| **G5 SCOPE** (`self-<worktree>`, `scope_excluded`) | code-side | per-cell env (`FINOPS_CELL_ID`/`self-<worktree>`); the orchestrator's emit_self scoped to the cell; retrieval unchanged |
| **G6 CONSUMER READ-ONLY** | consumer-side | the kb-worker containers get **no** `FINOPS_KB_WRITE`; the `kb_worker.py:212` `authorized=True` write-back is the one audited exception (D-11) |

**Master-control boundary (design §8, restated for the mapping):** the supervisor is
KB-read-only; the operators are the only writers beyond the cell producers; nothing in the
ladder self-activates — the proposal awaits the operator's sign-off before slice 1 begins.

**LOG (p4):** topology = cell (16 units) / orchestrator (3) / supervisor (6) / operator +
2 retired + 1 supervisor-managed host unit; access matrix = **37/37 touches placed** (13
writes, 4 consumer store-write paths, 16 reads, 6 guards); compose = `docker-compose.ladder.yml`
with the D-2 auth set + the socket in the orchestrator tier only (D-3); images = base →
orchestrator → supervisor; neo4j bridge = the supervised `kb-neo4j` cell container (idempotent
MERGE, no write-back, `pending=0` measure); slices = 4 with rollbacks; guards = G1-G6 placed
unchanged. 12 risks from p3 carried with mitigations in §0/§5. **PASS** — proposal assembled
and committed; **awaiting the operator's sign-off** (nothing implements).
