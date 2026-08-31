# persistent_code_graph — p4 seam wiring (the graph-first change-analysis, additive + rollback)

**Phase:** `p4_seam_wiring` (spec `persistent_code_graph@0.1`).
**Role:** wire the graph-first change-analysis seam — BOUNDED to the implementation. Modify
`code_change_facts.py` (or its seam) so the impacted computation queries the PERSISTENT graph
instead of the in-process AST walk — with the semantics DECLARED (behavioral vs structural, the
2e lesson) and the ROLLBACK: any graph failure (down / empty / timeout) falls back to the
in-process walk. ADDITIVE ONLY — the graph never gates a run. Machine-readable twin:
`experiments/results/graph_family/seam_wiring.json`.
**Date:** 2026-08-31.

## The seam's change

The seam is the runtime-owned `ChangeAnalyzer` protocol's concrete implementation
(`control.evidence_analyzer.EvidenceChangeAnalyzer`, injected at the composition root). Its
impacted computation is now **graph-first with the in-process rollback as the default posture**:

1. **The in-process AST walk is the default.** `_in_process_impacted` (a pure, deterministic,
   no-I/O function over the typed `CodeSnapshot`) always computes the impacted set: the change's
   symbols' NON-SEED structural dependants over the AST call graph, bounded 1-2 hops. The seam
   always has an answer — the graph never gates a run.
2. **A healthy persistent graph upgrades the answer.** When the graph leg succeeds, the
   ACL-scoped `expand_candidates` expansion (the same `IMPACT_EXPANSION_RELS` traversal) is
   preferred when its result is at least as rich as the in-process walk's.
3. **Any graph failure rolls back.** Down (populate/expand raises or stalls — the hard
   client-side deadline still holds), **or empty/truncated** (the graph returns fewer dependants
   than the AST can see — the 2d/2e wall's exact signature: the 300ms/40-node BFS reads 0 while
   the structural edges exist): the seam keeps the in-process walk's answer and records the
   provenance.

## The semantics DECLARED (queryable + auditable)

`code_change_facts.py` now carries `IMPACTED_SEMANTICS` — the pinned definition:

> **definition: structural** — the impacted count is the number of NON-SEED structural
> dependants of the change's symbols reachable over the CALLS edges (bounded 1-2 hop,
> ACL-scoped). **contrast: behavioral** — a behavior-preserving change has zero behavioral
> impact on its callers even though the structural edges exist (the 2d/2e wall: the
> widgets-call-add edges EXIST while the behavioral counter read 0).

The declaration rides on every emission: `ChangeAnalysis.impacted_semantics` +
`impacted_source` (`"graph"` | `"in_process_walk"`) on the ledger record, the
`impacted_symbols` evidence payload (`{"count", "semantics", "source"}`) backing the fact, and
the EVIDENCE context the next phase receives. Never implicit.

## The wall's fix, reproduced at the seam

The wall-style fixture (a behavior-preserving change to `add` + the added `widgets` calling it):
the graph query comes back **empty** (returns only the seeds — the wall's truncation
signature), so the seam **rolls back to the in-process walk and reports impacted=1** (`test_add`
— the non-seed structural dependant the 300ms BFS missed). The wall's wrong 0 is NOT
reproduced by the seam; the semantics' inspectability is.

## The test outcome + the controlled graph-unavailable check

`tests/test_change_analyzer.py` (the seam's hermetic loop, 16 tests) covers:

- the healthy-graph path (graph result preferred, `source="graph"`);
- the **empty/truncated rollback** (the wall fixture: graph returns 0 → in-process walk's
  impacted=1, `source="in_process_walk"`, `graph_status="available"`);
- the **controlled graph-unavailable check** — a graph whose `populate` raises, a graph whose
  `expand` raises, and a **stalled graph** (60s sleep under a 1s deadline) all return within the
  deadline with `graph_status="unavailable"`, the in-process walk's impacted computation, and
  declared provenance — **the seam falls back, never blocks**;
- the declared-semantics assertions + the pure/deterministic in-process walk unit test.

The affected modules' suites all pass: `test_change_analyzer.py` (16), `test_code_change_facts.py`
(31 with the guards), `test_workflow_runner.py` (82 — the composition-root loop + the EVIDENCE
context), `test_cap_2a_spec.py` + `test_graph.py` + `test_dependency_direction.py` (42),
`test_run_workflow_graph_cli.py` (15), `test_script_classification.py` + `test_cli_resolution.py`
(76). Ruff clean on all changed modules.

## Honest limits

- The in-process walk resolves called names to qualified names within the snapshot (best-effort,
  matching the graph's CALLS extraction); it is the bounded rollback, not a second graph.
- The seam is opt-in (the default remains the no-op analyzer); the graph-first path activates
  when a `graph_client` is injected at the composition root.

**LOG:** the seam's change (graph-first impacted computation + the declared semantics + the
in-process rollback) committed with the tests; the controlled graph-unavailable check passes (the
seam falls back, never blocks); the wall-style fixture reports impacted=1 via the rollback.
**PASS.**
