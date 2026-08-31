---
status: accepted
---

# persistent_code_graph_findings — known-safe list

**Spec:** `persistent_code_graph@0.1`. **Adversarial phase p6.**
Every item below was verified mechanically (live Neo4j re-queries over the raw driver, source reads,
test runs, SHA checks) during the adversarial review
(`docs/reviews/persistent_code_graph_findings_adversary.md`). Nothing in this list is assumed.

| # | item | evidence |
|---|---|---|
| K1 | The wall's structural edges EXIST in the persistent graph | fresh-driver `MATCH (a:SymbolVersion)-[:CALLS]->(b {qualified_name:'add'})` per `incorrect_rebuilt` cell returns **20** inbound dependants (`test_add` + `widget_1..19`) for all four cells — `abstention_r1/r2`, `status_quo_r1/r2` |
| K2 | The impacted counter recorded 0 (the wall's other fact) | `experiments/results/cap_adaptive_2d/p1_incorrect_rebuilt_probe.json` carries `impacted_symbol_count = 0` and `facts.impacted_symbol_count = "0"` on disk, unchanged; `changed_symbol_count = "20"`, `changed_symbols_with_tests_ratio = "0.05"`, `probe_verified_with_10s_deadline.impacted = 3` |
| K3 | The impacted semantics are declared, cited, and on every emission — never implicit | `IMPACTED_SEMANTICS` (`code_change_facts.py:122-139`): `definition="structural"` + a `contrast` naming the widgets-call-add wall + a `source` (design §1/§2, spec hard rule 3); written onto the `impacted_symbols` evidence payload (`evidence_analyzer.py:363-375`) and `ChangeAnalysis.impacted_semantics`/`impacted_source` (`:250-251`) |
| K4 | The rollback is the default posture and never blocks | `_in_process_impacted` (`evidence_analyzer.py:67-111`) is pure/deterministic/no-I/O and computed first (`:183-184`); the graph leg runs under `GRAPH_LEG_TIMEOUT_SECONDS=30` via a `ThreadPoolExecutor` deadline; raised `populate`/`expand` and empty/truncated results all roll back to the walk with declared provenance |
| K5 | The seam's hermetic loop passes | ran 8 `tests/test_change_analyzer.py` tests (wall rollback, healthy-graph-preferred, graph-down, expand-failure, no-graph, requested-but-unavailable, semantics-declared, in-process-pure) — **8 passed** |
| K6 | The pre-verification dependant sets are real | raw-graph re-derivation matches `pre_verification.json`: `add`→20, `tally`→`test_tally` (1), `widget_1`→0 (leaf negative), `subtract`→`test_subtract` (1, mid) |
| K7 | The spec SHA pins correctly | `sha256sum workflows/repository/persistent_code_graph.yaml` = `3b7984bc7ff6587d423592562056c48b6538c85bdffc06d2716d2d45886cebe7` — matches the header |
| K8 | The graph-load sources and snapshot depth are honest | `p1_build_graph.json`: 108 framework modules (module layer only), 12 fixture codebases (module + symbol layer), one clean 6-revision story arc (402 symbols / 413 supersedes / 368 calls); the findings' §6 limits match, nothing padded |
| K9 | The recorded wall facts and the phase records are all on disk | `p1_build_graph.json`, `wall_reproduction.json`, `pre_verification.json`, `seam_wiring.json` (and the probe) all exist and reconcile to the findings' figures |

**Not known-safe** (deliberately flagged, see the adversary):

- **K-not-safe-1 — the `evidence_analyzer.py:225-247` line citation is stale.** The findings §3
  inherits this pointer from `wall_reproduction.json`'s `counter_definition.mechanism` (accurate at p2
  time). p4's seam refactor replaced the `_neighborhood` method with `_graph_neighborhood` +
  `_in_process_impacted`, so the cited mechanism moved: the `timeout_ms=300` deadline now lives at
  `evidence_analyzer.py:314`, the seeds-exclusion at `:324-325` (in-process mirror `:96-99`). The cited
  *content* still exists and was independently re-confirmed — the defect is the *line pointer*. Re-point
  it to the stable identifiers (`IMPACTED_SEMANTICS`, `_graph_neighborhood`, `_in_process_impacted`)
  rather than re-pinning numbers a future refactor will move again.
