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

## Remediation round 2 (the second review's findings F1–F5)

The second independent review (terra, against `f481c8d4e`) returned FAIL with five findings.
Each is closed here, completely:

- **F1 — non-Python inline/block comments.** `_normalize_source`'s fallback now strips comments
  with a string-aware scanner (`diversity._strip_comments`) covering `#`, `//`, and `/* */`
  outside quotes; string contents survive (`"http://x"` is not a comment). Tests:
  `tests/test_diversity.py::test_inline_and_block_comments_in_non_python_normalize_to_zero`
  (JS inline, C block/leading/trailing, URL preservation).
- **F2/F4 — no production consumer for the instrument.** Built the scorer seam:
  `src/agentic_dynamics/measurement/portfolio_score.py` + `scripts/score_flash_ladder.py`
  (CLI `agentic-dynamics experiment flash-ladder-score`). It loads `run.py` result JSON, groups
  by condition, **excludes** `solution_code is None` attempts while **reporting**
  `excluded_null_source`, computes `portfolio_diversity`, and persists the score with input
  sha256s and the code sha. Tests: `tests/test_portfolio_scorer.py` (null exclusion + coverage,
  all-null → empty not zero, hashes/code sha).
- **F3 — live-store evidence not reproducible where the reviewer sits.** The network topology
  is now the documented contract: `neo4j` (`infrastructure_kb-neo4j_1`) is on `fleet-net`, so
  the **lexical live probe is reproducible in-cell at `bolt://neo4j:7687`** (never
  `localhost`); `chromadb` is on `infrastructure_ai-infra` and is **not reachable from cells by
  design**, so the dense live evidence is host-side, produced by the committed runner
  `scripts/probe_retrieval_reachability.py` and attached as
  `docs/reviews/flash_exploration_retrieval_probe.json`. In-cell reproduction of the dense leg
  is structurally impossible and is reported as an environment boundary, not a failure; the
  reviewer verifies the runner's code path and the artifact's internal consistency instead.
  Artifact (this HEAD): `dense_available: true`, `fallback_mode: full` both flag settings,
  48 knowledge records selected (43 findings, 2 decisions, 2 flags, 1 meta-session),
  `stale_source_selected: 0`.
- **F5 — stale Probe 5 output + wrong consumer path.** `docs/reviews/flash_exploration_verify.md`
  Probe 5 now records the F4 semantics (`None`) with a correction note, and the archived
  consumer path is corrected to `scripts/archive/backfill_artifacts.py`.
- **Reproduction caveat (from review 1, still true).** F2b (live DERIVED-pattern query + a
  second live dry-run proving 0/0) requires the controller-approved mint; it is the first
  post-mint act and is not part of this review's evidence classes.

## Remediation round 3 (the third review's findings F1–F4)

The third independent review (terra, against `1b7ca911d`) returned FAIL with four findings;
all are closed here, at commit `10c1f3519`:

- **F1 — interior whitespace / non-Python reformatting still inflatable.** `_normalized_forms`
  now returns TWO forms: a **canonical** form (AST for parseable Python; otherwise
  comment-stripped with ALL whitespace runs collapsed to single spaces) that every axis except
  structure compares, and a **line_form** (comment-free, blank lines dropped) whose line count
  feeds structure divergence so LOC does not degenerate. Interior whitespace left by a removed
  comment, and whitespace-only reformatting, now read as `0.0`. Tests:
  `tests/test_diversity.py::test_interior_whitespace_and_comment_removal_normalize_to_zero`.
- **F2 — omitted/malformed `solution_code` silently unscored.** `ConditionScore` gained
  `excluded_invalid_source`: a missing key or a non-string, non-null value is counted
  separately (never scored, never folded into the null count). Tests:
  `tests/test_portfolio_scorer.py::test_scorer_reports_invalid_source_separately`.
- **F3 — probe artifact unbound to the candidate and no per-leg counts.** The probe now records
  `generated_at`, `code_sha` (git HEAD), the resolved `agentic_dynamics` and `retrieval`
  module paths, and **direct per-leg hit counts** (never inferred from `fallback_mode`).
  Regenerated artifact at `10c1f3519`: `dense_hits: 10`, `lexical_hits: 10`,
  `dense_available: true`, `fallback_mode: "full"` both settings, 48 knowledge records, 0
  stale SOURCE (`docs/reviews/flash_exploration_retrieval_probe.json`).
- **F4 — contradictory Probe 5 evidence.** `docs/reviews/flash_exploration_verify.md` Probe 5 is
  a **regenerated current-HEAD transcript** at `10c1f3519` (labeled), and the document head now
  distinguishes historical captures (Probes 1–4 at `f3957a318`) from the regenerated Probe 5.

## Remediation round 4 (the fourth review's findings A1–A3)

The fourth independent review (terra, against `fd97a2ea9`) returned FAIL with three findings —
two of them genuine regressions introduced by earlier remediation rounds. All are closed at
commit `693ded194`:

- **A1 — false zeros in non-Python normalization.** The comment scanner stripped a leading
  ``#`` that opens a C/C++ preprocessor directive (so ``#define VALUE 1`` and ``#define VALUE 2``
  canonicalized equal → hard zero) and did not track JavaScript template literals (so
  ``\`http://one\``` lost everything after ``//``). Fixed: `_CPP_DIRECTIVES` preserves
  directive lines, backticks are a quote class, and semantic changes now score > 0 while
  cosmetic changes stay 0.0. Tests:
  `tests/test_diversity.py::test_semantic_c_macro_and_js_template_literals_are_not_cosmetic`.
- **A2 — graph expansion bypassed the SOURCE commit gate.** Expanded neighbors were appended
  after fusion with authority/pattern/scope checks but no freshness check, so a stale SOURCE
  neighbor was selectable. Fixed: `freshness_multiplier` is applied to every expanded candidate
  before it is appended (SOURCE mismatched commit → excluded; MEASURED/DERIVED/ADVISORY
  admitted). Test:
  `tests/test_retrieval.py::test_retrieve_expansion_applies_commit_gate_to_source_neighbors`.
- **A3 — Probe 5 was not a runnable/current transcript.** The section is rewritten at
  `693ded194`: a runnable command (heredoc with a closing `PY` marker) followed by a separate
  output fence, both regenerated and consistent with the document head.
- Regenerated evidence at `693ded194`: `docs/reviews/flash_exploration_retrieval_probe.json`
  (provenance-bound; `dense_hits`/`lexical_hits` direct) and the Probe 5 transcript.
