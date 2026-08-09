# Game Report: remove_critical_constraint_s0.5_r2-perturbed

**Model:** openai/gpt-5.6-fast  |  **Task:** [remove_critical_constraint_s0.5_r2] gpt_gather_gpt_5_6_fast...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:30:41

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.829

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.74) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.7548, ~1866J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.736 |
| Architecture div [H] | 0.800 |
| Structure div [H] | 0.417 |
| Thinking ratio [C] | 8.1% |
| Quality/$ [C] | 1 |
| Quality/J [C] | 0.0005 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (12/12 tests) [M] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 441 |
| Cyclomatic complexity [C] | 72.0 |
| Code quality [H] | 0.227 |
| Novelty vs baseline [H] | 0.971 |
| **Composite [H]** | **0.798** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 39 |
| Completion tokens [M] | 6,853 |
| Reasoning tokens [M] | 610 |
| Cache read tokens [M] | 121,475 |
| Cache write tokens [M] | 14,810 |
| **Total tokens** | **7,502** |
| Thinking ratio [C] | 8.1% |
| Output efficiency [C] | 91.3% |
| Input cost [M] | $0.000196 |
| Output cost [M] | $0.275679 |
| Reasoning cost [M] | $0.024539 |
| Cache cost [M] | $0.454356 |
| **Total cost** | **$0.754770** |
| **Total energy [X]** | **~1866 J** |
| Solution density [C] | 0.058784 LOC/tok |
| Correctness/$ [C] | 5 |
| Quality/J [C] | 0.000428 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.7548  |  **Energy:** ~1866J  |  **Thinking:** 8%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_dm1gxwnd/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 4 |
| Total lines (Py) | 441 |
| Functions | 36 |
| Classes | 0 |
| Functions/file | 9.0 |
| Classes/file | 0.0 |
| Avg lines/file | 110 |
| Type hints | 22% |
| Docstrings | 0% |
| Error handlers | 4 |
| Imports | 21 |
| Decorators | 20 |
| Test files | 2 |
| Test file rate | 50% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 12 |
| Failed | 0 |
| Errors | 0 |
| Total | 12 |
| Pass rate | 100% |
| Duration | 3.2s |
