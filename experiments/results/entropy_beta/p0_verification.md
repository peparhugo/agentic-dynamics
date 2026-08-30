# entropy_beta_instruments — p0 verification record (spec SHA pinned + mandates' pins verified)

**Phase:** `p0_pin_mandates` (spec `entropy_beta_instruments@0.1`).
**Role:** verification — the two designs (`docs/designs/proposed/neo4j_graph_analysis_design.md`
§3 + `docs/designs/proposed/beta_snowball_measurement_design.md` §2-3) are the mandates. Append
this spec's SHA256 to the Δ-entropy design's header (the ONLY edit allowed). Verify the mandates'
pins: the solution/test split, the three-axis join, the four-quadrant contract, the
coordination-tax formula, the 2b prior. A deviation is a FAILED finding.
**Date:** 2026-08-30.
**Source revision (branch HEAD at phase start):** `62f8e5db2`.

## Pinned header

`docs/designs/proposed/neo4j_graph_analysis_design.md` header now carries the spec SHA256:

```
**Spec:** `entropy_beta_instruments` (`workflows/repository/entropy_beta_instruments.yaml` SHA256
`eb20ac83051740873efec942f92761470546b811003648c651c23ea37458ace6`; `entropy_beta_instruments@0.1`).
```

Measured: `sha256sum workflows/repository/entropy_beta_instruments.yaml` =
`eb20ac83051740873efec942f92761470546b811003648c651c23ea37458ace6` — **MATCHES**. The header was
appended as the ONLY edit (verified via `git diff`: exactly one inserted `**Spec:**` line +
blank line; no other change to the design). No further edit is needed.

## Verification items

| # | item | pinned value | verification | finding |
|---|---|---|---|---|
| 1 | spec SHA pinned in Δ-entropy header | `eb20ac83…` | `sha256sum` of the actual spec file matches the header; the header append is the ONLY edit | **PASS** |
| 2 | the solution/test split (neo4j §3.1) | "two separate dimensions: ΔH_solution (production code only — test files excluded by naming + `tests/`-dir rules) + ΔH_tests (the test tree's own structural entropy)" | present in §3.1 pin 1 | **PASS** |
| 3 | the three-axis join (neo4j §3.2) | "ΔH_solution (structure) · `changed_symbols_with_tests_ratio` (linkage) · `test_executed_success` (outcome)" | present in §3.2 pin 2 | **PASS** |
| 4 | the four-quadrant contract (neo4j §3.3 + §6) | the high/low ΔH × pass/fail table; the 4th quadrant = "clean but wrong" (the 2d/2e wall, the blind-spot case); "the instrument never reports ΔH without the quadrant"; §6 "a report of ΔH without the test-join is a FAILED finding" | present in §3.3 pin 3 + §6 | **PASS** |
| 5 | the coordination-tax formula (beta §2) | "`coordination_overhead(campaign) = (wrapper + merge + chain + review time/cost) / (cell time/cost)`" — per campaign from the ledgers + merge records + chain runs + review rounds | present in §2 | **PASS** |
| 6 | the 2b prior (beta §1) | the wrapper-phase share "**63%** ($0.17 of $0.27 — phases, not cells)" | present in §1's measured-proxy table | **PASS** |

## Findings

1. **All six pins verify — no deviation.** Each mandate pin (§1-§6) is present in its design and
   consistent with the spec's hard rules: the split (hard rule 3), the four-quadrant contract
   (hard rule 2), the coordination-tax formula (hard rule 5), the measured-not-estimated guard
   (hard rule 4, mirroring beta §6's "measured, never blended").
2. **One clarifying nuance, not a deviation.** beta §2 writes the formula as
   "(wrapper + merge + chain + review **time/cost**) / (cell **time/cost**)", while spec hard
   rule 5 writes "(wrapper + merge + chain + review) / (cell)". The designs resolve this
   internally: beta §6 pins "measured, never blended — … the coordination tax cites the
   wrapper/merge/chain/review fields", so the wrapper/cell terms are the measured cost fields
   and the merge/chain/review terms are the event records (a different unit). The two mandate
   documents agree; no pin is contradicted.
3. **The blind-spot case is pinned.** neo4j §3.3 names the fourth quadrant (ΔH low, tests fail)
   as "clean but wrong — the invisible cell", the 2d/2e unseen-family wall; the spec's question
   and hard rule 2 carry the same case. Consistent.

**LOG:** pinned header verified (SHA matches; the ONLY allowed edit made once, on this phase) +
6 of 6 verification items PASS, 0 FAILED findings. **PASS.**
