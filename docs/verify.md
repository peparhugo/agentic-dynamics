# Control Room Review Findings — Verification

Scope: fable-5's Control Room review (`docs/review/code_review.md`, `docs/review/architecture_review.md`),
applied per `docs/fixplan.md`. This pass covers the four MAJOR findings (M1–M4) plus the
cheap safe MINORs (N5, N6); C1 was already fixed and is verify-only.

## Verdict

**PASS — all required checks pass and M1–M4 plus N5/N6 are implemented and covered by tests.**

## Checklist

| Check | Result |
|---|---|
| `python3 -m pytest tests/test_admin_server.py tests/test_admin_frontend.py tests/test_admin_design_sessions.py -q` | **PASS — 29 passed** |
| `python3 -m pytest tests/test_live.py -q` | **PASS — 7 passed** |
| M1 — Redis pipeline for `/api/matrix` | **PASS — implemented** |
| M2 — `history_capped` surfaced honestly | **PASS — implemented** |
| M3 — persist-before-publish in `live.py` | **PASS — implemented** |
| M4 — dev-server limitation documented | **PASS — documented** |
| N5 — return-type annotations in `admin/server.py` | **PASS — all module-level defs annotated** |
| N6 — lines ≤ 100 chars in `admin/server.py` | **PASS — zero offenders** |

## Findings verified

### M1 — `/api/matrix` reads all cell logs in one pipeline round trip

`_retained_telemetry` (`admin/server.py:300-380`) now builds the full key list, issues all
`lrange` reads through `redis_client.pipeline(transaction=False)`, and executes once
(`admin/server.py:319-328`). A whole-connection failure degrades to `histories = [None] * N`
and marks `available = False` without dropping the legacy matrix response. A per-cell `None`
still sets `available = False` for that cell only, preserving the pre-existing contract.
`FakeRedis.pipeline()` + `FakePipeline` (`tests/test_admin_server.py:62-81`) record key order so
the existing `requested_logs` assertion still holds; `test_matrix_pipeline_failure_keeps_telemetry_additive`
covers the connection-failure path.

### M2 — `history_capped` is surfaced to the operator, not just computed

- Backend: `_retained_telemetry` tracks a fleet-level `capped = capped or len(history) >= EVENT_LOG_MAX`
  (`admin/server.py:334`) and returns top-level `"history_capped"` (`admin/server.py:378`); the per-cell
  `history_capped` field was already present (`admin/server.py:366`).
- Frontend: `renderRail` (`admin/static/app.js:131-157`) reads `state.telemetry.history_capped`, appends
  `±` to the spend value, extends the `aria-label` with "truncated at 500 entries", and sets
  `#spend-provenance` to `"RETAINED WINDOW · TRUNCATED"` when capped.
- Tests: `test_matrix_flags_history_capped_when_window_full`, `test_matrix_history_capped_false_when_window_open`,
  and `test_spend_rail_surfaces_retained_window_truncation`.

### M3 — `live.py` persists before it publishes

`LivePublisher.publish_event` (`src/instrument/live.py:98-106`) is reordered to
`lpush` → `ltrim` → `publish`, so "delivered live" implies "already retained". A poll that starts
after a publish is now guaranteed to observe the entry (or it was evicted from the bounded window,
which M2 labels). The reverse failure mode (lpush succeeds, publish fails) degrades to a bounded
5s poll pickup instead of a permanent, non-self-healing loss. Locked in by
`test_publish_event_persists_before_publish` (`tests/test_live.py:77-101`), which asserts the exact
`["lpush", "ltrim", "publish"]` call order.

### M4 — dev-server limitation documented (not over-engineered)

The `admin/server.py` module docstring now carries a "Deployment note" (`admin/server.py:16-23`)
explaining that `app.run(threaded=True)` is Flask's single-process development server with no
connection cap (each SSE client holds one thread + one Redis Pub/Sub subscription), plus a
threaded-gunicorn example for multi-operator use. The `app.run(...)` call and the
`python3 admin/server.py` direct-run entry point are unchanged.

### N5 — return-type annotations

Every module-level `def` in `admin/server.py` now carries a `->` return annotation (route handlers,
`_step_sample` → `dict[str, Any] | None`, `_retained_telemetry` → `dict[str, Any]`,
`_reported_number` → `float | None`, etc.), matching `src/instrument/live.py`'s fully-hinted style.
The five remaining unannotated `def`s are nested closures/generators (`gen`, `create`, `save`, `run`),
which are not part of the review's citation surface.

### N6 — line-length convention

`admin/server.py` has zero lines exceeding the 100-character cap (`ruff` line-length is 100). The
previously cited long lines (including the `jsonify(...)` argument lists and list comprehensions) are
wrapped onto continuation lines with no logic change.

## What changed (summary)

| File | Change |
|---|---|
| `src/instrument/live.py` | M3 — `publish_event` reordered to lpush → ltrim → publish (persist-before-publish). |
| `admin/server.py` | M1 — pipelined `_retained_telemetry`; M2 — fleet-level `history_capped`; M4 — deployment-note docstring; N5 — return annotations; N6 — line wraps. |
| `admin/static/app.js` | M2 — `renderRail` surfaces `history_capped` (`±`, truncated provenance label, aria-label). |
| `tests/test_live.py` | `test_publish_event_persists_before_publish` (M3 ordering). |
| `tests/test_admin_server.py` | `FakePipeline`/`FakeRedis.pipeline`; pipeline-failure and history-capped tests. |
| `tests/test_admin_frontend.py` | `test_spend_rail_surfaces_retained_window_truncation` (M2 surfacing). |

## MINORs skipped (per fixplan, no change)

N1 (dead `identity`), N2 (redundant `beginReplay`), N3 (ghost-cell staleness), N4 (250ms dedup
window) — deferred as documented in `docs/fixplan.md` §3: each is either bounded/self-healing,
latent infrastructure for a future identity-based reconcile, or a high-regression-risk touch on an
already-correct dedup path. None affects this pass.

## Note on full-suite collection

`python3 -m pytest` over the whole repo attempts to collect generated `test_*.py` artifacts under
`experiments/results/reports/` (import errors) — a pre-existing repository state unrelated to this
change. The scoped test commands above (the ones this phase requires) all pass. The CI subset
(`.github/workflows/pytest.yml`) does not collect from `experiments/results/reports/`.
