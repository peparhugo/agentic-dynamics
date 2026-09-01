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

## p1 measurement (the fusion-quality campaign) — the join answer + hypothesis verdict

**Instrument landed.** `Candidate` now carries `join_content_hash` (the sha256 of the stored
text, derived identically on both legs via `knowledge.compute_content_hash`) + a `legs`
property (`dense` / `lexical` / `both` / `expansion`), and `RetrievalAttempt.leg_overlap()`
answers the content join per query (artifact persisted in `RetrievalAttempt.to_dict()`).
The census rows carry per-candidate legs + content hashes, and `content_join_totals` +
`hypothesis_split` report the answer over the whole set. The join is observational only:
`join_content_hash` never feeds `deduplicate`/`collapse_redundant`/fusion, so the fusion-off
path is byte-identical (no-regression). Artifact:
`experiments/results/retrieval_census/20260901T035547Z.json`.

**The join answer.** Across the same 15-query census set (same weights `retrieval-weights/v1`,
same stores): **fused = 0, content_pairs = 0, distinct_content_hashes = 0.** Not one dense
candidate shares a content hash with a lexical candidate — including after deriving the text
hash on the lexical leg, where the store does not persist it.

**Per-hypothesis split:**

| Hypothesis | Verdict | Measured basis |
|---|---|---|
| 1. Id-namespace disjointness | **FALSE** | The stores share the id namespace: all 812 `knowledge_chunks_v1` ids exist in Neo4j under the SAME `knowledge_id` with byte-identical text (812/812). A same-content pair carries the same id, so the id-based fusion check would fire if the same record co-surfaced — it never does. |
| 2. Content granularity mismatch | **TRUE (as a two-view ranking divergence)** | 0 same-content pairs in the fused candidate sets. The stores hold the same units (deep overlap: 437/812 id overlaps at full depth for `context_abstraction_implement`, all with identical text) — but the top-40 semantic and top-40 full-text sets never intersect on any of the 15 queries. The disjointness is in the per-query top-K selection, not in the indexed units. |
| 3. Content-hash gaps | **PARTIAL (present, not causal)** | The dense leg persists `content_hash` for all candidates (549/549); the lexical leg persists it only for `code` records (32,001/33,961 nodes — the kb-neo4j-v1 SET clause omits `content_hash` for findings/story/review/observation/spec). Closing the gap (deriving the text hash) does not change the join answer: still 0 pairs. |

**Verdict (the campaign's deliberate outcome).** The join does NOT warrant a content-hash dedupe
before the RRF: there are 0 same-content pairs to merge, and forcing a merge would be a no-op on
genuinely distinct-per-query candidate sets. The campaign takes the hypothesis-2 path: the two
legs are a healthy two-view system at the fusion cutoff (semantic top-K vs lexical top-K rank
the shared corpus disjointly), and **fused = 0 is the documented, deliberate two-view outcome** —
not a defect to be "fixed" by a merge that nothing would join.
