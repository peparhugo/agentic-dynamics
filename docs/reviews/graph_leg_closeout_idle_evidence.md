---
status: accepted
kind: evidence
spec: graph_leg_closeout
phase: a2_verify_daemon_survives_idle
run: run-57b8ec179e30
generated_at: 2026-09-04T03:30:00Z
---

# graph_leg_closeout — daemon idle-survival evidence (a2)

**Restart-policy evidence for the a1 fix** (`e6409b07b`, `[workflow] a1_fix_idle_exit`): a
caught-up DAEMON under `restart:on-failure` semantics survives idle — it does NOT self-exit
and the supervisor records zero restarts. The throwaway unit and its artifacts were fully
removed by the phase's end; no live unit, compose file, or store was changed (SCOPE FENCE:
evidence + throwaway unit ONLY).

## Setup

| Field | Value |
|---|---|
| Code under test | `scripts/kb_worker.py` at the b1/b2 worktree HEAD (branch `feature/graph-leg-closeout`, `8b91310ac`/`b71246b1a` — includes the a1 idle-exit removal, `e6409b07b`) |
| Throwaway unit | `~/.config/systemd/user/agentic-dynamics-kb-idletest.service` — `Restart=on-failure`, `RestartSec=5`, `WorkingDirectory=/tmp/wt_graph_leg_closeout`, `ExecStart=/usr/bin/python3 /tmp/wt_graph_leg_closeout/scripts/kb_worker.py --group kb-registry-v1 --consumer kb-idletest-a2` |
| Consumer | `kb-registry-v1` group, fresh consumer `kb-idletest-a2` — the group was **quiet** at probe time (Redis XINFO: pending 0, lag 0, group caught up to stream head `1788491998105-0`), so every poll is an EMPTY poll |
| Isolation | `FINOPS_CONTROL_DB=/tmp/a2_idletest_control.db` (absent) — the empty-poll watermark refresh therefore logs `watermark unavailable (ControlDBError: …)` once per poll, which doubles as the **per-poll cadence proof** in the journal; the throwaway touched NO live control-db row (frontier `1788491998105-0` on the live `registry`/`ledger` rows is byte-unchanged) and processed ZERO entries (`jobs=0` on its heartbeat) |
| Started | `2026-09-04 05:21:53 CEST` (03:21:53Z), Main PID `2662669` |
| Old threshold (the a1 target) | pre-a1 code self-exited after `IDLE_POLLS_BEFORE_EXIT = 12` consecutive empty polls ≈ 12 × 10 s `BLOCK_TIMEOUT_MS` ≈ 2 minutes, exiting 0 — which `restart:on-failure` (restarts only failures) leaves dead |

## The idle window (observed)

| Elapsed | systemd state | MainPID | NRestarts | Empty polls logged |
|---|---|---|---|---|
| ~2 min (`05:23:54`) | active (running) | `2662669` (unchanged) | 0 | journal lines at 10 s cadence (`05:23:34 / :44 / :54`) — **past the old 12-poll / ~2-min exit point** |
| ~3.7 min (`05:25:43`) | active (running) | `2662669` (unchanged) | 0 | 24 |
| **~5.5 min** (`05:27:15–25`) | **active (running)** | **`2662669` (unchanged)** | **0** | **33** |

Journal excerpt (the per-poll cadence — each line is one EMPTY poll's watermark refresh on the
isolated side-channel):

```
[05:23:34][kb-worker] watermark unavailable (ControlDBError: control_db: no control database at /tmp/a2_idletest_control.db)
[05:23:44][kb-worker] watermark unavailable (ControlDBError: control_db: no control database at /tmp/a2_idletest_control.db)
[05:23:54][kb-worker] watermark unavailable (ControlDBError: control_db: no control database at /tmp/a2_idletest_control.db)
...
[05:27:15][kb-worker] watermark unavailable (ControlDBError: control_db: no control database at /tmp/a2_idletest_control.db)
[05:27:25][kb-worker] watermark unavailable (ControlDBError: control_db: no control database at /tmp/a2_idletest_control.db)
```

`systemctl --user show` at the final sample:
`ActiveState=active · SubState=running · MainPID=2662669 · NRestarts=0 · ExecMainStartTimestamp=Fri 2026-09-04 05:21:53 CEST`

The Redis worker heartbeat (`worker:kb-registry-v1:<host>:2662669`) was live at start; because
the process never exited, the daemon heartbeat thread beat for the whole window.

## What this proves

- **(a) the process does NOT exit on idle.** MainPID `2662669` is the same process across the
  entire 5.5-minute window; it kept polling empty batches (33 journal lines ≈ one per ~10 s) —
  more than 2.7× the old 12-poll threshold. Under the pre-a1 code it would have logged
  `idle after 12 polls; exiting` and exited 0 at ~2 minutes; it did not.
- **(b) the supervisor records zero restarts.** `NRestarts=0` across the window — the daemon
  never exited (cleanly or otherwise), so `restart:on-failure` never had a failure to act on.
  This is precisely the semantics the a1 fix makes safe: the OLD clean exit-0 was the footgun
  (on-failure does not restart clean exits); the fix removed the self-exit path entirely.
- **(c) it stays Up until the unit is stopped.** The unit was `active (running)` until the
  phase's explicit `systemctl --user stop`.

## Teardown (clean, verified)

| Check | Result |
|---|---|
| `systemctl --user stop agentic-dynamics-kb-idletest.service` | stopped |
| unit file `rm` + `systemctl --user daemon-reload` | removed; `systemctl --user status` → "could not be found"; `list-unit-files` → 0 |
| idletest process | none remains (`pgrep` for the consumer name → empty) |
| live kb units | `agentic-dynamics-kb-chroma/ledger/registry.service` all still `active (running)` — untouched (they remain `Restart=always`, the documented live-op mitigation; this card only evidenced, never changed them) |
| kb-neo4j container | `infrastructure_kb-neo4j_1 Up 2 hours` — untouched |
| live control db | `registry`/`ledger` watermark frontier unchanged (`1788491998105-0`) — the throwaway's isolated `FINOPS_CONTROL_DB` wrote nothing live |
| worktree | `git status` clean — no stray throwaway artifacts |

## Verdict

**PASS** — a caught-up DAEMON running the a1-fixed `kb_worker` under a `Restart=on-failure`
supervisor survived 5.5 minutes of quiet (33 empty polls, >2.7× the old exit threshold) with
zero restarts and a single unchanged MainPID, staying Up until explicitly stopped; the
throwaway unit and its side-channel were removed and the live units/container/watermarks are
byte-for-byte untouched. The a1 code fix (`e6409b07b`) holds under real supervisor semantics.
