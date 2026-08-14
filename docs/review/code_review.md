# Control Room code review

Scope: `admin/server.py` (Flask + SSE backend, 367 lines), `admin/static/app.js`
(browser controller, 901 lines), `admin/static/control-room-core.js` (pure data
helpers, 277 lines), `admin/static/style.css` (996 lines), `admin/static/index.html`.
Supporting modules read for grounding: `src/instrument/live.py` (SSE publisher),
`src/instrument/routing.py` (routing board data), `conventions/python.yaml`,
`tests/test_admin_server.py`, `tests/test_admin_frontend.py`.

All 9 existing tests in `tests/test_admin_server.py` and `tests/test_admin_frontend.py`
pass as-is (`python3 -m pytest tests/test_admin_server.py tests/test_admin_frontend.py -q`
→ `9 passed`). They cover matrix aggregation, SSE replay ordering, and DOM/source
invariants well, but none of them exercise the issues below (auth, Redis fan-out,
publish/lpush ordering, or the unused `history_capped`/`identity` signals).

---

## CRITICAL

### C1 — Unauthenticated `/api/experiments` defaults to a real-money "enqueue" on any malformed/empty POST, and the server listens on `0.0.0.0`

`admin/server.py:340-345`:

```python
@app.post("/api/experiments")
def api_experiments():
    body = request.get_json(silent=True) or {}
    action = body.get("action", "enqueue")
    if action not in ("enqueue", "clear"):
        return jsonify({"error": f"unknown action {action!r}"}), 400
```

`request.get_json(silent=True)` returns `None` for any POST that isn't
`application/json` (including a plain HTML `<form method="post">` submission,
which browsers send as `application/x-www-form-urlencoded` without a CORS
preflight). `body` then becomes `{}`, and `action` defaults to `"enqueue"` —
the same action the frontend itself warns is costly:

`admin/static/app.js:883-886`:
```js
$("#enqueue-button").addEventListener("click", () => {
  const warning = "This enqueues the full experiment matrix (~30 cells) on the default model and will incur real cost. Continue?"
  if (window.confirm(warning)) runQueueAction("enqueue")
})
```

That `confirm()` dialog is a client-side UX nicety only — it provides no
protection at all against a direct request. There is no CSRF token, no
Origin/Referer check, and no authentication anywhere in `admin/server.py`.
Combined with the bind address at `admin/server.py:365-367`:

```python
if __name__ == "__main__":
    port = int(os.environ.get("FINOPS_PORT", "8000"))
    app.run(host="0.0.0.0", port=port, threaded=True)
```

any host that can reach this port — or a browser tab an operator has open
that loads an attacker-controlled page — can trigger `scripts/enqueue.py`
(builds and queues ~30 experiment cells, per `scripts/enqueue.py`'s own
docstring) or clear the queue, with zero confirmation on the server side.
A single `curl -X POST http://<host>:8000/api/experiments` with no body does
it.

**Fix:**
- Require an explicit `action` field and reject requests with no JSON body
  instead of defaulting to `"enqueue"`:
  ```python
  body = request.get_json(silent=True)
  if not isinstance(body, dict) or "action" not in body:
      return jsonify({"error": "missing action"}), 400
  action = body["action"]
  ```
- Add authentication (shared-secret header, or bind to `127.0.0.1` and put it
  behind an authenticated reverse proxy / SSH tunnel for remote access) before
  this ships anywhere off a trusted single-operator machine. At minimum,
  default `host` to `127.0.0.1` and require an explicit opt-in env var to
  bind wider.

---

## MAJOR

### M1 — `/api/matrix` does one blocking `LRANGE` per cell, unpiped, on every 5-second poll from every open tab

`admin/server.py:161-222` (`_retained_telemetry`) loops over every cell and
issues a separate `redis_client.lrange(f"{EVENT_LOG_PREFIX}{cell_id}", 0, -1)`
(`admin/server.py:178`) — a synchronous network round trip per cell, each of
which can return up to `EVENT_LOG_MAX = 500` entries (`src/instrument/live.py:20`)
that are then individually `json.loads`-ed in `_step_sample` (`admin/server.py:102-105`).

This runs inside the Flask request handler for `GET /api/matrix`
(`admin/server.py:225-253`), which `admin/static/app.js:16,899` polls every
`MATRIX_POLL_MS = 5000` from every open browser tab. `scripts/enqueue.py`'s
own matrix (`STORIES × TIERS × quality × conditions`) already produces ~30
cells per model; with several tabs open this becomes dozens of sequential,
unpipelined Redis round trips and up to 15,000 JSON decodes every 5 seconds,
each blocking one Werkzeug worker thread for the duration.

**Fix:** batch the reads with a Redis pipeline (`pipe = redis_client.pipeline(); [pipe.lrange(...) for cid in cell_ids]; pipe.execute()`) so the fan-out is one
round trip instead of N, and consider caching the aggregate for the poll
interval so multiple tabs don't each pay the full cost independently.

### M2 — `history_capped` truncation signal is computed but never surfaced, so "reported spend" can silently understate reality for long-running cells

`admin/server.py:207-210` computes, per cell:

```python
"history_size": len(history),
"history_capped": len(history) >= EVENT_LOG_MAX,
```

but `grep -n "history_capped" admin/static/*.js` returns nothing — the field
is never read by `app.js` or `control-room-core.js`. Meanwhile
`events_log:{cell_id}` is a rolling window shared by **every** event type
(`text`, `reasoning`, `tool_use`, `step_start`, `step_finish` — see
`src/instrument/live.py:72-87`, which `lpush`+`ltrim`s on every
`publish_event()` call regardless of type), capped at 500 total entries
(`EVENT_LOG_MAX`). A chatty session with many reasoning/tool events can evict
older `step_finish` cost samples before 500 of them accumulate, so
`reported_cost` in `/api/matrix` (and the "Reported spend" rail at
`admin/static/index.html:24`) becomes a silent lower bound with no
in-UI indication, even though the backend already knows and reports it.

**Fix:** thread `history_capped`/`available` through to the rail — e.g. append
a "±" or footnote to `#reported-spend` / the per-cell sparkline
(`admin/static/app.js:186-234`) when any selected/visible cell has
`history_capped: true`, so operators know the total is a floor, not an exact
figure.

### M3 — Publish-before-persist ordering in the SSE publisher can cause silent, non-self-healing undercounts

`src/instrument/live.py:85-87`:

```python
self._r.publish(channel, payload)
self._r.lpush(log_key, payload)
self._r.ltrim(log_key, 0, EVENT_LOG_MAX - 1)
```

`publish` happens before the event is durably recorded in the retained list.
`admin/server.py:293-298` (`api_events`) deliberately subscribes to the pubsub
channel *before* reading history, with a comment explaining exactly this race
("an event published during replay is queued by Redis instead of falling
through the history/live gap") — and `admin/static/app.js:428-445`
(`isReplayRaceDuplicate`) correctly de-duplicates the resulting replay/live
overlap for a **single** event.

The unhandled half of the same race is on the aggregation side:
`admin/static/app.js:571-582` (`pruneReconciledSamples`) drops a live-overlay
sample once a *later* `/api/matrix` poll's request sequence number has passed,
on the assumption that the poll's `LRANGE` must have already observed
everything published earlier. That assumption is a timing heuristic, not a
verified fact — it never checks whether the specific sample is actually
present in the new snapshot's `cells[cellId].samples`. If `ltrim` has already
evicted the entry (see M2 — the 500-slot window is shared across all event
types) by the time the next poll's `LRANGE` runs, the overlay is discarded
under the belief that it's "now baked into the aggregate," when in fact it
never made it into Redis's retained window at all. The cost is dropped from
the running total permanently, with no retry and no visible signal.

**Fix:** either (a) reorder `live.py` to `lpush`+`ltrim` before `publish`, so
"delivered live" implies "already retained," or (b) have
`pruneReconciledSamples` verify the sample's identity is actually present in
the new snapshot's per-cell `samples` before dropping the overlay (this is
exactly what the already-computed `identity` field in `_step_sample`
(`admin/server.py:139-148`) and `extractSample`
(`control-room-core.js:101-114`) was seemingly built for — see M4).

### M4 — Server admin dashboard runs on Werkzeug's threaded dev server with no connection cap, for a workload defined by long-lived SSE connections

`admin/server.py:367`: `app.run(host="0.0.0.0", port=port, threaded=True)`.
Both `/api/status` (`admin/server.py:256-279`) and `/api/events/<cell_id>`
(`admin/server.py:282-322`) are infinite generators (`while True: ... timeout=1.0`)
that hold a thread and a Redis pubsub connection open for as long as a browser
tab stays connected. Werkzeug's built-in server is explicitly documented by
Flask as not production-grade and has no configured bound on concurrent
threads/connections here. A handful of operators leaving Control Room open in
several tabs (each opening one `/api/status` and one `/api/events/...`
connection) is enough to start exhausting the default thread pool on a modest
host. This is consistent with `admin/server.py:13-14`'s own framing ("Run:
`python3 admin/server.py`") as the intended deployment.

**Fix:** run behind a proper ASGI/WSGI server with a worker/connection limit
(e.g. `gunicorn --worker-class gthread --threads N`), or move SSE fan-out to
an async framework if concurrent viewers are expected to grow beyond a
handful.

---

## MINOR

### N1 — `identity` is computed with matched 12-decimal-precision logic on both sides but is dead code

`admin/server.py:88-92` (`_identity_number`) and `control-room-core.js:54-58`
(`identityNumber`) are written to format numbers *identically* between Python
and JS ("Format numbers consistently with the Flask sample identity helper"),
and `_step_sample` (`admin/server.py:139-150`) / `extractSample`
(`control-room-core.js:101-114`) both build a composite `identity` string from
session id, timestamp, and every token/cost field. This value is returned to
the client in every retained sample and is stashed on live samples
(`admin/static/app.js:395`: `state.burnSamples.push({ identity: sample.identity, ... })`),
but it is never compared against anything — `grep -n "\.identity\b"
admin/static/*.js` shows exactly one read site, and that site only stores it,
never checks it. All de-duplication in the client actually happens on the raw
SSE payload text (`rawIdentity = String(raw ?? "")` at `admin/static/app.js:450`)
or on the timing heuristic in M3, not on this field.

**Fix:** either wire `identity` into the M3 fix (verify overlay-vs-snapshot
membership by identity instead of by timing) or delete the now-unused
computation and the matched-precision comment on both sides — as written it
is complexity with no behavior attached to it.

### N2 — Redundant `beginReplay()` call on the initial connection

`admin/static/app.js:483-490` calls `beginReplay()` once before constructing
the `EventSource`, then `source.onopen` (`admin/static/app.js:495-500`) calls
`beginReplay()` again. On the very first connection nothing can arrive between
construction and `onopen` (no messages precede `onopen` in the `EventSource`
spec), so the first call is redundant. Harmless, but worth removing or adding
a one-line comment distinguishing "reset on connect attempt" from "reset on
(re)open" so a future reader doesn't wonder if it's protecting against a real
race.

### N3 — Ghost cells can linger up to two poll cycles after being removed from Redis

`applyStatusOverrides` (`admin/static/app.js:585-601`) writes
`cells[cellId] = override.status` even when `cellId` is absent from the
current snapshot (`cells[cellId]` is `undefined` → `normalizeStatus` → `"unknown"`,
which won't match `override.status` on the first comparison), which
re-introduces a key that no longer exists server-side into `state.cells` for
up to `remainingSnapshots` (2) polls (~10s at `MATRIX_POLL_MS = 5000`) before
the override is discarded. This is a bounded, self-healing staleness window
and is presumably intentional (comment at `admin/static/app.js:596`: "Repeated
matrix disagreement wins if the status stream missed a later transition"),
but it does mean `#fleet-total` (`admin/static/app.js:303`) can transiently
overcount by one after a `clear-queue` action. Worth a one-line note in the
docstring at `admin/static/app.js:6-9` calling this out explicitly as a known
trade-off, since it isn't otherwise documented anywhere.

### N4 — Fixed 250ms replay/live race-dedup window is a hard-coded assumption about delivery latency

`admin/static/app.js:15` (`REPLAY_RACE_WINDOW_MS = 250`) bounds how long
`isReplayRaceDuplicate` (`admin/static/app.js:435-445`) will suppress the
known subscribe-before-history duplicate described in M3's design comment. If
delivery of the duplicate live message is delayed past 250ms (server under
load, slow client main-thread, or a burst of other events processed first),
the duplicate is treated as a new event: it is shown twice in the transcript
and, since `row.sample && !state.replayMode` is true at that point
(`admin/static/app.js:462`), it is double-counted into `liveSamplesByCell`
and the burn-rate rail. Low likelihood in normal operation, but there's no
telemetry or fallback (e.g. also checking against `state.eventLedgerCounts`,
which already tracks presented occurrences) if the window is missed.

---

## Convention conformance

Checked against the repo's own `conventions/python.yaml`, which
`commit_analysis.py`'s `score_conventions()` scores against.

### N5 — `admin/server.py` has zero return-type-annotated functions despite importing `from __future__ import annotations`

`conventions/python.yaml:52-54` states: "Function signatures should use type
hints." `admin/server.py:17` imports `from __future__ import annotations` but
none of its 15 function definitions carry a `->` return annotation
(`grep -cE "^\s*def [a-zA-Z_]+\([^)]*\) ->" admin/server.py` → `0`), and only
one local variable (`counts: dict[str, int]` at `admin/server.py:236`) is
annotated at all. This is inconsistent with the sibling module it imports
from, `src/instrument/live.py`, which fully type-hints every method (e.g.
`def publish_status(self, status: str) -> None:` at `src/instrument/live.py:63`,
`def make_publisher() -> LivePublisher | None:` at `src/instrument/live.py:92`).

**Fix:** add return types at minimum to the route handlers and the
`_retained_telemetry`/`_step_sample` family (`-> dict[str, Any]`,
`-> float | None`, etc.) to match `live.py`'s style.

### N6 — Four lines exceed the repo's 100-character line-length convention

`conventions/python.yaml:56-59` caps lines at 100 characters.
`admin/server.py:61` (101 chars), `admin/server.py:200` (106 chars),
`admin/server.py:201` (109 chars), and `admin/server.py:335` (112 chars) all
exceed it. None are meaningfully harder to read wrapped; a formatter pass
(`ruff format` / `black`, if configured for the project) would fix these
mechanically.

---

## What's solid (no action needed, noted for context)

- No `innerHTML`/`outerHTML`/`eval` usage anywhere in `admin/static/*.js` —
  all text insertion goes through `element()`'s `textContent`
  (`admin/static/app.js:72-78`), so the transcript renderer is not vulnerable
  to XSS from attacker-influenced event payloads (tool names, reasoning text,
  etc.).
- The subscribe-before-history-read ordering in `api_events`
  (`admin/server.py:293-298`) plus the client-side race-dedup
  (`admin/static/app.js:428-445`) correctly close the single-event replay/live
  overlap gap described in M3 — the gap in M3 is specifically the *aggregate*
  bookkeeping downstream of that already-correct single-event handling.
- `_reported_number` (`admin/server.py:65-75`) and `safeNumber`
  (`control-room-core.js:14-16`) are kept in lockstep (both reject booleans,
  NaN/Infinity, and negatives), and `tests/test_admin_server.py:114-134`
  exercises the malformed-input paths directly — good parity between the two
  runtimes that this file class of bug is easy to introduce in.
- `admin/static/style.css` includes the responsive breakpoint, reduced-motion,
  and focus-visible rules the tests assert on (`tests/test_admin_frontend.py:65-73`),
  and all CSS classes referenced from `app.js` (`state-badge`, `token-bar`,
  `cost-line`, `sparkline-empty`, etc.) resolve to a real rule — no dangling
  class references found.
