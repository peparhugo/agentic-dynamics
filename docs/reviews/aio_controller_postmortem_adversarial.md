---
status: accepted
---

# AIO controller postmortem - adversarial re-review after p5 repair

**Reviewer role:** independent adversarial reviewer. This re-review tests repair commit
`26e2ed7ed3f1751725127c1f8b8fb3e9dd16baf2` against the original A1-A7 findings and the g10
fast-path budget. It treats a passing unit test as evidence for its exact invariant, not as
evidence for a broader class claim.

**Method:** inspected the p0 corpus, taxonomy, p5 verification claims, repair implementation,
and regression tests; replayed the named test paths and generated-surface guard. Historical
Git evidence was rechecked directly. Host OpenCode transcript pointers remain the primary
evidence for local, uncommitted incidents; the committed corpus preserves their identifiers.

## Release Verdict

**FAIL - not merge-ready.** The repair genuinely fixes A1, A2, A3, A6, A7, and the g10 budget
gate. It also adds a bounded F-03 drain defense, so A4's former "no rail at all" premise is no
longer true. But the release claim remains too broad: R2 cannot catch the F-04 marker-line
dedup signature it says it catches, R4 remains directive-only and cannot stop the create-then-
delete launcher signature, and the F-06 re-track vector has no index/commit catching rail.
The corrected dirty-file count is still missing its promised primary `git status` pointer in the
corpus evidence list. These are shipped assertions and release predicates, not merely future
enhancements.

## A1-A7 And Budget Table

| ID | Verdict | Re-verification | Residual or correction |
|---|---|---|---|
| A1 - R1 self-masking | **REPAIRED** | `recording_sweep.scan()` now requires a decision on day D or a close strictly later than D. The real `session close` replay is exercised by `TestRecordingProbe::test_same_day_close_cannot_cover_its_own_audit`; the focused suite passed. | This is detective and best-effort: `session close` still writes successfully after reporting a gap, and a session that never closes is not caught at close time. That limitation does not re-open the same-day self-mask. |
| A2 - C4 claim split | **REPAIRED** | `aio_controller_postmortem_verify.md:96-116` separates F-09, F-01, F-08, F-11, and F-12. F-08 is explicitly uncovered; F-11 is explicitly not R1; F-12 is explicitly partial. | F-01 remains doctrine rather than a catching rail. F-11's row-close mechanism is not a substitute for an R1 claim, as the repaired text now admits. |
| A3 - R5 resolver | **REPAIRED** | `test_fixture_tier_resolver_resolves_every_current_row_and_fails_on_one_unresolvable` drives `canonical_corpus.load_canonical_tables` over manifest rows and real fixture payloads, then removes a payload and names `("story", "s1")`. The replay passed. | This is a synthetic hermetic fixture, not a replay of the committed 402/407-row corpus and not a waiver case. It supports the narrow fixture-resolver claim, not a full-corpus resolution claim. |
| A4 - C1 catching rail | **REPAIRED, BOUNDED** | `generate_manifest.py` refuses a compacted version-count shrink against a valid previous manifest. `test_registry_drain_guard_refuses_a_smaller_compaction` passed within the focused suite. This catches the F-03 drain at that seam. | The p5 statement that the same rule catches F-04 is false; see B1. Raw index edits, a missing/corrupt baseline, and `--allow-shrink` remain outside the catch. |
| A5 - dirty-file count | **STILL OPEN** | The text was corrected from unsupported `~292` to `~237` (1 modified + 236 untracked) in `aio_controller_postmortem_corpus.md:95-102`. | The evidence list at `:105-114` does not identify the retained opening `git status` transcript part that establishes 237. The value is plausible and independently recoverable from the host transcript, but it is not yet self-contained primary evidence as the corpus claims. |
| A6 - class counting | **REPAIRED** | `aio_controller_postmortem_taxonomy.md:17-21,226-231` explicitly says the threshold counts corpus rows and that C6's two rows are one independent incident chain. | C2's F-13/F-14 acts are also causally connected, so the taxonomy should not imply all C1-C5 pairs are independent without separate support. The stated row-count gate itself is now honest. |
| A7 - absent-data sweep | **REPAIRED** | In this source checkout, `python3 scripts/recording_sweep.py --report` returned `UNMEASURED`; `experiments/results/recording/audit.json` remained absent. The code returns before report/backfill writes, and the focused regression suite passed. | No dedicated CLI test asserts the report file remains absent, although the direct replay and control flow confirm it here. |
| g10 - fast-path budget | **REPAIRED** | `python3 -m pytest tests/test_fast_path_gate.py -q -p no:cacheprovider` passed: **3 passed in 32.68s**. That test invokes the fast subset and enforces its 180-second budget. | The fast-marker audit is syntax/regex based, so alternate marker or corpus-dependency shapes can evade it. The p5 prose also says "two" corpus modules while naming three (`verify.md:323-326`). |

## Fresh Adversarial Findings

| ID | Severity | Finding | Evidence and falsification | Required disposition |
|---|---|---|---|---|
| B1 | P0 | **R2 overclaims F-04 coverage.** | `generate_manifest.py` compacts rows sharing a `knowledge_id` before `detect_registry_drain()` counts versions. F-04 deleted tombstone/supersede marker lines that deliberately share that id with their target (`aio_controller_postmortem_corpus.md:161-188`). The counter can therefore remain unchanged while those lifecycle lines are lost. `verify.md:152-154` says the guard catches F-04; it does not. | Retract the F-04-catching assertion. Either add a full-row/lifecycle-marker conservation assertion at the durable-store mutation seam, or explicitly retain F-04 as uncovered. |
| B2 | P1 | **R4 is still doctrine, not a catching defense for launch improvisation.** | `verify.md:200-221` correctly says "Rail: none selected." Script classification catches an unclassified file only if it survives; F-13 was written and deleted after the controller objected. The rule is directive and valuable, but it would not have stopped the actual transcript moment. | Keep R4 as an explicit policy residual, not a PASS that contributes to a "top classes have catching rails" release condition. Add a pre-creation/new-mechanism gate only if the existing documented path can host it. |
| B3 | P1 | **F-06's re-track path is asserted retired without an index/commit catch.** | The corpus migration and `.gitignore` prevent ordinary re-adds, but do not prevent force-staging or an ordering error before ignore state lands. The repository's own `test_relabel_tree_gate.py` uses `git add -Af`, demonstrating the index can still be forced. `verify.md:159-162` therefore overstates C1 protection. | Mark F-06 residual. Extend an existing staged-tree or commit gate only if it can reject tracked `experiments/results/**` without creating parallel machinery. |
| B4 | P1 | **The C2 two-item claim is a row count, not evidence of two independent incidents.** | F-14's wrapper produced the F-12 failed launches, and F-12 triggered F-13's launcher draft (`aio_controller_postmortem_corpus.md:351-403`). They are two real acts, but one connected improvisation chain. | Preserve C2's row-count classification, but do not use it as independent-incident evidence without an explicit counting-basis statement matching C6. |

## Corpus And Taxonomy Re-verification

The requested worst items are present and point to primary evidence:

- **Hammer:** F-01 records the 1 modified + 236 untracked basis and the abandoned session
  (`aio_controller_postmortem_corpus.md:80-114`). The numerical statement needs the missing
  exact transcript-part citation noted in A5.
- **Registry drain:** F-03 is severity 5 and Git-reproducible. The direct replay produced
  `1 43311` for `git diff --numstat 9bdb74059 9e4773fb1 -- registry_index.jsonl`; the blobs are
  48,321 and 5,011 lines respectively.
- **Registry dedup:** F-04 gives the 48,324 to 20,132 transcript result, self-correction, and
  full-row-equality recovery pointer (`corpus.md:161-188`).
- **`git add -A` re-track:** F-06 names the ordered command, the immediate admission, and the
  32,312-path recovery commit (`corpus.md:214-237`).
- **Launch improvisation:** F-13 names write, controller objection, and deletion timestamps;
  no committed `scripts/launch_workflow.py` exists (`corpus.md:368-383`).

No further severity-5 event was found in the corpus's declared 2026-09-04 through 2026-09-10
window. F-03 is the sole documented severity-5 item. A pre-window one-line registry collapse
is relevant historical context but is not an omission under that bounded corpus definition.

All classes have at least two **rows** except Rare. The taxonomy now explicitly distinguishes
rows from independent chains for C6, which repairs A6. C2 needs the same caution (B4); it is
not force-fit, because F-13 and F-14 are distinct real actions, but neither proves two unrelated
incidents.

## Reproduction Log

```text
$ PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
    tests/test_recording_sweep.py tests/test_session_spine.py::TestRecordingProbe \
    tests/test_generate_manifest.py tests/test_build_data.py \
    -k 'not test_build_data' -q -p no:cacheprovider
33 passed, 34 deselected in 1.06s

$ PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_build_data.py \
    -k fixture_tier_resolver -q -p no:cacheprovider
1 passed, 33 deselected in 0.19s

$ PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_fast_path_gate.py \
    -q -p no:cacheprovider
3 passed in 32.68s

$ python3 scripts/recording_sweep.py --report
recording_sweep: UNMEASURED - no KB artifact dir on disk; refused to report or backfill
# experiments/results/recording/audit.json: absent after the command

$ python3 scripts/_gen_instructions.py --check
surfaces OK - 38 generated files match agent_config/

$ git diff --numstat 9bdb74059 9e4773fb1 -- experiments/results/registry_index.jsonl
1       43311   experiments/results/registry_index.jsonl
$ git show 9bdb74059:experiments/results/registry_index.jsonl | wc -l
48321
$ git show 9e4773fb1:experiments/results/registry_index.jsonl | wc -l
5011
```

## Completion Log

- **A1-A7 and g10 re-verified:** PASS with A5 still open and the stated bounded residuals.
- **At least three fresh evidence-grounded findings:** PASS (B1-B4).
- **Blast-radius generated-surface check:** PASS.
- **Top classes have complete catching rails:** FAIL (B1-B3).
- **Nothing unverified shipped:** FAIL (the F-04 and F-06 coverage claims overstate the rails).
- **RELEASE VERDICT:** **FAIL - not merge-ready.**
- **LOG:** FAIL.
