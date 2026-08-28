# cap_adaptive_2e — p0 verification record (spec SHA pinned + preregistration verified)

**Phase:** `p0_pin_spec` (campaign `cap_adaptive_2e`, spec `cap_adaptive_2e@0.1`).
**Role:** verification — the preregistration is committed before any cell ran; the spec SHA256 is
pinned in its header (the ONLY edit allowed). A deviation is a FAILED finding.
**Date:** 2026-08-28.

## Pinned header

`docs/designs/current/cap_adaptive_2e_preregistration.md` header carries the campaign spec SHA256:

```
**Campaign:** `cap_adaptive_2e` (`workflows/repository/cap_adaptive_2e.yaml` SHA256
`b0ad1c4fe65d364478db4c508e694b58a09c2377a8063efe514796a1d853e4ad`; `cap_adaptive_2e@0.1`).
```

Measured: `sha256sum workflows/repository/cap_adaptive_2e.yaml` =
`b0ad1c4fe65d364478db4c508e694b58a09c2377a8063efe514796a1d853e4ad` — **MATCHES**. The header is
already pinned (appended on the spec commit `3458f916d`, on main); no edit is needed.

## Verification items

| # | item | pinned value | verification | finding |
|---|---|---|---|---|
| 1 | spec SHA pinned in header | `b0ad1c4f…` | sha256 of the actual spec file matches the header | **PASS** |
| 2 | preregistration committed BEFORE any cell ran | `d1a0ad777` (on main, before the spec commit `3458f916d`) | `git log` + no `experiments/results/cap_adaptive_2e/` results exist | **PASS** |
| 3 | 6-cell table (§3) | unseen_family x2 per arm + absent-defective x1 per arm = 6 cells, 2+2+1+1 | table enumerates exactly `cap2e_unseen_family_abstention_r1/r2`, `cap2e_unseen_family_status_quo_r1/r2`, `cap2e_absent-defective_abstention_r1`, `cap2e_absent-defective_status_quo_r1` | **PASS** |
| 4 | seed (§3) | `sha256("cap_2e\|reconstruct-unseen-family\|fingerprint\|20260828")` = committed `0f3e7c1b…` | **measured `sha256(seed_string)` = `d8f9bb19…`, NOT `0f3e7c1b…`** | **FAIL** |
| 5 | fingerprint tolerance | 1e-9 (§4, §5) | present in the decision rule + guard | **PASS** |
| 6 | capture floor | ≥ 2/3 of the 3 low-information cells (§4) | present | **PASS** |
| 7 | $30 stop | `stop: {budget_usd: 30.0}` (spec) + "stop $30" (§5) | present | **PASS** |
| 8 | construction premise (§1) | "2c's unseen-family construction added `test_tally` → ratio 1.0 (2c per-cell facts)" | the recorded 2c per-cell facts measure **ratio 0.5** (changed_symbol_count 2, one symbol test-linked) — the §1 claim is contradicted by the 2c evidence it cites | **FAIL** |

## Findings

1. **Seed deviation (FAIL).** The preregistration's committed seed hash `0f3e7c1b…` is NOT
   `sha256` of the documented seed string (`d8f9bb19…`), under the repo's own convention (the 2d
   preregistration's committed seed verifies exactly). The grid is fully enumerated in the §3
   table ("no randomization beyond the seed's arm assignment" — the assignment is written out), so
   the mismatch does not change any cell, arm, or threshold; it is a preregistration-integrity
   defect, recorded, never silently corrected.
2. **Construction-premise deviation (FAIL).** §1 claims the 2c construction added `test_tally`
   and measured ratio 1.0; the recorded 2c facts measure ratio 0.5. This puts the §3 fingerprint
   construction in direct doubt before p1.
3. **Mechanistic pre-check (reported, not decided here).** Under the real TESTED_BY rule
   (`src/agentic_dynamics/core/language.py:811`), a new test-file function is a changed symbol but
   is never test-linked. The REQUIRED `test_tally` addition therefore forces
   `changed_symbol_count = 2` while only `tally` is test-linked → ratio 0.5 → multi-term risk.
   p1 measures this on the real stack.

**Deviation policy:** per the campaign guard, a deviation is a FAILED finding. Items 4 and 8 are
recorded as FAILED findings above and carried into p3/p4/p5. The measurement proceeds (p1 → p2)
because the grid, arms, tolerance, floor, and stop are all explicitly fixed in the table; the seed
governs nothing here.

**LOG:** pinned header verified (SHA matches) + 7 of 9 verification items PASS, 2 FAILED findings
(seed hash; §1 construction premise) recorded. **PARTIAL — deviations recorded; campaign proceeds.**
