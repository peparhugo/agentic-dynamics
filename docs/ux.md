# Control Room UX Design

The Control Room replaces the three disconnected admin views with one operational surface. Its hierarchy is deliberately financial: reported spend and burn rate are always visible, the fleet explains where that spend is occurring, and the selected agent's transcript explains why.

The surface is observational in this phase. A running cell can be attached and watched, but the current runner has no authenticated inbound command channel, retained process registry, or writable subprocess input. The UI must not imply that a prompt, pause, abort, or steering action is available. This preserves the approved scope while leaving the control pane structurally ready for a future, explicitly secured command transport.

## 1. Layout and Screen Map

### Desktop: one screen, three levels of attention

The application fills the viewport and uses a fixed command rail above a three-pane workspace. Only the pane interiors scroll; keeping the financial header and fleet state anchored prevents context loss during a long transcript.

```text
+--------------------------------------------------------------------------------------+
| CONTROL ROOM   LIVE | REPORTED SPEND  $12.4821  PARTIAL | BURN  $0.084/min  60s      |
| 14:32:08 UTC        | INPUT 4.18M | OUTPUT 682K       | Redis: live | 03 running     |
+------------------------------------+--------------------------------+----------------+
| FLEET  30 CELLS                    | CELL / TRANSCRIPT              | SESSION CONTROL|
| [All] [Running] [Risk] [Search...] | story__tier__model__condition | READ ONLY      |
|                                    | RUNNING  stream: live          |                |
| +----------------+ +-------------+ |                                | Cell           |
| | RUNNING    24c | | QUEUED      | | 14:31:58  THINK                 | full cell id   |
| | story...       | | story...    | | Checking the failing route... |                |
| | ▁▂▃▅ tokens  ╱$| | no samples  | |                                | Status RUNNING |
| +----------------+ +-------------+ | 14:32:01  TOOL bash             | Stream LIVE    |
| +----------------+ +-------------+ | $ pytest tests/test_api.py     | Session abc123 |
| | DONE       $...| | FAILED  !   | | completed in 1.8s              |                |
| | story...       | | story...    | |                                | [Detach]       |
| | ▁▂▂▃ tokens  ╱$| | ▂▅▇ cost    | | 14:32:04  STEP                 |                |
| +----------------+ +-------------+ | 1,284 in / 312 out / $0.0241   | Watching does  |
|                                    |                                | not control the|
|  queued 14  running 3  done 11    | [Follow: on] [Pause] [Clear]   | experiment.    |
|  failed 1  timeout 1              |                                |                |
+------------------------------------+--------------------------------+----------------+
| ROUTING BOARD  collapsed drawer                 | Queue actions | telemetry: partial |
+--------------------------------------------------------------------------------------+
```

The column proportions are `5fr 5fr 2.5fr`, with practical minimum widths rather than equal columns. The fleet and transcript carry most of the operator's work, while the control pane remains narrow because it exposes identity and connection state rather than a fake command console.

### Command rail

The command rail contains four groups in reading order:

1. **Identity and clock:** `CONTROL ROOM`, UTC clock, and an overall `LIVE`, `RECONNECTING`, or `OFFLINE` label. UTC avoids ambiguity when correlating transcript entries with server logs.
2. **Reported spend:** cumulative numeric cost with four decimal places and a `PARTIAL` or `RETAINED WINDOW` qualifier when completeness cannot be proven. The qualifier is adjacent to the amount so reported telemetry cannot be mistaken for an invoice.
3. **Burn rate:** cost per minute over a labeled rolling 60-second window, plus a tiny horizontal trace of recent live cost deltas. A fixed window makes movement interpretable rather than merely animated.
4. **Token and fleet counters:** input tokens, output tokens, running cells, and Redis state. Tokens explain movement in cost without competing visually with the primary monetary signal.

Before a valid numeric cost event exists, the amount reads `WAITING FOR COST TELEMETRY`; it never displays `$0.00` as if zero spend were known. Negative, absent, or malformed cost and token values do not enter totals.

### Fleet pane

The fleet pane replaces the Matrix view with a dense, selectable card field. Its header includes total cells, filter chips (`All`, `Running`, `Risk`), and search by full cell ID. Filters change presentation only and never interrupt telemetry collection.

Each card contains:

- A shape icon and explicit status word: `QUEUED`, `RUNNING`, `DONE`, `FAILED`, `TIMEOUT`, or `UNKNOWN`.
- The full cell ID over multiple lines rather than an ellipsis. Cell IDs encode experiment factors, so truncation would remove operationally useful identity.
- Latest reported step cost, or `no cost yet`; unsupported zeroes are not invented.
- A 36-pixel token-cost sparkline. Muted vertical bars encode total tokens per step and an amber line encodes reported step cost. Two encodings let the operator distinguish token volume from price movement in very little space.
- An accessible summary such as `Latest sample: 1,596 tokens, 2.4 cents; 8 samples shown`. The chart itself is decorative because a tiny chart cannot carry sufficient accessible meaning.

Cards sort by urgency first (`running`, `failed`, `timeout`, `queued`, `done`) and then by cell ID. This puts spend-producing and intervention-worthy cells above completed work while retaining deterministic order within a state.

The selected card receives a solid inset keyline and `SELECTED` text. Selection cannot rely on glow alone. A running card's accessible action is `Watch running cell <id>`; queued and terminal cards use `Inspect cell <id>`.

### Transcript pane

The center pane is a terminal, not a JSON viewer. Its sticky header shows the selected cell's full ID, status, stream state, and local transcript controls. The feed translates known events into compact semantic rows:

| Event | Presentation | Reasoning |
|---|---|---|
| `reasoning` | `THINK` row with softly dimmed prose | Keeps the agent's working process readable without making it louder than outcomes. |
| `text` | `AGENT` row in the brightest body text | Treats the answer or narration as primary transcript content. |
| `tool_use` | `TOOL <name>` row with status, summarized input, and expandable output | Shows what the agent did while preventing large tool payloads from overwhelming the feed. |
| `step_start` | Thin numbered divider | Makes long sessions scannable without adding a card around every step. |
| `step_finish` | `STEP` row with input, output, reasoning, cache tokens, and reported cost when present | Connects each unit of work directly to its financial consequence. |
| Unknown JSON | `EVENT` row with a collapsed, formatted details disclosure | Preserves forward compatibility instead of silently dropping data. |
| Plain text | `RAW` row with escaped text | Keeps malformed or legacy events visible and safe. |

Rows use a UTC timestamp when one is supplied. If an event has no timestamp, the UI uses an arrival marker such as `received now` and does not fabricate server time.

The feed retains at most 500 rendered rows. `Follow` scrolls only when the operator is already at the bottom; manual upward scrolling suspends follow and exposes a `Jump to live` control. `Pause` freezes rendering locally while buffering within the same bound. `Clear view` removes local rows only and is followed by helper text stating that Redis history and the experiment are unchanged.

### Session control pane

The right pane is titled `SESSION CONTROL` with a persistent `READ ONLY` badge. It contains:

- Selected cell ID and current cell status.
- Event-stream state: `connecting`, `live`, `reconnecting`, `disconnected`, or `unavailable`.
- OpenCode session ID when a selected event supplies `sessionID`; otherwise `Session identity not observed yet`.
- `Watch` for an unattached running cell and `Detach` for an attached stream. Detach closes only the browser's selected-cell `EventSource` and leaves the worker untouched.
- A short boundary statement: `Watching does not send input or control the experiment.`

No disabled prompt box, Send button, process Pause button, or Abort button is shown. Disabled controls would still suggest a capability the system does not possess. A future steering phase can add a command composer in this pane only after cell-to-session identity, authentication, authorization, command acknowledgement, and graceful cancellation are implemented outside the current Redis telemetry contract.

### Routing and queue utilities

The existing Routing view becomes a bottom drawer so it remains reachable without displacing live operations. Opening the drawer fetches routing data and presents the current per-task and strategy tables unchanged in meaning.

Queue actions live in a small utility menu rather than the primary rail because queue administration is secondary to observation. `Enqueue` and `Clear queued work` use the existing experiments API. Clear requires confirmation with the exact warning `This clears queued metadata; it does not cancel running work.`

### Narrow screens

At widths below `760px`, the command rail wraps into a two-row spend strip and the workspace becomes one vertical sequence: spend, fleet, transcript, session control, routing drawer. The fleet uses one card per row at `375px`; the transcript receives at least `55vh` so it remains useful rather than becoming a token preview.

The selected card exposes `Jump to transcript`, and the transcript exposes `Back to fleet`. These are anchor movements within the same document, not separate views, preserving the single-screen mental model. No pane or control creates horizontal page overflow; only long terminal payloads may scroll inside their own code block.

## 2. Interaction Flow

### Arrival and hydration

1. The shell renders immediately with skeleton cards and explicit `connecting` labels rather than blank regions.
2. `GET /api/matrix` hydrates cell identity, statuses, counts, and additive retained-window telemetry summaries. Last-known content remains visible on later fetch failures because an outage should not erase operational context.
3. `GET /api/status` opens once and applies status transitions in place. Native EventSource retry is surfaced as `reconnecting`; the application must not create parallel status streams.
4. If no cells exist, the fleet displays `No cells are queued or retained` with an optional `Enqueue experiment` action. Spend remains `WAITING FOR COST TELEMETRY` rather than zero.
5. No cell is selected automatically unless there is exactly one running cell. This avoids surprising attachment in a busy fleet while making the single-agent case immediate.

The matrix telemetry addition is a snapshot, not an append-only client ledger: each successful response replaces the retained-window totals and per-cell sample arrays. Replacement prevents five-second polling from counting the same history repeatedly. The existing response fields and meanings remain unchanged; new telemetry fields are additive and derived from existing `events_log:<cell_id>` entries.

### Selecting and watching a cell

1. Clicking a card, pressing Enter on its focused action, or choosing `Watch` sets one global selected-cell ID.
2. The card receives the selection keyline, the transcript header changes immediately, and any previous selected-cell EventSource closes before the new one opens.
3. The browser connects to `GET /api/events/<encoded-cell-id>`. Retained events render chronologically, followed by live events from the same stream.
4. The session pane changes from `connecting` to `live` on the first event. A quiet but healthy stream remains live; lack of agent output is not itself an error.
5. If a native event contains `sessionID`, the pane reveals it with a copy action. Session identity is informational because a cell may span multiple native sessions and Claude translation may not supply one.
6. Selecting another card repeats the handoff without affecting the global status stream or matrix polling.

For a queued cell, the pane says `Waiting for worker` and remains ready to receive history/live events. For `done`, `failed`, or `timeout`, it says `Inspecting retained history`; terminal cards do not imply that the underlying process is attachable.

### Reading live work

Incoming selected-cell events are normalized by type before rendering. Known text is escaped, tool input/output is summarized, and unknown content remains available through a disclosure. This provides terminal immediacy without trusting event payloads as HTML.

When a valid `step_finish` arrives, the selected card sparkline and its latest-cost label update immediately. The spend rail reconciles that sample against the latest fleet snapshot rather than blindly adding it, so replay and automatic reconnection cannot double-count reported spend. Replayed samples may hydrate cumulative retained spend, but only samples observed after the live boundary enter the rolling burn-rate window.

Because the current retained event list is capped at 500 entries, any total derived from a full list or an unknown history boundary is labeled `PARTIAL` or `RETAINED WINDOW`. Cost language consistently uses `reported`, never `actual`, `invoice`, or `bill`.

### Stream interruption and recovery

The status source and selected-cell source each expose these visible states:

- `connecting`: initial connection has not delivered data.
- `live`: connection is open and data has been observed.
- `reconnecting`: EventSource reported an error and will retry.
- `disconnected`: the operator detached or the page intentionally closed the source.
- `unavailable`: the server returned a nonrecoverable response or Redis is unavailable.

On interruption, cards, totals, samples, and transcript rows remain in place with a `last update` age. Reconnection resumes into the same selected cell, deduplicates retained replay before rendering or aggregation, and does not multiply EventSource instances. This favors continuity while clearly distinguishing stale data from live telemetry.

### Transcript controls

- `Pause` stops DOM insertion, not network receipt or the experiment. Its label becomes `Resume (N buffered)`.
- `Resume` appends the bounded buffer in order and follows only if follow mode was active before pausing.
- `Follow` toggles automatic bottom alignment. Manual upward scrolling turns it off without discarding events.
- `Clear view` requests confirmation only when buffered content exists, clears local presentation, and never calls a backend deletion endpoint.
- `Detach` closes the selected-cell stream and freezes the current transcript. The selected card remains selected so the operator can reattach without searching again.

### Keyboard and announcements

Cards are real buttons or contain one real button, support normal tab order, and use visible focus rings. Status transitions announce through a polite live region; failures and Redis loss use an assertive alert. Continuous transcript content is not automatically announced because it would overwhelm screen-reader users; the transcript is a named log region that can be entered on demand.

## 3. Visual Language

### Color

The palette resembles a dim operations room rather than a generic analytics dashboard:

| Token | Value | Use and rationale |
|---|---:|---|
| `--ink-0` | `#07090c` | Viewport background; near-black gives luminous telemetry contrast without pure-black glare. |
| `--ink-1` | `#0d1117` | Pane background; a small lift establishes structure without visible card chrome everywhere. |
| `--ink-2` | `#151b23` | Selected and interactive surfaces. |
| `--line` | `#2a3441` | Borders and graph grids; blue-gray stays subordinate to data. |
| `--text` | `#e8edf2` | Primary text at accessible contrast. |
| `--muted` | `#8b98a8` | Labels and inactive metadata, never essential status alone. |
| `--cost` | `#ffbf47` | Spend, burn, and cost traces; amber is the protagonist and appears nowhere decorative. |
| `--queued` | `#8793a1` | Neutral queued state. |
| `--running` | `#43b9ff` | Active work and connection indicators. |
| `--done` | `#57d38c` | Successful terminal state. |
| `--failed` | `#ff6470` | Failed state and actionable errors. |
| `--timeout` | `#c995ff` | Timeout; violet distinguishes it from both cost amber and failure red. |

Every status combines color with a word and icon: hollow circle for queued, rotating-notch circle for running, check for done, cross for failed, and clock for timeout. Cost retains exclusive ownership of amber so the eye learns one stable financial cue.

Subtle one-pixel grid lines may sit behind the fleet at low opacity. They provide instrument-panel character without scanline animation, fake noise, gradients on every card, or decorative data that could be mistaken for telemetry.

### Typography and numbers

The UI uses dependency-free local stacks:

- Labels and controls: `system-ui, -apple-system, "Segoe UI", sans-serif`.
- Cell IDs, transcript, clocks, costs, and tokens: `ui-monospace, "SFMono-Regular", Consolas, monospace`.

Section labels are uppercase, letter-spaced, and small; body text remains sentence case. Monetary figures use tabular numerals and a larger weight, preventing width jitter as spend updates. Costs show four decimals below `$100`, tokens use compact suffixes in the rail, and exact values remain available in accessible labels or details.

### Motion

Motion communicates state changes only:

- Running cards emit a restrained two-second border pulse, not a whole-card scale animation. This indicates active spend without making the matrix visually unstable.
- A new cost sample draws the final sparkline segment over 180 milliseconds and briefly brightens the spend amount. The movement ties cause to financial effect.
- Status transitions cross-fade the icon and border over 160 milliseconds. Terminal states stop all pulsing immediately.
- Transcript rows appear without typewriter effects; streaming content is already moving and does not need theatrical delay.
- Drawer and pane transitions use at most 180 milliseconds and never block input.

Under `prefers-reduced-motion: reduce`, pulses, line drawing, smooth scrolling, and cross-fades are removed. Running state remains apparent through icon, status text, border color, and live connection copy.

### Density, shape, and hierarchy

Cards use four-pixel corner radii, one-pixel borders, and almost no shadow. The compact industrial shape differentiates the Control Room from soft consumer dashboards and leaves visual emphasis for the amber spend rail.

Spacing follows a four-pixel base unit. Fleet cards are information-dense but retain a minimum 44-pixel selection target. Pane headings and controls remain fixed while content scrolls, and terminal line length is constrained enough to read reasoning while tool output can expand to full pane width.

## 4. Data and SSE Element Map

The design preserves Flask, all current paths, and the existing Redis names and meanings: `story_jobs`, `story_results`, `story_status`, `status`, `events:<cell_id>`, and `events_log:<cell_id>`. No iframe, second service, framework, or alternate realtime transport is introduced.

| Source | Transport and cadence | Elements fed | Client behavior |
|---|---|---|---|
| `GET /api/matrix` | JSON on load and every five seconds | Fleet inventory, initial/current statuses, state counts, Redis-unavailable state, reported-spend snapshot, token totals, and all card sparkline histories | Preserve current fields. Add only derived telemetry summaries/samples from retained event logs. Replace snapshots rather than accumulating them so polling cannot duplicate spend. Keep the last good snapshot on errors. |
| `GET /api/status` | One page-lifetime SSE connection | Card status word/icon/border/pulse, fleet counters, selected-cell status, overall connection indicator | Parse existing `{cell_id, status}` messages. Unknown statuses use the neutral treatment. Heartbeat comments maintain the connection but do not create visual events. |
| `GET /api/events/<encoded-cell-id>` | One SSE connection for the selected cell; retained replay then live Pub/Sub | Terminal rows, selected-card live sparkline, selected latest-cost label, immediate spend/token reconciliation, rolling burn-rate samples, session ID, and selected-stream state | Close the previous source before switching. Interpret existing `text`, `reasoning`, `tool_use`, `step_start`, and `step_finish` payloads; preserve unknown JSON and plain text. Bound rendered rows to 500 and deduplicate replay on reconnect. |
| `GET /api/routing` | JSON when the Routing drawer first opens, with manual refresh | Per-task routing and strategy simulation drawer | Preserve current table meanings and show explicit empty/error states. Routing never blocks the live workspace. |
| `POST /api/experiments` | JSON request initiated from the utility menu | Enqueue and clear progress/result notices | Send only existing `enqueue` or `clear` actions. Disable the initiating control while pending. Require confirmation for clear and state that running work is not cancelled. |
| `GET /` and `/static/*` | Initial document/assets | Entire Control Room shell | Render useful connecting and empty states before Redis data arrives. No iframe or frontend build step is required. |

### Feed ownership and reconciliation

The matrix snapshot owns fleet-wide retained totals and sparkline history; the selected event SSE owns immediate presentation for one watched cell. This split is intentional: opening an EventSource for every card would exceed common HTTP/1 per-origin connection limits and duplicate the backend's per-cell Pub/Sub work.

For selected-cell events, the client keeps a cell-scoped identity ledger for the retained window and reconciles incoming samples with the next matrix snapshot. Automatic SSE replay can therefore redraw missing transcript rows without adding cost twice. Historical samples establish cumulative reported telemetry but do not enter the live 60-second burn window; only newly observed post-attachment samples do.

The UI treats the current event schema defensively:

- `part.tokens.input`, `part.tokens.output`, `part.tokens.reasoning`, and cache counts contribute only when finite and non-negative.
- `part.cost` contributes only when finite and non-negative.
- Missing fields render as unavailable rather than numeric zero unless the event explicitly reports zero.
- `sessionID` is displayed when present but is never assumed to be stable for the entire cell.
- Tool payloads are escaped and collapsed by default.

The current SSE streams have no durable cursor and the event log retains only 500 entries. The visual contract therefore promises a live operational estimate, not accounting completeness. Whenever the client cannot prove complete history, the spend rail and affected card details visibly carry `PARTIAL` or `RETAINED WINDOW` provenance.
