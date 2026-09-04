---
status: accepted
kind: evidence
spec: graph_leg_closeout
phase: c3_assoc_probe
run: run-57b8ec179e30
generated_at: 2026-09-04T03:45:00Z
---

# graph_leg_closeout — associative first-family live probe (c3)

**Live evidence that the associative first family is real**, per the c1 doc's probe criteria
(`docs/designs/current/graph_leg_associative_edges.md` §5). Exactly ONE real corpus record was
replayed through the c2 writer (`Neo4jClient.merge_wave_finding_produced_by` at
`416b863b0`) — the single write the c1 doc authorizes. Everything else is read-only
`MATCH`/`RETURN`. Probe run from the c2 worktree against the live kb-neo4j leg
(`bolt://localhost:7687`, kb-neo4j-v1 lag 0) and the machine-local corpus at the main checkout.

## The replayed record (real, not synthetic)

| Field | Value |
|---|---|
| Wave | `admission_leases` (a completed wave with a real adversarial/ledger conclusion) |
| knowledge_id | `bf82d637d75c72f14a13e22dd761c859b186a9a1505c2b0666ae21ecafcc45fc` |
| locator / target | `wave:admission_leases` → `spec:admission_leases` |
| Replay identity check | the record was re-derived with `kb_backfill_findings.derive_wave_record` and its `knowledge_id` EQUALS the id already registered in `registry_index.jsonl` — so this is a byte-identical REPLAY of an existing record, never a new fabrication |
| Spec target | a `current` graph spec node exists (`spec:admission_leases` — 4 duplicate current copies, the pre-existing condition c1 §4.3 recorded) |

## Census BEFORE the replay

```
Knowledge-only nodes (any degree)      : 4199
Knowledge-only LEAF nodes (degree 0)   : 4199
chosen finding node degree             : 0
PRODUCED_BY edges in the whole store   : 0        # the family had no edges at all
chosen finding node's PRODUCED_BY edges: 0
```

## Replay #1 — the c1-doc-authorized write

```
writer status: edge_merged
edge now      : 1      (finding node degree 1)
```

Query (the writer's single statement, abridged): `MATCH (s:Knowledge {entity_id:
'spec:admission_leases', source_type:'spec', lifecycle_state:'current'}) WITH s ORDER BY
coalesce(s.indexed_at,'') DESC, s.knowledge_id DESC LIMIT 1 MERGE (f:Knowledge
{knowledge_id:$fid}) SET <record provenance> MERGE (f)-[:PRODUCED_BY]->(s) RETURN count(s)`.

## Replay #2 — idempotency

Replaying the SAME record a second time: `edge now: 1` — exactly one edge, no duplicate
(MERGE on the deterministic `(knowledge_id, spec entity)` pair).

## (a) the record's node carries the edge to its cited target

```
MATCH (f:Knowledge {knowledge_id:$fid})-[r:PRODUCED_BY]->(s:Knowledge)
RETURN type(r), s.entity_id, s.source_type, s.lifecycle_state, f.entity_id

rel        : PRODUCED_BY
target     : spec:admission_leases
target st  : spec        target lifecycle_state: current
source fe  : c5e05cdf271eb2000c2fbb9c88ecda6dcba4a34cf8b75ac882bca7be99f8f87a
```

## (b) traversal FROM the record reaches the spec — the leaf property is broken

Forward (depth-1 `expand_candidates` from the finding node, broad scope, default allowlist):

```
expansion nodes: 2   depth: {0, 1}
PRODUCED_BY depth-1 neighbor: {entity_id: spec:admission_leases,
                               source_type: spec, logical_locator: admission_leases}
```

Reverse (depth-1 from the SPEC node the writer pinned — its knowledge_id
`8011631b84a95c0e61b3ea6de20dcd1b0730fbbc50e50b754f01ca5f1ecd9f60`):

```
reverse spec -> finding reached: True
neighbor: {knowledge_id: bf82d637…, source_type: finding, logical_locator: wave:admission_leases}
```

Probe note: `spec:admission_leases` has 4 duplicate `current` copies in the live graph (the
pre-existing spec-lifecycle condition c1 §4.3 documented). The reverse probe must seed from the
pinned copy that actually carries the edge (the one the writer chose by newest `indexed_at`);
seeding from an arbitrary duplicate (e.g. an unordered `single()` over the 4) returns a copy
without the edge. This is a property of the duplicate-spec condition, NOT of the family — the
edge is exactly one and points at exactly one (the newest) spec copy.

## (c) the census numbers moved

```
Knowledge-only LEAF nodes: 4199  ->  4197     delta -2
chosen finding node degree:   0  ->    1
PRODUCED_BY edges store-wide: 0  ->    1
```

The delta is **2, not 1**, because BOTH endpoints of the first edge were leaves: the finding
record AND the spec hub each leave the degree-0 set. Every further finding edge to the SAME hub
drops the leaf count by 1 (only the finding leaves; the spec is already non-leaf) — so c1 §5.3's
"drops by 1 per replayed record" describes the per-record marginal once the hub is connected;
the first edge lifts two leaves. The family is live: exactly one real `PRODUCED_BY` edge exists
in the store, joining a real wave-conclusion record to its real spec.

## Bonus — the b2 residual warning is gone

The b2 probe recorded one remaining `UnknownRelationshipTypeWarning` (PRODUCED_BY) before c2
ran. Now that the first PRODUCED_BY edge exists, its rel-type token is in the store — the
expansion query over the finding seed returns **0 server notifications** (the post-b1 7-rel
union is fully warning-free, closing b2's documented residual).

## Verdict

| c1 §5 criterion | Result |
|---|---|
| 1. One real record replayed through the writer → exactly one edge to `spec:<name>` | **PASS** — `edge_merged`; edge count 1 |
| 2. Traversal breaks leaf-ness (record → spec; reverse reaches the finding) | **PASS** — depth-1 expansion from the record returns the spec; reverse from the pinned spec copy returns the record |
| 3. Census numbers move (leaf count drops by the family's records) | **PASS** — leaf count 4199 → 4197 (−2: both endpoints were leaves; per-further-record marginal −1), finding node degree 0 → 1 |
| 4. Idempotent on replay | **PASS** — replay #2 leaves exactly one edge |
| 5. Best-effort honest | **PASS** (established by c2's tests: outage → `skipped`, logged, emit succeeds) |

**c3 verdict: PASS** — the associative first family is live in the graph with one real,
idempotent, traversable `PRODUCED_BY` edge from a real wave-conclusion record to its real spec
entity, and the leaf-node property is broken for the family as designed. Scope fence honored:
evidence + the single authorized replay only — no further code changes (none needed).
