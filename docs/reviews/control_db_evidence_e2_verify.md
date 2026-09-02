---
status: accepted
kind: verification
spec: control_db_evidence
phase: e2_drain_and_lifecycle
run: verification-rerun
run_id: run-5e31f69b4afa
author_model: deepseek/deepseek-v4-flash
generated_at: 2026-09-02T13:07:00Z
---

# e2 phase verification — the outbox drain command + the zombie-run sweep on merged main

**What this phase is.** The e2 mandate (spec `control_db_evidence`, phase `e2_drain_and_lifecycle`)
says the operator recovery path + the run lifecycle must exist: (a) a drain COMMAND
(`agentic-dynamics control drain-outbox`) that drains the outbox to empty when the stream was
down, reporting delivered/dead/pending honestly; (b) a ZOMBIE-RUN SWEEP that finds `running`
runs whose heartbeat has expired and transitions them to `CANCELLED` via the legitimate
`transition_run` + `ALLOWED_TRANSITIONS` API — never raw SQL — without steering a live run with
a fresh heartbeat. On this VERIFICATION RE-RUN the phase executes against merged main
(`a5ca7988f…`, worktree HEAD `c5c489541…`), where the original run's e2 deliverable
(`65c1b7867`) is already the launched code. The mandate therefore reduces to PROOF, not
re-implementation: is the deliverable present, SHAPE-compliant, wired, tested, and live? This
document records the proof. No source or test file was modified in this phase — the deliverable
was verified, and the scope fence (drain command + zombie sweep ONLY: no change to
`record_terminal_run`'s enqueue shape, no change to the publisher's ack-then-mark) held by
construction — `outbox.py` is not touched anywhere in the merged deliverable's diff.

---

## 1. The deliverable is present in the launched code, SHAPE-compliant

| SHAPE requirement | Where it holds (launched code at HEAD `c5c489541`, source identical to merged main) |
|---|---|
| **(a)** A drain COMMAND (`agentic-dynamics control drain-outbox`), wired in the CLI's control namespace, that drains the outbox so an operator can clear pending rows when the stream was down | `scripts/control_drain_outbox.py:180-211` (`main`) → `run_drain` (`:68-117`) re-runs the SAME `OutboxPublisher.drain` the run path's terminal write uses (`outbox.py:484-518`), under the SAME `_authorized_kb_write()` posture — the recovery path re-runs delivery, it does not re-implement it. CLI mapping `src/agentic_dynamics/cli.py:113` (+ usage `:166`); classified maintained in `scripts/CONTEXT.md`. Resolves live: `python3 -m agentic_dynamics.cli control drain-outbox --help` renders. |
| Reporting delivered/dead/pending counts **honestly** | The machine report carries BOTH the pass accounting (`drained`: delivered/skipped/retried/dead/stream_error) AND the table state before/after (`outbox_before`/`outbox_after`: pending/delivered/dead from `outbox.summarize`), `scripts/control_drain_outbox.py:97-117` — so a stream outage reads as `stream_error` set + `pending` staying put, never a delivered count that did not happen (docstring `:91-95`; `outbox.py:491-496` charges nobody an attempt for an unreachable stream). Exit codes: `0` a report was produced (even with `stream_error`), `3` no control database (never creates one), `2` an argument/database refusal (`:23-33`, `:62-65`). |
| **(b)** A ZOMBIE-RUN SWEEP that finds `running` runs whose heartbeat/lease expired and transitions them to `CANCELLED` with a reason, via the LEGITIMATE transition API (`transition_run` + `ALLOWED_TRANSITIONS`), never raw SQL | `control/run_lifecycle.py:180-252` — `sweep_zombie_runs` reads `db.runs(state=RUNNING)` in one snapshot, judges each run's heartbeat, and for a zombie calls `db.transition_run(run.run_id, CANCELLED, reason=…, actor=…)` (`:237`) with a reason naming the staleness evidence (`:227-230`). `control_db.transition_run` (`:1485`) enforces `ALLOWED_TRANSITIONS` (`:243`) and refuses an illegal edge with `InvalidTransitionError` (`:1528-1529`); the append-only `run_transitions` log (`:867-880`) gains the row — the transition history stays the single honest record. Sweep rules in `control/run_lifecycle.py`, CLI shell `scripts/control_sweep_zombies.py` (mapping `cli.py:114`), which never creates the db (exit 3) and previews with `--dry-run`. |
| The sweep is flag/transition-only, never steers live runs with a fresh heartbeat | Liveness is three-valued (`run_lifecycle.py:28-39`, `classify_running_run` `:161-177`): `live` (heartbeat `last_seen_at` inside the staleness window) → untouched; `zombie` (expired) → cancelled; `unknown` (no heartbeat row at all) → reported, NOT cancelled — absence of evidence of life is not evidence of death. `--dry-run` reports the runs it WOULD cancel without transitioning anything (`:200-204`, `:231-235`). |
| The heartbeat that makes the sweep safe | `RunHeartbeatThread` (`run_lifecycle.py:258-334`) — a daemon thread the composition root starts around the engine: the thread lives exactly as long as the orchestrator process, so a killed runner stops beating. Wired at `scripts/run_workflow.py:567-588` (one beat SEEDED synchronously at run start + thread started — only when there is a run row, never in child mode) and stopped in the `finally` (`:614-616`) before the writer handle closes. A beat is deliberately NOT a state transition: `record_run_heartbeat` (`control_db.py:1665`) upserts `run_heartbeats` (`:860-865`, additive schema v3 `:128`) without touching `runs`/`run_transitions`/the control epoch (`:1397-1398`), so a beat every 30s never reads as a stream of durable changes. Best-effort by contract: a failed beat is logged and swallowed (`run_lifecycle.py:325-334`). |
| Run-path drain NOT rebuilt; `record_terminal_run` enqueue shape + publisher ack-then-mark untouched | The merged deliverable's diff (`65c1b7867`) adds `control/run_lifecycle.py`, the two `scripts/control_*.py` shells, the additive heartbeat schema + writers, the CLI mappings, and the composition-root wiring — it does NOT touch `outbox.py` (the publisher's ack-then-mark and `record_terminal_run`'s enqueue are byte-identical), honoring the fence by construction. |

## 2. VERIFY (a)–(d) — proven by the merged tests, run fresh

All commands ran against this worktree at HEAD `c5c489541`, `-p no:cacheprovider`.

| Point | Test(s) | Result |
|---|---|---|
| (a) the drain command delivers pending rows when the stream returns (the operator path) and reports delivered/dead/pending honestly | `test_drain_delivers_pending_rows_and_reports_honestly` (real db + `FakeStream`; delivered 2, pending → 0, rows really DELIVERED, stream received the events); `test_drain_reports_dead_and_pending_honestly` (a pre-existing DEAD row stays dead, never re-attempted — dead stays dead, pending falls to zero, delivered counts real rows); `test_drain_when_the_stream_is_down_leaves_rows_pending` (a downed stream is reported with `stream_error` and every row honestly stays pending with its retry budget intact — never a delivered count that did not happen); `test_drain_retries_are_reported_and_then_delivered_when_the_stream_returns` (transient failures reported as `retried`, rows stay pending, the SAME drain delivers them once the stream accepts); CLI honesty: `test_cli_reports_a_stream_outage_honestly` (exit 0 + "stream unreachable … stay pending", no lie) | pass |
| (b) the sweep transitions a synthetic zombie `running` row (no heartbeat for N minutes) to CANCELLED via `transition_run`; the append-only log gains the row | `test_sweep_cancels_a_zombie_via_the_legitimate_transition_api` — real SQLite db: the run's state becomes CANCELLED, the `run_transitions` history's last row is `RUNNING → CANCELLED` with `actor == "zombie-sweep"` and a reason naming the last heartbeat, and a second sweep examines 0 (terminal stays terminal); classification rule: `test_classify_running_run_is_three_valued` (live/zombie/unknown — no heartbeat row is never called a zombie) | pass |
| (c) a live run with a fresh heartbeat is NOT touched | `test_sweep_never_touches_a_live_run_with_a_fresh_heartbeat` (fresh beat right now → not cancelled, not transitioned, history shows the creation row only); `test_sweep_reports_unknown_runs_and_leaves_them_alone`; `test_sweep_mixes_live_unknown_and_zombie_in_one_pass` (one pass accounts for every running run; the parts add up to the whole) | pass |
| (d) a drain/sweep failure never fails the run | `test_drain_failure_never_raises` (an unreachable stream and all-publishes-fail both RETURN an honest report — `stream_error`, exhausted rows go `dead` — instead of raising); `test_sweep_failure_on_one_run_never_aborts_the_pass` (a per-run transition refusal is recorded in `errors`, the remaining zombie is still cancelled, the refused row is left untouched); `test_heartbeat_thread_failure_is_swallowed_and_logged` (a failed beat is logged and swallowed, never raised) | pass |
| (supporting) the heartbeat is a liveness proof, not a state change | `test_record_run_heartbeat_upserts_and_does_not_bump_the_epoch` (upsert updates `last_seen_at`/`beat_count`, appends NO `run_transitions` row, moves NO epoch); `test_record_run_heartbeat_refuses_an_unknown_run`; `test_heartbeat_thread_beats_until_stopped` (a started thread beats ≥2× at a 1s interval; `stop()` halts it, is idempotent, and leaves the run untouched) | pass |
| (supporting) the composition root + CLI wiring | `test_main_starts_and_stops_a_run_heartbeat_for_a_recorded_run` and `test_child_mode_starts_no_run_heartbeat` (`tests/test_run_workflow_graph_cli.py:335,358`); the CLI resolution table pins `control drain-outbox`/`control sweep-zombies` (`tests/test_cli_resolution.py:107-109`); `test_sweep_dry_run_cancels_nothing`; `test_sweep_report_serializes`; `test_cli_refuses_when_there_is_no_control_database` (exit 3, never creates the db) | pass |

Command results (all green):

```
python3 -m pytest tests/test_run_lifecycle.py tests/test_control_drain_outbox.py -q -p no:cacheprovider
  → 19 passed          (the sweep + heartbeat + operator-drain, both directions, real sqlite dbs)
python3 -m pytest tests/test_run_workflow_graph_cli.py tests/test_cli_resolution.py tests/test_outbox.py -q -p no:cacheprovider
  → 138 passed         (composition-root heartbeat wiring, CLI resolution, the publisher's run-path drain the command reuses)
python3 -m pytest tests/test_control_db.py tests/test_dependency_direction.py -q -p no:cacheprovider
  → 81 passed          (the heartbeat storage + transition API the sweep uses; Debt-2 boundary intact)
python3 -m pytest tests/test_phase_evidence.py tests/test_control_status.py -q -p no:cacheprovider
  → 74 passed          (the e1 write side this run's premise accrues on + the packet/health surface)
```

**312 tests green** across the control/outbox/lifecycle/CLI/workflow families.

## 3. The deliverable is LIVE for this run — heartbeat beating, sweep provably inert on the live run

Read from the live control db at `/home/drseuss/ai-finops-framework/experiments/results/control/control.db`
at `2026-09-02T13:06Z` (this phase's start boundary), read-only unless noted:

- **The heartbeat is beating for THIS run.** `run_heartbeats` holds one row:
  `run-5e31f69b4afa · last_seen_at 2026-09-02T13:04:47Z · beat_count 34 · actor orchestrator`.
  Observed LIVE over a 30s window: `beat_count` advanced 33 → 34 between two read-only reads
  30s apart — the composition root's `RunHeartbeatThread` is beating every ~30s for the running
  run, exactly the "prove it is alive until the process dies" signal the sweep keys on.
- **The sweep is provably inert on the live run (VERIFY c in the wild).** A `--dry-run` pass of
  the real command over a backup copy of the live db (sqlite `.backup` to
  `/tmp/opencode/live_control_copy.db`, then `scripts/control_sweep_zombies.py --db … --dry-run --json`)
  examined the live dataset and classified the run's fresh heartbeat as **live**:
  `examined: 1 · cancelled: [] · would_cancel: [] · live: [run-5e31f69b4afa] · unknown: [] · errors: []`.
  The running run is untouched — and it would still be untouched by a real pass, because its
  heartbeat is inside the 600s staleness window.
- **The drain command reports the real table honestly.** `scripts/control_drain_outbox.py --db <copy> --json`
  (exit 0): `drained: delivered 0 · stream_error ""` and `outbox_before == outbox_after` at
  `pending 0 · delivered 132 · dead 0`. Nothing is owed: the run path's terminal-write drains —
  68 rows at the followups run + 64 at the failed first evidence run — discharged every
  obligation (the e2 premise, "the run-path drain ALREADY WORKS", is what `pending: 0` shows).
  An empty operator drain reports empty honestly; the delivery path itself is proven by VERIFY (a).
- **No control database → exit 3, never created.** `control drain-outbox --db /tmp/opencode/does-not-exist/control.db --json`
  returned `error: control_db_unavailable` with exit `3`.
- **The pattern the sweep mechanizes is in the history.** The two killed runs the deep review
  documented — `run-d61ec458cb6b` and `run-0aeb16f0d855` — sit `cancelled` with actor
  `orchestrator` and reason `operator cancel: killed run left a dangling row (deep-review cleanup)`:
  manual cancellations through the same `transition_run` the sweep now performs automatically on
  an expired heartbeat. Both are terminal, so the sweep leaves them alone.

The run's own evidence continues to accrue on the same engine: `step_attempts` for
`run-5e31f69b4afa` already holds `e0_pin_spec` and `e1_phase_evidence`, both attempt 1, state
`ok`. This phase's row is appended when it ends; the preregistered criterion
(`step_attempts >= 8`, `gate_results > 0`) stays on track.

## 4. Scope fence

- **Changed:** `docs/reviews/control_db_evidence_e2_verify.md` (this verification record) — one
  file. No source, no tests, no spec, no workflow YAML were modified.
- **Not done, deliberately:** no re-implementation of the drain command or the sweep (both are
  the merged launch state; editing them would undermine the run's premise), no change to
  `record_terminal_run`'s enqueue shape, no change to the publisher's ack-then-mark, no e3
  hermeticity work, no e4 packet work. No live control-db row was mutated: the live read was
  read-only; the sweep demonstration was `--dry-run` on a throwaway copy.

## 5. Verdict

**PASS.** The e2 deliverable — the operator drain command, the zombie-run sweep, and the run
heartbeat that makes the sweep safe — is present in the launched code, matches the SHAPE point
for point (legitimate `transition_run` over `ALLOWED_TRANSITIONS`, never raw SQL; three-valued
liveness; honest both-level reporting; the run-path drain untouched), is wired into the CLI's
control namespace and the composition root, and is proven in BOTH directions by the merged unit
tests (312 green across the four commands above). The live control plane confirms the wiring is
firing for this run: the run's heartbeat row is advancing every 30s as this phase runs, a
dry-run sweep over the live dataset classifies `run-5e31f69b4afa` as live and would cancel
nothing, and the drain command reports the real table honestly (nothing pending — the run path
already drained it). The preregistered run-level criterion (`step_attempts >= 8`,
`gate_results > 0` for this run_id) continues to accrue by the run's own engine writes as
phases e2–e7 complete.
