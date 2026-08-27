---
status: accepted
---

# cap_adaptive_2c — pre-registration (p0): the boundary campaign (when should the gate decline to adapt?)

**Status: accepted · PRE-REGISTERED — committed BEFORE any cell runs.**
**Campaign:** `cap_adaptive_2c` (`workflows/repository/cap_adaptive_2c.yaml`, SHA256
`15e15019d5435233079d5cd17b933de449fd5212f227b3229b433d16ee419940`; `cap_adaptive_2c@0.1`).
**Design authority (reused):** `docs/designs/current/cap_2b_design.md` §2 (the pre-registration
pattern) SHA256 `9bf3072b74913093d8358dbc14fd909047c566c83f97cf5fd566ebe985605263`.
**Predecessor verdicts (all measured):** `cap_2b.md` (the 2b verdict — NON-INFERIOR, cpvo ratio
0.7857, and the limitation this campaign attacks) SHA256
`3153f1a8dfe75c2dc121dd7f10fb40faf376beaf66d2306492d6cb91a8d66e03`; the 2b pre-registration
SHA256 `21fc3b41bbe462d0bd53ba5463ef30de77922f8ce12c9839a6f603768f92a615`; the 2b score JSON
`experiments/results/cap_2b/cap_2b_score_20260826T160018Z.json` SHA256
`5f24f5072f1bb0ab17769b8db3734680b83981c2506df3b57fffa529c42ed3d9`; the measured-E_x campaign
score `experiments/results/cap_escalation_measurement/cap_escalation_measurement_score_20260826T125726Z.json`
SHA256 `6d3c7a7c48ba718b0ccd7d9e1f3a9898336ed89c83ba791274dca7330b890329`; the measurement-design
pins `docs/designs/current/cap_2a_rerun2_measurement_design.md` (the reachable BLOCKER/CRITICAL
surface, the S1244/S3776 pins, the severity filter) SHA256
`8b9dcf7ad995c5bf7432afc08ad69815c6b8a12466bbfc3afa90185c8d9e5993`.
**Stimulus family (extended):** `cap_2a_cell_clean@0.1` SHA256
`65730a228e238513747fdd658679d4b89389140f92f2a26021170cab338cbba0`, `cap_2a_cell_critical@0.1`
SHA256 `6ecb2bd93e8718c8c42382f648e859672c649de761e46ba74c2d7a460721e4d7`,
`cap_2a_cell_style@0.1` SHA256 `eaf7e806ce8f3b7f49f3f804904df513887e58387a73e1dc2ffe1337fd994ab4`.
**Treatment (code-unchanged):** `src/agentic_dynamics/control/verify_proposal.py` SHA256
`5cf7ea71af9d14345062d298211bc3b01e761c31b21386efdb5d572ecaa32385` and the risk reducer
`src/agentic_dynamics/control/reducers/code_change_facts.py` SHA256
`eb3c76bb0d7b60302d081cf6556a528a91375be792d30f0a0e9e882a7ef6ddf3`.
**Cell model:** `deepseek/deepseek-v4-pro` (the stimulus set's model — unchanged from 2b).

> **The registration rule:** nothing in §0–§7 may be redefined after this commit. A deviation from
> this pre-registered plan — a redefined margin, a reseeded assignment, a dropped cell, a
> post-hoc re-labelled class — is a **FAILED finding** in p5, not a limitation. The assignment
> table (§4) is the canonical record; the seed is the reproducibility key. Every number below is
> derived from a cited artifact (hashes in the header) or from the arithmetic of the pinned
> machinery (§0); the class constructions are buildable from this document alone.

---

## 0. The pinned machinery facts the classes are grounded in (current_state rule 4)

The stimulus classes are built **against the verifier's real machinery**, pinned here from the
cited treatment files. The pre-registration invents no thresholds; every constant below is read
from the cited source.

**The proposal action tree** (`verify_proposal.py` `build_verify_proposal`, lines 169–255),
in priority order:

1. **`rework`** (depth 3) ⟺ `new_sonar_critical_count > 0` **or** `new_lsp_error_count > 0`
   ("has_critical") — a measured BLOCKER/CRITICAL issue or error-severity diagnostic introduced by
   the change.
2. **`continue`** (depth 0, empty scope) ⟺ `changed_symbol_count == 0`.
3. **`verify`** (depth = `_risk_depth(risk)`: 1 if risk < 0.15, 2 if risk < 0.3, else 3) ⟺
   `code_change_risk >= VERIFY_RISK_THRESHOLD` with **`VERIFY_RISK_THRESHOLD = 0.2`**
   (`verify_proposal.py:61`).
4. **`continue`** (depth 0) otherwise (low-risk change).

The seam **refuses** (`ValueError`, the "refuse to run" contract) when any required fact
(`changed_symbol_count`, `ast_parse_coverage`, `code_change_risk`) is missing or unparseable —
**never** a hand-authored proposal past a failing seam.

**The `code_change_risk` formula** (`code_change_facts.py` module docstring, lines 44–52, and
`RISK_WEIGHTS`, lines 117–122; weights `[P]` operator policy, UNCHANGED from v1):

```
risk = [ 0.35·min(1, new_sonar_critical_count/10)
       + 0.25·min(1, new_lsp_error_count/10)
       + 0.20·(1 − changed_symbols_with_tests_ratio)
       + 0.20·min(1, impacted_symbol_count/10) ] / Σ(weights of the MEASURABLE terms)
```

Terms whose analyzer did not run, whose ratio is deferred, or whose count is absent are **omitted**
and the remaining weights **renormalized** to sum 1; `risk` is `None` (fact omitted) when no term
is measurable. `new_sonar_critical_count` is the **severity-filtered, change-introduced** count
(`workflow_runner.py:469–519`): issues fetched with the server-side `severities=BLOCKER,CRITICAL`
filter only — **a MAJOR finding (e.g. `python:S1244`) NEVER counts**. `changed_symbols_with_tests_ratio`
is `tested_changed_symbols / changed_symbols` under the TESTED_BY rule (`language.py:780–808`:
`test_<m>.py → <m>.py`); **a symbol in a module with a matching test file is tested even if no
test references it**; the fact is **DEFERRED (omitted)** when the rule links no changed symbol —
"never 0".

**The measured reference costs** (all MEASURED, from the cited score JSONs):

| quantity | value | artifact field |
|---|---|---|
| base downstream defect cost | **$0.004021** | escalation score JSON `base_downstream_defect_cost_usd` (0.112588 / 28, re-derived) |
| E_x (openai/gpt-5.6-sol escalation fix, n=1) | **11.4671** | escalation score JSON `per_model[0].E_x` (0.102619 / 0.008949) |
| E_x (anthropic/claude-sonnet-5 escalation fix, n=1) | **12.5134** | escalation score JSON `per_model[1].E_x` |
| wrong-continue loss @ E_x=11.4671 | **$0.046109** | escalation score JSON `loss_table` |
| wrong-continue loss @ E_x=28 (sourced) | **$0.112588** | escalation score JSON `loss_table` |
| 2b cpvo ratio | **0.7857** [0.6842, 0.9105] | 2b score JSON `decision_rule.cpvo_ratio` / `.cpvo_ratio_ci_95` |
| 2b success gap (static − adaptive) | **−0.3333** | 2b score JSON `decision_rule.success_gap_static_minus_adaptive` |
| 2b per-arm cpvo | static **$0.013344** (n=9), adaptive **$0.010485** (n=9) | 2b score JSON `per_arm` |
| 2b per-cell cost range | **$0.0057–$0.0169** | 2b score JSON `per_cell[].cost_usd` |
| 2b defect-bearing conversion q | **1.0 (3/3 applied reworks fixed)** | 2b score JSON `defect_bearing` |

**The 2b limitation this campaign attacks** (the campaign question, `cap_adaptive_2c.yaml`):
2b established NON-INFERIORITY where proposals were essentially correct but "does not establish
that adaptive policies are generally superior when proposals can be wrong, ambiguous, competing,
absent, or from unseen defect families."

---

## 1. Primary outcome metric + secondary + the HARM model

**Primary — cost-per-accepted-outcome (cpvo) per arm**, the site KPI, the 2b definition verbatim:

```
cpvo_arm = (Σ measured cell cost over the arm) / (Σ accepted outcomes over the arm)
```

- **Total cost** = Σ `cost_usd` per cell (the measured, ledgered run cost).
- **Accepted outcome** (per cell) = `test_executed_success == true` (the independent
  `runtime.test_runner` verdict on the final commit) **AND**
  `defect_present_on_final_commit == false` (the post-hoc evaluator's defect determination on the
  same immutable commit). **For competing cells, accepted additionally requires BOTH defects
  absent** (§3, class 4). Both must hold; a cell failing either is **not accepted**.

**Secondary — verified-success rate per arm**: `accepted outcomes in the arm / cells in the arm`.

Denominator discipline (2b practice, carried forward): a cell stopped by the budget/SLA guard or
flagged (graph-down/analyzer-down) is reported **in its denominator** with its status printed,
never silently dropped; a cell scored under a different arm than its assignment is **invalid**
(p3 guard). The absent-defective variant is a **designed** analyzer/graph-down cell (§3, class 5b) —
flagged as designed, never dropped.

**HARM (per-cell, the boundary campaign's core addition over 2b).** Two components, both
pre-registered here:

1. **wrong-apply (the false-positive action — labelled "wrong-rework" in the campaign spec):
   passes wasted [MEASURED].** The cost of one extra pass in the adaptive arm, measured as the
   adaptive cell's cost minus its matched static cell's cost (same class, same repetition block).
   In this campaign the constructible false-positive is the **`verify` pass** — a false-positive
   **`rework` is NOT constructible** under the severity filter (only change-introduced
   BLOCKER/CRITICAL issues trigger `rework`; on a defect-free change `new_sonar_critical_count`
   and `new_lsp_error_count` are 0 by construction). That non-constructibility is a **recorded
   filter strength**, not a gap: the incorrect class (§3, class 2) measures the constructible
   false-positive's cost, and the filter-strength statement means the harm of a false-positive
   **rework** is bounded *above* by the measured verify-pass cost in this campaign.
2. **wrong-continue: E_x-scaled [E_x 11.47 cited, n=1 per model, sensitivity 11.47/28].** For each
   **escaped defect** (a defect present on the final commit whose proposal did not apply a fix):
   `harm = E_x × base_downstream_defect_cost_usd = E_x × $0.004021`. At the **measured** E_x =
   11.4671: **$0.046109** per escaped defect; at the **sourced** E_x = 28: **$0.112588** per
   escaped defect. Both multipliers reported (sensitivity); the n=1-per-model limitation is stated
   (two measured E_x values, one cell each). A wrong-continue arises in: correct-static (rework
   ignored), competing (per unfixed defect), absent-defective (refusal → escape), unseen-family
   (continue → escape), and competing partial_rework's unfixed defect.

The HARM model is **measured, not inferred** (spec hard-rule 5): wrong-apply cost is the measured
pass delta; wrong-continue is E_x × the measured base defect cost, with the multiplier's
sensitivity reported.

---

## 2. Non-inferiority margin + decision rule + the ABSTENTION rule

**Margin — the 2b rule reused verbatim** (`cap_2b_preregistration.md` §2), applied to the **full
heterogeneous grid** (all six classes pooled):

```
NI  ⟺  cpvo_adaptive ≤ 1.10 × cpvo_static
   AND  verified_success_adaptive ≥ verified_success_static − 5 percentage points
```

(equivalently cpvo ratio `r = cpvo_adaptive / cpvo_static ≤ 1.10` and success gap
`succ_static − succ_adaptive ≤ 0.05`.) Justification is the measured 2b effect prior, restated
(cited in §0): 2b measured ratio 0.7857 (0.31 below the 1.10 boundary, ratio CI upper bound 0.9105
still below it) and success gap −0.3333 (38.3pts inside the 5pt boundary), at n=9/arm. The margin
is unregistered nowhere else; this campaign registers it for the heterogeneous case.

**The decision is made on the full-grid point estimates with n + CI reported** (bootstrap for the
ratio, Wilson for the rate — §5). **Per-class, the rule is REPORTED, never decided:** at n=2 per
arm per class the CI is descriptive; the per-class table identifies *which* classes push the
pooled ratio toward or past the margin.

**The ABSTENTION rule (new, descriptive at the campaign's n).** The verdict reports whether
**confidence-gated abstention** — decline to apply when the proposal's measured confidence is
below a threshold θ — improves cpvo at any θ in the observed confidence distribution:

```
abstention improves value  ⟺  ∃ θ ∈ (0,1) : cpvo_gated(θ) < cpvo_gated(0)
cpvo_gated(θ) = (Σ cost + Σ harm over all 24 cells under the gated regime) / (Σ accepted under the gated regime)
gated regime at θ: apply proposals with confidence ≥ θ (their adaptive-arm outcome);
                  decline proposals with confidence < θ (their static-arm counterfactual outcome).
```

`cpvo_gated(0)` is the pure adaptive-arm result (apply everything); `cpvo_gated(1)` is the pure
static-arm result (decline everything). The analysis is computed from the **recorded proposals +
outcomes** (§5), is **EXPLORATORY (post-hoc, labelled as such — the pre-registration fixes no
threshold it cannot know)**, and the verdict is **descriptive at the campaign's n**. The abstention
rule does not change the non-inferiority margin; it is a second, independent reported outcome.

---

## 3. Coverage analysis — the stimulus classes × arms × repetitions

**Grid shape:** six stimulus classes (the `correct / incorrect / irrelevant / competing / absent /
unseen-family` set of spec hard-rule 4), the absent class carrying its two pinned variants
(absent-clean, absent-defective). Each class × each arm × **2 repetitions** → **24 cells**,
12 static / 12 adaptive. The absent block's 4 cells are 1 static + 1 adaptive per variant
(2 variants). This coverage satisfies the 2b-registered power requirement by carry-over: the grid
contains **≥ 6 defect-bearing cells per arm** (correct 2 + competing 2 + absent-defective 1 +
unseen-family 2 = **7 per arm**), the 2b power threshold (n ≥ 6 defect-bearing → ≥ 18 cells) at
the measured conversion effect. Per-class inference is descriptive (n=2 per arm per class).

**Budget arithmetic (fits the $30 stop budget, `cap_adaptive_2c.yaml` `stop.budget_usd`):** 2b's
measured per-cell cost range is $0.0057–$0.0169; 24 cells at that range ≈ **$0.14–$0.41**. The
campaign's own wrapper phases (p0–p5, the flash orchestrator) dominate, as they did in 2b
($0.1744 total on 18 cells + phases). p1's measured E4 cell produces the FORECAST (measured × 2)
used by p2's per-cell guard; a cell whose forecast exceeds the envelope or the stop budget is
stopped and recorded as not-run (never dropped silently).

**Seed app (shared, all classes):** a fresh disposable worktree seeded with the tiny calc package
— `calc.py` (`add`, `subtract`) and `test_calc.py` (`test_add`, `test_subtract`). Language python,
model `deepseek/deepseek-v4-pro`, backend opencode, full seam (`--change-analysis`
[`--change-analysis-graph`]). Each class's implement phase is specified so the change produces the
class's expected measured facts; the **falsifiability contract** below states what proves the
class instantiated. A cell whose measured facts do not instantiate its class is a **construction
failure** — flagged + recorded as such, never re-labelled to a different class and never silently
passed (p5 attacks this first).

### Class 1 — `correct` (a real defect; the 2b-critical shape)

- **Construction (the 2b critical cell, reused verbatim):** add `classify(value)` to `calc.py` with
  a deep nested decision tree (≥ 20 branches across ≥ 4 nesting levels → cognitive complexity >
  15 → **`python:S3776` CRITICAL** on this server's profile) **and one real defect**: the boundary
  at `[10, 20)` uses `>` instead of `>=`, so `classify(10.0)` is misclassified. Add
  `test_classify` asserting the boundary contract, including `classify(10.0)`.
- **Expected measured facts:** `new_sonar_critical_count = 1` (S3776, severity-filtered
  BLOCKER/CRITICAL — the reachable critical surface, pinned in `cap_2a_rerun2_measurement_design.md`
  §1 R1.8/R1.11); `changed_symbol_count ≥ 1`; `code_change_risk` measurable.
- **Expected proposal:** **`rework`, depth 3** (has_critical branch — the proposal is correct).
- **Outcome:** defect present (the boundary test fails → `test_executed_success = false`,
  `defect_present_on_final_commit = true`). **Static**: not accepted; 1 escaped defect →
  wrong-continue harm **$0.046109 @ 11.47 / $0.112588 @ 28**. **Adaptive**: applies the rework as
  ONE bounded pass over the proposal scope; if the defect is fixed (2b measured q = 1.0 at n=3),
  accepted, no harm.

### Class 2 — `incorrect` (false-positive VERIFY on a clean change, built via the tests-ratio term)

- **Construction (defect-free; the arithmetic SHOWN):** `calc.py`: modify `add(a, b)` with a
  **behavior-preserving** body change (`return a + b` → `result = a + b; return result`). Add a NEW
  module `widgets.py` with **19 trivial pure functions** `widget_1(x) … widget_19(x)` (each returns
  a constant or an identity) and **NO `test_widgets.py`**. No defect, no S3776 complexity, no S1244
  float-`==`, no LSP errors.
- **Expected measured facts:** `changed_symbol_count = 20` (`add` + 19 widgets); TESTED_BY marks
  every `calc.py` symbol tested (its test file exists) but **no** `widgets.py` symbol tested →
  `changed_symbols_with_tests_ratio = 1/20 = 0.05`; `new_sonar_critical_count = 0`,
  `new_lsp_error_count = 0`; `impacted_symbol_count ≥ 1` (structurally guaranteed: the seeded
  `test_add` calls the modified `add`, so the 1-2 hop dependent set is non-empty).
- **Expected risk arithmetic (all four terms measurable):**

  ```
  risk = [ 0.35·0 + 0.25·0 + 0.20·(1 − 0.05) + 0.20·min(1, impacted/10) ] / 1.0
       = 0.19000 + 0.02·min(10, impacted)
       ≥ 0.21000          (impacted ≥ 1, structurally guaranteed)
  ```

  → `risk ≥ VERIFY_RISK_THRESHOLD 0.2` → **`verify`, depth 2** (0.2 ≤ risk < 0.3). The tests-ratio
  term is the **decisive** term: without it (`ratio = 1.0`) risk = 0.02 < 0.2 → `continue`.
  **Renormalization is robust:** analyzers-down (weights over tests+impacted) → risk ≥ 0.475;
  graph-down (weights over sonar+lsp+tests) → 0.19000/0.80 = 0.2375; both down → 0.19000/0.20 =
  0.95. The only state that fails is `impacted = 0` with analyzers up (0.19), which the structural
  guarantee (a seeded test calls the changed `add`) excludes.
- **False-positive REWORK is not constructible** under the severity filter — stated as a **filter
  strength** (see §1 component 1). This class therefore measures the constructible false-positive:
  the wasted **verify** pass.
- **Outcome:** clean in both arms (no defect → accepted on test_runner). **Static**: accepted, no
  harm. **Adaptive**: applies the verify as ONE pass over the proposal scope → accepted but pays
  the extra pass → **wrong-apply harm = the measured pass-cost delta** (adaptive cell cost minus
  its matched static cell cost). The falsifiability contract: if the emitted proposal is **not**
  verify on the clean change, the cell did not instantiate the class → construction failure,
  flagged + recorded.

### Class 3 — `irrelevant` (a trivial, fully-tested change — the gate's correct null)

- **Construction (the 2b clean cell, reused verbatim):** add `product(values)` to `calc.py`
  (product of a non-empty list, `ValueError("empty values")` guard) **with** `test_product`
  asserting `product([1, 2, 3, 4]) == 24`. A trivial, low-value change; no defect.
- **Expected measured facts (measured identically in 2b's clean cells):** `changed_symbol_count =
  2`, `changed_symbols_with_tests_ratio = 0.5`, `impacted_symbol_count = 4`,
  `new_sonar_critical_count = 0`, `new_lsp_error_count = 0`, `code_change_risk = 0.18 < 0.2`
  (2b `p2_cells_run.json` facts, verbatim).
- **Expected proposal:** **`continue`, depth 0** (risk < 0.2 — the correct null). *Construction
  note:* the campaign spec's parenthetical describes irrelevant as "a trivial change the verifier
  proposes verify on"; under the pinned action tree a properly-tested trivial change lands *below*
  `VERIFY_RISK_THRESHOLD` (its tests-ratio term is ~0), so the constructible irrelevant proposal is
  `continue`. This deviation from the parenthetical is grounded in the pinned machinery and stated
  here; the class's claim is **value-neutrality** (the gate adds neither cost nor missed defects on
  changes that don't matter).
- **Outcome:** accepted in both arms, no harm either arm. Adaptive application = provable null
  (`continue`). The class isolates the "gate on an irrelevant change costs nothing" leg of the
  boundary.

### Class 4 — `competing` (two defects in one change — ambiguous scope; the pinned one-of-two semantics)

- **Construction:** add `classify(value)` to `calc.py` with a deep nested decision tree (S3776
  CRITICAL, as class 1) **and TWO real boundary defects in the same changed scope**: the `[10, 20)`
  boundary uses `>` for `>=` (10.0 → wrong label) **and** the `[20, 30)` boundary uses `>` for
  `>=` (20.0 → wrong label). Add `test_classify` asserting both boundaries.
- **Expected measured facts:** `new_sonar_critical_count = 1` (S3776) →
  **`rework`, depth 3**; proposal `scope` = the bounded neighborhood (the changed symbols — both
  defects are inside `classify`, so the scope **contains the realized scope**).
- **Pinned one-of-two semantics (spec hard-rule 4b(a), registered verbatim):** the evaluator counts
  **BOTH** defects; a rework proposal **hits** only when its scope contains the realized scope AND
  both defects are fixed; **one-of-two fixed = partial_rework** with harm = the unfixed defect's
  E_x-scaled cost; **accepted requires BOTH defects absent**.
- **Outcome:** **Static**: not accepted; 2 escaped defects → wrong-continue harm **2 × $0.046109 =
  $0.092218 @ 11.47 / 2 × $0.112588 = $0.225176 @ 28**. **Adaptive**: ONE bounded rework pass;
  both fixed → accepted, no harm; one fixed → partial_rework, not accepted, harm = 1 × E_x ×
  $0.004021 for the unfixed defect; none fixed → not accepted, 2 escaped defects' harm.

### Class 5 — `absent` (no proposal emitted — the seam refuses): the two pinned variants

- **5a. absent-clean.** A **clean change** (add one trivial pure helper `widget(x)` returning `x`
  in a NEW module `widgets.py`, no test file → `tested_changed = 0`, ratio deferred) run with the
  change-analysis seam in a **designed degraded state** (sonar + lsp unavailable AND graph
  unavailable). With no analyzer counts, no tests ratio, and no impacted set, **no risk term is
  measurable** → `code_change_risk` is omitted → `build_verify_proposal` **raises** (the "refuse
  to run" contract). *Construction note:* the refusal is the only reliable absent trigger on a
  clean change — with the analyzers up, `risk` is always measurable (the sonar/lsp zero-terms are
  present) and the action tree returns `continue`; and `ast_parse_coverage` is omitted only when
  `changed_files = 0` (an empty commit, gated by the NO_CHANGES runner guard). The designed
  degraded state is therefore the seam's own refuse path, exercised deliberately. The cell
  **records the refusal + the facts present** (never a hand-authored proposal). Outcome: the
  change is clean → accepted in both arms; **the refusal is value-preserving** (recorded). No harm.
- **5b. absent-defective (the abstention-harm case).** A **real defect** (a wrong-operation defect:
  `wrong_op(a, b)` in a NEW module `widgets.py` returns `a + b` where documented `a - b`; no test
  file → `tested_changed = 0`, ratio deferred) run with the change-analysis seam in the **same
  designed degraded state** (sonar + lsp unavailable AND graph unavailable) → no risk term
  measurable → `code_change_risk` omitted → the seam **refuses**. The cell records the refusal +
  the facts present. Outcome: the defect escapes in **both** arms → not accepted, wrong-continue
  harm **$0.046109 @ 11.47 / $0.112588 @ 28** in each. This is the abstention question's harm
  side: when the seam declines to act, a defect escapes at the E_x-scaled cost. Flagged as
  **designed** (this variant deliberately exercises the refusal path on a defective change; it is
  distinct from an accidental graph/analyzer-down flag, which the campaign still never drops). The
  variant's independent variable vs absent-clean is the clean-vs-defective change; the refusal
  mechanism is identical.

### Class 6 — `unseen-family` (a defect outside the enumerated calibrated families)

- **The calibrated families (enumerated from `workflows/operations/cap_2a_cell_*.yaml` + the
  rerun2/2b cells; this list is the campaign's closed check-set):**
  1. **boundary-compare** — an inverted boundary comparison (the critical cell's defect: `>` for
     `>=` at `[10, 20)`, `cap_2a_cell_critical.yaml`);
  2. **S1244 float** — direct float `==` comparison (the style cell's finding, `python:S1244`
     MAJOR/type BUG, `cap_2a_cell_style.yaml`; pinned in the rerun2 probes R1.5/R1.10);
  3. **S3776 complex-method** — cognitive complexity > 15 (the critical cell's CRITICAL
     CODE_SMELL, threshold 15, pinned in R1.11).
- **Construction (specified OUTSIDE the enumerated families):** a **mutation/aliasing defect** in a
  new `tally(scores)` function (`calc.py`): documented to return a new descending-sorted list
  **without modifying the input**, implemented with `scores.sort(reverse=True); return scores` →
  mutates the caller's list. The defect's family is **ordering/mutation**, not any calibrated
  family. Add `test_tally` asserting the input list is unchanged (the test fails → defect caught).
- **Why the verifier misses it:** the change is simple (no S3776), uses no float `==` (no S1244),
  and is not a boundary-comparison error → `new_sonar_critical_count = 0`,
  `new_lsp_error_count = 0`; `changed_symbols_with_tests_ratio = 1.0` (test added) → tests term 0;
  risk ≈ `0.20·min(1, impacted/10)` → **`continue`, depth 0 (wrong-continue)**.
- **Evaluator's family-verification step (defined, mandatory):** after scoring, the post-hoc
  evaluator (a) confirms the defect is present on the immutable final commit, (b) **classifies its
  family**, and (c) verifies it is **NOT** in {boundary-compare, S1244 float, S3776 complex-method}
  — this is the class's checkable claim; a defect that turns out to be a calibrated family is a
  construction failure, flagged.
- **Outcome:** the defect escapes in **both** arms (continue = null in adaptive; adaptive applies
  nothing) → not accepted, wrong-continue harm **$0.046109 @ 11.47 / $0.112588 @ 28** in each. The
  class demonstrates adaptive's blind spot: it can only add value when it can **see** the defect.

**Coverage summary (per class × arm × rep):**

| class | variant | defect? | expected proposal | adaptive value | static value | wrong-apply | wrong-continue (per escaped defect) |
|---|---|---|---|---|---|---|---|
| correct | — | yes (1) | rework d3 | fix → accepted | escape → rejected | none | 1×E_x |
| incorrect | — | no | verify d2 (FP) | wasted pass | accepted | measured pass delta | none |
| irrelevant | — | no | continue d0 | null (accepted) | accepted | none | none |
| competing | — | yes (2) | rework d3 | both-fixed → accepted; one → partial_rework | escape → rejected | none | 1× or 2×E_x |
| absent | clean | no | refuse | value-preserving | value-preserving | none | none |
| absent | defective | yes (1) | refuse | escape → rejected | escape → rejected | none | 1×E_x (each arm) |
| unseen-family | — | yes (1) | continue d0 (wrong) | escape → rejected | escape → rejected | none | 1×E_x (each arm) |

Defect-bearing n = 7 per arm (correct 2 + competing 2 + absent-defective 1 + unseen-family 2);
clean n = 5 per arm (incorrect 2 + irrelevant 2 + absent-clean 1). Total 12 per arm, 24 cells.

---

## 4. Randomization scheme

**Design:** block-randomized by **stimulus class** (six blocks). Within each block, **exactly 50%
static / 50% adaptive** (2 static + 2 adaptive). The absent block is ordered as its two sub-variants
(clean, defective), each 1 static + 1 adaptive. Cell model and stimulus spec are identical within
each arm — the only difference between arms is the treatment (static = proposals recorded, NEVER
applied; adaptive = proposals applied exactly as proposed: rework = ONE bounded pass over the
proposal scope, verify = one pass, continue = null — provable in the commit trail).

**Committed seed (hex):** `92983f6f06f8b5a13d24ecfae87aac5b6f707b780e716a5bf434a244c3e0f252`
(derived as `sha256("cap_adaptive_2c|blocked-by-stimulus|50-50|static-vs-adaptive|20260827")` —
an honest committed seed, not a hand-picked permutation).

**Reproducibility key (p5 must re-derive the table from this):**

```python
import random
random.seed("92983f6f06f8b5a13d24ecfae87aac5b6f707b780e716a5bf434a244c3e0f252")
for cls in ("correct", "incorrect", "irrelevant", "competing", "absent", "unseen_family"):
    if cls == "absent":
        # the absent block: two sub-variants, each 1 static + 1 adaptive (no full-block shuffle)
        for variant in ("clean", "defective"):
            arms_v = ["static", "adaptive"]
            random.shuffle(arms_v)  # occurrence order = this variant's r1 cells (slots in block order)
    else:
        arms = ["static"] * 2 + ["adaptive"] * 2
        random.shuffle(arms)        # slot i (1..4) -> arms[i-1]; within-arm repetition = occurrence order
```

**Repetition labels:** within each (class, arm), cells are labelled `r1`, `r2` (the occurrence
order of that arm in the block's seeded permutation). Cell ids: `cap2c_<class>_<arm>_r<k>` (absent:
`cap2c_absent-<variant>_<arm>_r<k>`).

**The exact assignment table — pre-computed, canonical, committed here** (slot # = seeded
permutation position within the block; the execution order):

| cell_id | class | variant | arm | repetition | slot # |
|---|---|---|---|---|---|
| `cap2c_correct_adaptive_r1` | correct | — | adaptive | r1 | 1 |
| `cap2c_correct_adaptive_r2` | correct | — | adaptive | r2 | 2 |
| `cap2c_correct_static_r1` | correct | — | static | r1 | 3 |
| `cap2c_correct_static_r2` | correct | — | static | r2 | 4 |
| `cap2c_incorrect_adaptive_r1` | incorrect | — | adaptive | r1 | 1 |
| `cap2c_incorrect_adaptive_r2` | incorrect | — | adaptive | r2 | 2 |
| `cap2c_incorrect_static_r1` | incorrect | — | static | r1 | 3 |
| `cap2c_incorrect_static_r2` | incorrect | — | static | r2 | 4 |
| `cap2c_irrelevant_adaptive_r1` | irrelevant | — | adaptive | r1 | 1 |
| `cap2c_irrelevant_static_r1` | irrelevant | — | static | r1 | 2 |
| `cap2c_irrelevant_static_r2` | irrelevant | — | static | r2 | 3 |
| `cap2c_irrelevant_adaptive_r2` | irrelevant | — | adaptive | r2 | 4 |
| `cap2c_competing_static_r1` | competing | — | static | r1 | 1 |
| `cap2c_competing_static_r2` | competing | — | static | r2 | 2 |
| `cap2c_competing_adaptive_r1` | competing | — | adaptive | r1 | 3 |
| `cap2c_competing_adaptive_r2` | competing | — | adaptive | r2 | 4 |
| `cap2c_absent-clean_static_r1` | absent | clean | static | r1 | 1 |
| `cap2c_absent-clean_adaptive_r1` | absent | clean | adaptive | r1 | 2 |
| `cap2c_absent-defective_static_r1` | absent | defective | static | r1 | 1 |
| `cap2c_absent-defective_adaptive_r1` | absent | defective | adaptive | r1 | 2 |
| `cap2c_unseen_family_static_r1` | unseen-family | — | static | r1 | 1 |
| `cap2c_unseen_family_adaptive_r1` | unseen-family | — | adaptive | r1 | 2 |
| `cap2c_unseen_family_static_r2` | unseen-family | — | static | r2 | 3 |
| `cap2c_unseen_family_adaptive_r2` | unseen-family | — | adaptive | r2 | 4 |

Totals: **24 cells · 12 static · 12 adaptive · 4 cells per class block · 7 defect-bearing cells
per arm**. Arm labels come from this committed seed + block scheme, **never** from the model's
choice and never post-hoc. **E4** (the p1 measurement cell, per the p1 prompt "the correct-class
adaptive arm first") = the first adaptive-arm cell in the correct block by slot order:
**`cap2c_correct_adaptive_r1`**. Every cell runs in a fresh worktree with a unique `FINOPS_CELL_ID`;
the proposal is emitted and validated BEFORE the outcome is recorded; p2's execution manifest lists
every cell of this table and no others.

---

## 5. Analysis plan

**Inputs:** only immutable p1/p2 artifacts; join validated on `(cell_id, class, variant, arm,
repetition)` against §4's table. A cell scored under a different arm than its assignment is
**invalid**, not corrected. Output JSON:
`experiments/results/cap_adaptive_2c/cap_adaptive_2c_score_<ts>.json` (schema
`cap_adaptive_2c_score/v1`), plus a validation result tracing every verdict number to a field.

**Per-arm estimates (with n + CI):**

| quantity | estimator | CI |
|---|---|---|
| cpvo per arm | `Σ cost / Σ accepted` over the arm's cells | bias-corrected percentile bootstrap, 10,000 resamples of cells within the arm, stratified by class block; 95% |
| cpvo ratio `r` | `cpvo_adaptive / cpvo_static` | bootstrap percentile, 95% (reported as uncertainty; the decision uses the point estimate) |
| verified-success rate per arm | `accepted / cells` | Wilson 95% |
| per-class cpvo + success | same estimators over the class's cells (n=2 per arm per class) | reported descriptively, never decided |

**Decision rule (pre-registered, §2):** `non-inferior ⟺ cpvo ratio ≤ 1.10 AND success gap ≤ 0.05`
on the pooled grid; the per-class table reports which classes push the pooled estimates. The
harm-inclusive cpvo (`(Σ cost + Σ harm) / (Σ accepted)`, harm per §1) is reported as the
asymmetric-loss-adjusted view, alongside the raw cpvo.

**The HARM table (per-cell, measured):** wrong-apply pass deltas (adaptive-minus-matched-static
cell cost, per cell) and wrong-continue escaped-defect counts × E_x × $0.004021, at **both**
E_x = 11.4671 (measured, n=1 per model) and E_x = 28 (sourced), per the 2b asymmetric-loss
practice.

**The ABSTENTION analysis plan (pre-registered method; exploratory threshold search):**

1. Every proposal record (§7) carries the **measured confidence field** — the [H] per-attempt
   execution-confidence of the attempt whose change was analyzed (the implement phase), read from
   the cell's `AgenticResult.confidence` (`opencode.py:118–144`: 0.0 on error; else
   `tests_passed / tests_total` when tests ran; else the tool-call success fraction; `None` with no
   signal). A proposal record **without** the confidence field is **invalid** for the abstention
   analysis — flagged, **never imputed**.
2. Bin all 24 recorded confidences into deciles d ∈ [0,0.1) … [0.9,1.0].
3. Per decile d: **value(apply; d)** = cpvo over the adaptive-arm cells in d
   (`Σ cost / Σ accepted`); **value(abstain; d)** = cpvo over the static-arm cells in d (the same
   classes' declined outcomes — the static arm IS the abstain counterfactual, block-randomized).
   The harm-inclusive variants `(Σ cost + Σ harm)/Σ accepted` are reported alongside.
4. **Threshold curve (exploratory, post-hoc, labelled):** `cpvo_gated(θ)` per §2 over
   θ ∈ {0} ∪ {observed unique confidences} ∪ {1}; the verdict reports whether any θ ∈ (0,1) yields
   `cpvo_gated(θ) < cpvo_gated(0)` — i.e., whether confidence-gated abstention would have improved
   value, and at which observed threshold. **Descriptive at the campaign's n; no threshold is fixed
   here.**

**Expected-effect checks:** every adaptive-arm proposal's `expected_effect` claims are submitted to
`validate_expected_effects` where the next-phase facts are measurable (the 2b structural limit —
rework passes were not handed to a post-rework change analyzer, and `continue` = null gate leaves no
next-phase facts — is recorded as the known ceiling, carried forward).

**Pre-registered contingency:** if the pooled decision rule does not decide (defect-bearing n below
the carry-over requirement, or the ratio CI straddling the margin), the plan extends the grid under
the **same** block scheme + a documented seed extension (e.g. a third repetition per class block),
re-running both arms' new cells — the margin, outcome metric, and class definitions are **not**
re-opened.

---

## 6. Authorization boundary

**A 2c finding authorizes a DESIGN CHANGE to the gate's application policy — and nothing else.**
Concretely, this pre-registration and any subsequent verdict:

- authorize a design-review conversation about **confidence-gated abstention** (decline to apply
  when proposal confidence < θ) and any other application-policy change the boundary verdict
  motivates;
- do **not** launch the regime itself — 2c never flips `control_route`, never arms actuation,
  never writes a policy that applies proposals outside this pilot, and never escalates adaptive
  control into production;
- do **not** modify the treatment: `verify_proposal.py`, `_risk_depth`, `VERIFY_RISK_THRESHOLD`,
  `RISK_WEIGHTS`, or the severity filter stay code-unchanged (spec hard-rule 10).

If the campaign shows adaptive stays non-inferior under proposal heterogeneity, the design review
receives: the pooled + per-class tables, the harm table, the abstention curve, and this
authorization statement. If a class breaks non-inferiority, that is the boundary finding the design
review acts on (a design change proposal, not an activation).

---

## 7. Confidence-recording requirement (restated for p2's cell records)

Restated so p2's records provably satisfy spec hard-rule 4b(c):

- Every cell's proposal record MUST carry the measured confidence field (the [H] per-attempt
  execution-confidence of the analyzed attempt — §5 step 1). The 2b proposal records carry **no**
  confidence field (verified: `experiments/results/cap_2b/proposals/77407338625fb177.json` has no
  such field); **2c's cell records must add it**, or the cell is flagged invalid for the abstention
  analysis.
- A record without the field is **flagged, never imputed**; `None` (no signal: no error, no tests,
  no tool calls) is recorded as `null` and excluded from the decile bins (with its count reported).
- The confidence is recorded at proposal-emission time (BEFORE the outcome is known) so it is a
  genuine predictor, not a post-hoc label.

---

## Guard (provenance of every number)

Every number in §0–§6 derives from a cited artifact with its SHA256 (header) or from the pinned
machinery's arithmetic, shown inline:

- **VERIFY_RISK_THRESHOLD 0.2, action tree, `_risk_depth`, refuse contract** = `verify_proposal.py`
  (lines 61, 143–150, 169–255).
- **risk formula weights 0.35/0.25/0.20/0.20, renormalization, severity filter, ratio deferral** =
  `code_change_facts.py` (module docstring + `RISK_WEIGHTS`) + `workflow_runner.py` (severity
  filter) + `language.py` (TESTED_BY rule).
- **$0.004021, E_x 11.4671/12.5134, loss $0.046109/$0.112588** = escalation score JSON
  `base_downstream_defect_cost_usd`, `per_model[].E_x`, `loss_table`.
- **ratio 0.7857, success gap −0.3333, per-arm cpvo, per-cell cost range, conversion q = 1.0** =
  2b score JSON `decision_rule`, `per_arm`, `per_cell[].cost_usd`, `defect_bearing`.
- **incorrect-class risk 0.19 + 0.02·min(10, impacted) ≥ 0.21** = the §0 formula applied to the
  §3 construction's expected facts (ratio 1/20), shown in full.
- **Base rate / defect-bearing n (7/arm)** = the §3 coverage construction (classes 1, 4, 5b, 6 are
  defect-bearing by construction).
- **Seed + assignment table** = concrete hex `92983f6f…` with the reproducibility key and the full
  24-row table committed in §4 — no placeholders, no run-time randomization.
- **Budget ≈ $0.14–$0.41 vs $30 stop** = 2b measured cell-cost range × 24 cells; the $30 stop from
  `cap_adaptive_2c.yaml` `stop.budget_usd`.

## LOG

Pre-registration complete and internally consistent: primary cpvo + verified-success + the
per-cell HARM model (wrong-apply measured pass delta; wrong-continue E_x × $0.004021 at 11.47/28,
n=1-per-model sensitivity stated); the 2b non-inferiority margin reused on the pooled grid plus the
new descriptive abstention rule; the six-class coverage grid with buildable class definitions
grounded in the pinned machinery (tests-ratio false-positive VERIFY construction with the arithmetic
shown, the unconstructible false-positive REWORK stated as a filter strength, the enumerated
calibrated families with the evaluator's family-verification step, the competing one-of-two
semantics, the two absent variants); the committed seed + full 24-cell assignment table; the
abstention analysis plan (per-decile value(apply) vs value(abstain), exploratory threshold search);
the authorization boundary (design change only); the confidence-recording requirement restated.
**PASS** — committing before any cell runs.
