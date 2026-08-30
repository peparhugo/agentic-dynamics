---
status: accepted
---
# Control Room Refresh: Adversarial QA Log

**Date:** 2026-08-23
**Scope:** `apps/control_room/static/` refresh at commit under review.

## Verdict

**PASS with two accepted follow-ups.** The 28-route contract, both SSE endpoints, existing static
frontend contracts, and full non-external regression suite remain intact. The follow-ups below
require an intentionally separate transcript/lifecycle-runtime refactor; they are not concealed
as completed work.

## Finding Table

| Attack | Finding | Disposition | Evidence |
| --- | --- | --- | --- |
| Safe area | Refresh shorthand reset the command rail's base `safe-area-inset-top` padding. | **Fixed.** The final rail rule restores `padding-top: max(...)`. | `static/style.css` c2 rail override. |
| 768px layout | A 448px docked Detail column left Fleet narrower than its 180px card track. | **Fixed.** Detail is capped to `min(320px, 38vw)` until the 1200px wide layout. | `static/style.css` desktop c2 media rules. |
| Touch target | The sheet grabber's visible pill was within a 20px hit area. | **Fixed.** The shared handle now has `min-height: var(--touch-target)` while its visual pill stays centered. | `static/style.css` `.sheet-handle`. |
| Telemetry SVG | Generated `polyline` and `rect` nodes used CSS box properties, so traces/bars could render invisibly. | **Fixed.** `.cost-line` receives SVG stroke properties and `.token-bar` receives SVG fill/radius properties. | `static/style.css` telemetry geometry rules; producer remains `static/app.js`. |
| Detail modal | Phone Detail trapped Tab but did not announce dialog semantics or isolate the background. | **Fixed.** Modal Detail now sets `role="dialog"` and `aria-modal`, while command rail, nav, and boards become inert/`aria-hidden`; docked desktop Detail remains a normal landmark. | `static/detail-sheet.js` `setModalSemantics()`. |
| Nested Escape | Escape on supervisor interrupt or Registry closed its parent Detail/System surface after closing the nested control. | **Fixed.** Nested handlers stop propagation after local close. | `static/app.js` control bindings. |
| Reduced motion | Explicit `scrollIntoView({behavior:"smooth"})` bypassed CSS reduced-motion preferences. | **Fixed.** Shell and Detail select `auto` for `prefers-reduced-motion: reduce`. | `static/shell.js`, `static/detail-sheet.js`. |
| Forced colors | Custom form focus resets could obscure focus in high-contrast mode. | **Fixed.** Forced-colors supplies a system-color `:focus-visible` outline. | `static/style.css` forced-colors media query. |
| Badge contrast | Interactive ownership text used accent ink on an inset surface. | **Fixed.** Interactive badges use iris foreground on iris wash. | `static/style.css` c2 badge overrides. |
| Light status contrast | Legacy light aliases overwrote c2 lifecycle colors, reducing 11px status-word contrast. | **Fixed.** Aliases now map back to the darker c2 light tokens. | `static/style.css` `[data-theme="light"]`. |
| Pipeline dots | Stage pseudo-dots used `currentColor` but stages only colored their border. | **Fixed.** Every stage state sets foreground color as well as its border. | `static/style.css` `.pipeline-stage.stage-*`. |
| Design polling | A removed selected design session detached its stream but left draft polling active. | **Fixed.** The roster-removal path clears and nulls `draftPollTimer`. | `static/app.js` `loadDesignSessions()`. |
| Transcript churn | Every unpaused event rebuilds up to 500 transcript log rows. | **Accepted follow-up.** A bounded keyed/append-only transcript renderer changes live-region announcement and replay semantics; it needs dedicated browser coverage before alteration. The existing hard 500-row cap, one EventSource, and selected-stream replacement remain intact. | `static/app.js` `renderTranscript()` and `receiveEvent()`; c1 audit §Performance Risks. |
| Page lifecycle | Page-lifetime polling/status SSE does not pause on hidden pages or explicitly tear down on `pagehide`. | **Accepted follow-up.** Existing timers are created once at boot and selected SSE cleanup occurs on every selection change, so this is not runaway behavior. `pagehide/pageshow` lifecycle ownership should be added with browser regression tests rather than opportunistically changing six live data paths. | `static/app.js` boot intervals and selected-stream handoff; c1 audit §Performance Risks. |

## Route and SSE Smoke Matrix

The portal booted from this worktree at `FINOPS_PORT=8023`; port 8000 was not touched. Mutation
routes were exercised through `OPTIONS` only, never `POST`.

| Surface | Result |
| --- | --- |
| `GET /` | `200` |
| `GET /api/matrix`, `/api/routing`, `/api/flags`, `/api/registry`, `/api/design-sessions`, `/api/claude-agents`, `/api/claude-agents/daemon` | `200` |
| `GET /api/status` | `200` after bounded heartbeat wait; client disconnected cleanly at timeout. |
| `GET /api/events/smoke-cell` | `200` with retained replay boundary before bounded client disconnect. |
| `GET /api/registry/smoke-entity`, `/api/design-sessions/smoke/spec` | Expected `404` for absent resources. |
| `GET /api/claude-agents/smoke/logs` | Expected `502` because no smoke Claude client/session exists. |
| 15 POST-only routes | `OPTIONS 200`: experiments, queue reinterleave, both flag actions, five design mutations, six Claude mutations. |

SSE resilience evidence comes from the existing stream design plus tests: `replaceEventSource()`
closes an old source before constructing the next; malformed event text is retained as `RAW`; the
server replays history, emits named `replay_complete`, then continues live frames. These contracts
remain exercised by `tests/test_admin_frontend.py` and `tests/test_admin_server.py`.

## Console and Viewport Evidence

| Check | Result | Reason |
| --- | --- | --- |
| JS module request resolution | **PASS** | `/static/style.css` and all static module references remain served by the Flask shell; structural frontend contracts pass. |
| Browser console clean | **Accepted limitation** | No Chromium, Firefox, Playwright, or Node runtime is installed in this worktree. A real browser console could not be observed honestly. |
| Computed 360px / 768px / 1440px layout | **Static PASS; runtime limitation** | CSS has 360-safe rail compaction, compact Detail width at 768px, wide detail at 1200px, safe-area padding, 44px handle targets, and reduced-motion/forced-colors rules. Computed layout still needs browser visual regression tooling. |
| Keyboard | **Static PASS; runtime limitation** | Detail and System trap focus when modal; System returns focus; nested Escape is local; visible and forced-colors focus treatment is defined. Physical keyboard traversal requires a browser harness. |

## Final Polish Notes

1. The command rail now preserves notch spacing and presents liveness through the existing
   browser connection state, not inaccessible SSE ping comments.
2. Fleet remains dense without theatrical card pulses: running state is text/icon/color plus a
   restrained stage/header dot, while selected work uses iris elevation.
3. Traces and bars are now real SVG marks rather than CSS boxes attached to SVG nodes.
4. Light mode is a first-class retained preference: direct c2 tokens and legacy aliases now agree
   on status contrast.
5. Modal behavior is consistent: System is a labelled dialog, and phone Detail dynamically gains
   equivalent semantics and background isolation.

## Release Steps

1. Merge branch `feature/control-room-refresh` into the deployment branch after review.
2. On the portal host, pull the merged revision and restart the Control Room process on port 8000
   using the normal service manager or `FINOPS_PORT=8000 python3 apps/control_room/server.py`.
3. Open `/` and verify `/api/matrix`, `/api/status`, and one selected `/api/events/<cell_id>`
   stream against live data. Do not send a mutation as a smoke check.

## Follow-ups

1. Add a browser runtime (Playwright or equivalent) to test real 360px/768px/1440px layout,
   console cleanliness, Tab/Escape paths, forced-colors, and reduced-motion behavior.
2. Refactor transcript rendering to append/reconcile the bounded 500-row log and announce only
   new rows; cover replay and pause/follow behavior before shipping it.
3. Add page lifecycle ownership for polling and page-level status SSE, with a regression harness
   proving no duplicate intervals or sources after bfcache restoration.
