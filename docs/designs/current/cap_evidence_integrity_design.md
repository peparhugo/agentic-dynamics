---
status: accepted
---
# Evidence Integrity — versioned code snapshot, revision-correct quality signals, and the
# code-change fact plane

**Status: accepted as the design for the next implementation stream.** Grounded in an external
review whose load-bearing claims were verified against the tree (2026-08-25). Implementation
runs as `cap_evidence_integrity` (flash) with a sonnet-5 adversary review; the two campaigns
(`cap_evidence_campaign_1`/`2`) are ExperimentSpecs designed here, authored separately.

## 1. Problem (verified)

| Gap | Verification |
|---|---|
| **Sonar provenance is revision-incorrect.** `quality_ingestion.py:215` calls
  `run_sonar_analysis(str(codebase_path))` — no `project_key`, no revision. `sonar.py:167`
  is fetch-first: if the server holds a cached analysis it returns it directly. A current
  record can be stamped with the current commit while its analysis is from an older revision
  (the live `exp_src` analysis dates Aug 16 and references retired `instrument/*` paths). | read
  `quality_ingestion.py:210-220`, `sonar.py:157-170` |
| **No LSP tooling active.** Every configured adapter (pyright, mypy, tsc, golangci-lint,
  rust) reports unavailable. | `lsp_diagnostics.py` probe results |
| **"AST diff" is regex.** `commit_analysis.py:218-223` computes diff-stat heuristics over
  `git diff` lines; the docstring admits it. tree-sitter exists (`core/language.py:194
  parse_codebase`) but produces no versioned semantic deltas. | `commit_analysis.py` docstring |
| **Graph has nodes, no topology.** Live inspection: 1,082 `code` nodes, zero relationships;
  the 133 `CodeModule` nodes belong to one old run; `DEFINES/IMPORTS/CALLS/TESTED_BY` are
  allowlisted (`knowledge/graph.py:27-37`) but unpopulated. | graph inspection |
| **Quality signals over-compressed.** 93 issue-level Sonar findings (file/line/rule/
  severity/message/remediation) collapse to one sentence (`quality_ingestion.py:100-123`);
  LSP diagnostics likewise. The engine cannot connect an issue to the symbol it affects. | read
  the reducers |

## 2. Target architecture

Neo4j is a **versioned evidence graph**, never the controller's truth store. The controller
consumes canonical facts only (`context_compiler.py:11-21` — arbitrary retrieved text never
becomes control truth).

```text
Revision -[:CONTAINS]-> ModuleVersion -[:DEFINES]-> SymbolVersion
ModuleVersion -[:IMPORTS]-> ModuleVersion
SymbolVersion -[:CALLS]-> SymbolVersion
SymbolVersion -[:TESTED_BY]-> TestSymbol
Diagnostic    -[:AFFECTS]-> SymbolVersion
SonarIssue    -[:AFFECTS]-> SymbolVersion
new version   -[:SUPERSEDES]-> old version
```

**Identity rule:** every node identity includes `repository_id` + commit SHA. Global
`module_path` uniqueness is insufficient across revisions and worktrees (the identity-collision
lesson, applied to the graph preemptively).

**ACL rule (refinement added):** the bounded neighborhood the executor receives carries the
same scope discipline as the fact plane — the private repo's symbols must never appear in a
public-repo executor's expansion. `repository_id` on every node makes this enforceable.

**Two consumers, kept separate:**

| Consumer | Input | Purpose |
|---|---|---|
| Executor (agent) | Bounded Neo4j neighborhood (callers, imports, tests, active issues) | Coding context — retrieval supports execution |
| Controller | Canonical facts only | Verification depth, routing, continuation, escalation — through the existing validator |

## 3. First useful intelligence: change-impact and verification, not routing

1. Before a change: identify likely target symbols from the task.
2. Expand 1-2 graph hops: callers, imports, tests, active issues.
3. Give only that bounded neighborhood to the executor.
4. After the commit: rerun AST + Pyright quickly.
5. Run Sonar at the verification/phase boundary (cost-disciplined: one scan's cost measured
   before it enters the loop — the E4 lesson).
6. Compute the before/after `CodeDelta`.
7. Propose targeted tests, full verification, or rework from measured facts.
8. All proposals shadow-only initially.

## 4. `code_change_facts/v1` (the first reducer)

Job-scoped facts, consumed by a `verify_code_change/v1` contract (shadow):

- `analysis_revision_matches` — the analysis's revision equals the job's revision
- `ast_parse_coverage` — fraction of changed files parsed by tree-sitter
- `lsp_analysis_status` — pyright ran / unavailable
- `sonar_analysis_status` — sonar ran / unavailable / **stale-revision-refused**
- `changed_symbol_count` — from CodeDelta (minting-order guard: minted ONLY after the typed
  CodeDelta exists)
- `impacted_symbol_count` — 1-2 hop reachable set
- `new_lsp_error_count` — post-change delta
- `new_sonar_critical_count` — post-change delta
- `changed_symbols_with_tests_ratio`
- `code_change_risk` — composite `[C]`

**Unavailable analysis remains unknown, never zero** (m2 discipline).

## 5. Implementation order (the workflow's phases)

1. **Sonar revision identity** — revision-scoped project key; persist tool version, config
   hash, analyzed SHA, coverage in the quality record; a stale-fetched analysis is REFUSED
   (recorded as `sonar_analysis_status: stale-refused`), never stamped. Verify: the live
   `exp_src` staleness is now detected.
2. **Pyright pinned** — the Python repo's LSP tool; availability probe durable; diagnostics
   ingested one-record-per-diagnostic, linked to the smallest containing symbol.
3. **Typed CodeSnapshot + CodeDelta** — tree-sitter-based; replaces the regex heuristic path
   (API-compatible with CommitAnalysis); versioned semantic deltas.
4. **Versioned graph population** — ModuleVersion/SymbolVersion with repository_id+commit,
   SUPERSEDES edges; populate DEFINES, IMPORTS first; CALLS, TESTED_BY next; ACL on the
   neighborhood expansion.
5. **`code_change_facts/v1` + `verify_code_change/v1`** — the reducer (minting-order guard:
   only after CodeDelta exists) + the shadow contract.
6. **Injected phase-boundary analyzer protocol** — dependency inversion like the existing
   routing/telemetry seam.

## 6. Campaigns (designed here, authored as ExperimentSpecs after the workflow lands)

**Campaign 1 — context value (unconfounded):**

| Arm | Context |
|---|---|
| Baseline | current workflow (no augmentation) |
| RAG | existing lexical/dense augmentation |
| Graph | revision-correct symbol neighborhood |

**Campaign 2 — control value:**

| Arm | Verification |
|---|---|
| Static | existing fixed verification |
| Shadow adaptive | verification proposed from code-change facts |
| Applied adaptive | only after shadow is non-inferior |

**Measured:** independent test success, new LSP errors, new Sonar criticals, rework, cost,
latency, context tokens, predicted-vs-observed blast radius.

## 7. Constraints carried from the session's rules

- No phantom producers: predicates minted only when their source (CodeDelta, analyzers) exists.
- Null-not-zero on every analyzer status.
- Identity includes repository_id + commit everywhere.
- ACL on every surface the executor can reach.
- Shadow-only before any new automatable action (AUTOMATABLE_ACTIONS unchanged).
- The four in-flight branches + their adversary reviews land first.
