---
status: accepted
---
# CAP gate migration: spec rules -> requires_facts/decision_type

Workflow: `workflows/repository/cap_gate_migration.yaml`. Goal: migrate committed spec rules onto
the CAP I5 `requires_facts`/`decision_type` vocabulary against the real `FACT_PREDICATES`
registry (`src/agentic_dynamics/control/facts.py`, 29 predicates, produced by 5 reducers under
`src/agentic_dynamics/control/reducers/`), make the R1-R11 gate
(`src/agentic_dynamics/core/contracts.py:validate_fact_contracts`, wired to real data via
`src/agentic_dynamics/control/context_compiler.py:validate_spec_fact_contracts`) fire for real,
record every unmappable requirement as BLOCKED with its missing producer, and adversarially
rescan to zero. Skips the three in-flight workflows per the workflow's hard rule #2.

## Skipped (in-flight, never edited)

Per the workflow's hard rule #2, a live workflow runner may resume and re-read these spec files
at any time, so they are never opened for editing, only named here:

- `cap_shadow_campaign` (`workflows/repository/cap_shadow_campaign.yaml`)
- `cap_fact_auto_emit` (`workflows/repository/cap_fact_auto_emit.yaml`)
- `cap_addendum_implement` (`workflows/repository/cap_addendum_implement.yaml`)

Confirmed untouched: `git diff --stat` against all three is empty (checked in the adversarial
rescan below).

## m1 — Inventory and mapping methodology

Every spec under `experiments/definitions/*.yaml` and `workflows/**/*.yaml` that declares a
`rules:` key (77 specs, minus the 3 skipped above) was loaded via `ExperimentSpec.from_dict` and
every `RuleSpec` enumerated. Of those 77, 12 declare `rules: []` (present but empty) and
contribute no rows; the remaining 65 contribute all 129 in-scope rules. (The corpus glob finds 95
spec files total; `experiments/specs/STATUS.md`'s last regeneration — 2026-08-23, pre-dating this
very workflow's own spec file — reports 94, one less, which is exactly `cap_gate_migration.yaml`
itself, added by the commit that authored this workflow.)

For every rule with a non-empty legacy `requires` list, each requirement name was checked against
`FACT_PREDICATES` for an exact name match (there are zero — confirmed programmatically, see
Counts) and then against the nearest plausible predicate by reading the actual producing
reducer's source (`control/reducers/{attempt_facts,job_facts,policy_facts,workflow_facts,
spec_status}.py`) to determine whether that reducer is genuinely producible for the requiring
spec's own workload — never on name similarity alone. This is the load-bearing finding of the
whole migration:

**`FACT_PREDICATES` (I0-I3) is scoped entirely to CAP's own `agent_task` workflow-execution
meta-state** — spec lifecycle, job/phase status, cost, and workflow health — all derived from
either (a) the typed `WorkflowRunResult`/`PhaseResult` JSON that `scripts/run_workflow.py` writes
for `agent_task` workflows (`attempt_facts/v1`, `job_facts/v1`, `workflow_facts/v1`), or (b) the
spec YAML's own declared `StopSpec`/model-pool configuration (`policy_facts/v1`), or (c) the spec
lifecycle index (`spec_status/v1`). **No reducer consumes the story/experiment ledger**
(`ledger_ingestion.py`'s `AttemptRecord`/`JobRecord` rows, populated by
`run.py`/`enqueue.py`/`worker.py` for `story`/`experiment`/`task`-kind specs) — so every legacy
requirement naming a research-measurement signal (`confidence`, `first_pass`,
`perturbation_strength`, `test_executed_success`, `cache_hit`, token splits, cost components,
`budget`/`deadline_slack`, lineage fields) is structurally unreachable from the fact plane for
those specs, regardless of name similarity to a real predicate. A second, unrelated class of
legacy requirements (`fact_schema`, `record_factory`, `shell_nav_done`, `spec_index`, …) are
bespoke per-workflow completion markers — a category mismatch with "reusable fact about the
world," not an instrumentation gap.

The one exception is `policy_facts/v1`, which reads `StopSpec.budget_usd`/`max_attempts`/
`model_pool` directly off **the spec itself** — producible for every spec regardless of
`workflow.kind`. That is the one honest migration in the entire corpus (below).

## m2 — The one honest migration

`experiments/definitions/routing_regret_under_degradation.yaml`, rule `budget_ceiling` (control,
`requires: [budget, forecast_cost, actual_cost]`) gets:

```yaml
requires_facts: [{fact: max_spend_usd, scope: parent, min_authority: POLICY,
                   on_missing: halt, on_conflict: halt}]
```

Verified against R1-R8: `max_spend_usd` is declared (R1), produced by `policy_facts/v1` (R2), its
producer consumes `spec` (not a predicate, so R3 is inapplicable by design), `scope: parent` is a
relative keyword so R4's compile-time scope check does not apply (correctly deferred to the I4
Context Compiler at runtime), `min_authority: POLICY != ADVISORY` (R5), `max_spend_usd` is not
volatile so R6's `max_age_seconds` requirement does not apply, `on_missing`/`on_conflict` are both
valid vocabulary (R7), and no `value_type` override is set (R8 inapplicable). No `decision_type` is
set (no contract matches this decision, so none is declared — guard #5). `forecast_cost` and
`actual_cost` have no honest mapping and are recorded BLOCKED (see the per-requirement detail
below); the legacy `requires: [budget, forecast_cost, actual_cost]` is left untouched (additive
migration only, per design).

**Real gate run, full in-scope corpus, with this migration applied:** `validate_spec_fact_contracts`
called against every one of the 77 in-scope specs (real `FACT_PREDICATES`/`REDUCERS`/loaded
`experiments/contexts/*.yaml` contracts) returns **zero refusals**.

## m2 — Exercising the gate for real: two refusals, fired and resolved

Both demonstrations below use REAL corpus rules (not synthetic scratch data) with a plausible,
initially-tempting `requires_facts` mapping, run through `validate_spec_fact_contracts` against
the live registries, then reverted (never persisted) once the refusal confirmed the mapping was
unfixable — exactly the workflow's instruction: "either the mapping was wrong (fix it) or the
requirement genuinely has no producer (drop it, record BLOCKED)."

### Refusal 1 — R4 (scope reachability), `rag_bare_vs_augmented` / `augment_prompt`

`rag_bare_vs_augmented.yaml` is the one in-scope spec whose `workflow.kind: agent_task` means its
cells genuinely DO write `WorkflowRunResult` artifacts — so unlike every other spec, its
`test_executed_success` requirement is tempting: `phase_test_verified` really is producible for
this spec's own workload. But the rule's metric is declared `over: cell` (a whole grid cell —
model x policy x task — not one phase), while `phase_test_verified` is `attempt` (single-phase)
scoped with `aggregates_from: ""` (no rollup reducer declared). Attempting:

```
requires_facts: [{fact: phase_test_verified, scope: job, min_authority: MEASURED,
                   on_missing: halt, on_conflict: halt}]
```

fires, verbatim, against the real registries:

```
rule "augment_prompt" requires 'phase_test_verified' at scope 'job' from a 'attempt'-scoped
fact — no aggregation reducer exists. Declare one or raise the requirement's scope. (R4)
```

**Resolution:** unfixable today — no cell/job-level aggregation reducer over `phase_test_verified`
exists. Reverted (never persisted). Recorded BLOCKED: needs a cell-level aggregation reducer
(`aggregates_from: phase_test_verified` on a new job-scoped predicate) before this can ever be
required at job/cell scope.

### Refusal 2 — R5 (no control rule may consume ADVISORY), `routing_regret_under_degradation` / `model_cascade`

`attempt_confidence`'s own epistemic status, per `attempt_facts.py`'s `_EPISTEMIC_BY_PREDICATE`, is
hardcoded `ADVISORY` (a self-report) — so writing the requirement at the authority the data
*actually* carries:

```
requires_facts: [{fact: attempt_confidence, scope: self, min_authority: ADVISORY,
                   on_missing: halt, on_conflict: halt}]
```

fires, verbatim, against the real registries:

```
rule "model_cascade" requires 'attempt_confidence' at min_authority ADVISORY — a control rule
may never consume an advisory value. (R5)
```

**Resolution:** unfixable in principle, not just today — `attempt_confidence` can never legally
satisfy ANY control rule's `requires_facts`, at any `min_authority` setting, because its true
authority is always below every legal `min_authority` floor (`MIN_AUTHORITY_LEVELS` excludes
`ADVISORY` by construction). This is independent of, and in addition to, the producer-domain gap
already recorded (this spec is `workflow.kind: story`, so `attempt_confidence` is doubly
unreachable). Reverted (never persisted). Recorded BLOCKED.

These two confirm the R1-R11 validator is not vacuous against real data: it inspects the actual
`FACT_PREDICATES`/`REDUCERS` registries, correctly refuses a scope-unreachable requirement and an
authority-illegal one, and the one genuine migration in the corpus passes it cleanly.

## m3 — Adversarial rescan

Independent re-enumeration and re-checks, run after m1/m2:

1. **Re-run the gate independently**, loading every in-scope spec via `ExperimentSpec.from_yaml`
   (`load_spec`, not the manual `yaml.safe_load` + `from_dict` path m1/m2 used) and calling
   `validate_spec_fact_contracts` again: **0 refusals** across every spec that declares at least
   one rule (65 of the 77 "has a `rules:` key" specs — the other 12 declare `rules: []` and were
   never going to produce a refusal either way).
2. **Weakened-mapping hunt:** the one migrated requirement (`budget_ceiling`) sets
   `min_authority: POLICY` (the highest tier `FACT_PREDICATES` MIN_AUTHORITY_LEVELS defines — not
   lowered) and `on_missing: halt` / `on_conflict: halt` (not degraded to `classify`) — matches the
   legacy requirement's intent (an admission decision made without knowing the ceiling is unsafe,
   same reasoning the `route_next_job` contract already uses for its own invariants). No
   weakening found.
3. **Phantom `decision_type` hunt:** `grep -rn "decision_type:" experiments/definitions
   workflows` returns nothing — no rule anywhere in the corpus sets `decision_type`, so R9/R10
   never apply and there is no phantom contract to find.
4. **Stretched-predicate hunt:** `grep -rln "requires_facts" experiments/definitions workflows`
   finds exactly one YAML with a REAL `rules[].requires_facts` key
   (`routing_regret_under_degradation.yaml`, the one migration above). The other five hits
   (`cap_addendum_implement.yaml`, `cap_gate_scan.yaml`, `cap_gate_migration.yaml`,
   `cap_implement_repair.yaml`, `cap_addendum_design.yaml`) are prose mentions of the term inside
   phase prompts/context blocks, not `rules:` entries — confirmed by inspecting each match's line.
   No GAP row was secretly "fixed" by stretching a predicate outside its producible scope.
5. **In-flight specs untouched:** `git diff --stat` against `cap_shadow_campaign.yaml`,
   `cap_fact_auto_emit.yaml`, `cap_addendum_implement.yaml` is empty. Confirmed.
6. **Index parity — deviation, recorded and justified:** `python scripts/spec_status.py` was run
   once during m2 and immediately reverted (`git checkout -- experiments/specs/{STATUS.md,
   index.json}`) because `experiments/results/workflows/` — the run-ledger directory
   `spec_status.py` reads for `last_run`/`ok`/`model`/`cost`/`n_runs` — is git-ignored and does not
   exist in this worktree (`/tmp/wt_gate_migration`), a fresh checkout with no local run history.
   Regenerating here replaced every spec's real completion history with "never run," which would
   have been a destructive false statement if committed (`STATUS.md`'s "Work remaining" jumped
   from 25 open / 69 completed to a fabricated 86 open / 9 completed). This edit does not require
   an index refresh anyway: the lifecycle index tracks `name`/`kind`/`repeatable`/`status`/
   `version`/`supersedes`/`last_run`/`ok`/`model`/`cost`/`n_runs` — none of which changed (only a
   rule's `requires_facts` field did, which the index does not track). Index parity holds without
   regeneration; forcing one in this environment would have corrupted it instead. Re-verified on
   this rescan: `git diff 9a061ca65 --stat -- experiments/specs/STATUS.md experiments/specs/index.json`
   is empty — neither commit this migration produced touched the index.

### New finding this pass (7) — `requires_facts` on a bare `RuleSpec` has no runtime consumer yet

Not caught in the first m3 pass: `grep -rn "\.requires_facts\b" src/` shows the field is read in
exactly two places — `experiment_spec.py` (dataclass plumbing) and
`core/contracts.py:validate_fact_contracts` (the compile-time R1-R11 gate). The actual runtime
resolver, `context_compiler.py:compile_context`, reads `contract.requires_facts` — a
**`ContractSpec`**, loaded from `experiments/contexts/<decision_type>.yaml` by `decision_type` —
and never touches `RuleSpec.requires_facts` directly. `context_compiler.py:79`'s own comment
states the relationship precisely: "a spec's `RuleSpec.requires_facts` (I5) is the per-spec
binding *to* one [contract]." A rule with `requires_facts` but no `decision_type` — every rule in
this migration, including `budget_ceiling` — is therefore not bound to anything: its
`requires_facts` is proven producible by the compile-time gate but has **zero runtime effect**
until a `decision_type` contract for that decision exists and is declared alongside it. This is
consistent with the workflow's own guard #5 ("decision_type only where a contract exists... no
phantom contracts") — no contract matches `budget_ceiling`'s decision, so leaving `decision_type`
unset is the correct, non-phantom choice — but it means **this migration is a compile-time-only
proof of producibility, not a live control-loop wiring.** Recorded here rather than "fixed":
inventing a `budget_ceiling` contract file to wire it live would be exactly the kind of scope
creep m1's methodology and guard #5 both rule out (a contract must correspond to a decision the
system already makes deterministically, per `route_next_job`'s own precedent — no such
incumbent exists for budget admission). Not a defect; a scope caveat worth stating plainly so a
future reader does not assume `budget_ceiling` is now live-gated.

No further findings — the migration and gate exercise are adversarially clean.

### Finding table (this rescan)

| # | Attack vector | Result |
|---|---|---|
| 1 | Independent re-enumeration + gate re-run | 0 refusals, 77 specs / 129 rules, matches m1/m2 exactly |
| 2 | Weakened mappings (authority/scope/on_missing) | None found — `budget_ceiling` uses `POLICY`/`halt`/`halt`, the strictest legal settings |
| 3 | Phantom `decision_type` | None found — zero rules set `decision_type` anywhere in the corpus |
| 4 | Stretched predicates behind a "fixed" GAP | None found — exactly one real `requires_facts` key exists; the other 5 grep hits are prose |
| 5 | In-flight specs touched | None — `git diff` against all 3, and against `9a061ca65`, is empty |
| 6 | Index parity | Holds — confirmed untouched by either commit; regeneration deviation re-justified |
| 7 | Runtime wiring of the migrated `requires_facts` | New finding: compile-time-only, no `compile_context` consumer without a `decision_type` contract — documented, not a defect |

## Counts

- Specs in scope (declare a `rules:` key, minus the 3 skipped): 77 (of which 12 declare `rules: []`
  and contribute no rows; 65 contribute all rows below)
- Rules in scope: 129
- Rules with no requirements (nothing to migrate): 77
- Requirement instances **MIGRATED** (honest `FACT_PREDICATES` mapping): 1 (`budget` ->
  `max_spend_usd`, `routing_regret_under_degradation`/`budget_ceiling`)
- Requirement instances **GAP** (BLOCKED, missing producer named): 101
  - structural ledger-domain gaps (a real research signal, but no CAP reducer bridges the
    story/experiment ledger into the fact plane): 63
  - out-of-scope bespoke deliverable markers (category mismatch, not an instrumentation gap): 38
- Distinct requirement names seen: 60, of which exactly 0 are an exact `FACT_PREDICATES` name
  match (confirmed programmatically) and 27 are legacy `LEDGER_FIELDS` names (the rest bespoke)
- Real gate refusals fired and resolved during the migration: 2 (R4, R5 — see m2)
- Real gate refusals on the final in-scope corpus: 0

## Instrumentation backlog (every BLOCKED row's missing producer, deduplicated)

1. **A story/experiment-ledger analogue of `attempt_facts/v1`.** The single largest gap class:
   `confidence`, `test_executed_success`, `accepted`, `evaluator_independent`, `first_pass`,
   `cache_hit`, token splits, and cost components all have a real, measured value on the
   story/experiment ledger (`ledger_ingestion.py`) but no reducer emits them as `CanonicalFact`s —
   `attempt_facts/v1` only reads `workflow_run` (`agent_task`) artifacts. Closing this unlocks
   `model_cascade`/`dynamics`/`grit`/`first_pass_quality` as genuinely migratable control/
   measurement rules.
2. **A session-lineage reducer** over `parent_attempt_id`/`attempt_number`/`escalation_from`/
   `escalation_to` — needed for `cap_session_routing_evidence`'s `session_lineage_sim` and
   `rework_cost` rules.
3. **A value-accounting reducer** for `value`/`rework_cost`/`reuse_value` — needed for
   `routing_regret_under_degradation`'s `outcome_multiplier` and `self_recommending_experiment`'s
   `measure_regret`.
4. **A cell/job-level aggregation reducer over `phase_test_verified`** (an `aggregates_from`
   rollup) — needed before any `over: cell` metric on an `agent_task`-kind spec (currently only
   `rag_bare_vs_augmented`) can require it at job/cell scope (Refusal 1 above).
5. **`deadline_slack` has no producer anywhere in the codebase** — `control/facts.py`'s own
   `PredicateSpec` docstring names it as the worked example of an unwritable `LEDGER_FIELDS` entry.
   Not this migration's job to fix; recorded for visibility since `remediation_data_integrity`'s
   `dynamics` rule still names it in legacy `requires`.

Everything else (the 38 bespoke-marker GAPs) needs no instrumentation action — they are
per-workflow deliverable checklists, correctly gated by the pre-existing legacy `requires`/
`produces` validator, and out of `FACT_PREDICATES`' scope by design.

## PASS/FAIL

**PASS.** m1 inventory complete (129/129 rules mapped, every row names its predicate or GAP with a
missing-producer reason). m2 migration applied (1 honest match), the gate exercised for real (2
refusals fired against the live registries and correctly resolved), 0 refusals on the full
in-scope corpus. m3 adversarial rescan (two passes): first pass 0 findings beyond the recorded
index-regeneration deviation; second pass surfaces one new, non-blocking scope caveat (finding 7:
the migrated `requires_facts` is compile-time-only — no `decision_type` contract binds it to
`compile_context` yet) — documented, not fixed, because fixing it would mean inventing a phantom
contract, which guard #5 explicitly forbids. In-flight specs and the lifecycle index confirmed
untouched across both passes.

## Full per-spec mapping table
## `cap_session_routing_evidence`
`experiments/definitions/cap_session_routing_evidence.yaml` -- workflow.kind=`experiment`, artifact_kind=`experiment`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `session_lineage_sim` | measurement | `parent_attempt_id`, `attempt_number`, `escalation_from`, `escalation_to`, `cache_hit` | `arm_assignment`, `fork_point`, `escalation_point`, `cache_reuse` | `parent_attempt_id` -> **GAP**<br>`attempt_number` -> **GAP**<br>`escalation_from` -> **GAP**<br>`escalation_to` -> **GAP**<br>`cache_hit` -> **GAP** |
| `verified_success` | measurement | `test_executed_success`, `accepted`, `evaluator_independent` | `verified_outcome`, `verified_success_rate` | `test_executed_success` -> **GAP**<br>`accepted` -> **GAP**<br>`evaluator_independent` -> **GAP** |
| `cost_per_verified_outcome` | measurement | `cost_inference`, `cost_orchestration`, `actual_cost`, `verified_outcome` | `cost_per_verified_outcome` | `cost_inference` -> **GAP**<br>`cost_orchestration` -> **GAP**<br>`actual_cost` -> **GAP**<br>`verified_outcome` -> **GAP** |
| `cache_utilization` | measurement | `cache_hit` | `cache_hit_rate` | `cache_hit` -> **GAP** |
| `rework_cost` | measurement | `rework_cost`, `attempt_number`, `parent_attempt_id` | `rework_cost_per_verified_outcome` | `rework_cost` -> **GAP**<br>`attempt_number` -> **GAP**<br>`parent_attempt_id` -> **GAP** |
| `token_growth` | measurement | `tokens_in`, `tokens_out`, `tokens_answer`, `tokens_explanation`, `attempt_number` | `token_growth_ratio` | `tokens_in` -> **GAP**<br>`tokens_out` -> **GAP**<br>`tokens_answer` -> **GAP**<br>`tokens_explanation` -> **GAP**<br>`attempt_number` -> **GAP** |

## `explanation_tax`
`experiments/definitions/explanation_tax.yaml` -- workflow.kind=`task`, artifact_kind=`experiment`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `instrument_token_split` | measurement | _(none)_ | `answer`, `explanation` | no requirements -- nothing to migrate |
| `output_decomposition` | measurement | `answer`, `explanation` | `answer_ratio`, `explanation_ratio` | `answer` -> **GAP**<br>`explanation` -> **GAP** |
| `narration_value` | measurement | `explanation`, `first_pass` | `narration_predicts_outcome` | `explanation` -> **GAP**<br>`first_pass` -> **GAP** |
| `reasoning_side_channel` | measurement | `tokens_reasoning` | `reasoning_ratio` | `tokens_reasoning` -> **GAP** |

## `process_perturbation_resample`
`experiments/definitions/process_perturbation_resample.yaml` -- workflow.kind=`task`, artifact_kind=`experiment`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `instrument_grit_inputs` | measurement | _(none)_ | `perturbation_strength`, `test_executed_success` | no requirements -- nothing to migrate |
| `grit` | measurement | `perturbation_strength`, `test_executed_success` | `grit`, `grit_auc` | `perturbation_strength` -> **GAP**<br>`test_executed_success` -> **GAP** |
| `basin_escape` | measurement | _(none)_ | `escape` | no requirements -- nothing to migrate |
| `basin_verdict` | measurement | `escape` | `basin_type` | `escape` -> **GAP** |

## `rag_bare_vs_augmented`
`experiments/definitions/rag_bare_vs_augmented.yaml` -- workflow.kind=`agent_task`, artifact_kind=`experiment`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `measure_outcome` | measurement | _(none)_ | `test_executed_success`, `cost`, `flail` | no requirements -- nothing to migrate |
| `augment_prompt` | control | `test_executed_success`, `cost`, `flail` | `augmented_prompt` | `test_executed_success` -> **GAP**<br>`cost` -> **GAP**<br>`flail` -> **GAP** |

## `routing_kb_experiment_design`
`experiments/definitions/routing_kb_experiment_design.yaml` -- workflow.kind=`agent_task`, artifact_kind=`experiment`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|

## `routing_kb_experiment_design_research`
`experiments/definitions/routing_kb_experiment_design_research.yaml` -- workflow.kind=`agent_task`, artifact_kind=`experiment`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|

## `routing_regret_under_degradation`
`experiments/definitions/routing_regret_under_degradation.yaml` -- workflow.kind=`story`, artifact_kind=`experiment`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `first_pass_quality` | measurement | `attempt_number`, `accepted`, `evaluator_independent` | `first_pass_rate`, `accepted_outcome` | `attempt_number` -> **GAP**<br>`accepted` -> **GAP**<br>`evaluator_independent` -> **GAP** |
| `grit` | measurement | `perturbation_strength`, `test_executed_success`, `condition` | `grit`, `retention`, `grit_auc`, `recovery_premium` | `perturbation_strength` -> **GAP**<br>`test_executed_success` -> **GAP**<br>`condition` -> **GAP** |
| `outcome_multiplier` | measurement | `value`, `rework_cost`, `reuse_value` | `net_value` | `value` -> **GAP**<br>`rework_cost` -> **GAP**<br>`reuse_value` -> **GAP** |
| `model_cascade` | control | `confidence` | `escalation_decision` | `confidence` -> **GAP** |
| `budget_ceiling` | control | `budget`, `forecast_cost`, `actual_cost` | `admit_or_halt` | `budget` -> **MIGRATED** (`max_spend_usd`)<br>`forecast_cost` -> **GAP**<br>`actual_cost` -> **GAP** |

## `auto_posthoc_wiring`
`workflows/operations/auto_posthoc_wiring.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `posthoc_autotrigger` | measurement | `first_pass`, `test_executed_success` | `posthoc_auto` | `first_pass` -> **GAP**<br>`test_executed_success` -> **GAP** |
| `ready_for_policy` | control | `posthoc_auto` | `admit_policy` | `posthoc_auto` -> **GAP** |

## `labbook_refresh`
`workflows/operations/labbook_refresh.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `labbooks_fresh` | measurement | `test_executed_success`, `first_pass` | `story_side_fresh` | `test_executed_success` -> **GAP**<br>`first_pass` -> **GAP** |
| `data_regenerated` | control | `story_side_fresh` | `site_ready` | `story_side_fresh` -> **GAP** |

## `posthoc_pipeline`
`workflows/operations/posthoc_pipeline.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `posthoc_complete` | measurement | `test_executed_success`, `first_pass` | `posthoc_ready` | `test_executed_success` -> **GAP**<br>`first_pass` -> **GAP** |
| `review_admit` | control | `posthoc_ready` | `ready_for_policy` | `posthoc_ready` -> **GAP** |

## `queue_steer`
`workflows/operations/queue_steer.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `measure_provider_spread` | measurement | _(none)_ | `provider_imbalance` | no requirements -- nothing to migrate |
| `reinterleave_queue` | control | `provider_imbalance` | `reinterleaved` | `provider_imbalance` -> **GAP** |

## `registry_canonicalize`
`workflows/operations/registry_canonicalize.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `canonicalized` | measurement | _(none)_ | `noop_relabeled`, `single_task_registered`, `summary_retired` | no requirements -- nothing to migrate |

## `canonical_publication_closure`
`workflows/repository/canonical_publication_closure.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `publication_closed` | measurement | _(none)_ | `singular_door`, `resolution_fail_closed`, `contracts_semantic`, `counts_scoped` | no requirements -- nothing to migrate |

## `canonical_state_design`
`workflows/repository/canonical_state_design.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `store_inventory` | measurement | _(none)_ | `store_map` | no requirements -- nothing to migrate |
| `design_coverage` | measurement | _(none)_ | `questions_answered`, `migration_plan` | no requirements -- nothing to migrate |
| `traceability` | measurement | `store_map`, `migration_plan` | `corruption_prevented` | `store_map` -> **GAP**<br>`migration_plan` -> **GAP** |

## `canonical_state_finalize`
`workflows/repository/canonical_state_finalize.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `gaps_closed` | measurement | _(none)_ | `consumer_operation_handled`, `projection_derived`, `autoclear_wired` | no requirements -- nothing to migrate |
| `rail_preserved` | measurement | `consumer_operation_handled` | `flag_only_rail` | `consumer_operation_handled` -> **GAP** |

## `canonical_state_implement`
`workflows/repository/canonical_state_implement.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `steps_implemented` | measurement | _(none)_ | `plan_steps_done` | no requirements -- nothing to migrate |
| `tests_green` | measurement | _(none)_ | `verification_passed` | no requirements -- nothing to migrate |
| `rail_preserved` | measurement | `plan_steps_done` | `flag_only_rail` | `plan_steps_done` -> **GAP** |

## `canonical_state_round2`
`workflows/repository/canonical_state_round2.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `delta_coverage` | measurement | _(none)_ | `deltas_addressed` | no requirements -- nothing to migrate |
| `plan_completeness` | measurement | _(none)_ | `implementation_plan` | no requirements -- nothing to migrate |
| `traceability` | measurement | `deltas_addressed`, `implementation_plan` | `gaps_closed` | `deltas_addressed` -> **GAP**<br>`implementation_plan` -> **GAP** |

## `cap_addendum_design`
`workflows/repository/cap_addendum_design.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `cap_addendum_designed` | measurement | _(none)_ | `review_written`, `design_written`, `design_verified`, `adversarial_clean` | no requirements -- nothing to migrate |

## `cap_gate_migration`
`workflows/repository/cap_gate_migration.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `cap_gate_migrated` | measurement | _(none)_ | `inventory_documented`, `specs_migrated`, `gate_fired`, `migration_adversarial_clean` | no requirements -- nothing to migrate |

## `cap_gate_scan`
`workflows/repository/cap_gate_scan.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `cap_gate_scanned` | measurement | _(none)_ | `corpus_scanned`, `refusals_closed`, `rescan_clean` | no requirements -- nothing to migrate |

## `cap_i0_i3_remediation`
`workflows/repository/cap_i0_i3_remediation.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `cap_i0_i3_remediated` | measurement | _(none)_ | `attempt_identity_safe`, `null_semantics_safe`, `ladder_integrated`, `remediation_adversarial_clean` | no requirements -- nothing to migrate |

## `cap_implement_repair`
`workflows/repository/cap_implement_repair.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `cap_implement_repairable` | measurement | _(none)_ | `paths_repointed`, `spec_unpaused`, `notes_recorded`, `audit_clean` | no requirements -- nothing to migrate |

## `cap_session_routing_spec`
`workflows/repository/cap_session_routing_spec.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `cap_session_routing_specced` | measurement | _(none)_ | `spec_authorized`, `gate_passed`, `validity_checked` | no requirements -- nothing to migrate |

## `consolidation_release`
`workflows/repository/consolidation_release.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `consolidation_staged` | measurement | _(none)_ | `coverage_complete`, `specs_gate_passing`, `sequence_sound` | no requirements -- nothing to migrate |

## `consolidation_release_execute`
`workflows/repository/consolidation_release_execute.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `consolidation_executed` | measurement | _(none)_ | `stages_complete`, `gates_green`, `log_complete` | no requirements -- nothing to migrate |

## `consolidation_stage_0_architecture_spine`
`workflows/repository/consolidation_stage_0_architecture_spine.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `architecture_spine_delivered` | measurement | _(none)_ | `arch_spine_single`, `doc_lifecycle_statused`, `cap_frozen`, `supersession_mapped` | no requirements -- nothing to migrate |

## `consolidation_stage_1_package_move`
`workflows/repository/consolidation_stage_1_package_move.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `package_move_delivered` | measurement | _(none)_ | `imports_resolve`, `dependency_lint_green`, `deprecated_retired`, `bootstrap_centralized` | no requirements -- nothing to migrate |

## `consolidation_stage_2_experiments_workflows_split`
`workflows/repository/consolidation_stage_2_experiments_workflows_split.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `split_delivered` | measurement | _(none)_ | `classification_guard_green`, `spec_paths_resolve`, `workorders_separated` | no requirements -- nothing to migrate |

## `consolidation_stage_3_cli_classification`
`workflows/repository/consolidation_stage_3_cli_classification.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `cli_classification_delivered` | measurement | _(none)_ | `cli_commands_cover_scripts`, `scripts_classified`, `review_worker_retired`, `archive_populated` | no requirements -- nothing to migrate |

## `consolidation_stage_4_instruction_surfaces`
`workflows/repository/consolidation_stage_4_instruction_surfaces.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `instruction_surfaces_delivered` | measurement | _(none)_ | `generated_surfaces_match`, `single_instruction_source` | no requirements -- nothing to migrate |

## `consolidation_stage_5_apps_realignment`
`workflows/repository/consolidation_stage_5_apps_realignment.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `apps_realignment_delivered` | measurement | _(none)_ | `apps_import_system`, `apps_no_domain_rules`, `dual_firebase_synced`, `readme_reframed` | no requirements -- nothing to migrate |

## `consolidation_stage_6_verification_release`
`workflows/repository/consolidation_stage_6_verification_release.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `consolidation_verified` | measurement | _(none)_ | `coverage_complete`, `ws_dispositioned`, `invariants_intact`, `dual_firebase_deployed` | no requirements -- nothing to migrate |

## `context_abstraction_implement`
`workflows/repository/context_abstraction_implement.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `fact_schema` | measurement | _(none)_ | `fact_schema` | no requirements -- nothing to migrate |
| `reducers` | measurement | `fact_schema` | `spec_facts`, `ledger_facts`, `workflow_facts` | `fact_schema` -> **GAP** |
| `compiler` | measurement | `workflow_facts` | `control_snapshots` | `workflow_facts` -> **GAP** |
| `contracts` | measurement | `fact_schema` | `fact_contracts` | `fact_schema` -> **GAP** |
| `shadow_controller` | measurement | `control_snapshots`, `fact_contracts` | `shadow_decisions` | `control_snapshots` -> **GAP**<br>`fact_contracts` -> **GAP** |
| `decision_calibration` | measurement | `shadow_decisions` | `decision_regret` | `shadow_decisions` -> **GAP** |
| `apply_gate` | measurement | `shadow_decisions` | `apply_seam` | `shadow_decisions` -> **GAP** |

## `context_abstraction_plane`
`workflows/repository/context_abstraction_plane.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `component_audit` | measurement | _(none)_ | `component_gap_map` | no requirements -- nothing to migrate |
| `design_coverage` | measurement | _(none)_ | `context_plane_design` | no requirements -- nothing to migrate |
| `traceability` | measurement | `component_gap_map`, `context_plane_design` | `design_input_covered` | `component_gap_map` -> **GAP**<br>`context_plane_design` -> **GAP** |

## `control_room_hardening`
`workflows/repository/control_room_hardening.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `boundary_hardened` | measurement | _(none)_ | `experiments_gated`, `delivery_fixed`, `inventory_regen`, `actuation_recorded` | no requirements -- nothing to migrate |

## `control_room_posthoc_visibility`
`workflows/repository/control_room_posthoc_visibility.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `pipeline_visibility` | measurement | _(none)_ | `posthoc_visible` | no requirements -- nothing to migrate |

## `control_room_refresh`
`workflows/repository/control_room_refresh.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `control_room_refreshed` | measurement | _(none)_ | `ui_audited`, `design_delivered`, `implementation_verified`, `adversarial_polished` | no requirements -- nothing to migrate |

## `control_room_ui_implement`
`workflows/repository/control_room_ui_implement.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `design_implemented` | measurement | _(none)_ | `shell_nav_done`, `boards_done`, `mobile_visual_done` | no requirements -- nothing to migrate |
| `invariants_held` | measurement | `shell_nav_done` | `no_new_endpoints`, `flag_only_rail`, `single_context` | `shell_nav_done` -> **GAP** |

## `control_room_ui_rebuild`
`workflows/repository/control_room_ui_rebuild.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `rebuilt` | measurement | _(none)_ | `foundation`, `fleet`, `boards_detail` | no requirements -- nothing to migrate |
| `invariants_held` | measurement | `foundation` | `no_new_endpoints`, `flag_only_rail`, `mobile_first` | `foundation` -> **GAP** |

## `control_room_ui_redesign`
`workflows/repository/control_room_ui_redesign.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `research_rich` | measurement | _(none)_ | `research_reference` | no requirements -- nothing to migrate |
| `design_grounded` | measurement | `research_reference` | `redesign_proposal` | `research_reference` -> **GAP** |

## `control_room_workflow_phase`
`workflows/repository/control_room_workflow_phase.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `phase_visibility` | measurement | _(none)_ | `workflow_phase` | no requirements -- nothing to migrate |

## `finding_economics_closure`
`workflows/repository/finding_economics_closure.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `finding_economics_closed` | measurement | _(none)_ | `economics_coverage`, `attestation_exact`, `parquet_verified`, `versions_bumped`, `hunt_clean` | no requirements -- nothing to migrate |

## `investing_domain_audit`
`workflows/repository/investing_domain_audit.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `investing_domain_audited` | measurement | _(none)_ | `observable_inventoried`, `policies_inventoried`, `gaps_mapped`, `audit_adversarial_clean` | no requirements -- nothing to migrate |

## `kb_event_typing`
`workflows/repository/kb_event_typing.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `envelope_typed` | measurement | _(none)_ | `event_scope_type`, `scope_fail_closed`, `extractor_safe` | no requirements -- nothing to migrate |

## `kb_lineage_reconcile`
`workflows/repository/kb_lineage_reconcile.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `lineage_reconciled` | measurement | _(none)_ | `standin_retired`, `reconcile_wired` | no requirements -- nothing to migrate |

## `kb_producer_factory`
`workflows/repository/kb_producer_factory.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `factory_landed` | measurement | _(none)_ | `record_factory` | no requirements -- nothing to migrate |
| `types_centralized` | measurement | `record_factory` | `source_type_registry` | `record_factory` -> **GAP** |

## `kb_record_fidelity`
`workflows/repository/kb_record_fidelity.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `bugs_fixed` | measurement | _(none)_ | `observed_at_roundtrip`, `subject_fields`, `perturbation_none` | no requirements -- nothing to migrate |

## `kb_write_path`
`workflows/repository/kb_write_path.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `write_path_deduped` | measurement | _(none)_ | `register_records`, `paths_module`, `story_adapter` | no requirements -- nothing to migrate |

## `measurement_bug_fixes`
`workflows/repository/measurement_bug_fixes.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `bugs_fixed` | measurement | _(none)_ | `model_label`, `contradiction_domain`, `recovery_dedup` | no requirements -- nothing to migrate |

## `measurement_contribution_closure`
`workflows/repository/measurement_contribution_closure.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `contributions_closed` | measurement | _(none)_ | `join_explicit`, `coverage_universal`, `contracts_derived`, `temporal_terminal`, `hunt_clean` | no requirements -- nothing to migrate |

## `perturbation_operators_fix`
`workflows/repository/perturbation_operators_fix.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `operator_determinism` | measurement | _(none)_ | `deterministic` | no requirements -- nothing to migrate |
| `strength_zero_noop` | measurement | _(none)_ | `noop_at_zero` | no requirements -- nothing to migrate |
| `cross_model_prompt_consistency` | measurement | _(none)_ | `same_prompt` | no requirements -- nothing to migrate |

## `public_truth_closure`
`workflows/repository/public_truth_closure.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `public_truth_closed` | measurement | _(none)_ | `narrative_canonical`, `null_not_zero`, `scopes_explicit`, `waivers_tombstoned`, `contract_global` | no requirements -- nothing to migrate |

## `rag_knowledge_base_build`
`workflows/repository/rag_knowledge_base_build.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `exact_identifier_match` | measurement | _(none)_ | `exact_identifier_match` | no requirements -- nothing to migrate |
| `classify_authority` | measurement | _(none)_ | `authority_class` | no requirements -- nothing to migrate |
| `knowledge_freshness` | measurement | _(none)_ | `freshness_lag` | no requirements -- nothing to migrate |
| `fuse_candidate_ranks` | measurement | _(none)_ | `fused_score` | no requirements -- nothing to migrate |
| `score_graph_expansion` | measurement | _(none)_ | `graph_contribution` | no requirements -- nothing to migrate |
| `validate_prompt_plan` | measurement | _(none)_ | `plan_validity` | no requirements -- nothing to migrate |
| `constraint_coverage` | measurement | _(none)_ | `constraint_recall` | no requirements -- nothing to migrate |
| `citation_validity` | measurement | _(none)_ | `citation_validity` | no requirements -- nothing to migrate |
| `evaluate_retrieval` | measurement | _(none)_ | `recall_at_k` | no requirements -- nothing to migrate |
| `rag_economics` | measurement | _(none)_ | `rag_cost` | no requirements -- nothing to migrate |

## `rag_knowledge_base_reconcile`
`workflows/repository/rag_knowledge_base_reconcile.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|

## `rag_knowledge_base_wire`
`workflows/repository/rag_knowledge_base_wire.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|

## `rag_knowledge_produce`
`workflows/repository/rag_knowledge_produce.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|

## `rag_knowledge_produce_fix`
`workflows/repository/rag_knowledge_produce_fix.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|

## `rag_knowledge_sources`
`workflows/repository/rag_knowledge_sources.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|

## `rag_scope_emit`
`workflows/repository/rag_scope_emit.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|

## `rag_seam_split`
`workflows/repository/rag_seam_split.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `seam_split` | measurement | _(none)_ | `augment_module`, `docs_refreshed` | no requirements -- nothing to migrate |

## `refactor_master_plan`
`workflows/repository/refactor_master_plan.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `master_plan_delivered` | measurement | _(none)_ | `audit_complete`, `research_grounded`, `plan_sequenced`, `specs_gate_passing` | no requirements -- nothing to migrate |

## `refactor_repair_release`
`workflows/repository/refactor_repair_release.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `repair_released` | measurement | _(none)_ | `ops_repaired`, `context_repaired`, `identity_explicit`, `lifecycle_useful`, `hardened` | no requirements -- nothing to migrate |

## `remediation_data_integrity`
`workflows/repository/remediation_data_integrity.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `instrument_confidence` | measurement | _(none)_ | `confidence` | no requirements -- nothing to migrate |
| `instrument_grit_inputs` | measurement | _(none)_ | `perturbation_strength`, `test_executed_success` | no requirements -- nothing to migrate |
| `instrument_token_split` | measurement | _(none)_ | `answer`, `explanation` | no requirements -- nothing to migrate |
| `grit` | measurement | `perturbation_strength`, `test_executed_success` | `grit` | `perturbation_strength` -> **GAP**<br>`test_executed_success` -> **GAP** |
| `explanation_tax` | measurement | `answer`, `explanation`, `cost_inference` | `explanation_tax` | `answer` -> **GAP**<br>`explanation` -> **GAP**<br>`cost_inference` -> **GAP** |
| `model_cascade` | control | `confidence`, `first_pass` | `escalation_decision` | `confidence` -> **GAP**<br>`first_pass` -> **GAP** |
| `dynamics` | control | `confidence`, `first_pass`, `deadline_slack` | `admit_or_halt` | `confidence` -> **GAP**<br>`first_pass` -> **GAP**<br>`deadline_slack` -> **GAP** |

## `routing_kb_dispatch`
`workflows/repository/routing_kb_dispatch.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|

## `routing_kb_wiring`
`workflows/repository/routing_kb_wiring.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|

## `semantic_integrity_release`
`workflows/repository/semantic_integrity_release.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `semantic_integrity_released` | measurement | _(none)_ | `labs_quarantined`, `lab_contract_enforced`, `outputs_canonical`, `context_canonical` | no requirements -- nothing to migrate |

## `spec_lifecycle`
`workflows/repository/spec_lifecycle.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `spec_index` | measurement | _(none)_ | `spec_index` | no requirements -- nothing to migrate |
| `spec_lifecycle` | measurement | `spec_index` | `spec_lifecycle_state` | `spec_index` -> **GAP** |

## `task_vocabulary_unify`
`workflows/repository/task_vocabulary_unify.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `vocabulary_unified` | measurement | _(none)_ | `task_vocabulary`, `reverse_import_removed` | no requirements -- nothing to migrate |

## `website_data_pipeline`
`workflows/repository/website_data_pipeline.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|

## `website_registry_repoint`
`workflows/repository/website_registry_repoint.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `site_registry_repointed` | measurement | _(none)_ | `corpus_gated`, `summary_retired`, `counts_canonical` | no requirements -- nothing to migrate |

## `website_repoint`
`workflows/repository/website_repoint.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `site_repointed` | measurement | _(none)_ | `ui_seam_fixed`, `labels_resolved`, `pricing_fixed`, `counts_canonical` | no requirements -- nothing to migrate |

## `website_rewrite`
`workflows/repository/website_rewrite.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `site_consistency` | measurement | _(none)_ | `provenance_clean` | no requirements -- nothing to migrate |
| `publish_ready` | control | `provenance_clean` | `deployable` | `provenance_clean` -> **GAP** |

## `deep_architecture_review`
`workflows/research/deep_architecture_review.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `map_complete` | measurement | _(none)_ | `architecture_mapped` | no requirements -- nothing to migrate |
| `seed_repo_gap` | measurement | _(none)_ | `generalization_gap` | no requirements -- nothing to migrate |
| `roadmap_actionable` | measurement | `architecture_mapped`, `generalization_gap` | `refactor_roadmap` | `architecture_mapped` -> **GAP**<br>`generalization_gap` -> **GAP** |

## `rag_knowledge_base`
`workflows/research/rag_knowledge_base.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|

## `repo_review_fable`
`workflows/research/repo_review_fable.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `areas_covered` | measurement | _(none)_ | `five_areas_delivered` | no requirements -- nothing to migrate |
| `findings_grounded` | measurement | `five_areas_delivered` | `file_line_evidence` | `five_areas_delivered` -> **GAP** |

## `routing_kb_more_itertools`
`workflows/research/routing_kb_more_itertools.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `outcome_measure` | measurement | `test_executed_success`, `accepted`, `evaluator_independent` | `accepted_outcome` | `test_executed_success` -> **GAP**<br>`accepted` -> **GAP**<br>`evaluator_independent` -> **GAP** |
| `cost_measure` | measurement | `cost_inference`, `cost_orchestration`, `actual_cost` | `cost_per_accepted_outcome` | `cost_inference` -> **GAP**<br>`cost_orchestration` -> **GAP**<br>`actual_cost` -> **GAP** |
| `flail_measure` | measurement | `tool_calls`, `tokens_reasoning`, `tokens_out` | `flail` | `tool_calls` -> **GAP**<br>`tokens_reasoning` -> **GAP**<br>`tokens_out` -> **GAP** |

## `self_recommending_experiment`
`workflows/research/self_recommending_experiment.yaml` -- workflow.kind=`agent_task`, artifact_kind=`workflow`

| rule | plane | legacy requires | legacy produces | requirement -> predicate/GAP |
|---|---|---|---|---|
| `measure_regret` | measurement | `cost_inference`, `value`, `test_executed_success` | `regret` | `cost_inference` -> **GAP**<br>`value` -> **GAP**<br>`test_executed_success` -> **GAP** |
| `recommend_experiment` | control | `regret` | `recommendation` | `regret` -> **GAP** |

## Per-requirement detail

Every distinct legacy requirement name that appears anywhere in the in-scope corpus, with the full reasoning behind its verdict.

### `accepted` -> GAP
No predicate. Distinct from phase_test_verified (independent test verification) -- `accepted` is an editorial/evaluator acceptance flag. Missing producer: a story/experiment-ledger reducer emitting an `attempt_accepted` predicate.

### `actual_cost` -> GAP
Nearest predicates attempt_cost_usd / job_accumulated_cost_usd, both producible only from `workflow_run` artifacts (agent_task phases); this spec's cells write to the story/experiment ledger instead. Missing producer: a ledger-domain cost reducer.

### `answer` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `architecture_mapped` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `attempt_number` -> GAP
No predicate; attempt/session lineage (retry count) is not modeled. Missing producer: a session-lineage reducer over parent_attempt_id/attempt_number/escalation_from/to.

### `budget` -> MIGRATED
max_spend_usd. policy_facts/v1 reads this spec's own `stop.budget_usd` (declared, workload-scoped, [P]) -- producible for every spec regardless of workflow.kind. requires_facts added to routing_regret_under_degradation/budget_ceiling: {fact: max_spend_usd, scope: parent, min_authority: POLICY, on_missing: halt, on_conflict: halt}.

### `cache_hit` -> GAP
Nearest predicate attempt_cache_hit_rate, but it is a workflow-phase RATE aggregate from `workflow_run.cache_hit_rate`, not the story ledger's per-attempt boolean cache_hit, and is producible only for agent_task workflows. Missing producer: a ledger-domain cache reducer.

### `component_gap_map` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `condition` -> GAP
No predicate; a factor level (perturbation condition), not world state -- out of FACT_PREDICATES scope by design, not an instrumentation gap.

### `confidence` -> GAP
Nearest predicate attempt_confidence, but (a) attempt_facts/v1 derives it only from `workflow_run` artifacts, never the story/experiment ledger this spec's cells write to, and (b) attempt_confidence is intrinsically ADVISORY (attempt_facts.py's epistemic map) -- R5 forbids ANY control rule from requiring an ADVISORY fact, so even if the producer-domain gap were closed this predicate could never legally satisfy a control rule. Missing producer: a MEASURED confidence predicate has no design today.

### `consumer_operation_handled` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `context_plane_design` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `control_snapshots` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `cost` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `cost_inference` -> GAP
No predicate splits inference/orchestration cost; nearest attempt_cost_usd is a single aggregate from `workflow_run`, producible only for agent_task phases. Missing producer: a ledger-domain cost-component reducer.

### `cost_orchestration` -> GAP
Same gap as cost_inference -- no cost-component split predicate exists.

### `deadline_slack` -> GAP
No predicate anywhere. control/facts.py's own PredicateSpec docstring names `deadline_slack` explicitly as the worked example of a LEDGER_FIELDS entry declared with ZERO producer -- "impossible to declare here until something actually produces it." Missing producer: none exists in the codebase today.

### `deltas_addressed` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `escalation_from` -> GAP
No predicate; session lineage not modeled. Missing producer: a session-lineage reducer (same as attempt_number).

### `escalation_to` -> GAP
No predicate; session lineage not modeled. Missing producer: a session-lineage reducer (same as attempt_number).

### `escape` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `evaluator_independent` -> GAP
No predicate; evaluator-identity is not modeled in the fact plane. Missing producer: a ledger-domain evaluator-identity reducer.

### `explanation` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `fact_contracts` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `fact_schema` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `first_pass` -> GAP
No predicate. phase_test_verified is a different concept (independently-verified pass, not first-attempt success) and is workflow_run-scoped only. Missing producer: a first-pass-quality reducer over the story/experiment ledger.

### `five_areas_delivered` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `flail` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `forecast_cost` -> GAP
No predicate. Nearest concept is projected_budget_overrun (a workflow-level derived overrun forecast from job_accumulated_cost_usd) -- a different aggregate, and workflow_run-scoped only. Missing producer: a ledger-domain forecast reducer.

### `foundation` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `generalization_gap` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `implementation_plan` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `migration_plan` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `parent_attempt_id` -> GAP
No predicate; session lineage not modeled. Missing producer: a session-lineage reducer (same as attempt_number).

### `perturbation_strength` -> GAP
No predicate; a research/experimental factor axis (the strength dial), not workflow meta-state -- out of FACT_PREDICATES scope by design; would need a new research-domain predicate + reducer if this axis were ever promoted to a control input.

### `plan_steps_done` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `posthoc_auto` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `posthoc_ready` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `provenance_clean` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `provider_imbalance` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `record_factory` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `regret` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `research_reference` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `reuse_value` -> GAP
Same gap as value -- no value-accounting predicate exists.

### `rework_cost` -> GAP
Same gap as value -- no value-accounting predicate exists.

### `shadow_decisions` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `shell_nav_done` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `spec_index` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `store_map` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `story_side_fresh` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `test_executed_success` -> GAP
Nearest predicate phase_test_verified -- SAME underlying concept (independent test-runner verification, bool) -- but attempt_facts/v1 derives it only from `workflow_run` artifacts. This spec's cells verify via test_runner + ledger_ingestion.py, which no reducer bridges into the fact plane. Missing producer: a story/experiment-ledger analogue of attempt_facts/v1.

### `tokens_answer` -> GAP
No predicate splits answer/explanation/reasoning; only aggregate tokens_in/out exist, and only from `workflow_run`. Missing producer: an answer/explanation/reasoning-split reducer.

### `tokens_explanation` -> GAP
Same gap as tokens_answer -- no answer/explanation/reasoning split predicate exists.

### `tokens_in` -> GAP
Nearest attempt_tokens_in, producible only from `workflow_run` (agent_task phases). Missing producer: a ledger-domain token reducer.

### `tokens_out` -> GAP
Nearest attempt_tokens_out, same gap as tokens_in.

### `tokens_reasoning` -> GAP
Same gap as tokens_answer -- no answer/explanation/reasoning split predicate exists.

### `tool_calls` -> GAP
No predicate; tool-call counts are not modeled in the fact plane. Missing producer: a tool-usage reducer.

### `value` -> GAP
No predicate; economic-outcome signals (value/rework_cost/reuse_value) are not modeled. Missing producer: a value-accounting reducer.

### `verified_outcome` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

### `workflow_facts` -> GAP
GAP (out of scope by design). Bespoke per-workflow deliverable marker -- this rule's own or a prior same-spec rule's `produces` -- not a reusable canonical fact about the world, so not a candidate for FACT_PREDICATES. The legacy requires/produces gate (validate_rules) already validates this chain correctly; no instrumentation action needed.

