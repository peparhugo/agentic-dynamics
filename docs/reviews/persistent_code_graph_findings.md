---
status: accepted
---

# persistent_code_graph_findings — the 2e wall made inspectable, and the graph-first change-analysis that closes it

**Findings for the `persistent_code_graph` spec** (`workflows/repository/persistent_code_graph.yaml`,
SHA256 `3b7984bc7ff6587d423592562056c48b6538c85bdffc06d2716d2d45886cebe7`,
`persistent_code_graph@0.1`). Written from p0–p4's committed outputs — no re-computation. The
mandate design is `docs/designs/proposed/neo4j_graph_analysis_design.md` §2 (the persistent code
graph + the graph-first change-analysis). Every figure below cites a field in the phase records
under `experiments/results/graph_family/` (`p1_build_graph.json`, `wall_reproduction.json`,
`pre_verification.json`, `seam_wiring.json`) or the wall's own artifacts
(`experiments/results/cap_adaptive_2d/p1_incorrect_rebuilt_probe.json`).

## 1. The question

The 2d/2e campaigns hit a wall: the `incorrect_rebuilt` cells' `impacted_symbol_count` read **0**
despite the structural dependant edges existing — the widgets-call-`add` graph edges were present
in the neighborhood, the counter still read 0. The cause was undiagnosable at the time because the
per-change AST graph is **discarded after each cell** — nothing could inspect the edges against the
counter's definition after the fact. This spec asked: **does a persistent, queryable code graph make
the wall's semantics inspectable — the behavioral-vs-structural impacted definitions checkable
BEFORE a campaign runs?** The answer, from the four phases, is **yes**, with the honest bounds
stated in §6.

## 2. Methodology — the four phases

### 2.1 The graph build (p1) — the corpus into the live neo4j

`scripts/graph_family_build.py` loaded three sources into `bolt://localhost:7687`
(`FINOPS_NEO4J_URI`) using the existing wiring (`code_ingestion.ingest_codebase_graph` →
`graph.load_codebase_graph` for the module layer, `graph.populate_versioned_graph` for the symbol
layer), all additive (`MERGE` + the two-ID contract — nothing deleted):

| source | loaded as | `[M]` counts |
|---|---|---|
| the framework's own `src/agentic_dynamics` | `:CodeModule` + `IMPORTS`/`IMPORTED_BY` under `framework-src` | 108 modules, 125 imports |
| the 2d/2e fixture cells (12 codebases — the four `incorrect_rebuilt` cells, the probe, the 2e cells) | `:CodeModule` + `:ModuleVersion`/`:SymbolVersion`/`:Revision` with `CALLS`/`SUPERSEDES` | 3 modules / 23 symbol versions per cell |
| one story's 5-session arc (`/tmp/story_c55b0cf5d2e9`, `notification_service` clean, deepseek-v4-pro) | per-commit `CodeSnapshot` → 6 `:Revision` snapshots with `SUPERSEDES` chains + per-commit `CodeDelta` | 402 symbol versions, 413 supersedes, 368 calls |

Post-build live graph (`p1_build_graph.json` → `graph_counts`): 244 `:CodeModule`, 4,098
`:ModuleVersion`, 32,001 `:SymbolVersion`, 281 `:Revision`, 33,961 `:Knowledge` nodes; 565 `IMPORTS`
/ 214 `IMPORTED_BY` / 272 `TOUCHED` / 5,394 `CALLS` / 36,099 `CONTAINS` / 32,001 `DEFINES` / 3,958
`SUPERSEDES` / 9,685 `TESTED_BY` edges. The `SymbolVersion` and `SUPERSEDES` bulk is the earlier
corpus ingestion the ladder's slice 3 already carried; this build added the module layer for the
framework and the symbol layer for the 12 fixture codebases + the one story arc.

**The wall's edges, made persistent.** For every `incorrect_rebuilt` cell the graph holds the
`widgets→add` inbound `CALLS` dependants: `add` carries **20 structural dependants** (`test_add` +
`widget_1..widget_19`) — `p1_build_graph.json` → `wall_edges.cells_with_edges`.

### 2.2 The wall reproduction (p2) — the query that shows both facts

`scripts/graph_family_wall.py` re-ran the analyzer's exact expansion against the persistent graph.
The recorded wall facts (`wall_reproduction.json` → `wall_facts_recorded`, sourced from the probe +
cell records): `impacted_symbol_count = 0`, `changed_symbol_count = 20`,
`changed_symbols_with_tests_ratio = 0.05`. The live trace (`analyzer_trace`) reproduces the
divergence mechanically at two deadlines:

| deadline | expansion nodes | impacted count | non-seed dependants |
|---|---|---|---|
| **300 ms** (the recorded deadline) | 20 (the seeds only) | **0** | — |
| **10 s** (the probe's verification) | 26 | **3** | `subtract`, `test_add`, `test_subtract` |

### 2.3 The pre-verification (p3) — the campaign-time query

`scripts/graph_family_preverify.py` asked the pinned question — **"does this construction's changed
symbol have structural dependants?"** — against the persistent graph for 15 cells across the 2d/2e
families, plus a leaf control and a mid reference, with the per-symbol dependant set recorded
(`pre_verification.json`).

### 2.4 The seam wiring (p4) — the graph-first change-analysis with the rollback

The seam is the runtime-owned `ChangeAnalyzer` protocol's concrete implementation
(`control.evidence_analyzer.EvidenceChangeAnalyzer`), with the impacted computation made
graph-first and the semantics declared. Details in §5.

## 3. The wall diagnosed — the behavioral counter vs the structural edges

**The 2e lesson, restated as a graph fact.** The impact counter computes a **BEHAVIORAL** impact —
a behavior-preserving change has zero behavioral impact on its callers — while the construction
assumed **STRUCTURAL** reach (the callers' edges). This is now a checkable graph fact, not a buried
root-cause: the structural edges EXIST in the persistent graph **and** the counter read 0, side by
side in one artifact (`wall_reproduction.json` → `verdict`: `edges_exist = true`,
`counter_recorded_0 = true`).

**The mechanism, now inspectable.** Two cited lines explain the 0 (`counter_definition.mechanism`,
`evidence_analyzer.py:225-247`):

1. **Seeds exclusion.** The changed symbols are the *seeds* of the impact expansion, and the seeds
   themselves are excluded from the impacted set. The 19 `widget_*` symbols are *added* symbols (the
   probe's seeds), so even though they call `add`, they cannot count as "impacted".
2. **Deadline truncation.** The 20-seed BFS runs under a hard `timeout_ms=300`, which truncates
   before it reaches the only non-seed dependants (`subtract`, `test_add`, `test_subtract`).

The live trace makes the divergence concrete: at 300 ms the expansion holds only the 20 seeds →
impacted 0; at 10 s the same expansion reaches 26 nodes → impacted 3 with the probe's exact
dependant set (`analyzer_trace.generous_10s`). **The wall's 0 is the deadline + seeds-exclusion, not
a missing edge.** The p2 record notes the residual caveat honestly: the 0 is the *recorded* fact,
reproduced live on a warm graph today — but a faster machine could complete the 20-seed expansion
inside 300 ms and read 3, which is precisely the nondeterminism the wall exposed (the deadline is
the bug, not the graph).

## 4. The pre-verification's answer — what would have been caught BEFORE the grid

Fifteen constructions were queried (`pre_verification.json` → `cells`), with per-symbol dependant
sets recorded. The verdicts (`verdict`):

| construction (class) | changed hub symbol | structural dependants | pre-run verdict |
|---|---|---|---|
| `incorrect_rebuilt` (4 cells) | `add` | **20** (`test_add` + `widget_1..19`) | **VERIFY — caught before the grid** |
| `correct` / `competing` / `harmful_partial` | `classify` | 0 | clean — no structural blast radius |
| `irrelevant` | `product` | 1 (`test_product`) | test-only signal |
| `absent` (absent-clean) | `widget` | 0 | clean |
| `absent` (absent-defective, 3 cells) | `wrong_op` | 0 | clean |
| `unseen_family` (3 cells) | `tally` | 1 (`test_tally`) | **WEAK** — structural tripwire, not a semantic oracle |
| leaf control | `widget_1` | 0 | negative case returned cleanly |
| mid reference | `subtract` | 1 (`test_subtract`) | the mid case |

**The headline: the wall would have been caught.** The construction that hit the 2d/2e wall —
changing `add` in a codebase where 20 widgets call it — returns VERIFY *before any grid runs*, which
is the 2e lesson operationalized as a graph query.

**The honest bound.** The `unseen_family` construction (the input-mutation defect) changes `tally`,
which carries only one *test-only* dependant — the structural signal is weak, and its defect is
behavioral, invisible to the structural question. The pre-verification is a **structural tripwire,
not a semantic oracle**: it discriminates blast-radius (20 vs 1 vs 0) but cannot see a
behavior-preserving-or-mutating defect that leaves the structure intact.

## 5. The seam's posture — the rollback and the additive guarantee

The seam (`seam_wiring.json` → `the_change`) is **graph-first with the in-process AST walk as the
default posture and fallback**:

1. **The in-process walk is the default.** `_in_process_impacted` — a pure, deterministic, no-I/O
   function over the typed `CodeSnapshot` — always computes the impacted set. The seam always has an
   answer; **the graph never gates a run**.
2. **A healthy graph upgrades the answer.** When the graph leg succeeds, the ACL-scoped
   `expand_candidates` expansion (the same `IMPACT_EXPANSION_RELS` traversal) is preferred when its
   result is at least as rich as the in-process walk's.
3. **Any graph failure rolls back.** Down (populate/expand raises or stalls — the hard client-side
   deadline still holds), **or empty/truncated** (the graph returns fewer dependants than the AST can
   see — the 2d/2e wall's exact signature): the seam keeps the in-process walk's answer and records
   the provenance.

**The semantics are DECLARED, never implicit.** `code_change_facts.py` carries `IMPACTED_SEMANTICS`
— the pinned definition: *structural* (the number of non-seed structural dependants over the `CALLS`
edges, bounded 1–2 hops, ACL-scoped), contrasted against *behavioral* (a behavior-preserving change
has zero behavioral impact on its callers even though the structural edges exist — the 2d/2e wall).
The declaration rides on every emission: `ChangeAnalysis.impacted_semantics` +
`impacted_source` (`"graph"` | `"in_process_walk"`) on the ledger record, the `impacted_symbols`
evidence payload (`{"count", "semantics", "source"}`), and the EVIDENCE context the next phase
receives.

**The wall's fix, reproduced at the seam.** The wall-style fixture (a behavior-preserving change to
`add` + the added widgets calling it): the graph query comes back empty (returns only the seeds —
the wall's truncation signature), so the seam **rolls back to the in-process walk and reports
impacted=1** (`test_add` — the non-seed dependant the 300 ms BFS missed). The wall's wrong 0 is NOT
reproduced by the seam; the semantics' inspectability is.

**The controlled graph-unavailable check.** A graph whose `populate` raises, a graph whose `expand`
raises, and a **stalled graph** (60 s sleep under a 1 s deadline) all return within the deadline with
`graph_status = "unavailable"`, the in-process walk's impacted computation, and declared provenance
— the seam falls back, never blocks (`seam_wiring.json` → `the_wall_fix.controlled_check`).

**Test outcome.** `tests/test_change_analyzer.py` (16), `tests/test_code_change_facts.py` (with the
guards), `tests/test_workflow_runner.py` (82), `test_cap_2a_spec.py` + `test_graph.py` +
`test_dependency_direction.py` (42), `test_run_workflow_graph_cli.py` (15), and
`test_script_classification.py` + `test_cli_resolution.py` (76) all pass. The full suite reads 2367
passed / 6 failed / 9 skipped; the six failures are **pre-existing derived-surface drift** (stale
parquet, README spec count, stale lab contracts, stale `data.js`) — none touch the seam's modules.

## 6. Honest limits

- **Coverage is the wall cells + one story arc, not the whole corpus.** The graph landed the
  framework's `src/` (module layer only — the symbol layer for a ~4k-symbol framework was out of
  scope for this bounded build), the 12 2d/2e fixture codebases (module + symbol layer), and one
  story's 5-session arc (`notification_service`, clean). The full 28-cell 2d grid, the other two
  stories, and the perturbation-condition arcs are **not** in the graph.
- **Snapshot depth is one clean arc.** The cross-commit evolution shape is demonstrated on a single
  clean run (seed → S1 greenfield → S2 feature → S3 integration → S4 refactor → S5 cross-cutting):
  6 revisions, 402 symbol versions, 413 supersedes, 368 call edges, coupling drift 16 → 117 `CALLS`
  edges, and a new hub (`_recv_json`, in-degree 16 → 59). The perturbed/degraded arcs are left to
  later phases. The framework src is module-layer only, so no symbol-level `SUPERSEDES` chain exists
  for the framework's own code.
- **The pre-verification is structural, not semantic.** It returns VERIFY on blast radius (20
  dependants) but a WEAK signal on the `unseen_family` mutation defect (1 test-only dependant). A
  behavior-preserving-or-mutating defect that leaves the call graph intact is invisible to it — the
  structural question is a tripwire, not an oracle, and the verdicts say so explicitly.
- **The wall's 0 is the recorded fact; the live 300 ms trace reproduces it, not proves it.** A faster
  machine could beat the 300 ms deadline and read 3 — the deadline is the bug, and the reproduction
  makes the nondeterminism visible rather than hiding it.
- **The seam is opt-in.** The default remains the no-op analyzer; the graph-first path activates only
  when a `graph_client` is injected at the composition root. The in-process walk resolves called
  names to qualified names best-effort (matching the graph's `CALLS` extraction) — it is the bounded
  rollback, not a second graph.
- **The 300 ms deadline is a policy choice, now exposed.** The `IMPACTED_SEMANTICS` declaration pins
  the structural definition and names the behavioral contrast, but the specific `timeout_ms=300` that
  produced the wall is a parameter in `evidence_analyzer.py`, not a law — the query makes it
  auditable, and the seam's rollback makes it non-fatal.

## 7. What this means for the campaign loop

The three campaigns (2d, 2e, 2f) that hit the wall each carried the same undiagnosable defect — a
per-change AST graph discarded after the cell. With the persistent graph, the cost of that failure
mode drops in two independent ways: the **pre-verification** surfaces the blast radius *before* a
grid runs (VERIFY on `add` → 20), and the **seam's rollback** makes the runtime answer robust to the
graph's own truncation (impacted=1 via the in-process walk instead of the wall's 0). Neither is a
gate: the graph is additive, and the in-process walk is the default posture. This is the design §2
mandate delivered — the semantics inspectable, the pre-verification a query, the rollback the default
— with the coverage and snapshot-depth bounds that remain.

**LOG:** findings written from p0–p4's committed outputs (no re-computation); the methodology (the
graph build, the wall reproduction, the pre-verification, the seam + the rollback); the wall
diagnosed (the behavioral counter vs the structural edges side-by-side, the 2e lesson restated as a
graph fact — edges EXIST + counter read 0, mechanism cited to `evidence_analyzer.py:225-247`); the
pre-verification's answer (the `incorrect_rebuilt` construction caught BEFORE the grid at 20
dependants, `unseen_family` a weak structural tripwire, the leaf control a clean negative); the
seam's posture (the rollback, the additive guarantee, the declared semantics, the controlled
graph-unavailable check); the honest limits (coverage = framework src module-layer + 12 fixture
codebases + one clean story arc; snapshot depth = one 6-revision arc). Every figure cited to the
phase records. **PASS.**
