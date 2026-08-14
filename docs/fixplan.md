# Control Room Review — Triage & Fix Plan

Scope: act on `docs/review/code_review.md` (C1, M1–M4, N1–N6) and
`docs/review/architecture_review.md` (recs 1–5). The code has moved since the
review: `admin/server.py` grew from ~367 to 622 lines (the `design_sessions`
feature merged in). Every citation below is re-located to the current file:line;
the findings are structural, so the fixes are identical even where line numbers
have shifted.

Baseline: the four test files that assert on the affected code
(`tests/test_admin_server.py`, `tests/test_admin_frontend.py`,
`tests/test_admin_design_sessions.py`, `tests/test_live.py`) pass as-is:
**31 passed, 0 failed**.

---

## 1. Findings re-located + concrete fix per finding

### C1 — unauthenticated enqueue + `0.0.0.0` bind — ALREADY FIXED (verify only)

- Old citation: `admin/server.py:340-345`, `admin/server.py:365-367`.
- Now: the missing-action guard is `admin/server.py:463-483` (explicit
  `if not isinstance(body, dict) or "action" not in body: return ..., 400` at
  `466-468`), and the bind defaults to loopback at `admin/server.py:618-622`
  (`host = os.environ.get("FINOPS_HOST", "127.0.0.1")`, wider bind is explicit
  opt-in).
- Action: none. Confirm only. No test asserts on the old default-host or
  default-action behavior, so nothing to reconcile.

### M1 — `/api/matrix` issues one unpipelined `LRANGE` per cell

- Now: `_retained_telemetry` at `admin/server.py:274-335`; the per-cell
  `redis_client.lrange(f"{EVENT_LOG_PREFIX}{cell_id}", 0, -1)` is `admin/server.py:291`,
  inside the `for cell_id in cell_ids` loop at `289`.
- Concrete fix: batch the reads in one round trip.

  ```python
  # admin/server.py — _retained_telemetry
  keys = [f"{EVENT_LOG_PREFIX}{cid}" for cid in cell_ids]
  try:
      pipe = redis_client.pipeline(transaction=False)
      for key in keys:
          pipe.lrange(key, 0, -1)
      histories = pipe.execute()
  except Exception:
      # A connection-level failure marks telemetry incomplete but must not
      # erase the legacy matrix response (same contract as today).
      histories = [None] * len(cell_ids)

  for cell_id, history in zip(cell_ids, histories):
      if history is None:
          available = False
          history = []
      ...
  ```

  Design notes:
  - `transaction=False` keeps the call a single network round trip while still
    returning per-key results, so a per-cell command error (`ResponseError`) can
    be tolerated the way the current per-cell `try/except` is (set
    `available = False`, treat that cell as empty). A whole-connection failure
    raises at `execute()` and is caught once, which is strictly cheaper than the
    current per-cell failure handling.
  - Preserve the exact response shape: `available`, `provenance`,
    `partial`, `reported_cost`, `cells` — the additive contract is untouched.
- Test impact: `FakeRedis` in `tests/test_admin_server.py:34-60` must gain a
  `pipeline()` that records keys in the same order and returns logs per key, so
  the existing assertion
  `redis.requested_logs == ["events_log:alpha", "events_log:beta", "events_log:odd"]`
  (`test_admin_server.py:111`) still holds.

### M2 — `history_capped` computed but never surfaced

- Now: per-cell `"history_capped": len(history) >= EVENT_LOG_MAX` is
  `admin/server.py:322` (with `history_size` at `321`). `grep history_capped`
  over `admin/static/*` returns nothing — the flag is never read. The
  "Reported spend" rail is `admin/static/index.html:22-26`
  (`#reported-spend`, `#spend-provenance` "RETAINED WINDOW"), rendered by
  `renderRail` at `admin/static/app.js:131-155`.
- Concrete fix: thread a fleet-level flag through, additive-only.
  1. Backend: in `_retained_telemetry` track
     `capped = capped or (len(history) >= EVENT_LOG_MAX)` in the loop and add a
     top-level `"history_capped": capped` to the returned dict
     (`admin/server.py:326-335`). This mirrors the existing top-level
     `available`/`reported_cost` pattern.
  2. Frontend: in `renderRail` (`app.js:131-155`), after computing totals, read
     `state.telemetry.history_capped`. When true:
     - append `"±"` to the spend value (`#reported-spend`) and add a footnote to
       its `aria-label` ("…reported spend, retained window truncated at 500
       entries"),
     - set `#spend-provenance` text to `"RETAINED WINDOW · TRUNCATED"`.
     No HTML change is required — the provenance span already exists.
- Design note: this keeps the fix purely additive on the API (a new boolean
  field) and label-only on the client; it does not change any cost aggregation.

### M3 — publish-before-persist ordering in `src/instrument/live.py`

- Now: `publish_event` body at `src/instrument/live.py:98-101`:

  ```python
  try:
      self._r.publish(channel, payload)
      self._r.lpush(log_key, payload)
      self._r.ltrim(log_key, 0, EVENT_LOG_MAX - 1)
  ```

- Concrete fix: reorder to persist-then-publish (review option **a**, the root
  cause — preferred over the client-side identity-verification option **b**):

  ```python
  try:
      self._r.lpush(log_key, payload)
      self._r.ltrim(log_key, 0, EVENT_LOG_MAX - 1)
      self._r.publish(channel, payload)
  ```

  This makes "delivered live" imply "already retained", closing the silent
  non-self-healing undercount: the client's `pruneReconciledSamples` timing
  heuristic (`app.js:811-821`) becomes safe because a poll that started after a
  publish is guaranteed to observe the entry (or it was evicted by the shared
  500-slot window, which M2 now labels). The reverse case — `lpush` succeeds but
  `publish` fails — degrades to a bounded 5s poll pickup, which is
  self-healing, unlike the current permanent loss.
- Test impact: `tests/test_live.py:48-74` record publish and log calls
  independently and only assert the channel names and newest-first log order, so
  the reorder is test-compatible with no assertion change.

### M4 — Werkzeug threaded dev server, no connection cap — DOCUMENT, don't over-engineer

- Now: `admin/server.py:618-622` (`app.run(host=host, port=port, threaded=True)`).
- Concrete fix (per triage: it is a local operator tool, so no ASGI migration):
  1. Extend the module docstring (`admin/server.py:1-15`) with a note that the
     built-in server is single-process/threaded and not production-grade, plus a
     gunicorn example for multi-operator use:

     ```text
     gunicorn --worker-class gthread --threads 4 --workers 1 \
       --bind 127.0.0.1:8000 'admin.server:app'
     ```

  2. Do not change the `app.run(...)` call, add no connection cap, and keep the
     `python3 admin/server.py` direct-run entry point working (a hard
     requirement in `docs/scope.md`).
- Design note: the two SSE endpoints (`api_status`, `api_events`) each hold a
  thread + pubsub connection per tab; the plan acknowledges this as an accepted
  operator-tool limitation, documented rather than solved.

### N5 — zero return-type annotations in `admin/server.py`

- Now: confirmed — no `def` in `admin/server.py` carries a `->` annotation
  (all 19 functions, including `_step_sample` `:208`, `_retained_telemetry`
  `:274`, and every `@app` route handler).
- Concrete fix: add return types to match `live.py`'s fully-hinted style, at
  minimum:
  - `_reported_number(...) -> float | None`, `_event_timestamp(...) -> str | int | float | None`,
    `_identity_number(...) -> str`, `_step_sample(...) -> dict[str, Any] | None`,
    `_retained_telemetry(...) -> dict[str, Any]`, `_sse(...) -> Response`,
    `_design_error(...) -> tuple[Response, int]`,
    `_design_mutation_body(...) -> tuple[dict | None, tuple[Response, int] | None]`,
    `_idempotent_design_response(...) -> Response`.
  - Route handlers: `api_matrix -> Response`, `api_status -> Response`,
    `api_events -> Response`, `api_routing -> Response`,
    `api_experiments -> Response`, the four design-session handlers `-> Response`,
    `index -> Response`.
  - `_redis() -> redis.Redis`, `_design_sessions() -> DesignSessionManager`.
  The file already imports `from __future__ import annotations`
  (`admin/server.py:17`), so string-style forward references are unnecessary.
- Test impact: none (annotations are not asserted by any test).

### N6 — lines exceeding the 100-char convention

- Now: the stale citations (`61, 200, 201, 335`) no longer apply. Current
  offenders (re-measured): `admin/server.py:76`, `134`, `137`, `174`, `313`,
  `314`, `458`, `504`, `535`, `539` (longest is `539` at 121 chars).
- Concrete fix: wrap these mechanically (split long call chains /
  `jsonify(...)` argument lists onto continuation lines). No logic change.
- Test impact: none.

---

## 2. Order

1. **M3** (`src/instrument/live.py` reorder) — smallest change, root cause,
   self-contained, and makes M2's honesty guarantee meaningful (a live event is
   always in the retained window).
2. **M1** (pipeline `_retained_telemetry`) — pure perf, touches one function +
   one test fixture; do early so the pipeline-friendly code is in place before
   M2 touches the same function.
3. **M2** (surface `history_capped`) — backend aggregate + frontend label;
   builds on the now-stable retained-window semantics.
4. **M4** (document dev-server limitation + gunicorn example) — docstring only.
5. **N5** (return-type annotations) — mechanical style, after the structural
   edits so annotations match the final signatures.
6. **N6** (wrap long lines) — mechanical, last so it isn't re-broken by prior
   edits.

Rationale for this sequence: correctness (M3) before performance (M1) before
honesty/UX (M2); docs (M4) and style (N5/N6) trail because they must reflect the
final code, not an intermediate state.

---

## 3. MINORs to skip (and why)

- **N1 — dead `identity` computation: skip (defer).** It is not truly trivial:
  removing it requires coordinated deletion across `_step_sample`
  (`admin/server.py:252-261`), `_identity_number` (`admin/server.py:201-205`),
  `extractSample` (`admin/static/control-room-core.js:101-112`),
  `identityNumber` (`control-room-core.js:54-58`), and the one read site
  `app.js:504` (`state.burnSamples.push({ identity: sample.identity, ... })`).
  It spans two runtimes held in lockstep with zero behavioral payoff, and it
  remains the latent hook for M3's option **b** (identity-verified
  reconcile) should the reorder ever prove insufficient. Deleting it now is
  risk without benefit; the field is additive (extra sample key) and harms no
  contract. Defer until a future identity-based reconcile lands or dies.
- **N2 — redundant initial `beginReplay()`: skip.** It sits in the
  stream-reconnect lifecycle (`app.js:674` vs `app.js:684`); removing it risks
  a subtle reconnect/`onopen` race for zero behavioral gain. Better left as a
  comment-only clarification, and even that is not worth touching the
  connection state machine in this pass.
- **N3 — ghost cells linger up to two poll cycles: skip.** Bounded, self-healing
  staleness (`app.js:824-840`) that is already presumed intentional by the
  in-code comment. Documenting it is a one-line docstring addition with no
  test coverage to protect; changing it risks the status-override reconciliation
  that the 25 admin tests indirectly lean on. Defer.
- **N4 — fixed 250ms replay/live race-dedup window: skip.** A hard-coded
  delivery-latency assumption (`app.js:15`, `544-554`) with no telemetry and no
  fallback. Hardening it (e.g. checking `state.eventLedgerCounts`) touches the
  single-event dedup path that the review itself calls "already correct" — the
  marginal value is low and the regression risk on replay dedup is high. Not
  worth it in this pass.

---

## 4. Test impact + verification

- Behavior-preserving for the existing admin contract: M1/M2 are additive on
  the response and M3 changes no asserted ordering; N5/N6 are annotation/format
  only. The only test fixture touched is `FakeRedis` gaining a `pipeline()`
  method for M1 (assertions unchanged).
- Verification commands:
  ```bash
  python3 -m pytest tests/test_admin_server.py tests/test_admin_frontend.py \
       tests/test_admin_design_sessions.py tests/test_live.py -q
  ```
- Do not touch `firebase/public/data.js` or `admin/static/style.css`. Preserve
  the observational/no-write-path property and the additive-only API contract
  (`docs/scope.md` §4).
