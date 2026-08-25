# e6 — Runtime-loop smoke (cap_evidence_integrity)

Date: 2026-08-25 · Branch: feature/cap-evidence-integrity

## The implementation (design §5.7)

1. **Runtime-owned protocol** (`runtime/change_analyzer.py`, dependency-inverted like
   `runtime/telemetry.py`): `ChangeAnalyzer` Protocol + `ChangeInput`/`ChangeAnalysis` (PURE
   DATA — no `control.facts` types, no graph handles) + `NoopChangeAnalyzer` +
   `default_change_analyzer()` + `run_change_analysis(change, analyzer=None)`. The default is a
   strict no-op — a run that never injects an analyzer is byte-identical to one without the seam.
   `runtime` imports NOTHING from `control` (guard held; `test_dependency_direction` green).
2. **Concrete composition-root implementation** (`control/evidence_analyzer.py`,
   `EvidenceChangeAnalyzer`): the concrete data flow —
   `change -> CodeSnapshot/CodeDelta -> versioned-graph update (populate_versioned_graph) ->
   code_change_facts/v1 emit -> executor neighborhood supplied`. The neighborhood is the
   ACL-scoped 1-2 hop reachable set seeded from the changed symbols' `version_id`s
   (`expand_candidates` with `repository_id` + `acl_scope`, e4); facts are de-typed to plain
   dicts so runtime stays control-free. The `graph_client` is duck-typed, so the analyzer is
   hermetic-testable and never requires a live analyzer/Neo4j.
3. **Exports**: `runtime/__init__.py` + `control/__init__.py` updated.

## The tests (`tests/test_change_analyzer.py`, 6)

- Default no-op is a strict `ChangeAnalysis()` (existing behavior identical).
- `run_change_analysis` dispatches to the injected analyzer (None → no-op).
- **Hermetic loop smoke**: fixture change → delta → graph update (store double, ACL threaded) →
  facts (changed_symbol_count=2, statuses, impacted=1, risk=0.115 with tests-ratio 2/2) →
  neighborhood (`("Calc",)`, seeds excluded).
- No graph client → graph_updated False, impacted OMITTED (never zero), delta facts still emit.
- **Live Neo4j composition-root proof**: the REAL data flow populates the versioned graph for
  the after-revision (3 SymbolVersions), emits the facts, and the ACL-scoped neighborhood is
  supplied.
- `test_context_plane_facts` allowlist widened explicitly for the new producer.

Full suite: **1947 passed** (excluding pre-existing environmental hangs — Chroma/Ollama — and
the pre-existing lab-output failures on the parent checkout).

## Verdict

**PASS** — the injected phase-boundary protocol (runtime owns it; default no-op; injected at the
composition root) PLUS the concrete data flow proven by a fixture and a live-Neo4j smoke:
change → delta → graph update → facts emit → bounded executor neighborhood.
