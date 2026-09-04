---
status: accepted
kind: review
spec: promote_row_closeout
phase: g9_adversarial
generated_at: 2026-09-04T14:40:09Z
---

# promote_row_closeout - adversarial review (g9)

**Independent falsification** of the promote row close-out, run in a different session/model
(`openai/gpt-5.6-terra`) from the flash author. The review target is branch
`feature/promote-row-closeout` at `41533eda0` (`p0_pin_defect` ->
`a1_close_row_on_success` -> `a2_stale_candidate_guard`). Nothing below is accepted on the
author's claim: every result was re-derived against the current code and isolated synthetic
repositories/control databases. A bare PASS would fail this review; the three concrete failures
in the finding table are blocking and make the release verdict **NOT MERGE-READY**.

The reviewer phase is `adversarial_readonly`: it may create this review and throwaway probes, but
does not alter production code. Each failure is therefore recorded with a precise remediation;
none is accepted for release as an intentional limitation.

## 1. Attack results that hold

The requested positive paths are real. They are not sufficient for release because the negative
attacks in section 2 fail, but they establish exactly what the current code does correctly.

| Attack | Independent probe and result |
|---|---|
| Landed push closes its row | A fresh candidate one commit ahead of `main`, a fake push returning `ffff...`, and a real temporary `ControlDB` row produced `LANDED_CLOSE: merged [('promotable', 'promoting', 'promote'), ('promoting', 'merged', 'promote')] 1`. The row reaches `merged`, both legitimate transition hops are append-only, and one promotions row exists. |
| Control DB fails after the push | A fresh candidate plus a DB path below a regular file printed `WARNING - could not close control row run-outage ... close-out sweep remains the backstop - the push has landed and stands`, then returned normally. The push is not unwound. |
| Dry run does not write the row | A promotable row before the dry run remained `promotable`, with its original three transitions and zero promotions afterward: `DRY_DB_FREE: promotable 3 0`. |
| Base-head stale branch refuses before push | A branch forked from base v1, re-committed to main's v2 tree, and therefore tree-identical but not an ancestor of main, raised `stale candidate`; the fake push was never called and the seeded row remained `promotable` with zero promotions: `STALE_PRE_PUSH: True push_calls=0 promotable 0`. |
| Idempotence / fresh candidate | Targeted suite: `test_a1_default_close_row_is_idempotent_when_already_merged` and `test_a2_genuinely_new_candidate_still_promotes` both pass. The former does not add a second transition/promotion; the latter reaches the fake push and close seam. |

The six direct target tests covering those paths all passed:

```text
tests/test_promote.py::{a1 default close, a1 db outage, a1 dry run,
                        a1 idempotence, a2 stale real-shot, a2 fresh candidate}
6 passed in 0.35s
```

## 2. Finding table

| # | Severity | Attack | Finding | Evidence | Disposition |
|---|---|---|---|---|---|
| F1 | High | Row binding | `_default_close_row` accepts an empty `runs.candidate_sha`. `row_sha = ...` at `scripts/promote.py:348-349` guards a mismatch only when the field is non-empty, then the code transitions and records a promotion at `:362-397`. A pre-candidate/legacy `promotable` row can therefore be recorded as the pushed candidate without any candidate binding. | Real temporary DB: seeded `candidate_sha=''`, then called `_default_close_row(... candidate_sha='a'*40 ...)` -> `EMPTY_SHA: {'closed': True, ...} merged 5 1`. The run acquired two close transitions and a promotion row for a tree it had never named. | **BLOCKER - fix required.** Fail closed when `run.candidate_sha` is empty or ambiguous. Bind it against the ledger's persisted candidate identity (not merely an arbitrary prefix of the live HEAD) before either transition or `record_promotion`. This directly violates a1's required ledger run-id + pushed-sha binding. |
| F2 | High | Missing control plane | `_default_close_row` opens `ControlDB.open(db_path)` at `scripts/promote.py:337-339`. Writer `open` creates a missing DB, so a typo or absent `--db` does not produce the promised outage warning alone: it creates a durable empty control plane and reports `unknown_run`. The documented distinction between a missing DB (exit 3) and a quiet DB is erased. | Called `_default_close_row` with nonexistent `<tmp>/missing/control.db` -> `MISSING_DB: {'closed': False, 'reason': 'unknown_run'} created=True`. The path did not exist before the probe and existed afterward. | **BLOCKER - fix required.** Resolve the path and open it with `create=False` (or an explicit existing-path check followed by a non-creating writer). On absence, warn with the run id and sweep backstop while leaving no database behind. |
| F3 | Medium | Dry-run truthfulness | The stale guard deliberately exempts an ancestor/equal candidate at `scripts/promote.py:774-775`. Because dry-run returns at `:526-541` before the later empty-diff check at `:543-549`, `HEAD == main` prints "would squash-merge + push" while the identical real invocation refuses `candidate has no changes vs the base`. The existing happy-path fixture codifies this topology: `tests/test_promote.py:109-122` creates `main` at candidate HEAD. | Same-commit synthetic repo: dry-run printed `verified ... would squash-merge + push`; real mode raised `candidate has no changes vs the base - nothing to promote`, `push_calls=0`. The plan is therefore not a truthful projection of the real command. | **BLOCKER - fix required.** Run the non-mutating merge-base/empty-diff preflight before the dry-run return, so both modes refuse the no-op. Replace the degenerate existing happy fixture with a genuinely-new candidate ahead of main; a dry run must not bless an invocation real mode rejects. |

### Finding rationale

F1 is a false-history risk, not a cosmetic validation omission: the transition log and promotions
table would state that an unbound run produced a specific merged tree. F2 is a control-plane
integrity risk: later readers can observe a newly created empty DB rather than the truthful
"control database unavailable" state. F3 makes the controller's safe preview misleading; it
offers a promotion that the real command refuses without a push. Each is independently
reproducible in one attempt and remains unpatched because this phase is review-only.

## 3. Leak and order check

The intended ordering itself is correct on the normal path: `_run_promotion` calls `push` at
`promote.py:565-567`, then calls the `close_row` seam at `:573-585`. The stale refusal is before
both at `:508-516`; the real-shot stale probe proves no push, transition, or promotion row is
created. A raised close seam is swallowed by `_close_row_best_effort` (`:414-429`), so a landed
push stands. Re-running an already-merged row is idempotent because `_default_close_row` exits
at `run.state != PROMOTABLE` (`:362-372`), and the targeted test confirmed transition and
promotion counts do not grow.

Those passes do not neutralize F1-F3: they cover a correctly bound, existing database and a
non-degenerate candidate. The review deliberately varied exactly those assumptions.

## 4. Release verdict

**NOT MERGE-READY.** The nominal graph-leg stale-promotable class is improved on the happy path:
successful pushes close bound rows, tree-identical divergent candidates refuse, dry-run itself
does not write, and an unavailable database after a push does not unwind it. But the class is
not closed safely enough for main:

1. An unbound `promotable` row can be marked merged for arbitrary content (F1).
2. A missing DB can be silently materialized as a new empty control plane (F2).
3. Dry-run can still advertise a promotion that real mode rejects (F3).

Required next implementation pass: fail closed on empty/ambiguous row SHA binding; make the
post-push close open an existing DB only; move the no-change preflight before dry-run and give
the happy test a real candidate-vs-base topology. Re-run this review's four probes plus
`tests/test_promote.py` after those fixes. The controller alone decides whether the repaired
branch is then merged to main.
