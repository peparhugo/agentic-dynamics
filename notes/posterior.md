# Control Room Detail Truth Posterior

## Violations

1. **The implementation is only a partial match for `notes/plan.md`.**
   `services/operations.py` now emits the row facets used by the Operations roster and sorts
   `run_rows` by the server-owned `attention.rank`. This is the intended direction, but the
   plan also required the Operations board to render `safe_actions`, unhealthy-worker identity
   and age, and projection health/age/error detail. `renderOperations()` still renders only
   `unhealthy_workers.length` (`apps/control_room/static/app.js:3300-3306`), renders only the
   projection lag counts (`apps/control_room/static/app.js:3414-3421`), and never reads
   `data.safe_actions`. Those values remain omitted or reduced in the served table.

2. **Unknown lifecycle state is still given a fabricated screen.**
   `_screen_for_run()` returns `running` for every unrecognised state
   (`apps/control_room/services/operations.py:105-109`). The plan required an unknown state to
   remain a named unknown with its reason. The current fallback can therefore present an
   unclassified run as being in the execution path and mark it `live` through `_run_view()`.

3. **The state-screen implementation is structural, not the complete state truth table.**
   The service emits six names and the client paints generic cards, but the landed renderer does
   not render state-specific primary elements beyond a count/reason and optional run links
   (`apps/control_room/static/app.js:3377-3411`). The gate checks the six names and their text,
   not the full R0/R1/R2/R3 state-specific content described by the plan. The fixture's
   `state_screens` block is also hand-authored and the gate's `build_operations_payload()` joins
   it into rows; it does not exercise the real `ControlDB` service projection.

4. **The required new capture set was not landed.**
   The plan called for candidate-bound captures for truth rows, healthy empty Operations,
   unbound logs, unavailable logs, worker/projection health, and partial Surfaces. None of those
   capture cases exists in the current gate profile. The existing report is bound to candidate
   `489b0bf15b467fae5e2892bbcadc9385cc6da4b9`, while the current candidate is
   `3cdced24ffc0ad0157e38e39e4709931283530d7`. Therefore the old report cannot prove the
   current commit.

5. **The acceptance profile was not executable in this environment.**
   `python3 scripts/verify_control_room_rendering.py --profile acceptance --candidate 3cdced24f`
   stopped with `playwright is not installed` (exit 2). No new candidate-bound screenshots were
   produced. The browser gate's fixture precheck did pass, but that is not a substitute for the
   required rendered captures.

## Unknowns

- The real served `/api/operations` response was not browser-exercised at the current `HEAD`.
  The fixture gate proves the synthetic wire payload, not that the Flask route and the real
  control database produce the same enriched row shape.
- There is no current acceptance capture proving that the Operations board displays a safe
  action bound to its exact `run_id`, `gate_id`, `candidate_sha`, and action.
- There is no current capture for `run_detail_unknown` or an injected unavailable log store.
  The service tests cover named `unbound` and `unavailable` states, but the plan required their
  visible drawer evidence as well.
- There is no independent browser proof for real `stalled` or `escalated` rows. The committed
  fixture names those screens, while `_screen_for_run()` only gets `stalled` from the attention
  join and `escalated` from recorded attempt escalation fields.
- The current gate report's claim of `No violations` is historical for candidate `489b...`; it
  must not be cited as evidence for `3cdced24f`.

## UPDATES

### Values moved server-side

| Value | Landed owner and rule | Fixture/gate evidence | Capture evidence |
|---|---|---|---|
| Attention state, kind, and rank | `services/operations.py:_run_view()` emits `attention.state`, `attention.kind`, and `attention.rank`; `operational_snapshot()` orders `run_rows` by rank, then `run_id`. The Operations renderer no longer builds `attentionByRun` or sorts runs. | `apps/control_room/verification/fixtures/boards_endpoints.json:42-58,72-89`; `scripts/verify_control_room_rendering.py:2575-2600`. | Historical Operations captures: `apps/control_room/verification/boards_operations_desktop_dark_1440x900.png`, `boards_operations_desktop_light_1440x900.png`, and `boards_operations_narrow_dark_1024x768.png`. These are not current-candidate proof. |
| Started age | `services/operations.py:_age_seconds()` and `_age_label()` measure and label age at the read boundary. `run_detail()` exposes the same value in `display`; `app.js` renders the label without `Date.now()` for Operations rows or the drawer. | `boards_endpoints.json:143-146` and `scripts/verify_control_room_rendering.py:2638-2642,3734-3741` require `4d ago` / `345600`. | Historical drawer captures: `apps/control_room/verification/boards_keyboard_drawer_dark_1440x900.png`, `boards_keyboard_drawer_light_1440x900.png`, and their `*_logs_*` variants. |
| Run-row evidence facets | `_run_view()` composes target, attempt, live state, cost provenance, evidence, eligibility, receipt, and source fields from packet/detail/run-evidence data. The browser reads those emitted keys and uses labelled unknowns when absent. | `boards_endpoints.json:17-38` plus the expanded rows built by `build_operations_payload()`; fixture validation requires the named row fields. | The historical Operations captures above show the roster, but the old report does not bind them to `3cdced24f`. |
| State-screen names and named degraded state | `_state_screens()` emits `running`, `blocked`, `stalled`, `failed`, `escalated`, and `done`; the context fallback emits all six as `unavailable` when the control DB cannot be read. | `boards_endpoints.json:91-123`; fixture checks and the loading/degraded checks in `verify_control_room_rendering.py`. | `apps/control_room/verification/boards_operations_desktop_dark_1440x900.png` and `boards_degraded_operations_desktop_dark_1440x900.png` are historical only. |

### What remains client-side

- DOM construction, labels, text formatting, table layout, state-screen card layout, keyboard
  focus, drawer opening/closing, and row selection remain client-side. These are presentation and
  interaction responsibilities and do not assert new facts.
- `formatAge()` remains in `app.js` for the supervisor flag board's `at` and
  `last_activity_at` timestamps (`app.js:1024-1025,1143`). That is a separate flags payload and
  is not the Operations run age moved by this plan.
- `renderOperations()` still derives summary counts from array lengths and sorts projection keys
  for display. The key sort is presentation-only, but the worker/attention/promotable counts are
  still client-side derivations and should be replaced by named server summary fields if the
  Operations contract is intended to be wholly server-owned.
- Safe-action rendering, worker detail rendering, projection health detail rendering, and the
  state-specific truth-table elements remain unimplemented in the served renderer. These are
  violations, not acceptable client responsibilities.

### Verification evidence

- `python3 scripts/verify_control_room_rendering.py --check-fixtures`: **PASS** (`F-0..F-7`
  plus boards fixtures).
- `python3 -m pytest tests/test_control_room_operations.py tests/test_control_room_static_views.py tests/test_control_room_glance_integrity.py tests/test_control_room_paths.py -q -p no:cacheprovider`: **50 passed**.
- Acceptance attempt: **BLOCKED** by missing Playwright; output directory
  `/tmp/opencode/l33-acceptance` contains no rendered proof.
- Historical report: `apps/control_room/verification/gate_report.json` and
  `apps/control_room/verification/gate_report.md` record 23 captures for candidate `489b...`.
  Their relevant paths are the Operations navigation captures, the loading capture
  `boards_loading_operations_reload_desktop_dark_1440x900.png`, the degraded capture
  `boards_degraded_operations_desktop_dark_1440x900.png`, and the keyboard drawer/log captures.
  They establish prior served-board behavior only; they do not close the current candidate's
  acceptance gate.
