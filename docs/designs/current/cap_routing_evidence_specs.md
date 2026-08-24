# CAP routing-evidence specs — gate results, adversarial review, release verdict

**Status:** authored, gated, adversarially reviewed. **Nothing has been run.** Every spec below
is `experiments/definitions/cap_*.yaml` — a declarative `ExperimentSpec`, not code; "running" one
means invoking the existing spec/compiler + execution machinery (`compile_experiment.py`,
`scripts/run_workflow.py`, `scripts/enqueue.py`/`worker.py`) against it, none of which this
workflow phase touched.

**Scope:** the four "start-now" policy-routing evidence specs named in
`workflows/repository/cap_routing_evidence_specs.yaml`'s question — E1 shadow comparison, E2
confidence cascade, E3 coverage-routing impact, E4 grit-strength grid — authored in phases
r1-r3, then attacked here (r4) by a fresh adversarial pass against the REAL registries
(`FACT_PREDICATES`, `REDUCERS`, `LEDGER_FIELDS`) and the real corpus (workflow-run JSONs, the KB
artifact store, `canonical_corpus`'s registry-governed resolvers). Two prior specs are visible in
this repo but out of scope here: `cap_session_routing_evidence.yaml` (the precedent this family
follows for its retrospective/coverage discipline) and `cap_gate_migration.yaml` (the workflow
that introduced the `requires_facts`/`decision_type` vocabulary these four specs use).

## Gate results (ran for real, not asserted)

Every spec was compiled against the ACTUAL, currently-installed registries — `FACT_PREDICATES`
(29 predicates) and `REDUCERS` (5 reducers) from `src/agentic_dynamics/control/`, `LEDGER_FIELDS`
(the legacy ledger schema) from `experiment_spec.py` — via `validate_spec` (the legacy
requires/produces gate) and `control.context_compiler.validate_spec_fact_contracts` (the real
R1-R11 CAP-fact gate). This is the SAME gate a future `scripts/run_workflow.py`/pipeline
invocation would apply; nothing here is a simulation of the gate.

| Spec | Rules | Legacy gate errors | R1-R11 errors | Grouping cells | Parse warnings |
|---|---|---|---|---|---|
| `cap_shadow_comparison.yaml` | 7 | 0 | 0 | 14 | 0 |
| `cap_confidence_cascade.yaml` | 8 | 0 | 0 | 4 | 0 |
| `cap_coverage_routing_impact.yaml` | 5 | 0 | 0 | 2 | 0 |
| `cap_grit_strength_grid.yaml` | 7 | 0 | 0 | 8 | 0 |

**Every spec parses, compiles to the 7-phase DAG (`validate → cells → execute → measure → compare
→ writeup → adapt`), and passes both gates with zero refusals and zero `from_dict` key
warnings.** "Grouping cells" is `compile_experiment.experiment_matrix()`'s factor cross-product —
for the three retrospective specs (E1-E3) this is an analysis GROUPING over an existing corpus,
not new work; only E4's 8 cells are live cells that would ever execute if run.

## Four-spec summary table

| | E1 `cap_shadow_comparison` | E2 `cap_confidence_cascade` | E3 `cap_coverage_routing_impact` | E4 `cap_grit_strength_grid` |
|---|---|---|---|---|
| **Mode** | retrospective | retrospective | retrospective | **LIVE** (only live spec) |
| **Arms** | `step_routing` (real, executes) vs `shadow_rule` (`route_next_job_v1` proposal, counterfactual, never applied) | `baseline` (single-model, as-recorded) vs `cascade_theta_{0.3,0.5,0.7}` (counterfactual escalation, never applied) | `coverage_corrected` (real `routing.compute_routing`) vs `legacy_zero_default` (re-derived `lab_task_routing.py` formula, same corpus) | `condition_strength` {clean, bad_seed_low/mid/high} × `policy_arm` {baseline, grit_retry}, model pinned `anthropic/claude-sonnet-5` |
| **Null hypothesis** | `shadow_rule` is not inferior to `step_routing` on cost-per-verified-outcome | no threshold improves cost-per-verified-outcome over baseline | zero changes (no recommendation differs between formulas) | `grit_retry` does not improve cost-per-verified-outcome over baseline |
| **Coverage pre-check(s)** | `phase_coverage_precheck` (attempt_cost_usd 420/420=100%, phase_status 420/420=100%, **phase_test_verified 0/420=0%** — r4 fix); `shadow_decision_coverage` (**0/2696** KB artifacts are `source_type=actuation`) | `confidence_coverage_precheck` (attempt_confidence 327/420=77.9%); `phase_success_coverage_precheck` (phase_status 420/420=100%); `job_outcome_join` (job_status 116/116=100%) | `entry_coverage_precheck` (cost_usd 64/64=100%, correctness 64/64=100%) | `attempt_coverage_precheck` (r4 addition — no data yet, 0 cells run) |
| **Cost envelope** | nominal (`budget_usd: 5.0`) — no live cells | nominal (`budget_usd: 5.0`) — no live cells | nominal (`budget_usd: 5.0`) — no live cells | **real**: ~$7.20 estimated (scaled from an observed $0.057 deepseek-flash story via `PROVIDER_PRICING`'s anthropic-sonnet5 ratio), **$10.00 ceiling** |
| **Grouping cells** | 14 (`routing_arm`×`model`) | 4 (`cascade_arm`) | 2 (`stats_method`) | 8 (`condition_strength`×`policy_arm`×`model`, ≤12 cap) |
| **requires_facts** | 8 entries, all real `FACT_PREDICATES` | 12 entries, all real `FACT_PREDICATES` | 0 (honestly — no reducer bridges this corpus into the fact plane) | 0 (honestly — BLOCKED, named explicitly; see below) |
| **Headline finding today** | BOTH arms' primary metric unmeasured at n=0, for two independent reasons (r4-corrected) | null untestable **by construction** — no attempt was ever actually escalated | null holds **trivially** — 100% coverage means the two formulas cannot diverge | not yet run — the only spec whose null is genuinely testable once it is |

## Adversarial findings, by the review's own six dimensions

### (1) Arm discriminability — is each arm's data actually there?

- **E1 — checked live, not assumed.** 116 workflow-run JSONs / 420 agent phases exist, but **0 of
  2696** KB artifacts are `source_type="actuation"` — `control.rules.make_shadow_router` has never
  been wired into a real `run_workflow.py` invocation. `shadow_decision_coverage` reports this as
  n=0/n, not a synthetic "0% regret." **r4 correction:** the step_routing side is not fully
  measurable either (see dimension 3) — this spec's ONLY fully-covered number today is the
  corpus's own existence.
- **E2 — checked live.** `attempt_confidence` is captured on 327/420 = 77.9% of agent phases —
  NOT near-zero, so `confidence_coverage_precheck` alone would not have flagged this spec
  INCONCLUSIVE. The real blocker is different in kind (see dimension 4).
- **E3 — checked live, the surprising direction.** Both `cost_usd` and `correctness` are captured
  on 64/64 = 100% of current `finding` rows — the arms exist and both compute, but a formula
  divergence needs a MISSING value to manifest, and none exists today. Discriminable in principle,
  degenerate in practice, on THIS corpus.
- **E4 — not yet run.** No cells have executed under this spec name; discriminability is
  unverifiable until it does. This is the expected, honest state for a not-yet-run live spec, not
  a defect.

### (2) Confounding

- **E1** — stratifies by `model` (a real grid factor, 7 levels); `arm_comparison` reads the
  regret within-model, not pooled.
- **E2** — **model × threshold, FIXED in this r4 pass.** The original spec stratified only by
  `job_status`; the review's own checklist named model × threshold as a distinct, unchecked risk.
  `arm_comparison` now also requires `attempt_model` (already required elsewhere in the same
  spec — no new instrumentation) and produces
  `escalation_trigger_rate_by_model_range_theta_{0.3,0.5,0.7}`, a max-min confound-magnitude
  indicator, without exploding the metric surface into a 7×3 table.
- **E3** — N/A by construction: both arms compute over the identical `routing_entries`, so there
  is no second data-generating process to confound with the first (unlike E1/E2/E4, which compare
  arms whose UNDERLYING attempts could differ).
- **E4** — **condition × strength, FIXED at authoring time, reconfirmed here.**
  `PerturbationCondition.CLEAN` structurally fixes `perturbation_strength=0.0` — a naive
  `perturbation_strength{low,mid,high} × condition{clean,bad_seed}` cross would have produced
  three operationally-identical `clean × {low,mid,high}` cells. Collapsed into one 4-level
  `condition_strength` factor instead of 6 naive levels; re-verified against
  `runtime/story/conditions.py` in this pass, not just cited from memory.

### (3) Coverage — any metric dividing by an uncaptured denominator?

- **E1 — a real gap FOUND and FIXED in this pass, not merely re-confirmed.** The original
  `phase_coverage_precheck` checked `attempt_cost_usd` and `phase_status` (both 100% covered) and
  read as "the step_routing side is sound." It missed that `verified_outcome` actually bottlenecks
  on `phase_test_verified`, captured on **0 of 420** agent phases — the SAME corpus-wide gap E2
  discovered independently. Found here by cross-referencing the two specs during the r4 sweep, then
  verified directly against E1's own corpus (not assumed transferable). `phase_coverage_precheck`
  now checks all three predicates; the header finding is corrected to state that BOTH arms'
  cost-per-verified-outcome are unmeasured today, not only the shadow side.
- **E2** — already checked three predicates at authoring time (confidence, phase_status,
  job_status); no new gap found in this pass.
- **E3** — already checked (cost_usd, correctness) at authoring time; the LEGACY arm's own
  zero-default formula is INTENTIONALLY not captured-only (that is the point of the comparison,
  not a bug).
- **E4 — a real gap FOUND and FIXED in this pass.** The spec originally had no coverage-precheck
  rule at all (reasoned, at authoring time, that "no cells have run yet" made one premature) — the
  odd one out in a family where the other three all open with this rule. Once cells DO run, nothing
  guarantees every attempt captures `actual_cost`/`test_executed_success` (a crashed session could
  leave either uncaptured). `attempt_coverage_precheck` now opens E4's rule list too.

### (4) Counterfactual soundness — escalation simulated on runs where it never happened

- **E1** — `shadow_rule_cost_per_verified_outcome` is a PROXY valid only on the agreement subset
  (proposed model == baseline model); on disagreement the counterfactual cost is unmeasurable and
  excluded, never zero-costed. Sound by construction, reconfirmed.
- **E2 — the family's deepest finding, reconfirmed unchanged in this pass.** `model_cascade` has
  ZERO call sites anywhere in the codebase — no attempt was EVER actually escalated. On the
  non-escalated subset, the cascade arm's cost is tautologically identical to baseline's (nothing
  diverged); on the escalated subset it is genuinely unknown. `routing_arm_regret_theta_*` is 0 by
  construction, never interpretable as "escalation confirmed harmless" — `null_testable_theta_*`
  is the honest signal, expected `false` on this spec's first run.
- **E3** — N/A: neither arm is a counterfactual: both formulas are ACTUALLY COMPUTED over real,
  captured entries; only the AGGREGATION differs.
- **E4** — N/A in the E1/E2 sense (no proposal-never-executed pattern — `grit_retry` genuinely
  executes a second attempt when triggered), but the retry policy's OPERATIONAL definition is
  itself DECLARED (`[P]` policy/prior), not verified against `reinterleave`'s exact mechanics — an
  accepted limitation, named at authoring time, unchanged here.

### (5) E4's grid size vs. effect size — is 12 cells (8 used) honest about power?

Reconfirmed, unchanged: 8 cells × ~1-2 attempts each ≈ 12-16 total attempts is enough to compute
the headline ratios per cell but not enough for a well-powered per-cell confidence interval.
`stop.uncertainty_threshold: 0.35` (wide, deliberately) and the writeup's REQUIRED
`power_caveat` section make this explicit — E4 is authored and labeled as a **pilot**, not a
publication-grade sweep, and its own header says so before any regret number could be
misread as decisive.

### (6) Gate vocabulary — any legacy `requires:` leak into the CAP-fact gate's blind spots?

Checked mechanically in this pass, not just re-asserted: `grep -n "plane: control"` across all
four specs returns zero rule definitions (one prose mention inside a comment, correctly negating
its own applicability); zero rules set `decision_type`. Since R9-R11 (contract binding) only apply
to `plane: control` rules with a `decision_type`, and none exist, those three refusal classes are
structurally unreachable here — not because the specs got lucky, but because every rule across the
family is `plane: measurement` by design (the load-bearing rule: this family GATHERS information,
it does not yet CONSUME it as policy). Re-ran `validate_spec` + `validate_spec_fact_contracts`
against all four specs after every r4 edit (findings 2 and 3's fixes) — 0 errors, confirmed live,
not carried over from the per-spec authoring passes.

## Finding log

| # | Spec | Dimension | Disposition | Fixed in this pass? |
|---|---|---|---|---|
| A | E2 | (2) confounding — model × threshold | FIXED — `arm_comparison` now requires `attempt_model`, produces `escalation_trigger_rate_by_model_range_theta_*` | yes |
| B | E4 | (3) coverage — no pre-check rule existed | FIXED — added `attempt_coverage_precheck` (cost_coverage_ratio, test_verification_coverage_ratio) | yes |
| C/D | E1 | (3) coverage — `phase_coverage_precheck` missed `phase_test_verified` (0/420) | FIXED — pre-check now checks all 3 predicates; header corrected: both arms unmeasured today, not one | yes |
| — | E1 | (1) shadow decisions at n=0 | accepted limitation — spec is gate-clean; becomes measurable once `make_shadow_router` is wired into a real run | recorded, not a spec defect |
| — | E2 | (4) escalation never executed anywhere | accepted limitation — the null is untestable by construction until a live cascade grid or an attempt-lineage proxy exists | recorded, not a spec defect |
| — | E3 | (1) 100% coverage today | accepted limitation — this run's value is prospective (a leading indicator), not a policy verdict | recorded, not a spec defect |
| — | E4 | (5) grid power | accepted limitation — explicitly labeled a pilot, `uncertainty_threshold: 0.35` | recorded, not a spec defect |
| — | E4 | (4) `grit_retry`'s exact mechanics | accepted limitation — declared `[P]`, not verified against `reinterleave` | recorded, not a spec defect |
| — | all | (6) gate vocabulary | clean — verified by grep + a full gate re-run after every fix | confirmed, no leak found |

**8 findings total: 3 fixed, 5 recorded as accepted limitations. Zero findings left unresolved
(every row above has an explicit disposition).**

## Cross-spec instrumentation gap (named once, not four times)

`phase_test_verified` — the independent test-verification predicate — is captured on **0 of 420**
agent phases in the current workflow-run corpus. This affects E1's `verified_outcome` directly and
is the reason `model_cascade` (E2) has never been measurable against a truly-independent success
signal. The forward fix is a real, scoped piece of work: wire `test_runner.run_suite` into the
`agent_task` workflow phase path (`scripts/run_workflow.py`) the same way it is already wired into
`runtime.story.orchestration.run_story` (which is why E4, a story-cell spec, does NOT have this
gap — `test_executed_success` is real, independently-verified data there). Naming this once here,
rather than in every spec that depends on it, is deliberate: the fix belongs to the workflow
runtime, not to any one spec's evaluator.

## Release verdict

**All four specs are gate-clean and ready to compile/execute in the sense that
`compile_spec`/`validate_spec_fact_contracts` accept them today with zero refusals.** "Ready to
run" beyond that means different things per spec, given the findings above — recommended order:

1. **E3 (`cap_coverage_routing_impact`) — run first.** Zero live cost, zero repository side
   effects, exercises the full retrospective pipeline (`experiment_matrix` → evaluation rules →
   `compare_arms`-style diff) end to end as a cheap smoke test before anything spends money. The
   expected result (zero changed recommendations, per finding 1/E3 above) is itself a useful,
   correct confirmation that the coverage-correction migration hasn't silently regressed anything
   on the current corpus — not a wasted run.
2. **E1 (`cap_shadow_comparison`) — run second.** Also zero live cost. Its own coverage pre-checks
   (`shadow_decision_coverage`, and now `phase_coverage_precheck`'s third predicate) are the
   leading indicators for two SEPARATE, real instrumentation gaps (the shadow router never wired;
   `phase_test_verified` never populated) — running it now establishes the documented n=0 baseline
   and gives future re-runs something to compare against as those gaps close.
3. **E2 (`cap_confidence_cascade`) — run third.** Also zero live cost. Recommended after E1 because
   E2's gap (`model_cascade` has no live execution path at all) is a strictly narrower,
   spec-specific limitation than E1's two corpus-wide gaps — running it documents the tautology
   finding formally (with real numbers in place of this doc's estimates) and produces the
   `escalation_trigger_rate` table, which is genuinely informative regardless of the null's
   testability.
4. **E4 (`cap_grit_strength_grid`) — run last, and only with explicit budget sign-off.** The only
   spec with real cost (~$7.20 estimated, $10 ceiling) and real repository side effects
   (sandboxed worktree commits). Recommended last because: (a) it is the only spec whose null is
   genuinely testable on its own first run, so there is no reason to rush it ahead of the free
   diagnostic runs above; (b) its own header already frames it as a PILOT — the honest next step
   after this pilot's realized per-cell n/cost are in hand is deciding whether to scale up, not
   assuming the 8-cell grid alone settles the question.

No spec is blocked from compiling or executing by any finding above — every "accepted limitation"
is a statement about how INFORMATIVE a run will be today, never about whether the spec is valid to
run. **PASS.**
