---
status: accepted
---

# kb_finding_layer k4 — the graph-leg investigation + the untyped-record resolution

**Status: PASS · Role: `kb_finding_layer` k4 (`k4_graph_and_untyped`).** The k4 phase owns two
investigations: (a) the empty-`source_type` retrieval candidates and (b) the zero-path graph
leg. Every number below is a live command against the machine-local KB state at the main
checkout (Neo4j `bolt://localhost:7687`, Redis 6380 db 2, Chroma `knowledge_chunks_v1`).

## 1. The untyped-record investigation — resolved by TYPING (not by silent dropping)

### What writes empty `source_type` records

Nothing current. The producer contract requires a type by construction
(`record_factory.build_record` takes `source_type` as a required kwarg), the registry's compact
manifest is 100% typed (14,911 rows, zero missing), and every durable artifact
(`experiments/results/kb/<id>.json`) carries a real `source_type`.

The probe's 40/61 empty candidates are **stale store metadata, not stale records**: the dense
leg's Chroma population (812 docs in `knowledge_chunks_v1`) was written by an older kb-chroma
projection (pre-`637fd8455`, 2026-08-18) that did not persist the `source_type` property. The
same records' durable artifacts are typed — **812/812 resolve** to
`kb/<knowledge_id>.json`, carrying `finding` (241) / `story` (302) / `review` (242) /
`meta_session` (27). The kb-chroma-v1 consumer group has never consumed (`last-delivered 0-0`),
so the legacy population was never re-projected.

### The fix (retrieval-side, `src/agentic_dynamics/knowledge/retrieval.py`)

1. **`source_type_resolver` seam.** `retrieve()` accepts a deterministic `candidate_id ->
   source_type` resolver, consulted only when store metadata is silent. `default_retrieve_fn`
   (`augment.py`) wires a durable-artifact resolver (reads `kb/<id>.json`; memoised), so a
   stale-metadata record is TYPED from the authoritative layer instead of entering selection
   untyped.
2. **Cross-leg typing.** When the dense leg surfaces a record whose metadata is silent and the
   lexical leg (Neo4j) carries the type for the same canonical id, the merged candidate adopts
   the typed value.
3. **No-silent-empties gate.** A candidate that is STILL untyped after both the store metadata
   and the resolver were consulted never participates in the top-K ahead of a typed one: it is
   excluded from selection and the exclusion is recorded on the attempt
   (`RetrievalAttempt.untyped_excluded` — `{id, reason}`), never silent. An entirely-untyped
   pool (a pure legacy store) stays selectable — back-compatible.

### Probe result after the fix

The 2026-09-02 probe (`repository_id=""`, `acl_scope=""`, phase objective set) NOW returns:

```
selected: 61
source mix: {'code': 21, 'review': 40}      # was {'code': 21, '': 40}
graph_paths: {}
untyped_excluded: []
```

Zero untyped candidates in the top-K. The 40 former empties are typed `review` records (their
durable artifacts' real type), so they participate as typed content — nothing is silently
dropped.

## 2. The graph-leg investigation — resolved: edges EXIST, but only on versioned, scoped nodes; the KB-event consumer projects leaf nodes; the leg is documented DOWN

### Consumer + graph state (measured live)

```
kb-neo4j-v1   consumers 3   pending 0   lag 0    last-delivered 1788451849953-0   (caught up)
kb-chroma-v1  consumers 0   last-delivered 0-0                                   (never consumed)
kb-registry-v1 consumers 61  pending 2461 lag 1726

Knowledge nodes by source_type: code 33,083 | story 302 | finding 265 | review 242 | policy 37 | meta_session 27 | spec 3 | report 2
  of which versioned (multi-label ModuleVersion/SymbolVersion/Revision): 32,001
  of which legacy (pure :Knowledge): 1,960  (legacy nodes hold ZERO allowlisted out-edges)

Relationship census: CONTAINS 36,099 | DEFINES 32,001 | TESTED_BY 9,685 | CALLS 5,394 |
  SUPERSEDES 3,958 | HAS_STEP 2,435 | NEXT 2,213 | IMPORTS 565 | RUN_ON 435 | TOUCHED 272 | ...
```

### Why `graph_paths` is 0 for the KB corpus

The retrieval graph leg is NOT broken, and the graph is NOT empty of edges (~90k exist). The
zero has two compounding causes, and both are **honest state**, not a query/leg bug:

1. **Write-side absence for the records retrieval ranks.** The KB-event consumer
   (`scripts/kb_worker.py --group kb-neo4j-v1`, caught up, lag 0) projects each knowledge event
   as a relationship-less `:Knowledge` node. It writes edges ONLY for lineage events
   (`operation=supersede` → `SUPERSEDES`; `operation=delete`+`causes` → `CLEARED_BY` /
   `REPLACED_BY`). Ordinary upserts — the findings/reviews/stories/observations retrieval
   actually ranks — produce leaf nodes. No event type maps to a relationship between two
   distinct knowledge records, so the graph has nothing to traverse for the corpus retrieval
   answers with.
2. **The only edge-rich subgraph is scope-invisible to an unscoped probe.** The ~90k structural
   edges (`DEFINES`/`CALLS`/`CONTAINS`/`TESTED_BY`/…) live on **versioned** nodes
   (`ModuleVersion`/`SymbolVersion`), which are populated only by the opt-in versioned-graph
   path (change-analysis `--change-analysis-graph`, `graph_family_build`) and carry a
   `repository_id`+`acl_scope` tenancy identity. `expand_candidates`'s traversal ACL fails
   closed on missing scope (`_acl_clause` → `NOT (n:ModuleVersion OR n:SymbolVersion)`), so an
   empty-scope probe is structurally incapable of traversing the only edges that match the
   allowlist.

### The positive proof (edges exist → paths returned)

The leg itself is functional. A **scoped** expansion over a populated versioned scope
(`self-cap2a_p2_registry_canonicalize`, 29,675 versioned code nodes) returns real paths:

```
expand_candidates(real seed, scoped): 40 nodes, depth distribution {0: 1, 1: 7, 2: 32}
  traversed rel types: CALLS (34), DEFINES (2), CONTAINS (1), IMPORTS (2)
a scoped retrieve() over that scope: graph_paths 5 (non-empty)
```

Committed as `tests/test_versioned_graph.py::TestVersionedPopulation::test_expansion_returns_a_path_when_edges_exist`
(external, live-Neo4j): seed two functions with a real `CALLS` edge → scoped expansion returns a
depth ≥ 1 path. So the graph leg is real and correct; the KB-corpus zero is a **documented
down-state**, matching the preregistration's Edge-5 baseline.

### What would populate the KB-corpus graph leg

- A producer/consumer change that writes knowledge→knowledge edges between the records
  retrieval ranks (e.g. a phase-emitted finding linked to the code/story it measured, or a
  review linked to the story it reviewed) — the `emit_self`/self-build path is the natural
  place, since it already knows the phase's `causes`.
- Or a scoped retrieval against a worktree whose versioned code graph was populated by the
  change-analysis path — the expansion then traverses real code edges.

Neither is a fix inside `expand_candidates`, whose behavior is correct and tested.

## LOG

**PASS.** (a) The empty-`source_type` population is stale store metadata from an older chroma
projection; the retrieval fix types it from the durable artifacts (resolver seam + cross-leg
typing) and excludes any residual untyped record from the top-K with a recorded reason — the
probe's mix goes from `{'code': 21, '': 40}` to `{'code': 21, 'review': 40}`, zero untyped.
(b) The graph leg: edges EXIST (~90k) on versioned, scope-gated nodes; the KB-event consumer
projects leaf nodes; `graph_paths: 0` is honest state for the KB corpus and is documented down
with the consumer evidence above, while a synthetic seeded test proves the leg returns paths
when edges exist in scope. Committed.
