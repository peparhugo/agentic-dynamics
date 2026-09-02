---
status: accepted
kind: verification
spec: control_db_evidence
phase: e1_phase_evidence
run: verification-rerun
run_id: run-5e31f69b4afa
author_model: deepseek/deepseek-v4-flash
generated_at: 2026-09-02T13:00:20Z
---

# e1 phase verification — the per-phase evidence recorder on merged main

**What this phase is.** The e1 mandate (spec `control_db_evidence`, phase `e1_phase_evidence`)
says the engine must write the per-phase evidence — one `step_attempts` row + one `gate_results`
row per fired gate verdict per executed phase — and the write side + its tests must be committed.
On this VERIFICATION RE-RUN the phase executes against merged main (`a5ca7988f…`, worktree HEAD
`e56dbe6dc…`), where the original run's e1 commit (`c353ddf58`) is already the launched code.
The mandate therefore reduces to PROOF, not re-implementation: is the write side present,
SHAPE-compliant, wired, tested, and live? This document records the proof. No source or test
file was modified in this phase — the deliverable was verified, and the scope fence (e1 write
side only: no e2 drain, no e4 packet, no e3 hermeticity changes) held by construction.

---

## 1. The write side is present in the launched code, SHAPE-compliant

| SHAPE requirement | Where it holds (launched code at HEAD) |
|---|---|
| One `step_attempts` row per executed phase `(run_id, step_id, attempt_no, model, state, started_at, ended_at, tokens, cost_usd, exit_code, error)` | `control/phase_evidence.py:63-79` — `record_phase_evidence` composes `db.start_attempt` → `db.finish_attempt` in ONE transaction; every field the SHAPE names is passed. |
| One `gate_results` row per gate verdict `(commit_gate, relabel_gate, deploy_gate)`, bound to the candidate | `control/phase_evidence.py:80-92` — one `db.record_gate_result` per fired gate with `candidate_sha=evidence.candidate_sha`; `runtime/phase_evidence.py:55-60,96-113` — a gate contributes a row only when it FIRED (a clean gate leaves no fabricated row); the verdict maps `APPROVED → pass`, every violation reason → `fail`. |
| Reuse the control db's existing writers (the INSERT path `transition_run` uses; `record_gate_result`) | `control/phase_evidence.py` reuses `start_attempt`/`finish_attempt`/`record_gate_result` verbatim; attempt numbering comes from `next_attempt_no` inside `start_attempt`, so the `uq_step_attempts_run_step_no` UNIQUE retry contract is satisfied by the writer, never by the engine guessing (docstring `control/phase_evidence.py:45-49`). |
| Recorded in the phase loop of the engine (composition root), bound to the candidate | `runtime/workflow_runner.py:3363-3372` — `_emit_phase_evidence` runs ONCE per executed phase, at the loop tail AFTER every gate and AFTER a checkpoint phase's `awaiting` flip, so the recorded status is the phase's FINAL status and the ledger and the control db agree; `candidate_sha = pr.commit_hash or _git_head(wd)`. |
| Best-effort: a control-db failure never fails the phase; a failure is a NAMED warning, never silent | `runtime/workflow_runner.py:967-974` — the recorder call is wrapped; an exception prints `warning: control-db per-phase evidence write failed for phase '<name>' (...)` to stderr and the phase stands. |
| The parent aggregates; child mode (`--only-phase`) stays inert | `scripts/run_workflow.py:564-565` — the composition root binds `make_phase_evidence_recorder(control_db, control_run_id)` and hands it to the engine; `control/phase_evidence.py:107-108` returns `None` when there is no run row; `_control_open_run` (`scripts/run_workflow.py:801-807`) returns `(None, None)` in child mode, so a `--only-phase` sibling structurally cannot record. |
| Debt-2: runtime owns the contract, never imports control | `runtime/phase_evidence.py` (PhaseEvidence value object + `PhaseEvidenceRecorder` protocol, pure data + one protocol) ↔ `control/phase_evidence.py` (the writer); pinned by `tests/test_dependency_direction.py` (green, §3). |

## 2. VERIFY (a)–(e) — proven by the merged tests, run fresh

All three commands ran against this worktree at HEAD `e56dbe6dc`, `-p no:cacheprovider`.

| Point | Test(s) | Result |
|---|---|---|
| (a) synthetic 2-phase spec + fake agent → 2 `step_attempts` rows + the produced `gate_results`, state/tokens/cost populated | `test_engine_records_two_attempt_rows_and_the_gate_results_phases_produced` (real engine + real recorder + real db) and writer-level `test_record_phase_evidence_writes_one_attempt_row_with_all_fields` | pass |
| (b) a FAILED phase records a failed attempt, never skipped | `test_engine_records_a_failed_phase_as_a_failed_attempt` + `test_a_failed_phase_records_a_failed_attempt_never_skipped` | pass |
| (c) a retried phase records attempt_no 1 then 2 (UNIQUE index contract) | `test_a_retried_phase_records_attempt_no_1_then_2` | pass |
| (d) a control-db outage during the phase write does not fail the run; the warning is named | `test_control_db_outage_during_the_phase_write_does_not_fail_the_run` (asserts `ok`, both phases ok, and `"control-db per-phase evidence write failed"` on stderr) + `test_a_run_without_a_control_db_still_exits_cleanly` | pass |
| (e) child mode (`--only-phase`) records nothing | writer `test_make_phase_evidence_recorder_is_inert_without_a_run_row`; composition `test_child_mode_records_no_run_and_injects_no_recorder` and `test_control_open_run_child_mode_never_opens_the_control_db` | pass |

`python3 -m pytest tests/test_phase_evidence.py -q -p no:cacheprovider` → **14 passed**.
`python3 -m pytest tests/test_run_workflow_graph_cli.py -q -p no:cacheprovider` → **20 passed**
(composition-root wiring: parent injection `test_main_injects_a_phase_evidence_recorder_when_a_run_is_recorded`
plus the child-mode inertness tests above).
`python3 -m pytest tests/test_control_db.py tests/test_dependency_direction.py -q -p no:cacheprovider`
→ **81 passed** (the writers the recorder reuses + the Debt-2 tier boundary that keeps `runtime`
free of `control` imports).

## 3. The recorder is LIVE for this run — real rows are accumulating

The e0 preregistration preregistered the proof criterion for `run-5e31f69b4afa`: after the run,
`step_attempts >= 8` and `gate_results > 0` for this run_id. That proof accrues per-phase because
the engine writes each phase's row as the phase ENDS — it does not depend on any phase's commit.
Read from the live control db at `/home/drseuss/ai-finops-framework/experiments/results/control/control.db`
at `2026-09-02T13:00:20Z` (this phase's start boundary), read-only:

```
runs:           [('run-5e31f69b4afa', 'control_db_evidence', 'running')]
step_attempts:  [('e0_pin_spec', 1, 'ok', 109832, 0.0280392448,
                  '2026-09-02T12:48:46.950583Z', '2026-09-02T12:55:57.448883Z')]
gate_results:   0
control_epoch:  11
run_transitions: [('run-5e31f69b4afa', None, 'running')]
```

The e0 phase — the phase that ran immediately before this one, on the SAME launched engine —
recorded a fully-populated `step_attempts` row (step `e0_pin_spec`, attempt 1, state `ok`,
tokens 109832, cost `$0.0280`, start/end stamps spanning the phase). `gate_results` is 0 for the
run so far for the correct reason: e0 fired no gate (a clean phase produces no fabricated row —
`runtime/phase_evidence.py:30-38`). This is the exact behavior the first evidence run
(`run-ba8a4deda548`, `step_attempts: 0 / gate_results: 0` for 8 executed phases) could not
produce, because its orchestrator launched pre-e1 and never reloaded its modules. This run is
the first post-merge run the e6 adversarial review of the original run predicted would "populate
the tables live." At this phase's end the engine will append e1's row the same way.

## 4. Scope fence

- **Changed:** `docs/reviews/control_db_evidence_e1_verify.md` (this verification record) — one
  file. No source, no tests, no spec, no workflow YAML were modified.
- **Not done, deliberately:** no re-implementation of the write side (it is the merged launch
  state; editing it would undermine the run's premise), no e2 drain/lifecycle work, no e4 packet
  work, no e3 hermeticity work, no drain/queue/sweep or checkpoint interactions.

## 5. Verdict

**PASS.** The e1 deliverable — the per-phase evidence write side + its tests — is present in the
launched code, matches the SHAPE point for point, is wired end-to-end at the composition root
and called in the engine's phase loop for every outcome, and is proven in BOTH directions by the
merged unit tests (writer and engine seam; 115 tests green across the three commands above). The
live control db confirms the recorder is firing for this run: `run-5e31f69b4afa` already holds a
real, fully-populated `step_attempts` row for the phase that preceded this one. The preregistered
run-level criterion (`step_attempts >= 8`, `gate_results > 0` for this run_id) is on track to be
satisfied by the run's own engine writes as phases e1–e7 complete.
