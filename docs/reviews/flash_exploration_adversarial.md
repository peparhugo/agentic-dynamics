---
status: accepted
---

# Flash Exploration Adversarial Review

**Reviewer:** `openai/gpt-5.6-terra` (independent of the flash author)
**Reviewed branch:** `feature/flash-exploration` at `f481c8d4e`
**Scope:** review only. This pass changed no implementation or test files.
**Verdict: FAIL.** The branch is not merge-ready for the data-plane mint or ladder. Fix F1 and
F2, then repeat the unavailable live-store probes required by F3. F4 and F5 must also be
corrected before treating `p4_verify` as a passing gate artifact.

## Findings

| ID | Severity | Finding | Direct evidence | Required disposition |
|---|---|---|---|---|
| F1 | High | `portfolio_diversity` remains gameable by inline comments in non-Python source. The fallback only discards whole `#`/`//` lines; it retains inline `//` and block comments, which raise `mean_composite` and `max_composite` despite no semantic change. | `pairwise_divergence("function f(){ return 1; }", "function f(){ return 1; } // cosmetic")` returned `composite=0.10909090909090909`; the analogous C block-comment pair returned `0.16153846153846152`. `src/agentic_dynamics/measurement/diversity.py:93-99` implements the incomplete fallback. | Normalize comments for every collected language, or restrict the metric to a parser-backed representation and explicitly report unsupported-language coverage. Add JavaScript/C inline-comment regression tests. |
| F2 | High | The new portfolio instrument is not connected to a production measurement path. It is defined and unit-tested, but no non-test caller calculates it from result JSON or records a portfolio result. `solution_code` therefore cannot yield the declared `portfolio_diversity_measured` signal. | Repository search found `portfolio_diversity(` only at `src/agentic_dynamics/measurement/diversity.py:199` and `tests/test_diversity.py`; `solution_code` is written only by `scripts/run.py:217,347` and has no scorer consumer. | Add the intended scorer/aggregation seam, persist the result with its coverage, and test it from a result JSON containing `None` and collected source. |
| F3 | High | The three live retrieval layers were not independently re-verified on this HEAD. The dense probe cannot start because `chromadb` is absent, and the lexical probe cannot connect because `bolt://localhost:7687` refuses connections. Pure filter/unit evidence does not demonstrate either running store accepts exempt authorities or rejects stale SOURCE at the current commit. | `from agentic_dynamics.knowledge.embeddings import ChromaStore; ChromaStore(...)` raised `ModuleNotFoundError: No module named 'chromadb'`. A direct `Neo4jClient(uri="bolt://localhost:7687", ...)` mismatched-commit query raised `neo4j.exceptions.ServiceUnavailable: connection refused`. | Re-run the mismatched-commit probe against live Chroma and Neo4j on the candidate HEAD. Show MEASURED/DERIVED/ADVISORY admitted and mismatched SOURCE excluded in every layer. |
| F4 | Medium | `solution_code` is deliberately nullable, not always populated. This is the right absence representation, but it does not meet a literal claim that every attempt has recoverable solution code, and there is no downstream scorer enforcing the documented exclusion rule. | `_serialize_solution_code(None)` and `_serialize_solution_code({})` both returned `None`; `scripts/run.py:585-590` documents the same rule. `_collect_code` returns `None` for an unavailable worktree or no supported source at `scripts/run.py:615-631`. | Make the ladder's coverage denominator explicit, exclude null-source attempts in the real scorer, and report the excluded count. Do not describe this field as universally populated. |
| F5 | Medium | `p4_verify` is not a passing verification artifact under its own `DONE_WHEN`. It labels the dense clause untested, pattern convergence simulated rather than live, and Probe 5's raw output records the superseded `""` behavior. Its consumer command also names nonexistent `scripts/backfill_artifacts.py`; the actual archived consumer is `scripts/archive/backfill_artifacts.py`. | `docs/reviews/flash_exploration_verify.md:15-25,56-60,648-684,719-745`; `workflows/repository/flash_exploration_build.yaml:161-174`; actual consumer at `scripts/archive/backfill_artifacts.py:74-178`. | Replace the stale/raw-incompatible Probe 5 evidence, inspect the actual archived consumer, and do not mark the phase complete until F3's live-store and live-convergence evidence exist. |

## Re-Verified Passes

The following checks are positive evidence, but they do not outweigh the findings above.

| Probe | Result |
|---|---|
| Focused suites | `143 passed, 1 skipped`: `test_retrieval.py`, `test_context_plane_pattern.py`, `test_kb_produce_facts_integration.py`, `test_diversity.py`, and `test_run_result_shape.py`. |
| Fusion and dense predicate | At a mismatched commit, `freshness_multiplier` returned `None` for SOURCE and `1.0` for MEASURED/DERIVED; `_dense_filter` contained only empty/exact commit plus MEASURED/DERIVED/ADVISORY authority clauses. This is code-path evidence only, not F3's live-store proof. |
| Pattern stability | With the same three finding rows in opposite order at revisions `a*40` and `b*40`, the reducer emitted the same `evidence:8bc42bb1c1108965` window and equal fact fingerprints. Adding `k4` changed the window to `evidence:500c7dff003c1c8e` and changed the fingerprint. |
| Edge/null rules | Empty strings, whitespace-only strings, and two identical samples produced exact zero pairwise diversity. Empty and singleton portfolios produced null aggregate metrics with `coverage` `empty` and `single`. |
| Artifact names and consumers | Nine `(seed_variant, repetition)` pairs produced nine distinct suffixes and the default suffix remained empty. Direct inspection found no incompatible consumer dependency: `analyze_worktrees` and archived `backfill_artifacts` derive their own names from worktrees; `inventory` does not consume these fields. |

## Probe Record

The review ran the following representative commands at the reviewed HEAD.

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_retrieval.py tests/test_context_plane_pattern.py \
  tests/test_kb_produce_facts_integration.py tests/test_diversity.py \
  tests/test_run_result_shape.py -q -p no:cacheprovider
```

```text
143 passed, 1 skipped in 1.49s
```

```bash
PYTHONPATH=src python3 - <<'PY'
import importlib.util

from agentic_dynamics.control import fact_ingestion as fi
from agentic_dynamics.control.reducers.pattern import decode_pattern_payload, pattern_v1

spec = importlib.util.spec_from_file_location("pattern_tests", "tests/test_context_plane_pattern.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
rows = [
    mod._finding(knowledge_id="k1", test_executed_success=True),
    mod._finding(knowledge_id="k2", test_executed_success=False),
    mod._finding(knowledge_id="k3", test_executed_success=True),
]
a = pattern_v1(mod._reducer_input(rows, source_revision="a" * 40))[0]
b = pattern_v1(mod._reducer_input(list(reversed(rows)), source_revision="b" * 40))[0]
added = pattern_v1(
    mod._reducer_input(rows + [mod._finding(knowledge_id="k4", test_executed_success=True)])
)[0]
window_a = decode_pattern_payload(a.value).validity_window
window_b = decode_pattern_payload(b.value).validity_window
window_added = decode_pattern_payload(added.value).validity_window
print("stable_window", window_a, window_b, window_a == window_b)
print("stable_fingerprint", fi.fact_fingerprint(fi.build_fact_record(a)) == fi.fact_fingerprint(fi.build_fact_record(b)))
print("added_window_changed", window_a, window_added, window_a != window_added)
print("added_fingerprint_changed", fi.fact_fingerprint(fi.build_fact_record(a)) != fi.fact_fingerprint(fi.build_fact_record(added)))
PY
```

```text
stable_window evidence:8bc42bb1c1108965 evidence:8bc42bb1c1108965 True
stable_fingerprint True
added_window_changed evidence:8bc42bb1c1108965 evidence:500c7dff003c1c8e True
added_fingerprint_changed True
```

```bash
PYTHONPATH=src python3 - <<'PY'
from agentic_dynamics.measurement.diversity import pairwise_divergence

pairs = [
    ("js_inline_comment", "function f(){ return 1; }\n", "function f(){ return 1; } // cosmetic\n"),
    ("c_block_comment", "int f(void) { return 1; }\n", "int f(void) { /* cosmetic */ return 1; }\n"),
]
for name, before, after in pairs:
    print(name, "composite=" + str(pairwise_divergence(before, after)["composite"]))
PY
```

```text
js_inline_comment composite=0.10909090909090909
c_block_comment composite=0.16153846153846152
```

The first two results establish the evidence-window behavior. The final result falsifies the
remediation claim that non-Python cosmetic changes cannot affect the diversity metric.

## Release Decision

**FAIL: do not mint or launch the ladder from this branch.** The minimum repair sequence is:

1. Eliminate F1's non-Python comment inflation and add regression coverage.
2. Wire F2 into a real, coverage-aware portfolio scorer over persisted result records.
3. Re-run the current candidate against live Chroma and Neo4j, including a real DERIVED pattern
   after the controller-approved mint, to close F3.
4. Refresh `p4_verify` with raw output from the repaired HEAD and correct F4/F5's stale claims.
