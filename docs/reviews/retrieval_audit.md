---
status: accepted
---

# What do we retrieve? — the standing audit

**Why this file exists.** "What do we retrieve?" has been asked repeatedly across sessions and
answered nowhere durable — every answer was displaced by the next urgent thread. This is the
durable answer: measured, date-stamped, and to be re-run whenever the corpus or the emission
switches change.

## 2026-09-21 — first audit (measured live)

**Corpus** (`experiments/results/registry_index.jsonl`, 54,286 records): `fact` 45,858 (85%) ·
`finding` 3,908 · (untyped/superseded) 1,470 · `code` 1,073 · `spec` 454 · `story` 330 ·
`meta_session` 245 · `review` 242 · `decision` 171 · `report` 120 · `reflection` 117 ·
`wave_verdict` 115. Lifecycle: current 52,303 / superseded 1,470 / tombstoned 513. Last 24h:
`finding` 158 · `fact` 48 · `spec` 3 · `wave_verdict` 3.

**Legs** (measured): the **lexical** leg (Neo4j full-text over `Knowledge.text`) works. The
**dense** leg is a vector search over Neo4j (`Neo4jVectorStore` — the Chroma service was retired
2026-09-19) and works via `default_retrieve_fn` (3 hits for "cache hit rate"). The **registry**
works. A **scoped** pipeline query (`repository_id`/`acl_scope` = `agentic-dynamics`) can return
**0 candidates** for generic queries — the scope pre-filter admits only exact-scope records.

**What queries actually return:**

- `"cache hit rate economics"` → code symbols (`derive_cache_hit_rate`), one decision, one wave
  finding — code-index hits, not the lab's analysis text.
- `"submission accepted versus work completed"` → **spec-index regeneration churn** (four
  `138 specs changed` findings). The arc's central failure pattern is *not in the KB*, so
  retrieval returns administrative noise.
- `"context capacity compaction false trip"` → code symbols (`run_plan`, `backfill_worktree`)
  plus one relevant decision.
- `"contemplation synthesis delivery repair"` → the session's own records (decision `3811e316…`,
  decision `e2c0533c…`, meta_session `70c84cd6…`, finding `fd4a3960…`) — i.e., exactly what we
  explicitly emitted.

**Verdict.** We retrieve: **code symbols, process telemetry** (facts, spec churn, wave
verdicts), **spine records** (decisions/sessions/reflections), and the findings we have
explicitly emitted. We do **not** retrieve the arc's analysis content — the contemplation
answers, the lab conclusions, the failure-pattern wisdom — because those were never emitted.

**Gaps, ranked:**

1. Analysis/contemplation specs opt out of emission (`emit_self: false` in ~10 specs) — the
   content never enters the KB.
2. Facts dominate (85%); the curated knowledge layer is thin.
3. Scoped pipeline queries return 0 for generic queries (scope pre-filter behavior) — a reader
   must know the exact scope to retrieve anything.
4. Retrieval-in-the-loop (augmentation) is enabled by only 8 specs; most phases never retrieve
   at all.

**Standing question.** Re-run this audit when the emission switches change. The answer is only
as good as the corpus, and the corpus is only as good as what we emit.

**Update, 2026-09-21.** Gap 3's CLI side is closed: `agentic-dynamics knowledge read --query Q
--scope S` (script `kb_read.py`) is the reader verb — ranked retrieval through the existing
pipeline with a deterministic artifact-scan fallback (`--contains`, offline), documented by the
`knowledge-reader` skill. The scope rules are unchanged (exact-match pre-filter; a non-empty
explicit scope is the shared override).

**Update 2, 2026-09-21.** Gap 1 resolved for every tracked workflow spec: all 20 `emit_self:
false` opt-outs were flipped to `emit_self: true` (`control_room_run_journey.yaml` pending its
uncommitted v0.2 edit). Research/analysis runs now emit their reports as retrievable findings
by default — the corpus should begin carrying analysis content, not just telemetry.
