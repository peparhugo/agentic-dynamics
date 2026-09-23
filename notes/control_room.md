# Control Room Detail Truth

## Problem

The Control Room is a read-only operator surface over several authorities, but the served room
does not yet make the ownership boundary complete. L23 left two material caveats: attention/order/
age were derived in the browser and the required state screens were only partially present. L33
then demonstrated the acceptance consequence. The candidate passed its in-cell tests and its
workflow gates, but the host render gate failed because the asserted server-owned
`operations-attention.state` value, `active`, was not visible text in the rendered page.

L47 is the policy boundary that explains why this cannot be waived by a green workflow run. The
fleet image does not contain the browser acceptance environment. The host must run the acceptance
profile against the exact candidate that the controller is considering, and the report must carry
candidate-bound captures. A passing pytest run proves neither browser rendering nor candidate
identity.

The requested failed report at
`experiments/results/control_room_render/L33_candidate_f7ab43551/gate_report.json` is not present
in this checkout. The committed `apps/control_room/verification/gate_report.json` is a different,
passing candidate report, so it is not used as evidence for the missing L33 artifact. The L33
failure and its four remediation requirements are therefore recorded from
`docs/reviews/loose_ends_register.md` and the declared workflow context, with the current gate,
fixtures, services, routes, and static renderer used for the implementation inventory below.

## What Exists

### Authority and delivery

The room has a mostly coherent read path:

| Surface/value | Service that owns the value | Fixture assertion | Capture that shows it |
|---|---|---|---|
| Operations packet schema, control epoch, and repository head | `apps/control_room/services/operations.py:326-365`, delivered by `routes/operations.py:/api/operations` | `boards_endpoints.json:3-7`; `check_boards_fixtures()` validates the operations seed and the gate reads the rendered truth strip | `boards_operations_desktop_dark_1440x900.png`, light equivalent, and `boards_operations_narrow_dark_1024x768.png` |
| Active and promotable run arrays, including run id, spec, model, phase counts, state, candidate, and start time | `services.operations.operational_snapshot()` passes through `control_status.build_packet()`; `services.context.operations_snapshot()` supplies the packet inputs | `boards_endpoints.json:8-18`; `verify_control_room_rendering.py:2546-2571` expands the seed into 18 rows and `:2643-2654` checks row count and attention identity | Operations captures above |
| Awaiting approvals and failed runs in the decisions-owed attention block | `services.operations.operational_snapshot():342-347`; the route is `/api/operations` | `boards_endpoints.json:19-35`; `tests/test_control_room_operations.py:73-108` proves packet identifier parity | Operations captures; the attention table is visible in the Operations capture |
| Projection lag and its unknown/degraded distinction | `services.operations` passes `projection_lag` and `degraded`; projection authority is `agentic_dynamics.control.projection_watermarks` | `boards_endpoints.json:37-41,58-65`; `check_boards_fixtures():2655-2657` requires a degraded variant | Operations and degraded-Operations captures |
| Unhealthy worker identities and ages when worker heartbeats are readable | `services.context.operations_snapshot():141-145` obtains heartbeats; `control_status.build_packet()` supplies `unhealthy_workers` | `boards_endpoints.json:43-48` carries `session_id` and `age_seconds`, but the current gate only checks the list shape indirectly | No dedicated worker-row capture; the Operations capture shows only the count |
| Named control-database, repository-head, projection, and worker-health degradation | `services.context.operations_snapshot():137-165`; the packet keeps the degraded entries named | `boards_endpoints.json:50-65` supplies the control-db failure case; the current gate asserts named degraded content at `verify_control_room_rendering.py:3133-3160` | `boards_degraded_operations_desktop_dark_1440x900.png` |
| Run detail raw identity, attempts, gates, approvals, and command receipts | `services.operations.run_detail():368-420`, delivered by `routes/operations.py:/api/runs/<run_id>` | `boards_endpoints.json:67-149`; `check_boards_fixtures():2595-2613` requires the raw keys | `boards_keyboard_drawer_dark_1440x900.png` and light equivalent |
| Cost provenance, including measured zero versus unknown | `services.run_evidence.cost_block():307-317` | `boards_endpoints.json:150-151,296-299`; `check_boards_fixtures():2614-2619,2636-2639` | Keyboard drawer captures |
| Independent measured verification, decision receipt, and agent narration | `services.run_evidence.evidence_block():319-330` | `boards_endpoints.json:153-157,300-303`; `check_boards_fixtures():2622-2623` | Keyboard drawer captures |
| Ledger pointer and presence, delivered knowledge, prepared-step reference, and timing states | `services.run_evidence.recorded_block()`, `delivered_knowledge_block()`, `prepared_block()`, and `timings_block()` | `boards_endpoints.json:158-245,305-330`; `check_boards_fixtures():2603-2613,2620-2628` | Keyboard drawer captures; the gate specifically asserts delivered ids, prepared path, and unknown timing |
| Bounded logs, state, match basis, event class/text, and follow target | `services.operations.read_run_logs():202-275` and `logs_block():45-99` | `boards_endpoints.json:247-274,332-339`; `check_boards_fixtures():2629-2635,2639-2642` | `boards_keyboard_drawer_logs_dark_1440x900.png` and light equivalent |

### Values derived in the browser or not rendered

The following table is the ownership inventory required before changing the room. “Should own”
means the authoritative service/read model that must emit the value or its named absence. It does
not mean that the browser cannot format a value for presentation; it means that the browser must
not decide the operational fact.

| Current value or omission | Current behavior | Service that should own it | Fixture assertion the gate should use | Capture |
|---|---|---|---|---|
| `attention.state` (`active` or `none`) | `app.js:3113-3136` infers membership in `attention` and exposes `active` primarily as `data-attention-state`; the L33 host failure showed that the asserted value was not visible text | `services.operations` should emit the state on each state-screen/run row; `app.js` should render that exact state as visible text | `boards_endpoints.json` should carry the state-screen row; `verify_control_room_rendering.py` should assert the visible text of `[data-field="attention.state"] [data-value]`, not only a data attribute | Operations capture, with the active attention value visible in the roster |
| `started.age` | `app.js:3171-3174` calls `formatAge()` and reads `Date.now()` in the browser | `services.operations` should emit a named age/age state from the injected packet time, or a named unknown; the browser may format an already-owned duration | Fixture carries `started_age` or an explicit unknown state; the gate asserts a stable fixture string, not a wall-clock result | Operations capture |
| Run ordering and “leading” attention order | `app.js:3368-3371` sorts active/promotable rows using client-side `runLeads()` | `services.operations` should emit the triage order and the state-screen order; the client should preserve it | Assert that rendered row ids equal the fixture's ordered `runs` ids, and that the `state_screens[i]` identity/order equals `runs[i]` | Operations capture; scrolling capture proves the ordered list remains reachable |
| Run lifecycle roster | `app.js:3085-3110` maps the shipped fleet vocabulary and turns unsupported states into an unknown chip; only active/promotable rows are displayed | `control_db.RunState` in `src/agentic_dynamics/control/control_db.py:140-182` is the lifecycle authority; `services.operations` should expose only reachable lifecycle states and named state screens | Fixture covers the required named `unknown`/missing-evidence case separately from lifecycle, plus `promotable`, `cancelled`, and `quarantined`; no `stalled` or `escalated` row is allowed without a real `RunState` or evidence contract | Operations capture; separate captures are needed for state variants if retained as acceptance claims |
| `run.live` and terminal target | `app.js:3175-3180` renders `unknown` because `/api/operations` does not carry these facets | `services.operations` should emit them from the packet/run record, or explicitly keep them out of the contract | Fixture includes measured live/terminal values and named unknown cases; gate asserts both visible labels | Operations capture |
| Attempt number | Hidden behind the labelled unknown path in `runFieldValue()` | `services.operations` should project the selected attempt number from run evidence/control records | Fixture supplies `attempt.number`; gate asserts the visible value and the unknown case | Operations capture |
| Cost provenance in the roster | Detail service owns it, but the Operations roster does not receive it and renders unknown | `services.run_evidence` should remain the derivation owner; `services.operations` should carry the block into each row if the roster claims it | Fixture row includes the provenance; gate asserts measured zero and unknown text in the roster, not only the drawer | Operations capture; drawer captures already show the detail value |
| Decision eligibility and receipt | Hidden as unknown in the roster; raw receipt exists in run detail | `services.run_evidence` for evidence/receipt and `services.operations` for row projection | Fixture includes eligibility/receipt and gate asserts visible text plus missing-state labels | Operations capture; drawer captures for raw receipt |
| Evidence advisory | Hidden as unknown in the roster although `run_evidence.evidence_block()` carries measured, receipt, and narration labels | `services.run_evidence` owns the distinction; `services.operations` owns its placement in the roster | Fixture carries all three evidence labels; gate asserts independent measured text is not replaced by narration | Operations capture and drawer captures |
| `safe_actions` | `services.operations` passes packet actions through at `:363`, but `app.js` never renders them; the static test intentionally documents this omission | `control_status.build_packet()` remains the authority; `services.operations` should either expose a clearly labelled read-only action list or remove it from this board contract | Fixture has safe actions and an explicit assertion that they are rendered, or a contract test asserts they are intentionally excluded from the Operations board | None today; no capture exists |
| Unhealthy-worker metric | `app.js:3304-3311` always renders `String((data.unhealthy_workers || []).length)`, so degraded/unobserved input becomes `0` | `services.context` must mark `unhealthy_workers` unavailable in `degraded` whenever heartbeat collection fails or was never observed; `services.operations` carries the named state | Degraded fixture includes `degraded: [{"surface":"unhealthy_workers",...}]`; gate asserts metric text is exactly `unavailable`, never `0` | Degraded Operations capture |
| Worker identity and age rows | Service emits `session_id` and `age_seconds`, but only the count is visible | `services.context`/packet owns the evidence; `app.js` should render rows or explicitly remove the fields from the contract | Fixture contains a worker row and gate asserts both identity and age, or a static contract test proves the fields are not advertised | None today |
| Failed-run state screen | Failed runs enter `attention`, but there is no separate failed state screen/roster | `services.operations` should project failed runs from `packet.failed_runs` without duplicating or renaming them | Fixture includes failed state-screen entries whose ids and order match the canonical run list | Operations capture |
| Cancelled and quarantined state screens | The control database can reach both terminal states, but the current Operations fixture manufactures only running/promotable rows | `control_db.RunState` plus `services.operations` should supply these actual rows; no browser-only states | Fixture contains real cancelled/quarantined rows and gate asserts their state labels and ids | Operations capture; dedicated captures if these remain acceptance claims |
| Stalled/escalated screens | These names are not members of `RunState`; presenting them would be manufactured state | Remove them from the state roster unless a durable service contract adds evidence and a reachable state | Gate asserts the roster is exactly the `RunState`-reachable set, with no `stalled`/`escalated` without evidence | None today |
| Telemetry liveness and age | `services.telemetry` computes `phases.live`, `last_phase_ts`, and `age_seconds`; `app.js` formats some values and computes rolling burn from samples | `services.telemetry` should own liveness/age; client owns only formatting and chart geometry | `parity_endpoints.json:/api/matrix:15-20` and the boards fixture carry live/age states; gate asserts live, stale, and age-unknown labels | Fleet and Status captures |
| Overall connection state, running count, spend, and burn | `app.js:220-269` derives these from retained matrix/SSE state and live samples; the UTC clock is local browser time | `services.telemetry` owns reported telemetry/provenance; `services.context`/route owns availability; the clock is presentation-only | `parity_endpoints.json:/api/matrix:4-51` asserts matrix inputs; gate should assert unavailable/retained-window labels, not a fabricated live cost | Fleet and Status captures; no stable capture for a specific clock value |
| Supervisor flag age and row status | `services.supervisor` normalizes flags and mapping state; `app.js` formats age from `last_activity_at` and maps the status vocabulary | `services.supervisor` should emit a named age/state; the browser may format it | `parity_endpoints.json:/api/flags:53-60` plus a stale/unavailable mapping case; gate asserts named state and age | Flags captures |
| Design-session row values | `services.design_sessions`/`routes/design_sessions.py` supplies the session list; the client normalizes display text | `services.design_sessions` owns identity, draft state, revision, model, and workdir label | `boards_endpoints.json:345-359` and fixture router mapping; gate asserts the visible session identity and draft state | Sessions captures |
| Routing recommendations, strategy totals, and percentages | `routes/telemetry.api_routing()` reads the canonical corpus and `compute_routing()` derives recommendations; the client formats tables and percentages | `routes/telemetry.py` plus `control.routing` should own all recommendation/strategy values; client owns table layout | `boards_endpoints.json:360-390`, `ROUTING_FIXTURE_ANCHORS` at `verify_control_room_rendering.py:2427-2435` | Routing desktop dark/light and narrow captures |
| Routing loading, delayed, and failed states | The gate drives them with router controls; the client settles into loading or named failure | `routes/telemetry.api_routing()` owns the error envelope; the fixture router owns deterministic delay/failure injection | `verify_control_room_rendering.py:2733-2745` and `_board_ready_js():2763-2783` assert settled behavior and named errors | No dedicated delayed/failed capture; the report records screenshotless checks |
| Surface quality/value/arms/SLA/escalation/batch/energy values | `services.context` calls projection services; `app.js` renders the returned panels and their degraded lists | The corresponding projection service in `services.context`/`agentic_dynamics.control.projections` owns each metric; client owns labels and layout | `boards_endpoints.json:392-552`, `BOARD_SURFACE_PATHS` at `verify_control_room_rendering.py:2410-2418`, and surface failure checks at `:3185-3241` | Surfaces desktop dark/light and narrow captures; no dedicated failure capture |
| Registry, subscription/admission, docs health, recording audit, and decisions | Their routes exist, but several are System or hidden surfaces; `/api/decisions` and `/api/recording-audit` have no current loader in the served board | Their existing route/service owners should remain authoritative; the room must either render them with named states or state that they are not part of the served contract | `parity_endpoints.json:62-115` covers fixture payloads, but no current acceptance assertion proves visible rendering for every one | No dedicated served-room capture for registry, usage, decisions, or recording audit |
| Run detail ledger JSON, raw gate/approval/command JSON, log timestamps/ids, live binding metadata, augmentation versions/tokens/cost | `services.operations` emits these fields, but `app.js` filters raw JSON and does not display several additive fields; the drawer renders only selected evidence | `services.run_evidence` and `services.operations` own the fields; the renderer must either show them with labels or remove them from the public contract | Extend `boards_endpoints.json` and the drawer probe to assert each retained field, or add a contract assertion that the field is deliberately not public | Drawer captures show the selected subset; no capture proves the hidden fields |
| Seven-board visibility, active destination, theme, density, and scroll reset | `shell.js` owns these client-only presentation states; no service should own them | `verify_control_room_rendering.py:2823-2884` checks one visible board, `aria-current`, and navigation; the report records the board captures | Seven board captures in dark/light and narrow routing/operations/surfaces captures |

## Gaps

1. The Operations fixture is a hand-authored twin. `build_operations_payload()` expands one seed
   into rows, while the production service passes through packet rows. The fixture can therefore
   assert a shape the service cannot emit. It checks that attention ids exist, but not that every
   state-screen row is the same run, in the same order, with the same state.
2. The roster is not aligned to `RunState`. The authoritative vocabulary is the twelve-value enum
   in `control_db.py:140-182`; the static renderer instead recognizes a smaller fleet vocabulary,
   and the current fixture only manufactures `running` and `promotable`. `stalled` and
   `escalated` must not be presented as lifecycle states without durable evidence. Reachable
   `unknown`, `promotable`, `cancelled`, and `quarantined` cases are not covered by the acceptance
   fixture.
3. A degraded worker source is rendered as healthy-looking `0`. The service already records a
   named `unhealthy_workers` degradation, but the renderer counts an empty list. This violates the
   room's named-state rule.
4. The host gate is the acceptance authority, but the candidate can satisfy an assertion through a
   hidden data attribute rather than visible text. The L33 `attention.state` failure is exactly
   this mismatch. `gate_report.json` in the repository is a passing different candidate and cannot
   repair the absent L33 artifact.
5. Several values are emitted but hidden: `safe_actions`, worker identities/ages, ledger presence,
   augmentation metadata, log timestamps/ids, live binding basis, and some route payloads. Hidden
   values are not automatically defects, but they must be declared either outside the served
   contract or rendered and asserted. Otherwise the notes, fixture, and gate disagree about what
   the room promises.
6. The current report explicitly omits mobile, forced-colors, contrast, first-paint, charts,
   visuals, style, accessibility, parity, live, and legacy interactions. Those omissions are safe
   only when no claim is made that those classes are accepted by this profile.

## Sources

The source ledger is machine-readable in `notes/sources.jsonl`. The primary sources are:

- `docs/reviews/loose_ends_register.md:55,145,147` for L23, L33, and L47 status and recorded findings.
- `apps/control_room/services/operations.py:1-19,326-421` for the one-packet read model, named states, attention projection, and run detail.
- `apps/control_room/services/context.py:124-196` for packet collection, worker degradation, and run-detail error behavior.
- `apps/control_room/services/telemetry.py:20-24,131-211,252-289` for retained telemetry, phase liveness, and age provenance.
- `apps/control_room/services/run_evidence.py:307-513` for cost, evidence, ledger, knowledge, prepared-step, and timing derivations.
- `apps/control_room/services/supervisor.py:95-161` for flag normalization, mapping state, and degraded source behavior.
- `apps/control_room/routes/operations.py:1-41` and `routes/telemetry.py:71-331` for route ownership and delivery.
- `apps/control_room/static/app.js:144-183,2944-3397` for client-side formatting, Operations rendering, and the current hidden/derived fields.
- `apps/control_room/static/shell.js:27-177` and `board-fleet.js:39-160` for board navigation and lifecycle/attention vocabularies.
- `apps/control_room/verification/fixtures/boards_endpoints.json` and `parity_endpoints.json` for deterministic payloads.
- `scripts/verify_control_room_rendering.py:1844-1854,2398-2784,2823-2884` for the acceptance profile, fixture router, and navigation/loading contract.
- `apps/control_room/verification/gate_report.json:1-293` for the currently committed, different passing report and its capture inventory.
- `src/agentic_dynamics/control/control_db.py:140-234` for the exact `RunState` vocabulary and transition graph.
- `tests/test_control_room_operations.py:73-165` and `tests/test_control_room_static_views.py:97-204` for current service/render invariants.
