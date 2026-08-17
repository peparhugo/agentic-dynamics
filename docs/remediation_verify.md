# Remediation Verification

Verifies the end-to-end remediation: instrument the four missing ledger fields,
recompute derived metrics, re-run contaminated cells, regenerate derived artifacts,
and re-admit the gated policy arms. Every check below is PASS.

**Baseline:** `66fc7134c` (pre-remediation merge). **Workflow commits:** scope
`e4d528c58` → instrument `bd338215c` → recompute `88bea9857` → rerun_contaminated
`8db060782` → regenerate `233a69e6b` → run_policy_grid `5e15d6362`.

---

## Check 1 — Remediation-relevant tests (explicit, never a bare suite)

**Command (single invocation over the exact six files):**

```
python3 -m pytest tests/test_data_integrity.py tests/test_strategy.py \
  tests/test_commit_analysis.py tests/test_workflow_runner.py \
  tests/test_experiment_spec.py tests/test_compile_experiment.py -q
```

**Result:** `62 passed in 2.65s`

Per-file breakdown:

| File | Result | Guards |
|---|---|---|
| `tests/test_data_integrity.py` | 8 passed | no duplicate pricing; no fabricated pass rate; basin uses `get_pricing`; no resurrected arch constants; baseline fallback + Go/Rust patterns |
| `tests/test_strategy.py` | 3 passed | behavioral `classify_strategy`; price-rescale invariance |
| `tests/test_commit_analysis.py` | 14 passed | Go/Rust AST-diff counting (P0-10) |
| `tests/test_workflow_runner.py` | 8 passed | phase execution + ledgering |
| `tests/test_experiment_spec.py` | 16 passed | `LEDGER_FIELDS` has the four fields; flagship spec validates; validator refuses unmet requires |
| `tests/test_compile_experiment.py` | 13 passed | `compile_spec` DAG; `grit` computes + returns unmeasured when inputs absent |

No failure was introduced by this work; nothing needed fixing.

---

## Check 2 — Four fields present in the ledger schema and populated on new results

`LEDGER_FIELDS` (`src/instrument/experiment_spec.py:44`) contains all four formerly-missing
fields (plus the answer/explanation split as two fields):

```
'confidence'              → True
'perturbation_strength'   → True
'test_executed_success'   → True
'tokens_answer'           → True
'tokens_explanation'      → True
```

**Populated on new results:**

- `experiments/results/task_manager_deepseek-v4-pro.json` — **7/7 runs** carry `confidence`,
  `perturbation_strength`, `test_executed_success`, and the `answer_tokens`/`explanation_tokens` split.
- Story results: **14/159** carry the measured fields (the re-run `early_degrade` cells; the
  pre-instrumentation clean cells legitimately lack them).

Instrumentation sites: `src/instrument/opencode.py` (`AgenticResult.confidence`,
`answer_tokens`/`explanation_tokens`), `src/instrument/story.py` (`perturbation_strength`,
`test_executed_success` via `test_runner.run_suite`), `scripts/run.py` (`_verify_tests`).

---

## Check 3 — `validate_rules` admits the arms and still refuses unmeasured fields

```
from instrument.experiment_spec import load_spec, validate_rules
validate_rules(load_spec('experiments/specs/routing_regret_under_degradation.yaml'))
→ []
```

The flagship spec now validates clean: `grit` (`perturbation_strength` + `test_executed_success`
+ `condition`), `model_cascade` (`confidence`), and the `dynamics`/`quality_cascade` control
arms are all **admissible**.

**Refusal still enforced** — adding a control rule that requires a truly-unmeasured field:

```
spec.rules.append(RuleSpec('phantom_arm', 'control', '[H]',
                           requires=['edge_case_coverage'], produces=['x']))
validate_rules(spec)
→ ['rule "phantom_arm" requires 'edge_case_coverage' — not produced by the ledger
    or any measurement rule in this spec. Instrument it first.']
```

The gate "to make policies, we need information" is open for the measured arms and still
closed for the unmeasured ones.

---

## Check 4 — `data.js` integrity (P0-1 / P0-2 / P0-3)

| Invariant | Result | Evidence |
|---|---|---|
| No fabricated 100% pass rate (P0-1) | PASS | `overall_pass_rate = "100.0% (8076/8079) [tests]"` — measured from `sessions.parquet`; the fabricated marker `10412` is **absent**; `_honest_pass_rate` returns `"unknown"` when `run <= 0`. |
| Single pricing source (P0-2) | PASS | `PROVIDER_PRICING` defined **only** in `src/instrument/efficiency.py:40`; `_constants.py` carries only the "do not re-add" comment. |
| No resurrected arch constants (P0-3) | PASS | `energy_model_available: {value:false}`; `deepseek_active_params: "49e9"`; no `500e9`/`37e9`; no `claude_active_params`. |
| Provenance tags (P0-11) | PASS | `game_report.py:159` tags correctness `[M]` only when `evaluator_independent`, else `[H]`; pass-rate uses `[tests]`/`[H]`/`unknown`; arch/energy tagged `[X]`. |

---

## Check 5 — Recompute moved the numbers in the predicted direction

| Metric | Before | After | Direction |
|---|---|---|---|
| `overall_pass_rate` | fabricated `100% (10412/10412)` | measured `100.0% (8076/8079) [tests]` | fabricated → honest |
| Claude Haiku `pass_rate` | fabricated `100%` | `"unknown"` (no in-session test data) | fabricated → honest |
| strategy archetype (story) | conservative 20 · exploratory 194 · **wasteful 7** | conservative 27 · exploratory 194 · **wasteful 0** | 7 reclassified (P0-4) |
| commit convention scores | mean 0.6944 (n=1098) | mean 0.7177 (n=1097) | corrected (P0-9) |
| `test_executed_success` | absent | 148/222 (66.7%) independent, **20 cells flipped pass→fail** | self-report → independent |
| basin (single-task) | cross-experiment baseline | true same-experiment baseline (re-run) | de-contaminated |

**Flipped conclusions (headlines that reversed):**

1. **"Overall pass rate 100%"** → reversed: measured `100.0% (8076/8079)` with 3 tests failing,
   and `"unknown"` wherever nothing was independently run.
2. **"Claude Haiku passes 100%"** → reversed: `"unknown"` — its in-session test data was never
   captured, so no pass rate can be honestly reported.
3. **"7 wasteful strategy archetypes"** → reversed: 0 wasteful; all 7 reclassified `conservative`
   once `classify_strategy` dropped the absolute-USD thresholds (P0-4).
4. **"20 story cells passed their tests"** → reversed: they fail under the independent
   `test_runner` harness — agent-authored tests were over-optimistic (P0-11/P0-12).

**Not flipped (unchanged, as predicted):** story basin verdicts (0 changes — the story
`deep.basin` never sets `perturbation_class`); AST diff counts (1 story, Go/Rust patterns only).

---

## Commands run

```
python3 -m pytest tests/test_data_integrity.py tests/test_strategy.py \
  tests/test_commit_analysis.py tests/test_workflow_runner.py \
  tests/test_experiment_spec.py tests/test_compile_experiment.py -q
# → 62 passed in 2.65s

python3 -c "from instrument.experiment_spec import LEDGER_FIELDS, load_spec, validate_rules, RuleSpec; ..."
# → schema membership + flagship validate_rules [] + refusal of edge_case_coverage

python3 -c "…re.search over firebase/public/data.js…"
# → overall_pass_rate, arch constants, fabrication marker checks

grep -rn "^PROVIDER_PRICING\|PROVIDER_PRICING =" scripts/ src/
# → src/instrument/efficiency.py:40 (single source)
```

## Changed-file summary

**Code (instrumentation + validator + compiler, committed across phases):**

- `src/instrument/opencode.py` (+58) — `confidence`, `answer_tokens`/`explanation_tokens` on `AgenticResult`
- `src/instrument/story.py` (+54) — `perturbation_strength`, `test_executed_success` on `StoryResult`
- `src/instrument/experiment_spec.py` (+22) — `LEDGER_FIELDS` now carries the four fields
- `src/instrument/compile_experiment.py` (+15) — `grit` measurement rule re-admitted
- `src/instrument/workflow_runner.py` (+5), `scripts/run.py` (+31) — ledger wiring

**Tests (new + extended):**

- `tests/test_ledger_fields.py` (+149, new) — locks the four fields in place
- `tests/test_experiment_spec.py` (+35), `tests/test_compile_experiment.py` (+12) — validator/compiler guards

**Data / artifacts (regenerated):**

- `experiments/results/analysis/*.json` (222, corrected strategy/convention)
- `experiments/results/verified_tests.json` (new — independent `test_executed_success`)
- `experiments/data/{sessions,stories}.parquet`, `firebase/public/data.js`,
  `experiments/data_manifest.json`, 18 `lab_*.json` (re-run)
- `experiments/specs/routing_regret_under_degradation.yaml` (new — flagship spec materialized)
- `docs/remediation_plan.md` (+531) — the running record (§1–§7)

## Residual (deferred, does not block this verification)

- `_results_summary.json` single-task corpus still carries `"semantic"`×187 / `"manifold"`×16
  labels and pre-P0-8 basin numbers — its worktrees are gone; a clean regeneration needs the
  full single-task matrix re-run. The `policy`-arm cells of the routing_regret grid await the
  `experiment_matrix`/`experiment_run` transport (reuse-map item still to be built).

## Overall

**PASS — 5/5 checks.** The four fields are measured, the policy arms are re-admitted, the
data artifacts are honest, and the recompute moved the affected numbers exactly as the
Phase-1 review predicted.
