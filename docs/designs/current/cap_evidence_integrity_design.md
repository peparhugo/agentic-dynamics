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

**Identity rule (two-ID contract — sol review finding 9):** every versioned node carries a
stable logical slot and an immutable version, mirroring the knowledge plane:
`entity_id = f(repository_id, path, qualified_name, kind)` and
`version_id = f(entity_id, commit, content_hash)`; `new -[:SUPERSEDES]-> old` is deterministic
from these. Rename handling: **explicitly unsupported** (a rename is a new entity, recorded as
such — no implicit matching).

**ACL rule (traversal-enforced — finding 2):** `repository_id` is tenancy identity, NOT the ACL
field; `acl_scope` is. The isolation is enforced INSIDE the traversal: `expand_candidates`
accepts both `repository_id` and `acl_scope`, constrains the seed and every Cypher hop, and
FAILS CLOSED for any versioned node missing either property. Filtering after traversal
(`retrieval.py:1018-1019`) remains a second layer, never the enforcement.

**Seed join (finding 3):** the executor's retrieval seeds are `Knowledge` records; the versioned
nodes must be reachable from them. Chosen: **multi-labeled `Knowledge:SymbolVersion` nodes** on
the code records the versioned graph populates, so existing full-text seeds expand directly
into symbol versions. `CONTAINS` and `AFFECTS` are ADDED to `ALLOWED_EXPANSION_RELS`
(`graph.py:27-37`) and `RELATIONSHIP_WEIGHTS` (`retrieval.py:78-87`) with weights, so every
relation the executor must traverse is traversable.

**Durable record representation (finding 7):** the structured analyzer fields
(`tool_version`, `config_hash`, `analyzed_sha`, `rule`, `severity`, `line`, `coverage`) are
carried as a **typed JSON payload inside `text`** (the existing `record_factory` surface stays
unchanged — no schema migration; `extra_fields` is used only for the established keys). Chosen
now by design; the implementation does not choose ad hoc.

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

## 5. Implementation order (the workflow's phases — revised per sol review findings 4/5/6/10/11)

1. **Prerequisite gate** — the four in-flight branches + their adversary reviews must be
   complete before this stream fires; the lifecycle index is refreshed (spec_status).
2. **Sonar revision identity** — revision-scoped project key; persist tool version, config
   hash, analyzed SHA, coverage (typed JSON payload in `text`); a stale-fetched analysis is
   REFUSED (`sonar_analysis_status: stale-refused`), never stamped. Verify: the live `exp_src`
   staleness is now detected.
3. **Typed CodeSnapshot + CodeDelta** (moved BEFORE diagnostic linking — finding 4) —
   tree-sitter-based; `_CodeSymbol` gains `qualified_name` + `source_span`; replaces the regex
   heuristic path (API-compatible with CommitAnalysis); the two-ID contract lands here.
4. **Issue-level records (Sonar AND Pyright — finding 5)** — one record per Sonar issue AND per
   LSP diagnostic, each linked to the smallest containing symbol (symbols now exist from step 3);
   the 93-issue compression is retired. TESTED_BY derivation rule: deterministic test-linking
   (test-file→module name matching, recorded as the rule's provenance); if not derivable for a
   given fixture, `changed_symbols_with_tests_ratio` is DEFERRED (fact omitted), never invented.
5. **Versioned graph population** — ModuleVersion/SymbolVersion with the two-ID contract,
   SUPERSEDES edges; multi-labeled `Knowledge:SymbolVersion` seeds; CONTAINS/DEFINES/IMPORTS
   populated first, CALLS/TESTED_BY/AFFECTS next; ACL enforced in the traversal (finding 2).
6. **`code_change_facts/v1` + `verify_code_change/v1`** — minted only from the typed CodeDelta
   (minting-order guard); semantics per finding 8: status facts carry a measured enum
   (`available`/`unavailable`/`stale-refused`), dependent counts are OMITTED when the analyzer
   did not run (never `None`-as-zero, never fabricated); denominators + zero-change behavior
   defined; `code_change_risk` is `[C]` with its deterministic formula and policy provenance
   recorded (no arbitrary weights).
7. **Runtime loop smoke (finding 6)** — the injected phase-boundary analyzer protocol + a
   concrete composition-root data flow (change → CodeSnapshot/CodeDelta → graph update →
   `code_change_facts` emit → executor neighborhood supplied) proven by ONE fixture or smoke
   workflow. Opt-in, OFF by default, but the end-to-end evidence loop is demonstrated, not
   merely declared.

## 6. Campaigns (revised per sol review finding 1 — unconfounded)

**Campaign 1 — context value (unconfounded):** the RAG arm explicitly DISABLES graph expansion
(the existing fusion already expands via Neo4j at `retrieval.py:1001-1049` — without the
disable, RAG and Graph arms both use topology and the contrast is void):

| Arm | Context |
|---|---|
| Baseline | current workflow (no augmentation) |
| RAG | lexical/dense augmentation, **graph expansion disabled** |
| Graph | revision-correct symbol neighborhood (traversal-enforced ACL) |

**Campaign 2 — control value (split, finding 1):** shadow routing always executes the baseline,
so it cannot measure outcome value directly. Split:
- **2a — shadow calibration:** the adaptive verifier proposes (depth/scope/rework) while the
  baseline executes; measure proposal quality vs the outcome the baseline actually produced
  (predicted vs observed blast radius).
- **2b — live static-vs-adaptive:** separately authorized AFTER 2a shows non-inferiority; only
  then does the adaptive verifier actually select verification.

| 2a (shadow calibration) | 2b (live, gated on 2a) |
|---|---|
| Static (baseline executes; adaptive proposes) | Static |
| Shadow adaptive (proposals scored vs realized outcome) | Applied adaptive (only after 2a non-inferior) |

**Measured:** independent test success, new LSP errors, new Sonar criticals, rework, cost,
latency, context tokens, predicted-vs-observed blast radius.

## 7. Constraints carried from the session's rules

- No phantom producers: predicates minted only when their source (CodeDelta, analyzers) exists.
- Null-not-zero on every analyzer status.
- Identity includes repository_id + commit everywhere.
- ACL on every surface the executor can reach.
- Shadow-only before any new automatable action (AUTOMATABLE_ACTIONS unchanged).
- The four in-flight branches + their adversary reviews land first.
