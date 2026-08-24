# E4 — cap_grit_strength_grid: pilot writeup (x4)

**Spec:** `cap_grit_strength_grid@0.1` (`experiments/definitions/cap_grit_strength_grid.yaml`)
**Metrics source:** `experiments/results/cap_grit_grid_metrics.json` (schema `cap_grit_grid_metrics/v1`, grid_status=COMPLETED)
**Ledger source:** `experiments/results/cap_grit_grid_ledger.json` (8 cells, 9 attempts)
**Execution record:** runplan §8 (x2) + §9 (x3)
**Every number below traces to the metrics JSON unless marked [P] (declared policy) or [H] (heuristic estimate).**

---

## hypothesis

A retry-on-failure policy (`grit_retry`: a second attempt when the first attempt's
`test_executed_success` is false) improves **cost-per-verified-outcome** over a single-attempt
baseline, across perturbation_strength {low=0.2, mid=0.5, high=0.8} (all under
condition=BAD_SEED) plus a clean (s=0.0) reference cell, on one BUILTIN_STORY
(`task_manager_api`), pinned to `anthropic/claude-sonnet-5`.

The mechanism the hypothesis rests on: a first attempt that fails its independently-run test
suite is a "bad draw" in an otherwise-competent model's capability envelope; a second attempt at
the same cell can recover at lower marginal cost than accepting the failed outcome (whose
spent cost then buys no verified outcome at all).

## null_hypothesis

`grit_retry` does **not** improve cost-per-verified-outcome over baseline. Equivalently,
`regret(baseline vs grit_retry) >= 0` per condition_strength stratum — a retry on failure is no
cheaper than scoring the single attempt unconditionally, once the full cost of the extra attempt
is charged.

**This null is the honest center of the grid.** The spec's finding 5 explicitly predicts the
grid is under-powered to reject it — see `power_caveat`. The default outcome of this pilot is
therefore "inconclusive," not "reject."

## method

Live grid, 8 cells = `condition_strength` {clean, bad_seed_low, bad_seed_mid, bad_seed_high}
(4) × `policy_arm` {baseline, grit_retry} (2) × `model` {anthropic/claude-sonnet-5} (1),
factorial design, one BUILTIN_STORY (`task_manager_api`, 5 sessions per story attempt).

- Each cell runs a full 5-session story in a disposable git worktree under `/tmp` via
  `run_story(...)` on `anthropic/claude-sonnet-5`, backend `claude_cli` (`CLAUDE_BIN` =
  `/home/drseuss/.local/bin/claude`, Claude Code 2.1.228).
- `test_executed_success` is measured by the harness's independent `test_runner.run_suite` —
  never the model's self-report — on the final worktree state.
- `grit_retry` cells apply finding 4's declared policy at the ledger level: if attempt 1's
  `test_executed_success` is false, attempt 2 runs (`attempt_number=2`,
  `parent_attempt_id=<attempt 1>`) before the cell is scored. Baseline scores the single
  attempt unconditionally (`max_attempts=1`).
- 9 attempt rows were recorded into the grid ledger (`LEDGER_FIELDS` vocabulary: `actual_cost`,
  `rework_cost`, `perturbation_strength`, `test_executed_success`, `policy_arm`,
  `attempt_number`, `parent_attempt_id`, `condition`, `strength`). **8 cells ran; the only
  second attempt fired on bad_seed_high × grit_retry.**
- Measurement ran the spec's registered rules over the ledger via `scripts/measure_cap_grit_grid.py`
  (coverage-first: both coverage ratios reported before any denominator use; no fabricated attempts).

## grid_design_collapse

The naive cross `perturbation_strength{low,mid,high} × condition{clean,bad_seed}` would have
produced 6 levels but only 4 distinct behaviors, because `condition=clean` structurally fixes
strength=0.0 regardless of any strength label crossed with it (verified against
`runtime/story/conditions.py` before authoring, not assumed — `PerturbationCondition.CLEAN`'s
own docstring: "No mutation, no codebase degradation"). The two factors were therefore collapsed
into **one 4-level `condition_strength` factor**:

| factor level | condition | degradation mechanism | strength |
|---|---|---|---|
| clean | CLEAN | none | 0.0 |
| bad_seed_low | BAD_SEED | `inject_bug` artifact `mut_3caacc977303246d` via the mutation override seam | 0.2 |
| bad_seed_mid | BAD_SEED | standard path: pre-generated `bad/` variant (on-disk) | 0.5 |
| bad_seed_high | BAD_SEED | `inject_bug` artifact `mut_1957f3238ebc0f5c` via the mutation override seam | 0.8 |

4 × 2 × 1 = **8 cells**, within the 12-cell ceiling (not padded to exactly 12 with redundant
cells).

## strength_value_provenance

The strength values are **declared**, and their mechanical realization is verified against real
code (runplan §3, findings F1–F4):

- `condition_to_mutations` (`runtime/story/conditions.py`) hardcodes a single
  `CONDITION_STRENGTH = 0.5` for every degrading condition — there is no native low/mid/high
  selector at the condition level. The **mid** cell therefore uses the standard path
  (condition=BAD_SEED, mutation=None → the pre-generated `bad/` variant on disk), which is the
  real, already-exercised mechanism at s=0.5.
- `bad_seed` is **not** a registered compiler operator (`"bad_seed" not in ALL_OPERATORS`,
  `measurement/mutation.py:51`; `compile_mutation(..., operator="bad_seed")` raises
  `ValueError: Unknown operator`). The **low/high** cells therefore use the real codebase
  operator `inject_bug` at the declared strengths, compiled against the actual seed `app.py` and
  verified as clean patches (`experiments/results/cap_grit_grid_mutations/mut_3caacc977303246d.json`
  s=0.2, `mut_1957f3238ebc0f5c.json` s=0.8), passed via `run_story`'s documented
  `mutation=` override seam.
- `perturbation_strength` is recorded from the **effective** degradation: `mutation.strength`
  when an artifact is supplied (0.2/0.8), else the condition's canonical value (0.0 CLEAN /
  0.5 degrading) — fixed in code per finding F3, so the ledger rows carry the honest strength,
  not a label.

Three genuinely distinct mechanical degradations are on disk (single-hunk s=0.2, multi-hunk
s=0.8, on-disk variant s=0.5).

## retry_policy_definition

Declared policy (finding 4, evidence_class [P] — a policy choice authored in the spec, not a
measured fact):

- **baseline** (`max_attempts=1`): the single attempt is scored unconditionally; never a second
  attempt.
- **grit_retry** (`max_attempts=2`): if attempt 1's `test_executed_success` is `false`, attempt
  2 is queued for the same cell (`attempt_number=2`, `parent_attempt_id=<attempt 1>`) before the
  cell is scored; if attempt 1 passed, no retry.

No new retry machinery was claimed — `policy_arm`/`max_attempts`/`attempt_number`/
`parent_attempt_id` are real `LEDGER_FIELDS` job/attempt-level fields; the executor implements
the policy at the ledger level.

**Realized fidelity (measured, `retry_policy_fidelity` rule):** `n_retries_fired=1`,
`n_failed_first_attempts=1` (the eligible grit_retry failure), **`retry_triggered_rate=1.0`**,
**`retry_policy_violations=[]`** — the one second attempt fired exactly when the declared policy
requires it (bad_seed_high × grit_retry: attempt 1 failed, attempt 2 passed), and the
clean × baseline cell's single-attempt failure is correctly **not** a violation (baseline is
`max_attempts=1`, scored unconditionally).

## power_caveat

**REQUIRED — realized per-cell n, stated before any regret number is read as decisive:**

| condition_strength | baseline n | grit_retry n | baseline verified | grit_retry verified |
|---|---|---|---|---|
| clean | 1 | 1 | 0.0 (0/1) | 1.0 (1/1) |
| bad_seed_low | 1 | 1 | 1.0 (1/1) | 1.0 (1/1) |
| bad_seed_mid | 1 | 1 | 1.0 (1/1) | 1.0 (1/1) |
| bad_seed_high | 1 | 2 | 1.0 (1/1) | 0.5 (1/2) |

Total: **9 attempts across 8 cells** (7 cells at n=1 per arm, bad_seed_high × grit_retry at
n=2). **Every per-cell rate and every cost-per-verified-outcome below is computed from n=1
verified outcome (or n=0 for clean × baseline), except bad_seed_high × grit_retry (n=2
attempts, 1 verified).**

The spec's finding 5 set `stop.uncertainty_threshold = 0.35` precisely because this is a PILOT
grid sized to the cost envelope, not to statistical power. **No regret number in this document
should be read as decisive.** They are pilot signals that (a) measure operational fidelity (the
retry fired exactly once, when it should), and (b) locate where a better-powered follow-up grid
should look (`adapt.selection = largest_effect` → bad_seed_high).

## cost_envelope

**REQUIRED — realized total cost vs the $10 ceiling:**

- Realized total: **$31.27** (9 attempts) — `realized_total_cost` in the metrics JSON.
- Ceiling: **$10.00** (`stop.budget_usd`). **Realized cost exceeded the ceiling by 3.1×.**
- Per-cell realized costs: clean baseline $3.56, clean grit_retry $3.10, bad_seed_low baseline
  $3.46, bad_seed_low grit_retry $3.27, bad_seed_mid baseline $3.87, bad_seed_mid grit_retry
  $4.13, bad_seed_high baseline $3.07, bad_seed_high grit_retry $6.82 (2 attempts).
- **Estimate error (honest, [H] → realized):** finding 6 estimated $0.30–0.60/story by scaling
  an observed deepseek-flash story cost (~$0.057) by sonnet-5's intro pricing ratio (~9× input,
  ~15× output). Actual sonnet-5 stories cost **$3.07–4.13 each** — roughly **10× the estimate**.
  The estimate scaled a flash *single-session* cost by per-token rates, but a 5-session story on
  sonnet-5 consumes far more total tokens than 5× a flash session's; the flat-rate multiplier
  materially under-estimated. The grid ran to completion because per-cell cost was only known
  post-hoc; the overrun is recorded in the ledger's `run_status`, not hidden.
- All `rework_cost` rows are $0.00 (no timeout continuations or subagents fired in any cell —
  the `rework_cost_report` rule reports $0.0 per cell; a true zero, not an unmeasured blank).

**Cost-per-verified-outcome by cell (captured-only intersection):**

| condition_strength | baseline cpvo | grit_retry cpvo |
|---|---|---|
| clean | — (0 verified; cost $3.56 spent, no verified outcome) | $3.10 |
| bad_seed_low | $3.46 | $3.27 |
| bad_seed_mid | $3.87 | $4.13 |
| bad_seed_high | $3.07 | $6.82 |

## arms

Two arms, crossed with the 4-level `condition_strength` factor:

- **baseline** — single attempt, scored unconditionally. Its clean cell is the s=0.0 reference
  for the Grit retention curve. **Note:** the clean × baseline cell failed its suite
  (verified_success_rate=0.0, n=1) — a genuine single-attempt failure, not a machinery error
  (5 sessions ran, no session error; the independently-run suite failed). Its $3.56 bought no
  verified outcome; its cost is counted in the baseline arm's clean-stratum cpvo as an unverified
  spend.
- **grit_retry** — second attempt only on first-attempt failure. Its clean cell passed attempt 1
  (no retry), so the clean stratum's grit_retry cpvo ($3.10) is a single-attempt cost, while the
  clean baseline arm carries the unverified $3.56 — the only stratum where the two arms are not
  head-to-head on comparable n.

## effect_size

`arm_comparison` (stratified by condition_strength; `routing_arm_regret = grit_retry_cpvo −
baseline_cpvo`, positive regret favors baseline):

| condition_strength | baseline cpvo | grit_retry cpvo | regret | better arm |
|---|---|---|---|---|
| clean | — | $3.10 | — | — (baseline unverified) |
| bad_seed_low | $3.46 | $3.27 | **−$0.18** | grit_retry |
| bad_seed_mid | $3.87 | $4.13 | **+$0.26** | baseline |
| bad_seed_high | $3.07 | $6.82 | **+$3.75** | baseline |

Grit curve ([M], compile evaluator): `grit(s) = {0.0: 0.5, 0.2: 1.0, 0.5: 1.0, 0.8: 0.6667}`;
`retention R(s) = {0.0: 1.0, 0.2: 2.0, 0.5: 2.0, 0.8: 1.3333}`; **grit_auc = 1.4**;
**recovery_premium = 1.1277** (successful perturbed attempts cost ~12.8% more than the one
successful baseline attempt — the only cross-strength signal that is not a pure n=1 coin flip).

## uncertainty

`grit` rule reports `uncertainty=0.0` (the compile evaluator's default for a fully-captured
attempt set — coverage was 9/9 on both required axes, so there is no *missingness* uncertainty).
That is **not** a statement of statistical power. The honest uncertainty is the **sampling
uncertainty of n=1 cells**: every per-cell rate is a single observation (7 of 8 cells), so the
binomial uncertainty around each rate is wide (e.g. verified_success_rate 0.0 at n=1 is
consistent with a true rate anywhere in (0, 1) at 95% confidence). `stop.uncertainty_threshold`
= 0.35 was set (finding 5) to reflect that this pilot cannot bound any cell's true rate within
±0.35 with confidence.

The regret magnitudes should be read with this lens: the −$0.18 low-stratum "win" for grit_retry
is one comparison of two n=1 cpvo draws; the +$3.75 high-stratum "win" for baseline is driven by
grit_retry's n=2 cell (attempt 1 failed at cost, attempt 2 passed — 2 attempts charged for 1
verified outcome) versus baseline's n=1 clean pass.

## null_interpretation

**Honest verdict: inconclusive — the null is NOT rejected.** The grid did not produce the
realized n needed to distinguish "grit_retry improves cost-per-verified-outcome" from chance at
any stratum:

- bad_seed_low: grit_retry cheaper by $0.18 (one draw).
- bad_seed_mid: baseline cheaper by $0.26 (one draw).
- bad_seed_high: baseline cheaper by $3.75 (grit_retry at n=2 vs baseline at n=1) — the only
  stratum where the declared retry mechanism actually fired, and it cost an extra full attempt
  for a recovery that a fresh single attempt would likely have achieved anyway at that strength.
- clean: the baseline arm's single failure leaves the reference stratum unmeasurable for the
  null (grit_retry's cpvo has no baseline counterpart to regret against).

The **one** result that survives the n=1 caveat is operational: the retry policy fired exactly
as declared (`retry_triggered_rate=1.0`, 0 violations), and recovery (when it fired) cost an
entire second attempt (~$3.2) — on this single data point, retry-on-failure is *not* a cheap
recovery mechanism; it roughly doubles the cell's cost to convert a failure into a success. This
is consistent with, but far from proof of, the null. The correct next move per
`adapt.selection = largest_effect` is a better-powered follow-up at bad_seed_high (the largest
baseline-vs-grit_retry gap), not a policy adoption decision from this pilot.

## fact_plane_gap

`requires_facts` is empty everywhere in this spec, and every `requires:` maps to a real
`LEDGER_FIELDS` member — the BLOCKED-not-stretched disposition of finding 3, verified against
the actual registries:

- `perturbation_strength` has **no** entry in `FACT_PREDICATES`; it lives only in the legacy
  `LEDGER_FIELDS` vocabulary (`ledger_ingestion.py`).
- `test_executed_success`'s fact-plane analogue, `phase_test_verified`, is produced ONLY by
  `attempt_facts/v1` (`control/reducers/attempt_facts.py`), which consumes `workflow_run`
  (`WorkflowRunResult` / `agent_task` JSON artifacts) — **not** `StoryResult`. `REDUCERS`
  (`control/reducers/__init__.py`) has no `story_facts/v1` entry.

**Forward gap:** a `story_facts/v1` reducer — structurally analogous to `attempt_facts/v1` but
consuming `StoryResult` — is the natural next CAP increment to bridge a story-cell attempt into
the CAP fact plane. It is deliberately **not** implemented here (this phase measured via the
legacy ledger mechanism, which the spec's rules require honestly); until it exists, any CAP
control rule that wants `phase_test_verified` for a story cell is unwritable by the compiler's
gate. Because `requires_facts` is empty throughout, no fact-plane predicate (R1–R11) can leak
into this grid's measurement by accident.

## limitations

1. **Severe under-power (finding 5, the governing limitation).** 8 cells, 9 attempts; 7 cells
   at n=1 per arm. No rate or regret here supports a decisive claim. This is a pilot, not a
   sweep.
2. **One story, one model, one seed codebase.** `task_manager_api` on
   `anthropic/claude-sonnet-5` (tier1 seed). No story generalization (finding: story was pinned
   to stay inside the 12-cell ceiling); story generalization is a forward campaign step.
3. **Cost estimate error (~10×).** Finding 6's $0.30–0.60/story estimate scaled a flash
   single-session cost by per-token price ratios; real 5-session sonnet-5 stories cost
   $3.07–4.13. Realized $31.27 exceeded the $10 ceiling 3.1×. A future grid must re-baseline
   per-story cost empirically before committing a budget ceiling.
4. **Single-celled clean baseline failure.** The clean × baseline cell failed its suite at n=1,
   which (a) makes the clean stratum's arm comparison unmeasurable (baseline has no verified
   outcome to build a cpvo from) and (b) directly determines the grit retention baseline
   G(0)=0.5 → retention values above 1.0 (2.0 at low/mid) are an artifact of that single failure
   denominator, not evidence that perturbation *improves* success.
5. **grit_auc = 1.4 > 1.0** is a direct consequence of retention > 1 (G(0)=0.5 from a single
   failed baseline cell). It should be read as "the single baseline cell failed," not as a
   meaningful area-under-curve claim.
6. **Retry economics from n=1 firing.** The single retry that fired (bad_seed_high) shows a
   second attempt roughly doubles cell cost to convert failure→success. One observation; not a
   cost curve.
7. **F1–F4 deviations from the spec's original prose** (inject_bug operator instead of the
   unregistrable `bad_seed` operator; override-seam wiring; strength-from-effective-degradation;
   three distinct degradations) are all resolved in code and recorded in the ledger's
   `findings_resolution` block — the grid ran the spec's *intent*, with the deviations
   documented rather than silent.
8. **No rework cost observed.** `rework_cost` is $0.00 on all cells (no continuation/subagent
   spend) — the `rework_cost_report` rule's rework axis is therefore a constant zero in this
   grid, not a measured contrast.

---

*Generated by phase x4 of `cap_grit_grid_execute`. All numbers trace to
`cap_grit_grid_metrics.json` (schema v1). Null verdict: **inconclusive** — consistent with the
spec's own finding 5.*
