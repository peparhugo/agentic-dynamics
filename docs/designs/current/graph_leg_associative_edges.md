---
status: accepted
---

# graph_leg_associative_edges — first-family design decision

**Status: accepted · c1 decision (graph_leg_closeout).** Committed by `p0_pin_threads`'s
successor phase `c1_assoc_edge_design`; the code that implements it is `c2_assoc_edge_writer`
(this doc is the design authority that doc must satisfy, and `b1_prune_expansion_rels` must
keep every rel name this doc claims). Scope fence: ONE family — not the whole associative
layer. Follow-on families are named in §7 as deliberately out of scope.

---

## 1. Context — what the graph leg needs

The 2026-09-04 close record (session `2026-09-04-kb-facts-and-graph-repair`, merged
`96738e6da`) and the `p0_pin_threads` preregistration measured the live graph:

- **4,192 Knowledge-only records are ALL degree-0 leaves** — findings (1,294), reviews,
  policies, specs, sessions/meta_session (30), verdicts/wave_verdict (1), and 2,155 flat code
  records. None carries a single edge.
- **Only the multi-label code symbols** (`SymbolVersion`, which `populate_versioned_graph`
  also labels `:Knowledge`) carry edges — CALLS 5,394 / TESTED_BY 9,685 / SUPERSEDES 3,958 /
  CONTAINS / DEFINES / IMPORTS, all among code-structure nodes.
- `finding→code/spec` edges are never written. The graph leg's distinctive value (typed
  traversal from a distilled-knowledge record to the thing it is about, and back) awaits a
  design item — this is that item, scoped to ONE first family.

## 2. The decision (one family)

**Family: the wave-conclusion finding records → the spec entity that produced them.**

- **Source records** — `source_type="finding"`, `extractor_version="wave-backfill/v1"`,
  `logical_locator="wave:<spec>"`. These are the deterministic per-wave conclusion records
  `scripts/kb_backfill_findings.py` derives from the adversarial/known-safe/prereg review docs
  + run ledgers ("THE PAST ENTERS DETERMINISTICALLY"). Measured at the pin: **308 records in
  the corpus, all 308 present as live graph nodes** (`:Knowledge {source_type:'finding',
  logical_locator STARTS WITH 'wave:'}`).
- **Target** — the **spec entity** the record cites: the graph node
  `:Knowledge {entity_id: 'spec:<spec>', source_type: 'spec'}` (the `spec:` entity convention
  the `spec` records already carry — `entity_id = spec:<name>`, `source_uri =
  file://workflows/repository/<name>.yaml`). 165 spec entities exist in the corpus; 45 unique
  spec entities are present as graph spec nodes at the pin (78 nodes, all `lifecycle_state =
  current` — the same entity appearing multiple times is the pre-existing duplication §4.3
  documents). All counts are pin-time (2026-09-04) measurements; they drift as the corpus grows.
- **Edge + direction** — `(finding)-[:PRODUCED_BY]->(spec)`. Read: *this wave-conclusion
  finding was produced by (running) spec S.* `PRODUCED_BY` is an EXISTING allowlisted name
  (`graph.py:46`); claiming it here keeps it through the `b1` prune (the hard rule: a name may
  stay if a writer exists OR the c1 design claims it — this doc claims it, `c2` writes it).
- **What this buys.** The 308 leaf finding nodes gain their first real edges; the spec node
  becomes a hub for its run-outcome records. Retrieval seeded on a spec (its name, its review
  docs) can traverse to the distilled conclusions of every wave run of that spec — the first
  typed Knowledge↔Knowledge hop, demonstrating the writer architecture for every later family.

## 3. Why spec — and why NOT code symbol (the constraint that decides)

The mandate's hard rule: **the citation address must already live in the record or its
artifact; never invent locators.** Verified against the actual corpus:

- The wave-conclusion finding's own `logical_locator` (`wave:<spec>`) and `outcome_id`
  (`<spec>`) ALREADY name the spec. `spec:<name>` is how the target addresses itself. The
  address is resolved, not invented: **269 of 308** records resolve to a spec entity in the
  corpus; **66 of 308** resolve to a spec node already `current` in the live graph at the pin
  (the rest land as the spec records project).
- **No distilled-knowledge record carries a code-symbol citation today.** Measured across the
  leaf corpus: findings cite `exp_*` worktrees (`measured-finding/v1`), `wave:<spec>`
  (`wave-backfill/v1`), or `self-*` cells (`phase-finding/v1`); reviews cite worktree commits;
  meta_sessions cite attempt ids. None carries a `(file_path, qualified_name, kind)` address,
  and a `SymbolVersion`'s canonical id is a content-hashed `version_id` unknowable at
  record-emit time. A code-targeted first family would require text heuristics (invented
  locators) or a record-schema extension — both rejected for the first family. The
  finding→code leg is a documented follow-on (§7) that needs the code citation added at the
  record's source first.

## 4. Writer site, provenance, idempotency (the contract c2 implements)

- **Site** — producer-side, in the wave-conclusion producer's emit path:
  `scripts/kb_backfill_findings.py` `emit_record()` — after the durable artifact + registry row
  (the record is already safe), call the edge helper with the in-memory record. A graph failure
  there must never fail the emit: `best-effort` (try/except, logged), per hard rule 3 and the
  c2 DONE_WHEN "a graph outage degrades to the record emit succeeding without edges".
- **Helper contract (named for c2)** — `graph.write_wave_finding_produced_by(record,
  graph_client)` (or an equivalent single function in the graph module, mirroring how
  `code_ingestion.ingest_codebase_graph` drives `load_codebase_graph`). It:
  1. derives the spec name from `record.logical_locator` (`wave:` prefix stripped) → target
     `entity_id = "spec:" + name`;
  2. **MERGEs the source node** `(:Knowledge {knowledge_id: record.knowledge_id})` and SETs the
     record's own provenance fields with the SAME SET clause the kb-neo4j consumer
     (`scripts/kb_worker.py` kb-neo4j handler) uses — so the producer's node write and the
     consumer's projection converge on ONE node (both are idempotent MERGE+SET of identical
     bytes), never two;
  3. **MATCHes the target, never fabricates it** — and pins a SINGLE node deterministically:
     spec `entity_id` is indexed but NOT unique-constrained, and the live graph already holds
     duplicate `current` copies of the same spec entity (measured at the pin: 12 of 45 spec
     entities appear up to 7×, e.g. `spec:authoring_product_aio` ×7 — a pre-existing
     spec-lifecycle projection condition, NOT something this writer creates). The writer
     therefore resolves
     `MATCH (s:Knowledge {entity_id: 'spec:<name>', source_type: 'spec', lifecycle_state: 'current'})`
     and pins the newest copy deterministically
     (`ORDER BY coalesce(s.indexed_at, ''), s.knowledge_id DESC LIMIT 1`), so a duplicated
     entity still yields exactly ONE target. The spec node is the kb-neo4j consumer's to
     create — the writer never MERGEs a spec node by entity (that would mint more duplicates);
     when NO current spec node is present (spec not yet projected), the writer **skips and
     logs** — idempotent and healing: a later replay (or the c3 replay) lands the edge the
     moment the target exists. The duplicate-current condition is recorded for g9 as a
     pre-existing graph state this family neither causes nor repairs;
  4. **MERGEs the edge** `(f)-[:PRODUCED_BY]->(s)`.
- **Provenance/scope** — the edge is a node-pair fact; it inherits the source record's
  authority + evidence class (`Authority.DERIVED`, `[C]` — the wave-conclusion records are
  deterministic derivations from review docs + ledgers, no LLM) and the record's own
  `repository_id`/`acl_scope`. The endpoints carry different tenancy today (`wave:<spec>`
  source vs `agentic-dynamics`/`public` spec target): under the traversal ACL's **legacy-only
  path** (either repo or scope omitted — the shape the broad org-retrieval queries use) both
  endpoints are unversioned and therefore reachable, so the hop traverses immediately. Under an
  **exact-scope** query only a caller whose scope matches one endpoint per hop resolves it —
  recorded here as the known reachability caveat of this first family (the fix is a later
  family over org-scoped records, §7; g9's leak check must probe this, not assume it away).
- **Idempotency / rerun-safety** — the edge is a `MERGE` keyed on the deterministic pair
  `(record.knowledge_id, spec entity_id)`; the record's `knowledge_id` is itself a pure function
  of (wave, spec sha, content). Re-emitting the same record derives the same pair → exactly one
  edge. `kb_backfill_findings.py` already skips ids present in the registry, so replaying a
  record through the writer is the c3 route (§5).

## 5. The c3 probe criteria (what "the family is live" means)

`c3_assoc_probe` must show, against the live graph (read-only except the ONE replay the c1 doc
authorizes):

1. **One real record replayed through the writer** (pick a wave-conclusion finding whose spec
   target is a `current` graph spec node — 66 such records exist at the pin, e.g. the
   `test_suite_speed` record) → the finding's `:Knowledge` node now carries **exactly one**
   `-[:PRODUCED_BY]->` edge to the `spec:<name>` node.
2. **Traversal breaks leaf-ness**: a depth-1 `expand_candidates` from that finding node (broad
   scope, default allowlist) returns the spec node as a depth-1 neighbor; the reverse
   traversal from the spec node reaches the finding.
3. **The census numbers move**: that finding node's degree goes 0 → 1; the Knowledge-only leaf
   count (§1) drops by 1 for the replayed record (up to 66 if the whole backfill is replayed
   through the writer).
4. **Idempotent on replay**: replaying the SAME record a second time leaves exactly one edge
   (the `PRODUCED_BY` count for the pair does not grow).
5. **Best-effort is honest**: with the graph client fault-injected, the record emit still
   succeeds (no edge, logged) — the c2 degradation test.

## 6. Interplay with b1 (the expansion-leg prune)

`b1_prune_expansion_rels` prunes `ALLOWED_EXPANSION_RELS` to {writers} ∪ {c1-claimed names}.
**This doc claims `PRODUCED_BY`** (c2 writes it) — it survives the prune, and after c2 the live
server's per-query `UnknownRelationshipTypeWarning` for it disappears. `CONTRADICTS` and
`PRECEDES` remain writer-less and are NOT claimed → b1 prunes them. `AFFECTS` is not claimed →
b1 may prune it (dormant writer, zero live edges). `SUPERSEDES`/`CALLS`/`TESTED_BY`/
`DEFINES`/`CONTAINS`/`IMPORTS` keep their existing writers.

## 7. Out of scope (named, not designed)

- **The other run-outcome members of the same semantic family** — `wave_verdict/v1` records
  (emitted live by `run_workflow.py` at run completion, `repository_id = agentic-dynamics`) cite
  the same spec and are the natural second member; c2 implements the wave-finding producer only.
- **finding→code** — needs code citations added at the record source first (never invented).
- **session-spine records** — cite waves/specs by name in their payload; wait until the
  session/v1 family is publishing to the graph.

---

**Decision: first family = `wave-backfill/v1` finding records → the `spec:<name>` entity they
cite, via `-[:PRODUCED_BY]->`, written producer-side in `kb_backfill_findings.py`'s emit path,
best-effort and MERGE-idempotent; live when the c3 probe's five criteria hold.**
