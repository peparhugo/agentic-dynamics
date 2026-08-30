---
status: accepted
---

# Fleet-ladder slice 1 — LIVE cut-over log (the worker pools + supervisor tier)

**Status: PASS · Date: 2026-08-30 · Role: slice 1 live (`fleet_ladder_implementation` p1 —
the execution phase).** Brings the slice-1 compose live on the host docker daemon
(29.1.3) and executes the D-10 sequenced review cut-over + the portal SPOF cut-over. Every
finding is a live command or a container log, not a claim.

## 0. Verdict

**PASS.** The cell + supervisor groups come up, the story/analysis workers drain the queues
without double-processing (BRPOP-atomic distribution proven), the heartbeats appear
(`worker:<type>:<id>`), the DLQ is live and surfaced on `fleet:board`, the review path cut
over exactly once (sequenced, no double-review), and the portal + daemons run as
supervisor-tier containers (the host portal is stopped).

Three slice-1 implementation defects were found and fixed on the way (each a code/mapping
fix, none a guard weakening): the in-network Redis port, the worktree path mapping, and the
missing flask dep. Details in §3.

## 1. Live compose state (the deliverable)

`docker-compose -f infrastructure/docker-compose.ladder.yml ps` (post-cutover):

| service | tier | state | note |
|---|---|---|---|
| `story-worker` ×4 | cell | Up | heartbeat live (`worker:story:<id>:1`) |
| `analysis-worker` ×4 | cell | Exit 0 | drained → idle-exit (existing `IDLE_POLLS_BEFORE_EXIT`) |
| `review-unit` | cell | Exit 0 | ran `review_all` once, then exited (D-10) |
| `orphan-sweep` | cell | Up | flag-only observer |
| `egress` | — | Up | the D-17 internet policy point |
| `fleet-manager` | supervisor | Up | read-only watcher → `fleet:board` |
| `control-room` | supervisor | Up | portal on `127.0.0.1:8001` (HTTP 200) |
| `game-board` | supervisor | Exit 0 | snapshot → results (see §3.4) |
| `trigger-reviews` | supervisor | Exit 0 | `--trigger-only`: signalled review-unit, exited |

The `Exit 0` rows are run-to-completion (correct for `restart: "no"` / drained loops); the
`Up` rows are the persistent daemons. Workers idle-exit when drained (existing `worker.py`
`IDLE_POLLS_BEFORE_EXIT`), consistent with D-14's static-pools + `restart: on-failure`
model — the pool is refilled by `up -d --scale`.

### 1a. The board surfaces the liveness (item 3)

`GET fleet:board` (db1 / 6380) after the probe:

```
alive: 8  dead: 0   dlq: {story_jobs: 0, analysis_jobs: 0, review_jobs: 0}
workers: worker:story:* ×4, worker:analysis:* ×4   (all age < 3s)
```

After the DLQ probe (§2): `dlq: {story_jobs: 0, analysis_jobs: 3, review_jobs: 0}` — the
DLQ surface is live and the board reads it.

### 1b. The network policy holds (D-17)

`fleet-net` membership = `finops-queue chromadb neo4j sonarqube ×4` + the ladder services.
`finops-redis` (6379) and `redis-test` (6399) are **absent** — the story-agent sandbox is
structurally unreachable from the cells.

## 2. Test evidence — no double-processing

The story/analysis queues were empty at cut-over (no in-flight work to double-process), so
the atomicity was proven with a controlled 3-job probe onto `analysis_jobs` (synthetic jobs
with missing worktrees — the terminal-failure path, R4):

1. `RPUSH analysis_jobs` 3 jobs (`__dlq_probe_1..3`) → `LLEN` 3→0 **instantly**.
2. Each job processed by a **distinct** worker (worker_1, worker_2, worker_4) — BRPOP
   atomic distribution, no job claimed twice.
3. `analysis_status` = `failed` ×3 (each exactly once).
4. `analysis_jobs:dead_letter` = 3 entries, reason `worktree missing: …` — the DLQ recorded
   the terminal failures; `fleet:board` reflects `dlq.analysis_jobs = 3`.

**No double-process.** (BRPOP atomicity is a Redis guarantee; the 3→3 distinct-worker
distribution is the empirical confirmation.)

## 3. Defects found and fixed (all live, none a guard weakening)

| # | defect | fix |
|---|---|---|
| D-1 | the ladder connected to `finops-queue:6380` — the **host** published port; on `fleet-net` the queue listens on its **internal** 6379 (Connection refused at boot) | `FINOPS_REDIS_PORT: 6379` in `x-ladder-env` (comment explains host 6380 → container 6379; the 6379 sandbox is never attached, so the two-channel rule holds topologically) |
| D-2 | the worktree mount was `host /tmp → /wt` with `FINOPS_WORKTREE_ROOT=/wt`, but existing story results store `worktree: /tmp/story_*` (host path) and `run_story.py` hardcodes `/tmp` — the additive cut-over needs one path namespace | mount `${FINOPS_WORKTREE_ROOT:-/tmp}:/tmp:rw` + `FINOPS_WORKTREE_ROOT: /tmp` (identical host/container paths; still the "worktree rw" category) |
| D-3 | `control-room` (portal) crashed: `ModuleNotFoundError: flask` — the image installs `.[neo4j]` only | `Containerfile.fleet` → `.[neo4j,admin]` (the `admin` extra = flask) |
| D-4 | `game-board` (`system_snapshot.py`) crashed: `PermissionError` writing `/app/agent_config` (repo ro, `/app` root-owned) | `--out /app/experiments/results/system_snapshot.md` (results rw); canonical L0 board stays host-generated |
| D-5 | `enqueue_reviews.py` hardcoded `REDIS_HOST=127.0.0.1` (unreachable in-container) | `FINOPS_REDIS_HOST` env |
| D-6 | `review_cutover.sh` `pgrep -f` self-matched a `bash -c` wrapper carrying the pattern in argv | patterns tightened to `python3 .*<name>\.py` |

Plus two **wiring** gaps the modules anticipated but never connected (the heartbeats/DLQ
were written but not attached to the workers):

- `scripts/worker.py` / `scripts/analysis_worker.py` now start a `HeartbeatThread`
  (`worker:<type>:<hostname>:<pid>`) and `record_dead` on terminal failures (the R4 class).
- The review path split (D-10): `trigger_reviews.py` gained `--trigger-only` (enqueue →
  LPUSH `fleet:review_trigger` → exit); new `scripts/fleet/review_unit.py` BRPOPs that
  trigger and runs `review_all.py` exactly once. The supervisor no longer runs `review_all`
  itself — exactly one review runner, no double-review window.

## 4. The review cut-over (D-10, sequenced)

1. **STOP** — no host `trigger_reviews`/`review_all` was running (verified before the
   cut-over; the host's synchronous review path was already idle).
2. **DRAIN** — no in-flight `review_all` (drained).
3. **START** — `up -d trigger-reviews review-unit`.

Result (container logs): `trigger-reviews` → "Analysis complete … Enqueued 0 review jobs …
Signalled review-unit via fleet:review_trigger (len=1)"; `review-unit` → `review_all.py`
"Done: 244 stories, 0 errors … exited 0". **The review ran exactly once.** (The `review_jobs`
list still holds 338 stale entries from the retired Redis review worker — `review_all` reads
the filesystem, never that queue; a pre-existing orphan, not a cut-over regression.)

Note: `review_all` re-writing 6 review files (3 +/3 −) as it re-synced commit reviews to the
current worktree state was **reverted** — the cut-over's purpose is mechanism verification,
not review-data mutation.

## 5. The portal cut-over (item 4, the SPOF fix)

The host portal (`run_control_room.sh` + `server.py` on `0.0.0.0:8001`) was stopped and its
respawn loop terminated; the container `control-room` (binds `127.0.0.1:8001`) serves
`GET /` and `GET /api/matrix` → HTTP 200. The portal is a **cut-over** (not additive): the
host held `0.0.0.0:8001`, which the container's `127.0.0.1:8001` publish conflicts with, so
the host process is stopped before the container binds — no double-process, only a port
bind.

## 6. Known issues (not slice-1 regressions)

- The `story-worker` logs `Timeout reading from socket` every ~70s (pre-existing
  `health_check_interval=30` + blocking `BRPOP` interaction in `worker.py`); non-fatal —
  workers reconnect and keep heartbeating.
- The `review_jobs` queue (338) is orphaned (retired review worker); `enqueue_reviews.py`
  re-populates it but nothing consumes it. Slice-3 DLQ triage territory.
- The egress proxy is defined and Up, but the cells do not yet set `HTTP(S)_PROXY` to it
  (the network-policy *enforcement* is the slice-4 guard's job).

## LOG

**PASS.** Slice 1 live: compose up (12 services), BRPOP-atomic drain proven (3 jobs → 3
distinct workers, no double-process), heartbeats + DLQ live on `fleet:board`, the review
path cut over exactly once (sequenced D-10), the portal containerized (host portal stopped).
Six live defects fixed (port 6379, `/tmp` path mapping, flask, game-board write, enqueue
host, cut-over pattern) + the heartbeat/DLQ/review-split wiring completed. Committed.
