---
status: accepted
---

# flash_exploration — remediation pass (`g5` findings F2a/F3/F4/F5/F6)

**Authored after:** the independent adversarial review
(`docs/reviews/flash_exploration_adversarial.md`, verdict **FAIL**) against the continuation
run `run-d7dc526ad91a` / candidate `e152bc823`.
**Scope:** the author-side repairs + the host-side live probe the review required. No live-KB
write; the pattern mint remains the controller-approved data-plane act.

## F3 — cosmetic edits no longer read as divergence

`pairwise_divergence` now normalizes each source **before** any axis is scored
(`measurement/diversity.py: _normalize_source`): parseable Python goes through
`ast.parse`/`ast.unparse` (comments, blank lines, indentation style, and trailing whitespace
vanish); non-Python/unparseable sources take a line filter (blank and `#`/`//` lines dropped,
line edges stripped). A pair that normalizes equal is a hard zero.

- Regression tests: `tests/test_diversity.py::test_cosmetic_edits_normalize_to_zero`,
  `::test_cosmetic_portfolio_has_zero_diversity`, `::test_genuine_change_remains_positive`;
  `test_pairwise_fields_are_the_basin_primitives` now asserts on the normalized sources.
- Bound, stated honestly: whitespace/comment churn scores `0.0`; a one-token semantic change
  still scores (that is the metric working as designed, not gameability). The preregistered
  primary `distinct_fraction` at 0.5 was already out of reach of novelty-only cosmetic edits;
  the repair closes the `mean_composite`/`max_composite` inflation path too.

## F4 — `solution_code` distinguishes uncollected from empty

`scripts/run.py::_serialize_solution_code` now returns `None` when no source is collectable
(never `""`, which was indistinguishable from an intentionally empty solution), and the
docstring states the ladder rule: **a scorer must exclude `solution_code is None` attempts,
never score them as empty source.**

- Test: `tests/test_run_result_shape.py` (new) — `None`/`{}` → `None`; deterministic headers.

## F2a — live dense (Chroma) probe, and a defect it exposed

The review's blocker: the dense leg had never run live. Host-side probe (real `retrieve()`,
real Chroma + Neo4j, a commit that matches **no** record):

```bash
$ cd /tmp/wt_flash_exploration && PYTHONPATH=src python3 - <<'PY'
from agentic_dynamics.knowledge.retrieval import retrieve
from agentic_dynamics.knowledge.embeddings import ChromaStore
from agentic_dynamics.knowledge.graph import Neo4jClient
store = ChromaStore(host="127.0.0.1", port=8100, collection_name="knowledge_chunks_v1")
gc = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="password123")
MIS = "0" * 40
for proj in (False, True):
    att = retrieve("grit recovery under process perturbation test success",
                   dense_store=store, graph_client=gc,
                   repository_id="agentic-dynamics", acl_scope="public",
                   commit_sha=MIS, pattern_projection=proj)
    counts = {}
    for c in att.selected_evidence:
        counts[c.source_type] = counts.get(c.source_type, 0) + 1
    print(f"pattern_projection={proj}: fallback={att.fallback_mode} "
          f"candidates={len(att.candidates)} selected={len(att.selected_evidence)} types={counts}")
PY
```

**Raw output (after the fix below):**

```text
pattern_projection=False: fallback=full candidates=51 selected=48 types={'finding': 43, 'meta_session': 1, 'decision': 2, 'flag': 2}
pattern_projection=True:  fallback=full candidates=51 selected=48 types={'finding': 43, 'meta_session': 1, 'decision': 2, 'flag': 2}
```

**Reading.** Both legs ran live (`fallback=full`) and 48 knowledge records were selected at a
mismatched commit — MEASURED findings, DERIVED findings, decisions, flags, meta-sessions. No
stale `SOURCE` record was selected. `pattern_projection` is inert only because the live KB
still holds **0 pattern projections** (F2b — the mint supplies them). F2a is now demonstrated,
not inferred from the pure filter.

**New defect found by the probe and fixed.** The first live run crashed:
`freshness_multiplier` subtracted a **naive** parsed timestamp from an **aware** reference
clock (`TypeError: can't subtract offset-naive and offset-aware datetimes`), which excluded
every ADVISORY record (reviews, decisions) from retrieval. Fixed: a naive timestamp is treated
as UTC and the injected reference clock is normalized the same way
(`retrieval.py: freshness_multiplier`). Regression test:
`tests/test_retrieval.py::test_freshness_multiplier_advisory_naive_timestamp_is_utc`.

## F5/F6 — overstated claims corrected

`docs/reviews/flash_exploration_verify.md` now carries a **PARTIAL** disposition with the
unavailable gates named (dense leg unexercised in-container; no live DERIVED record; live
convergence not demonstrated — both live dry-runs report the one-time supersede migration).
Its raw outputs are unchanged; only the disposition and the convergence sentence were
downgraded.

## F1 — sequencing note

The review's F1 cited the *previous* attempt's ledger (g6 refused). The same continuation run
then executed the repaired verifier path: `g6_test_gate` recorded `test_executed_success=true`,
`137 passed / 137 total` (`experiments/results/workflows/flash_exploration_build_resume/20260910T181030Z.json`).
The reviewer could not see a gate that ran after it — the sequencing is the disposition.

## Remaining before the mint + ladder

1. A fresh adversarial re-review + `g6_test_gate` on this repaired HEAD.
2. Controller approval of the one-time pattern mint; then the **F2b** probes: a live
   DERIVED-pattern query and a second live dry-run proving 0 fact / 0 projection
   supersessions.
