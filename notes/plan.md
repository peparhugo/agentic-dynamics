# Control Room Detail Truth Plan

## Files

- `apps/control_room/services/operations.py`: make the Operations read model the owner of the
  state-screen/run-row projection, visible attention state, stable triage order, and any roster
  facets the board claims. Preserve the packet's identifiers and named availability states; do not
  derive a second authority from browser membership.
- `apps/control_room/services/context.py`: distinguish a readable empty worker list from an
  unobserved or degraded heartbeat source. Add `{"surface": "unhealthy_workers", "reason": ...}`
  whenever the source is unavailable, so the renderer has evidence for `unavailable`.
- `src/agentic_dynamics/control/control_db.py`: use `RunState` as the lifecycle vocabulary. Do
  not add `stalled` or `escalated` to the UI roster unless the control database and transition
  graph gain durable, reachable states for them. The safer default is to remove those manufactured
  states from the room's contract.
- `apps/control_room/static/app.js`: render service-owned `attention.state` as visible text,
  render the service-owned ordering without resorting, and render `Unhealthy workers` as
  `unavailable` when the packet says the source is degraded or unobserved. Keep formatting and DOM
  layout client-side, but not operational causation.
- `apps/control_room/verification/fixtures/boards_endpoints.json`: replace the twin-like
  Operations seed with a documented service-contract fixture, or add explicit `runs` and
  `state_screens` arrays whose identity and order are checked against one another. Add reachable
  unknown/promotable/cancelled/quarantined cases and a degraded worker-health case.
- `scripts/verify_control_room_rendering.py`: strengthen deterministic fixture checks and the host
  browser assertions. The gate must inspect visible text, not only `data-*` attributes, and must
  produce candidate-bound captures for every visual claim.
- `tests/test_control_room_operations.py`: extend packet/read-model parity tests to cover the
  state-screen/run invariant, the complete reachable state roster, and degraded worker health.
- `tests/test_control_room_static_views.py` and `tests/test_control_room_feature_parity.py`:
  pin the renderer's visible `attention.state` contract and the unavailable worker metric without
  relying on the parked workbench implementation.
- `apps/control_room/verification/gate_report.json`: regenerate only through the host acceptance
  run, with the actual candidate identity and capture paths. Do not copy the current report into an
  L33 result directory or treat a different candidate's PASS as evidence.
- `notes/sources.jsonl`: retain the source paths and evidence roles for this plan; the missing
  requested L33 report is recorded as missing rather than silently replaced.

## Tests

- Run the focused service tests: `pytest tests/test_control_room_operations.py -q`.
- Run the static contract tests: `pytest tests/test_control_room_static_views.py tests/test_control_room_feature_parity.py -q`.
- Run the deterministic fixture check through the render gate before browser work. It must fail if
  an attention/state-screen row has no corresponding run, if order differs, if a fixture names a
  lifecycle outside `RunState`, or if degraded worker health has no named state.
- Run the host browser acceptance against the exact candidate: `python3 scripts/verify_control_room_rendering.py --profile acceptance --candidate <candidate-sha>`.
- Inspect the generated report and every capture. A screenshotless check may prove behavior, but a
  visual claim about a rendered value requires a non-empty, candidate-bound capture.
- Confirm the host gate's served-asset identity check succeeds. The browser must exercise the same
  candidate whose SHA is recorded in the report, not the working tree or a different preview.

## Acceptance

- The acceptance report has `status: PASS`, `candidate_verified: true`, `preview_verified: true`,
  `preview_exercised: true`, and `preview_serves_candidate: true`.
- `requested_classes` and `executed_classes` are exactly `navigation`, `loading`, `degraded`,
  `scrolling`, and `keyboard`; no class is omitted or inherited from another report.
- The Operations fixture is tied to the production contract. The chosen invariant is explicit:
  for every index `i`, `state_screens[i].run_id == runs[i].run_id` and
  `state_screens[i].state == runs[i].state`; the rendered row order equals the fixture order.
- The visible Operations roster covers only the `RunState`-reachable lifecycle vocabulary. It
  demonstrates the named `unknown`/missing-evidence case separately from lifecycle, plus
  `promotable`, `cancelled`, and `quarantined` where those records are supplied, and it contains no
  manufactured `stalled` or `escalated` state.
- The active attention row visibly contains the literal `active` in the `attention.state` value
  element. A data attribute alone is not acceptance evidence.
- The degraded Operations screen visibly renders `Unhealthy workers` as `unavailable` when
  heartbeat evidence is degraded or unobserved. It must not render `0` for that case.
- The Operations, degraded Operations, drawer, log drawer, Fleet, Status, Flags, Sessions,
  Routing, and Surfaces captures exist where the report claims them, are readable, and are bound to
  the candidate under review.
- The named-state rule holds throughout: `recorded`, `unbound`, `unavailable`, `unknown`, and
  measured zero remain distinct; no missing read becomes a fabricated zero, blank, or all-clear.

## Risks

- A fixture generated by a separate helper can still drift from `services.operations` while looking
  structurally valid. The identity/order assertion is mandatory even if the fixture remains static.
- Expanding the state roster without checking `RunState` transitions would reintroduce the exact
  manufactured-state problem identified by the adversarial review.
- A client-only age calculation can pass a screenshot at one instant and fail deterministically at
  another. Use injected service age or assert only named age states in the browser.
- The worker count can look correct in healthy fixtures while hiding a degraded source. The degraded
  fixture must omit or invalidate the source and assert `unavailable`, not merely test a non-empty
  worker list.
- A workflow/container test can pass while host browser acceptance fails because Playwright is not
  available in the fleet image. Host acceptance remains a separate pre-promotion obligation.
- The current committed `apps/control_room/verification/gate_report.json` can be mistaken for the
  absent L33 artifact. Candidate identity and report path must remain explicit in every review.
- Rendering every emitted field would overload the resting screen. For each retained hidden field,
  choose explicitly between a labelled rendering, a deeper drawer surface, or removal from the
  public contract; do not leave the choice implicit.

## Remediation

1. **Fixture contract or state-screen/run invariant.** Update
   `apps/control_room/verification/fixtures/boards_endpoints.json` and
   `scripts/verify_control_room_rendering.py:check_boards_fixtures()`. The fixture must expose
   canonical `runs` and `state_screens` arrays, and the check must assert, for every index `i`,
   `state_screens[i]["run_id"] == runs[i]["run_id"]`,
   `state_screens[i]["state"] == runs[i]["state"]`, and the rendered row ids preserve that same
   order. This closes the P1 twin fixture finding without requiring a hand-authored payload the
   service could never emit.
2. **RunState-reachable roster.** Update `src/agentic_dynamics/control/control_db.py` only if a
   durable state is genuinely missing; otherwise update `services.operations.py`,
   `app.js`, the fixture, and the focused tests to use the existing twelve-value `RunState` enum.
   The proving assertion belongs in `scripts/verify_control_room_rendering.py` and should compare
   every lifecycle fixture state to `{state.value for state in RunState}` while requiring the
   separate named-absence fixture for `unknown` plus lifecycle coverage for `promotable`,
   `cancelled`, and `quarantined`. Add an explicit negative assertion that `stalled` and
   `escalated` are absent unless a real service evidence field is present.
3. **Degraded `Unhealthy workers`.** Update `apps/control_room/services/context.py` to mark worker
   health unavailable when `read_worker_heartbeats()` is degraded/unobserved, and update
   `apps/control_room/static/app.js:3304-3311` to render `unavailable` whenever the packet has the
   named `unhealthy_workers` degradation. Add the degraded fixture in
   `boards_endpoints.json` and assert in `verify_control_room_rendering.py` that the metric text is
   exactly `unavailable` and is not `0`. Capture the result in
   `boards_degraded_operations_desktop_dark_1440x900.png`.
4. **Host-satisfiable browser assertions.** Update
   `apps/control_room/static/app.js:3113-3136` so the service-owned attention state is visible
   text, not only `data-attention-state`. Update the acceptance gate in
   `scripts/verify_control_room_rendering.py` to assert the visible text `active` in the
   `attention.state` value node and to retain a non-empty Operations capture. Run the gate on the
   host with `--candidate <candidate-sha>` and inspect the served-asset identity fields before
   promotion. This directly prevents the L33 failure where the gate asserted a value the candidate
   exposed only through an attribute.
