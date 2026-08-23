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

**Apply stayed OFF for this entire campaign.** No spec passed `--control-route`; no spec's YAML
sets `workflow.params.control_route`; `tests/test_context_plane_seam.py::test_no_committed_spec_
opts_into_control_route` (run today) confirms the committed spec corpus still has zero opt-ins.

## 1. Cells run

Four sub-run attempts against three specs; two completed, three failed before reaching a real
agent call.

| spec | model | phases | status | cost (USD) | duration | LEDGER file |
|---|---|---|---|---|---|---|
| `kb_write_path` | anthropic/claude-sonnet-5 | 3/3 ok | **ok** | 1.4435 | 283s | `kb_write_path/20260823T234214Z.json` |
| `code_review` | anthropic/claude-sonnet-5 | 2/2 ok | **ok** | 8.2082 | 913s | `code_review/20260823T233711Z.json` |
| `labbook_refresh` (attempt 1) | deepseek/deepseek-v4-flash | 0/1 ok | **failed** (`exit_code=1`, 3s) | 0.0 | 3s | `labbook_refresh/20260823T231554Z.json` |
| `labbook_refresh` (attempt 2) | deepseek/deepseek-v4-flash | 0/1 ok | **failed** (`exit_code=1`, 3s) | 0.0 | 3s | `labbook_refresh/20260823T231642Z.json` |
| `routing_kb_more_itertools` | deepseek/deepseek-v4-flash | 0/1 ok | **failed** (`exit_code=1`, 3s) | 0.0 | 3s | `routing_kb_more_itertools/20260823T231644Z.json` |

**Finding — 3 of 5 attempts never reached CAP.** Despite the campaign's hard rule to run every
sub-run with `--model anthropic/claude-sonnet-5 --backend claude_cli`, `labbook_refresh` and
`routing_kb_more_itertools` each ran their one agent phase against `deepseek/deepseek-v4-flash`
(LEDGER: `"model": "deepseek/deepseek-v4-flash"` on the phase, not the top-level spec model) and
failed in ~3 seconds with `exit_code=1` — consistent with AGENTS.md's "DeepSeek credits are
exhausted." These two specs pin a phase-level model in their own YAML that the top-level
`--model` flag does not override, so the campaign's model choice never reached the phase. This is
an operational gap in how those two specs are authored, not a bug in the three report scripts —
recorded here as an accepted limitation, out of scope for this pass. Net effect: **2 real cells**
(`kb_write_path`, `code_review`) produced usable data, matching the "2-3 small real cells" floor
but at the low end.

`n_executed_phases = 8` (**ARM**) = 5 real anthropic phases + 3 failed deepseek phases. The
`anthropic/claude-sonnet-5` arm (n=5, avg_correctness=1.0, weighted_loss=-3.0697) is the best
measured arm; the `deepseek/deepseek-v4-flash` arm (n=3, avg_correctness=0.0, weighted_loss=0.0)
reflects the 3 zero-cost failures above, not a real routing comparison — **ARM**.

## 2. Shadow records: real, and validated through C1–C10

Every recorded shadow decision was inspected directly (`control.rules.load_shadow_decisions`
scan of `experiments/results/kb/*.json`, `extractor_version == "actuation/v1"`). All 11 are real:
timestamped 2026-08-24 01:15–01:39 local (i.e. within the s1 sub-run window), `causes`-linked to
one of 5 distinct `context_snapshot` artifacts that are ALSO present in the compacted registry
(`experiments/data_manifest.json`'s `registry` array — 5 rows, `source_type: context_snapshot`,
IDs match exactly the 5 `causes` values referenced by the 11 decisions). No orphaned or
unregistered snapshot.

**Every one of the 11 decisions was rejected — at check C2, not applied, and that rejection is
itself the finding.** Each decision's `rationale` reads: `"snapshot inadmissible: allowed_models
(workload): halt; max_spend_usd (workload): halt; workflow_phases_remaining (parent): halt | C2:
snapshot is not admissible: ..."`. The validator (`control.validator.validate_decision`, C1-C10)
worked exactly as designed: it caught every inadmissible snapshot at the second check and refused
before the decision could be recorded as anything but `action="continue"`. Zero decisions were
wrongly admitted; zero reached C3-C10. This is evidence the C1-C10 gate is doing its job, not
evidence the plane is unsafe.

**Coverage caveat on `n=11`:** the 5 distinct snapshots do not map 1:1 to the 11 decisions —
`route_step`/the shadow router is called exactly once per phase in `workflow_runner.py`
(confirmed: single call site, `src/agentic_dynamics/runtime/workflow_runner.py:532`), so the 8
measured phases (**ARM**, §1) should produce 8 decisions, not 11. The extra 3 decisions
(distribution across snapshots: 4/3/2/1/1) most likely come from sub-run invocations of
`run_workflow.py` that were retried or interrupted before producing a final ledger JSON — the
shadow-recording path is best-effort and independent of whether a ledger file is ultimately
written, so an earlier, superseded invocation's router call still lands in the KB even though its
phase never appears in `n_executed_phases`. This could not be reconstructed further from what's
on disk; recorded as an accepted limitation. **The effective independent sample size for the
flip decision is n=5 (one per distinct compiled snapshot), not n=11** — small either way.

## 3. Analysis: shadow vs `step_routing`

- **Agreement rate: 0.0%** (`decision_regret = 1.0`, n=11 — **DEC**). But this is **mechanical**,
  not a measured routing-quality gap: `route_next_job_v1` always returns `action="continue"` when
  `ctx.admissible` is `False` (`src/agentic_dynamics/control/rules.py:105-115`), and every one of
  the 5 snapshots this campaign compiled was inadmissible (§4). `step_routing.route_step` always
  returns `action="route"` with a real model. With `admissibility_rate = 0.0%`, `decision_regret
  = 1.0` is the *only* value `decision_calibration` can produce — the campaign never got far
  enough to compare a routing choice against another routing choice.
- No rejected decision disagreed with `step_routing` on grounds of a worse proposed model — the
  plane never got to propose a model at all.

## 4. Coverage: n per cell, missing facts

| signal | n | source |
|---|---|---|
| context snapshots compiled | 5 | **CTX** |
| admissible snapshots | 0 (0.0%) | **CTX** |
| shadow decisions recorded | 11 (5 independent, §2) | **DEC** |
| decisions admitted past C2 | 0 | inspected directly, §2 |
| real executed phases | 8 (5 ok + 3 failed) | **ARM** |
| real cells (spec runs that completed) | 2 (`kb_write_path`, `code_review`) | §1 |

Every one of the 5 snapshots is missing the same 5 predicates, 5/5 times each (**CTX**):
`allowed_models`, `job_accumulated_cost_usd`, `max_spend_usd`, `phase_test_verified`,
`workflow_phases_remaining`. `unknown_rate = 100%`, `conflict_rate = 0%`, `stale_rate = 0%` — the
facts are never resolved (no producer writes them for these cells), not stale or conflicting.
This is the direct cause of §3's 0% agreement rate.

## 5. Verdict: apply may **NOT** flip yet — n too small, AND the underlying facts aren't populated

Per `docs/context_abstraction/implementation_notes.md` §12 step 4: flip only once
`shadow_decision_report.py`'s agreement rate and `decision_arm_comparison.py`'s per-model loss
together support "the plane is at least non-inferior for this spec." Neither can say that yet:

1. **n is too small.** 5 independent snapshots (11 recorded decisions) across 2 real cells is far
   below a usable sample for any non-inferiority claim, campaign-wide or per-spec.
2. **Zero admissible decisions exist.** `admissibility_rate = 0.0%` (**CTX**) means the plane has
   never once proposed a real `route` choice to compare against `step_routing` — the 100%
   disagreement rate measures fact-population gaps, not routing quality. There is currently no
   way to distinguish "the plane's policy is bad" from "the plane never got a chance to decide."

**Flip prerequisites (blocking, in order):**

1. Wire `FactStore` producers for the 5 currently-unknown predicates — `allowed_models`,
   `job_accumulated_cost_usd`, `max_spend_usd`, `phase_test_verified`,
   `workflow_phases_remaining` — so snapshots for real workflow cells become admissible at least
   some of the time. Until `admissibility_rate > 0`, no cell can produce a comparable decision.
2. Fix the two specs (`labbook_refresh`, `routing_kb_more_itertools`) whose phase-level model
   pin ignores `--model`, or route future shadow-campaign sub-runs around them, so attempts don't
   burn against exhausted DeepSeek credits before reaching CAP (§1).
3. Re-run `--cap-shadow` across enough ADMISSIBLE decisions (not just recorded ones) to read a
   meaningful `decision_regret` — implementation_notes.md §12 step 1's "meaningful number of
   cycles" is not met by n=5.
4. Re-read `shadow_decision_report.py` (agreement rate) and `decision_arm_comparison.py`
   (per-model measured loss) together (§12 steps 2-3). Only once both show non-inferior once
   admissible data exists does an operator add `workflow.params.control_route: true` to one
   spec's YAML, in a normal reviewable commit.
5. Apply stays OFF for every other spec regardless — this is a per-spec opt-in, never a default
   (§12).

No report script required a fix this pass — `context_snapshot_report.py`,
`shadow_decision_report.py`, and `decision_arm_comparison.py` were each re-run fresh and
byte-for-byte reproduced the committed report JSONs.
