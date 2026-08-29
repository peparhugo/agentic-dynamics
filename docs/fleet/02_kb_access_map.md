---
status: proposed
---

# Fleet-ladder KB access map — every knowledge-base touch, read/write, store, guard

**Status: PROPOSED · Date: 2026-08-29T15:35Z · Source: p2_research_kb_access of the
`fleet_ladder_plan` spec (spec_sha256 `0d30d4bc…`).** Bounded to the access map — no
topology proposed. The deliverable is the touch-by-touch table so p4 can place each touch
on a ladder tier **without weakening a guard**.

Ground truth anchors (live, 2026-08-29): the stream `kb:v1:changes` on Redis **db2 / 6380**
(`knowledge_stream.py:47,51,53`); four declared consumer groups
(`knowledge_stream.py:62`); **only `kb-registry-v1` has ever consumed** (22 consumers;
chroma/ledger/neo4j groups idle at `0-0` — see the p1 inventory, K-1). Stores populated by
direct batch producers: chroma 812/2,215; neo4j 33,517 Knowledge nodes.

## 1. Every KB producer (writes to the stream)

| # | touch (call site) | what it writes | when (write-guard env) | read-need | current home | tier candidate |
|---|---|---|---|---|---|---|
| P1 | `runtime/story/persistence.py:197-205` (`save_story_result`) | story records — `story/v1`, MEASURED [M] | `FINOPS_KB_WRITE=1` checked (:199) | none at the same time | host (worker child) | cell |
| P2 | `scripts/run.py:398-412` (`_save_results`) | story records — `story/v1` via `derive_story_records_from_run_output` | `FINOPS_KB_WRITE=1` checked (:402) | none | host (run.py) | cell |
| P3 | `scripts/finalize_reviews.py:74-87` | review records — `review/v1`, ADVISORY [H] | `FINOPS_KB_WRITE=1` checked (:79) | none | host (review) | cell |
| P4 | `scripts/supervise.py:270-291` (`emit_flag`) | flag records — `observation/v1`, ADVISORY [H] | `FINOPS_KB_WRITE=1` checked (:280); best-effort | none | host daemon (supervise) | cell |
| P5 | `scripts/supervise.py:383-407` (`supervise_once`) | observation records — `observation/v1`, ADVISORY [H] | `FINOPS_KB_WRITE=1` checked (:395); best-effort | none | host daemon | cell |
| P6 | `control/orphan_sweep.py:494-508` | observation records | `FINOPS_KB_WRITE=1` checked (:508); best-effort | none | host daemon (orphan sweep) | cell |
| P7 | `scripts/kb_produce.py:128-186` | findings — `measured-finding/v1`, MEASURED [M] | **sets** `FINOPS_KB_WRITE=1` for the run (:186) | none | host (batch) | cell |
| P8 | `scripts/kb_produce_sources.py:101-138,331-333` | code `code/v1` SOURCE [C] · quality `quality/v1` MEASURED [M]/DERIVED [C] · policy `policy/v1` POLICY [P] · spec `spec-lifecycle/v1` | **sets** `FINOPS_KB_WRITE=1` (:333) | none | host (batch) | cell |
| P9 | `scripts/kb_produce_facts.py:1155,1244-1245` | fact records (from the epistemic map) | **sets** `FINOPS_KB_WRITE=1` (:1245) | none | host (batch) | cell |
| P10 | `scripts/kb_produce_campaign_evidence.py:199-253` | report records — `campaign-evidence/v2`, MEASURED [M] | **sets** `FINOPS_KB_WRITE=1` (:253) | none | host (batch) | cell |
| P11 | `workflow_runner.py:772-785` (`_emit_self_finding` → `knowledge_ingestion.py:512-547` `emit_phase_finding`) | finding — `phase-finding/v1`; scoped to `self-<worktree>` (`cell_scope`) | temporary `FINOPS_KB_WRITE=1` for the emit only (`knowledge_ingestion.py:439-440`); gated on `rag_params.emit_self` **default OFF** (`workflow_runner.py:2874`) | **yes** — runs inside `rag_augment` agent phases (reads R1-R4 before emitting) | host (run_workflow) | cell (orchestrator-run agent) |

All producers write via `register_records(…, fail_loud=…)` (`knowledge_stream.py:204`) →
`record_to_event` → `publish_event` (the guarded write path). The write-time registration
sites (P1-P3) are `fail_loud=True` by design (a downed stream raises rather than swallowing
a canonical-state write); the supervisor/daemon sites (P4-P6) are `fail_loud=False` so a
downed DB2 never kills a live assessment pass.

## 2. Every KB consumer (reads the stream, writes a store)

| # | group | what it reads | what it writes | store | guards | status (live) | tier candidate |
|---|---|---|---|---|---|---|---|
| C1 | `kb-chroma-v1` | pointer events | `ChromaStore(knowledge_chunks_v1)` upsert — dense embeddings (`kb_worker.py:336-365`; skips `fact`) | chromadb (8000) | consumer is a READER by default; the only write-back is the flag tombstone, `FINOPS_KB_WRITE`-gated (`kb_worker.py:198,203`) | 0 consumers, `0-0` — **never consumed** (store fed by direct producers) | cell |
| C2 | `kb-ledger-v1` | pointer events | checkpoint-hash HSET — the ledger reducer (`kb_worker.py:228-234`) | Redis db2 (checkpoint keys) | reader default | 0 consumers, `0-0` — **never consumed** | cell |
| C3 | `kb-registry-v1` | pointer events | one compacted line per record, appended to `experiments/results/registry_index.jsonl` + the in-process flag index + the flag auto-clear tombstone write-back (`kb_worker.py:236-334`) | the registry index (append-only) | append discipline (see G4); tombstone write-back `FINOPS_KB_WRITE`-gated (:198) | **22 consumers, live, delivered** (`1787711512064-0`) | cell |
| C4 | `kb-neo4j-v1` | pointer events | `create_knowledge_schema()` + `MERGE (k:Knowledge)` full SET clause + SUPERSEDES/CLEARED_BY/REPLACED_BY edges (`kb_worker.py:367-463`) | neo4j (7474/7687), `knowledge_text_ft` maintained | reader default | 0 consumers, `0-0` — **never consumed**; handler EXISTS (not the "missing consumer"); graph populated by direct producers (33,517 nodes) | cell |

## 3. Every KB read

| # | touch | what it reads | store(s) | guard | current home | tier candidate |
|---|---|---|---|---|---|---|
| R1 | `retrieval.py:849` `retrieve()` — dense leg | `ChromaStore(knowledge_chunks_v1)` query | chromadb (8000) | `scope_excluded` hard per-cell pre-filter (`retrieval.py:395-408,979-983`) | host (workflow runner when `rag_augment`) | cell |
| R2 | `retrieval.py:891-899` `_lexical_leg()` → `graph.py:1271-1285` `search_knowledge_fulltext` | `knowledge_text_ft` full-text over `Knowledge.text` | neo4j (7687) | same scope filter | host | cell |
| R3 | `retrieval.py:276-283` `rrf_base` + `:349-371` `compute_fused_score` | none — in-process fusion of R1+R2 (RRF_K 60.0, weights, multipliers) | in-process | — | host | cell (in-process) |
| R4 | `knowledge/augment.py:106-198` `augment_prompt` + `:201-238` `default_retrieve_fn` (binds ChromaStore + Neo4jClient); wired at `workflow_runner.py:2692-2706` | R1-R3 results → constructed prompt | (via R1-R3) | default **OFF** (`rag_augment`, `workflow_runner.py:2503-2504`) | host | cell (orchestrator-run agent phases) |
| R5 | `control/evidence_analyzer.py:78-86` — graph impact expansion (duck-typed `graph_client` → `Neo4jClient`) | graph neighborhoods / impact edges | neo4j (7687) | a graph error degrades, never blocks (:86) | host (cap_2a-era analyzer) | cell |
| R6 | `control/context_compiler.py:336` + `knowledge/spec_ingestion.py:356` `registry_head` | `registry_index.jsonl` head-resolution for specs | registry index | — | host | cell / orchestrator |
| R7 | `scripts/registry.py:78` `load_registry` + `cmd_show/query/lineage` (:148-259) | `experiments/data_manifest.json` `registry` array (compacted) | manifest | read-only | host CLI | operator tool / supervisor |
| R8 | `apps/control_room/routes/registry.py:20-35` `api_registry` → `_load_registry_cached` + `registry_cli.load_registry` | manifest `registry` array (table + lineage) | manifest | GET only, read-only | Control Room portal (8001) | supervisor-run unit |
| R9 | `scripts/system_snapshot.py:107-111,147-163` — the game board | registry line count + chroma collection counts | registry index + chromadb (8000) | best-effort, never blocks | host snapshot generator | supervisor-run unit |
| R10 | `scripts/bundle_artifacts.py:53,116` | the registry index as the reference set for the bundle check | registry index | read-only | host (release) | operator tool / supervisor |

## 4. The guardrails (exact conditions — p4 must place, never weaken)

| # | guard | exact condition | location | applies to |
|---|---|---|---|---|
| G1 | **WRITE GUARD** | `publish_event` raises unless `authorized=True` **or** `FINOPS_KB_WRITE == "1"` | `knowledge_stream.py:184-186` | every stream write (all producers P1-P11) |
| G2 | **ACTUATION-ARMED** | for `source_type="actuation"`, additionally `armed=True` **or** `FINOPS_ACTUATION_ARMED == "1"` | `knowledge_stream.py:188-191` | actuation events (zero call sites today — `actuation/v1` fires nothing) |
| G3 | **LINEAGE** | an actuation's `causes` must resolve to an observation via `_resolves_to_observation` (`:121-132`), backed by `SOURCE_TYPE_INDEX_KEY` (`kb:v1:source_type_index`, `:76`); non-actuation events populate the index (`:200`) | `knowledge_stream.py:194-198` | actuation events only; the index is written on every other event |
| G4 | **REGISTRY APPEND DISCIPLINE** | one compacted line per record appended to `registry_index.jsonl`, **never rewritten in place**; `generate_manifest.py:51-121` compacts to one row per `entity_id` (latest-per-entity, `lifecycle_state` derived) | `kb_worker.py` registry handler + `generate_manifest.py` | the registry index (C3) |
| G5 | **SCOPE DISCIPLINE (two-channel)** | per-cell `repository_id` = `self-<worktree>` (`workflow_runner.py:741-750`); explicit non-empty `repository_id` = shared-scope override; empty never means global; `retrieval.py:395-408` hard-excludes out-of-scope candidates | `workflow_runner.py` + `retrieval.py` | retrieval reads R1/R2 and the emit P11 |
| G6 | **CONSUMER READ-ONLY DEFAULT** | a kb consumer is a READER of the stream; the only write-back (the flag auto-clear tombstone) requires `FINOPS_KB_WRITE=1` | `kb_worker.py:198,203` | the consumers C1-C4 |

## 5. The unmapped list

After the enumeration above: **empty** — 11 producers (P1-P11), 4 consumers (C1-C4), 10
reads (R1-R10), 6 guards (G1-G6) = **31 touches mapped**, each to a store, its guard, its
current home, and a tier candidate. No KB touch found outside this map. The p4 proposal
must assign every row a tier without weakening G1-G6; the two live-consume anomalies
(chroma/ledger/neo4j groups never delivered — C1/C2/C4) and the direct-producer stores are
the proposal's open reconciliation items (p1 inventory K-1/K-2).

**LOG (p2):** 31 touches mapped (11 producers, 4 consumers, 10 reads, 6 guards); unmapped
list empty; the four groups verified against `knowledge_stream.py:62`; the write guard,
actuation-armed gate, lineage, and append discipline pinned to their exact conditions for
p4's guard-placement table. **PASS** — access map committed.
