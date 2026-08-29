---
status: accepted
---

# cap_adaptive_2f — known-safe review

**Role:** known-safe verifier — confirm the campaign did what it claims and nothing it must not.
Campaign `cap_adaptive_2f` (`cap_adaptive_2f@0.1`, spec SHA256
`aac533b6b4400e5a48ef3e43b9214a401bda799fccaa90dcdeee820986d69ec3`).
**Verdict under review:** REFUTE (capture 1/3 < 2/3 — the ratio wall; flag-cost ceiling vacuous;
flag-cost magnitude $0.000634 measured). **Score:** `cap_adaptive_2f_score_20260828T210239Z.json`
(SHA256 `fa6bc16b5c32773c…`).

## Known-safe items

| # | claim | verification | finding |
|---|---|---|---|
| K1 | preregistration committed BEFORE any cell ran | `d199c50b6` (prereg) precedes the spec commit `694cc6029`; no `cap_adaptive_2f` cell records existed at p0; the spec SHA was appended to the prereg header on the spec commit (the ONLY edit) | **SAFE** |
| K2 | spec SHA pinned in the prereg header matches the spec file | `sha256sum workflows/repository/cap_adaptive_2f.yaml` = `aac533b6…` = the header | **SAFE** |
| K3 | 10-cell grid ran exactly per the §2 table | p2 manifest + per-cell records: 10 cells, 0 invalid joins, 0 unlisted cells | **SAFE** |
| K4 | status_quo applied exactly; abstention shadow-only | status_quo worktrees show continue = null (no extra apply commits); the treatment code diff is empty | **SAFE** |
| K5 | B trigger applied exactly (risk < 0.2 AND ratio >= 1.0; leg 2 on absent), no post-hoc widening | per-cell `abstention_decision` re-computed from recorded facts in the adversary F5/F6 | **SAFE** |
| K6 | outcomes independent (pytest + post-hoc evaluator) | outcome fields per class are internally consistent and consistent with the recorded defects | **SAFE** |
| K7 | no generated-surface edits, no secrets, no external actuation | `.opencode/`/`.claude/` untouched; secrets scan clean; the abstention rule stayed shadow-only (no activation) | **SAFE** |
| K8 | budget within the $30 stop | 10 cells total $0.085758 ≈ 0.3% of the $30 stop | **SAFE** |
| K9 | verdict numbers trace to the score JSON + validation artifact | every verdict number is traced in `cap_adaptive_2f_validation_20260828T210239Z.json` to an immutable record field or a pre-registered constant | **SAFE** |
| K10 | the data chain stays single-writer; the parallel-vehicles rule holds | cell worktrees are disposable (`/tmp/cap2f_*`); the deepseek envelope is the campaign's; no anthropic-envelope cells ran | **SAFE** |

## Non-issues (reviewed, no action)

- **The seed mismatch (`e4f9c1a7…` vs measured `4d5ed42e…`)** is a preregistration-integrity
  FAILED finding (reported in the adversary F13 + p0/p4), not a data-integrity issue: the grid is
  fully enumerated and no cell depends on the seed.
- **The vacuous flag-cost ceiling** is the pre-registered expectation, reported, never re-scoped.

## Conclusion

The campaign is known-safe on every checked dimension: it did what the preregistration fixed, the
arms behaved exactly, the trigger was applied without widening, outcomes were independent, and the
verdict REFUTE is traceable to immutable records. The one preregistration FAILED finding (seed) is
recorded and does not change the verdict.

**LOG:** 10/10 known-safe items PASS. **PASS.**
