# Control Room Detail Truth Plan

## Files

The implementation should start from the current `main` checkout. The archived L33 candidate is
evidence only and must not be edited or copied as a base.

### Read-model ownership

- `apps/control_room/services/operations.py`: add the server-owned Operations row projection,
  attention state, deterministic triage order, age state/value, state-screen roster, and worker
  health block. Preserve raw packet identifiers and the named-availability contract. Keep the
  function pure for fixed database, heartbeat, and `now` inputs.
- `apps/control_room/services/context.py`: preserve the composition-root behavior and ensure a
  worker-heartbeat read failure reaches Operations as a named degraded source rather than an
  empty healthy list.
- `apps/control_room/services/run_evidence.py`: reuse existing cost, evidence, receipt, and
  timing derivations. Do not introduce a second browser-shaped implementation of those rules.
- `apps/control_room/routes/operations.py`: keep the route as transport. Add no derivation here;
  the route should continue to return the service payload and status.
- `apps/control_room/routes/glance.py`: if a shared row helper is needed, move the common pure
  projection below the service boundary and keep glance-specific assembly in the route. The
  route must not become a second authority for Operations order or state.
- `src/agentic_dynamics/control/control_status.py` and `control_db.py`: use the existing packet
  and `RunState` vocabulary. Do not add `stalled` or `escalated` enum values merely for UI
  convenience. If those operator screens remain, attach them to explicit heartbeat/attempt
  evidence and label them as observations.

### Fixtures and browser renderer

- `apps/control_room/verification/fixtures/boards_endpoints.json`: make the Operations seed
  service-plausible. Add server-owned row fields, both attention states, fixed age data, the
  worker-health/degraded case, and `state_screens` generated from or identity-checked against
  the same run seed. Keep the existing measured-zero, unknown timing, recorded logs, and error
  detail cases.
- `scripts/verify_control_room_rendering.py`: make `check_boards_fixtures()` verify the actual
  service contract and the `state_screens[i] <-> runs[i]` identity/order invariant. Extend the
  degraded browser check to inspect the visible `Unhealthy workers` value. Extend the loading
  check to inspect visible server-owned attention and age values. Keep candidate SHA binding and
  zero-capture failure behavior.
- `apps/control_room/static/app.js`: consume the emitted Operations values. Remove client-side
  attention/order/age decisions. Render `attention.state` as visible text, not only a
  `data-*` attribute. Render worker health as the named state from the service. Keep DOM wiring,
  keyboard focus, and row click-through unchanged.
- `apps/control_room/static/index.html`: change markup only if the renderer needs an explicit
  state-screen or worker-health region. Preserve the one-visible-board and one-instance ID
  invariants.
- `apps/control_room/static/shell.js` and `board-fleet.js`: change only if the new Operations
  state labels need shared vocabulary. Do not reuse the Fleet heuristic `stalled` token as a
  database lifecycle state.

### Contract anchors

- `tests/test_control_room_operations.py`: assert server-owned attention, order, age state,
  worker-health degradation, state-screen identity/order, and RunState-reachable roster values.
- `tests/test_control_room_static_views.py`: update the deliberate read-contract anchors if a
  packet field is renamed or moved, and assert visible rendering anchors for attention and worker
  health. This update must be in the same commit as any renderer rename; attempt eleven proved
  that otherwise the declared suite fails.
- `tests/test_control_room_feature_parity.py`: preserve Operations labels, degraded rendering,
  row click-through, and the loaded script contract.
- `tests/test_control_room_glance_integrity.py`: preserve unknown-not-zero behavior and verify
  shared row evidence has not diverged between glance and Operations.
- `tests/test_control_room_build_contract.py` and `tests/test_control_room_paths.py`: retain the
  workflow and repository-root contracts declared by L33.
- `tests/test_control_status.py`: retain packet key order, null-not-zero projection lag, and
  unobserved worker degradation assertions.

## Tests

Run these browser-free checks from the final candidate, not from an earlier phase commit:

```text
python3 scripts/verify_control_room_rendering.py --check-fixtures
pytest tests/test_control_room_operations.py
pytest tests/test_control_room_glance_integrity.py
pytest tests/test_control_room_build_contract.py
pytest tests/test_control_room_static_views.py
pytest tests/test_control_room_paths.py
```

The declared five-suite gate is an all-green requirement. A skipped or zero-target test phase is
not evidence. The final renderer must also satisfy the relevant packet guards in
`tests/test_control_status.py` and the static feature-parity guards.

The host-only browser check is separate and must run against the exact candidate:

```text
python3 scripts/verify_control_room_rendering.py --profile acceptance
```

It must record the acceptance classes, screenshots, candidate identity, and no browser assertion
that the renderer cannot satisfy. Playwright must not be installed in the fleet container and
captures must not be fabricated.

## Acceptance

Acceptance is both a data contract and rendered evidence.

- `operations.py` emits all Operations row values the board claims, with the packet as the
  authority and named `unknown`/`unavailable` states for absent or unreadable evidence.
- Attention state, row order, and age are server-owned. The browser may create DOM nodes and
  format already-owned text, but it cannot choose urgency, causation, lifecycle, or freshness.
- The fixture checker proves that every `state_screens[i]` refers to the same run identity and
  position as `runs[i]`, or the fixture is generated directly from the service payload.
- The state roster is reachable from `control_db.RunState`. `stalled` and `escalated` are either
  backed by explicit heartbeat/attempt observations or absent from the served lifecycle roster.
  The fixture covers `unknown`, `promotable`, `cancelled`, and `quarantined`.
- A degraded or unobserved worker source renders `Unhealthy workers: unavailable`, never `0`.
  An observed empty unhealthy list may render a measured healthy value, but only when the packet
  says the worker source was observed.
- The loading capture visibly contains the server-owned `active` attention value and any other
  asserted row values. The gate must inspect visible text, not `data-attention-state` or another
  metadata attribute.
- The degraded capture visibly contains the named control-database reason and the unavailable
  worker value while preserving independent sibling panels.
- The acceptance report contains captures for the requested classes. Zero captures is a
  structural failure even when fixture checks pass.
- The five declared suites are green on the final commit, including any intentionally updated
  static anchor suite. A green in-cell run without the host acceptance is not promotable evidence.

## Risks

- A fixture can become a hand-authored twin that passes while the service cannot emit it. The
  identity/order invariant or generation step is the mitigation.
- A UI label can accidentally mint a lifecycle state. `RunState` membership and explicit
  observation-backed mapping are the mitigation.
- `[]` can be mistaken for observed health. The service's degraded note and the renderer's
  `unavailable` branch are required together.
- Moving a packet field can make the static anchor suite fail late, as in attempt eleven. Update
  its anchor deliberately in the same commit and rerun all five suites.
- A browser gate can pass against stale JavaScript or a different candidate. Candidate binding,
  served-JS identity checks, host execution, and capture paths are required.
- The current `parity.js` is parked and unserved. It must not be used as evidence for the served
  restored room, and changing it does not fix `app.js`.
- Clock-derived age can be nondeterministic. Inject `now` into the service and use fixed fixture
  timestamps; the browser must not calculate a different age from its own clock.

## Remediation

### 1. Service-plausible fixture or identity/order invariant

Files: `apps/control_room/verification/fixtures/boards_endpoints.json`,
`scripts/verify_control_room_rendering.py`, and `tests/test_control_room_operations.py`.

Preferred implementation: generate the fixture's `state_screens` and run rows from one service
read-model seed. If the deterministic gate must retain JSON fixtures, add a check in
`check_boards_fixtures()` that, for every index, asserts:

```text
state_screens[index].run_id == runs[index].run_id
state_screens[index].order == runs[index].order
```

Also assert that every attention row references an emitted run. The test proves the fixture is a
projection of the service shape rather than a second imaginary API. The `boards-loading` capture
then shows the same ordered rows that the invariant checked.

### 2. RunState-reachable state roster

Files: `src/agentic_dynamics/control/control_db.py`,
`apps/control_room/services/operations.py`,
`apps/control_room/verification/fixtures/boards_endpoints.json`, and
`tests/test_control_room_operations.py`.

Use `RunState` as the exhaustive lifecycle source. Add fixture rows and assertions for reachable
`unknown`, `promotable`, `cancelled`, and `quarantined` cases. If `stalled` remains an operator
screen, its assertion must require a stale heartbeat or explicit phase evidence while preserving
the underlying `RunState.RUNNING`; if no such evidence is implemented, remove `stalled` from the
served roster. Apply the same refusal to `escalated` unless an attempt escalation record exists.
The proving assertion is that every rendered lifecycle value is in `RunState` or is an explicitly
named observation mapping with its evidence, never a manufactured enum.

### 3. Degraded `Unhealthy workers` rendering

Files: `apps/control_room/services/context.py`, `apps/control_room/services/operations.py`,
`apps/control_room/static/app.js`, `apps/control_room/verification/fixtures/boards_endpoints.json`,
`scripts/verify_control_room_rendering.py`, and
`tests/test_control_room_static_views.py`.

Carry a worker-health state that distinguishes observed healthy, observed degraded, and
unavailable/unobserved. In `renderOperations()`, assert and render the state rather than
`(data.unhealthy_workers || []).length`. Extend `operations_degraded` with a worker observation
failure and add the gate assertion:

```text
probe.metrics["Unhealthy workers"] == "unavailable"
```

The same degraded probe must assert the named source reason remains visible. Update the static
anchor test in the same commit if the packet read changes from `unhealthy_workers` to
`worker_health`; this directly prevents attempt-eleven's 78/79 failure.

### 4. Host-satisfiable browser assertions

Files: `apps/control_room/static/app.js`, `scripts/verify_control_room_rendering.py`, and the
host-produced acceptance report under `experiments/results/control_room_render/`.

Render every asserted server-owned value as text in the candidate's DOM. For `attention.state`,
the proving assertion is that the Operations row's visible text contains `active` for the fixture
attention row; the gate must not accept `data-attention-state="active"` alone. Keep the
`boards-loading` screenshot and add its visible-text probe to the gate. Run the acceptance profile
on the host against the candidate SHA, require all requested classes and nonzero captures, and
carry the report/capture pointers into the next decision record. The fleet container's lack of
Playwright is a reason to move this verification to the host, not a reason to weaken or fake the
assertion.
