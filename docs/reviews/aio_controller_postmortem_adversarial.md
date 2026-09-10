---
status: accepted
---

# AIO Controller Postmortem: Final Adversarial Re-Review

**Reviewer:** independent adversarial review (terra)

**Scope:** convergence repair `96958a4d5` (A5 and B1-B4). This review tests the
claims against the primary transcript, committed history, implementation, and executable
guards. A rail is credited only for the signature its implementation actually refuses.

## Finding Table

| ID | Severity | Finding | Evidence | Release effect |
|---|---|---|---|---|
| F1 | P0 | The B1 rail is a raw-row-count drain guard, not full-row or lifecycle-marker conservation. It rejects the supplied marker-loss fixture, but it cannot tell a lost marker from a lost ordinary row, and a marker can be replaced by an unrelated valid row with the count unchanged. | `scripts/generate_manifest.py:279-292` counts `_iter_registry_rows`; `:345-361` compares only integer counts; `:438-463` refuses only a count decrease. `tests/test_generate_manifest.py:406-458` proves the narrow `2 -> 1` count-drop signature. `verify.md:186-228`, `:459-460`, and the release log call this "full-row/lifecycle-marker conservation." | **FAIL.** The shipped assertion is false. Rename and bound the rail as a raw-source-row-count drain guard, or preserve and compare row identities/content if full-row conservation is intended. |
| F2 | P0 | The release predicate says R1 catches its scoped class, although its own scope table says F-01 is only "covered by doctrine (no catching rail)" and F-08/F-11/F-12 are not R1 catches. The exercised same-day recording test is an F-09 test, not an abandonment/no-close interception. | `verify.md:121-141` states the exclusions; `:131` explicitly says no catching rail for F-01; `:492-493` nevertheless says the scoped rails, including R1, demonstrably catch their class. | **FAIL.** The R1 release claim must be narrowed to F-09's tested same-day-recording signature. F-01 must remain a policy/detection residual unless a rail actually catches no-close abandonment. |
| F3 | P0 | The same release predicate overstates R3 and R5 from a signature-level replay to class-level coverage. R3 reproduces README/index drift F-19 only; it does not catch F-15 wrong-command selection or F-16 direct-main work. R5 exercises a three-row fixture for F-05 only; it does not catch the C5 mount-provenance or heartbeat-TTL signatures F-17/F-18. | R3 replay is only F-19 at `verify.md:241-260`; C3 still includes F-15/F-16 at `taxonomy.md:56, 73, 82-86`. R5 fixture scope is stated at `verify.md:302-320`; C5 includes F-17/F-18 at `taxonomy.md:58, 84-85`. The class-level claim remains at `verify.md:492-493`. | **FAIL.** The predicate must name individual covered signatures, not the broader C3/C5 classes, or add and replay the missing class rails. |
| F4 | P1 | The A5 primary pointer resolves and proves an opening snapshot of 237 tab-prefixed status rows. It does not prove that those same files remained dirty for four days, so the corpus duration wording exceeds its cited evidence. | Read-only query of `opencode.db` part `prt_06d0793c6001c5VS663QZ6oYh4`: 1 modified + 236 untracked = 237. The unsupported persistence wording is `corpus.md:95-103`. | Bound the statement to the 2026-09-04 opening snapshot, plus the separately proven no-git-activity interval. Do not infer unchanged dirty paths across that interval. |
| F5 | P1 | The taxonomy now honestly distinguishes row count from independent incident count. C2 and C6 each have two genuine corpus rows but only one connected incident chain, so they do not satisfy a two-independent-case standard. | `taxonomy.md:17-26`, `:143-149`, and `:238-243`; the same caveat appears at `verify.md:354-368`. | **PASS, corrected.** No independent-case over-claim remains if all threshold language retains the row-count qualifier. |
| F6 | P1 | R4 and the F-06 re-track vector are honestly retained as residuals rather than counted as catching rails. | `verify.md:214-225`, `:264-291`, and `:461-475`. | **PASS, corrected.** |

## Corpus Result

The four requested worst items are present with first-hand pointers:

- The hammer snapshot is the retained transcript part above; it establishes 237 status rows.
- The registry dedup transcript records `48324 -> 20132`, admits marker loss, then shows a
  restoration and full-row-equality rededup: `corpus.md:166-193`.
- The re-track transcript and the cleanup commit are recorded at `corpus.md:219-242`; commit
  `ab887b5c8` changes 32,312 files and removes 15,620,993 lines.
- The launch improvised draft, controller objection, and deletion are separately pointed at
  `corpus.md:373-388`.

The only severity-5 item is F-03. It is present, and the committed comparison confirms the
claimed drain: `9bdb74059 -> 9e4773fb1` is `+1/-43311` lines, with 48,321 source lines before
and 5,011 after. No severity-5 corpus item is absent.

## Executed Verification

| Check | Result |
|---|---|
| `test_registry_source_row_guard_refuses_marker_line_loss` | PASS, 1 passed. The guard rejects the precise marker-line count-drop fixture. |
| Fixture-tier publication resolver test | PASS, 1 passed. This is a fixture-scale F-05 check. |
| Recording, manifest, doc-lifecycle, agent-config, and session-spine tests | PASS, 112 passed. |
| `python3 scripts/scan_docs_drift.py --check spec_lifecycle --fail-on-drift` | PASS, drift score 0. |
| `python3 scripts/_gen_instructions.py --check` | PASS, 38 generated surfaces match. |
| `ruff check scripts/generate_manifest.py tests/test_generate_manifest.py` | PASS. |

These checks show that the repair did not break the exercised existing surfaces. They do not
convert a count-only guard into full-row conservation or a signature-level replay into
class-level coverage.

## Final Verdict

**FAIL - not merge-ready.** A5 resolves, B1's named marker-loss fixture is caught, B2/B3 are
honestly residual, B4 states its row-count basis, and generated surfaces are clean. However,
`verify.md` still contains false shipped assertions: the B1 count guard is labeled full-row /
lifecycle-marker conservation, and the release predicate claims R1/R2/R3/R5 catch their
classes despite explicitly uncovered or doctrine-only signatures. The release predicate must
be rewritten to enumerate only demonstrated signatures before this postmortem can be released.

## Required Correction

1. Replace every B1 "full-row" or general "lifecycle-marker conservation" claim with
   "raw valid source-row-count drain guard," including its equal-count replacement limitation.
2. Replace `verify.md`'s class-level release predicate with signature-level coverage: R1/F-09,
   R2/F-03 and the count-decrease form of F-04, R3/F-19, and R5/F-05 fixture resolution.
3. Bound F-01's dirty-tree claim to the measured opening snapshot; retain the no-git-activity
   interval as separate evidence rather than asserting path persistence.

**LOG:** FAIL.
