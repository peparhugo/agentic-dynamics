# Game Report: perturbed-baseline

**Model:** deepseek/deepseek-v4-pro  |  **Task:** [silent_sweep:perturbed:forced] DeepSeek_v4_Pro...
**Operator:** baseline (baseline, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-30T18:48:28

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** CONSERVATIVE
**Score:** 0.767

**Verdict:** CONSERVATIVE — model maintained sound reasoning (correctness=100%, quality=0.71) with moderate resource use ($0.0357, ~14323J). Model absorbed the perturbation without divergence.

**Recommendation:** Reliable but not novel. Good for production, not for exploration.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | nan |
| Architecture div [H] | nan |
| Structure div [H] | nan |
| Thinking ratio [C] | 52.7% |
| Quality/$ [C] | nan |
| Quality/J [C] | nan |
| Converged back [H] | None |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (0/0 tests) [H] |
| Constraint satisfaction [H] | 86% (6/7 constraints) |
| Lines of code [M] | 862 |
| Cyclomatic complexity [C] | 89.0 |
| Code quality [H] | 0.116 |
| Novelty vs baseline [H] | 0.500 |
| **Composite [H]** | **0.705** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,735 |
| Completion tokens [M] | 12,029 |
| Reasoning tokens [M] | 23,102 |
| Cache read tokens [M] | 376,064 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **43,866** |
| Thinking ratio [C] | 52.7% |
| Output efficiency [C] | 27.4% |
| Input cost [M] | $0.002464 |
| Output cost [M] | $0.010179 |
| Reasoning cost [M] | $0.019549 |
| Cache cost [M] | $0.003536 |
| **Total cost** | **$0.035727** |
| **Total energy [X]** | **~14323 J** |
| Solution density [C] | 0.019651 LOC/tok |
| Correctness/$ [C] | 12 |
| Quality/J [C] | 0.000049 |

---

## Headline Metric
**Strategy:** CONSERVATIVE  |  **Correctness:** 100%  |  **Cost:** $0.0357  |  **Energy:** ~14323J  |  **Thinking:** 53%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_swp_DeepSeek_fp/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 22 |
| Total lines (Py) | 862 |
| Functions | 103 |
| Classes | 7 |
| Functions/file | 4.7 |
| Classes/file | 0.3 |
| Avg lines/file | 39 |
| Type hints | 0% |
| Docstrings | 0% |
| Error handlers | 14 |
| Imports | 67 |
| Decorators | 33 |
| Test files | 8 |
| Test file rate | 36% |
| Parse errors | 0 |
