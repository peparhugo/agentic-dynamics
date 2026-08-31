---
status: preregistered
---

# Δ-entropy response curve — pre-registration: the structural-disorder axis for the next calibration campaign

**Status: PREREGISTERED — committed BEFORE any cell of the next calibration campaign runs.**
**Design authority:** `docs/designs/proposed/neo4j_graph_analysis_design.md` §3 (Part B —
the solution/test split + the three-axis join + the four-quadrant contract) + the campaign
integration pin (§3.4: *"the perturbation strengths gain the structural-disorder response
axis — does stronger stress produce messier solutions, and does the mess correlate with the
review texture and the outcomes?"*).
**Instrument:** `scripts/measure_delta_entropy.py` (schema `delta_entropy/v1` — measured
2026-08-30, corpus: 235 story cells + 86 campaign cells; the split is live: ΔH_solution
(production only — the naming + `tests/`-dir rules) as the primary axis, ΔH_tests as the
recorded secondary).
**Measured baseline (this corpus, [M]):** quadrant distribution — messy_but_right 99,
messy_and_broken 21, clean_and_right 5, **clean_but_wrong 1** (the 2d/2e wall); test-join
complete 126 of 321 measured (the join is the quadrant's gate — incomplete = FAILED
finding, never a quadrant).

## 1. The axis

The next calibration grid (the E4/grit-style perturbation campaign — operators × strengths
× conditions on a fixed story) gains a recorded response axis: **ΔH_solution as a function
of the cell's perturbation strength**. The instrument measures the baseline (the seeded
codebase) and the final (the worktree HEAD) per cell — the cell's ΔH is the structural
disorder the agent's work introduced — joined with the two already-measured axes:
`changed_symbols_with_tests_ratio` (linkage, the seam's tests term) and
`test_executed_success` (outcome, the independent test runner).

## 2. The pre-registered hypotheses (falsifiable, measured not estimated)

- **H1 — the mess rises with the stress.** ΔH_solution is monotone non-decreasing in the
  perturbation strength: stronger stress → messier solutions. REFUTED if the highest
  strength's mean ΔH_solution is not greater than the baseline (clean) condition's by the
  instrument's measured threshold ([P] sign-of-delta, the design leaves the cut
  unspecified — the response is reported as the per-strength distribution, never a single
  fitted number).
- **H2 — the mess correlates with the review texture.** The messy_but_right cells'
  debt/hygiene review rates exceed the clean_and_right cells' on the same grid. REFUTED if
  the review-texture rates do not separate by quadrant at the grid's scale.
- **H3 — the wall is structure-invisible.** The clean_but_wrong incidence (the blind-spot
  quadrant — ΔH low AND tests fail) does NOT rise with the strength: it is the unseen-family
  defect class, invisible to structure and to the tests' passage at the cell level. REFUTED
  if clean_but_wrong's per-strength incidence rises monotonically — a strength-linked
  invisible defect would change the instrument's blind-spot story.

## 3. The measurement rule (the pins)

1. **The split is law:** every measured cell records BOTH ΔH axes — a cell with one axis
   missing is a FAILED finding, never a half-report.
2. **The quadrant contract:** no ΔH without the test-join (ratio + outcome). A report of
   ΔH_solution alone is a FAILED finding; the quadrant is the interpretation.
3. **Coverage exact:** baseline-missing worktrees are listed, never imputed.
4. **The response is a distribution:** per-strength ΔH_solution (and ΔH_tests) summaries —
   mean/median/IQR + n — not a regression line over a handful of cells.
5. **The wall is a count:** clean_but_wrong cells reported per strength bin, exactly.

## 4. The falsifiability contract

The campaign is judged on H1-H3 as written. A strength-response that contradicts H1 (the
mess does not rise) is a real REFUTE with the measured distribution as the evidence — not a
failed campaign. The instrument's guard stands: a cell whose join is incomplete records
`test_join_complete=false` and `quadrant=null` — the coverage table tells the reader what
the grid actually measured.

**LOG:** the axis pinned (ΔH_solution vs strength, joined with the linkage + outcome);
H1-H3 pre-registered with their refute conditions; the measurement rule (the split law, the
quadrant contract, exact coverage, distribution-not-fit, the wall as a count); the
falsifiability contract. **PREREGISTERED — the next calibration campaign consumes this
axis without amendment.**
