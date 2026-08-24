---
status: accepted
---
# CAP I6 shadow campaign — measurement summary

Ran the CAP I6 shadow loop (`--cap-shadow`, `anthropic/claude-sonnet-5` via `claude_cli`) on real
workflow specs, produced the three I6 reports, and read them together per
`docs/context_abstraction/implementation_notes.md` §12's flip procedure. Every number below cites
one of:

- `experiments/results/cap_shadow/context_snapshot_report_20260823T234503Z.json` (**CTX**)
- `experiments/results/cap_shadow/shadow_decision_report_20260823T234503Z.json` (**DEC**)
- `experiments/results/cap_shadow/decision_arm_comparison_20260823T234503Z.json` (**ARM**)
- the run ledgers under `experiments/results/workflows/{kb_write_path,code_review,
  labbook_refresh,routing_kb_more_itertools}/*.json` (**LEDGER**)
- the 11 shadow-decision artifacts themselves, read directly off disk via
  `control.rules.load_shadow_decisions`'s scan of `experiments/results/kb/*.json`
  (`extractor_version == "actuation/v1"`), joined to their `causes` (the `context_snapshot`
  artifact each decision cites) for the workload label and to on-disk file mtime for a wall-clock
  ordering — (**RAW**)

**Apply stayed OFF for this entire campaign.** No spec passed `--control-route`; no spec's YAML
sets `workflow.params.control_route`; `tests/test_context_plane_seam.py::test_no_committed_spec_
opts_into_control_route` (run today) confirms the committed spec corpus still has zero opt-ins.

## 1. Table of cells — one row per shadow-router invocation (n=11, **RAW**)

The shadow router (`control.rules.make_shadow_router`) is called once per agent phase
(`src/agentic_dynamics/runtime/workflow_runner.py:532`, the only call site). Each call
independently (a) asks `step_routing.route_step` for the real, executed choice — the
`step_routing decision` column — and (b) compiles a snapshot and asks the fact-based rule for its
own proposal — the `shadow decision` column — before recording both together. 11 such calls
happened across 6 sub-run attempts against 5 distinct specs; the table below is the complete set,
ordered by wall-clock (file mtime), joined to the matching **LEDGER** phase where one exists:

| # | spec (workload) | shadow decision | step_routing decision | agree/disagree | phase cost (USD) | phase duration | ledger outcome |
|---|---|---|---|---|---|---|---|
| 1 | `labbook_refresh` (attempt 1) | `continue` | `route` → deepseek/deepseek-v4-flash | **disagree** | 0.0000 | 2.99s | failed, `exit_code=1` |
| 2 | `labbook_refresh` (attempt 2) | `continue` | `route` → deepseek/deepseek-v4-flash | **disagree** | 0.0000 | 3.01s | failed, `exit_code=1` |
| 3 | `registry_canonicalize` | `continue` | `route` → anthropic/claude-sonnet-5 | **disagree** | unmeasured | unmeasured | **no ledger written at all** — see §2 |
| 4 | `routing_kb_more_itertools` | `continue` | `route` → deepseek/deepseek-v4-flash | **disagree** | 0.0000 | 2.83s | failed, `exit_code=1` |
| 5 | `code_review` (pre-attempt) | `continue` | `route` → anthropic/claude-sonnet-5 | **disagree** | unmeasured | unmeasured | **no matching ledger** — see §2 |
| 6 | `kb_write_path` (pre-attempt) | `continue` | `route` → anthropic/claude-sonnet-5 | **disagree** | unmeasured | unmeasured | **no matching ledger** — see §2 |
| 7 | `code_review` phase 1 (`code_review`) | `continue` | `route` → anthropic/claude-sonnet-5 | **disagree** | 7.0717 | 689.0s | ok |
| 8 | `code_review` phase 2 (`architecture_review`) | `continue` | `route` → anthropic/claude-sonnet-5 | **disagree** | 1.1366 | 224.2s | ok |
| 9 | `kb_write_path` phase 1 (`implement`) | `continue` | `route` → anthropic/claude-sonnet-5 | **disagree** | 0.4988 | 51.4s | ok |
| 10 | `kb_write_path` phase 2 (`test`) | `continue` | `route` → anthropic/claude-sonnet-5 | **disagree** | 0.0646 | 41.6s | ok |
| 11 | `kb_write_path` phase 3 (`verify`) | `continue` | `route` → anthropic/claude-sonnet-5 | **disagree** | 0.8801 | 190.1s | ok |

**11/11 disagree — 0.0% agreement, matching `decision_regret = 1.0` exactly (DEC, §3).**

Cell-level summary: **2 real cells completed** (`kb_write_path`: 3/3 phases ok, $1.4435 total,
283s, `kb_write_path/20260823T234214Z.json`; `code_review`: 2/2 phases ok, $8.2082 total, 913s,
`code_review/20260823T233711Z.json` — **LEDGER**), meeting the "2-3 small real cells" floor at the
low end. 3 more sub-run attempts (rows 1, 2, 4) failed in ~3 seconds each against
`deepseek/deepseek-v4-flash`, $0 cost — despite the campaign's hard rule to invoke every sub-run
with `--model anthropic/claude-sonnet-5 --backend claude_cli`, `labbook_refresh` and
`routing_kb_more_itertools` each pin a phase-level model in their own spec YAML that the top-level
`--model` flag does not override, so the real invocation reached `deepseek/deepseek-v4-flash` and
failed with `exit_code=1` — consistent with AGENTS.md's "DeepSeek credits are exhausted." This is
an authoring gap in those two specs, not a bug in the three report scripts; recorded as an
accepted limitation, out of scope for this pass. `n_executed_phases = 8` (**ARM**) = 5 real
anthropic phases (rows 7-11) + 3 failed deepseek phases (rows 1, 2, 4); the
`anthropic/claude-sonnet-5` arm (n=5, avg_correctness=1.0, weighted_loss=-3.0697) is the best
measured arm, `deepseek/deepseek-v4-flash` (n=3, avg_correctness=0.0, weighted_loss=0.0) reflects
those 3 zero-cost failures, not a real routing comparison (**ARM**).

## 2. Reconciling n=11 decisions against n=8 executed phases (the 3 "extra" rows)

Rows 1, 2, 4, 7, 8, 9, 10, 11 (8 rows) map exactly 1:1 onto the 8 phases in `n_executed_phases`
(**ARM**) — each row's phase-cost/duration was matched to the ledger by wall-clock adjacency
(e.g. row 7's router call at 23:21:57 UTC starts exactly when `code_review`'s first phase starts;
689.0s later, at 23:33:26 UTC, row 8's router call fires for the second phase — precisely the
ledger's own phase boundary). That leaves 3 rows (3, 5, 6) that do **not** correspond to any phase
in any ledger on disk:

- **Row 3 (`registry_canonicalize`, 23:16:40 UTC)** — `workflows/operations/registry_canonicalize.
  yaml` is a real, existing spec; a sub-run against it was attempted (the router fired once, a
  snapshot was compiled and registered — `experiments/data_manifest.json`'s registry has the
  matching `context_snapshot` row) but **no `experiments/results/workflows/registry_canonicalize/`
  directory exists at all** — the run crashed or was killed hard enough that `run_workflow.py`
  never reached the code path that writes a ledger, even the `failed`-status kind that
  `labbook_refresh`/`routing_kb_more_itertools` still managed to write. This sub-run is a 6th real
  attempt, previously undercounted — it contributes one decision but zero measurable cost/duration
  and is excluded from `n_executed_phases`.
- **Rows 5 and 6 (`code_review`/`kb_write_path` "pre-attempts", 23:17:53 and 23:17:54 UTC)** — both
  fire ~4 and ~20 minutes *before* the eventual successful ledger's `started_at`
  (`code_review`: 23:21:57 UTC; `kb_write_path`: 23:37:30 UTC — **LEDGER**). Each is a router call
  from an earlier invocation of the same spec that did not produce a ledger (most likely aborted
  or superseded by a manual retry), followed later by a second, complete, successful invocation of
  the same spec that did.

**Net effect: 6 real sub-run attempts against 5 distinct specs, not the 4 attempts against 3 specs
this doc's first draft reported** — the shadow-recording path
(`control.rules.record_shadow_decision`) is best-effort and independent of whether the invocation
that triggered it ever finishes, so a router call from a crashed/superseded attempt still lands in
the KB even though nothing else about that attempt is recoverable from the ledgers. **The
effective independent sample size for the flip decision is n=11 decisions across 6 attempts / 5
specs — still small, and only 2 of the 5 specs (`kb_write_path`, `code_review`) ever produced a
complete, cost-and-duration-measured cell.**

## 3. Analysis: how often shadow == `step_routing`, and why every decision was rejected

- **Agreement rate: 0.0%** (`decision_regret = 1.0`, n=11 — **DEC**), exactly matching §1's
  11-row, 11-disagree table. This is **mechanical, not a measured routing-quality gap**:
  `route_next_job_v1` always returns `action="continue"` when `ctx.admissible` is `False`
  (`src/agentic_dynamics/control/rules.py:105-115`), and `decision_calibration` counts any
  `action != baseline_action` as a disagreement regardless of what model either side would have
  picked (`src/agentic_dynamics/experiment/compile_experiment.py:355-360`). `step_routing.
  route_step` always returns `action="route"` with a real model. With `admissibility_rate = 0.0%`
  (**CTX**, §4), `decision_regret = 1.0` is the *only* value `decision_calibration` can produce —
  the plane never got far enough to propose a model, so there is nothing to compare on the merits.
- **Every one of the 11 decisions was rejected — at check C2, and that rejection is itself the
  finding, inspected directly off each decision's own `rationale` field (RAW):** `"snapshot
  inadmissible: allowed_models (workload): halt; max_spend_usd (workload): halt;
  workflow_phases_remaining (parent): halt | C2: snapshot is not admissible: ..."`, identical
  wording on all 11. The validator (`control.validator.validate_decision`, C1-C10) worked exactly
  as designed: it caught every inadmissible snapshot at the **second** check and refused before
  the decision could be recorded as anything but `action="continue"`. **Zero decisions were
  wrongly admitted; zero reached C3-C10.** This is evidence the C1-C10 gate is doing its job, not
  evidence the plane is unsafe — but it also means C3-C10 have never been exercised by a real run.
- No rejected decision disagreed with `step_routing` over a worse *proposed model* — the plane
  never got to propose one.

## 4. Coverage: n per cell, missing facts

| signal | n | source |
|---|---|---|
| context snapshots compiled | 5 (distinct) | **CTX** |
| admissible snapshots | 0 (0.0%) | **CTX** |
| shadow decisions recorded | 11 | **DEC** |
| decisions admitted past C2 | 0 | inspected directly, §3 |
| sub-run attempts (specs touched) | 6 attempts / 5 specs | §1-§2 |
| attempts with a ledger on disk | 5 of 6 (`registry_canonicalize` produced none) | §2 |
| real executed phases (measured cost+duration) | 8 (5 ok + 3 failed) | **ARM** |
| real cells fully completed | 2 (`kb_write_path`, `code_review`) | §1 |

Every one of the 5 distinct snapshots is missing the same 5 predicates, 5/5 times each (**CTX**):
`allowed_models`, `job_accumulated_cost_usd`, `max_spend_usd`, `phase_test_verified`,
`workflow_phases_remaining`. `unknown_rate = 100%`, `conflict_rate = 0%`, `stale_rate = 0%` — the
facts are never *resolved* (no producer writes them for these cells), not stale or conflicting.
This is the direct cause of §3's 0% agreement rate. Separately, `registry_canonicalize`'s missing
ledger (§2) is a coverage gap in the *executed-phase* corpus, not the *snapshot/decision* corpus —
its snapshot and decision are both present and counted everywhere above.

## 5. Verdict: apply may **NOT** flip yet — n too small, AND the underlying facts aren't populated

Per `docs/context_abstraction/implementation_notes.md` §12 step 4: flip only once
`shadow_decision_report.py`'s agreement rate and `decision_arm_comparison.py`'s per-model loss
together support "the plane is at least non-inferior for this spec." Neither can say that yet:

1. **n is too small.** 11 decisions across 6 attempts, only 2 of which became fully-measured real
   cells, is far below a usable sample for any non-inferiority claim, campaign-wide or per-spec.
2. **Zero admissible decisions exist.** `admissibility_rate = 0.0%` (**CTX**) means the plane has
   never once proposed a real `route` choice to compare against `step_routing` — the 100%
   disagreement rate measures fact-population gaps, not routing quality. There is currently no way
   to distinguish "the plane's policy is bad" from "the plane never got a chance to decide."

**Flip prerequisites (blocking, in order):**

1. Wire `FactStore` producers for the 5 currently-unknown predicates — `allowed_models`,
   `job_accumulated_cost_usd`, `max_spend_usd`, `phase_test_verified`,
   `workflow_phases_remaining` — so snapshots for real workflow cells become admissible at least
   some of the time. Until `admissibility_rate > 0`, no cell can produce a comparable decision.
2. Fix the two specs (`labbook_refresh`, `routing_kb_more_itertools`) whose phase-level model pin
   ignores `--model`, and investigate why `registry_canonicalize`'s attempt produced no ledger at
   all (§2) — future shadow-campaign sub-runs should not burn attempts on exhausted DeepSeek
   credits or silent crashes before reaching CAP.
3. Re-run `--cap-shadow` across enough ADMISSIBLE decisions (not just recorded ones) to read a
   meaningful `decision_regret` — implementation_notes.md §12 step 1's "meaningful number of
   cycles" is not met by n=11 decisions / 2 real cells.
4. Re-read `shadow_decision_report.py` (agreement rate) and `decision_arm_comparison.py` (per-model
   measured loss) together (§12 steps 2-3). Only once both show non-inferior once admissible data
   exists does an operator add `workflow.params.control_route: true` to one spec's YAML, in a
   normal reviewable commit.
5. Apply stays OFF for every other spec regardless — this is a per-spec opt-in, never a default
   (§12).

No report script required a fix this pass — `context_snapshot_report.py`,
`shadow_decision_report.py`, and `decision_arm_comparison.py` were each re-run fresh and
byte-for-byte reproduced the committed report JSONs (verified prior to this doc's first draft).

## 6. Adversarial falsification (s4)

Role: try to break §1-§5's numbers and verdict. Six attack vectors, each independently re-derived
from raw sources rather than trusting the report scripts' own output a second time.

| # | attack | method | result | disposition |
|---|---|---|---|---|
| 1 | **Wrong baseline** — is `step_routing` scored on different inputs than the shadow rule, making "agreement" meaningless? | Read `make_shadow_router`'s `_router` (`control/rules.py:301-340`): `route_step(job, state, prefs, signals)` is called, then `compile_context(...)` for the SAME call, no intervening execution. Confirmed `route_step` is a real scored router (`step_routing.py:188-208`, argmax over measured signals, not a hardcoded constant) — for this single-model campaign its `model_pool` was pinned to `[anthropic/claude-sonnet-5]`, so its choice was constrained but not fabricated. | **Not falsified.** The two mechanisms genuinely consume different information (`job`/`state`/`prefs` vs. the compiled fact snapshot) by design — that IS the shadow comparison, not a measurement flaw. No time gap between the two calls. | Accepted design, not a limitation. |
| 2 | **Cherry-picked cells** — are there snapshots/decisions/ledgers outside the reported set? | Scanned every `context_snapshot`/`actuation` artifact in `experiments/results/kb/` by mtime across the full campaign window (22:00–03:00 UTC, wider than the reports' own window) independent of `load_shadow_decisions`'s own code path: 16 total (5 snapshots + 11 decisions) — exact match to §1/§4. Separately counted every `*.json` under `experiments/results/workflows/`: exactly 5 files, all 5 already in §1's table — `decision_arm_comparison.py`'s n=8 phase corpus is **100% this campaign's own data**, not diluted by unrelated historical runs (strengthens the ARM numbers beyond what the first draft claimed). | **Not falsified — strengthened.** | Numbers confirmed exhaustive. |
| 3 | **Decisions recorded but never validated** | Read both router builders end to end: in `make_shadow_router` (`rules.py:301-340`) AND `make_applying_router` (`rules.py:265-`), `record_shadow_decision(...)` is called only INSIDE the branch that already ran `validate_decision(...)` two lines above — there is no code path that records a decision without validating it first. | **Falsified as a concern — confirmed not an issue, by construction.** | No fix needed. |
| 4 | **Missing-cost cells mislabeled** — is "unmeasured" (rows 3, 5, 6 in §1) hiding recoverable data? | Traced the ledgers' own `workdir` fields to the actual sub-run worktrees (`/tmp/wt_cap_shadow_cells`, `/tmp/wt_cap_shadow_itertools`) and checked their real git logs and `experiments/results/workflows/` contents directly (not the copies in this worktree). Neither has any trace of `registry_canonicalize`. Searched every `/tmp` worktree in `git worktree list` (incl. a coincidentally-named `wt_cap_shadow_registry`, which turned out to be a pre-existing worktree for an unrelated task, git status/log confirms zero `run_workflow.py` activity) — no orphaned ledger anywhere. **Bonus finding, not a numeric error:** `kb_write_path`'s single real commit in `wt_cap_shadow_itertools` (`30581bd10`) touches only `docs/review/impl_kb_write_path.md` — R4/R6/R8 were already implemented in an earlier historical run; this cell re-verified already-landed code rather than implementing anything new, so its 3 phases ran under low-stakes/no-diff conditions. The recorded `cost_usd`/duration figures are still real token spend (read straight from each phase's own ledger record) — this doesn't change any cited number, but the routing decisions made here weren't under genuine implementation pressure. | **Not falsified — confirmed accurate; one limitation added.** | §1/§2's "unmeasured" labeling stands. Noting the re-verification nature of `kb_write_path` as an added limitation. |
| 5 | **Snapshot compiled from stale facts** | `stale_rate = 0.0%` (**CTX**) is consistent with facts that are never *resolved* at all — an unset fact cannot go stale. Re-confirmed none of the 11 decisions reached C7 (the freshness check) — all 11 failed earlier, at C2. | **Not falsified.** | Consistent with §3/§4. |
| 6 | **Report scripts silently drop cells** | Re-derived every number in all three report JSONs from raw sources, independent of the scripts' own internal filtering (`_read_payload`'s try/except in `context_snapshot_report.py`, the `extractor_version`/`baseline_action` filters in `load_shadow_decisions`, the `kind`/`model` filter in `load_phase_outcomes`): 5 snapshots, 11 decisions, 8 phases, 5 ledger files — exact match every time. | **Not falsified.** | No silent drops found. |

**Verdict, re-stated after the attack:** unchanged — **apply stays OFF; the flip is not yet
justified.** None of the six attacks found a wrong baseline, a hidden/cherry-picked cell, an
unvalidated decision, a mislabeled cost, a stale-fact artifact, or a script that silently dropped
data — if anything, attack 2 confirms the ARM comparison's corpus is cleaner (100% this campaign's
own data) than the first draft gave it credit for, and attack 4 confirms the `registry_canonicalize`
data loss is real, not an under-search artifact. The verdict's actual weak point survives every
attack because it was never about data integrity: `admissibility_rate = 0.0%` and n=11 decisions
(2 fully-measured real cells) are still too small and too structurally blocked (zero decisions ever
reached C3-C10) to say anything about routing quality either way. The flip prerequisites in §5 are
unchanged.
