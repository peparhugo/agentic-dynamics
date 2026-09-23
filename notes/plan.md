## Files

The implementation should remain additive and should not create a new route or persistence plane.
The smallest ownership-preserving change is to enrich the existing Operations read model, reuse the
existing evidence helpers, and make the served renderer consume the enriched wire shape.

| File | Planned change | Design decision |
|---|---|---|
| `apps/control_room/services/operations.py` | Add server-owned row presentation fields and a deterministic ordered run list. Reuse the packet identifiers and `run_evidence` helpers. Compute age from an injected observation time or emit a named unknown; never read a browser clock here. | Operations is already the room's packet gate. Keeping the derivation here prevents a second client-side authority and preserves read-only behavior. |
| `apps/control_room/services/context.py` | Thread any observation-time input through the existing service seam if the implementation needs it; preserve the current named degraded response. | The composition root should choose the observation basis. A hidden wall clock inside a service would make fixtures and replay nondeterministic. |
| `apps/control_room/routes/operations.py` | Keep `/api/operations` and `/api/runs/<run_id>` shapes additive; document the new fields rather than adding endpoints. | Existing consumers and the render gate already use these routes. A new route would duplicate the packet authority. |
| `apps/control_room/services/run_evidence.py` | Reuse, or minimally expose, the existing cost, attempt, target, evidence, receipt, timing, and recorded-state helpers. Do not duplicate their logic in Operations. | This module already proves the glance row and drawer can answer the same question identically. |
| `apps/control_room/routes/glance.py` | Keep the existing glance row derivation as the shared semantic reference. If Operations needs the same row fields, call shared service helpers rather than copying `_run_row` logic into a route. | Selection and delivery are already distinguished here; the follow-up must not turn evidence IDs into a causal claim. |
| `apps/control_room/static/app.js` | Consume server-emitted attention/order/age and run facets. Remove client-side `runLeads`, `Array.sort` triage, and `Date.now()` age derivation from the Operations path. Render named state screens and any service-provided `safe_actions`; preserve the keyboard drawer and unknown labels. | The browser should format and lay out values, not decide what is urgent, how old it is, or which evidence state exists. |
| `apps/control_room/static/index.html` | Change markup only where the served Operations board needs explicit state-screen containers or stable labels. Keep one visible board, existing IDs, and the current drawer location. | The shell already owns board navigation and lazy loading; avoid moving data ownership into shell chrome. |
| `apps/control_room/static/shell.js` | No derivation change expected. Preserve board switching, lazy-load initialization, and scroll reset. | Shell is explicitly data-free and should not become another state authority. |
| `apps/control_room/static/board-fleet.js` | No Operations derivation change expected. Reuse its vocabulary only where the served state labels are semantically the same. | Lifecycle and attention are separate axes; do not map an attention verdict into a lifecycle color or token. |
| `apps/control_room/verification/fixtures/boards_endpoints.json` | Extend the real served-board fixture with server-owned row fields, explicit ordered rows, safe actions if retained, deterministic age, and state variants. Keep recorded/unbound/unavailable examples. | This is the fixture the restored-board gate actually reads. `F-0..F-7` alone cannot prove the served Operations contract. |
| `apps/control_room/verification/fixtures/F-0.json` and `scripts/verify_control_room_rendering.py` | Modify only if the implementation intentionally re-houses glance values into the served room. Otherwise leave the parked glance fixture as prior art and do not claim it covers Operations. Add structural and browser assertions for the new wire fields and captures. | Acceptance must test the real served path, not a hand-written twin or parked module. |
| `tests/test_control_room_operations.py` | Add pure read-model tests for packet parity, explicit ordering, deterministic age, named unknown/degraded states, and safe-action field preservation. | These tests should fail if a server-owned value silently returns to client derivation or if missing data becomes zero. |
| `tests/test_control_room_glance_integrity.py` | Extend same-run parity tests so the shared row and drawer still agree after the Operations enrichment. | One run must have one answer for cost, evidence, receipt, target, attempt, and timing. |
| `tests/test_control_room_static_views.py` and `tests/test_control_room_feature_parity.py` | Replace tests that encode intentional omission only when the served board begins rendering the corresponding server fields; add guards against `Date.now()`/client sorting in the Operations renderer. | Tests must describe the served page, not the parked workbench. |
| `scripts/verify_control_room_rendering.py` | Extend `check_boards_fixtures()` and the acceptance browser probes to assert the exact server values, state screens, and capture count. Run with `--profile acceptance --candidate <same-sha>`. | A zero-capture run is a structural failure, and an unbound candidate is not evidence. |

## Tests

Run the deterministic fixture check first:

```text
python3 scripts/verify_control_room_rendering.py --check-fixtures
```

Run the focused room suite named by the workflow:

```text
pytest -q \
  tests/test_control_room_operations.py \
  tests/test_control_room_glance_integrity.py \
  tests/test_control_room_build_contract.py \
  tests/test_control_room_static_views.py \
  tests/test_control_room_paths.py
```

Run the served acceptance gate only after the fixture and focused tests pass:

```text
python3 scripts/verify_control_room_rendering.py --profile acceptance --candidate <candidate-sha>
```

The independent test phase declared by the workflow must also remain the named target, not a
zero-target interpretation of this prose:

```text
pytest -q \
  tests/test_control_room_operations.py \
  tests/test_control_room_glance_integrity.py \
  tests/test_control_room_build_contract.py \
  tests/test_control_room_static_views.py \
  tests/test_control_room_paths.py
```

The implementation phase should inspect the generated captures, not rely on a passing exit code.
At minimum, inspect the dark desktop Operations board, dark narrow Operations board, degraded
Operations board, and both dark/light keyboard drawer captures.

## Acceptance

- The server response contains every Operations roster value that the authoritative packet or
  shared evidence service can answer: identity, spec/cell, target, model, attempt, phase progress,
  lifecycle, live state, commit, cost provenance, attention, advisory evidence, measured evidence,
  evidence source, eligibility, receipt, and deterministic age state.
- The response carries an explicit ordered run list or equivalent server-owned rank. The client
  preserves that order and does not classify or sort runs by state/attention.
- The response carries an explicit age/age-state basis. The Operations renderer does not use
  `Date.now()` to turn `started_at` into an actionable value. Missing timestamps render a named
  unknown, never `0s ago` or an empty cell.
- `safe_actions`, if retained in the Operations contract, are rendered from the packet with their
  action, run, candidate, and gate identifiers. The page does not invent an action from a state.
- The complete state-screen fixture set covers running, blocked, stalled, failed, escalated, and
  done, plus unknown/unavailable. Each state has its primary elements asserted by the gate; no
  state falls through to a fabricated default.
- The existing recorded/unbound/unavailable log, unknown-cost, missing-ledger, unknown-timing,
  measured-zero, independent-verification, delivered-knowledge, and prepared-step cases remain
  green.
- The browser gate serves the actual Flask shell, intercepts the committed fixture routes, writes
  non-empty captures, and reports the same candidate SHA for source binding, fixture source, and
  gate report. The acceptance profile must show zero violations and no omitted required class.
- The refreshed Operations desktop and narrow captures visibly show the values moved from hidden or
  client-derived status into the server-owned renderer. A structural DOM assertion without a
  corresponding capture is not sufficient for this acceptance claim.
- The parked `parity.js`/legacy classes are not used as evidence for the restored served room.

## Risks

- **Candidate provenance drift:** The current report (`489b0bf...`), fixture (`bc2c728...`), and
  promoted L23 row (`1b1697e...`) disagree. Mitigation: fail acceptance unless one candidate identity
  binds the checked-out static bytes, fixtures, and report.
- **Clock nondeterminism:** Client `Date.now()` can make screenshots and ordering vary. Mitigation:
  inject a server observation instant or emit fixture age values and test the unknown branch.
- **Causation overclaim:** A selected knowledge ID or delivered prompt does not prove use or cause.
  Mitigation: retain `use=not_established` and keep evidence labels separate.
- **State vocabulary collision:** `promotable` and `awaiting_approval` are control run states, not
  Fleet lifecycle tokens. Mitigation: give them explicit state-screen semantics instead of mapping
  them to a generic `unknown` chip or silently changing the packet state.
- **Fixture twin:** A hand-written renderer fixture can pass while the real service emits another
  shape. Mitigation: assert the service-produced field names and values in focused tests, then use
  the same committed fixture through the real Flask/Playwright route interception.
- **Parked-surface confusion:** `parity.js` contains a richer Operations lens than the served
  `app.js`. Mitigation: acceptance selectors and captures must target `index.html`'s restored board
  and its loaded scripts only.
- **Degraded-state regression:** Enriching the happy path can turn an unreadable DB into zero rows.
  Mitigation: preserve `services/context.py`'s named 200 response and assert the degraded fixture
  still renders `unavailable` with its reason.
- **Responsive overload:** Adding all hidden fields can recreate mid-word truncation or below-fold
  loss. Mitigation: keep the wrapping E10 field grid, exercise desktop and narrow captures, and
  drop no field silently; use labelled unknowns and explicit state blocks.
