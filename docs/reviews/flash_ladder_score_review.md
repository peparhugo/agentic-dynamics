---
status: accepted
---
# Flash Ladder Round-1 Score Review

**Verdict: PASS (score and decision).** Independent replay from the committed
`experiments/ladder_evidence/round1/` exports reproduces every quality, diversity,
exclusion, bootstrap, delta, and decision value in `score_round1.json`. No number is
wrong, no cell is misclassified by the registered scorer, the pristine restoration is
faithful, and the recorded `FLAT` decision follows the pre-registered rule.

## Scope And Method

This review used only the committed round-1 score, 12 cell records, and generated
`taskman` source exports; it did not read `experiments/results` or host `/tmp` runtime
evidence. It ran:

```bash
python3 scripts/score_flash_ladder.py \
  --cells experiments/ladder_evidence/round1 \
  --base-sha 121126dfbcd65a656883e3f3cc81b12e612aeeeb \
  --out /tmp/opencode/flash_ladder_recomputed.json
```

The scorer collects every supported layout (`taskman/`, `src/taskman/`, or
`taskman.py`), restores `tests/flash_ladder/taskman_contract_test.py` from the pinned
base, and calls `portfolio_diversity` for the composite `0.4 * architecture + 0.3 *
structure + 0.3 * novelty`. The full base SHA resolves to
`121126dfbcd65a656883e3f3cc81b12e612aeeeb`; its contract-test SHA-256 is
`57ffac37664d2ae85d370a8363b46362221c18b6bfd0f1f3ed41c5616d9fe022`, identical to
the checked-out file. This confirms that the restored pristine test was the pinned
base test, not a substituted test.

`python3 -m pytest tests/test_flash_ladder_scoring.py tests/test_diversity.py -q -p no:cacheprovider`
also passed: **20 passed**.

## Recomputed Score

| Condition | Valid / exclusions (recorded = recomputed) | Pristine Q (recorded = recomputed) | Pristine tests | D (recorded = recomputed) | 95% CI | Scored / unsupported pairs | Distinct fraction |
|---|---:|---:|---:|---:|---:|---:|---:|
| C0 | 3/3, 0/0 | 3 = 3 | 13/13 in each of C0-r1..r3 | 0.3570757005306961 = 0.3570757005306961 | [0, 0.35707570053069615] | 3 / 0 | 0.0 |
| C1 | 3/3, 0/0 | 3 = 3 | 13/13 in each of C1-r1..r3 | 0.36255016332370044 = 0.36255016332370044 | [0, 0.36255016332370044] | 3 / 0 | 0.0 |
| C2 | 3/3, 0/0 | 3 = 3 | 13/13 in each of C2-r1..r3 | 0.40715594922110765 = 0.40715594922110765 | [0, 0.4071559492211077] | 3 / 0 | 0.0 |
| C3 | 3/3, 0/0 | 3 = 3 | 13/13 in each of C3-r1..r3 | 0.4193636366716957 = 0.4193636366716957 | [0, 0.4193636366716957] | 3 / 0 | 0.0 |

All 12 exports contained a discovered package source, including the `src/taskman/`
layout in C3-r2. All three pairwise comparisons per condition were parser-supported;
there were no null sources, invalid sources, or unsupported pairs. Therefore the
score's full coverage and zero excluded/unsupported accounting are correct.

## Cell Validity And Provenance

| Check | Raw result | Review result |
|---|---|---|
| Assignment coverage | Exactly C0-r1..r3, C1-r1..r3, C2-r1..r3, and C3-r1..r3 records are present. | PASS |
| Test integrity | Every record says `tests_changed: false`; the base-restored contract ran 13/13 in every exported tree. | PASS |
| Export availability | All 12 record-named export directories contain discoverable Python `taskman` source. | PASS |
| Recorded run status | All 12 records say `status: ok`, `exit_code: 0`, `run_state: succeeded`, and `test_executed_success: true`. | PASS |
| Run-SHA traceability | The 12 abbreviated `git_sha` values are recorded, but none resolves to a Git object in this clone; the base SHA does resolve. | LIMITED: commit identity/ancestry cannot be replayed from the frozen inputs. |
| Ledger traceability | Each record supplies a ledger pathname under `/tmp/wt_flash_exploration/...`; no ledger payload is included in the committed evidence. | LIMITED: ledger-derived cost, token, and augmentation fields cannot be independently replayed. |

The two limited provenance checks do not affect the registered validity predicate or
the recomputed Q/D score: the scorer defines a valid cell as a present source export
with `tests_changed: false`, and computes Q from the independently restored contract.
They are recorded here to avoid treating unavailable ledger or commit objects as
verified evidence.

## C3 Augmentation State

| Field | Recorded score | Raw-export recomputation |
|---|---|---|
| `fallback_mode` | `lexical_graph_only` for C3-r1, C3-r2, and C3-r3 | Unavailable: the value is ledger-derived and the referenced ledgers are not committed. The raw replay therefore returns null per cell / `['']` at condition level. |
| Selected evidence count | Not present in `score_round1.json` or any C3 record. | Unavailable: the only references are to absent ledger files. |

This is a data-availability statement, not a score discrepancy: neither field enters
Q, D, the exclusion accounting, or the pre-registered escalation rule.

## Decision Arithmetic

Section 4 of
`docs/experiments/preregistrations/flash_exploration_preregistration.md` requires
`delta_D = D_c - D_C0`, `delta_Q = Q_c - Q_C0`, and escalation only when any
`abs(delta_D) >= 0.10` or `abs(delta_Q) >= 1`.

| Comparison | Recomputed delta_D | Recomputed delta_Q | Threshold reached? |
|---|---:|---:|---|
| C1 - C0 | 0.005474462793004342 | 0 | No |
| C2 - C0 | 0.050080248690411555 | 0 | No |
| C3 - C0 | 0.06228793614099959 | 0 | No |

The largest absolute diversity effect is C3, `0.06228793614099959`, below `0.10`.
All quality deltas are zero, below `1`. The recorded verdict is therefore correctly
**FLAT** with the registered directive: "flat within the registered margin; no policy
claim." No confirmatory escalation is warranted by this round.
