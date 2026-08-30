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
| `253a5a089` | the FLEET LADDER — the full implementation: the containerized worker pools (cell/orchestrator/supervisor tiers), the D-2 mount contract, the fleet manager, the egress proxy, the spawn-wrapper + the scope model, the neo4j bridge, the seven audit guards, the smoke-handoff. **Smoke-tested live: a real story ran through the container path ($0.092, 5 sessions, all_successful)** |
| `837799f19` + `c87462442` | the Δ-entropy/β instruments + the LEDGER instrumentation (the attempt/breach fields + the checkpoint-record persistence) |
| `190712d5a` | the DOCS RESTRUCTURE — 150 docs into the taxonomy tree (architecture/designs/preregistrations/results/postmortems/verification/release), the doc-lifecycle guard generalized |
| `f76df9e5e` | the D-2 revision (the smoke test's five findings: the results overlay, the isolated CLI state, the credential-file-ro/state-rw split, the provider config) |
| `49b53f968` + the earlier | grit PARKED (operator's review: the 84-cell campaign over-built — the retry decision is a lookup, not a curve); the OBSERVATIONAL retry analysis + the CONCURRENCY LADDER specs authored + launched |

**Suite: 2,262 passed.** The spec index: 156 (11 experiments + 145 workflows). Main is green.

## 2. The machine's live state (the pick-up picture)

**The fleet (docker, the ladder's real deployment — PARTIAL):**
- 1 story worker up (the concurrency ladder's RUNG-1 — processing the grid at 1-wide)
- 1 trigger-reviews up (the supervisor-tier, waiting on the analysis drain)
- the other 7 pool containers exited (analysis: idle-exit; story: the rung resize)
- the supervisor's CONTAINER version (the `fleet/supervisor` image) built but NOT the one running — the fleet_manager runs as a HOST python process (the F2 gap)
- the data plane unchanged: redis 6380 (finops-queue) + 6379 (finops-redis, the story-agent sandbox) + chroma 8000 + neo4j + sonar ×4

**The queues (redis 6380):**
- story_jobs: 26 queued + 1 running (the ladder's rung-1 grid — the SAME 27 cells re-run at 1 worker to TIME coordination; the outcomes are not new science)
- analysis: 3 queued / 106 failed / 29 done (the failed = the dead-file class + the poison job — correct)
- review_jobs: 550 enqueued (the review pipeline's backlog — the review_unit is triggered by the drain)

**The wrappers (host sessions):**
- the retry-obs: at p4 (the final adversarial — the retry-worthiness findings)
- the conc-ladder: at p0-p1 (rung 1 in flight)
- the portal: systemd (the user unit, Tailscale-only bind 100.83.229.3:8001 — Restart=always — the 5-death fragility class is over)

## 3. The open items (named, actionable — the next session's work list)

1. **F2 — the supervisor as its container.** The `fleet/supervisor` image exists; the fleet_manager runs host-python instead. Run it as the supervisor-tier container (the F2 closure). The game-board surface reads the heartbeats → the portal.
2. **F1 — the egress proxy's enforcement.** The proxy runs (the DENY/ALLOW probe passed); the workers' routing THROUGH it as the single internet policy point — unverified.
3. **The per-phase model split.** Everything's been running pro (the escalation pattern's over-application). The runner supports per-phase models; the mechanical phases (extraction, rungs, computation) should be FLASH, the interpretation phases pro. This also returns flash to the front line (it's registered in opencode — the defaults moved to pro).
4. **The graph-family parts** (the persistent code graph + the trajectory graph — the designs committed as proposed). The neo4j is LIVE now (the ladder's slice 3 ran the consumer — lag 0). The 2e-wall diagnosis (impacted=0 despite the structural edges) becomes runnable on the persistent graph.
5. **The sonnet re-measurement** — blocked on the Claude subscription window (the session-limit deaths are the honest failures — the worker's real-run validation catches them, no junk).
6. **The retry-obs + the conc-ladder verdicts** — when they complete, merge them; the retry-worthiness lookup + the β curve are the replacements for the parked grit campaign.
7. **The regression-table follow-ups** (the docs restructure's post-merge: the experiment indexes — phase 3; the data.js rebuild — done in the seal).

## 4. The operator's decisions already recorded

- **Backlog permanence** (2026-08-29): the old branches (site-revamp, canonical-state, rag-kb, etc.) LEFT AS-IS — historical, not merged, not re-reviewed.
- **Runtime: docker for now** (the podman detour deferred — the data plane stays docker; the side-by-side was the worst of both).
- **EPM = the horizon risk factor** (provider selection + WFM/budget planning, never per-session).
- **β = the snowball tax (measured)** — context inflation + the coordination overhead.
- **Grit parked** — the observational retry analysis + the ladder measure the two operational questions instead.

## 5. The concrete next moves (pick one)

1. Run the supervisor as its container (F2) — 30 min, closes the unused-image gap
2. The per-phase model split (the two active specs' phases carry the model fields) — saves the pro envelope
3. Wait for the retry-obs + the ladder's verdicts, then merge them (the next two findings)
4. The graph-family Part A (the persistent code graph) — the neo4j's live, the 2e-wall fixture's waiting

**LOG:** the session's merges enumerated; the live machine state (the fleet's partial deployment, the queues, the wrappers, the portal); the seven open items named with the actionable fixes; the operator's recorded decisions (backlog, runtime, EPM, β, grit-parked); the concrete next moves. **The machine is green and running; the next session picks up at §3.**
