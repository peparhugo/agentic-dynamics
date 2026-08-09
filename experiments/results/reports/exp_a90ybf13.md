# Game Report: inject_phantom_success_s0.5_r2-perturbed

**Model:** openai/gpt-5.5  |  **Task:** [inject_phantom_success_s0.5_r2] gpt_final_gpt_5_5...
**Operator:** perturbed (semantic, strength=0.0)
**Repetitions:** 1  |  **Timestamp:** 2026-08-09T18:24:41

---

> **Legend:** [M] measured &middot; [C] computed from measured &middot; [H] heuristic estimate &middot; [X] externally sourced

## Strategy [H]
**Classification:** EXPLORATORY
**Score:** 0.841

**Verdict:** EXPLORATORY — model escaped attractor (escape=0.73) and found a novel correct solution (novelty=0.97, correctness=100%). Cost: $0.2251, ~1822J.

**Recommendation:** Promote this operator. The perturbation succeeded.

---

## Reasoning Dynamics
| Metric | Value |
|--------|-------|
| Escape score [H] | 0.732 |
| Architecture div [H] | 0.800 |
| Structure div [H] | 0.403 |
| Thinking ratio [C] | 2.5% |
| Quality/$ [C] | 4 |
| Quality/J [C] | 0.0005 |
| Converged back [H] | False |

---

## Solution Quality
| Metric | Value |
|--------|-------|
| Correctness | 100% (7/7 tests) [M] |
| Constraint satisfaction [H] | 100% (7/7 constraints) |
| Lines of code [M] | 247 |
| Cyclomatic complexity [C] | 45.0 |
| Code quality [H] | 0.405 |
| Novelty vs baseline [H] | 0.970 |
| **Composite [H]** | **0.877** |

---

## Resource Efficiency
| Metric | Value |
|--------|-------|
| Prompt tokens [M] | 8,383 |
| Completion tokens [M] | 4,351 |
| Reasoning tokens [M] | 320 |
| Cache read tokens [M] | 86,016 |
| Cache write tokens [M] | 0 |
| **Total tokens** | **13,054** |
| Thinking ratio [C] | 2.5% |
| Output efficiency [C] | 33.3% |
| Input cost [M] | $0.021256 |
| Output cost [M] | $0.088257 |
| Reasoning cost [M] | $0.006491 |
| Cache cost [M] | $0.109049 |
| **Total cost** | **$0.225053** |
| **Total energy [X]** | **~1822 J** |
| Solution density [C] | 0.018921 LOC/tok |
| Correctness/$ [C] | 9 |
| Quality/J [C] | 0.000481 |

---

## Headline Metric
**Strategy:** EXPLORATORY  |  **Correctness:** 100%  |  **Cost:** $0.2251  |  **Energy:** ~1822J  |  **Thinking:** 2%

---

## Artifacts

Raw session transcript and generated source code for independent verification.

- [Generated code](./exp_a90ybf13/code/)

---

## Code Quality

| Metric | Value |
|--------|-------|
| Python files | 4 |
| Total lines (Py) | 247 |
| Functions | 30 |
| Classes | 1 |
| Functions/file | 7.5 |
| Classes/file | 0.2 |
| Avg lines/file | 62 |
| Type hints | 35% |
| Docstrings | 0% |
| Error handlers | 5 |
| Imports | 12 |
| Decorators | 18 |
| Test files | 2 |
| Test file rate | 50% |
| Parse errors | 0 |


---

## Pytest Results

| Metric | Value |
|--------|-------|
| Passed | 7 |
| Failed | 0 |
| Errors | 0 |
| Total | 7 |
| Pass rate | 100% |
| Duration | 0.9s |
