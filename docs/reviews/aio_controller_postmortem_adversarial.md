---
status: accepted
---

# AIO controller postmortem - adversarial review

**Reviewer role:** independent adversarial reviewer. This review attacks the corpus, taxonomy,
defense audit, remediation, replay evidence, and generated-surface blast radius rather than
accepting their self-reported completion logs.

**Evidence checked:** the committed p0-p5 documents (`d19ef95a9` through `b7cd6cf71`), Git
history, the host OpenCode pointers named by p0, installed code/tests, and live deterministic
commands. This is a review record, not a remediation: no production behavior was changed here.

## Release Verdict

**FAIL - not merge-ready.** The p5 claim that "all five are committed verified"
(`aio_controller_postmortem_verify.md:13-14`) is false at the selected-remediation scope.
R1 self-masks a same-day recording gap and does not cover most of the C4 failures attributed to
it. R5 checks a generated self-attestation rather than independently resolving fixture rows.
R2, the only selected response to the severity-5 destructive-store class, remains rule text
without a catching rail. Do not promote this branch until the findings below are either repaired
and replayed against the named historical signatures, or the documents retract the broader PASS
claims and explicitly park the uncovered classes.

## Finding Table

| ID | Severity | Finding | Evidence and adversarial result | Required disposition |
|---|---|---|---|---|
| A1 | P0 | **R1 self-masks the missing-decision condition it claims to catch.** | `session_close.py:259-280` writes the close before calling `_recording_check()`. `recording_sweep.py:131-148` then treats a day as covered when it has **either** a decision **or any close**. An unrecorded act followed by the current close therefore becomes covered by the close being checked. The p5 replay only creates an uncovered day with no same-day close (`tests/test_recording_sweep.py:73-106`); its close-probe tests mock `scan()` (`tests/test_session_spine.py:1001-1021`). | Retract R1 PASS. Re-design the coverage invariant so a close cannot satisfy the evidence check for the act it is auditing, then add an end-to-end same-day close regression and replay F-09. |
| A2 | P0 | **R1 is presented as C4 (F-08 through F-12) remediation but implements only a narrow F-09/F-01 backstop.** | The selected scope is explicitly "C4 (F-08...F-12) + C6" (`aio_controller_postmortem_remediation.md:25-31`). R1 adds rule text and the close-time sweep; it adds no producer attribution check for F-08, no binding of decisions to acts, no promotion-row check for F-11, and no pre-row workdir validation for F-12. The runner still opens its control row at `run_workflow.py:641-655`, constructs orchestrator executors at `:657-681`, and only seeds the heartbeat at `:704-725`; an exception in that interval leaves the historical no-heartbeat failure shape. | Split the C4 claim by signature. Add and replay a rail for each claimed signature, or reduce R1's scope to F-09/F-01 and mark F-08/F-11/F-12 uncovered. |
| A3 | P0 | **R5 is a static self-attestation guard, not the independent fixture-tier resolution assertion designed in p3.** | p3 requires that every current fixture registry row resolve to a payload or sanctioned waiver/tombstone and that one unresolvable fixture row fail (`aio_controller_postmortem_remediation.md:182-202`). The delivered test only parses committed `data.js` and asserts counters in its `resolution_report` are zero (`tests/test_build_data.py:770-800`); it loads no registry, payload, waiver, or corpus root. The negative replay mutates the report counter itself (`aio_controller_postmortem_verify.md:167-179`), not a registry row/payload. A stale or falsified all-zero report passes. | Retract R5's independent-resolution PASS. Either implement the fixture-tier resolver replay specified in p3, or rename R5 as an artifact-attestation guard and leave F-05's resolution defense partial. |
| A4 | P0 | **The severity-5 C1 class has no catching rail, contrary to the release requirement.** | F-03 is independently real: `git diff --numstat 9bdb74059 9e4773fb1 -- experiments/results/registry_index.jsonl` returns `1 43311`; historical blobs are `48321` then `5011` lines. But R2 deliberately supplies rule text only (`aio_controller_postmortem_verify.md:88-102`). A directive may be clear, but it does not catch/block a future destructive merge, dedup, or index operation. | Do not claim the top classes have catching rails. Either implement a bounded existing-gate extension for the active durable-store path or explicitly accept C1 as a residual and keep the release verdict FAIL. |
| A5 | P1 | **The corpus labels an unsupported quantity as verified evidence.** | F-01 says the main checkout was "~292 files dirty" (`aio_controller_postmortem_corpus.md:95-100`) while the corpus globally states 19 verified items and zero unverified claims (`:14-18`). The retained opening hammer `git status` pointer contains 237 tab-indented paths (1 modified plus 236 untracked); no cited retained surface establishes 292. The abandonment and uncommitted-wave core are supported, but this quantity is not. | Correct the count to the evidenced value, qualify it as an estimate with a source, or move the unsupported detail to an unverified note. Re-run the corpus completeness claim afterward. |
| A6 | P1 | **The taxonomy's C6 minimum-size claim is inflated by splitting one incident chain.** | C6 has exactly F-01 and F-02 (`aio_controller_postmortem_taxonomy.md:43-49,57-58`), both the same hammer session and same 19-hour, uncommitted abandonment arc (`aio_controller_postmortem_corpus.md:78-133`). They are distinguishable symptoms, but not two independent real incidents. The stated class-size test is therefore satisfied only by row splitting. | State whether the threshold counts corpus rows or independent incident chains. If it requires independent incidents, reclassify C6 as a singleton/rare class or find a second independent C6 event. |
| A7 | P1 | **The recording rail is operationally inconsistent with its own unmeasured claim.** | On this branch, `python3 -B scripts/recording_sweep.py --scan` reports `GAPS: 12 uncovered day(s)` and exits 1 because the runtime KB data is absent. By contrast, only the `session_close` wrapper recognizes that absence as `unmeasured` (`tests/test_session_spine.py:975-999`). `recording_sweep.py:48-84` itself treats a missing artifact directory as zero decision/close coverage. A nightly run from a source checkout can therefore produce false gaps and backfill reconstructions without evidence. | Make the sweep itself return an explicit unmeasured result on absent runtime data, and ensure report/backfill modes refuse mutation while unmeasured. Replay the source-checkout condition. |

## Corpus And Taxonomy Re-verification

The four required incidents are present with actionable primary pointers:

- The Sep-4 registry drain (F-03) is in p0 with Git and transcript pointers; the Git numerical
  proof above confirms the severity-5 loss.
- The dedup over-deletion (F-04) is in p0 with the 48,324 to 20,132 transcript output and the
  self-correction/restore pointers (`aio_controller_postmortem_corpus.md:159-186`).
- The `git add -A` re-track (F-06) is in p0 with the ordered command and the 32,311-file recovery
  pointer (`:212-235`).
- The launch improvisation (F-13) is in p0 with write, controller objection, and deletion
  timestamps (`:366-381`); no committed `scripts/launch_workflow.py` exists.

No required severity-5 item was absent: F-03 is present and primary-evidenced. The severity-5
corpus issue is precision, not omission: F-01's dirty-file count is not established by the cited
evidence (A5). The taxonomy arithmetic is internally consistent (19 rows; six classes with at
least two rows plus Rare), but A6 shows that its C6 threshold does not demonstrate two independent
incidents.

## Defense And Replay Re-verification

The review agrees with two narrow clean claims:

- R3 is a genuine replay: the wired `scan_docs_drift.py --check spec_lifecycle --fail-on-drift`
  fails against historical `24837b7d0`, names `README.md:96`, and is clean at HEAD. It catches the
  F-19 generated-surface signature, not direct-main F-16.
- R2 and R4 are imperative doctrine, not suggestions: the rendered rules use "must", "never",
  "is a violation", "do not", and named commands. That is useful policy, but it is not a catching
  rail and cannot satisfy a release claim that the top classes are mechanically caught.

The implementation's targeted tests pass but do not falsify A1-A3: `82 passed, 3 skipped` across
the R1/R5-related test files. `python3 scripts/_gen_instructions.py --check` also passes (38
generated surfaces match). This validates render blast radius only; it does not validate the
semantic coverage promised in the p5 verification document.

## Reproduction Log

```text
$ git diff --numstat 9bdb74059 9e4773fb1 -- experiments/results/registry_index.jsonl
1       43311   experiments/results/registry_index.jsonl
$ git show 9bdb74059:experiments/results/registry_index.jsonl | wc -l
48321
$ git show 9e4773fb1:experiments/results/registry_index.jsonl | wc -l
5011

$ python3 -m pytest tests/test_recording_sweep.py tests/test_session_spine.py \
    tests/test_build_data.py -q -p no:cacheprovider
82 passed, 3 skipped
$ python3 scripts/_gen_instructions.py --check
surfaces OK - 38 generated files match agent_config/
$ python3 -B scripts/recording_sweep.py --scan
GAPS: 12 uncovered day(s)
exit 1
```

## Completion Log

- **Required worst incidents checked:** PASS, with A5's count qualification.
- **At least three evidence-grounded findings:** PASS (A1-A7).
- **Blast-radius render check:** PASS (generated surfaces clean).
- **Top classes have catching rails:** FAIL (A1-A4).
- **Nothing unverified shipped:** FAIL (A1-A3 and A5).
- **RELEASE VERDICT:** **FAIL - not merge-ready.**
- **LOG:** FAIL.
