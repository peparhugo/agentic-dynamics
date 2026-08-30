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
- 1 story worker up (the concurrency ladder's RUNG-1 — processing the grid at 1-wide, cell ~4/30)
- 1 trigger-reviews up (the supervisor-tier, waiting on the analysis drain)
- the other 7 pool containers exited (analysis: idle-exit; story: the rung resize)
- the data plane unchanged: redis 6380 (finops-queue) + 6379 (finops-redis, the story-agent sandbox) + chroma 8000 + neo4j + sonar ×4

**The queues (redis 6380):**
- story_jobs: 26 queued + 1 running (the ladder's rung-1 grid — the SAME 27 cells re-run at 1 worker to TIME coordination; the outcomes are not new science)
- analysis: 3 queued / 106 failed / 29 done (the failed = the dead-file class + the poison job — correct)
- review_jobs: 180 queued (the review pipeline's backlog — the review_unit is triggered by the drain)

**The wrappers (host sessions):**
- the retry-obs: **DONE + MERGED** (the findings landed; the worktree discarded)
- the conc-ladder: at p1 (rung 1 in flight — the grid's at ~4/30 cells)
- the portal: systemd (the user unit, Tailscale-only bind 100.83.229.3:8001 — Restart=always — the 5-death fragility class is over)

## 3. The open items (named, actionable — the next session's work list)

1. ~~**F2 — the supervisor as its container.**~~ **CLOSED** (commit `6624c2089`): the fleet-manager runs as its container on the canonical repo; the game-board writes the full snapshot to the results mount; the host duplicate killed. If the host ever reboots: `systemctl enable --now fleet-bootstrap` (the unit in `infrastructure/fleet-bootstrap.service`) is the ONE bootstrap step — it is currently NOT installed.
2. **F1 — the egress proxy's enforcement.** The proxy runs (the DENY/ALLOW probe passed); the workers' routing THROUGH it as the single internet policy point — unverified.
3. **The per-phase model split — BLOCKED-BY-PINNING (recorded, not done).** Both candidate specs are hash-pinned: the retry spec's SHA256 is pinned in its own findings/adversary docs + the ledger, and the ladder spec's SHA256 (`cd2bd37a…`) is pinned in the β design header by p0 — editing either breaks traceability, and the running wrapper loaded its spec in-memory at start, so the split can't apply mid-run. **The standard is recorded: mechanical phases (extraction, rungs, computation) → `deepseek/deepseek-v4-flash`, interpretation phases (findings, adversarial) → pro. Apply to the NEXT authored spec** (the graph-family Part A spec), and to the ladder spec at its post-merge revision.
4. **The graph-family parts** (the persistent code graph + the trajectory graph — the designs committed as proposed). The neo4j is LIVE now (the ladder's slice 3 ran the consumer — lag 0). The 2e-wall diagnosis (impacted=0 despite the structural edges) becomes runnable on the persistent graph. **Part A (the persistent code graph) is the pick** — and it is where the per-phase split standard (§3) applies first.
5. **The sonnet re-measurement** — blocked on the Claude subscription window (the session-limit deaths are the honest failures — the worker's real-run validation catches them, no junk).
6. ~~**The retry-obs + the conc-ladder verdicts.**~~ The retry-obs half is **DONE + MERGED** (`e2458bcba`): the retry-worthiness lookup is unidentified (n=1, economically irrational at measured scales — the replacement for the parked grit campaign). The **conc-ladder verdict** is still pending — the rung-1 grid is in flight (~4/30 cells at 1 worker); when the rungs complete, merge them: the β curve is the second half of the grit replacement.
7. **The regression-table follow-ups** (the docs restructure's post-merge: the experiment indexes — phase 3; the data.js rebuild — done in the seal).

## 4. The operator's decisions already recorded

- **Backlog permanence** (2026-08-29): the old branches (site-revamp, canonical-state, rag-kb, etc.) LEFT AS-IS — historical, not merged, not re-reviewed.
- **Runtime: docker for now** (the podman detour deferred — the data plane stays docker; the side-by-side was the worst of both).
- **EPM = the horizon risk factor** (provider selection + WFM/budget planning, never per-session).
- **β = the snowball tax (measured)** — context inflation + the coordination overhead.
- **Grit parked** — the observational retry analysis + the ladder measure the two operational questions instead.

## 5. The concrete next moves (pick one)

1. ~~Run the supervisor as its container (F2)~~ — **done** (`6624c2089`); if the host reboots, enable `fleet-bootstrap.service`.
2. **The graph-family Part A** (the persistent code graph) — the neo4j's live, the 2e-wall fixture's waiting, and the per-phase model split standard (§3) applies to this spec first.
3. Wait for the conc-ladder's rungs, then merge the β curve (the second half of the grit replacement — the ladder's rung-1 grid is at ~4/30 cells).
4. **F1** — verify the workers' egress actually routes through the proxy (the single internet policy point) — a verification pass, ~1h.

**LOG:** the session's merges enumerated; the live machine state (the fleet's partial deployment, the queues, the wrappers, the portal); the seven open items named with the actionable fixes; the operator's recorded decisions (backlog, runtime, EPM, β, grit-parked); the concrete next moves. **The machine is green and running; the next session picks up at §3.**
