# Plan — Item 4: land the missing regression check for the stale next-action state

*Execute phase follows this file. Deviations go in `notes/deviations.md`; the posterior diffs
against `notes/world_model.md` and this plan.*

## 0. Decision (from the world model)

The c15 stale-next-action gap is **already closed** for the one confirmed AIO action that has a
durable recording path — a workflow submit (`scripts/fleet/fleet_manager.py:853`,
`_record_submission_in_task`, commit `246490028`, an ancestor of HEAD). The recording REPLACES
`next_action` with a version-guarded `[auto] submitted job …` string, and the capsule renders
the binding's `next_action` with precedence over predecessor threads
(`scripts/session_open.py:393-400`).

Therefore this task lands the **missing regression check**, not a source change. The check must
pin the carrier-level property the c15 finding names: *a completed instruction can never remain
the actionable next action after its confirmed action happened.* No new memory format, no
`handoff` object, no generalized prose compiler.

Fallback (only if a test fails): apply the smallest existing-machinery fix that makes it pass,
and record the deviation. Do not invent a new record family.

## 1. Files to touch

| file | change |
|---|---|
| `tests/test_session_binding.py` | ADD two tests: (a) replace-not-append for a non-empty prior `next_action`; (b) capsule-level regression that a completed `next_action` is superseded by a progress write and cannot appear as the capsule's next action. |
| `tests/test_fleet_manager.py` | ADD one end-to-end regression: seed the exact c15 stale instruction, run the REAL `fleet_manager submit` (confirmed action), then compose the capsule and assert the stale instruction is gone and the `[auto]` job record is the next action. |
| `notes/deviations.md` | CREATE only if a deviation occurs (the execute prompt requires it when reality differs). |

Explicitly NOT touched: `scripts/session_open.py`, `src/agentic_dynamics/knowledge/session_ingestion.py`,
`scripts/fleet/fleet_manager.py`, `.opencode/plugins/aio-context.ts`, `docs/reviews/*` — unless the
fallback is triggered.

## 2. Tests to create

### 2.1 `tests/test_session_binding.py` (pure unit; no Redis, no subprocess)

1. `test_a_progress_write_replaces_a_completed_next_action` — in `TestVersionedContext`:
   - write a binding with `next_action="activate PR #77 then call run_workflow"`;
   - `si.update_binding_context("ses_test_1", context={"next_action": "observe job abc123"},
     expected_version=1, artifact_dir=tmp_path, connect_fn=_FakeRedis)`;
   - assert the read-back `next_action == "observe job abc123"` (replaced, not concatenated);
   - assert the superseded text is retained in `context_history[0]["next_action"]`
     (nothing lost — the audit trail is the history, not the live carrier);
   - assert `context_version == 2` and the authorization id/epoch are unchanged (progress-only,
     per round-9).
   - Rationale: today's tests only exercise a non-empty `next_action` on an EMPTY prior value
     (`tests/test_session_binding.py:491-520`), so replace semantics against a stale non-empty
     value are unproven.

2. `test_the_capsule_cannot_show_a_completed_next_action` — in `TestConstraintPreservation`
   (it already has the `_capsule` helper and `compose_capsule`):
   - write the binding with the c15 stale `next_action`;
   - perform the progress write that records the confirmed action;
   - compose the capsule from the read-back binding (packet/budget stubbed as in
     `tests/test_session_binding.py:590-598`);
   - assert `"activate PR #77" not in capsule["next_action"]["text"]` AND not in `capsule["text"]`;
   - assert `capsule["next_action"]["source"] == "binding"` and the new record is present.
   - Rationale: this is c15 §4.6 rendered against the machinery that actually exists.

### 2.2 `tests/test_fleet_manager.py` (the real submit path)

3. `test_a_submission_supersedes_a_completed_next_action_in_the_capsule` — reuse the existing
   harness (`_binding_store`, `_fleet_manager`, `_FakeRedis`, and either the light `fm.main`
   argv at `tests/test_fleet_manager.py:1034-1041` or the full `_submit_fixture`/`_aio_argv`
   pair at `:1110-1148`):
   - after `_binding_store`, issue an `si.update_binding_context` that sets the c15 stale
     `next_action` (the binding was created empty by `_binding_store`, so version 1→2);
   - run the real submit with `--binding-context-version 2` and `--retry-safe --json`;
   - assert `payload["task_note"] == ""` (recorded cleanly) and the `[auto]`/`job_id` in the
     read-back `next_action`;
   - compose the capsule (load `scripts/session_open.py` exactly as
     `tests/test_session_binding.py:45-49` does, or import `compose_capsule` via the same
     `importlib` seam) with the read-back binding and stubbed packet/budget;
   - assert the capsule text contains the new `job_id` and does NOT contain `"activate PR #77"`.
   - Rationale: proves the *path* that the AIO actually uses records, not just that the writer
     can; closes the loop from action → binding → carrier.

## 3. Local verification commands

```bash
# the two touched test modules (and the neighbouring binding/exec suites)
python3 -m pytest tests/test_session_binding.py tests/test_fleet_manager.py \
                 tests/test_spawn_wrapper.py -q -p no:cacheprovider

# lint the touched files (whole-surface ruff is the repo rule)
ruff check tests/test_session_binding.py tests/test_fleet_manager.py

# the fast smoke, to confirm no fast-marked guard broke
python3 -m pytest tests/ -m fast -q -p no:cacheprovider
```

If a fast-eligible module already carries the `fast` marker selectively, follow the existing
marking convention in the module; do not mark a test `fast` if it spins up the real spec fixture
(the parallel-safety audit in `tests/test_fast_path_gate.py` will reject it).

## 4. Acceptance criteria

1. The three named tests exist, are deterministic, and pass.
2. The capsule-level tests assert the completed instruction is absent from BOTH
   `capsule["next_action"]["text"]` and the rendered `capsule["text"]` — the carrier, not just
   the JSON.
3. `tests/test_session_binding.py` and `tests/test_fleet_manager.py` and
   `tests/test_spawn_wrapper.py` are green; `ruff check` on the touched files is clean.
4. No source file is modified unless the fallback fires; if it fires, the change is additive and
   uses `update_binding_context` only, and `notes/deviations.md` names the failing test, the
   observed behavior, and the minimal change.
5. `notes/deviations.md` exists and records any delta between this plan and what was done.

## 5. Risks and deviations to watch

- **Fixture heaviness / non-determinism.** The full `_submit_fixture` builds a real git repo and
  copies `workflows/repository/fleet_job_submission.yaml`; prefer the lighter `fm.main` argv
  (`tests/test_fleet_manager.py:1034-1041`) if it suffices, to keep the test fast and hermetic.
  If the light path cannot satisfy the submit validator, fall back to `_submit_fixture`.
- **Import seam for `compose_capsule`.** `tests/test_session_binding.py` loads `session_open.py`
  by path via `importlib` (`:45-49`) because the module lives under `scripts/`, not the package.
  Reuse that helper; do not add a new import mechanism.
- **Over-claiming scope.** The tests must cover the submit path only. Non-submit confirmed
  actions (e.g. approvals) have no binding address today (see world model §4.2). Do NOT add a
  test that implies coverage there, and do NOT extend `approve_workflow.py` — that is out of the
  bounded ask.
- **The covered path may reveal a real gap.** If the end-to-end capsule test fails because the
  capsule is served from a 30 s TTL cache (`.opencode/plugins/aio-context.ts:86`) or because the
  recording did not run, STOP and record the deviation rather than widening the change.
- **KB read degradation in the worktree.** `experiments/results/registry_index.jsonl` is absent
  in this worktree, so `scripts/kb_read.py --contains` raises `FileNotFoundError`; use the
  canonical checkout for KB probes, and note the degradation rather than mistaking it for an
  empty corpus.

## 6. Out of scope (explicitly)

- The c15 `handoff` object / any new binding field or record family.
- A generalized prose compiler or a new governance framework (controller direction,
  `aio_arc_findings_and_results.md:204-205`).
- `work_unit` backfill, monitor pointers, corrections arrays, lineage beyond one hop — the other
  c15 categories; this item is the next-action state only.
- The in-process (`orchestrator=false`) run mode, which by the project rules is not the fleet
  path and does not record.
