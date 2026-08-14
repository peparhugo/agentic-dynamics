# Control Room — Architecture Review

Scope: `admin/server.py` (Flask + SSE backend, 367 lines), `admin/static/app.js`
(browser controller, 901 lines), `admin/static/control-room-core.js` (pure data
helpers, 277 lines), `admin/static/style.css` (996 lines). Read for grounding:
`src/instrument/live.py` (SSE publisher), `src/instrument/routing.py`, `docs/scope.md`,
`docs/code_review.md` (prior correctness/security pass — not repeated here except
where a finding is architectural rather than a bug), `BLUEPRINT_v3.md` (the
instrument → derive → policy → grid → campaign chain this repo is organized around).

This review is about shape, not bugs: where boundaries sit, who owns what data, and
whether the Control Room's structure helps or fights the rest of the repo. `docs/code_review.md`
already covers correctness/security findings (auth, Redis fan-out, race conditions);
this document is a second, orthogonal pass and does not re-derive those.

---

## 1. Architecture summary

The Control Room is a three-tier read-only observability layer bolted onto the
existing Redis-backed experiment transport:

```
Redis (story_status, story_jobs, story_results, events:<id>, events_log:<id>)
        │
        ▼
admin/server.py  ─── Flask routes, no persistent server-side state ───┐
   /api/matrix        (poll) status hash + queue length + derived     │
                        "retained telemetry" aggregate                │
   /api/status         (SSE)  status-transition pub/sub relay          │
   /api/events/<id>    (SSE)  per-cell replay (LRANGE) + pub/sub relay │
   /api/routing        (poll) reads a results-summary JSON file        │
   POST /api/experiments  shells out to scripts/enqueue.py             │
        │                                                              │
        ▼                                                              │
admin/static/control-room-core.js  ── pure functions, no DOM, no I/O ──┘
   parseEvent, extractSample, normalizeTranscriptEvent, reconcileTelemetry,
   burnRate, sortCellIds — deterministic, unit-testable in isolation
        │
        ▼
admin/static/app.js  ── stateful browser controller ──
   one mutable `state` object, DOM rendering, two long-lived EventSources
   (status stream + selected-cell stream), a 5s matrix poll, reconciliation
   of "authoritative snapshot" vs "live overlay not yet baked into a poll"
```

Two design decisions define almost everything downstream:

- **The server is a stateless relay, not an aggregator-of-record.** `api_matrix`
  recomputes `_retained_telemetry` (admin/server.py:161-222) from a fresh `LRANGE`
  per cell on every request; nothing is cached or persisted by the Control Room
  itself. The browser is the only place that holds a running "session" concept
  (`state.liveSamplesByCell`, `state.burnSamples`), and it discards that state on
  reload. This matches the stated constraint in `docs/scope.md`: "Preserve the
  names, types, and meanings of `story_jobs`, ... events_log:<cell_id>... Any
  endpoint or response-field addition ... must be additive ... derived from the
  existing Redis keys."
- **Derivation is duplicated across two runtimes on purpose.** `_step_sample`
  (admin/server.py:95-158) and `extractSample` (control-room-core.js:71-123),
  `_reported_number`/`safeNumber`, and `_identity_number`/`identityNumber` are
  independent reimplementations of the same parsing/validation rules, one in
  Python for the retained-window poll path, one in JS for the live SSE path. This
  is a real architectural fork, not an oversight — `docs/code_review.md`'s N5/N1
  findings note the two are kept in careful lockstep, and `tests/test_admin_server.py`
  exercises the malformed-input paths on the Python side while
  `tests/test_admin_frontend.py` presumably covers the JS side.

### Data flow (SSE + Redis telemetry path)

1. A running experiment session (opencode backend) calls `LivePublisher.publish_event`
   (`src/instrument/live.py:72-89`), which does `PUBLISH events:<id>` then
   `LPUSH events_log:<id>` + `LTRIM ... 0 499` — pub/sub for live delivery, a
   capped list for replay. This module is outside `admin/` and untouched by this
   feature (per `docs/scope.md`'s "do not alter workers, publishers... " constraint).
2. `GET /api/events/<cell_id>` (admin/server.py:282-322) subscribes to the pub/sub
   channel *before* reading the retained list, then replays the list, then streams
   live messages — a deliberate ordering to avoid a replay/live gap (comment at
   admin/server.py:295-296).
3. `GET /api/matrix` (admin/server.py:225-253) is a *second, independent* read of
   the same `events_log:<cell_id>` keys, via `_retained_telemetry`, polled every
   5s by every open tab (`app.js:16`, `MATRIX_POLL_MS`).
4. The browser reconciles the two: the matrix poll is authoritative for "settled"
   totals, the SSE stream contributes live samples not yet reflected in a poll,
   via `reconcileTelemetry` (control-room-core.js:220-236) and
   `pruneReconciledSamples` (app.js:571-582).

This is the crux of the module's cohesion: **the two HTTP data paths (poll vs.
stream) are aggregating the same underlying Redis list independently, and the
client reconciles them by timing rather than by the server producing one
authoritative merged view.** It works because of the care put into `identity`
matching and the request-sequence pruning heuristic, but it is a client-side
answer to what is structurally a server-side consistency problem.

### Client-vs-server split

The split follows a defensible line: **the server owns "what does Redis currently
say," the client owns "what have I personally observed since I've been open."**
Concretely:

| Concern | Owner | Where |
|---|---|---|
| Redis connectivity, retry-free reads | server | `admin/server.py:_redis`, every route |
| Parsing raw event payloads into a `{cost, tokens, identity}` sample | **both** (duplicated) | `_step_sample` / `extractSample` |
| "Is this the authoritative total" | server (per-poll) | `_retained_telemetry` |
| "Is this a duplicate of something already shown" | client only | `isReplayRaceDuplicate`, `rememberEvent` |
| Burn rate (60s rolling window) | client only | `burnRate` (control-room-core.js:239-245) |
| Cell selection / which SSE stream is open | client only | `state.selectedId`, `connectSelectedStream` |
| Enqueue/clear side effects | server (shells to `scripts/enqueue.py`) | `api_experiments` |

Given the `docs/scope.md` constraint of "vanilla JS/HTML/CSS, no bundler, no new
service, no new runtime dependency," keeping burn-rate and dedup logic in the
browser is close to the only option available — a real aggregation service would
violate the "no new service" constraint outright. That constraint, not taste,
is what pushes so much derivation logic into `app.js`.

### Fit with the repo's instrument → derive → policy → grid → campaign chain

`BLUEPRINT_v3.md`'s framing is explicit: the repo's product is *information*,
produced by a chain where `instrument` (the ledger: events, attempts, tokens) is
the base layer, `derive` turns that into measurement fields, and `policy`/`grid`/
`campaign` consume the derived information to make and compare routing decisions.

The Control Room sits **entirely within `instrument`**, and its own `_step_sample`
/`extractSample` pair is a second, small `derive` step — but a *presentation-only*
one. It is worth being precise about what it does and does not do relative to
that chain:

- It **does not** write anything back into the ledger (`AttemptRecord`) that
  Blueprint v3's step 3 (`confidence`, `perturbation_strength`,
  `test_executed_success`) depends on. `reported_cost`/`input_tokens` derived here
  live only in the HTTP response and the browser's `state` object; nothing is
  persisted to a new Redis key or file. This is correct given `docs/scope.md`'s
  "derived from existing Redis keys, additive, backward-compatible" constraint —
  the Control Room is explicitly not supposed to become a new instrumentation
  source of record — but it does mean the same `_step_sample` parsing logic (cost/
  token extraction from `step_finish` events) may eventually need to be written
  *again*, a third time, wherever Blueprint v3 step 3's ledger instrumentation
  lands (likely in `src/instrument/`, adjacent to `live.py`). That module would
  be a natural place to promote a shared "extract a reported-cost sample from an
  opencode event" helper to, rather than duplicating it across `admin/server.py`,
  `control-room-core.js`, and a future ledger writer.
- It **is** a pure `[derive-for-display]` consumer of `instrument`-layer data,
  cleanly separated from `policy`/`grid`/`campaign` — `/api/routing`
  (admin/server.py:325-337) is the one place those two worlds touch, and it does
  so by delegating entirely to `compute_routing` in `src/instrument/routing.py`
  rather than reimplementing routing logic in `admin/`. That is the right
  boundary: `admin/server.py` never contains policy logic itself.
- The dashboard is consistent with "the agent itself is a measurable workflow"
  only in the passive sense of watching it; it has no write path into that loop
  (by explicit design — see `docs/scope.md`'s "connection is intentionally
  observational" framing). Architecturally this keeps Control Room off the
  critical path of the experiment machine: a bug in `admin/` cannot corrupt a
  cell's ledger, only misrepresent it to an operator. That is a load-bearing
  property worth preserving deliberately in any future change here.

---

## 2. Strengths

- **Hard separation between pure derivation and stateful rendering on the
  client.** `control-room-core.js` has zero DOM/`window`/`fetch` references —
  confirmed by its own docstring's intent ("Keeping parsing, reconciliation, and
  transcript normalization independent of the DOM makes stream behavior
  deterministic and browser-free testable") and by it exporting through
  `module.exports` for Node-side testing (control-room-core.js:276). This is the
  single best structural decision in the change: the highest-risk logic (event
  parsing, dedup, reconciliation) is isolated from the DOM and testable without a
  browser, directly satisfying `docs/scope.md`'s "deterministic DOM/event tests
  ... without Redis or opencode running" constraint.
- **The server stays a thin, stateless relay.** No new database, cache, or
  in-memory aggregation state was introduced in `admin/server.py`; every route
  recomputes from Redis on demand. This keeps the module's failure modes simple
  (worst case: a slow or wrong read, never a stale in-process cache diverging
  from Redis) and keeps `admin/server.py` at 367 lines despite the added
  telemetry surface — the file did not grow into a second application.
- **Additive-only contract with the existing transport is actually honored.**
  `/api/matrix`'s response keeps every pre-existing field (`total`,
  `remaining_in_queue`, `cells`, etc. — admin/server.py:240-251) and adds a new
  `telemetry` key rather than reshaping the response; `/api/events/<cell_id>`
  keeps emitting the same raw `data: <payload>` frames existing clients rely on
  and adds a new named `replay_complete` event rather than changing frame
  semantics. `src/instrument/live.py` (the publisher, outside `admin/`) is
  untouched. This is a case where a stated constraint (`docs/scope.md`: "Preserve
  all existing endpoint paths and existing response fields") was followed
  precisely rather than approximately.
- **The routing board integration is a clean delegation, not a reimplementation.**
  `/api/routing` (admin/server.py:325-337) does file I/O and error shaping only;
  all actual routing logic stays in `src/instrument/routing.py`, keeping
  `admin/` free of policy code.
- **`docs/scope.md` reads as a real architectural contract, and the code was
  visibly written against it** — the "observational, not control" framing shows
  up directly in the code (`admin/server.py`'s docstring, `api_experiments`'
  explicit `action` allowlist, the client's read-only Attach/Detach-only
  affordances). Scope documents that predict the shipped shape this closely are
  uncommon; it's worth preserving the practice of writing the constraint doc
  before the implementation for future `admin/` work.

## 3. Risks / debt

Ordered roughly by how much they compound if left alone. Findings that are
strictly correctness/security bugs (unauthenticated enqueue, unpiped Redis reads,
publish-before-persist race) are in `docs/code_review.md` (C1, M1, M3) and not
repeated here; the entries below are shape/boundary problems that would remain
even if every bug in that review were fixed.

- **Triple-duplicated derivation logic, with a fourth copy likely coming.**
  `_step_sample` (Python) and `extractSample` (JS) already implement the same
  cost/token-extraction rules twice, kept in sync by convention and a matching
  `_identity_number`/`identityNumber` formatter (admin/server.py:88-92,
  control-room-core.js:54-58) — a coupling that is invisible in either file's
  imports and enforced only by developer discipline plus
  `docs/code_review.md`'s N5. Per §1, Blueprint v3's step 3 (instrumenting
  `confidence`/`perturbation_strength`/`test_executed_success` into the ledger
  proper) will plausibly need this exact "extract a reported sample from a
  `step_finish` event" logic a third time, in `src/instrument/`. Nothing today
  enforces the three stay compatible. **This is a structural violation waiting
  to happen, not yet an actual one** — worth flagging before step 3 lands rather
  than after.
- **The matrix-poll and SSE-replay paths are two independent readers of the same
  Redis list with no shared abstraction**, reconciled only by the client's
  timing heuristics (`pruneReconciledSamples`, the 250ms `REPLAY_RACE_WINDOW_MS`
  — see `docs/code_review.md` M3/N4 for the correctness consequences). Architecturally,
  this is the same root cause as the duplication above: `admin/server.py` has no
  single function that says "give me the authoritative telemetry for cell X as of
  now" — that concept exists only implicitly, split across `_retained_telemetry`
  and the raw SSE relay, and stitched back together in the browser. A server-side
  per-cell aggregate endpoint/helper would collapse two sources of truth into
  one and remove the need for timing-based reconciliation on the client
  entirely — though it would cost an extra Redis round trip per poll unless
  fused with the M1 pipelining fix in `docs/code_review.md`.
- **`admin/server.py` reaches into `src/instrument` via a manual `sys.path`
  insert** (admin/server.py:27: `sys.path.insert(0, str(Path(__file__)...  / "src"))`)
  rather than the package being installed/importable normally. This works, but
  it means `admin/` is not really an independent module with a declared
  dependency on `instrument` — it's coupled by a runtime path hack that assumes
  a specific directory layout relative to `admin/server.py`'s location. It is a
  pre-existing pattern (not introduced by this change) but the Control Room
  deepens the dependency (importing `live`'s channel/key constants directly, in
  addition to `routing`), so the fragility now has more surface area than
  before.
- **`app.js` at 901 lines is a single file mixing five responsibilities**:
  DOM rendering (`renderRail`, `renderFleet`, `renderTranscript`,
  `createSparkline`), stream lifecycle (`connectSelectedStream`,
  `connectStatusStream`), reconciliation bookkeeping (`recordLiveSample`,
  `pruneReconciledSamples`, `applyStatusOverrides`), a11y announcements
  (`announce`), and control wiring (`bindControls`, the enqueue/clear action).
  Under the "no bundler" constraint this can't be split into ES modules without
  either multiple `<script>` tags (viable — no build step needed for that) or
  accepting the current shape. As-is, `state` (admin/static/app.js:27-65, ~40
  fields) is a single global mutable object every one of those five concerns
  reads and writes, so reasoning about which function can affect which state
  field requires reading the whole file. This is a stylistic/scale concern, not
  a violated constraint — flagging it because at 901 lines it is close to the
  point where further feature growth (more telemetry fields, more transcript
  event kinds) will make `state`'s implicit contract the bottleneck.
- **No formal schema for the opencode event payloads `_step_sample`/
  `extractSample` parse.** Both functions defensively branch over `part` being
  present-or-not, `tokens.cache` being scalar-or-object, multiple possible
  timestamp key names, etc. (admin/server.py:95-158,
  control-room-core.js:71-123). This defensiveness is appropriate given
  `docs/scope.md`'s "treat costs and tokens as reported telemetry, not billing
  truth... ignore malformed values safely" constraint, but it also means the
  actual shape of an opencode `step_finish` event is defined only implicitly, by
  what these two functions happen to handle, in two languages. A shared,
  documented (even informally, in a comment block or a small JSON Schema) event
  shape — living in `src/instrument/` next to `live.py`, the actual publisher —
  would give both derivations one source to validate against instead of each
  inferring the shape independently.
- **`admin/server.py` still shells out to a script (`scripts/enqueue.py`) for
  its one write path** (admin/server.py:347-357, `subprocess.run`). This was true
  before the Control Room work and is unchanged by it, but the feature grows the
  UI's investment in that endpoint (adding a confirm-gated Clear action per
  `docs/scope.md` acceptance criterion 17), increasing exposure to a process-boundary
  write path (env/cwd/argv passing, `capture_output` buffering full stdout)
  where a direct function call into `scripts/enqueue.py`'s logic would be
  more debuggable and avoid a spawned-process failure mode. Not a new problem,
  but the Control Room is the first caller to add a second action (`clear`) to
  it, which is a natural point to have reconsidered the interface rather than
  extending the string-based `action` parameter over a subprocess call.

## 4. Recommended changes, ranked by impact vs. effort

| # | Change | Impact | Effort | Notes |
|---|---|---|---|---|
| 1 | Give `_retained_telemetry`/`_step_sample` (Python) and `extractSample`/`reconcileTelemetry` (JS) a documented, shared "sample shape" contract — even just a comment block enumerating the exact fields/types each must produce, co-located in both files, cross-referenced by name — so the two stay in sync as more than convention. | High: prevents silent drift between the two derivations as the codebase changes them independently over time. | Low: no code restructuring, just an explicit contract + a test asserting the same fixture payload produces field-for-field-equal output in both runtimes. | Complements `docs/code_review.md` N5 (type hints) — this is about behavioral parity, not style. |
| 2 | Before Blueprint v3 step 3 lands ledger-level `confidence`/`perturbation_strength` instrumentation, extract the `step_finish` → `{cost, tokens}` parsing rules (currently `_step_sample`) into a `src/instrument/` helper that both `admin/server.py` and the future ledger writer import, rather than letting a third copy diverge in the ledger code. | High: this is the one duplication that's about to become a triplication if not addressed proactively; `src/instrument/` is exactly where Blueprint v3 says the real instrumentation work is heading. | Medium: requires moving logic across the `admin/` boundary, i.e. `admin/server.py` starts depending on a new shared module instead of owning the logic itself — needs the JS side to stay a hand-maintained port since there's no bundler to share code with the browser. | Worth sequencing *before* step 3's ledger work starts, not after — retrofitting shared logic once three copies exist is more expensive than designing for it now. |
| 3 | Give `admin/server.py` one server-side function that returns the authoritative telemetry for a single cell (folding in live-vs-replay dedup by `identity`, per `docs/code_review.md` M3's fix option (b)), so the client's timing-based `pruneReconciledSamples` heuristic can be simplified or removed. | Medium-high: removes a class of edge cases (M3, N4) at the root — a timing-window heuristic — rather than patching around it, and reduces `app.js`'s reconciliation surface. | Medium: touches both the aggregation endpoint and the client's overlay logic; should be paired with `docs/code_review.md` M1's pipelining fix since both touch `_retained_telemetry`. | Architectural root cause behind two of the four MAJOR findings in the prior code review. |
| 4 | Split `admin/static/app.js` along its five responsibilities (render / stream-lifecycle / reconciliation / a11y / controls) into separate `<script>`-tag-loaded files, matching how `control-room-core.js` is already split out — no bundler required, just more files. | Medium: improves navigability at the current size; not urgent, but cheaper to do now than after more telemetry/transcript features land on top of the current single-file `state` object. | Low-medium: mechanical split, main cost is deciding where `state` itself lives (likely stays a single shared object passed/closed-over across files). | Purely a maintainability call, not a constraint violation — defer if no near-term `app.js` growth is planned. |
| 5 | Replace the `sys.path.insert` import hack in `admin/server.py:27` with a proper package-relative import (e.g. running the app as `python -m admin.server` from the repo root with `src/` on `PYTHONPATH` via a `pyproject.toml`/`conftest.py` mechanism already used by the test suite, if one exists) or an installed editable package. | Low-medium: doesn't fix a bug, but removes a layout-fragile pattern that the Control Room deepened (now imports two `instrument` submodules instead of implicitly none). | Low: mechanical, but needs verifying it doesn't break the `python3 admin/server.py` direct-run entry point that `docs/scope.md` explicitly requires ("keeps the dashboard runnable through `python admin/server.py`"). | Lowest priority — cosmetic/consistency, and the constraint to keep direct-run working caps how much this can change. |

---

*Reviewed: `admin/server.py`, `admin/static/{app.js,control-room-core.js,style.css}` at
commit `44a1e288e`. This document assesses structure and fit with the repo's stated
architecture (`docs/scope.md`, `BLUEPRINT_v3.md`); it does not restate the
correctness/security findings already tracked in `docs/code_review.md`.*
