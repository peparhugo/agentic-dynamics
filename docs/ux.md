# Control Room Live Design Sessions

The Control Room remains one operational surface: reported spend and burn establish financial context, the fleet shows active work, and the terminal explains what the selected agent is doing. Live design sessions extend that chain upstream so an operator can move from intent to a validated `ExperimentSpec` without leaving the command rail.

Two session kinds are supported:

- **Workflow design** turns a feature goal into an `ExperimentSpec` with `workflow.kind: agent_task` and an ordered phase plan.
- **Experiment design** turns a research question into a factorial `ExperimentSpec` with factors, rules, metrics, and a comparison.

Both are portal-owned OpenCode sessions. Existing experiment cells remain observational; Send, Steer, Interrupt, Save, Run, and Enqueue controls never appear for an ordinary fleet cell. This boundary is necessary because current cell subprocesses have no writable command channel, while the native OpenCode session API has explicit prompt and interrupt operations.

## 1. Layout and Screen Map

### Desktop

The existing full-viewport grid and `5fr 5fr 2.5fr` workspace proportions remain unchanged. Design work occupies the existing transcript and session-control panes rather than opening an editor, modal workspace, iframe, or second application. Reuse keeps spend, queue health, and competing fleet work visible while a spec is drafted.

```text
+------------------------------------------------------------------------------------------------+
| CONTROL ROOM  LIVE | REPORTED SPEND $12.4821 PARTIAL | BURN $0.084/min | 03 running | Redis live|
+-------------------------------------+----------------------------------+--------------------------+
| FLEET 30 CELLS                      | DESIGN / TERMINAL                | SESSION CONTROL          |
| [All] [Running] [Risk] [Search...]  | EXPERIMENT DESIGN   drafting    | DESIGN SESSIONS          |
|                                     | session ds_7af / stream live     | [Workflow design]        |
| +----------------+ +--------------+ |                                  | [Experiment design]      |
| | RUNNING        | | QUEUED       | | 14:31:58 OPERATOR                |                          |
| | story...       | | story...     | | Compare retry policies...        | Kind  Experiment         |
| | ▁▂▃▅ tokens ╱$ | | no samples   | |                                  | Model deepseek/...       |
| +----------------+ +--------------+ | 14:32:01 AGENT                   | Draft draft-7af.yaml     |
| +----------------+ +--------------+ | I'll define policy as a factor...| Revision 8               |
| | DONE           | | FAILED       | |                                  |                          |
| | story...       | | story...     | | 14:32:05 SPEC                    | VALIDATION               |
| | ▁▂▂▃ tokens ╱$ | | ▂▅▇ cost     | | name: retry-policy-study         | VALID / 12 CELLS         |
| +----------------+ +--------------+ | factors:                         |                          |
|                                     |   - name: policy                 | [Save spec] [Enqueue]    |
| queued 14  running 3  done 11       |     levels: [fixed, dynamics]    |                          |
| failed 1  timeout 1                 |                                  | [Send] [Steer]           |
|                                     | 14:32:06 VALIDATE  PASS          | [Interrupt] [Detach]     |
|                                     | spec valid - 12 cells            |                          |
|                                     |                                  | Recent design sessions   |
|                                     | [Follow on] [Pause] [Clear view] | wf_2c1  valid            |
|                                     | > Ask for a change...      [Send]| ds_7af  drafting         |
+-------------------------------------+----------------------------------+--------------------------+
| ROUTING BOARD  collapsed drawer                    | Queue actions | telemetry: partial          |
+------------------------------------------------------------------------------------------------+
```

### Command rail and fleet

The reported-spend ticker, 60-second burn trace, token totals, fleet counters, Redis state, cards, filters, and queue utility menu retain their current positions and meanings. Design-session cost events contribute to reported telemetry only when the backend can attribute finite, non-negative token and cost values; otherwise the rail continues to say `WAITING FOR COST TELEMETRY` or carries `PARTIAL` provenance. This avoids turning session creation into an unsupported accounting claim.

Design sessions do not masquerade as experiment cells in the fleet. A compact `Recent design sessions` list lives in the session pane, while workflow executions and enqueued experiment cells enter the fleet under distinct execution identities. Separating conversation identity from execution identity prevents one transcript from implying that drafting and running are the same lifecycle.

### Session launchers

`Workflow design` and `Experiment design` are persistent, equally weighted buttons under a `DESIGN SESSIONS` label at the top of the session pane. Their full labels are always visible; icons may supplement but never replace the words. The pane is the correct location because these actions create sessions, while the command rail remains reserved for fleet-wide financial and connection state.

Choosing a launcher replaces the lower session details with a compact start form:

| Session kind | Required fields | Optional fields | Why |
|---|---|---|---|
| Workflow design | Feature goal, model, approved workdir | Backend, thinking budget | The goal seeds phases, and explicit execution context prevents the agent from choosing a repository or cost profile implicitly. |
| Experiment design | Research question, model, approved workdir | Seed, budget ceiling | The question anchors factors and metrics, while seed and budget make eventual cell growth visible early. |

`Start workflow design` and `Start experiment design` use kind-specific labels rather than a generic `Create`. The initiating button is disabled while pending, and the typed prompt remains visible after a failure so retries do not require reconstruction.

### Terminal in design mode

Selecting a design session changes the center heading from `CELL / TRANSCRIPT` to `DESIGN / TERMINAL`; it does not change the pane's terminal structure. The selected fleet keyline clears, the prior detail `EventSource` closes, and one design-session stream opens. Selecting a fleet card reverses this handoff and restores the read-only cell controls.

Design mode adds four semantic row types to the existing `THINK`, `AGENT`, `TOOL`, `STEP`, `EVENT`, and `RAW` rows:

| Row | Presentation | Design decision |
|---|---|---|
| `OPERATOR` | Submitted prompt with `queued`, `steered`, or `admission failed` state | Admission is shown separately from agent output because a successful prompt request confirms receipt, not completion. |
| `SPEC` | Complete current draft in a mono, syntax-aware YAML block, labeled with draft revision | The backend-owned draft is the save/run artifact; showing it avoids treating conversational YAML as executable truth. |
| `VALIDATE PASS` | `spec valid - 12 cells`, or `spec valid - workflow ready` | A positive row makes the gate visible in the same chronology as the edit that satisfied it. |
| `VALIDATE ERROR` | One parser, construction, or `validate_spec` error per wrapped line, followed by a count | Verbatim server errors preserve the authoritative validator and keep requires/produces failures actionable. |

The latest `SPEC` row is expanded by default and earlier spec revisions collapse to `SPEC revision N`. A `Show previous revision` disclosure preserves audit context without making repeated YAML dominate the transcript. Syntax highlighting is presentation-only and uses escaped text nodes; the browser never parses highlighted markup from agent output.

Validation rows are inserted only when the draft revision or validation state changes. This prevents polling from flooding the terminal with duplicate `spec valid` rows. The session pane always mirrors the latest state as `NO DRAFT`, `PARSING`, `INVALID YAML`, `INVALID SPEC`, `VALID`, `VALID / UNSAVED CHANGES`, or `SAVED`.

### Session control pane

For a portal-owned design session, the pane shows:

- Session kind, portal session ID, OpenCode session ID, model, approved workdir label, and stream state.
- Draft basename, revision, last validation time, validation state, and cell count when available.
- `Save spec` plus kind-specific `Run workflow` or `Enqueue` actions.
- A prompt composer with `Send` and `Steer`, followed by `Interrupt` and browser-only `Detach`.
- Recent portal-owned design sessions, sorted active first and then by most recent activity.

`Send` queues the next turn. `Steer` injects guidance into active work and is visually secondary because it can redirect an in-progress response. `Interrupt` requests native session interruption and requires confirmation. `Detach` only closes the browser stream and never implies process control. Distinct verbs prevent four materially different actions from collapsing into an ambiguous Pause control.

For an ordinary fleet cell, the pane returns to the existing `READ ONLY` badge, identity, stream state, Watch/Detach behavior, and boundary copy. Design-only controls are removed rather than disabled so the portal does not advertise unsupported control over worker subprocesses.

### Validation and action area

`Save spec` is enabled only for a draft that parses, constructs as `ExperimentSpec`, and returns no errors from server-side `validate_spec`. If the destination exists, confirmation shows the repository-relative path and requires an explicit `Replace existing spec` action. This protects committed specifications from an agent-selected overwrite.

After saving, any draft change marks the session `VALID / UNSAVED CHANGES` and disables Run/Enqueue until the new revision is saved. Executions therefore always reference a stable repository artifact rather than mutable temporary content.

For workflow design, `Run workflow` opens an in-pane confirmation sheet listing spec path, goal, model, workdir, backend, timeout, token budget, and commit intent. The final button reads `Run workflow`; the sheet states that tools may modify the worktree and spend model budget.

For experiment design, `Enqueue` opens the same style of confirmation sheet listing spec path, exact cell count, factor dimensions, models, seed, queue target, and any available budget estimate. The final button reads `Enqueue 12 cells`; it never says merely `Confirm`. The server revalidates the saved bytes and recomputes the matrix before admission, rejecting the request if the revision or count changed.

The current `story_jobs` worker cannot execute generic `experiment_matrix` cells. Therefore `Enqueue` is rendered only when the draft-state response advertises `capabilities.enqueue: true` from a generic ExperimentSpec dispatcher. Until that transport exists, a valid experiment shows `Validated; enqueue unavailable` with `Save spec` still active. This is a deliberate honesty constraint, not a disabled-looking promise.

### Narrow screens

Below `760px`, the existing page sequence remains spend rail, fleet, transcript, session control, and routing drawer. Starting or selecting a design session adds `Jump to design terminal` from the session pane and `Back to session controls` from the terminal. At `375px`, launchers stack, the prompt composer uses a full-width text area, action pairs wrap into 44-pixel minimum targets, and YAML scrolls inside its own block without page-level horizontal overflow.

The transcript retains at least `55vh`, because reducing it to a preview would make agent drafting and validation errors impossible to follow. Confirmation sheets remain in document flow rather than becoming viewport modals, preserving keyboard order and avoiding mobile viewport traps.

## 2. Interaction Flow

### Shared session lifecycle

1. The operator chooses one of the two labeled launchers, supplies the required intent, model, and approved workdir, then starts the session.
2. `POST /api/design-sessions` creates a portal-owned session, backend-selected temporary YAML path, and native OpenCode session. The initial prompt names the exact draft path and the constraints for that session kind.
3. The portal selects the returned design session, closes any prior detail stream, and attaches through the existing terminal SSE relay. The operator's initial intent appears as the first `OPERATOR` row.
4. OpenCode reasoning, text, tools, and usage appear through the normal terminal row renderer. The transcript retains the existing Follow, Pause, Clear view, replay, and 500-row bounds.
5. While attached, the browser requests the latest draft after a relevant tool/text event and at a bounded idle cadence. The backend reads the temporary file, parses it safely, constructs `ExperimentSpec`, calls `validate_spec`, and returns the authoritative revision and state.
6. A changed draft produces one `SPEC` row and one changed `VALIDATE` result. Parser and construction failures remain distinct from semantic validator errors so the operator knows whether to fix YAML shape or experiment logic.
7. The operator can ask for a correction with `Send`, redirect active drafting with `Steer`, or interrupt only the portal-owned native session. Prompt admission appears immediately; model output remains asynchronous.
8. The operator saves only after a passing validation state. The backend re-reads and revalidates before atomically writing under `experiments/specs/`.
9. Run or Enqueue requires that exact saved revision and a second explicit confirmation. A successful launch returns a separate execution identity, which becomes selectable in the fleet without replacing the design conversation.

On reload, `GET /api/design-sessions` restores portal-owned session summaries and the most recently selected identity. It does not enumerate arbitrary OpenCode sessions, because portal ownership determines which sessions may expose mutating controls.

### Workflow design flow

1. The operator selects `Workflow design` and enters a concrete feature goal such as `Add audit-log export with tests`, plus model and approved workdir.
2. The agent is prompted to maintain one draft whose `workflow.kind` is `agent_task` and whose parameters contain ordered phases. The terminal shows the operator intent before agent drafting so the artifact can be judged against its source request.
3. The first draft appears as `SPEC revision 1`. Live validation checks the complete `ExperimentSpec`, including factorial structure and rule requirements, not only the workflow block.
4. If validation fails, errors appear inline, for example `workflow.kind 'story' ...` or an unmet requires/produces message ending in `Instrument it first.` `Save spec` and `Run workflow` remain unavailable.
5. The operator sends a correction or lets the agent revise. A passing draft displays `VALIDATE PASS - spec valid - workflow ready`; the session pane switches to `VALID`.
6. `Save spec` asks for a safe `.yaml` basename and, only when needed, an overwrite confirmation. Success reports the repository-relative path and marks the revision `SAVED`.
7. `Run workflow` presents all launch parameters and side effects. On confirmation, the backend revalidates the saved file and starts the existing workflow runner under a new execution identity.
8. The portal selects the new fleet execution only if the operator chooses `Watch run`; otherwise the design transcript remains visible. This avoids destroying the context needed for a follow-up revision.

### Experiment design flow

1. The operator selects `Experiment design` and enters a research question such as `Does a dynamics retry policy reduce cost without lowering accepted quality?`, plus model and approved workdir.
2. The agent is prompted to maintain one factorial draft containing factors, rules, metrics, comparison, stopping conditions, and provenance-bearing evidence classes.
3. Each draft revision is passed to `validate_spec`. In particular, control-rule `requires` must be available from ledger fields or measurement-rule `produces`; policy arms cannot become enqueueable merely because their YAML parses.
4. After validation passes, the backend computes a bounded `experiment_matrix` preview. The terminal prints `VALIDATE PASS - spec valid - 12 cells`, and the session pane exposes the total plus a collapsed factor-assignment preview.
5. Zero cells, duplicate-looking cell IDs, a matrix above the configured preview/admission cap, or a missing generic dispatcher are capability errors, not `validate_spec` errors. The UI labels them separately as `VALID SPEC / NOT ENQUEUEABLE`, preserving the meaning of the authoritative validator.
6. `Save spec` persists the validated revision. If generic dispatch is available, `Enqueue` then shows the exact cell count and dimensions in the queue-style confirmation sheet.
7. On confirmation, the backend revalidates, recomputes the matrix, and enqueues an immutable saved revision. A mismatch returns to the draft with `Spec changed; review the new 16-cell matrix` rather than admitting a different workload.
8. Accepted cells appear through the normal fleet snapshot and status stream. The design session stays available in Recent design sessions for interpretation and later adaptation.

### Validation feedback rules

The draft-state contract distinguishes these states because each has a different remedy:

| State | Terminal copy | Available actions |
|---|---|---|
| No draft | `Waiting for the agent to write the assigned draft` | Send, Steer, Interrupt, Detach |
| Invalid YAML | Parser location and message | Send, Steer, Interrupt, Detach |
| Construction error | Dataclass/schema construction message | Send, Steer, Interrupt, Detach |
| Validation errors | Verbatim `validate_spec` errors | Send, Steer, Interrupt, Detach |
| Valid, unsaved | `spec valid - N cells` or `workflow ready` | Save spec, conversation controls |
| Valid, saved | Saved path and revision | Run workflow or Enqueue when capable, conversation controls |
| Valid, not runnable | Capability reason such as matrix cap or unavailable dispatcher | Save spec, conversation controls |

The browser never duplicates `validate_spec` logic. Client-side checks cover only required form fields and obvious request shape; all validity, cell counts, saved-revision checks, and launch gates come from the backend. One source of truth prevents a green browser state from disagreeing with execution.

### Confirmation and failure behavior

Save, Run, Enqueue, Interrupt, and existing queue-clear operations use the same compact confirmation pattern: action name, target, consequences, Cancel first, and a specific final verb. Destructive or spend-producing actions are never triggered by Enter while focus is in the prompt composer.

While a mutation request is pending, only its initiating control is disabled and labeled with progress, such as `Saving...` or `Enqueueing 12 cells...`. Duplicate submissions carry an idempotency key. Failure leaves the latest transcript, draft, entered filename, and confirmation parameters in place, then focuses an inline error summary. Preserving context is more useful than resetting a control plane after a transient OpenCode, Redis, or filesystem error.

Stream reconnection, draft polling failure, and OpenCode unavailability are separate states. A stream failure marks transcript freshness; a draft failure marks validation stale and disables Save/Run/Enqueue; an OpenCode control failure disables Send/Steer/Interrupt. Independent degradation keeps safe read-only information available.

## 3. Visual Language

### Existing operations-room palette

The feature uses the implemented Control Room tokens rather than introducing editor chrome:

| Token | Value | Use |
|---|---:|---|
| `--ink-0` | `#07090c` | Viewport and terminal ground |
| `--ink-1` | `#0d1117` | Pane background |
| `--ink-2` | `#151b23` | Selected and interactive rows |
| `--line` | `#2a3441` | Borders and YAML guides |
| `--line-strong` | `#46566a` | Focus and selected revision boundaries |
| `--text` | `#e8edf2` | Agent text and YAML values |
| `--muted` | `#9ba8b8` | Metadata and inactive labels |
| `--cost` | `#ffbf47` | Money only |
| `--running` | `#43b9ff` | Live stream, drafting, links, YAML keys |
| `--done` | `#57d38c` | Valid and saved states |
| `--failed` | `#ff6470` | Parser, construction, validation, and request errors |
| `--timeout` | `#c995ff` | Timeout and YAML scalar accents |

Amber remains exclusive to reported money and cost traces. Validation uses green/red and syntax uses blue, violet, text, and muted tones, so syntax highlighting cannot be mistaken for spend.

### Typography and syntax

Labels and controls use the existing system sans stack. Prompts, transcript rows, IDs, timestamps, validation text, and YAML use `ui-monospace, "SFMono-Regular", Consolas, monospace`. This makes the design session feel like the current terminal rather than a foreign embedded IDE.

The YAML block has line numbers, preserved indentation, wrapped comments, and horizontal scrolling only for indivisible tokens. Keys, strings, numbers, booleans, nulls, comments, and punctuation receive restrained syntax color, but the raw source remains selectable and available through `Copy YAML`. Highlighting runs over escaped source and never accepts model-produced HTML.

`OPERATOR`, `AGENT`, `SPEC`, and `VALIDATE` remain uppercase, letter-spaced row labels in the same timestamp gutter used by current events. Validation errors wrap beneath the label with hanging indentation so long requires/produces messages stay scannable.

### Shape, hierarchy, and motion

Launchers and actions use the current one-pixel border, four-pixel radius, and 44-pixel minimum target. The draft is a terminal row with a stronger left rule, not a floating rounded card. This keeps the industrial hierarchy and prevents the spec from looking detached from the conversation that produced it.

The latest validation state is repeated in the session pane because it governs actions; earlier validation remains in transcript chronology because it explains the path to validity. This intentional duplication separates current control state from historical evidence.

New transcript rows appear without typewriter effects. A changed validation badge cross-fades over at most 160 milliseconds; drafting retains the existing restrained running pulse; terminal validation stops pulsing. Under `prefers-reduced-motion: reduce`, all pulses, fades, and smooth scrolling are removed while words, icons, and border states remain.

### Accessibility and trust

Every state combines text, icon, and color. The transcript remains a named `role="log"` that is not continuously announced; prompt admission, validation-state changes, and mutation results use a separate polite live region, while failed Save/Run/Enqueue uses an assertive alert. This announces consequential changes without reading every model token to screen-reader users.

Keyboard order follows launcher, start form, terminal controls, prompt composer, session actions, and recent sessions. Opening a confirmation moves focus to its heading; Cancel or success returns focus to the initiating control. Escape closes only the confirmation or routing drawer and never detaches or interrupts a session.

Prompt text, agent output, tool payloads, YAML, filenames, and validation errors are always rendered with `textContent` or equivalent escaped nodes. The backend owns workdirs and temporary paths, while Save accepts only a normalized `.yaml` basename under `experiments/specs/`. These trust boundaries are part of the experience because a design session can spend budget, run tools, and write repository files.

## 4. Endpoint and Stream Element Map

The feature is additive. Existing endpoints keep their current contracts; rows marked **new** are required for portal-managed design sessions. The browser remains same-origin and never connects directly to the OpenCode server.

| Source | Status and cadence | Elements fed | Contract and rationale |
|---|---|---|---|
| `GET /` and `/static/*` | Existing, initial load | Entire shell, launchers, terminal and control-pane states | The static Flask application remains the only frontend surface; no iframe or build system is required. |
| `GET /api/matrix` | Existing JSON, load plus five-second poll | Fleet, counts, retained telemetry, reported spend, token totals, card traces | Design conversations are not cells. Only launched workflow executions or admitted experiment cells appear here under separate IDs. |
| `GET /api/status` | Existing page-lifetime SSE | Fleet status transitions, counters, global connection state | The page opens one global status stream. Design-session lifecycle does not create one stream per session. |
| `GET /api/events/<encoded-stream-id>` | Existing SSE relay, one selected detail at a time | Cell or design transcript, reasoning, agent text, tools, usage, session identity, replay boundary | Design relays normalize native OpenCode events into the existing retained Redis channel/log pattern. Switching selection closes the previous source before opening another. |
| `GET /api/routing` | Existing JSON, drawer open/refresh | Routing drawer | Design mode does not displace or reinterpret routing evidence. |
| `POST /api/experiments` | Existing JSON mutation | Existing hardcoded queue Enqueue/Clear notices | This endpoint retains story-queue semantics and is never used for a drafted ExperimentSpec. |
| `POST /api/design-sessions` | **New** JSON mutation | Start-form pending/success/error, selected design identity | Accepts `kind`, intent, model, approved workdir key, and bounded options; creates the portal/native session and assigned temporary draft. |
| `GET /api/design-sessions` | **New** JSON on load and manual retry | Recent design sessions, restored selection, lifecycle badges | Returns portal-owned summaries only, without unrestricted filesystem paths or arbitrary native sessions. |
| `GET /api/design-sessions/<id>/spec` | **New** JSON after relevant events and bounded polling | `SPEC` row, validation rows, current badge, cell preview, action capability gates | Reads the exact temporary artifact, parses, constructs, calls `validate_spec`, and only then computes a bounded matrix preview. Revision/ETag support avoids duplicate rows. |
| `POST /api/design-sessions/<id>/input` | **New** JSON mutation | `OPERATOR` admission row, Send/Steer status | Maps `delivery: queue` to Send and `delivery: steer` to Steer. Admission acknowledgement is not presented as agent completion. |
| `POST /api/design-sessions/<id>/interrupt` | **New** JSON mutation | Interrupt confirmation/result and lifecycle state | Proxies native interrupt only for a portal-owned session. It is separate from browser Detach. |
| `POST /api/design-sessions/<id>/save` | **New** JSON mutation | Saved path/revision, overwrite confirmation, Save result | Re-parses and revalidates, enforces a safe basename, and writes atomically under `experiments/specs/`; existing files require explicit overwrite intent. |
| `POST /api/design-sessions/<id>/run` | **New** workflow-only JSON mutation | Run confirmation/result and returned fleet execution ID | Revalidates the immutable saved revision and invokes the workflow runner with explicit launch parameters. |
| `POST /api/design-sessions/<id>/enqueue` | **New**, gated experiment-only JSON mutation | Enqueue capability, exact-cell confirmation, admission result | Requires a generic ExperimentSpec dispatcher, revalidates and recomputes cells, and must not write generic cells into the existing story-only queue. |

### Draft-state response

The draft endpoint returns one coherent snapshot so the spec text, validation state, matrix count, and enabled actions cannot come from different revisions:

```json
{
  "session_id": "ds_7af",
  "revision": 8,
  "draft_state": "valid",
  "yaml": "name: retry-policy-study\n...",
  "validation": {
    "valid": true,
    "errors": [],
    "validated_at": "2026-08-14T14:32:06Z"
  },
  "matrix": {
    "count": 12,
    "preview": [{"cell_id": "...", "policy": "fixed"}],
    "truncated": false
  },
  "saved": {
    "revision": 8,
    "path": "experiments/specs/retry-policy-study.yaml"
  },
  "capabilities": {
    "save": true,
    "run": false,
    "enqueue": true,
    "reason": null
  }
}
```

For malformed YAML or construction failure, `yaml` and the exact error remain available while `validation.valid` is false and all mutation capabilities are false except conversation controls. For a valid but unsaved revision, `save` is true and Run/Enqueue are false. Capability fields are backend decisions, not client inference.

### Stream ownership and event handling

The page owns exactly two SSE connections at most: one global `/api/status` source and one selected `/api/events/<stream-id>` source. Reusing the selected-detail stream avoids browser connection fan-out and preserves the existing replay/follow/pause machinery.

The native OpenCode relay tracks its durable aggregate sequence before publishing into the portal's bounded Redis event log. Browser reconnect still receives retained events followed by `replay_complete`; occurrence-based deduplication remains defensive, but durable relay sequencing prevents native reconnects from multiplying design rows.

Draft validation is not scraped from SSE prose. The browser fetches the backend-owned file snapshot through the spec endpoint, then creates local `SPEC` and `VALIDATE` terminal rows keyed by revision and state hash. This split makes the artifact authoritative while keeping validation visually integrated with the streamed conversation.

### Launch handoff

A successful workflow Run or experiment Enqueue returns an execution ID and stream ID. Subsequent status comes from `/api/matrix` and `/api/status`, and selecting that execution reads `/api/events/<stream-id>` like any other fleet item. The design-session stream remains separate and recoverable from Recent design sessions.

All mutating design endpoints require same-origin JSON, bounded bodies, portal-session ownership, an idempotency key, and loopback access unless authentication is added. Errors from OpenCode, Redis, validation, filesystem writes, queue admission, or the runner are returned as structured JSON and rendered inline without erasing last-known transcript or draft content.
