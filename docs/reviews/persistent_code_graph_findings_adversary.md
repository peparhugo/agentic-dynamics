---
status: accepted
---

# persistent_code_graph_findings — adversarial review (p6)

**Role:** adversarial verifier — falsify the findings. Spec `persistent_code_graph@0.1`
(`workflows/repository/persistent_code_graph.yaml`). Findings under review:
`docs/reviews/persistent_code_graph_findings.md`, grounded in
`experiments/results/graph_family/{p1_build_graph,wall_reproduction,pre_verification,seam_wiring}.json`
and the wall's own artifacts (`experiments/results/cap_adaptive_2d/p1_incorrect_rebuilt_probe.json`).

Every item below was re-derived independently — from the live Neo4j graph (`bolt://localhost:7687`,
reached directly over the driver, not through the phase scripts), the seam source
(`src/agentic_dynamics/control/{evidence_analyzer,reducers/code_change_facts}.py`,
`src/agentic_dynamics/runtime/change_analyzer.py`), and the raw artifact JSONs — never from the
findings doc's own numbers.

## Finding table

| # | check | attempt to falsify | result | finding |
|---|---|---|---|---|
| F1 | **the wall reproduction** (both facts present, re-queried raw) | re-queried the live graph directly: `MATCH (a:SymbolVersion)-[:CALLS]->(b {qualified_name:'add'})` per `incorrect_rebuilt` cell, and read the recorded counter from the probe | all four cells return **20 inbound `CALLS` dependants** (`test_add` + `widget_1..19`), exactly the committed `wall_edges` set; `p1_incorrect_rebuilt_probe.json` records `impacted_symbol_count = 0` + `facts.impacted_symbol_count = "0"` + `changed_symbol_count = "20"` + `ratio = "0.05"` + `probe_verified_with_10s_deadline.impacted = 3` | **CLEAN** — the edges EXIST and the counter read 0, both confirmed |
| F2 | **the semantics** (declared + cited in the seam, no implicit definition) | read `code_change_facts.py` and `evidence_analyzer.py` for an *implicit* or *undeclared* impacted definition | `IMPACTED_SEMANTICS` (`code_change_facts.py:122-139`) is a recorded constant — `definition="structural"`, a `description`, a `contrast` (the behavioral-vs-structural lesson, the widgets-call-add wall named), and a `source` (design §1/§2 + spec hard rule 3). It is written onto every emission: the `impacted_symbols` evidence payload `{"count","semantics","source"}` (`evidence_analyzer.py:363-375`) and `ChangeAnalysis.impacted_semantics`/`impacted_source` (`:250-251`). No implicit definition anywhere | **CLEAN** |
| F3 | **the rollback** (controlled graph-unavailable falls back, never blocks) | read the analyzer's failure paths + ran the seam's hermetic loop | `_in_process_impacted` (`evidence_analyzer.py:67-111`) is pure/deterministic/no-I/O and is computed FIRST (the default posture, `:183-184`); the graph leg runs under `GRAPH_LEG_TIMEOUT_SECONDS=30` via a `ThreadPoolExecutor` deadline (`:193-218`); empty/truncated graph results roll back to the walk (`:225-230`); a raised `populate`/`expand` and a stalled client all degrade to `graph_status="unavailable"` + the walk's answer. Ran 8 seam tests: `test_wall_style_seam_recovers_structural_dependant`, `test_healthy_graph_preferred_when_richer`, `test_graph_down_preserves_delta_facts_and_exposes_status`, `test_expand_failure_degrades_to_unavailable`, `test_no_graph_client_still_emits_delta_facts`, `test_requested_but_unavailable_graph_is_not_mislabeled`, `test_semantics_declared_queryable_on_the_record`, `test_in_process_walk_is_pure_and_deterministic` — **8 passed** | **CLEAN** |
| F4 | **the pre-verification** (dependant sets re-derived) | re-queried the raw graph for the wall hub, the weak-signal symbol, the leaf control, and the mid reference | `add` → 20; `tally` (`unseen_family`) → `test_tally` (1); `widget_1` → 0 (leaf, negative); `subtract` → `test_subtract` (1, mid). All four match `pre_verification.json` exactly | **CLEAN** |
| F5 | **the citations resolve** (every pointer resolves to its content) | resolved the design §1/§2, the spec hard rule 3, the probe path, the phase-record paths, the spec SHA, and the `evidence_analyzer.py` line pointer | design + spec + probe + phase records + SHA all resolve (`sha256sum` = `3b7984bc…` — match). **One pointer is stale:** `evidence_analyzer.py:225-247` (inherited from `wall_reproduction.json`'s `counter_definition.mechanism`) no longer points at the mechanism — see F5a | **CAVEAT (F5a)** |
| F5a | the `evidence_analyzer.py:225-247` line pointer (a sub-check of F5) | read the current source at lines 225-247 and located the mechanism | post-p4 the `_neighborhood` method is **gone** (renamed `_graph_neighborhood`, `:288`); the `timeout_ms=300` deadline now lives at **`:314`**, the seeds-exclusion at **`:324-325`** (and the in-process mirror at `:96-99`). Lines 225-247 now hold the *rollback comparison* + `ChangeAnalysis` construction, not the cited seeds-exclusion/deadline | **FAILED FINDING (citation drift)** |
| F6 | **the coverage / snapshot-depth honesty** | checked the graph-load sources + the story arc against `p1_build_graph.json` | 108 framework modules (module layer only), 12 fixture codebases, one clean 6-revision story arc (402 symbols / 413 supersedes / 368 calls) — the findings' §6 limits are stated, not padded | **CLEAN** |

## Findings (the one real failure, the caveat)

1. **F5a — the `evidence_analyzer.py:225-247` line citation is stale (FAILED finding, non-substantive).**
   The findings §3 cites the wall's mechanism to `evidence_analyzer.py:225-247` (a pointer inherited
   from `wall_reproduction.json`'s `counter_definition.mechanism`, which was accurate at p2 time).
   p4's seam refactor replaced the `_neighborhood` method (which held the `timeout_ms=300` BFS at
   `:225-234` and the seeds-exclusion at `:235-247`) with `_graph_neighborhood` + `_in_process_impacted`,
   so the line pointer drifted: the deadline is now `evidence_analyzer.py:314` and the seeds-exclusion
   `evidence_analyzer.py:324-325`. **The cited content still exists and was independently re-confirmed**
   (F1/F4 re-derived the seeds-exclusion + deadline semantics against the live graph) — the defect is
   the *line pointer*, not the *claim*. It should be re-pointed to the stable identifiers (the
   `IMPACTED_SEMANTICS` constant and `_graph_neighborhood`/`_in_process_impacted` method names) rather
   than re-pinned to numbers that a later refactor will move again.

2. **F5 — every other citation resolves.** The design §1/§2, the spec hard rule 3, the probe path,
   the four phase-record paths, and the spec SHA all resolve to their content. The one drift is F5a.

## Attempted (and failed) falsifications of the findings

- **Could the "edges EXIST" be a leftover of the phase scripts' own writes?** No — I queried the raw
  graph with a fresh driver connection and a hand-written Cypher `MATCH ... [:CALLS] ->`, bypassing
  `scripts/graph_family_wall.py` entirely; all four cells still return 20 dependants on `add`.
- **Could the "counter read 0" be fabricated?** No — `p1_incorrect_rebuilt_probe.json` carries
  `impacted_symbol_count = 0` and `facts.impacted_symbol_count = "0"` on disk, unchanged.
- **Could the semantics be implicit in practice (declared in a docstring but not on the record)?** No —
  the declaration rides on the `impacted_symbols` evidence payload and the `ChangeAnalysis` fields, and
  `test_semantics_declared_queryable_on_the_record` asserts both.
- **Could the rollback block?** No — the graph leg is deadline-guarded (`ThreadPoolExecutor` +
  `GRAPH_LEG_TIMEOUT_SECONDS`), the in-process walk is computed unconditionally first, and the
  empty/truncated branch (`graph_impacted >= impacted or 0`) rolls back exactly on the wall's signature.
  (Test-harness note, not a seam defect: `test_stalled_graph_degrades_within_deadline_never_hangs`
  asserts `elapsed < 10.0` — the analyzer returns within the deadline — but the `StalledGraphClient`'s
  60s sleep runs in a non-daemon `ThreadPoolExecutor` worker, so the *pytest process* lingers ~60s after
  the assertion passes. That is the documented "abandoned worker thread keeps waiting" note
  (`evidence_analyzer.py:161-162`), not a blocked phase.)
- **Could the pre-verification dependant sets be padded?** No — `add`→20, `tally`→1, `widget_1`→0,
  `subtract`→1 all re-derive identically from the raw graph.

## Conclusion

All five mandated attack surfaces are CLEAN except one non-substantive citation defect: the wall
reproduction (both facts re-confirmed live), the semantics (declared + cited + on every emission), the
rollback (default in-process posture, deadline-guarded, falls back never blocks — 8 seam tests pass),
and the pre-verification (dependant sets re-derived) all survive. The one FAILED finding is F5a — the
`evidence_analyzer.py:225-247` line pointer drifted when p4 refactored the analyzer, and the cited
mechanism now lives at `:314` (deadline) and `:324-325` (seeds-exclusion). This does not overturn the
findings' central claims — the semantics the stale pointer was meant to establish were re-derived
independently — but it is a real citation-hygiene defect to fix.

**LOG:** 5 attack surfaces checked — wall reproduction (re-queried raw: 20 dependants + recorded 0,
CLEAN), semantics (declared + cited, CLEAN), rollback (default in-process + deadline-guarded + 8 tests
pass, CLEAN), pre-verification (dependant sets re-derived, CLEAN), citations (resolve, with one
FAILED finding). **1 FAILED finding (F5a: the `evidence_analyzer.py:225-247` line pointer is stale —
mechanism now at `:314` + `:324-325`); non-substantive, findings stand.**
