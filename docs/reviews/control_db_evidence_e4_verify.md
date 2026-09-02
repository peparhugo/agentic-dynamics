---
status: accepted
kind: verification
spec: control_db_evidence
phase: e4_phase_epoch
run: verification-rerun
run_id: run-5e31f69b4afa
author_model: deepseek/deepseek-v4-flash
generated_at: 2026-09-02T13:17:00Z
---

# e4 phase verification — the per-phase epoch + the packet's phase-progress fields on merged main

**What this phase is.** The e4 mandate (spec `control_db_evidence`, phase `e4_phase_epoch`) says a
turn-to-turn diff must see phase progress, not only run-state movement: (a) `control_epoch` —
which advanced only on run-state transitions (`create→running→promotable` = 2 for an 8-phase run)
— advances on PER-PHASE transitions too, each `step_attempt`'s start and end bumping it inside the
same transaction, with the epoch's meaning documented as "any durable state change, run-level or
phase-level"; (b) the packet keeps its existing fields and additionally exposes
`phases_completed`/`phases_total` for the active run, derived from the run's `step_attempts` rows;
(c) the scope fence is the epoch/phase-progress derivation ONLY — no changes to what the db records
(e1 owns the rows), no drain changes.

On this VERIFICATION RE-RUN the phase executes against merged main (`a5ca7988f…`, worktree HEAD
`bdcd88fdf…`), where the original run's e4 deliverable (`a944e04f9`) is already the launched code —
its two source files (`control_db.py`, `control_status.py`) are **byte-identical at this HEAD**:
`git diff a944e04f9 HEAD -- src/agentic_dynamics/control/control_db.py src/agentic_dynamics/control/control_status.py`
is empty, because no later commit (e5, e6, or the merge) touched them. This branch's only
differences from main are the e0-e3 review documents (`docs/reviews/control_db_evidence_{preregistration,e1_verify,e2_verify,e3_verify}.md`)
and the runner's `run.log`. The mandate therefore reduces to PROOF, not re-implementation: is the
per-phase epoch present and SHAPE-compliant, does the packet name phase progress, do the merged
tests prove both directions, is it LIVE for this run? This document records the proof. **No source
or test file was modified in this phase** — the deliverable was verified, and the scope fence held
by construction.

---

## 1. The deliverable is present in the launched code, SHAPE-compliant

| SHAPE requirement | Where it holds (launched code at HEAD `bdcd88fdf`, byte-identical to merged main's e4) |
|---|---|
| **(a)** `control_epoch` advances on PER-PHASE transitions — each `step_attempt`'s start and end bumps the epoch | `control_db.py` — `start_attempt` (`:1744`) bumps inside its transaction at `:1782` ("a phase moving from not started to in flight is a durable state change (e4)"); `finish_attempt` (`:1787`) bumps at `:1828`. The run-level bumps are unchanged alongside them: `create_run` `:1479`, `transition_run` `:1565`. A *heartbeat* is deliberately epoch-neutral — `record_run_heartbeat` (`:1665`) never calls `_bump_epoch` (the four call sites above are the only ones in the file), because a beat every few seconds is not a state change and must not read as one. |
| The attempt's start/end bump is atomic with the row it describes | Both bumps sit **inside** the same `with self.transaction()` block as the `INSERT` (`:1782`) / `UPDATE` (`:1828`) — an observer can never see a `step_attempts` row whose epoch did not move, nor an epoch move whose row is not durable. |
| **(b)** the epoch's meaning is documented as "any durable state change, run-level or phase-level" | `control_db.py:1384-1402` (`_bump_epoch` docstring, verbatim: "The epoch's meaning (control_db_evidence e4): **any durable state change, run-level or phase-level**") and `:1407` (`control_epoch` docstring); `control_status.py` module docstring `:47-53`. No schema version bump: purely additive semantics on the existing `control_epoch` row, no column or table touched. |
| **(c)** the packet exposes `phases_completed`/`phases_total` for the active run, from the `step_attempts` rows | `control_status.py` — `run_phase_progress` (`:354`) derives the pair from the run's attempt rows: `phases_total` = distinct `step_id`s with ≥ 1 attempt row, `phases_completed` = those whose LATEST attempt (highest `attempt_no`) reached a terminal outcome (`:378-380`; `AttemptRecord.is_terminal` at `control_db.py:525`). `active_run_ref` (`:383`) adds the pair to NON-terminal entries (`:393-394`); `run_ref` (`:333`) keeps the narrow identifier shape for terminal (failed) entries. Both JSON Schema (`_RUN_REF_SCHEMA`, optional integer fields `:215-216`) and `validate_packet` (non-negative int, `bool` excluded, `:862-871`) permit the fields; `format_packet` renders them on the active-run line (`:990-992`). |
| The packet keeps its existing fields | `build_packet`'s key list and every other block are unchanged; the phase fields are additive and optional. `phases_total` is monotonic within a run (append-only rows); a queued run with no rows is `(0, 0)` — no invented progress; a retried phase counts once, by its latest outcome. |

The schema already forbids `(run_id, step_id, attempt_no)` duplicates (`control_db.py:888-900`), so a
retry is a new attempt row on the SAME step — which is what lets `run_phase_progress` count a
retried phase once (`phases_total` is distinct steps, not attempts).

## 2. VERIFY (a)–(d) — proven by the merged tests, run fresh

All commands ran against this worktree at HEAD `bdcd88fdf`, `-p no:cacheprovider`.

| Point | Test(s) / command | Result |
|---|---|---|
| (a) a synthetic 2-phase run with recorded attempts advances the epoch at least 4 (attempt start/end per phase) — a turn-to-turn diff now shows phase progress | `test_phase_evidence.py::test_two_phases_advance_the_epoch_by_attempt_start_plus_finish_each` — one `record_phase_evidence` call is a start+finish pair, so phase 1 moves the epoch by exactly +2 and phase 2 by ≥ +4 total. `test_control_db.py::test_control_epoch_advances_on_attempt_start_and_finish` — the atomic row-level proof: `start_attempt` is `base + 1`, `finish_attempt` is `base + 2`, reads never move it, and a second phase lands on `base + 4` ("an 8-phase run moves the epoch 16 times while it executes"). | pass |
| (b) the packet exposes `phases_completed`/`phases_total` for the active run from the `step_attempts` rows | `test_control_status.py::test_active_run_carries_phase_progress_derived_from_step_attempts` — the active-run entry reads **1/2 mid-flight and 2/2 after finish**, validated by BOTH `validate_packet` and jsonschema. The direction's other edges: `test_a_retried_phase_counts_once_and_by_its_latest_outcome` (attempt 1 then 2 on one step → 1/1, by the latest outcome), `test_promotable_run_carries_its_completed_phase_count` (promotable entries carry it too, 2/2), `test_a_run_with_no_recorded_phases_reports_zero_zero` (0/0, no invented progress), `test_failed_run_entries_keep_the_narrow_identifier_shape` (terminal entries omit the pair), `test_phase_progress_entries_are_byte_identical_for_a_fixed_database` (deterministic per fixed db). | pass |
| (c) the existing epoch tests (run-state transitions) stay green | `test_control_db.py::test_control_epoch_advances_on_every_transition_and_not_on_reads` (create +1, transition +1, reads do not move it); `test_control_status.py::{test_control_epoch_advances_on_a_transition, test_control_epoch_does_not_move_without_a_transition, test_control_epoch_is_monotonic_across_many_transitions}`. All unchanged and green. | pass |
| (d) a run with NO control db still exits cleanly — the epoch is a control-plane feature, never a run gate | `test_phase_evidence.py::test_a_run_without_a_control_db_still_exits_cleanly` — `make_phase_evidence_recorder(None, None)` is `None` (no db, no run row → the seam is inert) and a 2-phase `run_workflow` under it completes `result.ok is True` with both phases `ok`. The CLI twins in `test_run_workflow_graph_cli.py` confirm the same inertness at the seams: `test_control_open_run_child_mode_never_opens_the_control_db`, `test_child_mode_records_no_run_and_injects_no_recorder`; and the read side never fabricates a db: `test_control_status.py::test_cli_distinguishes_a_missing_control_db_from_an_empty_one`. | pass |

Command results (all run fresh this phase):

```
python3 -m pytest tests/test_phase_evidence.py tests/test_control_db.py tests/test_control_status.py -q
  → 144 passed in 4.01s     (the e1 recorder + control_db + control_status suites together: the
                             epoch/phase-progress direction (a)-(d) above plus every e1/e2/p4
                             sibling in the three files, none regressed)
python3 -m pytest tests/test_run_workflow_graph_cli.py -q
  → 20 passed in 0.29s      (per-phase recorder wiring, child-mode inertness, heartbeat
                             composition root — the (d) no-db clean exit holds across the wiring)
```

## 3. The epoch's new meaning is on the instruction surfaces (the original deliverable's docs, verified present)

The merged e4 deliverable updated the surfaces that teach the meaning; all four are in sync at this
HEAD:

- `agent_config/mental-model.md` (the source) and its renders
  `.opencode/instructions/mental-model.md:349-353` / `.claude/rules/mental-model.md`: "`control_epoch`
  = ANY durable state change, run-level (transition_run/create_run) OR phase-level (each
  step_attempt's start/end — control_db_evidence e4), so a turn-to-turn diff sees phase progress";
  "every non-terminal active_runs / promotable_runs entry additionally carries
  phases_completed/phases_total derived from the run's step_attempts rows (what e1 records); failed
  entries keep the narrow identifier shape".
- `scripts/CONTEXT.md:169` (the `control_status.py` classification row): "the db's monotonic
  counter, bumped on EVERY durable state change — run-level transitions AND each step-attempt's
  start/end (control_db_evidence e4), so a turn-to-turn diff sees phase progress"; each
  non-terminal entry carries `phases_completed`/`phases_total`.

## 4. The deliverable is LIVE for this run — the epoch moves per phase and the packet names the progress

Read from the live control db at `/home/drseuss/ai-finops-framework/experiments/results/control/control.db`
at `2026-09-02T13:17Z` (this phase's window), read-only:

```
runs:           run-5e31f69b4afa  control_db_evidence  running
step_attempts:  e0_pin_spec              1 ok  109832 tok  $0.0280
                e1_phase_evidence        1 ok  128397 tok  $0.0334
                e2_drain_and_lifecycle   1 ok  102097 tok  $0.0298
                e3_hermetic_publication  1 ok  116651 tok  $0.0273
gate_results:   0
run_heartbeats: run-5e31f69b4afa · beat 59 · actor orchestrator
control_epoch:  17
```

The live packet, built read-only over that db (`build_packet`, heartbeats not collected):

```
control-status/v1  epoch 17  head bdcd88fdf
  active 2 · awaiting 0 · promotable 1 · failed 1 · unhealthy workers 0
  [running]    run-5e31f69b4afa  control_db_evidence  (no sha)  phases 4/4
  [promotable] run-2bc253a8d87a  control_db_followups  ca0248992  phases 0/0
  safe actions (3):  promote run-2bc253a8d87a · cancel run-2bc253a8d87a ·
                     cancel run-5e31f69b4afa
```

The e4 properties, live on the merged engine's own rows:

- **The packet names the progress.** The active run carries `phases_completed: 4, phases_total: 4`
  derived from its four `step_attempts` rows — the human glance renders `phases 4/4` on the
  active-run line. The old `control_db_followups` run (`run-2bc253a8d87a`, promotable, predates
  e1's recorder) renders `0/0`: **no rows → no invented progress**, exactly the merged test's
  zero-zero direction, on one real database beside a live run at 4/4.
- **A turn-to-turn diff sees phase movement, and heartbeats do not read as one.** e3's verification
  snapshot (`control_db_evidence_e3_verify.md` §4, its `13:10` window) recorded `control_epoch: 15`
  with e0-e2 rows; this phase's read records `control_epoch: 17` with e0-e3 rows. The only durable
  change between the two reads is e3's phase evidence — its attempt start+finish pair, row written
  `13:12:30` — advancing the epoch by exactly **+2 for one finished phase** while the heartbeat
  advanced 45 → 59 (14 epoch-neutral beats in the same window). The epoch moves on the phase, never
  on the beat.
- **Two packets over the unchanged db are byte-identical** (`packet_json` equal across back-to-back
  reads): observation never bumps the epoch, so "nothing changed" is distinguishable from "I have
  not looked".

The preregistered run-level criterion (`step_attempts >= 8`, `gate_results > 0` for
`run-5e31f69b4afa`) continues to accrue by the run's own engine writes: four fully-populated rows so
far, `gate_results` 0 for the correct reason (e0-e3 fired no gate — a clean phase produces no
fabricated row). e4's own row lands when this phase ends, moving the packet's progress line to 5/5.

## 5. Residuals

None introduced by this phase. The wider suite was not re-run here (this phase changes no source or
test, so it cannot introduce a new outcome); the standing pre-existing residuals recorded at the
earlier re-run phases — e3's R-1 (README "By the Numbers" corpus drift, `test_publication_singular_door`
and `test_doc_lifecycle` classes) — are untouched by the e4 epoch/phase-progress fence and remain
recorded-not-fixed for the wave that owns corpus/README drift.

## 6. Scope fence

- **Changed:** `docs/reviews/control_db_evidence_e4_verify.md` (this verification record) — one
  file. No source, no tests, no spec, no workflow YAML were modified.
- **Not done, deliberately:** no re-implementation of the per-phase epoch or the packet's phase
  fields (they are the merged launch state, byte-identical to the original e4 commit `a944e04f9`;
  editing them would undermine the run's premise), no new tests (the merged family covers every
  VERIFY point and runs green), no drain or db-record changes (e1 owns the rows; e4's fence is the
  derivation only), no fix of the standing pre-existing residuals (out of fence). No live
  control-db row was mutated: all live reads were read-only.

## 7. Verdict

**PASS.** The e4 deliverable — the per-phase epoch and the packet's phase-progress fields — is
present in the launched code, matches the SHAPE point for point (`control_db.py`: `start_attempt`
`:1782` / `finish_attempt` `:1828` bump the epoch atomically with their rows while
`record_run_heartbeat` never does; `control_status.py`: `run_phase_progress` `:354` +
`active_run_ref` `:383` expose `phases_completed`/`phases_total` on non-terminal entries, schema +
checker + CLI renderer all carry them; the epoch's run-level-or-phase-level meaning is documented
in code and on the instruction surfaces), and is proven in BOTH directions by the merged unit tests
run fresh (144 passed across the three e4-relevant suites + 20 passed on the workflow/CLI wiring).
It is LIVE for this run: the epoch moved 15 → 17 across the e3 → e4 turn — exactly +2 for the one
phase that completed, against 14 epoch-neutral heartbeats — and the active run's packet entry
renders `phases 4/4` from its real `step_attempts` rows, while the pre-recorder run renders 0/0
(no invented progress). (d) holds: a run with no control db exits cleanly, in the merged tests and
at the wiring seams. No source or test file was modified, the scope fence held, and the
preregistered run-level criterion (`step_attempts >= 8`, `gate_results > 0` for
`run-5e31f69b4afa`) continues to accrue as phases e4–e7 complete.
