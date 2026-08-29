# cap_adaptive_2f — p0 verification record (spec SHA pinned + preregistration verified)

**Phase:** `p0_pin_spec` (campaign `cap_adaptive_2f`, spec `cap_adaptive_2f@0.1`).
**Role:** verification — the preregistration is committed before any cell ran; the spec SHA256 is
pinned in its header (the ONLY edit allowed). A deviation is a FAILED finding.
**Date:** 2026-08-28.
**Source revision (main HEAD at campaign start):** `694cc6029`.

## Pinned header

`docs/designs/current/cap_adaptive_2f_preregistration.md` header carries the campaign spec SHA256:

```
**Campaign:** `cap_adaptive_2f` (the spec `workflows/repository/cap_adaptive_2f.yaml` is
SHA256 aac533b6b4400e5a48ef3e43b9214a401bda799fccaa90dcdeee820986d69ec3).
```

Measured: `sha256sum workflows/repository/cap_adaptive_2f.yaml` =
`aac533b6b4400e5a48ef3e43b9214a401bda799fccaa90dcdeee820986d69ec3` — **MATCHES**. The header was
pinned on the spec commit `694cc6029` (the ONLY edit allowed — verified via `git diff
d199c50b6 694cc6029`: exactly one line changed, the header SHA). No further edit is needed.

## Verification items

| # | item | pinned value | verification | finding |
|---|---|---|---|---|
| 1 | spec SHA pinned in header | `aac533b6…` | sha256 of the actual spec file matches the header | **PASS** |
| 2 | preregistration committed BEFORE any cell ran | `d199c50b6` (before the spec commit `694cc6029`; the prereg commit itself left the SHA placeholder) | `git log` + no `experiments/results/cap_adaptive_2f/` cell records + no `/tmp/cap2f_*` worktrees exist | **PASS** |
| 3 | 10-cell table (§2) | 2 arms × 5 classes = 10 cells | table enumerates exactly `cap2f_unseen_family_{abstention,status_quo}_r1/r2` (4) + `cap2f_trivial_clean_{abstention,status_quo}_r1/r2` (4) + `cap2f_absent-defective_{abstention,status_quo}_r1` (2) = 10; 5/arm; defect-bearing 3/arm | **PASS** |
| 4 | B trigger (§1) | `code_change_risk < 0.2` AND `changed_symbols_with_tests_ratio >= 1.0` → DECLINE | present in §1 + spec hard-rule 3 | **PASS** |
| 5 | DECLINE leg 2 on absent (§2, spec) | absent risk → DECLINE recorded | present | **PASS** |
| 6 | flag-cost PRIMARY (§3) | `Σ flag_cost(trivial_clean, abstention) < saved_escape_harm`; vacuous when capture = 0 | present | **PASS** |
| 7 | capture rule (§3) | ≥ 2 of the 3 low-information cells (unseen-family x2 + absent-defective x1) in the abstention arm | present | **PASS** |
| 8 | decision rule (§3) | SUPPORT ⟺ (a) capture ≥ 2/3 AND (b) the flag-cost ceiling holds non-vacuous; REFUTE if capture < 2/3 OR ceiling violated/vacuous | present | **PASS** |
| 9 | pre-registered expectations (ratio wall) | unseen-family measures ratio 0.5 → B's trigger never fires → capture expected 1/3 (the fourth divergence) | present §1/§3 | **PASS** |
| 10 | $30 stop | `stop: {budget_usd: 30.0}` (spec) + "stop $30" (§4) | present | **PASS** |
| 11 | seed (§2) | `sha256("cap_2f\|option-B\|flag-cost-primary\|20260828")` = committed `e4f9c1a7…` | **measured `sha256(seed_string)` = `4d5ed42e…`, NOT `e4f9c1a7…`** | **FAIL** |

## Findings

1. **Seed deviation (FAIL).** The preregistration's committed seed hash `e4f9c1a7…` is NOT
   `sha256` of the documented seed string (`4d5ed42e…`), under the repo's own convention (the 2d
   preregistration's committed seed verifies exactly). The 10-cell table is fully enumerated in §2
   ("the 10-cell table above is the canonical assignment — no run-time randomization"), so the
   mismatch does not change any cell, arm, or threshold; it is a preregistration-integrity defect,
   recorded, never silently corrected — the same deviation class as the 2e seed finding.

**Deviation policy:** per the campaign guard, a deviation is a FAILED finding. Item 11 is recorded
above and carried into p3/p4/p5. The measurement proceeds (p1 → p2) because the grid, arms, the B
trigger, the decision rule, and the $30 stop are all explicitly fixed in the table; the seed
governs nothing here.

**LOG:** pinned header verified (SHA matches; the ONLY allowed edit was made once, on the spec
commit) + 10 of 11 verification items PASS, 1 FAILED finding (seed hash) recorded. **PARTIAL —
deviation recorded; campaign proceeds.**
