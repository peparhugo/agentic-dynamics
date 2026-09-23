# Control Room Detail Truth

## Problem

The L23 change established the served seven-board room, but its browser layer still answers
questions that belong to the server read model. In particular, `app.js` currently derives the
per-run attention value from the Operations `attention` list, sorts the combined active and
promotable arrays by a client-only `runLeads` predicate, and formats `started_at` into an age.
Those are not harmless formatting choices: they are operator-facing claims about priority,
ordering, and freshness. A second renderer, a changed packet, or a missing timestamp can make
the room disagree with the packet it is supposed to display.

The same renderer also hides data that the server already has. The Operations row schema lists
`run.live`, `terminal.target`, `attempt.number`, `cost.provenance`, `decision.eligibility`,
`decision.receipt`, `evidence.advisory`, `evidence.measured`, and `evidence.source`, but
`runFieldValue()` falls back to `unknown` for those fields because `/api/operations` does not
carry them. The glance read model already composes many of those values from the packet, control
records, and the recorded ledger. The result is a table that can look complete while omitting
the evidence the service actually knows.

The L33 failure makes the acceptance boundary concrete. The declared failure was:

`[desktop/boards/loading] operations-attention.state: the server-owned attention.state value
'active' was not rendered`

The requested report at
`experiments/results/control_room_render/L33_candidate_f7ab43551/gate_report.json` is not
present in this checkout, and its archived ref is not present locally either. I therefore use
the preserved register row and workflow domain context for the failure description, not an
invented reading of an absent JSON file. The frozen candidate is not modified.

L47 is the governing acceptance rule: an in-cell pytest pass is not browser acceptance. The
container cannot run Playwright, so `scripts/verify_control_room_rendering.py --profile
acceptance` must run on the host against this exact candidate, produce captures, and prove that
the candidate's own renderer paints every asserted value as visible text. A `data-*` attribute
is metadata, not rendered evidence.

## What Exists

### Authorities and transports

`src/agentic_dynamics/control/control_db.py` owns the enforced `RunState` vocabulary:
`queued`, `running`, `awaiting_approval`, `verifying`, `promotable`, `promoting`, `merged`,
`projecting`, `published`, `failed`, `cancelled`, and `quarantined`. There is no `stalled` or
`escalated` `RunState`; those names in the research state-screen document are operator views
that require a reachable database state plus an observation, or must be removed from the served
roster.

`src/agentic_dynamics/control/control_status.py` builds the one packet. It owns packet identity,
run lists, approvals, failed runs, unhealthy workers, projection lag, safe actions, and degraded
notes. Its null-not-zero rules are already tested: an unobserved worker population is an empty
list plus a degraded note, and a projection that never reported is `null`, not `0`.

`apps/control_room/services/context.py` is the composition boundary. `ControlRoomServices` opens
the read-only ControlDB, gathers the repository head and worker heartbeats, and converts failures
to a named `degraded` entry while returning HTTP 200. It must remain the owner of dependency
injection; routes should not reacquire state from server globals.

`apps/control_room/services/operations.py` is the Operations read-model owner. Its
`operational_snapshot()` calls `build_packet()`, projects packet attention rows, and passes
through `active_runs`, `promotable_runs`, `unhealthy_workers`, `projection_lag`, `safe_actions`,
and `degraded`. Its `run_detail()` passes through the raw control records and adds the shared
`run_evidence.py` blocks. It already names log states `recorded`, `unbound`, and `unavailable`.

`apps/control_room/services/run_evidence.py` is the shared owner for ledger-derived cost,
evidence, recorded-artifact, knowledge-delivery, prepared-step, and timing labels. It preserves
measured zero cost, distinguishes unknown cost, and never turns an absent timing into zero. Any
Operations/glance reuse should call this owner rather than copy its rules.

`apps/control_room/routes/operations.py` is transport only: `/api/operations` serves the
Operations snapshot and `/api/runs/<run_id>` serves run detail. `apps/control_room/routes/glance.py`
currently assembles the glance row and system blocks; its `_run_row()` exposes identity, cell,
target, command, model, attempt, phase, lifecycle, liveness, commit, cost, attention, evidence,
eligibility, receipt, epoch, and events. Its `_worker_health()` already distinguishes observed
healthy, observed degraded, and unobserved workers, although it currently uses `age_seconds: 0`
for the named state block. The Operations work should reuse the shared service vocabulary rather
than silently diverge from glance.

### Value ownership and current visibility

The table is the acceptance inventory. “Target owner” states where the value must be computed or
selected. “Fixture assertion” names the deterministic data contract. “Capture” names the current
render-gate evidence class or the required new capture when no current capture proves the claim.

| Value the room derives or hides | Current behavior | Target owner | Fixture assertion | Capture evidence |
|---|---|---|---|---|
| `source.packet_schema`, `source.control_epoch`, `source.repo_head_sha` | `/api/operations` emits them and `renderTruthStrip()` displays them. The client only formats the display. | `operations.operational_snapshot()` projects the packet source; `control_status.build_packet()` remains authoritative. | `boards_endpoints.json:operations.source` must match the expanded Operations payload; the fixture check must reject a missing source block. | `boards-loading` Operations reload capture; the same values are also visible in the Operations board navigation capture. |
| Active/promotable run populations and their counts | `app.js` computes counts with `active.length` and `promotable.length`, then concatenates the arrays. | `operations.py` should expose the packet populations plus server-owned summary/count fields, or explicitly define that the count is the length of the emitted population. | `boards_endpoints.json:operations` and `operations_degraded`; assert normal counts are measured and degraded counts are `unavailable`, never `0`. | `boards-loading` for normal values and `boards-degraded` for unavailable values. |
| Decisions owed / `attention` rows | `operations.py` projects approval and failed packet rows, but the table is rendered from the client list. | `operations.py` owns the ordered attention projection; packet identifiers remain selected from `control_status`, never inferred from DOM rows. | Assert every attention `run_id` exists in the service-emitted run roster, with stable order; preserve `test_attention_is_a_projection_of_the_packet`. | `boards-loading` Operations attention section. |
| Per-run `attention.state` (`active` or `none`) | `runAttentionValue()` derives it from a client `Map`; `active` is placed in `data-attention-state` and the kind word is painted. The failed L33 assertion caught the case where the server-owned value was not visible. | `operations.py` should emit the state on each row, using the packet attention projection; `app.js` should render that emitted value as text. | Add `attention.state` to the Operations run seed and assert the row's state equals the `state_screens[i]`/run identity contract. Assert the fixture includes both `active` and `none`. | `boards-loading` must visibly show `active` in the Operations attention field; the gate check must inspect text, not only `data-*`. |
| Run order / triage priority | `runs = active.concat(promotable)` and a client `Array.sort()` moves `runLeads()` rows first. This is a client-side causal/priority decision. | `operations.py` owns triage order, with a named order basis; `routes/operations.py` only delivers it. | Assert `state_screens[i]` and `runs[i]` have identical identity and order. Reject a hand-authored screen list that the service could not emit. | `boards-loading` shows the top order; `wheel-below-fold` proves the ordered roster reaches its last row. |
| Started age / freshness | `runFieldValue("started.age")` calls client `formatAge(entry.started_at)`. Missing `started_at` becomes a client unknown. | `operations.py` should emit a named measured/unknown age derived from injected `now`, or emit the timestamp plus an explicit state and keep formatting purely presentational. | Add fixed `now`, `started_at`, and age-state cases to `boards_endpoints.json`; assert no age is computed from a browser clock in the fixture gate. | `boards-loading` shows measured age; the degraded/loading capture shows the named unknown case if the source is absent. |
| Run identity, spec/cell, model, phase progress, lifecycle, source commit | The packet rows flow through and the client displays them in `RUN_FIELDS`; lifecycle values outside the old fleet vocabulary become an `unknown` chip with the raw state. | `control_status` owns lifecycle and identity; `operations.py` owns the Operations row projection. `app.js` should not normalize a RunState into a different lifecycle state. | Assert the expanded rows preserve `run_id`, `spec_name`, `model`, phases, `state`, and candidate SHA exactly. | `boards-loading`, plus `wheel-below-fold` for stable row identity. |
| `run.live`, `terminal.target`, `attempt.number` | The row schema claims these fields, but `runFieldValue()` currently falls through to `runUnknown()` because Operations does not emit them. Glance has corresponding values. | `operations.py` should reuse the control records and `run_evidence.py`/glance derivations and emit named fields; the client should only paint them. | Add these fields to `operations.run_seed`; assert a measured case and an explicit unknown case, rather than accepting the current “not emitted” fallback. | `boards-loading` visible run roster; `drawer-open` can cross-check the selected run detail. |
| Cost provenance and evidence: `cost.provenance`, advisory/measured/source | Operations detail already owns these blocks through `run_evidence.py`, but the roster hides them as unknown and the glance row is not used by the Operations board. | `run_evidence.py` remains the single derivation owner; `operations.py` exposes the row projection and detail blocks. | Reuse `run_detail` measured-zero, independent-test, recorded-ledger, and unknown cases; add the same provenance to the Operations row seed. | `drawer-open` and `drawer-logs` currently prove detail evidence; the updated `boards-loading` capture must prove the row values. |
| Decision eligibility and receipt | The client hides both with the generic unknown path even though glance composes eligibility and receipts from packet/control records. | `operations.py` should expose `decision.eligibility` and `decision.receipt`; `control_status.safe_actions` remains the action authority. | Add an approval/promotable row and a missing-receipt row; assert eligibility is one of the legal packet states and receipt absence is named. | `boards-loading` for the row; `drawer-open` for command/approval receipt details. |
| `safe_actions` | `operations.py` passes the packet block through, but `app.js` deliberately does not render it. It is therefore hidden, not absent from the server. | `control_status` owns safe-action derivation from `ALLOWED_TRANSITIONS`; `operations.py` owns delivery; the UI may render it read-only without inventing controls. | Add a safe-action fixture block tied to the same run/candidate IDs and assert every action is a legal packet action. | No current Operations capture proves this hidden block. Add a loading/Operations capture or explicitly document that it is API-only. |
| `unhealthy_workers` and worker health state | The service passes the list, but `app.js` renders `String((data.unhealthy_workers || []).length)`. An unobserved/degraded source therefore displays fabricated `0`. | `control_status` owns worker observations; `operations.py` owns a named worker-health block (`up`, `degraded`, or `unavailable/unknown`) and its reason. | Extend `operations_degraded` with a degraded `unhealthy_workers` source and assert the rendered metric is `unavailable`, not `0`; preserve the observed stale-worker case in `operations`. | `boards-degraded` must visibly show `Unhealthy workers: unavailable`; normal observed workers are shown in `boards-loading`. |
| Projection lag and projection health | Packet values pass through; the client renders values but an empty object becomes “No projection watermarks reported.” | `control_status`/projection watermarks own lag and health; `operations.py` owns the named degraded projection surface. | Keep `0` for current measured watermarks, `null`/unknown for never-reported or stale values, and assert the degraded reason. | `boards-loading` normal lag table; `boards-degraded` named absence. |
| Degraded surfaces and reasons | `operations.py` returns named entries and `app.js` renders their surface/reason table. | `operations.py` owns the envelope; client only renders the supplied labels. | `operations_degraded.degraded` must contain `control_db` and the worker source where applicable. | `boards-degraded` Operations capture. |
| Run-detail raw records and derived blocks | `run_detail()` is already service-owned and the client renders attempts, gates, approvals, commands, cost, evidence, recorded, delivered knowledge, prepared, timings, and logs. | Keep `operations.py` plus `run_evidence.py`; do not duplicate these derivations in the browser. | `run_detail`, `run_detail_unknown`, and `run_detail_error` assertions in `check_boards_fixtures()`. | `drawer-open`, `drawer-logs`, and the dark/light keyboard captures. |
| Glance row and system dimensions | `routes/glance.py` owns a rich row and named worker/projection/system states, but the restored Operations tables do not display the glance row. | Keep glance projections in their route/service boundary and make Operations reuse shared evidence helpers. If the UI claims glance values, expose them through an Operations contract first. | `F-0.json`/parity fixtures cover the legacy/glance vocabulary; add an Operations fixture only if the restored board claims these values. | No current restored-board capture proves the hidden glance row. Do not cite legacy parked captures as evidence for the served Operations board. |
| Required state screens | The served Operations board renders only active/promotable rosters plus attention and does not render a complete state-screen roster. | `control_db.RunState` is authoritative; `operations.py` maps reachable states to screen rows. `stalled` and `escalated` require real observations or must be removed. | Add `state_screens` generated from the same `runs` seed and assert identity/order; cover `unknown`, `promotable`, `cancelled`, and `quarantined`, while separately proving any observation-backed screen. | `boards-loading` for the normal roster and a new state-roster capture/check; `boards-degraded` for unavailable dependencies. |

### Honesty rules

The room's service contract is named availability, not optimistic emptiness. `recorded`,
`unbound`, and `unavailable` are states; an absent cost is `unknown`; a measured zero remains a
measured zero; a worker list that could not be observed is not a healthy empty list. The renderer
may format a value, but it may not decide its causal meaning, urgency, order, age, or lifecycle.

The fixture is a contract, not a second hand-written application. The safest form is a fixture
payload generated from the service read-model contract. If deterministic generation is not
practical, the fixture gate must at least prove `state_screens[i]` and `runs[i]` have the same
identity and order. This is the minimum protection against a fixture that passes while the
service could never emit the claimed pairing.

## Gaps

1. The requested L33 `gate_report.json` is absent locally, so the failure is preserved through
   the register/workflow record rather than a locally verifiable report artifact.
2. `app.js` still derives `attention.state`, urgency order, and started age.
3. Operations passes packet run entries through, but the renderer hides several server-available
   glance/evidence fields behind `unknown`.
4. `unhealthy_workers` is rendered as a list length, so degraded or unobserved input can look
   like a measured zero.
5. The current fixture expands only active/promotable rows and has no `state_screens` identity /
   order invariant.
6. The research state-screen roster includes `stalled` and `escalated`, but those are not
   `RunState` values and escalation has no current mechanism. The implementation must not mint
   lifecycle states merely to satisfy a screen label.
7. The current host gate asserts rendered behavior but the failed candidate exposed `active`
   only through a data attribute. The assertion and renderer were not joined by visible text.
8. Attempt eleven shows a separate contract risk: replacing `unhealthy_workers` with a new
   `worker_health` read without updating `tests/test_control_room_static_views.py` made the
   declared suite fail at 78/79. The static anchor suite is part of the read contract.

## Sources

The machine-readable source ledger is `notes/sources.jsonl`. The primary sources are:

- `docs/reviews/loose_ends_register.md`, rows L23, L33, and L47.
- `workflows/repository/control_room_detail_truth.yaml`, especially the domain context and the
  five declared gate suites.
- `apps/control_room/services/operations.py`, `context.py`, and `run_evidence.py`.
- `apps/control_room/routes/operations.py` and `routes/glance.py`.
- `src/agentic_dynamics/control/control_db.py` and `control_status.py`.
- `apps/control_room/static/app.js`, `shell.js`, `board-fleet.js`, and `index.html`.
- `apps/control_room/verification/fixtures/boards_endpoints.json` and `F-0.json`.
- `scripts/verify_control_room_rendering.py` and the Control Room test suites.
- `docs/research/control_room_state_screens.md` for the prior operator-view design, subject to
  reconciliation with the reachable `RunState` vocabulary.
