# Control Room Detail Truth Posterior

## Violations

- The host acceptance contract is not proven in this cell. The required command
  `python3 scripts/verify_control_room_rendering.py --profile acceptance --candidate a381de35839af87ca1842a4f352fcf023a7acd11`
  stopped with `playwright is not installed`. It did run the browser-free fixture check, but it
  produced no browser captures. L47 therefore remains open; the in-cell pytest result is not a
  substitute for host acceptance.
- L33 remediation item 2 is only partial. `operations.py` maps `running`, `verifying`,
  `promoting`, and `projecting` to the `running` screen, and it maps `awaiting_approval`,
  `failed`, `promotable`, `merged`, and `published` to named screens. The fixture covers
  `queued` (the `unknown` case), `promotable`, `cancelled`, and `quarantined`, and the test covers
  a heartbeat-backed `stalled` observation. However, the fixture does not include the reachable
  `verifying`, `promoting`, or `projecting` states, and there is no exhaustive assertion over
  `RUN_STATE_ROSTER`. `RUN_STATE_ROSTER` is declared in `operations.py` but is not used as an
  exhaustive gate. The proof is therefore coverage of selected states, not proof of the complete
  `RunState` roster.
- L33 remediation item 3 is partial at the renderer boundary. The service emits the named
  `worker_health` block and the degraded fixture sets `state: unavailable`, `value: unavailable`.
  The browser-free degraded assertion checks the visible metric. However, `renderOperations()`
  still falls back to `String(unhealthyWorkers.length)` when `worker_health` is missing or has no
  value. A malformed or omitted server block can therefore still become a fabricated count in
  the client. The intended invariant, "unobserved or degraded workers never render as 0", is
  proven only for the normal payload shape.
- The plan called for a named server-owned triage/order basis. The client-side `Array.sort()` was
  removed, and the service now delivers `db.runs()` order, but no explicit order-basis field or
  assertion exists. The fixture proves that `runs` and `state_screens` preserve identical ids in
  identical order; it does not prove why that order is the operator's triage order.
- The plan inventory identified row values already available through glance, including
  `run.live`, `terminal.target`, `attempt.number`, cost/evidence fields, decision eligibility,
  and decision receipts. They were not added to the Operations roster in this execute commit.
  `runFieldValue()` still renders those fields as labelled `unknown` because the Operations
  payload does not carry them. This is a scoped omission, not evidence that the values are absent
  from the control plane.

## Unknowns

- Whether the host browser profile passes against candidate `a381de35839af87ca1842a4f352fcf023a7acd11`
  is unknown. The host-side Playwright environment and its capture directory are outside this
  in-cell result, and no capture was fabricated.
- Whether the served Operations page renders every `state_screens` row without clipping or
  browser-only console errors is unknown. The browser-free gate checks the payload and renderer
  source, not the host layout engine.
- Whether `db.runs()` ordering is the intended operational ordering is unknown. The landed code
  preserves that database order and prevents a second client policy, but the current contract
  does not name or independently test the ordering basis.
- The historical failed `L33_candidate_f7ab43551/gate_report.json` is not present in this
  checkout. The prior failure description is supported here by the workflow context and the
  preserved register, not by a locally readable report artifact.

## UPDATES

### Server-owned values

- Attention state moved into the Operations row projection. `project_run_rows()` writes
  `row["attention"]` with `state: active|none`, kind, and reason from the service's attention
  projection. The fixture is expanded through the same helper in
  `scripts/verify_control_room_rendering.py:build_operations_payload()`, and the fixture check
  verifies every row has an `active` or `none` state. The browser-free check passed:

  ```text
  fixture check PASS (F-0..F-7 legacy + boards)
  ```

- Run age moved into the service projection. `_age_seconds()` and `_age_label()` in
  `apps/control_room/services/operations.py` use the injected/server-side projection instant;
  `app.js` reads `started_age` and does not call its former client clock formatter for Operations
  rows. The fixture uses a fixed instant and the drawer fixture carries `4d ago`; the fixture
  check requires that drawer value and every roster row's `started_age`. The same fixture-check
  output above is the available deterministic proof.
- State-screen values moved into the service projection. Each emitted row carries
  `state_screen`, and `operational_snapshot()` emits the parallel `state_screens` list. The
  fixture builder calls `project_run_rows()` and then derives `state_screens` from the resulting
  rows; `check_boards_fixtures()` asserts equal lengths and identical ordered run ids. The
  Operations renderer visibly includes the `State screens` table, and its loading assertion
  requires visible `active`, `cancelled`, `quarantined`, and `promotable` text. The fixture check
  passed, but host visibility remains unproven because the browser profile could not start.
- Worker availability moved into the service's `worker_health` block. `_worker_health()` returns
  `unavailable` when the packet has a degraded `unhealthy_workers` source, while the context
  failure path also emits a named unavailable block. `operations_degraded` carries the fixture
  case and the browser-free degraded check requires the visible `Unhealthy workers` metric to be
  `unavailable`. The declared five-suite run and fixture check passed; the host capture is still
  missing.
- Attention visibility moved from metadata-only to visible text. `runAttentionValue()` now paints
  `active` beside the attention kind, and the loading gate searches `operationsText` for the
  literal `active`. This directly addresses the L33 assertion failure, subject to host proof.

### L33 remediation status

- Item 1, service-plausible fixture: landed with a bounded proof. The fixture builder uses the
  service's pure `project_run_rows()` helper rather than hand-authoring derived row fields, then
  derives `state_screens` from those rows. The gate asserts equal lengths, identical ordered ids,
  attention references to emitted runs, and presence of service-owned age/attention fields. The
  invariant is in `check_boards_fixtures()` and passed. Full object equality is not separately
  asserted because the fixture list is generated from the same projected rows.
- Item 2, reachable state roster: partially landed. `operator_state_for_run()` uses the imported
  `RunState` values and refuses to invent `escalated`; `stalled` requires positive stale-heartbeat
  evidence. The operations test proves `stalled`, `unknown` for `cancelled` and `quarantined`,
  and `unavailable` worker health. The missing exhaustive `RUN_STATE_ROSTER` assertion and the
  absent fixture rows for `verifying`, `promoting`, and `projecting` are the remaining gap.
- Item 3, degraded worker rendering: landed for the declared degraded fixture. The service emits
  a named unavailable state, the fixture carries it, and the gate asserts
  `probe.metrics["Unhealthy workers"] == "unavailable"`. The client fallback for a missing or
  malformed `worker_health` block means the stronger fail-closed renderer invariant has not
  landed completely.
- Item 4, host-satisfiable visible assertions: landed in source and browser-free checks, not in
  acceptance evidence. The renderer visibly emits `active`, and the gate checks visible text
  rather than `data-attention-state`. The host command was attempted and refused by the missing
  Playwright dependency; therefore no acceptance capture or candidate-bound PASS exists in-cell.

### In-cell acceptance evidence

- Fixture contract: `python3 scripts/verify_control_room_rendering.py --check-fixtures` passed
  with `fixture check PASS (F-0..F-7 legacy + boards)`.
- Declared room suites: the exact five workflow targets passed with `76 passed in 23.51s`:
  `test_control_room_operations.py`, `test_control_room_glance_integrity.py`,
  `test_control_room_build_contract.py`, `test_control_room_static_views.py`, and
  `test_control_room_paths.py`.
- Capture guard: `python3 -m pytest tests/test_render_gate_captures.py -q` passed with
  `17 passed, 1 skipped`. This verifies the zero-capture guard itself; it does not create or
  substitute for host captures.
- Host acceptance: attempted against the exact candidate, but returned
  `playwright is not installed; run with --check-fixtures for the browser-free check`. No
  capture artifacts exist in-cell, so the candidate is not accepted by L47.

### Remaining client-side work

- DOM construction, labels, glyphs, and table text remain client-side because they are rendering
  concerns over already-owned values. The renderer no longer chooses the Operations row order or
  computes age from `started_at`.
- `attentionByRun` remains a client lookup fallback for payloads that lack the row attention
  block. It preserves compatibility with the packet attention list, but strict server ownership
  would remove the fallback and render a named unknown when the row projection is absent.
- `renderOperations()` still has a raw-list fallback for worker counts. It should instead render
  `unavailable` whenever `worker_health.state` is not the recognized recorded state.
- Summary counts are still displayed from client array lengths. They are presentation counts of
  the server-delivered arrays, not new causal decisions, but a future contract can expose explicit
  server count fields if the room needs those values to be independently auditable.
- The roster fields not emitted by `/api/operations` remain labelled `unknown` rather than being
  re-derived from the parked glance renderer. This preserves the selection/delivery boundary;
  exposing them requires an additive Operations read-model contract and fixture evidence first.
