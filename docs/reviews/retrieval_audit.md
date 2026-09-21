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

**Update 3, 2026-09-21 (the re-run the standing question asked for — the emission flips are
measured).** All four audited queries re-run verbatim through `agentic-dynamics knowledge read
--scope agentic-dynamics`; the corpus recounted from `registry_index.jsonl`.

*Corpus.* 54,524 records: `fact` 46,056 (84.5%) · `finding` 3,936 · (untyped) 1,470 · `code`
1,073 · `spec` 455 · `story` 330 · `meta_session` 248 · `review` 242 · `decision` 174 ·
`report` 120 · `reflection` 119 · `wave_verdict` 118 · `flag` 102 · `policy` 34 · `pattern` 25 ·
`context_snapshot` 11 · `actuation` 11. Lifecycle: current 52,541 / superseded 1,470 /
tombstoned 513. The categories now sum exactly to the total (the first audit's list summed to
54,103 against its stated 54,286 — the 183-record discrepancy is closed by the recount).

*The verdict, re-measured.* "We do not retrieve the arc's analysis content" no longer holds where
material was emitted: `"submission accepted versus work completed"` returns the item-4 closure
finding (`93706c05…`), its residual-correction record (`7e9de311…`), and the skeleton-contract
finding (`27856b77…`) — not the four `138 specs changed` spec-churn findings of the first audit.
`"contemplation synthesis delivery repair"` returns the audit + design findings; `"cache hit rate
economics"` and `"context capacity compaction false trip"` return emitted findings alongside code
symbols. The `--contains` offline scan remains the deterministic fallback.

*Last 24h.* `finding` 463 · `fact` 316 · `wave_verdict` 9 · `spec` 7 · `decision` 5. The finding
surge is mostly ONE evening of pre-disarm suite emissions (422 records on 2026-09-20 17:00–19:00,
before `f653336ca` disarmed the suite) plus ~21 real analysis emissions on 2026-09-21.

*New finding — the test-emit disarm has a hole.* An explicit spec `rag.emit_self: true` outranks
the suite's `FINOPS_EMIT_SELF=0` disarm (`workflow_runner.py:1726-1728`), so
`tests/test_world_model_gates.py`'s fixture spec — which opts in to exercise `emit_report` —
writes real findings to the live KB on every run: 4 `self-test_artifact_gate_*` records observed
at 14:41 today. Fix shape: stub the emit seam in the module's other tests (the convention its
emit test already follows), or drop the fixture spec's opt-in outside that test. Bounded, named,
unfixed.

*Still open.* Exact-match scope pre-filter (gap 3's rule side — a scoped pipeline query can still
return 0); retrieval-in-the-loop coverage (8 specs; not re-measured); and the scope observation
the loop's own posterior recorded: a run's metadata findings land in its cell scope
(`self-<workdir>`), not `agentic-dynamics` — `emit_scope` is honored only by the report variant
(`workflow_runner.py`; world-model-loop posterior U3).
