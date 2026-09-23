## Problem

L23 is recorded as promoted, but its adversarial review is not present in this checkout. The
surviving register row is the authoritative L23 summary: commit `1b1697e1d` restructured the
resting room into a packet header, attention rows, and per-run inspection rows, and reported 23
candidate-bound captures plus 121 focused tests. The row preserves two findings for this follow-up:

1. The served Operations board still derives attention/order and run age in the browser.
2. The read models already carry useful per-run and glance values, but the served tables omit
   those values and the required state screens are only partially represented.

This checkout has no L23 run clone, no `notes/adversarial_review.md`, and no control database from
that run. I therefore do not treat an unavailable review as evidence. The L23 register row,
current source, committed fixtures, tests, and render-gate report are the evidence used here.

There are also three different candidate identities in the surviving evidence. The L23 register
names promoted commit `1b1697e1d40bcd981431a186f5850ddf421105e9`; the committed render report is
bound to `489b0bf15b467fae5e2892bbcadc9385cc6da4b9`; and the Operations fixture source is bound to
`bc2c728633273947d278f285c2e8929946aaa082`. These identities must be reconciled before a future
render-gate result is treated as evidence for the implementation that is being promoted.

The honesty rule is non-negotiable. A read model may report `recorded`, `unbound`, `unavailable`,
`unknown`, or another named state supported by its authority. It must not turn missing evidence
into zero, all-clear, a guessed workspace, a guessed stream, or a successful HTTP response that
looks like a healthy empty board. Services own selection and delivery; they do not claim that
selected knowledge caused an outcome.

## What Exists

The following inventory covers every value in the current Operations and glance contracts that is
derived, rendered, or currently hidden by the served room. "Capture" is deliberately literal: a
capture is listed only when the current acceptance report says that the served page produced it.
`none yet` identifies a gap for the implementation phase, not proof that the value is already
covered.

| Value or behavior | Service that owns it | Current served behavior | Fixture the gate can assert | Capture showing it |
|---|---|---|---|---|
| Packet schema, control epoch, and repository head | `services/operations.py:326-365`, fed by `control_status.build_packet` | Rendered in the Operations metric cards and truth strip | `boards_endpoints.json.operations.source` (`control_epoch`, `repo_head_sha`) | `boards_operations_desktop_dark_1440x900.png`; also light and narrow Operations captures |
| Active-run, promotable-run, decision-owed, and unhealthy-worker populations | `services/operations.py:349-364` pass-through from the packet | Counts are rendered; active and promotable entries are concatenated into one roster | `boards_endpoints.json.operations.run_seed`, `active_count`, `promotable_count`, `attention`, and `unhealthy_workers` | `boards_operations_desktop_dark_1440x900.png` and `boards_operations_narrow_dark_1024x768.png` |
| Projection lag and its absence | `services/operations.py:357-364`, with the packet's projection watermark result | Rendered as a table; an empty map becomes `No projection watermarks reported.` | `boards_endpoints.json.operations.projection_lag`; `operations_degraded.projection_lag` is the empty/degraded case | Operations desktop and narrow captures; the degraded Operations capture shows the degraded sibling state |
| Named degraded surfaces and reasons | `services/context.py:124-165` and `services/operations.py:326-365` | A degraded table is rendered; an unreadable control DB becomes named `unavailable` text rather than zero | `boards_endpoints.json.operations_degraded.degraded` with `surface=control_db` and a reason | `boards_degraded_operations_desktop_dark_1440x900.png` |
| Attention rows and their packet identifiers | `services/operations.py:342-347`; the packet is the authority for `run_id`, `gate_id`, `candidate_sha`, and purpose | The table is rendered from the packet, but row emphasis and section order are derived in `app.js` | `boards_endpoints.json.operations.attention` contains approval and promotion rows tied to fixture run IDs | `boards_operations_desktop_dark_1440x900.png`; current capture does not prove the derivation basis |
| Attention classification (`active`/`none`) | Should be emitted by `services/operations.py` as a row field, based on the packet attention block | `app.js:3120-3136` re-derives it by matching `attention` to each run | Extend `operations.run_seed` with explicit row attention state and assert parity with `attention` | No current capture proves server ownership; required in the refreshed Operations desktop and narrow captures |
| Run ordering / "leads" triage | Should be emitted by `services/operations.py` as an ordered run list or explicit rank, using packet attention and legal run state | `app.js:3139-3143` and `3368-3371` classify and sort client-side; the packet order is otherwise retained | Extend `operations` with at least one attention/failed row and one ordinary row, plus an explicit expected order; assert the wire order is preserved | Operations desktop capture shows a visual order, but no current capture proves its server basis; refresh the same named Operations captures after the move |
| Run age / started age | Should be emitted by `services/operations.py` from an injected observation time, or as a named unknown; it must not read the browser clock | `app.js:158-168` uses `Date.now()` and formats `started_at` in both the roster and drawer | Extend `operations.run_seed` and `run_detail.run` with a deterministic observation/age field, including an unknown case; assert no client-clock value is needed | Operations desktop/narrow and keyboard drawer captures currently show age-shaped output, but not deterministic server ownership; refreshed captures are required |
| Run identity, spec, model, lifecycle state, phase progress, candidate commit, and `started_at` | Packet fields are passed through by `services/operations.py`; `routes/operations.py` exposes them without reshaping | The roster renders only the fields selected by `RUN_FIELDS`; some missing values fall back to client text | `boards_endpoints.json.operations.run_seed` and expanded `active_runs`/`promotable_runs` | Operations desktop, light, and narrow captures |
| Live state, terminal target, attempt number, cost provenance, eligibility, receipt, advisory evidence, measured evidence, and evidence source | `services/run_evidence.py` owns cost/evidence/attempt/target derivations; `routes/glance.py:419-458` composes the 16-field row | The served Operations payload does not carry these fields, so `app.js:3176-3180` paints labelled `unknown`; the parked `parity.js` displays a different table and is not acceptance evidence | `boards_endpoints.json.run_detail` carries the raw/detail source and additive `cost`, `evidence`, `recorded`, `prepared`, `timings`, and knowledge blocks; add an Operations row fixture sourced from the same derivations | No current acceptance capture shows these fields in the Operations roster; the keyboard drawer captures show related detail blocks only |
| Safe actions and their gate/run/candidate bindings | `control_status.build_packet` derives them from the enforced transition graph; `services/operations.py:363` passes them through | The served Operations renderer hides them; the parked `parity.js:1828-1839` renders them, which is not the served-room contract | Add `safe_actions` to `boards_endpoints.json.operations`, plus empty and degraded variants; assert the rendered rows retain action/run/candidate/gate exactly | No current served Operations capture; required in the refreshed Operations capture if this value remains in the board contract |
| Raw run records: attempts, gates, approvals, and command receipts | `services/operations.py:390-400` passes `ControlDB` records through; `routes/operations.py:38-41` serves them | The drawer renders generic tables for each raw block | `boards_endpoints.json.run_detail.attempts`, `.gates`, `.approvals`, `.commands` | `boards_keyboard_drawer_dark_1440x900.png` and the light counterpart |
| Cost provenance, measured verification, agent narration, and decision receipt | `services/run_evidence.py:307-341` | The drawer renders these additive blocks; measured zero remains metered and absent cost remains unknown | `boards_endpoints.json.run_detail.cost`, `.evidence`, `.recorded`, plus `run_detail_unknown.cost.provenance=unknown` | `boards_keyboard_drawer_logs_dark_1440x900.png`; the current report says the gate also exercises the unknown-cost path, but has no separate capture for it |
| Delivered knowledge and prepared-step references | `services/run_evidence.py:364-450`; selection/delivery only, with `use=not_established` | The drawer renders IDs, provenance, fallback/errors, and prepared path/hash | `boards_endpoints.json.run_detail.delivered_knowledge` and `.prepared`; unknown detail uses named `absent` states | Keyboard drawer logs capture; the fixture gate asserts IDs and the prepared path even when no separate screenshot exists |
| Timing rows and measured/unknown timing state | `services/run_evidence.py:453-513` | The drawer renders timing values and state markers | `boards_endpoints.json.run_detail.timings`, including `phase.duration_s=0.0` measured and `phase.first_token_at=null` unknown | Keyboard drawer logs capture; the fixture gate asserts an unknown timing row |
| Fleet-job log state, binding, match basis, event count, and bounded events | `services/operations.py:45-99,202-275` | The drawer renders the retained event tail; `recorded`, `unbound`, and `unavailable` are distinct | `boards_endpoints.json.run_detail.logs`, `.run_detail_unknown.logs`, and `.run_detail_error` | `boards_keyboard_drawer_logs_dark_1440x900.png` and light counterpart |
| Glance system dimensions: browser, control plane, workers, projections, with ages | `routes/glance.py:148-215` and `_system_block` | The current served seven-board room does not render the `/api/glance` system blocks as its Operations table | `F-0.json.system` plus F-4/F-5/F-6 deltas; these are legacy parked fixtures, not current Operations fixtures | None in the current acceptance profile; legacy parked screenshots cannot be cited for the served room |
| Glance trust epoch, worst age, projection state, degraded/stale/partial/unknown counts | `routes/glance.py:218-247` | Derived server-side but not shown in the served Operations roster | `F-0.json.trust` plus F-4/F-5 deltas | None in the current acceptance profile |
| Glance decision, risk, and next-item selection | `routes/glance.py:250-339` | Derived server-side, but the served Operations board has its own attention table and hides the glance blocks | `F-0.json.attention`, plus F-7 empty-queue delta | None in the current acceptance profile |
| Glance run counts, cost/money risk, health detail, and composition | `routes/glance.py:342-356,461-507,510-557`; cost reads `services/subscription_usage.py` | The values exist in the glance projection; the restored Operations board does not display them as the glance row | `F-0.json.run_counts`, `.cost`, `.health_detail`, `.composition`, plus F-1..F-7 deltas | None in the current acceptance profile |
| Required lifecycle state screens | Packet state is owned by `control_status` and pass-through belongs to `services/operations.py`; per-run evidence remains in `run_evidence.py` | The served board has generic lifecycle chips and a generic roster, not the complete running/blocked/stalled/failed/escalated/done truth-table screens; `promotable` and `awaiting_approval` become unknown lifecycle tokens in `app.js:3085-3110` | Add named state variants to `boards_endpoints.json` and assert primary elements plus unknown/degraded states; retain `run_detail_unknown` and `run_detail_error` for absence paths | Existing Operations captures show only the generic roster; no current capture proves all state screens |

The current gate does prove useful structural behavior: the served shell, seven-board navigation,
lazy loading, degraded rendering, scrolling, and keyboard entry to the drawer. It does not prove
that the hidden fields above are absent from the wire for a principled reason, nor that the client
does not re-derive attention/order/age. The distinction matters because `tests/test_control_room_static_views.py`
explicitly records that safe actions are not rendered by the served Operations board, while the
parked workbench does render them.

## Gaps

### Surviving evidence gaps

- The L23 `notes/adversarial_review.md` cannot be recovered from this checkout. The expected
  `/tmp/agentic-dynamics-runs/run-56d270a29a28/repo` clone and `experiments/results/` are absent.
- The committed gate report, its fixture source, and the promoted L23 commit carry different SHAs.
  A future report must bind the candidate, served bytes, and fixture-backed assertions to the same
  candidate identity.
- The acceptance report lists 23 screenshots, but several gate result entries are structural checks
  with an empty `screenshot` field. That is valid for non-visual checks, but it must not be used as
  evidence for a value that is only asserted in the DOM.
- The profile omits mobile, forced-colors, contrast, first-paint, and the parked legacy classes.
  No claim about those surfaces can be made from the current report.

### Product and ownership gaps

- `app.js` computes attention membership, lead classification, run order, and age. These are
  consequential triage/presentation values and should be emitted by the server read model with an
  injected observation basis.
- `operations.py` passes through `active_runs`, `promotable_runs`, and detail blocks, but the
  served roster does not consume the row values already composed by `glance.py` and
  `run_evidence.py`. This creates a visible mismatch between what the authority knows and what the
  operator can inspect.
- `safe_actions` are carried by the packet and by the Operations service but are hidden by the
  served renderer. If they remain part of the Operations contract, they need a served-board fixture
  and capture; if they do not belong there, the service contract and plan must say so explicitly.
- The current board has a generic lifecycle chip, but it does not render the complete state-screen
  truth table requested by `control_room_run_states.yaml`. The fixture has no one-to-one coverage
  for running, blocked, stalled, failed, escalated, and done.
- The existing `F-0..F-7` fixtures describe the parked glance/workbench contract. They are useful
  source vocabulary for named states, but they cannot substitute for `boards_endpoints.json` when
  the served restored-board gate is the acceptance target.

## Sources

The machine-readable source inventory is in `notes/sources.jsonl`. Important source classes are:

- L23 register and workflow definition: the only surviving L23 review summary and the exact prior
  phase prompt.
- Server read models and routes: packet pass-through, run detail, shared evidence derivation, and
  glance row composition.
- Served static room: `index.html`, `app.js`, `shell.js`, and `board-fleet.js`; `parity.js` is
  explicitly marked parked and is not acceptance evidence.
- Fixture and gate: `boards_endpoints.json`, `F-0.json`, `verify_control_room_rendering.py`, and
  the committed JSON/Markdown gate reports.
- Focused tests: Operations parity/absence tests, glance derivation parity, static-view contract,
  and restored-room feature-parity tests.
