---
status: accepted
---

# Retrieval Agenda - 2026-09-01

**Status: PASS - p1 agenda reconstruction only.** This document reconstructs the deferred
retrieval work from the surviving record. It does not decide D1/D2, implement the pattern
projection, or turn on a new measurement run. No source files or existing documents were changed
for this phase.

## 1. Why This Agenda Exists

The 2026-08-30/31 session left a retrieval follow-up, but its working notes were lost during
session compaction. The durable record is the contract for the follow-up:

- `HANDOFF.md` records the completed fleet and measurement work, the live machine state, and the
  next-move pattern. It does not contain a retrieval-specific decision record.
- `docs/architecture/current/visibility_matrix.md` records the unresolved visibility decisions,
  especially D1 (agent access to facts) and D2 (pattern projection).
- `docs/fleet/06_slice3_neo4j_rrf_log.md` records the slice-3 RRF and Neo4j product-gate claim.
- `docs/fleet/07_slice4_guards_log.md` records the slice-4 audit-guard suite and its result.
- The retrieval and augmentation module docstrings define the implemented runtime boundaries and
  failure behavior.

The agenda below separates recorded historical claims from claims verified against the current
tree. A live-service claim is not upgraded to current measured evidence merely because a log says
that it passed.

## 2. Reconstructed Sequence

The deferred sequence is:

1. Reconstruct the agenda from the durable record.
2. Decide D1 and D2 without violating the two-channel rule.
3. Implement a retrieval-facing projection of the typed `PatternPayload`, if the decision is
   ratified.
4. Activate the RRF plus augmentation path as a measured gate: measure leg contribution and
   fallback modes, verify index health, and run one real augmented workflow phase.

This is the sequence named by the `retrieval_activation` workflow's phases. The present document
delivers only step 1.

## 3. What Was Promised

### Slice 3: the product gate

The slice-3 log promises all of the following:

- The `kb-neo4j-v1` consumer is live and supervised, catches up from the D-12 stream head, and
  reaches `pending = 0` and `lag = 0`.
- The Neo4j `knowledge_text_ft` full-text index is online and populated over `Knowledge.text`.
- Dense Chroma retrieval and lexical Neo4j retrieval both contribute to the RRF result, with
  `fallback_mode = "full"`.
- `rag_augment` is turned on as the measured product gate, with rollback defined as turning it back
  off and stopping the consumer.

The operational meaning of the gate is not just "the stores answer a demo query." It is a
measured pass over retrieval quality and augmentation behavior: leg contributions, named fallback
modes, and a prompt-construction path that does not block the phase when infrastructure fails.

### D1 and D2: the visibility decisions

The visibility matrix leaves two related cells open:

- **D1 - agent access to facts:** whether an agent session may retrieve facts at all.
- **D2 - pattern projection:** how I9 patterns become visible to retrieval if D1 permits a
  restricted form of access.

The matrix records three D1 choices:

- **Option A, status quo:** agents retrieve knowledge records; facts remain for rules and are not
  retrieved by agents.
- **Option B, recommended:** agents retrieve compressed, uncertainty-carrying, citable patterns,
  but never raw facts.
- **Option C, rejected direction:** agents retrieve full facts, including attempt-level and
  predicate-level rows. This undermines the two-channel rule and invites stale or unsorted control
  truth into prompts.

The matrix's D2 recommendation is the projection required by D1 Option B: a read-only knowledge
  record with `source_type = "pattern"`, the `PatternPayload` as its body, DERIVED authority and
  `[C]` evidence class, retrievable through the existing Chroma plus Neo4j RRF path. It is a view of
  a pattern fact, not a second fact-store row.

### Slice 4: the audit guards

The slice-4 log promises seven read-only guard families:

1. Compose mount and Docker-socket contract.
2. Fleet health: worker heartbeats and per-queue dead-letter counts.
3. Neo4j index: `knowledge_text_ft` covers `Knowledge.text`, and the KB consumer writes text
   while skipping fact rows.
4. Single write-back: only `kb-registry` carries `FINOPS_KB_WRITE=1`; no service arms actuation.
5. Binary resolution probes fail loudly for missing or non-executable launchers.
6. Scope vocabulary and authorization checks.
7. Network policy: fleet-network attachment and forbidden-port restrictions.

The log reports 22 tests and a green deterministic suite, plus a live external check for a
populated index and a caught-up consumer group. The retrieval activation agenda narrows the
relevant follow-up to the Neo4j index-health evidence and the product proof; it must not silently
drop the other guard families when claiming the full slice-4 result.

## 4. What Exists Now

### Verified in the current tree

- `src/agentic_dynamics/knowledge/retrieval.py` has two ranked retrieval legs: dense Chroma and
  lexical Neo4j full-text. The legs run in parallel, candidates merge by canonical id, and
  `rrf_base()` adds the weighted contribution from each surviving leg. Graph expansion is a
  bounded, decayed boost after fusion, not a third ranked peer.
- The retrieval implementation names degradation as `full`, `lexical_graph_only`,
  `dense_local_exact`, or `no_rag`. `RetrievalAttempt` records ranks, raw scores, selected
  evidence, token count, latency, dedup path, weights version, and fallback mode before the LLM
  call.
- `src/agentic_dynamics/knowledge/augment.py` contains the read-only
  `retrieve -> construct -> render` seam. Retrieval and construction failures return the base
  prompt with a named fallback mode; the seam does not write to the knowledge base.
- `src/agentic_dynamics/runtime/workflow_runner.py` resolves augmentation from an explicit
  argument, then `workflow.params.rag_augment`, then `False`. Therefore the seam is default OFF,
  although a workflow may opt in. Test phases bypass it.
- `PatternPayload` exists as a frozen typed payload in `control/facts.py`, and
  `control/reducers/pattern.py` deterministically encodes it into a canonical `pattern` fact.
  The reducer carries claim, population, conditions, support, uncertainty, validity window, and
  source experiment.
- The current knowledge source-type vocabulary contains `fact` but not `pattern`. The KB
  consumers skip `source_type = "fact"`, and the retrieval path consumes knowledge records rather
  than fact-plane rows. No current `source_type = "pattern"` projection was found, and
  `retrieve()` has no pattern projection input or candidate surface.
- `tests/test_fleet_guards.py` exists with the seven guard families and an external
  `test_neo4j_index_populated_and_group_caught_up_live` check. This verifies that the guard code is
  present; it does not itself establish that the external check passed today.

### Not yet established as current measured evidence

- The slice-3 log's live counts, non-empty store responses, and two-leg contribution are historical
  operational evidence. Static inspection cannot reproduce Chroma, Neo4j, Redis, or the container
  fleet.
- The tree contains a workflow configuration with `rag_augment: true`, and the slice-3 log says
  the product gate was enabled. The current tree does not prove a successful augmented workflow
  phase, its fallback census, or acceptance of its constructed prompt. That proof remains an
  explicit p4 deliverable.
- The external guard's source asserts a live full-text hit and separately documents the pending
  group expectation, but the deterministic test does not establish a live equivalence between
  `populationPercent` and stream pending state. That equivalence needs to be measured in the
  activation run.
- The slice-4 historical total of 2,201 passed tests is a log result, not a result of this p1
  reconstruction. It is not re-reported as a fresh run here.

## 5. Decision Inputs And Boundaries

The decision boundary is deliberately asymmetric:

- Agents may receive narrative knowledge records and, if D1=B/D2 is ratified, compressed
  patterns with uncertainty and citations.
- Controllers consume raw facts by declared address through the fact/context contracts.
- Raw facts do not become RRF candidates. A pattern projection must not duplicate the fact-store
  row or turn an LLM summary into canonical control truth.
- Pattern records must retain repository and cell scope, deterministic lineage, and enough source
  information for an agent to cite the underlying experiment.
- `ADVISORY` remains uncitable under C5. A reducer-minted pattern is a derived `[C]` record only
  if its support and uncertainty come from real measured inputs.

The recommended path carried forward from the matrix is **D1 Option B plus the D2 pattern
projection**: agents read what the system learned, while controllers consume what the system has
measured as control truth. This is a recommendation for the next decision phase, not a decision
made by this agenda.

## 6. Acceptance Criteria For The Deferred Work

The next phases should not call retrieval "activated" until all of these are recorded:

- D1 and D2 have a signed decision record, including the consequences for the two-channel rule.
- A deterministic, scoped, idempotent pattern projection carries `PatternPayload` without putting
  raw fact rows in either index.
- Pattern and ordinary knowledge candidates can be fused and selected without changing the
  projection-off behavior; uncertainty is preserved in the candidate and citation path.
- A retrieval census reports dense-only, lexical-only, and fused contributions, plus the
  `fallback_mode` distribution and the active `WEIGHTS_VERSION`.
- The Neo4j index-health guard and its stream-catch-up evidence pass against the live services.
- One workflow phase runs with `rag_augment` enabled, records retrieval and constructor outcomes,
  and either accepts the augmented prompt or records the named fallback without blocking the
  phase.

## LOG

**PASS.** The deferred agenda was reconstructed from the surviving record. Reconstructed items:
the slice-3 two-leg RRF and `rag_augment` product-gate promise; D1 options A/B/C; D1's recommended
Option B; D2's retrieval-facing `PatternPayload` projection; and the seven slice-4 guard families.

**Verified against the current tree:** two-leg RRF retrieval and named fallback modes exist;
the retrieve/construct/render seam exists and is default OFF; `PatternPayload` and its deterministic
fact reducer exist; no retrieval-facing `source_type = "pattern"` projection exists; and the
slice-4 guard tests, including the external Neo4j check, are present.

**Unverifiable without a live run:** the historical slice-3 service counts and leg contribution;
whether an augmented workflow phase has successfully run and been accepted; the current
fulltext-population/stream-pending equivalence; and the historical 2,201-test total as a fresh
result.

This pass intentionally leaves code changes, D1/D2 ratification, pattern projection, and measured
activation to the subsequent phases.
