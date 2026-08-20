---
status: accepted
---
# Workflow Phase Badge — Verification

**Goal:** publish the live workflow phase (name / index / total) from `workflow_runner` and
render it as a badge on workflow cells in the Control Room.

**Method:** extend `tests/test_workflow_runner.py` (publish-at-start + resume-index), extend
`tests/test_admin_server.py` (matrix surfaces the phase keyed by cell id), add a structural
frontend check to `tests/test_admin_frontend.py` (the `.phase-badge` render path), plus the
`LivePublisher.set_phase` hash write in `tests/test_live.py`. Then run the targeted files.

---

## Commands run

```bash
python3 -m pytest tests/test_workflow_runner.py tests/test_admin_server.py \
    tests/test_admin_frontend.py tests/test_live.py -v
```

Result: **49 passed** in 8.05s (Python 3.10.12, pytest 8.4.2).

```bash
python3 -m pytest tests/test_step_routing.py tests/test_admin_supervisor.py \
    tests/test_claude_agents_supervisor.py tests/test_ledger_fields.py -q
```

Result: **48 passed** in 0.37s (regression guard around the `FINOPS_CELL_ID` adoption change).

```bash
python3 -m py_compile src/instrument/live.py src/instrument/workflow_runner.py admin/server.py
```

Result: **OK** (no syntax errors).

---

## Check results

| # | Check | Asserted by | Result |
|---|-------|-------------|--------|
| 1 | Phase published at **phase start** (before the agent runs), for every phase incl. `test` phases | `test_run_workflow_publishes_phase_before_agent_runs` | **PASS** |
| 2 | Phase payload is `{name, index, total}`; names `[scope, ux_design, implement, verify]`, indexes `[1,2,3,4]`, total `4` | `test_run_workflow_publishes_phase_per_phase` | **PASS** |
| 3 | `resume` keeps the **1-based absolute index** (re-run publishes `implement=3`, `verify=4`, not re-based `1,2`) | `test_run_workflow_resume_publishes_original_phase_index` | **PASS** |
| 4 | `LivePublisher.set_phase` writes `story_phase[cell_id] = {name,index,total}` JSON | `test_set_phase_writes_phase_hash` | **PASS** |
| 5 | `/api/matrix` surfaces `phases` keyed by the same cell id as `cells`; malformed/no-name entries dropped | `test_matrix_surfaces_live_workflow_phases` | **PASS** |
| 6 | Fleet cards render a `.phase-badge` from `state.phases` fed by `data.phases` (source-level, no JS runtime) | `test_workflow_phase_badge_rendered_on_fleet_cards` | **PASS** |
| 7 | No regression to phase **commit + ledger** behavior | `test_run_workflow_commits_per_phase`, `test_run_workflow_excludes_instrument_from_commit`, `test_run_workflow_phases_in_order`, `test_run_workflow_fails_fast` | **PASS** |
| 8 | No regression to matrix legacy fields + retained telemetry | `test_matrix_preserves_legacy_fields_and_adds_retained_telemetry` | **PASS** |
| 9 | No regression to routing / supervisor / ledger-field suites (the `FINOPS_CELL_ID` adoption touched `run_workflow`) | `test_step_routing.py`, `test_admin_supervisor.py`, `test_claude_agents_supervisor.py`, `test_ledger_fields.py` | **PASS** |

All checks **PASS**. No check failed.

---

## What was added (test side)

- `tests/test_workflow_runner.py`
  - `test_run_workflow_publishes_phase_per_phase` — every phase emits `{name, index, total}`.
  - `test_run_workflow_publishes_phase_before_agent_runs` — phase is published *before* the agent
    is invoked, and a `test` phase emits a phase start with no agent call.
  - `test_run_workflow_resume_publishes_original_phase_index` — resume preserves absolute index.
- `tests/test_admin_server.py`
  - `test_matrix_surfaces_live_workflow_phases` — matrix returns `phases` keyed by cell id;
    asserts the running cell carries `4/7 rerun_contaminated`; malformed/no-name entries dropped.
  - `FakeRedis.hgetall` extended for `story_phase`.
- `tests/test_admin_frontend.py`
  - `test_workflow_phase_badge_rendered_on_fleet_cards` — `state.phases` / `data.phases` /
    `element("span", "phase-badge")` in `app.js` and `.phase-badge` in `style.css`.
- `tests/test_live.py`
  - `test_set_phase_writes_phase_hash` — `story_phase` hash write keyed by cell id.

## Coverage gap note (not a failure)

There is no JS runtime in this repo (`tests/test_admin_frontend.py` is source-structural by
design), so the badge *pixel-level* render is verified at the source invariant level rather
than in a browser. The data path from `workflow_runner` → `story_phase` → `/api/matrix` →
`app.js` is fully covered end-to-end in Python tests.
