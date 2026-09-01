---
status: proposed
---

# Fleet-ladder infra inventory — the execution plane as it is TODAY

**SUPERSEDED BY IMPLEMENTATION (2026-09-01):** the design this inventory fed has moved to
`docs/designs/implemented/fleet_ladder_architecture.md` (`status: implemented`, implemented by
`workflows/repository/fleet_ladder_implementation.yaml`). This document is the historical p1
snapshot — queue state, store occupancy, and the failure ledger as of 2026-08-29 — not
current-state documentation; the accepted slice logs supersede its operational claims.

**Status: PROPOSED · Date: 2026-08-29T15:24:02Z · Source: p1_research_infra of the
`fleet_ladder_plan` spec (spec_sha256 `0d30d4bc…`; the design under mapping is
`docs/designs/implemented/fleet_ladder_architecture.md`).**

This is a **factual inventory** — no design, no proposal, no infra touched. Every number is
cited to a live command or a file path. It answers the design's §1 problem statement with
ground truth and feeds p3 (review) and p4 (proposal).

## 1. The container fleet — `docker ps` (2026-08-29T15:20Z)

```
NAME            IMAGE                       PORTS                                    STATUS
sonarqube       sonarqube:10.7-community    127.0.0.1:9000->9000/tcp                Up 2 weeks
sonarqube-9001  sonarqube:10.7-community    127.0.0.1:9001->9000/tcp                Up 2 weeks
sonarqube-9002  sonarqube:10.7-community    127.0.0.1:9002->9000/tcp                Up 2 weeks
sonarqube-9003  sonarqube:10.7-community    127.0.0.1:9003->9000/tcp                Up 2 weeks
finops-queue    redis:7-alpine              127.0.0.1:6380->6379/tcp               Up 2 weeks
finops-redis    redis:7-alpine              127.0.0.1:6379->6379/tcp               Up 2 weeks
redis-test      redis:7-alpine              0.0.0.0:6399->6379/tcp                 Up 2 weeks
neo4j           neo4j:5.26-community        0.0.0.0:7474/7687 (+7473)              Up 2 weeks
chromadb        chromadb/chroma:1.0.13      0.0.0.0:8000->8000/tcp                 Up 39 min
```

9 containers. **The data plane is already dockerized** (the design's §4 "data plane | docker
(unchanged)" row is accurate). Sources: the three compose files under `infrastructure/`:

- `infrastructure/docker-compose.yml` — neo4j 5.26 (:4-18), chromadb 1.0.13 (:20-35), and an
  **opencode-server** container (:37-52). The opencode-server is declared but **NOT running**
  (`docker ps` shows no opencode-server; the host runs `opencode web --port 4096` natively —
  see §2). Its `- /path/to/your/project` mount is a placeholder, not real.
- `infrastructure/docker-compose.experiment.yml` — finops-redis 6379 (:8-15) + finops-queue
  6380 (:34-41) with the DB reservation doc (:20-27): **DB 1** = story_jobs/status + live.py
  pub-sub telemetry; **DB 2** = the KB Streams (`kb:v1:*`), reserved. Never 6379 for framework
  state (story agents run flushdb()/flushall() against it).
- `infrastructure/docker-compose.sonar.yml` — the four sonarqube 10.7 instances, 9000-9003.

Notables:
- **redis-test (6399)** is live but declared in **no** compose file — a scratch/leftover
  instance.
- The repo-root **`Dockerfile`** is the **reproduction** image (CORE pipeline), not the
  execution plane: it mounts `~/.opencode/bin/opencode`, the opencode.db, results, website,
  manifest (`Dockerfile:7-11`) and defaults to `reproduce.sh core`. It is evidence that
  containerizing the toolchain is already precedented, but it is not the fleet.

**Store occupancy (live, first-hand):**
- Chroma (port 8000): `knowledge_chunks_v1` **812** · `session_embeddings` **2,215**
  (`ChromaStore(...).collection.count()`, 2026-08-29; matches `agent_config/system_snapshot.md:42`).
- Neo4j (7474/7687): **33,517** `Knowledge` nodes (+ 4,076 ModuleVersion, 2,435 Step, 427
  ExperimentRun, 271 Revision, 222 Session, 133 CodeModule, 37 ExperimentConfig); fulltext
  indexes **`knowledge_text_ft` + `step_text_ft` both present** (`SHOW FULLTEXT INDEXES`,
  2026-08-29). **Neo4j is NOT empty** — the design's §5 "running, empty" is outdated (see §3,
  finding F-2).

## 2. The host workers + the queue state (live, 2026-08-29T15:20Z)

**Ad-hoc host processes** (`ps aux`, non-kernel, sorted by start):
- `opencode web --hostname 0.0.0.0 --port 4096` — the opencode server, **host-native**
  (replaces the declared-but-not-running opencode-server container).
- `bash scripts/run_control_room.sh` — the portal **respawn supervisor** (a `while true`
  loop; `scripts/run_control_room.sh:2` "died silently three times"). It is itself a host
  process with **no restart of its own** — the SPOF the design names.
- `python3 apps/control_room/server.py` — the Control Room portal (FINOPS_PORT 8001).
- `python3 scripts/trigger_reviews.py` — the review trigger (polls analysis, then runs
  `review_all.py` **synchronously**; `scripts/trigger_reviews.py:64-68`; the Redis review
  worker is **retired**).
- `python3 scripts/run_workflow.py --spec workflows/repository/fleet_ladder_plan.yaml …` —
  this workflow's own wrapper (the "campaign wrapper" shape).
- `python3 scripts/review_all.py` + 4× `opencode run … --format json --auto` (story/commit
  reviews, deepseek-v4-flash) — the live review workload.
- (Daemon, not currently spawned: `scripts/orphan_sweep.py --interval 300` per
  `HANDOFF.md:19` — the orphan sweep, ledger `experiments/results/orphans/orphans.jsonl`.)

**Launch pattern** (documented fragility): `setsid nohup python3 … &` —
`HANDOFF.md:44-45` ("setsid is mandatory for anything long-running — nohup alone died
twice"); `scripts/pipeline.py:312-325` `_spawn_workers` uses `subprocess.Popen(["nohup", …],
start_new_session=True)`.

**Queue state — Redis 6380, db1** (`LLEN`/`HLEN`/`HGETALL`, 2026-08-29T15:20Z):

| queue | len | status hash | breakdown |
|---|---|---|---|
| `story_jobs` | 0 | `story_status` **261** | done 218 · failed 42 · running 1 |
| `analysis_jobs` | 0 | `analysis_status` **129** | failed **104** · done 25 |
| `review_jobs` | **326** | `review_status` **168** | queued 168 |

- No job queue has a **dead-letter** surface — failed jobs just sit in the status hash as
  `failed` (the design's §1 "no dead-letter surface" is true for the job queues; the KB
  stream has one — §3).
- Nothing **watches** the queues to spawn workers when they fill — the "fleet has no
  watcher" claim is confirmed: no code scans queue length to start workers; the 129
  analysis entries include 104 failed, consistent with a queued-with-no-worker episode.

**KB stream — Redis 6380, db2** (`XINFO STREAM/GROUPS`, `XLEN`, 2026-08-29T15:20Z):

- `kb:v1:changes` — **26,877** entries.
- Consumer groups (`knowledge_stream.py:62`): all four declared.

| group | consumers | pending | last-delivered |
|---|---|---|---|
| `kb-chroma-v1` | 0 | 0 | `0-0` (never) |
| `kb-ledger-v1` | 0 | 0 | `0-0` (never) |
| `kb-neo4j-v1` | 0 | 0 | `0-0` (never) |
| `kb-registry-v1` | **22** | 0 | `1787711512064-0` (delivered) |

- `kb:v1:dead_letter` — **2,640** entries (the KB stream's own DLQ; `knowledge_stream.py:54`).

**Key observation K-1 (corrects the design's §5 "live/dead" labels):** only
`kb-registry-v1` has ever consumed the stream. The chroma/ledger/neo4j **stream consumers
are all idle** (0 consumers, 0-0). Yet chroma (812/2,215) and neo4j (33,517) are **populated**
— by the **batch producers writing directly to the stores** (`kb_produce_sources.py`,
`kb_produce_facts.py`, `kb_produce_campaign_evidence.py`), not by stream consumers. The
design's table labels chroma/ledger "live"; at the stream level they are as unwired as
neo4j. p3/p4 must reconcile this.

## 3. The code surfaces

**Worker loops:**
- `scripts/worker.py` — `QUEUE_KEY="story_jobs"`, `STATUS_KEY="story_status"` (:30-31);
  BRPOP loop (:142); spawns `run_story.py` per cell (:188); status writes running (:172) /
  failed (:241,:254) / done (:248) / timeout (:264); `LivePublisher` (:40).
- `scripts/analysis_worker.py` — `QUEUE_KEY="analysis_jobs"`, `STATUS_KEY="analysis_status"`
  (:40-41); BRPOP (:105); running (:128) / done (:156) / failed (:161); **fails jobs whose
  worktree is gone**: `raise RuntimeError(f"worktree missing: {worktree}")` (:135) — the
  mechanism behind the "dead jobs pointed at removed files" class.
- `scripts/trigger_reviews.py` — no BRPOP loop; polls analysis then invokes
  `review_all.py` synchronously (:67). Redis review worker retired (per `scripts/CONTEXT.md`).
- `scripts/kb_worker.py` — `build_handler()` (:222) registers **all four** groups:
  `kb-ledger-v1` (:228-234, checkpoint-hash HSET), `kb-registry-v1` (:236-334, appends one
  line per record to `registry_index.jsonl` + in-process flag index + the auto-clear
  tombstone path), `kb-chroma-v1` (:336-365, `ChromaStore(knowledge_chunks_v1)` upsert,
  skips `fact`), `kb-neo4j-v1` (:367-463, `create_knowledge_schema()` + `MERGE (k:Knowledge)`
  with the full SET clause + SUPERSEDES/CLEARED_BY/REPLACED_BY edges). CLI accepts all four
  groups (:495). **The neo4j handler EXISTS** — K-2 (below).

**The stream + guards — `src/agentic_dynamics/knowledge/knowledge_stream.py`:**
- `REDIS_PORT` default **6380** (:47), `REDIS_DB` default **2** (:51), `STREAM_KEY
  "kb:v1:changes"` (:53), `DEAD_LETTER_KEY "kb:v1:dead_letter"` (:54),
  `CONSUMER_GROUPS` the four (:62), `MAX_RETRIES 3` (:65), `SOURCE_TYPE_INDEX_KEY` (:76).
- **WRITE GUARD** (:184-186): publish raises unless `authorized=True` or `FINOPS_KB_WRITE==1`.
- **ACTUATION-ARMED GATE** (:188-191): for `source_type="actuation"`, additionally `armed=True`
  or `FINOPS_ACTUATION_ARMED==1`.
- **LINEAGE** (:194-198): an actuation's `causes` must resolve to an observation via
  `_resolves_to_observation` (:121-132); non-actuation events populate the source-type index (:200).
- Consumer-side gate: `scripts/kb_worker.py:198` — a consumer is normally a READER; the only
  write-back (the flag auto-clear tombstone) requires `FINOPS_KB_WRITE=1` (:203).

**The retrieval two legs + RRF — `src/agentic_dynamics/knowledge/retrieval.py`:**
- Constants: `RRF_K = 60.0` (:47), `LEXICAL_LEG_WEIGHT = 1.2` (:48), `DENSE_LEG_WEIGHT = 1.0`
  (:49), `EXACT_IDENTIFIER_MULTIPLIER = 1.15` (:50), `CONFLICT_MULTIPLIER = 0.70` (:51),
  `EXACT_COMMIT_MULTIPLIER = 1.10` (:52), `AUTHORITY_MULTIPLIER` (:66-71).
- `rrf_base` (:276-283), `compute_fused_score` (:349-371); `retrieve()` runs dense + lexical
  in parallel (:849, :888-906), the lexical leg calls
  `graph_client.search_knowledge_fulltext` (:891-899); `scope_excluded` hard pre-filter
  applied pre-fusion (:395-408, :979-983).
- **K-3:** both legs are LIVE today — the lexical leg returns real hits (33,517 Knowledge
  nodes + `knowledge_text_ft`). The RRF fusion is not "dead"; the read path is gated by
  `rag_augment` defaulting OFF (`runtime/workflow_runner.py:2503-2504`).

**The graph client — `src/agentic_dynamics/knowledge/graph.py`:**
- Fulltext index DDL `knowledge_text_ft` (:97-100), created by `create_knowledge_schema()`
  (:216-228); `search_fulltext(index_name, …)` (:1240);
  `search_knowledge_fulltext(query, limit, commit)` → `search_fulltext("knowledge_text_ft", …)`
  (:1271-1285).

**The registry write path:**
- `scripts/kb_worker.py` kb-registry-v1 handler appends one compacted line per record to
  `experiments/results/registry_index.jsonl` (append-only, never rewritten in place).
- `scripts/generate_manifest.py:51-121` compacts it into `experiments/data_manifest.json`
  `registry` (latest-per-entity, `lifecycle_state` DERIVED). Counts (live):
  **registry_index.jsonl = 34,921 lines**; compacted manifest `registry` = **13,031 rows**
  (12,936 current + 95 tombstoned).
- `scripts/bundle_artifacts.py:53` references the index for the bundle reference check.

**Queue dashboards:** `scripts/monitor.py:28-38` reads all three queues; the queue
reinterleave exists (`scripts/reinterleave_queue.py`, core in
`src/agentic_dynamics/runtime/queue_reinterleave.py`).

**Auth dirs / toolchain (verified on this host):**
- `~/.claude/` (`.credentials.json`, 0700), `~/.local/share/opencode/` (auth.json + the
  62 GB opencode.db), `~/.local/bin/` (claude → `~/.local/share/claude/versions/2.1.228`,
  node, sonar-scanner → `/tmp/sonar-scanner-6.2.1.4610-linux-x64/bin`).
- The **opencode binary is `~/.opencode/bin/opencode`** (v1.18.15) — NOT under `~/.local/bin`
  (see `src/agentic_dynamics/adapters/opencode.py:26-33`). The design's §3 auth-dir mount list
  omits it; the reproduction Dockerfile already mounts it (`Dockerfile:7`). p4 must resolve.

## 4. The failure ledger — the session's fragility evidence (the ladder's requirements)

Each entry: the incident, the evidence, and the requirement the ladder must satisfy.

| # | Incident (design §1 claim) | Evidence | Requirement the ladder must fix |
|---|---|---|---|
| F-1 | cross_models pipeline died (bare-`python` PATH, 600s timeout, archived script path) | `docs/reviews/cross_models_mixed_effect_caveat.md:39-43` (the three backend-reliability defects); `git e6385cac6` (600s shell timeout killed analyze → 3600 at `experiments/definitions/configs/plans.yaml:188,195`); `plans.yaml:121,203` invokes `scripts/archive/backfill_costs.py` (archived by `git f9f89984a`+`b04645a37`) | R1 canonical env per unit; R5 live logs (block-buffered autopsies) |
| F-2 | Campaign wrappers died mid-run (watchdog; post-cells death) | `git b928c4d17` (p1_phase_watchdog: stale agent SIGTERM'd → phase STALLED); `git b435c734e` (2d spec index, STALLED ledger; `experiments/specs/index.json` cap_adaptive_2d status failed); the resumable-grid answer: `scripts/run_cap_2d_grid.py:830-857` (execution-manifest-first, skip recorded); `HANDOFF.md:214` (first campaign launch died — nohup only guards SIGHUP) | R2 health + restart-with-backoff; R3 queue watcher |
| F-3 | Portal + respawn supervisor died (the supervisor SPOF) | `scripts/run_control_room.sh:2` ("died silently three times"); `HANDOFF.md:52,224`; the respawn loop is itself a bare host process | R2 (the supervisor becomes a top-rung container, host runs only the bootstrap) |
| F-4 | 129 analysis jobs queued, zero workers | Live `analysis_status` = exactly **129** (104 failed / 25 done); no watcher code exists; the analysis worker only runs when started by hand | R3 queue watcher + per-queue pools |
| F-5 | Worker env broke twice (claude PATH, then OAuth) | `docs/archive/HANDOFF_2026-08-19.md:129-131` (claude needs `PATH="$HOME/.local/bin:$PATH"` + live OAuth); `docs/experiments/designs/cap_grit_grid_runplan.md:110` (CLAUDE_BIN not exported), `:208-218` (OAuth tokens empty, session expired); `HANDOFF.md:54` (Claude auth down); fix `git d3a1e71db` | R1 canonical env baked into the image |
| F-6 | 70 dead analysis jobs pointed at removed files | Not independently documented (the design's own number); mechanism live at `scripts/analysis_worker.py:135` (worktree missing → fail) | R4 job-queue DLQ surface |
| F-7 | 13 silent-dead story records (0 tokens, 0 cost, exit<0) | `docs/reviews/cross_models_mixed_effect_caveat.md:46-50,80-81`; `git 3bb286195`, `0b5bb38a8` (13 removed), `705a8eb3f` (worker validates real runs) | R2 health; worker-side run validation (already partially done) |
| F-8 | Block-buffered logs; dead-process autopsy | `HANDOFF.md:44-45` (setsid; nohup died twice) | R5 live/streamed logs |

The KB plane's own ledger corroborates the same classes: the stream DLQ holds **2,640**
entries and `kb:v1:dead_letter` already models the dead-letter discipline the job queues lack.

## 5. Open questions carried to p3 (flagged, not fixed here)

- **O-1 (design §2 vs §4):** §2 reserves the socket escalation for the orchestrator rung;
  §4 lists the supervisor as "socket + fleet configs + logs volume + redis". Whether the
  supervisor mounts the socket or delegates restart authority through the orchestrator must
  be resolved in the proposal.
- **O-2 (design §5 currency):** "neo4j empty / consumer missing / chroma-ledger live" do not
  match the stream state (K-1) nor the graph (33,517 nodes) — the design's problem statement
  is outdated, but its commitment (a supervised kb-neo4j-v1 consumer container) still closes
  the real gap: the stream consumers are unwired as **running units**.
- **O-3 (mount contract):** the opencode binary lives at `~/.opencode/bin/opencode`, outside
  the design's §3 auth-dir list — the compose layout must carry it explicitly.
- **O-4:** `redis-test` (6399) and the declared-but-not-running `opencode-server` container
  are unmapped by the design — the proposal's container census must place or retire them.

**LOG (p1):** fleet = 9 containers (all data-plane; no execution container); host = the
opencode server + portal + respawn loop + review trigger/runner + the workflow wrapper
(every execution unit is host-native); queues = story 261 (42 failed) / analysis 129 (104
failed) / review 326 queued, **no DLQ, no watcher**; KB stream = 26,877 entries, **only
kb-registry-v1 has ever consumed** (chroma/ledger/neo4j idle), DLQ 2,640; neo4j populated
33,517 (not empty); the kb-neo4j-v1 handler exists (`kb_worker.py:367-463`); the RRF
two-leg fusion is live, gated by `rag_augment` OFF. Failure ledger = 8 incidents mapped to
requirements R1-R5 (canonical env, health/restart, watcher, DLQ, live logs).
**PASS** — inventory committed.
