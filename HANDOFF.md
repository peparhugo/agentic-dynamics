---
status: accepted
---

# HANDOFF — session 2026-08-30/31: the fleet ladder + the measurement wave

**Status: the session's work is merged and running. This document is the operator's pick-up
surface — the next session starts here. The machine is in a stable, running state; the queued
work is visible; the open items are named.**

## 1. What the session accomplished (all merged to main)

| commit | what landed |
|---|---|
| `e2458bcba` + `602bd8add` | the retry-observational FINDINGS merged — the worktree's 5 phases (extraction → lookup → findings → adversarial 6/6 PASS) + the run ledger + 46 workflow facts. **The headline: exactly one real retry event in the corpus, economically irrational at the measured scales (a $3.19 re-attempt to avoid $0.046 of escaped-defect harm — 69×), so the retry-worthiness lookup is UNIDENTIFIED and the machine's best read at first-failure is cost, not confidence.** The grit parking note landed with it (p0's pin). |
| `6624c2089` | the F2 CLOSURE — the supervisor tier runs as its container on the canonical repo: the game-board's `working_dir: /repo` + `--out /repo/experiments/results/system_snapshot.md` (it was executing the image's stale /app copy and writing the snapshot into the container layer); the stale HOST fleet_manager duplicate killed (the container, bootstrapped from the same compose, is the sole writer of `fleet:board`). |
| `253a5a089` | the FLEET LADDER — the full implementation: the containerized worker pools (cell/orchestrator/supervisor tiers), the D-2 mount contract, the fleet manager, the egress proxy, the spawn-wrapper + the scope model, the neo4j bridge, the seven audit guards, the smoke-handoff. **Smoke-tested live: a real story ran through the container path ($0.092, 5 sessions, all_successful)** |
| `837799f19` + `c87462442` | the Δ-entropy/β instruments + the LEDGER instrumentation (the attempt/breach fields + the checkpoint-record persistence) |
| `190712d5a` | the DOCS RESTRUCTURE — 150 docs into the taxonomy tree (architecture/designs/preregistrations/results/postmortems/verification/release), the doc-lifecycle guard generalized |
| `f76df9e5e` | the D-2 revision (the smoke test's five findings: the results overlay, the isolated CLI state, the credential-file-ro/state-rw split, the provider config) |
| `49b53f968` + the earlier | grit PARKED (operator's review: the 84-cell campaign over-built — the retry decision is a lookup, not a curve); the OBSERVATIONAL retry analysis + the CONCURRENCY LADDER specs authored + launched |

**Suite: 2,262 passed.** The spec index: 156 (11 experiments + 145 workflows). Main is green.

## 2. The machine's live state (the pick-up picture)

**The fleet (docker, the ladder's real deployment — the supervisor tier CLOSED, the cells live):**
- the fleet-manager RUNS AS ITS CONTAINER (the F2 gap closed) — `infrastructure_fleet-manager_1`, `restart: always`, mounted to the CANONICAL repo (/home/drseuss/ai-finops-framework → /repo; it was previously booted with FINOPS_REPO_DIR=/tmp/wt_fleet_impl — the ephemeral worktree), sole writer of `fleet:board` (fresh every 15s; the stale HOST duplicate killed)
- the game-board container now writes the FULL L0 snapshot (13495 bytes, HEAD + history + spec counts) to `experiments/results/system_snapshot.md` via the results mount (was: the image's stale /app copy → a thin 1134-byte file inside the container layer)
- the STORY pool: 1 worker up (the ladder's rung-1 grid at 1-wide — the measurement; the pool resizes to 2/4/8 at the rungs)
- the ANALYSIS pool: 4 workers up (drained the 4 queued in 11s each — the analysis is REAL: full deep metrics written; each cell enqueues 6 review jobs)
- the REVIEW pool: 2 review-units up (1 consumed the manual trigger and ran review_all — 258/259, near-drained)
- the other 5 pool containers exited (analysis idle-exit; story rung resize)
- the data plane unchanged: redis 6380 (finops-queue) + 6379 (finops-redis, the story-agent sandbox) + chroma 8000 + neo4j + sonar ×4

**The wrappers (host sessions):**
- the conc-ladder: at p1 (rung 1 in flight — the grid's at ~4/30 cells)
- the sonnet re-measurement: /tmp/remeasure_sonnet.py — 30 cells, 2 concurrent claude sessions, DIRECT runner (bypasses story_jobs BY DESIGN — the ladder's grid owns the queue). The first launch died 1s-per-cell (the host PATH lacks ~/.local/bin → `claude` not found; the dead files removed + the wrapper fixed: PATH + dead-run self-cleanup). ~4h ETA. Log: /tmp/sonnet_remeasure_run.log.
- the graph-family Part A: /tmp/wt_graph_persistent_code_graph (feature/persistent-code-graph) — the spec carries the PER-PHASE MODEL SPLIT (model_pool [pro, flash]; mechanical phases flash, interpretation pro). p0 in flight. Log: /tmp/graph_family_a_run.log.
- the portal: systemd (the user unit, Tailscale-only bind 100.83.229.3:8001 — Restart=always — the 5-death fragility class is over)

## 3. The open items (named, actionable — the next session's work list)

1. ~~**F2 — the supervisor as its container.**~~ **CLOSED** (commit `6624c2089`): the fleet-manager runs as its container on the canonical repo; the game-board writes the full snapshot to the results mount; the host duplicate killed. If the host ever reboots: `systemctl enable --now fleet-bootstrap` (the unit in `infrastructure/fleet-bootstrap.service`) is the ONE bootstrap step — it is currently NOT installed.
2. **F1 — the egress proxy's enforcement — VERIFIED UNWIRED (the fix is post-ladder).** The proxy runs with the allowlist but has seen ZERO traffic in 5h of logs, and the workers carry no HTTP(S)_PROXY env — they egress directly via NAT; the D-17 "single policy point" is not enforced. The wiring (authored, NOT applied — changing the egress path mid-ladder breaks the rung comparability): add to `ladder-env` in `infrastructure/docker-compose.ladder.yml` `HTTP_PROXY=http://egress:8888` + `HTTPS_PROXY=http://egress:8888` + `NO_PROXY=finops-queue,neo4j,chromadb,localhost,127.0.0.1` (the by-name data-plane hosts), then recreate the pools AFTER the ladder completes.
3. **The per-phase model split — APPLIED (the graph-family Part A spec is the first consumer).** The retry + ladder specs stay hash-pinned (untouched). The standard: mechanical phases (extraction, rungs, computation, build, wiring) → `deepseek/deepseek-v4-flash`, interpretation phases (findings, adversarial, mandate) → pro — carried by `workflow.params.model_pool: [deepseek/deepseek-v4-pro, deepseek/deepseek-v4-flash]` + the per-phase `model:` pins (pin wins over the router — workflow_runner.py:2770). The ladder spec takes the same treatment at its post-merge revision.
4. **The graph-family parts — Part A LAUNCHED** (the persistent code graph, the graph-first change-analysis; the 2e-wall fixture). The neo4j is LIVE (the kb-neo4j consumer — lag 0). Wrapper: /tmp/wt_graph_persistent_code_graph (feature/persistent-code-graph), p0 in flight, log /tmp/graph_family_a_run.log. The 2e-wall diagnosis (impacted=0 despite the structural edges) becomes runnable on the persistent graph.
5. **The sonnet re-measurement — RUNNING** (unblocked 2026-08-31: the Claude auth restored — the binary works; the host PATH just lacked ~/.local/bin). 30 cells via the DIRECT runner (/tmp/remeasure_sonnet.py — bypasses story_jobs: the ladder's grid owns the queue), 2 concurrent claude sessions, ~4h ETA, log /tmp/sonnet_remeasure_run.log. The session-limit deaths were the honest failures — the real-run validation catches them, no junk.
6. ~~**The retry-obs + the conc-ladder verdicts.**~~ The retry-obs half is **DONE + MERGED** (`e2458bcba`): the retry-worthiness lookup is unidentified (n=1, economically irrational at measured scales — the replacement for the parked grit campaign). The **conc-ladder verdict** is still pending — the rung-1 grid is in flight (~4/30 cells at 1 worker); when the rungs complete, merge them: the β curve is the second half of the grit replacement.
7. **The regression-table follow-ups** (the docs restructure's post-merge: the experiment indexes — phase 3; the data.js rebuild — done in the seal).

## 4. The operator's decisions already recorded

- **Backlog permanence** (2026-08-29): the old branches (site-revamp, canonical-state, rag-kb, etc.) LEFT AS-IS — historical, not merged, not re-reviewed.
- **Runtime: docker for now** (the podman detour deferred — the data plane stays docker; the side-by-side was the worst of both).
- **EPM = the horizon risk factor** (provider selection + WFM/budget planning, never per-session).
- **β = the snowball tax (measured)** — context inflation + the coordination overhead.
- **Grit parked** — the observational retry analysis + the ladder measure the two operational questions instead.

## 5. The concrete next moves (pick one)

1. **Collect the Part A + sonnet + ladder verdicts as they land** — three findings are in flight: the graph-family Part A (p0 in flight, ~hours), the sonnet re-measurement (30 cells, ~4h), the ladder's β curve (rung-1 ~4/30 cells, then rungs 2/4/8). Each merges when its wrapper completes (the established pattern).
2. **F1 post-ladder** — apply the egress wiring (HTTP(S)_PROXY + NO_PROXY) to `ladder-env` + recreate the pools once the ladder's four rungs are done (the rung resizes already recreate the story pool — the env change rides along).
3. **The per-phase split at the ladder's revision** — when the ladder merges, add the model_pool + phase pins to `concurrency_ladder.yaml` (Part A is the template).
4. **Part B (the Δ-entropy instrument)** — the design's second half (the solution/test split, the three-axis join, the four-quadrant table); a preregistration pins the ΔH response-curve axis for the next calibration campaign.

**LOG:** the session's merges enumerated; the live machine state (the fleet's partial deployment, the queues, the wrappers, the portal); the seven open items named with the actionable fixes; the operator's recorded decisions (backlog, runtime, EPM, β, grit-parked); the concrete next moves. **The machine is green and running; the next session picks up at §3.**
