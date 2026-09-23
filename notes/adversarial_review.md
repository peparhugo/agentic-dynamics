# Adversarial Review: Control Room Detail Truth

## Scope And Evidence

Reviewed the final candidate commits (`03763d5b3`, `a381de358`, and `e19e997e4`), the phase notes,
the Operations read model, the served renderer, the committed board fixture, the render gate, and
the declared test suites. The fixture-only gate passed. The declared suites passed:

```text
19 passed  tests/test_control_room_operations.py
17 passed  tests/test_control_room_glance_integrity.py
23 passed  tests/test_control_room_build_contract.py
12 passed  tests/test_control_room_static_views.py
5 passed   tests/test_control_room_paths.py
```

The required host browser profile was attempted against `HEAD` but could not start because this
environment has no Playwright. It emitted no captures. That is unknown acceptance evidence, not
a passing acceptance result.

## Findings

### P1: Operations summary values still re-derive in the client

`renderOperations()` calculates `Active runs`, `Decisions owed`, and `Promotable runs` from the
lengths of `active_runs`, `attention`, and `promotable_runs`
(`apps/control_room/static/app.js:3295-3329`). The service carries lists but no server-owned
summary/count block (`apps/control_room/services/operations.py:592-615`). This is a second
derivation of operator-facing values, contrary to the stated server-owned contract.

The phase-progress renderer also turns an omitted half of a progress pair into zero
(`app.js:3158-3164`): `{phases_total: 2}` renders `0/2`, and `{phases_completed: 1}` renders
`1/0`. An omitted measurement is therefore rendered as a fabricated zero.

Falsifier: have the service cap `active_runs` for delivery while emitting an authoritative total,
or emit only `phases_total`. The current browser will show the delivered-list length and `0/2`,
not the server-owned count and a named incomplete/unknown value. No declared test or browser
assertion forces that input.

### P1: The Operations fixture is not a faithful Operations response

The normal fixture omits the service response's top-level `schema` and
`source.packet_schema` (`apps/control_room/verification/fixtures/boards_endpoints.json:3-7`),
although `operational_snapshot()` always emits both (`operations.py:592-599`).
`check_boards_fixtures()` does not require either field
(`scripts/verify_control_room_rendering.py:2613-2688`). A test fixture that can omit mandatory
wire fields cannot prove the renderer consumes the real server shape.

More seriously, the builder manufactures `active_runs` from the derived roster while explicitly
removing `promotable` (`verify_control_room_rendering.py:2603-2608`). The packet's real active
block includes every non-terminal `RunState`, including `promotable`
(`src/agentic_dynamics/control/control_status.py:149,816-823`). The fixture therefore cannot
represent the list semantics produced by the service it purports to exercise.

Falsifier: create a real `PROMOTABLE` run, compare `/api/operations.active_runs` with the fixture
payload, and observe that the service includes it while the fixture excludes it. The current
identity/order check for `runs` and `state_screens` passes despite this disagreement because it
never compares the packet pass-through blocks with the service contract.

### P1: Reachable lifecycle coverage is incomplete

`RunState` exposes twelve reachable lifecycle values
(`src/agentic_dynamics/control/control_db.py:171-182`). The fixture covers nine and omits
`verifying`, `promoting`, and `projecting`
(`boards_endpoints.json:19-38`); the fixture gate only requires `cancelled`, `quarantined`, and
`promotable` (`verify_control_room_rendering.py:2716-2722`). The service roster is complete in
principle because it reads `db.runs()` (`operations.py:239-259`), but the claimed fixture/gate
proof is not exhaustive.

Falsifier: change the mapping for `verifying`, `promoting`, or `projecting` to an invalid or
missing screen. The fixture check and the declared Operations roster test remain green because
neither instantiates or asserts those states.

### P1: Worker unavailability is still fail-open for an omitted block

The service properly produces `worker_health.state == "unavailable"` when the packet carries a
degraded `unhealthy_workers` source (`operations.py:262-279`). However, the renderer falls back
to `String(unhealthyWorkers.length)` whenever `worker_health` is absent or lacks `value`
(`app.js:3324-3329`). With both values omitted, its defaults are `{}` and `[]`, so the rendered
claim is `Unhealthy workers: 0` rather than `unavailable`.

The degraded fixture always supplies `worker_health`, and the gate checks only that supplied
shape (`boards_endpoints.json:91-97`, `verify_control_room_rendering.py:2723-2727`). It does not
exercise the renderer's fail-open fallback.

Falsifier: serve `{degraded: [{surface: "unhealthy_workers", reason: "collector failed"}],
unhealthy_workers: []}` without `worker_health`. The board displays `0`; the named source is
degraded, so that zero is fabricated.

### P1: Several drawer browser assertions are metadata-only and can pass vacuously

The drawer probe reads measured-zero cost and prepared-step path from `data-*` attributes, and
only checks that an unknown timing row has `data-state="unknown"`
(`scripts/verify_control_room_rendering.py:2508-2546,3713-3766`). The static suite explicitly
anchors those same attributes (`tests/test_control_room_static_views.py:198-223`). These are not
visible-text assertions, unlike the newly repaired attention/state-screen checks.

Falsifier: retain `data-cost-provenance`, `data-prepared-step-path`, and
`tr[data-state="unknown"]`, but render blank text nodes. The current probe and static suite pass
while an operator cannot see the cost provenance, prepared reference, or unknown timing state.

### P2: Some malformed worker inputs can bypass the named-degradation boundary

`read_worker_heartbeats()` parses `FINOPS_REDIS_PORT` and `FINOPS_REDIS_DB` before its `try`
block (`control_status.py:703-716`). A non-integer environment value raises before the collector
can return a named error, and `operations_snapshot()` invokes that collector before its
control-database exception boundary (`apps/control_room/services/context.py:137-151`). This can
make the Operations endpoint return a 500 rather than its promised named unavailable response.

`_float_or_none()` also accepts non-finite `inf`, which causes a future heartbeat to be treated
as healthy (`control_status.py:598-605,633-644`).

Falsifier: set `FINOPS_REDIS_PORT=not-a-port`, or inject `last_seen: "inf"`. The first request
raises instead of returning a degraded worker state; the second removes an untrustworthy worker
from the unhealthy list.

## What Passed

- The client no longer sorts the server-owned `runs` roster, and `state_screens` are generated
  from the same service projection in the fixture builder. The fixture check verifies matching
  run IDs and order (`verify_control_room_rendering.py:2699-2711`).
- A normal unobserved-worker collection failure is represented as a named unavailable
  `worker_health` block and is visibly rendered when that block is present.
- The `attention.state` repair is visible text (`active`) rather than only a data attribute
  (`app.js:3135-3140`).

## FINDING

This candidate is **not ready for promotion**. It fixed the prior visible `attention.state`
failure and preserves ordered `state_screens`, but it still fabricates zero-like values for
partial phase progress and an omitted worker-health block, re-derives summary counts in the
client, and validates a fixture whose packet list semantics and required wire fields diverge from
the actual service. The five declared pytest suites are green, but they do not falsify these P1
defects, and no host acceptance capture exists for this candidate.
