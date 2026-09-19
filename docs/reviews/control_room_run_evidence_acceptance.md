---
status: proposed
---

# Control Room — run-evidence slice: acceptance record (2026-09-19)

**Deliverable.** The served run drawer explains a real run: cost with provenance, verification
with independence kept separate from the agent's claim, delivered knowledge (selection +
delivery, never "use"), the prepared-step reference (recorded going forward), and timings with
an explicit measured/unknown state — with the glance and run-detail surfaces sharing ONE set of
pure derivations at the service boundary.

**Identities.**
- Run: `run-dd5b2e19a0c2` (`control_room_run_journey` v0.2, base `0eb4b4592ccf`,
  model `deepseek/deepseek-v4-flash`, cost $0.164194, phases `evidence` + `verify` both ok,
  `test_executed_success: true`, `evaluator_independent: true`).
- Workflow candidate (as produced): `2e53b165b` (agent commits `73a05839f` + `2e53b165b`).
- Delivery head (this branch): `ca1ef46dc` — candidate + AIO remediation commits (drop the
  leaked prepared-step transport file; fix the drawer-content gate's row targeting, re-applied
  without an editor's whole-file reformatting), with the gate evidence rebound to the head.
- Spec: `workflows/repository/control_room_run_journey.yaml` (sha256
  `e6bf1d415b7a…` as submitted; spec bytes carried into the run clone).

**Independent verification (host-side, at the delivery head).**
- `pytest` on the spec's verification list + the prepared-step/namespace suites:
  **250 passed** in `/tmp/wt_run_evidence` (PYTHONPATH pinned to the candidate's `src/`).
- Render gate, restored-board acceptance profile:
  **PASS** — candidate `8d550763c` verified against the checkout HEAD, 21 captures,
  classes navigation/loading/degraded/scrolling/keyboard, 0 errors
  (`apps/control_room/verification/gate_report.md` + `.json` + screenshots, committed).
- Review fix the browser gate caught: the keyboard class focused `rows.first` — the Operations
  attention table's unknown-cost run — while its rich-content assertions are written for the
  rich fixture row; they were unreachable as produced. The gate now selects the rich row by id
  (`run-fixture-0001`) and the class passes end to end.

**Required-acceptance coverage (executed vs omitted — an omitted check is not a pass).**

| Requirement | Coverage |
|---|---|
| Normal + degraded payloads | gate degraded class (unreadable control db reads `unavailable`, never 0) + `/api/operations` degraded; run-detail 200 envelope case in the keyboard class |
| Missing + measured-zero cost | drawer measured-zero provenance on the rich row; explicit `unknown` on the no-ledger run (`run-fixture-0007`); service tests (measured zero stays metered) |
| Mixed provenance | shared `cost_provenance` label + glance-integrity tests (mixed stays mixed) |
| Failed/pending/non-independent tests | `evidence.measured` states incl. independence; glance-integrity tests |
| Missing knowledge artifacts | `delivered_knowledge.state`/`reason` named absence; service tests with and without a ledger |
| HTTP-200 error envelopes | gate drawer error case (`run-fixture-0008`) renders the named error; service/route tests |
| Saved-board reload | gate loading class (reload; exactly one request per endpoint) |
| Long-content wheel scrolling | gate scrolling class (real wheel input; negative case) |
| Enter / Escape / focus return | gate keyboard class (focus to drawer close; Escape returns focus to the originating row; drawer-first scope) |
| Loaded page, not parked parity.js | all classes exercise the served seven-board room; `parity.js` untouched |
| Desktop / narrow / mobile / accessibility | desktop + narrow EXECUTED (dark+light for navigation, dark for narrow); **mobile 390x844, forced-colors, WCAG-AA contrast OMITTED** (named in the gate report) |

**Unit 4 trace — an approved source, delivered, and observed in use.**
- Selected + delivered: run `run-75e8319533fb`'s ledger records `augmentation_evidence` = `{id: 3c4d382ea677…, revision: 121126dfb…, source_type:
  pattern, locator: workload:skill/flash-ladder/taskman#pattern}`, `fallback_mode:
  lexical_graph_only`, dense/embedding leg errors named; the prepared step
  (`prepared_step_generate.a1.json`, `prompt_sha256 784bdb0b…` verified) carries the citation
  `[K:3c4d382e…@121126dfb…:workload:skill/flash-ladder/taskman#pattern]`, and the worker's own
  child session contains it.
- Use observed: the delivered pattern's claim ("a single TaskManager over an id-keyed mapping,
  dependencies as explicit id lists, validation concentrated in `_require`/`_validate_*`
  helpers, cycle detection before any mutation") is mirrored by the worker's own commit
  (`136d1c2fc`): "a single TaskManager class over an insertion-ordered {id: task-dict} mapping …
  Validation is concentrated in private helpers (`_require_task` … `_detect_cycle`) …" — an
  authoritative DERIVED [C] record (support 12/12) informing a concrete implementation choice.
  Delivery remains qualified per the Unit 4B forensic note (image-baked-code caveat); use here
  is evidenced by the artifact's structure + the worker's record, not claimed beyond that.

**Residual gaps (named, not papered over).**
1. **Parent-side recording activates on the next run from merged code.** The prepared-step
   path/hash recording lives in the parent (orchestrator) — this run's parent executed
   pre-candidate code, so the run's own ledger truthfully shows the fields absent and the
   drawer names the absence for historical runs. The recording code + its tests are in this
   candidate; it is exercisable end-to-end only after merge.
2. **Prepared-step transport leak (recurring, with a separate fix).** The engine's post-phase
   `git add -A` committed `.fleet/prepared_steps/evidence.a1.json` into the candidate; the
   same mechanism has already landed `fit.a1.json`/`journey.a1.json` on main. Root cause:
   `_write_prepared_step`'s `.git/info/exclude` write silently no-ops when a run clone has no
   `.git/info/`. The fix + tests + the main cleanup ride `feature/prepared-step-commit-hygiene`
   (separate review); this branch drops the leaked file.
3. **Coverage omitted** (mobile viewport, forced-colors, WCAG-AA contrast, first-paint timing)
   as named above.
4. **Activation is distinct from merge.** The live portal process (started 2026-09-14) serves
   the current static files from disk but its route code predates this candidate: after merge,
   the portal must be restarted for the new `/api/runs` blocks to reach the live room. No
   restart now (pre-merge it would serve unchanged code).
