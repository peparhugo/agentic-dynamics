---
status: accepted
supersedes: docs/review/restructure.md §5.2 (source_type-vocabulary centralization, R2)
---
# Knowledge base review — experiments and real workflows

Phase 5 (knowledge_base) of `repo_review_fable`. Scope: the merged KB — `knowledge.py`,
`knowledge_stream.py`, the nine producer modules, `retrieval.py`, `prompt_constructor.py`, and the
scripts (`kb_produce.py`, `kb_produce_sources.py`, `kb_produce_registry.py`, `kb_worker.py`,
`generate_manifest.py`, `registry.py`). Assessed the two ways the KB is now *actually used*:
**(a) by experiments** (batch producers + registry/tombstone machinery) and **(b) by real
workflows** (the runtime `retrieve → construct → render` seam + `emit_self`). Builds on
`docs/review/restructure.md` (R1–R9) and `docs/review/bugs.md` (BUG-1/4) — referenced, not
re-derived. All `file:line` re-read at commit `1baff2a6f`.

---

## 1. The two usage modes

| | (a) By experiments — batch producers | (b) By real workflows — runtime RAG |
|---|---|---|
| Entry | `kb_produce.py` / `kb_produce_sources.py` / `kb_produce_registry.py` | `workflow_runner.run_workflow` → `_augment_prompt` (`workflow_runner.py:249-341`) |
| Write path | `derive_*_records` → `record_to_artifact` → `record_to_event` → `publish_event` | `save_story_result` / `run.py` / `finalize_reviews` / `supervise.py` inline emits; `emit_self` after a phase commit |
| Read path | `kb_worker.py` consumer groups → Chroma/Neo4j/ledger/registry | `retrieve()` (dense + lexical) → `construct` → `render` |
| Authority/staleness machinery | `generate_manifest` compaction, supersede/tombstone, `registry.py` CLI, `/api/registry` | `AUTHORITY_MULTIPLIER`, freshness multipliers, `pinned_policy` |
| Scope | `repository_id` = `"agentic-dynamics"` (global-ish batch) | `cell_scope(wd)` = `self-<worktree>` per cell |

The two modes share one transport (the pointer contract) but **different scope semantics** — batch
ingestion stamps a single repository scope, runtime RAG stamps a per-cell scope. That distinction
is what makes the scope-isolation questions below load-bearing rather than cosmetic.

---

## 2. Authority contract — HONORED on the production path, one latent de-authoring foot-gun

The ordinal `POLICY > SOURCE > MEASURED > DERIVED > ADVISORY` (`knowledge.py:61-85`) is enforced at
four independent sites, and they agree:

1. **Producer assignment** — `policy_ingestion.build_policy_record` → `POLICY`/`[P]`
   (`policy_ingestion.py:218`), `code_ingestion` → `SOURCE`/`[C]` (`code_ingestion.py:299`),
   `knowledge_ingestion.build_record` → `MEASURED`/`[M]`, `quality_ingestion` → `MEASURED`/`[M]`
   or `DERIVED`/`[C]` (`quality_ingestion.py:260, 298`), phase-finding → `MEASURED` when
   `test_executed_success` is a bool else `ADVISORY`.
2. **Retrieval fusion** — `AUTHORITY_MULTIPLIER` (`retrieval.py:66-71`) weights SOURCE 1.15,
   MEASURED 1.05, DERIVED 1.00, ADVISORY 0.80, and **POLICY is absent** because pinned policy is
   never a probabilistic candidate (`retrieval.py:64-65`).
3. **Prompt construction** — `render_prompt` emits pinned policy under a distinct
   "authoritative, not retrieved" header (`prompt_constructor.py:477-478`), and `validate_plan`
   rejects authority escalation (`prompt_constructor.py:377` "cites evidence as control text") and
   requires hard-constraint text to trace to user text or pinned policy, not to retrieved evidence
   (`prompt_constructor.py:383`).
4. **Dedup** — `deduplicate` keeps the higher-authority survivor (`retrieval.py:479`).

**Finding A1 (MEDIUM, latent):** `knowledge_stream.default_extract` (`knowledge_stream.py:325-362`)
assigns `authority=DERIVED`, `evidence_class="[C]"`, `source_type=""`, `repository_id=""`,
`acl_scope=""` to **whatever** artifact it decodes. It is the `process_entry` default
(`knowledge_stream.py:397`). On today's production path it never runs because `kb_worker` always
injects `extractor=ki.extract_record` (`kb_worker.py:491, 500`), which recovers the record's real
authority/type/scope from the durable JSON. But the *default* would silently de-author a POLICY
record to DERIVED and empty its scope. This is a wrong-default, not a wrong-call: either make
`extract_record` the default, or make `default_extract` raise on an unrecognized artifact shape.

---

## 3. Scope isolation — HONORED in production, but the discriminator is not on the wire

The per-cell filter is real and hard: `retrieve()` drops any candidate whose *non-empty*
`repository_id` differs from the requested scope, before fusion and graph expansion
(`retrieval.py:392-405`, `:976-979`). `run_workflow` defaults `repository_id`/`acl_scope` to
`cell_scope(wd)` before building the retrieve fn, and preserves an explicit non-empty override
(`workflow_runner.py:600-603`). The Chroma leg carries `repository_id`/`acl_scope` in metadata
specifically so the dense leg doesn't return nothing under a non-empty scope (`kb_worker.py:376-381`).

**Finding S1 (HIGH, structural):** the scope discriminator is **not on the event envelope**.
`KnowledgeEvent` carries `knowledge_id`/`entity_id`/`operation`/`source_uri`/`source_revision`/
`content_hash`/`occurred_at`/`schema_version`/`event_id`/`causes`/`reason` (`knowledge.py:189-206`)
— no `source_type`, no `repository_id`, no `acl_scope`. The only way a consumer recovers scope is
by reading the **artifact** via the rich extractor. `default_extract` doesn't, so a consumer that
slips to the default produces empty-scope records — and `scope_excluded` treats an *empty candidate
scope* as "unscoped/legacy, stay eligible" (`retrieval.py:397-399`), not as excluded. Net effect:
**any record that loses its `repository_id` becomes visible in every cell's retrieval**, silently
undoing the per-cell invariant. Today the invariant holds only because two things line up by
convention (every producer writes full JSON artifacts; every worker injects `extract_record`) —
there is no type system or gate enforcing either.

**Finding S2 (MEDIUM):** the empty-candidate-scope "eligible" default is the wrong fail-open.
For a cell-scoped query (`repository_id` non-empty), a candidate with empty scope should be
excluded (or at minimum flagged), not admitted. The current behavior is explicitly "unscoped data,
not global" (`retrieval.py:398`), which is defensible for the legacy batch corpus but is exactly
the ambiguity a *per-cell* invariant needs to close.

---

## 4. Write guard — SOUND, with a documented soft door and one consumer-writer

`publish_event` raises unless `FINOPS_KB_WRITE=1` or `authorized=True` (`knowledge_stream.py:177-180`);
actuation additionally requires `FINOPS_ACTUATION_ARMED=1`/`armed=True` **and** a `causes` that
resolves to an observation via the lineage gate (`:181-191`). Batch producers set the env flag for
their run (`kb_produce.py:184`, `kb_produce_sources.py:275`); the inline write-time emits pass
`authorized=True` (`story.py:979`, `run.py:396`) or gate on the flag (`supervise.py`,
`kb_worker.py:229`). No hole found: the guard is a convention, not a security boundary, but that is
the stated design ("prevent accidental writes, not adversarial").

**Finding W1 (LOW, correctness-of-invariant):** the one consumer that *writes back* to the stream
is `kb_worker`'s flag auto-clear (`kb_worker.py:243`). It is correctly gated on `FINOPS_KB_WRITE=1`
(`:229`) and can only ever emit a `source_type="flag"` tombstone (`:213`), so the
"retrieve → construct → render references `publish_event` ZERO times" invariant still holds. But
this is a subtle place where a *reader* group (`kb-registry-v1`) mutates the same stream it reads —
worth a standing test asserting the group never publishes a non-`flag` event.

---

## 5. retrieve-vs-registry surface split — three divergent views of "what is this record"

This is the deepest structural finding. There are now **three** separate registries of
`source_type`, all fed from different consumers and none guaranteed to agree:

1. `SOURCE_TYPE_INDEX_KEY` — a Redis hash (`knowledge_stream.py:69`), populated as a side effect
   of `publish_event` (`:192-193`), documented as "a stand-in for the eventual canonical registry
   index" (`:66-68`).
2. The flat `registry_index.jsonl` — written by the `kb-registry-v1` consumer (`kb_worker.py:307-322`),
   compacted by `generate_manifest._compact_registry_index`, surfaced via `registry.py` + `/api/registry`.
3. The search stores — `source_type`/`authority` written into Chroma metadata (`kb_worker.py:372`) and
   Neo4j (`kb_worker.py:433`) by their own consumer groups.

**Finding R1 (HIGH):** the lineage gate `_resolves_to_observation` reads **only** the
`SOURCE_TYPE_INDEX_KEY` stand-in (`knowledge_stream.py:122`), which is now the *least* authoritative
of the three — it is populated only by processes that call `publish_event` with a non-empty
`source_type`, lives in a separate Redis hash, and is not reconciled against the registry index
that `generate_manifest`/`registry.py` now treat as canonical. Two records with the same
`knowledge_id` can disagree across the three views (e.g. a batch producer that omits `source_type`
still emits a valid event that the registry records, but the lineage gate's index never sees).
**The stand-in should be retired or reconciled against `registry_index.jsonl` now that the registry
is live.**

**Finding R2 (MEDIUM):** the registry and the retrieval stores are written by *different* consumer
groups, so at any instant a record can exist in the registry (append-only log) but not yet in
Chroma/Neo4j, or vice versa. `reconcile_missing` (`knowledge_stream.py:431-449`) is the intended
repair, but it has **no production caller** — `kb_worker.main` logs "no manifest wired in v1"
every hour (`kb_worker.py:552-554`) and does nothing. Dead-lettered events (after 3 retries) and
events lost before a group existed have no repair path. Wire the reconciliation pass or document
the loss mode as accepted.

---

## 6. Does the "one typed stream" hold end to end?

**Yes on the happy path; fragile on the type boundary.** The chain
`record → artifact (full JSON: type + scope + authority) → event (pointer, hash) → consumer
(extract_record recovers type + scope from artifact)` round-trips a record correctly *because* every
producer writes full JSON via `record_to_artifact` and every worker uses `extract_record`. But:

- **The type discriminator is not on the stream.** `source_type` is passed to `publish_event`
  (`knowledge_stream.py:135`) where it drives the gate + index, then is dropped — `KnowledgeEvent`
  has no `source_type` field (`knowledge.py:208-222`). A consumer therefore **cannot** type-dispatch
  from the event; it must use the universal JSON extractor. `default_extract` (the "raw file"
  extractor meant for code/policy text) would store a raw JSON blob as empty-typed, empty-scoped,
  DERIVED-authority `text` — and nothing in the system distinguishes a "JSON record artifact" from
  a "raw source file artifact" because that distinguishing fact (`source_type`) is the one field the
  envelope drops.
- **`observed_at` doesn't survive the round-trip** (BUG-1) — the freshness signal both the retrieval
  leg (`ADVISORY_FRESH_*`, `retrieval.py:74-75`) and the registry `--since` filter depend on is
  replaced by the producer wall-clock (`knowledge_ingestion.extract_record`).

**Finding T1 (HIGH):** add `source_type` to `KnowledgeEvent` (trailing-default, like `causes`/`reason`
were) so the stream is genuinely typed; then `default_extract` can dispatch (or refuse) on it instead
of silently producing empty-scope records. This is the single change that makes "one typed stream"
true rather than convention-true.

---

## 7. What to fix first

| # | Severity | Location | Change |
|---|---|---|---|
| T1 | HIGH | `knowledge.py:189-206`, `knowledge_stream.py:325-362` | put `source_type` on `KnowledgeEvent`; make `default_extract` dispatch/refuse on it |
| S1 | HIGH | `retrieval.py:392-405` + `knowledge_stream.py:341-353` | empty candidate scope must not silently bypass the per-cell filter |
| R1 | HIGH | `knowledge_stream.py:62-69, 114-125` | retire/reconcile the `SOURCE_TYPE_INDEX_KEY` stand-in against `registry_index.jsonl` |
| BUG-1 | MEDIUM | `knowledge_ingestion.py:417-424` | stop clobbering `observed_at` with `occurred_at` on the round-trip |
| R2 | MEDIUM | `kb_worker.py:550-554` | wire `reconcile_missing` (or drop the "no manifest wired" claim) |
| A1 | MEDIUM | `knowledge_stream.py:397` | default `extractor=extract_record`, not `default_extract` |
| BUG-4 | MEDIUM | `kb_worker.py:128-158` | carry `cell_id`/`status` structurally instead of parsing prose |
| R2 (restructure) | LOW | `knowledge.py:100-103`, `registry.py:59-62` | one source_type vocabulary |

**Bottom line.** The KB is genuinely used both ways and the core invariants — authority ordering,
per-cell scope, the write guard, the pointer contract — are honored on every production path. The
weaknesses are all the *same shape*: the facts that make the invariants true (`source_type`,
`repository_id`, `authority`, `observed_at`) are either dropped from the stream envelope or
silently defaulted, so the invariants hold by convention rather than by construction. T1, S1, and
R1 close those three gaps at the boundary; everything else is cleanup on top.
