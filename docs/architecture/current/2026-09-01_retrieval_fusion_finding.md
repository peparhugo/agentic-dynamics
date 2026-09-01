---
status: accepted
---

# Retrieval fusion finding — fused = 0 (the RRF is a union, not a fusion)

**Date: 2026-09-01 · Source: the retrieval-activation census (scripts/fleet/retrieval_census.py,
15 real query strings from committed workflow specs).**

## The measurement

Two census runs over the same query set, same weights (`retrieval-weights/v1`), same stores:

| Run | dense_only | lexical_only | fused | fallback |
|---|---|---|---|---|
| 2026-09-01T022132Z | 70 | 336 | **0** | full × 15 |
| 2026-09-01T023603Z | 549 | 373 | **0** | full × 15 |

Both legs are live and contributing on every query (`fallback_mode: full` — the RRF path
executes). But the same document is NEVER surfaced by both legs: **fused = 0 across all 15
queries** (the dense candidate count tripled between runs as the day's knowledge landed; the
fused count did not move).

## What this means

The RRF fusion currently behaves as a **union with rank arbitration, not a fusion**: the two
stores return disjoint candidate sets, so the fusion weights never get to arbitrate between
competing rankings of the same document. The lexical leg dominates the candidate supply
(336–373 per census vs the dense leg's 70–549); the dense leg adds head candidates the graph
does not index, and vice versa — but a document that both stores know is never ranked twice.

This is not (yet) a quality failure — it may be a healthy two-view system (two representations,
two indexes, disjoint strengths). But it is **unmeasured** in the only way that matters: we
cannot distinguish "the stores index different documents" from "the stores index the same
documents under different ids". The candidate ids are opaque (50-char hashes), the per-leg
attribution is aggregate-only, and no content-hash join exists across the legs — so the
"fused" count cannot rise even when both legs return the same content.

## Hypotheses (to be tested by the fusion-quality campaign)

1. **Id-namespace disjointness**: the dense (Chroma) and lexical (Neo4j) stores assign
   different record ids to the same ingested document (e.g., chroma ids vs neo4j element ids
   vs the knowledge_id), so the same-id fusion check never matches.
2. **Content granularity mismatch**: the two legs index different units (session chunks vs
   knowledge records), so the same underlying text genuinely never appears on both legs.
3. **Content-hash gaps**: the candidates carry no content_hash, so even a same-content join is
   currently impossible — the fusion cannot dedupe by content even where content matches.

## What is already fixed alongside

The census exposed the retrieve latency bottleneck (the cosine-collapse's per-candidate embed
fan-out: 73 sequential HTTP calls ≈ 29s of a 31.5s pass). Fixed with a top-24 cap + an
8-thread pool: **31.5s → 6.2s** (commit `9a4d83623`).

## The gate this opens

`retrieval_fusion_quality` (the follow-up campaign) instruments the per-leg ids + content
hashes, joins them across legs on the census query set, and — if hypothesis 1 holds — dedupes
by content hash before the RRF so same-content documents actually fuse. The measured gate:
**fused > 0 on the same 15-query census set**.

Provenance: [C] computed — `scripts/fleet/retrieval_census.py` over the live Chroma + Neo4j
stores; artifacts `experiments/results/retrieval_census/20260901T022132Z.json` +
`20260901T023603Z.json`.
