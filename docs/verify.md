# Supervisor Surface Verification

## Verdict

**PASS.** The Control Room exposes supervisor assessments for human review and
provides explicit steer and interrupt controls. The supervisor itself only flags;
it does not act on a session.

## Checks

| Check | Result | Evidence |
|---|---|---|
| Required frontend/backend suite | **PASS** | `python3 -m pytest tests/test_admin_server.py tests/test_admin_frontend.py tests/test_admin_design_sessions.py -q` completed with **30 passed, 0 failed**. |
| Additional supervisor tests | **PASS** | `python3 -m pytest tests/test_admin_supervisor.py tests/test_supervise.py -q` completed with **7 passed, 0 failed**. |
| Maintained project suite | **PASS** | `python3 -m pytest tests/ -q` completed with **451 passed, 0 failed** and 6 warnings. |
| Needs Attention rail shows flagged sessions | **PASS** | `renderSupervisorFlags` renders normalized status, the session title as the compact summary, `why` as the reason, and model/flag/activity metadata (`admin/static/app.js:357-405`). The frontend contract checks the rail and human-action controls (`tests/test_admin_frontend.py:142-164`). |
| Selecting a flag loads its stream in the terminal | **PASS** | `selectSupervisorFlag` accepts only an exact mapped `review.cell_id`, closes the prior stream, resets terminal state, selects the mapped cell, and reconnects the sole stream (`admin/static/app.js:954-1011`). `/api/events/<cell_id>` replays retained events and then streams live events (`admin/server.py:644-684`). An unmapped flag is shown but deliberately cannot guess or replace a terminal stream. |
| `GET /api/flags` returns supervisor flags | **PASS** | `/api/flags` returns the newest bounded, normalized assessments loaded from the `supervisor_flags` Redis list, with a durable JSONL fallback (`admin/server.py:632-641`). Tests cover malformed-record rejection, newest-first deduplication, mapping enrichment, and fallback (`tests/test_admin_supervisor.py:94-138`). |
| Steer uses the mocked OpenCode client | **PASS** | The operator form posts the selected session, mapped cell, and prompt (`admin/static/app.js:1331-1366`). The server reauthorizes the mapping and calls `send_input(..., delivery="steer")` (`admin/server.py:799-823`). The mocked-client test verifies the exact call (`tests/test_admin_supervisor.py:141-175`). |
| Interrupt uses the mocked OpenCode client and requires confirmation | **PASS** | Opening the one-way door performs no request; submission requires the exact typed phrase `INTERRUPT <session_id>` (`admin/static/app.js:1368-1419`). The server independently rejects any other confirmation before calling `interrupt` (`admin/server.py:826-848`). The mocked-client test proves a bad confirmation returns 400 and the exact confirmation produces one interrupt (`tests/test_admin_supervisor.py:141-185`). |
| No autonomous steering | **PASS** | `scripts/supervise.py` declares flag-only behavior and forbids steering or interruption (`scripts/supervise.py:1-10,48-57`). Its only prompt calls target the monitor with `delivery="queue"` (`scripts/supervise.py:82-100,257-286`). A repository search found the sole production `delivery="steer"` call in the human-triggered `/api/flags/<session_id>/steer` route. |

## Summary

The supervisor persists assessments with status, title/summary, model, and reason;
the Control Room presents them in the Needs Attention rail. A human can select an
exactly mapped session to reuse the single terminal stream, submit a steer prompt,
or cross a separately confirmed interrupt boundary. Mapping revalidation and
idempotency prevent stale or repeated controls from reaching OpenCode.

An unscoped `python3 -m pytest -q` was also attempted. Pytest recursively collected
generated third-party experiment code under `experiments/results/reports/` and
stopped with 688 collection errors before running tests. This is an existing test
discovery limitation, not a supervisor failure; the repository's maintained
`tests/` suite passes in full as reported above.
