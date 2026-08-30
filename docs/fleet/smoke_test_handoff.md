---
status: proposed
---

# Fleet-ladder — the operator's smoke-test HANDOFF

**Status: PROPOSED — the operator's gate.** The implementation phases (slices 1-4 + the
adversarial pass) are committed. This document is the handoff for the **operator's smoke test**
— a real cell through the container path. The smoke test is **NOT run by the implementation**
(the operator gates production, proposal §7). Everything below is the exact commands, the
expected outputs, and the rollback — prepared, not executed.

> Known-open findings from the adversarial pass (`docs/reviews/fleet_ladder_implementation_
> adversary.md`): **F1** (the egress proxy is not yet the enforced single internet policy
> point) and **F2** (the `fleet/supervisor` image is unused). Neither blocks this smoke test —
> it exercises the cell path, the queues, the heartbeats, and the RRF — but the operator
> should read them before any production cut-over.

## Part 1 — Run instructions

### 1a. A REAL cell through the container path (the story cell)

The cell is the **story worker**: `docker-compose` runs `scripts/worker.py` (the BRPOP worker)
in the `fleet/base` container; it pops a job off `story_jobs`, runs the 5-session story, and
saves the result.

```bash
cd /tmp/wt_fleet_impl

# 1. Enqueue ONE real cell (a real cell id + factor assignment) onto the framework queue
#    (db1 on finops-queue, in-network port 6379).
docker exec finops-queue redis-cli -n 1 RPUSH story_jobs \
  '{"cell_id":"smoke_deepseek_task_manager_api_tier1_minimal_good_clean",'\
'"story":"task_manager_api","tier":"tier1_minimal","quality":"good","condition":"clean",'\
'"model":"deepseek/deepseek-v4-pro"}'

# 2. Bring up ONE story-worker container (the cell container, non-root uid 1001).
docker-compose -f infrastructure/docker-compose.ladder.yml up -d --scale story-worker=1 story-worker

# 3. Watch it pop the job + run the 5-session story (the binary probe runs first).
docker logs -f infrastructure_story-worker_1
```

**Alternative — run the cell directly (no queue) via `docker compose run`.** The one-shot
shape the operator's gate names — the same `story-worker` cell service, command overridden to
run one story with a test cell id:

```bash
docker-compose -f infrastructure/docker-compose.ladder.yml run --rm \
  -e FINOPS_CELL_ID=smoke_test_000 \
  story-worker python3 scripts/run_story.py task_manager_api \
  --model deepseek/deepseek-v4-pro --tier tier1_minimal \
  --codebase-quality good --condition clean
```

(The `run-single` batch service is the analogous one-shot for a *perturbation* experiment:
`docker-compose -f infrastructure/docker-compose.ladder.yml run --rm run-single
<config.yaml> --model deepseek/deepseek-v4-pro` — a different cell kind, not the story cell.)

**Expected result path.** The worker's own log prints the machine-readable
`{"result_path": "..."}` line when the cell saves; the file lands at

```
experiments/results/stories/<story>_<model-slug>_<condition>_<story_id>.json
# concrete (model_slug('deepseek/deepseek-v4-pro') == 'deepseek_v4_pro'):
#   experiments/results/stories/task_manager_api_deepseek_v4_pro_clean_<story_id>.json
```

and the `story_status` hash flips to `done` (`docker exec finops-queue redis-cli -n 1 HGET
story_status <cell_id>`).

**Expected heartbeats.** While the cell runs (and after), the board shows it:

```bash
docker exec finops-queue redis-cli -n 1 --scan --pattern 'worker:story:*'
# → worker:story:<container-id>:1   (a hash with last_seen/jobs/pid)
docker exec finops-queue redis-cli -n 1 GET fleet:board
# → "alive_workers" >= 1 with the worker:story:* entry listed
```

### 1b. The binary-resolution probe — expected output

Every cell/orchestrator container runs the probe at start (D-18). Expected output (from a
healthy host):

```
[ok]     opencode: /home/drseuss/.opencode/bin/opencode -> /home/drseuss/.opencode/bin/opencode (1.18.15)
[ok]     claude: /home/drseuss/.local/bin/claude -> /home/drseuss/.local/share/claude/versions/2.1.228 (2.1.228 (Claude Code))
BINARY-PROBE: PASS — opencode + claude chains resolve and run.
```

A broken symlink chain exits non-zero with `BINARY-PROBE: FAIL` and a per-CLI failure reason —
the container fails loudly, not silently.

### 1c. The review cut-over — re-run instructions (D-10)

If a new analysis/review cycle is needed, re-run the sequenced cut-over (it stops the host
path, drains it, then starts the containerized path):

```bash
bash scripts/fleet/review_cutover.sh cutover
```

Expected: `[review-cutover] STOP: …` / `DRAIN: …` / `START: … containerized review path is up`;
`trigger-reviews` enqueues + signals `fleet:review_trigger`, and `review-unit` runs
`review_all.py` exactly once (no double-review window).

### 1d. The orchestrator's scope-driven spawn (optional, the slice-2 path)

The sibling-spawn path is `run_workflow.py --orchestrator` (each agent phase spawns as a
sibling cell with its scope, validated by `spawn_wrapper` before the socket call):

```bash
docker-compose -f infrastructure/docker-compose.ladder.yml run --rm workflow-runner \
  --spec workflows/repository/fleet_ladder_implementation.yaml \
  --goal "<the goal>" --model deepseek/deepseek-v4-pro --workdir /tmp/wt_fleet_impl --orchestrator
```

(A phase whose scope fails validation is REFUSED before the socket — `REFUSED before the
socket call` in the log.)

## Part 2 — The verification checklist

The smoke test passes when ALL of these hold:

- [ ] **The cell's result lands.** A new `experiments/results/stories/*.json` appears for the
      cell, and `story_status[<cell_id>] == "done"`.
- [ ] **The queues move without double-processing.** `story_jobs` drains to 0, and the cell is
      processed exactly once (BRPOP-atomic — one worker, one result; the probe in slice 1 showed
      3 jobs → 3 distinct workers).
- [ ] **The heartbeats appear.** `worker:story:*` keys exist on `fleet:board`, `alive_workers`
      ≥ 1, and the entry's `last_seen` is fresh (< 45 s stale).
- [ ] **The neo4j group is caught up.** `docker exec finops-queue redis-cli -n 2 XPENDING
      kb:v1:changes kb-neo4j-v1` → `0`.
- [ ] **The RRF returns fused results.** A real query returns non-empty from BOTH legs:
      `search_knowledge_fulltext(<query>)` non-empty (lexical) AND `retrieve(<query>)` returns
      fused candidates with `fallback_mode == "full"` (dense + lexical).
- [ ] **The guard suite is green.** `python3 -m pytest tests/ -m "not external" -q` → 0 failed
      (the seven slice-4 guards included).

## Part 3 — Rollback (the additive inverse)

The story/analysis migration was **additive** (BRPOP-atomic), so rolling back is just stopping
the containerized workers and re-launching the ad-hoc host workers:

```bash
# 1. Stop the containerized workers + the supervisor tier.
docker-compose -f infrastructure/docker-compose.ladder.yml stop story-worker analysis-worker \
  fleet-manager control-room game-board trigger-reviews kb-neo4j

# 2. Re-launch the ad-hoc host workers (the pre-ladder shape).
setsid nohup python3 scripts/worker.py          >/tmp/worker.log 2>&1 &
setsid nohup python3 scripts/analysis_worker.py >/tmp/analysis.log 2>&1 &
bash scripts/run_control_room.sh &              # the host portal (respawn loop)

# 3. The review path is a cut-over (not additive) — restart the host trigger_reviews:
setsid nohup python3 scripts/trigger_reviews.py >/tmp/trigger_reviews.log 2>&1 &
```

Because the queue is shared and BRPOP is atomic, no job is double-processed during the
transition — the old and new workers drain the same queue without overlap. The neo4j graph is
not rolled back (MERGE is additive — D-12); stop `kb-neo4j` and the graph simply stops growing.
`rag_augment` is set back to `false` in `workflows/repository/fleet_ladder_implementation.yaml`
(the slice-3 product gate's inverse).

## LOG

Handoff prepared (not run): the story-cell command + expected result path + expected
heartbeats; the binary-probe expected output; the review cut-over re-run; the orchestrator
scope-spawn; the six-item verification checklist; the additive-inverse rollback. Status:
proposed — the operator's smoke test gates production.
