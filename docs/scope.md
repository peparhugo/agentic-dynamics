# Live Design Sessions Scope

## 1. Problem

The Control Room can observe experiment cells, but it cannot host the design work that precedes them. An operator must leave the command rail to start an OpenCode conversation, draft YAML by hand, run validation separately, and then return to the portal to run or monitor work. This breaks the operational chain from intent to an executable `ExperimentSpec` and makes schema or requires/produces errors easy to discover too late.

This feature extends the existing Control Room rather than replacing it. It adds two portal-managed, live OpenCode session kinds to the existing terminal and session-control panes:

1. A **workflow design session** starts from an operator's feature description and directs the agent to maintain an unsaved `ExperimentSpec` whose `workflow.kind` is `agent_task` and whose workflow parameters contain phases.
2. An **experiment design session** starts from an operator's research question and directs the agent to maintain a factorial `ExperimentSpec` containing factors, rules, metrics, and a comparison. A valid draft also receives a live cell preview from `experiment_matrix`.

Both kinds use a server-owned temporary YAML draft as the exchange boundary between the agent and the portal. The backend parses and calls `validate_spec` whenever the UI requests the latest draft state, so syntax, construction, and validation errors can be shown beside the live transcript before Save or Run is enabled. A temporary file is chosen over scraping YAML from streamed prose because file content has a stable, testable boundary and OpenCode already operates in the repository workspace.

The feature also changes the meaning of interactivity narrowly. Existing experiment-cell attachments remain observational. A portal-created design session may show Send and Steer controls because the investigated OpenCode API has an explicit, acknowledged backend path for both operations. This avoids implying that the existing `opencode run` subprocesses can be controlled.

## 2. Investigated Integration Facts

### Existing Control Room

- The Flask app already serves the fleet snapshot, two SSE feeds, routing, queue actions, and the static shell at `GET /api/matrix`, `GET /api/status`, `GET /api/events/<cell_id>`, `GET /api/routing`, `POST /api/experiments`, and `GET /` [admin/server.py:225-253, 256-322, 325-362]. The new feature must be additive because these paths are the running Control Room contract.
- Cell-event SSE subscribes before replaying `events_log:<cell_id>`, emits retained events oldest-first, sends a named `replay_complete` boundary, and then relays `events:<cell_id>` with heartbeats [admin/server.py:282-322]. Reusing this relay for a design-session stream preserves the current Redis/SSE behavior and frontend transcript machinery.
- The frontend already renders the selected session identity from streamed `sessionID` values and labels the pane's current action as Watch, Detach, or retained-history inspection [admin/static/app.js:311-345]. Selecting another card closes the prior `EventSource`, clears cell-local transcript state, and opens only the selected stream [admin/static/app.js:531-558].
- Detach currently closes only the browser `EventSource`; it sends no process-control request [admin/static/app.js:560-569]. That behavior remains unchanged for ordinary experiment cells.
- Known and unknown events are rendered with DOM nodes and `textContent`, so a native OpenCode event adapter can preserve unfamiliar event data without injecting event payloads as HTML [admin/static/app.js:348-379; admin/static/control-room-core.js:144-217].

### ExperimentSpec and execution

- `ExperimentSpec.from_yaml` uses `yaml.safe_load` and `from_dict`, while `to_yaml` writes to the caller-provided path without creating a parent directory or restricting the destination [src/instrument/experiment_spec.py:325-356]. A portal save endpoint must therefore enforce its own filename, directory, and atomic-write rules.
- `validate_spec(spec: ExperimentSpec) -> list[str]` accumulates structural and requires/produces errors; an empty list means valid [src/instrument/experiment_spec.py:406-446]. `validate_rules` makes ledger fields plus measurement-rule outputs available and reports an unmet requirement with an "Instrument it first" error [src/instrument/experiment_spec.py:367-403]. The portal must display these returned strings verbatim rather than inventing a second validator.
- `experiment_matrix(spec)` returns the Cartesian product of active factor levels as flat dictionaries with deterministic `cell_id` values [src/instrument/compile_experiment.py:107-128]. It does not call `validate_spec`, so the portal must validate first and only generate a preview when there are no errors.
- `scripts/run_workflow.py` requires `--spec`, `--goal`, `--model`, and `--workdir`, accepts backend/budget/timeout controls, and runs the loaded spec through `run_workflow` [scripts/run_workflow.py:26-52]. It writes a JSON ledger under `experiments/results/workflows/<spec.name>/` [scripts/run_workflow.py:54-62].
- The current queue is specifically named `story_jobs` and stores story status/results in `story_status` and `story_results` [scripts/enqueue.py:32-46]. Its worker unconditionally reads story, model, tier, quality, and condition fields and invokes `scripts/run_story.py` [scripts/worker.py:125-148]. A generic factorial cell from `experiment_matrix` is therefore not enqueue-compatible in this feature.

### Running OpenCode server contract

The contract below was checked on 2026-08-14 against the running server at `http://127.0.0.1:4096`, OpenCode `1.18.15`, and the installed SDK `1.18.15`. Runtime probe commands were:

```text
/home/drseuss/.opencode/bin/opencode --version
/home/drseuss/.opencode/bin/opencode web --help
curl --dump-header - 'http://127.0.0.1:4096/api/session?limit=1'
curl --no-buffer --dump-header - 'http://127.0.0.1:4096/api/event'
```

- `opencode web --help` confirms `--port`, `--hostname`, and repeatable `--cors` options. The live `GET /api/session?limit=1` returned HTTP 200 JSON with `{data: [...], cursor: {previous, next}}`. Each observed session included an ID, agent, model, token/cost/time data, title, and location.
- The native session methods are `GET /api/session` to list, `POST /api/session` to create, `GET /api/session/{sessionID}/message` to reconstruct projected messages, and `POST /api/session/{sessionID}/prompt` to submit input [`.opencode/node_modules/@opencode-ai/sdk/dist/v2/gen/sdk.gen.js`:3297-3350, 3425-3452, 3567-3586].
- Session creation accepts optional ID, agent, and model fields plus a location; the generated SDK sends them as JSON to `POST /api/session` [`.opencode/node_modules/@opencode-ai/sdk/dist/v2/gen/sdk.gen.js`:3324-3350]. The portal can therefore bind each design session to the repository directory without spawning another OpenCode server.
- Prompt admission accepts a required prompt plus optional `delivery: "queue" | "steer"` and `resume`, returns HTTP 200 with `SessionInputAdmitted`, and defines 400, 401, 404, and 409 errors [`.opencode/node_modules/@opencode-ai/sdk/dist/v2/gen/types.gen.d.ts`:9855-9894]. This is the explicit backend-supported Send/Steer path required before making the design pane interactive.
- `GET /api/session/{sessionID}/event?after=<sequence>` is an SSE subscription that replays durable events after an aggregate sequence and then follows new events [`.opencode/node_modules/@opencode-ai/sdk/dist/v2/gen/sdk.gen.js`:3493-3531]. The observed `GET /api/event` response was `200 text/event-stream` with `data:` frames, `server.connected`, and heartbeat comments. Session and global event delivery are SSE, not WebSocket.
- The generated client also exposes `POST /api/session/{sessionID}/interrupt`, explicitly documented as interrupting active execution and doing nothing for an idle session [`.opencode/node_modules/@opencode-ai/sdk/dist/v2/gen/sdk.gen.js`:3533-3544]. Interrupt is available for a portal-owned design session but does not apply to legacy experiment-cell subprocesses.
- `@opencode-ai/sdk` is an ES module at version `1.18.15`; its package exports native v2 JavaScript and type entry points [`.opencode/node_modules/@opencode-ai/sdk/package.json`:3-5, 12-43]. An `.mjs` client can import it, but the current Flask backend cannot use the JavaScript SDK without adding a Node process or moving control-plane credentials and event handling into the browser.

### Existing CLI alternative

- `run_opencode_agentic` constructs `opencode run --model ... --format json --auto --dir ...`, optionally adds variant/title, and appends one prompt [src/instrument/opencode.py:251-267]. It decodes stdout JSONL and publishes events, but exposes no native session client [src/instrument/opencode.py:269-297].
- The shared subprocess runner closes stdin with `DEVNULL`, retains no writable channel, and treats process exit or timeout as the lifecycle boundary [src/instrument/streaming.py:31-50, 66-106]. Reusing it would provide process-per-prompt output, not a long-lived Send/Steer design session.

## 3. Chosen Integration Approach

### Decision

Use a small Python adapter in `admin/` for the native OpenCode v2 HTTP API, then re-expose session events through the Control Room's existing Redis-backed `GET /api/events/<stream_id>` SSE path. The browser never contacts port `4096` directly.

The backend flow is:

1. `POST /api/design-sessions` accepts a kind (`workflow` or `experiment`), description/question, model, and an approved repository work directory. It creates a portal ID and temporary draft path, calls `POST /api/session`, records the returned OpenCode session ID, and submits a kind-specific initial prompt with `delivery: "queue"`.
2. The initial prompt tells the agent to maintain only the assigned draft YAML. The workflow prompt requires `workflow.kind: agent_task` and phases; the experiment prompt requires factorial factors, rules, metrics, and comparison. A fixed draft path makes validation independent of conversational formatting.
3. One backend relay per active design session consumes `GET /api/session/{id}/event?after=<last_sequence>`, records the durable sequence, adds the portal/OpenCode session identity, and publishes normalized or safely preserved events to the same bounded Redis channel/log pattern used by cell transcripts. Durable sequence tracking is required so an OpenCode reconnect does not duplicate the portal's retained log.
4. `GET /api/design-sessions/<portal_id>/spec` reads the temporary draft, reports YAML/parser or `ExperimentSpec.from_dict` construction errors, then calls `validate_spec`. For a valid experiment design it also calls `experiment_matrix` and returns the ordered cell preview and count. Polling this lightweight endpoint while the pane is attached provides live validation without another event protocol or filesystem watcher service.
5. `POST /api/design-sessions/<portal_id>/input` maps ordinary follow-up input to `delivery: "queue"` and an explicit Steer action to `delivery: "steer"`. The UI shows admission/failure separately from model output because the prompt response only acknowledges durable input.
6. `POST /api/design-sessions/<portal_id>/save` re-parses and re-validates the current draft, derives or checks a safe `.yaml` basename, and atomically writes under `experiments/specs/`. Save never trusts an agent-supplied absolute path or `..` segment.
7. `POST /api/design-sessions/<portal_id>/run` is offered only for a valid, saved workflow design. It invokes the existing `scripts/run_workflow.py` contract with explicit goal, model, workdir, timeout, and commit choice, and streams the resulting run under its own existing Control Room cell identity. Experiment-design enqueueing is not included because the current worker cannot dispatch generic matrix cells.

### Rationale

- **Raw native HTTP instead of the JS SDK:** both surfaces describe the same generated routes, but raw HTTP fits the Python Flask process. It avoids a Node bridge, a frontend build step, and direct browser access to the OpenCode control plane. The installed SDK remains the pinned schema reference.
- **Native API instead of `opencode run`:** the API has durable session identity, message reconstruction, session SSE, queue/steer admission, and interrupt. The current CLI wrapper has closed stdin and a subprocess-shaped lifecycle, so adapting it would recreate weaker session management.
- **Backend event proxy instead of browser-to-4096:** the proxy preserves the command rail's one selected `EventSource`, retained Redis replay, transcript normalization, and same-origin error handling. It also keeps filesystem locations and control operations off the browser-visible OpenCode API.
- **Polling a draft-state endpoint instead of parsing streamed prose:** the YAML file is the artifact that will be saved and run. Validating that exact file prevents a displayed conversational example from diverging from the executable spec and is deterministic under tests.
- **Separate design-session metadata from `story_status`:** story queue keys have a fixed worker contract. Separate metadata avoids making portal conversations look like runnable story jobs, while their event streams can still reuse bounded `events:<stream_id>` and `events_log:<stream_id>` transport.
- **Workflow Run now, generic enqueue later:** `run_workflow.py` already accepts the saved artifact, whereas `story_jobs` cannot represent or execute `experiment_matrix` cells. Hiding unsupported enqueue controls is safer than writing nominal jobs that the worker will fail.

## 4. Constraints

- Preserve the current command-rail layout, visual language, fleet monitoring, terminal behavior, routing drawer, queue utilities, and narrow-screen behavior. Design sessions are an additive mode in the existing terminal and session pane, not a replacement dashboard or iframe.
- Preserve all existing endpoint paths, response fields, Redis story keys, queue semantics, and the 500-entry cell-event retention behavior. New design-session APIs and metadata must not repurpose `story_jobs`, `story_status`, or `story_results`.
- Use the already running OpenCode server, defaulting to `http://127.0.0.1:4096` through configuration. Do not start another OpenCode server, add a Node sidecar, add a WebSocket service, or require browser CORS access to port `4096`.
- Keep the OpenCode integration native-v2-only for portal-created sessions. Do not mix `/api/session...` lifecycle calls with compatibility `/session...` messages or `/event` envelopes, because their projections and pagination differ.
- Treat OpenCode `1.18.15` and the installed `@opencode-ai/sdk` v2 generated files as the implemented contract. Unknown event types must remain visible, and API/schema mismatch must produce an explicit unavailable/error state rather than silently dropping data.
- Keep ordinary experiment-cell panes observational. Send, Steer, and Interrupt appear only when the selected identity is a portal-owned design session with a recorded OpenCode session ID. Detach remains a browser-stream action and must not be labeled as Interrupt.
- Keep the unsaved draft outside `experiments/specs/`. Only the backend may choose its temporary path, and only an explicit successful Save may create or replace an `experiments/specs/*.yaml` file.
- Parse YAML safely, catch parser and dataclass-construction errors, and call the existing `validate_spec` as the authoritative semantic gate. Do not duplicate or relax its rules in JavaScript. Call `experiment_matrix` only after that gate passes.
- Save only a normalized basename ending in `.yaml`, reject path traversal and symlink escape, and use an atomic same-directory replacement. Existing files require explicit overwrite confirmation so an agent cannot silently replace a committed spec.
- Run only a valid, saved workflow spec. Require explicit model, workdir, timeout, and commit intent; display the exact launch parameters and require confirmation before starting because `run_workflow.py` can modify and commit a worktree.
- Do not expose experiment-design Enqueue in this phase. Supporting it requires a separate generic job schema and worker dispatch path, which is outside this extension and must not be simulated through `story_jobs`.
- Restrict mutating design-session endpoints to same-origin, JSON requests from a loopback operator unless the portal gains authentication. The Flask app currently binds beyond loopback, and the new endpoints can spend model budget and write files, so read-only deployment assumptions are insufficient.
- Bound request sizes, prompt sizes, relay buffers, reconnect backoff, retained design events, and draft polling frequency. An unavailable Redis or OpenCode server must degrade to a visible state without blocking the Flask request worker indefinitely.
- Never render prompt, YAML, validation error, model output, or tool payload as trusted HTML. Preserve keyboard operation, textual status, visible focus, live-region announcements, `375px` usability, and `prefers-reduced-motion` behavior.
- Add no new infrastructure or frontend build system. Python modules and the existing vanilla JavaScript/CSS/static Flask application are the implementation surface.

## 5. Acceptance Criteria

1. [ ] `GET /` still loads the existing single-screen Control Room, and all pre-existing API and SSE tests pass without changing the baseline semantics of matrix, status, cell events, routing, or queue actions.
2. [ ] The Control Room presents distinct `New workflow design session` and `New experiment design session` actions without hiding the existing fleet, transcript, session pane, routing drawer, or queue utilities.
3. [ ] Starting either kind requires a non-empty feature description or research question and an explicit model; while the request is pending the initiating control is disabled and duplicate submissions are prevented.
4. [ ] A successful start calls native `POST /api/session` with the approved worktree location, stores both portal and OpenCode session IDs, sends the kind-specific initial prompt through `POST /api/session/{id}/prompt` with `delivery: "queue"`, and returns a stable design-session summary to the browser.
5. [ ] `GET /api/design-sessions` returns portal-owned sessions after a page reload without including arbitrary OpenCode sessions, and exposes kind, title, portal stream ID, OpenCode session ID, lifecycle state, draft state, and timestamps without exposing unrestricted filesystem paths.
6. [ ] Selecting a design session uses the existing terminal feed and closes any previously selected cell/design `EventSource`; selecting an ordinary fleet cell restores its existing read-only controls and transcript behavior.
7. [ ] The backend consumes native `GET /api/session/{id}/event?after=<sequence>` as SSE, relays text, reasoning, tool, status, usage, and unknown events safely into the selected Control Room stream, and includes the OpenCode session identity needed by the control pane.
8. [ ] If the OpenCode SSE disconnects, the relay reconnects with the last durable aggregate sequence and does not duplicate already retained events. Browser reconnect and Redis replay remain bounded and preserve the existing `replay_complete` behavior.
9. [ ] If a relay must reconstruct display state, it uses native `GET /api/session/{id}/message`; it does not mix native sessions with compatibility `/session` or `/event` responses.
10. [ ] A selected portal-owned design session exposes Send, Steer, Interrupt, and browser-only Detach with distinct labels and confirmation where destructive; ordinary experiment cells expose none of Send, Steer, or Interrupt.
11. [ ] Send maps to `delivery: "queue"`, Steer maps to `delivery: "steer"`, and both display input-admitted acknowledgement separately from subsequent model events. HTTP 400, 401, 404, 409, timeout, and malformed-response cases produce actionable inline errors without duplicating input.
12. [ ] Interrupt calls native `POST /api/session/{id}/interrupt` only for the selected portal-owned session and reports whether the request was accepted; Detach only closes the browser stream and never interrupts OpenCode.
13. [ ] Each design session receives a unique backend-owned temporary `.yaml` draft and an initial prompt that names that exact path. The agent's conversational YAML is never treated as the saved artifact unless it exists in that draft.
14. [ ] The draft-state API distinguishes no draft yet, invalid YAML, `ExperimentSpec` construction failure, `validate_spec` errors, and valid state. Returned validation errors are displayed inline beside the terminal and update without a full page reload.
15. [ ] Every syntactically loadable draft is passed to the existing `validate_spec`; JavaScript does not decide validity, and Save/Run remain disabled whenever parsing, construction, or validation returns an error.
16. [ ] A workflow design prompt and resulting valid draft use `workflow.kind: agent_task` with phase parameters, while an experiment design prompt and resulting valid draft use `design: factorial` and include factors, rules, metrics, and comparison.
17. [ ] For a valid experiment design, the backend calls `experiment_matrix` only after validation and returns the ordered cell count and assignments. Zero cells, duplicate-looking IDs, and a preview too large for the pane are reported safely rather than freezing or silently enqueueing work.
18. [ ] Save accepts only a safe `.yaml` basename under `experiments/specs/`, re-parses and re-validates immediately before writing, writes atomically, rejects traversal/symlink escape, and requires explicit confirmation before replacing an existing spec.
19. [ ] A successful Save reports the repository-relative path and exact saved content; a failed Save leaves both the existing destination and temporary draft intact.
20. [ ] Run is available only for a valid, saved workflow design. Before launch, the UI shows and confirms spec path, goal, model, workdir, timeout, backend/budget options, and commit intent, then invokes `scripts/run_workflow.py` with those explicit values.
21. [ ] A launched workflow receives a distinct Control Room cell/stream identity so its output can be watched with the existing fleet transcript behavior; design-session conversation events and workflow execution events are not merged into one misleading lifecycle.
22. [ ] Experiment design offers Save and matrix preview but no Enqueue action. No implementation path writes generic matrix cells into `story_jobs` or causes the current story worker to receive a non-story job.
23. [ ] OpenCode unavailable, Redis unavailable, invalid server JSON, SSE disconnect, missing draft, and workflow-launch failure each preserve the last useful transcript/draft content and expose a textual retryable or terminal state without a blank pane or uncaught JavaScript error.
24. [ ] Mutating design-session endpoints reject non-JSON, oversized, cross-origin, and non-loopback unauthenticated requests. User-supplied filenames and workdirs cannot escape configured allowlists, and OpenCode connection details are not returned to the browser.
25. [ ] At desktop and `375px` widths, session creation, transcript, validation errors, matrix preview, and Save/Run controls remain readable without page-level horizontal overflow. All actions are keyboard reachable, status is not color-only, and motion honors `prefers-reduced-motion`.
26. [ ] Backend tests mock OpenCode and Redis and cover create/list, native request bodies, SSE parsing/reconnect sequence, event relay bounds, draft parsing, `validate_spec` gating, matrix preview gating, safe atomic Save, workflow Run arguments, authorization checks, and every documented error response.
27. [ ] Frontend tests cover kind selection, one-stream handoff, read-only versus interactive controls, Send/Steer/Interrupt mapping, live validation states, matrix-preview bounds, Save/Run enablement, duplicate-submit prevention, and empty/offline/error accessibility states.
28. [ ] A contract test or documented local smoke test against OpenCode `1.18.15` verifies list, create, queue input, steer input, session SSE content type/replay, message reconstruction, and interrupt without relying on WebSockets or direct browser access to port `4096`.
29. [ ] The complete repository `pytest` suite passes after implementation.
