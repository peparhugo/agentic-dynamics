## Files

- `apps/control_room/services/operations.py`: extend the operations read model, not the route, with a deterministic ordered roster, an injected observation-time/age block, explicit operator-state mapping, worker detail, failed-run detail, and safe-action bindings. Preserve raw packet identifiers and named `recorded`/`unbound`/`unavailable`/`unknown` states. Add docstrings and inline comments for each derivation because this is the single source of truth for the room.
- `apps/control_room/services/context.py`: pass the same observation inputs into the operations service and preserve named collector failures. Do not add a second read of the control database or a route-local fallback.
- `apps/control_room/routes/operations.py`: keep the two existing read-only endpoints thin. Change only if the service payload needs a versioned response contract or an explicit error envelope field.
- `apps/control_room/services/run_evidence.py`: expose any already-recorded ledger fields needed by the drawer, especially `recorded`, knowledge metadata, timing scope, and log provenance. Do not label selected knowledge as used or infer causation.
- `apps/control_room/static/app.js`: delete client-side operational decisions: browser-clock age, first-attention collapse, roster concatenation/ranking, and zero-default phase progress. Render the server-owned ordered rows, state mapping, ages, worker detail, action bindings, and named absent states. Keep formatting-only behavior such as truncation and table layout.
- `apps/control_room/static/board-fleet.js`: add only presentation tokens for the server's explicit state mapping. Keep lifecycle and attention axes separate; unknown raw states must remain visibly unknown with the raw state and reason.
- `apps/control_room/static/shell.js`: leave shell ownership intact, but audit badge suppression and drawer/board state labels so an unavailable consequential value is not hidden as an empty badge.
- `apps/control_room/verification/fixtures/boards_endpoints.json`: add deterministic packet-derived fields and state cases for running, blocked, stalled, failed, escalated, and done; duplicate attention; worker identity/age/reason; `safe_actions`; explicit source/observation time; rich/unknown/unbound drawer metadata; and the missing/error variants.
- `apps/control_room/verification/fixtures/F-0.json`: update only if the parked glance fixture is used as a compatibility comparison. It is not the restored-board source of truth.
- `scripts/verify_control_room_rendering.py`: extend the restored-board fixture checker and browser probes. Add state-screen assertions, server-order/age assertions, safe-action binding checks, explicit unknown checks, and screenshot records for each new case. Keep the required `acceptance` profile candidate-bound and fail on zero captures.
- `apps/control_room/verification/gate_report.md` and `apps/control_room/verification/gate_report.json`: regenerate from the acceptance run; never hand-edit the report to claim coverage.
- `tests/test_control_room_operations.py`: test deterministic order, injected age, state mapping, duplicate attention preservation, safe-action identity binding, worker detail, failed/stalled data, and named absent/unavailable behavior.
- `tests/test_control_room_static_views.py` and the relevant browser gate tests: assert the client renders service values and does not derive age/order or silently drop required blocks.
- `tests/test_control_room_build_contract.py` and `tests/test_control_room_parity.py`: run if the route/schema or fixture contract changes; preserve the one-packet and feature-parity guards.

## Tests

- Browser-free fixture contract: `python scripts/verify_control_room_rendering.py --check-fixtures`.
- Operations service tests: `pytest tests/test_control_room_operations.py tests/test_control_room_glance_integrity.py -q`.
- Static and build contracts: `pytest tests/test_control_room_static_views.py tests/test_control_room_build_contract.py tests/test_control_room_parity.py -q`.
- Focused source checks: assert that operational age/order/attention selectors in `app.js` consume payload fields and that no operational path calls `Date.now()` or applies a first-entry attention map.
- Render acceptance, with a candidate-bound preview and real screenshots: `python scripts/verify_control_room_rendering.py --profile acceptance --candidate <candidate-sha> --base <candidate-preview-url>`.
- If the preview is not separately reachable, run the profile against the candidate checkout and retain the report's explicit self-served preview status. Do not treat a report with zero captures, an unverified candidate, or omitted required classes as acceptance.

## Acceptance

- `/api/operations` has one service-owned, deterministic projection for packet metadata, attention, active/promotable/failed rows, worker health, projection lag, safe actions, degradation, run state, progress, and observation age. The client does not reorder, collapse, age, or classify these values.
- Every operator-facing state screen has a fixture and a rendered assertion: running has a live marker and fresh observation; blocked has decision target/kind/epoch/authority/eligibility and only packet-permitted actions; stalled has heartbeat/phase age and no fabricated zero; failed has terminal reason plus independent evidence; escalated has attempt tier boundary or an explicit `no cascade armed`; done distinguishes merged/projecting/published and shows receipt/projection state.
- The six state screens preserve the named mapping from `docs/research/control_room_state_screens.md`; `awaiting_approval` is never rendered as failed, and merged is never rendered as published.
- Worker identity, age, reason, failed-run detail, safe actions, ledger presence, knowledge metadata, timing scope, and log match/provenance are either visible in their owning surface or explicitly named as unavailable/unknown. No service-provided field is silently reduced to a count or dropped from the drawer without a documented reason.
- `recorded`, `unbound`, and `unavailable` remain distinguishable in logs and derived blocks. Unknown cost remains literal `unknown`; measured zero remains metered; no absent value becomes `0`, blank, or an all-clear.
- The deterministic fixture gate passes, the focused service/static tests pass, and the acceptance profile executes all five required classes.
- The acceptance report has a verified candidate SHA, candidate-bound captures with non-zero bytes, and screenshots for operations in dark/light plus the state/detail cases added by this phase. A report with no captures is a structural failure.
- The report states the still-omitted coverage honestly. Mobile, forced-colors, WCAG contrast, first-paint, and parked legacy classes are not acceptance claims unless their checks are actually run.

## Risks

- **Second source of truth:** adding an age/order helper in `app.js` instead of the service would preserve the L23 defect. Mitigation: unit-test payload order and injected time, then assert the browser renders that order unchanged.
- **Causal overreach:** mapping an attention or state observation to “the agent caused” a failure would violate the read-model boundary. Mitigation: use selection/delivery language and retain evidence-class labels; do not add causal fields without a producer.
- **Fixture-only success:** a rich JSON fixture can pass while the real service omits fields. Mitigation: assert the Python service payload and the browser's rendered selectors separately, then run the candidate-bound gate.
- **False named state:** treating a missing worker read as zero or a missing age as current would make the room look healthier than its evidence. Mitigation: test `unavailable` and `unknown` variants explicitly, including worker-read failure.
- **Lifecycle collapse:** mapping `promotable`, `awaiting_approval`, `merged`, or `projecting` into the existing Fleet vocabulary can erase operator decisions. Mitigation: preserve raw state and render an explicit unknown/raw token until a reviewed mapping exists.
- **Capture drift:** reusing the incumbent 23 screenshots could make the report appear to prove the new values. Mitigation: regenerate captures from the candidate checkout and bind the report to its SHA; verify files and bytes mechanically.
- **Over-expansion:** trying to repair every parked legacy board in this phase could obscure the L23/L33 acceptance target. Mitigation: keep the change centered on operations/glance/run detail and state screens; list unrelated board coverage as omitted unless the gate runs it.
- **Ignored notes:** a plain `git add notes/` will refuse these files. Mitigation: stage with `git add -f notes/` and verify the staged paths before committing.
