---
status: accepted
---
# Control Room Refresh: Pre-Implementation Audit

**Audit date:** 2026-08-23  
**Scope:** `apps/control_room/` only. This is a source audit, not a restyle. It makes no
network requests and does not start, stop, or alter the portal on port 8000.

## Audit Log

| Check | Result | Evidence |
| --- | --- | --- |
| Registered route count | **28 PASS** | `server.py:14-29` declares the count; `routes/__init__.py:22-35` registers all six route modules; registration calls total 28 at `routes/telemetry.py:220-229`, `flags.py:86-92`, `registry.py:89-94`, `design_sessions.py:155-165`, `claude_agents.py:279-291`, and `index.py:20-26`. |
| SSE endpoint count | **2 PASS** | `/api/status` and `/api/events/<cell_id>` are registered at `routes/telemetry.py:224-226`; each returns the shared SSE response at `telemetry.py:102,143`. |
| Browser module count | **6 PASS** | The ordered classic-script graph is loaded at `static/index.html:721-726`. |
| `innerHTML` / string-to-DOM rendering | **0 PASS** | The controller creates nodes and writes text with `textContent` through `element()` at `static/app.js:111-117`; semantic tables are built with DOM APIs at `app.js:1794-1817`; transcript rows do the same at `app.js:1175-1200`. |
| Dated-element list | **8 recorded** | Listed in [Visual System and Dated Elements](#visual-system-and-dated-elements). These are appearance/readability findings, not functional defects. |
| Contract completeness | **PASS** | The 28 registrations above have one corresponding inventory row below. The two SSE streams, their protocol event names, producer data variants, and all browser subscriptions are listed below. |
| Alternate-port boot | **PASS** | `FINOPS_PORT=8017 timeout 5 python3 apps/control_room/server.py` bound the worktree server at `127.0.0.1:8017`; port 8000 was not touched. The port override is implemented at `server.py:209-213`. |
| Focused regression suite | **123 passed** | `python3 -m pytest tests/test_admin_server.py tests/test_admin_frontend.py tests/test_admin_design_sessions.py tests/test_admin_claude_agents.py tests/test_admin_claude_agents_frontend.py tests/test_admin_supervisor.py tests/test_control_room_paths.py -q` completed in 0.80 seconds. |

## Contract Guardrails

The refresh must retain the following behavior exactly.

1. `server.py` is the composition root: it constructs the Flask application and injects a
   `ControlRoomServices` context into route registration at `server.py:114,198-206`.
2. All six route modules use the injected context rather than importing the server as a service
   locator, and registrations are centralized in `routes/__init__.py:22-35`.
3. Mutating routes are not cosmetic actions. Their shared admission layer enforces loopback/host,
   same-origin, JSON, body-size, and idempotency constraints; this is documented in
   `services/mutations.py:26-218` and used by telemetry mutations at
   `routes/telemetry.py:170-172,201-203`, supervisor mutations at `routes/flags.py:29-31,60-62`,
   and design-session mutations at `routes/design_sessions.py:30-32,60-62,93-96,105-107,123-125`.
4. The static shell has no build step. The scripts are classic, ordered globals, not ES modules:
   `index.html:24-26,721-726`. A visual implementation must preserve that load order unless the
   delivery architecture is deliberately migrated and regression-tested as a separate change.
5. The selected detail view owns at most one cell-event `EventSource`; a new one closes the old
   source through `replaceEventSource()` at `static/control-room-core.js:263-267` and selection
   transitions close an existing source at `static/app.js:1430-1433,1470-1473,1542-1544,1585-1588`.

## Route Inventory

### Static Shell

| Method and endpoint | Request | Success response | Frontend consumer |
| --- | --- | --- | --- |
| `GET /` | No body or query. | Serves `static/index.html`. Route: `routes/index.py:20-26`. | The document loads the six SPA scripts at `static/index.html:721-726`. |

### Telemetry and Queue: 6 Routes

| Method and endpoint | Request | Success response | Errors and frontend consumer |
| --- | --- | --- | --- |
| `GET /api/matrix` | No body or query. | JSON `{total, remaining_in_queue, queued, running, done, failed, timeout, completed, results_saved, cells, phases, stages:{execute,analyze,review}, telemetry}`. The legacy execute fields are intentionally retained while `stages` and `phases` are additive: `routes/telemetry.py:39-78`. | `503 {error:"redis_unavailable", cells:{}}` on Redis failure (`telemetry.py:41-48`). `loadMatrix()` fetches it, overlays fresher status messages, retains the last known state on failure, and renders fleet, stages, and selection: `static/app.js:1661-1703`; scheduled every 5 seconds at `app.js:2850,2856`. |
| `GET /api/status` | No body or query. SSE, not a finite JSON response. | Default SSE `message` frames contain the raw Redis status payload; expected producer data is `{cell_id:string,status:string}`. Sends `: ping` comments after the heartbeat interval: `routes/telemetry.py:80-102`. | No named error frame is emitted; Redis failures close the generator. One page-lifetime `EventSource` subscribes at `static/app.js:1762-1792`; only string `cell_id` and `status` are applied (`app.js:1770-1785`). |
| `GET /api/events/<cell_id>` | Path `cell_id`; no route-level validation, body, or query. SSE. | Replays `events_log:<cell_id>` oldest-first as default `message` frames, emits named `replay_complete` with `{cell_id}`, then relays live `events:<cell_id>` frames; sends heartbeat comments: `routes/telemetry.py:104-143`. | History-read failures are swallowed and live failures close the generator (`telemetry.py:114-141`). `connectSelectedStream()` creates the subscription and handles default messages, `replay_complete`, opening, and errors at `static/app.js:1379-1426`; parsing is in `static/control-room-core.js:147-220`. |
| `GET /api/routing` | No body or query. | `compute_routing(entries)` result, normally `{_meta:{tasks_analyzed,total_valid_entries}, per_task, strategies, routing_distribution}` from `routes/telemetry.py:145-159`. | Missing or malformed summary is a successful empty-state envelope `{_meta:{tasks_analyzed:0},per_task:[],strategies:{},note:"no results summary yet"}` (`telemetry.py:146-158`). Lazily loaded by `loadRouting()` at `static/app.js:1819-1863`, triggered from the Routing controls at `app.js:2580-2597` and first board activation at `static/shell.js:116-124`. |
| `POST /api/experiments` | Admitted JSON `{action:"enqueue"\|"clear"}` plus `Idempotency-Key`; shared admission rules apply. | `{ok:boolean, output:string}` after `scripts/enqueue.py` completes: `routes/telemetry.py:161-191`. | `400` for an unknown action (`telemetry.py:174-176`) plus shared mutation failures. `runQueueAction()` posts `{action}`, reports inline outcome, and refreshes the matrix: `static/app.js:1966-1992`; bound to Enqueue and the typed Clear Queue door at `app.js:2620-2654`. |
| `POST /api/queue/reinterleave` | Admitted JSON object plus `Idempotency-Key`; no route-specific fields. | `{ok:true,count,before:{by_provider,order,longest_provider_run},after:{by_provider,order,longest_provider_run}}`: `routes/telemetry.py:193-218`. | Shared mutation failures; queue/reinterleaving errors are surfaced by the helper. **No current frontend caller.** The only page API calls are enumerated in `static/app.js:1316,1667,1711,1765,1824,1883,1950,1975,2172,2202,2227,2256,2290,2321,2330,2382,2462,2680,2709,2728,2748,2778,2803,2827`. |

### Supervisor Flags: 3 Routes

| Method and endpoint | Request | Success response | Errors and frontend consumer |
| --- | --- | --- | --- |
| `GET /api/flags` | Optional query `limit`; invalid values become `50`, then clamp to `1..100`: `routes/flags.py:17-25`. | `{generated_at,source,degraded,warnings,flags}` from the supervisor service: `flags.py:17-25`. | Service supplies the status, including its `503` degraded envelope. `loadSupervisorFlags()` requests `?limit=50`, retains prior rows on error, and renders loading/degraded/empty states: `static/app.js:1707-1760`; runs every 5 seconds at `app.js:2851,2857`. |
| `POST /api/flags/<session_id>/steer` | Admitted JSON `{cell_id:nonempty string,prompt:nonblank string <=12000}` plus `Idempotency-Key`: `routes/flags.py:27-56`. | `{action:"steer",admitted:true,session_id}`. | `400` for invalid fields (`flags.py:33-40`), plus authorization, upstream, and shared mutation failures. `submitSupervisorSteer()` preserves retry identity and posts it at `static/app.js:2064-2099`; the form is in `static/index.html:234-242`. |
| `POST /api/flags/<session_id>/interrupt` | Admitted JSON `{cell_id:nonempty string,confirmation:"INTERRUPT <session_id>"}` plus `Idempotency-Key`: `routes/flags.py:58-84`. | `{action:"interrupt",accepted:true,session_id}`. | `400` for invalid fields or confirmation (`flags.py:64-69`), plus authorization, upstream, and shared mutation failures. The browser opens a local typed-confirmation door at `static/app.js:2101-2119` and posts exactly that confirmation at `app.js:2121-2151`; markup is `static/index.html:247-262`. |

### Registry: 2 Routes

| Method and endpoint | Request | Success response | Errors and frontend consumer |
| --- | --- | --- | --- |
| `GET /api/registry` | Optional query `record_type`, `lifecycle`, and lexicographic `since`: `routes/registry.py:20-49`. | `{registry:[manifest rows],count:number}` after file-backed filtering: `registry.py:35-49`. | No explicit error response; unavailable cache input yields the registry service's empty data. `loadRegistry()` builds the query from three controls at `static/app.js:1871-1891`; `renderRegistryTable()` displays it at `app.js:1893-1935`. |
| `GET /api/registry/<entity_id>` | Path `entity_id`. | `{record}` and, for an actuation with a resolvable cause, `{record,causes_record}`: `routes/registry.py:51-87`. | `404 {error:"not_found",entity_id}` and `409 {error:"ambiguous",entity_id,count,records}` at `registry.py:67-80`. `loadRegistryLineage()` renders record/cause JSON or an error state at `static/app.js:1943-1964`; table-row activation occurs at `app.js:1914-1928`. |

### Design Sessions: 7 Routes

| Method and endpoint | Request | Success response | Errors and frontend consumer |
| --- | --- | --- | --- |
| `GET /api/design-sessions` | No body or query. | Service-owned `{sessions:[public session],workdirs:[{key,label}]}`: `routes/design_sessions.py:21-26`. | Manager errors use `_design_error`. `loadDesignSessions()` receives rows and approved workdirs at `static/app.js:2169-2197`; it runs every 10 seconds at `app.js:2852,2858`. |
| `POST /api/design-sessions` | Admitted JSON `{kind:"workflow"\|"experiment",intent:string <=12000,model:string,workdir:string}` plus `Idempotency-Key`: `routes/design_sessions.py:28-49`. | `201 {ok:true,session}`. | `400` for invalid intent (`design_sessions.py:34-39`), manager, and shared admission errors. `startDesignSession()` posts it at `static/app.js:2245-2276`; launch controls are `static/index.html:486-521`. |
| `GET /api/design-sessions/<portal_id>/spec` | Path `portal_id`. | Draft-state object: `{session_id,revision,draft_state,yaml,validation:{valid,errors,validated_at},matrix,saved,capabilities:{save,run,enqueue,reason}}`: `routes/design_sessions.py:51-56`; the displayed fields are consumed at `static/app.js:1309-1371,888-928`. | `_design_error`, usually including not found or upstream errors. Draft/YAML validation is represented in the successful draft body rather than HTTP failure. The selected design session fetches it immediately and every 3 seconds at `app.js:1509-1511`. |
| `POST /api/design-sessions/<portal_id>/input` | Admitted JSON `{prompt:string <=12000,delivery:"queue"\|"steer"}` plus `Idempotency-Key`: `routes/design_sessions.py:58-89`. | Manager response, wrapped by `jsonify`; expected admission fields include `{ok,admitted,delivery,response}`. | `400` invalid prompt or delivery (`design_sessions.py:64-78`) plus manager/shared errors. `submitDesignInput()` posts queue or steer at `static/app.js:2278-2305`. |
| `POST /api/design-sessions/<portal_id>/interrupt` | Admitted empty JSON object plus `Idempotency-Key`: `routes/design_sessions.py:91-101`. | Manager response, expected `{ok:true,accepted:true,response}`. | Manager/shared errors. Bound at `static/app.js:2453-2474`. |
| `POST /api/design-sessions/<portal_id>/save` | Admitted JSON `{filename:string,overwrite?:boolean}` plus `Idempotency-Key`: `routes/design_sessions.py:103-119`. | `{ok:true,path,revision,content}`; conflict result is returned as `409` when `result.conflict` is truthy. | `400` for nonboolean `overwrite` (`design_sessions.py:109-110`), `409` conflict, manager/shared errors. `saveSpec()` retries an operator-confirmed overwrite at `static/app.js:2307-2345`. |
| `POST /api/design-sessions/<portal_id>/run` | Admitted JSON requiring `{goal,model,workdir,timeout:int,commit:bool}`; optional `backend`, `thinking_budget_tokens:int`, and `output_token_limit:int`: `routes/design_sessions.py:121-153`. | `202` manager launch object, expected `{ok:true,execution_id,stream_id,launch:{spec,goal,model,workdir,timeout,backend,thinking_budget_tokens,output_token_limit,commit}}`. | `400` for missing/type-invalid explicit launch fields (`design_sessions.py:127-138`) plus manager/shared errors. `runWorkflow()` confirms launch parameters then posts at `static/app.js:2348-2396`. |

### Claude Background Sessions: 9 Routes

| Method and endpoint | Request | Success response | Errors and frontend consumer |
| --- | --- | --- | --- |
| `GET /api/claude-agents` | No body or query. | `{agents,workdirs:[{key,label}]}`: `routes/claude_agents.py:32-49`. | Supervisor roster unavailability deliberately returns `200 {error:"supervisor_unavailable",agents:[],workdirs}` (`claude_agents.py:41-49`). `loadClaudeAgents()` polls it at `static/app.js:2199-2222,2853,2859`. |
| `GET /api/claude-agents/<session_id>/logs` | Validated path ID matching the server `SESSION_ID_PATTERN`. | Plain-text tail, bounded to 65,536 bytes, with `X-Claude-Agent-Log-Truncated` and `X-Claude-Agent-Log-Note`: `routes/claude_agents.py:51-66`. | `400 {error:"invalid session id"}` or `502 {error,code}` (`claude_agents.py:53-58`). Only external-agent selection calls it via `fetch(...).text()` at `static/app.js:2797-2814`. |
| `GET /api/claude-agents/daemon` | No body or query. | Daemon status JSON, normally `{running,...}`: `routes/claude_agents.py:68-74`. | Client failure is a successful `{running:false,error,code}` envelope (`claude_agents.py:70-74`). `loadClaudeAgentDaemon()` polls it at `static/app.js:2224-2233,2854,2860`. |
| `POST /api/claude-agents` | Claude mutation JSON `{task:nonblank string <=12000,workdir:approved key,model?:string,advisor?:"fable"\|"opus"\|"sonnet"\|full model ID}` plus `Idempotency-Key`: `routes/claude_agents.py:76-125`. | `201 {ok:true,id}`. | `400` local field errors (`claude_agents.py:83-109`), `502` malformed client ID, and shared Claude mutation errors. Start form posts at `static/app.js:2668-2700`. |
| `POST /api/claude-agents/<session_id>/stop` | Claude mutation empty JSON plus `Idempotency-Key`; server rechecks ownership. | `{ok:true,id,note,result}`: `routes/claude_agents.py:127-146`. | Invalid ID, ownership, client, and shared errors. Bound at `static/app.js:2702-2720`. |
| `POST /api/claude-agents/<session_id>/respawn` | Claude mutation empty JSON plus `Idempotency-Key`; server rechecks ownership. | `{ok:true,id,result}`: `routes/claude_agents.py:148-162`. | Invalid ID, ownership, client, and shared errors. Bound at `static/app.js:2722-2739`. |
| `POST /api/claude-agents/<session_id>/rm` | Claude mutation empty JSON plus `Idempotency-Key`; server rechecks ownership. | `{ok:true,id,note,result}`: `routes/claude_agents.py:164-190`. | Invalid ID, ownership, client, and shared errors. Bound at `static/app.js:2741-2765`. |
| `POST /api/claude-agents/<session_id>/steer` | Claude mutation JSON `{prompt:nonblank string <=12000,model?:string,advisor?:allowed value}` plus `Idempotency-Key`; ownership check happens inside the idempotent action: `routes/claude_agents.py:192-256`. | `{ok:true,id,resumed_from,note}`. | Local, ownership, malformed client ID, and shared errors. Bound at `static/app.js:2767-2792`. |
| `POST /api/claude-agents/daemon/stop` | Claude mutation JSON `{keep_workers:boolean}` plus `Idempotency-Key`: `routes/claude_agents.py:258-277`. | `{ok:true,keep_workers,result}`. | `400` when `keep_workers` is missing/nonboolean (`claude_agents.py:265-270`) plus client/shared errors. The browser uses one or two explicit `confirm()` dialogs before posting at `static/app.js:2816-2842`. |

## SSE Inventory

### Protocol Events

| Stream | SSE event name | Data fields | Browser subscription |
| --- | --- | --- | --- |
| `/api/status` | Default `message` | Raw Redis data. The browser accepts `{cell_id:string,status:string}` only. | `new EventSource("/api/status")`, `onmessage`, and `onerror`: `static/app.js:1762-1792`. |
| `/api/status` | `ping` comment | No data fields; literal `: ping`. This is an SSE comment, not a browser event. | No browser listener; generated at `routes/telemetry.py:89-94`. |
| `/api/events/<cell_id>` | Default `message` | Raw retained or live event JSON/text. The browser parser accepts non-JSON as a `RAW` transcript row and object payloads as normalized rows. | `source.onmessage` at `static/app.js:1409-1411`, passed to `receiveEvent()` at `app.js:1267-1295`. |
| `/api/events/<cell_id>` | `replay_complete` | `{cell_id}`. | `addEventListener("replay_complete", ...)` turns off replay accounting and enables the brief history/live de-duplication window: `static/app.js:1398-1408`. |
| `/api/events/<cell_id>` | `ping` comment | No data fields; literal `: ping`. Not a browser event. | No listener; generated at `routes/telemetry.py:129-135`. |

The shared SSE response declares `text/event-stream`, disables cache and proxy buffering, and
keeps the connection alive in `services/telemetry.py:20-30`. Neither endpoint emits a named
SSE `error` event; connection failure is represented by generator closure and the browser
`EventSource.onerror` paths at `static/app.js:1412-1423,1787-1791`.

### Event-Data Variants on `/api/events/<cell_id>`

These are `data.type` values, not SSE event names. The route is transparent (`routes/telemetry.py:121-132`), so producers rather than Flask define the event-data schema. The browser's complete normalization vocabulary is at `static/control-room-core.js:147-220`.

| `data.type` | Fields consumed or emitted | Source and browser rendering |
| --- | --- | --- |
| `reasoning` | `{type:"reasoning",part:{type:"reasoning",text},sessionID?}` | Claude adapter relay: `src/agentic_dynamics/adapters/claude_adapter.py:88-185`; shown as `THINK` from `part.text` at `static/control-room-core.js:173-175`. |
| `text` | `{type:"text",part:{type:"text",text},sessionID?}` | OpenCode relay: `src/agentic_dynamics/adapters/opencode.py:314-329`; shown as `AGENT` at `control-room-core.js:180-182`. |
| `tool_use` or `tool` | `{type,part:{tool|name,callID?,state:{status,input,output}},sessionID?}` | Claude relay source above; browser shows tool/status/input and puts output in collapsed details at `control-room-core.js:183-197`. |
| `step_start` | `{type:"step_start",part:{type:"step-start",step?|id?},sessionID?}` | Adapter relay conventions; browser shows a `STEP START` row at `control-room-core.js:198-201`. |
| `step_finish` | `{type:"step_finish",part:{type:"step-finish",tokens:{input,output,reasoning,total,cache?},cost?,text?},sessionID?}` | Workflow relay: `src/agentic_dynamics/runtime/workflow_runner.py:647-661`; browser extracts token/cost telemetry at `static/control-room-core.js:74-125` and renders it at `control-room-core.js:202-211`. |
| `operator` | `{type:"operator",text,delivery,admitted?,sessionID}` | Design-session manager emits it at `apps/control_room/services/design_sessions.py:336-339,427-430`; rendered as queued or steered at `static/control-room-core.js:176-179`. |
| `session_status` | `{type:"session_status",status,sessionID}` | Design-session relay: `services/design_sessions.py:83-117`; not specially recognized, so it becomes generic `EVENT` data at `static/control-room-core.js:213-219`. |
| `relay_error` | `{type:"relay_error",message,sessionID}` | Design-session relay: `services/design_sessions.py:364-387`; generic `EVENT` in the current parser. |
| `run_error` | `{type:"run_error",message}` | Design-session workflow relay: `services/design_sessions.py:776-790`; generic `EVENT` in the current parser. |
| `raw` | `{type:"raw",data}` | OpenCode client fallback: `apps/control_room/clients/opencode_client.py:144-176`; generic `EVENT` because it is valid JSON. |
| Other native type | `{type:<native type or "native_event">,sessionID,native:<original event>}` | Design-session relay: `services/design_sessions.py:83-117`; generic `EVENT` with full payload in details at `static/control-room-core.js:213-219`. |
| Malformed/non-object payload | No reliable fields. | The parser preserves it as a `RAW` row rather than discarding it: `static/control-room-core.js:32-44,147-161`. |

## JavaScript Architecture

### Module Graph

```text
index.html
  -> control-room-core.js       pure parser, telemetry, bounded-data helpers
  -> keyed-list.js              generic keyed DOM reconciliation/write-on-change helpers
  -> board-fleet.js             pure lifecycle/attention vocabulary, filtering, signatures
  -> shell.js                   boards, theme, density, system sheet, shell mirrors
  -> detail-sheet.js            detail opening, focus, modal behavior, drag dismissal
  -> app.js                     application state, fetch/SSE transport, rendering, actions
```

The graph and required order are explicit in `static/index.html:24-26,721-726`. Each module
exports a namespace on `window`: core at `control-room-core.js:269-285`, keyed list at
`keyed-list.js:134-138`, fleet at `board-fleet.js:186-204`, shell at `shell.js:374-390`, and
detail at `detail-sheet.js:303-308`. `app.js` consumes all of them at `static/app.js:10-32`.

### Responsibilities and State Flow

| Module | Responsibility | Evidence |
| --- | --- | --- |
| `index.html` | Semantic shell: command rail, destination nav, five boards, one transversal detail surface, and System overflow. | `static/index.html:55-126,128-350,356-610,615-726`. |
| `control-room-core.js` | Pure, browser-free status normalization, raw-event parsing, transcript normalization, telemetry reconciliation, cost burn calculation, sorting, and EventSource replacement. | `static/control-room-core.js:13-281`. |
| `keyed-list.js` | Reconciles stable row keys without replacing unchanged DOM, and avoids same-value DOM writes. | `static/keyed-list.js:31-65,88-132`. |
| `board-fleet.js` | Keeps lifecycle and supervisor-attention vocabularies structurally separate, then supplies facet filtering, ordering support, counts, and render signatures. | `static/board-fleet.js:44-90,100-199`. |
| `shell.js` | Owns board visibility, persisted theme and density, single-region reparenting, System sheet, scrim, and mirrored telemetry text; intentionally fetches nothing. | `static/shell.js:4-22,61-148,182-245,288-390`. |
| `detail-sheet.js` | Owns detail presentation and focus only: desktop dock/mobile sheet, focus return/trap, Escape, and drag-to-dismiss; intentionally fetches and streams nothing. | `static/detail-sheet.js:4-22,68-135,137-307`. |
| `app.js` | Owns the authoritative in-page state and mixes transport, all data rendering, transient selection state, local controls, queue/design/agent actions, and timers. | State object `static/app.js:34-104`; initial boot and six recurring timers `app.js:2845-2862`. |

The state flow is: matrix snapshot -> `state.cells/stages/phases/telemetry` -> keyed fleet/stage
renderers; page-level status SSE -> `statusOverrides` -> fleet render; selected event SSE ->
transcript rows, live telemetry overlays, and selection render. The implementation is visible at
`static/app.js:1628-1703,1762-1792,1267-1295`. Design, supervisor, registry, and Claude data
follow the same fetch -> state -> renderer pattern at `app.js:1309-1371,1707-1760,1819-1964,2169-2233`.

### Rendering Approach

1. **Safe DOM construction:** There is no `innerHTML`, `outerHTML`, or `insertAdjacentHTML` use.
   The common `element()` helper writes via `textContent` (`static/app.js:111-117`); server data
   is therefore not parsed as markup.
2. **Keyed in-place lists:** Fleet cards, flags, design rows, and Claude cards are reconciled by
   stable identity at `static/app.js:510-537,730-736,844-850,1033-1039`. This protects focus,
   animation continuity, text selection, and scroll anchoring under polls as the keyed-list
   contract explains at `static/keyed-list.js:4-25`.
3. **Deliberate full replacements:** Pipeline-stage cards, routing/registry content, form
   options, and the transcript use `replaceChildren()` because their rendered units are not keyed
   (`static/app.js:580-590,1155-1173,1794-1817,1819-1863,1871-1964,2154-2167`). This is safe from
   injection but not equally cheap or focus-stable.
4. **Delegated interaction:** Selection is delegated at list/container level, avoiding a growing
   listener count and rebinds on dynamic cards: `static/app.js:2478-2505`; detail opening is
   also document-delegated at `static/detail-sheet.js:241-250`.

### Known Architecture Smells

| Priority | Finding | Evidence and refresh implication |
| --- | --- | --- |
| High | `app.js` is a 2,862-line god controller with state, API client, renderer, selection lifecycle, and mutation handlers in one IIFE. | It holds the entire state at `static/app.js:34-104`, rendering from `app.js:197-1173`, transport from `app.js:1309-2233`, controls from `app.js:2412-2843`, and boot/timers at `app.js:2845-2862`. A UI refresh should avoid adding more behavior here; extract visual board renderers or presentation adapters only after locking the API/SSE tests. |
| High | Selection reset logic is copied across cell, design, supervisor, and Claude selectors. | Repeated source closing and transcript/replay/map resets occupy `static/app.js:1428-1464,1466-1512,1514-1572,1581-1615`. A new visual selection type would be regression-prone. Centralize only if the refresh needs a new detail state. |
| Medium | All modules communicate through globals and implicit script order. | Classic ordered loading is required at `static/index.html:24-26,721-726`; module dependencies are read from `window` at `static/app.js:10-32` and `shell.js:24`. A missing/reordered file fails at runtime without import diagnostics. Preserve order for this work. |
| Medium | The transcript recreates up to 500 rows on every received event. | Bound is `MAX_TRANSCRIPT_ROWS = 500` at `static/app.js:12`; `renderTranscript()` clears and rebuilds at `app.js:1154-1173`, called for every unpaused event at `app.js:1284-1291`. This can produce layout/GC pressure and lose text selection in a busy stream. |
| Medium | Polls have no abort/timeout/visibility policy. | Six intervals are always scheduled at `static/app.js:2856-2861`; fetches do not pass `AbortSignal` or an application timeout (for example `app.js:1667,1711,1824,1883,2172,2202,2227`). Matrix and flag have in-flight guards, but design/Claude/daemon loads do not. Visual refresh must not increase polling or add duplicate subscriptions. |
| Low | The server serves a queue reinterleave control route without a UI affordance. | Route implementation and registration: `routes/telemetry.py:193-229`; no browser invocation appears in the API call sites listed in the route inventory. This is a product-surface gap, not a reason to silently add high-impact UI control during a visual-only refresh. |

## Visual System and Dated Elements

### Current System

The existing design is coherent and technically disciplined, but its visual language is
utilitarian developer-console rather than premium operations product.

| System area | Current implementation | Evidence |
| --- | --- | --- |
| Color | Dark navy/blue-gray layered surfaces, indigo interaction accent, cyan/green/red/amber lifecycle colors, and rose/amber attention colors. Light theme mirrors the tokens. | `static/style.css:37-67,110-134`. |
| Type | `Inter`/system sans for UI, system mono for IDs, metrics, transcripts, and tables. Headings use 11-13px uppercase with letter spacing; the hero metric is only 24px. | `static/style.css:76-84,166-187,191-213`. |
| Spacing and shape | Four-pixel scale, 4/8/14px radii, 44px touch targets, a 48px rail, 56px mobile tab bar, and 92px desktop nav rail. | `static/style.css:68-107`. |
| Layout | Mobile-first sticky command rail + bottom nav, then desktop left rail and optional 420/460px detail column. | `static/style.css:284-356,360-430,1665-1787`. |
| Motion | 120ms interaction / 200ms sheet timing; only running cards pulse; reduced motion suppresses animation and smooth scrolling. | `static/style.css:91-94,1630-1633,1817-1845`; drag behavior honours reduced motion at `static/detail-sheet.js:150-165,195-211`. |
| Visual semantics | Lifecycle and supervisor attention are separate vocabularies with glyph + word + color, not color alone. | `static/board-fleet.js:11-26,44-66`; token/selector split `static/style.css:28-32,253-280,892-895`. |

### Dated-Element List

1. **Terminal-command styling is over-applied.** Nearly all headings are tiny uppercase,
   letter-spaced labels (`static/style.css:166-175,191-204`), while the product name itself is
   uppercase at `static/index.html:63-66`. This makes the hierarchy read as an internal admin
   console rather than a composed premium dashboard. Keep mono for provenance, IDs, and live
   telemetry; promote a calmer display hierarchy for page/board titles.
2. **Text-symbol iconography is inconsistent and visually brittle.** Navigation and controls use
   glyph characters such as `▦`, `$`, `▲`, `◉`, `⇄`, `⚙`, `◐`, and `✕`
   (`static/index.html:80-89,99-125,166-169`). Font-dependent symbols vary in weight,
   alignment, and perceived polish across platforms. Replace decoratives with a single SVG icon
   family while retaining text labels and accessible names.
3. **Nearly every information unit is a bordered rectangle.** Cards, stages, forms, panels,
   tables, and sheets repeat one-pixel borders and small radii (`static/style.css:476-485,
   581-602,713-721,899-909,1091-1110,1399-1407`). The consistent rule is maintainable, but
   flattening all depth into equal chrome obscures primary versus secondary information.
4. **The persistent command rail duplicates abbreviated metrics without hierarchy.** It mirrors
   Spend, Burn, Running, and Redis in small text (`static/index.html:73-78`,
   `static/style.css:317-344`) while the Status board is the canonical analytical view. On a
   dense desktop, the top rail reads like an old status bar rather than an executive signal strip.
5. **Fleet cards spend scarce space on weakly meaningful microcharts.** Every card includes a
   12-sample token/cost sparkline (`static/app.js:274-321,399-401`), constrained to 22px tall
   (`static/style.css:655-660`). At matrix scale, the marks cannot support comparison and compete
   with cell identity/status. Preserve the data but show it only on hover, selection, or a
   meaningful aggregate/risk condition.
6. **Pills and all-caps badges proliferate.** Status, phase, ownership, validation, connection,
   attention count, and read/act states each use compact outlined or rounded treatments
   (`static/style.css:636-646,757-769,825-834,974-986,1467-1488,1520-1529`). They communicate
   state but create visual noise when a row/card carries several simultaneously.
7. **The System surface is treated as an overflow drawer despite holding a dense data product.**
   Registry is hidden behind the gear/System sheet (`static/index.html:615-686`) and uses the
   same generic drawer style as Routing (`static/style.css:998-1083`). This makes canonical
   state feel incidental and forces a wide table into a modal context.
8. **Browser-native confirmation dialogs interrupt the composed visual language.** Save overwrite,
   workflow launch, design interrupt, enqueue, stop/remove agent, and daemon stop use
   `window.confirm()` (`static/app.js:2324-2330,2375,2453-2457,2620-2623,2702-2705,2741-2744,
   2818-2822`), whereas queue clear and supervisor interrupt already use considered typed doors
   (`app.js:2101-2151,2624-2654`). A premium refresh should converge presentation, while keeping
   all server confirmation and idempotency behavior unchanged.

### Data That Is Present but Hard to Read

| Surface | Current data treatment | Readability issue | Direction for refresh |
| --- | --- | --- | --- |
| Matrix / Fleet | One responsive card per cell with status, full compound ID, phase, latest step cost, and sparkline; filters are only All/Running/Risk plus free-text search. | Card density is governed by viewport rather than operator task. Full IDs dominate; comparative cost/risk/age are not scannable across a large grid. | Create a density ladder that preserves each card's button and stable DOM identity: executive compact rows/table at high density, richer cards at lower density, and a clear selected/risk state. Do not replace keyed reconciliation. |
| Flags | Full-board list with a clamped reason, model, time, source provenance, and review availability. | Clamping protects list density but can hide the causal clause; all flags share similar card weight and lack a scan-friendly priority/time axis. | Add visible severity/recency hierarchy and an inspect affordance; retain the current row selection and the `Supervisor flags. You decide.` boundary at `static/index.html:467-474`. |
| Routing | Lazy table of per-task recommendation and strategy simulation. | It begins hidden and requires a toggle even when its board is active (`static/index.html:588-610`); the table exposes no uncertainty, sample count per recommendation, or direct explanation in the primary scan line. | Keep lazy data fetch, but show a premium empty/skeleton/summary state and expose confidence/provenance before dense detail. Do not invent signals the API does not provide. |
| Sessions | Design launchers, recent designs, daemon state, Claude start form, and Claude roster share one long board. | Two different lifecycle models and high-impact controls compete for attention; ownership, daemon scope, and actions are visually adjacent to routine session browsing. | Separate session observability from controlled actions within the existing board/route model, and retain ownership cues derived from server data (`static/app.js:930-947`). |

## Experience, Accessibility, and Performance Gaps

### Loading, Empty, and Error States

| Surface | Current state coverage | Gap |
| --- | --- | --- |
| Fleet | Initial three skeleton cards (`static/index.html:396-400`), no-cells/no-filter empty copy (`static/app.js:463-506`), and last-known data on matrix failure (`app.js:1661-1703`). | It has no visually distinct offline/error panel inside the matrix; connection meaning is split between rail, age text, and cards. |
| Flags | Loading, healthy-empty, degraded-empty, retained-on-error states are differentiated (`static/app.js:675-737`). | Stronger than other boards, but the error is styled as a text state only; stale timestamp and next-refresh expectation are not made explicit. |
| Routing / Registry | Explicit loading, empty, and unavailable messages (`static/app.js:1819-1863,1871-1891,1893-1964`). | Generic `error-state` wording does not distinguish response failure, no source data, stale cached data, or malformed content. |
| Design sessions | Has initial empty markup (`static/index.html:494-497`) and an error replacement (`static/app.js:2169-2197`). | On a transient failed poll, the keyed prior list is wholesale replaced by an error paragraph, losing recoverable context and focus continuity. |
| Claude roster / daemon | Initial loading copy (`static/index.html:582-584`), supervisor-unavailable empty copy (`static/app.js:1016-1031`), daemon falls back to `NOT RUNNING` (`app.js:1056-1061,2224-2233`). | Transport failure, absent supervisor, and an actually stopped daemon are visually collapsed or easily confused. |
| Selected transcript | Clear initial, connecting, and no-history states (`static/app.js:1154-1173`) plus reconnect/unavailable announcements (`app.js:1412-1423`). | It has no persistent, visible stream-error/retry summary inside the feed after live events resume; a transient live region announcement can be missed. |

### Responsiveness and Accessibility

1. **Strong foundations already exist.** The viewport is mobile-aware (`static/index.html:31`),
   inactive boards use `hidden` rather than offscreen-only CSS (`index.html:50-54`), touch
   targets are tokenized at 44px (`static/style.css:97-102,1342-1352`), dense tables scroll
   horizontally (`style.css:1031-1059`), focus has one visible accent treatment
   (`style.css:1819-1825`), and reduced motion is respected (`style.css:1836-1845`).
2. **Mobile detail is focus-trapped, but System is not.** `detail-sheet.js` traps Tab only while
   the detail sheet is modal (`static/detail-sheet.js:78-101,267-270`). The System sheet opens a
   scrim and moves focus to its close button (`static/shell.js:196-223,230-245`), but has no
   `role="dialog"`, `aria-modal="true"`, or focus trap in markup/logic (`static/index.html:622-716`,
   `static/shell.js:182-245`). Keyboard users can navigate to controls behind an open modal.
3. **Clickable table rows are semantically fragile.** Registry rows use `tr tabindex="0"
   role="button"` (`static/app.js:1914-1928`). This is keyboard-supported but does not provide a
   native button target within the table and can be inconsistently announced. A refresh should
   use a real link/button in a cell or adopt an explicit grid interaction model.
4. **The desktop detail layout relies on `:has()`.** The third column appears only through
   `.app-shell:has(.detail-surface[data-open="true"])` at `static/style.css:1755-1761`. Modern
   support is broad, but there is no layout fallback if an embedded/legacy browser lacks `:has`.
5. **Detail control order changes visually on mobile.** Transcript controls move after transcript
   content with CSS `order` (`static/style.css:1639-1659`), preserving DOM reading order but
   making visual and screen-reader order differ. This is intentional, but a refresh should avoid
   adding time-sensitive controls that require visual and assistive technology order to match.

### Performance Risks

1. Fleet/flags render every five seconds and design/Claude/daemon every 10/10/15 seconds;
   `tick()` also renders rail and flags every second (`static/app.js:2398-2410,2856-2861`).
   Keyed list writes reduce list churn, but `tick()` still recalculates/render-path work even when
   no data changes.
2. Event transcripts rebuild every visible row for each unpaused stream message
   (`static/app.js:1154-1173,1284-1291`). Keep the 500-entry safety bound but consider keyed or
   append-only rendering with retention trimming before adding visual row complexity.
3. Each fleet card can render an SVG with up to 12 bars plus a polyline (`static/app.js:274-321`),
   and every card is considered on every fleet render (`app.js:480-543`). The card signature
   avoids unnecessary redraws, but a large active matrix plus live telemetry remains a likely
   paint hot path.
4. There is no `visibilitychange` pause/backoff, cancellation, or request timeout for polling
   (`static/app.js:1661-1703,1707-1760,2169-2233,2856-2861`). A refresh must not mask a stale UI
   with more animation; stale state should be explicit.

## Premium Refresh Direction

This audit does not implement the following direction; it establishes boundaries for the next
phase.

1. **Make the command rail a quiet instrument panel.** Use one strong run-health statement and
   two or three prioritized metrics; keep the existing canonical source elements and
   `data-mirror` mechanism rather than creating competing state writers (`static/shell.js:288-328`).
2. **Rebalance hierarchy, not semantics.** Retain the current dark/light tokens, lifecycle versus
   attention separation, words, and glyph/text accessibility contract. Improve depth, scale, and
   contrast through typography, surface hierarchy, and a restrained visual rhythm rather than
   introducing more colors.
3. **Treat Fleet as an operating surface.** Preserve its stable keyed cards and button semantics,
   but provide a compact comparison mode that prioritizes status, phase, age, cost, and selected
   risk. Do not turn current model/cell payloads into invented business metrics.
4. **Unify confirmation presentation.** Replace browser `confirm()` dialogs with in-product,
   accessible confirmation surfaces only if every existing typed phrase, explicit acknowledgement,
   server validation, and `Idempotency-Key` behavior remains intact.
5. **Make state quality visible.** Every premium surface needs distinct initial loading, live,
   stale/degraded, empty, and hard-error treatment. Existing status values and source provenance
   are the authority; the refresh must not infer health from animation.
6. **Repair modal semantics as part of visual polish.** Make the System sheet a true modal on
   small screens, with a label, focus containment, Escape behavior, and focus return matching
   the existing detail sheet.

## Refresh Acceptance Criteria

The implementation phase should be considered **PASS** only when all conditions below hold.

1. All 28 routes register unchanged, retain methods/status codes/payload shape, and every current
   frontend request still targets the same endpoint with the same request shape.
2. `/api/status` and `/api/events/<cell_id>` retain default-message handling, `replay_complete`,
   heartbeat comments, and the one-selected-stream rule.
3. The static page continues to work when launched in this worktree on a port other than 8000;
   no validation action stops or interrupts the live portal.
4. Fleet, flags, design rows, and Claude rows retain keyed reconciliation and delegated selection;
   no untrusted API field is introduced through HTML-string interpolation.
5. Light/dark, 320px-class phone width, 760px transition, 1200px desktop, keyboard-only use,
   reduced motion, loading, empty, degraded, and error states receive visual QA.
6. System-sheet modal semantics, focus order, modal dismissal, horizontal table access, and
   transcript follow/pause behavior are manually tested.
7. The refresh does not add API polling, EventSources, or a second source of truth for mirrored
   telemetry.

**Audit result: PASS.** The server/API/SSE contract is fully mapped; the SPA has a stable,
security-conscious rendering foundation and identifiable visual, accessibility, and performance
targets for a no-regression premium refresh.
