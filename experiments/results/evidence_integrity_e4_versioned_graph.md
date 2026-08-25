# e4 — Versioned graph + traversal ACL (cap_evidence_integrity)

Date: 2026-08-25 · Branch: feature/cap-evidence-integrity

## The implementation (design §5.5)

1. **Versioned graph population** — `Neo4jClient.populate_versioned_graph(snapshot, revision,
   repository_id, acl_scope, issues=, diagnostics=)`:
   - `Revision` / `ModuleVersion` / `SymbolVersion` nodes with the **two-ID contract**
     (`entity_id` = stable slot `f(repository_id, path, qualified_name, kind)`, `version_id` =
     `f(entity_id, commit, content_hash)`); renames are new entities (no implicit matching).
   - `SUPERSEDES` edges new→every older version of the same entity, deterministic from the ids
     and anchored by `version_id` (re-population never cross-links).
   - Edges populated first: `CONTAINS` (Revision→Module, Module→Symbol), `DEFINES`, `IMPORTS`;
     next: `CALLS` (name-based from `CodeSymbol.calls`), `TESTED_BY` (the §5.4 rule), `AFFECTS`
     (optional issues/diagnostics → smallest containing `SymbolVersion`).
   - **Seed join**: every `SymbolVersion` is ALSO `:Knowledge` (`knowledge_id` = `version_id`,
     `text`, `authority='SOURCE'`, `source_type='code'`), so existing full-text seeds expand
     directly into symbol versions.
   - Additive: only versioned nodes/edges written; existing unversioned nodes untouched.
2. **Traversal ACL (finding 2, fail-closed)** — `expand_candidates` gains `repository_id` +
   `acl_scope`; `_resolve_node` (seed) and `_neighbors` (every hop) enforce the predicate
   INSIDE the Cypher WHERE, never as a post-filter:
   - Both supplied → nodes must carry that exact `repository_id` + `acl_scope`.
   - Either omitted (legacy default) → versioned nodes (`ModuleVersion`/`SymbolVersion`) are
     NEVER traversed (fail closed on missing scope, always); only unversioned legacy nodes are
     reachable.
   - `retrieval.retrieve` caller updated to pass both explicitly.
3. **Allowlist/weights** — `CONTAINS` + `AFFECTS` added to `ALLOWED_EXPANSION_RELS`
   (`graph.py`) and `RELATIONSHIP_WEIGHTS` (`retrieval.py`).

## The tests

- `tests/test_versioned_graph.py` (new, 9 live-Neo4j integration tests): revision pair →
  versions + SUPERSEDES; CONTAINS/DEFINES/IMPORTS; CALLS + TESTED_BY edges; AFFECTS from
  issues; the multi-label Knowledge seed join (full-text seed → SymbolVersion); scoped seed
  cannot reach a private-repo node (hop constraint); legacy-omitted scope fails closed for
  versioned; legacy-omitted scope still reaches unversioned nodes; population is additive.
- `tests/test_graph.py::test_allowlisted_relationships_are_fixed` updated for CONTAINS/AFFECTS.

112 graph/retrieval/data-flow tests green; full suite green for the changed surfaces.

## Verdict

**PASS** — a fixture revision pair produces versioned nodes + SUPERSEDES + populated edges; a
public-scope seed cannot reach a private-repo node (the hop constraint, not post-filter); the
Knowledge→SymbolVersion seed join works; additive (unversioned nodes untouched) and fail-closed
legacy defaults.
