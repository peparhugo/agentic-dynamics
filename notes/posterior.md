## Violations

1. **The landed served client is not executable.** `apps/control_room/static/app.js:3271`
   declares `const runs` for the server projection, but `:3335` still declares
   `const runs = active.concat(promotable)`. `node --check apps/control_room/static/app.js`
   fails with `SyntaxError: Identifier 'runs' has already been declared`. This blocks the
   served render path, so the acceptance screenshots cannot prove the current candidate.

2. **The acceptance report is not bound to the landed candidate.**
   `apps/control_room/verification/gate_report.json:17` and
   `apps/control_room/verification/gate_report.md:13` identify candidate
   `489b0bf15b467fae5e2892bbcadc9385cc6da4b9`, while the landed commit is
   `214c22e53cbd18feb5846bc8f3cc25111811e27a`. The reported capture set predates the
   landing and the reported candidate is not present in the local object database. The report's
   `candidate_verified: true` therefore cannot be used as evidence for this checkout.

3. **The fixture passes a structural check without exercising the declared state contract.**
   `python3 scripts/verify_control_room_rendering.py --check-fixtures` passes, but
   `scripts/verify_control_room_rendering.py:2589-2641` synthesizes only `running` and
   `promotable` rows and hard-codes `started.age` to `4d`. It does not provide an injected
   observation instant, safe actions, failed/stalled/escalated/done seeds, or worker identity
   and reason data. `boards_endpoints.json:49-55` names six screens, but the generated payload
   can only record `running` and `blocked`; the other screens are unbound placeholders.

4. **The six screens are not implemented to the accepted content contract.**
   `operations.py:423-445` can classify blocked, failed, done, and escalated rows, but it does
   not classify a stalled row from heartbeat or phase evidence. `operations.py:544-572` then
   correctly names an absent stalled screen, but that is not the planned stalled screen with
   heartbeat age, affected phase, and permitted actions. The client renderer at
   `app.js:3201-3234` renders only Run/Lifecycle/Age for a populated screen. It does not render
   the required blocked decision target/actions, stalled evidence/actions, failed terminal
   reason, escalation boundary/reason, or done receipt/projection distinction.

5. **Server-carried values remain omitted from the served tables.**
   `operations.py:638-642` returns `safe_actions` and `unhealthy_workers`, but
   `app.js:3279-3285` reduces workers to a count and never renders `safe_actions`.
   `run_row()` does not attach worker identity, age, or reason to the owning row. The fixture's
   worker record at `boards_endpoints.json:43-47` is consequently not visible evidence of the
   stale worker identity or age. The plan explicitly required these values either to be visible
   or to have a named unavailable/unknown state.

6. **The presentation vocabulary was not completed.** `board-fleet.js` still contains only the
   Fleet lifecycle vocabulary (`queued`, `running`, `done`, `failed`, `timeout`, `retry`, and
   `unknown`). `app.js:3094-3110` therefore renders server states such as `promotable` through
   the old lifecycle lookup and falls back to an unknown glyph plus raw text. That preserves the
   raw value, but it is not the planned explicit presentation mapping for the operator state
   screens and does not prove the required distinctions for `merged`, `projecting`, and
   `published`.

7. **The current gate has no dedicated proof for the new values.** The report lists 23 captures,
   but none is a state-specific running/blocked/stalled/failed/escalated/done capture, a
   safe-action capture, a worker-detail capture, or a current glance-row capture. The gate's
   browser assertions at `scripts/verify_control_room_rendering.py:3671-3717` check that six
   screen labels and row fields exist, not that each state contains its required evidence.

## Unknowns

- The current browser-rendered behavior is unknown. Playwright is not installed, so the
  candidate-bound acceptance command could not produce a new render report; the existing report
  is stale and the current JavaScript fails syntax validation before boot.
- The current `/api/operations` payload has not been exercised against a live read-only control
  database after this landing. In particular, the actual `safe_actions`, failed-run details,
  heartbeat evidence, escalation attempts, and terminal projection states are unverified.
- The current `/api/glance` route does call the shared `ops.run_row()` projection at
  `routes/glance.py:467-488`, with a server observation timestamp, but no current served-room
  capture proves that its enriched `run_sample` is rendered. The parked `F-0` fixture contains
  richer glance fields, but it is not the restored Operations endpoint's proof.
- The existing PNG files are non-empty, but their relation to this landing is unknown because
  the report binds them to the other candidate. Non-zero bytes satisfy only the capture-file
  requirement, not candidate identity or semantic coverage.
- Focused pytest verification could not run in this environment: the `pytest` launcher exits
  with `ModuleNotFoundError: No module named 'pytest'`. Python fixture validation is therefore
  the only completed automated gate in this checkout.
- The L23 run clone and adversarial review referenced by `notes/control_room.md` are not present
  under `/repo` or `/tmp`; the accepted plan and current tree are the available provenance.

## UPDATES

### Values moved server-side

- **Attention membership, kind, state, and order.** `operations.py:448-477` now builds the
  attention projection and writes `attention.state`, `attention.kind`, and `attention.order`.
  The fixture source is `boards_endpoints.json:19-35`, and the browser-facing Operations capture
  is `apps/control_room/verification/boards_operations_desktop_dark_1440x900.png` (with the
  corresponding light and narrow captures below). The fixture and capture show the table, but
  the stale candidate binding and the missing semantic order assertion mean they are not
  acceptance proof for this landing.
- **Run-row facets.** `operations.py:480-541` now emits `session.identity`, `spec.cell`,
  `model.provider`, `phase.progress`, `lifecycle.state`, `run.live`, `terminal.target`,
  `attempt.number`, cost/evidence fields, eligibility/receipt, and `started.age`. The fixture
  expansion is `scripts/verify_control_room_rendering.py:2589-2637`; the intended visual proof
  is the Operations desktop capture and the scrolling capture
  `apps/control_room/verification/boards_operations_narrow_dark_1024x768.png`. The current
  browser cannot render these fields because of the duplicate declaration.
- **Injected age calculation.** `operations.py:338-359` owns `_age_label()` and receives
  `now` through `context.py:148-151`; `routes/glance.py:467-480` reuses the same projection with
  `observed_at`. The current fixture does not prove this derivation because it hard-codes `4d`
  and has no observation-time field. Existing Operations captures show an age-like value only;
  they do not prove an injected clock.
- **Named operator-state screens.** `operations.py:47-54` declares the six names and
  `:544-572` emits `recorded`, `unbound`, or `unavailable` states. The fixture names them at
  `boards_endpoints.json:49-55`, and the keyboard capture
  `apps/control_room/verification/boards_keyboard_drawer_dark_1440x900.png` is the closest
  existing interaction evidence. It does not prove the required state-specific data, because
  the fixture only supplies running/blocked rows.
- **Shared glance-row derivation.** `routes/glance.py:473-488` now uses `ops.run_row()` for
  active, promotable, and failed rows. This removes a second derivation path server-side. No
  current restored-room capture proves the `/api/glance` row; the listed keyboard captures prove
  drawer content, not the glance route.
- **Existing run-detail evidence blocks remain service-owned.** The current drawer captures
  `boards_keyboard_drawer_dark_1440x900.png`,
  `boards_keyboard_drawer_light_1440x900.png`,
  `boards_keyboard_drawer_logs_dark_1440x900.png`, and
  `boards_keyboard_drawer_logs_light_1440x900.png` are evidence for the already-landed cost,
  evidence, knowledge, prepared-step, timing, and log blocks. They do not prove the new
  Operations roster/state values.

### Values that remain client-side

- **Formatting and DOM projection remain client-side by design.** `runFieldValue()` and
  `runStateChip()` at `app.js:3113-3124` create labels, chips, glyphs, and unknown markers;
  `runRoster()` at `:3134-3157` creates the table; `renderStateScreens()` at `:3201-3234`
  creates the cards. These are presentation operations and should consume the server values
  without sorting, aging, joining, or defaulting them.
- **Shell behavior remains client-side by design.** Board navigation, theme/density preferences,
  focus management, modal/drawer open/close behavior, and responsive layout remain in
  `shell.js`, `detail-sheet.js`, and the surrounding `app.js` DOM code. They are interaction
  state, not control-plane evidence.
- **Non-Operations live UI timing remains client-side.** `app.js:158-183` and `:261-274` use
  the browser clock for flags, retained telemetry, burn-window expiry, and live overlays. This
  is acceptable only for those UI freshness calculations; it must not be reused for the
  authoritative Operations `started.age`, which is now service-owned.
- **The client intentionally preserves raw packet blocks for parity.**
  `app.js:3265-3273` retains `active_runs` and `promotable_runs` while selecting `data.runs`
  as the intended roster source. The old concatenation at `:3335` is not an intentional
  client-side value owner; it is an unfinished leftover and must not survive the repair.

### Gate evidence

- Completed: `python3 scripts/verify_control_room_rendering.py --check-fixtures` returned
  `fixture check PASS (F-0..F-7 legacy + boards)`. This is fixture structure only, not render
  acceptance.
- Failed source gate: `node --check apps/control_room/static/app.js` reports the duplicate
  `runs` declaration at line 3335.
- Not run to completion: the acceptance command
  `python3 scripts/verify_control_room_rendering.py --profile acceptance --candidate
  214c22e53cbd18feb5846bc8f3cc25111811e27a` cannot render because Playwright is not installed.
- Existing non-empty capture paths, retained as historical evidence only:
  `apps/control_room/verification/boards_operations_desktop_dark_1440x900.png`,
  `apps/control_room/verification/boards_operations_desktop_light_1440x900.png`,
  `apps/control_room/verification/boards_operations_narrow_dark_1024x768.png`,
  `apps/control_room/verification/boards_degraded_operations_desktop_dark_1440x900.png`,
  `apps/control_room/verification/boards_keyboard_drawer_dark_1440x900.png`,
  `apps/control_room/verification/boards_keyboard_drawer_light_1440x900.png`,
  `apps/control_room/verification/boards_keyboard_drawer_logs_dark_1440x900.png`, and
  `apps/control_room/verification/boards_keyboard_drawer_logs_light_1440x900.png`.
- The incumbent report claims PASS at `gate_report.md:3-18` and enumerates all 23 paths at
  `:20-44`, but its candidate mismatch, absent current browser run, and lack of state-specific
  assertions downgrade those captures to historical/non-attributable evidence for this phase.
