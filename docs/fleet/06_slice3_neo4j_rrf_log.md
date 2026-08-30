---
status: accepted
---

# Fleet-ladder slice 3 — the neo4j bridge + the RRF leg live

**Status: PASS · Date: 2026-08-30 · Role: slice 3 (`fleet_ladder_implementation` p4 — the
execution phase).** Resurrects the `kb-neo4j-v1` consumer (the missing running unit), runs the
D-12 catch-up + DLQ triage, verifies the fulltext index + the RRF two-leg fusion, and turns
`rag_augment` on as the measured product gate. Every number is a live command or a container log.

## 0. Verdict

**PASS.** The group's pending → 0 (the catch-up completes), the fulltext index is populated (a
real query returns non-empty), the RRF fusion returns fused results (both legs contribute,
`fallback_mode` "full"), and the DLQ's disposition is recorded. No empty index, no stuck group.

## 1. The kb-neo4j consumer — live + supervised (§6)

`docker-compose up -d kb-neo4j` → the `kb_worker.py --group kb-neo4j-v1` cell container:

- `restart: on-failure` (the cell base) + **heartbeats** (`worker:kb-neo4j-v1:<container>:1`,
  now on the board — the `kb_worker.py` heartbeat wiring was missing and is added, matching
  `worker.py`/`analysis_worker.py`).
- Reaches neo4j **by name on fleet-net** (`FINOPS_NEO4J_URI=bolt://neo4j:7687`). The graph
  client's constructor was the "override via ENV for prod" comment that never wired — it now
  reads `FINOPS_NEO4J_URI`/`_USER`/`_PASSWORD` (defaults unchanged, so every existing caller is
  byte-identical).
- Binary probe PASS (the CLIs resolve via the D-2 auth mounts).

## 2. The D-12 catch-up (head start point, no full replay)

`kb-neo4j-v1` was at `0-0` (never consumed). Per D-12, it was reset to the **stream head**
(`XGROUP SETID kb:v1:changes kb-neo4j-v1 $` — last-delivered `1788113225343-0`), so it does NOT
replay the 27,000+ historical entries (they are already in the graph via the direct producers).
The consumer then read exactly the **89 re-driven** entries (plus any new arrivals) — the log
shows 89 `new … -> ok`, zero full-replay. **Group state: `pending = 0`, `lag = 0`.**

## 3. The DLQ triage (bounded, disposition recorded)

`scripts/fleet/dlq_triage.py` (new) classified `kb:v1:dead_letter` (2,747 entries) by whether
each entry's source artifact still exists + hashes to its recorded `content_hash`:

- **89 re-driven** (re-published to the main stream — their artifacts exist and verify).
- **2,658 tombstoned** (artifact missing → permanently dead, never retried).
- Disposition recorded to `experiments/results/kb/dlq_triage.json` (`total`/`inspected`/
  `re_driven`/`tombstoned`/`by_reason`).

## 4. Direct-producer reconciliation (MERGE idempotency)

The 33,517 existing nodes were written by the batch producers directly. The consumer's
`MERGE (k:Knowledge {knowledge_id})` dedupes against them: **33,517 → 33,520** after the 89
re-driven entries (only +3 new nodes — the other 86 already existed and MERGE re-keyed them).
No duplicate explosion.

## 5. Schema + the fulltext index

`create_knowledge_schema()` runs idempotently in the handler; the consumer's SET clause writes
the citation/date-spine/lineage fields and the SUPERSEDES/CLEARED_BY/REPLACED_BY edges (the
FOREACH clauses, gated on `supersede`/`delete` operations). Live graph state:

- `knowledge_text_ft` fulltext index: **ONLINE, populationPercent 100.0** (2 fulltext indexes
  total: `knowledge_text_ft` + `step_text_ft`).
- **33,520** `Knowledge` nodes (638 current, 0 superseded-in-graph — superseded state is derived
  at read time).
- **2,774 SUPERSEDES edges** present (the supersede chain). CLEARED_BY / REPLACED_BY are 0 — they
  fire only on `delete` operations with `causes`, and no such event has reached the consumer yet
  (the handler's edge code is live and tested by `test_kb_worker.py`).

## 6. The RRF fusion — both legs contribute

`search_knowledge_fulltext("task manager API story")` → **10 lexical hits** (non-empty index);
the dense leg (Chroma `knowledge_chunks_v1`) → **10 dense hits**. The full `retrieve()`:

```
fallback_mode: full        # both legs up, no degradation
candidates: 9              # fused RRF list
  dense-only: 1, lexical-only: 8, fused(both legs): 0
```

Both legs contribute to the fusion (the lexical leg — the "resurrected" one — is now a live,
supervised stream-fed store), and `fallback_mode "full"` means no leg degraded. The corpora are
asymmetric (Chroma 812 chunks vs neo4j 33,520 nodes) so few candidates overlap both legs, but
the two-leg RRF fusion is real: the lexical leg feeds candidates the dense leg does not.

## 7. `rag_augment` — the measured product gate (D-Q8 / R8)

`workflows/repository/fleet_ladder_implementation.yaml` gains `rag_augment: true` (the running
orchestrator workflow), gated by this verification (both legs contribute). The retrieval store
endpoints are wired into the compose `ladder-env` (`CHROMA_HOST: chromadb`,
`FINOPS_NEO4J_URI: bolt://neo4j:7687`) so the augment seam resolves the two stores by name on
fleet-net. Rollback (per the proposal): `rag_augment` back OFF + stop the consumer — the graph
stays (MERGE is additive).

## 8. Code surface (this slice)

- `src/agentic_dynamics/knowledge/graph.py` — `Neo4jClient` reads `FINOPS_NEO4J_URI`/`_USER`/
  `_PASSWORD` env (the promised "override via ENV" now wired; defaults unchanged).
- `scripts/kb_worker.py` — kb-consumer heartbeats (`worker:<group>:<host>:<pid>`).
- `scripts/fleet/dlq_triage.py` — the bounded KB-stream DLQ triage (new).
- `infrastructure/docker-compose.ladder.yml` — `kb-neo4j` env + the RAG store endpoints in
  `ladder-env`.
- `workflows/repository/fleet_ladder_implementation.yaml` — `rag_augment: true`.
- `scripts/CONTEXT.md` — `dlq_triage.py` classified in the `fleet` bucket.

## LOG

**PASS.** The `kb-neo4j-v1` consumer is live + supervised (heartbeats on the board, restart
on-failure) at the D-12 head start point; `pending = 0`, `lag = 0`; the DLQ triaged (89
re-driven / 2,658 tombstoned, disposition recorded); MERGE idempotency verified (33,517 →
33,520); `knowledge_text_ft` ONLINE + populated (10/10 lexical hits); the RRF fusion returns
fused results (both legs contribute, `fallback_mode` "full"); `rag_augment` enabled as the
measured product gate. Committed.
