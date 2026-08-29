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

**REVISED (2026-08-29, p0_revise of `fleet_ladder_revision`, escalated to deepseek-v4-pro):** the
p5 adversarial returned 7 FAILED findings (F-A1…F-A7 — `docs/reviews/fleet_ladder_proposal_adversary.md`).
This revision closes all 7, each by editing the mapping itself (not prose). See the REVISION
LOG (§7). The guards (G1-G6), the four constraints, the 14 known-safe protections, and the neo4j
bridge are unchanged in strength.

The proposal is complete only if every one of the **37** KB touches (31 mapped + F-1…F-6) is
placed on a tier with a read/write classification and its guards intact.

## 0. Decisions that resolve the review's findings

| # | finding (p3/p5) | decision |
|---|---|---|
| D-1 | mount-contract gap: `~/.opencode/bin` (opencode binary) + `~/.local/share/claude` (the claude symlink's target) outside §3's list | **D-1:** the auth row becomes a bounded five-dir set (D-2), keeping the four *categories* (worktree/results/repo/auth) unchanged — no new mount category, the "no other host path, ever" rule holds |
| D-2 | — | **D-2 (the auth set):** `~/.claude` ro · `~/.local/share/opencode` ro · `~/.local/bin` ro · `~/.local/share/claude` ro · `~/.opencode/bin` ro. CLIs get working binaries + credentials; `credentials.json` (0700) stays ro |
| D-3 | socket §2-vs-§4 inconsistency | **D-3 (the socket):** the docker socket mounts in the **orchestrator tier ONLY** (hard-rule 6). The supervisor does NOT mount it; routine restarts are docker's own `restart: on-failure` policies declared in the supervisor-owned compose configs; fleet-level spawn/drain is executed by the orchestrator (the socket-holder) on the supervisor's command. The supervisor's §2 "restart authority" = the compose policies it owns + the orchestrator as its hands |
| D-4 | F-1 spec refresh (`spec_ingestion.py:560`), F-2 context_snapshot (`context_compiler.py:918`) | **D-4:** both are orchestrator-tier producers (they fire inside `run_workflow`), using the same code-side temp-write authorization as P11 — `_authorized_kb_write()` for F-1, the `authorized=` param for F-2 (neither needs the env — see D-15) |
| D-5 | F-3 analyze_trajectories, F-4 lab_basin_topology | **D-5:** cell-tier (analysis) read-only store consumers |
| D-6 | F-5 cap_2e grid graph probe | **D-6:** orchestrator-tier (the grid harness) graph read |
| D-7 | F-6 context_snapshot_report / shadow_decision_report | **D-7:** supervisor-tier read tools (the board's report surface) |
| D-8 | Q9 redis-test (6399) + the declared-but-dead opencode-server | **D-8:** retire both from the census (redis-test is scratch; opencode-server never ran) |
| D-9 | Q1 the opencode server (4096) + 62 GB db (F-A5) | **D-9:** the opencode web server (4096) + its 62 GB db are **operator-side master control** — the operator's own chat server, **outside the ladder entirely** (like the operator's shell/editor). NOT a ladder unit, NOT supervisor-managed. The host's footprint of ours stays the bootstrap unit only; the units slice 1 places under the supervisor are the *ladder's own* portal + daemons (containerized), not host services |
| D-10 | Q6 the review worker (F-A6) | **D-10:** the retired Redis review worker is NOT revived; slice 1 containerizes `review_all` as a cell-tier review unit (its ThreadPoolExecutor), triggered by the supervisor-managed `trigger_reviews`. The review migration is a **sequenced cut-over, never additive**: stop the host `trigger_reviews` + drain its in-flight `review_all` FIRST, then start the containerized path — no double-review window |
| D-11 | Q10 `kb_worker.py:198,212` flag auto-clear write-back (F-A2) | **D-11:** the flag auto-clear is gated by BOTH the env (`kb_worker.py:198`, `FINOPS_KB_WRITE=1`) and the code `authorized=True` (`:212`). The **kb-registry consumer is the ONE kb-worker container granted `FINOPS_KB_WRITE=1`** — so the env gate passes and the tombstone write-back fires. G6's strength (the env gate) governs the exception; the slice-4 guard test asserts exactly one consumer carries the env |
| D-12 | Q7 the 26,877-entry replay + 2,640 DLQ | **D-12:** the chroma/ledger/neo4j groups reset to the stream head (no full replay); the DLQ gets a bounded triage pass in slice 3 (re-drive or tombstone) |
| D-13 | F-A3 — supervisor mount-contract breach | **D-13 (the supervisor mounts):** the supervisor is the fleet manager, not an execution container. Its two out-of-contract mounts are absorbed into the four: the "fleet configs" are the repo's own compose files (already on `repo ro`), and the "logs" become a docker **named volume** (`fleet-logs` — docker-managed, not a host path). The supervisor mounts a subset of the four (results rw · repo ro · auth ro) + that named volume. No tier mounts a host path beyond the four categories + the D-2 auth five-dir set |
| D-14 | F-A4 — socket/watcher mechanism | **D-14 (the socket + the watcher):** the pools are **static** (compose `--scale` counts) + docker's own `restart: on-failure` — no socket for restart. The **watcher is read-only** (queue depth + worker heartbeats + DLQ counts → the board; it never spawns). A fleet-level resize/drain is the supervisor **commanding the orchestrator** (the socket-holder) over a declared channel — Redis `fleet:commands` (db1, 6380) — and the orchestrator's **spawn-wrapper** validates every request against the compose allowlist + the mount contract before the socket call. The audit surface is named: the compose files + the spawn-wrapper's validation log + the slice-4 guard test |
| D-15 | F-A7 — orchestrator env ambiguity | **D-15 (the orchestrator env):** the orchestrator **never carries `FINOPS_KB_WRITE=1`** at the container level. Its F-1/F-2/P11 writes authorize in code — `_authorized_kb_write()` (`knowledge_ingestion.py:439-440`, sets the flag for the emit then restores it) for F-1/P11, the `authorized=` param for F-2. "Temporary" cannot be expressed in compose env; the code-side context manager is the mechanism |

**Risk dispositions (p3 R1-R12 → decision/section):** R1 live workload → slice 1's additive/cut-over rollbacks; R2 single-writer → G4 + the per-store single consumer; R3 auth mounts → D-2; R4 image maintenance → §3; R5 socket trust boundary → D-3/D-14; R6 neo4j dual-write → §4 MERGE + D-12; R7 consumer replay storm → D-12; R8 `rag_augment` OFF → slice 3 product gate; R9 opencode server → D-9; **R10 review-worker revival → D-10**; R11 port discipline → D-8 + §2 by-name reachability (chroma 8000 / portal 8001, no collisions); R12 kb_worker exception → D-11. All 12 disposed.

## 1. The container topology per tier + the KB access matrix (the centerpiece)

Every unit from p1's inventory placed; every one of the **37** KB touches assigned read/write.

### 1a. The ladder placement (units → tier)

| p1 unit | tier | notes |
|---|---|---|
| story worker (`worker.py`), analysis worker (`analysis_worker.py`), review unit (`review_all` containerized), kb consumers ×4 (`kb_worker --group …`), batch producers (`kb_produce`, `kb_produce_sources`, `kb_produce_facts`, `kb_produce_campaign_evidence`), `run.py` single-runner, `supervise` (flag monitor), orphan sweep, `analyze_trajectories` (F-3), `lab_basin_topology` (F-4) | **cell** | mount contract, no socket, one job at a time |
| campaign wrapper / grid harness (`run_cap_*_grid` p2 phase), `run_workflow` runner, the cap_2e graph probe (F-5) | **orchestrator** | mount contract + **the socket (ro)** — guarded by the spawn-wrapper (D-14) |
| fleet manager (pools, watcher, heartbeats, DLQ, live logs, drain), Control Room portal, game-board snapshot, `trigger_reviews`, read tools: registry CLI, `bundle_artifacts` reference check (R10), `context_snapshot_report`/`shadow_decision_report` (F-6) | **supervisor** | no socket (D-3/D-14); mounts results rw · repo ro (the compose files) · auth ro + the `fleet-logs` named volume (D-13) |
| the operator chat (master control) | **operator** | the game board + the permanence gate + the CLI; never a daemon |
| the opencode web server (4096) + its 62 GB db | **operator-side master control** (D-9) — outside the ladder | the operator's own chat server; not a ladder unit |
| `redis-test` (6399), the declared `opencode-server` container | **retired** (D-8) | |

### 1b. The access matrix — tier | units | KB reads | KB writes | guards | mounts

| tier | KB reads | KB writes | guards | mounts |
|---|---|---|---|---|
| **cell** | R1 dense (chroma) · R2 lexical (neo4j) · R3 RRF (in-process) · R5 evidence_analyzer graph · R6 registry head · F-3 session_embeddings read · F-4 basin graph read | **P1-P10** stream (story/run/review/supervise/orphan + the four batch producers) · **C1-C4** store writes (chroma upsert / ledger checkpoint / registry append / neo4j MERGE) | G1 (`FINOPS_KB_WRITE=1` on writer units **only**) · G2/G3 (code-side) · G4 (the registry consumer is the sole appender) · G5 (per-cell `self-<worktree>` scope) · G6 (consumers read-only; the kb-registry consumer carries the env, D-11) | worktree rw · results rw · repo ro · **auth ro (D-2 five dirs)** · toolchain baked |
| **orchestrator** | R1-R4 (the augment seam in agent phases) · R5 (grid probes) · R6 | **P11** emit_self (scoped) · **F-1** spec refresh · **F-2** context_snapshot (both opt-in, code-side temp write auth) | G1 (code-side `_authorized_kb_write()`/`authorized=` for F-1/F-2/P11 — no env, D-15) · G2/G3 · G5 (workflow scope) | the cell set **+ `/var/run/docker.sock` ro — the ONE escalation** |
| **supervisor** | R7 registry CLI · R8 Control Room registry route · R9 game-board counts · R10 bundle reference check (registry index + manifest) · F-6 report reads | **none** — the supervisor is KB-read-only (the master-control boundary) | G1-G6 untouched — never sets `FINOPS_KB_WRITE` | results rw · repo ro (the compose files) · auth ro (for the report/registry tooling) · the `fleet-logs` named volume (D-13) |
| **operator** | R7 (registry show/query/lineage), R9 | none — never self-activates | — | the game board only |

**Completeness:** 37/37 touches placed — 13 writes (P1-P11, F-1, F-2) + 4 consumer store-write
paths (C1-C4) + 14 reads (R1-R10, F-3…F-6) + 6 guards (G1-G6). No unmapped touch remains.

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
    `FINOPS_KB_WRITE=1` **only** on P1-P10 units, plus the **kb-registry consumer** (D-11 — the
    flag auto-clear's env gate); never on the other kb consumers (G6);
    `CLAUDE_BIN=/root/.local/bin/claude`, `PATH=/root/.local/bin:$PATH`.
  - **mounts (D-2):** `<wt>:/wt:rw`, `experiments/results:/app/experiments/results:rw`,
    `<repo>:/repo:ro`, `~/.claude:/root/.claude:ro`, `~/.local/share/opencode:/root/.local/share/opencode:ro`,
    `~/.local/bin:/root/.local/bin:ro`, `~/.local/share/claude:/root/.local/share/claude:ro`,
    `~/.opencode/bin:/root/.opencode/bin:ro`.
- **fleet/orchestrator:** `campaign-wrapper`, `workflow-runner`. Same mounts, **plus**
  `/var/run/docker.sock:/var/run/docker.sock:ro` (D-3 — the only escalation, guarded by the
  spawn-wrapper, D-14). **Env (D-15): the cell env MINUS `FINOPS_KB_WRITE`** — the orchestrator
  never carries the write flag at the container level; its F-1/F-2/P11 writes authorize in code
  (`_authorized_kb_write()` / `authorized=`). `restart: on-failure`.
- **fleet/supervisor:** `fleet-manager`, `control-room`, `game-board`, `trigger-reviews`,
  `registry-cli`, `bundle-reference-check`, `report-tools`. Mounts (D-13): results rw, repo ro
  (the compose files ride here), auth ro, + the `fleet-logs` named volume (docker-managed, not a
  host path). **No socket (D-3/D-14), no `FINOPS_KB_WRITE`.** `restart: always` (the only `always`).

**The socket + the watcher mechanism (D-14):** the pools are **static** — the compose declares
`--scale story-worker=4 --scale analysis-worker=4 --scale review-unit=2`; routine restarts are
docker's `restart: on-failure` + the supervisor's restart-with-backoff, **no socket for
restart**. The **watcher is read-only**: `fleet-manager` reads queue depth (`LLEN`), the worker
heartbeats (`worker:<type>:<id>`), and the DLQ counts, and surfaces them to the board / Control
Room — it never spawns. A fleet-level **resize/drain** is the supervisor LPUSHing a bounded
command (`{action: scale|drain, service, count}`) onto Redis `fleet:commands` (db1, 6380); the
orchestrator's **spawn-wrapper** BRPOPs it, validates (service ∈ the compose allowlist, count
bounded, the mount contract unchanged), and only then runs the `docker compose up -d --scale`
socket call. The audit surface: the compose files (every service + mount), the spawn-wrapper's
validation log, and the slice-4 compose-contract guard test (the socket appears in exactly one
tier — the orchestrator).

**The host's footprint (per the design §2):** the docker daemon + one bootstrap unit —
`systemd` unit that runs `docker compose -f infrastructure/docker-compose.ladder.yml up -d
fleet-manager`, `Restart=always` (~3 lines). The opencode web server (4096) is operator-side
(D-9) — not ours, not on the ladder.

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
  the one write-back anywhere is the flag auto-clear in the kb-registry consumer, gated by
  `FINOPS_KB_WRITE=1` (`kb_worker.py:198`) AND `authorized=True` (`:212`) — and the kb-registry
  container is the one consumer granted that env, D-11); G5 respected (records carry their
  `repository_id`; the consumer does not re-scope); G2/G3 untouched.
- **Supervision:** a dedicated `kb-neo4j` container under the fleet manager, `restart:
  on-failure`, heartbeats → the board. **Success measure (design §9):** the group's `pending =
  0` and the RRF lexical leg returns non-empty on real queries.
- **Slice-3 preconditions:** the D-12 catch-up (head start point, DLQ triage) and the
  direct-producer reconciliation (MERGE idempotency verified on the 33,517 existing nodes).

## 5. The migration slices (each bounded, each with a rollback)

| slice | scope | deliverables | rollback |
|---|---|---|---|
| **1 — base image + supervisor + the worker pools** (design §7.1) | build `fleet/base` + `fleet/supervisor`; story/analysis workers as cell containers (the ad-hoc workers replaced — **additive**: BRPOP is atomic, so old + new workers drain the same queue without double-processing); the **read-only queue watcher** live (queue depth + heartbeats → the board, fixes the "no watcher" R3); heartbeats + the job **DLQ** live (fixes R4 — the 70-dead-jobs class); the **review path as a sequenced cut-over** (F-A6): stop the host `trigger_reviews` + drain its in-flight `review_all` FIRST, then start the containerized `review-unit` + the supervisor `trigger-reviews`; the portal + daemons as supervisor-tier containers (fixes the SPOF F-3-in-p1) | the images, `docker-compose.ladder.yml` §cell/§supervisor, the fleet manager, the heartbeats/DLQ, the board surfaces | **story/analysis: additive** (the old `setsid nohup` workers still run; stop the supervisor, re-launch the ad-hoc workers); **review: cut-over** (stop the container path, restart the host `trigger_reviews` — never both live) |
| **2 — the orchestrator migration** (design §7.2) | the campaign wrapper + grid harness run as orchestrator containers (the socket mount); sibling cell spawning container-to-container; the 4-wide shape unchanged (`run_cap_*_grid` p2) | `fleet/orchestrator` image, the sibling-spawn wrapper (the socket policy check), the grid wave plumbing | the wrappers still run host-native — the orchestrator is a thin layer |
| **3 — the neo4j consumer + the RRF leg live** (design §7.3) | the `kb-neo4j` cell container live + supervised; the D-12 group catch-up + DLQ triage; the direct-producer reconciliation; `rag_augment` enabled for the orchestrator workflows as a **measured product gate** (D-Q8) — the two-leg RRF verified | the `kb-neo4j` service, the catch-up/DLQ disposition, the RRF verification report | stop the consumer; `rag_augment` back OFF; the graph stays (MERGE is additive) |
| **4 — the audit guards** (design §7.4) | the compose-contract guard test (the mount contract holds — no unexpected mount), the fleet-health guard (heartbeats + DLQ counts on the board), the neo4j index guard (the fulltext index populated ↔ the group's `pending = 0`), the single-write-back audit (D-11) | the three guard tests + the D-11 audit | read-only tests — nothing to roll back |

## 6. The guard-placement table (unchanged in strength)

| guard | code home | placement per tier |
|---|---|---|
| **G1 WRITE GUARD** (`FINOPS_KB_WRITE=1`/`authorized=True`, `knowledge_stream.py:184`) | code-side | `FINOPS_KB_WRITE=1` set **only** on the cell writers (P1-P10) + the kb-registry consumer (D-11). The orchestrator does NOT set it — its F-1/F-2/P11 writes authorize in code (`_authorized_kb_write()` / `authorized=`, D-15). Never on the other consumers, the supervisor, or the read tools |
| **G2 ACTUATION-ARMED** (`FINOPS_ACTUATION_ARMED`, `:188`) | code-side | never set in the ladder — zero actuation producers; a future actuation unit sets it per-process |
| **G3 LINEAGE** (`causes`→observation, `:194` + `SOURCE_TYPE_INDEX_KEY`) | code-side | untouched by placement; the index population continues on every non-actuation event |
| **G4 REGISTRY APPEND** (append-only `registry_index.jsonl`, `generate_manifest.py` compaction) | consumer-side | the kb-registry consumer stays the **only appender**; producers write only via the stream — no direct index writes in any tier |
| **G5 SCOPE** (`self-<worktree>`, `scope_excluded`) | code-side | per-cell env (`FINOPS_CELL_ID`/`self-<worktree>`); the orchestrator's emit_self scoped to the cell; retrieval unchanged |
| **G6 CONSUMER READ-ONLY** | consumer-side | the kb-worker containers get **no** `FINOPS_KB_WRITE` — **except the kb-registry consumer, which carries it (D-11)** so the flag auto-clear's env gate (`kb_worker.py:198`) AND `authorized=True` (`:212`) both pass. G6's strength (the env gate) governs the single exception; no other consumer writes back |

**Master-control boundary (design §8, restated for the mapping):** the supervisor is
KB-read-only; the operators are the only writers beyond the cell producers; nothing in the
ladder self-activates — the proposal awaits the operator's sign-off before slice 1 begins.

## 7. REVISION LOG (p0_revise — the p5 adversarial FAIL, F-A1…F-A7)

Each finding → the resolution → the section edited. The mechanism is closed by the mapping
itself, not by prose. The guards (G1-G6), the four constraints, the 14 known-safe protections
(`fleet_ladder_proposal_known_safe.md`), and the neo4j bridge are unchanged in strength.

| finding | resolution | section edited |
|---|---|---|
| **F-A1** R10 unmapped + the 37-touch miscount | the p2 read **R10** (`bundle_artifacts.py:53,116` — the registry reference check over `registry_index.jsonl` + `data_manifest.json`) is placed on the **supervisor** tier (read-only, over the results mount); the p3 **risk R10** (review-worker revival) is disposed by D-10. The completeness line is corrected to **14 reads (R1-R10, F-3…F-6) → 13 + 4 + 14 + 6 = 37** | §0 (risk dispositions), §1a (R10 in the read tools), §1b (supervisor reads + the arithmetic) |
| **F-A2** G6-vs-D11 dead (the flag auto-clear never fires) | **the guard wins**: D-11 now grants the **kb-registry consumer `FINOPS_KB_WRITE=1`** — the flag auto-clear's env gate (`kb_worker.py:198`) AND the code `authorized=True` (`:212`) both pass, so the tombstone write-back fires. G6 is restated to the guard's actual code (read-only by default; the ONE write-back is env-gated), and the slice-4 guard test asserts exactly one consumer carries the env | §0 (D-11), §2 (the cell env line), §4 (the neo4j guard note), §6 (G6) |
| **F-A3** supervisor mount-contract breach | **D-13**: the supervisor's two out-of-contract mounts are absorbed — the "fleet configs" are the repo's own compose files (already `repo ro`), and the "logs" become a docker **named volume** (`fleet-logs`, not a host path). The supervisor mounts a subset of the four + that named volume; no tier mounts a host path beyond the four + the D-2 auth set | §0 (D-13), §1a (supervisor row), §1b (supervisor mounts), §2 (the supervisor service) |
| **F-A4** socket/watcher unspecified | **D-14**: static pools + `restart: on-failure` (no socket for restart); the watcher is **read-only** (depth/heartbeats/DLQ → the board, never spawns); a resize/drain is the supervisor→orchestrator command over Redis `fleet:commands` (db1, 6380), validated by the orchestrator's **spawn-wrapper** (compose allowlist + mount contract) before the socket call. The audit surface is named: compose files + the spawn-wrapper log + the slice-4 guard test | §0 (D-14), §2 (the socket + watcher mechanism paragraph), §5 (slice 1's "watcher" restated) |
| **F-A5** host-footprint D-9 | **D-9 reclassified**: the opencode web server (4096) + 62 GB db are **operator-side master control** (the operator's own chat server), **outside the ladder** — not a ladder unit, not supervisor-managed. The host's footprint of ours stays the bootstrap unit only | §0 (D-9), §1a (the opencode row), §2 (the host-footprint note), §5 (slice 1) |
| **F-A6** double-review window | **D-10 sequenced**: the review migration is a **cut-over, not additive** — stop the host `trigger_reviews` + drain its in-flight `review_all` BEFORE the containerized `review-unit`/`trigger-reviews` starts. The slice-1 rollback is split: story/analysis additive (BRPOP atomic), review cut-over | §0 (D-10), §5 (slice 1 scope + rollback) |
| **F-A7** orchestrator env ambiguity | **D-15**: the orchestrator **never carries `FINOPS_KB_WRITE=1`** at the container level; F-1/F-2/P11 authorize in code (`_authorized_kb_write()` at `knowledge_ingestion.py:439-440` for F-1/P11, the `authorized=` param for F-2) — "temporary" cannot live in compose env | §0 (D-15), §2 (the orchestrator service env), §6 (G1) |

**LOG (p4):** topology = cell (16 units) / orchestrator (3) / supervisor (6) / operator +
2 retired + the opencode server reclassified operator-side; access matrix = **37/37 touches
placed** (13 writes, 4 consumer store-write paths, 14 reads, 6 guards); compose =
`docker-compose.ladder.yml` with the D-2 auth set + the socket in the orchestrator tier only
(D-3); images = base → orchestrator → supervisor; neo4j bridge = the supervised `kb-neo4j` cell
container (idempotent MERGE, no write-back, `pending=0` measure); slices = 4 with rollbacks;
guards = G1-G6 placed unchanged. 12 risks from p3 carried with mitigations in §0/§5.
**PASS** — proposal assembled and committed; **awaiting the operator's sign-off** (nothing
implements).

**LOG (p0_revise, deepseek-v4-pro):** closed F-A1…F-A7 — R10 mapped + the arithmetic fixed
(14 reads / 37), the guard wins in G6-vs-D11 (kb-registry carries the env), D-13 absorbs the
supervisor's out-of-contract mounts, D-14 specifies static pools + the read-only watcher + the
spawn-wrapper socket guard + the `fleet:commands` channel, D-9 reclassifies the opencode server
as operator-side, D-10 sequences the review cut-over, D-15 removes the orchestrator write flag.
Guards G1-G6 unchanged in strength; the four constraints hold; the 14 known-safe protections
survive; the neo4j bridge intact. **PASS — revision committed; awaiting the operator's
sign-off.**
