# Hindsight (Vectorize) — solution dissection, read against `agentic_dynamics`

**Date:** 2026-09-23 · **Author:** AIO Control Agent · **Trigger:** controller directive ("dissect this
entire solution and repo", starting from `https://hindsight.vectorize.io/developer/api/mental-models`).

**What this is.** An external-solution review: what Hindsight 0.10 *is* as documented, how its nouns map
onto this repo's nouns, where the two designs converge (external validation), where they diverge on
purpose, what is worth borrowing, and what should stay out. Claims about Hindsight are **[X] external**
and bounded to the pages read (listed in §10); claims about this repo are **[C] cited** to files/planes.

---

## 1. What Hindsight is

Hindsight (Vectorize, Inc.; docs v0.10; paper arXiv:2512.12818; `github.com/vectorize-io/hindsight`) is
a **memory service for AI agents**: agents `retain()` what happens, `recall()` by meaning, and
`reflect()` over retrieved memory in an agentic loop. It is multi-tenant by **memory bank**, ships
Python/TS/Go/CLI SDKs, an MCP server, Docker/K8s deployment, and first-class integrations for coding
agents — **including opencode**. Its marketing claim is benchmark leadership; its architecture claim is
that memory needs *consolidation*, *hierarchical retrieval*, and *curated summaries*, not a single
vector index.

## 2. The architecture, in their nouns

**The loop.** retain → (worker: consolidation) → recall/reflect → (worker: refresh). Memory lives in a
bank; content arrives as documents/sources and is chunked, embedded, indexed, and **LLM-extracted into
facts**.

**Memory types** (their hierarchy, highest priority first in reflect):

| type | what it is | who makes it |
|---|---|---|
| **Mental model** | saved, curated reflect answer for a source query | user-configured; refreshed |
| **Observation** | consolidated belief from many facts; evidence + proof count; history-preserving | consolidation worker |
| **World fact** | objective fact received | retain (LLM extraction) |
| **Experience fact** | the bank's own actions/interactions | retain |

**TEMPR retrieval.** Four arms run in parallel — **semantic** (vectors), **keyword** (BM25), **graph**
(entities), **temporal** (dates/ranges) — fused by **RRF** (`Σ 1/(60+rank)`), then a cross-encoder, then
recency/time/proof boosts, then a token budget. "Nothing is decided yet about which kind of search fits
[the query best], so every arm that applies runs."

**Consolidation (facts → observations).** Dedup; evidence tracking with exact quotes and proof counts;
**refinement, not overwrite** (contradictions produce history-preserving beliefs: "was previously a React
enthusiast … has now switched to Vue"); near-duplicate reconciliation by cosine threshold
(`HINDSIGHT_API_CONSOLIDATION_DEDUP_THRESHOLD`, default 0.97); scoped consolidation
(`observation_scopes`); an `observations_mission` to shape *what* gets synthesised; deletes cascade
(observations derived from deleted memories are deleted; survivors are re-consolidated).

**Mental models** (the endpoint that triggered this review). A mental model = `{name, source_query, tags,
trigger}` whose content is a **saved reflect response**:

- **Hierarchical priority** at reflect: mental models first, then observations, then raw facts.
- **Triggers:** `refresh_after_consolidation` (mutually exclusive with) `refresh_cron`; **rate-limited**
  by `min_refresh_interval_seconds` with **coalescing** — "a burst of twenty retains costs one refresh";
  a parked refresh reports `next_retry_at`.
- **Staleness gating:** every refresh first asks "is there a memory in this model's *resolved scope*
  newer than its last refresh?"; no writes in scope → no LLM call, no spend. Two timestamps answer two
  questions: `last_refreshed_at` (wall-clock; "have I already done this?") vs `last_memory_seen_at`
  (a position in the data; compared against the bank's `last_memory_write_at`). **Named limitation:
  "deletions are invisible to it."**
- **Two refresh modes:** `full` (regenerate; default) vs `delta` (typed operations
  — `add_section`/`remove_section`/`rename_section`/`replace_section_blocks`/`append_block`/
  `insert_block`/`replace_block`/`remove_block` — against an authoritative structured document; untouched
  blocks are copied through **byte-identical**; operations addressed by **id, never position**; invalid
  ops are **dropped**, not guessed; explicit fallback reasons: `no_baseline_content`,
  `source_query_changed`, `structured_doc_unreadable`, `delta_ops_failed`, `delta_ops_all_skipped`).
- **Conservatism:** "a failed retrieval is not an empty one" — a retriever failure *fails* the refresh and
  preserves content + watermark, so a retry reads the same window; a delta refresh never replaces a
  populated document with a partial or empty one.
- **Dry run:** the production pipeline with exactly two writes skipped; costs the same tokens; *not
  configurable by design* ("a dry run you can configure stops predicting the refresh it exists to
  predict"). **`keep_trace`:** per-refresh traces (tool calls with reasons, LLM calls, delta ops applied/
  skipped, usage, outcome) — kept even on failure.
- **Structured output:** optional `response_schema` → a typed `structured_output` beside the markdown;
  "fails loudly" rather than persisting content without its structured view.
- **Detail levels** (`metadata`/`content`/`full`) exist to protect context budget — list defaults to
  metadata; get defaults to full.

**Banks** configure `mission` (identity), `directives` (hard rules), `disposition` (soft traits, 1–5).
These affect `reflect` only, never `recall`. Other surfaces: **knowledge pages** (per-entity documents
refreshed like models), **memory defense** (security), operations API (async task board), webhooks.

## 3. `agentic_dynamics`, the corresponding nouns

This repo is an **information-acquisition machine for AI economics** — controlled trials → measured
information → policy → grid → campaign — plus the control plane that runs it and the knowledge plane
that records it. The eight planes (`ARCHITECTURE.md` §1): `core`, `experiment`, `measurement`,
`runtime`, `adapters`, `knowledge`, `control`, `reporting`.

Where memory/knowledge lives here:

- **Knowledge plane** — `knowledge_stream.py` (Redis Streams `kb:v1:changes`, four consumer groups),
  nine `source_type`s, ordered `Authority` (POLICY > SOURCE > MEASURED > DERIVED > ADVISORY), evidence
  classes `[M]/[C]/[H]/[P]/[X]`, lineage (`supersedes`/`causes`), `operation: upsert|supersede|delete`
  (delete = tombstone, **requires a reason**), scope = `repository_id` (default `self-<worktree>`;
  explicit non-empty = shared override), a write guard (`FINOPS_KB_WRITE`), and four projections
  (chroma/neo4j/ledger/registry) each acking independently with **projection watermarks**
  (`null` = unknown, never 0; FAILING/STALE/LAGGING/CURRENT).
- **Retrieval** — deterministic `retrieval.py`: dense (Chroma) × lexical (Neo4j full-text) → **RRF
  fusion**; hard per-cell scope pre-filter; evidence cards; a typed `prompt_constructor`; `augment.py`
  (retrieve→construct→render; named fallback modes; never blocks a phase).
- **Consolidation-analogs** — the fact plane (`facts` + `reducers/`), the 19 lab books over the
  canonical registry corpus, `generate_manifest.py` compaction (latest-per-entity; lifecycle_state
  current/superseded/tombstoned), and the append-only registry index.
- **Derived surfaces** — `scripts/_gen_instructions.py` (agent surfaces), `surfaces sync|snapshot`,
  `spec_status.py` (index + STATUS.md), `build_data.py` (website), with `--check` freshness and the
  **docs-drift scanner** (seven axes: cli_surface, module_inventory, spec_lifecycle,
  status_vocabulary, anchor_integrity, manifest_counts, fast_path).
- **Self-knowledge layer (loop 2)** — session records (`session open|close`), decision records
  (`decision record`, at the moment of the act), belief records with an update protocol, the controller
  model, the measured scoreboard, and a session-keyed **reflection series** (`reflect --read`).
- **Control plane** — the control db (runs/step_attempts/transitions), the ONE **control packet**
  (`control-status/v1`, `safe_actions` derived from the enforced transition graph), admission leases +
  settlement + watchdog + quarantine, supervisor flags (observe-only), and the permanence gate
  (`promote.py` — the only path to `main`; `publish release` — the one publication transaction).
- **The fleet** — host-side launch broker, typed launch requests, containerized orchestrator, spec
  compile/validate, declared test gates, host-side acceptance for UI candidates.

**Two name collisions worth stating:** their **"mental model"** is a *saved, curated, auto-refreshed
answer document*; our `agent_config/mental-model.md` is a *hand-authored, generated-surface file map*.
Their **"observation"** is a *consolidated belief*; our `source_type="observation"` is a *supervisor
rail record* (semi-structured, ADVISORY authority). The words match; the semantics do not.

## 4. The mapping table

| Hindsight | `agentic_dynamics` | verdict |
|---|---|---|
| memory bank / tags / scopes | `repository_id` cell scopes + org scopes + "explicit = shared" override | **convergent** (both made scope a first-class gate; both have an explicit shared/global mode) |
| retain (LLM fact extraction) | nine ingestion producers (deterministic derivation of measured fields) + write guard + actuation arming + lineage | **divergent in kind** (extraction vs derivation; ours carries authority/evidence provenance) |
| recall / TEMPR (4 arms, RRF, cross-encoder, boosts) | `retrieval.py` dense × lexical → **RRF** | **convergent on fusion**; ours lacks temporal/graph arms (Neo4j is projected, not fused) |
| observations (consolidated beliefs, dedup, contradiction-preserving) | fact plane reducers + labs + manifest compaction + `supersedes` chains | **same goal, different epistemics** (synthesis vs derivation; ours never invents a value) |
| freshness: unconsolidated facts → stale observations | projection **watermarks** (lag, `null`≠0, classify STALE/FAILING) | **convergent**, ours stricter on unknown-vs-zero; theirs scoped + queryable per model |
| mental models (curated, triggers, full/delta, dry-run, traces) | derived surfaces (`agent_config/*`, STATUS.md, `system_snapshot.md`) + docs-drift + generator `--check`; the register; the self-knowledge records | **same species** (curated/derived documents with refresh discipline) — theirs has delta-editing, per-doc triggers, and traces; ours has generator purity + drift scanners |
| reflect (agent loop; mission/directives/disposition) | the AIO itself (`session open/close`, `reflect`, `decision record`), `augment.py`, control-plane routing | **structural cousins**; our "mission/directives" are the rules file + P0/P1 + admission gates, not bank config |
| knowledge pages | registry entities + `docs/` tree | partial |
| memory defense | authority ordering + lease/quarantine + knowledge identity/authorization | partial (ours is access + truth-ordering; theirs is adversarial-poisoning oriented) |
| MCP server / SDKs | `.opencode/tools/` adapters + CLI | partial; **their opencode integration is noted** |
| — | admission/lease/settlement, spend gate, cost provenance | **absent on their side** (they *rate-limit* refreshes; they do not run a spend plane) |
| — | measurement plane (grit, efficiency, basin, routing) + the ledger + economics | **absent on their side** (no cost/quality instrument; benchmarks, not measurement rules as policy inputs) |
| — | workflow factory + gates + permanence gate | **absent on their side** |

## 5. Convergences worth noticing (external validation)

1. **Hybrid retrieval fuses by RRF on both sides** — independent convergence on the same rank-fusion
   family, ours from the corpus's lexical/dense split.
2. **Scope-as-gate** — their `all_strict` default vs our "empty never means global" rule; both refuse
   accidental over-reach.
3. **Freshness as first-class state** — their `is_stale` per model vs our watermark classifications;
   both refuse to render staleness as success. Ours already refuses to render **unknowable** as zero,
   which their model does not state (worth remembering as *our* advantage).
4. **History-preserving updates** — their contradiction reconciliation vs our `supersedes`/tombstone
   chains: both keep the story, never just the latest value.
5. **Dry-run discipline** — their "same pipeline, writes skipped, not configurable" articulates the
   standard our `--dry-run` flags already aim at; their phrasing is quotable for our conventions.
6. **Curated-first retrieval** — their mental-models-first priority is structurally similar to our
   authority ordering (POLICY > SOURCE > MEASURED > DERIVED > ADVISORY) — both put the most deliberately
   curated, most trustworthy material at the top of the reading order.

## 6. Divergences that matter

1. **Truth model.** Theirs is **belief consolidation**: an LLM synthesises a durable belief from facts
   (with evidence + proof counts). Ours is **measurement + derivation**: values are measured or absent,
   provenance and evidence classes are attached, and "unknown" is a legal, named outcome. For an
   economics instrument, this is not a preference — it is the product.
2. **Verification rails.** Their refresh is defended by conservatism (fail loudly, preserve content,
   dry-run, traces). Ours adds *independent* verification: separate test gates, adversarial review
   phases, host-side acceptance, and a permanence gate that refuses anything unsigned or unverified.
3. **Economics.** No spend plane, no cost provenance, no policy-as-arm loop on their side.
4. **Deletion semantics.** Their staleness gate is **blind to deletions** (named); our append-only
   stores treat shrinkage as a violation ("an operation that shrinks an append-only store is a violation
   until proven otherwise") and tombstones carry reasons. Copying their gate wholesale would import a
   known blind spot.
5. **Curation priority vs authority ordering.** Theirs orders by *how curated*; ours by *what kind of
   evidence*. Ours is richer where truth matters; theirs is simpler to operate.

## 7. What I would borrow (ranked; each is a proposal, not a decision)

1. **Delta-typed refresh for long-lived curated documents.** The register
   (`docs/reviews/loose_ends_register.md`), `agent_config/mental-model.md`, and `ARCHITECTURE.md` are
   edited by hand *and* by machines (status columns, counts). A typed-operation refresh that preserves
   untouched blocks **byte-identical** would let machines update enumerated fields without ever
   paraphrasing prose. Our generators currently do full re-render + `--check`; this is a complementary
   mode for the *hybrid* documents, with their fallback discipline (`no_baseline_content`,
   `source_query_changed` → full).
2. **Scoped staleness watermarks for derived surfaces.** A `last_seen`/`last_written` pair per generated
   artifact, so "does anything in my scope postdate my last read?" precedes regeneration. Keep our
   `null`≠0 semantics; add their **two-timestamp** distinction (refreshed-at vs seen-at) where people
   currently misread `generated_at`.
3. **Refresh traces for generators.** "Why did STATUS.md change this time?" is currently answerable only
   by `git diff`. A small trace (inputs read, decisions taken, fallbacks hit) attached to expensive
   regenerations would mirror `keep_trace` at our layer.
4. **Temporal (and eventually graph) retrieval arms.** Our retrieval fuses dense × lexical. The ledger
   carries rich attempt/time fields; Neo4j is projected but unfused. TEMPR is the existence proof that
   four-arm fusion + boosts + budget is operationally approachable — a candidate experiment, not a
   queue jump.
5. **Coalescing + minimum-interval for expensive refreshes.** Their parked-refresh-with-`next_retry_at`
   pattern ("twenty retains → one refresh") is the same shape as our admission/settlement thinking at a
   different layer; worth citing when we design rebuild cadences for labs/data chains.

## 8. What I would NOT adopt

- **LLM consolidation as the AIO spine's truth.** The self-knowledge layer's records are *recorded*,
  not synthesised; replacing that with belief consolidation would quietly trade evidence for narrative.
- **Deletion-blind staleness** (their named limitation) and **cascade-delete invalidation** (their
  observations vanish with sources; ours are append-only with tombstones).
- **Curation-priority as a substitute for authority ordering** — we need the evidence axis more than the
  curation axis.
- **The service itself, today.** Per the doctrine ("when the documented path fails, stop and record the
  gap"), a net-new top-level mechanism needs a named gap it closes. Today's register's gaps are
  control-room truth, model pins, and workflow rails — none of them a memory-quality problem this repo
  cannot already state. If an external memory layer is ever wanted (e.g. cross-repo agent memory, or a
  memory arm in an economics grid), Hindsight is the obvious first candidate to evaluate as a *subject*,
  with its opencode integration as the seam.

## 9. If pursued (options only)

- **Research arm:** "memory as a policy factor" — does a consolidated-memory layer change cost/quality/
  grit on long-horizon tasks? Hindsight is a ready-made external arm; our grid machinery already knows
  how to measure an arm.
- **Seam option:** their opencode integration — the least invasive place to run such an arm inside the
  existing cell runtime.
- **Design borrows** from §7 can be queued individually; none requires the service.

## 10. Bounded claims — what was read, and what was not

**Read (2026-09-23):** `hindsight.vectorize.io/` (Overview), `/developer/observations`, and
`/developer/api/mental-models` (v0.10). **Not read:** `/developer/retain`, `/developer/retrieval`,
`/developer/reflect` deep pages, `/developer/performance`, `/developer/storage`,
`/developer/memory-defense`, `/developer/knowledge-pages`, the API reference and the paper
(arXiv:2512.12818). Claims about those surfaces are deliberately absent; anything above that touches
them is inference from the overview diagrams and is marked as such in tone. No repo files were modified
by this review.
