# Control Room — run-journey recovery: investigation and first slice

**Date:** 2026-09-18 · **Reviewed main revision:** `4d834e9a9aae` · **Deployed UI observed:** `100.83.229.3:8001`
(server routes loaded 2026-09-14, unchanged since; static served from the current checkout) ·
**Status:** investigation recorded; first slice implemented (reference) and delivered through the ordinary
workflow pipeline (run id recorded in the close/decision records).

This review separates four things the operator's "one screener" report conflated: the **historical
deletion**, the **subsequent restoration**, the **current deployed behavior**, and the **remaining gaps**.
It exists because a code-only reading of the first two produced a wrong present-state conclusion.

## 1. Historical deletion (2026-09-11)

- Commit `4535145a0` — *"[workflow] a0_ia_layout — Implement the Control Room facelift"* (produced by the
  `control_room_refresh_integration` workflow): `index.html` 847 → ~200 lines, static net **−7,617 lines**.
  The destinations nav and its boards — Fleet | Status | Flags | Sessions | Routing | Operations |
  Surfaces — plus the system sheet, transcript panes and supervisor review were removed.
- The single-resting-screen wireframe (`docs/research/control_room_wireframe.md`, commit `5dabc9d99`,
  phase `d4_room_design`) was committed **~4 hours later**; the facelift review then endorsed the
  roster-centric IA ("the run roster is the central data surface rather than four peer boards",
  `docs/reviews/control_room_facelift_design.md:87`).
- Therefore: a deliberate, reviewed redesign — not an accident — whose **cost to the operator is real**:
  the boards' direct access disappeared, and the replacement's planned richness (the wireframe's lens
  inventory) was never fully delivered. The wireframe's `L-*` identifiers are not a literal requirement;
  what matters is what an operator can accomplish (section 3).

## 2. Subsequent restoration

`apps/control_room/static/parity.js` (phases u4/a2_rework) re-houses the dropped surfaces as a **Workbench
with 13 lenses** (Fleet, Attention, Money, Registry, Sessions, Queue, Routing, Docs, Audit, Health,
Workforce, Operations, Surfaces), each lazily loading the same endpoints the old room used, plus a
run-detail drawer backed by `GET /api/runs/<run_id>`. The old boards' *functions* largely exist again —
behind one affordance. The remaining question is discoverability, fidelity, and interaction, measured in
the browser.

## 3. Current deployed behavior — browser-verified capability table

Observed at 1440×900 on `4d834e9a9` (screenshots under `/tmp/unit5_j_*.png`; deploy = portal process).

| Operator task | Current entry point and read model | Observed result | Specific defect |
|---|---|---|---|
| Glance (J1) | Resting screen regions; `/api/glance` | usable; unknowns render as unknowns | — |
| Find a run outside the resting sample | Workbench → Operations → "Find a run (id, spec, state)" finder over `tr[data-run-id]` | usable — the finder filters rows (verified with `dc61`, `row_content`, exact id) | — |
| Open the found run's detail | Run row (role=button) → `#run-detail-drawer` → `/api/runs/<id>` | usable — state, cost, attempts, step timings | — |
| Phase / attempt / worker | Drawer attempts table; dock address band | attempts + phase shown; worker identity `unbound` (honest — not stamped) | — |
| Claim vs verification | Dock `SAID` / `MEASURED` (glance run_sample) | **failing** — `MEASURED: "test result unknown"` although the run's ledger records `test_executed_success: true / evaluator_independent: true` | ledger pointer `/repo/...` never resolved on the host → every ledger-derived field silently unknown |
| Elapsed time and cost with provenance | Dock `COST` (glance run_sample) | **failing** — `COST: unknown` although the control record carries `cost_usd = 0.027517` | cost hard-coded `unknown` in `_run_row` |
| Return without losing the found list | Escape with the drawer open | **failing** — Escape closed the whole workbench (`drawerHidden: false`, `workbenchHidden: true`), dismissing the list; the drawer's own Escape never fired (focus sat on the originating row, outside the drawer) | Escape precedence missing |

Not yet covered by observation (recorded as gaps, not conclusions): narrow/mobile pass on this journey,
keyboard-only traversal, Money/Health/Sessions/Registry panel fidelity, long-roster scrolling, and the
unloaded legacy board code (`shell.js`, `board-fleet.js` are no longer referenced by `index.html`).

## 4. First slice (Unit 5 recovery)

1. **Actions the operator cannot complete:** (a) after selecting a durable run, read its recorded cost and
   its independent verification verdict (both render `unknown` while the records hold them); (b) open a
   found run's detail from Operations and return to the found list without dismissing it.
2. **Observed failures:** revision `4d834e9a9`, 1440×900 — dock for `run-dc61bcb7d334`: `COST unknown`,
   `MEASURED test result unknown`; Escape after opening the drawer: workbench closed, drawer open, filter
   preserved but the list view dismissed.
3. **Intended user-visible behavior:** the selected-run detail reports the recorded spend with its
   provenance or an explicit *source unknown* (never `$0.00` for a missing measurement), and the
   independent verification verdict distinguishes the agent's narrative from verification; Escape in the
   drawer returns to the found list with focus on the originating row and the finder intact; a second
   Escape closes the workbench.
4. **Owners:** `apps/control_room/routes/glance.py` (ledger-path mapping `/repo/` → checkout, cost
   provenance, measured verdict wording) and `apps/control_room/static/parity.js` (Escape precedence,
   drawer focus). No new read model, no new status authority.
5. **Browser assertions:** before — `COST` contains `unknown`; `MEASURED` contains `test result unknown`;
   after drawer-open Escape the workbench is hidden. After — `COST` shows `$0.0275 · source unknown`;
   `MEASURED` shows `independent tests passed`; first Escape hides the drawer with the workbench open,
   focus on the originating row, finder value retained; second Escape hides the workbench.
6. **Preserved:** all glance/parity/static tests (57 passed, 3 added); honest `unknown`s for genuinely
   absent fields; `unbound` worker identity stays explicit; no public exposure changes; no unrelated churn.

Reference implementation and tests accompany this document on the delivery branch; the ordinary-pipeline
run that carries the slice records its own candidate, prepared prompt (with the pinned
`job_walkthroughs.md` J1/J4 excerpts), and independent verification.

## 5. Remaining product recovery (ordered by observed usefulness)

1. Run navigation/inspection incl. return behavior — this slice.
2. Sessions and available transcript/tool/evidence inspection; attention items that name a next action.
3. Spend and health views that explain measurement, freshness and unknowns.
4. Routing, queue, Operations/Surfaces, registry, documentation and audit gaps; narrow-viewport pass;
   decide the fate of the unloaded legacy board code (reuse or delete once replacement behavior is
   proven).
