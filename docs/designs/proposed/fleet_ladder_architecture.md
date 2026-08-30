---
status: proposed
spec_sha256: 0d30d4bc6d6014c8f1d2283aaad88c79dd9b6d749ca9a48e6b028f35ff733589
---

# The fleet ladder — containerized execution, supervised fleet, master control

**Status: PROPOSED (2026-08-29, operator-directed).** The infrastructure design: every
execution unit becomes a container on a **privilege ladder** (cell → orchestrator →
supervisor), the host runs one bootstrap unit, the queue pools live inside the supervisor's
domain, the knowledge base wires into the data plane (with the **resurrected neo4j lexical
leg** — the RRF fusion is already coded in `retrieval.py`/`graph.py`; the missing piece is the
`kb-neo4j-v1` consumer), and **master control is this chat** — outside the ladder entirely.

## 1. The problem (this session's measured evidence)

The execution plane is host-native ad-hoc processes (started by hand with `setsid nohup`):
the story/analysis/review queue workers, the campaign wrappers, the portal, the daemons. The
session's failure ledger:

- the cross_models pipeline died 3× (bare-`python` PATH, a 600s timeout, an archived script
  path) — each diagnosis required a dead-process autopsy (block-buffered logs);
- two campaign wrappers died mid-run (the watchdog; the post-cells death) — no restart, no
  health;
- the portal + its respawn supervisor died (the supervisor pattern's SPOF flaw);
- 129 analysis jobs sat queued with zero workers (the fleet has no watcher);
- worker env broke twice (the claude PATH, then OAuth) — no canonical env;
- 70 dead analysis jobs pointed at removed files — no dead-letter surface.

**The operator's constraint:** the agents (opencode / claude CLI sessions) need host-level
access — worktrees, the repo, the CLIs' auth — so **docker was off-limits for execution**.
This design resolves the tension by re-scoping what "host access" means: the *container* gets
exactly the host paths the agents need (the mount contract), and the container runtime
provides the isolation the bare processes lacked.

## 2. The architecture

```
HOST (your box)
├── docker daemon                       ← the only host service
├── ONE bootstrap unit (systemd, ~3 lines): run the supervisor container, restart=always
└── [SUPERVISOR container]              ← top rung
    │  manages the fleet: data plane + orchestrators + cells + queue pools + kb consumers
    │  publishes heartbeats → the game board
    │
    └── the ladder (one declared escalation per rung, all in the compose configs):
        cell          (no socket)
        orchestrator  (+docker socket — spawns sibling cells)
        supervisor    (+fleet configs, log volume, restart authority)

MASTER CONTROL — this chat, OUTSIDE the ladder
├── reads the game board (supervisor-published state)
├── holds the permanence gate (what becomes chronological history)
├── directs the supervisor (start / stop / drain via the CLI)
└── never a daemon — the operator's authority, modeled in the repo as the controller role
```

**The host's footprint of ours: the bootstrap unit only.** Everything else is a container on
the ladder, or the operator's chat.

## 3. The mount contract (the isolation constant — hard rule)

Every execution container mounts EXACTLY this set:

| mount | mode | why |
|---|---|---|
| its worktree (the cell's `/tmp/wt_*` or the orchestrator's campaign worktree) | rw | the only writable host path |
| the results dir (`experiments/results/…`) | rw | where results land |
| the repo | ro | the runner/specs — read-only |
| the auth dirs (`~/.claude`, `~/.local/share/opencode`, `~/.local/bin`) | ro | the model CLIs' credentials + binary |
| the toolchain | baked into the image | python deps, node, git, the sonar client |

Rule: **no other host path is mounted, ever.** A cell container can `rm -rf /` — it kills
only its own cell. The isolation claim holds only while the mount discipline holds; the
compose configs are the audit surface (a guard test verifies them — see §9).

## 4. The unit taxonomy + per-queue pools

| unit type | runs in | privileges | fleet role |
|---|---|---|---|
| data plane (redis 6380, chroma 8000, sonar 9000–9003, neo4j 7474/7687) | docker (unchanged) | network | the services |
| **cell** (story/analysis/review worker loops, kb consumers — each worker = one container running its queue loop) | docker | mount contract | one job at a time, per-queue pools |
| **orchestrator** (campaign wrappers, grid harnesses) | docker | mount contract + socket | spawns sibling cell containers per grid wave |
| **supervisor** | docker | socket + fleet configs + logs volume + redis | the fleet manager: pools, restart-with-backoff, live logs, heartbeats, drain |
| master control | this chat | the game board + the permanence gate | direction only |

**The queue topology (per-queue pools, inside the supervisor's domain):** `story_jobs`,
`analysis_jobs`, review jobs each bind a dedicated pool of cell-tier containers (a configurable
count per queue); failed jobs land in a **dead-letter list** (the session's 70-dead-jobs
lesson); each worker writes `worker:<type>:<id> → {last_seen, jobs, pid}` heartbeats that the
supervisor surfaces to the game board + Control Room.

**The grid mechanism:** the orchestrator container (the campaign wrapper's p2 phase) mounts
the socket and spawns N sibling cell containers per wave — the 4-wide shape unchanged, now
container-to-container.

## 5. The knowledge-base wiring (incl. the resurrected neo4j leg)

The KB stream (`kb_stream`, Redis db2 on 6380 — the framework queue's second DB) is produced
by the ingestion call sites (story/run/review/supervise + the `kb_produce*` scripts). Four
consumer groups are declared (`knowledge_stream.CONSUMER_GROUPS`); the wiring in the ladder:

| group | consumer (a cell-tier container) | target | state |
|---|---|---|---|
| `kb-chroma-v1` | the dense embedder + upsert | **chromadb** (data plane, port 8000) | **live** — `knowledge_chunks_v1` 812 + `session_embeddings` 2,215 |
| `kb-ledger-v1` | the ledger reducer | the ledger facts | live |
| `kb-registry-v1` | the append-only registry index | `registry_index.jsonl` → the manifest | live (13k entities) |
| `kb-neo4j-v1` | **the missing consumer — to be built** | **neo4j** (data plane, running, empty) | **dead — the resurrected leg** |

**The resurrected neo4j plan (NOT lost — half-built):** the retrieval side is fully coded —
`retrieval.py` plans two legs (dense Chroma + lexical Neo4j full-text), fuses them with the
RRF base (`rrf_base`, `RRF_K = 60.0`, the authority/freshness/exact/conflict multipliers), and
the graph client implements `search_knowledge_fulltext` over the `Knowledge.text` full-text
index (`graph.py`). What was never built: **the consumer that populates neo4j from the stream**
(the group is declared, nothing consumes it — the graph is empty, which is why neo4j appears
"unused"). This design wires it: the `kb-neo4j-v1` consumer container ingests the stream →
upserts Knowledge nodes + maintains the full-text index → the lexical leg goes live → the RRF
fusion becomes real (the two-leg retrieval the code already promises). The neo4j container
stays in the data plane; the consumer is the missing bridge.

## 6. The images (base → orchestrator → supervisor)

- `fleet/base` — python deps (the repo's), node, git, the sonar client, the auth-aware CLIs'
  entrypoints; the mount contract as the default (`WORKDIR` + the four mounts declared in the
  compose, not the image).
- `fleet/orchestrator` — base + the docker CLI + a policy wrapper for sibling spawn (the only
  escalation).
- `fleet/supervisor` — orchestrator + the fleet manager (the supervisor logic: pools,
  restart-with-backoff, live logs, heartbeats, drain) + the compose configs (read-only) + the
  logs volume.

Built from the repo (a `Dockerfile` at the repo root, versioned — the image is a controlled
variable of the experiments, rebuildable at any commit).

## 7. The migration path (slices)

1. **The base image + the supervisor + the first pools** — the story/analysis/review workers
   as cell-tier containers under the supervisor (the current ad-hoc workers replaced); the
   portal + daemons as supervisor-managed units; heartbeats + DLQ live; the game board +
   Control Room surface the fleet.
2. **The orchestrator migration** — the campaign wrapper runs as an orchestrator container;
   the grid harness spawns sibling cell containers (the 2f/grit-era shape).
3. **The neo4j consumer + the RRF leg live** — the `kb-neo4j-v1` consumer built + supervised;
   the retrieval's two-leg fusion activates; the retired-vs-wired question closes (wired).
4. **The audit guards** — a compose-contract guard test (the mount contract holds: no
   unexpected mounts), a fleet-health guard (the heartbeats + DLQ counts on the board), the
   neo4j index-guard (the full-text index populated ↔ the stream's pending).

## 8. The master-control boundary (restated)

This chat is master control: it reads the game board, decides the permanence gate, and directs
the supervisor. It is not a service. The supervisor never decides what becomes permanent; the
controller (operator + the game board) does — the repo's existing role split, now with the
supervisor as a container instead of a fragile respawn script.

## 9. Guard

The ladder's contract is auditable: the compose configs declare every mount (the guard test
parses them and asserts the mount contract — no path outside the four), every escalation (one
per rung), and every unit's restart policy (`restart=on-failure` + backoff). The heartbeats +
DLQ are the board's fleet-health numbers. The KB wiring's completeness is measured: the
`kb-neo4j-v1` group's pending = 0 (the graph caught up), and the RRF fusion's lexical leg
returns non-empty on real queries.

**LOG:** the fragility evidence enumerated; the ladder (cell → orchestrator → supervisor) with
the mount contract as the isolation constant; the supervisor as the top-rung container behind
a 3-line host bootstrap; master control = this chat, outside the ladder; the per-queue pools +
DLQ + heartbeats; the KB wiring table with the resurrected neo4j leg (the retrieval RRF fusion
is coded; the `kb-neo4j-v1` consumer is the missing bridge); the image layout; the migration
slices; the audit guards. **PROPOSED — slice 1 is the first implementation.**
