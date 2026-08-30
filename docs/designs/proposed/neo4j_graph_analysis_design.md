---
status: proposed
---

# Neo4j graph analysis — beyond the retrieval bridge (the persistent code graph, the Δ-entropy instrument, the lineage walks)

**Status: PROPOSED (2026-08-29, operator-directed).** Slice 3 of the fleet ladder wires neo4j
for RETRIEVAL (the RRF lexical leg — the Knowledge nodes + the fulltext index + the lineage
edges). This design is the SECOND phase — what the graph carries beyond retrieval: the
**persistent code graph** (the dependency graph the change-analysis computes in-process today),
the **Δ-entropy instrument** (structural-disorder as a campaign measurement signal — with the
operator's question answered: how tests factor in), and the **lineage walks** (the graph
queries over the supersede/causes chains). The motivating case is the session's own wall: the
2d/2e campaigns' impacted-counter failures were graph-semantics problems a persistent,
inspectable graph would have diagnosed in one pass instead of three campaigns.

## 1. The motivating evidence (measured, this session)

| measured fact | value | artifact |
|---|---|---|
| the incorrect_rebuilt cells' `impacted_symbol_count` | **0** — despite the widgets-call-`add` dependant edges (the graph's neighborhood INCLUDED the widgets) | `cap_adaptive_2d/p1_incorrect_rebuilt_probe.json` + `p2_records_sha_index.json` |
| the same cells' `code_change_risk` | 0.475 (analyzers-down renormalization) vs 0.19 (analyzers-up) — the construction's risk flips with the analyzer state | the 2d probe + cell records |
| the unseen-family cells' ratio | **0.5, never 1.0** — the construction and the fingerprint mutually exclusive "under the real measurement rule" | the 2e verdict (`cap_adaptive_2d_e.md`) |
| campaigns consumed | **3** (2d, 2e, 2f) hitting the wall, plus the probe-only 2f captures | the verdict docs |

**The lesson:** the impact counter computes a BEHAVIORAL impact (a behavior-preserving change has
zero behavioral impact on its callers), while the constructions assumed STRUCTURAL reach (the
callers' edges). The computation happens in-process on a per-change AST graph that is
**discarded after each cell** — nothing inspects it after the fact, so the divergence was
undiagnosable. A **persistent, queryable code graph** makes the semantics inspectable: the
edges exist, the counter's definition is checkable, the construction's assumptions are
verifiable BEFORE a campaign runs (the p1-pre-verification the 2e lesson demanded).

## 2. Part A — the persistent code graph

**The mechanism:** the KB already produces code records (one per function/class —
`code_ingestion.py`'s `derive_code_records`, authority SOURCE, evidence [C]) and the wiring
exists (`ingest_codebase_graph` → `graph.load_codebase_graph`). The ladder's slice 3 adds the
neo4j nodes/edges; Part A adds the **graph-first change-analysis**:

- The change-analysis seam (`code_change_facts.py`) queries the PERSISTENT graph for the
  impacted computation instead of the in-process AST walk — with the semantics made explicit:
  the design pins the **impacted definition** (behavioral vs structural, the 2e lesson) as a
  declared choice, queryable, auditable.
- **Cross-commit evolution:** each story session's commits produce graph snapshots — the
  structural delta per commit (added/removed symbols, coupling drift, new hub nodes) — the
  stories' 5-session arcs become graph trajectories.
- **The campaign-time value:** the p1 pre-verification (the 2e lesson) becomes a graph query —
  "does this construction's changed symbol have structural dependants?" — asked BEFORE the
  grid runs, with the answer visible.

## 3. Part B — the Δ-entropy instrument (with the tests-factoring pinned)

**The measurement:** `ΔH(cell) = entropy(solution_final) − entropy(solution_baseline)` — the
structural disorder the agent's work introduced, as a per-cell measurement signal.

**How tests factor in (the operator's question — the pins):**

1. **The solution/test split (the confound fix).** Today `compute_entropy` walks the WHOLE tree
   (the skip list is only `__pycache__`/`node_modules`/`.git`/`dist`/`build`/`venv`/
   `.pytest_cache` — test files and `tests/` dirs are silently INCLUDED). A solution's entropy
   is mixed with its test suite's structure. The instrument measures **two separate
   dimensions**: `ΔH_solution` (production code only — test files excluded by naming +
   `tests/`-dir rules) as the primary axis, and `ΔH_tests` (the test tree's own structural
   entropy) as a recorded secondary dimension — the tests' structure is an agent work-product
   signal feeding the hygiene findings' texture (F4).
2. **The three-axis join.** Δ-entropy is only interpretable joined with the already-measured
   axes: `ΔH_solution` (structure) · `changed_symbols_with_tests_ratio` (linkage, the seam's
   tests term) · `test_executed_success` (outcome, the independent test runner).
3. **The four-quadrant interpretation (the measurement's decision table):**

   | | tests pass | tests fail |
   |---|---|---|
   | **ΔH high** | messy but right (the hygiene texture — flash's F4 profile) | messy and broken |
   | **ΔH low** | clean and right | **clean but wrong — the invisible cell** |

   The fourth quadrant is the 2d/2e unseen-family wall: structurally clean, semantically wrong,
   with the countable facts reading "clean". **The tests are the entropy's blind-spot
   corrector** — ΔH measures the mess; the tests measure the meaning. The instrument never
   reports ΔH without the quadrant.
4. **The campaign integration.** The perturbation strengths (the E4/grit grids) gain the
   structural-disorder response axis: does stronger stress produce messier solutions, and does
   the mess correlate with the review texture (the debt/hygiene rates) and the outcomes? A new
   preregistered axis for the next calibration campaign — the ΔH response curve.

## 4. Part C — the lineage walks

The Knowledge nodes' edges (SUPERSEDES / CLEARED_BY / REPLACED_BY / CAUSES) become graph
queries: the supersede chains (today a jsonl scan in `scripts/registry.py`), the
observation→actuation causality paths (the actuation design's lineage gate), the
cell→campaign provenance walks. Read-only, served alongside the registry's existing
show/query/lineage.

## 5. The sequencing

1. **Slice 3 (the ladder)** lands the retrieval bridge — the machine needs the RRF leg live
   first (the proposal §6, in the implementation workflow).
2. **3.5a — the graph-first change-analysis** (Part A): the impacted computation against the
   persistent graph with the pinned semantics; the 2e construction becomes the verification
   fixture (the graph query reproduces the 2e wall's facts, then the construction's
   assumptions are checked pre-run).
3. **3.5b — the Δ-entropy instrument** (Part B): the solution/test split + the three-axis join
   + the four-quadrant reporting; a preregistration pins the ΔH response-curve axis for the
   next calibration campaign.
4. **3.5c — the lineage walks** (Part C): read-only graph queries over the existing edges.
5. Each part bounded (the flash-sized-phase rule), each with the tests + the rollback (the
   graph is additive; the seam falls back to the in-process walk on any graph failure).

## 6. Guard

Every measurement pin is cited (the entropy implementation's skip list + the five dimensions,
the impact counter's semantics from the 2d/2e score JSONs, the test-ratio + outcome fields from
the seam and the test runner). The Δ-entropy's quadrant table is the interpretation contract —
a report of ΔH without the test-join is a FAILED finding. The 2e lesson is recorded as the
motivating fixture: the graph query must reproduce the wall's facts (impacted 0 despite the
structural edges) — the semantics' inspectability is the design's own verification.

**LOG:** the session's wall restated as the motivation (the impacted counter's behavioral-vs-
structural semantics, undiagnosable because the per-change graph is discarded); Part A (the
persistent code graph, the graph-first change-analysis, the cross-commit evolution, the
campaign-time pre-verification); Part B (the Δ-entropy instrument with the operator's question
pinned: the solution/test split, the three-axis join, the four-quadrant table with the
clean-but-wrong wall as the blind-spot case, the campaign integration); Part C (the lineage
walks); the sequencing (slice 3 first, then the three parts, each bounded with a rollback); the
guard (citations, the quadrant contract, the 2e fixture). **PROPOSED — the implementation
follows the ladder's slice 3, then the operator's sign-off.**
