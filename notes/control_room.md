# Control Room Detail Truth

## Problem

The L23 candidate improved the served Control Room's resting layout, but its adversarial caveats
remain real. The room still has two sources of presentation truth: the server exposes the control
packet and run evidence, while `app.js` derives attention membership, ordering, and started age in
the browser. The Operations roster also contains fields whose values already exist in the glance
read model or the run ledger, but renders them as labelled `unknown` because `/api/operations`
does not carry them.

This is not only a visual omission. A client-side `Date.now()` calculation can disagree with the
server snapshot, and a client-side sort can reorder runs without a named server decision. Hiding a
packet value behind `unknown` is also misleading when the authoritative service already measured
it. The repair must therefore make the Operations read model the owner of the complete row view,
while keeping the browser as a formatter and interaction layer.

The honesty rule is non-negotiable: every service/read-model value must have a named state such as
`recorded`, `unbound`, `unavailable`, `unknown`, or `not_established`. Missing evidence is never a
fabricated zero, and selection/delivery is never model use.

## What Exists

### Read-model ownership

| Value or state | Current owner and behavior | Fixture assertion | Existing capture |
|---|---|---|---|
| Packet schema, control epoch, repository HEAD | `services/operations.py:204-243` passes `control_status.build_packet()` metadata through `source`; `app.js:3236-3257` renders the truth strip. | `boards_endpoints.json:operations.source` carries `control_epoch` and `repo_head_sha`; the fixture gate requires the operations seed. | `boards_operations_desktop_dark_1440x900.png`, `boards_operations_desktop_light_1440x900.png`, and `boards_operations_narrow_dark_1024x768.png`. |
| Active, failed, and promotable run references | `control_status.build_packet()` is authoritative; `services/operations.py:218-243` passes `active_runs` and `promotable_runs` without inventing rows. | `boards_endpoints.json:operations.run_seed`, `active_count`, and `promotable_count`; `check_boards_fixtures()` requires at least 12 expanded rows. | The three Operations navigation captures above. |
| Decisions owed / attention entries | `services/operations.py:220-225` projects packet approvals and failures into `attention`; the current client builds `attentionByRun` and the chip in `app.js:3293-3298,3113-3136`. | `boards_endpoints.json:operations.attention` contains approval and promotion entries whose run ids must exist in the expanded row set. | Operations captures show the attention table; the exact row-level chip is in the Operations captures. |
| Degraded control database and named reasons | `services/context.py:124-165` and `operations_snapshot()` return HTTP 200 with a `degraded` entry instead of a 500; `app.js:3300-3331,3333-3358` renders the reason. | `boards_endpoints.json:operations_degraded` requires `surface: control_db`, empty run blocks, and a named reason. | `boards_degraded_operations_desktop_dark_1440x900.png`. |
| Projection lag counts | `services/operations.py` passes packet `projection_lag`; `app.js:3236-3257,3384-3391` sorts the keys and renders the count. | `boards_endpoints.json:operations.projection_lag` contains `chroma`, `ledger`, `neo4j`, and `registry` values. | Operations captures show the Projection lag block. |
| Unhealthy-worker count | The packet owns the list, but `app.js:3303-3311` derives `length` in the browser and displays only the count. | `boards_endpoints.json:operations.unhealthy_workers` contains a stale worker with `session_id` and `age_seconds`; current fixture coverage proves input presence, not row-level rendering. | Operations captures show only the aggregate metric, not the worker identity or age. |
| Safe actions | `services/operations.py:241` passes `safe_actions`, derived by the control-status transition graph, but the Operations renderer does not display them. | `boards_endpoints.json:operations` does not yet carry a non-empty `safe_actions` case; add one to the normal operations fixture and assert the action binding. | No current capture proves safe-action rendering. Required future capture: `boards_operations_actions_desktop_dark_1440x900.png`. |
| Fleet lifecycle status and urgency order | Fleet lifecycle vocabulary and ordering are in `static/board-fleet.js:45-127`; this is valid for the Fleet board because it operates on matrix cells. | `F-0.json:run_counts`, `run_sample`, and the `F-0..F-7` fixture deltas exercise lifecycle/risk ordering. | `boards_fleet_desktop_dark_1440x900.png` and the other navigation captures. |
| Phase liveness and phase age | `services/telemetry.py:301-355` computes `last_phase_ts`, `age_seconds`, and `live` from phase/tail timestamps with an injected `now`; `app.js:493-514,542-569` formats those values. | `parity_endpoints.json:/api/matrix.phases` contains both a live recent phase and an old phase with explicit ages; the restored board fixture exercises the served phase path through the matrix endpoint. | `live_desktop_dark_1440x900.png` and `live_narrow_dark_1024x768.png` are legacy parked captures, not acceptance-profile proof for the served Operations roster. |
| Run-detail cost provenance | `services/run_evidence.py:95-183,307-316` owns aggregate cost and provenance; `operations.run_detail()` attaches `cost`; the client only labels it. | `boards_endpoints.json:run_detail.cost.provenance` must be the measured-zero case `$0.0000 · metered`; the unknown detail case must be `unknown`. | `boards_keyboard_drawer_dark_1440x900.png` and `boards_keyboard_drawer_light_1440x900.png`. |
| Run-detail evidence, receipt, narration | `services/run_evidence.py:244-329` keeps independent measured verification, decision receipt, and agent narration separate; `app.js:3488-3497` renders separate lines. | `boards_endpoints.json:run_detail.evidence` requires independent tests passed; the fixture also carries receipt and narration labels. | The two keyboard drawer captures above. |
| Delivered knowledge and prepared-step reference | `services/run_evidence.py:364-450` owns selection/delivery and prepared-step state; `app.js:3545-3618` explicitly says use is not established. | `boards_endpoints.json:run_detail.delivered_knowledge` requires selected evidence ids; `prepared.phases` requires a recorded path/hash. | `boards_keyboard_drawer_logs_dark_1440x900.png` and `boards_keyboard_drawer_logs_light_1440x900.png` show the lower drawer evidence. |
| Timing values and unknown timing state | `services/run_evidence.py:453-513` emits measured/unknown rows and preserves measured zero; `app.js:3621-3660` formats without calculating duration. | `boards_endpoints.json:run_detail.timings` must contain both measured and `unknown` rows. | The keyboard drawer captures are the current timing proof. |
| Job logs, binding basis, and capped history | `services/operations.py:45-153` owns `recorded`, `unbound`, and `unavailable` log states and names `by_run_id` versus `by_spec_time`; `app.js:3691-3727` renders that state. | `run_detail.logs` is `recorded` with `cell_id`, `match`, events, and cap metadata; `run_detail_unknown.logs` is `unbound`; the service error path is `unavailable`. | The two `boards_keyboard_drawer_logs_*` captures prove the recorded tail; the unbound/unavailable branches currently have no capture. |
| Surface-panel state and partial failure | `context.py` owns analytic service access; `app.js:3787-3813,3826-3840` renders each panel independently and names a failed URL. | `boards_endpoints.json:surfaces` carries all seven panels; the gate's `surface_failures` path asserts a named failed panel while siblings render. | `boards_surfaces_desktop_dark_1440x900.png`, `boards_surfaces_desktop_light_1440x900.png`, and `boards_surfaces_narrow_dark_1024x768.png`. |

### Values currently derived or hidden in the client

The Operations roster is the specific L23 problem surface. `RUN_FIELDS` declares the intended
facets in `app.js:3024-3047`, but `runFieldValue()` only reads a subset from each packet row:

- `session.identity`, `spec.cell`, `model.provider`, `phase.progress`, `lifecycle.state`, and
  `source.commit` are rendered from the Operations packet row.
- `attention.state` is derived from top-level attention membership and `kind`, rather than being
  a server-owned field on the row.
- `started.age` is derived from `started_at` with browser `Date.now()` in `formatAge()`.
- `run.live`, `terminal.target`, `attempt.number`, `cost.provenance`, `decision.eligibility`,
  `decision.receipt`, `evidence.advisory`, `evidence.measured`, and `evidence.source` all fall
  through to the literal `unknown` because the Operations payload does not emit them, even though
  `routes/glance.py:_run_row()` and `services/run_evidence.py` already have the corresponding
  records or derivations.
- `renderOperations()` derives `active.length`, `attention.length`, `promotable.length`, and
  `unhealthy_workers.length`. It also sorts active plus promotable rows with `runLeads()` before
  rendering. These are presentation decisions that should arrive as a server-owned ordered row
  projection, not be recomputed from partial payloads in the browser.
- `safe_actions` is returned by the read model but hidden entirely by the Operations board.
- Worker identity/age, projection health/age/error details, and per-row action eligibility are
  reduced to aggregate counts or omitted. The packet has more information than the table exposes.

The correct boundary is not to move every UI string server-side. The service owns facts, named
states, ordering, and age calculations; the browser may still format an already measured number,
choose table markup, and manage focus. This keeps the rendered result deterministic for a fixed
packet and injected clock while preserving the existing accessibility behavior.

## Gaps

1. **Server-side row projection is incomplete.** Add an Operations row projection that reuses the
   `run_evidence` derivations and carries the full declared roster facets, including a named age
   state and the packet's action eligibility. The service must not infer a worktree, cell id, use,
   or causation when the record is absent.
2. **Attention/order/age are split across planes.** `attentionByRun`, `runLeads()`, the stable
   client sort, and `formatAge(started_at)` should be replaced with service-owned values. Preserve
   packet order as the tie-breaker after the service's explicit urgency order; do not invent a
   causality claim from display order.
3. **Existing values are hidden.** The Operations table should render target, attempt, live state,
   cost provenance, evidence, receipt, eligibility, and source commit from the server row. A value
   that is not present must carry `unknown` plus its reason, not become a blank or zero.
4. **Safe actions and worker details are omitted.** Render the packet's `safe_actions` with the
   exact run/gate/candidate binding, and render unhealthy-worker identity plus age as a named
   detail block. These are selection and delivery/eligibility facts, not evidence that an action
   caused a run transition.
5. **Projection health is under-described.** The Operations view currently shows lag numbers but
   not the projection health state, age, or last error. Extend the service payload or add a
   service-owned projection detail block so `current`, `lagging`, `stale`, `failing`, and `unknown`
   remain distinguishable.
6. **Required state screens are only partially captured.** The gate covers loading, degraded,
   populated, scrolling, and the recorded run drawer. It does not capture an empty healthy
   Operations screen, a run with unbound logs, an unavailable log store, an unknown ledger, or a
   safe-action row. Add deterministic fixture variants and capture cases before claiming the
   required state profile is complete.
7. **Acceptance metadata is historical, not the next candidate's proof.** The committed report
   records 23 captures for the L23 candidate (`489b0bf...`), but a new candidate must run
   `--profile acceptance --candidate <sha>` and produce candidate-bound captures again. The
   container/browser limitation recorded in the L23 row means host execution is acceptable only
   when the report binds the exercised target and captures to the candidate.

## Sources

The detailed source ledger is `notes/sources.jsonl`. The primary authority is the current
read-model code and the committed fixture/gate contract; the L23 register row is used for the
preserved adversarial finding because the candidate's ignored run-clone notes are not reachable in
this checkout.
