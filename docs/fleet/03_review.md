---
status: proposed
---

# Fleet-ladder review — p1 (infra inventory) + p2 (KB access map) vs the design + the operator's constraints

**Status: PROPOSED · Date: 2026-08-29T15:50Z · Source: p3_review of the `fleet_ladder_plan`
spec (spec_sha256 `0d30d4bc…`).** BOUNDED to validation — no re-inventory, no re-map. Every
finding cites the p1/p2 artifacts or the code; an unmapped touch is a **FAILED finding**
(reported, not fixed).

## 1. The access-matrix completeness check (p2 map vs the code)

Cross-checked the p2 map's 31 touches against every `register_records(` / `publish_event(` /
`derive_*_records` / retrieval call site in `src/agentic_dynamics/` + `scripts/`. Result:
**6 unmapped KB touches found — FAILED findings (must be added by the proposal).**

| # | unmapped touch | read/write | store | why it was missed | severity |
|---|---|---|---|---|---|
| **F-1** | `knowledge/spec_ingestion.py:560-600` — the run-time per-spec lifecycle publish (`refresh_spec_status`), called from `scripts/run_workflow.py:415` and `scripts/spec_status.py:72` | **write** (stream, `source_type=spec`, `_authorized_kb_write()` temp flag) | kb stream → registry | p2 mapped spec only under P8's batch path (`kb_produce_sources.py:226`); this is a second, run-time entry point | FAILED |
| **F-2** | `control/context_compiler.py:918` — the context-snapshot persist (`make_snapshotting_router`, `SNAPSHOT_SOURCE_TYPE="context_snapshot"`), wired opt-in at `scripts/run_workflow.py:274-276` (`--cap-snapshot`) | **write** (stream, `source_type=context_snapshot`, `authorized=` param) | kb stream → registry | p2's producer list was story/run/review/supervise/kb_produce*/emit — the CAP I4 seam was not enumerated | FAILED |
| **F-3** | `scripts/analyze_trajectories.py:344-347` — reads the `session_embeddings` chroma collection | **read** | chromadb (8000) | p2's R-list covered retrieval/augment/registry/game-board, not the post-hoc analysis reads | FAILED |
| **F-4** | `scripts/lab_basin_topology_neo4j.py:44-60` — the basin-topology lab reads Model/ExperimentRun nodes | **read** | neo4j (7687) | same — a lab analysis read outside the enumerated R categories | FAILED |
| **F-5** | `scripts/run_cap_2e_grid.py:609-633` — the grid probe drives `EvidenceChangeAnalyzer(graph_client=Neo4jClient(...), graph_requested=True)` | **read** | neo4j (7687) | the grid harness's graph read (cap_2e grit-era shape) was not in p2 | FAILED |
| **F-6** | `scripts/context_snapshot_report.py` + `scripts/shadow_decision_report.py` — manifest-registry reports over `context_snapshot` / decision records | **read** | manifest registry | p2's R-list has registry.py + the Control Room, not these report tools | FAILED |

The 31 mapped touches themselves check out (each verified to a live call site). **Net: the
complete KB touch count is 37, not 31.** The proposal's access matrix must absorb F-1…F-6.

## 2. The constraint check (the design's claims vs p1's inventory)

| Design claim | verdict | notes |
|---|---|---|
| The ladder (cell → orchestrator → supervisor) | **PASS** | §2/§4/§6 place every unit type; no *unit type* is unplaced. |
| The mount contract (worktree rw / results rw / repo ro / auth ro) | **FAILED** (two gaps) | p1 found the **opencode binary at `~/.opencode/bin/opencode`** (adapter default, `adapters/opencode.py:26-33`) — outside the §3 auth-dir list; and the **claude binary's target `~/.local/share/claude/versions/…`** is not mounted while the `~/.local/bin/claude` symlink is — a container mounting §3's list gets a broken `claude` and no `opencode`. The proposal must extend the auth set or bake both binaries. |
| The host bootstrap (ONE systemd unit, ~3 lines) | **PASS** | p1: no systemd unit exists today; nothing contradicts the design. |
| Master control = the operator chat | **PASS** | p1 confirms the game board (`system_snapshot.md`) + the CLI surface; the design's §2/§8 restatement holds. |
| The socket as the ONE escalation | **FAILED** (internal inconsistency) | §2 reserves the socket for the orchestrator rung (supervisor adds "fleet configs, log volume, restart authority"), but §4 lists the supervisor as "socket + fleet configs + logs volume + redis". Under the strict reading ("the socket lives ONLY in the orchestrator tier"), §4's supervisor row violates it. The proposal must resolve: supervisor restart authority delegated via the orchestrator, or the socket explicitly admitted to the top rung. |
| The KB wiring incl. the resurrected neo4j leg | **PASS*** | §5's *commitment* (supervised `kb-neo4j-v1` consumer container → the RRF leg live) holds; its *current-state* diagnosis is outdated (p1 K-1/K-2: graph populated 33,517, handler exists, only registry has consumed) — carried to the risk list, not a constraint deviation. |

**Unplaced by the design's ladder (constraint-check residue, into p4):**
- the **opencode web server** (host-native on 4096; the compose-declared `opencode-server`
  container is not running) and its **62 GB opencode.db** — no taxonomy row;
- **`redis-test` (6399)** — live, in no compose file;
- the **review workload** (`trigger_reviews` + synchronous `review_all` + the review
  subprocesses) — the design says "review jobs bind a dedicated pool" but the Redis review
  worker is **retired**; slice 1 must decide containerized-review_all vs a revived worker.

## 3. The guard-preservation check (p2 G1-G6 vs the code)

| guard | p2 condition | verified | preservable |
|---|---|---|---|
| G1 WRITE GUARD | `knowledge_stream.py:184-186` (`FINOPS_KB_WRITE=1` or `authorized=True`) | ✓ exact | **yes** — env-per-process; placement just sets it on writer units only |
| G2 ACTUATION-ARMED | `knowledge_stream.py:188-191` (`FINOPS_ACTUATION_ARMED=1`/`armed=True`) | ✓ exact | **yes** — zero actuation producers today; trivially preserved |
| G3 LINEAGE | `knowledge_stream.py:194-198` + `:121-132` + `SOURCE_TYPE_INDEX_KEY` | ✓ exact | **yes** — code-side; placement keeps the index population |
| G4 REGISTRY APPEND | append-only `registry_index.jsonl`, `generate_manifest.py` compaction | ✓ exact | **yes** — single-writer discipline; the containerized registry consumer keeps it |
| G5 SCOPE (two-channel) | `cell_scope` `self-<worktree>`; `scope_excluded` hard filter | ✓ exact | **yes** — per-cell env, unchanged |
| G6 CONSUMER READ-ONLY | `kb_worker.py:198,203` | ✓ exact | **yes** — the only write-back (flag tombstone) keeps its gate |

**One nuance to preserve explicitly:** the flag auto-clear write-back uses
`authorized=True` **code-side** (`kb_worker.py:212`), bypassing the env check — it is the
single deliberate exception (a consumer writing back a tombstone) and must stay the ONLY
one. The new producers found in §1 (F-1 `_authorized_kb_write()`, F-2 `authorized=` param)
use the same env/param discipline — the proposal must not convert any of them into
un-gated stream writes. **PASS with the documented exception.**

## 4. The risk list + the open questions (for the proposal)

**Risks (12):**
- **R1 — the live workload:** `review_jobs` holds **326 queued** and the analysis drain is
  mid-flight; slice 1 (worker-loop containerization) must not interrupt them (the workflow's
  "only reads" rule extends to the migration).
- **R2 — the data chain single-writer:** containerized producers must preserve
  artifact-before-pointer ordering and the registry append discipline; two consumers
  appending concurrently would corrupt `registry_index.jsonl`.
- **R3 — the auth mounts:** `~/.local/share/claude` + `~/.opencode/bin` are absent from §3's
  list (constraint finding); OAuth `credentials.json` (0700) must stay ro; the **62 GB
  opencode.db** cannot ride the "results rw" mount.
- **R4 — image maintenance:** the base image must bake python deps, node, git, the sonar
  client (currently in `/tmp/sonar-scanner-6.2.1.4610` — ephemeral) + the CLIs' entrypoints;
  drift risk between the image and the host state.
- **R5 — the socket trust boundary:** orchestrator/supervisor mount the socket; a
  compromised top-rung unit is host-equivalent. The isolation claim holds only for cells.
- **R6 — the neo4j dual-write divergence:** the graph is populated by **direct producers**
  (graph client); wiring the stream consumer adds a second writer (MERGE) — duplication /
  supersession divergence risk until the two paths reconcile.
- **R7 — the consumer replay storm:** the chroma/ledger/neo4j groups sit at `0-0`; bringing a
  consumer online replays all **26,877** stream entries (and the **2,640** DLQ entries need a
  disposition). Slice 3 must pick the group's starting point + DLQ drain.
- **R8 — `rag_augment` OFF:** the RRF read path is gated off by default; the "leg goes live"
  claim depends on a product decision to enable it, not just wiring.
- **R9 — the opencode server unplaced:** where the 4096 server + its db live (a
  supervisor-managed unit? host-retained?) is unanswered.
- **R10 — the review-worker revival:** "review jobs bind a pool" requires either reviving the
  retired Redis review worker or containerizing `review_all`; scope creep risk in slice 1.
- **R11 — port discipline:** chroma owns 8000, the portal 8001 (the game-board note); the
  containerized units must not collide, and the declared-but-dead `opencode-server` (4096)
  must be retired or reconciled with the host process.
- **R12 — the kb_worker exception:** the `authorized=True` write-back (`kb_worker.py:212`)
  is code-side; any container refactor must not generalize it.

**Open questions (10) the proposal must answer:**
- Q1 Where do the opencode server (4096) + its 62 GB db live on the ladder?
- Q2 Does the supervisor mount the socket, or is restart authority delegated through the
  orchestrator (resolve §2 vs §4)?
- Q3 How are F-1…F-6 placed (tiers + read/write) in the access matrix?
- Q4 How do the direct-producer stores reconcile with the never-consumed stream groups?
- Q5 Which mounts carry `~/.opencode/bin` and `~/.local/share/claude`?
- Q6 Is the review worker revived or does `review_all` stay a supervisor-run unit?
- Q7 What is the consumer groups' starting point + the DLQ (2,640) disposition in slice 3?
- Q8 Is the `rag_augment` ON decision part of slice 3 or a separate product gate?
- Q9 Are `redis-test` (6399) and the dead `opencode-server` retired or placed?
- Q10 Does the `kb_worker.py:212` `authorized=True` exception move behind the env gate?

**LOG (p3):** access-matrix completeness = **FAILED** (6 unmapped touches: F-1…F-6; 37 total);
constraint check = **PASS on 4/6** (mount contract: 2 gaps; socket: §2-vs-§4 inconsistency);
guard preservation = **PASS** (G1-G6 exact, one documented exception); risks = **12**, open
questions = **10**. **FAIL** — the review passes the guard checks but fails completeness;
the proposal must absorb F-1…F-6 before it can be verified. Review committed.
