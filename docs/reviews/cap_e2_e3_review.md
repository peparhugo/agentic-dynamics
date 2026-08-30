---
status: accepted
---

# CAP E2/E3 Run — Sonnet-5 Adversarial Review (a1_review_e2_e3)

**Reviewer:** claude-sonnet-5, `feature/cap-sonnet-adversary` phase `a1_review_e2_e3`
**Target:** `feature/cap-e2_cascade_run` (spec names it `feature/cap-e2-cascade-run`; the actual
branch uses underscores — a cosmetic name mismatch, not a missing branch, confirmed by
`git rev-parse` below).
**Target commits:** `ef2ef3d2f` (e1_cascade_simulation), `84f3fb9a2` (e2_coverage_impact),
`f6274020b` (e3_writeup), on top of shared base `6cdefa102`.
**Method:** every artifact re-derived independently in the branch's own worktree
(`/tmp/wt_e2_cascade_run`, checked out at `f6274020b`) — both evaluator scripts were re-run live
against the on-disk corpus and diffed byte-for-byte against the committed JSON artifacts; every
number quoted in the writeup doc was cross-checked against the regenerated JSON, not trusted from
prose; source code (`model_cascade` call sites, CLI dispatch table, `.gitignore`, `compute_routing`
eligibility logic) was read directly, not assumed from the doc's claims.

## Verdict: **PASS, with one mandatory fix**

The branch exists, has committed all three expected `[workflow]` phases, and its two headline
artifacts (`cap_cascade_retrospective.json`, `cap_coverage_routing_impact.json`) reproduce
byte-identically from a live re-run of their generating scripts. The writeup's honesty discipline
(coverage-first, counterfactual-only, null-not-zero, regret-is-a-tautology-not-a-safety-signal) is
real and enforced by the code, not just asserted in prose — I found the one place where it slipped.
No fabricated numbers, no silently-zeroed uncaptured data, no mislabeled INCONCLUSIVE-as-PASS.

## Findings (re-verified)

| # | Finding | Severity | Evidence |
|---|---|---|---|
| 1 | **§1.6 job-status trigger-rate figure is wrong: doc says "30.0% of confidence-captured phases in ok-false runs would trigger" at θ=0.7; the actual value is 37.5% (9/24).** The number 30 appears to be the *ok-true* bucket's `n_escalated` count (30/338 = 8.9%, correctly cited immediately after) misapplied as a percentage to the ok-false bucket. The directional claim ("escalation concentrates in failed jobs") still holds under the correct number (37.5% > 8.9%, even more concentrated than stated) — but the doc's own LOG table (§1.9) claims "PASS — reproduced from `cap_cascade_retrospective.json`, cross-checked by hand" for "every number traces," and this one does not. | **Mandatory fix** (doc-only; no code or JSON is wrong) | `cap_cascade_retrospective.json`: `arms.0_7.by_job_status.False.escalation_trigger_rate` = `{"value": 0.375, "n_escalated": 9, "n_captured_confidence": 24}`, re-derived independently in `/tmp/wt_e2_cascade_run` and matching the committed artifact exactly. Doc text at `docs/experiments/designs/cap_e2_e3_run.md:125-126`. |
| 2 | Commit message for `84f3fb9a2` (e2_coverage_impact) is corrupted: dollar amounts `$0.31`, `$0.044`, `$0.65`, `$0.19` render as `/bin/bash.31`, `/bin/bash.044`, `/bin/bash.65`, `/bin/bash.19` — `$0` was expanded by an unquoted shell context (`$0` → the shell binary path) before the commit message reached `git commit`. Cosmetic only: the doc and JSON artifacts that the commit introduces are unaffected (verified correct, see known-safe #3 below) — only the human-readable commit message is garbled. | Minor / tooling | `git show 84f3fb9a2 -s --format=%B` |
| 3 | The two new scripts (`cap_cascade_retrospective.py`, `cap_coverage_routing_impact.py`, ~700 lines together) ship with zero dedicated unit tests. They are registered `maintained` in `scripts/CONTEXT.md` and CLI-wired, which is the maintained-script bar, but the maintained bucket elsewhere in this repo generally has `tests/test_*.py` coverage. No regression test would catch e.g. finding #1's category of error (a hand-computed number diverging from the JSON) or a future change to `_theta_arm`/`diff_recommendations` silently breaking the honesty invariants. | Minor / gap, not blocking | `find tests -iname "*cascade*" -o -iname "*coverage_routing_impact*"` → empty; confirmed via `git diff` on `tests/` across the three phase commits → empty. |

## Known-safe list (attacked, did not falsify)

| # | Attack attempted | Result |
|---|---|---|
| 1 | **Coverage pre-check is fabricated or skipped** — does the script actually compute and report confidence coverage *before* any downstream metric, or is "EVALUABLE_WITH_CAVEAT" hardcoded? | **Not falsified.** `compute()` in `cap_cascade_retrospective.py` derives `precheck` from live counts (`n_conf/n_total`) and only emits `EVALUABLE_WITH_CAVEAT` when `n_conf > 0`; re-run live against the current corpus (462 phases, up from 455 at the last census — the corpus grew between runs, confirming this is a live recompute, not a cached/stale number) yields 362/462 = 78.3%, matching the doc and committed JSON exactly. |
| 2 | **Counterfactual-only guard is violated** — does anything in the E2 script actually call a model, apply an escalation, or mutate state? | **Not falsified.** `cap_cascade_retrospective.py` only reads `experiments/results/workflows/**/*.json` and writes its own output JSON; `model_cascade` has zero implementation and zero call sites in `src/` or `scripts/` (grepped) — only four comment/docstring mentions as a reserved future arm. `routing_arm_regret` is documented and coded as `0.0` unconditionally (never computed from a real escalated execution), and `null_testable` correctly flags `false` whenever the escalated-but-unmeasured subset is non-empty (true at every θ tested: 6/13/39). |
| 3 | **Thresholds {0.3, 0.5, 0.7} are honest, not cherry-picked or silently changed** — do the script's `THETAS` and the spec's factor levels agree? | **Not falsified.** `cap_confidence_cascade.yaml:170` factor `cascade_arm` levels `[baseline, cascade_theta_0.3, cascade_theta_0.5, cascade_theta_0.7]`; `cap_cascade_retrospective.py`'s `THETAS = (0.3, 0.5, 0.7)` matches exactly. Spec pre-existed this branch (introduced in `5aa7f7a00`/`5220c279e`, not authored by this branch), ruling out post-hoc threshold selection to fit a result. |
| 4 | **E3's change-rate table is trusted from prose rather than recomputed from the registry** — does `changed_recommendation_count = 0` actually hold when independently recomputed? | **Not falsified.** Re-ran `cap_coverage_routing_impact.py --json` live in the branch worktree; output is byte-identical to the committed `cap_coverage_routing_impact.json` (`json.dumps(..., sort_keys=True)` comparison). Independently re-derived the underlying corpus size via `canonical_corpus.load_canonical_tables("finding")` → 64 rows, matching the doc's claim without going through the script at all. |
| 5 | **Legacy vs. coverage-corrected arms use different eligibility filters, making the "0 changes" comparison unfair (e.g. one arm silently drops a task the other keeps)** | **Not falsified.** Read `compute_routing()` (`src/agentic_dynamics/control/routing.py:187`) and `_eligible_tasks()` (`cap_coverage_routing_impact.py`) side by side: identical `narration_failure` filter, identical `task == "?" or task.startswith("exp_")` exclusion, identical `min_models=2` threshold. Both arms analyze the same 2 tasks (`task_manager` 7 models/49 entries, `process_perturbation_resample` 3 models/15 entries), confirmed via direct inspection of the JSON's `per_task` lists. |
| 6 | **Inconclusive-vs-confirmed-null labeling is honest** — does the doc call E2's null "confirmed" anywhere, or consistently "untestable-by-construction"? | **Not falsified.** §1.2, §1.6, §3.2, §3.6 all use "untestable-by-construction" / "inconclusive-by-construction," explicitly distinguished from a confirmed null; §1.6 explicitly warns "Do NOT read 'regret = 0' as 'escalation is safe.'" E3's null (§2.6, §3.6) is separately and correctly labeled "confirmed" because its mechanism (both formulas mathematically evaluated on the same fully-covered-enough corpus) is genuinely different from E2's structural unmeasurability. |
| 7 | **"Every number traces to the registry" is a bare assertion, not actually checkable** — spot-check every distinct number in the doc against the JSON/registry. | **Mostly not falsified — one exception found (finding #1).** Verified independently: baseline cost/verified $1.8109 (785.9273/434, hand-computed to match); all three θ trigger rates (1.66/3.59/10.77% → 1.7/3.6/10.8%); all three per-model trigger ranges (0.2857/0.2857/0.5); all three non-escalated-subset verified-success rates (99.16/99.14/99.38%); job_status split at θ=0.3 (403 ok-true @ $1.3678, 49 ok-false @ $7.5714, 31/49=63.3% verified); E3's 7×/3.5× underpricing ratios (0.309695/0.044242=7.00, 0.648012/0.185146=3.50); E3's 49/15 per-task entry counts; the `.gitignore` claim for `experiments/results/workflows/` (Limitation §3.7 #7). All matched except the θ=0.7 job-status trigger rate (finding #1). |
| 8 | **The corpus the script reads is contaminated by this workflow's own execution (circular measurement)** | **Not falsified — checked directly, not assumed.** Searched `experiments/results/workflows/**/*.json` for any run with `spec_name == "cap_e2_cascade_run"` — zero matches. The 126-run/462-phase corpus (up from the census's 125/455 at an earlier point in the branch's history) grew from unrelated concurrent work, not this workflow's own phases. |
| 9 | **CLI wiring (`agentic-dynamics analyze cascade-retrospective` / `coverage-routing-impact`) is registered but non-functional** | **Not falsified, after correcting a false-positive.** Initial test against `python3 -m agentic_dynamics.cli` failed — but this was an environment artifact: the ambient editable install resolves `agentic_dynamics.cli` to the *main* worktree, not the reviewed branch. Re-run with `PYTHONPATH` pointed at the branch's own `src/`, both subcommands dispatch and execute correctly end-to-end. |
| 10 | **Existing test suite regressed** | **Not falsified, on the guards that matter for this diff.** `tests/test_script_classification.py` and `tests/test_data_flow.py` (the two guards that would catch a malformed `scripts/CONTEXT.md` entry or a data-flow violation from the new scripts) pass cleanly. A full `pytest tests/` run was attempted but hung on a live socket connection unrelated to this branch's diff (no test file was touched by any of the three phase commits — confirmed via `git diff --stat -- tests/` across the branch, which is empty) and was terminated rather than left to time out; not treated as a finding against this branch since the hang is pre-existing infra (this repo's tests skip gracefully when infra like Redis/Neo4j is unavailable per `tests/conftest.py`, but at least one test evidently blocks instead of skipping — an environment issue, not something this branch introduced). |

## Mandatory fix

Correct `docs/experiments/designs/cap_e2_e3_run.md:125-126` — replace "30.0% of confidence-captured
phases in ok-false runs would trigger" with **37.5%** (9/24), sourced from
`cap_cascade_retrospective.json`'s `arms.0_7.by_job_status.False.escalation_trigger_rate.value`.
The directional claim in that sentence is unaffected (37.5% > 8.9% is a *stronger* confound signal
than the doc currently states). Optional: repair the `$0.XX`-mangled commit message is not
possible without rewriting history and is not worth doing; flagging here for the phase-commit
tooling (whatever assembled `84f3fb9a2`'s message) so future runs quote dollar amounts.
