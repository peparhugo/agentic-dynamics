# Adversarial Review: Control Room Operations

**Candidate reviewed:** `5d693a501`

**Independent reviewer:** `deepseek/deepseek-v4-pro` (different model from the authoring run)

**Scope:** the L23/L33 Operations read model, its browser renderer, committed board fixtures,
the render gate, committed render report, and captures. The review inspected
`apps/control_room/services/operations.py`, `apps/control_room/services/context.py`,
`apps/control_room/static/app.js`,
`apps/control_room/verification/fixtures/boards_endpoints.json`, and
`scripts/verify_control_room_rendering.py`.

## Checks Performed

- `python3 scripts/verify_control_room_rendering.py --check-fixtures`: PASS.
- `python3 -m pytest tests/test_control_room_operations.py tests/test_control_room_static_views.py -q`:
  PASS, 32 tests.
- `python3 scripts/verify_control_room_rendering.py --profile acceptance --candidate 5d693a501`:
  could not run because Playwright is not installed. It produced no current-candidate captures.
- Read the committed `gate_report.md` and degraded Operations capture. That report is bound to
  candidate `489b0bf15b467fae5e2892bbcadc9385cc6da4b9`, not the reviewed candidate.

## Findings

### P1: The Operations fixture is a hand-written twin, not a response the server can emit

`operational_snapshot()` derives `state_screens` directly from its triage-ordered `runs`
projection, so every served screen has a corresponding run at the same position
(`apps/control_room/services/operations.py:589-627`). The fixture instead preserves six
independent `run-state-*` screens (`boards_endpoints.json:73-80`) while its builder emits 18
`run-fixture-*` rows (`verify_control_room_rendering.py:2578-2607`).

**Falsifier:** `build_operations_payload()` reports `screen_count=6`, `run_count=18`, and
`state_screen_run_ids_are_runs=False`. The first screen is `run-state-running`; the first
roster row is `run-fixture-0001`. Such a payload is impossible from the service, so a browser
test can pass while real server-derived state screens regress.

The same twin contradicts individual row derivations. A promoted candidate must have
`operator_state="unknown"` and `decision.eligibility="promote"` under the current service
(`operations.py:88-111, 202-239`), while the fixture seeds it as `running` and `inspect`
(`boards_endpoints.json:10-37`). Its builder updates `row["state"]` but leaves the seeded
`row["lifecycle.state"]`, allowing `promotable` beside `running` (`verify:2579-2602`).

### P1: Required state-screen coverage asserts states that cannot be served

The gate requires `running`, `blocked`, `stalled`, `failed`, `escalated`, and `done`
(`verify_control_room_rendering.py:2722-2727`). `RunState` has no `stalled` value
(`src/agentic_dynamics/control/control_db.py:140-182`), and the step-attempt records used by
`_operator_state()` do not supply the `escalation_from` and `escalation_to` fields required for
its escalation branch (`operations.py:106-108`). Conversely, real `promotable`, `cancelled`,
and `quarantined` rows reach the service's `unknown` state (`operations.py:97-111`), which the
gate omits.

**Falsifier:** `_operator_state({"state": "promotable"}, None)` returns `unknown`; the
fixture's promotable seed requires `running`. Also, fixture state-screen `attention` and
`action` values such as `stalled`, `escalated`, `cancel`, and `interrupt` are outside the
service's emitted attention/action vocabularies (`operations.py:203-208, 231-239`).

### P2: An unavailable worker read renders as a fabricated zero

When the control database cannot be opened, the context response includes
`"unhealthy_workers": []` plus named degradation (`context.py:159-174`). The Operations
renderer gates the database-derived run counts but always renders worker length as a number
(`app.js:3272-3283`). The committed degraded capture visibly renders `UNHEALTHY WORKERS 0`
beside `unavailable` cards. The degraded render class only asserts the three guarded metrics
(`verify_control_room_rendering.py:3256-3266`), so it cannot catch this breach.

**Falsifier:** the deterministic degraded payload has `unhealthy_workers: []` and a
`control_db` degradation; `renderOperations()` selects `String((data.unhealthy_workers ||
[]).length)`, therefore it renders `0` instead of `unavailable`.

### P1: No current-candidate acceptance evidence exists

The acceptance profile must produce captures, but it cannot execute in this environment because
Playwright is absent. The only committed acceptance report names older candidate
`489b0bf15b467fae5e2892bbcadc9385cc6da4b9` (`apps/control_room/verification/gate_report.md:13-16`),
not reviewed candidate `5d693a501`. It therefore cannot establish the served rendering of this
candidate.

**Falsifier:** rerunning the required command prints `playwright is not installed` and creates
zero candidate-bound captures. Under the render-gate contract, that is a structural failure, not
a pass carried forward from an older SHA.

## Claim Assessment

- **Server-derived attention, order, and age:** holds for the Operations roster. The client
  preserves `data.runs` order (`app.js:3330-3346`), only applies server-provided attention
  fields (`app.js:3113-3139`), and renders server-provided age (`app.js:3141-3159, 3475-3480`).
  Falsifier: replace the response order, attention state, or age label in an endpoint fixture;
  a compliant client must render that exact value without sorting, matching, or reading its clock.
- **Fixtures assert real server shape:** fails. The divergent `state_screens` and promotable row
  values above prove the fixture is a twin rather than the read model's contract.
- **Omitted values never become zero:** fails for `unhealthy_workers` on a degraded control DB.
  The server-side cost and age helpers are otherwise correctly named rather than zero-defaulted.
- **Required state screens render:** fails. The required roster contains unreachable states and
  omits a reachable `unknown` state; it is not a valid test of the actual state model.

## Required Remediation

1. Generate the Operations fixture from the service's read-model contract or make the fixture
   assert the `state_screens[i]` to `runs[i]` identity/order invariant instead of carrying a
   hand-authored second array.
2. Reconcile `_operator_state()` and the required state roster with `RunState`: either implement
   evidence for stalled/escalated or remove those manufactured states, then test reachable
   unknown/promotable/cancelled/quarantined cases.
3. Render `Unhealthy workers` as `unavailable` whenever its source is degraded or unobserved,
   and add it to the degraded render assertions.
4. Install Playwright and run the acceptance profile against this exact candidate so the report
   and captures are candidate-bound.

## FINDING

The Operations client no longer re-derives its roster's attention, ordering, or age, but the
acceptance artifact cannot substantiate the rest of the server-owned claim. Its fixture is a
hand-written response twin with impossible state-screen identities and state values; the gate
then validates that twin instead of the real service shape. In addition, an absent/unavailable
worker observation visibly renders as fabricated `0`, and the reviewed candidate has no
candidate-bound acceptance captures because the required browser is unavailable. This proposal
must not pass the render/promotion gate until the fixture contract, worker degradation render,
reachable state coverage, and current-candidate capture evidence are repaired.
