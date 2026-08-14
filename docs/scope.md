# Control Room Scope

## Problem Statement

The admin portal exposes the information needed to observe experiments, but splits it across a matrix, a cell inspector, and a routing view. An operator cannot currently see fleet state, current AI spend, per-cell token-cost behavior, and the selected agent's activity on one screen. Failures and stream disconnections are also easy to miss because most frontend network errors are silent.

This feature turns `admin/` into a single-screen Control Room for live experiment supervision. Cost is the primary operational signal: the screen must pair a live reported-spend and burn-rate ticker with stateful cell cards, compact token-cost history, and a readable terminal transcript. Selecting a running cell must attach the control pane to that cell's existing opencode event stream so the operator can watch the active session without leaving the page.

The connection is intentionally observational. The existing runner closes subprocess stdin and provides no inbound command channel, process registry, or authenticated command transport. Calling a read-only attachment “control” is preferable to adding unsafe or misleading steering controls outside the existing architecture. Queue administration may continue to use the existing experiments endpoint, but pause, abort, prompt injection, and same-session steering are out of scope.

## Constraints

- Preserve Flask and server-sent events as the backend and transport. This keeps deployment and operational behavior consistent with the current portal.
- Preserve the names, types, and meanings of `story_jobs`, `story_results`, `story_status`, `status`, `events:<cell_id>`, and `events_log:<cell_id>`, including the 500-event retained-log cap. The Redis defaults remain port `6380`, database `1`.
- Preserve all existing endpoint paths and existing response fields. Any endpoint or response-field addition required to aggregate telemetry must be additive, backward-compatible, and derived from the existing Redis keys or event payloads.
- Keep implementation changes inside `admin/`, apart from this scope and the subsequent UX documents. Do not alter workers, publishers, opencode execution, queue semantics, or experiment result formats.
- Use vanilla JavaScript, HTML, and CSS with no bundler, compilation step, new service, iframe, or new runtime dependency. This keeps the dashboard runnable through `python admin/server.py`.
- Treat costs and tokens as reported telemetry, not billing truth. Aggregate only numeric cost and token fields present in opencode events, ignore malformed values safely, avoid double-counting replayed events, and label totals as partial when the retained 500-event window cannot prove completeness.
- Compute burn rate from newly observed live cost events over a documented rolling window; retained replay may establish spend history but must not create an artificial burn spike when a cell is attached or reconnected.
- Keep the control pane read-only. It may attach, detach, select, filter, and clear local transcript presentation, but it must not imply that it can send prompts, pause, abort, or otherwise steer the running process.
- Retain access to the existing routing board and `POST /api/experiments` behavior. A queue clear remains queue cleanup, not cancellation of already-running work, and any UI that exposes it must say so and require confirmation.
- Support current desktop browsers and a usable narrow-screen layout. Motion must respect `prefers-reduced-motion`, and status must never be communicated by color or animation alone.
- Backend additions require pytest coverage. Frontend behavior must be structured so deterministic DOM/event tests or an equivalent browser-free verification can exercise telemetry parsing, aggregation, rendering, and reconnection behavior without Redis or opencode running.

## Acceptance Criteria

1. [ ] Loading `GET /` presents a single-screen Control Room containing the spend header, cell fleet, selected-cell terminal, and read-only control pane; the existing routing board remains reachable without a full page load.
2. [ ] The spend header shows cumulative reported cost, a clearly unit-labeled rolling burn rate, input tokens, and output tokens. Before numeric cost telemetry exists, it shows an explicit “waiting for telemetry” or “unavailable” state rather than presenting an unsupported billing total.
3. [ ] A valid cost-bearing live event updates the spend total and burn rate without a page refresh. A valid token-bearing event updates the corresponding token totals, while absent, non-numeric, negative, or malformed fields do not corrupt the displayed aggregates.
4. [ ] Historical replay contributes at most once to cumulative reported spend and token totals. Reattaching or automatic SSE reconnection does not duplicate retained events, and replayed history does not count as activity in the live burn-rate window.
5. [ ] If available telemetry may omit events because `events_log:<cell_id>` is capped at 500 entries, the spend display visibly identifies the total as retained-window or partial telemetry; the UI never labels it as an authoritative invoice total.
6. [ ] Every cell returned by `GET /api/matrix` renders as a selectable card showing its full cell ID, current status text, and a distinct visual state for `queued`, `running`, `done`, `failed`, and `timeout`; unknown statuses render safely with a neutral state.
7. [ ] Status messages from `GET /api/status` update the matching card, status counts, and selected-cell details in place. Running cards pulse, terminal states do not pulse, and all pulsing or nonessential animation is disabled when reduced motion is requested.
8. [ ] Each cell card contains a compact sparkline based on that cell's ordered, reported token/cost samples. It renders a stable empty state when no samples exist, scales without `NaN` or invalid geometry, and has a textual accessible label describing its latest available values.
9. [ ] Selecting a card selects the same cell throughout the Control Room, visually marks it, opens or switches to `GET /api/events/<encoded-cell-id>`, closes the prior cell stream, and preserves the matrix's live updates.
10. [ ] The selected-cell terminal first displays retained events in chronological order and then appends live events. It distinguishes text, reasoning, tool activity, step boundaries, token usage, cost, and status where those fields exist; unknown valid JSON and plain-text events remain readable instead of being dropped.
11. [ ] The terminal is bounded to 500 rendered entries, follows new output only while the operator is already at the bottom, and provides local clear and pause-follow controls without deleting Redis history or stopping the running experiment.
12. [ ] The control pane shows the selected cell ID, current cell status, event-stream connection state, and opencode session ID when an event supplies one. If no session ID has yet been observed, it says so without preventing attachment.
13. [ ] A running cell offers an explicit read-only Attach/Watch action and an attached cell offers Detach. Queued and terminal cells can still be inspected through retained events, but no Send, Pause Process, Abort, or steering action is presented.
14. [ ] Matrix fetches and both SSE connections expose visible `connecting`, `live`, `reconnecting`, `disconnected`, and Redis-unavailable states as applicable. Transient failures retain the last known cards and transcript, recover without a page reload, and do not multiply active `EventSource` instances.
15. [ ] Empty queue, no selected cell, no retained events, malformed events, failed fetches, and Redis `503` responses each produce a useful inline state without uncaught JavaScript errors or a blank page.
16. [ ] Existing clients remain compatible: `GET /api/matrix`, `GET /api/status`, `GET /api/events/<cell_id>`, `GET /api/routing`, `POST /api/experiments`, and `GET /` retain their current paths and baseline semantics, and no existing Redis key is renamed, repurposed, or made unbounded.
17. [ ] If enqueue or clear controls are surfaced, they call only `POST /api/experiments`, disable while pending, report success or failure, and require explicit confirmation before clear with copy stating that running work is not cancelled.
18. [ ] At desktop width the spend, fleet, terminal, and control pane are simultaneously usable without overlapping content. At `375px` width they reflow into a readable sequence with no horizontal page overflow, clipped controls, or transcript text smaller than the surrounding interface requires.
19. [ ] Keyboard users can select cells and operate all controls with visible focus, connection and status changes are exposed as text or appropriate live regions, semantic controls have accessible names, and status/cost meaning does not rely solely on hue, glow, or motion.
20. [ ] Automated tests cover every additive Flask response or endpoint, existing endpoint compatibility, telemetry parsing and aggregation edge cases, replay deduplication, cell selection and stream replacement, the 500-entry transcript bound, and empty/error states; the repository's pytest suite passes.
