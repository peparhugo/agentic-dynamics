## Violations

The execute plan was only partially realized by commit `6f84992ebd9e1662411964283a9b0b322b0eddc8`.

1. **The acceptance captures do not prove the landed implementation.** The committed report and PNGs
   are bound to candidate `489b0bf15b467fae5e2892bbcadc9385cc6da4b9`, not the landed commit
   `6f84992ebd9e1662411964283a9b0b322b0eddc8`. The inspected captures
   `apps/control_room/verification/boards_operations_desktop_dark_1440x900.png`,
   `apps/control_room/verification/boards_operations_narrow_dark_1024x768.png`, and
   `apps/control_room/verification/boards_degraded_operations_desktop_dark_1440x900.png`
   show the old `ACTIVE + PROMOTABLE RUNS` heading and no `Safe actions` or `State screens`
   section. They therefore cannot prove the new server-owned values.

2. **The fixture builder is a hand-written twin of the service shape.** The fixture source carries
   the intended fields in
   `apps/control_room/verification/fixtures/boards_endpoints.json:3-92`, but
   `scripts/verify_control_room_rendering.py:2579-2610` synthesizes `session.identity`, attention,
   rank, and `state_screen` independently. `--check-fixtures` proves that this synthetic payload is
   internally consistent; it does not prove that `services/operations.py` emits the same payload.

3. **The six state screens are label coverage, not the planned state truth table.** The service emits
   `state_screens` at `apps/control_room/services/operations.py:627`, and the fixture names all six
   states at `apps/control_room/verification/fixtures/boards_endpoints.json:73-79`. However, the
   gate only checks the six state strings at
   `scripts/verify_control_room_rendering.py:2722-2727`, while the client renders one generic table
   at `apps/control_room/static/app.js:3371-3391`. The planned per-state primary evidence from
   `docs/research/control_room_state_screens.md:87-96` is not asserted or captured.

4. **The Operations renderer still has a client-side reconstruction fallback.** At
   `apps/control_room/static/app.js:3332-3334`, missing `data.runs` is replaced with
   `active.concat(promotable, failed)`. The normal path preserves server order, but the fallback
   recreates the packet roster in the browser and can silently diverge from the server-owned order.

5. **The landed row shape is not fully coherent for the promoted state.** `run_row()` emits
   `operator_state: "unknown"` for `promotable` because `_operator_state()` only maps
   `awaiting_approval`, explicit `stalled`, `failed`, merged/projecting/published, and active
   lifecycle states (`apps/control_room/services/operations.py:88-111`). The fixture builder instead
   hard-codes `operator_state: "running"` for every generated row at
   `scripts/verify_control_room_rendering.py:2591-2599`. The fixture therefore masks a real service/
   fixture mismatch.

## Unknowns

- The required independent room suite was not executed: `pytest` is unavailable in this environment
  (`ModuleNotFoundError: No module named 'pytest'`). The declared target remains
  `tests/test_control_room_operations.py`, `tests/test_control_room_glance_integrity.py`,
  `tests/test_control_room_build_contract.py`, `tests/test_control_room_static_views.py`, and
  `tests/test_control_room_paths.py`.
- The required browser acceptance run was not executed: Playwright is not installed. The command
  `python3 scripts/verify_control_room_rendering.py --profile acceptance --candidate
  6f84992ebd9e1662411964283a9b0b322b0eddc8` refused before browser execution and produced no new
  captures. Existing capture paths are listed in `apps/control_room/verification/gate_report.md:20-44`,
  but they are stale evidence for this landing.
- No capture proves the server-owned `attention.state`/`attention.kind`, `triage_rank`, deterministic
  age, safe-action identifiers, or six state-screen cases for candidate `6f84992e...`. The only
  deterministic evidence available is the browser-free fixture result:
  `python3 scripts/verify_control_room_rendering.py --check-fixtures` ->
  `fixture check PASS (F-0..F-7 legacy + boards)`.
- The current acceptance report at
  `apps/control_room/verification/gate_report.{json,md}` is stale for this tree: it claims candidate
  `489b0bf...`, despite the current HEAD being `6f84992e...`. Its 23 capture paths are retained
  artifacts, not new gate evidence.
- The plan requested service-produced fixture parity and primary state-element assertions, but no
  executable evidence currently establishes either. Whether the intended resolution is to make the
  gate call the real read model or to add a separate service-contract fixture remains an implementation
  decision for the next phase.

## UPDATES

### Values moved server-side

| Value | Landed owner and fixture | Capture evidence |
|---|---|---|
| Attention membership and kind | `apps/control_room/services/operations.py:547-556,593-605`; fixture fields in `apps/control_room/verification/fixtures/boards_endpoints.json:41-57` and generated row fields in `scripts/verify_control_room_rendering.py:2584-2599` | Intended capture: `apps/control_room/verification/boards_operations_desktop_dark_1440x900.png`; not valid for this landing because it is candidate `489b0bf...` and visibly shows the old renderer |
| Triage rank and run order | `apps/control_room/services/operations.py:573-591`; fixture `operations.runs` is checked by `scripts/verify_control_room_rendering.py:2700-2718` | Intended captures: `boards_operations_desktop_dark_1440x900.png`, `boards_operations_narrow_dark_1024x768.png`; no candidate-bound proof exists |
| Started age and named unknown age | `apps/control_room/services/operations.py:46-85,201-202,242`; detail age at `:674-678`; fixture detail cases in `boards_endpoints.json:113-132,325-343` | Intended captures: Operations desktop/narrow and keyboard drawer captures; existing files are stale and cannot prove the injected observation basis |
| Run evidence facets | `apps/control_room/services/operations.py:200-242`, reusing `services/run_evidence.py`; fixture run seed fields at `boards_endpoints.json:17-37` | No valid current roster capture; the old drawer capture only proves the pre-existing detail path |
| Safe actions | Packet pass-through at `apps/control_room/services/operations.py:628-631`; fixture at `boards_endpoints.json:59-71`; renderer at `app.js:3352-3369` | Intended Operations capture: `boards_operations_desktop_dark_1440x900.png`; the existing image has no Safe actions section |
| Named state screens | `apps/control_room/services/operations.py:627`; fixture at `boards_endpoints.json:73-79`; renderer at `app.js:3371-3391` | Intended Operations capture: desktop and narrow Operations images; the existing images predate the section and show no state screens |

### Values that remain client-side, intentionally or incorrectly

- DOM construction, responsive layout, table formatting, lifecycle glyph selection, and attention
  vocabulary selection remain client-side. These are presentation of server values, not new
  selection, causation, ordering, or age calculations.
- Summary card counts remain client-side formatting of packet arrays. The population itself remains
  server-authoritative; the browser only displays `length`.
- The `data.runs` fallback at `app.js:3332-3334` remains an incorrect client-side reconstruction
  and must be removed or changed to a named unavailable state before the acceptance claim is made.
- The generic state-screen table remains a client-side layout of an under-specified server block. It
  does not yet render the state-specific evidence required by the plan and state-screen document.
- Existing visual mapping of unsupported lifecycle values to an `unknown` chip at
  `app.js:3085-3110` is a named client presentation state, but it exposes the unresolved
  `promotable`/`awaiting_approval` vocabulary mapping rather than proving a complete operator state.

### Gate evidence

- Browser-free fixture gate: PASS, with no capture output.
- Browser acceptance profile: NOT RUN, because Playwright is unavailable; zero new captures were
  produced.
- Independent pytest gate: NOT RUN, because pytest is unavailable.
- Existing stale capture/report paths retained for audit: `apps/control_room/verification/` entries
  listed in `gate_report.md:20-44`, especially the Operations desktop, narrow, degraded, and keyboard
  drawer images. They must be regenerated and rebound to `6f84992e...` before promotion.
