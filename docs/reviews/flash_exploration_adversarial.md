---
status: accepted
---

# Flash Exploration Adversarial Review

**Reviewer:** `openai/gpt-5.6-terra` (independent of the flash author)

**Reviewed branch:** `feature/flash-exploration` at `46e479bef`. The implementation candidate is
`693ded194f89f980dbae0ba9cb103922075ae63a`; changes after it are the close-out documentation,
the regenerated probe artifact, and workflow/preregistration material. `retrieval.py` and
`probe_retrieval_reachability.py` are unchanged from that candidate.

**Scope:** adversarial review only. This pass changes only this review document.

**Verdict: FAIL.** The required non-Python cosmetic-invariance attack remains bypassable, and a
second JavaScript-template bypass remains. The retrieval path also has a pre-existing ACL leak,
and the new host probe can falsely report dense availability. Do not release the ladder until
F1-F4 are repaired and independently re-reviewed.

## Findings

| Finding | Severity | Direct re-verification | Required disposition |
|---|---|---|---|
| F1: The non-Python fallback treats ordinary reformatting as diversity. Its canonical form collapses whitespace runs but preserves whitespace adjacent to punctuation, so equivalent JavaScript and C formatting remains textually different. This violates the required interior-whitespace/reformatting invariance and can inflate `portfolio_diversity`. | High | `pairwise_divergence("function f(){return 1;}\n", "function f() { return 1; }\n")["composite"] == 0.1607142857142857`; the C analogue (`int f(void){return 1;}` vs `int f( void ) { return 1; }`) is `0.23823529411764707`. `measurement/diversity.py:168-170` normalizes with `" ".join(stripped.split())`, which cannot make these equivalent. By contrast, comment-only pairs return `0.0`; the gap is specifically formatting around syntax. | Replace the fallback canonicalization with a language-aware/token-level representation that preserves literal contents and semantic token boundaries while discarding formatting. Add JavaScript and C whitespace/reformatting regression cases; every cosmetic case must be exactly `0.0`. |
| F2: The comment scanner treats a whole JavaScript template literal as opaque. Comments inside a `${...}` interpolation are JavaScript comments, not template content, but they survive canonicalization and inflate the score. | High | Comparing a template with interpolation `1` to the same template with `1 /* cosmetic */` in that interpolation returned composite `0.20322580645161292`. `_strip_comments` enters backtick quote mode at `measurement/diversity.py:113-117` and therefore does not lex interpolation expressions. | Parse or recursively lex `${...}` expressions while preserving literal segments. Add an interpolation-comment regression case with an exact-zero assertion. |
| F3: Direct lexical retrieval can return knowledge from a foreign ACL scope when its `repository_id` matches. This is pre-existing (`git blame` attributes the direct lexical call and post-filter to `e8eb2e4c6a`/`523c0bac14`), not introduced by the flash commit-gate patch, but it violates the documented hard per-cell scope boundary and is exposed by this reachability path. | High | A fake lexical graph returned a MEASURED record with `repository_id="self-a"` and `acl_scope="private-b"`. `retrieve(... repository_id="self-a", acl_scope="private-a")` produced `candidate_ids ['foreign-acl']` and `selected_ids ['foreign-acl']`. `retrieval.py:1431-1433` does not pass `acl_scope` to the direct lexical query; `:1572-1575` filters only `repository_id`, and `Candidate` does not retain ACL scope for a later filter. | Preserve and enforce ACL scope for the lexical leg, before fusion and selection, and add a direct-lexical foreign-ACL regression test. Treat this as a separate pre-existing security repair, not as a regression attribution against the flash author. |
| F4: The host probe's `dense_available` field means only that `ChromaStore` constructed, not that the dense store was reachable. It can therefore report `dense_available: true` while its direct dense leg failed. | Medium | `probe_retrieval_reachability.py:84-94,111` sets the field after construction. `embeddings.py:141-148` defers `get_or_create_collection()` until first use; `_leg_counts` then catches a search failure and emits `dense_hits: null` plus `dense_error` (`probe_retrieval_reachability.py:56-62`) without clearing `dense_available`. | Set availability only after a successful direct dense query, or rename it to `dense_constructed` and require the artifact validator to reject `dense_available: true` with `dense_hits: null`/`dense_error`. Regenerate the host artifact after the repair. |

## Passing Re-Verification

| Check | PASS evidence |
|---|---|
| Hermetic gate | `python3 -m pytest tests/test_retrieval.py tests/test_context_plane_pattern.py tests/test_kb_produce_facts_integration.py tests/test_diversity.py tests/test_run_result_shape.py tests/test_portfolio_scorer.py -q` completed with `151 passed, 1 skipped in 1.52s`. The existing tests do not cover F1/F2's bypasses. |
| A1 semantic-change protection | The C preprocessor change `#define VALUE 1` to `#define VALUE 2` scored `0.06818181818181819`; a JavaScript template literal `http://one` to `http://two` scored `0.1111111111111111`. Both are greater than zero. |
| Comments already covered by the fallback | Inline/block comment-only JavaScript and C examples scored `0.0`. This does not offset F1 or F2: the required attack includes whitespace/reformatting and comments inside template expressions. |
| Pattern validity window | The specified hermetic context-pattern suite passed. The reducer's evidence-digest window and fact fingerprint are therefore pinned against input ordering/revision churn, while changed evidence changes the window, as documented in the repaired verification artifact. |
| Scorer null/not-collected handling | A four-attempt result set with one `null`, one omitted value, one integer, and one string yielded `n_attempts=4`, `n_scored=1`, `excluded_null_source=1`, `excluded_invalid_source=2`, `coverage="single"`, and every aggregate diversity metric `null`. No uncollected/malformed attempt was scored as empty and no value was fabricated below two samples. |
| A2 expanded-neighbor commit gate | Re-executing the graph-expansion fixture produced candidates `['k_seed', 'k_measured_neighbor']` and selected the same pair. The expanded mismatched-commit SOURCE neighbor was absent from both candidates and selection; the mismatched MEASURED neighbor stayed eligible. This is enforced by `retrieval.py:1637-1644`. |
| Live lexical probe | In-cell, against `bolt://neo4j:7687` as required, a mismatched all-zero commit returned MEASURED records for `perturbed class semantic correctness`; the `spec-index-regeneration` query returned DERIVED and ADVISORY records; `docs-drift` returned ADVISORY and DERIVED records. The stale-SOURCE probe `relay_once` returned zero hits. No localhost endpoint was used. |
| Host dense artifact | `flash_exploration_retrieval_probe.json` has `generated_at`, `code_sha=693ded194...`, and resolved package/retrieval paths. It records direct `dense_hits=10` and `lexical_hits=10`, independently of `fallback_mode`. For both projection settings, `selected=48`, the per-type sum is `48`, `selected_evidence` has `48` entries, and `stale_source_selected` is empty. The runner and retrieval source are unchanged from `693ded194`. The artifact is internally consistent; F4 concerns an outage-path misstatement, not this successful capture. |
| Environment boundary | Chroma is host-side on `ai-infra`; cells are on `fleet-net` by design. The dense leg was not run in-cell and this is an environment fact, not a finding. The committed runner exercises real `retrieve()`, `ChromaStore`, and `_dense_filter`; the artifact provides direct per-leg counts. |
| Probe 5 artifact | `flash_exploration_verify.md:602-631` contains a syntactically complete heredoc command including its closing `PY` marker. Its raw output is in the separate `text` fence at `:634-662`. The document head labels Probes 1-4 as historical at `f3957a318` and Probe 5 as regenerated at `693ded194`, consistent with the round-3/round-4 remediation record. |

## Release Decision

**FAIL: do not mint or launch the ladder from this candidate.**

1. Repair F1 and F2, including adversarial C/JavaScript formatting and template-interpolation
   regression coverage.
2. Repair F3 as a separately attributed pre-existing ACL isolation defect; it must not be hidden
   by the otherwise-correct SOURCE commit gate.
3. Repair F4 and regenerate the host-side probe artifact.
4. Re-run the six-suite hermetic gate, the expanded-neighbor check, the in-cell live lexical
   probe, and an independent adversarial review on the repaired candidate.

## Repair Verification

**Verifier:** `openai/gpt-5.6-terra` (independent verification of the review-5 repairs only).
This pass intentionally did not open new attack surface. It checked R1-R4, the recorded
reachability/pattern regressions, and consistency between the host-side probe code and artifact.

| Repair | Direct evidence | Verdict |
|---|---|---|
| R1: parser-backed Python diversity contract | Direct execution returned null for every divergence axis, `scored: false`, and `reason: "unsupported_source"` for a JS/C pair. Python comment-only and formatting-only edits returned exactly `0.0`; a `return 1` to `return 2` change returned `0.03333333333333335`; and the headed multi-file `solution_code` blob returned `0.046153846153846156` for a semantic edit. `tests/test_diversity.py` covers these cases. | PASS |
| R2: portfolio coverage accounting | The direct mixed portfolio result was `n_pairs=3`, `n_scored_pairs=1`, `unsupported_pairs=2`, and `unsupported_fraction=0.6667`; its scored aggregate was unchanged from the Python-only pair. The JS/C portfolio returned `n_scored_pairs=0`, `unsupported_pairs=1`, `unsupported_fraction=1.0`, and null aggregates. | PASS |
| R3: direct and expanded ACL enforcement | The hermetic direct-lexical fake-graph test passed: foreign `private-b` evidence was absent from both candidates and selection under `private-a`, while matching ACL evidence was admitted. A separate execution using the same fake graph's expansion fixture excluded a foreign-ACL expanded neighbor and admitted a matching-ACL neighbor. The read-only live lexical probe against `bolt://neo4j:7687` returned `fallback_mode="lexical_graph_only"`, 40 candidates, 30 selected findings, and no stale SOURCE evidence. | PASS |
| R4: measured probe availability and provenance | `probe_retrieval_reachability.py` sets `dense_available` from `dense_hits is not None`, after the direct dense query, and records per-leg errors. The reviewed artifact has `generated_at`, code SHA `16ab8cb6bb7cdd67845ef4ee6559ccb68a44aed7`, resolved module paths, `dense_hits=10`, `lexical_hits=10`, two full-fallback runs, consistent selected-type totals, and no stale SOURCE selection. The relevant source files are unchanged from that SHA. | PASS |
| Regression check: reachability gate and pattern validity window | The hermetic suite includes the SOURCE-only commit gate, expanded-neighbor commit gate, pattern opt-in/scope gate, and pattern re-derivation stability checks. Same evidence remains byte-stable across order and source revision; changed evidence moves the validity window. | PASS |

**Hermetic gate:** `PYTHONPATH=src python3 -m pytest -q -p no:cacheprovider`
over `test_diversity.py`, `test_portfolio_scorer.py`, `test_retrieval.py`,
`test_context_plane_pattern.py`, `test_kb_produce_facts_integration.py`, and
`test_run_result_shape.py` completed with **152 passed, 1 skipped** in 1.43s. The focused
commit/pattern/ACL subset also completed with **5 passed**.

## Release Verdict

**PASS: R1-R4 are complete and internally consistent.** No scoped verification finding remains.
This verification accepts the repaired candidate as satisfying the review-5 repair contract; it
does not itself authorize the controller-only mint, launch, or release action.
