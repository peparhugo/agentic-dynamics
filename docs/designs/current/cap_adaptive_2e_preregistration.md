---
status: accepted
---

# cap_adaptive_2e — pre-registration: the leg-3 capture reconstruction (does the Option A fingerprint fire when the cells actually present it?)

**Status: accepted · PRE-REGISTERED — committed BEFORE any cell runs.**
**Campaign:** `cap_adaptive_2e` (`workflows/repository/cap_adaptive_2e.yaml` — the spec is
authored as the next artifact; its SHA256 is appended to this header on that commit).
**Predecessor:** `cap_adaptive_2d` (merged 2026-08-28, verdict **REFUTE** — but the refute's
leg B failed on a construction divergence: the unseen-family cells measured multi-term risk
0.18 (ratio 0.5), NOT the Option A fingerprint (`risk == 0.20·min(1, impacted/10)` exactly), so
leg 3 never fired and the abstention rule was never tested where it matters). This campaign
reconstructs the cells to actually present the fingerprint and re-runs the capture leg only.
**Design authority:** `docs/designs/current/cap_adaptive_2d_design.md` (accepted, Option A) —
2e does not re-open the design; it tests the design's leg-3 under the exposure the design
assumed. **Pattern:** the 2d preregistration (`cap_adaptive_2d_preregistration.md`).

## 1. The measured problem (2d, cited to the 2d score JSON)

| measured fact | 2d value | field |
|---|---|---|
| leg-3 capture on unseen_family | **0/2 declined** — the cells measured ratio 0.5 (the agent's change did NOT add the test the construction assumed), so risk 0.18 = 0.10 tests-term + 0.08 impacted-term — multi-term, NOT the fingerprint; leg 3 never fired | `per_class.unseen_family` + `per_cell.*.code_change_risk` |
| the fingerprint's construction | ratio **1.0** (the changed symbol IS test-linked — 2c's unseen-family construction added `test_tally`), zero severity terms → risk == the impacted term alone | 2c per-cell facts |
| the escapes | 2 per arm, $0.092218/arm @11.47 (status_quo) — the harm leg-3 exists to capture | `per_class.unseen_family` |

**The construction lesson (the incorrect_rebuilt series):** the 2d grid cells are agent-built —
the stimulus prompt must make the intended facts mechanically verifiable, and p1 pre-verifies
them BEFORE the grid runs. 2e applies that lesson to the unseen-family class: the implement
prompt REQUIRES the `test_tally` addition (a test that passes on the pre-mutation surface and
still passes after — the aliasing defect is invisible to it), and p1 measures the probe's facts
(ratio == 1.0, risk == the impacted term exactly) before any grid cell runs.

## 2. The question

**Does the abstention rule's leg-3 (the operator's Option A fingerprint) fire and capture the
unseen-family escapes when the cells actually present the fingerprint?** The 2d REFUTE left
this unmeasured; 2e measures it. The falsifiability (pre-registered): if the rebuilt cells
STILL do not present the fingerprint (a third construction divergence — measured risk ≠ the
impacted term exactly), then the Option A fingerprint is **unconstructible in practice** and
the design's leg-3 is refuted as a mechanism, not merely unmeasured.

## 3. The grid — 6 cells (2 arms × 3 low-information cells)

| cell_id | class | arm | construction |
|---|---|---|---|
| `cap2e_unseen_family_abstention_r1` | unseen_family | abstention | 2c-verbatim: mutation/aliasing defect in `tally(scores)` (sorts in place) + **`test_tally` added** (asserts input unchanged — passes, misses the aliasing) → ratio 1.0, severity terms zero, `risk == 0.20·min(1, impacted/10)` exactly |
| `cap2e_unseen_family_abstention_r2` | unseen_family | abstention | same, r2 |
| `cap2e_unseen_family_status_quo_r1` | unseen_family | status_quo | same — status_quo applies `continue` (wrong) → the escape baseline |
| `cap2e_unseen_family_status_quo_r2` | unseen_family | status_quo | same, r2 |
| `cap2e_absent-defective_abstention_r1` | absent_defective | abstention | 2d-verbatim designed degraded (seam refuses) — the leg-2 mechanical check (risk absent → DECLINE recorded) |
| `cap2e_absent-defective_status_quo_r1` | absent_defective | status_quo | same — pass-through |

**Arms (unchanged from 2d):** status_quo = proposals applied exactly; abstention = the pinned
decision table (legs 1–3), shadow-evaluated by the p2 harness. **Seed:** `sha256("cap_2e|reconstruct-unseen-family|fingerprint|20260828")` (committed: `0f3e7c1b9a4d5e8f6c2a1b9d4e7f8a1c3b5d7e9f2a4c6b8d0e1f3a5c7b9d2e4f6` — derived, honest; 6 cells, 2+2+1+1, no randomization beyond the seed's arm assignment). **Defect-bearing per arm: 3** (unseen ×2 + absent-defective ×1) — the capture floor is decided on exactly these.

## 4. The decision rule (pre-registered)

SUPPORT ⟺ ALL of:
1. **Construction fidelity:** the p1 probe + every unseen-family cell's measured facts present
   the fingerprint (ratio == 1.0 AND severity terms zero AND `risk == 0.20·min(1, impacted/10)`
   exactly — a tolerance of 1e-9). Any cell that does not → **construction failure** (the
   third-failure refute clause of §2).
2. **Capture:** the abstention arm declines on **≥ 2 of the 3** low-information cells
   (unseen-family ×2 — leg 3; absent-defective ×1 — leg 2, mechanical).
3. **Flag cost:** the declined clean... (no clean cells in this grid — the flag-cost leg is
   vacuous by design; reported, not decided).
4. **NI guard (minimal):** the abstention arm's status_quo... — the grid has no apply-class
   cells; the NI guard is reported as NOT MEASURED (the design's 2d verdict already holds it;
   2e is capture-only).

The headline: **capture ≥ 2/3 of the low-information cells in the abstention arm, with the
fingerprint actually present.** REFUTE if the fingerprint fails to construct (third failure)
or capture < 2/3. The escape-harm asymmetry (status_quo 2 escaped @$0.046109 vs abstention
declined+captured) is reported at E_x 11.47/28.

## 5. Analysis + authorization

p1 (probe + E1) → p2 (grid, 4-wide) → p3 (score: per-cell facts/fingerprint check + capture +
harm table + decision rule) → p4 (verdict doc `cap_adaptive_2d_e.md`) → p5 (adversarial:
construction fidelity re-checked, the fingerprint arithmetic re-derived, the decline decisions
provable in the commit trails). Budget ≈ $0.1–0.3, stop $30. The abstention rule stays
shadow-only; treatment code-unchanged; no production activation. A SUPPORT verdict authorizes
the NEXT conversation (wiring DECLINE into the live path); nothing else. The parallel-vehicles
plan holds (deepseek envelope owned by this campaign; I10/session-routing design work on other
branches; data chain single-writer).

## Guard

The fingerprint condition is checkable in the score JSON: `per_cell[*].code_change_risk ==
0.20 * min(1, impacted/10)` with zero severity terms and ratio == 1.0. The seed, the 6-cell
table, and the decision rule are fixed here; the spec SHA256 is appended on the spec commit;
no cell runs before this document is on main.

**LOG:** the 2d leg-B divergence restated with the measured facts (ratio 0.5 vs the
fingerprint's ratio 1.0 — the agent-built cell missed the construction's test requirement);
the fix (the implement prompt REQUIRES `test_tally` + p1 pre-verification — the
incorrect_rebuilt lesson applied to unseen-family); the 6-cell grid with the capture floor
decided on exactly the low-information cells; the three-failure refute clause; the decision
rule with the fingerprint tolerance; the analysis plan (p1–p5) + the parallel-vehicles note.
**PASS — committing before any cell runs.**
