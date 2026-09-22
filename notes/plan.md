# Control Room Detail Truth Plan

## Files

| File | Change | Ownership rule |
|---|---|---|
| `apps/control_room/services/operations.py` | Add a service-owned Operations row projection and named blocks for attention/order/age, safe actions, workers, and projection detail. Reuse `run_evidence` rather than duplicating derivations. | The service owns measured facts and state labels. It selects and delivers evidence; it never claims knowledge use or causation. |
| `apps/control_room/services/context.py` | Keep the application-context boundary read-only and ensure collector failures remain named in the payload. Add tests only if the new block needs an accessor. | An unreadable control DB, Redis, ledger, or projection store is `unavailable` with a reason, never an HTTP 500 or zero-count all-clear. |
| `apps/control_room/routes/operations.py` | Preserve the existing endpoint and status contract while exposing the additive service-owned row blocks. | Routes delegate to services; they do not derive values or open their own stores. |
| `apps/control_room/static/app.js` | Make the Operations board render the server row projection. Remove client-side attention membership, urgency sort, and `Date.now()` age calculation for Operations rows; retain formatting, table construction, filtering, and focus behavior. | The browser is a formatter and interaction layer, not a second authority. |
| `apps/control_room/verification/fixtures/boards_endpoints.json` | Extend the normal, empty, unbound, unavailable, and partial-state fixtures with the exact named values and reasons. Add safe-action, worker-detail, projection-health, and full row-facet cases. | Fixtures are the wire contract the gate reads. Every new value must be non-empty or explicitly named absent. |
| `scripts/verify_control_room_rendering.py` | Extend `check_boards_fixtures()` and the restored-board acceptance class to assert server-owned order, age labels/states, row facets, safe-action binding, worker/projection details, and each required state screen. | A missing request, missing capture, omitted class, or vacuous empty panel fails. |
| `apps/control_room/verification/gate_report.md` and `gate_report.json` | Regenerate the candidate-bound report and list every new capture. | The report must say which candidate was exercised and must not claim proof from a zero-capture run. |

## Tests

1. Run the focused service/read-model tests covering `operations`, `context`, `run_evidence`, and
   the Control Room route parity. Add pure tests for deterministic row projection with an injected
   clock: current timestamp, stale timestamp, absent timestamp, packet order ties, and missing
   ledger.
2. Test that a measured zero remains a measured cost, an absent cost is `unknown`, a missing
   ledger is `absent`, and logs distinguish `recorded`, `unbound`, and `unavailable`.
3. Test that attention/order is copied from the service row projection and that the client no
   longer sorts rows or recomputes `started.age` from wall-clock time.
4. Run the deterministic fixture gate:
   `python3 scripts/verify_control_room_rendering.py --check-fixtures`.
5. Run the required browser gate with the candidate identity and captures:
   `python3 scripts/verify_control_room_rendering.py --profile acceptance --candidate <sha>`.
6. Review the generated report for `executed_classes == requested_classes`, candidate-bound asset
   hashes, non-empty screenshots, and no named-state or overflow violations.

## Acceptance

The work is accepted only when all of the following are true:

- Every Operations row value is sourced from the service payload. The client does not derive
  attention membership, urgency order, or started age from partial rows or `Date.now()`.
- The service emits the full roster facets: run identity, spec/cell, model/provider, phase
  progress, lifecycle, live state, source commit, target, attempt, cost provenance, attention,
  measured/advisory evidence, decision eligibility, and receipt. Missing fields carry a named
  `unknown` reason.
- The Operations board renders the packet's safe actions with run, gate, candidate, and action
  bindings. It renders unhealthy worker identity/age and projection health/age/error detail rather
  than only aggregate counts.
- Healthy populated, healthy empty, degraded control-plane, partial surface, unknown ledger,
  unbound logs, unavailable logs, and recorded logs each have a visible named state. No state is
  represented only by a blank panel, a fabricated zero, or a 500 response.
- Selection/delivery labels remain explicit: selected evidence is not described as used, relevant,
  causal, or outcome-producing without an independent record.
- The fixture gate asserts all new wire values, and the acceptance render gate runs navigation,
  loading, degraded, scrolling, and keyboard with candidate-bound captures. The capture set must
  include the existing Operations/degraded/drawer proof plus the new state-screen captures named
  below.

Required capture additions:

| State or value | Fixture | Capture |
|---|---|---|
| Full row facets, service order, server age, attention, action eligibility | normal `operations` with expanded row fields and `safe_actions` | `boards_operations_truth_desktop_dark_1440x900.png` |
| Healthy empty Operations state | new `operations_empty` | `boards_operations_empty_desktop_dark_1440x900.png` |
| Unbound logs and unknown ledger | `run_detail_unknown` | `boards_keyboard_drawer_unbound_desktop_dark_1440x900.png` |
| Unavailable logs/control read | new `run_detail_unavailable` or injected Redis failure | `boards_keyboard_drawer_unavailable_desktop_dark_1440x900.png` |
| Worker identity/age and projection state/age/error | normal operations plus unhealthy/projection detail fixture | `boards_operations_health_desktop_dark_1440x900.png` |
| Partial surface with sibling panels still rendered | existing `surface_failures` route case | `boards_surfaces_partial_desktop_dark_1440x900.png` |

The existing captures remain valid regression evidence: the navigation captures prove board
reachability, `boards_loading_operations_reload_desktop_dark_1440x900.png` proves lazy loading,
`boards_degraded_operations_desktop_dark_1440x900.png` proves the named control-plane outage,
and the keyboard drawer captures prove recorded cost/evidence/timing/log rendering and focus
return. They do not substitute for the new state captures above.

## Risks

- **Two authorities can return.** If `glance.py` and `operations.py` continue to construct row
  facts independently, the drawer and roster can diverge. Reuse `run_evidence` and test equality
  for the same run rather than copying formulas.
- **Order can imply causation.** An urgency-first table is a selection aid, not a causal graph.
  Name the order basis and preserve packet order as the deterministic tie-breaker.
- **Age can become a false zero.** Inject `now` into the service projection; absent or malformed
  timestamps must remain `unknown`, while a real future/zero age remains measured according to the
  existing telemetry convention.
- **Partial reads can regress to all-clear.** Do not use `|| []` as the semantic boundary for an
  unavailable block. Carry the named state/reason alongside empty arrays.
- **Fixtures can pass without a browser proof.** The gate must fail on omitted classes or zero
  captures and must verify served assets against the candidate commit.
- **Legacy parked gates can confuse acceptance.** The served-room acceptance profile is the five
  restored classes in `verify_control_room_rendering.py`; legacy workbench classes are not proof
  for this change.
- **Ignored notes are process records.** These requested notes are intentionally force-added for
  this handoff because the user explicitly requested a commit; future workflow runs should still
  follow the repository's normal notes/worktree convention.
