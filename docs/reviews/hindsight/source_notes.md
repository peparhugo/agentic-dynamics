---
status: accepted
---

# Hindsight source notes — load-bearing excerpts by subsystem

Source: `vectorize-io/hindsight` @ `a7eafb2f395b3c905e9e577da691414d3ca8d08c` (MIT). Paths below are
relative to the clone. Quotes are verbatim; surrounding prose is ours. **Not a substitute for the
source** — where the dive needs more than this dossier carries, the gap is named, never invented.

## 0. Layout

- Server: `hindsight-api-slim/hindsight_api/` (≈920 modules; `hindsight-api` is a meta-package
  pinning `hindsight-api-slim[all]`). Engine: `engine/{retain, consolidation, memories, search,
  reflect, directives, transfer, storage, db, providers, parsers, sql}` with
  top-level helpers (`mental_model_refresh.py`, `query_analyzer.py`, `cross_encoder.py`,
  `entity_resolver.py`, `fact_budget.py`, `graph_maintenance.py`, `vector_index_health.py`,
  `loop_watchdog.py`, `cancellation.py`, `tracing.py`, `metrics*.py`).
- Also: Next.js `hindsight-control-plane`; `hindsight-dev/benchmarks/{consolidation,
  document_evolution,micro,multimodal_retain,obs,perf}`; `hindsight-system-evals`; ~40 integrations
  incl. `hindsight-integrations/opencode` and `coding-agents/` (with e2e Dockerfiles).
- Repo culture: `AGENTS.md` → `CLAUDE.md` (agent-facing conventions), like ours.

## 1. Structured document — markdown as a deterministic render (`engine/reflect/structured_doc.py`)

> Storing mental models as raw markdown forces every refresh to round-trip prose through an LLM,
> which then drifts on stylistic details (numbered vs bulleted lists, casing, separator lines,
> paraphrasing) even when instructed to preserve content byte-for-byte. The intrinsic mechanism of
> an LLM is to *generate* the next token from a gestalt of the input — not to copy tokens verbatim —
> so any "preserve unchanged content" instruction is fundamentally a soft constraint.
>
> The fix is to give the LLM no opportunity to drift on unchanged content. The structured document
> is the *source of truth*; the markdown stored in `mental_models.content` is a deterministic render
> of it.

Schema v2: an ordered list of `Section`s (`id` = stable slug from `heading`; renames keep the id) and
`Block`s (`id` + a **verbatim markdown fragment**: one paragraph, list, table, or code fence —
"never interpreted: stored as written and rendered as written"). v1 modelled blocks as a typed
union and *parsed* markdown into it; every construct the union could not express (nested lists,
blockquotes, hard breaks, table alignment, …) "collapsed into a paragraph whose lines were joined
with spaces" and was a fixed point — an abandoned design worth citing before anyone models prose as
a typed AST.

## 2. Delta operations (`engine/reflect/delta_ops.py`)

Two validation layers, two answers:

> - **Shape** (`parse_delta_operation_list`): does the reply match the schema? One op that does not
>   refuses the whole reply, and `request_delta_operations` asks the model again with the errors
>   quoted back.
> - **Reference** (`apply_operations`): does the op name something real? An unknown `section_id` or
>   `block_id`, or a block that lives in a different section, is **dropped** with a debug-friendly
>   reason and the rest still apply — the model addressed a document it misread, which the next
>   refresh sees afresh.

> Sections and blocks not mentioned by any op are physically copied through unchanged — there is no
> LLM-mediated re-emission of unchanged text, so prose drift is structurally impossible.

> Why blocks are addressed by id and not by index (#3273): An index has to be *counted* by the
> model, and an off-by-one is still in range, so it silently overwrites an unrelated block and is
> recorded as a success — no length change for a shrink guard to notice. An id is copied, not
> derived; a wrong one does not resolve and is skipped and reported.

Operations: `add_section`/`remove_section`/`rename_section`/`replace_section_blocks`/
`append_block`/`insert_block`/`replace_block`/`remove_block`. "Failure modes are by design
conservative: … the document stays as-is. The structure can only get better or stay the same per
refresh, never get worse." Zero ops → identical doc; operations are auditable (a log of exactly what
changed).

## 3. Mental-model refresh (`engine/mental_model_refresh.py`, 368 lines)

- Dry-run: "the production refresh pipeline with exactly two writes skipped — the content … and the
  watermark"; nothing persisted; **the same LLM calls** (costs the same); "a dry run you can
  configure stops predicting the refresh it exists to predict".
- Watermark: the recorded `last_memory_seen_at` is "the newest in-scope memory visible at" the
  snapshot — a write landing mid-refresh stays newer and is caught next round.
- Fallback reasons (enumerated): `no_baseline_content`, `source_query_changed`,
  `structured_doc_unreadable`, `delta_ops_failed`, `delta_ops_all_skipped`.
- Trace (`keep_trace`): per-refresh `effective_mode`, `mode_fallback_reason`, `outcome`
  (`content_written`, `content_preserved_no_new_facts`, `refresh_failed_*`), `tool_calls[]` (tool,
  reason, input, result_count, duration_ms, iteration), `llm_calls[]`, `delta_operations`, `usage`.
- Staleness gate: no in-scope write since last refresh → no LLM call, nothing spent; **deletions are
  invisible** to it (named limitation).

## 4. Consolidation — a decision engine with enforced epistemics

`engine/consolidation/consolidator.py` (3,763 lines) + `prompts.py` (240). Observations are stored
as rows in `memory_units` with `fact_type='observation'` (`proof_count`, `source_memory_ids`, a
JSONB `history`); mental models live in their own table. The LLM returns
`{"creates": [], "updates": [], "deletes": []}`, **every entry carrying a required `reason`**;
"AT MOST ONE UPDATE PER `observation_id`" (duplicate updates would silently overwrite); a `deletes`
entry without the exact observation id is rejected **and rejecting it discards the whole response**.

`prompts.py` — the DECISION GUIDE's rules, verbatim fragments:

> 1. PREFER UPDATE OVER CREATE … One canonical observation with many source facts is always better
> than many siblings with one source fact each. … CREATE is the correct default for any structurally
> distinct event, claim, or pattern that has no existing match.
> 2. ONE OBSERVATION PER DISTINCT FACET … 3. MATCH BY ENTITY/FACET, NOT TOPIC … 5. CASCADE TO ALL
> AFFECTED OBSERVATIONS … 7. PRESERVE HISTORY: … never DELETE them. Be very conservative with
> deletes.
> 8. NO COMPUTATION: you do not have the full picture — never calculate, derive, or adjust numeric
> values. If the user says "I have 2 dogs" and then "I have a dog named Rex", do NOT update the
> count to 3 — you don't know if Rex is one of the 2 or a new one. … Synthesize and consolidate what
> was stated, but never do arithmetic or logical deductions.
> 9. KEEP DISTINCT TOPICS DISTINCT …

Also: near-duplicate reconciliation (cosine threshold, default 0.97, Postgres-only);
`observation_scopes` (targeted consolidation); `observations_mission` (shape what gets synthesised);
deletes cascade to derived observations and reset survivors for re-consolidation.

## 5. Retrieval (`engine/search/`, `engine/query_analyzer.py`)

- `retrieval.py` — 4-way parallel: semantic, BM25, graph (pluggable `GraphRetriever`; default
  `LinkExpansionRetriever`), temporal; per-fact-type results; `min_semantic`/`min_keyword` floors.
- `fusion.py` — `reciprocal_rank_fusion(..., k: int = 60)` ("score(d) = sum_over_lists(1/(k+rank))")
  **and** `interleave_fusion` (round-robin), whose docstring names RRF's failure mode: a
  unique-but-important result reached by a small arm "so RRF drops it below" — the interleave exists
  for dedup-style recall.
- `query_analyzer.py` — temporal extraction; a false-positive date window is "worse than none,
  because the constraint is non-null so nothing downstream can tell extraction failed"; relative
  expressions anchor to **UTC, not the server's local wall clock** ("a window built from local
  midnight names a different day for part of every day").

## 6. Reflect agent (`engine/reflect/agent.py` ≈2,084 lines; `tools_schema.py`)

Tools, in priority order (schema text):

> 1. `search_mental_models` — User-curated stored reflect responses (highest quality, if applicable)
> 2. `search_observations` — Consolidated knowledge with freshness awareness … "If an observation is
> STALE, you should ALSO use recall() to verify with current facts." "IMPORTANT: If
> search_mental_models is available, you MUST call it FIRST before using this tool."
> 3. `recall` — Raw facts (world/experience) as ground truth fallback
> 4. `expand` (memory ids from recall) · 5. `done`

Budgeting: per-tool token ceilings "tightened by what is left of the context budget", with a floor —
"an unusable tool result is worse than the round-trip"; parallel calls bounded so they cannot
overshoot; named failure modes (finished without an answer; never produced a tool call).

## 7. Retain (`engine/retain/`)

`fact_extraction.py` — LLM extraction of "semantic facts, entities, and temporal information"
(world/experience fact types; entity labels; links; embeddings via a coalescing/processing pair);
`fold.py`, `attachment_store.py`, `memory_budget.py`, `orchestrator.py`. Retain is the only place
raw content becomes facts; observations are then derived by §4.

## 8. Operational surface (one line each)

`loop_watchdog.py`, `loop_lag.py`, `liveness.py`, `cancellation.py`, `tracing.py`, `metrics*.py`,
`vector_index_health.py`, `bank_attribution.py`, `cache_affinity.py`, `db_budget.py`, `fact_budget.py`
— a production memory service budgeted, watched, and traced at every seam.

## 9. Docs-site deltas the pages added (not in the clone scan)

Hierarchical retrieval priority; triggers (`refresh_after_consolidation` XOR `refresh_cron`) with
coalescing + `min_refresh_interval_seconds` ("a burst of twenty retains costs one refresh", parked
with `next_retry_at`); two timestamps (`last_refreshed_at` wall-clock vs `last_memory_seen_at`
position-in-data vs the bank's `last_memory_write_at`); `response_schema` → `structured_output`
("fails loudly"); `detail` levels (`metadata`/`content`/`full`) to protect context budget; bank
`mission`/`directives`/`disposition` (reflect-only); knowledge pages; memory defense; MCP server.
