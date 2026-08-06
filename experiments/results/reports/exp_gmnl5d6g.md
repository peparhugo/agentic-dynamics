# Game Report: standardized_build-perturbed

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [standardized_build] deepseek...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-06T22:25:07

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.786

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.50) and found a novel correct solution (novelty=0.72, correctness=100%). Cost: $0.0200, ~5226J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.501 |
| Architecture div [H] | 0.667 |
| Structure div [H] | 0.059 |
| Thinking ratio [C] | 11.0% |
| Quality/$ [C] | 50 |
| Quality/J [C] | 0.0002 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 43% (3/7 constraints) |
| Lines of code [M] | 558 |
| Cyclomatic complexity [C] | 69.0 |
| Code quality [H] | 0.179 |
| Novelty vs baseline [H] | 0.723 |
| **Composite [H]** | **0.623** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 22,492 |
| Completion tokens [M] | 7,345 |
| Reasoning tokens [M] | 3,696 |
| Cache read tokens [M] | 181,760 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **33,533** |
| Thinking ratio [C] | 11.0% |
| Output efficiency [C] | 21.9% |
| Input cost [M] | $0.003035 |
| Output cost [M] | $0.004038 |
| Reasoning cost [M] | $0.000259 |
| Cache cost [M] | $0.012717 |
| **Total cost** | **$0.020049** |
| **Total energy [X]** | **~5226 J** |
| Solution density [C] | 0.016640 LOC/tok |
| Correctness/$ [C] | 25 |
| Quality/J [C] | 0.000119 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.0200  |  **Energy:** ~5226J  |  **Thinking:** 11%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_gmnl5d6g/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 6 |
| Total lines (Py) | 558 |
| Functions | 47 |
| Classes | 5 |
| Functions/file | 7.8 |
| Classes/file | 0.8 |
| Avg lines/file | 93 |
| Type hints | 6% |
| Docstrings | 0% |
| Error handlers | 9 |
| Imports | 25 |
| Decorators | 2 |
| Test files | 1 |
| Test file rate | 17% |
| Parse errors | 0 |
